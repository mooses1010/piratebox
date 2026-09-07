# Hardware Integration Design (Stage 11)

**Status: DESIGN ONLY for the toggle switch and four of the five
momentary buttons.** Two pieces of hardware now have working, physically
verified implementations: **GPIO25/physical pin 22 (the
"hold-for-safe-shutdown" button)** - see `docs/PHYSICAL-CONTROL-UX-
DESIGN.md` §2/§3 and the "Stage 29 Implementation: Physical Shutdown
Button" entry in `docs/OPERATIONAL-DECISIONS.md` - and, as of
2026-09-03, **the SSD1306 OLED display** - I2C1 enabled, the display
physically wired and confirmed responding at 0x3C, and
`piratebox-oled.service`/`piratebox_oled_daemon.py` implemented and
bring-up tested (see §5 and §12 below and `docs/CHECKPOINTS.md` for the
full record, including a real power-quality finding from the bring-up
session that is NOT an OLED defect - see §12). The authoritative wiring
map in §2 below reflects current status of every pin. Everything else
in this document remains the plan to follow **only when that hardware
physically arrives and the operator explicitly says to build it** -
per instruction, this stage produced the design, not the
implementation, for the toggle switch and the four remaining buttons.

Hardware this design targets (ordered, not yet connected as of 2026-09-01):
- MTS-101 SPST maintained ON/OFF toggle switch
- STARELO 12mm normally-open momentary buttons (qty 5)
- ELEGOO SSD1306 0.96" 128x64 I2C OLED display
- 2.54mm Dupont jumper wire, plus existing thin hookup/mod wire

Target hardware: **Raspberry Pi 3 Model B Plus Rev 1.3** (confirmed via
`/proc/device-tree/model` this session).

---

## 1. Current Pi configuration (verified live, this session)

This matters because pin/interface recommendations below are grounded in
what's *actually* enabled on this specific Pi, not generic assumptions:

| Interface | Status | Detail |
|---|---|---|
| Serial console (UART) | **ACTIVE** | `enable_uart=1` in `/boot/firmware/config.txt`; `serial-getty@ttyS0.service` is running. **GPIO14 (TXD0) and GPIO15 (RXD0) are in use** - do not reassign. |
| I2C (`i2c_arm`) | **ENABLED, 2026-09-03** | `dtparam=i2c_arm=on` uncommented in `/boot/firmware/config.txt` (persistent, survives reboot - confirmed). **Two-part enablement, not just the config.txt line**: the device-tree overlay alone only brings up the bus adapters (`/sys/bus/i2c/devices/i2c-1`, `i2c-2`) - the `i2c-dev` kernel module, which creates the actual `/dev/i2c-*` character device nodes, must also be loaded and persisted (`/etc/modules-load.d/i2c.conf`). Missing this second half is a well-known, easy-to-hit gap when doing it by hand instead of via `raspi-config`'s "Enable I2C" (which does both) - found and fixed live during this bring-up. `/dev/i2c-1` (GPIO2/SDA, GPIO3/SCL) confirmed present; `i2cdetect -y 1` confirmed the OLED responding at 0x3C, nothing else on the bus. |
| SPI | Not enabled | No `/dev/spidev*`. Not needed for this design (I2C only). |
| `/dev/gpiochip0` permissions | `crw-rw---- root:gpio` | **Any process in the `gpio` group can read/write GPIO without root** - see Security Boundary below, this changes the design from what a root-only assumption would require. |
| `gpio`/`i2c`/`spi` groups | Already exist | `moose` is already a member of all three (inherited from initial Pi setup, not something this project added). |

**Pins to never use for this project** (fixed/reserved function):
- **GPIO0 / GPIO1** - HAT EEPROM ID (`ID_SD`/`ID_SC`) - reserved by
  convention on every Pi, regardless of whether a HAT is attached.
- **GPIO14 / GPIO15** - UART, actively in use for the serial console on
  this Pi (confirmed above). Reassigning these would either silently break
  the serial console or require disabling it first - out of scope, avoid
  entirely.
- **GPIO2 / GPIO3** - reserved *for* the OLED's I2C bus (see below), not
  available for anything else once I2C is enabled.

---

## 2. GPIO pin assignments - the authoritative PirateBox wiring map

**This table is the one place to check both the physical-pin-to-BCM
mapping and current real-world status for every assigned PirateBox
control pin.** Everything except GPIO25's row is still tentative/not
wired - adjust freely before any physical build. Chosen from the Pi
3B+'s general-purpose pins with no special boot/hardware function,
avoiding everything in the "never use" list above.

