#!/bin/bash
#
# READ-ONLY diagnostic for the DS3231 RTC. Captures evidence about its
# current state and this boot's kernel/driver history WITHOUT writing
# anything to the RTC, the system clock, or any config file. Run this
# BEFORE any recommissioning attempt whenever RTC behavior looks wrong
# (e.g. after a power-loss validation test), so evidence isn't
# overwritten before it's been reviewed.
#
# Run as root (needs /dev/rtc0 access):
#
#   sudo tools/diagnose_rtc_ds3231.sh
#
# WHY THIS EXISTS (2026-09-07): the first genuine total-power-loss
# validation test failed - after a real power-off with Ethernet
# disconnected, the Pi booted with the system clock stepped to
# ~2000-01-01, meaning the DS3231 did not retain time as expected from
# its CR2032. Diagnosing that properly requires reading the chip's
# current raw state and its boot-time kernel log BEFORE writing a
# fresh time into it (tools/configure_rtc_ds3231.sh, deliberately not
# invoked by this script) overwrites the very evidence being
# inspected. See docs/RTC-TIME-READINESS-DESIGN.md §9 for the full
# investigation this script's output feeds into.
#
# Every check below is independent and non-fatal (`|| true`) - one
# missing/unsupported piece of evidence must never stop the rest from
# being collected.

set -uo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This must be run as root (sudo tools/diagnose_rtc_ds3231.sh)." >&2
    exit 1
fi

echo "=== System time (NTP-corrected already, if network is up) ==="
date -u
timedatectl status
echo

echo "=== Direct RTC read - ground truth, independent of system clock ==="
hwclock -f /dev/rtc0 -r || true
echo

echo "=== Oscillator-stop / voltage-low flag ==="
hwclock -f /dev/rtc0 --vl-read || true
echo

echo "=== Boot-time RTC/ds1307/ds3231 kernel log lines (this boot only) ==="
dmesg -T | grep -iE 'rtc|ds1307|ds3231' || echo "(no matching dmesg lines found)"
echo

echo "=== Overlay/boot configuration ==="
grep -n 'i2c' /boot/firmware/config.txt || true
echo

echo "=== RTC device node ==="
ls -la /dev/rtc* 2>&1
echo

echo "=== I2C bus - confirms the OLED is unaffected and where the RTC sits ==="
i2cdetect -y 1 || true
echo

echo "=== OLED service ==="
systemctl is-active piratebox-oled.service 2>&1 || true
echo

echo "=== Uptime - is this the same boot as the event being diagnosed? ==="
uptime -s
uptime
echo

echo "This command only READ state above - nothing was written to the"
echo "RTC, the system clock, or any config file."
