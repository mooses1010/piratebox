#!/bin/bash
#
# One-time (per board) factory firmware backup for the commissioned
# ESP32-S3-N16R8, taken BEFORE the first custom flash ever overwrites
# it. See docs/ESP32-SUPERVISOR-DESIGN.md §11 for the full rationale.
#
# Reads the full 16MB flash image over the proven COM-port connection
# (docs/OPERATIONAL-DECISIONS.md, 2026-09-07 commissioning).
#
# USES PLATFORMIO'S BUNDLED esptool, NOT the system/apt one, and NOT
# --no-stub: the Debian-packaged esptool (4.7.0+dfsg-0.1) is missing
# its ESP32-S3 stub-flasher JSON file (fine for the small read-only
# identification commands used during commissioning, which all used
# --no-stub successfully) but --no-stub's ROM-only transfer proved
# UNRELIABLE for a full 16MB read on real hardware - two attempts each
# failed with "Serial data stream stopped: Possible serial noise or
# corruption" at different points (~1-6% in), never harming the board
# (read-only, and it stayed enumerated throughout both failures).
# PlatformIO's own bundled esptool (~/.platformio/packages/
# tool-esptoolpy/) ships the complete stub-flasher files this exact
# chip needs, so a full stub-mode read completes reliably. A full 16MB
# read still takes several minutes even with the stub; that's expected.
#
# Deliberately NOT stored inside the git tree - a 16MB binary blob does
# not belong in commit history. Stored under
# ~/piratebox-esp32-firmware-backups/ (a NEW, dedicated directory -
# NOT ~/piratebox-backups/, which already has an established, different
# meaning: pre-stage code/site snapshots for dev rollback, per
# CLAUDE.md).
#
# Run with: ./tools/backup_esp32_factory_firmware.sh
# (no sudo needed - the same unprivileged serial access already used
# for every esptool command this session)

set -euo pipefail

TOOLCHAIN_PYTHON="$HOME/.venvs/esp32-toolchain/bin/python3"
BUNDLED_ESPTOOL="$HOME/.platformio/packages/tool-esptoolpy/esptool.py"
if [ ! -x "$TOOLCHAIN_PYTHON" ] || [ ! -f "$BUNDLED_ESPTOOL" ]; then
    echo "ERROR: PlatformIO toolchain/bundled esptool not found - see" >&2
    echo "docs/ESP32-SUPERVISOR-DESIGN.md §2/§12 for the one-time setup." >&2
    exit 1
fi

BACKUP_DIR="$HOME/piratebox-esp32-firmware-backups"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="$BACKUP_DIR/esp32s3-n16r8-factory-${TIMESTAMP}.bin"
FLASH_SIZE_BYTES=$((16 * 1024 * 1024))
KNOWN_SERIAL="5CBB028993"
EXPECTED_DEV="/dev/serial/by-id/usb-1a86_USB_Single_Serial_${KNOWN_SERIAL}-if00"

mkdir -p "$BACKUP_DIR"

if [ ! -e "$EXPECTED_DEV" ]; then
    echo "ERROR: expected device not found: $EXPECTED_DEV" >&2
    echo "This board's known WCH bridge serial ($KNOWN_SERIAL) isn't present." >&2
    echo "Refusing to guess a different tty device for a factory backup." >&2
    ls -la /dev/serial/by-id/ 2>&1 >&2 || true
    exit 1
fi

echo "== Backing up factory flash from $EXPECTED_DEV (16MB, stub-mode, 460800 baud) =="
echo "NOTE: this esptool build buffers the ENTIRE read in memory and writes the"
echo "output file in one shot at the very end - the .bin file will NOT appear on"
echo "disk, or grow, until the read reaches 100%% and completes. Absence of the"
echo "file mid-run is normal, not a hang - watch the percentage progress printed"
echo "below (or the process's own CPU usage) instead of the destination file."
"$TOOLCHAIN_PYTHON" "$BUNDLED_ESPTOOL" -b 460800 -p "$EXPECTED_DEV" read_flash 0 "$FLASH_SIZE_BYTES" "$OUT_FILE"

echo
echo "== Verifying the backup is a real, non-trivial image =="
ACTUAL_SIZE=$(stat -c %s "$OUT_FILE")
if [ "$ACTUAL_SIZE" -ne "$FLASH_SIZE_BYTES" ]; then
    echo "ERROR: backup size ($ACTUAL_SIZE bytes) does not match expected flash size ($FLASH_SIZE_BYTES bytes)." >&2
    exit 1
fi

# Sanity check: a genuine factory image should not be all-0x00 or
# all-0xFF (both patterns a botched/erased read would produce). Sample
# the first 4KB rather than hashing the whole 16MB for this quick check.
HEAD_HEX=$(head -c 4096 "$OUT_FILE" | xxd -p | tr -d '\n')
if [[ "$HEAD_HEX" =~ ^(00)+$ ]] || [[ "$HEAD_HEX" =~ ^(ff)+$ ]]; then
    echo "ERROR: first 4KB of the backup is uniformly 0x00 or 0xFF - this does not" >&2
    echo "look like a real factory image. NOT trusting this backup." >&2
    exit 1
fi

sha256sum "$OUT_FILE" | tee "${OUT_FILE}.sha256"

echo
echo "Factory firmware backup verified and saved:"
echo "  $OUT_FILE"
echo
echo "To restore it later (full factory reset of this exact board):"
echo "  $TOOLCHAIN_PYTHON $BUNDLED_ESPTOOL -p $EXPECTED_DEV write_flash 0 $OUT_FILE"
