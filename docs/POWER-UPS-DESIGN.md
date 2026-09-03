# Power / UPS Design Requirements (Stage 12)

**Status: REQUIREMENTS DOCUMENT ONLY.** No power/UPS hardware has been
selected or purchased as part of this document, and nothing here is
implemented. This defines what future power hardware must satisfy, for
the operator to evaluate candidate products against later - it does not
pick one.

**For the current wall-power path's chronic undervoltage condition
(`0x50005`) - root-cause diagnosis, event timeline, failure-class
ranking, and the fan-stall question - see
`docs/POWER-INTEGRITY-DIAGNOSIS.md`.** That document is about *today's*
actual supply; this one is about *future* UPS/battery requirements. A
future UPS sits downstream of whatever supply issue that document
finds - it doesn't substitute for resolving one.

## 1. The two operating scenarios this hardware must support

**At home (stationary):**
```
wall power -> UPS/power-path hardware -> Raspberry Pi 3 B+ + external AP adapter
```
Battery stays charged and available. When mains fails: the Pi keeps
running, the AP keeps broadcasting, there is **no reboot and no
interruption to Wi-Fi clients already connected**, for as long as battery
capacity allows.

**Leaving home (portable):** the same *already-running* box gets
unplugged from mains and carried in a backpack or vehicle - power source
changes from wall to battery-only, but the Pi should **not** need to
reboot, and nothing about the transition should be disruptive to whatever
it was doing.

Both scenarios reduce to the same underlying requirement: **the load
(Pi + AP) must never see an power interruption when the source changes**,
whether that change is "mains failed" or "operator unplugged it
deliberately." This is why the requirements below focus heavily on true
seamless power-path behavior rather than treating "battery backup" as a
simple add-on.

## 2. Hard requirements for candidate hardware

### 2.1 True seamless power-path (UPS) behavior - not just "has a battery"

