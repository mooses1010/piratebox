#!/usr/bin/env python3
"""Deterministic tests for piratebox_button_daemon.py's callback logic -
matches the project's existing dependency-free tools/test_*.py
convention (see tools/test_silly_mode.py).

Run with: python3 tools/test_button_daemon.py

SAFETY: this suite NEVER constructs a real gpiozero Button() (which
would attempt to claim the real GPIO25 line - a genuine conflict risk
if piratebox-button.service is already running on this same hardware)
and NEVER lets a real `sudo systemctl poweroff` execute - every test
that exercises the SHUTDOWN_ENABLED path monkeypatches `subprocess.run`
to a recording stub first. Only the plain callback functions
(on_pressed/on_held/on_released) and the module-level gesture-state
flags are exercised directly - importing the module itself is safe (it
only imports the `Button` class, never instantiates one at import
time).

DOUBLE_TAP_WINDOW_S is monkeypatched to a tiny value in every test that
needs to wait it out, so this suite runs in well under a second total
despite exercising a real `threading.Timer` (not a mock) - the actual
timer/threading code path is what's under test, just on a compressed
timescale.
"""

import importlib.util
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
DAEMON_PATH = os.path.join(HERE, "..", "piratebox_button_daemon.py")

spec = importlib.util.spec_from_file_location("piratebox_button_daemon", DAEMON_PATH)
btn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(btn)

FAST_WINDOW = 0.03   # real threading.Timer, just compressed for fast tests
SETTLE = FAST_WINDOW * 3  # always sleep comfortably past the window


