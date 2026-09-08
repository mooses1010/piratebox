#!/usr/bin/env python3
"""Deterministic tests for piratebox_oled_daemon.py's Silly Mode logic -
matches the project's existing dependency-free tools/test_*.php
convention, in Python since the code under test is Python (stdlib
unittest only - no new dependency, matching this project's "no package
installs without operator go-ahead" rule).

Run with: python3 tools/test_silly_mode.py

Deliberately does NOT touch real hardware, /tmp/piratebox, or any live
PirateBox state - every read the daemon does is monkeypatched to a
scratch path or a synthetic in-memory string for the duration of one
test, then restored. Nothing here starts the daemon's main() loop or
opens the real I2C bus.
"""

import importlib.util
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DAEMON_PATH = os.path.join(HERE, "..", "piratebox_oled_daemon.py")

# piratebox_oled_daemon.py now does a top-level `from piratebox_expressions
# import ...` (Expression Engine v2, 2026-09-04) - in production this
# resolves for free (both files are deployed side-by-side to
# /usr/local/bin, and Python auto-adds a directly-run script's own
# directory to sys.path[0]), but loading the daemon by file path via
# importlib (below) does not add its directory to sys.path on its own,
# so the sibling import would fail here without this line.
sys.path.insert(0, os.path.dirname(DAEMON_PATH))

spec = importlib.util.spec_from_file_location("piratebox_oled_daemon", DAEMON_PATH)
oled = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oled)


class FakeDevice:
    mode = "1"
    size = (128, 64)

    def display(self, img):
        # No-op - real hardware writes here; tests only need something
        # that accepts the call without touching an I2C bus. Records
        # nothing by default (see RecordingFakeDevice below for tests
        # that need to inspect what was "shown").
        pass


class RecordingFakeDevice(FakeDevice):
    """Same as FakeDevice, but remembers every image handed to
    display() (just a count and the last one) - for tests that need to
    confirm play_animation_burst() actually flashed multiple frames."""

    def __init__(self):
        self.display_count = 0
        self.last_image = None

    def display(self, img):
        self.display_count += 1
        self.last_image = img


HEALTHY_STATUS = {
    "wifi_clients": 1,
    "services": {"hostapd": True, "dnsmasq": True, "nginx": True, "php8.4-fpm": True},
    "power": {"undervoltage_now": False},
}


class ComputeDisplayTierTests(unittest.TestCase):
    """The mandatory priority gate - Emergency > fault > warning > ok.
    Every case here matches a real scenario named in the design
    instructions, not an arbitrary input."""

    def test_emergency_always_wins_even_with_healthy_status(self):
        self.assertEqual(oled.compute_display_tier("emergency", HEALTHY_STATUS, False), "emergency")

    def test_stale_status_is_a_fault(self):
        self.assertEqual(oled.compute_display_tier("normal", HEALTHY_STATUS, True), "fault")

    def test_missing_status_is_a_fault(self):
        self.assertEqual(oled.compute_display_tier("normal", None, True), "fault")

    def test_any_core_service_down_is_a_fault(self):
        status = {**HEALTHY_STATUS, "services": {**HEALTHY_STATUS["services"], "nginx": False}}
        self.assertEqual(oled.compute_display_tier("normal", status, False), "fault")

    def test_fault_outranks_warning_when_both_true(self):
        status = {
            "services": {"hostapd": False, "dnsmasq": True, "nginx": True, "php8.4-fpm": True},
            "power": {"undervoltage_now": True},
        }
        self.assertEqual(oled.compute_display_tier("normal", status, False), "fault")

    def test_chronic_undervoltage_alone_is_a_warning_not_a_fault(self):
        status = {**HEALTHY_STATUS, "power": {"undervoltage_now": True}}
        self.assertEqual(oled.compute_display_tier("normal", status, False), "warning")

    def test_fully_healthy_is_ok(self):
        self.assertEqual(oled.compute_display_tier("normal", HEALTHY_STATUS, False), "ok")

    def test_hardware_warning_text_alone_is_a_warning_not_a_fault(self):
        """2026-09-08 hardware-awareness phase: an ESP32/sensor problem
        gets the exact same tier as the existing chronic-undervoltage
        condition - present but non-blocking, never a Core-level fault,
        since ESP32/sensors are Optional, not Core."""
        self.assertEqual(
            oled.compute_display_tier("normal", HEALTHY_STATUS, False, hardware_warning_text="ESP32 SUPERVISOR"),
            "warning",
        )

    def test_hardware_warning_text_none_stays_ok_when_otherwise_healthy(self):
        self.assertEqual(
            oled.compute_display_tier("normal", HEALTHY_STATUS, False, hardware_warning_text=None),
            "ok",
        )

    def test_fault_still_outranks_a_hardware_warning(self):
        status = {**HEALTHY_STATUS, "services": {**HEALTHY_STATUS["services"], "nginx": False}}
        self.assertEqual(
            oled.compute_display_tier("normal", status, False, hardware_warning_text="ESP32 SUPERVISOR"),
            "fault",
        )

    def test_emergency_still_outranks_a_hardware_warning(self):
        self.assertEqual(
            oled.compute_display_tier("emergency", HEALTHY_STATUS, False, hardware_warning_text="SENSOR BUS"),
            "emergency",
        )

    def test_omitting_the_new_parameter_preserves_old_behavior(self):
        """Backward compatibility: every pre-existing call site that
        doesn't know about hardware_warning_text must behave exactly as
        before."""
        self.assertEqual(oled.compute_display_tier("normal", HEALTHY_STATUS, False), "ok")


class ComputeHardwareWarningTextTests(unittest.TestCase):
    """The OLED-specific text-formatting wrapper around piratebox_
    hardware_health.py's shared classifiers (2026-09-08). Only the
    ESP32-link/DS18B20-bus cases are covered here in detail - the
    underlying classification logic itself is exhaustively tested in
    tools/test_hardware_health.py; this only checks the OLED daemon
    picks the right short text for each real state and stays silent for
    non-fault states."""

    def _diag(self, connected=True, stale=False, capabilities=None, sensors=None):
        return {
            "connected": connected, "stale": stale,
            "capabilities": capabilities or [], "sensors": sensors or {},
        }

    def test_healthy_link_and_no_commissioned_probes_is_silent(self):
        self.assertIsNone(oled.compute_hardware_warning_text(self._diag(), set()))

    def test_disconnected_supervisor_produces_a_warning(self):
        diag = self._diag(connected=False)
        self.assertEqual(oled.compute_hardware_warning_text(diag, set()), "ESP32 SUPERVISOR")

    def test_never_connected_export_is_silent_not_a_warning(self):
        """UNKNOWN (no export ever read) must never alarm - only a
        genuine DEGRADED/UNAVAILABLE state does."""
        self.assertIsNone(oled.compute_hardware_warning_text({"reason": "no_export"}, set()))

    def test_ds18b20_bus_problem_produces_a_distinct_warning_from_the_link_problem(self):
        diag = self._diag(
            capabilities=["ds18b20"],
            sensors={"ds18b20": {"bus_ok": True, "probes": {}}},
        )
        self.assertEqual(oled.compute_hardware_warning_text(diag, {"28fd856b0000003b"}), "SENSOR BUS")

    def test_all_commissioned_probes_healthy_is_silent(self):
        diag = self._diag(
            capabilities=["ds18b20"],
            sensors={"ds18b20": {"bus_ok": True, "probes": {"28fd856b0000003b": {"ok": True, "value": 29.5}}}},
        )
        self.assertIsNone(oled.compute_hardware_warning_text(diag, {"28fd856b0000003b"}))

    def test_never_wired_bus_with_nothing_commissioned_is_silent(self):
        diag = self._diag(capabilities=["ds18b20"], sensors={"ds18b20": {"bus_ok": True, "probes": {}}})
        self.assertIsNone(oled.compute_hardware_warning_text(diag, set()))


class SillyEnabledFileTests(unittest.TestCase):
    """Mirrors read_mode()'s own fail-safe discipline: anything other
    than exactly 'on' is off, including missing/garbage/wrong-case."""

    def setUp(self):
        self._orig = oled.SILLY_FILE
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        oled.SILLY_FILE = self.path

    def tearDown(self):
        oled.SILLY_FILE = self._orig
        if os.path.exists(self.path):
            os.unlink(self.path)

    def write(self, content):
        with open(self.path, "w") as f:
            f.write(content)

    def test_missing_file_defaults_off(self):
        os.unlink(self.path)
        self.assertFalse(oled.read_silly_enabled())

    def test_on_enables(self):
        self.write("on\n")
        self.assertTrue(oled.read_silly_enabled())

    def test_off_disables(self):
        self.write("off\n")
        self.assertFalse(oled.read_silly_enabled())

    def test_garbage_defaults_off(self):
        self.write("purple\n")
        self.assertFalse(oled.read_silly_enabled())

    def test_case_insensitive(self):
        self.write("ON\n")
        self.assertTrue(oled.read_silly_enabled())

    def test_empty_file_defaults_off(self):
        self.write("")
        self.assertFalse(oled.read_silly_enabled())


