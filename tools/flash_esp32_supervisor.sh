#!/bin/bash
#
# Safe build+flash for the ESP32-S3 hardware/sensor supervisor firmware.
# See docs/ESP32-SUPERVISOR-DESIGN.md for the full design and §11 for
# the deployment-safety rationale this script implements:
#   - identifies the expected device BEFORE flashing anything (refuses
#     to guess/flash an unrelated tty device)
#   - reports failures clearly
#   - verifies the device comes back afterward
#
# Requires the PlatformIO toolchain already set up at
# ~/.venvs/esp32-toolchain (see docs/ESP32-SUPERVISOR-DESIGN.md §2/§12).
#
# Run with: ./tools/flash_esp32_supervisor.sh
# (no sudo needed)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIRMWARE_DIR="$REPO_DIR/esp32-firmware"
PIO="$HOME/.venvs/esp32-toolchain/bin/pio"
KNOWN_SERIAL="5CBB028993"
EXPECTED_DEV="/dev/serial/by-id/usb-1a86_USB_Single_Serial_${KNOWN_SERIAL}-if00"

if [ ! -x "$PIO" ]; then
    echo "ERROR: PlatformIO not found at $PIO - see docs/ESP32-SUPERVISOR-DESIGN.md §2/§12" \
         "for the one-time toolchain setup." >&2
    exit 1
fi

if [ ! -e "$EXPECTED_DEV" ]; then
    echo "ERROR: expected device not found: $EXPECTED_DEV" >&2
    echo "This board's known WCH bridge serial ($KNOWN_SERIAL) isn't present." >&2
    echo "Refusing to flash an unrelated/guessed tty device." >&2
    echo "If this board's bridge was intentionally swapped, update KNOWN_SERIAL" >&2
    echo "here AND in piratebox_esp32_supervisor.py's KNOWN_BRIDGE_SERIAL." >&2
    ls -la /dev/serial/by-id/ 2>&1 >&2 || true
    exit 1
fi

echo "== Target device confirmed: $EXPECTED_DEV =="
echo
echo "== Building =="
(cd "$FIRMWARE_DIR" && "$PIO" run)

echo
echo "== Flashing via $EXPECTED_DEV =="
(cd "$FIRMWARE_DIR" && "$PIO" run -t upload --upload-port "$EXPECTED_DEV")

echo
echo "== Waiting for the device to re-enumerate after reset =="
for i in $(seq 1 15); do
    if [ -e "$EXPECTED_DEV" ]; then
        echo "  device present after ${i}s."
        break
    fi
    sleep 1
done

if [ ! -e "$EXPECTED_DEV" ]; then
    echo "WARNING: $EXPECTED_DEV did not reappear within 15s after flashing." >&2
    echo "Check the physical connection (COM port, externally powered hub -" >&2
    echo "see docs/OPERATIONAL-DECISIONS.md) before assuming a firmware problem." >&2
    exit 1
fi

echo
echo "Flash complete. Run 'python3 tools/diagnose_esp32_supervisor.py' (with the"
echo "daemon running) or 'screen $EXPECTED_DEV 115200' to confirm the new firmware"
echo "is talking correctly."
