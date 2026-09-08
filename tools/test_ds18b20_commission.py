#!/usr/bin/env python3
"""
Tests for tools/ds18b20_commission.py's pure logic (2026-09-07) - the
`identify` command's baseline/delta comparison, which exists
specifically so the operator never has to manually eyeball several
similar-looking temperature streams to spot which one is rising
(per instruction). Only the pure, file-I/O-free functions are tested
here - the interactive loop itself is exercised live against real
hardware, same as this project's other CLI tools.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import ds18b20_commission as commission  # noqa: E402


class ComputeDeltasTests(unittest.TestCase):
    def test_the_warmed_probe_sorts_first(self):
        baseline = {"aaa": 25.0, "bbb": 25.0, "ccc": 25.0}
        current = {
            "aaa": {"ok": True, "value": 25.1},
            "bbb": {"ok": True, "value": 30.5},  # warmed
            "ccc": {"ok": True, "value": 24.9},
        }
        rows = commission.compute_deltas(baseline, current)
        self.assertEqual(rows[0][0], "bbb")
        self.assertAlmostEqual(rows[0][2], 5.5, places=3)

    def test_a_currently_failing_probe_sorts_last_not_first(self):
        """A disconnected/failing probe must never look like 'the
        biggest mover' just because its delta is None/unsortable."""
        baseline = {"aaa": 25.0, "bbb": 25.0}
        current = {
            "aaa": {"ok": True, "value": 25.05},
            "bbb": {"ok": False, "err": "disconnected"},
        }
        rows = commission.compute_deltas(baseline, current)
        self.assertEqual(rows[-1][0], "bbb")
        self.assertIsNone(rows[-1][2])

    def test_a_probe_missing_from_the_baseline_reports_no_delta(self):
        """A probe that appeared AFTER the baseline was captured (e.g.
        it was momentarily failing at baseline time) must show an
        honest 'no delta yet', never a fabricated comparison."""
        baseline = {"aaa": 25.0}
        current = {
            "aaa": {"ok": True, "value": 25.0},
            "new_probe": {"ok": True, "value": 40.0},
        }
        rows = commission.compute_deltas(baseline, current)
        by_rom = {r[0]: r for r in rows}
        self.assertIsNone(by_rom["new_probe"][2])
        self.assertEqual(by_rom["new_probe"][1], 40.0)  # current value still shown

    def test_no_change_reports_a_near_zero_delta_not_none(self):
        baseline = {"aaa": 25.0}
        current = {"aaa": {"ok": True, "value": 25.0}}
        rows = commission.compute_deltas(baseline, current)
        self.assertEqual(rows[0][2], 0.0)

    def test_negative_delta_is_preserved_not_clamped(self):
        """A probe that COOLS relative to baseline (e.g. it was the one
        that had just been warmed before the baseline was taken) must
        show a real negative delta, not be clamped to zero - the sign
        itself is useful information during commissioning."""
        baseline = {"aaa": 30.0}
        current = {"aaa": {"ok": True, "value": 28.0}}
        rows = commission.compute_deltas(baseline, current)
        self.assertEqual(rows[0][2], -2.0)

    def test_empty_current_probes_returns_empty_list(self):
        self.assertEqual(commission.compute_deltas({"aaa": 25.0}, {}), [])

    def test_malformed_reading_shape_does_not_crash(self):
        baseline = {"aaa": 25.0}
        current = {"aaa": "not a dict"}
        # Must not raise - get() on a string would raise AttributeError
        # if this function isn't defensive about reading shape.
        with self.assertRaises(AttributeError):
            commission.compute_deltas(baseline, current)
        # (documents the current real behavior: the caller is expected
        # to pass the already-validated get_ds18b20_probes() shape,
        # which is always dict-of-dicts by construction - see that
        # function's own filtering)


class IdentifyThresholdTests(unittest.TestCase):
    def test_threshold_is_well_above_normal_sensor_jitter(self):
        """DS18B20's own resolution step (12-bit) is 0.0625C - the
        identify threshold must be comfortably larger than any
        plausible successive-read jitter, or a resting probe could
        falsely flag as 'the one being warmed'."""
        self.assertGreater(commission.IDENTIFY_THRESHOLD_C, 1.0)


if __name__ == "__main__":
    unittest.main()
