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

set -euo pipefail

OUT_DIR="/run/piratebox"
OUT_FILE="$OUT_DIR/status.json"
TMP_FILE="$OUT_FILE.tmp.$$"

mkdir -p "$OUT_DIR"
chmod 0755 "$OUT_DIR"

# --- Wi-Fi client count (associated stations on wlan0) ---
wifi_clients=0
if command -v iw >/dev/null 2>&1 && ip link show wlan0 >/dev/null 2>&1; then
    wifi_clients=$(iw dev wlan0 station dump 2>/dev/null | grep -c '^Station' || true)
fi

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
  }
}
EOF

chmod 0644 "$TMP_FILE"
mv -f "$TMP_FILE" "$OUT_FILE"
