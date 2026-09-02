# Field Tools / Offline Reference Instruments Design (Post-Stage-32)

**Status: IMPLEMENTED.** Live under `/utility/fieldtools/` (not yet
deployed to the live site as of this writing - see
`docs/OPERATIONAL-DECISIONS.md`, "Field Tools / Offline Reference
Instruments," for deploy status). This document is the durable design
record; that entry is a summary pointing here.

## 1. Why this exists

PirateBox's existing value is public file/community service (Files,
Chat, Logbook, Bulletin) plus an offline reference library
(`/utility/`). Neither covers the case where the device itself needs to
be a useful **instrument** during days of no mains power, no cell
service, and no Internet - converting an unfamiliar unit, working out
elapsed time, or reading a coordinate off a map. Field Tools is that
third role, deliberately kept separate from the other two:

- **Public PirateBox service** - files/community/reference content
  available to anyone who connects.
- **Operator console** - OLED, buttons, modes, health/radio/storage
  information (Stage 29).
- **Field instrument** - time, conversions, calculations (this stage).

Field Tools is public, same as the rest of `/utility/` - the tools
themselves (unit math, a clock) carry no sensitive information, so
there's no reason to gate them behind the admin page. See §5 for the
explicit Travel Mode decision this implies.

## 2. What's here

`/utility/fieldtools/` (landing page) links to three tool pages:

- **`/utility/fieldtools/time/`** - current local/UTC time, ISO-8601
  (both), Unix timestamp, weekday, day-of-year, system uptime, and this
  device's time-source status (§4) - plus interactive tools: an
  elapsed-time/duration calculator, a Unix timestamp &harr; date/time
  converter, a weekday/day-of-year lookup for an arbitrary date, and a
  12-hour &harr; 24-hour converter.
- **`/utility/fieldtools/units/`** - temperature (&deg;C/&deg;F);
  distance (mm/cm/m/km/in/ft/yd/mi); mass (g/kg/oz/lb); volume (US
  customary: mL/L/fl oz/cups/pints/quarts/gallons); speed (mph/km/h/
  m/s); pressure (PSI/kPa/bar); storage/data (binary, bytes/KiB/MiB/
  GiB/TiB); percentage (percent-of, percent-change); electrical (V
  &times; A = W, Ah&rarr;Wh) and a battery-runtime estimator with
  explicit theoretical-vs-real-world caveats (§3).
- **`/utility/fieldtools/coordinates/`** - decimal degrees &harr;
  degrees/minutes/seconds. Deliberately does not duplicate
  `/utility/maps/`'s written explanation of coordinate formats (DD/DMS/
  UTM/MGRS) - the two pages cross-link (maps = explanation, this =
  calculator).

**Deliberately not built:** a general scientific calculator, unit
categories beyond the ones listed above, and UTM/MGRS conversion
(genuinely more complex map-projection math, not a good fit for "avoid
turning this into an enormous scientific-calculator project" - the
Maps page's existing written explanation of what UTM/MGRS are stays the
reference for those).

## 3. "Estimate, not a guarantee" - where that matters most

Every conversion here is exact arithmetic except one: battery runtime
(`piratebox_battery_runtime_hours()` in `includes/fieldtools_convert.
php`). That function is `capacity_Wh &times; efficiency / load_W` -
correct arithmetic, but a poor model of reality on its own. The UI
states explicitly, right next to the tool, that real-world runtime is
normally *lower* than this suggests (inverter/converter losses, reduced
usable capacity at high discharge or low temperature, non-constant
load), that the efficiency factor is one blunt derate knob rather than
a precise model, and that this is a planning number, not a promise.
This caveat is deliberately not buried in a tooltip - it's a permanent,
visible `help-note` block above the calculator.

## 4. Time-source architecture - built for a DS3231 that isn't here yet

This Pi has **no hardware RTC installed** as of this writing (see
`docs/RTC-TIME-READINESS-DESIGN.md`, Stage 28 - that audit's findings
are unchanged by this stage; a DS3231 remains **planned, not
installed**). The Time page does not pretend otherwise.

