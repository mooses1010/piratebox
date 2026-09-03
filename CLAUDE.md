# PirateBox — Claude entrypoint

This file is the one authoritative starting point for a Claude Code
session working in this repo, including a session with **zero
conversation context** (fresh session, compacted history, crashed
process, reboot, disconnected Remote Control, whatever). Read this
file fully before doing anything else. It routes to existing sources
of truth rather than duplicating them — if something here conflicts
with the doc it points to, the doc wins.

If you arrived here via a breadcrumb at `/home/moose/CLAUDE.md`: that
file is intentionally tiny and exists only to make discovery
deterministic from this box's actual default session directory. See
"Why a breadcrumb exists" near the end — don't delete it as redundant.

Sections below are labeled **[generic]** (portable recovery principles,
not specific to this project) or **[piratebox]** (this project's own
rules/routing), so the generic parts can be lifted into another
project's own entrypoint later without dragging PirateBox specifics
with them. This file itself is not a framework — it's just one
project's entrypoint, written so the pattern is easy to see.

---

## 1. Establish reality first — before reading further, before acting **[generic]**

Conversation memory (yours or a summary you were handed) is the least
trustworthy source of truth available to you. Git state, live system
state, and this repo's own docs outrank it. If anything in your
context conflicts with what these commands show, **investigate the
discrepancy — don't act on the conversational claim.**

Run these from `~/piratebox` (this repo):

```bash
git status                          # dirty tree? on what branch?
git log --oneline -10                # recent work, at a glance
git worktree list                    # other checkouts, possibly still in use
git rev-parse --short HEAD

# Does the deployed web app match this checkout? Read the LIVE file
# (absolute path) — the repo's own var/www/html/includes/VERSION is
# gitignored and never populated in a checkout; only a real deploy
# writes the live one, and it's world-readable, no sudo needed.
cat /var/www/html/includes/VERSION   # stamped with the HEAD hash + time of
                                      # the last real (non-dry-run) deploy —
                                      # compare to `git rev-parse HEAD` above.
                                      # Mismatch = a deploy is pending/stale;
                                      # investigate rather than assume either
                                      # side is right (see §1a below).

# Live service/power health, right now, no sudo needed:
cat /run/piratebox/status.json
systemctl --failed                   # should be empty

# Any transient handoff note from an interrupted session?
cat CURRENT-WORK.md 2>/dev/null      # see §5 before trusting anything in it

# Durable record of what's actually done and safe to roll back to:
tail -60 docs/CHECKPOINTS.md
```

None of this requires sudo or touches anything. Do it before forming
any plan.

**§1a — when live state and a doc's claim disagree, trust the live
check.** A design doc's status banner (e.g. "implemented and
deployed") describes intent recorded at commit time, not a live
guarantee going forward. If `/var/www/html/includes/VERSION`'s
stamped commit is older than a feature's own commit, that specific
feature may not be the one live right now — don't conclude either way
from the doc alone; diff the specific file(s) in question between the
repo and their live path (both are on this same filesystem, no sudo
needed to read either side) before telling the operator something is
or isn't deployed.

`VERSION` means "the `HEAD` this checkout had at the last real web
deploy" — evidence about what's live, not proof. A deploy that ran
against a working tree already populated from a worktree branch, just
before that branch was formally merged into `main`, can leave it
naming a commit older than the content actually deployed (confirmed
case: `docs/OPERATIONAL-DECISIONS.md` → "VERSION Honesty Marker"). A
`(source had changes beyond this commit)` suffix on `VERSION` is that
same situation flagged by the deploy script itself, live — not an
error by itself, just a prompt to do the same file-level check.

## 2. Critical rules — non-negotiable **[piratebox]**

- **Never `git push` to `origin` unless explicitly asked.** This repo
  is deliberately kept ahead of `origin/main` (currently by dozens of
  commits) as a matter of practice — see `docs/CHECKPOINTS.md`.
- **Never install a package** (`apt`, `pip`, anything) without the
  operator's explicit go-ahead first, even one a design doc lists as
  a future dependency.
- **Anything destructive, anything touching networking/system
  configuration, any new privilege escalation, or physical hardware**
  stops for the operator. This session's standing automation is
  exactly two narrow `sudo` grants and nothing else — don't assume
  more exists:
  - `etc/sudoers.d/piratebox-claude` — 5 exact NOPASSWD lines:
    `piratebox_deploy.sh` (bare, and `--dry-run`) and
    `set_piratebox_mode.sh normal|emergency|status`.
  - `etc/sudoers.d/piratebox-button` — one NOPASSWD line, for the
    `piratebox-gpio` service user only: `systemctl poweroff`, no
    arguments.
