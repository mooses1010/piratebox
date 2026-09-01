#!/bin/bash
#
# Stage 25 (backup/restore): restores a tar.gz created by
# backup_piratebox_data.sh back onto the live site's data/ and
# public/uploads/ directories.
#
# DELIBERATELY NOT part of the NOPASSWD sudo automation
# (etc/sudoers.d/piratebox-claude) and NOT installed to /usr/local/bin -
# restoring live data is rare, high-stakes, and irreversible (it
# overwrites whatever chat/guestbook/bulletin/recovery-message history,
# device ID, and uploads currently exist), so this always requires the
# operator's own sudo password, on purpose, every single time, run
# directly from a checkout of this repo. It is also NOT exposed
# anywhere in the web UI (admin panel included) - unlike purge (which
# is confirm-gated but web-reachable), a restore path reachable over
# the network would be a much larger foothold for anyone who ever
# guessed/found the admin password, so this only ever runs from a local
# shell with sudo. See docs/OPERATIONAL-DECISIONS.md for the full
# rationale.
#
# Usage: sudo bash tools/restore_piratebox_data.sh <path-to-backup.tar.gz> [--yes]
#   --yes skips the interactive confirmation prompt (for a supervised,
#   scripted restore only - never pass this without having already
#   decided to proceed).

set -euo pipefail

SITE_ROOT="/var/www/html"

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ] || [ -z "${1:-}" ]; then
    echo "Usage: $0 <path-to-backup.tar.gz> [--yes]" >&2
    exit 1
fi

ARCHIVE="$1"
ASSUME_YES="${2:-}"

if [ "$(id -u)" -ne 0 ]; then
    echo "restore_piratebox_data.sh: must be run as root (sudo) - it needs to write files owned by www-data." >&2
    exit 1
fi

if [ ! -f "$ARCHIVE" ]; then
    echo "restore_piratebox_data.sh: $ARCHIVE not found." >&2
    exit 1
fi

# Sanity-check this actually looks like one of backup_piratebox_data.sh's
# own archives before extracting it anywhere - refuses an arbitrary or
# unrelated tarball rather than blindly trusting the filename/extension.
if ! tar -tzf "$ARCHIVE" 2>/dev/null | grep -qE '^(data|uploads)/'; then
    echo "restore_piratebox_data.sh: $ARCHIVE doesn't look like a backup_piratebox_data.sh archive (expected top-level data/ and uploads/ entries) - refusing." >&2
    exit 1
fi

echo "This will OVERWRITE the live chat/guestbook/bulletin/recovery-message"
echo "history, device ID, Emergency Mode runtime log, and uploaded files at"
echo "$SITE_ROOT with the contents of:"
echo "  $ARCHIVE"
echo "This cannot be undone except by restoring a different backup."
echo

if [ "$ASSUME_YES" != "--yes" ]; then
    read -r -p "Type YES to continue: " CONFIRM
    if [ "$CONFIRM" != "YES" ]; then
        echo "Aborted - no changes made."
        exit 1
    fi
fi

STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT
tar -xzf "$ARCHIVE" -C "$STAGING"

if [ -d "$STAGING/data" ]; then
    for f in "$STAGING"/data/*; do
        [ -e "$f" ] || continue
        name=$(basename "$f")
        cp "$f" "$SITE_ROOT/data/$name"
        chown www-data:www-data "$SITE_ROOT/data/$name"
    done
fi

if [ -d "$STAGING/uploads" ]; then
    for f in "$STAGING"/uploads/*; do
        [ -e "$f" ] || continue
        cp "$f" "$SITE_ROOT/public/uploads/"
        chown www-data:www-data "$SITE_ROOT/public/uploads/$(basename "$f")"
    done
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - restore_piratebox_data.sh: restored from $ARCHIVE"
