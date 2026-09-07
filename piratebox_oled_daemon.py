#!/usr/bin/env python3
#
# PirateBox OLED status display daemon - Stage 29 (Physical Control UX)
# / Stage 11 (Hardware Integration) implementation.
#
# Drives a 0.96" SSD1306 128x64 I2C OLED (bus 1, address 0x3C - GPIO2/
# SDA and GPIO3/SCL, physical pins 3/5) with a rotating glanceable-status
# display, following docs/PHYSICAL-CONTROL-UX-DESIGN.md's four-page
# design (Status -> Time -> Network -> Health) and docs/HARDWARE-
# INTEGRATION-DESIGN.md §5/§7's "never required for operation" contract.
#
# WHAT THIS DOES:
#   Reads only data that already exists and is already world-readable -
#   nothing here computes new PirateBox state or duplicates a privileged
#   read:
#     - /tmp/piratebox/mode           (same file every mode-aware page
#                                       reads; missing/invalid -> Normal,
#                                       identical fallback to
#                                       includes/mode.php's own logic)
#     - /run/piratebox/status.json    (written every 30s by the existing
#                                       root-run piratebox_status_helper.sh
#                                       - wifi_clients, per-service health,
#                                       power/undervoltage, time-source)
#     - /var/www/html/data/mode-transitions.log
#                                     (cumulative Emergency Mode runtime -
#                                       same append-only log
#                                       includes/metrics.php's
#                                       piratebox_get_emergency_runtime_
#                                       seconds() reads; the arithmetic
#                                       below is a direct port of that
#                                       function so both readers agree)
#     - /etc/hostapd/hostapd.conf    (SSID - parsed once per redraw,
#                                       cheap, avoids hardcoding a value
#                                       that could drift from real config)
#     - /proc/uptime, os.statvfs("/") (uptime, disk free/total - plain,
#                                       unprivileged, same facts the admin
#                                       page already computes)
#   The Wi-Fi AP's IP address (10.0.0.1) is NOT looked up - it is fixed
#   by this project's network design (static dhcpcd config), the same
#   assumption docs/HARDWARE-INTEGRATION-DESIGN.md's own content plan
#   makes explicit ("already known/fixed... no lookup needed").
#
# NEVER REQUIRED FOR OPERATION (hard requirement, not a goal):
#   This process holds no lock, writes no PirateBox data file, and is
#   never imported or shelled out to by anything else. If this daemon
#   is stopped, crashes, or the display is unplugged, Core (the AP and
#   site) and every other PirateBox service continue exactly as they do
#   today - see docs/ARCHITECTURE.md §2.
#
# DEGRADE, DON'T CRASH, WHEN THE DISPLAY ISN'T THERE:
#   If the OLED can't be initialized at startup (unplugged, wrong
#   address, I2C not enabled), this process logs once and waits, retrying
#   at a fixed interval - it does NOT busy-loop and does NOT exit/crash
#   (which would otherwise trip systemd's restart-count limit and leave
#   the service permanently dead until manually restarted). If the
#   display disappears mid-run (a real I2C write failure), the same
#   retry-until-found loop resumes automatically - "recovers when
#   hardware becomes available," per instruction, without needing an
#   external restart. Any *unexpected* exception outside that recovery
#   path still propagates and exits non-zero, so systemd's own
#   Restart=on-failure remains the backstop, not a substitute for this
#   daemon's own graceful path.
#
# NOT BUSY-POLLING, NO UNNECESSARY SD CARD WRITES:
#   Every data source above is read, never written, by this process.
#   The main loop sleeps (time.sleep) between redraws - no tight poll,
#   no per-event file, no JSON store of its own.
#
# DISPLAY POWER BEHAVIOR:
#   docs/PHYSICAL-CONTROL-UX-DESIGN.md §5 specifies dim-after-60s-idle,
#   waking on a button press (GPIO23, "wake display"). That button is
#   NOT physically wired yet (this bring-up is OLED-only) - dimming
#   with no way to wake it back up would defeat the display's entire
#   glanceable-status purpose (worse than staying bright, not better),
#   so auto-dim is deliberately NOT enabled by default here. The
#   set_contrast() plumbing below exists and is ready to be driven by a
#   future button callback the moment GPIO23 is wired - no redesign
#   needed, just wiring a call to it.
#
# PAGE ROTATION WITHOUT A CYCLE BUTTON:
#   §1's four-page cycle is specified as button-driven (GPIO22, also not
#   wired yet). Absent that input, this daemon auto-advances through the
#   same four pages on a fixed timer, so all four categories of status
#   stay visible over time rather than freezing on whichever page
#   happened to be current at boot. PAGE_ORDER/PAGE_SECONDS below are
#   the only two things a future button-driven implementation needs to
#   replace (swap the timer-driven advance for a button callback calling
#   the exact same render_<page>() functions) - the render functions
#   themselves don't change.
#
# PRIVILEGE BOUNDARY:
#   Runs as the existing dedicated, unprivileged piratebox-gpio system
#   user (already used by piratebox-button.service), with an added
#   SupplementaryGroups=i2c for /dev/i2c-1 access - never root, never
#   www-data, requests no sudo grant of any kind (this daemon has no
#   action to escalate to, unlike the shutdown button).
#
# PERSONALITY MODE (added round 7, 2026-09-03) - a small, bounded fun
# layer while the OLED sits exposed on the desk with no enclosure yet:
#   - A tiny procedurally-drawn skull-and-crossbones plus a rotating
#     one-line quip, shown as a fifth page inserted sparingly into the
#     rotation (every PERSONALITY_EVERY_N_CYCLES full cycles of the
#     four serious pages - roughly every several minutes, not every
#     few seconds). It replaces one "status" page slot for one
#     PAGE_SECONDS interval, then rotation continues exactly as before.
#   - A one-shot "a client joined" quip when status.json's wifi_clients
#     count goes up since the last redraw - reusing the exact same
#     aggregate counter the Status page already reads, not a new signal
#     or any per-client tracking.
#   - A one-shot uptime-milestone quip (1 day, 1 week) the first time
#     this process observes /proc/uptime crossing that threshold.
#   - ALL personality frames are gated by personality_allowed() below:
#     suppressed entirely in Emergency Mode, whenever status.json is
#     stale/missing, whenever any of the four Core services
#     (hostapd/dnsmasq/nginx/php8.4-fpm) is down, or whenever
#     power.undervoltage_now is true. A serious health/degraded
#     condition always wins - the display falls straight through to
#     the Health page instead of ever showing a quip while something
#     is actually wrong.
#   - Zero new state files: the "have I shown this milestone/
#     celebration yet" bookkeeping lives in plain Python variables in
#     main()'s own loop, not written to disk anywhere - it resets on
#     every service restart, which is fine for a cosmetic feature and
#     keeps the "no unnecessary SD card writes" contract intact.
#   - No animation loop, no external image/font asset, no new
#     dependency: the skull is drawn with a handful of Pillow
#     primitives (ellipses/lines) already used by every other page.
#
# SILLY MODE (added 2026-09-04) - REPLACES the "PERSONALITY MODE" block
# above with a single, user-toggleable, substantially more expressive
# personality layer. The old always-on sparse quip/celebration/milestone
# frames described above are GONE, folded into this - per instruction,
# this project doesn't keep two unrelated personality systems side by
# side. If Silly Mode is off (the default, every boot), the OLED is
# exactly the four serious pages, nothing else - no quips, no
# celebrations, no milestones. This is a deliberate behavior change from
# the old always-on-when-healthy quip, not an oversight.
#
#   - Explicit, instant, user-controlled toggle: `piratebox-silly
#     {on,off,status}` (unprivileged - this is a cosmetic desk toy, not
#     trusted operational state like Normal/Emergency Mode, so it does
#     NOT go through set_piratebox_mode.sh's root-only path). State
#     lives in one plain-text file, /tmp/piratebox/silly, containing
#     "on" or anything else (missing/garbage/"off" -> off, same
#     fail-safe-default discipline as MODE_FILE) - tmpfs, so it resets
#     to the default OFF on every reboot, matching the instruction that
#     there's no compelling reason to persist it.
#
#   - REAL, PREVIOUSLY-LATENT BUG FIXED as a prerequisite: this service
#     has always run with PrivateTmp=yes (originally added so Pillow's
#     font cache and gpiozero's notification pipe get a writable /tmp -
#     see the WorkingDirectory note above), which gives it its OWN
#     private /tmp mount namespace - it could never actually see the
#     real /tmp/piratebox/mode the operator's set_piratebox_mode.sh
#     writes, or (until now) any new /tmp/piratebox/silly toggle
#     either. `read_mode()` has silently always returned "normal" here,
#     regardless of the real state - meaning the existing mode-
#     transition banner and personality gating have never actually
#     reacted to a real Emergency Mode toggle on this hardware. Fixed
#     by pre-creating /tmp/piratebox (root:root 0755, matching
#     set_piratebox_mode.sh's own mkdir/chmod) via etc/tmpfiles.d/
#     piratebox-tmp.conf at boot - BEFORE this service starts, so it's
#     guaranteed to exist - and adding `BindReadOnlyPaths=/tmp/
#     piratebox:/tmp/piratebox` to piratebox-oled.service, which bind-
#     mounts that real host directory (read-only) into this service's
#     private /tmp namespace. Because it's a live bind of the
#     directory (not a one-time copy), files created inside it later -
#     including the very first `sudo ./set_piratebox_mode.sh emergency`
#     or the very first `piratebox-silly on` after a fresh boot -
#     become visible immediately, no service restart needed. This is a
#     correctness fix for the exact safety property Silly Mode depends
#     on (Emergency Mode must actually be observable to take priority),
#     not new Silly Mode behavior itself.
#
#   - PRIORITY MODEL (mandatory, checked fresh every tick, never
#     cached): compute_display_tier() below returns exactly one of:
#       "emergency" - Emergency Mode is active (MODE_FILE == "emergency").
#                      Always wins. Silly Mode never runs; the existing
#                      serious rotation + mode-transition banner are the
#                      entire display, unchanged from before this round.
#       "fault"     - status.json missing/stale, or any Core service
#                      (hostapd/dnsmasq/nginx/php8.4-fpm) is down. A
#                      real, actionable, currently-unknown-duration
#                      problem - Silly Mode never runs; falls straight
#                      to the serious rotation, same as "emergency"
#                      (this is the old personality_allowed()'s
#                      strictest gate, preserved exactly).
#       "warning"   - otherwise healthy, but power.undervoltage_now is
#                      true (this Pi's known, chronic, already-
#                      documented condition - see docs/POWER-INTEGRITY-
#                      DIAGNOSIS.md - not a new/actionable event).
#                      Silly Mode MAY run if enabled, but every Silly
#                      frame carries a small, fixed, always-drawn
#                      warning badge (top-left corner) so the condition
#                      stays unmistakable without blocking the display's
#                      fun purpose over an already-known, non-worsening
#                      condition - per instruction, "a persistent
#                      warning indicator may be better than permanently
#                      suppressing all personality."
#       "ok"        - fully healthy. Silly Mode may run with no badge.
#     Silly Mode itself is only ever considered at all when the tier is
#     "warning" or "ok" AND the operator has it toggled on - "emergency"
#     and "fault" both fall straight through to the exact same serious-
#     page code path that ran before this round, untouched.
#
#   - EXPRESSIONS: a face (two eyes, optional brows, a mouth, optional
#     decoration) drawn with the same plain Pillow primitives every
#     other page already uses - no image asset, no icon font, no new
#     dependency. See EXPRESSIONS below for the full set: idle/blink/
#     look-left/look-right (ambient), sleeping/waking (idle-triggered),
#     happy/excited/surprised (activity-triggered), confused (a client
#     leaving, or ambient while idle), smug (ambient, ordinary healthy
#     activity), ssh_watch (someone's SSHed in right now - see below),
#     and pirate_flourish (the evolved skull-and-crossbones + a short
#     original quip, replacing the old standalone "personality" page).
#
#   - REACTS TO REAL STATE, CHEAPLY, WITH NO NEW POLLING:
#       - wifi_clients rising/falling: the exact same status.json field
#         every other page already reads every tick - a rise from zero
#         triggers "excited," a further rise triggers "surprised," a
#         drop to zero triggers "confused," matching this project's
#         "no per-client tracking, aggregate count only" privacy
#         discipline exactly.
#       - idle duration: in-memory only (a timestamp updated whenever
#         the client count changes, compared against time.time() every
#         tick) - no new file, no new read. Past SILLY_SLEEP_AFTER_
#         SECONDS with zero clients, the face goes to "sleeping" until
#         a client reappears ("waking", one-shot) or SSH activity is
#         observed.
#       - SSH/admin activity: read_ssh_established() below reads
#         /proc/net/tcp(6) - already-exposed, unprivileged, whole-
#         system socket state Linux always maintains, checked for
#         local port 22 in state ESTABLISHED. This is ONE cheap file
#         read (no subprocess, no `ss`/`netstat` spawn), reused at the
#         same REFRESH_SECONDS cadence as everything else, and reports
#         only a live yes/no for "is anyone connected right now" - no
#         session content, no source IP/duration logged or persisted
#         anywhere, satisfying the "clean, lightweight, privacy-
#         preserving, no invasive session logging" instruction exactly.
#       - service health / the tier itself: same status.json read as
#         above, nothing new.
#
#   - NO NEW POLLING, NO FASTER REDRAW LOOP: Silly Mode redraws on the
#     exact same REFRESH_SECONDS=3.0s cadence as every other page - it
#     does not add a second loop, a thread, or a shorter sleep.
#     "Animation" (blinking, looking around) is simply which expression
#     gets chosen this tick, driven by a plain tick-counter modulo - see
#     compute_silly_expression() - so it looks alive without writing to
#     the display any more often than before. A periodic status
#     interlude (SILLY_CADENCE_STATUS_SECONDS of the real serious
#     rotation, alternating with SILLY_CADENCE_PERSONALITY_SECONDS of
#     ambient personality - see "PERSONALITY-VS-STATUS CADENCE" below)
#     keeps glanceable status genuinely reachable without needing to
#     turn Silly Mode off - real airtime, not a one-tick glance.
#
#   - FUTURE RGB COMPATIBILITY (not implemented now, per instruction):
#     compute_display_tier() and compute_silly_expression() are pure
#     functions of already-available state, deliberately kept separate
#     from any OLED-specific drawing code. A future addressable-RGB
#     status light can import/re-derive the same tier + expression
#     values and just skip the drawing step - this file does not import
#     or reference any lighting library, so no new dependency exists
#     yet, but the *shape* of "one personality/activity signal, one
#     priority order with Emergency/Fault always on top" is already
#     right here for that to plug into later without a redesign.
#
#   - Zero new state files beyond the one plain toggle: everything else
#     (idle timers, one-shot hold counters, last-seen client count) is
#     the same kind of plain in-memory bookkeeping main() already used
#     for the old personality/pulse features - resets on restart, never
#     written to disk, per this file's existing "no unnecessary SD card
#     writes" contract.
#
# PERSONALITY-VS-STATUS CADENCE (added 2026-09-04, "OLED cadence
# rebalance" round; extended 2026-09-04, "Distance/Glance Display"
# round) - makes Silly Mode read as "a useful status display with a
# personality," not "a face display with occasional stats." While
# Silly Mode is on and healthy (tier "ok"/"warning", no override active
# - see below), the display cycles through three phases:
#   - "personality": SILLY_CADENCE_PERSONALITY_SECONDS (~30s) of the
#     ambient/event/flourish behavior described above, unchanged.
#   - "glance": SILLY_CADENCE_GLANCE_SECONDS (~8s) of ONE large-format,
#     at-a-distance page (CPU/RAM/disk/clients/uptime/time/power - see
#     piratebox_glance.py) - added this round, trimming personality's
#     own share slightly to make room rather than lengthening the
#     overall cycle, per instruction not to let glance take over.
#   - "status": SILLY_CADENCE_STATUS_SECONDS (~15s) of the exact same
#     serious Status/Time/Network/Health rotation this daemon always
#     had - not a special "silly-mode status page," the real one,
#     including its own undervoltage-warning box on the Health page.
#     Deliberately UNCHANGED duration/share from before this round -
#     the detailed-status baseline this file's own instructions
#     protect is the "status" phase, not "glance," which is new,
#     additive airtime alongside it, not a replacement for any of it.
# The phase clock only advances while this cadence is actually driving
# the display - a sleep/one-shot-event-hold/pending-achievement-reveal/
# short-press-override interruption (all of which already took priority
# over ambient cycling before this round) PAUSES it rather than losing
# time, so "important events may interrupt this cadence" (per
# instruction) falls out of the existing precedence order for free,
# with no special-casing needed against the cadence itself. A SEPARATE,
# simpler two-phase cadence (advance_offline_glance_cadence() below)
# gives glance pages the same kind of occasional airtime when Silly
# Mode is OFF, alternating with the plain serious rotation instead of
# with personality - see that function's own comment for why a second,
# smaller cadence was the cleaner choice here rather than forcing one
# mechanism to serve two genuinely different contexts (the Silly-on
# cadence also has to respect sleep/hold/reveal states that simply
# don't exist when Silly is off at all).
#
# SHORT-PRESS STATUS-CHECK OVERRIDE (added 2026-09-04, same round) -
# reuses the existing physical shutdown button's ALREADY-tested
# short-press/long-hold distinction (piratebox_button_daemon.py) rather
# than adding a second button or a new debounce/hold state machine.
# That daemon's on_released() writes a plain Unix timestamp to
# STATUS_CHECK_REQUEST_FILE on a genuine short press (never on the
# release that follows a triggered long-press/shutdown - see that
# file's own `_hold_just_fired` guard) - this daemon reads it fresh
# every tick via read_status_check_active() and treats it as "active"
# for STATUS_CHECK_WINDOW_SECONDS (~15s) purely by recency, no request/
# acknowledge protocol needed. A repeated press naturally re-extends the
# window (a newer timestamp overwrites the old one). Ranks above Silly
# Mode/personality but below Emergency/fault in the priority order (see
# main()'s own branch chain) - a button tap can get you a quick real-
# status glance, it can never hide an actual problem. Deliberately a
# generic file-based signal, not a direct call from the button daemon
# into this one: per instruction, ANY future trigger (another button, a
# CLI command, an admin-UI action) could produce the identical signal
# with zero change needed here.
#
# INSTRUMENT-PANEL POLISH (round 8, 2026-09-03) - improves how the four
# serious pages themselves present, without changing what they're
# allowed to show or when. Philosophy: mostly static information plus
# brief, meaningful motion - animation communicates a real state
# change, it doesn't run just because it can.
#   - Every serious page now has a small header bar (inverted, like an
#     instrument label) with a tiny procedural icon and a heartbeat dot
#     that flips every redraw tick - proof the loop is alive, not
#     frozen, distinguishable from a genuinely stuck display.
#   - Status page gains a small Wi-Fi bars glyph (filled = clients
#     present, outline = none) and a brief inverted "pulse" on the
#     client count for the couple of redraws right after it increases -
#     this pulse is NOT personality-gated (it's plain operational
#     information, so it still fires in Emergency Mode or a degraded
#     state, unlike the separate, gated "celebration" quip page).
#   - Network page gains a small filled/hollow dot per Core service
#     instead of only a text count.
#   - Health page gains a compact horizontal storage-used bar, and its
#     undervoltage warning is now boxed for higher visual salience -
#     still one line, still conditional, still never hidden by
#     anything cosmetic.
#   - A brief (~150ms, four-frame) horizontal wipe plays when the
#     display auto-advances from one serious page to the next in the
#     normal rotation - it does NOT play for one-shot frames
#     (personality/celebration/milestone/mode-transition), keeping
#     those as instant, simple swaps. This is the only recurring
#     motion in the whole daemon, and it is tied to an actual page
#     change (once per PAGE_SECONDS), not a constant/ambient effect.
#   - A new one-shot mode-transition frame (brief, inverted, NOT
#     personality-gated - shows in Emergency Mode and under a degraded
#     condition, since "which mode is active" is exactly the kind of
#     thing that matters most when something else is already wrong)
#     appears the moment this daemon observes MODE_FILE's value
#     actually change, in either direction.
#   - None of this adds a new data source, a new file write, or a new
#     dependency - same Pillow primitives, same read-only inputs.

