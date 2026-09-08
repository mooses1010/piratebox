#!/usr/bin/env python3
"""
Tests for piratebox_temp_unit.py (2026-09-08) - the Python side of the
shared C/F display-unit preference. Matches this project's existing
dependency-free tools/test_*.py convention.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_temp_unit as tu


class ConvertCTests(unittest.TestCase):
    def test_freezing_point(self):
        self.assertAlmostEqual(tu.convert_c(0.0, "F"), 32.0)

    def test_boiling_point(self):
        self.assertAlmostEqual(tu.convert_c(100.0, "F"), 212.0)

    def test_crossover_point(self):
        """-40 is the one temperature where C and F agree exactly -
        a good sanity check the formula itself is right."""
        self.assertAlmostEqual(tu.convert_c(-40.0, "F"), -40.0)

    def test_celsius_passthrough_is_unchanged(self):
        self.assertEqual(tu.convert_c(29.5, "C"), 29.5)

    def test_none_passes_through_regardless_of_unit(self):
        self.assertIsNone(tu.convert_c(None, "F"))
        self.assertIsNone(tu.convert_c(None, "C"))

    def test_unrecognized_unit_behaves_like_celsius_passthrough(self):
        self.assertEqual(tu.convert_c(29.5, "K"), 29.5)

    def test_no_double_conversion_by_construction(self):
        """Converting an ALREADY-CONVERTED Fahrenheit value again would
        be wrong - this project's own architecture never does that
        (every caller converts a freshly-read Celsius value exactly
        once), but this test documents the arithmetic reality that
        would result if it ever did, as a canary: applying convert_c
        twice must never coincidentally look correct."""
        celsius = 20.0
        once = tu.convert_c(celsius, "F")
        twice = tu.convert_c(once, "F")
        self.assertNotAlmostEqual(twice, once)
        self.assertAlmostEqual(once, 68.0)


class ReadTempUnitTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._path = self._tmpdir.name + "/temp-unit.json"

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_file_defaults_to_celsius(self):
        self.assertEqual(tu.read_temp_unit(self._path), "C")

    def test_valid_fahrenheit_is_read(self):
        with open(self._path, "w") as f:
            json.dump({"unit": "F"}, f)
        self.assertEqual(tu.read_temp_unit(self._path), "F")

    def test_valid_celsius_is_read(self):
        with open(self._path, "w") as f:
            json.dump({"unit": "C"}, f)
        self.assertEqual(tu.read_temp_unit(self._path), "C")

    def test_corrupt_json_defaults_to_celsius(self):
        with open(self._path, "w") as f:
            f.write("{not valid json")
        self.assertEqual(tu.read_temp_unit(self._path), "C")

    def test_unrecognized_unit_value_defaults_to_celsius(self):
        with open(self._path, "w") as f:
            json.dump({"unit": "kelvin"}, f)
        self.assertEqual(tu.read_temp_unit(self._path), "C")

    def test_wrong_shape_defaults_to_celsius(self):
        with open(self._path, "w") as f:
            json.dump(["not", "a", "dict"], f)
        self.assertEqual(tu.read_temp_unit(self._path), "C")

    def test_default_module_path_constant_is_the_shared_php_file(self):
        """Documents the cross-process contract: this must be the
        exact same path var/www/html/includes/temp_unit.php writes."""
        self.assertEqual(tu.TEMP_UNIT_FILE, "/var/www/html/data/temp-unit.json")


if __name__ == "__main__":
    unittest.main()
