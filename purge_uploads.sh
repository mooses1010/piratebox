#!/bin/bash
#
# MANUAL maintenance utility - NOT scheduled by cron by default.
#
# Phase 2 (2026-08-31) decision: this PirateBox's default data-retention
# policy is "automatic deletion of user content = OFF". Uploads, chat
# history, and guestbook messages persist indefinitely unless an operator
# runs this script by hand (or a future configurable admin-interface
# cleanup policy is deliberately enabled). See
# docs/OPERATIONAL-DECISIONS.md for the full rationale. Do not re-add a
# cron entry for this script without updating that document.
#
# WARNING: running this script deletes ALL uploaded files and ALL chat/
# guestbook history immediately and irreversibly. There is no undo.

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

    # Set ownership to www-data user and group
    chown www-data:www-data "$TARGET_DIR"

    # Set permissions to 0755 (rwxr-xr-x)
    chmod 0755 "$TARGET_DIR"/public/uploads
fi

echo $(date) ": Ran purge_uploads.sh"