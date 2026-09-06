# Radio / SDR Capability — Investigation & Architecture (2026-09-04, revised 2026-09-05)

**Status: INVESTIGATION ONLY. Nothing in this document has been
installed, wired, or deployed.** No SDR package, driver, service, or
systemd unit has been added; Nginx/hostapd/dnsmasq/nftables are
unchanged; no hardware has been connected to the Pi. This document
exists to answer "is this possible, and if so how should it be built"
before any of that happens - see `docs/CAPABILITY-REGISTRY.md`'s own
SDR entry for the one-line current state, and §11 below for the
physical hardware gate that comes next.

**2026-09-05 correction, read this before anything else below:** the
owned receiver is **not confirmed to be an original MALAHITEAM-built
DSP2.** Physical inspection found: front label **"Malahit DSP SDR
V3"**; underside **"Designed by HiDY, Made in China"**; the boot
screen displays Malahit Team / original-project-author branding and
credits; the unit has its own internal battery. A follow-up, narrowly
targeted search (not a re-run of the original broad research) found
that **"HFDY"/"HiDY" is a well-documented Chinese manufacturer of
Malahit-DSP-derived clones**, and a specific community wiki page
exists for exactly this "HFDY Malahit DSP SDR v3" product — see §2a.
**Every claim below originally written about "the Malahit DSP2" was
researched against the ORIGINAL MALAHITEAM product, not this V3 clone
unit, and must now be read as lineage/reference material only, not as
verified fact for the owned hardware, unless a provenance tag says
otherwise.** §2a is the corrected, unit-specific section — read it
first; §2 (kept intact below it) is left as originally written,
now clearly scoped to the original DSP2 as reference material.

Owned hardware this investigation is scoped around: a **Malahit
DSP SDR V3 (HiDY-manufactured)** receiver (own internal battery), an
**RTL-SDR dongle** (exact model/revision not yet established), and an
**outdoor magnetic-loop antenna on PVC**, currently associated with
the user's existing SDR setup, not yet connected to the Pi.

## Provenance key (used throughout)

