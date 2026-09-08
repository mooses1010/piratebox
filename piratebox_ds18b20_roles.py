#!/usr/bin/env python3
#
# DS18B20 probe naming/role storage (2026-09-07). Sensor names are
# COSMETIC CONFIGURATION METADATA, never the hardware identity itself -
# the underlying identity is always the 1-Wire ROM address, reported by
# the ESP32 firmware (ds18b20.cpp) and never invented here. This module
# owns exactly one small durable file mapping ROM address -> a
# human-assigned name, plus the narrow request-file protocol that lets
# an unprivileged operator CLI (tools/ds18b20_commission.py) propose a
# naming change without racing the daemon's own writes to that file.
#
# WHY A DURABLE FILE, NOT A DATABASE: this project has no database by
# design (README/ARCHITECTURE.md) and a probe naming table is exactly
# the kind of small, rarely-changing, single-device configuration a
# flat JSON file already handles well elsewhere in this project
# (piratebox_progression.py's own state file, sensors-public.json,
# etc.) - a real database would be pure overhead for a handful of
# entries that change on the order of "once, when a probe is
# commissioned."
#
# WHY A REQUEST FILE, NOT DIRECT WRITES FROM THE CLI: mirrors
# piratebox_progression.py's own reset/import-request pattern exactly
# (see that file's "Reset / import, single-writer design" section) -
# only ONE process (piratebox_esp32_supervisor.py, via this module)
# ever writes the durable roles file, avoiding any concurrent-writer
# hazard between an interactively-run CLI and the always-running
# daemon. The CLI (running as the interactive operator, `moose`) can
# still write the SMALL REQUEST file directly, because both the
# request file and the durable roles file live under
# /var/lib/piratebox-esp32/ (systemd StateDirectory=, owned
# piratebox-gpio:gpio, mode 0770) and `moose` is already a member of
# the `gpio` group (confirmed 2026-09-07) - no bind-mount indirection
# needed, unlike the OLED daemon's own /tmp/piratebox arrangement,
# which exists to work around ITS OWN PrivateTmp=yes (this supervisor
# daemon also has PrivateTmp=yes, but that only isolates /tmp - it has
# no bearing on /var/lib/piratebox-esp32 at all).
#
# PRIVACY: this file contains only operator-chosen probe labels (e.g.
# "Enclosure", "Battery") and ROM addresses (a property of the sensor
# hardware itself, not of any visitor/person) - nothing here is
# visitor-identifying or privacy-sensitive by the standards this
# project already applies elsewhere (docs/TRAVEL-MODE-DESIGN.md,
# docs/ARCHITECTURE.md §6).

import json
import os
import time

ROLES_FILE = "/var/lib/piratebox-esp32/ds18b20-roles.json"
NAME_REQUEST_FILE = "/var/lib/piratebox-esp32/ds18b20-name-request.json"

# A friendly name is display metadata only - kept short and plain so it
# renders cleanly everywhere it's shown (Environment page, OLED, CLI).
MAX_NAME_LENGTH = 40


def load_roles() -> dict:
    """Returns {rom_hex: {"name": str, "assigned_at": float}, ...}.
    Missing/corrupt file degrades to an empty mapping - never raises,
    matching this project's "honest missing value" discipline; an
    unnamed probe is simply unnamed, not a fatal condition anywhere."""
    try:
        with open(ROLES_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    cleaned = {}
    for rom, entry in data.items():
        if isinstance(rom, str) and isinstance(entry, dict) and isinstance(entry.get("name"), str):
            cleaned[rom] = {"name": entry["name"], "assigned_at": entry.get("assigned_at")}
    return cleaned


def save_roles(roles: dict) -> None:
    """Atomic write (temp file + rename), same pattern used throughout
    this project's other durable/exported JSON files."""
    os.makedirs(os.path.dirname(ROLES_FILE), exist_ok=True)
    tmp_path = f"{ROLES_FILE}.tmp.{os.getpid()}"
    with open(tmp_path, "w") as f:
        json.dump(roles, f, indent=2, sort_keys=True)
    os.replace(tmp_path, ROLES_FILE)


def is_valid_rom(rom) -> bool:
    """A DS18B20 1-Wire ROM address is exactly 8 bytes -> 16 lowercase
    hex characters, no separators (matches ds18b20.cpp's romToHex())."""
    return isinstance(rom, str) and len(rom) == 16 and all(c in "0123456789abcdef" for c in rom)


def apply_name_request(roles: dict, request: dict) -> dict:
    """Pure function: given the current roles dict and one parsed
    request object, returns the NEW roles dict (does not mutate the
    input) - or the same dict, unchanged, if the request is malformed
    in any way (never raises, never partially applies a bad request).
    Testable without touching any file."""
    if not isinstance(request, dict):
        return roles
    action = request.get("action")
    rom = request.get("rom")
    if not is_valid_rom(rom):
        return roles

    new_roles = dict(roles)
    if action == "set":
        name = request.get("name")
        if not isinstance(name, str) or not name.strip():
            return roles
        name = name.strip()[:MAX_NAME_LENGTH]
        new_roles[rom] = {"name": name, "assigned_at": time.time()}
        return new_roles
    if action == "remove":
        new_roles.pop(rom, None)
        return new_roles
    return roles


def check_name_request(roles: dict, markers: dict, log=None) -> dict:
    """Call every daemon cycle. `markers` is a small dict the caller
    keeps in memory across cycles (never persisted, same as
    piratebox_progression.py's own check_reset_request marker
    pattern). Returns the (possibly updated) roles dict - saves to disk
    and clears the request file only if a genuinely new, valid request
    was found. A present-but-already-seen or malformed request is
    silently ignored, exactly like the progression reset/import
    pattern this mirrors."""
    try:
        mtime = os.path.getmtime(NAME_REQUEST_FILE)
    except OSError:
        return roles
    if mtime <= markers.get("name_request_mtime", 0.0):
        return roles
    markers["name_request_mtime"] = mtime

    try:
        with open(NAME_REQUEST_FILE) as f:
            request = json.load(f)
    except (OSError, ValueError) as exc:
        if log is not None:
            log.warning("DS18B20 name request unreadable/invalid JSON (%s) - ignored.", exc)
        return roles

    new_roles = apply_name_request(roles, request)
    if new_roles is not roles and new_roles != roles:
        save_roles(new_roles)
        if log is not None:
            log.info("DS18B20 role updated: %s", request)
        try:
            os.remove(NAME_REQUEST_FILE)
        except OSError:
            pass  # not fatal - the mtime marker above already prevents reapplying it
        return new_roles

    if log is not None:
        log.warning("DS18B20 name request present but invalid/no-op - ignored: %s", request)
    try:
        os.remove(NAME_REQUEST_FILE)
    except OSError:
        pass
    return roles
