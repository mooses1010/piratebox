#include "sensors.h"
#include <math.h>

bool pb_sensor_temp_internal_init() {
    // temperatureRead() (arduino-esp32 core) returns NAN if the
    // on-die temperature sensor peripheral isn't available on this
    // chip variant - checked once at boot so an unsupported chip
    // simply never advertises this capability, rather than reporting
    // "ok:false" forever on every subsequent read.
    float t = temperatureRead();
    return !isnan(t);
}

bool pb_sensor_temp_internal_read(float &outCelsius) {
    float t = temperatureRead();
    if (isnan(t)) {
        return false;
    }
    outCelsius = t;
    return true;
}
