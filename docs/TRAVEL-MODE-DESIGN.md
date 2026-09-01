# Travel Mode Design (Post-Stage-32)

**Status: implemented and deployed** (manual toggle only). The future
automation hook described in §6 is design-only - nothing in that
section is built.

Travel Mode is a privacy-oriented toggle that temporarily suppresses
this PirateBox's region-specific content (Local Information, its
regional map catalog, and any search/export surface that could embed
either) without deleting any of it. The scenario it protects against:
the operator relocates the device (backpack, vehicle, a different
event) and doesn't want a stranger connecting to it to learn what
region it's normally deployed in.

**Explicitly distinct from Stage 16's Recovery/Lost Mode** (deferred,
never built): that concept is about a *physically lost* device
announcing itself as missing to whoever finds it. Travel Mode is about
a device *deliberately relocated by its own operator* hiding home-region
content from ordinary visitors. Different trigger, different UI, no
shared code.

---

## 1. What Local Information touches - the full audit

Before writing any code, every consumer of `data/utility/local/info.json`
and everywhere region-specific content could otherwise leak was
enumerated:

**Content itself:**
- `data/utility/local/info.json` - region label, emergency management/
  NWS contacts, hospitals, shelters, amateur repeaters, radio notes, map
  references, other resources, plus `emergency_numbers` (911, Poison
  Control - explicitly documented as universal, not region-specific).
- `public/utility/local/index.php` - renders all of the above.

**Consumers that surface actual *content*, not just a nav label:**
1. **Global Search** (`utility/search/index.php` +
   `data/utility/search-index.json`) - `tools/build_search_index.py`
   bakes real hospital names/addresses, repeater callsigns/locations,
   and (see the leak found in §3) map-catalog entries into the index
   once Local Information is populated.
2. **"Take This With You" exports** (`tools/build_export_bundles.py`) -
   `maps-local-bundle.zip` and `complete-utility-library.zip` both bundle
   a static copy of Local Information as of whenever they were last
   built.
3. **Maps page's "Map Catalog"** (`data/utility/maps/catalog.json`) -
   explicitly documented on its own page as "for this box's area" -
   genuinely region-specific, distinct from the same page's generic
   coordinate/GPS-basics section (`reference.json`), which is universal.

**Left alone, deliberately** (operator-approved judgment call): generic
nav links/prose that only say "Local Information" by name (the
cross-link rows on Emergency/First Aid/Radio/Maps/Library, the Utility
Library landing grid card, `whatcanidohere.php`/homepage prose) - these
reveal nothing on their own. A visitor reaching the actual Local
Information page while Travel Mode is active simply sees that it's
intentionally hidden.

**Confirmed clean, no changes needed:** admin panel, manifest page,
Stats page, Radio section (repeaters live in Local Information, not
here).

## 2. Architecture

**New module `includes/travel_mode.php`**, matching the existing
`content_profile.php`/`mode.php` pattern:
- `piratebox_get_travel_mode(): bool`
- `piratebox_set_travel_mode(bool $enabled): bool` - also immediately
  re-applies the quarantine (§3) so on-disk protection is never out of
  sync with the state just set.
- `piratebox_apply_travel_mode_quarantine()` / helper move functions -
  see §3.

**Persistence:** `data/travel-mode.json` on the SD card - unlike
`mode.php`'s deliberately volatile `/tmp` state, Travel Mode must
survive a reboot that happens *while away from home* (a power cycle
mid-trip must not silently drop back to showing local info exactly when
it matters most).

**Fail-safe direction, deliberately the OPPOSITE of `mode.php`'s own
convention:** `mode.php` defaults any unreadable state to Normal (the
least alarming state). Travel Mode defaults any *unexpected* missing/
corrupt state to **ON/suppressed** (the least revealing state) - per
instruction, unavailable/invalid state must never accidentally expose
local information. The one deliberate exception: `piratebox_deploy.sh`
seeds `data/travel-mode.json` to `false` the very first time it's
missing, so shipping this feature doesn't suddenly hide Local
Information for an existing at-home deployment. Any file loss *after*
that first seed still fails toward suppressed.

**Fully orthogonal to Normal/Emergency Mode and to `content_profile.php`**
- this module never reads `piratebox_get_mode()`, and nothing in it
changes based on either. Someone traveling through a real emergency
should still not see the home region's hospital name.

## 3. Direct-access protection - the part that isn't just UI

