#!/usr/bin/env python3
#
# Pi-side daemon for the ESP32-S3 hardware/sensor supervisor
# commissioned 2026-09-07 (docs/OPERATIONAL-DECISIONS.md). This is the
# ONLY process that ever opens the serial link to that board - exactly
# the same "one owner of the real hardware" discipline
# piratebox_bh1750.py already established for I2C, applied here to a
# persistent serial connection instead of a polled bus. See
# docs/ESP32-SUPERVISOR-DESIGN.md for the full protocol/architecture
# writeup; this file is the concrete implementation of that design.
#
# WHY A SEPARATE DAEMON, NOT A MODULE IMPORTED INTO piratebox_oled_
# daemon.py (the way piratebox_bh1750.py is): a serial port can only be
# held open by one process, and this link needs continuous reading
# (heartbeats/sensor pushes arrive on their own schedule from the
# firmware) rather than the occasional on-demand poll BH1750 uses -
# blocking on that inside the OLED daemon's own 3-second tick loop
# would stall display redraws. So this owns the connection exclusively
# and publishes a small cached export
# (/run/piratebox-esp32/esp32-public.json) that everything else reads -
# the exact same "cached export, not direct hardware access" pattern
# sensors-public.json already established, and for the same reason
# (see that file's own header for the full precedent).
#
# DEGRADE, NEVER CRASH, NEVER BLOCK CORE: this daemon runs as its own
# independent systemd service (piratebox-esp32-supervisor.service),
# unrelated to and un-depended-upon by any Core PirateBox service. If
# the ESP32 is unplugged, powered off, mid-reset, or was never
# connected at all, this daemon simply keeps polling for the device to
# (re)appear and the export reports "connected": false - nothing here
# can affect hostapd/dnsmasq/nginx/php-fpm/the OLED/RTC/BH1750.
#
# STABLE DEVICE IDENTITY, NOT A HARDCODED /dev/ttyACM0: Linux already
# creates a stable udev symlink for this exact USB-serial bridge under
# /dev/serial/by-id/ (confirmed present without any custom rule -
# standard udev behavior for any USB CDC-ACM device with a real serial
# number). KNOWN_BRIDGE_SERIAL below records the WCH CH9102 bridge's
# own serial number (a property of that physical bridge chip, not of
# the ESP32 silicon itself) - if this exact board/bridge is ever
# swapped for a different unit, update this one constant. A safe
# single-candidate fallback (scan for any WCH "USB_Single_Serial"
# bridge if the exact serial isn't found) exists for that transition
# period; more than one match is treated as genuinely ambiguous and
# refused rather than guessed.

import glob
import json
import logging
import os
import sys
import time

try:
    import serial  # pyserial - already present system-wide (confirmed 2026-09-07)
except Exception:  # noqa: BLE001 - must never prevent the daemon from starting/logging why
    serial = None

DEVICE_BY_ID_GLOB = "/dev/serial/by-id/*"
KNOWN_BRIDGE_SERIAL = "5CBB028993"  # WCH CH9102 bridge, commissioned 2026-09-07 - see docs/OPERATIONAL-DECISIONS.md
BAUD = 115200
SERIAL_READ_TIMEOUT_S = 1.0

PROTOCOL_VERSION = 1

EXPORT_DIR = "/run/piratebox-esp32"
EXPORT_FILE = EXPORT_DIR + "/esp32-public.json"
EXPORT_PUBLISH_INTERVAL_S = 5.0

# ~4x the firmware's own 2s heartbeat interval (protocol.h /
# HEARTBEAT_INTERVAL_MS) - tolerates a couple of missed/delayed
# heartbeats before declaring the link stale, without taking many
# seconds to notice a real drop.
HEARTBEAT_TIMEOUT_S = 8.0

RECONNECT_POLL_S = 2.0
RECONNECT_MAX_BACKOFF_S = 10.0

MAX_LINE_BYTES = 4096  # generous vs. the firmware's own 512-char cap; just a sanity ceiling

log = logging.getLogger("piratebox_esp32_supervisor")


# --- Device discovery --------------------------------------------------

def _select_device_path(known_serial, exists_fn, glob_fn):
    """Pure selection logic - testable without touching /dev. Returns a
    dict: {"path": str|None, "fallback": bool, "ambiguous": [str, ...]}.
    `ambiguous` is non-empty only when more than one WCH bridge is
    present and none matches `known_serial` - the caller must refuse to
    guess in that case, not silently pick the first one."""
    exact = f"/dev/serial/by-id/usb-1a86_USB_Single_Serial_{known_serial}-if00"
    if exists_fn(exact):
        return {"path": exact, "fallback": False, "ambiguous": []}

    candidates = sorted(p for p in glob_fn(DEVICE_BY_ID_GLOB) if "1a86_USB_Single_Serial" in p)
    if len(candidates) == 1:
        return {"path": candidates[0], "fallback": True, "ambiguous": []}
    if len(candidates) > 1:
        return {"path": None, "fallback": False, "ambiguous": candidates}
    return {"path": None, "fallback": False, "ambiguous": []}


