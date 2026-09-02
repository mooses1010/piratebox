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
| Built-in `wlan0` (production AP) | Core | INSTALLED, CURRENT SCOPE | Integrated |
| TP-Link TL-WN722N v2/v3 | - | INSTALLED (physically present); REJECTED as AP candidate | Attachable |
| ALFA AWUS036NHA (AR9271) | - | REJECTED as AP candidate (never purchased) | n/a |
| ALFA AWUS036ACM (MT7612U) | Core (if adopted) | OWNED / INCOMING | Attachable today; would become semi-permanent if adopted |
| ALFA ARS-N19 antenna | Core (if AWUS036ACM adopted) | OWNED / INCOMING (operator-asserted this session - see note) | Attachable |
| GPIO25 shutdown button | Core | INSTALLED, CURRENT SCOPE | Integrated |
| Toggle switch (Normal/Emergency, GPIO17) | Operational | OWNED / INCOMING | Integrated (planned) |
| Momentary buttons, GPIO22/23/24/27 | Operational | OWNED / INCOMING | Integrated (planned) |
| OLED (SSD1306 0.96" 128x64) | Operational | OWNED / INCOMING | Integrated (planned) |
| Undervoltage / power-quality monitoring (software, `vcgencmd`) | Operational | INSTALLED, CURRENT SCOPE | Integrated (software) |
| UPS/battery hardware | Operational | CANDIDATE (requirements only) | Integrated (if adopted) |
| RTC (DS3231) | Operational | PLANNED (chip chosen, not purchased) | Integrated (planned) |
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
| SDR (e.g. RTL-SDR) | Optional/Field | CANDIDATE | Attachable |
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
  production AP; until then it's an evaluation candidate.
- **State:** **OWNED / INCOMING - ordered, confirmed NOT yet arrived or
  tested** (`docs/OPERATIONAL-DECISIONS.md`; live `lsusb` on this
  session confirms it is not currently attached).
- **Interface:** USB. Expected driver `mt76x2u` (**expected, not
  verified** - explicitly flagged as unconfirmed in the source doc).
- **Core dependency:** No, if adopted - `wlan0` is the documented
  fallback throughout the evaluation, and stays the current production
  AP unless/until a deliberate, separate migration decision is made
  after successful isolated testing.
- **Failure behavior (planned test discipline):** an 8-step test plan
  exists (`docs/OPERATIONAL-DECISIONS.md`) - isolated `PirateBox-USB-
  Test` AP first, production `wlan0` untouched throughout, production
  migration only as an explicit separate step after success.
- **Notes:** no maximum-client-count is claimed for this adapter -
  explicitly not yet tested or researched, not assumed.

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
- **State:** OWNED / INCOMING - ordered, **no I2C/OLED code exists on
  this Pi yet**, not physically wired.
- **Interface:** I2C1 (GPIO2/SDA, GPIO3/SCL) - reserved, fixed function,
  not usable for anything else once enabled.
- **Core dependency:** No - AP/site are fully independent of this
  display by design (`docs/ARCHITECTURE.md` §2).
- **Failure behavior (designed, not yet built):** degraded-state display
  spec already written - honest "not reporting" rather than blank/stale
  fields (`docs/PHYSICAL-CONTROL-UX-DESIGN.md` §1).
- **Privacy sensitivity:** physical/operational (§8's Normal/Attention/
  Warning/Critical concept applies once built) - not yet a factor,
  nothing is displayed today.

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

### SDR (e.g. RTL-SDR)

- **Purpose:** wideband receive, complementary to (not a replacement
  for) `/utility/radio/`'s existing static reference content.
- **State:** CANDIDATE. Layer: Optional/Field. Classification:
  Attachable (USB). Core dependency: No.

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
