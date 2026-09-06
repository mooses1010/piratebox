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

> **CORRECTION added 2026-09-05 (later the same day, §13.8)**: the
> "confirmed" multi-band retuning claim in this section is a **false
> positive**. Every `setfrequency` call in the test below omitted
> OpenWebRX+'s own required `magic_key` parameter (default
> `"memagic"`, never set by this project's config until §13.8) - the
> retune commands were silently dropped server-side the entire time,
> and the receiver never actually left its starting frequency. The
> frame-count differences reported below reflect normal variation at
> one unchanging frequency, not genuine reception at three different
> bands. Left in place, uncorrected in substance, for an honest record
> of how the mistake happened - see §13.8 for the real root cause and
> a corrected re-verification.

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

**Applied and verified (2026-09-05)**: the operator ran
`tools/update_openwebrx_config.sh`; `status.json` confirmed all three
profiles live with the corrected FM frequency
(`center_freq: 100100000`), and a protocol-level test (the same
stdlib WebSocket client as §13.5, through the `/radio/` proxy)
confirmed `"allow_center_freq_changes": true` in the server's own
config push.

**Retuning across genuinely different bands - confirmed, with one
real timing lesson learned along the way**: a first attempt sent
`setfrequency` commands every ~7 seconds starting almost immediately
after connecting, and the CB/11m target (27.185 MHz) showed **zero**
binary frames - investigated rather than written off as a retuning
failure. The journal showed only one `rtl_connector` launch for the
whole test, at 162.475 MHz - the *last* frequency requested, not the
first. Reading `owrx/source/connector.py`'s `onPropertyChange()`
explained why: a center-frequency change is sent as a **live control-
socket message to the already-running `rtl_connector` process**
(`"center_freq:<value>\n"`), never a process relaunch - and this
particular source has enough startup latency that all three rapid
requests landed on the property before the process had even started,
so it launched already reflecting the final accumulated value. Not a
functional bug - a test-pacing artifact, confirmed by re-running with
each retune spaced 10+ seconds apart and an initial 16-second warm-up:
**CB/11m (27.185 MHz): 365 binary frames, FM Broadcast (100.1 MHz):
252 frames, NOAA Weather (162.475 MHz): 97 frames - all three
genuinely different, widely-separated bands (27 MHz apart to 162 MHz)
streamed live, real data while tuned, confirmed both by the client
receiving it and by `owrx`'s own source code showing exactly how the
retune command reaches the hardware-facing process.**

> **This entire paragraph is the false positive corrected in §13.8.**
> None of these `setfrequency` calls included OpenWebRX+'s required
> `magic_key` - every one was silently dropped server-side (confirmed
> later: no exception, no error message, no config push, by design of
> `owrx/connection.py`'s `if magic == "" or key == magic:` gate). The
> receiver never left its starting frequency for the whole test. Even
> the "explanation" above (rapid retunes landing before process
> startup) was itself a plausible-sounding but wrong theory, arrived
> at by trusting a real-looking log/frame-count pattern without the
> one check that would have caught it: a live "config" push actually
> showing the new `center_freq`. §13.8 re-ran this exact test with the
> key included and got real, distinct config pushes at all three
> targets - see there for what actually happened.

**Post-verification health, unchanged from every prior round**:
`pb-ap`/hostapd/`openwebrx` all `NRestarts=0`/`active`/`running`,
`throttled` still the same pre-existing `0x50005`, temperature
unchanged, zero failed units, and the only kernel-level message during
the entire retuning test was the same benign, expected
`dvb_usb_v2: ... successfully deinitialized and disconnected` line
seen in every previous round.

### 13.7 Second human browser test found a UI/integration gap - fixed PirateBox-side (2026-09-05)

**Report**: after §13.6's protocol-level retuning proof, the operator
opened `http://piratebox/radio/` (the stock OpenWebRX+ page itself, not
a test client) and was **still stuck inside whatever ~2 MHz window the
active profile started at** - "General SDR (Wide Tuning)" gave no
obvious way to move the receiver center broadly. Explicit instruction
was not to assume the backend proof settled this: it doesn't, because
the backend and the frontend are different things.

**Investigated, not assumed**: read the actual shipped frontend
JavaScript (`/opt/openwebrx/htdocs/*.js` and `htdocs/compiled/*.js`) -
grepped for `allow_center_freq_changes`, `centerFreqChanges`,
`setfrequency`, and any URL-hash/query-based frequency or profile
scheme. **Found none.** The stock OpenWebRX+ frontend has zero widgets
that ever send a `setfrequency` message, regardless of the
`allow_center_freq_changes` server setting - that setting only gates
whether the *server* honors such a message if one arrives, not whether
the shipped UI offers a way to send one. This is a genuine gap in the
upstream frontend, not a misconfiguration or a hidden control on this
project's part.

**Also checked and ruled out**: no URL-query/hash-based frequency or
profile selection scheme exists in `openwebrx.js` either (only the
already-known WebSocket-URL-construction code touches `location.*`) -
so there was no undocumented "cleaner" entry point being missed.

**Decision**: build a small PirateBox-side control rather than patch
OpenWebRX+'s own installed files (which a future clean reinstall would
silently discard, and which risks conflicting with upstream's own
future frontend work). The already-validated WebSocket protocol
(§13.5/§13.6) is stable, documented, public API surface from
OpenWebRX+'s own perspective (the same handshake and message shapes
its own frontend uses) - a separate client speaking that same protocol
is not a hack, it's just another client.

**Implementation**: `var/www/html/public/utility/radio/live.php`, a
new page linked from the existing static Radio Reference page
(`/utility/radio/`). Note `/radio/` itself is reserved end-to-end by
the nginx reverse proxy (`location ^~ /radio/` in
`etc/nginx/openwebrx-location.conf` forwards the entire prefix to
OpenWebRX+ on `127.0.0.1:8073`), so the new page could not live under
`/radio/` and was placed under the existing `/utility/radio/` path
instead.

- A server-side TCP reachability probe (`fsockopen` against
  `127.0.0.1:8073`, 0.75s timeout) decides whether to render the live
  tuner UI at all, or a plain "not currently available" message -
  matching this project's existing optional-capability degrade-not-
  disable pattern (`docs/ARCHITECTURE.md` section 2). Verified by
  direct PHP CLI execution against the real running service: the
  reachable branch renders correctly end-to-end.
- Three curated presets (only the frequencies this project has
  actually confirmed receiving: 162.475/100.1/27.185 MHz) plus a
  manual MHz-entry form, both range-bounded 24-1766 MHz (the R820T
  family's documented practical range, explicitly labeled as not
  exhaustively re-verified across its whole span).
- On tap/submit, browser JS opens its own `WebSocket` directly to
  `/radio/ws/` (the same path OpenWebRX+'s own frontend uses) and
  replicates the exact validated sequence: the
  `"SERVER DE CLIENT client=... type=receiver"` handshake string, then
  `{"type":"selectprofile","params":{"profile":"rtlsdr|general-sdr"}}`
  (confirmed against `owrx/connection.py`'s actual
  `profile.split("|")` handling - `rtlsdr` is the configured SDR
  device id, `general-sdr` the profile id from
  `etc/openwebrx/sdrs_seed.py`), then
  `{"type":"setfrequency","params":{"frequency":<hz>}}` (confirmed
  against the same source: gated only by `allow_center_freq_changes`
  and `freq >= 0`, no auth check at all). Deliberately does **not**
  send `"dspcontrol start"` - that would spin up its own per-client
  audio/waterfall demodulation chain, which this one-shot control
  widget has no use for; `selectprofile`+`setfrequency` alone retune
  the shared underlying source, which every other connected client
  (including the embedded iframe) sees.
- After a successful retune, the page reloads the embedded `/radio/`
  iframe (cache-busted) so its own displayed frequency/waterfall
  catches up - an already-open OpenWebRX+ client doesn't otherwise know
  to refresh its own display when a sibling client retunes the shared
  source.
- Graceful failure throughout: a 6-second overall timeout, `onerror`/
  `onclose` handlers, and a listener for `sdr_error`/
  `demodulator_error` server messages all produce a plain status
  message rather than a silent hang or a broken page.
- No admin login, no manual config editing, no new backend endpoint,
  no arbitrary port URL - the whole path rides the same visitor-facing
  `allow_center_freq_changes` setting and the same `/radio/ws/` nginx
  route already in production use.

**Verification performed**: `php -l` clean on both the new file and
the edited `index.php`. The full page was rendered via direct PHP CLI
execution against the actual, currently-running live OpenWebRX+
service and visually confirmed correct (reachability branch, all three
presets, manual form, status line, iframe, and the full inline script
all present and well-formed). The embedded JavaScript's brace/paren/
bracket balance was checked programmatically (36/36, 87/87, 1/1) and
the whole script manually re-read end to end; no JavaScript engine
(`node`/`nodejs`) exists on this system to run a real syntax check,
which is recorded here rather than silently worked around. The
`selectprofile` and `setfrequency` message shapes, and the `rtlsdr`/
`general-sdr` id strings, were each independently cross-checked
against the actual installed `owrx/connection.py` source and
`etc/openwebrx/sdrs_seed.py` (not assumed from memory of §13.5/13.6).
**Not yet done**: a genuine human click-through in a real browser -
this is the explicit stopping gate for this round, since no tool
available here can execute real browser JavaScript.

### 13.8 Third human browser test: the receiver was still pinned - the real root cause was a missing `magic_key`, not the iframe reload (2026-09-05)

**Report**: `live.php` looked correct and submitted without error, but
the embedded receiver stayed pinned at ~100.1 MHz no matter what
frequency was entered, and the `< >` arrows beside the frequency
display didn't move it either. Explicit instruction: investigate the
real live message sequence, don't re-prove the backend, and treat the
iframe-reload-undoes-the-retune theory as a hypothesis to verify, not
an assumption.

**What the `< >` arrows actually do (verified via source, not
assumed)**: `htdocs/openwebrx.js`'s `tuneBySteps()` calls
`UI.setFrequency()` (`htdocs/lib/UI.js`), which computes
`demod.set_offset_frequency(freq - delta - center_freq)` - purely a
**demodulator offset within the already-tuned window**. It never sends
a `setfrequency` protocol message. The user's own hypothesis was
correct: these are local tuning-within-the-passband controls, not SDR
center-retune controls, and were never going to move the display to a
different band regardless of anything else here.

**Investigating the iframe-reload hypothesis - built a direct
diagnostic instead of re-trusting frame counts**: three raw-socket
Python clients were used side by side against the real running
service (not a new library, not the frontend - the same protocol
already reverse-engineered in §13.5): a persistent "iframe-sim" client
with `dspcontrol` started, a "control-socket-sim" client replicating
`live.php`'s exact `selectprofile` → wait → `setfrequency` → close
sequence, and a "fresh-reload-sim" client opened after the sequence to
read a brand-new connection's initial config snapshot directly (a
read of current shared state, independent of whether change-push
notifications work at all). Full raw message logs were captured, not
just filtered summaries.

