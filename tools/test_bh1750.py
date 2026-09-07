#!/usr/bin/env python3
"""
Regression tests for piratebox_bh1750.py (2026-09-07, BH1750 ambient
light sensor commissioning - docs/HARDWARE-INTEGRATION-DESIGN.md).

These test the module's own rate-limiting/staleness/degrade behavior
in isolation, without touching real hardware - `_read_raw_lux` (the
one function that actually does I2C) is monkeypatched in every test
that needs to control what a "read" returns, and restored in
tearDown. A real-hardware smoke test already exists and was run live
during commissioning (see tools/diagnose_bh1750.py) - these tests
exist to keep the degrade-gracefully contract from regressing, in an
environment that may have no I2C bus at all.

Covers exactly the operational questions this sensor's diagnostics
need to answer (see the module's own get_diagnostics() docstring):
detected/responding, current lux, staleness, last error - plus the
two behaviors most likely to regress silently: rate limiting (must not
hit real hardware on every call) and degrade-not-crash (any failure,
including smbus2 itself being absent, must return None, never raise).
"""
import sys
import time
import types
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_bh1750 as bh


class BH1750ReaderTests(unittest.TestCase):
    def setUp(self):
        self._orig_read_raw = bh._read_raw_lux
        self._orig_smbus2 = bh.smbus2
        # Reset module-level cache before each test - real mutable
        # state that must not leak between tests.
        bh._last_attempt_at = 0.0
        bh._last_success_at = None
        bh._last_lux = None
        bh._last_error = None

    def tearDown(self):
        bh._read_raw_lux = self._orig_read_raw
        bh.smbus2 = self._orig_smbus2

    def test_successful_read_returns_lux_and_updates_cache(self):
        bh._read_raw_lux = lambda: 12.34
        result = bh.read_ambient_lux()
        self.assertEqual(result, 12.3)  # rounded to 1 decimal
        diag = bh.get_diagnostics()
        self.assertTrue(diag["detected"])
        self.assertFalse(diag["stale"])
        self.assertIsNone(diag["last_error"])
        self.assertEqual(diag["lux"], 12.3)

    def test_rate_limited_second_call_does_not_hit_hardware_again(self):
        calls = []

        def counting_read():
            calls.append(1)
            return 5.0

        bh._read_raw_lux = counting_read
        bh.read_ambient_lux()
        bh.read_ambient_lux()  # immediately again - must be served from cache
        self.assertEqual(
            len(calls), 1,
            "a second call within MIN_READ_INTERVAL_S must not touch hardware again",
        )

    def test_failed_read_with_no_prior_success_returns_none(self):
        def failing():
            raise OSError("no ack from device")

        bh._read_raw_lux = failing
        result = bh.read_ambient_lux()
        self.assertIsNone(result)
        diag = bh.get_diagnostics()
        self.assertFalse(diag["detected"])
        self.assertIn("OSError", diag["last_error"])

    def test_failed_read_after_prior_success_falls_back_to_last_good_value(self):
        bh._read_raw_lux = lambda: 8.0
        bh.read_ambient_lux()
        bh._last_attempt_at = 0.0  # force the rate limiter to allow a retry

        def failing():
            raise OSError("transient bus error")

        bh._read_raw_lux = failing
        result = bh.read_ambient_lux()
        self.assertEqual(
            result, 8.0,
            "a transient failure should fall back to the last good reading while still fresh",
        )

    def test_stale_cached_value_is_not_reported_as_current(self):
        bh._read_raw_lux = lambda: 3.0
        bh.read_ambient_lux()
        bh._last_success_at = time.monotonic() - (bh.STALE_AFTER_S + 10)
        bh._last_attempt_at = 0.0

        def failing():
            raise OSError("still down")

        bh._read_raw_lux = failing
        result = bh.read_ambient_lux()
        self.assertIsNone(result, "a stale last-known-good value must never be reported as current")
        self.assertTrue(bh.get_diagnostics()["stale"])

    def test_never_raises_even_with_smbus2_missing(self):
        bh.smbus2 = None
        result = bh.read_ambient_lux()  # exercises the real _read_raw_lux, not a mock
        self.assertIsNone(result)
        self.assertIn("RuntimeError", bh.get_diagnostics()["last_error"])

    def test_diagnostics_has_every_expected_key(self):
        diag = bh.get_diagnostics()
        for key in ("i2c_bus", "address", "detected", "lux", "last_success_seconds_ago", "stale", "last_error"):
            self.assertIn(key, diag)


class BH1750ProtocolTests(unittest.TestCase):
    """The specific address and formula this module claims to use,
    checked directly - load-bearing for docs claiming these exact
    values were confirmed live against real hardware (2026-09-07)."""

    def setUp(self):
        self._orig_smbus2 = bh.smbus2

    def tearDown(self):
        bh.smbus2 = self._orig_smbus2

    def test_address_matches_confirmed_hardware(self):
        self.assertEqual(bh.ADDRESS, 0x23)

    def test_lux_formula_matches_datasheet(self):
        fake_bus = types.SimpleNamespace(
            write_byte=lambda *a, **k: None,
            read_i2c_block_data=lambda *a, **k: [0x00, 0x0c],  # raw = 12
            close=lambda: None,
        )
        bh.smbus2 = types.SimpleNamespace(SMBus=lambda bus_num: fake_bus)
        lux = bh._read_raw_lux()
        self.assertAlmostEqual(lux, 12 / 1.2)


if __name__ == "__main__":
    unittest.main()
