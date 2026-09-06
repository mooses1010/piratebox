# Vendored upstream OpenWebRX+ data - not PirateBox-authored

`bands.json` in this directory is **copied verbatim from the OpenWebRX+
project itself** (the `luarvique/openwebrx` fork this project already
installs and runs - see `tools/install_openwebrx.sh`), not written or
curated by PirateBox. It is checked into this repo only so a fresh
PirateBox install can reproduce OpenWebRX+'s own native "band plan"
feature without a manual, undocumented copy step - see
`docs/RADIO-SDR-ARCHITECTURE-DESIGN.md` section 14.3/15 for the full
investigation and design rationale.

## Provenance

- **Source repository**: `https://github.com/luarvique/openwebrx.git`
- **Source path**: `bands.json` (repository root)
- **Exact commit**: `2d60e894d0889382d2eb0574a19f027f8504dcfa` - the
  same commit this project already pins via `OPENWEBRX_COMMIT` in
  `tools/install_openwebrx.sh`. This file was copied directly from that
  exact checkout on this Pi (`/opt/openwebrx/src/openwebrx/bands.json`),
  confirmed identical via `git log -1 -- bands.json` against that commit
  and a `sha256sum` match - not retyped, not hand-edited, not sourced
  from a different version or a generic "OpenWebRX" project.
- **License**: OpenWebRX+ (`luarvique/openwebrx`) is licensed under the
  GNU Affero General Public License v3 (`LICENSE.txt` in that
  repository) - the same license already covering the rest of the
  OpenWebRX+ installation this project depends on and redistributes
  none of separately; vendoring this one data file changes nothing
  about this project's own licensing obligations beyond what already
  applies to running OpenWebRX+ itself.
- **What it is**: OpenWebRX+'s own default, region-independent ("region
  0") band plan - a flat list of named frequency ranges (amateur radio
  bands, shortwave/AM/FM broadcast bands, and public/service allocations
  like CB, PMR446, GMRS, ADS-B, VHF Air, VHF Marine) with no
  country-specific channelization and no geographic/GPS dependency.
  Deliberately NOT one of the region-specific variants
  (`bands-r1.json`/`bands-r2.json`/`bands-r3.json`, also present
  upstream) - region 0 matches this project's own config default
  (`bandplan_region` unset -> `0`) and avoids picking a specific ITU
  region for what is meant to stay a travel-safe, generic receiver.

## Keeping this in sync

If `OPENWEBRX_COMMIT` in `tools/install_openwebrx.sh` is ever bumped to
a newer upstream commit, re-copy this file from that new commit's own
`bands.json` at the same time (`git show <new-commit>:bands.json` against
a checkout of `https://github.com/luarvique/openwebrx.git`, or the
already-present build checkout under `/opt/openwebrx/src/openwebrx/`
after `tools/install_openwebrx.sh` has rebuilt against the new pin) -
don't let this file silently drift from the OpenWebRX+ version actually
installed.

## Do not hand-edit this file

If PirateBox ever wants its own curated, travel-aware band/service
annotations (see the Universal -> country -> region -> local -> live
content model in `docs/REFERENCE-CONTENT-DESIGN.md`), that belongs in a
clearly separate, PirateBox-authored file - not a modification of this
vendored copy, which should stay a faithful, easily-diffable mirror of
its upstream source.
