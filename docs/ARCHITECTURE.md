# PirateBox Architecture & Project Philosophy

**Status: FORMALIZATION OF DESIGN PRINCIPLES. Nothing in this document
changes running behavior.** This document records the long-term
architecture, privacy/trust philosophy, and self-awareness model this
project is deliberately building toward. It does not implement any of
it - no new service, sensor, authentication system, discovery
mechanism, UI, or GPIO behavior was added alongside this document. Where
a section describes something not yet built, it says so explicitly.
This is the durable "why the shape of things is the way it is" record
for the project's long-term direction, the same role
`docs/OPERATIONAL-DECISIONS.md` plays for individual decisions -
`CLAUDE.md` routes here for architecture/identity questions rather than
duplicating this content.

**Concrete capability inventory (what's actually installed vs. planned
vs. candidate vs. rejected) lives in `docs/CAPABILITY-REGISTRY.md`, not
here.** This document is semantics and principles; that one is state.

> **BUILD TODAY'S AFFORDABLE PIRATEBOX INSIDE TOMORROW'S ARCHITECTURE.**

PirateBox is currently maintained, owned, configured, and operated by
its creator. That is today's reality, and it legitimately shapes
today's configuration - but it must not become a permanent
architectural assumption. The current configuration describes THIS
PirateBox TODAY. It does not define what PirateBox must be forever.
This document exists to keep that distinction real as the project
grows, not just asserted once and forgotten.

---

## 1. Project identity - a field utility node

The original PirateBox identity remains fundamental and unchanged:

- independent local Wi-Fi network
- offline/local-first operation
- files/community/information
- useful without outside infrastructure
- understandable and usable by ordinary clients

This particular project is evolving into a broader **privacy-conscious
field utility node** on top of that foundation - not replacing it.
Everything in `README.md`'s feature list is still exactly what it says;
this document is about the shape the project grows into around that
core, not a redefinition of it.

**The Swiss Army knife analogy:** PirateBox is one Swiss Army knife in
the pocket. Sometimes it's the only tool available. Sometimes there are
several other tools nearby - phones, laptops, other Raspberry Pis,
ESP32/microcontroller projects, GNSS receivers, environmental sensor
nodes, SDR receivers, ham-radio equipment, external radios, weather
instruments, purpose-built field electronics, and things not yet
imagined. PirateBox should not try to permanently contain every
possible capability. It should be fully capable by itself, and able to
cooperate with explicitly supported external/companion equipment when
useful. **This is a way to prevent feature bloat, not justify it** - see
§2's Core/Operational/Optional layering and §3's companion-device model,
both of which exist specifically to keep that promise honest as
capabilities are added.

## 2. Three architectural layers

Every capability this project has, is building, or might someday add
belongs to exactly one of three layers. This is the primary tool for
keeping PirateBox simple as it grows.

### Core

The things that make PirateBox fundamentally PirateBox: the AP/network,
the offline site, files, community features (chat/guestbook/bulletin),
storage, basic safe operation, and shutdown/basic status. **Core should
have as few dependencies as practical.** Everything currently live on
this device is Core: nginx/PHP/hostapd/dnsmasq, the file-share/chat/
guestbook/bulletin app, Normal/Emergency Mode, Travel Mode, and the
physical shutdown button (a safety primitive, not an add-on capability).

### Operational

Capabilities that improve reliability, usability, maintainability, or
operator awareness: OLED, RTC, temperature monitoring, power/battery
monitoring, fan/thermal safety, undervoltage awareness, connection
statistics, physical controls, and other health/status instrumentation.
These may substantially improve PirateBox, but **Core should generally
remain usable when an Operational capability fails.** Field Tools
(`docs/FIELD-TOOLS-DESIGN.md`) is Operational in spirit - it's a field
instrument, not part of what makes the AP/site/community features work.

### Optional / Field Capabilities

