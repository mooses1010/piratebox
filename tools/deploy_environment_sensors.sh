#!/bin/bash
#
# Deploys the Environment web UI's system-level plumbing (2026-09-07):
# the updated piratebox-oled.service unit (gains
# RuntimeDirectory=piratebox-sensors, so the daemon can publish its new
# sensors-public.json export under ProtectSystem=strict), the updated
# PHP-FPM open_basedir (one new named file added, same narrow pattern
# already used for status.json/progression-public.json), and the OLED
# daemon + BH1750 module themselves (via tools/update_progression.sh,
# not duplicated here). Run as root:
#
#   sudo tools/deploy_environment_sensors.sh
#
# Idempotent - safe to re-run.
#
# WHY THESE PIECES TOGETHER: all three are required for
# /utility/environment/ to show a real reading - the daemon's new
# publish_sensors_export() needs somewhere to write
# (RuntimeDirectory=), PHP needs to be allowed to read the one new file
# it writes there (open_basedir), and the daemon needs to actually be
# running the new code that calls that function at all.
#
# SAFE BY CONSTRUCTION: touches exactly these files and restarts
# exactly two already-optional-to-Core services - piratebox-oled.service
# (no Requires=/BindsTo= on hostapd/dnsmasq/nginx/php-fpm in either
# direction, unchanged by this round) and php8.4-fpm (already a
# pre-existing dependency of the whole site; restarting it briefly for
# a config change is the same operational cost any open_basedir edit
# already requires, not something new this script introduces).

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This must be run as root (sudo tools/deploy_environment_sensors.sh)." >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Step 1: piratebox-oled.service unit (RuntimeDirectory=piratebox-sensors) ==="
cp "$REPO_ROOT/etc/systemd/system/piratebox-oled.service" /etc/systemd/system/piratebox-oled.service
systemctl daemon-reload
echo "Updated and reloaded - takes effect on this service's next (re)start below."

echo
echo "=== Step 2: PHP open_basedir (idempotent) ==="
PHP_INI=/etc/php/8.4/fpm/php.ini
if grep -q '/run/piratebox-sensors/sensors-public.json' "$PHP_INI"; then
    echo "Already present - no edit needed."
else
    sed -i '/^open_basedir = /{/sensors-public\.json/!s|$|:/run/piratebox-sensors/sensors-public.json|}' "$PHP_INI"
    echo "Added /run/piratebox-sensors/sensors-public.json to open_basedir."
fi
systemctl restart php8.4-fpm
echo "php8.4-fpm restarted."

echo
echo "=== Step 3: OLED daemon + BH1750 module (also restarts piratebox-oled) ==="
bash "$REPO_ROOT/tools/update_progression.sh"

echo
echo "=== Step 4: verify the new export actually appears ==="
echo "Waiting up to ${SENSORS_WAIT:-25}s for the daemon's first publish..."
for i in $(seq 1 "${SENSORS_WAIT:-25}"); do
    if [ -s /run/piratebox-sensors/sensors-public.json ]; then
        break
    fi
    sleep 1
done
ls -la /run/piratebox-sensors/ 2>&1 || echo "(directory not present yet - check journalctl -u piratebox-oled)"
echo
cat /run/piratebox-sensors/sensors-public.json 2>&1 || echo "(file not present yet)"
echo
echo "=== Step 5: regression check - OLED/RTC/EEPROM bus neighbors unaffected ==="
i2cdetect -y 1 || true
