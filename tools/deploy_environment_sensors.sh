#!/bin/bash
#
# Deploys the Environment web UI's system-level plumbing (2026-09-07;
# extended 2026-09-07 later the same day for the ESP32 supervisor's
# own export): the updated piratebox-oled.service unit (gains
# RuntimeDirectory=piratebox-sensors, so the daemon can publish its new
# sensors-public.json export under ProtectSystem=strict), the updated
# PHP-FPM open_basedir (each new named export file added, same narrow
# pattern already used for status.json/progression-public.json), and
# the OLED daemon + BH1750 module themselves (via tools/update_
# progression.sh, not duplicated here). Run as root:
#
#   sudo tools/deploy_environment_sensors.sh
#
# Idempotent - safe to re-run.
#
# WHY THESE PIECES TOGETHER: all three are required for
# /utility/environment/ to show a real reading - each daemon's own
# publish function needs somewhere to write (RuntimeDirectory=), PHP
# needs to be allowed to read the files it writes there
# (open_basedir), and the daemon needs to actually be running the new
# code that calls that function at all.
#
# A REAL GAP THIS SCRIPT WOULD HAVE CAUGHT (2026-09-07, ESP32 BH1750
# migration round): the ESP32 supervisor's own export
# (/run/piratebox-esp32/esp32-public.json, written by piratebox_esp32_
# supervisor.py) was added to includes/esp32_supervisor.php and wired
# into /utility/environment/ without ever adding it to open_basedir -
# the section silently, safely disappeared from the live page (correct
# "no fabricated data" degrade behavior, but for the wrong underlying
# reason) until this was caught and fixed. Lesson: any NEW named export
# file a PHP include reads must be added here (or a script like it)
# BEFORE assuming a page showing/hiding correctly means it's actually
# wired up end-to-end - a missing open_basedir entry looks identical,
# from the page's own behavior, to "hardware genuinely not installed."
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
echo "=== Step 2: PHP open_basedir (idempotent, one or more named exports) ==="
PHP_INI=/etc/php/8.4/fpm/php.ini
for EXPORT_PATH in \
    /run/piratebox-sensors/sensors-public.json \
    /run/piratebox-esp32/esp32-public.json \
; do
    if grep -q "$EXPORT_PATH" "$PHP_INI"; then
        echo "Already present: $EXPORT_PATH"
    else
        ESCAPED=$(printf '%s' "$EXPORT_PATH" | sed 's/[.[\*^$/]/\\&/g')
        sed -i "/^open_basedir = /{/$ESCAPED/!s|\$|:$EXPORT_PATH|}" "$PHP_INI"
        echo "Added: $EXPORT_PATH"
    fi
done
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
ls -la /run/piratebox-esp32/ 2>&1 || echo "(directory not present - check journalctl -u piratebox-esp32-supervisor, if that service is expected to be running)"
cat /run/piratebox-esp32/esp32-public.json 2>&1 || echo "(file not present - fine if the ESP32 supervisor isn't connected right now)"
echo
echo "=== Step 5: regression check - OLED/RTC/EEPROM bus neighbors unaffected ==="
i2cdetect -y 1 || true
