#!/bin/bash
#
# PirateBox - Phase 4 status helper.
#
# Narrowly-scoped, read-only system inspection, run periodically as root by
# piratebox-status.timer. This exists ONLY because the admin status page
# needs a few pieces of information PHP cannot obtain on its own without
# either running as root or having exec()/shell_exec() available - both of
# which are deliberately unavailable to PHP-FPM on this system (disable_functions
# in php.ini). Everything this script does is a fixed, hardcoded read of
# system state; it takes no arguments, reads no user input, and writes
# nothing but its own status file. It never touches www-data's write path
# and www-data is never granted sudo.
#
# Output is a single small JSON file on tmpfs (/run - never the SD card),
# written atomically (temp file + rename) and made world-readable so PHP
# can read it directly with a plain file read.
#
# Everything here is read-only inspection: iw station dump, systemctl
# is-active, vcgencmd get_throttled. Nothing here can be influenced by a
# web request.
#
# Post-Stage-32 addition: privacy-preserving connection-event tracking.
# See docs/OPERATIONAL-DECISIONS.md ("Connection Statistics") for the
# full design. In short: this compares each poll's associated-MAC list
# against the previous poll's (kept ONLY in a tmpfs scratch file,
# overwritten every 30s, never logged or copied to the SD card) to count
# new associations as "connection events." Only small integer counts,
# bucketed by hour, are ever persisted to the SD card
# (var/www/html/data/connection-stats.json) - no MAC address, IP,
# hostname, or other per-device identifier is ever written there or
# anywhere else. The persisted file is flushed once per hour (on
# rollover), not every 30-second poll, to keep SD card writes minimal.
#
# Field Tools addition: time-source status (rtc_detected/
# ntp_synchronized/fake_hwclock_installed) - see includes/
# fieldtools_time.php.
#
# Device Memory addition (docs/DEVICE-MEMORY-DESIGN.md): bounded
# Operational-History event tracking - boot events and undervoltage-
# onset events, edge-triggered (new event, not "still happening") the
# same way connection events already are, persisted to var/www/html/
# data/device-history.json ONLY when an event actually occurs (not
# every 30s poll). Boot events bounded by count (last 50); undervoltage
# events bucketed daily, bounded to a 90-day window. No raw per-second
# telemetry ever persists.

set -euo pipefail

OUT_DIR="/run/piratebox"
OUT_FILE="$OUT_DIR/status.json"
TMP_FILE="$OUT_FILE.tmp.$$"
PREV_STATIONS_FILE="$OUT_DIR/prev-stations"
HOUR_SCRATCH_FILE="$OUT_DIR/hour-scratch"
CONN_STATS_FILE="/var/www/html/data/connection-stats.json"

mkdir -p "$OUT_DIR"
chmod 0755 "$OUT_DIR"

