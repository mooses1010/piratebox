#!/bin/bash
#
# STAGED - DO NOT RUN. Not installed, not in any sudoers grant, not
# referenced by any automation. This is a reviewable draft of what the
# eventual production migration would actually execute, written so the
# migration itself is boring when it happens - see
# docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md "Migration plan" for the full
# design and the exact operator gate this script sits behind. Written
# during the External AP Architecture + Production Migration Readiness
# Round (2026-09-03); the AWUS036ACM Hardware Validation Round the same
# day proved the hardware/driver/AP-association layer works, but
# VALIDATED HARDWARE IS NOT THE SAME THING AS THIS SCRIPT BEING SAFE TO
# RUN - see that design doc's power-aware migration gate before ever
# running this for real.
#
# This script performs the ACTUAL migration - it hardcodes the two
# things this whole round was explicitly told never to do automatically:
# switching production hostapd to the ALFA, and moving 10.0.0.1 off
# wlan0. It is written, reviewed, and committed BUT NOT EXECUTED.
# Running it requires a human to read this whole header, confirm every
# preflight item below by hand, and invoke it deliberately - never as a
# side effect of any other automation (deploy, a scheduled task, a
# future Claude session finding it and assuming staged == approved).
#
# WHAT THIS DOES: stops production hostapd/dnsmasq on wlan0, starts them
# again bound to pb-ap instead, preserving every higher-level PirateBox
# behavior (10.0.0.1, dnsmasq's wildcard DNS/DHCP config, captive
# portal, nginx, the site itself) completely unchanged - only the
# physical radio changes. See "Captive/DHCP/DNS implications" in the
# design doc for why this is safe to do without a second PirateBox
# implementation: /etc/hostapd/hostapd.conf and /etc/dnsmasq.conf's
# interface= line is the ONLY thing this script changes in either file.
#
# WHAT THIS DELIBERATELY DOES NOT DO: touch nginx, PHP-FPM, captive
# portal logic, the site itself, live community data, or NetworkManager
# beyond the exclusion list already staged in
# etc/NetworkManager/conf.d/99-piratebox.conf. Does not repurpose
# onboard wlan0 for anything (management/scanning) - it is simply
# stopped, staying available and idle for a future deliberate decision.
# Does not touch regulatory domain - that is Preflight item 5 below, a
# SEPARATE, already-gated operator action (see the design doc's
# "Regulatory domain" section for the exact commands), because this
# script refuses to run without it already being correct.
#
# ROLLBACK: tools/rollback_visitor_ap_to_onboard.sh reverses every step
# here. Read it before running this script, not after something looks
# wrong.

set -euo pipefail

echo "=================================================================="
echo "  PirateBox visitor-AP migration: onboard wlan0 -> external pb-ap"
echo "  THIS SCRIPT IS STAGED. It should not normally be reachable to"
echo "  run - if you are seeing this banner, STOP and re-read"
echo "  docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md 'Migration plan' first."
echo "=================================================================="
echo

if [ "${PIRATEBOX_MIGRATION_CONFIRMED:-}" != "yes-I-read-the-design-doc" ]; then
    echo "Refusing to run: set PIRATEBOX_MIGRATION_CONFIRMED=yes-I-read-the-design-doc" >&2
    echo "to proceed, after actually reading that doc and confirming every" >&2
    echo "preflight item below by hand. This guard exists so this script" >&2
    echo "cannot be accidentally executed by a copy-paste or automation." >&2
    exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
    echo "Must run as root (sudo)." >&2
    exit 1
fi

# --- Preflight ------------------------------------------------------------
# Every check here is a hard stop (set -e + explicit checks) - this
# script refuses to proceed rather than migrate onto an unconfirmed
# foundation. Nothing below this block modifies anything.

echo "--- Preflight ---"

echo "[1/6] Ethernet management path..."
ip -br link show eth0 | grep -q "UP" || { echo "FAIL: eth0 is not up - refusing to remove your only other path to this Pi." >&2; exit 1; }
echo "  OK: eth0 is up."

echo "[2/6] Stable ALFA identity (pb-ap)..."
ip link show pb-ap >/dev/null 2>&1 || { echo "FAIL: no 'pb-ap' interface - is etc/udev/rules.d/99-piratebox-external-ap.rules installed and has the adapter been replugged/rebooted since?" >&2; exit 1; }
echo "  OK: pb-ap exists."

echo "[3/6] pb-ap driver sanity..."
DRIVER=$(ethtool -i pb-ap 2>/dev/null | awk -F': ' '/^driver/ {print $2}')
[ "$DRIVER" = "mt76x2u" ] || { echo "FAIL: pb-ap driver is '$DRIVER', expected mt76x2u." >&2; exit 1; }
echo "  OK: driver is mt76x2u."

echo "[4/6] Regulatory domain..."
CURRENT_REG=$(iw reg get | awk '/^country/ {print $2; exit}' | tr -d ':')
if [ "$CURRENT_REG" = "00" ]; then
    echo "FAIL: regulatory domain is still world/00. This migration defaults to" >&2
    echo "a 2.4GHz channel that IS legal under world/00 (see design doc), but a" >&2
    echo "chronically wrong regulatory domain is itself a real problem to fix" >&2
    echo "first - see docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md 'Regulatory" >&2
    echo "domain' for the exact fix (a one-character typo, UM -> US, found live" >&2
    echo "in /boot/firmware/cmdline.txt during this round)." >&2
    exit 1
