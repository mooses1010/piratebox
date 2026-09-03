# Approved checkpoints

Running list of operator-approved, tested, known-good commits for the
Offline Utility Library project. Each entry is a point it's safe to roll
back to (`git checkout <hash>` or restore the matching backup under
`~/piratebox-backups/`). Updated after each stage is approved.

| Stage | Commit | Backup |
|---|---|---|
| Utility Stage 1 (scaffolding, nav) | `e428b57` | `~/piratebox-backups/utility-phase1-pre-20260901-044929/` |
| Emergency Mode foundation | `620c05a` | `~/piratebox-backups/emergency-mode-phase1-pre-20260901-052052/` |
| Stage 2: Radio Reference | `1ead465` | `~/piratebox-backups/radio-reference-phase1-pre-20260901-053341/` |
| Stage 3: Emergency / Outage Reference | `8cdfb28` | `~/piratebox-backups/emergency-ref-stage3-pre-20260901-060133/` |
| Stage 4: First Aid Reference | `58cd348` | `~/piratebox-backups/firstaid-stage4-pre-20260901-061123/` |
| Stage 5: Maps / Location Framework | `99049d8` | `~/piratebox-backups/maps-stage5-pre-20260901-061942/` |
| Stage 6: Local Information | `4d86072` | `~/piratebox-backups/localinfo-stage6-pre-20260901-062636/` |
| Deployment/mode-switch automation | `1149f4e` | (infrastructure only, no site content) |
| Stage 7: Document Library | `d615346` | `~/piratebox-backups/library-stage7-pre-20260901-064228/` |
| Stage 8: Global Offline Search | `e1f19bd` | `~/piratebox-backups/search-stage8-pre-20260901-064643/` |
| Stage 9: Utility Landing / Emergency Polish | `9e14b53` | `~/piratebox-backups/polish-stage9-pre-20260901-065258/` |
| Stage 10: Accessibility/Resilience/Performance Audit | `0bab1f7` | `~/piratebox-backups/audit-stage10-pre-20260901-065552/` (docs only, no site changes) |
| Stage 11: Hardware Integration Design | `80046c1` | (design doc only, no site/system changes) |
| Stage 12: Future Power / UPS Design | `2dc8700` | (design doc only, no site/system changes) |
| Stage 13: Identity/Transparency/About (incl. Stage 15 Connection Help) | `2081c4b` | `~/piratebox-backups/identity-stage13-pre-20260901-071759/` |
| Stage 14: Main-Page Onboarding | `afabb4e` | `~/piratebox-backups/onboarding-stage14-pre-20260901-072201/` |
| Stage 16: PirateBox ID / Found Device / Recovery | `8266484` | `~/piratebox-backups/recovery-stage16-pre-20260901-072524/` |
| Deploy-script data-loss fix (recovery-messages.json exclude) | `a4478f1` | (infra fix) |
| Stage 17: Local Info / Content Audit | `7924e01` | `~/piratebox-backups/audit-stage17-pre-20260901-073340/` |
| Stage 18: Global Search Expansion (verification only) | `0190a70` | (no site changes) |
| Stage 19: "Take This With You" Export System | `87c4307` | `~/piratebox-backups/export-stage19-pre-20260901-075834/` |
| Stage 20: PirateBox Manifest ("What's On This PirateBox?") | `b241a4e` | `~/piratebox-backups/manifest-stage20-pre-20260901-094955/` |
| Stage 21: Stats/Metrics/Appliance Status | `7579ff9` | `~/piratebox-backups/stats-stage21-pre-20260901-095339/` |
| Stage 22: Community Bulletin Board | `0b046eb` | `~/piratebox-backups/bulletin-stage22-post-20260901-101015/` (post-stage, not pre - see OPERATIONAL-DECISIONS.md Stage 22 process note) |
| Stage 23: Voluntary Check-in Board (evaluated, deferred) | `90a93ba` | (docs only, no site/system changes) |
| Stage 24: Resilience Audit - Low-Storage Guard | `f8557af` | `~/piratebox-backups/resilience-stage24-pre-20260901-104616/` |
| Stage 25: Backup / Restore for Live Community Data | `7024d96` | (tools/systemd only, no var/www/html changes - no live deploy needed) |
| Stage 26: Versioning - VERSION auto-stamp on deploy | `ebc1b5f` | (deploy script only, no var/www/html changes; not yet live - pending `setup_claude_automation.sh` re-run) |
| Stage 27: Build/Maintenance Pipeline Consolidation | `11dda03` | `~/piratebox-backups/pipeline-stage27-post-20260901-111137/` (post-stage, not pre - see OPERATIONAL-DECISIONS.md) |
| Stage 28: RTC / Time Readiness (audited, design only) | `a246bae` | (docs only, no site/system changes) |
| Stage 29: Physical Control UX Design | `d94a9d1` | (docs only, no site/system changes) |
| Stage 30: Accessibility Audit (verification only) | `bf984d7` | (no site changes) |
| Stage 31: Content Profiles (deployment-scenario reordering) | `571fefe` | `~/piratebox-backups/content-profiles-stage31-pre-20260901-113046/` |
| Stage 32: Final Expansion Review / Wrap-Up (Stages 13-32 complete) | `7dc04a0` | (audit only, no site changes) |

Live box mode should be **Normal** when unattended between test sessions.

**Resolved 2026-09-01:** `worktree-stage24` has been fast-forward-merged
onto `main` (`main` now at `334f7f1`, identical commit to
`worktree-stage24`'s tip). Verified directly: `git status` clean, and a
full `diff -rq` of the primary checkout's `var/www/html` against the
live deployed `/var/www/html` shows zero code/content differences -
only the already-documented deploy-excluded live files (`VERSION`,
QR codes, `chat.json`/`messages.json`/`recovery-messages.json`,
`uploads/`) differ, exactly as designed. Nothing was pushed to the
`origin` GitHub remote (unchanged project practice).

Of the Stage 32 follow-up checklist, item 1 (this fold) is now done.
Items 2-5 (`setup_claude_automation.sh` re-run, the
`piratebox-status.service` fix, the backup timer install, and
`fake-hwclock`) were each attempted this session via `sudo -n` /
directly and confirmed still blocked - all four genuinely require the
operator's own interactive password (and, for `fake-hwclock`, an
explicit package-install go-ahead), exactly as documented; none of this
session's automation covers them. Items 6 (populate Local Information)
and 7 (the `purge_uploads.sh` gap) remain as-is - the former needs the
operator's real-world data, the latter is a deliberately-deferred future
maintenance item, not touched here per instruction to not start new
work.

**Commissioning completed 2026-09-01:** items 2-4 done interactively
(operator ran each command, verified after each step) -
`setup_claude_automation.sh` re-run (deployed scripts now match the
repo, `VERSION` auto-stamping confirmed live), the `piratebox-status.
service` fix applied (status helper now succeeds, `status.json`
populating), and the `piratebox-backup.timer` installed (already
produced a real automated backup). `fake-hwclock` (item 5) remains
deliberately not installed - operator may add a hardware RTC instead.
Items 6-7 remain untouched, as before.

| Post-Stage-32 feature | Commit | Backup |
|---|---|---|
| Privacy-preserving connection statistics | `7493974` | `~/piratebox-backups/connstats-pre-20260901-124144/` |
| Canonical human-facing URL (`http://piratebox/`) | `e3863ba` | `~/piratebox-backups/piratebox-url-pre-20260901-130355/` |
| Travel Mode (privacy-preserving local info suppression) | `a6f5143` | `~/piratebox-backups/travel-mode-pre-20260901-160913/` |
| Stage 29 Implementation: Physical Shutdown Button (GPIO25) | `1fa83ee` | (no `~/piratebox-backups/` snapshot - no `var/www/html` changes, no live deploy involved; see `docs/OPERATIONAL-DECISIONS.md` for the staged discovery/bring-up/dry-run discipline that substituted for one) |
| Stage 29 Real-Hardware Confirmation: full power-cycle test of the shutdown button, on standalone wall-brick power | `33846ce` | (docs-only commit; no site/system changes - see `docs/OPERATIONAL-DECISIONS.md` for the post-boot verification results, including the open undervoltage finding against that specific power brick) |
| Field Tools / Offline Reference Instruments (time/date, unit conversion, coordinates - `docs/FIELD-TOOLS-DESIGN.md`) | `aafc652` | `~/piratebox-backups/fieldtools-pre-20260902-031945/` |
| Field Tools: open_basedir time-source fix | `58ef5bb` | (no backup - `piratebox_status_helper.sh`/web-tree fix only, see `docs/OPERATIONAL-DECISIONS.md`) |
| Architecture/Philosophy Formalization (Core/Operational/Optional, privacy, ownership, self-awareness - `docs/ARCHITECTURE.md`, `docs/CAPABILITY-REGISTRY.md`) | `d0ec128` | (docs only, no site/system changes) |
| Device Memory / Unattended-Operation Design (`docs/DEVICE-MEMORY-DESIGN.md`) | `f1326f0` | (docs only, no site/system changes) |

