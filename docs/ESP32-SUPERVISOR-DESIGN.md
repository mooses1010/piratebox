# ESP32-S3 Hardware/Sensor Supervisor — Design

**Status: WORKING IMPLEMENTATION, multi-probe DS18B20 support ready
and awaiting its physical wiring gate (2026-09-07).** BH1750 ambient
light is live on the ESP32's own I2C bus (§16) — no longer Pi-owned.
DS18B20 multi-probe temperature support (§17), a commissioning
workflow for naming probes, an OLED probe glance page, and ambient-
light-driven OLED auto-brightness (§18) are all built, tested, and
ready — no DS18B20 hardware is physically wired yet; see §17's
consolidated physical gate. The board was
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

Today's capabilities: **`temp_internal`** — the ESP32-S3's own on-die
temperature sensor (`temperatureRead()`, no wiring required).
**Explicitly coarse, not a calibrated ambient reading** — Espressif's
own documentation does not characterize this peripheral as accurate
for ambient sensing; it drifts with CPU self-heating. Reported as-is,
labeled `temp_internal` everywhere (never "ambient" or "room
temperature"), so nobody downstream mistakes it for BH1750-grade data.
**`bh1750`** — see §16, migrated from the Pi. **`ds18b20`** — see §17;
this one follows a deliberately *different* presence rule than the
other two (below).

**`ds18b20` is a genuine exception to "one capability = one sensor
instance."** DS18B20 is a real multi-device 1-Wire bus — "zero probes
currently found" is itself a valid, meaningful, distinguishable state
(the bus exists and was scanned; nothing answered), not the same as
"this firmware build has no DS18B20 support compiled in at all."
Collapsing that distinction into the same "capability appears only
once a device responds" rule the single-instance sensors use would
make a genuine bus fault (probes were found before, now none are)
indistinguishable from "never wired." So: `ds18b20` appears in `caps`
once the bus has *ever* found at least one probe (a one-way latch —
see `pb_ds18b20_ever_found_a_probe()`), and stays present even if every
probe later disappears; the actual per-probe count/identity/health
always lives in the `sensors` message's own `ds18b20` block (§17),
which can legitimately report zero probes without the capability
itself being absent.

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
| 1-Wire bus (DS18B20) | **GPIO4** | **Firmware ready (2026-09-07), not yet wired** | Chosen for this bus — free on this board's PlatformIO definition, not a strapping pin, not part of the flash/PSRAM QSPI bus (GPIO26-37 avoided entirely — this module's PSRAM bus width hasn't been independently confirmed, see §15), not shared with the existing I2C bus. See §17 for the full multi-probe design and the wiring plan awaiting the physical gate |
| INA226 (future) | not yet assigned | CANDIDATE, not wired | I2C — would share GPIO8/9 above, same bus, no new pins needed |
| BME280 (future) | not yet assigned | CANDIDATE, not wired | I2C — would share GPIO8/9 above, same bus, no new pins needed |
| Onboard RGB LED | **unknown, deliberately not guessed** | **Evaluated, not implemented (2026-09-07)** | This board's generic PlatformIO manifest (`esp32-s3-devkitc-1.json`) declares no LED pin at all — some ESP32-S3 dev board revisions use GPIO48, others GPIO38, and guessing wrong risks driving a pin wired to something else entirely. See §20 |
| Physical buttons | not yet assigned | CANDIDATE, not wired | No pins reserved speculatively |

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
- **Environment web UI / OLED glance integration**: `includes/
  esp32_supervisor.php` covers Hardware Supervisor status, named
  DS18B20 probes, and (via `includes/sensors.php`) ambient light;
  `HARDWARE_SIGNALS` readers are registered for `esp32_temp_internal`
  and (via the migration) `ambient_lux`; OLED glance pages exist for
  ambient light and named temperature probes (§17).
- **DS18B20 multi-probe support**: COMPLETE in software (§17) - awaiting
  its physical wiring gate. Not an open item once that gate is done.
- **OLED ambient-light auto-brightness**: COMPLETE (§18).
- **ESP32 black-box/event-log**: EVALUATED, DEFERRED (§19) — belongs
  with the later power-supervision phase, per that section's reasoning.
- **Onboard RGB status LED**: EVALUATED, NOT IMPLEMENTED (§20) — this
  board's exact LED GPIO isn't safely known from its manifest; not
  guessed.
- **Power supervision (INA226, shutdown cooperation)**: architecture
  seam only (§9) — no hardware wired, no protocol messages defined yet.
- **BME280 / other future sensors**: not implemented — the capability
  model (§3b) and sensor abstraction (§7) exist specifically so adding
  them later doesn't require protocol changes, but no code for them
  exists yet.

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

## 17. DS18B20 multi-probe temperature bus

**Status: software complete, awaiting the physical wiring gate
(§17f).** Four waterproof DS18B20-style probes exist; none are wired
yet. This section covers the design; §17f is the exact, consolidated
physical request.

### 17a. Why a real multi-device bus, not four hardcoded inputs

Each DS18B20 carries its own unique, factory-burned 64-bit 1-Wire ROM
address (an 8-bit family code + 48-bit serial + CRC8) — this is the
hardware's own real identity, and it is the *only* thing this firmware
ever uses to identify a probe. There is no concept of "probe 1/2/3/4"
anywhere in the firmware or protocol — physical position on the bus is
never observed and never assumed stable (per instruction). ROM
addresses are discovered by a real bus search
(`OneWire::search()` + CRC8 validation), never invented, never
assumed present.

### 17b. Firmware: `esp32-firmware/include/ds18b20.h` / `ds18b20.cpp`

- **Library choice**: `paulstoffregen/OneWire` + `milesburton/
  DallasTemperature` (pinned versions in `platformio.ini`) — the
  standard, mature pairing for this exact chip family on Arduino-family
  cores. ROM search/CRC/scratchpad-format handling (DS18B20 vs. its
  DS1822/DS18S20 cousins, which use slightly different scratchpad
  layouts) is exactly the kind of well-trodden protocol logic not worth
  hand-rolling.
- **Non-blocking by design**: a 12-bit conversion takes up to ~750ms.
  `DallasTemperature::setWaitForConversion(false)` plus a small
  two-state machine (`Idle` / `Converting`, driven by
  `pb_ds18b20_tick(millis())` called every `loop()` iteration) means
  this never calls `delay()` and never risks tripping the task
  watchdog or delaying heartbeats — the same non-blocking discipline
  every other part of this firmware already follows.
- **Polling cadence, deliberately not aggressive**: a full read cycle
  (broadcast convert → wait → read every known probe) runs every 30s —
  environmental temperature does not need faster updates, and this
  bounds 1-Wire bus traffic. A full bus **re-search** (to notice a
  probe physically added or removed) runs far less often — once every
  10 read cycles, ~5 minutes — since walking the whole bus topology is
  the more disruptive of the two operations to get wrong mid-read.
- **Known DS18B20 realities, accounted for explicitly**:
  - *CRC validation*: `DallasTemperature::getTempC()` validates CRC
    internally and returns its own disconnected sentinel on failure —
    not re-implemented here.
  - *`DEVICE_DISCONNECTED_C` (-127.0)*: reported as `ok: false`, never
    as a real (and absurd) sub-zero reading.
  - *The well-known 85.0°C power-on/uninitialized-scratchpad value*:
    a genuine 12-bit conversion is affected by enough real thermal
    noise that landing on **exactly** 85.0 is vanishingly unlikely from
    a real reading — treated as suspect (`ok: false, err:
    "uninit_85c"`) rather than trusted at face value.
  - *Individual probe failure never affects another probe* — each
    probe's `ok`/`err` is fully independent; a `bus_ok` flag (see
    17c) separately tracks bus-wide health.
  - *Conversion/bus timing*: handled by the async state machine above,
    not by blocking.
