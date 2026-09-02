# Operational decisions

This file records intentional configuration/behavior decisions that differ
from the original upstream PirateBox project or from what the README used to
recommend, so a future maintainer (human or AI) doesn't "fix" them back to
the old behavior without knowing why they were changed. Each entry has a
date and the reasoning; if you're going to reverse one, update this file too.

## Stage 29 Implementation: Physical Shutdown Button (GPIO25)

**Decision date:** 2026-09-02. The first piece of Stage 11/29's
hardware design (`docs/HARDWARE-INTEGRATION-DESIGN.md`,
`docs/PHYSICAL-CONTROL-UX-DESIGN.md`) to move from design-only to
physically real. A 12mm normally-open momentary push button has been
connected to this Pi 3 B+ and brought up carefully, in stages, per
explicit instruction: read-only discovery first, safe electrical
testing before any persistent code, persistent-service testing in
dry-run before any real action, and the real shutdown action gated
behind its own explicit final step.

**Wiring mix-up caught before it mattered:** the button was initially
connected to physical pins 6 and 9 - **both GND**. Software-side
scanning (a `gpiomon`-based sweep of every header pin not already
reserved by I2C/UART/HAT-EEPROM) correctly found nothing, because there
was genuinely no GPIO in the circuit at all - the switch was just
shorting two ground points together. No electrical risk occurred either
way; this was caught by manual physical-pin inspection (a labelled 40-
pin header diagram) once automated scanning legitimately found nothing
to report, exactly the fallback the discovery process was designed to
reach.

**Bring-up test, GPIO25/physical pin 22 (other leg on physical pin 9,
GND), performed interactively before any persistent code existed:**
- Idle state: confirmed HIGH (internal pull-up, switch open).
- Pressed state: confirmed LOW (pulled to GND).
- Debounce: clean across roughly 20 taps in two separate test runs -
  zero bounce artifacts at 20ms software debounce.
- Short vs. long press: taps measured 0.08-0.56s, deliberate holds
  1.0-1.5s, and a 4.0-second hold threshold fired **exactly once**,
  precisely at 4.0s, with no re-fire during an extended 7.27s hold.
- Zero conflicts found with I2C (GPIO2/3, reserved for the not-yet-
  arrived OLED), UART (GPIO14/15, actively serving the serial console),
  or the existing dual-fan/heatsink setup (no fan-control overlay,
  service, or kernel module exists anywhere on this system - the fans
  are almost certainly wired to the header's fixed power pins, not any
  GPIO).
- One real bug found and fixed during this bring-up, unrelated to the
  hardware itself: the first Python test script's `print()` output was
  invisible until process exit, because Python fully buffers stdout
  when redirected to a file rather than a terminal. Every press had
  actually been detected correctly the whole time; fixed with explicit
  line buffering.

**Architecture - matches the project's existing privileged-helper
pattern exactly, not a new one:**
- `piratebox_button_daemon.py` (repo root, deployed to
  `/usr/local/bin`, root-owned/moose-unwritable - same anti-tampering
  property as `piratebox_deploy.sh`) - a `gpiozero`-based daemon,
  event-driven (kernel GPIO line-event notification via the `lgpio` pin
  factory, not a polling loop), watching only GPIO25.
- Runs as a **new dedicated, unprivileged system user
  (`piratebox-gpio`)** - no login shell, no home directory, member only
  of the `gpio` group - never `www-data`, never root, and deliberately
  not `moose` either (keeping this daemon's blast radius smaller than
  the interactive operator account's).
- `etc/sudoers.d/piratebox-button` - a **separate** narrow NOPASSWD
  grant (`piratebox-gpio ALL=(root) NOPASSWD: /usr/bin/systemctl
  poweroff`, no arguments to vary) - deliberately not added to
  `etc/sudoers.d/piratebox-claude`, which is a different actor's trust
  boundary (this session's deploy/mode-switch automation), per Stage
  29 §3's own explicit instruction.
- `etc/systemd/system/piratebox-button.service` - continuous (not
  timer-triggered like `piratebox-status`/`piratebox-backup`, since it
  must react the instant a press happens), `Restart=on-failure`.
  Deliberately does **not** set `NoNewPrivileges=yes` - the one
  hardening flag that would block this daemon's single legitimate
  escalation path - documented explicitly in the unit file as an
  understood exception, not an oversight.
- `setup_piratebox_button.sh` - one-time installer mirroring
  `setup_claude_automation.sh`'s exact pattern (create user, install
  daemon, validate + install sudoers with `visudo -cf` first, install +
  enable the systemd unit).

**Fails safely by design, not just by accident:**
- A short press has **no code path to anything** - not logged, not
  acted on, nothing.
- The real `poweroff` call is gated behind an explicit opt-in
  (`PIRATEBOX_BUTTON_ENABLE_SHUTDOWN=1`, set only in the systemd unit
  once the persistent service is verified end-to-end) - **absent by
  default**, so a misconfiguration can only ever fail toward inaction,
  never toward an unwanted shutdown.
- `sudo -n` (non-interactive) - if the sudoers grant is ever missing or
  broken, this fails immediately with a clear log line instead of
  hanging.
- No per-event data is written anywhere - not to a JSON store, not a
  log line for ordinary presses, nothing resembling the connection-
  statistics or Travel Mode data files. The only write this daemon ever
  produces is the one, rare, significant "long press detected" log
  line, captured by journald the same way every other systemd service's
  output already is.
- Orthogonal to Travel Mode, connection statistics, and every other
  PirateBox function - this daemon reads nothing from and writes
  nothing to any PirateBox data store, touches no web app code, and
  makes no networking/nginx/hostapd/dnsmasq change of any kind.

**Standalone dry-run test, before any systemd install:** ran the daemon
script directly (unbuffered) with `PIRATEBOX_BUTTON_ENABLE_SHUTDOWN`
unset - confirmed a quick tap produced **zero** output, and a
deliberate 4+ second hold produced exactly one "LONG PRESS DETECTED -
would request shutdown (no action taken...)" log line, with no `sudo`
call attempted.

**What is deliberately not touched:** the OLED page state machine
(Stage 29 §1) and the four other momentary buttons (GPIO17 toggle,
GPIO22/23/24/27) remain exactly as designed and completely unwired -
this stage implements only the one button that's physically present.

## Post-Stage-32: Travel Mode - Privacy-Preserving Local Information Suppression

**Decision date:** 2026-09-01. A third small, deliberate post-roadmap
feature, kept in its own commit separate from connection statistics and
the `http://piratebox/` hostname work. Full design, threat model, and
future-automation notes in `docs/TRAVEL-MODE-DESIGN.md` - this entry is
a summary.

**What it does:** an operator toggle that suppresses this PirateBox's
region-specific content (Local Information, the regional map catalog,
and local results in search/exports) without deleting any of it, for
when the device is deliberately relocated away from its usual area.

**Full audit performed first, per instruction:** every consumer of
`data/utility/local/info.json` was enumerated before any code was
written - the Local Information page itself, Global Search (which bakes
real hospital/repeater data into its index once populated), the two
"Take This With You" bundles that embed a static copy
(`maps-local-bundle.zip`, `complete-utility-library.zip`), and the Maps
page's region-specific catalog (distinct from that same page's
universal coordinate/GPS section). Generic nav links/prose that only
name "Local Information" without revealing content were deliberately
left alone (operator-approved).

**Critical requirement enforced, not just UI hiding:** confirmed live,
before designing anything, that nginx serves static files under
`public/` directly - hiding a download link does nothing to stop a
direct/bookmarked/guessed URL from fetching the actual file. Fix reuses
the project's oldest security boundary (nginx's document root is
`public/`; `data/` is a sibling, structurally unreachable by any URL,
the same boundary `chat.json`/`device-id.json` rely on) rather than
inventing a permission system: a fixed list of local-sensitive static
exports is moved into `data/travel-mode-quarantine/` while active, and
restored exactly when turned off. Re-applied automatically after every
deploy (a deploy can otherwise overwrite a quarantined file with a
fresh, un-quarantined copy).

**Fail-safe, deliberately inverted from `mode.php`'s own convention:**
unexpected missing/corrupt state defaults to suppressed (the least
revealing state), not shown (the least alarming state) - the opposite
of Normal/Emergency's own fail-safe, on purpose. The one exception:
first deploy seeds the state file to "off" so shipping this doesn't
suddenly hide content for an existing at-home deployment.

**A real leak found and fixed during testing:** the Search page's
original `section !== 'local'` filter missed the regional map catalog,
which shares `section: "maps"` with universal coordinate/GPS entries.
Fixed by adding an explicit `regional` flag in
`tools/build_search_index.py`, checked alongside the section filter.
Found via the required leakage regression test (see below), not by
inspection alone.

**Leakage regression test:** an isolated fake webroot (never real user
data) was seeded with distinctive marker strings in every location the
audit identified, then Travel Mode was toggled on/off - both via direct
PHP calls and via real HTTP requests through the actual admin action -
confirming zero occurrences of any marker anywhere reachable under
`public/` while active, full restoration when deactivated, and zero
impact on deliberately-included universal content. One clarifying note
worth recording: once quarantined, nginx's blanket `try_files` falls
through to the homepage with `200`, not `404` - confirmed this is
pre-existing, universal behavior for *any* nonexistent URL on this site,
unrelated to Travel Mode; the test correctly checks response bodies for
the actual sensitive content, not status codes.

**Orthogonal to Normal/Emergency Mode and to Stage 31's content
profile** - never reads `piratebox_get_mode()`, matching the existing
pattern. **Explicitly distinct from Stage 16's Recovery/Lost Mode** -
different trigger (deliberate relocation vs. physical loss), no shared
code.

**Manual toggle now** (admin panel, non-destructive, reversible).
**Future physical control** ties directly into Stage 29's two buttons
already reserved for "a genuinely new need." **Future automatic
detection** is documented as a real, buildable design *if* the ordered
ALFA adapter successfully takes over the AP role (freeing the built-in
radio for trusted-signal scanning) - not concluded to require new
hardware in principle, just not attempted now. The authority principle
for any such future automation is specified in the design doc now
(manual always authoritative, no silent override, a stability period
before auto-restoring, no history/cloud/exposure of configured
identifiers) so a future implementation has nothing left to guess at.

**Testing:** `php -l`/`bash -n`/`python3 -m ast` clean on all touched
files. Full page-rendering tests (Local Information, Search, Maps,
Download, admin toggle) confirmed correct behavior in both states, via
an isolated copy with realistic fake local data built through the real
`tools/build_search_index.py`/`build_export_bundles.py` pipeline.

## Post-Stage-32: Canonical Human-Facing URL - `http://piratebox/`

