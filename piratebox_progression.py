#!/usr/bin/env python3
#
# PirateBox Progression - a lightweight, persistent personality/history
# subsystem underneath Silly Mode (see piratebox_oled_daemon.py's "SILLY
# MODE" header for that layer's own design). Imported in-process by the
# OLED daemon - not a separate service, not a database, not a network
# call anywhere in this file.
#
# WHAT THIS FILE OWNS, so piratebox_oled_daemon.py doesn't have to:
#   - Durable state: XP/levels/titles, lifetime aggregate stats,
#     achievements, a small bounded "personality weights" vector, and a
#     locally-generated device identity - persisted to
#     /var/lib/piratebox-oled/progression.json (real disk, survives
#     reboot and Silly Mode being toggled off - explicitly NOT /tmp).
#   - Anti-farming: a generic cooldown/daily-cap helper used by every
#     XP source and every rare-event repeat check.
#   - The rarity/event engine: named "families" of alternate reactions
#     for situations the OLED daemon already detects (a client
#     arriving, waking up, the periodic flourish beat, plain ambient
#     idling), each with a common default plus uncommon/rare/legendary/
#     secret alternates gated by conditions, cooldowns, and history -
#     so a familiar moment can occasionally produce something the
#     operator has never seen before, even after months of daily use.
#   - A small, bounded, deterministic "personality weights" vector
#     (sociability/vigilance/resilience) - NOT machine learning, just a
#     clamped exponential moving average nudged by real history, used
#     only to gently bias which alternate a family roll favors.
#   - Clean extension points for hardware that is purchased/planned but
#     NOT YET commissioned (DS3231 RTC, INA226, BME280, DS18B20, BH1750,
#     future RGB, future GPS/travel) - a signal registry a future round
#     can register real readers into, without this file ever fabricating
#     a reading for hardware that isn't there. See "HARDWARE SIGNAL
#     EXTENSION POINTS" below.
#
# PRIVACY / ANTI-FARMING, BY CONSTRUCTION:
#   - No MAC address, IP, hostname, or per-client identity is ever read,
#     stored, or referenced anywhere in this file - every client-related
#     counter here is derived from status.json's existing
#     `wifi_clients` AGGREGATE integer, the exact same field every OLED
#     page already reads. This file cannot build a client identity
#     database even by accident - the data to do so never reaches it.
#   - Every repeatable XP source goes through `award_once()` below,
#     which enforces a cooldown and/or a daily cap - reconnecting the
#     same (or any) device over and over cannot produce unlimited XP.
#   - Progression NEVER unlocks or gates any core PirateBox capability
#     (networking, hostapd/dnsmasq/nginx/php-fpm, Emergency Mode). Every
#     reward this file can produce is cosmetic: XP, a level, a title, an
#     achievement flag, a personality-weight nudge, or a suggested
#     Silly Mode render - nothing here is ever consulted by anything
#     outside the OLED daemon's own display logic.
#
# PERSISTENCE / RELIABILITY:
#   - Single durable file, atomic writes (temp file + os.replace, same
#     directory/filesystem), coalesced (see `dirty`/`maybe_save()` below)
#     rather than written every tick - typical operation writes at most
#     once every SAVE_COALESCE_SECONDS even under heavy event activity,
#     and not at all on a tick where nothing changed.
#   - Corruption/loss is handled the way every other reader in this
#     project handles a bad data file: log once, fall back to a fresh
#     default state, keep running. A broken progression.json can never
#     crash the daemon, block Emergency Mode, or affect Core in any way
#     - see `load_state()`'s own try/except.
#   - Schema-versioned (`SCHEMA_VERSION`) so a future format change can
#     migrate old files instead of discarding them.

import json
import os
import random
import time

DATA_DIR = "/var/lib/piratebox-oled"
DATA_FILE = os.path.join(DATA_DIR, "progression.json")
SCHEMA_VERSION = 1

SAVE_COALESCE_SECONDS = 45.0   # minimum real-time gap between disk writes,
                                 # even if many events fire in between -
                                 # bounds worst-case SD-card write frequency