- **VERIFIED** — a specific, cited, current source states this as fact
  (about whichever specific product it's about — check which one).
- **DIFFERENT REVISION** — documented, but for different
  firmware/hardware than this unit is confirmed to have.
- **DIFFERENT PRODUCT (DSP2 lineage)** — documented for the original
  MALAHITEAM DSP1/DSP2/DSP3/DSP4 product line specifically, not
  confirmed to apply to the owned HiDY-manufactured "V3" clone at all.
  Useful as background/lineage, not as fact about the owned unit.
- **COMMUNITY** — a forum/blog/reviewer/wiki observation, not
  manufacturer-authoritative.
- **HYPOTHESIS** — our own inference; explicitly unverified.
- **NEEDS HARDWARE** — cannot be resolved without the physical unit(s)
  in hand.
- **OBSERVED, UNEXPLAINED** — something the user directly witnessed on
  the physical unit that no source (original or follow-up research)
  documents an explanation for.
- **CONFIRMED (this unit, 2026-09-05 enumeration)** — added after the
  first physical USB enumeration pass: directly read from this exact
  owned unit's own USB descriptors, kernel log, or ALSA driver state -
  the strongest tier in this document, but still scoped to what a
  passive descriptor/enumeration inspection can prove (see the next
  tier for where inference begins).
- **STRONGLY SUGGESTED (evidence-based inference, not proof)** — a
  conclusion that fits the confirmed descriptor-level evidence very
  well (e.g. channel-count/sample-rate signatures matching known SDR
  conventions) but has not been independently proven by actually
  exercising the interface (e.g. capturing and inspecting real audio
  content, or sending a query and reading a real reply).
- **CONFIRMED (this unit, 2026-09-05 second gate — ACM listen +
  passive audio capture)** — added after actually opening both serial
  ports (read-only, DTR/RTS held low, zero bytes transmitted) and
  capturing short samples from both audio interfaces; the strongest
  tier available short of active CAT interrogation or a known-signal
  tuning test (§11b).

---

## 1. Executive summary (revised 2026-09-05, seven times - see §2b for the physical enumeration update, §11b for the CDC-ACM listen test + audio characterization, §11c for the known-frequency retest, §3a for RTL-SDR identification + receive test, §3b for the librtlsdr wideband tuner characterization, §13 for the full OpenWebRX+ installation/verification - **real reception through OpenWebRX+ is now confirmed working, browser-accessible at `/radio/`**)

- **2026-09-05, physical enumeration complete (§2b)**: the V3 unit was
  connected to the Pi and passively characterized. Two genuinely
  distinct, confirmed audio streams exist - **mono, 40kHz** (very
  likely demodulated audio) and **stereo, 160kHz** (very likely IQ,
  matching the well-known "IQ-as-stereo-audio" convention) - plus two
  descriptor-identical CDC-ACM serial ports whose individual purpose
  (which one, if either, is CAT control) could not be determined
  passively. USB is Full Speed (12Mbit/s) only. The device declares
  itself "Self Powered" in its own USB descriptor, a favorable but not
  fully dispositive sign for the Pi's marginal rail. The ALFA
  Wi-Fi adapter briefly disconnected and re-enumerated one second
  *before* the Malahit's own enumeration completed - consistent with a
  brief shared-rail transient at insertion, not proven to be caused by
  the Malahit specifically, and no further disruption occurred once it
  settled. The documented "long-press power button, no USB, to see
  firmware version" check did **not** work on this exact unit -
  firmware version remains unknown. Full details, and the exact
  confirmed/suggested/unknown breakdown, are in §2b.
- **Hardware identity, corrected**: the owned receiver is a **Malahit
  DSP SDR V3, manufactured by HiDY ("HFDY"), made in China** — a
  well-documented Chinese clone of the original MALAHITEAM Malahit-DSP
  line, not a confirmed original DSP2. The boot screen honestly
  credits the original project authors, and community sources describe
  some HFDY-branded units as built "under license" to the original
  team — but this remains a COMMUNITY claim, not a verified fact, and
  regardless of licensing, **the hardware and firmware are a distinct
  product from what the original DSP2 research (§2) describes.** See
  §2a for what a narrow, targeted follow-up search found specifically
  about this "HFDY V3" product.
- A genuinely workable path may still exist: **OpenWebRX+** (the
  actively maintained `luarvique/openwebrx` fork) remains Trixie-aware,
  self-hosted with no CDN dependency, and supports RTL-SDR natively.
  Its Malahit support (`SoapyMalahitRR`) is now **more doubtful** for
  this specific unit than originally flagged: the plugin's own naming
  ("Malahit-**R1**") and its GPIO/SPI/I2C-heavy source tree increasingly
  look like they target a *different, bare receiver module* product in
  the broader Malahit-branded ecosystem — distinct from any handheld
  "DSP"-series unit, original or clone, by the naming alone (R1 vs
  DSP1/DSP2/DSP3/DSP4/**V3**). This was already a live concern before
  the hardware correction; it is a stronger concern now. **NEEDS
  HARDWARE** (and likely needs to read the plugin's actual source).
- Two load-bearing unknowns remain, now scoped to the correct product:
  **(a)** whether `SoapyMalahitRR` (or any other path) works with this
  V3 clone's actual USB interfaces at all, and **(b)** real OpenWebRX+
  CPU/RAM/client-count behavior on an actual Pi 3B+ under Trixie
  aarch64 — nobody has published that benchmark for any Malahit
  variant or RTL-SDR on this exact OS/hardware combination.
- **New, HFDY-V3-specific findings (§2a, COMMUNITY, one reported unit)**
  meaningfully narrow some of the original DSP2-based uncertainty for
  *this specific product line*: USB-C connector (confirmed for the
  HFDY V3 line specifically), a firmware version reportedly visible via
  a long-press of the power button at boot (a concrete, easy check),
  and — importantly — **charging and USB data connection appear to be
  bundled together whenever the unit is powered on while cabled** (one
  source: "will not charge off the computer USB port if the Malahit
  SDR is not powered on," but "when powered on, it will both charge
  and connect... simultaneously"). This means a data-only, no-charging
  enumeration may not be achievable simply by using a data-only cable
  while the unit is on — the precaution in §11 is written accordingly.
- The existing offline Radio reference content
  (`data/utility/radio/services.json`) is **not greenfield** — it
  already has numeric `freq_low_hz`/`freq_high_hz` fields tailor-made
  for a future "Tune Receiver" hook (§9). This is unaffected by the
  hardware-identity correction and still changes the integration
  design meaningfully: build toward this existing schema, don't invent
  a parallel one.
- Recommended architecture (§8) is **unaffected in shape** by the
  hardware correction — a strictly optional capability, a small
  backend-selection abstraction (Malahit-family vs RTL-SDR vs future),
  OpenWebRX+ reverse-proxied behind the existing Nginx on a new
  `/radio/` path, bound to loopback only, reachable exclusively via
  `pb-ap`, with the OLED/Core stack completely unaware of whether it's
  running. What changes is confidence in whether the Malahit branch of
  that abstraction will actually work for this hardware — RTL-SDR
  remains the far more certain of the two backends.
- Next concrete step (§11, revised): a controlled, read-only,
  before/after USB enumeration of the V3 unit — no drivers, no CAT
  commands, no firmware changes, no production changes. Exact
  procedure given, updated with the HFDY-specific power/charging
  finding above and a safe, hardware-only way to read the firmware
  version before ever connecting to the Pi.
- **One new observed-but-unexplained behavior**: holding both rotary
  encoder push-buttons simultaneously caused the unit to reboot and
  apparently reset at least some settings. Neither the original DSP2
  research nor the new HFDY-V3-specific search found any documentation
  of this combination. Recorded as OBSERVED, UNEXPLAINED in §2a — not
  to be deliberately repeated.

---

## 2a. The actual owned unit: Malahit DSP SDR V3, HiDY-manufactured (added 2026-09-05)

**This section is about the real, owned hardware. §2 below it is the
ORIGINAL research, scoped to the genuine MALAHITEAM DSP2 — read as
lineage/background only unless a claim here says it was confirmed to
carry over.**

### What physical inspection found

- Front label: **"Malahit DSP SDR V3."**
- Underside: **"Designed by HiDY," "Made in China."**
- Boot screen: displays Malahit Team / original-project-author
  branding and credits (the same RX9CIM/R6DAN/R6DCY lineage named in
  §2 below).
- Has its own internal battery (consistent with every Malahit-DSP-
  family variant, original or clone).

### What a targeted follow-up search found (COMMUNITY, not manufacturer-authoritative)

Searching specifically for "Malahit DSP SDR V3" + "HiDY" (not a
re-run of the original broad Malahit research) found:

- **VERIFIED (multiple independent sources agree the brand exists)**:
  "HFDY" (also transliterated "HiDY") is a well-known **Chinese
  manufacturer of Malahit-DSP-derived clones**, discussed by name in
  at least three independent sources: a SWLing Post comparison
  ("Malahit DSP-2 versus Chinese Clone: Taking the Gloves Off"), a
  SWLing Post head-to-head of two rival clone brands ("HFDY vs. Fire
  Brothers"), and a dedicated community wiki page for this exact
  product: **`wiki.robotz.com` — "HFDY Malahit DSP SDR v3"** (part of
  "The DUCK Project" knowledge base). The existence of a dedicated
  wiki page for "v3" specifically means this is a real, previously
  documented product, not an obscure one-off.
- **COMMUNITY (SWLing Post review)**: the HFDY clone's build quality
  (metal construction, dual SMA antenna jacks, extra internal
  shielding, front-firing speaker with a gold grille) was assessed in
  one review as **exceeding** the genuine Russian-made DSP-2's build
  quality. A separate source states some HFDY units are "built in
  China under license to the Russian MalahiTeam" and calls these
  "legitimate licensed clones" — plausible explanation for why the
  boot screen credits the original authors, but this licensing claim
  is itself COMMUNITY-level, not a verified legal fact.
- **COMMUNITY, important firmware-numbering distinction**: clone units
  in this line commonly ship with firmware version **1.10c**, while
  "the Russian Original" (genuine DSP2) runs firmware in the **2.10D/
  2.10F/2.20A** series (§2's own numbers). One source states the clone
  can be firmware-updated to make it "essentially the same level as a
  DSP2," but **the version-NUMBER scheme itself differs (1.x vs 2.x)
  even when functionally equivalent** — meaning any CAT command
  behavior documented against "2.10F" or "2.20A" firmware (§2) is NOT
  safe to assume applies to this unit's actual (1.x-numbered, until
  checked) firmware. This must be checked against whatever version
  this specific unit actually reports, not assumed either way.
- **COMMUNITY, from the `wiki.robotz.com` HFDY V3 page specifically**
  (one documented user's own exploration of this same product,
  presumably on their own unit — still a single reported unit, not a
  manufacturer spec, and not proof of what THIS unit will report):
  - **USB-C connector** ("USB-TYPEC interface") — resolves the
    micro-USB-vs-USB-C ambiguity §2 flagged, at least for this product
    line; still worth visually confirming on the actual unit.
  - **One reported `lsusb` line**: `Bus 003 Device 112: ID ffff:0737
    MicroGenSF Malahit reciever` — a real VID:PID from one specific
    reported unit. **Treat this as a hypothesis to check the owned
    unit against, not an assumed value** — clone hardware/firmware
    batches are known to vary (§2's own "Fire Brothers" vs "HFDY"
    rival-clone-brand finding is a reminder that "a Chinese Malahit
    clone" is not one single, uniform product).
  - **Firmware version is directly visible without any USB connection
    at all**: "When you first power the unit on, by long pressing the
    power button, the initial screen will offer information including
    the current firmware version." This is a safer, more concrete
    check than §2's original DSP2-based guidance (which only
    speculated about a HARD-menu location) — **do this first, before
    any USB/Pi connection**, per §11's revised procedure.
  - **Same three USB interface types as §2 describes for genuine
    DSP2** (IQ data, audio, CAT) appear present on this clone too, per
    this one source — but with **two** `/dev/ttyACM` devices reported
    (`/dev/ttyACM0` and `/dev/ttyACM1`), not confirmed to be exactly
    one as §2's DSP2 research assumed. The CAT protocol is described
    identically to §2's finding: "'borrows' the CAT profile of a
    Kenwood TS-480."
  - **Charging behavior, a real and specific finding**: "Will not
    charge off the computer USB port if the Malahit SDR is not powered
    on," but "when powered on, it will both charge and connect to the
    PC as an external sound device" **simultaneously**. This is more
    specific than anything found in the original DSP2 research (which
    found no confirmed charge-disable mechanism at all) — it suggests
    that for THIS clone line, there is **no way to get meaningful USB
    data enumeration without also triggering charging**, since the
    unit must be powered on for its USB stack (audio/CAT interfaces)
    to run at all, and charging appears bundled with power-on + cabled
    state. This sharpens, rather than resolves, the power precaution
    in §11 — a full battery before connecting remains the best
    available mitigation.
  - Update tooling mentioned: `dfu-utils` (standard, Linux-packaged
    STM32 DFU flashing tool) — consistent with §2's STM32-family
    finding, and a positive (if currently out-of-scope) sign that this
    hardware line is at least somewhat Linux-flashable, for whenever
    firmware updates are ever considered (not part of this
    investigation's scope).
  - No dual-encoder-button combination is documented on this page
    either — see the OBSERVED, UNEXPLAINED note below.

### Observed, unexplained: simultaneous encoder-button reboot

The user physically observed that **holding both rotary encoder
push-buttons at the same time caused the receiver to reboot and
apparently reset at least some settings.** Neither the original
broad Malahit research (§2) nor this targeted HFDY-V3 follow-up found
any documentation of this specific button combination, on any
Malahit-family product, original or clone. **This is recorded as
OBSERVED, UNEXPLAINED — not to be deliberately repeated to
investigate further.** Plausible explanations (a factory-reset combo,
an unrelated firmware quirk, a clone-specific behavior not present on
genuine units) are all equally unverified; if this project reaches the
point of engaging the OpenWebRX+/Malahit community directly, this
specific behavior (with the confirmed "V3"/HiDY identity) would be a
reasonable, concrete question to ask there rather than something to
keep probing alone.

### What this means for the rest of this document

Every section from here on (§2 through §12) was originally researched
and written against the **genuine MALAHITEAM DSP2**, before this
hardware correction. Rather than rewrite everything from a blank page
(which would discard real, still-useful lineage/background research),
each section below retains its original content with its original
provenance tags, but should now be read through this lens: **claims
about "the Malahit" describe the DSP2 product family in general and
must be independently confirmed against this specific HiDY V3 clone
before being relied on** — the §2a findings above are the closest
thing to unit-specific evidence currently available, and even those
are one community-reported unit, not a guarantee for this exact one.

---

## 2b. First physical USB enumeration — results (2026-09-05)

**The §11 physical hardware gate has been performed.** The V3 unit was
charged separately beforehand, connected to the Pi with a data cable
while powered on, and left connected for the passive characterization
below - no drivers installed, no CAT commands sent, no firmware or
calibration changes, no button-combo experiments repeated.

### One documentation claim did NOT hold up on this unit

§2a's "long-press the power button at boot, with no USB connected, to
see the firmware version" (sourced from the `wiki.robotz.com` HFDY V3
page) **did not work on this exact unit** - it performed a normal
startup with no version screen shown. This is recorded as a real,
useful negative result, not a failure: it's further evidence that
community documentation for "the HFDY V3" does not uniformly apply
even within that same clone family - consistent with §2's own earlier
"Fire Brothers" vs "HFDY" rival-clone-brand finding, and a reminder
that every claim in this document needs this unit's own evidence, not
just a same-named product's. **The firmware version remains unknown**,
and per instruction this is not to be re-attempted with other button
combinations.

### Before/after comparison

| | Before | After connecting |
|---|---|---|
| `lsusb` (new line) | none | `ID ffff:0737 MicroGenSF Malahit reciever` |
| ALSA capture hardware | none | card 2 "reciever", 2 capture devices, 1 playback device |
| `/dev/ttyACM*` | none | `/dev/ttyACM0`, `/dev/ttyACM1` |
| `/dev/ttyUSB*` | none | none |
| `vcgencmd get_throttled` | `0x50005` | `0x50005` (unchanged) |
| `vcgencmd measure_volts` | `1.2000V` (SoC core, not the 5V input rail) | `1.2000V` (unchanged) |
| temp | 39.2°C | 39.7°C |

No new driver/package was needed - the kernel's own in-tree `cdc_acm`
and `snd-usb-audio` bound automatically, exactly as §2's "standard USB
classes, no proprietary driver" finding predicted (that finding was
about the genuine product, but held true here too).

### CONFIRMED (this unit, 2026-09-05 enumeration)

Directly read from the device's own USB descriptors (`lsusb -v -d
ffff:0737`), the kernel log (`dmesg`), and the ALSA driver's own
parsed state (`/proc/asound/card2/*`) - all three independently agree:

- **VID:PID `ffff:0737`**, product string "Malahit reciever" [sic],
  manufacturer string "MicroGenSF", `bcdDevice` 1.06. (§2a's
  community-reported `ffff:0737` hypothesis from a different, unrelated
  unit turned out to match exactly - worth noting as a good sign that
  this VID:PID may be consistent across at least some portion of this
  clone line, though still only two data points.) The device's
  `iSerial` string decodes as non-printable/malformed binary, not a
  usable stable identifier - do not rely on it to distinguish this
  unit from another of the same batch.
- **Negotiated USB speed: Full Speed, 12Mbit/s** - not High Speed
  (480Mbit/s). This is a real, confirmed bandwidth ceiling for
  everything this device does over USB, shared across all ten of its
  interfaces at once.
- **`bmAttributes 0xc0` = Self Powered**, declared `MaxPower 250mA`.
  The device's own USB configuration descriptor tells the host it does
  not depend on bus power for its own operation, and requests only a
  small (250mA) allowance even though it's self-powered. This is a
  genuinely favorable data point for the Pi's marginal rail - but it
  is **not** the same thing as "never draws charging current via
  VBUS": the USB "Self Powered" bit governs whether the device's own
  logic/USB stack depends on bus power, not whether a separate,
  independent battery-charging circuit pulls current from VBUS. USB
  has no descriptor field that declares "I am also charging my
  battery right now." **The charging-current question from §2/§2a
  remains open** - this finding narrows what it can be about (the
  device isn't secretly asking for hundreds of mA to simply function),
  it doesn't resolve it.
- **Ten interfaces, five Interface Association Groups**, exactly
  matching the earlier reported "2 CDC-ACM pairs + 6 audio interfaces"
  shape:
  - **Interfaces 0-1** → `/dev/ttyACM0`. Communications class,
    "Abstract (modem)" subclass, "AT-commands (v.25ter)" protocol
    field (a generic USB class-code choice many non-AT-command CDC
    devices use as boilerplate - **not evidence this actually speaks
    Hayes AT commands**; §2's CAT research already found the genuine
    product's CAT protocol is Kenwood-TS-480-style ASCII, not AT
    commands). One Interrupt IN endpoint (status) + Bulk IN/OUT pair
    (data) - the standard CDC-ACM shape.
  - **Interfaces 2-3** → `/dev/ttyACM1`. **Descriptor-for-descriptor
    identical in shape and class/subclass/protocol to interfaces 0-1**
    (confirmed independently via both `lsusb -v` and `udevadm info -a`
    on both device nodes) - USB descriptors alone cannot distinguish
    what these two ports are each for.
  - **Interfaces 4-5** → ALSA card 2, device 0 (capture). AudioControl
    input terminal type `0x0710` = **"Radio Receiver"** (a real,
    specific USB Audio Class terminal type, not a generic microphone
    type). Actual streaming format: **mono, 16-bit (S16_LE), fixed
    40000 Hz**, confirmed identically by both the raw descriptor and
    `/proc/asound/card2/stream0`.
  - **Interfaces 6-7** → ALSA card 2, device 1 (capture only). Second,
    separate "Radio Receiver" input terminal. Actual streaming format:
    **stereo (channel map "FL FR"), 16-bit (S16_LE), fixed 160000
    Hz** - confirmed identically by both the raw descriptor and
    `/proc/asound/card2/stream1`.
  - **Interfaces 8-9** → ALSA card 2, device 0 (playback, bundled with
    the same "device 0" number as the mono capture pair since ALSA
    groups them). Direction is reversed from the others - a "USB
    Streaming" input terminal feeding a "Radio Receiver" *output*
    terminal, i.e. host-to-device. Format: mono, 16-bit, fixed 40000
    Hz - same rate/format as the mono capture pair, just the opposite
    direction.
- **Live USB topology** (`lsusb -t`, current): the Malahit sits at
  `Bus 001, Dev 007`, nested under the same internal 4-port hub the
  ALFA is attached to, but one level deeper (behind a second, 3-port
  internal hub that also carries the onboard Ethernet). The ALFA is a
  direct child of the first hub, not nested behind the second one.
  They are on different branches, but both ultimately draw from the
  **same shared upstream 5V feed** through the Pi's own internal
  combo hub chip.
- **`dmesg -T` timeline**: the ALFA's disconnect/re-enumeration
  (`usb 1-1.3: USB disconnect` → fresh re-enumeration one second
  later) is timestamped **one second BEFORE** the Malahit's own first
  enumeration line appears. The sequence is consistent with a brief
  shared-rail transient at the moment of *inserting* the Malahit
  (physically plugging in any USB device can cause a brief voltage
  sag as the host's port controller detects and powers up the new
  connection), not with an ongoing, sustained high-current draw from
  the Malahit afterward - no further disconnects or throttling-state
  changes were observed for the remainder of the session once the
  Malahit had settled into its enumerated state.

### STRONGLY SUGGESTED (evidence-based inference, not proof)

- **Interfaces 4-5 (mono, 40kHz) are very likely the demodulated
  receiver audio stream** ("Malahit RX" in §2's naming) - a mono
  voice/audio-bandwidth sample rate is exactly what demodulated
  AM/FM/SSB audio needs, and 40kHz specifically is a plausible,
  round-ish choice for that purpose. This has NOT been proven by
  actually capturing and inspecting the audio content - only by the
  channel-count/sample-rate signature matching the expected shape.
- **Interfaces 6-7 (stereo, 160kHz) are very likely the IQ/baseband
  stream** ("Malahit IQ" in §2's naming) - two channels at a much
  higher sample rate than any voice-audio use would need is the
  well-established "IQ as stereo audio" convention this whole category
  of hardware (Malahit-family and otherwise, e.g. FiFi-SDR) is known to
  use, with left/right channels carrying I and Q respectively. 160kHz
  doesn't exactly match any of the genuine DSP2's documented panorama
  spans (192/96/48kHz, §2) - consistent with this being a different
  product with its own bandwidth choice, not evidence against the
  IQ hypothesis itself. This has NOT been proven by capturing and
  analyzing the actual sample stream (e.g. confirming it looks like
  baseband RF content rather than something else entirely).
- **Interfaces 8-9 (mono, 40kHz playback) are plausibly a
  host-to-radio audio injection path** (matching the shape a firmware
  feature like a code-practice tone, an announcement, or a monitor
  function might use) - genuinely speculative; no source found
  documents what this is for on any Malahit-family product, original
  or clone.
- **`/dev/ttyACM0` and `/dev/ttyACM1` cannot be distinguished by
  descriptor alone; determining which (if either) is CAT control, and
  what the other one does, requires either testing (§12) or specific
  documentation for this exact VID:PID that has not been found.**

### Still unknown (unchanged or newly precise)

- Which, if either, `/dev/ttyACM*` port accepts CAT commands, and in
  what protocol (Kenwood-TS-480-style, per §2's genuine-product
  research, is a reasonable starting hypothesis to test - not a
  confirmed fact for this unit).
- Whether OpenWebRX+ (via `SoapyMalahitRR` or any other path) can
  actually consume either audio stream usefully - see §5's revised
  assessment below.
- Actual USB charging current draw - the "Self Powered" descriptor bit
  is a favorable but not dispositive data point (see above); no
  current-draw measurement has been taken.
- This unit's firmware version (the one documented check method did
  not work - see above).
- Whether the ALFA disconnect was genuinely power-related or coincidental -
  the timing is consistent with a brief insertion transient on a
  shared rail, but this is one observation, not a controlled,
  repeatable test.

---

## 2. Background: the original MALAHITEAM Malahit-DSP lineage (DIFFERENT PRODUCT from the owned unit — see §2a)

**Everything in this section describes the genuine, Russian-built
MALAHITEAM product line, researched before the §2a hardware
correction. Read it as background/lineage on the ecosystem the owned
HiDY V3 clone belongs to — not as verified fact about the owned unit
itself.** Where §2a found a specific, confirmed difference (firmware
numbering, USB connector, button behavior), that supersedes this
section for the owned hardware.

Designed by Georgy Yatsuk (RX9CIM, idea/DSP/initial circuit), Vladimir
Gordienko (R6DAN, GUI/control), Vadim Burlakov (R6DCY, final
circuit/build), and Igor Naumenko (retro-scale UI feature) — a
Yekaterinburg, Russia hobbyist project ("MALAHITEAM" / "TEAM.M dsp
technology"), publicly begun mid-2019. Official manual:
`malahiteam.com/wp-content/uploads/2021/11/manual_malahiteam_en.pdf`.
(VERIFIED as history of the ecosystem; the owned unit's own boot-screen
credits to this same team are consistent with it being a clone/
licensed-clone of this lineage, per §2a.)

- **DSP1** (VERIFIED, no longer manufactured, genuine product):
  50kHz–250MHz, 400MHz–2GHz; needs a separate auxiliary board for
  SW-mode/50Ω/attenuator; requires an activation-code exchange after
  flashing.
- **DSP2** (VERIFIED for the genuine product — **NOT confirmed to be
  the owned unit's generation**, which is labeled "V3" by its own
  manufacturer, HiDY, a distinct naming scheme): 20kHz–380MHz,
  400MHz–2GHz (one community source says 10kHz, a minor, unresolved
  discrepancy); panorama spans 192/96/48kHz; auxiliary-board
  functionality (attenuator, filters, 50Ω/Hi-Z switch) built in; adds
  bias-tee antenna power; **STM32H743** (Cortex-M7 @ 480MHz, per
  COMMUNITY source) driving an **MSi001** tuner chip.
- **COMMUNITY**: Chinese clones of the DSP2 circulate widely under
  various storefront names (Raddy, GOOZEEZOO, HFDY/HiDY, generic
  AliExpress/eBay) — **the owned unit is one of these**, specifically
  the HFDY/HiDY-branded "V3" (§2a). Officially-blessed upgrade paths
  (Russia, plus independent installers in Europe/US) exist from
  DSP1/clone to DSP2 firmware. One review found no functional
  difference post-upgrade, but this is anecdotal.
- **COMMUNITY**: the manufacturer has since moved on to DSP3
  (discontinued, chip shortage) and DSP4 (as of early 2026) — DSP2 is
  now a legacy generation in the current genuine product line. This
  doesn't change anything about the owned unit (whose own "V3"
  labeling is a separate, HiDY-specific naming scheme, not part of
  this DSP1→DSP4 sequence at all), just flags that most *current*
  search results about "the latest Malahit" mean DSP4, not DSP2 or V3.

### USB interfaces (VERIFIED for the genuine DSP1/DSP2, three independent sources agree — see §2a for the owned V3's own, partly-confirmed equivalent)

When connected via USB, the DSP2 presents as **three simultaneous
composite USB devices**, not configurable/exclusive:

1. **"Malahit RX"** — a USB Audio Class device carrying demodulated
   receiver audio (48kHz per one firmware-history note).
2. **"Malahit IQ"** — *also* a USB Audio Class device (not a
   vendor-specific interface), carrying the full IQ/panorama stream at
   whichever bandwidth (192/96/48kHz) the on-device panorama setting
   is currently set to.
3. **"Malahit CAT"** — a USB-CDC-ACM virtual serial port for
   frequency/mode/volume control (conventionally `/dev/ttyACM*` on
   Linux, but **no source confirms Linux enumeration specifically** —
   HYPOTHESIS until tested).

**No VID:PID is published anywhere** for any of the three interfaces,
for any firmware version — this is a genuine, universal documentation
gap, not something we failed to search for. **NEEDS HARDWARE.**

**CONFLICTING, DIFFERENT REVISION**: the official manual and the best
community FAQ both describe/photograph a **micro-USB** port. Current
reseller listings (Radioddity "Raddy DSP2," an Amazon "GOOZEEZOO"
listing) describe **USB-C, 5V/2A**. Both cannot be the same hardware —
this is almost certainly a running production change. **The physical
unit's own connector is the ground truth**, not either document.

Standard USB device classes (UAC + CDC-ACM) mean no proprietary
Windows driver is needed ("Windows 10 is supposed to have all the
drivers needed" — VERIFIED, community FAQ + independent blog,
identical wording). This is a *good sign* for Linux (both `snd-usb-
audio` and `cdc_acm` are in-kernel) but **zero sources tested Linux
specifically** — treat "it'll just work on Linux" as HYPOTHESIS.

### CAT/tuning control (COMMUNITY, genuine DSP-family firmware — §2a found the owned unit's firmware numbering differs; do not assume these exact command/version details carry over)

- Command set is reported **compatible with the Kenwood TS-480**
  subset (e.g. `FA;` queries frequency, `FA00006070000;` retunes).
- Recommended serial config (from OmniRig instructions): 19200 baud,
  8N1, RTS=High, DTR=High, Poll=500ms, Rig Type "TS-480."
- **Firmware-dependent, confirmed by the vendor's own firmware-history
  notes**: firmware 2.10F "completely redesigned CAT interface... NCO
  function... enhanced CAT... volume and antenna control"; 2.20A
  "improved CAT information output, including S-meter data." **A CAT
  command list found for one firmware version may not match this
  unit's actual firmware** — this must be checked against whatever
  version the owned unit reports (§6, §11).
- No complete, authoritative published CAT reference was found
  anywhere, official or community.

### USB power/charging, genuine DSP1/DSP2 family (background — §2a has a MORE SPECIFIC, and more concerning, finding for the owned HFDY V3 line: charging appears bundled with any powered-on USB connection)

- **VERIFIED** (official manual, applies to the DSP1/DSP2 family):
  single 18650 Li-Ion cell, "USB charging supported," ~300mA power
  consumption with headphones on. Battery cutoff is menu-controlled on
  DSP1 (Vbat: Standard 3.3V / Low 2.7V) but **hardware-automatic at
  3.1V on DSP2** specifically, per the manual.
- The official manual states **nothing** about whether plugging in USB
  always initiates charging, and documents **no menu option to disable
  charging** — I read every documented menu item; none relate to
  charge enable/disable.
- **COMMUNITY** (N9EWO review, independent but well-regarded SWL
  reviewer): "~4 hours to full from empty (receiver OFF), ~850mA peak
  charging current," explicitly recommending **a 2A USB supply "to
  prevent regulator overheating during charging."** This is one
  reviewer's characterization of (likely) an earlier micro-USB
  hardware revision, not confirmed against this unit.
- **COMMUNITY** (groups.io, snippet-only access — could not fetch full
  thread content, treat as moderate confidence): consensus that
  running the DSP2 directly from USB power works in practice, main
  risk being an underpowered source; a separate thread ("Malahit DSP2
  Wont charge, schematics?") confirms charging quirks are a real,
  recurring community topic, not a solved area. One unverified
  attribution associates a TP4056 charge-controller IC (~0.9A,
  4.5–5.5V input) with the design — plausible, not confirmed.
- **COMMUNITY** (vk2.net): there is always a small current drain even
  when the unit is off, and the DSP2 has **no hardware protection
  against over-discharge** — leaving it unpowered and depleted for
  long periods can permanently damage the battery. Relevant if the
  eventual plan is "leave it attached to the Pi indefinitely."
- **No source anywhere — official or community — documents**: a
  charge-disable/data-only mode; a confirmed idle (non-charging)
  current-draw figure; or anyone actually testing "run on internal
  battery, data-only cable, no charging" as a scenario. This exact
  question is the single most important thing to test empirically
  rather than assume, given the Pi's already-marginal 5V rail (§4).

### What to check on the physical unit — SUPERSEDED by §2a/§11

This checklist was written against the genuine DSP2 before the
hardware correction (§2a). It's kept here, struck through in spirit
but not deleted (the PCB-silkscreen and printed-label points are still
generically valid), because **§2a and §11 now give a more specific,
confirmed-relevant, and safer procedure for the actual owned unit** —
notably, §2a found the firmware version is reportedly visible via a
long-press of the power button at boot, with **no USB connection
needed at all**, which is both easier and safer than anything listed
here. Use §11's procedure, not this list, as the actual next step.

1. USB connector type — §2a already visually confirmed **USB-C** for
   this product line generally; confirm on the physical unit itself.
2. Firmware version — see §2a's long-press-power-button method instead
   of the HARD-menu speculation originally written here.
3. PCB silkscreen revision mark — still generically valid if the case
   is ever opened, but not required for this investigation's next step.
4. Printed serial/label — still generically valid; no established
   scheme is known for either the genuine product or this clone line.
5. `lsusb -v` / `dmesg` once connected — still the right idea; see
   §11 for the exact commands and the §2a-informed VID:PID hypothesis
   (`ffff:0737`, one reported unit, not an assumption) to check against.
6. Inline USB power-meter reading — still valid and still not
   required; see §11's revised precaution, which is now more specific
   given §2a's "charging is bundled with powered-on USB connection"
   finding.

---

## 3. RTL-SDR as a second backend

**Update 2026-09-05: physically identified and receive-tested - see
§3a.** The generic reasoning below (written before identification) is
kept intact as background; §3a is the unit-specific, evidence-backed
section.

Per instruction, the exact dongle model/revision is **unknown** and
must not be assumed (not necessarily RTL-SDR Blog V3/V4, direct
sampling, Bias-T, or HF-capable). This will be resolved the same way
the EXTERNAL-AP work already resolved ALFA identity: **by USB
enumeration** (`lsusb`, VID:PID, and if ambiguous, a photo of the
printed label), never by assumption. Generic RTL-SDR facts that don't
depend on the specific unit:

- Enumerates as a standard USB device (VID 0bda is the generic
  RTL2832U default; V3/V4 boards and various rebranded units share or
  override this depending on EEPROM programming — **cannot be assumed
  without seeing the actual `lsusb` output**).
- No internal battery, no charging behavior to investigate — it draws
  bus power only, a simpler power story than the Malahit, but still a
  new USB load on the same marginal rail (§4).
- Every browser-SDR candidate researched (§5) that supports any
  hardware at all supports RTL-SDR — it is the de facto lowest common
  denominator of the whole ecosystem, unlike the Malahit which only
  OpenWebRX+ has any support for.
- No IQ-over-USB-audio quirk — RTL-SDR exposes raw samples over a
  vendor USB bulk-transfer protocol (`librtlsdr`), a completely
  different and far better-trodden software path than the Malahit's
  USB-Audio-Class IQ stream.

**Architectural conclusion**: RTL-SDR is the "boring, well-supported"
backend and the Malahit is the "own-battery, unique but
less-proven-on-Linux" backend. A multi-backend design (§8) is
justified by this real difference, not abstraction for its own sake —
one backend already has a known-working software path (RTL-SDR + any
candidate), the other has exactly one candidate with one plugin whose
fit is still unconfirmed.

---

## 3a. RTL-SDR — first physical identification and receive sanity test (2026-09-05)

**Physical setup**: the RTL-SDR is connected via the ALFA's own
passive USB extension cable (reused for port-crowding reasons, not a
purpose-built RTL-SDR cable), with an MLA-50+ active loop antenna
attached, whose bias/power box is powered separately from the wall -
not drawing from the Pi. The antenna system itself is out of scope
for this round; it appears below only as an incidental real RF source
for the sanity test.

**A genuine physical gate occurred first**: the RTL-SDR initially
showed **zero USB enumeration trace at all** - not a failed/partial
enumeration, not a descriptor error, nothing in `dmesg` whatsoever,
and no over-current/hub-port-disable messages anywhere in the boot's
kernel log either. Reseating the connection once did not resolve it
and, as an incidental side effect, caused the ALFA to blip (proving
real electrical continuity in that area, just not for the RTL-SDR
specifically). Only a second reseat brought the RTL-SDR up. **Cause of
the initial non-enumeration is not established** - most likely an
imperfect seat on a passive, reused extension cable, but this was
never proven since the device simply started working; not investigated
further since the operator's own instruction was to move on once
enumeration succeeded.

### 3a.1 USB identification - CONFIRMED

- **VID:PID `0bda:2838`** (Realtek Semiconductor Corp., "RTL2838
  DVB-T"), `bcdDevice 1.00`, `iProduct` string **"RTL2838UHIDIR"**
  (the "UHIDIR" suffix is this specific unit's own string, not a
  generic Realtek default), `iSerial` **"00000001"** (a placeholder-
  looking serial, common on generic/unbranded RTL-SDR dongles - not
  treated as a meaningful per-unit identifier).
- **USB 2.0, negotiated High Speed (480 Mbit/s)** - confirmed via
  `lsusb -v` (`bcdUSB 2.00`, "Negotiated speed: High Speed"). This is
  a real, structural difference from the Malahit, which negotiates
  Full Speed (12 Mbit/s) only and shares that ceiling across all 10 of
  its own interfaces at once (§2b, §4). The RTL-SDR has no such
  shared-bandwidth constraint from its own USB side.
- **Topology**: enumerates behind the same 3-port hub as the Malahit
  did (`1-1.1.3`), a different branch from the ALFA (`1-1.3`, behind
  the first 4-port hub) - same shared 5V feed as everything else on
  this Pi, no dedicated power path.
- **Two USB interfaces**: interface 0 (Vendor Specific Class, one
  bulk-IN endpoint, `wMaxPacketSize 512 bytes`) is claimed by the
  kernel's own `dvb_usb_rtl28xxu` driver; interface 1 (Vendor Specific
  Class) shows driver `[none]` - not claimed by anything. Device
  descriptor: Bus Powered, `MaxPower 500mA`.
- **Bus Powered** (not Self Powered like the Malahit) - the RTL-SDR
  draws its ~500mA budget entirely from the Pi's own 5V rail, unlike
  the Malahit's own internal battery. This is a real, structural power
  difference worth keeping in mind given the chronic `0x50005`
  condition (§3a.4).

### 3a.2 Chip/tuner identification - CONFIRMED (kernel-probed, not assumed)

The kernel's own driver stack positively identified the actual silicon
via I2C probing, not inferred from the USB VID:PID alone:

- **Demodulator: Realtek RTL2832** - `rtl2832 11-0010: Realtek RTL2832
  successfully attached`.
- **Tuner: Rafael Micro R820T** - `r820t 12-001a: Rafael Micro r820t
  successfully identified, chip type: R820T`. **Note**: the Linux
  `r820t` kernel driver does not distinguish R820T from the later,
  functionally-compatible R820T2 revision in its own log output - both
  print identically as "R820T". This unit's exact revision (T vs. T2)
  remains **NEEDS HARDWARE** (would require opening the case or a
  vendor label check the driver itself can't provide), but this
  doesn't affect software compatibility either way - both are the same
  well-supported tuner family from `librtlsdr`/SoapySDR's perspective.
  The R820T/R820T2 is the most common, most widely-supported RTL-SDR
  tuner (roughly 24 MHz-1766 MHz coverage), not one of the rarer
  E4000/FC0012/FC0013 alternatives.
- This is a genuine, positively-identified, well-supported RTL-SDR -
  not a rebrand of unknown/exotic silicon.

### 3a.3 Existing software support - CONFIRMED

- **No `rtl-sdr`, `librtlsdr`, or SoapySDR package is installed** -
  confirmed via `dpkg -l` and `which rtl_test rtl_sdr rtl_eeprom
  rtl_tcp SoapySDRUtil` (all empty). **No package was installed for
  this round.**
- **The kernel's own built-in DVB/V4L2 stack already claimed the
  device automatically**, with no package install needed for this
  part - it ships as part of the mainline kernel: `dvb_usb_rtl28xxu`
  (interface 0, control) plus its companion `rtl2832_sdr` V4L2 SDR-API
  driver, which registered a **`/dev/swradio0`** device node.
- **`v4l2-ctl` (part of `v4l-utils`) was already installed** (a
  standard Raspberry Pi OS package for the camera/media stack, not
  installed for this round) and can query/capture from `/dev/swradio0`
  with zero new packages.
- **Important limitation of this no-install path, confirmed by direct
  query**: `/dev/swradio0`'s own reported tuner range is **0.300000
  MHz - 3.200000 MHz only** - this is the RTL2832's raw ADC **direct-
  sampling** mode, which bypasses the R820T tuner entirely. It does
  **not** expose the tuner's actual ~24 MHz-1766 MHz range at all. This
  is a real, structural distinction: the standard way RTL-SDR dongles
  are normally used for VHF/UHF reception (FM broadcast, NOAA weather,
  ADS-B, etc.) is via `librtlsdr`/SoapySDR talking to the tuner
  directly over USB - a different, better-known path than this V4L2
  fallback, and the one any real OpenWebRX+ integration would actually
  use.
- **PACKAGE-INSTALL GATE, not performed**: a **wideband** sanity test
  (e.g. at an actual FM broadcast or NOAA frequency, matching what the
  Malahit round tested) genuinely requires installing `rtl-sdr`
  (`librtlsdr0` + the `rtl-sdr` command-line tools) or `SoapySDR` +
  its RTL-SDR module - there is no way to exercise the R820T tuner
  itself without one of these. Per instruction, this was **not**
  installed; if/when pursued, `rtl_test -t` (a fast, deliberately
  transmit-incapable USB/tuner self-test) would be the natural first
  command, needing explicit operator go-ahead first.

### 3a.4 Receive sanity test - CONFIRMED, real signal-dependent result

Performed entirely with already-installed `v4l2-ctl`, against
`/dev/swradio0`'s direct-sampling mode (0.3-3.2 MHz), with the
MLA-50+ as a real, independently-powered RF source. Two short (~1
second, 50-buffer) raw `CU08` (8-bit unsigned complex I/Q) captures
were taken and analyzed with the Python standard library only (no new
package):

- At **3.200000 MHz** (the range's upper edge, reached accidentally by
  a `v4l2-ctl` units mistake on the first attempt - `--set-freq` takes
  **MHz**, not Hz): I/Q stdev **9.18/9.19**, range roughly 86-167,
  82-83/256 unique byte values.
- At the intended **1.000000 MHz** (squarely in the AM/mediumwave
  broadcast band): I/Q stdev **16.72/16.70**, range roughly 15-252,
  212-214/256 unique byte values - **substantially more variation**
  than the 3.2 MHz capture.
- Both captures: real, varying data (not stuck/all-zero/all-same-
  value), and both centered almost exactly on the expected 127.5
  midpoint for unsigned 8-bit ADC samples (offsets of only -0.09 to
  -0.13), indicating a well-biased ADC front end with no gross DC
  fault.

**STRONGLY SUGGESTED**: the frequency-dependent difference (~1.8x
higher standard deviation, ~2.6x more unique byte values at 1 MHz vs.
3.2 MHz) is consistent with genuinely receiving more RF energy in the
AM broadcast band than near the direct-sampling range's quiet upper
edge - i.e., real signal, not just ADC self-noise. This is not
conclusively proven (no attempt was made to demodulate actual
broadcast audio content, and this round deliberately avoided turning
into an antenna-performance investigation per instruction), but it is
genuine, end-to-end evidence that the full chain - MLA-50+ antenna,
its separately-powered bias box, the RTL-SDR's ADC, and the kernel
driver stack - passes real, frequency-dependent RF energy through to
a captured file, achieved with **zero new package installs**.

### 3a.5 Power/ALFA observations during this round

- **Two ALFA disconnect/re-enumeration events occurred during RTL-SDR
  physical handling**, both **directly attributable to physically
  reseating a shared USB connection point** while working on the
  RTL-SDR - not spontaneous, and not caused by the RTL-SDR's own
  operation once seated. Both times, `hostapd`'s `BindsTo=`/
  `ConditionPathExists=` behavior (from the same-day hostapd incident
  fix) correctly stopped hostapd cleanly with no thrashing, but the
  udev `SYSTEMD_WANTS` auto-restart trigger did not fire either time -
  already recorded as a known, separately-tracked issue (see
  `docs/OPERATIONAL-DECISIONS.md`'s "New known issue found after
  closure" entry) and **not re-investigated or redesigned here**, per
  explicit instruction to keep this round about the RTL-SDR.
- **No ALFA/USB events occurred during the receive-test captures
  themselves** (only during physical cable handling beforehand) -
  actually operating the RTL-SDR (setting frequency, streaming) caused
  no observable instability of any kind.
- **`throttled` remained `0x50005` throughout** - the same pre-
  existing chronic condition (§ POWER-INTEGRITY-DIAGNOSIS.md), no new
  bit set, no new event coincident with any RTL-SDR activity
  specifically.
- The RTL-SDR itself stayed at the same USB device number for its
  entire characterization (no re-enumeration once seated) - it was not
  the source of any of this round's USB instability.

### 3a.6 Reassessed comparison: RTL-SDR vs. Malahit as a PirateBox backend

| | RTL-SDR (this unit) | Malahit V3 (HiDY), §2b/§11b |
|---|---|---|
| USB speed | High Speed (480 Mbit/s) | Full Speed (12 Mbit/s), shared across 10 interfaces |
| Power | Bus Powered, ~500mA from the Pi's own rail | Self Powered claim + own internal battery, charging behavior still unconfirmed |
| Software path | `librtlsdr`/SoapySDR - the ecosystem's de facto standard (§3, §5); genuinely tested this round only via the narrower no-install V4L2 direct-sampling path | Generic `SoapyAudio` on a confirmed, statistically IQ-like 160kHz USB-audio stream (§11b) - concrete but custom, no ready-made plugin confirmed to fit |
| Frequency range demonstrated | 27.185 MHz and 100.1 MHz both exercised via the real R820T tuner (§3b.3), plus 0.3-3.2 MHz via the no-install V4L2 path (§3a) - full ~24 MHz-1766 MHz range not exhaustively swept, but the tuner itself is proven functional across a wide span | Whatever the receiver itself is tuned to (455.000 MHz and 162.400 MHz both exercised, §11c) - much wider practical range already demonstrated, but via a bespoke path |
| Serial/CAT control | None needed for IQ - tuning is via the standard V4L2/librtlsdr API itself, no separate protocol to reverse-engineer | Two descriptor-identical, still-unidentified CDC-ACM ports; CAT protocol entirely unresolved (§11b.1) |
| OpenWebRX+ fit | Native, first-class support - no plugin, no bridge, the most standard possible integration | Doubtful `SoapyMalahitRR` fit; a generic-audio-plus-bridge path is plausible but unbuilt |
| Confidence this becomes a working browser-SDR backend | **High** - the only genuinely open question is Pi 3B+ CPU/RAM headroom (§4), not software support | **Moderate at best** - real, positive evidence exists (§11b/§11c), but CAT/tuning and firm OpenWebRX+ compatibility remain unresolved |

**Architectural conclusion, updated**: this round's physical evidence
reinforces rather than changes §3's original reasoning - RTL-SDR
remains the safer, better-trodden path to an actually-working
OpenWebRX+ integration, and this specific unit is a genuine,
positively-identified, well-supported chipset (not an unknown/exotic
one), which removes what had been the single biggest RTL-SDR unknown
in this document. The Malahit path is not weakened by this - the two
remain complementary candidate backends in the multi-backend design
(§8), and nothing here suggests preferring one over building both.

---

## 3b. `rtl-sdr`/`librtlsdr` package-install gate crossed - wideband tuner characterization (2026-09-05)

**Packages installed, with operator approval, from Debian's own
trixie/main repo (no third-party source)**: `rtl-sdr` 2.0.2-2+b1 and
its dependency `librtlsdr0` 2.0.2-2+b1 - exactly the two packages
`apt-get install rtl-sdr` pulls in, confirmed via a dry-run simulation
before installing. No other packages were installed; OpenWebRX+ was
not touched.

### 3b.1 Driver-conflict handling - investigated, no blacklist needed

Per instruction to investigate the normal approach first: **Debian's
`librtlsdr0` package does NOT blacklist the kernel's DVB driver at
all.** Its own shipped udev rule
(`/usr/lib/udev/rules.d/60-librtlsdr0.rules`) only sets device-node
permissions (`MODE="0660", GROUP="plugdev"`) for a long list of known
RTL-SDR VID:PIDs, including this unit's exact `0bda:2838` - it does
not attempt to unbind or blacklist `dvb_usb_rtl28xxu`. This matches
how `librtlsdr` is actually designed to work: it detaches the kernel
driver itself, at runtime, via libusb's kernel-driver-detach call,
each time a tool opens the device, and reattaches it on close - no
permanent blacklist required, and DVB-T functionality (for anyone
who'd want it) is left intact for when no SDR tool has the device
open. **Confirmed working exactly this way, repeatedly, over six
separate tool invocations this round**: every `rtl_test`/`rtl_sdr` run
printed `Detached kernel driver` on open and the kernel logged a clean
`successfully deinitialized and disconnected` at that moment, then
`Reattached kernel driver` on close, followed by the kernel re-
attaching `dvb_usb_rtl28xxu`/`rtl2832_sdr` cleanly every time - zero
errors, zero USB resets, zero leftover conflicts across the whole
round.

**One extra step was needed, and it wasn't a driver-conflict fix**:
the newly-installed udev rule only applies to devices on their next
"add" event - it does not retroactively fix permissions on a device
that was already enumerated (under the old, pre-install ruleset)
before the package existed. The device node still showed `root:root
0644` immediately after installing. Rather than physically
replugging the RTL-SDR (which had already caused two ALFA blips this
session via the shared extension cable), the minimal, standard,
non-destructive fix was a **scoped `udevadm trigger`** matching only
this device's exact VID:PID:

```
sudo udevadm trigger --verbose --subsystem-match=usb --attr-match=idVendor=0bda --attr-match=idProduct=2838
```

Confirmed effective (`crw-rw---- root plugdev`) and confirmed **not**
to touch the ALFA/hostapd/pb-ap in any way - verified immediately
before and after.

### 3b.2 Tuner identification, independently reconfirmed

`rtl_test` positively re-identified **"Found Rafael Micro R820T
tuner"** - the same identification the kernel's own driver made
independently in §3a, now confirmed a second way, via `librtlsdr`
itself. 29 discrete gain steps were enumerated, 0.0 dB to 49.6 dB -
the standard R820T manual gain range.

**`[R82XX] PLL not locked!` - investigated, not dismissed.** This
warning appeared on every single tune operation across the whole
round (both `rtl_test`'s internal self-test frequency and every real
target frequency tried: 27.185 MHz, 100.1 MHz, both with automatic and
manual gain). Despite the warning, every capture produced the exact
expected byte count with real, substantial, frequency-dependent
signal content (§3b.3) - **STRONGLY SUGGESTED** to be a benign,
cosmetic message from this exact R820T unit/driver-version
combination (a message printed once during the tuner's initial PLL
calibration step, common enough in the wider RTL-SDR/R820T community
to not be unusual, and one this document does not chase further since
actual reception was demonstrably unaffected) rather than a real
functional fault - **not proven benign with certainty**, since no
direct PLL-lock-status register readout was attempted; flagged as
NEEDS HARDWARE/further-tooling if it ever needs to be settled
conclusively.

### 3b.3 Wideband receive tests - CONFIRMED, and a real gain/overload finding

Three short (2-second, 4,096,000-sample) captures via `rtl_sdr`,
analyzed with Python stdlib only (a fast single-pass 256-bucket
histogram approach, not the `statistics` module, which is
impractically slow - multiple minutes - on multi-million-sample
arrays):

- **27.185 MHz** (near the R820T's practical low end, 11m/CB band):
  automatic gain, full 0-255 byte range used, **14.6% of samples
  pinned at the extreme rail values (0-2 or 253-255)**.
- **100.1 MHz** (FM broadcast band), automatic gain: full 0-255 range,
  **51.7% of ALL samples pinned at the rail** - severe clipping.
- **100.1 MHz, manual gain forced to 8.70 dB** (down from whatever
  automatic gain selected): **clipping eliminated entirely - 0.0% of
  samples at the rail**, with a healthy, well-distributed population
  (12.2% within a narrow near-center window, consistent with real
  signal+noise rather than saturation).

**CONFIRMED**: the receive chain (MLA-50+ antenna and its separately-
powered bias box, through the RTL-SDR's R820T front end, to the ADC)
was significantly overloaded at automatic gain, especially in the FM
broadcast band - and manually lowering gain completely resolved it in
one try. This is a real, useful characterization result about *this
specific antenna+receiver combination as currently connected*, not a
receiver defect: the R820T's manual gain control demonstrably works
correctly and precisely (requested ~9 dB, delivered the nearest actual
step, 8.70 dB), and the overload is consistent with a broadband active
loop antenna's own onboard amplifier delivering more signal than the
front end's default AGC setting was built to expect - a known,
common, and entirely fixable real-world RTL-SDR/active-antenna
pairing issue, not investigated further here per instruction (this
document is not becoming an antenna-performance investigation).
**Practical implication for any future implementation**: automatic
gain should not be assumed correct by default with this particular
antenna attached - a sensible default manual gain (or a proper AGC
implementation, if the eventual software stack has one) will matter
in practice.

### 3b.4 Sample rate / stability

- **2.048 Msps** (the RTL-SDR ecosystem's traditional default): stable
  across every capture at this rate, correct byte counts every time,
  no dropped-sample warnings.
- **3.2 Msps** (a commonly-cited practical maximum for this chipset):
  one 10-second, 32,000,000-sample (64,000,000-byte) capture completed
  with the **exact** expected byte count and **no "lost bytes" warning**
  (the specific, explicit signal `rtl_sdr` prints if the USB/host
  pipeline can't keep up) - clean, stable USB throughput at this rate
  on this Pi 3B+ over the tested window. `/proc/loadavg`'s 1-minute
  average moved from 1.17 to 1.29 across the capture - a small,
  unremarkable bump, not a sign of the Pi struggling. Higher rates
  (RTL2832U's real ceiling is often cited around 3.2 Msps as the
  practical safe maximum across the wider ecosystem, not just this
  Pi) were not tested - not necessary to establish practical viability
  for typical single-channel VHF/UHF reception, which needs far less
  than 3.2 Msps.
- No CPU-bound demodulation was tested (raw IQ capture to a file is a
  USB-throughput/disk-write workload, not a CPU-bound one) - real
  OpenWebRX+ CPU/RAM behavior under actual demodulation + a web
  client remains open (§4, §6, §12), unaffected by this round's clean
  raw-capture results either way.

### 3b.5 Power/ALFA/AP observations

- **Zero ALFA disconnects, zero USB resets, zero dmesg errors or
  warnings (beyond the already-discussed `[R82XX] PLL not locked!`)
  across this entire round** - a meaningful contrast with §3a, where
  two ALFA blips occurred, both during *physical handling* of the
  shared extension cable. This round involved no physical handling at
  all (the RTL-SDR stayed seated throughout, only software tools were
  run) and correspondingly showed zero instability - further
  supporting §3a's own conclusion that these blips track physical
  disturbance of a marginal connection, not RTL-SDR operation itself.
- `throttled` remained `0x50005` throughout - unchanged, same
  pre-existing chronic condition.
- `hostapd`/`pb-ap` remained healthy and untouched before, during, and
  after every test - verified explicitly around the `udevadm trigger`
  step and again at the end of the round.

### 3b.6 What this proves for OpenWebRX+, updated

This is now real, direct, tool-level evidence (not just descriptor-
level plausibility) that the standard `librtlsdr`-based path - the
same one OpenWebRX+ and every other researched browser-SDR candidate
(§5) uses for RTL-SDR - works cleanly end-to-end on this exact unit,
on this exact Pi: kernel-driver handoff, tuner control, gain control,
and sustained USB streaming at a realistic sample rate, all confirmed
with zero errors and zero collateral instability. The remaining open
question for OpenWebRX+ specifically is no longer "does the hardware
work" (yes) but "how does the Pi 3B+ perform under OpenWebRX+'s own
CPU-bound demodulation and waterfall-rendering workload, with a real
web client attached" (§4, §6, §12) - a software-performance question
now, not a hardware-support one.

---

## 4. Pi 3 B+ resource reality (grounded in this Pi's own live numbers)

Live baseline captured today, **2026-09-04, no SDR hardware
connected**:

```
$ nproc
4
$ free -h
               total        used        free      shared  buff/cache   available
Mem:           905Mi       802Mi        72Mi       596Ki       108Mi       102Mi
Swap:          904Mi       442Mi       462Mi
$ vcgencmd get_throttled
throttled=0x50005
$ vcgencmd measure_volts
volt=1.2000V
$ vcgencmd measure_temp
temp=39.7'C
$ lsusb -t
/:  Bus 001.Port 001: Dev 001, Class=root_hub, Driver=dwc_otg/1p, 480M
    |__ Port 001: Dev 002, If 0, Class=Hub, Driver=hub/4p, 480M
        |__ Port 001: Dev 003, If 0, Class=Hub, Driver=hub/3p, 480M
            |__ Port 001: Dev 005, If 0, Class=Vendor Specific Class, Driver=lan78xx, 480M
        |__ Port 003: Dev 004, If 0, Class=Vendor Specific Class, Driver=mt76x2u, 480M
```

**Important honest caveat**: the `free -h`/swap figures above were
captured while this same development session (Claude Code, several
concurrent background jobs) was running on this Pi, which is itself a
large, atypical memory consumer (500MB+ RSS observed for one process
alone) — **this is not a clean "PirateBox alone" baseline** and should
not be read as "PirateBox uses 800MB." The actual production daemons
are individually tiny: `piratebox_oled_daemon.py` ~13MB RSS,
`piratebox_button_daemon.py` ~5MB RSS, `php-fpm` worker ~3MB RSS. A
true idle-PirateBox memory baseline should be re-measured with no
development session active before sizing OpenWebRX+ against it.

What the topology **does** conclusively show, independent of that
caveat: this Pi 3B+'s **onboard Ethernet (`lan78xx`) and the ALFA
Wi-Fi adapter (`mt76x2u`) already share the exact same internal USB 2.0
hub and upstream 480Mbit link** — this is the well-known Pi 3B+
topology where one internal USB/Ethernet combo chip backs all four
physical USB-A ports *and* the onboard Ethernet jack. Any SDR USB
traffic (RTL-SDR sample stream, or Malahit's two audio-class streams)
would contend on that **same shared bus** as `eth0` and the AP's own
Wi-Fi-to-USB traffic — a real, structural bottleneck distinct from
"USB 2.0 is generically slow," and one worth remembering when a future
benchmark looks worse than a Pi-3B+-in-isolation number would predict.
**Three of four physical USB-A ports are currently free** (only the
ALFA occupies one) — there is physical room to attach both the Malahit
and the RTL-SDR without a hub, though a hub may still be the right
choice for power reasons (§8).

**CONFIRMED, 2026-09-05 (§2b)**: the Malahit negotiates **Full Speed
(12Mbit/s), not High Speed (480Mbit/s)** - its own hardware ceiling,
not a Pi limitation. Its confirmed stereo IQ-candidate stream (160000
Hz × 2 channels × 16-bit) alone is ~5.1Mbit/s of raw PCM - a
meaningful fraction of that 12Mbit/s budget shared across all ten of
the device's own interfaces simultaneously (both audio streams, both
serial ports). This is a real, device-side bandwidth ceiling to keep
in mind independent of anything the Pi's own USB topology does -
worth remembering once actual throughput/reliability testing happens,
not something to try to work around by moving the device to a
different Pi port (Full Speed is negotiated by the device itself, not
assigned by the host).

**REQUIRES TESTING** (research finding, §5): no source anywhere
benchmarks current OpenWebRX+ (2026 build, full decoder set) on an
actual Pi 3B+ under Trixie aarch64 at a specific sample rate/client
count. The oft-repeated "quad-core 1.4GHz/1GB = 1-2 listeners on one
band" figure is COMMUNITY folklore describing hardware that happens to
match the Pi 3B+'s spec, not a benchmark of this fork on this OS.
**This must be measured directly once software is actually installed
in a later phase** — not assumed favorably or unfavorably here.

Conservative starting-point settings worth trying **once we reach
that phase** (not implemented now, per instruction): a single narrow
sample-rate profile (e.g. RTL-SDR at ~1.024–1.2MHz bandwidth rather
than the common 2.4MHz "wide" default), FFT size 2048 rather than
4096+ (the standard community mitigation — VERIFIED as the dominant
lever from `config_webrx.py`'s own exposed settings), ADPCM audio/FFT
compression (the only two options `config_webrx.py` exposes — no
Opus/MP3 option exists for the live stream), and a low `max_clients`
ceiling (the config exposes this as a plain setting, default
commented at 20 — far too high to start with on this hardware).

---

## 5. Browser SDR software comparison

**OpenWebRX+ (`luarvique/openwebrx`) remains the recommended candidate
for the software layer, provisionally** — the only one that is
simultaneously actively maintained, Trixie-aware, and has any Malahit-
branded-ecosystem support at all. This recommendation is **for the
software choice**, not a claim that its Malahit plugin will work with
the owned hardware — see the 2026-09-05 update below the table, which
now leans toward that specific plugin probably NOT applying to the
owned V3 unit. Even if the Malahit path doesn't pan out, OpenWebRX+
remains the right choice on RTL-SDR-support/maintenance/Trixie-
compatibility grounds alone.

| Criterion | OpenWebRX+ | RTL-SDR support | Malahit support | Trixie/aarch64 | Offline UI | Pi 3B+ evidence |
|---|---|---|---|---|---|---|
| **OpenWebRX+** (`luarvique/openwebrx`) | Active, 2026 releases | Yes, dual path (native connector + SoapySDR) | **Yes** — dedicated `SoapyMalahitRR` plugin, mechanism partly unconfirmed | Explicit apt repo + changelog-tracked Trixie fixes | Verified — all JS/CSS vendored locally (one optional Google-Maps feature is the exception, avoidable) | None published; folklore only |
| jketterl/openwebrx (upstream) | **Dormant since Oct 2023** | Yes | Not established | Unknown | Same lineage | None |
| SDR++ | Active (desktop app) | Yes | No | N/A | N/A | N/A — no headless/web mode; maintainer explicitly rejected a headless-mode feature request |
| no-sdr | Active, newer | Yes, RTL-SDR-only | No | Docker/ARM64, tested Pi 4/5 only | Unverified | Untested on Pi 3B+ |
| Cascade-SDR | Active, newer | Yes, RTL-SDR-only | No | Unspecified | Unverified | Untested |
| PhantomSDR-Plus | Active | Yes, via SoapySDR | No | x86-centric design (wideband/GPU FFT) | Unverified | Poor architectural fit for Pi 3B+ |
| GNU Radio + custom | You build it | Yes, via gr-osmosdr | Possible, unbuilt | You control it | You control it | No turnkey multi-user web product exists today |
| BrowSDR (WebUSB) | Active, niche | Yes | No | N/A | N/A | Single-user-per-browser-tab model, not a shared appliance |

Key details behind the table:

- OpenWebRX+'s architecture already assumes **multiple SDR devices**
  via per-device profiles (`sdrs.json`) — not a single-receiver
  assumption we'd need to work around.
- RTL-SDR is supported **two ways**: a native `rtl-connector` (no
  SoapySDR needed at all) and via SoapySDR. This matters for keeping
  the dependency/build footprint down if Malahit support turns out not
  to pan out — RTL-SDR-only doesn't require installing the whole Soapy
  stack.
- The **Malahit path specifically** is `SoapyMalahitRR`
  (`luarvique/SoapyMalahitRR`, same author as OpenWebRX+, MIT
  license), listed as an optional dependency on the Arch AUR package.
  Its source tree contains ALSA *and* SPI/I2C/GPIO interface files —
  this reads more like a driver for a bare Malahit-R1 module wired
  directly to a companion SBC's GPIO bus than a driver that opens a
  finished handheld unit's USB-Audio-Class "Malahit IQ" interface over
  a cable. **This distinction was not resolvable from public
  README/metadata and is the single most important software unknown
  in this whole investigation** — it decides whether the Malahit path
  works at all for the owned hardware. NEEDS HARDWARE (and likely
  needs to read the plugin's actual source once fetchable, or ask in
  the OpenWebRX+ community).
  **2026-09-05 update, this concern is now stronger, not resolved**:
  now that the owned unit is confirmed to be a handheld "Malahit DSP
  SDR V3" (HiDY-manufactured), not a bare module, the plugin's own
  naming — "Malahit-**R1**" — reads increasingly like a *different*
  product in the broader Malahit-branded ecosystem entirely, distinct
  from the DSP1/DSP2/DSP3/DSP4/V3 handheld-receiver naming sequence
  by name alone. "R1" appearing nowhere in any handheld-unit
  documentation found in either research pass (original DSP2 research
  or the targeted V3 follow-up, §2a) is circumstantial but consistent
  with "R1" being a bare-receiver-module product, not a firmware
  variant of the handheld line. **This should be treated as making
  Malahit-path OpenWebRX+ compatibility LESS likely for the owned
  hardware than originally framed, not equally uncertain** — still
  NEEDS HARDWARE/needs-source-reading to settle definitively, but the
  prior should shift toward "probably doesn't apply" rather than
  "50/50."
  **2026-09-05, post-enumeration update (§2b)**: the physical evidence
  neither confirms nor rules out `SoapyMalahitRR` compatibility
  directly (that plugin's own source hasn't been read against this
  unit's actual behavior), but it does clarify what a *working*
  integration would actually need to consume: a device presenting as
  **plain USB Audio Class capture interfaces** (confirmed: one mono
  40kHz, one stereo 160kHz) plus **two indistinguishable CDC-ACM serial
  ports** of unknown individual function - not the SPI/I2C/GPIO-wired
  bare-module shape `SoapyMalahitRR`'s own source tree suggested (§5's
  original finding). This is a genuine, USB-standard-class interface
  shape that **generic** tooling (not a Malahit-specific plugin) could
  plausibly consume - see the `SoapyAudio` path discussed just below,
  which becomes a materially more concrete option now that the actual
  audio interface shape (channel count, sample rate, format) is known
  rather than assumed. **Net effect: the Malahit-specific plugin path
  looks no more promising than before (still probably a mismatch), but
  a generic-audio-interface bridge path looks more concrete and
  buildable now that its exact target shape is confirmed, not
  hypothetical.**
- No generic "audio card as IQ source" input type exists in
  OpenWebRX+ analogous to SDR#/HDSDR's "IQ from soundcard" — what
  exists is device-specific integrations that happen to use ALSA
  (FiFi-SDR's documented `arecord`-based setup is the closest
  precedent). If the Malahit path doesn't pan out, **`SoapyAudio`**
  (`pothosware/SoapyAudio`, confirmed to exist, generic sound-card
  SoapySDR plugin) is a plausible, untested fallback — it would let
  OpenWebRX+ see the "Malahit IQ" interface as an ordinary Soapy
  device with zero OpenWebRX+ code changes, but tuning/gain control
  would need to come from somewhere else (the CAT serial link, most
  likely, mirroring how FiFi-SDR needs an external `rockprog` call
  alongside its `arecord` audio capture). **2026-09-05: this path now
  has a confirmed, specific target** (§2b) - a stereo, 16-bit, fixed
  160000 Hz ALSA capture device (`hw:CARD=reciever,DEV=1`) - rather
  than a hypothetical "some audio interface." Still untested whether
  `SoapyAudio` actually enumerates and streams this specific device
  correctly, and CAT control still depends on resolving which (if
  either) `/dev/ttyACM*` port is the right one (§2b, §11's next step).
- Live-stream audio codec is limited to **ADPCM or raw PCM only** — no
  Opus/MP3 option for the real-time listen stream (MP3 exists only for
  an optional server-side recording feature). This is actually good
  news for CPU cost on a Cortex-A53.
- Default port **8073**, no default credentials (must explicitly
  create an admin user), README explicitly lists HTTPS support and
  reverse-proxy awareness as existing features (client-IP handling
  behind a proxy).
- Multi-user model is the classic WebSDR pattern: the server captures
  one wide slice of spectrum at a fixed center frequency; each browser
  client gets independent demodulation/tuning **within** that captured
  slice for free, but moving the hardware's actual center frequency is
  a shared, global action affecting every listener at once. This
  matters for the "what does 'Tune Receiver' mean with 2 visitors
  connected" question in §9.

---

## 6. What we still need (updated 2026-09-05 after physical enumeration, then again after §11b, then again after §3a's RTL-SDR round, then again after §3b's librtlsdr characterization)

1. **Malahit DSP SDR V3 (HiDY)** — most of what could be learned from
   the unit alone via USB is now in hand (§2b: VID:PID, interface
   shape, audio formats, topology; §11b: serial-port listen result,
   audio-stream behavior and statistical IQ corroboration). Still
   needed:
   - Firmware version — the one documented check method (long-press
     power button, no USB) did **not** work on this unit (§2b); no
     other passive method is currently known. Not to be chased further
     with untried button combinations.
   - Which `/dev/ttyACM*` port (if either) is CAT, and in what
     protocol — the DTR-aware listen test (§11b.1) was performed; both
     ports were silent. Resolving this further needs either an actual
     protocol probe (a fresh, evidence-backed gate) or accepting
     manual tuning as the first-implementation posture.
   - Why the mono/40kHz audio interface fails to stream in the unit's
     current state (§11b.2) — needs the operator's on-screen
     observation (§11b.4) before this can be narrowed further.
   - PCB revision marking — optional, only if the case is opened for
     an unrelated reason; not required.
2. **RTL-SDR**: identified (§3a) and wideband-characterized (§3b) —
   `0bda:2838`, genuine RTL2832U + Rafael Micro R820T, confirmed via
   `rtl_test`/`rtl_sdr` at 27.185 MHz and 100.1 MHz, gain control
   confirmed working (fixed a real overload at automatic gain), USB
   streaming confirmed stable at 3.2 Msps. Still needed:
   - Real OpenWebRX+ CPU/RAM/waterfall-rendering behavior on this Pi
     3B+ with a real web client (§4, §6.item 7, §12) — the hardware/
     driver/tuner path itself is now proven; this is a software-
     performance question, not a hardware-support one (§3b.6).
   - R820T vs. R820T2 exact revision — cosmetic only, `NEEDS HARDWARE`
     (would need opening the case or a vendor label check), not
     required for software planning.
   - `[R82XX] PLL not locked!`'s exact cause — appeared on every tune
     operation this round without any observed functional impact
     (§3b.2); not proven benign with certainty, not chased further.
3. **Magnetic-loop antenna**: no electrical unknowns block this
   investigation phase — it only matters once an actual receive test
   is attempted, well past this document's scope.

---

## 7. Optional-capability principle (reusing the project's own established rule)

`docs/ARCHITECTURE.md` §2 already states the exact governing rule,
verbatim: **"OPTIONAL CAPABILITY FAILURE MUST DEGRADE THE PIRATEBOX,
NOT DISABLE THE PIRATEBOX."** SDR is already explicitly named in that
same section's Optional/Field examples. This capability adds nothing
new to that principle — it's simply the next one to actually build
against it. Concretely, applying §4's own pre-install checklist
(PURPOSE / INTERFACE / POWER / PHYSICAL LOCATION / SOFTWARE OWNER /
FAILURE MODE / UI EXPOSURE) to Radio specifically:

- **PURPOSE**: optional local browser-SDR receive capability,
  complementing (never replacing) the existing static Radio reference
  content.
- **INTERFACE**: USB (Malahit and/or RTL-SDR), identified by
  udev `ENV{}` matching (VID:PID + driver), the same technique already
  proven for the ALFA — not ancestor-walk `ATTRS{}` matching, which
  the EXTERNAL-AP work already found to be structurally broken for
  composite USB devices.
- **POWER**: unresolved pending §11's physical test; the unit's own
  battery does not obviously solve this (§2's charging section, and
  §2a's more specific finding that charging appears bundled with any
  powered-on USB connection for this product line) and may need an
  externally-powered USB hub rather than direct Pi attachment as the
  long-term architecture.
- **PHYSICAL LOCATION**: attachable, external, user-managed (plug in
  when wanted, unplug when not) — not integrated into the enclosure.
- **SOFTWARE OWNER**: a new, separate systemd service (OpenWebRX+ or
  whatever is eventually chosen) — never the OLED daemon, never
  PHP-FPM directly, never a Core service.
- **FAILURE MODE**: SDR hardware absent → Radio UI shows a friendly
  "receiver not connected" state (mirrors `capability_state.php`'s
  existing NOT_INSTALLED/AVAILABLE/DEGRADED/UNAVAILABLE/UNKNOWN
  vocabulary — reuse it, don't invent a parallel one); SDR service
  crashes → PirateBox Core (AP, site, uploads, chat, reference library)
  and every other Operational capability (OLED, buttons) continue
  completely unaffected, exactly like an RTC or GNSS failure already
  degrades gracefully per that same document's own worked examples.
- **UI EXPOSURE**: a new `/radio/` (or `/utility/radio-live/` — naming
  TBD in a later implementation pass) page, reachable only when the
  backend service is actually running and healthy; the existing static
  `/utility/radio/` reference page is unaffected either way.

---

## 8. Proposed architecture (design only — nothing built yet; updated 2026-09-05 with the confirmed interface shape)

```
Radio Capability (optional, Operational-adjacent but Optional/Field layer)
├── Backend abstraction
│   ├── Malahit-family backend
│   │   ├── SoapyMalahitRR (if it fits this unit - still doubtful, §5) -OR-
│   │   └── SoapyAudio + a small CAT-bridge daemon, targeting the NOW-
│   │       CONFIRMED (§2b) stereo/16-bit/160000Hz ALSA capture device
│   │       for IQ, plus whichever /dev/ttyACM* turns out to be CAT
│   │       (§11a) for tuning - two separate, ordinary Linux interfaces
│   │       rather than one Malahit-specific plugin
│   ├── RTL-SDR backend   (native rtl-connector or SoapySDR - well-trodden;
│   │   §3a confirms this specific unit is a genuine RTL2832U + R820T,
│   │   the most standard, best-supported RTL-SDR chipset combination -
│   │   remains the more certain-to-work backend, now with the single
│   │   biggest unknown - "what chip is this actually" - resolved)
│   └── (future backends - same shape, no redesign needed)
├── OpenWebRX+ (or, if it turns out unfit, a lighter RTL-SDR-only
│   candidate from §5's table) - bound to localhost only, never
│   directly exposed
├── Nginx - the project's FIRST real HTTP reverse proxy (`proxy_pass`
│   + WebSocket upgrade headers), at a new location block, alongside
│   the existing fastcgi_pass-to-PHP-FPM pattern (unrelated, both can
│   coexist)
└── nftables - one new explicit allow/deny rule (the existing
    SSH-isolation denylist doesn't need to change, but a NEW listening
    service needs its own rule - the denylist covers "nothing new can
    reach SSH," not "this new service is reachable from the right
    place")
```

**What changed here, 2026-09-05**: the Malahit-family backend branch
is now drawn as two concrete alternatives rather than one uncertain
plugin, because §2b's physical enumeration confirmed this unit exposes
its likely-IQ stream as a **plain, standard USB Audio Class capture
device** (stereo, 16-bit, fixed 160000 Hz) - not something requiring
Malahit-specific USB handling at all. That means a **generic**
SoapySDR audio-input plugin (`SoapyAudio`) pointed at that one already-
known ALSA device, paired with a **small, separate CAT-bridge script**
(once §11a resolves which serial port, if either, is CAT) that
OpenWebRX+ calls out to for tuning, is now a concrete, buildable
architecture - not a hypothetical fallback. This is architecturally
cleaner than depending on a plugin (`SoapyMalahitRR`) whose own fit for
this hardware remains doubtful: it only assumes standard, already-
confirmed Linux interfaces (ALSA capture + a serial port), the same
class of interfaces `gr-osmosdr`/FiFi-SDR-style integrations already
use elsewhere in this ecosystem (§5).

Why this shape, not a bigger or smaller one:

- **A backend abstraction is justified, not abstraction for its own
  sake**: the Malahit and RTL-SDR genuinely need different software
  paths today (one has zero proven Linux precedent and one unresolved
  plugin; the other is the best-supported SDR device in the entire
  open-source ecosystem). The abstraction boundary already exists at
  the OpenWebRX+ "SDR profile" layer if that's the software we end up
  using — we would not be inventing a new one, just documenting how
  PirateBox's own capability-detection layer (`capability_state.php`
  or a Radio-specific sibling) decides which profile(s) are actually
  present and healthy.
- **Nginx reverse-proxying a backend service is new to this project**
  (confirmed by the internal audit: no `proxy_pass` exists anywhere in
  the current config, only `fastcgi_pass` to PHP-FPM). This is a real,
  first-of-its-kind architectural addition, worth naming explicitly
  rather than treating as a trivial config tweak — it needs
  WebSocket-upgrade headers (`proxy_http_version 1.1`, `Upgrade`/
  `Connection`), which nginx doesn't do by default for a plain
  location block.
- **Binding to loopback only, proxied through Nginx**, is how this
  stays consistent with "prefer visitors interact through the existing
  local PirateBox environment rather than casually exposing another
  unrestricted network service" — OpenWebRX+'s own default (port 8073,
  no auth by default beyond what you configure) must never be directly
  reachable on `pb-ap`; only Nginx's own already-hardened surface
  should be.
- **The existing SSH-isolation nftables rule (`iifname != {eth0, lo}
  tcp dport 22 reject`) already protects SSH from any future radio
  interface for free** — it's a denylist of trusted paths, not an
  allowlist tied to today's specific interfaces, per its own comment.
  It does **not**, however, automatically restrict the new radio
  *service's own port* — if OpenWebRX+ ever listens on anything beyond
  loopback (it shouldn't, per the design above, but the rule should
  exist as defense in depth), that needs its own explicit new rule,
  the same way the SSH rule is explicit today.
- **Core stays completely unaware.** No OLED code, no Progression
  code, no button-daemon code, no hostapd/dnsmasq config references
  Radio's existence. If the Radio service is stopped, disabled, or was
  never installed, the rest of PirateBox is bit-for-bit identical to
  how it behaves today. This is the same guarantee already proven for
  every other Optional/Field capability in this project.

**Reproducibility**: per the project's standing goal, a fresh clone
must be able to rebuild PirateBox without owning a Malahit or this
exact RTL-SDR. The Radio capability's install path (whenever it's
actually built) needs to be: (1) entirely opt-in (a documented, not
default-run, install step), (2) gracefully absent if skipped — the
site and AP must work identically without it — and (3) hardware-
adaptive at runtime (detect what's actually plugged in via udev/
capability-state, not hardcoded to "the Malahit" or "the RTL-SDR").
Nothing in this design assumes a specific unit at install time, only
at *runtime detection* time.

---

## 9. Integration with the existing offline reference library

This is **not greenfield** — `data/utility/radio/services.json`
already exists (25 entries), consumed by
`public/utility/radio/index.php`, with exactly the numeric fields a
future "Tune Receiver" action needs:

```json
{
  "id": "noaa-weather-radio",
  "name": "NOAA Weather Radio (All Hazards)",
  "freq_low_hz": 162400000,
  "freq_high_hz": 162550000,
  "common_modes": ["NFM"],
  "typical_receiver_mode": "NFM (narrow FM)",
  ...
}
```

The right design is to **read this existing schema**, not invent a
parallel one: a future "Tune Receiver" button on a reference entry
would (a) check whether a Radio capability is currently AVAILABLE
(same vocabulary as `capability_state.php`), and if so (b) hand
`freq_low_hz` (and `typical_receiver_mode`) to whatever tuning
mechanism the live backend exposes (OpenWebRX+'s own URL-parameter
tuning, if that's what's running, or a small glue endpoint otherwise).
New fields should only be added to `services.json` if something is
genuinely missing (nothing found to be missing yet) — not as a
default first move.

**Multi-user caveat carried over from §5**: if two visitors are
already listening to different parts of the spectrum, a "Tune
Receiver" click from a reference page is not a free/isolated action —
retuning the hardware's actual center frequency (as opposed to a
client's own demodulation offset within an already-captured band) is a
shared action affecting every current listener. Whatever the eventual
UI is, it should be honest about this rather than pretending each
visitor gets an independent receiver — this is a real
architectural constraint of the WebSDR pattern itself, not a
limitation specific to our implementation choices.

The distinction the user asked to preserve — **Reference information**
(always available, works with zero hardware) vs. **Live hardware
capability** (only when connected/healthy) — maps directly onto the
existing `/utility/radio/` static page (untouched, Core-adjacent,
always works) plus a new, clearly-separate live page/section that only
appears/links when the capability-state check says a receiver is
actually there. No merging of the two into one page is recommended —
keeping them physically separate pages is the simplest way to never
let one's absence break the other.

---

## 10. Security/network summary

- Visitor-facing surface: `/radio/`-style Nginx location on the
  existing `pb-ap`-bound Nginx, HTTP only (matches the rest of
  PirateBox — no HTTPS/fake-cert introduced, per instruction).
- Backend binds to `127.0.0.1` only; never directly reachable from
  `pb-ap` or `eth0`.
- No CDN/external JS/CSS required for the core receiver UI (verified
  for OpenWebRX+'s bundled assets); the one exception (an optional
  Google-Maps-based feature) should simply stay disabled, or be
  reconfigured to the bundled Leaflet renderer with no tile server
  configured, if we ever adopt this software.
- No new SSH-reachable surface — the existing denylist already covers
  this; a new explicit nftables rule should still be added for the
  Radio service's own port as defense in depth, scoped to "reachable
  from `pb-ap` only," mirroring how the ALFA's own interface is
  already the sole trusted AP path.
- Authentication: OpenWebRX+ has a built-in user system (no default
  credentials), likely more machinery than a fully-anonymous PirateBox
  visitor page needs — worth deciding deliberately later whether the
  live receiver page requires any login at all, or stays as open as
  the rest of the anonymous site.
- No transmit capability anywhere in this design — receive only, per
  instruction.

---

## 11. First physical hardware gate — Malahit DSP SDR V3 (HiDY) USB enumeration

**COMPLETE (2026-09-05) — see §2b for the full results.** The
procedure below is kept for the record (it's what was actually
followed, and documents the reasoning), but the gate itself has been
passed: the unit was connected, passively characterized, and left
connected without incident. **§11a below is the NEW next gate** -
read that first if you're deciding what to do next; the rest of this
section is historical.

### What actually happened, briefly

The unit was pre-charged separately, connected with a data cable while
powered on, and characterized via `lsusb -v`, `udevadm info`,
`/proc/asound`, and `dmesg` - all purely passive, no writes to any
interface. Power state was unaffected by the Malahit's own presence
(§2b's before/after table). The one documented firmware-version check
(long-press power button, no USB) did not work on this unit. The
original text below is preserved as-followed; see §2b for what it
actually found.

### Original text (as followed)

**Do not connect the V3 yet without reading this section.**

### Step zero — a no-USB-connection check, do this first regardless of anything else

Per §2a, this product line's firmware version is reportedly visible by
**long-pressing the power button at boot**, with no USB/Pi connection
involved at all. Do this first, on the radio alone, and note whatever
version string appears (and its exact format — e.g. whether it looks
like the clone's typical "1.10c"-style numbering or something else).
This costs nothing and directly resolves one of §12's open questions
before any power/USB precaution below even becomes relevant.

### Power precaution (read before connecting to the Pi)

§2a's targeted follow-up found something more specific — and more
cautionary — than the original DSP2 research: for this product line,
**"will not charge off the computer USB port if the [unit] is not
powered on," but "when powered on, it will both charge and connect to
the PC as an external sound device" simultaneously** (one community
source, one reported unit — not guaranteed to describe this exact
unit's firmware/hardware batch, but the most specific finding
available). Since the unit necessarily needs to be powered ON for its
USB Audio/CAT interfaces to enumerate at all (this is what we're
trying to observe), **this suggests there is no way to get meaningful
USB data enumeration from this device without also potentially
triggering charging** — a data-only cable alone may not be sufficient
protection the way it might be for a device with independent
charge-enable control. This Pi's 5V rail is independently known to be
marginal (~4.7V baseline, `0x50005` chronic). Given that, and without
deliberately adding a substantial, unknown charging load to that rail:

1. **Charge the unit to full from its own separate power source
   first** (a wall charger or any USB port that is NOT the Pi),
   ideally powered OFF while doing this. A full battery draws
   little-to-no charge current when subsequently connected elsewhere —
   this remains the single best mitigation available, and is now more
   clearly load-bearing given §2a's "charging is bundled with
   powered-on USB connection" finding above.
2. **Use a cable you know carries data pins** (some cheap USB-C cables
   are charge-only). If in doubt, use the cable that shipped with the
   unit.
3. **This first session is enumeration only, time-boxed to a few
   minutes** — not a "leave it plugged in" arrangement. We are not yet
   trying to determine safe long-term power architecture (a
   separately-powered USB hub, per your own question, remains the most
   promising long-term answer, but that's a later decision).
4. Watch `vcgencmd get_throttled` and `vcgencmd measure_volts` before,
   immediately after connecting, and again after a couple of minutes —
   the known baseline is `0x50005`/~1.2V core; anything that changes
   from that pattern should be treated as a signal to disconnect and
   reassess, not push through.
5. If you have a USB power meter or a multimeter comfortable with
   inline USB current measurement, inserting it between the Pi and the
   unit for this session would directly answer the open charging-
   current question — genuinely valuable if convenient, not required.

### Exact procedure

Run the **"before"** block first, with nothing new connected:

```
lsusb
lsusb -t
vcgencmd get_throttled
vcgencmd measure_volts
vcgencmd measure_temp
dmesg | tail -40
arecord -l
arecord -L
aplay -l
ls /dev/ttyACM* /dev/ttyUSB* 2>&1
```

Then connect the unit (powered ON, per the precaution above), wait
about 10 seconds, and run the **"after"** block:

```
lsusb
lsusb -t
vcgencmd get_throttled
vcgencmd measure_volts
vcgencmd measure_temp
dmesg | tail -60
arecord -l
arecord -L
aplay -l
ls /dev/ttyACM* /dev/ttyUSB* 2>&1
udevadm info -a -n /dev/ttyACM0 2>&1   # and /dev/ttyACM1 too if it exists - §2a
                                        # found one reported unit with two
lsusb -v -d <VID:PID from the new lsusb line>   # fill in once known - §2a's
                                                  # one reported unit showed
                                                  # ffff:0737, a hypothesis
                                                  # to check against, not
                                                  # an assumed value
```

Then wait a few minutes (still connected, still not touched/configured
further) and re-check power state once more:

```
vcgencmd get_throttled
vcgencmd measure_volts
```

**What we're looking for**: the new `lsusb` line(s) — §2's original
DSP2 research found three composite interfaces; §2a's one reported V3
unit is consistent with that same three-interface shape (IQ, audio,
CAT) but with two `/dev/ttyACM*` devices rather than one, so don't be
surprised either way — their VID:PID (checked against the `ffff:0737`
hypothesis, not assumed to match), whether 1-3 new `/dev/ttyACM*`
and/or new ALSA capture devices appear, and whether the power readings
hold steady or degrade.

**What we will NOT do during this pass, and why**: no driver
installation (nothing should be needed for standard USB Audio Class +
CDC-ACM devices, and if something IS needed, that's itself useful
information to report back, not something to solve mid-session), no
CAT/serial commands sent (a `screen`/`minicom` session with an unknown,
now-confirmed-to-possibly-differ-from-documented command set risks
confusing the radio for no benefit at this stage), no firmware
changes, no calibration changes, no production networking changes,
and **no deliberate attempt to reproduce the dual-encoder-button
reboot** (§2a) — it's recorded as observed, not something to
re-trigger for further study. Purely observational.

Once this is done and reported back, the same controlled process
repeats for the RTL-SDR (§3) — kept as a clearly separate before/after
comparison, not combined with this unit's own results.

---

## 11a. Next gate — why the two serial ports are a deliberate stopping point (added 2026-09-05; EXECUTED same day, see §11b)

§2b's descriptor-level inspection genuinely exhausted what passive USB
enumeration can prove about `/dev/ttyACM0` vs `/dev/ttyACM1` - both are
descriptor-identical, confirmed independently via `lsusb -v` and
`udevadm info -a` on both device nodes. Distinguishing them requires
actually opening at least one of them - which is where this
investigation is deliberately stopping to flag a real, specific risk
rather than just proceeding.

**The risk, specifically**: opening a USB-CDC-ACM serial device on
Linux commonly asserts the DTR (Data Terminal Ready) control line as
part of the normal `open()`/termios initialization, unless the calling
code explicitly suppresses that (e.g. a library flag, or careful
`stty` sequencing before any read/write). This is a well-known
behavior class - it's exactly why many DTR-sensitive embedded/hobbyist
devices (some Arduino boards being the most famous example) reset
themselves the moment a terminal program opens their port, with no
data ever having been transmitted. Nothing in this investigation's
research found any documentation either confirming or ruling out that
this Malahit V3's own firmware reacts to DTR assertion in any way -
and this unit has *already* demonstrated one undocumented, unexplained
reset trigger (§2a's dual-encoder-button behavior), which is exactly
the kind of firmware quirk that would make a DTR-triggered reset
plausible rather than far-fetched. Opening a port "read-only" (never
writing a CAT command) does not avoid this risk - the risk is in the
act of opening the port itself, before any read or write happens.

**This is why it's being treated as a genuine next gate, not something
resolved autonomously in this round**: it's a real technical
uncertainty with a plausible failure mode on hardware that has already
shown one unexplained reset behavior, not a question answerable from
already-available evidence.

**Recommended safe approach, for whenever this is pursued** (design
only - not performed in this round):

1. Use a serial library/tool that can explicitly suppress DTR/RTS
   assertion on open (e.g. Python's `pyserial` with
   `dsrdtr=False, rtscts=False`, and setting `dtr=False`/`rts=False`
   *before* calling `open()` where the library allows it - not every
   tool exposes this; a plain `cat`/`screen`/`minicom` open with
   default settings should be assumed unsafe until proven otherwise).
   `pyserial` is not currently installed on this Pi and would need an
   explicit go-ahead to install, per this project's own "no package
   installs without operator approval" rule - this alone is a reason
   this step waits for a deliberate decision rather than happening
   automatically.
2. With DTR/RTS suppressed, open ONE port at a time in pure read mode
   (never write) for a short, timed window (a few seconds), and see
   whether anything is emitted unprompted - §2's own research found a
   firmware feature description ("improved CAT information output,
   including S-meter data") suggesting some Malahit-family firmware
   versions push telemetry without being asked, which would make a
   pure listen genuinely informative without ever transmitting.
3. Only after that - and only with explicit go-ahead - would sending
   an actual probe (e.g. the Kenwood-TS-480-style `FA;` frequency
   query §2 documents for the genuine product) be appropriate, and
   even then, one port and one command at a time, watching for any
   sign of a reset before trying the second port.

A short, passive audio-capture byte-level sanity check (confirming the
mono 40kHz stream looks like demodulated audio and the stereo 160kHz
stream looks like wideband/noise-like IQ content, without ever
listening to or transcribing any actual audio content) remains a
separate, lower-risk option that doesn't share this DTR concern at all
(USB Audio Class interfaces are activated via a standard alternate-
setting switch, not a control line with device-specific reset
semantics) - this was not performed in this round either, since §2b's
descriptor-level evidence (channel count + sample rate signature) was
already strong enough to report as "strongly suggested," and doing so
wasn't necessary to reach a genuine architectural conclusion. It
remains available as a next step if firmer confirmation is wanted
before further architecture decisions are made.

**Update: this step was performed the same day — see §11b.**

---

## 11b. Second physical gate — CDC-ACM listen test and passive audio characterization (2026-09-05)

**Dependency installed:** `python3-serial` was already present on this
system as the Debian-packaged `python3-serial` 3.5-2 (apt, `all`
arch), providing `pyserial` 3.5 at
`/usr/lib/python3/dist-packages/serial/__init__.py`. **No installation
action was taken or needed** — it predates this investigation.
Recorded here per the operator's instruction to document anything that
becomes part of a reproducible diagnostic procedure.

### 11b.1 CDC-ACM listen test (`/dev/ttyACM0`, then `/dev/ttyACM1`)

**Procedure**: a small script opened each port with `dtr=False`,
`rts=False`, `dsrdtr=False`, `rtscts=False` set *before* `open()` and
re-asserted immediately after (guarding against the library itself
touching the lines during setup), then read-only for a fixed 5-second
window with **zero bytes ever written** to the port, then closed
cleanly. Full `lsusb`/`lsusb -t`/`dmesg`/`vcgencmd get_throttled`/ALFA
enumeration snapshots were taken immediately before and after each
port, one port at a time, ACM0 first.

**ACM0 result** — **CONFIRMED (this unit, second gate)**:
- Opened successfully with DTR and RTS confirmed low throughout.
- **0 bytes received** in the 5-second window — silence.
- Device remained `Bus 001 Device 009` throughout — no
  disconnect/re-enumeration event, no new `New USB device` line in
  `dmesg`, all 10 interfaces still present and bound to their original
  drivers in `lsusb -t`.
- ALFA (`Dev 008`) and all PirateBox services (hostapd, dnsmasq,
  nginx, php8.4-fpm) unaffected; `throttled` unchanged at `0x50005`
  (no new undervoltage event coincident with the test).
- **Operator visual check**: watched "intermittently, not
  continuously" (operator's own characterization) during and after the
  test window; observed **no reboot/startup sequence, no screen
  flash/flicker, no visible settings change, no blanking** — recorded
  as "no observed abnormal behavior," explicitly *not* as a
  continuous-monitoring guarantee.
- One new, reproducible artifact: two kernel `WARN::
  dwc_otg_hcd_urb_dequeue:639: Timed out waiting for FSM NP transfer
  to complete on <N>` lines appeared in `dmesg` at the moment the port
  was closed. **STRONGLY SUGGESTED** to be a host-controller-side (Pi's
  own `dwc_otg` driver), not device-side, artifact of the kernel
  cancelling a pending read URB on `close()` — not a USB disconnect,
  not accompanied by any interface renumbering, and (see below)
  reproduced again on ACM1 with a different, larger set of endpoint
  numbers, which is consistent with a generic close-time driver quirk
  on this specific host-controller/device combination rather than
  anything specific to one port or evidence of a device-side event.

**ACM1 result** — **CONFIRMED (this unit, second gate)**: identical
outcome — opened cleanly, DTR/RTS confirmed low, **0 bytes received**
in 5 seconds, device stayed at `Dev 009` with no re-enumeration, ALFA/
services/throttled unchanged. The same `dwc_otg_hcd_urb_dequeue` WARN
pattern reappeared at close (this time on 4 endpoints instead of 2),
reinforcing the "generic close-time artifact, not port-specific"
reading above.

**Conclusion on the two serial ports**: passive listening **did not
distinguish ACM0 from ACM1** — both are silent under a pure listen.
Per the operator's own explicit instruction, **this silence is not
being read as "neither port is CAT."** It may simply mean this
firmware does not spontaneously emit telemetry in its current
state/menu, or only responds to a specific query. Resolving which
port is CAT (if either) still requires either (a) sending an actual,
protocol-specific probe — which remains gated behind a fresh,
evidence-backed justification per the operator's own requirement 6,
not performed here — or (b) further passive inference this
investigation does not currently have a source for.

**Side finding, corroborating §2b's power/ALFA observation**: the full
`dmesg` history pulled at the start of this gate showed the ALFA
disconnecting and re-enumerating on its own at 12:15 PDT while the
Malahit was **completely unplugged** (it had been removed at 11:08 and
was not reconnected until 14:03). This is a second, independent ALFA
hiccup with zero Malahit involvement, and lines up with the operator's
own observation that the PirateBox Wi-Fi network briefly disappeared
during that same window. Per the operator's own instruction, this is
recorded as corroborating — not proving — that the ALFA's earlier
one-second-coincident disconnect (§2b) reflects a pre-existing,
Malahit-independent power/enumeration marginality rather than anything
caused by the Malahit specifically.

### 11b.2 Passive audio characterization

**Procedure**: two-second captures via `arecord`, one interface at a
time, with the same before/after device-stability checks. No data was
ever written to the playback interface. No numpy or other new package
was installed for analysis — statistics (mean/DC-offset, min/max,
RMS, Pearson correlation) were computed with the Python standard
library only (`wave`, `struct`, `statistics`, `math`).

**Mono/40kHz interface (`hw:2,0`)** — **CONFIRMED (this unit, second
gate)**: capture **failed immediately** with `arecord: pcm_read:2272:
read error: Input/output error` on both of two independent attempts;
only a bare 44-byte WAV header was ever written (no sample data). No
kernel-level error was logged for either attempt — this is a
userspace/ALSA-level read failure, not a device fault — and the
device remained fully enumerated and stable both times. This is a
real, reproducible finding (not a one-off glitch): in the unit's
current state, this interface does not currently deliver a live
stream on open.

**Stereo/160kHz interface (`hw:2,1`)** — **CONFIRMED (this unit,
second gate)**: capture **succeeded cleanly**, producing exactly
1,280,000 bytes of sample data (2s × 160000Hz × 2ch × 2 bytes,
matching the spec exactly) plus the 44-byte WAV header. This interface
streams live with no CAT command, no tuning action, and no setup
beyond a standard ALSA open — right now, in whatever state the
receiver happens to be in.

**Statistical analysis of the stereo capture** — **STRONGLY SUGGESTED,
now with statistical corroboration** (still not proof — no known-
signal test has been performed): Pearson correlation between the two
channels was **0.039** (near zero), RMS power ratio L:R was **0.991**
(near-perfectly balanced), and both channels had a DC offset near
zero (-0.5 on each). This is precisely the statistical signature
expected of **quadrature I/Q components** — two components meant to be
in quadrature (90° phase-separated) carry, by design, very little
linear correlation and (for a healthy receiver front-end) balanced
power. It is *not* the signature genuine dual-channel program audio
from a single receiver's output would be expected to show, which
would typically carry substantially higher L/R correlation (shared
program content, or an intentional mono-duplicated-to-stereo signal).
This meaningfully strengthens (without fully proving) §2b's original
channel-count/sample-rate-based inference that the 160kHz stream
carries IQ, not audio.

### 11b.3 Reassessed integration path, given §11b.1-§11b.2

- **SoapyAudio / generic USB-audio IQ path**: materially more credible
  than before this gate. The 160kHz interface is not just
  correctly-shaped by descriptor (§2b) but now also *behaves*
  correctly (streams cleanly, on demand, no CAT dependency) and
  *statistically looks like* IQ (this section). A `SoapyAudio`-backed
  IQ source needs nothing from the CAT ports at all for basic
  streaming — only for programmatic tuning, which could otherwise be
  done manually via the receiver's own controls in a first
  implementation.
- **`SoapyMalahitRR`**: unaffected by this round's findings; the
  naming-mismatch concern from §5/§2b stands exactly as before.
- **CAT bridge requirements**: still entirely unresolved. Neither port
  emitted anything unprompted, and both remain descriptor-identical.
  Determining CAT now requires either (a) locating this firmware's
  actual documented CAT protocol (Kenwood-style or otherwise) and
  sending one carefully-chosen, evidence-backed probe with explicit
  fresh operator go-ahead, or (b) accepting manual tuning (no CAT at
  all) as the first-implementation posture.
- **OpenWebRX+ integration**: the generic "sound-card SDR" pattern
  this document's own concept inventory already names (the FiFi-SDR
  precedent) now has direct, unit-specific behavioral support, not
  just descriptor-level plausibility. Whether OpenWebRX+ specifically
  handles a 160000Hz sample rate cleanly on this Pi 3B+/Trixie
  combination remains untested (§4, §6) — this gate improved
  confidence in the *source*, not in the *downstream software or
  Pi's runtime headroom*.
- **RTL-SDR**: entirely unaffected; remains the more certain,
  conventional fallback backend. Not touched in this gate.
- **Pi 3B+ resource constraints**: unaffected by this round; §4's
  open questions stand as before.
- **No production deployment**: nothing was installed, wired, or
  deployed in this gate either. `python3-serial` was already present
  and required no installation action; no SDR software, service, or
  systemd unit exists on this Pi.

### 11b.4 Next gate

Both remaining paths forward need the operator's eyes/hands, not
further autonomous investigation:

1. **What is the Malahit currently displaying?** — pure observation,
   zero button-press risk: current frequency, mode, and whether audio
   is audible from the unit's own speaker/headphone output right now.
   This alone would explain the mono/40kHz stream's immediate failure
   (e.g. if the receiver is currently muted, in a mode with no active
   demodulated-audio output, or otherwise not actively decoding
   anything).
2. **Optional**: tune to a known strong local broadcast station using
   the receiver's own normal tuning control (not any button
   combination) and report frequency/mode/signal strength as
   displayed. This would let a future short, passive capture attempt
   look for expected structure in the 160kHz stream (further
   corroborating the IQ hypothesis) and re-attempt the 40kHz capture
   in a state where audio ought definitely to be flowing.

Neither of these requires touching the serial ports again, installing
anything, or approaching the dual-encoder-button behavior.

---

## 11c. On-screen observation and known-frequency capture (2026-09-05)

**§11b.4's on-screen observation, before retuning** (untouched state
during all of §11b's captures) — **CONFIRMED (this unit, direct visual
read, operator's transcription)**: `455.000 MHz`, `NFM`, 100 Hz tuning
step, 160 kHz spectrum span displayed, waterfall active, a narrow
visible feature at/near the tuned center, audio icon showing enabled
(not muted), and **audible static from the speaker**.

The full settings ("HARD") screen was also read, unchanged, purely
observational: SW antenna 50Ω, PREAMP disabled, ATT 1dB, RF GAIN 4,
F correct 0, Sm correct 0dB, `Audio out: Ph+Sp`, PGA Gain -12.00dB,
PGA BST enabled, ENC reverse disabled, **IQ swap: disabled**. No
setting was changed to obtain this reading. `F correct: 0` and
`Sm correct: 0dB` mean no frequency or S-meter calibration offset is
currently applied, which is useful context for any future signal-level
interpretation. `IQ swap: disabled` is useful context for any future
I/Q-channel-order-dependent analysis (e.g. determining the sign of a
frequency offset from the USB stereo stream).

**This is a significant finding, not just a state snapshot**: audio
was confirmed audible (static) at the physical speaker at 455.000 MHz
— the exact frequency/mode the mono/40kHz USB capture had already
failed on twice in §11b.2. This rules out "receiver currently muted"
or "squelch fully closed with the analog path silent" as an
explanation for that stream's failure, since the analog audio path was
demonstrably live at the time.

**Known-frequency retune, using only the normal tuning control** (per
operator's own statement — no button combinations, no calibration
changes): `455.000 MHz` → **`162.400 MHz`** (the first of the seven
standard NOAA Weather Radio channels, already documented in this
project's own `data/utility/radio/services.json`), mode left on NFM.
Result: **audible static, not an intelligible broadcast** — either no
NOAA transmitter covers this location at useful signal strength, or
the specific active channel locally is one of the other six, not
162.400 exactly. Not pursued further as an intelligible-content test
in this round (see §11c.3 below for why this wasn't necessary to reach
a conclusion).

### 11c.1 Third mono/40kHz capture attempt — now frequency/mode/squelch-independent

**CONFIRMED (this unit, third attempt)**: at 162.400 MHz/NFM, with
audible static confirmed present at the speaker, the mono/40kHz
capture (`hw:2,0`) **failed identically** to both §11b.2 attempts —
same `arecord: pcm_read:2272: read error: Input/output error`, only a
44-byte WAV header written, no kernel-level error, device fully
stable throughout (confirmed via the same before/after `lsusb`/
`dmesg`/ALFA/`throttled` checks as every prior test in this
investigation).

Three failures now, across two different tuned frequencies, with the
analog audio path confirmed live both times: this interface's failure
to stream is **evidence-backed as independent of tuned frequency,
mode, and squelch state**, not explained by "nothing to demodulate
right now." The actual cause (a specific alt-setting/negotiation
requirement `arecord`'s default invocation doesn't satisfy, a
bandwidth-sharing quirk given the very tight shared Full-Speed budget,
or something else entirely) remains unknown and is not chased further
in this round — it would require either testing with a different tool/
invocation, or examining the interface's exact alt-setting descriptors
in more depth than plain `arecord -D hw:2,0` exercises.

### 11c.2 Second stereo/160kHz capture and corrected phase-difference analysis

**CONFIRMED (this unit)**: a second clean 2-second stereo capture was
taken at 162.400 MHz/NFM, structurally identical to §11b.2's capture
(exactly 1,280,000 bytes of sample data). Correlation/power statistics
matched closely: Pearson correlation **0.0143** (vs. 0.039 before),
RMS ratio **0.979** (vs. 0.991 before), both channels' DC offset near
zero — consistent, reproducible corroboration of the quadrature-I/Q
reading across two different tuned frequencies, not a one-off result.

**A new check was added: an instantaneous-frequency estimate**, treating
consecutive (L,R) sample pairs as complex I+jQ samples and computing
the phase angle of `z[n] · conj(z[n-1])` across a 20,000-sample window
(pure Python `math`/`statistics`, no new package). The intent: a
dominant stable tone or DC/LO-leakage spike would produce phase
differences tightly clustered around one value (low standard
deviation); broadband noise would scatter phase differences roughly
uniformly across the full ±π range (standard deviation approaching the
π/√3 ≈ 1.814 rad theoretical maximum for a uniform-random circular
variable).

**Self-correction, in the interest of this document's own provenance
standards**: the first pass through this analysis used an uncalibrated
threshold (`> 2.0 rad = noise-like`) and mis-classified the very first
result (1.86 rad) as "tone-like" — this was wrong, and was caught and
corrected before being reported to the operator, by computing the
actual theoretical maximum for a uniform-random circular variable and
comparing against it properly.

**Corrected result, both captures**:
- §11b.2's original capture (455.000 MHz state): stdev **1.7903 rad**
  (98.7% of the 1.8138 rad theoretical maximum).
- §11c's new capture (162.400 MHz): stdev **1.8628 rad** (102.7% of
  the theoretical maximum).

**STRONGLY SUGGESTED**: both captures are essentially indistinguishable
from pure uniform-random phase noise — consistent with the audible
"static" reported at both frequencies, and showing no evidence of a
single dominant stable tone or DC/LO spike large enough to shift the
aggregate statistic. This does **not** rule out a weak spike or narrow
carrier sitting underneath the noise floor — this time-domain estimator
averages across the whole capture and cannot resolve that without a
proper spectral (FFT/PSD) analysis, which was not performed (no FFT
library is installed, and implementing one was judged out of scope for
this passive-characterization round).

### 11c.3 Reassessment — why an intelligible-content test wasn't pursued further

162.400 MHz did not yield an intelligible NOAA broadcast at this
location, and this round stops short of asking for a fourth retune to
chase one. The evidence already gathered is sufficient to update the
architecture assessment without it:

- The 40kHz/mono failure is now well-established as reproducible and
  state-independent — a real characteristic of this interface on this
  unit, not a symptom of "nothing playing right now." Any future
  implementation attempt should expect to need to solve this
  specifically (a different capture tool/invocation, or deeper
  alt-setting-level debugging), not assume it will resolve itself once
  the receiver has "real" audio to send.
- The 160kHz/stereo interface's IQ characteristics (balanced power,
  near-zero correlation, noise-like phase statistics matching the
  audibly-confirmed static) are now corroborated at two different
  tuned frequencies, which is stronger evidence than a single
  observation, even without an intelligible known-signal capture.
  A definitive "yes, this is unambiguously IQ carrying a real decodable
  signal" confirmation still awaits either an actual intelligible
  capture or spectral analysis - both reasonable future steps, neither
  performed here.

---

## 12. Open questions (updated 2026-09-05 after physical enumeration, then again after §11b, then again after §11c, then again after §3a's RTL-SDR round, then again after §3b's librtlsdr characterization)

**Resolved or substantially narrowed by §2b's physical enumeration:**

- ~~This unit's actual `lsusb` VID:PID~~ — **CONFIRMED**: `ffff:0737`,
  matching the one community-reported value found in §2a exactly.
- ~~Whether one or two `/dev/ttyACM*` devices appear~~ — **CONFIRMED**:
  two (`ttyACM0`, `ttyACM1`), descriptor-identical.
- ~~USB connector type~~ — moot for the Pi-side investigation now that
  the unit is confirmed connected via USB-C with a working data cable.
- Whether the audio interfaces carry anything resembling "Malahit
  RX"/"Malahit IQ" — **STRONGLY SUGGESTED, with statistical
  corroboration at two different tuned frequencies** (still not
  proven): mono/40kHz and stereo/160kHz respectively, by
  channel-count/sample-rate signature (§2b) *and*, for the 160kHz
  stream, by near-zero L/R correlation, balanced RMS power, and
  near-uniform-random phase-difference statistics matching audibly-
  confirmed static, reproduced independently at 455.000 MHz (§11b.2)
  and 162.400 MHz (§11c.2).

**Resolved or narrowed by §11b (the CDC-ACM listen test + audio
capture) and §11c (on-screen observation + known-frequency retest):**

- ~~Whether either `/dev/ttyACM*` port emits anything unprompted~~ —
  **CONFIRMED**: neither does, over a 5-second read-only window each,
  with DTR/RTS held low. Per the operator's own instruction, this is
  *not* read as proof neither port is CAT (§11b.1).
- ~~Whether opening either serial port destabilizes the device~~ —
  **CONFIRMED**: no. Both opens/closes left the device at the same
  `Bus 001 Device 009`, all 10 interfaces intact, ALFA/services/
  power unaffected. A reproducible `dwc_otg_hcd_urb_dequeue` kernel
  WARN appears at close on *both* ports — read as a generic
  host-controller artifact, not device-side evidence (§11b.1).
- ~~Whether the mono/40kHz and stereo/160kHz interfaces actually
  stream on open~~ — **CONFIRMED, now frequency/mode/squelch-
  independent**: the 160kHz interface streams cleanly on demand with
  no setup at both tested frequencies; the 40kHz interface
  reproducibly fails with an ALSA-level I/O error across three
  attempts at two different tuned frequencies, including one where
  audible static was confirmed present at the physical speaker —
  ruling out "nothing to demodulate right now" as the explanation
  (§11b.2, §11c.1).
- ~~Whether the receiver was muted/squelch-closed during the failed
  mono captures~~ — **CONFIRMED: no.** Audio icon showed enabled and
  static was audible at the speaker during the 455.000 MHz captures
  (§11c), yet the mono stream still failed identically.

**Still genuinely open:**

1. Does `SoapyMalahitRR` (naming: "Malahit-**R1**") actually work with
   this unit's confirmed USB Audio Class interfaces, or does it expect
   a different, bare wired module product entirely? Still NEEDS
   HARDWARE-level testing or source-reading to settle; no physical
   gate so far has changed the underlying naming-mismatch concern (§5,
   §2b).
2. Which, if either, `/dev/ttyACM0`/`/dev/ttyACM1` is CAT control, and
   in what protocol — still descriptor-identical and now also
   confirmed silent-under-passive-listen on both; resolving this
   further requires either an actual protocol-specific probe (a fresh,
   evidence-backed gate, not yet reached) or accepting manual tuning
   as the first-implementation posture (§11b.1, §11b.3).
3. This unit's firmware version — the one documented check method did
   not work on this unit (§2b); no other passive method is known.
4. Why the mono/40kHz interface fails to stream, now confirmed
   independent of frequency/mode/squelch (§11c.1) — the actual cause
   (alt-setting negotiation, bandwidth sharing, or something else)
   remains unknown and would need a different capture tool/invocation
   or deeper descriptor-level debugging to pin down.
5. Whether the 160kHz stream carries a real, decodable signal (vs.
   just noise at whatever frequency happens to be tuned) — the
   statistical evidence is consistent with IQ carrying broadband noise
   at both tested frequencies (neither produced an intelligible
   analog signal); a genuinely intelligible known-signal capture or
   spectral (FFT/PSD) analysis would strengthen this further but
   wasn't pursued in this round (§11c.3).
6. ~~This RTL-SDR's exact model/VID:PID, and whether it works as a
   wideband tuner via the standard software path~~ — **CONFIRMED**
   (§3a, §3b): `0bda:2838`, genuine Realtek RTL2832U + Rafael Micro
   R820T (T vs. T2 revision undistinguishable from software, doesn't
   matter functionally). `rtl_test`/`rtl_sdr` (the standard
   `librtlsdr` tools, installed with operator approval) confirmed
   clean kernel-driver detach/reattach, working gain control (fixed a
   real automatic-gain overload), and stable 3.2 Msps USB streaming -
   real tool-level evidence, not just descriptor-level plausibility.
7. ~~Real OpenWebRX+ CPU/RAM behavior on this actual Pi 3B+/Trixie,
   for the RTL-SDR path~~ — **CONFIRMED for one client** (§13.5):
   `openwebrx` ~10-14% CPU, `rtl_connector` ~11-27% CPU (settling
   ~12-13%), ~6.5-7% RAM, `throttled` unchanged. **Still open**: 2
   simultaneous clients (the configured `max_clients`), a real
   browser's own JS/rendering overhead, and sustained multi-minute
   operation - all untested. No published benchmark exists for the
   Malahit path on this hardware either way (§4, §5), and the Malahit
   path remains untouched/experimental per instruction.
8. Actual USB charging current draw — the "Self Powered" descriptor
   bit (§2b) is a favorable but not dispositive sign; no direct
   current measurement has been taken.
9. Whether the ALFA's disconnects/re-enumerations reflect a genuine
   hardware-interaction pattern or a pre-existing, hardware-
   independent power marginality — now observed **four** times across
   this investigation (§2b, a Malahit-independent instance in §11b.1,
   and two more in §3a.5, both directly attributable to physical
   handling of a shared USB connection point while working on the
   RTL-SDR, not spontaneous). The pattern increasingly looks like
   "physical disturbance of a marginal connection triggers a blip,
   regardless of which device is involved" rather than anything
   specific to the Malahit or the RTL-SDR - still observational, not a
   controlled test, but the accumulated evidence points more toward
   general connection/power marginality than device-specific causation.
10. Whether a separately-powered USB hub becomes the long-term
    architecture for one or both devices (§2b, §8) - the RTL-SDR
    round's repeated physical-handling-triggers-ALFA-blip pattern
    (§3a.5) makes this more attractive, not less.
11. The dual-encoder-button reboot/reset behavior (§2a) remains
    unexplained by any source found — not to be actively investigated
    further ourselves; worth asking about if this project ever engages
    the OpenWebRX+/Malahit community directly.

None of these block writing this document; all of them block writing
any code.

---

## 13. OpenWebRX+ implementation — installation, two build incidents, and verified real reception (2026-09-05)

With RTL-SDR hardware/software support proven (§3a, §3b), this section
covers moving from investigation into an actual, reproducible
OpenWebRX+ install (`tools/install_openwebrx.sh` and the config/
systemd/nginx files under `etc/`). See that script's own header
comment for the full, current install-method rationale; this section
records the *evidence and incidents* behind it, updated as the install
progresses.

### 13.1 Installation method chosen

Upstream's own `openwebrx-plus` apt repository
(luarvique.github.io/ppa) is **x64-only** and does not cover this
Pi's arm64/Debian-Trixie combination - confirmed before writing any
installer, not assumed. The installer instead follows upstream's own
documented "Manual Package installation" method (shared by the
original `jketterl/openwebrx` wiki and this project's chosen
`luarvique/openwebrx` fork, both building on the same
`csdr`/`pycsdr`/`owrx_connector` foundation), with two evidence-backed
adaptations: a dedicated Python venv instead of a system-wide
`setup.py install` (modern Debian's PEP 668 blocks the latter), and
seeding the SDR/profile configuration via OpenWebRX+'s own documented
`config migrate` command reading a classic-format file, rather than
hand-writing the modern JSON config store OpenWebRX+ itself says
isn't meant to be edited by hand. Confirmed via source inspection
(not assumed): OpenWebRX+'s own frontend JS constructs every asset
and WebSocket URL relative to `window.location.href` itself, making
it genuinely subpath-reverse-proxy-safe - the basis for choosing
`http://piratebox/radio/` over a separate hostname/port. Also
confirmed: OpenWebRX+ has its own complete built-in session/login
system gating `/settings*` (`AuthorizationMixin`), separating
administrative SDR configuration from the open visitor receiver page
without needing an additional nginx-level auth layer.

### 13.2 csdr build failure #1 — upstream `errhead()` bug (aarch64/GCC 14) - patch since superseded, see §13.4

First live install attempt stopped during csdr compilation:
`implicit declaration of function 'errhead'`. **Root cause,
investigated from the actual failed-build source tree, not assumed**:
csdr's `CMakeLists.txt` unconditionally enables a `NEON_OPTS` debug-
trace code path for every aarch64 build. That path calls `errhead()`,
which is defined *only* in the separate `csdr.c` CLI tool (a different
translation unit, never linked into the shared library) and depends
on that tool's own `argv_global`/`argc_global` - neither declared in
any shared header. This affects any aarch64 build of csdr's current
`master`, not something specific to this install: older GCC only
warned on the implicit declaration (leaving a latent, likely-dead
reference in the built library); GCC 14+ (Debian Trixie's default)
promotes `-Wimplicit-function-declaration` to a hard error for C,
turning this long-latent bug into an outright build failure.
**Confirmed via upstream research**: already reported as
[jketterl/csdr#13](https://github.com/jketterl/csdr/issues/13)
("does not compile under Raspbian Trixie [FIX]"), byte-for-byte
identical error text, but the issue is open with no merged fix and no
comments containing a proposed patch.

**Fix**: `etc/openwebrx/patches/csdr-errhead-neon-aarch64.patch` adds
a local, `NEON_OPTS`-scoped stand-in for `errhead()` directly in
`libcsdr.c` that preserves the intended trace-prefix behavior without
the bogus cross-translation-unit dependency - minimal, documented in
the patch's own header (including the upstream issue link), verified
to apply cleanly against the actual failed-build checkout before being
committed, and applied by the installer itself idempotently (a
marker-string check, so a re-run doesn't try to double-apply it).

### 13.3 Reboot incident during resumed csdr build — a genuine power/sustained-load finding

The patched build was re-run and progressed cleanly past the
`errhead()` failure point, reaching approximately 90% of csdr's own
build (multiple C/C++ objects, including its optional codec modules
like `fastddc`/`ima_adpcm`) before the operator's terminal output
stopped advancing. After roughly 15 minutes of no further output, the
operator opened a second SSH session and found: no `make`/`gcc`/`g++`/
`cc1`/`ld` processes running at all, an uptime of only ~19 minutes
(far shorter than the build's own elapsed time), and a fresh
`hwmon hwmon1: Undervoltage detected!` line early in the current
boot's `dmesg`.

**CONFIRMED, via `journalctl --list-boots`**: the Pi genuinely
rebooted (exactly one boot record, started well after the build had
begun) - this was a real reboot, not a stale/dead SSH session
illusion.

**NOT independently provable**: that undervoltage specifically caused
this reboot. This system has no persistent journald storage (`/etc/
systemd/journald.conf` has no `Storage=` override, defaulting to
`auto`, and no `/var/log/journal` exists) - the crashed boot's own
journal is genuinely unrecoverable, and `Undervoltage detected!` is
the same routine message this chronically undervolted Pi (§ POWER-
INTEGRITY-DIAGNOSIS.md, `throttled` a standing `0x50005`) logs early
in *every* boot, not a signal unique to this one. Per the operator's
own explicit instruction, this is recorded as a **strong candidate,
not a proven root cause**.

**What is a genuine, evidence-backed new data point**: no prior stress
anywhere in this entire investigation - RTL-SDR raw captures (§3b.4,
up to 3.2 Msps for 10 seconds), USB enumeration/hotplug events,
serial/audio characterization - involved *sustained* full-core CPU
load for minutes at a time the way a 4-way-parallel (`make -j4`, this
Pi 3B+'s `nproc`) C/C++ compilation does. That this specific, novel
load profile is the first thing in the whole investigation to
coincide with a full reboot (rather than the previously-seen pattern
of USB blips/re-enumerations) is a reasonable, evidence-consistent
basis for a direct mitigation, without needing to claim certainty
about the exact mechanism.

**Mitigation applied**: `tools/install_openwebrx.sh` now caps build
parallelism at `BUILD_JOBS=2` (half this Pi's 4 cores) for both the
csdr and `owrx_connector` builds, with the reasoning recorded directly
in the script, plus timestamped progress echoes around both `make`
invocations so a future interruption is easier to diagnose from
terminal scrollback alone (the only surviving record, given no
persistent journal).

**What survived the interruption, confirmed live rather than
assumed**: the [1/8] apt-dependency and [2/8] system-user steps had
already completed and remained correctly in place after the reboot;
the csdr source checkout and applied patch both survived on disk;
`/usr/local/lib/libcsdr.so` did **not** exist (the build/install never
completed); `owrx_connector` had not yet been cloned at all (the
crash happened within csdr's own extended multi-target build, not a
later stage as its build's file names might otherwise suggest -
`fastddc`/`ima_adpcm`/etc. are csdr's own optional codec modules, not
`owrx_connector`'s). No damaged or inconsistent state was found -
`pb-ap`/hostapd/dnsmasq/nginx were all healthy on the fresh boot
(normal systemd bring-up, unrelated to any installer or recovery
action), and the RTL-SDR re-enumerated normally.

**Recommendation, not acted on this round** (per instruction not to
make unrelated system changes merely because they'd be useful):
enabling persistent journald storage (`Storage=persistent` +
`mkdir -p /var/log/journal`) would let a future crash like this one
actually be diagnosed from logs instead of relying on terminal
scrollback and reasoning about what's missing from disk. Worth doing
as its own small, deliberate, operator-approved change - not bundled
into this OpenWebRX+ work.

**Also confirmed, directly relevant to whether BUILD_JOBS=2 helped**:
the re-run at the reduced parallelism completed the entire remaining
build (csdr through the original `owrx_connector`/`pycsdr`/`openwebrx`
stages) with **no second reboot**. This does not prove BUILD_JOBS=2
fixed anything, and does not prove the original reboot was power-
related - it is one data point in a small sample, recorded honestly as
useful-but-inconclusive evidence, not upgraded to a claimed fix.

### 13.4 csdr build failure #2 (masked by #1) — wrong upstream fork entirely

With the reboot mitigated, the install completed and started
`openwebrx.service` for the first time - which crashed immediately:

```
ImportError: cannot import name 'NoiseFilter' from 'pycsdr.modules'
```

**Root cause, confirmed by inspecting the actual installed commits and
the real upstream repositories - not assumed from the error text
alone**: this installer had been cloning `csdr`/`pycsdr`/
`owrx_connector` from **jketterl's original repositories**, per the
"Manual Package installation" wiki's own literal instructions. Those
repositories stopped receiving updates years ago -
`jketterl/pycsdr`'s own last-ever tag is `0.18.2`, dated **October
2023**, confirmed by listing its tags directly (nothing newer exists).
Meanwhile `luarvique/openwebrx` (correctly used from the start) is
under active, current development and its own `debian/control`
declares `python3-csdr (>= 0.18.40)` as a hard dependency - a version
that simply does not exist anywhere in jketterl's dormant pycsdr
history.

**The actual fix, confirmed rather than guessed**: `luarvique`
maintains his **own** actively-developed forks of `csdr`, `pycsdr`,
**and** `owrx_connector` (all three touched within days of this
writing, per GitHub's own repository listing for that account),
specifically so all four components stay mutually compatible - this
is the intended upstream dependency relationship for the OpenWebRX+
fork this project chose, not an alternate/unofficial source. Confirmed
directly, not inferred from version numbers alone: `NoiseFilter` is
genuinely present in `luarvique/pycsdr`'s source
(`pycsdr/modules.pyi`), and `luarvique/pycsdr`'s `master` branch
exactly matches its own `0.18.40` tag - precisely satisfying
OpenWebRX+'s declared minimum. A useful side effect: `luarvique/csdr`
has also been substantially restructured since diverging from
jketterl's original (modern header-based C++ under `include/*.hpp`,
no more monolithic `libcsdr.c`/`csdr.c`) - the `errhead()`/`NEON_OPTS`
bug patched in §13.2 does not exist anywhere in this source, so that
patch (`etc/openwebrx/patches/csdr-errhead-neon-aarch64.patch`) has
been removed from the repo - it no longer applies to anything this
installer touches, and jketterl's csdr is no longer cloned at all.

**Fix implemented**: the installer now clones all four components
(`openwebrx`, `pycsdr`, `csdr`, `owrx_connector`) from `luarvique`'s
account, each **pinned to a specific tested commit** rather than
tracked at a moving `master` - deliberately, so a future run can't
silently drift into a similar cross-repo incompatibility again the way
tracking `master` independently for each component already did once.
A shared `ensure_repo_at()` helper enforces this idempotently: if a
source directory already exists but points at the wrong remote or the
wrong commit - exactly the state left behind by the original
jketterl-sourced install - it is removed and re-cloned rather than
silently left in place. This closes a real bug the diagnosis surfaced
in the installer's own prior idempotency logic: checking only "does
`/usr/local/lib/libcsdr.so` exist" or "is `rtl_connector` on PATH"
would have let an already-built, wrong-source library silently pass as
"already installed" on a naive re-run, never actually fixing anything -
both checks are now gated on whether the source checkout itself needed
correcting, not just on a build artifact's bare existence.

**Not Python 3.13/Trixie's fault**: checked directly rather than
assumed innocent - the actual failure was an `ImportError` for a
symbol that never existed in the specific (stale) compiled extension
being imported, not a Python-version compatibility error of any kind;
the same import would have failed identically on any Python version
against that same wrong-source pycsdr build.

### 13.5 Verification — real reception, `/radio/` proxy, and Pi 3B+ performance under actual load (2026-09-05)

With the corrected fork/pinning fix installed, `openwebrx.service`
started cleanly (`NRestarts=0`, "Ready to serve requests." in the
journal, listening on `127.0.0.1:8073` only - confirmed via `ss`, not
exposed on any other interface).

**One real, minor config bug found and fixed**: startup logged
`WARNING - start_freq for profile "fm-broadcast" is out of range` -
the seed's `fm-broadcast` profile set `center_freq` to 98 MHz but
`start_freq` to 100.1 MHz, 2.1 MHz away - outside the ~1.024 MHz half-
width a 2.048 Msps profile actually covers. Fixed in
`etc/openwebrx/sdrs_seed.py` by centering the profile on 100.1 MHz
(the same frequency already validated as a real, working receive
point in §3b.3) rather than picking an arbitrary new center - both
fields now agree. The `noaa-weather` profile was correctly configured
from the start (75 kHz offset, well within range) and never warned.

**Real reception test through OpenWebRX+ itself - not merely
`rtl_test`/`rtl_sdr`**: no ready-made WebSocket client library exists
anywhere on this system (checked directly: neither system Python nor
the OpenWebRX+ venv has `websockets`/`aiohttp` installed - OpenWebRX+
implements its own raw protocol). A minimal stdlib-only (`socket`,
`base64`, `struct`) WebSocket client was written against the actual
installed protocol handler source
(`owrx/connection.py`'s `HandshakeMessageHandler`/
`OpenWebRxReceiverClient`, not guessed from the frontend JS alone),
simulating exactly what a real browser tab does: WebSocket handshake,
`SERVER DE CLIENT client=... type=receiver`, then a `dspcontrol start`
message. **CONFIRMED, both directly (client-side) and independently
via the server's own journal (not just inferred from one side)**:

- The server automatically selected the configured RTL-SDR source and
  its first profile (`sdr_id: rtlsdr`, `profile_id: noaa-weather`) -
  confirming the seeded configuration is genuinely recognized, not
  just present in a file.
- The journal showed OpenWebRX+ launch
  `rtl_connector -g 8.7 -P 0 -s 2048000 -f 162475000 -p ... -c ...` -
  the exact configured gain, sample rate, and frequency from the
  seeded profile, not defaults.
- `rtl_connector`'s own output showed it finding and opening this
  exact unit (`Realtek, RTL2838UHIDIR, SN: 00000001`), detaching the
  kernel driver, and identifying the Rafael Micro R820T tuner - a
  third independent confirmation of the tuner identity (kernel probe
  in §3a, `rtl_test`/`rtl_sdr` in §3b, now the full OpenWebRX+
  integration stack), followed by "Allocating 2 zero-copy buffers" -
  real USB IQ streaming beginning.
- On a longer (20-second) connection, the client received **219
  binary WebSocket frames totaling 216,910 bytes** (FFT/waterfall/
  audio data), plus a continuous stream of live `smeter` readings
  (small, roughly-consistent fractional values, consistent with a
  quiet/no-strong-signal noise floor at this untuned frequency, not a
  stuck/fake value), a live `temperature` reading (43°C, closely
  matching a direct `vcgencmd measure_temp` check taken around the
  same time), and a live `cpuusage` self-report from OpenWebRX+ itself.
- On disconnect, the journal showed a clean teardown:
  `received signal: 15` then `Reattached kernel driver` - the same
  graceful detach/reattach cycle already confirmed reliable in §3b,
  now happening automatically through the full application stack with
  no operator action.

**`/radio/` nginx reverse proxy - CONFIRMED working end-to-end**: the
identical test, repeated through `http://piratebox/radio/ws/` (port
80, `Host: piratebox`) instead of directly against `127.0.0.1:8073`,
produced the same result - 213 binary frames, 211,290 bytes, full
protocol handshake, real hardware activation. WebSocket upgrade
headers, path stripping (`proxy_pass`'s trailing slash), and the long
proxy timeouts are all confirmed correct in the actual deployed
config, not just reasoned about from source (§13.1).

**Pi 3B+ performance under one real, actively-streaming client**
(sampled every 2 seconds throughout a 20-second connection):

| | Idle (pre-test) | Under one active client |
|---|---|---|
| `openwebrx` process CPU | - | ~10-14% (one core) |
| `rtl_connector` process CPU | not running | ~11-27% (briefly 27% at stream startup, settling to ~12-13%) |
| 1-minute load average | 0.99 | rose to ~1.63-1.68 |
| `openwebrx` RSS | - | ~6.5-7% of this Pi's 905MB (roughly 60-65MB) |
| `throttled` | `0x50005` | **unchanged at every single sample** |
| Temperature | 42.9°C | 42.9-43°C (unchanged) |

Combined CPU for one client is roughly a quarter of one core on this
4-core Pi 3B+ - real, measured headroom remains for the configured
`max_clients: 2` and for the rest of PirateBox's own normal load, but
this is one client with plain NFM/analog demodulation and no digital-
voice decoding - not yet stress-tested at 2 simultaneous clients or
with a real browser's own JS/rendering overhead added on top (that
overhead lives client-side, not on the Pi, but a genuine end-to-end
UX judgment still needs an actual browser - see the closeout).

**Zero USB/kernel errors, zero ALFA disconnects, zero re-enumerations,
`pb-ap`/hostapd/dnsmasq/nginx all confirmed healthy before, during, and
after every test in this section** - the only kernel-level message
logged during the entire verification round was the expected, benign
`dvb_usb_v2: ... successfully deinitialized and disconnected` line
that accompanies every clean kernel-driver detach (§3b.1), confirmed
via a full `journalctl -k` sweep of the test window, not merely
absence-of-complaint.

### 13.6 Human browser test, and adding broad manual retuning (2026-09-05)

**Human confirmation, the gate §13.5 stopped at**: the operator opened
`http://piratebox/radio/` in a real browser. The waterfall/audio UI
loaded; NOAA Weather Radio and FM Broadcast both appeared as selectable
profiles; a real FM station was audible in the FM Broadcast window with
working browser audio; PirateBox itself remained usable in another tab
while the receiver was open. **Real, human-confirmed, end-to-end
reception through OpenWebRX+ and the `/radio/` proxy - not just
protocol-level evidence.**

**UX gap found**: each profile only let the operator tune within its
own fixed ~2 MHz window (NOAA ~161.5-163.5 MHz, FM ~97-99 MHz), with no
way to move that window - confirmed not to be an OpenWebRX+ limitation
but a config default (`allow_center_freq_changes` defaults to `False`
in `owrx/config/defaults.py`, confirmed by reading the actual installed
source) that this project's own seed file had never set.

**A real discovery that changed how this gets fixed**: `settings.json`
(`/var/lib/openwebrx/`'s "dynamic" config layer, written by OpenWebRX+'s
own `/settings` admin web UI, which takes priority over the classic
`config_webrx.py` file per `owrx/config/__init__.py`'s own
`PropertyStack` layer ordering) **does not exist on this system at
all** - confirmed by direct inspection, not assumed. This means the
classic `/etc/openwebrx/config_webrx.py` file is not a one-time seed
that stops mattering after `config migrate` runs, as this document
previously assumed (matching OpenWebRX+'s own "not intended to be
edited manually past migration" framing) - `owrx/config/classic.py`
actually **executes that file fresh on every service start**, and
since nothing is masking it, it is the *actual live source of truth*
for every setting in it, right now. (`config migrate`'s own
`store()` call, confirmed by reading `owrx/config/commands.py`, did
not end up producing a `settings.json` on this install for reasons not
further investigated - not essential to this fix, and not needed for
it to work correctly.) This matters because it changes the *correct*
way to apply an ongoing config change: not by re-running `config
migrate` a second time (which the `PropertyStack` layering would make
a silent no-op for any key the - nonexistent - dynamic layer already
had), but by editing the classic file directly and restarting the
service - genuinely effective on this system, not a workaround, for as
long as no admin account/`/settings` edit exists to start masking it.

**Fix implemented**:

- `allow_center_freq_changes = True` added to
  `etc/openwebrx/sdrs_seed.py` - a general, visitor-facing setting
  (confirmed via source: it sits alongside `allow_audio_recording`/
  `allow_chat`, not gated behind OpenWebRX+'s own admin `/settings`
  auth) that lets any connected client drag/retune the center
  frequency, no login required - matching the instruction not to
  require admin interaction for ordinary visitor tuning.
- A third profile, **"General SDR (Wide Tuning)"**, added to the same
  `rtlsdr` device - starting at the same already-validated 100.1 MHz
  FM signal (a known-good starting point, not an untested frequency),
  same conservative 2.048 Msps sample rate and 8.7 dB manual gain as
  the other two profiles. With `allow_center_freq_changes` enabled,
  a visitor can retune from this (or any) profile's starting point to
  anywhere the R820T tuner will actually lock onto.
- **No hard frequency min/max is enforced by OpenWebRX+ itself**,
  confirmed by reading the actual installed `owrx/source/rtl_sdr.py`:
  it declares a valid *sample-rate* range (`Range(250000, 3200000)`,
  matching librtlsdr's own real limits) but no frequency-range field
  at all for a plain connector-type device - a client can request any
  numeric center frequency, forwarded directly to `rtl_connector`/the
  tuner. The real, practical ceiling is the R820T/R820T2 family's own
  PLL lock range - community-documented as roughly 24 MHz-1766 MHz,
  **not re-measured across that whole span by this project** (this
  unit has been directly confirmed working at exactly three points:
  27.185 MHz, 100.1 MHz, and 162.475 MHz - §3b.3, §13.5). Tuning
  outside the real range doesn't damage anything - the tuner simply
  fails to produce a usable signal - documented honestly as an
  unenforced, community-sourced practical boundary, not a verified or
  OpenWebRX+-enforced hard limit.
- **Each profile/session still only ever shows one ~2.048 MHz-wide
  slice of spectrum at a time, centered on the current tuned
  frequency - retuning moves that slice, it does not widen it or show
  multiple bands simultaneously.** Recorded explicitly per instruction,
  so this is never misrepresented as full-spectrum simultaneous
  coverage.
- `tools/update_openwebrx_config.sh` added: a small, dedicated,
  reusable script for applying a changed `sdrs_seed.py` to an
  already-installed system (copy + restart) - distinct from
  `tools/install_openwebrx.sh`'s own first-time-only seeding guard, and
  the correct tool for this and any future config-file-driven change
  for as long as no admin account/`/settings` edit exists to complicate
  the picture (see that script's own header for the exact caveat).

**Not yet applied to the live system as of this commit**: this fix
requires root (editing `/etc/openwebrx/config_webrx.py` and restarting
the service) - `tools/update_openwebrx_config.sh` is written and
tested for syntax/logic but has not yet been run by the operator. The
live instance still has the pre-fix configuration (fixed NOAA/FM
windows only, no General SDR profile, `allow_center_freq_changes`
still `False`) until that happens. Retuning verification (confirming
the backend genuinely follows arbitrary center-frequency changes
across multiple very different bands, not just serving the profile's
own fixed starting point) is planned immediately after, using the
same protocol-level test method as §13.5 - see the operator gate this
round stops at.

---