def find_device_path():
    """Real (non-test) device discovery - logs clearly on fallback or
    ambiguity so an operator can see exactly why, instead of silent
    guessing or a bare 'not found'."""
    result = _select_device_path(KNOWN_BRIDGE_SERIAL, os.path.exists, glob.glob)
    if result["path"] and result["fallback"]:
        log.warning(
            "Configured bridge serial %s not found; falling back to the only "
            "WCH USB-serial bridge present: %s. If this board/bridge was "
            "intentionally swapped, update KNOWN_BRIDGE_SERIAL in this file.",
            KNOWN_BRIDGE_SERIAL, result["path"],
        )
    elif result["ambiguous"]:
        log.error(
            "Multiple WCH USB-serial bridges present and none match the "
            "configured serial %s - refusing to guess which is the ESP32 "
            "supervisor: %s", KNOWN_BRIDGE_SERIAL, result["ambiguous"],
        )
    return result["path"]


# --- State -----------------------------------------------------------

def fresh_state() -> dict:
    """A brand-new view of the supervisor - used at daemon startup and
    again every time a (re)connection is established, since a fresh
    connection means we know nothing about the other side yet until it
    tells us (a get_info request is sent immediately on connect - see
    run())."""
    return {
        "connected": False,
        "stale": False,
        "fw": None,
        "board": None,
        "mac": None,
        "reset_reason": None,
        "protocol_version": None,
        "uptime_ms": None,
        "caps": [],
        "sensors": {},
        "reboot_count": 0,
        "malformed_lines": 0,
        "last_remote_error": None,
        "last_heartbeat_monotonic": None,
        "last_hb_seq": None,
        "last_sensors_monotonic": None,
        "last_hello_monotonic": None,
        "last_seen_monotonic": None,
        "_warned_version": False,
    }


def handle_line(state: dict, raw: bytes, now: float) -> None:
    """Parses one line already read from the serial port (bytes,
    WITHOUT requiring a trailing newline - callers pass exactly what
    pyserial's readline() returned, newline included or not, either is
    fine since we strip it). Mutates `state` in place. Never raises -
    every failure mode (bad bytes, bad JSON, wrong shape, unknown
    fields) increments a counter and returns, exactly mirroring the
    firmware's own 'malformed input never crashes the loop' contract
    on the other end of this same link."""
    if not raw or len(raw) > MAX_LINE_BYTES:
        state["malformed_lines"] += 1
        return
    try:
        line = raw.decode("utf-8", errors="strict").strip()
    except UnicodeDecodeError:
        state["malformed_lines"] += 1
        return
    if not line:
        return
    try:
        msg = json.loads(line)
    except ValueError:
        state["malformed_lines"] += 1
        return
    if not isinstance(msg, dict):
        state["malformed_lines"] += 1
        return

    t = msg.get("t")
    if not isinstance(t, str):
        state["malformed_lines"] += 1
        return

    v = msg.get("v")
    if isinstance(v, int) and v > PROTOCOL_VERSION and not state["_warned_version"]:
        log.warning(
            "ESP32 supervisor speaks protocol v%s, newer than this daemon's v%s - "
            "reading known fields best-effort.", v, PROTOCOL_VERSION,
        )
        state["_warned_version"] = True

    state["connected"] = True
    state["stale"] = False
    state["last_seen_monotonic"] = now

    if t == "hello":
        new_uptime = msg.get("uptime_ms")
        prev_uptime = state.get("uptime_ms")
        rebooted = (
            state.get("board") is not None
            and isinstance(new_uptime, (int, float))
            and isinstance(prev_uptime, (int, float))
            and new_uptime < prev_uptime
        )
        if rebooted:
            state["reboot_count"] += 1
            log.warning(
                "ESP32 supervisor rebooted (uptime reset) - reset_reason=%s",
                msg.get("reset_reason"),
            )
        state["fw"] = msg.get("fw")
        state["board"] = msg.get("board")
        state["mac"] = msg.get("mac")
        state["reset_reason"] = msg.get("reset_reason")
        state["uptime_ms"] = new_uptime
        state["protocol_version"] = v
        caps = msg.get("caps")
        state["caps"] = caps if isinstance(caps, list) else []
        state["last_hello_monotonic"] = now
    elif t == "hb":
        state["last_heartbeat_monotonic"] = now
        seq = msg.get("seq")
        if isinstance(seq, (int, float)):
            state["last_hb_seq"] = seq
        up = msg.get("uptime_ms")
        if isinstance(up, (int, float)):
            state["uptime_ms"] = up
    elif t == "sensors":
        readings = msg.get("readings")
        if isinstance(readings, dict):
            state["sensors"] = readings
            state["last_sensors_monotonic"] = now
    elif t == "pong":
        pass  # reserved for a future latency/liveness check - not consumed yet
    elif t == "err":
        state["last_remote_error"] = msg.get("reason")
        log.debug("ESP32 supervisor reported a protocol error: %s", msg.get("reason"))
    # else: an unrecognized type from newer firmware - ignored per the
    # protocol's own extensibility contract (docs/ESP32-SUPERVISOR-
    # DESIGN.md), not treated as malformed.


