#!/usr/bin/env python3
"""
Generate a static, offline, public-domain US national reference map as
SVG - the "Country/National" layer of the Maps hierarchy, one level
below the World Reference Map.

Source: same Natural Earth 1:110m dataset family as the World Map
(public domain, naturalearthdata.com), this time the Admin 1 States/
Provinces layer, filtered to iso_a2=="US" (51 features: 50 states +
DC). Fetched from the same community mirror,
github.com/nvkelso/natural-earth-vector, geojson/
ne_110m_admin_1_states_provinces.geojson.

Three-panel layout (the standard convention for US reference maps,
since Alaska and Hawaii are far outside the continental bounding box
and would otherwise force the whole map absurdly wide/mostly-empty):
CONUS (48 states + DC) as the main panel, Alaska and Hawaii as smaller
insets - each panel is its own independent equirectangular projection
(x=lon, y=-lat) over its own real bounding box, same simple, no-new-
dependency technique as the World Map.

To regenerate: fetch
  https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_1_states_provinces.geojson
to a local file, then:
  python3 tools/build_us_reference_map.py <geojson-path> \\
      var/www/html/public/utility/maps/files/us-reference-map.svg
Verified after generation, not assumed correct: parsed back as
well-formed XML; Texas/California/Florida/Maine's rendered bounding
boxes were checked against their real lon/lat ranges within the CONUS
panel's own coordinate math and matched exactly; all 51 features
(50 states + DC) present, correctly split 49/1/1 across CONUS/Alaska/
Hawaii panels.
"""
import json
import sys

SRC = sys.argv[1]
OUT = sys.argv[2]

W, H = 2000, 1300
CAPTION_H = 90
MAP_H = H - CAPTION_H

PANELS = {
    "conus": {"lon": (-125.5, -66.5), "lat": (24.0, 49.8), "rect": (40, 30, 1960, 900)},
    "alaska": {"lon": (-172.0, -129.5), "lat": (54.0, 71.6), "rect": (40, 940, 620, 1190)},
    "hawaii": {"lon": (-160.5, -154.5), "lat": (18.5, 22.5), "rect": (680, 1000, 1000, 1190)},
}

def project(panel, lon, lat):
    lon0, lon1 = panel["lon"]
    lat0, lat1 = panel["lat"]
    x0, y0, x1, y1 = panel["rect"]
    x = x0 + (lon - lon0) / (lon1 - lon0) * (x1 - x0)
    y = y0 + (lat1 - lat) / (lat1 - lat0) * (y1 - y0)
    return x, y

def ring_to_path(panel, ring):
    pts = [project(panel, lon, lat) for lon, lat in ring]
    return "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + " Z"

def geom_to_path(panel, geom):
    t = geom["type"]
    parts = []
    if t == "Polygon":
        for ring in geom["coordinates"]:
            parts.append(ring_to_path(panel, ring))
    elif t == "MultiPolygon":
        for poly in geom["coordinates"]:
            for ring in poly:
                parts.append(ring_to_path(panel, ring))
    return " ".join(parts)

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

def panel_of(name, lon0, lon1, lat0, lat1):
    """Which named panel a feature's centroid-ish bbox belongs in."""
    if name == "Alaska":
        return "alaska"
    if name == "Hawaii":
        return "hawaii"
    return "conus"

with open(SRC) as f:
    data = json.load(f)

features = [f for f in data["features"] if f["properties"].get("iso_a2") == "US"]

paths_by_panel = {k: [] for k in PANELS}
for feat in features:
    name = feat["properties"].get("name") or "Unknown"
    geom = feat.get("geometry")
    if not geom:
        continue
    panel_name = "alaska" if name == "Alaska" else ("hawaii" if name == "Hawaii" else "conus")
    d = geom_to_path(PANELS[panel_name], geom)
    if d:
        paths_by_panel[panel_name].append((name, d))

svg = []
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" height="auto" role="img" aria-labelledby="usm-title usm-desc">')
svg.append(
    '<title id="usm-title">United States Reference Map</title>'
    '<desc id="usm-desc">A static map showing US state borders - continental US, '
    'plus Alaska and Hawaii insets - generated from Natural Earth public-domain data.</desc>'
)
style = """<style>
  .usm-ocean { fill: #dbe9f4; }
  .usm-states path { fill: #f2ecd8; stroke: #8a8266; stroke-width: 0.8; }
  .usm-states path:hover { fill: #e4dcc0; }
  .usm-panel-border { fill: none; stroke: #6b7c8c; stroke-width: 1.5; }
  .usm-panel-label { font-family: sans-serif; font-size: 20px; font-weight: bold; fill: #445; }
  .usm-caption-bg { fill: #ffffff; }
  .usm-caption text { font-family: sans-serif; fill: #333333; }
  .usm-caption text:first-child { font-size: 22px; font-weight: bold; }
  .usm-caption text:last-child { font-size: 14px; }
</style>"""

panel_labels = {"conus": "Continental United States", "alaska": "Alaska (inset, not to same scale)", "hawaii": "Hawaii (inset, not to same scale)"}

for pname, panel in PANELS.items():
    x0, y0, x1, y1 = panel["rect"]
    svg.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" class="usm-ocean"/>')
    svg.append(f'<g class="usm-states" fill-rule="evenodd">')
    for name, d in paths_by_panel[pname]:
        svg.append(f'<path d="{d}"><title>{esc(name)}</title></path>')
    svg.append('</g>')
    svg.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" class="usm-panel-border"/>')
    svg.append(f'<text x="{x0+8}" y="{y0+26}" class="usm-panel-label">{esc(panel_labels[pname])}</text>')

cap_y = MAP_H + 34
svg.append(
    f'<g class="usm-caption">'
    f'<rect x="0" y="{MAP_H}" width="{W}" height="{CAPTION_H}" class="usm-caption-bg"/>'
    f'<text x="20" y="{cap_y}">United States Reference Map - state borders, three independently-scaled panels</text>'
    f'<text x="20" y="{cap_y + 26}">Data: Natural Earth 1:110m Admin 1 States/Provinces (public domain, naturalearthdata.com), filtered to US. Alaska/Hawaii insets are NOT to the same scale as the continental panel.</text>'
    f'</g>'
)
svg.append('</svg>')

full = svg[0] + style + "".join(svg[1:])
with open(OUT, "w") as f:
    f.write(full)

print("panels:", {k: len(v) for k, v in paths_by_panel.items()})
print("output:", OUT)
