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
STATUS_FILE = "/run/piratebox/status.json"
TRANSITIONS_LOG = "/var/www/html/data/mode-transitions.log"
HOSTAPD_CONF = "/etc/hostapd/hostapd.conf"
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

# Fixed by this project's network design (static dhcpcd config) - not
# looked up, per docs/HARDWARE-INTEGRATION-DESIGN.md §5's own content
# plan ("already known/fixed... no lookup needed").
AP_IP_ADDRESS = "10.0.0.1"

# Personality mode (see header note above): shown once every this many
# full rotations of the four serious pages - deliberately "occasional,"
# not "every cycle." At PAGE_SECONDS=8s x 4 pages = 32s per rotation,
# 6 rotations is roughly 3 minutes between quips.
PERSONALITY_EVERY_N_CYCLES = 6

QUIPS = [
    "All quiet on the high seas.",
    "No leaks detected below decks.",
    "Charts and compass both in order.",
    "Powder's dry, crew's accounted for.",
    "Fair winds, following seas.",
    "Nothin' to report, cap'n.",
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


def personality_allowed(mode: str, status, stale: bool) -> bool:
    """Gate for every personality frame (the occasional quip page, the
    connection celebration, and the uptime milestone). A serious
    condition always wins: Emergency Mode, a stale/missing status
    snapshot, any Core service down, or active undervoltage all
    suppress personality frames entirely - the display falls straight
    through to a normal serious page instead. This is checked fresh
    every time a personality frame would be shown, not cached, so a
    condition that appears *during* the personality-quiet window takes
    effect on the very next redraw."""
    if mode == "emergency":
        return False
    if stale or not isinstance(status, dict):
        return False
    services = status.get("services", {})
    if any(v is not True for v in services.values()):
        return False
    if status.get("power", {}).get("undervoltage_now") is True:
        return False
    return True


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


def render_personality(draw, font, quip: str) -> None:
    draw_skull_and_crossbones(draw, 2, 4)
    draw.text((38, 8), "PIRATEBOX", font=font, fill="white")
    draw.text((38, 20), "OK", font=font, fill="white")
    draw.text((0, 40), quip, font=font, fill="white")


def render_celebration(draw, font, client_count) -> None:
    draw_skull_and_crossbones(draw, 2, 4)
    draw.text((38, 8), "AHOY!", font=font, fill="white")
    draw.text((0, 40), f"A client boarded! ({client_count} aboard)", font=font, fill="white")


def render_milestone(draw, font, message: str) -> None:
    draw_skull_and_crossbones(draw, 2, 4)
    draw.text((38, 8), "MILESTONE", font=font, fill="white")
    draw.text((0, 40), message, font=font, fill="white")


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
    elif page == "personality":
        render_personality(draw, font, extra["quip"])
    elif page == "celebration":
        render_celebration(draw, font, extra["client_count"])
    elif page == "milestone":
        render_milestone(draw, font, extra["message"])
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
        "(auto-rotating - no cycle button wired yet), %d-page cycle, "
        "personality quip every %d rotations (suppressed in Emergency "
        "Mode or any degraded condition).",
        I2C_PORT, I2C_ADDRESS, REFRESH_SECONDS, PAGE_SECONDS, len(PAGE_ORDER),
        PERSONALITY_EVERY_N_CYCLES,
    )

    page_index = 0
    seconds_on_current_page = 0.0
    device = None
    last_image = None  # previous displayed frame, for the slide transition
    tick = 0            # increments every redraw; drives the heartbeat dot

    # Personality-mode bookkeeping - deliberately plain in-memory state,
    # never written to disk (see the header note above).
    rotation_count = 0
    last_wifi_clients = None
    milestones_shown = set()

    # Round-8 instrument-panel bookkeeping - also plain in-memory state,
    # also never written to disk. Tracked separately from the
    # personality-only last_wifi_clients above because these two must
    # keep working even when personality_allowed() is False (Emergency
    # Mode, a stale snapshot, a down service, or active undervoltage) -
    # a client-count pulse and a mode-change banner are both plain
    # operational information, not personality.
    last_seen_clients_for_pulse = None
    pulse_ticks_remaining = 0
    last_mode_seen = None

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

        # Always-on, never personality-gated: a mode change is serious
        # operational information that must still show in Emergency
        # Mode or under a degraded condition.
        mode_transition = mode if (last_mode_seen is not None and mode != last_mode_seen) else None
        last_mode_seen = mode

        # Always-on, never personality-gated: the client-count pulse.
        # Shown for a couple of redraw ticks (not just one) so it's
        # actually visible at REFRESH_SECONDS=3s, not a single blink.
        if not stale and isinstance(status, dict):
            current_clients = status.get("wifi_clients")
            if isinstance(current_clients, int):
                if last_seen_clients_for_pulse is not None and current_clients > last_seen_clients_for_pulse:
                    pulse_ticks_remaining = 2
                last_seen_clients_for_pulse = current_clients
        pulse_now = pulse_ticks_remaining > 0
        if pulse_ticks_remaining > 0:
            pulse_ticks_remaining -= 1

        allowed = personality_allowed(mode, status, stale)

        # One-shot frames (connection celebration, uptime milestone) can
        # preempt whatever would otherwise show, but only ever a plain
        # data read - no new tracking, no per-client information kept.
        one_shot = None
        if allowed and not stale and isinstance(status, dict):
            current_clients = status.get("wifi_clients")
            if isinstance(current_clients, int):
                if last_wifi_clients is not None and current_clients > last_wifi_clients:
                    one_shot = ("celebration", {"client_count": current_clients})
                last_wifi_clients = current_clients
        if one_shot is None and allowed:
            uptime_days = read_uptime_seconds() / 86400.0
            for threshold, label in ((1, "1 day"), (7, "1 week")):
                if uptime_days >= threshold and threshold not in milestones_shown:
                    milestones_shown.add(threshold)
                    one_shot = ("milestone", {"message": f"Underway for {label}!"})
                    break

        # Priority order: a real mode change always wins (never gated),
        # then the personality one-shots (gated), then the occasional
        # personality quip slot, then the normal serious rotation.
        if mode_transition is not None:
            page, extra = "mode_transition", {"new_mode": mode_transition}
        elif one_shot is not None:
            page, extra = one_shot
        elif (
            page_index == 0
            and rotation_count > 0
            and rotation_count % PERSONALITY_EVERY_N_CYCLES == 0
            and allowed
        ):
            # The whole "status" slot for this rotation becomes a
            # personality slot instead - occasional, not constant.
            quip = QUIPS[(rotation_count // PERSONALITY_EVERY_N_CYCLES - 1) % len(QUIPS)]
            page, extra = "personality", {"quip": quip}
        else:
            page, extra = PAGE_ORDER[page_index], None

        # The brief slide wipe (see display_frame()) is reserved for an
        # actual page change in the normal rotation - seconds_on_current_
        # page resets to 0.0 exactly on the redraw right after page_index
        # advances, so this is true only on that one redraw, never on a
        # same-page refresh and never for a one-shot/personality frame.
        transition_wipe = page in PAGE_ORDER and seconds_on_current_page == 0.0 and last_image is not None

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
            if page_index == 0:
                rotation_count += 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
