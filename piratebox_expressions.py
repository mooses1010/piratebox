#!/usr/bin/env python3
#
# PirateBox Expression Engine v2 - the drawing/data layer underneath
# Silly Mode's "else" branch in piratebox_oled_daemon.py. This module
# owns every pixel Silly Mode can draw (face geometry, decorations,
# scenes, multi-frame animations) and the data tables describing what's
# drawable - piratebox_oled_daemon.py owns none of that anymore, only
# WHEN to show it (see that file's own "SILLY MODE" header and its
# main() priority chain). piratebox_progression.py owns WHICH one gets
# picked for a given moment (the rarity/eligibility/weighting engine,
# EVENT_FAMILIES/roll_event() - unchanged by this module, see that
# file's own header).
#
# WHY A SEPARATE MODULE (v2, 2026-09-04):
#   Before this round, EXPRESSIONS/draw_face()/draw_scene()/draw_zzz()/
#   draw_pirate_flourish()/draw_skull_and_crossbones() all lived inline
#   in piratebox_oled_daemon.py. That was fine for a couple dozen lines
#   of face-drawing, but kept growing every round a new expression or
#   flourish was added - exactly the "enormous pile of expression-
#   specific conditionals in the OLED daemon" this split exists to
#   avoid. Splitting it out means piratebox_oled_daemon.py's own job
#   shrinks back down to what it always should have been: read live
#   state, decide a page, hand off a render-spec, draw it via whatever
#   this module provides - never itself contain per-expression drawing
#   logic. Adding a future expression/animation/scene should mean
#   editing ONLY this file (a new EXPRESSIONS/ANIMATIONS/SCENES entry,
#   or a new elif in draw_scene() for a genuinely new set-piece shape),
#   never touching piratebox_oled_daemon.py's main() loop at all.
#
# WHAT THIS MODULE DOES NOT OWN:
#   - No I/O, no disk, no /tmp, no network, no persistence of any kind
#     - exactly like piratebox_progression.py's own discipline. Every
#     function here is pure: pixels in, pixels out (or a plain dict/
#     list describing what to draw). Fully unit-testable with a bare
#     PIL ImageDraw and no daemon, no hardware, no display.
#   - No rarity/eligibility/cooldown/weighting logic - that is entirely
#     piratebox_progression.py's EVENT_FAMILIES/roll_event() job. This
#     module only defines WHAT a given named expression/animation/scene
#     LOOKS like, never whether/how often it's allowed to appear. The
#     one exception is `bias_ambient_expression()` below, a small,
#     separate, directly-tested "mannerism" layer - see its own
#     docstring for why it's kept apart from roll_event's job too.
#
# RENDER-SPEC SHAPES (the plain dicts passed around between this
# module, piratebox_progression.roll_event(), and piratebox_oled_
# daemon.py's main() - unchanged contract from before this round, only
# ADDED to, never altered):
#   {"expression": <EXPRESSIONS key>, "decoration": <optional override>,
#    "quip": <optional str>}
#   {"scene": <SCENES key>, "quip": <optional str>}
#   {"anim": <ANIMATIONS key>, "quip": <optional str>}   <- NEW this round
# A render-spec is always exactly one of the three - callers never mix
# "expression"/"scene"/"anim" in the same dict. `render_silly()` below
# still only ever draws a SINGLE static frame per call, same as always
# - it does not understand "anim" at all. Resolving "anim" into a
# sequence of single-frame specs, and briefly flashing them, is
# main()'s own job (see resolve_animation_frames() below plus that
# file's play_animation_burst()) - this keeps this module's own
# rendering path exactly as simple/stateless as it always was, and
# keeps piratebox_oled_daemon.py's main() the one place that owns
# timing/sequencing, matching its existing role for every other kind
# of multi-tick state (the personality/status cadence, the one-shot
# event hold, etc.).
#
# HARDWARE HOOKS (DS3231/INA226/BME280/DS18B20/BH1750/RGB/GPS):
#   This module fabricates nothing hardware-related. Any future
#   expression/scene that should react to real sensor data belongs in
#   piratebox_progression.py's EVENT_FAMILIES as a `condition` reading
#   `ctx["hardware"]` (populated from piratebox_progression.
#   read_hardware_signals(), itself empty until a real reader is
#   registered - see that file's header) - never as a hardcoded branch
#   in this module. This module only ever draws what it's told to.
#
# SPOILER POLICY: this file and its own tests (tools/test_expressions.py)
# are fully explicit about every expression/animation/scene that
# exists - that's required to implement and verify them. Operator-
# facing docs and this feature's own completion report are NOT - they
# describe categories/mechanisms, never the full catalog. See
# piratebox_progression.py's own ACHIEVEMENTS "hidden" convention for
# the same split applied to achievements.