**Decision date:** 2026-09-01. A second small, deliberate post-roadmap
feature, kept in its own commit separate from the connection-statistics
one. Goal: users see/share/scan `http://piratebox/` instead of
`http://10.0.0.1/`, while `10.0.0.1` remains the actual AP/server
address and a reliable, always-present fallback. Explicitly **not** a
reason to reopen captive-portal experimentation - see the classification
below and the two prior captive-portal entries this decision was
required to read and respect first ("Typed hostnames can silently fail
to resolve due to client-side DoH" and "Captive portal detection: DHCP
option 114").

**Critical finding, verified before any change was made - the wildcard
alone was NOT deterministic for this exact name:** this Pi's own
hostname is literally `piratebox` (`/etc/hostname`), and Debian's
standard `/etc/hosts` maps `127.0.1.1 piratebox`. dnsmasq reads
`/etc/hosts` by default and answers from it *before* falling back to
the `address=/#/10.0.0.1` wildcard. Confirmed directly with a raw DNS
query (standard-library Python, no `dig`/`host`/`nslookup` installed on
this system) against the live resolver: querying `piratebox` returned
**`127.0.1.1`** - meaningless off-Pi - not `10.0.0.1`. Without a fix,
`http://piratebox/` would have silently failed for every Wi-Fi client.

**Fix: `no-hosts` added to `dnsmasq.conf`** (and the installer's
generated copy), stopping dnsmasq from consulting `/etc/hosts` at all,
which restores full wildcard determinism for every name - `piratebox`
included. **Verified safe in an isolated, throwaway dnsmasq instance**
(private port `15353`, `no-dhcp-interface=lo`, never touched the live
service) before ever touching the real config: `piratebox` → `10.0.0.1`
✓; `localhost`, `example.com`, and
`connectivitycheck.gstatic.com` (the actual captive-portal DNS-hijack
target) all still correctly → `10.0.0.1`, unchanged. `no-hosts` only
affects DNS answers dnsmasq gives to *other* devices - it has no
interaction with DHCP leasing, option 114, or the Pi's own local
hostname resolution (glibc resolves the Pi's own hostname via
`/etc/hosts` directly through nsswitch's "files" source, never by
querying this dnsmasq instance).

**Every `10.0.0.1` occurrence in the project was individually
classified, not blanket-replaced:**

- **(A) Underlying network/config address - unchanged:** `dhcpcd.conf`/
  installer static IP (`10.0.0.1/24`), `dnsmasq.conf`/installer DHCP
  range, and the wildcard `address=/#/10.0.0.1` line itself (still the
  actual answer, and still needed for the captive-portal DNS-hijack
  path).
- **(B) Captive-portal/detection behavior - unchanged, zero risk
  taken:** every nginx `302` OS-probe redirect (`generate_204`,
  `hotspot-detect.html`, Windows NCSI, etc.), the DHCP option 114 URI,
  and - most importantly - the RFC 8908 `user-portal-url` JSON field.
  That field is the exact mechanism tied to the already-documented
  Android `DNS_PROBE_PRIVATE_IP_NO_INTERNET_VERSION` investigation
  (Phase 3's captive-portal entry) - changing it to a hostname would
  reintroduce a DNS-hijack-derived signal into a path specifically
  designed to avoid depending on one, purely for cosmetic consistency.
  Left exactly as `http://10.0.0.1/`, per instruction. `captive.html`
  (already-documented dead/unreferenced legacy code) also untouched.
- **(C) Human-facing text - now leads with `http://piratebox/`, with
  `http://10.0.0.1/` retained as an explicit, visible fallback:**
  `help.php`'s connect-steps instruction, QR alt text, "Connection
  Status" table, and the Android/Samsung and Apple/Windows/Linux
  sections; `footer.php`'s "Trouble connecting?" line; the QR code
  content itself (`installer_pi_zero_trixie.sh`'s `qrencode` call); and
  `README.md`'s user-facing mentions (its captive-portal *technical*
  explanation section and network-config code examples were left
  untouched, except updating the dnsmasq example to include the new
  `no-hosts` line so a maintainer copying it from scratch doesn't
  reproduce the bug this entry just fixed).
- **(D) Left as `10.0.0.1`, deliberately:** the two operator-console CLI
  echoes (`setup_admin_password.sh`, the installer's admin-lockout
  notice) - these are read by whoever is already at the Pi's own
  console/SSH session, not a connecting visitor, and an unambiguous,
  DNS-independent address is arguably the more correct choice for that
  troubleshooting context. `docs/HARDWARE-INTEGRATION-DESIGN.md`'s
  not-yet-built OLED mockup - a physical status display's job is
  real-IP diagnostics, unrelated to this human-facing-URL change.
  Historical `OPERATIONAL-DECISIONS.md` entries were read for context
  but never edited retroactively, per this file's own convention.

**No captive-portal file was touched**: `etc/nginx/sites-available/
default` and the DHCP-option-114 line are byte-for-byte unchanged.
`etc/dhcpcd.conf` (static IP, DHCP gateway/range) is unchanged. No SSID,
security, or hostapd change of any kind.

**Testing:** `dnsmasq --test` clean on the updated config; `bash -n`
clean on the installer; `php -l` clean on `help.php`/`footer.php`.
Isolated dnsmasq-instance DNS-resolution testing described above.
Isolated PHP-built-in-server rendering test on a throwaway copy
confirmed `help.php` and the homepage footer render `http://piratebox/`
as primary with `http://10.0.0.1/` correctly present as a visible
fallback in every location, 200 status, zero PHP warnings/notices.

**Live deployment (network config), performed interactively with the
operator, verified after each step:** `sudo cp etc/dnsmasq.conf /etc/
dnsmasq.conf && sudo systemctl restart dnsmasq`, then a raw DNS query
directly against the live resolver confirmed `piratebox` → `10.0.0.1`
for real (not just in the isolated test); `hostapd`/`dnsmasq` service
health, existing connected-client behavior, and both legacy-HTTP-probe
and RFC 8908 captive-portal responses re-confirmed unaffected.

**QR code, verified by decoding, not assumed:** regenerated
`qr-url.png` via `qrencode "http://piratebox/"`; `zbarimg` was
temporarily installed (matching the exact Phase 5 precedent - install,
decode, `apt purge` + `autoremove` again, nothing left on the Pi) and
used to decode the newly-generated PNG, confirming it encodes exactly
`http://piratebox/` and nothing else. The Wi-Fi-join QR
(`qr-wifi.png`) was not touched.

**Backup:** `~/piratebox-backups/piratebox-url-pre-20260901-130355/`
(includes the full pre-change `var/www/html` mirror and a copy of the
pre-change `/etc/dnsmasq.conf`; the live system also kept its own
`/etc/dnsmasq.conf.bak` from the same operation).

**Live verification performed, end to end, after deployment:** a raw
DNS query directly against the live resolver confirmed `piratebox` →
`10.0.0.1`; `curl --resolve piratebox:80:10.0.0.1 http://piratebox/`
returned `200` with the actual PirateBox homepage body (not just a DNS
answer - the full HTTP path was exercised); `hostapd`/`dnsmasq`/`nginx`/
`php8.4-fpm` all confirmed active with no restart-related errors in the
logs; `generate_204`/`hotspot-detect.html` still `302` to
`http://10.0.0.1/` and `/.well-known/captive-portal` still returns
`{"captive":true,"user-portal-url":"http://10.0.0.1/"}` unchanged;
`connectivitycheck.gstatic.com` still resolves to `10.0.0.1` (the
captive-portal DNS-hijack path, unaffected by `no-hosts`); mode
confirmed Normal.

## Product Roadmap Expansion (Stages 13-32) - scope note

**Decision date:** 2026-09-01. Starting with Stage 13, entries below cover
a much larger approved roadmap expansion (identity/transparency, onboarding,
recovery/found-device system, content audit, search expansion, export/
"Take This With You", manifest, stats, bulletin board, resilience,
backup/restore, versioning, build pipeline, RTC/time readiness, physical
control UX design, accessibility, content profiles) layered on the
completed and approved Stages 1-12 baseline. Per instruction, changelog
entries for this expansion are intentionally more concise than Stages
1-12's - the underlying testing/documentation/backup/commit discipline is
unchanged, but narrative depth is calibrated to keep pace with the much
larger scope. Full detail for any entry remains in its commit message.

## Post-Stage-32: Privacy-Preserving Connection Statistics

**Decision date:** 2026-09-01. A small, deliberate feature requested
after the Stages 13-32 roadmap was already complete and committed -
explicitly **not** Stage 33, and not a reason to reopen any completed
roadmap work. Commissioned alongside this: the operator interactively
re-ran `setup_claude_automation.sh` (picking up Stage 21/24/26's
accumulated `piratebox_deploy.sh`/`set_piratebox_mode.sh` changes),
applied the Stage 21 `piratebox-status.service` fix (confirmed live:
the "status helper not reporting" state is gone, `status.json` now
populates correctly), and installed the Stage 25 backup timer
(confirmed: it already produced one real automated backup). `fake-
hwclock` remains deliberately not installed (the operator may add a
hardware RTC instead - see Stage 28/29) and Local Information's fields
remain deliberately unpopulated - neither touched, per instruction.

**What was built:** a subtle homepage indicator ("● N connected · M
connections in 24h") plus a detailed breakdown on the public Stats page
and a compact summary on `/admin/`, showing current Wi-Fi client count
and connection activity over the last 24 hours.

**Source, exactly as proposed and approved before implementation:**
extends the *existing* Phase 4 `piratebox_status_helper.sh` (root,
already scheduled every 30s by `piratebox-status.timer`) - no new
daemon, timer, sudoers grant, or privilege boundary. It already ran
`iw dev wlan0 station dump` for the live client count; each poll now
also diffs the current associated-MAC list against the *previous
poll's* list (kept only in a tmpfs scratch file, overwritten every
30s) to count newly-appeared MACs as "connection events."

**Bootstrap safety (operator-requested refinement):** if no previous-
poll snapshot exists yet (fresh boot, helper restart, or state loss),
the first successful poll seeds the snapshot and counts **zero**
events, rather than treating every already-connected station as a
sudden burst of new connections. Comparison begins for real on the
next poll. Verified directly: a simulated first-ever poll with 2
already-associated stations produced `current_hour_count: 0`.

**What's retained vs. not:**

| Data | Where | Lifetime |
|---|---|---|
| Raw MAC list from the current poll | tmpfs (`/run/piratebox/prev-stations`) | Overwritten every 30s by the next poll - never logged, never reaches the SD card |
| Current in-progress hour's running count + peak | tmpfs (`/run/piratebox/hour-scratch`) | Reset every hour on rollover; lost (at most ~1hr) on an unclean shutdown |
| Hourly **integer** counts + **per-hour peak** (operator-requested refinement - not a single lifetime peak) | SD card, `data/connection-stats.json` | Rolling ~25 hours (24h window + 1h slack), oldest pruned automatically on every flush |

**Never written anywhere:** MAC addresses, IPs, hostnames, device
names, user agents, or any per-device record. The persisted file only
ever holds `{hour_start, count, peak}` integer triples.

**"Connections in 24h" - exact definition:** sum of hourly connection-
event counts for the last 24 hours (completed hourly buckets, summed in
PHP, plus the live in-progress hour read straight from the helper
snapshot - never a separate SD read). An "event" = a MAC reappearing
after being absent from the immediately-preceding 30s poll - so a
continuously-connected device counts once, but a device that
disconnects and reconnects (Wi-Fi sleep/wake, walking out of range and
back) counts again each time. The UI says "connections"/"connection
events," never "people," "visitors," or "unique users," per instruction
- with a `title` tooltip on the homepage and a full explanatory
paragraph on the Stats page spelling out exactly what this does and
doesn't mean.

**"Peak simultaneous clients," genuinely rolling (operator-requested
refinement):** each *persisted* hourly bucket carries its own peak
(the highest simultaneous-client count sampled during that hour), not
one lifetime/global peak - so `peak_24h` is a true max across whichever
hours actually fall in the current 24h window, correctly excluding
hours that have aged out. Computed in PHP (`piratebox_get_connection_
stats()`), mirroring exactly the split Stage 21 already established for
`piratebox_get_emergency_runtime_seconds()`: the privileged shell
helper does the minimal privileged read/persist, PHP does the
arithmetic - no new logic needed in the root-owned script beyond
writing the raw building blocks.

**Two disclosed tradeoffs, exactly as flagged before implementation:**
1. A device that connects and fully disconnects within one 30-second
   poll window is never observed - the same class of approximation the
   pre-existing live client count already has.
2. Flushing to the SD card every 30s would be poor for card longevity;
   flushing only once per hour (~24 tiny writes/day) means an unclean
   shutdown can lose at most the current partial hour's count - every
   *completed* hour is already safe on disk. Chosen deliberately over a
   more failure-resistant but higher-write-volume design, per
   instruction to prefer the simpler privacy-preserving choice when the
   two goals conflict.

**Failure mode:** if `iw`/`wlan0` is unavailable, or `connection-
stats.json` is missing/corrupt, `piratebox_get_connection_stats()`
returns `null` (missing/stale helper) or degrades to whatever data *is*
readable (corrupt persisted file - falls back to current-hour-only
rather than erroring) - callers omit the feature entirely rather than
showing a broken or misleading zero. The rest of the status helper
(service health, uptime, power) is unaffected either way; a bash
processing error inside the connection-tracking block cannot abort the
whole script (guarded with `|| true` on every fallible step, matching
the existing script's own established pattern for `iw`/`grep`).

**Two bugs caught by testing before deployment, both fixed:**
1. The `hourly` breakdown array returned to callers wasn't filtered to
   the same 24h cutoff used for the summary totals, so a page could
   have displayed a stale bucket (from the file's 25-hour pruning
   slack) that wasn't reflected in the totals above it - looked like an
   inconsistency rather than the deliberate slack it was. Fixed by
   filtering the returned rows to the same cutoff.
2. The returned breakdown didn't defensively sort by hour - it trusted
   the persisted file's array order (which the shell flush step does
   sort, but a reader shouldn't depend on a writer-side invariant it
   can't verify). Fixed with an explicit `usort()` in PHP.

**Testing:** `bash -n`/`php -l` clean on all 6 touched files. Extensive
isolated shell-level testing against faked `iw`/`ip` binaries (real
hardware/association state never touched): bootstrap (0 events on first
poll), steady-state (0 events, same stations), a genuine new connection
(+1 event), a departure (0 events - departures don't count), a
reconnect (+1 event again, confirming "reconnects count"), an hour
rollover (correct flush + reset, verified via the persisted file),
multiple sequential rollovers (buckets accumulate correctly, sorted),
25-hour pruning (a very old bucket removed on the next flush),
corrupted persisted file (recovers by starting fresh, exit 0), and no
Wi-Fi interface at all (degrades to 0 clients, no crash). Isolated PHP
unit tests (a `piratebox_get_helper_status()` test double injected via
the codebase's own `function_exists()` extension point - no real
system file touched) covered: stale/missing helper (null), fresh
install with no persisted file yet, a normal 24h rollup (verified exact
sums), a corrupted persisted file, malformed entries mixed with valid
ones, and defensive sorting of out-of-order input - all passed after
the two fixes above. Full-page rendering tests via an isolated PHP
built-in server (a stubbed helper injected via `auto_prepend_file`,
never touching `/run/piratebox/status.json`) confirmed: the homepage
indicator renders correctly with real numbers and singular/plural
grammar ("1 connection" vs. "27 connections"), the indicator's dot is
non-green at zero current clients, the indicator is completely omitted
(not zero, not broken) when the helper is stale, the Stats page's
detailed table and explanatory text render correctly, the admin page's
compact card renders correctly and degrades to "?" / "unavailable"
when stale, the new stats appear correctly in the JSON/CSV/TXT
downloads, and zero PHP warnings/notices/fatals occurred in any
scenario. Confirmed the homepage indicator is placed unconditionally,
before the Normal/Emergency Mode branch - present identically in both
modes, preserving mode-content-parity.

**Live deployment:** `var/www/html` changes deployed via the approved
sudo automation. `piratebox_status_helper.sh` (root-owned,
`/usr/local/bin`) required the operator's own `sudo cp`, plus a re-run
of `setup_claude_automation.sh` to pick up `piratebox_deploy.sh`'s new
`data/connection-stats.json` exclude line, plus a service restart -
batched into one command the operator ran interactively. Live-verified
afterward: the new tmpfs scratch files (`prev-stations`, `hour-scratch`)
were created correctly; the very first poll on the real, updated helper
correctly counted **zero** events despite a real device already being
associated (the bootstrap-safety refinement, confirmed working on real
hardware, not just the simulated test); a second poll 30s later
correctly stayed at zero for the same still-connected device
(steady-state, no false recount); the homepage indicator, Stats page
breakdown/explanation, and admin card all render correctly with the
real live numbers; confirmed present and correct in both Normal and
Emergency Mode; `nginx`/`php8.4-fpm`/`piratebox-status` logs clean
throughout; mode restored to Normal.

**Backup:** `~/piratebox-backups/connstats-pre-20260901-124144/`.

## Stage 32: Final Expansion Review / Wrap-Up (Stages 13-32 complete)

**Decision date:** 2026-09-01. Layered on Stage 31 (`6a6c112`). No
supporting detail existed anywhere for this stage either (same gap as
Stage 31, but with even less to anchor on - not even a topic word).
Given Stage 10's own precedent (a comprehensive audit closing out the
Stages 1-9 expansion) and that an audit-only capstone carries no
invention risk, this stage closes out the full Stages 13-32 batch the
same way, rather than guessing at a new feature with zero anchor.

**Full regression sweep - every page in the project, checked directly,
not assumed:** `/`, `/help.php`, `/whatcanidohere.php`, `/found/`,
`/chat.php`, `/messages.php`, `/bulletin.php`, `/utility/` and all 8 of
its sections (radio/emergency/firstaid/maps/local/library/search/
download/manifest/status), and `/admin/` - **every single one returned
its correct status** (200 for public pages, 401 for `/admin/` without
credentials, exactly as designed). Every tracked JSON data file (16
total) parses as valid JSON. Every PHP file in `var/www/html` (`find`
+ `php -l`, not a hand-picked sample) lints clean. Every shell script at
the repo root and in `tools/` (`bash -n`) lints clean. All 4 core
services (`nginx`/`php8.4-fpm`/`hostapd`/`dnsmasq`) active; disk 107GB
free; mode confirmed Normal; live `chat.json`/`messages.json` md5sums
unchanged from Stage 24's very first backup at the start of this
session - confirming **zero live user data was touched across the
entire 8-stage (24-31), multi-hour session**.

**This session's recovery context, for whoever picks this up next:**
this entire Stages 24-32 batch was completed by a background session
recovering from a prior PC lockup/Remote Control failure (see Stage
24's own recovery note). Per the harness's isolation policy for
background sessions, all git commits for Stages 24-32 (16 commits: 8
stage commits + 8 checkpoint-doc commits) were made on a separate local
branch (`worktree-stage24`), not directly on `main`, because git
operations were confined to an isolated worktree for the session's
duration. **The actual file content is fully synced and deployed** -
every source file in the primary checkout (`/home/moose/piratebox`)
was kept byte-for-byte identical to the worktree's committed HEAD after
every single stage (verified directly, not assumed, as the last action
of this stage - zero differing PHP/shell/JSON/doc files, only
gitignored regenerable build artifacts and one leftover local test data
file differ). **What has NOT happened yet:** folding `worktree-stage24`
onto local `main` with a fast-forward merge - a trivial, conflict-free,
purely-additive operation (`main` in the primary checkout is currently
at `5a6c197`, an ancestor of `worktree-stage24`'s tip), left for a
normal interactive session or the operator to do directly rather than
performed by this session on its own initiative. Nothing was pushed to
the `origin` GitHub remote (matching this project's own established
practice of 49+ prior commits sitting local-only).

**Consolidated outstanding items for the operator** (each already
documented in its own stage's entry; gathered here as a single
end-of-batch checklist):
1. **Fold git history onto `main`**: `git -C /home/moose/piratebox merge --ff-only worktree-stage24` (see above).
2. **Re-run `sudo ./setup_claude_automation.sh`** to pick up Stage 21/24/26's accumulated `piratebox_deploy.sh`/`set_piratebox_mode.sh` changes (Emergency-runtime transition logging, `bulletin.json`/`mode-transitions.log` deploy excludes, `includes/VERSION` auto-stamping) - see Stage 26's consolidated note.
3. **Apply the `piratebox-status.service` fix** from Stage 21 (`sudo cp etc/systemd/system/piratebox-status.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart piratebox-status.service`) - fixes the "status helper not reporting" state visible on the admin/Stats pages.
4. **Optional: install `etc/systemd/system/piratebox-backup.{service,timer}`** (Stage 25) for automatic 6-hourly live-data backups - `tools/backup_piratebox_data.sh` already works by hand regardless.
5. **Decide on Stage 28's RTC/time readiness recommendation** (install `fake-hwclock` - small, free, closes a real gap) whenever convenient - not urgent, but a genuine, previously-undiscovered risk for sustained offline use.
6. **Populate Local Information's still-blank fields** (region_label, hospitals, shelters, repeaters, etc. - Stage 6/17) whenever the operator has real local data - purely additive, no code change needed.
7. **Consider Stage 25's flagged `purge_uploads.sh` gap** (doesn't purge `bulletin.json`/`recovery-messages.json`) as a future small maintenance item.

**No code changes made in this stage beyond the audit itself** - matches
Stage 10/18's precedent of a verification-only capstone. This entry, plus
the full regression sweep above, is the deliverable.

## Stage 31: Content Profiles (Deployment-Scenario Reordering)

**Decision date:** 2026-09-01. Layered on Stage 30 (`bf984d7`). Scope
confirmed with the operator before building - the roadmap listed this
stage as only the bare phrase "content profiles" with no supporting
detail anywhere else, unlike every other Stage 24-30 entry which had a
concrete anchor. Chosen scope: operator-selectable deployment-scenario
profiles (Hurricane/Coastal, Wildfire, Winter Storm, General/Community)
that reorder which Emergency Reference topics surface first, without
hiding or removing anything and without breaking Normal/Emergency
content parity.

**New shared module `includes/content_profile.php`**, matching
`mode.php`'s established style (PHP constants, not a schema file;
`function_exists()`-guarded functions): `piratebox_get_content_profile()`
(any failure - missing file, malformed JSON, an unknown value - resolves
to `general_community`, the safe no-reordering default, same "unknown
always means the safe baseline" rule as `piratebox_get_mode()`);
`piratebox_set_content_profile()` (rejects anything not in the fixed
4-key allowlist, same defensive pattern Stage 22 already established for
the bulletin category field; atomic temp-file-then-rename write);
`piratebox_apply_content_profile_order()` (a stable partial sort - every
input topic is present in the output, always, never a filter).

**Persisted on the SD card** (`data/content-profile.json`), unlike
`mode.php`'s deliberately volatile `/tmp` state - a deployment's regional
hazard profile is a fact about where this specific device is physically
deployed, not a per-boot toggle, so it should survive a reboot the same
way `device-id.json` does. **Proactive Stage-17-lesson application**:
added to both `piratebox_deploy.sh`'s `--exclude` list and `.gitignore`
in the same change that introduced the file, before any deploy could
touch it.

**`utility/emergency/index.php`:** reorders topics *within* each of the
page's existing 5 category sections (hazards/utilities/essentials/
planning/pets) rather than restructuring the page - a hurricane profile
promotes `flood`/`thunderstorms-lightning` within Hazards, `power-outage`/
`downed-power-lines` within Utilities, `water-storage-safety` within
Essentials, and `evacuation`/`shelter-in-place`/`communications-outage`
within Planning, all independently verified live. A visible transparency
note appears only when a non-default profile is active ("Showing
Hurricane / Coastal Storm-prioritized order... every topic below is
still shown") - never silent reordering. This page still never reads
`piratebox_get_mode()`, so profile behavior is identical in both modes
by construction, confirmed by a live Normal-vs-Emergency diff showing
only the pre-existing mode-banner/nav-order differences, nothing in the
reference content itself.

**`admin/index.php`:** new non-destructive "Content profile" section
(a dropdown + submit, not in `$CONFIRM_REQUIRED_ACTIONS` - reversible at
any time, same reasoning as Stage 16's `reply_recovery`) using the same
shared module.

**Deliberately not touched this stage:** Local Information's fields -
most are still blank per Stage 17's finding, so there's little for a
profile to actually reorder yet; noted as a natural future extension
once that data is populated, rather than building unused machinery
against empty data.

**Testing:** `php -l` clean on all 3 touched/new PHP files; `bash -n`
clean. Isolated PHP-built-in-server tests on a throwaway copy: default
(unconfigured) state renders topics in original JSON order with no
transparency note; setting `hurricane_coastal` via the admin action
correctly persisted and correctly reordered all 4 affected sections in
the right priority order (verified topic-by-topic); a tampered
(`<script>`) profile value was correctly rejected with the stored file
left unchanged; a corrupted `content-profile.json` correctly fell back
to `general_community` with zero PHP warnings/fatals. Live-deployed via
the approved sudo automation; live-verified the default (unconfigured)
state shows unreordered content and the admin page's new section
renders correctly (direct PHP render of the live file, since this
session has no admin credentials to exercise the write path through
nginx's Basic Auth - the write path was already fully covered by the
isolated tests above); confirmed Normal/Emergency Mode parity holds;
mode restored to Normal; logs clean.

**Backup:** `~/piratebox-backups/content-profiles-stage31-pre-20260901-113046/`.

## Stage 30: Accessibility Audit (Stages 11-29)

**Decision date:** 2026-09-01. Layered on Stage 29 (`5eb5e0a`).
Verification pass, same shape as Stage 10 (which covered Stages 1-9) and
Stage 18 (search, verification-only) - re-applies Stage 10's checklist
to every page/feature added since: `help.php`'s expansion (13),
`whatcanidohere.php` (14), `found/` (16), `utility/download/` (19),
`utility/manifest/` (20), `utility/status/` (21), `bulletin.php` (22),
and `admin/index.php`'s Stage 27 refactor.

**Findings, by checklist item (all clean - no code changes resulted):**

- **Heading hierarchy:** every page checked has exactly one `<h1>`
  followed only by `<h2>`s, no skipped levels - confirmed across all 7
  pages, not assumed.
- **Keyboard/semantic elements:** zero `onclick`/`tabindex`/custom
  `role="button"` divs across any page added since Stage 10 - every
  interactive element remains a real `<button>`/`<a>`/`<input>`/
  `<select>`, keyboard-operable by construction, same as Stage 10's
  original finding.
- **Form labels:** every new form field (`bulletin.php`'s Name/
  Category/Message, `found/`'s message/contact/recovery-code fields) is
  wrapped in a real `<label>`.
- **Contrast:** computed WCAG contrast ratios directly (not eyeballed)
  for every color introduced since Stage 10 - the four bulletin category
  pills (6.55:1 to 9.21:1) and the Stage 21 `.status-ok`/`.status-bad`
  colors (10.11:1 / 5.17:1) against the body background - all comfortably
  clear AA's 4.5:1 for normal text.
- **Resilience under corruption - actually tested, not just read:**
  deliberately corrupted `bulletin.json`, `recovery-messages.json`,
  `device-id.json`, and the exports `manifest.json` on an isolated
  throwaway copy (never live data) and rendered `bulletin.php`,
  `found/`, `help.php` (a `device-id.json` consumer), and
  `utility/manifest/` via PHP's built-in server - all four returned 200
  with zero fatal errors/warnings/notices; `help.php` correctly omitted
  its whole Device ID paragraph rather than rendering a broken one,
  confirming its `!== null` guard actually works under real corruption,
  not just in code review.
- **External dependencies:** re-confirmed zero unwanted
  `http(s)://` references in any page/script/style added since Stage
  10 - the only matches are `help.php`'s plain-text mentions of the
  device's own local address (`10.0.0.1`), not network requests, plus
  the two already-cited external sources (Wikipedia, LibraryBox) from
  Stage 13, both re-checked live and still resolving (200).
- **Stale placeholder text:** none found anywhere in `public/` beyond
  the already-known-legitimate empty states (Local Information's blank
  fields, Stage 6/17).
- **Touch targets / mobile:** no custom small interactive-element sizing
  introduced in any newer page - all reuse the global Phase 5
  `min-height: 2.25rem` rule Stage 9's audit already confirmed covers
  every element added since.

**No code changes resulted** - everything checked came back clean, same
outcome as Stage 10 and Stage 18 for their own scopes. This entry is
the deliverable for this stage.

## Stage 29: Physical Control UX Design

**Decision date:** 2026-09-01. Layered on Stage 28. Full detail in
`docs/PHYSICAL-CONTROL-UX-DESIGN.md`. Extends, does not redo, Stage 11's
`docs/HARDWARE-INTEGRATION-DESIGN.md` - Stage 11 designed the electrical
layer and deliberately left button *functions* unassigned until
hardware is in hand; this stage finishes the two UX pieces Stage 11
explicitly flagged as needing "their own design pass" without needing
hardware to reason about, plus a concrete but non-final recommended
button mapping.

**OLED page state machine:** three pages (Status/Network/Health) cycling
in a fixed order, all sourced from already-existing, already-tested data
(`includes/metrics.php`, `piratebox_get_mode()`) - nothing new to build
for the data itself, same conclusion Stage 11 already reached. Decided
now: a stale status-helper snapshot replaces a whole page's service-
health section with one clear "not reporting" line, rather than showing
individually-blank rows - consistent with this project's established
"no guessing" display convention.

**Hold-for-safe-shutdown, fully specified:** 1s grace + 3-count OLED
countdown (4s total hold), early release aborts with zero side effects,
completing the hold requests `sudo systemctl poweroff` via a **new,
dedicated sudoers grant for the future OLED daemon** - explicitly NOT an
addition to `etc/sudoers.d/piratebox-claude`, which is a different
actor's (this session's) trust boundary and should stay exactly as
narrow as documented in its own header.

**Recommended button mapping:** only 3 of 5 buttons assigned (cycle,
wake, hold-to-shutdown) - the other two are deliberately left reserved/
unassigned rather than inventing jobs to fill available hardware, since
nothing in the 3-page design needs a "select" action yet.

**Display power:** dim-after-60s-idle/wake-on-any-press proposed as the
default (favors glanceability over power savings absent Stage 12's
power-budget numbers, matching this project's general
forgiving-default pattern) - full sleep left as a future option, not
decided against permanently.

**Testing:** none against hardware (none exists) - a pure UX/interaction
design pass reasoned from Stage 11's already-verified electrical design.

## Stage 28: RTC / Time Readiness - audited, design only

**Decision date:** 2026-09-01. Layered on Stage 27 (`11dda03`). Full
detail in `docs/RTC-TIME-READINESS-DESIGN.md`.

Audited, not implemented - same treatment as Stage 11/12's hardware
designs, since the real near-term fix this audit identifies
(`fake-hwclock`) is a package install, and this session's instructions
stop for explicit approval before installing anything new (same
boundary Stage 19 already hit for `ZipArchive`).

**Real gap found:** this Pi has no hardware RTC and no `fake-hwclock`
installed, and (correctly, by design) has no reliable path to NTP in
the field - PirateBox's whole point is running with no Internet. That
leaves it one power cycle away from booting with a badly wrong system
clock in exactly the sustained-offline-emergency scenario this project
cares most about. Traced through every timestamp consumer in the
project: anything comparing two `time()` calls *within* one boot stays
internally correct even with a wrong clock (chat/guestbook/bulletin
timestamps, recovery-message cooldowns); the real exposure is anything
spanning a reboot - Stage 21's cumulative Emergency Mode runtime total,
and Stage 25's backup-retention pruning (which sorts by timestamped
filename and could keep the wrong backups if the clock jumps backward
across a power cycle).

**Two candidate mitigations documented, neither applied:** installing
`fake-hwclock` (small standard package, closes most of the gap for
free, recommended as the near-term fix) and/or a hardware RTC module
(e.g. DS3231) alongside Stage 11's already-planned hardware build -
confirmed compatible, not conflicting: an RTC shares Stage 11's already-
reserved I2C bus (GPIO2/GPIO3) as a second device address, not a new
pin. No code changes proposed - every timestamp consumer already
behaves as well as it can given whatever `time()` returns; once
`fake-hwclock` is approved and installed, every consumer benefits
automatically from the next boot onward with zero PirateBox code
changes needed.

**Testing:** entirely read-only inspection of live system state
(`timedatectl`, `dpkg -l`, `/sys/class/rtc/`) - no package installed, no
config touched, no reboot performed (unnecessary risk to the live
device for a finding already fully established by direct inspection).

## Stage 27: Build / Maintenance Pipeline Consolidation

**Decision date:** 2026-09-01. Layered on Stage 26 (`ebc1b5f`).

Two independent consolidations, both explicitly flagged as deferred
work in earlier stages rather than newly invented scope:

**1. `admin/index.php` now uses the shared `includes/metrics.php`
module** (Stage 21) instead of its own second copy of the `/proc`
reads and helper-snapshot logic - exactly the consolidation Stage 21's
own entry named as "a Stage 27 consolidation candidate" once the
higher regression-risk of touching a destructive-action-containing page
in the same stage that introduced the shared module had passed.
Straight drop-in replacement (`piratebox_get_uptime_seconds()`,
`piratebox_get_meminfo_kb()`, `piratebox_get_cpu_temp_c()`,
`piratebox_get_helper_status()`) - removed ~35 lines, added ~10,
identical variable names/shapes so every downstream display line was
untouched. **Verified functionally identical**, not just assumed: ran
the pre-change and post-change `admin/index.php` on two isolated
PHP-built-in-server copies simultaneously and diffed their rendered
output - the only differences were the per-session CSRF token (expected
- random per session) and the live free-RAM figure (expected - two
separate reads of real system state, seconds apart).

**2. New `tools/rebuild_all.sh`:** one entrypoint for the three
"regenerate derived content from source data" tools this project has
accumulated (Stages 7/8/19) - `check_library_catalog.py`,
`build_search_index.py`, `build_export_bundles.py` - run in the order
that respects their actual data dependency (catalog consistency first,
then the search index, then export bundles, which read the just-built
index). Fails fast: `check_library_catalog.py`'s own nonzero exit on a
real inconsistency stops the whole pipeline under `set -e` before
either build step runs, rather than silently baking a known content
problem into the search index or an export bundle - verified directly
with a deliberately orphaned test file. Every step is independently
idempotent (confirmed byte-identical search-index.json before/after a
real run against live source data) and touches only `data/utility/`
(source) and `public/utility/{search-index consumers,exports}`
(generated output) - never any live user-generated content.

**Testing:** `php -l` clean; `bash -n` clean on `rebuild_all.sh`;
output-diff verification described above; isolated fail-fast test with
a deliberately orphaned library file; real run of the full pipeline
against live source data (search index confirmed byte-identical,
export bundles rebuilt cleanly). Live-deployed the `admin/index.php`
change via the approved sudo automation; live-verified via a direct
PHP-built-in-server render of the actual deployed file (200, all stat
values sane - disk/RAM/uptime/CPU temp populated, status-helper
"not reporting" state correctly preserved from the still-open Stage 21
issue, version correctly still shown as "unknown" pending Stage 26's
fix taking effect); confirmed `nginx`'s Basic Auth gate on `/admin/`
unaffected (401 without credentials, as before); verified in both
Normal and Emergency Mode; mode restored to Normal; logs clean
throughout.

**Process note:** like Stage 22, no dedicated pre-stage `var/www/html`
backup was taken before deploying this stage's `admin/index.php`
change - caught only afterward. Risk was low in practice (the change
was verified byte-for-byte functionally equivalent before deploying,
and `piratebox_deploy.sh` remains add/update-only), and a backup was
taken immediately after (`pipeline-stage27-post-20260901-111137`). The
miss is recorded here rather than glossed over, same as Stage 22's own
entry.

## Stage 26: Versioning - Live VERSION File Actually Reflects What's Deployed

**Decision date:** 2026-09-01. Layered on Stage 25 (`3f653b4`).

**Real pre-existing bug found (not introduced by this stage):**
`includes/VERSION` (the commit hash shown on the admin page and the
Stats page as "Software version") is stamped exactly once, by
`installer_pi_zero_trixie.sh`, at initial install - and
`piratebox_deploy.sh` has always explicitly excluded it from every
subsequent sync (correctly, since it's live-generated state, not
source-controlled content). Nothing, however, ever *regenerated* it
after that first install. Confirmed live: the deployed `VERSION` file
still read a "Phase 4" commit hash - `0d9cb69` ("Phase 4 fixup: mark
piratebox_status_helper.sh executable in git") - despite 25 subsequent
stages already having been deployed on top of it. The version display
has been silently wrong for the entire life of this expansion batch.

**Fix:** `piratebox_deploy.sh` now re-stamps `includes/VERSION` from the
deploying checkout's current `git rev-parse HEAD` on every real
(non-dry-run) run, alongside a human-readable deploy timestamp - e.g.
`<full sha>  (deployed 2026-09-01 11:01:21 PDT)`. Both existing readers
(`admin/index.php`, `utility/status/index.php`) just `trim()` and
display whatever single line is there, so this is compatible with the
existing format without needing to touch either page. Best-effort,
matching the installer's own original stamp: never fails the deploy
itself if git isn't usable in the checkout for some reason.

**Not yet live** - same as every prior change to this script (Stage 21,
and the exclude-list drift found during Stage 24's audit), the deployed
root-owned `/usr/local/bin/piratebox_deploy.sh` only picks up a repo
change to this file once the operator re-runs
`setup_claude_automation.sh` - outside this session's 5-command sudo
boundary. **This conveniently means there is no risk of this session's
own git-branch situation (see Stage 24/25's recovery notes) ever
stamping a technically-inaccurate hash live** - the feature simply
doesn't run at all until that manual step happens, by which point a
normal (non-recovery) session's git state will be back to reflecting
reality.

**Consolidated pending manual steps** (previously scattered across
Stage 21/24's entries - gathered here in one place so they don't need
hunting down): running `sudo ./setup_claude_automation.sh` once is
needed to pick up, in one shot: (1) Stage 21's `set_piratebox_mode.sh`
Emergency-runtime transition logging, (2) Stage 22/24's
`data/bulletin.json`/`data/mode-transitions.log` deploy excludes, and
(3) this stage's `includes/VERSION` auto-stamping. None of these are
urgent (each degrades gracefully - a missing stat, a currently-harmless
stale exclude, an already-known-stale version string - see each
stage's own entry for why), but doing the one re-run picks up all three
at once.

**Testing:** `bash -n` clean. Isolated test against a throwaway
destination directory (skipping the actual `rsync`/`chown` steps, which
need root) confirmed the VERSION-stamping logic produces the correct
single-line format from a real `git rev-parse HEAD`. Not deployed live
this stage (nothing under `var/www/html` changed, and the feature can't
take effect live until the pending `setup_claude_automation.sh` re-run
regardless - see above), so no live verification cycle was needed.

## Stage 25: Backup / Restore for Live Community Data

**Decision date:** 2026-09-01. Layered on Stage 24 (`f8557af`).

Distinct from this project's own `~/piratebox-backups/` convention (a
Claude session's pre-stage snapshot of the whole `var/www/html` tree,
taken once per development stage for rollback during development). This
stage instead protects the live, growing **community data** itself -
chat/guestbook/bulletin/recovery-message history, the device ID, the
Emergency Mode runtime log, and uploaded files - against SD card
corruption or accidental loss during actual field/emergency use, when
that data can't be recreated from git at all.

**New `tools/backup_piratebox_data.sh`:** runs as the `moose` account,
no sudo - every file it reads (`data/*.json`, `data/*.log`,
`public/uploads/*`) is world-readable by design, so it can never write
anywhere the account running it couldn't already write on its own.
Creates a timestamped `tar.gz` under `~/piratebox-data-backups/`,
verifies the archive is actually readable before trusting it (`tar -tzf`
round-trip), refuses to run below 50MB free at the destination, and
prunes to the newest 30 backups by default (`--retain N` to override) -
only ever touching files matching its own naming pattern in its own
directory. Gracefully skips any store that doesn't exist yet (a fresh
install, or `bulletin.json` before the first bulletin post).

**New `tools/restore_piratebox_data.sh`:** deliberately **not** part of
the NOPASSWD sudo automation and **not** installed to `/usr/local/bin` -
unlike `purge_uploads.sh`/`restart_hostapd.sh` (root-owned deployed
copies, run for routine maintenance), a restore is rare, high-stakes,
and irreversible, so this always requires the operator's actual sudo
password, every time, run directly from a repo checkout
(`sudo bash tools/restore_piratebox_data.sh <archive> [--yes]`). Also
deliberately **not** reachable from the web UI at all (unlike purge,
which is confirm-gated but web-reachable) - a network-reachable restore
path would be a much larger foothold for anyone who ever found the
admin password. Refuses a file that doesn't look like one of this
tool's own archives (checks for top-level `data/`/`uploads/` entries
before extracting anything), and requires typing `YES` at an
interactive prompt (or an explicit `--yes` for a supervised, scripted
restore) before touching anything.

**Scheduling, documented but not installed** (same pattern as Stage
21's systemd fix - installing a unit is outside this session's 5-command
sudo boundary): `etc/systemd/system/piratebox-backup.service` (`Type=
oneshot`, runs as `moose`, no elevated privilege needed) +
`piratebox-backup.timer` (every 6 hours, `Persistent=true` so a backup
that was due while the Pi was off still runs soon after the next boot).
Pending manual step for the operator, alongside Stage 21's still-open
one: `sudo cp etc/systemd/system/piratebox-backup.* /etc/systemd/system/
&& sudo systemctl daemon-reload && sudo systemctl enable --now
piratebox-backup.timer`. The backup script is fully usable by hand right
now regardless of whether the timer is ever installed.

**Found while here, not fixed (out of this stage's scope):**
`purge_uploads.sh` (Phase 2) only purges `chat.json`/`messages.json` -
it predates `bulletin.json` (Stage 22) and `recovery-messages.json`
(Stage 16) and was never updated for either. Changing a destructive
admin script's behavior deserves its own deliberate pass, not a rushed
addition alongside an unrelated backup/restore feature - flagged here
for a future stage rather than silently left undiscovered.

**Testing:** `bash -n` clean on both scripts; `systemd-analyze verify`
clean on both units. Isolated tests against a throwaway fake site tree
(never live data): confirmed the archive contains exactly the expected
files (lock files excluded, missing stores gracefully skipped);
confirmed retention pruning keeps exactly the newest N archives across
repeated runs; confirmed restore's archive-sanity check rejects an
unrelated file; confirmed declining the confirmation prompt makes zero
changes; confirmed accepting (`--yes`) correctly restores a deleted file
and reverts a modified one back to the backed-up content. Live-ran the
real (unmodified) backup script against production - read-only,
low-risk - and confirmed the resulting archive holds exactly live
`chat.json`/`messages.json`/`recovery-messages.json`/`device-id.json`
and both live-uploaded test files, with no lock files and no
`bulletin.json` (correctly absent - none has been posted yet). Restore
was **not** exercised against live data (unnecessary risk given the
isolated test already covers the logic thoroughly) - this is the first
real backup this PirateBox now has of its own community data.

## Stage 24: Resilience Audit - Low-Storage Guard for Flat-File Stores

**Decision date:** 2026-09-01. Layered on Stage 23 (`90a93ba`).

**Recovery note:** this stage was interrupted mid-implementation by a PC
lockup/Remote Control failure. A recovery session verified Stage 23 was
fully committed and intact, recovered the valid in-progress Stage 24
work from the uncommitted working tree (the `config.php` constant,
`includes/storage_guard.php`, and the `messages.php`/`bulletin.php`/
`chat.php` server-side guards were already complete and correct),
confirmed no other Claude session was concurrently active, and finished
the one piece the recovered code's own comments already forecast but
hadn't been built yet - see below.

Audited every write path besides `upload.php` (which has had a
free-space guard since Phase 2) and found `chat.php`, `messages.php`,
and Stage 22's `bulletin.php` had none - a silently-dropped post under
genuine storage exhaustion, with the poster never told it wasn't saved.
New shared `includes/storage_guard.php` (`piratebox_low_storage()`)
mirrors `upload.php`'s `disk_free_space()` pattern, sized by a new,
deliberately independent constant `PIRATEBOX_MIN_FREE_BYTES_SMALL_WRITE`
(5MiB, vs. uploads' 1GiB) - a single post is at most a few KB, so
reusing the upload threshold would refuse guestbook posts while
gigabytes of reserved upload headroom sit untouched. Fails open (never
"low" if `disk_free_space()` itself can't be read).

`messages.php`/`bulletin.php`: guard checked before the write; on
failure, an honest on-page error is shown and the poster's
name/message/category are preserved in the form.

`chat.php`: same guard, but its form submits via JS `fetch()` and,
until now, never looked at the response at all - it optimistically
rendered the sent message in the sender's own browser regardless of
whether the server actually saved it. Fixed together: `chat.php` now
returns 507 Insufficient Storage on a guard failure, `scripts.js`
checks `response.ok` before the optimistic render (showing an inline
error and preserving the typed message instead), and the non-JS
fallback gets the same `$postError` treatment as the other two stores.

**Real pre-existing drift found (not introduced by this stage):** the
deployed `/usr/local/bin/piratebox_deploy.sh` (root-owned, updated only
by the operator re-running `setup_claude_automation.sh`) is missing
three `--exclude` lines the repo copy already has -
`data/mode-transitions.log` (Stage 21) and `data/bulletin.json` +
`.lock` (Stage 22) - confirming `setup_claude_automation.sh` hasn't
been re-run since before Stage 21, exactly as flagged at the time.
**No live impact today**, verified directly: the deploy source
(`var/www/html/data/`) never contains these gitignored runtime files,
so `rsync -a` (no `--delete`) has nothing to wrongly sync over them
regardless of the stale exclude list - confirmed live `chat.json`/
`messages.json` md5sums were unchanged after this stage's deploy, and
live `bulletin.json` doesn't currently exist at all. Still outside this
session's sudo automation boundary to fix (`setup_claude_automation.sh`
needs an interactive password, not one of the 5 granted commands) -
flagged again here rather than silently left to drift further.

**Testing:** `php -l` clean on all 5 touched/new PHP files; manual
brace/paren/bracket balance check on `scripts.js` (balanced: 102/102
braces, 348/348 parens, 17/17 brackets). Isolated PHP-built-in-server
tests on throwaway copies: forcing the threshold to `PHP_INT_MAX`
correctly rejected all three endpoints' posts (chat.php: 507;
messages/bulletin: honest on-page error), wrote no data file, and
preserved the submitted text in the re-rendered form; restoring the
real 5MiB threshold confirmed normal posting is unaffected. Live-
deployed via the approved sudo automation; live-verified in both Normal
and Emergency Mode; confirmed `chat.json`/`messages.json` untouched
(md5sum match against the pre-deploy backup); mode restored to Normal;
`nginx`/`php8.4-fpm` logs clean across the testing window.

**Backup:** `~/piratebox-backups/resilience-stage24-pre-20260901-104616/`.

## Stage 23: Voluntary Check-in Board - evaluated, deferred

**Decision date:** 2026-09-01. Layered on Stage 22 (`0b046eb`).

Evaluated and **deferred, not implemented** - full evaluation in
`docs/CHECKIN-BOARD-DESIGN.md`. In short: a structured "who has checked
in as safe" directory is a fundamentally different (and higher-stakes)
artifact than Bulletin Board's free-text posts, because PirateBox's
zero-account model means anyone can post any status under any name with
no way to verify it - impersonation and presence/absence disclosure
aren't edge cases for this specific feature, they're the central risk,
and neither is solved by making the feature simpler to build. The
governing instruction's "more capability must not make PirateBox
substantially more fragile" principle applies directly: a spoofable
safety directory is a worse kind of fragile than a missing stat. Stage
22's Bulletin Board already covers the legitimate underlying need
(voluntary self-reported status, in the poster's own words, with no
false authority attached). No code, page, or data file was added for
this stage.

## Stage 22: Community Bulletin Board

**Decision date:** 2026-09-01. Layered on Stage 21 (`7579ff9`/`fb17267`).

New `/bulletin.php`, modeled directly on `messages.php`'s Guestbook -
same JSON flat-file store, `flock()`-based atomic write, CSRF token,
server-side length caps, stale-tmp cleanup, and "newest first, capped
list" retention (200 posts here vs. the Guestbook's 100, since this is
meant to carry more operationally useful traffic during an actual
emergency: road closures, meeting points, "need water at X"). One added
field vs. the Guestbook: a `category` (Announcement / Info-Update /
Need Help / Offering Help), a client-supplied string validated against a
fixed server-side allowlist (invalid/tampered values silently fall back
to `info` - verified during testing with a deliberately malicious
`category` value). Not moderated beyond the existing admin "clear"
action (new `clear_bulletin`, mirroring `clear_chat`/`clear_messages`
exactly) - no accounts, no per-post delete, nothing new to keep secure.

Navbar: new `Bulletin` entry with the same unread-count badge pattern as
Chat/Guestbook (`includes/navbar.php`, `scripts.js`'s `updateBadges()`).
Placed early in Emergency Mode's nav order (right after Utility, before
Chat) given its coordination value during an actual emergency; kept in
its natural position after Guestbook in Normal Mode order.

**Proactive Stage-17-lesson application:** `data/bulletin.json` and its
`.lock` file were added to both `piratebox_deploy.sh`'s `--exclude` list
and `.gitignore` in the same change that introduced the feature, before
any deploy could touch them.

**Not added to the Stage 21 Stats page's counts** - that page is
explicitly scoped to device health + static content catalog, not live
community-post volume; left alone rather than expanding an
already-committed stage's scope.

**Process note:** unlike every prior stage, no dedicated pre-stage
`var/www/html` backup was taken before deploying this one - caught only
afterward. Risk was low in practice (`piratebox_deploy.sh` is
add/update-only, never deletes, and no `bulletin.json` existed yet to
lose), and git history itself still serves as the pre-stage baseline for
every repo file, but a live-tree snapshot should still have been taken
first as usual. A backup was taken immediately after
(`bulletin-stage22-post-20260901-101015`) and the miss is recorded here
rather than glossed over.

**Testing:** `php -l` clean (`bulletin.php`, `admin/index.php`,
`help.php`, `navbar.php`); manual JS brace/paren/bracket balance check
on `scripts.js` (no JS engine available in this environment); isolated
PHP-built-in-server flow test on a throwaway copy covered: empty-board
state, CSRF rejection (missing token -> 403), a legitimate post
(category pill and message rendered correctly, `?fetch=1` JSON
correct), and a deliberately malicious post (`<script>` in both the
message and the category field) - message body came back
`htmlspecialchars()`-escaped with no raw `<script>` tag in the response,
and the invalid category fell back to `info` exactly as designed;
live-deployed via the approved sudo automation; live-verified in both
Normal and Emergency Mode (page loads, nav link/badge present, nav
ordering correct per mode); confirmed `recovery-messages.json` and other
excluded live data untouched by the deploy; mode restored to Normal;
logs clean.

## Stage 21: Stats / Metrics / Appliance Status

**Decision date:** 2026-09-01. Layered on Stage 20 (`b241a4e`).

New public `/utility/status/` page (no login, unlike `/admin/`) shows
aggregate device health (uptime, storage/RAM free, CPU temp, current
mode, cumulative Emergency Mode runtime) and content-catalog counts
(reusing Stage 19/20's export `manifest.json` - not a third independent
count). Wi-Fi client count and per-service health reuse the existing
Phase 4 root status helper (`/run/piratebox/status.json`) with the same
staleness fallback `admin/index.php` already established. Page states its
privacy scope explicitly: aggregate-only, no visitor identity/IP/MAC,
no per-visitor or per-download logs.

**New shared module `includes/metrics.php`** extracts the `/proc` reads
and helper-snapshot logic into one place so the Stats page and any future
consumer (an OLED status line - see Stage 29) share one implementation.
**Deliberately not adopted by `admin/index.php` itself** - refactoring an
already-approved, destructive-action-containing page carried more
regression risk than the resulting de-duplication was worth; the
duplication is accepted and flagged as a Stage 27 (maintenance pipeline)
consolidation candidate.

**New feature: cumulative Emergency Mode runtime.** `set_piratebox_mode.sh`
now appends one line (`<unix timestamp> <mode>`) to
`data/mode-transitions.log` on every real transition - best-effort
(never fails the actual mode change if the log write fails), world-readable,
lives on the SD card (unlike mode state itself) since a running total
should survive a reboot. `includes/metrics.php` sums closed + any
still-open Emergency interval. **Lesson from Stage 17 applied proactively
this time**: the new data file was added to both `piratebox_deploy.sh`'s
`--exclude` list and `.gitignore` in the same change that introduced it,
before any deploy could touch it.

**Deferred, not implemented:** lifetime counters (downloads served,
aggregate bytes/devices served). Getting the aggregate-only,
zero-fingerprinting privacy boundary right deserves its own careful pass
rather than a rushed addition - left for a future stage.

**Real pre-existing bug found (not introduced by this stage):**
`/run/piratebox/status.json` was missing on the live device.
`piratebox-status.service` was failing every run with `226/NAMESPACE`
("Failed to set up mount namespacing: /run/piratebox: No such file or
directory"). Root cause: the unit used `ReadWritePaths=/run/piratebox`,
which grants access to a path but does not create it; `/run` is tmpfs and
is wiped every boot, and unlike `/var/www/piratebox-tmp` (which has a
`tmpfiles.d` rule - `etc/tmpfiles.d/piratebox-tmp.conf`), nothing ever
created `/run/piratebox`, so `ProtectSystem=strict`'s namespace setup
failed before the helper script's own `mkdir -p` could run. This has been
silently degrading `admin/index.php`'s Wi-Fi/service-health stats (and
would have done the same to this stage's new Stats page) to "not
reporting" since whenever this failure mode started.

**Fixed in the repo** (`etc/systemd/system/piratebox-status.service`):
replaced `ReadWritePaths=/run/piratebox` with `RuntimeDirectory=piratebox`
+ `RuntimeDirectoryPreserve=yes` - systemd's purpose-built mechanism for
exactly this (creates the directory before each start, owned by the
unit's user; `Preserve=yes` keeps `status.json` across this oneshot
unit's repeated 30s runs rather than tearing the directory down after
each one). **NOT deployed** - copying a unit into `/etc/systemd/system/`
plus `systemctl daemon-reload` is system configuration outside both the
5-command sudoers boundary and `setup_claude_automation.sh`'s scope
(which only installs the two deploy/mode-switch scripts + sudoers file).
Both this page and `admin/index.php` handle the missing snapshot
gracefully in the meantime (explicit "not reporting" state, never a
guess) - nothing is broken by leaving this unapplied, just less
informative.

**Two pending manual steps, outside this session's automation, for the
user's awareness:**
1. Re-run `sudo ./setup_claude_automation.sh` to pick up this stage's
   `set_piratebox_mode.sh` change (transition logging) at
   `/usr/local/bin/set_piratebox_mode.sh`. Until then, mode switches keep
   working exactly as before, they just don't log to
   `data/mode-transitions.log` yet, so the Stats page's Emergency-runtime
   figure stays at zero.
2. To apply the `piratebox-status.service` fix above:
   `sudo cp etc/systemd/system/piratebox-status.service /etc/systemd/system/piratebox-status.service && sudo systemctl daemon-reload && sudo systemctl restart piratebox-status.service`.

**Not added to the `/utility/` landing grid** (same 8-card judgment as
Stage 20) - cross-linked from the grid page's "Also on this PirateBox"
row and from Manifest/Download's own link rows instead.

**Testing:** `php -l` clean on all touched files; `bash -n` clean on both
shell scripts; isolated PHP-built-in-server test (learned from Stage 20)
confirmed the HTML page and all three download formats
(TXT/JSON/CSV, correct headers) on a throwaway copy, including the
graceful "status helper not reporting" fallback with no
`/run/piratebox/status.json` present; live-deployed via
`sudo -n piratebox_deploy.sh`; live-verified via `curl` in both Normal
and Emergency Mode (page content, mode cell, and Emergency banner all
correct); confirmed `data/recovery-messages.json` and other excluded
live data untouched by the deploy; mode restored to Normal afterward;
logs clean.

## Stage 20: PirateBox Manifest ("What's On This PirateBox?")

**Decision date:** 2026-09-01. Layered on Stage 19 (`87c4307`).

New `/utility/manifest/` combines two read-only sources rather than
recomputing anything: Stage 19's `manifest.json` (content counts, bundle
size - reused, not duplicated) plus a live count of `public/uploads/`
using the exact same `scandir()` logic `index.php`'s file listing already
uses (nothing newly exposed - that listing is already public). Offers
TXT/JSON/CSV downloads, generated on the fly (cheap - a handful of
numbers, not the "giant archive" the instruction warns against
rebuilding per-request - that concern applies to the ZIP bundles, built
once by Stage 19's script, not this small text formatting).

**Real bug found and fixed during testing:** the initial version pointed
at `../../exports/manifest.json` - one directory level too many
(`manifest/` and `exports/` are sibling directories, both direct children
of `utility/`, so it needed `../exports/`). Caught immediately because
testing showed every count rendering as `0` - traced, fixed, and
**re-verified with a corrected test method**: the first test pass used
`php index.php` under plain CLI, which doesn't populate `$_GET` from
`QUERY_STRING` (a CGI/SAPI-specific behavior) - it couldn't have caught
the three download-format code paths at all, only the fact that counts
were zero. Correctly re-tested via PHP's built-in web server instead
(same technique already used for Stage 16), confirming all three formats
work with correct headers (`Content-Disposition: attachment`,
appropriate `Content-Type`) and correct data.

**Not added to the `/utility/` landing grid** (already at 8 cards) -
cross-linked instead from the closely-related Download page, consistent
with the same "don't crowd the primary grid" judgment Stage 9 already
established for Local Information.

**Testing:** `php -l` clean; deploy previewed with an itemized dry-run;
live-verified the HTML page and all three download formats against
production (real upload count: 2 files, 143 bytes, matching actual
accumulated test uploads from earlier stages); full regression sweep
unaffected; logs clean; mode confirmed still Normal (not mode-
conditional, matching every other Utility section).

**Backup:** `~/piratebox-backups/manifest-stage20-pre-20260901-094955/`.

## Stage 19: "Take This With You" Download / Export System

**Decision date:** 2026-09-01. Layered on Stage 18 (`0190a70`). The
flagship feature of this expansion batch.

**PHP's `ZipArchive` extension is not installed** (confirmed directly:
`php -m | grep zip` empty, `class_exists('ZipArchive')` false) - installing
it would cross the explicit package-install stop condition. Resolved by
building ZIPs with **Python's standard-library `zipfile` module** (no new
package - `python3` is already present) inside a new **explicit, offline
build script** (`tools/build_export_bundles.py`), which is also exactly
the architecture the instruction itself prefers: source data → explicit
build process → cached/static bundles, never built per-request.

**Static offline copy - the core deliverable:** the build script reads
the *same* JSON files every live section page reads (single source of
truth) and generates genuinely standalone static HTML - relative links
throughout, `assets/styles.css`/`scripts.js` bundled verbatim (byte-
identical to live, confirmed), same `radio-entry`/`data-search`/
`data-group` markup as the live pages so the existing search/filter JS
works completely unmodified on the offline copy too. **Tested away from
the live environment**, per instruction: extracted the built ZIP into an
isolated temp directory and verified independently - correct file
structure, zero absolute `/utility/`or `/assets/` references anywhere,
zero leftover `<?php`/`<?=` tags, `<details>`/`</details>` balanced (37/37
on the Radio page), entry counts matching the live site exactly per
section, and the empty Library catalog degrading to a clean message
rather than an error.

**Three tiers, as specified:** individual raw JSON per section (the
lightest option - literally the same data files, copied verbatim);
4 logical bundles (Radio; Emergency+First Aid together, since they're
closely related life-safety reference; Maps+Local Information together;
Library - "Manuals/Documents"); one Complete Offline Utility Library ZIP.
Plus a CSV export for Radio's services table specifically - genuinely
tabular data, not a format added just to claim support (no CSV was added
for anything else).

**Export privacy, guaranteed by scope, not just checked after the fact:**
the build script only ever reads from `data/utility/*` and writes to
`public/utility/exports/` - there is no file-access path in it that could
reach chat/guestbook/recovery messages/admin credentials/uploads/system
config, by construction, not by an added filter. Documented explicitly at
the top of the script itself, not only here.

**Export performance:** pre-built once via the explicit script, never
per-request - confirmed by design (the download page only reads
`manifest.json` and serves plain static file links; nothing is generated
when a visitor loads the page). Total footprint is tiny: complete bundle
52KB, individual bundles 11-26KB, whole `exports/` directory 580KB on
disk - trivial for a Pi. Real, computed sizes (not estimates) are read
from the manifest and shown on the download page.

**Generated output deliberately NOT committed to git** - same convention
this project already uses for QR codes and the deployed `VERSION` file
(Phase 5): 100% regenerable from tracked source data via
`tools/build_export_bundles.py`, so committing the actual ZIPs/HTML would
mean hand-keeping two copies in sync. Added `public/utility/exports/` to
`.gitignore`; `piratebox_deploy.sh` still syncs it to live correctly since
`rsync` operates on the filesystem, independent of git tracking - verified
directly (deployed file's md5sum matched the locally-built one exactly).

**Also fixed while here:** `data/recovery-messages.json` (Stage 16) had
never been added to `.gitignore` despite being the same category of live
runtime data as `chat.json`/`messages.json`, which *are* ignored -
inconsistent, now corrected (`git rm --cached`, added to `.gitignore`,
local file left untouched on disk).

**Cross-linked from every section** (Radio/Emergency/First Aid/Maps/Local
Info/Library/Search hero-actions, plus a new card on the `/utility/`
landing grid) - found via the same audit habit Stage 17 established,
applied proactively this time rather than after the fact.

**Testing:** Python script syntax-checked (`ast.parse`) and run
successfully; `php -l` clean on all 9 touched/new PHP files; isolated
extraction test (above); deploy previewed with an itemized dry-run; live
regression sweep unaffected; live-downloaded ZIP's md5sum verified
identical to the locally-built one; live CSV download confirmed
well-formed; mode confirmed still Normal (download page is not
mode-conditional, matching every other Utility section); logs clean;
services untouched.

**Backup:** `~/piratebox-backups/export-stage19-pre-20260901-075834/`.

## Stage 18: Global Offline Search Expansion

**Decision date:** 2026-09-01. Layered on Stage 17 (`7924e01`).
Verification-only - no code changes, since the audit found Stage 8's
existing implementation (strengthened by Stage 17's cross-link fixes)
already satisfies this stage's requirements.

**Verified rather than assumed:** re-ran cross-section query checks
directly against the live index - `hypothermia` correctly spans Emergency
("Extreme Cold & Winter Weather") and First Aid ("Hypothermia &
Frostbite"), exactly the example in the instruction; `repeater` correctly
spans Radio bands and Local Information. `tools/build_search_index.py`'s
`load()` already returns `[]` for any missing dataset file rather than
erroring - confirmed by reading the code, consistent with Stage 10's
already-tested resilience discipline. The Search page's category chips
already cover all 6 sections (Radio/Emergency/First Aid/Maps/Local
Information/Library).

**Recovery/Found Device system deliberately stays OUT of global search** -
confirmed this is correct-by-design, not a gap: `build_search_index.py`
never reads `recovery-messages.json`, and `/found/` is a core PirateBox
page (like `help.php`/`chat.php`), not a `/utility/` JSON-driven section.
Indexing recovery messages would directly contradict Stage 16's own "no
enumeration" privacy requirement - the only correct search behavior here
is none at all.

**PDF full-text indexing remains deferred**, unchanged - no
`pdftotext`/`poppler-utils`, metadata/title/tag search only, per
instruction (moot in practice regardless, since the Library catalog has
no documents yet).

**No files changed, no deploy performed.**

## Stage 17: Complete Local Information / Content Audit

**Decision date:** 2026-09-01. Layered on Stage 16 (`8266484`/`84bb565`).
Commit note: the cross-link fixes below and the deploy-script data-loss
fix ended up in one commit (`a4478f1`) rather than two, because the
cross-link files were already `git add`-ed before the bug was discovered
mid-stage - both sets of changes are correct and tested, just not as
cleanly separated in history as usual.

**Audit method:** enumerated every dataset's entry count (confirms Maps
catalog and Library catalog are the only genuinely empty ones - by
design, not oversight); crawled every Utility section page's
`hero-actions` cross-links looking specifically for missing connections
between related sections.

**Missing cross-links found and fixed:** Radio didn't link to Emergency
(despite its own `emergency-monitoring-quick-reference` guide topic
conceptually pointing at it) or Local Information; First Aid and Library
didn't link to Local Information either. All four fixed - Local
Information is now reachable from every section whose content it
naturally complements (repeaters from Radio, hospitals/shelters from
Emergency/First Aid/Library), not just Emergency/Maps as before.

**Local Information - fields needing operator population** (not
fabricated, per instruction - deployment location isn't known to this
session): `region_label`, `last_updated`, `emergency_management`,
`nws_office`, `hospitals`, `shelters`, `amateur_repeaters`, `radio_notes`,
`map_references`, `other_resources` are all still blank. Only the two
universal `emergency_numbers` (911, Poison Control) are populated, as
established in Stage 6. **Schema enhanced** (not the content) so that
whenever these fields do get populated, each entry can optionally carry
`source`/`verified`/`confidence` - documented in a new
`data/utility/local/README.md` (mirroring Stage 7 Library's own README
pattern) and rendered on the page (`li_provenance()` helper) when present,
confirmed via direct unit test to render correctly when populated and
render nothing when absent.

**Curated content acquisition plan for Maps/Library (documentation only -
nothing downloaded)**, researched rather than guessed at:

| Candidate | Publisher/license | Approx. size | Assessment |
|---|---|---|---|
| Individual FEMA/Ready.gov hazard info sheets (thunderstorm, tornado, flood, earthquake, wildfire, extreme heat, winter storm, power outage, hurricane, etc.) | U.S. government work - public domain, FEMA explicitly permits reproduction | A few hundred KB each; the "full suite" PDF is a few MB | **Best near-term candidate** - small, clearly public domain, and would directly complement the Emergency Reference topics already citing these exact source pages. Still requires the operator's explicit go-ahead per instruction before any download. |
| FEMA "Are You Ready? An In-Depth Guide to Citizen Preparedness" (P-2064 / IS-22) | U.S. government work - public domain | **~183MB** (204 pages, per Internet Archive's listing) | Public domain, but the size alone crosses into "significant download" - would need its own explicit approval, not bundled into a smaller batch. |
| Red Cross first-aid/CPR reference guides | Redistribution terms **unclear** - offered through a "My Digital Books" access-controlled platform and a paid store in the material found this session | Not verified | **Do not acquire** without first getting clear confirmation of redistribution rights - unlike FEMA's government works, "free to view" was not confirmed to mean "free to redistribute" here. |
| ARRL band-plan/reference material | Member/copyrighted content, not public domain | N/A | **Excluded from any acquisition plan** - already correctly treated as citation-only (voluntary-convention source), never as bundled PDF content, throughout Stages 2-10. |
| Raspberry Pi/Linux/networking official documentation | Likely partially open-licensed (not verified this session) | Not researched | Flagged as a plausible future category - needs its own license/size research pass before any acquisition decision, not assumed. |

No files were downloaded. Per instruction, if/when the operator wants to
proceed with the FEMA hazard-info-sheet candidates (the only "ready to
acquire" row above), that's a small, explicit, separately-approved next
step - not something this audit triggers on its own.

**Testing:** `php -l` clean; deploy previewed with an itemized dry-run;
live regression sweep of every existing page unaffected (including the
deploy-script bug's own aftermath, fully resolved - see the separate
`a4478f1` entry above); `li_provenance()` unit-tested directly for both
populated and empty cases; mode confirmed still Normal throughout (no
mode-conditional content touched this stage).

**Backup:** `~/piratebox-backups/audit-stage17-pre-20260901-073340/`.

## Stage 16: Public PirateBox ID / Found Device / Recovery System

**Decision date:** 2026-09-01. Layered on Stage 14 (`afabb4e`). The
largest and most privacy-sensitive stage of the roadmap expansion so far -
tested more thoroughly than the pace-adapted norm for this batch (isolated
PHP-built-in-server flow tests before touching live data, plus one real
live production test).

**Device ID:** `tools/generate_device_id.sh` generates a random ID
(this device's: `PB-NSC5-3C`) from `/dev/urandom` - verified NOT derived
from MAC/serial/hostname/IP by construction (the script never reads any of
those). Idempotent-safe: refuses to overwrite an existing ID without
`--force`, specifically so cloning this SD card for a second physical unit
doesn't silently leave two devices sharing one ID. Stored in
`data/device-id.json`, read-only from PHP via `includes/device_id.php`
(same read-only-consumer pattern as every other small state file in this
project). Displayed on the Help/About page and the new Found Device page.

**`/found/`** (new): explains what PirateBox is, states plainly that
seeing the Wi-Fi signal alone is never a reason to locate the hardware,
and - for someone who has *physically* found the device - asks them not to
reset/dismantle/erase it and offers a recovery-message path. Safety/
property concerns are stated as taking priority throughout, not just once.

**Recovery messages: deliberately separate from Chat/Guestbook/uploads** -
own data file (`data/recovery-messages.json`), own lock, same atomic
temp-file-then-`rename()` write pattern every other store in this project
uses. No operator PII is ever displayed (nothing about the operator is
even stored). Finder contact is a free-text optional field, never
required. Explicit on-page statement that messages never leave the device
(true by construction - there's no Internet connection for them to leave
over).

**Rate-limiting, deliberately non-invasive:** submissions are throttled by
comparing against the store's *own last entry timestamp* under its
existing lock (30s cooldown) - no new per-client tracking file, no IP
logging. Lookups get a session-only cooldown (5s) - reuses the session
that already exists for CSRF, introduces no new tracking mechanism.

**Two-way thread implemented** (assessed as safely buildable within the
existing architecture, not deferred): each submission gets a random
6-character code (`ALPHABET` excludes 0/O/1/I/L for readability, ~30 bits
of entropy - judged adequate given this is a local-only, non-Internet-
exposed, rate-limited surface, not a public web service). No enumeration
endpoint exists anywhere - the only way to see a message is to already
have its code. Operator replies via a new, non-destructive `admin/`
action (`reply_recovery`) - deliberately **not** gated behind the
confirm-checkbox pattern used for destructive actions, since replying is
neither destructive nor irreversible (documented explicitly in-code so a
future reader doesn't "fix" this inconsistency without understanding it).
Purge (single or all) **is** confirm-gated, matching every other
destructive admin action.

**Testing performed:** isolated end-to-end flow tests using PHP's built-in
server against a throwaway temp copy (never live data) before touching
production - submit→code returned, immediate second submission correctly
cooldown-blocked, correct-code lookup shows the message, wrong code
correctly shows "not found," admin reply correctly persists and appears
on re-lookup, purge correctly requires confirmation and correctly clears
when confirmed. One bug found and diagnosed during testing: an early test
run appeared to show a reply not persisting - traced to a shell/grep
artifact in the test script itself (confirmed by re-running with raw JSON
inspection at each step, which showed the write path was correct all
along), not an application defect - documented here so the false alarm
doesn't get rediscovered and mistrusted later. `php -l` clean on all
files; deploy previewed with an itemized dry-run; live regression sweep
unaffected; one real live production submission test (clearly labeled,
purgeable via `/admin/`) confirmed the deployed code path end-to-end;
logs clean; services untouched; mode confirmed still Normal throughout
(neither new page reads `piratebox_get_mode()`, so no mode-switch cycle
was needed this stage).

**Design-only, not implemented, per instruction:**
- **Recovery/Lost Mode:** a third, *software-selectable* presentation
  state, explicitly separate from Normal/Emergency and **not** changing
  the physical toggle design at all. Concept: a prominent landing page
  stating the unit is marked missing/awaiting return, direct access to
  the Found Device messaging flow already built above, and just enough of
  the rest of the site left reachable to explain what the appliance is.
  Nothing about *how* this would be triggered has been decided (a future
  admin toggle is the obvious candidate, mirroring `set_piratebox_mode.sh`'s
  own pattern) - deliberately left open rather than guessed at now.
- **`PirateBox-Please-Return` SSID:** mentioned only as a future
  possibility for Recovery Mode. No SSID, hostapd, or networking change
  was made or is proposed as part of this stage - any actual SSID change
  remains squarely inside this session's explicit stop-condition and
  would need its own approval when it's actually time to build it.
- **Physical recovery label text** (documented here, no artwork
  generated): "PIRATEBOX - OFFLINE NETWORK APPLIANCE / This device
  provides a local Wi-Fi information and file-sharing service. / If
  operational, connect to the PirateBox Wi-Fi network and choose: About →
  Found This Device. / Device ID: `PB-NSC5-3C` / Please do not reset,
  dismantle, or erase the device merely because it was found." - no owner
  information anywhere on the label, matching instruction. A future QR
  code linking to the *local* `/found/` page (never an Internet URL,
  since one wouldn't resolve on this network anyway) is noted as a
  reasonable future addition once physical labels are actually produced -
  not built now.

**Backup:** `~/piratebox-backups/recovery-stage16-pre-20260901-072524/`.

## Stage 14: Main-Page Onboarding / "What Can I Do Here?"

**Decision date:** 2026-09-01. Layered on Stage 13 (`2081c4b`).

Normal Mode's hero gains one short paragraph (offline library exists,
link to the new capabilities page, Emergency Mode is physical-switch-only,
not-an-official-emergency-service) - kept short/non-intrusive per
instruction, doesn't touch the existing Files-first identity. Emergency
Mode's tagline became the literal "Emergency Mode is Active" (previously
"Local Offline Network"), with a subtle amber accent (reused color, not a
new alarm color) and the same not-an-official-service line, previously
missing from Emergency Mode entirely. New `public/whatcanidohere.php`:
mode-aware capabilities list covering every item in the instruction, not
added to the primary navbar (reachable via links) to avoid crowding it.

**Testing:** `php -l` clean; deployed via automation; live-verified both
modes; regression unaffected; mode restored to Normal.

**Backup:** `~/piratebox-backups/onboarding-stage14-pre-20260901-072201/`.

## Stage 13: PirateBox Identity / Transparency / About

**Decision date:** 2026-09-01. Expands `help.php` (no new page/data file)
with researched PirateBox history and appliance-transparency content.
Layered on Stage 12 (`dd09e5f`).

**History researched, not asserted from the prompt** - David Darts (NYU
Steinhardt, 2011, Free Art License), Dead Drops/pirate-radio/free-culture
inspiration, original OpenWrt-router implementation, popularity in France
(Jean Debaecker), later maintenance (Matthias Strubel), the LibraryBox
fork (Jason Griffey, 2012), and the project's Nov 17 2019 discontinuation
(cited reason: locked router firmware + HTTPS-only browsers) - sourced to
Wikipedia and LibraryBox's own About page, both cited on-page with
retrieval date. Explicit, prominent disclaimer that this installation is
an independent reimplementation, not an official continuation, no
affiliation with the original developers - satisfies the operator's
explicit non-affiliation instruction directly rather than leaving it
implied.

**"About This PirateBox"** describes the appliance at a deliberately safe
level (Raspberry Pi, local storage, independent AP, planned battery/
controls/display) - no serial numbers, MAC addresses, SSH/admin details,
exact location, or operator identity, matching the instruction's exposure
list exactly. Photo area reuses the existing `.utility-placeholder-note`
style (zero new CSS) and states a real photo will be added post-build -
no stock/fake/generated imagery per instruction.

**"If You Encounter This Network"** - one sentence is Emergency-Mode-only
(`help.php` now reads `piratebox_get_mode()` for the first time among core,
non-Utility pages), verified live present only in Emergency Mode: notes
that leaving an appropriately-placed unit running helps preserve access
for others during an actual emergency, exactly as instructed. Forward-
references `/found/`, built next in Stage 16.

**Also fixed in passing:** "Using PirateBox" never mentioned the Utility
Library at all - a real, pre-existing gap, corrected. Folded in a compact
Connection Status table (Stage 15's content) since it belongs on the same
page as everything else added this stage.

**Testing:** `php -l` clean; PHP-CLI render confirmed the mode-conditional
sentence correctly absent under the missing-file fallback; deployed via
automation; live-verified in both modes (conditional sentence present only
in Emergency); full regression sweep unaffected; mode restored to Normal.

**Backup:** `~/piratebox-backups/identity-stage13-pre-20260901-071759/`.

## Offline Utility Library - Stage 10: Accessibility / Resilience / Performance Audit

**Decision date:** 2026-09-01.

**Scope:** a dedicated review pass across the entire Utility Library
(Stages 1-9) - no code changes were needed as a result, since the audit
found no real defects. Purely read-only against the live site, plus one
safe, isolated resilience test against a throwaway temp copy that never
touched live data. Layered on Stage 9 (`9e14b53`); HEAD unchanged by this
entry except for this documentation.

**Findings, by checklist item:**

- **JSON validity:** all 15 data files across every section validated -
  clean.
- **Broken links:** crawled all 12 pages (main site + every Utility
  section), extracted every internal `href`/`src` (95 total, including
  every deep-link fragment introduced in Stage 8) - 15 unique destination
  pages, zero broken. Separately verified all 95 fragment-bearing links
  (`#entry-id`) actually resolve to a real element `id` on their target
  page, not just that the page loads - **zero mismatches**.
- **Source citations:** automated-checked all 52 unique source URLs across
  every dataset. 44 resolved `200` directly. 7 CDC URLs and 1 USGS URL
  returned `403`/failed to connect under automated request patterns -
  investigated rather than dismissed: confirmed `cdc.gov` itself is fully
  reachable (the block is anti-bot protection on specific content pages,
  the same pattern already well-documented for FCC/Ready.gov in Stages
  2-4, now confirmed to extend to CDC's domain too); the USGS failure was
  isolated to a **local Pi issue** - broken IPv6 routes to some of
  `usgs.gov`'s resolved addresses causing curl to exhaust IPv6 attempts
  before an SSL-related timeout, confirmed by forcing IPv4 (`curl -4`,
  still failed with an SSL cert error) and then confirming the actual page
  exists by skipping cert verification (`-k`, returned the same `403`
  anti-bot response as CDC) - not a dead or incorrect citation, and not
  something that affects the offline site at all (this only matters for
  the Pi's own outbound research capability during content-building
  sessions, never for an end user connected to the AP). No citation was
  changed; none needed to be.
- **Malformed-JSON / failure-scenario resilience** (the required
  "intentionally weak/failure scenario" test): explicitly corrupted
  (invalid syntax), deleted, and emptied three different section data
  files **on an isolated temp copy of the whole tree** (never the live
  site) and rendered each affected page via the PHP CLI directly. In every
  case: zero fatal errors, zero PHP warnings, the page chrome (title,
  nav, disclaimers) rendered correctly, and the *unaffected* content on
  the same page (e.g. Radio's modulation/guides sections when only
  `services.json` was corrupted) kept working normally - confirming the
  `is_array($decoded) ? $decoded : []` defensive pattern used by every
  section's data loader behaves exactly as designed under real corruption,
  not just in theory.
- **JS-off behavior:** every page in this project has been rendered and
  verified via the PHP CLI directly (which never executes JavaScript)
  before every single deploy since Stage 2 - this audit didn't need to
  re-invent that check, just confirms the pattern held throughout: all
  core reference content is server-rendered HTML, `<details>/<summary>`
  are native browser elements (keyboard-operable with no JS), and the only
  JS-dependent behavior anywhere is live search-as-you-type filtering and
  the Stage 8 deep-link auto-open convenience - both explicitly designed
  as enhancements over already-complete server-rendered content, never a
  requirement to see it.
- **Semantic HTML / heading hierarchy:** every page has exactly one
  `<h1>`, followed only by `<h2>` group headings with no skipped levels -
  checked across all 8 Utility pages plus the main site.
- **Keyboard navigation:** every interactive element across the whole
  Utility Library is a real semantic element (`<button>` for filter
  chips, native `<details>/<summary>` for expand/collapse, `<a>` for
  links, `<input>` for search) - no custom JS-dependent widgets anywhere,
  so keyboard operability is inherent, not something bolted on.
- **Contrast:** reconfirmed the Stage 9 review - new text colors (`#aaa`
  on `#181821`) clear WCAG AA comfortably.
- **Duplicated content:** reconfirmed Normal/Emergency Mode content
  identity holds (already proven live every stage since the Emergency
  Mode foundation phase); cross-section topics that sound related (e.g.
  Emergency's heat/cold guidance vs. First Aid's) are deliberately
  distinct in framing (preparedness vs. treatment) and were written
  separately from different source material, not copy-pasted duplicates.
- **Stale placeholder text:** none found - the only remaining "not yet"-
  style messages are the deliberate, correct empty-state messages for
  Local Information's still-blank fields and (unreachable in practice
  now, since it always exists) the Search page's missing-index fallback.
- **Unnecessary network requests / external dependencies:** re-confirmed
  zero `http(s)://` references anywhere in served PHP/JS/CSS other than
  the SVG XML namespace declaration (a required spec string, never a
  network fetch) and source-citation links a visitor would open
  deliberately.
- **Asset/data sizes and weak-Wi-Fi load behavior:** total
  `data/utility/` payload across all 6 sections is **212KB**; the two
  largest rendered pages (Radio, Search) are 108KB/77KB uncompressed but
  confirmed **actually compress to 17KB/13KB over the wire** (nginx gzip
  confirmed active via `Content-Encoding: gzip`, verified with real byte
  counts, not just the response header) - a 5.9-6.4x reduction, trivial
  even on a congested Pi 3B+ AP connection. `scripts.js` (~21.7KB) and
  `styles.css` (~21.3KB) are shared, cached-by-the-browser-after-first-
  load, single files - no bundle bloat, no per-page duplication.
- **Mobile/phone layouts:** re-confirmed the Stage 9 CSS-level findings
  hold across every section page, not just the one landing page Stage 9
  touched directly.

**No code changes resulted from this audit** - everything checked came
back clean or was a false alarm correctly diagnosed and explained above,
not silently ignored. This entry is the deliverable for this stage.

## Offline Utility Library - Stage 9: Utility Landing / Emergency Experience Polish

**Decision date:** 2026-09-01.

**Scope:** revisits Emergency Mode's root landing (`public/index.php`,
originally built in the Emergency Mode foundation phase before any real
Utility content existed) now that Stages 2-8 have given it real content to
prioritize. Normal Mode's landing and nav were deliberately left
untouched - confirmed unchanged. No networking/security-boundary/
Emergency-Mode-state-mechanism changes; no packages installed. Layered on
Stage 8 (`e1f19bd`).

**Card order changed** to match the operator's now-informed priority list:
Emergency Info, First Aid, Radio, Maps, Search, Library, Messages/Chat,
Files (previously: Emergency, Radio, Maps, First Aid, Messages/Chat,
Files, Search, Library - an order chosen back when Search and Library were
still empty placeholders). First Aid moved up next to Emergency Info;
Search and Library moved ahead of Chat/Files now that they're real,
useful, content-rich sections rather than stubs.

**Hero copy tightened** for the "random person finds the SSID during an
outage" scenario: tagline is now the literal phrase "Local Offline
Network"; the heading states plainly "This Network Does Not Require
Internet Access"; the body explicitly says "intentionally local" and
spells out that local file sharing/messaging still work normally, not
just that reference content exists. Same calm dark/purple visual language
as everywhere else on the site - no red/alarm styling, no security-tool
aesthetic, consistent with the operator's explicit "not a scary hacker
page" requirement.

**Local Information was deliberately NOT added to this 8-card grid** -
the operator's own priority list for this stage named exactly 8 items and
didn't include it; it stays reachable via the Emergency Info page's own
cross-link (added in Stage 6) and the full `/utility/` landing grid,
without crowding the primary Emergency Mode card list.

**Mobile-usability review performed at the CSS/design level** (no
physical device available this session, consistent with the same honest
disclosure Phase 5 already made about its own onboarding redesign):
confirmed `.utility-grid`'s `repeat(auto-fit, minmax(180px, 1fr))` reflows
to 2 columns at typical phone widths, confirmed the global button/input/
select/a `min-height: 2.25rem` touch-target rule (Phase 5) already covers
every new interactive element added since (`.radio-chip` is a real
`<button>`; `<details><summary>` already exceeds the 44px guideline from
its own padding), and confirmed new text colors (`#aaa` on `#181821`)
comfortably clear WCAG AA contrast. A real-device pass remains a good
idea before relying on this for an actual event, same caveat Phase 5
already carries forward.

**Testing performed:** `php -l` clean; confirmed Normal Mode's landing
renders byte-identical to before (no `utility-grid` present, `<h1>`
unchanged) - **zero regression to Normal Mode**; **deploy previewed with
an itemized dry-run** (confirmed only `public/index.php` would change)
before applying; live regression sweep of every existing page unaffected;
live-verified the new 8-card order and hero copy in Emergency Mode exactly
match spec; banner and `/admin/` gating confirmed still correct;
`nginx`/`php8.4-fpm`/`hostapd`/`dnsmasq` active throughout, no restarts;
error logs clean across the full testing window. Live mode restored to
explicit Normal before finishing - entire cycle via the automation.

**Backup:** `~/piratebox-backups/polish-stage9-pre-20260901-065258/` (full
`var/www/html` mirror + pre-change git HEAD `51b7e8f`).

## Offline Utility Library - Stage 8: Global Offline Search

**Decision date:** 2026-09-01.

**Scope:** builds out `/utility/search/` (a Stage 1 placeholder) into a
real global search across Radio, Emergency, First Aid, Maps, Local
Information, and the Document Library, plus a small deep-linking addition
to all 5 section pages. No networking/security-boundary/Emergency-Mode-
state changes; no packages installed. Layered on Stage 7 (`d615346`).

**`tools/build_search_index.py`** (new, re-runnable): reads the same JSON
data files each section page already reads and writes a single flat
`data/utility/search-index.json` (83 entries, ~34KB) - `{title, section,
url, snippet, keywords, freq?}` per item. This is the "rebuild the index"
command referenced in the project's original planning; re-run it any time
section content changes. No PDF text extraction, no `pdftotext`/
`poppler-utils` - metadata/title/tag search only, per instruction (moot
this stage anyway, since the Library catalog has no documents yet).

**Deep-linking, added to all 5 section pages:** every `<details
class="radio-entry">` across Radio/Emergency/First Aid/Maps/Library now
carries `id="<the item's own id from its JSON>"` (Maps catalog and Library
catalog entries fall back to a positional `map-N`/`doc-N` id if a future
entry omits one). A new guarded block in `scripts.js` checks
`window.location.hash` on load and, if it matches a `.radio-entry` id,
opens that `<details>` and scrolls to it - this is what makes "direct
local link" in a search result actually jump to the answer
(`/utility/radio/#noaa-weather-radio`) rather than just the section page.
Confirmed no duplicate ids on any page before deploying. This is the one
place this stage touched already-approved Stage 2-7 pages - a small,
mechanical, additive change (one attribute per entry), not a redesign.

**Search page design:** server-renders all 83 results as plain link cards
(title, section badge, frequency badge where relevant, snippet) - fully
browsable and useful with JavaScript off, same progressive-enhancement
principle as every other section. Reuses the exact same shared filter
component (`#radioSearch`/`#radioChips`/`data-group`/`data-search`) as
Radio/Emergency/First Aid/Maps/Library - chips here filter by *section*
instead of topic category. ~30 lines of new CSS for the result-card
layout (reusing `.radio-entry-name`/`.radio-entry-mode-badge`/
`.radio-entry-freq` for visual consistency); zero changes to the shared
filter JS itself - it already worked on this markup shape unmodified.

**Local Information indexing note:** since that dataset ships almost
empty (Stage 6), the index always includes one generic "Local Information"
pointer entry (keywords: local/hospital/shelter/repeater/emergency
contact) even though the underlying arrays are empty - so a search for
e.g. "hospital" still surfaces the right section rather than nothing,
confirmed live. The same pattern applies to the Document Library section.

**Testing performed:** search index validated (build-time + live, 83
entries both times); `php -l` clean on all 6 changed PHP files; rendered
the Search page via PHP CLI pre-deploy (83 result cards confirmed); no
duplicate entry ids confirmed on the Radio page before deploy; **deploy
previewed with an itemized dry-run** (filtered to real content changes)
before applying; live regression sweep of every existing page unaffected;
all 12 required test queries (NOAA, 40 meter, airband, generator,
bleeding, hypothermia, flood, water, GPS, GMRS, manual, hospital)
verified against the live index, each resolving to the correct
section(s); live deep-link verified end-to-end (entry id present on the
Radio page, search index href points at it, `scripts.js`'s handling code
confirmed deployed); live Normal vs. Emergency Mode content byte-diff on
both the Search page and (re-verified) the Radio page - **identical**;
`nginx`/`php8.4-fpm`/`hostapd`/`dnsmasq` active throughout, no restarts;
error logs clean across the full testing window. Live mode restored to
explicit Normal before finishing - entire cycle via the automation, no
manual round-trips.

**Backup:** `~/piratebox-backups/search-stage8-pre-20260901-064643/` (full
`var/www/html` mirror + pre-change git HEAD `b9edb15`).

## Offline Utility Library - Stage 7: Document Library

**Decision date:** 2026-09-01.

**Scope:** builds out `/utility/library/` (a Stage 1 placeholder). No
networking/security-boundary/Emergency-Mode-state changes; no packages
installed; **no documents downloaded or bundled** (per explicit
instruction). First stage built entirely using the new deployment/mode
automation - zero manual round-trips this stage. Layered on the automation
commit (`1149f4e`).

**Architecture decision - stayed under webroot, deliberately avoiding the
`open_basedir` change:** the operator's instructions explicitly said to
STOP before making an `open_basedir`/security-boundary change if the
previously-discussed outside-webroot `/var/www/library` design required
one. Rather than build that design and then stop, the framework was built
using the same under-webroot pattern Stage 5's Maps catalog already
established (`public/utility/library/files/`, matching the existing
`public/uploads/`) - which needs **zero** `open_basedir` change, so the
stop-condition never triggers. This is an explicit, documented tradeoff:
if real documents are later added that are sensitive, large, or raise
license/access-control concerns the outside-webroot design was meant to
address, that design should be revisited deliberately at that time, not
assumed to have been ruled out permanently.

**Data:** `data/utility/library/categories.json` (8 categories: Radio
Manuals; Raspberry Pi/Linux/Networking; Electronics References; Vehicle &
Generator/Power Equipment; Emergency & First-Aid Documents; Maps; Equipment
I Own; Other) and `catalog.json` - **intentionally empty array**, same
"don't fabricate content to look populated" principle as Stages 5-6. A
`README.md` alongside them documents the entry schema (title, category,
description, tags, file, file_type, file_size, source, date_version,
provenance_notes) for whoever adds a document later.

**`tools/check_library_catalog.py`** (new): a small, dependency-free
consistency checker - confirms every catalog entry's `file` exists in
`public/utility/library/files/`, and flags any file in that directory with
no matching catalog entry. Deliberately does NOT extract PDF metadata or
build a search index (that would need `pdftotext`/`poppler-utils`, which
the operator's instructions say not to install without stopping first -
this stays dependency-free and lets metadata/title/tag search work today
via the same client-side filter every other section uses). Tested against
both a clean catalog and a deliberately-introduced orphaned file to
confirm it actually catches problems, not just passes trivially.

**Testing performed:** both new JSON files validated (build-time + live);
`php -l` clean; rendered via PHP CLI pre-deploy (empty-state and
"Adding a Document" note both confirmed present, all 8 category chips
render); **deploy previewed with a read-only itemized `rsync --dry-run`
before applying** (confirmed only the new Library files + modified
`index.php` would change, nothing else, before running the real sync);
live regression sweep of every existing page unaffected; live empty-state/
instructions confirmed on the deployed page; live Normal vs. Emergency
Mode content byte-diff - **identical**; `nginx`/`php8.4-fpm`/`hostapd`/
`dnsmasq` active throughout, no restarts; error logs clean across the full
testing window. Live mode restored to explicit Normal before finishing -
entire cycle performed via the new automation with no manual round-trips.

**Backup:** `~/piratebox-backups/library-stage7-pre-20260901-064228/`
(full `var/www/html` mirror + pre-change git HEAD `1149f4e`).

## Claude deployment/mode-switch automation

**Decision date:** 2026-09-01.

**Scope:** infrastructure/tooling only - no site content, no networking,
no PHP security restrictions. Adds a narrow, auditable `sudo` NOPASSWD
grant so this session's automation can deploy repo changes and switch
Normal/Emergency Mode without a manual round-trip to the operator's
terminal for every stage, which had become the dominant bottleneck across
Stages 1-6.

**What was added:**
- `piratebox_deploy.sh` (new): replaces every stage's hand-written
  `rsync`/`cp` deploy block with one script. Syncs this repo's
  `var/www/html/` onto the live `/var/www/html/` - additive/update only
  (no `--delete`, ever), with an explicit `--exclude` for every piece of
  live user-generated content (uploads, chat/guestbook JSON + lock files,
  the deployed `VERSION` file, the admin password hash, generated QR
  codes) - belt-and-suspenders on top of the fact none of those are ever
  tracked in the repo/`.gitignore` in the first place, so a plain sync
  could not touch them regardless. Accepts no arguments beyond an optional
  `--dry-run` - nothing about its behavior is influenced by
  attacker/agent-controlled input.
- `etc/sudoers.d/piratebox-claude` (new): exactly 5 literal `NOPASSWD`
  command lines (no wildcards, no `ALL`) naming `piratebox_deploy.sh`
  (bare and `--dry-run`) and `set_piratebox_mode.sh` (`normal`/
  `emergency`/`status` - three separate exact lines, not a glob) at their
  `/usr/local/bin` paths.
- `setup_claude_automation.sh` (new): one-time, idempotent installer the
  operator runs with `sudo` - installs both scripts to `/usr/local/bin`
  (root:root, `0755`) and the sudoers rule (root:root, `0440`, validated
  with `visudo -cf` before installing, install aborts if validation
  fails).

**The critical safety property:** both granted scripts are installed
root-owned, **not writable by `moose`**. The `moose` account (which this
session runs as) can *trigger* them via the narrow sudo rule but cannot
*modify* what they do - this is what prevents a NOPASSWD grant from
becoming a privilege-escalation path (edit the script, then run the
now-malicious version via the trusted rule). This mirrors the exact
pattern this project already used for `purge_uploads.sh`/
`restart_hostapd.sh` (root-owned deployed copy in `/usr/local/bin`, plain
reference copy in the repo) - not a new convention introduced for this.

**Verification performed after the operator ran the installer:**
- Confirmed both scripts' deployed content matches the repo exactly, and
  confirmed their live ownership/permissions (`root:root`, `0755` for the
  scripts, `0440` for the sudoers file).
- `visudo -cf` on the installed sudoers file confirmed syntactically valid.
- Confirmed all 5 NOPASSWD commands work with `sudo -n` (which fails
  immediately rather than prompting if a password would actually be
  needed) - deploy dry-run, mode status, and (separately) real mode
  switches in both directions, and a real (non-dry-run) deploy.
- Confirmed the deploy script rejects any argument other than `--dry-run`
  (tested with `--delete`).
- **Caught and correctly diagnosed a false alarm during testing:**
  `sudo -n whoami` and `sudo -n cat /etc/shadow` initially succeeded
  without a password, which looked like a broader passwordless grant than
  intended. Root-caused to this system's pre-existing
  `Defaults timestamp_type=global` setting (visible in `sudo -l` output,
  not something this change touched) combined with the operator having
  authenticated with a real password moments earlier while running the
  installer - that leaves a short-lived cached credential shared across
  all sessions/ttys for the user, system-wide, not per-terminal. Proved
  this explicitly: `sudo -k` (clear the cached credential, needs no auth
  itself) immediately made `sudo -n whoami` fail again ("a password is
  required"), while all 5 approved commands continued to work correctly
  afterward - confirming they work via the sudoers rule itself, not
  residual cached credentials, and confirming nothing broader than the 5
  intended lines was ever actually granted. `sudo -l` further confirmed
  the pre-existing `(ALL : ALL) ALL` entry (standard Debian `sudo`-group
  membership, unrelated to and unmodified by this change) still requires
  a password in the general case - only the 5 named commands bypass it.
- Live regression sweep of every existing page, all 4 core services
  (`nginx`/`php8.4-fpm`/`hostapd`/`dnsmasq`), and error logs across the
  whole testing window - all clean, no restarts, no new errors. Mode
  confirmed restored to Normal at the end.

**What this changes going forward:** for Stage 7 onward, deployment and
Normal/Emergency test-mode switching are performed directly by this
session via the 5 approved commands - no further manual round-trips for
those two specific operations. Everything outside that exact boundary
(anything destructive, any networking/security/system-configuration
change, package installs, physical hardware) still stops for the
operator, unchanged from every prior stage.

## Offline Utility Library - Stage 6: Local Information

**Decision date:** 2026-09-01.

**Scope:** new `/utility/local/` page (no Stage 1 placeholder existed for
this - it was scoped as part of Stage 1's "Maps" placeholder originally,
now split out per the operator's staged plan). No networking/security-
boundary/Emergency-Mode-state changes; no packages installed. Layered on
Stage 5 (`99049d8`/`66aed5d`).

**One config file, not a searchable dataset:** `data/utility/local/info.json`
is a single object (region label, emergency management contact, NWS office,
hospitals, shelters, emergency numbers, amateur repeaters, radio notes, map
references, other resources) - not a list of many topics like Stages 2-5,
so this page intentionally does **not** reuse the `radio-entry`/search/chip
UI those pages share. Instead it's a plain, section-by-section reference
sheet (reusing `.help-section`/`table`/`.empty-state`, all pre-existing
classes - zero new CSS this stage). **Relocating this PirateBox to a new
area means editing this one JSON file - no PHP/HTML change required**,
exactly as instructed.

**Deliberately almost entirely empty, per explicit instruction:** every
array (`hospitals`, `shelters`, `amateur_repeaters`, `map_references`,
`other_resources`) and every named contact (`emergency_management`,
`nws_office`) ships blank - the page shows a plain "None/Not yet added for
this location" message rather than any fabricated placeholder content. The
**only** two pre-filled entries in `emergency_numbers` are 911 and the
National Poison Control number (1-800-222-1222) - both included because
they are universal, not region-specific, and the Poison Control number is
the same one already cited (from the same authoritative source) in Stage
4's First Aid data. Nothing else was invented to make the page look
populated.

**Integration with Emergency and Maps, as instructed:**
- Added to the main `/utility/` landing grid (7th card, between Maps and
  Library) - the only edit to that Stage 1 page this stage.
- Added a "Local Information" link to both `/utility/emergency/`'s and
  `/utility/maps/`'s existing `hero-actions` link rows.
- Corrected the Maps card's Stage 1 description text (it previously said
  "plus local emergency contacts," which became inaccurate once Local Info
  became its own section) to describe what Maps actually contains now.
- **Deliberately NOT added** to Emergency Mode's 8-card landing grid in
  root `index.php` (confirmed unchanged - still exactly 8 cards) - that
  grid's priority ordering is explicitly Stage 9's job to revisit
  holistically, not something to touch piecemeal each stage.

**Testing performed:** JSON validated (build-time + live); `php -l` clean
on all 4 touched files; rendered via PHP CLI pre-deploy (6 empty-state
sections, universal emergency-numbers table confirmed); live regression
sweep of every existing page unaffected; live checks confirmed the new
card, both cross-links, and the 911/Poison-Control table all render
correctly on the deployed site; live Normal vs. Emergency Mode content
byte-diff - **identical**; confirmed the Emergency-Mode root landing grid
is unchanged (still 8 cards); `nginx`/`php8.4-fpm`/`hostapd`/`dnsmasq`
active throughout, no restarts; error logs clean across the full testing
window. Live mode restored to explicit Normal before finishing.

**Backup:** `~/piratebox-backups/localinfo-stage6-pre-20260901-062636/`
(full `var/www/html` mirror + pre-change git HEAD `66aed5d`).

## Offline Utility Library - Stage 5: Maps / Location Framework

**Decision date:** 2026-09-01.

**Scope:** builds out `/utility/maps/` (a Stage 1 placeholder). No
networking/security-boundary/Emergency-Mode-state changes; no packages
installed; **no map data downloaded** (per explicit instruction). Layered
on Stage 4 (`58cd348`/`1411569`).

**Two independent halves on one page:**
1. **Reference section** (real content, works today): 5 topics on
   coordinates/GPS/navigation - Latitude & Longitude Basics, Coordinate
   Formats (DD/DMS/UTM/MGRS), How GPS Works Without Internet, Cardinal
   Directions & Compass Bearings, and Basic Offline Navigation Concepts.
   Sourced from USGS (coordinate formats) and NOAA/NCEI (magnetic
   declination); GPS mechanics cross-checked against general technical
   references (marked `confidence: medium` - no single authoritative page
   fetch succeeded this session for that specific topic, see Testing).
2. **Map catalog framework** (deliberately empty): a data-driven catalog
   (`data/utility/maps/catalog.json`) ready to list local/regional/
   evacuation/topographic/trail maps, each entry pointing at a static
   image/PDF file under `public/utility/maps/files/`. **Shipped as an
   empty array, on purpose** - no placeholder/fabricated map entries,
   consistent with the same "don't invent content to make a page look
   populated" principle that will also govern Stage 6's local-info dataset.
   The page's own empty-state message and an in-page "Adding a Map" note
   explain exactly how to add a real one later: drop the file in
   `public/utility/maps/files/`, add one JSON entry - no PHP editing
   required, mirroring the "clean metadata structure" the operator asked
   for.

**Why static files under webroot, not an outside-webroot design like
Library will use:** map images/PDFs aren't sensitive or copyright-risky
the way Stage 7's document library payload might be - they're reference
images. Keeping them in `public/utility/maps/files/` (same pattern as the
existing `public/uploads/`) needed zero `open_basedir` change and is
simpler; Stage 7 will make its own outside-webroot call deliberately, with
its own stop-and-explain if that needs an `open_basedir` change (per
instruction).

**Future offline slippy-map viewer - documented, not built:** the page
itself carries a short note (styled like Stage 1's other placeholder
notes) explaining the tradeoff: a real pan/zoom map viewer would need a
self-hosted JS mapping library (e.g. Leaflet - no CDN) plus locally-stored
map tiles (tens of MB to multiple GB depending on area/zoom coverage) -
explicitly flagged as a future, deliberate decision once real map data is
chosen, not something to default into. Static images/PDFs via the catalog
above work today with zero extra dependency.

**Testing performed:** all 3 JSON files validated (build-time + live);
`php -l` clean; rendered via PHP CLI pre-deploy (5 reference entries,
empty-state and future-viewer notes both confirmed present); live
regression sweep of every existing page unaffected; representative search
queries (`gps`, `utm`, `compass`, `coordinate`, `dead reckoning`) all
resolve correctly against live data; live empty-state and future-viewer
note confirmed rendering on the deployed page; live Normal vs. Emergency
Mode content byte-diff - **identical**; `nginx`/`php8.4-fpm`/`hostapd`/
`dnsmasq` active throughout, no restarts; error logs clean across the full
testing window. Live mode restored to explicit Normal before finishing.

**Backup:** `~/piratebox-backups/maps-stage5-pre-20260901-061942/` (full
`var/www/html` mirror + pre-change git HEAD `1411569`).

## Offline Utility Library - Stage 4: First Aid Reference

**Decision date:** 2026-09-01.

**Scope:** builds out `/utility/firstaid/` (a Stage 1 placeholder). HIGH-
STAKES CONTENT - see "Conservative-content decisions" below. No networking/
security-boundary/Emergency-Mode-state changes; no packages installed.
Layered on Stage 3 (`8cdfb28`/`9fc41c5`).

**Data:** 16 topics + 21 sources (~24KB) in `data/utility/firstaid/`,
sourced almost entirely from the **American Red Cross**'s own published
first-aid learning pages, plus CDC (concussion signs) and Ready.gov (heat/
cold - shared sourcing with Stage 3, first-aid-framed here). Same UI/data
pattern as Stages 2-3 (reused `radio-*` CSS/JS, `source_id`/`confidence`/
`source_note` provenance).

**Conservative-content decisions (per explicit instruction - this is high-
stakes material):**
- Every topic is **overview-level**: recognize the signs, take the
  immediate safe action, know when to call 911 - never a substitute for
  training or a diagnosis engine. No topic tells a reader to determine what
  condition someone has; every topic tells them what to watch for and when
  to escalate to a professional.
- **CPR/AED** got the most deliberate restraint: it states the well-known
  public-facing summary ("push hard and fast, about 100-120/min," "use an
  AED, it will guide you") because that phrasing is itself the standard
  Red-Cross/AHA public-education message, not an invented detail - but it
  deliberately does NOT attempt full compression-depth/hand-placement/
  breath-timing choreography, and carries its own explicit
  `training_note` field (rendered prominently on the page) stating that
  hands-on certified training is strongly recommended and this is a
  summary of what CPR involves, not a substitute for practicing it.
- A page-level disclaimer (styled with the existing `.help-note` component,
  not new alarm chrome) states plainly, before any topic content: this is
  not a substitute for professional care or training, call 911 for
  anything life-threatening, and any skill genuinely requiring practice is
  flagged explicitly.
- Nothing was invented: every quick-action bullet traces to specific
  language found in the cited Red Cross/CDC source this session (see
  Testing below - `ready.gov`/Red Cross pages also blocked direct
  automated fetch (403) same as Stages 2-3, so content was gathered via
  targeted search against `redcross.org`/`cdc.gov` domains specifically,
  not general web results).
- Two entries marked `confidence: medium` rather than high: **Minor Wounds**
  (the specific Red Cross page was identified but not individually
  re-verified line-by-line this session - the underlying practice is
  extremely well-established/uncontroversial across every source) and the
  **First-Aid Kit** reference (Red Cross publishes several activity-
  specific checklists rather than one canonical list; this entry is a
  synthesis of their commonly-recommended core contents, flagged as such).
- Deliberately excluded, per instruction: dosing/medication guidance beyond
  "use your own prescribed epinephrine auto-injector," any procedure
  requiring visual diagnosis (e.g. distinguishing burn/fracture severity
  precisely), and anything that reads as replacing professional judgment
  rather than bridging the gap until it's available.

**Testing performed:** JSON validated (build-time + live); `php -l` clean;
rendered via PHP CLI pre-deploy (16 entries, 5 sections, disclaimer and the
one `training_note` both confirmed present); live regression sweep of
every existing page unaffected; representative search queries (`bleeding`,
`choking`, `burn`, `cpr`, `poison`, `allergic`, `hypothermia`, `seizure`,
`snake`) all resolve to the correct single entry live; live disclaimer/
training-note rendering confirmed on the deployed page; live Normal vs.
Emergency Mode content byte-diff - **identical**; `nginx`/`php8.4-fpm`/
`hostapd`/`dnsmasq` active throughout, no restarts; error logs clean
across the full testing window. Live mode restored to explicit Normal
before finishing.

**Backup:** `~/piratebox-backups/firstaid-stage4-pre-20260901-061123/`
(full `var/www/html` mirror + pre-change git HEAD `9fc41c5`).

## Offline Utility Library - Stage 3: Emergency / Outage Reference

**Decision date:** 2026-09-01.

**Scope:** builds out `/utility/emergency/` (a Stage 1 placeholder) into a
skimmable, card-based practical reference. No networking/security-boundary/
Emergency-Mode-state changes; no packages installed. Layered on Stage 2
Radio Reference (`1ead465`).

**Deliberate UI/CSS/JS reuse - not duplication:** this page reuses the
*exact same* CSS classes and JS element IDs Stage 2 introduced for Radio
(`#radioSearch`, `#radioChips`, `.radio-entry`, `.radio-chip`, `.radio-group`,
`data-group-section`, etc.), rather than inventing a second parallel
"searchable card list" component. Since each Utility page is its own
separate document (never loaded alongside another), reusing the same
element IDs across pages is safe and required **zero changes** to the
already-tested `scripts.js` filter logic - it works on this page unmodified.
One new small CSS rule was added (`.ref-quick-actions`, a bullet list style)
since Emergency topics needed a "quick actions" list that Radio's schema
didn't have. This "shared reference-list component, `radio-*`-named but
domain-generic" pattern is intended to be reused again for First Aid,
Maps, and Library in later stages - noting it here once rather than
repeating the rationale in every subsequent stage's entry.

**Data:** 21 topics across 5 groups (Severe Weather & Hazards; Power,
Utilities & Home Safety; Water, Food & Sanitation; Planning &
Communication; Pets) in `data/utility/emergency/topics.json`, plus
`sources.json` (23 sources - primarily Ready.gov/FEMA, CDC, NOAA/NWS, and
NFPA). ~27KB total. Each topic has a one-line `summary`, a short
`quick_actions` bullet list (the primary skimmable content), an optional
`more_info` paragraph, and the same `source_id`/`confidence`/`source_note`
provenance fields Stage 2 established.

**Calm-not-alarmist design, per explicit instruction:** no red/danger
styling, no severity icons, no "WARNING" chrome. Priority is conveyed
structurally instead - hazards needing an immediate physical action
(tornado, earthquake, downed lines, CO) are grouped together and lead with
a one-line action-oriented `summary`, but visually use the same calm
card style as every other topic. The intro paragraph explicitly tells
readers to follow official local instructions over this reference.

**Data-quality notes:**
- Most topics (19/21) are `confidence: high`, sourced directly from
  Ready.gov/FEMA, CDC, NOAA/NWS, or NFPA topic pages - `ready.gov` also
  blocked direct automated fetch (403) this session same as FCC did in
  Stage 2, so content was gathered via targeted web search against these
  same official domains rather than a raw page fetch; multiple independent
  official sources were cross-referenced per topic where practical.
- **Downed power lines** (`confidence: medium`): no single federal
  Ready.gov-equivalent page was identified this session; guidance was
  consistent word-for-word in substance across multiple independent state
  utility-commission/electric-utility consumer-safety sources, which is
  why it's marked medium rather than low.
- **Sanitation without running water** (`confidence: medium`): the general
  need and health rationale are CDC-sourced, but specific low-tech
  practices (e.g. the "twin bucket" toilet method) were cross-checked via
  secondary sources this session, not fetched directly from the CDC page
  cited - flagged in `source_note` accordingly.
- **Communications outages** and **battery/power conservation** are marked
  `source_id: general-prep-education` (no single regulatory/agency
  citation - practical synthesis, consistent with how Stage 2 handled
  general RF-education content). The communications-outage topic
  deliberately cross-references this PirateBox itself as a working offline
  fallback.
- **Known gap, deliberately deferred:** hurricanes/broad "severe storm"
  guidance beyond thunderstorms/lightning was not given its own topic this
  stage (searching "hurricane" currently returns no results) - not a
  defect, a scope/completeness tradeoff made to avoid rushing a distinct
  research pass late in an already-large stage, consistent with the
  operator's "accuracy over completeness" instruction. Good candidate for
  a future small addition using the same Ready.gov/NOAA sourcing pattern.

**Testing performed:** JSON validated (build-time and post-deploy from the
live path); `php -l` clean; rendered via PHP CLI directly pre-deploy (21
entries, 5 sections, 19 source links, zero warnings); live regression sweep
of every existing page unaffected; simulated the live search/filter logic
in Python against deployed data for representative queries (`generator`,
`flood`, `water`, `evacuat*` all resolve correctly; `bleeding`/`hurricane`
correctly return nothing - First Aid and the noted gap, respectively, not
bugs); live Normal vs. Emergency Mode content byte-diff - **identical**,
confirming zero content duplication; `nginx`/`php8.4-fpm`/`hostapd`/
`dnsmasq` all remained active throughout with no restarts; error logs
reviewed across the full testing window - zero new entries. Live mode
restored to explicit Normal before finishing.

**Backup:** `~/piratebox-backups/emergency-ref-stage3-pre-20260901-060133/`
(full `var/www/html` mirror + pre-change git HEAD `1987f5a`).

## Offline Utility Library - Stage 2: Radio Reference

**Decision date:** 2026-09-01.

**Scope:** builds out `/utility/radio/` (a Stage 1 placeholder) into a real,
locally-searchable reference for a wideband receiver (built with a Malahit
DSP2-style receiver specifically in mind). No networking, hostapd, dnsmasq,
captive-portal, nginx architecture, PHP security restrictions, or the
Emergency Mode state system were touched. Checkpoint: layered directly on
top of the Emergency Mode foundation commit `620c05abd08fc5c4edceddaa2d94a0a56d4ae1fd`.

**Data-driven, not hard-coded:** all frequency/service data lives in 4 JSON
files under `data/utility/radio/` (`services.json`, `modulation.json`,
`guides.json`, `sources.json`) - none of it is hard-coded into
`radio/index.php`, which is pure rendering/filtering logic over whatever
these files contain. Total size: ~49KB across all 4 files - loads instantly,
no pagination needed. 25 top-level service entries (14 individual amateur
bands, AM/FM/shortwave broadcast, NOAA Weather Radio, CB, FRS, GMRS, MURS,
Marine VHF, Airband, Railroad), several with nested `channels` arrays
(NOAA's 7, CB's 40, FRS's 22, MURS's 5, Marine's 12 key channels, shortwave's
14 meter bands) so the page shows one card per *service* rather than one row
per individual channel. Plus 6 modulation-type glossary entries (AM/FM/WFM/
USB/LSB/CW) and 6 practical guide entries (RF spectrum overview, HF/VHF/UHF
explained, HF propagation basics, antenna guidance, receiver practical tips,
and a cross-service "what to monitor during severe weather/an emergency"
quick reference).

**Every record carries source/confidence/provenance**, per the operator's
explicit requirement: `source_id` (pointing into `sources.json`, which
records publisher, URL, and retrieval date), `confidence` (`high`/`medium`/
`low`), and a free-text `source_note` used especially where a regulator and
a voluntary band-plan source are combined, where a secondary source was
used only as a cross-check, or where regional/local assignments vary. See
"Data-quality methodology" below for how confidence was assigned.

**Receive vs. transmit is a field on every record, not just page text:**
each service entry carries `license_required_to_transmit` (bool) and a
plain-language `transmit_note`, rendered as a distinct colored badge
("License required to transmit" / "No license required to transmit") right
in the summary line, plus the full note in the expanded detail. The page's
intro paragraph states plainly that owning a receiver does not authorize
transmitting anywhere on the page. No entry implies otherwise.

**Data-quality methodology (this session, 2026-09-01):**
- `weather.gov/nwr` and `navcen.uscg.gov` (NOAA Weather Radio, Marine VHF)
  were fetched directly and successfully - marked `confidence: high`.
- FCC's own pages (eCFR and consumer-guide URLs for Part 97 amateur bands,
  Part 95 FRS/GMRS/MURS/CB, and the AM/FM broadcast pages) returned
  **HTTP 403 to every automated fetch attempt this session**. Those figures
  were instead cross-checked against Wikipedia's own sourced tables (which
  themselves cite the same CFR parts) and, for CB/MURS/AM/FM specifically,
  against multiple independent secondary sources that agreed exactly -
  marked `confidence: medium` (amateur bands, shortwave meter bands, FRS,
  GMRS, airband) or `confidence: high` (CB, MURS, AM/FM broadcast, where
  independent sources were unanimous and the allocation is long-stable).
  **Wikipedia is never recorded as the source-of-record in the shipped
  data** - every entry's `source_id` points at the primary regulator
  (FCC/NOAA/USCG/ITU); the cross-check methodology is disclosed in
  `source_note` instead.
- The 60m amateur band is separately flagged `confidence: medium` for a
  different reason: its rules were cross-checked as having changed as
  recently as December 2025, so it's called out as more likely to be
  out of date than the other amateur bands.
- **Railroad radio is deliberately conservative**, per explicit operator
  approval: three independent sources gave three different lower band-edge
  figures (159.57 / 159.810 / 160.110 MHz) and no single authoritative
  public channel table was found. The `railroad` entry ships with only the
  approximate range, a description of how the AAR channel system works,
  and practical receive guidance - **no specific numbered channel table** -
  marked `confidence: low` with the discrepancy documented in
  `source_note`. A future update can tighten this if a clean primary source
  is found.
- After research, this session's Pi had live outbound internet (confirmed:
  `curl https://www.google.com` returned `200`), which was used only to
  verify every citation URL in `sources.json` actually resolves (all 8
  returned `200`) - not to change what ships. The finished page requires no
  internet at all to use.

**Page design:** server-rendered (every entry is real HTML from PHP, not
injected by JS - confirmed by rendering the page via `php` CLI directly),
using native `<details>/<summary>` for expand/collapse so full detail
(nested channel tables, transmit note, source citation) is reachable with
JavaScript entirely off - only the live text-search and category-chip
filtering are JS-only, added to `assets/scripts.js` as one more guarded
block following the file's existing pattern (same technique as the
pre-existing file-list search). A small hand-authored inline SVG
(`spectrum.svg.php`, log-scale, 0.5 MHz-3 GHz) gives a quick visual
band-position reference - static markup, no charting library. All new CSS
(~220 lines) reuses the existing dark/purple palette and component
language (card backgrounds, accent borders, uppercase badges) rather than
introducing a new visual style.

**Shared with Emergency Mode, not duplicated:** `radio/index.php`
deliberately never calls `piratebox_get_mode()` or touches `includes/
mode.php` - confirmed live by fetching the page in both modes and
byte-diffing the `.radio-page` content: **identical in both**, 37
`<details>` entries either way. Only the site-wide navbar/banner (rendered
by the unmodified `includes/navbar.php` from Stage 2's earlier phase)
differs between modes, exactly as designed.

**Testing performed:**
- All 4 JSON files validated (`json.load` in Python) after generation and
  again post-deploy from the live path.
- `php -l` on `radio/index.php` and `spectrum.svg.php` - clean.
- Rendered `radio/index.php` via the PHP CLI directly (not just through
  nginx) to catch template bugs early - this caught and fixed a real bug:
  the channel-table column list was being built from only the *first* row
  of each service's `channels` array, silently dropping CB channel 23's
  extra `note` field (documenting a real, intentional historical CB
  channel-numbering quirk) since no other CB channel has that field. Fixed
  to take the union of keys across all rows; verified the note now renders
  and that rows without it still get a correctly-aligned empty cell.
- Live, in both Normal and Emergency Mode: full site status sweep (all
  existing pages, `/admin/` still `401`, all `/utility/...` pages, captive-
  portal probes) - zero regressions. A live CSRF-authenticated **file
  upload** (first real end-to-end upload test since Stage 1) and a live
  **chat POST** (since `scripts.js` changed) both succeeded.
- Simulated the exact client-side search/filter logic in Python against the
  live deployed JSON for all 9 required queries (`NOAA`, `2 meter`, `40m`,
  `airband`, `GMRS`, `FRS`, `marine`, `CB`, `shortwave`) - every one
  resolved to the correct entry. Noted, not fixed: plain substring matching
  means `"2 meter"` also incidentally matches `"12 Meter Band"` (a substring
  of "1**2 meter**") - harmless (both are genuine radio bands, the correct
  entry is always present), consistent with the existing file-list search's
  same plain-substring approach, not worth added complexity for this stage.
- All 8 unique source citation URLs in `sources.json` verified live to
  return HTTP `200`.
- nginx/php-fpm error logs reviewed across the full testing window: zero
  new errors - all matches are pre-existing historical entries from earlier
  phases (confirmed by timestamp).
- `nginx`, `php8.4-fpm`, `hostapd`, `dnsmasq` remained `active` throughout
  with no restarts. Final live mode restored to explicit Normal before
  finishing.

**Backup:** `~/piratebox-backups/radio-reference-phase1-pre-20260901-053341/`
(full `var/www/html` mirror + recorded pre-change git HEAD `620c05a`),
created before any edit in this phase.

**Known residual test data:** one more live chat entry
(`[Automated Stage 2 Radio Reference regression - safe to delete via
/admin/]`) and one uploaded file (`stage2-upload-test.txt`) from this
phase's live regression testing - not cleared automatically (no admin
credentials available to this assistant); both clearable via `/admin/`.

**Deliberately deferred:** Emergency, First Aid, Maps, Library, and Global
Search sections remain Stage-1 placeholders - out of scope for this stage
per explicit instructions. `poppler-utils`/PDF text extraction was not
installed (not needed - this stage has no PDFs). GPIO, SSID switching, and
the OLED/button hardware remain untouched, as in the prior phase.

## Emergency Mode: software presentation-mode foundation (no GPIO yet)

**Decision date:** 2026-09-01.

**Scope:** additive, presentation-layer only. No networking, hostapd,
dnsmasq/DHCP/DNS, captive-portal, nginx architecture, PHP security
restrictions (`open_basedir`/`disable_functions`), or existing application
logic (`upload.php`, `chat.php`, `messages.php`, `admin/index.php`) changed.
No GPIO access, no OLED display, no momentary-button handling, no SSID
change, and hostapd was never touched or restarted this phase - all
explicitly deferred, per the operator's own instructions, to a later phase
once the ordered hardware (MTS-101 toggle switch, SSD1306 OLED, momentary
buttons) actually arrives. Checkpoint: this phase starts from and is layered
directly on top of the Stage 1 commit `e428b578bf1bd25c7faf1c10980a4bfc8c001e8c`,
kept as the known-good pre-Emergency-Mode reference point.

**Concept:** the site now has two presentation modes, Normal and Emergency,
selected by a single piece of trusted state. Radio/Emergency/Maps/First
Aid/Library/Search/Files/Chat/Guestbook content is **not duplicated** between
modes - every page under `/utility/...` and every existing PirateBox page is
byte-identical regardless of mode (confirmed live - none of them even
reference the mode system). Only three things change with mode: the
homepage's landing content, the navbar's link order, and (site-wide) whether
a small "Emergency Mode" banner is shown. Eventually mode will also
determine the Wi-Fi SSID (not implemented this phase - see below).

**Where mode state lives:** `/tmp/piratebox/mode` - a single-line plain-text
file containing exactly the word `normal` or `emergency`, nothing else (no
JSON). Chosen over the JSON `status.json` pattern used elsewhere in this
project because a single enum value doesn't need JSON's structure, and
plain text has exactly one way to be malformed instead of a whole parser's
worth - simpler and more robust, matching the operator's explicit
"simple and robust" requirement for this subsystem.

**Why `/tmp` and not `/run/piratebox/` (which is what an earlier planning
discussion for this feature proposed):** the operator's safety list for this
phase explicitly said not to change "PHP security restrictions." `/tmp` is
already fully inside `open_basedir` (it has been since before this project's
Phase 1), so reading a file there required **zero** `php.ini`/`open_basedir`
edit. `/run/piratebox/mode.json` would have needed a new `open_basedir`
entry, same as `status.json` got in Phase 4 - a reasonable change in
general, but not one this phase's explicit instructions permitted, so the
design was adjusted to avoid it rather than doing it anyway. Both paths are
tmpfs, so the reboot-reset behavior below is identical either way; this can
be revisited when the real GPIO daemon is built, if there's a reason to
prefer `/run`.

**Why tmpfs specifically:** a fresh boot always starts with **no state file
present**, which resolves to the safe Normal fallback - by construction, not
by a special case that has to be remembered and kept correct. This also
matches the operator's stated requirement that the physical switch (once
wired) should be read fresh at every boot rather than trusting a persisted
last-known value from the SD card.

**How PHP reads it:** one new function, `piratebox_get_mode()` in the new
`includes/mode.php` (not `helpers.php`, which is documented as pure
formatting helpers - mode detection is a distinct concern and was given its
own small file so it stays the one obvious place this logic lives). Reads
the state file, trims/lowercases it, and returns the literal string
`'emergency'` only on an exact match; **every other outcome - file missing,
empty, unreadable, garbage content - returns `'normal'`.** The function
cannot throw and never returns a third "unknown" value. Verified against all
of these cases both as a direct unit-level check (`php -r` against the
deployed file, all 7 cases: missing dir, empty file, garbage content,
explicit `normal`, explicit `emergency`, mixed-case/whitespace `emergency`,
and `chmod 000`-unreadable) and live, end-to-end, against the actual
deployed site (missing-file case - the site's default state before this
phase's testing began, invalid-content case). Every one correctly resolved
to the expected mode.

**www-data/PHP never writes this file, ever, and there is deliberately no
web-reachable way to change mode.** Mode changes only come from a trusted,
privileged, out-of-band actor: today that's an operator running
`set_piratebox_mode.sh` by hand with `sudo`; later it will be a root-owned
GPIO daemon. This preserves the same "web tier can only read, a separate
privileged helper does anything sensitive" boundary this project has used
since the Phase 4 admin/status page.

**`set_piratebox_mode.sh`** (repo root, not yet installed to
`/usr/local/bin` - can be run directly from the repo path with `sudo`):
manual stand-in for the not-yet-installed MTS-101 toggle switch. Takes
`normal`, `emergency`, or `status`; refuses to run as non-root for
`normal`/`emergency` (mode changes are a trusted operation, matching the "no
public unauthenticated way to change mode" requirement even for this manual
tool); writes atomically (temp file in the same tmpfs directory, then
`rename()`) so a concurrent PHP request never observes a half-written file.
Deliberately built to be the same write path a future GPIO daemon will use -
proving out this script now means the daemon inherits already-tested
behavior rather than needing its own from-scratch verification of the state
file mechanics.

**Landing page (`index.php`) in Emergency Mode:** per the operator's
explicit instruction ("do not merely add a banner to the normal Files-first
page... someone who has never heard of PirateBox should connect and
immediately understand what this network is"), the root URL genuinely
changes what renders first - an emergency-framed hero ("Local Emergency
Information Network... designed to run on battery power... Internet access
is not required or provided...") followed by an 8-card grid (Emergency
Info, Radio, Maps, First Aid, Messages/Chat, Files, Search, Library, in that
order) using the exact `.utility-grid`/`.utility-card` component Stage 1
already built for `/utility/`'s own landing page - zero new CSS needed for
this part. The existing Files/Upload/file-list block - **completely
unchanged code**, not a copy - still renders on the same page immediately
below, now anchored `id="files"` so the grid's "Files" card can jump
straight to it, with its own heading demoted from `<h1>` to `<h2>` in
Emergency Mode only (correct HTML semantics with two hero sections on one
page; same text either way). In Normal Mode `index.php`'s output is
byte-for-byte what Stage 1 already produced - confirmed live.

**Navbar (`includes/navbar.php`):** same six links/targets in both modes -
only the order changes. Normal: Files, Upload, Chat, Guestbook, Help,
Utility (unchanged from Stage 1). Emergency: Utility, Chat, Files,
Guestbook, Help, Upload. Implemented as a small ordered-key array picked by
mode and rendered via one `foreach`, rather than two hard-coded `<li>`
blocks, so adding a mode or changing an order later is a one-line change.
Labels/hrefs deliberately left unchanged between modes (considered
relabeling "Utility" to "Emergency" in the navbar, rejected: it would then
point somewhere different from the landing page's separate "Emergency Info"
card, which links to `/utility/emergency/` specifically - keeping one
label/target pair everywhere avoids that mismatch).

**Emergency Mode banner:** a small site-wide notice ("Emergency Mode - this
is a local offline network. No Internet access is required or provided.")
rendered by `navbar.php` itself (so every page that includes the navbar
gets it automatically, with zero per-page changes) whenever mode is
Emergency, and rendered nowhere at all in Normal Mode. Reuses the existing
`.help-note` component style (warm amber accent, matching the project's
"informative, not alarming" visual language - not the red/`.status-bad`
styling used for actual faults) plus one small new 2-rule CSS block
(`.mode-banner`) purely for width/centering - confirmed present on `/`,
`/chat.php`, `/messages.php`, `/utility/`, and `/help.php` in Emergency
Mode, and confirmed absent from all of them in Normal Mode. `admin/index.php`
was deliberately left out (it hand-rolls its own nav, is Basic-Auth-gated,
and is an operator/status page rather than part of the public presentation
- not worth the extra touched file for this phase).

**Testing performed (unit-level and live, both directions):**
- `php -l` on every new/changed PHP file - clean.
- Direct unit-level test of `piratebox_get_mode()` against the deployed
  file for all 7 state-file conditions listed above - all correct.
- **Normal Mode** (the site's actual state through most of this phase's
  testing, since no state file existed yet): confirmed Files-first landing,
  correct nav order, no emergency hero/grid/banner anywhere, `/admin/` still
  `401`, all `/utility/...` pages still `200`, all 7 captive-portal probe
  paths and the Capport JSON endpoint unchanged, upload form still renders,
  and a **live CSRF-authenticated guestbook POST** accepted and visible on
  refetch (proving the write path still works through the modified
  `navbar.php`).
- **Emergency Mode** (operator ran `sudo set_piratebox_mode.sh emergency`):
  confirmed the emergency hero copy, all 8 grid cards resolving to their
  correct existing URLs (verified individually, not just that the grid
  exists), the "Also on this network" secondary links (Guestbook/Help/full
  Utility Library), correct reordered nav, the banner present on every page
  checked, `/admin/` still `401`, every existing and `/utility/...` page
  still `200`, captive-portal probes unchanged, and a **live
  CSRF-authenticated chat POST** accepted and visible on refetch.
- **Content-sharing check:** confirmed none of the files under
  `public/utility/*/index.php` reference `mode.php`/`piratebox_get_mode()`
  at all - they render identically regardless of mode, reached by a
  different nav path only.
- **Live failure-mode checks**, run against the actual deployed site (not
  just simulated): operator wrote invalid content
  (`echo not-a-real-mode > /tmp/piratebox/mode`) - site correctly rendered
  full Normal presentation, `/admin/` still gated. The state file not
  existing at all was also exercised live for real, since that was the
  site's actual condition before the first `set_piratebox_mode.sh` call
  this phase.
- `nginx`/`php8.4-fpm` error logs reviewed across the entire testing window
  (spanning both mode switches and all live POSTs): zero new errors: the
  only matches are pre-existing historical entries from earlier phases
  (confirmed by timestamp, well before this phase's testing began).
- `nginx`, `php8.4-fpm`, `hostapd`, `dnsmasq` all remained `active`
  throughout, with no restarts - expected, since nothing in this phase
  touches any of those services. Final state was explicitly restored to
  Normal Mode (`sudo set_piratebox_mode.sh normal`) before finishing.

**Backup:** `~/piratebox-backups/emergency-mode-phase1-pre-20260901-052052/`
(full `var/www/html` mirror + recorded pre-change git HEAD `e428b57`),
created before any edit in this phase.

**Known residual test data:** this phase's live write-path tests left two
more clearly-labeled entries in `data/chat.json`/`data/messages.json`
(`[Automated Emergency Mode Stage regression - ... - safe to delete via
/admin/]`), in addition to the two left by Stage 1's testing. Same as
before: not cleared automatically (no admin credentials available to this
assistant); clear via `/admin/` if desired.

**Deliberately deferred to a later phase** (per the operator's explicit
instructions - none of this exists yet):
- Actual GPIO access / the MTS-101 toggle switch. `set_piratebox_mode.sh`
  is the interim stand-in and is intended to be directly replaceable by a
  future root-owned GPIO daemon that writes the same state file with the
  same atomic-write technique.
- SSID switching. hostapd/`hostapd.conf` were not touched or restarted this
  phase. No Emergency SSID has been chosen. When this is implemented, the
  design this phase establishes is meant to support it safely: the
  privileged mode-writer (today the script, later the GPIO daemon) is the
  one place that would decide "did the mode actually change," debounce the
  physical switch before acting, and - only on a genuine, stable transition
  - swap in the correct static `hostapd-{normal,emergency}.conf` and
    restart hostapd, never on every poll.
- The SSD1306 OLED display and the five momentary buttons. Neither is
  implemented; no GPIO pins have been assigned to anything. The OLED is
  intended to eventually be a read-only consumer of the same
  `piratebox_get_mode()`-equivalent state, informational only, never
  required for the site to function - consistent with the fallback
  behavior already built and tested this phase.

## Offline Utility Library - Stage 1: scaffolding, landing page, nav link

**Decision date:** 2026-09-01 (Utility Phase 1).

**Scope:** additive only. No networking, hostapd/dnsmasq/DHCP/DNS, captive-portal,
nginx architecture, PHP security restrictions (`open_basedir`/`disable_functions`),
or existing application logic (`upload.php`, `chat.php`, `messages.php`,
`admin/index.php`, `index.php`) changed. This phase adds a new, currently
mostly-empty "Utility" section alongside the existing PirateBox, per the
project's long-term goal of also being an offline reference/utility node
(radio reference, emergency/first-aid reference, maps/local info, a document
library, and offline search) - see the project's own planning notes for the
full multi-stage scope. Stage 1 is scaffolding only: a landing page, one nav
link, and six clean "not built yet" placeholder pages - no radio/emergency/
first-aid/maps/library content or search index yet.

**New files:**
- `public/utility/index.php` - section landing page. Explains up front, before
  anything else, that this is a local/offline network that does not require
  or provide Internet access, then links to six large tap-target cards
  (Radio, Emergency, First Aid, Maps, Library, Search) plus a row of links
  back to the existing Files/Chat/Guestbook/Help pages, so a visitor who
  lands here from either direction never hits a dead end.
- `public/utility/{radio,emergency,firstaid,maps,library,search}/index.php` -
  one clean placeholder page per future section (not broken links, not
  missing pages), each stating plainly that the section isn't built yet and
  what it will eventually contain, with a link back to `/utility/` and to
  Search.
- `data/utility/.gitkeep` - reserves `data/utility/` (parallel to the
  existing `data/` used for `chat.json`/`messages.json`) as the future home
  for the Stage 2+ JSON reference datasets (radio bands, emergency/first-aid
  topics, local info, the generated search index). Empty this phase - no
  data written yet. Sits inside the existing `open_basedir` allowance
  (`/var/www/html`), so no PHP security-restriction change was needed to
  create it.

**Modified files:**
- `includes/navbar.php` - added one `<li>` for "Utility" (`/utility/`) as the
  last item, after Help. Every existing item and its order is unchanged.
  Also changed the logo `<img>` and the Chat/Guestbook/Help links from
  page-relative (`chat.php`) to root-absolute (`/chat.php`) paths. This was
  a required, not cosmetic, fix: `navbar.php` is `require`'d by pages at
  multiple directory depths (site root, and now one level down under
  `/utility/...`), and a page-relative href resolves against the requesting
  page's own URL, not the include's location - so `chat.php` written on a
  page served from `/utility/` would have pointed at the nonexistent
  `/utility/chat.php`. Root-absolute paths resolve identically to the old
  ones for every existing root-level page (`/`, `/chat.php`, etc.) and
  correctly for any future nesting depth. Verified live (see Testing below)
  that every existing nav link and the logo still load correctly after this
  change.
- `includes/footer.php` - same fix, same reason, for the one link it
  contains (`help.php` &rarr; `/help.php`). Footer is `require`'d by
  `index.php`/`help.php`/`messages.php`/the new utility pages (not
  `chat.php`, unchanged Phase 5 decision).
- `public/assets/styles.css` - appended a new block only (`.utility-grid`,
  `.utility-card*`, `.utility-breadcrumb`, `.utility-placeholder-note`); no
  existing rule was edited or removed. Deliberately reuses the existing dark/
  purple palette and the existing `.hero`/`.help-section`/`.help-note`
  components' visual language (card background `#292938`, `#8c8dff` accent
  border/links, uppercase bold labels) rather than introducing a second
  visual style, per the instruction to keep the existing PirateBox look.

**Why a nav link now, not deferred to a later stage:** the operator
explicitly asked for the Utility section to be reachable from the normal
site nav in this stage, not left as an undiscoverable orphan page until
content exists.

**Deployment mechanics:** `/var/www/html` is owned by `www-data`, and this
session has no passwordless `sudo`, so all edits were made in this repo's
`var/www/html` mirror (owned by `moose`) and then deployed to the live path
by the operator directly, via `rsync -a --chown=www-data:www-data`/`cp` run
in their own interactive SSH session (the only place `sudo` could actually
prompt for a password) - not by this assistant. Deployed files were then
byte-diffed against the repo copy to confirm an exact match before any
testing began.

**Explicitly not done this phase (deferred to later stages, per the
operator's own staged plan):** no `poppler-utils`/other new package
installed; no radio/emergency/first-aid/maps content or datasets added; no
document library or its `open_basedir` addition; no search index or search
UI logic - the Search placeholder page is a description of what's coming,
not a working search yet.

**Backup:** `~/piratebox-backups/utility-phase1-pre-20260901-044929/`
(full `var/www/html` mirror + recorded pre-change git HEAD
`74c040e39122c7e3fff20d7f69a4bd478618f684`), created before any edit in this
phase, following the same convention as the Phase 3/4/5 pre-change backups.

**Testing performed (live, after deployment):**
- Byte-diffed every deployed file against the repo copy (exact match) and
  confirmed `www-data:www-data` ownership.
- `php -l` on every new/modified PHP file (no syntax errors).
- HTTP status check across `/`, `/chat.php`, `/messages.php`, `/help.php`,
  `/admin/` (still `401`, unchanged - Basic Auth boundary untouched),
  `/utility/`, and all six placeholder pages (all `200`).
- Confirmed the new `/utility/` link and its target render correctly, and
  that all pre-existing nav links plus `/assets/*` (stylesheet, script,
  logo) still resolve `200` when requested by a browser sitting on a nested
  `/utility/...` page.
- Re-verified all seven captive-portal probe paths
  (`/generate_204`, `/gen_204`, `/hotspot-detect.html`,
  `/library/test/success.html`, `/success.html`, `/connecttest.txt`,
  `/ncsi.txt`) still `302` to `http://10.0.0.1/`, and
  `/.well-known/captive-portal` still returns the same RFC 8908 JSON body -
  all unchanged, as expected, since neither nginx config nor dnsmasq was
  touched.
- **Live write-path test, not just a page load:** posted a real,
  clearly-labeled test message (`[Automated Stage 1 verification post - safe
  to delete via /admin/]`) to both the guestbook and chat via an
  authenticated CSRF-token POST, and confirmed each was accepted and then
  appeared back on re-fetch - proving `chat.php`/`messages.php` still work
  correctly end-to-end through the modified `navbar.php`/`footer.php`
  includes they both `require`. **These two test posts are still live in
  `data/chat.json`/`data/messages.json`** - clear them from `/admin/` if you
  don't want them kept (three independent, confirmation-gated actions exist
  there for exactly this).
- Confirmed the upload form on `/` still renders (`enctype`, `name="file"`,
  max-size attribute) - `upload.php` itself was not touched this phase, so a
  full upload round-trip was not repeated.
- Checked `nginx`/`php8.4-fpm` error logs and `journalctl` for both units
  across the entire testing window: zero new errors correlated with any
  request made during this phase (pre-existing historical log entries from
  earlier phases are unrelated and unchanged).
- Confirmed `nginx`, `php8.4-fpm`, `hostapd`, `dnsmasq` all remained
  `active` throughout with no restarts, and disk free space (`107G`)
  unaffected.

## Wi-Fi adapter notes / planned hardware

**Decision date:** 2026-09-01 (post-Phase 6). Documentation only - no
networking, service, or live configuration change accompanies this entry.

**Current production state:** the PirateBox AP is, and remains, the
Raspberry Pi 3 B+'s **built-in `wlan0`**. Nothing below changes that.

### TP-Link TL-WN722N V2/V3 - tested, not suitable as-is

Tested in Phase 6 (USB ID `2357:010c`, Realtek RTL8188EU chipset, driver
`rtl8xxxu` - the mainline in-tree driver, no DKMS/vendor module
installed). `iw phy1 info` showed only `managed` and `monitor` in
`Supported interface modes` - no `AP`. Confirmed empirically, not just by
reading the capability list: `iw phy1 interface add ... type __ap`
returned **`Operation not supported (-95)` (EOPNOTSUPP)**, rejected at
the kernel/cfg80211 level before ever reaching the driver. This adapter
is **not suitable as the PirateBox AP with the current mainline driver**.

**Do not install an out-of-tree/DKMS RTL8188EU driver** (e.g. a vendor
`8188eu`-family fork with AP support) to work around this unless that
tradeoff - an external, non-mainline kernel module, with its own
maintenance and kernel-upgrade fragility - is deliberately revisited and
approved later. See the full Phase 6 findings (chipset, firmware, power/
undervoltage observations - unrelated to this adapter, see that report)
in git history for this decision's evidence.

### ALFA AWUS036NHA / Atheros AR9271 - considered, not chosen

Has excellent mainline Linux AP support via `ath9k_htc`. Not chosen as
the primary upgrade path because `ath9k_htc`/AR9271 AP-mode operation has
a well-documented firmware limitation of **approximately 7 associated
stations**. This limitation is specific to that candidate adapter's
firmware - **it does not apply to the current PirateBox `wlan0`** (the
Pi's built-in Broadcom chip), which has no such constraint.

### Ordered: ALFA AWUS036ACM (MediaTek MT7612U) - not yet tested

Hardware has been ordered for a future primary-AP upgrade attempt:
- Chipset: MediaTek MT7612U
- Dual-band 2.4/5 GHz, 2x2 MIMO, two detachable RP-SMA antennas
- Expected driver: mainline `mt76x2u` (**expected**, not yet verified -
  this hardware has NOT arrived or been tested on this Pi as of this
  entry)
- Intended future role: primary PirateBox USB AP, **if and only if**
  testing succeeds
- The AR9271's ~7-station firmware limitation above does **not** apply to
  the MT7612U/AWUS036ACM - different chipset, different firmware/driver
  stack entirely. Conversely, **no maximum client count is claimed for
  the AWUS036ACM here** - that has not been tested or researched yet, and
  should not be assumed until it is.

**Future test plan, when the AWUS036ACM arrives** (same discipline as
Phase 6 - read-only discovery first, no changes to the working `wlan0`
PirateBox until proven):
1. Identify USB VID:PID and chipset.
2. Confirm the loaded kernel driver.
3. Check `iw` `Supported interface modes` for `AP` (and, per the Phase 6
   lesson, confirm empirically with a real `iw ... type __ap` attempt,
   not just by reading the capability list).
4. Check power/USB stability (`vcgencmd get_throttled`, dmesg for resets/
   disconnects, distinguishing sticky/historical bits from active
   ones - see Phase 6 for the method).
5. Create an isolated, temporary `PirateBox-USB-Test` AP (not `10.0.0.1`,
   not colliding with the production DHCP server, not the production
   SSID).
6. Test real client association and stability while `wlan0` remains
   operational throughout.
7. Only after successful testing, consider migrating the production
   PirateBox AP from `wlan0` to the ALFA - a deliberate, separate,
   approved step, not an automatic consequence of a successful test.
8. Establish a stock-antenna range baseline before changing antennas.

## Phase 5: onboarding/UI redesign, help page, and QR codes

**Decision date:** 2026-09-01 (Phase 5).

**Scope:** front-end/UX only, per the phase's own instructions - no
networking, captive-portal, or backend architecture changes. Builds on
the existing dark/purple/sharp-corners visual identity from earlier
phases rather than replacing it.

**New pages/includes:**
- `includes/footer.php` - a small shared footer (not used on `chat.php`,
  see below) repeating the "this network is offline, no Internet
  required" message and the direct `http://10.0.0.1/` fallback, so it's
  discoverable without hunting for it, but not repeated on every single
  element of every page.
- `includes/helpers.php` - `piratebox_fmt_bytes()`/`piratebox_fmt_duration()`,
  pulled out of `admin/index.php` (which had its own private copy) once
  `index.php`'s file listing also needed human-readable byte formatting -
  now there's one shared copy instead of a second one.
- `public/help.php` - Connect steps, an Android/Samsung-specific note,
  generic Apple/Windows/Linux guidance, a short "using PirateBox" summary,
  and an About section. Content was written to the phase's exact
  constraints: it does **not** tell users to install a certificate,
  disable browser security, or click through an HTTPS warning to use
  PirateBox (there is no HTTPS on this device to warn about in the first
  place - see the Phase 3 captive-portal entries below), and it does
  **not** claim anonymity - it explicitly states "offline does not
  automatically mean anonymous," matching this device's actual behavior
  (it can see connected devices and their requests, like any local
  network).
- `index.php` gained a hero/intro block ("PirateBox - Offline File
  Sharing" + a one-sentence explanation + quick links) so a first-time
  visitor understands what this is and what they can do, without needing
  the Help page.

**Footer NOT added to `chat.php`:** that page uses a fixed-height,
`overflow: hidden` flex layout (message list scrolls internally, input
bar pinned to the bottom - a deliberate mobile chat UX pattern from
before this phase). Appending a footer there would either get clipped or
break that layout. Chat already has full nav access to Help, so nothing
is lost.

**QR codes:** generated at *install/deploy time* by the installer via
`qrencode` (added to the `apt-get install` line - a tiny, standard CLI
tool, not a PHP/runtime dependency), not committed to git (they're a
rendering of two static strings - `http://10.0.0.1/` and
`WIFI:T:nopass;S:PirateBox;;`, matching this device's fixed IP and open
`PirateBox` SSID - the installer already knows both, so there's nothing
gained by committing a rendered PNG that's trivially regenerable and
would need to be kept in sync by hand). Both live on the Help page,
visually distinguished by caption so scanning either one is unambiguous:
the URL QR to jump straight to PirateBox once already connected, the
Wi-Fi QR to join the network in the first place. Decoded with `zbarimg`
(a temporary verification tool, installed, used once, then `apt purge`d
+ `autoremove`d again - not left on the Pi) to confirm each PNG actually
encodes the exact intended string - both did.

**File list sorting:** a `<select>` (Newest/Oldest/Name/Size) plus
clickable/keyboard-activatable column headers, implemented as pure
client-side re-ordering of the already-rendered `<tr>` elements from
`data-*` attributes already on each row - no extra request, no server
round-trip, and the table is already correctly newest-first sorted by PHP
even if this JS never runs at all (progressive enhancement, not a
requirement).

**Progressive enhancement / JS-optional baseline:** timestamps
(`file-timestamp`/`chat-timestamp`/`message-time` spans) now render a
server-side `date('Y-m-d H:i', ...)` fallback string in PHP, which JS
then upgrades to a locale-formatted version via `Intl.DateTimeFormat` on
load - previously these spans were emptied and populated by JS alone, so
a no-JS visitor saw blank timestamps everywhere. Upload still requires JS
for the progress bar specifically (explicitly acceptable per this phase's
own instructions - "except features inherently requiring JS"), but file
Browse/download, chat/guestbook reading, and navigation all work with
JS disabled.

**Admin page:** visually reorganized into two clearly distinct zones -
"System status" (labeled `read-only`) and "Destructive maintenance"
(labeled `irreversible`, dashed red border) - with no change whatsoever
to the Phase 4 security/privilege model: same nginx Basic Auth boundary,
same CSRF token, same confirmation-checkbox requirement, same
`flock()`-based locking, no sudo, no exec, no reboot/service-restart
controls added.

**Offline-resource audit:** every served page (`/`, `help.php`,
`chat.php`, `messages.php`, `admin/`) plus `styles.css` and `scripts.js`
were fetched live and grepped for any `http(s)://` reference other than
`10.0.0.1` itself, and for `@import`/`url()` in CSS - none found anywhere.
The only network calls `scripts.js` ever makes are `fetch()` to this same
site's own `chat.php`/`messages.php` endpoints.

**Deferred / explicitly out of scope for this phase** (per instructions,
not oversights): file thumbnails, chunked/resumable uploads, WebSockets,
accounts/avatars, reboot/service-restart buttons, any further
captive-portal work, and the TP-Link adapter.

**Real-device testing status:** the operator did a quick real-device pass
and confirmed the redesigned UI looks good, but explicitly deferred the
full manual checklist (desktop browser, Android/Samsung portrait layout,
QR scanning with an actual camera app, upload progress, download, chat,
guestbook, help instructions, admin page rendering - see this phase's own
instructions for the complete list) rather than running it in this
session. Everything in that list was exercised programmatically
(`curl`/`zbarimg`/etc., see the automated test results in this phase's
git commit and report) but a real-camera QR scan and real-browser
rendering check on an actual phone have not yet happened. Do this before
relying on the QR codes or mobile layout for an actual event/demo.

## Phase 4 regression found and fixed: chat/guestbook posting was completely broken (missing mbstring)

**Decision date:** 2026-09-01 (Phase 5).

Phase 4 added `mb_substr()` calls to `chat.php`/`messages.php` (server-side
length caps matching the client-side `maxlength` attributes). The
`mbstring` PHP extension was never installed on this system, so every
single POST to `chat.php` or `messages.php` since that Phase 4 commit
threw an uncaught `Error: Call to undefined function mb_substr()` and
returned an HTTP 500 - **chat and the guestbook were completely unable to
accept new posts** for the entire time between the Phase 4 commit and
this fix. This was not caught by Phase 4's own testing: that phase tested
`GET` requests to both pages and tested the admin "clear chat"/"clear
messages" actions, but never re-POSTed a new message *after* the
`mb_substr()` code was added (an earlier POST test in that same session
ran before that code existed). Found during Phase 5's functional retest
of the redesigned pages.

**Fix:** installed `php8.4-mbstring` (`php-mbstring` in the installer, to
match the existing `php-fpm` version-agnostic package name convention).
`mb_substr()` was kept (not replaced with byte-based `substr()`) because
truncating raw bytes at a fixed offset can split a multi-byte UTF-8
character in the middle and produce invalid, corrupted text if a message
happens to land exactly at the 32/2000-character boundary - a real
concern for a chat/guestbook that has to handle arbitrary language
input - whereas installing one small, extremely common PHP extension has
no real downside. Verified live: posting to both `chat.php` and
`messages.php` now returns success and the message appears correctly.

**Lesson applied going forward:** after any change to a POST/write code
path, re-test that exact path with a live POST in the same session,
even if the underlying code "obviously" hasn't changed since an earlier
test in the same conversation.

## PHP's upload_tmp_dir moved off tmpfs onto the SD card

**Decision date:** 2026-09-01 (Phase 4).

PHP's default `upload_tmp_dir` is the system temp directory, which on this
system is `/tmp` - a **tmpfs** (RAM-backed) mount, ~453MB, on a Pi with
~905MB total RAM. Every upload sits fully in `$_FILES[...]['tmp_name']`
before `move_uploaded_file()` runs, so a large upload (this app allows up
to 120MB) was consuming real RAM rather than disk during that window, on a
system that already has 300-600MB RAM in active use.

**Fix:** `upload_tmp_dir` is now `/var/www/piratebox-tmp`, a dedicated
directory on the ext4/SD-backed root filesystem, set via
`php_admin_value[upload_tmp_dir]` in `pool.d/www.conf` (`php_admin_value`
rather than `php_value` so application code can't override it back via
`ini_set()`). The directory is `www-data:www-data`, mode `0700` (private -
only PHP-FPM needs it), created via `etc/tmpfiles.d/piratebox-tmp.conf` so
it exists with correct ownership after every boot. It sits outside
`/var/www/html/public` (nginx's document root), so nginx can never serve
it regardless of location-block configuration - there was nothing to
explicitly block.

**open_basedir** (`php.ini`) was extended to include the new directory -
without this, PHP would refuse to write there at all and every upload
would fail. `/tmp` itself was left in the allowed list (harmless, nothing
depends on removing it).

**Cleanup of abandoned temp files:** under normal operation PHP deletes
its own upload temp file at the end of every request whether or not
`move_uploaded_file()` was called, so nothing should ever actually
accumulate here. The `tmpfiles.d` rule also declares a 1-day cleanup age,
which uses systemd's existing `systemd-tmpfiles-clean.timer` (ships
enabled by default on Debian - no new cron/timer was added for this) to
catch the rare case of a file orphaned by a killed/crashed PHP-FPM worker
(OOM kill, `request_terminate_timeout`, power loss).

**Side benefit:** `upload_tmp_dir` and the `uploads/` directory are now on
the *same* filesystem, which is what makes `upload.php`'s new
collision-safe rename (see below) able to use `link()` at all - `link()`
fails across filesystems (`EXDEV`), which would have been a problem while
uploads landed in `uploads/` (ext4) via a tmpfs staging area.

**Gap found and fixed along the way:** the installer previously never
actually deployed `etc/php/8.4/fpm/pool.d/www.conf` at all (only
`sites-available/default` was copied for nginx) - the repo copy was
undeployed reference material, same category of gap as the already-
documented `php.ini` drift below. The installer now copies it, and also
now sets `open_basedir` itself (previously only ever set live, by hand,
during Phase 1 - never reproduced by a fresh install). Both are Phase 4
fixes, not new Phase 4 policy.

## Concurrent same-filename uploads no longer race

**Decision date:** 2026-09-01 (Phase 4).

`upload.php`'s duplicate-filename handling used to be
`file_exists($dest)` followed by `move_uploaded_file($tmp, $dest)` in a
loop - a classic check-then-act race. If two clients uploaded a file with
the same name at close to the same instant, both could pass the
`file_exists()` check for the same candidate name before either finished
moving its file, and the second `move_uploaded_file()` call would silently
overwrite the first, discarding one upload with no error to either party.

Now the upload is first moved to a privately-named staging file within
`uploads/` (a random 32-hex-char name, which can never collide with
anything), then the real, user-facing filename is *claimed* with
`link()` - a single atomic syscall that fails with `EEXIST` rather than
overwriting if another request claimed that name microseconds earlier. On
`EEXIST` the code retries with `_1`, `_2`, etc., exactly as before, just
race-free. Verified live with two genuinely concurrent uploads of the same
filename (see git history / this phase's testing) - both files survive
intact with distinct content.

**Also added:** an explicit filename-length cap (180 characters for the
base name, before the extension) - ext4 rejects a filename component over
255 bytes outright, and a very long original filename would previously
have failed at `move_uploaded_file()`/`link()` with a misleading "check
permissions" message instead of just... having a shorter name.

## Admin/status page (Phase 4): design and security boundaries

**Decision date:** 2026-09-01 (Phase 4).

A read-only status view plus three narrow maintenance actions, at
`/admin/`, protected by nginx HTTP Basic Auth on that path only. Design
goals: no accounts anywhere else in the app (unchanged), no privilege
escalation path from the web tier to root, and no arbitrary command
execution surface.

**Access control:** HTTP Basic Auth via `auth_basic_user_file
/etc/nginx/.piratebox_admin_htpasswd`, chosen over a PHP-level login
(simpler, well-tested, doesn't need a new session/account model) or a
"secret URL" (Basic Auth is stronger and standard). The installer creates
this file **empty** - a locked-out default, not a hardcoded credential -
so the admin page is completely inaccessible until an operator explicitly
runs `setup_admin_password.sh`. No password is ever written by the
installer or committed to git.

**Why the status data doesn't come from PHP directly:** `disable_functions`
already blocks `exec`/`shell_exec`/`system`/`passthru`/`proc_open`/`popen`
at the php.ini level for this whole app (a Phase 1/2 decision, unchanged).
Wi-Fi client count, per-service active/inactive state, and undervoltage
status all fundamentally require either running a command or reading
files a `www-data` process can't reach without broader privilege. Rather
than carve any exception into `disable_functions` or grant `www-data`
sudo, a **separate, narrowly-scoped root helper**
(`piratebox_status_helper.sh`) runs those specific reads on a fixed
30-second `systemd` timer, and writes the result as a small JSON file to
`/run/piratebox/status.json` (tmpfs - never the SD card), world-readable
(`0644`). The admin page just does a plain file read of that JSON - no
new privilege, no exec, no input the helper ever consumes (it takes no
arguments and reads no request data of any kind). The systemd unit also
runs the helper under `NoNewPrivileges`/`ProtectSystem=strict`/
`ProtectHome` for defense in depth, even though the script itself does
nothing but read system state.

Everything else the admin page shows (disk space, uploads directory size,
uptime, RAM, CPU temperature) PHP reads directly and safely: plain
`disk_free_space()`/`disk_total_space()` calls and plain reads of
`/proc/uptime`, `/proc/meminfo`, and
`/sys/class/thermal/thermal_zone0/temp` - each added to `open_basedir` as
an exact file path (not a whole directory) to keep the restriction as
narrow as everything else on that list.

**Maintenance actions - three, deliberately narrow:** clear chat, clear
guestbook messages, purge uploads. Each is independent (clearing chat
never touches messages or uploads), each requires the same CSRF token as
the rest of the app plus an explicit confirmation checkbox (plus a JS
`confirm()` dialog), and none of them shell out or need any privilege
`www-data` doesn't already have - `chat.json`/`messages.json`/`uploads/`
are already owned by `www-data` (PHP creates them), so no sudo is needed
for any of these three actions. Clearing chat/messages reuses the exact
`flock()` + atomic temp-file-then-`rename()` pattern Phase 1 established
for writes to those files, so an admin-triggered clear can never race a
visitor's concurrent post and corrupt the file.

**This fixes the Phase 2-documented `purge_uploads.sh` lock-race issue -
for the web-triggered path only.** Phase 2 noted that `purge_uploads.sh`
deletes `chat.json`/`messages.json` with a bare `rm`, which doesn't
coordinate with `flock()` at all. The new admin "clear chat"/"clear
messages" actions do NOT have this problem (they use the proper lock).
`purge_uploads.sh` itself was deliberately left unchanged - it remains the
manual, SSH-only, "wipe absolutely everything at once" utility it always
was, and still carries the same documented caveat as before. The admin
page's "purge uploads" action is also new/separate: it only touches
`uploads/`, never chat or messages, unlike the script.

**Deliberately deferred: no reboot or service-restart buttons.** Doing
these safely from `www-data` would need either broad `sudo` for
`www-data` (explicitly ruled out) or a second privileged helper with a
much larger and more dangerous surface than the read-only status helper
above (a helper that *restarts services or reboots on request* is a
fundamentally different risk than one that only ever reads and writes a
JSON snapshot on a fixed timer). Not worth it for what these commands
already do fine over SSH - see the README's "Known Issues and
troubleshooting" section for the exact commands
(`systemctl restart nginx`/`php8.4-fpm`/`dnsmasq`, `restart_hostapd.sh`,
`reboot`).

**Version display:** the installer writes the deployed commit hash to
`includes/VERSION` (best-effort - if the installer isn't run from a git
checkout, the admin page just shows "unknown" rather than failing). This
file is never committed to the repo itself (each deploy generates its
own); it's a `.gitignore`-worthy artifact but small enough not to bother
- if it's ever accidentally committed, it's harmless (just a commit hash).

## Typed hostnames can silently fail to resolve due to client-side DoH - not a PirateBox bug

**Decision date:** 2026-09-01 (post-Phase 3).

**Symptom investigated:** after Phase 3, a Samsung/Android phone that had
just gotten the correct captive "Sign in to network" prompt and could load
`http://10.0.0.1/` could **not** load `http://moosehost.net/` (an
arbitrary hostname relying on dnsmasq's `address=/#/10.0.0.1` wildcard),
even though the same hostname had reportedly worked before Phase 3.

**Investigation:** a bounded, temporary live `tcpdump` capture on `wlan0`
(installed just for this, no ongoing logging left behind) during a live
retest showed the phone's browser never sent a DNS query for
`moosehost.net` to the Pi at all. Instead it sent DNS-over-HTTPS/QUIC
queries straight to a hardcoded public resolver
(`10.0.0.206.41642 > 8.8.8.8.443: UDP, length 1200`, repeated, no reply),
which is unreachable on this intentionally offline network
(`net.ipv4.ip_forward` is `0`, no NAT/masquerade rule exists anywhere in
the `nftables` ruleset) - so the query simply timed out and the page
never loaded. In the same capture window, other hostnames resolved by
background apps (`graph.facebook.com`, and `mtalk.google.com` /
`alt6-mtalk.google.com` in an earlier capture) went through plain DNS to
`10.0.0.1:53` normally and got the correct wildcard answer. Queried
directly from the Pi, dnsmasq still resolves `moosehost.net` to `10.0.0.1`
correctly, and `etc/dnsmasq.conf`'s wildcard line is byte-for-byte
identical to the pre-Phase-3 backup. This conclusively rules out
PirateBox's own DNS/network config as the cause.

**Root cause:** the browser's own "Secure DNS" (DNS-over-HTTPS) feature -
possibly compounded by Android's system Private DNS setting - bypasses
the network-provided DNS server for some typed navigations, going to a
fixed public resolver instead of asking dnsmasq. This is client-side
behavior entirely outside PirateBox's control, and can plausibly be
intermittent/state-dependent (cache, per-network trust heuristics) rather
than a hard regression - which is consistent with the same hostname
having appeared to work at some point before Phase 3.

**Decision: not worked around server-side.** The only way to force a DoH
query back onto the local resolver would be to block or intercept
outbound HTTPS/QUIC (port 443/UDP-443) - which is exactly the kind of
HTTPS interception this project has already decided against (see the
"do not implement HTTPS MITM" constraint from Phase 3). PirateBox does
not intercept, block, or MITM HTTPS or DoH traffic, and won't start doing
so just to make manually-typed hostnames more reliable.

**What remains reliable, and is the actually-intended path:** direct
`http://10.0.0.1/` and the OS-level captive-portal flow (legacy HTTP
probes and the RFC 8908 Capport API added in Phase 3) both use the
device's own system network-validation HTTP client, not the browser's
DoH-enabled resolver, and are unaffected by this. Typing an arbitrary
plain-HTTP hostname was always a secondary/fallback way to reach
PirateBox, not the primary one - the primary, supported mechanism is
automatic captive-portal detection landing the user on `10.0.0.1`
directly. A user who wants typed-hostname browsing to also work
reliably can turn off their browser's "Use secure DNS" setting for this
network; that's a client-side choice, not a PirateBox configuration.

## `rpi-update` is intentionally NOT run by the installer

**Decision date:** pre-existing, documented 2026-08-31 (Phase 2).

The original README instructed running `sudo rpi-update` to move onto the
latest firmware/kernel, citing it as the fix for iOS-related Wi-Fi
disconnect/crash issues on a Pi Zero 2 W. `installer_pi_zero_trixie.sh` no
longer runs it. Modern Raspberry Pi OS (Trixie) should not be moved onto
bleeding-edge, less-tested firmware/kernel builds as a side effect of
installing PirateBox - that trade-off is for the operator to make
deliberately, not something an installer script should do by default.

**If you're hitting Wi-Fi stability problems:** check `dmesg`/`journalctl -k`
for `hwmon` undervoltage warnings first (power supply/cable issues are a
common and cheaper-to-fix cause on a Pi 3B+) before reaching for
`rpi-update`.

## Automatic deletion of user content is OFF by default

**Decision date:** 2026-08-31 (Phase 2).

The original README described `purge_uploads.sh` as an optional nightly cron
job that deletes all uploaded files, `chat.json`, and `messages.json`. This
PirateBox's default policy is:

> **Uploads, chat history, and guestbook messages persist indefinitely**
> unless an operator explicitly runs `purge_uploads.sh` by hand, or a future
> configurable admin-interface cleanup policy is deliberately turned on.

Reasoning: this system has ~114GiB of free storage and growing that content
organically is the point of the appliance - deleting people's files/messages
every night by default is user-hostile and was never something this
specific install actually had scheduled (the nightly cron entry the README
described was already absent from the live crontab before Phase 2 - this
decision makes that absence intentional rather than silent drift).

`purge_uploads.sh` remains installed at `/usr/local/bin/purge_uploads.sh`
and in this repo as a **manual** utility. It is NOT scheduled by cron by
default, and `installer_pi_zero_trixie.sh` does not install a cron entry for
it. Running it is a deliberate, irreversible, all-or-nothing wipe of
uploads + chat + messages - see the warning comment at the top of the script
itself.

**Before exposing this through a future admin interface:** note that the
script does not coordinate with the `flock()`-based locking added in
chat.php/messages.php - it deletes `chat.json`/`messages.json` directly with
`rm`, which does not respect or wait for another process's lock. A message
posted in the same instant as a purge could theoretically be lost rather
than either cleanly preserved or cleanly wiped. Low severity for a rare,
operator-triggered action, but worth having the admin interface acquire the
same `.lock` files before deleting, once that interface exists.

## The hourly `restart_hostapd.sh` cron job has been removed

**Decision date:** 2026-08-31 (Phase 2).

`restart_hostapd.sh` unconditionally ran `service hostapd restart` every
hour via cron, disconnecting every associated Wi-Fi client on the hour,
every hour, regardless of whether hostapd needed it. Journal history
reviewed before removal showed **zero evidence of an actual hostapd crash**
across the system's uptime - the only stop/restart cycle in the log was the
cron firing at the top of the hour, which disconnected the two clients that
happened to be connected at the time.

Real hostapd recovery is now handled natively by systemd:

- The Debian-packaged `hostapd.service` unit already sets
  `Restart=on-failure`, `RestartSec=2`, `StartLimitBurst=5`,
  `StartLimitIntervalUSec=10s` - this alone recovers from an actual process
  crash.
- Live crash-testing during Phase 2 (`kill -SIGKILL` on the running hostapd
  process) found a real gap: a hard kill can leave wlan0 in a state that
  briefly loses carrier, after which hostapd exits **cleanly** (exit code 0,
  since it correctly refuses to run an AP with no carrier) - and a clean
  exit is not a "failure" to `Restart=on-failure`, so recovery did not
  happen automatically; the AP stayed down until manually restarted.
- `etc/systemd/system/hostapd.service.d/override.conf` was updated to
  `Restart=always`, which restarts hostapd on *any* exit reason. A second
  live crash test with this in place recovered the AP fully and
  automatically within ~20 seconds, with no manual intervention. The base
  unit's `StartLimitBurst=5`/`StartLimitIntervalUSec=10s` is unchanged and
  still stops a genuine restart loop (e.g. truly dead Wi-Fi hardware) after
  5 attempts in 10 seconds, requiring `systemctl reset-failed hostapd &&
  systemctl start hostapd` to try again.

`restart_hostapd.sh` remains installed at `/usr/local/bin/restart_hostapd.sh`
as a manual recovery utility (e.g. if you ever need to force a restart after
changing `hostapd.conf` by hand). It is simply no longer scheduled.

No custom wlan0 health-check watchdog was added. There is no evidence a
failure mode exists that `Restart=always` doesn't already cover, and adding
one speculatively risks exactly the kind of restart-loop/over-engineering
this phase was told to avoid. Revisit only if a real, observed failure
pattern shows up that `Restart=always` doesn't handle.

## Upload storage-exhaustion guard

**Decision date:** 2026-08-31 (Phase 2).

`var/www/html/includes/config.php` defines `PIRATEBOX_MIN_FREE_BYTES` (1
GiB), the minimum free space that must remain on the uploads filesystem
after an upload is accepted. `upload.php` checks `disk_free_space()` against
it before calling `move_uploaded_file()`; if the upload would leave less
than that free, it is rejected with a plain-language error and never
committed to permanent storage. No existing files are ever deleted to make
room.

1 GiB was chosen because it is comfortably larger than the largest single
upload allowed (130MiB - no single upload can ever flip the system straight
from "fine" to "full"), while being a small fraction of this system's
~114GiB available capacity, so it costs essentially no usable storage.

This is deliberately the **one** place this policy value lives, so a future
admin interface has a single obvious constant to make configurable rather
than a value duplicated across files.

## Captive portal detection: DHCP option 114 (RFC 8910) added alongside legacy HTTP probes

**Decision date:** 2026-09-01 (Phase 3).

**Symptom:** a Samsung device running Android 16 (SM-F946U1) did not show a
normal "Sign in to network" captive-portal prompt on connecting to
PirateBox. Instead it showed "Internet may not be available" with
"Connect only this time / Always connect / Disconnect" - the fallback
Android shows when it decides a network has *no* internet and *no*
detected portal, which is a materially worse experience than the intended
"tap to open PirateBox" flow. Firefox/Linux, by contrast, already
correctly showed "You must log in to this network."

**Investigation:** the stock nginx access log doesn't include the `Host`
header, so a temporary, narrowly-scoped diagnostic log
(`map $request_uri $captive_diag_hit` + `access_log ... if=$captive_diag_hit`,
restricted to `/` and the known captive-probe URIs only - never all
traffic) was added to nginx, and dnsmasq's `log-dhcp` was enabled
temporarily. Both were removed again once the investigation below was
confirmed; this is a repeatable technique, not something left running.

This surfaced two things:

1. The device's system HTTP client (`Dalvik/2.1.0`, i.e. not a browser)
   was repeatedly requesting plain `GET /` with `Host: 10.0.0.1` - not
   `/generate_204` or any other standard Google/Samsung probe path - and
   getting `200` with the real PirateBox homepage body. This is a
   different, additional probe from Android's standard NetworkMonitor
   check; it was not the cause of the bad dialog by itself.
2. AOSP's `NetworkStack` module (`NetworkMonitor.java`) has a feature flag
   named `DNS_PROBE_PRIVATE_IP_NO_INTERNET_VERSION` and documented
   handling for the case where a captive-check hostname resolves to a
   private/RFC1918 address - exactly PirateBox's situation, since the
   wildcard DNS (`address=/#/10.0.0.1`) resolves
   `connectivitycheck.gstatic.com` (and everything else) to `10.0.0.1`.
   The working theory is that modern Android specifically distrusts a
   captive-portal signal derived from a DNS answer pointing at a private
   IP (a reasonable anti-hijacking precaution in general), and falls back
   to "no internet" rather than trusting the heuristic HTTP redirect - a
   fundamental limitation of DNS-hijack-based captive detection on an
   intentionally-private, intentionally-offline network like this one.

**Fix:** RFC 8910 (DHCP option 114) plus RFC 8908 (the Captive Portal API
JSON it points to) exist precisely to give clients a captive-portal signal
that doesn't depend on DNS-hijack heuristics. dnsmasq now sends option 114
(`dhcp-option=114,"http://10.0.0.1/.well-known/captive-portal"` - dnsmasq
2.91 has no built-in name for option 114, so it's set numerically; the
quoted value is sent as a raw ASCII URI string, which is the correct RFC
8910 wire encoding, confirmed both via `dnsmasq --test` and by reading the
live `log-dhcp` trace of the option actually being sent). nginx serves
that URL with `Content-Type: application/captive+json` and body
`{"captive":true,"user-portal-url":"http://10.0.0.1/"}`. `captive` is
permanently `true` - there is no "accept" flow, because this network never
gains real internet access and shouldn't pretend to; `user-portal-url`
points straight at the real PirateBox homepage over plain HTTP (neither
RFC 8908 nor RFC 8910 mandates TLS for this URL - it's a SHOULD in RFC
8910 section 5's security considerations, not a MUST - and this project
does not implement TLS/HTTPS interception).

**Confirmation:** the DHCP trace showed the device's own client
(`vendor class: android-dhcp-16`) requesting option 114 in its parameter
request list, and dnsmasq sending it back correctly encoded. After a live
Wi-Fi reconnect on the same device with this in place, the phone showed
the normal captive "Sign in to network" prompt instead of "Internet may
not be available" - confirmed by the device's owner in the same session.
Full end-to-end confirmation that tapping the notification loads the
PirateBox homepage in the system captive browser (as already independently
observed working via the legacy `/generate_204` redirect path earlier in
this same investigation) is still worth re-checking after any future
change, but the core fix - getting the correct prompt to appear at all -
is confirmed on real hardware, not just config-level testing.

The legacy DNS-hijack HTTP-probe redirects (`/generate_204`, `/gen_204`,
`/hotspot-detect.html`, `/library/test/success.html`, `/success.html`,
`/connecttest.txt`, `/ncsi.txt`, all still returning `302` to
`http://10.0.0.1/`) are unchanged and untouched - they remain the only
mechanism for Firefox/Linux, Windows NCSI, Apple, and any Android/ChromeOS
device that doesn't request option 114. The two mechanisms are additive,
not a replacement.

**Not done:** no attempt was made to intercept HTTPS, generate certificates,
redirect port 443, or otherwise make the network appear to have real
Internet access - all explicitly out of scope and contrary to this
project's offline-by-design intent.

**Housekeeping:** `var/www/html/public/captive.html` (a self-refreshing
HTML page, previously `try_files`-served for the Apple probe paths) is no
longer referenced by nginx now that those paths 302-redirect directly to
`http://10.0.0.1/` like every other probe path. Left in place, unreferenced
- harmless, and simple to wire back in if a future platform quirk needs a
non-redirect response instead of a 302.

## Pre-existing `dhcpcd.conf` / `hostapd.conf` live drift, synced during Phase 3

**Decision date:** 2026-09-01 (Phase 3).

While reviewing live config before making captive-portal changes, two
small pre-existing differences between the live system and this repo (not
part of Phase 1 or Phase 2's tracked changes) were found and synced into
the repo, since they reflect the actual working configuration and neither
carries any risk:

- `dhcpcd.conf`: `option ntp_servers` was uncommented live (harmless -
  just requests NTP server info via DHCP) and `denyinterfaces eth0` was
  present live but missing from the repo copy (keeps dhcpcd from touching
  eth0 at all, leaving it to plain DHCP/whatever the network provides -
  consistent with eth0 being the dedicated SSH/management interface, not
  part of the PirateBox AP).
- `hostapd.conf`: only a missing trailing newline - cosmetic.

No live system files were changed for this - only the repo's reference
copies, to match what was already actually running.

## The repo's `etc/php/8.4/fpm/php.ini` is a reference copy, not what gets deployed

**Decision date:** discovered during Phase 1, documented 2026-08-31.

`installer_pi_zero_trixie.sh` edits the **live system's**
`/etc/php/$PHP_VER/fpm/php.ini` directly with `sed`, based on whatever PHP
version it auto-detects (`ls /etc/php | sort -V | tail -1`). It does not
copy `etc/php/8.4/fpm/php.ini` from this repo anywhere. That means the
repo's copy of this file and the live deployed file can (and already have)
drift apart - confirmed during Phase 1 when their SHA256 hashes differed
before any Phase 1/2 change was made (`display_errors`, `log_errors`,
`memory_limit`, and `max_file_uploads` all differed).

This phase did **not** redesign that architecture. When you change a
PHP setting, you currently have to update both:

1. The live file (`/etc/php/8.4/fpm/php.ini`) for it to take effect, and
2. This repo's `etc/php/8.4/fpm/php.ini`, by hand, for documentation/future
   installs to match - the installer's `sed` commands do not read from it.

A future phase could make the installer deploy the repo's file directly (or
apply the same `sed` transforms to it too) so this can't drift again - out
of scope here.