| Function | GPIO (BCM) | Physical pin | Status | Notes |
|---|---|---|---|---|
| Normal/Emergency toggle | GPIO17 | 11 | Not wired | Input, internal pull-up, switch to GND |
| OLED SDA | GPIO2 | 3 | **WIRED, VERIFIED** | Fixed I2C1 function, not reassignable. OLED VCC on pin 1 (3.3V), GND on pin 14 - responds at address 0x3C, confirmed via `i2cdetect` and a real test frame written and visually confirmed 2026-09-03. |
| OLED SCL | GPIO3 | 5 | **WIRED, VERIFIED** | Fixed I2C1 function, not reassignable. See OLED SDA row - same bring-up. |
| DS3231 RTC + AT24C32 EEPROM | GPIO2/GPIO3 (shared) | 3/5 (shared) | **WIRED, VERIFIED - ROOT CAUSE OF FAILED FIRST TEST FIXED, SECOND TEST PENDING (2026-09-07)** | Same I2C1 bus/pins as the OLED above - multi-drop, no pin conflict, exactly as anticipated when this row was first written. Confirmed via `i2cdetect`: RTC at 0x68 (`UU` once driver-bound), its onboard EEPROM at 0x57 (not the same as, and no conflict with, the separate HAT-ID EEPROM bus on GPIO0/1). OLED (0x3c) confirmed unaffected throughout. **Production module has R4 (200 ohm charging resistor) removed and a CR2032 installed.** The first genuine total-power-loss test failed (chip came back at its factory default); root cause found and fixed - **the CR2032 had been installed upside down**, confirmed by measurement (~3.0V at the holder with Pi power fully off, both before/after matching), which also rules out R4's removal as a cause. See `docs/RTC-TIME-READINESS-DESIGN.md` §§9-10. Do not treat this row as "battery-backed, confirmed" until a **second** real power-loss test passes. |
| Momentary button 1 | GPIO22 | 15 | Not wired | Cycle page (Stage 29 §2) |
| Momentary button 2 | GPIO23 | 16 | Not wired | Wake display (Stage 29 §2) |
| Momentary button 3 | GPIO24 | 18 | Not wired | Reserved, unassigned (Stage 29 §2) |
| Momentary button 4 | GPIO27 | 13 | Not wired | Reserved, unassigned (Stage 29 §2) |
| **Momentary button 5** | **GPIO25** | **22** | **WIRED, VERIFIED, IMPLEMENTED, FULL POWER-CYCLE TESTED** | Hold-for-safe-shutdown (Stage 29 §3). Other leg on **physical pin 9 (GND)**. Electrical bring-up: idle HIGH, pressed LOW, clean debounce, 4.0s hold-trigger confirmed exact and non-repeating. Persistent `systemd` service: `piratebox-button.service` / `piratebox_button_daemon.py`. Real hold-to-shutdown, on standalone wall-brick power, taken all the way through poweroff and a clean automatic reboot with the service self-arming - see `docs/OPERATIONAL-DECISIONS.md` ("Stage 29 Real-Hardware Confirmation"), which also flags that wall brick's power headroom as an open question, unrelated to the button logic itself. **2026-09-04:** the same button's short press (released before the 4.0s threshold) now also writes a temporary "show real OLED status" signal - see `docs/OPERATIONAL-DECISIONS.md` → "OLED cadence rebalance + short-press status-check override" for the full design and the mandatory long-hold/short-press mutual-exclusion guarantee; the hold-to-shutdown path itself is unchanged. **2026-09-04 (later the same day):** a double tap on this same button now toggles Silly Mode on/off, with its own gesture-discrimination window sitting alongside the single-tap/long-hold logic above - see `docs/OPERATIONAL-DECISIONS.md` → "Double-tap Silly Mode toggle (physical button)"; the shutdown and single-tap paths are both unchanged. |

All buttons: input, internal pull-up, normally-open switch to GND (button
press = pin reads LOW) - identical electrical pattern to the toggle
switch, just five more of them. This keeps the wiring concept uniform:
every switch/button on this device is "GPIO input, internal pull-up,
other leg to GND," no external resistors needed anywhere. **Note found
during GPIO25's bring-up, worth remembering for the rest:** the Pi's
own hostname/HAT-EEPROM pins aside, it's easy to accidentally wire both
switch legs to GND (physically adjacent pins can look alike at a
glance) - always verify the *specific* physical pin each lead lands on
against this table before assuming a connection is correct, not just
that "one side reads GND-ish."

---

## 3. Normal/Emergency toggle switch

Already partially designed during the Emergency Mode software-foundation
phase (this document formalizes and completes it now that real hardware
details exist).

**Electrical:** GPIO17 configured as input with internal pull-up enabled
in software. Switch OFF = pin floats high (pulled up) = **Normal**.
Switch ON = pin shorted to GND = **Emergency**. This matches the
maintained (latching) nature of an SPST toggle - the pin state directly
and continuously reflects the physical switch position, not a momentary
pulse.

**Software:** a small, always-running daemon (see §7, "GPIO daemon")
reads GPIO17's level. Because this is a *maintained* switch (not a
momentary button), the read is a simple level check, not edge/interrupt
detection - there's no "press and release" to catch, just "what position
is it in right now." This is inherently simpler and more robust than
momentary-button handling.

**Debounce:** mechanical bounce on a toggle switch lasts a few
milliseconds at the moment of flipping. The daemon debounces by requiring
the read level to be **stable for a short confirmation window (proposed:
50-100ms)** before accepting it as a real change - e.g. using
`gpiozero`'s `Button` class with its built-in `bounce_time` parameter
(see §6), rather than hand-rolled polling logic. A `gpiozero`-style
debounced input also means the daemon reacts to a real flip within
roughly that same window, comfortably fast for a switch a human just
physically moved - no need for faster response than that.

**On a confirmed, debounced, real transition**, the daemon:
1. Atomically rewrites `/tmp/piratebox/mode` (same file, same
   temp-file-then-`rename()` technique `set_piratebox_mode.sh` already
   uses - see §8, "Coexistence").
2. Logs the transition once.
3. (Future, once SSID switching is implemented - see §9 - triggers the
   hostapd config swap, but only on this confirmed transition, never
   speculatively.)

