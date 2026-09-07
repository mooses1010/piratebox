#include "bh1750.h"
#include <Wire.h>

static const uint8_t POWER_ON = 0x01;
static const uint8_t ONE_TIME_HIGH_RES_MODE = 0x20;
static const unsigned long MEASURE_DELAY_MS = 200;  // datasheet: up to ~180ms conversion time

static bool readRawLux(uint16_t &outRaw) {
    Wire.beginTransmission(PB_BH1750_ADDRESS);
    Wire.write(POWER_ON);
    if (Wire.endTransmission() != 0) {
        return false;
    }
    Wire.beginTransmission(PB_BH1750_ADDRESS);
    Wire.write(ONE_TIME_HIGH_RES_MODE);
    if (Wire.endTransmission() != 0) {
        return false;
    }
    delay(MEASURE_DELAY_MS);

    if (Wire.requestFrom((int)PB_BH1750_ADDRESS, 2) != 2) {
        return false;
    }
    uint8_t hi = Wire.read();
    uint8_t lo = Wire.read();
    outRaw = ((uint16_t)hi << 8) | lo;
    return true;
}

bool pb_sensor_bh1750_init() {
    Wire.begin(PB_I2C_SDA_PIN, PB_I2C_SCL_PIN);
    uint16_t raw;
    // One real probe at boot - the only way to know a BH1750 is
    // actually present (this sensor has no separate "who am I"
    // register to read passively). Not wired yet as of this firmware
    // revision, so this is expected to return false until the
    // operator's physical migration - see this file's header.
    return readRawLux(raw);
}

bool pb_sensor_bh1750_read(float &outLux) {
    uint16_t raw;
    if (!readRawLux(raw)) {
        return false;
    }
    outLux = raw / 1.2f;  // BH1750 datasheet's own raw-to-lux formula (matches piratebox_bh1750.py exactly)
    return true;
}
