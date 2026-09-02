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