**Found live, corrected before this stage's first deploy:** an earlier
version of `piratebox_get_time_source_status()` read `/sys/class/rtc/`,
`/run/systemd/timesync/synchronized`, and `/etc/fake-hwclock.data`
directly. Rendering the Time page for real (not just `php -l`) showed
PHP-FPM's `open_basedir` restriction (`etc/php/8.4/fpm/php.ini`) blocks
every one of those paths - `file_exists()`/`glob()` returned a *silent*
`false` under a PHP warning, which would have looked like a real "not
present" answer while actually being a permissions block. That's
exactly the kind of fabricated-looking negative this feature is
supposed to refuse to produce, so it was fixed before shipping rather
than shipped and revisited: `piratebox_get_time_source_status()` now
reads `/run/piratebox/status.json` (which **is** inside `open_basedir`)
via `includes/metrics.php`'s existing `piratebox_get_helper_status()`,
the same "PHP can't read this directly, so a root-run periodic script
publishes it instead" pattern that function's own header already
documents and this app already relies on elsewhere. The actual
`/sys/class/rtc`/`/run/systemd/timesync`/`/etc/fake-hwclock.data` reads
now happen inside `piratebox_status_helper.sh` (runs as root, no
`open_basedir`), which publishes a new `time_source` block into that
status file:

- `rtc_detected` - true the instant any `/sys/class/rtc/rtcN` device
  exists. This is exactly what wiring a DS3231 per `docs/HARDWARE-
  INTEGRATION-DESIGN.md`'s I2C plan makes appear - **this needs zero
  code changes when that happens**, the script already reads whatever's
  really there.
- `ntp_synchronized` - systemd-timesyncd's own live verdict. Normally
  false on this device by design (isolated AP, no confirmed uplink) -
  the UI states this is expected here, not a fault.
