#!/usr/bin/env python3
#
# PirateBox-wide temperature display-unit preference - Python side
# (2026-09-08). Mirrors var/www/html/includes/temp_unit.php exactly -
# see that file's own header for the full architectural rationale
# (canonical data stays Celsius everywhere; this is presentation-only;
# a global, operator-set device preference, not per-visitor).
#
# READS THE SAME FILE THE PHP LAYER WRITES
# (var/www/html/data/temp-unit.json) - this is the one shared,
# cross-process, cross-language preference store. The OLED daemon
# (running as piratebox-gpio, under ProtectSystem=strict) only ever
# READS this file; ProtectSystem=strict blocks writes outside its own
# allowlisted paths, not reads elsewhere, so no systemd unit change was
# needed for this. Written by PHP as plain file_put_contents() output
# (0644, world-readable, same as every other file this project writes
# this way) - readable by any account, no group membership needed.
#
# This module never touches I2C/1-Wire/serial and never writes this
# file itself - only var/www/html/includes/temp_unit.php's admin-page
# form does that.

import json

TEMP_UNIT_FILE = "/var/www/html/data/temp-unit.json"

TEMP_UNITS = ("C", "F")


def read_temp_unit(path: str = None) -> str:
    """Returns 'C' or 'F'. Missing file, unreadable, malformed JSON, or
    an unrecognized value all resolve to 'C' - the canonical storage
    unit itself, so "preference not set yet" never fabricates a
    Fahrenheit default. `path` is injectable for tests."""
    try:
        with open(path or TEMP_UNIT_FILE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return "C"
    unit = data.get("unit") if isinstance(data, dict) else None
    return unit if unit in TEMP_UNITS else "C"


def convert_c(celsius, unit: str):
    """Pure conversion, the ONE place C->F arithmetic happens on the
    Python side. `celsius` is always assumed to be genuine Celsius -
    every caller in this codebase converts an already-read Celsius
    value exactly once, right before formatting for display, and never
    stores or re-passes the converted result anywhere else. None
    passes through as None so callers keep their existing "no reading"
    handling unchanged."""
    if celsius is None or unit != "F":
        return celsius
    return (celsius * 9.0 / 5.0) + 32.0
