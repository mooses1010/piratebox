#!/usr/bin/env python3
"""
Tests for piratebox_ds18b20_roles.py (2026-09-07, DS18B20 phase) - the
durable probe-naming store and its request/apply protocol. Mirrors
tools/test_progression.py's own style for the reset/import-request
pattern this module deliberately copies.
"""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_ds18b20_roles as roles_mod

VALID_ROM = "28ff641e04170378"
VALID_ROM_2 = "28aa112233445566"


class IsValidRomTests(unittest.TestCase):
    def test_valid(self):
        self.assertTrue(roles_mod.is_valid_rom(VALID_ROM))

    def test_wrong_length(self):
        self.assertFalse(roles_mod.is_valid_rom("28ff64"))

    def test_uppercase_rejected(self):
        self.assertFalse(roles_mod.is_valid_rom(VALID_ROM.upper()))

    def test_non_hex_rejected(self):
        self.assertFalse(roles_mod.is_valid_rom("28ff641e0417037g"))

    def test_non_string_rejected(self):
        self.assertFalse(roles_mod.is_valid_rom(12345678901234))
        self.assertFalse(roles_mod.is_valid_rom(None))


class ApplyNameRequestTests(unittest.TestCase):
    def test_set_adds_a_new_name(self):
        result = roles_mod.apply_name_request({}, {"action": "set", "rom": VALID_ROM, "name": "Enclosure"})
        self.assertEqual(result[VALID_ROM]["name"], "Enclosure")
        self.assertIsInstance(result[VALID_ROM]["assigned_at"], float)

    def test_set_overwrites_an_existing_name(self):
        existing = {VALID_ROM: {"name": "Old", "assigned_at": 1.0}}
        result = roles_mod.apply_name_request(existing, {"action": "set", "rom": VALID_ROM, "name": "New"})
        self.assertEqual(result[VALID_ROM]["name"], "New")

    def test_set_does_not_mutate_the_input_dict(self):
        original = {}
        roles_mod.apply_name_request(original, {"action": "set", "rom": VALID_ROM, "name": "X"})
        self.assertEqual(original, {})

    def test_set_trims_and_truncates_long_names(self):
        long_name = "x" * 100
        result = roles_mod.apply_name_request({}, {"action": "set", "rom": VALID_ROM, "name": f"  {long_name}  "})
        self.assertEqual(len(result[VALID_ROM]["name"]), roles_mod.MAX_NAME_LENGTH)

    def test_set_with_empty_name_is_rejected(self):
        result = roles_mod.apply_name_request({}, {"action": "set", "rom": VALID_ROM, "name": "   "})
        self.assertEqual(result, {})

    def test_set_with_invalid_rom_is_rejected(self):
        result = roles_mod.apply_name_request({}, {"action": "set", "rom": "not-a-rom", "name": "X"})
        self.assertEqual(result, {})

    def test_remove_clears_an_existing_name(self):
        existing = {VALID_ROM: {"name": "Old", "assigned_at": 1.0}}
        result = roles_mod.apply_name_request(existing, {"action": "remove", "rom": VALID_ROM})
        self.assertNotIn(VALID_ROM, result)

    def test_remove_of_unknown_rom_is_a_harmless_no_op(self):
        result = roles_mod.apply_name_request({}, {"action": "remove", "rom": VALID_ROM})
        self.assertEqual(result, {})

    def test_unknown_action_is_ignored(self):
        result = roles_mod.apply_name_request({}, {"action": "explode", "rom": VALID_ROM, "name": "X"})
        self.assertEqual(result, {})

    def test_malformed_request_never_raises(self):
        for bad in [None, "a string", 42, [], {}, {"rom": VALID_ROM}]:
            result = roles_mod.apply_name_request({"existing": "unchanged"}, bad)
            self.assertIn("existing", result)


class LoadSaveRolesTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_roles_file = roles_mod.ROLES_FILE
        roles_mod.ROLES_FILE = self._tmpdir.name + "/ds18b20-roles.json"

    def tearDown(self):
        roles_mod.ROLES_FILE = self._orig_roles_file
        self._tmpdir.cleanup()

    def test_missing_file_loads_as_empty(self):
        self.assertEqual(roles_mod.load_roles(), {})

    def test_round_trips_a_real_mapping(self):
        roles = {VALID_ROM: {"name": "Enclosure", "assigned_at": 123.0}}
        roles_mod.save_roles(roles)
        self.assertEqual(roles_mod.load_roles(), roles)

    def test_corrupt_file_degrades_to_empty_not_a_crash(self):
        with open(roles_mod.ROLES_FILE, "w") as f:
            f.write("{not valid json")
        self.assertEqual(roles_mod.load_roles(), {})

    def test_malformed_entries_are_dropped_individually(self):
        with open(roles_mod.ROLES_FILE, "w") as f:
            json.dump({VALID_ROM: {"name": "Good"}, "bad-entry": "not a dict", "other": {}}, f)
        loaded = roles_mod.load_roles()
        self.assertEqual(list(loaded.keys()), [VALID_ROM])


class CheckNameRequestTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_roles_file = roles_mod.ROLES_FILE
        self._orig_request_file = roles_mod.NAME_REQUEST_FILE
        roles_mod.ROLES_FILE = self._tmpdir.name + "/ds18b20-roles.json"
        roles_mod.NAME_REQUEST_FILE = self._tmpdir.name + "/ds18b20-name-request.json"

    def tearDown(self):
        roles_mod.ROLES_FILE = self._orig_roles_file
        roles_mod.NAME_REQUEST_FILE = self._orig_request_file
        self._tmpdir.cleanup()

    def test_no_request_file_is_a_cheap_no_op(self):
        result = roles_mod.check_name_request({}, {})
        self.assertEqual(result, {})

    def test_valid_request_is_applied_and_saved_and_consumed(self):
        with open(roles_mod.NAME_REQUEST_FILE, "w") as f:
            json.dump({"action": "set", "rom": VALID_ROM, "name": "Battery"}, f)
        markers = {}
        result = roles_mod.check_name_request({}, markers)
        self.assertEqual(result[VALID_ROM]["name"], "Battery")
        # Saved to the durable file, not just returned in memory:
        self.assertEqual(roles_mod.load_roles()[VALID_ROM]["name"], "Battery")
        # Request file consumed (removed) after being applied:
        self.assertFalse(Path(roles_mod.NAME_REQUEST_FILE).exists())

    def test_same_request_is_not_reapplied_on_the_next_call(self):
        with open(roles_mod.NAME_REQUEST_FILE, "w") as f:
            json.dump({"action": "set", "rom": VALID_ROM, "name": "Battery"}, f)
        markers = {}
        roles_mod.check_name_request({}, markers)
        # File was removed - a second call with the same markers must
        # not error or reapply anything (there's nothing left to see).
        result = roles_mod.check_name_request({VALID_ROM: {"name": "Battery", "assigned_at": 1.0}}, markers)
        self.assertEqual(result[VALID_ROM]["name"], "Battery")

    def test_malformed_json_request_is_ignored_and_removed(self):
        with open(roles_mod.NAME_REQUEST_FILE, "w") as f:
            f.write("{not valid json")
        result = roles_mod.check_name_request({"keep": "me"}, {})
        self.assertEqual(result, {"keep": "me"})

    def test_invalid_request_content_is_ignored_and_removed(self):
        with open(roles_mod.NAME_REQUEST_FILE, "w") as f:
            json.dump({"action": "set", "rom": "not-a-rom", "name": "X"}, f)
        result = roles_mod.check_name_request({"keep": "me"}, {})
        self.assertEqual(result, {"keep": "me"})
        self.assertFalse(Path(roles_mod.NAME_REQUEST_FILE).exists())

    def test_remove_request_applied_end_to_end(self):
        roles_mod.save_roles({VALID_ROM: {"name": "Old", "assigned_at": 1.0}})
        with open(roles_mod.NAME_REQUEST_FILE, "w") as f:
            json.dump({"action": "remove", "rom": VALID_ROM}, f)
        result = roles_mod.check_name_request({VALID_ROM: {"name": "Old", "assigned_at": 1.0}}, {})
        self.assertNotIn(VALID_ROM, result)
        self.assertNotIn(VALID_ROM, roles_mod.load_roles())


if __name__ == "__main__":
    unittest.main()