**Boot behavior - "physical switch should ultimately be authoritative":**
the daemon does an **immediate read of GPIO17 at startup**, before doing
anything else, and writes that as the initial mode state right away - not
waiting for a future change to happen. Combined with starting the daemon
early in boot (a systemd service ordered after `local-fs.target` but not
dependent on network/AP services being up first), this satisfies the
requirement directly: *"if the box is switched to EMERGENCY before
powering on, it boots into Emergency Mode."* Until that first read
completes (a fraction of a second after boot), the existing fallback
already handles the gap correctly - see §8.

---

## 4. Momentary buttons (5x STARELO 12mm)

**Functions deliberately NOT assigned yet**, per instruction. Candidate
uses, to decide on when the hardware is in hand and can be tested:

- **Wake/refresh the OLED display** (if it sleeps/dims to save power)
- **Next display page** (cycle through OLED status screens - see §5)
- **Select/action** (context-dependent, paired with whatever page is showing)
- **Show network/AP info** (jump straight to a specific OLED page)
- **Hold-for-safe-shutdown** (see below) - tentatively GPIO25, the button
  physically nearest the edge of a panel layout in most enclosure
  concepts, but this is a placement guess, not a decision

**Hold-for-safe-shutdown concept:** a single button held for a deliberate
duration (proposed: 3-5 seconds continuous, to avoid an accidental tap
shutting down the box) triggers `sudo systemctl poweroff` (or equivalent)
via the same narrowly-scoped-daemon pattern already used for mode
switching - **not** a new broad sudo grant. This needs its own explicit
design pass when actually built (debounce-for-duration is a different
pattern than debounce-for-level-change), and should almost certainly
include an OLED confirmation ("Hold to shut down... 3... 2... 1...") so
it's never a silent/surprising action - flagged here as a requirement for
that future pass, not solved yet.

**Debounce:** same `gpiozero`-style `bounce_time` approach as the toggle,
but momentary buttons additionally need **press/release edge detection**
(not just level reads) since a "tap" is inherently an event, not a
state - `gpiozero`'s `Button.when_pressed`/`when_released` callbacks
handle this directly and already include debouncing.

---

## 5. OLED status display (SSD1306 128x64 I2C)

**Built and physically verified 2026-09-03 - see §12 for the full
bring-up record and `piratebox_oled_daemon.py` for the implementation.**
The content plan below has since been superseded by the more detailed,
already-implemented page design in `docs/PHYSICAL-CONTROL-UX-DESIGN.md`
§1 (four pages - Status/Time/Network/Health - rather than the two mode-
specific layouts sketched here); this section's original reasoning is
kept for context, not because the layouts below are what's running.

**Never required for operation** - if the daemon driving it crashes, is
disabled, or the display is unplugged, the PirateBox continues operating
exactly as it does today. This is a hard requirement, not a goal: the
display daemon must be a pure, isolated consumer of existing state, never
a dependency of anything else.

**Content plan**, matching the two example layouts already discussed:

Normal Mode:
```
PIRATEBOX
NORMAL

SSID: PirateBox
IP: 10.0.0.1
Clients: 3
Storage: 107G free
```

Emergency Mode:
```
EMERGENCY NODE
MODE: EMERGENCY

SSID: [not yet chosen]
Clients: 3
IP: 10.0.0.1
```

**Data sources - all already exist, nothing new to build for the data
itself:**
- Mode: `/tmp/piratebox/mode` (same file everything else already reads)
- SSID, client count, per-service health, undervoltage: **already
  produced every 30s** by the existing `piratebox_status_helper.sh` →
  `/run/piratebox/status.json` (Phase 4) - the OLED daemon would just read
  this same file, not duplicate its logic or add new privileged reads.
- Storage free/total: same `disk_free_space()`-equivalent data the admin
  page already computes - the OLED daemon can read this directly (plain
  filesystem calls, no privilege needed) rather than depending on the
  status helper for it.
- IP address: static (`10.0.0.1`), already known/fixed by this project's
  network design - no lookup needed.

**Future additions mentioned in the stage instructions** (uptime, battery
info if available, AP status) - uptime is already read by the admin page
(`/proc/uptime`) and trivially available to an OLED daemon the same way;
battery/mains status depends entirely on Stage 12's future power hardware
and cannot be designed further until that hardware is chosen.

