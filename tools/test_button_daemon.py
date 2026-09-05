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
(on_held/on_released) and the module-level suppression flag are
exercised directly - importing the module itself is safe (it only
imports the `Button` class, never instantiates one at import time).
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


class ButtonDaemonTests(unittest.TestCase):
    def setUp(self):
        self._orig_file = btn.STATUS_CHECK_REQUEST_FILE
        self._orig_enabled = btn.SHUTDOWN_ENABLED
        fd, self.tmp_path = tempfile.mkstemp()
        os.close(fd)
        btn.STATUS_CHECK_REQUEST_FILE = self.tmp_path
        btn._hold_just_fired = False  # reset the module-level flag every test

    def tearDown(self):
        btn.STATUS_CHECK_REQUEST_FILE = self._orig_file
        btn.SHUTDOWN_ENABLED = self._orig_enabled
        btn._hold_just_fired = False
        if os.path.exists(self.tmp_path):
            os.unlink(self.tmp_path)

    def read_request_file(self):
        with open(self.tmp_path, "r") as f:
            return f.read()

    # --- The mandatory safety guarantee, tested directly and explicitly ---

    def test_long_press_does_not_also_fire_the_short_press_action(self):
        """The core requirement: a hold that triggers on_held() must
        leave the release that follows it a no-op, never writing the
        status-check request."""
        with open(self.tmp_path, "w") as f:
            f.write("SENTINEL-UNTOUCHED")
        btn.SHUTDOWN_ENABLED = False  # log-only path - still sets the flag
        btn.on_held()
        btn.on_released()
        self.assertEqual(self.read_request_file(), "SENTINEL-UNTOUCHED")

    def test_short_press_alone_writes_a_fresh_request(self):
        before = time.time()
        btn.on_released()
        content = self.read_request_file()
        written_ts = float(content.strip())
        self.assertGreaterEqual(written_ts, before)
        self.assertLessEqual(written_ts, time.time() + 1.0)

    def test_short_press_never_touches_shutdown_regardless_of_enabled_flag(self):
        """A short press must never risk shutdown - confirmed by
        recording every subprocess.run call and asserting zero of them
        happened, with SHUTDOWN_ENABLED set either way."""
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                btn.SHUTDOWN_ENABLED = enabled
                btn._hold_just_fired = False
                with mock.patch.object(btn.subprocess, "run") as run:
                    btn.on_released()
                    run.assert_not_called()

    def test_hold_flag_is_cleared_after_the_suppressed_release(self):
        """A subsequent, later, genuine short press (long after the
        hold) must work normally - the flag must not stay stuck set."""
        btn.SHUTDOWN_ENABLED = False
        btn.on_held()
        btn.on_released()  # suppressed - the long-press's own release
        self.assertFalse(btn._hold_just_fired)
        btn.on_released()  # a later, independent, genuine short press
        content = self.read_request_file()
        self.assertNotEqual(content.strip(), "")
        float(content)  # must parse as a real timestamp, not garbage

    # --- Regression: existing long-press/shutdown behavior unchanged ---

    def test_on_held_sets_the_suppression_flag(self):
        btn.SHUTDOWN_ENABLED = False
        self.assertFalse(btn._hold_just_fired)
        btn.on_held()
        self.assertTrue(btn._hold_just_fired)

    def test_on_held_calls_shutdown_exactly_when_enabled(self):
        btn.SHUTDOWN_ENABLED = True
        with mock.patch.object(btn.subprocess, "run") as run:
            btn.on_held()
            run.assert_called_once()
            args = run.call_args[0][0]
            self.assertEqual(args, ["sudo", "-n", "systemctl", "poweroff"])

    def test_on_held_does_not_call_shutdown_when_disabled(self):
        btn.SHUTDOWN_ENABLED = False
        with mock.patch.object(btn.subprocess, "run") as run:
            btn.on_held()
            run.assert_not_called()

    def test_on_held_flag_still_set_even_if_shutdown_call_raises(self):
        """A failed shutdown call must not leave the daemon thinking
        this was a short press - the flag is set before the call is
        even attempted (see on_held()'s own docstring)."""
        btn.SHUTDOWN_ENABLED = True
        with mock.patch.object(btn.subprocess, "run", side_effect=OSError("boom")):
            btn.on_held()  # must not raise
        self.assertTrue(btn._hold_just_fired)

    # --- Degrade, don't crash ---

    def test_on_released_write_failure_does_not_raise(self):
        btn.STATUS_CHECK_REQUEST_FILE = "/nonexistent/directory/for/this/test/file"
        btn.on_released()  # must not raise


if __name__ == "__main__":
    unittest.main(verbosity=2)