Examples: GNSS, environmental sensing, air quality, UV/light, IMU/
orientation, ToF/proximity, sound measurement, lightning detection,
radiation measurement, external isolated I/O, SDR, radio integrations,
companion sensor nodes, and other specialized field tools. **These must
not become accidental Core dependencies.**

### The rule that holds the layers together

> **OPTIONAL CAPABILITY FAILURE MUST DEGRADE THE PIRATEBOX, NOT DISABLE
> THE PIRATEBOX.**

Concretely: GNSS dies -> location/time-from-GNSS disappears. A CO2
sensor dies -> CO2 reading unavailable. OLED dies -> AP/site remain
operational (already true today - the OLED doesn't exist yet, and
nothing about the AP/site depends on it ever existing). RTC dies ->
time confidence degrades / the existing fallback applies (this is
already the live behavior - see `docs/RTC-TIME-READINESS-DESIGN.md` and
`includes/fieldtools_time.php`'s `piratebox_get_time_source_status()`,
which reports an honest "unavailable" rather than a guess). An external
radio dies -> fall back to the documented alternative where one exists
(the built-in `wlan0` AP is already exactly this fallback for the
not-yet-tested ALFA AWUS036ACM - see `docs/OPERATIONAL-DECISIONS.md`,
"Wi-Fi adapter notes / planned hardware"). A sensor bus dies -> affected
sensors disappear/degrade, not the whole device. A power monitor dies
-> telemetry disappears; **it must not itself remove power.** Automation
gets confused -> manual operator authority remains (already the pattern
`set_piratebox_mode.sh`/Travel Mode's manual toggle follow, and the
explicit design goal for GNSS-driven automatic Travel Mode in §7).

## 3. Integrated, attachable, and companion capabilities

Not every useful tool belongs permanently inside the enclosure. A
capability or device may be:

- **Integrated** - permanently or semi-permanently installed in
  PirateBox (e.g. the GPIO25 shutdown button today; a future OLED/RTC).
- **Attachable** - temporarily connected when needed, such as USB/
  serial/GPIO equipment (e.g. a USB SDR plugged in for a session).
- **Network companion** - an independently powered device communicating
  over the PirateBox LAN or another explicitly supported local
  interface (e.g. a future ESP32 sensor node, a remote weather
  instrument).
- **Operator device** - a phone/laptop/etc. that consumes PirateBox
  information or administers permitted functions while remaining an
  independent device the operator owns and controls separately.

Future companion equipment could include GNSS receivers, RTL-SDR/other
SDR, ham-radio interfaces, external radios, ESP32 sensor nodes, remote
weather instruments, external probes, another Pi, or specialized
homemade field electronics. **This document does not design a generic
plugin framework.** It establishes the concept and constraints only -
see `docs/CAPABILITY-REGISTRY.md` for how specific candidates are
tracked, and §9 below for the discovery states a future implementation
would need to distinguish.

**Companion devices must be able to disappear without breaking Core.**
This is the same rule as §2's layering, extended to things that aren't
even physically part of the box.

## 4. Physical modularity

A long-term design goal, not a current implementation: avoid opening
the enclosure in two years and finding an impossible-to-diagnose nest
of permanent Dupont wiring. Prefer, as capabilities are actually built:

- detachable/labeled harnesses
- documented connectors
- service loops
- module/branch numbering where useful
- organized power distribution
- organized I2C/GPIO/UART/SPI/USB boundaries
- replaceable modules
- isolation where appropriate
- the ability to disconnect an optional module without dismantling Core

A future internal distribution/interface/backplane board may eventually
make sense. **No such board is designed or built as part of this
document** - none of this project's existing docs define one either, so
there is nothing to reconcile here, only a placeholder for future work.
One specific idea worth recording now, before it's needed: a
PCA9548A/TCA9548A I2C multiplexer is useful not only for resolving
duplicate I2C addresses (several candidate sensors in
`docs/CAPABILITY-REGISTRY.md` may share an address) but potentially for
selectable branches and some degree of failure containment/diagnostic
isolation - one wedged/shorted sensor on its own mux branch shouldn't be
able to take the whole I2C bus down. Noted as a candidate concept for
when I2C fans out beyond the OLED+RTC pair already planned on it; not
selected, purchased, or designed now.

