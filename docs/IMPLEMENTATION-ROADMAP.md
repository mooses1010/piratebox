# PirateBox Implementation Roadmap

**Purpose:** the authoritative execution queue. Reconciled 2026-09-02
from the full commit history (159 commits), every `docs/*.md` design
document, `docs/CHECKPOINTS.md`, `docs/OPERATIONAL-DECISIONS.md`'s full
64-entry decision log, `docs/CAPABILITY-REGISTRY.md`, and live system
state (services, GPIO, I2C, USB, `systemctl --failed`) - not from the
most recent prompt alone. See the reconciliation's own record: `docs/
OPERATIONAL-DECISIONS.md`, "Roadmap Reconciliation" entry (top of file
as of this writing).

**Rule for future sessions/prompts:** a new prompt UPDATES or ADDS rows
here. It does not replace this document, and a row does not disappear
because a later prompt discussed something else. When an increment
finishes: update its row's evidence, checkpoint normally (`docs/
CHECKPOINTS.md`), come back here, pick the next actionable row. A clean
commit/deploy/checkpoint is not a stop condition by itself.

**Status vocabulary** (assigned by evidence, not by how detailed a
design doc is):

| Status | Meaning |
|---|---|
| PLANNED ONLY | Named as intent; no design or code yet. |
| DOCUMENTED ONLY | A design doc exists; no source code implements it. |
| PARTIALLY IMPLEMENTED | Some real code/UI exists; a meaningful part doesn't. |
| IMPLEMENTED IN REPO, NOT DEPLOYED | Source exists and is correct; not on the live site. |
| DEPLOYED, NOT LIVE-VERIFIED | On the live site; not actually exercised/checked there. |
| IMPLEMENTED + DEPLOYED + LIVE-VERIFIED | Working, on the live site, and directly confirmed there. |
| INTENTIONALLY DEFERRED | Considered, consciously not pursued now, reason on record. |
| BLOCKED BY HARDWARE | Needs hardware not physically present (checked live, not assumed). |
| BLOCKED BY OPERATOR DATA | Needs the operator's own real-world data (location, contacts, etc). |
| BLOCKED BY OPERATOR DECISION | Needs a privacy/security/ownership choice that isn't mine to make. |
| SUPERSEDED | Replaced by a later decision; kept for history, not active. |

---

## 1. Core PirateBox functionality

| Feature | Status | Evidence / blocker | Next action | Docs |
|---|---|---|---|---|
| File sharing (upload/download) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Original feature, live since first commit `a843225`; storage guard added Stage 24 | none | README.md |
| Chat | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | `chat.php`; live-verified this session (200, functional) | none | `docs/OPERATIONAL-DECISIONS.md` Phase 1 |
| Bulletin Board | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 22; `data/bulletin.json` currently empty (no posts yet - expected, not a defect) | none | OPERATIONAL-DECISIONS.md Stage 22 |
| Logbook (formerly "Guestbook") | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Renamed 2026-09-02 (`db06c6d`), message now optional, 3 real entries preserved live | none | OPERATIONAL-DECISIONS.md "Guestbook Reframed" |
| Found Device / Recovery messages | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 16; `purge_recovery_one`/`_all` admin actions exist | none | OPERATIONAL-DECISIONS.md Stage 16 |
| Help / About / "What can I do here?" | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 13/14; live-verified this session | none | OPERATIONAL-DECISIONS.md Stage 13/14 |
| Normal/Emergency Mode | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Emergency Mode foundation commit; `set_piratebox_mode.sh`; currently Normal | none | OPERATIONAL-DECISIONS.md "Emergency Mode" |
| purge_uploads.sh doesn't purge bulletin.json/recovery-messages.json | **IMPLEMENTED + DEPLOYED + LIVE-VERIFIED** | Fixed 2026-09-02, tested against an isolated scratch dir. Operator ran the install step 2026-09-02; `diff` against repo source confirmed byte-identical, executable, root-owned | none | OPERATIONAL-DECISIONS.md "purge_uploads.sh Completeness Gap Closed" |

## 2. Admin / maintenance / backup

| Feature | Status | Evidence | Next action | Docs |
|---|---|---|---|---|
| Admin/status page + auth gate | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Live-verified this session (401 without creds) | none | Phase 4 entry |
| Per-store clear actions (chat/logbook/bulletin/recovery) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | `admin/index.php` action switch, 10 actions confirmed present | none | Phase 4, Stage 16 |
| Backup (`piratebox-backup.timer`) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 25; installed live, "already produced a real automated backup" per CHECKPOINTS.md | none | Stage 25 |
| Restore (`tools/restore_piratebox_data.sh`) | IMPLEMENTED IN REPO, NOT LIVE-EXERCISED | Deliberately manual-only, never auto-run (correct by design - a real restore is destructive) | none - correct as designed | Stage 25 |
| Connection statistics (persisted 24h) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Post-Stage-32; **was silently broken since shipping** (`ProtectSystem=strict` blocked writes) - found and fixed 2026-09-02, confirmed via a real hourly rollover write | none | OPERATIONAL-DECISIONS.md "Connection-Stats Persistence Bug" |
| Versioning (`includes/VERSION` stamping) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 26; every deploy this session confirmed `VERSION` == `HEAD` | none | Stage 26 |

## 3. Reference Library / content

| Feature | Status | Evidence | Next action | Docs |
|---|---|---|---|---|
| Radio / Emergency / First Aid reference (national) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stages 2-4; INSTALLED per `/utility/about/`'s live reference-pack table. **Radio depth-expanded 2026-09-02** (roadmap item 3, see §3a below) | see §3a for the systematic audit and next actions | Stages 2-4, OPERATIONAL-DECISIONS.md "Deep Offline Reference Library: Radio Depth Expansion" |
| Navigation & Coordinates (universal) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 5 | none | Stage 5 |
| **World Reference Map (universal)** | **IMPLEMENTED+DEPLOYED+LIVE-VERIFIED** | Was CANDIDATE for "no WAN path" - that blocker was about the Pi's isolated visitor AP, not this session's own `eth0` management uplink (confirmed live). Sourced Natural Earth public-domain data, built `world-reference-map.svg`, wired into `/utility/maps/` always-visible (Travel-Mode-immune), verified live 2026-09-02 (`1db5fab`) | none | REFERENCE-CONTENT-DESIGN.md §5, OPERATIONAL-DECISIONS.md "World Reference Map" |
| Local Information | BLOCKED BY OPERATOR DATA | Stage 6/17; deliberately ships near-empty; framework complete, no code needed once data provided | operator supplies region/hospital/shelter/repeater data | Stage 6/17 |
| Document Library | BLOCKED BY OPERATOR DATA | Stage 7; empty by design until operator adds documents | operator adds files | Stage 7 |
| Local/Regional Map Catalog | BLOCKED BY OPERATOR DATA | Stage 5; ready-to-use, empty by design | operator adds local map files | Stage 5, REFERENCE-CONTENT-DESIGN.md |
| Global Offline Search | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 8/18; 99 indexed items as of 2026-09-02 (was 83 at last full audit, 92 after the World Map, 99 after Radio's depth expansion) | none | Stage 8/18 |
| "Take This With You" export/download | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 19; live-verified this session (200) | Field Tools calculators deliberately not bundled (§10 FIELD-TOOLS-DESIGN.md) - "worth revisiting if operators ask," not approved | Stage 19 |
| Manifest ("What's on this PirateBox?") | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 20 | none | Stage 20 |

### 3a. Deep Field Library content audit (2026-09-02)

**Guiding test:** would finding this PirateBox during a prolonged
infrastructure/communications failure be genuinely valuable, without
indiscriminately mirroring the Internet? Audited per-category before
picking where to expand, per instruction not to overbuild one subject
just because it was mentioned most recently.

| Category | Depth (entries) | Beginner use | Advanced use | Visual coverage | Provenance | Geo scope | Gap found |
|---|---|---|---|---|---|---|---|
| Radio Reference | 25 services + 6 modulation + **13 guides** (was 6) | Good - `<details>` accordion, plain-language guides, search/filter | Good after this increment - propagation/antenna/dB/SDR/simplex-repeater/polarization/connectors/phonetic/Morse all now present | 1 SVG spectrum chart (pre-existing); connector ID is a **table, not a diagram** | Per-entry `source_id` -> `sources.json` (FCC/ARRL/NOAA/ITU), `confidence` field on every entry | National (US band plans) + universal (propagation physics, phonetic/Morse standards) | **Closed this increment**: dB/dBm, SDR, simplex/repeater, polarization, connectors, phonetic alphabet, Morse code. **Still open**: connector/antenna-type diagrams (image, not table) |
| Emergency/Outage Reference | 21 topics | Good - already covers water storage, food safety, sanitation, shelter-in-place, power/generator/CO safety, evacuation | Moderate - practical guidance depth, not deep technical reference | None | Ready.gov/FEMA/CDC/NOAA/NFPA per-entry sourcing (Stage 3) | National | Already much broader/deeper than a first glance at "21 topics" suggests - **no action needed**, confirmed via full read, not assumed thin |
| First Aid Reference | 16 topics | Good - Red Cross "Check Call Care" framing, plain language | Shallow by design - deliberately conservative, not a clinical reference (correct for a liability-aware, non-professional-audience page) | **None - the one category where a diagram (CPR hand position, recovery position, Heimlich) would help most** | Red Cross/CDC per-entry sourcing (Stage 4) | National/universal | Visual gap real but **deliberately not rushed**: medical diagrams need verified redistribution rights from an authoritative source (Red Cross material is often not freely redistributable) - flagged as next action, not attempted from memory |
| Maps &amp; Location Reference | 2 maps (world + US, 2026-09-02) + 5 coordinate/GPS entries; local/regional catalog empty by design | Good - "at a glance" world/US maps, GPS/coordinate basics | Moderate - Universal+National layers now real; no Regional/State layer, no UTM/MGRS visual, no map-symbols reference | 2 SVG maps (world, US w/ AK+HI insets) | Natural Earth (public domain), USGS/NOAA/gps.gov | **Universal+National now real** (was Universal-only). Regional/State and Special-Purpose layers still absent | see updated next actions below |
| Local Information | Empty except 2 universal numbers | N/A until configured | N/A | None | Operator-provided | Local | Correctly BLOCKED BY OPERATOR DATA, not a content gap |
| Document Library | Empty | N/A | N/A | N/A | Operator-provided | Local | Correctly BLOCKED BY OPERATOR DATA |
| Field Tools | 3 tool pages (time/units/coordinates) | Good | Good for what's in scope | None (calculators/tables, not diagrams) | N/A (interactive tools); **Electrical Quick Reference (2026-09-02) cites standard Ohm's Law + AWG ampacity figures, reviewed against NEC-style references 2026-09-02 - figures confirmed already correctly using the conservative code-aligned breaker-sizing convention, not raw conductor ampacity; caveat text sharpened to say so precisely** | Universal | UTM/MGRS conversion deliberately out of scope (already re-audited, see §4) |

**New categories evaluated, not added (reasoned no, not silently skipped):**
- **Water/sanitation/shelter/food safety** - already substantially covered inside Emergency/Outage Reference (Water Storage & Boil-Water Advisories, Food Safety During an Outage, Sanitation Without Running Water, Shelter-in-Place vs. Evacuating). Adding a separate category would duplicate, not fill a gap.
- **Weather/environment** - storm-specific topics (thunderstorms, tornadoes, extreme heat/cold) already covered in Emergency Reference; a **cloud-identification visual chart** is a genuine, distinct, still-open gap (see below).
- **Computing/networking** - evaluated and rejected: doesn't fit this device's field/emergency-reference mission the way radio/first-aid/navigation do; PirateBox *is* the networking demonstration, not a subject it needs to teach.
- **Electrical/electronics reference** (Ohm's law, wire gauge/ampacity, common symbols) - genuinely absent, moderate field-repair value, not yet built - candidate for a future increment.
- **Knots/rigging/basic repair** - genuinely absent, field-useful, not yet built - candidate for a future increment, lower priority than Maps.
- **Signaling reference** (ground-to-air visual signals, distress signals) - Morse SOS now covered (this increment); a dedicated visual ground-to-air signal chart remains a genuine, small, not-yet-built gap.

**Next actions, in priority order** (highest user-visible value per
the audit above, feeding directly into implementation - not left as
prose):
1. ~~National-scope map (US)~~ - **done 2026-09-02**, see §3 above
   (`us-reference-map`, `tools/build_us_reference_map.py`).
2. **Cloud-identification visual reference** - genuinely useful, small,
   sourceable from NOAA/NWS public-domain material.
3. ~~Electrical/electronics quick reference~~ - **done 2026-09-02**
   (Ohm's Law + AWG ampacity tables, added to the existing Field Tools
   Units page - see OPERATIONAL-DECISIONS.md "Electrical Quick
   Reference"). Common electrical symbols as an actual diagram
   remains unbuilt (a visual asset, not a table) - lower-priority
   future item.
4. **First-aid visual diagrams** - real gap, but explicitly gated on
   finding an authoritatively-sourced, redistributable diagram set
   first (Red Cross material is often not freely redistributable) -
   do not attempt from model memory for anything medical.
5. **Connector/antenna-type diagrams for Radio** - upgrade the existing
   text table to an actual diagram once a sourcing approach is chosen.
6. **Regional/State map layer** - genuinely useful next Maps increment
   (the pipeline now trivially extends to a single state via the same
   Admin 1 dataset already fetched), but the *which state(s)* question
   is an operator scope decision (this device has no configured "home"
   region), not a sourcing blocker - action: ask the operator which
   state(s), if any, should get a dedicated regional pack, rather than
   guessing.
7. **Special-purpose maps** (UTM/MGRS visual grid reference, time-zone
   reference) - genuinely useful, not yet built. ~~Map symbols
   legend~~ - **done 2026-09-02**, see §3b below (USGS Topographic Map
   Symbols, retained as an original-source PDF rather than a
   PirateBox-authored summary).

### 3b. Layer 4: Original-Source Document/Visual/Media Library (added 2026-09-02)

**Concept:** the at-a-glance/learn/technical layers above are all
PirateBox-authored. A fourth layer sits alongside them: real,
authoritative original documents/images/charts (and, where genuinely
valuable, small audio) retained offline with full provenance - a
PirateBox summary should not replace a retainable authoritative
original. Exposed through the pre-existing `/utility/library/`
("Document Library," Stage 7) mechanism - it already had exactly the
right shape (category grouping, per-entry provenance fields, a
consistency checker) and was empty only because nothing verified-
redistributable had been sourced yet, not because it needed building.

**Source families investigated, redistribution basis confirmed or
rejected per source (not assumed uniformly):**

| Source | Redistribution basis | Status |
|---|---|---|
| NIST | US federal work, no US copyright (17 U.S.C. Sec. 105), verified against NIST's own policy page. SRD exception doesn't apply to narrative publications | **IMPLEMENTED+DEPLOYED+LIVE-VERIFIED** - SP 432 retained, cross-linked from Field Tools Time |
| USGS | Same basis, verified against USGS's own policy. Caveat: some USGS pages embed non-USGS third-party imagery that isn't PD | **IMPLEMENTED+DEPLOYED+LIVE-VERIFIED** - Topo Map Symbols retained, cross-linked from Maps |
| NOAA | Same basis, verified against NOAA Library's guidance. Caveat: NOAA material co-authored with a *non-federal* party isn't automatically PD | **IMPLEMENTED+DEPLOYED+LIVE-VERIFIED** - Sky Watcher Cloud Chart (NOAA+NASA, both federal) retained, cross-linked from Emergency + Radio |
| CDC | Same basis, verified against CDC's own copyright guidance | **IMPLEMENTED+DEPLOYED+LIVE-VERIFIED** - "Make Water Safe During an Emergency" retained, cross-linked to the Water Storage topic |
| FEMA | Same basis, verified against FEMA's own policy; Ready Campaign publications explicitly free to redistribute | **IMPLEMENTED+DEPLOYED+LIVE-VERIFIED** - Family Emergency Communication Plan retained, cross-linked to that topic |
| EPA | Same basis, verified against EPA's own copyright-policy framework (not on the original candidate list - found while researching US Forest Service wildfire material, which EPA co-publishes) | **IMPLEMENTED+DEPLOYED+LIVE-VERIFIED** - "Reduce Your Smoke Exposure" retained, cross-linked to the Wildfire & Smoke topic |
| USDA (FSIS) | Same PD basis expected (not yet confirmed - blocked before reaching the license question) | **LICENSING BLOCKED** *(access, not license)* - candidate URL (severe-storms food-safety brochure) returned HTTP 403 (Akamai bot protection); worth retrying via a different path or leaving for the operator to fetch manually |
| US Forest Service | Same PD basis expected | **SUPERSEDED BY BETTER SOURCE** - EPA's wildfire-smoke factsheet (co-developed with USFS) already fills this specific gap; no separate USFS document pursued |
| FCC | Already the citation basis for existing Radio content (Part 97/95/73) | **NOT USEFUL ENOUGH** *(for now)* - no additional FCC document identified as filling a gap beyond what's already cited; revisit if a specific need appears |
| SigIDWiki | Investigated directly (its own General Disclaimer): signal recordings/images are user-submitted "as is," explicitly "not under any licenses," users retain "sole responsibility for... intellectual property ownership" | **LICENSING BLOCKED** - no redistribution grant exists. Original non-SigIDWiki-derived signal-ID framework built instead (§3b/OPERATIONAL-DECISIONS.md) |
| ARRL | Not yet investigated per-publication (membership organization, not a blanket PD source) | **VERIFIED SOURCE, QUEUED** - verify per-publication before bundling anything; use as research reference only until then |

**Acquired so far** (`/utility/library/`, 6 documents total, ~8.4MB) -
see `docs/OPERATIONAL-DECISIONS.md` "Original-Source Document Library:
First Three Documents" and "Three More Original-Source Documents:
CDC/FEMA/EPA" for full provenance on each:
1. USGS Topographic Map Symbols (2.2 MB, `maps` category).
2. NIST SP 432 - Time and Frequency Services (1.9 MB, `reference`).
3. NOAA/NASA Sky Watcher Cloud Chart (2.5 MB, `reference`).
4. CDC "Make Water Safe During an Emergency" (730 KB, `emergency-firstaid`).
5. FEMA Family Emergency Communication Plan (1.0 MB, `emergency-firstaid`).
6. EPA "Reduce Your Smoke Exposure" wildfire smoke factsheet (346 KB, `emergency-firstaid`).

Total added this increment: **6.4 MB** (library files) - Reference/
Utility Library total is now ~6.65 MB (was 244 KB before this
increment; the two maps + JSON content are the rest).

**Signal Identification (Radio -> Signal ID), explicitly NOT built as
a SigIDWiki clone:** since SigIDWiki's own content isn't
redistributable, the next action is an **original, compact signal-
identification framework** using only content this project can
already verify - the real frequency/service data already in
`data/utility/radio/services.json` plus the modulation-type
explanations already in `modulation.json` - reorganized as an
identification aid (what to look for, not a waterfall-image gallery
this project can't legally source yet). No waterfall images or audio
samples until/unless a genuinely public-domain or clearly-licensed
source is found for those specifically (candidate: NTIA/FCC spectrum
charts, which are federal works, for a *frequency-allocation* visual -
distinct from SigIDWiki's per-signal waterfall images).

**Document Library UX:** kept the existing pattern rather than
inventing "Quick Reference / Learn / Technical / Documents & Sources"
labels - the existing per-subject `<details>` accordion (Radio/
Emergency/etc.) already serves layers 1-3, and `/utility/library/`
already serves layer 4 as a separate, linked destination (every
`hero-actions` footer already links to `/utility/library/` or
similar). Cross-linking from a subject page to a specific library
document (e.g. Radio -> the NIST time/frequency document) is a good
small future polish item, not yet done.

**Next actions, in priority order:**
1. ~~Original compact Signal Identification framework~~ - **done
   2026-09-02** (`data/utility/radio/signal-identification.json`, 8
   signal types, new "Signal Identification" section on
   `/utility/radio/` - see OPERATIONAL-DECISIONS.md "Original Signal
   Identification Framework, Not a SigIDWiki Clone"). Waterfall/audio
   examples remain unsourced (candidate: NTIA/FCC spectrum-allocation
   charts for a frequency-allocation visual, not per-signal crops).
2. ~~FEMA/FCC/CDC/USDA/US Forest Service candidate documents~~ -
   **substantially done 2026-09-02** (CDC, FEMA, EPA acquired; USDA
   FSIS access-blocked - HTTP 403, worth retrying later; FCC/USFS
   judged not-useful-enough/superseded for now - see the table above).
3. ARRL - verify redistribution terms for a specific candidate
   publication (e.g. a band plan chart) before deciding whether to
   bundle it or just cite it as a research source.
4. ~~Cross-links from subject reference pages to relevant Document
   Library entries~~ - **done 2026-09-02**, see §3c below
   (`includes/library_links.php`, metadata-driven via `catalog.json`'s
   own `related_pages` field - not hardcoded per-page).

### 3c. Document Library cross-linking (added 2026-09-02)

**Status: IMPLEMENTED + DEPLOYED + LIVE-VERIFIED.** See
`docs/OPERATIONAL-DECISIONS.md` "Document Library Cross-Linking" for
the full build/test record.

| Subject page | Links to | Direction |
|---|---|---|
| `/utility/maps/` | USGS Topographic Map Symbols | forward |
| `/utility/fieldtools/time/` | NIST SP 432 | forward |
| `/utility/emergency/` | NOAA/NASA Sky Watcher Cloud Chart | forward |
| `/utility/radio/` (severe-weather guide only) | NOAA/NASA Sky Watcher Cloud Chart | forward |
| `/utility/library/` | all three subject pages above | reverse ("See also") |

**Mechanism, for future documents:** add a `related_pages: [{"url",
"label"}]` array to a `catalog.json` entry - both the forward
(subject-page) and reverse (Library page) links pick it up
automatically, no PHP changes needed for a new cross-link, only for a
genuinely new subject page that doesn't already call
`piratebox_get_library_entries_for_page()`.

**Search discoverability**: audited and fixed in the same increment -
library documents are searchable by their source organization
(NOAA/NASA/USGS/NIST), not just title/description/tags -
`tools/build_search_index.py` extracts source-name keywords generically
for every library entry, not a one-off fix.

## 4. Field Tools

| Feature | Status | Evidence | Next action | Docs |
|---|---|---|---|---|
| Time/date tools + time-source status | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Built Post-Stage-32; `open_basedir` bug found+fixed same area 2026-09-02; status banner corrected from stale "not yet deployed" this session | none | FIELD-TOOLS-DESIGN.md |
| Unit conversion | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Same build | none | FIELD-TOOLS-DESIGN.md §2 |
| Coordinate converter (DD/DMS) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Same build | none | FIELD-TOOLS-DESIGN.md §2 |
| UTM/MGRS conversion | INTENTIONALLY DEFERRED | Explicit, reasoned scope decision ("not a good fit for avoid turning this into an enormous scientific-calculator project") - re-audited 2026-09-02, reasoning still holds | none - do not re-litigate without new instruction | FIELD-TOOLS-DESIGN.md §2 |
| Persisted "last NTP sync" timestamp | INTENTIONALLY DEFERRED | FIELD-TOOLS-DESIGN.md §4, deliberate | none | FIELD-TOOLS-DESIGN.md §4 |
| `date.timezone` php.ini fix | BLOCKED BY OPERATOR DECISION/PRIVILEGE | System-level `php.ini` edit, outside this project's narrow sudo grants, blast radius spans the whole app | needs an operator-run privileged step if ever pursued | FIELD-TOOLS-DESIGN.md §6 |

## 5. Device Memory / self-awareness

| Feature | Status | Evidence | Next action | Docs |
|---|---|---|---|---|
| Boot-event + undervoltage-event history | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | `data/device-history.json` write path confirmed fixed (`ReadWritePaths=`) same fix as connection-stats; **first actual write still unobserved** - no boot/undervoltage edge has fired since the fix | will self-confirm at the next real reboot or undervoltage onset - no action needed, just not yet witnessed | DEVICE-MEMORY-DESIGN.md §15 |
| "Since last review" summary | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | `mark_reviewed` action, `piratebox_device_memory_since()`; doc corrected 2026-09-02 from a stale "no such summary exists today" | none | DEVICE-MEMORY-DESIGN.md §3 |
| Capability/self-awareness state model | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | `capability_state.php`, `/utility/about/`, admin Capabilities table | none | ARCHITECTURE.md §6/§10 |
| Graceful self-diagnosis | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | `piratebox_diagnose_capability()`; doc corrected 2026-09-02 from a stale "not implemented"; storage DEGRADED/UNKNOWN diagnosis gap closed same day | none | ARCHITECTURE.md §13 |
| Progressive disclosure (Public->Operator->Diagnostics) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | `/utility/about/` (public) vs `admin/index.php` (operator) split, confirmed built to match `/utility/status/`'s existing exposure boundary | none | ARCHITECTURE.md §11 |
| Optional Field Sessions | DOCUMENTED ONLY | Concept only, `docs/DEVICE-MEMORY-DESIGN.md` §7 explicit "not implemented"; no GNSS/environmental hardware exists to summarize | needs GNSS/environmental hardware (none owned) AND a retention-policy decision | DEVICE-MEMORY-DESIGN.md §7 |
| GNSS history/exposure model | DOCUMENTED ONLY | ARCHITECTURE.md §9/§10, DEVICE-MEMORY-DESIGN.md §8 - semantics defined, nothing built | BLOCKED BY HARDWARE (no GNSS receiver) | ARCHITECTURE.md §9 |

## 6. Time / RTC / Power

| Feature | Status | Evidence | Next action | Docs |
|---|---|---|---|---|
| Time-source status (RTC/NTP/fake-hwclock detection) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Live: `rtc_detected: false, ntp_synchronized: false, fake_hwclock_installed: false` - all honestly reported | none | RTC-TIME-READINESS-DESIGN.md |
| Hardware RTC (DS3231) | BLOCKED BY HARDWARE | PLANNED (chip chosen), not purchased | operator purchase decision | CAPABILITY-REGISTRY.md |
| `fake-hwclock` software fallback | BLOCKED BY OPERATOR DECISION | CANDIDATE; needs an explicit package-install go-ahead (project rule: never install packages without one) | ask operator for go-ahead if wanted | RTC-TIME-READINESS-DESIGN.md, Stage 28 |
| Undervoltage/power monitoring | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Live `power.undervoltage_now: true` on current supply - honestly surfaced, diagnosis message present | operator's own PSU/cable investigation (hardware, not software) | POWER-UPS-DESIGN.md |
| UPS/battery hardware | DOCUMENTED ONLY | CANDIDATE, requirements only | BLOCKED BY HARDWARE + purchase decision | POWER-UPS-DESIGN.md |

## 7. Wi-Fi / AP / physical hardware

| Feature | Status | Evidence | Next action | Docs |
|---|---|---|---|---|
| Built-in `wlan0` AP (production) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Confirmed live: `phy#0 wlan0 type AP ssid PirateBox` | none | throughout |
| TP-Link TL-WN722N | SUPERSEDED / REJECTED | Confirmed live still plugged in (`lsusb`), but empirically proven AP-incapable (Phase 6, `EOPNOTSUPP`) - present, not in use as AP | none - correctly rejected, not a gap | "Wi-Fi adapter notes" |
| ALFA AWUS036ACM (MT7612U) upgrade | BLOCKED BY HARDWARE | Ordered ("OWNED/INCOMING"); confirmed live via `lsusb`/`iw dev` it has **not arrived** - only the old TP-Link is plugged in | test plan already written (§"Wi-Fi adapter notes"), executes itself once hardware arrives | OPERATIONAL-DECISIONS.md "Wi-Fi adapter notes" |
| GPIO25 shutdown button | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Live process `piratebox_button_daemon.py` running; real hardware power-cycle test passed (Stage 29 real-hardware confirmation) | none | Stage 29 |
| GPIO17 toggle switch (Normal/Emergency) | BLOCKED BY HARDWARE | "OWNED/INCOMING" per docs; confirmed live via `gpioinfo` GPIO17 is `input`, no consumer/daemon attached - genuinely not wired | operator physical wiring | PHYSICAL-CONTROL-UX-DESIGN.md |
| Momentary buttons (GPIO22/23/24/27) | BLOCKED BY HARDWARE | Same as above, "OWNED/INCOMING," not wired | operator physical wiring | PHYSICAL-CONTROL-UX-DESIGN.md |
| OLED (SSD1306, I2C) | BLOCKED BY HARDWARE | Confirmed live: no `/dev/i2c*` device node exists (I2C not even enabled) - genuinely not wired, not merely "not coded" | operator physical wiring + I2C enable | PHYSICAL-CONTROL-UX-DESIGN.md §1 |
| Physical transport lock | DOCUMENTED ONLY | CANDIDATE, design-only (accidental-input-resistance principles written, no mechanism chosen); GPIO25 daemon already reviewed and found to satisfy the model by construction (50ms debounce, 4s hold, no short-press path) | needs a lock mechanism choice (operator decision) | PHYSICAL-CONTROL-UX-DESIGN.md §4 |
| I2C multiplexer (PCA9548A/TCA9548A) | DOCUMENTED ONLY | CANDIDATE, no hardware chosen | BLOCKED BY HARDWARE | HARDWARE-INTEGRATION-DESIGN.md |
| Companion-device / capability-provider architecture | PARTIALLY IMPLEMENTED | `provider`/`provider_class` fields exist in `capability_state.php` (capability vs. provider distinction is real code); no actual companion device exists to provide anything yet - correctly "PirateBox itself" for every capability today | needs a real companion device to test against (none owned) | ARCHITECTURE.md §3, CAPABILITY-REGISTRY.md |
| SSID switching (Normal/Emergency, GPIO17-triggered) | DOCUMENTED ONLY | Full apply-then-verify-then-rollback design written, including a correction from an earlier draft (hostapd 2.10 has no config-validate flag, checked directly). Not implemented: the trigger is a confirmed GPIO17 mode transition, and GPIO17 is confirmed NOT wired (gpioinfo, see §7 above) | BLOCKED BY HARDWARE (toggle switch not wired) AND touches system networking config (`/etc/hostapd/hostapd.conf`) - outside this session's sudo grants regardless; Emergency SSID name also explicitly undecided (operator choice) | HARDWARE-INTEGRATION-DESIGN.md §10 |

