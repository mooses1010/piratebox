# Physical Control UX Design (Stage 29)

**Status: DESIGN ONLY for the OLED page state machine (§1) and the
still-unassigned buttons (§2).** No I2C/OLED code exists on this Pi.
**§3's hold-for-safe-shutdown flow has been implemented and physically
verified** on GPIO25/physical pin 22 - the exact design below (4.0s
hold, no re-fire, no action on early release) matches what's actually
running. See `docs/OPERATIONAL-DECISIONS.md` ("Stage 29 Implementation:
Physical Shutdown Button") for the bring-up test results and the
running service, and `docs/HARDWARE-INTEGRATION-DESIGN.md` §2 for the
authoritative wiring map. Everything else in this document remains the
plan to follow once the OLED and remaining buttons physically arrive.

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

Three pages, cycling in a fixed order, matching Stage 11 §5's two
content layouts plus one addition (§3 below):

```
[Status] --(short-press cycle button)--> [Network] --(cycle)--> [Health] --(cycle)--> [Status] ...
```

- **Status page**: mode (NORMAL/EMERGENCY), SSID, client count - the
  single most-wanted glance-info, so it's the page shown on wake and
  after an idle timeout returns here (see §4).
- **Network page**: IP, SSID again (in case someone starts here),
  per-service health (nginx/php-fpm/hostapd/dnsmasq - reusing
  `includes/metrics.php`'s `piratebox_get_helper_status()` exactly as
  the Stats page does, so a fourth reimplementation of that logic never
  gets written).
- **Health page**: uptime, storage free/total, CPU temp, cumulative
  Emergency Mode runtime (Stage 21's `piratebox_get_emergency_runtime_
  seconds()`) - the device-health facts an operator checks in on
  periodically rather than glances at constantly, which is why they're
  one press deeper than Status.

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
| GPIO23 | **Wake display** (short press) | If the OLED dims/sleeps to save power (see §4), this is the "wake it up" button - separate from cycle so a sleepy display doesn't eat a cycle press meant for after it's already awake. |
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

## 4. Display power behavior

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

## 5. What is deliberately still not decided

- **GPIO24/GPIO27's eventual function**, if any - see §2's reasoning.
- **Exact enclosure-driven button placement** - Stage 11 already
  correctly deferred this to when a real enclosure exists; nothing here
  changes that.
- **The OLED daemon's shutdown sudoers grant's exact syntax** - named as
  a requirement in §3, not written, since no sudoers file should be
  drafted for a daemon that doesn't exist yet to name.
- **Power-draw-driven display sleep policy** - depends on Stage 12
  numbers not yet available.

## 6. Testing performed

None against hardware (none exists). This is a pure UX/interaction
design pass, reasoned from Stage 11's already-verified electrical
design and this project's existing, already-tested data sources
(`includes/metrics.php`, `piratebox_get_mode()`) - no new live
verification was possible or needed for a document with no executable
change.
