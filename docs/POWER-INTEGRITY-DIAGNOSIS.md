# Power Integrity Diagnosis

**Status: DIAGNOSIS + ONE COMPLETED A/B TEST.** This round investigated
the chronic `0x50005` undervoltage condition and, in a same-day
follow-up, tested and **ruled out the power cable as a sufficient fix**
(§9a) - the original Samsung phone cable was replaced with a
higher-quality one, same Apple 12W brick, same loads; active
under-voltage remained after independent re-verification. This is the
required evidence gathering before the AWUS036ACM production
migration's power-aware gate (`docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md`
§8) can be considered met - it is **still not** that gate being met.
Read `docs/POWER-UPS-DESIGN.md` for the separate, forward-looking UPS/
battery requirements; this document is about the *current* wall-power
path.

**The goal was never to make `0x50005` disappear cosmetically.** It
hasn't disappeared. This document establishes what's actually known,
what's still genuinely uncertain, and what physical step should happen
next - all with the evidence that justifies it, not assumption. The
next controlled variable, per the operator's own plan, is the power
brick itself (§9a) - not yet tested.

---

## 1. What `0x50005` actually means on this Pi, verified locally

Bit meanings confirmed from this system's own `man vcgencmd` (not
copied from memory or prior documentation):

| Bit | Meaning | Kind |
|---|---|---|
| 0 | Under-voltage detected | **current** |
| 1 | Arm frequency capped | current |
| 2 | Currently throttled | **current** |
| 3 | Soft temperature limit active | current |
| 16 | Under-voltage has occurred | sticky (since boot) |
| 17 | Arm frequency capping has occurred | sticky |
| 18 | Throttling has occurred | sticky |
| 19 | Soft temperature limit has occurred | sticky |

`0x50005` = bits 0, 2, 16, 18 set. **Decoded precisely: this is not a
sticky/historical-only reading.** Bits 0 and 2 - the *current-condition*
bits - are set right now, alongside the historical bits. **This Pi is
reporting active under-voltage at the moment of every check performed
this round**, not merely remembering a past event.

**Not thermal:** `vcgencmd measure_temp` reads 40.8-41.3°C this round -
nowhere near this SoC's thermal limits. Bit 3/19 (soft temperature
limit) were never set. `dmesg` shows zero thermal-throttling or
frequency-capping messages this boot. CPU governor is `ondemand`, all
four cores at full 1400MHz throughout. **This is a voltage problem, not
a heat problem** - the operator's separate observation about the fans
sounding different after a power cycle is addressed on its own terms in
§10, not folded into this finding.

**Core voltage is not the input rail:** `vcgencmd measure_volts core`
reads a nominal 1.2000V, `sdram_c`/`sdram_i` read nominal 1.2500V,
`sdram_p` reads nominal 1.2250V - all in spec. These are the Pi's own
*regulated, downstream* rails, produced from the raw 5V input by the
board's own switching regulators. **A nominal core-voltage reading does
not prove the 5V input itself is healthy** - see §4 for why this
specific pattern (downstream nominal, input-side detector tripping) is
itself diagnostic.

---

## 2. Event timeline

### This boot (post-regulatory-domain-fix reboot, 2026-09-03 ~15:50 onward)

- **15:50:08** - `Undervoltage detected!` at boot. Stayed continuously
  asserted for the next ~19 minutes.
- **16:09:01 - 16:10:20** - **rapid oscillation**: `Voltage normalised`
  / `Undervoltage detected!` flipped four times within about 80 seconds
  (16:09:01 → 16:09:03 → 16:10:04 → 16:10:06 → 16:10:18 → 16:10:20),
  ending on `Undervoltage detected!` - still asserted at every
  subsequent check this round.
- **No correlated event found** in `dmesg` for the oscillation window -
  no USB activity, no thermal event, no frequency-capping. This
  session's own command history shows nothing running that would
  explain a load spike at that exact moment. **This specific
  oscillation's trigger is not established from available evidence** -
  recorded honestly as unexplained, not attributed to anything.
