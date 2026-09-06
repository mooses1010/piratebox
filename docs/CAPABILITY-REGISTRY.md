# PirateBox Capability Registry

**Status: LIVING INVENTORY. Reconciled against `docs/HARDWARE-
INTEGRATION-DESIGN.md`, `docs/OPERATIONAL-DECISIONS.md`, `docs/POWER-
UPS-DESIGN.md`, `docs/RTC-TIME-READINESS-DESIGN.md`, live `lsusb`, and
this session's own operator statements - not invented.** This is the
concrete companion to `docs/ARCHITECTURE.md`'s principles: that
document is semantics, this one is state. Where a claim in this
document could not be independently verified against an existing
authoritative doc or a live check, it says so explicitly rather than
presenting it as confirmed fact.

**Nothing in this document was purchased, installed, wired, or
configured by writing it.** It records inventory; it doesn't change it.

## How to read this document

### States

| State | Meaning |
|---|---|
| **INSTALLED** | Physically present and wired/connected today. |
| **OWNED / INCOMING** | Purchased/ordered, but not yet arrived, or arrived but not yet wired/integrated. |
| **CURRENT SCOPE** | Actively serving its role right now (paired with INSTALLED - something can be installed but *not* current scope, e.g. superseded hardware still physically present). |
| **PLANNED** | A specific product/approach has been decided on for when this capability is eventually built, but nothing has been purchased. |
| **CANDIDATE** | An idea worth tracking; no specific product chosen, nothing purchased. |
| **DEFERRED** | Considered and consciously not pursued for now (not rejected on merit - just not now). |
| **REJECTED** | Evaluated and ruled out for a specific role, with the reason recorded, so it isn't re-litigated from scratch later. |

**A capability may also be architecturally RESERVED** (a pin, an I2C
address, a role) without any hardware existing yet - see
`docs/ARCHITECTURE.md` §4. GPIO24/GPIO27 are the current example (wired,
explicitly unassigned).

### Fields

Recorded where known/useful, per `docs/ARCHITECTURE.md` §5's "document
*why*, not just *who*" convention: purpose, architectural layer
(Core/Operational/Optional - see `docs/ARCHITECTURE.md` §2), state,
hardware/candidate hardware, interface/bus, Core dependency, failure
behavior, physical considerations, power considerations, privacy
sensitivity, UI exposure, integrated/attachable/companion classification
(§3), and notes/unknowns. **A blank or "unknown" field is left that way
- nothing here is filled in to make an entry look more complete than
it is.**

---

## 1. Core platform (for orientation - not itself a "capability" entry)

| Item | State | Detail |
|---|---|---|
| Raspberry Pi 3 Model B+ (Rev 1.3) | INSTALLED, CURRENT SCOPE | Confirmed live via `/proc/device-tree/model` (`docs/HARDWARE-INTEGRATION-DESIGN.md`). |
| microSD storage | INSTALLED, CURRENT SCOPE | ~115GiB usable per live `df -h` (`/dev/mmcblk0p2`), consistent with a 128GB-class card. Exact card model/brand not recorded in any doc checked. |
| Software stack | INSTALLED, CURRENT SCOPE | nginx, PHP 8.4-FPM, hostapd, dnsmasq - see `README.md` and `docs/OPERATIONAL-DECISIONS.md` throughout. |

## 2. Capability summary table

