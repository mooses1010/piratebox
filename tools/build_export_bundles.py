#!/usr/bin/env python3
"""Builds "Take This With You" static offline export bundles (Stage 19).

Reads the same JSON data files every live /utility/ section page already
reads (single source of truth for content), generates self-contained
static HTML for each section (relative links, no PHP/server dependency),
and packages everything into ZIP archives using Python's standard-library
zipfile module - deliberately NOT PHP's ZipArchive extension, which is not
installed on this system and would require a new package (a stop
condition this project's instructions call for approval before crossing).
This is also the architecture the stage instructions themselves prefer:
source data -> explicit build process -> cached/static export bundles,
built once here, never per-request.

EXPORT PRIVACY (hard rule, see docs/OPERATIONAL-DECISIONS.md Stage 19):
this script only ever reads from data/utility/* and generates content for
the 6 Utility sections. It never touches chat.json, messages.json,
recovery-messages.json, the admin htpasswd, uploads, or any system/
network configuration - there is no code path in this script that could
reach any of those, by construction (no file access outside data/utility/
and the fixed set of paths listed in OUTPUT/ASSET constants below).

Run: python3 tools/build_export_bundles.py
Output: var/www/html/public/utility/exports/ (static/ + *.zip + manifest.json)
"""
import csv
import io
import json
import os
import shutil
import zipfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "var/www/html/data/utility")
WEBROOT = os.path.join(REPO_ROOT, "var/www/html/public")
OUT_DIR = os.path.join(WEBROOT, "utility/exports")
STATIC_DIR = os.path.join(OUT_DIR, "static")


def load(section, name):
    path = os.path.join(DATA_DIR, section, name)
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def esc(s):
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def blob(*fields):
    parts = []
    for f in fields:
        if isinstance(f, list):
            parts.append(" ".join(str(x) for x in f))
        elif f:
            parts.append(str(f))
    return esc(" ".join(parts).lower())


PAGE_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<link rel="stylesheet" href="{assets}styles.css">
<script src="{assets}scripts.js"></script>
</head>
<body>
<div class="help-note" style="max-width:900px;margin:0.75rem auto;">
  <p><strong>Offline saved copy.</strong> This is a "Take This With You" export from a PirateBox, saved {date_note}. It works fully offline - no PirateBox, server, or Internet connection needed. Some live-only features (uploading files, chat, guestbook) aren't included, since they require an active PirateBox.</p>