# --- Small local word lists for a fully offline, no-personal-info,
# no-cloud device identity - generated once, stored, never regenerated
# unless the operator explicitly resets progression. ---
_NAME_ADJECTIVES = [
    "Rusty", "Salty", "Foggy", "Iron", "Quiet", "Restless", "Lucky",
    "Windward", "Hollow", "Brine", "Ember", "Tidal", "Drifting", "Old",
]
_NAME_NOUNS = [
    "Gull", "Anchor", "Compass", "Lantern", "Barnacle", "Tern", "Skiff",
    "Beacon", "Kraken", "Petrel", "Driftwood", "Sextant", "Ledger", "Buoy",
]


def _default_state() -> dict:
    now = time.time()
    return {
        "schema_version": SCHEMA_VERSION,
        "device": {
            "name": None,           # filled in once by ensure_identity()
            "born_at": now,
        },
        "xp": {"total": 0, "level": 1},
        "uptime_accumulator_seconds": 0.0,   # carries the sub-hour remainder
        "stats": {
            "lifetime_uptime_seconds": 0.0,
            "boots_observed": 0,
            "total_client_encounters": 0,     # count of 0->N arrival events
            "max_simultaneous_clients": 0,
            "emergency_exercises": 0,
            "ssh_sessions_observed": 0,
            "silly_days_used": 0,
            "external_radio_commissioned": False,
        },
        "achievements": [],            # list of achievement ids, unlocked order
        "weights": {"sociability": 0.5, "vigilance": 0.5, "resilience": 0.5},
        "cooldowns": {},               # key -> {"last": ts, "day": "YYYY-MM-DD", "count": n}
        "seen_events": {},             # event id -> {"count": n, "last": ts}
        "milestones_shown": [],        # uptime-day thresholds already awarded
        "updated_at": now,
    }


def _atomic_write_json(path: str, data: dict) -> None:
    tmp = f"{path}.tmp-{os.getpid()}"
    with open(tmp, "w") as f:
        json.dump(data, f, separators=(",", ":"))
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o640)   # owner rw, group r (moose is in the `gpio`
                             # group - see etc/tmpfiles.d's own comment)
                             # regardless of this process's umask
    os.replace(tmp, path)   # atomic on the same filesystem


def load_state(log=None) -> dict:
    """Never raises. Missing/corrupt/wrong-shaped data degrades to a
    fresh default state - exactly this project's existing "honest
    default, never fabricate, never crash" discipline
    (docs/ARCHITECTURE.md §10), applied to a new data store the same
    way every other reader in this project already applies it."""
    try:
        with open(DATA_FILE, "r") as f:
            raw = json.load(f)
        if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("unexpected shape/version")
        # Merge onto a fresh default so a future field addition, or a
        # partially-written/older file, never KeyErrors downstream.
        state = _default_state()
        _deep_merge(state, raw)
        return state
    except FileNotFoundError:
        return _default_state()
    except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
        if log is not None:
            log.warning("progression.json unreadable/corrupt (%s) - starting fresh.", exc)
        return _default_state()


def _deep_merge(base: dict, overlay: dict) -> None:
    for k, v in overlay.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def save_state(state: dict, log=None) -> bool:
    """Best-effort durable save - a failure here (disk full, permission
    issue) is logged and swallowed, never raised: losing a progression
    write must never take down the OLED daemon or anything it drives."""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        state["updated_at"] = time.time()
        _atomic_write_json(DATA_FILE, state)
        return True
    except OSError as exc:
        if log is not None:
            log.warning("Could not save progression.json (%s) - continuing in-memory only.", exc)
        return False


def ensure_identity(state: dict, rng: random.Random) -> None:
    if state["device"].get("name") is None:
        state["device"]["name"] = f"{rng.choice(_NAME_ADJECTIVES)} {rng.choice(_NAME_NOUNS)}"


# --- XP / levels / titles ------------------------------------------------
# Progressively longer curve: early levels are quick and encouraging,
# later ones take real months/years of accumulated uptime + activity -
# see the module header for the tuning rationale.

def xp_for_level(level: int) -> int:
    """Cumulative XP required to REACH `level` (level 1 = 0)."""
    if level <= 1:
        return 0
    return round(60 * (level ** 1.55))


def level_for_xp(total_xp: int) -> int:
    level = 1
    while xp_for_level(level + 1) <= total_xp:
        level += 1
    return level