**Silly Mode (added 2026-09-04):** a user-toggleable (`piratebox-silly
{on,off,status}`), substantially more expressive face/personality layer,
layered entirely inside `piratebox_oled_daemon.py` on top of the four
pages above - never a fifth *operational* mode, and always subordinate
to Emergency Mode / a real fault (see `compute_display_tier()`). Full
design and rationale: the daemon's own "SILLY MODE" header comment and
`docs/OPERATIONAL-DECISIONS.md` → "OLED Silly Mode". Not documented
further in this file per this section's own established convention
(implementation detail lives in the script; this file stays at the
hardware/architecture level). **2026-09-04:** rebalanced to alternate
with a genuine status interlude (not a one-tick peek) on a deliberate
cadence, and made interruptible on demand by the shutdown button's
short press - see `docs/OPERATIONAL-DECISIONS.md` → "OLED cadence
rebalance + short-press status-check override". Also user-toggleable
by a double tap on that same physical button now, as an alternative to
the `piratebox-silly on`/`off` CLI (both control the exact same state) -
see `docs/OPERATIONAL-DECISIONS.md` → "Double-tap Silly Mode toggle
(physical button)". **2026-09-04 (Expression Engine v2):** the face/
animation drawing primitives and their data tables moved out of the
daemon into their own module (`piratebox_expressions.py`), gained
multi-frame animation (played as a brief, bounded synchronous burst -
the display's redraw cadence itself is unchanged), a richer eye/
decoration vocabulary, and a personality-mannerism layer that lets the
existing sociability/vigilance/resilience weights actually influence
which ambient variant shows. `piratebox-silly preview` is a new,
operator-only physical-validation command that demos a fixed, non-
secret sampler on the real display. See `docs/OPERATIONAL-DECISIONS.md`
→ "Expression Engine v2" for the full architecture; per that entry's
own spoiler policy, the new visual catalog itself isn't enumerated
here either. **2026-09-04 (Distance/Glance Display):** a large-format,
at-a-distance presentation layer (`piratebox_glance.py`) - a handful of
one-question-at-a-time pages (CPU, RAM, disk, client count, uptime,
time, the chronic power warning) shown in large centered text,
interleaved with both the Silly-on and Silly-off rotations via an
evolved (2→3-phase) cadence, never a separate operational mode.
`piratebox-silly glance-preview` is the equivalent operator-only
physical-validation command for this layer. See `docs/OPERATIONAL-
DECISIONS.md` → "Distance / Glance Display" for the full architecture.

**Progression (added 2026-09-04):** a persistent XP/level/title/
achievement/history layer underneath Silly Mode, in its own module
(`piratebox_progression.py`) - durable state at `/var/lib/piratebox-
oled/progression.json` (the one narrow `ReadWritePaths` exception this
otherwise-read-only daemon has), surviving reboot and Silly Mode being
off. Full design: `docs/OPERATIONAL-DECISIONS.md` → "PirateBox
Progression". **Relevant to this file specifically:** Progression
defines a `HARDWARE_SIGNALS` registry (`register_hardware_signal()` /
`read_hardware_signals()`) as the intended future integration point for
this section's own not-yet-commissioned hardware - the DS3231 RTC
(§ RTC-TIME-READINESS-DESIGN.md), INA226 power telemetry, BME280
environmental sensor, DS18B20 temperature probes, BH1750 ambient
light, a future addressable-RGB status light, and a future GPS/travel
capability. **Nothing in that registry is populated yet** - per
instruction, no reading is fabricated for hardware that isn't wired and
confirmed. When any of the above is actually commissioned, registering
its reader there (and, if wanted, a few new achievements/events keyed
off it) is the intended extension path - no change needed to
Progression's own engine.

**Captain's Log web profile (added 2026-09-04):** a read-only site page
(`/utility/captains-log/`) presenting Progression's data to visitors -
see `docs/OPERATIONAL-DECISIONS.md` → "Captain's Log web profile" for
the full design, including the `open_basedir` boundary it added (one
new named file, not a directory widening) to let PHP read Progression's
already-curated public export. The same empty `HARDWARE_SIGNALS`
registry flows through to this page automatically - no template change
needed once real hardware is commissioned and registered.

---

## 6. Likely packages

**`python3-luma.oled` and `i2c-tools` installed 2026-09-03 - see §12.**

**Checked live this session (`dpkg -l`/`apt-cache search`), not assumed:**

| Package | Purpose | Status on this Pi, right now |
|---|---|---|
| `python3-gpiozero` (2.0.1) | GPIO input handling (toggle + buttons); built specifically for "button/switch to GND with pull-up" wiring, debounce (`bounce_time`) built in | **Already installed** |
| `python3-lgpio` (0.2.2) | gpiozero's pin-factory backend on modern Raspberry Pi OS (the older `RPi.GPIO` is legacy) | **Already installed** (as an automatic dependency) |
| `python3-smbus2` (0.4.3) | I2C bus communication | **Already installed** |
| `python3-luma.oled` | SSD1306 display driver + simple drawing API, standard/widely-used for exactly this display | **Not installed** - confirmed available in apt (pulls in `python3-luma.core` and Pillow automatically) |
| `i2c-tools` | `i2cdetect`/`i2cget` - one-time bring-up confirmation that the display responds at its address (typically `0x3C`), not needed at runtime | **Not installed** - confirmed available in apt |

**The GPIO half of this design (toggle switch + momentary buttons) needs
zero new packages** - the full stack is already present. Only the
OLED-specific piece (`python3-luma.oled`, optionally `i2c-tools` for
bring-up) would need `apt install` when that part is actually built. Per
instruction, no installation happens now - this table reflects current
status, checked directly, not what will eventually be requested.

---

## 7. systemd/service architecture

**`piratebox-oled.service` implemented and running 2026-09-03 - see
§12.** The GPIO daemon (`piratebox-gpio.service` below) remains design-
only; only the OLED half of this section is built.

Two new services, following the exact hardening pattern already
established and approved for `piratebox-status.service`/`.timer` (Phase
4) and the Emergency Mode automation (this project's own precedent, not a
new convention invented here):

**`piratebox-gpio.service`** (the "GPIO daemon" referenced throughout this
doc) - always-running (not a timer, since button presses/switch flips are
events, not something to poll every 30s):
- Reads GPIO17 (toggle) continuously via `gpiozero` callbacks; on a
  confirmed, debounced transition, atomically rewrites
  `/tmp/piratebox/mode`.
- Reads the 5 momentary buttons via `gpiozero` callbacks; dispatches to
  whatever function each is assigned once that's decided (§4).
- Hardened via systemd: `NoNewPrivileges=true`, `ProtectSystem=strict`,
  `ProtectHome=true`, `PrivateTmp=false` (it specifically needs to write
  `/tmp/piratebox/mode` - tmpfs `/tmp` is intentionally shared, not
  private, for this one service), no network access needed
  (`PrivateNetwork=true` is a candidate), takes no external input of any
  kind (no arguments, no request handling).
- Ordered to start early in boot (`After=local-fs.target`,
  independent of `network.target`/`hostapd.service`) so the toggle's
  initial read happens as early as possible - see §3's boot-behavior
  requirement.

**`piratebox-oled.service`** - separate, always-running:
- Reads `/tmp/piratebox/mode` and `/run/piratebox/status.json` (both
  already-existing, already-read-only-consumed files - no new privileged
  reads needed) on a short interval (proposed: every 2-5 seconds, cheap
  file reads) and redraws the display.
- Deliberately a **separate service from the GPIO daemon** - a crash or
  bug in display rendering (a genuinely more complex code path, involving
  Pillow/font rendering) must never be able to affect mode-switching
  reliability, and vice versa. Same "narrow, single-purpose, don't couple
  unrelated concerns" principle the Emergency Mode design already applied
  when it kept the (future) GPIO daemon separate from the existing stats
  helper.
- Hardened the same way; additionally needs `SupplementaryGroups=i2c` (or
  runs as a user already in the `i2c` group - see §8) to reach
  `/dev/i2c-1`.

Both services `Restart=on-failure` (not `Restart=always` - unlike
hostapd's documented exception, there's no known failure mode here that
produces a "clean exit that isn't actually a failure," so the simpler
default is appropriate unless real-world testing says otherwise, mirroring
this project's own documented lesson about not adding restart-loop
complexity speculatively).

---

## 8. Security boundary (revised from earlier planning, based on this
session's verified findings)

Earlier discussion (before hardware/pin details were checked) assumed the
GPIO daemon would need to run as root, mirroring
`piratebox_status_helper.sh`. **This session's live check of
`/dev/gpiochip0` found it's `root:gpio` with group read/write** - meaning
GPIO access itself does **not** require root; a process only needs
membership in the `gpio` group (and `i2c` for the OLED). This is a
meaningful narrowing opportunity worth designing in from the start:

**Proposed: a dedicated, unprivileged service account** (e.g.
`piratebox-hw`, created with `useradd --system --no-create-home`), member
of the `gpio` group (both services) and `i2c` group (OLED service only) -
**not** `sudo`, **not** root, **not** a member of any other group. This
account can read GPIO and the I2C bus directly, and read the
already-world-readable `/run/piratebox/status.json`, with zero privilege
beyond that.

**The one gap this doesn't close on its own:** writing
`/tmp/piratebox/mode` currently requires root, because
`set_piratebox_mode.sh` creates `/tmp/piratebox/` as `root:root 0755` (only
root can create new entries in it). Two options when this is actually
built, to decide then rather than now:
1. **Keep the GPIO daemon's mode-writing path root** (simplest: run just
   `piratebox-gpio.service` as root, matching the existing
   `piratebox_status_helper.sh` precedent exactly, accepting that as the
   one already-approved trust tier this project uses for "small, narrow,
   input-free, systemd-hardened root daemons"), while still moving the
   **OLED service** (which never needs to write anything, only read) to
   the fully unprivileged `piratebox-hw` account. This is the pragmatic
   default recommendation - it needs no permission-model changes to
   `/tmp/piratebox/`, and root-for-this-one-narrow-purpose is a pattern
   already reviewed and accepted in this project (Phase 4's status
   helper).
2. **Widen `/tmp/piratebox/` to `root:gpio 0775`** so a `gpio`-group
   member can also create/rename files there, letting the GPIO daemon run
   fully unprivileged too. Rejected as the default recommendation: it
   would mean *any* process ever added to the `gpio` group (now or later,
   for an unrelated reason) gains the ability to flip the site's
   presentation mode, which is a broader blast radius than "one specific
   root-owned script/daemon does exactly this one thing" - the current
   `set_piratebox_mode.sh` model. Worth revisiting only if a concrete
   reason to minimize root usage further emerges later.

**Recommendation: option 1.** Document this choice explicitly when the
stage is actually implemented, the same way this document explains it now
- don't silently pick one without a written reason, per this project's
established convention (see `OPERATIONAL-DECISIONS.md`).

Neither service ever touches PHP, nginx, `open_basedir`, or
`disable_functions` - this is entirely separate from the web tier's
existing security boundary, consistent with how the web tier only ever
*reads* `/tmp/piratebox/mode` today and would continue to.

---

## 9. Coexistence with the current mode-state mechanism

**No change needed to `includes/mode.php` or `piratebox_get_mode()`** -
the GPIO daemon would write the exact same file
(`/tmp/piratebox/mode`, plain text, `normal`/`emergency`) via the exact
same atomic temp-file-then-`rename()` technique `set_piratebox_mode.sh`
already uses. The web tier already treats this file's producer as opaque
- it doesn't know or care today whether a human ran the script or (in the
future) the GPIO daemon wrote it, and that stays true. `set_piratebox_mode.sh`
itself remains useful indefinitely after the GPIO daemon exists, as the
manual override/testing tool it already is - not replaced, just no longer
the *only* writer.

