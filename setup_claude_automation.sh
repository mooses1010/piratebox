#!/bin/bash
#
# ONE-TIME setup: installs the two root-owned helper scripts
# (piratebox_deploy.sh, set_piratebox_mode.sh) to /usr/local/bin and
# installs a narrow sudoers NOPASSWD rule so Claude Code's automation can
# invoke exactly those, with exactly those arguments, without a password
# prompt each time. See docs/OPERATIONAL-DECISIONS.md ("Claude deployment/
# mode-switch automation") for the full design rationale.
#
# This does NOT grant broad or passwordless sudo generally - only these
# two specific, non-destructive, root-owned (moose-unwritable) scripts.
# Review etc/sudoers.d/piratebox-claude before running this.
#
# Run with: sudo ./setup_claude_automation.sh
#
# Idempotent - safe to re-run after updating either script's source in
# this repo to push the update live.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This installs system-wide root-owned files and a sudoers rule - re-run with sudo." >&2
    exit 1
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Installing helper scripts to /usr/local/bin (root:root, 0755) =="
install -m 0755 -o root -g root "$REPO_DIR/piratebox_deploy.sh" /usr/local/bin/piratebox_deploy.sh
install -m 0755 -o root -g root "$REPO_DIR/set_piratebox_mode.sh" /usr/local/bin/set_piratebox_mode.sh
echo "  installed: /usr/local/bin/piratebox_deploy.sh"
echo "  installed: /usr/local/bin/set_piratebox_mode.sh"

echo
echo "== Validating and installing sudoers rule =="
SUDOERS_SRC="$REPO_DIR/etc/sudoers.d/piratebox-claude"
if ! visudo -cf "$SUDOERS_SRC"; then
    echo "sudoers syntax check FAILED - not installing. No changes made." >&2
    exit 1
fi
install -m 0440 -o root -g root "$SUDOERS_SRC" /etc/sudoers.d/piratebox-claude
echo "  installed: /etc/sudoers.d/piratebox-claude"

echo
echo "== Verifying =="
ls -la /usr/local/bin/piratebox_deploy.sh /usr/local/bin/set_piratebox_mode.sh /etc/sudoers.d/piratebox-claude
echo
echo "Done. As the moose user, these should now work with no password prompt:"
echo "  sudo /usr/local/bin/piratebox_deploy.sh --dry-run"
echo "  sudo /usr/local/bin/set_piratebox_mode.sh status"