# Titles are intentionally sparse here in source comments - the full
# flavor text lives in TITLES below (source code is fair game per
# instruction; this file is not the operator-facing report).
TITLES = [
    (1, "Fresh Off the Dock"),
    (3, "Deckhand"),
    (6, "Able Seaman"),
    (10, "Quartermaster"),
    (15, "Bosun"),
    (22, "First Mate"),
    (30, "Captain"),
    (40, "Commodore"),
    (55, "Airwave Admiral"),
    (75, "Broadcast Ghost"),
    (100, "Static Sea Legend"),
]


def title_for_level(level: int) -> str:
    best = TITLES[0][1]
    for threshold, name in TITLES:
        if level >= threshold:
            best = name
        else:
            break
    return best


# --- Generic anti-farming helper ------------------------------------------

def award_once(state: dict, key: str, now: float, cooldown_s: float = None, daily_cap: int = None) -> bool:
    """Returns True exactly when `key` is allowed to award right now,
    and records that it did. `cooldown_s`: minimum seconds since the
    last successful award of this key. `daily_cap`: maximum successful
    awards of this key per calendar day (device-local date, from
    `time.localtime`). Either, both, or neither may be given - with
    neither, this degrades to "exactly once ever" (a plain unlock)."""
    cd = state["cooldowns"].setdefault(key, {"last": 0.0, "day": "", "count": 0})
    today = time.strftime("%Y-%m-%d", time.localtime(now))

    if cooldown_s is not None and (now - cd["last"]) < cooldown_s:
        return False

    if daily_cap is not None:
        if cd["day"] != today:
            cd["day"], cd["count"] = today, 0
        if cd["count"] >= daily_cap:
            return False
        cd["count"] += 1

    if cooldown_s is None and daily_cap is None:
        if cd["count"] >= 1:
            return False
        cd["count"] = 1

    cd["last"] = now
    return True


def add_xp(state: dict, amount: int) -> bool:
    """Returns True if this pushed the device to a new level."""
    if amount <= 0:
        return False
    state["xp"]["total"] += amount
    new_level = level_for_xp(state["xp"]["total"])
    if new_level > state["xp"]["level"]:
        state["xp"]["level"] = new_level
        return True
    return False


# --- Personality weights (bounded EMA, NOT machine learning) -------------
# Each call nudges one weight toward `target` by a small fixed fraction,
# then clamps to [0, 1]. Fully deterministic given the same call
# sequence - directly unit-testable, no hidden/opaque state.

_WEIGHT_ALPHA = 0.02


def nudge_weight(state: dict, name: str, target: float) -> None:
    w = state["weights"].get(name, 0.5)
    w = w + _WEIGHT_ALPHA * (target - w)
    state["weights"][name] = max(0.0, min(1.0, w))


# --- Achievements ----------------------------------------------------------
# Each achievement is a pure predicate over (state, ctx) - checked once
# per tick against the NOT-YET-unlocked set only (see check_achievements()
# below), so a predicate can be as simple as a ">=" comparison; it never
# needs to reason about "did I already fire," that's handled generically.
#
# `hidden`: True means this project's own operator-facing docs and the
# final feature report deliberately do NOT enumerate this one - it's
# meant to be discovered, not read about in advance. This module (and
# its own tests) MUST still be fully explicit about what triggers it -
# secrecy here is an operator-facing UX choice, not a codebase one.
#
# Every threshold below reads real, already-tracked state - nothing is
# invented or estimated to make an achievement "hittable."

def _mk(name, xp, hidden, check):
    return {"name": name, "xp": xp, "hidden": hidden, "check": check}