import random

# --- Canvas geometry (unchanged from before this round) --------------------

FACE_CX, FACE_CY = 64, 27
EYE_DX = 17
EYE_R = 9


# --- EXPRESSIONS: name -> (eyes, brows, mouth, decoration) ------------------
#
# Every value is a 4-tuple, exactly the shape this table has always
# had - `draw_face()` below is the only thing that interprets it.
# `eyes` may be a single style (both eyes match, the common case) OR a
# 2-tuple (left_style, right_style) for a genuinely asymmetric look
# (see "skeptical" below) - draw_face() handles both transparently, and
# every pre-existing entry keeps using the plain single-style form
# unchanged.
#
# The original dozen entries (idle through royal_welcome) are
# unchanged from before this round - the foundation, not replaced.
# Everything from "curious" onward is new this round: a mix of plain
# ambient variety (curious, content), personality-mannerism variants
# consumed by bias_ambient_expression() below (watchful, wistful,
# resolute), one asymmetric-eye demonstration (skeptical), and a few
# pirate-flavored accessory looks consumed by piratebox_progression.py's
# EVENT_FAMILIES at various rarity tiers (salty, shipshape, curiouser,
# windswept) - being listed here only means "this is drawable," not
# "this is common" - see that file for actual eligibility/rarity.
EXPRESSIONS = {
    "idle":          ("open",       "none",         "smile_small", None),
    "blink":         ("closed",     "none",         "smile_small", None),
    "look_left":     ("look_left",  "none",         "smile_small", None),
    "look_right":    ("look_right", "none",         "smile_small", None),
    "sleeping":      ("closed",     "none",         "flat",        None),
    "waking":        ("half",       "raised",       "o",           None),
    "happy":         ("open",       "none",         "smile_big",   None),
    "excited":       ("wide",       "raised",       "o",           "sparkle"),
    "surprised":     ("wide",       "raised",       "o_small",     None),
    "confused":      ("open",       "one_raised",   "wavy",        None),
    "smug":          ("half",       "one_raised",   "smirk",       None),
    "ssh_watch":     ("open",       "flat",         "smirk",       None),
    "royal_welcome": ("wide",       "raised",       "smile_big",   "crown"),

    # New this round - plain ambient variety, always drawable, no
    # rarity gate of their own (roll_event may still choose to use
    # them as named variants at whatever tier fits, exactly like any
    # pre-existing expression already could be).
    "curious":       ("look_left",  "raised",       "o_small",     None),
    "content":       ("half",       "none",         "smile_small", None),

    # New this round - personality-mannerism variants. Only ever
    # selected by bias_ambient_expression() below, never by the plain
    # tick-cycled ambient pools (AMBIENT_NO_CLIENTS/AMBIENT_WITH_
    # CLIENTS in piratebox_oled_daemon.py) directly, so a device whose
    # weights never drift far from neutral will rarely show these -
    # not because they're rarity-gated, but because nothing asks for
    # them without a personality skew present.
    "watchful":      ("narrow",     "flat",         "flat",        None),
    "wistful":       ("droopy",     "none",         "flat",        None),
    "resolute":      ("narrow",     "flat",         "smile_small", "anchor_charm"),

    # New this round - asymmetric-eye demonstration + accessory looks,
    # consumed by piratebox_progression.py's EVENT_FAMILIES at various
    # rarity tiers (see that file - not enumerated here).
    "skeptical":     (("narrow", "open"), "one_raised", "smirk",     None),
    "salty":         ("open",       "flat",         "smirk",       "eyepatch"),
    "shipshape":     ("open",       "raised",       "smile_big",   "tricorne"),
    "curiouser":     ("wide",       "one_raised",   "o_small",     "monocle"),
    "windswept":     ("closed",     "flat",         "wavy",        "bandana"),
}