This is the single most important requirement and deserves explicit
evaluation, not an assumption. Many cheap "UPS HAT" products for the Pi
use a simple relay/MOSFET switchover between mains and battery that takes
measurable time (anywhere from a few milliseconds to noticeably longer) -
during that gap, the Pi sees a voltage dip. A Raspberry Pi has **no
internal battery or supercapacitor buffering** and is known to brown out
or reset from even brief undervoltage - this project's own operational
history (see `OPERATIONAL-DECISIONS.md`'s Wi-Fi/power notes) already
treats undervoltage as a real, observed failure mode on this hardware
family, not a theoretical concern.

**Evaluation criterion:** look specifically for hardware described as
"true UPS," "seamless switchover," or using genuine **power-path
management (PPM)** - a charging/power IC that blends battery and mains
output continuously rather than switching between two discrete sources.
Several Pi UPS HAT products on the market explicitly advertise a
near-zero switchover time using this kind of chip; others don't and
shouldn't be assumed equivalent. This needs to be verified against each
candidate product's actual specification, not inferred from marketing
language like "UPS" alone, which gets applied loosely across very
different real designs.

### 2.2 Sufficient output current for BOTH the Pi and the external AP

Most Pi-focused UPS HATs are sized for the Pi alone (typically rated
somewhere around 2-2.5A combined output). This project's external AP
adapter (the ordered ALFA AWUS036ACM, MediaTek MT7612U) is a separate USB
load on top of the Pi's own draw, and higher-power USB Wi-Fi adapters -
especially under active transmit load - can draw meaningfully more
current than casual USB peripherals. **Total system budget (Pi + AP,
combined, under real load) needs to be sized generously above whatever a
"Pi-only" UPS HAT is rated for** - check the AP adapter's actual
datasheet/spec for its real current draw when evaluating hardware, rather
than assuming a Pi-sized UPS HAT is automatically adequate. Undersizing
this is a likely, easy-to-miss failure mode if a Pi-only UPS product is
picked without checking this specifically.

### 2.3 No output interruption when AC appears or disappears

Restated explicitly as its own testable requirement (not just implied by
2.1): plugging mains power back in after a battery-only period must be
**exactly as seamless** as losing it was. Some designs handle
battery-to-mains cleanly but introduce a glitch on the reverse transition
(mains returning) - both directions need to be evaluated, not just the
"power loss" direction, when real hardware is tested.

### 2.4 Safe battery charging

Whatever cell chemistry is chosen (most Pi UPS HATs use Li-ion or LiPo)
needs a proper charge-management IC providing: correct CV/CC charge
profile for that chemistry, over-voltage/over-current/over-temperature
protection, and cell balancing if the pack uses more than one cell in
series. This is a baseline safety requirement for any lithium battery
product, not something specific to this project - flagged here so it's
an explicit item checked against a candidate product's spec sheet, not
assumed.

### 2.5 Thermal considerations

The eventual rugged/portable enclosure (mentioned as this project's
long-term physical goal) will hold the Pi, the AP adapter, and a battery
pack together in a smaller, less-ventilated space than an open desk
setup. Two things compound here: (a) the AP adapter itself can run warm
under sustained transmit load, and (b) a power-path IC generates the most
heat *while simultaneously charging the battery and powering the load* -
the exact "at home, plugged in" scenario this design centers on, meaning
this isn't a rare edge case to size for, it's close to the default
operating condition. **Enclosure ventilation/thermal design is an
explicit requirement for whenever the physical enclosure is built**, not
solved by this document - flagged here so it isn't discovered late.

### 2.6 AC-present / battery-state detection, if practically available

Not a hard requirement (many simple UPS HATs don't expose this), but
**worth actively favoring** when comparing candidates: some Pi UPS HAT
products expose battery percentage, voltage, and/or an AC-present signal
over I2C (commonly via a fuel-gauge IC) or a GPIO pin. If chosen hardware
provides this, it plugs directly into the OLED design already documented
in Stage 11 (`HARDWARE-INTEGRATION-DESIGN.md` §5) - the OLED daemon there
was already scoped to read "battery/mains status" as a future data
source, specifically anticipating this. If chosen hardware does *not*
expose this, the OLED simply omits that line - never a blocker, per
Stage 11's "OLED is informational only, never required" principle
carrying forward here too.

### 2.7 Portable operation

Physical requirements for the backpack/vehicle scenario: connectors
(USB, power) should be secure enough not to work loose from vibration or
incidental snags during transport; overall weight/size should stay
reasonable for backpack carry; nothing should depend on being on a flat,
stationary surface to function (e.g., no reliance on gravity-fed
connectors or components that could shift internally). Detailed physical
integration is an enclosure-design question for later, not resolved here
- listed as a requirement candidate hardware shouldn't actively work
against.

### 2.8 Safe shutdown considerations

Two related but distinct needs:
- **Manual, deliberate shutdown** - already covered by the hold-to-
  shutdown button concept in Stage 11 (`HARDWARE-INTEGRATION-DESIGN.md`
  §4), unaffected by whatever power hardware is chosen.
- **Automatic low-battery shutdown** - worth actively favoring in
  candidate hardware: some UPS HATs provide a low-battery signal (I2C or
  GPIO) the Pi can watch and use to trigger a clean `shutdown -h now`
  before the battery is fully depleted. This matters specifically for
  this project because an uncontrolled power loss mid-write risks SD-card
  filesystem corruption - the same category of concern this project
  already takes seriously elsewhere (e.g. the atomic temp-file-then-
  `rename()` pattern used for every JSON write throughout the Utility
  Library, and for `/tmp/piratebox/mode` itself). A battery genuinely
  running out is a slower, more predictable event than a wall-power
  failure and is exactly the case where a clean automatic shutdown is
  both possible and worth having, if the hardware supports signaling it.

## 3. Explicit design principle: Internet loss is NOT emergency

**This document formalizes something already true of the existing system
and states it as a standing requirement for anything built on top of it
going forward, including any future power/battery automation:**

Loss of Internet access, by itself, must **never** automatically trigger
Emergency Mode. The current mode system (`includes/mode.php`,
`piratebox_get_mode()`) already only ever changes via a trusted, explicit,
out-of-band actor - a human running `set_piratebox_mode.sh`, or (per
Stage 11's design) a future GPIO daemon reading a physical switch someone
deliberately flipped. Nothing about network state, Internet reachability,
or (per this stage) power/battery state should be added as an automatic
mode trigger. This isn't a gap to close later - it's a deliberate,
permanent boundary, because this PirateBox is *intentionally* offline
under completely ordinary circumstances (no Internet is the normal,
everyday state of this device, not a signal of anything going wrong) -
see the project's own Help page copy, which already makes this exact
point to visitors.

**The one acceptable future automatic behavior, if ever built:** a
**notification or suggestion**, never a forced mode change. Concretely,
if future power hardware exposes AC-present detection (§2.6), a
plausible future feature is the OLED showing something like "Running on
battery - consider Emergency Mode" as an advisory line, or an admin-page
notice to the same effect - informational only, requiring the same
human decision (physical switch, or a future software toggle) to actually
act on it. This mirrors exactly how the OLED itself is designed to be
informational-only and never load-bearing (Stage 11 §5) - the same
principle extended to power state.

## 4. What this stage deliberately does not do

- No specific UPS HAT, battery, or power-path product has been evaluated,
  selected, or purchased.
- No wiring, no code, no systemd service for power monitoring exists.
- No decision on battery chemistry/capacity has been made - that follows
  from picking real hardware against the requirements above, not the
  reverse.
- No automatic mode-switching behavior of any kind has been built, and
  §3 above states the boundary that will keep it that way even once real
  power-state telemetry exists.

## 5. Recommended next step

When the operator is ready to evaluate specific UPS HAT/power-path
products, do so against §2 as a checklist - particularly §2.1 (verified
seamless switchover, not just marketed as "UPS") and §2.2 (combined
Pi + AP current budget, checked against the AP adapter's real spec) as
the two requirements most likely to silently disqualify an otherwise
appealing product if skipped.