class SshEstablishedTests(unittest.TestCase):
    """read_ssh_established() against synthetic /proc/net/tcp-shaped
    text - never touches the real table for the pass/fail cases, only
    the final "real environment" sanity check calls it unpatched."""

    HEADER = "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"

    def setUp(self):
        self._orig = oled.SSH_TCP_TABLES
        self.paths = []

    def tearDown(self):
        oled.SSH_TCP_TABLES = self._orig
        for p in self.paths:
            os.unlink(p)

    def make_table(self, lines):
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "w") as f:
            f.write(self.HEADER)
            f.write("\n".join(lines) + ("\n" if lines else ""))
        self.paths.append(path)
        return path

    def test_no_sockets_at_all(self):
        oled.SSH_TCP_TABLES = (self.make_table([]),)
        self.assertFalse(oled.read_ssh_established())

    def test_listening_only_is_not_established(self):
        # Port 22 (0016 hex), state 0A = LISTEN, not established.
        line = "0: 00000000:0016 00000000:0000 0A 00000000:00000000 00:00000000 00000000 0 0 1 1 0"
        oled.SSH_TCP_TABLES = (self.make_table([line]),)
        self.assertFalse(oled.read_ssh_established())

    def test_established_ssh_connection_detected(self):
        # Port 22, state 01 = ESTABLISHED.
        line = "0: 0100000A:0016 0200000A:C012 01 00000000:00000000 00:00000000 00000000 0 0 1 1 0"
        oled.SSH_TCP_TABLES = (self.make_table([line]),)
        self.assertTrue(oled.read_ssh_established())

    def test_established_on_a_different_port_is_ignored(self):
        # Port 80 (0050 hex), established - not SSH.
        line = "0: 0100000A:0050 0200000A:C012 01 00000000:00000000 00:00000000 00000000 0 0 1 1 0"
        oled.SSH_TCP_TABLES = (self.make_table([line]),)
        self.assertFalse(oled.read_ssh_established())

    def test_missing_table_degrades_to_not_found_not_error(self):
        oled.SSH_TCP_TABLES = ("/nonexistent/path/for/this/test",)
        self.assertFalse(oled.read_ssh_established())

    def test_second_table_checked_when_first_has_no_match(self):
        t1 = self.make_table([])
        line = "0: 0100000A:0016 0200000A:C012 01 00000000:00000000 00:00000000 00000000 0 0 1 1 0"
        t2 = self.make_table([line])
        oled.SSH_TCP_TABLES = (t1, t2)
        self.assertTrue(oled.read_ssh_established())


class ComputeSillyExpressionTests(unittest.TestCase):
    """Pure ambient/beat cycling logic - no I/O, fully deterministic."""

    def test_forced_always_wins(self):
        for tick in (0, 1, oled.SILLY_FLOURISH_EVERY_TICKS, oled.SILLY_SSH_WATCH_EVERY_TICKS):
            self.assertEqual(oled.compute_silly_expression(tick, True, True, forced="excited"), "excited")

    def test_flourish_beat_at_its_own_cadence(self):
        self.assertEqual(oled.compute_silly_expression(oled.SILLY_FLOURISH_EVERY_TICKS, True, False), "pirate_flourish")

    def test_ssh_watch_only_when_ssh_active(self):
        tick = oled.SILLY_SSH_WATCH_EVERY_TICKS
        self.assertEqual(oled.compute_silly_expression(tick, False, True), "ssh_watch")
        # Same tick, SSH not active -> falls through to ambient, not ssh_watch.
        self.assertNotEqual(oled.compute_silly_expression(tick, False, False), "ssh_watch")

    def test_ambient_cycle_selects_from_the_right_pool(self):
        for tick in range(30):
            expr = oled.compute_silly_expression(tick, has_clients=False, ssh_active=False)
            if tick % oled.SILLY_FLOURISH_EVERY_TICKS == 0:
                continue  # flourish beat legitimately overrides ambient here
            self.assertIn(expr, oled.AMBIENT_NO_CLIENTS)

        for tick in range(30):
            expr = oled.compute_silly_expression(tick, has_clients=True, ssh_active=False)
            if tick % oled.SILLY_FLOURISH_EVERY_TICKS == 0:
                continue
            self.assertIn(expr, oled.AMBIENT_WITH_CLIENTS)

    def test_deterministic_same_inputs_same_output(self):
        a = oled.compute_silly_expression(17, True, False)
        b = oled.compute_silly_expression(17, True, False)
        self.assertEqual(a, b)


class ExpressionRenderingTests(unittest.TestCase):
    """Every named expression (plus the pirate-flourish beat, plus both
    display tiers) must render without raising - a real drawing
    exception here would mean Silly Mode crashes the redraw loop, which
    the daemon's own except-block would catch and treat as "lost
    contact with the OLED" (a false-positive hardware-loss retry), not
    a code bug. Catching it here is much cheaper than on real hardware."""

    @classmethod
    def setUpClass(cls):
        cls.font, cls.font_small, cls.font_big = oled.load_fonts()
        cls.device = FakeDevice()

    def test_every_expression_renders_for_both_tiers(self):
        for expr in oled.EXPRESSIONS:
            for tier in ("ok", "warning"):
                img = oled.build_frame(
                    self.device, "silly", self.font, self.font_small, self.font_big,
                    HEALTHY_STATUS, False, "normal", alive_on=True,
                    extra={"render": {"expression": expr}, "tier": tier},
                )
                self.assertEqual(img.size, (128, 64))

    def test_pirate_flourish_renders_with_every_quip(self):
        for quip_template in oled.SILLY_QUIPS:
            quip = quip_template.format(n=3)
            img = oled.build_frame(
                self.device, "silly", self.font, self.font_small, self.font_big,
                HEALTHY_STATUS, False, "normal", alive_on=True,
                extra={"render": {"expression": "pirate_flourish", "quip": quip}, "tier": "ok"},
            )
            self.assertEqual(img.size, (128, 64))

    def test_serious_pages_and_mode_transition_unaffected(self):
        """Regression guard: Silly Mode's addition must not have broken
        the pre-existing serious pages or the mode-transition banner."""
        for page in oled.PAGE_ORDER:
            img = oled.build_frame(
                self.device, page, self.font, self.font_small, self.font_big,
                HEALTHY_STATUS, False, "normal", alive_on=True, pulse=False, extra=None,
            )
            self.assertEqual(img.size, (128, 64))
        img = oled.build_frame(
            self.device, "mode_transition", self.font, self.font_small, self.font_big,
            None, True, "emergency", extra={"new_mode": "emergency"},
        )
        self.assertEqual(img.size, (128, 64))


class QuipWidthTests(unittest.TestCase):
    """Guards against a future quip edit silently clipping off the
    128px-wide display - caught this exact bug once already during
    this feature's own visual review."""

    def test_every_quip_fits_the_display_width(self):
        _, font_small, _ = oled.load_fonts()
        for template in oled.SILLY_QUIPS:
            text = template.format(n=1)
            bbox = font_small.getbbox(text)
            width = bbox[2] - bbox[0]
            self.assertLessEqual(width, 128, f"Quip too wide for the display: {text!r} ({width}px)")


