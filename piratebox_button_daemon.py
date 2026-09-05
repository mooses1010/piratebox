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
#   - A short press (released before HOLD_SECONDS) writes a small,
#     non-persistent timestamp to STATUS_CHECK_REQUEST_FILE (2026-09-04,
#     "OLED cadence rebalance" round) - see that constant's own comment
#     for the full design. This is the ONLY thing a short press does:
#     no OLED rendering knowledge lives in this file, no direct call
#     into the display daemon - just "the button was tapped, at time T,"
#     for some other process to interpret however it likes. This keeps
#     the same "GPIO daemon has exactly one job" shape this file already
#     had for the long-press/shutdown path, and means a future second
#     button, a CLI command, or an admin-UI action could produce the
#     exact same signal without this file changing at all.
#   - CRITICAL, load-bearing ordering guarantee: a long press that
#     triggers shutdown must NEVER also produce the short-press signal
#     on release. gpiozero fires `when_released` on every release,
#     including one that follows an already-fired `when_held` - so
#     `on_released()` below checks a plain in-memory flag `on_held()`
#     sets, and does nothing at all if it's set (clearing it for next
#     time) rather than writing the request file. A short press never
#     sets that flag, so it can never suppress itself - only an actual
#     completed long-press/shutdown-trigger can suppress the release
#     action that would otherwise follow it.
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
import time

from gpiozero import Button

GPIO_PIN = 25
DEBOUNCE_S = 0.05
HOLD_SECONDS = 4.0
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s piratebox-button: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("piratebox-button")


_hold_just_fired = False   # see on_released() below - the one flag that
                            # makes "long press -> shutdown" and "short
                            # press -> status-check signal" mutually
                            # exclusive on the SAME physical release event


def on_held() -> None:
    """Fires exactly once after HOLD_SECONDS of continuous press
    (gpiozero's hold_repeat=False below). Sets `_hold_just_fired` FIRST,
    before anything else - even if the shutdown call itself somehow
    raises, the flag is already set, so the release that follows this
    (however this function exits) can never be mistaken for a short
    press."""
    global _hold_just_fired
    _hold_just_fired = True
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
    distinguish. If `_hold_just_fired` is set, this release is the tail
    end of an already-handled long press: do nothing but clear the flag,
    per the mandatory "long hold must not also fire the short-press
    action" requirement. Otherwise, this is a genuine short press-and-
    release: write the status-check request file. A short press can
    never itself set `_hold_just_fired` (only HOLD_SECONDS of continuous
    press does, via on_held() above), so this direction of the guarantee
    - "a short press must never risk shutdown" - was already true before
    this function existed; on_released() only ever writes a plain
    timestamp file, never anything privilege-related."""
    global _hold_just_fired
    if _hold_just_fired:
        _hold_just_fired = False
        return
    try:
        with open(STATUS_CHECK_REQUEST_FILE, "w") as f:
            f.write(f"{time.time()}\n")
    except OSError as exc:
        # Same fail-safe direction as everywhere else in this file: a
        # write failure here degrades to "the short press did nothing
        # visible," never a crash, never retried in a tight loop.
        log.warning("Could not write status-check request (%s) - ignoring.", exc)


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

    button.when_held = on_held
    button.when_released = on_released
    # Deliberately no when_pressed handler - nothing needs to react to
    # the press itself, only to how it resolves (held to the threshold,
    # or released before it).

    log.info(
        "Started. Watching BCM GPIO%d (physical pin 22), %dms debounce, "
        "%.0fs hold threshold. Real shutdown %s. Short press writes a "
        "status-check request to %s.",
        GPIO_PIN, int(DEBOUNCE_S * 1000), HOLD_SECONDS,
        "ENABLED" if SHUTDOWN_ENABLED else "disabled (dry-run/log-only)",
        STATUS_CHECK_REQUEST_FILE,
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
