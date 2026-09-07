#!/usr/bin/env python3
"""
Regression tests for piratebox_oled_daemon.publish_sensors_export()
(2026-09-07, Environment web UI round - docs/OPERATIONAL-DECISIONS.md).

Background this guards against regressing: progression-public.json's
"hardware" key was found to be permanently empty in production, because
piratebox_status_helper.sh generates it by invoking piratebox_
progression.py as a brand-new, separate CLI process every 30s - a fresh
process whose HARDWARE_SIGNALS registry is always empty, since
registration only ever happens inside the long-running OLED daemon's
own process memory. The fix is a dedicated export
(/run/piratebox-sensors/sensors-public.json) written directly by the
daemon process that actually holds the live, rate-limited sensor
reader - these tests exercise that function in isolation, using a
temp directory in place of the real /run path (which requires root to
create at the top level).
"""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_oled_daemon as daemon


class FakeBH1750:
    def __init__(self, diag):
        self._diag = diag

    def get_diagnostics(self):
        return self._diag


class PublishSensorsExportTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_dir = daemon.SENSORS_PUBLIC_DIR
        self._orig_file = daemon.SENSORS_PUBLIC_FILE
        daemon.SENSORS_PUBLIC_DIR = self._tmpdir.name + "/sensors"
        daemon.SENSORS_PUBLIC_FILE = daemon.SENSORS_PUBLIC_DIR + "/sensors-public.json"

    def tearDown(self):
        daemon.SENSORS_PUBLIC_DIR = self._orig_dir
        daemon.SENSORS_PUBLIC_FILE = self._orig_file
        self._tmpdir.cleanup()

    def _read_export(self):
        with open(daemon.SENSORS_PUBLIC_FILE) as f:
            return json.load(f)

    def test_writes_valid_json_with_a_detected_sensor(self):
        fake = FakeBH1750({"detected": True, "lux": 12.3, "stale": False, "last_success_seconds_ago": 1.0})
        daemon.publish_sensors_export(fake, 0.0, now=1000.0)
        data = self._read_export()
        self.assertEqual(data["generated_at"], 1000)
        self.assertEqual(
            data["sensors"]["ambient_light"],
            {"detected": True, "lux": 12.3, "stale": False, "last_success_seconds_ago": 1.0},
        )

    def test_module_none_omits_the_sensor_key_entirely(self):
        # Hardware never wired/imported - the key must be ABSENT, not
        # present-with-unavailable (no permanent fake/empty card).
        daemon.publish_sensors_export(None, 0.0, now=1000.0)
        data = self._read_export()
        self.assertEqual(data["sensors"], {})
        self.assertNotIn("ambient_light", data["sensors"])

    def test_throttled_within_publish_interval(self):
        fake = FakeBH1750({"detected": True, "lux": 5.0, "stale": False, "last_success_seconds_ago": 0.1})
        last = daemon.publish_sensors_export(fake, 0.0, now=1000.0)
        self.assertEqual(last, 1000.0)
        # A second call moments later, well inside SENSORS_PUBLISH_INTERVAL_S,
        # must not touch the file again (returns the SAME last-publish time).
        before_mtime = Path(daemon.SENSORS_PUBLIC_FILE).stat().st_mtime
        last2 = daemon.publish_sensors_export(fake, last, now=1000.0 + 1.0)
        self.assertEqual(last2, last, "must not publish again inside the throttle window")
        after_mtime = Path(daemon.SENSORS_PUBLIC_FILE).stat().st_mtime
        self.assertEqual(before_mtime, after_mtime)

    def test_publishes_again_after_interval_elapses(self):
        fake = FakeBH1750({"detected": True, "lux": 5.0, "stale": False, "last_success_seconds_ago": 0.1})
        last = daemon.publish_sensors_export(fake, 0.0, now=1000.0)
        last2 = daemon.publish_sensors_export(fake, last, now=1000.0 + daemon.SENSORS_PUBLISH_INTERVAL_S + 1)
        self.assertGreater(last2, last)

    def test_a_broken_diagnostics_call_does_not_raise_and_omits_the_sensor(self):
        class BrokenBH1750:
            def get_diagnostics(self):
                raise RuntimeError("bus error")

        # Must not raise - the daemon's own caller also wraps this, but
        # the function itself should already be safe on its own.
        daemon.publish_sensors_export(BrokenBH1750(), 0.0, now=1000.0)
        data = self._read_export()
        self.assertNotIn("ambient_light", data["sensors"])

    def test_output_file_is_world_readable(self):
        import stat
        fake = FakeBH1750({"detected": True, "lux": 1.0, "stale": False, "last_success_seconds_ago": 0.1})
        daemon.publish_sensors_export(fake, 0.0, now=1000.0)
        mode = Path(daemon.SENSORS_PUBLIC_FILE).stat().st_mode
        self.assertTrue(mode & stat.S_IROTH, "sensors-public.json must be world-readable for PHP (www-data)")

    def test_creates_the_directory_if_missing(self):
        # setUp already points at a not-yet-created subdirectory -
        # every test above already proves this implicitly, but assert
        # it explicitly too since it's the one thing that would break
        # a genuinely fresh install (the tmpfiles.d rule not yet applied).
        self.assertFalse(Path(daemon.SENSORS_PUBLIC_DIR).exists())
        fake = FakeBH1750({"detected": True, "lux": 1.0, "stale": False, "last_success_seconds_ago": 0.1})
        daemon.publish_sensors_export(fake, 0.0, now=1000.0)
        self.assertTrue(Path(daemon.SENSORS_PUBLIC_DIR).is_dir())


if __name__ == "__main__":
    unittest.main()
