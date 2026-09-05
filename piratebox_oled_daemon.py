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
#     the display any more often than before. An occasional real-status
#     "peek" (one of the four serious pages, for one tick, every
#     SILLY_STATUS_PEEK_EVERY_TICKS ticks) keeps glanceable status
#     honestly reachable without needing to turn Silly Mode off.
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
STATUS_FILE = "/run/piratebox/status.json"
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
SILLY_STATUS_PEEK_EVERY_TICKS = 20    # ~60s - one real serious page, one tick

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


# --- Silly Mode face rendering ------------------------------------------
# One parametrized primitive (draw_face) plus a small table mapping each
# named expression to its (eyes, brows, mouth, decoration) parameters -
# deliberately not one bespoke drawing function per expression, so
# adding/tuning an expression is a one-line table edit, not new drawing
# code. Every shape is a plain Pillow ellipse/arc/line/polygon, exactly
# like every other page on this display already uses.

FACE_CX, FACE_CY = 64, 27   # face center, leaving room above for the
                             # corner badges and below for a quip line
EYE_DX = 17                  # horizontal offset of each eye from center
EYE_R = 9                    # eye socket radius

EXPRESSIONS = {
    # name:          (eyes,         brows,          mouth,        decoration)
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
}


def draw_face(draw, eyes: str, brows: str, mouth: str, decoration: str = None) -> None:
    cx, cy = FACE_CX, FACE_CY
    lx, rx = cx - EYE_DX, cx + EYE_DX

    if decoration == "crown":
        draw.polygon(
            [(cx - 16, cy - EYE_R - 12), (cx - 10, cy - EYE_R - 22), (cx - 4, cy - EYE_R - 12),
             (cx, cy - EYE_R - 22), (cx + 4, cy - EYE_R - 12), (cx + 10, cy - EYE_R - 22),
             (cx + 16, cy - EYE_R - 12)],
            outline="white",
        )

    for ex in (lx, rx):
        # "wink" closes only the right eye, regardless of the base
        # `eyes` param for that side - the only per-eye asymmetry this
        # face system needs, so it's handled as a narrow special case
        # rather than a whole parallel eyes vocabulary.
        this_eye = "closed" if (decoration == "wink" and ex == rx) else eyes
        box = (ex - EYE_R, cy - EYE_R, ex + EYE_R, cy + EYE_R)
        if this_eye == "closed":
            draw.line((ex - EYE_R, cy, ex + EYE_R, cy), fill="white", width=2)
        elif eyes == "half":
            draw.arc(box, start=190, end=350, fill="white", width=2)
        elif eyes == "wide":
            wbox = (ex - EYE_R - 2, cy - EYE_R - 2, ex + EYE_R + 2, cy + EYE_R + 2)
            draw.ellipse(wbox, outline="white", width=2)
            draw.ellipse((ex - 3, cy - 3, ex + 3, cy + 3), fill="white")
        elif eyes in ("look_left", "look_right"):
            # Pupil pushed almost to the socket's edge (rather than a
            # small nudge from center) - a subtle few-pixel shift reads
            # as noise at this size, this reads as a clear direction.
            draw.ellipse(box, outline="white", width=2)
            shift = -(EYE_R - 4) if eyes == "look_left" else (EYE_R - 4)
            draw.ellipse((ex + shift - 3, cy - 3, ex + shift + 3, cy + 3), fill="white")
        else:  # "open"
            draw.ellipse(box, outline="white", width=2)
            draw.ellipse((ex - 3, cy - 3, ex + 3, cy + 3), fill="white")

        if brows == "raised":
            draw.line((ex - EYE_R, cy - EYE_R - 5, ex + EYE_R, cy - EYE_R - 8), fill="white", width=2)
        elif brows == "flat":
            draw.line((ex - EYE_R, cy - EYE_R - 4, ex + EYE_R, cy - EYE_R - 4), fill="white", width=2)
        elif brows == "one_raised" and ex == rx:
            draw.line((ex - EYE_R, cy - EYE_R - 3, ex + EYE_R, cy - EYE_R - 9), fill="white", width=2)

        if decoration == "sparkle":
            # A couple of short radiating tick marks above each eye -
            # distinguishes "excited" from the otherwise-similar
            # "surprised" (both wide-eyed) at a glance.
            draw.line((ex - EYE_R - 3, cy - EYE_R - 2, ex - EYE_R - 7, cy - EYE_R - 6), fill="white", width=1)
            draw.line((ex + EYE_R + 3, cy - EYE_R - 2, ex + EYE_R + 7, cy - EYE_R - 6), fill="white", width=1)

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
    """A couple of small 'z's near the top-right of a sleeping face -
    alternates size on tick parity for the only bit of "life" a resting
    face needs."""
    big = (tick % 2 == 0)
    draw.text((FACE_CX + 22, FACE_CY - 26), "z" if big else "Z", font=font_small, fill="white")
    draw.text((FACE_CX + 13, FACE_CY - 18), "Z" if big else "z", font=font_small, fill="white")


