#!/usr/bin/env python3
"""
Tests for piratebox_history.py (2026-09-08) - the bounded, lightweight
sensor-history storage/retention engine. Matches this project's
existing dependency-free tools/test_*.py convention.

Run with: python3 tools/test_history.py
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_history as history_mod

DAY = 86400
HOUR = 3600


class SignalIdTests(unittest.TestCase):
    def test_ds18b20_signal_id_round_trips(self):
        rom = "28fd856b0000003b"
        sid = history_mod.ds18b20_signal_id(rom)
        self.assertTrue(history_mod.is_ds18b20_signal_id(sid))
        self.assertEqual(history_mod.ds18b20_rom_from_signal_id(sid), rom)

    def test_non_ds18b20_signal_is_not_mistaken(self):
        self.assertFalse(history_mod.is_ds18b20_signal_id("ambient_lux"))
        self.assertIsNone(history_mod.ds18b20_rom_from_signal_id("ambient_lux"))

    def test_signal_file_path_rejects_unsafe_ids(self):
        for bad in ["../etc/passwd", "a/b", "", "a" * 200, "has space", None, 42]:
            with self.assertRaises(ValueError):
                history_mod.signal_file_path(bad)

    def test_signal_file_path_accepts_normal_ids(self):
        p = history_mod.signal_file_path("ds18b20_28fd856b0000003b")
        self.assertTrue(p.endswith("ds18b20_28fd856b0000003b.json"))


class AppendRawSampleTests(unittest.TestCase):
    def _empty(self):
        return history_mod._empty_history()

    def test_first_sample_is_recorded(self):
        h = history_mod.append_raw_sample(self._empty(), 1000.0, 21.5)
        self.assertEqual(h["raw"], [{"t": 1000.0, "v": 21.5}])

    def test_does_not_mutate_the_input(self):
        original = self._empty()
        history_mod.append_raw_sample(original, 1000.0, 21.5)
        self.assertEqual(original["raw"], [])

    def test_second_sample_after_the_gap_is_appended(self):
        h = history_mod.append_raw_sample(self._empty(), 1000.0, 21.5)
        h = history_mod.append_raw_sample(h, 1000.0 + history_mod.MIN_SAMPLE_GAP_SECONDS + 1, 22.0)
        self.assertEqual(len(h["raw"]), 2)

    def test_too_soon_after_the_last_sample_is_rejected(self):
        h = history_mod.append_raw_sample(self._empty(), 1000.0, 21.5)
        h2 = history_mod.append_raw_sample(h, 1000.0 + 1, 99.0)
        self.assertEqual(h2["raw"], h["raw"])  # unchanged - too soon

    def test_clock_stepping_backward_is_rejected(self):
        h = history_mod.append_raw_sample(self._empty(), 1000.0, 21.5)
        h2 = history_mod.append_raw_sample(h, 500.0, 99.0)
        self.assertEqual(h2["raw"], h["raw"])

    def test_exact_duplicate_timestamp_is_rejected(self):
        h = history_mod.append_raw_sample(self._empty(), 1000.0, 21.5)
        h2 = history_mod.append_raw_sample(h, 1000.0, 99.0)
        self.assertEqual(h2["raw"], h["raw"])

    def test_non_numeric_value_is_rejected(self):
        for bad in [None, "21.5", [], {}, True, False]:
            h = history_mod.append_raw_sample(self._empty(), 1000.0, bad)
            self.assertEqual(h["raw"], [])

    def test_nan_and_inf_are_rejected(self):
        for bad in [float("nan"), float("inf"), float("-inf")]:
            h = history_mod.append_raw_sample(self._empty(), 1000.0, bad)
            self.assertEqual(h["raw"], [])

    def test_old_raw_samples_are_pruned_on_append(self):
        h = self._empty()
        h["raw"] = [{"t": 0.0, "v": 1.0}]
        now = history_mod.RAW_RETENTION_SECONDS + 1000
        h = history_mod.append_raw_sample(h, now, 2.0)
        self.assertEqual(len(h["raw"]), 1)  # the old one pruned, only the new one remains
        self.assertEqual(h["raw"][0]["v"], 2.0)

    def test_int_value_is_stored_as_float(self):
        h = history_mod.append_raw_sample(self._empty(), 1000.0, 5)
        self.assertIsInstance(h["raw"][0]["v"], float)


class CompactHourlyTests(unittest.TestCase):
    def test_a_completed_hour_is_summarized(self):
        h = history_mod._empty_history()
        h["raw"] = [
            {"t": 3600 * 5 + 0, "v": 10.0},
            {"t": 3600 * 5 + 100, "v": 20.0},
            {"t": 3600 * 5 + 200, "v": 30.0},
        ]
        now = 3600 * 6 + 1  # hour 5 has fully ended
        h2 = history_mod.compact_hourly(h, now)
        self.assertEqual(len(h2["hourly"]), 1)
        entry = h2["hourly"][0]
        self.assertEqual(entry["t"], 3600 * 5)
        self.assertEqual(entry["min"], 10.0)
        self.assertEqual(entry["max"], 30.0)
        self.assertAlmostEqual(entry["avg"], 20.0)
        self.assertEqual(entry["n"], 3)

    def test_an_in_progress_hour_is_not_summarized(self):
        h = history_mod._empty_history()
        h["raw"] = [{"t": 3600 * 5 + 100, "v": 10.0}]
        now = 3600 * 5 + 200  # hour 5 is still ongoing
        h2 = history_mod.compact_hourly(h, now)
        self.assertEqual(h2["hourly"], [])

    def test_is_idempotent(self):
        h = history_mod._empty_history()
        h["raw"] = [{"t": 3600 * 5 + 0, "v": 10.0}]
        now = 3600 * 6 + 1
        h2 = history_mod.compact_hourly(h, now)
        h3 = history_mod.compact_hourly(h2, now)
        self.assertEqual(h2["hourly"], h3["hourly"])

    def test_multi_hour_gap_backfills_every_missing_hour(self):
        h = history_mod._empty_history()
        h["raw"] = [
            {"t": 3600 * 5 + 0, "v": 10.0},
            {"t": 3600 * 8 + 0, "v": 20.0},  # 3 hours later, nothing in between
        ]
        now = 3600 * 9 + 1
        h2 = history_mod.compact_hourly(h, now)
        self.assertEqual(len(h2["hourly"]), 2)  # only the two hours with data, no fabricated middle
        self.assertEqual([e["t"] for e in h2["hourly"]], [3600 * 5, 3600 * 8])

    def test_old_hourly_entries_are_pruned(self):
        h = history_mod._empty_history()
        h["hourly"] = [{"t": 0, "min": 1, "avg": 1, "max": 1, "n": 1}]
        now = history_mod.HOURLY_RETENTION_SECONDS + 10000
        h2 = history_mod.compact_hourly(h, now)
        self.assertEqual(h2["hourly"], [])

    def test_does_not_mutate_the_input(self):
        h = history_mod._empty_history()
        h["raw"] = [{"t": 3600 * 5, "v": 10.0}]
        original_raw = list(h["raw"])
        history_mod.compact_hourly(h, 3600 * 6 + 1)
        self.assertEqual(h["raw"], original_raw)
        self.assertEqual(h["hourly"], [])


class CompactDailyTests(unittest.TestCase):
    def test_a_completed_day_is_summarized_with_weighted_average(self):
        h = history_mod._empty_history()
        h["hourly"] = [
            {"t": DAY * 2 + 0, "min": 10.0, "avg": 10.0, "max": 10.0, "n": 6},
            {"t": DAY * 2 + HOUR, "min": 20.0, "avg": 20.0, "max": 20.0, "n": 2},
        ]
        now = DAY * 3 + 1
        h2 = history_mod.compact_daily(h, now)
        self.assertEqual(len(h2["daily"]), 1)
        entry = h2["daily"][0]
        self.assertEqual(entry["t"], DAY * 2)
        self.assertEqual(entry["min"], 10.0)
        self.assertEqual(entry["max"], 20.0)
        # weighted: (10*6 + 20*2) / 8 = 12.5, not the naive (10+20)/2=15
        self.assertAlmostEqual(entry["avg"], 12.5)
        self.assertEqual(entry["n"], 8)

    def test_an_in_progress_day_is_not_summarized(self):
        h = history_mod._empty_history()
        h["hourly"] = [{"t": DAY * 2 + HOUR * 3, "min": 1, "avg": 1, "max": 1, "n": 1}]
        now = DAY * 2 + HOUR * 5
        h2 = history_mod.compact_daily(h, now)
        self.assertEqual(h2["daily"], [])

    def test_old_daily_entries_are_pruned(self):
        h = history_mod._empty_history()
        h["daily"] = [{"t": 0, "min": 1, "avg": 1, "max": 1, "n": 1}]
        now = history_mod.DAILY_RETENTION_SECONDS + 100000
        h2 = history_mod.compact_daily(h, now)
        self.assertEqual(h2["daily"], [])

    def test_is_idempotent(self):
        h = history_mod._empty_history()
        h["hourly"] = [{"t": DAY * 2, "min": 1, "avg": 1, "max": 1, "n": 1}]
        now = DAY * 3 + 1
        h2 = history_mod.compact_daily(h, now)
        h3 = history_mod.compact_daily(h2, now)
        self.assertEqual(h2["daily"], h3["daily"])


class RecordSampleEndToEndTests(unittest.TestCase):
    """record_sample() is the sampler's actual entry point - load,
    append, compact both tiers, save. Uses a real temp directory (not
    mocked) to also exercise load/save's atomic-write path."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_dir = history_mod.HISTORY_DIR
        history_mod.HISTORY_DIR = self._tmpdir.name

    def tearDown(self):
        history_mod.HISTORY_DIR = self._orig_dir
        self._tmpdir.cleanup()

    def test_a_valid_sample_is_recorded_and_persisted(self):
        recorded = history_mod.record_sample("ambient_lux", 1000.0, 42.5)
        self.assertTrue(recorded)
        h = history_mod.load_signal_history("ambient_lux")
        self.assertEqual(h["raw"], [{"t": 1000.0, "v": 42.5}])

    def test_rejected_sample_reports_false(self):
        history_mod.record_sample("ambient_lux", 1000.0, 42.5)
        recorded = history_mod.record_sample("ambient_lux", 1000.5, 43.0)  # too soon
        self.assertFalse(recorded)

    def test_two_different_signals_are_stored_separately(self):
        history_mod.record_sample("ambient_lux", 1000.0, 42.5)
        history_mod.record_sample("esp32_temp_internal", 1000.0, 41.0)
        lux = history_mod.load_signal_history("ambient_lux")
        temp = history_mod.load_signal_history("esp32_temp_internal")
        self.assertEqual(lux["raw"][0]["v"], 42.5)
        self.assertEqual(temp["raw"][0]["v"], 41.0)

    def test_five_ds18b20_probes_are_stored_under_distinct_rom_keyed_signals(self):
        roms = ["28fd856b0000003b", "28a5ea00000000ce", "28c1fe2500000043",
                "2840ff00000000a2", "28a50d01000000ca"]
        for i, rom in enumerate(roms):
            history_mod.record_sample(history_mod.ds18b20_signal_id(rom), 1000.0, 29.0 + i)
        for i, rom in enumerate(roms):
            h = history_mod.load_signal_history(history_mod.ds18b20_signal_id(rom))
            self.assertEqual(h["raw"][0]["v"], 29.0 + i)

    def test_rom_identity_persists_across_a_simulated_rename(self):
        """The storage engine has no concept of "name" at all - a
        cosmetic rename (which only ever touches piratebox_ds18b20_
        roles.py's own separate file) can never fork or reset history,
        because history was never keyed by name in the first place."""
        rom = "28fd856b0000003b"
        sid = history_mod.ds18b20_signal_id(rom)
        history_mod.record_sample(sid, 1000.0, 29.5)
        history_mod.record_sample(sid, 1000.0 + history_mod.MIN_SAMPLE_GAP_SECONDS + 1, 29.6)
        # "Renaming" a probe never involves this module at all - the
        # signal id is the ROM, permanently. Simulate a second sampler
        # run after a hypothetical rename: the id passed in is still
        # derived from the ROM, so it's still the same file/history.
        history_mod.record_sample(sid, 1000.0 + 2 * (history_mod.MIN_SAMPLE_GAP_SECONDS + 1), 29.7)
        h = history_mod.load_signal_history(sid)
        self.assertEqual(len(h["raw"]), 3)

    def test_missing_probe_creates_a_gap_not_a_fabricated_point(self):
        rom = "28fd856b0000003b"
        sid = history_mod.ds18b20_signal_id(rom)
        history_mod.record_sample(sid, 1000.0, 29.5)
        # Probe goes missing for a while - sampler simply never calls
        # record_sample() for it during that window (see test_history_
        # sampler.py for that decision logic). Nothing to do here except
        # confirm the stored history has exactly the one real point,
        # with an honest gap in between when it comes back:
        history_mod.record_sample(sid, 1000.0 + 3600, 29.9)
        h = history_mod.load_signal_history(sid)
        self.assertEqual(len(h["raw"]), 2)
        self.assertEqual(h["raw"][1]["t"] - h["raw"][0]["t"], 3600)

    def test_survives_a_corrupt_existing_file(self):
        import os
        os.makedirs(history_mod.HISTORY_DIR, exist_ok=True)
        with open(history_mod.signal_file_path("ambient_lux"), "w") as f:
            f.write("{not valid json")
        recorded = history_mod.record_sample("ambient_lux", 1000.0, 42.5)
        self.assertTrue(recorded)
        h = history_mod.load_signal_history("ambient_lux")
        self.assertEqual(h["raw"][0]["v"], 42.5)

    def test_leftover_tmp_file_from_an_interrupted_write_does_not_break_future_writes(self):
        """Simulates a crash mid-write: a stray .tmp.<pid> file exists
        alongside a good, already-committed file. The next real write
        must succeed and must not be confused by the stray temp file
        (each write's temp file is uniquely named by the writer's own
        pid, and os.replace() only ever targets the real file)."""
        import os
        history_mod.record_sample("ambient_lux", 1000.0, 1.0)
        stray = history_mod.signal_file_path("ambient_lux") + ".tmp.999999"
        with open(stray, "w") as f:
            f.write("{incomplete")
        recorded = history_mod.record_sample(
            "ambient_lux", 1000.0 + history_mod.MIN_SAMPLE_GAP_SECONDS + 1, 2.0
        )
        self.assertTrue(recorded)
        h = history_mod.load_signal_history("ambient_lux")
        self.assertEqual(len(h["raw"]), 2)
        os.remove(stray)  # cleanup - not part of what's under test


