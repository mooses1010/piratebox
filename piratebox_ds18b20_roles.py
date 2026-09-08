#!/usr/bin/env python3
#
# DS18B20 probe naming/role storage (2026-09-07, extended 2026-09-08 for
# the PirateBox-wide hardware-awareness phase). Sensor names are
# COSMETIC CONFIGURATION METADATA, never the hardware identity itself -
# the underlying identity is always the 1-Wire ROM address, reported by
# the ESP32 firmware (ds18b20.cpp) and never invented here. This module
# owns exactly one small durable file mapping ROM address -> a
# human-assigned name (plus, as of this extension, a "commissioned"
# identity-tracking flag and reserved role slot - see below), plus the
# narrow request-file protocol that lets an unprivileged operator CLI
# (tools/ds18b20_commission.py) propose a change without racing the
# daemon's own writes to that file.
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
# THE IDENTITY -> NAME -> ROLE -> POLICY PIPELINE (2026-09-08 extension,
# see docs/ESP32-SUPERVISOR-DESIGN.md's hardware-awareness section for
# the full rationale): a probe's ROM address is permanent hardware
# identity, established once by physically warming it and watching
# which address responds (docs/OPERATIONAL-DECISIONS.md's commissioning
# record) - never by discovery order, never re-derived. That act of
# physical identification is recorded here as `commissioned` (bool) +
# `commissioned_at` (when) + `physical_index` (the operator's own 1..N
# physical identification order, e.g. "the probe warmed first") -
# **a stable label for referring to a specific physical probe before it
# has a name, NOT a functional role and NOT the same thing as whatever
# order the 1-Wire bus happens to enumerate ROMs in on any given boot.**
# `name` (optional, cosmetic) may be layered on top once the operator
# chooses one - independent of commissioning. `role` is a reserved,
# always-`None`-today field for a FUTURE functional classification
# (e.g. "this probe monitors the battery") that role-specific safety
# policy could eventually key off of - deliberately not populated by
# anything in this codebase yet, so that adding real roles later never
# requires another schema migration. See CAUTION below.
#
# CAUTION - DO NOT populate `role` from this codebase until the
# operator has made a real, physical, consequential decision about
# where each probe actually lives. A probe being "commissioned" only
# means its ROM identity is known and tracked; it says nothing about
# what the probe is attached to or whether any reading from it is
# safety-relevant.
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

# Sanity bound on physical_index - this project owns a handful of
# probes, not hundreds; a large/negative value in a request is treated
# as malformed rather than accepted verbatim.
MAX_PHYSICAL_INDEX = 64

_ENTRY_DEFAULTS = {
    "name": None,
    "assigned_at": None,
    "commissioned": False,
    "commissioned_at": None,
    "physical_index": None,
    "role": None,
}