# --- Visitor AP interface: auto-detected, not hardcoded -----------------
# External AP Architecture Round (2026-09-03): PirateBox may in the
# future serve visitors from either the onboard wlan0 or the external
# AWUS036ACM (stable name "pb-ap" once etc/udev/rules.d/
# 99-piratebox-external-ap.rules is installed - see
# docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md). Rather than keep a separate
# "which one is active" config file that could drift from reality, this
# asks the kernel directly, every poll: whichever interface `iw dev`
# currently reports as `type AP` IS the visitor AP, full stop. This is
# the same principle as the rest of this script (read real state, don't
# assume) and means connection statistics automatically follow a future
# migration with no code change and no coordination file to keep in
# sync - see that design doc's "Connection statistics" section.
#
# Today, only wlan0 is ever brought up in AP mode, so this resolves to
# exactly wlan0 - byte-identical behavior to before this change.
visitor_ap_iface=""
visitor_ap_provider="none"
visitor_ap_multiple_warning=false
if command -v iw >/dev/null 2>&1; then
    ap_ifaces=$(iw dev 2>/dev/null | awk '
        /^phy#/ { iface="" }
        /^[ \t]*Interface / { iface=$2 }
        /^[ \t]*type AP$/ { if (iface != "") print iface }
    ')
    ap_iface_count=$(printf '%s\n' "$ap_ifaces" | grep -c . || true)
    if [ "$ap_iface_count" -eq 1 ]; then
        visitor_ap_iface="$ap_ifaces"
    elif [ "$ap_iface_count" -gt 1 ]; then
        # Not a supported configuration (this project runs exactly one
        # visitor AP at a time) - prefer the external radio if it's one
        # of the AP-mode interfaces found, since a future migration
        # step bringing pb-ap up is expected to take wlan0 down first,
        # and if both are somehow up simultaneously that's the more
        # actionable radio to report against. Flag it either way so
        # this anomaly is visible rather than silently picking one.
        visitor_ap_multiple_warning=true
        if printf '%s\n' "$ap_ifaces" | grep -qx "pb-ap"; then
            visitor_ap_iface="pb-ap"
        else
            visitor_ap_iface=$(printf '%s\n' "$ap_ifaces" | head -n1)
        fi
    fi
    if [ "$visitor_ap_iface" = "pb-ap" ]; then
        visitor_ap_provider="external"
    elif [ -n "$visitor_ap_iface" ]; then
        visitor_ap_provider="onboard"
    fi
fi

# --- Wi-Fi client count (associated stations on the visitor AP) ---
# current_stations holds this poll's raw MAC list, sorted - needed
# transiently below to detect new associations. It is never written
# anywhere except the tmpfs scratch file that immediately replaces the
# previous poll's copy.
current_stations=""
wifi_clients=0
if [ -n "$visitor_ap_iface" ]; then
    current_stations=$(iw dev "$visitor_ap_iface" station dump 2>/dev/null | awk '/^Station/ {print $2}' | sort)
    wifi_clients=$(printf '%s\n' "$current_stations" | grep -c . || true)
fi

# --- Connection event tracking (privacy-preserving, see header) ---
# A MAC present in this poll but absent from the immediately-preceding
# poll counts as one connection event. Reconnects (Wi-Fi sleep/wake,
# walking in and out of range) count again each time - this is a
# "connection events" metric, not a count of distinct people or devices.
new_events=0
if [ -f "$PREV_STATIONS_FILE" ]; then
    prev_stations=$(cat "$PREV_STATIONS_FILE" 2>/dev/null || true)
    new_events=$(comm -23 <(printf '%s\n' "$current_stations") <(printf '%s\n' "$prev_stations") | grep -c . || true)
else
    # First successful poll since boot/helper (re)start - no previous
    # snapshot exists to compare against. Treat this as initialization
    # only: seed the snapshot below and count zero events this poll,
    # rather than counting every already-connected station as "new" just
    # because the helper itself (re)started. Comparison begins for real
    # on the next poll.
    new_events=0
fi
printf '%s\n' "$current_stations" > "$PREV_STATIONS_FILE"

# In-progress hour's running count/peak, kept only in tmpfs. Flushed to
# the SD card (as a completed, immutable hourly bucket) only when the
# wall-clock hour actually rolls over - see the header comment above
# for the storage-wear/durability tradeoff this implies.
now_epoch=$(date +%s)
hour_start=$(( (now_epoch / 3600) * 3600 ))

scratch_hour=0
scratch_count=0
scratch_peak=0
if [ -f "$HOUR_SCRATCH_FILE" ]; then
    read -r scratch_hour scratch_count scratch_peak < "$HOUR_SCRATCH_FILE" 2>/dev/null || true
fi
scratch_hour=${scratch_hour:-0}
scratch_count=${scratch_count:-0}
scratch_peak=${scratch_peak:-0}

if [ "$scratch_hour" != "$hour_start" ]; then
    # The hour has rolled over since the last poll (or this is the very
    # first poll ever, in which case scratch_hour is still its default
    # 0 and there is nothing yet to flush). Persist the just-completed
    # hour's totals - count AND peak, so a genuine rolling-24h peak can
    # be computed later - before starting a fresh in-progress hour.
    if [ "$scratch_hour" != "0" ]; then
        python3 - "$CONN_STATS_FILE" "$scratch_hour" "$scratch_count" "$scratch_peak" <<'PYEOF' || true
import json
import os
import sys
import time

path, hour_start, count, peak = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])

data = {"hourly": []}
try:
    with open(path, encoding="utf-8") as f:
        loaded = json.load(f)
    if isinstance(loaded, dict) and isinstance(loaded.get("hourly"), list):
        data = loaded
except Exception:
    # Missing, unreadable, or corrupt - start fresh rather than fail.
    # This is best-effort aggregate statistics, never load-bearing.
    pass