## 8. Travel Mode / privacy

| Feature | Status | Evidence | Next action | Docs |
|---|---|---|---|---|
| Travel Mode (local-content suppression) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Live `travel-mode.json: {"travel_mode": false}`; verified both states this session (World Map stays visible, operator map catalog correctly hides) | none | TRAVEL-MODE-DESIGN.md |
| Automatic Travel Mode detection | INTENTIONALLY DEFERRED | TRAVEL-MODE-DESIGN.md §7, explicit "not implemented now, kept open for later" | needs a location-change signal this device doesn't have (no GNSS) | TRAVEL-MODE-DESIGN.md §7 |
| Privacy-preserving connection statistics | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Aggregate counts only, never MAC/IP/hostname history; persistence bug fixed+verified 2026-09-02 | none | Post-Stage-32 entry |
| Voluntary check-in board | INTENTIONALLY DEFERRED | Stage 23, "evaluated, deferred" - trust-model mismatch identified (anonymous-posting model unsuited to "accurate record of who is safe") | needs an identity/trust redesign decision - not mine to make unprompted | CHECKIN-BOARD-DESIGN.md |

## 9. Ownership / trust / transfer

| Feature | Status | Evidence | Next action | Docs |
|---|---|---|---|---|
| Trust-is-not-binary principle | DOCUMENTED ONLY | ARCHITECTURE.md §14, semantics only | none pending - principle, not a feature | ARCHITECTURE.md §14 |
| Transferable ownership mechanism | DOCUMENTED ONLY | ARCHITECTURE.md §15, explicitly "None of these is chosen or implemented" | BLOCKED BY OPERATOR DECISION - a real security/identity choice | ARCHITECTURE.md §15 |
| Data-aware ownership transfer (reset vs. preserve) | DOCUMENTED ONLY | ARCHITECTURE.md §16, explicitly "not decided here" | BLOCKED BY OPERATOR DECISION | ARCHITECTURE.md §16 |
| Self-describing/inheritable device | PARTIALLY IMPLEMENTED (was; wiring gap now closed) | `/utility/about/` + admin Capabilities table + **new admin "Physical wiring" section (2026-09-02, `includes/hardware_wiring.php`, live-verified)**. Remaining gaps: broader maintenance/repair narrative, the ownership/recovery concept itself | Ownership/recovery concept is BLOCKED BY OPERATOR DECISION (§15-16); a fuller "Tell me about yourself" maintenance narrative is a larger future increment, not yet approved in principle | ARCHITECTURE.md §17, OPERATIONAL-DECISIONS.md "Physical Wiring Self-Description" |

