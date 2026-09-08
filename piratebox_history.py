#!/usr/bin/env python3
#
# Lightweight sensor history / retention engine (2026-09-08). Answers
# "what have the sensors been doing over time" as a small, bounded,
# embedded-system time-series feature - deliberately NOT Grafana/
# Prometheus/InfluxDB/a general telemetry stack. One small JSON file
# per SIGNAL (never per probe-label, never per role - see IDENTITY
# below), each holding three bounded tiers (raw/hourly/daily), written
# atomically, pruned on every write. No database: this project has
# none by design (README/ARCHITECTURE.md; piratebox_ds18b20_roles.py's
# own header makes the same point for exactly this reason), and the
# actual data volume here (a handful of signals, one sample every five
# minutes) never approaches a scale where that tradeoff would flip -
# see docs/ESP32-SUPERVISOR-DESIGN.md's history section for the sizing
# math this module was designed against.
#
# WHERE SAMPLES COME FROM: this module NEVER reads a sensor, opens I2C/
# 1-Wire/serial, or touches piratebox_esp32_client.py directly - it is
# a pure storage/retention engine. piratebox_history_sampler.py (the
# systemd-timer-triggered oneshot script) is the one caller that reads
# the already-cached ESP32 export and decides what's currently valid to
# record, using piratebox_hardware_health.py's existing classifiers -
# this module never introduces new sensor polling of any kind.
#
# IDENTITY: every signal is keyed by a PERMANENT, machine-stable
# identifier - never a cosmetic display label, never a physical role.
#   "ambient_lux"           - BH1750
#   "esp32_temp_internal"   - ESP32-S3's own on-die sensor
#   "ds18b20_<romhex>"      - one per DS18B20 ROM address (permanent
#                             hardware identity - see piratebox_ds18b20_
#                             roles.py's own header on why ROM, never a
#                             name or physical_index, is the identity
#                             key). Renaming a probe, or one day giving
#                             it a functional role, NEVER changes this
#                             key or forks its history - label
#                             resolution happens only at query/display
#                             time (see includes/history.php), reading
#                             the SAME roles data the live Environment
#                             page already uses.
# A future sensor (BME280, INA226, ...) fits this scheme with a new
# signal_id and zero changes to this module - see EXTENSIBILITY below.
#
# RETENTION (a starting point, not a rigid law - see module constants):
#   raw     5-minute-ish samples, kept  7 days  (~2016 points/signal)
#   hourly  min/avg/max/count,    kept 90 days  (~2160 points/signal)
#   daily   min/avg/max/count,    kept  1 year  (~365  points/signal)
# Compaction happens as a side effect of recording a new raw sample
# (record_sample()) - there is no separate compaction daemon/timer.
# Every step is a pure function over already-loaded data (append_raw_
# sample/compact_hourly/compact_daily), directly unit-testable without
# any file I/O, then one atomic (temp+rename) write per signal per
# sampler run - a handful of small writes every 5 minutes, not a
# database, not a high-frequency logger.
#
# GAPS ARE HONEST: a sensor that was stale/invalid/unavailable simply
# has no sample recorded for that interval - never a fabricated/
# sentinel value, never a straight-line interpolation. The chart
# renderer (public/assets/history-chart.js) breaks its line across any
# gap wider than a couple of sampling intervals, so an outage reads as
# an outage, not a smooth transition.
#
# CLOCK HANDLING: samples must stay in non-decreasing chronological
# order within a signal's own file. A wall-clock step backward (NTP
# correction, RTC glitch) or a duplicate/near-duplicate timestamp
# (MIN_SAMPLE_GAP_SECONDS) is never inserted - see append_raw_sample()'s
# own comment. A reboot gap needs no special handling at all: it is
# simply an absence of raw samples for that span, which naturally
# renders as a gap and is naturally skipped by the hourly/daily
# compaction (nothing to summarize for an hour with zero raw samples).
#
# EXTENSIBILITY: adding a new simple {ok,value,unit}-shaped sensor
# (BME280 temperature/humidity/pressure, INA226 voltage/current, a 6th
# DS18B20 probe) never touches this module - only piratebox_history_
# sampler.py's own small signal list grows by one entry each. This
# module's storage/retention/query logic is 100% signal-id-agnostic.