- `fake_hwclock_installed` - whether Stage 28's other candidate
  mitigation has since been installed (it hadn't, as of this stage).

**Three-state, not two:** `piratebox_get_time_source_status()` returns
`available` (bool) and `stale` (bool) alongside the three fields above,
which are `null` - never a fabricated guess - whenever `available` is
false. That happens in two real cases: the status snapshot is stale
(`piratebox_get_helper_status()`'s existing >300s window, same as every
other reader of that file), or the snapshot is fresh but doesn't carry
a `time_source` block yet, because the *deployed*
`piratebox_status_helper.sh` (root-owned, `/usr/local/bin/`, installed
separately from the web-tree deploy - see §9) predates this change. The
Time page shows an honest "not currently reporting" message in either
case rather than guessing. **This second case was this repo's actual
live state as of the `58ef5bb` commit** - the code fix was deployed,
but the root script that populates the new field wasn't yet installed
(see §9) - so the live Time page showed exactly that message,
correctly, until the operator installed the updated script on
2026-09-02 (§9). Live now reads `available: true` with real
(non-`null`) `rtc_detected`/`ntp_synchronized`/`fake_hwclock_installed`
values, confirmed via the actual generated `/run/piratebox/status.json`
and the live-rendered Time page - not the "not currently reporting"
branch anymore.

**Deliberately not built:** a persisted "last successful NTP sync"
timestamp. No component on this device currently records that moment -
it would need a new field in `piratebox_status_helper.sh`'s periodic
write, same file the RTC/NTP/fake-hwclock fields above already went
into, but a genuinely separate piece of work (this stage's fields are
all live/instantaneous checks; "last successful sync" needs actual
persistence logic). Deferred, not fabricated - see the Time page's own
statement of this.

**What becomes automatically better once a DS3231 is wired and its
kernel overlay loads**, with no further PirateBox code changes:
`rtc_detected` flips true, and the Time page's whole top warning block
switches from "no hardware RTC - treat this as best-effort" to the
already-written RTC-detected branch. The underlying `date()`/`time()`
PHP calls this whole feature is built on don't change at all - only
how trustworthy their answer is, which is exactly what this status
function exists to report honestly either way.

## 5. Travel Mode / Content Profile - deliberately not integrated

- **Travel Mode**: not applicable. Travel Mode (`includes/travel_mode.
  php`) quarantines *local/deployment-specific* content (this box's own
  configured hospitals, shelters, regional map catalog). Field Tools
  has none of that - a unit converter and a clock reveal nothing about
  where this device is deployed. No quarantine list entry, no
  `regional` flag on its search-index entries (see `tools/
  build_search_index.py`).
- **Content Profile** (Stage 31): not applicable. That mechanism
  reorders *Emergency Reference* topics by hazard scenario
  (hurricane/wildfire/winter storm) - Field Tools isn't hazard-scenario
  content, so it isn't a candidate for that reordering and doesn't read
  `includes/content_profile.php`.

## 6. Architecture: PHP canonical, JS mirrors it

`includes/fieldtools_convert.php` and `includes/fieldtools_time.php`
hold every formula as a small, pure, dependency-free function - no
filesystem/session/network access in the conversion functions
themselves, which is what makes `tools/test_fieldtools.php` able to
test them directly from the CLI with no web server involved. PHP is
authoritative and tested; the static reference tables on the Units page
are rendered server-side using these exact functions, so the page has
real, correct content even with JavaScript off.

The interactive converters (arbitrary user input, live feedback as you
type) need JavaScript - this project has no build step or shared PHP/JS
codegen, so `public/assets/fieldtools.js` is a hand-maintained mirror of
the same formulas/constants, called out explicitly in both files'
headers as needing to stay in lockstep. This was a deliberate tradeoff
over adding a `fetch`-based JSON endpoint (which would keep one copy of
the math but add a round-trip and a new attack-surface-shaped endpoint
for what is, in every case here, simple linear arithmetic) - accepted
because the formula set is small and simple enough that duplication
risk is low, and because the PHP side is the one that's actually
tested. Every page still degrades to a real, informative static page
with JavaScript off (`<noscript>` notices, server-rendered "right now"
time snapshot and reference tables) rather than breaking.

**Found and disclosed, not fixed by this stage:** this device's PHP has
no `date.timezone` configured (`etc/php/8.4/fpm/php.ini`), so `date()`
defaults to UTC regardless of the system's actual configured timezone
(`America/Los_Angeles` per `timedatectl`, on the box this was built on).
The Time page detects this and shows an explanatory note rather than
silently displaying identical "Local" and "UTC" columns. Not changed
here - `date.timezone` affects every timestamp this whole application
renders (chat, messages, admin page, everywhere else `date()` is
called), a blast radius well beyond one self-contained feature; fixing
it is a good small future stage on its own, not folded into this one.

## 7. Reuse audit performed before building

Checked for existing overlap before writing anything: no prior
date/time display beyond `piratebox_get_uptime_seconds()`/
`piratebox_fmt_duration()` (`includes/metrics.php`/`helpers.php`,
reused here rather than reimplemented) and raw `time()` calls scattered
through chat/messages/etc. (no shared "current time in every format"
helper existed). No prior unit-conversion code anywhere in the repo.
`/utility/maps/` has written coordinate-format *explanation* but no
interactive converter (see §2). Styling reuses existing classes
wholesale (`.radio-page`, `.utility-breadcrumb`, `.stat-grid`/
`.stat-card`, `.help-note`, `.table-wrapper`) - the only new CSS added
is dark-theme styling for `input[type=number/date/time/datetime-local]`
and `select` (the existing stylesheet only styled `input[type=text]`)
and three small `.fieldtools-*` layout classes.

## 8. Testing performed

- `tools/test_fieldtools.php` (new, PHP CLI, no dependency) - 86
  deterministic assertions against `includes/fieldtools_convert.php`
  and `includes/fieldtools_time.php`: boundary/sign cases (negative
  temperatures including the -40 fixed point and absolute zero, zero
  values, division-by-zero-guarded percentage/electrical functions),
  decimal values, round trips (temperature, distance, volume,
  coordinate DD&rarr;DMS&rarr;DD including a negative-longitude case),
  a leap-year and non-leap-year day-of-year check, and - after §4's
  fix - a direct, deterministic test of `piratebox_get_time_source_
  status()`'s three-state decision logic itself (fresh-but-no-block,
  stale-even-with-a-block, fresh-with-a-block), not just its shape,
  confirming the `null`-when-unavailable / real-booleans-when-available
  contract holds in every case. All 86 pass.