</div>
<nav class="navbar"><a class="navbar-brand" href="{home}">PirateBox Offline Utility Library</a>
<ul class="navbar-menu">
<li><a href="{home}">Home</a></li>
<li><a href="{root}radio/index.html">Radio</a></li>
<li><a href="{root}emergency/index.html">Emergency</a></li>
<li><a href="{root}firstaid/index.html">First Aid</a></li>
<li><a href="{root}maps/index.html">Maps</a></li>
<li><a href="{root}local/index.html">Local Info</a></li>
<li><a href="{root}library/index.html">Library</a></li>
<li><a href="{root}search/index.html">Search</a></li>
</ul></nav>
<div class="radio-page">
"""

PAGE_TAIL = """
</div>
</body>
</html>
"""


def render_entry(entry_id, name, freq, badge, tx_badge, quick_actions, more_info, source_line, group, search_text):
    tx_html = f'<span class="radio-tx-badge {"tx-licensed" if tx_badge else "tx-open"}">{"License required to transmit" if tx_badge else "No license required to transmit"}</span>' if tx_badge is not None else ""
    freq_html = f'<span class="radio-entry-freq">{esc(freq)}</span>' if freq else ""
    qa_html = ""
    if quick_actions:
        qa_html = '<ul class="ref-quick-actions">' + "".join(f"<li>{esc(a)}</li>" for a in quick_actions) + "</ul>"
    more_html = f"<p>{esc(more_info)}</p>" if more_info else ""
    return f'''<details class="radio-entry" id="{esc(entry_id)}" data-group="{esc(group)}" data-search="{search_text}">
<summary><span class="radio-entry-name">{esc(name)}</span>{freq_html}<span class="radio-entry-mode-badge">{esc(badge)}</span>{tx_html}</summary>
<div class="radio-entry-detail">{qa_html}{more_html}<p class="radio-entry-source">{source_line}</p></div>
</details>
'''


def source_line(sources, source_id, secondary_id, confidence, note):
    bits = []
    if source_id and sources and source_id in sources:
        s = sources[source_id]
        name = esc(s.get("name", ""))
        if s.get("url"):
            bits.append(f'<a href="{esc(s["url"])}" target="_blank" rel="noopener">{name}</a>')
        else:
            bits.append(name)
    if secondary_id and sources and secondary_id in sources:
        bits.append("plus " + esc(sources[secondary_id].get("name", "")))
    out = "Source: " + ("; ".join(bits) if bits else "unspecified")
    if confidence:
        out += f' &mdash; confidence: <span class="radio-confidence confidence-{esc(confidence)}">{esc(confidence)}</span>'
    if note:
        out += f"<br>{esc(note)}"
    return out


def search_ui(placeholder, chips):
    chip_html = "".join(f'<button type="button" class="radio-chip" data-group="{esc(k)}">{esc(v)}</button>' for k, v in chips)
    return f'''<div class="radio-search-bar">
<input type="text" id="radioSearch" placeholder="{esc(placeholder)}" aria-label="Search">
<div class="radio-chip-row" id="radioChips"><button type="button" class="radio-chip active" data-group="all">All</button>{chip_html}</div>
</div>
<p class="radio-no-results" id="radioNoResults" hidden>No matches. Try a different search term or choose "All".</p>
<div id="radioResults">
'''


def write_page(rel_path, title, body, depth):
    root = "../" * depth
    assets = root + "assets/"
    home = root + "index.html" if depth else "index.html"
    full = PAGE_HEAD.format(title=esc(title), assets=assets, home=home, root=root,
                             date_note="from a live PirateBox") + body + PAGE_TAIL
    out_path = os.path.join(STATIC_DIR, rel_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(full)
    return out_path


def build_radio():
    services = load("radio", "services.json") or []
    modulation = load("radio", "modulation.json") or []
    guides = load("radio", "guides.json") or []
    sources = load("radio", "sources.json") or {}

    groups = {"amateur": [], "noaa-wx": [], "broadcast": [], "personal-radio": [], "marine-vhf": [], "airband": [], "railroad": []}
    cat_map = {"amateur": "amateur", "noaa-wx": "noaa-wx", "broadcast-am": "broadcast", "broadcast-fm": "broadcast",
               "broadcast-shortwave": "broadcast", "cb": "personal-radio", "frs": "personal-radio", "gmrs": "personal-radio",
               "murs": "personal-radio", "marine-vhf": "marine-vhf", "airband": "airband", "railroad": "railroad"}
    labels = {"amateur": "Amateur Radio Bands", "noaa-wx": "NOAA Weather Radio & Emergency Monitoring",
              "broadcast": "Broadcast Radio (AM/FM/Shortwave)", "personal-radio": "CB/FRS/GMRS/MURS",
              "marine-vhf": "Marine VHF", "airband": "Aviation/Airband", "railroad": "Railroad"}
    for svc in services:
        g = cat_map.get(svc.get("category"))
        if g:
            groups[g].append(svc)

    body = '<h1>Radio Reference</h1><p class="utility-breadcrumb"><a href="../index.html">&larr; Offline Utility Library</a></p>'
    body += search_ui("Search radio reference...", [(k, v) for k, v in labels.items()] + [("modulation", "Modulation"), ("guides", "Guides")])
    for gk, glabel in labels.items():
        if not groups[gk]:
            continue
        body += f'<section class="radio-group" data-group-section="{gk}"><h2 class="radio-group-heading">{esc(glabel)}</h2>'
        for svc in groups[gk]:
            search_text = blob(svc.get("name"), svc.get("freq_range"), svc.get("keywords"), svc.get("category"))
            body += render_entry(svc.get("id", ""), svc.get("name", ""), svc.get("freq_range"),
                                  svc.get("typical_receiver_mode") or "/".join(svc.get("common_modes", [])),
                                  svc.get("license_required_to_transmit"), None, svc.get("practical_note"),
                                  source_line(sources, svc.get("source_id"), svc.get("secondary_source_id"), svc.get("confidence"), svc.get("source_note")),
                                  gk, search_text)
            if svc.get("transmit_note"):
                body = body.replace("</div>\n</details>\n" + "", "</div>\n</details>\n", 0)  # no-op placeholder to keep structure simple
        body += "</section>"
    body += "<section class=\"radio-group\" data-group-section=\"modulation\"><h2 class=\"radio-group-heading\">Modulation Types</h2>"
    for m in modulation:
        search_text = blob(m.get("name"), m.get("keywords"))
        body += render_entry(m.get("id", ""), m.get("name", ""), None, "", None, None, m.get("explainer"),
                              source_line(sources, m.get("source_id"), None, m.get("confidence"), m.get("source_note")),
                              "modulation", search_text)
    body += "</section><section class=\"radio-group\" data-group-section=\"guides\"><h2 class=\"radio-group-heading\">Practical Guides</h2>"
    for g in guides:
        search_text = blob(g.get("title"), g.get("keywords"))
        body += render_entry(g.get("id", ""), g.get("title", ""), None, "", None, None, g.get("body"),
                              source_line(sources, g.get("source_id"), None, g.get("confidence"), g.get("source_note")),
                              "guides", search_text)
    body += "</section></div>"
    return write_page("radio/index.html", "PirateBox Radio Reference (Offline Copy)", body, depth=1), services, modulation, guides


def build_simple_section(section, data_file, groupmap, labels, title, id_field="id", title_field="title", summary_field="summary", qa_field="quick_actions", more_field="more_info"):
    topics = load(section, data_file) or []
    sources = load(section, "sources.json") or {}
    groups = {k: [] for k in labels}
    for t in topics:
        g = groupmap(t) if callable(groupmap) else t.get("category")
        if g in groups:
            groups[g].append(t)

    body = f'<h1>{esc(title)}</h1><p class="utility-breadcrumb"><a href="../index.html">&larr; Offline Utility Library</a></p>'
    body += search_ui(f"Search {title.lower()}...", list(labels.items()))
    for gk, glabel in labels.items():
        if not groups[gk]:
            continue
        body += f'<section class="radio-group" data-group-section="{gk}"><h2 class="radio-group-heading">{esc(glabel)}</h2>'
        for t in groups[gk]:
            search_text = blob(t.get(title_field), t.get(summary_field), t.get("keywords"), gk)
            body += render_entry(t.get(id_field, ""), t.get(title_field, ""), None, t.get(summary_field, ""), None,
                                  t.get(qa_field), t.get(more_field),
                                  source_line(sources, t.get("source_id"), t.get("secondary_source_id"), t.get("confidence"), t.get("source_note")),
                                  gk, search_text)
        body += "</section>"
    body += "</div>"
    return write_page(f"{section}/index.html", f"PirateBox {title} (Offline Copy)", body, depth=1), topics


def build_maps():
    reference = load("maps", "reference.json") or []
    sources = load("maps", "sources.json") or {}
    body = '<h1>Maps &amp; Location Reference</h1><p class="utility-breadcrumb"><a href="../index.html">&larr; Offline Utility Library</a></p>'
    body += search_ui("Search maps and location reference...", [("reference", "Reference")])
    body += '<section class="radio-group" data-group-section="reference"><h2 class="radio-group-heading">Coordinates, GPS &amp; Navigation Basics</h2>'
    for t in reference:
        search_text = blob(t.get("title"), t.get("summary"), t.get("keywords"))
        body += render_entry(t.get("id", ""), t.get("title", ""), None, t.get("summary", ""), None,
                              t.get("quick_actions"), t.get("more_info"),
                              source_line(sources, t.get("source_id"), t.get("secondary_source_id"), t.get("confidence"), t.get("source_note")),
                              "reference", search_text)
    body += "</section></div>"
    return write_page("maps/index.html", "PirateBox Maps & Location Reference (Offline Copy)", body, depth=1), reference


def build_local():
    info = load("local", "info.json") or {}
    body = '<h1>Local Information</h1><p class="utility-breadcrumb"><a href="../index.html">&larr; Offline Utility Library</a></p>'
    if info.get("region_label"):
        body += f'<p>Currently set for: <strong>{esc(info["region_label"])}</strong></p>'
    body += '<section class="help-section"><h2>Emergency Numbers</h2><div class="table-wrapper"><table><thead><tr><th>What</th><th>Number</th><th>Notes</th></tr></thead><tbody>'
    for n in info.get("emergency_numbers", []):
        body += f'<tr><td>{esc(n.get("label"))}</td><td>{esc(n.get("number"))}</td><td>{esc(n.get("notes"))}</td></tr>'
    body += "</tbody></table></div></section></div>"
    return write_page("local/index.html", "PirateBox Local Information (Offline Copy)", body, depth=1), info


def build_library():
    categories = load("library", "categories.json") or {}
    catalog = load("library", "catalog.json") or []
    body = '<h1>Document Library</h1><p class="utility-breadcrumb"><a href="../index.html">&larr; Offline Utility Library</a></p>'
    if not catalog:
        body += '<p class="empty-state">No documents were in the catalog when this copy was made.</p></div>'
    else:
        body += search_ui("Search documents...", list(categories.items()))
        groups = {k: [] for k in categories}
        for d in catalog:
            if d.get("category") in groups:
                groups[d["category"]].append(d)
        for gk, glabel in categories.items():
            if not groups[gk]:
                continue
            body += f'<section class="radio-group" data-group-section="{gk}"><h2 class="radio-group-heading">{esc(glabel)}</h2>'
            for d in groups[gk]:
                search_text = blob(d.get("title"), d.get("description"), d.get("tags"), gk)
                body += render_entry(d.get("id", ""), d.get("title", "Untitled"), None, d.get("file_type", ""), None,
                                      None, d.get("description"), f"Source: {esc(d.get('source',''))}", gk, search_text)
            body += "</section>"
        body += "</div>"
    return write_page("library/index.html", "PirateBox Document Library (Offline Copy)", body, depth=1), catalog


def build_search_page(all_indexed):
    body = f'<h1>Search</h1><p class="utility-breadcrumb"><a href="../index.html">&larr; Offline Utility Library</a></p>'
    body += f"<p>{len(all_indexed)} indexed items in this offline copy.</p>"
    body += search_ui("Search everything...", [("radio", "Radio"), ("emergency", "Emergency"), ("firstaid", "First Aid"), ("maps", "Maps"), ("local", "Local"), ("library", "Library")])
    for item in all_indexed:
        search_text = blob(item["title"], item.get("snippet", ""), item.get("keywords"), item["section"])
        link = f'../{item["section"]}/index.html#{item["id"]}' if item.get("id") else f'../{item["section"]}/index.html'
        body += f'<div class="radio-entry search-result-entry" data-group="{esc(item["section"])}" data-search="{search_text}">'
        body += f'<a class="search-result-link" href="{link}"><span class="radio-entry-name">{esc(item["title"])}</span><span class="radio-entry-mode-badge">{esc(item["section"])}</span></a>'
        if item.get("snippet"):
            body += f'<p class="search-result-snippet">{esc(item["snippet"])}</p>'
        body += "</div>"
    body += "</div>"
    return write_page("search/index.html", "PirateBox Search (Offline Copy)", body, depth=1)


def build_index():
    body = '''<h1>Offline Utility Library</h1>
<p>This is an offline saved copy of a PirateBox's Utility Library. Open any section below - everything works without Internet, a server, or the original PirateBox.</p>
<div class="utility-grid">
<a class="utility-card" href="radio/index.html"><span class="utility-card-icon">&#128246;</span><span class="utility-card-title">Radio</span></a>
<a class="utility-card" href="emergency/index.html"><span class="utility-card-icon">&#128680;</span><span class="utility-card-title">Emergency</span></a>
<a class="utility-card" href="firstaid/index.html"><span class="utility-card-icon">&#129657;</span><span class="utility-card-title">First Aid</span></a>
<a class="utility-card" href="maps/index.html"><span class="utility-card-icon">&#128506;</span><span class="utility-card-title">Maps</span></a>
<a class="utility-card" href="local/index.html"><span class="utility-card-icon">&#128205;</span><span class="utility-card-title">Local Info</span></a>
<a class="utility-card" href="library/index.html"><span class="utility-card-icon">&#128218;</span><span class="utility-card-title">Library</span></a>
<a class="utility-card" href="search/index.html"><span class="utility-card-icon">&#128269;</span><span class="utility-card-title">Search</span></a>
</div>
</div>'''
    return write_page("index.html", "PirateBox Offline Utility Library (Saved Copy)", body, depth=0)


def zip_dir(zip_path, base_dir, include_dirs):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for d in include_dirs:
            src = os.path.join(base_dir, d)
            if not os.path.isdir(src):
                continue
            for root, _, files in os.walk(src):
                for fn in files:
                    full = os.path.join(root, fn)
                    arc = os.path.relpath(full, base_dir)
                    zf.write(full, arc)
    return os.path.getsize(zip_path)


def main():
    if os.path.isdir(STATIC_DIR):
        shutil.rmtree(STATIC_DIR)
    os.makedirs(os.path.join(STATIC_DIR, "assets"), exist_ok=True)

    # Bundle shared assets verbatim - no modification, same files the live
    # site uses (progressive-enhancement JS filter works unchanged).
    shutil.copy(os.path.join(WEBROOT, "assets/styles.css"), os.path.join(STATIC_DIR, "assets/styles.css"))
    shutil.copy(os.path.join(WEBROOT, "assets/scripts.js"), os.path.join(STATIC_DIR, "assets/scripts.js"))

    build_index()
    _, services, modulation, guides = build_radio()
    _, emergency_topics = build_simple_section(
        "emergency", "topics.json",
        lambda t: t.get("category"),
        {"hazards": "Severe Weather & Hazards", "utilities": "Power, Utilities & Home Safety",
         "essentials": "Water, Food & Sanitation", "planning": "Planning & Communication", "pets": "Pets"},
        "Emergency / Outage Reference")
    _, firstaid_topics = build_simple_section(
        "firstaid", "topics.json",
        lambda t: t.get("category"),
        {"basics": "Basics: Get Help, CPR/AED, Kit", "breathing": "Choking", "trauma": "Bleeding, Burns & Injuries",
         "medical": "Medical Emergencies", "environmental": "Heat, Cold & Bites/Stings"},
        "First Aid Reference")
    _, maps_ref = build_maps()
    _, local_info = build_local()
    _, library_catalog = build_library()

    # Rebuild a fresh copy of the full search index (same source data) for
    # the static search page.
    search_index = json.load(open(os.path.join(DATA_DIR, "search-index.json"), encoding="utf-8")) if os.path.isfile(os.path.join(DATA_DIR, "search-index.json")) else []
    for item in search_index:
        item.setdefault("id", item.get("url", "").rsplit("#", 1)[-1] if "#" in item.get("url", "") else "")
    build_search_page(search_index)

    # Individual-section raw JSON exports (a distinct, lighter-weight tier
    # from the styled HTML bundles above - the same data every live page
    # already reads, just exposed as a direct download for anyone who wants
    # the raw data rather than a browsable page).
    json_out_dir = os.path.join(OUT_DIR, "data")
    if os.path.isdir(json_out_dir):
        shutil.rmtree(json_out_dir)
    json_sizes = {}
    for section in ["radio", "emergency", "firstaid", "maps", "local", "library"]:
        src_dir = os.path.join(DATA_DIR, section)
        if not os.path.isdir(src_dir):
            continue
        dst_dir = os.path.join(json_out_dir, section)
        os.makedirs(dst_dir, exist_ok=True)
        total = 0
        for fn in os.listdir(src_dir):
            if fn.endswith(".json"):
                shutil.copy(os.path.join(src_dir, fn), os.path.join(dst_dir, fn))
                total += os.path.getsize(os.path.join(dst_dir, fn))
        json_sizes[section] = total

    # CSV export - Radio services (genuinely tabular data)
    csv_path = os.path.join(OUT_DIR, "radio-services.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "category", "name", "freq_range", "typical_receiver_mode", "license_required_to_transmit", "confidence"])
        for svc in services:
            w.writerow([svc.get("id"), svc.get("category"), svc.get("name"), svc.get("freq_range"),
                        svc.get("typical_receiver_mode"), svc.get("license_required_to_transmit"), svc.get("confidence")])

    # ZIP bundles
    sizes = {}
    sizes["radio"] = zip_dir(os.path.join(OUT_DIR, "radio-bundle.zip"), STATIC_DIR, ["radio", "assets"])
    sizes["emergency_firstaid"] = zip_dir(os.path.join(OUT_DIR, "emergency-reference-bundle.zip"), STATIC_DIR, ["emergency", "firstaid", "assets"])
    sizes["maps_local"] = zip_dir(os.path.join(OUT_DIR, "maps-local-bundle.zip"), STATIC_DIR, ["maps", "local", "assets"])
    sizes["library"] = zip_dir(os.path.join(OUT_DIR, "manuals-documents-bundle.zip"), STATIC_DIR, ["library", "assets"])
    sizes["complete"] = zip_dir(os.path.join(OUT_DIR, "complete-utility-library.zip"), STATIC_DIR,
                                 ["radio", "emergency", "firstaid", "maps", "local", "library", "search", "assets"])
    # index.html lives at STATIC_DIR root, not in a subdir - add explicitly
    with zipfile.ZipFile(os.path.join(OUT_DIR, "complete-utility-library.zip"), "a", zipfile.ZIP_DEFLATED) as zf:
        zf.write(os.path.join(STATIC_DIR, "index.html"), "index.html")
    sizes["complete"] = os.path.getsize(os.path.join(OUT_DIR, "complete-utility-library.zip"))
    sizes["radio_csv"] = os.path.getsize(csv_path)

    manifest = {
        "generated_at": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
        "bundles": {
            "radio-bundle.zip": {"label": "Radio Reference Bundle", "bytes": sizes["radio"]},
            "emergency-reference-bundle.zip": {"label": "Emergency Reference Bundle (Emergency + First Aid)", "bytes": sizes["emergency_firstaid"]},
            "maps-local-bundle.zip": {"label": "Maps / Local Reference Bundle", "bytes": sizes["maps_local"]},
            "manuals-documents-bundle.zip": {"label": "Manuals / Documents Bundle", "bytes": sizes["library"]},
            "complete-utility-library.zip": {"label": "Complete Offline Utility Library", "bytes": sizes["complete"]},
            "radio-services.csv": {"label": "Radio Services (CSV)", "bytes": sizes["radio_csv"]},
        },
        "individual_sections_json_bytes": json_sizes,
        "counts": {
            "radio_services": len(services), "radio_modulation": len(modulation), "radio_guides": len(guides),
            "emergency_topics": len(emergency_topics), "firstaid_topics": len(firstaid_topics),
            "maps_reference": len(maps_ref), "library_documents": len(library_catalog),
            "search_index_items": len(search_index),
        },
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("Export bundles built:")
    for name, info in manifest["bundles"].items():
        kb = info["bytes"] / 1024
        print(f"  {name:34s} {kb:8.1f} KB  {info['label']}")


if __name__ == "__main__":
    main()
