#include "ds18b20.h"
#include <OneWire.h>
#include <DallasTemperature.h>
#include <string.h>
#include <math.h>

// GPIO4: see docs/ESP32-SUPERVISOR-DESIGN.md §7a for the full pin-map
// rationale (free on this board, not a strapping pin, not used by
// flash/PSRAM QSPI, not shared with the existing I2C bus on GPIO8/9).
#define DS18B20_ONE_WIRE_PIN 4

// Full read cycle (broadcast convert -> wait -> read every known
// probe): every 30s. Environmental/enclosure temperature does not
// need faster updates, and this bounds 1-Wire bus traffic.
static const unsigned long DS18B20_CYCLE_INTERVAL_MS = 30000;

// 12-bit resolution (DallasTemperature's default) needs up to ~750ms
// to convert - a fixed, generous constant rather than calling
// millisToWaitForConversion() every cycle (that value never changes
// since resolution is never changed after begin()).
static const unsigned long DS18B20_CONVERSION_WAIT_MS = 750;

// A full bus re-search (to notice a probe added/removed) runs once
// every 10 full read cycles (~5 minutes) - far less often than an
// ordinary read, since walking the whole bus topology is the more
// disruptive of the two operations to get wrong mid-conversion.
static const int DS18B20_RESCAN_EVERY_N_CYCLES = 10;

// DS18B20-family 1-Wire family codes accepted: 0x28 (DS18B20 itself),
// plus 0x22 (DS1822) and 0x10 (DS18S20) - common compatible variants
// sometimes sold as "DS18B20-style" probes/clones. DallasTemperature's
// own getTempC() already knows how to read all three families'
// scratchpad formats correctly - this is purely a discovery-time
// filter so an unrelated 1-Wire device accidentally on the same bus
// isn't mistaken for a temperature probe.
static bool isKnownTemperatureFamily(uint8_t familyCode) {
    return familyCode == 0x28 || familyCode == 0x22 || familyCode == 0x10;
}

static OneWire oneWire(DS18B20_ONE_WIRE_PIN);
static DallasTemperature sensors(&oneWire);

enum class Ds18b20State { Idle, Converting };
static Ds18b20State state = Ds18b20State::Idle;
static unsigned long lastCycleAt = 0;
static unsigned long convertStartedAt = 0;
static int cycleCount = 0;

static DeviceAddress knownAddresses[DS18B20_MAX_PROBES];
static Ds18b20Probe probes[DS18B20_MAX_PROBES];
static int probeCount = 0;
static bool busOk = true;
static bool everFoundAnyProbe = false;

static void romToHex(const DeviceAddress addr, char *out) {
    static const char *hexDigits = "0123456789abcdef";
    for (int i = 0; i < 8; i++) {
        out[i * 2] = hexDigits[(addr[i] >> 4) & 0x0F];
        out[i * 2 + 1] = hexDigits[addr[i] & 0x0F];
    }
    out[16] = '\0';
}

// Real bus search - never assumes probe count or identity. Rebuilds
// the known-address list from scratch each time it's called, so a
// removed probe simply doesn't reappear (matches the "no fabricated/
// stale phantom entries" contract) and a newly added one is picked up
// on the next scheduled rescan, not instantly (see this file's header
// on rescan cadence).
static void rescanBus() {
    DeviceAddress found[DS18B20_MAX_PROBES];
    int foundCount = 0;

    oneWire.reset_search();
    DeviceAddress addr;
    while (foundCount < DS18B20_MAX_PROBES && oneWire.search(addr)) {
        if (OneWire::crc8(addr, 7) != addr[7]) {
            continue;  // corrupted ROM read - skip, don't fabricate an entry
        }
        if (!isKnownTemperatureFamily(addr[0])) {
            continue;  // some other 1-Wire device type - not ours to report
        }
        memcpy(found[foundCount], addr, sizeof(DeviceAddress));
        foundCount++;
    }

    if (foundCount == 0 && everFoundAnyProbe) {
        busOk = false;  // regression: we've seen probes before, now see none
    } else {
        busOk = true;   // either healthy, or genuinely never wired - not a fault
    }
    if (foundCount > 0) {
        everFoundAnyProbe = true;
    }

    for (int i = 0; i < foundCount; i++) {
        memcpy(knownAddresses[i], found[i], sizeof(DeviceAddress));
        romToHex(found[i], probes[i].romHex);
        probes[i].ok = false;
        probes[i].err = "not_yet_read";
    }
    probeCount = foundCount;
}

bool pb_ds18b20_init() {
    sensors.begin();
    sensors.setWaitForConversion(false);  // async - see this file's header
    rescanBus();
    return true;  // the bus itself always "initializes" - zero probes is valid
}

static void beginConversion(unsigned long nowMs) {
    sensors.requestTemperatures();  // broadcast convert to every device on the bus
    convertStartedAt = nowMs;
    state = Ds18b20State::Converting;
}

static void finishConversion() {
    for (int i = 0; i < probeCount; i++) {
        float value = sensors.getTempC(knownAddresses[i]);
        if (value == DEVICE_DISCONNECTED_C) {
            probes[i].ok = false;
            probes[i].err = "disconnected";
        } else if (fabs(value - 85.0f) < 0.001f) {
            // The well-known DS18B20 power-on/uninitialized scratchpad
            // value - a genuine 12-bit conversion essentially never
            // lands on exactly 85.0 due to real thermal noise, so this
            // is far more likely a read-before-ready glitch than a
            // real 85C reading. See this file's header.
            probes[i].ok = false;
            probes[i].err = "uninit_85c";
        } else {
            probes[i].ok = true;
            probes[i].value = value;
        }
    }
    state = Ds18b20State::Idle;
}

void pb_ds18b20_tick(unsigned long nowMs) {
    switch (state) {
        case Ds18b20State::Idle:
            if (nowMs - lastCycleAt >= DS18B20_CYCLE_INTERVAL_MS) {
                lastCycleAt = nowMs;
                cycleCount++;
                if (cycleCount % DS18B20_RESCAN_EVERY_N_CYCLES == 1) {
                    rescanBus();
                }
                if (probeCount > 0) {
                    beginConversion(nowMs);
                }
            }
            break;
        case Ds18b20State::Converting:
            if (nowMs - convertStartedAt >= DS18B20_CONVERSION_WAIT_MS) {
                finishConversion();
            }
            break;
    }
}

int pb_ds18b20_probe_count() {
    return probeCount;
}

const Ds18b20Probe &pb_ds18b20_probe_at(int index) {
    return probes[index];
}

bool pb_ds18b20_bus_ok() {
    return busOk;
}

bool pb_ds18b20_ever_found_a_probe() {
    return everFoundAnyProbe;
}