**Fallback behavior is unaffected and already sufficient:** every
failure case the GPIO daemon could hit (crashed, disabled, never
installed, hardware unplugged) looks identical to "the switch was never
wired up," which the site already handles correctly today - missing file
→ `normal`. No new fallback logic is needed in the web tier for this
stage; the existing design already anticipated it.

---

## 10. Future SSID switching (design only, still not implemented)

Reconfirms and slightly refines the plan already sketched during the
Emergency Mode foundation phase, now that pin/service details exist
alongside it:

- Two fully static, tracked config files -
  `etc/hostapd/hostapd-normal.conf` and `etc/hostapd/hostapd-emergency.conf`
  - identical except the `ssid=` line (and possibly `channel=`, if a
  future range-optimization decision picks different channels per mode -
  not decided).
- **`piratebox-gpio.service` is the only trigger point** - on a confirmed,
  debounced mode transition (never on every GPIO poll, never
  speculatively), it would: copy the correct static file over
  `/etc/hostapd/hostapd.conf` and restart hostapd, then check
  `systemctl is-active hostapd` immediately after. **Correction from an
  earlier draft of this document:** this installed hostapd (v2.10) has no
  dry-run/config-test flag - `hostapd -h` was checked directly this
  session, and its only `-t` option is "include timestamps in debug
  messages," not validation (verified rather than assumed, since an
  earlier pass through this design incorrectly cited `hostapd -t` as a
  config-check flag). Real hostapd failures (a bad channel for the
  regulatory domain, a driver rejecting a parameter) often only surface
  once it actually tries to bring the interface up, not from static
  parsing anyway, so **apply-then-verify-then-rollback** is both the only
  available approach and arguably the more reliable one: if `hostapd`
  fails to reach `active` within a short window, immediately restore the
  previous static config file and restart again, logging the failure
  clearly. This is the "rollback if a new configuration fails"
  requirement, implemented as revert-on-detected-failure rather than
  validate-before-applying, since the latter isn't available here.
