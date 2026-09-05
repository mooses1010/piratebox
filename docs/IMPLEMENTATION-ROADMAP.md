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
| Help / About / "What can I do here?" | IMPLEMENTED + DEPLOYED + LIVE-VERIFIED | Stage 13/14 base still live; **2026-09-02: fixed a real discoverability + staleness gap** - `/utility/about/` (the live, honest self-description page) was too buried under Utilities and had no early pointer from Help; `help.php` separately carried its own same-named "About This PirateBox" section with hardcoded capability bullets that had gone stale (e.g. "Physical mode/status controls (planned)" - actually built, GPIO25 shutdown button live, since an earlier stage). Fixed: `help.php` now opens with a 2-sentence pointer distinguishing "how do I use this" (Help) from "what is this device" (`/utility/about/`), and its own duplicate section was trimmed to stable narrative facts only, replaced the stale bullet list with a link to the live page instead of hardcoding capability claims a second place to go stale. Landing page's Upload-a-file focus and existing Help link preserved unchanged, only the link text sharpened ("Help / About This PirateBox"); no new landing-page cards added, per explicit instruction | none pending deploy | `docs/REFERENCE-CONTENT-DESIGN.md`, OPERATIONAL-DECISIONS.md Stage 13/14 |
| Discoverability/navigation audit (2026-09-02) | **IMPLEMENTED + DEPLOYED + LIVE-VERIFIED** | Targeted first-time-visitor audit (landing/Help/About/Utility index/Search/mobile/no-JS/naming consistency/dead ends), not a redesign, per instruction. Found and fixed one real naming inconsistency: the Utility Library index card said "Library" while the page itself is titled "Document Library" everywhere else it's referenced - now matches. Found one accepted, pre-existing, consistent (not newly introduced) tradeoff: `/utility/search/` uses the same shared JS-filtered reference-list pattern as every subject page - with JS off, the full ~178-entry index simply renders unfiltered rather than being hidden, which is functional (browser Ctrl+F still works) but not a true no-JS search experience; recorded as a possible future enhancement, not an urgent gap, since it's the same tradeoff already accepted everywhere else on the site, not something search introduced. Everything else checked (nav card completeness, cross-links, mobile viewport meta, breadcrumbs) was already sound | Full-text no-JS search fallback would be a real but nontrivial future increment (server-side search across all sections) - not attempted speculatively | this entry |
| Glossary / terminology (universal) | **IMPLEMENTED + DEPLOYED + LIVE-VERIFIED** | New 2026-09-02 (`/utility/glossary/`, **28 terms** across Computing/Radio/Maps/Electrical/**Weather (new category, 2026-09-02: beaufort-scale, watch-vs-warning)**) - see `docs/REFERENCE-CONTENT-DESIGN.md` §8 for the full architecture (reuses the existing reference-list pattern, no new UI/JS, `related_pages` links to deeper existing reference instead of re-explaining). Registered as reference pack `glossary-universal`; indexed by search; one-line, non-intrusive pointer added to Radio/Maps/Computing/Field-Tools-Units (not inline per-term links) | Populate remaining example terms from the original instruction as those categories grow further (not required now - tranches are deliberately representative, not exhaustive) | `docs/REFERENCE-CONTENT-DESIGN.md` §7-§8 |
| Normal/Emergency Mode | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Emergency Mode foundation commit; `set_piratebox_mode.sh`; currently Normal | none | OPERATIONAL-DECISIONS.md "Emergency Mode" |
| purge_uploads.sh doesn't purge bulletin.json/recovery-messages.json | **IMPLEMENTED + DEPLOYED + LIVE-VERIFIED** | Fixed 2026-09-02, tested against an isolated scratch dir. Operator ran the install step 2026-09-02; `diff` against repo source confirmed byte-identical, executable, root-owned | none | OPERATIONAL-DECISIONS.md "purge_uploads.sh Completeness Gap Closed" |

## 2. Admin / maintenance / backup

| Feature | Status | Evidence | Next action | Docs |
|---|---|---|---|---|
| Admin/status page + auth gate | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | **2026-09-02: real operator usability gap found and fixed, both operator actions completed** - first admin account created (`setup_admin_password.sh` run), `/admin/` confirmed returning 401/enforcing auth in the browser, updated `piratebox_status_helper.sh` reinstalled and confirmed live (`admin_auth.configured: true` present in `status.json`, `admin_panel` capability correctly showing `AVAILABLE`) - operator hit the nginx Basic Auth prompt at `/admin/` with no known credentials. Full audit (`docs/OPERATIONAL-DECISIONS.md` "Admin Panel Auth Readiness") found the underlying mechanism (`setup_admin_password.sh`, openssl-based, no missing dependency, deploy-excluded, reinstall-safe, correct permissions) was already fully correct - the gap was pure rediscoverability. Fixed: new `admin_panel` capability (self-description, `DEGRADED` not `UNAVAILABLE` when unconfigured - the secure default, not a fault), a `help.php` mention reachable pre-auth for a first-time operator, and an honest About-page wording tweak - without exposing credentials/paths to public clients (About only ever shows aggregate counts, never per-capability labels) | none - both operator actions completed and live-verified | Phase 4 entry, `docs/OPERATIONAL-DECISIONS.md` "Admin Panel Auth Readiness" |
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
| Computing &amp; Networking Reference (universal) | **IMPLEMENTED + DEPLOYED + LIVE-VERIFIED** | New 2026-09-02 (`/utility/computing/`, 10 entries) - see §3a discussion above for why this reverses an earlier "evaluated and rejected" call; live About page confirmed "INSTALLED (10)," computed live | none | new reference-packs.json entry `computing-universal` |
| Global Offline Search | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 8/18; 134 indexed items as of 2026-09-02 (99 after Radio's depth expansion increment; +5 Maps entries, +1 first-aid doc, +1 watch/warning guide, +10 Computing entries, +1 ground-to-air-signals topic added since) | none | Stage 8/18 |
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
| Radio Reference | 25 services + 6 modulation + **14 guides** (was 6; +watch-vs-warning terminology, 2026-09-02) | Good - `<details>` accordion, plain-language guides, search/filter | Good after this increment - propagation/antenna/dB/SDR/simplex-repeater/polarization/connectors/phonetic/Morse all now present | 3 SVG diagrams (spectrum chart, pre-existing; connector profile comparison, deployed/live-verified; **antenna-type comparison, built 2026-09-02**, `antenna-types.svg.php`, PirateBox-authored schematic - dipole/vertical/Yagi shapes plus a qualitative, explicitly-non-measured omni-vs-directional concept cue) | Per-entry `source_id` -> `sources.json` (FCC/ARRL/NOAA/ITU), `confidence` field on every entry | National (US band plans) + universal (propagation physics, phonetic/Morse standards) | **Closed**: dB/dBm, SDR, simplex/repeater, polarization, connectors, phonetic alphabet, Morse code, connector diagram, antenna diagram. Radio visual-reference gap from the original audit is now fully closed |
| Emergency/Outage Reference | 25 topics (was 21; +Ten Essentials, +Beaufort Wind Scale, +International Emergency Numbers, 2026-09-02) + **1 retained original document** | Good - already covers water storage, food safety, sanitation, shelter-in-place, power/generator/CO safety, evacuation, and now outdoor/field readiness and global emergency-number awareness | Moderate-good - practical guidance depth; **now backed by an authoritative full document for food/water during outages**, plus a genuinely universal Beaufort scale table (table-rendering support added to this page, mirroring Maps/Computing/Radio's existing pattern) | None | Ready.gov/FEMA/CDC/NOAA/NFPA/NPS per-entry sourcing (Stage 3); **FDA "Food and Water Safety During Power Outages and Floods" added and cross-linked** - a different USDA FSIS candidate on the same subject stayed HTTP-403-blocked, so an independent FDA source was found instead (source blocked != subject blocked). **NOAA/NWS Beaufort Wind Scale (2026-09-02)** - a US agency's presentation of an international WMO standard, correctly noted as universal, not US-specific. **International Emergency Numbers (2026-09-02)** - curated, cross-checked representative set (not a complete country list), directly improving usefulness outside the US | National + Universal (mixed, per-topic) | Broader/deeper than "21 topics" suggested even before this increment; now measurably deeper still - **no further action needed there** |
| First Aid Reference | 16 topics + **1 new retained original document (2026-09-02): DoD FM 4-25.11 First Aid, 227pp, full step-by-step illustrated procedures** | Good - Red Cross "Check Call Care" framing, plain language, now with a deep authoritative document one click away | Shallow by design at the PirateBox-authored layer (deliberately conservative, correct for a liability-aware page) - **but the visual/technical diagram gap is now closed via the retained original document** (CPR, recovery position, splinting, bleeding control, burns, and more, all with real illustrations) | **Closed 2026-09-02** - Red Cross material was confirmed not freely redistributable, so a different authoritative source (a public-domain joint US military field manual) was found instead, per the instruction that one blocked source doesn't mean the subject is blocked | Red Cross/CDC per-entry sourcing (Stage 4); **DoD FM 4-25.11 (PD-USGov-Military, verified via Wikimedia Commons' file tags + the manual's own "approved for public release" cover statement)** | National/universal | Visual gap closed without needing Red Cross material at all - see §3b below for full provenance |
| Maps &amp; Location Reference | 2 maps (world + US) + **10 reference entries (was 5), built 2026-09-02**: added map scale, contour-line reading, true-vs-magnetic-north (+ diagram), US time zones (+ table), world UTC reference (+ table); local/regional catalog empty by design | Good - "at a glance" world/US maps, GPS/coordinate basics, now also scale/contour/timezone/declination | Good after this increment - UTM/MGRS now has both text (pre-existing) and a visual grid-concept diagram; declination now has a diagram; still no Regional/State layer | 4 SVG visuals (world map, US map, **declination concept diagram (`declination.svg.php`) and UTM/MGRS grid concept diagram (`utm-grid.svg.php`), both built 2026-09-02**) | Natural Earth (public domain), USGS/NOAA/gps.gov, **time.gov (NIST/USNO) and IANA tz database for the new time zone entries** | Universal+National real; Regional/State layer still absent (operator scope decision, not a sourcing blocker) | see updated next actions below |
| Local Information | Empty except 2 universal numbers | N/A until configured | N/A | None | Operator-provided | Local | Correctly BLOCKED BY OPERATOR DATA, not a content gap |
| Document Library | Empty | N/A | N/A | N/A | Operator-provided | Local | Correctly BLOCKED BY OPERATOR DATA |
| Field Tools | **8 tool pages (time/units/coordinates/morse/subnet/wavelength/ohmslaw/checksum)** | Good | Good for what's in scope. Audited whether Morse/Subnet's shared boilerplate justified a common helper (2026-09-02) - only trivial `<noscript>`-text duplication found, result markup shapes differ meaningfully (textarea vs. table) for just 2-3 examples; **decided not yet justified**, revisit once 3+ tools clearly share an identical result shape, per instruction not to prematurely build a framework | **1 SVG diagram added 2026-09-02**: `electrical-symbols.svg.php` (resistor/capacitor/battery/ground/switch/fuse/diode-LED, standard IEC/ANSI-style schematic symbols) + a new Multimeter & Measurement Basics reference (continuity/voltage/resistance/current concepts, explicitly scoped to low-voltage/DC and not live-mains procedure) + **a new SI Prefixes reference table (giga through nano)**, integrated into the existing Units page rather than a separate page/calculator | N/A (interactive tools); **Electrical Quick Reference (2026-09-02) cites standard Ohm's Law + AWG ampacity figures, reviewed against NEC-style references 2026-09-02 - figures confirmed already correctly using the conservative code-aligned breaker-sizing convention, not raw conductor ampacity; caveat text sharpened to say so precisely** | Universal | **New Morse Code Converter (`/utility/fieldtools/morse/`, 2026-09-02)** - first "Reference -> Tool" implementation (see `docs/REFERENCE-CONTENT-DESIGN.md` §9): text<->Morse, server-rendered POST round trip works with JS off, JS enhancement reads the identical PHP-emitted mapping (no hand-duplicated table), malformed/unmapped tokens preserved and flagged rather than guessed at, cross-linked with Radio's Morse Code Reference and indexed by search. UTM/MGRS conversion deliberately out of scope (already re-audited, see §4) |

**New categories evaluated, not added (reasoned no, not silently skipped):**
- **Water/sanitation/shelter/food safety** - already substantially covered inside Emergency/Outage Reference (Water Storage & Boil-Water Advisories, Food Safety During an Outage, Sanitation Without Running Water, Shelter-in-Place vs. Evacuating). Adding a separate category would duplicate, not fill a gap.
- **Weather/environment** - storm-specific topics (thunderstorms, tornadoes, extreme heat/cold) already covered in Emergency Reference; cloud-identification visual chart done (§3b, NOAA/NASA Sky Watcher Cloud Chart); watch/warning terminology done (Radio guide); **Beaufort Wind Scale added 2026-09-02** (Emergency Reference, universal WMO standard, estimate wind without instruments). Genuinely still open: a compact "what actually differs, storm to storm" quick-comparison isn't built, but each individual hazard is already well covered - low priority.
- ~~Computing/networking - evaluated and rejected~~ - **reversed 2026-09-02 on explicit instruction**: PirateBox being a computing/networking appliance was reconsidered as a reason IN FAVOR of a compact reference (not a reason to skip one) - built as `/utility/computing/` (10 entries: IP addressing, private ranges, CIDR/subnet reference, DNS/DHCP, common ports, Wi-Fi terminology, Ethernet/cabling, USB/serial, checksums/hashes, text encoding). Deliberately scoped tight per the same instruction's own caution against "a giant generic Linux manual" - no shell/sysadmin/Linux-specific content, just the networking/computing concepts a field user might need regardless of platform.
- **Electrical/electronics reference** (Ohm's law, wire gauge/ampacity, common symbols) - genuinely absent, moderate field-repair value, not yet built - candidate for a future increment.
- ~~Outdoor/field: pre-trip safety checklist~~ - **done 2026-09-02**: new Emergency Reference topic "Ten Essentials for Outdoor/Field Safety" (`ten-essentials`), written originally (Tier 2 PirateBox Reference Material per `docs/REFERENCE-CONTENT-DESIGN.md` §7) from NPS's public-domain "The Ten Essentials" article - not copied verbatim, cited by source.
- ~~Knots/rigging/basic repair~~ - **done 2026-09-02** for the "basic field utility" portion: new `/utility/outdoor/` page, 8 knots/hitches (Bowline, Figure-Eight Stopper, Square/Reef Knot, Sheet Bend, Clove Hitch, Two Half Hitches, Taut-Line Hitch, Trucker's Hitch overview) - written originally as Tier 2 PirateBox Reference Material (knot-tying technique is functional/utilitarian, not copyrightable expression, so no source document is required for redistribution rights - see `docs/REFERENCE-CONTENT-DESIGN.md` §7). Each entry states what it's for AND what it's not for, explicitly excluding life-safety/climbing/rescue-rigging/lifting-people use per instruction. **Candidate Tier 1 document investigated, not retained**: US Army FM 5-125 (Rigging Techniques, Procedures, and Applications) is a plausible authoritative source (widely mirrored, part of an FM-5 series with several PD-tagged siblings on Wikimedia Commons) but direct cover-page/distribution-statement verification was blocked this session (no PDF-rendering tool installed - the existing poppler-utils blocker; a second mirror, globalsecurity.org, returned HTTP 403) - not retried further per instruction, and not retained without that direct confirmation. **Visual gap recorded honestly, not papered over**: no diagrams were built this increment - knot diagrams are genuinely harder to get right than the connector/antenna/electrical-symbol diagrams already built, and a rushed, unclear diagram would be worse than the current text-only entries. The Trucker's Hitch entry specifically flags itself as the one most in need of a diagram. Candidate for a focused future increment once a proper diagram design pass is done, not attempted speculatively.
- **First-aid visual extraction from FM 4-25.11** - genuinely desirable (the retained manual has real diagrams for CPR/splinting/etc. that could become web-friendly extracted images), but **blocked by tooling, not licensing**: this project's own `tools/check_library_catalog.py` documents that PDF-image extraction requires poppler-utils/similar, and CLAUDE.md §2 forbids installing any package without the operator's explicit go-ahead first. The whole source document is already confirmed public domain, so a derivative extraction would carry no licensing risk once the tooling question is resolved - this is purely "needs an operator-approved package install," not a content/rights blocker. Not attempted; flagged for the operator rather than worked around.
- ~~Signaling reference (ground-to-air visual signals)~~ - **done 2026-09-02**: new Emergency Reference topic "Ground-to-Air Emergency Signals" with an original diagram (`ground-to-air-signals.svg.php`) covering the 6 core standardized ICAO/FAA symbols (V/X/N/Y/F/arrow) - a publicly documented, internationally standardized code, not proprietary to any organization, so safe to author directly like the connector/antenna/electrical-symbol diagrams. Morse SOS (Radio page) and this ground-panel code are both covered now, as two different, complementary signaling methods.

**Next actions, in priority order** (highest user-visible value per
the audit above, feeding directly into implementation - not left as
prose):
1. ~~National-scope map (US)~~ - **done 2026-09-02**, see §3 above
   (`us-reference-map`, `tools/build_us_reference_map.py`).
2. ~~Cloud-identification visual reference~~ - **done 2026-09-02**
   (recognized during this reconciliation: already fulfilled by the
   NOAA/NASA Sky Watcher Cloud Chart acquired in §3b below, cross-linked
   from both Emergency and Radio's severe-weather guide - this row was
   stale, not a new gap).
3. ~~Electrical/electronics quick reference~~ - **done 2026-09-02**
   (Ohm's Law + AWG ampacity tables, added to the existing Field Tools
   Units page - see OPERATIONAL-DECISIONS.md "Electrical Quick
   Reference"). Common electrical symbols as an actual diagram
   remains unbuilt (a visual asset, not a table) - lower-priority
   future item.
4. ~~First-aid visual diagrams~~ - **done 2026-09-02, IMPLEMENTED +
   DEPLOYED + LIVE-VERIFIED**. Red Cross material stayed not-freely-
   redistributable, so a different authoritative source was found
   instead: DoD FM 4-25.11 First Aid (227pp, public domain, joint
   Army/Navy/Air Force/Marine Corps field manual retrieved via
   Wikimedia Commons, PD-USGov-Military tags verified), added to the
   Document Library and cross-linked from First Aid Reference. Full
   illustrated coverage of CPR, recovery position, bleeding control,
   splinting, burns, and more - not attempted from model memory, an
   actual authoritative document.
5. ~~Connector diagram for Radio~~ - **done 2026-09-02, IMPLEMENTED +
   DEPLOYED + LIVE-VERIFIED** (`connectors.svg.php`, an original
   PirateBox-authored schematic profile comparison of the 5 connector
   types already in the Feed Lines & Connectors guide's table - no
   sourcing/licensing question, same basis as the existing spectrum
   chart). Built on an isolated worktree branch
   (`worktree-continue-deep-library`) by a background session per its
   own policy against merging/deploying from there; the operator merged
   it into `main` (pure fast-forward to `e9bc4d3`) and ran the deploy.
   Live-verified in a follow-up recovery pass: `VERSION` matches `HEAD`
   exactly, both changed files byte-identical to the live tree,
   `/utility/radio/` (200) shows the diagram inline, zero failed units,
   no new nginx/PHP errors, full 206/206 regression - see
   `docs/CHECKPOINTS.md`.
   ~~Antenna-type diagrams~~ (dipole/vertical/Yagi) - **done 2026-09-02,
   IMPLEMENTED + DEPLOYED + LIVE-VERIFIED** (`antenna-types.svg.php`,
   wired into the existing "Antenna & Band Guidance" guide). Shows
   physical shape and a plain-language, explicitly-qualitative
   omnidirectional-vs-directional concept cue - deliberately NOT a
   measured/plotted radiation pattern, captioned as such, per the
   instruction not to make mathematically misleading pattern claims.
   Roadmap item 5 (connector + antenna diagrams) is now fully closed,
   deployed, and live-verified - see `docs/CHECKPOINTS.md`.
6. **Regional/State map layer** - genuinely useful next Maps increment
   (the pipeline now trivially extends to a single state via the same
   Admin 1 dataset already fetched), but the *which state(s)* question
   is an operator scope decision (this device has no configured "home"
   region), not a sourcing blocker - action: ask the operator which
   state(s), if any, should get a dedicated regional pack, rather than
   guessing. **Still open** - not touched this increment (correctly not
   guessed at).
7. ~~Special-purpose maps~~ (UTM/MGRS visual grid reference, time-zone
   reference) - **done 2026-09-02, IMPLEMENTED + DEPLOYED +
   LIVE-VERIFIED**. Five new `data/utility/maps/reference.json` entries: Map
   Scale, Reading Contour Lines (cross-referencing the retained USGS
   Topo Symbols document), True North vs. Magnetic North (with a new
   `declination.svg.php` concept diagram), United States Time Zones
   (full 9-zone table with the Arizona/Aleutian DST exceptions,
   live-checked against time.gov on 2026-09-02 rather than written from
   memory), and World Time Zones: UTC Reference Points (a clearly-
   labeled selection, not a false claim of a complete world time zone
   list). A new `utm-grid.svg.php` concept diagram was also added to the
   existing Coordinate Formats entry. Maps page gained generic table-
   rendering support (mirrors Radio's existing pattern) to support the
   two new tables. ~~Map symbols legend~~ - **done 2026-09-02**, see §3b
   below (USGS Topographic Map Symbols, retained as an original-source
   PDF rather than a PirateBox-authored summary).

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
| USDA (FSIS) | Same PD basis expected (not yet confirmed - blocked before reaching the license question) | **LICENSING BLOCKED** *(access, not license)* - candidate URL (severe-storms food-safety brochure) returned HTTP 403 (Akamai bot protection); **retried once 2026-09-02, still HTTP 403** - the block is durable, not transient; not retried further (per instruction not to hammer known-blocked URLs), leaving for the operator to fetch manually. **The subject itself is not blocked**: FDA's own "Food and Water Safety During Power Outages and Floods" (fda.gov/media/72124/download, confirmed public domain, HTTP 200) independently covers the same ground and was acquired instead - see below |
| US Forest Service | Same PD basis expected | **SUPERSEDED BY BETTER SOURCE** - EPA's wildfire-smoke factsheet (co-developed with USFS) already fills this specific gap; no separate USFS document pursued |
| FCC | Already the citation basis for existing Radio content (Part 97/95/73) | **NOT USEFUL ENOUGH** *(for now)* - no additional FCC document identified as filling a gap beyond what's already cited; revisit if a specific need appears |
| SigIDWiki | Investigated directly (its own General Disclaimer): signal recordings/images are user-submitted "as is," explicitly "not under any licenses," users retain "sole responsibility for... intellectual property ownership" | **LICENSING BLOCKED** - no redistribution grant exists. Original non-SigIDWiki-derived signal-ID framework built instead (§3b/OPERATIONAL-DECISIONS.md) |
| ARRL | Not yet investigated per-publication (membership organization, not a blanket PD source) | **LICENSING BLOCKED for the band-chart candidate specifically** - checked 2026-09-02: ARRL's own Frequency/Band Chart PDFs (`arrl.org/files/file/Regulatory/Band%20Chart/...`) are marked "Copyright (C) ARRL, All Rights Reserved," commercially sold via the ARRL Store - not a blanket-PD source and not redistributable as retained originals. Not re-litigated for every possible ARRL publication (a different, explicitly-licensed one could still exist), but the specific band-plan-chart candidate this project would actually want is closed. Continue using ARRL only as a citation (`source_id`), never as a retained original |
| FDA | Same PD basis as other federal sources - verified against FDA's own website policy (2026-09-02): "the contents of the FDA website...are not copyrighted...in the public domain" | **IMPLEMENTED + DEPLOYED + LIVE-VERIFIED** - "Food and Water Safety During Power Outages and Floods" retained (found as an alternate source after the USDA FSIS candidate on the same subject stayed blocked), cross-linked to Emergency's Food Safety and Power Outage topics |
| DoD (joint Army/Navy/Air Force/Marine Corps) | Federal work, public domain under 17 U.S.C. Sec. 105 - verified via Wikimedia Commons' PD-USGov-Military file tags plus the manual's own "approved for public release; distribution unlimited" cover statement | **IMPLEMENTED + DEPLOYED + LIVE-VERIFIED** - FM 4-25.11 First Aid (227pp, full illustrated procedures) retained, closes the previously-recorded First Aid visual-diagram gap without needing Red Cross material |

**Acquired so far** (`/utility/library/`, 8 documents total, ~9.6MB) -
see `docs/OPERATIONAL-DECISIONS.md` "Original-Source Document Library:
First Three Documents" and "Three More Original-Source Documents:
CDC/FEMA/EPA" for full provenance on the first 6; the 2 added
2026-09-02 are documented in this roadmap entry and their own
`catalog.json` provenance_notes:
1. USGS Topographic Map Symbols (2.2 MB, `maps` category).
2. NIST SP 432 - Time and Frequency Services (1.9 MB, `reference`).
3. NOAA/NASA Sky Watcher Cloud Chart (2.5 MB, `reference`).
4. CDC "Make Water Safe During an Emergency" (730 KB, `emergency-firstaid`).
5. FEMA Family Emergency Communication Plan (1.0 MB, `emergency-firstaid`).
6. EPA "Reduce Your Smoke Exposure" wildfire smoke factsheet (346 KB, `emergency-firstaid`).
7. **FDA "Food and Water Safety During Power Outages and Floods" (814 KB, `emergency-firstaid`) - added 2026-09-02.**
8. **DoD FM 4-25.11 First Aid (2.5 MB, `emergency-firstaid`) - added 2026-09-02.**

Total added this increment: **~3.3 MB** (2 new library files) -
Reference/Utility Library total is now roughly 10 MB including all
prior documents, maps, and JSON content (was ~6.65 MB before this
increment).

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

### 3d. Reference -> Tool audit (2026-09-02)

Per the new principle (`docs/REFERENCE-CONTENT-DESIGN.md` §9), audited
the candidate deterministic tools named across the reference library,
against the explicit bar: *would someone offline plausibly be glad it
was here* - not "is this mathematically possible."

| Candidate | Disposition | Reasoning |
|---|---|---|
| Morse text &harr; code | **Built** (`/utility/fieldtools/morse/`) | Real field/emergency-signaling use, existing reference already names the exact mapping needed, no ambiguity in scope |
| IPv4 CIDR/subnet calculator | **Built** (`/utility/fieldtools/subnet/`) | Genuine field-networking task (this device's own AP configuration is a live example); prefix<->netmask and network/broadcast/host-range are one coherent tool, not three |
| Ohm's Law solver (V/I/R/P) | **Built 2026-09-02** (`/utility/fieldtools/ohmslaw/`) | Reversed from "deferred": directly reinforces the existing Ohm's Law reference table, real recurring need (any 2-of-4 solve), cleanly scoped to DC resistive arithmetic with an explicit non-live-mains boundary |
| Frequency &harr; wavelength | **Built 2026-09-02** (`/utility/fieldtools/wavelength/`) | Reversed from "deferred": paired with the existing HF/VHF/UHF and Antenna & Band Guidance guides as the natural "look this up" moment; includes an explicit caveat that free-space wavelength is a reference value, not a build dimension, per instruction not to create misleading RF-engineering precision |
| dBm &harr; mW/W, dB power-ratio | **Deferred, not blocked** | Same reasoning - genuinely useful, not yet paired with a natural reference-page entry point |
| Decimal &harr; hex &harr; binary | **Rejected for now** | Common general-computing utility, but no specific field/emergency use case identified beyond "it exists" - exactly the "junk drawer of novelty converters" the principle warns against; revisit only if a concrete need surfaces |
| Bytes &harr; KiB/MiB/GiB | **Already covered** | Field Tools' existing Storage/data converter (`/utility/fieldtools/units/`) already does this - building a second one would be the explicit "no duplication" violation |
| Base64 encode/decode | **Rejected** | No concrete offline field/emergency use case identified - a "technically possible" utility, not a "someone would be glad it's here" one |
| Checksum/hash calculator | **Built 2026-09-02** (`/utility/fieldtools/checksum/`) | Reversed from "deferred" after the design pass it needed: unusually strong value specifically because PirateBox already stores/distributes files. Read-only against the existing uploads directory (no new upload path, filename only ever accepted if it exactly matches a real file the safe-listing function found, verified against path-traversal attempts); a separate paste-text panel needs no file access at all. SHA-256 presented as the hash to rely on; MD5 shown only for legacy-checksum matching, explicitly labeled not secure - per instruction not to recommend MD5/SHA-1 as secure hashes |
| Decimal degrees &harr; DMS | **Already covered, retrofitted 2026-09-02** | Field Tools' existing Coordinate Converter already did this, but JS-only - a real gap against the no-JS-required bar every tool since Morse follows. Retrofitted (not duplicated): wired the page to the canonical, already-tested `piratebox_dd_to_dms`/`piratebox_dms_to_dd` functions in `includes/fieldtools_convert.php` for a server-rendered POST fallback; `fieldtools.js`'s own instant-feedback path unchanged |
| Bearing/distance calculations | **Deferred, not blocked** | Technically sound (great-circle formulas are well-defined) but not yet paired with a clear reference-page entry point the way subnet/Morse were - candidate for a future Maps-adjacent increment |
| UTM/MGRS conversion | **Still deliberately out of scope** | Re-affirms the existing FIELD-TOOLS-DESIGN.md §2 decision (avoid turning Field Tools into "an enormous scientific-calculator project") - not reversed by this audit |
| Time-zone/UTC offset calculator | **Rejected as currently scoped** | This device's own time-confidence honesty model (RTC/NTP status) means a calculator implying trustworthy live time would contradict `docs/RTC-TIME-READINESS-DESIGN.md` - the existing Time & Date page's honest status display is the correct behavior, not a gap |

Two tools built this increment (Morse, Subnet); the "Deferred, not
blocked" rows are real candidates for a future increment, not silently
dropped - each has a specific reason it wasn't built *now* rather than
"not yet gotten to." Three more tools were built in a follow-up
increment the same day: Frequency/Wavelength, Ohm's Law Solver, and a
Checksum/Hash Calculator (the last reversed from its own "deferred"
row above after doing the design pass it needed - see its updated row
for the full reasoning). The existing Coordinate Converter was also
retrofitted (not duplicated) to add a server-rendered fallback, fixing
a real no-JS-required gap the audit surfaced by inspection rather than
by a prompted instruction.

### 3e. Global / non-US balance audit (2026-09-02)

Explicit audit of the reference library's content, per instruction, to
check for convenience bias (US federal public-domain material being
easiest to redistribute is not the same as the library actually
needing to be US-specific). Classified every major content area:

| Content | Classification | Assessment |
|---|---|---|
| Radio physics (propagation, dB/dBm, modulation, polarization, impedance/SWR) | Universal | Correctly universal already - physics doesn't have a nationality |
| Radio band plans/services (FCC Part 97/95/73) | US-specific, correctly labeled | Explicitly "National (US band plans)" scope in this roadmap and in the reference pack metadata - not presented as universal |
| First aid technique (CPR, splinting, bleeding control - FM 4-25.11) | Universal technique, US-sourced document | The *technique* is medically universal; the source happens to be a US DoD manual because it was the identified public-domain option, not because the technique is American |
| Emergency/hazard guidance (storms, floods, heat/cold) | Mostly universal, US-sourced | The hazards and responses apply anywhere; agency branding (Ready.gov/CDC) is a sourcing detail, not a scope limitation on usefulness |
| Maps: World Reference Map | Universal | Already correctly universal (Natural Earth data, always visible regardless of Travel Mode) |
| Maps: US Reference Map, US Time Zones | US-specific, correctly labeled | Explicitly scoped as such; paired with the universal World UTC Reference Points entry for balance |
| Electrical: AWG wire gauge, NEC ampacity | US/North America-specific, correctly labeled | AWG and NEC are real US/Canada conventions - the caveat text already says so; most of the rest of the world uses metric (mm&sup2;) wire sizing, which this table doesn't cover - a genuine gap, addressed this increment (see below) |
| Computing/Networking (IP addressing, DNS, ports, checksums, encoding) | Universal | Internet/computing standards are global by nature - correctly built with no US framing anywhere |
| Glossary (26 terms) | Universal | Same universal framing as the underlying reference material each term points to |

**One genuine gap found and closed this increment:** a **World
Electrical Power Standards** table (voltage/frequency/plug type by
major region) added to Field Tools Units' Electrical Quick Reference -
directly useful for carrying this device (or any electronics) outside
the US, which the existing AWG/NEC content did not address at all.
Curated to ~9 representative regions (not a 150+-country bulk list,
per instruction to curate rather than bulk-download), citing the
IEC's own World Plugs classification, with Japan's split-frequency
grid and Brazil's state-by-state voltage flagged specifically since
"one answer per country" doesn't always hold.

**Conclusion:** the library is not becoming US-centric in substance -
the underlying technical/physical/medical knowledge is already
universal wherever it appears, and every genuinely US-specific
reference (band plans, AWG/NEC, US time zones/map) is already
correctly labeled as national scope, not presented as universal. The
one real gap (world electrical standards) is now closed. Future
increments should keep applying this same test (universal knowledge
vs. US-specific reference vs. region-specific reference) rather than
assuming a US federal source automatically means US-only content.

### 3f. Visual reference audit (2026-09-02)

Reviewed the library for subjects where a diagram would materially
improve comprehension, per instruction, while working on knots.

**Built so far** (original PirateBox schematics, all self-authored,
no licensing question - see `docs/REFERENCE-CONTENT-DESIGN.md` §7's
Tier 3): connector types, antenna types, declination concept, UTM/MGRS
grid concept, electrical symbols, ground-to-air signals. **Retained
authoritative originals** (Tier 1, third-party PD documents, not
PirateBox-drawn): USGS Topographic Map Symbols, NOAA/NASA Sky Watcher
Cloud Chart.

**Genuine remaining gaps, in priority order:**
1. **Knot diagrams** - the freshest gap (§3a above). Deliberately not
   attempted this increment; knot geometry is harder to draw clearly
   than the connector/antenna/symbol diagrams already built, and a
   confusing diagram would be worse than the current text-only
   entries (per instruction: "do not pretend a poor diagram is safer
   than text"). The Trucker's Hitch entry specifically needs one most.
2. **First-aid procedure diagrams** (CPR hand position, recovery
   position, bleeding control, splinting) - licensing-clear (the
   retained FM 4-25.11 is already public domain and contains real
   diagrams) but **tooling-blocked**: extraction needs poppler-utils
   or similar, not installed, and this project's standing rule
   forbids installing a package without the operator's go-ahead. Not
   attempted, not worked around, per explicit instruction not to
   spend substantial time on this specific blocker.
3. **Antenna radiation-pattern nuance** - the existing antenna-types
   diagram already deliberately uses a qualitative "which directions
   are favored" cue rather than a measured polar plot (see its own
   commit); no further work identified as needed here.

Nothing else audited surfaced a comprehension gap severe enough to
justify a new diagram right now - most subjects (radio bands, computing
concepts, coordinate formats, Beaufort scale, emergency numbers) are
adequately served by text/tables, and adding a diagram "because a
subject exists" rather than because comprehension genuinely suffers
without one would be exactly the decorative-image anti-pattern the
instruction warned against.

### 3g. Original-source library expansion, round 2 (2026-09-02)

Second serious source-investigation pass, per explicit instruction
that the ~13MB library is nowhere near finished. Investigated broadly
across categories, retained what passed per-item verification,
recorded what didn't.

**Retained (4 new documents, ~9.6 MB, bringing the library to 12
documents / ~22 MB total):**

| Document | Source | Basis | Category | Scope |
|---|---|---|---|---|
| Map Reading and Land Navigation (FM 3-25.26) | US Army, 2005, 209pp, 7.8 MB | PD (17 U.S.C. Sec. 105) - Internet Archive's own "Public Domain Mark 1.0" tag + the manual's own "approved for public release" statement, same two-part confirmation as FM 4-25.11 | `maps` | Universal technique (UTM/MGRS/compass are international standards), US military authorship |
| United States Frequency Allocation Chart | NTIA/US Dept. of Commerce, Sept. 2025, 267 KB | PD - Wikimedia Commons' own federal-employee-work tag, exact byte match verified | `radio` | US-specific (this is a US spectrum allocation chart specifically, not a global one - labeled as such) |
| Electrical Safety (OSHA QuickCard) | OSHA/US Dept. of Labor, 2013 (rev. 2024), 39 KB | PD - OSHA's own published policy statement ("OSHA's rules are in the public domain") | `electronics` | Universal hazard concepts (shock, arc flash), US-agency authorship |
| Preparing for Emergencies: Guide for Communities | UK Cabinet Office, Sept. 2016, 285 KB | **Open Government Licence v3.0** (UK Crown copyright's default licence, confirmed as gov.uk's site-wide default unless stated otherwise) - a permissive grant, not a public-domain declaration, but functionally equivalent for redistribution here. First genuinely non-US-government source in this library | `emergency-firstaid` | **International** - the first real counterpart to this library's otherwise all-US-federal sourcing |

All four cross-linked via the existing `related_pages` metadata
mechanism (see §3c) to their relevant subject pages - no duplicate
document-list architecture needed, the existing Document Library
cross-link pattern already was the reusable "Related Documents"
pattern this round's instruction asked for (see the completeness
audit below).

**Investigated and rejected (licensing, not access):**

| Source | Finding | Disposition |
|---|---|---|
| WHO (Technical notes on drinking-water, sanitation and hygiene in emergencies) | "World Health Organization holds copyright to these materials with all rights reserved" | **Licensing blocked** - not retained. WHO material may still be cited as a research source for original PirateBox reference text in the future, never copied |
| ITU (Radio Regulations) | Free download explicitly for "personal use" only, not a redistribution grant | **Licensing blocked** - not retained. Continue citing ITU only as a source_id reference (already used for RF band nomenclature), never as a retained original |
| WMO (World Meteorological Organization publications) | Requires case-by-case permission beyond "short excerpts"; no blanket reuse grant | **Licensing blocked** - not retained. The existing Beaufort Wind Scale content correctly uses NOAA (a genuinely PD US federal presentation of the same international standard) instead, not a WMO document directly |
| EPA "Emergency Disinfection of Drinking Water" (Sept. 2017, EPA 816-F-15-003) | Licensing not in question (same PD basis as EPA's already-retained wildfire-smoke factsheet) - **deferred on redundancy grounds instead**: downloaded successfully (737 KB) but the PDF's text layer could not be extracted this session to confirm whether its content (reportedly precise bleach-dosing/measurement tables) is substantially distinct from the already-retained CDC "Make Water Safe During an Emergency" document or materially redundant with it | **Deferred, not rejected** - a genuinely different disposition than the licensing-blocked rows above. Not retained without confirming real added value first, per instruction to prefer the best source over accumulating near-duplicates; candidate for a focused future increment once content-uniqueness can actually be verified (e.g. once PDF-text extraction is available) |

**Document Library / Related Documents completeness audit:** the
existing `related_pages`-driven cross-link mechanism
(`includes/library_links.php`, §3c) already fully satisfies this
round's "documents should be visible from their subject category"
requirement - metadata-driven, one canonical catalog, no duplicate
lists possible. Auditing which subject pages actually call it found
one real gap: **Field Tools Units (Electrical)** and **Radio** had
never been wired to the page-level variant (Radio only had its
existing per-guide anchor variant) - both fixed this round, the same
reusable function, no new pattern invented.

**`poppler-utils` reconsidered, not installed:** with the library now
including two image/diagram-rich PD manuals (FM 4-25.11's first-aid
illustrations, FM 3-25.26's land-navigation figures/maps) alongside
the already-retained USGS/NOAA charts, the case for PDF-rendering
tooling to extract individual diagrams as inline reference images is
now measurably stronger than when this blocker was first recorded
against a single document - **this is now a reasonable candidate for
operator-approved installation**, not just a one-document nice-to-
have. Still not installed, per standing instruction; recorded here for
the operator's own decision, not acted on unilaterally.

**Library footprint:** 12 documents, ~22 MB total (was ~13 MB) -
trivial against the 128GB card; still curated, not bulk-mirrored.

### 3h. poppler-utils installed - exploiting retained manuals (2026-09-02)

The operator approved and installed `poppler-utils` (confirmed:
`pdfinfo`/`pdftotext`/`pdfimages` 25.03.0), closing the §3g/§3f
tooling blocker. This round used it to pull real value out of manuals
already retained, resolve one deferred redundancy question, and
re-verify one previously-inconclusive candidate - not just to acquire
more PDFs.

**First-aid diagrams (§3f gap #2, now closed for a small verified
set):** read FM 4-25.11's full text (pdftotext, 227 pages, form-feed
count matches page count exactly) and selected 5 diagrams, added to
`/utility/firstaid/`: pressure points (Fig 2-31), improvised
tourniquet (Fig 2-32), smothering/rolling for burning clothing (Fig
3-13), fracture types (Fig 4-1), board splints (Figs 4-18/4-19).
Explicitly searched the full text for "recovery position" first - the
term does not appear anywhere in this manual, so no recovery-position
diagram was added or invented; the page states this directly rather
than silently omitting it. Rendered as full manual pages (pdftoppm,
150dpi) rather than cropped figures - no image-editing tool is
installed to crop cleanly, and the full page also keeps each figure's
original caption/context attached, which is a genuine plus, not just
a workaround.

**Land-navigation diagram (§3f, land-nav wasn't flagged as a gap but
FM 3-25.26 was newly retained in §3g with figures never inspected):**
read FM 3-25.26's full text (209 pages, form-feed count matches) and
searched for terrain/contour figure references. Rather than pull the
individual hill/saddle/valley/ridge/draw/spur pages separately,
selected the single composite Figure 10-26 "Terrain features" - a
real topographic map excerpt with all ten standard landforms numbered
against one legend - added to the existing "Reading Contour Lines"
entry on `/utility/maps/`. The declination diagrams (Figs 6-8/6-9)
were reviewed and NOT added: the existing PirateBox-authored
`declination.svg.php` already covers that concept and the manual's
version would be a near-duplicate, not a complement.

**Knot diagrams (§3f gap #1, now closed for 6 of 8 knots): FM 5-125
re-verified and retained.** The §3g investigation left FM 5-125
unretained because the Internet Archive item page carried no explicit
rights tag and, without a PDF tool, its own cover/distribution
statement couldn't be checked directly. With poppler-utils now
installed, the PDF was downloaded and inspected directly: it carries
its own "DISTRIBUTION RESTRICTION: Approved for public release;
distribution is unlimited" statement and is signed by the Army Chief
of Staff - a Department of the Army field manual, public domain under
17 U.S.C. Sec. 105 like every other DoD manual in this library. Now
retained in full (169pp, 3.7MB) and used as the source for 5 diagram
pages covering 6 of the existing 8 knot entries: Bowline (Fig 2-11),
Square Knot + Single Sheet Bend (Figs 2-7/2-8, one page), Overhand +
Figure-Eight (Figs 2-3/2-4, one page), Clove Hitch (Fig 2-26), Two
Half Hitches (Fig 2-22). Taut-Line Hitch and Trucker's Hitch are not
covered by this manual (a rigging manual, not a camping/tarping
guide) and stay text-only - **the gap for those two is left honest,
not papered over with an invented or mismatched diagram**, per
instruction. Added a small reusable `diagram` field convention to
`data/utility/outdoor/reference.json` (image/alt/caption/source_line)
and generic rendering support in the page template, rather than
hardcoding per-knot markup.

**EPA water-disinfection document - deferred redundancy question
resolved, not auto-retained:** re-read via `pdftotext` rather than
retained on sight. It has a specific bleach-dosing table (drops per
quart/liter/gallon at 6% and 8.25% concentrations, doubled for
cold/cloudy water) plus a granular calcium hypochlorite (HTH) method
and an iodine tincture method - none of which are in the existing CDC
water-safety fact sheet, which stays at a higher level with no exact
measurements. Genuinely complementary, not a duplicate - retained
(EPA 816-F-15-003, 2pp, 737KB, PD).

New shared CSS (`.doc-figure-gallery`/`.doc-figure` in
`assets/styles.css`) added once and reused across firstaid/maps/
outdoor, documented in place as the pattern for future
selectively-extracted-diagram additions - not per-page one-off markup.

**Verification:** catalog.json validates, `tools/check_library_
catalog.py` clean (14/14), search index rebuilt (184 entries), `php
-l` clean on all changed pages, full five-suite regression still
287/287, all new pages/images smoke-tested via `php -S` (all images
200, both PDFs download correctly, `/utility/about/` live count reads
"Document Library: INSTALLED (14)").

**Library footprint:** 14 documents, ~25 MB total (was ~22 MB) -
still trivial against the 128GB card.

### 3i. Deep bookshelf pass, round 3 (2026-09-02)

Third source-investigation pass, per explicit instruction that the
library is "nowhere near the desired eventual depth." Investigated
across Measurement/Math, Outdoor/Field (survival), Weather, Radio/RF,
and two non-US candidates. Retained what passed verification,
rejected two on distribution grounds worth documenting carefully
(both looked promising at first glance), deferred two on access.

**Retained (2 new documents, ~15.8 MB):**

| Document | Source | Basis | Category | Scope |
|---|---|---|---|---|
| Guide for the Use of the International System of Units (SI), NIST SP 811 | NIST, 2008 Ed., 90pp, 1.9 MB | PD (17 U.S.C. Sec. 105), hosted directly by nist.gov itself | `reference` | Universal (SI is an international standard) |
| Thunderstorms, Tornadoes, Lightning... A Preparedness Guide | NWS/NOAA, ~2010, 20pp, 13.9 MB | PD (17 U.S.C. Sec. 105) | `reference` | US-specific framing (NWS watch/warning terms) but hazard content is broadly applicable |

NIST SP 811 fills the "Measurement/Math/General Technical" priority
subject the mission brief called out as unaddressed - its Appendix B
conversion-factors table (US customary <-> SI) is genuinely useful
well beyond any single subject page, so it's linked from Field Tools
Units rather than a narrower page. The NOAA guide complements the
existing Sky Watcher Cloud Chart (identifies clouds) with hazard-
specific safety actions (what to do about severe weather) - checked
via pdftotext for substance before retaining, not assumed useful from
its title alone.

**Investigated and REJECTED - distribution restriction, not just
copyright (both worth recording in detail):**
- **FM 3-05.70 (FM 21-76), Survival, May 2002** - the current/best-
  known edition of the classic Army Survival Manual, and a tempting
  obvious pick for Outdoor/Field. Its Wikimedia Commons page carries
  a standard PD tag. But its own cover page, read directly via
  pdftotext, states: "DISTRIBUTION RESTRICTION: Distribution
  authorized to U.S. Government agencies and their contractors only
  ... Other requests for this document must be referred to
  Commander..." plus a destruction notice. Unlike every other DoD
  manual in this library (all marked "approved for public release;
  distribution is unlimited"), this specific manual is NOT cleared
  for public redistribution regardless of its underlying copyright
  status - a real distinction between "this text is technically
  public-domain" and "DoD authorizes republishing this specific
  document," and exactly the kind of check the mission asked for
  rather than assuming government-authored implies redistributable.
  Not retained.
- **FM 21-76, Survival, October 1957 edition** - the older edition,
  investigated as a fallback after the above rejection. Its own cover
  page states plainly: "This manual contains copyrighted material" -
  a self-declared exception to the usual DoD-manual PD status (almost
  certainly third-party illustrations licensed for the original
  printing only). Not retained. **Net result: the Outdoor/Field
  survival-manual gap stays open, honestly** - no verified-clean
  edition was found this round rather than substituting a
  lower-quality but "safe" alternative.

**Investigated and DEFERRED - access, not licensing:**
- **Canada's "Your Emergency Preparedness Guide: 72 hours" (Public
  Safety Canada)** - a promising non-US candidate (national guide,
  ~similar shape to the already-retained UK Cabinet Office document),
  but the direct PDF URL from Government of Canada Publications
  redirected to an HTML catalog page (in French) rather than serving
  the file - not chased further with alternate URL guessing this
  round. Worth revisiting.
- **FCC Part 97 (Amateur Radio Service rules, 47 CFR Part 97)** - a
  clean, self-evidently public-domain fit for Radio/RF (US federal
  regulation text) that would round out the mission's explicit "do
  not substitute copyrighted ARRL material" instruction with a truly
  free source. Not retained this round: govinfo.gov serves the full
  Title 47 Volume 5 CFR (hundreds of pages covering every FCC-
  regulated service, not just amateur radio) with no conveniently
  isolated Part 97 PDF, and eCFR.gov is a live database, not a static
  document. Extracting just Part 97 cleanly needs more page-boundary
  work than this round budgeted for - not attempted further, not
  called blocked on licensing grounds (it isn't).

Verification: catalog.json validates, tools/check_library_catalog.py
clean (16/16), search index rebuilt (186 entries), full five-suite
regression still 287/287, both new documents smoke-tested via php -S
(both PDFs 200, both category cross-links render live), `/utility/
about/` reads "Document Library: INSTALLED (16)".

**Library footprint:** 16 documents, ~41 MB total (was ~25 MB) -
still trivial against the 128GB card; still curated per-item, not
bulk-acquired to hit a size or count target.

**One more retained this same round:** Controlling Electrical Hazards
(OSHA 3075, 2002), 71pp, 379KB - public domain (carries its own "This
publication is in the public domain and may be reproduced fully or
partially without permission" statement on p.1). The full-length
booklet behind the already-retained OSHA electrical-safety QuickCard:
real depth on shock/burn mechanics, insulation/guarding/grounding,
GFCIs, static electricity, and lockout/tagout - not a restatement of
the one-page card. Same related_pages (Field Tools Units, Ohm's Law
Solver). catalog.json re-validated (17/17), search index rebuilt (187
entries), full regression still 287/287, smoke-tested (200, cross-
link renders). **Library footprint: 17 documents, ~41 MB total.**

### 3j. Deep bookshelf pass, round 4: global, computing, mechanical, RF (2026-09-02)

Fourth source-investigation pass, addressing the specific gaps named
at the end of round 3: global/non-US coverage, Radio/RF depth,
Computing/Networking depth, and Mechanical/Repair (previously a total
gap). Also resolved a stale/superseded-content question in Food
Safety.

**Retained (6 new documents, ~17.9 MB):**

| Document | Source | Basis | Category | Scope |
|---|---|---|---|---|
| How to Prepare and Store Powdered Infant Formula During an Emergency | CDC, Dec 2024, 2pp, 2.4MB | PD (17 U.S.C. Sec. 105) | `emergency-firstaid` | Universal technique, US-sourced |
| Community Recovery (AIDR Handbook 2) | Australian Institute for Disaster Resilience, 2018 3rd ed., 148pp, 4.2MB | CC BY 4.0 (confirmed via the document's own copyright page) | `emergency-firstaid` | Universal principles, Australian institutional framing |
| Fastener Design Manual (NASA RP-1228) | NASA, March 1990, 100pp, 5.1MB | PD (17 U.S.C. Sec. 105), no adverse notice found | `mechanical-repair` (**new category**) | Universal (fastener engineering is not jurisdiction-specific) |
| Plane Geometry (Wentworth) | 1899, via Project Gutenberg, 326pp, 2.9MB | PD (pre-1929 publication + Gutenberg's own redistribution terms) | `reference` | Universal, explicitly marked historical |
| NEETS Module 10: Wave Propagation, Transmission Lines, and Antennas | US Navy, Sept 1998, 276pp, 2.4MB | PD (17 U.S.C. Sec. 105 + the document's own "approved for public release" statement) | `radio` | Universal RF theory |
| NEETS Module 13: Number Systems and Logic | US Navy, Sept 1998, 218pp, 1.1MB | PD (same basis as Module 10) | `computing` (**new category**) | Universal (binary/Boolean logic is timeless) |

Two new Document Library categories added (`categories.json`):
`mechanical-repair` ("Mechanical & Basic Repair") and `computing`
("Computing & Digital Fundamentals") - both previously had zero
retained documents despite existing subject pages
(`/utility/computing/`) or being explicitly named as priority gaps
(Mechanical/Repair had no subject page at all; the NASA fastener
manual is cross-linked from Field Tools Units instead, since a new
subject page wasn't warranted for one document).

**Global/non-US progress:** the AIDR Community Recovery handbook is
the library's second non-US source (after the UK OGL guide), and the
first under a Creative Commons license rather than a Crown-copyright-
style government licence - verified by reading the document's own
copyright page rather than assumed from AIDR's institutional
reputation. Two other jurisdictions investigated and NOT resolved
this round, recorded honestly rather than silently dropped:
- **Canada** (Public Safety Canada's "Your Emergency Preparedness
  Guide") - tried three different URL structures this round (a
  guessed publications.gc.ca PDF path, the getprepared.gc.ca
  publications catalog page, and the getprepared.gc.ca homepage) -
  all three now redirect into an HTML-only canada.ca hazard-by-hazard
  page structure with no PDF found. Likely retired as a downloadable
  PDF in favor of accessible HTML. **DEFERRED - access**, not chased
  with further URL-guessing this round per instruction not to hammer
  dead links.
- **New Zealand** (Civil Defence "Get Ready") - the main site
  (getready.govt.nz) returned HTTP 403 to automated fetches; the
  household-plan resources found are fillable HTML forms/PDF
  templates, not a substantive downloadable guide. **DEFERRED -
  access.**

**Radio/RF progress:** NEETS Module 10 directly addresses propagation,
transmission lines, characteristic impedance, SWR, and antennas -
genuine technical depth beyond the frequency-allocation chart, with
zero ARRL material involved. FCC Part 97 was not re-attempted this
round (already recorded as a real, specific extraction problem in
round 3, not a licensing question - re-litigating it wouldn't change
the outcome without new information). The broader NEETS series (~24
modules total, confirmed clean PD via two modules now retained) is
recorded as a strong source for future DC/AC fundamentals,
semiconductor, and test-equipment modules rather than bulk-imported
now.

**Computing/Networking progress:** investigated NIST SP 800-12 Rev 1
("An Introduction to Information Security") as a candidate - rejected
as a mismatch: it's a security-controls handbook, not a networking-
fundamentals reference, and retaining it under "Computing/Networking"
would misrepresent its content. NEETS Module 13 (binary/hex/Boolean
logic/gates) was retained instead as a better-fitting, equally-PD
foundational match for the specific gap named (character encoding/
checksum concepts rest on exactly this material). Genuine remaining
gap: nothing retained yet on TCP/IP, subnetting, DNS, DHCP, Ethernet,
or Wi-Fi specifically - recorded as **NOT YET ATTEMPTED**, not
blocked; the existing Computing page's structured reference content
already covers these at an explanatory level, so this is a "no source
document yet" gap, not a missing-topic gap.

**Mechanical/Repair progress:** NASA RP-1228 opens this previously-
untouched area with a genuinely deep, safety-appropriate reference
(fastener engineering, not hazardous repair procedure). Hand tools,
bearings, lubrication, adhesives, and measuring-tool references
remain **NOT YET ATTEMPTED** - a real, honestly-recorded gap for a
future round, not treated as complete after one document.

**Food Safety resolved (not a new document, a correction):**
investigated USDA FSIS (blocked, HTTP 403, not re-hammered) and an
older (2008) CDC food/water safety factsheet found during the same
search. Read the 2008 document's full text: its water-treatment
guidance overlaps with the already-retained EPA disinfection document,
and its brief infant-formula section is superseded by CDC's own
current (Dec 2024) dedicated guidance - retained the current specific
document (see table above) instead of the older general one, per the
explicit instruction that high-stakes content must stay current.
**REJECTED - superseded/redundant** for the 2008 document; not
retained.

Verification: catalog.json validates, tools/check_library_catalog.py
clean (23/23), search index rebuilt (193 entries), full five-suite
regression still 287/287, all 6 new documents and their category
cross-links (Emergency x2, Field Tools Units x2, Radio, Computing)
smoke-tested via php -S (all 200, all cross-links render, both new
category chips - Computing & Digital Fundamentals, Mechanical & Basic
Repair - render correctly on the Document Library page), `/utility/
about/` reads "Document Library: INSTALLED (23)".

**Library footprint:** 23 documents, ~59 MB total (was ~41 MB) -
still a small fraction of the 128GB card; still curated per-item, not
bulk-acquired.

### 3k. Exploit-the-PDFs pass 2, and a category-page audit (2026-09-02)

Continuation of the same round: inspected the newly-retained NOAA
weather guide and NASA fastener manual for high-value figures, and
re-confirmed the knot-diagram gap; then audited every subject page's
Document Library wiring, since the library has grown enough (12 to 23
documents this session) that a wiring gap would now be easy to miss.

**Weather visual added:** NOAA's "Tornado Fiction and Fact" table
(p.6 of the newly-retained preparedness guide) - myth-busting content
(lakes/mountains don't protect you, buildings don't "explode," don't
open windows, highway overpasses are dangerous, mobile home bathrooms
aren't safe) that materially adds to the existing tornado entry's
core actions rather than repeating them. Added via a new `diagram`
field on the `tornado` topic in `data/utility/emergency/topics.json`
and generic rendering support in `emergency/index.php`, reusing the
same `.doc-figure` pattern from Outdoor/Maps/Firstaid.

**Mechanical visual - investigated, deliberately NOT extracted:**
inspected the NASA Fastener Design Manual for a diagram/table to pair
with the new Mechanical & Basic Repair category. Found the single
most obviously useful candidate - Table V, Bolt Torque - carries its
own footnote: "Reprinted from Machine Design, Nov. 19, 1987. Copyright
1987 by Penton Publishing, Inc." The adjacent Tables VI-VIII are
similarly credited "[From ref. 8]" / "[From ref. 15]" to other
commercial sources. This is exactly the caveat NASA's own NTRS
disclaimer page warns about ("U.S. government works may contain
privately created, copyrighted works... used under license") -
found by actually reading the page rather than assuming a NASA
report's content is uniformly NASA's own. The full PDF remains
retained/downloadable (NASA's own NTRS distributes the identical
complete file), but no individual page from it was re-published as a
standalone image this round - the risk of embedded third-party
content in this specific document wasn't fully ruled out for the
earlier figures either (locknut/washer diagrams carry manufacturer-
name footnotes of unclear copyright significance), so none were used.
**A genuinely useful, safely-verified mechanical diagram remains a
NOT YET ATTEMPTED gap.**

**Knot gap re-confirmed, not resolved:** searched FM 5-125's full
text again (now that the whole manual is retained, not just excerpts)
for Taut-Line Hitch or Trucker's Hitch equivalents - neither appears
anywhere in the manual (confirmed via full-text search, not
assumption). The manual's "Rolling Hitch" serves a similar adjustable-
hitch purpose but is a different knot with different geometry from a
Taut-Line Hitch - substituting it would misrepresent the existing
text entry and was correctly not done. **Gap stays honest and open.**

**Category-page audit:** checked every subject page (Emergency,
Firstaid, Maps, Outdoor, Radio, Computing, and all seven Field Tools
subpages) for whether it actually calls `piratebox_get_library_
entries_for_page()` for its own URL. Found one real, previously-
invisible gap: **`/utility/fieldtools/ohmslaw/` had zero Document
Library wiring**, despite two catalog entries (both OSHA electrical
documents) already naming it in their own `related_pages` - the
cross-link was silently rendering nothing. Fixed by wiring in the
same function every other page uses; the other Field Tools subpages
(checksum, subnet, morse, wavelength) checked clean - no catalog
entry currently names them, so their lack of wiring isn't yet a bug.

Verification: catalog.json/topics.json validate, tools/check_library_
catalog.py clean (23/23, unchanged - no new documents this pass),
search index rebuilt (193 entries, unchanged), php -l clean on both
changed pages, full five-suite regression still 287/287, both changes
smoke-tested via php -S (tornado figure renders + image 200 on
Emergency; both OSHA documents now render on Ohm's Law Solver, 200).

**One more retained this same round:** Basic Machines (NAVEDTRA
14037, Feb 1994), 178pp, 8.2MB - public domain (same "approved for
public release" basis as every other Navy/DoD manual here). Covers
all six simple machines (lever, wheel and axle, block and tackle,
gears, wedge, inclined plane/screw), mechanical advantage, gear
ratios, and friction/bearings/lubrication - content-checked via
pdftotext before retaining, not assumed from the title. Directly
complements the Fastener Design Manual with the mechanical-principle
side of the new Mechanical & Basic Repair category. A second
candidate, "Tools and Their Uses" (NAVEDTRA 14256, covers hand tools
and measuring tools/calipers - the other half of this priority list)
was investigated but its known mirrors (maritime.org direct link,
archive.org catalog search) didn't resolve to a working PDF this
round - **DEFERRED - access**, not chased further with more mirror
guessing. catalog.json re-validated (24/24), search index rebuilt
(194 entries), full regression still 287/287, smoke-tested (200,
cross-link renders on Field Tools Units). **Library footprint: 24
documents, ~67 MB total.**

### 3l. Deep bookshelf pass, round 5: substantial expansion (2026-09-03)

Following the OLED hardware milestone, a large source-acquisition and
integration pass across the priority areas named for this round:
Computing/Networking, Electronics/Electrical, Radio/RF, Mechanical/
Repair, Math/Physics, Astronomy/Navigation, Materials/Chemistry, and
continued global-source investigation. Storage headroom explicitly
not treated as a constraint - the goal was depth and coverage, still
per-item-verified, not bulk for its own sake.

**Retained (10 new documents, ~209 MB):**

| Document | Source | Basis | Category | Scope |
|---|---|---|---|---|
| American Practical Navigator (Bowditch) | US GPO, 1966 ed., 1542pp, 128MB | PD (17 U.S.C. Sec. 105) | `reference` | Universal navigation/celestial theory; dated on electronic-aids sections only |
| NEETS Module 1: Matter, Energy, and DC | US Navy, 338pp, 6.7MB | PD + "approved for public release" | `electronics` | Universal |
| NEETS Module 12: Modulation | US Navy, Sept 1998, 230pp, 1.6MB | PD + "approved for public release" | `radio` | Universal |
| NEETS Module 16: Introduction to Test Equipment | US Navy, Sept 1998, 272pp, 1.9MB | PD + "approved for public release" | `electronics` | Universal |
| Calculus Made Easy (Thompson, 1910) | Project Gutenberg | PD (pre-1929) | `reference` | Universal, historical |
| NIOSH Pocket Guide to Chemical Hazards | NIOSH/CDC, 2007, 454pp, 6.0MB | PD (explicit "in the public domain" statement) | `materials-chemistry` (**new category**) | Universal |
| Linux Fundamentals (Cobbaut) | linux-training.be, 2015, 365pp, 6.7MB | GNU FDL 1.3, no invariant sections | `pi-linux-networking` | Universal |
| Linux Networking (Cobbaut) | linux-training.be, 2015, 294pp, 5.8MB | GNU FDL 1.3, no invariant sections | `pi-linux-networking` | Universal |
| Tools and Their Uses (NAVEDTRA 14256) | US Navy, June 1992, 368pp, 18.3MB | PD + "approved for public release" | `mechanical-repair` | Universal |
| A First Course in Physics (Millikan & Gale, 1906) | Internet Archive | PD (pre-1929) | `reference` | Universal, historical |

One new Document Library category added: `materials-chemistry`
("Materials & Chemical Safety Reference"), previously nonexistent.
`pi-linux-networking` (existing since an earlier round, always empty
until now) gets its first two documents.

**A real licensing catch, not assumed away:** the USDA "Complete Guide
to Home Canning" (Guide 1: Principles) was investigated as a strong
candidate for Food/Water/Sanitation depth - genuinely excellent,
authoritative content on safe canning (acidity, altitude adjustment,
pressure vs. boiling-water canners, botulism prevention). **REJECTED -
licensing unclear**: its own front matter credits primary authorship
to university researchers (Penn State, University of Georgia) under a
USDA-funded cooperative grant, not federal employees acting in their
official capacity - the standard "work of the US government" basis
this library relies on for every other USDA/CDC/DoD document doesn't
clearly apply here. No explicit public-domain or reproduction-rights
statement was found on the document or its hosting page (National
Center for Home Food Preservation, University of Georgia) despite a
real search for one. Not retained without that confirmation, even
though the content itself is exactly what this round was looking for -
matches this project's own standing rule that government-published
does not automatically mean government-authored-and-PD.

**Global-source investigation continued, no new document found this
round:** UK Met Office, Environment/Natural Resources Canada, and NZ
Transport Agency were checked for concrete downloadable technical
references with clear licensing - none yielded a working candidate
this round (mostly HTML-only content or no direct PDF surfaced).
**DEFERRED - access/no candidate found**, not a rejected-on-licensing
outcome; the two non-US sources already retained (UK OGL, Australia
CC BY 4.0) remain the current state, an acknowledged, still-open gap
rather than something silently dropped.

**Figure extraction, two genuinely valuable diagrams added:**
- NEETS Module 16, Figure 4-1 (a fully-labeled Simpson 260 analog VOM/
  multimeter) added to Field Tools Units' existing "Multimeter &
  Measurement Basics" section - materially improves a previously
  text-only bullet list by showing what the range switch, jacks, and
  meter face actually look like.
- NEETS Module 12, Figures 2-19/2-20 (carrier vs. modulated wave, and
  PM-vs-FM waveform comparison) added to Radio's existing "Modulation
  Types" section, immediately above the AM/FM/WFM/SSB entries.

Both figures use the same `.doc-figure-gallery` pattern established in
earlier rounds - no new CSS/markup pattern invented. Both are full-page
renders (not cropped) for the same reason established previously (no
image-editing tool installed; preserves captions/context as a
byproduct, not a limitation).

**Category-page audit (repeated, per instruction to keep checking as
the library grows):** every related_pages target across all 34 catalog
entries (`computing`, `emergency`, `fieldtools/ohmslaw`, `fieldtools/
time`, `fieldtools/units`, `firstaid`, `maps`, `outdoor`, `radio`)
confirmed to actually call `piratebox_get_library_entries_for_page()`
- no new wiring gaps found. No duplicate catalog IDs or titles across
all 34 entries.

Verification: catalog.json validates, `tools/check_library_catalog.py`
clean (34/34), search index rebuilt (204 entries), php -l clean on
both changed pages, full five-suite regression still 287/287, all 10
new documents and both new figures smoke-tested via `php -S` (all
downloads 200, all cross-links render on their 6 distinct target
pages, both figure images 200, new `materials-chemistry` and
previously-empty `pi-linux-networking` category chips render
correctly on the Document Library page), `/utility/about/` reads
"Document Library: INSTALLED (34)".

**Library footprint:** 34 documents, ~267 MB total (was ~67 MB) -
still under 0.3% of the 128GB card; still curated per-item, still
rejecting on real licensing findings rather than assuming government-
published means government-authored-and-PD.

**Two more retained this same round**, rounding out Electronics
coverage between the DC-fundamentals and test-equipment modules
already retained: NEETS Module 3 (Introduction to Circuit Protection,
Control, and Measurement - fuses, breakers, switches, relays,
meter-shunt/multiplier theory) and NEETS Module 7 (Introduction to
Solid-State Devices and Power Supplies - diodes, transistors,
rectifiers, power supply filtering/regulation), both US Navy NAVEDTRA,
September 1998, same "approved for public release" basis as every
other NEETS module here. catalog.json re-validated (36/36), search
index rebuilt (206 entries), full regression still 287/287,
smoke-tested (both 200, both cross-links render on Field Tools Units).
**Library footprint: 36 documents, ~271 MB total.**

### 3m. Deep bookshelf pass, round 6: audit, global source, mining the existing library (2026-09-03)

Following an audit of the 36-document collection's strengths/
weaknesses (electronics/radio building up well via NEETS; global
sources still thin at 2; USB/serial/character-encoding and ANSI-
standard-adjacent topics genuinely hard to source cleanly; materials/
chemistry has one strong anchor (NIOSH) but little else), this round
prioritized: one more targeted global-source attempt, rounding out RF
coverage, and - the round's second major task - mining figures out of
already-retained documents, not just newly-downloaded ones.

**Retained (2 new documents, ~9.1 MB):**

| Document | Source | Basis | Category | Scope |
|---|---|---|---|---|
| National Risk Register (UK, 2025 ed.) | UK Cabinet Office, 187pp, 4.7MB | Crown copyright, Open Government Licence v3.0 (confirmed on the document's own final page) | `emergency-firstaid` | UK-specific hazard framework; this library's third non-US document |
| NEETS Module 11: Microwave Principles | US Navy, Sept 1998, 192pp, 4.4MB | PD + "approved for public release" | `radio` | Universal; extends Modules 10/12 into the microwave/waveguide regime |

**Global-source diversity - one real addition, other leads investigated
and correctly not forced:**
- UK National Risk Register (above) - genuinely broad (natural,
  technological, and security hazards with individual risk summaries),
  cleanly OGL-licensed, content-checked via pdftotext before retaining.
- Canada (`getprepared.gc.ca`/`publications.gc.ca`) - tried again with
  a fresh, specific search rather than the same dead URLs; still no
  working direct PDF found (redirects to HTML-only pages or catalog
  pages, consistent with the same finding across three prior rounds).
  **DEFERRED - access**, now confirmed dead across enough independent
  attempts that further retries aren't a good use of time absent a
  structurally different lead.
- WHO WASH Technical Notes in Emergencies - investigated, but prepared
  for WHO by a university partner (WEDC, Loughborough) under the same
  "agency-published, not clearly agency-authored" pattern already
  flagged for the round-5 USDA canning guide, plus WHO's own general
  "all rights reserved" policy already confirmed in an earlier round.
  **REJECTED - licensing**, not re-litigated further.
- Japan Meteorological Agency English-language earthquake/tsunami
  guides - found, but no explicit license/redistribution statement
  surfaced this round. **DEFERRED - licensing unclear**, not chased
  further; a genuine candidate for a future round if a clearer rights
  statement can be found.
- Australia (Geoscience Australia topographic symbols) - no direct CC
  BY PDF found. **DEFERRED - no candidate found.**

**A real, deliberately-avoided near-miss:** NASA-STD-6016B ("Standard
Materials and Processes Requirements for Spacecraft") is genuinely
PD ("approved for public release") and was briefly downloaded, but
turned out to be a narrow aerospace-component compliance
specification (outgassing limits, spacecraft flammability
requirements) rather than a general materials-properties reference -
**REJECTED - low value for this library's purpose**, not retained
merely because it was easy and free.

**Second major task: mining figures from already-retained documents,
not just new ones.** A Poppler-assisted inspection pass across the
existing collection (not limited to round 6's own new documents):
- **American Practical Navigator (Bowditch)** - explicitly flagged by
  instruction as worth checking given its size. Located and extracted
  two genuinely high-value figures to the Maps page: Figure 1504 (a
  clean photograph of a clamp-screw vernier sextant, p.402) and
  Figures 1505a/b (the actual view through the telescope while sighting
  the sun, plus a labeled star-sighting diagram, p.403) - selected
  after inspecting the surrounding chapter (Instruments for Celestial
  Navigation) specifically because the two pages together teach both
  "recognize this instrument" and "here's how it's actually used,"
  not because they were the first figures found. Full-text extraction
  of this 1542-page scanned book was abandoned partway (10+ minutes,
  still running) in favor of a faster targeted approach: extracting a
  small page range, reading the printed page number in the header to
  calibrate the PDF-page-to-printed-page offset, then jumping directly
  to the target chapter - a useful technique note for any future large
  scanned-book figure extraction.
- **Basic Machines (NAVEDTRA 14037)** - Figure 1-2 ("Three classes of
  levers," with the companion "oars are levers" and "simple lever"
  diagrams on the same page) was located and inspected - genuinely
  excellent, clearly labeled. **Deliberately NOT integrated this
  round**: Mechanical & Basic Repair has no dedicated subject page to
  attach it to, and inventing a new content section on an existing
  page (rather than just adding a figure to content that already
  exists) was judged to be authorship beyond "wire into existing
  reference pages" - flagged as a good candidate for a future round
  that also builds a minimal Mechanical/Repair reference section, not
  silently dropped.
- USGS Topographic Map Symbols was checked but is itself only 4 pages
  - already a compact, purpose-built reference chart rather than a
  large manual with under-exploited figures buried in it; no
  additional extraction judged worthwhile.

**Category-page audit (repeated again):** all `related_pages` targets
across all 38 catalog entries re-confirmed wired; no duplicate IDs or
titles.

Verification: catalog.json validates, `tools/check_library_catalog.py`
clean (38/38), search index rebuilt (208 entries), php -l clean on the
changed Maps page, full five-suite regression still 287/287, both new
documents and both new Bowditch figures smoke-tested via `php -S`
(downloads 200, cross-links render, figure images 200), `/utility/
about/` reads "Document Library: INSTALLED (38)".

**Library footprint:** 38 documents, ~281 MB total (was ~271 MB) -
still under 0.3% of the 128GB card.

**Genuine remaining gaps, recorded honestly rather than papered over:**
USB/serial/UART and character-encoding (ASCII/Unicode) standards
proved hard to source both authoritatively AND freely this round -
the underlying ANSI/USB-IF standards are commercially copyrighted even
when referenced by federal specifications, and no clean PD/openly-
licensed substitute was found. A PirateBox-original reference table
(the ASCII code-point mapping itself is an uncopyrightable fact, only
a specific standard's prose/typesetting is protected) remains a
plausible future path, not attempted this round since it would be new
reference-content authorship rather than library acquisition/
integration. Materials/Chemistry still has only one strong document
(NIOSH); global-source diversity improved (2 -> 3 non-US documents)
but remains thin relative to the collection's US-federal majority.

### 3n. Deep bookshelf pass, round 7 + round 8 gap-driven follow-up (2026-09-03)

Round 7 (own commits, no roadmap row added at the time - closed
retroactively here, same pattern as `docs/CHECKPOINTS.md`'s round-6
gap): 3 new reference pages closing long-open gaps - Mechanical &
Repair (8 entries, 3 figures), Electronics (6 entries, 1 figure),
Materials & Chemical Safety (6 entries; 2 new OSHA QuickCards - GHS
pictograms, SDS structure - downloaded alongside the pre-existing
NIOSH guide). Two new Radio guides (SWR/impedance matching, microwave/
waveguide). Utility hub page given a full Spanish translation layer.
Library: 38 -> 40 documents, ~281 MB. DOT/PHMSA Emergency Response
Guidebook researched and deferred (Akamai bot wall).

Round 8 (bounded, gap-driven per explicit instruction not to make this
another acquisition-only round):
- **ERG deferral re-checked, not re-attempted blindly**: tried a
  genuinely different host (`rosap.ntl.bts.gov`, DOT's own National
  Transportation Library/ROSA P repository) rather than hammering
  `phmsa.dot.gov` again - also Akamai-blocked (403, same CDN vendor,
  different property). Confirms this is a broader bot-wall pattern, not
  a fluke of one host; deferral stands, not worth further attempts
  without a genuinely different (non-Akamai) route.
- **Computing/USB-serial/encoding gap partially closed**: `text-
  encoding-basics` now cites RFC 20 (ASCII format for Network
  Interchange, IETF, 1969) as its primary source instead of the
  generic `general-networking-education` - a real, freely-redistributable,
  authoritative standard directly on-topic. `usb-serial-basics` gained
  a secondary citation to the already-retained NEETS Module 13 (digital
  logic/number systems) - a partial, honest grounding (digital-signal
  representation, not USB/RS-232 specifically). No public-domain
  USB-IF-equivalent or RS-232-specific standard was found (USB-IF's own
  spec and TIA-232-F are both proprietary/licensed) - this narrower gap
  remains open, not misrepresented as closed.
- **Global-source diversity checked, not padded**: one UK candidate
  (Cabinet Office/UKHSA "Emergency Preparedness, Resilience and
  Response Concept of Operations," Open Government Licence v3.0 -
  confirmed clearly licensed) was found and **rejected on fitness, not
  licensing** - it's an internal governance/process framework document,
  not a practical reference a visitor could use, and this project does
  not lower its usefulness bar just to move a country-diversity count.
  No addition made; still flat at round 7's level.
- **Materials/Chemistry**: no further documents added this round -
  audited but no new genuinely useful, safely-scoped PD candidate
  identified in the time available; remains a real, acknowledged gap
  for a future round.
- **OLED instrument-panel redesign** (not a library change, but the
  same round): see `docs/HARDWARE-INTEGRATION-DESIGN.md` §14.
- **NTP/time root-cause diagnosis**: see `docs/RTC-TIME-READINESS-
  DESIGN.md` §0 and §6 above - a config bug, not unreachability;
  genuine operator-sudo gate, not resolved by this session.

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
| Boot-event + undervoltage-event history | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | **Write confirmed live 2026-09-03** (Power Integrity Diagnosis round) - `data/device-history.json`'s `undervoltage_daily` shows real counts (5 events, current UTC-day bucket); the write path fix is genuinely working, no longer merely theorized | `boot_events` array is still empty (not populated from real boot transitions) - a future pass, not urgent | DEVICE-MEMORY-DESIGN.md §15, POWER-INTEGRITY-DIAGNOSIS.md |
| "Since last review" summary | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | `mark_reviewed` action, `piratebox_device_memory_since()`; doc corrected 2026-09-02 from a stale "no such summary exists today" | none | DEVICE-MEMORY-DESIGN.md §3 |
| Capability/self-awareness state model | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | `capability_state.php`, `/utility/about/`, admin Capabilities table | none | ARCHITECTURE.md §6/§10 |
| Graceful self-diagnosis | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | `piratebox_diagnose_capability()`; doc corrected 2026-09-02 from a stale "not implemented"; storage DEGRADED/UNKNOWN diagnosis gap closed same day | none | ARCHITECTURE.md §13 |
| Progressive disclosure (Public->Operator->Diagnostics) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | `/utility/about/` (public) vs `admin/index.php` (operator) split, confirmed built to match `/utility/status/`'s existing exposure boundary | none | ARCHITECTURE.md §11 |
| Optional Field Sessions | DOCUMENTED ONLY | Concept only, `docs/DEVICE-MEMORY-DESIGN.md` §7 explicit "not implemented"; no GNSS/environmental hardware exists to summarize | needs GNSS/environmental hardware (none owned) AND a retention-policy decision | DEVICE-MEMORY-DESIGN.md §7 |
| GNSS history/exposure model | DOCUMENTED ONLY | ARCHITECTURE.md §9/§10, DEVICE-MEMORY-DESIGN.md §8 - semantics defined, nothing built | BLOCKED BY HARDWARE (no GNSS receiver) | ARCHITECTURE.md §9 |

## 6. Time / RTC / Power

| Feature | Status | Evidence | Next action | Docs |
|---|---|---|---|---|
| Time-source status (RTC/NTP/fake-hwclock detection) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Live: `rtc_detected: false, ntp_synchronized: false, fake_hwclock_installed: false` - all honestly reported; reporting mechanism itself needs zero code changes once NTP is fixed below (round 8) | none | RTC-TIME-READINESS-DESIGN.md |
| NTP sync (root cause found, round 8) | BLOCKED BY OPERATOR SUDO | `/etc/systemd/timesyncd.conf`'s `NTP=` line is a malformed, duplicated hostname (`time.cloudflare.comtime.cloudflare.com`) that fails DNS resolution - confirmed live. `eth0` (management interface) has a real, working Internet path, contradicting the Stage 28 assumption that no uplink existed | operator runs the one-line `sed` fix + `systemctl restart` documented in RTC-TIME-READINESS-DESIGN.md §0 | RTC-TIME-READINESS-DESIGN.md §0 |
| Hardware RTC (DS3231) | BLOCKED BY HARDWARE | PLANNED (chip chosen), not purchased | operator purchase decision | CAPABILITY-REGISTRY.md |
| `fake-hwclock` software fallback | NOT RECOMMENDED (round 8) | Superseded by the NTP fix above - a reachable NTP source makes "last known time" the wrong fix, not just an unapproved one | none - re-evaluate only if the NTP fix somehow can't be applied | RTC-TIME-READINESS-DESIGN.md, Stage 28 |
| Undervoltage/power monitoring + root-cause diagnosis | MONITORING IMPLEMENTED+DEPLOYED+LIVE-VERIFIED; ROOT CAUSE DIAGNOSED, NOT RESOLVED | Live `power.undervoltage_now: true`, confirmed *currently active* (not just sticky) via independently-verified bit semantics; full diagnosis (event timeline, failure-class ranking, fan-stall assessment, ALFA-independence confirmation) in `docs/POWER-INTEGRITY-DIAGNOSIS.md` - evidence points toward the external supply/cable path | operator: read the wall brick's label + cable type (§8 of that doc), then decide on a physical A/B supply/cable swap (§9) - hardware action, not software; blocks the AWUS036ACM production migration's power-aware gate until resolved | `docs/POWER-INTEGRITY-DIAGNOSIS.md`, `docs/POWER-UPS-DESIGN.md` |
| UPS/battery hardware | DOCUMENTED ONLY | CANDIDATE, requirements only | BLOCKED BY HARDWARE + purchase decision | POWER-UPS-DESIGN.md |

## 7. Wi-Fi / AP / physical hardware

| Feature | Status | Evidence | Next action | Docs |
|---|---|---|---|---|
| Built-in `wlan0` AP (production) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Confirmed live: `phy#0 wlan0 type AP ssid PirateBox` | none | throughout |
| TP-Link TL-WN722N | SUPERSEDED / REJECTED | Confirmed live still plugged in (`lsusb`), but empirically proven AP-incapable (Phase 6, `EOPNOTSUPP`) - present, not in use as AP | none - correctly rejected, not a gap | "Wi-Fi adapter notes" |
| ALFA AWUS036ACM (MT7612U) upgrade | **COMMISSIONED AS PRODUCTION AP (2026-09-03), single-client validated - extended multi-hour/multi-client soak still separate and not yet done** | `pb-ap` is live production: `hostapd`/`dnsmasq` bound to it, `10.0.0.1/24` held by it, real client (phone) associated, got a real DHCP lease (`10.0.0.206`), loaded `http://piratebox/` and the real site; `status.json`/`capability_state.php`/OLED all confirmed live-correct (auto-detect, not hardcoded); `wlan0` confirmed down/idle, reserved, not repurposed; nftables SSH-from-wireless protection fixed (was silently broken by the migration - now `iifname != {eth0,lo}`, covers any future radio); zero kernel/USB/mt76x2u errors and no new power-throttle bits across the entire round. Three real bugs found and fixed live during this round (udev rename rule, hostapd validation hang, dhcpcd static-IP left on the wrong interface) - see `docs/OPERATIONAL-DECISIONS.md` "ALFA Migration Round" for the full evidence chain of each | **Commissioning itself is done - do not re-run or "finish" it further.** The separate, still-open item is the power-aware gate's full evidence bar from `docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md` §8/§16 (multi-hour soak, *simultaneous* multi-client, sustained ordinary traffic, continuous `vcgencmd`/kernel monitoring for new transitions) - today's validation was one client, briefly, mostly idle. Treat that soak as a deliberate, separately-scheduled, supervised future round, not a blocker on the migration already being live and working | `docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md`, `docs/OPERATIONAL-DECISIONS.md` "AWUS036ACM Hardware Validation Round" / "External AP Architecture + Production Migration Readiness Round" / "Regulatory Domain Correction + ALFA Post-Regulatory Validation Round" / "ALFA Migration Round" |
| Host/management DNS isolation (`eth0` vs. `pb-ap`) | **IMPLEMENTED+DEPLOYED+LIVE-VERIFIED (2026-09-03)** | Incident: the Pi's own hostname resolution (including Claude Code's API calls) silently resolved public hostnames to `10.0.0.1` after `/etc/resolv.conf` went empty. Root cause was two independent bugs: dhcpcd's global `resolv.conf` hook unconditionally overwrote NetworkManager's real `eth0`-learned nameservers with nothing (eth0 is denied to dhcpcd, pb-ap has none to offer), and dnsmasq answers DNS over loopback regardless of `interface=pb-ap`, so glibc's 127.0.0.1 fallback hit the captive wildcard. Fixed with `nohook resolv.conf` (dhcpcd.conf), `except-interface=lo` (dnsmasq.conf), and explicit `rc-manager=file` (new `etc/NetworkManager/conf.d/98-piratebox-dns-ownership.conf`) so NetworkManager is the sole, deterministic owner of `/etc/resolv.conf`. Live-validated both sides independently (public DNS/HTTPS on `eth0`; wildcard DNS/DHCP/captive-portal/nftables SSH isolation unchanged on `pb-ap`) and through a full NetworkManager+dhcpcd+dnsmasq+hostapd restart cycle, not just the temporary manual `resolv.conf` recovery. Installer, migration, and rollback scripts updated so a fresh install or a future ALFA migration/rollback cannot recreate this | none | `docs/OPERATIONAL-DECISIONS.md` "Host/Management DNS Isolation Fix" |
| GPIO25 shutdown button | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Live process `piratebox_button_daemon.py` running; real hardware power-cycle test passed (Stage 29 real-hardware confirmation) | none | Stage 29 |
| GPIO17 toggle switch (Normal/Emergency) | BLOCKED BY HARDWARE | "OWNED/INCOMING" per docs; confirmed live via `gpioinfo` GPIO17 is `input`, no consumer/daemon attached - genuinely not wired | operator physical wiring | PHYSICAL-CONTROL-UX-DESIGN.md |
| Momentary buttons (GPIO22/23/24/27) | BLOCKED BY HARDWARE | Same as above, "OWNED/INCOMING," not wired | operator physical wiring | PHYSICAL-CONTROL-UX-DESIGN.md |
| OLED (SSD1306, I2C) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED (2026-09-03); Silly Mode added 2026-09-04 | I2C1 enabled (`dtparam=i2c_arm=on` + `i2c-dev` module, both persistent); `i2cdetect -y 1` confirms the display at 0x3C; a real frame written and visually confirmed by the operator; `piratebox-oled.service` running, four-page rotation (Status/Time/Network/Health) confirmed live on the physical display. Silly Mode: optional, user-toggled (`piratebox-silly {on,off,status}`), default off, expressive face/personality display state subordinate to Emergency Mode/faults - see `docs/OPERATIONAL-DECISIONS.md` → "OLED Silly Mode" | none for the OLED itself - GPIO22/23 (cycle/wake buttons) remain BLOCKED BY HARDWARE, see the row below | HARDWARE-INTEGRATION-DESIGN.md §12, PHYSICAL-CONTROL-UX-DESIGN.md §1, OPERATIONAL-DECISIONS.md "OLED Silly Mode" |
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