**Operator step completed 2026-09-02:** the `58ef5bb` commit's one
pending manual step - installing the updated `piratebox_status_helper.
sh` to `/usr/local/bin/` (root-owned, no dedicated installer script,
outside Claude's `sudo` automation) - was done by the operator
(`sudo install -m 0755 -o root -g root ...` + `sudo systemctl restart
piratebox-status.timer`), verified in a later session: installed copy
byte-identical to repo source, service ran successfully, live
`/run/piratebox/status.json` now carries a real `time_source` block
with honest values, the Time page renders the "available" branch, zero
new warnings, all services/timer active, zero failed units. See
`docs/FIELD-TOOLS-DESIGN.md` §9 and `docs/OPERATIONAL-DECISIONS.md`
for the full record. No code changed - documentation-only follow-up.

| Autonomous phase, increment 1 | Commit | Backup |
|---|---|---|
| Self-Awareness Implementation + Physical Transport/Input Safety Design (`includes/capability_state.php`, `/utility/about/`, admin Capabilities & Health section) | `636fd49` | `~/piratebox-backups/self-awareness-pre-20260902-052640/` |
| Fix: capability_state.php storage check hit open_basedir (off-by-one path depth) - found live immediately after deploying above, fixed and redeployed same session | `44e2f42` | (same backup as above covers this too - no new pre-change snapshot needed for a same-session fix) |
| Capability/Provider Distinction + Reference Content Foundation + Device Memory (first slice) (`docs/REFERENCE-CONTENT-DESIGN.md`, `includes/reference_packs.php`, `includes/device_memory.php`) | `8bdc981` | (no `~/piratebox-backups/` snapshot - continuation of the same autonomous-run checkpoint above, no destructive change) |
| "Since Last Review" Boundary (`data/review-boundary.json`, `mark_reviewed` admin action, `piratebox_device_memory_since()`) | `007323f` | (no `~/piratebox-backups/` snapshot - continuation of the same autonomous-run checkpoint above, no destructive change) |
| Graceful Self-Diagnosis, first slice (`piratebox_diagnose_capability()`) | `990a4b8` | (no `~/piratebox-backups/` snapshot - continuation of the same autonomous-run checkpoint above, no destructive change) |

**Autonomous run summary (2026-09-02, `92f2ab4`..`990a4b8`):** four
increments (self-awareness + physical transport/input safety design;
capability/provider distinction + reference content foundation +
device memory first slice; "since last review" boundary; graceful
self-diagnosis first slice), each tested, deployed, and live-verified
before the next began, per the operator's explicit "test/deploy/
verify/document/commit/continue - do not stop at boundaries"
instruction. One pending operator step remains, deliberately not
requested mid-run (batched): installing the updated
`piratebox_status_helper.sh` (adds `time_source` - already pending
since `58ef5bb` - and now also `boot_events`/`undervoltage_daily`) to
`/usr/local/bin/`. See `docs/OPERATIONAL-DECISIONS.md` for the full
per-increment record.

| Connection-Stats Persistence Bug Found + Fixed (systemd sandboxing - `etc/systemd/system/piratebox-status.service` gains `ReadWritePaths=/var/www/html/data`) | `cc19d89` | (no `~/piratebox-backups/` snapshot - no `var/www/html` changes; see `docs/OPERATIONAL-DECISIONS.md` for the full root-cause account) |

**Operator step completed 2026-09-02 (partial):** the pending
`piratebox_status_helper.sh` install above was run
(`sudo install ... && sudo systemctl restart piratebox-status.timer`).
Verified: installed copy byte-identical to repo source, `time_source`
correctly live, no service regressions. **Verifying it also surfaced a
real, more serious, pre-existing bug** - see the row directly above.
**New pending step, not yet requested of the operator mid-run
(batched):**

```
sudo install -m 0644 -o root -g root /home/moose/piratebox/etc/systemd/system/piratebox-status.service /etc/systemd/system/piratebox-status.service
sudo systemctl daemon-reload
sudo systemctl restart piratebox-status.timer
```

**Operator step completed 2026-09-02 (closed) - persistence fix
live-verified:** the operator ran the command above; installed unit
confirmed byte-identical to repo source. At the device's own next
hourly boundary (its clock runs a few minutes behind wall-clock - no
RTC, NTP unavailable by design on this offline device, an already-
documented gap, not new), `data/connection-stats.json` appeared for
the first time ever with a correct entry, zero journal errors on that
run or any run since, zero failed units, all 168 test assertions still
passing, no community data touched. `piratebox_get_connection_stats()`
exercised against the live deployed tree confirms the admin/public
read path renders it correctly. `data/device-history.json` itself
still awaits its own first qualifying edge event (boot or undervoltage
onset) to be independently confirmed - reasoned-fixed by the same
change, not yet directly observed - see `docs/OPERATIONAL-DECISIONS.md`
and `docs/DEVICE-MEMORY-DESIGN.md` §15 for the full account. No further
operator step pending from this fix.

| Guestbook reframed as "Logbook" (terminology only - `messages.php` route/`data/messages.json`/field names/action IDs all unchanged; message field made optional) | `db06c6d` | `~/piratebox-backups/logbook-rename-pre-20260902-071428/` |

**Deployed and live-verified 2026-09-02:** dry-run previewed exactly
the 14 intended `var/www/html` files (independently confirmed via an
itemized `rsync --dry-run -i`, cross-checked against `git diff --stat`);
real deploy ran clean, `VERSION` stamped to `db06c6d` matching `HEAD`
exactly. Live: nav/home/Help/"What can I do here?"/admin all render
"Logbook"; the three pre-existing real `data/messages.json` entries
(`Stage1-Verify`, `EmergencyMode-Verify`, `Final-Regression`) still
present and rendering completely unchanged - no migration, no data
touched; zero failed units; no new nginx/PHP errors since deploy (one
unrelated, already-known `open_basedir` warning in the error log
predates this deploy by ~3.5 hours and had zero new occurrences after
it - confirmed stale, not introduced here). The optional-message
behavior and CSRF/blank-submission/ID-increment correctness were
verified pre-deploy against an isolated scratch copy, not live data,
per the no-testing-on-community-data rule - see
`docs/OPERATIONAL-DECISIONS.md` for the full account.

| Implementation-focused audit, increment 1: World Reference Map CANDIDATE -> INSTALLED (Natural Earth public-domain data, static SVG, always-visible Maps &amp; Location Reference section) | `1db5fab` | `~/piratebox-backups/world-map-pre-20260902-073511/` |

**Deployed and live-verified 2026-09-02:** dry-run clean, real deploy
clean, `VERSION` stamped to `1db5fab` matching `HEAD` exactly. Live:
`/utility/maps/files/world-reference-map.svg` serves as
`image/svg+xml` at the expected ~183KB; the Maps &amp; Location
Reference page's new "World Reference Map" section renders it with
correct caption/source citation; `/utility/about/`'s live
self-awareness table shows `World Reference Map: INSTALLED (1)`,
computed from the real file, not hand-set; zero failed units; no new
nginx/PHP errors since deploy. Travel-Mode-visibility (stays shown
while the operator's own regional map catalog correctly hides) was
verified against an isolated scratch copy before deploy, not by
toggling the live operator setting merely to re-test something already
confirmed. Full four-suite regression: 171 assertions, 0 failures. See
`docs/OPERATIONAL-DECISIONS.md` for the full provenance/sourcing
account.

| Implementation-focused audit, increment 2: storage self-diagnosis gap closed (`piratebox_classify_storage()`, reuses the existing 2x-reserve threshold) + two stale-doc fixes (self-diagnosis, since-last-review) | `9c7fd10` | `~/piratebox-backups/storage-diagnosis-pre-20260902-074044/` |

**Deployed and live-verified 2026-09-02:** dry-run clean, real deploy
clean, `VERSION` stamped to `9c7fd10` matching `HEAD` exactly. Live:
admin page still correctly gated (401, not 500 - no crash); live
capability check against the deployed tree confirms `storage` correctly
reads `AVAILABLE`/`null diagnosis` against this device's real free
space (114GB of 123GB); zero failed units; no new nginx/PHP errors
since deploy. Full four-suite regression: 181 assertions, 0 failures.

| Implementation-focused audit, increment 3: Reference Library navigation coherence fixes (utility/index.php Maps card, README's Maps/Search bullets, FIELD-TOOLS-DESIGN.md status banner - all text-only) | `bcd061e` | `~/piratebox-backups/nav-coherence-pre-20260902-074337/` |

**Deployed and live-verified 2026-09-02:** dry-run clean, real deploy
clean, `VERSION` stamped to `bcd061e` matching `HEAD` exactly. Live
Utility Library card text confirmed updated; zero failed units; no new
nginx/PHP errors since deploy. Text-only change - regression suite
unaffected by design, re-run anyway and still 181/181.

| Roadmap reconciliation: `docs/IMPLEMENTATION-ROADMAP.md` created, historical intent recovered from 159 commits + 64 decision-log entries + live hardware state | `d4e6082` | (docs only, no site/system changes) |

| Roadmap item 1: `purge_uploads.sh` now removes `bulletin.json`/`recovery-messages.json` too (gap open since Stage 25/32, never fixed until now) | `1708cfd` | (no `~/piratebox-backups/` snapshot needed - not a `var/www/html` change) |

**Operator step completed 2026-09-02 (closed):** the install command
above was run. Verified: `diff /home/moose/piratebox/purge_uploads.sh
/usr/local/bin/purge_uploads.sh` byte-identical, executable
(`-rwxr-xr-x`), root-owned. No further step pending from this fix.

| Roadmap item 2: Physical wiring self-description (`data/gpio-wiring.json`, `includes/hardware_wiring.php`, new admin "Physical wiring" section - `docs/ARCHITECTURE.md` §17's named gap) | `008dd17` | `~/piratebox-backups/wiring-selfdesc-pre-20260902-080134/` |

**Deployed and live-verified 2026-09-02:** dry-run clean, real deploy
clean, `VERSION` stamped to `008dd17` matching `HEAD` exactly. Live:
admin page still correctly gated (401, no crash); wiring data file
reads correctly via the deployed tree (8 rows, shutdown button
correctly shows wired); zero failed units; no new nginx/PHP errors
since deploy. Full five-suite regression: 202 assertions, 0 failures.

| Deep field library, increment 1: Radio depth expansion (7 new guides - dB/dBm, SDR, simplex/repeater, polarization, connectors, phonetic alphabet, Morse code; content audit in `docs/IMPLEMENTATION-ROADMAP.md` §3a) | `d92a416` | `~/piratebox-backups/radio-depth-pre-20260902-094039/` |

**Deployed and live-verified 2026-09-02:** dry-run clean, real deploy
clean, `VERSION` stamped to `d92a416` matching `HEAD` exactly. Live
`/utility/radio/` confirmed 200 with the three new table-based guides
(Feed Lines, NATO Phonetic Alphabet, Morse Code Reference) present;
zero failed units; no new nginx/PHP errors since deploy. Search index
rebuilt to 99 entries. Full five-suite regression: 202/202.

| Deep field library, increment 2: United States Reference Map (`us-reference-map.svg` - 50 states + DC, CONUS + Alaska/Hawaii insets; new "national" scope reference pack) | `7efe098` | `~/piratebox-backups/us-map-pre-20260902-094742/` |

**Deployed and live-verified 2026-09-02:** dry-run clean, real deploy
clean, `VERSION` stamped to `7efe098` matching `HEAD` exactly. Live:
`us-reference-map.svg` serves as `image/svg+xml` at the expected size;
Maps page shows the new section; `/utility/about/` shows `United
States Reference Map: INSTALLED (1)`, computed live; zero failed
units; no new nginx/PHP errors since deploy. Full five-suite
regression: 206/206.

| Deep field library, increment 3: Electrical Quick Reference (Ohm's Law + AWG ampacity tables, Field Tools Units page) | `1e7f8c1` | `~/piratebox-backups/electrical-ref-pre-20260902-095048/` |

**Deployed and live-verified 2026-09-02:** dry-run clean, real deploy
clean, `VERSION` stamped to `1e7f8c1` matching `HEAD` exactly. Live
`/utility/fieldtools/units/` confirmed 200 with the new section and
NEC caution text present; zero failed units; no new nginx/PHP errors
since deploy. Search index at 101 entries. Full five-suite regression:
206/206 (unaffected by design - static content, no new calc logic).

| Deep field library, increment 4: Original-Source Document Library (USGS Topo Map Symbols, NIST SP432 Time/Frequency, NOAA/NASA Cloud Chart - 6.4MB, each individually verified public domain) | `c64c71b` | `~/piratebox-backups/doc-library-pre-20260902-100205/` |

**Deployed and live-verified 2026-09-02:** dry-run clean, real deploy
clean, `VERSION` stamped to `c64c71b` matching `HEAD` exactly. Live:
all three PDFs serve as `application/pdf` at their exact byte sizes;
Document Library page shows all three; `/utility/about/` shows
`Document Library: INSTALLED (3)`, computed live; zero failed units;
no new nginx/PHP errors since deploy. `tools/check_library_catalog.py`
clean (3/3 agree). Full five-suite regression: 206/206.

| Deep field library, increment 5: Original Signal Identification (8 signal types, `radio/signal-identification.json` - explicit non-SigIDWiki-derived framework, transparent about the licensing decision on-page) | `cdd0682` | `~/piratebox-backups/signal-id-pre-20260902-100552/` |

**Deployed and live-verified 2026-09-02:** dry-run clean, real deploy
clean, `VERSION` stamped to `cdd0682` matching `HEAD` exactly. Live
`/utility/radio/` confirmed 200 with the new "Signal Identification"
section, a specific entry (CW), and the SigIDWiki transparency note
all present; zero failed units; no new nginx/PHP errors since deploy.
Search index at 112 entries. Full five-suite regression: 206/206.

| Deep field library, increment 6: Document Library cross-linking (`includes/library_links.php`, metadata-driven via `catalog.json`'s `related_pages` field; 4 subject pages + reverse links + search keyword fix) | `f04dbeb` | `~/piratebox-backups/library-crosslink-pre-20260902-101556/` |

**Deployed and live-verified 2026-09-02:** dry-run clean, real deploy
clean, `VERSION` stamped to `f04dbeb` matching `HEAD` exactly. Live:
all five pages (Maps, Field Tools Time, Emergency, Radio, Document
Library) confirmed showing their cross-link box; zero failed units; no
new nginx/PHP errors since deploy. Full five-suite regression:
206/206.

| Deep field library, increment 7: CDC/FEMA/EPA documents (Make Water Safe During an Emergency, Family Emergency Communication Plan, Reduce Your Smoke Exposure - 6 docs / ~8.4MB total library) | `a613784` | `~/piratebox-backups/cdc-fema-epa-docs-pre-20260902-102250/` |

**Deployed and live-verified 2026-09-02:** dry-run clean, real deploy
clean, `VERSION` stamped to `a613784` matching `HEAD` exactly. Live:
all three PDFs serve at exact byte sizes; Emergency Reference page
shows all three inside their correct topics; `/utility/about/` shows
`Document Library: INSTALLED (6)`, computed live; zero failed units;
no new nginx/PHP errors since deploy. Full five-suite regression:
206/206.

| AWG ampacity table reviewed against an authoritative source (no numbers changed - already correctly using the conservative NEC breaker-sizing convention; caveat text sharpened) | `56040f1` | `~/piratebox-backups/awg-review-pre-20260902-102513/` |

**Deployed and live-verified 2026-09-02:** dry-run clean, real deploy
clean, `VERSION` stamped to `56040f1` matching `HEAD` exactly. Live
`/utility/fieldtools/units/` confirmed the new precise caveat text
present; zero failed units; no new nginx/PHP errors since deploy. Full
five-suite regression: 206/206.

| Deep field library, increment 11: Radio connector diagram (`connectors.svg.php` - original PirateBox-authored schematic comparing the 5 connector types already in the Feed Lines & Connectors guide's table; closes roadmap item 5's connector half) | `e9bc4d3` | *(none taken under the usual `~/piratebox-backups/` naming - built on an isolated worktree branch by a background session per its own policy against merging/deploying from there; the operator merged `worktree-continue-deep-library` into `main` and ran the deploy directly. `56040f1`/`27b7db1` above remains the most recent backed-up rollback point; the merge was a pure fast-forward, so rolling back to `27b7db1` is still a clean `git checkout` if ever needed)* |

**Deployed and live-verified 2026-09-02 (merged from a worktree branch,
deploy run by the operator; verified in this follow-up recovery
pass):** `main` confirmed fast-forwarded to `e9bc4d3`
(`git merge-base --is-ancestor e9bc4d3 HEAD` true, `HEAD` equals
`e9bc4d3` exactly, tree clean). Live `includes/VERSION` stamped to
`e9bc4d3`, matching `HEAD`. Both changed files
(`public/utility/radio/connectors.svg.php`,
`public/utility/radio/index.php`) confirmed byte-identical between the
repo and the live `/var/www/html` tree. Live `/utility/radio/` (200)
contains the new diagram markup and the Feed Lines & Connectors guide;
`connectors.svg.php` requested directly also returns 200 with valid
`<svg>` markup (served as `text/html` since it's a `require`-included
partial, not a standalone asset - identical behavior to the
pre-existing `spectrum.svg.php`, not a regression). Zero failed units;
nginx error log's last entry predates this deploy (pre-existing,
already-documented `open_basedir` warning from `fieldtools_time.php`,
unrelated). Full five-suite regression: 206/206.

| Deep field library, increments 12-15: Radio antenna diagram, Maps navigation depth (5 entries + declination/UTM-MGRS diagrams), First Aid (DoD FM 4-25.11), food/water safety (FDA), electrical symbols + measurement concepts, watch/warning terminology, ground-to-air signals, new Computing & Networking category (10 entries), SI Prefixes reference | `ee5bfbb` | *(none taken under the usual `~/piratebox-backups/` naming - built across 4 commits on an isolated worktree branch by a background session per its own policy against merging/deploying from there; the operator merged `worktree-deep-library-continue2` into `main` and ran the deploy directly. `e9bc4d3`/`6f52726` above remains the most recent backed-up rollback point; the merge was a pure fast-forward, so rolling back to `6f52726` is still a clean `git checkout` if ever needed)* |

**Deployed and live-verified 2026-09-02 (merged from a worktree branch,
deploy run by the operator; this entry's verification was performed in
a follow-up recovery pass):** `main`/HEAD confirmed at `ee5bfbb`, tree
clean. Live `includes/VERSION` stamped to `ee5bfbb`, matching `HEAD`
exactly. Every changed file across all four increments (Radio,
Maps x2 diagrams, First Aid, Emergency x2 additions, Field Tools Units
x2 additions, Computing page, Utility index, Search page, and both new
library catalog/reference-pack JSON files) confirmed byte-identical
between the repo and the live `/var/www/html` tree, including both new
retained PDFs (DoD FM 4-25.11 and the FDA factsheet, both byte-for-
byte identical live). Live-verified over HTTP against the real
deployed site (not a dev server): `/utility/radio/` shows both the
antenna diagram and the watch/warning terminology guide;
`/utility/maps/` shows all 5 new reference entries plus both new
diagrams inline; `/utility/firstaid/` shows the FM 4-25.11 Document
Library cross-link; `/utility/emergency/` shows both the FDA
cross-link and the ground-to-air-signals diagram;
`/utility/fieldtools/units/` shows the electrical symbols diagram,
Multimeter & Measurement Basics, and the new SI Prefixes table;
`/utility/computing/` returns 200 with all 10 entries; the Utility
Library index shows the new Computing nav card; `/utility/about/`
correctly shows "Computing & Networking Reference: INSTALLED (10)",
computed live, not hardcoded. `tools/check_library_catalog.py` clean
(8/8 agree). Zero failed units; live search index confirmed at 134
entries. Full five-suite regression: 206/206.

| Deep field library, increments 16-17: Help/About discoverability + de-duplication, Glossary architecture (26 terms), Ten Essentials outdoor/field topic | `804c3ce` | *(none taken under the usual `~/piratebox-backups/` naming - built across 2 commits on an isolated worktree branch by a background session; the operator merged `worktree-deep-library-continue3` into `main` and ran the deploy directly. `ee5bfbb` above remains the most recent backed-up rollback point; the merge was a pure fast-forward)* |

**Deployed and live-verified 2026-09-02 (merged from a worktree
branch, deploy run by the operator; verified in this follow-up
recovery pass):** `main`/HEAD confirmed at `804c3ce`, tree clean. Live
`includes/VERSION` stamped to `804c3ce`, matching `HEAD`. Every
changed file (`help.php`, `index.php`, glossary page + data, emergency
topics/sources, reference-packs.json, search-index.json) confirmed
byte-identical between repo and live tree. Live-verified over HTTP
against the real deployed site: `help.php` shows the new "Two
different questions" pointer and no longer shows the stale
"planned/in progress" capability bullets; `/utility/about/` still
links back to Help (4 occurrences); `/utility/glossary/` returns 200
with `dhcp`/`cidr`/`polarization`/`declination` entries all present;
`/utility/emergency/` shows the new `ten-essentials` topic; live
search index confirmed at 161 entries with DHCP/CIDR/Polarization/
Declination all present in its titles. `tools/check_library_catalog.py`
clean (8/8). Zero failed units. Full five-suite regression: 206/206.

| Deep field library, increments 18-19: Reference -> Tool principle, Morse Code Converter, tool audit, IPv4 Subnet Calculator (36 new deterministic tests) | `d943d6e` | *(none taken under the usual `~/piratebox-backups/` naming - built across 2 commits on an isolated worktree branch by a background session; the operator merged `worktree-deep-library-continue4` into `main` and ran the deploy directly. `804c3ce` above remains the most recent backed-up rollback point; the merge was a pure fast-forward)* |

**Deployed and live-verified 2026-09-02 (merged from a worktree
branch, deploy run by the operator; verified in this follow-up
recovery pass):** `main`/HEAD confirmed at `d943d6e`, tree clean. Live
`includes/VERSION` stamped to `d943d6e`, matching `HEAD`. Every
changed file (`morse.php`, morse page, `subnet_calc.php`, subnet page,
search-index.json) confirmed byte-identical between repo and live
tree. Morse Code Converter live-verified over real HTTP with raw curl
POST (no JS involved): PIRATEBOX->Morse, SOS round-trip, "HI THERE"
word-separator handling, "CQ DX?" standard punctuation, and "AB#C"
unknown-character handling (preserved bracketed) all correct; Radio
page links to it; search index confirms "Morse Code Converter" present
(163 entries). IPv4 Subnet Calculator live-verified the same way:
192.168.1.10/24 standard case, 10.0.0.5/255.255.255.0 dotted-netmask
input, /31 (no broadcast, 2 usable addresses, RFC 3021 noted) and /32
(single host) edge cases, and a malformed-IP error message, all
correct; Computing page links to it (3 cross-linked entries); search
index confirms "Subnet Calculator" present. `tools/
check_library_catalog.py` clean (8/8). Zero failed units. Full
five-suite regression: 242/242.

| Deep field library, increments 20-23: Frequency/Wavelength Calculator, Ohm's Law Solver, Coordinate Converter no-JS retrofit, Checksum/Hash Calculator, global/non-US balance audit + World Electrical Power Standards | `b70c5ed` | *(none taken under the usual `~/piratebox-backups/` naming - built across 5 commits on an isolated worktree branch by a background session; the operator fast-forward merged `worktree-deep-library-continue5` into `main` (`d943d6e` -> `b70c5ed`) and ran the deploy directly, reapplying the Travel Mode quarantine with mode OFF. `d943d6e` above remains the most recent backed-up rollback point)* |

**Deployed and live-verified 2026-09-02 (merged from a worktree
branch, deploy run by the operator; verified in this follow-up
recovery pass):** `main`/HEAD confirmed at `b70c5ed`, tree clean. Live
`includes/VERSION` stamped to `b70c5ed`, matching `HEAD`. Every
changed file (`freq_wavelength.php`, `ohms_law.php`,
`checksum_tool.php`, coordinates page, units page, search-index.json)
confirmed byte-identical between repo and live tree. Live-verified
over real HTTP with raw curl POST (no JS involved): Frequency/
Wavelength (146 MHz -> 2.053 m, correctly banded VHF); Ohm's Law
(V=12, I=2 -> R=6 &#8486;, P=24 W); Coordinate Converter's new no-JS
path (40.6892,-74.0445 -> 40&deg;41'21.12" N, 74&deg;2'40.20" W);
Checksum tool's text panel (SHA-256/MD5 of "abc" match known test
vectors) and its path-traversal rejection (`../../../../etc/passwd`
correctly refused); World Electrical Power Standards table present on
the Units page. Search index confirms all four tool names present
(166 entries). `travel-mode.json` confirmed `{"travel_mode": false}`,
consistent with the operator's report. `tools/
check_library_catalog.py` clean (8/8). Zero failed units. Full
five-suite regression: 282/282.

| Deep field library, increment 24: Beaufort Wind Scale, International Emergency Numbers, glossary Weather category | `188f7c5` | *(none taken under the usual `~/piratebox-backups/` naming - built on an isolated worktree branch by a background session; the operator fast-forward merged `worktree-deep-library-continue6` into `main` (`b70c5ed` -> `188f7c5`) and ran the deploy directly, reapplying the Travel Mode quarantine with mode OFF. `b70c5ed` above remains the most recent backed-up rollback point)* |

**Deployed and live-verified 2026-09-02 (merged from a worktree
branch, deploy run by the operator; verified in this follow-up
recovery pass):** `main`/HEAD confirmed at `188f7c5`, tree clean. Live
`includes/VERSION` stamped to `188f7c5`, matching `HEAD`. Every
changed file confirmed byte-identical between repo and live tree.
Live-verified over real HTTP: `/utility/emergency/` shows both new
topics with their tables rendering correctly (Beaufort "0 - Calm"
row, International Emergency Numbers' "European Union" row both
present); `/utility/glossary/` shows the new Weather &amp; Environment
category with both new terms; live search index confirmed at 170
entries with both new topic titles present; `/utility/about/`
correctly shows "Glossary: INSTALLED (28)", computed live.
`travel-mode.json` confirmed `{"travel_mode": false}`. `tools/
check_library_catalog.py` clean (8/8). Zero failed units. Full
five-suite regression: 282/282.

| Admin panel auth readiness (discoverability fix) + Outdoor & Field Reference (knots/hitches) + discoverability audit | `1b757ff` | *(none taken under the usual `~/piratebox-backups/` naming - built across 2 commits on an isolated worktree branch; the operator fast-forward merged `worktree-deep-library-continue7` into `main` (`188f7c5` -> `1b757ff`) and ran the deploy directly, then completed both required operator actions: ran `setup_admin_password.sh` to create the first admin account, and reinstalled the updated `piratebox_status_helper.sh` to `/usr/local/bin/`)* |

**Deployed and live-verified 2026-09-02 (merged from a worktree
branch, deploy + both operator actions completed by the operator;
verified in this follow-up recovery pass):** `main`/HEAD confirmed at
`1b757ff`, tree clean. Live `includes/VERSION` stamped to `1b757ff`,
matching `HEAD`. `piratebox_status_helper.sh` confirmed byte-identical
between the repo and the installed `/usr/local/bin/` copy. Live
`/run/piratebox/status.json` confirmed the new `admin_auth.configured:
true` field is present and correct (htpasswd file confirmed non-empty,
44 bytes, by `ls -la` only - content never read). Live `/admin/` now
correctly returns 401 (auth actively enforced, not the old always-
locked-out empty-file state). `/utility/about/`'s Operational layer
count correctly went from "2 of 9" (pre-checkpoint) to "3 of 9"
working, reflecting `admin_panel` now classifying as `AVAILABLE` -
without ever naming the capability on the public page. Outdoor & Field
Reference live-verified: `/utility/outdoor/` returns 200 with all 8
knots/hitches present; About page shows "Outdoor & Field Reference:
INSTALLED (8)," computed live; live search index confirmed at 178
entries. `tools/check_library_catalog.py` clean (8/8). Zero failed
units. Full five-suite regression: 287/287.

| QR order fix, Document Library round 2 (4 new documents), Related Documents completeness audit, EPA redundancy deferral | `6c25dea` | *(none taken under the usual `~/piratebox-backups/` naming - built across 4 commits on an isolated worktree branch; the operator fast-forward merged `worktree-deep-library-continue8` into `main` and ran the deploy directly, then approved and installed poppler-utils)* |

**Deployed and live-verified 2026-09-02:** `main`/HEAD confirmed at
`6c25dea`, tree clean. Live `includes/VERSION` stamped to `6c25dea`,
matching `HEAD`. QR order confirmed live: `qr-wifi.png` renders before
`qr-url.png` in the page source, with "Connect to the...Wi-Fi" and
"Open PirateBox" captions both present; canonical `http://piratebox/`
payload unchanged. All 4 newly retained documents (FM 3-25.26, NTIA
frequency chart, OSHA electrical safety, UK Preparing for Emergencies)
confirmed downloadable (200, `application/pdf`) and each one's
category-level cross-link confirmed live on Maps, Radio, Field Tools
Units, and Emergency respectively. `tools/check_library_catalog.py`
clean (12/12). Live search index at 182 entries. About page correctly
shows "Document Library: INSTALLED (12)", computed live. Zero failed
units. Full five-suite regression: 287/287. Separately: `pdfinfo`/
`pdftotext`/`pdfimages` (poppler-utils 25.03.0) confirmed installed
and working - the standing tooling blocker on first-aid/land-nav
diagram extraction is closed.

| Deep-library pass: 5 new documents (EPA water disinfection, FM 5-125 rigging, NIST SP811 SI units, NOAA severe weather, OSHA 3075 electrical), first-aid/land-nav/knot diagram extraction, Outdoor cross-link bugfix | `05c8d1b` | *(none taken under the usual `~/piratebox-backups/` naming - built across 5 commits on an isolated worktree branch; the operator fast-forward merged `worktree-deep-library-continue9` into `main` and ran the deploy directly)* |

**Deployed and live-verified 2026-09-02:** `main`/HEAD confirmed at
`05c8d1b`, tree clean. Live `includes/VERSION` stamped to
`05c8d1be8b2b656299987ffd0505f9d169f9296d`, matching `HEAD` exactly.
Repo/live byte identity confirmed on catalog.json, search-index.json,
and all three changed page templates (firstaid/maps/outdoor index.php)
via `diff -q` - all identical. Document Library catalog confirmed at
17/17 (`tools/check_library_catalog.py` clean), retained-document
footprint confirmed at 41MB on disk. All 5 newly retained documents
(EPA Emergency Disinfection of Drinking Water, FM 5-125 Rigging
Techniques, NIST SP811 SI Units Guide, NOAA Thunderstorms/Tornadoes/
Lightning guide, OSHA 3075 Controlling Electrical Hazards) confirmed
downloadable live (200, `application/pdf`) via the real nginx/php-fpm
stack, not a dev server. Category-level Related Documents cross-links
confirmed live: EPA + NOAA on Emergency, FM 5-125 on Outdoor, NIST +
OSHA 3075 on Field Tools Units. New figures confirmed live: 5
first-aid diagrams on `/utility/firstaid/`, 1 land-navigation terrain-
features diagram on `/utility/maps/`, 6 knot-diagram blocks (5 unique
images, one reused) on `/utility/outdoor/` - including the corrected
FM 5-125 catalog cross-link (the earlier `#bowline`-fragment bug was
fixed and re-verified live). Live search index at 187 entries. About
page correctly shows "Document Library: INSTALLED (17)", computed
live. Zero failed units. Full five-suite regression: 287/287. Core
services (nginx, php8.4-fpm, hostapd, dnsmasq) all active; homepage
200.

| OLED bring-up: I2C1 enabled, SSD1306 physically verified, `piratebox-oled.service` implemented and live | `c5d4e99` on `worktree-oled-i2c-bringup` (not yet merged to `main`) | *(no `~/piratebox-backups/` snapshot taken - this is a physical hardware bring-up in a live interactive session, not a content/code deploy through `piratebox_deploy.sh`. The four changed/new files were installed directly from the worktree via `sudo install` at the operator's hand, one command at a time: `/usr/local/bin/piratebox_oled_daemon.py` (new), `/usr/local/bin/piratebox_status_helper.sh` (updated), `/etc/systemd/system/piratebox-oled.service` (new), `/var/www/html/includes/capability_state.php` (updated) - followed by `daemon-reload` and `enable --now`. The git branch itself remains unmerged; `includes/VERSION` on the live site therefore still reflects the pre-OLED commit until the branch is eventually merged and deployed through the normal flow - a cosmetic tracking gap, not a functional one, called out explicitly rather than silently left)* |

**Live-verified 2026-09-03, directly on this Pi (not a repo/live diff -
files were installed by hand, per above):**
- **I2C enablement:** `dtparam=i2c_arm=on` uncommented in `/boot/
  firmware/config.txt` (backed up first as `config.txt.pre-i2c-bak`),
  confirmed persistent across a real reboot. The `i2c-dev` kernel
  module (missing initially - the config.txt line alone only brings up
  the bus adapter, not the `/dev/i2c-*` nodes) loaded via `modprobe`
  and persisted via `/etc/modules-load.d/i2c.conf`, no second reboot
  needed for that half. `/dev/i2c-1` confirmed present, `crw-rw----
  root:i2c`.
- **Hardware verified, not assumed:** `i2cdetect -y 1` found the OLED
  at `0x3C`, nothing else on the bus; bus 2 (internal, not physically
  exposed) confirmed empty as a non-conflict sanity check. A real frame
  (full-white flash, then a bordered test pattern) was written via
  `luma.oled` and **visually confirmed by the operator** on the
  physical screen before any daemon/service was built - an address
  response alone was deliberately not treated as proof.
- **Pre-existing abnormal episode investigated first, per instruction:**
  immediately before this bring-up, the operator reconnected the OLED
  wiring live (Pi powered on), then SSH became extremely slow and the
  GPIO25 hold-to-shutdown did not trigger, ending in a hard power
  cycle. On the next boot, before resuming I2C work: `piratebox-
  button.service` came back up clean and healthy - no evidence of a
  defect in it. No previous-boot journal was available to examine the
  actual stall (`journalctl --list-boots` showed only the current boot
  - `/var/log/journal` exists but was never actually initialized for
  persistent storage on this system, a pre-existing gap, so the
  volatile journal was lost on the hard power-cut). `vcgencmd
  get_throttled` read `0x50005` on that fresh boot - **active
  under-voltage and throttling, confirmed again by 4 separate kernel
  "Undervoltage detected!" events in the first ~4 minutes of uptime** -
  a real, currently-open power-supply-headroom issue, previously
  flagged during the original GPIO25 bring-up
  (`docs/CAPABILITY-REGISTRY.md`), now recurring seriously enough to
  plausibly explain the stall (CPU throttling starving process
  scheduling, not a software defect). Filesystem/systemd/dmesg
  otherwise completely clean. **Explicitly not attributed to the OLED**
  - the condition was present on this same boot before the OLED daemon
  was even running, and the display's own current draw is a few mA.
  Still unresolved on this power source as of this checkpoint.
- **`piratebox-oled.service`:** installed, enabled, active. Journal
  shows a single clean startup (`Started`, `OLED initialized
  successfully`) with zero warnings or errors in the minutes following.
  Runs as the existing `piratebox-gpio` account with
  `SupplementaryGroups=i2c` (no `usermod` needed - granted at the
  systemd-unit level, not the account's real `/etc/group` membership).
- **Display content confirmed live and correct by direct operator
  observation:** all four pages (Status/Time/Network/Health) cycling
  correctly on the physical screen, matching
  `docs/PHYSICAL-CONTROL-UX-DESIGN.md` §1's design.
- **`status.json` confirmed carrying the new `hardware.
  oled_service_active: true` field**, correctly separated from the
  Core `services` object. **About page's live capability count moved
  from 3/9 to 4/9 Operational capabilities available** - the expected,
  and only, visible confirmation on the public page, which deliberately
  never names individual capabilities.
- **Nothing else disturbed:** `piratebox-button.service` (shutdown
  button) confirmed active and unaffected throughout; `hostapd`/
  `dnsmasq`/`nginx`/`php8.4-fpm` all confirmed active; heatsink fans are
  purely hardware-wired (physical pins 4/6, no GPIO/software
  involvement) and were never touched by any I2C configuration (I2C
  only uses physical pins 1/3/5/14).
- Full five-suite regression: 287/287 (run against the worktree before
  live installation, `capability_state` suite specifically 55/55, no
  assertion broke by the new `oled` classification logic).

**Merged to `main` and deployed 2026-09-03 - this is now the durable
known-good recovery point for the OLED bring-up**, not just a worktree
checkpoint. `worktree-oled-i2c-bringup` (`c5d4e99`, `31248d8`) fast-
forward merged cleanly into `main` (`2821af7` -> `31248d8`, no
divergence, no conflicts). `sudo /usr/local/bin/piratebox_deploy.sh`
run from `main` - Travel Mode quarantine re-applied (mode OFF), web
tree synced. Live `includes/VERSION` now correctly stamped to
`31248d8ab8a98045c0a0b3c1345bf92e5396381e`, matching `HEAD` exactly.
Re-verified after merge+deploy, not assumed carried over from the
pre-merge checks: `capability_state.php` byte-identical repo/live;
`piratebox_oled_daemon.py`, `piratebox_status_helper.sh`, and the
`piratebox-oled.service` unit file (all installed by hand before the
merge, from the worktree) all confirmed byte-identical to their
now-merged `main` copies - **zero deployment drift**.
`piratebox-oled.service` still active/enabled, same PID, journal still
clean (the deploy only touches `var/www/html/` - it does not and
should not restart unrelated services). `piratebox-button.service` and
all four Core services (hostapd/dnsmasq/nginx/php8.4-fpm) confirmed
active. Full five-suite regression re-run post-deploy: 287/287. Live
About page's capability count still correctly reads 4/9 Operational.
Homepage 200. The worktree and its branch were then removed
(`git worktree remove` + `git branch -d`) - safe, since every commit
on it is now reachable from `main`.

**Remaining known-open, deliberately not addressed by this pass:**
undervoltage/throttling remains active on this power source
(`vcgencmd get_throttled` still reads `0x50005` post-merge, unchanged) -
this is a hardware power-supply-headroom issue, explicitly preserved
as open/degraded per instruction, not something this checkpoint
resolves. See `docs/CAPABILITY-REGISTRY.md`'s "Undervoltage / power-
quality monitoring" entry for the full history.

| Deep bookshelf pass, round 5: 12 new documents (navigation/celestial, electronics x5, radio, math/physics x2, materials/chemistry, computing/networking x2, mechanical), 2 figure extractions, new `materials-chemistry` category | `c0af00e` on `worktree-library-round5` (not yet merged to `main`) | *(no `~/piratebox-backups/` snapshot - content/code pass, to be merged and deployed via the normal `piratebox_deploy.sh` workflow)* |

**Pre-merge state, 2026-09-03:** built and fully tested on an isolated
worktree branch across two commits (`f331e0e`, `c0af00e`). Explicitly
did NOT touch the OLED implementation, the undervoltage/power finding,
or RTC/time-confidence work - all three correctly out of scope for
this pass. catalog.json validated, `tools/check_library_catalog.py`
clean (36/36), search index rebuilt (206 entries), full five-suite
regression 287/287, all 12 new documents and both new figures smoke-
tested via `php -S` against the worktree (all downloads 200, all
Related Documents cross-links render on their target pages, both
figure images 200, new `materials-chemistry` and previously-empty
`pi-linux-networking` category chips render). One real licensing
rejection recorded (USDA Complete Guide to Home Canning - grant-funded
cooperative work, no explicit PD/reproduction statement found) rather
than assumed retainable. Library footprint: 36 documents, ~271 MB
total (was 24 documents, ~67 MB, at the start of this pass) - see
`docs/IMPLEMENTATION-ROADMAP.md` §3l for the full document-by-document
record. Merge/deploy and live re-verification recorded separately once
completed.

**Closing this out (2026-09-03): round 5 WAS in fact fast-forward
merged (`ebf59a3` -> `c54415d`) and deployed via `piratebox_deploy.sh`
in the same session, with a full post-merge live re-verification
(VERSION match, zero deployment drift including the 128MB Bowditch
file, 287/287 regression, all 12 documents + both figures 200 via the
real nginx/php-fpm stack, Core/OLED/button services all confirmed
active) - this follow-up note was simply never added back to this
file at the time. Recorded now so this entry doesn't read as
permanently unfinished; `c54415d` is the correct known-good point, not
just the pre-merge worktree tip.

| Deep bookshelf pass, round 6 (global source + RF depth + mining Bowditch) + trust statement + lightweight multilingual foundation (EN/ES) | `043ab8f` on `worktree-round6` (not yet merged to `main`) | *(no `~/piratebox-backups/` snapshot - content/code pass, to be merged and deployed via the normal `piratebox_deploy.sh` workflow)* |

**Pre-merge state, 2026-09-03:** built and fully tested on an isolated
worktree branch across two commits (`bf90905` trust/i18n, `043ab8f`
library round 6). Explicitly did NOT touch the OLED implementation,
the undervoltage/power finding, RTC/time work, the AWUS036ACM
migration, or the GPIO shutdown button - all correctly out of scope.
Library: 2 new documents (UK National Risk Register 2025, NEETS
Module 11), 2 new figures mined from the already-retained Bowditch
(not a new download) added to the Maps page. Site-level: a subtle
trust statement in the shared footer linking to a new Trust &
Transparency section on the Help page, every claim in it verified
against actual configuration (no HTTPS anywhere in nginx, no
setcookie() calls prior to this change, aggregate-only connection
stats, non-hardware-derived device ID, local-only captive portal) -
not assumed from the desired architecture; and a bounded English/
Spanish multilingual foundation (`includes/i18n.php`, flat JSON
dictionaries, manual-choice-wins locale precedence) applied to nav
labels, the Emergency Mode banner, the footer, and the Help page's
Connect + Trust sections - not a full site translation. catalog.json
validated, `tools/check_library_catalog.py` clean (38/38), search
index rebuilt (208 entries), full five-suite regression 287/287
(unaffected by the shared navbar.php/footer.php change - confirmed via
9 spot-checked diverse pages all still 200 with no PHP warnings). See
`docs/IMPLEMENTATION-ROADMAP.md` §3m and `docs/OPERATIONAL-
DECISIONS.md` ("Trust/Transparency Statement + Lightweight
Multilingual Foundation") for the full record. Merge/deploy and live
re-verification recorded immediately below, in the same session this
time.

**Closing this out (2026-09-03, from round 7): round 6 WAS in fact
fast-forward merged onto `main`** (`bf90905` -> `043ab8f`, both
directly reachable from `main`, no separate merge commit needed) and
deployed - `19a4e01` (the docs commit right above) is the current
round-7 worktree's own fork point, confirming round 6's content is
genuinely live. The promised merge/deploy follow-up note for round 6
itself was simply never appended to this file at the time - the same
gap pattern as round 5's, just one round later. Recorded now so this
entry doesn't read as permanently unfinished, though the original
post-merge live re-verification details from that session were not
captured and aren't reconstructed here; round 7's own pre- and
post-merge verification appears below.

| Deep bookshelf pass, round 7 (Mechanical/Electronics/Materials reference pages + OLED personality mode + Utility hub i18n) | `0491710` on `worktree-round7` (not yet merged to `main`) | *(no `~/piratebox-backups/` snapshot - content/code pass, to be merged and deployed via the normal `piratebox_deploy.sh` workflow)* |

**Pre-merge state, 2026-09-03:** built and fully tested on an isolated
worktree branch across five commits (`038082b` Mechanical, `5ff1f7c`
Electronics + Radio SWR/microwave, `d555be6` OLED personality mode,
`d313835` Materials & Chemical Safety, `0491710` Utility hub i18n).
Explicitly did NOT touch the undervoltage/power finding, RTC/time
work, the AWUS036ACM migration, enclosure design, or add any new Field
Tools/calculators - all correctly out of scope. Three new reference
pages closing the round's most obvious gaps: `/utility/mechanical/`
(8 entries, 2 figures from Basic Machines + 1 from Tools and Their
Uses), `/utility/electronics/` (6 entries, 1 figure from NEETS Module
7), `/utility/materials/` (6 entries; 2 new OSHA QuickCards downloaded
- GHS Pictograms, SDS structure - alongside the pre-existing NIOSH
Pocket Guide). Two new Radio guides (SWR/impedance matching, microwave/
waveguide) grounded in already-retained NEETS Modules 10-11. A bounded
OLED personality/idle layer added to `piratebox_oled_daemon.py` -
gated by `personality_allowed()` on every tick, verified directly
against this Pi's own live (still-open) undervoltage condition to
confirm it correctly suppresses all frivolous behavior under a real
degraded state, not just a synthetic one; not yet installed on the
running Pi (requires the operator's own `sudo install` step). Utility
hub page (`/utility/`) gained a full Spanish translation layer (~40
new i18n keys) on top of round 6's foundation - all four locale-
selection paths re-verified against the live page. One document
researched and DEFERRED rather than force-added: the DOT/PHMSA
Emergency Response Guidebook (2024), blocked by an Akamai bot wall on
its primary host and an AWS WAF challenge on its ReliefWeb mirror -
worth a future attempt via a different route, not repeatedly hammered
this round. catalog.json validated, `tools/check_library_catalog.py`
clean (40/40, was 38/38 at round start), search index rebuilt (232
entries, was 224), full five-suite regression 287/287 throughout
(unaffected by any of this round's changes - confirmed after each
commit, not just once at the end). All three new pages, all four new/
changed PDFs, and the i18n-translated hub page smoke-tested via
`php -S` (all 200, Related Documents cross-links render, both locales
render correctly). Library footprint: 40 documents, ~281 MB (was 38
documents, ~281 MB - the two new OSHA QuickCards are small enough not
to move the rounded total). Merge/deploy and live re-verification
recorded immediately below, in the same session.

**Closing this out (2026-09-03): round 7 WAS merged and deployed, with
full post-merge live re-verification, in the same session.** The
operator ran the merge and deploy by hand from the primary checkout
(this pass's own worktree isolation could not reach it) -
`git merge --ff-only worktree-round7` (`19a4e01` -> `7fad203`, no
divergence, no conflicts), then `sudo /usr/local/bin/
piratebox_deploy.sh`, then a manual install of the updated OLED daemon
(`sudo install` + `systemctl restart piratebox-oled.service`). A
follow-up session then independently verified the result rather than
trusting the operator's report at face value: live
`/var/www/html/includes/VERSION` reads
`7fad203efe49c6930be4d16bd204dcc372aabf82`, matching `HEAD` exactly
(the operator had first checked the wrong path, `/var/www/html/
VERSION`, which has never existed in this project - the real location
is `includes/VERSION`, confirmed against this file's own §1 in the
project's `CLAUDE.md`). Byte-compared 18 round-7 files (the OLED
daemon, all 3 new PHP pages, catalog.json, search-index.json, both
i18n dictionaries, all 6 mechanical/electronics/materials data files,
radio guides/sources, both new OSHA PDFs, and 4 figure images) between
repo and live paths - **zero deployment drift**. Full five-suite
regression re-run post-deploy: 287/287. `tools/
check_library_catalog.py`: 40/40. Homepage, `/utility/`, `/utility/
mechanical/`, `/utility/electronics/`, `/utility/materials/`, both new
OSHA PDFs, and the lever figure all confirmed 200 via the real nginx/
php-fpm stack; Materials page content and its Document Library
cross-link to the NIOSH entry confirmed rendering. OLED daemon
confirmed byte-identical live, and its journal showed the old process
stopping cleanly via SIGTERM and the new one starting clean, with its
own startup log line now announcing the personality-mode feature -
direct proof the new code is what's actually running. All four Core
services (hostapd/dnsmasq/nginx/php8.4-fpm) plus
`piratebox-oled.service` and `piratebox-button.service` confirmed
active and enabled, zero failed units. `vcgencmd get_throttled` still
reads `0x50005` with `undervoltage_now: true` in `status.json` -
unchanged, confirming round 7 neither caused nor worsened the
pre-existing, already-acknowledged power condition. The worktree and
its branch were then removed (`ExitWorktree`, after independently
confirming `main`, `worktree-round7`, and `HEAD` were all identical at
`7fad203` - no work was at risk) - `git worktree list` and `git branch
--list` both confirmed clean afterward. `main` left clean with no
uncommitted changes.

| Round 8: UX discoverability + lightweight theme system + OLED instrument-panel polish + NTP root-cause diagnosis + bounded reference growth | `56048bc` on `worktree-round8` (not yet merged to `main`) | *(no `~/piratebox-backups/` snapshot - content/code pass, to be merged and deployed via the normal `piratebox_deploy.sh` workflow)* |
| Round 9: theme selector regression fix (Priority 0) + bounded reference/search/i18n work | `9e6d9f3` on `main` | *(no `~/piratebox-backups/` snapshot - content/code pass, merged via `git merge --ff-only` from `f4e4812` and deployed via `piratebox_deploy.sh`)* |

**Pre-merge state, 2026-09-03:** built and fully tested on an isolated
worktree branch across seven commits (`56ecd40` round-7 checkpoint
closure, `5f4df54` theme system, `33c0de5` landing page, `6d001ff` NTP
diagnosis, `ca98468` OLED polish, `8bfe6a3` reference growth,
`56048bc` trust/accessibility). Explicitly did NOT touch the
undervoltage/power finding, RTC hardware, the AWUS036ACM migration, the
enclosure, or add any new Field Tools/calculators - all correctly out
of scope. Landing page gained a "Two Ways to Use This PirateBox"
section (Connect & Share / Explore & Reference) without listing every
Utility category, absent in Emergency Mode by design. A five-theme
system (Default/Terminal/Amber/Low Light/Pirate) was added entirely
client-side (localStorage + a `data-theme` attribute, no cookie, no
server state) on top of `:root` CSS custom properties converted from
the previously-hardcoded palette - WCAG contrast computed (not
eyeballed) for every theme, one real failure found and fixed (Pirate's
warning color, 3.85:1 -> 4.99:1). The OLED's four serious pages gained
header-bar icons, a heartbeat tick, a Wi-Fi bars glyph, an
always-on (non-personality-gated) client-count pulse, per-service
status dots, a storage bar, a boxed undervoltage warning, a brief
page-change wipe transition, and a new always-on mode-transition
banner - personality mode's own gating (round 7) is unchanged and was
re-verified against this Pi's real, current `0x50005` condition. The
operator-reported wrong clock was root-caused to a malformed,
duplicated hostname in `/etc/systemd/timesyncd.conf`'s `NTP=` line
(confirmed via failed DNS resolution on the exact corrupted string) -
`eth0` has real, working Internet connectivity, contradicting an
earlier audit's assumption; the fix is a one-line `sed` + service
restart, documented as a genuine operator-sudo gate rather than
attempted from this session. Reference growth was deliberately bounded:
two citation upgrades in the Computing page (RFC 20 for ASCII, NEETS
Module 13 as a secondary for USB/serial), the ERG deferral re-checked
against a genuinely different host (also blocked, confirming the
pattern) rather than re-attempted, and one UK global-source candidate
evaluated and rejected on fitness (not licensing) - no new catalog
documents added, catalog stays at 40/40. `tools/check_library_
catalog.py` clean, search index rebuilt byte-identical (232 entries,
no reference.json changes), full five-suite regression 287/287
throughout (confirmed after every commit). All key pages (landing,
Utility hub, all three round-7 reference pages, Computing, Search,
Maps, Help, Chat, Bulletin, Logbook, Status) smoke-tested 200 via
`php -S` with zero PHP fatal/parse errors; both locales and the theme
switcher's five options confirmed rendering. Merge/deploy and live
re-verification (including installing the updated OLED daemon) to be
recorded separately once completed, per the same operator-gated
workflow round 7 used.

**Closing this out (2026-09-03): round 8 WAS merged, deployed, and its
NTP fix applied, with full post-merge live re-verification, in the
same session.** The operator ran the same operator-gated sequence
round 7 used, from the primary checkout: `git merge --ff-only
worktree-round8` (`7fad203` -> `149acac`, no divergence, no
conflicts), `sudo /usr/local/bin/piratebox_deploy.sh`, then installed
the updated OLED daemon (`sudo install` + `systemctl restart
piratebox-oled.service`). Separately, the operator applied round 8's
own NTP diagnosis: `sudo sed -i` correcting `/etc/systemd/
timesyncd.conf`'s malformed `NTP=` line, then `systemctl restart
systemd-timesyncd`.

A follow-up session then independently verified all of it rather than
trusting the operator's report at face value:
- **Provenance**: live `/var/www/html/includes/VERSION` reads
  `149acaca4acf706911a0e6a215fb5de2f3bbc73b`, matching `main`'s `HEAD`
  exactly.
- **Zero deployment drift**: byte-compared every round-8 changed file
  (styles.css, scripts.js, index.php, help.php, navbar.php, theme.php,
  both i18n dictionaries, both computing data files, catalog.json,
  search-index.json) between the repo and its live path - all
  identical.
- **NTP fix confirmed live, not just reported**: `timedatectl status`
  now reads `System clock synchronized: yes`; `/etc/systemd/
  timesyncd.conf`'s `NTP=` line now reads the corrected
  `time.cloudflare.com` (no more duplication);
  `/run/piratebox/status.json`'s `time_source.ntp_synchronized` is now
  `true` - exactly the "zero PirateBox code changes needed" result
  round 8's diagnosis predicted. `rtc_detected` remains honestly
  `false` - no hardware RTC exists or is claimed anywhere.
- **OLED**: `/usr/local/bin/piratebox_oled_daemon.py` confirmed
  byte-identical to the repo's round-8 copy; journal shows a clean
  restart with no errors/warnings/tracebacks since install.
  `personality_allowed()` was re-run against this Pi's own real,
  current `status.json` (imported directly from the live installed
  file, not a copy) and still correctly returns `False` - personality
  mode remains suppressed under the real, unchanged `0x50005`
  undervoltage condition. The Health page's boxed warning was
  confirmed to actually render against that same live data. The
  operator separately, physically observed the new OLED display and
  reported the redesign "looks really cool" - real-hardware visual
  acceptance, not just a code-level check.
- **Landing page, themes, i18n**: `/`'s "Two Ways to Use This
  PirateBox" section, its Connect & Share / Explore & Reference cards
  and links, all five theme `<option>`s, the Spanish landing section
  (`?lang=es`), and the new Help page trust item all confirmed
  rendering via the real nginx/php-fpm stack (not just `php -S`).
- **All six services** (`hostapd`/`dnsmasq`/`nginx`/`php8.4-fpm`/
  `piratebox-oled.service`/`piratebox-button.service`) confirmed
  active and enabled, zero failed units. Travel Mode confirmed `OFF`
  live, matching the deploy's own "quarantine re-applied (mode: OFF)"
  report.
- Full five-suite regression re-run post-deploy: 287/287.
  `tools/check_library_catalog.py`: 40/40 - the round-8 computing
  citation upgrades were data-only (no new catalog documents), and the
  live catalog confirms exactly 40.

This closing record itself lands as one more commit on
`worktree-round8` (docs-only, no change anywhere under `var/www/html/`
- per the project's own VERSION semantics, this does not need a
redeploy, and `VERSION` correctly continues to name `149acac`, the
commit actually reflected in the live web tree, until some future real
content/code change is deployed). Once that commit is fast-forwarded
into `main` and confirmed reachable, the worktree and its branch are
safe to remove - no further live verification needed, since nothing
under `var/www/html/` changes.

## Round 9: closed post-power-outage, `9e6d9f3` on `main`

**Priority 0 - theme selector regression, root-caused and fixed:**
the operator reported real use didn't match round 8's own passing
verification: picking a theme changed the dropdown's own text but not
the page, and the choice was lost on the next page load. Root cause
(full trace in `docs/OPERATIONAL-DECISIONS.md` "Round 9: Theme
Selector Regression"): `/etc/nginx/sites-available/default` set no
`Cache-Control` on `/assets/` at all, so a browser that had visited
before round 8 could keep silently serving its OLD cached
`scripts.js`/`styles.css`. Fix: a `location ^~ /assets/` block with
`Cache-Control: no-cache`, forcing revalidation on every use. New
`tools/test_theme_system.php` (18 assertions) covers the structural
invariants a browser test would need true.

**Real-browser verification: PASSED.** One false alarm along the way
(an operator report right after this round's commit, later traced to
testing from a stale/old browser tab - not a reproducible defect; no
extra debugging work happened chasing it, since the corrective prompt
describing it was never actually sent). The operator then ran fresh
tests directly against both supported origins, `http://10.0.0.1/` and
`http://piratebox/`: selecting a theme visibly changes the page, all
five themes are visibly distinct, on both origins. Recorded here as
the actual, final confirmation this bug is fixed - the deterministic
suite established every statically-checkable precondition, but the
operator's own browser test is what proved it works.

**A genuine discrepancy - found before the outage, independently
re-confirmed after it, still open:** the operator reported running
`sudo cp etc/nginx/sites-available/default
/etc/nginx/sites-available/default`, `nginx -t` (passed), and
`systemctl reload nginx`. This was checked twice - once during the
original round-9 closure pass (byte diff + `curl`), and again from
scratch during the post-power-outage recovery below - and both times:
**the live `/etc/nginx/sites-available/default` does NOT contain round
9's `location ^~ /assets/` block.** It is byte-for-byte the pre-round-9
112-line file, not the round-9 134-line one, and `/assets/scripts.js`
serves with no `Cache-Control` header at all (confirmed via `curl -sI`
against both `http://127.0.0.1/` and `http://10.0.0.1/`). The live
file's own mtime (13:35:17 PDT) lands 8 seconds *before* this round's
`piratebox_deploy.sh` run (`VERSION` timestamp 13:35:25 PDT) - so the
`cp` step did run at roughly the right time, but whatever it copied
was not round 9's `etc/nginx/sites-available/default` content. Cause
not established (possibly a stale/wrong working directory in the
operator's manual step). **This does not call the real-browser
theme-verification result into question** - that test passed because
the underlying JS/CSS/PHP mechanism (verified by
`tools/test_theme_system.php`) was always correct; the missing header
only affects whether a *returning* visitor's cached browser picks up a
*future* deploy promptly. It does mean the specific preventive fix
this round diagnosed is **still not live**. Nginx config changes are
outside this session's sudo automation (only `piratebox_deploy.sh` and
`set_piratebox_mode.sh` are NOPASSWD) and outside general system-config
authority per `CLAUDE.md` - **this remains a genuine open operator
action**, not something to silently mark done.

**Round 9's content/code work, independently re-verified after the
outage:** `main` HEAD and `/var/www/html/includes/VERSION` both read
`9e6d9f3` - full match, no drift. Spot-checked `var/www/html/` files
(both i18n dictionaries, search-index.json, materials reference/
sources) byte-identical repo vs. live. Full five-suite regression plus
the theme suite re-run from scratch: 305/305 (55+27+162+21+22+18).
`tools/check_library_catalog.py`: 42/42. Materials and Search pages
both confirmed live 200 via the real nginx/php-fpm stack. Travel Mode
confirmed `OFF` live (`{"travel_mode": false}`).

**Post-power-outage recovery (2026-09-03, same day):** an unexpected
household power outage hit mid-write of what would have been this
same closing commit, in the `round9` worktree
(`.claude/worktrees/round9`, branch `worktree-round9`). Four git loose
objects (the commit and its tree/blob dependencies) were left as
zero-byte files on disk - `git fsck` confirmed corruption, and that
worktree's branch ref (`b4daf1c...`) is unreadable. **No round-9 code
or content was lost**: the worktree's own `HEAD` reflog cleanly ends at
`9e6d9f3`, identical to `main`'s HEAD and to the operator's own
pre-outage account of the worktree tip - the interrupted commit was
purely this closing docs entry, nothing under `var/www/html/`. Its
intended text survived as an uncommitted, uncorrupted working-tree file
(`docs/CHECKPOINTS.md` in the round9 worktree, since working-tree files
are plain files, not git objects) and was used as a starting point here
- but every substantive claim in it (the nginx discrepancy above, the
regression/catalog counts, VERSION/drift, live 200s) was independently
re-verified from scratch post-outage rather than trusted as-is, per
this project's own recovery discipline. A full recursive diff of the
round9 worktree against `main` turned up nothing else uncommitted
besides this one file. Session/services health after the resulting
cold boot: `systemctl --failed` empty; all six services (`hostapd`/
`dnsmasq`/`nginx`/`php8.4-fpm`/`piratebox-oled.service`/
`piratebox-button.service`) active and enabled; `timedatectl` reports
`System clock synchronized: yes` with NTP active (`RTC time: n/a` -
still no hardware RTC, as expected, unchanged, not touched);
`vcgencmd get_throttled` reads `0x50005`, the same known pre-existing
undervoltage condition as prior rounds - acknowledged, not attempted,
per standing instruction. With containment established (all real
round-9 commits reachable from `main`; nothing else uncommitted in the
worktree), the `round9` worktree and its branch are safe to remove via
the normal worktree-cleanup procedure.

**Do not begin Round 10 from this entry** - the live nginx discrepancy
above is a real open item for the operator, not a blocker recorded as
if it were code work still to do.