Hiding a link or a page's content is not sufficient if the underlying
static file is still directly fetchable by a known, bookmarked, or
guessed URL. Confirmed directly, live, before designing the fix: with
`nginx`'s `location / { try_files $uri $uri/ /index.php?$args; }`,
**any real static file under `public/` is served straight from disk,
completely bypassing PHP** - `curl http://.../utility/exports/
maps-local-bundle.zip` returns the file whether or not the download
page's own link is showing.

**Fix: reuse the project's oldest, most-tested security boundary
instead of inventing a new authorization system.** nginx's document
root is `public/` - `data/` is a *sibling* directory, structurally
unreachable by any URL no matter what nginx does, the same boundary
`chat.json`/`device-id.json` have relied on since Phase 1. Travel Mode
moves a fixed, hardcoded list of local-sensitive static artifacts
between their normal location under `public/utility/exports/` and a
holding directory, `data/travel-mode-quarantine/`, when the mode
changes:

```
maps-local-bundle.zip
complete-utility-library.zip
data/local                    (directory - the raw JSON export)
data/maps/catalog.json        (file only - reference.json/sources.json stay)
static/local                  (directory - the static rendered page)
static/search                 (directory - see below)
```

This is deliberately a **blunt mechanism, not a content inspector or a
permission check**: it never tries to determine whether a given path
*currently* contains real local data - the same fixed list is always
quarantined together, and universal-only bundles (radio, emergency,
first aid, manuals, generic maps reference) are never in it.

**Why `static/search` is quarantined wholesale rather than filtered:**
Stage 8's Search page server-renders every result into one flat static
HTML file when exported - local and universal results aren't separable
after the fact without a full rebuild. Quarantining it costs nothing:
the *live* Search page (§4) is correctly filtered and remains fully
available; only the static, offline-takeaway copy of Search is
unavailable while traveling. This is an honest, small, explicitly
accepted limitation, not a workaround for a bug.

**Enforcement is idempotent and runs from exactly two places:**
1. `piratebox_set_travel_mode()` - immediately, for a live admin toggle.
2. `tools/apply_travel_mode_quarantine.php`, called by
   `piratebox_deploy.sh` after every real deploy - because a deploy can
   write fresh, un-quarantined copies of these exact files straight over
   ones that were already quarantined. Verified directly: simulating a
   deploy landing a fresh local-containing ZIP while Travel Mode was
   already ON, the next quarantine-apply call correctly detected and
   re-quarantined it, keeping the *newer* content.

**Content is preserved, never deleted** - toggling back off restores
everything to its exact original location. **Previously downloaded
copies obviously cannot be affected by this or anything else** once
they've left the device - stated plainly on the download page and here,
not glossed over.

## 4. A real leak found and fixed during testing

The Search page's render-time filter was originally written as
`section !== 'local'`. Testing with a distinctive fake map-catalog entry
found this insufficient: `tools/build_search_index.py` indexes the
regional map catalog under `section: "maps"` - the *same* section as
the universal coordinate/GPS reference entries, since both belong on the
same live page. A section-only filter could not tell them apart.

**Fix:** `build_search_index.py`'s `entry()` gained an optional
`regional=True` flag, set only on catalog-derived map entries. The
Search page's filter now excludes `section === 'local'` **or**
`regional === true`. Verified: rebuilding the index with a fake catalog
entry and re-testing confirmed the leak closed, and toggling Travel Mode
back off correctly restored the entry to search results (no
over-suppression).

## 5. Leakage regression test (isolated fixture, no real user data)

An isolated fake webroot (never the live tree) was populated with
distinctive marker strings (`ZZZFAKETESTHOSPITAL`, `ZZZFAKETESTREGION`,
`ZZZFAKETESTMAPCATALOG`, etc.) in every location identified in §1,
alongside genuinely universal content (a fake `radio-bundle.zip`,
generic `maps/reference.json`) that must **never** be touched. The test
covered:

- Fail-safe default (no state file yet) → suppressed, confirmed via
  `piratebox_get_travel_mode()` directly.
- Explicit OFF → all fake markers present at their normal, servable
  paths; universal content also present (baseline).
- Toggle ON → **zero** occurrences of any fake marker anywhere under
  `public/`, checked by full-tree `grep`, both via direct PHP calls to
  the quarantine function and via real HTTP requests through a live PHP
  server. Content confirmed preserved (not deleted) in
  `data/travel-mode-quarantine/`. Universal content confirmed untouched
  at its original path.
- Toggle OFF → full restoration, byte-for-byte, to original locations;
  quarantine directory emptied.
- Simulated deploy race (fresh un-quarantined file written directly to
  the normal path while Travel Mode was ON) → the deploy-time CLI
  wrapper correctly detected and re-quarantined it.