- Zero USB resets/disconnects this boot beyond the ALFA's single,
  expected enumeration sequence (no repeat of the original hot-plug
  disconnect/reconnect cycle from the Hardware Validation Round).
- Zero SD/MMC I/O errors, zero ext4 errors, zero read-only-filesystem
  transitions this boot (see §7).

**Pattern significance:** a long stable-bad period followed by rapid
flip-flopping is consistent with a rail sitting *very close* to the
firmware's detection threshold (commonly ~4.63V on this hardware
family) - close enough that small, ordinary fluctuations tip it either
side of the line repeatedly, rather than a hard, deep brownout.

### This project's own operational memory (`data/device-history.json`)

```json
{"undervoltage_daily": [{"day_start": "2026-09-02 17:00 PDT (UTC-day boundary)", "count": 5}], ...}
```
5 undervoltage events recorded for the current UTC-day bucket as of
this file's last update (15:50:02 PDT - just before this boot's own
first detection at 15:50:08). **This boot's later 16:09-16:10
oscillation (4 further transitions) had not yet been reflected in this
counter as of this round's check** - the true same-day count is higher
than the file currently shows. `boot_events` is empty (this project's
existing device-memory mechanism does not currently populate that
array from real boot transitions - noted, not fixed this round, since
this is diagnosis-only).

### Prior documented episodes (from this project's own history, not
re-derived from memory)

- **Stage 29 (2026-09-02), first observation:** the Pi's shutdown
  button was tested on "standalone wall-brick power" for the first
  time. `0x50005` was observed on the very next boot - 4 separate
  `Undervoltage detected!` lines in the first ~4 minutes, the "-now"
  bits still set after 3 rechecks over the following 35 seconds (not a
  boot-time blip that cleared). Rail voltages (core, sdram) read
  nominal at the same time; CPU stayed at full 1400MHz - **the exact
  same signature reproduced by this round's own checks**, three weeks
  of project time earlier under a different actual boot. (See
  `docs/OPERATIONAL-DECISIONS.md` "Stage 29 Real-Hardware Confirmation"
  for the full original entry.)
- **OLED I2C bring-up session (2026-09-03), the severe episode:**
  **triggered by the operator physically reconnecting the OLED's I2C
  wiring while the Pi was powered on** - not by fan interaction. SSH
  became extremely slow, the GPIO25 hold-to-shutdown did not trigger,
  ending in a hard power cycle. Investigated on the next boot:
  `piratebox-button.service` came back up clean (no software defect in
  it - CPU starvation under throttling can stall any process's
  scheduling without indicating a bug in that process). No previous-
  boot journal was available then either (see §8 - this gap is
  pre-existing, not new). (See `docs/HARDWARE-INTEGRATION-DESIGN.md`
  and `docs/OPERATIONAL-DECISIONS.md`, both already recording this.)
- **AWUS036ACM insertion (Hardware Validation Round):** one disconnect/
  re-enumeration at first insertion, coincident with one SD-card I/O
  error and one USB host-controller timeout - self-resolved, never
  repeated across every subsequent ALFA test (2.4GHz AP, WPA2
  association x3, 5GHz AP, WPA2 association x2, this reboot).

**No persistent journal exists across any of these boots** -
`journalctl --list-boots` shows only the current boot every time this
has been checked, including during this round. `/var/log/journal`
still does not exist. This gap was already flagged as worth fixing
during the OLED bring-up session and remains unfixed - **still not
addressed this round**, since enabling it is a system-level config
change requiring an operator gate (see §14), not something to do
silently while investigating an unrelated problem.

---

## 3. Current power path, audited without physically touching anything

- **Board:** confirmed via `/proc/device-tree/model` - genuine
  Raspberry Pi 3 Model B Plus Rev 1.3 (not a different board than
  assumed).
- **Input connector:** the Pi 3B+'s standard micro-USB power input (no
  USB-C on this board revision).
