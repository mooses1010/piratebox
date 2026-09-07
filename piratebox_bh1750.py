#!/usr/bin/env python3
#
# BH1750 ambient light sensor reader - a single, narrow module owning
# ALL direct I2C access to this specific sensor. Mirrors piratebox_
# expressions.py's own "one concern per file" rationale, applied to
# hardware instead of drawing: this is the ONLY file in the project
# that should ever import smbus2 or reference address 0x23 for this
# sensor.
#
# HARDWARE (commissioned 2026-09-07): BH1750FVI ambient light sensor,
# wired onto I2C bus 1 - the same bus already shared by the SSD1306
# OLED (0x3c) and the DS3231 RTC (0x68), multi-drop, no conflict,
# confirmed live via `i2cdetect` alongside both of those still healthy.
# ADDR is left unconnected on this board -> address 0x23 (confirmed
# live via i2cdetect AND by successfully round-tripping the real
# BH1750 protocol - power-on, one-time high-res measurement, a
# plausible non-zero/non-garbage lux value - not assumed from the
# address alone). See docs/HARDWARE-INTEGRATION-DESIGN.md for the full
# wiring record.
#
# WHY A SEPARATE MODULE, AND WHY THIS MATTERS FOR A FUTURE ESP32-S3
# MIGRATION: docs/CAPABILITY-REGISTRY.md already lists a possible
# future "remote microcontroller/sensor node" (a hardware supervisor
# that could one day sit between sensors like this one and the Pi,
# e.g. over UART/serial instead of direct I2C) as a CANDIDATE, concept
# only - NOT implemented, NOT started by this round. Keeping every
# direct-I2C detail (bus number, address, opcodes, timing, rate
# limiting) inside this one file, behind a single zero-argument
# `read_ambient_lux()` function, means that IF that migration ever
# happens, only this file's internals need to change (e.g. read a
# value over serial instead of I2C) - piratebox_progression.py's
# HARDWARE_SIGNALS registry, and every consumer of
# ctx["hardware"]["ambient_lux"], stay identical either way. This is a
# design property being preserved now, not a project being started.
#
# RATE-LIMITED BY DESIGN, NOT BY ACCIDENT: piratebox_oled_daemon.py
# ticks every REFRESH_SECONDS=3s and calls piratebox_progression.
# read_hardware_signals() (and therefore this module's reader) every
# single tick. A real BH1750 one-time measurement blocks for up to
# ~180ms (datasheet) - issuing one on every 3-second tick, forever,
# would needlessly load the I2C bus this sensor shares with the OLED
# and RTC, and briefly stall each OLED redraw, for a physical quantity
# (ambient light) that changes slowly in ordinary use. This module
# caches the last successful reading and only performs a real I2C
# transaction every MIN_READ_INTERVAL_S - the reader function's own
# contract (zero-argument, JSON-safe return or None) is unchanged
# either way, so callers never need to know this is happening.
#
# DEGRADE, NEVER CRASH: any I2C failure (sensor unplugged, bus error,
# smbus2 missing, wrong/no ACK from the address) is caught here and
# reported as None - the same "honest missing value, never fabricated"
# discipline piratebox_progression.py's own HARDWARE_SIGNALS docstring
# already requires of every reader. Importing this module, calling its
# reader, or the sensor being entirely absent must never raise past
# this file's own boundary - nothing here can affect OLED rendering,
# the RTC, or any core PirateBox service either way.

import time

try:
    import smbus2
except Exception:  # noqa: BLE001 - smbus2 itself might not be installed
    smbus2 = None

I2C_BUS = 1
ADDRESS = 0x23              # confirmed live, 2026-09-07 - see module header
POWER_ON = 0x01
ONE_TIME_HIGH_RES_MODE = 0x20
MEASURE_DELAY_S = 0.2        # datasheet: up to ~180ms conversion time
MIN_READ_INTERVAL_S = 15.0   # bounds real I2C traffic - see module header
STALE_AFTER_S = 120.0        # a cached value older than this reports as None,
                              # not a silently-aging number