ACHIEVEMENTS = {
    # --- Lifetime uptime ---
    "uptime_1d":    _mk("First Full Day", 40, False, lambda s, c: s["stats"]["lifetime_uptime_seconds"] >= 86400),
    "uptime_1w":    _mk("One Week Underway", 100, False, lambda s, c: s["stats"]["lifetime_uptime_seconds"] >= 604800),
    "uptime_1m":    _mk("A Month at Sea", 250, False, lambda s, c: s["stats"]["lifetime_uptime_seconds"] >= 2592000),
    "uptime_100d":  _mk("Hundred-Day Voyage", 400, False, lambda s, c: s["stats"]["lifetime_uptime_seconds"] >= 8640000),
    "uptime_1y":    _mk("One Year Underway", 1200, False, lambda s, c: s["stats"]["lifetime_uptime_seconds"] >= 31536000),

    # --- Boots / resilience ---
    "boots_10":     _mk("Ten Landings", 30, False, lambda s, c: s["stats"]["boots_observed"] >= 10),
    "boots_50":     _mk("Old Salt", 150, False, lambda s, c: s["stats"]["boots_observed"] >= 50),

    # --- Client encounters (aggregate only, never per-device) ---
    "encounter_1":  _mk("First Contact", 15, False, lambda s, c: s["stats"]["total_client_encounters"] >= 1),
    "encounter_10": _mk("Small Crowd", 40, False, lambda s, c: s["stats"]["total_client_encounters"] >= 10),
    "encounter_100": _mk("Regular Haunt", 150, False, lambda s, c: s["stats"]["total_client_encounters"] >= 100),
    "encounter_1000": _mk("Local Legend", 600, False, lambda s, c: s["stats"]["total_client_encounters"] >= 1000),

    # --- Simultaneous clients ---
    "simul_2":      _mk("A Pair Aboard", 20, False, lambda s, c: s["stats"]["max_simultaneous_clients"] >= 2),
    "simul_5":      _mk("Standing Room Only", 80, False, lambda s, c: s["stats"]["max_simultaneous_clients"] >= 5),
    "simul_10":     _mk("Packed Deck", 250, False, lambda s, c: s["stats"]["max_simultaneous_clients"] >= 10),

    # --- Emergency Mode history ---
    "emergency_1":  _mk("Weathered the Storm", 50, False, lambda s, c: s["stats"]["emergency_exercises"] >= 1),
    "emergency_10": _mk("Storm-Tested", 300, False, lambda s, c: s["stats"]["emergency_exercises"] >= 10),

    # --- SSH / admin activity ---
    "ssh_1":        _mk("Bridge Visitor", 15, False, lambda s, c: s["stats"]["ssh_sessions_observed"] >= 1),
    "ssh_100":      _mk("Well-Worn Terminal", 200, False, lambda s, c: s["stats"]["ssh_sessions_observed"] >= 100),

    # --- Silly Mode adoption itself ---
    "silly_1":      _mk("Let Loose", 10, False, lambda s, c: s["stats"]["silly_days_used"] >= 1),
    "silly_30":     _mk("Habitual", 120, False, lambda s, c: s["stats"]["silly_days_used"] >= 30),

    # --- Real hardware/capability milestones (already-available signals only) ---
    "external_radio": _mk("Upgraded Rigging", 80, False, lambda s, c: s["stats"]["external_radio_commissioned"]),

    # --- Meta ---
    "collector_10": _mk("Collector", 150, False, lambda s, c: len(s["achievements"]) >= 10),

    # --- Hidden / secret (deliberately not summarized in operator docs) ---
    "hidden_night_owl": _mk(
        "Night Owl", 60, True,
        lambda s, c: 2 <= time.localtime(c["now"]).tm_hour < 4 and (c.get("current_clients") or 0) > 0,
    ),
    "hidden_long_watch": _mk(
        "The Long Watch", 90, True,
        lambda s, c: c.get("idle_seconds", 0) >= 86400,
    ),
    "hidden_leet": _mk(
        "Nice", 13, True,
        lambda s, c: s["stats"]["lifetime_uptime_seconds"] >= 133700
        and int(s["stats"]["lifetime_uptime_seconds"]) % 133700 < 45,
    ),
    "hidden_insomniac": _mk(
        "Insomniac", 70, True,
        lambda s, c: c.get("wake_count_today", 0) >= 5,
    ),
    "hidden_full_house": _mk(
        "Full House", 100, True,
        lambda s, c: (c.get("current_clients") or 0) >= 3 and c.get("ssh_active"),
    ),
}


RARITY_COMMON = "common"
RARITY_UNCOMMON = "uncommon"
RARITY_RARE = "rare"
RARITY_LEGENDARY = "legendary"
RARITY_SECRET = "secret"


