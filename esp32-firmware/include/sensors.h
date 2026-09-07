// Sensor abstraction - deliberately tiny today (one built-in sensor,
// nothing wired), but shaped so future sensors (BH1750 migrated from
// the Pi, DS18B20, BME280, INA226) slot in the same way: one init
// function, one read function, each independently guarded so a
// failing/absent sensor can never affect another - the same
// discipline piratebox_bh1750.py already established on the Pi side
// (docs/ESP32-SUPERVISOR-DESIGN.md "Sensor abstraction").
//
// A sensor's capability id only appears in the firmware's "hello"
// message if init() actually succeeded - this firmware must never
// claim a capability that isn't really there (same "no fake/phantom
// hardware" rule the Pi-side project already follows everywhere else).
#pragma once

#include <Arduino.h>

// ESP32-S3's own on-die temperature sensor. No wiring required - every
// unit has this. Deliberately documented as COARSE: Espressif's own
// datasheet does not characterize this peripheral as a calibrated
// ambient-temperature sensor - it drifts with CPU load/self-heating
// and is intended for rough die-temperature monitoring, not weather-
// station-grade ambient readings. Reported "as-is", labeled clearly on
// the Pi side, never presented to a visitor as a precise reading.
bool pb_sensor_temp_internal_init();
bool pb_sensor_temp_internal_read(float &outCelsius);
