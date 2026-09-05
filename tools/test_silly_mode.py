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

spec = importlib.util.spec_from_file_location("piratebox_oled_daemon", DAEMON_PATH)
oled = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oled)


class FakeDevice:
    mode = "1"
    size = (128, 64)


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
                    extra={"expression": expr, "quip": None, "tier": tier},
                )
                self.assertEqual(img.size, (128, 64))

    def test_pirate_flourish_renders_with_every_quip(self):
        for quip_template in oled.SILLY_QUIPS:
            quip = quip_template.format(n=3)
            img = oled.build_frame(
                self.device, "silly", self.font, self.font_small, self.font_big,
                HEALTHY_STATUS, False, "normal", alive_on=True,
                extra={"expression": "pirate_flourish", "quip": quip, "tier": "ok"},
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