def _v(vid, rarity, weight, render, condition=None, cooldown_s=None, min_level=1):
    """One alternate reaction inside an event family. `render` is a
    plain dict the OLED daemon interprets - this module never imports a
    drawing library, keeping it fully testable without hardware or
    Pillow. `condition`, if given, is (state, ctx) -> bool; `cooldown_s`
    suppresses re-selection of this specific variant for that many
    seconds after it last won a roll (common variants should leave this
    None - they're meant to recur freely)."""
    return {
        "id": vid, "rarity": rarity, "weight": weight, "render": render,
        "condition": condition, "cooldown_s": cooldown_s, "min_level": min_level,
    }


def _long_idle(hours):
    return lambda s, c: c.get("idle_seconds", 0) >= hours * 3600


def _quiet_hours(c):
    h = time.localtime(c["now"]).tm_hour
    return h < 6 or h >= 22


# Event families - see the module header. Every family MUST include at
# least one condition-free, cooldown-free "common" entry so a roll can
# never come back empty; everything above that is genuinely optional
# texture. Rarity/weight numbers and the exact hidden variants are
# deliberately not summarized in operator-facing docs (see instruction).
EVENT_FAMILIES = {
    "client_arrival": [
        _v("client_arrival.common_excited", RARITY_COMMON, 100, {"expression": "excited"}),
        _v("client_arrival.uncommon_delighted", RARITY_UNCOMMON, 18,
           {"expression": "excited", "decoration": "sparkle", "quip": "Well, look who it is!"},
           cooldown_s=3600),
        _v("client_arrival.rare_royal", RARITY_RARE, 4,
           {"expression": "royal_welcome", "quip": "A guest of note!"},
           condition=lambda s, c: s["stats"]["total_client_encounters"] >= 10,
           cooldown_s=86400 * 2, min_level=5),
        _v("client_arrival.legendary_reunion", RARITY_LEGENDARY, 0.4,
           {"scene": "reunion", "quip": "It's been a while, hasn't it?"},
           condition=_long_idle(48), cooldown_s=86400 * 21, min_level=8),
    ],
    "wake": [
        _v("wake.common", RARITY_COMMON, 100, {"expression": "waking"}),
        _v("wake.uncommon_groggy", RARITY_UNCOMMON, 20,
           {"expression": "waking", "quip": "Five more minutes..."}, cooldown_s=7200),
        _v("wake.rare_startled", RARITY_RARE, 5,
           {"expression": "surprised", "quip": "Oh! Didn't see you there."},
           condition=_quiet_hours, cooldown_s=86400, min_level=4),
    ],
    "flourish": [
        _v("flourish.common", RARITY_COMMON, 100, {"expression": "pirate_flourish"}),
        _v("flourish.uncommon_wink", RARITY_UNCOMMON, 15,
           {"expression": "pirate_flourish", "decoration": "wink"}, cooldown_s=3600 * 6),
        _v("flourish.rare_logbook", RARITY_RARE, 3,
           {"scene": "logbook"}, condition=lambda s, c: len(s["achievements"]) >= 3,
           cooldown_s=86400 * 3, min_level=6),
        _v("flourish.legendary_bottle", RARITY_LEGENDARY, 0.3,
           {"scene": "message_bottle"},
           condition=lambda s, c: s["stats"]["lifetime_uptime_seconds"] >= 86400 * 30,
           cooldown_s=86400 * 30, min_level=10),
    ],
    "ambient": [
        # No common entry needed here - this family is only ever rolled
        # opportunistically as texture ON TOP of the normal ambient
        # cycle (see the daemon's own integration), so an empty result
        # (None) is the expected, ordinary outcome almost every time.
        _v("ambient.secret_star", RARITY_SECRET, 0.15,
           {"scene": "shooting_star", "quip": "Make a wish."},
           condition=lambda s, c: c.get("idle_seconds", 0) >= 1800 and _quiet_hours(c),
           cooldown_s=86400 * 14, min_level=3),
        _v("ambient.secret_glimmer", RARITY_SECRET, 0.1,
           {"scene": "treasure_glimmer"},
           condition=lambda s, c: s["weights"].get("sociability", 0.5) < 0.3,
           cooldown_s=86400 * 10, min_level=7),
    ],
}

_forced_queue = []


def force_next_event(family: str, variant_id: str) -> None:
    """TEST/DEV ONLY. Not called from any CLI or production code path -
    pushes an override consumed by the very next roll_event(family, ...)
    call, bypassing weight/condition/cooldown filtering entirely, so
    this module's own tests can deterministically exercise rare/
    legendary/secret content without depending on real probability."""
    _forced_queue.append((family, variant_id))


