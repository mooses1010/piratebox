#!/usr/bin/env python3
"""
Regression tests for tools/diagnose_rtc_ds3231.sh
(2026-09-07, docs/RTC-TIME-READINESS-DESIGN.md §9): the first genuine
total-power-loss validation test failed - the DS3231 came back reading
its factory power-on default (~2000-01-01) instead of advancing time
from its CR2032, per the operator's report and confirmed live via
dmesg. Diagnosing that root cause requires reading the chip's current
raw state before anything overwrites it, so this script exists as a
strictly READ-ONLY counterpart to tools/configure_rtc_ds3231.sh -
evidence-preserving by construction, not just by convention.

These are static content/text assertions against the repo's own
tracked script - there is no live /dev/rtc0 or root access in this
test environment (same style as tools/test_rtc_ds3231_config.py). The
goal is to catch the one mistake that would matter most here: this
script accidentally gaining a write path and destroying the evidence
it exists to preserve.
"""
import re
import stat
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "diagnose_rtc_ds3231.sh"

# Any of these appearing as an actual hwclock function flag (not just
# mentioned in a comment) would mean this "read-only" script can write
# to the RTC, the exact thing it must never do.
WRITE_FUNCTION_FLAGS = ("--systohc", "-w", "--set ", "--vl-clear", "--hctosys", "--adjust")


class TestDiagnosticScriptIsReadOnly(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), f"missing {SCRIPT}")
        self.text = SCRIPT.read_text()
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

    def test_never_writes_to_the_rtc(self):
        for flag in WRITE_FUNCTION_FLAGS:
            self.assertNotIn(
                flag, self.code_only,
                f"diagnostic script must never write to the RTC "
                f"({flag!r} found) - it exists to preserve evidence, "
                "not overwrite it",
            )

    def test_never_edits_config_txt_or_any_other_file(self):
        for forbidden in ("sed -i", "cp ", ">>", "> /boot", "> /etc"):
            self.assertNotIn(
                forbidden, self.code_only,
                f"diagnostic script must not modify files ({forbidden!r} found)",
            )

    def test_never_restarts_or_touches_unrelated_services(self):
        for forbidden in ("systemctl restart", "systemctl stop", "hostapd", "dnsmasq", "nginx", "php-fpm"):
            self.assertNotIn(forbidden, self.code_only)

    def test_never_triggers_the_physical_power_off_itself(self):
        command_lines = [
            line for line in self.code_only.splitlines()
            if not line.strip().startswith("echo")
        ]
        command_text = "\n".join(command_lines)
        for forbidden in ("reboot", "poweroff", "shutdown "):
            self.assertNotIn(forbidden, command_text)

    def test_reads_raw_rtc_time_and_vl_flag(self):
        self.assertIn("hwclock -f /dev/rtc0 -r", self.code_only)
        self.assertIn("--vl-read", self.code_only)

    def test_reads_boot_time_dmesg_evidence(self):
        self.assertIn("dmesg", self.code_only)
        match = re.search(r"dmesg[^\n]*grep[^\n]*", self.code_only)
        self.assertIsNotNone(match, "no dmesg | grep line found")
        self.assertRegex(match.group(0), r"rtc", re.IGNORECASE)

    def test_includes_oled_regression_check(self):
        self.assertIn("i2cdetect -y 1", self.text)
        self.assertIn("piratebox-oled.service", self.text)

    def test_every_check_is_non_fatal(self):
        # No single missing/unsupported piece of evidence should ever
        # stop the rest of the diagnostic from running.
        self.assertNotIn("set -e", self.text)
        # The one legitimate exit 1 is the root-check gate itself.
        exit_count = self.code_only.count("exit 1")
        self.assertEqual(
            exit_count, 1,
            "expected exactly one 'exit 1' (the root-required gate) - "
            "any other exit would abort evidence collection partway through",
        )


if __name__ == "__main__":
    unittest.main()
