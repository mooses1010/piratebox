#!/bin/bash
#
# STAGED - DO NOT RUN except to actually reverse
# tools/migrate_visitor_ap_to_alfa.sh. Not installed, not in any
# sudoers grant, not referenced by any automation. See
# docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md "Rollback plan".
#
# Deliberately simple and defensive: this restores onboard wlan0 as the
# PirateBox visitor AP from the most recent pre-migration backup this
# host has, and is meant to be runnable over Ethernet/SSH by someone
# who is not deep in this design doc at 2am - minimal thinking required,
# maximal safety.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Must run as root (sudo)." >&2
    exit 1
fi

BACKUP_DIR=$(ls -dt /home/moose/piratebox-backups/visitor-ap-migration-pre-* 2>/dev/null | head -n1 || true)
if [ -z "$BACKUP_DIR" ] || [ ! -f "$BACKUP_DIR/hostapd.conf" ]; then
    echo "No migration backup found under /home/moose/piratebox-backups/." >&2
    echo "Falling back to restoring interface=wlan0 directly instead (same" >&2
    echo "net effect, just without restoring every other line from before" >&2
    echo "the migration - review the result)." >&2
    sed -i 's/^interface=pb-ap$/interface=wlan0/' /etc/hostapd/hostapd.conf
    sed -i 's/^interface=pb-ap$/interface=wlan0/' /etc/dnsmasq.conf
    # dhcpcd.conf's static 10.0.0.1/24 block also moved to pb-ap at
    # migration time (found necessary live, 2026-09-03 - see
    # docs/OPERATIONAL-DECISIONS.md "ALFA Migration Round") - move it
    # back, or the Pi ends up with neither interface holding 10.0.0.1.
    sed -i 's/^interface pb-ap$/interface wlan0/' /etc/dhcpcd.conf
else
    echo "Restoring from $BACKUP_DIR ..."
    cp -a "$BACKUP_DIR/hostapd.conf" /etc/hostapd/hostapd.conf
    cp -a "$BACKUP_DIR/dnsmasq.conf" /etc/dnsmasq.conf
    [ -f "$BACKUP_DIR/dhcpcd.conf" ] && cp -a "$BACKUP_DIR/dhcpcd.conf" /etc/dhcpcd.conf
fi

echo "Stopping hostapd/dnsmasq..."
systemctl stop hostapd dnsmasq

echo "Restarting dhcpcd to move the static IP back to wlan0..."
systemctl restart dhcpcd

echo "Starting hostapd/dnsmasq on wlan0..."
systemctl start hostapd dnsmasq

sleep 2
echo "--- Verifying restoration ---"
if iw dev wlan0 info | grep -q "type AP" && systemctl is-active --quiet hostapd && systemctl is-active --quiet dnsmasq && ip -4 addr show wlan0 | grep -q "inet 10\.0\.0\.1/24"; then
    echo "OK: wlan0 is back up as the PirateBox AP with 10.0.0.1/24, hostapd/dnsmasq active."
else
    echo "wlan0 did NOT come back up cleanly - hostapd/dnsmasq status:" >&2
    systemctl status hostapd dnsmasq --no-pager -l >&2
    echo "Ethernet/SSH access to this Pi is unaffected regardless of the" >&2
    echo "above - this failure is isolated to the wireless AP." >&2
    exit 1
fi

curl -sf -o /dev/null http://10.0.0.1/ && echo "OK: http://10.0.0.1/ responds." || echo "WARNING: http://10.0.0.1/ did not respond - investigate nginx/php-fpm separately, this is outside what this rollback touches."

echo
echo "Rollback complete. pb-ap (if present) has been left alone - it is not"
echo "started by this script, only wlan0's production role was restored."