def _pop_forced(family: str):
    for i, (fam, vid) in enumerate(_forced_queue):
        if fam == family:
            return _forced_queue.pop(i)[1]
    return None


def roll_event(family: str, state: dict, ctx: dict, rng: random.Random):
    """Returns a winning variant dict, or None if the family is unknown/
    empty. Every well-formed family (see EVENT_FAMILIES) always has an
    unconditioned common entry, so None only happens for a family with
    no unconditioned fallback (deliberately true for "ambient", which is
    opportunistic texture, not a required reaction)."""
    variants = EVENT_FAMILIES.get(family, [])
    if not variants:
        return None

    forced_id = _pop_forced(family)
    if forced_id is not None:
        for v in variants:
            if v["id"] == forced_id:
                seen = state["seen_events"].setdefault(v["id"], {"count": 0, "last": 0.0})
                seen["count"] += 1
                seen["last"] = ctx["now"]
                return v
        return None

    now = ctx["now"]
    level = state["xp"]["level"]
    pool, weights = [], []
    for v in variants:
        if v["min_level"] > level:
            continue
        if v["condition"] is not None and not v["condition"](state, ctx):
            continue
        if v["cooldown_s"] is not None:
            last = state["cooldowns"].get(v["id"], {}).get("last", 0.0)
            if (now - last) < v["cooldown_s"]:
                continue
        pool.append(v)
        weights.append(v["weight"])

    if not pool:
        return None

    chosen = rng.choices(pool, weights=weights, k=1)[0]
    if chosen["cooldown_s"] is not None:
        state["cooldowns"].setdefault(chosen["id"], {"last": 0.0, "day": "", "count": 0})["last"] = now
    seen = state["seen_events"].setdefault(chosen["id"], {"count": 0, "last": 0.0})
    seen["count"] += 1
    seen["last"] = now
    return chosen


# --- Hardware signal extension points --------------------------------------
# Purchased/planned hardware NOT YET commissioned (DS3231 RTC, INA226
# power telemetry, BME280 environmental, DS18B20 temperature probes,
# BH1750 ambient light, a future addressable-RGB status light, a future
# GPS/travel capability) has NO reader implemented here, per instruction
# - this file never fabricates a reading for hardware that isn't there.
#
# What exists instead: a place for a future commissioning round to
# register one, without touching the engine above at all. A signal is a
# zero-argument callable returning a small JSON-safe value (or raising/
# returning None if the hardware isn't currently reachable - the same
# "honest missing value, never fabricated" discipline this whole file
# already follows elsewhere). Once registered, a future event/
# achievement condition can read it from `ctx["hardware"]` (populated by
# read_hardware_signals() below, called once per tick alongside every
# other read) - no change needed to roll_event()/check_achievements()
# themselves. Starts empty and MUST stay empty until real hardware is
# actually wired and confirmed - never populate this speculatively.
HARDWARE_SIGNALS = {}


def register_hardware_signal(name: str, reader) -> None:
    HARDWARE_SIGNALS[name] = reader


def read_hardware_signals() -> dict:
    out = {}
    for name, reader in HARDWARE_SIGNALS.items():
        try:
            out[name] = reader()
        except Exception:  # noqa: BLE001 - one bad sensor must never stop the tick
            out[name] = None
    return out


def check_achievements(state: dict, ctx: dict) -> list:
    """Returns the list of newly-unlocked achievement ids this tick (may
    be empty, occasionally more than one). Mutates state (records the
    unlock + awards its XP via add_xp) - callers should inspect the
    return value for anything display-worthy, not re-derive it."""
    newly = []
    unlocked = set(state["achievements"])
    for aid, spec in ACHIEVEMENTS.items():
        if aid in unlocked:
            continue
        try:
            if spec["check"](state, ctx):
                state["achievements"].append(aid)
                add_xp(state, spec["xp"])
                newly.append(aid)
        except Exception:  # noqa: BLE001 - a bad predicate must never crash the daemon
            continue
    return newly


