# Device Memory & Unattended Operation Design

**Status: DESIGN ONLY.** Formalizes principles for how PirateBox should
eventually remember what happened while it was unattended. **Nothing in
this document is implemented** - no logging mechanism, database,
retention job, review boundary, "since last review" summary, Field
Session handling, or GNSS capture exists on this device as a result of
this document. Where an example below looks like a real screen or a
real data shape, it is illustrative only, marked as such.

This document is the detailed companion to `docs/ARCHITECTURE.md` §12
(current-state awareness, refined below) - that document states the
principles briefly and points here; this document works through their
implications in full, the same relationship `docs/FIELD-TOOLS-DESIGN.md`
and `docs/TRAVEL-MODE-DESIGN.md` already have to `docs/ARCHITECTURE.md`
and `docs/OPERATIONAL-DECISIONS.md`. `docs/CAPABILITY-REGISTRY.md`
cross-references this document only where a specific capability's
retention/privacy implications belong on its own entry - it does not
duplicate this document's general model.

---

## 1. Why this exists

PirateBox may spend much of its life unattended: sitting at home
untouched for months, powered occasionally, thrown into a backpack for
a trip and never taken out during it, used briefly in a hotel room,
running for hours or days without the operator looking at it, returning
home, remaining untouched again, and eventually being reviewed days,
weeks, or months later. The operator may or may not care what happened
during that period. When they do look, PirateBox should be able to
answer:

> **"WHAT HAPPENED WHILE I WASN'T LOOKING?"**

This is an **extension** of `docs/ARCHITECTURE.md`'s self-awareness
model (§10-13 there), not a rejection of its privacy principles (§6-8,
§12 there). Unattended operation is normal lifecycle behavior for this
project, not an edge case - see §9 below.

## 2. The refined history principle

`docs/ARCHITECTURE.md` §12 states:

> **PREFER CURRENT-STATE AWARENESS OVER HISTORICAL SURVEILLANCE.**

That principle stands, unchanged - and it was never actually violated
by remembering *anything*: the existing connection-statistics feature
(`docs/OPERATIONAL-DECISIONS.md`, "Post-Stage-32: Privacy-Preserving
Connection Statistics") already retains hourly aggregate counts on the
SD card, not just instantaneous state, while never once writing a MAC
address, IP, or per-device record anywhere. That feature is the proof
this principle was always about *what kind* of history, not *whether*
any history exists. Two principles now made explicit, refining rather
than replacing it:

> **RETAIN ENOUGH HISTORY FOR THE OPERATOR TO UNDERSTAND WHAT HAPPENED
> WHILE PIRATEBOX WAS UNATTENDED, BUT MAKE RETENTION PURPOSEFUL,
> BOUNDED, PRIVACY-CLASSIFIED, AND APPROPRIATE TO THE CAPABILITY.**

> **PIRATEBOX SHOULD BE ABLE TO SUMMARIZE THE PERIOD SINCE THE OPERATOR
> LAST REVIEWED IT.**

The goal is not indiscriminate surveillance or permanent raw telemetry.
It's a useful, privacy-conscious operational memory - closer in spirit
to a car's trip odometer and warning-light history than to a security
camera's continuous recording.

## 3. "Since last review" as an operator concept

A future operator review boundary: PirateBox may eventually know
something like "last reviewed 43 days ago, 12 noteworthy events since."
**Illustrative only - no such summary exists today:**

```
SINCE LAST REVIEW (conceptual example - not implemented)

Runtime
  powered on 3 times
  18h 42m total uptime
  longest session 11h 08m

Networking
  27 anonymous connection events
  peak simultaneous clients 4
  preferred external radio remained available
  1 fallback event to built-in Wi-Fi

Environment
  temperature range
  enclosure high temperature
  humidity range
  warning events

Power
  undervoltage events
  thermal/power warnings
  protective shutdowns, if any

Location
  GNSS availability percentage
  position-history policy
  whether travel occurred
  whether exact route capture was enabled/disabled

Companions
  known optional devices/capabilities that appeared
  duration/availability where useful

System
  failed/recovered capabilities
  time-confidence problems
  storage changes/thresholds
  core-service failures or lack thereof
```

**None of these line items is mandatory** - this is the shape a summary
*could* take once the underlying capabilities exist, not a checklist a
future implementation must fill in completely. Most of these sections
depend on hardware that doesn't exist yet (GNSS, environmental sensors,
companions - see `docs/CAPABILITY-REGISTRY.md`); Runtime, Networking,
and System are the only sections with any real data source today
(uptime, connection statistics, service health), and even those have no
"since last review" boundary built. A future "Mark reviewed" action may
establish a new boundary for the next summary - not designed here.