import json
import logging
import os
import random
import re
import signal
import sys
import time

from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont

# Expression Engine v2 (2026-09-04) - see that module's own header, and
# the "Silly Mode face rendering" comment further down this file, for
# why every drawing primitive/data table lives there now, not here.
from piratebox_expressions import (
    EXPRESSIONS, ANIMATIONS, SCENES, FACE_CX, FACE_CY, EYE_DX, EYE_R,
    draw_face, draw_zzz, draw_pirate_flourish, draw_scene,
    draw_skull_and_crossbones, resolve_animation_frames, bias_ambient_expression,
)

# Distance / Glance Display (2026-09-04) - large-format, at-a-distance
# pages. Same separation as the Expression Engine v2 import above: this
# daemon owns state acquisition (reading /proc, status.json) and
# scheduling integration; piratebox_glance.py owns eligibility/
# weighting selection and pixel-level rendering, and touches no I/O of
# its own - see that module's own header for the full rationale.
from piratebox_glance import (
    GLANCE_PAGES, GLANCE_PREVIEW_ORDER, LABEL_FONT_SIZES, render_glance_page, select_glance_page,
)

I2C_PORT = 1
I2C_ADDRESS = 0x3C
RETRY_SECONDS = 20.0          # how long to wait between init attempts
                               # while the display is missing/unreachable
REFRESH_SECONDS = 3.0         # how often data is re-read and redrawn
PAGE_SECONDS = 8.0            # how long each page stays up before
                               # auto-advancing (see header note above)
STALE_AFTER_SECONDS = 300     # matches includes/metrics.php's own
                               # piratebox_get_helper_status() staleness
                               # window exactly, so both readers agree

MODE_FILE = "/tmp/piratebox/mode"
SILLY_FILE = "/tmp/piratebox/silly"   # see "SILLY MODE" header note - same
                                       # directory as MODE_FILE, now
                                       # reliably bind-mounted into this
                                       # service's private /tmp (see
                                       # piratebox-oled.service)
STATUS_CHECK_REQUEST_FILE = "/tmp/piratebox/status-check-request"  # short-
                                       # press signal from piratebox_button_
                                       # daemon.py - see read_status_check_
                                       # active() below and that file's own
                                       # STATUS_CHECK_REQUEST_FILE comment
STATUS_CHECK_WINDOW_SECONDS = 15.0    # how long a press keeps the override active
SILLY_TOGGLE_REQUEST_FILE = "/tmp/piratebox/silly-toggle-request"  # double-
                                       # tap confirmation signal from
                                       # piratebox_button_daemon.py's
                                       # toggle_silly_mode() - see
                                       # read_silly_toggle_edge() below.
                                       # Purely cosmetic: the actual new
                                       # state is read fresh from SILLY_FILE
                                       # itself, never duplicated into this
                                       # file's own content.
PREVIEW_REQUEST_FILE = "/tmp/piratebox/silly-preview-request"  # operator-
                                       # only "show me common expressions"
                                       # request from `piratebox-silly
                                       # preview` - see read_preview_active()
                                       # and PREVIEW_PLAYLIST below. Same
                                       # recency-based, no-acknowledge
                                       # pattern as STATUS_CHECK_REQUEST_FILE.
PREVIEW_WINDOW_SECONDS = 45.0         # long enough to see the whole
                                       # PREVIEW_PLAYLIST once at a
                                       # relaxed pace, short enough that
                                       # a forgotten preview can't run
                                       # for long unattended
GLANCE_PREVIEW_REQUEST_FILE = "/tmp/piratebox/glance-preview-request"  # operator-
                                       # only "show me the ordinary glance
                                       # pages" request from `piratebox-silly
                                       # glance-preview` - independent of
                                       # PREVIEW_REQUEST_FILE above (that one
                                       # demos Silly content and requires
                                       # Silly Mode on; glance pages work
                                       # regardless of Silly on/off, so this
                                       # gets its own signal file rather
                                       # than reusing that one's gate).
GLANCE_PREVIEW_WINDOW_SECONDS = 45.0
STATUS_FILE = "/run/piratebox/status.json"
# Environment web UI round (2026-09-07): a small, narrowly-scoped
# public export for hardware sensor readings - deliberately NOT
# progression-public.json (that file is Progression/Captain's Log's
# own spoiler-safe export; sensors are a different, non-secret concern
# and get their own file rather than broadening that one). Written by
# THIS process only, since it's the one place a registered sensor
# reader's own internal rate-limiting/caching actually lives in memory
# - see publish_sensors_export() below for why that matters. The
# directory is created fresh on every start by systemd itself
# (piratebox-oled.service's own `RuntimeDirectory=piratebox-sensors`),
# owned by this daemon's account, mode 0755 (world-traversable, same
# pattern as /run/piratebox itself) so PHP (www-data) can read the
# 0644 file this daemon writes inside, via its open_basedir allowlist -
# no manual mkdir, no etc/tmpfiles.d rule needed for this one.
SENSORS_PUBLIC_DIR = "/run/piratebox-sensors"
SENSORS_PUBLIC_FILE = SENSORS_PUBLIC_DIR + "/sensors-public.json"
SENSORS_PUBLISH_INTERVAL_S = 20.0  # independent of any single sensor's
                                     # own internal read rate-limit -
                                     # this just serializes whatever the
                                     # currently-cached reading is
TRANSITIONS_LOG = "/var/www/html/data/mode-transitions.log"
HOSTAPD_CONF = "/etc/hostapd/hostapd.conf"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
SSH_TCP_TABLES = ("/proc/net/tcp", "/proc/net/tcp6")
SSH_PORT = 22

# Fixed by this project's network design (static dhcpcd config) - not
# looked up, per docs/HARDWARE-INTEGRATION-DESIGN.md §5's own content
# plan ("already known/fixed... no lookup needed").
AP_IP_ADDRESS = "10.0.0.1"

# Silly Mode tuning (see header note above). All cadences are expressed
# in ticks - one tick = one REFRESH_SECONDS redraw (3s) - so Silly Mode
# never redraws any faster than the rest of this daemon already does.
SILLY_SLEEP_AFTER_SECONDS = 600.0     # 10 idle minutes (zero clients) -> sleeping
SILLY_ONE_SHOT_HOLD_TICKS = 3         # how long an event reaction (excited/
                                       # surprised/confused/waking) stays up
                                       # before falling back to ambient (~9s)
SILLY_FLOURISH_EVERY_TICKS = 45       # ~135s between pirate-flourish/quip beats
SILLY_SSH_WATCH_EVERY_TICKS = 14      # ~42s - only actually shown if SSH is active