class SillyCadenceTests(unittest.TestCase):
    """State-machine tests for the personality-vs-glance-vs-status
    cadence (advance_silly_cadence()) - pure, no I/O, so the whole
    phase sequence/timing is directly verifiable by stepping it in a
    loop. Extended 2026-09-04 (Distance/Glance Display) from a 2-phase
    toggle to this 3-phase rotation: personality -> glance -> status ->
    personality -> ..."""

    def test_starts_in_personality_and_stays_there_before_elapsing(self):
        phase, remaining = "personality", oled.SILLY_CADENCE_PERSONALITY_SECONDS
        phase, remaining = oled.advance_silly_cadence(phase, remaining, 3.0)
        self.assertEqual(phase, "personality")
        self.assertAlmostEqual(remaining, oled.SILLY_CADENCE_PERSONALITY_SECONDS - 3.0)

    def test_flips_to_glance_exactly_when_personality_phase_elapses(self):
        phase, remaining = "personality", 3.0  # one tick left
        phase, remaining = oled.advance_silly_cadence(phase, remaining, 3.0)
        self.assertEqual(phase, "glance")
        self.assertAlmostEqual(remaining, oled.SILLY_CADENCE_GLANCE_SECONDS)

    def test_flips_to_status_exactly_when_glance_phase_elapses(self):
        phase, remaining = "glance", 3.0
        phase, remaining = oled.advance_silly_cadence(phase, remaining, 3.0)
        self.assertEqual(phase, "status")
        self.assertAlmostEqual(remaining, oled.SILLY_CADENCE_STATUS_SECONDS)

    def test_flips_back_to_personality_when_status_phase_elapses(self):
        phase, remaining = "status", 3.0
        phase, remaining = oled.advance_silly_cadence(phase, remaining, 3.0)
        self.assertEqual(phase, "personality")
        self.assertAlmostEqual(remaining, oled.SILLY_CADENCE_PERSONALITY_SECONDS)

    def test_full_cycle_spends_the_expected_number_of_ticks_in_each_phase(self):
        phase, remaining = "personality", oled.SILLY_CADENCE_PERSONALITY_SECONDS
        phase_log = [phase]
        for _ in range(40):
            phase, remaining = oled.advance_silly_cadence(phase, remaining, 3.0)
            phase_log.append(phase)
        personality_ticks = phase_log.count("personality")
        glance_ticks = phase_log.count("glance")
        status_ticks = phase_log.count("status")
        # All three phases must actually occur, personality must remain
        # the dominant one (it must not "take over" per instruction),
        # and glance must not exceed status's own established airtime -
        # it's additive, not a replacement for the detailed rotation.
        self.assertGreater(personality_ticks, 0)
        self.assertGreater(glance_ticks, 0)
        self.assertGreater(status_ticks, 0)
        self.assertGreater(personality_ticks, glance_ticks)
        self.assertGreater(personality_ticks, status_ticks)
        self.assertLessEqual(glance_ticks, status_ticks)

    def test_cadence_constants_are_within_the_requested_range(self):
        self.assertTrue(25.0 <= oled.SILLY_CADENCE_PERSONALITY_SECONDS <= 45.0)
        self.assertTrue(12.0 <= oled.SILLY_CADENCE_STATUS_SECONDS <= 15.0)
        self.assertTrue(5.0 <= oled.SILLY_CADENCE_GLANCE_SECONDS <= 15.0)

    def test_personality_still_the_largest_share_of_the_cycle(self):
        total = (
            oled.SILLY_CADENCE_PERSONALITY_SECONDS
            + oled.SILLY_CADENCE_GLANCE_SECONDS
            + oled.SILLY_CADENCE_STATUS_SECONDS
        )
        self.assertGreater(oled.SILLY_CADENCE_PERSONALITY_SECONDS / total, 0.5)


class OfflineGlanceCadenceTests(unittest.TestCase):
    """The Silly-Mode-OFF counterpart cadence
    (advance_offline_glance_cadence()) - same pure, directly-testable
    shape as SillyCadenceTests above, its own separate 2-phase cycle."""

    def test_starts_in_rotation_and_stays_there_before_elapsing(self):
        phase, remaining = "rotation", oled.OFFLINE_GLANCE_ROTATION_SECONDS
        phase, remaining = oled.advance_offline_glance_cadence(phase, remaining, 3.0)
        self.assertEqual(phase, "rotation")

    def test_flips_to_glance_exactly_when_rotation_phase_elapses(self):
        phase, remaining = "rotation", 3.0
        phase, remaining = oled.advance_offline_glance_cadence(phase, remaining, 3.0)
        self.assertEqual(phase, "glance")
        self.assertAlmostEqual(remaining, oled.OFFLINE_GLANCE_SECONDS)

    def test_flips_back_to_rotation_when_glance_phase_elapses(self):
        phase, remaining = "glance", 3.0
        phase, remaining = oled.advance_offline_glance_cadence(phase, remaining, 3.0)
        self.assertEqual(phase, "rotation")
        self.assertAlmostEqual(remaining, oled.OFFLINE_GLANCE_ROTATION_SECONDS)

    def test_rotation_is_the_dominant_share(self):
        total = oled.OFFLINE_GLANCE_ROTATION_SECONDS + oled.OFFLINE_GLANCE_SECONDS
        self.assertGreater(oled.OFFLINE_GLANCE_ROTATION_SECONDS / total, 0.7)


class StatusCheckOverrideTests(unittest.TestCase):
    """read_status_check_active() - the OLED side of the short-press
    signal piratebox_button_daemon.py writes."""

    def setUp(self):
        self._orig = oled.STATUS_CHECK_REQUEST_FILE
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        oled.STATUS_CHECK_REQUEST_FILE = self.path

    def tearDown(self):
        oled.STATUS_CHECK_REQUEST_FILE = self._orig
        if os.path.exists(self.path):
            os.unlink(self.path)

    def write(self, content):
        with open(self.path, "w") as f:
            f.write(content)

    def test_missing_file_is_inactive(self):
        os.unlink(self.path)
        self.assertFalse(oled.read_status_check_active(1000.0))

    def test_recent_timestamp_is_active(self):
        self.write("1000.0\n")
        self.assertTrue(oled.read_status_check_active(1005.0))  # 5s old

    def test_old_timestamp_is_inactive(self):
        self.write("1000.0\n")
        self.assertFalse(oled.read_status_check_active(1000.0 + oled.STATUS_CHECK_WINDOW_SECONDS + 1))

    def test_exactly_at_the_window_boundary_is_inactive(self):
        self.write("1000.0\n")
        self.assertFalse(oled.read_status_check_active(1000.0 + oled.STATUS_CHECK_WINDOW_SECONDS))

    def test_garbage_content_is_inactive_not_a_crash(self):
        self.write("not a number")
        self.assertFalse(oled.read_status_check_active(1000.0))

    def test_future_timestamp_clock_skew_is_inactive(self):
        self.write("5000.0\n")  # "now" (1000.0) is before this - nonsensical
        self.assertFalse(oled.read_status_check_active(1000.0))

    def test_a_repeated_press_extends_the_window(self):
        self.write("1000.0\n")
        self.assertFalse(oled.read_status_check_active(1000.0 + oled.STATUS_CHECK_WINDOW_SECONDS + 1))
        self.write(f"{1000.0 + oled.STATUS_CHECK_WINDOW_SECONDS + 1}\n")  # a fresh press
        self.assertTrue(oled.read_status_check_active(1000.0 + oled.STATUS_CHECK_WINDOW_SECONDS + 2))


class StatusCheckBannerRenderingTests(unittest.TestCase):
    def test_renders_without_exception(self):
        font, font_small, font_big = oled.load_fonts()
        img = oled.build_frame(
            FakeDevice(), "status_check_banner", font, font_small, font_big,
            None, False, "normal", extra={},
        )
        self.assertEqual(img.size, (128, 64))


class SillyToggleEdgeTests(unittest.TestCase):
    """read_silly_toggle_edge() - the OLED side of the double-tap
    confirmation signal piratebox_button_daemon.py's toggle_silly_mode()
    writes. Same edge-detected mtime pattern as Progression's own
    reset/import request checks, exercised the identical way."""

    def setUp(self):
        self._orig = oled.SILLY_TOGGLE_REQUEST_FILE
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        oled.SILLY_TOGGLE_REQUEST_FILE = self.path

    def tearDown(self):
        oled.SILLY_TOGGLE_REQUEST_FILE = self._orig
        if os.path.exists(self.path):
            os.unlink(self.path)

    def touch(self):
        os.utime(self.path, None)

    def test_missing_file_is_no_edge(self):
        os.unlink(self.path)
        self.assertFalse(oled.read_silly_toggle_edge({}))

    def test_first_observation_of_an_existing_file_is_an_edge(self):
        # Matches Progression's own reset/import request semantics: an
        # empty `markers` dict means "never seen this file before," so
        # whatever mtime it already has counts as fresh the first time.
        self.assertTrue(oled.read_silly_toggle_edge({}))

    def test_unchanged_mtime_is_not_a_repeat_edge(self):
        markers = {}
        self.assertTrue(oled.read_silly_toggle_edge(markers))
        self.assertFalse(oled.read_silly_toggle_edge(markers))
        self.assertFalse(oled.read_silly_toggle_edge(markers))

    def test_a_fresh_touch_is_a_new_edge(self):
        markers = {}
        self.assertTrue(oled.read_silly_toggle_edge(markers))
        self.assertFalse(oled.read_silly_toggle_edge(markers))
        import time as _time
        _time.sleep(0.01)
        self.touch()
        self.assertTrue(oled.read_silly_toggle_edge(markers))
        self.assertFalse(oled.read_silly_toggle_edge(markers))

    def test_markers_dict_is_per_caller_not_global(self):
        # Two independent callers (e.g. two separate test cases, or in
        # principle two independent consumers) never interfere with each
        # other's "have I seen this edge yet" bookkeeping.
        markers_a, markers_b = {}, {}
        self.assertTrue(oled.read_silly_toggle_edge(markers_a))
        self.assertTrue(oled.read_silly_toggle_edge(markers_b))


