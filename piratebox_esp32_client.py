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


def _ds18b20_block():
    """Shared by both DS18B20 HARDWARE_SIGNALS readers below - a single
    diagnostics fetch, not two."""
    diag = get_diagnostics()
    if not diag["connected"] or diag["stale"]:
        return None
    ds18b20 = diag["sensors"].get("ds18b20")
    return ds18b20 if isinstance(ds18b20, dict) else None


def read_ds18b20_probes_ok():
    """HARDWARE_SIGNALS reader - zero-argument, returns an int (count of
    CURRENTLY-OK, COMMISSIONED probes this cycle) or None if the
    supervisor link itself isn't available. Register with:
    register_hardware_signal("ds18b20_probes_ok", read_ds18b20_probes_ok).
    Paired with read_ds18b20_probes_commissioned() below - together they
    let a consumer (e.g. piratebox_progression.py) ask "are all of them
    healthy right now" without ever hardcoding how many probes this
    device happens to own."""
    ds18b20 = _ds18b20_block()
    if ds18b20 is None:
        return None
    probes = ds18b20.get("probes")
    commissioned = ds18b20.get("commissioned")
    if not isinstance(probes, dict) or not isinstance(commissioned, dict):
        return 0
    return sum(
        1 for rom in commissioned
        if isinstance(probes.get(rom), dict) and probes[rom].get("ok")
    )


def read_ds18b20_probes_commissioned():
    """HARDWARE_SIGNALS reader - zero-argument, returns an int (count of
    ROMs this device has ever physically commissioned - see
    piratebox_ds18b20_roles.py) or None if the supervisor link itself
    isn't available. Register with: register_hardware_signal(
    "ds18b20_probes_commissioned", read_ds18b20_probes_commissioned)."""
    ds18b20 = _ds18b20_block()
    if ds18b20 is None:
        return None
    commissioned = ds18b20.get("commissioned")
    return len(commissioned) if isinstance(commissioned, dict) else 0


if __name__ == "__main__":
    import pprint
    pprint.pprint(get_diagnostics())