## 4. Operational history vs. sensitive observation history

The central distinction this document formalizes. Every future retained
datum falls into one of two broad categories:

### Operational history

Generally useful for understanding device health and unattended
behavior; low privacy sensitivity by nature. Examples: boot/shutdown
events, uptime, service/capability degraded-recovered events, thermal
warnings, undervoltage warnings, storage thresholds, radio fallback/
recovery, time-confidence changes, a known module attached/removed,
software/configuration changes, and aggregate anonymous client
connection counts (already real - see §2). This is the category the
existing connection-statistics and undervoltage-monitoring features
already populate today, in miniature.

### Sensitive observation history

Could reveal people, movement, surroundings, or operator behavior.
Examples: exact GNSS coordinates/routes, raw audio recordings, nearby
Wi-Fi identifiers, radio captures, identifiable client/device
information, highly detailed sensor timelines tied to exact location,
or anything else in that spirit.

> **Sensitive observation history must not exist merely because the
> hardware is capable of collecting it. It should require an explicit
> purpose/policy.** The fact that PirateBox *can* observe something
> does not mean it *should* persist it - see §10's retention-symmetry
> principle.

## 5. Retention classes / semantics

Not a schema - semantics only, in the same spirit as
`docs/ARCHITECTURE.md` §11's "no database designed yet." Names are not
sacred; reconciled here with what this project already does in practice
rather than invented fresh:

- **Current only** - ephemeral state, RAM/tmpfs where appropriate, not
  intended to survive reboot. Already the live pattern for the
  connection-statistics feature's raw per-poll MAC list and in-progress
  hour counter (`/run/piratebox/prev-stations`, `/run/piratebox/hour-
  scratch` - both tmpfs, both gone on reboot).
- **Event history** - compact, persistent, noteworthy events (a boot, a
  fallback, a threshold crossed) rather than continuous samples.
- **Summary history** - bounded aggregate summaries (hourly/daily/min/
  max/count) rather than every raw sample. Already the live pattern for
  connection statistics' persisted `{hour_start, count, peak}` triples
  (`data/connection-stats.json`, rolling ~25-hour window, oldest pruned
  automatically).