# --- ANIMATIONS: name -> {"frames": [...], "frame_gap_s", "hold_ticks"} ----
#
# A frame is either a plain EXPRESSIONS key (str) or a small dict
# override (e.g. {"expression": "excited", "decoration": "sparkle"} or
# {"scene": "..."}), normalized by resolve_animation_frames() below.
# `frame_gap_s` is how far apart consecutive frames are flashed during
# the brief synchronous burst piratebox_oled_daemon.py's
# play_animation_burst() plays ONCE when this animation is first
# chosen (never during the ordinary 3s per-tick cadence - see that
# function's own docstring for why this stays a bounded, sub-second
# burst rather than turning the whole daemon into a high-frequency
# redraw loop). `hold_ticks` is how many further ORDINARY (3s) ticks
# the animation's own final frame stays on screen afterward, reusing
# the exact same hold/countdown mechanism one-shot event reactions
# already used before this round (SILLY_ONE_SHOT_HOLD_TICKS was the
# fixed value every one-shot used; animations may ask for a different
# hold via this field, one-shot non-animated reactions keep using the
# old fixed constant unchanged).
ANIMATIONS = {
    "quick_blink_pair": {
        "frames": ["idle", "blink", "idle", "blink", "idle"],
        "frame_gap_s": 0.12,
        "hold_ticks": 2,
    },
    "look_around_curious": {
        "frames": ["look_left", "idle", "look_right", "curious"],
        "frame_gap_s": 0.18,
        "hold_ticks": 2,
    },
    "startle_and_settle": {
        "frames": ["surprised", "waking", "idle"],
        "frame_gap_s": 0.15,
        "hold_ticks": 3,
    },
    "victory_flourish": {
        "frames": ["happy", "excited", "shipshape"],
        "frame_gap_s": 0.2,
        "hold_ticks": 4,
    },
    "wave_hello": {
        "frames": ["look_left", "idle", "look_right", "happy"],
        "frame_gap_s": 0.18,
        "hold_ticks": 3,
    },
}


def resolve_animation_frames(anim_id: str, tier: str, quip: str = None):
    """Turns ANIMATIONS[anim_id] into a list of ready-to-draw render-
    spec dicts (`{"render": {...}, "tier": tier}`, exactly the shape
    build_frame()'s "silly" page already expects) plus the burst's
    per-frame gap and the post-burst hold length. Returns
    (frame_specs, frame_gap_s, hold_ticks), or (None, None, None) for
    an unknown id (callers degrade to treating the render as a no-op,
    same fail-safe direction as an unknown `expression`/`scene` key
    already degrades to a blank frame in draw_face/draw_scene's own
    lookups elsewhere). `quip` is applied to the LAST frame only (a
    quip appearing mid-blink would be unreadable at 0.12-0.2s/frame -
    it belongs on the frame that actually holds still afterward)."""
    anim = ANIMATIONS.get(anim_id)
    if anim is None:
        return None, None, None

    frames = anim["frames"]
    specs = []
    for i, frame in enumerate(frames):
        if isinstance(frame, str):
            render = {"expression": frame}
        else:
            render = dict(frame)
        if quip and i == len(frames) - 1:
            render["quip"] = quip
        specs.append({"render": render, "tier": tier})
    return specs, anim["frame_gap_s"], anim["hold_ticks"]


