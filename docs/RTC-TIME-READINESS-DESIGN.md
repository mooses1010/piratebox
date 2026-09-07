# RTC / Time Readiness Design (Stage 28)

**Status: AUDIT + DESIGN ONLY.** No package was installed, no hardware
was wired, and no config file was changed as part of this stage. This
document records what was verified live on this Pi, the real
(previously undocumented) risk that verification found, and the two
candidate mitigations for the operator to choose from later - per
instruction, installing a new package or wiring new hardware both stop
for explicit approval first, same as every prior stage that touched
either boundary (Stage 19's `ZipArchive` stop, Stage 11/12's hardware
designs).

**Superseded 2026-09-06 - see §6.** The DS3231 is no longer "planned,
not installed": it is physically wired onto the I2C1 bus and confirmed
present via `i2cdetect`. `fake-hwclock` remains not installed (correctly
so - a real RTC makes it redundant, see §6). Read §6 first if you're
orienting on current state; §§0-5 below are kept for the audit history
that led here.

**Still true, unchanged by Field Tools (Post-Stage-32):** this audit's
own live checks (`/sys/class/rtc/`, the NTP-synchronized flag) are now
also surfaced to visitors, honestly, on the live site itself -
`includes/fieldtools_time.php`'s `piratebox_get_time_source_status()`
and `/utility/fieldtools/time/` - and named in `docs/PHYSICAL-CONTROL-
UX-DESIGN.md`'s OLED Clock page spec as what that future page should
read too. See `docs/FIELD-TOOLS-DESIGN.md` §4 for that design. Nothing
in this document's own findings needed correcting.

---

## 0. Round 8 update (2026-09-03): the operator-observed wrong clock was a config bug, not unreachability

**The operator reported the displayed clock being noticeably off.**
Investigating that from scratch (not assuming §1/§2 below still holds)
found something this document's original Stage 28 audit did not
anticipate: **`eth0` (the management/wired interface) currently has a
real, working Internet path** - `ip route` shows a default route via
`192.168.1.1`, `/etc/resolv.conf` has working nameservers, and both
DNS resolution (`getent hosts time.cloudflare.com` returns real
addresses) and ICMP (`ping 1.1.1.1`, ~9-19ms RTT) succeed. §1/§2's
"this Pi has no confirmed onward Internet uplink... NTP cannot ever
actually sync in the field" was a correct description of this Pi's
situation *at Stage 28's time*, but is no longer the operative fact -
whether that's because the network topology changed since or because
it was never actually tested end-to-end at Stage 28 wasn't
determined, and doesn't change what to do next.

**Root cause of the sync failure, found and confirmed:**
`/etc/systemd/timesyncd.conf`'s `[Time]` section reads
`NTP=time.cloudflare.comtime.cloudflare.com` - the string
`time.cloudflare.com` appears twice with no space or separator between
the copies, producing one malformed hostname instead of one valid one.
`getent hosts time.cloudflare.comtime.cloudflare.com` fails to resolve
(confirmed live, exit code 2) - `systemd-timesyncd` has been trying to
sync against a domain that doesn't exist. `systemctl status
systemd-timesyncd` confirms the service itself is `active` and
otherwise healthy (no crash, no permission error) - `timedatectl`'s
`System clock synchronized: no` is entirely explained by this one
malformed line, not a deeper problem. The `#FallbackNTP=` line just
below it has the identical corruption pattern (`time.cloudflare.
com0.debian.pool.ntp.org...`, missing a separator) but is commented
out, so it currently has no effect either way.

There is no drop-in override - `systemd-analyze cat-config systemd/
timesyncd.conf` confirms `/etc/systemd/timesyncd.conf` plus one
harmless RPi-packaged `SaveIntervalSec=5m` drop-in is the complete,
actually-effective configuration, so fixing the one file fixes the
real behavior.

**This is a standard-OS-mechanism, zero-network-risk fix** - it only
changes what hostname `systemd-timesyncd` queries over the existing,
already-configured `eth0` management interface; it does not touch
`hostapd`, `dnsmasq`, `wlan0`, or anything the visitor-facing AP
depends on. But it requires editing a system config file and
restarting a systemd unit, which is outside this project's two narrow
`NOPASSWD` sudoers grants (`piratebox_deploy.sh` and
`set_piratebox_mode.sh` only - see `CLAUDE.md` §2) - **a genuine
operator gate, not something this session can complete itself.**

**Recommended fix, for the operator to run:**
```
sudo sed -i 's/^NTP=.*/NTP=time.cloudflare.com/' /etc/systemd/timesyncd.conf
sudo systemctl restart systemd-timesyncd
timedatectl status   # expect "System clock synchronized: yes" within
                      # a few seconds to ~1 minute, given eth0's
                      # confirmed live path to time.cloudflare.com
```
Optional cosmetic cleanup of the same corruption in the inactive
`#FallbackNTP=` line (harmless to fix or leave, since it's commented
out either way):
```
sudo sed -i 's/^#FallbackNTP=.*/FallbackNTP=0.debian.pool.ntp.org 1.debian.pool.ntp.org 2.debian.pool.ntp.org 3.debian.pool.ntp.org/' /etc/systemd/timesyncd.conf
```

