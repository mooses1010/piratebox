#!/usr/bin/env python3
"""
Tests for piratebox_hardware_health.py (2026-09-08, hardware-awareness
phase) - the shared sensor-health classifier reused by the OLED daemon,
diagnostics tooling, and mirrored in PHP for the admin capability
table. Every function under test is pure (an already-built diagnostics
dict in, a state string/dict out) - no file I/O anywhere here.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_hardware_health as health

ROM_1 = "28fd856b0000003b"
ROM_2 = "28a5ea00000000ce"
ROM_3 = "28c1fe2500000043"


def _diag(connected=True, stale=False, capabilities=None, sensors=None, reason=None):
    d = {
        "connected": connected,
        "stale": stale,
        "capabilities": capabilities if capabilities is not None else [],
        "sensors": sensors if sensors is not None else {},
    }
    if reason is not None:
        d["reason"] = reason
    return d


class ClassifyEsp32SupervisorTests(unittest.TestCase):
    def test_no_export_is_unknown_not_not_installed(self):
        self.assertEqual(health.classify_esp32_supervisor(_diag(reason="no_export")), "UNKNOWN")

    def test_connected_and_fresh_is_available(self):
        self.assertEqual(health.classify_esp32_supervisor(_diag(connected=True, stale=False)), "AVAILABLE")

    def test_connected_but_stale_heartbeat_is_degraded(self):
        self.assertEqual(health.classify_esp32_supervisor(_diag(connected=True, stale=True)), "DEGRADED")

    def test_not_connected_is_unavailable(self):
        self.assertEqual(health.classify_esp32_supervisor(_diag(connected=False, stale=True)), "UNAVAILABLE")

    def test_not_a_dict_is_unknown(self):
        for bad in (None, "x", 42, []):
            self.assertEqual(health.classify_esp32_supervisor(bad), "UNKNOWN")


class ClassifySimpleSensorTests(unittest.TestCase):
    def test_link_problem_is_inherited_verbatim(self):
        diag = _diag(connected=False)
        self.assertEqual(health.classify_simple_sensor(diag, "bh1750"), "UNAVAILABLE")

    def test_capability_never_advertised_is_not_installed(self):
        diag = _diag(capabilities=["temp_internal"], sensors={"temp_internal": {"ok": True, "value": 1.0}})
        self.assertEqual(health.classify_simple_sensor(diag, "bh1750"), "NOT_INSTALLED")

    def test_advertised_and_ok_is_available(self):
        diag = _diag(capabilities=["bh1750"], sensors={"bh1750": {"ok": True, "value": 42.5, "unit": "lux"}})
        self.assertEqual(health.classify_simple_sensor(diag, "bh1750"), "AVAILABLE")

    def test_advertised_but_reading_not_ok_is_degraded(self):
        diag = _diag(capabilities=["bh1750"], sensors={"bh1750": {"ok": False, "err": "disconnected"}})
        self.assertEqual(health.classify_simple_sensor(diag, "bh1750"), "DEGRADED")

    def test_advertised_but_missing_from_this_cycles_sensors_is_unknown(self):
        diag = _diag(capabilities=["bh1750"], sensors={})
        self.assertEqual(health.classify_simple_sensor(diag, "bh1750"), "UNKNOWN")

    def test_temp_internal_uses_the_same_logic(self):
        diag = _diag(capabilities=["temp_internal"], sensors={"temp_internal": {"ok": True, "value": 41.5}})
        self.assertEqual(health.classify_simple_sensor(diag, "temp_internal"), "AVAILABLE")


class ClassifyDs18b20BusTests(unittest.TestCase):
    def test_link_problem_is_inherited_with_zeroed_detail(self):
        diag = _diag(connected=False)
        result = health.classify_ds18b20_bus(diag, {ROM_1})
        self.assertEqual(result["state"], "UNAVAILABLE")
        self.assertEqual(result["probes_ok"], 0)

    def test_never_commissioned_and_capability_absent_is_not_installed(self):
        diag = _diag(capabilities=[])
        result = health.classify_ds18b20_bus(diag, set())
        self.assertEqual(result["state"], "NOT_INSTALLED")

    def test_commissioned_but_capability_vanished_entirely_is_unavailable(self):
        """A regression: this device HAS commissioned probes before,
        but the current export no longer even advertises the
        capability - must not be reported as if nothing was ever
        wired."""
        diag = _diag(capabilities=[])
        result = health.classify_ds18b20_bus(diag, {ROM_1})
        self.assertEqual(result["state"], "UNAVAILABLE")

    def test_all_five_commissioned_and_all_ok_is_available(self):
        probes = {rom: {"ok": True, "value": 29.5, "unit": "C"} for rom in (ROM_1, ROM_2, ROM_3)}
        diag = _diag(capabilities=["ds18b20"], sensors={"ds18b20": {"bus_ok": True, "probes": probes}})
        result = health.classify_ds18b20_bus(diag, {ROM_1, ROM_2, ROM_3})
        self.assertEqual(result["state"], "AVAILABLE")
        self.assertEqual(result["probes_ok"], 3)
        self.assertEqual(result["missing_commissioned"], [])
        self.assertEqual(result["failing_commissioned"], [])

    def test_one_commissioned_probe_missing_from_probes_is_degraded(self):
        probes = {ROM_1: {"ok": True, "value": 29.5}, ROM_2: {"ok": True, "value": 29.6}}
        diag = _diag(capabilities=["ds18b20"], sensors={"ds18b20": {"bus_ok": True, "probes": probes}})
        result = health.classify_ds18b20_bus(diag, {ROM_1, ROM_2, ROM_3})
        self.assertEqual(result["state"], "DEGRADED")
        self.assertEqual(result["missing_commissioned"], [ROM_3])

    def test_one_commissioned_probe_present_but_not_ok_is_degraded(self):
        probes = {
            ROM_1: {"ok": True, "value": 29.5},
            ROM_2: {"ok": False, "err": "disconnected"},
        }
        diag = _diag(capabilities=["ds18b20"], sensors={"ds18b20": {"bus_ok": True, "probes": probes}})
        result = health.classify_ds18b20_bus(diag, {ROM_1, ROM_2})
        self.assertEqual(result["state"], "DEGRADED")
        self.assertEqual(result["failing_commissioned"], [ROM_2])

    def test_bus_ok_false_is_unavailable_even_with_no_commissioned_probes(self):
        diag = _diag(capabilities=["ds18b20"], sensors={"ds18b20": {"bus_ok": False, "probes": {}}})
        result = health.classify_ds18b20_bus(diag, set())
        self.assertEqual(result["state"], "UNAVAILABLE")

    def test_bus_ok_false_outranks_missing_commissioned_detail(self):
        diag = _diag(capabilities=["ds18b20"], sensors={"ds18b20": {"bus_ok": False, "probes": {}}})
        result = health.classify_ds18b20_bus(diag, {ROM_1})
        self.assertEqual(result["state"], "UNAVAILABLE")

    def test_genuinely_never_wired_is_not_installed_not_degraded(self):
        """bus_ok is true both when healthy and when genuinely never
        wired (firmware semantics) - zero probes and nothing
        commissioned must never read as a fault."""
        diag = _diag(capabilities=["ds18b20"], sensors={"ds18b20": {"bus_ok": True, "probes": {}}})
        result = health.classify_ds18b20_bus(diag, set())
        self.assertEqual(result["state"], "NOT_INSTALLED")

    def test_a_brand_new_uncommissioned_probe_appearing_is_available_not_degraded(self):
        """A probe nobody has commissioned yet showing up on the bus is
        not a fault condition - it's new information, not a problem."""
        probes = {ROM_1: {"ok": True, "value": 30.0}}
        diag = _diag(capabilities=["ds18b20"], sensors={"ds18b20": {"bus_ok": True, "probes": probes}})
        result = health.classify_ds18b20_bus(diag, set())
        self.assertEqual(result["state"], "AVAILABLE")

    def test_ds18b20_block_not_a_dict_is_unknown(self):
        diag = _diag(capabilities=["ds18b20"], sensors={"ds18b20": "not a dict"})
        result = health.classify_ds18b20_bus(diag, {ROM_1})
        self.assertEqual(result["state"], "UNKNOWN")

    def test_detail_counts_are_always_present_and_consistent(self):
        probes = {ROM_1: {"ok": True, "value": 1.0}, ROM_2: {"ok": False}}
        diag = _diag(capabilities=["ds18b20"], sensors={"ds18b20": {"bus_ok": True, "probes": probes}})
        result = health.classify_ds18b20_bus(diag, {ROM_1, ROM_2})
        self.assertEqual(result["probes_expected"], 2)
        self.assertEqual(result["probes_ok"], 1)


if __name__ == "__main__":
    unittest.main()