hourly = [b for b in data.get("hourly", []) if isinstance(b, dict) and "hour_start" in b]
# Replace any existing bucket for this hour rather than duplicating it -
# keeps this idempotent if the helper is ever re-run for the same hour.
hourly = [b for b in hourly if b.get("hour_start") != hour_start]
hourly.append({"hour_start": hour_start, "count": count, "peak": peak})

# Keep only the last 25 hours of buckets - one hour of slack over the
# 24h window this feeds, so it never grows unbounded and never needs a
# separate pruning pass.
cutoff = hour_start - 25 * 3600
hourly = [b for b in hourly if b.get("hour_start", 0) >= cutoff]
hourly.sort(key=lambda b: b["hour_start"])

out = {"hourly": hourly, "updated_at": int(time.time())}

tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(out, f)
os.chmod(tmp, 0o644)
os.replace(tmp, path)
PYEOF
    fi
    scratch_hour="$hour_start"
    scratch_count=0
    scratch_peak=0
fi

scratch_count=$(( scratch_count + new_events ))
if [ "$wifi_clients" -gt "$scratch_peak" ]; then
    scratch_peak=$wifi_clients
fi
printf '%s %s %s\n' "$scratch_hour" "$scratch_count" "$scratch_peak" > "$HOUR_SCRATCH_FILE"

# --- Service health ---
json_bool() { if [ "$1" = "active" ]; then echo true; else echo false; fi; }

hostapd_state=$(systemctl is-active hostapd 2>/dev/null || true)
dnsmasq_state=$(systemctl is-active dnsmasq 2>/dev/null || true)
nginx_state=$(systemctl is-active nginx 2>/dev/null || true)
phpfpm_state=$(systemctl is-active php8.4-fpm 2>/dev/null || true)

# Optional/physical hardware daemons - deliberately reported separately
# from the "services" block above, not folded into it: those four are
# all Core-dependency services, while the OLED daemon is an optional,
# non-Core capability (docs/ARCHITECTURE.md §2, docs/CAPABILITY-
# REGISTRY.md's "oled" entry). Mixing them into one list would make a
# missing/unplugged OLED look like a Core outage to anything summing
# the "services" object. "active" here means the systemd unit itself is
# running - it does not confirm the display is physically present and
# responding (the daemon's own retry loop handles that; see
# piratebox_oled_daemon.py's header for why a running-but-retrying
# daemon is the correct honest state when the display is unplugged).
oled_service_state=$(systemctl is-active piratebox-oled 2>/dev/null || true)

# --- Undervoltage / throttling status (Raspberry Pi specific) ---
throttled_hex="unavailable"
undervoltage_now=false
undervoltage_since_boot=false
if command -v vcgencmd >/dev/null 2>&1; then
    raw=$(vcgencmd get_throttled 2>/dev/null || true)
    # Expected form: throttled=0x50000
    throttled_hex=$(echo "$raw" | sed -n 's/^throttled=//p')
    if [ -n "$throttled_hex" ]; then
        val=$((throttled_hex))
        # Bit 0: under-voltage now. Bit 16: under-voltage has occurred since boot.
        if (( val & 0x1 )); then undervoltage_now=true; fi
        if (( val & 0x10000 )); then undervoltage_since_boot=true; fi
    else
        throttled_hex="unavailable"
    fi
fi

# --- Device memory: bounded operational event history (docs/DEVICE-
# MEMORY-DESIGN.md) ---
# "Prefer current-state awareness over historical surveillance, but
# retain enough history for the operator to understand what happened
# while unattended." Two Operational-History-class events, chosen
# because they're the two this project's own docs already flagged as
# useful for a since-last-review summary and are cheap to detect
# correctly: boot events (uptime resetting lower than last poll means a
# reboot happened) and undervoltage-onset events (edge-triggered, same
# discipline connection-stats already uses for "new" vs. "still
# connected"). Only small integers + timestamps ever persist - no raw
# per-second telemetry, matching docs/DEVICE-MEMORY-DESIGN.md §5's
# aggregation-over-raw-samples principle. Bounded by count (boot
# events) or a fixed day window (undervoltage), never unbounded.
DEVICE_HISTORY_FILE="/var/www/html/data/device-history.json"
DEVMEM_SCRATCH_FILE="$OUT_DIR/devmem-scratch"

