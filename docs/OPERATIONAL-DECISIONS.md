# Operational decisions

This file records intentional configuration/behavior decisions that differ
from the original upstream PirateBox project or from what the README used to
recommend, so a future maintainer (human or AI) doesn't "fix" them back to
the old behavior without knowing why they were changed. Each entry has a
date and the reasoning; if you're going to reverse one, update this file too.

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
