#!/bin/bash
#
# Manually set the PirateBox presentation mode (Normal / Emergency).
#
# THIS IS A STAND-IN FOR THE PHYSICAL MTS-101 TOGGLE SWITCH, which has not
# arrived yet (see docs/OPERATIONAL-DECISIONS.md, "Emergency Mode software
# foundation"). It writes the exact same state file
# (/tmp/piratebox/mode) that a future GPIO daemon will write once the
# switch is wired up - so everything this script proves out today (PHP
# reading the file, the site's presentation switching correctly, safe
# fallback behavior) carries over unchanged when the real daemon replaces
# manual use of this script. This script does NOT talk to any GPIO pin -
# there is none connected yet.
#
# Deliberately root-only, and deliberately NOT web-reachable from anywhere
# in the PHP app: mode changes must come from a trusted, privileged actor
# (an operator with sudo today; a root-owned daemon later), never from an
# unauthenticated site visitor. Run with sudo, e.g.:
#
#   sudo ./set_piratebox_mode.sh emergency
#   sudo ./set_piratebox_mode.sh normal
#   sudo ./set_piratebox_mode.sh status
#
# The state file lives on tmpfs (/tmp), not the SD card, so it does NOT
# persist across a reboot - a fresh boot always starts with no file
# present, which PirateBox's PHP side treats as the safe Normal fallback
# until this script (or, later, the GPIO daemon) writes a value again.

set -euo pipefail

STATE_DIR="/tmp/piratebox"
STATE_FILE="$STATE_DIR/mode"

usage() {
    echo "Usage: sudo $0 {normal|emergency|status}" >&2
    exit 1
}

if [ "$#" -ne 1 ]; then
    usage
fi

ACTION="$1"

case "$ACTION" in
    normal|emergency)
        if [ "$(id -u)" -ne 0 ]; then
            echo "This changes trusted PirateBox state and must be run as root - re-run with sudo." >&2
            exit 1
        fi

        mkdir -p "$STATE_DIR"
        chmod 0755 "$STATE_DIR"

        # Atomic write: temp file in the same directory (same filesystem,
        # so the rename below is a single atomic syscall), then rename over
        # the real path - a concurrent reader (a PHP request) never sees a
        # half-written file, only the old value or the new one.
        TMP_FILE=$(mktemp "$STATE_DIR/.mode.tmp.XXXXXX")
        printf '%s\n' "$ACTION" > "$TMP_FILE"
        chmod 0644 "$TMP_FILE"
        mv -f "$TMP_FILE" "$STATE_FILE"

        echo "$(date '+%Y-%m-%d %H:%M:%S') - PirateBox mode set to: $ACTION"
        ;;
    status)
        if [ -r "$STATE_FILE" ]; then
            echo "State file: $STATE_FILE"
            echo "Raw content: $(cat "$STATE_FILE")"
        else
            echo "State file $STATE_FILE does not exist or is not readable."
            echo "The site will treat this as: normal (safe default)."
        fi
        ;;
    *)
        usage
        ;;
esac
