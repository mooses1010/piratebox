#!/usr/bin/env python3
#
# PirateBox physical button daemon - Stage 29 implementation.
#
# Watches BCM GPIO25 (physical header pin 22) - the "hold-for-safe-
# shutdown" button from docs/PHYSICAL-CONTROL-UX-DESIGN.md §3, wired as
# a normally-open momentary switch to GND on physical pin 9, using the
# Pi's internal pull-up (no external resistor). Physically bring-up
# tested interactively before this daemon was written - see
# docs/OPERATIONAL-DECISIONS.md and docs/HARDWARE-INTEGRATION-DESIGN.md
# for the verified electrical results (idle HIGH, pressed LOW, clean
# debounce, exact 4.0s hold-trigger timing, no re-fire on an extended
# hold).
#
# WHAT THIS DOES:
#   - A press held continuously for HOLD_SECONDS (4.0s) triggers exactly
#     once: it logs one line and then requests a clean shutdown via
#     `sudo -n systemctl poweroff`. Holding longer than the threshold
#     does not re-trigger (hold_repeat=False) - matching Stage 29 §3's
#     "no countdown-abort undo after zero, but no repeated action either"
#     design.
#   - A SINGLE short tap (released before HOLD_SECONDS, no second tap
#     follows within DOUBLE_TAP_WINDOW_S) writes a small, non-persistent
#     timestamp to STATUS_CHECK_REQUEST_FILE (2026-09-04, "OLED cadence
#     rebalance" round) - see that constant's own comment for the full
#     design.
#   - A DOUBLE tap (a second short tap arrives within DOUBLE_TAP_WINDOW_S
#     of the first one's release) toggles Silly Mode by writing directly
#     to SILLY_FILE - the SAME file `piratebox-silly on`/`off` already
#     control (2026-09-04, "double-tap Silly toggle" round) - deliberately
#     not a second, parallel Silly-state mechanism. A tiny second signal,
#     SILLY_TOGGLE_REQUEST_FILE, is also touched purely so the OLED
#     daemon can show a one-shot confirmation - see toggle_silly_mode()
#     below.
#   - Neither of the above involves any OLED rendering knowledge in this
#     file, no direct call into the display daemon - just plain state/
#     signal writes for some other process to interpret however it
#     likes. This keeps the same "GPIO daemon has exactly one job [per
#     gesture]" shape this file already had for the long-press/shutdown
#     path, and means a future second button, a CLI command, or an
#     admin-UI action could produce the identical signals without this
#     file changing at all.
#
# GESTURE DISCRIMINATION (single tap vs. double tap vs. long hold):
#   gpiozero gives this daemon exactly three primitive signals for one
#   button - `when_pressed`, `when_released`, `when_held` (fired once,
#   mid-press, after HOLD_SECONDS) - no built-in double-tap concept, so
#   this file implements a small state machine on top:
#     - On release, if this WASN'T the second half of a pending double-
#       tap window (see below), it might be a lone tap - but we can't
#       know that yet, since a second tap might still be coming. So a
#       `threading.Timer` for DOUBLE_TAP_WINDOW_S is started; if nothing
#       else happens before it fires, THAT's when the single-tap action
#       (status-check) actually runs - not at release time. This is the
#       "reasonable small delay before a single-tap status check" the
#       design explicitly accepts as the cost of correct discrimination.
#     - `on_pressed()` (a new handler, added this round) is where a
#       PENDING window actually gets resolved: if a new press begins
#       while a single-tap timer is still running, that timer is
#       canceled immediately (so the eventual single-tap action never
#       fires) and `_awaiting_second_tap_resolution` is set, meaning
#       "how THIS press resolves decides what happens":
#         - released quickly -> `on_released()` sees the flag set and
#           fires the double-tap action (Silly Mode toggle) - no
#           single-tap action ever ran for either half of the gesture.
#         - held to HOLD_SECONDS -> `on_held()` clears the flag before
#           doing anything else, so the pending tap is silently
#           discarded (no single-tap, no double-tap) and the long-press/
#           shutdown path runs exactly as it always has. This is the
#           "if a pending first tap exists and the next interaction
#           becomes a long hold, cancel/resolve that state safely"
#           requirement, satisfied at the moment the second press
#           begins - well before HOLD_SECONDS elapses, so there is no
#           window where a stray single-tap action could still fire out
#           from under an in-progress hold.
#   `_tap_lock` (a plain `threading.Lock`) guards the one piece of state
#   a background `threading.Timer` thread and gpiozero's own callback
#   thread can BOTH touch - the pending timer reference itself - so a
#   cancel() racing the timer's own about-to-fire callback can never
#   result in the single-tap action running anyway (each side checks,
#   under the lock, whether it's still the ACTIVE timer before acting).
#
# CRITICAL, load-bearing ordering guarantee, unchanged from before this
# round: a long press that triggers shutdown must NEVER also produce a
# tap action on release. gpiozero fires `when_released` on every
# release, including one that follows an already-fired `when_held` - so
# `on_held()` sets `_hold_just_fired` FIRST, before anything else, and
# `on_released()` checks it before any tap-gesture logic at all. A tap
# (single or the first half of a double) can never itself set that
# flag, so "a short press must never risk shutdown" remains
# structurally true regardless of how the tap-discrimination logic
# above evolves.
#
# FAILS SAFELY:
#   - The real shutdown call is gated behind an explicit opt-in
#     (PIRATEBOX_BUTTON_ENABLE_SHUTDOWN=1 in the environment, set only
#     in the systemd unit once the operator has verified the persistent
#     service end-to-end). Without it, a "long press" only logs what it
#     WOULD have done - this is the deliberate default, so a
#     misconfiguration can never cause an unwanted shutdown; it can only
#     ever fail toward inaction.
#   - `sudo -n` (non-interactive): if the sudoers grant is ever missing
#     or misconfigured, this fails immediately with a clear error
#     instead of hanging waiting for a password that will never come.
#   - Any exception constructing the Button (e.g. the pin is somehow
#     already claimed) is logged and exits non-zero rather than retrying
#     in a tight loop - systemd's own Restart=on-failure/RestartSec
#     backoff handles retries, so this script doesn't need its own.
#
# NOT BUSY-POLLING, NOT WRITING TO THE SD CARD ON EVERY EVENT:
#   gpiozero's default pin factory on this system (lgpio) uses kernel
#   GPIO line-event notification, not a manual polling loop - the
#   process is asleep (signal.pause()) between events. Nothing here
#   writes a data file at all: short presses produce zero I/O, and the
#   rare long-press trigger produces exactly one log line via the
#   process's own stdout, captured by systemd/journald the same way
#   every other systemd service's output already is - no dedicated
#   per-event file, no JSON store, nothing resembling the connection-
#   statistics or Travel Mode data stores.
#
# PRIVILEGE BOUNDARY:
#   This daemon runs as the dedicated, unprivileged `piratebox-gpio`
#   system user (systemd's User=/Group= directives - see
#   etc/systemd/system/piratebox-button.service), never as root and
#   never as www-data. It holds exactly one narrow, dedicated sudoers
#   grant (etc/sudoers.d/piratebox-button) for exactly one command with
#   no arguments to vary - a completely separate trust boundary from
#   etc/sudoers.d/piratebox-claude (a different actor: this project's
#   deploy/mode-switch automation, not a locally-running hardware
#   daemon), per Stage 29 §3's explicit instruction not to widen that
#   file for this purpose.