- **USB topology** (`lsusb -t`): a single internal 4-port hub off the
  SoC's own USB controller, feeding a second internal 3-port hub, which
  in turn feeds both the onboard Ethernet chip (Microchip/SMSC
  `0424:7800`, `lan78xx` driver - confirmed via `ethtool`/sysfs to be
  the Pi's own internal chip, not a separate external dongle sharing
  the bus) and the AWUS036ACM. **Everything - Pi core, onboard
  Ethernet, and the ALFA - draws from the same single 5V input**, as
  expected for this board; there is no separate power injection point.
- **GPIO-powered loads, per the operator's own account this round**
  (not previously recorded in any project doc - noted as newly
  provided, same provenance convention as other operator-asserted
  facts in this project): two small heatsink fans wired directly to
  physical pin 4 (5V) and physical pin 6 (GND) - simple always-on
  fans, no PWM/software control exists with this wiring. The OLED is
  I2C (low current, a few mA per prior findings). The shutdown button
  is GPIO25, negligible current.
- **What could NOT be determined from existing project records or
  without physically reading a label:** the wall brick's exact make/
  model/rated output, and the power cable's exact gauge/length/
  connector quality. `docs/POWER-UPS-DESIGN.md` and
  `docs/OPERATIONAL-DECISIONS.md` both refer to "a standalone wall-
  brick power supply" as a category (distinguishing it from a shared
  USB-hub source) but record no specific rating. **This is not
  guessed here** - see §8 for exactly what the operator should read
  off the physical hardware.

---

## 4. Likely failure-class ranking

Evaluated against the instruction that a nominally adequate wattage/
current rating does not prove adequate *voltage* at the Pi under load:

**Strongest evidence: A (inadequate power brick) and/or B (excessive
cable voltage drop), acting together as a marginal supply path.**
The repeated, cross-session signature - the firmware's *input-side*
under-voltage detector trips while every *downstream, Pi-regulated*
rail (core, sdram) reads nominal and the CPU runs unthrottled at full
frequency - is the specific fingerprint of a raw 5V input that dips
below the ~4.63V detection threshold while the Pi's own onboard
switching regulators are still successfully holding their outputs in
spec. That points upstream of the Pi's own regulation, toward the
brick and/or the cable between it and the Pi, not at the Pi's internal
power path. This is consistent across every occasion this has been
checked - Stage 29, the OLED episode, and every check this round -
spanning weeks of project time and very different activity levels
(idle, GPIO reconnection, ALFA AP/association testing, reboots),
which argues for a **chronic headroom deficit**, not a one-off fault.

**Plausible, not ruled out: C (poor/loose connector/contact).** No
evidence for or against this specific mechanism exists from software
alone - a marginal connector often worsens under vibration or a
specific cable angle, neither of which is observable from here. Worth
a simple visual inspection (see §8), not assumed.