def check_staleness(state: dict, now: float) -> None:
    """Call every loop iteration regardless of whether a line was just
    read. A supervisor that stops sending heartbeats (crashed without
    resetting cleanly, or a comms fault) is 'stale' - still logically
    the last-known device, but its readings must no longer be presented
    as current."""
    if not state["connected"]:
        return
    last = state.get("last_heartbeat_monotonic")
    if last is None:
        return
    if now - last > HEARTBEAT_TIMEOUT_S and not state["stale"]:
        log.warning("No heartbeat from ESP32 supervisor in %.1fs - marking stale.", now - last)
        state["stale"] = True


def build_export(state: dict, now_wall: float) -> dict:
    return {
        "generated_at": int(now_wall),
        "connected": bool(state["connected"]),
        "stale": bool(state["stale"]),
        "fw_version": state.get("fw"),
        "protocol_version": state.get("protocol_version"),
        "board": state.get("board"),
        "mac": state.get("mac"),
        "reset_reason": state.get("reset_reason"),
        "uptime_ms": state.get("uptime_ms"),
        "reboot_count": state.get("reboot_count", 0),
        "capabilities": state.get("caps", []),
        "sensors": state.get("sensors", {}),
        "malformed_lines": state.get("malformed_lines", 0),
    }


def publish_export(state: dict, last_publish: float, now: float, now_wall: float = None) -> float:
    """Coalesced write, same throttle pattern as piratebox_oled_daemon.
    publish_sensors_export(). `now` is monotonic (throttle bookkeeping),
    `now_wall` is wall-clock for the generated_at field (defaults to
    time.time(), injectable for tests)."""
    if now - last_publish < EXPORT_PUBLISH_INTERVAL_S:
        return last_publish
    if now_wall is None:
        now_wall = time.time()

    export = build_export(state, now_wall)
    try:
        os.makedirs(EXPORT_DIR, exist_ok=True)
        tmp_path = f"{EXPORT_FILE}.tmp.{os.getpid()}"
        with open(tmp_path, "w") as f:
            json.dump(export, f)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, EXPORT_FILE)
    except OSError:
        pass  # optional export - never worth crashing the daemon over

    return now


# --- Main loop ---------------------------------------------------------

def run() -> None:
    if serial is None:
        log.error("pyserial is not importable - this daemon cannot function. "
                   "Exiting cleanly (systemd Restart= will retry).")
        sys.exit(1)

    state = fresh_state()
    ser = None
    current_path = None
    last_export_publish = 0.0
    next_reconnect_attempt = 0.0
    backoff = RECONNECT_POLL_S

    log.info("ESP32 supervisor daemon starting.")

    while True:
        now = time.monotonic()

        if ser is None:
            if now >= next_reconnect_attempt:
                path = find_device_path()
                if path:
                    try:
                        ser = serial.Serial(path, BAUD, timeout=SERIAL_READ_TIMEOUT_S)
                        current_path = path
                        state = fresh_state()
                        log.info("Connected to ESP32 supervisor at %s.", path)
                        # A fresh connection knows nothing yet - ask
                        # immediately rather than waiting for the
                        # firmware's own boot-time-only hello (which we
                        # may have missed if the ESP32 was already
                        # running before this daemon started/restarted).
                        ser.write(json.dumps({"v": PROTOCOL_VERSION, "t": "get_info"}).encode("utf-8") + b"\n")
                        backoff = RECONNECT_POLL_S
                    except (OSError, serial.SerialException) as exc:
                        log.warning("Failed to open %s: %s", path, exc)
                        ser = None
                if ser is None:
                    backoff = min(backoff * 1.5, RECONNECT_MAX_BACKOFF_S)
                    next_reconnect_attempt = now + backoff
        else:
            if current_path and not os.path.exists(current_path):
                log.warning("Serial device %s disappeared - disconnecting.", current_path)
                try:
                    ser.close()
                except Exception:  # noqa: BLE001
                    pass
                ser = None
                current_path = None
                state["connected"] = False
                next_reconnect_attempt = now
            else:
                try:
                    raw = ser.readline()
                except (OSError, serial.SerialException) as exc:
                    log.warning("Serial error (%s) - disconnecting.", exc)
                    try:
                        ser.close()
                    except Exception:  # noqa: BLE001
                        pass
                    ser = None
                    current_path = None
                    state["connected"] = False
                    next_reconnect_attempt = now
                else:
                    if raw:
                        handle_line(state, raw, now)

        check_staleness(state, now)
        last_export_publish = publish_export(state, last_export_publish, now)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    run()