def draw_pirate_flourish(draw, font, font_small, quip: str) -> None:
    """The evolved skull-and-crossbones beat - same primitive as before
    (draw_skull_and_crossbones), now one entry in Silly Mode's own
    rotation rather than a standalone always-present page."""
    draw_skull_and_crossbones(draw, 2, 4)
    draw.text((38, 10), "PIRATEBOX", font=font, fill="white")
    draw.text((0, 46), quip, font=font_small, fill="white")


def draw_scene(draw, font, font_small, scene: str) -> None:
    """Legendary/secret "scene" beats - a step up from a plain face,
    still just plain Pillow primitives, still no image asset. Each is
    hand-drawn once here; piratebox_progression.py never imports this
    module or any drawing library - it only ever hands back a plain
    `{"scene": "<name>"}` dict, keeping state/logic and rendering
    cleanly separated (see that module's own header)."""
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
        draw.rectangle((cx - 4, cy - 10, cx + 4, cy - 2), outline="white")  # the note, rolled inside
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
    else:
        draw_face(draw, "open", "none", "smile_small")


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


def draw_skull_and_crossbones(draw, x: int, y: int) -> None:
    """A small (~28x28px) skull-and-crossbones, drawn with plain Pillow
    primitives - no external image file, no font glyph, nothing beyond
    what every other page on this display already uses."""
    # Cranium
    draw.ellipse((x, y, x + 24, y + 20), outline="white", fill="white")
    # Eye sockets (punched out in black)
    draw.ellipse((x + 4, y + 6, x + 10, y + 13), fill="black")
    draw.ellipse((x + 14, y + 6, x + 20, y + 13), fill="black")
    # Nose
    draw.polygon([(x + 12, y + 13), (x + 10, y + 17), (x + 14, y + 17)], fill="black")
    # Jaw/teeth
    draw.rectangle((x + 4, y + 19, x + 20, y + 24), outline="white", fill="white")
    for tx in range(x + 6, x + 20, 3):
        draw.line((tx, y + 19, tx, y + 24), fill="black")
    # Crossbones behind/below
    draw.line((x - 4, y + 28, x + 28, y + 20), fill="white", width=2)
    draw.line((x - 4, y + 20, x + 28, y + 28), fill="white", width=2)


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
        "status, any Core service down) - see compute_display_tier().",
        I2C_PORT, I2C_ADDRESS, REFRESH_SECONDS, PAGE_SECONDS, len(PAGE_ORDER),
        SILLY_FILE,
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
    silly_peek_index = 0         # rotates the occasional real-status peek
    wake_count_today = 0
    wake_count_day = None

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

        if mode_transition is not None:
            # A real mode flip always wins outright - never gated,
            # never mixed with Silly Mode.
            page, extra = "mode_transition", {"new_mode": mode_transition}
        elif tier in ("emergency", "fault") or not silly_enabled:
            # The mandatory priority floor: Emergency/fault always fall
            # straight through to the plain serious rotation, exactly
            # as this daemon behaved before Silly Mode existed. Silly
            # Mode disabled behaves identically - no quips, no faces,
            # matching the "default off = exactly today's display"
            # requirement. Note: pending level-up/achievement reveals
            # are simply left queued - they surface the next time this
            # branch isn't taken, never interrupting a fault/emergency
            # or a deliberately-off display.
            page, extra = PAGE_ORDER[page_index], None
            transition_wipe = seconds_on_current_page == 0.0 and last_image is not None
        else:
            # tier is "ok" or "warning" and Silly Mode is on.
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
                silly_hold_render, silly_hold_remaining = render, SILLY_ONE_SHOT_HOLD_TICKS

            if pending_reveals and not in_special_state:
                kind, payload = pending_reveals.pop(0)
                page, extra = kind, payload
            elif silly_sleeping and event is None:
                page, extra = "silly", {"render": {"expression": "sleeping"}, "tier": tier}
            elif silly_hold_remaining > 0:
                render = silly_hold_render
                silly_hold_remaining -= 1
                page, extra = "silly", {"render": render, "tier": tier}
            elif not in_special_state and tick % SILLY_STATUS_PEEK_EVERY_TICKS == 0:
                # A brief, occasional glance at real status - keeps
                # information reachable without needing Silly Mode off.
                page, extra = PAGE_ORDER[silly_peek_index % len(PAGE_ORDER)], None
                silly_peek_index += 1
            else:
                expression = compute_silly_expression(
                    tick, has_clients=(current_clients or 0) > 0, ssh_active=ssh_active,
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
                    if "quip" not in render or render.get("quip") is None:
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
