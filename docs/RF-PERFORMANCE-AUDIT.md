# ALFA AWUS036ACM RF Performance/Range Audit (2026-09-04)

**Status: READ-ONLY AUDIT. No live configuration changed.** Performed
after real-world range testing of production `pb-ap` (Debian laptop:
~-15 dBm near the unit, ~-30 dBm outside the room, ~-45 to -55 dBm
through the house, ~-60 to -70 dBm in a far closed-door room) prompted
the question of whether the adapter is running at its practical/legal
ceiling or still on the conservative baseline carried over from the
ALFA Migration Round. This document is the evidence trail behind that
question; see "Findings summary" for the answer and
`docs/IMPLEMENTATION-ROADMAP.md` for whatever tuning round follows it.

Nothing here is new capability discovery — most of the hardware
capability facts (regulatory domain, 5GHz channel map, VHT 2x2) were
already established in `docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md` §6/§16
and are restated here only where needed for context. What's new this
round: live production-config inspection (`hostapd.conf` as actually
running, not just as designed), per-channel survey/occupancy data,
antenna/chain/power-save verification, USB-bus characterization, and
the single-radio dual-band question answered from `iw`'s own interface-
combination data rather than assumption.

---

## 1. Findings summary

**The adapter is already at its legal TX-power ceiling on channel 6
(23 dBm, matching `country US` exactly) and both RF chains are present
and enabled.** The measured range so far reflects real hardware/RF
limits (path loss, walls, channel congestion, possibly power
integrity) - not a config knob left conservative on power. **What *is*
genuinely conservative, and untouched since migration:** `hostapd.conf`
enables 802.11n (`ieee80211n=1`) but sets **no `ht_capab` at all**, so
hostapd advertises hostapd's own bare default HT capability mask -
concretely, **no 40 MHz channel bonding, no short guard interval, no
LDPC, no STBC** are advertised in the beacon, despite the ALFA
genuinely supporting all of them on this band. This doesn't move raw
*range* (that's power/antenna/propagation), but it caps *usable
throughput and link robustness at the edge of range*, where MCS
fallback headroom matters most.

**Single MT7612U radio cannot run 2.4GHz and 5GHz simultaneously** -
confirmed structurally from `iw phy1 info`'s own interface-combination
rule (`#channels <= 1`), not assumed. This is a single-radio hardware
limit, not a driver/hostapd config choice: the chip has one RF/channel
context, so 2.4 and 5GHz are strictly time-shared (reboot/restart to
switch bands), never concurrent, on this adapter alone.

**Power integrity remains the single largest unresolved variable that
could be silently capping real-world reliability at range**, per
`docs/POWER-INTEGRITY-DIAGNOSIS.md`: this Pi's 5V rail sits ~70mV above
its own undervoltage-detection threshold with periodic 1.2-1.4V sags,
independent of the ALFA. Nothing this round found is inconsistent with
that document's conclusions; nothing this round found newly implicates
the ALFA either.

---

## 2. Regulatory domain and effective TX-power ceiling

`iw reg get` confirms production is running under a genuine FCC
ruleset, not world/fallback:

```
country US: DFS-FCC
  2400 - 2472 @ 40   -> 30 dBm max (regulatory ceiling; see below for actual per-channel)
  5150 - 5250 @ 80   -> 23 dBm, AUTO-BW
  5250 - 5350 @ 80   -> 24 dBm, DFS, AUTO-BW
  5470 - 5730 @ 160  -> 24 dBm, DFS
  5730 - 5850 @ 80   -> 30 dBm, AUTO-BW
```

This is the *domain-wide* ceiling table; the adapter's own per-channel
table (from `iw phy1 info`, below) is what actually governs, and it is
already at or under this ceiling everywhere - **no regulatory headroom
is being left unused.**

One live oddity, noted for completeness and *not* a problem: `iw reg
get` also shows a second block, `phy#0 country 99: DFS-UNSET`. That is
the **onboard Broadcom radio (`wlan0`/`phy0`)** reporting its own
self-managed regulatory state (`brcmfmac` manages its own reg domain
independently of the global `cfg80211` domain) - it does not apply to
`phy1`/`pb-ap`/the ALFA, which correctly follows the global `US`
domain. Confirmed by mapping `iw dev` output (`pb-ap` -> `wiphy 1`,
`wlan0` -> `wiphy 0`) before drawing this conclusion.

**Per-channel ceiling actually enforced on the ALFA** (`iw phy1 info`,
Band 1 = 2.4GHz):

| Channels | Ceiling | State |
|---|---|---|
| 1-11 | **23 dBm** | enabled |
| 12-14 | - | **disabled** (correct US behavior, not merely "no IR") |

**Actual configured/running TX power, verified live:**
`iw dev pb-ap info` -> `txpower 23.00 dBm` on channel 6. **This already
equals the adapter's own regulatory ceiling for that channel** -
hostapd is not capping power below what's legally available; there is
no headroom left on the table here. (`hostapd.conf` has no explicit
`tx_power`/`min_tx_power` override; the driver's own reg-limited
maximum is what's in effect, which is the correct default.)

---

## 3. hostapd radio configuration - full live file, and its gaps

Live `/etc/hostapd/hostapd.conf` in full (confirmed identical to the
repo copy except the expected `interface=` line):

```
interface=pb-ap
driver=nl80211
ssid=PirateBox
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
auth_algs=1
wpa=0
country_code=US
```

That's the entire file. Checked the repo's history and design docs
(`grep -rn "ht_capab\|HT40\|ampdu"`) - **this was never a deliberate
decision**, in either direction; the file simply hasn't been touched
since the original wlan0-era config, carried through the ALFA
migration unchanged.

**What this leaves un-set, concretely, against what the hardware
supports** (§4 below has the full capability list):

| Setting | Live config | Hardware supports | Effect of leaving it unset |
|---|---|---|---|
| `ht_capab` (40MHz/HT40+) | not set | HT20/HT40 | Beacon advertises **HT20 only** - clients that would happily do 40MHz-wide 2.4GHz (rare/discouraged there anyway, see §7) can't; irrelevant for range, minor for throughput near the AP |
| `ht_capab` short-GI (`[SHORT-GI-20][SHORT-GI-40]`) | not set | RX HT20 SGI, RX HT40 SGI | Slightly lower peak PHY rate at every MCS; small, not a range factor |
| `ht_capab` LDPC (`[LDPC]`) | not set | RX LDPC | LDPC mainly helps *decode margin at low SNR* - i.e. **exactly the far-corner-room case this audit is about.** Not advertising it doesn't prevent it (LDPC is often auto-negotiated per-frame capability, not just a beacon flag; needs to be confirmed against hostapd/mt76's actual behavior before assuming beacon-only), but it's a genuine gap worth closing |
| `ht_capab` STBC (`[TX-STBC][RX-STBC1]`) | not set | TX STBC, RX STBC 1-stream | STBC (transmit diversity) is one of the few *hardware capabilities that directly targets weak-signal robustness at range*, not just throughput - this is the single most range-relevant item in this table |
| `wmm_enabled` | `1` (set) | AP-side U-APSD supported | Already correctly on - no gap |
| A-MPDU / A-MSDU aggregation | not configured (hostapd has no direct knob here beyond `ht_capab`'s max-A-MSDU bit; aggregation itself is driver/firmware-negotiated) | Max RX AMPDU 65535 bytes, no min spacing restriction | Driver default is already the hardware maximum; nothing to change |
| `country_code` | `US` (set) | - | Correct, matches `iw reg get` |
| `ieee80211n` | `1` (set) | - | Correct, HT is enabled at all - the gap is specifically the *capability mask*, not whether 11n is on |

**Framing this correctly for the range question asked:** none of the
`ht_capab` bits change transmit power or antenna gain - they don't
extend the *radio* range. What they change is **how gracefully the
link degrades as signal drops toward the edge of range** (STBC, LDPC)
and **peak throughput for clients already well within range** (40MHz,
SGI). For a `-60 to -70 dBm far-room` client, STBC/LDPC availability
is plausibly the difference between "stays connected at a lower MCS"
and "drops association" - directly relevant to the "reliability at
long range" part of the ask, even though it's not a dBm/coverage
change.

---

## 4. HT/VHT capability inventory - what the hardware exposes vs. what's active

From `iw phy1 info` (phy1 = `pb-ap` = the ALFA, confirmed via `iw dev`
wiphy-index mapping):

**2.4GHz (Band 1):**
- HT20/HT40, RX LDPC, RX Greenfield, RX HT20 SGI, RX HT40 SGI, TX
  STBC, RX STBC 1-stream, SM Power Save **disabled** (good - means the
  chip isn't power-saving down to single-chain automatically).
- HT MCS 0-15 (i.e. genuine 2-stream HT, up to 300 Mbps PHY at
  HT40+SGI - not reachable at `hw_mode=g`/HT20-only as currently
  configured, see §3).
- Max RX A-MPDU 65535 bytes, no minimum spacing restriction (already
  hardware-maximum, nothing to tune).
- Channels 1-11 at 23 dBm; 12-14 correctly disabled under `US`.

**5GHz (Band 2):**
- HT20/HT40 plus full VHT: `VHT Capabilities (0x318001b0)` - RX LDPC,
  short-GI 80MHz, TX STBC, max MPDU 3895 bytes, **max channel width 80
  MHz (not 160/80+80)** - this is the chip's own ceiling, not a
  regulatory or config limit.
- VHT RX/TX MCS 0-9 on **both 1 and 2 streams** - genuine 2x2 MIMO,
  confirmed again this round (matches the Regulatory Domain Correction
  Round's earlier finding).
- Non-DFS, immediately usable: 36/40/44/48 (UNII-1) and
  149/153/157/161/165 (UNII-3), all 20 dBm.
- DFS-gated (correctly, not enabled): 52-144, all flagged `(radar
  detection)`.
- Not usable under this domain: 169/173/177, `(no IR)`.

**What's actually enabled today: 2.4GHz only, HT20 only, no VHT in
use** (5GHz is not running at all - see §6 for why that's the right
call, not an oversight). Within that scope, the gap identified in §3
(`ht_capab` unset) is the only place capability and configuration
diverge.

---

## 5. RF chains / antennas - verified operating as expected

- `iw phy1 info`: **Available Antennas: TX 0x3 RX 0x3** - two bits
  set, confirming the driver sees a genuine 2-chain/2-antenna radio on
  both TX and RX, matching the ALFA's stock matched dual-band antenna
  pair and the chip's advertised 2x2 MIMO. This is independent
  confirmation of what VHT MCS reporting (2-stream support, §4) already
  implied.
- **One reporting oddity, investigated, not a functional problem:**
  `iw phy1 info` also shows `Configured Antennas: TX 0x202 RX 0x202` -
  a value outside the valid 2-bit range implied by `Available Antennas:
  0x3`. This is a known category of `mt76` driver quirk (the antenna-
  configuration query/set path isn't fully meaningful for this driver
  family the way it is for e.g. `ath9k`) rather than evidence of a
  real 1-antenna or misconfigured state - corroborated by the VHT
  2-stream RX/TX capability actually being negotiable (a true 1-chain
  radio could not report 2-stream VHT MCS support at all). `mt76`'s
  debugfs (`/sys/kernel/debug/ieee80211/phy1/mt76/`) exists but exposes
  no `chainmask` file on this driver version to cross-check further
  without root; not pursued further this round since this is
  read-only-only and the VHT-capability cross-check already gives
  reasonable confidence.
- **No live client was connected during this audit** (`iw dev pb-ap
  station dump` returned empty, matching `status.json`'s
  `wifi_clients: 0`), so **per-client signal/chain RSSI could not be
  directly verified this round** - the real-world range numbers in the
  prompt are the only evidence of both chains actually contributing to
  received signal quality; a future soak with a station connected
  could pull `iw dev pb-ap station dump`'s per-chain signal fields
  (`signal:` list, when present) for direct confirmation.

---

## 6. Single-radio dual-band question - answered from `iw`, not assumed

**Simultaneous 2.4GHz + 5GHz AP operation on the ALFA alone is not
possible with this hardware**, confirmed structurally rather than
inferred from general MT7612U knowledge:

```
valid interface combinations:
  #{ IBSS } <= 1, #{ managed, AP, mesh point, P2P-client, P2P-GO } <= 2,
  total <= 2, #channels <= 1, STA/AP BI must match
```

The MT7612U can technically host up to 2 concurrent AP-mode virtual
interfaces - but **`#channels <= 1`** means every concurrent interface
on this radio must share the *same channel*. 2.4GHz and 5GHz are
different bands entirely (never the same channel/frequency), so this
single radio's one RF/PLL context can only ever be tuned to one band
at a time. This is a **chip/radio-architecture limit**, not a driver
build option or a hostapd config choice - no combination of settings
on this single adapter changes it.

**What this means for "retain 5GHz capability without losing 2.4GHz
range," concretely:**

- **Band-switching (time-shared), on this one adapter, is real and
  already validated**: stop `hostapd`/change `hw_mode`+`channel`+
  restart to flip to a temporary 5GHz profile, then flip back. This was
  exactly the mechanism the Regulatory Domain Correction Round used for
  its isolated 5GHz test. Usable for an explicit alternate-profile mode
  an operator selects (matching this document's own existing "5GHz:
  optional, not default" stance) - not for simultaneous dual-band.
- **True simultaneous dual-band AP requires a second physical radio.**
  The onboard `wlan0` (Broadcom `brcmfmac`, `phy0`) is architecturally
  a separate radio that could, in principle, run its own independent
  AP concurrently with `pb-ap` - but per this project's explicit
  standing architecture (**"wlan0 = onboard Wi-Fi reserved/inactive"**,
  restated in this audit's own instructions), that is out of scope to
  even evaluate further here, and doing so would be a real architecture
  change (a second concurrent visitor network, or repurposing wlan0
  entirely), not a tuning change. Recorded here only to answer the
  question precisely: **the capability to add real concurrent dual-band
  exists in the hardware already present on this Pi (a second radio),
  it is just not the ALFA providing it, and using it is a deliberate
  future architecture decision, not something this pass should decide
  or stage.**
- **Not evaluated and not recommended**: a second USB Wi-Fi adapter
  purely to get concurrent dual-band from two ALFA-class radios - not
  asked for, would add a second USB-bus/power load on an already
  power-marginal Pi (see §9), and is a hardware-acquisition decision
  outside a configuration audit's scope.

---

## 7. 2.4GHz channel 6 - current environment, from safely-obtained data

**Method used, and why:** `iw dev pb-ap survey dump` reads the radio's
own per-channel energy-detection counters **without changing the
radio's channel or interrupting the AP** - the AP stays on channel 6
throughout, beaconing and associating normally. This is different from
an active `scan`, which would briefly tune the radio off-channel and
was avoided on `pb-ap` for exactly that reason.

**Result, over the current `hostapd` run's full uptime (~3h48m since
last start):**

| Channel | Active time | Busy time | Busy % |
|---|---|---|---|
| **6 (in use)** | 13,647,989 ms | 4,040,733 ms | **~29.6%** |
| 1, 2, 3, 4, 5, 7, 8, 9, 10, 11 | 0 ms each | 0 ms | n/a - radio never dwells there while parked on ch6, no data available this way |

**~29.6% channel-busy time on channel 6, with only 409 ms of that being
this AP's own transmit time**, means roughly 4 million ms of energy
detected on channel 6 over ~3.8 hours came from **something other than
this AP's own traffic** - other Wi-Fi (neighboring APs/clients) and/or
non-Wi-Fi 2.4GHz energy (Bluetooth, microwave, baby monitors, etc. are
all plausible in a residential environment; not distinguishable from
this counter alone). **~30% is moderate congestion** - not saturated,
but a real, measurable contention factor a client at the edge of range
has to compete with.

**Whether channel 6 is still the right choice cannot be fully answered
from this data alone**, because the survey mechanism only reports
energy on the channel the radio is *currently tuned to* - it cannot
show what channels 1 or 11 look like without the radio actually
visiting them (a scan). **A safe, non-`pb-ap` path exists but could not
be completed this round**: the onboard `wlan0` radio is a separate
physical radio (`phy0`, confirmed idle, unassociated, unmanaged by
NetworkManager) that could run a passive scan to survey neighboring
2.4GHz APs/channels/signal strength with **zero effect on `pb-ap`**
(different phy entirely) - but bringing `wlan0` up and issuing a scan
both require root, which is outside this session's two narrow standing
`sudo` grants (deliberately scoped to deploy/mode-switch scripts only,
per `CLAUDE.md` §2). **Recommended follow-up, safe and non-disruptive,
operator-run:**

```bash
sudo ip link set wlan0 up
sudo iw dev wlan0 scan | grep -E "^BSS|freq:|signal:|SSID:"
sudo ip link set wlan0 down   # return to the documented reserved/inactive state
```

This would show real neighboring-network channel/signal data without
ever touching `pb-ap` or production traffic, and is the concrete next
step to actually answer "is channel 6 still sensible" with data rather
than the ~30%-busy proxy this round could obtain unattended.

**What this round's evidence does support:** channel 6 is not
obviously wrong (30% busy is not severe), but it also isn't confirmed
optimal - it's the traditional non-overlapping default (1/6/11), never
re-evaluated against this specific environment since migration. A
2.4GHz channel choice is generally 5-10 minutes of low-risk, easily-
reversible work once real neighbor data exists (change `channel=` in
hostapd.conf, restart hostapd) - appropriate for a future tuning round
guided by the scan above, not this read-only pass.

---

## 8. Power save and other kernel/driver factors

- **`iw dev pb-ap get power_save` -> `Power save: off`.** Confirmed
  correct for an AP-mode interface - power save here governs client-
  side behavior on a managed-mode link, not applicable the same way to
  AP mode, but it's explicitly off, not left ambiguous.
- **SM (spatial multiplexing) Power Save: disabled** on both bands per
  `iw phy1 info` - correct; if this were enabled, the radio could drop
  to single-chain operation to save power, silently halving MIMO
  capability. It is not enabled.
- **USB autosuspend: confirmed off.** `/sys/bus/usb/devices/1-1.3/
  power/control` reads `on` (not `auto`) - the ALFA's USB link is not
  subject to autosuspend, which would otherwise introduce latency/
  wake-up delay or, in worse cases, adapter drops under a marginal
  power rail (see §9). No change needed here; already correct.
- **`mt76-usb`'s `disable_usb_sg` parameter is `N`** (scatter-gather
  enabled - the recommended/default state, not disabled). No change
  needed.
- **CPU governor `ondemand`, running at full 1400MHz** at time of
  check - not currently frequency-capped (`vcgencmd get_throttled`'s
  bit 1 is clear even though bit 2 "currently throttled" is set - a
  known Pi-firmware nuance already documented in
  `docs/POWER-INTEGRITY-DIAGNOSIS.md` §1, not re-litigated here). CPU
  headroom is not currently limiting hostapd/mt76 processing.
- **No `ctrl_interface` is configured in `hostapd.conf`** -
  `hostapd_cli` cannot attach live (`wpa_ctrl_open: No such file or
  directory`). This is an operational/diagnostics gap, not an RF one:
  it means there's no easy live per-client signal/rate/rejection
  visibility via `hostapd_cli all_sta` today. Worth adding in a future
  round (`ctrl_interface=/var/run/hostapd` + restart) purely for
  future troubleshooting - **not a range or performance factor itself**,
  listed here for completeness since the audit went looking for
  anything that could matter.

---

## 9. USB 2.0 bus - throughput vs. RF range, kept explicitly distinct

**Confirmed via `lsusb -t`:** the ALFA is the sole device on the
second internal USB hub tier, at `480M` (USB 2.0 high-speed) link
speed, alongside the Pi's onboard Ethernet chip (`lan78xx`) one level
up the same tree. All three - Pi SoC, onboard Ethernet, and the ALFA -
share the SoC's single USB 2.0 host controller (`dwc_otg`) on the Pi
3B+; this is a hardware fact about this board revision, not a
configuration choice.

**Why this matters for throughput, not range:** USB 2.0's ~480 Mbps
raw/~300 Mbps practical ceiling, shared with Ethernet traffic, bounds
*how much data* can move between the ALFA and the Pi's CPU regardless
of how strong the RF link is. A client sitting at -15 dBm right next
to the AP with an excellent RF link could still be throughput-capped
by this shared bus well below what 2x2 HT/VHT could otherwise deliver.

**Why this does *not* explain the range/RSSI numbers in the prompt:**
RSSI/path-loss/coverage is purely a function of TX power, antenna
gain, and propagation (walls, distance, obstructions) - none of which
route through the USB bus. A weak signal at the far room is not a USB
symptom; a *slow transfer* despite a strong signal near the AP would
be. **This audit's RF-chain and TX-power findings (§2, §5) are the
right lens for the range numbers; USB is the right lens only for
throughput at short range.** Nothing found this round suggests the
USB bus is contributing to *reliability* problems specifically (no
USB errors/resets/disconnects correlated with AP operation, per
`docs/POWER-INTEGRITY-DIAGNOSIS.md`'s §9c load-isolation test) - the
concern there is bus-power-sharing with the same marginal 5V rail (see
§10), not the data-link speed itself.

---

## 10. Power integrity - explicitly not conflated with RF behavior

Per instruction, and per this project's own extensively-tested
`docs/POWER-INTEGRITY-DIAGNOSIS.md`: **`0x50005` (active undervoltage,
current + sticky) is confirmed present right now** (`vcgencmd
get_throttled` re-checked live this round, unchanged), and **has
already been independently proven, across four separate controlled A/B
tests (cable, brick, ALFA-removed, fans-removed), to be unrelated to
the ALFA's presence or activity** - it is chronic, predates the ALFA,
and persists identically with the ALFA physically absent.

**What this audit adds, specific to the RF question asked:** nothing
tested this round contradicts that prior conclusion, and nothing this
round found newly implicates the ALFA. However, the prior document's
own §9d finding remains the single most important *caveat* on "maximum
practical, stable RF performance": a **5V rail sitting only ~70mV above
this board's own undervoltage-detection threshold, with periodic
1.2-1.4V transient sags** is not a comfortable margin for *any*
USB-bus device drawing variable current - including brief TX-power
transients from the ALFA itself during heavy beaconing/retry bursts
under poor-RSSI conditions (exactly the far-room scenario this audit
is about). **This was not tested this round** (would require sustained
multi-client load specifically to see if TX bursts correlate with new
undervoltage transitions, which is exactly the deferred "power-aware
migration gate" soak in `docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md` §8/
§16 - still not met, still not run, for the same reasons already on
record: don't stress-test a known-marginal supply without the
operator's own direction). **Recorded honestly:** if any future tuning
change (e.g. raising 2.4GHz TX power - moot here, already at
ceiling - or increasing beacon/retry aggressiveness) ever increases
instantaneous current draw, the *first* place to check for a new
failure mode is this rail, not the ALFA's RF behavior, per this
document's own explicit instruction not to misattribute one to the
other.

---

## 11. mt76x2u-specific notes

- **ASIC/firmware, confirmed from `dmesg`:** ASIC revision `76120044`,
  firmware `0.0.00` (build 1, built `201507311614`), ROM patch build
  `20141115060606a` - an old-but-standard in-kernel `mt76x2u` firmware
  blob; no separate/newer firmware package exists to install for this
  driver (not evaluated as an action item - the project's "no package
  installs without operator go-ahead" rule applies, and no version gap
  evidence was found suggesting this firmware is deficient).
- **`mt76`'s debugfs `txpower` node reports `Target power: 34`** (raw
  driver/firmware units, not directly dBm) alongside `iw`'s
  user-facing `23.00 dBm` - both readings are internally consistent
  with the adapter running at its regulatory ceiling; the raw debugfs
  value is not a separate, higher, unused ceiling being left off.
- **No `chainmask` debugfs file exists** on this driver version to
  directly force/verify per-chain enablement beyond the `iw phy info`
  antenna-count evidence already gathered (§5).
- **No mt76x2u module parameters exist beyond the shared `mt76-usb`
  `disable_usb_sg` flag** (`modinfo mt76x2u` shows no `parm:` lines of
  its own) - there is no hidden per-driver tunable being missed here;
  the tuning surface for this chip is genuinely `iw`/`hostapd`-level,
  not module-parameter-level.

---

## 12. Recommended tuning changes, ranked by expected benefit vs. risk

**Not implemented this round, per instruction - staged as
recommendations for a future, explicitly-approved tuning pass.**

| # | Change | Expected benefit | Risk | Why this rank |
|---|---|---|---|---|
| 1 | Add `ht_capab=[STBC][LDPC][SHORT-GI-20][SHORT-GI-40]` (or the subset the mt76x2u/hostapd combination actually accepts - verify exact syntax before applying) to `hostapd.conf`, restart hostapd | Better link robustness/decode margin specifically at low-SNR/long-range conditions (STBC, LDPC), modest throughput gain near the AP (SGI) | Low - purely a beacon/negotiation capability change, backward-compatible with older clients, easily reverted by removing the line and restarting | Highest benefit-to-risk: directly targets "reliability at long range," which is the stated goal, with a trivially reversible one-line/one-restart change |
| 2 | Run the safe `wlan0`-based passive scan (§7) to get real neighbor-channel data, then reconsider `channel=6` vs. 1/11 if the data supports it | Could reduce the ~30%-busy contention if a genuinely quieter channel exists nearby | Low for the scan itself (doesn't touch `pb-ap`); Low-Medium for an eventual channel change (one-line `hostapd.conf` edit + restart, brief AP interruption during restart) | High information value, low cost to gather; the channel change itself should wait for the actual scan data, not be guessed from the 30%-busy figure alone |
| 3 | Add `ht_capab=[HT40+]` (2.4GHz 40MHz bonding) | Peak throughput increase for close-in clients that support it | **Not recommended as a default for this specific deployment** - 40MHz on 2.4GHz roughly halves the number of non-overlapping channels available, worsening exactly the contention problem #2 is trying to measure/fix, in a residential multi-neighbor environment already showing ~30% channel busy time. Listed for completeness, not endorsed. | Explicitly ranked below #1/#2, opposite direction from the range/reliability goal |
| 4 | Add `ctrl_interface=/var/run/hostapd` to `hostapd.conf` | Enables `hostapd_cli` for live per-client diagnostics in future rounds (including the A/B testing this document's own §13 recommends) | Low - purely additive, standard hostapd feature, no behavior change to the radio itself | Operational convenience, not RF performance - useful groundwork for testing future changes, not a performance change on its own |
| 5 | 5GHz as an explicit, operator-selected alternate profile (band-switch, not concurrent) using the already-validated non-DFS channels | Higher peak throughput at short-to-medium range for 5GHz-capable clients, when chosen | Medium - requires a real config swap (not concurrent with 2.4GHz per §6), a service restart, and re-validation; also re-opens the USB2 bus-sharing throughput ceiling (§9) as the limiting factor for any throughput gain actually realized | Legitimate, previously validated, but a mode switch/operational decision, not a tuning tweak - matches this document's own "5GHz: optional, not default" stance; sequence after 1-2, and only if the operator wants a 5GHz profile at all |

---

## 13. What should NOT be changed

- **TX power on 2.4GHz** - already at the regulatory ceiling (23 dBm on
  channel 6). No config change can legally exceed this; nothing found
  suggests hostapd/driver defaults are capping below it.
- **Antenna hardware** - the stock matched ALFA dual-band pair is
  correct for this adapter's genuine 2x2 MIMO capability; per
  `docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md` §7, the ARS-N19 (2.4GHz-
  only, unmatched single antenna) would silently degrade MIMO to
  effective 1x1 and remains explicitly out of the baseline. No passive
  Y-splitting either, for the same reason.
- **Regulatory domain / country code** - already correctly `US`,
  `DFS-FCC`. No override, patched regdb, or non-standard country code
  should be used, consistent with the instruction and with this
  project's own standing rule.
- **USB autosuspend / `disable_usb_sg`** - both already at their
  correct, non-power-saving, full-performance settings; nothing to
  change.
- **Attempting simultaneous 2.4+5GHz on the ALFA alone** - structurally
  impossible on this radio (§6); don't spend further config effort
  trying.
- **Any change to production `wlan0`, `eth0`, the `10.0.0.1/24`
  addressing, or the `PirateBox` SSID** - out of scope for an RF tuning
  pass and not touched by anything recommended above.
- **Any stress/soak test of the current power supply** to validate
  tuning changes "under load" - per `docs/POWER-INTEGRITY-DIAGNOSIS.md`
  and `docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md` §8/§16, deliberately not
  run until the operator decides the marginal-rail question is either
  acceptable or separately addressed.

---

## 14. Objective A/B testing method for future changes

To evaluate any of §12's recommendations (or future ones) without
guessing from subjective "feels better," matching the same fixed-
location methodology already used for this round's baseline range
numbers:

**Fixed test points (reuse the exact locations from this round's
baseline, so results are comparable):**
1. Near the PirateBox (baseline ~-15 dBm).
2. Just outside the room/door (baseline ~-30 dBm).
3. Through the middle of the house (baseline ~-45 to -55 dBm).
4. Far corner room, door closed (baseline ~-60 to -70 dBm).

**At each point, for both the "before" and "after" configuration,
record:**
- **RSSI**: `iw dev <client-iface> link` (client side) and/or `iw dev
  pb-ap station dump`'s `signal:`/`signal avg:` (AP side, while the
  client stays associated) - prefer the AP-side reading where possible
  since it reflects what the AP actually receives from the client, the
  more failure-relevant direction for range.
- **Ping loss/latency**: a fixed-count, fixed-interval ping from the
  client to `10.0.0.1` (e.g. `ping -c 100 -i 0.2 10.0.0.1`) - record %
  loss and RTT distribution (min/avg/max, and ideally p95) at each
  point, not just an average.
- **Throughput**: a real file transfer of a fixed, sufficiently large
  file already present on PirateBox (avoids needing to install
  `iperf3`, matching the project's own tooling caution) - record
  transfer time and effective Mbps, and note that near-AP measurements
  are the ones actually informative for USB2-bus-limited throughput
  claims (§9), while far-room measurements are the ones informative for
  RF-robustness claims (STBC/LDPC, channel congestion).

**Procedure discipline, matching this project's own established A/B
method** (`docs/POWER-INTEGRITY-DIAGNOSIS.md` §9a-§9d):
- **Change exactly one variable at a time** (e.g. `ht_capab` alone, or
  the channel alone) - don't bundle multiple recommendations from §12
  into one test, or a result can't be attributed to a specific change.
- **Same client device, same test points, same time-of-day-ish
  conditions** where practical, since 2.4GHz neighbor congestion (§7)
  is itself a variable that changes over the day.
- **Record `vcgencmd get_throttled` and `dmesg`/`journalctl -k` (mt76/
  USB errors) before and after each change**, exactly as the power
  diagnosis document's own tests did - so that if a future change
  happens to coincide with a new undervoltage transition, that's
  visible and attributable rather than silently blamed on the RF
  change (or missed entirely).
- **Revert immediately if the "after" measurement is worse at any
  point**, rather than accumulating multiple untested changes -
  matches this project's own preview-then-apply, verify-live discipline
  (`CLAUDE.md` §2).

---

## 15. What was and wasn't done this round

**Performed, all read-only, zero production impact:**
- Full live `hostapd.conf`/`dhcpcd.conf` inspection and diff against
  the repo.
- `iw reg get`, `iw phy1 info` (full capability dump), `iw dev`
  interface/wiphy mapping, `iw dev pb-ap info` (live channel/txpower),
  `iw dev pb-ap survey dump` (channel-6 occupancy over the current
  hostapd run), `iw dev pb-ap station dump` (confirmed empty, matching
  `status.json`), `iw dev pb-ap get power_save`.
- USB topology/speed (`lsusb -t`), driver identification (`ethtool -i`
  on both `wlan0` and `pb-ap`), USB autosuspend state, `mt76-usb`
  module parameters, `mt76` debugfs enumeration (no root available for
  the gated files, noted honestly rather than skipped silently).
- `rfkill list`, `vcgencmd get_throttled`/`measure_temp` (fresh reads,
  cross-checked against `docs/POWER-INTEGRITY-DIAGNOSIS.md`'s existing
  conclusions, not re-litigated from scratch).
- `dmesg` review for `mt76x2u`/USB enumeration/firmware version.
- Repo-wide grep confirming `ht_capab`/HT40/SGI/STBC tuning was never
  previously discussed or deliberately decided - this round's §3/§12
  findings are genuinely new, not a re-litigation of a settled call.

**Not done, per instruction (production untouched):**
- No `hostapd.conf`, `dhcpcd.conf`, or any other live config file was
  edited.
- No active `scan` was run on `pb-ap` (would have taken the radio
  off-channel, however briefly - avoided per instruction to not
  disrupt the production AP).
- The recommended `wlan0` passive-scan follow-up (§7) was attempted but
  **could not complete** - bringing the interface up and scanning both
  require root, outside this session's two narrow standing `sudo`
  grants; exact commands left for the operator.
- No channel change, no `ht_capab` change, no band switch, no service
  restart of any kind.
- No stress/soak test of the power supply.
- No hardware was touched (antennas, cabling, brick).

---

## 16. Suggested next step

Per the operator's own instruction, this pass stops here for review.
If the recommendations in §12 are approved, the natural order is:
**(1) run the safe `wlan0` neighbor scan (§7) first** (zero risk,
informs whether a channel change is worth making alongside the
`ht_capab` change), **then (2) apply the `ht_capab` addition and the
channel decision together as one small, reversible `hostapd.conf`
change**, verified with the §14 A/B method at all four fixed points
before considering it done.