- **Parasite power: deliberately not supported.** Per instruction, this
  project uses conventional powered three-wire DS18B20 wiring
  (VCC/DATA/GND) — no compelling reason exists to add parasite-power
  complexity, and it would only weaken reliability for no benefit here.

### 17c. Protocol shape

```json
{"v":1,"t":"sensors","seq":42,"readings":{
  "ds18b20": {
    "bus_ok": true,
    "probes": {
      "28ff641e04170378": {"ok": true, "value": 21.4, "unit": "C"},
      "28aa112233445566": {"ok": false, "err": "disconnected"}
    }
  }
}}
```

`bus_ok` is `true` unless the bus has **regressed** from "has
previously found at least one probe" to "finds none now" — a bus that
has *never* found anything reports `bus_ok: true` (that's "not wired
yet," not a fault; see `pb_ds18b20_bus_ok()`'s own header). This is how
"bus failure" is distinguished from "nothing was ever connected" from
the exact same underlying electrical signal (a 1-Wire reset getting no
presence pulse).

### 17d. Pi-side: ROM identity, naming, and the commissioning workflow

**Sensor names are cosmetic configuration metadata; the ROM address
remains the permanent hardware identity — always.** A name is never
used to *identify* a probe internally, only to *display* it.

- **Storage: a single durable JSON file**
  (`/var/lib/piratebox-esp32/ds18b20-roles.json`, `{rom: {name,
  assigned_at}}`), not a database — this project has none by design,
  and a handful of rarely-changing entries is exactly what a flat file
  already handles well elsewhere (`piratebox_progression.py`'s own
  state file, `sensors-public.json`, etc.).
- **Single-writer discipline**: mirrors `piratebox_progression.py`'s
  own reset/import-request pattern exactly. `tools/ds18b20_
  commission.py` (run by the operator, as `moose`) never writes the
  durable file directly — it drops a small request file
  (`ds18b20-name-request.json`) that `piratebox_esp32_supervisor.py`
  (the daemon, running as `piratebox-gpio`) picks up and applies. Both
  files live under one systemd `StateDirectory=piratebox-esp32`
  (persistent — survives reboots, unlike the daemon's own
  `RuntimeDirectory=` export), created with **mode 0770**: `moose` is
  already a member of the `gpio` group (confirmed 2026-09-07), so the
  request file needs no sudo and no bind-mount indirection — a cleaner
  answer than the OLED daemon's own `/tmp/piratebox` arrangement (which
  exists specifically to work around *its own* `PrivateTmp=yes`; this
  daemon's `PrivateTmp=yes` only isolates `/tmp`, irrelevant here).
- **Commissioning workflow** (`tools/ds18b20_commission.py`):
  1. `python3 tools/ds18b20_commission.py watch` — lists every
     discovered ROM address with its live temperature, refreshing
     every few seconds.
  2. Operator warms **one** physical probe with their fingers.
  3. The ROM address whose temperature visibly rises is now identified.
  4. `python3 tools/ds18b20_commission.py name <rom> "Enclosure"` —
     assigns the name. Repeat per probe.
  5. `python3 tools/ds18b20_commission.py list` confirms it stuck.
  - Never touches the serial port directly — reads only the daemon's
    already-published cached export, same discipline as every other
    consumer of this data.

### 17e. Pi-side / UI representation of every required state

| State | Representation |
|---|---|
| Zero probes ever found | `ds18b20` capability absent from `hello.caps` entirely |
| Bus wired, zero probes right now | `ds18b20` capability present, `sensors.ds18b20.probes` is `{}` |
| One or more probes, all healthy | Each ROM's own `{"ok": true, "value": ..., "unit": "C"}` |
| A probe added | Appears in `probes` after the next bus rescan (≤ ~5 min) |
| A probe removed | Disappears from `probes` after the next bus rescan — never a stale phantom entry |
| A probe's reading temporarily fails | That ROM's own `{"ok": false, "err": "disconnected"/"uninit_85c"}` — other probes and the rest of the firmware are unaffected |
| Bus failure (previously had probes, now finds none) | `bus_ok: false` |
| Named vs. unnamed | `piratebox_esp32_bh1750.py`-style enrichment adds `"name"` (or `null`) per probe at the Pi daemon layer — see `_enrich_ds18b20_with_names()` in `piratebox_esp32_supervisor.py` |
| Public Environment page | Shows **only named** probes, by name — ROM addresses never appear on the ordinary visitor page (they belong in `tools/ds18b20_commission.py`); an "N probe(s) detected, not yet named" note appears if any are unnamed |
| OLED | A "probe" glance page (§ piratebox_glance.py) shows one **named, currently-ok** probe at a time, rotating by wall-clock minute if more than one qualifies — an unnamed or currently-failing probe is never glance-worthy |

### 17f. THE PHYSICAL GATE — wiring plan

**Not performed. Requires the operator.** Everything above is built,
tested, and ready to flash the moment probes are wired.

| DS18B20 wire | Connects to |
|---|---|
| VCC | 3.3V |
| GND | GND |
| DATA | **GPIO4** |

**Wiring color convention** (per the project's own established
harness colors — see `docs/OPERATIONAL-DECISIONS.md` for the BH1750
precedent this follows): DS18B20 is 1-Wire, not I2C, so it does **not**
reuse SDA/SCL's yellow/orange — a **BLUE** wire is designated for
DATA on this bus (VCC stays RED, GND stays GREEN, matching the
existing ESP32-side convention exactly; only DATA needed a new color
since I2C's SCL/SDA pair doesn't map onto a single-wire bus).

**Using the DAT/VCC/GND breakout with its onboard "472" resistor**:
yes, planned — 472 (in the standard 3-digit resistor code) means
47 × 10² Ω = **4.7 kΩ**, exactly the DATA-to-VCC pull-up a DS18B20 bus
needs. **Verify, don't assume**, per instruction: confirm with a
multimeter that the resistor actually measures ~4.7 kΩ and is wired
between DATA and VCC (not DATA-to-GND, which would be wrong) before
trusting it — if confirmed, no second external pull-up is needed; if
not, add a conventional 4.7 kΩ resistor between DATA and 3.3V
yourself.

**Verify probe lead colors before trusting them**: waterproof DS18B20
probes are commonly sold as red=VCC/black=GND/yellow=DATA, but cheap
clones are inconsistent — **confirm with a multimeter (continuity/
resistance from each lead into the probe body) rather than trusting
the color alone**, exactly the same "verify, don't assume" discipline
already applied throughout this project's wiring work.

**Start with ONE probe, not all four** — isolates any wiring mistake
to a single, easily-disconnected device before committing all four,
and matches this project's own "one variable at a time" testing
discipline used throughout the BH1750 migration.

**Power state**: neither the Pi nor the ESP32 needs to be powered down
for this — DATA/VCC/GND are new connections to previously-unused pins
(GPIO4, plus 3.3V/GND already used elsewhere on the same rail); nothing
existing is disturbed. As ordinary hot-plug hygiene, disconnect the
ESP32's own USB connection while making the physical wiring changes
(the exact same precaution used for the BH1750 migration), then
reconnect through the same externally-powered hub afterward.

**What happens immediately after reconnecting**: (1) confirm the ESP32
is communicating normally (`hello`/heartbeat, per the now-established
pattern — a repeat of the recent BH1750-migration wiring fault would
show the same signature: USB bridge enumerates fine, chip silent even
under `esptool`); (2) flash the DS18B20-aware firmware (already built
and validated this round — `tools/flash_esp32_supervisor.sh`);
(3) run `tools/ds18b20_commission.py watch` and confirm the one
connected probe appears with a plausible room-temperature reading;
(4) if that's good, connect the remaining three probes (still one at a
time, verified between each) and repeat; (5) name each probe via
`tools/ds18b20_commission.py name`; (6) confirm the Environment page
and OLED probe glance page both show the named probe(s) with real,
plausible data; (7) full regression check (core services, ALFA/`pb-ap`/
hostapd, I2C bus, `vcgencmd get_throttled`) — the same battery of
checks every physical change in this project's history has used.