- Rate-limited the same way hostapd's own crash recovery already is
  (`StartLimitBurst`/`StartLimitIntervalUSec`) - a genuine mode flip is a
  rare, deliberate physical action; nothing about this design should be
  able to restart hostapd in a tight loop.
- **No Emergency SSID has been chosen** - explicitly deferred, per
  instruction, to a separate conversation with the operator when this is
  actually built.
- Restarting hostapd briefly disconnects every associated Wi-Fi client -
  unavoidable and expected for an actual SSID change, and acceptable
  specifically because it only ever happens on a deliberate physical
  switch flip, not a background process.

---

## 11. Future testing procedure (when hardware arrives)

Mirrors the hardware-optional testing approach already used successfully
for the Emergency Mode software foundation (`set_piratebox_mode.sh` let
the entire mode system be built and tested before any switch existed):

1. **Before any wiring:** unit-test the GPIO daemon's debounce logic using
   `gpiozero`'s `Device.pin_factory = MockFactory()` - simulates pin
   transitions (including simulated bounce) entirely in software.
2. **Bring-up, isolated:** wire one component at a time on a breadboard
   (not the final enclosure) - confirm the toggle switch alone first
   (read GPIO17 state changes with a simple test script, no systemd
   service yet), then the OLED alone (`i2cdetect -y 1` confirms it
   responds at its address, then a minimal luma.oled "hello world" before
   any real content), then one button at a time.
3. **Integration on a test SSID:** if/when SSID switching is built,
   validate it against a temporary, isolated test AP name first (never
   the production `PirateBox` SSID), the same discipline already
   documented for the Wi-Fi adapter evaluation work (`PirateBox-USB-Test`
   precedent in `OPERATIONAL-DECISIONS.md`).
4. **Only after each piece is individually confirmed working**, install
   the real systemd services and test end-to-end: flip the physical
   switch with the Pi already running (confirms live transition), then
   power off, flip the switch, power on (confirms the boot-time
   authoritative-read requirement from §3).
5. **Failure-injection, matching Stage 10's methodology:** stop each new
   service individually and confirm the site keeps working normally
   (mode falls back to Normal, OLED simply goes blank/stale) - the same
   "prove the fallback, don't just assume it" discipline already applied
   throughout this project.

## 12. OLED bring-up record (2026-09-03)

The plan in §5-§8 above is now built and physically verified, not just
designed. Recorded here rather than rewriting §5-§8 into past tense
throughout, so the original design reasoning stays intact alongside
what actually happened.

**I2C enablement - two real gotchas found, both fixed persistently:**
1. `dtparam=i2c_arm=on` uncommented in `/boot/firmware/config.txt`
   (backed up first: `config.txt.pre-i2c-bak`). This alone brought up
   the bus adapters (confirmed via `/sys/bus/i2c/devices/`) but did
   **not** create `/dev/i2c-*` - a genuinely easy thing to miss doing
   this by hand instead of via `raspi-config`.
2. The `i2c-dev` kernel module (the character-device frontend) was
   missing and had no autoload entry. Fixed with `modprobe i2c-dev`
   (immediate, no reboot needed for this half) plus a persistent
   `/etc/modules-load.d/i2c.conf` entry so it survives every future
   boot without repeating this step.

**Hardware verified, not assumed:** `i2cdetect -y 1` found the display
at `0x3C` (the expected default SSD1306 address) with nothing else on
the bus (bus 2, the internal HDMI-only bus, confirmed empty as a
non-conflict sanity check). A real frame was written via `luma.oled`
(full-white flash, then a bordered test-pattern frame) and visually
confirmed by the operator on the physical screen - address response
alone was deliberately not treated as proof the display works.

