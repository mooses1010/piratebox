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

import json
import logging
import os
import re
import signal
import sys
import time

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import ImageFont

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


# --- Page renderers -----------------------------------------------------
# Each function draws exactly one page into the given ImageDraw context.
# None of these touch the network, sudo, or any writable PirateBox state
# - pure read-and-render.

def render_status(draw, font, mode: str, status, stale: bool) -> None:
    draw.text((0, 0), "PIRATEBOX", font=font, fill="white")
    mode_label = "EMERGENCY" if mode == "emergency" else "NORMAL"
    draw.text((0, 14), f"Mode: {mode_label}", font=font, fill="white")
    draw.text((0, 28), f"SSID: {read_ssid()}", font=font, fill="white")
    if stale or status is None:
        draw.text((0, 42), "Clients: unknown", font=font, fill="white")
    else:
        draw.text((0, 42), f"Clients: {status.get('wifi_clients', '?')}", font=font, fill="white")


def render_time(draw, font, status, stale: bool) -> None:
    now = time.localtime()
    utc = time.gmtime()
    draw.text((0, 0), "TIME", font=font, fill="white")
    draw.text((0, 12), f"Local {time.strftime('%I:%M:%S %p', now)}", font=font, fill="white")
    draw.text((0, 24), f"UTC   {time.strftime('%H:%M:%S', utc)}", font=font, fill="white")
    draw.text((0, 36), f"Date  {time.strftime('%Y-%m-%d', now)}", font=font, fill="white")
    ts = (status or {}).get("time_source") if not stale and status else None
    if ts is None:
        draw.text((0, 48), "Source: unknown", font=font, fill="white")
    else:
        rtc = "RTC" if ts.get("rtc_detected") else "no-RTC"
        ntp = "NTP-synced" if ts.get("ntp_synchronized") else "not synced"
        draw.text((0, 48), f"{rtc}, {ntp}", font=font, fill="white")


def render_network(draw, font, status, stale: bool) -> None:
    draw.text((0, 0), "NETWORK", font=font, fill="white")
    draw.text((0, 12), f"SSID: {read_ssid()}", font=font, fill="white")
    draw.text((0, 24), f"IP:   {AP_IP_ADDRESS}", font=font, fill="white")
    if stale or status is None:
        draw.text((0, 36), "Services: unknown", font=font, fill="white")
        return
    services = status.get("services", {})
    ok = sum(1 for v in services.values() if v is True)
    total = len(services) if services else 0
    draw.text((0, 36), f"Services: {ok}/{total} up", font=font, fill="white")
    down = [name for name, v in services.items() if v is not True]
    if down:
        draw.text((0, 48), f"Down: {','.join(down)[:20]}", font=font, fill="white")


def render_health(draw, font, status, stale: bool) -> None:
    draw.text((0, 0), "HEALTH", font=font, fill="white")
    draw.text((0, 12), f"Uptime: {format_duration(read_uptime_seconds())}", font=font, fill="white")
    free, total = read_disk_free_total()
    draw.text((0, 24), f"Storage: {format_bytes_gb(free)}/{format_bytes_gb(total)}", font=font, fill="white")
    temp = read_cpu_temp_c()
    temp_str = f"{temp:.0f}C" if temp is not None else "unknown"
    emergency_s = read_emergency_runtime_seconds()
    draw.text((0, 36), f"CPU: {temp_str}  Emerg: {format_duration(emergency_s)}", font=font, fill="white")
    # Power warning - conditional, one line, only when there's something
    # to say. Deliberately does NOT claim the OLED caused or is affected
    # by this; it is purely reporting the same power.undervoltage_now
    # flag the Stats/About pages already surface.
    if not stale and isinstance(status, dict):
        power = status.get("power", {})
        if power.get("undervoltage_now") is True:
            draw.text((0, 48), "! POWER: UNDERVOLTAGE", font=font, fill="white")


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


def render_page(device, font, page: str, status, stale: bool, mode: str, extra=None) -> None:
    with canvas(device) as draw:
        if page == "status":
            render_status(draw, font, mode, status, stale)
        elif page == "time":
            render_time(draw, font, status, stale)
        elif page == "network":
            render_network(draw, font, status, stale)
        elif page == "health":
            render_health(draw, font, status, stale)
        elif page == "personality":
            render_personality(draw, font, extra["quip"])
        elif page == "celebration":
            render_celebration(draw, font, extra["client_count"])
        elif page == "milestone":
            render_milestone(draw, font, extra["message"])


def load_font():
    try:
        return ImageFont.truetype(FONT_PATH, 11)
    except OSError:
        log.warning("Could not load %s, falling back to PIL default bitmap font.", FONT_PATH)
        return ImageFont.load_default()


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

    font = load_font()
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

    # Personality-mode bookkeeping - deliberately plain in-memory state,
    # never written to disk (see the header note above).
    rotation_count = 0
    last_wifi_clients = None
    milestones_shown = set()

    while not stop:
        if device is None:
            device = init_device()
            if device is None:
                time.sleep(RETRY_SECONDS)
                continue
            log.info("OLED initialized successfully.")

        status, stale = read_status_json()
        mode = read_mode()
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

        if one_shot is not None:
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

        try:
            render_page(device, font, page, status, stale, mode, extra=extra)
        except Exception as exc:
            # A real write/communication failure - the display was
            # likely unplugged mid-run. Drop back to the retry-init
            # loop rather than crashing; this is the "recovers when
            # hardware becomes available" path, not an error exit.
            log.warning("Lost contact with OLED (%s) - will retry.", exc)
            device = None
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