# Personality-vs-status cadence (2026-09-04, "OLED cadence rebalance"
# round): Silly Mode alternates between an ambient/personality phase and
# a status-interlude phase, so the OLED reads as "a useful status
# display with a personality," not "a face display with occasional
# stats." Both are expressed in seconds (not ticks, unlike the other
# SILLY_* constants above) because the phase clock only advances while
# this cadence is actually the active display mode - see main()'s own
# comment on why an event hold/sleep/pending-reveal effectively PAUSES
# it rather than losing time. Replaces the old single-tick-every-60s
# "peek" mechanic entirely - a five-tick status interlude reads as
# genuinely useful, a one-tick glance didn't.
SILLY_CADENCE_PERSONALITY_SECONDS = 30.0   # trimmed slightly from 36s
                                             # (2026-09-04) to make room
                                             # for the new glance phase
                                             # below, without lengthening
                                             # the overall cycle
SILLY_CADENCE_GLANCE_SECONDS = 8.0          # NEW (2026-09-04) - one
                                             # large-format at-a-distance
                                             # page, see piratebox_glance.py
SILLY_CADENCE_STATUS_SECONDS = 15.0        # ~12-15s of the real Status/Time/
                                             # Network/Health rotation -
                                             # UNCHANGED by the glance round

# Offline (Silly Mode OFF) glance cadence - see advance_offline_
# glance_cadence() below. Deliberately a much larger rotation share
# than glance's share of the Silly-on cadence above: when Silly is off,
# the plain serious rotation IS the primary display, not a competing
# phase alongside personality - glance is a genuinely occasional guest
# here, not a co-equal partner.
OFFLINE_GLANCE_ROTATION_SECONDS = 40.0
OFFLINE_GLANCE_SECONDS = 8.0

# Ambient (no event happening) expression cycles - one entry picked per
# tick via tick % len(cycle), so the face is never static for long but
# never redraws faster than the existing loop already does. Two
# separate cycles (idle vs. active) so the "vibe" matches whether anyone
# is actually connected right now.
AMBIENT_NO_CLIENTS = [
    "idle", "idle", "blink", "look_left", "idle",
    "confused", "idle", "look_right", "idle", "blink",
]
AMBIENT_WITH_CLIENTS = [
    "happy", "idle", "blink", "look_right", "happy",
    "smug", "idle", "look_left", "happy", "blink",
]

# Original PirateBox-flavored one-liners for the occasional pirate-
# flourish beat - deliberately short (fits font_small at 128px), and
# deliberately NOT a copy of any other project's persona/phrasing.
# {n} is substituted with the current client count where present.
SILLY_QUIPS = [
    "Radio go brrr.",
    "Oh hai, matey.",
    "LAN acquired.",
    "{n} scallywag(s)!",
    "Offline. As intended.",
    "Channel six, ahoy.",
    "Few bars, big heart.",
    "Off-grid, lovin' it.",
    "Mast up, hope's low.",
    "Come aboard, matey.",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s piratebox-oled: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("piratebox-oled")


# --- Data readers -----------------------------------------------------
# Every function below is a plain, unprivileged, read-only file access.
# Each fails toward a safe/honest default on any error rather than
# raising - a missing or malformed data source degrades one field, never
# the whole display.

def read_mode() -> str:
    """Mirrors includes/mode.php's piratebox_get_mode() exactly: missing
    file, or anything other than the literal string 'emergency', is
    Normal. There is no third state exposed anywhere in this project."""
    try:
        with open(MODE_FILE, "r") as f:
            value = f.read().strip().lower()
        return "emergency" if value == "emergency" else "normal"
    except OSError:
        return "normal"


def read_status_json():
    """Returns (status_dict_or_None, stale_bool). 'stale' mirrors
    piratebox_get_helper_status()'s exact rule: missing/unparseable, or
    older than STALE_AFTER_SECONDS, is stale. A stale/missing snapshot
    means every field derived from it is reported as unknown, never as
    a fabricated healthy-looking value."""
    try:
        with open(STATUS_FILE, "r") as f:
            raw = f.read()
        status = json.loads(raw)
        if not isinstance(status, dict):
            return None, True
        age = time.time() - float(status.get("generated_at", 0))
        return status, age > STALE_AFTER_SECONDS
    except (OSError, ValueError):
        return None, True


def publish_sensors_export(bh1750_module, last_publish: float, now: float) -> float:
    """Coalesced write (same pattern as piratebox_progression.py's own
    maybe_save_and_report()): writes at most once every
    SENSORS_PUBLISH_INTERVAL_S. Returns the new last-publish time
    (unchanged if this call didn't write). Reads no hardware itself -
    `bh1750_module` is either None (never imported - see this file's
    startup section) or the already-imported module
    (`piratebox_esp32_bh1750` as of the 2026-09-07 ESP32 migration),
    whose get_diagnostics() just returns its own already-cached state
    (no new I2C/serial transaction is triggered by publishing).

    A sensor only ever appears in the output dict if its module
    actually imported successfully - hardware that was never wired
    must never show up as a permanent "unavailable" entry (see this
    project's own "do not show fake/permanent-empty cards" rule for
    the web UI this feeds)."""
    if now - last_publish < SENSORS_PUBLISH_INTERVAL_S:
        return last_publish

    sensors = {}
    if bh1750_module is not None:
        try:
            diag = bh1750_module.get_diagnostics()
            sensors["ambient_light"] = {
                "detected": bool(diag.get("detected")),
                "lux": diag.get("lux"),
                "stale": bool(diag.get("stale")),
                "last_success_seconds_ago": diag.get("last_success_seconds_ago"),
            }
        except Exception:  # noqa: BLE001 - a broken diagnostics call must
            pass            # never stop publishing (or crash the daemon)

    try:
        os.makedirs(SENSORS_PUBLIC_DIR, exist_ok=True)
        tmp_path = f"{SENSORS_PUBLIC_FILE}.tmp.{os.getpid()}"
        with open(tmp_path, "w") as f:
            json.dump({"generated_at": int(now), "sensors": sensors}, f)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, SENSORS_PUBLIC_FILE)
    except OSError:
        pass  # optional export - never worth crashing the daemon over

    return now


def read_emergency_runtime_seconds() -> float:
    """Direct port of includes/metrics.php's
    piratebox_get_emergency_runtime_seconds() arithmetic, reading the
    exact same log file, so both readers always agree. Missing file or
    unparseable lines degrade to 0 / skipped, never an error."""
    try:
        with open(TRANSITIONS_LOG, "r") as f:
            raw = f.read()
    except OSError:
        return 0.0

    total = 0.0
    emergency_started_at = None
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\d+)\s+(normal|emergency)$", line)
        if not m:
            continue
        ts, mode = int(m.group(1)), m.group(2)
        if mode == "emergency":
            if emergency_started_at is None:
                emergency_started_at = ts
        else:
            if emergency_started_at is not None:
                total += max(0, ts - emergency_started_at)
                emergency_started_at = None
    if emergency_started_at is not None:
        total += max(0, time.time() - emergency_started_at)
    return total


def read_silly_enabled() -> bool:
    """Mirrors read_mode()'s exact fail-safe shape: missing file,
    unreadable file, or any content other than the literal string 'on'
    resolves to False (off) - the only safe default, matching the
    instruction that Silly Mode starts OFF after every boot. Written by
    the unprivileged `piratebox-silly` CLI, not by set_piratebox_mode.sh -
    this is a cosmetic toggle, not trusted operational state."""
    try:
        with open(SILLY_FILE, "r") as f:
            return f.read().strip().lower() == "on"
    except OSError:
        return False


def read_ssh_established() -> bool:
    """Whole-system 'is anyone SSHed in right now' - a single cheap read
    of the kernel's own already-exposed, unprivileged TCP socket table
    (no subprocess, no `ss`/`netstat`), checked for local port 22 in
    state 01 (ESTABLISHED). Reports only a live yes/no for this instant;
    nothing about who, when, or for how long is read, kept, or written
    anywhere - satisfies the "no invasive session logging" instruction
    by construction, not by omission. Missing/unreadable table(s)
    (e.g. IPv6 disabled) degrade to "not found" for that table only,
    never an error."""
    port_hex = f"{SSH_PORT:04X}"
    for path in SSH_TCP_TABLES:
        try:
            with open(path, "r") as f:
                lines = f.readlines()[1:]  # skip the header row
        except OSError:
            continue
        for line in lines:
            fields = line.split()
            if len(fields) < 4:
                continue
            local_addr, state = fields[1], fields[3]
            if state == "01" and local_addr.rsplit(":", 1)[-1].upper() == port_hex:
                return True
    return False


def read_status_check_active(now: float) -> bool:
    """A short press on the physical shutdown button (piratebox_button_
    daemon.py's on_released()) writes a plain Unix timestamp here - this
    is "active" for exactly as long as that timestamp is recent, no
    consume/acknowledge step needed (a repeated press naturally re-
    extends the window just by writing a newer timestamp - see that
    file's own comment). Missing file, unreadable, non-numeric content,
    or a nonsensical future timestamp (clock skew, a corrupt write) all
    degrade to "not active," never a crash and never a stuck-forever
    override - this daemon has no way to distinguish "malformed" from
    "absent" and doesn't need to; both mean the same thing here."""
    try:
        with open(STATUS_CHECK_REQUEST_FILE, "r") as f:
            ts = float(f.read().strip())
    except (OSError, ValueError):
        return False
    age = now - ts
    return 0.0 <= age < STATUS_CHECK_WINDOW_SECONDS


def read_preview_active(now: float) -> bool:
    """`piratebox-silly preview` (operator-only, see that script) writes
    a plain Unix timestamp here - identical recency-based pattern to
    read_status_check_active() above (same fail-safe degradation:
    missing/malformed/future-timestamped all mean "not active"). No
    daily cap, no cooldown - this is a deliberately simple, always-
    available developer/operator tool, not a rarity-gated Silly
    behavior; see PREVIEW_PLAYLIST below for why it can never show
    secret/rare content regardless of how often it's run."""
    try:
        with open(PREVIEW_REQUEST_FILE, "r") as f:
            ts = float(f.read().strip())
    except (OSError, ValueError):
        return False
    age = now - ts
    return 0.0 <= age < PREVIEW_WINDOW_SECONDS


def read_glance_preview_active(now: float) -> bool:
    """`piratebox-silly glance-preview` (operator-only, see that
    script) - identical recency-based pattern to read_preview_active()
    just above, its own independent request file (see GLANCE_PREVIEW_
    REQUEST_FILE's own comment for why). Distance/Glance Display
    (2026-09-04)."""
    try:
        with open(GLANCE_PREVIEW_REQUEST_FILE, "r") as f:
            ts = float(f.read().strip())
    except (OSError, ValueError):
        return False
    age = now - ts
    return 0.0 <= age < GLANCE_PREVIEW_WINDOW_SECONDS


# A fixed, hand-picked, deterministic sampler of ordinary/common Silly
# Mode content for `piratebox-silly preview` (see read_preview_active()
# above) - built ENTIRELY from plain render-spec dicts, never by
# calling piratebox_progression.roll_event(), so it is structurally
# impossible for a preview to surface an uncommon/rare/legendary/secret
# variant, no matter how many times an operator runs it or what the
# device's real level/history/personality happens to be. This is the
# "representative selection of the non-secret/common visual
# improvements" the feature's own physical-validation step asked for -
# deliberately not exhaustive (it doesn't enumerate the full EXPRESSIONS/
# ANIMATIONS/SCENES tables), just enough of a sampler to judge whether
# faces stay readable, timing feels right, and the personality/
# information balance still feels right.
PREVIEW_PLAYLIST = [
    {"expression": "idle"},
    {"expression": "happy"},
    {"expression": "excited"},
    {"expression": "curious"},
    {"expression": "confused"},
    {"expression": "content"},
    {"anim": "quick_blink_pair"},
    {"anim": "look_around_curious"},
    {"expression": "pirate_flourish", "quip": "Preview mode, matey."},
]
PREVIEW_SECONDS_PER_ITEM = 5.0   # long enough to actually look at each one


def read_silly_toggle_edge(markers: dict) -> bool:
    """A double tap on the physical button touches SILLY_TOGGLE_
    REQUEST_FILE purely as a cosmetic cue - this returns True exactly
    once per fresh write (edge-detected via mtime, the same pattern
    Progression's own reset/import request checks use), never based on
    the file's content (it's a bare timestamp - the actual new Silly
    Mode state is read fresh from SILLY_FILE by the caller, never
    duplicated here). `markers` is a small dict the caller keeps across
    ticks, never persisted - a toggle confirmation is a one-shot
    cosmetic cue, not history worth remembering (Progression's own
    Captain's Log is a different, deliberate mechanism for anything
    that IS worth remembering)."""
    try:
        mtime = os.path.getmtime(SILLY_TOGGLE_REQUEST_FILE)
    except OSError:
        return False
    if mtime <= markers.get("silly_toggle_mtime", 0.0):
        return False
    markers["silly_toggle_mtime"] = mtime
    return True


def read_ssid() -> str:
    try:
        with open(HOSTAPD_CONF, "r") as f:
            for line in f:
                m = re.match(r"^\s*ssid\s*=\s*(.+?)\s*$", line)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return "PirateBox"


def read_uptime_seconds() -> float:
    try:
        with open("/proc/uptime", "r") as f:
            return float(f.read().split()[0])
    except (OSError, ValueError, IndexError):
        return 0.0


def read_disk_free_total():
    """Bytes (free, total) for the root filesystem - same facts the
    admin page's own storage figure is built from, read directly rather
    than through PHP."""
    try:
        st = os.statvfs("/")
        free = st.f_bavail * st.f_frsize
        total = st.f_blocks * st.f_frsize
        return free, total
    except OSError:
        return 0, 0


def read_cpu_temp_c():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return int(f.read().strip()) / 1000.0
    except (OSError, ValueError):
        return None