**Weaker evidence: D (Pi's own input/power-path problem).** The
"downstream rails nominal, CPU unthrottled" signature argues against a
*failed* onboard regulator specifically (a failing regulator would
more likely show a downstream rail out of spec, not a clean pass-
through). A degraded input connector *on the Pi's own board* can't be
fully excluded without physical inspection, but nothing in the evidence
points there more than it points upstream.

**Real but insufficient alone: E (load/transient problem).** Genuinely
contributing (see §5 on fan-stall, and the ALFA's one insertion-time
event, itself best explained as a USB hot-plug inrush transient) - but
cannot be the *sole* explanation, since under-voltage was observed
continuously and then oscillating **with no known load-transient
event occurring** during large stretches of this round's own timeline
(including the unexplained 16:09-16:10 oscillation).

**Overall characterization: F, a combination** - a marginal-headroom
supply/cable path (A/B, chronic baseline) that ordinary load
fluctuations and occasional larger transients (E) are enough to tip
below threshold, sometimes briefly (the common case, self-recovering,
no further effect) and at least once severely enough to compound with
a *separate* physical event (live OLED reconnection) into a real stall
requiring a hard power cycle.

---

## 5. The fan-stall question - answered directly

**Could momentarily stopping/releasing one directly-powered 5V fan
contribute to an undervoltage event? Physically plausible, yes.** A
small DC fan's rotor draws elevated stall current while prevented from
turning, and a restart-from-stall current spike when released is a
real, well-understood mechanism for brushless DC motors - on an
already-marginal 5V rail with little headroom, a transient of even
this small magnitude could plausibly tip an already-close-to-threshold
rail across the line for a moment.

**Is it the explanation for the chronic condition? No - not
established, and the evidence argues against it being the primary or
sole cause.** Undervoltage was observed continuously for ~19 minutes
at this boot's start, and again during the unexplained 16:09-16:10
oscillation, with **no fan manipulation known to have occurred at
either time** (the operator's account describes occasional, brief,
past finger-stops - not an ongoing behavior during this round's
checks). **Undervoltage demonstrably occurs independent of fan
manipulation** on this Pi, both today and across every prior
documented episode (Stage 29's finding, in particular, involved no
mention of fan interaction at all).

**Conclusion: fan-stalling is a plausible contributing/aggravating
transient on an already-marginal rail, not the root cause.** The
underlying chronic headroom problem (§4) exists independent of it. Per
instruction, this was **not tested by deliberately stalling a fan** -
this conclusion rests entirely on the timeline evidence already
gathered.

---

## 6. Does the ALFA materially worsen power integrity?

**No, evidence does not support that.** `0x50005` is identical - same
exact hex value - in every check performed before the ALFA was ever
purchased, immediately after it was first connected, throughout every
subsequent AP/association test on both bands, after this round's
reboot, and during this round's own checks. The one ALFA-time-
correlated event on record (the original insertion disconnect/SD-error/
USB-timeout cluster) occurred exactly once, at the moment of USB
enumeration - consistent with an inrush-current transient at hot-plug,
not sustained stress - and never repeated across dozens of subsequent
minutes of real 2.4GHz and 5GHz AP operation and multiple real WPA2
associations. **The chronic condition predates the ALFA and continues
identically whether or not it's attached or active.**

---

## 7. Filesystem/SD health

- Root filesystem (`/dev/mmcblk0p2`, ext4) mounted `rw,noatime`,
  confirmed writable by a direct write test this round.
- Zero ext4 errors, zero `I/O error` lines, zero read-only-filesystem
  transitions in this boot's `dmesg` - only the normal, expected
  `orphan cleanup on readonly fs` → `re-mounted ... r/w` sequence every
  clean boot produces.
- 105G free of 115G (5% used) - ample headroom.
- No SD/eMMC-specific health telemetry is available on this card
  (`life_time`/`pre_eol_info` sysfs attributes, which some eMMC devices
  expose, don't exist for this consumer microSD card; `mmc-utils`/
  `smartctl` aren't installed - not installed this round, since a
  package install requires explicit operator go-ahead per this
  project's own rule, and wasn't necessary to reach a clean-storage
  conclusion here). **Honest limit, not filled in with a guess.**
- **No offline `fsck` was run** - the filesystem is currently mounted
  and shows no evidence warranting one. If ever warranted, that stops
  at an operator gate per instruction (unmounting the root filesystem
  live is itself a disruptive, gated action) - not applicable this
  round.

**Conclusion: storage is currently healthy.** The one prior SD-I/O
event remains isolated to the single original ALFA insertion moment,
not a sign of ongoing or worsening storage trouble.

---

## 8. What the operator needs to physically check - not guessed here

To narrow §4's ranking further, please read (no test/replacement
needed for this step, just reading labels):

1. **The wall brick itself:** its printed output rating - look for
   "Output: 5V⎓___A" (or similar) on the brick's own label. Note the
   exact number, and whether it's a generic/unbranded adapter or a
   name-brand/Raspberry-Pi-specific one.
2. **The cable:** its approximate length, and whether it's a cable that
   came bundled with a phone/generic charger (often thinner-gauge,
   sized for lower-current phone charging, not Pi-level sustained
   current) versus one sold/labeled specifically for Raspberry Pi use.
3. **The micro-USB connector on the Pi itself:** a visual check for
   any looseness, bent pins, or visible wear - no need to unplug/
   replug to check this, just look.

This is read-only information gathering, not a physical change - no
operator gate needed for this specific step, but the *next* step
(§9/§12) does need one.

---

