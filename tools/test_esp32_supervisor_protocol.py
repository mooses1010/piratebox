#!/usr/bin/env python3
"""
Tests for piratebox_esp32_supervisor.py (Pi-side ESP32 supervisor
daemon, 2026-09-07 - docs/ESP32-SUPERVISOR-DESIGN.md) and
piratebox_esp32_client.py (its cached-export reader).

Exercises exactly the failure modes docs/ESP32-SUPERVISOR-DESIGN.md's
"Heartbeat / failure behavior" section requires the Pi side to survive:
malformed/partial/oversized lines, an unrecognized message type from
newer firmware, a version-mismatch hello, a mid-session reboot
(uptime reset), heartbeat staleness detection, and the cached-export
reader's own degrade-to-unavailable behavior. No real serial hardware
is touched by any test here - see esp32-firmware's own PlatformIO
project for firmware-side logic, which is validated on the real
commissioned board instead (host-testing C++ built against a
memory-constrained MCU target is not attempted here - not worth the
added toolchain complexity for logic this small; the "one bad sensor/
one bad line never breaks the loop" contract is already directly
exercised on both sides of this same test suite in spirit).
"""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_esp32_supervisor as sup
import piratebox_esp32_client as client


class SelectDevicePathTests(unittest.TestCase):
    def test_exact_serial_match_is_preferred(self):
        exact = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_5CBB028993-if00"
        result = sup._select_device_path(
            "5CBB028993",
            exists_fn=lambda p: p == exact,
            glob_fn=lambda pattern: [exact, "/dev/serial/by-id/usb-other-if00"],
        )
        self.assertEqual(result["path"], exact)
        self.assertFalse(result["fallback"])
        self.assertEqual(result["ambiguous"], [])

    def test_single_fallback_candidate_used_with_flag_set(self):
        other = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_DIFFERENT-if00"
        result = sup._select_device_path(
            "5CBB028993",
            exists_fn=lambda p: False,
            glob_fn=lambda pattern: [other],
        )
        self.assertEqual(result["path"], other)
        self.assertTrue(result["fallback"])

    def test_multiple_candidates_refuses_to_guess(self):
        a = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_AAA-if00"
        b = "/dev/serial/by-id/usb-1a86_USB_Single_Serial_BBB-if00"
        result = sup._select_device_path(
            "5CBB028993",
            exists_fn=lambda p: False,
            glob_fn=lambda pattern: [a, b],
        )
        self.assertIsNone(result["path"])
        self.assertEqual(result["ambiguous"], [a, b])

    def test_nothing_present(self):
        result = sup._select_device_path(
            "5CBB028993", exists_fn=lambda p: False, glob_fn=lambda pattern: [],
        )
        self.assertIsNone(result["path"])
        self.assertFalse(result["fallback"])
        self.assertEqual(result["ambiguous"], [])