| Capability | Layer | State | Integrated/Attachable/Companion |
|---|---|---|---|
| Built-in `wlan0` | Operational (reserved) | INSTALLED, RESERVED FOR FUTURE USE - no longer the production AP as of the ALFA Migration Round (2026-09-03); confirmed down/idle, not repurposed (see `docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md` "Radio role model") | Integrated |
| TP-Link TL-WN722N v2/v3 | - | INSTALLED (physically present); REJECTED as AP candidate | Attachable |
| ALFA AWUS036NHA (AR9271) | - | REJECTED as AP candidate (never purchased) | n/a |
| ALFA AWUS036ACM (MT7612U) | Core | **PRODUCTION AP, COMMISSIONED (2026-09-03)** - `pb-ap` is the live PirateBox visitor AP; real client validated (association, DHCP lease, site load); single-client only so far, the separate multi-hour/multi-client soak evidence bar is not yet met (see `docs/IMPLEMENTATION-ROADMAP.md` §7 for the exact distinction) | Semi-permanent, installed |
| ALFA ARS-N19 antenna | Core (if AWUS036ACM adopted) | OWNED / INCOMING (operator-asserted this session - see note) | Attachable |
| ALFA AWUS036ACM built-in LED | - | **INVESTIGATED, NOT CONTROLLABLE - closed (2026-09-03)**. Kernel fully supports LED control (`CONFIG_MT76_LEDS`/`MAC80211_LEDS`/`LEDS_CLASS`/`LEDS_TRIGGERS` all present); this adapter never registers a `/sys/class/leds/` device, and the one exposed debugfs knob (`led_pin`) was tested twice (instant + sustained hold, operator watching) with no visible effect either time. No raw register write was guessed. See `docs/PHYSICAL-CONTROL-UX-DESIGN.md` §8 for the full evidence chain | n/a - no safe control path exists |
| Enclosure RGB/status LED(s) | Operational (future) | DOCUMENTED ONLY - future requirement, no hardware chosen; must be mode-aware (Emergency/fault priority, Stealth/Night/Transport suppress all cosmetic lighting) once a real enclosure exists | BLOCKED BY HARDWARE (no enclosure yet) |
| GPIO25 shutdown button | Core | INSTALLED, CURRENT SCOPE | Integrated |
| Toggle switch (Normal/Emergency, GPIO17) | Operational | OWNED / INCOMING | Integrated (planned) |
| Momentary buttons, GPIO22/23/24/27 | Operational | OWNED / INCOMING | Integrated (planned) |
| OLED (SSD1306 0.96" 128x64) | Operational | **INSTALLED, CURRENT SCOPE** (2026-09-03) | Integrated |
| Undervoltage / power-quality monitoring (software, `vcgencmd`) | Operational | INSTALLED, CURRENT SCOPE | Integrated (software) |
| UPS/battery hardware | Operational | CANDIDATE (requirements only) | Integrated (if adopted) |
| RTC (DS3231) | Operational | PLANNED (chip chosen, not purchased) | Integrated (planned) |
| Self-awareness / capability-state model (software) | Operational | INSTALLED, CURRENT SCOPE | Integrated (software) |
| About This PirateBox page (software) | Operational | INSTALLED, CURRENT SCOPE | Integrated (software) |
| Reference Pack model (software) | Operational | INSTALLED, CURRENT SCOPE | Integrated (software) |
| Device Memory - bounded event history (software) | Operational | INSTALLED (persistence fix live-verified 2026-09-02; device-history.json's own first write still awaits a boot/undervoltage edge - see docs/DEVICE-MEMORY-DESIGN.md §15) | Integrated (software) |
| Physical transport lock | Operational | CANDIDATE (design only, no hardware/mechanism chosen) | Integrated (if adopted) |
| `fake-hwclock` (software time fallback) | Operational | CANDIDATE | n/a (software) |
| Field Tools (time/date, unit conversion, coordinates) | Operational | INSTALLED, CURRENT SCOPE | Integrated (software) |
| I2C multiplexer (PCA9548A/TCA9548A) | Operational/infrastructure | CANDIDATE | Integrated (if adopted) |
| GNSS receiver | Optional/Field | CANDIDATE | Attachable or Integrated (undecided) |
| Environmental sensing (temp/humidity beyond CPU) | Optional/Field | CANDIDATE | Integrated or Companion |
| Air quality (CO2/particulate/VOC) | Optional/Field | CANDIDATE | Integrated or Companion |
| Light / UV | Optional/Field | CANDIDATE | Integrated or Companion |
| Motion / orientation (IMU) | Optional/Field | CANDIDATE | Integrated |
| Proximity (ToF) | Optional/Field | CANDIDATE | Integrated |
| Sound measurement | Optional/Field | CANDIDATE | Integrated or Companion |
| Lightning detection | Optional/Field | CANDIDATE | Integrated or Companion |
| Radiation measurement | Optional/Field | CANDIDATE | Integrated or Companion |
| External isolated I/O | Optional/Field | CANDIDATE | Attachable |
| SDR (Malahit-derived + RTL-SDR, owned) | Optional/Field | INSTALLED (OpenWebRX+ verified working via RTL-SDR at `/radio/`; visitor-facing wide retuning via `/utility/radio/live.php` fixed in repo (missing `magic_key`) but not yet deployed/confirmed live; Malahit path untouched/experimental) | Attachable |
| Ham-radio interface | Optional/Field | CANDIDATE | Attachable or Companion |
| Remote microcontroller/sensor node (e.g. ESP32) | Optional/Field | CANDIDATE | Network Companion |
| Another Pi / general companion node | Optional/Field | CANDIDATE | Network Companion |

---

## 3. Detailed entries

### Built-in `wlan0` (production AP)

- **Purpose:** the PirateBox Wi-Fi access point.
- **Layer:** Core.
- **State:** INSTALLED, CURRENT SCOPE.
- **Hardware:** Raspberry Pi 3 B+'s on-board Broadcom Wi-Fi.
- **Interface:** on-board, hostapd-managed.
- **Core dependency:** this **is** Core - the AP.
- **Failure behavior:** not documented as having a fallback of its own
  today (it *is* the fallback for the candidate ALFA upgrade - see
  below).
- **Privacy sensitivity:** none beyond what the AP already exposes
  (SSID, association) - not a new consideration.
- **Notes:** no per-adapter maximum-client-count limitation is
  documented for this chip (unlike the rejected AR9271 candidate
  below).

### TP-Link TL-WN722N v2/v3

- **Purpose:** originally evaluated as a possible AP upgrade path.
- **State:** INSTALLED (physically attached - confirmed live via
  `lsusb`, ID `2357:010c`); **REJECTED as an AP candidate.**
- **Hardware:** Realtek RTL8188EUS chipset, driver `rtl8xxxu`
  (mainline, no DKMS module installed).
- **Interface:** USB.
- **Failure/rejection reason:** `iw phy1 info` showed no `AP` in
  supported interface modes; confirmed empirically with a real `iw ...
  type __ap` attempt, which returned `EOPNOTSUPP` at the kernel/
  cfg80211 level (`docs/OPERATIONAL-DECISIONS.md`, "Wi-Fi adapter
  notes / planned hardware"). An out-of-tree DKMS driver could
  theoretically add AP support but is explicitly **not** installed
  without a separate, deliberate approval (maintenance/kernel-upgrade
  fragility tradeoff).
- **Notes/unknowns:** currently visible as `wlan1` in `managed` mode on
  this live system. **What, if anything, `wlan1` is currently being
  used for beyond being present is not established by any doc checked
  - recorded as unknown rather than guessed.**

### ALFA AWUS036NHA (Atheros AR9271)

- **Purpose:** considered as an AP upgrade candidate.
- **State:** REJECTED (never purchased - ruled out on paper before
  ordering).
- **Rejection reason:** excellent mainline `ath9k_htc` AP support, but
  a well-documented firmware limitation of ~7 associated stations,
  specific to that adapter's firmware (does not apply to the current
  `wlan0`).

### ALFA AWUS036ACM (MediaTek MT7612U)

- **Purpose:** candidate primary-AP upgrade, dual-band 2.4/5GHz, 2x2
  MIMO.
- **Layer:** would become Core only if/when actually adopted as the
  production AP; until then it's an evaluation candidate. **Not yet
  adopted - `wlan0` remains the production AP.**
- **State (2026-09-03, AWUS036ACM Hardware Validation Round):**
  physically connected, detected, driver bound, and hardware/driver/AP-
  association **VALIDATED** - `iw phy` correctly listed `AP` as a
  supported interface mode, and a live `hostapd` instance on an
  isolated test SSID (`PirateBox-ALFA-Test`, 2.4GHz channel 6,
  WPA2-PSK) reached `AP-ENABLED` and beaconed stably. The operator then
  tested from a phone and a laptop: `hostapd`'s own log shows a real
  client completing the full WPA2 4-way handshake **three independent
  times**, and one client was observed live, still connected
  (`authenticated: yes`, `associated: yes`, `authorized: yes`, signal
  -17 to -25 dBm). A client-side "Couldn't connect" message on the
  phone was traced to the test network's intentional absence of a DHCP
  server (each client disconnected itself shortly *after* a completed
  handshake - the standard mobile-OS DHCP-timeout abort pattern, not an
  authentication/radio rejection) - a full DHCP/IP-layer test was
  deliberately not performed, since doing so would have required
  touching production `dnsmasq` or installing a second DHCP
  implementation, and it was not needed to answer the 802.11/WPA2
  association question this round exists to settle. **Still not the
  production AP - `wlan0` continues in that role.** See
  `docs/OPERATIONAL-DECISIONS.md` "AWUS036ACM Hardware Validation
  Round" for the full evidence.
- **Migration architecture/readiness (2026-09-03, External AP
  Architecture + Production Migration Readiness Round):** a stable
  interface identity (`pb-ap`, udev rule matching driver+VID:PID - see
  `docs/EXTERNAL-AP-ARCHITECTURE-DESIGN.md` "Stable ALFA identity"),
  radio role model, boot-time fallback design, NetworkManager
  ownership fix, regulatory-domain findings (a real pre-existing
  `UM`/`US` typo in `/boot/firmware/cmdline.txt`, unrelated to but
  found during this work), band/antenna strategy, a power-aware
  migration gate, and a full migration+rollback plan are all designed
  and staged - **none installed, enabled, or executed.** `wlan0`
  remains production. See that document in full, especially its "Exact
  operator gate for eventual migration" section, before treating any of
  this as ready to run.
- **Regulatory domain + 5GHz validation (2026-09-03, Regulatory Domain
  Correction + ALFA Post-Regulatory Validation Round):** the `UM`/`US`
  typo above is now **fixed and independently verified** -
  `iw reg get` reads `country US: DFS-FCC`. Fixing it needed more than
  the one documented command: the live-apply half (`iw reg set`) proved
  genuinely broken on this system (reproduced twice), and a **reboot**
  was required to exercise the boot-time path, which worked. Under the
  corrected domain, **5GHz AP capability is now VALIDATED** - legal
  non-DFS channels 36/40/44/48 and 149/153/157/161/165, genuine 2x2 VHT
  to 80MHz, and a bounded isolated test (`PirateBox-ALFA-5G-Test`,
  channel 36) reached `AP-ENABLED` with a real client completing the
  WPA2 4-way handshake twice (judged from `hostapd`'s own log, not the
  phone's generic post-handshake UI wording - the same DHCP-timeout
  artifact already understood from the 2.4GHz test). **VALIDATED 5GHZ
  CAPABILITY ≠ 5GHZ PRODUCTION DEFAULT** - the band strategy is
  unchanged, 2.4GHz stays primary, and `wlan0` remains the production
  AP untouched throughout both this and the prior round.
- **Identity, confirmed live (not assumed from the purchase):** USB ID
  `0e8d:7612` (MediaTek Inc. MT7612U 802.11a/b/g/n/ac Wireless
  Adapter), enumerates as `wlan1` on this Pi today. USB2 480M
  high-speed under a nested onboard hub (Raspberry Pi 3 B+'s USB2-only
  limitation applies - no USB3 available regardless of adapter
  capability).
- **Driver:** `mt76x2u` (mainline in-tree, confirmed bound and
  functional - not merely present as a module). Firmware loaded:
  ASIC revision `76120044`, ROM patch build `20141115060606a`, firmware
  version `0.0.00` build 1. No DKMS/vendor/out-of-tree driver used or
  needed.
- **Confirmed wireless capabilities (live `iw phy` query, this
  session):** interface modes include `AP` (and `monitor`, `IBSS`,
  `mesh point`, `P2P-client/GO`) - genuinely supports AP mode under the
  mainline driver, unlike the TL-WN722N V2 (which returned `EOPNOTSUPP`
  on the equivalent AP-vif-creation probe - see that adapter's own
  entry above). 2.4GHz: HT20/HT40, channels 1-11 usable for
  transmission under the current (world/`00`) regulatory domain,
  12-14 restricted (no-IR). 5GHz: VHT (802.11ac) present, RX/TX MCS
  0-9 on 1 and 2 spatial streams (confirms genuine 2x2), max channel
  width 80MHz (no 160/80+80) - **but every 5GHz channel currently
  shows `(no IR)` under the active world regulatory domain**, so a
  5GHz AP test is not legally possible today without a separate,
  deliberate regulatory-domain decision (out of scope for this round).
  Interface-combination limit: up to 2 concurrent vifs on this phy,
  but only 1 channel at a time - no simultaneous multi-channel AP+scan
  on the ALFA itself (irrelevant to the two-radio wlan0+wlan1 case,
  since they're independent phys).
- **Power/USB soak findings - read carefully before assuming either
  "adapter is fine" or "adapter is the problem":** the Pi's `vcgencmd
  get_throttled` reads `0x50005` (under-voltage detected now AND since
  boot, throttled now AND since boot) - this is the **same known
  pre-existing chronic condition** recorded before the ALFA was ever
  involved (identical value in the Round 9 post-outage recovery, with
  no ALFA present at all) - **not new, not caused by this adapter.**
  Separately, at the ALFA's first insertion this session, a single
  USB disconnect/re-enumeration cycle occurred ~11 seconds after first
  appearing, coincident with one SD-card (`mmcblk0`) read I/O error and
  one USB host-controller (`dwc_otg`) transfer-timeout warning - a
  cross-subsystem pattern consistent with a momentary power-rail sag
  at insertion, not an mt76 driver/firmware defect (no firmware crash
  or repeated failures were observed). It was a **single, self-resolved
  event**, not a repeating pattern - stable for the remainder of the
  session afterward, including through ~15+ seconds of live AP
  beaconing with no new errors and no change in the throttled reading.
  **Record this caveat prominently in any future troubleshooting** so
  a future USB reset or disconnect on this adapter is checked against
  the Pi's chronic power condition before being treated as an mt76
  defect.
- **NetworkManager/ownership:** `wlan1` shows as NetworkManager-managed
  (`unmanaged-devices` in `/etc/NetworkManager/conf.d/99-piratebox.conf`
  - a live-only file, not tracked in this repo - currently excludes
  only `wlan0` by name) but NetworkManager's own wifi radio switch
  (`nmcli radio wifi`) is globally `disabled`, so nothing auto-connected
  it during this round. Not yet given the same explicit unmanaged
  exclusion as `wlan0` - worth doing before any future production
  migration, not required for this evaluation round.
- **Core dependency:** No, if adopted - `wlan0` is the documented
  fallback throughout the evaluation, and stays the current production
  AP unless/until a deliberate, separate migration decision is made
  after successful isolated testing and operator RF verification.
- **Isolated test artifacts:** temporary, non-persisted (killed/removed
  after verification, no systemd unit, no production file touched) -
  hostapd config and IP assignment lived only in this session's job
  tmp directory and a live `ip addr`/`hostapd` process, not the repo or
  `/etc/`.
- **Notes:** no maximum-client-count, range, or throughput claims are
  made - not tested, not assumed. The MAC address observed this
  session is transient adapter-instance information and is
  deliberately not recorded here.

### ALFA ARS-N19 (2.4GHz antenna)

- **Purpose:** antenna for the AWUS036ACM evaluation.
- **State:** **OWNED / INCOMING - operator-asserted during this
  documentation session; not previously recorded in any existing repo
  doc, and not independently verifiable via a live check (antennas
  don't enumerate on USB).** Recorded here on the operator's own
  statement, consistent with `docs/ARCHITECTURE.md` §5's provenance
  convention - flagged as newly-recorded rather than presented as
  independently confirmed.
- **Notes/unknowns:** whether this is the only antenna intended for the
  AWUS036ACM (which ships with two RP-SMA connectors) is not stated
  anywhere; not assumed here either way.

### GPIO25 shutdown button

- **Purpose:** safe hold-to-shutdown physical control.
- **Layer:** Core (per `docs/ARCHITECTURE.md` §2 - "shutdown/basic
  status" is explicitly Core).
- **State:** INSTALLED, CURRENT SCOPE - wired, electrically verified,
  implemented, and confirmed through a real full power-cycle test on
  standalone power (`docs/HARDWARE-INTEGRATION-DESIGN.md` §2,
  `docs/OPERATIONAL-DECISIONS.md` "Stage 29" entries).
- **Interface:** GPIO25 / physical pin 22, other leg on pin 9 (GND).
- **Software owner:** `piratebox_button_daemon.py` /
  `piratebox-button.service`.
- **Core dependency:** is itself a Core safety primitive.
- **Failure behavior:** fails toward inaction by design (real shutdown
  gated behind an explicit enable flag, armed only after full
  verification - see the Stage 29 entries).
- **Privacy sensitivity:** none.
- **UI exposure:** none (physical-only today; a future OLED confirmation
  screen is designed, not built - `docs/PHYSICAL-CONTROL-UX-DESIGN.md`
  §3).

### Toggle switch (Normal/Emergency presentation, GPIO17)

- **Purpose:** physical Normal/Emergency Mode selector, replacing the
  current software-only `set_piratebox_mode.sh` toggle.
- **Layer:** Operational (interface to a Core concept - Core's mode
  switching already works fully via software without this hardware).
- **State:** OWNED / INCOMING - hardware ordered, **not yet wired**
  (`docs/HARDWARE-INTEGRATION-DESIGN.md` §2: "Not wired").
- **Interface:** GPIO17 / physical pin 11, internal pull-up, switch to
  GND.
- **Core dependency:** No - `set_piratebox_mode.sh` remains fully
  functional regardless.
- **Failure behavior:** falls back to software toggle; Normal/Emergency
  mode itself always fails safe to Normal if its state can't be read
  (existing behavior, independent of this switch).

### Momentary buttons, GPIO22/23/24/27

- **Purpose:** OLED page-cycle (GPIO22, planned), display-wake
  (GPIO23, planned); GPIO24/GPIO27 explicitly **reserved,
  unassigned** - "don't invent a job for a button that doesn't have
  one yet" (`docs/PHYSICAL-CONTROL-UX-DESIGN.md` §2).
- **Layer:** Operational.
- **State:** OWNED / INCOMING - hardware ordered (part of the same
  5-button STARELO set GPIO25 came from), not yet wired.
- **Core dependency:** No.
- **Failure behavior:** no function assigned yet to 2 of the 4, so
  nothing to fail; the 2 assigned functions (cycle/wake) are OLED-
  dependent and inherit the OLED's own degrade-not-disable behavior.

### OLED display (SSD1306 0.96" 128x64, I2C)

- **Purpose:** compact glanceable status - Status/Time/Network/Health
  page cycle (`docs/PHYSICAL-CONTROL-UX-DESIGN.md` §1, updated to a
  4-page cycle including Time - see `docs/FIELD-TOOLS-DESIGN.md` §11).
- **Layer:** Operational.
- **State:** **INSTALLED, CURRENT SCOPE (2026-09-03)** - physically
  wired (GPIO2/SDA, GPIO3/SCL, VCC on 3.3V/pin 1, GND on pin 14),
  I2C1 enabled, confirmed responding at address 0x3C via `i2cdetect`
  and a real test frame visually confirmed. `piratebox_oled_daemon.py`
  / `piratebox-oled.service` implemented and running - see
  `docs/HARDWARE-INTEGRATION-DESIGN.md` §12 for the full bring-up
  record.
- **Interface:** I2C1 (GPIO2/SDA, GPIO3/SCL) - reserved, fixed function,
  not usable for anything else once enabled.
- **Core dependency:** No - AP/site are fully independent of this
  display by design (`docs/ARCHITECTURE.md` §2); verified in practice,
  not just by design - the daemon runs as a separate, unprivileged
  systemd service with no PirateBox process depending on it.
- **Failure behavior:** implemented as designed - the daemon retries on
  a fixed interval if the display is missing/unreachable at startup or
  disappears mid-run, never crash-loops, never busy-polls, and writes
  no PirateBox data file (every data source it reads is read-only). See
  the daemon's own header comment for the full contract.
- **Interim departures from the full §1/§5 design, both explained in
  the daemon's header and in `docs/PHYSICAL-CONTROL-UX-DESIGN.md` §1/
  §5 directly:** pages auto-rotate on a timer rather than a cycle
  button (GPIO22 not wired yet), and auto-dim-after-idle is not enabled
  (GPIO23 wake button not wired yet - dimming with no way to wake it
  would be a regression, not a power-saving improvement). Both are
  additive, button-driven upgrades once that hardware exists - no
  redesign needed.
- **Live capability signal:** `capability_state.php`'s `oled` entry now
  reads `piratebox-oled.service`'s live systemd state (via
  `piratebox_status_helper.sh` -> `status.json`'s new `hardware.
  oled_service_active` field) rather than a hardcoded NOT_INSTALLED -
  see `piratebox_classify_oled()`'s own doc comment for the honest
  limit of what this signal can confirm (service running, not
  necessarily the physical display responding).
- **Privacy sensitivity:** physical/operational (§8's Normal/Attention/
  Warning/Critical concept could apply to a future richer display) -
  today's four pages show only already-public-facing facts (mode,
  SSID, client count, service health, storage, uptime, power state) -
  nothing not already visible on the Stats/About pages to anyone on the
  network.
- **Silly Mode (added 2026-09-04):** an optional, user-toggleable
  (`piratebox-silly {on,off,status}`, default OFF every boot),
  substantially more expressive face/personality display state layered
  on top of the four pages above - never a fifth operational mode, and
  always subordinate to Emergency Mode / a real fault
  (`compute_display_tier()`: emergency > fault > warning-with-badge > ok).
  Replaces the earlier always-on "Personality Mode" (round 7/8), which
  is removed. Reacts to client join/leave, idle duration, and (via a
  single cheap `/proc/net/tcp` read, no logging) whether an SSH session
  is currently established. Full rationale: `docs/OPERATIONAL-
  DECISIONS.md` → "OLED Silly Mode"; design detail: the daemon's own
  "SILLY MODE" header comment.
- **Progression (added 2026-09-04):** a persistent XP/level/title/
  achievement/lifetime-statistics layer underneath Silly Mode, in its
  own module (`piratebox_progression.py`) - durable at `/var/lib/
  piratebox-oled/progression.json`, survives reboot and Silly Mode
  being off, never unlocks or gates any core capability (cosmetic-only
  rewards throughout). Anti-farming (cooldowns/daily caps) and privacy
  (aggregate-only client counts, no MAC/IP/identity ever touched) both
  by construction, not policy alone. Includes a rarity-tiered event/
  reaction engine (common/uncommon/rare/legendary/secret alternates for
  situations Silly Mode already reacts to) and a `HARDWARE_SIGNALS`
  extension-point registry for the not-yet-commissioned sensors listed
  in `docs/HARDWARE-INTEGRATION-DESIGN.md` §5 - currently empty, no
  reading fabricated for anything not actually wired. Full rationale:
  `docs/OPERATIONAL-DECISIONS.md` → "PirateBox Progression" (deliberately
  stops at the architecture level - hidden achievements and exact
  rare-event triggers are not spoiled there or here, per instruction).
- **Captain's Log web profile (added 2026-09-04):** a read-only site
  page (`/utility/captains-log/`, linked from the Utility hub)
  presenting the above to visitors - identity, level/title, XP
  progress, lifetime stats, discovered achievements, personality
  traits (as labels, never raw weights), and a sparse chronological
  log. No reset/import/debug/force-event operation is reachable from
  the web - those stay CLI-only. Reads Progression's own public export
  (`/run/piratebox/progression-public.json`, published by
  `piratebox_status_helper.sh` from `build_public_summary()`) rather
  than the raw durable file - no filesystem permission was loosened to
  make this possible; one narrow, explicit `open_basedir` addition
  (one named file, not a directory) was needed instead. Full rationale:
  `docs/OPERATIONAL-DECISIONS.md` → "Captain's Log web profile".

### Undervoltage / power-quality monitoring (software)

- **Purpose:** detect and report Pi power-supply undervoltage/
  throttling.
- **Layer:** Operational.
- **State:** INSTALLED, CURRENT SCOPE - live today via `vcgencmd
  get_throttled`, surfaced in `piratebox_status_helper.sh` ->
  `/run/piratebox/status.json` -> the Stats page.
- **Core dependency:** No - purely informational.
- **Failure behavior:** already honest - `throttled_hex: "unavailable"`
  if `vcgencmd` can't be read, never a fabricated healthy reading.
- **Real, currently-open finding:** an undervoltage condition was
  directly observed live on the standalone wall-brick power source used
  for the Stage 29 hardware test (`docs/OPERATIONAL-DECISIONS.md`,
  "Stage 29 Real-Hardware Confirmation") - **this remains an open,
  unresolved caveat about that specific power source**, not something
  this document resolves. No UPS/power hardware decision has been made
  because of it.
- **Recurrence, 2026-09-03 (OLED bring-up session):** immediately
  before the OLED I2C bring-up, an abnormal episode (SSH became
  extremely slow, the GPIO25 hold-to-shutdown did not trigger, ending in
  a hard power cycle) was investigated on the next boot. `vcgencmd
  get_throttled` read `0x50005` (under-voltage detected right now,
  throttling occurred since boot) with 4 separate kernel-log
  "Undervoltage detected!" events in the first ~4 minutes of that boot -
  this is very plausibly the actual explanation for the stall
  (CPU throttling can starve any process's scheduling, including a
  GPIO-watching daemon, without indicating a software defect in it).
  Everything else checked (filesystem, systemd units, dmesg for USB/
  network errors) was clean - this is specifically a power-supply
  headroom problem, not a broader fault, and is **not attributed to the
  OLED itself** (a few mA of added draw, and the condition was observed
  before the OLED daemon was even running). See
  `docs/HARDWARE-INTEGRATION-DESIGN.md` §12 for the full record. Still
  unresolved on this power source; still no UPS/power hardware decision
  made.
- **Root-cause diagnosis (2026-09-03, Power Integrity Diagnosis +
  Undervoltage Root-Cause Round):** full investigation in
  `docs/POWER-INTEGRITY-DIAGNOSIS.md` - independently reconfirmed the
  bit semantics from this system's own `man vcgencmd` (bits 0/2 are
  *current*-condition, not just sticky), found the condition is
  chronic and *currently active* every time it's been checked across
  weeks of project history, and found a real, previously-unrecorded
  oscillation pattern (rapid detect/normalise flipping) during this
  round's own boot. Evidence points toward the external supply/cable
  path (downstream Pi-regulated rails stay nominal while the input-side
  detector trips - the fingerprint of an upstream, not on-Pi, headroom
  deficit) - not proven without a physical A/B supply swap, which
  wasn't performed. **Confirmed the AWUS036ACM does not materially
  worsen this** (identical `0x50005` before/after/throughout every ALFA
  test on both bands). Investigated and could not confirm a fan-stall
  root cause - physically plausible as a contributing transient, but
  undervoltage demonstrably occurs with no fan interaction, ruling it
  out as sole cause. This round is diagnosis only - nothing physical
  was changed, and the AWUS036ACM production migration's power-aware
  gate remains unmet.
- **Retention:** live/current state (`status.json`) plus a real,
  already-existing persisted counter - `var/www/html/data/
  device-history.json`'s `undervoltage_daily` (daily-bucketed event
  counts, e.g. 5 events recorded for the UTC-day spanning this round's
  own checks). **Correction to this entry's own prior claim** ("no
  persisted undervoltage-event history... not designed/built now") -
  that was stale; this persistence already exists live, found during
  this round's diagnosis. `boot_events` in the same file remains an
  empty array - not currently populated from real boot transitions,
  unfixed, noted for a future pass.

### UPS / battery hardware

- **Purpose:** seamless power-path battery backup for the Pi + AP
  adapter, both stationary and portable use.
- **Layer:** Operational.
- **State:** CANDIDATE - `docs/POWER-UPS-DESIGN.md` (Stage 12) is a
  **requirements document only**; explicitly, "no power/UPS hardware
  has been selected or purchased."
- **Interface:** TBD (candidate evaluation criteria only - true power-
  path management, not simple switchover; sized for Pi + external AP
  adapter combined load).
- **Core dependency:** No.
- **Notes:** directly relevant to the undervoltage finding above, but
  no product has been chosen or purchased.

### RTC (Real-Time Clock)

- **Purpose:** battery-backed absolute time across power-off, closing
  the gap `docs/RTC-TIME-READINESS-DESIGN.md` (Stage 28) identified (no
  hardware RTC today - the Pi's clock starts every boot from whatever
  gets there first: NTP, unavailable by design here; `fake-hwclock`,
  not installed; or an uncontrolled kernel/filesystem default).
- **Layer:** Operational.
- **State:** **PLANNED, not purchased.** DS3231 is the specific chip
  named repeatedly (`docs/RTC-TIME-READINESS-DESIGN.md` §3's candidate
  table originally listed it as one example among standard I2C RTC
  breakouts, e.g. DS3231/PCF8523; `docs/FIELD-TOOLS-DESIGN.md` and
  `docs/PHYSICAL-CONTROL-UX-DESIGN.md` now refer to it as *the* planned
  part) - **planned means "this is the specific part intended when RTC
  hardware is purchased," not "already purchased."**
- **Interface:** I2C1, same bus as the OLED (multi-drop, no pin
  conflict).
- **Core dependency:** No.
- **Failure behavior:** already built and live today, ahead of the
  hardware itself -
  `piratebox_get_time_source_status()`
  (`includes/fieldtools_time.php`) reports `rtc_detected: false`
  honestly right now, and is written to flip to `true` with **zero
  code changes** the moment a real RTC's kernel device appears at
  `/sys/class/rtc/` (`docs/FIELD-TOOLS-DESIGN.md` §4). This is the
  concrete, already-shipped example of `docs/ARCHITECTURE.md` §2's
  "optional capability failure degrades, doesn't disable" rule.
- **UI exposure:** `/utility/fieldtools/time/` already shows this
  status live; a future OLED Clock page is specified to show the same
  underlying data (`docs/PHYSICAL-CONTROL-UX-DESIGN.md` §1).

### `fake-hwclock` (software time fallback)

- **Purpose:** "last known good" time across a reboot with no RTC and
  no network, closing most of the practical clock-trust gap at zero
  hardware cost.
- **Layer:** Operational.
- **State:** CANDIDATE - recommended in `docs/RTC-TIME-READINESS-
  DESIGN.md` as the near-term fix, **not installed** (would require a
  package-install approval this project's standing rule requires be
  explicit and separate).
- **Core dependency:** No.

### Self-awareness / capability-state model (software)

- **Purpose:** a single, tested, truthful answer to "what does this
  device have, and is it working" - `docs/ARCHITECTURE.md` §6/§10 moved
  from principle to implementation.
- **Layer:** Operational.
- **State:** INSTALLED, CURRENT SCOPE - `includes/capability_state.php`
  (`piratebox_get_capability_state()`/`piratebox_get_operational_
  state()`), covering the 12 capabilities in this registry that have a
  live or config-based signal today, each also carrying `provider`/
  `provider_class` (`docs/ARCHITECTURE.md` §3) and, where recognized,
  a `piratebox_diagnose_capability()` explanation (`docs/ARCHITECTURE.md`
  §13 - graceful self-diagnosis, first slice). Tested:
  `tools/test_capability_state.php` (40 deterministic assertions on the
  pure classification/diagnosis functions - null/missing-data/stale/
  degraded/unrecognized-id cases, not just the happy path).
- **Core dependency:** No - reads through the exact same channels every
  other page already uses (`includes/metrics.php`'s
  `piratebox_get_helper_status()`, `includes/fieldtools_time.php`), no
  new hardware/filesystem access, no new `open_basedir` exposure.
- **UI exposure:** public layer-level summary (`/utility/about/`);
  full per-capability detail behind the existing admin password
  (`admin/index.php`, "Capabilities & Health").
- **Notes:** deliberately does not enumerate every Optional/Field
  candidate individually in code - one honest "0 installed, see the
  registry" summary entry instead, avoiding a second copy of this whole
  document living in PHP.

### About This PirateBox page (software)

- **Purpose:** first real step toward `docs/ARCHITECTURE.md` §17's
  self-describing-device goal.
- **Layer:** Operational.
- **State:** INSTALLED, CURRENT SCOPE - `/utility/about/`, public,
  reads `includes/capability_state.php`. Deliberately excludes anything
  the existing public Stats page (`/utility/status/`) already treats as
  operator-only (power/undervoltage detail, per-capability breakdown) -
  follows that page's existing exposure boundary rather than setting a
  new one.
- **Core dependency:** No.
- **Notes:** does not yet cover wiring assignments, the ownership/
  recovery concept, or maintenance/repair information - see
  `docs/ARCHITECTURE.md` §17 for what remains future work.

### Reference Pack model (software)

- **Purpose:** self-awareness extended to content/resources, not just
  hardware - `docs/ARCHITECTURE.md` §14, `docs/REFERENCE-CONTENT-
  DESIGN.md`.
- **Layer:** Operational.
- **State:** INSTALLED, CURRENT SCOPE - `data/reference-packs.json` +
  `includes/reference_packs.php`, live on `/utility/about/`. Tested:
  `tools/test_reference_packs.php` (15 assertions - missing/malformed/
  empty file cases, the Local Information special-case counting rule).
- **Core dependency:** No.
- **Notes:** registers existing content (Radio/Emergency/First Aid/
  Maps-universal/Local Info/Library/map catalog); does not add any new
  reference content itself - see `docs/REFERENCE-CONTENT-DESIGN.md` §5
  for why new map/geographic content was deliberately not bundled.

### Device Memory - bounded event history (software)

- **Purpose:** "what happened while I wasn't looking" - `docs/DEVICE-
  MEMORY-DESIGN.md`.
- **Layer:** Operational.
- **State:** write side (`piratebox_status_helper.sh`) installed live
  2026-09-02 (byte-identical, confirmed). A separate systemd-sandboxing
  bug found during that install's verification - `piratebox-status.
  service`'s `ProtectSystem=strict` had no write exception for
  `var/www/html/data/`, so every write there (this feature's, and
  pre-existing connection-stats') silently failed - has been **fixed
  and live-verified** (`ReadWritePaths=/var/www/html/data`, installed
  by the operator, the next hourly connection-stats rollover wrote
  successfully with zero journal errors): see `docs/OPERATIONAL-
  DECISIONS.md`, "Connection-Stats Persistence Bug Found + Fixed," for
  the full account. **This feature's own write (`data/device-history.
  json`) shares that same fix but is reasoned-fixed, not yet
  independently observed** - its trigger is a boot or undervoltage-
  onset edge event, neither of which has recurred since the fix was
  installed; confirmed the next time either happens. Read side
  (`includes/device_memory.php`, 27 test assertions) is live and
  correctly reports `available: false` until that first write actually
  succeeds - not fabricated ahead of it. **"Since last review" boundary
  logic is real and tested** (`data/review-boundary.json`,
  `mark_reviewed` admin action) but has nothing to summarize yet for
  the same reason.
- **Core dependency:** No.
- **Privacy sensitivity:** low - boot timestamps and undervoltage-event
  counts only, both Operational History class, never raw per-second
  telemetry (`docs/DEVICE-MEMORY-DESIGN.md` §4).
- **UI exposure:** operator-only (`admin/index.php`, "Operational
  history") - raw event counts are diagnostic, not public-safe framing.

### Physical transport lock

- **Purpose:** make the physical control panel inert while carried
  (backpack/transport) - `docs/PHYSICAL-CONTROL-UX-DESIGN.md` §4.2.
- **Layer:** Operational.
- **State:** CANDIDATE - design concept only. No lock switch/mechanism
  purchased; the enclosure/panel isn't finalized. Reported honestly as
  `NOT_INSTALLED` by `includes/capability_state.php` today, not a
  fabricated `LOCKED`/`ENABLED` state.
- **Core dependency:** No - and must remain No by design once built
  (`docs/PHYSICAL-CONTROL-UX-DESIGN.md` §4.2).
- **Notes/unknowns:** exact mechanism (dedicated switch, gesture, or
  combination) not decided; whether GPIO25 shutdown stays available
  while locked is explicitly flagged as unresolved
  (`docs/PHYSICAL-CONTROL-UX-DESIGN.md` §4.4).

### Field Tools (time/date, unit conversion, coordinates)

- **Purpose:** offline field-instrument role - time/date tools, unit
  conversion, coordinate conversion.
- **Layer:** Operational (a field instrument, not part of what makes
  the AP/site/community features work).
- **State:** INSTALLED, CURRENT SCOPE - live at `/utility/fieldtools/`.
  Full detail: `docs/FIELD-TOOLS-DESIGN.md`.
- **Core dependency:** No.
- **Privacy sensitivity:** none - generic tools + this device's own
  system time, no home-location data; deliberately not gated by Travel
  Mode (`docs/FIELD-TOOLS-DESIGN.md` §5).
- **UI exposure:** public, same as the rest of `/utility/`.

### I2C multiplexer (PCA9548A / TCA9548A class)

- **Purpose:** candidate for resolving duplicate I2C addresses among
  future sensors, selectable branches, and some failure containment/
  diagnostic isolation (a wedged sensor on its own branch shouldn't
  take the whole bus down) - `docs/ARCHITECTURE.md` §4.
- **Layer:** Operational/infrastructure.
- **State:** CANDIDATE - not selected, purchased, or designed. Noted
  now, before it's needed, because it's cheap to reserve the concept
  and expensive to retrofit later.
- **Interface:** I2C1, same bus as OLED/RTC.
- **Core dependency:** No.

### GNSS receiver

- **Purpose:** position and/or accurate UTC.
- **Layer:** Optional/Field.
- **State:** CANDIDATE - no GNSS hardware exists on this device today;
  not mentioned in any prior doc before this session.
- **Core dependency:** No.
- **Privacy sensitivity:** **high** - see `docs/ARCHITECTURE.md` §7 in
  full. Position and time are architecturally separable outputs;
  position defaults private, no history, no cloud, no automatic
  embedding anywhere public.
- **UI exposure:** none today (no hardware). Future exposure states
  (Private/Approximate/Public) are conceptual only - `docs/
  ARCHITECTURE.md` §7.
- **Retention:** position availability and position *history* are
  separate questions - route capture would be Sensitive Capture class,
  opt-in only, never a side effect of using GNSS for time or a Home/
  Travel check. Full treatment: `docs/DEVICE-MEMORY-DESIGN.md` §8.

### Environmental sensing (temperature/humidity, beyond CPU temp)

- **Purpose:** ambient/outside conditions reporting.
- **Layer:** Optional/Field.
- **State:** CANDIDATE - no specific product chosen, nothing owned.
- **Core dependency:** No.
- **Privacy sensitivity:** low, unless correlated with position (see
  GNSS entry).

### Air quality (CO2 / particulate / VOC)

- **State:** CANDIDATE. No product chosen. Layer: Optional/Field. Core
  dependency: No.

### Light / UV

- **State:** CANDIDATE. No product chosen. Layer: Optional/Field. Core
  dependency: No.

### Motion / orientation (IMU)

- **State:** CANDIDATE. No product chosen. Layer: Optional/Field. Core
  dependency: No.

### Proximity (Time-of-Flight)

- **State:** CANDIDATE. No product chosen. Layer: Optional/Field. Core
  dependency: No.

### Sound measurement

- **State:** CANDIDATE. No product chosen. Layer: Optional/Field. Core
  dependency: No.

### Lightning detection

- **State:** CANDIDATE. No product chosen. Layer: Optional/Field. Core
  dependency: No.

### Radiation measurement

- **State:** CANDIDATE. No product chosen. Layer: Optional/Field. Core
  dependency: No. **Privacy sensitivity:** none directly, but see
  `docs/ARCHITECTURE.md` §8 - unusual electronics visible in an
  enclosure is itself an operational-discretion consideration
  regardless of the specific sensor.

### External isolated I/O

- **Purpose:** bounded interface for external circuits without
  exposing Core GPIO directly.
- **State:** CANDIDATE. Layer: Optional/Field. Core dependency: No.

### SDR (Malahit-derived receiver + RTL-SDR, owned; browser-SDR "Radio" capability)

- **Purpose:** wideband receive, complementary to (not a replacement
  for) `/utility/radio/`'s existing static reference content. Full
  investigation: `docs/RADIO-SDR-ARCHITECTURE-DESIGN.md`.
- **State:** Hardware itself is **OWNED** - a "Malahit DSP SDR
  V3" receiver (manufactured by HiDY, made in China - a documented
  clone/derivative of the Russian MALAHITEAM Malahit-DSP line, NOT a
  confirmed genuine original; own internal battery), an RTL-SDR dongle,
  and an MLA-50+ active loop antenna (separately powered) are owned and
  have all been connected and characterized at least once (2026-09-05).
  **Malahit**: a series of passive/read-only characterization passes -
  a USB enumeration pass (confirmed VID:PID `ffff:0737`, two USB Audio
  Class capture interfaces and two descriptor-identical CDC-ACM serial
  ports); a serial+audio pass that read-only-opened both serial ports
  (DTR/RTS held low, zero bytes transmitted - both silent, device
  unaffected) and briefly captured from both audio interfaces; and an
  on-screen-observation + known-frequency retest pass. Across two
  different tuned frequencies (455.000 MHz and 162.400 MHz, both with
  audible static confirmed at the speaker), the 160kHz stereo interface
  reproducibly streams cleanly and statistically resembles IQ
  (near-zero L/R correlation, balanced power, noise-like phase
  statistics matching the audible static), while the 40kHz mono
  interface reproducibly fails to stream every time, confirmed
  independent of tuned frequency, mode, and squelch state - cause
  still unknown. **RTL-SDR**: confirmed genuine `0bda:2838` (Realtek
  RTL2832U + Rafael Micro R820T, the most standard/best-supported
  RTL-SDR chipset combination), USB 2.0 High Speed. A receive sanity
  test via the kernel's own already-present V4L2 SDR driver (zero
  package installs) showed real, frequency-dependent signal variation
  with the MLA-50+ antenna attached, in that path's limited 0.3-3.2MHz
  direct-sampling range. **`rtl-sdr`/`librtlsdr0` (Debian trixie/main,
  no third-party source) were then installed with operator approval**
  - the only software installed for this capability so far. Confirmed
  via `rtl_test`/`rtl_sdr`: clean kernel-driver detach/reattach on
  every open/close (no blacklist needed - Debian's own package relies
  on `librtlsdr`'s runtime detach, not a modprobe blacklist), working
  gain control (fixed a real automatic-gain overload at 100.1MHz -
  51.7% of samples clipped at automatic gain, 0% at a manually-set
  8.70dB), and stable USB streaming at 3.2 Msps with no dropped
  samples. This is real tool-level evidence the standard OpenWebRX+
  software path works end-to-end on this exact unit and this exact Pi.
  **OpenWebRX+ (`luarvique/openwebrx`, pinned commit `2d60e894`) has
  since been installed and verified working end-to-end (2026-09-05,
  docs/RADIO-SDR-ARCHITECTURE-DESIGN.md section 13)**: a real simulated
  client (a minimal stdlib WebSocket client, matching the exact
  installed protocol source, not guessed) triggered `openwebrx.service`
  to launch `rtl_connector` with the configured gain/frequency/sample
  rate, open this exact RTL-SDR, detach the kernel driver, and stream
  219 binary FFT/waterfall/audio frames (216,910 bytes) plus live
  S-meter/temperature/CPU-usage telemetry back over the WebSocket -
  both directly against the backend and through the production
  `http://piratebox/radio/` nginx reverse proxy, with an identical
  result (213 frames, 211,290 bytes). One real config bug was found
  and fixed in the process (`fm-broadcast` profile's `start_freq` was
  out of range for its `center_freq` - both now agree on 100.1 MHz).
  Measured under one active client: `openwebrx` ~10-14% CPU,
  `rtl_connector` ~11-27% CPU (settling to ~12-13%), `throttled`
  unchanged at every sample, zero USB/kernel errors, zero ALFA/hostapd
  disruption. OpenWebRX+ itself binds to `127.0.0.1:8073` only, never
  directly reachable from `pb-ap` clients; its own built-in login
  system gates `/settings*` separately from the open visitor receiver
  page. **Human browser test confirmed (2026-09-05)**: real waterfall/
  audio UX at `http://piratebox/radio/`, an actual FM station audible
  with working browser audio, PirateBox itself remaining usable in
  another tab. **Broad manual retuning "added and confirmed" the same
  day - later found to be a false positive, see below.**
  `allow_center_freq_changes` was enabled (a general, visitor-facing
  setting, no admin login needed) plus a new "General SDR (Wide
  Tuning)" profile added; a protocol-level test reported three
  genuinely different, widely-separated bands (27.185/100.1/162.475
  MHz) streaming real data. **This result did not hold up**: every
  `setfrequency` call in that test omitted OpenWebRX+'s own required
  `magic_key` parameter, so every retune was silently dropped
  server-side and the receiver never left its starting frequency - see
  the §13.8 entry below for the real root cause and a corrected
  re-verification.
  **UI/integration gap found and fixed (2026-09-05, same day, see
  §13.7)**: a follow-up human browser test found that despite the
  (as it turned out, unverified) backend claim above, the *stock
  OpenWebRX+ frontend itself* has no control that ever sends a
  `setfrequency` message at all - confirmed by grepping every shipped
  `htdocs/*.js` file for `allow_center_freq_changes`/`setfrequency`
  and finding zero references. A visitor using `/radio/` directly was
  still stuck inside whatever ~2.048 MHz window the active profile
  started at. Fixed entirely on the PirateBox side, without touching
  OpenWebRX+'s own installed files: a new page,
  `var/www/html/public/utility/radio/live.php` (linked from the
  existing Radio Reference page, `/utility/radio/`), whose browser JS
  opens its own direct WebSocket to `/radio/ws/` and replicates the
  already-validated handshake/`selectprofile`/`setfrequency` protocol
  sequence against the `general-sdr` profile, then reloads the
  embedded `/radio/` iframe so its own display catches up. Offers both
  the same three confirmed-working presets (27.185/100.1/162.475 MHz)
  and free-form manual MHz entry, range-bounded client- and
  server-side to 24-1766 MHz (the R820T's documented practical range).
  No admin login, no manual config editing, no new backend endpoint.
  Degrades gracefully (a server-side TCP probe of OpenWebRX+'s
  loopback port shows a plain "not currently available" message
  instead of a broken page when the optional service/hardware is
  absent). **This page's own UI/protocol design was correct, but
  retuning still didn't work when tested live - see §13.8.**
  **Third human browser test found the receiver still pinned at
  ~100.1 MHz - real root cause identified and fixed, awaiting operator
  deploy + re-confirmation (2026-09-05, same day, see §13.8)**: the
  `< >` frequency-display arrows were confirmed (via
  `htdocs/lib/UI.js`) to be demodulator-offset-within-window controls
  only, never SDR retune controls - not the bug, but a real point of
  visitor confusion worth naming. The actual cause: OpenWebRX+'s
  `setfrequency` handler (`owrx/connection.py`) gates the only line
  that calls `setCenterFreq()` on `magic == "" or key == magic`, where
  `magic` is the configured `magic_key` - defaulting (`owrx/config/
  defaults.py`) to `"memagic"`, never set by this project's own config
  until now. `live.php` never sent a key (by design - no visitor
  secret was the whole point), so every retune request was silently
  dropped: no exception, no error, no config push. Confirmed
  empirically, not just by reading source: the identical call with
  `"key": "memagic"` added produced an instant, correct live update,
  and a corrected re-run of the three-band test (with the key
  included) produced genuine, distinct `center_freq` confirmations at
  all three targets. Fixed in `etc/openwebrx/sdrs_seed.py`:
  `magic_key = ""` (removes the gate entirely, so no client - `live.php`
  or any future stock-frontend control - needs to know any secret) and
  `max_clients` raised from 2 to 4 (unrelated to the pinning bug, but a
  real fragility: `live.php`'s design uses two concurrent connections
  by itself, leaving no headroom under the old limit). `live.php`
  itself needed no code change. **Not yet applied to the live
  system** - requires `sudo tools/update_openwebrx_config.sh`, a
  password-gated command outside this session's standing sudo grants;
  the operator needs to run it, then a genuine human browser
  click-through against `/utility/radio/live.php` is the actual close
  of this capability's retuning story.
  The RECEIVE CAPABILITY ITSELF (a browser-accessible SDR backend/UI,
  within a single profile's fixed ~2 MHz window) is **INSTALLED** for
  the RTL-SDR path specifically - confirmed working by both
  protocol-level tests and a real human/browser test. **Broad,
  visitor-driven retuning across widely-separated bands is fixed in
  the repo but not yet confirmed live** - the fix above is
  unapplied/unverified pending the operator step. Real unknowns remain
  (which Malahit serial port, if either, is CAT control and in what
  protocol; why the Malahit's 40kHz audio interface won't stream;
  whether any existing SDR-software Malahit support actually applies
  to that hardware variant - the Malahit path remains untouched,
  deliberately kept separate/experimental; two-simultaneous-client
  validation for the RTL-SDR path; `live.php` is linked from the Radio
  Reference page, not yet from the PirateBox homepage itself, and not
  yet reflected in `capability_state.php`) - see the design doc's own
  open-questions list. Layer: Optional/Field. Classification:
  Attachable (USB). Core dependency: No - confirmed live, not just by
  design: `pb-ap`/hostapd/dnsmasq/nginx were verified healthy
  throughout every OpenWebRX+ install/test/load/retune round.

### Ham-radio interface

- **State:** CANDIDATE. Layer: Optional/Field. Classification:
  Attachable or Network Companion, depending on the specific interface.
  Core dependency: No.

### Remote microcontroller/sensor node (e.g. ESP32)

- **Purpose:** the concrete example of a Network Companion device -
  independently powered, communicates over the PirateBox LAN.
- **State:** CANDIDATE - concept only, no specific project chosen.
- **Layer:** Optional/Field. Classification: Network Companion. Core
  dependency: No - **must be able to disappear without breaking Core**
  (`docs/ARCHITECTURE.md` §3).

### Another Pi / general companion node

- **State:** CANDIDATE - concept only. Layer: Optional/Field.
  Classification: Network Companion or Operator Device, depending on
  role. Core dependency: No.

---

## 4. What this document intentionally does not do

- It does not invent specifications, models, or purchase dates for any
  CANDIDATE item.
- It does not claim any Optional/Field capability is closer to real
  than "an idea worth tracking."
- It does not design discovery/pairing/trust for companion devices -
  see `docs/ARCHITECTURE.md` §3 for the constraints a future
  implementation must satisfy.
- It does not resolve the open undervoltage finding on the wall-brick
  power source - that remains a live, unresolved caveat (see the
  undervoltage entry above and `docs/OPERATIONAL-DECISIONS.md`, "Stage
  29 Real-Hardware Confirmation").

## 5. Maintenance note

Update this document, not `docs/ARCHITECTURE.md`, whenever a
capability's real-world state changes (purchased, arrived, wired,
tested, adopted, rejected, deferred). `docs/ARCHITECTURE.md` should
rarely need to change once a principle is settled; this document is
expected to change often as the project actually grows.
