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
#   - Stage 26 (versioning): every real (non-dry-run) run re-stamps
#     includes/VERSION from this checkout's current HEAD, so the admin/
#     Stats pages' version display reflects what's actually live instead
#     of going stale after the first install (see
#     docs/OPERATIONAL-DECISIONS.md).
#   - Post-Stage-32 (Travel Mode): every real run also re-applies the
#     Travel Mode direct-access quarantine after syncing, in case this
#     deploy just wrote fresh, un-quarantined copies of a local-
#     sensitive static export over ones that were already quarantined
#     (see includes/travel_mode.php and docs/TRAVEL-MODE-DESIGN.md).
#
# Run via: sudo /usr/local/bin/piratebox_deploy.sh [--dry-run]

set -euo pipefail

SRC="/home/moose/piratebox/var/www/html/"
DST="/var/www/html/"
TOOLS_DIR="/home/moose/piratebox/tools"

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
    --exclude 'data/bulletin.json' \
    --exclude 'data/bulletin.json.lock' \
    --exclude 'data/content-profile.json' \
    --exclude 'data/connection-stats.json' \
    --exclude 'data/travel-mode.json' \
    --exclude 'data/travel-mode-quarantine/' \
    --exclude 'includes/VERSION' \
    --exclude 'public/assets/qr-url.png' \
    --exclude 'public/assets/qr-wifi.png' \
    --exclude '.piratebox_admin_htpasswd' \
    "$SRC" "$DST"

if [ "${#DRYRUN[@]}" -eq 0 ]; then
    # Stage 26 (versioning): keep includes/VERSION reflecting what's
    # actually live, not just what was true at initial install.
    # installer_pi_zero_trixie.sh's one-time stamp (Phase 4) went stale
    # after the very first deploy and was never updated again since -
    # found live still showing a "Phase 4" commit hash after 25
    # subsequent stages had already been deployed on top of it. Every
    # real (non-dry-run) deploy now re-stamps it from this checkout's
    # actual HEAD. Best-effort, same as the installer's own version
    # stamp: never fails the deploy itself if git isn't usable here for
    # some reason (e.g. a non-git deployment of this repo).
    if COMMIT=$(git -C "${SRC%/}" rev-parse HEAD 2>/dev/null); then
        echo "$COMMIT  (deployed $(date '+%Y-%m-%d %H:%M:%S %Z'))" > "${DST}includes/VERSION"
        chown www-data:www-data "${DST}includes/VERSION"
    fi

    # Post-Stage-32 (Travel Mode): seed data/travel-mode.json to "off" the
    # very first time this feature is deployed, before anything else ever
    # reads it. includes/travel_mode.php's own fail-safe default is "on"
    # (suppressed) for any UNEXPECTED missing/corrupt state - correct for
    # ongoing operation, but wrong for a first-ever deploy, which would
    # otherwise make Local Information appear to vanish the moment this
    # code ships for a box that was showing it normally. Only ever writes
    # this file if it doesn't already exist - never overwrites an
    # operator's actual, deliberate Travel Mode choice.
    if [ ! -f "${DST}data/travel-mode.json" ]; then
        echo '{"travel_mode": false}' > "${DST}data/travel-mode.json"
        chown www-data:www-data "${DST}data/travel-mode.json"
    fi

    # Re-apply the direct-access quarantine against what's now live.
    # Best-effort, same spirit as the VERSION stamp above - never fails
    # the deploy itself.
    if [ -f "$TOOLS_DIR/apply_travel_mode_quarantine.php" ]; then
        php "$TOOLS_DIR/apply_travel_mode_quarantine.php" "${DST%/}" || true
    fi

    echo "$(date '+%Y-%m-%d %H:%M:%S') - piratebox_deploy.sh: synced $SRC -> $DST"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - piratebox_deploy.sh: DRY RUN (nothing changed)"
fi
