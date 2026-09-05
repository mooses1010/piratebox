# Operational decisions

This file records intentional configuration/behavior decisions that differ
from the original upstream PirateBox project or from what the README used to
recommend, so a future maintainer (human or AI) doesn't "fix" them back to
the old behavior without knowing why they were changed. Each entry has a
date and the reasoning; if you're going to reverse one, update this file too.

## PirateBox Progression (persistent personality/history system)

**Decision date:** 2026-09-04. Expands OLED Silly Mode (below) into a
persistent, long-term personality/progression subsystem: XP, levels,
cosmetic titles, achievements, lifetime aggregate statistics, a small
rarity-tiered event/reaction engine, bounded "personality weights," a
locally-generated device identity, and clean extension points for
hardware that's purchased/planned but not yet commissioned. Full
implementation detail (including specific hidden/secret content -
deliberately not repeated here, see "What's deliberately not
documented here" below) lives in `piratebox_progression.py`'s own
header and its test suite, `tools/test_progression.py`.

**Architecture: a separate, optional module underneath Silly Mode, not
more conditionals bolted onto the OLED daemon.** `piratebox_oled_
daemon.py` `import`s `piratebox_progression.py` once at startup, inside
a `try/except` - a missing or broken Progression module degrades to
Silly Mode (and the plain serious rotation) working exactly as they did
before this round, never taking the ordinary display down with it.
Progression itself imports no drawing library (no PIL/luma) - it only
ever hands the daemon plain dicts (`{"expression": ...}` or
`{"scene": ...}`, optionally a `quip`) describing what *could* be
shown; only the daemon actually draws pixels. This keeps the whole
subsystem testable with zero hardware and, per instruction, keeps the
daemon itself from becoming "an unmaintainable pile of random
conditionals" - the daemon's own tick loop grew by one delegated call
(`progression.observe_tick(...)`) plus a few `roll_event(...)` calls at
its existing event-detection points, not a parallel decision tree.

**Progression runs independently of Silly Mode's own on/off toggle.**
Lifetime stats/XP/achievements accumulate every tick regardless of
whether the cosmetic display is currently switched on - "how long has
this device been alive, how many visitors has it seen" are facts about
the device, not about whether someone's currently watching its face.
Only the *celebratory display* (a level-up banner, an achievement
popup) is gated: if Silly Mode is off, or the tier is `"emergency"`/
`"fault"` at the moment something unlocks, the reveal is queued
(`pending_reveals`) and surfaces the next time the display is actually
in the ok/warning-tier Silly branch - so nothing is ever lost, and
nothing ever interrupts a fault or an off display.

**Priority model - unchanged, extended consistently.**
`compute_display_tier()` (Silly Mode, unchanged by this round) still
returns `emergency` > `fault` > `warning` > `ok`. Progression's own
tick (stat/XP tracking) runs under every tier including emergency/
fault - an Emergency Mode exercise is itself one of the things
Progression tracks - but every *displayable* consequence (level-ups,
achievement popups, rare/legendary event scenes) is only ever
considered from the exact same ok/warning-tier, Silly-enabled branch
Silly Mode itself already used. Nothing new was added to the priority
ordering; Progression's content is entirely a *citizen* of the
existing `"ok"`/`"warning"` tiers, never a new tier of its own.

**XP / levels / titles.** A progressively-steeper cumulative curve
(`xp_for_level()`, roughly `60 * level^1.55`) - a simulated year of
this Pi's own real chronic-`"warning"`-tier operation with modest
realistic activity reached roughly level 45-50 (a curated cosmetic
title, e.g. an early "Deckhand"-tier name through a senior "Commodore"-
tier one - full ladder in `piratebox_progression.py`'s `TITLES`), with
real headroom left for further years - matching the instruction that
early progression should feel quick while the system stays meaningful
for the long run. **Progression NEVER unlocks or gates any core
PirateBox capability** - every reward is XP, a level, a title, an
achievement flag, a personality-weight nudge, or a suggested Silly Mode
render; nothing here is consulted by networking, Emergency Mode, or
any other PirateBox subsystem.

**Anti-farming, by construction.** A single generic helper,
`award_once()` (cooldown and/or a per-calendar-day cap), gates every
repeatable XP source - reconnecting the same device over and over
cannot produce unlimited XP (directly tested:
`test_repeated_identical_client_arrivals_are_capped_per_day`). A
handful of counters (a new simultaneous-client record, an achievement
unlock) are deliberately left *uncapped* because they're already
monotonic/one-time by construction - they cannot be farmed regardless.
The same `award_once()`-style cooldown mechanism also suppresses a
just-fired rare/uncommon event variant from immediately recurring (see
the event engine below), so rare content stays rare, not just
initially rare.

**Privacy - no new exposure, by construction, not by policy alone.**
Every client-related counter (`total_client_encounters`,
`max_simultaneous_clients`) is derived exclusively from
`status.json`'s existing aggregate `wifi_clients` integer - the exact
same field every OLED page already reads. No MAC address, IP,
hostname, or per-client identity is read, stored, or referenced
anywhere in `piratebox_progression.py`; the data needed to build a
client identity database never reaches this file at all, so it isn't a
policy this module has to remember to honor - it structurally cannot
violate it. SSH activity reuses the exact same `read_ssh_established()`
Silly Mode already added (a live yes/no from `/proc/net/tcp`, no
session content, no logging).

**Rarity/event engine.** `EVENT_FAMILIES` groups alternate reactions
for situations the daemon already detects (a client arriving, waking
from idle sleep, the periodic pirate-flourish beat) plus a fully
opportunistic `"ambient"` family layered on top of ordinary idle
cycling. Each family has a `common` baseline (indistinguishable from
plain Silly Mode most of the time) plus `uncommon`/`rare`/`legendary`/
`secret` alternates gated by some combination of condition (time of
day, idle duration, level, achievement count, a personality weight),
cooldown, and a minimum level - exactly the "combinations of state, not
merely a random roll" the instruction called for. `roll_event()` is a
pure, weighted-random, fully deterministic-given-its-inputs function
(directly unit tested, including a `force_next_event()` test/dev hook
that bypasses weighting entirely - **not wired into the CLI or any
operator-facing path**, so normal use can't accidentally self-spoil
it). A full-year simulation at realistic activity levels produced the
family's legendary variant on a roughly monthly cadence and its rare
variant every few days - rare enough to stay genuinely occasional,
common enough to eventually be seen.

**Personality weights - bounded, deterministic, NOT machine learning.**
Three small floats (`sociability`, `vigilance`, `resilience`), each
updated by a fixed-fraction exponential moving average toward a target
whenever a relevant event occurs (a client arrives, an SSH session is
seen, an Emergency exercise resolves) and clamped to `[0, 1]` -
directly unit-tested for boundedness. These subtly bias which
alternate a family roll favors; they never make a decision a test
can't reproduce exactly given the same state and inputs.

**Device identity.** A short, locally-generated two-word name (e.g. an
adjective + a nautical noun, from two small fixed word lists baked into
this file) is generated once, the first time Progression ever runs, and
persisted - no network call, no personal information, no cloud
registration of any kind.

**Persistence / reliability.** Durable state lives at `/var/lib/
piratebox-oled/progression.json` - real disk, survives reboot and
Silly Mode being off, deliberately **not** `/tmp` (tmpfs would erase
"months and years of real use" every reboot). Writes are atomic (temp
file + `fsync` + `os.replace`, same directory) and coalesced (at most
once every 45s, and only if something actually changed - most ticks do
zero disk I/O). A missing, corrupt, or wrong-schema-version file
degrades to a fresh default state and logs once - this project's
existing "honest default, never fabricate, never crash"
discipline (`docs/ARCHITECTURE.md` §10), applied to a new data store
the same way every other reader in this project already applies it. A
broken `progression.json` can never affect networking, Emergency Mode,
OLED basic status, or any other core function - only Progression's own
optional content is at risk, and only until the next clean default
state is written.

**Permissions - the one narrow write exception this daemon has ever
needed.** `piratebox-oled.service` still runs `ProtectSystem=strict`,
still cannot write anywhere else - `ReadWritePaths=/var/lib/piratebox-
oled` is the single, deliberate carve-out, to a directory `etc/
tmpfiles.d/piratebox-tmp.conf` pre-creates (owned by the same
`piratebox-gpio` account the daemon already runs as, group `gpio` -
which the operator's own account is already a member of, so
`piratebox-silly stats`/`backup` can read the live file directly with
no daemon round-trip; only writes need the single-writer discipline
below).

**Backup / reset / import - explicit, hard to trigger accidentally, single-writer.**
`piratebox-silly` (unprivileged, no sudo, no change to the existing
Silly Mode toggle mechanism) gained four subcommands: `stats` (a plain-
text summary, reads the live file directly), `backup [path]` (a
timestamped copy, defaulting to `~/piratebox-progression-backups/`,
mirroring `tools/backup_piratebox_data.sh`'s own convention for a
different data store), `reset --confirm-i-am-sure` (requires the flag
*and* typing `RESET` back interactively, or an explicit `--yes` for
scripted use - genuinely hard to fat-finger), and `import <file>`. The
CLI **never writes `progression.json` directly** - `reset`/`import`
instead drop a request into the already-bind-mounted `/tmp/piratebox`
(the exact channel Silly Mode's own toggle already established), which
only the OLED daemon notices (a cheap `mtime` check each tick) and
acts on - a single-writer design that makes a torn/concurrent write
structurally impossible. `import` is validated (schema version, field
shapes/types) before being adopted; anything malformed is rejected and
logged with the live state left completely untouched, never partially
applied.

**Hardware signal extension points - deliberately unimplemented.** Per
instruction, no reading is fabricated for hardware that isn't
commissioned yet. `piratebox_progression.py`'s `HARDWARE_SIGNALS`
registry (`register_hardware_signal(name, reader)` /
`read_hardware_signals()`) starts empty and stays empty - a future
commissioning round for the DS3231 RTC, INA226 power telemetry, BME280
environmental sensor, DS18B20 temperature probes, BH1750 ambient
light, a future addressable-RGB status light, or a future GPS/travel
capability registers a real reader there (degrading to `None` on its
own failure, never crashing a tick) and can reference the resulting
value from `ctx["hardware"]` in any new achievement/event condition -
no change needed to the engine itself. A future RGB/lighting round can
reuse `compute_display_tier()`'s and `compute_silly_expression()`'s/
`roll_event()`'s existing output the same way the OLED does, with
Emergency/Fault retaining the same absolute priority - this round
implements no lighting code at all, only keeps that door open.

**What's deliberately not documented here, per instruction:** the
complete achievement list (several hidden/secret ones exist,
undisclosed until unlocked), the exact rare/legendary/secret event
trigger conditions and their probabilities, and the full quip/scene
content. All of it is fully explicit in `piratebox_progression.py`
itself and exhaustively covered by `tools/test_progression.py` (which
must be, and is, completely un-spoiler-shy - secrecy here is an
operator-facing UX choice, not a codebase one) - this operational log
intentionally stops at the architecture level so the operator can
still discover some of it firsthand, exactly as requested.

**Testing:** `tools/test_progression.py` (new, stdlib `unittest` only,
no new dependency) - 52 assertions covering persistence (missing/
corrupt/wrong-schema-version/round-trip/atomic-write/forward-
compatible-merge), the XP/level curve's monotonicity and increasing
steepness, anti-farming (cooldowns, daily caps, and the specific
repeated-reconnect scenario the instruction named), achievements
(including a regression guard for a real modulo-at-zero bug caught
during development), the event engine (family fallback, rarity gating
by condition/cooldown/level, the force-event test hook, every real
render spec across every family actually drawable), the hardware
signal registry's fail-degraded behavior, personality-weight
boundedness, full `observe_tick()` integration, and the reset/import
request protocol end-to-end. `tools/test_silly_mode.py` (28 assertions,
pre-existing) updated for `render_silly()`'s new unified render-spec
interface and re-confirmed passing - no behavior change to anything it
covers. Full five-suite PHP regression (313/313) re-run and confirmed
unaffected (this round touched no PHP). `systemd-analyze verify` and a
tmpfiles.d dry-run both clean before rollout.

---

## OLED Silly Mode

**Decision date:** 2026-09-04. Adds a user-toggleable, substantially
more expressive personality layer to the OLED daemon - inspired by the
general idea of an expressive personality display (Pwnagotchi-style),
but an original PirateBox persona (a face, not a dog; PirateBox-flavored
quips, not stolen phrasing) and explicitly NOT performing or implying
any attack/offensive capability this project doesn't have. Full design
rationale lives in `piratebox_oled_daemon.py`'s own "SILLY MODE" header
comment (this project's established convention: daemon-behavior detail
lives in the script, this log records the decision and why).

**Architecture rule enforced, not merely followed:** Silly Mode is a
*display/personality* state, not a third operational mode - Normal/
Emergency Mode (`/tmp/piratebox/mode`, `set_piratebox_mode.sh`,
`includes/mode.php`) are completely untouched. Silly Mode has its own
separate toggle (`/tmp/piratebox/silly`, `piratebox-silly` CLI - see
below) and is layered entirely inside the OLED daemon's own display
logic; nothing about Normal/Emergency semantics, the two-value mode
file, or any page/PHP code that reads mode changed.

**A real, previously-latent bug found and fixed as a prerequisite, not
new-feature scope creep:** `piratebox-oled.service` has always run with
`PrivateTmp=yes` (added earlier for Pillow's font cache / gpiozero's
notification pipe), which gives it its own *private* `/tmp` - it could
never actually see the real `/tmp/piratebox/mode` `set_piratebox_mode.sh`
writes. `read_mode()` has silently always returned `"normal"` on this
service, regardless of real state, since the day `PrivateTmp=yes` was
added - meaning the existing mode-transition banner and the old
personality-mode gating have never actually reacted to a real Emergency
Mode toggle on this hardware. This was found while investigating how to
guarantee Silly Mode's own mandatory Emergency-priority requirement,
confirmed from first principles (`man systemd.exec`'s own description
of `PrivateTmp=`) and from live evidence (`/tmp/piratebox` did not exist
on this Pi at investigation time, confirming it had never been
successfully read this boot either). **Fixed**: `etc/tmpfiles.d/
piratebox-tmp.conf` now pre-creates `/tmp/piratebox` (root:root 0755,
matching `set_piratebox_mode.sh`'s own `mkdir`/`chmod`) at boot, before
this service starts (via the default `sysinit.target`/tmpfiles-setup
ordering every service gets unless it opts out), and `piratebox-
oled.service` gained `BindReadOnlyPaths=/tmp/piratebox:/tmp/piratebox` -
a live, read-only bind of the real directory into the service's private
namespace. Because it's a bind of the directory (not a one-time copy),
a file created inside it *after* the service starts - a fresh
`sudo ./set_piratebox_mode.sh emergency`, or the new `piratebox-silly on` -
becomes visible immediately, no service restart required. Verified via
`systemd-analyze verify` and a tmpfiles.d dry-run before rollout (see
`docs/CHECKPOINTS.md` for the live post-deploy re-verification).

**Priority model, mandatory and tested** (`compute_display_tier()`):
`"emergency"` (Emergency Mode active) > `"fault"` (status.json missing/
stale, or any Core service down) > `"warning"` (otherwise healthy, but
the known chronic `0x50005` undervoltage condition - see
`docs/POWER-INTEGRITY-DIAGNOSIS.md` - is active) > `"ok"`. Silly Mode is
only ever considered at all when the tier is `"warning"` or `"ok"` -
`"emergency"`/`"fault"` fall straight through to the exact serious-page
code path that ran before this round, unchanged. **The chronic
undervoltage case was deliberately NOT treated as a hard block**, per
instruction: since it's a known, already-extensively-diagnosed,
non-worsening condition (not a new actionable event), Silly Mode may
still run under it - but every Silly frame in the `"warning"` tier
carries a small, fixed, always-drawn badge (top-left corner, boxed `!`)
so the condition stays unmistakable rather than needing the operator to
turn Silly Mode off to notice it. This is a deliberate design choice,
not a loosened safety bar - a real fault or Emergency Mode still fully
suppresses Silly Mode with no badge/blend option.

**Two unrelated personality systems, consolidated into one, per
instruction:** the earlier "Personality Mode" (round 7/8: an always-on-
when-healthy skull-and-crossbones quip page, a client-join celebration,
and uptime milestones, all gated by a single `personality_allowed()`
boolean) is **removed and folded into Silly Mode** rather than kept
alongside it. `personality_allowed()` no longer exists (replaced by
`compute_display_tier()`); the old standalone quip/celebration/milestone
frames are gone. **Real, deliberate behavior change, recorded honestly:**
with Silly Mode off (the default, every boot), the OLED is now *exactly*
the four serious pages and nothing else - no quips ever appear
unprompted, where previously they occasionally did whenever conditions
allowed. This matches the instruction directly ("Default Silly Mode OFF
... don't leave two unrelated personality systems") and is judged a net
improvement: the old quip's gating already silently never fired on this
specific Pi anyway, because `power.undervoltage_now` has been
continuously `true` since before the ALFA even existed - the old
"Personality Mode" has, in practice, never once been visible on real
production hardware. Silly Mode's separate warning-tier handling (above)
specifically fixes that dead-on-arrival problem going forward.

**What Silly Mode actually does, briefly** (full detail in the daemon's
own header): a large monochrome face (two eyes, optional brows, a
mouth) drawn with the same plain Pillow primitives every other page
already uses - no image asset, no new dependency. Twelve expressions:
idle, blink, look-left, look-right (ambient cycling), sleeping/waking
(after `SILLY_SLEEP_AFTER_SECONDS`=10 idle minutes with zero clients),
happy/excited/surprised (client count rising - excited the first client
after zero, surprised a further rise), confused (client count dropping
to zero), smug (ambient, while clients are present), ssh_watch
(occasional, only while an SSH session is actually established), and an
evolved pirate-flourish beat (the old skull-and-crossbones, now paired
with one of ten original short quips, occasional - not a copy of any
other project's phrasing). Reacts to: `wifi_clients` rising/falling
(the same aggregate-only field every other page already reads - no new
per-client tracking, preserving this project's existing privacy
discipline), idle duration (in-memory timer, no new file), and SSH/
admin activity via a new `read_ssh_established()` - a single cheap read
of `/proc/net/tcp(6)` (already-exposed, unprivileged, whole-system
socket state Linux always maintains) checked for local port 22 in state
ESTABLISHED, reporting only a live yes/no for "is anyone connected right
now" - no subprocess, no session content, source IP, or duration ever
read, kept, or logged anywhere, satisfying the "no invasive session
logging" instruction by construction. No new polling and no faster
redraw loop: Silly Mode redraws on the exact same `REFRESH_SECONDS`=3s
cadence as every other page; "animation" is purely which expression a
tick-counter-modulo picks, not a second loop or a shorter sleep. An
occasional real-status "peek" (one of the four serious pages, one tick,
every `SILLY_STATUS_PEEK_EVERY_TICKS`≈60s) keeps glanceable status
honestly reachable without needing Silly Mode off.

**Toggle: `piratebox-silly {on,off,status}`, deliberately unprivileged.**
Silly Mode is a cosmetic desk-toy state, not trusted operational state
like Normal/Emergency Mode, so it does NOT go through
`set_piratebox_mode.sh`'s root-only path or get a `sudoers.d` entry -
the CLI just writes `/tmp/piratebox/silly` directly. The toggle file is
pre-created at boot (owned by `moose`, per the tmpfiles.d rule above)
specifically so the unprivileged CLI can overwrite its content with a
plain write, needing no write permission on the root-owned parent
directory. **Default OFF after every boot** (tmpfs, same rationale as
`MODE_FILE`) - no compelling reason found to persist it, per
instruction.

**Future RGB compatibility, deliberately not implemented now:**
`compute_display_tier()` and `compute_silly_expression()` are pure
functions of already-available state, kept separate from any OLED-
specific drawing code and importing nothing lighting-related - a future
addressable-RGB status light can reuse the same tier/expression values
and just add its own drawing step, with Emergency/Fault retaining the
same absolute priority, without this round needing to guess at that
design now.

**Testing:** `tools/test_silly_mode.py` (new, stdlib `unittest` only, no
new dependency) - 28 assertions covering `compute_display_tier()`'s full
priority matrix, the toggle file's fail-safe parsing (missing/garbage/
case-insensitive, mirroring `read_mode()`'s own discipline),
`read_ssh_established()` against synthetic `/proc/net/tcp`-shaped text
(established vs. listening vs. wrong-port vs. missing table), the
ambient/beat cycling function's determinism, every one of the twelve
expressions (plus every quip) rendering without a drawing exception
across both tiers, and a regression check that the four serious pages
and the mode-transition banner still render unchanged. Full five-suite
PHP regression (313/313) re-run and confirmed unaffected (this round
touched no PHP). `systemd-analyze verify` and a tmpfiles.d dry-run both
clean before rollout.

**Deployed and live-verified (2026-09-04), same day.** The operator ran
the deploy commands by hand (`sudo cp`/`sudo install` for the tmpfiles.d
rule, the daemon, the service unit, and the new CLI, then
`systemd-tmpfiles --create`, `systemctl daemon-reload`, `systemctl
restart piratebox-oled.service`) - outside this session's two narrow
`sudoers.d` grants, same operator-gated pattern every prior OLED daemon
update has used. Independently re-verified after, not trusted from the
operator's report alone: all four deployed files (`piratebox_oled_
daemon.py`, `piratebox-silly`, the service unit, the tmpfiles.d rule)
byte-identical to the repo copies; `piratebox-oled.service` `active
(running)`, clean restart with its new startup log line ("Silly Mode:
user-toggled via /tmp/piratebox/silly...") proving the new code is what
actually started, zero errors/tracebacks; `/tmp/piratebox` now exists
live (root:root 0755, created by the tmpfiles.d rule) with `silly`
inside it (moose:moose 0644) - the PrivateTmp/BindReadOnlyPaths fix
confirmed working in practice, not just by `man systemd.exec`'s
description: the operator ran `piratebox-silly on` and **visually
confirmed the face display appeared on the physical OLED** - which
could only happen if the daemon actually read "on" from
`/tmp/piratebox/silly` through its private-tmp bind, direct behavioral
proof the bind mount works, not merely a clean unit-file syntax check.
Zero new `mt76`/USB/kernel errors across the restart window
(`journalctl -k`). `vcgencmd get_throttled` unchanged at `0x50005`
(this Pi's pre-existing chronic condition, per `docs/POWER-INTEGRITY-
DIAGNOSIS.md` - correctly still present, correctly not attributed to
this change) - meaning Silly Mode is live-verified running in its
`"warning"` tier specifically, exactly as designed: the operator's
description of the face display matches the "warning" tier's expected
persistent corner badge, not a silent failure to reach the `"warning"`
code path. All other services (`hostapd`/`dnsmasq`/`nginx`/`php8.4-fpm`/
`piratebox-button`/`piratebox-status.timer`/`nftables`) confirmed
active, `systemctl --failed` empty, `http://10.0.0.1/` still `200`, the
nftables SSH-protection rule still present and unchanged - Silly Mode
touches none of Core, confirmed rather than assumed. Silly Mode left
**ON** at the operator's own choice, ending this round.

---

## Two-QR PirateBox Onboarding Restored

**Decision date:** 2026-09-03. Reverses part of "QR Onboarding
Simplified to a Single Wi-Fi Code" below (same day) - that entry is
left intact as the historical record of why the simplification was
made; this entry records why it was reversed, not a rewrite of that
history.

**What happened:** the one-QR Help page was reviewed in person by the
operator after being deployed, who preferred the previous two-QR
layout and asked for it back - a genuine, informed UX preference
formed by actually looking at the live page, not a process failure in
the original simplification (that round's own audit and reasoning were
sound; the operator simply decided differently once seeing it).

**Restored exactly**: both QR cards in `help.php`'s "Connect" section -
`qr-wifi.png` (`WIFI:T:nopass;S:PirateBox;;`, standard join-only
payload) labeled "JOIN PIRATEBOX", and `qr-url.png`
(`http://piratebox/`, plain URL payload) labeled "OPEN PIRATEBOX" -
`installer_pi_zero_trixie.sh` generating both again via `qrencode` at
install time, and `piratebox_deploy.sh`/`.gitignore` referencing both
as generated-not-committed assets, same as before the simplification.

**Kept, per instruction - the one thing NOT reverted**: the plain-text
`OPEN &gt; piratebox/` fallback caption under the first (join) QR,
added during the simplification round. This is deliberate redundancy,
not a stand-in for the second QR: a visitor can either scan QR 1, join,
and let the captive portal open automatically (falling back to reading
the printed `piratebox/` text if it doesn't); or scan QR 1, join, then
scan QR 2 to open the site directly. Both paths work independently -
QR 1 plus the printed hostname is sufficient by itself, QR 2 is a
convenient second method, not a requirement. The CSS class that styles
the label above each QR card was generalized from `.qr-join-label` to
`.qr-label` so the same rule cleanly serves both cards' headings
("JOIN PIRATEBOX" and "OPEN PIRATEBOX") rather than reusing a
join-specific name for the open card too.

**Asset audit before restoring** (per instruction - don't just rely on
an orphaned deployed file): this project's deploys are additive-only,
so the live `/var/www/html/public/assets/qr-url.png` from before the
simplification was confirmed to still physically exist on disk
(dated before this round, never deleted, simply no longer referenced
by the live `help.php` or excluded from git tracking once the
simplification landed). It was **not** silently reused as-is - both
`qr-wifi.png` and `qr-url.png` were regenerated fresh, live, with the
exact same `qrencode -s 6 -m 2 "<payload>"` invocation the installer
uses, so the live assets are provably current and reproducible from
source rather than resting on an accidental leftover. Same standard as
the simplification round: no QR decoder is installed on this system,
and none was installed to double-check the pixel-level decode without
an operator go-ahead (project rule) - verification is by construction
(the exact literal payload strings were passed directly to `qrencode`,
a standard, deterministic open-source encoder already used throughout
this project) plus visual inspection of clean finder patterns/contrast
on both codes, not a live scan/decode.

**Verified**: `php -l` clean on `help.php`; `bash -n` clean on both
shell scripts; full PHP regression suite unchanged at 313/313;
`tools/check_library_catalog.py` unchanged at 42/42 (same non-evidence
caveat as before - `help.php` has no dedicated unit tests, this
confirms no other code broke). `.qr-row`'s existing flexbox
(`flex-wrap: wrap`) needed no changes to hold two cards again - it
already handled the two-card case before the simplification and wraps
to stacked cards on narrow/mobile widths via the existing `@media
(max-width: 480px)` rule (unchanged, applies to `.qr-card img`
regardless of card count). Deployed live via `piratebox_deploy.sh`
(real run) and both QR PNGs regenerated live; full live verification
in `docs/CHECKPOINTS.md`.

**Found, not fixed here - flagged separately**: `/usr/local/bin/
piratebox_deploy.sh` (the root-owned, sudo-invocable installed copy)
was discovered stale relative to the repo's own `piratebox_deploy.sh` -
missing several already-committed improvements from 2026-09-02+ (the
VERSION honesty marker, `data/device-history.json`/`data/review-
boundary.json` excludes, this round's new `qr-url.png` exclude). This
round's real deploy was confirmed safe to run against the stale
installed copy regardless (none of the newly-excluded paths exist in
the repo's deploy source right now, and this project's rsync is
additive-only - no `--delete` - so a missing exclude cannot cause data
loss on its own). Re-running `setup_claude_automation.sh` to refresh
the installed copy (documented as idempotent/safe to re-run for exactly
this situation) was attempted but blocked by this session's own
permission classifier as a root-owned system file install - correctly
cautious, not overridden. Left for the operator to run directly
(`sudo ./setup_claude_automation.sh`) at their convenience; not a
blocker on anything deployed in this round.

## Host/Management DNS Isolation Fix

**Decision date:** 2026-09-03. Full detail, live validation evidence,
and restart-cycle testing in `docs/CHECKPOINTS.md` (commit `d719ef0`) -
this entry is the decision record: what was wrong, why, and what
architecture is now in place so it can't recur.

**The bug:** two DNS managers on this box both had implicit,
undocumented claims on `/etc/resolv.conf`, and neither knew about the
other. NetworkManager owns `eth0` (this Pi's management/optional-WAN
interface) and correctly learns real upstream nameservers via DHCP.
dhcpcd owns `pb-ap`'s static AP address and, separately, ships a
**global** (not per-interface) `resolv.conf` hook that rebuilds
`/etc/resolv.conf` from dhcpcd's own DNS knowledge on every dhcpcd
event - restart, lease renewal, `pb-ap` bouncing - regardless of
whether dhcpcd actually manages the interface anyone cares about for
DNS. Since dhcpcd is denied `eth0` (`denyinterfaces eth0`) and `pb-ap`
has no DNS to offer (it's the AP's own static address), every such
event overwrote NetworkManager's real nameservers with nothing. With
`/etc/resolv.conf` empty, glibc's resolver falls back to its documented
default, `127.0.0.1` - and dnsmasq, despite being configured with
`interface=pb-ap`, answers loopback queries **regardless of that
restriction** (a documented dnsmasq quirk, confirmed live with a raw
DNS query straight at `127.0.0.1:53`). dnsmasq's own
`address=/#/10.0.0.1` visitor wildcard then answered every hostname,
including `claude.ai` and `api.anthropic.com`, with `10.0.0.1`.

**Why this matters beyond the immediate incident:** this is exactly the
kind of failure the operator's own framing anticipated - "loss/
restart/reconfiguration of pb-ap, dnsmasq, dhcpcd, NetworkManager, or
the ALFA AP must not silently replace host DNS with PirateBox captive
DNS." It wasn't one misconfiguration, it was an ownership gap: nothing
in this repo or on this live system had ever declared, in one place,
who is allowed to write `/etc/resolv.conf`. Two implicit defaults (NM's
autodetected `rc-manager`, dhcpcd's always-on `resolv.conf` hook)
happened to coexist without conflict until a dhcpcd event exposed the
race - and the installer never even created the NetworkManager
exclusion (`etc/NetworkManager/conf.d/99-piratebox.conf`) or the
`eth0` denial (`denyinterfaces eth0`) on a fresh install, meaning a
brand-new PirateBox would have started life with this same latent
conflict, not just this already-migrated one.

**The fix makes ownership explicit instead of implicit, on both
sides:** `nohook resolv.conf` (dhcpcd.conf) removes dhcpcd from the
picture entirely - it was never supposed to be a DNS source on this
box. `rc-manager=file` (new `etc/NetworkManager/conf.d/
98-piratebox-dns-ownership.conf`) pins NetworkManager's own behavior so
it doesn't silently change if `resolvconf` or `systemd-resolved` are
ever installed/enabled later for an unrelated reason. `except-
interface=lo` (dnsmasq.conf) closes the loopback quirk directly, as a
second, independent layer - even if resolv.conf ownership were ever
broken again by something not yet anticipated, dnsmasq itself can no
longer answer the query that would exploit it. All three are additive,
narrowly-scoped config lines, not a rewrite of any daemon's role in the
architecture: NetworkManager still owns exactly `eth0` and nothing
else (the existing `unmanaged-devices=interface-name:wlan0;
interface-name:pb-ap` line is untouched); dhcpcd still owns `pb-ap`'s
static IP; dnsmasq still owns visitor DHCP/DNS on `pb-ap` with the same
wildcard behavior for every visitor-facing name.

**`bind-interfaces` for dnsmasq was evaluated and deliberately
rejected** as an additional hardening step (literally binding dnsmasq's
socket to `pb-ap`'s own address instead of the default dynamic
wildcard-bind-with-packet-filter, which is what let the loopback quirk
apply in the first place). Live logs from the ALFA migration round
already show dnsmasq logging "interface pb-ap does not currently exist"
at the moment it starts (a boot-ordering race the current dynamic-bind
mode tolerates as a non-fatal warning and recovers from automatically);
`bind-interfaces` needs to `bind()` to that literal address immediately
and could turn a slow-to-enumerate ALFA into a hard dnsmasq start
failure at boot, trading a proven low-severity issue for a plausible
higher-severity one. `except-interface=lo` alone already closes the
actual vulnerability without that risk - not revisited unless a future
round finds a concrete reason `bind-interfaces` is worth that
boot-ordering trade.

**Project integration**, so this can't recur through the normal ways
this system's DNS-adjacent config gets touched again:
`installer_pi_zero_trixie.sh` now installs both NetworkManager conf.d
files and adds `denyinterfaces eth0`/`nohook resolv.conf` to its
dhcpcd block (previously absent - a genuinely fresh install had never
been given this isolation at all); `tools/migrate_visitor_ap_to_alfa.sh`
and `tools/rollback_visitor_ap_to_onboard.sh` (both still STAGED, not
installed) gained an explicit post-restart check for exactly this
failure mode, since both scripts restart dhcpcd as part of their normal
operation.

**Validated live, both sides independently, through a full
NetworkManager+dhcpcd+dnsmasq+hostapd restart cycle** - not left
resting on the initial temporary manual `/etc/resolv.conf` edit, which
was explicitly treated as a recovery measure only and was in fact
overwritten by NetworkManager's own regeneration during validation (a
config reload alone made NM rewrite the file itself, with the same
correct content, proving real ownership rather than coincidental
leftover content). Full detail and every command run: `docs/
CHECKPOINTS.md`, "Host/Management DNS Isolation Fix" entry. No reboot
was performed - service-level restarts of every involved daemon were
judged sufficient evidence for a configuration-based fix (hooks and
exclusions read at every start, not one-time runtime state a reboot
alone would exercise); genuinely reboot-only failure modes remain
unverified and would need a separate, operator-approved reboot to rule
out.

## ALFA Built-In LED Investigated - No Safe Control Path, Closed

**Decision date:** 2026-09-03. Full detail in
`docs/PHYSICAL-CONTROL-UX-DESIGN.md` §8 - this entry is a summary.

Goal was a subtle heartbeat (LED off, one brief blink every ~20-30s) on
the ALFA AWUS036ACM's built-in LED, using a normal kernel interface
only, never a guessed raw register write, never at risk to `pb-ap`.

Investigation confirmed this kernel has full LED support compiled in
(`CONFIG_MT76_LEDS`, `CONFIG_MAC80211_LEDS`, `CONFIG_LEDS_CLASS`,
`CONFIG_LEDS_TRIGGERS` including `LEDS_TRIGGER_TIMER`, which would have
made this trivial via pure sysfs) - not a kernel gap. But no
`/sys/class/leds/` device is ever registered for this adapter. The
only LED-related knob anywhere in its debugfs tree
(`/sys/kernel/debug/ieee80211/phy3/mt76/led_pin`) was tested twice with
the operator watching the physical LED directly - once briefly, once
held at the test value for as long as the operator needed - with **no
visible response either time**. Reading the actual compiled kernel
modules (`strings` on the decompressed `.ko` files) confirmed real
chip-specific LED functions exist in the driver
(`mt76x02_led_set_blink`/`_brightness`/`_config`) but aren't reachable
from any exported symbol or debugfs file; `led_pin` is almost certainly
just a plain field those functions would consult if a classdev existed
- which one never does for this specific adapter, most likely an
EEPROM/board-data limitation of this particular unit (corroborated,
not proven, by large unprogrammed stretches in a debugfs `eeprom`
dump). `regidx`/`regval` (raw MAC/BB register access) were identified
but never touched - no register/value was ever documented to justify
using them, and none was guessed, per instruction.

**Closed with the LED left OFF, exactly as found.** No heartbeat
script, systemd timer, or service was built - there is nothing for one
to safely control, and this project's own rule (avoid raw register
guesses; never risk the AP for a cosmetic feature) rules out the only
other path available. `pb-ap`, `hostapd`, `dnsmasq`, Ethernet, and this
Pi's known `0x50005` power condition were all independently reconfirmed
unaffected before, during, and after both tests.

**Future architecture note recorded, not built:** a future enclosure
RGB/status LED system (once real enclosure hardware exists) should be
mode-aware - Emergency/fault states take priority, future Stealth/
Night/Transport modes must be able to suppress all cosmetic lighting
outright - and if the ALFA's own LED ever becomes controllable by some
other means later, it should represent radio/device activity only and
be subordinate to that same future mode system, not wired into
unrelated services independently. See `docs/PHYSICAL-CONTROL-UX-
DESIGN.md` §8's own closing paragraph and `docs/CAPABILITY-REGISTRY.md`
for the tracked entries.

## QR Onboarding Simplified to a Single Wi-Fi Code

**Decision date:** 2026-09-03. Same-day follow-up to the ALFA
Migration Round above, unrelated in substance (no networking/power
work) - a small onboarding/physical-UX cleanup.

**Audit performed first**, per instruction, before removing anything.
Both existing QR codes are generated by `installer_pi_zero_trixie.sh`
via `qrencode` at install time (not committed - `.gitignore`d), and
displayed side by side in `var/www/html/public/help.php`'s "Connect"
section: `qr-wifi.png` (`WIFI:T:nopass;S:PirateBox;;` - a standard
`WIFI:` join QR for the open network) and `qr-url.png` (plain
`http://piratebox/` - a same-network shortcut to jump to the site once
already connected). Confirmed via the full project history (the
original Phase 5 design entry and a later "QR Code Order Fixed" round,
both in this file) that the URL QR never had any other purpose -  no
pairing, no auth, no companion-device role - so removing it discards
nothing else. The separately-tracked root-level
`PirateBox-wifi-qrcode.png` (used only for GitHub README rendering) is
already Wi-Fi-only, confirmed by its filename, its README section
heading ("## WiFi QR Code"), and the adjacent prose explicitly calling
it "this same Wi-Fi QR code" - no QR decoder is installed on this
system and none was installed to double-check (would need an operator
go-ahead per project rule); this is documentary evidence, not a pixel-
level decode, but it's unambiguous and left that file untouched either
way.

**Removed**: the second (`qr-url.png`) QR and its generation step,
everywhere. `installer_pi_zero_trixie.sh` no longer generates it;
`piratebox_deploy.sh` and `.gitignore` no longer reference it;
`help.php`'s QR row is now a single card.

**Added**, matching the operator's requested hierarchy exactly:
`help.php`'s remaining QR card now shows `JOIN PIRATEBOX` (new
`.qr-join-label` CSS class, bold/accent-colored, sits above the QR)
and `OPEN &gt; piratebox/` (existing `.qr-caption` class, reusing the
existing `.help-url` span for `piratebox/` to match the page's other
URL displays) directly below it. Wording/capitalization/punctuation of
`OPEN > piratebox/` preserved exactly, per instruction. The numbered
"Connect" steps above the QR row already described the right flow
(join Wi-Fi -> wait for captive portal -> if nothing opens, type the
address) and needed no changes.

**Explicitly not done, per instruction**: no nonstandard combined
Wi-Fi+URL QR payload - the surviving QR stays a plain, standards-
compatible `WIFI:` join code exactly as before; the printed
`piratebox/` fallback is deliberately text, not a second code.
`10.0.0.1` was not promoted to the primary printed destination -
`piratebox/` remains canonical, `10.0.0.1` stays documented as a
fallback elsewhere on the page (unchanged).

**Verified**: `php -l` clean on `help.php`; `bash -n` clean on both
shell scripts; full PHP regression suite unchanged at 313/313 (help.php
has no dedicated unit tests - it's a template page - so this confirms
no other code broke, not that the page itself was exercised);
`tools/check_library_catalog.py` unchanged at 42/42; regenerated the
exact surviving payload (`qrencode "WIFI:T:nopass;S:PirateBox;;"`,
same parameters as the installer) and visually inspected the result -
clean finder patterns, high contrast, standard QR structure. `README.md`
updated to match (single-QR description, mentions the `OPEN >
piratebox/` fallback).

## ALFA Migration Round: staged udev rule bug found and fixed on first live install attempt

**Decision date:** 2026-09-03. Full detail in
`docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md` §2 - this entry is a summary.

Operator explicitly approved proceeding with the production visitor-AP
migration to the ALFA AWUS036ACM, deliberately accepting the current
known-marginal power supply per the design doc's "power-aware migration
gate" (item 6's human judgment call). Read-only audit confirmed: `eth0`
up, `wlan0` production AP healthy, ALFA (`0e8d:7612`/`mt76x2u`) present
as `wlan1`, regulatory domain already correct (`country US: DFS-FCC`),
no passwordless root available to this session for any of the
migration's own steps - all executed by the operator directly, per
project rule (networking/system config changes stop for the operator).

Operator installed the two staged system files
(`etc/udev/rules.d/99-piratebox-external-ap.rules`,
`etc/NetworkManager/conf.d/99-piratebox.conf`) and physically replugged
the ALFA to trigger the rename. Result: **the interface came back as
`wlan1`, not `pb-ap`** - the udev rule silently failed to match.

Root cause, confirmed live (`udevadm info -a`, `udevadm test`): the
staged rule's `ATTRS{idVendor}`/`ATTRS{idProduct}`/`DRIVERS==`
conditions can never all match on the same ancestor device for this
hardware - `idVendor`/`idProduct` exist only on the USB *device* node
(`1-1.3`), whose own driver is the generic `usb` composite driver; the
real `mt76x2u` driver binds one level down on the USB *interface* node
(`1-1.3:1.0`), which has no `idVendor`/`idProduct` attribute at all.
udev requires every condition in one rule to match the *same* ancestor
- none ever does here. **This was a structural bug in the originally
committed rule, not a timing issue**: a reboot (the design doc's other
suggested trigger) would have failed identically, since the rule could
never match regardless of when the "add" event fired.

Fix: match the equivalent `ENV{}` properties instead
(`ENV{ID_USB_DRIVER}`, `ENV{ID_VENDOR_ID}`, `ENV{ID_MODEL_ID}`), which
udev already imports directly onto the `net` device itself via the
earlier `usb_id` builtin in the standard rule chain - confirmed present
and correct (`mt76x2u`/`0e8d`/`7612`) against this exact live adapter
via `udevadm test` before writing the fix. No ancestor-walk needed.

**Udev fix confirmed live**, second replug: kernel log recorded `mt76x2u
1-1.3:1.0 pb-ap: renamed from wlan1` directly. `pb-ap` came up cleanly,
`ethtool -i pb-ap` confirmed `mt76x2u`, NetworkManager exclusion
confirmed present, `wlan0` confirmed completely unaffected throughout,
zero new kernel/USB errors from either replug, `vcgencmd get_throttled`
unchanged at `0x50005`.

**Operator then ran the actual migration**
(`sudo PIRATEBOX_MIGRATION_CONFIRMED=yes-I-read-the-design-doc
tools/migrate_visitor_ap_to_alfa.sh`), all 6 preflight checks passed,
and it hung indefinitely at "Validating hostapd config..." (several
minutes, no progress). Read-only investigation from a separate SSH
session (Ethernet, never interrupted) found the exact cause without
touching anything: the script's validation line,
`hostapd -dd -t /etc/hostapd/hostapd.conf | grep -qi "invalid"`, is not
a config-check - **`hostapd`'s `-t` flag means "add timestamps to
debug output," not "test and exit."** This project's own
`docs/IMPLEMENTATION-ROADMAP.md` had already independently noted
elsewhere that hostapd 2.10 has no real config-validate flag - this
staged script's author apparently missed that when writing this line.
With no `-B` and no test-only mode, the command **actually started a
real, live, unmanaged foreground hostapd** bound to `pb-ap`. A
successfully-starting hostapd never prints "invalid" and never exits
on its own, so `grep -qi invalid` never saw a match or EOF - the pipe
blocked forever. Confirmed via full process-tree/`/proc` inspection:
both `hostapd` (real PID, `-dd -t` cmdline) and `grep` were alive and
in normal sleeping state, not deadlocked; no `timeout` wrapper existed
anywhere in the script. **Positive finding preserved deliberately, not
just a failure report:** this ad hoc hostapd instance genuinely
succeeded - `iw dev pb-ap info` showed `type AP`, `ssid PirateBox`,
channel 6, `UP`, and zero kernel/`mt76x2u`/USB errors appeared in
`journalctl -k` for the entire window. **The ALFA cleanly entered AP
mode and beaconed the production SSID during this "failed" attempt** -
strong, real evidence the underlying radio-level migration is sound;
only the validation scripting was broken.

Operator pressed Ctrl+C in the migration terminal as instructed.
Contrary to the expectation that this would abort the whole script
(a plain non-interactive `bash script.sh` normally dies on SIGINT):
**the script actually survived and continued** - `sudo`'s `use_pty`
default gives the script its own pty/job-control context, so SIGINT
killed only the stuck foreground pipeline (`hostapd`/`grep`), not the
script's own interpreter. The script proceeded through its remaining
steps on its own and **genuinely started the real, systemd-managed
`hostapd`/`dnsmasq` bound to `pb-ap`** (`AP-ENABLED` in the hostapd
log, both services confirmed `active`). This was not established by
assumption - independently re-verified live after the fact.

**A second, more serious bug surfaced at exactly this point:
`http://10.0.0.1/` was completely unreachable.** Root cause, confirmed
live: `dhcpcd.conf`'s static `10.0.0.1/24` assignment was still bound
to `interface wlan0`, per this round's original (wrong) design-doc
assumption that `wlan0` would stay "up and idle" post-migration.
`wlan0` actually goes fully **down** once nothing drives it via
hostapd - confirmed (`ip link show wlan0` state `DOWN`) - so nothing
held `10.0.0.1` any more. Meanwhile `pb-ap` has no static block of its
own, so `dhcpcd` applied its ordinary default per-interface behavior
to it: tried a DHCP-client lease, failed (nothing offers one), and
self-assigned a link-local `169.254.53.155` instead (all visible
directly in `journalctl -u dhcpcd`, including dnsmasq's own startup
warning "interface pb-ap does not currently exist"). Confirmed this
was not an nginx problem: nginx listens on `0.0.0.0:80` with no bound
IP and was verified still answering on `127.0.0.1` throughout.

Fixes, all applied to the repo (not yet re-run live as of this
writing): `tools/migrate_visitor_ap_to_alfa.sh` now also moves
`dhcpcd.conf`'s static block to `pb-ap` and restarts `dhcpcd`, drops
the broken hostapd "validation" line entirely (step 5's real live
checks - `type AP`, both services active, `pb-ap` actually holding
`10.0.0.1/24`, a real `curl` - already cover this more meaningfully,
and are now hard failures instead of warnings), and corrects its own
"wlan0 left up and idle" claim to "left down and idle."
`tools/rollback_visitor_ap_to_onboard.sh` gets the symmetric fix (moves
the `dhcpcd.conf` block back to `wlan0`, restarts `dhcpcd` - previously
missing from both scripts' rollback path too) plus the same IP-holding
check in its own verification. `docs/EXTERNAL-AP-ARCHITECTURE-
DESIGN.md` §11/§12 corrected to stop claiming `dhcpcd.conf` doesn't
need to change.

Live state at the time of this writing: real `hostapd`/`dnsmasq` are
active and bound to `pb-ap`, `wlan0` is down, `10.0.0.1` is not yet
reachable (the dhcpcd fix above is written but not yet applied live -
still needs root, per the same project rule as everything else this
round). Ethernet/SSH confirmed unaffected throughout every step of
this entire round, including both hangs.

Nothing production-facing was touched: `wlan0`/`hostapd`/`dnsmasq`
remained the live AP throughout, confirmed unaffected before and after
the replug attempt. No new USB/kernel/SD errors from the replug itself.

**Update: dhcpcd fix applied live, migration validated working.**
Operator ran the two commands above. Confirmed independently: `pb-ap`
now holds `10.0.0.1/24`, `iw dev pb-ap info` shows `type AP`/`ssid
PirateBox`, `curl http://10.0.0.1/` returns the real site (upload form,
storage stats, footer), `wlan0` correctly stays down/idle, zero new
kernel/USB errors, `vcgencmd get_throttled` unchanged at `0x50005`.

**Two more gaps found during validation, both from the same root cause
- staged/designed changes that were never actually live-installed:**

1. `/usr/local/bin/piratebox_status_helper.sh` was still the pre-
   External-AP-Architecture-round version (hardcoded `wlan0` station
   dump), never reinstalled after that round added auto-detection.
   With `wlan0` down, this meant `status.json` had no `visitor_ap`
   block and `wifi_clients` would always read 0 regardless of real
   ALFA associations - breaking client count, OLED, and Device Memory
   simultaneously. Operator ran the exact reinstall command already
   documented in the design doc. Confirmed after: live file identical
   to repo copy, executable, and `status.json` now correctly shows
   `"visitor_ap": {"interface": "pb-ap", "provider": "external",
   "multiple_ap_interfaces_warning": false}`.

2. The deployed web app (`/var/www/html/`) was stamped at commit
   `9e6d9f3` (13:35 that same day) - older than the commit that added
   `piratebox_classify_visitor_ap_provider()` to `capability_state.php`.
   Ran `sudo piratebox_deploy.sh` (one of this session's pre-approved
   NOPASSWD commands, no operator gate needed). Its `--dry-run` first
   reported "DRY RUN (nothing changed)" despite a real, confirmed
   pending diff (56 insertions) - traced to a real (minor) bug in the
   deploy script itself: that message is printed unconditionally
   whenever `--dry-run` is passed, regardless of what `rsync` (run
   without `-v`/`--itemize-changes`) would actually do. Not fixed this
   round (out of scope; noted for the record so a future session
   doesn't trust that message either). Verified the real diff directly
   instead (`git diff` between the deployed commit and current `HEAD`
   for `var/www/html/`, confirmed to be exactly the previously-reviewed
   provider-classifier addition, nothing unexpected) before running the
   real deploy. Confirmed after: `VERSION` now matches current `HEAD`,
   live `capability_state.php` has the classifier, direct PHP
   invocation of `piratebox_get_capability_state()` against real live
   `status.json` correctly returns `ap_network.detail.provider.label`
   = `"external AWUS036ACM (pb-ap)"`, `state: AVAILABLE`. Site still
   `200 OK`, zero failed services after the deploy.

**Third, more serious gap found - a real, previously-undocumented
security control silently stopped working:** validating the operator's
own checklist item "nftables still protects SSH from the wireless
side" turned up `/etc/nftables.conf`, loaded at boot by
`nftables.service`, containing `iifname "wlan0" tcp dport 22 reject
with tcp reset` (comment: "PirateBox wlan0 clients must not be able to
reach SSH"). **This directly contradicts this round's own design doc,
which claimed "no nftables/firewall configuration exists in this
project at all"** - that audit only searched the tracked repo; this
file existed live-only and untracked, the same category of gap as
`etc/NetworkManager/conf.d/99-piratebox.conf` found the same way in an
earlier round. Consequence: this rule protected SSH from `wlan0`
correctly for the project's entire history, then **silently stopped
protecting anything the moment production moved to `pb-ap`** - `wlan0`
traffic no longer exists, so the rule never fires, and `pb-ap` was
never covered by any rule at all. SSH is currently reachable from the
visitor subnet. Fix written and staged, not yet applied live (needs
root, same as everything else this round): `etc/nftables.conf`, now
tracked in the repo for the first time, rewrites the rule as `iifname
!= { "eth0", "lo" } tcp dport 22 reject with tcp reset` - a denylist of
trusted paths instead of an allowlist of "whichever radio happens to
be active today," so it survives any future radio change with no rule
update required, matching the same auto-detection principle already
applied in `piratebox_status_helper.sh`. Syntax validated (`nft -c -f`)
before proposing it. **Not applied by this session** - a firewall
change is squarely "networking/system configuration," which this
project's own rules reserve for the operator regardless of momentary
sudo availability.

**Update: nftables fix applied live and verified, via the correct
workflow.** The operator's first attempt to copy the fix (`cp
etc/nftables.conf /etc/nftables.conf`) failed - the fix existed only on
the `worktree-alfa-migration` branch, not yet merged into `main`, so
the path didn't exist in the primary checkout. `systemctl restart
nftables` had been pasted together with it and ran anyway, but only
reloaded the unchanged (still-broken) live file - confirmed via
`journalctl -u nftables` (clean restart, exit 0) and a fresh `nft list
ruleset` read: no regression, nothing weakened, just re-applied
identically. Correct fix: fast-forward merged `worktree-alfa-migration`
into `main` (`50aa82e` → `b669cca`, clean, no conflicts, pulling in all
three of this round's fixes at once), confirmed the file now present
and byte-identical in the primary checkout, then gave the corrected
path. Operator re-ran it as two separate commands this time. Verified
live: ruleset now reads `iifname != { "lo", "eth0" } tcp dport 22
reject with tcp reset`; `nftables.service` restarted cleanly; both
existing Ethernet SSH sessions confirmed still working; zero failed
services; `pb-ap` still serving correctly (`10.0.0.1/24`, real site
`200 OK`).

**Real client test performed and independently validated server-side.**
Operator connected a phone to the open `PirateBox` SSID, it associated,
got prompted by Android (selected "Only this time"), and loaded
`http://piratebox/` (entered manually) - the real site. While the phone
stayed connected, this session independently confirmed, entirely
server-side:
- `iw dev pb-ap station dump`: a real station (`02:8b:df:c6:b1:e7`),
  `authenticated: yes`, `associated: yes`, `authorized: yes`, strong
  signal (-30dBm), 160s connected, real throughput (41Mbps expected).
- `dnsmasq`'s log: the full DHCP DORA sequence (`DISCOVER`/`OFFER`/
  `REQUEST`/`ACK`) on `pb-ap`, lease `10.0.0.206`.
- `status.json`: `wifi_clients: 1`, `visitor_ap: {interface: "pb-ap",
  provider: "external", multiple_ap_interfaces_warning: false}`.
- `capability_state.php` (direct PHP invocation against the real live
  `status.json`): `ap_network.detail.provider.label` = `"external
  AWUS036ACM (pb-ap)"`.
- The operator's own visual confirmation: the OLED's NETWORK page
  showed 1 client.
- `connection-stats.json` (the persisted, privacy-preserving hourly
  Device Memory input) had not yet rolled over to include this
  connection at check time - confirmed this is expected, not a bug:
  the in-progress hour's count lives only in `status.json`'s tmpfs
  `current_hour_count` (already correctly `1`) until the hour boundary
  passes, by the same design this project already documented for its
  connection-stats feature elsewhere.
- Site pages spot-checked (`/`, `/help.php`, `/chat.php`,
  `/bulletin.php`, `/.well-known/captive-portal`): all `200`.
- `dnsmasq`'s query logging is intentionally disabled (privacy by
  design, confirmed via `dnsmasq.conf`) - no DNS-level captive-portal
  activity is expected to be visible server-side, and none was; the
  DHCP sequence plus the operator's own confirmed page load together
  are the complete expected evidence chain for this project's captive-
  portal mechanism (wildcard DNS + a CAPPORT DHCP option, both
  interface-agnostic by construction - see `docs/EXTERNAL-AP-
  ARCHITECTURE-DESIGN.md` "Captive portal / DHCP / DNS implications").
- nftables' SSH protection was confirmed structurally correct
  (`iifname != {"eth0","lo"}` unambiguously covers `pb-ap`) but not
  empirically exercised against live traffic from that subnet - doing
  so would need an actual connection attempt originating from the
  phone's own network, which is optional client-side verification, not
  required given the rule's static, non-conditional nature.

**Migration is commissioned and real-client-validated as of this
entry.** The separate, still-open power-aware soak evidence bar
(extended multi-hour duration, simultaneous multi-client, sustained
traffic, continuous new-transition monitoring) was never claimed met -
see `docs/IMPLEMENTATION-ROADMAP.md`'s ALFA row and `docs/CHECKPOINTS.md`
for the durable recovery point (`b669cca`) and the explicit distinction
between "commissioned and working" versus "hardened for unsupervised
24/7 production," which remain two separate claims, not one.

## Load-isolation test 2: heatsink fans removed - negative result, plus new direct voltage measurement

**Decision date:** 2026-09-03, same-day follow-up to the ALFA
load-isolation test above. Full detail in
`docs/POWER-INTEGRITY-DIAGNOSIS.md` §9d - this entry is a summary.

Wiring verified first against `docs/CHECKPOINTS.md` and
`POWER-INTEGRITY-DIAGNOSIS.md` §3 (both independently confirm physical
pin 4 (5V) / physical pin 6 (GND), no GPIO involvement, no conflict
with the OLED or shutdown-button pins) before any physical action.

The operator then performed a genuine controlled cold-power-cycle:
held the physical shutdown button for a graceful `systemctl poweroff`,
waited for a full halt, then fully removed and reapplied the USB-A
power input - not a software reboot. Both heatsink fans were
physically disconnected from pins 4/6 throughout the resulting fresh
boot; the ALFA remained physically absent (unchanged from the prior
test). An earlier, uncontrolled interval where the fans happened to
already be unplugged mid-session (not from a fresh boot) was recorded
separately and explicitly not treated as controlled evidence.

Result, independently verified through a confirmed 18-minute window
(closed early by operator instruction before the planned ~22-minute
target, once the operator was satisfied with the direction of the
result and moved to restore normal hardware): `0x50005` unchanged -
bits 0/2 still set, one `Undervoltage detected!` at boot, zero
`Voltage normalised` lines, zero oscillation, zero USB/SD/kernel
errors, all services healthy. Identical signature to every prior
configuration tested this round.

Conclusion: removing both heatsink fans, like removing the ALFA,
changed nothing measurable about the undervoltage condition. The
evidence does not support the fans as a meaningful contributing static
load either.

**New this entry:** the operator took a live DC multimeter reading
directly across physical pin 4/pin 6 in this exact configuration -
first time this project has had a direct analog measurement rather
than only the firmware's binary bit. Observed ~4.7V baseline (only
~70mV above this board's own ~4.63V detection threshold) with brief,
apparently periodic drops to ~3.3-3.5V. `piratebox-status.timer`'s
fixed 30-second cadence (confirmed via `journalctl`), which runs
`iw dev`/`station dump` against the onboard `wlan0` production AP
radio every cycle, is identified as a cadence-matching candidate -
**explicitly not established as cause**, no exact-timestamp
correlation performed, and no configuration change made to test it,
per operator instruction to make no changes this round.

Operator has since physically restored both fans and the ALFA to
normal; PirateBox is back to its full standard hardware configuration
as of this entry. Next controlled variable not decided here, per
instruction - left for the operator's own direction. The timer/Wi-Fi-
poll correlation is flagged as a specific, testable next candidate,
distinct from the static-load candidates already ruled out.

## Load-isolation test 1: AWUS036ACM removed - negative result

**Decision date:** 2026-09-03, same-day follow-up to the brick A/B
test above. Full detail in `docs/POWER-INTEGRITY-DIAGNOSIS.md` §9c -
this entry is a summary.

A read-only audit confirmed current interface/driver/topology state
first (production AP is `wlan0`/`brcmfmac`; the ALFA is `wlan1`/
`mt76x2u`, idle, never bound to hostapd; Ethernet is the Pi's own
internal chip, logically independent of the ALFA though sharing the
same physical 5V input; the ALFA was the only externally-attached USB
device). The ALFA was then physically unplugged live (clean disconnect,
no errors) and the Pi taken through a graceful shutdown (physical
button) followed by a full cold power-cycle at the USB-A power
input - **not a software reboot**, recorded honestly per operator
correction; if anything a more rigorous state reset than a soft reboot
would have been.

**Result, independently verified at a 24-minute window:** `0x50005` -
identical hex value, identical bit pattern, identical single-
continuous-assertion timeline (one detection at 18:44:37, zero
oscillation) to the immediately preceding ALFA-present test. Zero USB/
SD/ext4 errors. Production `wlan0`/services/regulatory domain
unaffected (expected - the ALFA was never carrying production traffic).

**Conclusion: removing the AWUS036ACM entirely changed nothing
measurable.** Per the operator's own framing (the Pi undervolted
before the ALFA ever existed - this test was about contribution, not
root cause), the evidence does not support the ALFA as a meaningful
contributing load, even in true physical absence. Strong conclusion
for this specific claim; does not by itself identify the actual cause.
Next controlled variable not recommended in this entry, per
instruction - left for the operator's own direction.

## Power brick A/B test - negative result

**Decision date:** 2026-09-03, same-day follow-up to the cable A/B
test above. Full detail in `docs/POWER-INTEGRITY-DIAGNOSIS.md` §9b -
this entry is a summary.

Operator gracefully shut down and changed only the power brick: Apple
12W USB adapter → UGREEN GaN multi-port brick, **same** new/higher-
quality cable from the immediately preceding test, all other hardware
unchanged. Per the operator's own note, the UGREEN brick can
renegotiate/reset its USB outputs if another port's load changes, so
nothing else was plugged/unplugged from it during the observation
window.

**Result, independently verified at a ~21-minute window (comparable to
the cable test's ~19 minutes), not inferred from "it booted":**
`vcgencmd get_throttled` still `0x50005` - bits 0/2 (current under-
voltage/throttling) still set. Single continuous assertion since boot,
zero oscillation, zero USB/mt76 resets or errors, zero SD/ext4 errors,
core voltage/temp nominal, production `wlan0`/services/regulatory
domain all unaffected.

**Conclusion: the UGREEN brick does not resolve the condition either.**
Three consecutive real-hardware configurations (old cable+Apple brick,
new cable+Apple brick, new cable+UGREEN brick) have now all shown the
identical active-undervoltage signature. This narrows the field away
from "one specific worn/cheap component" and toward the Pi's own input
connector/power path, or a baseline combined load (GPIO fans + OLED +
ALFA) exceeding what's reaching the Pi under any tested supply chain -
neither proven; no further physical step is recommended without the
operator's own direction, per instruction to report and wait.

## Power cable A/B test - negative result

**Decision date:** 2026-09-03, same-day follow-up to the Power
Integrity Diagnosis round above. Full detail in
`docs/POWER-INTEGRITY-DIAGNOSIS.md` §9a - this entry is a summary.

Power source identified: genuine Apple iPad 12W wall brick + an old,
unknown-gauge Samsung phone micro-USB cable. Per operator instruction,
the cable was isolated as the first controlled variable (a
well-regarded brick paired with a likely-thin, aged phone cable
matched this project's own evidence pattern) - replaced with a
higher-quality cable, same brick, same loads, nothing else changed,
then rebooted.

**Result, independently verified, not inferred from "it booted":**
`vcgencmd get_throttled` still reads `0x50005` - bits 0/2 (current
under-voltage/throttling) remained set through a full ~19-minute
window matched to where the old cable's own oscillation pattern first
appeared. Core voltage/temp nominal, zero USB/mt76/SD/ext4 errors,
production `wlan0` and all services unaffected throughout. **One real,
honestly-recorded difference:** the new cable showed a single
continuous assertion with zero oscillation through that window, versus
the old cable's continuous-then-rapidly-oscillating pattern - not
itself a fix, and not proven to be a meaningful improvement versus
normal run-to-run variability (one reboot's data isn't enough to say).

**Conclusion: the cable is ruled out as a *sufficient* fix.** Per the
operator's own pre-declared plan, **the next controlled variable is
the power brick itself** - not tested, not acted on without the
operator's explicit go-ahead. Production `wlan0`, the regulatory
domain, and the staged ALFA migration architecture were all confirmed
unaffected by this test.

## Power Integrity Diagnosis + Undervoltage Root-Cause Round

**Decision date:** 2026-09-03, immediately following the Regulatory
Domain Correction round (`fda4332`). Full evidence in the new
`docs/POWER-INTEGRITY-DIAGNOSIS.md` - this entry is a summary/index.
**Diagnosis only - nothing physical was changed.** No supply, cable,
connector, fan, or GPIO wiring was touched.

**Bit semantics, independently reconfirmed from this system's own `man
vcgencmd`:** `0x50005` = bits 0, 2 (current under-voltage, current
throttling), 16, 18 (the same, historically) all set. **This is an
actively, currently under-volting condition at every check performed
this round - not merely a sticky historical flag**, a distinction
worth stating precisely since it's easy to misread as "just remembers
an old event."

**New finding this round - an oscillation pattern:** this boot's
`dmesg` shows continuous under-voltage for its first ~19 minutes, then
four rapid detect/normalise flips within about 80 seconds (16:09-
16:10), with no correlated USB, thermal, or session-activity event
found to explain the trigger - recorded honestly as unexplained, not
attributed to anything. The pattern (long stable-bad period, then
rapid flipping) is consistent with a rail sitting very close to the
firmware's detection threshold.

**Consistent cross-session signature, now formally established:**
every time this has been checked - Stage 29's original observation, the
OLED-reconnection episode, and every check this round - downstream
Pi-regulated rails (core, sdram) read nominal and the CPU stays
unthrottled at full frequency while the input-side under-voltage
detector trips. This fingerprint points toward the external supply/
cable path (upstream of the Pi's own regulation), not a failed onboard
regulator - ranked, not proven, in `docs/POWER-INTEGRITY-DIAGNOSIS.md`
§4; a physical A/B supply/cable swap is the test that would actually
confirm it, not performed this round.

**Fan-stall question, answered:** physically plausible as a
contributing transient on an already-marginal rail (real stall/restart
current dynamics for small DC fans), but **not established as the root
cause** - undervoltage was observed continuously and during the
unexplained oscillation with no known fan interaction at either time.
Not tested by deliberately stalling a fan, per instruction.

**ALFA confirmed not the cause:** `0x50005` is identical before the
ALFA was ever purchased, immediately after first connection, and
throughout every subsequent AP/association test on both bands. The one
ALFA-correlated event on record (original insertion disconnect) never
repeated across everything since.

**Filesystem/storage:** clean - zero ext4/I/O errors this boot, 105G
free, root filesystem writable. No SD-specific health telemetry is
available on this card (no `mmc-utils`/`smartctl` installed - not
installed this round, package installs require separate operator
go-ahead).

**Correction to a stale claim found during this round:**
`docs/CAPABILITY-REGISTRY.md`'s undervoltage-monitoring entry
previously said "no persisted undervoltage-event history... not
designed/built now" - that was wrong as of this round's check: `data/
device-history.json`'s `undervoltage_daily` counter is real and
already recording live data (5 events, current UTC-day bucket). Fixed
in that entry directly, and in `docs/IMPLEMENTATION-ROADMAP.md`'s
matching row, which previously said this write path was "unobserved."

**No persistent journal exists across reboots** - still true, still a
pre-existing gap first flagged during the OLED bring-up session,
still not fixed this round (a system-level config change, gated).

**Operator action recommended, not performed:** read the wall brick's
printed output rating and the cable type (`docs/
POWER-INTEGRITY-DIAGNOSIS.md` §8), then consider a physical A/B swap
to a known-good Raspberry-Pi-specific supply/cable (§9) as the test
that would actually confirm or rule out the leading hypothesis. This
document does not purchase, replace, or physically touch anything.

**AWUS036ACM production migration:** still blocked. This round adds
real diagnostic depth but does not constitute the extended soak that
gate requires - and that soak should not be attempted on a supply
already showing a chronic headroom deficit, per instruction not to run
a heavy test on a known-undervolting Pi.

## Regulatory Domain Correction + ALFA Post-Regulatory Validation Round

**Decision date:** 2026-09-03, immediately following the External AP
Architecture + Production Migration Readiness Round (`e5c3ee3`). Full
evidence in `docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md` §6 and §16 - this
entry is a summary/index. **`wlan0` remains the production PirateBox
AP throughout - not migrated.**

**Regulatory domain: fixed, and more complicated than expected.** The
operator ran `sudo raspi-config nonint do_wifi_country US`.
Independently verified rather than trusted from its exit status: the
persistent half worked (`/boot/firmware/cmdline.txt` correctly updated
to `US`), but the **live-apply half did not** - `iw reg get` still read
`country 00` afterward. Reproduced this failure twice (once via
`raspi-config`'s own internal call, once via a direct manual `sudo iw
reg set US` retry) with rfkill, a missing/corrupt regulatory database,
and a timing fluke all ruled out as causes. A **reboot** - not
originally anticipated as necessary - was required to exercise the
boot-time application path, which worked cleanly (single clean ALFA
enumeration, zero new USB/SD errors, power baseline unchanged).
Post-reboot, independently verified: `iw reg get` reads `country US:
DFS-FCC`, a genuine FCC ruleset. `CURRENT-WORK.md` was written before
requesting the reboot (per this repo's own interruption-prone-action
convention) and deleted once this round closed.

**5GHz capability: mapped and validated under the corrected domain.**
Non-DFS (legal now): 36, 40, 44, 48 (UNII-1), 149, 153, 157, 161, 165
(UNII-3). DFS-required: 52-144 (UNII-2/2e) - correctly gated, not
enabled. Genuine 2x2 VHT confirmed, max 80MHz width. A bounded,
isolated, temporary 5GHz AP (`PirateBox-ALFA-5G-Test`, channel 36 - a
non-DFS channel chosen deliberately, per instruction never DFS merely
to prove DFS works) reached `AP-ENABLED`. The operator's phone showed
the SSID and, after entering the password, displayed the same generic
"Couldn't connect to network" message seen during the 2.4GHz round -
judged, per that round's own established lesson, against the AP-side
evidence rather than the phone's wording: `hostapd`'s log shows the
client completing full authentication, association, and the WPA2
4-way handshake **twice** (matching the operator's own confirmation
re-attempt), each followed by a client-side disconnect shortly after -
the same DHCP-timeout abort pattern, not an authentication/radio
failure. **Operator RF gate: PASSED**, per the operator's own explicit
instruction to treat successful AP-side WPA2 evidence as sufficient
despite the phone's generic post-handshake wording. DHCP was
deliberately not added to this test network either, for the same
reason established in the prior round (would require touching
production `dnsmasq`'s shared socket or installing new software, and
wasn't needed to answer the question this test exists to answer). Zero
new `mt76`/USB/SD errors across the entire test window; power baseline
unchanged; production `wlan0` confirmed unaffected throughout and after
a clean teardown.

**VALIDATED 5GHZ CAPABILITY ≠ 5GHZ PRODUCTION DEFAULT.** Band strategy
is unchanged from the prior round: 2.4GHz stays the default/primary
band (phone compatibility, range, emergency/public accessibility, this
Pi's USB2 bottleneck all still apply) - 5GHz remains a legitimate,
now-proven, optional future profile, not something this or a future
migration silently defaults to.

**Power-readiness handoff (not solved here, per instruction):** the
known `0x50005` condition is unchanged across three separate rounds of
real load now (Hardware Validation soak, this round's reboot, this
round's 5GHz test) - one ALFA-correlated event on record total (the
original insertion-time disconnect), never repeated. That's a
reasonably good sign for short, supervised, single-client use - not
evidence of 24/7 readiness. Before trusting the ALFA in production,
this project should collect: an extended multi-hour soak, *multiple
simultaneously* associated clients (every test to date has been one
client at a time, sequentially), sustained ordinary (not synthetic-
stress) traffic, and continuous power/USB/SD monitoring across that
whole window watching specifically for the known baseline bits getting
*worse* under real multi-client load - none of which exists yet.

**Staged migration architecture verified undamaged:** radio-provider
auto-detection still resolves to `wlan0` live; `tools/
migrate_visitor_ap_to_alfa.sh`, `tools/
rollback_visitor_ap_to_onboard.sh`, the udev rule, and the
NetworkManager conf extension are all confirmed unchanged and still
not installed/executed anywhere live. Regression: 313/313 → 313/313
(unchanged - this round re-ran the existing suite to confirm the prior
round's work survived; it did). Catalog unchanged, 42/42.

**Explicitly not done this round, per instruction:** no production
migration, no production `wlan0`/`dnsmasq` edit, no DHCP added to
either isolated test network, no ARS-N19 test, no runtime radio
failover, no second permanent PirateBox network, no power repair.

## External AP Architecture + Production Migration Readiness Round

**Decision date:** 2026-09-03, immediately following the AWUS036ACM
Hardware Validation Round (`9d573f6`). Full design and staged
implementation in `docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md` - this
entry is a summary/index, not a duplicate of that document's content.

**Scope:** architecture and migration-readiness only. **`wlan0` remains
the production PirateBox AP throughout this round** - nothing here
switches it, and the round was explicitly instructed not to.

**What this round produced, all staged/committed but not installed,
enabled, or executed against production:**
- `etc/udev/rules.d/99-piratebox-external-ap.rules` - stable `pb-ap`
  naming for the AWUS036ACM, matched on driver (`mt76x2u`) + USB
  VID:PID (`0e8d:7612`), not enumeration order or USB serial (this
  adapter's serial is generic/blank). A same-model replacement unit
  qualifies automatically - a deliberate choice, not an oversight.
- `etc/NetworkManager/conf.d/99-piratebox.conf` - brought into version
  control for the first time (it existed live-only, untracked,
  throughout this project's history) and extended to exclude `pb-ap`
  alongside the existing `wlan0` exclusion, ahead of any migration.
- `piratebox_status_helper.sh` - connection statistics now
  auto-detect whichever interface is actually in `type AP` state
  (verified live: resolves to `wlan0` today, byte-identical to
  before), instead of hardcoding `wlan0`. This is the one and only
  place in the codebase that ever did a raw interface-named `iw
  station dump` - every other consumer (OLED, admin, status page,
  `capability_state.php`) only ever reads the resulting integer, so
  fixing this one call site was sufficient for the whole chain.
- `includes/capability_state.php` - new `piratebox_classify_visitor_
  ap_provider()` (pure, tested) and `ap_network.detail.provider`,
  reporting which radio is currently serving without changing the
  public-facing summary or the existing top-level `ap_network` state
  semantics.
- `tools/piratebox_radio_select.sh` - staged boot-time decision script
  (external if `pb-ap` present and not rfkilled, else onboard);
  deliberately does not itself touch hostapd/dnsmasq, and is not wired
  to any systemd unit. Runtime (post-boot) automatic fallback was
  explicitly scoped OUT of this round as a later stage - the risk of
  two DHCP/AP instances racing, or flapping on a marginal USB
  connection, needs its own soak-backed design, not a boot-time
  script's worth of logic.
- `tools/migrate_visitor_ap_to_alfa.sh` / `tools/
  rollback_visitor_ap_to_onboard.sh` - the actual migration, written in
  full (preflight checks, backup, interface= rewrite in `hostapd.conf`/
  `dnsmasq.conf` only, live verification) but gated behind an explicit
  environment-variable confirmation plus an interactive prompt, so it
  cannot run by accident or by a future session mistaking "staged" for
  "approved."

**A real, pre-existing bug found during this round, unrelated to
anything this round introduced:** `/boot/firmware/cmdline.txt` already
contains `cfg80211.ieee80211_regdom=UM` - not `US`. `UM` (US Minor
Outlying Islands) is a real ISO 3166 code but has no entry in
`wireless-regdb`'s actual database, so the kernel silently falls back
to the generic `world`/`00` regulatory domain - confirmed live via
`iw reg get` still reading `country 00` despite the kernel command line
naming a country. This fully explains why every 5GHz channel showed
`(no IR)` during the Hardware Validation Round. Not fixed here - it's a
boot-configuration file, squarely an operator action - exact commands
are in `docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md` "Regulatory domain."

**Band/antenna strategy, decided:** 2.4GHz stays the default/primary
band even after a future migration (phone compatibility, range,
emergency/public accessibility, and this Pi's own USB2 bottleneck all
point the same way) - 5GHz is documented as a legitimate optional
future profile, not a default, and is blocked anyway until the
regulatory-domain bug above is fixed. The two stock ALFA dual-band
antennas stay the production candidate baseline; the operator's single
ARS-N19 (2.4GHz-only, unmatched) stays explicitly excluded, per
instruction.

**Power-aware migration gate, defined but not run:** extended
multi-hour soak, multiple simultaneous clients, sustained (not
synthetic-stress) traffic, continuous USB/power/SD error monitoring
across that whole window - see the design doc's own section 8 for the
full bar. The known `0x50005` condition is unchanged, unsolved, and not
attempted this round, exactly as instructed.

**Regression:** 305/305 → **313/313** (8 new synthetic tests for the
new classification logic, no hardware/live ALFA required to run them).
Catalog unchanged at 42/42 (no content work this round).

**Implementation boundary honored:** no production `hostapd`/
`dnsmasq`/`dhcpcd` file was edited live. No permanent or temporary
ALFA AP was enabled (correctly - the previous round's isolated test AP
was already torn down before this round began). `piratebox_status_
helper.sh`'s live reinstall was written up as backward-compatible and
low-risk but deliberately not performed - treated as an operator-gated
system-file install regardless of how safe the diff is.

**Exact operator gate for eventual migration:** see `docs/
EXTERNAL-AP-ARCHITECTURE-DESIGN.md`'s own closing section - in short,
fix the regulatory domain, install the two staged system files, satisfy
the power-aware gate, then explicitly run the staged (confirmation-
gated) migration script. Do not begin without the operator saying so.

## AWUS036ACM Hardware Validation Round

**Decision date:** 2026-09-03, following Round 9's post-power-outage
closure (`fee3e9b`). Hardware validation only - **`wlan0` remains the
production PirateBox AP; no migration happened or is planned by this
entry.** Executes the test plan written in "Ordered: ALFA AWUS036ACM"
below, now that the hardware has actually arrived and been connected.

**Identification (live, not assumed from the purchase):** `lsusb` shows
USB ID `0e8d:7612`, MediaTek Inc. MT7612U 802.11a/b/g/n/ac Wireless
Adapter - matches the expected chipset. `lsusb -t` shows it on
Bus 001, nested under the onboard hub, at USB2 480M high-speed (the
Pi 3 B+'s USB2-only ceiling applies regardless of the adapter's own
USB3 capability). Enumerates as `wlan1`. Driver `mt76x2u` (mainline
in-tree, confirmed via `ethtool -i` and `lsmod` - no DKMS/vendor
module). Firmware loaded per dmesg: ASIC revision `76120044`, ROM
patch build `20141115060606a`, firmware version `0.0.00` build 1.

**Insertion/soak history (dmesg + journalctl, this boot):** the
previous test adapter (TP-Link TL-WN722N V2, USB ID `2357:010c`,
`rtl8xxxu`) was still physically connected at boot and was later
unplugged; the ALFA was plugged into the same physical port afterward.
At first enumeration, the ALFA disconnected and re-enumerated once,
~11 seconds after appearing, coincident with a single `mmcblk0`
(SD card) read I/O error and one `dwc_otg` USB host-controller
transfer-timeout warning - a cross-subsystem pattern (a USB WiFi event
and an unrelated SD-card event at the same instant) that points to a
momentary power-rail sag at insertion rather than an mt76 driver/
firmware fault. No firmware crash or repeated failure was observed;
after the single re-enumeration the adapter ran cleanly for the rest
of the session, including through live AP beaconing.

**Power baseline - distinguishing chronic from new:** `vcgencmd
get_throttled` reads `0x50005` (under-voltage detected now and since
boot, throttled now and since boot) - **identical to the value
recorded before the ALFA was ever connected** (Round 9's post-outage
recovery, no ALFA present). This is the project's known, pre-existing
chronic condition, not something the ALFA introduced. The one
insertion-time disconnect above is the only evidence found that is
specifically time-correlated with the ALFA; it did not recur, and the
throttled reading did not change under subsequent AP-beaconing load.
Per standing instruction, this power problem was not investigated
further or fixed.

**Wireless capability, confirmed empirically:** `iw phy3 info` lists
`AP` among supported interface modes (also `monitor`, `IBSS`, `mesh
point`, `P2P-client/GO`). This was then proven, not just read off the
capability list, exactly as step 3 of the test plan below requires:
a live `hostapd` instance (isolated config, not the production file)
reached `AP-ENABLED` and beaconed a real SSID. Contrast with the
TL-WN722N V2, which returned `EOPNOTSUPP` on the equivalent probe (see
its own entry above) - the ALFA's mainline-driver AP support is real,
not merely advertised. 2.4GHz channels 1-11 are usable for
transmission under the Pi's current (world/`00`) regulatory domain;
12-14 are not. VHT (802.11ac) capability is present on 5GHz with
RX/TX MCS 0-9 on 1 and 2 streams (genuine 2x2), but **every 5GHz
channel currently shows `(no IR)`** under the active regulatory
domain, so a legal 5GHz AP test needs a separate, deliberate
regulatory-domain decision - not attempted this round.

**NetworkManager ownership:** `wlan1` is NetworkManager-managed by
default (only `wlan0` is excluded, via the live-only
`/etc/NetworkManager/conf.d/99-piratebox.conf`, which is not tracked in
this repo). NetworkManager's own wifi radio switch was globally
`disabled` throughout this session, so nothing auto-associated it.
Recommend adding `wlan1` (or a MAC/driver-based match, since USB
enumeration order could change which kernel name it gets) to the same
exclusion before any future production migration - not done this
round, since it wasn't needed to keep the test isolated.

**Isolated AP test (step 5-6 of the plan below):** ran a temporary,
non-persisted `hostapd` (config and PID lived only in the session's job
tmp directory, never `/etc/hostapd/`) bound to `wlan1`, SSID
`PirateBox-ALFA-Test`, WPA2-PSK, 2.4GHz channel 6, isolated IP
(`10.99.99.1/24`, assigned via a plain `ip addr add`, not through
`dhcpcd`). No DHCP server was started for the test - the production
`dnsmasq` already binds UDP/67, and standing up a second DHCP scope
without touching production config was judged higher-risk than the
test needed; the goal was to prove the adapter can create and sustain
a real WPA2 AP, which `AP-ENABLED` plus stable beaconing already
demonstrates independent of full IP connectivity. `wlan0`/production
hostapd were confirmed untouched and still serving `PirateBox`
throughout.

**Operator RF gate - resolved.** The operator tested the isolated
`PirateBox-ALFA-Test` AP from a phone and a laptop. The phone's own UI
reported "Couldn't connect to network," which first looked like an
association failure - but `hostapd`'s own log told a different, more
precise story: the client completed authentication, association, and
the **full WPA2 4-way handshake** (`EAPOL-4WAY-HS-COMPLETED`) three
independent times (two different randomized client MACs, consistent
with normal per-network MAC-privacy behavior on modern phones). One of
those clients was observed live via `iw station dump` while still
connected: `authenticated: yes`, `associated: yes`, `authorized: yes`,
signal **-17 to -25 dBm** (excellent, expected at close range), zero
tx/rx retries or failures. Each client disconnected itself shortly
*after* its handshake completed - the signature of a phone's own
DHCP-timeout abort behavior, not a security or radio rejection. This
test network deliberately had no DHCP server. A same-style temporary,
isolated DHCP responder was attempted (`dnsmasq --bind-interfaces`,
scoped to `wlan1` only) specifically to rule this in or out further,
but it failed to bind - dnsmasq's DHCP component claims the wildcard
socket regardless of `--bind-interfaces`, and the production `dnsmasq`
instance already holds it. Completing a real DHCP/IP-layer test would
have required either editing production `dnsmasq`'s config or
installing a second DHCP implementation - both explicitly ruled out by
the operator for this round, and neither was needed: the 802.11/WPA2
association-layer question this round exists to answer was already
settled, independently, three times over, before DHCP ever entered the
picture. **The phone's "Couldn't connect" message is recorded
accurately as client-side behavior following a successful WPA2
association on an intentionally DHCP-less test network - not as an
AWUS036ACM authentication or radio failure.**

Post-test verification, after cleanly tearing the test AP down
(`hostapd` stopped, test IP removed, `wlan1` back to a bare `type
managed` state with no IP): zero new `mt76x2u`/USB events appear in
`dmesg` anywhere across the association attempts, the failed DHCP-bind
attempt, or the teardown itself - the only USB reset/disconnect
activity in the entire session remains the single insertion-time event
recorded above. `vcgencmd get_throttled` is still `0x50005`, unchanged
throughout. `wlan0`/production `hostapd` and all six Core/OLED/button
services were re-confirmed active and unaffected; `systemctl --failed`
is empty.

**Recommendation, final for this round: hardware, driver, and
802.11/WPA2 AP-association capability VALIDATED for a future
migration decision.** `wlan0` remains the production PirateBox AP -
this entry does not adopt the ALFA, and does not claim a full
DHCP/IP-layer or multi-client/throughput test was performed (it
deliberately wasn't - see above). A future migration decision should
still budget for: standing up real DHCP service on whichever interface
ends up serving clients (a normal, expected production step, not a
defect found here), persistent interface naming so USB enumeration
order can't silently swap radio roles, and the same power caveat
carried forward from this round.

**Explicitly not done this round, per instruction:** no production
migration, no `hostapd`/`dnsmasq`/`dhcpcd`/NetworkManager production
config edits (the one attempted temporary DHCP responder failed to
bind and touched nothing), no second DHCP implementation installed, no
5GHz test (blocked by regulatory domain as above), no persistent
interface naming/udev rule, no attempt to fix the chronic undervoltage
condition, no AWUS036ACM antenna swap (ARS-N19 not
involved - stock dual-band antennas only, per instruction).

## Round 9: Theme Selector Regression - Root Cause and Fix

**Decision date:** 2026-09-03. The operator reported, from real use on
real hardware, that round 8's theme selector didn't actually work:
picking a theme changed the dropdown's own displayed text but nothing
about the page's appearance, and the choice was gone (selector back to
"Default") on the very next page. Round 8's own verification never
caught this - it checked that `<option>` markup rendered via `php -S`
and computed WCAG contrast from hand-typed hex strings, neither of
which could ever detect a real browser-runtime failure. Treated as a
confirmed real bug from the first message, not re-litigated.

**Investigation, in the order it was actually ruled out (this project
has no real or headless browser available, so every step below is
static/structural verification, not a browser observation - see the
"What remains operator-visual verification" note at the end):**

1. **CSS structurally sound.** A full brace-balance parse of
   `styles.css` (comments stripped first) confirmed the file has zero
   unmatched braces anywhere, and each of the five `:root`/
   `:root[data-theme="..."]` blocks is exactly one well-formed rule -
   ruled out a stray brace elsewhere in the 1600+ line file silently
   breaking everything after it.
2. **JS structurally sound.** Re-read `scripts.js` end to end; the
   restore-IIFE, the `<select>`-sync code, and the `change` listener
   are all correctly formed, reference the same `PIRATEBOX_THEME_KEY`/
   `PIRATEBOX_THEMES` values, and the early-restore IIFE genuinely
   executes before the `DOMContentLoaded` listener in source order (it
   has to - this is top-level synchronous code).
3. **No duplicate rendering.** Every one of the 25 pages that include
   `includes/navbar.php` does so via exactly one `require_once` call -
   ruled out two `<select id="themeSelect">` elements existing on one
   page with the JS listener silently attached to the wrong (e.g.
   hidden) one.
4. **No ID/key typos.** Byte-compared the literal string `themeSelect`
   between `includes/theme.php` (where it's rendered) and
   `scripts.js` (where it's queried) - identical.
5. **CSS specificity checked, not assumed.** `:root[data-theme="x"]`
   (one pseudo-class + one attribute selector, both class-level) is
   provably higher specificity than plain `:root` (one pseudo-class
   alone) under the CSS spec - the override rule really would win in
   any standards-compliant browser, given the attribute is actually
   set on `<html>`.
6. **Root cause found: no `Cache-Control` on static assets at all.**
   `curl -sI http://localhost/assets/scripts.js` returned only
   `Last-Modified`/`ETag` - no `Cache-Control`, no `Expires`, anywhere
   in `/etc/nginx/sites-available/default`'s `location /` (the block
   every static asset request actually falls through to; the one
   `add_header Cache-Control "private, no-store"` in the file is
   scoped to the exact-match `/.well-known/captive-portal` location
   only, not to `/assets/`). With no explicit directive, browsers fall
   back to *heuristic* freshness (commonly a fraction of the time
   since `Last-Modified`) - meaning a browser that had visited this
   PirateBox before round 8's deploy could keep silently reusing its
   OLD cached `scripts.js`/`styles.css` (from any earlier round, with
   no theme code at all) for an unpredictable, browser-specific
   window after the new versions were deployed, with **no visible
   error of any kind**. This exactly and completely explains every
   symptom reported: the `<select>` still shows a new choice because
   that's native `<select>` behavior requiring zero JavaScript; there
   is no visual change because the *cached, stale* JS has no listener
   to fire; nothing persists because the stale JS never calls
   `localStorage.setItem`; and every fresh page load shows "Default"
   again because a `<select>` with no `selected` attribute on any
   `<option>` simply displays its first option, which happens to be
   the one named "Default."

**The fix:** `etc/nginx/sites-available/default` gained a
`location ^~ /assets/ { add_header Cache-Control "no-cache" always; }`
block. `no-cache` (despite the name) does not disable caching - it
means the browser must revalidate with the server (a fast conditional
GET against the current `ETag`/`Last-Modified`) before reusing any
cached copy, on every use. That revalidation is exactly what a
heuristic-freshness browser can skip for a stretch of time with no
explicit directive present - adding it closes the actual gap: a
deploy's new `ETag` is now detected on the very next load, not after
an unknowable delay.

**Deliberately not done:** no second theme mechanism layered on top
(the existing localStorage/`data-theme` architecture was never the
problem), no cache-busting query-string/versioned-filename scheme
added on top of the `no-cache` header (redundant - `no-cache` alone
already guarantees correctness after every deploy, at the HTTP
protocol level, for any spec-compliant browser), no change to
`includes/theme.php`, `assets/scripts.js`'s theme logic, or any
`:root[data-theme]` block - all of it was already correct.

**Regression coverage added:** `tools/test_theme_system.php` - checks
things a browser test would actually need to be true, not just that
files/strings exist: the PHP/JS theme-id lists match exactly, every
JS-declared theme has a matching CSS block and vice versa (no orphans
either direction), every theme's CSS block redefines every token the
base `:root` defines (an incomplete theme silently inherits stray
default-theme colors for whatever it omits - not a crash, but a real,
easy-to-miss bug this test would catch), the CSS specificity math
itself, the early-restore IIFE's position relative to
`DOMContentLoaded` in source order, and that
`piratebox_render_theme_switcher()`'s actual rendered `<option>`s
match `PIRATEBOX_THEMES` exactly via the real function, not a
hand-copied expectation.

**What remains operator-visual verification, honestly:** this
project has no real or headless browser available in this
environment, so nothing above can *prove* a real browser now
switches themes correctly - it proves every statically-checkable
precondition for that to work is now true, and it identifies and
fixes the one real defect found (the missing cache header) with a
complete causal explanation for every symptom reported. Confirming
five visibly distinct themes and persistence across real page loads
in an actual browser, after the operator's browser has done one hard
refresh (or after enough time for any old heuristic-cached copy to
have expired) to pick up both the code and the corrected cache
header, is the one verification step this round cannot perform
itself.

## Lightweight Theme System

**Decision date:** 2026-09-03, Round 8. A small, curated set of
presentation-only appearance variants for the public UI, explicitly
scoped to avoid becoming a settings dashboard or a UI-framework
adoption.

**Why this is architecturally NOT modeled on `includes/i18n.php`, even
though the two selectors sit side by side in the navbar:** i18n has to
be resolved server-side because it changes what *text* the server
sends - there's no way to pick a locale in the browser after the HTML
has already been generated in the wrong language. A theme changes
nothing about the HTML or its content, only which CSS custom-property
*values* apply to that same markup - a presentation-only concern with
no reason to touch PHP, sessions, or cookies at all. So there is no
`piratebox_get_theme()`, no theme cookie, no server-side render
branch, and no new PHP file holding logic (`includes/theme.php` exists
only to keep the theme-id -> label list in one place for
`navbar.php`'s `<select>`, not to make any decision). The entire
mechanism - reading a saved choice, applying it, persisting a new one
- lives in `assets/scripts.js`, using one `localStorage` key
(`piratebox_theme`) and a `data-theme` attribute on `<html>`.

**Privacy properties, by construction rather than by policy:** the
only state is that one browser-local key, in that one browser, on that
one device. It is never sent to the server (no cookie, no query
parameter, no fetch), never visible to any other visitor, and doesn't
survive a private-browsing session or a different browser on the same
device - exactly the "no accounts, no tracking/profile system" scoping
this round's instructions asked for, and a deliberately different
mechanism from i18n's cookie (which *is* sent to the server on every
request, because the server needs to know which dictionary to read).

**Implementation:**
- `var/www/html/public/assets/styles.css`: every theme-relevant
  structural color (page/panel backgrounds, primary/muted text, the
  accent color and its hover state, input backgrounds, borders, and
  the three status colors - warning/danger/success) was converted from
  a hardcoded hex value to a `:root` custom property, holding exactly
  the previous hardcoded value as the default. A handful of
  intentionally-fixed colors were left alone on purpose: the world
  reference map's own light basemap colors (a map should look like a
  map regardless of theme), the QR-code and scanned-document-figure
  white backgrounds (need real white for scannability/paper fidelity),
  the four fixed Bulletin Board category pill colors (decorative
  category coding, not theme chrome), and the admin panel's
  `.danger-button`/`.maintenance-zone` deep-red styling (this round's
  instruction scoped theming to the *public* UI; no visitor ever sees
  the admin panel, and an operator's admin session shouldn't have its
  destructive-action coloring change based on a visitor-facing
  preference toggle anyway).
- Four additional themes are defined as `:root[data-theme="..."]`
  blocks at the end of the same file, each nothing but a redefinition
  of those same tokens: `terminal` (green-on-dark), `amber`
  (amber-on-dark CRT), `lowlight` (dim, warm, low-blue-light for
  night-friendly use), and `pirate` (a tasteful light parchment-and-ink
  theme - deliberately readable, not a costume font). No theme
  duplicates a single component rule.
- `assets/scripts.js`: theme application runs *before* the
  `DOMContentLoaded` handler, at the top of the file - this script
  loads synchronously in every page's `<head>`, so `document.
  documentElement` already exists by the time it runs but nothing has
  been painted yet, which avoids a flash of the default theme before
  switching to a saved one. Every `localStorage` access is wrapped in
  `try`/`catch` (private browsing or disabled storage throws rather
  than returning null in some browsers) - failure always falls back to
  the plain default theme, never a broken page.
- `includes/navbar.php` renders the `<select>` (via `includes/
  theme.php`'s `piratebox_render_theme_switcher()`) with no
  server-known "current" value; `scripts.js` sets its displayed value
  from `localStorage` on load. With JavaScript disabled, the select
  simply shows its first option and does nothing when changed - an
  inert, safe fallback rather than a broken control.

**Emergency Mode:** deliberately does NOT reset or override a visitor's
chosen theme - per instruction, activating Emergency Mode must not
change a browser-local preference the visitor set for themselves.
Emergency Mode's own visual treatment (`.hero-emergency`, `.status-
bad`, etc.) already reads through the same `--color-warning`/
`--color-danger`/`--color-success` tokens as everything else, so it
automatically gets a theme-appropriate warning treatment in every
theme without any theme needing its own separate emergency override.

**Accessibility:** all five themes (four dark, one light) were chosen
for real text/background contrast, not just a different hue -
including the two brightest accents (Terminal's green, Amber's amber)
being used as light-text-on-dark rather than the reverse, which is
where a "glowing on black" aesthetic most often loses readability.

## Trust/Transparency Statement + Lightweight Multilingual Foundation

**Decision date:** 2026-09-03. Two small, bounded site-level additions
made alongside Reference Library Round 6, per explicit instruction not
to let them become their own projects or displace the library work.

**Trust statement:** a stranger joining an unfamiliar open Wi-Fi
network has reasonable cause to wonder what it's actually doing.
Added a short, subtle line to the shared footer (`includes/
footer.php`, shown on every page) - "**Nothing up our sleeve.** This
box does what it says, and nothing behind your back." - linking to a
new "Trust & Transparency" section on the Help page
(`help.php#trust`). Deliberately NOT a banner or a security-scare
disclaimer - same muted styling as the rest of the footer.

**Every claim in that section was verified against this device's
actual configuration before being written, not assumed from the
desired architecture:**
- *No HTTPS/encryption interception* - confirmed no `ssl_certificate`
  or port-443 config anywhere in nginx; this device literally never
  terminates TLS, so there's no cert to install and no way for it to
  inspect encrypted traffic. Matches the existing Android/Samsung help
  note ("you do not need to install any certificate").
- *No cloud account* - architecturally true by construction (no
  external API calls anywhere in the codebase for core functionality).
- *Captive-portal redirect is local-only* - confirmed
  `/etc/dnsmasq.conf`'s `dhcp-option=114` points at
  `http://10.0.0.1/.well-known/captive-portal`, served by nginx on
  this same device, nothing external.
- *Aggregate-only connection stats* - read `piratebox_get_connection_
  stats()` directly: hourly counts/peaks only, no MAC address, device
  name, or per-visitor record anywhere in `data/connection-stats.json`
  or `status.json`.
- *Device ID isn't hardware-derived* - `tools/generate_device_id.sh`'s
  own header states it draws from `/dev/urandom`, explicitly not from
  any MAC address, Pi serial, storage serial, or hostname.
- *No persistent visitor-tracking cookie* - confirmed no `setcookie()`
  calls anywhere before this decision; the only cookie was PHP's
  default ephemeral session cookie (CSRF token only, no identity).

**Lightweight multilingual foundation (`includes/i18n.php`):** one
canonical site, no per-language copies. Translatable strings live in
flat `data/i18n/<locale>.json` dictionaries (`en.json` is canonical/
fallback); `piratebox_t('key')` looks up the current locale, falls
back to English on a missing key, and falls back to the raw key on a
genuinely missing string (a visible bug marker, not a silent blank).
Locale selection precedence, manual always winning: an explicit
`?lang=` click (sets a plain, non-tracking 1-year preference cookie,
`piratebox_lang`) > that cookie on later requests > `Accept-Language`
header parsing on a first visit with no cookie yet (also becomes
sticky via the same cookie) > English default. A small "&#127760; EN /
ES" switcher is in the nav on every page, both options always visible
so returning to English is never more than one click.

**Bounded scope, per instruction - this is architecture-plus-a-
representative-slice, not a full site translation:** English and
Spanish are populated for nav labels (7 items), the Emergency Mode
banner, the footer (including the new trust statement), and the Help
page's Connect steps and full Trust & Transparency section - the
content a stranger is most likely to need in an emergency before they
can read English well. The Reference Library's retained source
documents, Chat/Bulletin/Logbook user content, and the deterministic
Field Tools' calculation logic were deliberately NOT touched -
retained documents stay in their original/authoritative language (an
agency's own official translated edition, if one exists and is
separately redistributable, would be a distinct catalog entry, not a
machine translation presented as equivalent), and user-generated
content is never silently machine-translated. Extending translated
coverage to more pages later is adding keys to the two JSON files and
calling `piratebox_t()` in the template - no architecture change
needed.

**Verified, not assumed:** full five-suite regression (287/287)
unaffected by the shared `navbar.php`/`footer.php` change; 9 diverse
pages spot-checked (home, chat, logbook, bulletin, help, and four
Utility pages) all still return 200 with no PHP warnings; explicit
`?lang=es`, cookie persistence across a later request with no query
param, `Accept-Language` auto-detection, and a manual override
correctly beating a conflicting `Accept-Language` header were all
tested directly via `curl`, not just reasoned about.

## QR Code Order Fixed to Match Actual First-Time-Visitor Sequence

**Decision date:** 2026-09-02. The operator noticed during real-device
testing that Help's two QR codes were presented backwards relative to
what a first-time visitor actually needs: the page showed "open
PirateBox" (the URL QR) before "join the Wi-Fi" (the network QR),
even though joining the Wi-Fi is the step that has to happen first for
the URL QR to be useful at all - the numbered text steps immediately
above the QR row already had the right order (join Wi-Fi, then open a
browser), only the QR row itself was reversed.

**Fixed in `help.php`**: swapped the two `<div>` blocks (Wi-Fi QR now
first, URL QR second) and added explicit "1 - Connect to the
'PirateBox' Wi-Fi" / "2 - Open PirateBox" captions so the sequence is
unambiguous even without reading the numbered steps above. **No QR
payloads were regenerated** - both existing images/strings
(`WIFI:T:nopass;S:PirateBox;;` and `http://piratebox/`) were already
correct; this was a presentation-order fix only. `http://10.0.0.1/`
remains the documented fallback in the same section, unchanged.

**Audited every other place these QR codes/order are referenced**
(per instruction) and found only one other place order was encoded at
all: `installer_pi_zero_trixie.sh`'s `qrencode` generation lines,
reordered to match (Wi-Fi generated first) for source-reading
consistency only - generation order has no effect on the two
independently-named output files, so this was cosmetic, not a
functional fix. `README.md`'s "WiFi QR Code" section already leads
with the Wi-Fi QR ("plus a second one for the direct URL") and needed
no change. `piratebox_deploy.sh`'s two `--exclude` lines and
`docs/OPERATIONAL-DECISIONS.md`'s existing historical entries are
plain file references with no ordering semantics - left as-is.

## Admin Panel Auth Readiness (discoverability, not a mechanism change)

**Decision date:** 2026-09-02. The operator tried `/admin/`, hit nginx's
HTTP Basic Auth prompt, and had no credentials to enter. Investigation
(audited before changing anything, per instruction) found the
underlying mechanism was already fully correct on every dimension that
matters:

- `setup_admin_password.sh` already exists, already documented
  prominently in `README.md`, and is already printed at the end of
  `installer_pi_zero_trixie.sh`'s own install output.
- It uses `openssl passwd -apr1` (already installed) - **no
  apache2-utils/htpasswd dependency needed**, so nothing to install.
- Interactive-only: prompts for username/password twice (no echo),
  refuses an empty password, never writes plaintext anywhere, never
  touches git.
- `piratebox_deploy.sh` already explicitly excludes
  `.piratebox_admin_htpasswd` from its rsync (line 93) - a deploy can
  never overwrite an operator-set password.
- `installer_pi_zero_trixie.sh` only `touch`es the file `if [ ! -f ... ]`
  - a reinstall cannot erase existing credentials, only an empty file
  gets created fresh. `chown`/`chmod` are reapplied unconditionally
  (harmless - ownership/permissions, not content).
- Permissions confirmed correct by the operator's own investigation:
  `root:www-data`, `0640` - group-readable by `www-data` (the file's
  purpose), unreadable by anyone else, unwritable by the web server.

**Nothing above needed fixing.** The actual gap was pure
rediscoverability: an operator who set this up once, then forgot the
command months later, had no way to relearn it short of re-reading
`README.md`. Addressed:

1. **`piratebox_status_helper.sh`** (root-run, outside PHP-FPM's
   `open_basedir` for the same reason `rtc_detected`/
   `fake_hwclock_installed` already are - see that script's own
   comment) now publishes `admin_auth.configured` (a boolean, nothing
   else - never a username, hash, or file path) to `status.json`.
2. **`includes/capability_state.php`** gained a new `admin_panel`
   capability (`piratebox_classify_admin_panel()`, unit-tested):
   `AVAILABLE` if configured, **`DEGRADED` (not `UNAVAILABLE`) if not -
   this is the intentional secure default, not a fault**, `UNKNOWN` if
   the status helper itself is stale/unavailable.
3. **`/utility/about/` (public)** - already only ever shows aggregate
   per-layer counts ("N of M working"), never per-capability labels,
   so this integrates without ever stating "admin panel: not
   configured" to a public visitor by name. Its existing admin-mention
   paragraph was reworded to state plainly that nothing on that page
   reveals whether a password has been set.
4. **`/admin/` (already-authenticated view)** - `piratebox_diagnose_
   capability()` gained an `admin_panel` message with the exact setup/
   reset command, for an operator who's already in and wants a
   reminder for next time (rotating the password, adding a note for a
   successor operator, etc.) - not reachable by definition before the
   first password exists, so this doesn't solve the *first-time* case.
5. **`help.php` (public, unauthenticated - the actual fix for the
   first-time case)** - added an "Admin" bullet to the existing "Using
   PirateBox" list: what `/admin/` is, that it's locked until the
   operator sets a password, and that `README.md` in this device's own
   source repository explains how - reachable by anyone including a
   first-time operator who forgot, without printing the literal `sudo`
   command on a page any Wi-Fi guest can load.

**No new authentication system.** Nginx Basic Auth is unchanged;
`setup_admin_password.sh` is unchanged. This is a self-description +
documentation-discoverability fix, not a mechanism change.

**Operator action still required, unavailable to fix here (interactive
sudo):** the actual first password/username has to be set by the
operator themselves - Claude Code must never see or handle the
plaintext. Run **exactly this**, once, on the device (or over SSH):

```
sudo /usr/local/bin/setup_admin_password.sh
```

It will prompt for a username (default `admin`) and a password (typed
twice, never echoed), then reload nginx automatically. Re-run the same
command at any time to change the password later - there is no
separate "reset" command because setting a new one *is* the reset.

**A second, unrelated operator step is also needed** for the new
`admin_panel` self-description above to actually take effect:
`piratebox_status_helper.sh` is a root-installed script outside the
normal `piratebox_deploy.sh` web-content sync (like
`setup_admin_password.sh`, it lives at `/usr/local/bin/` and isn't in
this session's narrow sudo grants), so the repo's updated copy needs
manually reinstalling once:

```
sudo cp piratebox_status_helper.sh /usr/local/bin/piratebox_status_helper.sh
sudo chmod +x /usr/local/bin/piratebox_status_helper.sh
```

No service restart needed - `piratebox-status.timer` re-invokes the
script fresh on its next poll (well under a minute). Until this step
runs, `status.json` simply won't have the new `admin_auth` block yet -
`admin_panel` capability then correctly reports `DEGRADED` (helper
fresh, field absent - the same "don't fabricate AVAILABLE" treatment
every other capability here already gives a missing field), not a
wrong answer, just not yet the *newly precise* one.

## AWG Ampacity Table Reviewed Against an Authoritative Source (roadmap item 10)

**Decision date:** 2026-09-02. Explicit instruction: the existing
electrical quick-reference's AWG table "should be reviewed against an
authoritative source if that has not already been done." It hadn't -
researched NEC-style ampacity references directly rather than assuming
the earlier figures were fine.

**Finding:** the table's 14/12/10 AWG figures (15/20/30 A) turn out to
exactly match the NEC's standard branch-circuit overcurrent protection
(breaker/fuse) sizing convention for those gauges - not a coincidence,
and not wrong, but worth being precise about: NEC Table 310.16 rates a
14 AWG conductor's raw ampacity considerably higher (roughly 25-36 A
depending on insulation temperature rating), and code deliberately
caps its breaker at 15 A anyway for safety margin. **The table was
already using the more conservative, code-aligned numbers, not the
higher raw ratings - no number changed.** Only the caveat text was
rewritten to say this precisely (which specific NEC concept these
figures approximate, and why raw-ampacity numbers are deliberately not
shown), so a reader understands *why* these particular numbers rather
than assuming they're an arbitrary simplification.

**Testing:** `php -l` clean. Full five-suite regression: 206/206
(unaffected by design - text-only change, no logic).

## Three More Original-Source Documents: CDC/FEMA/EPA (roadmap item 9)

**Decision date:** 2026-09-02. Continuing source investigation with
the candidates named next in priority: FEMA, FCC, CDC, USDA, US
Forest Service.

**Investigated, per-source, same discipline as before:**
- **CDC**: confirmed public domain, verified against CDC's own
  copyright guidance ("Most of the information on the CDC and ATSDR
  websites is not subject to copyright, is in the public domain").
  Acquired: **Make Water Safe During an Emergency** fact sheet
  (730KB) - directly strengthens the existing PirateBox-authored
  "Water Storage & Boil-Water Advisories" topic with the actual CDC
  original behind it, matching the instruction that a PirateBox
  summary shouldn't replace a retainable authoritative original.
- **FEMA**: confirmed public domain, verified against FEMA's own
  policy ("Most material on FEMA.gov is free of copyright... Ready
  Campaign publications" explicitly made available for free
  reproduction). Acquired: **Family Emergency Communication Plan**
  (1.0MB, full fillable planning document) - a genuinely useful
  original the existing "Family Emergency Communication Plan" topic
  only described, never provided.
- **EPA** (not originally on the candidate list, but directly
  relevant - discovered while researching US Forest Service wildfire
  material, which EPA co-develops with): confirmed public domain,
  verified against EPA's own copyright-policy framework. Acquired:
  **Reduce Your Smoke Exposure** wildfire smoke factsheet (346KB,
  2026 edition) - fills the "Wildfire & Smoke" topic the same way.
- **USDA (FSIS)**: candidate identified (a "Severe Storms, Hurricanes,
  Power Outages" food-safety brochure) but the direct URL returned
  **HTTP 403** (Akamai bot protection, not a licensing issue) -
  recorded as access-blocked, not licensing-blocked; worth retrying
  later or leaving for the operator to fetch manually if wanted.
- **FCC**: not pursued this increment - already the citation basis for
  existing Radio content (Part 97/95/73); no new specific FCC document
  identified as filling a genuine additional gap yet.
- **US Forest Service**: not pursued directly this increment (see EPA
  above, which substitutes as the practical publisher for the wildfire-
  smoke material USFS co-develops) - no additional USFS-specific
  document identified as necessary beyond that.

**Integrated exactly like the first three** - `categories.json`
unchanged (all three fit the existing `emergency-firstaid` category);
three new `catalog.json` entries with full provenance; each carries a
**topic-specific** `related_pages` entry (not page-level) pointing at
the exact Emergency Reference topic it strengthens
(`water-storage-safety`, `family-emergency-plan`, `wildfire-smoke`).

**`emergency/index.php` upgraded to match**: the per-topic cross-link
check used on Radio's severe-weather guide (previous increment) is now
also used per-*topic* on the Emergency Reference page, not just
page-level - the existing page-level cloud-chart link stays (general
weather awareness), and the three new documents each appear inside
their own specific topic's detail block.

**Testing:** `tools/check_library_catalog.py` clean (6/6 agree).
`php -l` clean. `piratebox_get_reference_packs()` confirmed live:
`library` pack now `INSTALLED`, `entry_count: 6`. Rendered
`emergency/index.php` directly - confirmed all three new documents
render inside their correct topic. Search index rebuilt (115 entries,
was 112). Full five-suite regression: 206 assertions, 0 failures.

**Disposition:** Document Library now holds 6 documents, ~8.4MB total,
every one individually sourced/licensed/cross-linked - not a bulk
import. See `docs/IMPLEMENTATION-ROADMAP.md` §3b for the updated
source-status table using the newly-requested status vocabulary
(IMPLEMENTED+DEPLOYED+LIVE-VERIFIED / VERIFIED SOURCE, QUEUED /
LICENSING BLOCKED / etc.).

## Document Library Cross-Linking (roadmap item 8)

**Decision date:** 2026-09-02. High-priority item per operator
instruction: turn the Document Library from "a thing that exists" into
something a subject-page reader discovers naturally, without needing
to already know `/utility/library/` exists.

**Built:** `includes/library_links.php` -
`piratebox_get_library_entries_for_page(string $pageUrl)` (matches a
page's own URL against every catalog entry's `related_pages` array -
returns nothing fabricated when no entry names that page) and
`piratebox_render_library_links_html()` (one consistent "Original
source material available offline" box, reused everywhere rather than
each page inventing its own markup). **Metadata-driven, not a
hardcoded link graph**, per instruction: the association lives in
`data/utility/library/catalog.json`'s own `related_pages` field
(`[{"url", "label"}, ...]`) - both directions (subject-page -> Library,
Library -> subject-page) read the same one field, nothing kept in
sync separately.

**Wired into four subject pages** (each pulling its own relevant
entries, none hardcoding another page's content):
- `/utility/maps/` -> USGS Topographic Map Symbols
- `/utility/fieldtools/time/` -> NIST SP 432 (Time and Frequency
  Services)
- `/utility/emergency/` -> NOAA/NASA Sky Watcher Cloud Chart
- `/utility/radio/`'s specific "What to Monitor During Severe
  Weather" guide (not the whole Radio page) -> the same cloud chart,
  since that's the one guide it's actually relevant to - matched via
  a per-guide URL (`/utility/radio/#<guide-id>`), not a page-level
  match, so the box only appears on the one relevant guide.

**Reverse direction:** `/utility/library/` itself now renders each
document's own "See also:" links from the same `related_pages` field -
no separate lookup, same single source of metadata.

**Search discoverability audited and fixed:** library documents were
already generically indexed (title/description/tags), but a search for
the source organization itself (e.g. "NOAA", "USGS") wouldn't have
matched, since `source` wasn't fed into search keywords.
`tools/build_search_index.py`'s library loop now also extracts
words from each entry's `source` field into its keyword list - a
small, generic fix (works for any future library entry, not a
one-off patch of these three).

**Testing:** `php -l` clean on all five changed/new files. Each of the
four subject pages rendered directly and independently (isolating each
`include` in its own PHP process, after an initial combined test
falsely suggested a session/redeclaration bug that was actually just
an artifact of including multiple full pages in one process - not a
real defect, confirmed by re-testing each in isolation exactly as
php-fpm would serve it) - all four show their correct cross-link box
with correct document title. Library page rendered directly - "See
also" links confirmed present and correct for two of three documents
(the third, USGS, wasn't checked by name but uses identical code).
Search index rebuilt (112 entries, same count as before - this was a
keyword-enrichment fix, not a new-entry fix) - `NOAA`/`NASA`/`USGS`/
`NIST` keywords confirmed present on the relevant entries. Full
five-suite regression: 206 assertions, 0 failures.

## Original Signal Identification Framework, Not a SigIDWiki Clone (roadmap item 7)

**Decision date:** 2026-09-02. Direct follow-through on the SigIDWiki
finding recorded in the previous increment: investigated and rejected
as a copy source, but the underlying idea (a Radio -> Signal
Identification reference, valuable alongside SDR hardware) was not
abandoned - built as an original PirateBox work instead, using only
content this project can already stand behind.

**Built:** `data/utility/radio/signal-identification.json` - 8 signal
types genuinely likely to be encountered on a wideband receiver (CW/
Morse, SSB voice, AM voice/broadcast, NFM voice, NOAA SAME digital
alert bursts, DTMF, RTTY, Packet/APRS), each with frequency area,
bandwidth, modulation, and a plain-language "how to recognize it"
description (what it sounds like / how it behaves), cross-linked to
related signals. Wired into `radio/index.php` as a new "Signal
Identification" section/chip, same accordion pattern as every other
section on that page.

**Explicit transparency about the licensing decision, on the page
itself, not just in this log:** the new section's own intro states
plainly that SigIDWiki was investigated and not copied from (its own
content policy grants no redistribution license - see the previous
entry), and that no waterfall images or audio samples are included for
that reason - identification here relies on frequency/modulation/
description only. This matches the project's own self-awareness
discipline (never silently omit a limitation) applied to content, not
just hardware/capability state.

**Deliberately excluded:** anything resembling actual SigIDWiki
content (specific per-signal waterfall crops, audio recordings,
wording lifted from that site). Every fact here is either already-
established radio theory (frequency bands, modulation behavior - same
register as the guides added earlier this session) or well-known
amateur/SWL operating knowledge, not a transcription of any single
source.

**Testing:** `php -l` clean, JSON valid (8 entries). Rendered
`radio/index.php` directly - confirmed the section, a specific entry
(CW), the SigIDWiki transparency note, and APRS all render correctly.
`tools/build_search_index.py` updated (new loop for signal-
identification.json) and re-run - 112 entries, up from 104. Full
five-suite regression: 206 assertions, 0 failures (unaffected by
design - static reference content).

**Not yet built:** waterfall/spectrum imagery and audio examples for
each signal - explicitly deferred pending a genuinely redistributable
source (candidate: NTIA/FCC spectrum-allocation charts for a
*frequency-allocation* visual, distinct from per-signal waterfall
crops, which remain unsourced). See `docs/IMPLEMENTATION-ROADMAP.md`
§3b.

## Original-Source Document Library: First Three Documents (roadmap item 6)

**Decision date:** 2026-09-02. New addendum to the Deep Offline
Reference Library direction: a fourth layer, alongside the existing
at-a-glance/learn/technical layers - a curated ORIGINAL-SOURCE library
(real authoritative documents/charts retained offline with provenance,
not PirateBox-authored summaries replacing them where a real original
can legally be kept).

**Discovered rather than built from scratch:** `/utility/library/`
("Document Library," Stage 7) already existed as exactly this
mechanism - `data_file`/category grouping, per-entry
`source`/`date_version`/`provenance_notes` fields, a consistency
checker (`tools/check_library_catalog.py`), and an explicit
"don't add copyrighted material you don't have the right to
redistribute" rule already written into its own README. It was empty
"by design... per instruction not to bulk-download or fabricate
entries" - not because the mechanism was missing, but because no
verified-redistributable content had been sourced yet. This is exactly
the "documented but forgotten vs. genuinely blocked" distinction the
project's own roadmap-reconciliation discipline exists to catch.

**Source investigation performed before acquiring anything** (per the
explicit "publicly accessible does not mean redistributable" hard
requirement):
- **NIST**: confirmed public domain - works of NIST employees carry no
  US copyright (17 U.S.C. Sec. 105), verified directly against NIST's
  own copyright policy page. The Standard Reference Data Act exception
  (15 U.S.C. Sec. 290e) does not apply to narrative technical
  publications like the one retained here.
- **USGS**: same public-domain basis, verified against USGS's own
  copyright policy - with the confirmed caveat that some USGS pages
  embed third-party (non-USGS) images that aren't public domain. The
  document retained here (a symbols legend, USGS's own cartographic
  work) doesn't have that problem.
- **NOAA**: same basis, verified against NOAA Library's own copyright
  guidance - with the confirmed caveat that NOAA material co-authored
  with a *non-federal* party (a university, a Cooperative Institute)
  isn't automatically public domain. The document retained here is
  co-published with NASA - also a federal agency, so the caveat
  doesn't apply.
- **SigIDWiki**: investigated and explicitly NOT used. Its own general
  disclaimer states signal recordings/images are user-submitted "as
  is," "not under any licenses," with users retaining "sole
  responsibility for... intellectual property ownership" - the
  opposite of a clear redistribution grant. Recorded as a licensing-
  blocked source, not silently dropped - see the roadmap for what
  happens instead (an original, non-SigIDWiki-derived compact
  reference using only content this project can already verify).
- **ARRL**: not yet needed for this increment (no ARRL material was
  acquired) - flagged in the roadmap as "verify per-publication before
  bundling anything," per instruction, since ARRL is a membership
  organization, not a blanket public-domain source.

**Acquired (all three independently verified: reachable, correct
`Content-Type: application/pdf`, byte-for-byte size match against the
server's own `Content-Length`, valid `%PDF-` header and `%%EOF`
trailer - not merely assumed intact):**
1. **USGS Topographic Map Symbols** (2.2 MB) - the standard map-symbols
   legend; fills the "map symbols reference" / "topographic-map
   education" gap flagged in the earlier audit.
2. **NIST SP 432 (2002): NIST Time and Frequency Services** (1.9 MB) -
   ties directly into this device's own existing time-confidence/RTC/
   NTP self-awareness theme.
3. **NOAA/NASA Sky Watcher Cloud Chart** (2.5 MB) - fills the
   "cloud-identification visual" gap flagged in the earlier audit.

**Integrated via the existing mechanism, no new code path:** files
placed in `public/utility/library/files/`, three `catalog.json`
entries added with full provenance (source URL, retrieval date,
publication identifier/edition, explicit license basis citing the
specific statute and the specific policy page checked - not a vague
"probably public domain"). One new category added to `categories.json`
("reference" - General Reference & Standards) since NIST/USGS/NOAA
material didn't fit the existing radio/electronics/maps/emergency
buckets cleanly. `data/reference-packs.json`'s `library` pack entry
updated - its `license`/`note` fields previously claimed a blanket
"Operator-provided," now correctly says "mixed, see per-document
provenance" since curated public-domain content and (eventually)
operator-added personal manuals will coexist.

**Testing:** `tools/check_library_catalog.py` - clean, catalog and
files directory agree exactly (3/3). `php -l` clean.
`piratebox_get_reference_packs()` confirmed live: `library` pack now
`INSTALLED`, `entry_count: 3` - computed from the real files, not
hand-set. Rendered `library/index.php` directly - all three documents,
their filenames, and the license-basis text render correctly. Search
index rebuilt (104 entries, was 101). Full five-suite regression:
206 assertions, 0 failures (unaffected by design - no suite covers
static document metadata).

**Disposition:** the Document Library moves from CANDIDATE-in-spirit
(a working, empty mechanism) to genuinely populated, with every entry
individually sourced and licensed - not a bulk import. See
`docs/IMPLEMENTATION-ROADMAP.md` for the new Layer 4 section and the
continuing source-investigation queue (ARRL, remaining NOAA/USGS/FEMA
candidates, the SigIDWiki-alternative signal-ID framework).

## Deep Offline Reference Library: Electrical Quick Reference (roadmap item 5)

**Decision date:** 2026-09-02. Third content increment, continuing the
audit's priority list (`docs/IMPLEMENTATION-ROADMAP.md` §3a item 3):
electrical/electronics reference was evaluated during the audit as
genuinely absent, moderate field-repair value, and safely buildable
from well-established physics/engineering reference (not a
safety-critical *procedure* the way medical/electrical-work-execution
guidance would be).

**Built:** a new "Electrical Quick Reference" section on the existing
Field Tools Units page (`/utility/fieldtools/units/`), placed directly
after the existing Volts x Amps / battery-runtime calculators it
naturally extends - no new page, no new nav entry, matching "keep the
existing UI visual language unless depth genuinely requires
navigation changes." Two tables: **Ohm's Law &amp; power
relationships** (V/I/R/P, all four standard forms - fixed physics, not
a judgment call) and a **copper wire gauge (AWG) ampacity reference**
(18 AWG through 8 AWG, approximate safe current + typical use).

**Safety framing, per the request's own instruction to preserve
warnings for consequential material:** an explicit `help-note` states
this is general reference only, not a substitute for the National
Electrical Code or a qualified electrician, and that real wiring
decisions depend on insulation rating, bundling, ambient temperature,
and run length that this simplified table doesn't capture - the same
"estimate, not a guarantee" register the page's own pre-existing
battery-runtime tool already uses for its own caveat.

**Testing:** `php -l` clean. Rendered `fieldtools/units/index.php`
directly - confirmed the new section, both tables, and the NEC caution
text all render. `tools/build_search_index.py` gained one new static
entry (Field Tools' index is a curated list, not JSON-driven, unlike
the reference sections) - 101 entries, up from 100.
`tools/test_fieldtools.php` unaffected by design (86/86 - this is
static reference content with no new PHP calculation logic to unit-
test; the structural render check above is this change's verification,
same as the Radio guides increment). Full five-suite regression:
206 assertions, 0 failures.

## Deep Offline Reference Library: United States Reference Map (roadmap item 4)

**Decision date:** 2026-09-02. Second content increment, following the
audit's own priority order (`docs/IMPLEMENTATION-ROADMAP.md` §3a): "the
single largest gap this audit found" was Maps having only a Universal
layer - no National/Regional/State layer existed at all, despite the
World Reference Map's own note explicitly saying "not the end of the
Maps feature."

**Built:** `tools/build_us_reference_map.py` - the same proven pipeline
as the World Map (Natural Earth public domain, equirectangular
projection, stdlib-only), one administrative level down: Admin 1
States/Provinces, filtered to `iso_a2=="US"` (51 features - 50 states +
DC, all present, none silently dropped). **Three-panel layout**
(continental US as the main panel, Alaska and Hawaii as independently-
scaled insets - the standard convention for US reference maps, since
both are far outside the continental bounding box and would otherwise
force the whole map absurdly wide) rather than a simplified CONUS-only
map that quietly excluded two states. Output:
`public/utility/maps/files/us-reference-map.svg` (~44KB).

**Verified after generation:** parsed back as well-formed XML; Texas/
California/Florida/Maine's rendered bounding boxes checked against
their real lon/lat ranges within the CONUS panel's own projection math
and matched exactly; confirmed all 51 features present, correctly
split 49 (CONUS+DC) / 1 (Alaska) / 1 (Hawaii) across panels.

**Wired into the Reference Library exactly like the World Map:** new
always-visible "United States Reference Map" section on `/utility/
maps/` (new `usmap` search chip), a `data/utility/maps/
us-reference-map.json` descriptor (same one-entry-array pattern, no
special-casing), a new `natural-earth-110m-admin1` source citation,
indexed in Global Search (not `regional`, so Travel Mode doesn't hide
it - **per the explicit instruction that national public reference
material stays available in Travel Mode**, unlike the local/regional
operator map catalog). `data/reference-packs.json` gained a
`us-reference-map` row, `scope: "national"` (distinct from the World
Map's `"universal"` scope - the hierarchy now has two real rungs, not
one).

**Testing:** `php -l` clean. Rendered `maps/index.php` directly -
confirmed the new section, the SVG file, Alaska's presence, and the
source citation name all render correctly. `piratebox_get_reference_
packs()` confirmed live: `us-reference-map` -> `INSTALLED`, scope
`national`, `entry_count: 1` - computed, not hand-set.
`tools/test_reference_packs.php` gained 4 new assertions (key exists,
INSTALLED, scope is national not universal, entry_count not
fabricated). Full five-suite regression: 206 assertions, 0 failures
(was 202, +4 new).

**Disposition:** the Maps hierarchy now has two real rungs (Universal,
National) instead of one. Regional/State (e.g. a Texas-specific pack)
and Special-Purpose (UTM/MGRS visual, map symbols) layers remain
correctly unbuilt - Regional/State needs an operator scope decision
(which state(s) actually matter for this box), not a sourcing blocker;
Special-Purpose is recorded as a future increment, not lost. See
`docs/IMPLEMENTATION-ROADMAP.md` §3a for the full updated priority
list.

## Deep Offline Reference Library: Radio Depth Expansion (roadmap item 3)

**Decision date:** 2026-09-02. First increment of a new major
direction: grow the Reference/Utility Library into a genuinely
substantial offline field library, guided by the test "someone finds
this PirateBox during a prolonged infrastructure/communications
failure - is finding it genuinely valuable?" Content audit done first
(recorded in `docs/IMPLEMENTATION-ROADMAP.md`'s new "Reference Library
content audit" section) before picking where to start.

**Audit finding that changed the plan:** Radio Reference turned out
already substantially deeper than a first look at entry counts
suggested - 25 services, 6 modulation types, and 6 already-well-written
guides (RF spectrum overview, HF/VHF/UHF, HF propagation, antenna
basics, receiver tips, emergency monitoring), plus an existing SVG
spectrum-chart visual (`spectrum.svg.php`) and a working `<details>`-
based progressive-disclosure pattern (summary = at-a-glance, expanded =
full explanation + source citation) already matching the requested
"at a glance / learn / technical reference" shape. **The real gap was
narrower and more specific than "Radio needs more depth" in general:**
seven concrete topics named in the request were genuinely absent -
dB/dBm, SDR concepts, simplex/repeater, polarization, feed lines/
connector identification, the NATO phonetic alphabet, and Morse code.

**Built:** seven new entries in `data/utility/radio/guides.json`,
reusing the exact existing guide schema/rendering (no new page
structure) plus one small additive extension: guides can now optionally
carry a `table`/`table_caption` (reusing the identical union-of-keys
table renderer `services.channels` already used, just applied to
guides too) - used for the connector-identification, phonetic-
alphabet, and Morse-code entries, since those are genuinely
tabular reference material, not prose. `radio/index.php` updated
accordingly (one small additive block, same pattern as the existing
channels table).

**Provenance:** the NATO phonetic alphabet and International Morse
Code are both fixed ITU/ICAO standards, not judgment calls or
generated procedures - transcribed directly (not "generated from
memory" in the risky sense the project's own sourcing discipline
warns about; these are unambiguous, universally-fixed lookup tables,
same register as transcribing a known physical constant). The dB/dBm,
SDR, simplex/repeater, polarization, and connector guides are
conceptual/educational content in the same register and citing the
same `general-rf-education`/`itu-r-v431` source ids the existing six
guides already use - no safety-critical transmission procedures were
added, and the page's existing receive-focused/license-required-to-
transmit framing is unchanged.

**Testing:** `php -l` clean. Rendered the actual repo `radio/index.php`
directly (GET-only structural check) - confirmed all seven new guides
render, the phonetic-alphabet table shows Alfa through Zulu, the Morse
table shows the SOS prosign correctly. `tools/build_search_index.py`
re-run (99 entries, was 92 - 44 of the 99 are now Radio section
entries). Full five-suite regression: 202 assertions, 0 failures
(unaffected by design - no suite covers static reference content, as
before).

**Not yet built from this same audit** (recorded in the roadmap, not
lost): visual connector-identification diagrams (currently a text
table, not an image - a genuine future improvement but requires
sourcing/creating an actual diagram, not rushed into this increment);
antenna-type/radio-band visual diagrams beyond the existing spectrum
chart. See `docs/IMPLEMENTATION-ROADMAP.md` for the full audit and
next actions across every other Reference Library category.

## Physical Wiring Self-Description (roadmap item 2)

**Decision date:** 2026-09-02. Second roadmap-driven implementation
increment. `docs/ARCHITECTURE.md` §17 ("self-describing/inheritable
device") named a specific, concrete, still-missing piece: "Neither
[`/utility/about/` nor admin's Capabilities table] yet covers wiring
assignments... reachable today only by reading this repository's own
docs directly, not from a page." Everything else that section
mentions (ownership/recovery concept, replaceable-hardware-role
narrative) is either a genuine operator decision or a much larger
scope - wiring assignments specifically is small, static, already
fully known (`docs/HARDWARE-INTEGRATION-DESIGN.md` §2), and needed no
decision to surface.

**Built:** `data/gpio-wiring.json` (mirrors §2's table exactly - that
design doc stays the authoritative source for wiring *decisions*, this
is what actually renders on-device), `includes/hardware_wiring.php`
(`piratebox_parse_gpio_wiring()`/`piratebox_get_gpio_wiring()`, same
pure-parser-plus-thin-fs-wrapper shape as `reference_packs.php` -
returns `null`, never a fabricated empty list, on missing/malformed
data), and a new "Physical wiring" section in `admin/index.php`
(operator tier, next to Capabilities &amp; Health - physical wiring
detail is diagnostic, not public-safe, same boundary logic already
applied to Power/undervoltage). **Deliberately not live-sensed:**
there's no software way to discover what a floating, unclaimed GPIO
pin is physically wired to - `status` is the same operator-maintained
fact the design doc already records, honestly presented as such (the
one row that IS truly live-verifiable, GPIO25/shutdown button, already
has its own real capability-state entry elsewhere - this file adds the
physical-pin context that capability doesn't carry, not a competing
source of truth for it).

**Testing:** `php -l` clean; `tools/test_hardware_wiring.php` (new, 21
assertions - null/malformed/missing-field/mixed-garbage-and-valid-rows
cases, plus an integration check against the real data file confirming
exactly one row - the shutdown button - is marked wired, matching
`gpioinfo`'s live confirmation that every other assigned pin is an
unclaimed `input`). Rendered the actual repo `admin/index.php` directly
(bypassing the nginx Basic Auth layer for a structural GET-only check,
same technique as prior sessions' admin-page smoke tests) - confirmed
the new section renders, GPIO25 shows its wired status, every other
row shows "Not wired," no PHP warnings/errors. Full five-suite
regression: 202 assertions, 0 failures (was 181, +21 new).

**Disposition:** `docs/ARCHITECTURE.md` §17's wiring-assignments gap
closed. Ownership/recovery concept and the fuller "Tell me about
yourself" narrative remain correctly out of scope - the former is a
genuine operator decision (§15-16), the latter a much larger, less
concretely-scoped future increment, not "already approved in
principle" the way this specific gap was.

## purge_uploads.sh Completeness Gap Closed (roadmap item 1)

**Decision date:** 2026-09-02. First roadmap-driven implementation
increment after reconciliation. `docs/IMPLEMENTATION-ROADMAP.md` §1
flagged that `purge_uploads.sh` never actually removed
`data/bulletin.json` or `data/recovery-messages.json`, despite its own
header and README.md both describing its scope as "wipe everything" -
found in Stage 25, repeated in Stage 32's checklist, never fixed.

**Fixed:** two more `rm -f` lines added, matching the existing
chat.json/messages.json lines' exact style (same `-f` tolerance for a
fresh install where the file doesn't exist yet). `README.md`'s
description updated to match ("all chat/logbook/bulletin/recovery-
message history," not just the first two). A comment block explains
what changed and why, so a future reader doesn't wonder whether this
was deliberate.

**Testing:** `bash -n` clean. Functional test against an isolated
scratch directory (never `/var/www/html`): seeded `chat.json`,
`messages.json`, `bulletin.json`, `recovery-messages.json` (all `[]`)
plus a `device-id.json` that must survive (out of scope - device
identity isn't "uploads/community content") and one uploaded file.
Ran a copy of the script with `TARGET_DIR` redirected at the scratch
dir: all four JSON stores and the uploaded file were removed;
`device-id.json` was correctly left untouched. `chown` failed
harmlessly in the test (not running as root there) - real root-owned
production runs via `sudo` don't hit that.

**Not yet live** - this is a root-owned script installed via a plain
`cp`/`chmod +x` (`installer_pi_zero_trixie.sh`), outside this
project's narrow sudo automation (same class of gap as every other
root-owned-file install this project has hit). New pending step,
batched rather than stopping the run for it:

```
sudo cp /home/moose/piratebox/purge_uploads.sh /usr/local/bin/purge_uploads.sh
sudo chmod +x /usr/local/bin/purge_uploads.sh
```

**Roadmap updated:** `docs/IMPLEMENTATION-ROADMAP.md` §1's
`purge_uploads.sh` row moves from "PARTIALLY IMPLEMENTED" to
"IMPLEMENTED IN REPO, NOT DEPLOYED" pending the step above.

## Roadmap Reconciliation

**Decision date:** 2026-09-02. Operator correction of process: across
many large staged/master prompts, continuation prompts, and addenda
over this project's history, a suspicion arose that later prompts may
have displaced earlier valid execution queues rather than merging with
them. Instructed to reconstruct historical intent from the repository
itself before doing any more feature work, and to create a durable
tracked roadmap so this can't happen again.

**Recovered:** the full 159-commit history; every `## ` heading in this
file (64 entries - the complete decision timeline, both the "Offline
Utility Library - Stage 1-10" sub-track and the main "Stage 13-32"
track, plus the pre-Stage-13 Phase 1-5 foundation and this year's
autonomous-phase increments); `docs/CAPABILITY-REGISTRY.md`'s full
hardware/software table; Stage 32's own "consolidated outstanding items
for the operator" checklist (7 items - cross-checked one by one against
current state: 4 already resolved by later sessions, 1 correctly still
open pending operator data, 1 correctly still open pending an operator
package-install decision, and **1 - `purge_uploads.sh`'s incomplete
file list - found to have genuinely fallen out, never fixed despite
being named twice**); live system state (`systemctl`, `lsusb`, `iw
dev`, `gpioinfo`, `/dev/i2c*`) checked against every hardware-related
CANDIDATE/OWNED-INCOMING claim rather than trusting the doc text
alone.

**Findings, per the specific distinctions requested:**
- **One stale blocker overturned** (already handled this session,
  cross-referenced here): the World Reference Map's CANDIDATE status
  was based on "no WAN path," true for the Pi's isolated visitor AP but
  not for this session's own management uplink - checked live, not
  assumed, before building it.
- **Two doc-drift cases** (documentation claiming something
  unimplemented when it already existed - also already handled this
  session): graceful self-diagnosis (`ARCHITECTURE.md` §13) and "Since
  last review" (`DEVICE-MEMORY-DESIGN.md` §3).
- **One genuinely fallen-out item, newly found:** `purge_uploads.sh`
  doesn't remove `data/bulletin.json` or `data/recovery-messages.json`
  - flagged in Stage 25, repeated verbatim in Stage 32's checklist item
  7, never fixed across three later sessions. Not deliberately
  deferred - simply never circled back to. Scheduled as the next
  increment.
- **Every hardware-gated item checked live, not assumed:** ALFA
  AWUS036ACM confirmed NOT present (`lsusb`/`iw dev` show only the
  already-rejected TP-Link on `wlan0`'s companion `phy#1`); GPIO17/
  toggle/buttons/OLED confirmed NOT wired (`gpioinfo` shows GPIO17 as
  unclaimed `input`, no `/dev/i2c*` device node exists at all - I2C
  isn't even enabled, not merely uncoded). All CANDIDATE/OWNED-INCOMING
  hardware classifications in `CAPABILITY-REGISTRY.md` confirmed
  accurate, not stale.
- **Ownership/trust/transfer (`ARCHITECTURE.md` §14-17):** confirmed
  still deliberately principle-only, "None of these is chosen or
  implemented" - a genuine security/identity decision, correctly left
  to the operator, not re-litigated.

**Built:** `docs/IMPLEMENTATION-ROADMAP.md` - the new authoritative
execution queue. Structured as compact per-area tables (not prose),
one row per meaningful capability, each carrying status (from an
explicit 11-value vocabulary distinguishing "documented" from
"implemented" from "deployed" from "live-verified"), evidence,
blocker, next action, and a doc pointer - links to detail rather than
duplicating it. `CLAUDE.md` updated in two places: a new top-priority
routing-table row, and a note in §4 (the "history is not a to-do list"
section) directing future sessions to update this roadmap's rows
rather than regenerate a new plan from whichever prompt arrived most
recently.

**Disposition:** reconciliation complete. Resuming implementation
against the roadmap's actionable rows, starting with the
`purge_uploads.sh` gap.

## Reference Library Navigation Coherence Fixes (implementation-focused audit, increment 3)

**Decision date:** 2026-09-02. Continuing the same audit
("coherent Reference Library navigation" was one of its explicit
categories), checking whether the two things increments 1-2 actually
shipped (the World Reference Map; the storage self-diagnosis fix) were
reflected everywhere a reader would reasonably expect them to be, not
just at the one place each was built.

**Found and fixed, all text-only, no logic changes:**
- `public/utility/index.php`'s Maps card still described the section as
  "Coordinates, GPS basics, and a local/regional map catalog" - didn't
  mention the World Reference Map at all, understating what's actually
  there now. Updated.
- `README.md`'s Maps &amp; Location Reference bullet still said "an
  empty, ready-to-use map catalog framework... No map data ships by
  default" - flatly wrong now (a real map does ship by default).
  Reworded to distinguish the *local/regional* catalog (still correctly
  empty by design) from the World Reference Map (ships, always
  available).
- `README.md`'s Search bullet had a stale hardcoded "83 indexed items"
  from an earlier stage - the live search page itself was never wrong
  (`count($index)`, computed, not hardcoded), only this static doc
  text was. Updated to the real current count (92) with a note that the
  live page's own count is the one to trust going forward, not this
  number.
- `docs/FIELD-TOOLS-DESIGN.md`'s status banner still said "not yet
  deployed to the live site as of this writing," left over from before
  that deploy happened - Field Tools has been live for multiple
  sessions now (including this session's own earlier `/utility/
  fieldtools/time/` checks). Corrected to "IMPLEMENTED and deployed
  live."

**Also audited and deliberately left alone:** `docs/FIELD-TOOLS-
DESIGN.md` §10's "What's deferred" list (UTM/MGRS conversion,
persisted NTP-sync timestamp, `date.timezone` fix, export-bundle
integration) - each already carries its own explicit reasoning for
staying out (UTM/MGRS: "genuinely more complex map-projection math, not
a good fit for 'avoid turning this into an enormous scientific-
calculator project'" - a deliberate, already-reasoned scope boundary,
not a mere oversight; `date.timezone`: a system-level `php.ini` change
outside this project's narrow sudo automation, not software-only;
NTP-sync persistence: deliberately not built, see §4; export-bundle
integration: "worth revisiting if operators ask for it," not something
already approved in principle). None of these are the kind of gap this
audit is for - re-litigating an already-reasoned "no" is not the same
as finishing an already-planned "yes."

**Testing:** `php -l` clean on the one changed PHP file (text-only
change, a card description string). Markdown fence balance checked on
`docs/FIELD-TOOLS-DESIGN.md` (even). No test suite covers static page
text, so the existing 181-assertion regression suite is unaffected by
design, not skipped - re-run anyway as part of this increment's own
verification and still 181/181.

## Storage Self-Diagnosis Gap Closed + Doc-Drift Fixes (implementation-focused audit, increment 2)

**Decision date:** 2026-09-02. Continuing the same implementation-
focused audit as increment 1 (World Reference Map). Two more of the
audit's explicit categories - "self-awareness/operator capability
presentation" and "graceful unavailable/degraded states" - turned up a
real, small, safe gap while checking whether `piratebox_diagnose_
capability()`'s coverage actually matched every capability this device
can report a problem for today (it did, for every id except one).

**Found:** the `storage` capability (`includes/capability_state.php`)
only ever reported `AVAILABLE` or `UNKNOWN` - it never reflected
genuinely low free space, even though this project already has a real,
established "low storage" concept everywhere else (`upload.php`'s hard
reject at `PIRATEBOX_MIN_FREE_BYTES`; the small-JSON-write guard at
`PIRATEBOX_MIN_FREE_BYTES_SMALL_WRITE`; the home page's own "within 2x
the reserve" warning banner). An admin looking at the Capabilities &amp;
Health table with the disk nearly full would have seen a flat
"AVAILABLE," not the warning the home page was already showing them
one click away - an ungraceful, silently-inconsistent degraded state,
exactly the audit category this was meant to catch.

**Fixed:** new pure `piratebox_classify_storage(?int $freeBytes, ?int
$totalBytes): string` - `UNKNOWN` on read failure (unchanged), `DEGRADED`
below the exact same `PIRATEBOX_MIN_FREE_BYTES * 2` threshold the home
page's warning already uses (deliberately reusing that number rather
than inventing a second, differently-tuned opinion about the same
disk), `AVAILABLE` otherwise. Wired into the existing `storage`
capability block (one field changed, `state` now computed instead of a
two-way ternary) and given a `piratebox_diagnose_capability()` entry for
both `DEGRADED` and `UNKNOWN`, surfaced automatically by `admin/
index.php`'s existing generic per-capability diagnosis loop - no
template change needed there. Confirmed live against this device's real
current numbers (114GB free of 123GB - genuinely `AVAILABLE`, diagnosis
correctly `null`) rather than assumed safe.

**Also fixed - two stale doc claims found during the same audit pass,
corrected rather than left to mislead the next reader:**
- `docs/ARCHITECTURE.md` §13 ("Graceful self-diagnosis") still called
  `piratebox_diagnose_capability()` "a future design goal, not
  implemented," even though it shipped in an earlier session (`docs/
  OPERATIONAL-DECISIONS.md`, "Graceful Self-Diagnosis, First Slice").
  Rewritten to describe what actually exists (coverage list, where it's
  surfaced), keeping the illustrative hardware-dependent examples
  (external Wi-Fi adapter, environmental sensor) clearly labeled as
  illustrative rather than implying the whole section is aspirational.
- `docs/DEVICE-MEMORY-DESIGN.md` §3 ("Since last review") said "no such
  summary exists today" - also no longer true (`mark_reviewed`,
  `piratebox_device_memory_since()`, admin page section, shipped the
  same earlier session). Rewritten to say precisely what's real (the
  Runtime/Power rows - boots and undervoltage events) versus what
  remains illustrative (Networking/Environment/Location rows, which
  stay aspirational because the underlying device state they'd
  summarize doesn't exist yet either - no discrete connection-event log,
  no environmental/GNSS hardware).

**Testing:** `php -l` clean. `tools/test_capability_state.php` gained
10 new assertions (the new classifier's null/boundary/above/below
cases, using the real `PIRATEBOX_MIN_FREE_BYTES` constant rather than a
hand-picked number so the test can never silently drift from the real
threshold; both new diagnosis entries; confirms `AVAILABLE` still
yields no diagnosis). Full four-suite regression: 181 assertions, 0
failures (was 171). Markdown fence balance checked on both edited docs
(even counts, no unclosed block). No community data touched - this
increment is entirely code/docs/tests.

**Disposition:** `storage` joins every other currently-live capability
with real DEGRADED/UNKNOWN diagnosis coverage. See `docs/CHECKPOINTS.md`
for the deploy/live-verification record.

## World Reference Map: CANDIDATE -> INSTALLED (implementation-focused audit, increment 1)

**Decision date:** 2026-09-02. Explicit operator correction of emphasis:
several capabilities existed only as design docs/registry entries/
CANDIDATE rather than deployed features, and the instruction was to
implement already-planned, hardware-independent, decision-independent
items rather than document them again. The World Reference Map was
given as the flagship example. Recovered state first (clean tree at
`e335077`, matching the Logbook-rename checkpoint) before starting.

**Why this was CANDIDATE, and why that no longer applied:**
`docs/REFERENCE-CONTENT-DESIGN.md` §5 previously deferred this because
this Pi's own visitor-facing network has no general WAN path by design.
That's still true - but it's a fact about the Pi's isolated AP, not
about every environment this project's own tooling runs in. Checked
rather than assumed: this session's own execution environment (this
same Pi, but via its separate `eth0` management uplink - confirmed live
with `ip route`/`curl`, distinct from the `wlan0` visitor AP this
project keeps isolated on purpose) has ordinary outbound access. Used it
for exactly one thing - fetching a well-defined, small, public-domain
data file once - not as an ongoing dependency.

**Source, verified before use, not assumed:** Natural Earth's 1:110m
Admin 0 Countries dataset. Fetched
`https://www.naturalearthdata.com/about/terms-of-use/` directly this
session and confirmed: "All versions of Natural Earth raster + vector
map data found on this website are in the public domain... No
permission is needed to use Natural Earth. Crediting the authors is
unnecessary." The GeoJSON itself was pulled from
`github.com/nvkelso/natural-earth-vector` (a Natural Earth core
contributor's own mirror - its README independently corroborates the
public-domain claim), 838KB, 177 country features, real coordinate
data - not fabricated, not a placeholder.

**Built:** `tools/build_world_reference_map.py` - equirectangular
projection (x=lon, y=-lat), stdlib `json` + arithmetic only, no new
package dependency (matplotlib/cartopy/geopandas were deliberately not
reached for - this project doesn't install packages without explicit
approval, and didn't need to here). Produces
`public/utility/maps/files/world-reference-map.svg` (~183KB, single
self-contained file, no external references, one `<path>` per country
ring with even-odd fill for holes/enclaves, a light 30-degree
graticule, an embedded attribution caption). **Verified after
generation rather than assumed correct:** parsed back as well-formed
XML; five geographically-spread countries' rendered bounding boxes
(Australia/USA/Brazil/Russia including its antimeridian span/Japan)
were checked against their real-world lon/lat ranges and matched
exactly.

**Wired into the Reference Library, not left as a standalone file:**
`public/utility/maps/index.php` gained a new, always-visible "World
Reference Map" section - deliberately placed *outside* the existing
`$travelMode ? [] : ...` gate that already suppresses the operator's
own region-specific map catalog, per the explicit requirement that this
stay available regardless of Travel Mode or whether Local Information
is configured (verified live both ways, see Testing below). New search
chip (`data-group="worldmap"`), new small descriptor
(`data/utility/maps/world-reference-map.json`, one entry - reuses the
exact same generic array-count pattern every other reference pack
already uses, no special-casing added), a new `natural-earth-110m`
entry in `data/utility/maps/sources.json` following the project's
existing per-source citation convention, and a `tools/
build_search_index.py` block so it's findable via Global Search too
(deliberately not `regional=True`, unlike the operator catalog's search
entries, so Travel Mode doesn't hide it from search either).
`data/reference-packs.json`'s `world-reference-map` row lost its
`state_override: "candidate"` and now flows through
`piratebox_get_reference_packs()`'s normal live-check path exactly like
every other pack - state is computed from the real shipped file, not
hand-set.

**Testing:** `php -l` clean; `tools/build_search_index.py` re-run
(92 entries, new World Reference Map entry confirmed present and not
`regional`). Functional testing against an isolated scratch copy of the
site (own temp dir, own `php -S` instance): page loads 200; the new
section renders with the correct image, caption, and source citation;
the SVG itself serves as `image/svg+xml` at the expected size; toggling
`data/travel-mode.json` between `false` and `true` confirmed the World
Map section stays visible in both states while the operator catalog
correctly switches to its existing "hidden while Travel Mode is active"
message in the `true` case; `/utility/about/`'s live self-awareness
table correctly shows `World Reference Map: INSTALLED (1)` - computed,
not hand-set. `tools/test_reference_packs.php` updated (the old
hardcoded "CANDIDATE" assertions were now testing something no longer
true) to assert `INSTALLED`/scope/real entry_count instead, **plus a
new synthetic-fixture test added so the `state_override="candidate"`
code path itself stays covered** even though no real pack exercises it
any more - it's still a real, reachable branch for a genuinely
unsourceable future candidate. Full four-suite regression: 171
assertions, 0 failures (was 168; +3 net in `test_reference_packs.php`).
All scratch test artifacts removed after testing - no live/community
data touched.

**Disposition:** `data/reference-packs.json`'s `world-reference-map`
entry moves from CANDIDATE to a real, sourced, licensed INSTALLED pack.
See `docs/REFERENCE-CONTENT-DESIGN.md` §5 (rewritten to describe what
now actually exists, including the general lesson for future
candidates) and `docs/CHECKPOINTS.md` for the deploy/live-verification
record.

## Guestbook Reframed as "Logbook" (terminology, not a rebuild)

**Decision date:** 2026-09-02. Raised outside this session and handed in
as one narrow currently-actionable increment: the feature at
`messages.php` (previously labeled "Guestbook" everywhere) is better
understood as a physical-style visitor/field logbook - a voluntary
"I was here," not a message board. Recovered state first (clean tree at
`6518a14`, matching the just-closed persistence-fix checkpoint) before
starting.

**What changed - human-facing only:** every user-visible occurrence of
"Guestbook" (nav link, page `<h1>`/`<title>`, home page, Utility Library
landing, "What can I do here?", Help page, admin maintenance section -
heading, confirm dialog, checkbox label, button, and result message) now
reads "Logbook." `messages.php` gained a short intro line in the same
style `bulletin.php` already uses (`<p class="muted"
style="text-align:center;">`): "Sign the PirateBox logbook - leave your
name or handle, a short note, or simply mark that you were here." The
name field's label became "Name / handle / callsign:" to match the
callsign use case named in the request - still free-text, still
optional (defaults to "Anonymous"), still not verified identity and not
a tracking mechanism (unchanged from before - just made explicit in the
label). Code comments describing the feature conceptually (across
`bulletin.php`, `found/index.php`, `config.php`, `admin/index.php`,
`scripts.js`, `styles.css`, the deploy/backup/restore/purge/rebuild
tooling, and the current-terminology passages of `ARCHITECTURE.md`,
`CHECKIN-BOARD-DESIGN.md`, `FIELD-TOOLS-DESIGN.md`,
`RTC-TIME-READINESS-DESIGN.md`, `README.md`) were updated too, for the
same reason `docs/CAPABILITY-REGISTRY.md` is kept reconciled rather than
just extended - stale terminology in a comment is a small trap for
whoever reads it next. **This file's own past entries were deliberately
left untouched** - they're a decision log, not current-state prose (see
this file's own preamble and `CLAUDE.md` §4); rewriting "Guestbook" to
"Logbook" in a 2026-08-31 entry would misrepresent what was actually
built and named that day.

**What did NOT change:** `messages.php` (route), `data/messages.json`
(storage file), the `clear_messages`/`messages` action/nav-key
identifiers, the `MESSAGES_FILE` variable, every deploy-exclude/backup/
restore/purge file reference, and the `message`/`name`/`id`/`timestamp`
JSON field names - all stayed exactly as-is, per the operator's explicit
instruction to prefer relabeling over migration risk. **No data
migration of any kind** - existing `data/messages.json` entries load and
render completely unchanged (verified below). CSRF protection, the
32/2000-char server-side caps, the exclusive-lock-then-atomic-write
pattern, the stale-`.tmp` cleanup, the free-space guard
(`piratebox_low_storage()`), Travel Mode, and every backup/restore/
export/deploy behavior are all untouched - only string literals moved
plus the one behavior change below.

**The one real behavior change - message now optional:** the request
asked to evaluate whether a name-only entry ("just mark that you were
here") could be safely allowed. It can: the textarea's HTML `required`
was the only thing enforcing a message, there's no security property
that depends on it, and the write path already defaults an empty name
to "Anonymous" - the missing piece was a symmetric rule for the message
side. Added `$hasEntry = ($name !== '' || $content !== '')`, computed
*before* the empty-name default is applied, and used to gate both the
low-storage check and the write (replacing the old `$content !== ''`
gate in both places). This means: name-only saves an entry with an
empty message (rendered without a message-body element, so it doesn't
show a blank box); message-only keeps working exactly as before
(defaults to "Anonymous"); and a **fully blank submission still creates
nothing at all**, same as before the change - `$hasEntry` is false in
that case too, so there's no new way to post an empty ghost row. No
ambiguity or validation weakening identified, so the optional-message
behavior was implemented rather than deferred.

**Testing:** `php -l` clean on every changed PHP file, `bash -n` clean
on every changed shell script. Functional testing done against an
isolated scratch copy of the site (own temp directory, own seeded
`messages.json`, own `php -S` instance on a high port) - **never
against live community data** - covering: a pre-existing entry (seeded,
not created by this session) survives and renders unchanged; a
name-only POST saves correctly with an empty message and no
message-body element in the output; a fully-blank POST creates no entry
(still 200/re-render, not a redirect - unchanged from before); a normal
name+message POST still works and IDs still increment correctly; a
forged/missing CSRF token is still rejected (403). All scratch files and
the temporary server were removed after testing. Full four-suite
regression (`test_fieldtools.php`/`test_capability_state.php`/
`test_reference_packs.php`/`test_device_memory.php`, 168 assertions -
none of which cover this feature, so an unaffected clean pass is the
expected/correct result, not new coverage) still passes.

## Connection-Stats Persistence Bug Found + Fixed (systemd sandboxing)

**Decision date:** 2026-09-02. The operator ran the pending
`piratebox_status_helper.sh` install (adds `time_source` - closed
already, `docs/FIELD-TOOLS-DESIGN.md` §9 - and now also Device Memory's
`boot_events`/`undervoltage_daily` write). **Verification of that
install found a real, more serious, pre-existing bug** while checking
the new write side, not a clean success - reported honestly rather than
closing the pending step as resolved.

**Confirmed working:** installed script byte-identical to repo source;
`time_source` correctly live in `/run/piratebox/status.json`; no
service regressions, zero failed units.

**Found broken:** the very first live run of the updated script logged
`OSError: [Errno 30] Read-only file system: '/var/www/html/data/
device-history.json.tmp'`. Investigating *why* (this directly relates
to the work just verified, was clearly understood, and was low-risk to
correct - per this session's own "fix it" criteria for exactly this
situation) found something bigger: `journalctl -u piratebox-status.
service` showed the **identical** `Read-only file system` error for
`data/connection-stats.json.tmp` at every hourly rollover this boot
(03:00, 04:00, 05:00, 06:00) - and `data/connection-stats.json` does
not exist anywhere on the live filesystem (`find /` confirmed). **The
persisted 24-hour connection-statistics history has apparently never
successfully written since that feature shipped on 2026-09-01, not
just today** - see the correction appended to "Post-Stage-32: Privacy-
Preserving Connection Statistics," above.

**Root cause:** `piratebox-status.service` has `ProtectSystem=strict`
(makes the whole filesystem read-only except explicitly carved-out
paths) with a `RuntimeDirectory=piratebox` exception for `/run/
piratebox` (tmpfs) - but no exception was ever added for `var/www/
html/data/`, the SD-card path both connection-stats' hourly rollup and
the new Device Memory writes need. The `python3 ... || true` wrapping
both writers already use (deliberately, so a write failure can never
crash the unit or block the rest of the snapshot) meant this failed
completely silently, every single hour, since the feature shipped -
every other check of this feature (including its own original live
regression testing) only ever observed the tmpfs-backed live counters,
which were never affected, so nothing looked wrong.

**Fixed:** `etc/systemd/system/piratebox-status.service` gains
`ReadWritePaths=/var/www/html/data` - the same class of fix, and same
file, as the existing documented `RuntimeDirectory=` fix for `/run/
piratebox` (Stage 21) - narrow, additive, does not relax
`ProtectSystem=strict` for anything else. `systemd-analyze verify`
clean (exit 0). **Not yet installed live** - same boundary as every
root-owned-file install this project has hit before (no dedicated
installer, no `sudo` grant for installing a systemd unit). New,
separate pending step:

```
sudo install -m 0644 -o root -g root /home/moose/piratebox/etc/systemd/system/piratebox-status.service /etc/systemd/system/piratebox-status.service
sudo systemctl daemon-reload
sudo systemctl restart piratebox-status.timer
```

**What this does NOT affect:** the live in-progress-hour connection
counters (already correct, tmpfs-backed, unaffected by this bug); any
Core service; any community data; the already-working `time_source`
fields. Once installed, both `data/connection-stats.json` (retroactively
correct from that point forward - no way to recover the missing
history, only prevent further loss) and `data/device-history.json`
should begin persisting correctly; will be verified live once the
operator runs the command above.

**Testing:** `systemd-analyze verify` on the modified unit (clean);
confirmed via `journalctl` evidence rather than assumption that this
has been silently failing since the connection-stats feature shipped,
not introduced by today's work; confirmed no service regression from
the file/timer restart already performed. Full live verification of
the fix (a real hourly rollover succeeding, `device-history.json`
appearing) deferred until the operator installs the corrected unit -
recorded as the next actionable item, not assumed successful in
advance.

**Live verification, confirmed 2026-09-02 07:00 (same day):** operator
installed the corrected unit (`sudo install -m 0644 -o root -g root
etc/systemd/system/piratebox-status.service /etc/systemd/system/
piratebox-status.service && sudo systemctl daemon-reload && sudo
systemctl restart piratebox-status.timer`), verified byte-identical to
repo source. Watched for the device's own next hourly boundary rather
than assuming wall-clock 07:00 applied - this Pi's clock is not
NTP-synchronized (no RTC, NTP unavailable by design on this offline
device, `fake-hwclock` not installed - the already-documented time-
confidence gap, not a new finding) and was running a few minutes
behind. At the device's own 07:00 rollover:

- `data/connection-stats.json` appeared for the first time ever:
  `{"hourly": [{"hour_start": 1788354000, "count": 2, "peak": 1}],
  "updated_at": 1788357614}` - the persisted 24h history now writing
  successfully.
- `journalctl -u piratebox-status.service` for that run and every run
  since the unit install: clean, zero errors (`Read-only`/`OSError`/
  `Traceback` grep: no matches).
- `piratebox_get_connection_stats()` (`includes/metrics.php`),
  exercised against the live deployed tree (not the repo checkout - an
  earlier same-session check against the repo path gave a misleading
  empty-looking result purely from `__DIR__` resolving to the wrong
  directory tree, caught and corrected before drawing any conclusion
  from it): correctly merges the newly-persisted hour with the live
  in-progress hour - `last_24h => 2, peak_24h => 1`, two hourly rows.
- Zero failed units; `piratebox-status.timer` active; all 168
  assertions across all four test suites still passing; no community
  data file's mtime changed from this verification work.
- `data/device-history.json` **still does not exist** - expected, not
  a failure: that write only fires on a boot or undervoltage-onset
  edge event (`docs/DEVICE-MEMORY-DESIGN.md`), and no such edge has
  occurred since the fix was installed. The write path shares the
  identical fix (same `ReadWritePaths=`, same directory, same
  `python3 ... || true` pattern) as the now-confirmed connection-stats
  write, so it is reasoned-fixed, but **its own first live write is
  still independently unobserved** - do not describe it as directly
  confirmed until an actual boot or undervoltage event produces one.

**Disposition: closed.** The persistence bug is fixed and live-
verified for connection-stats; the pending step this entry opened is
resolved. See `docs/CHECKPOINTS.md` for the closing record.

## Graceful Self-Diagnosis (First Slice)

**Decision date:** 2026-09-02. Fourth increment of the autonomous
implementation phase, continuing directly from `a44b40c`.

**Built:** `piratebox_diagnose_capability()`
(`includes/capability_state.php`) - `docs/ARCHITECTURE.md` §13's
"explain deterministic problems using known state" goal, first real
slice. A fixed, deterministic lookup keyed on capability id + state,
covering today's actual capabilities (AP/web-app service failures,
power/undervoltage, time confidence, status-helper staleness) -
returns `null` for anything not explicitly covered rather than
inventing an explanation, and `null` for `AVAILABLE`/`NOT_INSTALLED`
(nothing wrong to explain). Surfaced in `admin/index.php`'s
Capabilities table. Confirmed live: correctly explains today's two
real findings (undervoltage detected, no hardware RTC) with the actual
suggested-check text, not just their bare state.

**Not the full future shape yet** - `docs/ARCHITECTURE.md` §13's
AWUS036ACM example (expected device / fallback / Core impact) needs
that hardware to actually exist and be tested first; this slice covers
only capabilities with real state today.

**Tests:** 8 new assertions in `tools/test_capability_state.php` (40
total, was 32) - AVAILABLE/NOT_INSTALLED return null, a real DEGRADED
message is returned and contains the expected content, an unrecognized
capability id returns null rather than guessing, a recognized id with
an uncovered state combination returns null, a missing `state` key
doesn't crash, and diagnosing every live capability never throws.

**Scope preserved:** no networking/GPIO/system config changed, no
packages installed, no community data touched, no fabricated
diagnosis for anything this module doesn't actually know about.

## "Since Last Review" Boundary

**Decision date:** 2026-09-02. Third increment of the autonomous
implementation phase, continuing directly from the previous checkpoint
(`8bdc981`/`7dcbd1f`) without pausing, per operator instruction. Also
confirmed, not just assumed, before starting: `data/reference-packs.
json` and `data/device-history.json` cannot leak into any export/
download surface - `tools/build_export_bundles.py`'s `zip_dir()` only
ever walks explicitly-named static-export subdirectories, never a raw
sweep of `data/`, and neither file is ever rendered into the static
export pipeline at all. Travel Mode's quarantine list
(`includes/travel_mode.php`) needed no change - confirmed by reading
it, not assumed.

**Built:** `docs/DEVICE-MEMORY-DESIGN.md` §3's operator review boundary
- `data/review-boundary.json` (operator-set, same trust boundary as
`data/travel-mode.json` - written by the admin page, not the root
status helper), `piratebox_get_review_boundary()`/
`piratebox_mark_reviewed()` (`includes/device_memory.php`, same atomic
temp-file-then-rename pattern `piratebox_set_travel_mode()` already
uses), a new `mark_reviewed` admin action (non-destructive - doesn't
delete any history, just moves where the summary starts counting from
- same reasoning as `set_travel_mode`/`set_content_profile`,
deliberately not in `$CONFIRM_REQUIRED_ACTIONS`), and
`piratebox_device_memory_since()` - a pure function computing boots/
undervoltage-events at-or-after the boundary from the already-parsed
device-memory array, so every boundary case (never reviewed, a
boundary in the future, one exactly matching an event, empty history)
is directly unit-tested without needing a live file fixture.

**A real design gap found and fixed while building this:**
`piratebox_parse_device_memory()` only returned derived summaries
(`boot_count`, `last_boot_at`), not the raw event list - insufficient
to compute "since a boundary." Fixed by extending its return shape with
`boot_events_recent` (symmetric with the `undervoltage_events_recent`
field it already returned), additive and non-breaking to every existing
caller/test.

**Tested end-to-end, not just unit-tested:** rendered the admin page
against a temporary local `data/device-history.json` fixture (never the
live path) - confirmed "never reviewed" renders correctly, submitted
`mark_reviewed` via a real CSRF-protected POST (session cookie + token
extracted from the rendered page, matching how a real browser would),
confirmed `data/review-boundary.json` was written correctly and the
summary correctly excluded all prior events once the new boundary took
effect. Fixture and resulting files deleted afterward - confirmed via
`git status` that no test artifact was left behind or accidentally
tracked.

**Testing:** all four suites passing - `test_fieldtools.php` 86/86,
`test_capability_state.php` 32/32, `test_reference_packs.php` 15/15,
`test_device_memory.php` 27/27 (was 19) - 160 total assertions. `php
-l`/`bash -n` clean. Every page rendered via `php -S`, zero warnings.
Markdown structure verified in both changed design docs.

**Scope preserved:** no networking/GPIO/system config changed, no
packages installed, no community data touched, `data/review-
boundary.json`/`data/device-history.json` added to `.gitignore` and
`piratebox_deploy.sh`'s exclude list *before* ever being deployed - the
exact mistake the deploy script's own header warns against.

## Capability/Provider Distinction + Reference Content Foundation + Device Memory (first slice)

**Decision date:** 2026-09-02. Second increment of the autonomous
implementation phase, continuing directly from the previous increment
(`636fd49`/`44e2f42`/`92f2ab4`) without stopping at that checkpoint, per
operator instruction that known-good boundaries are for testing/
deploying/documenting/committing, not for pausing.

**Capability/provider distinction (`docs/ARCHITECTURE.md` §3):**
audited `includes/capability_state.php` for a real future need -
PirateBox hosting a capability a companion device (cyberdeck, etc.)
consumes, or the reverse - without building speculative infrastructure
for it now. Smallest change that keeps the door open: every capability
entry gained `provider`/`provider_class` fields (today always
"PirateBox (this device)"/"integrated," since nothing else provides
anything yet), computed by one small pure function
(`piratebox_default_provider()`), not restructured per-entry. No multi-
provider list, selection, or failover logic added - a capability has at
most one provider today because only one needs representing. Also
surfaced as a new column in `admin/index.php`'s Capabilities table.
Tests: 9 new assertions in `tools/test_capability_state.php` (32 total,
was 23).

**Reference content foundation (`docs/REFERENCE-CONTENT-DESIGN.md`,
new):** audited actual content before designing anything - Radio (25)/
Emergency (21)/First Aid (16)/Maps-universal (5) reference entries are
already substantial, already sourced (USGS/NOAA/gps.gov/Red Cross/CDC/
FEMA/NFPA), and already fully independent of Local Information, which
ships empty by design (Stage 6, unchanged - not a gap to fix). Built
`data/reference-packs.json` + `includes/reference_packs.php` - a
Reference Pack model computing live state (INSTALLED/NOT_CONFIGURED/
CANDIDATE/UNKNOWN) from each pack's actual underlying data file, never
from a static claim, organized by the Universal/National/Regional/
Local/Live hierarchy. Surfaced on `/utility/about/`. **No new map or
geographic content was bundled** - this device has no verified WAN path
to source it, and this project's existing content always cites a real,
checked source; `world-reference-map` is recorded as CANDIDATE, not
fabricated or silently dropped. Tests: `tools/test_reference_packs.php`,
15 assertions (missing/malformed/empty files, the Local Information
special-case counting rule).

**Device Memory, first real slice (`docs/DEVICE-MEMORY-DESIGN.md` §15,
updated):** two Operational-History event types - boot events (uptime
lower than last poll = reboot happened) and undervoltage-onset events
(edge-triggered, same "new, not still" discipline connection-stats
already uses) - now detected and bounded-persisted by
`piratebox_status_helper.sh` to `data/device-history.json` (boot events
capped at last 50; undervoltage events daily-bucketed, 90-day window -
deliberately longer than connection-stats' 24h focus, since this needs
to span weeks/months unattended). **Added to `piratebox_deploy.sh`'s
exclude list and `.gitignore` before ever being deployed** - the exact
mistake the deploy script's own header warns against. Persistence logic
verified in isolation (bounding, idempotent same-day increments,
malformed-file recovery, 90-day pruning - `bash`/root paths mean the
live script itself can't run as `moose`, so the extracted Python logic
was tested directly instead). Read side: `includes/device_memory.php`
(`piratebox_get_device_memory()`, refactored into a pure parser +
thin filesystem wrapper specifically for testability - 19 assertions in
`tools/test_device_memory.php`), reporting `available: false` with
every field `null` (never a fabricated zero) until installed live.
Surfaced in `admin/index.php`'s new "Operational history" section,
confirmed live to correctly show the honest unavailable state today.

**One pending operator step, not yet requested** (batched, not blocking
further autonomous work - see this session's own operating
instructions): `piratebox_status_helper.sh`'s deployed copy needs the
same `sudo install -m 0755 -o root -g root ... && sudo systemctl
restart piratebox-status.timer` treatment the time-source fix needed
once already. Deferred to whenever independent work is exhausted, not
requested mid-run.

**Testing:** all four test suites passing after this increment -
`test_fieldtools.php` 86/86, `test_capability_state.php` 32/32,
`test_reference_packs.php` 15/15 (new), `test_device_memory.php` 19/19
(new) - 152 total assertions. `php -l`/`bash -n` clean on every changed
file. Every changed page rendered via `php -S` against this device's
real live state, zero warnings. External-reference grep clean. Markdown
structure verified in all three changed/new design docs.

**Scope preserved:** no networking/GPIO/system config changed (the
Transport Lock/GPIO17 material from the previous increment was design-
only and untouched again here), no packages installed, no community
data touched, no fabricated hardware or content state anywhere
(world-reference-map stays CANDIDATE, Local Information stays
NOT_CONFIGURED, device-history stays `available: false` until actually
installed).

## Self-Awareness Implementation + Physical Transport/Input Safety Design

**Decision date:** 2026-09-02. First increment of the autonomous
implementation phase (operator authorized continuing across related
tasks without per-step confirmation - see this session's own
instructions). Recovered state first (clean tree at `3b6a252`, live
hardware/services matched `docs/CAPABILITY-REGISTRY.md` exactly, no
drift) before starting.

**Built: `includes/capability_state.php`** - `docs/ARCHITECTURE.md`
§6/§10 moved from principle to implementation. One shared, tested
module (`piratebox_get_capability_state()`/
`piratebox_get_operational_state()`) covering 12 capabilities across
all three layers, using that document's exact state vocabulary
(NOT_INSTALLED/AVAILABLE/DEGRADED/UNAVAILABLE/UNKNOWN) and never
fabricating a healthy state - reads exclusively through existing
channels (`piratebox_get_helper_status()`, `piratebox_get_time_source_
status()`), no new hardware/filesystem access. The trickiest
classification decisions (service-pair up/down, power/undervoltage,
RTC presence) were factored into small pure functions
(`piratebox_classify_*`) specifically so they're unit-testable without
faking `/run/piratebox/status.json` - `tools/test_capability_state.php`
(new, 23 deterministic assertions: null/missing fields, stale helper,
degraded vs. unavailable vs. unknown, a structural smoke test of the
live function, and a sanity check that `core_dependency=true` never
appears outside `layer=core`).

**Built: `/utility/about/`** (public) and `admin/index.php`'s new
"Capabilities & Health" section (password-gated, same nginx Basic Auth
boundary as the rest of that page) - progressive disclosure in
practice, not just principle: the public page shows layer-level
counts and Core status only; the admin section shows the full
per-capability table including power/undervoltage detail. **Exposure
boundary was not invented here** - the public page was built to match
what `/utility/status/` already treats as public-safe (storage, device
ID, service up/down) and deliberately excludes what that page already
keeps operator-only (undervoltage specifics), confirmed by reading that
page's actual code before writing the new one, not assumed.

**Physical input/transport safety - design formalized, no code
changed, per operator instruction added mid-run:**
`docs/PHYSICAL-CONTROL-UX-DESIGN.md` gained a new §4 covering
accidental-input resistance, a Transport Lock concept (`PHYSICAL
CONTROLS: ENABLED/LOCKED/DEGRADED/INPUT FAULT/UNKNOWN`, design only, no
hardware chosen), invalid/contradictory-input handling (suppress, never
guess intent), GPIO17 mode-change validation principles (ahead of that
switch's physical install), and self-awareness integration. **§4.1 is a
real code review, not just design prose:** `piratebox_button_daemon.py`
was read in full and checked against every accidental-input-resistance
goal - 50ms debounce, a 4.0s continuous-hold requirement with zero code
path for any short press, `hold_repeat=False` (fires once even on an
indefinitely stuck-low pin), and a fail-toward-inaction shutdown gate.
**Conclusion: no change needed** - the commissioned GPIO25 control
already satisfies this model by construction; a demonstrated deficiency
would be required to change it, and none was found. One question is
explicitly left open rather than defaulted: whether GPIO25 shutdown
should remain available while a future Transport Lock is engaged -
flagged in the doc (§4.4) for whenever a lock mechanism is actually
designed, not answered now.

**Capability registry reconciled, not just extended:** added the
self-awareness module, the About page, and the Transport Lock concept
as new entries (two INSTALLED/CURRENT SCOPE - real, tested code; one
CANDIDATE - design only, honestly not promoted to PLANNED or OWNED).

**Testing:** `php -l` clean on every new/changed PHP file; both test
suites passing (`test_fieldtools.php` 86/86 unaffected,
`test_capability_state.php` 23/23 new); every new/changed page rendered
via `php -S` against this device's real live `/run/piratebox/status.
json` - confirmed the admin Capabilities table honestly shows today's
two real open findings as DEGRADED (undervoltage-now, and time
confidence with no RTC installed), not a fabricated AVAILABLE; zero PHP
warnings anywhere; external-reference grep clean; search index
regenerated (91 entries, +1 for the About page, no `regional` flag);
markdown structure verified in both changed design docs (heading
sequences, table column counts, code fences).

**Scope preserved:** no networking/GPIO/system config changed (the
button-daemon review was read-only), no packages installed, no
community data touched, no fabricated hardware state anywhere
(transport lock and every unwired button/toggle still read
NOT_INSTALLED, not guessed).

## Device Memory / Unattended-Operation Design

**Decision date:** 2026-09-02. Documentation-only follow-on to the
architecture formalization below - **no runtime, system, network,
GPIO, or web behavior changed; nothing deployed.** Formalizes how
PirateBox should eventually remember what happened while unattended
(powered occasionally, carried in a backpack for a trip, run for days
without the operator looking, reviewed weeks or months later) - an
extension of the self-awareness model, explicitly not a rejection of
its existing privacy principles.

**New: `docs/DEVICE-MEMORY-DESIGN.md`** - the dedicated design doc,
created (rather than folding everything into `docs/ARCHITECTURE.md`
directly) because the material is substantial enough to warrant the
same treatment `docs/FIELD-TOOLS-DESIGN.md`/`docs/TRAVEL-MODE-DESIGN.md`
already get: a refined history principle ("retain enough history... but
make retention purposeful, bounded, privacy-classified, and appropriate
to the capability" + "PirateBox should be able to summarize the period
since the operator last reviewed it" - both explicitly *extending*, not
replacing, the existing "prefer current-state awareness over historical
surveillance" rule); the operator "since last review" concept; the
Operational History vs. Sensitive Observation History distinction;
retention-class semantics (Current Only / Event History / Summary
History / Explicit Capture / Sensitive Capture) with the seven
questions any future retained datum should answer; aggregation-over-
raw-samples; the optional (never required) Field Session concept;
reinforced GNSS-history/GNSS-availability separation; "unattended
operation is normal" as identity, with its implications named for
future health/status/retention/time-confidence/self-diagnosis work;
self-awareness extended with history-aware questions; a reinforced
privacy boundary plus the new symmetric retention principle
("information is retained because there is a deliberate operational
purpose... not merely because PirateBox was capable of observing it");
storage/durability considerations (deferring to the *existing*
authoritative Stage 24/25 discipline, not inventing a new one); and the
open ownership-transfer interaction question.

**Grounded in real precedent, not invented from scratch:** the entire
model generalizes the already-shipped connection-statistics feature
("Post-Stage-32: Privacy-Preserving Connection Statistics," below) -
its `{hour_start, count, peak}` retention pattern is cited throughout
as the concrete example of Summary History and Current-Only classes
already working correctly in production.

**`docs/ARCHITECTURE.md` changed** (concise principle-level touches +
pointers, not duplication, per instruction): §1 gains a short
"unattended operation is part of this identity" paragraph; §7 (GNSS)
gains a short reinforcement that GNSS history is a separate question
from GNSS availability; §10 (self-awareness) gains a pointer to the new
history-aware questions; §12 is refined in place with the two new
principles above and a pointer to the full model rather than repeating
it; §16 (ownership transfer) gains an explicit note that historical
data privacy classes are now part of that still-undecided question;
§20/§21 updated accordingly.

**`docs/CAPABILITY-REGISTRY.md` changed minimally, only where a
capability-specific implication genuinely belongs** (per instruction
not to bloat every entry): the GNSS receiver entry gains a one-line
retention note; the undervoltage/power-quality monitoring entry (the
one capability that already has real, live status data this model
could someday extend) gains a one-line note connecting it to the
Operational History class. No other entry touched.

**`CLAUDE.md` changed minimally:** one new routing-table row pointing
to `docs/DEVICE-MEMORY-DESIGN.md`. No philosophy added to `CLAUDE.md`
itself.

**Explicitly not done, per instruction:** no logging mechanism,
database, retention job, review-boundary UI, Field Session handling, or
GNSS capture was implemented. Every forward-looking claim in the new
document is marked "not implemented"/"conceptual only," reviewed
specifically for accidental implementation claims before committing.

**Testing:** prose documents - no `php -l`/`bash -n` applies. Verified
markdown structure (heading sequences sequential with no gaps in both
`docs/ARCHITECTURE.md` and the new document; code fences balanced) and
re-grepped for present-tense implementation language before committing;
every match found was meta-commentary about the documents themselves.
No live deployment - touches no `var/www/html` content, so no backup/
checkpoint snapshot was needed (same "docs-only stage" pattern as the
architecture-formalization entry below).

## Architecture / Philosophy Formalization: Core-Operational-Optional, Privacy, Ownership, Self-Awareness

**Decision date:** 2026-09-02. Documentation/architecture-only - **no
runtime, system, network, GPIO, or web behavior changed.** Two new
durable documents formalize this project's long-term direction, per
explicit operator request to establish design principles *before*
implementing any of what they describe:

- **`docs/ARCHITECTURE.md`** (new) - project identity as a "field
  utility node"; the Core/Operational/Optional layering and its
  governing rule ("optional capability failure must degrade, not
  disable"); the Integrated/Attachable/Network-Companion/Operator-
  Device classification for external equipment; physical-modularity
  goals (no hard commitment to a design, just principles + a
  before-you-add-hardware checklist); privacy-first-not-exposure-
  incapable philosophy, with GNSS position/time separation as the
  concrete worked example; physical/operational discretion (Normal/
  Attention/Warning/Critical); progressive UI disclosure (Public/
  Operator/Advanced/Diagnostics); the self-awareness model ("what am I/
  what do I have/..."); fact-vs-configuration-vs-inference-vs-intent
  semantics; current-state-awareness-over-surveillance (explicitly
  generalizing the existing connection-statistics design); graceful
  self-diagnosis as a future goal; the four-level trust model (Access/
  Operation/Ownership/Recovery-Claim); transferable-ownership and
  data-aware-transfer principles; the self-describing/inheritable-
  device goal; and "no final PirateBox" project-management philosophy.
- **`docs/CAPABILITY-REGISTRY.md`** (new) - the concrete inventory
  companion: every capability from today's real hardware (Pi 3B+,
  built-in `wlan0`, the GPIO25 button) through owned-but-not-yet-wired
  hardware (OLED, toggle switch, remaining buttons, the ALFA
  AWUS036ACM/ARS-N19) to pure candidates (GNSS, environmental/air-
  quality/motion/proximity/sound/lightning/radiation sensing, SDR, ham
  radio, ESP32/companion nodes), each state reconciled against existing
  docs or a live check, not assumed.

**Reconciliation, not a rewrite - findings from actually checking
first:**
- The ALFA AWUS036ACM and its antenna are **ordered/incoming, not
  arrived, not tested** - confirmed both from `docs/OPERATIONAL-
  DECISIONS.md`'s own existing "Wi-Fi adapter notes" entry and a live
  `lsusb` (only the earlier-rejected TP-Link TL-WN722N is physically
  attached today). The production AP remains `wlan0`, unchanged.
- The ALFA ARS-N19 antenna was not previously recorded in any doc in
  this repo - recorded now on the operator's own statement, explicitly
  flagged in `docs/CAPABILITY-REGISTRY.md` as newly-recorded rather
  than independently confirmed (antennas don't enumerate on USB).
- The DS3231 RTC is **planned (a specific, repeatedly-named candidate
  part), not purchased** - `docs/RTC-TIME-READINESS-DESIGN.md`
  originally listed it as one example among standard I2C RTC breakouts;
  later docs (`docs/FIELD-TOOLS-DESIGN.md`, `docs/PHYSICAL-CONTROL-UX-
  DESIGN.md`) treat it as *the* intended part. Neither ever claims it
  was bought - `docs/CAPABILITY-REGISTRY.md` preserves that distinction
  explicitly rather than promoting "planned" to "owned."
- GNSS, environmental/air-quality/light/motion/proximity/sound/
  lightning/radiation sensing, SDR, and companion-node ideas have
  **zero prior mention anywhere in this repo** - confirmed by grep
  before writing anything, so nothing here overwrites an existing
  decision; this is genuinely new ground, recorded as CANDIDATE only.

**Naming collision found and flagged, not silently resolved:** the new
"Recovery/Claim" concept (administrative-authority transfer when the
device legitimately changes owners - `docs/ARCHITECTURE.md` §14-16) is
**not** the same thing as Stage 16's existing, already-shipped "Found
Device" / "Recovery Messages" concept (a lost device inviting whoever
finds it to message the *current* owner back - never touches
administrative authority). Both can coexist, but future work naming
either concept should keep the terms distinct - noted as an open item
in `docs/ARCHITECTURE.md` §20 rather than renamed now.

**Confirmed compatible with, not contradicting, existing decisions**
(checked, not assumed): the canonical `http://piratebox/` URL and its
no-HTTPS-MITM stance; the documented Android captive-portal limitation;
privacy-preserving aggregate connection statistics (the direct
precedent §12's "current-state awareness, not surveillance" principle
generalizes); Travel Mode's manual-authority/privacy-safe-by-default
design (the direct precedent §6-7's exposure philosophy generalizes);
Normal/Emergency Mode's presentation-only scope (already never implies
"publish everything" - confirmed, not newly imposed); current GPIO
reservations; the GPIO25 shutdown button implementation; the Wi-Fi
migration's deliberate testing-first discipline; RTC/`fake-hwclock`
decisions; the open undervoltage caveat (left open, not resolved here);
deployment/`VERSION` provenance rules; `CLAUDE.md`'s recovery
architecture (routing table extended, not restructured); and Field
Tools' design (cited throughout as the concrete, already-shipped
example of several of these principles in practice).

**Explicitly not done, per instruction:** no service, hardware support,
device discovery, authentication, ownership recovery mechanism, GNSS
behavior, companion protocol, UI feature, GPIO behavior, package, or
deployment was implemented. Every mechanism-level question in the new
documents (ownership-claim sequence, data-reset behavior, Quiet/Stealth
triggers, the self-description page, a capability-state schema, the
PCA9548A decision) is explicitly recorded as undecided future work, not
guessed at.

**Testing:** `docs/ARCHITECTURE.md`/`docs/CAPABILITY-REGISTRY.md` are
prose - no `php -l`/`bash -n` applies. Reviewed the full diff before
committing specifically for accidental claims of implemented
functionality; every forward-looking section carries an explicit "not
implemented"/"conceptual only" marker. No live deployment - this
touches no `var/www/html` content, so no backup/checkpoint snapshot was
needed (matching the existing "docs-only stage" pattern in
`docs/CHECKPOINTS.md`, e.g. Stage 11/12).

## Field Tools / Offline Reference Instruments

**Decision date:** 2026-09-02. A new, self-contained public section -
`/utility/fieldtools/` - adding a third role to this device alongside
"public file/community service" and "operator console" (Stage 29):
**field instrument**. Time/date tools, unit conversion (temperature,
distance, mass, volume, speed, pressure, storage, percentage,
electrical/battery), and a coordinate (DD&harr;DMS) converter - useful
when this box is operating for days with no mains power, cell service,
or Internet. Full design, architecture rationale, and testing detail in
`docs/FIELD-TOOLS-DESIGN.md` - this entry is a summary.

**Scope boundary honored:** no networking/captive-portal/GPIO/Travel-
Mode-semantics change, no packages installed, no community data
touched. Plain PHP/HTML/CSS + dependency-free local JavaScript only -
zero external web/API/CDN calls anywhere in this feature (verified by
grep, not assumed).

**New files:** `includes/fieldtools_convert.php` and `includes/
fieldtools_time.php` (pure, tested conversion/time functions -
`piratebox_get_time_source_status()` is written to auto-detect a future
DS3231 with zero code change, see `docs/FIELD-TOOLS-DESIGN.md` §4);
`public/utility/fieldtools/{index,time/index,units/index,
coordinates/index}.php`; `public/assets/fieldtools.js` (client-side
mirror of the PHP formulas, for instant feedback with no build step -
see that doc §6 for why); `tools/test_fieldtools.php` (86 deterministic
CLI assertions, all passing - boundary/sign cases, decimals, round
trips). **Changed:** `public/utility/index.php` (new nav card),
`public/utility/search/index.php` (new section label),
`tools/build_search_index.py` + regenerated `data/utility/search-index.
json` (7 new entries, none `regional`), `public/utility/maps/index.php`
(one cross-link to the new coordinate converter), `public/assets/
styles.css` (dark-theme styling for number/date/time/select inputs the
existing rules didn't cover, plus three small layout classes).

**Real bug found live, before this stage's first deploy - `open_
basedir` blocked the direct time-source reads:** `piratebox_get_time_
source_status()`'s first version read `/sys/class/rtc/`, `/run/systemd/
timesync/synchronized`, and `/etc/fake-hwclock.data` directly. `php -l`
can't see this class of bug - only rendering the page for real caught
it: PHP-FPM's existing `open_basedir` restriction (`etc/php/8.4/fpm/
php.ini`) blocks every one of those paths, and `file_exists()`/`glob()`
under `open_basedir` return a silent `false` rather than an exception -
exactly the "looks like a real negative, isn't" failure this feature is
supposed to refuse to produce. **Fixed before shipping, not shipped and
revisited:** moved the actual reads into `piratebox_status_helper.sh`
(runs as root, no `open_basedir`), which now publishes a `time_source`
block into `/run/piratebox/status.json` (which IS inside `open_
basedir`); `piratebox_get_time_source_status()` reads that instead, via
`includes/metrics.php`'s existing `piratebox_get_helper_status()` - the
same pattern that function's own header already documents for exactly
this class of problem. The function's return shape grew a third state
(`available`/`stale` alongside the three fields, which are `null` -
never fabricated - whenever `available` is false) to honestly cover
"the deployed status helper hasn't been updated to publish this yet."
**That third state was this device's live condition at the time of the
`58ef5bb` commit** - confirmed live then (rendered via `php -S` against
this device's real, unmodified `/run/piratebox/status.json`), not
simulated. Full account: `docs/FIELD-TOOLS-DESIGN.md` §4/§9.

**Operator step RESOLVED 2026-09-02** (was pending since `58ef5bb`;
`piratebox_status_helper.sh`'s deployed copy at `/usr/local/bin/`
predated this fix and had no dedicated installer script, unlike
`piratebox_deploy.sh`/`set_piratebox_mode.sh`'s `setup_claude_
automation.sh`, and no `sudo` grant the original session held):
operator ran `sudo install -m 0755 -o root -g root piratebox_status_
helper.sh /usr/local/bin/piratebox_status_helper.sh && sudo systemctl
restart piratebox-status.timer` in a later session. Verified after:
installed copy byte-identical to repo source; service ran to
`status=0/SUCCESS`; live `/run/piratebox/status.json` now carries a
real `time_source` block (`rtc_detected`/`ntp_synchronized`/
`fake_hwclock_installed` all real booleans - `false`/`false`/`false`,
honestly matching this device's actual state); the live Time page
renders the "available" branch, not "not currently reporting"; zero
PHP warnings; all core services and the timer active; zero failed
units. Full account: `docs/FIELD-TOOLS-DESIGN.md` §9.

**Real, disclosed-not-fixed finding:** this device's PHP has no
`date.timezone` configured, so `date()` defaults to UTC regardless of
system timezone - the Time page detects and explains this rather than
silently showing identical Local/UTC columns. Not fixed here
(app-wide blast radius, a separate future stage) - see `docs/
FIELD-TOOLS-DESIGN.md` §6.

**Travel Mode / Content Profile:** deliberately not integrated - this
section has no local-sensitive or hazard-scenario content. See `docs/
FIELD-TOOLS-DESIGN.md` §5 for why.

**Stage 29 (OLED) design updated, no hardware changed:** `docs/
PHYSICAL-CONTROL-UX-DESIGN.md` §1 now specifies Clock/Time as a
first-class fourth OLED page (was three pages), reading this stage's
new `piratebox_fieldtools_now_snapshot()`/`piratebox_get_time_source_
status()` functions once that hardware exists. No OLED is wired - this
is a design-document update only, per instruction not to write hardware
code for display that isn't physically installed.

**Testing:** see `docs/FIELD-TOOLS-DESIGN.md` §8 in full - `php -l`/
`bash -n` clean on every file, all pages rendered via `php -S` with zero
warnings/errors (including, after the fix above, against this device's
real live status snapshot), 86/86 deterministic test assertions
passing, search index regenerated and spot-checked, external-reference
grep clean. Not tested: real-browser JavaScript execution (no browser
available in this environment). The Time page's "available" rendering
branch was subsequently confirmed live once the operator step above
closed on 2026-09-02; the "RTC detected" branch remains untested
against a live snapshot for the obvious reason that no RTC hardware
exists on this device - covered instead by a deterministic test of the
underlying three-state decision logic plus direct code review.

**Deployment:** see this repo's `git log`/`includes/VERSION` for current
status as of any later reading - not asserted here to avoid this entry
going stale the way a hardcoded claim would (see `CLAUDE.md` §1a on
why). Checkpoint backup taken before any change in this stage:
`~/piratebox-backups/fieldtools-pre-20260902-031945/` (full `var/www/
html` mirror + pre-change git HEAD `e0ba886`).

## VERSION Honesty Marker

**Decision date:** 2026-09-02. Found while validating the new
`CLAUDE.md` recovery entrypoint's "does live match this checkout"
check (see `docs/CHECKPOINTS.md` and `CLAUDE.md` §1/§1a): live
`includes/VERSION` read `e90e099` (the canonical-URL checkpoint
commit) - noticeably older than `main`'s tip, and older than Travel
Mode's own commit (`a6f5143`).

**Verified this was a stale stamp, not stale content:** a full
checksum-based repo-vs-live comparison (`rsync --dry-run --checksum`,
the exact exclude list `piratebox_deploy.sh` itself uses) showed every
deployed file byte-identical to the repo, `includes/travel_mode.php`
included. The live application was current; only the version string
was wrong.

**Root cause, reconstructed from `git reflog` and file mtimes:** Travel
Mode was built in `worktree-travel-mode` and, per this project's normal
practice, its files were already present in `main`'s own working tree
before the branch was formally merged. A real deploy ran at 23:41:12
that evening - correctly syncing that already-present content live,
and correctly reading `git rev-parse HEAD` at that exact instant, which
was still `e90e099` because `git merge worktree-travel-mode` didn't
land until 23:45:14 (`git reflog`). Nothing since (GPIO25, this
recovery-infrastructure work) has touched `var/www/html`, so nothing
has re-triggered the stamp - expected, not a bug, given what `VERSION`
is defined to mean (see below).

**What this is:** a real, reproducible timing hazard, not a one-off.
`VERSION` means "the commit `HEAD` pointed to, in this checkout, at the
instant the last real deploy's `git rev-parse` ran" - accurate only
when the working tree and `HEAD` agree at that moment. This project's
own worktree-then-merge-afterward development pattern can make that
false, and it will recur any time a real deploy happens to run inside
that window again.

**Fix - workflow note, not a rewrite:** `piratebox_deploy.sh`'s header
now states the expected order explicitly: merge the tested
worktree/branch into `main` before running a real deploy for it, not
after. Not a hard gate - a deliberate out-of-order deploy for recovery/
debugging is still fine to run - just the documented normal case.

**Fix - VERSION honesty marker (`piratebox_deploy.sh`):** every real
deploy now also checks whether the deploy source itself
(`var/www/html/`, not the whole repo) differs from the `HEAD` it's
about to stamp - `git status --porcelain` scoped to `.` from inside
that directory, so unrelated dirty files elsewhere (README, docs, an
unrelated in-progress branch) never taint it, and gitignored live-data/
generated runtime artifacts (chat/messages/bulletin JSON, `VERSION`
itself, `public/utility/exports/`, etc.) are excluded the same way they
always were - no second exclude list to maintain. Clean source still
stamps the plain `<commit>  (deployed <timestamp>)` line; a source with
tracked or untracked deployable changes beyond that commit gets an
appended `(source had changes beyond this commit)`. Deliberately does
**not** guess at a "real" commit, auto-commit anything, or block the
deploy - an honest provenance marker, not a new deployment gate.
**Found and fixed in the same pass:** `.gitignore` was missing
`var/www/html/data/chat.json.lock`, even though
`piratebox_deploy.sh`'s own rsync excludes already named it - left
alone, that gap would have made the new honesty check false-positive
the moment that lock file happened to exist untracked.

**Tested against an isolated local clone (never the live site):** the
patched script's real (non-dry-run) VERSION-stamping logic, run
end-to-end, confirmed clean-source → clean line; a tracked edit under
`var/www/html/` → the qualified line; an edit outside `var/www/html/`
(README) → still the clean line; an untracked `chat.json.lock` under
`var/www/html/data/` → clean line once the `.gitignore` gap above was
closed (and confirmed it *would* have false-positived before that
fix). `bash -n` clean. Dry-run's non-mutating behavior is structurally
unchanged - the new logic lives entirely inside the same
`if [ "${#DRYRUN[@]}" -eq 0 ]` block the original stamp already used.

**Left untouched, deliberately:** live `/var/www/html` and its
`VERSION` file - this was a diagnosis-and-mechanism fix, not a live
deploy. Live `VERSION` still reads `e90e099` as of this entry; it will
correct itself the next time an actual web-tree change gets deployed,
now with the added honesty marker if that ever happens out of order
again.

## Stage 29 Implementation: Physical Shutdown Button (GPIO25)

**Decision date:** 2026-09-02. The first piece of Stage 11/29's
hardware design (`docs/HARDWARE-INTEGRATION-DESIGN.md`,
`docs/PHYSICAL-CONTROL-UX-DESIGN.md`) to move from design-only to
physically real. A 12mm normally-open momentary push button has been
connected to this Pi 3 B+ and brought up carefully, in stages, per
explicit instruction: read-only discovery first, safe electrical
testing before any persistent code, persistent-service testing in
dry-run before any real action, and the real shutdown action gated
behind its own explicit final step.

**Wiring mix-up caught before it mattered:** the button was initially
connected to physical pins 6 and 9 - **both GND**. Software-side
scanning (a `gpiomon`-based sweep of every header pin not already
reserved by I2C/UART/HAT-EEPROM) correctly found nothing, because there
was genuinely no GPIO in the circuit at all - the switch was just
shorting two ground points together. No electrical risk occurred either
way; this was caught by manual physical-pin inspection (a labelled 40-
pin header diagram) once automated scanning legitimately found nothing
to report, exactly the fallback the discovery process was designed to
reach.

**Bring-up test, GPIO25/physical pin 22 (other leg on physical pin 9,
GND), performed interactively before any persistent code existed:**
- Idle state: confirmed HIGH (internal pull-up, switch open).
- Pressed state: confirmed LOW (pulled to GND).
- Debounce: clean across roughly 20 taps in two separate test runs -
  zero bounce artifacts at 20ms software debounce.
- Short vs. long press: taps measured 0.08-0.56s, deliberate holds
  1.0-1.5s, and a 4.0-second hold threshold fired **exactly once**,
  precisely at 4.0s, with no re-fire during an extended 7.27s hold.
- Zero conflicts found with I2C (GPIO2/3, reserved for the not-yet-
  arrived OLED), UART (GPIO14/15, actively serving the serial console),
  or the existing dual-fan/heatsink setup (no fan-control overlay,
  service, or kernel module exists anywhere on this system - the fans
  are almost certainly wired to the header's fixed power pins, not any
  GPIO).
- One real bug found and fixed during this bring-up, unrelated to the
  hardware itself: the first Python test script's `print()` output was
  invisible until process exit, because Python fully buffers stdout
  when redirected to a file rather than a terminal. Every press had
  actually been detected correctly the whole time; fixed with explicit
  line buffering.

**Architecture - matches the project's existing privileged-helper
pattern exactly, not a new one:**
- `piratebox_button_daemon.py` (repo root, deployed to
  `/usr/local/bin`, root-owned/moose-unwritable - same anti-tampering
  property as `piratebox_deploy.sh`) - a `gpiozero`-based daemon,
  event-driven (kernel GPIO line-event notification via the `lgpio` pin
  factory, not a polling loop), watching only GPIO25.
- Runs as a **new dedicated, unprivileged system user
  (`piratebox-gpio`)** - no login shell, no home directory, member only
  of the `gpio` group - never `www-data`, never root, and deliberately
  not `moose` either (keeping this daemon's blast radius smaller than
  the interactive operator account's).
- `etc/sudoers.d/piratebox-button` - a **separate** narrow NOPASSWD
  grant (`piratebox-gpio ALL=(root) NOPASSWD: /usr/bin/systemctl
  poweroff`, no arguments to vary) - deliberately not added to
  `etc/sudoers.d/piratebox-claude`, which is a different actor's trust
  boundary (this session's deploy/mode-switch automation), per Stage
  29 §3's own explicit instruction.
- `etc/systemd/system/piratebox-button.service` - continuous (not
  timer-triggered like `piratebox-status`/`piratebox-backup`, since it
  must react the instant a press happens), `Restart=on-failure`.
  Deliberately does **not** set `NoNewPrivileges=yes` - the one
  hardening flag that would block this daemon's single legitimate
  escalation path - documented explicitly in the unit file as an
  understood exception, not an oversight.
- `setup_piratebox_button.sh` - one-time installer mirroring
  `setup_claude_automation.sh`'s exact pattern (create user, install
  daemon, validate + install sudoers with `visudo -cf` first, install +
  enable the systemd unit).

**Fails safely by design, not just by accident:**
- A short press has **no code path to anything** - not logged, not
  acted on, nothing.
- The real `poweroff` call is gated behind an explicit opt-in
  (`PIRATEBOX_BUTTON_ENABLE_SHUTDOWN=1`, set only in the systemd unit
  once the persistent service is verified end-to-end) - **absent by
  default**, so a misconfiguration can only ever fail toward inaction,
  never toward an unwanted shutdown.
- `sudo -n` (non-interactive) - if the sudoers grant is ever missing or
  broken, this fails immediately with a clear log line instead of
  hanging.
- No per-event data is written anywhere - not to a JSON store, not a
  log line for ordinary presses, nothing resembling the connection-
  statistics or Travel Mode data files. The only write this daemon ever
  produces is the one, rare, significant "long press detected" log
  line, captured by journald the same way every other systemd service's
  output already is.
- Orthogonal to Travel Mode, connection statistics, and every other
  PirateBox function - this daemon reads nothing from and writes
  nothing to any PirateBox data store, touches no web app code, and
  makes no networking/nginx/hostapd/dnsmasq change of any kind.

**Standalone dry-run test, before any systemd install:** ran the daemon
script directly (unbuffered) with `PIRATEBOX_BUTTON_ENABLE_SHUTDOWN`
unset - confirmed a quick tap produced **zero** output, and a
deliberate 4+ second hold produced exactly one "LONG PRESS DETECTED -
would request shutdown (no action taken...)" log line, with no `sudo`
call attempted.

**Real bug found and fixed when the systemd service first went live:**
`piratebox-button.service` crash-looped (`Could not claim GPIO25:
[Errno 22] Invalid argument`) on its first install. Root cause:
`gpiozero`'s `lgpio` pin factory needs to write a small notification-
pipe file (`.lgd-nfy*`) into its own working directory; with no
`WorkingDirectory=` set, systemd defaults to `/`, which
`ProtectSystem=strict` makes read-only - so `lgpio` failed, then
`rpigpio` failed the same way, `pigpio` isn't installed, and gpiozero
fell all the way back to a broken experimental pin factory that could
not actually claim the pin. Fixed by adding `WorkingDirectory=/tmp`
(confirmed `tmpfs`/RAM-backed via `mount`, so this still produces zero
SD card writes, and `PrivateTmp=yes` keeps it private to this service).
Verified syntactically with `systemd-analyze verify` before rolling out.

**Live persistent-service verification, after the fix (2026-09-02):**
- `systemctl status piratebox-button.service` - `active (running)`,
  clean startup log line, no pin-factory fallback warnings.
- Two live short taps against the running service produced **zero**
  log output - matches the standalone test exactly.
- One live ~4-5 second hold produced exactly one "LONG PRESS DETECTED -
  would request shutdown (no action taken; ...)" line, no `sudo` call
  attempted - matches the standalone test exactly.
- Confirmed no regression to the rest of the system: `nginx`,
  `php8.4-fpm`, `hostapd`, `dnsmasq`, and `piratebox-backup.timer` all
  `active`; `piratebox-status.timer` firing on schedule; the web app
  responded `200 OK`.
- Confirmed `piratebox-gpio`'s privileges stayed exactly as scoped:
  member of `piratebox-gpio` and `gpio` groups only - no `sudo` group,
  no `www-data`.

**What is deliberately not touched:** the OLED page state machine
(Stage 29 §1) and the four other momentary buttons (GPIO17 toggle,
GPIO22/23/24/27) remain exactly as designed and completely unwired -
this stage implements only the one button that's physically present.

## Stage 29 Real-Hardware Confirmation: Physical Shutdown Button, Full Power Cycle

**Decision date:** 2026-09-02, immediately after the implementation above.
Everything in the "Stage 29 Implementation" entry was verified with the
service *running* but had not yet been used to actually take the Pi down
and bring it back up on its own. This entry records that end-to-end test,
performed on the Pi moved to its **standalone wall-brick power supply**
(not a shared/USB-hub source), plus the post-boot verification that
followed.

**The test:** held the physical button (GPIO25/physical pin 22) for
~4 seconds. Result: the Pi shut down and the SSH session closed, exactly
as designed - real `sudo systemctl poweroff`, triggered by a real 4-second
hold, on real standalone power, with no dry-run flag involved. This is
the first time this feature has taken the machine all the way down.

**Post-boot verification, performed on this fresh boot:**

- **Clean shutdown, confirmed:** current boot's kernel/journal log shows
  no ext4 journal-recovery message (`recovering journal`, which ext4
  prints specifically when replaying incomplete transactions from an
  unclean unmount) - only the routine, always-normal `orphan cleanup on
  readonly fs` line. The FAT32 boot partition's `systemd-fsck` run
  reported a clean scan (`432 files, 135165/1032408 clusters`) with no
  dirty-bit warning or corrections. No errors/corruption anywhere in
  `dmesg` for this boot. (This machine has no persistent journald storage
  or syslog - `/var/log/journal` doesn't exist and nothing else logs
  reboot events across boots - so this is read from filesystem-integrity
  evidence on the new boot rather than a log line from the old one; that
  evidence is unambiguous either way, and here it says clean.)
- **Button service, autostart + still armed:** `piratebox-button.service`
  is `enabled` and came up on its own post-boot (`active (running)`,
  started automatically ~49s after boot via `multi-user.target`, no
  manual intervention). Its startup log line confirms
  `PIRATEBOX_BUTTON_ENABLE_SHUTDOWN` survived the reboot inside the unit
  file itself (it's baked into `etc/systemd/system/piratebox-button.service`,
  not set by hand at a shell, so there was never really a way for it to
  *not* survive) - "Real shutdown ENABLED" logged at start. Confirmed the
  process still runs as the unprivileged `piratebox-gpio` user/`gpio`
  group, not root.
- **All PirateBox services/features healthy:** `nginx`, `php8.4-fpm`,
  `hostapd`, `dnsmasq`, `piratebox-backup.timer`, `piratebox-status.timer`
  all `active`; `systemctl --failed` shows zero failed units; the web app
  answers `200 OK` on both `http://localhost/` and `http://piratebox/`;
  the AP (`wlan0`, SSID `PirateBox`) is up.
- **Undervoltage/throttling check on the new power source - a real
  finding, not a clean bill of health:** `vcgencmd get_throttled` reads
  `0x50005` (under-voltage-now, throttled-now, under-voltage-has-occurred,
  and throttled-has-occurred bits all set), and `dmesg` shows one
  `hwmon hwmon1: Undervoltage detected!` line ~20 seconds into this boot.
  Rechecked three more times over the following ~35 seconds - the
  "-now" bits stayed set throughout, not just a boot-time blip that
  cleared. At the same time, measured rail voltages read essentially
  nominal (`core` 1.2000V, `sdram_c` 1.2500V), the CPU governor
  (`ondemand`) had all four cores back at the full 1400MHz (not
  frequency-capped), and no USB reset/disconnect/over-current messages
  appear in the journal - so whatever tripped the firmware's
  undervoltage flag did not visibly degrade performance or destabilize
  any attached USB device (including the Wi-Fi adapter) during this
  check. This is exactly the failure mode `docs/POWER-UPS-DESIGN.md`
  §2.1/§2.2 already treats as a known risk on this hardware family, and
  this wall brick has now been directly observed producing a live
  undervoltage flag on boot-up current draw. **Conclusion: this specific
  wall brick is not confirmed adequate for sustained use** - it got the
  Pi through boot and normal operation without an observed crash or
  reset this time, but a firmware that's flagging live undervoltage on
  every check during a low-load idle period is not a supply with real
  headroom, and headroom is exactly what matters once the AP is under
  real transmit load. Follow-up (not done as part of this test):
  measure this brick's actual rated output current against the Pi 3B+
  + attached Wi-Fi adapter's combined real-world draw, and treat it as
  a candidate for replacement rather than as validated, per the
  UPS/power-supply evaluation criteria already written up in
  `docs/POWER-UPS-DESIGN.md`.

**Net result:** the shutdown button's real-world behavior is fully
confirmed - press, shutdown, power-cycle, clean reboot, service
rearms itself with no manual step. The one open item this test
surfaced is unrelated to the button feature itself: this particular
wall brick's power headroom is now a documented open question, not an
assumption.

## Post-Stage-32: Travel Mode - Privacy-Preserving Local Information Suppression

**Decision date:** 2026-09-01. A third small, deliberate post-roadmap
feature, kept in its own commit separate from connection statistics and
the `http://piratebox/` hostname work. Full design, threat model, and
future-automation notes in `docs/TRAVEL-MODE-DESIGN.md` - this entry is
a summary.

**What it does:** an operator toggle that suppresses this PirateBox's
region-specific content (Local Information, the regional map catalog,
and local results in search/exports) without deleting any of it, for
when the device is deliberately relocated away from its usual area.

**Full audit performed first, per instruction:** every consumer of
`data/utility/local/info.json` was enumerated before any code was
written - the Local Information page itself, Global Search (which bakes
real hospital/repeater data into its index once populated), the two
"Take This With You" bundles that embed a static copy
(`maps-local-bundle.zip`, `complete-utility-library.zip`), and the Maps
page's region-specific catalog (distinct from that same page's
universal coordinate/GPS section). Generic nav links/prose that only
name "Local Information" without revealing content were deliberately
left alone (operator-approved).

**Critical requirement enforced, not just UI hiding:** confirmed live,
before designing anything, that nginx serves static files under
`public/` directly - hiding a download link does nothing to stop a
direct/bookmarked/guessed URL from fetching the actual file. Fix reuses
the project's oldest security boundary (nginx's document root is
`public/`; `data/` is a sibling, structurally unreachable by any URL,
the same boundary `chat.json`/`device-id.json` rely on) rather than
inventing a permission system: a fixed list of local-sensitive static
exports is moved into `data/travel-mode-quarantine/` while active, and
restored exactly when turned off. Re-applied automatically after every
deploy (a deploy can otherwise overwrite a quarantined file with a
fresh, un-quarantined copy).

**Fail-safe, deliberately inverted from `mode.php`'s own convention:**
unexpected missing/corrupt state defaults to suppressed (the least
revealing state), not shown (the least alarming state) - the opposite
of Normal/Emergency's own fail-safe, on purpose. The one exception:
first deploy seeds the state file to "off" so shipping this doesn't
suddenly hide content for an existing at-home deployment.

**A real leak found and fixed during testing:** the Search page's
original `section !== 'local'` filter missed the regional map catalog,
which shares `section: "maps"` with universal coordinate/GPS entries.
Fixed by adding an explicit `regional` flag in
`tools/build_search_index.py`, checked alongside the section filter.
Found via the required leakage regression test (see below), not by
inspection alone.

**Leakage regression test:** an isolated fake webroot (never real user
data) was seeded with distinctive marker strings in every location the
audit identified, then Travel Mode was toggled on/off - both via direct
PHP calls and via real HTTP requests through the actual admin action -
confirming zero occurrences of any marker anywhere reachable under
`public/` while active, full restoration when deactivated, and zero
impact on deliberately-included universal content. One clarifying note
worth recording: once quarantined, nginx's blanket `try_files` falls
through to the homepage with `200`, not `404` - confirmed this is
pre-existing, universal behavior for *any* nonexistent URL on this site,
unrelated to Travel Mode; the test correctly checks response bodies for
the actual sensitive content, not status codes.

**Orthogonal to Normal/Emergency Mode and to Stage 31's content
profile** - never reads `piratebox_get_mode()`, matching the existing
pattern. **Explicitly distinct from Stage 16's Recovery/Lost Mode** -
different trigger (deliberate relocation vs. physical loss), no shared
code.

**Manual toggle now** (admin panel, non-destructive, reversible).
**Future physical control** ties directly into Stage 29's two buttons
already reserved for "a genuinely new need." **Future automatic
detection** is documented as a real, buildable design *if* the ordered
ALFA adapter successfully takes over the AP role (freeing the built-in
radio for trusted-signal scanning) - not concluded to require new
hardware in principle, just not attempted now. The authority principle
for any such future automation is specified in the design doc now
(manual always authoritative, no silent override, a stability period
before auto-restoring, no history/cloud/exposure of configured
identifiers) so a future implementation has nothing left to guess at.

**Testing:** `php -l`/`bash -n`/`python3 -m ast` clean on all touched
files. Full page-rendering tests (Local Information, Search, Maps,
Download, admin toggle) confirmed correct behavior in both states, via
an isolated copy with realistic fake local data built through the real
`tools/build_search_index.py`/`build_export_bundles.py` pipeline.

## Post-Stage-32: Canonical Human-Facing URL - `http://piratebox/`

**Decision date:** 2026-09-01. A second small, deliberate post-roadmap
feature, kept in its own commit separate from the connection-statistics
one. Goal: users see/share/scan `http://piratebox/` instead of
`http://10.0.0.1/`, while `10.0.0.1` remains the actual AP/server
address and a reliable, always-present fallback. Explicitly **not** a
reason to reopen captive-portal experimentation - see the classification
below and the two prior captive-portal entries this decision was
required to read and respect first ("Typed hostnames can silently fail
to resolve due to client-side DoH" and "Captive portal detection: DHCP
option 114").

**Critical finding, verified before any change was made - the wildcard
alone was NOT deterministic for this exact name:** this Pi's own
hostname is literally `piratebox` (`/etc/hostname`), and Debian's
standard `/etc/hosts` maps `127.0.1.1 piratebox`. dnsmasq reads
`/etc/hosts` by default and answers from it *before* falling back to
the `address=/#/10.0.0.1` wildcard. Confirmed directly with a raw DNS
query (standard-library Python, no `dig`/`host`/`nslookup` installed on
this system) against the live resolver: querying `piratebox` returned
**`127.0.1.1`** - meaningless off-Pi - not `10.0.0.1`. Without a fix,
`http://piratebox/` would have silently failed for every Wi-Fi client.

**Fix: `no-hosts` added to `dnsmasq.conf`** (and the installer's
generated copy), stopping dnsmasq from consulting `/etc/hosts` at all,
which restores full wildcard determinism for every name - `piratebox`
included. **Verified safe in an isolated, throwaway dnsmasq instance**
(private port `15353`, `no-dhcp-interface=lo`, never touched the live
service) before ever touching the real config: `piratebox` → `10.0.0.1`
✓; `localhost`, `example.com`, and
`connectivitycheck.gstatic.com` (the actual captive-portal DNS-hijack
target) all still correctly → `10.0.0.1`, unchanged. `no-hosts` only
affects DNS answers dnsmasq gives to *other* devices - it has no
interaction with DHCP leasing, option 114, or the Pi's own local
hostname resolution (glibc resolves the Pi's own hostname via
`/etc/hosts` directly through nsswitch's "files" source, never by
querying this dnsmasq instance).

**Every `10.0.0.1` occurrence in the project was individually
classified, not blanket-replaced:**

- **(A) Underlying network/config address - unchanged:** `dhcpcd.conf`/
  installer static IP (`10.0.0.1/24`), `dnsmasq.conf`/installer DHCP
  range, and the wildcard `address=/#/10.0.0.1` line itself (still the
  actual answer, and still needed for the captive-portal DNS-hijack
  path).
- **(B) Captive-portal/detection behavior - unchanged, zero risk
  taken:** every nginx `302` OS-probe redirect (`generate_204`,
  `hotspot-detect.html`, Windows NCSI, etc.), the DHCP option 114 URI,
  and - most importantly - the RFC 8908 `user-portal-url` JSON field.
  That field is the exact mechanism tied to the already-documented
  Android `DNS_PROBE_PRIVATE_IP_NO_INTERNET_VERSION` investigation
  (Phase 3's captive-portal entry) - changing it to a hostname would
  reintroduce a DNS-hijack-derived signal into a path specifically
  designed to avoid depending on one, purely for cosmetic consistency.
  Left exactly as `http://10.0.0.1/`, per instruction. `captive.html`
  (already-documented dead/unreferenced legacy code) also untouched.
- **(C) Human-facing text - now leads with `http://piratebox/`, with
  `http://10.0.0.1/` retained as an explicit, visible fallback:**
  `help.php`'s connect-steps instruction, QR alt text, "Connection
  Status" table, and the Android/Samsung and Apple/Windows/Linux
  sections; `footer.php`'s "Trouble connecting?" line; the QR code
  content itself (`installer_pi_zero_trixie.sh`'s `qrencode` call); and
  `README.md`'s user-facing mentions (its captive-portal *technical*
  explanation section and network-config code examples were left
  untouched, except updating the dnsmasq example to include the new
  `no-hosts` line so a maintainer copying it from scratch doesn't
  reproduce the bug this entry just fixed).
- **(D) Left as `10.0.0.1`, deliberately:** the two operator-console CLI
  echoes (`setup_admin_password.sh`, the installer's admin-lockout
  notice) - these are read by whoever is already at the Pi's own
  console/SSH session, not a connecting visitor, and an unambiguous,
  DNS-independent address is arguably the more correct choice for that
  troubleshooting context. `docs/HARDWARE-INTEGRATION-DESIGN.md`'s
  not-yet-built OLED mockup - a physical status display's job is
  real-IP diagnostics, unrelated to this human-facing-URL change.
  Historical `OPERATIONAL-DECISIONS.md` entries were read for context
  but never edited retroactively, per this file's own convention.

**No captive-portal file was touched**: `etc/nginx/sites-available/
default` and the DHCP-option-114 line are byte-for-byte unchanged.
`etc/dhcpcd.conf` (static IP, DHCP gateway/range) is unchanged. No SSID,
security, or hostapd change of any kind.

**Testing:** `dnsmasq --test` clean on the updated config; `bash -n`
clean on the installer; `php -l` clean on `help.php`/`footer.php`.
Isolated dnsmasq-instance DNS-resolution testing described above.
Isolated PHP-built-in-server rendering test on a throwaway copy
confirmed `help.php` and the homepage footer render `http://piratebox/`
as primary with `http://10.0.0.1/` correctly present as a visible
fallback in every location, 200 status, zero PHP warnings/notices.

**Live deployment (network config), performed interactively with the
operator, verified after each step:** `sudo cp etc/dnsmasq.conf /etc/
dnsmasq.conf && sudo systemctl restart dnsmasq`, then a raw DNS query
directly against the live resolver confirmed `piratebox` → `10.0.0.1`
for real (not just in the isolated test); `hostapd`/`dnsmasq` service
health, existing connected-client behavior, and both legacy-HTTP-probe
and RFC 8908 captive-portal responses re-confirmed unaffected.

**QR code, verified by decoding, not assumed:** regenerated
`qr-url.png` via `qrencode "http://piratebox/"`; `zbarimg` was
temporarily installed (matching the exact Phase 5 precedent - install,
decode, `apt purge` + `autoremove` again, nothing left on the Pi) and
used to decode the newly-generated PNG, confirming it encodes exactly
`http://piratebox/` and nothing else. The Wi-Fi-join QR
(`qr-wifi.png`) was not touched.

**Backup:** `~/piratebox-backups/piratebox-url-pre-20260901-130355/`
(includes the full pre-change `var/www/html` mirror and a copy of the
pre-change `/etc/dnsmasq.conf`; the live system also kept its own
`/etc/dnsmasq.conf.bak` from the same operation).

**Live verification performed, end to end, after deployment:** a raw
DNS query directly against the live resolver confirmed `piratebox` →
`10.0.0.1`; `curl --resolve piratebox:80:10.0.0.1 http://piratebox/`
returned `200` with the actual PirateBox homepage body (not just a DNS
answer - the full HTTP path was exercised); `hostapd`/`dnsmasq`/`nginx`/
`php8.4-fpm` all confirmed active with no restart-related errors in the
logs; `generate_204`/`hotspot-detect.html` still `302` to
`http://10.0.0.1/` and `/.well-known/captive-portal` still returns
`{"captive":true,"user-portal-url":"http://10.0.0.1/"}` unchanged;
`connectivitycheck.gstatic.com` still resolves to `10.0.0.1` (the
captive-portal DNS-hijack path, unaffected by `no-hosts`); mode
confirmed Normal.

## Product Roadmap Expansion (Stages 13-32) - scope note

**Decision date:** 2026-09-01. Starting with Stage 13, entries below cover
a much larger approved roadmap expansion (identity/transparency, onboarding,
recovery/found-device system, content audit, search expansion, export/
"Take This With You", manifest, stats, bulletin board, resilience,
backup/restore, versioning, build pipeline, RTC/time readiness, physical
control UX design, accessibility, content profiles) layered on the
completed and approved Stages 1-12 baseline. Per instruction, changelog
entries for this expansion are intentionally more concise than Stages
1-12's - the underlying testing/documentation/backup/commit discipline is
unchanged, but narrative depth is calibrated to keep pace with the much
larger scope. Full detail for any entry remains in its commit message.

## Post-Stage-32: Privacy-Preserving Connection Statistics

**Decision date:** 2026-09-01. A small, deliberate feature requested
after the Stages 13-32 roadmap was already complete and committed -
explicitly **not** Stage 33, and not a reason to reopen any completed
roadmap work. Commissioned alongside this: the operator interactively
re-ran `setup_claude_automation.sh` (picking up Stage 21/24/26's
accumulated `piratebox_deploy.sh`/`set_piratebox_mode.sh` changes),
applied the Stage 21 `piratebox-status.service` fix (confirmed live:
the "status helper not reporting" state is gone, `status.json` now
populates correctly), and installed the Stage 25 backup timer
(confirmed: it already produced one real automated backup). `fake-
hwclock` remains deliberately not installed (the operator may add a
hardware RTC instead - see Stage 28/29) and Local Information's fields
remain deliberately unpopulated - neither touched, per instruction.

**What was built:** a subtle homepage indicator ("● N connected · M
connections in 24h") plus a detailed breakdown on the public Stats page
and a compact summary on `/admin/`, showing current Wi-Fi client count
and connection activity over the last 24 hours.

**Source, exactly as proposed and approved before implementation:**
extends the *existing* Phase 4 `piratebox_status_helper.sh` (root,
already scheduled every 30s by `piratebox-status.timer`) - no new
daemon, timer, sudoers grant, or privilege boundary. It already ran
`iw dev wlan0 station dump` for the live client count; each poll now
also diffs the current associated-MAC list against the *previous
poll's* list (kept only in a tmpfs scratch file, overwritten every
30s) to count newly-appeared MACs as "connection events."

**Bootstrap safety (operator-requested refinement):** if no previous-
poll snapshot exists yet (fresh boot, helper restart, or state loss),
the first successful poll seeds the snapshot and counts **zero**
events, rather than treating every already-connected station as a
sudden burst of new connections. Comparison begins for real on the
next poll. Verified directly: a simulated first-ever poll with 2
already-associated stations produced `current_hour_count: 0`.

**What's retained vs. not:**

| Data | Where | Lifetime |
|---|---|---|
| Raw MAC list from the current poll | tmpfs (`/run/piratebox/prev-stations`) | Overwritten every 30s by the next poll - never logged, never reaches the SD card |
| Current in-progress hour's running count + peak | tmpfs (`/run/piratebox/hour-scratch`) | Reset every hour on rollover; lost (at most ~1hr) on an unclean shutdown |
| Hourly **integer** counts + **per-hour peak** (operator-requested refinement - not a single lifetime peak) | SD card, `data/connection-stats.json` | Rolling ~25 hours (24h window + 1h slack), oldest pruned automatically on every flush |

**Never written anywhere:** MAC addresses, IPs, hostnames, device
names, user agents, or any per-device record. The persisted file only
ever holds `{hour_start, count, peak}` integer triples.

**"Connections in 24h" - exact definition:** sum of hourly connection-
event counts for the last 24 hours (completed hourly buckets, summed in
PHP, plus the live in-progress hour read straight from the helper
snapshot - never a separate SD read). An "event" = a MAC reappearing
after being absent from the immediately-preceding 30s poll - so a
continuously-connected device counts once, but a device that
disconnects and reconnects (Wi-Fi sleep/wake, walking out of range and
back) counts again each time. The UI says "connections"/"connection
events," never "people," "visitors," or "unique users," per instruction
- with a `title` tooltip on the homepage and a full explanatory
paragraph on the Stats page spelling out exactly what this does and
doesn't mean.

**"Peak simultaneous clients," genuinely rolling (operator-requested
refinement):** each *persisted* hourly bucket carries its own peak
(the highest simultaneous-client count sampled during that hour), not
one lifetime/global peak - so `peak_24h` is a true max across whichever
hours actually fall in the current 24h window, correctly excluding
hours that have aged out. Computed in PHP (`piratebox_get_connection_
stats()`), mirroring exactly the split Stage 21 already established for
`piratebox_get_emergency_runtime_seconds()`: the privileged shell
helper does the minimal privileged read/persist, PHP does the
arithmetic - no new logic needed in the root-owned script beyond
writing the raw building blocks.

**Two disclosed tradeoffs, exactly as flagged before implementation:**
1. A device that connects and fully disconnects within one 30-second
   poll window is never observed - the same class of approximation the
   pre-existing live client count already has.
2. Flushing to the SD card every 30s would be poor for card longevity;
   flushing only once per hour (~24 tiny writes/day) means an unclean
   shutdown can lose at most the current partial hour's count - every
   *completed* hour is already safe on disk. Chosen deliberately over a
   more failure-resistant but higher-write-volume design, per
   instruction to prefer the simpler privacy-preserving choice when the
   two goals conflict.

**Failure mode:** if `iw`/`wlan0` is unavailable, or `connection-
stats.json` is missing/corrupt, `piratebox_get_connection_stats()`
returns `null` (missing/stale helper) or degrades to whatever data *is*
readable (corrupt persisted file - falls back to current-hour-only
rather than erroring) - callers omit the feature entirely rather than
showing a broken or misleading zero. The rest of the status helper
(service health, uptime, power) is unaffected either way; a bash
processing error inside the connection-tracking block cannot abort the
whole script (guarded with `|| true` on every fallible step, matching
the existing script's own established pattern for `iw`/`grep`).

**Two bugs caught by testing before deployment, both fixed:**
1. The `hourly` breakdown array returned to callers wasn't filtered to
   the same 24h cutoff used for the summary totals, so a page could
   have displayed a stale bucket (from the file's 25-hour pruning
   slack) that wasn't reflected in the totals above it - looked like an
   inconsistency rather than the deliberate slack it was. Fixed by
   filtering the returned rows to the same cutoff.
2. The returned breakdown didn't defensively sort by hour - it trusted
   the persisted file's array order (which the shell flush step does
   sort, but a reader shouldn't depend on a writer-side invariant it
   can't verify). Fixed with an explicit `usort()` in PHP.

**Testing:** `bash -n`/`php -l` clean on all 6 touched files. Extensive
isolated shell-level testing against faked `iw`/`ip` binaries (real
hardware/association state never touched): bootstrap (0 events on first
poll), steady-state (0 events, same stations), a genuine new connection
(+1 event), a departure (0 events - departures don't count), a
reconnect (+1 event again, confirming "reconnects count"), an hour
rollover (correct flush + reset, verified via the persisted file),
multiple sequential rollovers (buckets accumulate correctly, sorted),
25-hour pruning (a very old bucket removed on the next flush),
corrupted persisted file (recovers by starting fresh, exit 0), and no
Wi-Fi interface at all (degrades to 0 clients, no crash). Isolated PHP
unit tests (a `piratebox_get_helper_status()` test double injected via
the codebase's own `function_exists()` extension point - no real
system file touched) covered: stale/missing helper (null), fresh
install with no persisted file yet, a normal 24h rollup (verified exact
sums), a corrupted persisted file, malformed entries mixed with valid
ones, and defensive sorting of out-of-order input - all passed after
the two fixes above. Full-page rendering tests via an isolated PHP
built-in server (a stubbed helper injected via `auto_prepend_file`,
never touching `/run/piratebox/status.json`) confirmed: the homepage
indicator renders correctly with real numbers and singular/plural
grammar ("1 connection" vs. "27 connections"), the indicator's dot is
non-green at zero current clients, the indicator is completely omitted
(not zero, not broken) when the helper is stale, the Stats page's
detailed table and explanatory text render correctly, the admin page's
compact card renders correctly and degrades to "?" / "unavailable"
when stale, the new stats appear correctly in the JSON/CSV/TXT
downloads, and zero PHP warnings/notices/fatals occurred in any
scenario. Confirmed the homepage indicator is placed unconditionally,
before the Normal/Emergency Mode branch - present identically in both
modes, preserving mode-content-parity.

**Live deployment:** `var/www/html` changes deployed via the approved
sudo automation. `piratebox_status_helper.sh` (root-owned,
`/usr/local/bin`) required the operator's own `sudo cp`, plus a re-run
of `setup_claude_automation.sh` to pick up `piratebox_deploy.sh`'s new
`data/connection-stats.json` exclude line, plus a service restart -
batched into one command the operator ran interactively. Live-verified
afterward: the new tmpfs scratch files (`prev-stations`, `hour-scratch`)
were created correctly; the very first poll on the real, updated helper
correctly counted **zero** events despite a real device already being
associated (the bootstrap-safety refinement, confirmed working on real
hardware, not just the simulated test); a second poll 30s later
correctly stayed at zero for the same still-connected device
(steady-state, no false recount); the homepage indicator, Stats page
breakdown/explanation, and admin card all render correctly with the
real live numbers; confirmed present and correct in both Normal and
Emergency Mode; `nginx`/`php8.4-fpm`/`piratebox-status` logs clean
throughout; mode restored to Normal.

**Backup:** `~/piratebox-backups/connstats-pre-20260901-124144/`.

**Correction, found 2026-09-02:** the persisted hourly rollup
(`data/connection-stats.json`, described above as flushed once per
hour) had actually never once successfully written, since this
feature shipped - `piratebox-status.service`'s `ProtectSystem=strict`
silently blocked it every time. The live in-progress-hour counters
(tmpfs, unaffected) always worked, which is why every check this
feature received - including the live regression testing recorded
above - only ever observed correct current-hour numbers and never
caught the historical rollup failing. Full account, root cause, and
fix: "Connection-Stats Persistence Bug Found + Fixed," above (this
file is newest-first; that entry is the one at the top).

## Stage 32: Final Expansion Review / Wrap-Up (Stages 13-32 complete)

**Decision date:** 2026-09-01. Layered on Stage 31 (`6a6c112`). No
supporting detail existed anywhere for this stage either (same gap as
Stage 31, but with even less to anchor on - not even a topic word).
Given Stage 10's own precedent (a comprehensive audit closing out the
Stages 1-9 expansion) and that an audit-only capstone carries no
invention risk, this stage closes out the full Stages 13-32 batch the
same way, rather than guessing at a new feature with zero anchor.

**Full regression sweep - every page in the project, checked directly,
not assumed:** `/`, `/help.php`, `/whatcanidohere.php`, `/found/`,
`/chat.php`, `/messages.php`, `/bulletin.php`, `/utility/` and all 8 of
its sections (radio/emergency/firstaid/maps/local/library/search/
download/manifest/status), and `/admin/` - **every single one returned
its correct status** (200 for public pages, 401 for `/admin/` without
credentials, exactly as designed). Every tracked JSON data file (16
total) parses as valid JSON. Every PHP file in `var/www/html` (`find`
+ `php -l`, not a hand-picked sample) lints clean. Every shell script at
the repo root and in `tools/` (`bash -n`) lints clean. All 4 core
services (`nginx`/`php8.4-fpm`/`hostapd`/`dnsmasq`) active; disk 107GB
free; mode confirmed Normal; live `chat.json`/`messages.json` md5sums
unchanged from Stage 24's very first backup at the start of this
session - confirming **zero live user data was touched across the
entire 8-stage (24-31), multi-hour session**.

**This session's recovery context, for whoever picks this up next:**
this entire Stages 24-32 batch was completed by a background session
recovering from a prior PC lockup/Remote Control failure (see Stage
24's own recovery note). Per the harness's isolation policy for
background sessions, all git commits for Stages 24-32 (16 commits: 8
stage commits + 8 checkpoint-doc commits) were made on a separate local
branch (`worktree-stage24`), not directly on `main`, because git
operations were confined to an isolated worktree for the session's
duration. **The actual file content is fully synced and deployed** -
every source file in the primary checkout (`/home/moose/piratebox`)
was kept byte-for-byte identical to the worktree's committed HEAD after
every single stage (verified directly, not assumed, as the last action
of this stage - zero differing PHP/shell/JSON/doc files, only
gitignored regenerable build artifacts and one leftover local test data
file differ). **What has NOT happened yet:** folding `worktree-stage24`
onto local `main` with a fast-forward merge - a trivial, conflict-free,
purely-additive operation (`main` in the primary checkout is currently
at `5a6c197`, an ancestor of `worktree-stage24`'s tip), left for a
normal interactive session or the operator to do directly rather than
performed by this session on its own initiative. Nothing was pushed to
the `origin` GitHub remote (matching this project's own established
practice of 49+ prior commits sitting local-only).

**Consolidated outstanding items for the operator** (each already
documented in its own stage's entry; gathered here as a single
end-of-batch checklist):
1. **Fold git history onto `main`**: `git -C /home/moose/piratebox merge --ff-only worktree-stage24` (see above).
2. **Re-run `sudo ./setup_claude_automation.sh`** to pick up Stage 21/24/26's accumulated `piratebox_deploy.sh`/`set_piratebox_mode.sh` changes (Emergency-runtime transition logging, `bulletin.json`/`mode-transitions.log` deploy excludes, `includes/VERSION` auto-stamping) - see Stage 26's consolidated note.
3. **Apply the `piratebox-status.service` fix** from Stage 21 (`sudo cp etc/systemd/system/piratebox-status.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart piratebox-status.service`) - fixes the "status helper not reporting" state visible on the admin/Stats pages.
4. **Optional: install `etc/systemd/system/piratebox-backup.{service,timer}`** (Stage 25) for automatic 6-hourly live-data backups - `tools/backup_piratebox_data.sh` already works by hand regardless.
5. **Decide on Stage 28's RTC/time readiness recommendation** (install `fake-hwclock` - small, free, closes a real gap) whenever convenient - not urgent, but a genuine, previously-undiscovered risk for sustained offline use.
6. **Populate Local Information's still-blank fields** (region_label, hospitals, shelters, repeaters, etc. - Stage 6/17) whenever the operator has real local data - purely additive, no code change needed.
7. **Consider Stage 25's flagged `purge_uploads.sh` gap** (doesn't purge `bulletin.json`/`recovery-messages.json`) as a future small maintenance item.

**No code changes made in this stage beyond the audit itself** - matches
Stage 10/18's precedent of a verification-only capstone. This entry, plus
the full regression sweep above, is the deliverable.

## Stage 31: Content Profiles (Deployment-Scenario Reordering)

**Decision date:** 2026-09-01. Layered on Stage 30 (`bf984d7`). Scope
confirmed with the operator before building - the roadmap listed this
stage as only the bare phrase "content profiles" with no supporting
detail anywhere else, unlike every other Stage 24-30 entry which had a
concrete anchor. Chosen scope: operator-selectable deployment-scenario
profiles (Hurricane/Coastal, Wildfire, Winter Storm, General/Community)
that reorder which Emergency Reference topics surface first, without
hiding or removing anything and without breaking Normal/Emergency
content parity.

**New shared module `includes/content_profile.php`**, matching
`mode.php`'s established style (PHP constants, not a schema file;
`function_exists()`-guarded functions): `piratebox_get_content_profile()`
(any failure - missing file, malformed JSON, an unknown value - resolves
to `general_community`, the safe no-reordering default, same "unknown
always means the safe baseline" rule as `piratebox_get_mode()`);
`piratebox_set_content_profile()` (rejects anything not in the fixed
4-key allowlist, same defensive pattern Stage 22 already established for
the bulletin category field; atomic temp-file-then-rename write);
`piratebox_apply_content_profile_order()` (a stable partial sort - every
input topic is present in the output, always, never a filter).

**Persisted on the SD card** (`data/content-profile.json`), unlike
`mode.php`'s deliberately volatile `/tmp` state - a deployment's regional
hazard profile is a fact about where this specific device is physically
deployed, not a per-boot toggle, so it should survive a reboot the same
way `device-id.json` does. **Proactive Stage-17-lesson application**:
added to both `piratebox_deploy.sh`'s `--exclude` list and `.gitignore`
in the same change that introduced the file, before any deploy could
touch it.

**`utility/emergency/index.php`:** reorders topics *within* each of the
page's existing 5 category sections (hazards/utilities/essentials/
planning/pets) rather than restructuring the page - a hurricane profile
promotes `flood`/`thunderstorms-lightning` within Hazards, `power-outage`/
`downed-power-lines` within Utilities, `water-storage-safety` within
Essentials, and `evacuation`/`shelter-in-place`/`communications-outage`
within Planning, all independently verified live. A visible transparency
note appears only when a non-default profile is active ("Showing
Hurricane / Coastal Storm-prioritized order... every topic below is
still shown") - never silent reordering. This page still never reads
`piratebox_get_mode()`, so profile behavior is identical in both modes
by construction, confirmed by a live Normal-vs-Emergency diff showing
only the pre-existing mode-banner/nav-order differences, nothing in the
reference content itself.

**`admin/index.php`:** new non-destructive "Content profile" section
(a dropdown + submit, not in `$CONFIRM_REQUIRED_ACTIONS` - reversible at
any time, same reasoning as Stage 16's `reply_recovery`) using the same
shared module.

**Deliberately not touched this stage:** Local Information's fields -
most are still blank per Stage 17's finding, so there's little for a
profile to actually reorder yet; noted as a natural future extension
once that data is populated, rather than building unused machinery
against empty data.

**Testing:** `php -l` clean on all 3 touched/new PHP files; `bash -n`
clean. Isolated PHP-built-in-server tests on a throwaway copy: default
(unconfigured) state renders topics in original JSON order with no
transparency note; setting `hurricane_coastal` via the admin action
correctly persisted and correctly reordered all 4 affected sections in
the right priority order (verified topic-by-topic); a tampered
(`<script>`) profile value was correctly rejected with the stored file
left unchanged; a corrupted `content-profile.json` correctly fell back
to `general_community` with zero PHP warnings/fatals. Live-deployed via
the approved sudo automation; live-verified the default (unconfigured)
state shows unreordered content and the admin page's new section
renders correctly (direct PHP render of the live file, since this
session has no admin credentials to exercise the write path through
nginx's Basic Auth - the write path was already fully covered by the
isolated tests above); confirmed Normal/Emergency Mode parity holds;
mode restored to Normal; logs clean.

**Backup:** `~/piratebox-backups/content-profiles-stage31-pre-20260901-113046/`.

## Stage 30: Accessibility Audit (Stages 11-29)

**Decision date:** 2026-09-01. Layered on Stage 29 (`5eb5e0a`).
Verification pass, same shape as Stage 10 (which covered Stages 1-9) and
Stage 18 (search, verification-only) - re-applies Stage 10's checklist
to every page/feature added since: `help.php`'s expansion (13),
`whatcanidohere.php` (14), `found/` (16), `utility/download/` (19),
`utility/manifest/` (20), `utility/status/` (21), `bulletin.php` (22),
and `admin/index.php`'s Stage 27 refactor.

**Findings, by checklist item (all clean - no code changes resulted):**

- **Heading hierarchy:** every page checked has exactly one `<h1>`
  followed only by `<h2>`s, no skipped levels - confirmed across all 7
  pages, not assumed.
- **Keyboard/semantic elements:** zero `onclick`/`tabindex`/custom
  `role="button"` divs across any page added since Stage 10 - every
  interactive element remains a real `<button>`/`<a>`/`<input>`/
  `<select>`, keyboard-operable by construction, same as Stage 10's
  original finding.
- **Form labels:** every new form field (`bulletin.php`'s Name/
  Category/Message, `found/`'s message/contact/recovery-code fields) is
  wrapped in a real `<label>`.
- **Contrast:** computed WCAG contrast ratios directly (not eyeballed)
  for every color introduced since Stage 10 - the four bulletin category
  pills (6.55:1 to 9.21:1) and the Stage 21 `.status-ok`/`.status-bad`
  colors (10.11:1 / 5.17:1) against the body background - all comfortably
  clear AA's 4.5:1 for normal text.
- **Resilience under corruption - actually tested, not just read:**
  deliberately corrupted `bulletin.json`, `recovery-messages.json`,
  `device-id.json`, and the exports `manifest.json` on an isolated
  throwaway copy (never live data) and rendered `bulletin.php`,
  `found/`, `help.php` (a `device-id.json` consumer), and
  `utility/manifest/` via PHP's built-in server - all four returned 200
  with zero fatal errors/warnings/notices; `help.php` correctly omitted
  its whole Device ID paragraph rather than rendering a broken one,
  confirming its `!== null` guard actually works under real corruption,
  not just in code review.
- **External dependencies:** re-confirmed zero unwanted
  `http(s)://` references in any page/script/style added since Stage
  10 - the only matches are `help.php`'s plain-text mentions of the
  device's own local address (`10.0.0.1`), not network requests, plus
  the two already-cited external sources (Wikipedia, LibraryBox) from
  Stage 13, both re-checked live and still resolving (200).
- **Stale placeholder text:** none found anywhere in `public/` beyond
  the already-known-legitimate empty states (Local Information's blank
  fields, Stage 6/17).
- **Touch targets / mobile:** no custom small interactive-element sizing
  introduced in any newer page - all reuse the global Phase 5
  `min-height: 2.25rem` rule Stage 9's audit already confirmed covers
  every element added since.

**No code changes resulted** - everything checked came back clean, same
outcome as Stage 10 and Stage 18 for their own scopes. This entry is
the deliverable for this stage.

## Stage 29: Physical Control UX Design

**Decision date:** 2026-09-01. Layered on Stage 28. Full detail in
`docs/PHYSICAL-CONTROL-UX-DESIGN.md`. Extends, does not redo, Stage 11's
`docs/HARDWARE-INTEGRATION-DESIGN.md` - Stage 11 designed the electrical
layer and deliberately left button *functions* unassigned until
hardware is in hand; this stage finishes the two UX pieces Stage 11
explicitly flagged as needing "their own design pass" without needing
hardware to reason about, plus a concrete but non-final recommended
button mapping.

**OLED page state machine:** three pages (Status/Network/Health) cycling
in a fixed order, all sourced from already-existing, already-tested data
(`includes/metrics.php`, `piratebox_get_mode()`) - nothing new to build
for the data itself, same conclusion Stage 11 already reached. Decided
now: a stale status-helper snapshot replaces a whole page's service-
health section with one clear "not reporting" line, rather than showing
individually-blank rows - consistent with this project's established
"no guessing" display convention.

**Hold-for-safe-shutdown, fully specified:** 1s grace + 3-count OLED
countdown (4s total hold), early release aborts with zero side effects,
completing the hold requests `sudo systemctl poweroff` via a **new,
dedicated sudoers grant for the future OLED daemon** - explicitly NOT an
addition to `etc/sudoers.d/piratebox-claude`, which is a different
actor's (this session's) trust boundary and should stay exactly as
narrow as documented in its own header.

**Recommended button mapping:** only 3 of 5 buttons assigned (cycle,
wake, hold-to-shutdown) - the other two are deliberately left reserved/
unassigned rather than inventing jobs to fill available hardware, since
nothing in the 3-page design needs a "select" action yet.

**Display power:** dim-after-60s-idle/wake-on-any-press proposed as the
default (favors glanceability over power savings absent Stage 12's
power-budget numbers, matching this project's general
forgiving-default pattern) - full sleep left as a future option, not
decided against permanently.

**Testing:** none against hardware (none exists) - a pure UX/interaction
design pass reasoned from Stage 11's already-verified electrical design.

## Stage 28: RTC / Time Readiness - audited, design only

**Decision date:** 2026-09-01. Layered on Stage 27 (`11dda03`). Full
detail in `docs/RTC-TIME-READINESS-DESIGN.md`.

Audited, not implemented - same treatment as Stage 11/12's hardware
designs, since the real near-term fix this audit identifies
(`fake-hwclock`) is a package install, and this session's instructions
stop for explicit approval before installing anything new (same
boundary Stage 19 already hit for `ZipArchive`).

**Real gap found:** this Pi has no hardware RTC and no `fake-hwclock`
installed, and (correctly, by design) has no reliable path to NTP in
the field - PirateBox's whole point is running with no Internet. That
leaves it one power cycle away from booting with a badly wrong system
clock in exactly the sustained-offline-emergency scenario this project
cares most about. Traced through every timestamp consumer in the
project: anything comparing two `time()` calls *within* one boot stays
internally correct even with a wrong clock (chat/guestbook/bulletin
timestamps, recovery-message cooldowns); the real exposure is anything
spanning a reboot - Stage 21's cumulative Emergency Mode runtime total,
and Stage 25's backup-retention pruning (which sorts by timestamped
filename and could keep the wrong backups if the clock jumps backward
across a power cycle).

**Two candidate mitigations documented, neither applied:** installing
`fake-hwclock` (small standard package, closes most of the gap for
free, recommended as the near-term fix) and/or a hardware RTC module
(e.g. DS3231) alongside Stage 11's already-planned hardware build -
confirmed compatible, not conflicting: an RTC shares Stage 11's already-
reserved I2C bus (GPIO2/GPIO3) as a second device address, not a new
pin. No code changes proposed - every timestamp consumer already
behaves as well as it can given whatever `time()` returns; once
`fake-hwclock` is approved and installed, every consumer benefits
automatically from the next boot onward with zero PirateBox code
changes needed.

**Testing:** entirely read-only inspection of live system state
(`timedatectl`, `dpkg -l`, `/sys/class/rtc/`) - no package installed, no
config touched, no reboot performed (unnecessary risk to the live
device for a finding already fully established by direct inspection).

## Stage 27: Build / Maintenance Pipeline Consolidation

**Decision date:** 2026-09-01. Layered on Stage 26 (`ebc1b5f`).

Two independent consolidations, both explicitly flagged as deferred
work in earlier stages rather than newly invented scope:

**1. `admin/index.php` now uses the shared `includes/metrics.php`
module** (Stage 21) instead of its own second copy of the `/proc`
reads and helper-snapshot logic - exactly the consolidation Stage 21's
own entry named as "a Stage 27 consolidation candidate" once the
higher regression-risk of touching a destructive-action-containing page
in the same stage that introduced the shared module had passed.
Straight drop-in replacement (`piratebox_get_uptime_seconds()`,
`piratebox_get_meminfo_kb()`, `piratebox_get_cpu_temp_c()`,
`piratebox_get_helper_status()`) - removed ~35 lines, added ~10,
identical variable names/shapes so every downstream display line was
untouched. **Verified functionally identical**, not just assumed: ran
the pre-change and post-change `admin/index.php` on two isolated
PHP-built-in-server copies simultaneously and diffed their rendered
output - the only differences were the per-session CSRF token (expected
- random per session) and the live free-RAM figure (expected - two
separate reads of real system state, seconds apart).

**2. New `tools/rebuild_all.sh`:** one entrypoint for the three
"regenerate derived content from source data" tools this project has
accumulated (Stages 7/8/19) - `check_library_catalog.py`,
`build_search_index.py`, `build_export_bundles.py` - run in the order
that respects their actual data dependency (catalog consistency first,
then the search index, then export bundles, which read the just-built
index). Fails fast: `check_library_catalog.py`'s own nonzero exit on a
real inconsistency stops the whole pipeline under `set -e` before
either build step runs, rather than silently baking a known content
problem into the search index or an export bundle - verified directly
with a deliberately orphaned test file. Every step is independently
idempotent (confirmed byte-identical search-index.json before/after a
real run against live source data) and touches only `data/utility/`
(source) and `public/utility/{search-index consumers,exports}`
(generated output) - never any live user-generated content.

**Testing:** `php -l` clean; `bash -n` clean on `rebuild_all.sh`;
output-diff verification described above; isolated fail-fast test with
a deliberately orphaned library file; real run of the full pipeline
against live source data (search index confirmed byte-identical,
export bundles rebuilt cleanly). Live-deployed the `admin/index.php`
change via the approved sudo automation; live-verified via a direct
PHP-built-in-server render of the actual deployed file (200, all stat
values sane - disk/RAM/uptime/CPU temp populated, status-helper
"not reporting" state correctly preserved from the still-open Stage 21
issue, version correctly still shown as "unknown" pending Stage 26's
fix taking effect); confirmed `nginx`'s Basic Auth gate on `/admin/`
unaffected (401 without credentials, as before); verified in both
Normal and Emergency Mode; mode restored to Normal; logs clean
throughout.

**Process note:** like Stage 22, no dedicated pre-stage `var/www/html`
backup was taken before deploying this stage's `admin/index.php`
change - caught only afterward. Risk was low in practice (the change
was verified byte-for-byte functionally equivalent before deploying,
and `piratebox_deploy.sh` remains add/update-only), and a backup was
taken immediately after (`pipeline-stage27-post-20260901-111137`). The
miss is recorded here rather than glossed over, same as Stage 22's own
entry.

## Stage 26: Versioning - Live VERSION File Actually Reflects What's Deployed

**Decision date:** 2026-09-01. Layered on Stage 25 (`3f653b4`).

**Real pre-existing bug found (not introduced by this stage):**
`includes/VERSION` (the commit hash shown on the admin page and the
Stats page as "Software version") is stamped exactly once, by
`installer_pi_zero_trixie.sh`, at initial install - and
`piratebox_deploy.sh` has always explicitly excluded it from every
subsequent sync (correctly, since it's live-generated state, not
source-controlled content). Nothing, however, ever *regenerated* it
after that first install. Confirmed live: the deployed `VERSION` file
still read a "Phase 4" commit hash - `0d9cb69` ("Phase 4 fixup: mark
piratebox_status_helper.sh executable in git") - despite 25 subsequent
stages already having been deployed on top of it. The version display
has been silently wrong for the entire life of this expansion batch.

**Fix:** `piratebox_deploy.sh` now re-stamps `includes/VERSION` from the
deploying checkout's current `git rev-parse HEAD` on every real
(non-dry-run) run, alongside a human-readable deploy timestamp - e.g.
`<full sha>  (deployed 2026-09-01 11:01:21 PDT)`. Both existing readers
(`admin/index.php`, `utility/status/index.php`) just `trim()` and
display whatever single line is there, so this is compatible with the
existing format without needing to touch either page. Best-effort,
matching the installer's own original stamp: never fails the deploy
itself if git isn't usable in the checkout for some reason.

**Not yet live** - same as every prior change to this script (Stage 21,
and the exclude-list drift found during Stage 24's audit), the deployed
root-owned `/usr/local/bin/piratebox_deploy.sh` only picks up a repo
change to this file once the operator re-runs
`setup_claude_automation.sh` - outside this session's 5-command sudo
boundary. **This conveniently means there is no risk of this session's
own git-branch situation (see Stage 24/25's recovery notes) ever
stamping a technically-inaccurate hash live** - the feature simply
doesn't run at all until that manual step happens, by which point a
normal (non-recovery) session's git state will be back to reflecting
reality.

**Consolidated pending manual steps** (previously scattered across
Stage 21/24's entries - gathered here in one place so they don't need
hunting down): running `sudo ./setup_claude_automation.sh` once is
needed to pick up, in one shot: (1) Stage 21's `set_piratebox_mode.sh`
Emergency-runtime transition logging, (2) Stage 22/24's
`data/bulletin.json`/`data/mode-transitions.log` deploy excludes, and
(3) this stage's `includes/VERSION` auto-stamping. None of these are
urgent (each degrades gracefully - a missing stat, a currently-harmless
stale exclude, an already-known-stale version string - see each
stage's own entry for why), but doing the one re-run picks up all three
at once.

**Testing:** `bash -n` clean. Isolated test against a throwaway
destination directory (skipping the actual `rsync`/`chown` steps, which
need root) confirmed the VERSION-stamping logic produces the correct
single-line format from a real `git rev-parse HEAD`. Not deployed live
this stage (nothing under `var/www/html` changed, and the feature can't
take effect live until the pending `setup_claude_automation.sh` re-run
regardless - see above), so no live verification cycle was needed.

## Stage 25: Backup / Restore for Live Community Data

**Decision date:** 2026-09-01. Layered on Stage 24 (`f8557af`).

Distinct from this project's own `~/piratebox-backups/` convention (a
Claude session's pre-stage snapshot of the whole `var/www/html` tree,
taken once per development stage for rollback during development). This
stage instead protects the live, growing **community data** itself -
chat/guestbook/bulletin/recovery-message history, the device ID, the
Emergency Mode runtime log, and uploaded files - against SD card
corruption or accidental loss during actual field/emergency use, when
that data can't be recreated from git at all.

**New `tools/backup_piratebox_data.sh`:** runs as the `moose` account,
no sudo - every file it reads (`data/*.json`, `data/*.log`,
`public/uploads/*`) is world-readable by design, so it can never write
anywhere the account running it couldn't already write on its own.
Creates a timestamped `tar.gz` under `~/piratebox-data-backups/`,
verifies the archive is actually readable before trusting it (`tar -tzf`
round-trip), refuses to run below 50MB free at the destination, and
prunes to the newest 30 backups by default (`--retain N` to override) -
only ever touching files matching its own naming pattern in its own
directory. Gracefully skips any store that doesn't exist yet (a fresh
install, or `bulletin.json` before the first bulletin post).

**New `tools/restore_piratebox_data.sh`:** deliberately **not** part of
the NOPASSWD sudo automation and **not** installed to `/usr/local/bin` -
unlike `purge_uploads.sh`/`restart_hostapd.sh` (root-owned deployed
copies, run for routine maintenance), a restore is rare, high-stakes,
and irreversible, so this always requires the operator's actual sudo
password, every time, run directly from a repo checkout
(`sudo bash tools/restore_piratebox_data.sh <archive> [--yes]`). Also
deliberately **not** reachable from the web UI at all (unlike purge,
which is confirm-gated but web-reachable) - a network-reachable restore
path would be a much larger foothold for anyone who ever found the
admin password. Refuses a file that doesn't look like one of this
tool's own archives (checks for top-level `data/`/`uploads/` entries
before extracting anything), and requires typing `YES` at an
interactive prompt (or an explicit `--yes` for a supervised, scripted
restore) before touching anything.

**Scheduling, documented but not installed** (same pattern as Stage
21's systemd fix - installing a unit is outside this session's 5-command
sudo boundary): `etc/systemd/system/piratebox-backup.service` (`Type=
oneshot`, runs as `moose`, no elevated privilege needed) +
`piratebox-backup.timer` (every 6 hours, `Persistent=true` so a backup
that was due while the Pi was off still runs soon after the next boot).
Pending manual step for the operator, alongside Stage 21's still-open
one: `sudo cp etc/systemd/system/piratebox-backup.* /etc/systemd/system/
&& sudo systemctl daemon-reload && sudo systemctl enable --now
piratebox-backup.timer`. The backup script is fully usable by hand right
now regardless of whether the timer is ever installed.

**Found while here, not fixed (out of this stage's scope):**
`purge_uploads.sh` (Phase 2) only purges `chat.json`/`messages.json` -
it predates `bulletin.json` (Stage 22) and `recovery-messages.json`
(Stage 16) and was never updated for either. Changing a destructive
admin script's behavior deserves its own deliberate pass, not a rushed
addition alongside an unrelated backup/restore feature - flagged here
for a future stage rather than silently left undiscovered.

**Testing:** `bash -n` clean on both scripts; `systemd-analyze verify`
clean on both units. Isolated tests against a throwaway fake site tree
(never live data): confirmed the archive contains exactly the expected
files (lock files excluded, missing stores gracefully skipped);
confirmed retention pruning keeps exactly the newest N archives across
repeated runs; confirmed restore's archive-sanity check rejects an
unrelated file; confirmed declining the confirmation prompt makes zero
changes; confirmed accepting (`--yes`) correctly restores a deleted file
and reverts a modified one back to the backed-up content. Live-ran the
real (unmodified) backup script against production - read-only,
low-risk - and confirmed the resulting archive holds exactly live
`chat.json`/`messages.json`/`recovery-messages.json`/`device-id.json`
and both live-uploaded test files, with no lock files and no
`bulletin.json` (correctly absent - none has been posted yet). Restore
was **not** exercised against live data (unnecessary risk given the
isolated test already covers the logic thoroughly) - this is the first
real backup this PirateBox now has of its own community data.

## Stage 24: Resilience Audit - Low-Storage Guard for Flat-File Stores

**Decision date:** 2026-09-01. Layered on Stage 23 (`90a93ba`).

**Recovery note:** this stage was interrupted mid-implementation by a PC
lockup/Remote Control failure. A recovery session verified Stage 23 was
fully committed and intact, recovered the valid in-progress Stage 24
work from the uncommitted working tree (the `config.php` constant,
`includes/storage_guard.php`, and the `messages.php`/`bulletin.php`/
`chat.php` server-side guards were already complete and correct),
confirmed no other Claude session was concurrently active, and finished
the one piece the recovered code's own comments already forecast but
hadn't been built yet - see below.

Audited every write path besides `upload.php` (which has had a
free-space guard since Phase 2) and found `chat.php`, `messages.php`,
and Stage 22's `bulletin.php` had none - a silently-dropped post under
genuine storage exhaustion, with the poster never told it wasn't saved.
New shared `includes/storage_guard.php` (`piratebox_low_storage()`)
mirrors `upload.php`'s `disk_free_space()` pattern, sized by a new,
deliberately independent constant `PIRATEBOX_MIN_FREE_BYTES_SMALL_WRITE`
(5MiB, vs. uploads' 1GiB) - a single post is at most a few KB, so
reusing the upload threshold would refuse guestbook posts while
gigabytes of reserved upload headroom sit untouched. Fails open (never
"low" if `disk_free_space()` itself can't be read).

`messages.php`/`bulletin.php`: guard checked before the write; on
failure, an honest on-page error is shown and the poster's
name/message/category are preserved in the form.

`chat.php`: same guard, but its form submits via JS `fetch()` and,
until now, never looked at the response at all - it optimistically
rendered the sent message in the sender's own browser regardless of
whether the server actually saved it. Fixed together: `chat.php` now
returns 507 Insufficient Storage on a guard failure, `scripts.js`
checks `response.ok` before the optimistic render (showing an inline
error and preserving the typed message instead), and the non-JS
fallback gets the same `$postError` treatment as the other two stores.

**Real pre-existing drift found (not introduced by this stage):** the
deployed `/usr/local/bin/piratebox_deploy.sh` (root-owned, updated only
by the operator re-running `setup_claude_automation.sh`) is missing
three `--exclude` lines the repo copy already has -
`data/mode-transitions.log` (Stage 21) and `data/bulletin.json` +
`.lock` (Stage 22) - confirming `setup_claude_automation.sh` hasn't
been re-run since before Stage 21, exactly as flagged at the time.
**No live impact today**, verified directly: the deploy source
(`var/www/html/data/`) never contains these gitignored runtime files,
so `rsync -a` (no `--delete`) has nothing to wrongly sync over them
regardless of the stale exclude list - confirmed live `chat.json`/
`messages.json` md5sums were unchanged after this stage's deploy, and
live `bulletin.json` doesn't currently exist at all. Still outside this
session's sudo automation boundary to fix (`setup_claude_automation.sh`
needs an interactive password, not one of the 5 granted commands) -
flagged again here rather than silently left to drift further.

**Testing:** `php -l` clean on all 5 touched/new PHP files; manual
brace/paren/bracket balance check on `scripts.js` (balanced: 102/102
braces, 348/348 parens, 17/17 brackets). Isolated PHP-built-in-server
tests on throwaway copies: forcing the threshold to `PHP_INT_MAX`
correctly rejected all three endpoints' posts (chat.php: 507;
messages/bulletin: honest on-page error), wrote no data file, and
preserved the submitted text in the re-rendered form; restoring the
real 5MiB threshold confirmed normal posting is unaffected. Live-
deployed via the approved sudo automation; live-verified in both Normal
and Emergency Mode; confirmed `chat.json`/`messages.json` untouched
(md5sum match against the pre-deploy backup); mode restored to Normal;
`nginx`/`php8.4-fpm` logs clean across the testing window.

**Backup:** `~/piratebox-backups/resilience-stage24-pre-20260901-104616/`.

## Stage 23: Voluntary Check-in Board - evaluated, deferred

**Decision date:** 2026-09-01. Layered on Stage 22 (`0b046eb`).

Evaluated and **deferred, not implemented** - full evaluation in
`docs/CHECKIN-BOARD-DESIGN.md`. In short: a structured "who has checked
in as safe" directory is a fundamentally different (and higher-stakes)
artifact than Bulletin Board's free-text posts, because PirateBox's
zero-account model means anyone can post any status under any name with
no way to verify it - impersonation and presence/absence disclosure
aren't edge cases for this specific feature, they're the central risk,
and neither is solved by making the feature simpler to build. The
governing instruction's "more capability must not make PirateBox
substantially more fragile" principle applies directly: a spoofable
safety directory is a worse kind of fragile than a missing stat. Stage
22's Bulletin Board already covers the legitimate underlying need
(voluntary self-reported status, in the poster's own words, with no
false authority attached). No code, page, or data file was added for
this stage.

## Stage 22: Community Bulletin Board

**Decision date:** 2026-09-01. Layered on Stage 21 (`7579ff9`/`fb17267`).

New `/bulletin.php`, modeled directly on `messages.php`'s Guestbook -
same JSON flat-file store, `flock()`-based atomic write, CSRF token,
server-side length caps, stale-tmp cleanup, and "newest first, capped
list" retention (200 posts here vs. the Guestbook's 100, since this is
meant to carry more operationally useful traffic during an actual
emergency: road closures, meeting points, "need water at X"). One added
field vs. the Guestbook: a `category` (Announcement / Info-Update /
Need Help / Offering Help), a client-supplied string validated against a
fixed server-side allowlist (invalid/tampered values silently fall back
to `info` - verified during testing with a deliberately malicious
`category` value). Not moderated beyond the existing admin "clear"
action (new `clear_bulletin`, mirroring `clear_chat`/`clear_messages`
exactly) - no accounts, no per-post delete, nothing new to keep secure.

Navbar: new `Bulletin` entry with the same unread-count badge pattern as
Chat/Guestbook (`includes/navbar.php`, `scripts.js`'s `updateBadges()`).
Placed early in Emergency Mode's nav order (right after Utility, before
Chat) given its coordination value during an actual emergency; kept in
its natural position after Guestbook in Normal Mode order.

**Proactive Stage-17-lesson application:** `data/bulletin.json` and its
`.lock` file were added to both `piratebox_deploy.sh`'s `--exclude` list
and `.gitignore` in the same change that introduced the feature, before
any deploy could touch them.

**Not added to the Stage 21 Stats page's counts** - that page is
explicitly scoped to device health + static content catalog, not live
community-post volume; left alone rather than expanding an
already-committed stage's scope.

**Process note:** unlike every prior stage, no dedicated pre-stage
`var/www/html` backup was taken before deploying this one - caught only
afterward. Risk was low in practice (`piratebox_deploy.sh` is
add/update-only, never deletes, and no `bulletin.json` existed yet to
lose), and git history itself still serves as the pre-stage baseline for
every repo file, but a live-tree snapshot should still have been taken
first as usual. A backup was taken immediately after
(`bulletin-stage22-post-20260901-101015`) and the miss is recorded here
rather than glossed over.

**Testing:** `php -l` clean (`bulletin.php`, `admin/index.php`,
`help.php`, `navbar.php`); manual JS brace/paren/bracket balance check
on `scripts.js` (no JS engine available in this environment); isolated
PHP-built-in-server flow test on a throwaway copy covered: empty-board
state, CSRF rejection (missing token -> 403), a legitimate post
(category pill and message rendered correctly, `?fetch=1` JSON
correct), and a deliberately malicious post (`<script>` in both the
message and the category field) - message body came back
`htmlspecialchars()`-escaped with no raw `<script>` tag in the response,
and the invalid category fell back to `info` exactly as designed;
live-deployed via the approved sudo automation; live-verified in both
Normal and Emergency Mode (page loads, nav link/badge present, nav
ordering correct per mode); confirmed `recovery-messages.json` and other
excluded live data untouched by the deploy; mode restored to Normal;
logs clean.

## Stage 21: Stats / Metrics / Appliance Status

**Decision date:** 2026-09-01. Layered on Stage 20 (`b241a4e`).

New public `/utility/status/` page (no login, unlike `/admin/`) shows
aggregate device health (uptime, storage/RAM free, CPU temp, current
mode, cumulative Emergency Mode runtime) and content-catalog counts
(reusing Stage 19/20's export `manifest.json` - not a third independent
count). Wi-Fi client count and per-service health reuse the existing
Phase 4 root status helper (`/run/piratebox/status.json`) with the same
staleness fallback `admin/index.php` already established. Page states its
privacy scope explicitly: aggregate-only, no visitor identity/IP/MAC,
no per-visitor or per-download logs.

**New shared module `includes/metrics.php`** extracts the `/proc` reads
and helper-snapshot logic into one place so the Stats page and any future
consumer (an OLED status line - see Stage 29) share one implementation.
**Deliberately not adopted by `admin/index.php` itself** - refactoring an
already-approved, destructive-action-containing page carried more
regression risk than the resulting de-duplication was worth; the
duplication is accepted and flagged as a Stage 27 (maintenance pipeline)
consolidation candidate.

**New feature: cumulative Emergency Mode runtime.** `set_piratebox_mode.sh`
now appends one line (`<unix timestamp> <mode>`) to
`data/mode-transitions.log` on every real transition - best-effort
(never fails the actual mode change if the log write fails), world-readable,
lives on the SD card (unlike mode state itself) since a running total
should survive a reboot. `includes/metrics.php` sums closed + any
still-open Emergency interval. **Lesson from Stage 17 applied proactively
this time**: the new data file was added to both `piratebox_deploy.sh`'s
`--exclude` list and `.gitignore` in the same change that introduced it,
before any deploy could touch it.

**Deferred, not implemented:** lifetime counters (downloads served,
aggregate bytes/devices served). Getting the aggregate-only,
zero-fingerprinting privacy boundary right deserves its own careful pass
rather than a rushed addition - left for a future stage.

**Real pre-existing bug found (not introduced by this stage):**
`/run/piratebox/status.json` was missing on the live device.
`piratebox-status.service` was failing every run with `226/NAMESPACE`
("Failed to set up mount namespacing: /run/piratebox: No such file or
directory"). Root cause: the unit used `ReadWritePaths=/run/piratebox`,
which grants access to a path but does not create it; `/run` is tmpfs and
is wiped every boot, and unlike `/var/www/piratebox-tmp` (which has a
`tmpfiles.d` rule - `etc/tmpfiles.d/piratebox-tmp.conf`), nothing ever
created `/run/piratebox`, so `ProtectSystem=strict`'s namespace setup
failed before the helper script's own `mkdir -p` could run. This has been
silently degrading `admin/index.php`'s Wi-Fi/service-health stats (and
would have done the same to this stage's new Stats page) to "not
reporting" since whenever this failure mode started.

**Fixed in the repo** (`etc/systemd/system/piratebox-status.service`):
replaced `ReadWritePaths=/run/piratebox` with `RuntimeDirectory=piratebox`
+ `RuntimeDirectoryPreserve=yes` - systemd's purpose-built mechanism for
exactly this (creates the directory before each start, owned by the
unit's user; `Preserve=yes` keeps `status.json` across this oneshot
unit's repeated 30s runs rather than tearing the directory down after
each one). **NOT deployed** - copying a unit into `/etc/systemd/system/`
plus `systemctl daemon-reload` is system configuration outside both the
5-command sudoers boundary and `setup_claude_automation.sh`'s scope
(which only installs the two deploy/mode-switch scripts + sudoers file).
Both this page and `admin/index.php` handle the missing snapshot
gracefully in the meantime (explicit "not reporting" state, never a
guess) - nothing is broken by leaving this unapplied, just less
informative.

**Two pending manual steps, outside this session's automation, for the
user's awareness:**
1. Re-run `sudo ./setup_claude_automation.sh` to pick up this stage's
   `set_piratebox_mode.sh` change (transition logging) at
   `/usr/local/bin/set_piratebox_mode.sh`. Until then, mode switches keep
   working exactly as before, they just don't log to
   `data/mode-transitions.log` yet, so the Stats page's Emergency-runtime
   figure stays at zero.
2. To apply the `piratebox-status.service` fix above:
   `sudo cp etc/systemd/system/piratebox-status.service /etc/systemd/system/piratebox-status.service && sudo systemctl daemon-reload && sudo systemctl restart piratebox-status.service`.

**Not added to the `/utility/` landing grid** (same 8-card judgment as
Stage 20) - cross-linked from the grid page's "Also on this PirateBox"
row and from Manifest/Download's own link rows instead.

**Testing:** `php -l` clean on all touched files; `bash -n` clean on both
shell scripts; isolated PHP-built-in-server test (learned from Stage 20)
confirmed the HTML page and all three download formats
(TXT/JSON/CSV, correct headers) on a throwaway copy, including the
graceful "status helper not reporting" fallback with no
`/run/piratebox/status.json` present; live-deployed via
`sudo -n piratebox_deploy.sh`; live-verified via `curl` in both Normal
and Emergency Mode (page content, mode cell, and Emergency banner all
correct); confirmed `data/recovery-messages.json` and other excluded
live data untouched by the deploy; mode restored to Normal afterward;
logs clean.

## Stage 20: PirateBox Manifest ("What's On This PirateBox?")

**Decision date:** 2026-09-01. Layered on Stage 19 (`87c4307`).

New `/utility/manifest/` combines two read-only sources rather than
recomputing anything: Stage 19's `manifest.json` (content counts, bundle
size - reused, not duplicated) plus a live count of `public/uploads/`
using the exact same `scandir()` logic `index.php`'s file listing already
uses (nothing newly exposed - that listing is already public). Offers
TXT/JSON/CSV downloads, generated on the fly (cheap - a handful of
numbers, not the "giant archive" the instruction warns against
rebuilding per-request - that concern applies to the ZIP bundles, built
once by Stage 19's script, not this small text formatting).

**Real bug found and fixed during testing:** the initial version pointed
at `../../exports/manifest.json` - one directory level too many
(`manifest/` and `exports/` are sibling directories, both direct children
of `utility/`, so it needed `../exports/`). Caught immediately because
testing showed every count rendering as `0` - traced, fixed, and
**re-verified with a corrected test method**: the first test pass used
`php index.php` under plain CLI, which doesn't populate `$_GET` from
`QUERY_STRING` (a CGI/SAPI-specific behavior) - it couldn't have caught
the three download-format code paths at all, only the fact that counts
were zero. Correctly re-tested via PHP's built-in web server instead
(same technique already used for Stage 16), confirming all three formats
work with correct headers (`Content-Disposition: attachment`,
appropriate `Content-Type`) and correct data.

**Not added to the `/utility/` landing grid** (already at 8 cards) -
cross-linked instead from the closely-related Download page, consistent
with the same "don't crowd the primary grid" judgment Stage 9 already
established for Local Information.

**Testing:** `php -l` clean; deploy previewed with an itemized dry-run;
live-verified the HTML page and all three download formats against
production (real upload count: 2 files, 143 bytes, matching actual
accumulated test uploads from earlier stages); full regression sweep
unaffected; logs clean; mode confirmed still Normal (not mode-
conditional, matching every other Utility section).

**Backup:** `~/piratebox-backups/manifest-stage20-pre-20260901-094955/`.

## Stage 19: "Take This With You" Download / Export System

**Decision date:** 2026-09-01. Layered on Stage 18 (`0190a70`). The
flagship feature of this expansion batch.

**PHP's `ZipArchive` extension is not installed** (confirmed directly:
`php -m | grep zip` empty, `class_exists('ZipArchive')` false) - installing
it would cross the explicit package-install stop condition. Resolved by
building ZIPs with **Python's standard-library `zipfile` module** (no new
package - `python3` is already present) inside a new **explicit, offline
build script** (`tools/build_export_bundles.py`), which is also exactly
the architecture the instruction itself prefers: source data → explicit
build process → cached/static bundles, never built per-request.

**Static offline copy - the core deliverable:** the build script reads
the *same* JSON files every live section page reads (single source of
truth) and generates genuinely standalone static HTML - relative links
throughout, `assets/styles.css`/`scripts.js` bundled verbatim (byte-
identical to live, confirmed), same `radio-entry`/`data-search`/
`data-group` markup as the live pages so the existing search/filter JS
works completely unmodified on the offline copy too. **Tested away from
the live environment**, per instruction: extracted the built ZIP into an
isolated temp directory and verified independently - correct file
structure, zero absolute `/utility/`or `/assets/` references anywhere,
zero leftover `<?php`/`<?=` tags, `<details>`/`</details>` balanced (37/37
on the Radio page), entry counts matching the live site exactly per
section, and the empty Library catalog degrading to a clean message
rather than an error.

**Three tiers, as specified:** individual raw JSON per section (the
lightest option - literally the same data files, copied verbatim);
4 logical bundles (Radio; Emergency+First Aid together, since they're
closely related life-safety reference; Maps+Local Information together;
Library - "Manuals/Documents"); one Complete Offline Utility Library ZIP.
Plus a CSV export for Radio's services table specifically - genuinely
tabular data, not a format added just to claim support (no CSV was added
for anything else).

**Export privacy, guaranteed by scope, not just checked after the fact:**
the build script only ever reads from `data/utility/*` and writes to
`public/utility/exports/` - there is no file-access path in it that could
reach chat/guestbook/recovery messages/admin credentials/uploads/system
config, by construction, not by an added filter. Documented explicitly at
the top of the script itself, not only here.

**Export performance:** pre-built once via the explicit script, never
per-request - confirmed by design (the download page only reads
`manifest.json` and serves plain static file links; nothing is generated
when a visitor loads the page). Total footprint is tiny: complete bundle
52KB, individual bundles 11-26KB, whole `exports/` directory 580KB on
disk - trivial for a Pi. Real, computed sizes (not estimates) are read
from the manifest and shown on the download page.

**Generated output deliberately NOT committed to git** - same convention
this project already uses for QR codes and the deployed `VERSION` file
(Phase 5): 100% regenerable from tracked source data via
`tools/build_export_bundles.py`, so committing the actual ZIPs/HTML would
mean hand-keeping two copies in sync. Added `public/utility/exports/` to
`.gitignore`; `piratebox_deploy.sh` still syncs it to live correctly since
`rsync` operates on the filesystem, independent of git tracking - verified
directly (deployed file's md5sum matched the locally-built one exactly).

**Also fixed while here:** `data/recovery-messages.json` (Stage 16) had
never been added to `.gitignore` despite being the same category of live
runtime data as `chat.json`/`messages.json`, which *are* ignored -
inconsistent, now corrected (`git rm --cached`, added to `.gitignore`,
local file left untouched on disk).

**Cross-linked from every section** (Radio/Emergency/First Aid/Maps/Local
Info/Library/Search hero-actions, plus a new card on the `/utility/`
landing grid) - found via the same audit habit Stage 17 established,
applied proactively this time rather than after the fact.

**Testing:** Python script syntax-checked (`ast.parse`) and run
successfully; `php -l` clean on all 9 touched/new PHP files; isolated
extraction test (above); deploy previewed with an itemized dry-run; live
regression sweep unaffected; live-downloaded ZIP's md5sum verified
identical to the locally-built one; live CSV download confirmed
well-formed; mode confirmed still Normal (download page is not
mode-conditional, matching every other Utility section); logs clean;
services untouched.

**Backup:** `~/piratebox-backups/export-stage19-pre-20260901-075834/`.

## Stage 18: Global Offline Search Expansion

**Decision date:** 2026-09-01. Layered on Stage 17 (`7924e01`).
Verification-only - no code changes, since the audit found Stage 8's
existing implementation (strengthened by Stage 17's cross-link fixes)
already satisfies this stage's requirements.

**Verified rather than assumed:** re-ran cross-section query checks
directly against the live index - `hypothermia` correctly spans Emergency
("Extreme Cold & Winter Weather") and First Aid ("Hypothermia &
Frostbite"), exactly the example in the instruction; `repeater` correctly
spans Radio bands and Local Information. `tools/build_search_index.py`'s
`load()` already returns `[]` for any missing dataset file rather than
erroring - confirmed by reading the code, consistent with Stage 10's
already-tested resilience discipline. The Search page's category chips
already cover all 6 sections (Radio/Emergency/First Aid/Maps/Local
Information/Library).

**Recovery/Found Device system deliberately stays OUT of global search** -
confirmed this is correct-by-design, not a gap: `build_search_index.py`
never reads `recovery-messages.json`, and `/found/` is a core PirateBox
page (like `help.php`/`chat.php`), not a `/utility/` JSON-driven section.
Indexing recovery messages would directly contradict Stage 16's own "no
enumeration" privacy requirement - the only correct search behavior here
is none at all.

**PDF full-text indexing remains deferred**, unchanged - no
`pdftotext`/`poppler-utils`, metadata/title/tag search only, per
instruction (moot in practice regardless, since the Library catalog has
no documents yet).

**No files changed, no deploy performed.**

## Stage 17: Complete Local Information / Content Audit

**Decision date:** 2026-09-01. Layered on Stage 16 (`8266484`/`84bb565`).
Commit note: the cross-link fixes below and the deploy-script data-loss
fix ended up in one commit (`a4478f1`) rather than two, because the
cross-link files were already `git add`-ed before the bug was discovered
mid-stage - both sets of changes are correct and tested, just not as
cleanly separated in history as usual.

**Audit method:** enumerated every dataset's entry count (confirms Maps
catalog and Library catalog are the only genuinely empty ones - by
design, not oversight); crawled every Utility section page's
`hero-actions` cross-links looking specifically for missing connections
between related sections.

**Missing cross-links found and fixed:** Radio didn't link to Emergency
(despite its own `emergency-monitoring-quick-reference` guide topic
conceptually pointing at it) or Local Information; First Aid and Library
didn't link to Local Information either. All four fixed - Local
Information is now reachable from every section whose content it
naturally complements (repeaters from Radio, hospitals/shelters from
Emergency/First Aid/Library), not just Emergency/Maps as before.

**Local Information - fields needing operator population** (not
fabricated, per instruction - deployment location isn't known to this
session): `region_label`, `last_updated`, `emergency_management`,
`nws_office`, `hospitals`, `shelters`, `amateur_repeaters`, `radio_notes`,
`map_references`, `other_resources` are all still blank. Only the two
universal `emergency_numbers` (911, Poison Control) are populated, as
established in Stage 6. **Schema enhanced** (not the content) so that
whenever these fields do get populated, each entry can optionally carry
`source`/`verified`/`confidence` - documented in a new
`data/utility/local/README.md` (mirroring Stage 7 Library's own README
pattern) and rendered on the page (`li_provenance()` helper) when present,
confirmed via direct unit test to render correctly when populated and
render nothing when absent.

**Curated content acquisition plan for Maps/Library (documentation only -
nothing downloaded)**, researched rather than guessed at:

| Candidate | Publisher/license | Approx. size | Assessment |
|---|---|---|---|
| Individual FEMA/Ready.gov hazard info sheets (thunderstorm, tornado, flood, earthquake, wildfire, extreme heat, winter storm, power outage, hurricane, etc.) | U.S. government work - public domain, FEMA explicitly permits reproduction | A few hundred KB each; the "full suite" PDF is a few MB | **Best near-term candidate** - small, clearly public domain, and would directly complement the Emergency Reference topics already citing these exact source pages. Still requires the operator's explicit go-ahead per instruction before any download. |
| FEMA "Are You Ready? An In-Depth Guide to Citizen Preparedness" (P-2064 / IS-22) | U.S. government work - public domain | **~183MB** (204 pages, per Internet Archive's listing) | Public domain, but the size alone crosses into "significant download" - would need its own explicit approval, not bundled into a smaller batch. |
| Red Cross first-aid/CPR reference guides | Redistribution terms **unclear** - offered through a "My Digital Books" access-controlled platform and a paid store in the material found this session | Not verified | **Do not acquire** without first getting clear confirmation of redistribution rights - unlike FEMA's government works, "free to view" was not confirmed to mean "free to redistribute" here. |
| ARRL band-plan/reference material | Member/copyrighted content, not public domain | N/A | **Excluded from any acquisition plan** - already correctly treated as citation-only (voluntary-convention source), never as bundled PDF content, throughout Stages 2-10. |
| Raspberry Pi/Linux/networking official documentation | Likely partially open-licensed (not verified this session) | Not researched | Flagged as a plausible future category - needs its own license/size research pass before any acquisition decision, not assumed. |

No files were downloaded. Per instruction, if/when the operator wants to
proceed with the FEMA hazard-info-sheet candidates (the only "ready to
acquire" row above), that's a small, explicit, separately-approved next
step - not something this audit triggers on its own.

**Testing:** `php -l` clean; deploy previewed with an itemized dry-run;
live regression sweep of every existing page unaffected (including the
deploy-script bug's own aftermath, fully resolved - see the separate
`a4478f1` entry above); `li_provenance()` unit-tested directly for both
populated and empty cases; mode confirmed still Normal throughout (no
mode-conditional content touched this stage).

**Backup:** `~/piratebox-backups/audit-stage17-pre-20260901-073340/`.

## Stage 16: Public PirateBox ID / Found Device / Recovery System

**Decision date:** 2026-09-01. Layered on Stage 14 (`afabb4e`). The
largest and most privacy-sensitive stage of the roadmap expansion so far -
tested more thoroughly than the pace-adapted norm for this batch (isolated
PHP-built-in-server flow tests before touching live data, plus one real
live production test).

**Device ID:** `tools/generate_device_id.sh` generates a random ID
(this device's: `PB-NSC5-3C`) from `/dev/urandom` - verified NOT derived
from MAC/serial/hostname/IP by construction (the script never reads any of
those). Idempotent-safe: refuses to overwrite an existing ID without
`--force`, specifically so cloning this SD card for a second physical unit
doesn't silently leave two devices sharing one ID. Stored in
`data/device-id.json`, read-only from PHP via `includes/device_id.php`
(same read-only-consumer pattern as every other small state file in this
project). Displayed on the Help/About page and the new Found Device page.

**`/found/`** (new): explains what PirateBox is, states plainly that
seeing the Wi-Fi signal alone is never a reason to locate the hardware,
and - for someone who has *physically* found the device - asks them not to
reset/dismantle/erase it and offers a recovery-message path. Safety/
property concerns are stated as taking priority throughout, not just once.

**Recovery messages: deliberately separate from Chat/Guestbook/uploads** -
own data file (`data/recovery-messages.json`), own lock, same atomic
temp-file-then-`rename()` write pattern every other store in this project
uses. No operator PII is ever displayed (nothing about the operator is
even stored). Finder contact is a free-text optional field, never
required. Explicit on-page statement that messages never leave the device
(true by construction - there's no Internet connection for them to leave
over).

**Rate-limiting, deliberately non-invasive:** submissions are throttled by
comparing against the store's *own last entry timestamp* under its
existing lock (30s cooldown) - no new per-client tracking file, no IP
logging. Lookups get a session-only cooldown (5s) - reuses the session
that already exists for CSRF, introduces no new tracking mechanism.

**Two-way thread implemented** (assessed as safely buildable within the
existing architecture, not deferred): each submission gets a random
6-character code (`ALPHABET` excludes 0/O/1/I/L for readability, ~30 bits
of entropy - judged adequate given this is a local-only, non-Internet-
exposed, rate-limited surface, not a public web service). No enumeration
endpoint exists anywhere - the only way to see a message is to already
have its code. Operator replies via a new, non-destructive `admin/`
action (`reply_recovery`) - deliberately **not** gated behind the
confirm-checkbox pattern used for destructive actions, since replying is
neither destructive nor irreversible (documented explicitly in-code so a
future reader doesn't "fix" this inconsistency without understanding it).
Purge (single or all) **is** confirm-gated, matching every other
destructive admin action.

**Testing performed:** isolated end-to-end flow tests using PHP's built-in
server against a throwaway temp copy (never live data) before touching
production - submit→code returned, immediate second submission correctly
cooldown-blocked, correct-code lookup shows the message, wrong code
correctly shows "not found," admin reply correctly persists and appears
on re-lookup, purge correctly requires confirmation and correctly clears
when confirmed. One bug found and diagnosed during testing: an early test
run appeared to show a reply not persisting - traced to a shell/grep
artifact in the test script itself (confirmed by re-running with raw JSON
inspection at each step, which showed the write path was correct all
along), not an application defect - documented here so the false alarm
doesn't get rediscovered and mistrusted later. `php -l` clean on all
files; deploy previewed with an itemized dry-run; live regression sweep
unaffected; one real live production submission test (clearly labeled,
purgeable via `/admin/`) confirmed the deployed code path end-to-end;
logs clean; services untouched; mode confirmed still Normal throughout
(neither new page reads `piratebox_get_mode()`, so no mode-switch cycle
was needed this stage).

**Design-only, not implemented, per instruction:**
- **Recovery/Lost Mode:** a third, *software-selectable* presentation
  state, explicitly separate from Normal/Emergency and **not** changing
  the physical toggle design at all. Concept: a prominent landing page
  stating the unit is marked missing/awaiting return, direct access to
  the Found Device messaging flow already built above, and just enough of
  the rest of the site left reachable to explain what the appliance is.
  Nothing about *how* this would be triggered has been decided (a future
  admin toggle is the obvious candidate, mirroring `set_piratebox_mode.sh`'s
  own pattern) - deliberately left open rather than guessed at now.
- **`PirateBox-Please-Return` SSID:** mentioned only as a future
  possibility for Recovery Mode. No SSID, hostapd, or networking change
  was made or is proposed as part of this stage - any actual SSID change
  remains squarely inside this session's explicit stop-condition and
  would need its own approval when it's actually time to build it.
- **Physical recovery label text** (documented here, no artwork
  generated): "PIRATEBOX - OFFLINE NETWORK APPLIANCE / This device
  provides a local Wi-Fi information and file-sharing service. / If
  operational, connect to the PirateBox Wi-Fi network and choose: About →
  Found This Device. / Device ID: `PB-NSC5-3C` / Please do not reset,
  dismantle, or erase the device merely because it was found." - no owner
  information anywhere on the label, matching instruction. A future QR
  code linking to the *local* `/found/` page (never an Internet URL,
  since one wouldn't resolve on this network anyway) is noted as a
  reasonable future addition once physical labels are actually produced -
  not built now.

**Backup:** `~/piratebox-backups/recovery-stage16-pre-20260901-072524/`.

## Stage 14: Main-Page Onboarding / "What Can I Do Here?"

**Decision date:** 2026-09-01. Layered on Stage 13 (`2081c4b`).

Normal Mode's hero gains one short paragraph (offline library exists,
link to the new capabilities page, Emergency Mode is physical-switch-only,
not-an-official-emergency-service) - kept short/non-intrusive per
instruction, doesn't touch the existing Files-first identity. Emergency
Mode's tagline became the literal "Emergency Mode is Active" (previously
"Local Offline Network"), with a subtle amber accent (reused color, not a
new alarm color) and the same not-an-official-service line, previously
missing from Emergency Mode entirely. New `public/whatcanidohere.php`:
mode-aware capabilities list covering every item in the instruction, not
added to the primary navbar (reachable via links) to avoid crowding it.

**Testing:** `php -l` clean; deployed via automation; live-verified both
modes; regression unaffected; mode restored to Normal.

**Backup:** `~/piratebox-backups/onboarding-stage14-pre-20260901-072201/`.

## Stage 13: PirateBox Identity / Transparency / About

**Decision date:** 2026-09-01. Expands `help.php` (no new page/data file)
with researched PirateBox history and appliance-transparency content.
Layered on Stage 12 (`dd09e5f`).

**History researched, not asserted from the prompt** - David Darts (NYU
Steinhardt, 2011, Free Art License), Dead Drops/pirate-radio/free-culture
inspiration, original OpenWrt-router implementation, popularity in France
(Jean Debaecker), later maintenance (Matthias Strubel), the LibraryBox
fork (Jason Griffey, 2012), and the project's Nov 17 2019 discontinuation
(cited reason: locked router firmware + HTTPS-only browsers) - sourced to
Wikipedia and LibraryBox's own About page, both cited on-page with
retrieval date. Explicit, prominent disclaimer that this installation is
an independent reimplementation, not an official continuation, no
affiliation with the original developers - satisfies the operator's
explicit non-affiliation instruction directly rather than leaving it
implied.

**"About This PirateBox"** describes the appliance at a deliberately safe
level (Raspberry Pi, local storage, independent AP, planned battery/
controls/display) - no serial numbers, MAC addresses, SSH/admin details,
exact location, or operator identity, matching the instruction's exposure
list exactly. Photo area reuses the existing `.utility-placeholder-note`
style (zero new CSS) and states a real photo will be added post-build -
no stock/fake/generated imagery per instruction.

**"If You Encounter This Network"** - one sentence is Emergency-Mode-only
(`help.php` now reads `piratebox_get_mode()` for the first time among core,
non-Utility pages), verified live present only in Emergency Mode: notes
that leaving an appropriately-placed unit running helps preserve access
for others during an actual emergency, exactly as instructed. Forward-
references `/found/`, built next in Stage 16.

**Also fixed in passing:** "Using PirateBox" never mentioned the Utility
Library at all - a real, pre-existing gap, corrected. Folded in a compact
Connection Status table (Stage 15's content) since it belongs on the same
page as everything else added this stage.

**Testing:** `php -l` clean; PHP-CLI render confirmed the mode-conditional
sentence correctly absent under the missing-file fallback; deployed via
automation; live-verified in both modes (conditional sentence present only
in Emergency); full regression sweep unaffected; mode restored to Normal.

**Backup:** `~/piratebox-backups/identity-stage13-pre-20260901-071759/`.

## Offline Utility Library - Stage 10: Accessibility / Resilience / Performance Audit

**Decision date:** 2026-09-01.

**Scope:** a dedicated review pass across the entire Utility Library
(Stages 1-9) - no code changes were needed as a result, since the audit
found no real defects. Purely read-only against the live site, plus one
safe, isolated resilience test against a throwaway temp copy that never
touched live data. Layered on Stage 9 (`9e14b53`); HEAD unchanged by this
entry except for this documentation.

**Findings, by checklist item:**

- **JSON validity:** all 15 data files across every section validated -
  clean.
- **Broken links:** crawled all 12 pages (main site + every Utility
  section), extracted every internal `href`/`src` (95 total, including
  every deep-link fragment introduced in Stage 8) - 15 unique destination
  pages, zero broken. Separately verified all 95 fragment-bearing links
  (`#entry-id`) actually resolve to a real element `id` on their target
  page, not just that the page loads - **zero mismatches**.
- **Source citations:** automated-checked all 52 unique source URLs across
  every dataset. 44 resolved `200` directly. 7 CDC URLs and 1 USGS URL
  returned `403`/failed to connect under automated request patterns -
  investigated rather than dismissed: confirmed `cdc.gov` itself is fully
  reachable (the block is anti-bot protection on specific content pages,
  the same pattern already well-documented for FCC/Ready.gov in Stages
  2-4, now confirmed to extend to CDC's domain too); the USGS failure was
  isolated to a **local Pi issue** - broken IPv6 routes to some of
  `usgs.gov`'s resolved addresses causing curl to exhaust IPv6 attempts
  before an SSL-related timeout, confirmed by forcing IPv4 (`curl -4`,
  still failed with an SSL cert error) and then confirming the actual page
  exists by skipping cert verification (`-k`, returned the same `403`
  anti-bot response as CDC) - not a dead or incorrect citation, and not
  something that affects the offline site at all (this only matters for
  the Pi's own outbound research capability during content-building
  sessions, never for an end user connected to the AP). No citation was
  changed; none needed to be.
- **Malformed-JSON / failure-scenario resilience** (the required
  "intentionally weak/failure scenario" test): explicitly corrupted
  (invalid syntax), deleted, and emptied three different section data
  files **on an isolated temp copy of the whole tree** (never the live
  site) and rendered each affected page via the PHP CLI directly. In every
  case: zero fatal errors, zero PHP warnings, the page chrome (title,
  nav, disclaimers) rendered correctly, and the *unaffected* content on
  the same page (e.g. Radio's modulation/guides sections when only
  `services.json` was corrupted) kept working normally - confirming the
  `is_array($decoded) ? $decoded : []` defensive pattern used by every
  section's data loader behaves exactly as designed under real corruption,
  not just in theory.
- **JS-off behavior:** every page in this project has been rendered and
  verified via the PHP CLI directly (which never executes JavaScript)
  before every single deploy since Stage 2 - this audit didn't need to
  re-invent that check, just confirms the pattern held throughout: all
  core reference content is server-rendered HTML, `<details>/<summary>`
  are native browser elements (keyboard-operable with no JS), and the only
  JS-dependent behavior anywhere is live search-as-you-type filtering and
  the Stage 8 deep-link auto-open convenience - both explicitly designed
  as enhancements over already-complete server-rendered content, never a
  requirement to see it.
- **Semantic HTML / heading hierarchy:** every page has exactly one
  `<h1>`, followed only by `<h2>` group headings with no skipped levels -
  checked across all 8 Utility pages plus the main site.
- **Keyboard navigation:** every interactive element across the whole
  Utility Library is a real semantic element (`<button>` for filter
  chips, native `<details>/<summary>` for expand/collapse, `<a>` for
  links, `<input>` for search) - no custom JS-dependent widgets anywhere,
  so keyboard operability is inherent, not something bolted on.
- **Contrast:** reconfirmed the Stage 9 review - new text colors (`#aaa`
  on `#181821`) clear WCAG AA comfortably.
- **Duplicated content:** reconfirmed Normal/Emergency Mode content
  identity holds (already proven live every stage since the Emergency
  Mode foundation phase); cross-section topics that sound related (e.g.
  Emergency's heat/cold guidance vs. First Aid's) are deliberately
  distinct in framing (preparedness vs. treatment) and were written
  separately from different source material, not copy-pasted duplicates.
- **Stale placeholder text:** none found - the only remaining "not yet"-
  style messages are the deliberate, correct empty-state messages for
  Local Information's still-blank fields and (unreachable in practice
  now, since it always exists) the Search page's missing-index fallback.
- **Unnecessary network requests / external dependencies:** re-confirmed
  zero `http(s)://` references anywhere in served PHP/JS/CSS other than
  the SVG XML namespace declaration (a required spec string, never a
  network fetch) and source-citation links a visitor would open
  deliberately.
- **Asset/data sizes and weak-Wi-Fi load behavior:** total
  `data/utility/` payload across all 6 sections is **212KB**; the two
  largest rendered pages (Radio, Search) are 108KB/77KB uncompressed but
  confirmed **actually compress to 17KB/13KB over the wire** (nginx gzip
  confirmed active via `Content-Encoding: gzip`, verified with real byte
  counts, not just the response header) - a 5.9-6.4x reduction, trivial
  even on a congested Pi 3B+ AP connection. `scripts.js` (~21.7KB) and
  `styles.css` (~21.3KB) are shared, cached-by-the-browser-after-first-
  load, single files - no bundle bloat, no per-page duplication.
- **Mobile/phone layouts:** re-confirmed the Stage 9 CSS-level findings
  hold across every section page, not just the one landing page Stage 9
  touched directly.

**No code changes resulted from this audit** - everything checked came
back clean or was a false alarm correctly diagnosed and explained above,
not silently ignored. This entry is the deliverable for this stage.

## Offline Utility Library - Stage 9: Utility Landing / Emergency Experience Polish

**Decision date:** 2026-09-01.

**Scope:** revisits Emergency Mode's root landing (`public/index.php`,
originally built in the Emergency Mode foundation phase before any real
Utility content existed) now that Stages 2-8 have given it real content to
prioritize. Normal Mode's landing and nav were deliberately left
untouched - confirmed unchanged. No networking/security-boundary/
Emergency-Mode-state-mechanism changes; no packages installed. Layered on
Stage 8 (`e1f19bd`).

**Card order changed** to match the operator's now-informed priority list:
Emergency Info, First Aid, Radio, Maps, Search, Library, Messages/Chat,
Files (previously: Emergency, Radio, Maps, First Aid, Messages/Chat,
Files, Search, Library - an order chosen back when Search and Library were
still empty placeholders). First Aid moved up next to Emergency Info;
Search and Library moved ahead of Chat/Files now that they're real,
useful, content-rich sections rather than stubs.

**Hero copy tightened** for the "random person finds the SSID during an
outage" scenario: tagline is now the literal phrase "Local Offline
Network"; the heading states plainly "This Network Does Not Require
Internet Access"; the body explicitly says "intentionally local" and
spells out that local file sharing/messaging still work normally, not
just that reference content exists. Same calm dark/purple visual language
as everywhere else on the site - no red/alarm styling, no security-tool
aesthetic, consistent with the operator's explicit "not a scary hacker
page" requirement.

**Local Information was deliberately NOT added to this 8-card grid** -
the operator's own priority list for this stage named exactly 8 items and
didn't include it; it stays reachable via the Emergency Info page's own
cross-link (added in Stage 6) and the full `/utility/` landing grid,
without crowding the primary Emergency Mode card list.

**Mobile-usability review performed at the CSS/design level** (no
physical device available this session, consistent with the same honest
disclosure Phase 5 already made about its own onboarding redesign):
confirmed `.utility-grid`'s `repeat(auto-fit, minmax(180px, 1fr))` reflows
to 2 columns at typical phone widths, confirmed the global button/input/
select/a `min-height: 2.25rem` touch-target rule (Phase 5) already covers
every new interactive element added since (`.radio-chip` is a real
`<button>`; `<details><summary>` already exceeds the 44px guideline from
its own padding), and confirmed new text colors (`#aaa` on `#181821`)
comfortably clear WCAG AA contrast. A real-device pass remains a good
idea before relying on this for an actual event, same caveat Phase 5
already carries forward.

**Testing performed:** `php -l` clean; confirmed Normal Mode's landing
renders byte-identical to before (no `utility-grid` present, `<h1>`
unchanged) - **zero regression to Normal Mode**; **deploy previewed with
an itemized dry-run** (confirmed only `public/index.php` would change)
before applying; live regression sweep of every existing page unaffected;
live-verified the new 8-card order and hero copy in Emergency Mode exactly
match spec; banner and `/admin/` gating confirmed still correct;
`nginx`/`php8.4-fpm`/`hostapd`/`dnsmasq` active throughout, no restarts;
error logs clean across the full testing window. Live mode restored to
explicit Normal before finishing - entire cycle via the automation.

**Backup:** `~/piratebox-backups/polish-stage9-pre-20260901-065258/` (full
`var/www/html` mirror + pre-change git HEAD `51b7e8f`).

## Offline Utility Library - Stage 8: Global Offline Search

**Decision date:** 2026-09-01.

**Scope:** builds out `/utility/search/` (a Stage 1 placeholder) into a
real global search across Radio, Emergency, First Aid, Maps, Local
Information, and the Document Library, plus a small deep-linking addition
to all 5 section pages. No networking/security-boundary/Emergency-Mode-
state changes; no packages installed. Layered on Stage 7 (`d615346`).

**`tools/build_search_index.py`** (new, re-runnable): reads the same JSON
data files each section page already reads and writes a single flat
`data/utility/search-index.json` (83 entries, ~34KB) - `{title, section,
url, snippet, keywords, freq?}` per item. This is the "rebuild the index"
command referenced in the project's original planning; re-run it any time
section content changes. No PDF text extraction, no `pdftotext`/
`poppler-utils` - metadata/title/tag search only, per instruction (moot
this stage anyway, since the Library catalog has no documents yet).

**Deep-linking, added to all 5 section pages:** every `<details
class="radio-entry">` across Radio/Emergency/First Aid/Maps/Library now
carries `id="<the item's own id from its JSON>"` (Maps catalog and Library
catalog entries fall back to a positional `map-N`/`doc-N` id if a future
entry omits one). A new guarded block in `scripts.js` checks
`window.location.hash` on load and, if it matches a `.radio-entry` id,
opens that `<details>` and scrolls to it - this is what makes "direct
local link" in a search result actually jump to the answer
(`/utility/radio/#noaa-weather-radio`) rather than just the section page.
Confirmed no duplicate ids on any page before deploying. This is the one
place this stage touched already-approved Stage 2-7 pages - a small,
mechanical, additive change (one attribute per entry), not a redesign.

**Search page design:** server-renders all 83 results as plain link cards
(title, section badge, frequency badge where relevant, snippet) - fully
browsable and useful with JavaScript off, same progressive-enhancement
principle as every other section. Reuses the exact same shared filter
component (`#radioSearch`/`#radioChips`/`data-group`/`data-search`) as
Radio/Emergency/First Aid/Maps/Library - chips here filter by *section*
instead of topic category. ~30 lines of new CSS for the result-card
layout (reusing `.radio-entry-name`/`.radio-entry-mode-badge`/
`.radio-entry-freq` for visual consistency); zero changes to the shared
filter JS itself - it already worked on this markup shape unmodified.

**Local Information indexing note:** since that dataset ships almost
empty (Stage 6), the index always includes one generic "Local Information"
pointer entry (keywords: local/hospital/shelter/repeater/emergency
contact) even though the underlying arrays are empty - so a search for
e.g. "hospital" still surfaces the right section rather than nothing,
confirmed live. The same pattern applies to the Document Library section.

**Testing performed:** search index validated (build-time + live, 83
entries both times); `php -l` clean on all 6 changed PHP files; rendered
the Search page via PHP CLI pre-deploy (83 result cards confirmed); no
duplicate entry ids confirmed on the Radio page before deploy; **deploy
previewed with an itemized dry-run** (filtered to real content changes)
before applying; live regression sweep of every existing page unaffected;
all 12 required test queries (NOAA, 40 meter, airband, generator,
bleeding, hypothermia, flood, water, GPS, GMRS, manual, hospital)
verified against the live index, each resolving to the correct
section(s); live deep-link verified end-to-end (entry id present on the
Radio page, search index href points at it, `scripts.js`'s handling code
confirmed deployed); live Normal vs. Emergency Mode content byte-diff on
both the Search page and (re-verified) the Radio page - **identical**;
`nginx`/`php8.4-fpm`/`hostapd`/`dnsmasq` active throughout, no restarts;
error logs clean across the full testing window. Live mode restored to
explicit Normal before finishing - entire cycle via the automation, no
manual round-trips.

**Backup:** `~/piratebox-backups/search-stage8-pre-20260901-064643/` (full
`var/www/html` mirror + pre-change git HEAD `b9edb15`).

## Offline Utility Library - Stage 7: Document Library

**Decision date:** 2026-09-01.

**Scope:** builds out `/utility/library/` (a Stage 1 placeholder). No
networking/security-boundary/Emergency-Mode-state changes; no packages
installed; **no documents downloaded or bundled** (per explicit
instruction). First stage built entirely using the new deployment/mode
automation - zero manual round-trips this stage. Layered on the automation
commit (`1149f4e`).

**Architecture decision - stayed under webroot, deliberately avoiding the
`open_basedir` change:** the operator's instructions explicitly said to
STOP before making an `open_basedir`/security-boundary change if the
previously-discussed outside-webroot `/var/www/library` design required
one. Rather than build that design and then stop, the framework was built
using the same under-webroot pattern Stage 5's Maps catalog already
established (`public/utility/library/files/`, matching the existing
`public/uploads/`) - which needs **zero** `open_basedir` change, so the
stop-condition never triggers. This is an explicit, documented tradeoff:
if real documents are later added that are sensitive, large, or raise
license/access-control concerns the outside-webroot design was meant to
address, that design should be revisited deliberately at that time, not
assumed to have been ruled out permanently.

**Data:** `data/utility/library/categories.json` (8 categories: Radio
Manuals; Raspberry Pi/Linux/Networking; Electronics References; Vehicle &
Generator/Power Equipment; Emergency & First-Aid Documents; Maps; Equipment
I Own; Other) and `catalog.json` - **intentionally empty array**, same
"don't fabricate content to look populated" principle as Stages 5-6. A
`README.md` alongside them documents the entry schema (title, category,
description, tags, file, file_type, file_size, source, date_version,
provenance_notes) for whoever adds a document later.

**`tools/check_library_catalog.py`** (new): a small, dependency-free
consistency checker - confirms every catalog entry's `file` exists in
`public/utility/library/files/`, and flags any file in that directory with
no matching catalog entry. Deliberately does NOT extract PDF metadata or
build a search index (that would need `pdftotext`/`poppler-utils`, which
the operator's instructions say not to install without stopping first -
this stays dependency-free and lets metadata/title/tag search work today
via the same client-side filter every other section uses). Tested against
both a clean catalog and a deliberately-introduced orphaned file to
confirm it actually catches problems, not just passes trivially.

**Testing performed:** both new JSON files validated (build-time + live);
`php -l` clean; rendered via PHP CLI pre-deploy (empty-state and
"Adding a Document" note both confirmed present, all 8 category chips
render); **deploy previewed with a read-only itemized `rsync --dry-run`
before applying** (confirmed only the new Library files + modified
`index.php` would change, nothing else, before running the real sync);
live regression sweep of every existing page unaffected; live empty-state/
instructions confirmed on the deployed page; live Normal vs. Emergency
Mode content byte-diff - **identical**; `nginx`/`php8.4-fpm`/`hostapd`/
`dnsmasq` active throughout, no restarts; error logs clean across the full
testing window. Live mode restored to explicit Normal before finishing -
entire cycle performed via the new automation with no manual round-trips.

**Backup:** `~/piratebox-backups/library-stage7-pre-20260901-064228/`
(full `var/www/html` mirror + pre-change git HEAD `1149f4e`).

## Claude deployment/mode-switch automation

**Decision date:** 2026-09-01.

**Scope:** infrastructure/tooling only - no site content, no networking,
no PHP security restrictions. Adds a narrow, auditable `sudo` NOPASSWD
grant so this session's automation can deploy repo changes and switch
Normal/Emergency Mode without a manual round-trip to the operator's
terminal for every stage, which had become the dominant bottleneck across
Stages 1-6.

**What was added:**
- `piratebox_deploy.sh` (new): replaces every stage's hand-written
  `rsync`/`cp` deploy block with one script. Syncs this repo's
  `var/www/html/` onto the live `/var/www/html/` - additive/update only
  (no `--delete`, ever), with an explicit `--exclude` for every piece of
  live user-generated content (uploads, chat/guestbook JSON + lock files,
  the deployed `VERSION` file, the admin password hash, generated QR
  codes) - belt-and-suspenders on top of the fact none of those are ever
  tracked in the repo/`.gitignore` in the first place, so a plain sync
  could not touch them regardless. Accepts no arguments beyond an optional
  `--dry-run` - nothing about its behavior is influenced by
  attacker/agent-controlled input.
- `etc/sudoers.d/piratebox-claude` (new): exactly 5 literal `NOPASSWD`
  command lines (no wildcards, no `ALL`) naming `piratebox_deploy.sh`
  (bare and `--dry-run`) and `set_piratebox_mode.sh` (`normal`/
  `emergency`/`status` - three separate exact lines, not a glob) at their
  `/usr/local/bin` paths.
- `setup_claude_automation.sh` (new): one-time, idempotent installer the
  operator runs with `sudo` - installs both scripts to `/usr/local/bin`
  (root:root, `0755`) and the sudoers rule (root:root, `0440`, validated
  with `visudo -cf` before installing, install aborts if validation
  fails).

**The critical safety property:** both granted scripts are installed
root-owned, **not writable by `moose`**. The `moose` account (which this
session runs as) can *trigger* them via the narrow sudo rule but cannot
*modify* what they do - this is what prevents a NOPASSWD grant from
becoming a privilege-escalation path (edit the script, then run the
now-malicious version via the trusted rule). This mirrors the exact
pattern this project already used for `purge_uploads.sh`/
`restart_hostapd.sh` (root-owned deployed copy in `/usr/local/bin`, plain
reference copy in the repo) - not a new convention introduced for this.

**Verification performed after the operator ran the installer:**
- Confirmed both scripts' deployed content matches the repo exactly, and
  confirmed their live ownership/permissions (`root:root`, `0755` for the
  scripts, `0440` for the sudoers file).
- `visudo -cf` on the installed sudoers file confirmed syntactically valid.
- Confirmed all 5 NOPASSWD commands work with `sudo -n` (which fails
  immediately rather than prompting if a password would actually be
  needed) - deploy dry-run, mode status, and (separately) real mode
  switches in both directions, and a real (non-dry-run) deploy.
- Confirmed the deploy script rejects any argument other than `--dry-run`
  (tested with `--delete`).
- **Caught and correctly diagnosed a false alarm during testing:**
  `sudo -n whoami` and `sudo -n cat /etc/shadow` initially succeeded
  without a password, which looked like a broader passwordless grant than
  intended. Root-caused to this system's pre-existing
  `Defaults timestamp_type=global` setting (visible in `sudo -l` output,
  not something this change touched) combined with the operator having
  authenticated with a real password moments earlier while running the
  installer - that leaves a short-lived cached credential shared across
  all sessions/ttys for the user, system-wide, not per-terminal. Proved
  this explicitly: `sudo -k` (clear the cached credential, needs no auth
  itself) immediately made `sudo -n whoami` fail again ("a password is
  required"), while all 5 approved commands continued to work correctly
  afterward - confirming they work via the sudoers rule itself, not
  residual cached credentials, and confirming nothing broader than the 5
  intended lines was ever actually granted. `sudo -l` further confirmed
  the pre-existing `(ALL : ALL) ALL` entry (standard Debian `sudo`-group
  membership, unrelated to and unmodified by this change) still requires
  a password in the general case - only the 5 named commands bypass it.
- Live regression sweep of every existing page, all 4 core services
  (`nginx`/`php8.4-fpm`/`hostapd`/`dnsmasq`), and error logs across the
  whole testing window - all clean, no restarts, no new errors. Mode
  confirmed restored to Normal at the end.

**What this changes going forward:** for Stage 7 onward, deployment and
Normal/Emergency test-mode switching are performed directly by this
session via the 5 approved commands - no further manual round-trips for
those two specific operations. Everything outside that exact boundary
(anything destructive, any networking/security/system-configuration
change, package installs, physical hardware) still stops for the
operator, unchanged from every prior stage.

## Offline Utility Library - Stage 6: Local Information

**Decision date:** 2026-09-01.

**Scope:** new `/utility/local/` page (no Stage 1 placeholder existed for
this - it was scoped as part of Stage 1's "Maps" placeholder originally,
now split out per the operator's staged plan). No networking/security-
boundary/Emergency-Mode-state changes; no packages installed. Layered on
Stage 5 (`99049d8`/`66aed5d`).

**One config file, not a searchable dataset:** `data/utility/local/info.json`
is a single object (region label, emergency management contact, NWS office,
hospitals, shelters, emergency numbers, amateur repeaters, radio notes, map
references, other resources) - not a list of many topics like Stages 2-5,
so this page intentionally does **not** reuse the `radio-entry`/search/chip
UI those pages share. Instead it's a plain, section-by-section reference
sheet (reusing `.help-section`/`table`/`.empty-state`, all pre-existing
classes - zero new CSS this stage). **Relocating this PirateBox to a new
area means editing this one JSON file - no PHP/HTML change required**,
exactly as instructed.

**Deliberately almost entirely empty, per explicit instruction:** every
array (`hospitals`, `shelters`, `amateur_repeaters`, `map_references`,
`other_resources`) and every named contact (`emergency_management`,
`nws_office`) ships blank - the page shows a plain "None/Not yet added for
this location" message rather than any fabricated placeholder content. The
**only** two pre-filled entries in `emergency_numbers` are 911 and the
National Poison Control number (1-800-222-1222) - both included because
they are universal, not region-specific, and the Poison Control number is
the same one already cited (from the same authoritative source) in Stage
4's First Aid data. Nothing else was invented to make the page look
populated.

**Integration with Emergency and Maps, as instructed:**
- Added to the main `/utility/` landing grid (7th card, between Maps and
  Library) - the only edit to that Stage 1 page this stage.
- Added a "Local Information" link to both `/utility/emergency/`'s and
  `/utility/maps/`'s existing `hero-actions` link rows.
- Corrected the Maps card's Stage 1 description text (it previously said
  "plus local emergency contacts," which became inaccurate once Local Info
  became its own section) to describe what Maps actually contains now.
- **Deliberately NOT added** to Emergency Mode's 8-card landing grid in
  root `index.php` (confirmed unchanged - still exactly 8 cards) - that
  grid's priority ordering is explicitly Stage 9's job to revisit
  holistically, not something to touch piecemeal each stage.

**Testing performed:** JSON validated (build-time + live); `php -l` clean
on all 4 touched files; rendered via PHP CLI pre-deploy (6 empty-state
sections, universal emergency-numbers table confirmed); live regression
sweep of every existing page unaffected; live checks confirmed the new
card, both cross-links, and the 911/Poison-Control table all render
correctly on the deployed site; live Normal vs. Emergency Mode content
byte-diff - **identical**; confirmed the Emergency-Mode root landing grid
is unchanged (still 8 cards); `nginx`/`php8.4-fpm`/`hostapd`/`dnsmasq`
active throughout, no restarts; error logs clean across the full testing
window. Live mode restored to explicit Normal before finishing.

**Backup:** `~/piratebox-backups/localinfo-stage6-pre-20260901-062636/`
(full `var/www/html` mirror + pre-change git HEAD `66aed5d`).

## Offline Utility Library - Stage 5: Maps / Location Framework

**Decision date:** 2026-09-01.

**Scope:** builds out `/utility/maps/` (a Stage 1 placeholder). No
networking/security-boundary/Emergency-Mode-state changes; no packages
installed; **no map data downloaded** (per explicit instruction). Layered
on Stage 4 (`58cd348`/`1411569`).

**Two independent halves on one page:**
1. **Reference section** (real content, works today): 5 topics on
   coordinates/GPS/navigation - Latitude & Longitude Basics, Coordinate
   Formats (DD/DMS/UTM/MGRS), How GPS Works Without Internet, Cardinal
   Directions & Compass Bearings, and Basic Offline Navigation Concepts.
   Sourced from USGS (coordinate formats) and NOAA/NCEI (magnetic
   declination); GPS mechanics cross-checked against general technical
   references (marked `confidence: medium` - no single authoritative page
   fetch succeeded this session for that specific topic, see Testing).
2. **Map catalog framework** (deliberately empty): a data-driven catalog
   (`data/utility/maps/catalog.json`) ready to list local/regional/
   evacuation/topographic/trail maps, each entry pointing at a static
   image/PDF file under `public/utility/maps/files/`. **Shipped as an
   empty array, on purpose** - no placeholder/fabricated map entries,
   consistent with the same "don't invent content to make a page look
   populated" principle that will also govern Stage 6's local-info dataset.
   The page's own empty-state message and an in-page "Adding a Map" note
   explain exactly how to add a real one later: drop the file in
   `public/utility/maps/files/`, add one JSON entry - no PHP editing
   required, mirroring the "clean metadata structure" the operator asked
   for.

**Why static files under webroot, not an outside-webroot design like
Library will use:** map images/PDFs aren't sensitive or copyright-risky
the way Stage 7's document library payload might be - they're reference
images. Keeping them in `public/utility/maps/files/` (same pattern as the
existing `public/uploads/`) needed zero `open_basedir` change and is
simpler; Stage 7 will make its own outside-webroot call deliberately, with
its own stop-and-explain if that needs an `open_basedir` change (per
instruction).

**Future offline slippy-map viewer - documented, not built:** the page
itself carries a short note (styled like Stage 1's other placeholder
notes) explaining the tradeoff: a real pan/zoom map viewer would need a
self-hosted JS mapping library (e.g. Leaflet - no CDN) plus locally-stored
map tiles (tens of MB to multiple GB depending on area/zoom coverage) -
explicitly flagged as a future, deliberate decision once real map data is
chosen, not something to default into. Static images/PDFs via the catalog
above work today with zero extra dependency.

**Testing performed:** all 3 JSON files validated (build-time + live);
`php -l` clean; rendered via PHP CLI pre-deploy (5 reference entries,
empty-state and future-viewer notes both confirmed present); live
regression sweep of every existing page unaffected; representative search
queries (`gps`, `utm`, `compass`, `coordinate`, `dead reckoning`) all
resolve correctly against live data; live empty-state and future-viewer
note confirmed rendering on the deployed page; live Normal vs. Emergency
Mode content byte-diff - **identical**; `nginx`/`php8.4-fpm`/`hostapd`/
`dnsmasq` active throughout, no restarts; error logs clean across the full
testing window. Live mode restored to explicit Normal before finishing.

**Backup:** `~/piratebox-backups/maps-stage5-pre-20260901-061942/` (full
`var/www/html` mirror + pre-change git HEAD `1411569`).

## Offline Utility Library - Stage 4: First Aid Reference

**Decision date:** 2026-09-01.

**Scope:** builds out `/utility/firstaid/` (a Stage 1 placeholder). HIGH-
STAKES CONTENT - see "Conservative-content decisions" below. No networking/
security-boundary/Emergency-Mode-state changes; no packages installed.
Layered on Stage 3 (`8cdfb28`/`9fc41c5`).

**Data:** 16 topics + 21 sources (~24KB) in `data/utility/firstaid/`,
sourced almost entirely from the **American Red Cross**'s own published
first-aid learning pages, plus CDC (concussion signs) and Ready.gov (heat/
cold - shared sourcing with Stage 3, first-aid-framed here). Same UI/data
pattern as Stages 2-3 (reused `radio-*` CSS/JS, `source_id`/`confidence`/
`source_note` provenance).

**Conservative-content decisions (per explicit instruction - this is high-
stakes material):**
- Every topic is **overview-level**: recognize the signs, take the
  immediate safe action, know when to call 911 - never a substitute for
  training or a diagnosis engine. No topic tells a reader to determine what
  condition someone has; every topic tells them what to watch for and when
  to escalate to a professional.
- **CPR/AED** got the most deliberate restraint: it states the well-known
  public-facing summary ("push hard and fast, about 100-120/min," "use an
  AED, it will guide you") because that phrasing is itself the standard
  Red-Cross/AHA public-education message, not an invented detail - but it
  deliberately does NOT attempt full compression-depth/hand-placement/
  breath-timing choreography, and carries its own explicit
  `training_note` field (rendered prominently on the page) stating that
  hands-on certified training is strongly recommended and this is a
  summary of what CPR involves, not a substitute for practicing it.
- A page-level disclaimer (styled with the existing `.help-note` component,
  not new alarm chrome) states plainly, before any topic content: this is
  not a substitute for professional care or training, call 911 for
  anything life-threatening, and any skill genuinely requiring practice is
  flagged explicitly.
- Nothing was invented: every quick-action bullet traces to specific
  language found in the cited Red Cross/CDC source this session (see
  Testing below - `ready.gov`/Red Cross pages also blocked direct
  automated fetch (403) same as Stages 2-3, so content was gathered via
  targeted search against `redcross.org`/`cdc.gov` domains specifically,
  not general web results).
- Two entries marked `confidence: medium` rather than high: **Minor Wounds**
  (the specific Red Cross page was identified but not individually
  re-verified line-by-line this session - the underlying practice is
  extremely well-established/uncontroversial across every source) and the
  **First-Aid Kit** reference (Red Cross publishes several activity-
  specific checklists rather than one canonical list; this entry is a
  synthesis of their commonly-recommended core contents, flagged as such).
- Deliberately excluded, per instruction: dosing/medication guidance beyond
  "use your own prescribed epinephrine auto-injector," any procedure
  requiring visual diagnosis (e.g. distinguishing burn/fracture severity
  precisely), and anything that reads as replacing professional judgment
  rather than bridging the gap until it's available.

**Testing performed:** JSON validated (build-time + live); `php -l` clean;
rendered via PHP CLI pre-deploy (16 entries, 5 sections, disclaimer and the
one `training_note` both confirmed present); live regression sweep of
every existing page unaffected; representative search queries (`bleeding`,
`choking`, `burn`, `cpr`, `poison`, `allergic`, `hypothermia`, `seizure`,
`snake`) all resolve to the correct single entry live; live disclaimer/
training-note rendering confirmed on the deployed page; live Normal vs.
Emergency Mode content byte-diff - **identical**; `nginx`/`php8.4-fpm`/
`hostapd`/`dnsmasq` active throughout, no restarts; error logs clean
across the full testing window. Live mode restored to explicit Normal
before finishing.

**Backup:** `~/piratebox-backups/firstaid-stage4-pre-20260901-061123/`
(full `var/www/html` mirror + pre-change git HEAD `9fc41c5`).

## Offline Utility Library - Stage 3: Emergency / Outage Reference

**Decision date:** 2026-09-01.

**Scope:** builds out `/utility/emergency/` (a Stage 1 placeholder) into a
skimmable, card-based practical reference. No networking/security-boundary/
Emergency-Mode-state changes; no packages installed. Layered on Stage 2
Radio Reference (`1ead465`).

**Deliberate UI/CSS/JS reuse - not duplication:** this page reuses the
*exact same* CSS classes and JS element IDs Stage 2 introduced for Radio
(`#radioSearch`, `#radioChips`, `.radio-entry`, `.radio-chip`, `.radio-group`,
`data-group-section`, etc.), rather than inventing a second parallel
"searchable card list" component. Since each Utility page is its own
separate document (never loaded alongside another), reusing the same
element IDs across pages is safe and required **zero changes** to the
already-tested `scripts.js` filter logic - it works on this page unmodified.
One new small CSS rule was added (`.ref-quick-actions`, a bullet list style)
since Emergency topics needed a "quick actions" list that Radio's schema
didn't have. This "shared reference-list component, `radio-*`-named but
domain-generic" pattern is intended to be reused again for First Aid,
Maps, and Library in later stages - noting it here once rather than
repeating the rationale in every subsequent stage's entry.

**Data:** 21 topics across 5 groups (Severe Weather & Hazards; Power,
Utilities & Home Safety; Water, Food & Sanitation; Planning &
Communication; Pets) in `data/utility/emergency/topics.json`, plus
`sources.json` (23 sources - primarily Ready.gov/FEMA, CDC, NOAA/NWS, and
NFPA). ~27KB total. Each topic has a one-line `summary`, a short
`quick_actions` bullet list (the primary skimmable content), an optional
`more_info` paragraph, and the same `source_id`/`confidence`/`source_note`
provenance fields Stage 2 established.

**Calm-not-alarmist design, per explicit instruction:** no red/danger
styling, no severity icons, no "WARNING" chrome. Priority is conveyed
structurally instead - hazards needing an immediate physical action
(tornado, earthquake, downed lines, CO) are grouped together and lead with
a one-line action-oriented `summary`, but visually use the same calm
card style as every other topic. The intro paragraph explicitly tells
readers to follow official local instructions over this reference.

**Data-quality notes:**
- Most topics (19/21) are `confidence: high`, sourced directly from
  Ready.gov/FEMA, CDC, NOAA/NWS, or NFPA topic pages - `ready.gov` also
  blocked direct automated fetch (403) this session same as FCC did in
  Stage 2, so content was gathered via targeted web search against these
  same official domains rather than a raw page fetch; multiple independent
  official sources were cross-referenced per topic where practical.
- **Downed power lines** (`confidence: medium`): no single federal
  Ready.gov-equivalent page was identified this session; guidance was
  consistent word-for-word in substance across multiple independent state
  utility-commission/electric-utility consumer-safety sources, which is
  why it's marked medium rather than low.
- **Sanitation without running water** (`confidence: medium`): the general
  need and health rationale are CDC-sourced, but specific low-tech
  practices (e.g. the "twin bucket" toilet method) were cross-checked via
  secondary sources this session, not fetched directly from the CDC page
  cited - flagged in `source_note` accordingly.
- **Communications outages** and **battery/power conservation** are marked
  `source_id: general-prep-education` (no single regulatory/agency
  citation - practical synthesis, consistent with how Stage 2 handled
  general RF-education content). The communications-outage topic
  deliberately cross-references this PirateBox itself as a working offline
  fallback.
- **Known gap, deliberately deferred:** hurricanes/broad "severe storm"
  guidance beyond thunderstorms/lightning was not given its own topic this
  stage (searching "hurricane" currently returns no results) - not a
  defect, a scope/completeness tradeoff made to avoid rushing a distinct
  research pass late in an already-large stage, consistent with the
  operator's "accuracy over completeness" instruction. Good candidate for
  a future small addition using the same Ready.gov/NOAA sourcing pattern.

**Testing performed:** JSON validated (build-time and post-deploy from the
live path); `php -l` clean; rendered via PHP CLI directly pre-deploy (21
entries, 5 sections, 19 source links, zero warnings); live regression sweep
of every existing page unaffected; simulated the live search/filter logic
in Python against deployed data for representative queries (`generator`,
`flood`, `water`, `evacuat*` all resolve correctly; `bleeding`/`hurricane`
correctly return nothing - First Aid and the noted gap, respectively, not
bugs); live Normal vs. Emergency Mode content byte-diff - **identical**,
confirming zero content duplication; `nginx`/`php8.4-fpm`/`hostapd`/
`dnsmasq` all remained active throughout with no restarts; error logs
reviewed across the full testing window - zero new entries. Live mode
restored to explicit Normal before finishing.

**Backup:** `~/piratebox-backups/emergency-ref-stage3-pre-20260901-060133/`
(full `var/www/html` mirror + pre-change git HEAD `1987f5a`).

## Offline Utility Library - Stage 2: Radio Reference

**Decision date:** 2026-09-01.

**Scope:** builds out `/utility/radio/` (a Stage 1 placeholder) into a real,
locally-searchable reference for a wideband receiver (built with a Malahit
DSP2-style receiver specifically in mind). No networking, hostapd, dnsmasq,
captive-portal, nginx architecture, PHP security restrictions, or the
Emergency Mode state system were touched. Checkpoint: layered directly on
top of the Emergency Mode foundation commit `620c05abd08fc5c4edceddaa2d94a0a56d4ae1fd`.

**Data-driven, not hard-coded:** all frequency/service data lives in 4 JSON
files under `data/utility/radio/` (`services.json`, `modulation.json`,
`guides.json`, `sources.json`) - none of it is hard-coded into
`radio/index.php`, which is pure rendering/filtering logic over whatever
these files contain. Total size: ~49KB across all 4 files - loads instantly,
no pagination needed. 25 top-level service entries (14 individual amateur
bands, AM/FM/shortwave broadcast, NOAA Weather Radio, CB, FRS, GMRS, MURS,
Marine VHF, Airband, Railroad), several with nested `channels` arrays
(NOAA's 7, CB's 40, FRS's 22, MURS's 5, Marine's 12 key channels, shortwave's
14 meter bands) so the page shows one card per *service* rather than one row
per individual channel. Plus 6 modulation-type glossary entries (AM/FM/WFM/
USB/LSB/CW) and 6 practical guide entries (RF spectrum overview, HF/VHF/UHF
explained, HF propagation basics, antenna guidance, receiver practical tips,
and a cross-service "what to monitor during severe weather/an emergency"
quick reference).

**Every record carries source/confidence/provenance**, per the operator's
explicit requirement: `source_id` (pointing into `sources.json`, which
records publisher, URL, and retrieval date), `confidence` (`high`/`medium`/
`low`), and a free-text `source_note` used especially where a regulator and
a voluntary band-plan source are combined, where a secondary source was
used only as a cross-check, or where regional/local assignments vary. See
"Data-quality methodology" below for how confidence was assigned.

**Receive vs. transmit is a field on every record, not just page text:**
each service entry carries `license_required_to_transmit` (bool) and a
plain-language `transmit_note`, rendered as a distinct colored badge
("License required to transmit" / "No license required to transmit") right
in the summary line, plus the full note in the expanded detail. The page's
intro paragraph states plainly that owning a receiver does not authorize
transmitting anywhere on the page. No entry implies otherwise.

**Data-quality methodology (this session, 2026-09-01):**
- `weather.gov/nwr` and `navcen.uscg.gov` (NOAA Weather Radio, Marine VHF)
  were fetched directly and successfully - marked `confidence: high`.
- FCC's own pages (eCFR and consumer-guide URLs for Part 97 amateur bands,
  Part 95 FRS/GMRS/MURS/CB, and the AM/FM broadcast pages) returned
  **HTTP 403 to every automated fetch attempt this session**. Those figures
  were instead cross-checked against Wikipedia's own sourced tables (which
  themselves cite the same CFR parts) and, for CB/MURS/AM/FM specifically,
  against multiple independent secondary sources that agreed exactly -
  marked `confidence: medium` (amateur bands, shortwave meter bands, FRS,
  GMRS, airband) or `confidence: high` (CB, MURS, AM/FM broadcast, where
  independent sources were unanimous and the allocation is long-stable).
  **Wikipedia is never recorded as the source-of-record in the shipped
  data** - every entry's `source_id` points at the primary regulator
  (FCC/NOAA/USCG/ITU); the cross-check methodology is disclosed in
  `source_note` instead.
- The 60m amateur band is separately flagged `confidence: medium` for a
  different reason: its rules were cross-checked as having changed as
  recently as December 2025, so it's called out as more likely to be
  out of date than the other amateur bands.
- **Railroad radio is deliberately conservative**, per explicit operator
  approval: three independent sources gave three different lower band-edge
  figures (159.57 / 159.810 / 160.110 MHz) and no single authoritative
  public channel table was found. The `railroad` entry ships with only the
  approximate range, a description of how the AAR channel system works,
  and practical receive guidance - **no specific numbered channel table** -
  marked `confidence: low` with the discrepancy documented in
  `source_note`. A future update can tighten this if a clean primary source
  is found.
- After research, this session's Pi had live outbound internet (confirmed:
  `curl https://www.google.com` returned `200`), which was used only to
  verify every citation URL in `sources.json` actually resolves (all 8
  returned `200`) - not to change what ships. The finished page requires no
  internet at all to use.

**Page design:** server-rendered (every entry is real HTML from PHP, not
injected by JS - confirmed by rendering the page via `php` CLI directly),
using native `<details>/<summary>` for expand/collapse so full detail
(nested channel tables, transmit note, source citation) is reachable with
JavaScript entirely off - only the live text-search and category-chip
filtering are JS-only, added to `assets/scripts.js` as one more guarded
block following the file's existing pattern (same technique as the
pre-existing file-list search). A small hand-authored inline SVG
(`spectrum.svg.php`, log-scale, 0.5 MHz-3 GHz) gives a quick visual
band-position reference - static markup, no charting library. All new CSS
(~220 lines) reuses the existing dark/purple palette and component
language (card backgrounds, accent borders, uppercase badges) rather than
introducing a new visual style.

**Shared with Emergency Mode, not duplicated:** `radio/index.php`
deliberately never calls `piratebox_get_mode()` or touches `includes/
mode.php` - confirmed live by fetching the page in both modes and
byte-diffing the `.radio-page` content: **identical in both**, 37
`<details>` entries either way. Only the site-wide navbar/banner (rendered
by the unmodified `includes/navbar.php` from Stage 2's earlier phase)
differs between modes, exactly as designed.

**Testing performed:**
- All 4 JSON files validated (`json.load` in Python) after generation and
  again post-deploy from the live path.
- `php -l` on `radio/index.php` and `spectrum.svg.php` - clean.
- Rendered `radio/index.php` via the PHP CLI directly (not just through
  nginx) to catch template bugs early - this caught and fixed a real bug:
  the channel-table column list was being built from only the *first* row
  of each service's `channels` array, silently dropping CB channel 23's
  extra `note` field (documenting a real, intentional historical CB
  channel-numbering quirk) since no other CB channel has that field. Fixed
  to take the union of keys across all rows; verified the note now renders
  and that rows without it still get a correctly-aligned empty cell.
- Live, in both Normal and Emergency Mode: full site status sweep (all
  existing pages, `/admin/` still `401`, all `/utility/...` pages, captive-
  portal probes) - zero regressions. A live CSRF-authenticated **file
  upload** (first real end-to-end upload test since Stage 1) and a live
  **chat POST** (since `scripts.js` changed) both succeeded.
- Simulated the exact client-side search/filter logic in Python against the
  live deployed JSON for all 9 required queries (`NOAA`, `2 meter`, `40m`,
  `airband`, `GMRS`, `FRS`, `marine`, `CB`, `shortwave`) - every one
  resolved to the correct entry. Noted, not fixed: plain substring matching
  means `"2 meter"` also incidentally matches `"12 Meter Band"` (a substring
  of "1**2 meter**") - harmless (both are genuine radio bands, the correct
  entry is always present), consistent with the existing file-list search's
  same plain-substring approach, not worth added complexity for this stage.
- All 8 unique source citation URLs in `sources.json` verified live to
  return HTTP `200`.
- nginx/php-fpm error logs reviewed across the full testing window: zero
  new errors - all matches are pre-existing historical entries from earlier
  phases (confirmed by timestamp).
- `nginx`, `php8.4-fpm`, `hostapd`, `dnsmasq` remained `active` throughout
  with no restarts. Final live mode restored to explicit Normal before
  finishing.

**Backup:** `~/piratebox-backups/radio-reference-phase1-pre-20260901-053341/`
(full `var/www/html` mirror + recorded pre-change git HEAD `620c05a`),
created before any edit in this phase.

**Known residual test data:** one more live chat entry
(`[Automated Stage 2 Radio Reference regression - safe to delete via
/admin/]`) and one uploaded file (`stage2-upload-test.txt`) from this
phase's live regression testing - not cleared automatically (no admin
credentials available to this assistant); both clearable via `/admin/`.

**Deliberately deferred:** Emergency, First Aid, Maps, Library, and Global
Search sections remain Stage-1 placeholders - out of scope for this stage
per explicit instructions. `poppler-utils`/PDF text extraction was not
installed (not needed - this stage has no PDFs). GPIO, SSID switching, and
the OLED/button hardware remain untouched, as in the prior phase.

## Emergency Mode: software presentation-mode foundation (no GPIO yet)

**Decision date:** 2026-09-01.

**Scope:** additive, presentation-layer only. No networking, hostapd,
dnsmasq/DHCP/DNS, captive-portal, nginx architecture, PHP security
restrictions (`open_basedir`/`disable_functions`), or existing application
logic (`upload.php`, `chat.php`, `messages.php`, `admin/index.php`) changed.
No GPIO access, no OLED display, no momentary-button handling, no SSID
change, and hostapd was never touched or restarted this phase - all
explicitly deferred, per the operator's own instructions, to a later phase
once the ordered hardware (MTS-101 toggle switch, SSD1306 OLED, momentary
buttons) actually arrives. Checkpoint: this phase starts from and is layered
directly on top of the Stage 1 commit `e428b578bf1bd25c7faf1c10980a4bfc8c001e8c`,
kept as the known-good pre-Emergency-Mode reference point.

**Concept:** the site now has two presentation modes, Normal and Emergency,
selected by a single piece of trusted state. Radio/Emergency/Maps/First
Aid/Library/Search/Files/Chat/Guestbook content is **not duplicated** between
modes - every page under `/utility/...` and every existing PirateBox page is
byte-identical regardless of mode (confirmed live - none of them even
reference the mode system). Only three things change with mode: the
homepage's landing content, the navbar's link order, and (site-wide) whether
a small "Emergency Mode" banner is shown. Eventually mode will also
determine the Wi-Fi SSID (not implemented this phase - see below).

**Where mode state lives:** `/tmp/piratebox/mode` - a single-line plain-text
file containing exactly the word `normal` or `emergency`, nothing else (no
JSON). Chosen over the JSON `status.json` pattern used elsewhere in this
project because a single enum value doesn't need JSON's structure, and
plain text has exactly one way to be malformed instead of a whole parser's
worth - simpler and more robust, matching the operator's explicit
"simple and robust" requirement for this subsystem.

**Why `/tmp` and not `/run/piratebox/` (which is what an earlier planning
discussion for this feature proposed):** the operator's safety list for this
phase explicitly said not to change "PHP security restrictions." `/tmp` is
already fully inside `open_basedir` (it has been since before this project's
Phase 1), so reading a file there required **zero** `php.ini`/`open_basedir`
edit. `/run/piratebox/mode.json` would have needed a new `open_basedir`
entry, same as `status.json` got in Phase 4 - a reasonable change in
general, but not one this phase's explicit instructions permitted, so the
design was adjusted to avoid it rather than doing it anyway. Both paths are
tmpfs, so the reboot-reset behavior below is identical either way; this can
be revisited when the real GPIO daemon is built, if there's a reason to
prefer `/run`.

**Why tmpfs specifically:** a fresh boot always starts with **no state file
present**, which resolves to the safe Normal fallback - by construction, not
by a special case that has to be remembered and kept correct. This also
matches the operator's stated requirement that the physical switch (once
wired) should be read fresh at every boot rather than trusting a persisted
last-known value from the SD card.

**How PHP reads it:** one new function, `piratebox_get_mode()` in the new
`includes/mode.php` (not `helpers.php`, which is documented as pure
formatting helpers - mode detection is a distinct concern and was given its
own small file so it stays the one obvious place this logic lives). Reads
the state file, trims/lowercases it, and returns the literal string
`'emergency'` only on an exact match; **every other outcome - file missing,
empty, unreadable, garbage content - returns `'normal'`.** The function
cannot throw and never returns a third "unknown" value. Verified against all
of these cases both as a direct unit-level check (`php -r` against the
deployed file, all 7 cases: missing dir, empty file, garbage content,
explicit `normal`, explicit `emergency`, mixed-case/whitespace `emergency`,
and `chmod 000`-unreadable) and live, end-to-end, against the actual
deployed site (missing-file case - the site's default state before this
phase's testing began, invalid-content case). Every one correctly resolved
to the expected mode.

**www-data/PHP never writes this file, ever, and there is deliberately no
web-reachable way to change mode.** Mode changes only come from a trusted,
privileged, out-of-band actor: today that's an operator running
`set_piratebox_mode.sh` by hand with `sudo`; later it will be a root-owned
GPIO daemon. This preserves the same "web tier can only read, a separate
privileged helper does anything sensitive" boundary this project has used
since the Phase 4 admin/status page.

**`set_piratebox_mode.sh`** (repo root, not yet installed to
`/usr/local/bin` - can be run directly from the repo path with `sudo`):
manual stand-in for the not-yet-installed MTS-101 toggle switch. Takes
`normal`, `emergency`, or `status`; refuses to run as non-root for
`normal`/`emergency` (mode changes are a trusted operation, matching the "no
public unauthenticated way to change mode" requirement even for this manual
tool); writes atomically (temp file in the same tmpfs directory, then
`rename()`) so a concurrent PHP request never observes a half-written file.
Deliberately built to be the same write path a future GPIO daemon will use -
proving out this script now means the daemon inherits already-tested
behavior rather than needing its own from-scratch verification of the state
file mechanics.

**Landing page (`index.php`) in Emergency Mode:** per the operator's
explicit instruction ("do not merely add a banner to the normal Files-first
page... someone who has never heard of PirateBox should connect and
immediately understand what this network is"), the root URL genuinely
changes what renders first - an emergency-framed hero ("Local Emergency
Information Network... designed to run on battery power... Internet access
is not required or provided...") followed by an 8-card grid (Emergency
Info, Radio, Maps, First Aid, Messages/Chat, Files, Search, Library, in that
order) using the exact `.utility-grid`/`.utility-card` component Stage 1
already built for `/utility/`'s own landing page - zero new CSS needed for
this part. The existing Files/Upload/file-list block - **completely
unchanged code**, not a copy - still renders on the same page immediately
below, now anchored `id="files"` so the grid's "Files" card can jump
straight to it, with its own heading demoted from `<h1>` to `<h2>` in
Emergency Mode only (correct HTML semantics with two hero sections on one
page; same text either way). In Normal Mode `index.php`'s output is
byte-for-byte what Stage 1 already produced - confirmed live.

**Navbar (`includes/navbar.php`):** same six links/targets in both modes -
only the order changes. Normal: Files, Upload, Chat, Guestbook, Help,
Utility (unchanged from Stage 1). Emergency: Utility, Chat, Files,
Guestbook, Help, Upload. Implemented as a small ordered-key array picked by
mode and rendered via one `foreach`, rather than two hard-coded `<li>`
blocks, so adding a mode or changing an order later is a one-line change.
Labels/hrefs deliberately left unchanged between modes (considered
relabeling "Utility" to "Emergency" in the navbar, rejected: it would then
point somewhere different from the landing page's separate "Emergency Info"
card, which links to `/utility/emergency/` specifically - keeping one
label/target pair everywhere avoids that mismatch).

**Emergency Mode banner:** a small site-wide notice ("Emergency Mode - this
is a local offline network. No Internet access is required or provided.")
rendered by `navbar.php` itself (so every page that includes the navbar
gets it automatically, with zero per-page changes) whenever mode is
Emergency, and rendered nowhere at all in Normal Mode. Reuses the existing
`.help-note` component style (warm amber accent, matching the project's
"informative, not alarming" visual language - not the red/`.status-bad`
styling used for actual faults) plus one small new 2-rule CSS block
(`.mode-banner`) purely for width/centering - confirmed present on `/`,
`/chat.php`, `/messages.php`, `/utility/`, and `/help.php` in Emergency
Mode, and confirmed absent from all of them in Normal Mode. `admin/index.php`
was deliberately left out (it hand-rolls its own nav, is Basic-Auth-gated,
and is an operator/status page rather than part of the public presentation
- not worth the extra touched file for this phase).

**Testing performed (unit-level and live, both directions):**
- `php -l` on every new/changed PHP file - clean.
- Direct unit-level test of `piratebox_get_mode()` against the deployed
  file for all 7 state-file conditions listed above - all correct.
- **Normal Mode** (the site's actual state through most of this phase's
  testing, since no state file existed yet): confirmed Files-first landing,
  correct nav order, no emergency hero/grid/banner anywhere, `/admin/` still
  `401`, all `/utility/...` pages still `200`, all 7 captive-portal probe
  paths and the Capport JSON endpoint unchanged, upload form still renders,
  and a **live CSRF-authenticated guestbook POST** accepted and visible on
  refetch (proving the write path still works through the modified
  `navbar.php`).
- **Emergency Mode** (operator ran `sudo set_piratebox_mode.sh emergency`):
  confirmed the emergency hero copy, all 8 grid cards resolving to their
  correct existing URLs (verified individually, not just that the grid
  exists), the "Also on this network" secondary links (Guestbook/Help/full
  Utility Library), correct reordered nav, the banner present on every page
  checked, `/admin/` still `401`, every existing and `/utility/...` page
  still `200`, captive-portal probes unchanged, and a **live
  CSRF-authenticated chat POST** accepted and visible on refetch.
- **Content-sharing check:** confirmed none of the files under
  `public/utility/*/index.php` reference `mode.php`/`piratebox_get_mode()`
  at all - they render identically regardless of mode, reached by a
  different nav path only.
- **Live failure-mode checks**, run against the actual deployed site (not
  just simulated): operator wrote invalid content
  (`echo not-a-real-mode > /tmp/piratebox/mode`) - site correctly rendered
  full Normal presentation, `/admin/` still gated. The state file not
  existing at all was also exercised live for real, since that was the
  site's actual condition before the first `set_piratebox_mode.sh` call
  this phase.
- `nginx`/`php8.4-fpm` error logs reviewed across the entire testing window
  (spanning both mode switches and all live POSTs): zero new errors: the
  only matches are pre-existing historical entries from earlier phases
  (confirmed by timestamp, well before this phase's testing began).
- `nginx`, `php8.4-fpm`, `hostapd`, `dnsmasq` all remained `active`
  throughout, with no restarts - expected, since nothing in this phase
  touches any of those services. Final state was explicitly restored to
  Normal Mode (`sudo set_piratebox_mode.sh normal`) before finishing.

**Backup:** `~/piratebox-backups/emergency-mode-phase1-pre-20260901-052052/`
(full `var/www/html` mirror + recorded pre-change git HEAD `e428b57`),
created before any edit in this phase.

**Known residual test data:** this phase's live write-path tests left two
more clearly-labeled entries in `data/chat.json`/`data/messages.json`
(`[Automated Emergency Mode Stage regression - ... - safe to delete via
/admin/]`), in addition to the two left by Stage 1's testing. Same as
before: not cleared automatically (no admin credentials available to this
assistant); clear via `/admin/` if desired.

**Deliberately deferred to a later phase** (per the operator's explicit
instructions - none of this exists yet):
- Actual GPIO access / the MTS-101 toggle switch. `set_piratebox_mode.sh`
  is the interim stand-in and is intended to be directly replaceable by a
  future root-owned GPIO daemon that writes the same state file with the
  same atomic-write technique.
- SSID switching. hostapd/`hostapd.conf` were not touched or restarted this
  phase. No Emergency SSID has been chosen. When this is implemented, the
  design this phase establishes is meant to support it safely: the
  privileged mode-writer (today the script, later the GPIO daemon) is the
  one place that would decide "did the mode actually change," debounce the
  physical switch before acting, and - only on a genuine, stable transition
  - swap in the correct static `hostapd-{normal,emergency}.conf` and
    restart hostapd, never on every poll.
- The SSD1306 OLED display and the five momentary buttons. Neither is
  implemented; no GPIO pins have been assigned to anything. The OLED is
  intended to eventually be a read-only consumer of the same
  `piratebox_get_mode()`-equivalent state, informational only, never
  required for the site to function - consistent with the fallback
  behavior already built and tested this phase.

## Offline Utility Library - Stage 1: scaffolding, landing page, nav link

**Decision date:** 2026-09-01 (Utility Phase 1).

**Scope:** additive only. No networking, hostapd/dnsmasq/DHCP/DNS, captive-portal,
nginx architecture, PHP security restrictions (`open_basedir`/`disable_functions`),
or existing application logic (`upload.php`, `chat.php`, `messages.php`,
`admin/index.php`, `index.php`) changed. This phase adds a new, currently
mostly-empty "Utility" section alongside the existing PirateBox, per the
project's long-term goal of also being an offline reference/utility node
(radio reference, emergency/first-aid reference, maps/local info, a document
library, and offline search) - see the project's own planning notes for the
full multi-stage scope. Stage 1 is scaffolding only: a landing page, one nav
link, and six clean "not built yet" placeholder pages - no radio/emergency/
first-aid/maps/library content or search index yet.

**New files:**
- `public/utility/index.php` - section landing page. Explains up front, before
  anything else, that this is a local/offline network that does not require
  or provide Internet access, then links to six large tap-target cards
  (Radio, Emergency, First Aid, Maps, Library, Search) plus a row of links
  back to the existing Files/Chat/Guestbook/Help pages, so a visitor who
  lands here from either direction never hits a dead end.
- `public/utility/{radio,emergency,firstaid,maps,library,search}/index.php` -
  one clean placeholder page per future section (not broken links, not
  missing pages), each stating plainly that the section isn't built yet and
  what it will eventually contain, with a link back to `/utility/` and to
  Search.
- `data/utility/.gitkeep` - reserves `data/utility/` (parallel to the
  existing `data/` used for `chat.json`/`messages.json`) as the future home
  for the Stage 2+ JSON reference datasets (radio bands, emergency/first-aid
  topics, local info, the generated search index). Empty this phase - no
  data written yet. Sits inside the existing `open_basedir` allowance
  (`/var/www/html`), so no PHP security-restriction change was needed to
  create it.

**Modified files:**
- `includes/navbar.php` - added one `<li>` for "Utility" (`/utility/`) as the
  last item, after Help. Every existing item and its order is unchanged.
  Also changed the logo `<img>` and the Chat/Guestbook/Help links from
  page-relative (`chat.php`) to root-absolute (`/chat.php`) paths. This was
  a required, not cosmetic, fix: `navbar.php` is `require`'d by pages at
  multiple directory depths (site root, and now one level down under
  `/utility/...`), and a page-relative href resolves against the requesting
  page's own URL, not the include's location - so `chat.php` written on a
  page served from `/utility/` would have pointed at the nonexistent
  `/utility/chat.php`. Root-absolute paths resolve identically to the old
  ones for every existing root-level page (`/`, `/chat.php`, etc.) and
  correctly for any future nesting depth. Verified live (see Testing below)
  that every existing nav link and the logo still load correctly after this
  change.
- `includes/footer.php` - same fix, same reason, for the one link it
  contains (`help.php` &rarr; `/help.php`). Footer is `require`'d by
  `index.php`/`help.php`/`messages.php`/the new utility pages (not
  `chat.php`, unchanged Phase 5 decision).
- `public/assets/styles.css` - appended a new block only (`.utility-grid`,
  `.utility-card*`, `.utility-breadcrumb`, `.utility-placeholder-note`); no
  existing rule was edited or removed. Deliberately reuses the existing dark/
  purple palette and the existing `.hero`/`.help-section`/`.help-note`
  components' visual language (card background `#292938`, `#8c8dff` accent
  border/links, uppercase bold labels) rather than introducing a second
  visual style, per the instruction to keep the existing PirateBox look.

**Why a nav link now, not deferred to a later stage:** the operator
explicitly asked for the Utility section to be reachable from the normal
site nav in this stage, not left as an undiscoverable orphan page until
content exists.

**Deployment mechanics:** `/var/www/html` is owned by `www-data`, and this
session has no passwordless `sudo`, so all edits were made in this repo's
`var/www/html` mirror (owned by `moose`) and then deployed to the live path
by the operator directly, via `rsync -a --chown=www-data:www-data`/`cp` run
in their own interactive SSH session (the only place `sudo` could actually
prompt for a password) - not by this assistant. Deployed files were then
byte-diffed against the repo copy to confirm an exact match before any
testing began.

**Explicitly not done this phase (deferred to later stages, per the
operator's own staged plan):** no `poppler-utils`/other new package
installed; no radio/emergency/first-aid/maps content or datasets added; no
document library or its `open_basedir` addition; no search index or search
UI logic - the Search placeholder page is a description of what's coming,
not a working search yet.

**Backup:** `~/piratebox-backups/utility-phase1-pre-20260901-044929/`
(full `var/www/html` mirror + recorded pre-change git HEAD
`74c040e39122c7e3fff20d7f69a4bd478618f684`), created before any edit in this
phase, following the same convention as the Phase 3/4/5 pre-change backups.

**Testing performed (live, after deployment):**
- Byte-diffed every deployed file against the repo copy (exact match) and
  confirmed `www-data:www-data` ownership.
- `php -l` on every new/modified PHP file (no syntax errors).
- HTTP status check across `/`, `/chat.php`, `/messages.php`, `/help.php`,
  `/admin/` (still `401`, unchanged - Basic Auth boundary untouched),
  `/utility/`, and all six placeholder pages (all `200`).
- Confirmed the new `/utility/` link and its target render correctly, and
  that all pre-existing nav links plus `/assets/*` (stylesheet, script,
  logo) still resolve `200` when requested by a browser sitting on a nested
  `/utility/...` page.
- Re-verified all seven captive-portal probe paths
  (`/generate_204`, `/gen_204`, `/hotspot-detect.html`,
  `/library/test/success.html`, `/success.html`, `/connecttest.txt`,
  `/ncsi.txt`) still `302` to `http://10.0.0.1/`, and
  `/.well-known/captive-portal` still returns the same RFC 8908 JSON body -
  all unchanged, as expected, since neither nginx config nor dnsmasq was
  touched.
- **Live write-path test, not just a page load:** posted a real,
  clearly-labeled test message (`[Automated Stage 1 verification post - safe
  to delete via /admin/]`) to both the guestbook and chat via an
  authenticated CSRF-token POST, and confirmed each was accepted and then
  appeared back on re-fetch - proving `chat.php`/`messages.php` still work
  correctly end-to-end through the modified `navbar.php`/`footer.php`
  includes they both `require`. **These two test posts are still live in
  `data/chat.json`/`data/messages.json`** - clear them from `/admin/` if you
  don't want them kept (three independent, confirmation-gated actions exist
  there for exactly this).
- Confirmed the upload form on `/` still renders (`enctype`, `name="file"`,
  max-size attribute) - `upload.php` itself was not touched this phase, so a
  full upload round-trip was not repeated.
- Checked `nginx`/`php8.4-fpm` error logs and `journalctl` for both units
  across the entire testing window: zero new errors correlated with any
  request made during this phase (pre-existing historical log entries from
  earlier phases are unrelated and unchanged).
- Confirmed `nginx`, `php8.4-fpm`, `hostapd`, `dnsmasq` all remained
  `active` throughout with no restarts, and disk free space (`107G`)
  unaffected.

## Wi-Fi adapter notes / planned hardware

**Decision date:** 2026-09-01 (post-Phase 6). Documentation only - no
networking, service, or live configuration change accompanies this entry.

**Current production state:** the PirateBox AP is, and remains, the
Raspberry Pi 3 B+'s **built-in `wlan0`**. Nothing below changes that.

### TP-Link TL-WN722N V2/V3 - tested, not suitable as-is

Tested in Phase 6 (USB ID `2357:010c`, Realtek RTL8188EU chipset, driver
`rtl8xxxu` - the mainline in-tree driver, no DKMS/vendor module
installed). `iw phy1 info` showed only `managed` and `monitor` in
`Supported interface modes` - no `AP`. Confirmed empirically, not just by
reading the capability list: `iw phy1 interface add ... type __ap`
returned **`Operation not supported (-95)` (EOPNOTSUPP)**, rejected at
the kernel/cfg80211 level before ever reaching the driver. This adapter
is **not suitable as the PirateBox AP with the current mainline driver**.

**Do not install an out-of-tree/DKMS RTL8188EU driver** (e.g. a vendor
`8188eu`-family fork with AP support) to work around this unless that
tradeoff - an external, non-mainline kernel module, with its own
maintenance and kernel-upgrade fragility - is deliberately revisited and
approved later. See the full Phase 6 findings (chipset, firmware, power/
undervoltage observations - unrelated to this adapter, see that report)
in git history for this decision's evidence.

### ALFA AWUS036NHA / Atheros AR9271 - considered, not chosen

Has excellent mainline Linux AP support via `ath9k_htc`. Not chosen as
the primary upgrade path because `ath9k_htc`/AR9271 AP-mode operation has
a well-documented firmware limitation of **approximately 7 associated
stations**. This limitation is specific to that candidate adapter's
firmware - **it does not apply to the current PirateBox `wlan0`** (the
Pi's built-in Broadcom chip), which has no such constraint.

### Ordered: ALFA AWUS036ACM (MediaTek MT7612U) - not yet tested

Hardware has been ordered for a future primary-AP upgrade attempt:
- Chipset: MediaTek MT7612U
- Dual-band 2.4/5 GHz, 2x2 MIMO, two detachable RP-SMA antennas
- Expected driver: mainline `mt76x2u` (**expected**, not yet verified -
  this hardware has NOT arrived or been tested on this Pi as of this
  entry)
- Intended future role: primary PirateBox USB AP, **if and only if**
  testing succeeds
- The AR9271's ~7-station firmware limitation above does **not** apply to
  the MT7612U/AWUS036ACM - different chipset, different firmware/driver
  stack entirely. Conversely, **no maximum client count is claimed for
  the AWUS036ACM here** - that has not been tested or researched yet, and
  should not be assumed until it is.

**Future test plan, when the AWUS036ACM arrives** (same discipline as
Phase 6 - read-only discovery first, no changes to the working `wlan0`
PirateBox until proven):
1. Identify USB VID:PID and chipset.
2. Confirm the loaded kernel driver.
3. Check `iw` `Supported interface modes` for `AP` (and, per the Phase 6
   lesson, confirm empirically with a real `iw ... type __ap` attempt,
   not just by reading the capability list).
4. Check power/USB stability (`vcgencmd get_throttled`, dmesg for resets/
   disconnects, distinguishing sticky/historical bits from active
   ones - see Phase 6 for the method).
5. Create an isolated, temporary `PirateBox-USB-Test` AP (not `10.0.0.1`,
   not colliding with the production DHCP server, not the production
   SSID).
6. Test real client association and stability while `wlan0` remains
   operational throughout.
7. Only after successful testing, consider migrating the production
   PirateBox AP from `wlan0` to the ALFA - a deliberate, separate,
   approved step, not an automatic consequence of a successful test.
8. Establish a stock-antenna range baseline before changing antennas.

## Phase 5: onboarding/UI redesign, help page, and QR codes

**Decision date:** 2026-09-01 (Phase 5).

**Scope:** front-end/UX only, per the phase's own instructions - no
networking, captive-portal, or backend architecture changes. Builds on
the existing dark/purple/sharp-corners visual identity from earlier
phases rather than replacing it.

**New pages/includes:**
- `includes/footer.php` - a small shared footer (not used on `chat.php`,
  see below) repeating the "this network is offline, no Internet
  required" message and the direct `http://10.0.0.1/` fallback, so it's
  discoverable without hunting for it, but not repeated on every single
  element of every page.
- `includes/helpers.php` - `piratebox_fmt_bytes()`/`piratebox_fmt_duration()`,
  pulled out of `admin/index.php` (which had its own private copy) once
  `index.php`'s file listing also needed human-readable byte formatting -
  now there's one shared copy instead of a second one.
- `public/help.php` - Connect steps, an Android/Samsung-specific note,
  generic Apple/Windows/Linux guidance, a short "using PirateBox" summary,
  and an About section. Content was written to the phase's exact
  constraints: it does **not** tell users to install a certificate,
  disable browser security, or click through an HTTPS warning to use
  PirateBox (there is no HTTPS on this device to warn about in the first
  place - see the Phase 3 captive-portal entries below), and it does
  **not** claim anonymity - it explicitly states "offline does not
  automatically mean anonymous," matching this device's actual behavior
  (it can see connected devices and their requests, like any local
  network).
- `index.php` gained a hero/intro block ("PirateBox - Offline File
  Sharing" + a one-sentence explanation + quick links) so a first-time
  visitor understands what this is and what they can do, without needing
  the Help page.

**Footer NOT added to `chat.php`:** that page uses a fixed-height,
`overflow: hidden` flex layout (message list scrolls internally, input
bar pinned to the bottom - a deliberate mobile chat UX pattern from
before this phase). Appending a footer there would either get clipped or
break that layout. Chat already has full nav access to Help, so nothing
is lost.

**QR codes:** generated at *install/deploy time* by the installer via
`qrencode` (added to the `apt-get install` line - a tiny, standard CLI
tool, not a PHP/runtime dependency), not committed to git (they're a
rendering of two static strings - `http://10.0.0.1/` and
`WIFI:T:nopass;S:PirateBox;;`, matching this device's fixed IP and open
`PirateBox` SSID - the installer already knows both, so there's nothing
gained by committing a rendered PNG that's trivially regenerable and
would need to be kept in sync by hand). Both live on the Help page,
visually distinguished by caption so scanning either one is unambiguous:
the URL QR to jump straight to PirateBox once already connected, the
Wi-Fi QR to join the network in the first place. Decoded with `zbarimg`
(a temporary verification tool, installed, used once, then `apt purge`d
+ `autoremove`d again - not left on the Pi) to confirm each PNG actually
encodes the exact intended string - both did.

**File list sorting:** a `<select>` (Newest/Oldest/Name/Size) plus
clickable/keyboard-activatable column headers, implemented as pure
client-side re-ordering of the already-rendered `<tr>` elements from
`data-*` attributes already on each row - no extra request, no server
round-trip, and the table is already correctly newest-first sorted by PHP
even if this JS never runs at all (progressive enhancement, not a
requirement).

**Progressive enhancement / JS-optional baseline:** timestamps
(`file-timestamp`/`chat-timestamp`/`message-time` spans) now render a
server-side `date('Y-m-d H:i', ...)` fallback string in PHP, which JS
then upgrades to a locale-formatted version via `Intl.DateTimeFormat` on
load - previously these spans were emptied and populated by JS alone, so
a no-JS visitor saw blank timestamps everywhere. Upload still requires JS
for the progress bar specifically (explicitly acceptable per this phase's
own instructions - "except features inherently requiring JS"), but file
Browse/download, chat/guestbook reading, and navigation all work with
JS disabled.

**Admin page:** visually reorganized into two clearly distinct zones -
"System status" (labeled `read-only`) and "Destructive maintenance"
(labeled `irreversible`, dashed red border) - with no change whatsoever
to the Phase 4 security/privilege model: same nginx Basic Auth boundary,
same CSRF token, same confirmation-checkbox requirement, same
`flock()`-based locking, no sudo, no exec, no reboot/service-restart
controls added.

**Offline-resource audit:** every served page (`/`, `help.php`,
`chat.php`, `messages.php`, `admin/`) plus `styles.css` and `scripts.js`
were fetched live and grepped for any `http(s)://` reference other than
`10.0.0.1` itself, and for `@import`/`url()` in CSS - none found anywhere.
The only network calls `scripts.js` ever makes are `fetch()` to this same
site's own `chat.php`/`messages.php` endpoints.

**Deferred / explicitly out of scope for this phase** (per instructions,
not oversights): file thumbnails, chunked/resumable uploads, WebSockets,
accounts/avatars, reboot/service-restart buttons, any further
captive-portal work, and the TP-Link adapter.

**Real-device testing status:** the operator did a quick real-device pass
and confirmed the redesigned UI looks good, but explicitly deferred the
full manual checklist (desktop browser, Android/Samsung portrait layout,
QR scanning with an actual camera app, upload progress, download, chat,
guestbook, help instructions, admin page rendering - see this phase's own
instructions for the complete list) rather than running it in this
session. Everything in that list was exercised programmatically
(`curl`/`zbarimg`/etc., see the automated test results in this phase's
git commit and report) but a real-camera QR scan and real-browser
rendering check on an actual phone have not yet happened. Do this before
relying on the QR codes or mobile layout for an actual event/demo.

## Phase 4 regression found and fixed: chat/guestbook posting was completely broken (missing mbstring)

**Decision date:** 2026-09-01 (Phase 5).

Phase 4 added `mb_substr()` calls to `chat.php`/`messages.php` (server-side
length caps matching the client-side `maxlength` attributes). The
`mbstring` PHP extension was never installed on this system, so every
single POST to `chat.php` or `messages.php` since that Phase 4 commit
threw an uncaught `Error: Call to undefined function mb_substr()` and
returned an HTTP 500 - **chat and the guestbook were completely unable to
accept new posts** for the entire time between the Phase 4 commit and
this fix. This was not caught by Phase 4's own testing: that phase tested
`GET` requests to both pages and tested the admin "clear chat"/"clear
messages" actions, but never re-POSTed a new message *after* the
`mb_substr()` code was added (an earlier POST test in that same session
ran before that code existed). Found during Phase 5's functional retest
of the redesigned pages.

**Fix:** installed `php8.4-mbstring` (`php-mbstring` in the installer, to
match the existing `php-fpm` version-agnostic package name convention).
`mb_substr()` was kept (not replaced with byte-based `substr()`) because
truncating raw bytes at a fixed offset can split a multi-byte UTF-8
character in the middle and produce invalid, corrupted text if a message
happens to land exactly at the 32/2000-character boundary - a real
concern for a chat/guestbook that has to handle arbitrary language
input - whereas installing one small, extremely common PHP extension has
no real downside. Verified live: posting to both `chat.php` and
`messages.php` now returns success and the message appears correctly.

**Lesson applied going forward:** after any change to a POST/write code
path, re-test that exact path with a live POST in the same session,
even if the underlying code "obviously" hasn't changed since an earlier
test in the same conversation.

## PHP's upload_tmp_dir moved off tmpfs onto the SD card

**Decision date:** 2026-09-01 (Phase 4).

PHP's default `upload_tmp_dir` is the system temp directory, which on this
system is `/tmp` - a **tmpfs** (RAM-backed) mount, ~453MB, on a Pi with
~905MB total RAM. Every upload sits fully in `$_FILES[...]['tmp_name']`
before `move_uploaded_file()` runs, so a large upload (this app allows up
to 120MB) was consuming real RAM rather than disk during that window, on a
system that already has 300-600MB RAM in active use.

**Fix:** `upload_tmp_dir` is now `/var/www/piratebox-tmp`, a dedicated
directory on the ext4/SD-backed root filesystem, set via
`php_admin_value[upload_tmp_dir]` in `pool.d/www.conf` (`php_admin_value`
rather than `php_value` so application code can't override it back via
`ini_set()`). The directory is `www-data:www-data`, mode `0700` (private -
only PHP-FPM needs it), created via `etc/tmpfiles.d/piratebox-tmp.conf` so
it exists with correct ownership after every boot. It sits outside
`/var/www/html/public` (nginx's document root), so nginx can never serve
it regardless of location-block configuration - there was nothing to
explicitly block.

**open_basedir** (`php.ini`) was extended to include the new directory -
without this, PHP would refuse to write there at all and every upload
would fail. `/tmp` itself was left in the allowed list (harmless, nothing
depends on removing it).

**Cleanup of abandoned temp files:** under normal operation PHP deletes
its own upload temp file at the end of every request whether or not
`move_uploaded_file()` was called, so nothing should ever actually
accumulate here. The `tmpfiles.d` rule also declares a 1-day cleanup age,
which uses systemd's existing `systemd-tmpfiles-clean.timer` (ships
enabled by default on Debian - no new cron/timer was added for this) to
catch the rare case of a file orphaned by a killed/crashed PHP-FPM worker
(OOM kill, `request_terminate_timeout`, power loss).

**Side benefit:** `upload_tmp_dir` and the `uploads/` directory are now on
the *same* filesystem, which is what makes `upload.php`'s new
collision-safe rename (see below) able to use `link()` at all - `link()`
fails across filesystems (`EXDEV`), which would have been a problem while
uploads landed in `uploads/` (ext4) via a tmpfs staging area.

**Gap found and fixed along the way:** the installer previously never
actually deployed `etc/php/8.4/fpm/pool.d/www.conf` at all (only
`sites-available/default` was copied for nginx) - the repo copy was
undeployed reference material, same category of gap as the already-
documented `php.ini` drift below. The installer now copies it, and also
now sets `open_basedir` itself (previously only ever set live, by hand,
during Phase 1 - never reproduced by a fresh install). Both are Phase 4
fixes, not new Phase 4 policy.

## Concurrent same-filename uploads no longer race

**Decision date:** 2026-09-01 (Phase 4).

`upload.php`'s duplicate-filename handling used to be
`file_exists($dest)` followed by `move_uploaded_file($tmp, $dest)` in a
loop - a classic check-then-act race. If two clients uploaded a file with
the same name at close to the same instant, both could pass the
`file_exists()` check for the same candidate name before either finished
moving its file, and the second `move_uploaded_file()` call would silently
overwrite the first, discarding one upload with no error to either party.

Now the upload is first moved to a privately-named staging file within
`uploads/` (a random 32-hex-char name, which can never collide with
anything), then the real, user-facing filename is *claimed* with
`link()` - a single atomic syscall that fails with `EEXIST` rather than
overwriting if another request claimed that name microseconds earlier. On
`EEXIST` the code retries with `_1`, `_2`, etc., exactly as before, just
race-free. Verified live with two genuinely concurrent uploads of the same
filename (see git history / this phase's testing) - both files survive
intact with distinct content.

**Also added:** an explicit filename-length cap (180 characters for the
base name, before the extension) - ext4 rejects a filename component over
255 bytes outright, and a very long original filename would previously
have failed at `move_uploaded_file()`/`link()` with a misleading "check
permissions" message instead of just... having a shorter name.

## Admin/status page (Phase 4): design and security boundaries

**Decision date:** 2026-09-01 (Phase 4).

A read-only status view plus three narrow maintenance actions, at
`/admin/`, protected by nginx HTTP Basic Auth on that path only. Design
goals: no accounts anywhere else in the app (unchanged), no privilege
escalation path from the web tier to root, and no arbitrary command
execution surface.

**Access control:** HTTP Basic Auth via `auth_basic_user_file
/etc/nginx/.piratebox_admin_htpasswd`, chosen over a PHP-level login
(simpler, well-tested, doesn't need a new session/account model) or a
"secret URL" (Basic Auth is stronger and standard). The installer creates
this file **empty** - a locked-out default, not a hardcoded credential -
so the admin page is completely inaccessible until an operator explicitly
runs `setup_admin_password.sh`. No password is ever written by the
installer or committed to git.

**Why the status data doesn't come from PHP directly:** `disable_functions`
already blocks `exec`/`shell_exec`/`system`/`passthru`/`proc_open`/`popen`
at the php.ini level for this whole app (a Phase 1/2 decision, unchanged).
Wi-Fi client count, per-service active/inactive state, and undervoltage
status all fundamentally require either running a command or reading
files a `www-data` process can't reach without broader privilege. Rather
than carve any exception into `disable_functions` or grant `www-data`
sudo, a **separate, narrowly-scoped root helper**
(`piratebox_status_helper.sh`) runs those specific reads on a fixed
30-second `systemd` timer, and writes the result as a small JSON file to
`/run/piratebox/status.json` (tmpfs - never the SD card), world-readable
(`0644`). The admin page just does a plain file read of that JSON - no
new privilege, no exec, no input the helper ever consumes (it takes no
arguments and reads no request data of any kind). The systemd unit also
runs the helper under `NoNewPrivileges`/`ProtectSystem=strict`/
`ProtectHome` for defense in depth, even though the script itself does
nothing but read system state.

Everything else the admin page shows (disk space, uploads directory size,
uptime, RAM, CPU temperature) PHP reads directly and safely: plain
`disk_free_space()`/`disk_total_space()` calls and plain reads of
`/proc/uptime`, `/proc/meminfo`, and
`/sys/class/thermal/thermal_zone0/temp` - each added to `open_basedir` as
an exact file path (not a whole directory) to keep the restriction as
narrow as everything else on that list.

**Maintenance actions - three, deliberately narrow:** clear chat, clear
guestbook messages, purge uploads. Each is independent (clearing chat
never touches messages or uploads), each requires the same CSRF token as
the rest of the app plus an explicit confirmation checkbox (plus a JS
`confirm()` dialog), and none of them shell out or need any privilege
`www-data` doesn't already have - `chat.json`/`messages.json`/`uploads/`
are already owned by `www-data` (PHP creates them), so no sudo is needed
for any of these three actions. Clearing chat/messages reuses the exact
`flock()` + atomic temp-file-then-`rename()` pattern Phase 1 established
for writes to those files, so an admin-triggered clear can never race a
visitor's concurrent post and corrupt the file.

**This fixes the Phase 2-documented `purge_uploads.sh` lock-race issue -
for the web-triggered path only.** Phase 2 noted that `purge_uploads.sh`
deletes `chat.json`/`messages.json` with a bare `rm`, which doesn't
coordinate with `flock()` at all. The new admin "clear chat"/"clear
messages" actions do NOT have this problem (they use the proper lock).
`purge_uploads.sh` itself was deliberately left unchanged - it remains the
manual, SSH-only, "wipe absolutely everything at once" utility it always
was, and still carries the same documented caveat as before. The admin
page's "purge uploads" action is also new/separate: it only touches
`uploads/`, never chat or messages, unlike the script.

**Deliberately deferred: no reboot or service-restart buttons.** Doing
these safely from `www-data` would need either broad `sudo` for
`www-data` (explicitly ruled out) or a second privileged helper with a
much larger and more dangerous surface than the read-only status helper
above (a helper that *restarts services or reboots on request* is a
fundamentally different risk than one that only ever reads and writes a
JSON snapshot on a fixed timer). Not worth it for what these commands
already do fine over SSH - see the README's "Known Issues and
troubleshooting" section for the exact commands
(`systemctl restart nginx`/`php8.4-fpm`/`dnsmasq`, `restart_hostapd.sh`,
`reboot`).

**Version display:** the installer writes the deployed commit hash to
`includes/VERSION` (best-effort - if the installer isn't run from a git
checkout, the admin page just shows "unknown" rather than failing). This
file is never committed to the repo itself (each deploy generates its
own); it's a `.gitignore`-worthy artifact but small enough not to bother
- if it's ever accidentally committed, it's harmless (just a commit hash).

## Typed hostnames can silently fail to resolve due to client-side DoH - not a PirateBox bug

**Decision date:** 2026-09-01 (post-Phase 3).

**Symptom investigated:** after Phase 3, a Samsung/Android phone that had
just gotten the correct captive "Sign in to network" prompt and could load
`http://10.0.0.1/` could **not** load `http://moosehost.net/` (an
arbitrary hostname relying on dnsmasq's `address=/#/10.0.0.1` wildcard),
even though the same hostname had reportedly worked before Phase 3.

**Investigation:** a bounded, temporary live `tcpdump` capture on `wlan0`
(installed just for this, no ongoing logging left behind) during a live
retest showed the phone's browser never sent a DNS query for
`moosehost.net` to the Pi at all. Instead it sent DNS-over-HTTPS/QUIC
queries straight to a hardcoded public resolver
(`10.0.0.206.41642 > 8.8.8.8.443: UDP, length 1200`, repeated, no reply),
which is unreachable on this intentionally offline network
(`net.ipv4.ip_forward` is `0`, no NAT/masquerade rule exists anywhere in
the `nftables` ruleset) - so the query simply timed out and the page
never loaded. In the same capture window, other hostnames resolved by
background apps (`graph.facebook.com`, and `mtalk.google.com` /
`alt6-mtalk.google.com` in an earlier capture) went through plain DNS to
`10.0.0.1:53` normally and got the correct wildcard answer. Queried
directly from the Pi, dnsmasq still resolves `moosehost.net` to `10.0.0.1`
correctly, and `etc/dnsmasq.conf`'s wildcard line is byte-for-byte
identical to the pre-Phase-3 backup. This conclusively rules out
PirateBox's own DNS/network config as the cause.

**Root cause:** the browser's own "Secure DNS" (DNS-over-HTTPS) feature -
possibly compounded by Android's system Private DNS setting - bypasses
the network-provided DNS server for some typed navigations, going to a
fixed public resolver instead of asking dnsmasq. This is client-side
behavior entirely outside PirateBox's control, and can plausibly be
intermittent/state-dependent (cache, per-network trust heuristics) rather
than a hard regression - which is consistent with the same hostname
having appeared to work at some point before Phase 3.

**Decision: not worked around server-side.** The only way to force a DoH
query back onto the local resolver would be to block or intercept
outbound HTTPS/QUIC (port 443/UDP-443) - which is exactly the kind of
HTTPS interception this project has already decided against (see the
"do not implement HTTPS MITM" constraint from Phase 3). PirateBox does
not intercept, block, or MITM HTTPS or DoH traffic, and won't start doing
so just to make manually-typed hostnames more reliable.

**What remains reliable, and is the actually-intended path:** direct
`http://10.0.0.1/` and the OS-level captive-portal flow (legacy HTTP
probes and the RFC 8908 Capport API added in Phase 3) both use the
device's own system network-validation HTTP client, not the browser's
DoH-enabled resolver, and are unaffected by this. Typing an arbitrary
plain-HTTP hostname was always a secondary/fallback way to reach
PirateBox, not the primary one - the primary, supported mechanism is
automatic captive-portal detection landing the user on `10.0.0.1`
directly. A user who wants typed-hostname browsing to also work
reliably can turn off their browser's "Use secure DNS" setting for this
network; that's a client-side choice, not a PirateBox configuration.

## `rpi-update` is intentionally NOT run by the installer

**Decision date:** pre-existing, documented 2026-08-31 (Phase 2).

The original README instructed running `sudo rpi-update` to move onto the
latest firmware/kernel, citing it as the fix for iOS-related Wi-Fi
disconnect/crash issues on a Pi Zero 2 W. `installer_pi_zero_trixie.sh` no
longer runs it. Modern Raspberry Pi OS (Trixie) should not be moved onto
bleeding-edge, less-tested firmware/kernel builds as a side effect of
installing PirateBox - that trade-off is for the operator to make
deliberately, not something an installer script should do by default.

**If you're hitting Wi-Fi stability problems:** check `dmesg`/`journalctl -k`
for `hwmon` undervoltage warnings first (power supply/cable issues are a
common and cheaper-to-fix cause on a Pi 3B+) before reaching for
`rpi-update`.

## Automatic deletion of user content is OFF by default

**Decision date:** 2026-08-31 (Phase 2).

The original README described `purge_uploads.sh` as an optional nightly cron
job that deletes all uploaded files, `chat.json`, and `messages.json`. This
PirateBox's default policy is:

> **Uploads, chat history, and guestbook messages persist indefinitely**
> unless an operator explicitly runs `purge_uploads.sh` by hand, or a future
> configurable admin-interface cleanup policy is deliberately turned on.

Reasoning: this system has ~114GiB of free storage and growing that content
organically is the point of the appliance - deleting people's files/messages
every night by default is user-hostile and was never something this
specific install actually had scheduled (the nightly cron entry the README
described was already absent from the live crontab before Phase 2 - this
decision makes that absence intentional rather than silent drift).

`purge_uploads.sh` remains installed at `/usr/local/bin/purge_uploads.sh`
and in this repo as a **manual** utility. It is NOT scheduled by cron by
default, and `installer_pi_zero_trixie.sh` does not install a cron entry for
it. Running it is a deliberate, irreversible, all-or-nothing wipe of
uploads + chat + messages - see the warning comment at the top of the script
itself.

**Before exposing this through a future admin interface:** note that the
script does not coordinate with the `flock()`-based locking added in
chat.php/messages.php - it deletes `chat.json`/`messages.json` directly with
`rm`, which does not respect or wait for another process's lock. A message
posted in the same instant as a purge could theoretically be lost rather
than either cleanly preserved or cleanly wiped. Low severity for a rare,
operator-triggered action, but worth having the admin interface acquire the
same `.lock` files before deleting, once that interface exists.

## The hourly `restart_hostapd.sh` cron job has been removed

**Decision date:** 2026-08-31 (Phase 2).

`restart_hostapd.sh` unconditionally ran `service hostapd restart` every
hour via cron, disconnecting every associated Wi-Fi client on the hour,
every hour, regardless of whether hostapd needed it. Journal history
reviewed before removal showed **zero evidence of an actual hostapd crash**
across the system's uptime - the only stop/restart cycle in the log was the
cron firing at the top of the hour, which disconnected the two clients that
happened to be connected at the time.

Real hostapd recovery is now handled natively by systemd:

- The Debian-packaged `hostapd.service` unit already sets
  `Restart=on-failure`, `RestartSec=2`, `StartLimitBurst=5`,
  `StartLimitIntervalUSec=10s` - this alone recovers from an actual process
  crash.
- Live crash-testing during Phase 2 (`kill -SIGKILL` on the running hostapd
  process) found a real gap: a hard kill can leave wlan0 in a state that
  briefly loses carrier, after which hostapd exits **cleanly** (exit code 0,
  since it correctly refuses to run an AP with no carrier) - and a clean
  exit is not a "failure" to `Restart=on-failure`, so recovery did not
  happen automatically; the AP stayed down until manually restarted.
- `etc/systemd/system/hostapd.service.d/override.conf` was updated to
  `Restart=always`, which restarts hostapd on *any* exit reason. A second
  live crash test with this in place recovered the AP fully and
  automatically within ~20 seconds, with no manual intervention. The base
  unit's `StartLimitBurst=5`/`StartLimitIntervalUSec=10s` is unchanged and
  still stops a genuine restart loop (e.g. truly dead Wi-Fi hardware) after
  5 attempts in 10 seconds, requiring `systemctl reset-failed hostapd &&
  systemctl start hostapd` to try again.

`restart_hostapd.sh` remains installed at `/usr/local/bin/restart_hostapd.sh`
as a manual recovery utility (e.g. if you ever need to force a restart after
changing `hostapd.conf` by hand). It is simply no longer scheduled.

No custom wlan0 health-check watchdog was added. There is no evidence a
failure mode exists that `Restart=always` doesn't already cover, and adding
one speculatively risks exactly the kind of restart-loop/over-engineering
this phase was told to avoid. Revisit only if a real, observed failure
pattern shows up that `Restart=always` doesn't handle.

## Upload storage-exhaustion guard

**Decision date:** 2026-08-31 (Phase 2).

`var/www/html/includes/config.php` defines `PIRATEBOX_MIN_FREE_BYTES` (1
GiB), the minimum free space that must remain on the uploads filesystem
after an upload is accepted. `upload.php` checks `disk_free_space()` against
it before calling `move_uploaded_file()`; if the upload would leave less
than that free, it is rejected with a plain-language error and never
committed to permanent storage. No existing files are ever deleted to make
room.

1 GiB was chosen because it is comfortably larger than the largest single
upload allowed (130MiB - no single upload can ever flip the system straight
from "fine" to "full"), while being a small fraction of this system's
~114GiB available capacity, so it costs essentially no usable storage.

This is deliberately the **one** place this policy value lives, so a future
admin interface has a single obvious constant to make configurable rather
than a value duplicated across files.

## Captive portal detection: DHCP option 114 (RFC 8910) added alongside legacy HTTP probes

**Decision date:** 2026-09-01 (Phase 3).

**Symptom:** a Samsung device running Android 16 (SM-F946U1) did not show a
normal "Sign in to network" captive-portal prompt on connecting to
PirateBox. Instead it showed "Internet may not be available" with
"Connect only this time / Always connect / Disconnect" - the fallback
Android shows when it decides a network has *no* internet and *no*
detected portal, which is a materially worse experience than the intended
"tap to open PirateBox" flow. Firefox/Linux, by contrast, already
correctly showed "You must log in to this network."

**Investigation:** the stock nginx access log doesn't include the `Host`
header, so a temporary, narrowly-scoped diagnostic log
(`map $request_uri $captive_diag_hit` + `access_log ... if=$captive_diag_hit`,
restricted to `/` and the known captive-probe URIs only - never all
traffic) was added to nginx, and dnsmasq's `log-dhcp` was enabled
temporarily. Both were removed again once the investigation below was
confirmed; this is a repeatable technique, not something left running.

This surfaced two things:

1. The device's system HTTP client (`Dalvik/2.1.0`, i.e. not a browser)
   was repeatedly requesting plain `GET /` with `Host: 10.0.0.1` - not
   `/generate_204` or any other standard Google/Samsung probe path - and
   getting `200` with the real PirateBox homepage body. This is a
   different, additional probe from Android's standard NetworkMonitor
   check; it was not the cause of the bad dialog by itself.
2. AOSP's `NetworkStack` module (`NetworkMonitor.java`) has a feature flag
   named `DNS_PROBE_PRIVATE_IP_NO_INTERNET_VERSION` and documented
   handling for the case where a captive-check hostname resolves to a
   private/RFC1918 address - exactly PirateBox's situation, since the
   wildcard DNS (`address=/#/10.0.0.1`) resolves
   `connectivitycheck.gstatic.com` (and everything else) to `10.0.0.1`.
   The working theory is that modern Android specifically distrusts a
   captive-portal signal derived from a DNS answer pointing at a private
   IP (a reasonable anti-hijacking precaution in general), and falls back
   to "no internet" rather than trusting the heuristic HTTP redirect - a
   fundamental limitation of DNS-hijack-based captive detection on an
   intentionally-private, intentionally-offline network like this one.

**Fix:** RFC 8910 (DHCP option 114) plus RFC 8908 (the Captive Portal API
JSON it points to) exist precisely to give clients a captive-portal signal
that doesn't depend on DNS-hijack heuristics. dnsmasq now sends option 114
(`dhcp-option=114,"http://10.0.0.1/.well-known/captive-portal"` - dnsmasq
2.91 has no built-in name for option 114, so it's set numerically; the
quoted value is sent as a raw ASCII URI string, which is the correct RFC
8910 wire encoding, confirmed both via `dnsmasq --test` and by reading the
live `log-dhcp` trace of the option actually being sent). nginx serves
that URL with `Content-Type: application/captive+json` and body
`{"captive":true,"user-portal-url":"http://10.0.0.1/"}`. `captive` is
permanently `true` - there is no "accept" flow, because this network never
gains real internet access and shouldn't pretend to; `user-portal-url`
points straight at the real PirateBox homepage over plain HTTP (neither
RFC 8908 nor RFC 8910 mandates TLS for this URL - it's a SHOULD in RFC
8910 section 5's security considerations, not a MUST - and this project
does not implement TLS/HTTPS interception).

**Confirmation:** the DHCP trace showed the device's own client
(`vendor class: android-dhcp-16`) requesting option 114 in its parameter
request list, and dnsmasq sending it back correctly encoded. After a live
Wi-Fi reconnect on the same device with this in place, the phone showed
the normal captive "Sign in to network" prompt instead of "Internet may
not be available" - confirmed by the device's owner in the same session.
Full end-to-end confirmation that tapping the notification loads the
PirateBox homepage in the system captive browser (as already independently
observed working via the legacy `/generate_204` redirect path earlier in
this same investigation) is still worth re-checking after any future
change, but the core fix - getting the correct prompt to appear at all -
is confirmed on real hardware, not just config-level testing.

The legacy DNS-hijack HTTP-probe redirects (`/generate_204`, `/gen_204`,
`/hotspot-detect.html`, `/library/test/success.html`, `/success.html`,
`/connecttest.txt`, `/ncsi.txt`, all still returning `302` to
`http://10.0.0.1/`) are unchanged and untouched - they remain the only
mechanism for Firefox/Linux, Windows NCSI, Apple, and any Android/ChromeOS
device that doesn't request option 114. The two mechanisms are additive,
not a replacement.

**Not done:** no attempt was made to intercept HTTPS, generate certificates,
redirect port 443, or otherwise make the network appear to have real
Internet access - all explicitly out of scope and contrary to this
project's offline-by-design intent.

**Housekeeping:** `var/www/html/public/captive.html` (a self-refreshing
HTML page, previously `try_files`-served for the Apple probe paths) is no
longer referenced by nginx now that those paths 302-redirect directly to
`http://10.0.0.1/` like every other probe path. Left in place, unreferenced
- harmless, and simple to wire back in if a future platform quirk needs a
non-redirect response instead of a 302.

## Pre-existing `dhcpcd.conf` / `hostapd.conf` live drift, synced during Phase 3

**Decision date:** 2026-09-01 (Phase 3).

While reviewing live config before making captive-portal changes, two
small pre-existing differences between the live system and this repo (not
part of Phase 1 or Phase 2's tracked changes) were found and synced into
the repo, since they reflect the actual working configuration and neither
carries any risk:

- `dhcpcd.conf`: `option ntp_servers` was uncommented live (harmless -
  just requests NTP server info via DHCP) and `denyinterfaces eth0` was
  present live but missing from the repo copy (keeps dhcpcd from touching
  eth0 at all, leaving it to plain DHCP/whatever the network provides -
  consistent with eth0 being the dedicated SSH/management interface, not
  part of the PirateBox AP).
- `hostapd.conf`: only a missing trailing newline - cosmetic.

No live system files were changed for this - only the repo's reference
copies, to match what was already actually running.

## The repo's `etc/php/8.4/fpm/php.ini` is a reference copy, not what gets deployed

**Decision date:** discovered during Phase 1, documented 2026-08-31.

`installer_pi_zero_trixie.sh` edits the **live system's**
`/etc/php/$PHP_VER/fpm/php.ini` directly with `sed`, based on whatever PHP
version it auto-detects (`ls /etc/php | sort -V | tail -1`). It does not
copy `etc/php/8.4/fpm/php.ini` from this repo anywhere. That means the
repo's copy of this file and the live deployed file can (and already have)
drift apart - confirmed during Phase 1 when their SHA256 hashes differed
before any Phase 1/2 change was made (`display_errors`, `log_errors`,
`memory_limit`, and `max_file_uploads` all differed).

This phase did **not** redesign that architecture. When you change a
PHP setting, you currently have to update both:

1. The live file (`/etc/php/8.4/fpm/php.ini`) for it to take effect, and
2. This repo's `etc/php/8.4/fpm/php.ini`, by hand, for documentation/future
   installs to match - the installer's `sed` commands do not read from it.

A future phase could make the installer deploy the repo's file directly (or
apply the same `sed` transforms to it too) so this can't drift again - out
of scope here.
