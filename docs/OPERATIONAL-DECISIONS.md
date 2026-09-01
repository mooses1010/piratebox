# Operational decisions

This file records intentional configuration/behavior decisions that differ
from the original upstream PirateBox project or from what the README used to
recommend, so a future maintainer (human or AI) doesn't "fix" them back to
the old behavior without knowing why they were changed. Each entry has a
date and the reasoning; if you're going to reverse one, update this file too.

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