def load_roles() -> dict:
    """Returns {rom_hex: {"name", "assigned_at", "commissioned",
    "commissioned_at", "physical_index", "role"}, ...}. Missing/corrupt
    file, or an entry missing newer fields (written by an older version
    of this module), degrades to the documented defaults - never
    raises, matching this project's "honest missing value" discipline.
    A ROM with no entry at all is simply unknown here - callers should
    treat that as "not yet commissioned," not as an error."""
    try:
        with open(ROLES_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    cleaned = {}
    for rom, entry in data.items():
        if not (isinstance(rom, str) and isinstance(entry, dict)):
            continue
        # A pre-extension entry only ever had a valid "name" - still a
        # legitimate (if not-yet-commissioned) entry today.
        has_name = isinstance(entry.get("name"), str)
        has_commission = entry.get("commissioned") is True
        if not (has_name or has_commission):
            continue
        merged = dict(_ENTRY_DEFAULTS)
        merged["name"] = entry["name"] if has_name else None
        merged["assigned_at"] = entry.get("assigned_at")
        merged["commissioned"] = bool(entry.get("commissioned", False))
        merged["commissioned_at"] = entry.get("commissioned_at")
        idx = entry.get("physical_index")
        merged["physical_index"] = idx if isinstance(idx, int) and idx > 0 else None
        # role is reserved/unused - passed through as-is (always None
        # today) rather than silently dropped, so a future version that
        # DOES populate it doesn't need another migration to be readable.
        merged["role"] = entry.get("role")
        cleaned[rom] = merged
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


def commissioned_roms(roles: dict) -> set:
    """The set of ROM addresses this device has ever physically
    identified and recorded as a known fixture - the basis for a
    generic "expected commissioned probe missing" health check.
    Deliberately says nothing about names or roles."""
    return {rom for rom, entry in roles.items() if entry.get("commissioned")}


def physical_label(roles: dict, rom: str) -> str:
    """A display label safe to show before (or instead of) a name:
    the operator's own name if one is set, else "Probe N" using the
    durable physical_index (never raw discovery order, never the ROM
    itself), else a generic fallback for a ROM this device has never
    commissioned at all (should be rare - typically means a brand-new
    probe just appeared on the bus)."""
    entry = roles.get(rom)
    if not entry:
        return "Unidentified probe"
    if entry.get("name"):
        return entry["name"]
    if entry.get("physical_index"):
        return f"Probe {entry['physical_index']}"
    return "Unnamed probe"


def _is_valid_commission_batch(probes) -> bool:
    if not isinstance(probes, list) or not probes:
        return False
    seen_roms = set()
    seen_indices = set()
    for item in probes:
        if not isinstance(item, dict):
            return False
        rom = item.get("rom")
        idx = item.get("physical_index")
        if not is_valid_rom(rom) or rom in seen_roms:
            return False
        if not isinstance(idx, int) or not (0 < idx <= MAX_PHYSICAL_INDEX) or idx in seen_indices:
            return False
        seen_roms.add(rom)
        seen_indices.add(idx)
    return True


def apply_name_request(roles: dict, request: dict) -> dict:
    """Pure function: given the current roles dict and one parsed
    request object, returns the NEW roles dict (does not mutate the
    input) - or the same dict, unchanged, if the request is malformed
    in any way (never raises, never partially applies a bad request).
    Testable without touching any file.

    Actions:
      "set"             - assign/replace a cosmetic name for one ROM.
      "remove"          - clear a ROM's name (does NOT un-commission it
                           - commissioning is a hardware-identity fact,
                           independent of whether a name is currently set).
      "commission_batch" - record a whole set of ROM<->physical_index
                           identities at once (the durable result of a
                           physical warming-test commissioning session).
                           Applied atomically: either every entry in the
                           batch is valid (distinct ROMs, distinct
                           positive indices) and all are applied, or
                           none are - a partially-invalid batch must
                           never corrupt already-commissioned probes.
                           Re-running with the same data is idempotent;
                           a ROM already commissioned keeps its existing
                           name/role untouched, only commissioned/
                           commissioned_at/physical_index are set.
    """
    if not isinstance(request, dict):
        return roles
    action = request.get("action")

    if action == "commission_batch":
        probes = request.get("probes")
        if not _is_valid_commission_batch(probes):
            return roles
        new_roles = dict(roles)
        now = time.time()
        for item in probes:
            rom = item["rom"]
            existing = dict(_ENTRY_DEFAULTS)
            existing.update(new_roles.get(rom, {}))
            existing["commissioned"] = True
            existing["commissioned_at"] = existing.get("commissioned_at") or now
            existing["physical_index"] = item["physical_index"]
            new_roles[rom] = existing
        return new_roles

    rom = request.get("rom")
    if not is_valid_rom(rom):
        return roles

    new_roles = dict(roles)
    if action == "set":
        name = request.get("name")
        if not isinstance(name, str) or not name.strip():
            return roles
        name = name.strip()[:MAX_NAME_LENGTH]
        entry = dict(_ENTRY_DEFAULTS)
        entry.update(new_roles.get(rom, {}))
        entry["name"] = name
        entry["assigned_at"] = time.time()
        new_roles[rom] = entry
        return new_roles
    if action == "remove":
        if rom not in new_roles:
            return roles
        entry = dict(new_roles[rom])
        # Clearing a name never un-commissions a probe or forgets its
        # physical_index - those are hardware-identity facts, not
        # cosmetic display state. Drop the entry entirely only if it
        # was never commissioned in the first place (a pure legacy
        # name-only record with nothing else worth keeping).
        if entry.get("commissioned"):
            entry["name"] = None
            entry["assigned_at"] = None
            new_roles[rom] = entry
        else:
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
