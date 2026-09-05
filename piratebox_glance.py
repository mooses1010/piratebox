#!/usr/bin/env python3
#
# PirateBox Distance / Glance Display - a large-format, at-a-distance
# presentation layer for the OLED (128x64 SSD1306), added 2026-09-04.
#
# WHY A SEPARATE MODULE, AND WHAT IT DOES NOT OWN:
#   Same architectural split Expression Engine v2 already established
#   for faces (piratebox_expressions.py) and Progression already
#   established for the rarity/personality engine (piratebox_
#   progression.py) - state acquisition, selection, and presentation
#   stay in three different places, never mixed:
#     - STATE ACQUISITION (reading /proc/stat, /proc/meminfo,
#       /sys/class/thermal/..., status.json, etc.) lives in
#       piratebox_oled_daemon.py, alongside every other read_*()
#       helper that file already has (read_cpu_temp_c(),
#       read_uptime_seconds(), read_disk_free_total(), the two new
#       read_meminfo_kb()/read_cpu_jiffies() added for this feature) -
#       NOT here. This module has ZERO disk/subprocess/network access.
#     - SELECTION (which glance page to show right now) is
#       select_glance_page() below - a small, deterministic, weighted
#       eligibility/cooldown scheduler, not a scoring "AI."
#     - PRESENTATION (drawing one page) is render_glance_page() below -
#       pure, stateless, takes an already-built `metrics` dict and
#       draws pixels, nothing else.
#   piratebox_oled_daemon.py's main() is the only thing that calls
#   both halves in sequence: read metrics -> select_glance_page() ->
#   render_glance_page() (via build_frame()'s "glance" page dispatch).
#
# METRICS DICT CONTRACT (built once per glance-phase-entry by
# piratebox_oled_daemon.py's build_glance_metrics(), passed whole to
# every function below - this module never reaches into status.json,
# /proc, or anything else on its own):
#   cpu_percent            float 0-100, or None (no prior /proc/stat
#                          sample yet - e.g. right after daemon start)
#   cpu_temp_c             float, or None
#   ram_percent            float 0-100, or None
#   disk_percent           float 0-100, or None
#   clients                int, or None
#   clients_recently_changed  bool - mirrors the daemon's own existing
#                          client-count "pulse" edge (see
#                          build_glance_metrics()'s own comment) -
#                          reused, not a new signal.
#   uptime_str             str, already formatted via the daemon's own
#                          format_duration() - this module does no
#                          time arithmetic of its own.
#   time_str               str ("HH:MM"), or None - None means time
#                          confidence doesn't currently permit showing
#                          it (see GLANCE_PAGES["time"]["eligible"]).
#   undervoltage_now       bool
#
# FUTURE HARDWARE HOOKS: exactly the same pattern piratebox_
# progression.py's HARDWARE_SIGNALS registry already established - a
# future page (INA226 power, BME280 room climate, DS18B20 enclosure
# temp, a real DS3231-backed time-confidence upgrade, etc.) is added
# the same way every page below already is: a new GLANCE_PAGES entry
# whose `eligible()` checks for a metrics-dict key that stays absent/
# None until a future round's build_glance_metrics() actually starts
# populating it from a real, registered sensor reader. Nothing here
# fabricates a reading for hardware that isn't commissioned yet - see
# the deliberate absence of any such key in the contract above.
#
# SPOILER POLICY: not applicable here. Glance pages are plain utility,
# entirely outside Progression's rarity/secret system - there is no
# hidden glance content, so nothing in this module or its tests needs
# to be withheld from operator-facing docs.

import random

CANVAS_W = 128
CANVAS_H = 64


# --- Small centering helpers -----------------------------------------------