def read_meminfo_kb():
    """(total_kb, available_kb) for RAM - same two `/proc/meminfo`
    fields (and the same plain-file-read approach, no subprocess) the
    admin page's own `piratebox_get_meminfo_kb()` already uses
    (includes/metrics.php) - read directly here rather than through
    PHP, matching read_disk_free_total()'s own precedent just above.
    Distance/Glance Display (2026-09-04)."""
    try:
        with open("/proc/meminfo", "r") as f:
            raw = f.read()
    except OSError:
        return None, None
    total = available = None
    for line in raw.splitlines():
        if line.startswith("MemTotal:"):
            total = int(line.split()[1])
        elif line.startswith("MemAvailable:"):
            available = int(line.split()[1])
    return total, available


def read_cpu_jiffies():
    """(total_jiffies, idle_jiffies) from the first line of `/proc/
    stat` - a single cheap file read, no subprocess. A single sample is
    meaningless on its own; CPU utilization needs a DELTA between two
    samples taken some time apart - see compute_cpu_percent() just
    below, which takes two of these tuples. Distance/Glance Display
    (2026-09-04)."""
    try:
        with open("/proc/stat", "r") as f:
            fields = f.readline().split()[1:]
        values = [int(x) for x in fields]
        idle = values[3] + (values[4] if len(values) > 4 else 0)  # idle + iowait
        return sum(values), idle
    except (OSError, ValueError, IndexError):
        return None


def compute_cpu_percent(prev, curr):
    """Pure - no I/O, unlike read_cpu_jiffies() above. Kept in this
    file (not piratebox_glance.py) deliberately: it's a transform
    specific to /proc/stat's own jiffie-counter format, the same reason
    read_cpu_jiffies() itself lives here - piratebox_glance.py never
    needs to know what a "jiffy" is, it only ever sees the resulting
    plain percentage in the metrics dict. Returns None if either sample
    is missing/unreadable, or if no time has actually elapsed between
    them (a zero-length interval can't produce a rate) - both degrade
    to "unavailable," never a crash or a nonsensical value."""
    if prev is None or curr is None:
        return None
    prev_total, prev_idle = prev
    curr_total, curr_idle = curr
    total_delta = curr_total - prev_total
    idle_delta = curr_idle - prev_idle
    if total_delta <= 0:
        return None
    return max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta)))


def format_bytes_gb(n: int) -> str:
    return f"{n / (1024 ** 3):.0f}G"


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours:02d}h"
    if hours > 0:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def build_glance_metrics(status, stale: bool, prev_cpu_jiffies, clients_recently_changed: bool, bh1750_module=None):
    """Assembles the one-shot `metrics` dict piratebox_glance.py's
    scheduler/renderers consume (see that module's own documented
    contract) - the ONE place in this daemon where raw reads (several
    already used by render_health() above, plus the two new ones added
    for this feature) get combined into that shape. Called once per
    glance-phase-ENTRY, not every tick - see main()'s own comment - a
    glance page holds the SAME metrics for its whole ~8-10s slot,
    exactly like every other held render in this daemon already does,
    so this does at most one read of each source per slot, not per
    tick. Returns (metrics, new_cpu_jiffies) - the caller threads
    new_cpu_jiffies back in as next time's prev_cpu_jiffies, the same
    explicit-state-threading pattern main() already uses for
    silly_hold_render/silly_last_clients/etc. `clients_recently_
    changed` is passed in rather than computed here because main()
    already has it for free (the existing client-count "pulse" used by
    render_status()'s own inverted-box cue) - reused, not duplicated.

    `bh1750_module` (2026-09-07, ambient light glance page; ESP32-owned
    since the same-day migration): the SAME already-imported module
    reference (`piratebox_esp32_bh1750`) main() already keeps for the
    HARDWARE_SIGNALS registration - passed in, never imported again
    here. Deliberately calls ONLY get_diagnostics() (a read of that
    module's own already-cached state), never read_ambient_lux()
    directly - this must never be a second, parallel trigger of a real
    I2C/serial transaction alongside the one HARDWARE_SIGNALS's own
    registered reader already causes; rate limiting now lives on the
    ESP32 firmware's own sensor-publish cadence (piratebox_esp32_
    supervisor.py's cached export) and is completely unaffected by how
    many times get_diagnostics() itself
    is called. Defaults to None (matching every existing caller in
    tools/test_silly_mode.py, which predates this parameter) so this
    stays fully backward compatible - omitting it simply means
    ambient_lux is always None, the same honest "not available" value
    a Pi with no BH1750 wired would produce anyway."""
    curr_cpu_jiffies = read_cpu_jiffies()
    cpu_percent = compute_cpu_percent(prev_cpu_jiffies, curr_cpu_jiffies)

    total_kb, available_kb = read_meminfo_kb()
    ram_percent = None
    if total_kb and available_kb is not None and total_kb > 0:
        ram_percent = max(0.0, min(100.0, 100.0 * (1.0 - available_kb / total_kb)))

    free, total = read_disk_free_total()
    disk_percent = (1.0 - free / total) * 100.0 if total > 0 else None

    clients = None
    undervoltage_now = False
    time_confident = False
    if not stale and isinstance(status, dict):
        wc = status.get("wifi_clients")
        if isinstance(wc, int):
            clients = wc
        undervoltage_now = status.get("power", {}).get("undervoltage_now") is True
        ts = status.get("time_source", {})
        # Deliberately conservative: only claim confidence when NTP is
        # actually synced or a real RTC is detected - matching the
        # instruction "if time confidence permits." A device that has
        # neither still shows every other glance page; it just never
        # shows a large clock it can't vouch for.
        time_confident = bool(ts.get("ntp_synchronized")) or bool(ts.get("rtc_detected"))

    # Same "None means don't claim it" discipline as time_confident
    # above: only a genuinely current reading (actually detected, not
    # gone stale, a real number) becomes a value here - a never-wired
    # sensor, a temporarily unresponsive one, or a stale last-known
    # value all honestly degrade to None, never a fabricated 0.
    ambient_lux = None
    if bh1750_module is not None:
        try:
            diag = bh1750_module.get_diagnostics()
            if diag.get("detected") and not diag.get("stale") and isinstance(diag.get("lux"), (int, float)):
                ambient_lux = float(diag["lux"])
        except Exception:  # noqa: BLE001 - a broken diagnostics call must
            ambient_lux = None  # never break this glance-phase-entry

    metrics = {
        "cpu_percent": cpu_percent,
        "cpu_temp_c": read_cpu_temp_c(),
        "ram_percent": ram_percent,
        "disk_percent": disk_percent,
        "clients": clients,
        "clients_recently_changed": clients_recently_changed,
        "uptime_str": format_duration(read_uptime_seconds()),
        "time_str": time.strftime("%H:%M") if time_confident else None,
        "undervoltage_now": undervoltage_now,
        "ambient_lux": ambient_lux,
    }
    return metrics, curr_cpu_jiffies


# --- Tiny procedural icons + instrument-panel chrome (round 8) --------
# All plain Pillow primitives (ellipse/line/polygon/rectangle/arc) at
# ~10x10px - no image asset, no icon font, nothing beyond what
# draw_skull_and_crossbones already established as this project's
# pattern for "small bitmap, drawn, not loaded."

def icon_status(draw, x: int, y: int, color: str) -> None:
    """Small diamond-with-center-dot - a generic "device/at a glance"
    glyph for the Status page header."""
    draw.polygon([(x + 5, y), (x + 10, y + 5), (x + 5, y + 10), (x, y + 5)], outline=color)
    draw.ellipse((x + 4, y + 4, x + 6, y + 6), fill=color)


def icon_clock(draw, x: int, y: int, color: str) -> None:
    draw.ellipse((x, y, x + 10, y + 10), outline=color)
    cx, cy = x + 5, y + 5
    draw.line((cx, cy, cx, y + 1), fill=color)
    draw.line((cx, cy, x + 8, cy + 2), fill=color)


def icon_network(draw, x: int, y: int, color: str) -> None:
    """Small antenna/mast glyph for the Network page header."""
    draw.line((x + 4, y + 2, x + 4, y + 10), fill=color)
    draw.line((x, y + 10, x + 8, y + 10), fill=color)
    draw.arc((x - 2, y - 3, x + 10, y + 5), start=200, end=340, fill=color)


def icon_health(draw, x: int, y: int, color: str) -> None:
    """Small heartbeat/EKG zigzag for the Health page header."""
    draw.line(
        [(x, y + 6), (x + 2, y + 6), (x + 4, y), (x + 6, y + 10), (x + 8, y + 6), (x + 10, y + 6)],
        fill=color,
    )


def icon_wifi_bars(draw, x: int, y: int, active: bool) -> None:
    """Three ascending bars - filled when the AP has at least one
    associated client right now, outline (present but idle) when it
    doesn't. Binary rather than tiered by exact count: at this size a
    3-level indicator reads as noise, "someone's connected or not"
    is the one fact worth a glance."""
    for i, h in enumerate((3, 6, 9)):
        bx = x + i * 4
        top = y + (9 - h)
        if active:
            draw.rectangle((bx, top, bx + 2, y + 9), fill="white")
        else:
            draw.rectangle((bx, top, bx + 2, y + 9), outline="white")


def draw_bar(draw, x: int, y: int, w: int, h: int, frac: float) -> None:
    """A compact horizontal progress/level bar - outline box, filled
    left-to-right by frac (0..1, clamped)."""
    frac = max(0.0, min(1.0, frac))
    draw.rectangle((x, y, x + w, y + h), outline="white")
    fill_w = int((w - 2) * frac)
    if fill_w > 0:
        draw.rectangle((x + 1, y + 1, x + 1 + fill_w, y + h - 1), fill="white")


def header_bar(draw, title: str, font_small, icon_fn, alive_on: bool) -> None:
    """The shared instrument-panel title bar every serious page now
    opens with: inverted (white bar, black text/icon) for a clear
    visual break between "page identity" and "page content" below it,
    a small procedural icon, and a heartbeat dot in the top-right that
    flips every redraw tick - the "is this actually alive" indicator,
    always in the same place regardless of which page is showing."""
    draw.rectangle((0, 0, 127, 11), fill="white")
    icon_fn(draw, 2, 0, "black")
    draw.text((14, 0), title, font=font_small, fill="black")
    if alive_on:
        draw.ellipse((120, 3, 125, 8), fill="black")
    else:
        draw.ellipse((120, 3, 125, 8), outline="black")


# --- Page renderers -----------------------------------------------------
# Each function draws exactly one page into the given ImageDraw context.
# None of these touch the network, sudo, or any writable PirateBox state
# - pure read-and-render.

def render_status(draw, font, font_small, mode: str, status, stale: bool, alive_on: bool, pulse: bool) -> None:
    header_bar(draw, "PIRATEBOX", font_small, icon_status, alive_on)
    mode_label = "EMERGENCY" if mode == "emergency" else "NORMAL"
    draw.text((0, 15), f"Mode: {mode_label}", font=font, fill="white")
    draw.text((0, 27), f"SSID: {read_ssid()}", font=font, fill="white")
    has_clients = not stale and isinstance(status, dict) and (status.get("wifi_clients") or 0) > 0
    icon_wifi_bars(draw, 0, 40, has_clients)
    label = "Clients: unknown" if (stale or status is None) else f"Clients: {status.get('wifi_clients', '?')}"
    if pulse:
        # Brief inverted "pulse" the couple of redraws right after the
        # client count increases - plain operational information, NOT
        # personality-gated (unlike the separate, gated "celebration"
        # page), so it still fires in Emergency Mode or a degraded
        # state. textbbox-measured so the box fits any digit count.
        bbox = draw.textbbox((16, 40), label, font=font)
        draw.rectangle((bbox[0] - 2, bbox[1] - 1, bbox[2] + 2, bbox[3] + 1), fill="white")
        draw.text((16, 40), label, font=font, fill="black")
    else:
        draw.text((16, 40), label, font=font, fill="white")


def render_time(draw, font, font_small, status, stale: bool, alive_on: bool) -> None:
    header_bar(draw, "TIME", font_small, icon_clock, alive_on)
    now = time.localtime()
    utc = time.gmtime()
    draw.text((0, 14), f"Local {time.strftime('%I:%M:%S %p', now)}", font=font, fill="white")
    draw.text((0, 26), f"UTC   {time.strftime('%H:%M:%S', utc)}", font=font, fill="white")
    draw.text((0, 38), f"Date  {time.strftime('%Y-%m-%d', now)}", font=font, fill="white")
    ts = (status or {}).get("time_source") if not stale and status else None
    if ts is None:
        draw.text((0, 51), "Source: unknown", font=font_small, fill="white")
    else:
        rtc = "RTC" if ts.get("rtc_detected") else "no-RTC"
        ntp = "NTP-synced" if ts.get("ntp_synchronized") else "not synced"
        draw.text((0, 51), f"{rtc}, {ntp}", font=font_small, fill="white")


def render_network(draw, font, font_small, status, stale: bool, alive_on: bool) -> None:
    header_bar(draw, "NETWORK", font_small, icon_network, alive_on)
    draw.text((0, 14), f"SSID: {read_ssid()}", font=font, fill="white")
    draw.text((0, 26), f"IP:   {AP_IP_ADDRESS}", font=font, fill="white")
    if stale or status is None:
        draw.text((0, 40), "Services: unknown", font=font, fill="white")
        return
    services = status.get("services", {})
    # Small filled/hollow dot per service plus its (truncated) name,
    # laid out in a fixed-width row - a glance shows which ones, not
    # just how many, are up.
    dx = 1
    for name, ok in services.items():
        if ok is True:
            draw.ellipse((dx, 41, dx + 6, 47), fill="white")
        else:
            draw.ellipse((dx, 41, dx + 6, 47), outline="white")
        draw.text((dx + 9, 38), name[:4], font=font_small, fill="white")
        dx += 32