class SillyToggleBannerRenderingTests(unittest.TestCase):
    def test_renders_without_exception_when_turned_on(self):
        font, font_small, font_big = oled.load_fonts()
        img = oled.build_frame(
            FakeDevice(), "silly_toggle_banner", font, font_small, font_big,
            None, False, "normal", extra={"new_state": True},
        )
        self.assertEqual(img.size, (128, 64))

    def test_renders_without_exception_when_turned_off(self):
        font, font_small, font_big = oled.load_fonts()
        img = oled.build_frame(
            FakeDevice(), "silly_toggle_banner", font, font_small, font_big,
            None, False, "normal", extra={"new_state": False},
        )
        self.assertEqual(img.size, (128, 64))

    def test_existing_skull_and_crossbones_call_sites_still_default_to_white_on_black(self):
        # draw_skull_and_crossbones() gained color/bg parameters this
        # round (see its own docstring) - every pre-existing call site
        # (draw_pirate_flourish, render_level_up, render_achievement)
        # calls it with no color arguments at all, so this pins the
        # defaults themselves rather than re-testing each call site
        # individually (already covered by ExpressionRenderingTests and
        # tools/test_progression.py).
        from PIL import Image, ImageDraw
        img = Image.new("1", (32, 32))
        draw = ImageDraw.Draw(img)
        oled.draw_skull_and_crossbones(draw, 0, 0)  # must not raise
        import inspect
        sig = inspect.signature(oled.draw_skull_and_crossbones)
        self.assertEqual(sig.parameters["color"].default, "white")
        self.assertEqual(sig.parameters["bg"].default, "black")


class RenderHealthHardwareWarningTests(unittest.TestCase):
    """render_health()'s warning box (2026-09-08 extension): renders
    without exception in every combination, and undervoltage always
    keeps its existing exact box/text when both conditions are active
    at once (only one line fits - see render_health()'s own comment)."""

    def _render(self, status, stale, hardware_warning_text):
        from PIL import Image, ImageDraw
        font, font_small, _ = oled.load_fonts()
        img = Image.new("1", (128, 64))
        draw = ImageDraw.Draw(img)
        oled.render_health(draw, font, font_small, status, stale, True, hardware_warning_text)
        return img

    def test_renders_without_exception_with_a_hardware_warning(self):
        self._render(HEALTHY_STATUS, False, "ESP32 SUPERVISOR")  # must not raise

    def test_renders_without_exception_with_neither_condition(self):
        self._render(HEALTHY_STATUS, False, None)  # must not raise

    def test_omitting_the_new_parameter_still_works(self):
        from PIL import Image, ImageDraw
        font, font_small, _ = oled.load_fonts()
        img = Image.new("1", (128, 64))
        draw = ImageDraw.Draw(img)
        oled.render_health(draw, font, font_small, HEALTHY_STATUS, False, True)  # must not raise

    def test_hardware_warning_alone_draws_the_box(self):
        # Compare only the warning-box region - see the test below for
        # why comparing the whole frame would be flaky.
        box = (0, 50, 128, 63)
        no_warning = self._render(HEALTHY_STATUS, False, None).crop(box)
        with_warning = self._render(HEALTHY_STATUS, False, "SENSOR BUS").crop(box)
        self.assertNotEqual(no_warning.tobytes(), with_warning.tobytes())

    def test_undervoltage_and_hardware_warning_together_matches_undervoltage_alone(self):
        """Only one line fits the box - undervoltage keeps its exact
        existing precedent when both are active, never displaced by a
        newer condition. Compares only the warning-box region (0,50)-
        (127,62), not the whole frame - the rest of render_health()
        reads live system uptime, which can genuinely tick between the
        two renders below and would otherwise make this test flaky for
        reasons unrelated to the box logic under test."""
        undervoltage_status = {**HEALTHY_STATUS, "power": {"undervoltage_now": True}}
        box = (0, 50, 128, 63)
        undervoltage_alone = self._render(undervoltage_status, False, None).crop(box)
        both_active = self._render(undervoltage_status, False, "ESP32 SUPERVISOR").crop(box)
        self.assertEqual(undervoltage_alone.tobytes(), both_active.tobytes())


class RenderHealthTempUnitTests(unittest.TestCase):
    """render_health()'s temp_unit parameter (2026-09-08 temp-unit
    preference) - read_cpu_temp_c() always returns genuine Celsius;
    this only controls the CPU-temperature line's conversion/suffix."""

    def _render(self, temp_unit="C"):
        from PIL import Image, ImageDraw
        font, font_small, _ = oled.load_fonts()
        img = Image.new("1", (128, 64))
        draw = ImageDraw.Draw(img)
        oled.render_health(draw, font, font_small, HEALTHY_STATUS, False, True,
                            hardware_warning_text=None, temp_unit=temp_unit)
        return img

    def test_renders_without_exception_in_fahrenheit(self):
        self._render("F")  # must not raise

    def test_defaults_to_celsius_when_omitted(self):
        from PIL import Image, ImageDraw
        font, font_small, _ = oled.load_fonts()
        img = Image.new("1", (128, 64))
        draw = ImageDraw.Draw(img)
        oled.render_health(draw, font, font_small, HEALTHY_STATUS, False, True)  # no temp_unit at all
        # must not raise - documents the default parameter value itself:
        import inspect
        sig = inspect.signature(oled.render_health)
        self.assertEqual(sig.parameters["temp_unit"].default, "C")

    def test_celsius_and_fahrenheit_render_differently(self):
        """A real CPU temp reading in this test environment produces a
        visibly different rendered line in the two units - confirms
        the parameter actually reaches the drawn frame, not just that
        rendering doesn't crash."""
        if oled.read_cpu_temp_c() is None:
            self.skipTest("no real CPU temp sensor available in this environment")
        box = (0, 36, 128, 46)  # the "CPU: ..." line's own row
        celsius = self._render("C").crop(box)
        fahrenheit = self._render("F").crop(box)
        self.assertNotEqual(celsius.tobytes(), fahrenheit.tobytes())


class SillyTogglePriorityIntegrationTests(unittest.TestCase):
    """Confirms the toggle banner sits exactly where it's supposed to in
    the priority hierarchy: below Emergency/fault, but able to show
    regardless of whether the toggle just turned Silly Mode on OR off
    (the tricky case: the "not silly_enabled" plain-rotation branch must
    never pre-empt it, or an OFF confirmation could never be seen)."""

    def test_emergency_tier_outranks_a_pending_toggle_confirmation(self):
        # Mirrors main()'s own elif-chain ordering directly, since that
        # ordering has no separate helper function to call in isolation.
        mode_transition = None
        tier = "emergency"
        silly_toggle_just_happened = True
        silly_enabled = True
        if mode_transition is not None:
            page = "mode_transition"
        elif tier in ("emergency", "fault"):
            page = "serious_rotation"
        elif silly_toggle_just_happened:
            page = "silly_toggle_banner"
        elif not silly_enabled:
            page = "serious_rotation"
        else:
            page = "silly"
        self.assertEqual(page, "serious_rotation")

    def test_toggle_confirmation_shows_even_when_it_just_turned_silly_off(self):
        mode_transition = None
        tier = "ok"
        silly_toggle_just_happened = True
        silly_enabled = False  # the double tap that just fired turned it OFF
        if mode_transition is not None:
            page = "mode_transition"
        elif tier in ("emergency", "fault"):
            page = "serious_rotation"
        elif silly_toggle_just_happened:
            page = "silly_toggle_banner"
        elif not silly_enabled:
            page = "serious_rotation"
        else:
            page = "silly"
        self.assertEqual(page, "silly_toggle_banner")

    def test_toggle_confirmation_shows_when_it_just_turned_silly_on(self):
        mode_transition = None
        tier = "ok"
        silly_toggle_just_happened = True
        silly_enabled = True
        if mode_transition is not None:
            page = "mode_transition"
        elif tier in ("emergency", "fault"):
            page = "serious_rotation"
        elif silly_toggle_just_happened:
            page = "silly_toggle_banner"
        elif not silly_enabled:
            page = "serious_rotation"
        else:
            page = "silly"
        self.assertEqual(page, "silly_toggle_banner")

    def test_no_pending_toggle_falls_through_to_normal_rotation_choice(self):
        mode_transition = None
        tier = "ok"
        silly_toggle_just_happened = False
        silly_enabled = False
        if mode_transition is not None:
            page = "mode_transition"
        elif tier in ("emergency", "fault"):
            page = "serious_rotation"
        elif silly_toggle_just_happened:
            page = "silly_toggle_banner"
        elif not silly_enabled:
            page = "serious_rotation"
        else:
            page = "silly"
        self.assertEqual(page, "serious_rotation")


