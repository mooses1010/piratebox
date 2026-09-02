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

**Still true, unchanged by Field Tools (Post-Stage-32):** no hardware
RTC or `fake-hwclock` has been installed since this audit - the DS3231
remains **planned, not installed**. What did change: this audit's own
live checks (`/sys/class/rtc/`, the NTP-synchronized flag) are now also
surfaced to visitors, honestly, on the live site itself -
`includes/fieldtools_time.php`'s `piratebox_get_time_source_status()`
and `/utility/fieldtools/time/` - and named in `docs/PHYSICAL-CONTROL-
UX-DESIGN.md`'s OLED Clock page spec as what that future page should
read too. See `docs/FIELD-TOOLS-DESIGN.md` §4 for that design. Nothing
in this document's own findings needed correcting.

---

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
