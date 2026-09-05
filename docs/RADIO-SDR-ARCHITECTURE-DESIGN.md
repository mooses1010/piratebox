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

---

## 1. Executive summary (revised 2026-09-05)

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
  alongside its `arecord` audio capture).
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

## 6. What we still need from the user's actual hardware (updated 2026-09-05)

1. **Malahit DSP SDR V3 (HiDY)** — hardware identity is now known
   (§2a); still needed:
   - Firmware version, via the long-press-power-button method §2a
     found documented for this exact product — **no USB connection
     required for this check.**
   - Confirmation of USB-C (already found likely true for this
     product line generally, per §2a; a glance at the unit confirms).
   - `lsusb`/`dmesg` output once connected (§11) — the actual next
     step, checked against the `ffff:0737`/"MicroGenSF Malahit
     reciever" hypothesis from §2a, not assumed to match.
   - Whether one or two `/dev/ttyACM*` devices appear (§2a found one
     reported unit with two).
   - PCB revision marking — optional, only if the case is opened for
     an unrelated reason; not required for this investigation.
2. **RTL-SDR**: no advance information needed — this gets identified
   the same way the ALFA was: real `lsusb` output once connected, and
   a photo of the printed label if the VID:PID/product string is
   ambiguous or ambiguous-looking (rebranded units are common in this
   ecosystem).
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

## 8. Proposed architecture (design only — nothing built yet)

```
Radio Capability (optional, Operational-adjacent but Optional/Field layer)
├── Backend abstraction
│   ├── Malahit backend   (SoapyMalahitRR, if it fits this unit - NEEDS HARDWARE)
│   ├── RTL-SDR backend   (native rtl-connector or SoapySDR - well-trodden)
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

## 11. First physical hardware gate — Malahit DSP SDR V3 (HiDY) USB enumeration (revised 2026-09-05)

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

## 12. Open questions carried forward (updated 2026-09-05)

1. Does `SoapyMalahitRR` (naming: "Malahit-**R1**") actually work with
   this owned V3 handheld unit's USB-Audio-Class IQ interface, or does
   it expect a different, bare wired module product entirely? The
   hardware correction (§2a) makes this LESS likely to pan out than
   originally framed, not equally uncertain. (§2a, §5)
2. This unit's exact firmware version (checkable now, with no USB
   connection, via the long-press-power-button method — §2a, §11 step
   zero) and confirmed USB connector type (likely USB-C per §2a, worth
   a glance to confirm).
3. Whether this unit's actual `lsusb` VID:PID matches the one
   community-reported value found (`ffff:0737`, "MicroGenSF Malahit
   reciever") or differs, and whether one or two `/dev/ttyACM*`
   devices appear. (§2a, §11)
4. This RTL-SDR's exact model/VID:PID. (§3, §6)
5. Real OpenWebRX+ CPU/RAM/client-count behavior on this actual Pi
   3B+/Trixie — no published benchmark exists for any Malahit variant
   or RTL-SDR on this OS/hardware combination. (§4, §5)
6. Actual USB charging behavior of this unit when attached to the Pi —
   §2a's finding that charging appears bundled with any powered-on USB
   connection makes a true data-only arrangement look less likely to
   be achievable by cable choice alone; needs direct measurement.
   (§2a, §11)
7. Whether a separately-powered USB hub becomes the long-term
   architecture for one or both devices, once §11's findings are in.
   (§2a, §8)
8. The dual-encoder-button reboot/reset behavior (§2a) remains
   unexplained by any source found — not something to actively
   investigate further ourselves, but worth asking about if this
   project ever engages the OpenWebRX+/Malahit community directly.

None of these block writing this document; all of them block writing
any code.