uptime_now=0
if [ -r /proc/uptime ]; then
    uptime_now=$(awk '{print int($1)}' /proc/uptime 2>/dev/null || echo 0)
fi

prev_uptime=0
prev_undervoltage=false
if [ -f "$DEVMEM_SCRATCH_FILE" ]; then
    read -r prev_uptime prev_undervoltage < "$DEVMEM_SCRATCH_FILE" 2>/dev/null || true
fi
prev_uptime=${prev_uptime:-0}
prev_undervoltage=${prev_undervoltage:-false}

# A reboot happened since the last poll if uptime is now LOWER than it
# was last poll (uptime only ever increases within one boot). The very
# first poll ever (no scratch file yet) is NOT counted as a boot event -
# it would just be recording that the helper started, not that the
# device rebooted.
boot_event=false
if [ -f "$DEVMEM_SCRATCH_FILE" ] && [ "$uptime_now" -lt "$prev_uptime" ]; then
    boot_event=true
fi

# Undervoltage EVENT = the moment it turns on (false -> true), not every
# poll it happens to still be true - same "new, not still" distinction
# connection-stats already draws for MAC associations.
undervoltage_event=false
if [ "$undervoltage_now" = "true" ] && [ "$prev_undervoltage" != "true" ]; then
    undervoltage_event=true
fi

printf '%s %s\n' "$uptime_now" "$undervoltage_now" > "$DEVMEM_SCRATCH_FILE"

if [ "$boot_event" = "true" ] || [ "$undervoltage_event" = "true" ]; then
    python3 - "$DEVICE_HISTORY_FILE" "$boot_event" "$undervoltage_event" <<'PYEOF' || true
import json
import os
import sys
import time

path, boot_event, undervoltage_event = sys.argv[1], sys.argv[2] == "true", sys.argv[3] == "true"
now = int(time.time())

data = {"boot_events": [], "undervoltage_daily": [], "history_started_at": now}
try:
    with open(path, encoding="utf-8") as f:
        loaded = json.load(f)
    if isinstance(loaded, dict):
        data = loaded
        data.setdefault("boot_events", [])
        data.setdefault("undervoltage_daily", [])
        data.setdefault("history_started_at", now)
except Exception:
    # Missing, unreadable, or corrupt - start fresh rather than fail.
    # Best-effort aggregate history, never load-bearing for Core.
    pass

if boot_event:
    events = [e for e in data["boot_events"] if isinstance(e, int)]
    events.append(now)
    # Bounded by count, not time - a fixed cap keeps this small even if
    # the device reboots unusually often, without needing a time-based
    # prune pass for something that isn't naturally hourly/daily.
    data["boot_events"] = events[-50:]

if undervoltage_event:
    day_start = (now // 86400) * 86400
    daily = [d for d in data["undervoltage_daily"] if isinstance(d, dict) and "day_start" in d]
    daily = [d for d in daily if d.get("day_start") != day_start] + [
        {"day_start": day_start, "count": next((d["count"] for d in daily if d.get("day_start") == day_start), 0) + 1}
    ]
    # Bounded to a fixed ~90-day window - daily granularity is plenty for
    # a "since last review" summary spanning weeks/months (unlike
    # connection stats' 24h-focused hourly buckets), and stays compact.
    cutoff = day_start - 90 * 86400
    daily = [d for d in daily if d.get("day_start", 0) >= cutoff]
    daily.sort(key=lambda d: d["day_start"])
    data["undervoltage_daily"] = daily

data["updated_at"] = now

tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f)
os.chmod(tmp, 0o644)
os.replace(tmp, path)
PYEOF
fi

