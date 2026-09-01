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