---

## Recovered process findings (roadmap reconciliation, 2026-09-02)

**Two numbering tracks existed and can look like one:** "Offline
Utility Library - Stage 1" through "Stage 10" (the utility library's
own sub-track) run in parallel with the main "Stage 13" through "Stage
32" track (`docs/OPERATIONAL-DECISIONS.md`, "Product Roadmap Expansion
(Stages 13-32) - scope note" explicitly calls out "Stages 1-12" as the
baseline the expansion built on). Not a data-loss risk in itself, but a
likely source of confusion if stage numbers alone are trusted without
reading the scope note.

**Nothing found to have silently fallen out of the historical plan
except one item:** `purge_uploads.sh`'s incomplete file list (missing
`bulletin.json`/`recovery-messages.json`) - flagged in Stage 25,
repeated verbatim in Stage 32's own end-of-batch checklist as item 7,
and never actually fixed across three later sessions' worth of work.
Genuinely forgotten, not deliberately deferred. **Fixed in repo the
same day this reconciliation happened** - see §1 above; pending only
the operator's install step.

**Two doc-drift cases found and fixed this session** (documented as
unimplemented when the code already existed): graceful self-diagnosis
(`docs/ARCHITECTURE.md` §13) and "Since last review" (`docs/
DEVICE-MEMORY-DESIGN.md` §3) - both corrected 2026-09-02, see §5 above.

**One stale blocker overturned:** the World Reference Map's "no WAN
path" reasoning was true for the Pi's isolated visitor AP but not for
this session's own `eth0` management uplink - checked live rather than
assumed, see §3 above.

**Everything else recovered from the historical stage list checks out
against live state** - no other case found where documentation claimed
something built that live inspection disproved, or vice versa.
