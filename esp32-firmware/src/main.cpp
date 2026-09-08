// PirateBox ESP32-S3 hardware/sensor supervisor - firmware entry
// point. See docs/ESP32-SUPERVISOR-DESIGN.md for the full architecture;
// this file is deliberately thin - protocol.cpp owns wire format,
// sensors.cpp owns hardware reads, this file just wires them together
// on a timer loop plus a task watchdog.
//
// DESIGN PRINCIPLES THIS FILE FOLLOWS (see the design doc for why):
//   - The ESP32 proactively broadcasts hello/heartbeat/sensors. It
//     never blocks waiting for the Pi - a disconnected/absent/silent
//     Pi has zero effect on this loop continuing to run.
//   - A hung sensor read or any other loop stall is caught by the task
//     watchdog, which resets the chip cleanly rather than hanging
//     forever - the NEXT "hello" reports reset_reason so the Pi can
//     see *why* a reset happened, not just that one did.
//   - Serial uses the physical UART0 pins (the board's "COM" port,
//     wired to its WCH CH9102 bridge) - see platformio.ini's
//     ARDUINO_USB_MODE/ARDUINO_USB_CDC_ON_BOOT flags. The native "USB"
//     port's own peripheral is never touched by this firmware.
//   - No WiFi/BT radio is ever started - MAC is read directly from
//     efuse (esp_efuse_mac_get_default), which needs no radio
//     initialization at all. Reserved for a real future need, not
//     started "because the chip can."

#include <Arduino.h>
#include <esp_system.h>
#include <esp_mac.h>
#include <esp_task_wdt.h>

#include "protocol.h"
#include "sensors.h"
#include "bh1750.h"
#include "ds18b20.h"

// --- Timing ----------------------------------------------------------
static const unsigned long HEARTBEAT_INTERVAL_MS = 2000;
static const unsigned long SENSORS_INTERVAL_MS = 5000;
// Generous relative to both intervals above - a single slow sensor
// read must not trip the watchdog under normal conditions, only a
// genuine hang (e.g. an I2C bus lockup in a future sensor).
static const uint32_t TASK_WDT_TIMEOUT_S = 8;

static unsigned long lastHeartbeatAt = 0;
static unsigned long lastSensorsAt = 0;
static unsigned long heartbeatSeq = 0;
static unsigned long sensorsSeq = 0;

static bool tempInternalAvailable = false;
static bool bh1750Available = false;

static String inputBuffer;

static String macAddressString() {
    uint8_t mac[6] = {0};
    esp_efuse_mac_get_default(mac);
    char buf[18];
    snprintf(buf, sizeof(buf), "%02x:%02x:%02x:%02x:%02x:%02x",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
    return String(buf);
}

static String resetReasonString() {
    switch (esp_reset_reason()) {
        case ESP_RST_POWERON:   return "poweron";
        case ESP_RST_EXT:       return "ext";
        case ESP_RST_SW:        return "sw";
        case ESP_RST_PANIC:     return "panic";
        case ESP_RST_INT_WDT:   return "int_wdt";
        case ESP_RST_TASK_WDT:  return "task_wdt";
        case ESP_RST_WDT:       return "wdt";
        case ESP_RST_DEEPSLEEP: return "deepsleep";
        case ESP_RST_BROWNOUT:  return "brownout";
        case ESP_RST_SDIO:      return "sdio";
        // Newer reset-reason values (USB/JTAG/EFUSE/PWR_GLITCH/CPU_LOCKUP)
        // were added in later ESP-IDF releases than the one bundled with
        // this project's pinned espressif32 platform version (see
        // platformio.ini) - deliberately omitted rather than #ifdef'd
        // per value, since they're rare reset causes and "unknown" (the
        // default below) is an honest, safe fallback for any of them.
        default:                return "unknown";
    }
}

static void sendLine(const String &line) {
    Serial.print(line);
    Serial.print('\n');
}

static void sendHello() {
    sendLine(pb_build_hello(macAddressString(), resetReasonString(), millis(),
                             bh1750Available, pb_ds18b20_ever_found_a_probe()));
}

static void handleLine(const String &line) {
    PbParsedCommand cmd = pb_parse_command(line);
    switch (cmd.type) {
        case PbCommand::Ping:
            sendLine(pb_build_pong(cmd.nonce));
            break;
        case PbCommand::GetInfo:
            sendHello();
            break;
        case PbCommand::Unknown:
        default:
            sendLine(pb_build_err(cmd.parseError ? "bad_json" : "unknown_type"));
            break;
    }
}

static void pollSerialInput() {
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (c == '\n') {
            if (inputBuffer.length() > 0) {
                handleLine(inputBuffer);
            }
            inputBuffer = "";
            continue;
        }
        if (c == '\r') {
            continue; // tolerate CRLF sends from the host
        }
        inputBuffer += c;
        if (inputBuffer.length() > PIRATEBOX_MAX_LINE_LEN) {
            // Runaway line with no newline - drop it and resync rather
            // than growing an unbounded String on a memory-constrained
            // MCU. The next '\n' (from whatever comes after) starts a
            // fresh line normally.
            inputBuffer = "";
        }
    }
}

