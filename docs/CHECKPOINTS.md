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

Live box mode should be **Normal** when unattended between test sessions.
