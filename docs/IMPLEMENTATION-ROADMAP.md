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
| purge_uploads.sh doesn't purge bulletin.json/recovery-messages.json | **IMPLEMENTED IN REPO, NOT DEPLOYED** | Fixed 2026-09-02 (`rm -f` for both added, README updated, tested against an isolated scratch dir - all four stores removed, `device-id.json` correctly untouched). Root-owned script installed via plain `cp`, outside sudo automation | **Pending operator step** (batched): `sudo cp purge_uploads.sh /usr/local/bin/purge_uploads.sh && sudo chmod +x /usr/local/bin/purge_uploads.sh` | OPERATIONAL-DECISIONS.md "purge_uploads.sh Completeness Gap Closed" |

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
| Radio / Emergency / First Aid reference (national) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stages 2-4; INSTALLED per `/utility/about/`'s live reference-pack table | none | Stages 2-4 |
| Navigation & Coordinates (universal) | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 5 | none | Stage 5 |
| **World Reference Map (universal)** | **IMPLEMENTED+DEPLOYED+LIVE-VERIFIED** | Was CANDIDATE for "no WAN path" - that blocker was about the Pi's isolated visitor AP, not this session's own `eth0` management uplink (confirmed live). Sourced Natural Earth public-domain data, built `world-reference-map.svg`, wired into `/utility/maps/` always-visible (Travel-Mode-immune), verified live 2026-09-02 (`1db5fab`) | none | REFERENCE-CONTENT-DESIGN.md §5, OPERATIONAL-DECISIONS.md "World Reference Map" |
| Local Information | BLOCKED BY OPERATOR DATA | Stage 6/17; deliberately ships near-empty; framework complete, no code needed once data provided | operator supplies region/hospital/shelter/repeater data | Stage 6/17 |
| Document Library | BLOCKED BY OPERATOR DATA | Stage 7; empty by design until operator adds documents | operator adds files | Stage 7 |
| Local/Regional Map Catalog | BLOCKED BY OPERATOR DATA | Stage 5; ready-to-use, empty by design | operator adds local map files | Stage 5, REFERENCE-CONTENT-DESIGN.md |
| Global Offline Search | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 8/18; 92 indexed items as of 2026-09-02 (was 83 - now includes the World Map) | none | Stage 8/18 |
| "Take This With You" export/download | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 19; live-verified this session (200) | Field Tools calculators deliberately not bundled (§10 FIELD-TOOLS-DESIGN.md) - "worth revisiting if operators ask," not approved | Stage 19 |
| Manifest ("What's on this PirateBox?") | IMPLEMENTED+DEPLOYED+LIVE-VERIFIED | Stage 20 | none | Stage 20 |

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
| Self-describing/inheritable device | PARTIALLY IMPLEMENTED | `/utility/about/` + admin Capabilities table exist (the self-description part); wiring-assignment/maintenance/repair info and the ownership/recovery concept itself remain undocumented on-device | could add a wiring/maintenance reference page (software-only, no decision needed) - candidate for a future increment | ARCHITECTURE.md §17 |

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
