# ESP32-S3 Hardware/Sensor Supervisor — Design

**Status: WORKING IMPLEMENTATION with a first real sensor migrated
(2026-09-07).** BH1750 ambient light is now live on the ESP32's own
I2C bus (§16) — no longer Pi-owned. The board was
commissioned (identity fully proven read-only via `esptool`) earlier
the same day — see `docs/OPERATIONAL-DECISIONS.md`'s two commissioning
entries and `docs/CAPABILITY-REGISTRY.md`'s "Remote microcontroller/
sensor node" row for that history. This document covers everything
built on top of that commissioned hardware: the firmware, the Pi-side
daemon, the wire protocol between them, and the architectural boundary
between the two computers. Read this file fully before touching either
side — it routes to the concrete source files rather than duplicating
their comments.

## 1. Role and boundary

The Raspberry Pi remains PirateBox's high-level computer: web UI,
storage, Wi-Fi AP/networking, SDR, progression, OLED UI, application
logic, durable user-facing data. **None of that moves to the ESP32.**

The ESP32-S3 is a **dedicated low-level hardware/sensor supervisor** —
a real-time-capable microcontroller that owns direct sensor/GPIO access
the Pi doesn't need to (and, for timing-sensitive future work like
1-Wire probes or a power-monitoring watchdog, shouldn't) do itself. Its
role is expected to grow to include environmental sensors, temperature
probes, electrical/power telemetry, physical controls, hardware
health/heartbeat, and eventually safe-shutdown cooperation — but only
as each is actually built and validated, never claimed in advance.

**Classification correction:** `docs/CAPABILITY-REGISTRY.md` previously
listed this board as "Network Companion (pending re-evaluation — board
connects via USB, not LAN)". Per `docs/ARCHITECTURE.md` §3's own
taxonomy, a device connected over "USB/serial/GPIO" is explicitly an
**Attachable** capability, not a Network Companion (which means
independently powered, communicating over the LAN). This board is
USB/serial-attached and, in its current prototype topology, actually
draws power *through* that same USB connection (via the externally
powered hub) rather than being independently powered — Attachable is
the correct classification. Updated in the registry alongside this
document.

**The device-independence test still applies** (`docs/ARCHITECTURE.md`
§3): unplug the ESP32 and PirateBox Core is completely unaffected — no
Core service depends on it, nothing here touches hostapd/dnsmasq/nginx/
php-fpm/OLED/RTC/BH1750's own existing operation. Unplug the Pi and the
ESP32 keeps running its own loop, oblivious, harming nothing.

## 2. Firmware toolchain choice

**Chosen: PlatformIO Core + the Arduino framework**, targeting
`esp32-s3-devkitc-1` with pinned versions (`esp32-firmware/
platformio.ini`).

Considered and rejected for this round:

- **Raw ESP-IDF** — more "proper" for a production Espressif product,
  but a steep jump in boilerplate (component structure, `menuconfig`)
  for a firmware this small. Left open as a future migration if a
  specific need (fine-grained power/sleep control, a peripheral
  Arduino's core doesn't expose well) actually outgrows Arduino's API —
  not adopted preemptively.
- **Arduino IDE** (the GUI application) — not scriptable from this
  headless Debian/Pi environment; PlatformIO Core is the CLI-first,
  reproducible equivalent, usable in the same non-interactive
  build/flash workflow as the rest of this project's tooling.

**Why PlatformIO specifically:**

- **Reproducible builds from this exact environment.**
  `esp32-firmware/platformio.ini` pins `platform = espressif32 @ 6.9.0`,
  `framework = arduino`, and `bblanchon/ArduinoJson @ 7.2.0` — a fresh
  checkout on a fresh Pi gets the *same* toolchain and library
  versions, not whatever happens to be current the day someone runs
  it. This matters specifically because the project's stated goal is
  "fresh Pi OS/card → clone repository → installer → reproducible
  PirateBox" (`CLAUDE.md` §3, `docs/ARCHITECTURE.md`).