## 9. Safest next physical step, if the operator wants to proceed

**The standard, most diagnostic control test: swap in a genuine
Raspberry-Pi-specific power supply and cable (rated 5.1V/2.5A official
supply, or equivalent well-reviewed Pi-specific supply) with nothing
else changed, and recheck `vcgencmd get_throttled` after normal
operation resumes.** This isolates the supply/cable variable cleanly
(A/B test), rather than changing the cable alone or the brick alone
first if only one replacement is available - though if the operator
already owns a known-good Pi-specific cable separately from a known-
good Pi-specific brick, replacing them **one at a time**, waiting
between each, would make the specific culprit (brick vs. cable)
interpretable, per instruction to change one controlled variable at a
time.

**This document does not perform this test or ask the operator to buy
anything** - per instruction, this is reported as the recommended next
step, gated on the operator's own decision to act on it. See §14 for
the exact operator actions this stops at.

**Do not treat "seems to be a name-brand fast charger" as sufficient**
- a phone-fast-charging brick's marketing claims (wattage, "fast
charge") do not guarantee steady 5.1V under the specific current draw
profile a Pi 3B+ plus an active USB Wi-Fi adapter plus GPIO loads
presents, which is a different load shape than phone charging.

---

## 9a. Cable A/B test - completed, negative result (2026-09-03)

**The power source was identified**: a genuine Apple iPad 12W wall
brick (well-regulated by reputation, an unlikely culprit on its own),
paired with an old, unknown-gauge Samsung phone micro-USB cable -
exactly the profile this document's own evidence pattern pointed
toward (phone-charging cables are commonly thinner-gauge than sustained
Pi-level current draw needs, and age/wear adds resistance). Per
operator instruction, the cable was isolated as the first controlled
variable: **replaced only the cable** (shortest, highest-quality,
lowest-resistance micro-USB cable available), same brick, same loads
(fans/OLED/ALFA) attached throughout, nothing else changed.

**Result, independently verified after reboot - not inferred from "it
booted":**

| | Old cable | New cable |
|---|---|---|
| `vcgencmd get_throttled` | `0x50005` | `0x50005` (unchanged) |
| Bits 0/2 (current under-voltage/throttling) | SET | **still SET** |
| Core voltage / temp | nominal | nominal (unchanged) |
| Timeline through a matched ~19-minute window | continuous assertion, then repeated rapid detect/normalise oscillation (multiple flips within seconds, recurred more than once) | continuous assertion since boot, **zero** oscillation observed through the same window |
| USB/mt76/SD/ext4 errors | none (beyond the one historical insertion event) | none |
| Production `wlan0`/services/regulatory domain | unaffected | unaffected |