**No PirateBox code needs to change for this fix to take effect.**
`piratebox_status_helper.sh` already reads `timedatectl`'s live
synchronized flag into `/run/piratebox/status.json`'s `time_source.
ntp_synchronized` field (confirmed live: currently `false`, correctly
and honestly reflecting the current broken state - not a bug in the
reporting), `includes/fieldtools_time.php`'s
`piratebox_get_time_source_status()` already surfaces that field
as-is, and `piratebox_oled_daemon.py`'s Time page already renders
`"{rtc}, {ntp}"` from the same field. Once the operator's fix lands,
all three will correctly start reporting `NTP-synced` whenever `eth0`
has connectivity, and correctly fall back to `not synced` the moment
it doesn't (e.g. the Pi taken off the LAN into the field) - that
graceful, honest fallback already works today (it's exactly what
"`System clock synchronized: no`" is doing right now), so nothing
about the "untrusted/no RTC" state's behavior needed fixing, only the
config bug that was keeping this Pi stuck in it unnecessarily while
plugged into a network that could have corrected it.

**Restating this project's three conceptual time-confidence states in
light of that** (unchanged in shape from what this project has always
intended - see `docs/FIELD-TOOLS-DESIGN.md` §4 - just now achievable
in the first state rather than permanently theoretical):

1. **NTP synchronized** - achievable today, whenever `eth0` has a
   working uplink, once the operator applies the fix above. Not
   presented as available until it actually reports true.
2. **RTC-backed but not presently NTP-synchronized** - **not currently
   exposed anywhere as an available state, correctly**, since no
   hardware RTC exists (`/sys/class/rtc/` empty, confirmed again this
   session) and none of `rtc_detected`, `piratebox_status_helper.sh`,
   or the OLED/Field Tools consumers claim otherwise. This stays
   accurate/inert until a DS3231 (or similar) is actually installed -
   see §3's still-current hardware option, unattempted this round per
   "do not install RTC hardware" being explicitly out of scope for
   round 8.
3. **Untrusted / no RTC** - this Pi's actual, honestly-reported state
   right now, and its correct fallback state the moment `eth0` is
   disconnected even after the NTP fix - not a defect, the intended
   honest-degradation behavior this whole document's design already
   called for.

**Explicitly not done this round, per instruction:** no `fake-hwclock`
install (would only paper over a gap that a real, reachable NTP source
can close outright - see §3's original reasoning, which favored
`fake-hwclock` specifically for a Pi with *no* uplink; that premise no
longer holds here), no hardcoded time, no RTC hardware purchase/wiring,
no change to how Emergency Mode or offline operation behaves offline
(a disconnected Pi still degrades to state 3 exactly as before).

## 1. Current state (verified live, this session)

| Check | Result |
|---|---|
| Hardware RTC present | **No** - `timedatectl` reports `RTC time: n/a`; `/sys/class/rtc/` is empty. |
| `fake-hwclock` installed | **No** - not in `dpkg -l`. This is the piece that matters most (see §2). |
| Time sync mechanism | `systemd-timesyncd` (NTP), currently `active` but `System clock synchronized: no` - this Pi has no path to a real NTP server (it *is* the isolated access point; it has no confirmed onward Internet uplink), so NTP cannot ever actually sync in the field. |
| System clock at time of this audit | Plausible (`2026-09-01`, matching every other timestamp in this session) - the Pi has stayed powered since its last correct time source, whatever that was. This audit could not observe a real "cold boot with no network" scenario without power-cycling the live device, which was not done. |

## 2. The real risk this creates

A Raspberry Pi has no battery-backed clock of its own. Without a
hardware RTC, the kernel's clock starts every boot from whichever of
these gets there first, in order: **(a)** NTP, if a network path to a
time server exists, **(b)** `fake-hwclock`'s saved last-known time, if
that package is installed, or **(c)** whatever fallback the kernel/
bootloader default to otherwise - which can be significantly wrong
(commonly the kernel build date, or the last-modified time of some
filesystem read during boot).

**PirateBox's whole design point is running with no Internet access.**
That makes (a) unavailable *by design*, not as an edge case - and (b) is
not installed. That leaves this Pi one power cycle away from booting
with a badly wrong clock, in the exact deployment scenario (a real,
sustained, off-grid emergency) where this project's own instructions
already flag Emergency Mode's reliability as the highest-stakes
property in the whole build.

**What a wrong clock actually breaks**, reasoned through this project's
own timestamp consumers rather than assumed:

- **Displayed dates are wrong, but *relative* durations inside one boot
  session stay correct.** Chat/Logbook/Bulletin message timestamps
  (`time()` at write time), the recovery-message rate-limit cooldowns
  (Stage 16), and the CSRF/session lifetime all compare two `time()`
  calls taken *after* the same boot - if the clock is wrong but stable,
  those comparisons are still internally consistent. The *displayed*
  date/time next to a chat message would just be wrong, which is
  confusing but not a functional failure.
- **Anything that spans a reboot is the real exposure.** Stage 21's
  cumulative Emergency Mode runtime (`data/mode-transitions.log`) sums
  `<timestamp> <mode>` pairs across the device's whole lifetime - a
  clock that resets to a wrong value on every boot would corrupt this
  total (a transition logged under a wildly wrong clock, followed by one
  under a corrected clock, produces a nonsense duration - possibly
  negative, definitely wrong). Stage 25's backup filenames
  (`piratebox-data-<timestamp>.tar.gz`) sort and prune by filename - a
  backwards-jumping clock across reboots could produce a new backup that
  *sorts as older* than one it should supersede, which would defeat
  `--retain N`'s "keep the newest" pruning logic silently.
- **Device ID and content are unaffected.** `device-id.json` (Stage 16)
  is generated once, from `/dev/urandom`, never from the clock - no
  exposure there. All static reference content is timestamp-independent.

## 3. Candidate mitigations (for the operator to choose - neither done yet)

| Option | What it is | Cost | Recommendation |
|---|---|---|---|
| **Install `fake-hwclock`** | Standard Debian/Raspberry Pi OS package. A systemd service saves the current time to `/etc/fake-hwclock.data` periodically and on shutdown, then restores it *before* any other service starts on the next boot - "last known good," not "actually correct," but close enough to keep timestamps monotonically sane across a power cycle with no network. | One `apt install fake-hwclock` (small, no compilation, no reboot required to take effect on the *next* boot) - crosses this session's explicit no-package-installs-without-asking boundary, so **not installed by this stage**. | **Recommended near-term fix** - closes the actual gap found above at negligible cost, with no hardware purchase needed. |
| **Add a hardware RTC module** (e.g. DS3231, PCF8523 - any standard I2C RTC breakout) | A battery-backed clock chip that keeps real, absolute time across arbitrarily long power-off periods, unlike `fake-hwclock`'s "time froze while off" model. | A small part purchase, physical wiring, `dtoverlay=i2c-rtc,ds3231`-style config, and `hwclock` integration - this is genuine new hardware, so it belongs alongside Stage 11's OLED/button build, not this stage. **Shares Stage 11's already-reserved I2C bus** (GPIO2/SDA, GPIO3/SCL) - an RTC is a second device address on the *same* two-wire bus the OLED already claims, not a new pin conflict, since I2C is multi-drop by design. | **Good complementary long-term addition** if/when the Stage 11 hardware order happens, but not a substitute needed urgently given `fake-hwclock` alone already closes most of the practical gap for free. |

Both can coexist - a hardware RTC gives the Pi accurate absolute time
immediately on boot even after weeks of power-off; `fake-hwclock`
remains a reasonable zero-cost fallback for a Pi that never gets the RTC
add-on.

## 4. What is *not* proposed

- **No software workaround for the clock itself** (e.g. an NTP fallback
  server bundled locally) - this project has no reliable way to know a
  correct time independent of the clock it doesn't trust yet; that's
  circular. The fix is at the OS/hardware layer (§3), not in PHP.
- **No change to any timestamp-consuming code this stage** - every
  consumer surveyed in §2 already behaves exactly as well as it can
  given whatever `time()` returns; the code isn't the problem, the
  clock source is. Once §3's near-term fix (`fake-hwclock`) is approved
  and installed, no PirateBox code changes are needed to benefit from
  it - `time()` starts returning something more trustworthy from the
  next boot onward, and every existing consumer picks that up for free.

## 5. Testing performed

Entirely read-only against the live system: `timedatectl`, `dpkg -l`,
`ls /sys/class/rtc/`, `date`, `uptime -s`. No package installed, no
config file touched, no reboot performed (a real cold-boot-with-no-
network test would have required power-cycling the live production
device, which was judged unnecessary risk for a finding already
confirmed by direct inspection of the relevant system state - the
absence of both a hardware RTC and `fake-hwclock` is sufficient by
itself to establish the risk in §2 without needing to reproduce it
live).

## 6. DS3231 physically wired - hardware verification + operator gate (2026-09-06)

**What changed:** the operator wired a DS3231 RTC breakout (with its
onboard AT24C32 EEPROM) onto the existing I2C1 bus via a breadboard -
the same bus §3's original candidate table anticipated ("shares Stage
11's already-reserved I2C bus... not a new pin conflict"). The OLED was
briefly broken by two wiring mistakes during that work and is now
confirmed working again.

**Bus scan, this session, before any config change:**

```
i2cdetect -y 1
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
30: -- -- -- -- -- -- -- -- -- -- -- -- 3c -- -- --
50: -- -- -- -- -- -- -- 57 -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- 68 -- -- -- -- -- -- --
```

All three expected devices, nothing unexpected: **0x3c** (the existing
OLED, unaffected), **0x57** (the DS3231 board's AT24C32 EEPROM), **0x68**
(the DS3231 itself). Note this scan alone only proves each address
*acknowledges* on the bus - it does not yet prove a kernel driver is
bound or that the chip's actual RTC registers are readable; §6's script
(next) verifies that with a real driver bind and a real register
read/write, not just the raw address probe.

**Configuration state found (before this round):** no RTC overlay in
`/boot/firmware/config.txt` (only `dtparam=i2c_arm=on` from the OLED
bring-up), no `/dev/rtc*`, no `/etc/adjtime`, `fake-hwclock` not
installed (still correctly true - see below), and no udev hwclock rule
on this OS image. The running kernel (`6.18.39+rpt-rpi-v8`) is
confirmed built with `CONFIG_RTC_HCTOSYS=y` /
`CONFIG_RTC_HCTOSYS_DEVICE="rtc0"` (checked directly against
`/boot/config-$(uname -r)`, not assumed) - meaning **the moment
`/dev/rtc0` exists, the kernel itself sets the system clock from it,
very early in every future boot, with no additional service, udev
rule, or package required.** This is why the fix is exactly one
`dtoverlay` line plus a live-apply/verify pass, not a larger change.

**What was added:** `tools/configure_rtc_ds3231.sh` (new, idempotent,
tested - see `tools/test_rtc_ds3231_config.py`, 12 assertions). It:
1. Adds `dtoverlay=i2c-rtc,ds3231` to `/boot/firmware/config.txt`
   (backed up first as `config.txt.pre-rtc-bak.<timestamp>`, matching
   the OLED bring-up's own `config.txt.pre-i2c-bak` convention) - the
   overlay file (`/boot/firmware/overlays/i2c-rtc.dtbo`) already ships
   on this OS image, so no package install is involved.
2. Applies the overlay **live** via the `dtoverlay` command, so the
   whole chain can be verified in one run without a reboot (the
   config.txt line still makes it persist across every future boot on
   its own).
3. Confirms `/dev/rtc0` and the `dmesg` driver-registration lines.
4. Reads the RTC **before** writing anything - a fresh, never-set,
   battery-less DS3231 has no reason to already know the correct time,
   so a stale/garbage read (or an oscillator-stop-flag warning) at this
   step is itself positive evidence of real chip communication, not a
   stub.
5. Writes the current (NTP-correct) system time to the RTC with
   `hwclock --systohc --utc`, then reads it back to confirm the round
   trip.
6. Re-checks `i2cdetect -y 1` and `piratebox-oled.service` as an
   explicit regression guard - the RTC is a second device on the OLED's
   own bus, and this project's discipline is "prove the neighbor is
   still fine," not assume it.

**Why this is the operator gate, not something completed
automatically:** per `CLAUDE.md` §2, any system-configuration change
(`/boot/firmware/config.txt`) and any physical-hardware change are
explicit stop conditions - this session has no standing `sudo` grant
covering either, and none was added (a new sudoers line would itself be
"new privilege escalation," also out of scope). The single command:

```
sudo tools/configure_rtc_ds3231.sh
```

**`fake-hwclock` - deliberately still not proposed here.** §3
originally recommended it as a *near-term, zero-hardware-cost*
mitigation for a Pi with no RTC at all; now that a real hardware RTC is
wired and about to be configured, installing `fake-hwclock` alongside
it would add a redundant fallback mechanism for a gap the RTC itself
already closes better (an actual absolute clock vs. "time froze at
shutdown"). Not installed, not needed, no change to that recommendation
beyond noting why it no longer applies.

**The missing battery - what it does and doesn't block.** This board
has a charging circuit for a rechargeable cell, and the coin cell
supplied is a non-rechargeable CR2032 - correctly *not* inserted, since
charging a non-rechargeable cell is a real safety hazard, not a
formality. What this means concretely:
- **Not blocked:** everything §6's script does. The DS3231 runs
  entirely off Pi power (`VCC`) for as long as the Pi stays on, which is
  the actual condition under which the script's read/write/round-trip
  verification happens - this is a completely genuine test of the chip
  and the kernel/hwclock path, not a simulation.
- **Blocked, and cannot be honestly tested yet:** the actual point of
  an RTC - keeping correct time **through a real power-off**. Without a
  battery (rechargeable, correctly installed, and given time to charge)
  or the CR2032 swapped onto a non-charging board/holder, a power cycle
  will make the DS3231 lose time exactly like the Pi's own clock does
  today, and this document will not claim otherwise. Confirming true
  persistence requires: fit an appropriate battery, then perform a real,
  deliberate power-off-and-back-on test and re-read `hwclock -r` - future
  work, once battery hardware exists, not this round.

**No PirateBox application code changes this round.** Exactly as §4
already predicted: `piratebox_get_time_source_status()`
(`includes/fieldtools_time.php`) reads `/sys/class/rtc/` generically and
will report `rtc_detected: true` the instant `/dev/rtc0`/`/sys/class/
rtc/rtc0` exists, with zero code changes - this round only had to make
that device actually exist.

## 7. First real run: missing `hwclock` + a clock-clobber hazard found and fixed (2026-09-06, same day)

**What happened:** the operator ran §6's script. The overlay bound
correctly (`rtc-ds1307 1-0068: registered as rtc0`, `/dev/rtc0`
present, the unset RTC read back ~2000-01-01 as expected for a never-
set, battery-less chip), but Steps 4/5 failed with `hwclock: command
not found`.

**Root cause, confirmed live, not guessed:** this Pi runs Debian 13
("trixie"). `dpkg -S hwclock` shows only doc/systemd-unit/bash-
completion references - no binary - and `dpkg -l util-linux` confirms
`util-linux` (2.41.5) is installed without it. `apt-cache show
util-linux-extra` confirms that package exists, is available from
`trixie-security`, and (per `apt-get install --dry-run
util-linux-extra`) installs as exactly one clean new package with zero
removals and zero other upgrades. This is a real, current Debian
packaging split (`hwclock` moved out of the base `util-linux` package
into `util-linux-extra`), not a broken install or a PirateBox mistake -
a minimal Raspberry Pi OS image simply doesn't carry the "extra"
package by default.

**Fix:** `tools/configure_rtc_ds3231.sh` gained a Step 0 -
`command -v hwclock`, and only if that fails, `apt-get update && apt-get
install -y util-linux-extra`, then a hard verification that `hwclock`
now resolves before continuing. Idempotent: a system that already has
it (this Pi, after the fix is applied once) never triggers the network
apt operation again on a re-run.

**A second, more important finding while fixing this: the live-apply
step can silently clobber a known-good NTP-synchronized system
clock.** `CONFIG_RTC_HCTOSYS` (confirmed `=y` in §6) does not wait for
a reboot to act - the kernel's hctosys mechanism fires the instant the
named RTC class device (`rtc0`) is registered, which is exactly what
the live `dtoverlay` apply in Step 2 does. The operator's own captured
output (`rtc-ds1307 1-0068`'s ~2000-01-01 read, right at bind time) is
consistent with this having already happened: the moment the overlay
bound, the kernel almost certainly stepped the system clock from
NTP-correct back to the RTC's unset ~2000-01-01 default, *before* the
script ever reached the commands meant to fix that. Left unguarded,
this is worse than having no RTC at all - the previous no-RTC fallback
paths (NTP unavailable, or a kernel/filesystem-mtime default) rarely
land 26 years off; an unset DS3231 reliably does.

**Hardening added:** a new `resync_and_verify_ntp_time()` helper -
always force-restarts `systemd-timesyncd` and polls `timedatectl show
-p NTPSynchronized --value` until it reports `yes` (aborting after 15s
if it never does, rather than trusting an unverified clock). It
deliberately never trusts a *cached* "already synchronized" flag,
since that flag only reflects timesyncd's own last poll and has no way
to know the kernel silently stepped the clock afterward. Called twice,
bracketing the live-apply: once immediately before (recovers from
exactly the scenario the operator hit - a previous run that got far
enough to trigger the clobber and then failed on the missing binary),
and once immediately after (undoes the clobber this run's own
live-apply may have just caused), before anything reads system time as
ground truth or writes it into the RTC in Step 5.

**Known, accepted limitation - not solved by this fix, and not in
scope to solve this round:** without a battery, the exact same
clobber-then-recover sequence will repeat at **every future boot**,
not just during this commissioning session - `CONFIG_RTC_HCTOSYS` is
unconditional and fires on every boot once the overlay is persisted in
`config.txt`, and the battery-less DS3231 will keep reporting a
stale/reset value after every real power-off. In practice this Pi's
`eth0` NTP path (confirmed reliable earlier this document) should
correct it within moments of `systemd-timesyncd` starting, the same
way it always has - but the transient wrongness during that window is
now a large, specific jump (~2000-01-01) rather than the milder
defaults the no-RTC fallback path used to produce. This is a real
trade-off of commissioning the RTC ahead of its battery, honestly
recorded rather than glossed over; it closes on its own the moment a
battery is fitted (the RTC will then hold real time across a boot, and
`hctosys` will seed the system clock with something correct instead of
a reset default). No new boot-time watchdog/service was added to paper
over this window this round - out of scope for a commissioning-time
script fix, and not requested.

**Validation performed:** static tests only in this environment (no
live `/boot/firmware/config.txt`, network, or root access here) -
`tools/test_rtc_ds3231_config.py` grew from 12 to 17 assertions,
covering the gated/idempotent package install, the update-before-install
ordering, the post-install verification, and that
`resync_and_verify_ntp_time` is both defined and called at least twice
around the live-apply, with its own failure path refusing to proceed
rather than trusting an unverified clock. Full existing test suite
re-run and confirmed unaffected.

## 8. Battery-backed production module: R4 modification, OSF handling, and the power-loss validation test (2026-09-07)

**Hardware change:** the original (unmodified) DS3231/AT24C32 module
used for §§6-7 has been replaced with a second, identical module that
was modified specifically for safe non-rechargeable battery use, and a
real CR2032 is now installed:

- **R4** (marked "201" = 200 ohm), which feeds the module's onboard
  VCC-to-battery charging path, was **removed**. Most cheap DS3231
  breakout boards include this resistor to trickle-charge a
  rechargeable cell (LIR2032) from VCC - continuously trying to charge
  a normal, non-rechargeable CR2032 is a real hazard (overheating,
  venting, leakage), not a formality to skip.
- **Measured before/after, not assumed:** with the module powered from
  the Pi's 3.3V rail and the battery holder empty, it read a stable
  **~3.14-3.18V** with R4 in place (the charging path actively driving
  the holder) and only **~0.22V** after R4's removal - direct
  confirmation the charging path is genuinely broken, not just
  "probably fine."
- A standard **CR2032 is now installed** in the modified holder. The
  module is still powered from Pi 3.3V and wired identically (SCL/SDA/
  VCC/GND, same shared I2C1 bus as the OLED) - only the RTC board
  itself changed, nothing on the Pi side.

**Live re-verification after the swap (this round), before touching
anything:** `i2cdetect -y 1` confirmed all three expected addresses
again - `0x3c` (OLED), `0x57` (EEPROM), `0x68` **shown as `UU`**
(already kernel-driver-bound, not just acknowledging a raw probe - a
stronger confirmation than §6's original scan, which happened before
any driver existed yet). `dmesg -T` showed the boot-time bind for the
*new* chip: `rtc-ds1307 1-0068: SET TIME!` /
`registered as rtc0` / `setting system clock to 2000-01-01T00:00:26 UTC`
- exactly the §7 hazard, reproduced live and unprompted: a fresh
module, even a battery-backed one that has simply never been *set*
yet, still reports an invalid/default time on its first-ever read, and
`CONFIG_RTC_HCTOSYS` still clobbers the system clock with it at boot.
`uptime -s` confirmed this was a real, recent reboot (consistent with
needing the Pi powered off to safely handle the module swap on a
breadboard), and `systemd-timesyncd` had already corrected the
*system* clock in the ~12 minutes since. **Deliberately not trusted as
proof the chip itself held correct time:** `timedatectl status`'s "RTC
time" field is not a reliable live read for this purpose (it can
reflect a cached offset rather than a fresh hardware query) - the only
trustworthy read is `hwclock -r` on `/dev/rtc0` directly, which needs
root and is exactly what `tools/configure_rtc_ds3231.sh` performs
early (Step 4) before writing anything.

**Oscillator-stop / voltage-low (OSF) handling - new this round:**
`hwclock` (util-linux 2.41.5, already installed per §7) exposes
`--vl-read`/`--vl-clear`. Its own man page: *"Some RTC devices are able
to monitor the voltage of the backup battery... The `--vl-clear`
function resets the Voltage Low information, which is necessary for
some RTC devices after a battery replacement."* This commissioning
**is** exactly that case - the chip's first-ever battery. The DS3231's
OSF bit (surfaced generically by `hwclock` as "voltage low") latches
whenever the chip can't vouch for its own stored time, which is
unconditionally true before any real time has ever been written to it.
`tools/configure_rtc_ds3231.sh` now: reads the flag before writing
anything (diagnostic baseline, expected to show a stop/low condition),
writes the NTP-verified time (unchanged Step 5/6 mechanics from §6/§7),
then clears the flag and re-reads it to confirm - never clearing before
a real time exists, since the flag being set is exactly correct until
that point. All three `--vl-*` calls are non-fatal (`|| true`) per
hwclock's own caveat that "not all RTC devices have this monitoring
capability" - this is diagnostic value-add, never a load-bearing
requirement for real commissioning to succeed.

**The one remaining software step - same command as §6/§7, now
carrying this round's fixes too:**

```
sudo tools/configure_rtc_ds3231.sh
```

### The power-loss validation test (operator action - not performed or requested by this round's automation)

Everything above proves the chip communicates correctly and can be
written/read while the Pi stays powered - it does **not** yet prove
the CR2032 actually holds time through a real, total loss of Pi power.
That is a genuine physical test, deliberately left for the operator to
choose when to run:

1. **Before powering off:** run `date -u` and write down the exact UTC
   time. This is your ground truth to compare against after the test.
2. **Disconnect the network path first:** unplug the `eth0` cable (this
   Pi's only confirmed real NTP uplink - see §0). This is what makes
   the test meaningful - if NTP can reach this Pi at boot, it will
   silently paper over an RTC failure by re-correcting the system clock
   within moments, and you'd never know the RTC alone had failed.
   PirateBox's own visitor AP (`pb-ap`) does not provide this Pi with
   any time source either way, so only `eth0` needs to be pulled.
3. **Perform a genuine full power-off** - not just `sudo reboot`. Two
   safe options, either is fine:
   - `sudo poweroff` (or the existing physical hold-to-shutdown button
     - GPIO25, `docs/HARDWARE-INTEGRATION-DESIGN.md` §2) and wait for
     it to fully halt, **then physically disconnect the power supply**
     (unplug at the wall or the Pi's power input) - this is the step
     that actually removes power from the 3.3V rail the RTC module
     shares; a halted-but-still-plugged-in Pi may not be a clean test.
4. **Leave it fully unpowered for a meaningful duration** - at least
   10-15 minutes, longer (an hour+) is a stronger proof. A few seconds
   only shows "didn't instantly reset," not genuine timekeeping.
5. **Reconnect power, but leave `eth0` unplugged**, and let the Pi boot
   normally.
6. **Immediately after boot - before plugging `eth0` back in - check,
   in this order** (so NTP cannot hide an RTC failure by correcting
   things before you look):
   - `dmesg -T | grep -iE 'rtc|ds3231|ds1307'` - look for the bind
     line's reported time. **Success looks like a plausible time close
     to what you'd expect given how long the Pi was off** (your Step 1
     timestamp plus the elapsed off-time). **Failure looks like
     `SET TIME!` and a ~2000-01-01 reported time again** - the exact
     signature from §7/this section's own live re-verification, this
     time with no NTP available to quietly fix it.
   - `timedatectl status` - with `eth0` still unplugged, expect
     `System clock synchronized: no` (confirms NTP genuinely had no
     path, so whatever time is showing came from the RTC, not the
     network) and a `Universal time` consistent with the RTC having
     kept ticking through the outage.
   - `sudo hwclock -f /dev/rtc0 -r` - the direct, ground-truth read of
     the chip itself, same command the commissioning script itself
     trusts as ground truth.
7. **Only after recording all three of the above**, reconnect `eth0`
   and let NTP resync normally (harmless at this point - the evidence
   is already captured).

**This section documents the procedure only.** No power-off was
performed or requested as part of this round's work - per instruction,
that stays a genuine, separate operator action.

## 9. First power-loss test FAILED - root-cause diagnosis (2026-09-07, same day)

**The operator performed §8's exact procedure.** Ethernet disconnected
first, a genuine full power-off (not just a reboot), a real off period,
then powered back on with Ethernet still disconnected. Result: **the
system date/time came back around 1999**, and time-dependent behavior
was wrong until Ethernet was reconnected and NTP corrected it. Per
instruction, this is treated as evidence the battery backup is **NOT
validated** - not papered over by NTP correcting it afterward, and not
assumed fixed just because the module is detected while Pi-powered.

**Diagnosis performed - everything gathered without root first, since
this was still the same boot as the failed test** (`uptime -s`
confirmed it): `dmesg -T` for this exact boot showed:

```
rtc-ds1307 1-0068: SET TIME!
rtc-ds1307 1-0068: registered as rtc0
rtc-ds1307 1-0068: setting system clock to 2000-01-01T00:00:25 UTC (946684825)
```

**What this rules out:** the overlay/driver/boot configuration is
confirmed correct - `dtoverlay=i2c-rtc,ds3231` is still in
`/boot/firmware/config.txt`, the driver bound successfully
(`registered as rtc0`), and `CONFIG_RTC_HCTOSYS` successfully read the
chip and set the system clock from it. This was **not** a software
init failure, a missed overlay, or a driver problem - the kernel did
exactly what it should with whatever the chip actually reported.

**What this points to:** the value the chip reported was not corrupt
or random - it was the *exact same clean factory power-on default*
(`SET TIME!` + `2000-01-01T00:00:25 UTC`) seen during this same
module's very first-ever bring-up in §8, before it had ever held a
battery. A chip that had kept advancing time on a working CR2032 would
report a plausible, advancing date - not reset cleanly back to zero.
**This is strong, specific evidence that the DS3231 itself lost time
across the power-loss test - i.e., VBAT backup was not actually
effective during the outage - rather than a case of the RTC correctly
retaining time but the system failing to read/apply it.**
Corroborating detail: 2000-01-01T00:00:25 UTC converts to
1999-12-31 ~16:00/17:00 America/Los_Angeles - an exact match to the
operator's own "around 1999" observation, not merely a rough one.

**Two more pieces of evidence still needed (root-only, not yet
captured as of this writing) before the diagnosis is complete:** a
direct `hwclock -f /dev/rtc0 -r` (ground truth, compared against the
now-NTP-corrected system time) and `hwclock -f /dev/rtc0 --vl-read`
(the chip's own oscillator-stop/voltage-low flag - if set, that is the
chip's own internal confirmation that it detected a genuine loss of
both power rails, independent corroboration of the dmesg evidence
above). New **read-only** diagnostic script, deliberately incapable of
writing to the RTC (see its own tests):

```
sudo tools/diagnose_rtc_ds3231.sh
```

This captures all of the above (system time, direct RTC read, VL flag,
boot dmesg, config, device node, I2C bus/OLED regression, uptime) in
one pass, without writing anything - evidence is preserved before any
recommissioning is attempted, per instruction.

### Leading hypothesis and what would confirm or rule it out

Given R4's removal only touches the VCC→battery *charging* path, a
correctly-designed board should still connect the battery holder's
positive terminal to the DS3231's VBAT pin directly, unaffected by
that removal. The leading hypotheses, in rough order of likelihood,
none confirmed yet:

1. **Bad contact between the CR2032 and the holder** - not fully
   seated, dirty/oxidized contact, or a holder spring that isn't making
   reliable contact once Pi power (and whatever slight pressure/heat
   handling occurred during the R4 rework) is factored in.
2. **Battery inserted with reversed polarity** - would read plausible
   voltage with a meter across the holder in some conditions but not
   actually deliver correct polarity to VBAT.
3. **This specific clone board's layout routes the battery holder's
   positive terminal only through the same node R4 was part of**,
   rather than via a separate direct trace to VBAT - on some cheap
   DS3231 modules the "charge path" and "battery supply path" are less
   cleanly separated than the standard reference design assumes, and
   removing R4 could have inadvertently opened the *only* path from
   the holder to VBAT, not just the charging trickle. This would
   explain every symptom observed: perfectly normal behavior whenever
   Pi power is present (VBAT irrelevant while VCC is up), yet a clean
   loss of time the instant VCC drops.
4. **A weak/marginal CR2032 cell** - reads plausible open-circuit
   voltage on a meter but can't sustain the DS3231's (very small, but
   nonzero) current draw. Less likely to produce a *clean* factory-
   default reset rather than a slowly-drifting/partially-wrong time,
   but not ruled out without swapping in a cell of known-good condition.

### Physical measurements requested from the operator (voltage only - no current/load/short test on the cell)

A standard multimeter voltage measurement draws negligible current and
is not the kind of battery test being avoided - only a deliberate
load/short/current test on the cell itself is out of scope here, and
none of the following is that.

**Measurement A - across the battery holder terminals, CR2032 installed:**
Red probe on the holder's (+) contact, black probe on the holder's (-)
contact (or any convenient GND point) - the same two points measured
empty in §8, now with the cell in place.
- **With Pi powered ON:** record the reading.
- **With Pi fully powered OFF and unplugged** (a brief power-down is
  enough for this measurement - no extended soak needed yet): record
  the reading. **This is the single most diagnostic number.** A
  healthy, properly-connected CR2032 should read close to its rated
  ~3.0V in *both* conditions, since the holder terminals are directly
  the battery's own terminals - if this drops to near 0V specifically
  when Pi power is removed, the battery is not the limiting factor
  (the cell is fine) but something about how it's wired in is.

**Measurement B - directly at the DS3231 IC's VBAT pin, if you're
comfortable locating it (optional, but the most conclusive single
check for hypothesis 3 above):** On the standard DS3231 SOIC-8
package, pin 1 is marked with a small dot or notch on the chip body;
counting around, **pin 3 is VBAT** and **pin 4 is GND** (adjacent to
it). Measure VBAT (pin 3) relative to GND (pin 4, or any other GND
point on the board):
- **With Pi powered ON:** record the reading.
- **With Pi fully powered OFF and unplugged:** record the reading.
If Measurement A (holder terminals) reads good battery voltage in both
conditions but Measurement B (the chip's actual VBAT pin) reads ~0V
with Pi power off, that pinpoints a broken/never-connected trace
between the holder and the chip - consistent with hypothesis 3 - as
the exact root cause, independent of the battery or its seating.

**Do not perform another full multi-hour power-loss test yet.** Take
these measurements first (Measurement A requires only a brief,
controlled power-down, not a soak) - re-running the full validation
test without first understanding why it failed would very likely just
reproduce the same failure and cost another battery-and-time cycle
without new information. Once the measurements point to a specific
fix (reseat/re-orient the battery, or a rework of the VBAT trace, or a
known-good replacement cell), that physical fix should happen first,
*then* recommissioning (`sudo tools/configure_rtc_ds3231.sh` - safe to
re-run, already NTP-verified and idempotent) and only then a repeat of
the full §8 power-loss test to confirm the fix actually worked.

**Not done this round, deliberately:** no recommissioning write was
performed - per instruction, evidence is preserved first. No config,
overlay, or script logic was changed in response to this failure,
since nothing gathered so far points to a software cause to fix -
`tools/configure_rtc_ds3231.sh` already behaved correctly (it wrote a
good time before the test; the test's whole point was checking whether
that time survived a real power-off, which it did not). No second
power-loss test was performed or requested.
