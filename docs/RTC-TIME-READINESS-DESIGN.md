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
