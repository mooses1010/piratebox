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

set -euo pipefail

OUT_DIR="/run/piratebox"
OUT_FILE="$OUT_DIR/status.json"
TMP_FILE="$OUT_FILE.tmp.$$"
PREV_STATIONS_FILE="$OUT_DIR/prev-stations"
HOUR_SCRATCH_FILE="$OUT_DIR/hour-scratch"
CONN_STATS_FILE="/var/www/html/data/connection-stats.json"

mkdir -p "$OUT_DIR"
chmod 0755 "$OUT_DIR"

# --- Wi-Fi client count (associated stations on wlan0) ---
# current_stations holds this poll's raw MAC list, sorted - needed
# transiently below to detect new associations. It is never written
# anywhere except the tmpfs scratch file that immediately replaces the
# previous poll's copy.
current_stations=""
wifi_clients=0
if command -v iw >/dev/null 2>&1 && ip link show wlan0 >/dev/null 2>&1; then
    current_stations=$(iw dev wlan0 station dump 2>/dev/null | awk '/^Station/ {print $2}' | sort)
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
  }
}
EOF

chmod 0644 "$TMP_FILE"
mv -f "$TMP_FILE" "$OUT_FILE"