- **No system-package pollution.** Installed into an isolated venv
  (`~/.venvs/esp32-toolchain`, created via `python3 -m venv` — already
  present via the `python3-venv` apt package, no `pip`/`apt` install
  needed for PlatformIO itself beyond that one already-installed
  building block) rather than system-wide `pip`/`apt`. Deleting that
  one directory removes the entire toolchain cleanly.
- **Mature ESP32-S3 support**, including the native/COM USB duality
  this exact board has (`ARDUINO_USB_MODE`/`ARDUINO_USB_CDC_ON_BOOT`
  build flags — see §4), watchdog access (`esp_task_wdt`), reset-reason
  introspection (`esp_reset_reason()`), and a huge, well-documented
  sensor library ecosystem for the future hardware this design
  anticipates (DS18B20 via OneWire/DallasTemperature, BME280, INA226 —
  all have mature, widely-used Arduino libraries).
- **One-command, scriptable build+flash** (`pio run`, `pio run -t
  upload`) — fits directly into the same "run a script, read its
  output, done" operator workflow every other tool in this repo
  already uses (`piratebox_deploy.sh`, `tools/*.sh`).

**A local packaging note, not a toolchain concern:** the Debian-
packaged `esptool` (4.7.0+dfsg-0.1, already installed, used throughout
commissioning) is missing its ESP32-S3 stub-flasher JSON file — see
`docs/OPERATIONAL-DECISIONS.md`'s commissioning entries for the
disclosed workaround (`--no-stub`). This is unrelated to PlatformIO,
which bundles/manages its own `esptool` internally as a Python
dependency and is unaffected by the system package's gap.

## 3. Protocol

**Wire format: newline-delimited JSON (NDJSON) over the serial link
(COM port, 115200 8N1).** One JSON object per line, UTF-8, terminated
by exactly one `\n`. Chosen over a binary framing specifically so the
link stays inspectable with nothing more than a terminal
(`screen /dev/serial/by-id/... 115200` shows readable text), and so a
single malformed/truncated line can never desynchronize framing for
more than that one line — the next `\n` always resynchronizes both
sides.

Every message, both directions, carries:

| Field | Type | Meaning |
|---|---|---|
| `v` | int | Protocol version (`1` today) |
| `t` | string | Message type |

**A receiver that sees an unrecognized `t` must keep running
completely normally** — this is the extensibility contract that lets
newer firmware talk to an older Pi daemon (or vice versa) without
either side breaking. The ESP32 replies to an unrecognized command with
an `err` message; the Pi daemon silently ignores an unrecognized
message type from the ESP32 (logs at debug, does not raise, does not
disconnect).

### ESP32 → Pi

| `t` | When sent | Fields |
|---|---|---|
| `hello` | Once at boot; again on request (`get_info`) | `fw` (semver string), `board` (`"esp32s3-n16r8"`), `mac`, `reset_reason`, `uptime_ms`, `caps` (array of capability id strings) |
| `hb` (heartbeat) | Every 2s | `seq` (monotonic counter, resets to 0 on reboot), `uptime_ms` |
| `sensors` | Every 5s | `seq`, `readings`: `{capability_id: {"ok": bool, "value"?, "unit"?, "err"?}}` |
| `pong` | Reply to `ping` | `nonce` (echoed back unchanged) |
| `err` | Malformed/unrecognized input received | `reason` (`"bad_json"` or `"unknown_type"`) |

### Pi → ESP32 (deliberately minimal — see §3a)

| `t` | Purpose |
|---|---|
| `ping` | Liveness/latency check; `nonce` field echoed back in `pong` |
| `get_info` | Request a fresh `hello` on demand (used immediately after the Pi daemon (re)connects, so it doesn't have to wait for the ESP32's next natural reboot to learn identity) |

### 3a. Deliberately not a remote shell

