#!/bin/bash
#
# Syncs this repo's var/www/html/ tree onto the live /var/www/html/.
#
# SAFE BY CONSTRUCTION:
#   - No arguments accepted except an optional --dry-run (anything else is
#     rejected). There is no argument that changes source/destination/
#     behavior beyond that one flag - nothing here is attacker-controlled
#     input, so there is no argument-injection surface.
#   - No --delete: this can only ADD or UPDATE files that exist in the
#     repo. It can never remove a live file. Removing something from the
#     site remains a deliberate, separate, manual action.
#   - Explicit --exclude list for every piece of live user-generated
#     content (uploads, chat/guestbook data, recovery messages, the
#     deployed VERSION file, the admin password hash, generated QR codes) -
#     belt-and-suspenders on top of the fact that none of these are ever
#     tracked in the repo/.gitignore in the first place, so a plain sync
#     could not touch them even without these excludes. See
#     docs/OPERATIONAL-DECISIONS.md for the full rationale ("Claude
#     deployment/mode-switch automation"; recovery-messages.json gap found
#     and fixed in Stage 17 - see that entry for what happened and why).
#     IMPORTANT: any future live-writable data store (a new user-facing
#     form that writes its own JSON file) needs adding here BEFORE its
#     first deploy, not after - this file is the one place that forgetting
#     to do so has real consequences.
#   - Installed to /usr/local/bin, root:root, not writable by the `moose`
#     account - the account this runs on behalf of cannot modify what this
#     script actually does, only trigger it via the narrow sudoers rule
#     that names this exact path.
#
# Run via: sudo /usr/local/bin/piratebox_deploy.sh [--dry-run]

set -euo pipefail

SRC="/home/moose/piratebox/var/www/html/"
DST="/var/www/html/"

DRYRUN=()
if [ "$#" -gt 0 ]; then
    if [ "$#" -eq 1 ] && [ "$1" = "--dry-run" ]; then
        DRYRUN=(--dry-run)
    else
        echo "Usage: $0 [--dry-run]" >&2
        exit 1
    fi
fi

rsync -a "${DRYRUN[@]}" --chown=www-data:www-data \
    --exclude 'uploads/' \
    --exclude 'data/chat.json' \
    --exclude 'data/chat.json.lock' \
    --exclude 'data/messages.json' \
    --exclude 'data/messages.json.lock' \
    --exclude 'data/recovery-messages.json' \
    --exclude 'data/recovery-messages.json.lock' \
    --exclude 'data/mode-transitions.log' \
    --exclude 'includes/VERSION' \
    --exclude 'public/assets/qr-url.png' \
    --exclude 'public/assets/qr-wifi.png' \
    --exclude '.piratebox_admin_htpasswd' \
    "$SRC" "$DST"

if [ "${#DRYRUN[@]}" -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - piratebox_deploy.sh: synced $SRC -> $DST"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - piratebox_deploy.sh: DRY RUN (nothing changed)"
fi
