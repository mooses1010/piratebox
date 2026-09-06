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
# adjtime state and, if missing, one package; does not touch the OLED,
# hostapd/dnsmasq/nginx/php-fpm, or any other PirateBox service.
#
# WHAT THIS DOES AND WHY (confirmed live before writing this script -
# see docs/RTC-TIME-READINESS-DESIGN.md's update for the full
# investigation):
#
# 0. Ensures `hwclock` actually exists before relying on it anywhere
#    below. **Found live during this round's first real run:** on this
#    OS (Debian 13 "trixie"), `hwclock` is no longer part of the base
#    `util-linux` package - Debian split it into `util-linux-extra`
#    (confirmed via `dpkg -S`/`apt-cache show` before writing this fix;
#    `apt-get install --dry-run` shows it as the one clean new package,
#    no removals, no other upgrades). A minimal Raspberry Pi OS image
#    does not carry it. Installed only if missing, so a system that
#    already has it (or gets it from some other package in the future)
#    never re-triggers this.
# 1. Adds `dtoverlay=i2c-rtc,ds3231` to /boot/firmware/config.txt (same
#    file already carrying `dtparam=i2c_arm=on` from the OLED bring-up -
#    this is one more line in it, not a new mechanism). This is the
#    complete, standard, official way to attach a DS3231 on Raspberry
#    Pi OS - the overlay file already ships in this OS image
#    (/boot/firmware/overlays/i2c-rtc.dtbo), so no package install is
#    needed for this part.
# 2. Applies the overlay LIVE via the `dtoverlay` command, so this
#    script can verify real hardware behavior in one run without
#    requiring a reboot. The config.txt line makes it persist across
#    every future boot too.
# 3. Once /dev/rtc0 exists, NOTHING ELSE is required for this Pi to use
#    it automatically at every future boot: the running kernel is built
#    with CONFIG_RTC_HCTOSYS=y / CONFIG_RTC_HCTOSYS_DEVICE="rtc0"
#    (confirmed from /boot/config-$(uname -r) before writing this
#    script) - the kernel itself reads rtc0 and sets the system clock
#    from it. No udev rule, no fake-hwclock, no extra systemd unit.
#    fake-hwclock is confirmed NOT installed on this Pi, so there is no
#    conflicting mechanism to remove either.
#
# CLOCK-SAFETY HARDENING (added after this round's first real run):
# CONFIG_RTC_HCTOSYS does not wait for a reboot - it fires the instant
# the named RTC class device (rtc0) is registered, which the live
# `dtoverlay` apply in step 2 triggers immediately. Confirmed live: a
# fresh, never-set, battery-less DS3231 read back ~2000-01-01 the
# moment its driver bound - meaning the live-apply step, left
# unguarded, silently steps a known-good NTP-synchronized system clock
# backward by roughly 26 years, right before the very commands (step 5)
# that would otherwise have written a *correct* time into the chip.
# `resync_and_verify_ntp_time()` below forces a fresh NTP resync and
# waits for `timedatectl` to confirm it (never trusts a merely-cached
# "already synchronized" flag, since that flag reflects timesyncd's own
# last poll, not whether something else - here, the kernel - has since
# stepped the clock out from under it). It is called once before the
# overlay is touched (recovers from this exact scenario if a previous
# run already got this far and left the clock wrong) and once more
# right after the overlay/live-apply step (undoes the hctosys clobber
# from *this* run), before anything reads system time as ground truth
# or writes it into the RTC.
#
# WHAT THIS DELIBERATELY DOES NOT DO:
# - Does not touch the AT24C32 EEPROM at 0x57. It needs no kernel driver
#   or config for the RTC to function and is out of scope for this
#   round (no PirateBox feature currently uses it).
# - Does not install any package beyond the one confirmed-missing
#   `hwclock` dependency above - the overlay file and i2c-tools both
#   already ship on this OS image.
# - Does not assume a battery is installed. This board's coin cell is
#   not yet fitted (charging circuit + non-rechargeable CR2032
#   supplied, deliberately not inserted) - see the report this script's
#   output feeds into. Everything below works from Pi power alone,
#   which is genuinely how the RTC is being validated right now. (This
#   also means the same ~2000-01-01 hctosys risk this script guards
#   against during commissioning will recur at every future boot until
#   a battery is fitted - see docs/RTC-TIME-READINESS-DESIGN.md §6/§7
#   for that honestly-documented, accepted limitation; not solved by
#   this script, which only runs during commissioning, not at boot.)

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "This must be run as root (sudo tools/configure_rtc_ds3231.sh)." >&2
    exit 1
fi

CONFIG=/boot/firmware/config.txt
OVERLAY_LINE="dtoverlay=i2c-rtc,ds3231"

# --- helper: make sure the resulting clock is real, fresh NTP time,
# never a value some other mechanism (e.g. RTC_HCTOSYS reading an
# unset, battery-less RTC) may have just stepped it to. Always forces a
# fresh resync rather than trusting a cached "synchronized" flag, since
# that flag only reflects timesyncd's own last successful poll - it has
# no way to know the kernel silently overwrote the clock afterward. ---
resync_and_verify_ntp_time() {
    echo "Forcing a fresh NTP resync before trusting the system clock..."
    systemctl restart systemd-timesyncd
    tries=0
    while [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" != "yes" ]; do
        tries=$((tries + 1))
        if [ "$tries" -gt 15 ]; then
            echo "System clock could not be confirmed NTP-synchronized after a fresh resync attempt (${tries}s) - refusing to proceed." >&2
            echo "No RTC battery is installed yet, so there is no other trustworthy time source on this Pi right now - fix network/NTP reachability and re-run." >&2
            exit 1
        fi
        sleep 1
    done
    echo "System clock confirmed NTP-synchronized: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
}

echo "=== Step 0: ensure hwclock is actually available ==="
if command -v hwclock >/dev/null 2>&1; then
    echo "hwclock already present ($(command -v hwclock)) - nothing to install."
else
    echo "hwclock not found - this OS (Debian 13/trixie) ships it in the"
    echo "separate util-linux-extra package, not the base util-linux package."
    apt-get update
    apt-get install -y util-linux-extra
    if ! command -v hwclock >/dev/null 2>&1; then
        echo "hwclock still not found after installing util-linux-extra - aborting." >&2
        exit 1
    fi
    echo "Installed util-linux-extra - hwclock now at $(command -v hwclock)."
fi

echo
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
# Recover the clock FIRST, in case a previous run already got this far
# and left the system clock stepped back by the RTC's unset value.
resync_and_verify_ntp_time
if [ -e /dev/rtc0 ]; then
    echo "/dev/rtc0 already exists - overlay already active from a previous run/boot."
else
    dtoverlay i2c-rtc,ds3231
    sleep 1
fi
# The overlay/live-apply above (or a previous run's apply, in the
# already-active branch) is exactly what triggers the kernel's
# CONFIG_RTC_HCTOSYS sync from the RTC's own (currently unset) value -
# undo/verify that now, before anything below trusts system time.
resync_and_verify_ntp_time

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
echo "survive a real power-off until a battery is fitted, and the same"
echo "unset-clock-at-bind hazard this script just guarded against will"
echo "recur at every future boot until then (see docs/RTC-TIME-"
echo "READINESS-DESIGN.md for the accepted limitation and why)."