class HandleLineTests(unittest.TestCase):
    def setUp(self):
        self.state = sup.fresh_state()

    def _send(self, obj, now=1000.0):
        sup.handle_line(self.state, (json.dumps(obj) + "\n").encode("utf-8"), now)

    def test_empty_line_is_ignored_not_malformed(self):
        sup.handle_line(self.state, b"\n", 1000.0)
        self.assertEqual(self.state["malformed_lines"], 0)
        self.assertFalse(self.state["connected"])

    def test_garbage_bytes_counted_as_malformed(self):
        sup.handle_line(self.state, b"{not json at all\n", 1000.0)
        self.assertEqual(self.state["malformed_lines"], 1)
        self.assertFalse(self.state["connected"])

    def test_oversized_line_rejected(self):
        huge = b"x" * (sup.MAX_LINE_BYTES + 1)
        sup.handle_line(self.state, huge, 1000.0)
        self.assertEqual(self.state["malformed_lines"], 1)

    def test_json_array_instead_of_object_is_malformed(self):
        sup.handle_line(self.state, b"[1,2,3]\n", 1000.0)
        self.assertEqual(self.state["malformed_lines"], 1)

    def test_missing_type_field_is_malformed(self):
        self._send({"v": 1, "foo": "bar"})
        self.assertEqual(self.state["malformed_lines"], 1)

    def test_unrecognized_type_from_newer_firmware_is_ignored_not_malformed(self):
        # Forward compatibility contract: an unknown "t" must never be
        # treated as malformed - it just means this daemon is older
        # than the firmware it's talking to.
        self._send({"v": 1, "t": "future_message_type", "stuff": 123})
        self.assertEqual(self.state["malformed_lines"], 0)
        self.assertTrue(self.state["connected"])  # still counts as a live, well-formed line

    def test_hello_populates_identity(self):
        self._send({
            "v": 1, "t": "hello", "fw": "0.1.0", "board": "esp32s3-n16r8",
            "mac": "7c:4f:ad:b6:2f:94", "reset_reason": "poweron",
            "uptime_ms": 42, "caps": ["temp_internal"],
        })
        self.assertEqual(self.state["fw"], "0.1.0")
        self.assertEqual(self.state["board"], "esp32s3-n16r8")
        self.assertEqual(self.state["mac"], "7c:4f:ad:b6:2f:94")
        self.assertEqual(self.state["caps"], ["temp_internal"])
        self.assertEqual(self.state["reboot_count"], 0)  # first hello ever - not a reboot

    def test_uptime_going_backwards_after_a_known_board_is_a_reboot(self):
        self._send({"v": 1, "t": "hello", "board": "esp32s3-n16r8", "uptime_ms": 50000,
                     "fw": "0.1.0", "mac": "aa", "reset_reason": "poweron", "caps": []})
        self.assertEqual(self.state["reboot_count"], 0)
        self._send({"v": 1, "t": "hello", "board": "esp32s3-n16r8", "uptime_ms": 12,
                     "fw": "0.1.0", "mac": "aa", "reset_reason": "task_wdt", "caps": []})
        self.assertEqual(self.state["reboot_count"], 1)
        self.assertEqual(self.state["reset_reason"], "task_wdt")

    def test_heartbeat_updates_seq_and_uptime(self):
        self._send({"v": 1, "t": "hb", "seq": 5, "uptime_ms": 9000}, now=1000.0)
        self.assertEqual(self.state["last_hb_seq"], 5)
        self.assertEqual(self.state["uptime_ms"], 9000)
        self.assertEqual(self.state["last_heartbeat_monotonic"], 1000.0)

    def test_sensors_message_stores_readings(self):
        self._send({"v": 1, "t": "sensors", "seq": 1,
                     "readings": {"temp_internal": {"ok": True, "value": 34.5, "unit": "C"}}})
        self.assertEqual(self.state["sensors"]["temp_internal"]["value"], 34.5)

    def test_sensors_message_with_non_dict_readings_ignored_safely(self):
        self._send({"v": 1, "t": "sensors", "seq": 1, "readings": "not a dict"})
        self.assertEqual(self.state["sensors"], {})  # unchanged, no crash

    def test_ds18b20_multi_probe_readings_flow_through_generically(self):
        # handle_line() is intentionally generic about "readings" shape
        # (no per-capability parsing) - this pins that a real multi-probe
        # ds18b20 block round-trips exactly as sent, nesting included.
        self._send({
            "v": 1, "t": "sensors", "seq": 1,
            "readings": {
                "ds18b20": {
                    "bus_ok": True,
                    "probes": {
                        "28ff641e04170378": {"ok": True, "value": 21.4, "unit": "C"},
                        "28aa112233445566": {"ok": False, "err": "disconnected"},
                    },
                },
            },
        })
        ds18b20 = self.state["sensors"]["ds18b20"]
        self.assertTrue(ds18b20["bus_ok"])
        self.assertEqual(ds18b20["probes"]["28ff641e04170378"]["value"], 21.4)
        self.assertFalse(ds18b20["probes"]["28aa112233445566"]["ok"])

    def test_ds18b20_zero_probes_is_a_valid_distinct_state(self):
        self._send({"v": 1, "t": "sensors", "seq": 1,
                     "readings": {"ds18b20": {"bus_ok": True, "probes": {}}}})
        self.assertEqual(self.state["sensors"]["ds18b20"]["probes"], {})

    def test_hello_ds18b20_capability_present_alongside_others(self):
        self._send({"v": 1, "t": "hello", "board": "esp32s3-n16r8", "uptime_ms": 1,
                     "fw": "0.2.0", "mac": "aa", "reset_reason": "poweron",
                     "caps": ["temp_internal", "bh1750", "ds18b20"]})
        self.assertEqual(self.state["caps"], ["temp_internal", "bh1750", "ds18b20"])

    def test_err_message_recorded(self):
        self._send({"v": 1, "t": "err", "reason": "unknown_type"})
        self.assertEqual(self.state["last_remote_error"], "unknown_type")

    def test_newer_protocol_version_warns_once_but_still_reads_known_fields(self):
        self._send({"v": 99, "t": "hb", "seq": 1, "uptime_ms": 1})
        self.assertTrue(self.state["_warned_version"])
        self.assertEqual(self.state["last_hb_seq"], 1)