import json
import os

HISTORY_DIR = "/var/lib/piratebox-history"
SCHEMA_VERSION = 1

RAW_RETENTION_SECONDS = 7 * 86400        # 7 days
HOURLY_RETENTION_SECONDS = 90 * 86400    # 90 days
DAILY_RETENTION_SECONDS = 365 * 86400    # 1 year

# A DS18B20/BH1750/ESP32-temp reading changes slowly - nothing here
# needs samples closer together than this. Also the guard that makes a
# stray double-invocation (e.g. manual testing, an overlapping systemd
# timer run) a safe no-op rather than a duplicate/near-duplicate point.
# Comfortably below the ~300s (5 min) target sampling interval so a
# normally-scheduled run is never itself rejected.
MIN_SAMPLE_GAP_SECONDS = 60

DS18B20_SIGNAL_PREFIX = "ds18b20_"


def ds18b20_signal_id(rom: str) -> str:
    """The permanent, machine-stable signal id for one DS18B20 ROM."""
    return f"{DS18B20_SIGNAL_PREFIX}{rom}"


def is_ds18b20_signal_id(signal_id: str) -> bool:
    return isinstance(signal_id, str) and signal_id.startswith(DS18B20_SIGNAL_PREFIX)


def ds18b20_rom_from_signal_id(signal_id: str):
    """Returns the ROM address, or None if this isn't a ds18b20 signal id."""
    if not is_ds18b20_signal_id(signal_id):
        return None
    return signal_id[len(DS18B20_SIGNAL_PREFIX):]


def _is_safe_signal_id(signal_id) -> bool:
    """Directly used as a filename component - reject anything that
    could escape HISTORY_DIR or collide with a non-history file. A
    signal id is always machine-generated (never user input), but this
    module never trusts that without checking anyway."""
    return (
        isinstance(signal_id, str)
        and 1 <= len(signal_id) <= 128
        and all(c.isalnum() or c in "_-" for c in signal_id)
    )


def signal_file_path(signal_id: str) -> str:
    if not _is_safe_signal_id(signal_id):
        raise ValueError(f"unsafe signal id: {signal_id!r}")
    return os.path.join(HISTORY_DIR, f"{signal_id}.json")


def _empty_history() -> dict:
    return {"schema_version": SCHEMA_VERSION, "raw": [], "hourly": [], "daily": []}


def load_signal_history(signal_id: str) -> dict:
    """Never raises. Missing/corrupt/wrong-shaped data degrades to an
    empty history - same "honest missing value, never fabricate, never
    crash" discipline as every other durable reader in this project
    (piratebox_progression.py's load_state(), piratebox_ds18b20_roles.
    load_roles(), etc.). A signal with no file yet simply has no
    history yet - not an error."""
    try:
        with open(signal_file_path(signal_id)) as f:
            data = json.load(f)
    except (OSError, ValueError, TypeError):
        return _empty_history()
    if not isinstance(data, dict):
        return _empty_history()
    out = _empty_history()
    for tier in ("raw", "hourly", "daily"):
        entries = data.get(tier)
        if isinstance(entries, list):
            out[tier] = [e for e in entries if isinstance(e, dict) and isinstance(e.get("t"), (int, float))]
    return out