# --- Personality-driven ambient mannerisms -----------------------------
#
# Deliberately NOT part of piratebox_progression.py's roll_event()/
# EVENT_FAMILIES engine, on purpose: that engine answers "which
# reaction to THIS specific moment" (a client arrived, it just woke
# up, the periodic flourish beat), gated by rarity/cooldown/condition/
# min_level. This function answers a different question - "given the
# plain ambient expression the tick-cycled pools in piratebox_oled_
# daemon.py already picked for an ordinary idle moment, should this
# PARTICULAR device's accumulated personality occasionally reshape it
# into a mannerism variant instead?" No rarity tiers, no cooldowns, no
# level gate - just a small, bounded, deterministic-given-the-same-RNG-
# draw substitution, so two devices with different histories can
# gradually develop visibly different idle habits (per the design
# brief) without either losing any base expression or needing its own
# whole rarity-engine entry per mannerism.
#
# Kept deliberately subtle: each bias only ever fires from a specific
# small subset of plain ambient expressions (never overriding an
# event/flourish/ssh-watch/sleeping/scene render - those already won
# the priority chain before this function is ever called), at a modest
# probability, and only when the relevant weight has actually drifted
# noticeably from the neutral 0.5 starting point (nudge_weight() in
# piratebox_progression.py moves it there gradually via real history -
# see that file). A freshly-born device (all weights at 0.5) never
# shows any of these - they emerge, they aren't preloaded.
# (weight name, direction, threshold, {eligible base expression -> substitute}, probability)
_MANNERISM_RULES = (
    ("vigilance",   "high", 0.65, {"idle": "watchful", "blink": "watchful"}, 0.14),
    ("sociability", "low",  0.35, {"idle": "wistful"}, 0.12),
    ("resilience",  "high", 0.65, {"idle": "resolute"}, 0.10),
)


def bias_ambient_expression(expression: str, weights: dict, rng: random.Random) -> str:
    """Given the plain ambient expression already chosen this tick,
    returns either that same expression unchanged (the common case) or
    a personality-mannerism substitute. `rng` is the SAME seeded/
    threaded random.Random the caller already uses for
    piratebox_progression.roll_event() (piratebox_oled_daemon.py's
    main() owns one instance for the process's lifetime) - passing a
    seeded one in tests makes this fully deterministic to verify.
    `weights` is Progression's own state["weights"] dict (sociability/
    vigilance/resilience, each 0.0-1.0) - a missing/empty dict
    degrades to "never substitutes anything," same fail-safe direction
    as everywhere else Progression's absence is tolerated. Rules are
    checked in order and the first eligible-and-rolled one wins (the
    three rules above target disjoint base expressions today, so
    ordering doesn't currently matter in practice, but a future rule
    added to this table should keep that in mind before assuming
    otherwise)."""
    if not weights:
        return expression
    for name, direction, threshold, subs, probability in _MANNERISM_RULES:
        if expression not in subs:
            continue
        value = weights.get(name, 0.5)
        active = (value >= threshold) if direction == "high" else (value <= threshold)
        if active and rng.random() < probability:
            return subs[expression]
    return expression


# --- Face/decoration drawing primitives -------------------------------

