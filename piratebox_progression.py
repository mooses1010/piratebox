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
            "rare_events_witnessed": 0,    # count of rare/legendary/secret-tier
                                             # variants ever chosen by roll_event() -
                                             # an aggregate only, never which ones
        },
        "achievements": [],            # list of achievement ids, unlocked order
        "achievement_unlocked_at": {},  # id -> unix ts (best-effort; ids unlocked
                                          # before this field existed have no entry -
                                          # see build_public_summary()'s handling)
        "history": [],                 # bounded Captain's Log entries - see
                                          # _append_history() - {"ts","kind","label"}
        "weights": {"sociability": 0.5, "vigilance": 0.5, "resilience": 0.5},
        "cooldowns": {},               # key -> {"last": ts, "day": "YYYY-MM-DD", "count": n}
        "seen_events": {},             # event id -> {"count": n, "last": ts}
        "milestones_shown": [],        # uptime-day thresholds already awarded
        "updated_at": now,
    }


HISTORY_MAX_ENTRIES = 200   # Captain's Log stays sparse/durable, not a raw event
                             # log - bounded by count, oldest trimmed, matching
                             # this project's existing bounded-history convention
                             # (piratebox_status_helper.sh's own boot_events/
                             # undervoltage_daily lists use the same discipline).


def _append_history(state: dict, kind: str, label: str, now: float) -> None:
    """kind: "achievement" / "level_up" / "title_change" / "rare_event".
    `label` must already be spoiler-safe and human-readable - callers
    are responsible for that (see check_achievements(), observe_tick(),
    and roll_event() below for what each kind actually puts here)."""
    state["history"].append({"ts": now, "kind": kind, "label": label})
    if len(state["history"]) > HISTORY_MAX_ENTRIES:
        state["history"] = state["history"][-HISTORY_MAX_ENTRIES:]


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
# `description`: a short, spoiler-safe, human-readable sentence
# explaining what the achievement MEANS - shown on Captain's Log, but
# ONLY once an achievement has actually been unlocked (see
# build_public_summary() below, which only ever iterates the device's
# own unlocked list, never this whole catalog). This is a REQUIRED
# positional argument specifically so a future achievement added
# without one is a loud TypeError at import time, not a silently blank
# card discovered later. The distinction that matters (2026-09-06,
# Captain's Log achievement-description round):
#   MEANING (this field) - what happened / what it recognizes. Safe to
#     reveal after discovery, and the whole point of this field.
#   MECHANICS (the `check` lambda below) - the exact threshold/code
#     condition that unlocked it. Never surfaced anywhere web-facing,
#     regardless of discovery state - a description must never restate
#     a `check` lambda's literal number/comparison (see the module's
#     own BAD/GOOD examples this round: "uptime_seconds >= 604800" is
#     mechanics; "Kept watch through a very long voyage" is meaning).
#
# Every threshold below reads real, already-tracked state - nothing is
# invented or estimated to make an achievement "hittable."

def _mk(name, xp, hidden, description, check):
    return {"name": name, "xp": xp, "hidden": hidden, "description": description, "check": check}


