# PirateBox ESP32-S3 supervisor firmware

Full design, protocol spec, and rationale: **`../docs/ESP32-SUPERVISOR-DESIGN.md`**.
Build/commissioning history and real-hardware evidence: **`../docs/OPERATIONAL-DECISIONS.md`**.

## Quick start

One-time toolchain setup (isolated venv, no sudo, no system package changes):

```sh
python3 -m venv ~/.venvs/esp32-toolchain
~/.venvs/esp32-toolchain/bin/pip install platformio
```

Build:

```sh
~/.venvs/esp32-toolchain/bin/pio run
```

Build + flash (use the safety-checked wrapper instead of raw `pio run -t
upload` - it verifies the expected device before writing anything):

```sh
../tools/flash_esp32_supervisor.sh
```

Connect via the board's **"COM"** USB-C port (not "USB") - see the
design doc §4 for why that distinction matters on this chip.