def draw_face(draw, eyes, brows, mouth: str, decoration: str = None) -> None:
    """Unchanged geometry/behavior from before this round for every
    pre-existing (eyes, brows, mouth, decoration) combination - moved
    here verbatim from piratebox_oled_daemon.py, plus additive new
    branches only (new eye styles "narrow"/"droopy", asymmetric `eyes`
    as a 2-tuple, and new decorations "eyepatch"/"tricorne"/"monocle"/
    "bandana"/"anchor_charm"). No existing branch's drawing changed."""
    cx, cy = FACE_CX, FACE_CY
    lx, rx = cx - EYE_DX, cx + EYE_DX

    if decoration == "crown":
        draw.polygon(
            [(cx - 16, cy - EYE_R - 12), (cx - 10, cy - EYE_R - 22), (cx - 4, cy - EYE_R - 12),
             (cx, cy - EYE_R - 22), (cx + 4, cy - EYE_R - 12), (cx + 10, cy - EYE_R - 22),
             (cx + 16, cy - EYE_R - 12)],
            outline="white",
        )
    elif decoration == "tricorne":
        # A small tricorne-hat silhouette - three flat brim segments
        # meeting in a shallow peak, sitting on the crown's own shelf
        # above the eyes so the two decorations never collide.
        draw.polygon(
            [(cx - 18, cy - EYE_R - 10), (cx - 6, cy - EYE_R - 20), (cx, cy - EYE_R - 14),
             (cx + 6, cy - EYE_R - 20), (cx + 18, cy - EYE_R - 10)],
            outline="white", fill="white",
        )
    elif decoration == "bandana":
        # A triangular cloth draped over the top of the head with a
        # small knotted tail trailing off one side.
        draw.polygon(
            [(cx - 20, cy - EYE_R - 6), (cx + 20, cy - EYE_R - 6),
             (cx + 8, cy - EYE_R - 18), (cx - 8, cy - EYE_R - 18)],
            outline="white", fill="white",
        )
        draw.line((cx + 18, cy - EYE_R - 8, cx + 26, cy - EYE_R - 2), fill="white", width=2)

    for ex in (lx, rx):
        is_right = (ex == rx)
        this_eye = "closed" if (decoration == "wink" and is_right) else eyes
        if isinstance(this_eye, tuple):
            this_eye = this_eye[1] if is_right else this_eye[0]
        box = (ex - EYE_R, cy - EYE_R, ex + EYE_R, cy + EYE_R)
        if this_eye == "closed":
            draw.line((ex - EYE_R, cy, ex + EYE_R, cy), fill="white", width=2)
        elif this_eye == "half":
            draw.arc(box, start=190, end=350, fill="white", width=2)
        elif this_eye == "narrow":
            # A watchful slit - shorter and flatter than "closed"'s
            # full-width line, centered slightly higher in the box so
            # it reads as narrowed rather than shut.
            draw.line((ex - EYE_R + 2, cy - 2, ex + EYE_R - 2, cy - 2), fill="white", width=2)
        elif this_eye == "droopy":
            # A heavy upper eyelid covering most of the eye - the
            # mirror emphasis of "half" (which reads as relaxed/smug):
            # this arc sits lower and wider, reading as tired rather
            # than amused.
            draw.arc(box, start=200, end=340, fill="white", width=3)
        elif this_eye == "wide":
            wbox = (ex - EYE_R - 2, cy - EYE_R - 2, ex + EYE_R + 2, cy + EYE_R + 2)
            draw.ellipse(wbox, outline="white", width=2)
            draw.ellipse((ex - 3, cy - 3, ex + 3, cy + 3), fill="white")
        elif this_eye in ("look_left", "look_right"):
            draw.ellipse(box, outline="white", width=2)
            shift = -(EYE_R - 4) if this_eye == "look_left" else (EYE_R - 4)
            draw.ellipse((ex + shift - 3, cy - 3, ex + shift + 3, cy + 3), fill="white")
        else:  # "open"
            draw.ellipse(box, outline="white", width=2)
            draw.ellipse((ex - 3, cy - 3, ex + 3, cy + 3), fill="white")

        if decoration == "eyepatch" and is_right:
            # Drawn AFTER the eye itself so it fully covers it,
            # regardless of whatever `eyes` style was requested for
            # this side - a solid patch with a strap, distinct from
            # "wink" (which just closes the lid, a momentary gesture,
            # not a pirate accessory).
            draw.rectangle((ex - EYE_R - 2, cy - EYE_R - 2, ex + EYE_R + 2, cy + EYE_R + 2), fill="black")
            draw.polygon((ex - EYE_R - 1, cy - EYE_R, ex + EYE_R + 1, cy + EYE_R), fill="black")
            draw.line((ex - EYE_R - 2, cy - EYE_R - 4, lx - EYE_R + 6, cy - EYE_R - 10), fill="white", width=1)
        elif decoration == "monocle" and is_right:
            draw.ellipse((ex - EYE_R - 3, cy - EYE_R - 3, ex + EYE_R + 3, cy + EYE_R + 3),
                         outline="white", width=1)
            draw.line((ex + EYE_R + 3, cy + EYE_R, ex + EYE_R + 6, cy + EYE_R + 10), fill="white", width=1)

        if brows == "raised":
            draw.line((ex - EYE_R, cy - EYE_R - 5, ex + EYE_R, cy - EYE_R - 8), fill="white", width=2)
        elif brows == "flat":
            draw.line((ex - EYE_R, cy - EYE_R - 4, ex + EYE_R, cy - EYE_R - 4), fill="white", width=2)
        elif brows == "one_raised" and is_right:
            draw.line((ex - EYE_R, cy - EYE_R - 3, ex + EYE_R, cy - EYE_R - 9), fill="white", width=2)

        if decoration == "sparkle":
            draw.line((ex - EYE_R - 3, cy - EYE_R - 2, ex - EYE_R - 7, cy - EYE_R - 6), fill="white", width=1)
            draw.line((ex + EYE_R + 3, cy - EYE_R - 2, ex + EYE_R + 7, cy - EYE_R - 6), fill="white", width=1)

    if decoration == "anchor_charm":
        # A tiny anchor glyph near the chin - a small, recurring
        # "Restless Anchor" brand motif rather than a functional
        # accessory, drawn last so it always sits on top of the mouth
        # area's own ink.
        ax, ay = cx, FACE_CY + 32
        draw.line((ax, ay - 4, ax, ay + 4), fill="white", width=1)
        draw.line((ax - 3, ay - 4, ax + 3, ay - 4), fill="white", width=1)
        draw.arc((ax - 4, ay - 1, ax + 4, ay + 7), start=0, end=180, fill="white", width=1)

    my = cy + 20
    if mouth == "smile_small":
        draw.arc((cx - 10, my - 6, cx + 10, my + 6), start=200, end=340, fill="white", width=2)
    elif mouth == "smile_big":
        draw.arc((cx - 16, my - 10, cx + 16, my + 8), start=200, end=340, fill="white", width=2)
    elif mouth == "o":
        draw.ellipse((cx - 6, my - 6, cx + 6, my + 6), outline="white", width=2)
    elif mouth == "o_small":
        draw.ellipse((cx - 4, my - 4, cx + 4, my + 4), outline="white", width=2)
    elif mouth == "flat":
        draw.line((cx - 8, my, cx + 8, my), fill="white", width=2)
    elif mouth == "wavy":
        draw.line([(cx - 10, my - 2), (cx - 4, my + 3), (cx + 2, my - 3), (cx + 8, my + 2)], fill="white", width=2)
    elif mouth == "smirk":
        draw.line((cx - 6, my + 2, cx + 8, my - 2), fill="white", width=2)