**Packages installed (§6's candidates, confirmed via apt):**
`i2c-tools` (4.4-2), `python3-luma.oled` (3.10.0-1, pulled in
`python3-luma.core` 2.4.2-1 and `python3-pil` 11.1.0-5 automatically).
`python3-gpiozero`/`python3-lgpio`/`python3-smbus2` were already
installed, as §6 predicted - no GPIO-side packages were needed for
this OLED-only bring-up.

**Service architecture matches §7's design closely, one naming note:**
`piratebox-oled.service` is implemented exactly as designed (separate
from any button/GPIO service, `Restart=on-failure`, hardened). It runs
as the existing `piratebox-gpio` system account (the same one
`piratebox-button.service` already uses) with `SupplementaryGroups=i2c`
added, rather than creating the separate `piratebox-hw` account §8
sketched - reusing the account that already exists rather than adding
a second one, since both are the same "unprivileged, gpio-group,
narrowly-scoped hardware daemon" trust tier §8 itself argued for.

**No sudoers grant needed for this daemon** - unlike
`piratebox-button.service`, the OLED daemon has no privileged action to
escalate to (it only reads already-world-readable files and writes to
the display), so §3's "OLED daemon needs its own sudoers grant" note
never applied here; that was specifically about button daemon actions,
not the display itself.

**A real, currently-active power-quality finding from this session -
NOT an OLED defect:** immediately before this bring-up, the operator
reconnected the OLED wiring while the Pi was powered on, then observed
SSH become extremely slow and the existing GPIO25 hold-to-shutdown not
trigger, ultimately requiring a hard power cycle. Investigated on the
next boot, before any I2C work resumed:
- `piratebox-button.service` came back up clean and healthy on the new
  boot - no evidence of a software defect in the button daemon itself.
- No previous-boot journal was available to examine the actual stall
  (`journalctl --list-boots` showed only the current boot) - `/var/log/
  journal` exists but was never actually initialized for persistent
  storage on this system, a pre-existing gap unrelated to this
  incident, so the volatile (`/run`-only) journal was lost on the hard
  power-cut. Worth fixing at some point for future diagnosability, not
  addressed in this pass.
- `vcgencmd get_throttled` returned `0x50005` on the fresh boot -
  **under-voltage detected right now**, and throttling had occurred
  since boot, confirmed again by 4 separate "Undervoltage detected!"
  kernel log lines in the first ~4 minutes of uptime. This condition
  was already flagged as an open question about the wall-brick power
  source during the original GPIO25 bring-up (§8's cross-reference,
  `docs/OPERATIONAL-DECISIONS.md`) - it is not new, but it has now
  plausibly manifested seriously enough to explain the SSH slowness and
  the button's non-response (CPU throttling can starve any process's
  scheduling, this daemon included, without indicating a defect in it).
- Filesystem, systemd units, and dmesg were otherwise completely clean
  (no ext4/mmc errors, zero failed units, no USB/network errors) - this
  is specifically and only a power-supply headroom problem, not a
  broader hardware or software fault.
- **This remains an open, unresolved condition on this specific power
  source**, exactly as already flagged in `docs/CAPABILITY-REGISTRY.md`'s
  "Undervoltage / power-quality monitoring" entry - not resolved by
  this bring-up, and explicitly not attributed to the newly-added OLED
  (the OLED's own current draw is a few mA, well within what any
  correctly-speced 5V/2.5A+ supply should handle; the undervoltage
  condition was observed on this same boot before the daemon was even
  running).

**Live installation on this Pi** (not yet reflected in a merged commit
at design-doc-write time - see `docs/CHECKPOINTS.md` for the exact
sequence and verification): `piratebox_oled_daemon.py` installed to
`/usr/local/bin/`, `piratebox-oled.service` installed to
`/etc/systemd/system/`, `piratebox-gpio` added to the `i2c` group,
service enabled and started, confirmed rendering all four pages in
rotation on the physical display.

## 13. Personality/idle mode (added round 7, 2026-09-03)

The enclosure is not built yet, so the OLED sits exposed on the desk.
`piratebox_oled_daemon.py` gained a small, explicitly bounded
personality layer on top of the four serious pages above - this is a
side feature while the hardware is visible, not an OLED redesign, and
the serious pages (§5-§12) are unchanged and remain the priority.

**What it does:** roughly once every 6 full page rotations (~3
minutes), the normally-scheduled "status" slot is replaced for that
one rotation by a short pirate-flavored quip next to a small
procedurally-drawn skull-and-crossbones (plain Pillow `ellipse`/
`polygon`/`rectangle`/`line` calls - no image asset, no new font, no
animation library). Two one-shot frames can briefly preempt whatever
is showing: a "client boarded" frame when `status.json`'s
`wifi_clients` count rises, and a one-time uptime milestone message at
1 day and 1 week of continuous runtime.

**Gated, every single time, by `personality_allowed()`** - checked
fresh on every tick, never cached: refuses to show anything frivolous
whenever mode is Emergency, `status.json` is stale, any Core service
is down, or `undervoltage_now` is true. This was verified against this
Pi's own currently-live status (`0x50005`, `undervoltage_now: true`,
the open condition tracked in `docs/CAPABILITY-REGISTRY.md`) - the
gate correctly suppresses all personality behavior under the exact
real degraded condition this hardware is in right now, not just a
synthetic test case.

**Zero new state:** the rotation counter, last-seen client count, and
which milestones have already fired all live in plain local variables
inside `main()`'s loop - nothing is written to disk, so a service
restart simply resets the "occasional" timer and re-allows milestones
that already fired this run. No new tracking of individual clients or
devices was added; the celebration frame reads the same aggregate
`wifi_clients` count the status page already displays.