import logging
import os
import signal
import subprocess
import sys
import threading
import time

from gpiozero import Button

GPIO_PIN = 25
DEBOUNCE_S = 0.05
HOLD_SECONDS = 4.0
DOUBLE_TAP_WINDOW_S = 0.4   # within the requested 350-500ms range; long
                             # enough for a deliberate second tap, short
                             # enough that a single-tap status check
                             # doesn't feel sluggish
SHUTDOWN_ENABLED = os.environ.get("PIRATEBOX_BUTTON_ENABLE_SHUTDOWN") == "1"

# Short-press "show me real stats" signal (2026-09-04). A plain text file
# containing one Unix timestamp - "a short press happened at time T,"
# nothing else. Deliberately NOT a request/acknowledgment protocol like
# Progression's reset/import requests (piratebox_progression.py) - there
# is nothing to consume or validate here, just a recency check ("is now
# within STATUS_CHECK_WINDOW_SECONDS of the last write") - so any
# consumer (the OLED daemon today; conceivably a future second button,
# a CLI command, or an admin-UI action later, per instruction) can just
# stat/read this file on its own schedule with no coordination needed.
# A repeated short press naturally re-extends the window - each write
# simply replaces the timestamp with a newer one.
#
# Lives in /tmp/piratebox/ (tmpfs) - explicitly non-persistent, gone on
# reboot, matching every other transient signal in that directory
# (Silly Mode's own toggle, Progression's request files). Pre-created
# (owned piratebox-gpio:piratebox-gpio) by etc/tmpfiles.d/
# piratebox-tmp.conf, with a single-file `BindPaths=` (read-write) in
# piratebox-button.service - this daemon's PrivateTmp=yes would
# otherwise hide the real host path entirely (the same class of issue
# Silly Mode's own bring-up found and fixed for the OLED daemon's
# BindReadOnlyPaths) - deliberately the single narrowest bind that
# works: this daemon gets read-write access to exactly this one file,
# nothing else in that directory (it has no legitimate reason to see
# the mode file, the Silly Mode toggle, or Progression's requests).
STATUS_CHECK_REQUEST_FILE = "/tmp/piratebox/status-check-request"

