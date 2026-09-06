#!/usr/bin/env python3
"""
Regression tests for the DS3231 hardware RTC integration
(2026-09-06, docs/RTC-TIME-READINESS-DESIGN.md's Stage 28 update): the
DS3231 (0x68) + AT24C32 EEPROM (0x57) board was wired onto the same
I2C1 bus as the existing SSD1306 OLED (0x3c) and confirmed present via
i2cdetect. tools/configure_rtc_ds3231.sh is the one-command operator
gate that adds the `dtoverlay=i2c-rtc,ds3231` line to
/boot/firmware/config.txt, applies it live, and verifies the resulting
hwclock/timedatectl behavior.

These are static content/text assertions against the repo's own
tracked script - there is no live /boot/firmware/config.txt or root
access in this test environment (see tools/test_openwebrx_bandplan_deploy.py
and tools/test_hostapd_recovery_config.py for the same style/rationale).
The goal is to catch the specific mistakes that would silently misfire
against a real Pi without any install-time error:

  - the script must be idempotent (checking for the exact line before
    adding it) - re-running it (this project's own stated discipline:
    "preview before applying... verify live after") must never append
    the overlay line twice, which would be harmless to the overlay
    itself but would be a sloppy, ever-growing config.txt;
  - it must back up config.txt before editing it, matching the same
    pattern already used for the OLED's own i2c_arm=on change
    (docs/HARDWARE-INTEGRATION-DESIGN.md's "config.txt.pre-i2c-bak");
  - it must require root rather than silently no-op or partially apply;
  - it must not touch any other PirateBox service (hostapd, dnsmasq,
    nginx, php-fpm, the OLED daemon) - this is a narrow, single-purpose
    hardware config change, not a broad change;
  - it must not install any package OTHER than the one confirmed-
    missing `hwclock` dependency (Debian 13/trixie split `hwclock` out
    of the base `util-linux` package into `util-linux-extra` - found
    live when this script's first real run failed with `hwclock:
    command not found`) - the overlay file and i2c-tools both already
    ship on this OS image and need no install;
  - that one install must be gated behind an actual `command -v
    hwclock` check, never unconditional - a system that already has it
    must never re-trigger a network apt operation on every run;
  - it must never claim or assume a battery is installed, and must not
    instruct the operator to insert one - this board's coin cell is
    deliberately not fitted yet (see the script's own header);
  - it must write time to the RTC in UTC explicitly (`--utc`), matching
    this Pi's existing `RTC in local TZ: no` convention rather than
    leaving hwclock to guess;
  - it must force and verify a fresh NTP resync both before and after
    the live overlay apply - found live during this round's first real
    run: `CONFIG_RTC_HCTOSYS` fires the instant `/dev/rtc0` registers,
    not just at boot, so an unguarded live-apply silently steps a
    known-good NTP-synchronized system clock back to the unset RTC's
    ~2000-01-01 default. The check must force a fresh resync
    (`systemctl restart systemd-timesyncd`) rather than trust a cached
    "already synchronized" flag, since that flag can't know the kernel
    stepped the clock afterward.
"""
import re
import stat
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "configure_rtc_ds3231.sh"


