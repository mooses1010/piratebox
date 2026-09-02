#!/bin/bash
#
# MANUAL maintenance utility - NOT scheduled by cron by default.
#
# Phase 2 (2026-08-31) decision: this PirateBox's default data-retention
# policy is "automatic deletion of user content = OFF". Uploads, chat
# history, and logbook entries persist indefinitely unless an operator
# runs this script by hand (or a future configurable admin-interface
# cleanup policy is deliberately enabled). See
# docs/OPERATIONAL-DECISIONS.md for the full rationale. Do not re-add a
# cron entry for this script without updating that document.
#
# WARNING: running this script deletes ALL uploaded files and ALL
# chat/logbook/bulletin/recovery-message history immediately and
# irreversibly. There is no undo.
#
# Gap closed 2026-09-02 (roadmap reconciliation - flagged in Stage 25,
# repeated in Stage 32's own end-of-batch checklist, never actually
# fixed until now): this script's own header and README.md both always
# described its scope as "wipe everything" / "all uploads + all
# chat/[logbook] history," but bulletin.json and recovery-messages.json
# were never actually included below - an operator running this
# expecting a true "wipe everything" would have found those two stores
# silently untouched. Both admin/index.php's individual clear_bulletin/
# purge_recovery_all actions already covered them (this was never a
# case of no cleanup mechanism existing at all) - only this specific
# "wipe everything at once" script had the gap.

# The directory to clean
TARGET_DIR="/var/www/html"

# Check if the directory exists
if [ -d "$TARGET_DIR" ]; then
    # Remove all files and folders inside the target directory
    # The :? syntax prevents running on root if the variable is unset
    rm -rf "${TARGET_DIR:?}"/public/uploads/*

    # Remove messages json file (-f: it may not exist yet on a fresh install)
    rm -f "${TARGET_DIR:?}"/data/messages.json

    # Remove chat messages json file (-f: it may not exist yet on a fresh install)
    rm -f "${TARGET_DIR:?}"/data/chat.json

    # Remove bulletin board posts (-f: may not exist yet - Stage 22)
    rm -f "${TARGET_DIR:?}"/data/bulletin.json

    # Remove found-device recovery messages (-f: may not exist yet - Stage 16)
    rm -f "${TARGET_DIR:?}"/data/recovery-messages.json

    # Set ownership to www-data user and group
    chown www-data:www-data "$TARGET_DIR"

    # Set permissions to 0755 (rwxr-xr-x)
    chmod 0755 "$TARGET_DIR"/public/uploads
fi

echo $(date) ": Ran purge_uploads.sh"