- **Repo vs. deployed/live is not the same filesystem.** This
  checkout's `var/www/html/` is source; the live site is the
  root-owned `/var/www/html/`, updated only by `piratebox_deploy.sh`
  (additive-only — no `--delete`, ever). Scripts callable via sudo are
  root-owned, `moose`-unwritable copies under `/usr/local/bin` —
  editing the repo copy changes nothing live until it's redeployed or
  reinstalled via its setup script.
- **Live community data is real user content — never hand-edit or
  delete it.** (`var/www/html/data/*.json`, `public/uploads/`, etc.)
  Two *different* backup mechanisms exist; don't confuse them:
  `~/piratebox-backups/` = pre-stage code/site snapshots for dev
  rollback (taken before a deploy); `~/piratebox-data-backups/` =
  recurring live-data snapshots (`piratebox-backup.timer` +
  `tools/backup_piratebox_data.sh`). Restoring live data
  (`tools/restore_piratebox_data.sh`) is deliberately manual-only, not
  part of the sudo automation — it's rare, high-stakes, and can
  overwrite real history.
- **Checkpoint/test/deploy discipline stays the same regardless of
  time pressure:** preview before applying (dry-run), verify live
  after, record the result. This is the pattern every entry in
  `docs/OPERATIONAL-DECISIONS.md` already follows — keep following it.

## 3. Source-of-truth routing — read the specific doc for your task **[piratebox]**

| Subsystem | Authoritative source |
|---|---|
| **What's actually done vs. planned, and what to work on next** | **`docs/IMPLEMENTATION-ROADMAP.md`** — the authoritative execution queue, reconciled from the full commit history + every design doc + live state (2026-09-02). Read this before assuming something is finished, before assuming something is still open, and before inventing a new plan from whatever prompt just arrived. Update its rows as work completes; a new prompt adds/updates rows here rather than displacing them. |
| Long-term architecture, layering, privacy/trust/ownership philosophy, self-awareness model | `docs/ARCHITECTURE.md` |
| Concrete capability inventory (installed/owned/planned/candidate/deferred/rejected) | `docs/CAPABILITY-REGISTRY.md` |
| Unattended-operation memory/history model (retention classes, "since last review," Field Sessions) | `docs/DEVICE-MEMORY-DESIGN.md` |
| Reference content organization (Universal/National/Regional/Local/Live), Reference Packs | `docs/REFERENCE-CONTENT-DESIGN.md` |
| GPIO/hardware wiring, current pin status | `docs/HARDWARE-INTEGRATION-DESIGN.md` §2 (the one live wiring map) |
| Physical buttons / toggle / OLED UX design | `docs/PHYSICAL-CONTROL-UX-DESIGN.md` |
| Power / UPS / undervoltage design | `docs/POWER-UPS-DESIGN.md`; live reading: `/run/piratebox/status.json`, `vcgencmd get_throttled` |
| RTC / time readiness | `docs/RTC-TIME-READINESS-DESIGN.md` |
| Field Tools (time/date, unit conversion, coordinates) | `docs/FIELD-TOOLS-DESIGN.md` |
| Travel Mode | `docs/TRAVEL-MODE-DESIGN.md` |
| Voluntary check-in board (evaluated, deferred) | `docs/CHECKIN-BOARD-DESIGN.md` |
| Wi-Fi / AP adapter / external-AP migration architecture | **`docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md`** - stable interface identity, radio role model, boot fallback, NetworkManager ownership, regulatory domain, migration/rollback plan. Earlier history: `docs/OPERATIONAL-DECISIONS.md` → "Wi-Fi adapter notes / planned hardware" (grep for the heading). |
| Deployment mechanism (repo → live) | `piratebox_deploy.sh` header comments + `docs/OPERATIONAL-DECISIONS.md` → "Claude deployment/mode-switch automation" |
| Backup / restore of live community data | `tools/backup_piratebox_data.sh`, `tools/restore_piratebox_data.sh` header comments + `docs/OPERATIONAL-DECISIONS.md` → "Stage 25: Backup / Restore for Live Community Data" |
| Known-good rollback points | `docs/CHECKPOINTS.md` |
| Full decision/implementation history, anything not listed above | `docs/OPERATIONAL-DECISIONS.md` — see the warning in §4 before reading it as a task list |
| Feature list, install instructions, human-facing overview | `README.md` |

When nothing above fits, `grep` the feature/stage name against
`docs/OPERATIONAL-DECISIONS.md` before assuming it isn't documented —
it's the largest single source here.

## 4. `OPERATIONAL-DECISIONS.md` and "Stage N" are history, not a to-do list **[generic + piratebox]**

