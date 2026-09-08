// DS18B20 multi-device 1-Wire temperature bus driver.
//
// PREPARED, NOT YET WIRED: as of this firmware revision, no DS18B20
// hardware is physically connected - four waterproof probes exist but
// remain unwired pending the operator's physical commissioning gate
// (docs/ESP32-SUPERVISOR-DESIGN.md §16b). Exactly like bh1750.cpp
// before its own migration, this driver's init() performs a real bus
// search; if nothing responds (the current, expected state), zero
// probes are ever reported - never a fake/phantom entry.
//
// GENUINE MULTI-DEVICE 1-WIRE BUS, NOT FOUR HARDCODED INPUTS: probes
// are identified by their own 64-bit 1-Wire ROM address (family code +
// 48-bit serial + CRC8), read via a real bus search
// (OneWire::search()), never by physical position on the wire. Up to
// MAX_PROBES may be tracked at once - four are expected, the headroom
// above that costs nothing and avoids an arbitrary-feeling exact-4
// limit.
//
// NON-BLOCKING BY DESIGN: DS18B20 conversion takes ~750ms at 12-bit
// resolution. This driver never calls delay() - pb_ds18b20_tick(now)
// is a small state machine (advance() below) called every main-loop
// iteration; it returns almost immediately except for the few
// microseconds of real 1-Wire bus I/O, and the ~750ms conversion wait
// is tracked by comparing millis() timestamps, not by blocking. This
// is the same non-blocking discipline the task watchdog and heartbeat
// timing already depend on (main.cpp never blocks for any one sensor).
//
// POLLING CADENCE: a full read cycle (broadcast convert -> wait ->
// read every known probe) runs every DS18B20_CYCLE_INTERVAL_MS -
// environmental/enclosure temperature does not change fast enough to
// need frequent updates, and 1-Wire bus traffic has a real (if small)
// cost. A full bus RE-SEARCH (to notice a probe added or removed) runs
// far less often than that - see DS18B20_RESCAN_EVERY_N_CYCLES -
// since discovering the bus topology is the more expensive, more
// disruptive-if-mistimed operation of the two.
//
// KNOWN DS18B20 REALITIES THIS DRIVER ACCOUNTS FOR:
//   - CRC validation: handled inside DallasTemperature::getTempC()
//     itself (it returns DEVICE_DISCONNECTED_C on a CRC mismatch) -
//     not re-implemented here.
//   - DEVICE_DISCONNECTED_C (-127.0): reported as ok=false, not as a
//     real (and absurd) sub-zero reading.
//   - The well-known 85.0C power-on/uninitialized scratchpad value:
//     a real 12-bit conversion is affected by enough analog noise that
//     landing on EXACTLY 85.0 from a genuine reading is vanishingly
//     unlikely - treated as suspect (ok=false) rather than trusted.
//   - Individual probe failure never affects other probes or the rest
//     of the firmware - each probe's ok/err is independent.
//
// PARASITE POWER: not supported or accounted for - this project uses
// conventional powered three-wire DS18B20 wiring (VCC/DATA/GND) by
// deliberate choice (docs/ESP32-SUPERVISOR-DESIGN.md §16b) - no
// compelling reason to add parasite-power complexity.
#pragma once

#include <Arduino.h>

#define DS18B20_MAX_PROBES 8
#define DS18B20_ROM_HEX_LEN 16  // 8 bytes -> 16 hex chars, no separators

struct Ds18b20Probe {
    char romHex[DS18B20_ROM_HEX_LEN + 1];
    bool ok;
    float value;      // valid only if ok
    const char *err;  // valid only if !ok - a short, stable string literal
};

// Call once from setup(). Performs a real bus search - returns true if
// the 1-Wire bus itself initialized (regardless of whether any probes
// were found - "bus present, zero probes" is a valid, expected state,
// not a failure).
bool pb_ds18b20_init();

// Call every main-loop iteration. Cheap when idle; advances the
// internal non-blocking state machine.
void pb_ds18b20_tick(unsigned long nowMs);

// Current known probe count (0..DS18B20_MAX_PROBES) and read-only
// access to each - for building the "sensors" protocol message.
int pb_ds18b20_probe_count();
const Ds18b20Probe &pb_ds18b20_probe_at(int index);

// True unless the bus has REGRESSED from "has previously found at
// least one probe" to "finds none now" - see this file's header.
// Always true if no probe has ever been found (that's "not wired yet",
// not a fault).
bool pb_ds18b20_bus_ok();

// True the instant pb_ds18b20_init() finds real hardware (or a later
// rescan does) - governs whether the "ds18b20" capability is ever
// advertised at all. Unlike bh1750/temp_internal, this reflects "the
// bus itself has ever had a device," not "exactly one fixed sensor is
// present" - see docs/ESP32-SUPERVISOR-DESIGN.md for why DS18B20 gets
// its own capability-presence rule.
bool pb_ds18b20_ever_found_a_probe();
