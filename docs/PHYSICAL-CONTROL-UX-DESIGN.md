# Physical Control UX Design (Stage 29)

**Status: DESIGN ONLY for the still-unassigned buttons (§2) - the OLED
page state machine (§1) is now implemented.** **§3's hold-for-safe-
shutdown flow has been implemented and physically verified** on
GPIO25/physical pin 22 - the exact design below (4.0s hold, no re-fire,
no action on early release) matches what's actually running. See
`docs/OPERATIONAL-DECISIONS.md` ("Stage 29 Implementation: Physical
Shutdown Button") for the bring-up test results and the running
service, and `docs/HARDWARE-INTEGRATION-DESIGN.md` §2 for the
authoritative wiring map. **As of 2026-09-03, §1's four-page OLED
design (Status/Time/Network/Health) is built and physically verified**
- `piratebox_oled_daemon.py`/`piratebox-oled.service`, see
`docs/HARDWARE-INTEGRATION-DESIGN.md` §12 for the full bring-up record.
One deliberate interim departure from §1/§5 below, explained in full in
the daemon's own header comment and in §1's note below: with GPIO22
("cycle page") and GPIO23 ("wake display") not physically wired yet,
the daemon auto-rotates through the four pages on a timer instead of
waiting for a cycle button, and does not auto-dim (dimming with no way
to wake the display back up would defeat its glanceable purpose
entirely). Both are straightforward to switch to the button-driven
behavior specified below once those two buttons are wired - the
per-page render functions don't change. Everything else in this
document (the remaining buttons, transport lock, mode-switch UX)
remains the plan to follow once that hardware physically arrives.

**Relationship to Stage 11:** Stage 11 designed the *electrical* layer
(pin assignments, debounce mechanism, package needs) and deliberately
left button *functions* unassigned "per instruction," to decide once
hardware is in hand and testable - ergonomics of a real enclosure
affect which physical button suits which job. This stage does not
override that caution. What it does do is finish the two pieces of *UX*
design Stage 11 explicitly flagged as needing "its own explicit design
pass" without needing hardware in hand to reason about: the hold-to-
shutdown confirmation flow, and a complete page/button interaction
state machine - plus a concrete *recommended* default button mapping,
offered as a starting point for the operator to accept, reorder, or
override once the hardware is physically testable, not as a final
decision made on this session's own authority.

---

## 1. OLED page state machine

**Updated (Post-Stage-32, Field Tools): Clock/Time is now a first-class
fourth page, not a secondary field folded into Status.** Originally
this section specified three pages; a Time page was added once Field
Tools (`docs/FIELD-TOOLS-DESIGN.md`) built the exact shared time/time-
source functions this page needs, on the reasoning that "what time is
it, and can I trust this device's clock" is glance-info in its own
right during an off-grid deployment, not a detail worth burying inside
another page. Four pages, cycling in a fixed order, matching Stage 11
§5's two content layouts plus two additions (§3 below, and this one):

```
[Status] --(cycle)--> [Time] --(cycle)--> [Network] --(cycle)--> [Health] --(cycle)--> [Status] ...
```

- **Status page**: mode (NORMAL/EMERGENCY), SSID, client count - the
  single most-wanted glance-info, so it's the page shown on wake and
  after an idle timeout returns here (see §5).
- **Time page** *(new)*: local time, UTC, date, weekday/day-of-year, and
  system uptime - a compact view of exactly what
  `includes/fieldtools_time.php`'s `piratebox_fieldtools_now_snapshot()`
  and `piratebox_get_time_source_status()` already compute for the web
  Time &amp; Date tool (`/utility/fieldtools/time/`), reused rather than
  reimplemented, same "one tested copy" pattern as the Network/Health
  pages below. A compact target layout for the 128&times;64 display
  (exact formatting adaptable):
  ```
  TIME
  Local  03:42:18 PM
  UTC    22:42:18
  Date   2026-09-02
  Day    Wednesday / 245
  Uptime 5d 07h
  ```
  **Must also show this device's time-source status**, not just the
  numbers - whatever `piratebox_get_time_source_status()` reports
  (`rtc_detected`, `ntp_synchronized`), rendered honestly the same way
  the web page does (no hardware RTC installed as of this writing - see
  `docs/RTC-TIME-READINESS-DESIGN.md` - so today this page must say so
  plainly rather than implying a precision the clock doesn't have). Once
  a DS3231 is wired (`docs/HARDWARE-INTEGRATION-DESIGN.md`), this page's
  source line updates automatically - the function it reads already
  reports whatever RTC hardware it actually finds, with no OLED-side
  code change needed.
- **Network page**: IP, SSID again (in case someone starts here),
  per-service health (nginx/php-fpm/hostapd/dnsmasq - reusing
  `includes/metrics.php`'s `piratebox_get_helper_status()` exactly as
  the Stats page does, so a fourth reimplementation of that logic never
  gets written).
- **Health page**: uptime, storage free/total, CPU temp, cumulative
  Emergency Mode runtime (Stage 21's `piratebox_get_emergency_runtime_
  seconds()`) - the device-health facts an operator checks in on
  periodically rather than glances at constantly, which is why they're
  one press deeper than Status. (Uptime now also appears on the Time
  page, per the mockup above - a harmless small overlap between "what
  time is it" and "how long has this box been running," not worth
  engineering around.)

**Degraded-state display, decided now rather than left to whoever
builds this later:** every page must show an honest "not reporting"
state for any datum it can't read, using the exact same pattern this
project already uses everywhere else (the Stats page, `admin/index.php`)
- never a blank field, never a stale number presented as current. A
status-helper-stale condition should replace the whole Network/Health
pages' service-health section with one clear line ("status helper not
reporting") rather than showing individually-blank rows, since a stale
snapshot means none of those numbers can be trusted at once, not just
one of them.

## 2. Button function mapping (recommended default, not final)

| Button (Stage 11 pin) | Proposed function | Reasoning |
|---|---|---|
| GPIO22 | **Cycle page** (short press) | Matches §1's page order; the most-used control gets the most GPIO-conventional "first" button. |
| GPIO23 | **Wake display** (short press) | If the OLED dims/sleeps to save power (see §5), this is the "wake it up" button - separate from cycle so a sleepy display doesn't eat a cycle press meant for after it's already awake. |
| GPIO24 | *Reserved, unassigned* | Stage 11 listed 5 buttons against a 3-page display with no confirmed "select/action" need yet (every page here is read-only info, nothing to select into) - assigning a function to every button that doesn't need one yet would be inventing UX to fill hardware, backwards from designing UX first. Left open for a genuinely new need (e.g. a future admin-adjacent action) rather than assigned now. |
| GPIO27 | *Reserved, unassigned* | Same reasoning as GPIO24. |
| GPIO25 | **Hold-for-safe-shutdown** (see §3) | Matches Stage 11's own tentative placement note (nearest a panel edge in most enclosure concepts) - kept as proposed, not re-litigated. |

This intentionally assigns only 3 of 5 buttons. Two unused momentary
buttons, wired but doing nothing yet, is a correct, honest outcome of
"don't invent a job for a button that doesn't have one" - not a gap to
paper over. If a genuinely new physical-control need shows up later
(the OLED page set grows, or a new admin-adjacent physical action gets
approved), GPIO24/27 are already wired and reserved for exactly that,
no rewiring needed.

## 3. Hold-for-safe-shutdown: full UX flow

Stage 11 named this as needing its own design pass and explicitly
flagged the pattern difference (debounce-for-duration vs. debounce-for-
level-change) without solving it. Full flow, decided now:

1. **Idle**: button not pressed. Display shows whatever page §1 left it
   on.
2. **Press starts a hold timer.** At **1 second** held, the OLED
   interrupts whatever page was showing with a full-screen countdown:
   `HOLD TO SHUT DOWN\n\n3...` counting down to `1...`, updating once
   per second.
3. **Early release at any point before the countdown reaches zero
   aborts with no action taken** - display returns to whatever page was
   showing before the hold began (not necessarily the Status page -
   don't disorient someone who was mid-way through checking something
   else). No log entry, no side effect - an aborted hold is a no-op by
   design, exactly as unsurprising as letting go of a key.
4. **Held continuously through zero** (proposed total: **4 seconds** -
   1s grace before the countdown starts, plus a 3-count, long enough
   that bumping the button by accident while handling the device is very
   unlikely to reach it, short enough that a deliberate hold doesn't feel
   broken) triggers the actual shutdown: OLED shows `SHUTTING DOWN...`
   (a final, non-interruptible confirmation that the action was
   registered) and the daemon requests `sudo systemctl poweroff` via a
   new, narrowly-scoped sudoers line dedicated to this exact command -
   **not** an addition to the existing `piratebox-claude` sudoers file
   (Claude's deploy/mode-switch automation), which is a different trust
   boundary belonging to a different actor (this session, not a
   locally-running display daemon) and should stay exactly as narrow as
   it is today, per that file's own header. A future implementation
   pass should give the OLED daemon its own dedicated, single-purpose
   sudoers grant instead of widening an unrelated one.
5. **No countdown-abort undo after zero** - by the time `poweroff` is
   requested, the decision is final, matching how every other physical
   power button in the world already behaves; the 4-second hold is the
   deliberate-intent gate, not a step people are meant to cancel out of
   after commit.

This is a state-timing design, not a debounce mechanic - `gpiozero`'s
`when_held` (with `hold_time` set) plus `when_released` naturally
express "start a timer on press, cancel it on early release, act if the
timer completes" without needing a custom polling loop, confirmed
against `gpiozero`'s documented API shape (not yet tested against real
hardware, since none exists in this environment).

**Implemented and physically verified** (`piratebox_button_daemon.py`,
`piratebox-button.service`): steps 1, 3, 4, and 5 above are real and
confirmed on hardware - a short press does nothing, an early release
aborts silently, a continuous 4.0-second hold triggers exactly once
with no re-fire, and `sudo systemctl poweroff` is gated behind its own
dedicated `etc/sudoers.d/piratebox-button` grant exactly as specified.
**Step 2's specific "1s grace + 3-count visual countdown" does not
exist yet** - that's OLED-display output, and no OLED is wired yet;
today the button is functionally a flat 4.0-second hold-time trigger
with no interim visual feedback of any kind. When the OLED is built,
step 2 can be added as a purely additional display behavior without
changing the underlying hold-detection logic at all - the daemon
already correctly implements "start on press, abort on early release,
fire once at 4.0s," which is the only part that actually gates the
shutdown.

## 4. Transport / input safety

**Added 2026-09-02, following from a real property of this device: it
is meant to be carried, thrown in a backpack, bumped, and left
unattended (`docs/DEVICE-MEMORY-DESIGN.md` §9's "unattended operation
is normal").** External buttons/switches must not assume every
electrical transition is deliberate operator intent. This section
formalizes that as an explicit input-safety model, extending §2's
"don't invent a function for a button that doesn't have one" caution to
"don't invent operator *intent* from a raw signal either."

### 4.1 Review of the existing GPIO25 implementation - no change made

**Reviewed against this model before writing anything new, per
instruction not to touch a commissioned control without a concrete
demonstrated deficiency.** `piratebox_button_daemon.py` already
satisfies every accidental-input-resistance goal below, by construction,
not by accident:

- **Debounce:** `bounce_time=0.05` (50ms), electrically bring-up tested
  clean across ~20 taps in two separate runs (`docs/OPERATIONAL-
  DECISIONS.md`, "Stage 29 Implementation").
- **Stable-state/hold-threshold requirement:** the only action this
  daemon can take requires **4.0 continuous seconds** of held-low state
  - a single bump, a mashed/rapid sequence of taps, or a brief snag
  cannot reach it. A short press has **zero code path to anything** -
  `when_pressed`/`when_released` are deliberately not wired at all, only
  `when_held`. This is the *same* debounce/hold-threshold mechanism
  doing double duty as both "detect a deliberate hold" and "reject
  accidental input," not a second, independent mechanism layered on top
  - kept intentionally simple per this section's own "don't add hidden
  timing complexity unnecessarily."
- **Stuck-active / retrigger prevention:** `hold_repeat=False` - even
  an indefinitely stuck-low pin (e.g. genuinely trapped under something
  in a bag) fires the shutdown request **exactly once**, never
  repeatedly, confirmed live to 7.27s with no re-fire (Stage 29 bring-up
  testing).
- **Fail-safe default:** the real `poweroff` call is gated behind an
  explicit opt-in env var, `sudo -n` fails immediately rather than
  hanging if misconfigured, and any exception is logged without a
  crash-loop retry - every failure mode points toward inaction, per
  `docs/ARCHITECTURE.md` §2's "optional capability failure must
  degrade, not disable" (the shutdown button is Core, per that
  document's §2, but the same fail-toward-inaction discipline applies).

**Conclusion: no code change to `piratebox_button_daemon.py` or its
systemd unit.** A genuinely sustained (4+ second) hold from backpack
compression could still trigger a real shutdown - this is an inherent
tradeoff of a physical hold-to-shutdown control that the original
design (§3) already reasoned through explicitly ("long enough that
bumping the button by accident... is very unlikely to reach it, short
enough that a deliberate hold doesn't feel broken"), not a newly
discovered gap. If real-world experience ever demonstrates this
tradeoff is wrong in practice, that's a concrete deficiency to revisit
then - not guessed at now.

**Updated 2026-09-04 (short press, then double tap): the "zero code
path" bullet above no longer describes the implementation.**
`when_pressed`/`when_released` are now wired (a short tap drives a
temporary status-check override; a double tap toggles Silly Mode - see
`docs/OPERATIONAL-DECISIONS.md` → "OLED cadence rebalance +
short-press status-check override" and "Double-tap Silly Mode toggle
(physical button)"). Reviewed against this same accidental-input-
resistance model rather than assumed safe: a bump or snag can now reach
a short-tap or double-tap code path that plain `when_held` alone could
never reach - but neither path can ever cause it to `poweroff`, escalate
privilege, or touch durable state; the worst an accidental double-tap
can do is leave the desk-toy Silly Mode display in the other of its two
cosmetic states until the next real press (a UX nuisance, not a safety
regression), and the worst an accidental short tap can do is show real
status pages for ~15s instead of faces. `HOLD_SECONDS`/`hold_repeat`/
the fail-safe defaults for the one actually consequential action
(shutdown) are all unchanged from the review above, and the new gesture
state machine is structurally unable to set the shutdown flag itself
(see the two `OPERATIONAL-DECISIONS.md` entries' own long-hold-safety
sections) - so this update narrows the bullet's accuracy, not this
section's conclusion.

### 4.2 Panel/transport-lock concept (design only - no lock hardware exists)

A future **Transport Lock** - a deliberate way to make the physical
control panel inert while carried - is desirable but **not chosen or
built**: no dedicated lock switch is purchased (see
`docs/CAPABILITY-REGISTRY.md`), and the enclosure/panel itself isn't
finalized (§6). Conceptual states, for a future implementation:

```
PHYSICAL CONTROLS: ENABLED | LOCKED | DEGRADED | INPUT FAULT | UNKNOWN
```

Constraints for whenever this is built, regardless of the eventual
mechanism (dedicated maintained switch, a deliberate button gesture, or
a combination - **not decided now**):

- When **LOCKED**, ordinary noncritical external controls (page-cycle,
  display-wake) must not trigger actions; the OLED may remain quiet/
  asleep.
- Safety monitoring must continue regardless of lock state.
- **Critical protective behavior must never be disabled merely because
  the panel is locked** - this includes GPIO25 shutdown; see §4.4 below
  for why that specific question is flagged rather than answered here.
- The lock itself must introduce no Core dependency
  (`docs/ARCHITECTURE.md` §2) - Core (AP/site) is already fully
  independent of every physical control, lock included.
- **Public Wi-Fi users must never be able to remotely override a
  physical transport lock.** A physical safety state stays
  physical-input-authoritative, not web-request-overridable - no
  network path to this state is proposed anywhere in this document.

### 4.3 Invalid / contradictory input

PirateBox should recognize when physical input doesn't represent a
valid command, rather than guessing at operator intent. Examples this
model must eventually cover: mutually contradictory maintained-switch
readings, implausibly rapid transitions, multiple unrelated buttons
mashed together, a button stuck active for an unreasonable period, an
unstable switch state, or input repeated far beyond plausible
deliberate use. In every such case: **suppress the ambiguous action,
never guess.** Prefer a deterministic, honest status over a story:

```
Physical controls: DEGRADED
Reason: contradictory input state
Ambiguous actions suppressed
Core services unaffected
```

**Not** "device is being stepped on" or "inside a backpack" - represent
what was observed (a contradictory/unstable electrical state), never a
narrative about why, matching `docs/ARCHITECTURE.md` §10's "prefer
honest UNKNOWN over confidently inventing" applied to physical input
specifically.

### 4.4 Mode changes (GPIO17, not yet wired) - open design question

For the planned Normal/Emergency maintained toggle (GPIO17): a single
electrical edge must not be treated as sufficient proof of intended
mode. A future implementation should require a **stable, validated
input state** (appropriate debounce/settling, not a raw instantaneous
read) before acting, and if the state is genuinely ambiguous or
unavailable, must not flap between modes - it should hold the last
known valid state (mirroring `piratebox_get_mode()`'s existing
fail-safe-to-Normal behavior for a missing/corrupt state file - see
`includes/mode.php`) and expose the degraded physical-control condition
to the operator rather than silently guessing. **No code changes were
made for GPIO17** - the switch is not physically wired
(`docs/HARDWARE-INTEGRATION-DESIGN.md` §2), and per that document's own
rule, function/behavior for unwired hardware is designed, not
implemented, ahead of the physical build.

**Explicitly flagged, not answered here:** whether the GPIO25 shutdown
control should remain available while a future Transport Lock is
engaged. This is exactly the kind of fork §4.2 warns "critical
protective behavior must never be disabled" about, but *how* a lock
mechanism and a safety-critical control interact is a real design
decision this document does not have enough information to make yet
(it depends on the lock mechanism eventually chosen, per §4.2 - "not
decided now"). **When a Transport Lock implementation is actually
designed, this specific question must be resolved explicitly, not
defaulted silently** - flagged here so it's not missed later.

### 4.5 Self-awareness integration

Physical control health belongs in the same self-awareness model as
everything else (`docs/ARCHITECTURE.md` §10, `includes/
capability_state.php`). Illustrative target shape, matching that
module's existing state vocabulary (not a new one invented here):

```
Panel: NOT_INSTALLED (no multi-button panel exists yet - only the
       single-purpose GPIO25 shutdown control is wired)
Shutdown button: AVAILABLE
Mode switch: NOT_INSTALLED
Transport lock: NOT_INSTALLED
```

or, once real panel hardware exists and something goes wrong:

```
Panel: DEGRADED
Input fault: GPIO17 unstable
Last valid mode: Normal
Core impact: none
```

**Bounded history, not raw transition logging:** if this is ever
extended into Device Memory (`docs/DEVICE-MEMORY-DESIGN.md`), only
*meaningful* events belong there - "panel entered degraded state,"
"stuck input detected," "ambiguous mode change suppressed" - never
every raw button transition. This is the same Operational-History-not-
raw-stream discipline `docs/DEVICE-MEMORY-DESIGN.md` §4-6 already
establishes generally, applied here specifically.

### 4.6 Physical design considerations (for when enclosure work begins)

Not decided or built now - recorded so it isn't lost before the
enclosure is designed: recessed or guarded switches, switch placement
and button spacing chosen to resist accidental bag-contact, mechanically
protected controls, whether a locking/keyed/recessed control is
actually worth its complexity, and the existing physical-modularity
goals (`docs/ARCHITECTURE.md` §4 - detachable/labeled harnesses,
documented connectors, service loops) applying to the control panel
specifically, not just sensor wiring generally.

## 5. Display power behavior

**Interim status (2026-09-03): NOT enabled yet, by design, not an
oversight.** This section's dim-after-idle behavior depends on the
wake button (§2, GPIO23) to be recoverable at all - without it, an
auto-dimmed display has no way back to full brightness short of
restarting the service, which is worse than the "always poked
brightness" case this section explicitly argues against. `piratebox_
oled_daemon.py` implements the contrast-setting plumbing this section
needs and leaves it unused, ready to wire to GPIO23's callback the
moment that button is physically installed - see the daemon's own
header comment for the full reasoning. The display currently stays at
full brightness continuously.

**Proposed: dim (not fully off) after 60 seconds idle, wake instantly on
any button press** (the dedicated wake button from §2, or any other -
waking on *any* press is more forgiving than requiring the one
"correct" button, and this project consistently favors the forgiving
default over the strict one, e.g. Stage 24's truncate-rather-than-reject
length caps). A full display sleep was considered and rejected as the
default: the OLED's whole value is glanceable status without touching
anything, and a display that's fully blank until poked defeats that for
the common "just glance at it" case. Dimming preserves glanceability at
lower power cost; full sleep remains a reasonable *option* to expose
later if Stage 12's eventual power-budget numbers say the display's
power draw actually matters to runway - not decided against permanently,
just not the default absent that data.

## 6. What is deliberately still not decided

- **GPIO24/GPIO27's eventual function**, if any - see §2's reasoning.
- **Exact enclosure-driven button placement** - Stage 11 already
  correctly deferred this to when a real enclosure exists; nothing here
  changes that.
- **The OLED daemon's shutdown sudoers grant's exact syntax** - named as
  a requirement in §3, not written, since no sudoers file should be
  drafted for a daemon that doesn't exist yet to name.
- **Power-draw-driven display sleep policy** - depends on Stage 12
  numbers not yet available.
- **The Transport Lock's actual mechanism** (§4.2) - dedicated switch,
  gesture, or combination; not chosen, since no lock hardware exists and
  the panel/enclosure isn't finalized.
- **Whether GPIO25 shutdown remains available while a future Transport
  Lock is engaged** (§4.4) - explicitly flagged as needing a real
  decision once a lock mechanism is actually designed, not defaulted
  silently now.
- **The contradictory/unstable-input detection mechanism itself** (§4.3)
  - the *principle* (suppress, don't guess) is decided; no state
  machine or code implements it yet, since it has no consumer until
  GPIO17/a multi-button panel exists.

## 7. Testing performed

None against new hardware (none exists beyond GPIO25, already covered
by Stage 29's own bring-up testing). This remains primarily a UX/
interaction design pass. **2026-09-02 addition:** §4.1's review of the
existing `piratebox_button_daemon.py` against the new transport/input-
safety model *was* performed against real, already-shipped code (not
just reasoned about in the abstract) - read in full, checked against
each accidental-input-resistance goal individually, concluding no
change was needed. That is itself a form of testing (a targeted code
review against a new requirement set), even though no new executable
change resulted.

---

## 8. ALFA AWUS036ACM built-in LED: investigated and closed, no safe control path found (2026-09-03)

**Goal, as instructed:** a subtle heartbeat (LED off most of the time,
one brief blink every ~20-30s) on the ALFA's own built-in LED, using a
normal kernel LED/sysfs interface if one exists, never a guessed raw
register write, and never at any risk to `pb-ap`.

**Investigated, all read-only/reversible, confirmed:**
- No `/sys/class/leds/` entry exists for this adapter (only the Pi's
  own `ACT`/`PWR`/`mmc0`/`default-on`) - not a kernel gap: this kernel
  has full LED support compiled in (`CONFIG_MT76_LEDS=y`,
  `CONFIG_MAC80211_LEDS=y`, `CONFIG_LEDS_CLASS=y`,
  `CONFIG_LEDS_TRIGGERS=y`, including the exact `CONFIG_LEDS_TRIGGER_
  TIMER=y` that would have made a clean 20-30s blink trivial via pure
  sysfs, had a classdev existed).
- Production `pb-ap` confirmed mapped to `phy3`
  (`/sys/devices/.../1-1.3:1.0/ieee80211/phy3`).
- `mt76`'s debugfs tree for this phy (`/sys/kernel/debug/ieee80211/
  phy3/mt76/`) exposes one LED-related file, `led_pin` (root-only,
  default `0`) - a genuine driver-native debugfs attribute, not a raw
  MAC/BB register (`regidx`/`regval`, also present in that same
  directory, were identified but never touched - no documented
  register/value was ever available to justify using them, and none
  was guessed).
- Inspecting the actual loaded kernel modules (`strings` on the
  decompressed `.ko` files - real compiled code, not documentation)
  confirmed real LED support exists in this exact driver stack:
  `mt76.ko` has a generic `mt76_led_init()` oriented around device-tree
  boards (`"led registration was explicitly disabled by dts"`) - not
  applicable to a hot-plugged USB adapter, which has no DT node -  and
  `mt76x02-lib.ko` (covering this exact mt76x02/mt76x2u chip family)
  has real, chip-specific `mt76x02_led_set_blink`/`_set_brightness`/
  `_set_config` functions. None of those three are exported symbols
  reachable from outside that module, and `led_pin` (the one thing that
  *is* exposed) is almost certainly just a plain configuration field
  those functions would consult *if* a LED classdev ever got
  registered - which never happened for this adapter.
- A raw `eeprom` debugfs dump (also present in that directory) was read
  for corroborating evidence only, not acted on: this exact adapter's
  MAC address (`00:c0:ca:ba:aa:a4`) appears at the expected offset,
  confirming the dump is genuine, and large stretches of it are
  unprogrammed (`0xff`) - consistent with, though not conclusive proof
  of, a low-cost OEM unit whose LED configuration was simply never
  populated at the factory. No specific byte/bit was ever claimed to
  *be* the LED-enable flag - that would have required documentation
  this session didn't have, exactly the kind of guess the operator
  explicitly ruled out.

**Live test performed, twice, both fully reversible:** wrote `1` to
`led_pin`, confirmed the write succeeded (readback `1`, zero `dmesg`
errors), operator watched the physical LED. First attempt was brief
(operator flagged a brief write might be missed); repeated with a
sustained hold (value left at `1`, untouched, for as long as the
operator needed to look) - **the operator confirmed no visible LED
response either time.** Reverted to `0` immediately both times.
Independently confirmed after each revert: `pb-ap` still `type AP`/
`ssid PirateBox`, `hostapd`/`dnsmasq` still `active`, `eth0` unaffected,
`systemctl --failed` empty, zero new kernel/USB/`mt76x2u` messages of
any kind across the entire investigation, `vcgencmd get_throttled`
unchanged at `0x50005`.

**Conclusion: no safe, driver-native, or documented way to light this
specific adapter's LED was found on this kernel/hardware combination.**
This is not a kernel configuration gap and not something a systemd
timer or script could fix - the underlying hardware/EEPROM path never
registers a controllable LED device in the first place. Per instruction
("if there isn't [a safe way], leave the LED off and close/document the
investigation cleanly"), **no heartbeat script, timer, or service was
built** - there is nothing for one to safely control, and building a
script around an unverified raw-register poke was explicitly ruled
out. The LED remains OFF, exactly as found. Nothing about `pb-ap`,
`hostapd`, `dnsmasq`, Ethernet, or this Pi's known power condition was
touched or affected by this investigation.

**Future architecture note, as instructed - not built now:** PirateBox
will likely eventually gain dedicated enclosure RGB/status LED(s), once
a real enclosure exists (the same "not until real hardware exists"
deferral already applied elsewhere in this document - see §6). When
that's designed, it should be **mode-aware**: Emergency/fault states
take priority over any cosmetic indication, and future Stealth/Night/
Transport modes (§4 above already establishes Transport as a real,
if not-yet-mechanized, concept) must be able to suppress *all*
cosmetic lighting outright, not dim it. If the ALFA's LED ever does
become controllable (a different, better-EEPROM'd unit; a firmware
technique not yet investigated; documented register access an operator
explicitly authorizes with a real datasheet in hand) it should
represent **radio/device activity only**, and should be one of the
things that future mode system can override/suppress - not a
permanently-independent blink wired into unrelated services. This is a
requirement recorded for that future design pass, not a decision made
here, and not implemented now.