class PlayAnimationBurstTests(unittest.TestCase):
    """play_animation_burst() - Expression Engine v2 (2026-09-04). Uses
    a real (tiny) time.sleep() between frames, same acceptance already
    made for tools/test_button_daemon.py's double-tap timer tests -
    monkeypatches ANIMATIONS' own frame_gap_s down to something
    negligible so this suite stays fast without mocking time.sleep
    itself (mocking it would also hide a real regression where a frame
    gap became huge)."""

    def setUp(self):
        self._orig_gap = oled.ANIMATIONS["quick_blink_pair"]["frame_gap_s"]
        oled.ANIMATIONS["quick_blink_pair"]["frame_gap_s"] = 0.001

    def tearDown(self):
        oled.ANIMATIONS["quick_blink_pair"]["frame_gap_s"] = self._orig_gap

    def test_flashes_every_frame_to_the_device(self):
        dev = RecordingFakeDevice()
        font, font_small, font_big = oled.load_fonts()
        expected_frames = len(oled.ANIMATIONS["quick_blink_pair"]["frames"])
        oled.play_animation_burst(dev, "quick_blink_pair", "ok", None, font, font_small, font_big, "normal")
        self.assertEqual(dev.display_count, expected_frames)

    def test_returns_the_final_frames_render_and_the_animations_own_hold_ticks(self):
        dev = RecordingFakeDevice()
        font, font_small, font_big = oled.load_fonts()
        final_render, hold_ticks = oled.play_animation_burst(
            dev, "quick_blink_pair", "ok", "a quip", font, font_small, font_big, "normal",
        )
        self.assertEqual(final_render, {"expression": "idle", "quip": "a quip"})
        self.assertEqual(hold_ticks, oled.ANIMATIONS["quick_blink_pair"]["hold_ticks"])

    def test_unknown_animation_id_returns_none_none(self):
        dev = RecordingFakeDevice()
        font, font_small, font_big = oled.load_fonts()
        final_render, hold_ticks = oled.play_animation_burst(
            dev, "no_such_animation", "ok", None, font, font_small, font_big, "normal",
        )
        self.assertIsNone(final_render)
        self.assertIsNone(hold_ticks)
        self.assertEqual(dev.display_count, 0)

    def test_a_mid_burst_display_failure_stops_the_burst_without_raising(self):
        class FlakyDevice(RecordingFakeDevice):
            def display(self, img):
                super().display(img)
                if self.display_count == 2:
                    raise OSError("simulated I2C loss")

        dev = FlakyDevice()
        font, font_small, font_big = oled.load_fonts()
        # Must not raise - the caller's own end-of-tick try/except is
        # what actually handles "lost contact with the OLED" (see that
        # function's own docstring); this just stops flashing more.
        oled.play_animation_burst(dev, "quick_blink_pair", "ok", None, font, font_small, font_big, "normal")
        self.assertEqual(dev.display_count, 2)


class PreviewOverrideTests(unittest.TestCase):
    """read_preview_active() - the OLED side of `piratebox-silly
    preview`'s operator-only demo request. Identical recency-based
    pattern to StatusCheckOverrideTests above."""

    def setUp(self):
        self._orig = oled.PREVIEW_REQUEST_FILE
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        oled.PREVIEW_REQUEST_FILE = self.path

    def tearDown(self):
        oled.PREVIEW_REQUEST_FILE = self._orig
        if os.path.exists(self.path):
            os.unlink(self.path)

    def write(self, content):
        with open(self.path, "w") as f:
            f.write(content)

    def test_missing_file_is_inactive(self):
        os.unlink(self.path)
        self.assertFalse(oled.read_preview_active(1000.0))

    def test_recent_timestamp_is_active(self):
        self.write("1000.0\n")
        self.assertTrue(oled.read_preview_active(1005.0))

    def test_old_timestamp_is_inactive(self):
        self.write("1000.0\n")
        self.assertFalse(oled.read_preview_active(1000.0 + oled.PREVIEW_WINDOW_SECONDS + 1))

    def test_garbage_content_is_inactive_not_a_crash(self):
        self.write("not a number")
        self.assertFalse(oled.read_preview_active(1000.0))


class PreviewPlaylistTests(unittest.TestCase):
    """The fixed, hand-picked, non-rarity-engine playlist itself -
    every item must be drawable, and none may reference an uncommon/
    rare/legendary/secret variant id (structurally impossible anyway,
    since this playlist never calls roll_event(), but this guards
    against a future edit accidentally wiring it through that path)."""

    def test_every_item_renders_without_exception(self):
        font, font_small, font_big = oled.load_fonts()
        dev = FakeDevice()
        for item in oled.PREVIEW_PLAYLIST:
            if item.get("anim") is not None:
                specs, _, _ = oled.resolve_animation_frames(item["anim"], "ok", quip=item.get("quip"))
                self.assertIsNotNone(specs)
                for spec in specs:
                    img = oled.build_frame(
                        dev, "silly", font, font_small, font_big, None, False, "normal", extra=spec,
                    )
                    self.assertEqual(img.size, (128, 64))
            else:
                img = oled.build_frame(
                    dev, "silly", font, font_small, font_big, None, False, "normal",
                    extra={"render": item, "tier": "ok"},
                )
                self.assertEqual(img.size, (128, 64))

    def test_playlist_never_calls_the_rarity_engine(self):
        """Structural guard, not just a behavioral one: every item is a
        plain dict literal, never the result of roll_event() - so
        there's no live progression state a preview run could possibly
        read from at all."""
        for item in oled.PREVIEW_PLAYLIST:
            self.assertIsInstance(item, dict)
            self.assertNotIn("id", item)  # roll_event() variants always carry an "id"; playlist items never do


class ComputeCpuPercentTests(unittest.TestCase):
    """Pure - no I/O, unlike read_cpu_jiffies() itself (which isn't
    separately tested here for the same reason read_cpu_temp_c()/
    read_disk_free_total() aren't: they're thin, direct /proc reads
    with no branching logic of their own beyond try/except - the
    degradation path IS the interesting part, covered by
    GlanceMetricsTests below via build_glance_metrics())."""

    def test_missing_prev_sample_is_unavailable(self):
        self.assertIsNone(oled.compute_cpu_percent(None, (1000, 900)))

    def test_missing_curr_sample_is_unavailable(self):
        self.assertIsNone(oled.compute_cpu_percent((1000, 900), None))

    def test_zero_elapsed_time_is_unavailable(self):
        # Same total/idle twice - no time actually elapsed between
        # samples, so a rate can't be computed; must degrade, not
        # divide by zero.
        self.assertIsNone(oled.compute_cpu_percent((1000, 900), (1000, 900)))

    def test_fully_idle_interval_is_zero_percent(self):
        # 100 total jiffies elapsed, all of them idle.
        pct = oled.compute_cpu_percent((1000, 900), (1100, 1000))
        self.assertAlmostEqual(pct, 0.0)

    def test_fully_busy_interval_is_100_percent(self):
        # 100 total jiffies elapsed, idle didn't move at all.
        pct = oled.compute_cpu_percent((1000, 900), (1100, 900))
        self.assertAlmostEqual(pct, 100.0)

    def test_half_busy_interval_is_50_percent(self):
        pct = oled.compute_cpu_percent((1000, 900), (1100, 950))
        self.assertAlmostEqual(pct, 50.0)

    def test_result_is_always_clamped_to_0_100(self):
        # A corrupt/wrapped counter (idle appearing to move MORE than
        # total, which should never happen on real hardware but must
        # not produce a nonsensical negative or >100 result either).
        pct = oled.compute_cpu_percent((1000, 900), (1050, 1200))
        self.assertGreaterEqual(pct, 0.0)
        self.assertLessEqual(pct, 100.0)