def render_health(draw, font, font_small, status, stale: bool, alive_on: bool) -> None:
    header_bar(draw, "HEALTH", font_small, icon_health, alive_on)
    draw.text((0, 14), f"Uptime: {format_duration(read_uptime_seconds())}", font=font, fill="white")
    draw.text((0, 26), "Storage:", font=font, fill="white")
    free, total = read_disk_free_total()
    used_frac = 1.0 - (free / total) if total > 0 else 0.0
    draw_bar(draw, 60, 27, 66, 8, used_frac)
    temp = read_cpu_temp_c()
    temp_str = f"{temp:.0f}C" if temp is not None else "unknown"
    emergency_s = read_emergency_runtime_seconds()
    draw.text((0, 38), f"CPU: {temp_str}  Emerg: {format_duration(emergency_s)}", font=font, fill="white")
    # Power warning - conditional, one line, only when there's something
    # to say. Deliberately does NOT claim the OLED caused or is affected
    # by this; it is purely reporting the same power.undervoltage_now
    # flag the Stats/About pages already surface. Boxed (round 8) for
    # higher visual salience than plain text - a warning should look
    # different from routine information, not just say so in words.
    if not stale and isinstance(status, dict):
        power = status.get("power", {})
        if power.get("undervoltage_now") is True:
            draw.rectangle((0, 50, 127, 62), outline="white")
            draw.text((3, 52), "! POWER: UNDERVOLTAGE", font=font_small, fill="white")


def render_mode_transition(draw, font_big, new_mode: str) -> None:
    """A brief, full-screen, inverted banner shown exactly once at the
    moment this daemon observes the mode actually change - NOT
    personality-gated (mode is serious operational information, so this
    shows in Emergency Mode and under a degraded condition too, unlike
    the gated "celebration"/"personality" frames)."""
    draw.rectangle((0, 0, 127, 63), fill="white")
    label = "EMERGENCY MODE" if new_mode == "emergency" else "NORMAL MODE"
    sub = "ACTIVATED" if new_mode == "emergency" else "RESTORED"
    draw.text((6, 16), label, font=font_big, fill="black")
    draw.text((6, 36), sub, font=font_big, fill="black")


def render_status_check_banner(draw, font_big) -> None:
    """A brief, one-shot, full-frame banner shown exactly once, the
    tick a short-press status-check request is first noticed - not on
    every tick it stays active (see main()'s own edge-detection). This
    is the one visual acknowledgment reserved for the deliberate, on-
    demand button press specifically - the same phase change happening
    automatically as part of the ordinary personality/status cadence
    (see SILLY_CADENCE_* above) does NOT get this banner, so it doesn't
    become repetitive noise every 30-45 seconds forever."""
    draw.rectangle((0, 0, 127, 63), fill="white")
    draw.text((6, 24), "STATUS CHECK", font=font_big, fill="black")


def render_silly_toggle_banner(draw, font, font_big, new_state: bool) -> None:
    """A brief, one-shot confirmation shown exactly once, the tick a
    double tap is first noticed (see main()'s own edge-detection via
    read_silly_toggle_edge()) - never based on this function's own
    guess at state; the caller reads the real current value from
    SILLY_FILE and passes it in. Reuses the existing skull-and-
    crossbones flourish icon (draw_skull_and_crossbones) for a little
    charm rather than a plain text-only banner, per instruction -
    still just the one existing drawing primitive, no new asset."""
    draw.rectangle((0, 0, 127, 63), fill="white")
    draw_skull_and_crossbones(draw, 4, 18, color="black", bg="white")
    draw.text((44, 16), "SILLY MODE", font=font, fill="black")
    draw.text((44, 34), "ON" if new_state else "OFF", font=font_big, fill="black")


def compute_display_tier(mode: str, status, stale: bool) -> str:
    """The mandatory priority gate: Emergency > required operational
    warning > Silly Mode > normal cosmetic personality (see the "SILLY
    MODE" header note for the full rationale). Returns exactly one of
    "emergency" / "fault" / "warning" / "ok". Checked fresh every tick,
    never cached, so a condition that appears while Silly Mode is
    showing takes effect on the very next redraw - the same discipline
    the old personality_allowed() already used, now with an explicit,
    named middle tier instead of one all-or-nothing boolean.

    "emergency" and "fault" both mean Silly Mode must not run at all
    this tick (checked identically by callers) - kept as two distinct
    names rather than collapsing them because they're diagnostically
    different (a real Emergency Mode toggle vs. a data/service
    problem), even though today's display behavior for both is the
    same fall-through to the serious rotation."""
    if mode == "emergency":
        return "emergency"
    if stale or not isinstance(status, dict):
        return "fault"
    services = status.get("services", {})
    if any(v is not True for v in services.values()):
        return "fault"
    if status.get("power", {}).get("undervoltage_now") is True:
        return "warning"
    return "ok"


def compute_silly_expression(tick: int, has_clients: bool, ssh_active: bool, forced: str = None) -> str:
    """Pure, deterministic "what face shows this tick" function - the
    only inputs are already-computed booleans/counters, no I/O, so this
    is directly unit-testable without a display or real status data.
    `forced` (an event-driven one-shot: excited/surprised/confused/
    waking/sleeping, decided by main()'s own stateful bookkeeping)
    always wins when set. Otherwise: the occasional pirate-flourish beat
    wins next (rarest), then the SSH-watch beat (only when someone's
    actually connected), then plain ambient cycling keyed off whether
    anyone's associated right now."""
    if forced is not None:
        return forced
    if tick % SILLY_FLOURISH_EVERY_TICKS == 0:
        return "pirate_flourish"
    if ssh_active and tick % SILLY_SSH_WATCH_EVERY_TICKS == 0:
        return "ssh_watch"
    cycle = AMBIENT_WITH_CLIENTS if has_clients else AMBIENT_NO_CLIENTS
    return cycle[tick % len(cycle)]


_SILLY_CADENCE_ORDER = ("personality", "glance", "status")
_SILLY_CADENCE_DURATIONS = {
    "personality": SILLY_CADENCE_PERSONALITY_SECONDS,
    "glance": SILLY_CADENCE_GLANCE_SECONDS,
    "status": SILLY_CADENCE_STATUS_SECONDS,
}


def advance_silly_cadence(phase: str, seconds_remaining: float, refresh_seconds: float):
    """Pure state-machine step for the personality-vs-glance-vs-status
    cadence (see the "PERSONALITY-VS-STATUS CADENCE" header note) -
    decrements the phase clock by one tick's worth of real time and
    advances to the NEXT phase in `_SILLY_CADENCE_ORDER` exactly when
    it elapses, resetting to that phase's own duration. Extended
    2026-09-04 (Distance/Glance Display) from a 2-phase toggle
    (personality<->status) to this 3-phase rotation - existing callers
    are unaffected (same signature, same return shape), but the actual
    SEQUENCE changed: a phase now always advances to the next entry in
    `_SILLY_CADENCE_ORDER`, wrapping around, rather than simply
    flipping between two names. No I/O, no reference to `main()`'s
    other state - directly unit-testable by calling it in a loop and
    asserting the resulting phase sequence/timing. Callers are
    responsible for only calling this once per tick, and only while
    this cadence is actually driving the display (see main()'s own
    "pauses rather than drifts" comment)."""
    seconds_remaining -= refresh_seconds
    if seconds_remaining <= 0:
        idx = _SILLY_CADENCE_ORDER.index(phase)
        phase = _SILLY_CADENCE_ORDER[(idx + 1) % len(_SILLY_CADENCE_ORDER)]
        seconds_remaining = _SILLY_CADENCE_DURATIONS[phase]
    return phase, seconds_remaining


_OFFLINE_GLANCE_ORDER = ("rotation", "glance")
_OFFLINE_GLANCE_DURATIONS = {
    "rotation": OFFLINE_GLANCE_ROTATION_SECONDS,
    "glance": OFFLINE_GLANCE_SECONDS,
}


def advance_offline_glance_cadence(phase: str, seconds_remaining: float, refresh_seconds: float):
    """The Silly-Mode-OFF counterpart to advance_silly_cadence() above -
    a separate, simpler two-phase cycle (plain serious rotation
    <-> one glance page) rather than reusing the 3-phase Silly cadence
    with "personality" simply skipped: the Silly-on cadence also has to
    respect sleep/one-shot-hold/pending-reveal interruptions that don't
    exist at all when Silly is off, so forcing one mechanism to serve
    both contexts would mean either a false shared dependency or extra
    conditionals here just to ignore state that's irrelevant in this
    context - a second small, independently-testable pure function was
    the cleaner choice. Same shape/contract as advance_silly_cadence()
    otherwise: pure, decrements by one tick's worth of real time,
    advances to the next phase and resets its duration when the clock
    elapses. Callers only advance this while Silly Mode is actually
    off AND no higher-priority override (Emergency/fault/mode-
    transition/status-check/preview) is active - see main()'s own
    `not silly_enabled` branch."""
    seconds_remaining -= refresh_seconds
    if seconds_remaining <= 0:
        idx = _OFFLINE_GLANCE_ORDER.index(phase)
        phase = _OFFLINE_GLANCE_ORDER[(idx + 1) % len(_OFFLINE_GLANCE_ORDER)]
        seconds_remaining = _OFFLINE_GLANCE_DURATIONS[phase]
    return phase, seconds_remaining


# --- Silly Mode face rendering ------------------------------------------
# The actual drawing primitives and data tables (EXPRESSIONS, ANIMATIONS,
# SCENES, draw_face/draw_scene/draw_zzz/draw_pirate_flourish/draw_skull_
# and_crossbones, plus the personality-mannerism bias_ambient_expression())
# moved out to piratebox_expressions.py in the "Expression Engine v2"
# round (2026-09-04) - imported at the top of this file, see that
# module's own header for the full rationale ("do not let this file
# become an enormous pile of expression-specific conditionals"). This
# daemon now only ever decides WHEN to show something (main()'s
# priority chain, unchanged in shape) and hands off a render-spec dict
# to render_silly() below, which is now a thin dispatcher over
# piratebox_expressions's own functions - it no longer contains any
# per-expression drawing logic itself. Every imported name (EXPRESSIONS,
# draw_skull_and_crossbones, etc.) stays reachable as `piratebox_oled_
# daemon.<name>` exactly as before, so no existing test needed to
# change for this move alone.


def render_silly(draw, font, font_small, render: dict, tier: str, alive_on: bool) -> None:
    """Renders exactly one Silly Mode frame from a render-spec dict:
    `{"expression": <EXPRESSIONS key>}` for a face (optionally
    overriding its default decoration or adding a quip line), or
    `{"scene": <name>}` for a legendary/secret set-piece (see
    draw_scene()). `tier` is "ok" or "warning" only (callers never reach
    this with "emergency"/"fault" - see compute_display_tier()) -
    "warning" draws the small persistent badge unconditionally,
    regardless of what else is showing, per the mandatory priority
    design (the warning must stay unmistakable, not just possible to
    stumble across)."""
    expression = render.get("expression")
    scene = render.get("scene")
    quip = render.get("quip")

    if expression == "pirate_flourish":
        draw_pirate_flourish(draw, font, font_small, quip or "")
    elif scene is not None:
        draw_scene(draw, font, font_small, scene)
        if quip:
            draw.text((0, 54), quip, font=font_small, fill="white")
    elif expression is not None:
        eyes, brows, mouth, default_decoration = EXPRESSIONS[expression]
        draw_face(draw, eyes, brows, mouth, render.get("decoration", default_decoration))
        if expression == "sleeping":
            draw_zzz(draw, font_small, 0 if alive_on else 1)
        if quip:
            draw.text((0, 54), quip, font=font_small, fill="white")

    # Small always-on heartbeat dot, top-right - same "proof the loop is
    # alive" convention every serious page's header_bar already uses.
    if alive_on:
        draw.ellipse((120, 2, 125, 7), fill="white")
    else:
        draw.ellipse((120, 2, 125, 7), outline="white")

    # The mandatory persistent warning badge - drawn last so nothing
    # else can ever cover it, small and fixed in the top-left corner,
    # every single Silly frame, whenever tier == "warning".
    if tier == "warning":
        draw.rectangle((1, 1, 11, 11), outline="white")
        draw.text((4, 1), "!", font=font_small, fill="white")


def render_level_up(draw, font, font_small, font_big, level: int, title: str) -> None:
    """A brief, one-shot, full-frame celebration - not personality-
    gated any differently than the rest of Silly Mode (callers only
    reach this from the same ok/warning-tier, Silly-enabled branch), but
    visually distinct (inverted, like the existing mode-transition
    banner) since a level-up is a bigger deal than an ambient face. The
    title is drawn at font_small (verified by tools/test_progression.py
    to fit every real title) - level-up is rare enough that legibility
    matters more than a bigger font here."""
    draw.rectangle((0, 0, 127, 63), fill="white")
    draw_skull_and_crossbones(draw, 4, 4)
    draw.text((40, 10), "LEVEL UP!", font=font_big, fill="black")
    draw.text((40, 30), f"Level {level}", font=font, fill="black")
    draw.text((0, 48), title, font=font_small, fill="black")


def render_achievement(draw, font, font_small, name: str) -> None:
    """A brief one-shot achievement banner - boxed, not inverted (kept
    visually distinct from the rarer/bigger level-up banner above). The
    name is drawn full-width at font_small so even the longest
    achievement title (verified by tools/test_progression.py) fits
    without clipping."""
    draw.rectangle((2, 2, 125, 61), outline="white")
    draw.text((8, 6), "ACHIEVEMENT", font=font_small, fill="white")
    draw_skull_and_crossbones(draw, 6, 18)
    draw.text((2, 48), name, font=font_small, fill="white")


