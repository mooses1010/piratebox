#!/usr/bin/env python3
"""
DS18B20 probe commissioning CLI (2026-09-07). Answers the one question
the operator actually needs answered when wiring multiple probes:
"which physical probe is which ROM address?" - and lets them assign a
permanent, human-readable name once they know.

Reads ONLY the ESP32 supervisor's already-published cached export
(/run/piratebox-esp32/esp32-public.json) - never touches the serial
port or hardware directly, same discipline as every other consumer of
this daemon's data (tools/diagnose_esp32_supervisor.py,
includes/esp32_supervisor.php).

Naming a probe writes a small REQUEST file that the supervisor daemon
itself picks up and applies - this tool never writes the durable roles
file directly. See piratebox_ds18b20_roles.py's own header for the
full single-writer rationale. No sudo needed: both files live under
/var/lib/piratebox-esp32/, group-writable by `gpio` (the interactive
operator account is already a member of that group).

TYPICAL WORKFLOW:
    python3 tools/ds18b20_commission.py watch
        # warm one probe with your fingers, watch which ROM's
        # temperature rises - Ctrl+C once you've identified it
    python3 tools/ds18b20_commission.py name 28ff641e04170378 Enclosure
    python3 tools/ds18b20_commission.py list
        # confirm the name is now attached
"""
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_ds18b20_roles as roles_module  # noqa: E402 - path insert must happen first

EXPORT_FILE = "/run/piratebox-esp32/esp32-public.json"


def read_export():
    try:
        with open(EXPORT_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def get_ds18b20_probes(export):
    if not export:
        return {}
    sensors = export.get("sensors")
    if not isinstance(sensors, dict):
        return {}
    ds18b20 = sensors.get("ds18b20")
    if not isinstance(ds18b20, dict):
        return {}
    probes = ds18b20.get("probes")
    return probes if isinstance(probes, dict) else {}


def print_probe_table(export, roles):
    if export is None:
        print("No supervisor export found - is piratebox-esp32-supervisor.service running")
        print("and the ESP32 connected? (see tools/diagnose_esp32_supervisor.py)")
        return
    if not export.get("connected") or export.get("stale"):
        print("Supervisor is not currently connected / data is stale.")
        return

    probes = get_ds18b20_probes(export)
    ds18b20 = export.get("sensors", {}).get("ds18b20", {})
    if not probes:
        if "ds18b20" not in export.get("capabilities", []):
            print("This firmware build has never found a DS18B20 probe yet.")
            print("Nothing is wired, or the bus hasn't been scanned since booting with probes attached.")
        else:
            print("DS18B20 bus present, 0 probes currently found "
                  f"(bus_ok={ds18b20.get('bus_ok')}).")
        return

    print(f"{'ROM address':<18} {'Temp':>8}  {'Status':<12} Name")
    print("-" * 60)
    for rom in sorted(probes):
        reading = probes[rom]
        role = roles.get(rom)
        name = role["name"] if isinstance(role, dict) else "(unnamed)"
        if reading.get("ok"):
            temp_str = f"{reading['value']:.1f}C"
            status = "ok"
        else:
            temp_str = "--"
            status = reading.get("err", "error")
        print(f"{rom:<18} {temp_str:>8}  {status:<12} {name}")


def cmd_list(_args):
    print_probe_table(read_export(), roles_module.load_roles())


def cmd_watch(args):
    interval = float(args[0]) if args else 3.0
    print(f"Watching every {interval:.0f}s - Ctrl+C to stop.")
    print("Warm one probe with your fingers and watch which ROM's reading rises.\n")
    try:
        while True:
            print(f"--- {time.strftime('%H:%M:%S')} ---")
            print_probe_table(read_export(), roles_module.load_roles())
            print()
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")


def cmd_name(args):
    if len(args) < 2:
        print("Usage: ds18b20_commission.py name <rom_hex> <friendly name>", file=sys.stderr)
        sys.exit(1)
    rom, name = args[0].lower(), " ".join(args[1:])
    if not roles_module.is_valid_rom(rom):
        print(f"'{rom}' doesn't look like a 16-hex-character ROM address.", file=sys.stderr)
        sys.exit(1)
    request = {"action": "set", "rom": rom, "name": name}
    with open(roles_module.NAME_REQUEST_FILE, "w") as f:
        json.dump(request, f)
    print(f"Requested: {rom} -> \"{name}\". The supervisor daemon will apply this within a few seconds.")
    print("Run 'list' again shortly to confirm.")


def cmd_unname(args):
    if len(args) < 1:
        print("Usage: ds18b20_commission.py unname <rom_hex>", file=sys.stderr)
        sys.exit(1)
    rom = args[0].lower()
    if not roles_module.is_valid_rom(rom):
        print(f"'{rom}' doesn't look like a 16-hex-character ROM address.", file=sys.stderr)
        sys.exit(1)
    request = {"action": "remove", "rom": rom}
    with open(roles_module.NAME_REQUEST_FILE, "w") as f:
        json.dump(request, f)
    print(f"Requested: remove name for {rom}.")


COMMANDS = {
    "list": cmd_list,
    "watch": cmd_watch,
    "name": cmd_name,
    "unname": cmd_unname,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print(f"Commands: {', '.join(COMMANDS)}")
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