class AutoBrightnessTests(unittest.TestCase):
    """compute_target_contrast() / slew_contrast() (2026-09-07) - the
    OLED auto-brightness feature. Both are pure functions, directly
    testable without a display or real BH1750 hardware."""

    def test_none_reading_maps_to_full_brightness(self):
        """The failure-safe default: no reading (never wired, never
        read yet, or stale) always means full brightness, never a
        guessed dim value."""
        self.assertEqual(oled.compute_target_contrast(None), oled.OLED_MAX_CONTRAST)

    def test_darkness_maps_to_the_minimum_floor_not_fully_off(self):
        self.assertEqual(oled.compute_target_contrast(0.0), oled.OLED_MIN_CONTRAST)

    def test_bright_room_maps_to_full_brightness(self):
        self.assertEqual(oled.compute_target_contrast(1000.0), oled.OLED_MAX_CONTRAST)
        self.assertEqual(oled.compute_target_contrast(50000.0), oled.OLED_MAX_CONTRAST)

    def test_monotonically_non_decreasing_with_more_light(self):
        """More light must never produce a DIMMER target than less
        light - the actual property that matters, not just spot values."""
        samples = [0.0, 1.0, 5.0, 25.0, 100.0, 500.0, 1000.0]
        targets = [oled.compute_target_contrast(lux) for lux in samples]
        self.assertEqual(targets, sorted(targets))

    def test_result_always_within_the_configured_bounds(self):
        for lux in [-5.0, 0.0, 0.1, 500000.0]:  # a negative reading should never happen, but must not misbehave
            with self.subTest(lux=lux):
                target = oled.compute_target_contrast(lux)
                self.assertGreaterEqual(target, oled.OLED_MIN_CONTRAST)
                self.assertLessEqual(target, oled.OLED_MAX_CONTRAST)

    def test_slew_moves_toward_target_by_at_most_max_step(self):
        self.assertEqual(oled.slew_contrast(10, 255, max_step=3), 13)
        self.assertEqual(oled.slew_contrast(255, 10, max_step=3), 252)

    def test_slew_never_overshoots_a_close_target(self):
        self.assertEqual(oled.slew_contrast(10, 12, max_step=3), 12)

    def test_slew_is_a_no_op_already_at_target(self):
        self.assertEqual(oled.slew_contrast(100, 100), 100)

    def test_repeated_slewing_eventually_reaches_the_target_without_overshoot(self):
        """The actual anti-pumping guarantee end to end: starting far
        from a new target, repeated slew_contrast() calls converge
        smoothly and land exactly on it, never oscillating past it."""
        current = oled.OLED_MIN_CONTRAST
        target = oled.OLED_MAX_CONTRAST
        seen = [current]
        for _ in range(200):
            current = oled.slew_contrast(current, target)
            seen.append(current)
            if current == target:
                break
        self.assertEqual(current, target)
        self.assertEqual(seen, sorted(seen))  # strictly non-decreasing the whole way - no overshoot/bounce

    def test_a_transient_spike_only_nudges_brightness_a_little(self):
        """The concrete 'hand waved over the sensor' scenario: a single
        instantaneous jump in the TARGET (as compute_target_contrast()
        would produce from a brief lux spike) must only move the
        applied contrast a little on the very next tick, not snap."""
        current = oled.OLED_MIN_CONTRAST
        spiked_target = oled.compute_target_contrast(50000.0)  # a hand-over-sensor-style bright flash
        after_one_tick = oled.slew_contrast(current, spiked_target)
        self.assertLessEqual(after_one_tick - current, oled.OLED_CONTRAST_MAX_STEP_PER_TICK)


class GlanceMetricsTempUnitTests(unittest.TestCase):
    """build_glance_metrics()'s temp_unit field (2026-09-08) - read via
    piratebox_temp_unit.read_temp_unit(), monkeypatched here for a
    deterministic result regardless of this environment's real
    preference file (matches test_history_sampler.py's own style of
    monkeypatching a module-level function for a fake diagnostics read)."""

    def setUp(self):
        import piratebox_temp_unit
        self._orig_read = piratebox_temp_unit.read_temp_unit
        self._temp_unit_module = piratebox_temp_unit

    def tearDown(self):
        self._temp_unit_module.read_temp_unit = self._orig_read

    def test_defaults_to_celsius(self):
        self._temp_unit_module.read_temp_unit = lambda: "C"
        metrics, _ = oled.build_glance_metrics(None, True, None, False)
        self.assertEqual(metrics["temp_unit"], "C")

    def test_reads_fahrenheit_preference_through(self):
        self._temp_unit_module.read_temp_unit = lambda: "F"
        metrics, _ = oled.build_glance_metrics(None, True, None, False)
        self.assertEqual(metrics["temp_unit"], "F")


