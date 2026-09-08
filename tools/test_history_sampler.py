#!/usr/bin/env python3
"""
Tests for piratebox_history_sampler.py (2026-09-08) - the systemd-
timer-triggered oneshot that decides "is this reading valid to record"
and calls piratebox_history.record_sample(). Fakes piratebox_esp32_
client.get_diagnostics() (monkeypatched) rather than touching the real
export file - matches tools/test_hardware_health.py's own style of
constructing diagnostics dicts directly.
"""
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_esp32_client as client
import piratebox_history as history_mod
import piratebox_history_sampler as sampler

ROM_1 = "28fd856b0000003b"
ROM_2 = "28a5ea00000000ce"


def _diag(connected=True, stale=False, capabilities=None, sensors=None):
    return {
        "connected": connected, "stale": stale,
        "capabilities": capabilities if capabilities is not None else [],
        "sensors": sensors if sensors is not None else {},
    }


class SampleOnceTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_dir = history_mod.HISTORY_DIR
        history_mod.HISTORY_DIR = self._tmpdir.name
        self._orig_get_diag = client.get_diagnostics

    def tearDown(self):
        history_mod.HISTORY_DIR = self._orig_dir
        client.get_diagnostics = self._orig_get_diag
        self._tmpdir.cleanup()

    def _fake(self, diag):
        client.get_diagnostics = lambda: diag

    def test_healthy_bh1750_and_temp_internal_are_recorded(self):
        self._fake(_diag(
            capabilities=["bh1750", "temp_internal"],
            sensors={
                "bh1750": {"ok": True, "value": 42.5, "unit": "lux"},
                "temp_internal": {"ok": True, "value": 41.0, "unit": "C"},
            },
        ))
        result = sampler.sample_once(now=1000.0)
        self.assertIn("ambient_lux", result["recorded"])
        self.assertIn("esp32_temp_internal", result["recorded"])
        self.assertEqual(history_mod.load_signal_history("ambient_lux")["raw"][0]["v"], 42.5)

    def test_stale_link_records_nothing(self):
        self._fake(_diag(connected=False))
        result = sampler.sample_once(now=1000.0)
        self.assertEqual(result["recorded"], [])

    def test_reading_not_ok_is_skipped_not_recorded(self):
        self._fake(_diag(
            capabilities=["bh1750"],
            sensors={"bh1750": {"ok": False, "err": "disconnected"}},
        ))
        result = sampler.sample_once(now=1000.0)
        self.assertEqual(result["recorded"], [])
        self.assertEqual(history_mod.load_signal_history("ambient_lux")["raw"], [])

    def test_capability_never_advertised_is_skipped(self):
        self._fake(_diag(capabilities=[]))
        result = sampler.sample_once(now=1000.0)
        self.assertEqual(result["recorded"], [])

    def test_two_commissioned_probes_both_recorded_under_rom_keyed_signals(self):
        self._fake(_diag(
            capabilities=["ds18b20"],
            sensors={"ds18b20": {
                "bus_ok": True,
                "probes": {
                    ROM_1: {"ok": True, "value": 29.5, "name": None, "physical_index": 1},
                    ROM_2: {"ok": True, "value": 29.8, "name": None, "physical_index": 2},
                },
                "commissioned": {ROM_1: {"name": None, "physical_index": 1}, ROM_2: {"name": None, "physical_index": 2}},
            }},
        ))
        result = sampler.sample_once(now=1000.0)
        self.assertIn(history_mod.ds18b20_signal_id(ROM_1), result["recorded"])
        self.assertIn(history_mod.ds18b20_signal_id(ROM_2), result["recorded"])
        self.assertEqual(
            history_mod.load_signal_history(history_mod.ds18b20_signal_id(ROM_1))["raw"][0]["v"], 29.5
        )
        self.assertEqual(
            history_mod.load_signal_history(history_mod.ds18b20_signal_id(ROM_2))["raw"][0]["v"], 29.8
        )

    def test_a_commissioned_but_currently_missing_probe_is_skipped_not_a_gap_filled_with_a_fake_value(self):
        self._fake(_diag(
            capabilities=["ds18b20"],
            sensors={"ds18b20": {
                "bus_ok": True,
                "probes": {},  # ROM_1 commissioned but not reporting this cycle
                "commissioned": {ROM_1: {"name": None, "physical_index": 1}},
            }},
        ))
        result = sampler.sample_once(now=1000.0)
        self.assertEqual(result["recorded"], [])
        self.assertIn((history_mod.ds18b20_signal_id(ROM_1), "not_ok"), result["skipped"])

    def test_a_failing_commissioned_probe_is_skipped(self):
        self._fake(_diag(
            capabilities=["ds18b20"],
            sensors={"ds18b20": {
                "bus_ok": True,
                "probes": {ROM_1: {"ok": False, "err": "disconnected"}},
                "commissioned": {ROM_1: {"name": None, "physical_index": 1}},
            }},
        ))
        result = sampler.sample_once(now=1000.0)
        self.assertEqual(result["recorded"], [])

    def test_an_uncommissioned_probe_on_the_bus_is_never_recorded(self):
        """Only commissioned ROMs get a history stream at all - a
        brand-new, never-commissioned probe is real live data on the
        Environment page (see the hardware-awareness phase) but
        deliberately has no historical identity yet."""
        self._fake(_diag(
            capabilities=["ds18b20"],
            sensors={"ds18b20": {
                "bus_ok": True,
                "probes": {ROM_1: {"ok": True, "value": 30.0, "name": None, "physical_index": None}},
                "commissioned": {},
            }},
        ))
        result = sampler.sample_once(now=1000.0)
        self.assertEqual(result["recorded"], [])

    def test_85c_style_suspect_value_is_never_recorded(self):
        """The firmware itself refuses to report ok=true for the
        85C power-on/uninitialized sentinel - this test documents that
        the sampler correctly trusts and relies on that upstream
        validation (ok=false here), never re-implementing its own
        85C-specific check."""
        self._fake(_diag(
            capabilities=["ds18b20"],
            sensors={"ds18b20": {
                "bus_ok": True,
                "probes": {ROM_1: {"ok": False, "err": "suspect_85c_init"}},
                "commissioned": {ROM_1: {"name": None, "physical_index": 1}},
            }},
        ))
        result = sampler.sample_once(now=1000.0)
        self.assertEqual(result["recorded"], [])

    def test_sample_once_does_not_add_its_own_exception_handling_on_top_of_the_clients_own_contract(self):
        """piratebox_esp32_client.get_diagnostics() already guarantees
        "never raises" (its own docstring) - sample_once() deliberately
        trusts that rather than adding a second, redundant try/except.
        If that contract were ever violated, an exception here would
        propagate out of this oneshot systemd unit - a safe failure
        mode (the unit is simply marked failed for this run; the next
        scheduled timer tick tries again 5 minutes later, and nothing
        was written since record_sample() is only reached after a
        successful read), never a crash loop or corrupted history."""
        def _raise():
            raise RuntimeError("violates get_diagnostics()'s own contract")
        client.get_diagnostics = _raise
        with self.assertRaises(RuntimeError):
            sampler.sample_once(now=1000.0)


if __name__ == "__main__":
    unittest.main()
