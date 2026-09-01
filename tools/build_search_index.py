#!/usr/bin/env python3
"""Builds data/utility/search-index.json - the flat index the Global
Search page (Stage 8) searches client-side.

Re-run this any time content changes in Radio/Emergency/First Aid/Maps/
Local Info/Library: python3 tools/build_search_index.py

Reads the same JSON data files each section's own page already reads -
this does not duplicate content, it extracts a lightweight
{title, section, url, snippet, keywords} pointer to each item, plus a
direct #entry-id link where the underlying section page renders one (see
OPERATIONAL-DECISIONS.md, Stage 8, for the id/deep-link convention every
section page follows).
"""
import json
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "var/www/html/data/utility")
OUT_PATH = os.path.join(DATA_DIR, "search-index.json")


def load(*parts):
    path = os.path.join(DATA_DIR, *parts)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data


def entry(title, section, section_label, url, snippet, keywords=None, freq=None, regional=False):
    e = {
        "title": title,
        "section": section,
        "section_label": section_label,
        "url": url,
        "snippet": snippet,
        "keywords": keywords or [],
    }
    if freq:
        e["freq"] = freq
    if regional:
        # Post-Stage-32 (Travel Mode): marks an entry as region-specific
        # even though its "section" is a shared, mostly-universal one
        # (e.g. the maps catalog shares section="maps" with the generic
        # coordinate/GPS reference entries) - the live Search page filters
        # on this in addition to section="local" when Travel Mode is
        # active. Every entry actually IN the "local" section is already
        # covered by that section check alone; this flag exists only for
        # entries elsewhere that are still regional. See
        # includes/travel_mode.php.
        e["regional"] = True
    return e


index = []

# --- Radio ------------------------------------------------------------
for svc in load("radio", "services.json"):
    index.append(entry(
        svc.get("name", ""), "radio", "Radio Reference",
        f"/utility/radio/#{svc.get('id', '')}",
        svc.get("practical_note") or svc.get("transmit_note") or "",
        svc.get("keywords"), svc.get("freq_range"),
    ))
for m in load("radio", "modulation.json"):
    index.append(entry(
        m.get("name", ""), "radio", "Radio Reference",
        f"/utility/radio/#{m.get('id', '')}",
        m.get("explainer", ""), m.get("keywords"),
    ))
for g in load("radio", "guides.json"):
    index.append(entry(
        g.get("title", ""), "radio", "Radio Reference",
        f"/utility/radio/#{g.get('id', '')}",
        g.get("body", "")[:160], g.get("keywords"),
    ))

# --- Emergency ----------------------------------------------------------
for t in load("emergency", "topics.json"):
    index.append(entry(
        t.get("title", ""), "emergency", "Emergency / Outage Reference",
        f"/utility/emergency/#{t.get('id', '')}",
        t.get("summary", ""), t.get("keywords"),
    ))

# --- First Aid ------------------------------------------------------------
for t in load("firstaid", "topics.json"):
    index.append(entry(
        t.get("title", ""), "firstaid", "First Aid Reference",
        f"/utility/firstaid/#{t.get('id', '')}",
        t.get("summary", ""), t.get("keywords"),
    ))

# --- Maps -----------------------------------------------------------------
for t in load("maps", "reference.json"):
    index.append(entry(
        t.get("title", ""), "maps", "Maps & Location Reference",
        f"/utility/maps/#{t.get('id', '')}",
        t.get("summary", ""), t.get("keywords"),
    ))
for i, m in enumerate(load("maps", "catalog.json")):
    index.append(entry(
        m.get("title", "Untitled map"), "maps", "Maps & Location Reference",
        f"/utility/maps/#{m.get('id', f'map-{i}')}",
        m.get("description", ""), m.get("tags"),
        regional=True,
    ))

# --- Local Information ------------------------------------------------
local_info = load("local", "info.json")
if isinstance(local_info, dict):
    index.append(entry(
        "Local Information", "local", "Local Information",
        "/utility/local/",
        "Emergency management, NWS office, hospitals, shelters, amateur repeaters, and other resources for this PirateBox's current location.",
        ["local", "hospital", "shelter", "repeater", "emergency contact"],
    ))
    for n in local_info.get("emergency_numbers", []):
        index.append(entry(
            n.get("label", ""), "local", "Local Information",
            "/utility/local/",
            f"{n.get('number', '')} - {n.get('notes', '')}".strip(" -"),
            [n.get("label", ""), n.get("number", "")],
        ))
    for h in local_info.get("hospitals", []):
        index.append(entry(
            h.get("name", ""), "local", "Local Information", "/utility/local/",
            h.get("address", ""), ["hospital"],
        ))
    for s in local_info.get("shelters", []):
        index.append(entry(
            s.get("name", ""), "local", "Local Information", "/utility/local/",
            s.get("address", ""), ["shelter"],
        ))
    for r in local_info.get("amateur_repeaters", []):
        index.append(entry(
            r.get("callsign", "Repeater"), "local", "Local Information", "/utility/local/",
            f"{r.get('frequency', '')} - {r.get('location', '')}".strip(" -"),
            ["repeater", "amateur radio"],
        ))

# --- Document Library ----------------------------------------------------
for i, doc in enumerate(load("library", "catalog.json")):
    index.append(entry(
        doc.get("title", "Untitled document"), "library", "Document Library",
        f"/utility/library/#{doc.get('id', f'doc-{i}')}",
        doc.get("description", ""), doc.get("tags"),
    ))
# Always index the Library section itself, even if the catalog is empty,
# so a search for e.g. "manual" still points somewhere useful.
index.append(entry(
    "Document Library", "library", "Document Library", "/utility/library/",
    "Catalog of manuals and reference documents stored on this device.",
    ["manual", "document", "library", "pdf"],
))

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"wrote {OUT_PATH} ({os.path.getsize(OUT_PATH)} bytes, {len(index)} entries)")
