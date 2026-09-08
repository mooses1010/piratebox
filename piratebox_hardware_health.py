#!/usr/bin/env python3
#
# Shared hardware-health classification (2026-09-08, PirateBox-wide
# hardware-awareness integration phase). Answers exactly one question,
# for exactly the ESP32-supervised sensors this project currently owns:
# "can I communicate with this sensor/subsystem right now, and should I
# trust what it's reporting?" - nothing more.
#
# VOCABULARY: reuses, rather than reinvents, var/www/html/includes/
# capability_state.php's existing five-value model verbatim (see that
# file's own header for the canonical definitions - this module mirrors
# them so an operator reading both a web page and a Python diagnostic
# never has to learn two different words for the same idea):
#   NOT_INSTALLED - the capability/hardware does not exist on this device.
#   AVAILABLE     - present and working normally.
#   DEGRADED      - present, but reporting a real problem.
#   UNAVAILABLE   - should be reporting but currently isn't.
#   UNKNOWN       - not enough information to say anything else.
#
# WHY THIS MODULE EXISTS: a 2026-09-08 whole-project audit found the
# "is this reading connected/fresh" reduction independently
# reimplemented at least five times (piratebox_esp32_client.py itself,
# piratebox_esp32_bh1750.py, piratebox_oled_daemon.py,
# tools/ds18b20_commission.py, tools/diagnose_esp32_supervisor.py; plus
# two more in PHP). This module does NOT replace any of those - it adds
# ONE small classification layer on top of the diagnostics dict
# piratebox_esp32_client.get_diagnostics() already produces (the
# established canonical connected/stale reducer), so callers that need
# a HEALTH STATE for display (admin capability table, OLED fault
# surfacing, diagnostics tooling) stop each writing their own ad hoc
# if/elif chain. Every function here is pure - takes an already-fetched
# diagnostics dict, does no file/network I/O itself - so all of this is
# directly unit-testable without touching the real export file.
#
# SENSOR HEALTH vs. ROLE/POLICY HEALTH - a deliberate, load-bearing
# distinction (see docs/ESP32-SUPERVISOR-DESIGN.md's hardware-awareness
# section for the full rationale): this module answers only "can I
# trust this reading right now" (SENSOR HEALTH). It has NO concept of
# what a sensor is physically attached to, or whether a given value is
# safe for that attachment (ROLE/POLICY HEALTH) - because as of this
# phase, the five commissioned DS18B20 probes have no physical role
# assigned yet (piratebox_ds18b20_roles.py's `role` field exists,
# reserved, and is always None today). Do NOT add temperature
# thresholds ("too hot for a battery", "enclosure critical") to this
# module - a future role-policy layer, once real roles exist, should
# read THIS module's output as one of its own inputs, not be folded
# into it.

STATES = ("NOT_INSTALLED", "AVAILABLE", "DEGRADED", "UNAVAILABLE", "UNKNOWN")


def classify_esp32_supervisor(diag: dict) -> str:
    """The link itself - is the ESP32 supervisor daemon publishing a
    fresh export, and is the board's own heartbeat current? Every other
    classifier in this module calls this first and inherits its result
    when it isn't AVAILABLE, since no sensor behind a broken/uncertain
    link can be assessed on its own."""
    if not isinstance(diag, dict):
        return "UNKNOWN"
    if diag.get("reason") == "no_export":
        # The export has never been read successfully - could mean the
        # daemon was never installed, or simply hasn't published its
        # first cycle yet. Genuinely not enough information to say
        # "not installed" (a real architectural fact elsewhere in this
        # project's vocabulary) vs. "temporarily unavailable" - honest
        # UNKNOWN, matching capability_state.php's own precedent for
        # exactly this situation (e.g. time_confidence when the status
        # helper snapshot itself is missing).
        return "UNKNOWN"
    connected = bool(diag.get("connected"))
    stale = bool(diag.get("stale"))
    if connected and not stale:
        return "AVAILABLE"
    if connected and stale:
        # Serial link open, but the board's own heartbeat has gone
        # quiet - present, reporting a real problem, not yet a full
        # disconnect.
        return "DEGRADED"
    return "UNAVAILABLE"


