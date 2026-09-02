# Hardware Integration Design (Stage 11)

**Status: DESIGN ONLY for everything except one button.** No I2C/OLED
code exists on this Pi, and the toggle switch and four of the five
momentary buttons remain unwired. **The exception: GPIO25/physical pin
22 (the "hold-for-safe-shutdown" button) has been physically wired,
electrically bring-up tested, and has a working persistent
implementation** - see `docs/PHYSICAL-CONTROL-UX-DESIGN.md` §2/§3 and
the "Stage 29 Implementation: Physical Shutdown Button" entry in
`docs/OPERATIONAL-DECISIONS.md` for the full story, and the
authoritative wiring map in §2 below for current status of every pin.
Everything else in this document remains the plan to follow **only
when that hardware physically arrives and the operator explicitly says
to build it** - per instruction, this stage produced the design, not
the implementation, for the rest.

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
| I2C (`i2c_arm`) | Not yet enabled | `i2c_bcm2835` kernel module is loaded, but no `dtparam=i2c_arm=on` in config.txt and no `/dev/i2c-*` device exists yet. **GPIO2 (SDA1)/GPIO3 (SCL1) are free** - enabling I2C is a one-line config.txt addition when this stage is actually implemented. |
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
| OLED SDA | GPIO2 | 3 | Not wired | Fixed I2C1 function, not reassignable - reserved, do not use for anything else |
| OLED SCL | GPIO3 | 5 | Not wired | Fixed I2C1 function, not reassignable - reserved, do not use for anything else |
| Momentary button 1 | GPIO22 | 15 | Not wired | Cycle page (Stage 29 §2) |
| Momentary button 2 | GPIO23 | 16 | Not wired | Wake display (Stage 29 §2) |
| Momentary button 3 | GPIO24 | 18 | Not wired | Reserved, unassigned (Stage 29 §2) |
| Momentary button 4 | GPIO27 | 13 | Not wired | Reserved, unassigned (Stage 29 §2) |
| **Momentary button 5** | **GPIO25** | **22** | **WIRED, VERIFIED, IMPLEMENTED** | Hold-for-safe-shutdown (Stage 29 §3). Other leg on **physical pin 9 (GND)**. Electrical bring-up: idle HIGH, pressed LOW, clean debounce, 4.0s hold-trigger confirmed exact and non-repeating. Persistent `systemd` service: `piratebox-button.service` / `piratebox_button_daemon.py`. See `docs/OPERATIONAL-DECISIONS.md`. |

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

---

## 6. Likely packages

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