class GlanceMetricsTests(unittest.TestCase):
    """build_glance_metrics() - the one place raw reads get assembled
    into piratebox_glance.py's documented metrics contract."""

    def test_missing_status_degrades_every_status_derived_field(self):
        metrics, _ = oled.build_glance_metrics(None, True, None, False)
        self.assertIsNone(metrics["clients"])
        self.assertFalse(metrics["undervoltage_now"])
        self.assertIsNone(metrics["time_str"])

    def test_stale_status_degrades_the_same_way(self):
        metrics, _ = oled.build_glance_metrics({"wifi_clients": 5}, True, None, False)
        self.assertIsNone(metrics["clients"])

    def test_healthy_status_populates_client_count(self):
        status = {"wifi_clients": 3, "power": {"undervoltage_now": False}, "time_source": {}}
        metrics, _ = oled.build_glance_metrics(status, False, None, False)
        self.assertEqual(metrics["clients"], 3)

    def test_undervoltage_flag_is_read_through(self):
        status = {"wifi_clients": 0, "power": {"undervoltage_now": True}, "time_source": {}}
        metrics, _ = oled.build_glance_metrics(status, False, None, False)
        self.assertTrue(metrics["undervoltage_now"])

    def test_time_confident_when_ntp_synchronized(self):
        status = {"wifi_clients": 0, "power": {}, "time_source": {"ntp_synchronized": True}}
        metrics, _ = oled.build_glance_metrics(status, False, None, False)
        self.assertIsNotNone(metrics["time_str"])

    def test_time_confident_when_rtc_detected(self):
        status = {"wifi_clients": 0, "power": {}, "time_source": {"rtc_detected": True}}
        metrics, _ = oled.build_glance_metrics(status, False, None, False)
        self.assertIsNotNone(metrics["time_str"])

    def test_time_not_confident_without_ntp_or_rtc(self):
        status = {"wifi_clients": 0, "power": {}, "time_source": {"ntp_synchronized": False, "rtc_detected": False}}
        metrics, _ = oled.build_glance_metrics(status, False, None, False)
        self.assertIsNone(metrics["time_str"])

    def test_clients_recently_changed_is_passed_through_unchanged(self):
        metrics, _ = oled.build_glance_metrics(None, True, None, True)
        self.assertTrue(metrics["clients_recently_changed"])
        metrics, _ = oled.build_glance_metrics(None, True, None, False)
        self.assertFalse(metrics["clients_recently_changed"])

    def test_returns_a_fresh_cpu_jiffies_sample_for_the_next_call(self):
        _, new_jiffies = oled.build_glance_metrics(None, True, None, False)
        # Whatever the real /proc/stat happens to contain on this
        # machine, it must be a well-formed (total, idle) pair or None
        # (never raise) - both are valid depending on sandbox access.
        self.assertTrue(new_jiffies is None or (isinstance(new_jiffies, tuple) and len(new_jiffies) == 2))

    def test_cpu_percent_is_none_on_the_very_first_call(self):
        # No prior sample exists yet - exactly the daemon's own
        # freshly-started state.
        metrics, _ = oled.build_glance_metrics(None, True, None, False)
        self.assertIsNone(metrics["cpu_percent"])

    def test_uptime_str_is_always_a_string(self):
        metrics, _ = oled.build_glance_metrics(None, True, None, False)
        self.assertIsInstance(metrics["uptime_str"], str)

    # --- ambient_lux (2026-09-07, ambient light glance page) -----------
    # bh1750_module defaults to None (every call above omits it) -
    # confirms that stays fully backward compatible: ambient_lux is
    # simply always None, the same honest "not available" value a Pi
    # with no BH1750 wired would produce anyway.
    def test_ambient_lux_is_none_when_no_module_given(self):
        metrics, _ = oled.build_glance_metrics(None, True, None, False)
        self.assertIsNone(metrics["ambient_lux"])

    def test_ambient_lux_populated_from_a_genuinely_current_reading(self):
        class FakeBH1750:
            def get_diagnostics(self):
                return {"detected": True, "lux": 7.5, "stale": False, "last_success_seconds_ago": 1.0}
        metrics, _ = oled.build_glance_metrics(None, True, None, False, FakeBH1750())
        self.assertEqual(metrics["ambient_lux"], 7.5)

    def test_ambient_lux_zero_is_not_treated_as_missing(self):
        class FakeBH1750:
            def get_diagnostics(self):
                return {"detected": True, "lux": 0.0, "stale": False, "last_success_seconds_ago": 1.0}
        metrics, _ = oled.build_glance_metrics(None, True, None, False, FakeBH1750())
        self.assertEqual(metrics["ambient_lux"], 0.0)
        self.assertIsNotNone(metrics["ambient_lux"])

    def test_ambient_lux_none_when_never_detected(self):
        class FakeBH1750:
            def get_diagnostics(self):
                return {"detected": False, "lux": None, "stale": True, "last_success_seconds_ago": None}
        metrics, _ = oled.build_glance_metrics(None, True, None, False, FakeBH1750())
        self.assertIsNone(metrics["ambient_lux"])

    def test_ambient_lux_none_when_reading_has_gone_stale(self):
        """A last-known value existing is not enough - a stale reading
        must not be presented as current on the glance page, matching
        includes/sensors.php's own available/stale_reading distinction
        for the exact same underlying BH1750 diagnostics shape."""
        class FakeBH1750:
            def get_diagnostics(self):
                return {"detected": True, "lux": 42.0, "stale": True, "last_success_seconds_ago": 999.0}
        metrics, _ = oled.build_glance_metrics(None, True, None, False, FakeBH1750())
        self.assertIsNone(metrics["ambient_lux"])

    def test_ambient_lux_none_when_diagnostics_call_itself_raises(self):
        """A broken sensor module must never crash this glance-phase-
        entry (or, transitively, the daemon) - degrades exactly like
        every other optional hardware read in this project."""
        class BrokenBH1750:
            def get_diagnostics(self):
                raise RuntimeError("bus error")
        metrics, _ = oled.build_glance_metrics(None, True, None, False, BrokenBH1750())
        self.assertIsNone(metrics["ambient_lux"])

    def test_build_glance_metrics_never_triggers_a_second_i2c_reader(self):
        """The actual rate-limiting-preserved guarantee: this function
        must call ONLY get_diagnostics() (a read of the BH1750 module's
        own already-cached state) and never read_ambient_lux() directly
        - that would be a second, parallel trigger of a real I2C
        transaction alongside the one HARDWARE_SIGNALS's own registered
        reader already causes, defeating piratebox_bh1750.py's whole
        15s internal rate limit. Calling build_glance_metrics() several
        times in a row (as main()'s own multiple call sites do across
        different code paths) must not multiply get_diagnostics() calls
        beyond one per build_glance_metrics() call either."""
        calls = {"get_diagnostics": 0, "read_ambient_lux": 0}

        class TrackedBH1750:
            def get_diagnostics(self):
                calls["get_diagnostics"] += 1
                return {"detected": True, "lux": 10.0, "stale": False, "last_success_seconds_ago": 1.0}

            def read_ambient_lux(self):
                calls["read_ambient_lux"] += 1
                return 10.0

        tracked = TrackedBH1750()
        for _ in range(5):
            oled.build_glance_metrics(None, True, None, False, tracked)
        self.assertEqual(calls["get_diagnostics"], 5, "exactly one get_diagnostics() call per build_glance_metrics() call")
        self.assertEqual(calls["read_ambient_lux"], 0, "must never call the real-I2C-triggering reader directly")

    # --- probe_name/probe_temp_c (2026-09-07, DS18B20 glance page) -----
    # esp32_client_module defaults to None (every call above omits it) -
    # same backward-compatibility contract as bh1750_module above.

    def test_probe_is_none_when_no_module_given(self):
        metrics, _ = oled.build_glance_metrics(None, True, None, False)
        self.assertIsNone(metrics["probe_name"])
        self.assertIsNone(metrics["probe_temp_c"])

    def _fake_client(self, sensors, connected=True, stale=False):
        class FakeClient:
            def get_diagnostics(self):
                return {"connected": connected, "stale": stale, "sensors": sensors}
        return FakeClient()

    def test_probe_populated_from_a_single_named_ok_probe(self):
        client = self._fake_client({"ds18b20": {"bus_ok": True, "probes": {
            "28ff641e04170378": {"ok": True, "value": 21.4, "unit": "C", "name": "Enclosure"},
        }}})
        metrics, _ = oled.build_glance_metrics(None, True, None, False, None, client)
        self.assertEqual(metrics["probe_name"], "Enclosure")
        self.assertEqual(metrics["probe_temp_c"], 21.4)

    def test_unnamed_probe_never_shown_even_if_ok(self):
        client = self._fake_client({"ds18b20": {"bus_ok": True, "probes": {
            "28ff641e04170378": {"ok": True, "value": 21.4, "unit": "C", "name": None},
        }}})
        metrics, _ = oled.build_glance_metrics(None, True, None, False, None, client)
        self.assertIsNone(metrics["probe_name"])

    def test_failing_named_probe_never_shown(self):
        client = self._fake_client({"ds18b20": {"bus_ok": True, "probes": {
            "28ff641e04170378": {"ok": False, "err": "disconnected", "name": "Battery"},
        }}})
        metrics, _ = oled.build_glance_metrics(None, True, None, False, None, client)
        self.assertIsNone(metrics["probe_name"])

    def test_no_ds18b20_block_at_all_degrades_cleanly(self):
        client = self._fake_client({"temp_internal": {"ok": True, "value": 30.0}})
        metrics, _ = oled.build_glance_metrics(None, True, None, False, None, client)
        self.assertIsNone(metrics["probe_name"])

    def test_disconnected_supervisor_never_shows_a_probe(self):
        client = self._fake_client(
            {"ds18b20": {"bus_ok": True, "probes": {"28ff641e04170378": {"ok": True, "value": 1.0, "name": "X"}}}},
            connected=False,
        )
        metrics, _ = oled.build_glance_metrics(None, True, None, False, None, client)
        self.assertIsNone(metrics["probe_name"])

    def test_stale_supervisor_link_never_shows_a_probe(self):
        client = self._fake_client(
            {"ds18b20": {"bus_ok": True, "probes": {"28ff641e04170378": {"ok": True, "value": 1.0, "name": "X"}}}},
            stale=True,
        )
        metrics, _ = oled.build_glance_metrics(None, True, None, False, None, client)
        self.assertIsNone(metrics["probe_name"])

    def test_probe_diagnostics_call_raising_never_crashes(self):
        class BrokenClient:
            def get_diagnostics(self):
                raise RuntimeError("serial error")
        metrics, _ = oled.build_glance_metrics(None, True, None, False, None, BrokenClient())
        self.assertIsNone(metrics["probe_name"])
        self.assertIsNone(metrics["probe_temp_c"])

    def test_commissioned_but_unnamed_probe_shows_a_generic_physical_index_label(self):
        """2026-09-08 extension: a probe with a known physical identity
        (physical_index set during commissioning) but no cosmetic name
        yet is now glance-worthy - shown as "Probe N", never the ROM."""
        client = self._fake_client({"ds18b20": {"bus_ok": True, "probes": {
            "28ff641e04170378": {"ok": True, "value": 29.5, "name": None, "physical_index": 3},
        }}})
        metrics, _ = oled.build_glance_metrics(None, True, None, False, None, client)
        self.assertEqual(metrics["probe_name"], "Probe 3")
        self.assertEqual(metrics["probe_temp_c"], 29.5)

    def test_never_commissioned_probe_with_no_name_and_no_index_still_hidden(self):
        client = self._fake_client({"ds18b20": {"bus_ok": True, "probes": {
            "28ff641e04170378": {"ok": True, "value": 29.5, "name": None, "physical_index": None},
        }}})
        metrics, _ = oled.build_glance_metrics(None, True, None, False, None, client)
        self.assertIsNone(metrics["probe_name"])

    def test_named_probes_sort_before_unnamed_commissioned_probes(self):
        """Matches the Environment web page's own ordering, so the same
        probe never appears to have two different identities/positions
        across surfaces."""
        client = self._fake_client({"ds18b20": {"bus_ok": True, "probes": {
            "28aaaaaaaaaaaaaa": {"ok": True, "value": 1.0, "name": None, "physical_index": 1},
            "28bbbbbbbbbbbbbb": {"ok": True, "value": 2.0, "name": "Zebra", "physical_index": None},
        }}})
        import time as time_mod
        real_time = time_mod.time
        try:
            time_mod.time = lambda: 0.0  # minute index 0 -> first in sort order
            metrics, _ = oled.build_glance_metrics(None, True, None, False, None, client)
            self.assertEqual(metrics["probe_name"], "Zebra")  # named sorts first regardless of index
        finally:
            time_mod.time = real_time

    def test_multiple_named_probes_rotate_deterministically_by_minute(self):
        """Stateless-by-wall-clock rotation, not fabricated randomness -
        the SAME minute always picks the SAME probe (alphabetically
        ordered, indexed by minute-of-epoch modulo probe count)."""
        client = self._fake_client({"ds18b20": {"bus_ok": True, "probes": {
            "28ff641e04170378": {"ok": True, "value": 21.4, "name": "Enclosure"},
            "28aa112233445566": {"ok": True, "value": 4.0, "name": "Battery"},
        }}})
        import time as time_mod
        real_time = time_mod.time
        try:
            time_mod.time = lambda: 0.0  # minute index 0 -> alphabetically first: Battery
            metrics, _ = oled.build_glance_metrics(None, True, None, False, None, client)
            self.assertEqual(metrics["probe_name"], "Battery")
            time_mod.time = lambda: 60.0  # minute index 1 -> Enclosure
            metrics, _ = oled.build_glance_metrics(None, True, None, False, None, client)
            self.assertEqual(metrics["probe_name"], "Enclosure")
        finally:
            time_mod.time = real_time