def _centered_x(draw, text: str, font, canvas_w: int = CANVAS_W) -> int:
    """x-offset that horizontally centers `text` in `canvas_w` pixels,
    measured via textbbox (not a fixed guess) so it stays correct
    regardless of digit count - "8%" and "100%" both actually end up
    centered, not just left-aligned at the same x."""
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    return max(0, (canvas_w - width) // 2) - bbox[0]


def _draw_centered(draw, text: str, font, y: int, canvas_w: int = CANVAS_W, fill: str = "white") -> None:
    draw.text((_centered_x(draw, text, font, canvas_w), y), text, font=font, fill=fill)


def _fmt_pct(value) -> str:
    return "--%" if value is None else f"{round(value)}%"


def _fmt_temp(value) -> str:
    return "--C" if value is None else f"{round(value)}C"


# --- One render function per page -------------------------------------
# Each takes (draw, font_small, font_medium, font_big, metrics) and
# draws exactly one full-screen page: a short label near the top in
# font_small (minimal decoration, per instruction - no boxes/icons
# here, those cost pixels this page's whole point needs), then the
# value(s) as large as the layout allows, centered. Every one handles
# a missing/None metric by showing a "--" placeholder rather than
# crashing or printing a garbled value - whether a page is worth
# showing AT ALL given missing data is the SCHEDULER's job
# (`eligible()` below), not the renderer's; a renderer's job is to
# never look broken if it does get called.

def _render_cpu(draw, font_small, font_medium, font_big, metrics: dict) -> None:
    _draw_centered(draw, "CPU", font_small, 1)
    _draw_centered(draw, _fmt_pct(metrics.get("cpu_percent")), font_medium, 14)
    _draw_centered(draw, _fmt_temp(metrics.get("cpu_temp_c")), font_medium, 37)


def _render_ram(draw, font_small, font_medium, font_big, metrics: dict) -> None:
    _draw_centered(draw, "RAM", font_small, 1)
    _draw_centered(draw, _fmt_pct(metrics.get("ram_percent")), font_big, 20)


def _render_disk(draw, font_small, font_medium, font_big, metrics: dict) -> None:
    _draw_centered(draw, "DISK", font_small, 1)
    _draw_centered(draw, _fmt_pct(metrics.get("disk_percent")), font_big, 20)


def _render_clients(draw, font_small, font_medium, font_big, metrics: dict) -> None:
    _draw_centered(draw, "CLIENTS", font_small, 1)
    clients = metrics.get("clients")
    _draw_centered(draw, "--" if clients is None else str(clients), font_big, 20)


def _render_uptime(draw, font_small, font_medium, font_big, metrics: dict) -> None:
    _draw_centered(draw, "UPTIME", font_small, 1)
    _draw_centered(draw, metrics.get("uptime_str") or "--", font_medium, 24)


def _render_time(draw, font_small, font_medium, font_big, metrics: dict) -> None:
    _draw_centered(draw, "TIME", font_small, 1)
    _draw_centered(draw, metrics.get("time_str") or "--:--", font_big, 20)


def _render_power_warning(draw, font_small, font_medium, font_big, metrics: dict) -> None:
    # Deliberately plain, not alarming beyond what a WARNING tier fact
    # warrants - this is the chronic undervoltage condition
    # (docs/POWER-INTEGRITY-DIAGNOSIS.md), represented honestly but
    # without the visual weight an actual Emergency gets (that's a
    # wholly different, higher-priority branch in main() - see
    # piratebox_oled_daemon.py's compute_display_tier()/priority chain,
    # unchanged by this feature - a glance page is NEVER how Emergency
    # is presented).
    _draw_centered(draw, "POWER", font_small, 1)
    _draw_centered(draw, "LOW", font_big, 20)


_RENDERERS = {
    "cpu": _render_cpu,
    "ram": _render_ram,
    "disk": _render_disk,
    "clients": _render_clients,
    "uptime": _render_uptime,
    "time": _render_time,
    "power_warning": _render_power_warning,
}


def render_glance_page(draw, font_small, font_medium, font_big, page_id: str, metrics: dict) -> None:
    """The sole entry point piratebox_oled_daemon.py's build_frame()
    calls for page=="glance". An unknown page_id degrades to a plain
    "--" rather than raising - matches the fail-safe fallback every
    other unknown-key lookup in this project already uses (e.g.
    draw_scene()'s own unknown-scene default)."""
    renderer = _RENDERERS.get(page_id)
    if renderer is None:
        _draw_centered(draw, "--", font_big, 20)
        return
    renderer(draw, font_small, font_medium, font_big, metrics)


# --- Eligibility / weighting registry + scheduler -----------------------
#
# Each entry: `eligible(metrics) -> bool` (can this page even be shown
# right now, given what's actually known - never fabricates a value to
# become eligible), `weight(metrics) -> float` (relative likelihood
# among the currently-eligible pool; context-aware nudges live here,
# not in a separate scoring system), and an optional `cooldown_s`
# (minimum real seconds between two selections of the SAME page - used
# only by "power_warning" today, so a chronic condition stays honestly
# represented without ever monopolizing the rotation).
DISK_FULL_THRESHOLD_PERCENT = 80.0
POWER_WARNING_COOLDOWN_SECONDS = 900.0   # 15 minutes

GLANCE_PAGES = {
    "cpu": {
        "eligible": lambda m: True,
        "weight": lambda m: 10.0,
    },
    "ram": {
        "eligible": lambda m: True,
        "weight": lambda m: 10.0,
    },
    "disk": {
        "eligible": lambda m: True,
        # More prominent once storage is meaningfully full - an
        # already-existing, real fact (disk_percent), not a new alarm
        # threshold invented just for this page.
        "weight": lambda m: 30.0 if (m.get("disk_percent") or 0) >= DISK_FULL_THRESHOLD_PERCENT else 10.0,
    },
    "clients": {
        "eligible": lambda m: True,
        # Baseline weight matches the other routine pages when nobody's
        # connected (a lone "0" isn't very interesting); noticeably
        # more prominent once someone is connected; briefly much more
        # prominent right after the count actually changes (reuses the
        # daemon's own existing client-count "pulse" edge - see
        # build_glance_metrics()'s own comment - not a new signal).
        "weight": lambda m: (
            40.0 if m.get("clients_recently_changed")
            else (16.0 if (m.get("clients") or 0) > 0 else 6.0)
        ),
    },
    "uptime": {
        "eligible": lambda m: True,
        "weight": lambda m: 8.0,
    },
    "time": {
        # Only eligible when the daemon's own build_glance_metrics()
        # decided time confidence permits it (NTP-synced or a real RTC
        # detected) - see that function; this module just respects
        # "time_str is None means don't show it," never second-guesses.
        "eligible": lambda m: m.get("time_str") is not None,
        "weight": lambda m: 10.0,
    },
    "power_warning": {
        "eligible": lambda m: bool(m.get("undervoltage_now")),
        "weight": lambda m: 12.0,
        "cooldown_s": POWER_WARNING_COOLDOWN_SECONDS,
    },
}


def select_glance_page(metrics: dict, rng: random.Random, last_page_id, cooldowns: dict, now: float):
    """Picks exactly one page id from GLANCE_PAGES, or None if nothing
    is currently eligible (doesn't happen today - several pages have
    no `eligible` gate at all - but handled so a future all-conditional
    page set degrades to "skip this glance slot," never a crash).
    `cooldowns` is a small dict the caller keeps across calls, mutated
    here exactly like piratebox_progression.py's own per-variant
    cooldown dict - deliberately NOT persisted to disk anywhere (a
    glance-page cooldown is display-scheduling trivia, not history
    worth remembering across a restart). `rng` is `random.choices()`-
    driven weighted selection, the same primitive the rarity engine
    already uses - fully deterministic given a seeded rng, so this is
    directly unit-testable. Deliberately avoids repeating the same page
    as last time whenever a genuine alternative exists (never a hard
    rule - if only one page is eligible, it repeats; that's correct,
    not a bug), so two consecutive glance slots don't show the
    identical page back to back purely by chance."""
    pool, weights = [], []
    for page_id, spec in GLANCE_PAGES.items():
        if not spec["eligible"](metrics):
            continue
        cooldown_s = spec.get("cooldown_s")
        if cooldown_s is not None and (now - cooldowns.get(page_id, 0.0)) < cooldown_s:
            continue
        w = spec["weight"](metrics)
        if w <= 0:
            continue
        pool.append(page_id)
        weights.append(w)

    if not pool:
        return None

    if last_page_id in pool and len(pool) > 1:
        idx = pool.index(last_page_id)
        pool.pop(idx)
        weights.pop(idx)

    chosen = rng.choices(pool, weights=weights, k=1)[0]
    if GLANCE_PAGES[chosen].get("cooldown_s") is not None:
        cooldowns[chosen] = now
    return chosen


# --- Operator-only preview playlist ---------------------------------
# `piratebox-silly glance-preview` (see that script) cycles through
# this FIXED, stable-order list rather than calling
# select_glance_page() - every glance page is "ordinary" by definition
# (there is no rarity/secret concept here, unlike Silly Mode), so a
# preview is really just "show me each page once, regardless of
# current context weighting," which context-aware selection alone
# could otherwise make slow to stumble across manually (e.g. "clients"
# is only prominent right after a real change; a healthy device may
# rarely roll "power_warning" at all - and showing it when NOT
# genuinely active would misrepresent real state, so it is
# deliberately left out of this fixed list entirely; the operator
# already sees it live, honestly, if and when it's actually eligible).
GLANCE_PREVIEW_ORDER = ["cpu", "ram", "disk", "clients", "uptime", "time"]
