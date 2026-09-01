# Local Information schema

`info.json` is a single object (not a list) describing this PirateBox's
*current* deployment location. See `docs/OPERATIONAL-DECISIONS.md` (Stage
6, Stage 17) for the "don't fabricate local content" principle this file
follows - every array here ships empty until real, verified information
for wherever this box actually is gets added by hand.

## Top-level fields

- `region_label` - e.g. "Example County, ST". Empty until set.
- `last_updated` - date this file was last hand-edited, e.g. "2026-09-01".
- `notes` - free text, currently used for maintainer guidance.
- `emergency_management`, `nws_office` - single objects: `name`, `phone`,
  `website`, `notes`.
- `hospitals`, `shelters`, `amateur_repeaters`, `other_resources` - arrays,
  schema below.
- `emergency_numbers` - array of `{label, number, notes}` - the only
  section with any pre-filled content (911, Poison Control - both
  universal/non-regional).
- `radio_notes` - free text.
- `map_references` - array of `{title, note}` pointing at entries in the
  Maps catalog (`data/utility/maps/catalog.json`).

## Optional provenance fields (Stage 17)

Any entry in `hospitals`, `shelters`, `amateur_repeaters`, or
`other_resources` can include these three optional fields, on top of its
normal fields (`name`/`address`/`phone`/`notes` for hospitals/shelters;
`callsign`/`frequency`/`offset`/`tone`/`location`/`notes` for repeaters):

```json
{
  "name": "Example Regional Hospital",
  "address": "123 Main St, Example, ST",
  "phone": "555-0100",
  "notes": "Level II trauma center",
  "source": "Hospital's own published contact page",
  "verified": "2026-09-01",
  "confidence": "high"
}
```

- `source` - where this specific fact came from (a publisher/organization
  name is enough - not required to be a URL, though one is fine).
- `verified` - the date this entry was last confirmed accurate.
- `confidence` - `high` / `medium` / `low`, same scale the Radio/Emergency/
  First Aid/Maps datasets already use.

None of these three are required - use them for anything that could
plausibly go stale (a phone number, an hours-of-operation note) and skip
them for something you're confident is stable. When present, they render
on the Local Information page (`/utility/local/`) alongside the entry.

## Updating this file when the box moves

Edit only this file (`info.json`) - no PHP/HTML change is ever required.
`local/index.php` renders whatever this file contains, section by
section, with a clean empty-state message for anything still blank.