class ButtonDaemonTests(unittest.TestCase):
    def setUp(self):
        self._orig_status_file = btn.STATUS_CHECK_REQUEST_FILE
        self._orig_silly_file = btn.SILLY_FILE
        self._orig_toggle_file = btn.SILLY_TOGGLE_REQUEST_FILE
        self._orig_enabled = btn.SHUTDOWN_ENABLED
        self._orig_window = btn.DOUBLE_TAP_WINDOW_S

        fd, self.status_path = tempfile.mkstemp()
        os.close(fd)
        fd, self.silly_path = tempfile.mkstemp()
        os.close(fd)
        fd, self.toggle_path = tempfile.mkstemp()
        os.close(fd)

        btn.STATUS_CHECK_REQUEST_FILE = self.status_path
        btn.SILLY_FILE = self.silly_path
        btn.SILLY_TOGGLE_REQUEST_FILE = self.toggle_path
        btn.DOUBLE_TAP_WINDOW_S = FAST_WINDOW

        btn._hold_just_fired = False
        btn._awaiting_second_tap_resolution = False
        btn._pending_single_tap_timer = None

    def tearDown(self):
        # Cancel any timer a failed assertion might have left running,
        # so one test can never bleed a delayed write into the next.
        if btn._pending_single_tap_timer is not None:
            btn._pending_single_tap_timer.cancel()
        btn.STATUS_CHECK_REQUEST_FILE = self._orig_status_file
        btn.SILLY_FILE = self._orig_silly_file
        btn.SILLY_TOGGLE_REQUEST_FILE = self._orig_toggle_file
        btn.SHUTDOWN_ENABLED = self._orig_enabled
        btn.DOUBLE_TAP_WINDOW_S = self._orig_window
        btn._hold_just_fired = False
        btn._awaiting_second_tap_resolution = False
        btn._pending_single_tap_timer = None
        for p in (self.status_path, self.silly_path, self.toggle_path):
            if os.path.exists(p):
                os.unlink(p)

    def read(self, path):
        with open(path, "r") as f:
            return f.read()

    def tap(self):
        """A single short tap: press, then release before hold_time -
        exactly what a real quick press-and-release produces."""
        btn.on_pressed()
        btn.on_released()

    # --- The mandatory long-hold safety guarantee ---

    def test_long_press_does_not_also_fire_the_short_press_action(self):
        with open(self.status_path, "w") as f:
            f.write("SENTINEL-UNTOUCHED")
        btn.SHUTDOWN_ENABLED = False  # log-only path - still sets the flag
        btn.on_pressed()
        btn.on_held()
        btn.on_released()
        time.sleep(SETTLE)
        self.assertEqual(self.read(self.status_path), "SENTINEL-UNTOUCHED")

    def test_long_press_never_touches_shutdown_with_a_pending_tap_first(self):
        """A pending single-tap window followed by a separate long hold
        must resolve safely - no single-tap, no double-tap, and the
        hold/shutdown path proceeds exactly as it always does."""
        with open(self.silly_path, "w") as f:
            f.write("off")
        self.tap()  # starts a pending window
        btn.SHUTDOWN_ENABLED = False
        btn.on_pressed()   # a second press begins DURING the window
        btn.on_held()      # ...and reaches the hold threshold
        btn.on_released()
        time.sleep(SETTLE)
        self.assertEqual(self.read(self.status_path), "")  # never written
        self.assertEqual(self.read(self.silly_path).strip(), "off")  # never toggled

    def test_short_press_never_touches_shutdown_regardless_of_enabled_flag(self):
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                btn.SHUTDOWN_ENABLED = enabled
                btn._hold_just_fired = False
                with mock.patch.object(btn.subprocess, "run") as run:
                    self.tap()
                    time.sleep(SETTLE)
                    run.assert_not_called()

    def test_hold_flag_is_cleared_after_the_suppressed_release(self):
        btn.SHUTDOWN_ENABLED = False
        btn.on_pressed()
        btn.on_held()
        btn.on_released()  # suppressed - the long-press's own release
        self.assertFalse(btn._hold_just_fired)
        self.tap()  # a later, independent, genuine short press
        time.sleep(SETTLE)
        content = self.read(self.status_path)
        self.assertNotEqual(content.strip(), "")
        float(content)  # must parse as a real timestamp, not garbage

    def test_on_held_calls_shutdown_exactly_when_enabled(self):
        btn.SHUTDOWN_ENABLED = True
        with mock.patch.object(btn.subprocess, "run") as run:
            btn.on_pressed()
            btn.on_held()
            run.assert_called_once()
            self.assertEqual(run.call_args[0][0], ["sudo", "-n", "systemctl", "poweroff"])

    def test_on_held_flag_still_set_even_if_shutdown_call_raises(self):
        btn.SHUTDOWN_ENABLED = True
        with mock.patch.object(btn.subprocess, "run", side_effect=OSError("boom")):
            btn.on_pressed()
            btn.on_held()  # must not raise
        self.assertTrue(btn._hold_just_fired)

    # --- Single tap: deferred, and only fires once the window elapses ---

    def test_single_tap_does_not_fire_immediately(self):
        """The whole point of the window: a lone tap's release must NOT
        write the request immediately - only after DOUBLE_TAP_WINDOW_S
        has passed with no second tap."""
        self.tap()
        self.assertEqual(self.read(self.status_path), "")  # not yet
        time.sleep(SETTLE)
        self.assertNotEqual(self.read(self.status_path).strip(), "")  # now it has

    def test_single_tap_produces_exactly_one_status_check_request(self):
        before = time.time()
        self.tap()
        time.sleep(SETTLE)
        written_ts = float(self.read(self.status_path).strip())
        self.assertGreaterEqual(written_ts, before)
        self.assertLessEqual(written_ts, time.time() + 1.0)

    # --- Double tap: toggles Silly Mode, never also fires a single tap ---

    def test_double_tap_toggles_silly_from_off_to_on(self):
        with open(self.silly_path, "w") as f:
            f.write("off")
        self.tap()
        self.tap()  # second tap arrives well within the (fast) window
        self.assertEqual(self.read(self.silly_path).strip(), "on")

    def test_double_tap_toggles_silly_from_on_to_off(self):
        with open(self.silly_path, "w") as f:
            f.write("on")
        self.tap()
        self.tap()
        self.assertEqual(self.read(self.silly_path).strip(), "off")

    def test_double_tap_writes_the_confirmation_signal(self):
        with open(self.silly_path, "w") as f:
            f.write("off")
        before = time.time()
        self.tap()
        self.tap()
        written_ts = float(self.read(self.toggle_path).strip())
        self.assertGreaterEqual(written_ts, before)

    def test_double_tap_does_not_also_generate_a_single_tap_request(self):
        with open(self.silly_path, "w") as f:
            f.write("off")
        with open(self.status_path, "w") as f:
            f.write("SENTINEL-UNTOUCHED")
        self.tap()
        self.tap()
        time.sleep(SETTLE)  # long enough for a wrongly-surviving timer to fire
        self.assertEqual(self.read(self.status_path), "SENTINEL-UNTOUCHED")

    def test_double_tap_toggles_exactly_once_not_twice(self):
        """Guards against a bug where both taps' releases each toggle -
        the state must flip exactly once per double-tap gesture."""
        with open(self.silly_path, "w") as f:
            f.write("off")
        self.tap()
        self.tap()
        self.assertEqual(self.read(self.silly_path).strip(), "on")
        time.sleep(SETTLE)
        self.assertEqual(self.read(self.silly_path).strip(), "on")  # still "on", not flipped back

    def test_repeated_double_taps_toggle_predictably(self):
        with open(self.silly_path, "w") as f:
            f.write("off")
        expected = ["on", "off", "on", "off"]
        for want in expected:
            self.tap()
            self.tap()
            self.assertEqual(self.read(self.silly_path).strip(), want)
            time.sleep(SETTLE)  # let state fully settle between gestures

    def test_on_pressed_alone_does_not_toggle_or_request_anything(self):
        """A press with no matching release yet (still physically held,
        below the hold threshold) must not act - only a resolved
        gesture (release or held) does."""
        with open(self.silly_path, "w") as f:
            f.write("off")
        btn.on_pressed()
        self.assertEqual(self.read(self.silly_path).strip(), "off")
        self.assertEqual(self.read(self.status_path), "")

    # --- Degrade, don't crash ---

    def test_on_released_write_failure_does_not_raise(self):
        btn.STATUS_CHECK_REQUEST_FILE = "/nonexistent/directory/for/this/test/file"
        self.tap()
        time.sleep(SETTLE)  # must not raise from the timer thread either

    def test_missing_silly_file_toggle_defaults_to_on(self):
        os.unlink(self.silly_path)  # simulates a missing/malformed runtime file
        self.tap()
        self.tap()
        self.assertEqual(self.read(self.silly_path).strip(), "on")

    def test_garbage_silly_file_content_is_treated_as_off(self):
        with open(self.silly_path, "w") as f:
            f.write("not a valid state\n")
        self.tap()
        self.tap()
        self.assertEqual(self.read(self.silly_path).strip(), "on")

    def test_toggle_request_write_failure_does_not_block_the_actual_toggle(self):
        with open(self.silly_path, "w") as f:
            f.write("off")
        btn.SILLY_TOGGLE_REQUEST_FILE = "/nonexistent/directory/for/this/test/file"
        self.tap()
        self.tap()
        self.assertEqual(self.read(self.silly_path).strip(), "on")  # toggle still happened


if __name__ == "__main__":
    unittest.main(verbosity=2)
