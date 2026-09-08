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

TYPICAL WORKFLOW (single probe, or you're comfortable eyeballing a
short list):
    python3 tools/ds18b20_commission.py watch
        # warm one probe with your fingers, watch which ROM's
        # temperature rises - Ctrl+C once you've identified it
    python3 tools/ds18b20_commission.py name 28ff641e04170378 Enclosure
    python3 tools/ds18b20_commission.py list
        # confirm the name is now attached

MULTI-PROBE WORKFLOW (recommended with several probes at once -
the tool does the comparison instead of you eyeballing N similar
numbers): `identify` captures a baseline the moment it starts, then
shows each probe's LIVE DELTA from that baseline, sorted with the
biggest mover first and flagged once it's unambiguous:
    python3 tools/ds18b20_commission.py identify
        # (tool captures baseline here - don't warm anything yet)
        # now warm ONE probe; within a couple of read cycles its row
        # rises to the top with ">>> LIKELY THIS ONE <<<"
    python3 tools/ds18b20_commission.py name <rom> "..."
        # repeat identify for the next probe

Once every physical probe's ROM is known (from one or more 'identify'
sessions), record the whole set as a permanent hardware-identity fact
in one shot with 'commission' - ROMs in the order you physically
identified them, NOT bus discovery order:
    python3 tools/ds18b20_commission.py commission <rom1> <rom2> ... <romN>
        # assigns physical_index 1..N in the order given - no name or
        # role is assigned by this step
    python3 tools/ds18b20_commission.py list
        # confirm all N show as commissioned (Probe 1..Probe N)
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

    print(f"{'ROM address':<18} {'Temp':>8}  {'Status':<12} {'Physical':<10} Name")
    print("-" * 75)
    for rom in sorted(probes):
        reading = probes[rom]
        role = roles.get(rom)
        commissioned = isinstance(role, dict) and role.get("commissioned")
        physical = f"#{role['physical_index']}" if commissioned and role.get("physical_index") else "-"
        name = role["name"] if isinstance(role, dict) and role.get("name") else "(unnamed)"
        if reading.get("ok"):
            temp_str = f"{reading['value']:.1f}C"
            status = "ok"
        else:
            temp_str = "--"
            status = reading.get("err", "error")
        print(f"{rom:<18} {temp_str:>8}  {status:<12} {physical:<10} {name}")
    uncommissioned = [rom for rom in probes if not (isinstance(roles.get(rom), dict) and roles[rom].get("commissioned"))]
    if uncommissioned:
        print(f"\n{len(uncommissioned)} probe(s) above have never been commissioned - see 'commission'.")


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


# A DS18B20's successive-read jitter (12-bit resolution, 0.0625C
# steps) never approaches this - a delta this large is unambiguously a
# hand warming the probe, not sensor noise. Chosen well above the
# largest natural drift observed during this project's own commissioning
# (< 0.5C over minutes at rest).
IDENTIFY_THRESHOLD_C = 1.5


def capture_baseline():
    """Returns {rom: value} for every currently-ok probe - the
    reference point identify() measures live deltas against. Probes
    that are currently NOT ok (disconnected/uninit_85c/etc.) are
    simply excluded from the baseline - they'll appear once they start
    reporting real values, with no baseline to compare against yet
    (shown as delta unknown, never a fabricated zero)."""
    export = read_export()
    baseline = {}
    for rom, reading in get_ds18b20_probes(export).items():
        if reading.get("ok") and isinstance(reading.get("value"), (int, float)):
            baseline[rom] = float(reading["value"])
    return baseline


