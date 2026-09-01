#!/bin/bash
#
# Generates this PirateBox's public random device ID (Stage 16).
#
# The ID is PURELY RANDOM - drawn from /dev/urandom, NOT derived from any
# hardware identifier (no MAC address, Pi serial, storage serial, hostname,
# username, or IP). It's meant to be a persistent, non-sensitive label a
# finder or the operator can reference (About page, Found Device page, a
# future physical label/OLED screen) without exposing anything about the
# actual hardware.
#
# Format: PB-XXXX-XX (example only - not a real generated ID)
# Alphabet excludes easily-confused characters (0/O, 1/I/L) so a device ID
# read off a label or a phone screen is easy to type back in correctly.
#
# Run ONCE per physical device: sudo or plain ./tools/generate_device_id.sh
# Deliberately refuses to overwrite an existing ID unless --force is given,
# so cloning this SD card for a second physical unit doesn't silently leave
# both units sharing the same ID - regenerate explicitly on the clone
# instead.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_PATH="$REPO_DIR/var/www/html/data/device-id.json"
ALPHABET="23456789ABCDEFGHJKMNPQRSTUVWXYZ"

if [ -f "$OUT_PATH" ] && [ "${1:-}" != "--force" ]; then
    echo "A device ID already exists at $OUT_PATH:" >&2
    grep '"id"' "$OUT_PATH" >&2 || true
    echo "Refusing to overwrite it. Pass --force to regenerate (e.g. when cloning this SD card for a NEW physical device)." >&2
    exit 1
fi

random_chars() {
    local count="$1"
    local out=""
    local alphabet_len=${#ALPHABET}
    while [ ${#out} -lt "$count" ]; do
        byte=$(od -An -tu1 -N1 /dev/urandom | tr -d ' ')
        idx=$((byte % alphabet_len))
        out="${out}${ALPHABET:$idx:1}"
    done
    echo "$out"
}

PART1=$(random_chars 4)
PART2=$(random_chars 2)
DEVICE_ID="PB-${PART1}-${PART2}"
GENERATED_AT=$(date '+%Y-%m-%d %H:%M:%S')

mkdir -p "$(dirname "$OUT_PATH")"
cat > "$OUT_PATH" <<EOF
{
  "id": "$DEVICE_ID",
  "generated_at": "$GENERATED_AT",
  "generation_method": "random (/dev/urandom via tools/generate_device_id.sh) - not derived from any hardware identifier"
}
EOF

echo "Generated device ID: $DEVICE_ID"
echo "Written to: $OUT_PATH"