PAGE_ORDER = ["status", "time", "network", "health"]


def build_frame(
    device, page: str, font, font_small, font_big, status, stale: bool, mode: str,
    alive_on: bool = True, pulse: bool = False, extra=None,
):
    """Renders exactly one page into a standalone PIL Image (device's
    own mode/size) and returns it, WITHOUT writing it to the display.
    Separated from actually displaying (see display_frame() below) so
    main() can hold onto the previous frame and the newly-built one at
    the same time - needed for the brief slide transition between
    pages, which needs both images to composite intermediate frames
    from. Building the image is pure/side-effect-free (safe to unit
    test, and safe to call even when device is only used for its
    .mode/.size, never actually written to)."""
    img = Image.new(device.mode, device.size)
    draw = ImageDraw.Draw(img)
    if page == "status":
        render_status(draw, font, font_small, mode, status, stale, alive_on, pulse)
    elif page == "time":
        render_time(draw, font, font_small, status, stale, alive_on)
    elif page == "network":
        render_network(draw, font, font_small, status, stale, alive_on)
    elif page == "health":
        render_health(draw, font, font_small, status, stale, alive_on)
    elif page == "silly":
        render_silly(draw, font, font_small, extra["render"], extra["tier"], alive_on)
    elif page == "level_up":
        render_level_up(draw, font, font_small, font_big, extra["level"], extra["title"])
    elif page == "achievement":
        render_achievement(draw, font, font_small, extra["name"])
    elif page == "mode_transition":
        render_mode_transition(draw, font_big, extra["new_mode"])
    elif page == "status_check_banner":
        render_status_check_banner(draw, font_big)
    elif page == "silly_toggle_banner":
        render_silly_toggle_banner(draw, font, font_big, extra["new_state"])
    elif page == "glance":
        render_glance_page(
            draw, extra["label_fonts"], extra["font_cpu_label"],
            extra["font_medium"], extra["font_big"],
            extra["page_id"], extra["metrics"],
        )
    return img


def display_frame(device, new_img, old_img=None, transition: bool = False) -> None:
    """Writes new_img to the real display. If transition is True and a
    previous frame (old_img) exists, plays a brief (~150ms, four extra
    device.display() writes) horizontal wipe first - the only recurring
    motion this daemon has, reserved for an actual page change in the
    normal rotation (see main()'s own transition_wipe flag). Every
    other call path (one-shot frames, same-page refreshes, the very
    first frame after startup/reconnect) just writes new_img directly,
    identical to how this daemon always displayed a frame before round
    8's transition was added."""
    if transition and old_img is not None:
        w, h = device.size
        steps = 4
        for i in range(1, steps + 1):
            offset = int(w * i / steps)
            frame = Image.new(device.mode, (w, h))
            frame.paste(old_img.crop((offset, 0, w, h)), (0, 0))
            frame.paste(new_img.crop((0, 0, offset, h)), (w - offset, 0))
            device.display(frame)
            time.sleep(0.04)
    device.display(new_img)


def play_animation_burst(device, anim_id: str, tier: str, quip, font, font_small, font_big, mode: str):
    """Multi-frame animation, Expression Engine v2 (2026-09-04). Flashes
    a short (well under 1 second - each ANIMATIONS entry's own
    frame_gap_s times its own frame count, see piratebox_expressions.py)
    sequence of already-resolved single-frame Silly renders directly to
    the display, bypassing the normal 3s-per-tick redraw pacing - the
    SAME technique display_frame()'s own transition wipe already uses
    (a handful of extra device.display() calls with a short time.sleep()
    between), just repurposed for a snappy reaction instead of a page-
    to-page wipe, and reusing ONE proven pattern rather than inventing a
    second animation mechanism. This is a deliberately conservative way
    to get real sub-3s animation without changing this daemon's overall
    REFRESH_SECONDS or turning main() into a high-frequency redraw loop
    (see piratebox_expressions.py's own ANIMATIONS docstring) - only
    ever called from the ok/warning-tier, Silly-Mode-on branch of
    main()'s priority chain, which Emergency/fault/mode-transition
    already always pre-empt, so a burst can never delay a serious page.

    Returns (final_render_dict, hold_ticks) so the caller can fold the
    animation's own settle frame into the exact same hold/countdown
    bookkeeping (`silly_hold_render`/`silly_hold_remaining`) a plain,
    non-animated one-shot reaction already used before this round -
    callers never need their own separate "an animation is playing"
    state. Returns (None, None) for an unknown anim id (fail-safe,
    matching every other unknown-key lookup in this daemon) - the
    caller falls back to its own default render in that case."""
    frame_specs, frame_gap_s, hold_ticks = resolve_animation_frames(anim_id, tier, quip=quip)
    if frame_specs is None:
        return None, None
    for spec in frame_specs:
        try:
            img = build_frame(device, "silly", font, font_small, font_big, None, False, mode, extra=spec)
            device.display(img)
        except Exception:
            # A real display failure mid-burst - let the caller's own
            # end-of-tick try/except (which still runs right after this
            # returns) discover and handle "lost contact with the OLED"
            # exactly as it always does; this just stops flashing more
            # frames into a display that's no longer responding.
            break
        time.sleep(frame_gap_s)
    return frame_specs[-1]["render"], hold_ticks


def load_fonts():
    """Three sizes of the same face - not a new dependency, just three
    ImageFont objects from the font already used everywhere. 11pt for
    normal body text (unchanged from before round 8), 9pt for one-line
    secondary detail (the time-source line, service-name labels), 14pt
    for the rare, brief mode-transition banner where bigger is the
    point. All three fail together to PIL's built-in bitmap font if the
    TTF is missing, so a missing font file degrades the display, it
    never crashes the daemon."""
    try:
        return (
            ImageFont.truetype(FONT_PATH, 11),
            ImageFont.truetype(FONT_PATH, 9),
            ImageFont.truetype(FONT_PATH, 14),
        )
    except OSError:
        log.warning("Could not load %s, falling back to PIL default bitmap font.", FONT_PATH)
        default = ImageFont.load_default()
        return default, default, default


def load_glance_fonts():
    """Fonts for the Distance/Glance Display (2026-09-04) - kept as a
    SEPARATE function rather than widening load_fonts()'s own return
    tuple, since that tuple's exact 3-item shape (`font, font_small,
    font_big = load_fonts()`) is already unpacked positionally in a
    couple dozen places across this file and every test that loads it
    - changing its arity would be a needless, wide-blast-radius risk
    for what is really an unrelated, additive need.

    Returns (label_fonts, font_cpu_label, font_medium, font_big):
      - `label_fonts`: a 3-tuple of pre-loaded sizes matching
        piratebox_glance.LABEL_FONT_SIZES (biggest first) - that
        module picks the largest of these that actually fits a given
        label's measured width (see its own _fit_label_font()), fixing
        a real physical-validation finding (2026-09-04): the original
        single small (9pt) label size was unreadable at the same
        distance the big numeric value below it read fine at.
      - `font_cpu_label`: the CPU page's own dedicated, smaller label
        size - that page stacks two values instead of one, so it has
        less vertical room than the single-value pages label_fonts
        serves; see piratebox_glance.py's own render_glance_page() note.
      - `font_medium` (22pt): a page with two stacked values (CPU's
        percent-and-temperature) or a longer single value (uptime).
      - `font_big` (32pt): a page with exactly one short value, filling
        as much of the 128x64 canvas as legibly possible.
    Value sizes/positions are UNCHANGED from before the label-size fix,
    per instruction to leave already-validated numeric readability
    alone - only the label side of load_glance_fonts() grew. Same
    fail-safe fallback as load_fonts() - a missing TTF degrades to
    PIL's bitmap default for every size, never a crash."""
    try:
        label_fonts = tuple(ImageFont.truetype(FONT_PATH, size) for size in LABEL_FONT_SIZES)
        return (
            label_fonts,
            ImageFont.truetype(FONT_PATH, 20),
            ImageFont.truetype(FONT_PATH, 22),
            ImageFont.truetype(FONT_PATH, 32),
        )
    except OSError:
        log.warning("Could not load %s for glance fonts, falling back to PIL default bitmap font.", FONT_PATH)
        default = ImageFont.load_default()
        return (default, default, default), default, default, default


def init_device():
    """One attempt to bring up the display. Returns the device on
    success, None on any failure - callers loop on this, they never
    treat a None here as fatal."""
    try:
        serial = i2c(port=I2C_PORT, address=I2C_ADDRESS)
        return ssd1306(serial, width=128, height=64)
    except Exception as exc:
        log.warning("OLED not available (%s) - will keep retrying every %.0fs.", exc, RETRY_SECONDS)
        return None