def compute_deltas(baseline: dict, current_probes: dict) -> list:
    """Pure function: given a baseline {rom: value} and the current
    probes dict (the live 'probes' shape from the export), returns a
    list of (rom, current_value_or_None, delta_or_None) tuples sorted
    by delta descending (unknown deltas - a probe missing from the
    baseline, or currently not-ok - sort last, not first, so a
    disconnected probe never looks like "the biggest mover"). Directly
    testable without any file I/O."""
    rows = []
    for rom, reading in current_probes.items():
        if reading.get("ok") and isinstance(reading.get("value"), (int, float)):
            value = float(reading["value"])
            delta = (value - baseline[rom]) if rom in baseline else None
        else:
            value = None
            delta = None
        rows.append((rom, value, delta))
    rows.sort(key=lambda r: (r[2] is None, -(r[2] or 0)))
    return rows


def cmd_identify(args):
    interval = float(args[0]) if args else 5.0
    print("Capturing baseline - do not warm any probe yet...")
    baseline = capture_baseline()
    if not baseline:
        print("No currently-ok probes found to baseline against. Check 'list' first.")
        return
    print(f"Baseline captured for {len(baseline)} probe(s). Now warm ONE probe with your")
    print(f"fingers - refreshing every {interval:.0f}s (the sensor itself only updates every")
    print("~30s internally, so allow at least one full cycle to see a change). Ctrl+C to stop.\n")
    try:
        while True:
            export = read_export()
            probes = get_ds18b20_probes(export)
            rows = compute_deltas(baseline, probes)
            print(f"--- {time.strftime('%H:%M:%S')} ---")
            print(f"{'ROM address':<18} {'Now':>8} {'Delta':>8}")
            print("-" * 40)
            for rom, value, delta in rows:
                now_str = "--" if value is None else f"{value:.2f}C"
                if delta is None:
                    delta_str = "n/a"
                    flag = ""
                else:
                    delta_str = f"{delta:+.2f}C"
                    flag = "   >>> LIKELY THIS ONE <<<" if delta >= IDENTIFY_THRESHOLD_C else ""
                print(f"{rom:<18} {now_str:>8} {delta_str:>8}{flag}")
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


def cmd_commission(args):
    """Records a whole set of ROM<->physical_index identities at once -
    the durable result of a physical warming-test commissioning session
    (see 'identify' above). Takes ROMs in PHYSICAL IDENTIFICATION ORDER
    as positional arguments (the order you warmed them in, NOT bus
    discovery order) - physical_index 1 is assigned to the first ROM
    given, 2 to the second, and so on. This does NOT assign any name or
    functional role - purely a permanent hardware-identity record, safe
    to run before any naming/role decision has been made.

    Usage: ds18b20_commission.py commission <rom1> <rom2> ... <romN>
        (one ROM per physical probe, in the order you identified them)
    """
    if len(args) < 1:
        print("Usage: ds18b20_commission.py commission <rom1> <rom2> ... <romN>", file=sys.stderr)
        print("  ROMs in PHYSICAL IDENTIFICATION order (the order you warmed them), not bus order.", file=sys.stderr)
        sys.exit(1)
    roms = [a.lower() for a in args]
    for rom in roms:
        if not roles_module.is_valid_rom(rom):
            print(f"'{rom}' doesn't look like a 16-hex-character ROM address.", file=sys.stderr)
            sys.exit(1)
    if len(set(roms)) != len(roms):
        print("Duplicate ROM address given - each probe must be listed exactly once.", file=sys.stderr)
        sys.exit(1)
    request = {
        "action": "commission_batch",
        "probes": [{"rom": rom, "physical_index": i + 1} for i, rom in enumerate(roms)],
    }
    with open(roles_module.NAME_REQUEST_FILE, "w") as f:
        json.dump(request, f)
    print(f"Requested: commission {len(roms)} probe(s) as Probe 1..{len(roms)}, in the order given:")
    for i, rom in enumerate(roms):
        print(f"  Probe {i + 1}: {rom}")
    print("No names or roles assigned - run 'list' shortly to confirm, then 'name <rom> \"...\"' when ready.")


COMMANDS = {
    "list": cmd_list,
    "watch": cmd_watch,
    "identify": cmd_identify,
    "commission": cmd_commission,
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
