#!/usr/bin/env python3
#
# BH1750 ambient light reader - ESP32-owned (migrated 2026-09-07). The
# physical sensor was moved from the Pi's own I2C bus to the ESP32-S3
# supervisor's I2C bus (GPIO8/SDA, GPIO9/SCL) - see docs/OPERATIONAL-
# DECISIONS.md for the full migration record and docs/ESP32-SUPERVISOR-
# DESIGN.md §16 for the wiring plan that was executed.
#
# THIS IS A DROP-IN REPLACEMENT for the retired registration of
# piratebox_bh1750.py (that module itself is UNCHANGED and still in
# the repo - see its own header, which anticipated exactly this
# migration - but nothing imports it anymore as of this file existing;
# its own I2C bus no longer has a sensor to find, so its diagnostics
# would now correctly report "not detected" if it were still queried,
# but querying real I2C hardware that's no longer expected to be there
# has no upside - retired, not deleted, for historical/rollback
# reference). SAME two-function public interface (`read_ambient_lux()`,
# `get_diagnostics()`) and SAME `get_diagnostics()` return shape, so
# piratebox_oled_daemon.py's `publish_sensors_export()` and
# `build_glance_metrics()` needed ZERO changes to their own bodies -
# only which module gets imported/registered at startup changed. This
# is exactly the design property piratebox_bh1750.py's own header
# said it was preserving for "if this migration ever happens."
#
# UNLIKE piratebox_bh1750.py, this module NEVER touches I2C or serial
# hardware directly - piratebox_esp32_supervisor.py remains the sole
# owner of the actual link (see that daemon's own header for why).
# This module only ever reads its cached export via
# piratebox_esp32_client.py - the same "one process touches real
# hardware, everything else reads a cache" discipline used everywhere
# else in this project.

import piratebox_esp32_client as _client


def read_ambient_lux():
    """Same contract as the retired piratebox_bh1750.read_ambient_lux():
    zero-argument, returns a float lux value or None - never raises,
    never fabricates a value. Register with
    register_hardware_signal("ambient_lux", read_ambient_lux)."""
    diag = _client.get_diagnostics()
    if not diag["connected"] or diag["stale"]:
        return None
    reading = diag["sensors"].get("bh1750")
    if not isinstance(reading, dict) or not reading.get("ok"):
        return None
    value = reading.get("value")
    return float(value) if isinstance(value, (int, float)) else None


def get_diagnostics() -> dict:
    """Same shape as the retired piratebox_bh1750.get_diagnostics() -
    consumed unchanged by publish_sensors_export() and
    build_glance_metrics(). `i2c_bus`/`address` are now informational
    only (the sensor sits behind the ESP32's own I2C bus, not the
    Pi's) - kept in the dict so any consumer that displays them
    verbatim still gets a sensible string instead of a missing key."""
    diag = _client.get_diagnostics()
    connected_fresh = diag["connected"] and not diag["stale"]
    reading = diag["sensors"].get("bh1750") if connected_fresh else None
    detected = isinstance(reading, dict) and reading.get("ok") is True
    lux = reading.get("value") if detected else None
    return {
        "i2c_bus": "esp32-supervisor",
        "address": "0x23",
        "detected": detected,
        "lux": lux,
        "last_success_seconds_ago": diag.get("export_age_seconds") if detected else None,
        "stale": not detected,
        "last_error": None if diag["connected"] else "esp32 supervisor not connected",
    }


if __name__ == "__main__":
    import pprint
    pprint.pprint(get_diagnostics())