class StalenessTests(unittest.TestCase):
    def test_not_connected_never_flagged_stale(self):
        state = sup.fresh_state()
        sup.check_staleness(state, now=1000.0)
        self.assertFalse(state["stale"])

    def test_recent_heartbeat_is_not_stale(self):
        state = sup.fresh_state()
        state["connected"] = True
        state["last_heartbeat_monotonic"] = 1000.0
        sup.check_staleness(state, now=1002.0)
        self.assertFalse(state["stale"])

    def test_old_heartbeat_becomes_stale(self):
        state = sup.fresh_state()
        state["connected"] = True
        state["last_heartbeat_monotonic"] = 1000.0
        sup.check_staleness(state, now=1000.0 + sup.HEARTBEAT_TIMEOUT_S + 1)
        self.assertTrue(state["stale"])


class PublishExportTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._orig_dir = sup.EXPORT_DIR
        self._orig_file = sup.EXPORT_FILE
        sup.EXPORT_DIR = self._tmpdir.name + "/esp32"
        sup.EXPORT_FILE = sup.EXPORT_DIR + "/esp32-public.json"

    def tearDown(self):
        sup.EXPORT_DIR = self._orig_dir
        sup.EXPORT_FILE = self._orig_file
        self._tmpdir.cleanup()

    def _read(self):
        with open(sup.EXPORT_FILE) as f:
            return json.load(f)

    def test_writes_expected_shape(self):
        state = sup.fresh_state()
        state["connected"] = True
        state["fw"] = "0.1.0"
        state["sensors"] = {"temp_internal": {"ok": True, "value": 30.0, "unit": "C"}}
        sup.publish_export(state, 0.0, now=1000.0, now_wall=1700000000.0)
        data = self._read()
        self.assertTrue(data["connected"])
        self.assertEqual(data["fw_version"], "0.1.0")
        self.assertEqual(data["generated_at"], 1700000000)
        self.assertEqual(data["sensors"]["temp_internal"]["value"], 30.0)

    def test_ds18b20_probes_enriched_with_configured_names(self):
        state = sup.fresh_state()
        state["connected"] = True
        state["sensors"] = {
            "ds18b20": {
                "bus_ok": True,
                "probes": {
                    "28ff641e04170378": {"ok": True, "value": 21.4, "unit": "C"},
                    "28aa112233445566": {"ok": True, "value": 4.0, "unit": "C"},
                },
            },
        }
        roles = {"28ff641e04170378": {"name": "Enclosure", "assigned_at": 1.0}}
        sup.publish_export(state, 0.0, now=1000.0, ds18b20_roles=roles)
        data = self._read()
        probes = data["sensors"]["ds18b20"]["probes"]
        self.assertEqual(probes["28ff641e04170378"]["name"], "Enclosure")
        self.assertIsNone(probes["28aa112233445566"]["name"])  # unnamed, not fabricated

    def test_ds18b20_enrichment_never_mutates_the_live_state_dict(self):
        state = sup.fresh_state()
        state["sensors"] = {"ds18b20": {"bus_ok": True, "probes": {"28ff641e04170378": {"ok": True, "value": 1.0}}}}
        original_probe = state["sensors"]["ds18b20"]["probes"]["28ff641e04170378"]
        sup.publish_export(state, 0.0, now=1000.0, ds18b20_roles={"28ff641e04170378": {"name": "X"}})
        self.assertNotIn("name", original_probe)  # the live in-memory state is untouched

    def test_no_ds18b20_block_and_no_roles_publishes_cleanly(self):
        state = sup.fresh_state()
        state["sensors"] = {"temp_internal": {"ok": True, "value": 30.0}}
        sup.publish_export(state, 0.0, now=1000.0, ds18b20_roles=None)
        data = self._read()
        self.assertNotIn("ds18b20", data["sensors"])

    def test_throttled_within_publish_interval(self):
        state = sup.fresh_state()
        last = sup.publish_export(state, 0.0, now=1000.0)
        before = Path(sup.EXPORT_FILE).stat().st_mtime
        last2 = sup.publish_export(state, last, now=1000.5)
        self.assertEqual(last, last2)
        after = Path(sup.EXPORT_FILE).stat().st_mtime
        self.assertEqual(before, after)

    def test_publishes_again_after_interval(self):
        state = sup.fresh_state()
        last = sup.publish_export(state, 0.0, now=1000.0)
        last2 = sup.publish_export(state, last, now=1000.0 + sup.EXPORT_PUBLISH_INTERVAL_S + 1)
        self.assertGreater(last2, last)

    def test_disconnected_state_exports_cleanly(self):
        state = sup.fresh_state()
        sup.publish_export(state, 0.0, now=1000.0)
        data = self._read()
        self.assertFalse(data["connected"])
        self.assertEqual(data["sensors"], {})