- **Explicit capture** - retained because the operator deliberately
  enabled a capture function/session (see §7's Field Session concept).
- **Sensitive capture** - explicit capture with stronger privacy/
  exposure expectations (§4's sensitive-observation category, only ever
  retained under this class).

For anything retained under any of these classes, a future design
should be able to answer, per `docs/ARCHITECTURE.md` §11's fact/intent
distinctions:

- **WHAT** is retained?
- **WHY** is it retained?
- **FOR HOW LONG?**
- **WHO** can see it?
- **HOW sensitive** is it?
- **CAN** the operator purge/export it?
- **WHAT** happens when storage is constrained?

exactly the same discipline `docs/ARCHITECTURE.md` §12 already requires
of any retained telemetry, restated here per-class rather than
per-feature. **No universal retention duration is decided here** -
different capabilities may reasonably have different policies (a
30-second-resolution temperature summary and a months-long uptime
counter aren't the same shape of data).

## 6. Aggregation over raw data where practical

Use aggregation whenever the operator's real question can be answered
without raw samples. Illustrative:

```
Instead of storing enclosure temperature every second for eight months:

  Sep 2: min 64F, avg 77F, max 109F, warning events: 1
```

High-resolution/raw history may be useful during an explicitly enabled
experiment or field session (§7), but should not automatically become
the default for every sensor. This also directly serves SD-card
longevity - the same write-minimization discipline
`piratebox_status_helper.sh`'s existing hourly-flush design already
applies for connection statistics (§2) generalizes to every future
sensor. **No specific sampling rate is chosen here** for any capability
- none of the hardware this would apply to exists yet (see
`docs/CAPABILITY-REGISTRY.md`).

## 7. Optional Field Sessions

A possible future organizational concept - **not a required operating
mode.** The normal box must remain fully useful without ever starting
one; nothing about Core or Operational capabilities depends on a
session existing. Illustrative only:

```
FIELD SESSION (conceptual example - not implemented)
Name: Texas trip
Mode: Travel

Capture policy:
  + system events
  + environmental summary
  + power events
  + anonymous connection totals
  + companion availability
  + GNSS route
  - nearby Wi-Fi identifiers
  - client identifiers
  - audio recording
```

The idea: let an operator deliberately change capture/retention policy
for a particular trip, experiment, ham-radio outing, or weather-
observation period, without that policy applying the rest of the time.
At completion, a future system might offer a review report, export,
archive, or a purge of anything captured under the Sensitive Capture
class specifically. **Session handling, its triggering UX, and its
exact policy toggles are not designed here** - this section records the
concept and its constraint (optional, never required) only.

## 8. GNSS history must remain separate from GNSS availability

Reinforces `docs/ARCHITECTURE.md` §7 (no GNSS hardware exists on this
device today - this is forward design only). PirateBox may have
`Current GNSS position: AVAILABLE` while separately having `GNSS
history: DISABLED` - or, by deliberate operator choice, `GNSS history:
ENABLED FOR CURRENT FIELD SESSION` / `Exposure: OWNER ONLY`. Three
principles that must hold regardless of how GNSS is eventually wired:

- Being able to determine **current position** must never silently
  imply **route logging.**
- Using GNSS for **UTC** must never imply **position logging** (already
  stated in `docs/ARCHITECTURE.md` §7 - position and time are
  independent outputs of the same hardware).
- Using GNSS for local **Travel/Home determination** must never imply
  **position history** (`docs/ARCHITECTURE.md` §7's local-comparison-
  only design already implies this; stated explicitly here too).

Exact route capture is a sensitive explicit capability (§4/§5's
Sensitive Capture class) - it exists only when deliberately turned on,
never as a side effect of GNSS being present or useful for something
else.

## 9. Unattended operation is normal, not an edge case

Part of this project's field-device identity
(`docs/ARCHITECTURE.md` §1), stated explicitly:

> It sits on a shelf. It goes into a backpack. It wakes up. It performs
> the work it was configured to perform. It records only the history
> its policy permits. It may return home without ever being interacted
> with. Later, when the operator cares, it can explain what happened.

PirateBox should tolerate being ignored - the operator should not have
to continuously supervise it for it to remain understandable later.
This has implications for future work this document does not itself
resolve, only names:

- **health/status design** - a status surface must remain meaningful
  after a long gap, not just moment-to-moment.
- **retention policy** (§5) - must work unattended by construction, not
  assume a human is watching to decide what to keep.
- **time confidence** - already a live concern
  (`docs/RTC-TIME-READINESS-DESIGN.md`, `docs/FIELD-TOOLS-DESIGN.md`
  §4) - a device that's been unattended and unpowered is exactly the
  scenario where clock trust matters most for dating any history
  collected around a reboot.
- **sensor summaries** (§6) - must accumulate correctly across gaps of
  arbitrary length, including full power-off.
- **power monitoring** - the existing undervoltage/throttling detection
  already runs unattended today; future power/battery capabilities
  inherit the same expectation.
- **graceful recovery** - a capability that failed while unattended
  should be observable as "failed, since <time>," not silently absent.
- **self-diagnosis** (`docs/ARCHITECTURE.md` §13) - "since last review"
  summaries are exactly the input a future self-diagnosis surface would
  read from.
- **operator UX** - a review flow has to work for someone returning
  after an hour and someone returning after eight months without being
  overwhelming in either case (see §3's "not every line item is
  mandatory").

## 10. Self-awareness with memory

Extends `docs/ARCHITECTURE.md` §10's self-awareness question set with
history-aware questions - deterministic device/state/history awareness,
explicitly **not** an attempt at artificial "AI memory":

- **What is true now?** (already `docs/ARCHITECTURE.md` §10's "how am I
  doing?"/"what can I use right now?")
- **What happened?**
- **What changed?**
- **What was important?**
- **What has the operator already reviewed?** (§3's review boundary)
- **What history exists?**
- **What history was intentionally not collected?** (as important as
  what *was* - a deliberate absence, per §4/§10 below, not a gap to be
  confused with a failure to collect)
- **What history is sensitive?** (§4's classification)
- **What is stale/unknown?** (already `docs/ARCHITECTURE.md` §10's
  core "prefer honest UNKNOWN" rule, extended to history itself - a
  missing or incomplete history record should say so, not be silently
  treated as "nothing happened")

Illustrative combined current-state-plus-history example (**not a real
page**):

```
External AP: active now
Fallback events since last review: 1

Power: good now
Undervoltage events since last review: 5

GNSS: fix available now
Route history: disabled

Environment: normal now
Highest enclosure temperature since last review: 126F
```

This gives the operator meaning rather than a wall of logs - the same
progressive-disclosure instinct as `docs/ARCHITECTURE.md` §9, applied
to history instead of just current state.

## 11. Privacy boundary

Useful historical awareness must **not** quietly undo any existing
privacy decision. Explicitly preserved, unchanged by this document:

- aggregate connection statistics rather than persistent client
  identifiers (already true - §2)
- no default GNSS trail
- no automatic nearby-device history
- no automatic raw audio history
- no indiscriminate radio/network capture
- no cloud telemetry requirement
- public users do not automatically gain access to operator historical
  data
- Travel Mode remains privacy protective (`docs/TRAVEL-MODE-DESIGN.md`
  - untouched by anything in this document)

`docs/ARCHITECTURE.md` §6 already states:

> **INFORMATION IS EXPOSED BECAUSE THE OPERATOR DELIBERATELY CHOSE A
> USEFUL EXPOSURE, NOT MERELY BECAUSE THE BOX POSSESSES THE
> INFORMATION.**

This document adds the analogous retention principle:

> **INFORMATION IS RETAINED BECAUSE THERE IS A DELIBERATE OPERATIONAL
> PURPOSE FOR RETAINING IT, NOT MERELY BECAUSE PIRATEBOX WAS CAPABLE OF
> OBSERVING IT.**

## 12. Storage / durability / failure considerations

At architecture level only - **no database is designed here.** Any
future unattended-history mechanism must eventually account for:
bounded storage, free-space protection, SD-card write-amplification/
endurance, corruption resilience, atomic/durable writes, power loss,
time confidence, stale sensors, summaries-vs-raw-streams (§6), data
export, purge, privacy-sensitive purge (§4/§5), and behavior when
storage becomes constrained. **This project's existing safeguards in
this space are already authoritative and remain so:**
`docs/OPERATIONAL-DECISIONS.md` "Stage 24: Resilience Audit - Low-
Storage Guard for Flat-File Stores" (bounded-write/low-storage
discipline for the existing flat-file stores) and "Stage 25: Backup /
Restore for Live Community Data" (durable-write and backup/restore
pattern every persisted store in this project already follows,
including connection statistics' own atomic temp-file-then-rename
writes). A future history mechanism should extend that existing
discipline, not invent a separate one.

## 13. Ownership transfer interaction

Connects to `docs/ARCHITECTURE.md` §16 (data-aware ownership transfer,
already flagged there as undecided). Historical data belongs to
different privacy classes (§4/§5), and **a future ownership transfer
must not automatically expose the previous operator's sensitive
historical captures.** Illustrative, not decided:

- public/community data may potentially be preserved
- generic operational history (§4) may or may not be appropriate to
  preserve across a transfer
- private GNSS route history (§8) should receive stronger treatment
  than operational history
- sensitive captures/integration credentials must not simply become
  readable because ownership was reclaimed

**Exact transfer/wipe rules are not decided here** - this section
exists to make sure the eventual data-aware ownership-transfer design
(`docs/ARCHITECTURE.md` §16) explicitly accounts for history/retention
classes as part of that work, rather than discovering the interaction
late.

## 14. What this document deliberately leaves undecided

- The exact review-boundary mechanism ("Mark reviewed") - trigger, UI,
  storage (§3).
- Which "since last review" line items, if any, become real, and their
  exact wording/thresholds (§3).
- Field Session triggering UX and exact policy-toggle set (§7).
- Any specific sampling rate, summary interval, or retention duration
  for any future capability (§5/§6).
- The GNSS history storage format/location, if ever built (§8).
- Exact ownership-transfer wipe/preserve rules for historical data
  (§13) - flagged for the future data-aware ownership-transfer design
  to resolve.
- Whether/how this document's classes map onto an eventual capability-
  state schema (`docs/ARCHITECTURE.md` §11 also leaves this open).

## 15. Cross-references

- **Principles this extends:** `docs/ARCHITECTURE.md` §6-13
  (exposure/privacy, self-awareness), §16 (ownership transfer).
- **Concrete precedent this generalizes from:**
  `docs/OPERATIONAL-DECISIONS.md`, "Post-Stage-32: Privacy-Preserving
  Connection Statistics" (the existing, live example of Summary History
  + Current Only classes in practice).
- **Existing storage/durability discipline to extend, not replace:**
  `docs/OPERATIONAL-DECISIONS.md`, "Stage 24" (low-storage guard) and
  "Stage 25" (backup/restore for live community data).
- **GNSS/location privacy this reinforces:** `docs/ARCHITECTURE.md` §7.
- **Time confidence:** `docs/RTC-TIME-READINESS-DESIGN.md`,
  `docs/FIELD-TOOLS-DESIGN.md` §4.
- **Concrete capability inventory:** `docs/CAPABILITY-REGISTRY.md` -
  consult per-capability for whether/how this document's retention
  classes apply to something specific and real.
