#!/usr/bin/env python3
"""
Standalone ESP32-S3 hardware/sensor supervisor diagnostic (2026-09-07,
docs/ESP32-SUPERVISOR-DESIGN.md). Answers exactly the operator
questions that matter without reverse-engineering journalctl:

  - Is the supervisor connected right now?
  - What firmware/protocol version is it running?
  - What's its uptime and last reset reason?
  - What capabilities/sensors does it report, and are they fresh?
  - Has the daemon seen any malformed lines or unexpected reboots?
  - Is the piratebox-esp32-supervisor.service itself running?

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

    print()
    print("=== Sensor readings ===")
    sensors = diag.get("sensors") or {}
    if not sensors:
        print("  (none reported)")
    for name, reading in sensors.items():
        print(f"  {name}: {reading}")

    print()
    print("=== systemd service ===")
    print("  piratebox-esp32-supervisor.service:",
          run(["systemctl", "is-active", "piratebox-esp32-supervisor.service"]).strip())

    print()
    print("=== USB/serial (informational only - the daemon owns the actual link) ===")
    print(run(["sh", "-c", "ls -la /dev/serial/by-id/ 2>&1"]))

    print()
    if diag.get("connected") and not diag.get("stale"):
        print("ESP32 supervisor: CONNECTED and reporting fresh data.")
    elif diag.get("reason") == "no_export":
        print("ESP32 supervisor: NO EXPORT FOUND - is piratebox-esp32-supervisor.service "
              "installed and running? (see setup_piratebox_esp32_supervisor.sh)")
    else:
        print("ESP32 supervisor: NOT currently connected / data is stale - "
              "check the physical USB connection (COM port, externally powered "
              "hub - see docs/OPERATIONAL-DECISIONS.md) before assuming a "
              "software issue.")


if __name__ == "__main__":
    main()
