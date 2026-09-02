# Reference Content & Reference Pack Design

**Status: ARCHITECTURE + FIRST IMPLEMENTATION.** The Reference Pack
model (`data/reference-packs.json`, `includes/reference_packs.php`) is
real, tested, and live - it registers and reports on content that
already existed; it does not itself add new geographic/map content
(see §5 for why that's deliberately deferred, not forgotten).

## 1. The principle

> **PIRATEBOX SHOULD CONTAIN USEFUL OFFLINE REFERENCE MATERIAL EVEN
> WHEN NO LOCATION-SPECIFIC CONTENT HAS BEEN CONFIGURED.**

Local information should **add** usefulness. It must never be the
**prerequisite** for usefulness. This was already true in practice
before this document existed - Radio/Emergency/First Aid Reference
(62 entries combined, all nationally-scoped, all sourced) and Maps'
coordinate/GPS reference (5 entries, universal) work regardless of
Local Information's state. This document makes that fact visible and
durable rather than incidental, and gives it a name: content is
organized

```
UNIVERSAL/GLOBAL -> COUNTRY/NATIONAL -> REGION/STATE -> LOCAL -> CURRENT/LIVE/DEVICE-DERIVED
```

Not every tool needs every level - this is a hierarchy to apply where
it fits (maps, geographic/navigation references, emergency references,
radio reference, weather/climate reference), not a mold to force
everything into.

## 2. Audit performed before writing anything

Checked actual content before designing around it, per this project's
"reconcile, don't assume" convention:

| Section | Entries | Scope | Sourced? |
|---|---|---|---|
| Maps - coordinate/GPS reference | 5 | Universal | Yes - USGS/NOAA/gps.gov (`data/utility/maps/sources.json`) |
| Radio Reference | 25 | National (US band plans) | Yes |
| Emergency/Outage Reference | 21 | National (Ready.gov/FEMA/CDC/NOAA/NFPA) | Yes |
| First Aid Reference | 16 | National (Red Cross/CDC) | Yes |
| Local Information | 0 configured (2 universal numbers ship by design) | Local | N/A - operator-provided |
| Document Library | 0 (empty by design) | Local | N/A |
| Maps catalog (actual map files) | 0 (empty by design) | Local | N/A |

**Conclusion confirmed, not assumed:** this project's Universal/National
layer is already substantial (67 sourced entries) and already fully
independent of Local Information, which was deliberately shipped empty
except two universal numbers (`docs/OPERATIONAL-DECISIONS.md`, Stage 6)
- not an oversight to fix, a documented choice that already satisfies
§1's principle. What was missing was making this *visible* as a
structure, not the underlying fact.

## 3. Reference Pack architecture (implemented)

`data/reference-packs.json` holds small, mostly-static metadata per
pack (id, title, scope, URL, source data file, license). **State is
never read from that file** - `includes/reference_packs.php`'s
`piratebox_get_reference_packs()` computes it live from the actual
underlying data file's real content (INSTALLED if it has real entries,
NOT_CONFIGURED if the framework exists but is empty, UNKNOWN if the
file is malformed - never a fabricated count), the same "observed
fact, never trusted claim" discipline `includes/capability_state.php`
already applies to hardware
(`docs/ARCHITECTURE.md` §6/§10/§14 - "self-awareness includes
information resources," extended here rather than duplicated: this is
a sibling module to `capability_state.php`, not a competing framework,
because content availability and hardware capability are different
kinds of fact worth keeping in separate small models).

`local-reference` is handled as a special case (not generic reflection)
- its two universal numbers don't count as "configured," matching Stage
6's own documented intent exactly.

**Not built:** a package manager. A pack today is exactly what §13 of
the originating request asked for and no more: a structured content
directory, metadata, source/license/availability, and UI grouping -
nothing installs, downloads, or removes a pack; adding one is still
"drop a file, add a data-file entry," unchanged from before this
document.

Surfaced on `/utility/about/` (public) as a Universal→Live table -
public-safe by construction, since it shows only pack titles/states/
scope, never Local Information's actual contents.

## 4. Small + durable + high value, not huge + comprehensive + stale

> Prefer **SMALL + DURABLE + HIGH VALUE** over **HUGE + COMPREHENSIVE +
> QUICKLY STALE.**

A useful world reference resource that stays useful for years beats
gigabytes of data that ages quickly. This project's existing content
(radio bands, first-aid guidance, coordinate math) already follows this
- none of it needs updating on any predictable schedule. Any future
addition should be held to the same bar.

## 5. Why no new map/geographic content was added now

**Deliberately deferred, not forgotten - `world-reference-map` is
recorded as CANDIDATE in `data/reference-packs.json`, not silently
dropped.** Two real constraints, checked rather than assumed:

- **No verified WAN/Internet path from this device.** PirateBox is an
  isolated access point by design (`docs/RTC-TIME-READINESS-DESIGN.md`
  already established this for the NTP-sync question; the same fact
  applies here) - there is no reliable way to fetch cartographic data
  from here.
- **This project's own sourcing discipline applies to new content the
  same as old.** Every existing reference entry cites a real,
  cross-checked source (`sources.json`/per-entry `source_id`,
  `confidence`, retrieval date). Bundling a map "because it's probably
  fine" without a real, checked source and clear redistribution rights
  would violate that discipline, not extend it.

**Static maps remain the right target format when this is eventually
done** - a slippy-tile server or map engine is not needed; a
well-chosen raster/SVG/PDF world or regional reference map, sourced and
licensed properly (public domain / permissively licensed / clearly
redistributable - never bundled merely because something is
downloadable), would be a genuinely valuable, low-complexity addition.
Not built now because it cannot be sourced responsibly from this
environment in this session - a real gap to revisit with either
operator-provided files or a future session with a verified path to
properly licensed data, not a permanent decision against it.

## 6. Graceful content availability

Confirmed live, not just designed: `/utility/about/`'s Reference
content table already shows exactly this shape today -

```
Universal   Navigation & Coordinates   INSTALLED (5)
Universal   World Reference Map        CANDIDATE
National    Radio Reference            INSTALLED (25)
National    Emergency/Outage Reference INSTALLED (21)
National    First Aid Reference        INSTALLED (16)
Local       Local Information          NOT_CONFIGURED
Local       Document Library           NOT_CONFIGURED
Local       Local/Regional Map Files   NOT_CONFIGURED
```

The absence of the Local layer doesn't empty the table or the site -
exactly §11's requirement, already true and now visible. Travel Mode
(`docs/TRAVEL-MODE-DESIGN.md`) continues to govern the Local layer
specifically - nothing here changes that boundary; Universal/National
material was already unaffected by Travel Mode (it reveals nothing
about the operator's home region) and remains so.

## 7. What's deliberately not done

- No new map images/geographic data bundled (§5).
- No package-manager-style pack install/remove mechanism (§3).
- No Regional-scope packs (Texas, etc.) - no candidate content
  identified/sourced yet; the scope level exists in the hierarchy and
  is ready to use the moment real, sourced content exists for it.
- No change to Local Information's actual (empty) content - filling
  it in requires the operator's real-world data, unchanged from Stage
  6's own original position.
