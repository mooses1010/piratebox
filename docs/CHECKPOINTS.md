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

Live box mode should be **Normal** when unattended between test sessions.
