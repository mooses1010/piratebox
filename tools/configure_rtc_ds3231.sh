#!/bin/bash
#
# Configures the DS3231 RTC (wired on the same I2C1 bus as the SSD1306
# OLED - see docs/HARDWARE-INTEGRATION-DESIGN.md) as this Pi's hardware
# clock, verifies it end-to-end, and reports the result. Run as root:
#
#   sudo tools/configure_rtc_ds3231.sh
#
# PRODUCTION HARDWARE (2026-09-07): the module in service has been
# modified for safe non-rechargeable battery use - R4 (200 ohm, marked
# "201"), which fed the module's VCC-to-battery charging path, has been
# removed, and a standard CR2032 is installed. Confirmed by direct
# measurement before/after the modification: the empty battery holder
# read ~3.14-3.18V while charging (R4 present, powered from the Pi's
# 3.3V rail) and only ~0.22V after R4's removal - the charging path is
# genuinely broken, so a non-rechargeable cell is safe here. See
# docs/RTC-TIME-READINESS-DESIGN.md §8 for the full hardware record.
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
# OSCILLATOR-STOP / VOLTAGE-LOW HANDLING (added for the battery-backed
# module): the DS3231 latches a flag (its OSF bit, surfaced generically
# by hwclock as "voltage low") whenever it can't vouch for its own
# stored time - which is unconditionally true the first time a chip is
# ever powered/backed at all. hwclock(8) documents `--vl-clear` as
# "necessary for some RTC devices after a battery replacement" - this
# commissioning is exactly that case (first battery this chip has ever
# had). Read before AND after the time write, purely diagnostic/
# non-fatal either way (`|| true` - not all RTC/driver combinations
# support it, per hwclock's own man page, and its absence must never
# block real commissioning), then explicitly cleared once a known-good
# NTP-verified time has actually been written - never before, since the
# flag existing is exactly correct until that point.
#
# WHAT THIS DELIBERATELY DOES NOT DO:
# - Does not touch the AT24C32 EEPROM at 0x57. It needs no kernel driver
#   or config for the RTC to function and is out of scope for this
#   round (no PirateBox feature currently uses it).
# - Does not install any package beyond the one confirmed-missing
#   `hwclock` dependency above - the overlay file and i2c-tools both
#   already ship on this OS image.
# - Does not touch or rely on R4/the charging circuit itself - that is
#   a one-time physical hardware modification already done to the
#   module before it was wired in, not something software configures.

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
echo "Relevant dmesg lines (wall-clock timestamps, for cross-checking"
echo "against 'uptime -s' - see docs/RTC-TIME-READINESS-DESIGN.md §11):"
dmesg -T | grep -iE 'rtc|ds3231|ds1307' | tail -20
echo
echo "Boot time (compare against the dmesg timestamps above - a boot-time"
echo "RTC event only means something about THIS commissioning run if it"
echo "happened on or after this boot):"
uptime -s

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
echo "=== Step 5: oscillator-stop / voltage-low flag, BEFORE clearing it ==="
echo "(expected to report a stop/low condition - this chip has never had a"
echo "trustworthy time source before now; non-fatal if unsupported)"
hwclock -f /dev/rtc0 --vl-read || true

echo
echo "=== Step 6: write the current (NTP-correct) system time to the RTC ==="
hwclock -f /dev/rtc0 --systohc --utc
echo "Read back:"
hwclock -f /dev/rtc0 -r

echo
echo "=== Step 7: clear the oscillator-stop / voltage-low flag ==="
echo "(now that a known-good time has actually been written - not before)"
hwclock -f /dev/rtc0 --vl-clear || true
echo "Confirming it cleared:"
hwclock -f /dev/rtc0 --vl-read || true

echo
echo "=== Step 8: confirm the OS now sees a real hardware clock ==="
timedatectl status

echo
echo "=== Step 9: regression check - OLED bus neighbor unaffected ==="
i2cdetect -y 1
systemctl is-active piratebox-oled.service 2>&1 || true

echo
echo "Done. dtoverlay=i2c-rtc,ds3231 is persisted in $CONFIG and active now,"
echo "with a known-good time written to the battery-backed RTC. This is"
echo "ready for the real validation: a genuine full power-off test to"
echo "confirm the CR2032 actually holds time with no Pi power at all -"
echo "see docs/RTC-TIME-READINESS-DESIGN.md §8 for that procedure. This"
echo "script does not perform or request that test itself."
