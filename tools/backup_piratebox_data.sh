#!/bin/bash
#
# Stage 25 (backup/restore): creates a timestamped tar.gz snapshot of
# PirateBox's live, user-generated data - the chat/logbook/bulletin/
# recovery-message JSON stores, the device ID, the Emergency Mode
# runtime log, and uploaded files - into ~/piratebox-data-backups/, then
# prunes old backups beyond a fixed retention count.
#
# This is a DIFFERENT thing from the ~/piratebox-backups/ pre-stage
# snapshots a Claude session takes before deploying a code change (those
# capture the whole var/www/html tree once per development stage, for
# rollback during development). This script instead protects the live
# COMMUNITY DATA itself against SD card corruption or accidental loss
# during actual field/emergency use - meant to be run regularly (see the
# optional systemd timer below), not just before a code change.
#
# Read-only against the live site: every file this touches
# (data/*.json, data/*.log, public/uploads/*) is world-readable by
# design (see includes/config.php and every JSON store's own comments),
# so this runs as a normal user - no sudo needed, and it can never write
# anywhere the account running it couldn't already write on its own.
#
# Usage: tools/backup_piratebox_data.sh [--retain N]   (default N=30)
#
# To run automatically instead of by hand, see the (documented, not
# auto-installed - see docs/OPERATIONAL-DECISIONS.md) systemd timer at
# etc/systemd/system/piratebox-backup.timer.

set -euo pipefail

SITE_ROOT="/var/www/html"
BACKUP_DIR="$HOME/piratebox-data-backups"
RETAIN=30

if [ "$#" -gt 0 ]; then
    if [ "$#" -eq 2 ] && [ "$1" = "--retain" ] && [[ "$2" =~ ^[0-9]+$ ]] && [ "$2" -gt 0 ]; then
        RETAIN="$2"
    else
        echo "Usage: $0 [--retain N]" >&2
        exit 1
    fi
fi

mkdir -p "$BACKUP_DIR"

# Refuse to run if the destination filesystem is nearly full - a backup
# script that risks filling the disk it's meant to protect against data
# loss on would be self-defeating. 50MB is comfortably larger than this
# project's entire live data footprint has ever been (Stage 24's own
# low-storage guard uses 5MB for a single small write; this allows
# headroom for a full tar.gz of everything at once, even with a modest
# uploads folder).
AVAIL_KB=$(df -Pk "$BACKUP_DIR" | awk 'NR==2 {print $4}')
if [ "${AVAIL_KB:-0}" -lt 51200 ]; then
    echo "backup_piratebox_data.sh: refusing to run - less than 50MB free at $BACKUP_DIR" >&2
    exit 1
fi

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
ARCHIVE="$BACKUP_DIR/piratebox-data-$TIMESTAMP.tar.gz"
STAGING=$(mktemp -d)
trap 'rm -rf "$STAGING"' EXIT

# Copy only what's actually live data, skipping lock files (always
# empty/transient scratch state, never data) and gracefully skipping
# anything that doesn't exist yet (a fresh install, or a store nobody
# has posted to yet - e.g. bulletin.json before the first bulletin
# post).
mkdir -p "$STAGING/data" "$STAGING/uploads"
for f in chat.json messages.json bulletin.json recovery-messages.json \
         device-id.json mode-transitions.log; do
    if [ -f "$SITE_ROOT/data/$f" ]; then
        cp "$SITE_ROOT/data/$f" "$STAGING/data/$f"
    fi
done
if [ -d "$SITE_ROOT/public/uploads" ]; then
    find "$SITE_ROOT/public/uploads" -maxdepth 1 -type f -exec cp {} "$STAGING/uploads/" \;
fi

tar -czf "$ARCHIVE" -C "$STAGING" data uploads

# Verify the archive is actually readable before trusting it - a backup
# that silently corrupted during write would be worse than no backup at
# all (false confidence at exactly the moment it matters).
if ! tar -tzf "$ARCHIVE" > /dev/null 2>&1; then
    echo "backup_piratebox_data.sh: archive verification failed for $ARCHIVE" >&2
    rm -f "$ARCHIVE"
    exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - backup_piratebox_data.sh: created $ARCHIVE ($(du -h "$ARCHIVE" | cut -f1))"

# Prune: keep only the newest $RETAIN backups this script created. Only
# ever touches files matching this script's own naming pattern in its
# own backup directory - never anything else.
mapfile -t OLD < <(ls -1t "$BACKUP_DIR"/piratebox-data-*.tar.gz 2>/dev/null | tail -n "+$((RETAIN + 1))")
if [ "${#OLD[@]}" -gt 0 ]; then
    for old in "${OLD[@]}"; do
        rm -f "$old"
        echo "$(date '+%Y-%m-%d %H:%M:%S') - backup_piratebox_data.sh: pruned $old (retention: $RETAIN)"
    done
fi