**Before installing any future capability, work through this
checklist** (also recorded per-capability in
`docs/CAPABILITY-REGISTRY.md`):

```
PURPOSE
INTERFACE
POWER
PHYSICAL LOCATION
SOFTWARE OWNER
FAILURE MODE
UI EXPOSURE
```

A capability may be architecturally **RESERVED** without being
purchased or implemented - this is exactly what GPIO24/GPIO27 already
are (see `docs/PHYSICAL-CONTROL-UX-DESIGN.md` §2: wired, unassigned,
"don't invent a job for a button that doesn't have one").

## 5. Capability provenance - document *why*, not just *who*

Capability/hardware documentation should make it possible to
understand: what's installed, why it's installed, what role it
currently serves, whether that role is required, whether it's
replaceable, what fallback exists, and what happens when it fails. This
is a convention for **future** documentation to follow, applied going
forward - it does not retroactively rewrite existing docs' rationale
(which, checked while writing this document, already mostly follows it
- see e.g. `docs/HARDWARE-INTEGRATION-DESIGN.md` §2's wiring table,
which already explains *why* each pin was chosen, not just which pin).

Bad: *"Don't use GPIO25 because Moose said so."*

Good: *"GPIO25 is currently assigned to the momentary shutdown control
and was selected while preserving I2C pins used by display/RTC. Verify
current hardware before reassignment."* (This is, in substance, exactly
what `docs/HARDWARE-INTEGRATION-DESIGN.md` §2 already says.)

Example of the target shape for a hardware entry (illustrative, not a
new claim about real state beyond what `docs/CAPABILITY-REGISTRY.md`
already establishes):

```
AWUS036ACM
Role: Preferred primary Wi-Fi AP (candidate - not yet tested)
Status: Ordered, not yet arrived/tested
Core requirement: No - built-in wlan0 remains primary until proven
Fallback: built-in wlan0 (today's actual production AP)
Replaceable: Yes
Configured role: current operator's evaluation plan
```

## 6. Privacy-first, not exposure-incapable

> **PIRATEBOX IS PRIVACY-FIRST, NOT EXPOSURE-INCAPABLE.**

Default behavior should minimize unnecessary collection, unnecessary
persistence, unnecessary disclosure, and unnecessary transmission. But
PirateBox is a **tool**. There may be legitimate situations where the
operator deliberately wants normally-private information exposed.
Therefore:

> **INFORMATION IS EXPOSED BECAUSE THE OPERATOR DELIBERATELY CHOSE A
> USEFUL EXPOSURE, NOT MERELY BECAUSE THE BOX POSSESSES THE
> INFORMATION.**

