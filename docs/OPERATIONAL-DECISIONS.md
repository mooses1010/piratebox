# Operational decisions

This file records intentional configuration/behavior decisions that differ
from the original upstream PirateBox project or from what the README used to
recommend, so a future maintainer (human or AI) doesn't "fix" them back to
the old behavior without knowing why they were changed. Each entry has a
date and the reasoning; if you're going to reverse one, update this file too.

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