ACHIEVEMENTS = {
    # --- Lifetime uptime ---
    "uptime_1d":    _mk("First Full Day", 40, False,
                        "Clocked a full day of running time since it was first switched on.",
                        lambda s, c: s["stats"]["lifetime_uptime_seconds"] >= 86400),
    "uptime_1w":    _mk("One Week Underway", 100, False,
                        "Added up to a full week of running time so far.",
                        lambda s, c: s["stats"]["lifetime_uptime_seconds"] >= 604800),
    "uptime_1m":    _mk("A Month at Sea", 250, False,
                        "Tallied a month's worth of running time across its life so far.",
                        lambda s, c: s["stats"]["lifetime_uptime_seconds"] >= 2592000),
    "uptime_100d":  _mk("Hundred-Day Voyage", 400, False,
                        "Racked up a hundred days of running time over its life so far.",
                        lambda s, c: s["stats"]["lifetime_uptime_seconds"] >= 8640000),
    "uptime_1y":    _mk("One Year Underway", 1200, False,
                        "Reached a full year of accumulated running time since it was first switched on.",
                        lambda s, c: s["stats"]["lifetime_uptime_seconds"] >= 31536000),

    # --- Boots / resilience ---
    "boots_10":     _mk("Ten Landings", 30, False,
                        "Has come back online again and again - restarts are old news to it by now.",
                        lambda s, c: s["stats"]["boots_observed"] >= 10),
    "boots_50":     _mk("Old Salt", 150, False,
                        "A true veteran of restarts - nothing about coming back online rattles it anymore.",
                        lambda s, c: s["stats"]["boots_observed"] >= 50),

    # --- Client encounters (aggregate only, never per-device) ---
    "encounter_1":  _mk("First Contact", 15, False,
                        "Welcomed its very first visitor aboard.",
                        lambda s, c: s["stats"]["total_client_encounters"] >= 1),
    "encounter_10": _mk("Small Crowd", 40, False,
                        "Has welcomed a modest, steady trickle of visitors over time.",
                        lambda s, c: s["stats"]["total_client_encounters"] >= 10),
    "encounter_100": _mk("Regular Haunt", 150, False,
                        "Become a regular stop for a good number of visitors by now.",
                        lambda s, c: s["stats"]["total_client_encounters"] >= 100),
    "encounter_1000": _mk("Local Legend", 600, False,
                        "Welcomed enough visitors, over time, to become a fixture of the neighborhood.",
                        lambda s, c: s["stats"]["total_client_encounters"] >= 1000),

    # --- Simultaneous clients ---
    "simul_2":      _mk("A Pair Aboard", 20, False,
                        "Had two visitors connected at the very same moment.",
                        lambda s, c: s["stats"]["max_simultaneous_clients"] >= 2),
    "simul_5":      _mk("Standing Room Only", 80, False,
                        "Hosted a genuinely busy moment with several visitors aboard at once.",
                        lambda s, c: s["stats"]["max_simultaneous_clients"] >= 5),
    "simul_10":     _mk("Packed Deck", 250, False,
                        "Hosted its busiest moment yet - a real crowd, all connected at once.",
                        lambda s, c: s["stats"]["max_simultaneous_clients"] >= 10),

    # --- Emergency Mode history ---
    "emergency_1":  _mk("Weathered the Storm", 50, False,
                        "Came through an Emergency Mode exercise and settled back into normal service.",
                        lambda s, c: s["stats"]["emergency_exercises"] >= 1),
    "emergency_10": _mk("Storm-Tested", 300, False,
                        "Has weathered Emergency Mode enough times to be thoroughly practiced at it.",
                        lambda s, c: s["stats"]["emergency_exercises"] >= 10),

    # --- SSH / admin activity ---
    "ssh_1":        _mk("Bridge Visitor", 15, False,
                        "Received its first visit from someone working directly at the terminal.",
                        lambda s, c: s["stats"]["ssh_sessions_observed"] >= 1),
    "ssh_100":      _mk("Well-Worn Terminal", 200, False,
                        "Has seen the operator sit down at its terminal a great many times.",
                        lambda s, c: s["stats"]["ssh_sessions_observed"] >= 100),

    # --- Silly Mode adoption itself ---
    "silly_1":      _mk("Let Loose", 10, False,
                        "Had its playful side switched on for the very first time.",
                        lambda s, c: s["stats"]["silly_days_used"] >= 1),
    "silly_30":     _mk("Habitual", 120, False,
                        "Its playful side has been switched on so often it's practically routine now.",
                        lambda s, c: s["stats"]["silly_days_used"] >= 30),

    # --- Real hardware/capability milestones (already-available signals only) ---
    "external_radio": _mk("Upgraded Rigging", 80, False,
                        "Gained a proper external radio receiver of its own.",
                        lambda s, c: s["stats"]["external_radio_commissioned"]),

    # --- Meta ---
    "collector_10": _mk("Collector", 150, False,
                        "Amassed a solid handful of achievements along the way.",
                        lambda s, c: len(s["achievements"]) >= 10),

    # --- Hidden / secret (deliberately not summarized in operator docs) ---
    "hidden_night_owl": _mk(
        "Night Owl", 60, True,
        "Had a visitor drop by in the dead of night.",
        lambda s, c: 2 <= time.localtime(c["now"]).tm_hour < 4 and (c.get("current_clients") or 0) > 0,
    ),
    "hidden_long_watch": _mk(
        "The Long Watch", 90, True,
        "Stood a long, quiet watch with nobody around to keep it company.",
        lambda s, c: c.get("idle_seconds", 0) >= 86400,
    ),
    "hidden_leet": _mk(
        "Nice", 13, True,
        "Its lifetime clock ticked past a suspiciously tidy number, right on the nose.",
        lambda s, c: s["stats"]["lifetime_uptime_seconds"] >= 133700
        and int(s["stats"]["lifetime_uptime_seconds"]) % 133700 < 45,
    ),
    "hidden_insomniac": _mk(
        "Insomniac", 70, True,
        "Was roused from rest again and again within a single day.",
        lambda s, c: c.get("wake_count_today", 0) >= 5,
    ),
    "hidden_full_house": _mk(
        "Full House", 100, True,
        "Had a full house - visitors aboard and the operator on deck, all at once.",
        lambda s, c: (c.get("current_clients") or 0) >= 3 and c.get("ssh_active"),
    ),
    "hidden_curious_collection": _mk(
        # Expression Engine v2 (2026-09-04) - rewards actually having
        # witnessed a real spread of the rarer visual variants, not any
        # specific one by name (this predicate never names a variant id
        # - see _record_variant_choice()'s own rare_events_witnessed
        # counter, which every rare/legendary/secret pick already
        # increments regardless of which family/variant it came from).
        "The Curious Collection", 90, True,
        "Has been lucky enough to witness a handful of its own rarer moments and reactions.",
        lambda s, c: s["stats"].get("rare_events_witnessed", 0) >= 8,
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
#
# Expression Engine v2 (2026-09-04) additions below use two new render-
# spec shapes on top of the pre-existing {"expression":...}/{"scene":...}:
#   {"anim": <ANIMATIONS key>} - a brief multi-frame reaction, resolved
#     and flashed by piratebox_oled_daemon.py's play_animation_burst()
#     (this module never imports piratebox_expressions.py or knows what
#     an animation actually looks like - same separation of concerns as
#     every existing {"scene":...} entry already had).
#   A `condition` reading `ctx["hardware"]` - the future-sensor-hook
#   pattern: `read_hardware_signals()` returns `{}` until a real reader
#   is registered (see that function's own header), so any such
#   condition is permanently False today and becomes eligible on its
#   own, automatically, the moment a future round registers the real
#   reader - no code here needs to change when that happens.
EVENT_FAMILIES = {
    "client_arrival": [
        _v("client_arrival.common_excited", RARITY_COMMON, 100, {"expression": "excited"}),
        _v("client_arrival.uncommon_delighted", RARITY_UNCOMMON, 18,
           {"expression": "excited", "decoration": "sparkle", "quip": "Well, look who it is!"},
           cooldown_s=3600),
        _v("client_arrival.uncommon_wave", RARITY_UNCOMMON, 14,
           {"anim": "wave_hello", "quip": "Ahoy there!"}, cooldown_s=5400, min_level=2),
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
        _v("wake.uncommon_look_around", RARITY_UNCOMMON, 16,
           {"anim": "look_around_curious", "quip": "Where was I?"}, cooldown_s=5400, min_level=2),
        _v("wake.rare_startled", RARITY_RARE, 5,
           {"anim": "startle_and_settle", "quip": "Oh! Didn't see you there."},
           condition=_quiet_hours, cooldown_s=86400, min_level=4),
    ],
    "flourish": [
        _v("flourish.common", RARITY_COMMON, 100, {"expression": "pirate_flourish"}),
        _v("flourish.uncommon_wink", RARITY_UNCOMMON, 15,
           {"expression": "pirate_flourish", "decoration": "wink"}, cooldown_s=3600 * 6),
        _v("flourish.uncommon_salty", RARITY_UNCOMMON, 12,
           {"expression": "salty", "quip": "Aye, matey."}, cooldown_s=3600 * 5, min_level=3),
        _v("flourish.rare_logbook", RARITY_RARE, 3,
           {"scene": "logbook"}, condition=lambda s, c: len(s["achievements"]) >= 3,
           cooldown_s=86400 * 3, min_level=6),
        _v("flourish.rare_victory", RARITY_RARE, 2,
           {"anim": "victory_flourish"},
           condition=lambda s, c: len(s["achievements"]) >= 5,
           cooldown_s=86400 * 4, min_level=7),
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
        # NOTE ON COOLDOWN LENGTH: unlike every OTHER family, "ambient"
        # has no condition-free "common" baseline entry to dilute
        # against (see the family-level comment above) - every ambient
        # tick that isn't showing "pirate_flourish" calls roll_event()
        # here, so an entry's OWN cooldown is the only thing standing
        # between "uncommon" and "constant." A short cooldown was tried
        # and caught live during this round's own development smoke
        # test (it won almost every single ambient tick, immediately
        # drowning out the plain ambient cycle AND bias_ambient_
        # expression()'s mannerism layer, which only ever gets a chance
        # to show through on ticks this family returns None) - these
        # cooldowns are deliberately long enough (many hours, not
        # minutes) to actually read as occasional.
        _v("ambient.uncommon_skeptical", RARITY_UNCOMMON, 8,
           {"expression": "skeptical"}, cooldown_s=3600 * 10, min_level=2),
        _v("ambient.uncommon_curiouser", RARITY_UNCOMMON, 6,
           {"expression": "curiouser"}, cooldown_s=3600 * 14, min_level=3),
        _v("ambient.secret_star", RARITY_SECRET, 0.15,
           {"scene": "shooting_star", "quip": "Make a wish."},
           condition=lambda s, c: c.get("idle_seconds", 0) >= 1800 and _quiet_hours(c),
           cooldown_s=86400 * 14, min_level=3),
        _v("ambient.secret_glimmer", RARITY_SECRET, 0.1,
           {"scene": "treasure_glimmer"},
           condition=lambda s, c: s["weights"].get("sociability", 0.5) < 0.3,
           cooldown_s=86400 * 10, min_level=7),
        _v("ambient.secret_night_watch", RARITY_SECRET, 0.1,
           {"scene": "night_watch"},
           # Future BH1750 hook: `ctx["hardware"]["ambient_lux"]` is
           # always None until a real reader is registered (see
           # HARDWARE_SIGNALS below) - this variant is permanently
           # ineligible until that happens, exactly matching "no
           # sensor-dependent behavior becomes eligible until that
           # capability is actually commissioned."
           condition=lambda s, c: (
               (c.get("hardware") or {}).get("ambient_lux") is not None
               and c["hardware"]["ambient_lux"] < 5
           ),
           cooldown_s=86400 * 5, min_level=4),
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
                _record_variant_choice(state, v, ctx["now"])
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
    _record_variant_choice(state, chosen, now)
    return chosen


def _record_variant_choice(state: dict, variant: dict, now: float) -> None:
    """Shared bookkeeping for a variant that just won a roll (forced or
    weighted): updates its seen-history, and - for rare/legendary/secret
    tiers only - bumps the aggregate `rare_events_witnessed` counter and
    logs a spoiler-safe Captain's Log entry (the variant's own quip if it
    has one, else a generic rarity-tier label - never the internal
    family/variant id, never a hint at how it triggered)."""
    seen = state["seen_events"].setdefault(variant["id"], {"count": 0, "last": 0.0})
    seen["count"] += 1
    seen["last"] = now
    if variant["rarity"] in (RARITY_RARE, RARITY_LEGENDARY, RARITY_SECRET):
        state["stats"]["rare_events_witnessed"] = state["stats"].get("rare_events_witnessed", 0) + 1
        label = variant["render"].get("quip") or f"A {variant['rarity']} moment."
        _append_history(state, "rare_event", label, now)


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
                state["achievement_unlocked_at"][aid] = ctx["now"]
                add_xp(state, spec["xp"])
                _append_history(state, "achievement", spec["name"], ctx["now"])
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
    leveled_up = level_after > level_before
    if leveled_up:
        _append_history(state, "level_up", f"Reached level {level_after}", now)
        title_before, title_after = title_for_level(level_before), title_for_level(level_after)
        if title_after != title_before:
            _append_history(state, "title_change", f"Became {title_after}", now)

    return {
        "leveled_up": leveled_up,
        "new_level": level_after if leveled_up else None,
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


# --- Web profile export (Captain's Log page) --------------------------
# This section decides what's safe to publish to the site-facing
# Captain's Log / Profile page - the ONE place in this file that has to
# think about a web visitor as its audience, not the OLED. Deliberately
# excludes anything that could reveal undiscovered content: internal
# achievement/event ids, cooldown timers, per-variant seen_events
# detail, hidden-achievement predicates, or any count of how many
# achievements/events remain undiscovered (`len(ACHIEVEMENTS)` is never
# exposed here). Only what has actually happened to THIS device is ever
# included - see docs/OPERATIONAL-DECISIONS.md's own note on why the
# full achievement/event list isn't documented anywhere operator-facing
# either.
#
# 2026-09-06 addition: each unlocked achievement now also carries its
# spoiler-safe `description` (see _mk()'s own header for the MEANING-
# vs-MECHANICS distinction that governs its wording) - still subject to
# the exact same "only what's already unlocked" boundary as `name`
# itself, since both come from the same per-achievement loop below.
#
# This module never writes web-reachable state directly (that would
# mean www-data and piratebox-gpio both needing access to the same
# path, or loosening this directory's permissions - neither acceptable
# per this project's existing security boundaries). Instead:
# `python3 piratebox_progression.py` (this file's own `__main__` below)
# prints this summary as JSON to stdout; `piratebox_status_helper.sh`
# (already running as root, on its existing 30s timer) captures that
# output and publishes it to /run/piratebox/progression-public.json
# (world-readable tmpfs) - the exact same "privileged reader bridges to
# a public snapshot" pattern that script already uses for status.json.
# No permission was loosened anywhere to make this possible.

def _trait_label(value: float, low: str, mid: str, high: str) -> str:
    if value < 0.35:
        return low
    if value > 0.65:
        return high
    return mid


def personality_traits(weights: dict) -> dict:
    """Broad, human-readable trait labels derived from the bounded
    weights - never the raw floats (see the module header's "NOT
    machine learning" note). Any presentation layer (this web page, a
    future status light) should use this, never `weights` directly."""
    return {
        "sociability": _trait_label(weights.get("sociability", 0.5), "Solitary", "Balanced", "Social"),
        "vigilance": _trait_label(weights.get("vigilance", 0.5), "Relaxed", "Watchful", "Vigilant"),
        "resilience": _trait_label(weights.get("resilience", 0.5), "Untested", "Steady", "Resilient"),
    }


def build_public_summary(state: dict, now: float = None) -> dict:
    """The one function every web-facing consumer of Progression data
    goes through - see the section header above for the full rationale.
    Pure (given `state`/`now`), so it's directly unit-testable without
    touching disk."""
    if now is None:
        now = time.time()

    level = state["xp"]["level"]
    xp_total = state["xp"]["total"]
    this_level_floor = xp_for_level(level)
    next_level_need = xp_for_level(level + 1)
    span = max(1, next_level_need - this_level_floor)
    progress_fraction = max(0.0, min(1.0, (xp_total - this_level_floor) / span))

    unlocked_at = state.get("achievement_unlocked_at", {})
    achievements = []
    for aid in state.get("achievements", []):
        spec = ACHIEVEMENTS.get(aid)
        if spec is None:
            continue  # a removed/renamed achievement id - skip rather than guess
        achievements.append({
            "name": spec["name"],
            "hidden": bool(spec["hidden"]),
            "unlocked_at": unlocked_at.get(aid),  # None for pre-existing unlocks
            # Spoiler-safe MEANING only (see _mk()'s own header) - safe
            # to include here specifically because this loop only ever
            # runs over state["achievements"] (what THIS device has
            # actually unlocked), never over ACHIEVEMENTS itself. An
            # achievement not yet in that list never reaches this line
            # at all, so its description can never leak ahead of
            # discovery by construction, not by a runtime check here.
            "description": spec.get("description") or "",
        })

    history = [
        {"ts": e.get("ts"), "kind": e.get("kind"), "label": e.get("label")}
        for e in state.get("history", [])
        if isinstance(e, dict) and isinstance(e.get("label"), str)
    ]

    return {
        "available": True,
        "generated_at": now,
        "device": {"name": state.get("device", {}).get("name") or "Unnamed PirateBox"},
        "xp": {
            "total": xp_total,
            "level": level,
            "this_level_floor": this_level_floor,
            "next_level_at": next_level_need,
            "progress_fraction": round(progress_fraction, 4),
        },
        "title": title_for_level(level),
        "stats": dict(state.get("stats", {})),
        "achievements": achievements,
        "history": history,
        "traits": personality_traits(state.get("weights", {})),
        "hardware": read_hardware_signals(),  # empty today - see HARDWARE_SIGNALS
    }


if __name__ == "__main__":
    # Invoked by piratebox_status_helper.sh, as root, on its existing
    # 30s timer - never invoked by the web server or in response to a
    # request. Always prints valid JSON, even on total failure, so the
    # caller's redirect is never at risk of writing garbage.
    try:
        _state = load_state()
        _summary = build_public_summary(_state)
    except Exception:  # noqa: BLE001 - this must never fail to produce valid JSON
        _summary = {"available": False}
    print(json.dumps(_summary))