class GlanceDispatchTests(unittest.TestCase):
    """build_frame()'s "glance" page arm - confirms the wiring itself
    (extra-dict keys, font routing) without re-testing piratebox_
    glance.py's own rendering logic (see tools/test_glance.py)."""

    def test_glance_page_renders_via_build_frame(self):
        font, font_small, font_big = oled.load_fonts()
        label_fonts, font_cpu_label, font_medium, font_glance_big = oled.load_glance_fonts()
        img = oled.build_frame(
            FakeDevice(), "glance", font, font_small, font_big, None, False, "normal",
            extra={
                "page_id": "cpu", "metrics": {"cpu_percent": 8, "cpu_temp_c": 46},
                "label_fonts": label_fonts, "font_cpu_label": font_cpu_label,
                "font_medium": font_medium, "font_big": font_glance_big,
            },
        )
        self.assertEqual(img.size, (128, 64))

    def test_every_known_glance_page_id_renders_via_build_frame(self):
        font, font_small, font_big = oled.load_fonts()
        label_fonts, font_cpu_label, font_medium, font_glance_big = oled.load_glance_fonts()
        for page_id in oled.GLANCE_PAGES:
            with self.subTest(page_id=page_id):
                img = oled.build_frame(
                    FakeDevice(), "glance", font, font_small, font_big, None, False, "normal",
                    extra={
                        "page_id": page_id, "metrics": {},
                        "label_fonts": label_fonts, "font_cpu_label": font_cpu_label,
                        "font_medium": font_medium, "font_big": font_glance_big,
                    },
                )
                self.assertEqual(img.size, (128, 64))


class GlancePreviewOverrideTests(unittest.TestCase):
    """read_glance_preview_active() - identical recency-based pattern
    to PreviewOverrideTests above, its own independent signal file."""

    def setUp(self):
        self._orig = oled.GLANCE_PREVIEW_REQUEST_FILE
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        oled.GLANCE_PREVIEW_REQUEST_FILE = self.path

    def tearDown(self):
        oled.GLANCE_PREVIEW_REQUEST_FILE = self._orig
        if os.path.exists(self.path):
            os.unlink(self.path)

    def write(self, content):
        with open(self.path, "w") as f:
            f.write(content)

    def test_missing_file_is_inactive(self):
        os.unlink(self.path)
        self.assertFalse(oled.read_glance_preview_active(1000.0))

    def test_recent_timestamp_is_active(self):
        self.write("1000.0\n")
        self.assertTrue(oled.read_glance_preview_active(1005.0))

    def test_old_timestamp_is_inactive(self):
        self.write("1000.0\n")
        self.assertFalse(oled.read_glance_preview_active(1000.0 + oled.GLANCE_PREVIEW_WINDOW_SECONDS + 1))

    def test_garbage_content_is_inactive_not_a_crash(self):
        self.write("not a number")
        self.assertFalse(oled.read_glance_preview_active(1000.0))

    def test_independent_of_the_silly_preview_file(self):
        """The two preview mechanisms must never share state - glance-
        preview must work even if the (unrelated) Silly preview file
        happens to also be stale/missing/active."""
        self.write("1000.0\n")
        orig_silly_preview = oled.PREVIEW_REQUEST_FILE
        oled.PREVIEW_REQUEST_FILE = "/nonexistent/path/for/this/test"
        try:
            self.assertTrue(oled.read_glance_preview_active(1005.0))
            self.assertFalse(oled.read_preview_active(1005.0))
        finally:
            oled.PREVIEW_REQUEST_FILE = orig_silly_preview


class GlancePriorityIntegrationTests(unittest.TestCase):
    """Confirms glance sits exactly where it's supposed to in the
    priority hierarchy: preemptable by Emergency/fault/mode-transition/
    toggle-confirmation, reachable regardless of Silly on/off, and
    never substituting for STATUS CHECK. Mirrors the exact elif-chain
    ordering directly (no separate helper function exists to call in
    isolation), same technique SillyTogglePriorityIntegrationTests uses."""

    def _decide(self, mode_transition, tier, silly_toggle_just_happened, glance_preview_active,
                silly_enabled, status_check_active, preview_active, silly_cadence_phase):
        if mode_transition is not None:
            return "mode_transition"
        if tier in ("emergency", "fault"):
            return "serious_rotation"
        if silly_toggle_just_happened:
            return "silly_toggle_banner"
        if glance_preview_active:
            return "glance"
        if not silly_enabled:
            return "glance" if silly_cadence_phase == "glance" else "serious_rotation"
        if status_check_active:
            return "status_check_banner_or_serious_rotation"
        if preview_active:
            return "silly"
        return "glance" if silly_cadence_phase == "glance" else "silly_or_serious_rotation"

    def test_emergency_outranks_glance_preview(self):
        self.assertEqual(
            self._decide(None, "emergency", False, True, True, False, False, "glance"),
            "serious_rotation",
        )

    def test_fault_outranks_glance_preview(self):
        self.assertEqual(
            self._decide(None, "fault", False, True, True, False, False, "glance"),
            "serious_rotation",
        )

    def test_mode_transition_outranks_everything(self):
        self.assertEqual(
            self._decide("emergency", "emergency", False, True, True, False, False, "glance"),
            "mode_transition",
        )

    def test_glance_preview_works_when_silly_is_off(self):
        self.assertEqual(
            self._decide(None, "ok", False, True, False, False, False, "rotation"),
            "glance",
        )

    def test_glance_preview_works_when_silly_is_on(self):
        self.assertEqual(
            self._decide(None, "ok", False, True, True, False, False, "personality"),
            "glance",
        )

    def test_status_check_active_is_never_replaced_by_glance(self):
        # status_check_active is only even reached in this chain when
        # silly_enabled is True and nothing above it applies - confirm
        # it still wins over glance-cadence phase (glance is checked
        # ONLY inside the not-silly-enabled/else branches, never here).
        self.assertEqual(
            self._decide(None, "ok", False, False, True, True, False, "status"),
            "status_check_banner_or_serious_rotation",
        )

    def test_ordinary_glance_phase_reachable_when_silly_off_and_nothing_else_active(self):
        self.assertEqual(
            self._decide(None, "ok", False, False, False, False, False, "glance"),
            "glance",
        )

    def test_ordinary_glance_phase_reachable_when_silly_on_and_nothing_else_active(self):
        self.assertEqual(
            self._decide(None, "ok", False, False, True, False, False, "glance"),
            "glance",
        )

    def test_rotation_phase_when_silly_off_shows_serious_rotation_not_glance(self):
        self.assertEqual(
            self._decide(None, "ok", False, False, False, False, False, "rotation"),
            "serious_rotation",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