fi
echo "  OK: regulatory domain is $CURRENT_REG."

echo "[5/6] NetworkManager ownership..."
grep -q "interface-name:pb-ap" /etc/NetworkManager/conf.d/99-piratebox.conf 2>/dev/null || { echo "FAIL: pb-ap is not excluded from NetworkManager - install the staged etc/NetworkManager/conf.d/99-piratebox.conf first." >&2; exit 1; }
echo "  OK: pb-ap is NetworkManager-excluded."

echo "[6/6] Power-aware migration gate..."
echo "  This script CANNOT verify the soak/multi-client evidence bar from"
echo "  docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md 'Power-aware migration gate'"
echo "  automatically - that requires a human decision informed by a real"
echo "  extended soak test, not a boot-time check. Confirming"
echo "  PIRATEBOX_MIGRATION_CONFIRMED above is where that human judgment"
echo "  call is supposed to have already happened - this is a reminder, not"
echo "  an automated pass/fail."
echo

read -r -p "Type 'migrate' to proceed, anything else aborts: " CONFIRM
[ "$CONFIRM" = "migrate" ] || { echo "Aborted, nothing changed."; exit 1; }

# --- Backup current production config before touching anything -----------
BACKUP_DIR="/home/moose/piratebox-backups/visitor-ap-migration-pre-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -a /etc/hostapd/hostapd.conf "$BACKUP_DIR/"
cp -a /etc/dnsmasq.conf "$BACKUP_DIR/"
cp -a /etc/dhcpcd.conf "$BACKUP_DIR/" 2>/dev/null || true
echo "Backed up current production config to $BACKUP_DIR"

# --- Migration --------------------------------------------------------------
echo "--- Migration ---"

echo "Stopping hostapd/dnsmasq..."
systemctl stop hostapd dnsmasq

echo "Rewriting interface= in /etc/hostapd/hostapd.conf, /etc/dnsmasq.conf, and /etc/dhcpcd.conf..."
sed -i 's/^interface=wlan0$/interface=pb-ap/' /etc/hostapd/hostapd.conf
sed -i 's/^interface=wlan0$/interface=pb-ap/' /etc/dnsmasq.conf
# dhcpcd.conf: move the static 10.0.0.1/24 block from wlan0 to pb-ap.
# Found live during the first migration attempt (2026-09-03): stopping
# hostapd's wlan0 binding takes the interface fully DOWN (nothing else
# keeps it up), so leaving this block on wlan0 - the original plan -
# means nothing holds 10.0.0.1 any more, while pb-ap (no static block
# of its own) falls through to dhcpcd's default per-interface DHCP-
# client/IPv4LL behavior and self-assigns a useless 169.254.x.x
# address instead. Confirmed: nginx itself was never the problem
# (listen 80 default_server, no bound IP) - nothing on the Pi held the
# address at all. See docs/OPERATIONAL-DECISIONS.md "ALFA Migration
# Round" for the full evidence chain.
sed -i 's/^interface wlan0$/interface pb-ap/' /etc/dhcpcd.conf
echo "Restarting dhcpcd to apply the moved static IP..."
systemctl restart dhcpcd

echo "Starting hostapd/dnsmasq on pb-ap..."
systemctl start hostapd dnsmasq

echo "--- Post-migration live checks ---"
sleep 2
iw dev pb-ap info | grep -q "type AP" || { echo "FAIL: pb-ap did not come up as AP - see rollback script." >&2; exit 1; }
systemctl is-active --quiet hostapd || { echo "FAIL: hostapd not active - see rollback script." >&2; exit 1; }
systemctl is-active --quiet dnsmasq || { echo "FAIL: dnsmasq not active - see rollback script." >&2; exit 1; }
ip -4 addr show pb-ap | grep -q "inet 10\.0\.0\.1/24" || { echo "FAIL: pb-ap does not hold 10.0.0.1/24 - dhcpcd did not apply the static IP. See rollback script." >&2; exit 1; }
curl -sf -o /dev/null http://10.0.0.1/ || { echo "FAIL: http://10.0.0.1/ did not respond even though pb-ap holds 10.0.0.1 - investigate (nginx? firewall?) before telling the operator to test. See rollback script." >&2; exit 1; }

echo
echo "Migration steps complete. wlan0 has been left DOWN and idle (not"
echo "repurposed - confirmed live that stopping its hostapd binding takes"
echo "it fully down, not merely idle-while-up as originally assumed - see"
echo "docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md 'Radio role model' for"
echo "future onboard-radio use)."
echo
echo "NEXT: hand off to the Operator test steps in"
echo "docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md 'Migration plan' - this"
echo "script does not and cannot confirm a real client's experience."
echo "If anything looks wrong, run tools/rollback_visitor_ap_to_onboard.sh"
echo "immediately - it is designed to be simple enough to run over SSH."
