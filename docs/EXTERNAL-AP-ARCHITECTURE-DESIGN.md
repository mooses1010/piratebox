# External AP Architecture + Production Migration Readiness

**Status banner:** this document describes an **architecture and
migration-readiness design**, produced during the External AP
Architecture + Production Migration Readiness Round (2026-09-03),
immediately after the AWUS036ACM Hardware Validation Round confirmed
the adapter's hardware/driver/AP-association capability. Read that
distinction literally:

**VALIDATED HARDWARE ≠ PRODUCTION MIGRATION COMPLETE.**

As of this document, `wlan0` (the onboard Raspberry Pi radio) **remains
the production PirateBox AP.** Nothing in this round switched it. The
staged code, config, and scripts referenced throughout are committed to
the repository for review but are **not installed, not enabled, and
not executed** against live production - see each section's own "Live
state" note. The one explicit exception is `piratebox_status_helper.sh`
and `includes/capability_state.php`, whose changes are backward
compatible by construction (see "Connection statistics" below) and may
be deployed without changing any observable production behavior; the
rest of this document is design plus staged, unexecuted artifacts.

---

## 1. Current network stack audit

Full audit performed against both the repository and live system state
(2026-09-03). Every `wlan0` occurrence found, classified:

| Location | Classification | Notes |
|---|---|---|
| `etc/hostapd/hostapd.conf:1` (`interface=wlan0`) | **production-radio identity** | The literal AP binding. Migration target. |
| `etc/dnsmasq.conf:1` (`interface=wlan0`) | **production-radio identity** | DHCP/DNS binding for the visitor subnet. |
| `etc/dhcpcd.conf:46` (`interface wlan0`, static `10.0.0.1/24`) | **production-radio identity** | Where `10.0.0.1` actually lives. |
| `piratebox_status_helper.sh` (`iw dev wlan0 station dump`) | **production-radio identity** | Fixed this round - see "Connection statistics". |
| `installer_pi_zero_trixie.sh` (multiple) | **production-radio identity, installer-scoped** | The fresh-install path for a wlan0-based PirateBox. Left as-is - a future external-AP install path is a distinct, not-yet-written installer flow, not a retrofit of this one. |
| `etc/systemd/system/hostapd.service.d/override.conf:5` | **harmless display/historical** | A comment explaining a past hostapd hard-kill bug; not a binding. |
| `piratebox_oled_daemon.py` (`HOSTAPD_CONF` path) | **not an interface reference at all** | Reads `/etc/hostapd/hostapd.conf` by *path* to parse the SSID - stable regardless of which interface that file's `interface=` line names. No change needed. |
| `var/www/html/includes/capability_state.php` (`ap_network`) | **not an interface reference at all** | Already keyed on `hostapd`/`dnsmasq` *service* activity, not an interface name. No change needed for that part; extended this round with provider detail (see below). |
| `var/www/html/public/**` (status/admin pages) | **not an interface reference at all** | All consume `wifi_clients`/service booleans from `status.json`, never touch an interface name directly. |
| `docs/**` | **historical/documentation** | Out of scope for this audit pass; updated separately where this round's decisions change what they should say (this file, `CAPABILITY-REGISTRY.md`, `IMPLEMENTATION-ROADMAP.md`, `OPERATIONAL-DECISIONS.md`). |

**No nftables/firewall configuration exists in this project at all** -
confirmed by search; PirateBox's network isolation is DHCP/DNS-scope
only (no visitor subnet routing to WAN exists to firewall off). Nothing
to audit or migrate there.

**Key finding that simplified everything downstream:** exactly **one**
place in the entire codebase does a raw `iw dev <iface> station dump` -
`piratebox_status_helper.sh`. Every other consumer (OLED, admin page,
status page, `capability_state.php`, `metrics.php`) reads the resulting
`wifi_clients` integer from `status.json`, never an interface name.
Fixing the one real place fixes everything transitively - see
"Connection statistics".

---

## 2. Stable ALFA identity

**Do not trust `wlan1` as identity** - confirmed necessary: this Pi's
enumeration already showed the ALFA can land on different `wlanN`
numbers depending on what else is plugged in and when (the AWUS036ACM
Hardware Validation Round found `wlan1`; an earlier round's TL-WN722N
V2 also used `wlan1` before it was unplugged).

**Mechanism chosen: udev, matched on driver + USB VID:PID, naming it
`pb-ap`.** Staged at
`etc/udev/rules.d/99-piratebox-external-ap.rules` (not installed):

```
SUBSYSTEM=="net", ACTION=="add", DRIVERS=="mt76x2u", ATTRS{idVendor}=="0e8d", ATTRS{idProduct}=="7612", NAME="pb-ap"
```

**Why VID:PID+driver, not USB serial:** the AWUS036ACM's own USB
descriptor reports a generic/blank serial number (`000000000`, per
`udevadm info` during the Hardware Validation Round) - not a usable
per-unit identifier. Matching the chipset is the only stable property
actually available.

**Replacement-unit question, answered:** if this exact ALFA dies and is
replaced with another AWUS036ACM, **the replacement automatically
qualifies** - same VID:PID, same driver, same rule match, no operator
action needed. This was a deliberate choice, not an oversight: the
project's own instruction not to overengineer a generic hardware-
plugin framework, combined with the fact that no better per-unit
identity exists for this hardware, made "trust the chipset, not a
device serial" the only practical option. The accepted tradeoff: this
rule would rename *any* MT7612U-chipset adapter using the `mt76x2u`
driver plugged into this Pi, not literally this physical unit - judged
acceptable because this is single-purpose deployed hardware (not a
shared desktop where a coincidental second MT7612U device is a
realistic scenario), and restricting the match to the specific
`mt76x2u` kernel driver (not just any driver claiming that VID:PID)
avoids misfiring on an unrelated device that merely shares a MediaTek
USB ID range under a different driver.