# --- Progression public export (Captain's Log web page) ---
# piratebox_progression.py's durable store (/var/lib/piratebox-oled/
# progression.json) is deliberately root:piratebox-gpio-only (see that
# file's own "Web profile export" section and etc/tmpfiles.d's comment)
# - www-data cannot read it, and per instruction that permission is not
# to be loosened just to serve a web page. This script already runs as
# root on a fixed schedule for exactly this class of problem (see this
# file's own header), so it's the natural bridge: invoke
# piratebox_progression.py directly (root can always read a 0640 file
# regardless of group), which prints ONLY the already-curated,
# spoiler-safe public summary (see that file's build_public_summary())
# as JSON - never the raw progression.json - to
# /run/piratebox/progression-public.json (world-readable tmpfs, same
# pattern as status.json itself). Missing/uninstalled/failing
# gracefully skips this block entirely - a public export lagging or
# absent must never affect this script's own primary job (status.json)
# or the OLED/network stack in any way.
PROGRESSION_HELPER="/usr/local/bin/piratebox_progression.py"
PROGRESSION_PUBLIC_FILE="$OUT_DIR/progression-public.json"
if [ -x "$PROGRESSION_HELPER" ] || [ -f "$PROGRESSION_HELPER" ]; then
    PROGRESSION_TMP="$PROGRESSION_PUBLIC_FILE.tmp.$$"
    if python3 "$PROGRESSION_HELPER" > "$PROGRESSION_TMP" 2>/dev/null \
        && python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$PROGRESSION_TMP" >/dev/null 2>&1; then
        chmod 0644 "$PROGRESSION_TMP"
        mv -f "$PROGRESSION_TMP" "$PROGRESSION_PUBLIC_FILE"
    else
        rm -f "$PROGRESSION_TMP" 2>/dev/null || true
    fi
fi

# --- Time source (Field Tools, Post-Stage-32) ---
# PHP-FPM's open_basedir (etc/php/8.4/fpm/php.ini) deliberately does not
# include /sys/class/rtc, /run/systemd/timesync, or /etc/fake-hwclock.data
# - the same security boundary that's the whole reason this script exists
# (see this file's own header). This runs as root with no such
# restriction, so it does the read and publishes the result here instead -
# see includes/fieldtools_time.php's piratebox_get_time_source_status(),
# which reads this block rather than touching those paths directly.
rtc_detected=false
if ls /sys/class/rtc/rtc* >/dev/null 2>&1; then rtc_detected=true; fi
ntp_synchronized=false
if [ -f /run/systemd/timesync/synchronized ]; then ntp_synchronized=true; fi
fake_hwclock_installed=false
if [ -f /etc/fake-hwclock.data ]; then fake_hwclock_installed=true; fi

# --- Admin panel auth readiness ---
# /etc/nginx/.piratebox_admin_htpasswd is outside PHP-FPM's open_basedir
# for the same reason as the block above - it's root:www-data 0640, so
# www-data COULD read it (group permission), but it isn't in the
# open_basedir allowlist, so a direct PHP read is blocked regardless.
# This runs as root with no such restriction, so it does the read here.
# Only a boolean (configured or not) is ever published - never the
# file's content, never a username, never anything password-related.
# See includes/capability_state.php's 'admin_panel' entry and
# setup_admin_password.sh (the one place this file is ever written).
ADMIN_HTPASSWD_FILE="/etc/nginx/.piratebox_admin_htpasswd"
admin_auth_configured=false
if [ -s "$ADMIN_HTPASSWD_FILE" ]; then admin_auth_configured=true; fi

cat > "$TMP_FILE" <<EOF
{
  "generated_at": $(date +%s),
  "wifi_clients": $wifi_clients,
  "services": {
    "hostapd": $(json_bool "$hostapd_state"),
    "dnsmasq": $(json_bool "$dnsmasq_state"),
    "nginx": $(json_bool "$nginx_state"),
    "php8.4-fpm": $(json_bool "$phpfpm_state")
  },
  "power": {
    "throttled_hex": "$throttled_hex",
    "undervoltage_now": $undervoltage_now,
    "undervoltage_since_boot": $undervoltage_since_boot
  },
  "connections": {
    "current_hour_start": $scratch_hour,
    "current_hour_count": $scratch_count,
    "current_hour_peak": $scratch_peak
  },
  "time_source": {
    "rtc_detected": $rtc_detected,
    "ntp_synchronized": $ntp_synchronized,
    "fake_hwclock_installed": $fake_hwclock_installed
  },
  "admin_auth": {
    "configured": $admin_auth_configured
  },
  "hardware": {
    "oled_service_active": $(json_bool "$oled_service_state")
  },
  "visitor_ap": {
    "interface": $([ -n "$visitor_ap_iface" ] && echo "\"$visitor_ap_iface\"" || echo null),
    "provider": "$visitor_ap_provider",
    "multiple_ap_interfaces_warning": $visitor_ap_multiple_warning
  }
}
EOF

chmod 0644 "$TMP_FILE"
mv -f "$TMP_FILE" "$OUT_FILE"