# Module-level cache, deliberately simple (single sensor, single
# daemon, no threads) - mirrors the plain-globals style already used
# elsewhere in this project's small hardware daemons rather than
# introducing a class for one sensor.
_last_attempt_at = 0.0
_last_success_at = None
_last_lux = None
_last_error = None


def _read_raw_lux() -> float:
    """Exactly one real I2C transaction - power on, request a one-time
    high-resolution measurement, wait for it, read the 2-byte result.
    Raises on any failure; never called directly by anything outside
    this module except its own CLI smoke test below."""
    if smbus2 is None:
        raise RuntimeError("smbus2 not available")
    bus = smbus2.SMBus(I2C_BUS)
    try:
        bus.write_byte(ADDRESS, POWER_ON)
        bus.write_byte(ADDRESS, ONE_TIME_HIGH_RES_MODE)
        time.sleep(MEASURE_DELAY_S)
        data = bus.read_i2c_block_data(ADDRESS, 0x00, 2)
    finally:
        bus.close()
    raw = (data[0] << 8) | data[1]
    return raw / 1.2  # BH1750 datasheet's own raw-to-lux formula


def _fresh_enough(now: float) -> bool:
    return _last_success_at is not None and (now - _last_success_at) <= STALE_AFTER_S


def read_ambient_lux():
    """The HARDWARE_SIGNALS reader - register this with
    piratebox_progression.register_hardware_signal("ambient_lux", ...).
    Zero-argument, returns a float lux value, or None if the sensor has
    never been read successfully (or that success has gone stale) -
    never raises, never fabricates a value. Uses time.monotonic() for
    its own internal rate-limit/staleness bookkeeping specifically
    because it is immune to wall-clock jumps (NTP corrections, or the
    RTC's own boot-time hctosys sync) - this module has no reason to
    care what the wall-clock date is, only how much real time has
    elapsed."""
    global _last_attempt_at, _last_success_at, _last_lux, _last_error
    now = time.monotonic()
    if now - _last_attempt_at < MIN_READ_INTERVAL_S:
        return _last_lux if _fresh_enough(now) else None
    _last_attempt_at = now
    try:
        lux = round(_read_raw_lux(), 1)
        _last_lux = lux
        _last_success_at = now
        _last_error = None
        return lux
    except Exception as exc:  # noqa: BLE001 - hardware can fail in any way
        _last_error = f"{type(exc).__name__}: {exc}"
        return _last_lux if _fresh_enough(now) else None


def get_diagnostics() -> dict:
    """Human/machine-readable snapshot for operator diagnostics (see
    tools/diagnose_bh1750.py) - answers exactly the questions that
    matter for this sensor: is it installed/responding, what's the
    current reading, how stale is it, and what (if anything) went
    wrong last. Never called from the hot per-tick path."""
    now = time.monotonic()
    return {
        "i2c_bus": I2C_BUS,
        "address": f"0x{ADDRESS:02x}",
        "detected": _last_success_at is not None,
        "lux": _last_lux,
        "last_success_seconds_ago": None if _last_success_at is None else round(now - _last_success_at, 1),
        "stale": not _fresh_enough(now),
        "last_error": _last_error,
    }


if __name__ == "__main__":
    # Standalone manual smoke test - bypasses the rate limiter (a
    # direct _read_raw_lux() call) since a human running this by hand
    # wants an immediate real reading, not a cached one. Not imported
    # by anything, not part of the daemon's own startup path - see
    # tools/diagnose_bh1750.py for the fuller operator-facing check.
    print(f"Reading BH1750 directly on i2c bus {I2C_BUS}, address 0x{ADDRESS:02x}...")
    try:
        lux = round(_read_raw_lux(), 1)
        print(f"lux = {lux}")
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {type(exc).__name__}: {exc}")
