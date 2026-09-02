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
for s in load("radio", "signal-identification.json"):
    index.append(entry(
        s.get("name", ""), "radio", "Radio Reference",
        f"/utility/radio/#{s.get('id', '')}",
        s.get("identifying_characteristics", "")[:160],
        [s.get("category", ""), "signal identification", "sigid"],
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
# World Reference Map: universal scope, NOT regional=True - unlike the
# operator map catalog above, this ships with PirateBox itself and must
# stay findable (and shown) during Travel Mode too.
for m in load("maps", "world-reference-map.json"):
    index.append(entry(
        m.get("title", "World Reference Map"), "maps", "Maps & Location Reference",
        f"/utility/maps/#{m.get('id', 'world-reference-map')}",
        m.get("summary", ""), m.get("keywords"),
    ))
# United States Reference Map: national scope, also NOT regional=True -
# same reasoning as the World Reference Map above.
for m in load("maps", "us-reference-map.json"):
    index.append(entry(
        m.get("title", "United States Reference Map"), "maps", "Maps & Location Reference",
        f"/utility/maps/#{m.get('id', 'us-reference-map')}",
        m.get("summary", ""), m.get("keywords"),
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

# --- Field Tools (Post-Stage-32) ------------------------------------------
# Hand-written, not data-file-driven - these are interactive tools, not a
# JSON reference catalog like every section above. No `regional` flag on
# any of these: nothing here is local/deployment-specific, so Travel Mode
# never needs to hide them (see includes/travel_mode.php).
for title, url, snippet, keywords in [
    ("Field Tools", "/utility/fieldtools/",
     "Time/date, unit conversion, and coordinate calculators for offline field use.",
     ["field tools", "calculator", "converter"]),
    ("Time & Date", "/utility/fieldtools/time/",
     "Current local/UTC time, ISO-8601, Unix timestamp, elapsed-time calculator, day of year.",
     ["time", "clock", "date", "utc", "iso 8601", "unix timestamp", "elapsed", "duration", "weekday", "day of year"]),
    ("Temperature Converter", "/utility/fieldtools/units/",
     "Celsius to Fahrenheit and back.",
     ["temperature", "celsius", "fahrenheit", "convert"]),
    ("Distance / Mass / Volume / Speed / Pressure Converter", "/utility/fieldtools/units/",
     "mm/cm/m/km/in/ft/yd/mi, g/kg/oz/lb, mL/L/US fl oz/cups/pints/quarts/gallons, mph/km/h/m/s, PSI/kPa/bar.",
     ["distance", "mass", "weight", "volume", "speed", "pressure", "convert", "units", "metric", "imperial"]),
    ("Storage / Percentage Converter", "/utility/fieldtools/units/",
     "Bytes/KiB/MiB/GiB/TiB, percentage-of and percent-change calculators.",
     ["storage", "bytes", "kib", "mib", "gib", "percent", "percentage", "ratio"]),
    ("Electrical & Battery Runtime", "/utility/fieldtools/units/",
     "Volts x Amps = Watts, amp-hours to watt-hours, and a theoretical battery runtime estimate.",
     ["electrical", "volts", "amps", "watts", "battery", "runtime", "power"]),
    ("Electrical Quick Reference", "/utility/fieldtools/units/",
     "Ohm's Law and power relationships, common copper wire gauge (AWG) ampacity reference.",
     ["ohms law", "ohm's law", "wire gauge", "awg", "ampacity", "resistance", "electrical reference"]),
    ("Coordinate Converter", "/utility/fieldtools/coordinates/",
     "Decimal degrees to/from degrees-minutes-seconds (DMS).",
     ["coordinates", "gps", "latitude", "longitude", "dms", "decimal degrees"]),
]:
    index.append(entry(title, "fieldtools", "Field Tools", url, snippet, keywords))

# --- About This PirateBox (self-description) --------------------------
index.append(entry(
    "About This PirateBox", "about", "About This PirateBox", "/utility/about/",
    "What this device is, what's installed, and its current health - the same public-safe status the Stats page already shows, organized around self-description.",
    ["about", "self-description", "capabilities", "what is this", "device info"],
))

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(index, f, indent=2, ensure_ascii=False)
    f.write("\n")

print(f"wrote {OUT_PATH} ({os.path.getsize(OUT_PATH)} bytes, {len(index)} entries)")