def draw_zzz(draw, font_small, tick: int) -> None:
    """Unchanged from before this round."""
    big = (tick % 2 == 0)
    draw.text((FACE_CX + 22, FACE_CY - 26), "z" if big else "Z", font=font_small, fill="white")
    draw.text((FACE_CX + 13, FACE_CY - 18), "Z" if big else "z", font=font_small, fill="white")


def draw_skull_and_crossbones(draw, x: int, y: int, color: str = "white", bg: str = "black") -> None:
    """Unchanged from before this round."""
    draw.ellipse((x, y, x + 24, y + 20), outline=color, fill=color)
    draw.ellipse((x + 4, y + 6, x + 10, y + 13), fill=bg)
    draw.ellipse((x + 14, y + 6, x + 20, y + 13), fill=bg)
    draw.polygon([(x + 12, y + 13), (x + 10, y + 17), (x + 14, y + 17)], fill=bg)
    draw.rectangle((x + 4, y + 19, x + 20, y + 24), outline=color, fill=color)
    for tx in range(x + 6, x + 20, 3):
        draw.line((tx, y + 19, tx, y + 24), fill=bg)
    draw.line((x - 4, y + 28, x + 28, y + 20), fill=color, width=2)
    draw.line((x - 4, y + 20, x + 28, y + 28), fill=color, width=2)


def draw_pirate_flourish(draw, font, font_small, quip: str) -> None:
    """Unchanged from before this round."""
    draw_skull_and_crossbones(draw, 2, 4)
    draw.text((38, 10), "PIRATEBOX", font=font, fill="white")
    draw.text((0, 46), quip, font=font_small, fill="white")


# --- SCENES: full-screen set-pieces, still static single frames -------
#
# `SCENES` is just an enumeration (for iteration/testing, mirroring how
# `EXPRESSIONS`'s keys are already iterated by tools/test_silly_mode.py)
# - the actual drawing lives in draw_scene()'s elif chain below, exactly
# like before this round. Kept static (not multi-frame) deliberately:
# a custom full-canvas set-piece needs bespoke per-frame drawing code
# to animate well, which is a much bigger cost per scene than the
# ANIMATIONS registry's reuse of existing face expressions as frames -
# not worth it for the modest number of scenes this project has. The
# two new scenes this round (compass_spin, night_watch) follow the
# same static-set-piece shape the original five already established.
SCENES = (
    "shooting_star", "message_bottle", "treasure_glimmer", "reunion", "logbook",
    "compass_spin", "night_watch",
)


