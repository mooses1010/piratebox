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

## 5. World Reference Map - built 2026-09-02, no longer CANDIDATE

Originally deferred here as CANDIDATE for a real, checked reason: this
Pi's own visitor-facing network has no general WAN path by design, and
this project's sourcing discipline (every reference entry cites a real,
cross-checked source - `sources.json`/per-entry `source_id`,
`confidence`, retrieval date) rules out bundling a map "because it's
probably fine" without one.

**That constraint was about this device's own network path, not about
every environment this project's tooling ever runs in.** Revisited
during an implementation-focused audit: Claude Code's own development
environment (distinct from the Pi's isolated visitor AP) has ordinary
outbound network access. Investigating that path rather than declaring
the feature permanently blocked found a genuinely solid source -
**Natural Earth's 1:110m Admin 0 Countries dataset, explicitly public
domain** ("No permission is needed to use Natural Earth. Crediting the
authors is unnecessary." - naturalearthdata.com Terms of Use, verified
directly this session) - fetched once from that environment, not from
the Pi, and not at any point during normal PirateBox operation.

**What was built:** `tools/build_world_reference_map.py` projects the
public-domain country-boundary coordinates (plain equirectangular - no
new library dependency, just `json` + arithmetic) into a single
self-contained SVG - `public/utility/maps/files/world-reference-map.svg`
(~180KB). Verified after generation, not just assumed correct: parsed
back as well-formed XML, and five geographically-spread countries'
rendered bounding boxes were checked against their real lon/lat ranges
and matched. Static, exactly as this section originally called for - no
slippy-tile engine, no map-server dependency, no live WAN reliance of
any kind after the one-time fetch. Lives in the Maps &amp; Location
Reference page's own always-visible "World Reference Map" section
(`public/utility/maps/index.php`) - deliberately outside the Travel-
Mode-gated operator map catalog, since this is universal content, not
regional. Full provenance: `data/utility/maps/sources.json`'s
`natural-earth-110m` entry; full account of the sourcing/verification
work: `docs/OPERATIONAL-DECISIONS.md`.

**The general lesson stands for future candidates too:** "no WAN path"
should be checked against the tooling environment actually available at
implementation time, not assumed to mean "unsourceable forever" - but
the sourcing discipline itself (real, checked, properly licensed
sources only) is unchanged and was not relaxed to get this done.

## 6. Graceful content availability

Confirmed live, not just designed: `/utility/about/`'s Reference
content table already shows exactly this shape today -

```
Universal   Navigation & Coordinates   INSTALLED (5)
Universal   World Reference Map        INSTALLED (1)
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

## 7. Four content tiers (formalized 2026-09-02)

The Deep Field Library's growth (radio/maps/first-aid/emergency/
computing reference pages, retained original documents, PirateBox-
authored diagrams) makes an implicit distinction worth stating
explicitly, so future work classifies new material consistently
instead of re-deriving the question each time:

1. **Original Source Material** - authoritative documents/assets
   retained verbatim (`/utility/library/`, `catalog.json`). Never
   edited/summarized in place; the point is that it's the real thing,
   with full provenance (e.g. DoD FM 4-25.11, NIST SP 432).
2. **PirateBox Reference Material** - concise definitions,
   explanations, tables, and reference cards *built from* verified
   sources, but not the source documents themselves (e.g. the AWG
   ampacity table, the US Time Zones table, every `reference.json`/
   `topics.json`/`guides.json` entry across the subject pages). Written
   originally, not mechanically copied prose, even when the underlying
   facts come from an authoritative source - a concise sourced
   explanation beats a pasted paragraph.
3. **PirateBox Original Material** - diagrams/explanations with no
   external source at all, because none was needed: the connector,
   antenna, declination, UTM/MGRS, electrical-symbol, and ground-to-
   air-signal SVGs are original schematics of generic/standardized
   forms (a resistor symbol, a compass bearing) - authored directly,
   same basis as writing an explanation, not a licensing question.
4. **External Copyrighted Reference** - material investigated and
   found useful for citation/research but not confirmed redistributable
   (ARRL band charts, Red Cross first-aid material). Cited by name
   (`source_id` -> `sources.json`) where it informed a Tier 2 entry's
   accuracy; never retained as a Tier 1 document, never mechanically
   reproduced as Tier 2 prose.

**Verification discipline stays per-item, not per-organization**: a
".gov" domain does not make every asset on it public domain (co-
authored/third-party content is the recurring exception - see NOAA's
non-federal-co-author caveat, §3b of `docs/IMPLEMENTATION-ROADMAP.md`)
and a government or standards body's *specific* publication still
needs its own license check even when the same organization's other
work is already confirmed clear (the ARRL band-chart-specifically
finding is the concrete example on record).

**Where a term fits which tier isn't always obvious in advance** - the
test is: would a reasonable person mind PirateBox writing its own
short explanation of this, sourced honestly? If yes (a specific
copyrighted diagram, a proprietary chart), it's Tier 4, cite-only. If
no (a standard's defined term, a physical law, a generic technical
concept), a Tier 2/3 PirateBox-authored explanation is both legally
fine and usually more useful than a retained PDF page for it - see §8
(Glossary) for where this tiering was first put into practice
end-to-end.

## 8. Glossary / terminology architecture (2026-09-02)

**Problem:** the library now has enough depth that a beginner
encountering "polarization," "CIDR," or "declination" mid-page has
nowhere offline to ask "what does that mean?" without either (a)
turning every subject page into a wall of inline hyperlinks/tooltips
(rejected - clutters the exact beginner-first pages this is meant to
help) or (b) re-explaining every term inline everywhere it's used
(rejected - duplicates content across pages, goes stale independently
in each place).

**Design chosen:** one small, centralized, searchable glossary page
(`/utility/glossary/`), built on the *exact same* reference-list
pattern already proven across Radio/Maps/Emergency/First
Aid/Computing (`<details>` accordion, `radioSearch`/`radioChips`,
`ref_search_blob`/`ref_source_line` helpers) - no new UI pattern, no
JavaScript beyond the same shared `scripts.js` filter/search behavior
every other reference page already uses, works with JS entirely off
(every entry is plain expandable HTML). No database: `data/utility/
glossary/terms.json` (array, same shape discipline as every other
reference data file) plus a sibling `sources.json`.

**Per-entry shape**, deliberately close to the existing `reference.json`
shape rather than inventing new field names for the same concepts:

```
{
  "id": "cidr",
  "title": "CIDR",                 // the term itself
  "summary": "...",                // AT A GLANCE - one plain sentence
  "quick_actions": ["..."],        // UNDERSTAND - 1-3 short points
  "related_pages": [{"url","label"}], // TECHNICAL/RELATED - link(s) to
                                       // the existing deeper reference,
                                       // not a re-explanation
  "keywords": ["cidr", "subnetting", "prefix length"], // aliases/abbreviations
  "source_id": "...", "confidence": "..."
}
```

`related_pages` intentionally reuses the exact field name/shape the
Document Library's `catalog.json` already uses for its own subject-
page cross-links - one convention for "this metadata names a page this
belongs with," not two competing ones.

**Deliberately NOT done:** no inline auto-linking of terms as they
appear in Radio/Maps/etc. body text (the "wall of hyperlinks" this
was designed to avoid), no tooltip/hover JavaScript, no full-text
search into retained PDFs. The connection back from a subject page is
one short, existing-pattern link (matching how Maps already points to
the Coordinate Converter, or how a Document Library cross-link box
works) - not scattered inline links.

**Search:** glossary terms are indexed by `tools/build_search_index.py`
exactly like every other reference entry - searching "DHCP" surfaces
the glossary definition through the existing search architecture, no
separate glossary-only search box.

**Self-description:** registered as a `reference-packs.json` entry
(`glossary-universal`) so `/utility/about/` truthfully reports how many
terms are actually defined, computed live like every other pack -
never a hardcoded claim.

## 9. Reference -> Tool (formalized 2026-09-02)

**Principle:** the library so far answers "what is this?" A reference
entry that names a deterministic, well-defined operation (convert
text to Morse, solve Ohm's Law, work out a subnet) can go one step
further and let the visitor actually *do* that operation offline,
right there. The progression is:

```
WHAT IS IT?  ->  UNDERSTAND IT  ->  REFERENCE IT  ->  USE IT
(glossary)       (guide/topic)      (table/chart)      (tool)
```

**This is not license to build a junk drawer of novelty
encoders/calculators.** The bar for adding a tool is the same bar
every other addition to this library already uses: *would someone
offline plausibly be glad it was here?* A subnet calculator clears
that bar for anyone doing field networking setup; a base64 encoder
clears it only if a concrete, recurring offline need for one actually
shows up - "technically possible to implement" is not sufficient
justification by itself.

**Requirements for any tool built under this principle:**
- Entirely offline, deterministic, local - no network/API call of any
  kind, ever (this is a stricter bar than "no *external* API" - not
  even a same-origin AJAX round trip to a server-side endpoint is
  needed when the computation is this cheap; see the implementation
  note below).
- **Core functionality works with JavaScript off** - a real server-
  rendered POST-and-redisplay path, not a JS-only widget with a
  "doesn't work without JavaScript" notice. JavaScript may *enhance*
  the same page (instant client-side conversion without a page
  reload), but the underlying logic must not fork into two
  independently-maintained implementations that can silently drift -
  see the shared-data-emission pattern used by the Morse converter
  (§ below in each tool's own page comment) for how this project
  avoids that.
- Graceful malformed input: never a crash/500, always a legible
  explanation of what was and wasn't understood - "silently invent a
  mapping" is explicitly disallowed; an unrecognized token is
  preserved/flagged, never guessed at.
- No duplication of an existing Field Tools calculator's job - a new
  tool either fills a genuinely new gap or it doesn't get built.
- Nothing entered into a tool is logged, stored in `$_SESSION`, or
  written to any PirateBox data file - computed and displayed for
  that one request only, same privacy posture as the rest of this
  device.
- Placed and linked the same way every other cross-reference in this
  library already works: the relevant guide/reference page links to
  the tool, the tool links back to the deeper reference/glossary term,
  search picks it up via the same metadata-driven indexing as
  everything else - no new discovery mechanism invented per tool.

## 10. What's deliberately not done

- No new map images/geographic data bundled (§5).
- No package-manager-style pack install/remove mechanism (§3).
- No Regional-scope packs (Texas, etc.) - no candidate content
  identified/sourced yet; the scope level exists in the hierarchy and
  is ready to use the moment real, sourced content exists for it.
- No change to Local Information's actual (empty) content - filling
  it in requires the operator's real-world data, unchanged from Stage
  6's own original position.