**Everything else about the daemon is unchanged:** same retry/degraded
behavior on lost hardware, same unprivileged `piratebox-gpio` account,
same read-only access to already-world-readable files, same trivial
CPU/RAM footprint (one extra dict lookup and, at most, a few more
Pillow draw calls per tick - no added polling, no new files touched).
Core has no dependency on this daemon before or after this change.

Tested offline (module functions exercised directly against an
in-memory image, including the gating checks above) rather than by
running a second process against the physical I2C bus, since
`piratebox-oled.service` was already active on this device at the time
and a duplicate process opening the same bus was avoidable risk for no
real benefit. Installing the updated daemon onto the running Pi still
requires the operator's usual `sudo install` + `systemctl restart`
step (this session cannot run `sudo`) - see `docs/CHECKPOINTS.md`.

## 14. Instrument-panel polish (round 8, 2026-09-03)

Round 7's four serious pages (Status/Time/Network/Health) worked but
looked like plain debug text dumps. This round improves how they
present, without changing what they're allowed to show or when -
personality mode (§13) is unchanged, including its gating.

**Philosophy, stated once so it governs every choice below:** mostly
static information plus brief, meaningful motion. Animation exists to
communicate an actual state change, never just because it's possible.

**What changed, all still plain Pillow primitives, no new
dependency:**
- **Header bar**: every serious page now opens with an inverted
  (white-bar, black-text) title strip carrying a small ~10x10px
  procedural icon (a diamond for Status, a clock face for Time, a
  small antenna for Network, a heartbeat zigzag for Health) and a
  heartbeat dot in the top-right corner that flips filled/hollow every
  redraw tick - proof the loop is alive and refreshing, not frozen,
  without adding any new data source (it's driven by the daemon's own
  existing per-tick counter).
- **Status page**: a small Wi-Fi bars glyph (filled when at least one
  client is associated, outline when none are) replaces a bare number
  as the "is anyone connected" glance. The client count itself briefly
  renders inverted (measured via `draw.textbbox` so the box fits any
  digit count) for the couple of redraws right after it increases -
  this pulse is plain operational information, so it is **not**
  personality-gated and still fires in Emergency Mode or under a
  degraded condition, unlike the separate, gated "celebration" page
  personality mode already had.
- **Network page**: a small filled/hollow dot per Core service next to
  its (truncated) name, alongside the existing "N/4 up" text - a
  glance shows *which* service is down, not just the count.
- **Health page**: the storage line gained a compact horizontal
  used-space bar next to the existing free/total text. The undervoltage
  warning (unchanged condition/wording) is now boxed - a warning should
  look different from routine information, not just say so in smaller
  words. Verified this box actually renders against this Pi's own real,
  current `0x50005` condition, not just a synthetic fixture.
- **Page-change wipe**: a brief (~150ms, four extra frame writes)
  horizontal slide plays when the display auto-advances from one
  serious page to the next in the normal rotation - the only recurring
  motion in the whole daemon, and it only ever fires on an actual page
  change (once per `PAGE_SECONDS`, currently 8s), never on a same-page
  data refresh (every `REFRESH_SECONDS`, 3s) and never for a one-shot
  frame (personality/celebration/milestone/mode-transition), which all
  still swap instantly. Implemented by bypassing `luma.core.render.
  canvas()` for a lower-level `device.display(image)` call so two
  already-rendered frames (previous/next) can be cropped and pasted
  into a handful of intermediate composites - no animation library, no
  persistent per-frame state, each transition is a short, self-
  contained burst of extra I2C writes that ends before the next
  `REFRESH_SECONDS` tick.
- **Mode-transition banner (new)**: a brief, full-screen, inverted
  frame ("EMERGENCY MODE / ACTIVATED" or "NORMAL MODE / RESTORED")
  appears exactly once, the moment this daemon observes `MODE_FILE`'s
  value actually change. Deliberately **not** personality-gated - which
  mode is active is serious operational information, so this still
  shows in Emergency Mode and under a degraded condition (arguably more
  important then, not less).

**Refactor this required:** `render_page()` (round 7) drew directly
into a `canvas(device)`-managed image and returned nothing. It's now
`build_frame(...)`, a pure function that returns a standalone `PIL.
Image` without touching the display, plus a separate `display_frame
(device, new_img, old_img, transition)` that does the actual write
(with or without the wipe). This split is what makes the wipe possible
(it needs both the outgoing and incoming frame at once) and, as a side
benefit, makes `build_frame()` trivially unit-testable offline - no
real device object needed, just anything with `.mode`/`.size`
attributes matching the real `ssd1306`.

**Unaffected by this round, confirmed rather than assumed:**
`personality_allowed()`'s gating logic is byte-for-byte unchanged from
round 7 and was re-tested against this Pi's own real, current
undervoltage condition - still correctly suppresses every personality
frame. The retry/degraded-hardware behavior, the unprivileged
`piratebox-gpio` service account, and Core's total independence from
this daemon are all untouched. CPU/RAM cost remains trivial - the wipe
adds at most 4 extra small (128x64, 1-bit) frame writes once every 8
seconds, not a continuous loop.

**Tested offline** the same way round 7's personality mode was: a fake
device object (`.mode`/`.size` only, no real I2C) exercising
`build_frame()` for every page type (including stale/missing status),
the pulse effect, `display_frame()`'s frame-count with and without the
transition, and `personality_allowed()` against this Pi's actual live
`status.json`. Not yet installed on the running Pi - requires the
operator's usual `sudo install` + `systemctl restart` step, same as
every prior OLED daemon update.