There is no generic command-execution or arbitrary-config interface.
The ESP32 receives only the two commands above. This is intentional,
not an oversight: a broad remote-control surface on a locally-attached
microcontroller is exactly the kind of unnecessary attack surface
`docs/ARCHITECTURE.md`'s privacy/security philosophy argues against
(§14 "Trust is not binary", and the project's general "don't invent a
use simply because the hardware supports it" stance). Future config
needs (e.g. adjusting a sensor's polling interval) get a new, narrowly
-scoped message type added to this table when a real need exists — not
a generic passthrough today "just in case."

### 3b. Capability model

`hello`'s `caps` array is the **only** source of truth for what this
specific firmware build can do. A capability id only appears there if
the corresponding sensor's `init()` actually succeeded at boot (see
`esp32-firmware/include/sensors.h`) — this firmware must never claim a
capability that isn't really there, mirroring the "no fake/phantom
hardware" discipline `piratebox_bh1750.py` already established on the
Pi side. Pi-side software must treat any capability id it doesn't
recognize as an opaque, ignorable string — this is how a future sensor
gets added to the firmware without requiring an in-lockstep Pi-side
update first.

Today's only capability: **`temp_internal`** — the ESP32-S3's own
on-die temperature sensor (`temperatureRead()`, no wiring required).
**Explicitly coarse, not a calibrated ambient reading** — Espressif's
own documentation does not characterize this peripheral as accurate
for ambient sensing; it drifts with CPU self-heating. Reported as-is,
labeled `temp_internal` everywhere (never "ambient" or "room
temperature"), so nobody downstream mistakes it for BH1750-grade data.

## 4. Which UART does `Serial` mean on this board?

The ESP32-S3 has two USB-C ports: the native "USB" port (the chip's own
USB-Serial-JTAG peripheral) and the "COM" port (a WCH CH9102 UART
bridge wired to UART0's physical pins). Commissioning
(`docs/OPERATIONAL-DECISIONS.md`, 2026-09-07) proved the native "USB"
port's factory app firmware does **not** support `esptool`'s automatic
bootloader-reset signaling, while the "COM" port's real UART bridge
does. **This project's programming/communication path is the COM port,
exclusively.**

Arduino-ESP32's `Serial` object is ambiguous on S2/S3/C3-class chips —
depending on build flags it can mean either the native USB-CDC
peripheral or the physical UART0 pins. `platformio.ini` sets
`ARDUINO_USB_MODE=1` and `ARDUINO_USB_CDC_ON_BOOT=0` specifically to
force `Serial` to mean UART0 (the COM port's bridge), never the native
USB peripheral this firmware doesn't use at all. **Confirmed necessary
on the real board** — verified end-to-end during bring-up (§8).

## 5. Device discovery — no hardcoded `/dev/ttyACM0`

Linux already creates a stable per-device symlink for this exact
USB-serial bridge without any custom udev rule (confirmed 2026-09-07:
`/dev/serial/by-id/usb-1a86_USB_Single_Serial_5CBB028993-if00` exists
out of the box — standard udev behavior for any USB CDC-ACM device that
reports a real serial number, which the WCH CH9102 bridge does). **No
custom udev rule was needed or written.**

`piratebox_esp32_supervisor.py`'s `KNOWN_BRIDGE_SERIAL` constant
records that bridge's own serial number (`5CBB028993`) — a property of
the *physical bridge chip*, not the ESP32 silicon itself. If this exact
board/bridge is ever swapped for a different unit, update that one
constant. A safe fallback exists for the transition: if the exact
serial isn't found but exactly one other WCH "USB_Single_Serial"
bridge is present, that one is used (logged clearly as a fallback).
**More than one match with no exact serial hit is treated as genuinely
ambiguous and refused, never guessed** — see
`piratebox_esp32_supervisor.py::_select_device_path()` (unit-tested,
`tools/test_esp32_supervisor_protocol.py`).

## 6. Heartbeat / failure behavior

| Scenario | Pi daemon behavior | ESP32 firmware behavior |
|---|---|---|
| Board unplugged / hub loses power | Serial device path disappears → daemon closes the handle, polls for it to reappear (2s initial, backs off to 10s cap) — never busy-loops | N/A |
| Board reboots mid-session | Detected via a fresh unsolicited `hello` arriving with `uptime_ms` less than previously seen → logged with `reset_reason`, `reboot_count` incremented in the export | Sends `hello` unprompted immediately at boot, always |
| Firmware hangs (e.g. a future sensor's I2C bus lockup) | Sees heartbeats stop → after `HEARTBEAT_TIMEOUT_S` (8s, ~4x the firmware's 2s interval) marks the link `stale` in the export, degrading readings to "not current" | Task watchdog (`esp_task_wdt`, 8s timeout, `trigger_panic=true`) fires and resets the chip cleanly — the *next* `hello`'s `reset_reason` will read `"task_wdt"`, so the cause is visible afterward, not just the fact of a reset |
| Malformed/partial/oversized line received | Counted (`malformed_lines`), line dropped, loop continues — never raises (`tools/test_esp32_supervisor_protocol.py::HandleLineTests`) | `PIRATEBOX_MAX_LINE_LEN` (512 bytes) bounds input; a bad-JSON or unrecognized-type line gets an `err` reply, never a crash |
| Pi daemon itself restarts | Rebuilds all state from scratch (no persistent Pi-side sensor cache) and immediately sends `get_info` rather than waiting on the ESP32's next natural reboot | N/A — asymmetric protocol; the ESP32 never needs to notice the Pi daemon restarting |
| Pi disappears entirely / no host heartbeat ever arrives | N/A | Firmware has **no dependency on hearing from the Pi at all** — it broadcasts `hello`/`hb`/`sensors` proactively regardless of whether anything is listening. This is deliberate: the protocol is asymmetric by design (§3), so "no host heartbeat" is simply the normal disconnected case, not a fault condition on the ESP32 side |
| One sensor fails, others still work | Each capability's `readings` entry is independent (`"ok": false` for the failed one only) — never blocks other sensors' data | Each sensor's read function is independently guarded (§ "Sensor abstraction" below) |

**Distinguishing detected / unavailable / stale:** a capability absent
from `caps` entirely means "this firmware build doesn't have this
sensor" (never wired, or firmware predates it). A capability present
but reporting `"ok": false` means "wired/expected, but the read just
failed." The Pi export's own `connected`/`stale` flags mean "is the
link itself currently alive and recent" — the same three-state
distinction (`installed` / `detected` / `stale`) `includes/sensors.php`
already established for BH1750, reused here for consistency.

## 7. Sensor abstraction (firmware side)

`esp32-firmware/include/sensors.h` / `sensors.cpp`: one `init()` +
`read()` pair per sensor, each independently guarded — the same "one
bad sensor can never affect another" discipline `piratebox_bh1750.py`
already established on the Pi side, applied here to the firmware. Only
`temp_internal` exists today. Future sensors (a migrated BH1750,
DS18B20, BME280, INA226) get added the same way: their own init/read
pair, their own capability id, no change needed to the protocol
encoding itself (`protocol.cpp`'s `pb_build_sensors()` already
iterates a `readings` object generically).

## 7a. ESP32-S3 GPIO/pin resource map

The running record of this board's own pin usage — grows only as
sensors are actually wired, never pre-assigned speculatively (mirrors
`docs/HARDWARE-INTEGRATION-DESIGN.md` §2's own discipline for the Pi's
GPIO table).

| Function | Pin(s) | Status | Notes |
|---|---|---|---|
| Internal temperature | (none — on-die peripheral) | **WIRED, VERIFIED** | `temperatureRead()`, no external pins |
| I2C bus (SDA/SCL) | GPIO8 / GPIO9 | **WIRED, VERIFIED (2026-09-07)** | Standard default I2C pins for this board's PlatformIO definition; not a strapping pin. BH1750 ambient light sensor now live here (migrated from the Pi - §16); shared bus, available for future I2C sensors (BME280, INA226) with no new pins needed |
| BH1750 (ambient light) | GPIO8 (SDA) / GPIO9 (SCL), shared bus above | **WIRED, VERIFIED, MIGRATED FROM THE PI (2026-09-07)** | Address 0x23, ADDR floating — same wiring convention as its original Pi-side commissioning. See §16 for the full migration record, including a real mid-migration wiring fault that was found and fixed |
| Strapping pins (GPIO0, GPIO3, GPIO45, GPIO46) | — | **Reserved, deliberately unused** | Boot-mode/voltage-selection significance on this chip — avoided for any general-purpose sensor/GPIO use |
| USB "COM" port (UART0, physical pins) | — | **WIRED, VERIFIED, IN USE** | The Pi↔ESP32 communication link itself (§4) — not available for other use |
| Native USB "USB" port | — | Present, unused by this firmware | Native USB-CDC peripheral; this firmware never initializes it (§4) |
| DS18B20 (future) | not yet assigned | CANDIDATE, not wired | 1-Wire needs one GPIO + a pull-up; pin TBD when actually built |
| INA226 (future) | not yet assigned | CANDIDATE, not wired | I2C — would share GPIO8/9 above, same bus, no new pins needed |
| Physical buttons/RGB (future) | not yet assigned | CANDIDATE, not wired | No pins reserved speculatively |

## 8. Real-hardware validation performed this round

- Firmware built via `pio run` against the pinned toolchain — compiles
  cleanly (RAM 5.7%, Flash 21.2% used - large margins for future
  sensors).
- **Factory firmware backed up** before the first custom flash (see
  §11) via PlatformIO's bundled `esptool` (stub-mode `read_flash`, 460800
  baud) over the proven COM-port path — full 16MB image, stored outside
  the git tree. **Validated, not just taken on faith**: exact size
  (16,777,216 bytes), SHA-256 recorded alongside the file, first bytes
  confirmed as a genuine ESP image header (`E9 03 02 40...` - the
  standard esptool/ESP-IDF magic byte), and an independent live re-read
  of both the first and last 64KB compared byte-for-byte against the
  saved file - both matched exactly. See §11 for location, the exact
  commands, and the restore procedure. **A real mid-attempt mistake is
  recorded honestly here, not smoothed over**: a first backup attempt
  (default settings, no explicit baud) was misdiagnosed as hung after
  ~19 minutes with no output file yet on disk, and killed at that
  point - re-reading the actual captured console output afterward
  showed it had reached 72% with continuous, genuine progress the
  entire time; the absence of a file was a red herring, since this
  esptool build only writes the output file in one shot at the very
  end of a stub-mode `read_flash`; watching the destination file rather
  than the actual progress output was the wrong signal to check. No
  harm resulted (read-only, board unaffected) - the retry (at an
  explicit 460800 baud, this time watched via its real console output)
  completed cleanly in 542.6 seconds.
- Custom firmware flashed via the COM port
  (`tools/flash_esp32_supervisor.sh`, which wraps `pio run -t upload` -
  PlatformIO's bundled `esptool`, at 460800 baud). Every write chunk
  reported "Hash of data verified." The device re-enumerated within 1
  second of the post-flash reset.
- Verified live end-to-end: the Pi daemon (run manually, export
  redirected to a writable path for this pre-systemd-install check)
  received a real `hello` — `fw_version: "0.1.0"`, `board:
  "esp32s3-n16r8"`, `mac: "7c:4f:ad:b6:2f:94"` (exactly matching the
  MAC read independently during commissioning), `reset_reason:
  "poweron"`, `capabilities: ["temp_internal"]` — followed by a live
  `temp_internal` reading of 41.5°C and zero malformed lines.
- Verified PirateBox core services, ALFA/`pb-ap`/hostapd, Ethernet, and
  the existing BH1750/OLED/RTC path were all unaffected throughout.
- `vcgencmd get_throttled` recorded before/after — see
  `docs/OPERATIONAL-DECISIONS.md`'s entry for this round for the exact
  readings; unchanged, as expected (this work never touches Pi power).

(This section is a pointer — the exact commands, timestamps, and
readings live in `docs/OPERATIONAL-DECISIONS.md`, which is the
project's actual decision/evidence log; this design doc stays the
stable architecture reference.)

## 9. Power supervision — prepared, not implemented

The Pi's chronic `vcgencmd get_throttled = 0x50005` condition
(`docs/POWER-INTEGRITY-DIAGNOSIS.md`) is **unresolved** and **out of
scope for this firmware to fix**. The externally powered USB hub
resolved the ESP32's *own* USB connection stability — it did **not**
clear the Pi's undervoltage condition, and this firmware makes no claim
that it did.

The anticipated long-term architecture:

```
external DC -> proper power/UPS/regulation -> Pi / radios / peripherals
                                            -> telemetry (INA226, future)
                                            -> supervisor-assisted safe shutdown
```

**Nothing in this round implements autonomous power-cut behavior of any
kind.** No INA226 is wired. No shutdown-request path from ESP32 to Pi
exists yet. This section exists so a future round has a documented seam
to build into rather than retrofitting one: when INA226 telemetry and a
real shutdown-cooperation protocol are eventually built, they must
include (per the operator's own explicit requirement): clear states,
hysteresis, a timeout/failsafe, logging of *why* any action was taken,
Pi graceful-shutdown cooperation (never a hard power cut sprung on a
running Pi), and protection against reboot loops. **The ESP32 must
never unexpectedly kill Pi power** — this remains true until a future
round deliberately, carefully builds and validates that capability with
explicit operator sign-off at each step, not before.

## 10. Privacy / security posture

- Wi-Fi and BLE radios are **never started** by this firmware. MAC
  address is read directly from efuse (`esp_efuse_mac_get_default()`),
  which requires no radio initialization at all — reported for
  identification purposes only, exactly mirroring how the commissioning
  round already read it via `esptool`.
- No cloud service, account, or Internet dependency of any kind.
- No visitor MAC/IP/identity history is ever stored on the ESP32 — it
  has no visibility into PirateBox's Wi-Fi clients at all; nothing here
  changes that.
- The protocol (§3a) is deliberately not a remote-shell/arbitrary-
  command surface, even locally.
- Travel Mode is unaffected — this subsystem carries no visitor-facing
  data and has no interaction with Travel Mode's quarantine mechanism.

## 11. Deployment / firmware update safety

- **Factory firmware backup, made once, before the first custom
  flash** (`tools/backup_esp32_factory_firmware.sh`): a full 16MB
  `read_flash` over the proven COM-port connection, using PlatformIO's
  bundled `esptool` in normal stub mode — **not** the system/apt
  `esptool`'s `--no-stub` path, which proved unreliable for a transfer
  this large (two attempts each failed mid-read with "Serial data
  stream stopped," never harming the board — read-only, and it stayed
  enumerated throughout both failures; the Debian package's own missing
  stub-flasher file, already disclosed in §2, is the underlying cause —
  PlatformIO's copy has the complete stub files this chip needs).
  Verified by checking the read image's size matches exactly and it is
  not all-zero/all-`0xFF` (a full erase pattern) — a real, non-trivial
  factory image. **Location and restore command are recorded in
  `docs/OPERATIONAL-DECISIONS.md`'s entry for this round** (kept out of
  the git tree deliberately — a 16MB binary blob doesn't belong in
  history, and the backup's value is as a recoverable file, not as a
  tracked artifact).
- **Flashing tooling identifies the expected device before writing
  anything**: the same `KNOWN_BRIDGE_SERIAL`-based discovery used by
  the Pi daemon (§5) — a flash attempted against any other tty device
  is refused, not guessed.
- **No security efuses burned, ever, by any tool or script in this
  round.** Secure Boot and Flash Encryption remain disabled (confirmed
  at commissioning, re-confirmed unaffected after this round's flash) —
  intentional, standard, reversible development state. Burning either
  is a one-way, irreversible hardware change and is explicitly out of
  scope unless a future round has a real production-security reason and
  explicit, deliberate operator sign-off.
- Firmware version is embedded at build time
  (`PIRATEBOX_FW_VERSION` in `platformio.ini`) and reported in every
  `hello` — an operator can always tell what's actually running without
  guessing from source-tree state.

## 12. Reproducibility

A fresh PirateBox install reproduces this subsystem via:

1. `python3 -m venv ~/.venvs/esp32-toolchain && ~/.venvs/esp32-toolchain/bin/pip install platformio`
   (one-time, isolated, no sudo — see §2).
2. `cd esp32-firmware && ~/.venvs/esp32-toolchain/bin/pio run -t upload`
   (COM port connected, externally powered hub in place per the
   current prototype topology — see §13) to flash the supervisor.
3. `sudo ./setup_piratebox_esp32_supervisor.sh` to install and enable
   the Pi-side daemon (mirrors `setup_piratebox_button.sh`'s exact
   pattern — reuses the same `piratebox-gpio` account, no new sudoers
   grant).

No step here depends on undocumented state specific to this one Pi.

## 13. Known current-prototype-only physical dependency

**The externally powered USB hub is required for a stable connection
in the CURRENT prototype topology** (`docs/OPERATIONAL-DECISIONS.md`,
2026-09-07 A/B/C hub-power investigation) — direct Pi-to-ESP32 USB was
unreliable, and this is a property of this specific Pi's marginal USB
power delivery (correlated with, not proven caused by, the Pi's
separately-tracked `0x50005` condition — see
`docs/POWER-INTEGRITY-DIAGNOSIS.md`), not of the ESP32 or this
software. A future enclosure/power revision may remove this dependency;
until then, any fresh setup of this subsystem needs the same externally
powered hub in the same position.

## 14. Testing

- **Protocol/daemon logic**: `tools/test_esp32_supervisor_protocol.py` —
  29 tests covering device-selection ambiguity, malformed/oversized/
  non-object/missing-type lines, unknown-message-type forward
  compatibility, hello/heartbeat/sensor field population, reboot
  detection via uptime rollback, staleness timing, and the cached-
  export reader's degrade-to-unavailable behavior. Run via
  `python3 tools/test_esp32_supervisor_protocol.py -v`.
- **Firmware-side logic** is validated on the real commissioned board
  (§8) rather than host-testing the C++ — the actual logic (JSON
  encode/decode, line framing) is thin enough that ArduinoJson's own
  test suite already covers the hard part, and the meaningful risk
  (does the COM port actually behave as designed, does the watchdog
  actually recover a hang) is inherently a real-hardware question, not
  a host-testable one.
- **Explicitly not tested by an automated suite**: the physical
  disconnect/reconnect/reboot scenarios in §6's table were validated by
  reasoning from the code + the same kind of direct observation used
  throughout commissioning, not a scripted physical fault-injection
  harness — appropriate for this project's scale.

## 15. Open items / deliberately deferred

- **PSRAM confirmed present, deliberately not yet enabled.** Read-only
  commissioning proved 8MB embedded PSRAM via efuse config
  (`docs/OPERATIONAL-DECISIONS.md`). This firmware does not enable it
  (`platformio.ini` has no PSRAM build flags) because (a) it isn't
  needed yet by anything this firmware does, and (b) the WROOM-1 "R8"
  module family conventionally uses **octal**-SPI PSRAM, but that bus
  width has not been independently confirmed for this exact unit —
  enabling the wrong PSRAM interface mode risks a boot failure for zero
  present benefit. Revisit when a real feature (e.g. simultaneous
  BLE + WiFi + large buffers) actually needs the extra RAM.
- **BH1750 migration**: COMPLETE (§16) - no longer an open item.
- **Environment web UI / OLED glance integration**: a minimal
  `includes/esp32_supervisor.php` reader exists (mirrors
  `includes/sensors.php`'s pattern) and a `HARDWARE_SIGNALS` reader is
  registered (`esp32_temp_internal`) — see
  `docs/OPERATIONAL-DECISIONS.md` for what shipped this round vs. what
  remains a natural follow-up.
- **Power supervision (INA226, shutdown cooperation)**: architecture
  seam only (§9) — no hardware wired, no protocol messages defined yet.
- **DS18B20 / BME280 / future sensors**: not implemented — the
  capability model (§3b) and sensor abstraction (§7) exist specifically
  so adding them later doesn't require protocol changes, but no code
  for them exists yet.

## 16. BH1750 migration — COMPLETE (2026-09-07)

**Status: done, validated, and switched over.** The BH1750 was
physically moved from the Pi's own I2C1 bus to the ESP32-S3
supervisor's I2C bus (GPIO8/GPIO9), the BH1750-aware firmware (built
ahead of time — see the original plan preserved below) was flashed,
and a real, plausible reading (**11.67 lux**, `ok: true`) was confirmed
flowing through the full pipeline: firmware → daemon → cached export.
`HARDWARE_SIGNALS`'s `"ambient_lux"` now reads from the ESP32 path
(`piratebox_esp32_bh1750.py`, a drop-in replacement for the retired
`piratebox_bh1750.py` registration — see that file's own header).

**A real complication during the physical move, resolved and recorded
honestly:** immediately after the first physical reconnection, the
ESP32 went completely silent — its USB bridge (CH9102) stayed cleanly
enumerated throughout (ruling out a USB/hub/cable/Pi-power problem),
but the chip itself produced zero bytes, even under `esptool`'s own
forced-reset sequence (which talks to the ROM bootloader independent
of any application firmware — a very reliable, well-tested path
throughout this entire project up to that point). That combination —
stable bridge, totally unresponsive chip, unresponsive even at the ROM
level — is only consistent with the chip's own core losing a stable
power/reset path, not a software or USB fault. The operator re-checked
and corrected the physical wiring; communication was fully restored
immediately afterward with no further action needed, confirming the
original fault was electrical (most likely on the 3.3V/GND leads
specifically, since those are the only new connections that gate
whether the chip's core boots at all — SDA/SCL miswiring would not
explain a totally silent ROM bootloader). No hardware damage resulted;
the ESP32-S3 itself, its factory identity, and the supervisor firmware
were all confirmed intact once wiring was corrected.

**A second, separate complication**: flashing the corrected firmware
initially failed with "Serial data stream stopped" during connection —
not a hardware problem this time, but simple resource contention: the
systemd `piratebox-esp32-supervisor.service` daemon was holding the
serial port open, and `esptool` needs exclusive access for its
handshake. Confirmed via the daemon's own logs (it correctly detected
the interference — `malformed_lines: 6`, marked itself `stale` —
without crashing, exactly the resilience this project was built for).
Resolved with one operator `sudo systemctl stop
piratebox-esp32-supervisor.service` before the successful flash.

**Original plan, preserved below for historical reference** — this is
exactly what was executed:

**ESP32-S3 I2C pins chosen for this**: GPIO8 (SDA) / GPIO9 (SCL) — the
standard default I2C pins for this board's `esp32-s3-devkitc-1`
PlatformIO board definition, and deliberately not a strapping pin (this
chip's strapping pins are GPIO0/3/45/46 — none touched here). See §7a
for the running pin/resource map this project will keep as more
sensors are added.

**Wiring plan** (BH1750 → ESP32-S3):

| BH1750 pin | ESP32-S3 connection |
|---|---|
| VCC | 3.3V |
| GND | GND |
| SDA | GPIO8 |
| SCL | GPIO9 |
| ADDR | Left floating (unconnected) — same as its current Pi wiring, giving address `0x23` |

**Electrical/safety notes**: this is a low-voltage (3.3V logic, low
current) I2C sensor — no different in risk from its current Pi wiring.
The BH1750 module in service has its own onboard pull-up resistors (the
same module already proven working on the Pi), so no external
pull-ups are needed on the ESP32 side either. **Shutting down the Pi
first is not required** for this specific move — the wiring changes are
entirely on the BH1750/ESP32 side; nothing is added, removed, or
touched on the Pi's own GPIO2/GPIO3 I2C bus, so the Pi can stay running
throughout. The ESP32 itself should have its USB/power connection
removed while moving the three data/power leads, purely as ordinary
hot-plug hygiene (avoiding a half-connected transient on the sensor's
GND/VCC while the leads are being moved), then reconnected through the
same externally-powered hub afterward.

**Test sequence actually executed, all steps passed**: (1) flashed the
`bh1750`-aware firmware; (2) confirmed `hello`'s `caps` array included
`"bh1750"`; (3) confirmed the `sensors` message carried a `bh1750`
reading with `"ok": true` and a plausible lux value (11.67, consistent
with the earlier Pi-side commissioning's ~9-12 lux range in similar
ambient conditions); (4) `HARDWARE_SIGNALS`'s `"ambient_lux"` then
switched to the ESP32 path only after that reading was confirmed good.
`piratebox_bh1750.py` (the original Pi-side module) is unchanged and
left in the repo for historical/rollback reference — nothing imports
it anymore.
