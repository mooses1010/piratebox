# Field Tools / Offline Reference Instruments Design (Post-Stage-32)

**Status: IMPLEMENTED.** Live under `/utility/fieldtools/` (not yet
deployed to the live site as of this writing - see
`docs/OPERATIONAL-DECISIONS.md`, "Field Tools / Offline Reference
Instruments," for deploy status). This document is the durable design
record; that entry is a summary pointing here.

## 1. Why this exists

PirateBox's existing value is public file/community service (Files,
Chat, Guestbook, Bulletin) plus an offline reference library
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
installed**). The Time page does not pretend otherwise:
`includes/fieldtools_time.php`'s `piratebox_get_time_source_status()`
reports, read-only, with no `shell_exec` (disabled for PHP-FPM - see
`etc/php/8.4/fpm/php.ini`):

- `rtc_detected` - true the instant any `/sys/class/rtc/rtcN` device
  exists. This is exactly what wiring a DS3231 per `docs/HARDWARE-
  INTEGRATION-DESIGN.md`'s I2C plan makes appear - **this function
  needs zero code changes when that happens**, it already reads
  whatever's really there.
- `ntp_synchronized` - systemd-timesyncd's own live verdict
  (`/run/systemd/timesync/synchronized`'s existence). Normally false on
  this device by design (isolated AP, no confirmed uplink) - the UI
  states this is expected here, not a fault.
- `fake_hwclock_installed` - whether Stage 28's other candidate
  mitigation has since been installed (it hadn't, as of this stage).

**Deliberately not built:** a persisted "last successful NTP sync"
timestamp. No component on this device currently records that moment -
adding it would mean a new field in `piratebox_status_helper.sh`'s
periodic write (a root-run script, a different trust boundary than this
web-facing stage), which this stage did not touch, consistent with
"do not change ... unless absolutely required." The Time page states
plainly that no such record exists yet rather than fabricating one.
`piratebox_get_time_source_status()`'s shape already has room for this
field to be added later without a breaking change.

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

- `tools/test_fieldtools.php` (new, PHP CLI, no dependency) - 73
  deterministic assertions against `includes/fieldtools_convert.php`
  and `includes/fieldtools_time.php`: boundary/sign cases (negative
  temperatures including the -40 fixed point and absolute zero, zero
  values, division-by-zero-guarded percentage/electrical functions),
  decimal values, round trips (temperature, distance, volume,
  coordinate DD&rarr;DMS&rarr;DD including a negative-longitude case),
  a leap-year and non-leap-year day-of-year check, and structural checks
  on the time-source status function. All 73 pass.
- `php -l` clean on every new/changed PHP file.
- Every new/changed page rendered via `php -S` (PHP's built-in dev
  server) - all return HTTP 200, zero PHP warnings/errors/notices in
  the server log, spot-checked rendered output for the "right now"
  snapshot and time-source note.
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

## 9. What's deferred

- **Export-bundle integration** (`tools/build_export_bundles.py`,
  Stage 19's "Take This With You") - not added. That mechanism assumes
  static reference content, not interactive calculators; bundling the
  static reference tables alone was judged not worth the complexity for
  this stage. Worth revisiting if operators ask for it.
- **Persisted "last NTP sync" timestamp** - see §4.
- **`date.timezone` fix** - see §6.
- **UTM/MGRS coordinate conversion** - see §2.

## 10. Relationship to Stage 29 (OLED)

The OLED Clock page design (`docs/PHYSICAL-CONTROL-UX-DESIGN.md` §1)
now names `piratebox_get_time_source_status()` and
`piratebox_fieldtools_now_snapshot()` (this stage's new functions,
`includes/fieldtools_time.php`) as what a future OLED daemon should
read for its Clock page, the same "one tested copy, multiple readers"
pattern `includes/metrics.php` already established for the Status/
Network/Health pages. No OLED code exists yet (no display is wired) -
only the design document was updated; see that document directly for
the page-content spec.
