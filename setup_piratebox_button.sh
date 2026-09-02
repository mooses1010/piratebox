#!/bin/bash
#
# ONE-TIME setup: creates the dedicated, unprivileged `piratebox-gpio`
# system user, installs the button daemon to /usr/local/bin, installs
# its narrow sudoers NOPASSWD rule, and installs+enables the systemd
# service. See docs/OPERATIONAL-DECISIONS.md ("Stage 29 Implementation:
# Physical Shutdown Button") for the full design rationale, and
# piratebox_button_daemon.py's own header for what the daemon does.
#
# SAFE BY DEFAULT: the installed service does NOT enable real shutdown -
# a 4-second hold only logs what it would have done until you
# deliberately add PIRATEBOX_BUTTON_ENABLE_SHUTDOWN=1 to the unit
# yourself (see etc/systemd/system/piratebox-button.service's own
# comment for exactly where), after verifying the persistent service
# end-to-end. This script does not flip that switch for you.
#
# This does NOT grant broad or passwordless sudo - only one exact
# command (`systemctl poweroff`, no arguments to vary) to one dedicated,
# unprivileged system user. Review etc/sudoers.d/piratebox-button before
# running this.
#
# Run with: sudo ./setup_piratebox_button.sh
#
# Idempotent - safe to re-run after updating the daemon script or unit
# file in this repo to push the update live. Does not remove or
# re-enable the shutdown opt-in if you've already set it (a re-run only
# touches the base unit file's content up to, not including, the
# Environment= line you'd have added yourself in a drop-in - see below).

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This creates a system user and installs system-wide files - re-run with sudo." >&2
    exit 1
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Creating dedicated system user (if not already present) =="
if id piratebox-gpio >/dev/null 2>&1; then
    echo "  piratebox-gpio already exists - leaving it as-is."
else
    useradd --system --no-create-home --shell /usr/sbin/nologin --groups gpio piratebox-gpio
    echo "  created: piratebox-gpio (system user, no login, no home, member of 'gpio' group only)"
fi

echo
echo "== Installing the daemon to /usr/local/bin (root:root, 0755) =="
install -m 0755 -o root -g root "$REPO_DIR/piratebox_button_daemon.py" /usr/local/bin/piratebox_button_daemon.py
echo "  installed: /usr/local/bin/piratebox_button_daemon.py"

echo
echo "== Validating and installing sudoers rule =="
SUDOERS_SRC="$REPO_DIR/etc/sudoers.d/piratebox-button"
if ! visudo -cf "$SUDOERS_SRC"; then
    echo "sudoers syntax check FAILED - not installing. No changes made." >&2
    exit 1
fi
install -m 0440 -o root -g root "$SUDOERS_SRC" /etc/sudoers.d/piratebox-button
echo "  installed: /etc/sudoers.d/piratebox-button"

echo
echo "== Installing systemd unit =="
install -m 0644 -o root -g root "$REPO_DIR/etc/systemd/system/piratebox-button.service" /etc/systemd/system/piratebox-button.service
systemctl daemon-reload
systemctl enable piratebox-button.service
systemctl restart piratebox-button.service
echo "  installed, enabled, and (re)started: piratebox-button.service"

echo
echo "== Verifying =="
id piratebox-gpio
ls -la /usr/local/bin/piratebox_button_daemon.py /etc/sudoers.d/piratebox-button /etc/systemd/system/piratebox-button.service
systemctl status piratebox-button.service --no-pager -l || true

echo
echo "Done. The daemon is running in DRY-RUN mode - a 4-second hold on"
echo "GPIO25 will log 'LONG PRESS DETECTED - would request shutdown' but"
echo "will NOT actually shut the Pi down. Check journalctl -u piratebox-button"
echo "to confirm it's detecting presses correctly before enabling the real"
echo "shutdown action."