- End-to-end via the actual admin HTTP action (not just direct PHP
  calls) - toggling through the real form submission, then `curl`-ing
  the direct file URLs and grepping response **bodies** (not status
  codes - see the note below) for the fake markers: zero matches for
  all 6 quarantined paths; universal paths unaffected.

**Note on HTTP status codes, so a future reader doesn't mistake this for
a gap:** once a path is quarantined, nginx's blanket
`try_files $uri $uri/ /index.php?$args` falls through to the PirateBox
homepage with a `200` status - **not** a `404`. Confirmed this is
pre-existing, universal site behavior, unrelated to Travel Mode:
requesting *any* URL that has never existed on this site (tested with a
random made-up filename) gets the identical `200`-homepage fallback,
because this site has no custom routing or 404 page. The privacy
property that actually matters - the sensitive bytes are never
transmitted - was verified by inspecting response *bodies*, not status
codes, which is the correct and only meaningful test here.

## 6. Manual toggle (implemented) and physical control (future)

**Now:** a non-destructive admin-panel action (`set_travel_mode`), same
UX pattern as the Stage 31 content-profile toggle - reversible, no
confirm-checkbox, immediate effect.

**Public UI:** no site-wide banner. The only public-facing mention is
the Local Information page itself stating why it's empty when visited -
contextual, necessary so the page doesn't just look broken, not an
obnoxious global notice. The admin panel shows current state plainly.

**Future physical control - ties directly into Stage 29's existing
design, not new territory:** Stage 29 already reserved two momentary
buttons (GPIO24/27) specifically for "a genuinely new need" it didn't
have yet. Travel Mode toggle is exactly that need - a short-press toggle
with a brief OLED confirmation ("TRAVEL MODE: ON/OFF"), once that
hardware exists. Nothing to build now.

## 7. Automatic detection - not implemented now, kept open for later

**Decision: manual-only for the foreseeable present.** No GPS exists or
is planned; the built-in Wi-Fi radio is fully committed to serving as
the AP. Implementing automatic detection today would require either new
hardware or degrading the AP, so it isn't attempted.

**This is explicitly a "not yet," not a permanent architectural
conclusion.** The ordered ALFA AWUS036ACM (see the "Wi-Fi adapter notes"
entry in `OPERATIONAL-DECISIONS.md`) is planned as a potential
*replacement* for the AP role currently played by the Pi's built-in
`wlan0`. **If** that migration succeeds, the built-in radio would become
free for a secondary role - at which point a privacy-preserving
automatic design becomes plausible without adding any new hardware:

- The freed radio periodically scans (station/monitor mode, brief,
  low-duty-cycle) for one or more **explicitly operator-configured**
  trusted home/local Wi-Fi signals (e.g. specific BSSIDs or SSIDs the
  operator names once, during setup).
- Only a **live present/absent boolean** is ever evaluated - no scan
  history, no signal-strength trend, no logged timeline of what
  networks were seen when. Each scan result is compared to the
  configured trusted set and then discarded, exactly like the
  connection-statistics feature already discards raw MAC data after
  each 30-second comparison.
- No Internet dependency, no cloud geofencing, no external service of
  any kind - the "trusted signal" set is configured locally and checked
  locally.
- **The configured home-network identifiers themselves are never
  exposed publicly** - not on any public page, not in exports, not in
  logs beyond what's operationally necessary.

**Authority principle, matching how this project already treats manual
vs. automatic elsewhere (e.g. Normal/Emergency Mode being physical-
switch-only, never web-triggerable) - specified now so a future
implementation has no ambiguity to resolve on its own:**
- **Manual Travel Mode selection is always authoritative.** Automation
  must never silently override an operator's explicit, current choice
  in either direction.
- If automation itself is what entered Travel Mode (because the
  trusted signal disappeared), it may restore Local/Normal presentation
  **only** after the trusted signal has been continuously present again
  for a conservative stability period - not on the first sighting, to
  avoid flapping at the edge of range.
- If the operator manually turned Travel Mode on or off, automation must
  not reverse that decision on its own - a manual choice stands until
  the operator changes it again, regardless of what the radio sees.
- No movement history, scan history, or cloud geofencing, ever - this
  list is a hard constraint on any future design in this space, not a
  suggestion.

This section exists so a future implementer (human or AI) has the
authority model and privacy constraints already settled, rather than
needing to re-derive them - and so "no GPS/no second radio" is
understood as a hardware-timing fact, not a reason automatic detection
was ruled out in principle.