Exposure should be explicit, understandable, scoped, reversible, and
privacy-safe by default. **Emergency Mode must not automatically mean
"publish everything."** This is already true today, not just a future
goal - Emergency Mode (`docs/OPERATIONAL-DECISIONS.md`, "Emergency
Mode: software presentation-mode foundation") is a *presentation*
reorder only, and Travel Mode (`docs/TRAVEL-MODE-DESIGN.md`) is the
*only* thing that suppresses region-specific content, gated on its own
manual toggle, orthogonal to Normal/Emergency. An emergency may be
exactly when an operator desperately wants to publish location, or
exactly when they desperately do not - the software must not assume
which. This principle formalizes and generalizes what Travel Mode
already does for one specific case (home-region content); it applies to
every future capability that could expose something sensitive (GNSS
position chief among them - see §7).

## 7. GNSS / location privacy

**No GNSS hardware exists on this device today** (see
`docs/CAPABILITY-REGISTRY.md` - CANDIDATE, not owned). This section is
forward design for if/when it's added, not a description of current
behavior.

GNSS is the clearest example of §6's principle: PirateBox may **know**
where it is without automatically **telling** anyone where it is. Exact
position is sensitive telemetry by default. Design intent for a future
GNSS integration:

- exact current position: operator-only by default
- no public exact position by default
- no location history by default
- no cloud transmission
- no hidden coordinate persistence
- no automatic embedding into exports/QR codes/public pages
- Travel Mode remains privacy-safe (a future GNSS integration must not
  create a new leak path around it)
- manual operator authority remains primary

**Separate GNSS-derived TIME from GNSS-derived POSITION.** A GNSS
receiver may be extremely useful for accurate UTC (directly relevant to
`docs/RTC-TIME-READINESS-DESIGN.md`'s clock-trust problem) even while
coordinate exposure remains completely disabled - these are two
independent outputs of the same hardware, and disabling one must not
require disabling the other.

Potential future exposure states (**not implemented, conceptual only**):

- **Private** - exact position available internally/operator-only.
- **Approximate** - only deliberately coarse/manual region-level
  information exposed.
- **Public** - exact current coordinates intentionally exposed.

Public location sharing must be an explicit operator choice, not an
automatic consequence of installing GNSS hardware or enabling Emergency
Mode. If GNSS is eventually used for automatic Home/Travel detection:
comparison should happen locally, avoid building a location history,
discard coordinates after the necessary determination where practical,
keep manual Travel Mode authoritative over any automatic guess, and
introduce no cloud dependency.

## 8. Physical / operational privacy

Privacy is not only about stored data. PirateBox may eventually
physically contain a computer, storage, multiple radios, antennas,
GNSS, environmental sensors, unusual electronics, a display, and
buttons - it may look more interesting than it actually is. Account for
operational discretion. Concept for a future indicator/behavior policy
(**not implemented now** - no OLED exists yet to apply it to):

- **Normal:** quiet. Display may sleep/dim (already the plan in
  `docs/PHYSICAL-CONTROL-UX-DESIGN.md` §4). Subtle indicators. No
  gratuitous broadcasting of sensitive status.
- **Attention:** display/status may wake or change.
- **Warning:** low storage, temperature, power problem, undervoltage,
  degraded capability - visible but not obnoxious.
- **Critical:** threat to hardware/data/reliability - allowed to be
  obvious, and protective action allowed where explicitly designed (the
  GPIO25 shutdown button is exactly this kind of allowed protective
  action today, just operator-triggered rather than automatic).

A future Quiet/Stealth policy may suppress non-critical indicators, but
**must never suppress required safety behavior.** Not implemented now.

## 9. Progressive disclosure in the UI

A UI hierarchy to preserve as future status/self-description surfaces
are built (**none of this is implemented now** - it's the target model
for pages like a future "About This PirateBox," building on the pattern
the existing Stats page and admin page already follow informally):

```
ANSWER -> USEFUL DETAIL -> TECHNICAL DETAIL -> DIAGNOSTICS
```

Ordinary/public users should not be presented with an airplane cockpit.
Illustrative example (not a real page, not implemented):

```
PUBLIC:      PirateBox is operational.
             Weather: 71F / 46% RH

OPERATOR:    Wi-Fi       Good
             Storage     Good
             Power       Good
             Time        Trusted
             Sensors     4/5
             Companions  2

ADVANCED:    Primary AP: AWUS036ACM
             Fallback: wlan0 ready
             RTC: DS3231 synchronized
             GNSS: 3D fix / position PRIVATE
             ENV-02: stale

DIAGNOSTICS: USB IDs, interfaces, I2C addresses/branches, drivers,
             raw readings, timestamps, service states, dependencies
```

## 10. Self-awareness

Not AI consciousness, and not needless telemetry. It means PirateBox
should maintain an accurate, inspectable understanding of itself and
its currently useful environment.

> **PIRATEBOX SHOULD KNOW, AS FAR AS PRACTICAL AND USEFUL: WHAT IT IS,
> WHAT IT HAS, WHAT IT CAN DO, WHAT IT IS CURRENTLY DOING, WHAT IT CAN
> CURRENTLY USE, WHAT IT IS EXPOSING, WHAT IS DEGRADED, AND WHAT IT
> DOES NOT KNOW.**

The device should eventually be able to answer (**future goal - the
questions below are the target shape of a future self-description
surface, not a description of anything built now**):

- **What am I?** Hardware platform, software/version, current
  configuration/profile, storage.
- **What do I have?** Radios, OLED, RTC, sensors, buttons, interfaces,
  attached companion devices.
- **What can I do?** Available capabilities, not merely installed
  packages.
- **What am I doing?** AP state, public services, Normal/Emergency,
  Travel Mode, active integrations, privacy/exposure states.
- **How am I doing?** Temperatures, power quality, storage, service
  health, radio health, sensor health, time confidence.
- **What can I use right now?** e.g. a compatible GNSS receiver
  present, a known ESP32 node available, an SDR connected, a secondary
  Wi-Fi interface available.
- **What am I exposing?** Public services, operator-only information,
  whether location is shared, relevant active radio behavior, other
  intentionally exposed sensitive capability states.
- **Who currently has authority?** Public, recognized operator, owner/
  admin, recovery state (see §14).
- **How can I be maintained?** Local docs, wiring assignments, software
  source, hardware roles, replacement information, known caveats.
- **What don't I know?**

That last question matters as much as any other. PirateBox must
distinguish, for example:

```
GNSS: NOT INSTALLED | PRESENT BUT UNSUPPORTED | DISABLED | FAILED |
      AVAILABLE / NO FIX | AVAILABLE / FIX | STALE | UNKNOWN
```

`POWER GOOD` is not equivalent to `POWER MONITORING UNAVAILABLE`. `TIME
TRUSTED` is not equivalent to `NO RTC DETECTED`. **This distinction
already exists in real, shipped code today** -
`piratebox_get_time_source_status()`
(`includes/fieldtools_time.php`, see `docs/FIELD-TOOLS-DESIGN.md` §4)
returns an explicit `available`/`stale` state with `null` fields rather
than fabricating a boolean when it can't honestly answer, precisely
because a real bug (an `open_basedir` restriction silently producing a
false "not detected") demonstrated why this matters. That incident is
the concrete proof this principle is worth formalizing, not a
hypothetical: **prefer an honest UNKNOWN/UNAVAILABLE/STALE state over
confidently inventing a healthy state**, everywhere, going forward.

## 11. Fact vs. configuration vs. inference vs. intent

Self-awareness should distinguish different kinds of knowledge about
the same capability. Example (illustrative):

```
Hardware detected:  AWUS036ACM
Configured role:    Primary AP
Current state:      Active
Fallback:           built-in wlan0
Required for Core:  No
Operator intent:    Preferred PirateBox radio
```

Or for GNSS:

```
Receiver:                 PRESENT
Fix:                      3D
UTC source:                AVAILABLE
Position:                  AVAILABLE
Position persistence:      DISABLED
Public position exposure:  PRIVATE
Travel Mode use:           ENABLED
```

Merely possessing a position does not imply sharing it. The relevant
distinct kinds of knowledge, worth keeping separate wherever a future
implementation records capability state:

- **observed fact** (what's physically detected)
- **configured role** (what the operator set it up to do)
- **inferred capability** (what the software concludes is possible)
- **operator intent** (what the operator wants, even if not currently
  achievable)
- **current state** (what's true right now)
- **desired state** (what should be true)
- **confidence/staleness** (how much to trust the current state)
- **privacy/exposure state** (what's actually being shared, to whom)

**No database/schema is designed for this now.** This section defines
semantics, not implementation - a future capability-state store (see
`docs/CAPABILITY-REGISTRY.md`'s own note on this) can adopt these
categories when it's actually built.

## 12. Current-state awareness, not surveillance

> **PREFER CURRENT-STATE AWARENESS OVER HISTORICAL SURVEILLANCE.**

PirateBox may know "4 clients are currently connected" without storing
every MAC address - this is not aspirational, it's the live, shipped
design of the connection-statistics feature
(`docs/OPERATIONAL-DECISIONS.md`, "Post-Stage-32: Privacy-Preserving
Connection Statistics"): only small aggregate hourly counts persist,
never a MAC address, IP, or hostname. This principle **generalizes that
existing decision** to every future capability: PirateBox may know "I
currently have a GNSS fix" without storing a location trail; "ENV-02 is
currently available" without permanently logging every device that's
ever appeared; "external AP failed and fallback is active" without
automatically maintaining months of forensic telemetry.

Some limited history is genuinely useful for maintenance - temperature
maximum, undervoltage events, storage warnings, capability failures,
restart/recovery events. **But history should be deliberate.** For any
future retained telemetry, define explicitly:

- **WHAT** is retained
- **WHY**
- **FOR HOW LONG**
- **WHO** can see it

exactly the four questions the connection-statistics design already
answers for its own data. Apply the same discipline to anything new.

## 13. Graceful self-diagnosis

A future design goal, not implemented: PirateBox should eventually be
able to explain deterministic problems using known system state - not
"AI magically diagnoses everything," but a direct readout from explicit
capability/dependency/state knowledge (§10/§11). Illustrative examples
of the target shape:

```
DEGRADED: External Wi-Fi radio unavailable
PirateBox moved to built-in radio. Public services remain available.
Range/performance may be reduced.
Expected device: AWUS036ACM
Core impact: none.
Suggested check: USB connection/power.
```

```
TIME CONFIDENCE LOW
RTC unavailable at startup and no trusted time source has been
acquired. Messages continue working, but displayed timestamps may be
inaccurate.
```

```
OUTSIDE TEMPERATURE STALE
Last reading from ENV-02 was 18 minutes ago.
```

Nothing here is implemented. It's the target shape a future status/
diagnostics surface should aim for, once enough of §10/§11's knowledge
actually exists to derive it from.

## 14. Trust is not binary

If PirateBox is open and independent, how does it know who the
operator is? Today, the creator is owner/operator/maintainer - that's
today's real state, not a permanent architectural assumption (see §18).
A Wi-Fi visitor is not automatically an operator. Physical access for a
few minutes should not automatically mean ownership. The device may
someday be gifted, sold, inherited, or found. A legitimate future owner
must not require the original owner's cloud account or presence
forever.

Four distinct levels, formalized here for the first time in this
project (**none implemented - no authentication/authorization system of
any kind exists today beyond the admin page's existing password, which
this section does not change**):

- **Access** - ability to use public PirateBox services (files, chat,
  guestbook, bulletin, Field Tools, reference library - what any
  connected visitor already gets today with zero login).
- **Operation** - ability to perform routine trusted operator actions
  (today's closest real analog: whoever knows the admin page's
  password, and this session's own narrow `sudo` automation for
  deploy/mode-switch).
- **Ownership / Administration** - ability to change trust/
  configuration/privacy/capability settings.
- **Recovery / Claim** - a deliberate physical/local process capable of
  superseding old ownership when the device genuinely changes hands or
  credentials are lost.

**Naming collision to avoid, flagged explicitly:** this "Recovery/
Claim" concept is *not* the same thing as Stage 16's existing "Recovery
Messages" / "Recovery/Lost Mode" concept
(`docs/OPERATIONAL-DECISIONS.md`, "Stage 16: Public PirateBox ID / Found
Device / Recovery System"; design-only, never built). That existing
concept is about a *physically lost* device announcing itself as
missing and inviting whoever finds it to message the *current* owner
back - it does not touch who has administrative authority at all. This
new "Recovery/Claim" concept is about *administrative authority
changing hands* when the device legitimately changes owners. They can
coexist without conflict (a found-and-returned device never needed an
ownership claim; a sold/gifted device might use both a "please return
if lost" label *and*, separately, an ownership-claim process for the
new owner) - but future work must keep the terms distinct, and should
consider renaming one of them (e.g. "Found Device Recovery" vs.
"Ownership Claim") once both are actually being designed together, to
avoid the collision this document is now flagging rather than quietly
creating.

**Do not implement authentication or recovery now.** This section
defines the distinction, not a mechanism.

## 15. Transferable ownership

> **PHYSICAL POSSESSION ALONE SHOULD NOT GRANT IMMEDIATE ADMINISTRATIVE
> AUTHORITY, BUT PERMANENT OWNERSHIP MUST REMAIN TRANSFERABLE WITHOUT
> DEPENDENCY ON THE ORIGINAL OWNER OR ANY EXTERNAL SERVICE.**

An offline box cannot determine whether long-term physical possession
means theft, gift, sale, inheritance, legitimate recovery, or abandoned/
found hardware. Cryptography cannot determine morality. The desired
model, in principle only:

- casual physical access != ownership
- remote Wi-Fi access != ownership
- current operator credentials remain meaningful
- deliberate physical recovery may eventually supersede prior ownership
- recovery should be intentionally difficult to trigger accidentally
- no mandatory cloud account
- no permanent creator backdoor
- no requirement that the original creator authorize every future
  transfer

Possible future recovery mechanisms might involve deliberate physical
sequences, boot-time actions, local recovery credentials, hardware
tokens, or paired devices. **None of these is chosen or implemented
here.** This section defines the semantics and security goals a future
mechanism must satisfy, deliberately before picking one.

## 16. Data-aware ownership transfer

A new owner should gain **the device**, not automatically gain **the
previous owner's secrets**. A future recovery/transfer process should
consider resetting: old operator credentials, paired operator trust,
private/home location configuration, trusted-home network identifiers,
sensitive integration credentials, GNSS exposure preferences (back to
privacy-safe defaults), and other private operator configuration -
while potentially allowing deliberate preservation of: public files,
bulletin/community content, public references, and non-sensitive device
documentation. Two conceptual options for a future design to weigh:
**Adopt/Preserve Public Data** vs. **Factory Transfer/Reset**. **Exact
destructive behavior is not defined here** - that needs careful future
design work evaluating the real data model (which live files are
actually sensitive, which are genuinely public-safe to carry forward)
before any behavior is chosen. This document records the principle,
not the procedure.

## 17. Self-describing / inheritable device

> **THE DEVICE SHOULD BE SELF-DESCRIBING ENOUGH THAT A LEGITIMATE
> FUTURE OWNER CAN UNDERSTAND, RECOVER, OPERATE, REPAIR, AND EXTEND IT
> WITHOUT NEEDING ACCESS TO THE ORIGINAL OWNER'S ACCOUNTS.**

If this physical box outlives its current creator/operator, a
legitimate future owner should be able to understand it **from the box
itself.** A future "About This PirateBox" / "Tell me about yourself"
facility could eventually explain: what PirateBox is, hardware
platform, storage, radios, installed capabilities, optional/absent
capabilities, current health, privacy/exposure state, physical
controls, safe shutdown, maintenance information, wiring assignments,
the local source repository, documentation, the ownership/recovery
concept (§14-16), replaceable hardware roles, and known degraded
capabilities. Illustrative, not implemented:

```
ABOUT THIS PIRATEBOX

This is a Raspberry Pi-based offline field utility and local network
appliance.

Core services:          Operational
Storage:                 128 GB
Primary Wi-Fi:            AWUS036ACM
Fallback Wi-Fi:           built-in wlan0
RTC:                      Installed / trusted
GNSS:                     Installed / 3D fix / position PRIVATE
Environmental sensors:    3 available
External node:            1 connected
Travel Mode:               Enabled
Sensitive public exposure: None
Degraded capabilities:     particulate sensor unavailable

Capabilities | Privacy | Hardware | Health | Maintenance | Ownership
```

**This example describes a future, more-built-out PirateBox - it is not
a claim about this device's current state.** See
`docs/CAPABILITY-REGISTRY.md` for what's actually installed today.

The existing local Git repository and durable documentation
(`docs/`, `CLAUDE.md`, `README.md`) are already, today, part of this
machine's long-term serviceability - this is not a new mechanism to
build, but an existing one to keep maintaining with this future reader
in mind. Documentation should explain **why** assignments exist, not
merely who chose them (§5).

## 18. Current owner vs. future owner

The device is **currently** created by its present creator, owned by
its present owner, maintained by its present maintainer, and operated
according to the present operator's goals. Those facts legitimately
influence current configuration - nothing in this document asks for
that to change today. But they must not become inseparable from
PirateBox identity. A future owner may replace the Pi, replace the
radio, install or remove sensors, use different emergency profiles,
expose GNSS deliberately, never use GNSS, orient the device around
radio work, orient it around environmental monitoring, or use no
optional field tools at all. **The project should preserve a stable
Core while allowing the implementation around it to evolve.**

## 19. No "final PirateBox" requirement

PirateBox does not need to reach a mythical final feature-complete
state. There should be **known-good baselines** - `docs/CHECKPOINTS.md`
already is exactly this mechanism, one row per stage, each a safe point
to stand on or roll back to. At any known-good baseline: Core works,
optional capabilities may exist or not, experimentation can stop, and
the device remains useful. Future capabilities are additive. The goal
is to be able to discover an interesting new piece of hardware or
project idea next year and ask *"where does this fit into our
architecture?"* (§2-§5 exist to make that question answerable) rather
than *"do we have to redesign PirateBox?"*

## 20. What this document deliberately leaves undecided

Consistent with the rest of this document's own discipline: these are
open questions for future design work, not gaps to silently fill now.

- The exact ownership-claim mechanism (§14-15) - sequence, credential
  type, hardware token or not.
- Exact data-transfer/reset behavior (§16).
- The Quiet/Stealth indicator policy's exact trigger/scope (§8).
- The progressive-disclosure UI's actual implementation (§9) - no page
  described there exists.
- The self-description ("About This PirateBox") page itself (§17).
- The capability-state store's schema (§11) - semantics only, no schema
  chosen.
- Whether/how a PCA9548A-class I2C mux gets adopted (§4) - noted as a
  future option, not decided.
- The naming collision between Stage 16's "Recovery" and this
  document's "Recovery/Claim" (§14) - flagged, not resolved.

## 21. Cross-references

- **Concrete capability state** (what's installed, owned, planned,
  candidate, deferred, rejected): `docs/CAPABILITY-REGISTRY.md`.
- **GPIO/hardware wiring, current pin status:**
  `docs/HARDWARE-INTEGRATION-DESIGN.md`.
- **Physical buttons / OLED UX design:**
  `docs/PHYSICAL-CONTROL-UX-DESIGN.md`.
- **Power / UPS / undervoltage:** `docs/POWER-UPS-DESIGN.md`.
- **RTC / time readiness:** `docs/RTC-TIME-READINESS-DESIGN.md`.
- **Field Tools (time/date, unit conversion, coordinates - today's
  closest real example of an Operational capability with an honest
  degraded state):** `docs/FIELD-TOOLS-DESIGN.md`.
- **Travel Mode (today's real example of §6/§7's exposure
  discipline):** `docs/TRAVEL-MODE-DESIGN.md`.
- **Found Device / "Recovery Messages" (distinct from §14's
  "Recovery/Claim" - see that section's explicit note):**
  `docs/OPERATIONAL-DECISIONS.md`, "Stage 16."
- **Zero-context recovery / session entrypoint:** `CLAUDE.md`.
- **Every dated implementation decision:** `docs/OPERATIONAL-
  DECISIONS.md` (reverse-chronological history, not a task list - see
  `CLAUDE.md` §4).