# Double-tap Silly Mode toggle (2026-09-04). SILLY_FILE is the EXACT
# same file `piratebox-silly on`/`off` already read and write -
# deliberately not a second, parallel toggle mechanism. Its tmpfiles.d
# rule now sets group `gpio` (this service's own effective group, via
# Group=gpio below) with mode 0664, so this daemon can write it
# directly with no ownership change (moose - the CLI's own account -
# keeps write access unchanged via the owner bit). SILLY_TOGGLE_
# REQUEST_FILE is a second, purely cosmetic timestamp - like STATUS_
# CHECK_REQUEST_FILE above, nothing here decides what the OLED shows;
# it just marks "the toggle changed just now" for the OLED daemon to
# notice and read the real new state from SILLY_FILE itself.
SILLY_FILE = "/tmp/piratebox/silly"
SILLY_TOGGLE_REQUEST_FILE = "/tmp/piratebox/silly-toggle-request"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s piratebox-button: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("piratebox-button")


_hold_just_fired = False   # see on_released() below - the one flag that
                            # makes "long press -> shutdown" and "tap
                            # action" mutually exclusive on the SAME
                            # physical release event

_tap_lock = threading.Lock()           # guards _pending_single_tap_timer
                                         # only (see the header note on
                                         # why nothing else needs it)
_pending_single_tap_timer = None        # a threading.Timer, or None
_awaiting_second_tap_resolution = False # True from the moment a new press
                                         # begins during a pending single-
                                         # tap window, until THAT press
                                         # itself resolves (see on_pressed())


def write_status_check_request() -> None:
    """The single-tap action - see STATUS_CHECK_REQUEST_FILE's own
    comment. A separate top-level function (not inlined) so both the
    delayed-fire closure in on_released() and the test suite can call
    it directly."""
    try:
        with open(STATUS_CHECK_REQUEST_FILE, "w") as f:
            f.write(f"{time.time()}\n")
    except OSError as exc:
        # Same fail-safe direction as everywhere else in this file: a
        # write failure here degrades to "the tap did nothing visible,"
        # never a crash, never retried in a tight loop.
        log.warning("Could not write status-check request (%s) - ignoring.", exc)


def read_silly_enabled() -> bool:
    """Mirrors the OLED daemon's own read_silly_enabled() exactly (same
    fail-safe rule: anything other than the literal string "on" is
    off). Deliberately duplicated rather than imported - importing
    piratebox_oled_daemon.py here would drag in luma/PIL/hardware
    bindings this unrelated GPIO daemon has no business depending on,
    for the sake of avoiding two lines of obviously-synchronized logic."""
    try:
        with open(SILLY_FILE, "r") as f:
            return f.read().strip().lower() == "on"
    except OSError:
        return False


def toggle_silly_mode() -> None:
    """The double-tap action. Reads the CURRENT Silly Mode state from
    the same file `piratebox-silly on`/`off` already control, and
    writes the opposite - there is exactly one source of truth for this
    state, never a second toggle mechanism. Also touches
    SILLY_TOGGLE_REQUEST_FILE (a plain timestamp, nothing else) purely
    so the OLED daemon can show a one-shot confirmation - the toggle
    itself does not depend on the OLED noticing it, and a failure to
    write the confirmation signal does not undo or block the actual
    toggle (that write is attempted, and logged if it fails, regardless
    of whether the confirmation signal succeeds)."""
    new_state = "off" if read_silly_enabled() else "on"
    try:
        with open(SILLY_FILE, "w") as f:
            f.write(f"{new_state}\n")
    except OSError as exc:
        log.warning("Could not write Silly Mode toggle (%s) - ignoring.", exc)
        return
    try:
        with open(SILLY_TOGGLE_REQUEST_FILE, "w") as f:
            f.write(f"{time.time()}\n")
    except OSError as exc:
        log.warning("Could not write silly-toggle confirmation signal (%s).", exc)


def on_pressed() -> None:
    """Fires on every press (short or the start of a long hold) - the
    ONLY place a pending single-tap window actually gets resolved. If
    one is currently running (from a previous release), cancel it
    immediately (so its single-tap action can never fire) and remember
    that THIS press decides the outcome: a quick release makes it a
    double-tap (see on_released()), a hold to HOLD_SECONDS discards it
    entirely (see on_held()). If no window is pending, this press might
    become a lone tap or a hold - either way, nothing to do yet."""
    global _pending_single_tap_timer, _awaiting_second_tap_resolution
    with _tap_lock:
        if _pending_single_tap_timer is not None:
            _pending_single_tap_timer.cancel()
            _pending_single_tap_timer = None
            _awaiting_second_tap_resolution = True
        else:
            _awaiting_second_tap_resolution = False