def save_signal_history(signal_id: str, history: dict) -> None:
    """Atomic write (temp file + rename) - the same pattern used
    throughout this project's other durable JSON files. A crash/power
    loss mid-write leaves either the old file intact or the new one
    fully written - never a half-written, corrupt file. The temp file
    name includes the PID so two overlapping writers (shouldn't happen
    - this is a oneshot timer job - but never assumed) can't clobber
    each other's in-progress temp file.

    Explicit 0644 (world-readable): this file is written by the
    piratebox-gpio account (the sampler's own service user) but read
    directly by PHP-FPM (www-data) for the Environment page's history
    graphs - a different account, not a group-membership peer, so this
    deliberately mirrors the existing root-writes/PHP-reads pattern
    already used for var/www/html/data/device-history.json, rather
    than the group-writable 0770 pattern piratebox_ds18b20_roles.py
    uses (that one grants a group PEER write access; this one only
    ever needs a different account to READ). Sidesteps process umask
    entirely rather than assuming it happens to be permissive enough."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = signal_file_path(signal_id)
    tmp_path = f"{path}.tmp.{os.getpid()}"
    with open(tmp_path, "w") as f:
        json.dump(history, f, separators=(",", ":"))
    os.chmod(tmp_path, 0o644)
    os.replace(tmp_path, path)


def append_raw_sample(history: dict, now: float, value: float) -> dict:
    """Pure function: returns a NEW history dict with one more raw
    sample appended, or the SAME history (by value) if `now` doesn't
    represent forward progress - never mutates the input, never raises
    on a bad `now`/`value` (returns history unchanged).

    Rejects (silently, not an error - just "nothing to record this
    call"):
      - a non-finite/non-numeric value
      - now <= the last recorded raw sample's timestamp (clock stepped
        backward, or a duplicate/near-duplicate call) - chronological
        order within one signal's file is a hard invariant everything
        else here (compaction, range queries) relies on
      - now - last_t < MIN_SAMPLE_GAP_SECONDS (an accidental
        closely-spaced re-run - not a real new sample)

    Also prunes raw entries older than RAW_RETENTION_SECONDS (relative
    to `now`) - pruning happens on every append, so the file never
    grows past its bound even if compaction into hourly/daily is ever
    skipped for some reason."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return history
    try:
        value = float(value)
    except (TypeError, ValueError):
        return history
    if value != value or value in (float("inf"), float("-inf")):  # NaN/inf guard
        return history

    raw = history.get("raw", [])
    last_t = raw[-1]["t"] if raw else None
    if last_t is not None and now - last_t < MIN_SAMPLE_GAP_SECONDS:
        return history

    new_raw = raw + [{"t": now, "v": value}]
    cutoff = now - RAW_RETENTION_SECONDS
    new_raw = [e for e in new_raw if e["t"] >= cutoff]

    new_history = dict(history)
    new_history["raw"] = new_raw
    return new_history


def _weighted_stats(entries, value_key_min="min", value_key_avg="avg", value_key_max="max", count_key="n"):
    """Combines several already-aggregated {min,avg,max,n} entries into
    one - a correct weighted average, not a naive mean-of-means."""
    total_n = sum(e[count_key] for e in entries)
    if total_n <= 0:
        return None
    weighted_avg = sum(e[value_key_avg] * e[count_key] for e in entries) / total_n
    return {
        "min": min(e[value_key_min] for e in entries),
        "avg": weighted_avg,
        "max": max(e[value_key_max] for e in entries),
        "n": total_n,
    }