class TestScriptShapeAndSafety(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), f"missing {SCRIPT}")
        self.text = SCRIPT.read_text()
        # Executable lines only - the header comments deliberately
        # explain what is OUT of scope (mentioning hostapd/0x57 by name
        # to say "not touched"), which would otherwise false-positive
        # a naive substring check against the whole file.
        self.code_only = "\n".join(
            line for line in self.text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )

    def test_executable(self):
        mode = SCRIPT.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR, f"{SCRIPT} is not executable")

    def test_requires_root(self):
        self.assertIn('id -u', self.text)
        self.assertIn('exit 1', self.text)

    def test_uses_set_euo_pipefail(self):
        self.assertIn('set -euo pipefail', self.text)

    def test_idempotent_overlay_line_check(self):
        # Must check for the exact line before adding it, not just
        # grep -q (which would also match a commented-out or
        # differently-parameterized line and skip a real fix).
        self.assertIn('grep -qxF "$OVERLAY_LINE"', self.text)

    def test_correct_overlay_line_and_target_file(self):
        self.assertIn('OVERLAY_LINE="dtoverlay=i2c-rtc,ds3231"', self.text)
        self.assertIn('CONFIG=/boot/firmware/config.txt', self.text)

    def test_backs_up_config_before_editing(self):
        match = re.search(r"cp \"\$CONFIG\" \"(\$BACKUP)\"", self.text)
        self.assertIsNotNone(match, "script does not back up config.txt before editing it")
        self.assertIn('.pre-rtc-bak.', self.text)

    def test_hwclock_writes_in_utc(self):
        self.assertIn('--systohc --utc', self.text)

    def test_installs_exactly_the_confirmed_missing_hwclock_package(self):
        self.assertIn(
            'apt-get install -y util-linux-extra',
            self.code_only,
            "script must install util-linux-extra - Debian 13/trixie's "
            "actual home for hwclock, confirmed live via apt-cache/dpkg "
            "before this fix, not guessed",
        )
        # No OTHER package install anywhere - this fix is scoped to the
        # one confirmed-missing dependency, not a general apt-get spree.
        install_lines = [
            line for line in self.code_only.splitlines()
            if re.search(r'\b(apt-get install|apt install|pip install)\b', line)
        ]
        self.assertEqual(
            len(install_lines), 1,
            f"expected exactly one package-install line, found {install_lines!r}",
        )

    def test_hwclock_install_is_gated_not_unconditional(self):
        # Must only install when hwclock is actually missing - a system
        # that already has it must never trigger a network apt
        # operation on every run.
        match = re.search(
            r'if command -v hwclock.*?\n(.*?)\nfi',
            self.code_only,
            re.DOTALL,
        )
        self.assertIsNotNone(
            match, "hwclock presence check (`command -v hwclock`) not found"
        )
        self.assertIn('apt-get install -y util-linux-extra', match.group(0))

    def test_hwclock_install_updates_package_lists_first(self):
        # A genuinely fresh OS image may have empty/stale apt lists -
        # `apt-get update` must run before the install, not be assumed
        # already done, for this to be reproducible on a fresh install.
        update_idx = self.code_only.find('apt-get update')
        install_idx = self.code_only.find('apt-get install -y util-linux-extra')
        self.assertNotEqual(update_idx, -1, "script never runs apt-get update")
        self.assertLess(
            update_idx, install_idx,
            "apt-get update must run before installing util-linux-extra",
        )

    def test_verifies_hwclock_present_after_attempting_install(self):
        # Must not blindly assume the install worked - confirm the
        # command actually exists afterward and abort loudly if not.
        self.assertIn('command -v hwclock', self.code_only)
        self.assertIn('exit 1', self.code_only)

    def test_forces_and_verifies_fresh_ntp_resync_around_live_apply(self):
        # The core clock-safety fix: CONFIG_RTC_HCTOSYS fires the
        # instant /dev/rtc0 registers (not just at boot), so the live
        # overlay apply must be bracketed by a forced, VERIFIED resync -
        # never a cached "already synchronized" flag, since that flag
        # can't know the kernel stepped the clock out from under it.
        self.assertIn('systemctl restart systemd-timesyncd', self.code_only)
        self.assertIn('NTPSynchronized', self.code_only)
        # Called at least twice: once to recover from any clobber left
        # by a previous run, once more right after this run's own
        # live-apply, before anything trusts or writes system time.
        call_count = self.code_only.count('resync_and_verify_ntp_time')
        # Defined once, called at least twice - 3+ total occurrences.
        self.assertGreaterEqual(
            call_count, 3,
            "resync_and_verify_ntp_time must be defined once and called "
            "at least twice (before and after the live overlay apply)",
        )

    def test_ntp_resync_aborts_rather_than_trusts_an_unverified_clock(self):
        # If a fresh resync can't be confirmed, the script must refuse
        # to proceed rather than write a possibly-wrong time into the
        # RTC or otherwise trust the clock.
        match = re.search(
            r'resync_and_verify_ntp_time\(\)\s*\{(.*?)\n\}',
            self.code_only,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "resync_and_verify_ntp_time function not found")
        body = match.group(1)
        self.assertIn('exit 1', body)

    def test_does_not_touch_unrelated_services(self):
        for forbidden in ("hostapd", "dnsmasq", "nginx", "php-fpm", "piratebox-gpio"):
            self.assertNotIn(
                forbidden,
                self.code_only,
                f"script acts on unrelated service {forbidden!r} - this "
                "change must stay narrowly scoped to the RTC",
            )

    def test_never_assumes_or_instructs_battery_installation(self):
        lowered = self.text.lower()
        for forbidden in ("insert the battery", "insert a battery", "install the battery", "install the coin cell"):
            self.assertNotIn(
                forbidden,
                lowered,
                "script must not instruct inserting a battery - none is "
                "fitted yet by design (non-rechargeable CR2032, "
                "rechargeable-only charging circuit on this board)",
            )
        # Must actually say something explicit about the missing battery
        # rather than staying silent about the caveat.
        self.assertIn("no coin cell is installed", lowered)

    def test_eeprom_left_unconfigured(self):
        # The AT24C32 at 0x57 needs no driver/config for RTC timekeeping
        # and is explicitly out of scope this round - the script must
        # not bind or otherwise configure it (its address may still be
        # named in an explanatory comment saying exactly that).
        self.assertNotIn("0x57", self.code_only)
        self.assertNotIn("at24", self.code_only.lower())

    def test_includes_oled_regression_check(self):
        # This is a second device on the same bus the OLED already
        # depends on - the script must verify the OLED path is still
        # healthy, not just assume it.
        self.assertIn("i2cdetect -y 1", self.text)
        self.assertIn("piratebox-oled.service", self.text)


if __name__ == "__main__":
    unittest.main()