- `php -l`/`bash -n` clean on every new/changed PHP and shell file.
- Every new/changed page rendered via `php -S` (PHP's built-in dev
  server) - all return HTTP 200, zero PHP warnings/errors/notices in
  the server log. This is exactly how §4's `open_basedir` bug was
  caught in the first place (`php -l` alone can't see it - it's a
  runtime restriction, not a syntax error) - re-rendering after the fix
  against this device's actual live `/run/piratebox/status.json`
  (genuinely missing the `time_source` block, since the deployed status
  helper isn't updated yet - see §9) confirmed the real degraded case
  renders the honest "not currently reporting" message with zero
  warnings, not simulated.
- `grep` across every new file for `http://`/`https://`/`cdn.`/known
  CDN hostnames - zero matches; confirmed zero external requests
  anywhere in this feature (`fieldtools.js` contains no `fetch`/`XHR`
  call at all - see §6).
- Manual brace/paren/bracket balance check on `fieldtools.js` (no JS
  runtime available in this environment to execute it directly).
- `tools/build_search_index.py` re-run; confirmed 7 new `section:
  "fieldtools"` entries, valid JSON, none carrying a `regional` flag.
- Not tested: JavaScript execution in an actual browser (no browser
  available in this environment) - the PHP-rendered static content and
  JS syntax/logic were verified as above instead; a real-browser check
  is worth doing once this reaches live use.
- The Time page's "available, no RTC" rendering branch **was**
  subsequently verified live, once §9's pending step closed on
  2026-09-02: the actual live `/run/piratebox/status.json` and the
  live-rendered page both confirmed correct. The "RTC detected" branch
  remains untested against a real live snapshot, for the obvious reason
  that no RTC hardware exists on this device yet
  (`docs/CAPABILITY-REGISTRY.md`) - covered instead by the deterministic
  shape-logic test plus direct code review of the template's
  conditional structure, which mirrors that same tested logic exactly.

## 9. Operator step - RESOLVED 2026-09-02 (was pending since `58ef5bb`)

**Status: done.** Kept below for the historical record of why the gap
existed and how it was closed, per this project's convention of not
erasing rationale once it stops being current.

At the `58ef5bb` commit, this one thing was **finished and committed,
just not yet installed live**, because it was outside that session's
automation, not outside its scope: `piratebox_status_helper.sh` (repo
root) published the `time_source` block §4 describes, but the deployed
copy at `/usr/local/bin/piratebox_status_helper.sh` (root-owned,
installed separately from the `var/www/html/` web-tree deploy - there's
no `setup_*.sh` installer for this specific script, unlike
`piratebox_deploy.sh`/`set_piratebox_mode.sh`'s
`setup_claude_automation.sh`) still predated the change, and that
session had no `sudo` grant able to install/overwrite it. Until closed,
the live Time page correctly and honestly showed "time source: not
currently reporting" (§4's `available: false` case) rather than a wrong
or fabricated answer - confirmed live at the time, not just reasoned
through.

**Closed 2026-09-02:** the operator ran, verified in a later session:

```
sudo install -m 0755 -o root -g root /home/moose/piratebox/piratebox_status_helper.sh /usr/local/bin/piratebox_status_helper.sh
sudo systemctl restart piratebox-status.timer
```

(`install -m 0755 -o root -g root`, not a bare `cp` - matches the exact
ownership/mode convention `setup_claude_automation.sh` already uses for
`piratebox_deploy.sh`/`set_piratebox_mode.sh`, rather than leaving the
installed copy group-writable the way a plain `cp` from the `moose`-
owned, `0775` repo file would have.) Verified after: installed copy is
byte-identical to the repo source (`diff` clean); `piratebox-status.
service` ran to `status=0/SUCCESS`; the regenerated
`/run/piratebox/status.json` carries a real `time_source` block
(`rtc_detected: false`, `ntp_synchronized: false`,
`fake_hwclock_installed: false` - all real booleans, honestly reflecting
this device's actual state: no RTC installed, no NTP path on an
isolated AP, `fake-hwclock` not installed); the live Time page now
renders the "available" branch (the honest "no hardware RTC" message,
not "not currently reporting"); zero PHP warnings/errors; all core
services and `piratebox-status.timer` active; zero failed systemd
units; no unrelated file or runtime change.

## 10. What's deferred

- **Export-bundle integration** (`tools/build_export_bundles.py`,
  Stage 19's "Take This With You") - not added. That mechanism assumes
  static reference content, not interactive calculators; bundling the
  static reference tables alone was judged not worth the complexity for
  this stage. Worth revisiting if operators ask for it.
- **Persisted "last NTP sync" timestamp** - see §4.
- **`date.timezone` fix** - see §6.
- **UTM/MGRS coordinate conversion** - see §2.

## 11. Relationship to Stage 29 (OLED)

The OLED Clock page design (`docs/PHYSICAL-CONTROL-UX-DESIGN.md` §1)
now names `piratebox_get_time_source_status()` and
`piratebox_fieldtools_now_snapshot()` (this stage's new functions,
`includes/fieldtools_time.php`) as what a future OLED daemon should
read for its Clock page, the same "one tested copy, multiple readers"
pattern `includes/metrics.php` already established for the Status/
Network/Health pages. No OLED code exists yet (no display is wired) -
only the design document was updated; see that document directly for
the page-content spec.
