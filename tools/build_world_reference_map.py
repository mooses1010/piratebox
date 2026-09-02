#!/usr/bin/env python3
"""
Generate var/www/html/public/utility/maps/files/world-reference-map.svg -
the static, offline, public-domain world map for the Maps & Location
Reference page's always-available "World Reference Map" section
(docs/REFERENCE-CONTENT-DESIGN.md).

Source data: Natural Earth 1:110m Admin 0 Countries (public domain,
naturalearthdata.com - "No permission is needed to use Natural Earth.
Crediting the authors is unnecessary." - fetched 2026-09-02 via the
well-known community GitHub mirror
github.com/nvkelso/natural-earth-vector (a Natural Earth core
contributor's repo), specifically:
  https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson
This PirateBox device has no general WAN path (offline by design); the
source GeoJSON was fetched once from Claude Code's own development
environment (which does have outbound network access, confirmed
separately from the Pi's isolated visitor AP) and is not itself bundled
here - only the derived static SVG is. The raw GeoJSON is not needed
again unless regenerating this file (see below).

To regenerate: fetch the URL above to a local file, then run
  python3 tools/build_world_reference_map.py <geojson-path> \\
      var/www/html/public/utility/maps/files/world-reference-map.svg
Only needed if a newer Natural Earth release should replace this one -
the existing file does not go stale (borders are drawn as of the 2026
fetch date, recorded in data/utility/maps/sources.json).

Projection: plain equirectangular (x = lon, y = -lat) - no external
geo/plotting library needed (matplotlib/cartopy/geopandas are not
installed and this project does not install new packages without
explicit operator approval), just stdlib json + basic arithmetic. This
is the same projection used for countless simple reference world maps
and is entirely adequate for "which country is roughly where" context -
it is not a navigation-grade projection and is not presented as one.

Output: a single self-contained SVG (no external references, no
network calls at render time) with one <path> per country ring,
even-odd fill rule (handles holes/enclaves correctly), a light
graticule (lat/lon grid) for geographic context, and an embedded
attribution/caption so the source and license travel with the file.
Verified after generation (not just assumed correct): parsed back as
well-formed XML, and five widely-spread countries' rendered bounding
boxes (Australia/USA/Brazil/Russia/Japan) were checked against their
real-world lon/lat ranges and matched.
"""
import json
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "ne_110m_countries.geojson"
OUT = sys.argv[2] if len(sys.argv) > 2 else "world-reference-map.svg"

W, H = 2000, 1050  # slightly taller than 2:1 to leave room for the caption strip
MAP_H = 1000        # the actual -90..90 latitude band maps into this height
CAPTION_H = H - MAP_H

def project(lon, lat):
    x = (lon + 180.0) / 360.0 * W
    y = (90.0 - lat) / 180.0 * MAP_H
    return x, y

def ring_to_path(ring):
    pts = [project(lon, lat) for lon, lat in ring]
    d = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + " Z"
    return d

def geom_to_path(geom):
    t = geom["type"]
    parts = []
    if t == "Polygon":
        for ring in geom["coordinates"]:
            parts.append(ring_to_path(ring))
    elif t == "MultiPolygon":
        for poly in geom["coordinates"]:
            for ring in poly:
                parts.append(ring_to_path(ring))
    return " ".join(parts)

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))

with open(SRC) as f:
    data = json.load(f)

country_paths = []
for feat in data["features"]:
    props = feat.get("properties", {})
    name = props.get("ADMIN") or props.get("NAME") or props.get("SOVEREIGNT") or "Unknown"
    geom = feat.get("geometry")
    if not geom:
        continue
    d = geom_to_path(geom)
    if not d:
        continue
    country_paths.append((name, d))

svg_parts = []
svg_parts.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
    f'width="100%" height="auto" role="img" '
    f'aria-labelledby="wm-title wm-desc">'
)
svg_parts.append(
    '<title id="wm-title">World Reference Map</title>'
    '<desc id="wm-desc">A static equirectangular world map showing country '
    'borders, generated from Natural Earth 1:110m public-domain data for '
    'offline reference use on PirateBox.</desc>'
)

# Background (ocean)
svg_parts.append(f'<rect x="0" y="0" width="{W}" height="{MAP_H}" class="wm-ocean"/>')

# Graticule (every 30 degrees) for geographic context - drawn before
# countries so country fills sit on top of it.
grat = []
for lon in range(-180, 181, 30):
    x, _ = project(lon, 0)
    grat.append(f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{MAP_H}" class="wm-grat"/>')
for lat in range(-60, 61, 30):
    _, y = project(0, lat)
    grat.append(f'<line x1="0" y1="{y:.1f}" x2="{W}" y2="{y:.1f}" class="wm-grat"/>')
# Equator and prime meridian slightly heavier
_, y0 = project(0, 0)
grat.append(f'<line x1="0" y1="{y0:.1f}" x2="{W}" y2="{y0:.1f}" class="wm-grat-major"/>')
x0, _ = project(0, 0)
grat.append(f'<line x1="{x0:.1f}" y1="0" x2="{x0:.1f}" y2="{MAP_H}" class="wm-grat-major"/>')
svg_parts.append('<g>' + "".join(grat) + '</g>')

# Countries
svg_parts.append('<g class="wm-countries" fill-rule="evenodd">')
for name, d in country_paths:
    svg_parts.append(f'<path d="{d}"><title>{esc(name)}</title></path>')
svg_parts.append('</g>')

# Map border
svg_parts.append(f'<rect x="0" y="0" width="{W}" height="{MAP_H}" class="wm-border"/>')

# Caption strip
cap_y = MAP_H + 34
svg_parts.append(
    f'<g class="wm-caption">'
    f'<rect x="0" y="{MAP_H}" width="{W}" height="{CAPTION_H}" class="wm-caption-bg"/>'
    f'<text x="20" y="{cap_y}">World Reference Map - equirectangular projection, country borders only</text>'
    f'<text x="20" y="{cap_y + 26}">Data: Natural Earth 1:110m Admin 0 Countries (public domain, naturalearthdata.com). No attribution legally required; credited here as project practice.</text>'
    f'</g>'
)

svg_parts.append('</svg>')

style = """<style>
  .wm-ocean { fill: #dbe9f4; }
  .wm-grat { stroke: #b9c9d6; stroke-width: 1; }
  .wm-grat-major { stroke: #9fb3c4; stroke-width: 1.5; }
  .wm-countries path { fill: #f2ecd8; stroke: #8a8266; stroke-width: 0.6; }
  .wm-countries path:hover { fill: #e4dcc0; }
  .wm-border { fill: none; stroke: #6b7c8c; stroke-width: 2; }
  .wm-caption-bg { fill: #ffffff; }
  .wm-caption text { font-family: sans-serif; fill: #333333; }
  .wm-caption text:first-child { font-size: 22px; font-weight: bold; }
  .wm-caption text:last-child { font-size: 14px; }
</style>"""

svg = svg_parts[0] + style + "".join(svg_parts[1:])

with open(OUT, "w") as f:
    f.write(svg)

print(f"countries rendered: {len(country_paths)}")
print(f"output: {OUT}")