## 18. OLED ambient-light auto-brightness

**Status: COMPLETE (2026-09-07).** The "`set_contrast()` plumbing…
ready to be driven" this project's own OLED daemon header has
referenced since round 8 (deferred back then only because auto-DIM had
no way to *wake* the display, with no button wired) finally has a
real driver — and that old blocker doesn't apply here, because this
mechanism never goes fully dark and never needs waking from anything.

- **Mechanism**: `compute_target_contrast(ambient_lux)` maps the
  cached ambient-light reading (via `read_current_ambient_lux()` — the
  *exact same* already-cached BH1750 diagnostics the "ambient" glance
  page uses; no second I2C/serial trigger, ever) to a target SSD1306
  contrast value on a roughly logarithmic curve (perceived brightness
  is itself roughly logarithmic in lux), bounded to `[OLED_MIN_
  CONTRAST=10, OLED_MAX_CONTRAST=255]` — 10 is a readable floor in a
  dark room, never fully off.
- **Hysteresis/no-pumping**: `slew_contrast()` moves the *applied*
  contrast toward the target by at most a few units per ~3s tick (a
  full min↔max transition takes a few minutes) — this slew is the
  actual anti-pumping mechanism itself, not a separate debounce timer.
  A hand briefly waved over the sensor nudges brightness only slightly
  before the reading returns to normal; it can never cause a visible
  snap or flicker.
