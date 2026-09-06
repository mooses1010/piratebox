#!/bin/bash
#
# Configures the DS3231 RTC (wired on the same I2C1 bus as the SSD1306
# OLED - see docs/HARDWARE-INTEGRATION-DESIGN.md) as this Pi's hardware
# clock, verifies it end-to-end, and reports the result. Run as root:
#
#   sudo tools/configure_rtc_ds3231.sh
#
# Idempotent - safe to re-run. Touches exactly one file
# (/boot/firmware/config.txt, backed up first) plus standard hwclock/
# adjtime state; does not touch the OLED, hostapd/dnsmasq/nginx/php-fpm,
# or any other PirateBox service.
#
# WHAT THIS DOES AND WHY (confirmed live before writing this script -
# see docs/RTC-TIME-READINESS-DESIGN.md's update for the full
# investigation):
#
# 1. Adds `dtoverlay=i2c-rtc,ds3231` to /boot/firmware/config.txt (same
#    file already carrying `dtparam=i2c_arm=on` from the OLED bring-up -
#    this is one more line in it, not a new mechanism). This is the
#    complete, standard, official way to attach a DS3231 on Raspberry
#    Pi OS - the overlay file already ships in this OS image
#    (/boot/firmware/overlays/i2c-rtc.dtbo), so no package install is
#    needed.
# 2. Applies the overlay LIVE via the `dtoverlay` command, so this
#    script can verify real hardware behavior in one run without
#    requiring a reboot. The config.txt line makes it persist across
#    every future boot too.
# 3. Once /dev/rtc0 exists, NOTHING ELSE is required for this Pi to use
#    it automatically at every future boot: the running kernel is built
#    with CONFIG_RTC_HCTOSYS=y / CONFIG_RTC_HCTOSYS_DEVICE="rtc0"
#    (confirmed from /boot/config-$(uname -r) before writing this
#    script) - the kernel itself reads rtc0 and sets the system clock
#    from it, very early in boot, before any network/NTP is even
#    possible. No udev rule, no fake-hwclock, no extra systemd unit.
#    fake-hwclock is confirmed NOT installed on this Pi, so there is no
#    conflicting mechanism to remove either.
# 4. Reads the RTC BEFORE writing anything (expected to be stale/
#    uninitialized, or to report an oscillator-stop-flag warning - a
#    fresh, never-set, battery-less DS3231 has no reason to already
#    know the correct time; a garbage/flagged read is actually positive
#    evidence this is real chip communication, not a stub), then writes
#    the current system time to it (`hwclock --systohc --utc`) and
#    reads it back to confirm the round trip works.
#
# WHAT THIS DELIBERATELY DOES NOT DO:
# - Does not touch the AT24C32 EEPROM at 0x57. It needs no kernel driver
#   or config for the RTC to function and is out of scope for this
#   round (no PirateBox feature currently uses it).
# - Does not install any package (i2c-tools and the overlay file are
#   both already present on this OS image).
# - Does not assume a battery is installed. This board's coin cell is
#   not yet fitted (charging circuit + non-rechargeable CR2032
#   supplied, deliberately not inserted) - see the report this script's
#   output feeds into. Everything below works from Pi power alone,
#   which is genuinely how the RTC is being validated right now.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This must be run as root (sudo tools/configure_rtc_ds3231.sh)." >&2
    exit 1
fi

CONFIG=/boot/firmware/config.txt
OVERLAY_LINE="dtoverlay=i2c-rtc,ds3231"

echo "=== Step 1: persist the overlay in $CONFIG ==="
if grep -qxF "$OVERLAY_LINE" "$CONFIG"; then
    echo "Already present - no edit needed."
else
    BACKUP="${CONFIG}.pre-rtc-bak.$(date +%Y%m%d%H%M%S)"
    cp "$CONFIG" "$BACKUP"
    echo "Backed up $CONFIG -> $BACKUP"
    if grep -q '^dtparam=i2c_arm=on' "$CONFIG"; then
        sed -i "/^dtparam=i2c_arm=on/a ${OVERLAY_LINE}" "$CONFIG"
    else
        printf '%s\n' "$OVERLAY_LINE" >> "$CONFIG"
    fi
    echo "Added: $OVERLAY_LINE"
fi

echo
echo "=== Step 2: apply the overlay live (no reboot required to test) ==="
if [ -e /dev/rtc0 ]; then
    echo "/dev/rtc0 already exists - overlay already active from a previous run/boot."
else
    dtoverlay i2c-rtc,ds3231
    sleep 1
fi

echo
echo "=== Step 3: confirm the device node and kernel binding ==="
ls -la /dev/rtc* 2>&1
echo
echo "Relevant dmesg lines:"
dmesg | grep -iE 'rtc|ds3231|ds1307' | tail -20

if [ ! -e /dev/rtc0 ]; then
    echo
    echo "/dev/rtc0 did not appear after a live overlay apply." >&2
    echo "The config.txt line is saved, so a normal reboot (sudo reboot)" >&2
    echo "should bring it up cleanly - this is the standard, well-documented" >&2
    echo "fallback path for i2c-rtc overlays that do not take effect live." >&2
    exit 1
fi

echo
echo "=== Step 4: read the RTC BEFORE writing anything (baseline) ==="
hwclock -f /dev/rtc0 -r || true

echo
echo "=== Step 5: write the current (NTP-correct) system time to the RTC ==="
hwclock -f /dev/rtc0 --systohc --utc
echo "Read back:"
hwclock -f /dev/rtc0 -r

echo
echo "=== Step 6: confirm the OS now sees a real hardware clock ==="
timedatectl status

echo
echo "=== Step 7: regression check - OLED bus neighbor unaffected ==="
i2cdetect -y 1
systemctl is-active piratebox-oled.service 2>&1 || true

echo
echo "Done. dtoverlay=i2c-rtc,ds3231 is persisted in $CONFIG and active now."
echo "Reminder: no coin cell is installed yet. The RTC will keep correct"
echo "time only while the Pi stays powered - it cannot be expected to"
echo "survive a real power-off until a battery is fitted."