def classify_simple_sensor(diag: dict, capability: str) -> str:
    """For a sensor whose export shape is one flat {ok, value, unit}
    dict directly under sensors[capability] - covers both temp_internal
    and bh1750 today; any future single-value ESP32 sensor (e.g.
    BME280's individual fields) fits the same shape without a new
    function."""
    link_state = classify_esp32_supervisor(diag)
    if link_state != "AVAILABLE":
        return link_state
    if capability not in (diag.get("capabilities") or []):
        return "NOT_INSTALLED"
    reading = (diag.get("sensors") or {}).get(capability)
    if not isinstance(reading, dict):
        # Capability was advertised in the hello/capabilities list but
        # this particular sensors message didn't carry it - genuinely
        # can't say more than "don't know right now."
        return "UNKNOWN"
    return "AVAILABLE" if reading.get("ok") else "DEGRADED"


def classify_ds18b20_bus(diag: dict, commissioned_roms=()) -> dict:
    """The 1-Wire bus as a whole, aware of which ROM addresses this
    device has ever physically commissioned (see piratebox_ds18b20_
    roles.commissioned_roms()) - the basis for a genuine "expected
    commissioned probe missing" health signal, without needing any
    functional role to exist. Returns a detail dict, not just a bare
    state string, so a caller (admin table, OLED, diagnostics) can
    render specifics without re-deriving any of this itself:

        {"state": ..., "bus_ok": bool|None, "probes_ok": int,
         "probes_expected": int, "missing_commissioned": [rom, ...],
         "failing_commissioned": [rom, ...]}

    `missing_commissioned` = a commissioned ROM absent from this
    cycle's probes entirely. `failing_commissioned` = a commissioned
    ROM present but reporting ok=False (disconnected/CRC/suspect value
    - the firmware's own job, not re-diagnosed here)."""
    commissioned_roms = set(commissioned_roms or ())
    base = {
        "bus_ok": None,
        "probes_ok": 0,
        "probes_expected": len(commissioned_roms),
        "missing_commissioned": [],
        "failing_commissioned": [],
    }

    link_state = classify_esp32_supervisor(diag)
    if link_state != "AVAILABLE":
        return {"state": link_state, **base}

    if "ds18b20" not in (diag.get("capabilities") or []):
        # This firmware build has never found a probe on this bus at
        # all - genuinely nothing to report if nothing was ever
        # commissioned either; a regression (UNAVAILABLE) if this
        # device previously had commissioned identities and the
        # capability itself has now vanished.
        state = "UNAVAILABLE" if commissioned_roms else "NOT_INSTALLED"
        return {"state": state, **base}

    ds18b20 = (diag.get("sensors") or {}).get("ds18b20")
    if not isinstance(ds18b20, dict):
        return {"state": "UNKNOWN", **base}

    bus_ok = ds18b20.get("bus_ok")
    probes = ds18b20.get("probes") if isinstance(ds18b20.get("probes"), dict) else {}
    probes_ok = sum(1 for r in probes.values() if isinstance(r, dict) and r.get("ok"))
    missing = sorted(commissioned_roms - set(probes.keys()))
    failing = sorted(
        rom for rom in commissioned_roms
        if rom in probes and not (isinstance(probes[rom], dict) and probes[rom].get("ok"))
    )
    detail = {
        "bus_ok": bus_ok,
        "probes_ok": probes_ok,
        "probes_expected": len(commissioned_roms),
        "missing_commissioned": missing,
        "failing_commissioned": failing,
    }

    if bus_ok is False:
        # Firmware's own semantics: false only when probes were
        # previously found and the bus now finds none - a genuine
        # regression, never "never wired."
        return {"state": "UNAVAILABLE", **detail}
    if missing or failing:
        return {"state": "DEGRADED", **detail}
    if not commissioned_roms and not probes:
        # bus_ok is true both when healthy AND when genuinely never
        # wired (see esp32-firmware/src/ds18b20.cpp) - zero probes
        # AND nothing ever commissioned is the "never wired" case.
        return {"state": "NOT_INSTALLED", **detail}
    return {"state": "AVAILABLE", **detail}
