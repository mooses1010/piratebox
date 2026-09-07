#!/usr/bin/env python3
"""
Standalone BH1750 ambient light sensor diagnostic (2026-09-07,
docs/HARDWARE-INTEGRATION-DESIGN.md). Answers exactly the questions
operational diagnostics need to answer for this sensor:

  - Is a BH1750 installed / responding?
  - What lux value is it currently reporting?
  - When was the last successful reading (staleness)?
  - Are the OLED/RTC/EEPROM - this sensor's I2C bus neighbors -
    still healthy? (regression check, same discipline as
    tools/diagnose_rtc_ds3231.sh)

Needs NO sudo/root: /dev/i2c-1 is group-readable/writable by the `i2c`
group, which the interactive operator account is already a member of
(confirmed during the original OLED bring-up) - this is a genuinely
lower-privilege check than the RTC's own diagnostic script, which needs
root only because /dev/rtc0 itself is root-only.

Run directly:

    python3 tools/diagnose_bh1750.py

This performs REAL I2C writes to the sensor (the BH1750 protocol has
no way to "just read" without first commanding a measurement - see
piratebox_bh1750.py's own header) but touches no config file, no
service, and no other device on the bus - it is safe to run at any
time, including while piratebox-oled.service is also running (both
can share the bus; the daemon's own reader is separately rate-limited,
see that module's header).
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_bh1750  # noqa: E402 - path insert must happen first


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
    except Exception as exc:  # noqa: BLE001
        return f"(failed to run {cmd!r}: {exc})"


def main():
    print("=== BH1750 direct read (bypassing the daemon's own rate limiter) ===")
    try:
        lux = round(piratebox_bh1750._read_raw_lux(), 1)
        print(f"lux = {lux}  (address 0x{piratebox_bh1750.ADDRESS:02x}, i2c bus {piratebox_bh1750.I2C_BUS})")
        detected = True
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {type(exc).__name__}: {exc}")
        detected = False

    print()
    print("=== Reader diagnostics (as the daemon would see it after a real read) ===")
    piratebox_bh1750.read_ambient_lux()  # populate the module's own cache/diagnostics
    diag = piratebox_bh1750.get_diagnostics()
    for k, v in diag.items():
        print(f"  {k}: {v}")

    print()
    print("=== I2C bus - confirms the OLED/EEPROM/RTC neighbors are unaffected ===")
    print(run(["i2cdetect", "-y", "1"]))

    print("=== OLED service ===")
    print(run(["systemctl", "is-active", "piratebox-oled.service"]).strip())

    print()
    if detected:
        print("BH1750: DETECTED and responding.")
    else:
        print("BH1750: NOT detected / not responding - check wiring "
              "(VCC->3.3V, GND->GND, SDA/SCL on the shared I2C bus, "
              "ADDR left unconnected) before assuming a software issue.")


if __name__ == "__main__":
    main()