class ClientReaderTests(unittest.TestCase):
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

    def test_missing_export_reports_not_connected(self):
        diag = client.get_diagnostics()
        self.assertFalse(diag["connected"])
        self.assertTrue(diag["stale"])

    def test_fresh_connected_export_with_good_reading(self):
        self._write({
            "generated_at": int(time.time()), "connected": True, "stale": False,
            "sensors": {"temp_internal": {"ok": True, "value": 31.2, "unit": "C"}},
            "capabilities": ["temp_internal"],
        })
        diag = client.get_diagnostics()
        self.assertTrue(diag["connected"])
        self.assertEqual(client.read_temp_internal(), 31.2)

    def test_old_generated_at_treated_as_stale_export(self):
        self._write({
            "generated_at": int(time.time()) - 999, "connected": True, "stale": False,
            "sensors": {"temp_internal": {"ok": True, "value": 31.2}},
        })
        diag = client.get_diagnostics()
        self.assertTrue(diag["stale"])
        self.assertIsNone(client.read_temp_internal())

    def test_sensor_reporting_not_ok_returns_none(self):
        self._write({
            "generated_at": int(time.time()), "connected": True, "stale": False,
            "sensors": {"temp_internal": {"ok": False, "err": "read_failed"}},
        })
        self.assertIsNone(client.read_temp_internal())

    def test_corrupt_json_degrades_cleanly(self):
        with open(client.EXPORT_FILE, "w") as f:
            f.write("{not valid json")
        diag = client.get_diagnostics()
        self.assertFalse(diag["connected"])
        self.assertIsNone(client.read_temp_internal())


if __name__ == "__main__":
    unittest.main()