class ChooseTierForRangeTests(unittest.TestCase):
    def test_short_range_uses_raw(self):
        self.assertEqual(history_mod.choose_tier_for_range(6 * HOUR), history_mod.TIER_RAW)
        self.assertEqual(history_mod.choose_tier_for_range(24 * HOUR), history_mod.TIER_RAW)

    def test_week_range_uses_raw_since_raw_retention_covers_a_week(self):
        self.assertEqual(history_mod.choose_tier_for_range(7 * DAY), history_mod.TIER_RAW)

    def test_month_range_uses_hourly(self):
        self.assertEqual(history_mod.choose_tier_for_range(30 * DAY), history_mod.TIER_HOURLY)

    def test_year_range_uses_daily(self):
        self.assertEqual(history_mod.choose_tier_for_range(366 * DAY), history_mod.TIER_DAILY)


class QueryRangeTests(unittest.TestCase):
    def test_filters_to_the_window_inclusive(self):
        h = {"raw": [{"t": 100, "v": 1}, {"t": 200, "v": 2}, {"t": 300, "v": 3}]}
        result = history_mod.query_range(h, "raw", 100, 200)
        self.assertEqual([e["t"] for e in result], [100, 200])

    def test_returns_chronological_order_even_if_stored_out_of_order(self):
        h = {"raw": [{"t": 300, "v": 3}, {"t": 100, "v": 1}]}
        result = history_mod.query_range(h, "raw", 0, 1000)
        self.assertEqual([e["t"] for e in result], [100, 300])

    def test_unknown_tier_returns_empty_not_a_crash(self):
        h = {"raw": [{"t": 100, "v": 1}]}
        self.assertEqual(history_mod.query_range(h, "weekly", 0, 1000), [])

    def test_empty_history_returns_empty(self):
        self.assertEqual(history_mod.query_range({}, "raw", 0, 1000), [])


if __name__ == "__main__":
    unittest.main()
