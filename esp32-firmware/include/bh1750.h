// BH1750 ambient light sensor driver for the ESP32-S3 supervisor.
//
// PREPARED, NOT YET WIRED: as of this firmware revision, no BH1750 is
// physically connected to this board - it remains Pi-owned
// (piratebox_bh1750.py, I2C1 on the Pi's own GPIO2/GPIO3). This driver
// exists so the migration's SOFTWARE side is ready before the physical
// rewiring gate is requested of the operator (docs/ESP32-SUPERVISOR-
// DESIGN.md §16 and CLAUDE.md's own "don't ask for wiring before the
// software is ready" instruction). Init deliberately performs one real
// I2C probe at boot - if nothing responds (the current, expected
// state), the "bh1750" capability simply never appears in `hello`,
// exactly the same "no fake/phantom hardware" discipline
// piratebox_bh1750.py already established on the Pi side. Once the
// sensor is physically wired to this board's I2C pins, no firmware
// change is needed - the very next boot's probe succeeds and the
// capability appears on its own.
//
// Protocol mirrors piratebox_bh1750.py exactly (same opcodes, same
// timing, same raw-to-lux formula) so the two implementations report
// identically comparable values if ever run side-by-side during
// migration validation.
#pragma once

#include <Arduino.h>

// I2C pins: GPIO8 (SDA) / GPIO9 (SCL) - the standard default I2C pins
// for generic ESP32-S3 DevKitC-1 boards (this board's own PlatformIO
// board definition), deliberately NOT a strapping pin (S3 strapping
// pins are GPIO0/3/45/46 - none of these are touched here).
#define PB_I2C_SDA_PIN 8
#define PB_I2C_SCL_PIN 9

#define PB_BH1750_ADDRESS 0x23  // ADDR left floating - matches the Pi-side module's own commissioned wiring

bool pb_sensor_bh1750_init();
bool pb_sensor_bh1750_read(float &outLux);