- **Failure-safe**: a missing/never-wired/stale BH1750 reading always
  maps to full brightness (`OLED_MAX_CONTRAST`) — erring toward "too
  bright" costs a little contrast; erring toward "too dim" risks an
  unreadable display exactly when it matters most.
- **Emergency visibility preserved absolutely**: `tier == "emergency"`
  (from `compute_display_tier()`, unchanged) forces full brightness
  every tick, completely bypassing ambient-light logic — Emergency
  Mode's own display priority (already the highest in this daemon) is
  never dimmed by this feature, regardless of how dark the room is.
- **Zero new I2C traffic**: `read_current_ambient_lux()` reads only
  the BH1750 module's own already-cached diagnostics — the same call
  the "ambient" glance page already made, now also made once per
  ordinary tick (not just during a glance-phase-entry) so brightness
  tracks room light continuously; this triggers no new hardware
  transaction of any kind.

## 19. ESP32 black-box/event log — evaluated, deferred

**Evaluated. Deliberately not implemented this round.** A small
bounded hardware-event history (boot/reset reason, Pi-heartbeat lost/
restored, sensor appeared/disappeared, bus fault/recovery) would add
real diagnostic value eventually — but it belongs with the power-
supervision phase (§9), not this one, for a concrete reason: the
*first* genuinely compelling use case for this kind of history is
correlating a future INA226 power event with what the supervisor was
doing at the time ("did the bus fault happen right as a brownout was
detected?") — building the event log now, before there's anything
power-related to correlate against, would mean guessing at its shape
twice. When it is built: bounded/circular, RAM-resident (not flash —
avoiding flash wear for data whose value is almost entirely about
*recent* history, not months-old history), and explicitly excluding
anything resembling visitor telemetry (no MACs, no IPs, no message/
upload history, no user activity of any kind) — this supervisor has no
visibility into PirateBox's visitors at all today, and this feature
must never become the first thing that gives it any.

## 20. Onboard RGB LED — evaluated, not implemented

**Evaluated. Not implemented — the pin genuinely isn't known safely.**
This board's own PlatformIO manifest
(`~/.platformio/platforms/espressif32/boards/esp32-s3-devkitc-1.json`)
declares no LED pin at all (checked directly, not assumed) — unlike
some other ESP32-S3 board variants whose manifests do declare one.
Different real ESP32-S3 DevKitC-1 hardware revisions are known to wire
their onboard addressable RGB LED to different GPIOs (commonly GPIO38
or GPIO48 depending on revision) — guessing wrong would drive a pin
that might be wired to something else on this exact board entirely,
for a purely cosmetic feature. Per instruction: **if the exact GPIO/
type isn't safely known, don't guess.** If a future round can establish
this board's actual LED wiring by direct inspection or a manufacturer-
confirmed revision match (not a guess), the design intent would be:
off by default, subtle rather than bright/decorative, reserved for a
short palette of real supervisor states (booting, healthy, Pi
heartbeat lost, hardware fault) — never a duplicate of what the OLED
already shows, and never allowed to interfere with watchdog/timing/
sensor reliability (i.e., driven from the same non-blocking tick
pattern every other firmware feature already uses, never a blocking
animation loop).
