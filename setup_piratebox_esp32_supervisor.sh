#!/bin/bash
#
# ONE-TIME setup: installs the ESP32-S3 hardware/sensor supervisor
# daemon to /usr/local/bin and installs+enables its systemd service.
# See docs/ESP32-SUPERVISOR-DESIGN.md for the full design, and
# piratebox_esp32_supervisor.py's own header for what the daemon does.
#
# Reuses the existing `piratebox-gpio` system user (created by
# setup_piratebox_button.sh) - no new account, no new sudoers grant.
# This service touches no privileged operation at all: it only reads a
# serial port (via SupplementaryGroups=dialout, granted per-service by
# the unit file, not by a persistent usermod) and writes its own small
# export under a systemd-managed RuntimeDirectory.
#
# Run with: sudo ./setup_piratebox_esp32_supervisor.sh
#
# Idempotent - safe to re-run after updating the daemon script or unit
# file in this repo to push an update live.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This installs a system-wide daemon and systemd unit - re-run with sudo." >&2
    exit 1
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Checking for the shared piratebox-gpio system account =="
if ! id piratebox-gpio >/dev/null 2>&1; then
    echo "  piratebox-gpio does not exist yet - run setup_piratebox_button.sh first" \
         "(it creates this shared, unprivileged account)." >&2
    exit 1
fi
echo "  found: piratebox-gpio"

echo
echo "== Installing the daemon and its imported modules to /usr/local/bin (root:root, 0755/0644) =="
install -m 0755 -o root -g root "$REPO_DIR/piratebox_esp32_supervisor.py" /usr/local/bin/piratebox_esp32_supervisor.py
install -m 0644 -o root -g root "$REPO_DIR/piratebox_esp32_client.py" /usr/local/bin/piratebox_esp32_client.py
# piratebox_ds18b20_roles.py (2026-09-07) - imported by the daemon
# above; must live alongside it (the daemon's own script directory is
# on sys.path automatically) for that import to resolve at runtime.
install -m 0644 -o root -g root "$REPO_DIR/piratebox_ds18b20_roles.py" /usr/local/bin/piratebox_ds18b20_roles.py
echo "  installed: /usr/local/bin/piratebox_esp32_supervisor.py"
echo "  installed: /usr/local/bin/piratebox_esp32_client.py"
echo "  installed: /usr/local/bin/piratebox_ds18b20_roles.py"

echo
echo "== Installing systemd unit =="
install -m 0644 -o root -g root "$REPO_DIR/etc/systemd/system/piratebox-esp32-supervisor.service" \
    /etc/systemd/system/piratebox-esp32-supervisor.service
systemctl daemon-reload
systemctl enable piratebox-esp32-supervisor.service
systemctl restart piratebox-esp32-supervisor.service
echo "  installed, enabled, and (re)started: piratebox-esp32-supervisor.service"

echo
echo "== Verifying =="
ls -la /usr/local/bin/piratebox_esp32_supervisor.py /usr/local/bin/piratebox_esp32_client.py \
       /usr/local/bin/piratebox_ds18b20_roles.py /etc/systemd/system/piratebox-esp32-supervisor.service
sleep 2
systemctl status piratebox-esp32-supervisor.service --no-pager -l || true
echo
ls -la /var/lib/piratebox-esp32/ 2>&1 || echo "  (StateDirectory not yet created - should appear after the service's first start above)"

echo
echo "Done. Check 'journalctl -u piratebox-esp32-supervisor -f' and"
echo "'python3 tools/diagnose_esp32_supervisor.py' to confirm the board is"
echo "actually connected and reporting. Use 'python3 tools/ds18b20_commission.py"
echo "list' (or 'watch') once DS18B20 probes are physically wired to name them."