**Active under-voltage was not resolved by the cable swap.** The one
genuine difference observed - no rapid oscillation on the new cable
through a matched window - is real and worth recording honestly, but
is not itself a fix: bits 0/2 stayed continuously set the entire time,
which is at least as serious as the old cable's pattern at the same
point (the old cable's own first ~19 minutes were also continuous
before its oscillation began - so this comparison point alone doesn't
yet distinguish "better" from "the same, just observed for a shorter
total window"). **Whether the new cable's steadier-but-still-active
pattern represents a real partial improvement or is within the range
of this system's normal variability is not established from one
reboot's worth of data.**

**Conclusion, per the operator's own pre-declared plan:** the cable is
no longer the leading unexamined variable - it has been tested and
ruled out as a *sufficient* fix (it may still be a *contributing*
factor; that's not established either way). **The next controlled
variable is the supply itself** (the Apple 12W brick), per the
operator's own instruction - not acted on without the operator's
explicit go-ahead, and not performed as part of this round.

---

## 10. Fan noise observation - power vs. thermal vs. mechanical

The operator separately noticed the fans sounding louder after a power
cycle, and one briefly making an unusual noise. Addressed on its own
terms, not folded into the electrical finding above:

- **These fans have no software/PWM control with the current direct-
  to-5V/GND wiring** - confirmed from the operator's own account this
  round. Nothing PirateBox's software (OLED daemon, status helper, or
  anything else) does can command these fans faster, slower, or
  differently in any way. Any change in fan sound is not software-
  caused.
- **No system evidence suggests overheating** is driving fan behavior -
  temperature stayed at 40-41°C throughout this round, well below any
  throttling threshold, with zero thermal-limit kernel messages.
- A fan sounding different immediately after a power cycle (spin-up
  transient, or simply a different rotational starting position each
  time) is a normal, unremarkable thing for a simple always-on fan to
  do, and isn't itself evidence of a fault.
- **A genuine mechanical issue (bearing wear, blade rub, a rattle) is a
  separate concern from the 5V rail diagnosis in this document** -
  nothing gathered this round connects the two. If the unusual noise
  recurs or worsens, that's worth the operator's own physical
  inspection, independent of the power-path work here - not something
  this round investigated further, correctly out of scope for an
  electrical diagnosis.

---

## 11. Future enclosure power architecture - kept in mind, not implemented

This diagnosis deliberately avoids conclusions that would lock the
project into a bad future architecture:

- Whatever the current wall-brick/cable culprit turns out to be, **a
  clean, adequate 5V rail matters even more once a UPS/battery power
  path is added** (`docs/POWER-UPS-DESIGN.md`) - a marginal upstream
  supply feeding into seamless-switchover UPS hardware doesn't fix a
  headroom problem, it just relocates where the sag happens.
- Automatic battery failover, environmental/temperature monitoring,
  battery/power-bank temperature, safe shutdown-on-condition, and
  automatic restart-when-safe all remain **future** requirements
  documented in `docs/POWER-UPS-DESIGN.md` - nothing here implements
  any of them, and nothing here should be read as having decided their
  design.
- The AWUS036ACM's own future production power budget
  (`docs/POWER-UPS-DESIGN.md` §2.2) still needs to be sized against
  *whatever* supply eventually proves adequate for the Pi alone - this
  diagnosis doesn't change that requirement, it establishes whether
  today's supply even clears the Pi-alone bar first.

---

## 12. Power-aware ALFA migration gate - status

Restating `docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md` §8/§16's gate:
**still not met.** This round adds real diagnostic depth (the precise
bit semantics, the oscillation pattern, the ruling-out of fan-stall as
sole cause, the ALFA-independence confirmation) but does **not**
constitute the extended multi-hour, multiple-simultaneous-client,
sustained-ordinary-traffic soak with continuous monitoring that gate
requires - and, more fundamentally, **that soak shouldn't be run on a
supply already showing a chronic headroom deficit**, per this round's
own instruction not to run a heavy/sustained test on a known-
undervolting supply. **The logical next step before that soak is even
worth attempting is resolving what this document found** - not
proceeding to the soak on the current supply and hoping for the best.

---

## 13. What remains genuinely uncertain

Recorded honestly, not converted into false certainty:

- **The cable has been ruled out as a *sufficient* fix (§9a)** - active
  under-voltage remained after replacing it. Whether it was a
  *contributing* factor (i.e. whether the brick alone, with the old
  cable, would have been even worse) was not isolated - the test
  compared old-cable-alone-data against new-cable-alone-data, not a
  fully controlled brick-only baseline.
- **The exact root cause between the brick and any remaining connector/
  contact issue** is not proven - only ranked by evidence (§4), now
  narrowed by ruling out the cable. Only a physical brick-swap A/B test
  can narrow this further, per the operator's own next-step plan.
- **Whether the new cable's steadier (non-oscillating) but still
  continuously-active pattern is a real partial improvement or normal
  run-to-run variability** is not established from one reboot's data
  (§9a) - would need multiple comparable boots on each cable to say
  with confidence.
- **The 16:09-16:10 oscillation's specific trigger** on the old cable
  remains unexplained - no correlated dmesg event, no known operator
  action at that exact moment.
- **Whether the SD card itself has any latent wear** from repeated
  power-sag exposure over the project's history is not measurable with
  the tools available on this system.
- **Whether a genuinely known-good Pi-specific supply would fully
  resolve this** is a prediction based on the evidence pattern, not a
  proven fact until actually tested.