`docs/OPERATIONAL-DECISIONS.md` is a **reverse-chronological decision
log** (newest entry right after its short preamble, oldest at the
bottom) — one dated entry per intentional decision, recording what was
done and why. The "Stage N" numbering that runs through it and the
README is a **historical label for when work happened, not a queue of
work remaining.**

A stage/feature described there as done — especially one with a
matching row in `docs/CHECKPOINTS.md` and/or a merged commit reachable
from `main` — is **complete**. Do not resume it, re-verify it, "finish"
it further, or treat its presence in the roadmap as an open item,
merely because its name appears in a document. If you're unsure
whether something is actually finished, check independently (§1: git
log, `CHECKPOINTS.md`, live system state) rather than trusting either
the doc's prose tone or your own assumption about what "Stage 29"
etc. implies.

**The actual queue of open work lives in `docs/IMPLEMENTATION-
ROADMAP.md`, not in this file's prose or in whatever prompt just
arrived.** It was reconciled once (2026-09-02) against the full history
below plus live state specifically so a new large prompt can't silently
displace older still-valid requirements — update its rows as work
progresses; don't regenerate a new roadmap from scratch each session.

## 5. Interrupted work: worktrees, sessions, and `CURRENT-WORK.md` **[generic]**

- `git worktree list` may show checkouts besides this one. A worktree
  locked with a reason mentioning a Claude session **may still be in
  use by another active session right now.** Never force-remove it,
  never edit its files, never assume "looks merged, so it's fine to
  delete" overrides the lock — leave it and, if it matters, tell the
  operator.
- Never attach to or `--resume` a session that might still be running
  elsewhere. If something suggests another session may be active
  (a lock, a very recent timestamp, a process), treat it as live
  until the operator says otherwise.
- Uncommitted changes in a checkout are not automatically "your task
  in progress." Before assuming that, compare them against recent
  branches (`git diff <branch> -- <paths>`) — identical content to an
  already-merged branch usually means the work is *done* and this
  checkout just wasn't cleaned up, not that anything is actually
  unfinished. Cross-check against `CURRENT-WORK.md` (below) and the
  recent commit log before drawing a conclusion either way.
- **`CURRENT-WORK.md`** (repo root, gitignored, not always present) is
  an optional, transient handoff note — never a source of truth by
  itself. If present, it may contain: the task being worked on, the
  last independently-verified state, the intended next step, and any
  "do not redo this part" note, plus the git HEAD short-hash it was
  written against. **A recovering session must correlate it against:**
  current `git rev-parse HEAD`, `git status`/`git diff`, `git worktree
  list`, the actual recent commit log, the deployed `VERSION` file
  where relevant, and live system state where relevant. If any of
  those contradict the file, investigate and prefer the independently
  established reality — the file may be stale (the task it describes
  already finished and merged after it was written) or simply wrong.
  It is created only when about to do something interruption-prone
  (a physical test, a reboot, a risky live change), updated at real
  checkpoints, and **deleted as the last step of finishing the task it
  describes** — a lingering `CURRENT-WORK.md` after a clean merge is a
  sign it was forgotten, not a sign anything is still open.

## 6. Why a breadcrumb exists at `/home/moose/CLAUDE.md` **[piratebox]**

This Pi's actual default session directory is `/home/moose`, not this
repo — confirmed empirically (a real session started there, not
here). Claude Code loads `CLAUDE.md` by walking **up** from the
working directory; it doesn't search downward for one. Without the
breadcrumb, a session starting at `/home/moose` would never
auto-discover this file. The breadcrumb is intentionally tiny (a
pointer to `cd ~/piratebox` and read this file) and carries no project
state of its own — don't "clean it up" as a duplicate; it's covering a
real discovery gap, not redundant with this file.

## 7. Project identity, for orientation **[piratebox]**

An offline, anonymous Wi-Fi file-share/utility appliance running on a
Raspberry Pi (nginx/PHP/hostapd/dnsmasq, no database). Full feature
list and install instructions: `README.md`. Everything about *why*
things are built the way they are lives in `docs/`, routed above —
this file deliberately does not retell that content.

Longer-term: this project is deliberately built as *today's affordable
PirateBox inside tomorrow's architecture* — the current owner/hardware/
scope is real but not permanent, and the project's layering (Core/
Operational/Optional), privacy-exposure philosophy, self-awareness
model, and ownership/inheritance goals are formalized in `docs/
ARCHITECTURE.md`, with concrete capability state in `docs/CAPABILITY-
REGISTRY.md` (both routed in §3 above). None of that changes what's
actually running today — see those documents' own status banners.
