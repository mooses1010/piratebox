#!/usr/bin/env python3
"""
Tests for piratebox_esp32_bh1750.py - the drop-in replacement
registered after the BH1750 ambient light sensor's physical migration
from the Pi's own I2C bus to the ESP32-S3 supervisor (2026-09-07,
docs/OPERATIONAL-DECISIONS.md). Verifies the two public functions have
EXACTLY the same contract/shape as the retired piratebox_bh1750.py
registration (piratebox_oled_daemon.py's publish_sensors_export() and
build_glance_metrics() depend on this without knowing which module is
actually behind bh1750_module).

No real serial/I2C hardware is touched - piratebox_esp32_client.EXPORT_FILE
is redirected to a temp file, exactly like tools/test_esp32_supervisor_
protocol.py's ClientReaderTests.
"""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_esp32_client as client
import piratebox_esp32_bh1750 as bh


class Esp32Bh1750MigrationTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_file = client.EXPORT_FILE
        client.EXPORT_FILE = self._tmpdir.name + "/esp32-public.json"

    def tearDown(self):
        client.EXPORT_FILE = self._orig_file
        self._tmpdir.cleanup()

    def _write(self, data):
        with open(client.EXPORT_FILE, "w") as f:
            json.dump(data, f)

    def test_no_export_at_all_degrades_cleanly(self):
        self.assertIsNone(bh.read_ambient_lux())
        diag = bh.get_diagnostics()
        self.assertFalse(diag["detected"])
        self.assertIsNone(diag["lux"])
        self.assertTrue(diag["stale"])

    def test_real_reading_flows_through(self):
        self._write({
            "generated_at": int(time.time()), "connected": True, "stale": False,
            "sensors": {"bh1750": {"ok": True, "value": 11.7, "unit": "lux"}},
        })
        self.assertEqual(bh.read_ambient_lux(), 11.7)
        diag = bh.get_diagnostics()
        self.assertTrue(diag["detected"])
        self.assertEqual(diag["lux"], 11.7)
        self.assertFalse(diag["stale"])

    def test_bh1750_capability_absent_reports_not_detected(self):
        # Old firmware (pre-BH1750 flash) or a genuinely never-wired
        # board - "bh1750" key simply isn't in sensors at all.
        self._write({
            "generated_at": int(time.time()), "connected": True, "stale": False,
            "sensors": {"temp_internal": {"ok": True, "value": 30.0}},
        })
        self.assertIsNone(bh.read_ambient_lux())
        self.assertFalse(bh.get_diagnostics()["detected"])

    def test_bh1750_sensor_reporting_failure_returns_none(self):
        self._write({
            "generated_at": int(time.time()), "connected": True, "stale": False,
            "sensors": {"bh1750": {"ok": False, "err": "read_failed"}},
        })
        self.assertIsNone(bh.read_ambient_lux())

    def test_supervisor_disconnected_returns_none_not_fabricated(self):
        self._write({
            "generated_at": int(time.time()), "connected": False, "stale": True,
            "sensors": {},
        })
        self.assertIsNone(bh.read_ambient_lux())
        diag = bh.get_diagnostics()
        self.assertFalse(diag["detected"])
        self.assertIn("not connected", diag["last_error"])

    def test_stale_link_does_not_report_a_reading_as_current(self):
        self._write({
            "generated_at": int(time.time()), "connected": True, "stale": True,
            "sensors": {"bh1750": {"ok": True, "value": 5.0}},
        })
        self.assertIsNone(bh.read_ambient_lux())

    def test_get_diagnostics_shape_matches_retired_module(self):
        # Exact key set piratebox_bh1750.get_diagnostics() returns -
        # publish_sensors_export()/build_glance_metrics() index into
        # these by name and must never KeyError.
        self._write({
            "generated_at": int(time.time()), "connected": True, "stale": False,
            "sensors": {"bh1750": {"ok": True, "value": 9.9}},
        })
        diag = bh.get_diagnostics()
        expected_keys = {"i2c_bus", "address", "detected", "lux",
                          "last_success_seconds_ago", "stale", "last_error"}
        self.assertEqual(set(diag.keys()), expected_keys)


if __name__ == "__main__":
    unittest.main()