def compact_hourly(history: dict, now: float) -> dict:
    """Pure function: rolls any COMPLETE hour present in `raw` but not
    yet summarized into `hourly`, then prunes `hourly` older than
    HOURLY_RETENTION_SECONDS. "Complete" means the hour has fully
    ended (hour_start + 3600 <= now) - a still-in-progress hour is
    never partially summarized (it would need re-summarizing every
    run, and a partial summary is misleading as "the hour's data").
    Iterates every raw-covered hour not already in `hourly` (not just
    "the most recent one"), so a multi-hour gap (Pi was on, sampler
    missed a few runs) still backfills correctly from whatever raw
    samples exist - bounded by RAW_RETENTION_SECONDS (at most 7*24=168
    hours to ever consider), trivially cheap. Idempotent: re-running
    against the same input never duplicates an hour already present."""
    raw = history.get("raw", [])
    hourly = list(history.get("hourly", []))
    already = {e["t"] for e in hourly}

    buckets = {}
    for e in raw:
        hour_start = int(e["t"] // 3600) * 3600
        if hour_start + 3600 > now:
            continue  # this hour hasn't ended yet
        if hour_start in already:
            continue
        buckets.setdefault(hour_start, []).append(e["v"])

    for hour_start, values in buckets.items():
        hourly.append({
            "t": hour_start,
            "min": min(values),
            "avg": sum(values) / len(values),
            "max": max(values),
            "n": len(values),
        })

    hourly.sort(key=lambda e: e["t"])
    cutoff = now - HOURLY_RETENTION_SECONDS
    hourly = [e for e in hourly if e["t"] >= cutoff]

    new_history = dict(history)
    new_history["hourly"] = hourly
    return new_history


def compact_daily(history: dict, now: float) -> dict:
    """Same idiom as compact_hourly(), one tier up: rolls complete days
    from `hourly` into `daily` (weighted stats, not naive re-averaging),
    then prunes `daily` older than DAILY_RETENTION_SECONDS."""
    hourly = history.get("hourly", [])
    daily = list(history.get("daily", []))
    already = {e["t"] for e in daily}

    buckets = {}
    for e in hourly:
        day_start = int(e["t"] // 86400) * 86400
        if day_start + 86400 > now:
            continue  # this day hasn't ended yet
        if day_start in already:
            continue
        buckets.setdefault(day_start, []).append(e)

    for day_start, entries in buckets.items():
        stats = _weighted_stats(entries)
        if stats is not None:
            daily.append({"t": day_start, **stats})

    daily.sort(key=lambda e: e["t"])
    cutoff = now - DAILY_RETENTION_SECONDS
    daily = [e for e in daily if e["t"] >= cutoff]

    new_history = dict(history)
    new_history["daily"] = daily
    return new_history


def record_sample(signal_id: str, now: float, value: float) -> bool:
    """The main entry point piratebox_history_sampler.py calls once per
    currently-valid signal, each sampler run. Loads, appends, compacts
    both tiers, saves - one atomic write. Returns True if a new raw
    sample was actually recorded (False if append_raw_sample() rejected
    it - e.g. too soon since the last one, or a clock step backward)."""
    history = load_signal_history(signal_id)
    appended = append_raw_sample(history, now, value)
    recorded = appended is not history and len(appended.get("raw", [])) != len(history.get("raw", []))
    history = compact_hourly(appended, now)
    history = compact_daily(history, now)
    save_signal_history(signal_id, history)
    return recorded


TIER_RAW, TIER_HOURLY, TIER_DAILY = "raw", "hourly", "daily"

# Range-to-tier selection (SAMPLING/API sections of the design): short
# ranges use the finest resolution that still fits inside that tier's
# own retention window; long ranges use an already-aggregated tier so
# a query never has to resample thousands of raw points on every page
# load. The boundary is deliberately "which tier comfortably covers
# this whole range with a reasonable point count", not tied to exactly
# the four suggested UI ranges - a caller passing an unusual range still
# gets a sensible tier.
_ONE_DAY = 86400


def choose_tier_for_range(range_seconds: float) -> str:
    if range_seconds <= RAW_RETENTION_SECONDS:
        return TIER_RAW
    if range_seconds <= HOURLY_RETENTION_SECONDS:
        return TIER_HOURLY
    return TIER_DAILY


def query_range(history: dict, tier: str, start_t: float, end_t: float) -> list:
    """Pure function: the entries of one tier falling within
    [start_t, end_t] inclusive, in chronological order (tiers are
    already stored sorted, but this doesn't assume that of its input).
    Returns [] for an unknown tier rather than raising - a caller
    passing a bad tier gets an honest empty result, not a crash."""
    entries = history.get(tier)
    if not isinstance(entries, list):
        return []
    return sorted((e for e in entries if start_t <= e.get("t", -1) <= end_t), key=lambda e: e["t"])
