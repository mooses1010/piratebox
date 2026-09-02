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
#   - A short press/tap does absolutely nothing - not even a log line.
#     There is no code path from a short press to any action.
#   - A press held continuously for HOLD_SECONDS (4.0s) triggers exactly
#     once: it logs one line and then requests a clean shutdown via
#     `sudo -n systemctl poweroff`. Holding longer than the threshold
#     does not re-trigger (hold_repeat=False) - matching Stage 29 §3's
#     "no countdown-abort undo after zero, but no repeated action either"
#     design.
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s piratebox-button: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("piratebox-button")


def on_held() -> None:
    """Fires exactly once after HOLD_SECONDS of continuous press
    (gpiozero's hold_repeat=False below) - never on a short tap, which
    has no callback wired to it at all."""
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
    # Deliberately no when_pressed/when_released handler at all - a
    # short press has no code path to anything, consequential or not.

    log.info(
        "Started. Watching BCM GPIO%d (physical pin 22), %dms debounce, "
        "%.0fs hold threshold. Real shutdown %s.",
        GPIO_PIN, int(DEBOUNCE_S * 1000), HOLD_SECONDS,
        "ENABLED" if SHUTDOWN_ENABLED else "disabled (dry-run/log-only)",
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
