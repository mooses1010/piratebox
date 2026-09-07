#!/usr/bin/env python3
"""
Regression tests for tools/deploy_environment_sensors.sh (2026-09-07,
Environment web UI round). Static content assertions against the
repo's own tracked script - there is no live systemd/php-fpm/root
access in this test environment (same style as
tools/test_rtc_ds3231_config.py and tools/test_openwebrx_bandplan_deploy.py).
"""
import re
import stat
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "tools" / "deploy_environment_sensors.sh"
SERVICE_UNIT = REPO_ROOT / "etc" / "systemd" / "system" / "piratebox-oled.service"
PHP_INI = REPO_ROOT / "etc" / "php" / "8.4" / "fpm" / "php.ini"


class TestDeployScript(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), f"missing {SCRIPT}")
        self.text = SCRIPT.read_text()
        self.code_only = "\n".join(
            line for line in self.text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )

    def test_executable(self):
        mode = SCRIPT.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)

    def test_requires_root(self):
        self.assertIn("id -u", self.text)
        self.assertIn("exit 1", self.text)

    def test_uses_set_euo_pipefail(self):
        self.assertIn("set -euo pipefail", self.text)

    def test_deploys_the_systemd_unit_and_reloads(self):
        self.assertIn("etc/systemd/system/piratebox-oled.service", self.code_only)
        self.assertIn("/etc/systemd/system/piratebox-oled.service", self.code_only)
        self.assertIn("systemctl daemon-reload", self.code_only)

    def test_open_basedir_patch_is_idempotent(self):
        # Must check for the exact addition before making it - a
        # naive unconditional sed would append it again on every run.
        self.assertIn("grep -q '/run/piratebox-sensors/sensors-public.json'", self.code_only)
        self.assertIn("sed -i", self.code_only)

    def test_delegates_py_file_deploy_to_update_progression_sh(self):
        # Must not duplicate that script's copy/restart logic - the
        # two would drift out of sync over time.
        self.assertIn("tools/update_progression.sh", self.code_only)
        # And must not itself re-copy the .py files or re-restart
        # piratebox-oled a second, redundant time.
        self.assertNotIn("piratebox_oled_daemon.py\" /usr/local/bin", self.code_only)

    def test_restarts_only_the_two_expected_services(self):
        self.assertIn("systemctl restart php8.4-fpm", self.code_only)
        for forbidden in ("hostapd", "dnsmasq", " nginx", "piratebox-gpio.service", "piratebox-button"):
            self.assertNotIn(forbidden, self.code_only)

    def test_includes_bus_regression_check(self):
        self.assertIn("i2cdetect -y 1", self.text)

    def test_verifies_the_export_actually_appears(self):
        self.assertIn("sensors-public.json", self.code_only)
        self.assertIn("sleep 1", self.code_only)  # the wait-loop, not a blind fixed sleep


class TestSystemdUnitAndPhpIniAreConsistentWithTheScript(unittest.TestCase):
    def test_service_unit_declares_the_runtime_directory(self):
        text = SERVICE_UNIT.read_text()
        self.assertIn("RuntimeDirectory=piratebox-sensors", text)

    def test_service_unit_keeps_the_pre_existing_readwrite_path(self):
        # This round must not regress Progression's own durable-state
        # write access - added in an earlier round, unrelated to this one.
        text = SERVICE_UNIT.read_text()
        self.assertIn("ReadWritePaths=/var/lib/piratebox-oled", text)

    def test_php_ini_open_basedir_includes_the_new_export_and_keeps_the_old_ones(self):
        text = PHP_INI.read_text()
        match = re.search(r"^open_basedir = (.+)$", text, re.MULTILINE)
        self.assertIsNotNone(match, "open_basedir line not found")
        entries = match.group(1).split(":")
        self.assertIn("/run/piratebox-sensors/sensors-public.json", entries)
        self.assertIn("/run/piratebox/status.json", entries)
        self.assertIn("/run/piratebox/progression-public.json", entries)


if __name__ == "__main__":
    unittest.main()