**Privacy distinction, addressed explicitly per instruction:** this is
the PirateBox operator's own AP hardware, named for the appliance's
internal bookkeeping - conceptually unrelated to the project's existing
rule against persisting *visitor* MAC addresses (`docs/
DEVICE-MEMORY-DESIGN.md`). No client/visitor identifier is touched by
this mechanism, and this document does not record the ALFA's own
transient MAC anywhere (per the Hardware Validation Round's same
discipline).

**Live state:** not installed. `ip link show pb-ap` currently fails
(confirmed at design time - no such interface exists until this file
is copied to `/etc/udev/rules.d/` and the adapter replugged or the Pi
rebooted). Installing it is a migration-time step (see "Migration
plan").

---

## 3. Radio role model

Roles are defined as **capabilities**, not kernel interface numbers,
so future code never has to assume `visitor AP == wlan0`:

| Role | Today | Future (post-migration) |
|---|---|---|
| **Primary visitor AP** | onboard (`wlan0`) | external (`pb-ap`), if adopted |
| **Fallback visitor AP** | none (single-radio today) | onboard (`wlan0`), if `pb-ap` is absent/unhealthy at boot |
| **Management/scan radio** | none (Ethernet is management) | onboard `wlan0`, once freed from AP duty - **not implemented this round** |

This table is intentionally the entire "role model" artifact - no new
plugin framework, no generic device-discovery abstraction. The only
code-level manifestation of "role" that exists today is
`piratebox_status_helper.sh`'s live auto-detection of *whichever*
interface is actually in `type AP` state (see "Connection statistics")
- which already satisfies "reason about primary/fallback without
assuming wlan0 forever" for the one place that needed it. The
boot-time **selection** between primary and fallback is a separate,
staged mechanism (`tools/piratebox_radio_select.sh`, next section) -
kept deliberately unconnected to any actual radio bring-up this round.

**Not implemented this round, per instruction:** home/away detection
for Travel Mode using the onboard radio as a scanner, diagnostics use
of the freed onboard radio, or any code that assumes the onboard radio
is available for anything beyond its current AP duty. These remain
documented future uses of "management/scan radio," not built.

---

## 4. Boot fallback design and runtime-failure decision

**Boot-time selection: designed and staged**, not enabled -
`tools/piratebox_radio_select.sh`. Logic: if `pb-ap` exists and is not
rfkilled, decide `external`/`pb-ap`; otherwise decide
`onboard`/`wlan0`. Writes a small JSON decision record to
`/run/piratebox/radio-selection.json` (tmpfs, recomputed fresh every
boot). **Deliberately does not itself touch hostapd/dnsmasq/dhcpcd** -
deciding and applying are kept as two separate steps (the same
preview-then-apply discipline `piratebox_deploy.sh --dry-run` already
uses), so a future "apply" step can be reviewed and gated on its own
merits rather than folded into a boot-time script that's harder to
safely dry-run. Verified against live state during this round: with no
`pb-ap` present, it correctly decides `onboard`/`wlan0`, matching
current production exactly.

**Runtime disappearance: explicitly NOT automated this round.**
Per instruction ("if automatic runtime fallback is substantially
riskier than boot-time fallback, it is acceptable to implement robust
boot selection now and document runtime fallback as a later stage") -
that is the call made here. Reasoning:

- **Detection without busy-looping** is achievable cheaply (a udev
  `remove` rule or a periodic check against the existing 30s
  `piratebox-status.timer` cadence - no new polling loop needed).
- **Automatic bring-up of a second AP/DHCP instance while the first is
  still shutting down** is the real risk - two `hostapd`/`dnsmasq`
  instances racing for `10.0.0.1` is exactly the kind of conflict the
  instructions call out by name, and doing it safely needs stable-state
  validation (confirm the old radio is *actually* gone, not just
  transiently reset) before flipping - which in turn needs the same
  kind of soak-testing discipline as the power-aware gate below, not a
  boot-time script's worth of logic.
- **Flapping** is the specific failure mode a marginal USB connection
  (this Pi's own already-observed one-time insertion disconnect) could
  trigger if runtime fallback were naive - repeatedly tearing down and
  recreating the visitor AP as a flaky adapter resets is worse for
  visitors than staying degraded on one radio until the next boot.

**Recorded here as a deliberate scope decision, not an oversight:**
runtime automatic fallback is a **later stage**, to be designed with
its own soak evidence once boot-time selection has real production
experience behind it. Until then, an adapter disappearing at runtime
leaves PirateBox on whichever radio was already active (DEGRADED
`ap_network` capability state if that radio itself failed, `AVAILABLE`
if only the *other*, inactive radio was affected) - visible via the
capability/admin state this round already added, actionable by a human
rebooting or running the staged rollback script, not by an unattended
automatic transition.

---

## 5. NetworkManager / ownership

**Confirmed live during the Hardware Validation Round:** `wlan1` (the
ALFA, pre-udev-rename) showed up as NetworkManager-managed by default
(state `unavailable`, no active connection) - not excluded the way
`wlan0` is. It was only *not* touched because NetworkManager's own wifi
radio switch (`nmcli radio wifi`) happened to be globally `disabled`
throughout that round - correctly flagged there as "not a sufficient
production guarantee."

**Fix, staged:** `etc/NetworkManager/conf.d/99-piratebox.conf`, now
tracked in the repo for the first time (it existed live-only,
untracked, throughout the project's history until this round - see the
file's own provenance comment), extended from:

```
unmanaged-devices=interface-name:wlan0
```

to:

```
unmanaged-devices=interface-name:wlan0;interface-name:pb-ap
```

Excluding `pb-ap` **now, ahead of any migration**, is deliberate: a
regulatory-domain fix (next section) would re-enable NetworkManager's
wifi radio switch as a side effect (`raspi-config`'s
`do_wifi_country` calls `nmcli radio wifi on` when NetworkManager is
the active stack, which it is here) - having the exclusion already
staged means that re-enable, whenever it happens, opens no new exposure
window for `pb-ap` to be claimed.

**If onboard `wlan0` is later repurposed** (management/scanning, after
a migration), this file's continued exclusion of it should be
revisited deliberately at that time - not assumed either way, and
noted as such in the staged file's own comments.

**Global wifi radio toggle:** not touched this round. `nmcli radio
wifi` remains `disabled` live, exactly as found during hardware
validation - re-enabling it is bundled with the regulatory-domain fix
below, an explicit operator action, not something toggled casually
here.

**Live state:** the staged file is **not yet copied** to
`/etc/NetworkManager/conf.d/99-piratebox.conf` - the live file there
still has only the `wlan0` line. Installing the staged version is a
migration-time step (or can reasonably be done independently/earlier,
since it's a pure addition with no observable effect until `pb-ap`
exists - see "Migration plan").

---

## 6. Regulatory domain / 2.4 vs 5GHz

### Finding: a pre-existing, unrelated misconfiguration

Investigating "what mechanism sets the regulatory domain on this
system" turned up something this round did not expect and did not
introduce: **`/boot/firmware/cmdline.txt` already contains
`cfg80211.ieee80211_regdom=UM`** - not `US`. `UM` is a real ISO 3166-1
alpha-2 code (*United States Minor Outlying Islands*), confirmed
present in `/usr/share/zoneinfo/iso3166.tab`, but **not** present in
`wireless-regdb`'s actual regulatory database (confirmed via
`hexdump`) - so the kernel silently finds no matching ruleset for it at
boot and falls back to the generic `world`/`00` domain, which is
exactly the `country 00: DFS-UNSET` state observed throughout the
Hardware Validation Round (explaining why every 5GHz channel showed
`(no IR)` and no 5GHz test was possible). Confirmed this is not
currently taking effect via `dmesg`: the kernel command line shows the
parameter verbatim, but `iw reg get` still reads `country 00`.

This is reported, not silently corrected - it predates this round
(found in live boot config, not written by anything this round did)
and is a boot-configuration change, squarely in the "stops for the
operator" category regardless of how small the fix is.

### The correct, standard mechanism on this system

Verified directly against this Pi's actual `raspi-config` (not assumed
from general knowledge) - `do_wifi_country()`:

1. Persists via the kernel command line:
   `cfg80211.ieee80211_regdom=<CC>` in `/boot/firmware/cmdline.txt`
   (the pre-existing, mistyped mechanism above - just needs the one
   character fixed).
2. Applies immediately, live: `iw reg set <CC>`.
3. `wpa_cli ... set country` only runs if `dhcpcd` is active - **not
   applicable here** (this system uses NetworkManager, and hostapd's
   AP-mode interfaces don't use `wpa_supplicant` at all - confirmed no
   `/etc/wpa_supplicant/wpa_supplicant.conf` exists).
4. If NetworkManager is active (it is, here): `nmcli radio wifi on` -
   a real, confirmed side effect of running this, relevant to the
   NetworkManager section above.

### Exact operator-gate commands

Either of these is standard, minimal, and does not require installing
anything (`wireless-regdb` is already present):

```bash
# Simplest, does the whole standard flow (including the nmcli re-enable
# noted above):
sudo raspi-config nonint do_wifi_country US

# Equivalent by hand, if the nmcli side effect is unwanted right now:
sudo sed -i 's/cfg80211.ieee80211_regdom=UM/cfg80211.ieee80211_regdom=US/' /boot/firmware/cmdline.txt
sudo iw reg set US
```

Neither of these was run by this session. **Stopped here, per
instruction, with exact commands** - this is an operator action.

### Resolved: Regulatory Domain Correction + ALFA Post-Regulatory Validation Round (2026-09-03)

The operator ran `sudo raspi-config nonint do_wifi_country US`.
Independently verified, not trusted from the command's exit status:

- `/boot/firmware/cmdline.txt` correctly updated to
  `cfg80211.ieee80211_regdom=US` - the persistent half worked.
- `nmcli radio wifi` became `enabled` (the documented side effect) -
  harmless, since `pb-ap` didn't exist yet to be exposed and `wlan0`
  stayed excluded throughout - **a real-world confirmation that staging
  the `pb-ap` NetworkManager exclusion ahead of time (see
  "NetworkManager ownership" above) was the right call**, not
  theoretical caution.
- **The live-apply half did NOT work**, reproduced twice independently
  (once via `raspi-config`'s own internal `iw reg set US` call, once
  via a direct manual retry by this session immediately after): both
  returned success, neither changed `iw reg get`, which kept reading
  `country 00`. Ruled out as causes: rfkill (neither radio blocked),
  a missing/corrupt regulatory database (files present, correctly
  linked, no load-failure in `dmesg`), and a one-time timing fluke
  (reproduced twice, in different NetworkManager/rfkill states).

This meant the standard "one command, done" expectation didn't hold on
this system - a **reboot was genuinely required**, not merely
convenient, to exercise the boot-time application path (which runs at
`cfg80211` module init, before any of the state that was blocking the
live path existed). This session preserved recovery state
(`CURRENT-WORK.md`, deleted once this round closed) and confirmed
Ethernet management access before asking for it, per instruction.

**After the reboot, independently re-verified:** `iw reg get` now
reads `global / country US: DFS-FCC` - a genuine FCC ruleset, not the
world fallback. The reboot itself was clean: single clean ALFA
enumeration (no disconnect/reconnect cycle, unlike the very first
hot-plug insertion event recorded in the Hardware Validation Round),
zero new SD/USB errors, `vcgencmd get_throttled` unchanged at `0x50005`
(the same known pre-existing condition), production `wlan0` came back
healthy with all six services active.

**Actual measured ALFA capabilities under the corrected domain**
(`iw phy0 info` - phy numbering itself shifted across the reboot, from
`phy#3` to `phy#0`, while the `wlan0`/`wlan1` interface *names* held
stable this particular reboot - a live reminder of exactly the
enumeration fragility the staged `pb-ap` udev rule exists to close):

- **2.4GHz:** channels 1-11 permitted (23 dBm); channels 12-14 now
  genuinely `disabled` (not merely `no IR` as under world/00) - correct
  US behavior. HT20/HT40, MCS 0-15, unchanged from before.
- **5GHz, non-DFS (legal to transmit on immediately):** **36, 40, 44,
  48** (UNII-1) and **149, 153, 157, 161, 165** (UNII-3), all 20 dBm,
  no radar-detection or no-IR flags.
- **5GHz, DFS-required:** 52-144 (UNII-2/2e), all flagged `(radar
  detection)` - correctly gated, not enabled by this round.
- **Not available under this ruleset:** 169/173/177, flagged `(no
  IR)` - outside what this domain permits to initiate radiation on.
- **VHT/2x2, confirmed genuine:** RX/TX MCS 0-9 on both 1 and 2
  streams, max channel width 80MHz (not 160/80+80) - the MT7612U's own
  ceiling, unchanged by the regulatory fix (a capability limit, not a
  regulatory one).

**Bounded isolated 5GHz AP test - performed, passed:** temporary
`hostapd` (config/PID in job tmp only, never `/etc/hostapd/`), SSID
`PirateBox-ALFA-5G-Test`, **channel 36** (a legal non-DFS choice, per
instruction never a DFS channel merely to prove DFS works), WPA2-PSK,
20MHz width. Reached `AP-ENABLED`. The operator's phone saw the SSID,
entered the password, and got the same generic "Couldn't connect to
network" message seen during the 2.4GHz test - and, per the lesson
already learned there, that wording was judged against the AP-side
evidence rather than taken at face value: `hostapd`'s own log shows
the client completing full authentication, association, and the
**WPA2 4-way handshake twice** (`EAPOL-4WAY-HS-COMPLETED`, two
attempts, matching the operator's own "re-attempted once to confirm"),
each followed by a client-side disconnect shortly after - the same
DHCP-timeout abort pattern as before, not an authentication or radio
failure. Zero new `mt76`/USB/SD errors across the entire test window;
`vcgencmd get_throttled` unchanged. Production `wlan0` confirmed
unaffected throughout and after. **DHCP was deliberately not added
this round either** - the 802.11/WPA2 question this test exists to
answer was already settled by the handshake evidence, and adding a
parallel DHCP responder was already established (Hardware Validation
Round) to require touching production `dnsmasq`'s shared socket or
installing new software - neither appropriate just to make a phone's
UI wording look nicer.

**Recommendation, this round: 5GHz AP capability is now legally and
technically VALIDATED on this hardware** (non-DFS channels 36-48 and
149-165) - **this does not change the production band strategy below.**

### 2.4 vs 5GHz production strategy

**Recommendation: 2.4GHz remains the default/primary band**, not
because 5GHz/ac is unavailable but because the actual production
constraints point the same direction as the project's own mission:

- **Phone compatibility & emergency/public accessibility**: PirateBox's
  stated purpose (an appliance meant to work for anyone nearby, not
  just people with recent hardware) favors the band every device
  supports, not just newer ones.
- **Range/penetration**: 2.4GHz's longer wavelength penetrates
  walls/obstacles better - relevant for "useful sitting at home, riding
  in a vehicle, carried in a backpack, or set up at an event" (this
  project's own stated use cases, `help.php`).
- **Pi USB2 bottleneck**: this Pi's USB2-480M ceiling (confirmed during
  hardware validation) already caps whatever throughput advantage
  802.11ac could offer - the genuine 2x2 VHT capability observed is
  real, but it cannot be fully exploited over this bus, undercutting
  "5GHz/ac is newer, therefore faster, therefore default."
- **Crowded spectrum** cuts both ways (2.4GHz is more crowded in dense
  areas; 5GHz has more clean channels but shorter range) - not treated
  as decisive either way here.

**5GHz's place: optional, not default - unchanged even now that it's
validated.** The Regulatory Domain Correction round proved real,
legal, working 5GHz AP capability on this hardware (non-DFS channels
36-48 and 149-165, genuine 2x2 VHT, a real client completing WPA2
association twice) - **VALIDATED 5GHZ CAPABILITY ≠ 5GHZ PRODUCTION
DEFAULT.** The reasoning above (phone compatibility, range/penetration,
emergency/public accessibility, the Pi's USB2 bottleneck already
capping whatever throughput advantage 802.11ac could offer) did not
change just because the regulatory blocker did. A future higher-
throughput or advanced-deployment profile is a legitimate future use of
this now-proven capability - but it remains an explicit alternate
profile an operator opts into, not something a migration silently
defaults to. **Production `wlan0`'s band/channel was not touched by
either round** - this stays purely a capability finding.

---

## 7. Antenna baseline

**Production candidate baseline: the two matching stock ALFA dual-band
antennas** - unchanged from the Hardware Validation Round, which used
exactly this pair for its successful AP/association testing. This
round adds nothing here and changes nothing about that baseline.

**The ARS-N19 stays explicitly out of the baseline**, for the reasons
already on record (`docs/CAPABILITY-REGISTRY.md`): it is 2.4GHz-only,
there is only one of it, and it is not a matched 2x2 pair for this
adapter's genuine 2x2 MIMO capability. Using it would silently degrade
the adapter to effective 1x1 operation on one path - a real capability
loss, not a neutral swap. **Not tested this round**, per instruction.

**How future antenna experiments should be run, so they don't get
confused with radio/driver changes**: any antenna swap should be
treated as its own isolated variable - re-run the same soak/association
test this and the Hardware Validation Round already established
(`PirateBox-ALFA-Test`-style isolated SSID, not production) with only
the antenna changed and everything else (driver, config, channel) held
identical, so a difference in outcome can be attributed to the antenna
specifically. **No passive RF Y-splitting** - explicitly ruled out per
instruction; a Y-splitter is not a substitute for a genuine matched 2x2
pair and introduces its own loss/mismatch that would confound any such
test anyway.

---

## 8. Power-aware production migration gate

The known `0x50005` condition (`under-voltage detected now` +
`throttled now` + both `...since boot`) is **not solved and not
attempted this round** - it predates the ALFA, was observed identical
before the adapter was ever connected (post-power-outage recovery), and
remains exactly the same value throughout every check performed during
both this round and the Hardware Validation Round, including under live
AP-beaconing and WPA2-association load. The one ALFA-correlated event
on record - a single insertion-time USB disconnect/re-enumeration,
coincident with one SD-card I/O error and one USB host-controller
timeout - did not repeat across the rest of that round's testing
(association attempts, teardown, this round's design work).

**This is architectural work, not blocked on power being fixed** - per
instruction. But before trusting the ALFA as a **24/7 production** AP
(as opposed to a proven-capable, short-supervised-test AP, which is
what's actually been validated so far), the following evidence should
exist and does not yet:

**Proposed validation gate, for a later stage - not run this round:**

1. **Extended soak**, order of hours not seconds/minutes (the Hardware
   Validation Round's soak was on the order of tens of minutes total,
   including beaconing and association testing - informative, not
   exhaustive).
2. **Multiple simultaneously-associated clients** (validated so far:
   sequential single-client association, never concurrent).
3. **Sustained local traffic** (file transfer / chat use, not just
   idle beaconing + a brief association) - deliberately **not**
   framed as an "aggressive stress test" per instruction; ordinary
   PirateBox visitor traffic levels are the right target, not a
   synthetic saturation test on a known-marginal supply.
4. **Continuous kernel USB error monitoring** across that whole window
   (`dmesg`/`journalctl -k`, watching specifically for `mt76`/`1-1.x`
   reset or disconnect messages - the same method already established
   and used twice this project).
5. **`vcgencmd get_throttled` transition tracking** across the window -
   not just a point-in-time read, but whether new bits ever set beyond
   the already-known `0x50005` baseline (e.g. a fresh
   under-voltage-since-this-check event correlated with AP load, which
   has not yet been observed but also hasn't been tested for under
   sustained multi-client load).
6. **SD/MMC error monitoring** (`dmesg` for `mmcblk0` I/O errors) -
   because the one insertion-time event this project has on record
   showed a *cross-subsystem* correlation (USB WiFi + SD card at the
   same instant), any future evaluation should keep watching both, not
   just the adapter.
7. **Adapter reset count**: zero new resets across the entire soak
   window is the bar, not "resets happened but recovered."

**Do not run this gate automatically** - it requires deliberate,
supervised execution (a human present to abort if something looks
wrong, per the existing "do not stress-test aggressively on a
known-undervolting Pi" instruction), and should happen either after the
power supply is separately improved, or as a deliberately-accepted,
explicitly-flagged test on the current supply - not silently treated as
equivalent to a healthy-power result either way.

---

## 9. Status / OLED / admin implications

**Audit result: the OLED daemon needed zero changes.** It already
reads the SSID from `/etc/hostapd/hostapd.conf` by *file path*, not by
interface name, and reads client count from `status.json`'s
`wifi_clients` field, not from a direct `iw` call - both already
provider-agnostic. **The OLED's visual design is unchanged, per
instruction** - nothing here redesigns it.

**What was added: `ap_network.detail.provider`** in
`includes/capability_state.php`'s live capability state - a new pure,
tested classification (`piratebox_classify_visitor_ap_provider()`)
that reports:

- `state`: `AVAILABLE` / `DEGRADED` / `UNKNOWN` (never a fabricated
  healthy state, matching this file's existing vocabulary discipline).
- `label`: e.g. `"onboard Wi-Fi (wlan0)"` or `"external AWUS036ACM
  (pb-ap)"` - or `"multiple AP-mode interfaces detected - unsupported
  configuration"` if the (currently theoretical, not currently
  possible) two-radios-both-AP-mode state is ever seen live.

This is admin-page-reachable detail (`capability_state.php` already
distinguishes public-safe summary vs. operator-level detail per its own
header) - **public UI is unchanged**, since hardware provider identity
isn't useful information for an anonymous visitor. Today, live, this
always classifies to `onboard`/`wlan0` - no behavior change yet, since
production hasn't migrated.

---

## 10. Connection statistics

**The fix turned out to be entirely contained in one file.** Since
`piratebox_status_helper.sh` was the only place doing a raw interface-
named `iw dev wlan0 station dump`, and every downstream consumer
(OLED, admin, status page, `capability_state.php`, `metrics.php`) only
ever reads the resulting `wifi_clients` integer from `status.json`,
fixing that one call site fixes the whole chain with no other file
needing to change.

**Mechanism: live auto-detection, not a config flag to keep in sync.**
Every poll, the script now asks the kernel directly (`iw dev`) which
interface (if any) is currently in `type AP` state, and queries
*that* one - rather than trusting a separate "which radio is active"
setting that could drift from reality. Verified live during this round:
resolves to exactly `wlan0` today, byte-identical to the previous
hardcoded behavior. Handles the "more than one AP-mode interface"
anomaly (not a supported configuration, but not silently ignored
either) by preferring `pb-ap` if present among them and setting a new
`multiple_ap_interfaces_warning` flag, surfaced through to the
capability state above.

**Privacy guarantees, unchanged and re-verified against this specific
diff:**
- Current associations still come from live state only (`iw dev
  $IFACE station dump`) - the interface name is the only thing that
  became dynamic; the privacy-relevant logic (raw MAC list held only in
  a tmpfs scratch file, immediately overwritten, never logged) is
  untouched.
- Persistent storage remains small integer counts only
  (`connection-stats.json`'s hourly buckets) - this round added no new
  persistent field, only a live `status.json` block
  (`visitor_ap.interface`/`.provider`) that is itself tmpfs-only,
  regenerated every 30s, matching the rest of that file.
- No MAC/IP/hostname/UA persisted - unchanged.

**Live state:** the repo copy of `piratebox_status_helper.sh` has this
change; the **live installed copy at `/usr/local/bin/
piratebox_status_helper.sh` does not yet** (that file is a manually-
reinstalled root-owned copy, same category as nginx - see
`docs/OPERATIONAL-DECISIONS.md` "Claude deployment/mode-switch
automation"). Because this change is backward-compatible by
construction (verified: resolves to `wlan0` against live state
unchanged), reinstalling it is low-risk, but was **not done this
round** - staying consistent with treating any live root-owned script
install as an operator-gated action, not something this session does
unilaterally just because a change happens to be safe. Exact reinstall
command, when wanted:

```bash
sudo cp piratebox_status_helper.sh /usr/local/bin/piratebox_status_helper.sh
sudo chmod +x /usr/local/bin/piratebox_status_helper.sh
```

---

## 11. Captive portal / DHCP / DNS implications

**Audited, and the news is good: nothing here needs a second
implementation.** `dnsmasq.conf`'s wildcard DNS (`address=/#/10.0.0.1`,
`no-hosts`), the CAPPORT `dhcp-option=114` advertisement, and the
`interface=` binding are the *entire* mechanism - none of it references
`wlan0` beyond that one `interface=` line, and nginx/PHP's captive-
portal handling (`/.well-known/captive-portal`, the legacy HTTP-probe
paths) is interface-agnostic by construction (it's all HTTP-layer,
served the same way regardless of which radio delivered the visitor's
packets to `10.0.0.1`).

**The one real coupling**: `dnsmasq.conf`'s `interface=wlan0` and
`dhcpcd.conf`'s `interface wlan0` / `10.0.0.1/24` static assignment -
both are exactly what `tools/migrate_visitor_ap_to_alfa.sh` changes
(the `dnsmasq.conf` line) or leaves alone (`dhcpcd.conf`'s `10.0.0.1`
assignment is **not** touched by the staged migration script - `10.0.0.1`
stays defined against `wlan0` in `dhcpcd.conf`; only `hostapd`/
`dnsmasq`'s *radio* binding changes. See that script's own comments for
why this is sufficient: `dhcpcd.conf`'s `interface wlan0` block exists
to give `wlan0` its static IP and `nohook wpa_supplicant` - a future
migration that fully retires `wlan0` from AP duty would need to
reconsider this, but the current staged migration keeps `wlan0` up and
idle, not retired, so this is intentionally left alone this round).

**No captive portal, nginx, or firewall change of any kind is needed
for a radio migration** - confirmed by this audit, not assumed.

---

## 12. Migration plan

### Preflight
- Ethernet management path confirmed up (`eth0`).
- Known-good `main` checkpoint identified (currently `9d573f6`, this
  round's own starting point).
- `pb-ap` detected, driver confirmed `mt76x2u`.
- Regulatory domain confirmed correct (not `00`/world) - see the
  `UM`→`US` fix above.
- NetworkManager exclusion for `pb-ap` confirmed installed.
- Power state recorded (`vcgencmd get_throttled`, current dmesg
  baseline) - see "Power-aware migration gate."
- Production `hostapd.conf`/`dnsmasq.conf` backed up.

All of the above are encoded as hard preflight checks in
`tools/migrate_visitor_ap_to_alfa.sh` (staged) - it refuses to proceed
if any fail, and additionally requires an explicit environment-variable
confirmation plus an interactive `migrate` prompt, so it cannot run by
accident.

### Migration (what the staged script actually does, if run)
1. Stop `hostapd`/`dnsmasq`.
2. Change `interface=wlan0` → `interface=pb-ap` in both
   `/etc/hostapd/hostapd.conf` and `/etc/dnsmasq.conf` - the **only**
   lines either file needs to change (see "Captive/DHCP/DNS" above).
3. Validate the resulting hostapd config.
4. Start `hostapd`/`dnsmasq` again.
5. Live-check: `pb-ap` reports `type AP`, both services active, a
   basic `curl` against `http://10.0.0.1/` responds.
6. `10.0.0.1`, dnsmasq's wildcard DNS/DHCP behavior, CAPPORT, nginx,
   the site itself, connection statistics, and status/OLED reporting
   all continue working unchanged - by design, none of them reference
   the interface name directly (see sections 9-11).

### Operator test
- SSID visible on a real device.
- Phone connects, gets a real DHCP lease this time (unlike the
  Hardware Validation Round's deliberately DHCP-less isolated test).
- `http://piratebox/` and `http://10.0.0.1/` both load.
- Captive-portal behavior triggers correctly.
- Chat/files/etc. function.
- Multiple simultaneous clients, if practical - this is also the
  operator's chance to contribute toward the power-aware gate's
  multi-client evidence requirement.

### Rollback
`tools/rollback_visitor_ap_to_onboard.sh` (staged): restores
`hostapd.conf`/`dnsmasq.conf` from the migration script's own backup
(or falls back to a direct `pb-ap`→`wlan0` line restore if no backup is
found), restarts both services on `wlan0`, and verifies AP/service
state plus a basic `curl` check - written to be simple enough to run
over Ethernet/SSH under pressure, matching the instruction directly.

---

## 13. Implementation boundary - what was and wasn't done

**Implemented and committed this round** (all backward-compatible /
non-production-affecting, detailed above):
- `etc/udev/rules.d/99-piratebox-external-ap.rules` (staged, not
  installed).
- `etc/NetworkManager/conf.d/99-piratebox.conf` (staged extension; the
  live file is untracked and still has only the `wlan0` line).
- `piratebox_status_helper.sh`: visitor-AP auto-detection +
  `visitor_ap` status block (repo updated; live reinstall not
  performed).
- `includes/capability_state.php`: `piratebox_classify_visitor_ap_
  provider()` + `ap_network.detail.provider` (deployable - pure PHP
  app code, no system file).
- `tools/piratebox_radio_select.sh` (staged, not enabled/wired to any
  systemd unit).
- `tools/migrate_visitor_ap_to_alfa.sh` / `tools/
  rollback_visitor_ap_to_onboard.sh` (staged, not executed).
- Tests (see below).
- This document, plus updates to `CAPABILITY-REGISTRY.md`,
  `IMPLEMENTATION-ROADMAP.md`, `OPERATIONAL-DECISIONS.md`.

**Explicitly not done, per instruction:**
- Production `hostapd` was not switched to the ALFA.
- `10.0.0.1` was not moved off `wlan0`.
- Live `dnsmasq` bindings were not altered.
- Production `wlan0` was not disabled.
- No permanent (or temporary) ALFA AP was enabled this round -
  correctly, since the previous round's isolated test AP was already
  torn down before this round began.
- The final migration was not performed.
- Regulatory domain was not changed live (exact commands documented,
  left for the operator).
- `piratebox_status_helper.sh`'s live reinstall was not performed
  (backward-compatible, but treated as an operator-gated system-file
  install regardless).

---

## 14. Testing

**Regression baseline preserved and extended**, run this round:

| Suite | Before this round | After this round |
|---|---|---|
| Full PHP regression (`tools/test_*.php`) | 305/305 | **313/313** (+8, all in `test_capability_state.php`) |
| Library catalog (`tools/check_library_catalog.py`) | 42/42 | 42/42 (unchanged - no content work this round, per instruction) |

**New deterministic tests, `tools/test_capability_state.php`** -
synthetic, no hardware/live `iw`/ALFA required, per instruction not to
falsify hardware tests in software:
- Helper unavailable → `UNKNOWN` regardless of other fields.
- Onboard `wlan0` active (today's real production state) → `AVAILABLE`,
  labeled onboard.
- External `pb-ap` active (future post-migration state) → `AVAILABLE`,
  labeled external.
- No AP-mode interface found at all → `DEGRADED`, never a fabricated
  `AVAILABLE`.
- Multiple AP-mode interfaces flagged → `DEGRADED`, with the specific
  "unsupported configuration" label.
- Malformed/missing provider string → `DEGRADED`, not a guessed
  `AVAILABLE`.
- Live capability state (`ap_network.detail.provider`) is present and
  always one of the real vocabulary values against this environment,
  right now.

**`piratebox_status_helper.sh`'s new detection logic** was verified
directly against live `iw dev` output during this round (not merely
inspected) - confirmed to resolve to exactly `wlan0`, matching current
production, before being committed. The full JSON output shape
(`visitor_ap` block) was validated for all four cases (onboard active,
external active, none found, multiple-warning) via `python3 -m json`
parsing of the exact heredoc logic used in the real script - not run
against live production paths, since that script also writes real
persistent operational data files
(`var/www/html/data/connection-stats.json`,
`var/www/html/data/device-history.json`) that this round did not want
to touch outside the normal 30-second production timer.

**Not tested (cannot be, honestly) this round:** anything requiring
the actual ALFA hardware live in AP mode (that adapter was correctly
torn down at the end of the Hardware Validation Round, before this
round began, and this round is explicitly architecture/staging, not a
continuation of hardware testing) - the synthetic tests above establish
the classification logic is correct; they do not and cannot claim
`pb-ap` itself was exercised this round.

---

## 15. Documentation / checkpoint

Updated this round: this document (new),
`docs/CAPABILITY-REGISTRY.md`, `docs/IMPLEMENTATION-ROADMAP.md`,
`docs/OPERATIONAL-DECISIONS.md`. `docs/HARDWARE-INTEGRATION-DESIGN.md`
was reviewed; its §2 wiring map covers GPIO/physical hardware, not
Wi-Fi radio architecture, so no change was needed there - this document
is the correct home for this round's content instead, matching the
project's existing per-subsystem-doc convention (`POWER-UPS-DESIGN.md`,
`TRAVEL-MODE-DESIGN.md`, etc.).

---

## 16. Regulatory Domain Correction + ALFA Post-Regulatory Validation Round (2026-09-03)

Follow-on round, immediately after this document's initial version.
**Corrected the regulatory domain and validated 5GHz capability -
production migration status is unchanged: `wlan0` remains the
PirateBox AP.**

**Regulatory domain: fixed, verified, understood.** The `UM`/`US`
boot-parameter typo this document originally reported is now corrected
(`sudo raspi-config nonint do_wifi_country US`, operator-run). This
session discovered and documented something the original finding
didn't know: the standard **live-apply** half of that fix (`iw reg
set`) is genuinely broken on this system - reproduced twice
independently, with rfkill, a missing regdb, and a timing fluke all
ruled out as causes. A **reboot** (not previously anticipated as
necessary) was required to exercise the boot-time application path,
which worked cleanly. Post-reboot, `iw reg get` correctly reads
`country US: DFS-FCC` - a real FCC ruleset, independently verified, not
inferred from the fix command's exit status. See "Resolved: Regulatory
Domain Correction..." under "Regulatory domain" above for the full
evidence chain.

**5GHz capability: validated, not defaulted-to.** Full channel mapping
performed under the corrected domain (non-DFS 36-48 and 149-165, DFS
52-144, genuine 2x2 VHT up to 80MHz). A bounded, isolated, temporary
5GHz AP (`PirateBox-ALFA-5G-Test`, channel 36, non-DFS per instruction)
reached `AP-ENABLED`, and a real client completed the WPA2 4-way
handshake twice, judged from `hostapd`'s own log rather than the
phone's generic "Couldn't connect" wording (the same DHCP-timeout
artifact already understood from the 2.4GHz round). **VALIDATED 5GHZ
CAPABILITY ≠ 5GHZ PRODUCTION DEFAULT** - the band strategy in this
document is unchanged: 2.4GHz stays primary.

**Power-readiness handoff, for whenever the undervoltage condition is
addressed separately (not this round, not solved here):**

The known `0x50005` condition remains completely unchanged across
*three* separate rounds of real load now - the original Hardware
Validation soak, this round's reboot, and this round's 5GHz test - with
exactly one ALFA-correlated event on record (the original insertion-
time disconnect, still never repeated). That is a reasonably good sign,
but it is evidence of **short, supervised, single-client** tests, not
of 24/7 production readiness. Once the power supply is addressed, the
evidence this project should collect before trusting the ALFA in
production (unchanged from section 8's gate, restated here as the
concrete next step): an extended multi-hour soak, multiple
*simultaneously* associated clients (every test so far has been
strictly one client at a time, sequential), sustained ordinary traffic
(file transfer/chat, not synthetic stress), and continuous `dmesg`/
`vcgencmd get_throttled` monitoring across that whole window looking
specifically for **new** transitions beyond the already-known baseline
bits - not just an absence of adapter resets, but confirmation the
`0x50005` bits themselves never get *worse* under real multi-client
load. None of that is available yet, on this or any prior round, and
none of it should be inferred from today's clean single-client results.

**Regression:** 313/313 → 313/313 (unchanged - no new radio-role/
provider logic this round; this round's own verification re-ran the
existing suite to confirm the External AP Architecture round's staged
work was undamaged, and it wasn't). Catalog unchanged, 42/42.

**Explicitly not done this round, per instruction:** no production
migration, no production `wlan0`/`dnsmasq` edit, no DHCP added to
either isolated test network, no ARS-N19 test, no runtime radio
failover, no second permanent PirateBox network, no power repair.

---

## Exact operator gate for eventual migration

Everything above is preparation. The actual migration requires a human
to, in order:

1. Read this entire document (not just the gate list).
2. ~~Fix the regulatory domain~~ - **done** (2026-09-03, this round).
   `iw reg get` independently confirmed reading `country US: DFS-FCC`
   after a reboot. No further regulatory action needed before
   migration.
3. Install the two staged system files (udev rule, NetworkManager
   conf) - each independently safe/inert until `pb-ap` exists and/or
   NetworkManager's wifi radio is re-enabled (already re-enabled, as of
   this round - see "Regulatory domain" above; still no live exposure,
   since `pb-ap` doesn't exist until the udev rule is installed).
4. Decide, deliberately, that the power-aware gate's evidence bar
   (section 8, restated in section 16's power-readiness handoff above)
   has actually been met - not merely that hardware and 5GHz
   validation passed. **Still not met as of this round.**
5. Run `sudo PIRATEBOX_MIGRATION_CONFIRMED=yes-I-read-the-design-doc
   tools/migrate_visitor_ap_to_alfa.sh` and complete the Operator test
   steps in section 12.
6. Keep `tools/rollback_visitor_ap_to_onboard.sh` one command away
   until confident.

No part of this is scheduled, automated, or assumed to happen next
round. **Do not begin this migration without the operator explicitly
saying so.**