def draw_scene(draw, font, font_small, scene: str) -> None:
    """The first five branches (shooting_star through logbook) are
    unchanged from before this round. compass_spin and night_watch are
    new. An unknown scene name still degrades to a plain idle face
    (unchanged fail-safe default)."""
    cx, cy = FACE_CX, FACE_CY
    if scene == "shooting_star":
        for sx, sy in ((14, 8), (100, 14), (60, 4), (30, 20), (110, 30)):
            draw.point((sx, sy), fill="white")
        draw.line((20, 10, 55, 24), fill="white", width=2)
        draw.polygon([(55, 24), (49, 20), (51, 27)], fill="white")
        draw_face(draw, "open", "raised", "o_small")
    elif scene == "message_bottle":
        draw.line((cx - 6, cy - 18, cx - 6, cy + 8), fill="white", width=2)
        draw.line((cx + 6, cy - 18, cx + 6, cy + 8), fill="white", width=2)
        draw.arc((cx - 6, cy - 4, cx + 6, cy + 14), start=0, end=180, fill="white", width=2)
        draw.line((cx - 6, cy + 8, cx + 6, cy + 8), fill="white")
        draw.line((cx - 3, cy - 22, cx - 3, cy - 18), fill="white", width=2)
        draw.line((cx + 3, cy - 22, cx + 3, cy - 18), fill="white", width=2)
        draw.rectangle((cx - 4, cy - 10, cx + 4, cy - 2), outline="white")
    elif scene == "treasure_glimmer":
        draw.rectangle((cx - 16, cy, cx + 16, cy + 14), outline="white")
        draw.arc((cx - 16, cy - 10, cx + 16, cy + 6), start=180, end=360, fill="white", width=2)
        for gx, gy in ((cx - 22, cy - 6), (cx + 20, cy - 4), (cx, cy - 14)):
            draw.line((gx - 3, gy, gx + 3, gy), fill="white")
            draw.line((gx, gy - 3, gx, gy + 3), fill="white")
    elif scene == "reunion":
        draw_face(draw, "wide", "raised", "smile_big")
        for dx, dy in ((-30, 10), (28, 6), (-22, -20), (34, -16), (0, -26)):
            draw.point((cx + dx, cy + dy), fill="white")
    elif scene == "logbook":
        draw.rectangle((cx - 20, cy - 16, cx + 20, cy + 16), outline="white")
        for ly in range(cy - 10, cy + 12, 6):
            draw.line((cx - 14, ly, cx + 14, ly), fill="white")
    elif scene == "compass_spin":
        # A simple compass rose - outer ring, four cardinal ticks, and
        # a needle held at a fixed artistic angle (this is a static
        # scene, not an animation - see the module note above).
        r = 22
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline="white", width=2)
        for angle_deg in (0, 90, 180, 270):
            import math
            rad = math.radians(angle_deg - 90)
            tx, ty = cx + (r - 4) * math.cos(rad), cy + (r - 4) * math.sin(rad)
            draw.line((cx, cy, tx, ty), fill="white", width=1)
        draw.polygon([(cx, cy - r + 6), (cx - 4, cy + 4), (cx, cy), (cx + 4, cy + 4)], fill="white")
    elif scene == "night_watch":
        # A crescent moon and a couple of stars over a small resting
        # silhouette - the quiet-hours counterpart to shooting_star's
        # daytime-agnostic wish-making moment.
        draw.ellipse((14, 6, 30, 22), outline="white", width=2)
        draw.ellipse((19, 4, 35, 20), fill="black", outline="black")
        for sx, sy in ((90, 10), (105, 20), (75, 6)):
            draw.point((sx, sy), fill="white")
        draw_face(draw, "closed", "none", "flat")
    else:
        draw_face(draw, "open", "none", "smile_small")
