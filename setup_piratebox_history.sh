#!/bin/bash
#
# ONE-TIME setup: installs the sensor-history sampler to /usr/local/bin,
# installs+enables its systemd timer, and grants PHP-FPM read access to
# the new durable history store via open_basedir. See
# docs/ESP32-SUPERVISOR-DESIGN.md's history section for the full design,
# and piratebox_history.py/piratebox_history_sampler.py's own headers
# for what each piece does.
#
# Reuses the existing `piratebox-gpio` system user (same account the
# ESP32 supervisor/OLED/button daemons already run as) - no new
# account, no new sudoers grant. This subsystem touches no privileged
# operation: it only reads the ESP32 supervisor's already-published,
# world-readable cached export, and writes its own small, bounded,
# world-readable history files under a systemd-managed StateDirectory.
#
# Run with: sudo ./setup_piratebox_history.sh
#
# Idempotent - safe to re-run after updating piratebox_history.py/
# piratebox_history_sampler.py or either unit file in this repo to push
# an update live.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This installs a system-wide timer/service and edits php.ini - re-run with sudo." >&2
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
echo "== Installing the sampler and its imported modules to /usr/local/bin (root:root, 0755/0644) =="
install -m 0755 -o root -g root "$REPO_DIR/piratebox_history_sampler.py" /usr/local/bin/piratebox_history_sampler.py
install -m 0644 -o root -g root "$REPO_DIR/piratebox_history.py" /usr/local/bin/piratebox_history.py
# piratebox_esp32_client.py and piratebox_hardware_health.py are
# imported by the sampler above - only install them if not already
# present (they're already installed and kept current by
# setup_piratebox_esp32_supervisor.sh's own install step; re-installing
# here too would just be a second copy of the same already-current
# file, so this only fills a genuine gap on a system that somehow has
# the sampler but not the ESP32 supervisor - not expected in practice).
for f in piratebox_esp32_client.py piratebox_hardware_health.py; do
    if [ ! -f "/usr/local/bin/$f" ]; then
        install -m 0644 -o root -g root "$REPO_DIR/$f" "/usr/local/bin/$f"
        echo "  installed: /usr/local/bin/$f (was missing)"
    fi
done
echo "  installed: /usr/local/bin/piratebox_history_sampler.py"
echo "  installed: /usr/local/bin/piratebox_history.py"

echo
echo "== Installing systemd units =="
install -m 0644 -o root -g root "$REPO_DIR/etc/systemd/system/piratebox-history-sample.service" \
    /etc/systemd/system/piratebox-history-sample.service
install -m 0644 -o root -g root "$REPO_DIR/etc/systemd/system/piratebox-history-sample.timer" \
    /etc/systemd/system/piratebox-history-sample.timer
systemctl daemon-reload
systemctl enable --now piratebox-history-sample.timer
echo "  installed and enabled: piratebox-history-sample.timer"

echo
echo "== Granting PHP-FPM read access to the history store (open_basedir) =="
PHP_VER=$(ls /etc/php/ | sort -V | tail -n 1)
PHP_INI="/etc/php/$PHP_VER/fpm/php.ini"
if [ -f "$PHP_INI" ]; then
    if grep -q '/var/lib/piratebox-history' "$PHP_INI"; then
        echo "  already present in $PHP_INI - no change needed."
    else
        # Directory-scoped (not per-file, unlike the ESP32/sensors
        # exports elsewhere in this same open_basedir line) - the whole
        # point of this subsystem is a GROWING, unpredictable set of
        # per-signal filenames (one per DS18B20 ROM, plus future
        # sensors) that can't be enumerated in advance, the same reason
        # /var/www/html itself is a whole-directory entry rather than a
        # per-file list.
        sed -i "s|^open_basedir\s*=\s*\(.*\)|open_basedir = \1:/var/lib/piratebox-history|" "$PHP_INI"
        echo "  added /var/lib/piratebox-history to open_basedir in $PHP_INI"
        systemctl reload "php$PHP_VER-fpm" 2>/dev/null || systemctl restart "php$PHP_VER-fpm"
        echo "  reloaded php$PHP_VER-fpm"
    fi
else
    echo "  WARNING: $PHP_INI not found - open_basedir not updated. The history" >&2
    echo "  graphs on /utility/environment/ will not be able to read stored data" >&2
    echo "  until this is fixed by hand." >&2
fi

echo
echo "== Verifying =="
ls -la /usr/local/bin/piratebox_history_sampler.py /usr/local/bin/piratebox_history.py \
       /etc/systemd/system/piratebox-history-sample.service \
       /etc/systemd/system/piratebox-history-sample.timer
systemctl list-timers piratebox-history-sample.timer --no-pager || true
echo
echo "Triggering one immediate sample run to confirm it works end-to-end..."
systemctl start piratebox-history-sample.service
sleep 2
systemctl status piratebox-history-sample.service --no-pager -l || true
echo
ls -la /var/lib/piratebox-history/ 2>&1 || echo "  (StateDirectory not yet created - should appear after the run above)"

echo
echo "Done. Check 'journalctl -u piratebox-history-sample.service' to confirm a"
echo "sample was actually recorded, and /utility/environment/ for the new"
echo "historical graphs once a little data has accumulated."
