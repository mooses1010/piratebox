#!/usr/bin/env python3
#
# Sensor-history sampler (2026-09-08) - the ONLY thing that decides
# "is this reading valid to record right now", and the ONLY caller of
# piratebox_history.record_sample(). Run as a oneshot systemd service,
# triggered by piratebox-history-sample.timer every ~5 minutes (see
# etc/systemd/system/) - NOT a long-running daemon (this project
# already has two of those - the ESP32 supervisor and the OLED daemon -
# and a third, always-running process for something this infrequent
# would be pure overhead; a timer-triggered oneshot is the same pattern
# piratebox-status.timer already uses).
#
# INTRODUCES NO NEW SENSOR POLLING: reads ONLY piratebox_esp32_client.
# get_diagnostics() - the exact same already-cached export every other
# consumer (the Environment page, the admin capability table, the OLED
# daemon) already reads. This process never opens a serial port, I2C
# bus, or 1-Wire bus - piratebox_esp32_supervisor.py remains the sole
# hardware owner (see that daemon's own header for why).
#
# VALIDITY, using the SAME shared classifiers the admin capability
# table and OLED daemon already use (piratebox_hardware_health.py) -
# no separate/competing notion of "is this sensor healthy" is invented
# here: only a signal currently classified AVAILABLE is recorded. This
# is what makes "stale/invalid/85C-init/CRC-failed/disconnected never
# recorded" true for free - piratebox_hardware_health.classify_
# simple_sensor()/classify_ds18b20_bus() and the firmware's own ok=false
# handling (esp32-firmware/src/ds18b20.cpp) already reject exactly those
# cases upstream of this script ever seeing a value.
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

import piratebox_esp32_client as client  # noqa: E402
import piratebox_hardware_health as health  # noqa: E402
import piratebox_history as history  # noqa: E402

# Signal ids sampled from a flat {ok,value,unit} export shape - see
# piratebox_hardware_health.classify_simple_sensor()'s own docstring
# for the shape this assumes. Adding a future sensor of this same shape
# (a BME280 field, an INA226 field) means adding one entry here -
# nothing else in this module, piratebox_history.py, or the query/UI
# layer needs to change.
SIMPLE_SIGNALS = [
    ("bh1750", "ambient_lux"),
    ("temp_internal", "esp32_temp_internal"),
]


def sample_once(now: float = None) -> dict:
    """Reads the current diagnostics once, decides validity per signal,
    records every currently-valid one. Returns a small summary dict
    (never raises) - {"recorded": [...], "skipped": [...]} - so the
    caller can log a concise, honest line without either side needing
    to re-derive what happened."""
    now = now if now is not None else time.time()
    diag = client.get_diagnostics()
    recorded = []
    skipped = []

    for capability, signal_id in SIMPLE_SIGNALS:
        state = health.classify_simple_sensor(diag, capability)
        if state != "AVAILABLE":
            skipped.append((signal_id, state))
            continue
        reading = diag.get("sensors", {}).get(capability)
        value = reading.get("value") if isinstance(reading, dict) else None
        if not isinstance(value, (int, float)):
            skipped.append((signal_id, "no_value"))
            continue
        if history.record_sample(signal_id, now, value):
            recorded.append(signal_id)
        else:
            skipped.append((signal_id, "gap_guard"))

    ds18b20 = diag.get("sensors", {}).get("ds18b20")
    commissioned = ds18b20.get("commissioned") if isinstance(ds18b20, dict) else None
    commissioned_roms = set(commissioned.keys()) if isinstance(commissioned, dict) else set()
    probes = ds18b20.get("probes") if isinstance(ds18b20, dict) else {}
    probes = probes if isinstance(probes, dict) else {}

    for rom in commissioned_roms:
        signal_id = history.ds18b20_signal_id(rom)
        reading = probes.get(rom)
        # Per-probe validity: the reading must actually be present AND
        # ok this cycle - a commissioned probe that's temporarily
        # missing/failing is exactly the "gap" case (see module header),
        # never a fabricated/carried-forward value. The firmware itself
        # (esp32-firmware/src/ds18b20.cpp) already refuses to report
        # ok=true for a disconnected probe, a CRC failure, or the
        # 85C power-on/uninitialized-scratchpad sentinel value - this
        # script trusts that upstream validation rather than
        # re-implementing it.
        if not (isinstance(reading, dict) and reading.get("ok") is True):
            skipped.append((signal_id, "not_ok"))
            continue
        value = reading.get("value")
        if not isinstance(value, (int, float)):
            skipped.append((signal_id, "no_value"))
            continue
        if history.record_sample(signal_id, now, value):
            recorded.append(signal_id)
        else:
            skipped.append((signal_id, "gap_guard"))

    return {"recorded": recorded, "skipped": skipped}


def main() -> int:
    result = sample_once()
    print(f"history sampler: recorded {len(result['recorded'])} signal(s) "
          f"({', '.join(result['recorded']) or 'none'}); "
          f"{len(result['skipped'])} skipped.")
    for signal_id, reason in result["skipped"]:
        print(f"  skipped {signal_id}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