# --- Main orchestration ----------------------------------------------------
# The one entrypoint piratebox_oled_daemon.py calls, once per tick,
# regardless of whether Silly Mode's display is currently toggled on -
# progression is a fact about the device's life, not about whether its
# cosmetic display is switched on right now. All XP sources here are
# deliberately small and gated by award_once() - see the module header.

def observe_boot(state: dict) -> None:
    """Call exactly once, at daemon startup, before the main loop."""
    state["stats"]["boots_observed"] += 1


def observe_tick(state: dict, ctx: dict) -> dict:
    """`ctx` (all already computed by the daemon from data it reads
    anyway - nothing new is polled here):
      now, dt (seconds since the last tick), tier, current_clients
      (int or None), ssh_active (bool), idle_seconds (float),
      emergency_exercised (bool - True exactly on an emergency->normal
      transition tick), silly_enabled (bool), external_radio (bool),
      hardware (dict from read_hardware_signals(), may be empty).
    Returns {"leveled_up": bool, "new_level": int|None,
    "new_achievements": [ids]} - the daemon decides what, if anything,
    to show; this function never touches a display."""
    now = ctx["now"]
    tier = ctx.get("tier")
    dt = ctx.get("dt", 0.0)
    current_clients = ctx.get("current_clients")
    level_before = state["xp"]["level"]

    # Lifetime uptime counts all operational time, any tier - it's a
    # fact about the device, not a reward for being perfectly healthy.
    state["stats"]["lifetime_uptime_seconds"] += dt

    # Passive XP: healthy ("ok") operation earns slightly more per hour
    # than "warning" (the known chronic condition) - both earn something,
    # since neither is the device's fault, but "ok" is nudged as the
    # nominally better state. Pure elapsed wall-clock time, so this is
    # inherently ungrindable - no action can accelerate it.
    if tier in ("ok", "warning"):
        rate = 2 if tier == "ok" else 1
        state["uptime_accumulator_seconds"] += dt
        while state["uptime_accumulator_seconds"] >= 3600.0:
            state["uptime_accumulator_seconds"] -= 3600.0
            add_xp(state, rate)

    # Client arrival / simultaneous-record tracking - aggregate count
    # only, exactly status.json's own wifi_clients field, never a
    # per-device identity.
    prev = state.get("_last_clients_seen")
    if current_clients is not None:
        if current_clients > 0 and current_clients > state["stats"]["max_simultaneous_clients"]:
            state["stats"]["max_simultaneous_clients"] = current_clients
            add_xp(state, 25)  # monotonic record - no cap needed, can't be farmed
        if prev is not None and prev == 0 and current_clients > 0:
            state["stats"]["total_client_encounters"] += 1
            if award_once(state, "xp.client_arrival", now, daily_cap=10):
                add_xp(state, 8)
            nudge_weight(state, "sociability", 1.0)
        elif (current_clients or 0) == 0 and (prev or 0) == 0:
            nudge_weight(state, "sociability", 0.4)  # slow decay toward solitude while quiet
        state["_last_clients_seen"] = current_clients

    if ctx.get("ssh_active") and award_once(state, "xp.ssh_daily", now, cooldown_s=3600):
        state["stats"]["ssh_sessions_observed"] += 1
        add_xp(state, 5)
        nudge_weight(state, "vigilance", 1.0)

    if ctx.get("emergency_exercised"):
        state["stats"]["emergency_exercises"] += 1
        if award_once(state, "xp.emergency", now, daily_cap=3):
            add_xp(state, 20)
        nudge_weight(state, "resilience", 1.0)

    if ctx.get("silly_enabled") and award_once(state, "xp.silly_daily", now, cooldown_s=68000):
        state["stats"]["silly_days_used"] += 1
        add_xp(state, 3)

    if ctx.get("external_radio") and not state["stats"]["external_radio_commissioned"]:
        state["stats"]["external_radio_commissioned"] = True

    new_achievements = check_achievements(state, ctx)

    level_after = state["xp"]["level"]
    return {
        "leveled_up": level_after > level_before,
        "new_level": level_after if level_after > level_before else None,
        "new_achievements": new_achievements,
    }