def main() -> int:
    stop = False

    def handle_term(signum, frame):
        nonlocal stop
        log.info("Stopping (signal %d).", signum)
        stop = True

    signal.signal(signal.SIGTERM, handle_term)
    signal.signal(signal.SIGINT, handle_term)

    font, font_small, font_big = load_fonts()
    log.info(
        "Started. I2C bus %d address 0x%02X, %.0fs refresh, %.0fs/page "
        "(auto-rotating - no cycle button wired yet), %d-page cycle. "
        "Silly Mode: user-toggled via %s, off by default, always "
        "suppressed in Emergency Mode or any fault (missing/stale "
        "status, any Core service down) - see compute_display_tier(). "
        "Cadence: ~%.0fs personality / ~%.0fs glance / ~%.0fs status "
        "interlude (Silly on); ~%.0fs rotation / ~%.0fs glance (Silly off). "
        "Short-press status-check override: %s, ~%.0fs window. "
        "%d glance page(s) registered.",
        I2C_PORT, I2C_ADDRESS, REFRESH_SECONDS, PAGE_SECONDS, len(PAGE_ORDER),
        SILLY_FILE, SILLY_CADENCE_PERSONALITY_SECONDS, SILLY_CADENCE_GLANCE_SECONDS,
        SILLY_CADENCE_STATUS_SECONDS, OFFLINE_GLANCE_ROTATION_SECONDS, OFFLINE_GLANCE_SECONDS,
        STATUS_CHECK_REQUEST_FILE, STATUS_CHECK_WINDOW_SECONDS, len(GLANCE_PAGES),
    )

    page_index = 0
    seconds_on_current_page = 0.0
    device = None
    last_image = None  # previous displayed frame, for the slide transition
    tick = 0            # increments every redraw; drives the heartbeat dot

    # Always-on, never Silly-gated - a client-count pulse and a mode-
    # change banner are both plain operational information, not
    # personality, so they must keep working under any tier.
    last_seen_clients_for_pulse = None
    pulse_ticks_remaining = 0
    last_mode_seen = None

    # Silly Mode bookkeeping - plain in-memory state, never written to
    # disk (see the header note above); resets on every restart. Idle/
    # sleep tracking is computed every tick regardless of Silly Mode's
    # own on/off toggle now, because Progression (below) needs it too -
    # "is the device idle" is a fact about the device, not about
    # whether its cosmetic display happens to be switched on.
    silly_last_clients = None    # previous tick's wifi_clients, for event detection
    silly_zero_since = None      # wall-clock time.time() clients last became 0
    silly_sleeping = False
    silly_hold_render = None     # a held one-shot render-spec (excited/surprised/
                                   # confused/waking), shown for a few ticks
    silly_hold_remaining = 0
    wake_count_today = 0
    wake_count_day = None

    # Personality-vs-status cadence (see SILLY_CADENCE_* above) - starts
    # in the personality phase so a freshly-enabled Silly Mode opens
    # with faces, not an immediate status interlude. The clock only
    # advances while this cadence is actually driving the display (see
    # its own decrement below), so it naturally pauses - not drifts -
    # during a sleep/event-hold/pending-reveal/status-check-override
    # interruption and picks up exactly where it left off after.
    silly_cadence_phase = "personality"
    silly_cadence_seconds_remaining = SILLY_CADENCE_PERSONALITY_SECONDS

    # Short-press "show me real stats" override - see
    # read_status_check_active()'s own docstring. Edge-detected (like
    # mode_transition above) so the STATUS CHECK banner shows exactly
    # once per press, not on every tick the window stays open.
    status_check_was_active = False

    # Double-tap Silly toggle confirmation - same edge-detected, "in-
    # memory last seen mtime" pattern Progression's own reset/import
    # request checks use (see read_silly_toggle_edge() and that
    # function's own docstring). No "was_active" companion flag is
    # needed here (unlike status_check_was_active above) because the
    # signal is a one-shot edge, not a held-open window - it is true for
    # exactly one tick no matter what.
    silly_toggle_markers = {}

    # Operator-only "preview common expressions" request (Expression
    # Engine v2, 2026-09-04) - same edge-detected-banner-once, then-
    # held-open-window shape as status_check_was_active above.
    preview_was_active = False
    preview_started_at = None
    preview_last_index = -1
    preview_current_render = None

    # Distance/Glance Display (2026-09-04). The existing `silly_
    # cadence_phase`/`silly_cadence_seconds_remaining` above now drive
    # a 3-phase cycle including "glance" (see SILLY_CADENCE_* above);
    # `offline_glance_phase` drives the separate, simpler Silly-OFF
    # cadence (see OFFLINE_GLANCE_* above).
    # `glance_page_id`/`glance_metrics`/`prev_cpu_jiffies`/`glance_
    # cooldowns` are SHARED between both contexts on purpose - only one
    # of the two cadences is ever actually advancing on a given tick
    # (Silly is either on or off), so there's no real "which one owns
    # this" conflict, and sharing means a page's cooldown/last-shown
    # bookkeeping stays continuous across a Silly Mode toggle rather
    # than silently resetting. Nothing here is persisted to disk -
    # display-scheduling trivia, not history worth remembering, same
    # discipline as every other in-memory Silly Mode bookkeeping var.
    offline_glance_phase = "rotation"
    offline_glance_seconds_remaining = OFFLINE_GLANCE_ROTATION_SECONDS
    # Separate edge-detection flags for the two cadences (even though
    # the page/metrics/cooldown state above is shared) - keeps a Silly
    # Mode toggle that happens to land mid-glance-phase from confusing
    # one context's "did I already pick a page for this slot" with the
    # other's, since silly_enabled being flipped can switch which
    # branch is even reached from one tick to the next.
    silly_glance_was_active = False
    offline_glance_was_active = False
    glance_page_id = None
    glance_metrics = None
    glance_cooldowns = {}
    prev_cpu_jiffies = None
    glance_rng = random.Random()

    # Operator-only "preview the ordinary glance pages" request - same
    # shape as the Silly preview state above, but its own independent
    # signal file/state, since it must work regardless of whether Silly
    # Mode is on or off (glance pages are not Silly content).
    glance_preview_was_active = False
    glance_preview_started_at = None
    glance_preview_last_index = -1

    glance_label_fonts, font_glance_cpu_label, font_glance_medium, font_glance_big = load_glance_fonts()

    # Progression (piratebox_progression.py) - a separate, persistent,
    # always-on subsystem underneath Silly Mode. Loaded once at startup;
    # see that module's own header for the full design. A load/import
    # failure here degrades to Silly Mode continuing exactly as it did
    # before Progression existed - it must never take the ordinary OLED
    # display down with it.
    progression = None
    progression_state = None
    progression_rng = random.Random()
    progression_last_save = 0.0
    progression_dirty = False
    progression_request_markers = {}   # reset/import request de-dup - see check_*_request()
    pending_reveals = []   # queue of ("level_up", {...}) / ("achievement", {...})
    try:
        import piratebox_progression as progression
        progression_state = progression.load_state(log=log)
        progression.ensure_identity(progression_state, progression_rng)
        progression.observe_boot(progression_state)
        progression_dirty = True
        log.info(
            "Progression loaded: %s, level %d, %d achievement(s).",
            progression_state["device"]["name"], progression_state["xp"]["level"],
            len(progression_state["achievements"]),
        )
    except Exception as exc:  # noqa: BLE001 - Progression is fully optional to Silly Mode
        log.warning("Progression subsystem unavailable (%s) - Silly Mode continues without it.", exc)
        progression = None

    # BH1750 ambient light sensor - MIGRATED 2026-09-07 from the Pi's
    # own I2C1 bus to the ESP32-S3 supervisor's I2C bus (GPIO8/GPIO9) -
    # see docs/OPERATIONAL-DECISIONS.md for the full migration record.
    # piratebox_esp32_bh1750.py is a drop-in replacement for the
    # retired piratebox_bh1750.py registration: same two-function
    # interface, same get_diagnostics() shape, so nothing below this
    # block (publish_sensors_export(), build_glance_metrics()) needed
    # to change at all - only which module gets imported/registered
    # here changed. piratebox_bh1750.py itself is unchanged and still
    # in the repo for historical/rollback reference, but nothing
    # imports it anymore. A missing/failed sensor or module must never
    # affect Progression (already independently optional above) or the
    # OLED display - this is its own separate try/except specifically
    # so a BH1750-only failure can never undo a successful Progression
    # load, and vice versa.
    #
    # bh1750_module is kept (not just the bare reader function) so the
    # sensors-public.json export below (2026-09-07, Environment web UI
    # round) can call its get_diagnostics() too - stays None, and the
    # export below simply omits "ambient_light" entirely, if this
    # import ever fails; a module that was never wired/imported must
    # never appear in the public export at all (never a permanent
    # "unavailable" placeholder for hardware that isn't there).
    bh1750_module = None
    if progression is not None:
        try:
            import piratebox_esp32_bh1750
            progression.register_hardware_signal("ambient_lux", piratebox_esp32_bh1750.read_ambient_lux)
            bh1750_module = piratebox_esp32_bh1750
            log.info("BH1750 ambient light sensor signal registered (ESP32-owned, migrated 2026-09-07).")
        except Exception as exc:  # noqa: BLE001 - optional hardware, never fatal
            log.warning("BH1750 module unavailable (%s) - ambient_lux signal stays unregistered.", exc)

        # ESP32-S3 hardware/sensor supervisor (commissioned 2026-09-07,
        # firmware+daemon built the same day - see docs/ESP32-SUPERVISOR-
        # DESIGN.md). piratebox_esp32_client.py ONLY reads the separate
        # piratebox_esp32_supervisor.py daemon's own cached export - it
        # never opens the serial port itself, so importing it into THIS
        # process is safe (no port contention with that daemon, which
        # remains the sole owner of the actual hardware link - see its
        # own header for why). A missing/failed import must never affect
        # Progression, BH1750, or the OLED display - its own separate
        # try/except, same pattern as the BH1750 block just above.
        try:
            import piratebox_esp32_client
            progression.register_hardware_signal("esp32_temp_internal", piratebox_esp32_client.read_temp_internal)
            log.info("ESP32 supervisor temp_internal signal registered.")
        except Exception as exc:  # noqa: BLE001 - optional hardware, never fatal
            log.warning("ESP32 client module unavailable (%s) - esp32_temp_internal signal stays unregistered.", exc)

    sensors_last_publish = 0.0

    while not stop:
        if device is None:
            device = init_device()
            if device is None:
                time.sleep(RETRY_SECONDS)
                continue
            log.info("OLED initialized successfully.")
            last_image = None  # nothing to transition from after a reconnect

        status, stale = read_status_json()
        mode = read_mode()
        tick += 1
        alive_on = (tick % 2 == 0)
        now = time.time()

        # Always-on, never Silly-gated: a mode change is serious
        # operational information that must still show in Emergency
        # Mode or under a degraded condition.
        prev_mode = last_mode_seen
        mode_transition = mode if (prev_mode is not None and mode != prev_mode) else None
        last_mode_seen = mode
        emergency_exercised = (mode_transition == "normal" and prev_mode == "emergency")

        current_clients = None
        if not stale and isinstance(status, dict):
            cc = status.get("wifi_clients")
            if isinstance(cc, int):
                current_clients = cc

        # Always-on, never Silly-gated: the client-count pulse. Shown
        # for a couple of redraw ticks (not just one) so it's actually
        # visible at REFRESH_SECONDS=3s, not a single blink.
        if current_clients is not None:
            if last_seen_clients_for_pulse is not None and current_clients > last_seen_clients_for_pulse:
                pulse_ticks_remaining = 2
            last_seen_clients_for_pulse = current_clients
        pulse_now = pulse_ticks_remaining > 0
        if pulse_ticks_remaining > 0:
            pulse_ticks_remaining -= 1

        tier = compute_display_tier(mode, status, stale)
        silly_enabled = read_silly_enabled()
        ssh_active = read_ssh_established()
        status_check_active = read_status_check_active(now)
        status_check_just_started = status_check_active and not status_check_was_active
        status_check_was_active = status_check_active
        preview_active = read_preview_active(now)
        preview_just_started = preview_active and not preview_was_active
        if preview_just_started:
            preview_started_at = now
            preview_last_index = -1
            preview_current_render = None
        preview_was_active = preview_active
        glance_preview_active = read_glance_preview_active(now)
        glance_preview_just_started = glance_preview_active and not glance_preview_was_active
        if glance_preview_just_started:
            glance_preview_started_at = now
            glance_preview_last_index = -1
        glance_preview_was_active = glance_preview_active
        # Double-tap Silly toggle confirmation - edge is consumed every
        # single tick, even during Emergency/fault (see the branch below
        # for why): a toggle that happens mid-Emergency must never queue
        # up a delayed, surprising banner once Emergency later clears.
        silly_toggle_just_happened = read_silly_toggle_edge(silly_toggle_markers)
        transition_wipe = False

        # Idle/sleep tracking - always computed now (not just when
        # Silly Mode is on), because Progression needs "how long has it
        # been idle" and "did it just wake up" regardless of whether the
        # cosmetic display is currently switched on.
        if current_clients is not None and current_clients > 0:
            silly_zero_since = None
        elif silly_zero_since is None:
            silly_zero_since = now
        idle_seconds = (now - silly_zero_since) if silly_zero_since is not None else 0.0

        was_sleeping = silly_sleeping
        if idle_seconds >= SILLY_SLEEP_AFTER_SECONDS and not ssh_active:
            silly_sleeping = True
        elif (current_clients or 0) > 0 or ssh_active:
            silly_sleeping = False
        woke_this_tick = was_sleeping and not silly_sleeping
        if woke_this_tick:
            today = time.strftime("%Y-%m-%d", time.localtime(now))
            if wake_count_day != today:
                wake_count_day, wake_count_today = today, 0
            wake_count_today += 1

        # --- Progression: always runs, regardless of Silly Mode's own
        # toggle or the current tier - see piratebox_progression.py's
        # header for why. A missing/broken subsystem here must never
        # affect the display below it.
        if progression is not None:
            try:
                if progression.check_reset_request(progression_state, progression_request_markers, log=log):
                    pending_reveals.clear()
                elif progression.check_import_request(progression_state, progression_request_markers, log=log):
                    pending_reveals.clear()
                external_radio = (
                    isinstance(status, dict)
                    and status.get("visitor_ap", {}).get("provider") == "external"
                )
                p_ctx = {
                    "now": now, "dt": REFRESH_SECONDS, "tier": tier,
                    "current_clients": current_clients, "ssh_active": ssh_active,
                    "idle_seconds": idle_seconds, "emergency_exercised": emergency_exercised,
                    "silly_enabled": silly_enabled, "external_radio": external_radio,
                    "wake_count_today": wake_count_today,
                    "hardware": progression.read_hardware_signals(),
                }
                p_result = progression.observe_tick(progression_state, p_ctx)
                if p_result["leveled_up"]:
                    pending_reveals.append((
                        "level_up",
                        {"level": p_result["new_level"], "title": progression.title_for_level(p_result["new_level"])},
                    ))
                for aid in p_result["new_achievements"]:
                    spec = progression.ACHIEVEMENTS.get(aid)
                    if spec is not None:
                        pending_reveals.append(("achievement", {"name": spec["name"]}))
                if p_result["leveled_up"] or p_result["new_achievements"]:
                    progression_dirty = True
                progression_last_save, saved = progression.maybe_save_and_report(
                    progression_state, progression_dirty, progression_last_save, now, log=log,
                )
                if saved:
                    progression_dirty = False
            except Exception as exc:  # noqa: BLE001 - Progression must never break the display
                log.warning("Progression tick failed (%s) - continuing without it this tick.", exc)

        # Environment web UI round (2026-09-07): independent of whether
        # Progression's own tick above succeeded this cycle - a broken
        # Progression tick must not also stop sensor readings from
        # reaching the public export, and vice versa. Cheap: the
        # function's own throttle makes this a no-op most ticks.
        try:
            sensors_last_publish = publish_sensors_export(bh1750_module, sensors_last_publish, now)
        except Exception as exc:  # noqa: BLE001 - optional export, never fatal
            log.warning("Sensor export publish failed (%s) - continuing without it.", exc)

        if mode_transition is not None:
            # A real mode flip always wins outright - never gated,
            # never mixed with Silly Mode or the status-check override.
            page, extra = "mode_transition", {"new_mode": mode_transition}
        elif tier in ("emergency", "fault"):
            # The mandatory priority floor: Emergency/fault always fall
            # straight through to the plain serious rotation, exactly
            # as this daemon behaved before Silly Mode existed - ahead
            # of Silly Mode AND ahead of a short-press override (a
            # button tap cannot hide an actual fault). Note: pending
            # level-up/achievement reveals are simply left queued - they
            # surface the next time this branch isn't taken, never
            # interrupting a fault/emergency.
            page, extra = PAGE_ORDER[page_index], None
            transition_wipe = seconds_on_current_page == 0.0 and last_image is not None
        elif silly_toggle_just_happened:
            # Explicit temporary control confirmation - a double tap
            # just flipped /tmp/piratebox/silly (see
            # piratebox_button_daemon.py's toggle_silly_mode()).
            # Deliberately placed ABOVE the "not silly_enabled" branch
            # below, not below it: `silly_enabled` above was already
            # read AFTER the toggle took effect, so if the double tap
            # just turned Silly OFF, that branch would otherwise swallow
            # this tick before the confirmation ever got a chance to
            # show - and the user must see "OFF" too, not just "ON".
            # Ranked below Emergency/fault (the elif above already
            # excluded those) per the required priority: a toggle that
            # happens to land mid-Emergency still silently updates the
            # underlying state (read fresh next tick, no extra code
            # needed for that), but its visible confirmation is skipped
            # this tick rather than covering the Emergency screen - it
            # simply resumes as an ordinary, un-announced state change
            # once Emergency clears. This one tick briefly does not draw
            # the tier=="warning" badge either, the same accepted
            # trade-off the status-check banner immediately above it
            # already makes for its own one-shot tick.
            page, extra = "silly_toggle_banner", {"new_state": silly_enabled}
        elif glance_preview_active:
            # Operator-only "show me the ordinary glance pages" demo
            # (Distance/Glance Display physical-validation aid, see
            # `piratebox-silly glance-preview` and GLANCE_PREVIEW_ORDER).
            # Deliberately placed ABOVE `not silly_enabled` below (unlike
            # the Silly preview, which sits below it) - glance pages are
            # not Silly content, so this must work whether Silly Mode is
            # on or off; ranked below Emergency/fault/toggle-confirmation
            # per the same mandatory priority every override here
            # respects. Cycles the fixed, always-eligible page list once
            # every PREVIEW_SECONDS_PER_ITEM, reusing that same pacing
            # constant the Silly preview already uses - no separate
            # timing constant needed for an equivalent purpose.
            elapsed = now - (glance_preview_started_at or now)
            glance_preview_index = int(elapsed // PREVIEW_SECONDS_PER_ITEM) % len(GLANCE_PREVIEW_ORDER)
            if glance_preview_index != glance_preview_last_index or glance_metrics is None:
                glance_preview_last_index = glance_preview_index
                glance_page_id = GLANCE_PREVIEW_ORDER[glance_preview_index]
                glance_metrics, prev_cpu_jiffies = build_glance_metrics(status, stale, prev_cpu_jiffies, pulse_now, bh1750_module)
            page, extra = "glance", {
                "page_id": glance_page_id, "metrics": glance_metrics,
                "label_fonts": glance_label_fonts, "font_cpu_label": font_glance_cpu_label,
                "font_medium": font_glance_medium, "font_big": font_glance_big,
            }
        elif not silly_enabled:
            # Silly Mode is off - exactly today's plain serious rotation,
            # matching the "default off = exactly today's display"
            # requirement, EXCEPT for one addition (2026-09-04, Distance/
            # Glance Display): a separate, simpler cadence (see
            # advance_offline_glance_cadence()) occasionally interleaves
            # one large-format glance page into this rotation too, per
            # instruction that glance pages must not require Silly Mode
            # to be on. (A status-check press here would still be a
            # visual no-op the rest of the time anyway, since this
            # already IS the real status rotation - so it's deliberately
            # not specially detected in this branch; see status_check_
            # active below for where it actually changes anything.)
            offline_glance_phase, offline_glance_seconds_remaining = advance_offline_glance_cadence(
                offline_glance_phase, offline_glance_seconds_remaining, REFRESH_SECONDS,
            )
            if offline_glance_phase == "glance":
                if not offline_glance_was_active:
                    # Fresh entry into this glance slot - pick a page and
                    # read its metrics ONCE, then hold both for the whole
                    # slot (exactly like every other held render in this
                    # daemon), not re-picked/re-read every tick.
                    glance_metrics, prev_cpu_jiffies = build_glance_metrics(
                        status, stale, prev_cpu_jiffies, pulse_now, bh1750_module,
                    )
                    glance_page_id = select_glance_page(
                        glance_metrics, glance_rng, glance_page_id, glance_cooldowns, now,
                    )
                    offline_glance_was_active = True
                page, extra = "glance", {
                    "page_id": glance_page_id, "metrics": glance_metrics,
                    "label_fonts": glance_label_fonts, "font_cpu_label": font_glance_cpu_label,
                "font_medium": font_glance_medium, "font_big": font_glance_big,
                }
            else:
                offline_glance_was_active = False
                page, extra = PAGE_ORDER[page_index], None
                transition_wipe = seconds_on_current_page == 0.0 and last_image is not None
        elif status_check_active:
            # Explicit temporary override (a short press on the physical
            # button, or any future trigger of the same signal file) -
            # ranks above Silly Mode/personality, below Emergency/fault
            # (already excluded by the elif chain above). Shows the same
            # serious rotation "not silly_enabled" does, so the known
            # chronic undervoltage warning is represented exactly the
            # way it already is there (the Health page's own boxed
            # notice) - no separate badge logic needed for this branch.
            if status_check_just_started:
                page, extra = "status_check_banner", {}
            else:
                page, extra = PAGE_ORDER[page_index], None
                transition_wipe = seconds_on_current_page == 0.0 and last_image is not None
        elif preview_active:
            # Operator-only "show me common expressions" demo
            # (Expression Engine v2 physical-validation aid, see
            # `piratebox-silly preview` and PREVIEW_PLAYLIST above) -
            # same priority tier as status_check_active immediately
            # above (an explicit, deliberate operator action), and,
            # like every branch here, can never run during Emergency/
            # fault or while Silly Mode is off - both are already
            # excluded higher in this chain, so this branch is only
            # ever reached when neither applies. Cycles the fixed
            # playlist once every PREVIEW_SECONDS_PER_ITEM for as long
            # as the request stays fresh - no rarity engine call
            # anywhere in this branch, so nothing shown here can ever
            # be an uncommon/rare/legendary/secret variant, regardless
            # of the device's real level/history. The CLI itself prints
            # what's about to happen and for how long, so no dedicated
            # opening banner page is needed here - the first playlist
            # item just appears on the very next redraw.
            elapsed = now - (preview_started_at or now)
            preview_index = int(elapsed // PREVIEW_SECONDS_PER_ITEM) % len(PREVIEW_PLAYLIST)
            if preview_index != preview_last_index or preview_current_render is None:
                preview_last_index = preview_index
                item = PREVIEW_PLAYLIST[preview_index]
                if item.get("anim") is not None:
                    final_render, _ = play_animation_burst(
                        device, item["anim"], tier, item.get("quip"),
                        font, font_small, font_big, mode,
                    )
                    preview_current_render = final_render or {"expression": "idle"}
                else:
                    preview_current_render = item
            page, extra = "silly", {"render": preview_current_render, "tier": tier}
        else:
            # tier is "ok" or "warning," Silly Mode is on, and no
            # override is active.
            event = None
            if current_clients is not None and silly_last_clients is not None:
                if current_clients > silly_last_clients:
                    event = "excited" if silly_last_clients == 0 else "surprised"
                elif current_clients == 0 and silly_last_clients > 0:
                    event = "confused"
            if current_clients is not None:
                silly_last_clients = current_clients
            if woke_this_tick:
                event = "waking"  # the bigger transition wins over a same-tick client event

            had_hold_before = silly_hold_remaining > 0
            in_special_state = (event is not None) or silly_sleeping or had_hold_before

            # Personality-vs-status cadence clock - only advances here,
            # i.e. only while this branch is actually the one deciding
            # the display, so a sleep/hold/pending-reveal/status-check
            # interruption pauses it rather than losing time (see the
            # state's own initialization comment above).
            silly_cadence_phase, silly_cadence_seconds_remaining = advance_silly_cadence(
                silly_cadence_phase, silly_cadence_seconds_remaining, REFRESH_SECONDS,
            )

            if event is not None:
                # The rarity engine gets first say on how a freshly-
                # detected event actually looks - most of the time this
                # is indistinguishable from the plain reaction (the
                # family's own "common" variant), occasionally it isn't.
                family = {"excited": "client_arrival", "surprised": "client_arrival", "waking": "wake"}.get(event)
                render = None
                if progression is not None and family is not None:
                    try:
                        variant = progression.roll_event(family, progression_state, {
                            "now": now, "idle_seconds": idle_seconds, "ssh_active": ssh_active,
                            "current_clients": current_clients,
                        }, progression_rng)
                        if variant is not None:
                            render = dict(variant["render"])
                    except Exception:  # noqa: BLE001
                        render = None
                if render is None:
                    render = {"expression": event}
                if render.get("anim") is not None:
                    # Expression Engine v2: the rarity engine picked an
                    # animated variant for this event (e.g. an uncommon/
                    # rare reaction upgraded from a plain static face) -
                    # flash it now, then hold its settle frame exactly
                    # like a plain one-shot reaction already would.
                    final_render, anim_hold_ticks = play_animation_burst(
                        device, render["anim"], tier, render.get("quip"),
                        font, font_small, font_big, mode,
                    )
                    if final_render is not None:
                        render, hold_ticks = final_render, anim_hold_ticks
                    else:
                        render, hold_ticks = {"expression": event}, SILLY_ONE_SHOT_HOLD_TICKS
                else:
                    hold_ticks = SILLY_ONE_SHOT_HOLD_TICKS
                silly_hold_render, silly_hold_remaining = render, hold_ticks

            if pending_reveals and not in_special_state:
                kind, payload = pending_reveals.pop(0)
                page, extra = kind, payload
            elif silly_sleeping and event is None:
                page, extra = "silly", {"render": {"expression": "sleeping"}, "tier": tier}
            elif silly_hold_remaining > 0:
                render = silly_hold_render
                silly_hold_remaining -= 1
                page, extra = "silly", {"render": render, "tier": tier}
            elif silly_cadence_phase == "glance":
                # One large-format, at-a-distance page (Distance/Glance
                # Display, 2026-09-04) - see piratebox_glance.py. Picked
                # and read ONCE on fresh entry into this slot, then held
                # for the whole ~8s, exactly like the "status" phase
                # right below holds the same serious page for its own
                # duration rather than re-rendering a fresh decision
                # every tick.
                if not silly_glance_was_active:
                    glance_metrics, prev_cpu_jiffies = build_glance_metrics(
                        status, stale, prev_cpu_jiffies, pulse_now, bh1750_module,
                    )
                    glance_page_id = select_glance_page(
                        glance_metrics, glance_rng, glance_page_id, glance_cooldowns, now,
                    )
                    silly_glance_was_active = True
                page, extra = "glance", {
                    "page_id": glance_page_id, "metrics": glance_metrics,
                    "label_fonts": glance_label_fonts, "font_cpu_label": font_glance_cpu_label,
                "font_medium": font_glance_medium, "font_big": font_glance_big,
                }
            elif silly_cadence_phase == "status":
                silly_glance_was_active = False
                # The regular, automatic status interlude (see
                # SILLY_CADENCE_* above) - the ordinary serious rotation,
                # for real airtime (~12-15s), not a one-tick glance.
                # Deliberately NO special transition banner here (unlike
                # the button-triggered status_check_active branch above)
                # - this happens every ~30-45s forever as part of normal
                # operation, and a banner every cycle would become noise
                # rather than a helpful cue.
                page, extra = PAGE_ORDER[page_index], None
                transition_wipe = seconds_on_current_page == 0.0 and last_image is not None
            else:
                expression = compute_silly_expression(
                    tick, has_clients=(current_clients or 0) > 0, ssh_active=ssh_active,
                )
                if progression is not None:
                    # Personality-mannerism layer (Expression Engine v2,
                    # 2026-09-04) - a no-op unless `expression` happens
                    # to be one of the small handful bias_ambient_
                    # expression() knows how to reshape (currently just
                    # "idle"/"blink") AND the relevant weight has
                    # drifted from neutral AND a modest probability roll
                    # hits - see that function's own docstring. Never
                    # touches "pirate_flourish"/"ssh_watch" (neither is
                    # ever a substitution target), so this is safe to
                    # call unconditionally right here rather than
                    # special-casing which expressions are eligible.
                    expression = bias_ambient_expression(
                        expression, progression_state.get("weights", {}), progression_rng,
                    )
                render = {"expression": expression}
                if expression == "pirate_flourish":
                    family = "flourish"
                    variant = None
                    if progression is not None:
                        try:
                            variant = progression.roll_event(family, progression_state, {
                                "now": now, "idle_seconds": idle_seconds, "ssh_active": ssh_active,
                                "current_clients": current_clients,
                            }, progression_rng)
                        except Exception:  # noqa: BLE001
                            variant = None
                    if variant is not None:
                        render = dict(variant["render"])
                    if render.get("anim") is None and (
                        "quip" not in render or render.get("quip") is None
                    ):
                        n = current_clients if current_clients is not None else 0
                        render = dict(render)
                        render["quip"] = SILLY_QUIPS[
                            (tick // SILLY_FLOURISH_EVERY_TICKS - 1) % len(SILLY_QUIPS)
                        ].format(n=n)
                elif progression is not None:
                    # Rare/secret ambient texture, layered opportunistically
                    # on top of the plain ambient cycle - almost always a
                    # no-op (see EVENT_FAMILIES["ambient"]'s own header note).
                    try:
                        variant = progression.roll_event("ambient", progression_state, {
                            "now": now, "idle_seconds": idle_seconds, "ssh_active": ssh_active,
                            "current_clients": current_clients,
                        }, progression_rng)
                        if variant is not None:
                            render = dict(variant["render"])
                    except Exception:  # noqa: BLE001
                        pass

                if render.get("anim") is not None:
                    # An animated flourish/ambient variant was picked -
                    # flash it now and fold its settle frame into the
                    # ordinary hold mechanism, exactly like an animated
                    # event reaction does above, so it stays visible for
                    # more than the one tick a plain flourish gets.
                    final_render, anim_hold_ticks = play_animation_burst(
                        device, render["anim"], tier, render.get("quip"),
                        font, font_small, font_big, mode,
                    )
                    if final_render is not None:
                        silly_hold_render, silly_hold_remaining = final_render, anim_hold_ticks
                        render = final_render
                page, extra = "silly", {"render": render, "tier": tier}

        try:
            new_image = build_frame(
                device, page, font, font_small, font_big, status, stale, mode,
                alive_on=alive_on, pulse=pulse_now, extra=extra,
            )
            display_frame(device, new_image, old_img=last_image, transition=transition_wipe)
            last_image = new_image
        except Exception as exc:
            # A real write/communication failure - the display was
            # likely unplugged mid-run. Drop back to the retry-init
            # loop rather than crashing; this is the "recovers when
            # hardware becomes available" path, not an error exit.
            log.warning("Lost contact with OLED (%s) - will retry.", exc)
            device = None
            last_image = None
            time.sleep(RETRY_SECONDS)
            continue

        time.sleep(REFRESH_SECONDS)
        seconds_on_current_page += REFRESH_SECONDS
        if seconds_on_current_page >= PAGE_SECONDS:
            page_index = (page_index + 1) % len(PAGE_ORDER)
            seconds_on_current_page = 0.0

    return 0


if __name__ == "__main__":
    sys.exit(main())