def on_held() -> None:
    """Fires exactly once after HOLD_SECONDS of continuous press
    (gpiozero's hold_repeat=False below). Sets `_hold_just_fired` and
    clears `_awaiting_second_tap_resolution` FIRST, before anything
    else - even if the shutdown call itself somehow raises, both flags
    are already in their final state, so the release that follows this
    can never be mistaken for a tap gesture of any kind. Clearing the
    second flag here is what makes "a pending first tap followed by a
    long hold" safe: the pending tap is silently discarded the moment
    this fires (well before HOLD_SECONDS could ever elapse for a
    genuinely short second tap), never producing a delayed single- or
    double-tap action once the hold/shutdown path is already running."""
    global _hold_just_fired, _awaiting_second_tap_resolution
    _hold_just_fired = True
    _awaiting_second_tap_resolution = False
    if SHUTDOWN_ENABLED:
        log.info(
            "Long press detected on GPIO%d (held %.0fs) - requesting shutdown.",
            GPIO_PIN, HOLD_SECONDS,
        )
        try:
            subprocess.run(
                ["sudo", "-n", "systemctl", "poweroff"],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except Exception as exc:
            # Fail safely and loudly: if the sudo grant is missing/
            # misconfigured, or the command itself fails, this is
            # logged and the daemon keeps running rather than crash-
            # looping - the button remains inert until whatever's wrong
            # is fixed, which is the safe failure direction here.
            log.error("Shutdown request FAILED: %s", exc)
    else:
        log.info(
            "LONG PRESS DETECTED - would request shutdown (no action taken; "
            "PIRATEBOX_BUTTON_ENABLE_SHUTDOWN is not set)."
        )


def on_released() -> None:
    """Fires on EVERY release, short or long - gpiozero does not
    distinguish.
      1. `_hold_just_fired` set -> the tail end of an already-handled
         long press: do nothing but clear the flag (mandatory ordering
         guarantee, see the module header).
      2. `_awaiting_second_tap_resolution` set -> this release completes
         what `on_pressed()` already recognized as the second half of a
         double-tap: fire the Silly Mode toggle, no single-tap action
         ever runs for either half of the gesture.
      3. Otherwise -> this MIGHT be a lone tap, but a second one could
         still follow within DOUBLE_TAP_WINDOW_S, so the single-tap
         action is not run yet - a `threading.Timer` is started, and
         only fires it if nothing cancels it first (see on_pressed())."""
    global _hold_just_fired, _awaiting_second_tap_resolution, _pending_single_tap_timer
    if _hold_just_fired:
        _hold_just_fired = False
        return

    if _awaiting_second_tap_resolution:
        _awaiting_second_tap_resolution = False
        toggle_silly_mode()
        return

    def fire_if_still_pending():
        # Runs on the Timer's own thread, so this specific check-and-
        # clear must happen under the same lock on_pressed() uses to
        # cancel it - otherwise a cancel() that loses a genuine race
        # against this callback already starting could let the single-
        # tap action fire anyway, right as a double-tap is also being
        # recognized. Identity-checked against `timer` (not just
        # None-ness) so a timer that already fired and was superseded
        # by a later one can never mistakenly clear the newer one's slot.
        global _pending_single_tap_timer
        with _tap_lock:
            if _pending_single_tap_timer is not timer:
                return
            _pending_single_tap_timer = None
        write_status_check_request()

    timer = threading.Timer(DOUBLE_TAP_WINDOW_S, fire_if_still_pending)
    with _tap_lock:
        _pending_single_tap_timer = timer
    timer.start()


def main() -> int:
    try:
        button = Button(
            GPIO_PIN,
            pull_up=True,
            bounce_time=DEBOUNCE_S,
            hold_time=HOLD_SECONDS,
            hold_repeat=False,
        )
    except Exception as exc:
        log.error("Could not claim GPIO%d: %s", GPIO_PIN, exc)
        return 1

    button.when_pressed = on_pressed
    button.when_held = on_held
    button.when_released = on_released

    log.info(
        "Started. Watching BCM GPIO%d (physical pin 22), %dms debounce, "
        "%.0fs hold threshold, %.0fms double-tap window. Real shutdown "
        "%s. Single tap -> %s. Double tap -> toggles Silly Mode (%s).",
        GPIO_PIN, int(DEBOUNCE_S * 1000), HOLD_SECONDS, DOUBLE_TAP_WINDOW_S * 1000,
        "ENABLED" if SHUTDOWN_ENABLED else "disabled (dry-run/log-only)",
        STATUS_CHECK_REQUEST_FILE, SILLY_FILE,
    )

    def handle_term(signum, frame):
        log.info("Stopping (signal %d).", signum)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_term)
    signal.signal(signal.SIGINT, handle_term)
    signal.pause()
    return 0


if __name__ == "__main__":
    sys.exit(main())