def maybe_save_and_report(state: dict, dirty: bool, last_save_at: float, now: float, log=None):
    """Coalesced save: writes at most once every SAVE_COALESCE_SECONDS,
    and only if something actually changed since the last write - most
    ticks do zero disk I/O. Returns (new_last_save_at, did_save) -
    `new_last_save_at` is unchanged unless a write actually happened."""
    if dirty and (now - last_save_at) >= SAVE_COALESCE_SECONDS:
        save_state(state, log=log)
        return now, True
    return last_save_at, False


# --- Reset / import, single-writer design -----------------------------
# `piratebox-silly` (unprivileged) never writes progression.json
# directly - only this daemon process does, avoiding any concurrent-
# writer hazard. Instead the CLI drops a request into the already-
# bind-mounted /tmp/piratebox (see piratebox-oled.service's own
# comment), this daemon notices it on its next tick (a plain mtime
# check - negligible cost), and only THIS process ever touches the
# real durable file. The CLI is responsible for deleting the request
# file itself shortly after (operating on the real host path, which it
# can always write - only the DAEMON's view of this directory is
# read-only), so a stale marker never lingers meaningfully. `markers`
# is a small dict the caller keeps in memory across ticks (never
# persisted - a reset/import request is a one-time action, not history
# worth remembering).

RESET_REQUEST_FILE = "/tmp/piratebox/progression-reset-request"
IMPORT_REQUEST_FILE = "/tmp/piratebox/progression-import-request"
RESET_CONFIRM_TOKEN = "RESET-CONFIRMED"


def check_reset_request(state: dict, markers: dict, log=None) -> bool:
    """Returns True if a reset was just performed (state is now a fresh
    default, already saved to disk). A present-but-unconfirmed file
    (including the empty placeholder tmpfiles.d always keeps there) is
    silently ignored - only the exact confirmation token, freshly
    written, triggers anything."""
    try:
        mtime = os.path.getmtime(RESET_REQUEST_FILE)
    except OSError:
        return False
    if mtime <= markers.get("reset_mtime", 0.0):
        return False
    markers["reset_mtime"] = mtime
    try:
        with open(RESET_REQUEST_FILE, "r") as f:
            token = f.read().strip()
    except OSError:
        return False
    if token != RESET_CONFIRM_TOKEN:
        return False
    fresh = _default_state()
    state.clear()
    state.update(fresh)
    save_state(state, log=log)
    if log is not None:
        log.info("Progression state reset (operator-requested via piratebox-silly reset).")
    return True


def _validate_importable(candidate) -> bool:
    """Deliberately conservative structural validation (no schema
    library, no new dependency) - enough to refuse anything that would
    KeyError or produce nonsense downstream, not a full type-checker.
    Anything this rejects is left completely unadopted - the live state
    is simply untouched, per the "corruption must never impair anything"
    reliability requirement."""
    if not isinstance(candidate, dict) or candidate.get("schema_version") != SCHEMA_VERSION:
        return False
    xp = candidate.get("xp")
    if not isinstance(xp, dict) or not isinstance(xp.get("total"), (int, float)) or xp.get("total") < 0:
        return False
    if not isinstance(candidate.get("stats"), dict):
        return False
    if not isinstance(candidate.get("achievements"), list):
        return False
    if not all(isinstance(a, str) for a in candidate["achievements"]):
        return False
    return True


def check_import_request(state: dict, markers: dict, log=None) -> bool:
    """Returns True if an import was just adopted. An invalid/malformed
    staged file is rejected and logged - live state is left completely
    unchanged, never partially applied."""
    try:
        mtime = os.path.getmtime(IMPORT_REQUEST_FILE)
    except OSError:
        return False
    if mtime <= markers.get("import_mtime", 0.0):
        return False
    markers["import_mtime"] = mtime
    try:
        with open(IMPORT_REQUEST_FILE, "r") as f:
            raw = f.read()
        if not raw.strip():
            return False
        candidate = json.loads(raw)
    except (OSError, ValueError) as exc:
        if log is not None:
            log.warning("Progression import request unreadable/invalid JSON (%s) - ignored.", exc)
        return False
    if not _validate_importable(candidate):
        if log is not None:
            log.warning("Progression import request failed validation - ignored, live state unchanged.")
        return False
    fresh = _default_state()
    _deep_merge(fresh, candidate)
    state.clear()
    state.update(fresh)
    save_state(state, log=log)
    if log is not None:
        log.info("Progression state imported (operator-requested via piratebox-silly import).")
    return True