void setup() {
    Serial.begin(115200);

    // Older esp_task_wdt API (seconds, panic-on-timeout) - matches the
    // ESP-IDF version bundled with this project's pinned espressif32
    // platform (see platformio.ini). A newer core would offer the
    // struct-based esp_task_wdt_reconfigure() instead; this simpler
    // call is fully sufficient for this firmware's one need (a single
    // main-loop task watchdog).
    esp_task_wdt_init(TASK_WDT_TIMEOUT_S, true);
    esp_task_wdt_add(NULL);

    tempInternalAvailable = pb_sensor_temp_internal_init();
    // Real probe, not an assumption - see bh1750.cpp's header. Expected
    // to report false until the operator physically wires one; the
    // capability then appears on its own on the very next boot.
    bh1750Available = pb_sensor_bh1750_init();
    // Real bus search, not an assumption - see ds18b20.cpp's header.
    // Expected to find zero probes until the operator physically wires
    // them; the bus itself always "initializes" successfully either way.
    pb_ds18b20_init();

    // Announce identity immediately on boot - the Pi daemon does not
    // need to wait for the first heartbeat/sensors cycle to learn who
    // it's talking to, and a "hello" arriving unprompted mid-session is
    // exactly how the Pi detects an unexpected ESP32 reboot.
    sendHello();

    unsigned long now = millis();
    lastHeartbeatAt = now;
    lastSensorsAt = now;
}

void loop() {
    esp_task_wdt_reset();

    pollSerialInput();

    unsigned long now = millis();

    // Non-blocking - see ds18b20.cpp's header. Runs on its own much
    // slower internal cadence regardless of how often this outer loop
    // spins, so calling it every iteration costs nothing when idle.
    pb_ds18b20_tick(now);

    if (now - lastHeartbeatAt >= HEARTBEAT_INTERVAL_MS) {
        lastHeartbeatAt = now;
        sendLine(pb_build_heartbeat(heartbeatSeq++, now));
    }

    if (now - lastSensorsAt >= SENSORS_INTERVAL_MS) {
        lastSensorsAt = now;
        float tempC = 0.0f;
        bool tempOk = tempInternalAvailable && pb_sensor_temp_internal_read(tempC);
        float lux = 0.0f;
        bool bh1750Ok = bh1750Available && pb_sensor_bh1750_read(lux);
        // DS18B20 values are whatever its own last completed ~30s cycle
        // computed - this 5s "sensors" send just reports the latest
        // known state, it never triggers a new conversion itself.
        int probeCount = pb_ds18b20_probe_count();
        static Ds18b20Probe probeSnapshot[DS18B20_MAX_PROBES];
        for (int i = 0; i < probeCount; i++) {
            probeSnapshot[i] = pb_ds18b20_probe_at(i);
        }
        sendLine(pb_build_sensors(sensorsSeq++, tempC, tempOk, bh1750Available, lux, bh1750Ok,
                                   pb_ds18b20_ever_found_a_probe(), pb_ds18b20_bus_ok(),
                                   probeCount, probeSnapshot));
    }
}
