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
#   ambient_lux            float, or None - None means either the
#                          BH1750 was never registered, has never
#                          produced a reading, or its last reading has
#                          gone stale (see piratebox_oled_daemon.py's
#                          build_glance_metrics() - the same "only
#                          claim it when it's genuinely current" rule
#                          time_str already follows for time
#                          confidence). The FIRST real hardware sensor
#                          to use this exact "future hardware hook"
#                          mechanism (2026-09-07) - see "ambient" in
#                          GLANCE_PAGES below.
#
# FUTURE HARDWARE HOOKS: exactly the same pattern piratebox_
# progression.py's HARDWARE_SIGNALS registry already established - a
# future page (INA226 power, BME280 room climate, DS18B20 enclosure
# temp, a real DS3231-backed time-confidence upgrade, etc.) is added
# the same way every page below already is (and the way "ambient"
# itself now is): a new GLANCE_PAGES entry whose `eligible()` checks
# for a metrics-dict key that stays absent/None until a future round's
# build_glance_metrics() actually starts populating it from a real,
# registered sensor reader. Nothing here fabricates a reading for
# hardware that isn't commissioned yet - see
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


def _draw_top_aligned(draw, text: str, font, top_y: int, canvas_w: int = CANVAS_W, fill: str = "white") -> None:
    """Like _draw_centered(), but positions the text so its actual
    rendered INK top edge lands at `top_y`, not wherever the font's own
    internal line metrics happen to put it (DejaVu Sans Mono's
    ascender space above a plain all-caps label varies by size, so a
    literal y=1 would drift down at larger sizes) - measured via
    textbbox, the same "don't guess, measure" discipline _centered_x()
    already uses horizontally. This is what makes the label-vs-value
    vertical budget on each page below predictable across every label
    font size LABEL_FONT_SIZES actually picks."""
    bbox = draw.textbbox((0, 0), text, font=font)
    x = max(0, (canvas_w - (bbox[2] - bbox[0])) // 2) - bbox[0]
    draw.text((x, top_y - bbox[1]), text, font=font, fill=fill)


def _fmt_pct(value) -> str:
    return "--%" if value is None else f"{round(value)}%"


def _fmt_temp(value) -> str:
    return "--C" if value is None else f"{round(value)}C"


def _fmt_lux(value) -> str:
    """Below 100 lux, one decimal place matters for telling a genuinely
    dark room apart from a dim one; at or above 100, a whole number
    keeps the string short enough for the canvas at any realistic (or
    even the BH1750's own theoretical max, ~54612) reading - see
    tools/test_glance.py's own width-fit test for the exact numbers
    checked."""
    if value is None:
        return "--"
    if value < 100:
        return f"{value:.1f} LUX"
    return f"{round(value)} LUX"


# --- Ambient light classification --------------------------------------
# Mirrors var/www/html/includes/sensors.php's
# piratebox_classify_ambient_light() EXACTLY - same five boundaries, in
# the same order (Dark/Dim/Indoor/Bright/Very Bright). Kept as two
# independent, explicitly-synchronized implementations (Python here,
# PHP there) rather than one shared file across languages - see
# tools/test_ambient_light_consistency.py, which shells out to the real PHP
# function and asserts both classifiers place a set of representative
# lux values (including every exact boundary) into the SAME band, and
# docs/OPERATIONAL-DECISIONS.md for why sharing a single source file
# across Python/PHP was judged more architectural complexity than it's
# worth for five static numbers. If you change one implementation's
# boundaries, change the other's identically, then re-run that test.
#
# The DISPLAY STRING below is deliberately NOT identical to the web
# UI's own label text - "Very Bright" doesn't fit this display at any
# legible size (measured: 146px at font_medium, canvas is 128px) - so
# the OLED uses "V.BRIGHT", an unambiguous abbreviation of the exact
# same band, not a different definition. See tools/test_glance.py for
# the width-fit check on every label this returns.
#
# UI-ONLY presentation bands, independent of and never derived from
# any Progression/achievement condition or threshold - same statement
# as includes/sensors.php's own header, restated here since this is a
# second, independent place that statement must hold.
def _classify_ambient_light_label(lux: float) -> str:
    if lux < 10:
        return "DARK"
    if lux < 50:
        return "DIM"
    if lux < 250:
        return "INDOOR"
    if lux < 1000:
        return "BRIGHT"
    return "V.BRIGHT"


# --- Label sizing: "fit intelligently," not one fixed giant font -------
#
# Physical validation (2026-09-04) confirmed the numeric VALUES read
# fine at distance but the small label above them ("CPU"/"DISK"/etc.,
# originally drawn at the same 9pt font_small every other serious page
# uses for secondary detail) did not - defeating half the point of a
# distance page. Fixed with a small font LADDER instead of one bigger
# fixed size: LABEL_FONT_SIZES, biggest first. _fit_label_font() below
# picks the LARGEST of these three that still fits a given label's
# actual measured width (with a small margin) - short labels (CPU, RAM,
# DISK, TIME, POWER) all comfortably fit the biggest size and use it;
# the two genuinely long ones (CLIENTS, UPTIME) step down exactly as
# far as their own width requires and no further, so nothing clips and
# nothing is needlessly small just because ONE label is long. This
# means piratebox_oled_daemon.py's load_glance_fonts() now loads three
# label sizes (plus the two existing value sizes, unchanged) - still
# all loaded ONCE at daemon startup, not per-frame; this module still
# does zero I/O of its own, only picking among ALREADY-LOADED font
# objects it's handed, via pure Pillow geometry (textbbox), matching
# every other measurement in this file.
LABEL_FONT_SIZES = (36, 32, 28)  # must match load_glance_fonts()'s own
                                   # label_fonts tuple order (biggest first)
LABEL_MAX_WIDTH = CANVAS_W - 8    # 4px margin each side


def _fit_label_font(draw, text: str, label_fonts):
    """`label_fonts` is a sequence of pre-loaded ImageFont objects,
    ordered to match LABEL_FONT_SIZES (biggest first). Returns the
    first one whose rendered width for `text` fits LABEL_MAX_WIDTH;
    falls back to the smallest if even that doesn't fit (never raises -
    every label this module actually uses today fits comfortably
    within the smallest size, verified by test_glance.py, but a future
    label added without checking its width degrades to "smallest
    available" rather than clipping silently off-screen)."""
    for font in label_fonts:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= LABEL_MAX_WIDTH:
            return font
    return label_fonts[-1]


def _draw_label(draw, text: str, label_fonts, top_y: int = 1) -> None:
    """The one label-drawing entry point every render function below
    uses - picks the best-fitting size from `label_fonts` (see
    _fit_label_font()) and top-aligns it at `top_y` (see
    _draw_top_aligned()) so the label always starts at a predictable
    pixel regardless of which size it ended up using."""
    _draw_top_aligned(draw, text, _fit_label_font(draw, text, label_fonts), top_y)


# --- One render function per page -------------------------------------
# Each takes (draw, label_fonts, font_cpu_label, font_medium, font_big,
# metrics) and draws exactly one full-screen page: a label near the
# top (as large as LABEL_FONT_SIZES allows it to be, per the note
# above - minimal decoration otherwise, per instruction: no boxes/
# icons here, those cost pixels this page's whole point needs), then
# the value(s) as large as the layout allows, centered - value sizing/
# positioning is UNCHANGED from before the label-size fix, per
# instruction to leave already-validated numeric readability alone.
# Every one handles a missing/None metric by showing a "--" placeholder
# rather than crashing or printing a garbled value - whether a page is
# worth showing AT ALL given missing data is the SCHEDULER's job
# (`eligible()` below), not the renderer's; a renderer's job is to
# never look broken if it does get called.
#
# CPU is the one page with two stacked values instead of one, so it
# structurally has less vertical room for its own label than the
# single-value pages below - `font_cpu_label` is a dedicated, smaller
# label size chosen specifically to leave that room without shrinking
# either value line, rather than running "CPU" (which would otherwise
# fit the biggest LABEL_FONT_SIZES tier easily) through the same
# fit-to-width ladder the single-value pages use, which answers a
# different question (does it fit the WIDTH) than the one that
# actually constrains this page (does everything fit the HEIGHT).

def _render_cpu(draw, label_fonts, font_cpu_label, font_medium, font_big, metrics: dict) -> None:
    _draw_top_aligned(draw, "CPU", font_cpu_label, 0)
    _draw_centered(draw, _fmt_pct(metrics.get("cpu_percent")), font_medium, 19)
    _draw_centered(draw, _fmt_temp(metrics.get("cpu_temp_c")), font_medium, 41)


def _render_ram(draw, label_fonts, font_cpu_label, font_medium, font_big, metrics: dict) -> None:
    _draw_label(draw, "RAM", label_fonts)
    _draw_centered(draw, _fmt_pct(metrics.get("ram_percent")), font_big, 30)


def _render_disk(draw, label_fonts, font_cpu_label, font_medium, font_big, metrics: dict) -> None:
    _draw_label(draw, "DISK", label_fonts)
    _draw_centered(draw, _fmt_pct(metrics.get("disk_percent")), font_big, 30)


def _render_clients(draw, label_fonts, font_cpu_label, font_medium, font_big, metrics: dict) -> None:
    _draw_label(draw, "CLIENTS", label_fonts)
    clients = metrics.get("clients")
    _draw_centered(draw, "--" if clients is None else str(clients), font_big, 30)


def _render_uptime(draw, label_fonts, font_cpu_label, font_medium, font_big, metrics: dict) -> None:
    _draw_label(draw, "UPTIME", label_fonts)
    _draw_centered(draw, metrics.get("uptime_str") or "--", font_medium, 33)


def _render_time(draw, label_fonts, font_cpu_label, font_medium, font_big, metrics: dict) -> None:
    _draw_label(draw, "TIME", label_fonts)
    _draw_centered(draw, metrics.get("time_str") or "--:--", font_big, 30)


def _render_power_warning(draw, label_fonts, font_cpu_label, font_medium, font_big, metrics: dict) -> None:
    # Deliberately plain, not alarming beyond what a WARNING tier fact
    # warrants - this is the chronic undervoltage condition
    # (docs/POWER-INTEGRITY-DIAGNOSIS.md), represented honestly but
    # without the visual weight an actual Emergency gets (that's a
    # wholly different, higher-priority branch in main() - see
    # piratebox_oled_daemon.py's compute_display_tier()/priority chain,
    # unchanged by this feature - a glance page is NEVER how Emergency
    # is presented).
    _draw_label(draw, "POWER", label_fonts)
    _draw_centered(draw, "LOW", font_big, 30)


def _render_ambient(draw, label_fonts, font_cpu_label, font_medium, font_big, metrics: dict) -> None:
    # Same two-stacked-value structure as _render_cpu above (label
    # needs the smaller dedicated font_cpu_label to leave room for two
    # value lines) - not the single-big-value RAM/DISK/CLIENTS/TIME
    # layout, since this page always shows both the number AND its
    # plain-language classification, matching the task's own example
    # layout ("AMBIENT / 7.5 lux / DARK"). No icon: every other glance
    # page here is pure text at maximum legible size, and this page's
    # three lines already use the full 64px height - an icon would
    # cost pixels this page's own readability needs, not add clarity.
    _draw_top_aligned(draw, "AMBIENT", font_cpu_label, 0)
    lux = metrics.get("ambient_lux")
    _draw_centered(draw, _fmt_lux(lux), font_medium, 19)
    _draw_centered(draw, "--" if lux is None else _classify_ambient_light_label(lux), font_medium, 41)


_RENDERERS = {
    "cpu": _render_cpu,
    "ram": _render_ram,
    "disk": _render_disk,
    "clients": _render_clients,
    "uptime": _render_uptime,
    "time": _render_time,
    "power_warning": _render_power_warning,
    "ambient": _render_ambient,
}


def render_glance_page(draw, label_fonts, font_cpu_label, font_medium, font_big, page_id: str, metrics: dict) -> None:
    """The sole entry point piratebox_oled_daemon.py's build_frame()
    calls for page=="glance". `label_fonts` is the 3-tuple described
    above (LABEL_FONT_SIZES order); `font_cpu_label` is the CPU page's
    own dedicated smaller label size. An unknown page_id degrades to a
    plain "--" rather than raising - matches the fail-safe fallback
    every other unknown-key lookup in this project already uses (e.g.
    draw_scene()'s own unknown-scene default)."""
    renderer = _RENDERERS.get(page_id)
    if renderer is None:
        _draw_centered(draw, "--", font_big, 20)
        return
    renderer(draw, label_fonts, font_cpu_label, font_medium, font_big, metrics)


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
    "ambient": {
        # Only eligible with a genuinely current reading - the same
        # "None means don't show it, never second-guess the daemon"
        # rule "time" already follows above. build_glance_metrics()
        # is what decides "genuinely current" (detected AND not stale
        # AND a real number) - this module just respects the result.
        "eligible": lambda m: m.get("ambient_lux") is not None,
        # Same baseline as "uptime" - a routine, always-relevant-when-
        # available fact, not urgent enough to dominate the rotation
        # (per instruction) the way "clients" or "power_warning" can
        # become in their own more attention-worthy moments.
        "weight": lambda m: 8.0,
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
# "ambient" (2026-09-07) is included, unlike "power_warning" - it's a
# routine capability page like cpu/ram/disk, not a fault condition;
# on a Pi without the BH1750 wired it degrades to the same honest "--"
# placeholder every other page already shows for temporarily-missing
# data (see _render_ambient), never a fabricated reading.
GLANCE_PREVIEW_ORDER = ["cpu", "ram", "disk", "clients", "uptime", "time", "ambient"]
