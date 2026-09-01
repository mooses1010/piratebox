# Operational decisions

This file records intentional configuration/behavior decisions that differ
from the original upstream PirateBox project or from what the README used to
recommend, so a future maintainer (human or AI) doesn't "fix" them back to
the old behavior without knowing why they were changed. Each entry has a
date and the reasoning; if you're going to reverse one, update this file too.

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
