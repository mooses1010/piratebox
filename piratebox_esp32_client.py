#!/usr/bin/env python3
#
# Thin, read-only client for the ESP32-S3 hardware/sensor supervisor's
# cached export (/run/piratebox-esp32/esp32-public.json), written by
# the separate long-running piratebox_esp32_supervisor.py daemon. This
# module NEVER opens the serial port itself - see that daemon's own
# header for why only one process may ever hold that connection.
# Mirrors piratebox_bh1750.py's role (one small, single-purpose reader
# module other code imports) but reads a JSON export instead of
# polling I2C directly, since the real hardware owner here is a
# separate process, not something this module can poll on demand.
#
# Same "honest missing value, never fabricated" discipline as every
# other reader in this project: a missing/stale/corrupt export
# degrades to "not connected," never a fabricated reading.

import json
import time

EXPORT_FILE = "/run/piratebox-esp32/esp32-public.json"
STALE_AFTER_S = 30.0  # generous vs. the daemon's own 5s publish interval -
                       # allows a few missed publish cycles before treating
                       # the EXPORT ITSELF as stale (daemon stopped publishing),
                       # distinct from the "stale" flag INSIDE a fresh export
                       # (daemon running, but heartbeat from the board itself
                       # has gone quiet).


def _read_export():
    try:
        with open(EXPORT_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def get_diagnostics() -> dict:
    """Full supervisor status snapshot - what tools/diagnose_esp32_
    supervisor.py and the Environment web page both build on. Degrades
    to a single 'connected: False' shape if the export is missing,
    unreadable, or too old - never raises, never fabricates a reading."""
    data = _read_export()
    if data is None:
        return {"connected": False, "stale": True, "reason": "no_export",
                 "sensors": {}, "capabilities": []}

    age = time.time() - (data.get("generated_at") or 0)
    export_stale = age > STALE_AFTER_S
    return {
        "connected": bool(data.get("connected")) and not export_stale,
        "stale": bool(data.get("stale")) or export_stale,
        "fw_version": data.get("fw_version"),
        "protocol_version": data.get("protocol_version"),
        "board": data.get("board"),
        "mac": data.get("mac"),
        "reset_reason": data.get("reset_reason"),
        "uptime_ms": data.get("uptime_ms"),
        "reboot_count": data.get("reboot_count"),
        "capabilities": data.get("capabilities") or [],
        "sensors": data.get("sensors") or {},
        "malformed_lines": data.get("malformed_lines"),
        "export_age_seconds": round(age, 1),
    }


def read_temp_internal():
    """HARDWARE_SIGNALS reader - zero-argument, returns a float Celsius
    value or None. Register with:
    register_hardware_signal("esp32_temp_internal", read_temp_internal).
    Deliberately labeled 'temp_internal' throughout, never presented as
    an ambient/room reading - this is the ESP32-S3's own on-die sensor,
    not a calibrated environmental probe (see esp32-firmware/include/
    sensors.h's own caveat)."""
    diag = get_diagnostics()
    if not diag["connected"] or diag["stale"]:
        return None
    reading = diag["sensors"].get("temp_internal")
    if not isinstance(reading, dict) or not reading.get("ok"):
        return None
    value = reading.get("value")
    return float(value) if isinstance(value, (int, float)) else None


if __name__ == "__main__":
    import pprint
    pprint.pprint(get_diagnostics())