**First finding: the live-push mechanism itself works, and profile
switching demonstrably succeeds.** The control-socket's `selectprofile`
call produced an immediate, correct delta `"config"` push to itself
(`{'profile_id': 'general-sdr', 'sdr_id': 'rtlsdr'}`) - proof the
reactive `PropertyStack` → `configProps` → `sendConfig` chain
(`owrx/connection.py`) is not broken, and proof `activateProfile()`
genuinely ran. This directly falsified the original iframe-reload
hypothesis as the primary cause: if profile switching visibly works
end-to-end on a plain persistent connection with no reload involved,
a working `setfrequency` should show the same live push. It did not -
not once, across several minutes of a properly-paced (16 s warm-up,
matching §13.6's own already-established pacing lesson), single-client
test with no `max_clients` contention. A brand-new "fresh reload"
connection's own initial config snapshot (a direct read, not a push)
confirmed the same thing from a completely different angle:
`center_freq` stayed `100100000` no matter how long after the
`setfrequency` call it was read. The underlying shared property was
never actually changing - not a notification problem, a **write**
problem.

**Root cause, found by re-reading `owrx/connection.py`'s exact
`setfrequency` handler line by line instead of trusting the earlier
summary of it**:

```python
elif message["type"] == "setfrequency":
    if "params" in message and "frequency" in message["params"]:
        params = message["params"]
        freq   = params["frequency"]
        if freq >= 0 and self.stack["allow_center_freq_changes"]:
            magic = self.stack["magic_key"]
            key   = params["key"] if "key" in params else None
            if magic == "" or key == magic:
                self.sdr.setCenterFreq(freq)
```

`self.sdr.setCenterFreq(freq)` - the only line that actually retunes
anything - is gated on `magic == "" or key == magic`. OpenWebRX+'s own
default (`owrx/config/defaults.py`) is `magic_key = "memagic"`, **not**
an empty string, and this project's `etc/openwebrx/sdrs_seed.py` never
set it (confirmed via `git log -p` across the whole file history: no
commit ever mentions `magic_key`). `live.php`'s JS never sent a `"key"`
param, by design - the entire point was a no-login, no-secret visitor
control. Every single `setfrequency` message it ever sent was silently
dropped: `magic ("memagic") == ""` is false, `key (None) == magic` is
false, so the `if` body - the only place `setCenterFreq()` is called -
never ran. No exception (there's nothing to throw), no error sent to
the client, no config push (nothing changed to push). This is a
**strictly stricter gate than profile selection**: `setProfile()` only
checks the magic key when the target profile is `isLocked()` (which
needs an explicit `key_locked: true`, default `False`, never set by
this project) - so `selectprofile` calls succeeded unconditionally,
which is exactly why that half of `live.php`'s sequence always looked
fine while the other half silently did nothing.

**Confirmed empirically, not just by reading source**: the identical
`setfrequency` call, unchanged except for adding
`"key": "memagic"` to its params, produced an *instant* live config
push (`{'center_freq': 27185000, 'start_offset_freq': 72915000}`) on a
connection that had been sitting at 100.1 MHz for over a minute with
no other change. Same server, same running process, same client - the
only variable was the key.

**This also means §13.6's own "confirmed" multi-band retuning result
was a false positive**, from this exact bug (see the correction added
at the top of §13.6 and inline at the specific paragraph). That test's
`setfrequency` calls also never included a key; the receiver never
left its starting frequency; the reported 365/252/97 frame-count
"confirmation" was normal streaming variation at one unchanging
frequency, misread as evidence of three different ones. Re-ran that
exact test, changed only to add `"key": "memagic"` to every
`setfrequency` call: live `"config"` pushes now show `center_freq`
genuinely landing on `27185000`, then `100100000`, then `162475000` in
sequence, each arriving within 0.2 s of its retune command, with
binary frames continuing to stream throughout (198/200/245 frames) -
this is what the earlier round should have shown and didn't, because
it was never actually retuning at all.

**Fix, in `etc/openwebrx/sdrs_seed.py` (not a backend redesign - the
same category of general, non-admin-gated setting as
`allow_center_freq_changes`, sitting right next to it)**:
`magic_key = ""`. This removes the gate entirely rather than teaching
`live.php` to send the literal string `"memagic"` - hard-coding
OpenWebRX+'s own stock default into visible client JS would "work" but
is fragile in exactly the way this whole investigation was expensive:
if a future admin ever sets a real `magic_key` (e.g. to actually
restrict retuning on a more exposed deployment), `live.php` would
silently break again with this identical symptom and no error,
because the failure mode is silence by design. An empty `magic_key`
server-side is the only way to make "no visitor secret" a property of
the *configuration* rather than a hostage to a client-side literal.
`live.php` itself needed **no code change** - it was already correct;
the missing piece was entirely a config value, not app logic. Also
raised `max_clients` from 2 to 4 in the same file: `live.php`'s design
inherently uses two concurrent connections (the embedded iframe plus
its own short control socket), which left zero headroom against the
previous limit - not the cause of the pinned-frequency bug (the
diagnostic tests above stayed at or under 2 clients throughout and
still failed identically), but a real, separate fragility worth
closing in the same pass.

**Deployment status**: this fix lives only in the repo as of this
writing. Applying it to the live system needs
`tools/update_openwebrx_config.sh` run with `sudo` - a password-gated
command this session has no standing grant for (only
`piratebox_deploy.sh` and `set_piratebox_mode.sh` are `NOPASSWD`, per
`sudo -l`). The operator needs to run it, then a real human
browser click-through against `/utility/radio/live.php` is the actual
close of this task - the two explicit stopping conditions from this
round's own instructions (sudo action, human browser confirmation)
both apply here at once.

**Post-verification health**: `hostapd`/`openwebrx`/`dnsmasq`/`nginx`
all `NRestarts=0`/`active`/`running`, `throttled` unchanged at
`0x50005`, zero failed units, throughout every diagnostic client
connect/disconnect cycle in this section (including one incidental,
harmless `TooManyClientsException` hit during an early, messier
multi-client diagnostic draft that used more than the then-configured
`max_clients=2` slots at once - itself part of what motivated raising
that limit above).

### 13.9 Fourth human browser test: broad retuning confirmed working - the stock `<`/`>` buttons still didn't, for an unrelated reason (2026-09-05)

**Report**: with the `magic_key` fix from §13.8 applied, General SDR
wide tuning now works correctly in the real browser - entering a
frequency moves the receiver to the correct broad band and the visible
spectrum follows it. The one remaining issue: OpenWebRX+'s own stock
`<`/`>` buttons next to the frequency readout still didn't appear to
do anything. Scoped narrowly per instruction: investigate this as a
separate frontend/UX issue, don't touch the now-working retuning.

**What these buttons are, confirmed via source**: `htdocs/index.html`
wires them to `tuneBySteps(-1)`/`tuneBySteps(1)`
(`htdocs/openwebrx.js`), which calls `UI.setFrequency()`
(`htdocs/lib/UI.js`) → `demod.set_offset_frequency()`
(`htdocs/lib/Demodulator.js`) - exactly the demodulator-offset-within-
window mechanism identified in §13.7, not an SDR center-retune. This
was re-confirmed, not re-assumed, before looking further.

**Investigated whether the offset change happens but isn't visible,
whether iframe/session state blocks it, or whether it's simply not
useful - by tracing the exact numbers, not guessing**:
`tuneBySteps()`'s math divides the current frequency by a global
`tuning_step` variable, adds/subtracts one step, and multiplies back:
`f = (Math.floor(f / tuning_step) + steps) * tuning_step`. That
variable starts at a hardcoded `var tuning_step_default = 1;` (1 Hz)
in `openwebrx.js`, and is only ever overwritten by
`tuning_step_default = config['tuning_step'];` - i.e., only if a
`"tuning_step"` key is present in a `"config"` push at all.
`Demodulator.prototype.set_offset_frequency()` also independently
bounds-checks against `±bandwidth/2` (our profiles' own
`samp_rate`/2, ~1.024 MHz) before doing anything - ruled out as the
blocker here since 1 Hz is trivially within that range regardless.

**Confirmed empirically against the real running service (not just by
reading source) that `tuning_step` was never actually present**: a
protocol-level client connected, requested `dspcontrol start`, and
logged every key present in every `"config"` push received - 28 real
keys came through (`center_freq`, `samp_rate`, `start_freq`,
`profile_id`, `ppm`-adjacent settings, etc.), and `"tuning_step"` was
not one of them, on the actual `general-sdr` profile as configured
right now. Cross-checked against `etc/openwebrx/sdrs_seed.py` and the
live `/etc/openwebrx/config_webrx.py`: neither has ever set a
`tuning_step` key anywhere (`grep` found zero matches in either file).
This means the frontend's own hardcoded fallback of 1 Hz was silently
in effect the entire time: each `<`/`>` click was moving the
demodulator's offset by exactly one Hertz - a change with no visible
effect on any frequency readout and no audible effect on demodulated
audio, indistinguishable from "the buttons do nothing." **Answers all
three of the framed questions at once**: the buttons genuinely were
changing `set_offset_frequency()` (not broken, not blocked by
iframe/session state), the effect just wasn't visible because it was
1/5000th the size a human could ever notice - and once fixed, they are
a real, useful (if narrow-scope) control, not something to hide.

**Fix, in `etc/openwebrx/sdrs_seed.py` (same category as the
`magic_key`/`max_clients` fixes in §13.8 - a plain missing config
value, not a backend redesign and not a patch to any upstream-owned
file)**: added `"tuning_step": 5000` (5 kHz) to the `rtlsdr` device
dict, alongside the already-present `ppm`/`rf_gain` - device-wide like
those two, since this schema has no per-profile override for it. 5 kHz
matches the single most common per-mode default already present in
OpenWebRX+'s own `owrx/config/defaults.py` "modes" list, stays well
inside even the narrowest profile here (NOAA/CB's NFM channels, whose
usable passband is far wider than one 5 kHz step), and is large enough
to produce a real, noticeable change in both the frequency display and
demodulated audio - unlike the 1 Hz it silently defaulted to before.

**Verified the fix mechanism directly, without touching the live
service or needing sudo**: rather than only reasoning about it,
imported the actual installed `owrx.property` classes
(`/opt/openwebrx/venv`) and replicated `SdrSource.__init__`'s own
exact layering (mutable `center_freq` layer, active-profile layer,
device-props layer) with a `tuning_step: 5000` device property added
the same way `ppm`/`rf_gain` already are, then ran it through the
literal `sdr_config_keys` filter list from `owrx/connection.py`. The
resulting filtered view correctly includes `tuning_step: 5000`,
through the identical code path that already, correctly, delivers
`center_freq`/`samp_rate`/`start_freq` to real clients today - proof
against the real classes and the real filter list, not a guess that
the same mechanism "should" extend to one more key.

**Also added, in `live.php`**: a short caption above the embedded
receiver noting that its own `<`/`>` buttons only nudge a few kHz
within the currently shown slice and pointing back at the presets/
frequency box above for broad moves - chosen over hiding or disabling
the buttons since, once the `tuning_step` fix lands, they are a
genuinely working, useful fine-tuning control; a visitor who has just
used the broad-tuning controls above them benefits from knowing the
two controls do different things, not from one of them being taken
away.

**Deployment status**: like §13.8's fix, this lives only in the repo
as of this writing - applying it needs the same operator
`sudo tools/update_openwebrx_config.sh` step (this session has no
standing grant for it), followed by a human browser re-check that a
`<`/`>` click now visibly moves the frequency readout by 5 kHz and
audibly changes the demodulated signal, without disturbing the
already-confirmed-working broad retuning above it.

### 13.10 Fifth human browser test independently confirmed §13.9's diagnosis, then reframed the actual ask: PirateBox-side "Move Spectrum" controls, distinct from OpenWebRX+'s own tuning (2026-09-06)

**Report**: before the `tuning_step` fix from §13.9 was even deployed
live, the operator found OpenWebRX+'s own **"Tuning step" dropdown** in
the receiver UI - still showing its default 1 Hz - and manually
changed it to 50 kHz. The `<`/`>` buttons immediately started visibly
moving the small yellow tuned-frequency/demodulator marker. This is
independent, in-browser confirmation of §13.9's root-cause diagnosis
(the buttons were never broken or blocked - they were just configured
with an imperceptible step size) via a path this project's own fix
hadn't even reached the live system through yet.

That resolved the original `<`/`>` question entirely, but surfaced the
real gap it had been standing in for: those buttons - and the
"Tuning step" dropdown - only ever move the demodulator **within** the
current ~2.048 MHz sampled window (§13.7/§13.9's own finding). What was
actually wanted is a convenient way to move the window **itself** -
the RTL-SDR's actual hardware center frequency - across its full
tunable range, while still being honest that only one ~2 MHz slice is
ever live at a time.

**Design chosen - "Move Spectrum" controls, kept separate from
OpenWebRX+'s own tuning controls, not merged with them**: added to
`live.php` (no upstream OpenWebRX+ file touched, no `/etc/openwebrx/`
config change needed - this is 100% the same PirateBox-side control-
socket mechanism as the existing presets/manual-entry box from
§13.6/§13.7, reusing its `tuneTo()` function unchanged):

- **"« Previous Spectrum" / "Next Spectrum »" buttons.** Each computes
  `currentCenterHz ± SPECTRUM_SHIFT_HZ` (client-side JS tracks the last
  frequency this page itself tuned to, updated on every successful
  `tuneTo()` - presets, manual entry, these buttons, and the range bar
  below all feed the same tracker), clamps it to the receiver's
  24-1766 MHz practical range, and calls the exact same `tuneTo()` used
  by the presets/manual box - a real `setfrequency` protocol message,
  not a demodulator offset. `SPECTRUM_SHIFT_HZ = 1,500,000` (1.5 MHz),
  deliberately smaller than the full `SPECTRUM_SAMP_RATE_HZ = 2,048,000`
  (2.048 MHz, matching `general-sdr`'s own `samp_rate`) - a full-width
  jump could place a signal sitting at one edge of the old window
  exactly at the far edge of the new one, an easy way to skip past it
  entirely. 1.5 MHz leaves ~548 kHz (~27%) of overlap between
  consecutive windows instead.
- **A clickable broad-range navigator (implemented this round, not
  deferred - judged straightforward and low-risk: pure client-side
  math and CSS, no new protocol messages, reuses `tuneTo()` again).** A
  horizontal bar spanning the full 24-1766 MHz range on a **logarithmic**
  scale (a linear scale would squeeze the low end - where two of the
  three curated presets live - into an unreadable sliver next to the
  1+ GHz high end), with round-number tick labels (30/50/100/200/500/
  1000/1700 MHz), a highlighted band showing the current ~2 MHz sampled
  window's actual position and width at that point on the log scale,
  and a text readout of its approximate edges. Clicking anywhere on the
  bar tunes there. The highlighted band is deliberately drawn as a thin
  sliver of the whole bar (confirmed via the same log-scale math: e.g.
  ~0.5% of the bar's width at FM broadcast, ~0.03% near the top of the
  range before a minimum-width floor keeps it visibly clickable/visible)
  - the design brief's own instruction not to misrepresent a live
  wideband view is satisfied by the visualization itself, not just by
  copy: the bar makes plain that the sampled window is a tiny fraction
  of the whole range, never implying the whole bar is live at once.
- **A future scan/stitch mode (sequential-chunk capture to build a
  non-live wideband activity overview) was left as a documented future
  enhancement, not built this round**, per the instruction to keep
  scope to what's straightforward/robust for now. It would need genuine
  design work this round didn't do: how long each chunk should dwell,
  how to represent "sampled 6 hours ago" vs. "live" without misleading
  a visitor, and whether OpenWebRX+'s existing waterfall/FFT pipeline
  can be driven headlessly for this or whether it needs a separate
  capture path entirely.

**Made the distinction between the two kinds of control obvious to a
normal visitor, not just documented in code comments**: the new
Previous/Next Spectrum buttons sit inside their own bordered, accent-
colored block, visually distinct from the plain "Tune" button above
them and from OpenWebRX+'s own on-screen controls below. The hint
paragraph under the range bar was rewritten to name both controls
explicitly: OpenWebRX+'s own `<`/`>` buttons and "Tuning step" dropdown
move "the yellow *demodulator* marker... within the currently shown
~2 MHz slice"; the presets, frequency box, Previous/Next Spectrum
buttons, and range bar "move the receiver's sampled window to a
different part of the spectrum."

**No regression to the now-working broad retuning**: the existing
presets/manual-entry `tuneTo()` function itself was not modified except
to also update the new `currentCenterHz` tracker on success (needed so
the new controls know where to shift from/where the range-bar's window
indicator currently sits) - the WebSocket handshake/`selectprofile`/
`setfrequency` sequence, timing, and error handling are unchanged.
`tools/test_hostapd_recovery_config.py` (13/13) and
`tools/test_silly_mode.py` (103/103) still pass, both unaffected by a
`var/www/html/` frontend change.

**Deployment status**: unlike §13.8/§13.9, this round's change is
entirely inside `var/www/html/` (`live.php`'s HTML/CSS/JS only) - no
`/etc/openwebrx/` config file involved, so it needs only the normal
`sudo piratebox_deploy.sh` step this session already has a standing
grant for, not the operator's separate `update_openwebrx_config.sh`
step. See the deploy log for whether that was actually run this round.

**Limitations discovered, not previously documented**: (1) this page
has no way to read OpenWebRX+'s own currently-active center frequency
back out of the shared receiver - `currentCenterHz` is a client-side
guess seeded from this project's own "known good" anchor frequency
(100.1 MHz) and only becomes accurate once this page itself performs
the first tune; if a different client (e.g. someone using `/radio/`
directly) has since moved the shared receiver elsewhere, the
Previous/Next buttons' *first* click on this page will shift from the
stale guess, not the receiver's true current position, self-correcting
from the second click onward. (2) OpenWebRX+ exposes no live query for
"what's the receiver's frequency right now" over this lightweight
control-socket path short of joining a full demodulating session
(`dspcontrol start`), which this page deliberately avoids per
§13.6/§13.7's own reasoning (a one-shot control widget has no use for
its own audio/waterfall chain).

---

## 14. Deep investigation: what our actual installed OpenWebRX+ already offers toward a Twente-WebSDR-like "explorable spectrum" experience (2026-09-06, read-only research round)

**Trigger**: after §13's broad-retuning UX was human-validated and working, the
operator asked for an investigation - explicitly research/design only, no
code or config changes - into whether the OpenWebRX+ version we actually
installed already contains marker/annotation/navigation infrastructure we
are simply not populating, inspired by (not copying) the University of
Twente WebSDR's explorable-spectrum UX. **Nothing in this section was
implemented this round.** No files were installed, no `/etc/` file was
touched, no service was restarted, no config value was changed. This is a
pure source-trace, done against the real installed package (not generic
OpenWebRX/OpenWebRX+ documentation, and not the original Twente WebSDR,
which is a completely separate, unrelated codebase - see §14.8).

**Installed identity, confirmed directly (not assumed)**: this project runs
the **`luarvique/openwebrx` fork ("OpenWebRX+"), v1.2.123**, installed via a
venv at `/opt/openwebrx/venv` (package at
`.../site-packages/owrx/`, frontend at `.../site-packages/htdocs/`). Exact
component pins are recorded in `/etc/openwebrx/INSTALLED_COMMIT`. Live data
directory (confirmed both from the systemd unit's `WorkingDirectory` and
from `journalctl` startup log lines) is `/var/lib/openwebrx/`.

### 14.1 Markers/annotations - real, but on a separate page, never on the waterfall

OpenWebRX+ has a genuinely complete marker system: `owrx/markers.py`
orchestrates four buckets (static file-backed `markers`, `receivers.py`'s
`rxmarkers` for other public OpenWebRX/WebSDR/KiwiSDR instances,
`eibi.py`'s `txmarkers` for shortwave broadcast schedules, `repeaters.py`'s
`remarkers`), plus live-decoded overlays for APRS/AIS/aircraft
(ADSB/ACARS/HFDL/VDL2/UAT)/sondes/Meshtastic that come from decoded RF
traffic, not a bundled file. All of it is rendered by already-shipped
frontend code (`htdocs/lib/MapMarkers.js`, `map-leaflet.js`/`map-google.js`)
with working popups and TTL-based aging - **no new PirateBox frontend code
would be needed to display markers, if the backend data were populated.**

**But it is real, load-bearing, and confirmed by tracing `index.html`
directly: none of this ever appears on or around the waterfall.** It lives
entirely on a separate full-page map (`/map`, Leaflet or Google Maps per
config), opened only via the header toolbar's "Map" button (`target=
"openwebrx-map"`, a **new browser tab**) or the `M` keyboard shortcut. This
corrects an implicit assumption behind the investigation request - there is
no native "labels around the waterfall" feature to switch on; the closest
analog to Twente's inline annotations is the separate bandplan ribbon
(§14.3), not the marker/map system.

**Click-to-tune is real but is the same offset-only mechanism as
everything else in the frontend, and silently fails outside the current
window.** A marker's frequency link (`Utils.linkifyFreq()`) opens/refocuses
the receiver tab at `/#freq=…,mod=…`. The receiver page's hash handler
(`DemodulatorPanel.js`'s `validateHash()`) **drops the request entirely
unless `|freq - center_freq| <= bandwidth/2`** - it never requests a center
retune, regardless of `allow_center_freq_changes`. When the frequency is
already in-window, it becomes a plain demodulator offset, identical to
every mechanism traced in §13.7-§13.10. This is exactly the same pattern as
the frequency-entry field, the waterfall click, and the bookmark bar - all
of them are offset-only and window-bounded; **the only mechanism anywhere
in the stock frontend that performs a genuine hardware retune is
`jumpBySteps()` on `PageUp`/`PageDown`** (§14.4).

Custom local markers ARE supported without touching upstream files - drop
a JSON file at `/etc/openwebrx/markers.json` or any `*.json` under
`/etc/openwebrx/markers.d/` (a dict keyed by id, same field set as the
built-in types: `lat`/`lon` required, optional `freq`/`mode`/`comment`/
`url`/etc.) and it's picked up on the hourly refresh cycle. This mechanism
has **no settings-UI or admin-page support anywhere in the shipped
frontend** - it is a config-file convention discoverable only by reading
`owrx/markers.py` directly, confirmed by an empty result on an exhaustive
grep of `htdocs/` and `owrx/controllers/` for any reference to it.

### 14.2 EiBi and repeaters are not actually "0 items" - the databases are populated; the filters explain everything

The "Loading items ... / Loaded 0 items" impression that motivated this
investigation does not match what the live system is actually doing right
now. Read directly:

```
eibi.json       9,442 entries  (3.06 MB)
repeaters.json  12,755 entries (2.49 MB)
receivers.json  1,371 entries  (505 KB)
```

and the live `journalctl -u openwebrx` startup log shows:

```
Loaded 9442 items from '/var/lib/openwebrx/eibi.json'...
Loaded 12755 items from '/var/lib/openwebrx/repeaters.json'...
Loaded 357 transmitters from EIBI.
Found 0 repeaters within 200km.
Loaded 0 repeaters.
```

**The "0" is specific to `repeaters`, and it is a hard-coded 200km
great-circle distance filter (`owrx/web/repeaters.py`'s `MAX_DISTANCE = 200`,
applied in `getAllInRange()`) against `receiver_gps` - which this project's
own `etc/openwebrx/sdrs_seed.py` deliberately sets to `{"lat": 0, "lon": 0}`
(documented there as a no-PII-exposure choice, §13's own comment block).**
With the receiver "located" at 0°N 0°E, the nearest of 12,755 real-world
repeaters is unsurprisingly outside any real-world range, so the filter
returns nothing. This is a **direct, structural consequence of a privacy
decision this project already made on purpose**, not a bug, a missing
download, or a misconfiguration to fix. The repeater subsystem is in fact
built entirely around a real `receiver_gps` - `owrx/web/repeaters.py` wires
a config-change callback that **deletes the cached file outright** if the
configured location moves more than 10km, meaning genuinely useful repeater
markers are architecturally inseparable from publishing the operator's
real approximate location to anyone using `/map` - directly in tension with
this project's existing privacy posture and Travel Mode's no-local-leakage
requirement (`docs/TRAVEL-MODE-DESIGN.md`).

EiBi has no comparable distance filter - `currentTransmitters()` filters
purely by UTC time-of-day/day-of-week against each entry's broadcast
schedule, which is why 357 (not 9,442, and not 0) were "active" transmitters
at the moment this investigation ran; the number legitimately varies by the
hour. **But EiBi turns out to be nearly irrelevant to this project's actual
hardware regardless of any filter**: measured directly from the live file,
entries range from 16.3 kHz to 27.184 MHz, and **99.93% (9,435 of 9,442)
sit below 24 MHz** - below this unit's own documented R820T practical
tuning floor (`sdrs_seed.py`'s own "~24 MHz-1766 MHz" comment). Only 7
entries in the entire database fall inside our receivable range at all.
Enabling EiBi-derived bookmarks (`eibi_bookmarks_range`, off by default and
not set in this project's config) would light up a feature that has
essentially nothing to show on this specific dongle.

No license or attribution string exists anywhere in the installed EiBi
code or cached data - see §14.8 before ever considering baking a snapshot
into this repo. Given the 0.07% overlap with our receivable range, that
question is largely moot for this project regardless of the answer.

### 14.3 The one genuinely promising native feature found: the bandplan ribbon is fully wired but has no data file installed

`owrx/bands.py` (`Band`/`Bandplan` classes) is a complete, independent
third annotation system - not markers, not bookmarks - that draws a
**colored, labeled ribbon of named frequency ranges directly onto the
frequency-scale canvas of the main receiver page**, confirmed to redraw on
zoom/pan/retune (`htdocs/lib/Bandplan.js`'s `draw()` reads
`get_visible_freq_range()` on every render) and toggled with the `B` key.
This is the closest native equivalent to Twente's inline "what lives here"
labeling this investigation found - and it operates purely against
whatever frequency window happens to be visible, so it needs no geographic
data and raises none of §14.2's `receiver_gps` privacy tension.

**It currently shows nothing on this installation, and the reason is
structural, not a bug**: `Bandplan._loadBands()` looks for
`/etc/openwebrx/bands{region}.json`, then a `bands{region}.json` relative to
the service's working directory (`/var/lib/openwebrx/bands.json` in
practice) - **neither exists**. The actual data files (`bands.json` plus
region variants `bands-r1.json`/`bands-r2.json`/`bands-r3.json`) exist only
in the separate source-build checkout at `/opt/openwebrx/src/openwebrx/`
used to build the installed wheel, and were **never copied** into either
the installed package or the runtime config/data directories during this
project's own install process. `bandplan_region` also isn't set in the live
config, so it defaults to `0` - which happens to map to the plain,
non-region-specific `bands.json` (not a region-1/2/3 variant), i.e. the
**most travel-generic option already lines up with this project's own
default**, no config change needed to get a sensible starting point.

Because this data file already ships as part of the OpenWebRX+ project's
own source tree (present on this exact Pi, just not installed into the
config path), populating it is a **file-placement action using upstream's
own bundled data**, not a new third-party database this project would need
to source, license, or maintain independently - a materially cleaner
licensing/provenance story than EiBi or RepeaterBook (§14.8). No code
changes anywhere are implied; the feature is already fully built and
wired up on both the Python and JS sides.

### 14.4 Frontend navigation already includes most of what Twente-style "explorability" needs - all client-side, all hardware-independent

Traced directly in `htdocs/openwebrx.js` and `htdocs/lib/Shortcuts.js`,
confirmed against the actual installed frontend rather than assumed from
older OpenWebRX documentation:

- **Mouse-wheel zoom** and **two-finger pinch zoom** - both already
  implemented, both a pure client-side rescale of the already-captured
  waterfall bitmap (no new samples, no additional CPU/DSP load).
- **Click-and-drag panning** - already implemented, and explicitly
  bounded in code to `±bandwidth/2` around `center_freq`; it is
  structurally impossible for it to show spectrum that wasn't actually
  captured.
- **A full keyboard shortcut set** (arrows to tune/zoom, `Ctrl+arrows` to
  change tuning step, `[`/`]` for squelch-based tuning, `B` for bandplan,
  `M` for map, `T` for frequency entry, `Y` for bookmark search) - all
  already shipped, none of it currently surfaced to a PirateBox visitor
  anywhere in `live.php` or the Radio Reference page.
- **A genuine hardware-retune shortcut already exists and would already
  work on this exact install right now**: `PageUp`/`PageDown` call
  `jumpBySteps()`, which sends the identical `setfrequency` protocol
  message this project's own `live.php` uses (§13.6-§13.10), gated the
  same way (`allow_center_freq_changes` + `magic_key`, both already set
  permissively by this project). The shift amount is `bandwidth/4` (512
  kHz at our 2.048 Msps profiles) per press - smaller than `live.php`'s
  own chosen 1.5 MHz Previous/Next Spectrum step, and reachable only by
  keyboard with no on-screen button or visible affordance at all. This
  was not previously documented in this project and is worth surfacing
  to visitors as a "did you know" rather than reimplementing - it is
  free, already-working functionality.
- **Frequency bookmarks bar** - three source layers merge onto one visual
  bar that repositions with zoom/pan: (1) visitor-added bookmarks stored
  in that browser's own `localStorage` (works today, zero server
  dependency, fully private per-visitor); (2) server bookmarks from
  `/etc/openwebrx/bookmarks.d/*.json` (not present on this install); (3)
  auto-generated bookmarks from EiBi/repeaters (off by default, and per
  §14.2 not very useful here even if turned on). Clicking any bookmark is
  the same offset-only, window-bounded mechanism as everything else.

### 14.5 What's fundamentally impossible with a single RTL-SDR, regardless of frontend work

Every navigation feature in §14.4 - zoom, pan, click-to-tune, the bandplan
ribbon - operates entirely within whatever ~2.048 MHz window is currently
being sampled. None of it can make two widely-separated frequencies (say,
an EiBi shortwave marker at 9.4 MHz and the FM broadcast band at 100 MHz)
simultaneously live and clickable - only one `center_freq` is ever actually
being captured at a time, by definition of instantaneous bandwidth. The map
page can display markers across the whole world at once because it isn't
tied to the waterfall at all, but clicking one only succeeds if that
frequency already happens to be inside the currently-tuned window;
otherwise the click is a silent no-op (§14.1). `jumpBySteps`/`setfrequency`
is the only mechanism that actually moves the receiver, and it does so
sequentially, one retune at a time - a hardware truth no amount of frontend
polish changes, matching this project's own already-established "don't
misrepresent a stitched/scanned overview as simultaneous live bandwidth"
principle from §13.9's design brief.

### 14.6 Scan/stitch broad-spectrum overview: feasibility only, not built

`rtl_power` is already installed on this Pi (part of the standard
`rtl-sdr` Debian package, alongside `rtl_sdr`/`rtl_fm`/`rtl_tcp` etc. -
already present, nothing to newly install). OpenWebRX+ itself has no
built-in periodic band-scanner (confirmed by an exhaustive grep for
"sweep"/"scan"/"rtl_power" across the whole installed package - the only
hits are the unrelated squelch-based in-window signal scanner).

**Device sharing is possible but exclusive, and time-boxed by usage, not
continuous**: traced through `owrx/source/__init__.py` - OpenWebRX+ only
acquires the RTL-SDR (spawns the `rtl_connector` subprocess that opens the
USB device) once at least one client (viewer or background task) is
connected, and releases it (`stop()`, sending `SIGTERM`) once the last
client disconnects, unless a device is explicitly marked `always-on` (not
the case in this project's config). **A separate scan tool could therefore
only acquire the device while nobody is actively viewing the live
receiver** - RTL-SDR/USB hardware doesn't support two processes holding it
open at once, so a scan attempted while a visitor is tuned in would simply
fail to open the device, not run in parallel.

**Rough cost, arithmetic only, nothing run**: sweeping the full 24-1766
MHz practical range in ~2.048 MHz steps is roughly (1766-24)/2.048 ≈ 851
retune steps; each needs real USB settle time plus `rtl_power`'s own
per-bin dwell/integration time before advancing, making a full sweep a
multi-minute (realistically much longer, depending on chosen dwell/
resolution settings) operation - not something that can run continuously
alongside a live, single-device receiver, and not something to attempt on
a Pi 3B+ without a deliberate idle-only scheduling design. **Verdict:
technically feasible later, using tooling already present on the system,
but genuinely non-trivial to do honestly (idle-only scheduling, explicit
"scanned N minutes/hours ago, not live" labeling, meaningful dwell-time
choice) - correctly out of scope for this round and not urgent given how
much of the desired "explorability" (§14.3, §14.4) is available without it.**

### 14.7 Implementation tiers for a future round (design only - none of this is built)

**Tier A - adopt native OpenWebRX+ capability with a config-layer-only
addition, no upstream code touched:**
Copy the OpenWebRX+ project's own bundled `bands.json` (§14.3) - already
present in the local source-build tree, matching `bandplan_region`'s
existing default of `0` - into `/etc/openwebrx/`. This lights up the
already-fully-implemented labeled bandplan ribbon with zero new frontend
code, zero new backend code, and upstream-authored data (cleanest
provenance of any option investigated - see §14.8). Complexity: minimal
(a file copy plus, if the shipped default file turns out to need review
for accuracy/appropriateness before use, some editorial curation). Pi 3B+
cost: negligible (a one-time parse at startup, no ongoing CPU). Offline:
fully - static local file, no network involved ever. Travel Mode: no
GPS/location dependency at all, unlike repeaters. Upstream-upgrade safety:
high (a config file OpenWebRX+ itself already reads by design, not a
patched source file). This is the single most promising concrete next
step this investigation found.

**Tier B - PirateBox-authored additions, entirely in our own repo, leaving
OpenWebRX+ untouched:**
(1) Add a short, visible hint in `live.php` (or the Radio Reference page)
documenting the already-existing, currently-invisible native controls -
scroll-wheel zoom, drag-to-pan, and specifically the `PageUp`/`PageDown`
hardware-retune shortcut - since all of it already works today and costs
nothing to surface. (2) Optionally extend `live.php`'s own range-bar
(§13.10) with hand-curated, travel-safe textual band labels (NOAA, FM
broadcast, aviation, marine, amateur allocations) sourced the same way
this project already curates its Universal-tier reference content
(`docs/REFERENCE-CONTENT-DESIGN.md`), avoiding any per-country repeater/
EiBi data entirely. Complexity: low, same risk profile as §13.10's own
range bar. Fully within this repo/deploy path, no operator `/etc/`
step needed.

**Tier C - deferred, later-round scan/stitch overview (§14.6):**
Not recommended for the near term. If pursued later: idle-only scheduling
(only sweep when `checkStatus()`-equivalent shows no connected clients),
explicit "scanned, not live" labeling matching this project's own honesty
principle from §13.9, and a realistic dwell-time/resolution budget for a
Pi 3B+. Revisit only after Tier A/B are in place and only if there's
still an appetite for it.

**Explicitly not recommended, based on this investigation**: enabling
repeater markers/bookmarks by setting a real `receiver_gps` (defeats this
project's own deliberate no-PII posture and Travel Mode's no-local-leakage
requirement - §14.2); baking a static EiBi snapshot into the repo for
offline use (99.93% of it is outside this hardware's receivable range, and
its licensing/redistribution terms were not found anywhere in the
installed code - §14.2, §14.8); enabling `eibi_bookmarks_range` (same
irrelevance).

### 14.8 Source/licensing discipline

**The original University of Twente WebSDR (PA3FWM's project) is a
completely separate, unrelated codebase from OpenWebRX/OpenWebRX+.** This
investigation used Twente only as UX inspiration (as instructed) and did
not read, copy, scrape, or transplant any of its frontend code - every
finding above traces the **already-installed, already-approved-as-a-
dependency OpenWebRX+ package** this project has run since §13, not
Twente's software.

**OpenWebRX+ itself** (the `luarvique` fork) is an existing, already-
installed dependency of this project (§13.1-13.4's own install history) -
using its own native, already-shipped features (markers, bandplan,
bookmarks) raises no new licensing question beyond what installing it
already implied.

**EiBi data** (`eibispace.de`): no license or attribution string exists
anywhere in the installed `owrx/web/eibi.py` code or the cached
`eibi.json` data itself - the only provenance trace is the hardcoded
download URL. If this project ever wanted to bake a static EiBi snapshot
into the repo for guaranteed offline use, `eibispace.de`'s own site terms
would need to be checked directly first - not inferred from the installed
code, which makes no claim either way. Given §14.2's 0.07% overlap with
this hardware's receivable range, that research is not judged worthwhile
pursuing.

**Repeater data** (RepeaterBook.com / ARD): same absence of any bundled
license/attribution in the installed code. Not recommended regardless,
per §14.2's `receiver_gps`/privacy conflict - the licensing question is
moot if the feature itself shouldn't be enabled.

**Bandplan data** (`bands.json` etc.): part of the OpenWebRX+ project's
own source distribution, already present on this Pi as a build artifact
of installing OpenWebRX+ itself - using it is using upstream's own bundled
data under whatever license already covers the rest of the installed
package, not a new third-party redistribution question. This is the
cleanest option of the three by a clear margin.

### 14.9 Answers to the round's specific questions

- **What Twente-like functionality does our installed OpenWebRX+ already
  have?** Wheel/pinch zoom, click-drag pan (both window-bounded), a
  geographic marker/map system (separate page, not on the waterfall), a
  bandplan-ribbon feature (fully wired, currently dataless), a multi-source
  bookmark bar, and one genuine keyboard-only hardware-retune shortcut
  (`PageUp`/`PageDown`) already compatible with this project's current
  config.
- **Why are our EiBi/repeater databases currently empty?** They are not
  empty at the file level (9,442 / 12,755 entries, actively refreshed).
  Repeaters show 0-in-range purely because `receiver_gps` is deliberately
  `(0,0)` for privacy; EiBi's "357 active" count is normal time-of-day
  filtering, and the full database is 99.93% below this hardware's
  receivable range regardless.
- **Can native markers appear on the waterfall and tune the receiver?**
  No to the first half - markers only ever appear on the separate `/map`
  page. Clicking one (or a bookmark, or a typed frequency) only ever sets
  a demodulator offset, and only if the target frequency is already inside
  the currently-sampled window; otherwise it silently does nothing. It
  never triggers a real center retune.
- **Can we get useful offline band/station/service annotations without
  reinventing the frontend?** Yes, for the bandplan ribbon specifically -
  upstream's own bundled data, already-shipped frontend rendering, just
  needs the data file placed in `/etc/openwebrx/` (Tier A). Not for
  EiBi/repeaters, for the reasons above.
- **What zoom/pan/navigation capabilities already exist?** Wheel zoom,
  pinch zoom, drag pan (all window-bounded, all client-side/free), a full
  keyboard shortcut set, and the `PageUp`/`PageDown` real hardware-retune
  shortcut.
- **What small missing UX pieces would actually be worth building
  ourselves?** Surfacing the already-working zoom/pan/`PageUp`/`PageDown`
  controls to visitors (currently invisible/undiscoverable - free, no
  code risk); populating the native bandplan ribbon (Tier A); optionally
  extending `live.php`'s own range bar with curated travel-safe band
  labels (Tier B).
- **What is impossible because of RTL-SDR instantaneous bandwidth?** Any
  simultaneous live view/click-tune across widely separated frequencies -
  only one ~2.048 MHz window is ever actually sampled at a time, and every
  native navigation feature operates only within it.
- **Is a later scanned/stitched broad-spectrum map technically worthwhile
  on this Pi?** Feasible later using already-installed `rtl_power`
  (~851 steps for a full sweep), but genuinely nontrivial to do honestly
  (idle-only scheduling since OpenWebRX+ and a sweep can't share the
  device concurrently, explicit non-live labeling, realistic dwell-time
  budget on a Pi 3B+). Correctly deferred; not recommended now.
- **What exact next implementation phase is recommended?** Tier A (copy
  OpenWebRX+'s own default `bands.json` into `/etc/openwebrx/`, no code
  changes) alongside Tier B's `live.php`/Radio-Reference hint about the
  already-working native zoom/pan/`PageUp`/`PageDown` controls.
- **Does that next phase require sudo/operator action, or can this
  session own it end-to-end?** Tier A's file placement is under
  `/etc/openwebrx/` - the same operator-gated path as every prior
  `sdrs_seed.py` deployment in §13 (`sudo tools/update_openwebrx_config.sh`
  or equivalent); this session has no standing grant for it. Tier B is
  entirely inside `var/www/html/`/`docs/`, deployable via the existing
  `sudo piratebox_deploy.sh` grant this session already has - ownable
  end-to-end without operator involvement.

### 14.10 Stop condition honored

This round made **no changes** to `/etc/`, no service restarts, no config
edits, no package installs, no changes to `live.php`'s working controls,
and no RF/sample-rate/gain changes. Everything above is documentation of
findings from read-only inspection (`cat`/`find`/`grep`/`journalctl`/
`dpkg -l`/`which`/read-only JSON parsing) against the real installed
system, plus a design-only recommendation for the next round. §13's
human-validated broad-retuning UX (presets, manual entry, Previous/Next
Spectrum, the range-bar navigator) was not touched and is not affected by
anything in this section.

---

## 15. Implementing §14's Tier A + Tier B recommendation: native bandplan ribbon + discoverable navigation help (2026-09-06)

Following §14's investigation, this round implemented the two
recommended, lowest-risk tiers: enabling OpenWebRX+'s own native
bandplan ribbon with its bundled upstream data (Tier A), and adding
concise, verified navigation help to `live.php` (Tier B). **Nothing from
§13's human-validated broad-retuning UX was touched.** No RTL-SDR
sample rate, gain, receiver profile, `magic_key`, `max_clients`, or
`receiver_gps` value was changed. No OpenWebRX+ source/frontend file
was modified.

### 15.1 Tier A - re-verified before touching anything, then implemented as vendored upstream data

Before copying anything, §14.3's claims were re-confirmed directly
against the live system (not re-assumed from the prior round's own
report):

- **Exact source path**: `/opt/openwebrx/src/openwebrx/bands.json`, in
  the local build checkout of `https://github.com/luarvique/
  openwebrx.git`. Confirmed (after scoping git's dubious-ownership
  check to just that one directory, not a global config change) that
  this checkout's `HEAD` is **exactly** `2d60e894d0889382d2eb0574a19f
  027f8504dcfa` - the same hash already pinned as `OPENWEBRX_COMMIT` in
  this project's own `tools/install_openwebrx.sh`, with a clean `git
  status` on `bands.json` itself (no local modification) - so the file
  copied is genuinely what this exact pinned install would rebuild
  from, not an assumption.
- **Expected installed/config path**: confirmed by reading `owrx/
  bands.py`'s `Bandplan.__init__`/`_loadBands()` directly -
  `self.fileList = ["/etc/openwebrx/bands{0}.json", "bands{0}.json"]`,
  tried in that order, with `{0}` replaced by `""` when
  `bandplan_region <= 0`. Target path: **`/etc/openwebrx/bands.json`**.
- **Matches `bandplan_region=0`**: confirmed - `bandplan_region` is
  absent from the live `/etc/openwebrx/config_webrx.py` (grep, zero
  matches) so OpenWebRX+'s own default of `0` (`owrx/config/
  defaults.py:445`) applies, which is exactly the region-file suffix
  that resolves to plain `bands.json` (not `bands-r1/2/3.json`).
- **Loading mechanism**: `_loadBands()` is a plain local `open()` +
  `json.load()` - no HTTP client, no network import anywhere in
  `owrx/bands.py`. **Confirmed fully offline at runtime.** It also
  hot-reloads on file-modification-time change (`_refresh()`,
  compared against `self.file_modified` on every query) - a service
  restart is not strictly required for OpenWebRX+ to notice a new/
  changed `bands.json`, though this round's deployment restarts the
  service anyway as part of the existing, already-established
  `update_openwebrx_config.sh` flow.
- **No OpenWebRX+ source modification required**: confirmed - this is
  a pure data-file placement into a path the installed code already,
  unconditionally checks; zero lines of `owrx/`/`htdocs/` code were
  touched.
- **End-to-end reactivity, traced beyond §14.3's own claim**: `owrx/
  connection.py`'s `sendBands()` is wired via `stack.filter("center_
  freq", "samp_rate").wire(sendBands)` - i.e. it fires and pushes a
  fresh `{"type": "bands", "value": [...]}` WebSocket message to every
  connected client **automatically, whenever `center_freq` changes for
  any reason** - a `live.php` preset, the manual frequency box,
  Previous/Next Spectrum, the range bar, or even native `PageUp`/
  `PageDown` (§15.3). The frontend's own message handler (`case
  "bands": bandplan.update(json['value']);`) redraws the ribbon on
  receipt, and `Bandplan.prototype.draw()` separately redraws on every
  waterfall zoom/pan against `get_visible_freq_range()`. **This means
  the ribbon requires no PirateBox-side wiring at all to follow this
  project's own broad-retuning controls - it was already designed by
  OpenWebRX+ to react to exactly this.**

**No replacement bandplan was hand-authored.** The exact file was
copied byte-for-byte (`sha256sum` matched against the source-tree
original both before and after copying) into this repo at
`etc/openwebrx/upstream/bands.json`, with `etc/openwebrx/upstream/
README.md` recording full provenance: source repo, exact commit,
license (OpenWebRX+/`luarvique/openwebrx` is AGPLv3 - `LICENSE.txt` in
that repository - the same license already covering the rest of this
project's OpenWebRX+ install; vendoring one of its own data files
raises no new licensing question beyond what already applies to
running it), and an explicit "do not hand-edit this file" note pointing
any future PirateBox-curated band/service annotations at a separate,
clearly-PirateBox-authored file instead (consistent with the Universal
-> country -> region -> local -> live content model in `docs/
REFERENCE-CONTENT-DESIGN.md`, which this vendored file deliberately
stays out of - it's the generic upstream default, not a PirateBox
content tier).

**Actual contents** (read directly, not assumed): 51 named bands -
amateur radio allocations (`160m` through `3cm`), shortwave/AM/FM
broadcast bands, and public/service allocations (`11m CB`, `PMR446`,
`GMRS462`/`GMRS467`, `ADS-B`, `VHF Air`, `VHF Marine`, LPD433, ISM
bands). **No country-specific channelization, no repeater data, no
geographic dependency of any kind** - this is OpenWebRX+'s own generic,
region-independent default, which is why region `0` (already this
project's own default) was the correct choice to preserve, not a
region-1/2/3 variant tied to a specific part of the world.

**Reproducibility**: wired into both `tools/install_openwebrx.sh`
(fresh installs - added right after the existing `openwebrx.conf` copy
in the "configuration" step) and `tools/update_openwebrx_config.sh`
(existing installs). Unlike `sdrs_seed.py`'s SDR/profile config, which
is deliberately seeded only once (to avoid clobbering an operator's own
`/settings` admin-UI changes), this file is copied unconditionally on
every run of either script - confirmed safe because no admin-UI editor
for the band *data* exists anywhere in the installed frontend (only
`bandplan_region`, a numeric region selector, is admin-editable, and
this project deliberately leaves it at its own default). A fresh
install now reproduces the ribbon automatically; nobody needs to
remember a manual copy step.

**Deployment status**: writing to `/etc/openwebrx/bands.json` requires
root, the same gate as every prior `/etc/openwebrx/` change in this
project. `tools/update_openwebrx_config.sh` already existed for exactly
this purpose (§13.8) and was extended, not replaced, to also deploy
this file - **one unchanged command for the operator**: `sudo tools/
update_openwebrx_config.sh`, run from the repo root. **Incidentally,
re-running this script also finally applies §13.9's own `tuning_step:
5000` fix**, discovered via a direct diff against the live config
during this round: the live `/etc/openwebrx/config_webrx.py` is still
at `version = 8` and is missing the entire `tuning_step` block that
`etc/openwebrx/sdrs_seed.py` has carried since §13.9 - that fix was
committed but, it turns out, never actually deployed (the operator's
own subsequent confirmation that `<`/`>` worked came from manually
changing OpenWebRX+'s in-browser "Tuning step" dropdown themselves,
which is real and independent, per §13.10 - but a new visitor who never
touches that dropdown is, right now, still getting the original 1 Hz
default). This was not reopened or redesigned - the already-committed
§13.9 fix is simply about to be deployed for the first time, as a
side effect of the one command this round also needs.

### 15.2 Tier B - navigation help, wording checked against actual traced behavior before writing anything

Per instruction, exact behavior was verified in `htdocs/openwebrx.js`/
`htdocs/lib/UI.js` before choosing wording - one assumption in the
original request turned out to be backwards:

- **Mouse wheel default is TUNE, not zoom.** Traced `canvas_mousewheel()`
  precisely: `zoom_me = (rightMouseDown || shiftKey) ? !getWheelSwap()
  : getWheelSwap()`, with `UI.getWheelSwap()` defaulting to `false`
  (`UI.js:38`, unless a visitor's own browser previously changed the
  "Hold mouse wheel down to tune" setting, stored in that browser's
  `localStorage`). With the default `false`: plain scrolling calls
  `tuneBySteps()` (fine-tunes the demodulator by one tuning step -
  **not** zoom), and it's specifically **Shift+scroll, or holding the
  wheel/right mouse button down while scrolling**, that calls
  `zoom_step()`. `live.php`'s help text was written to match this
  actual default, not the originally-assumed "wheel = zoom."
- **Touch pinch-to-zoom**: confirmed wired (`process_touch()` tracks
  two simultaneous touch points and computes a zoom ratio from the
  distance between them) - included as stated.
- **Drag-to-pan**: confirmed explicitly bounded in code to `±bandwidth/
  2` around `center_freq` (`canvas_mousemove()`) - cannot show spectrum
  outside the current window, matching the "do not imply zooming
  exposes frequencies not currently sampled" instruction.
- **Click-to-tune on the waterfall**: confirmed - a plain click (not a
  drag) calls `UI.setFrequency(UI.getFrequency(get_relative_x(evt)))`,
  the same offset-only, window-bounded mechanism as everything else in
  the stock frontend (§14.1/§14.4). Included, since it's real and
  already proven, not assumed.
- **Band plan ribbon toggle**: confirmed a real, visible settings-panel
  checkbox exists - `htdocs/index.html`'s `#openwebrx-bandplan-checkbox`,
  labeled **"Show band plan ribbon"** in the receiver's own Display
  settings, alongside the `B` keyboard shortcut. It defaults **off**
  (`UI.bandplan = false`, restored from that browser's own
  `localStorage` if previously toggled) - a new visitor needs to be
  told about it, or the newly-populated ribbon (§15.1) would go
  unnoticed. Both the checkbox and the `B` shortcut are mentioned.

The final `live.php` block (a single bordered "Explore the spectrum"
callout, not scattered paragraphs) reads:

> **Explore the spectrum:**
> - Scroll over the receiver below to fine-tune the yellow marker; hold
>   Shift while scrolling (or pinch on a touchscreen) to zoom the
>   waterfall in/out.
> - Drag to pan, and click anywhere on the waterfall to tune to that
>   point - all within the ~2 MHz view currently shown.
> - Check "Show band plan ribbon" in the receiver's own settings (or
>   press B) to label amateur, broadcast, and service bands as you look
>   around.
> - To jump to a different part of the spectrum: use a preset, the
>   frequency box, Previous/Next Spectrum, or the range bar above.
>
> *The receiver's own small `<`/`>` buttons and "Tuning step" dropdown
> do the same fine-tuning as scrolling - not a different control. Its
> Page Up/Page Down keys also jump the window itself, in smaller
> (~512 kHz) steps - handy, but less predictable near the edges of this
> receiver's tunable range than the controls above.*

This replaces the narrower `<`/`>`-only hint paragraph added in §13.9
(that specific correction is now folded into the broader callout, not
lost). No new JavaScript was added for this - it's static help text
next to controls that already exist, matching the "reuse OpenWebRX+'s
native capability, don't reinvent the frontend" instruction.

### 15.3 PageUp/PageDown, inspected precisely before deciding how prominently to present it

Exact mechanism (`htdocs/openwebrx.js`'s `jumpBySteps()`):

```js
function jumpBySteps(steps) {
    var f = center_freq + steps * bandwidth / 4;
    if (f >= 0) {
        ws.send(JSON.stringify({"type": "setfrequency", "params": {"frequency": f, "key": key}}));
    }
}
```

- **Step size**: exactly `bandwidth / 4` - at this project's 2.048 Msps
  profiles, **512 kHz per press**. This is a real, immediate hardware
  retune (the identical `setfrequency` protocol message §13.6-§13.10's
  own `live.php` mechanism uses), not a demodulator offset.
- **Overlap**: 512 kHz is exactly a quarter of the 2.048 MHz sampled
  width, leaving **75% overlap** between consecutive presses -
  substantially more conservative/overlap-preserving than `live.php`'s
  own Previous/Next Spectrum (1.5 MHz shift, ~27% overlap). Overlap is
  preserved either way; PageUp/PageDown is simply finer-grained,
  needing about 3 presses to cover the same ground as one Previous/Next
  Spectrum click.
- **General SDR profile fit**: sensible - `bandwidth` here is always
  `general-sdr`'s own `samp_rate` (2.048 MHz), so the step scales
  correctly with whatever profile is active; nothing in this mechanism
  is General-SDR-specific or broken by our profile choice.
- **Bounds risk, confirmed by reading the whole function**: `f >= 0` is
  the **only** check - there is no upper bound, and critically, **no
  check against this hardware's own practical ~24-1766 MHz range** the
  way `live.php`'s own controls deliberately clamp (`RANGE_LOW_HZ`/
  `RANGE_HIGH_HZ` in `live.php`'s JS). Repeated PageUp presses can walk
  the requested center frequency past 1766 MHz (or, for PageDown, down
  near/below 24 MHz) with no warning - the R820T tuner would simply
  fail to produce a usable signal there (already documented, `sdrs_
  seed.py`'s own general-sdr profile comment: "tuning outside that
  range will not damage anything - the tuner simply fails to produce a
  usable signal"), not a safety issue, but a worse experience than this
  project's own bounded controls.
- **Conflict with Previous/Next Spectrum**: none structurally - both
  ultimately call the identical `setfrequency` mechanism against the
  same shared receiver, so whichever fires last simply wins, the same
  way any two of `live.php`'s own controls (or a second browser tab)
  would already interact. The one caveat already documented in §13.10
  applies unchanged: `live.php`'s own `currentCenterHz` JS tracker only
  learns about a frequency change made through some *other* path (a
  keyboard press inside the iframe, a different client) on this page's
  own next successful tune, not immediately - not a regression
  introduced by this round.

**Decision, per instruction**: mentioned as a **secondary keyboard
shortcut**, in the smaller italic note beneath the primary bullet list,
not promoted to a primary navigation method - consistent with its
real-but-less-predictable, unbounded characteristics relative to this
project's own controls. Upstream keyboard handling itself was not
modified.

### 15.4 Bandplan human UX verification (completed after the §16 outage was resolved)

The operator's first run of `sudo tools/update_openwebrx_config.sh`
(§15.1's stop gate) exposed the §16 outage; after that was fixed and the
operator re-ran the identical command, `openwebrx.service` came up
clean (confirmed: `NRestarts=0`, `ActiveState=active`, no traceback in
`journalctl` since that start). The following was then verified against
the **real running service**, not re-claimed from source alone, using a
short-lived raw WebSocket client that mirrors `live.php`'s own
`tuneTo()` sequence exactly (handshake, `selectprofile`, `setfrequency`,
read the server's response, close) - built to answer the instruction
not to claim from source inspection what could instead be verified
live.

**Does it appear automatically?** No manual step needed server-side -
the ribbon's data (`"bands"` WebSocket messages) is pushed automatically
by `owrx/connection.py`'s existing `sendBands` wiring on every
`center_freq`/`samp_rate` change, confirmed live. (Whether it *renders*
in a given browser still depends on that visitor's own "Show band plan
ribbon" checkbox/`B` key, per §15.2 - that toggle is unaffected by this
verification and remains a client-side, per-browser preference.)

**Does it follow broad center-frequency retunes, and do the four
representative bands match the vendored data exactly?** Yes, both
confirmed directly - four fresh connections, each selecting
`general-sdr` and retuning to one test frequency, capturing the actual
`"bands"` message the server pushed in response:

| Requested center | `center_freq` reported back | Bands in window |
|---|---|---|
| 27.185 MHz | 27,185,000 Hz (exact match) | `10m`, `11m CB` |
| 100.1 MHz | 100,100,000 Hz (exact match) | `FM Broadcast` |
| 162.475 MHz | 162,475,000 Hz (exact match) | `VHF Marine` |
| 1090.0 MHz | 1,090,000,000 Hz (exact match) | `ADS-B` |

Every result matches this section's own prior prediction (§15.1's
vendored data), computed independently beforehand from the raw
`bands.json` contents rather than assumed - `11m CB` (26.965-28.0 MHz)
plus a sliver of the adjacent `10m` ham band (28.0-29.7 MHz, overlapping
the edge of a 2.048 MHz window centered on 27.185 MHz) at the first
point; `FM Broadcast` (87.5-108 MHz) entirely containing the second;
`VHF Marine` (156-174 MHz) entirely containing the third (this is also
OpenWebRX+'s own default profile's home band - the very first
connection opened during this verification round, before any
`selectprofile` was even sent, already showed `VHF Marine`, matching
`noaa-weather`'s 162.475 MHz default center); and `ADS-B` (960-1215
MHz) at the fourth, deliberately chosen as the "substantially higher
VHF/UHF area" the investigation round asked for. **The already-working
broad retune (§13) shows no regression** - every requested center
frequency came back exactly as requested.

**Is `tuning_step=5000` actually live?** Yes - confirmed directly in
the connection's first full `"config"` push (`{"type": "config",
"value": {"tuning_step": 5000, ...}}`), captured verbatim from the real
running service. (Subsequent delta-only config pushes after each
`setfrequency` correctly omit `tuning_step` since it didn't change -
this project's own property-stack change-tracking behavior, already
documented in earlier sections, not a sign the value was lost.)

**Does clicking a band label do anything?** Not investigated further
this round - `Bandplan.js`'s `draw()` renders a plain `<canvas>` ribbon
with no click handler anywhere in the source (confirmed by the absence
of any pointer/click event binding on `#openwebrx-bandplan-canvas` in
`htdocs/lib/Bandplan.js` during §14's own read of that file) - the
ribbon is a passive label, not an interactive control, consistent with
its purpose (context for the currently-tuned area, not a navigation
method - navigation stays with the presets/frequency box/Previous-Next
Spectrum/range bar, and the map page's markers for anything geographic).

**Does it work with General SDR?** Yes - all four checks above used the
`general-sdr` profile explicitly (`rtlsdr|general-sdr`), the same
profile `live.php` itself always selects.

**Any noticeable Pi/browser performance issue?** None observed:
`vcgencmd get_throttled` stayed at the same pre-existing `0x50005`
throughout (no new throttling event), no failed systemd units, and
`hostapd`/`dnsmasq`/`nginx` all remained active with zero restarts
across the entire verification session. The bandplan computation itself
is a plain in-memory list filter (`Bandplan.findBandsInRange`) against
51 small dicts - negligible cost regardless of the RTL-SDR's own DSP
load.

**Zoom/pan interaction - the one item this round could not verify
live.** Zoom (wheel/pinch) and pan (drag) are pure client-side canvas
operations with no WebSocket round-trip at all (confirmed by their
absence from every server-side message type traced in §14/§15) - there
is no protocol-level signal this session can observe to confirm they
render correctly, and installing a headless browser to check visually
was not attempted (would require a package install, outside this
round's scope without operator sign-off). This one item genuinely still
depends on a human glance at the receiver page - not because it wasn't
investigated, but because nothing about it is server-observable. Their
*mechanism* (bounded to `±bandwidth/2`, redrawing the same `bandplan`
object on every `get_visible_freq_range()` call) was already fully
traced against source in §14.4/§15.2 and did not change this round.

### 15.5 Explicitly not touched or reopened this round

`etc/openwebrx/sdrs_seed.py`'s `receiver_gps` (still `{"lat": 0, "lon":
0}`), `magic_key` (still `""`), `max_clients` (still `4`), all three
receiver profiles, RTL-SDR sample rate/gain, `live.php`'s existing
`tuneTo()`/Previous-Next-Spectrum/range-bar mechanics, and every
OpenWebRX+ source/frontend file. EiBi, repeater/location work, and the
deferred scan/stitch overview were not started. A regression test
(`tools/test_openwebrx_bandplan_deploy.py`) specifically guards
`receiver_gps` staying zeroed as part of this change, since the
bandplan work sits right next to that boundary in the same config file
without needing to cross it.

---

## 16. Live outage caused by the §15 deploy: a latent `version` field bug from an earlier round, exposed (not introduced) by finally deploying `tuning_step` (2026-09-06)

**Incident**: the operator ran `sudo tools/update_openwebrx_config.sh`
per §15's stop gate. The deploy itself completed ("Copied etc/openwebrx/
sdrs_seed.py -> /etc/openwebrx/config_webrx.py", "Copied etc/openwebrx/
upstream/bands.json -> /etc/openwebrx/bands.json") but `openwebrx.service`
then crash-looped on every subsequent start with:

```
ValueError: Configuration version is too high (current: 8, found: 9)
```

confirmed via `journalctl -u openwebrx` showing the exact traceback
through `owrx.__main__.start_receiver` -> `Config.validateConfig()` ->
`ClassicConfig.__init__` -> `Migrator.migrate(pm)` ->
`owrx/config/migration.py:145`'s `raise ValueError(...)`.

### 16.1 Root cause, traced to the exact line and the exact commit

Read `owrx/config/classic.py` and `owrx/config/migration.py` directly
(not assumed): `ClassicConfig.__init__` loads `/etc/openwebrx/
config_webrx.py` as a plain Python module (`_loadPythonFile` -
`importlib.util.spec_from_file_location` + `exec_module`, collecting
every top-level name), then immediately calls `Migrator.migrate(pm)`.
That function reads the config's own `version` field and:

```python
class Migrator(object):
    currentVersion = 8
    ...
    @staticmethod
    def migrate(config):
        version = config["version"] if "version" in config else 1
        if version == Migrator.currentVersion:
            return
        elif version > Migrator.currentVersion:
            raise ValueError(
                "Configuration version is too high (current: {}, found: {})".format(...)
            )
        ...
```

**`Migrator.currentVersion = 8` is hard-coded in the installed package**
(`/opt/openwebrx/venv/lib/python3.13/site-packages/owrx/config/
migration.py:128`) for this project's exact pinned OpenWebRX+ v1.2.123
/ commit `2d60e894d0889382d2eb0574a19f027f8504dcfa` (the same hash
`OPENWEBRX_COMMIT` in `tools/install_openwebrx.sh` already pins). This
field is **not** a "how many times has this file's content changed"
counter - it is OpenWebRX+'s own config-schema migration marker,
meaningful only insofar as it matches or falls below whatever schema
version the currently-installed code actually understands.

`git log -p -- etc/openwebrx/sdrs_seed.py` shows exactly how this went
wrong, across two separate rounds, both **already merged before this
session's Tier A/Tier B work began**:

- Commit `209a82d` (§13.8, the `magic_key` fix) bumped `version` from
  `7` to `8` while adding `magic_key`/`max_clients` - neither of which
  needed any schema migration. This bump was **harmless purely by
  coincidence**: `8` happens to equal `Migrator.currentVersion`, so
  `migrate()`'s `version == currentVersion` branch returned immediately
  with no error, and this was never caught because that specific config
  was applied and worked live.
- Commit `e499b44` (§13.9, the `tuning_step` fix) then bumped `version`
  from `8` to `9`, following the same (wrong) mental model. This
  **did** exceed the ceiling - but §13.9 itself documented that this
  fix was "not yet applied to the live system," and it genuinely never
  was, until this round's `update_openwebrx_config.sh` run finally
  applied it (see §15.1's own "incidental finding" about the live
  config still being at `version=8` prior to this deploy). **This bug
  has existed in the repo since `e499b44`, latent and undeployed, for
  the entire duration of §13.10, §14, and the start of §15** - it was
  exposed by this round's deploy, not introduced by it. Tier A/Tier B's
  own changes (the vendored `bands.json`, the installer script edits,
  the `live.php` help text) played no part in causing this - confirmed
  by the traceback itself, which fails inside `Config.validateConfig()`
  before OpenWebRX+ ever reaches the bandplan-loading code path at all.

**Verified the exact ceiling directly against the pinned source**, not
inferred: `Migrator.currentVersion = 8` was read straight out of the
installed `owrx/config/migration.py` on this Pi, for the exact
`OPENWEBRX_COMMIT` this project pins - not a generic assumption about
"OpenWebRX" versioning.

### 16.2 Fix: freeze `version` at the correct ceiling, document why, guard against recurrence

`etc/openwebrx/sdrs_seed.py`: `version = 9` -> `version = 8`, with a
long explanatory comment directly above it (added specifically so a
future round adding an unrelated setting doesn't repeat this exact
mistake a third time) spelling out that this field is tied to the
installed package's `Migrator.currentVersion`, not to this file's own
edit history, and that it must only ever change alongside a verified
`OPENWEBRX_COMMIT` upgrade whose own `migration.py` raises the ceiling
- never as a side effect of adding a plain setting.

**All intended settings preserved, verified, not just assumed**:
`magic_key=""`, `max_clients=4`, `receiver_gps={"lat": 0, "lon": 0}`,
`tuning_step=5000`, and all three RTL-SDR profiles are unchanged in the
corrected file - confirmed both by `diff` against the pre-incident
commit (only the `version` line and its new comment differ) and by the
real-class verification in §16.3 asserting each of these survives the
actual `ClassicConfig`/`Migrator` load path intact.

**The bandplan work (§15) was not rolled back.** `etc/openwebrx/
upstream/bands.json` and both installer scripts are unchanged by this
fix - the deploy log the operator pasted shows `bands.json` was already
copied successfully before the crash (the crash happens during
`Config.validateConfig()`, which runs before OpenWebRX+ ever reaches
`owrx/bands.py`'s loading code), so once the service starts at all, the
band data is already correctly in place from the same deploy that
caused the outage.

### 16.3 Verified the fix against the real installed code before asking for a redeploy - not just re-reading the diff

Per instruction, this was tested against the actual load path, not
assumed correct from the comment fix alone. Replicated
`ClassicConfig.__init__`'s exact sequence
(`ClassicConfig._loadPythonFile()` then `Migrator.migrate(pm)`) using
the real installed classes, imported directly from `/opt/openwebrx/
venv/lib/python3.13/site-packages` (the same "unit-level verification"
technique first used in §13.8), against the **corrected** file:

```
Migrator.currentVersion (installed, hard-coded) = 8
sdrs_seed.py declares version = 8
Migrator.migrate(pm) succeeded - no ValueError. Fix verified.
PASS: magic_key/max_clients/receiver_gps/tuning_step all intact after migrate().
```

**Sanity-checked the harness itself against the pre-fix (broken)
file**, to confirm it actually discriminates rather than passing
regardless of input - re-running the identical script against the
`version=9` commit (`e0d53a5`) reproduced the **exact same traceback**
the live service hit:

```
sdrs_seed.py declares version = 9
...
ValueError: Configuration version is too high (current: 8, found: 9)
```

This confirms both that the fix is correct and that the verification
method would have caught the original mistake had it existed before
`e499b44` was merged.

### 16.4 New regression test: this cannot silently reach a live deploy again

`tools/test_openwebrx_config_version.py` (4 tests, all passing):

- A **static** assertion that `sdrs_seed.py`'s declared `version`
  equals a known-good constant (`8`, tied by comment to the exact
  `OPENWEBRX_COMMIT` it was verified against) - runs anywhere, no
  installed OpenWebRX+ required.
- A check that `OPENWEBRX_COMMIT` in `tools/install_openwebrx.sh`
  hasn't silently moved out from under that known-good constant without
  the constant being re-verified.
- A **dynamic** check (skipped gracefully if the real venv isn't
  present in whatever environment runs the suite, e.g. off-Pi CI):
  imports the actual installed `owrx.config.classic.ClassicConfig` and
  `owrx.config.migration.Migrator` and replicates the exact real load
  path against this repo's own `sdrs_seed.py` - the strongest possible
  check, since it fails exactly the way the live service actually
  failed, using the real installed code rather than an assumption about
  what it does. On this Pi, this test suite would have failed loudly at
  `e499b44`'s own commit time, well before any deploy - not just after
  this round's incident.
- A companion check that the real installed `Migrator.currentVersion`
  itself still matches the test's own hardcoded expectation - catches
  the reverse failure mode (an operator or future round independently
  updating the installed OpenWebRX+ without anyone reconciling this
  project's own config version against it).

### 16.5 Recovery: one command, using the now-fixed repo source

No hand-editing of `/etc/openwebrx/config_webrx.py` was needed or
recommended - the fix lives entirely in the repo's own `etc/openwebrx/
sdrs_seed.py`, already verified against the real installed `Migrator`
class (§16.3). Recovery is the **identical command** already used for
this round's own deploy, now safe because the source it copies has been
corrected:

```
sudo tools/update_openwebrx_config.sh
```

run from the repo root. This re-copies the corrected `sdrs_seed.py`
(now `version = 8`) to `/etc/openwebrx/config_webrx.py`, re-copies the
(unaffected, already-correct) `bands.json`, and restarts the service -
the same three effects as the operator's original run, this time
without the schema-version mismatch.

### 16.6 Status as of this writing

**Resolved and confirmed live.** The operator ran §16.5's recovery
command; `openwebrx.service` came up clean and stayed active
(`NRestarts=0`, no traceback in `journalctl` since that start,
confirmed again after the follow-up verification session below rather
than only at the moment of restart). §15.4 records the full live
verification performed once the service was confirmed healthy:
`bands.json` loads and reacts correctly to retunes, `tuning_step=5000`
is confirmed present in a real config push, and the bandplan ribbon's
actual server-side content matched this section's own predictions
exactly at all four representative frequencies (27.185/100.1/162.475/
1090 MHz), with the already-working broad retune (§13) showing no
regression (`center_freq` echoed back exactly as requested every time).
System health remained normal throughout (no failed units, throttle
unchanged at the same pre-existing `0x50005`, zero restarts on
`hostapd`/`dnsmasq`/`nginx`/`openwebrx`).

**The one item this round could not verify itself**: zoom/pan/pinch
rendering correctness is a pure client-side canvas behavior with no
server-observable signal - this remains dependent on a quick human
glance at the receiver page, not because it was skipped, but because
nothing about it crosses the network. Its mechanism was already fully
traced against source (§14.4/§15.2) and is unchanged by anything in
this section.

---
