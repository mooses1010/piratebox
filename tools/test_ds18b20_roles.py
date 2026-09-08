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


class CommissionedRomsTests(unittest.TestCase):
    def test_only_commissioned_roms_are_returned(self):
        roles = {
            VALID_ROM: {"commissioned": True},
            VALID_ROM_2: {"commissioned": False, "name": "Has a name but not commissioned"},
        }
        self.assertEqual(roles_mod.commissioned_roms(roles), {VALID_ROM})

    def test_empty_roles_yields_empty_set(self):
        self.assertEqual(roles_mod.commissioned_roms({}), set())


class PhysicalLabelTests(unittest.TestCase):
    def test_named_probe_shows_its_name(self):
        roles = {VALID_ROM: {"name": "Battery", "physical_index": 3}}
        self.assertEqual(roles_mod.physical_label(roles, VALID_ROM), "Battery")

    def test_unnamed_commissioned_probe_shows_generic_physical_index_label(self):
        roles = {VALID_ROM: {"name": None, "physical_index": 3}}
        self.assertEqual(roles_mod.physical_label(roles, VALID_ROM), "Probe 3")

    def test_unnamed_uncommissioned_probe_is_a_generic_unnamed_label(self):
        roles = {VALID_ROM: {"name": None, "physical_index": None}}
        self.assertEqual(roles_mod.physical_label(roles, VALID_ROM), "Unnamed probe")

    def test_unknown_rom_not_in_roles_at_all(self):
        self.assertEqual(roles_mod.physical_label({}, VALID_ROM), "Unidentified probe")

    def test_never_falls_back_to_the_rom_itself(self):
        for roles in ({}, {VALID_ROM: {}}, {VALID_ROM: {"name": None, "physical_index": None}}):
            self.assertNotIn(VALID_ROM, roles_mod.physical_label(roles, VALID_ROM))


class CommissionBatchRequestTests(unittest.TestCase):
    def test_a_valid_batch_commissions_every_probe_with_its_index(self):
        batch = {
            "action": "commission_batch",
            "probes": [
                {"rom": VALID_ROM, "physical_index": 1},
                {"rom": VALID_ROM_2, "physical_index": 2},
            ],
        }
        result = roles_mod.apply_name_request({}, batch)
        self.assertTrue(result[VALID_ROM]["commissioned"])
        self.assertEqual(result[VALID_ROM]["physical_index"], 1)
        self.assertTrue(result[VALID_ROM_2]["commissioned"])
        self.assertEqual(result[VALID_ROM_2]["physical_index"], 2)
        # Commissioning alone never invents a name or role:
        self.assertIsNone(result[VALID_ROM]["name"])
        self.assertIsNone(result[VALID_ROM]["role"])

    def test_commissioning_an_already_named_probe_preserves_its_name(self):
        existing = {VALID_ROM: {"name": "Kept", "assigned_at": 1.0}}
        batch = {"action": "commission_batch", "probes": [{"rom": VALID_ROM, "physical_index": 5}]}
        result = roles_mod.apply_name_request(existing, batch)
        self.assertEqual(result[VALID_ROM]["name"], "Kept")
        self.assertTrue(result[VALID_ROM]["commissioned"])
        self.assertEqual(result[VALID_ROM]["physical_index"], 5)

    def test_re_commissioning_is_idempotent_and_keeps_the_original_timestamp(self):
        batch = {"action": "commission_batch", "probes": [{"rom": VALID_ROM, "physical_index": 1}]}
        once = roles_mod.apply_name_request({}, batch)
        first_ts = once[VALID_ROM]["commissioned_at"]
        twice = roles_mod.apply_name_request(once, batch)
        self.assertEqual(twice[VALID_ROM]["commissioned_at"], first_ts)

    def test_duplicate_rom_within_one_batch_is_rejected_entirely(self):
        batch = {
            "action": "commission_batch",
            "probes": [
                {"rom": VALID_ROM, "physical_index": 1},
                {"rom": VALID_ROM, "physical_index": 2},
            ],
        }
        self.assertEqual(roles_mod.apply_name_request({}, batch), {})

    def test_duplicate_physical_index_within_one_batch_is_rejected_entirely(self):
        batch = {
            "action": "commission_batch",
            "probes": [
                {"rom": VALID_ROM, "physical_index": 1},
                {"rom": VALID_ROM_2, "physical_index": 1},
            ],
        }
        self.assertEqual(roles_mod.apply_name_request({}, batch), {})

    def test_one_invalid_rom_in_the_batch_rejects_the_whole_batch(self):
        """Partial application would leave physical_index assignments
        half-done - all or nothing, matching the module's own atomicity
        guarantee for this action."""
        batch = {
            "action": "commission_batch",
            "probes": [
                {"rom": VALID_ROM, "physical_index": 1},
                {"rom": "not-a-rom", "physical_index": 2},
            ],
        }
        result = roles_mod.apply_name_request({"keep": "me"}, batch)
        self.assertEqual(result, {"keep": "me"})

    def test_zero_or_negative_physical_index_is_rejected(self):
        for bad_index in (0, -1, "1", None):
            batch = {"action": "commission_batch", "probes": [{"rom": VALID_ROM, "physical_index": bad_index}]}
            self.assertEqual(roles_mod.apply_name_request({}, batch), {})

    def test_empty_probes_list_is_rejected(self):
        self.assertEqual(roles_mod.apply_name_request({}, {"action": "commission_batch", "probes": []}), {})

    def test_does_not_mutate_the_input_dict(self):
        original = {}
        batch = {"action": "commission_batch", "probes": [{"rom": VALID_ROM, "physical_index": 1}]}
        roles_mod.apply_name_request(original, batch)
        self.assertEqual(original, {})


class RemovePreservesCommissioningTests(unittest.TestCase):
    def test_removing_the_name_of_a_commissioned_probe_keeps_its_identity(self):
        existing = {
            VALID_ROM: {
                "name": "Old Name",
                "assigned_at": 1.0,
                "commissioned": True,
                "commissioned_at": 1.0,
                "physical_index": 2,
                "role": None,
            }
        }
        result = roles_mod.apply_name_request(existing, {"action": "remove", "rom": VALID_ROM})
        self.assertIn(VALID_ROM, result)
        self.assertIsNone(result[VALID_ROM]["name"])
        self.assertTrue(result[VALID_ROM]["commissioned"])
        self.assertEqual(result[VALID_ROM]["physical_index"], 2)

    def test_removing_the_name_of_a_never_commissioned_probe_drops_the_entry(self):
        existing = {VALID_ROM: {"name": "Old", "assigned_at": 1.0}}
        result = roles_mod.apply_name_request(existing, {"action": "remove", "rom": VALID_ROM})
        self.assertNotIn(VALID_ROM, result)


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
        # load_roles() normalizes every entry to the full current schema
        # (commissioned/commissioned_at/physical_index/role default to
        # falsy/None) - a legacy name-only entry round-trips as itself
        # plus those defaults, not byte-identical to what was saved.
        loaded = roles_mod.load_roles()
        self.assertEqual(loaded[VALID_ROM]["name"], "Enclosure")
        self.assertEqual(loaded[VALID_ROM]["assigned_at"], 123.0)
        self.assertFalse(loaded[VALID_ROM]["commissioned"])
        self.assertIsNone(loaded[VALID_ROM]["physical_index"])
        self.assertIsNone(loaded[VALID_ROM]["role"])

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
