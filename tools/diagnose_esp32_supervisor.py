#!/usr/bin/env python3
"""
Standalone ESP32-S3 hardware/sensor supervisor diagnostic (2026-09-07,
docs/ESP32-SUPERVISOR-DESIGN.md; extended 2026-09-08 for the
PirateBox-wide hardware-awareness phase). Answers exactly the operator
questions that matter without reverse-engineering journalctl:

  - Is the supervisor connected right now?
  - What firmware/protocol version is it running?
  - What's its uptime and last reset reason?
  - What capabilities/sensors does it report, and are they fresh?
  - Is the DS18B20 bus healthy, and is every COMMISSIONED probe (a
    known, permanent physical identity - see piratebox_ds18b20_roles.py)
    currently accounted for, or is one missing/failing?
  - Has the daemon seen any malformed lines or unexpected reboots?
  - Is the piratebox-esp32-supervisor.service itself running?

Uses piratebox_hardware_health.py's shared classification (the same
vocabulary the admin capability table and OLED daemon use) rather than
re-deriving its own ad hoc connected/stale logic - this file used to be
a fourth independent copy of that reduction (found during the
2026-09-08 hardware-awareness audit); it no longer is.

Reads ONLY the daemon's cached export
(/run/piratebox-esp32/esp32-public.json) via piratebox_esp32_client.py -
never opens the serial port itself (only the daemon may do that; see
its own header). Needs no sudo - the export is world-readable.

Run directly:

    python3 tools/diagnose_esp32_supervisor.py
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_esp32_client as client  # noqa: E402 - path insert must happen first
import piratebox_hardware_health as health  # noqa: E402


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except Exception as exc:  # noqa: BLE001
        return f"(failed to run {cmd!r}: {exc})"


def main():
    diag = client.get_diagnostics()

    print("=== ESP32 supervisor status (from cached export) ===")
    for key in ("connected", "stale", "fw_version", "protocol_version", "board",
                "mac", "reset_reason", "uptime_ms", "reboot_count",
                "capabilities", "malformed_lines", "export_age_seconds"):
        print(f"  {key}: {diag.get(key)}")
    link_state = health.classify_esp32_supervisor(diag)
    print(f"  link health: {link_state}")

    print()
    print("=== Sensor readings ===")
    sensors = diag.get("sensors") or {}
    if not sensors:
        print("  (none reported)")
    for name, reading in sensors.items():
        if name == "ds18b20":
            continue  # detailed breakdown below, not the raw dump
        state = health.classify_simple_sensor(diag, name)
        print(f"  {name}: {reading}  [{state}]")

    ds18b20 = sensors.get("ds18b20")
    if isinstance(ds18b20, dict):
        commissioned = ds18b20.get("commissioned")
        commissioned_roms = set(commissioned.keys()) if isinstance(commissioned, dict) else set()
        bus = health.classify_ds18b20_bus(diag, commissioned_roms)
        print()
        print("=== DS18B20 1-Wire bus ===")
        print(f"  bus health: {bus['state']}  (bus_ok={bus['bus_ok']})")
        print(f"  probes: {bus['probes_ok']} ok / {bus['probes_expected']} commissioned")
        if bus["missing_commissioned"]:
            print(f"  MISSING (commissioned but not reporting this cycle): {bus['missing_commissioned']}")
        if bus["failing_commissioned"]:
            print(f"  FAILING (commissioned, reporting, but ok=false): {bus['failing_commissioned']}")
        probes = ds18b20.get("probes") or {}
        for rom, reading in probes.items():
            label = "commissioned" if rom in commissioned_roms else "uncommissioned"
            print(f"  {rom}: {reading}  ({label})")
        uncommissioned_roms = set(probes.keys()) - commissioned_roms
        if uncommissioned_roms:
            print(f"  Note: {len(uncommissioned_roms)} probe(s) on the bus have never been "
                  f"commissioned - see tools/ds18b20_commission.py.")

    print()
    print("=== systemd service ===")
    print("  piratebox-esp32-supervisor.service:",
          run(["systemctl", "is-active", "piratebox-esp32-supervisor.service"]).strip())

    print()
    print("=== USB/serial (informational only - the daemon owns the actual link) ===")
    print(run(["sh", "-c", "ls -la /dev/serial/by-id/ 2>&1"]))

    print()
    if link_state == "AVAILABLE":
        print("ESP32 supervisor: CONNECTED and reporting fresh data.")
    elif diag.get("reason") == "no_export":
        print("ESP32 supervisor: NO EXPORT FOUND - is piratebox-esp32-supervisor.service "
              "installed and running? (see setup_piratebox_esp32_supervisor.sh)")
    else:
        print(f"ESP32 supervisor: {link_state} - "
              "check the physical USB connection (COM port, externally powered "
              "hub - see docs/OPERATIONAL-DECISIONS.md) before assuming a "
              "software issue.")


if __name__ == "__main__":
    main()
