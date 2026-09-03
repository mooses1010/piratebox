<?php
declare(strict_types=1);
session_start();

// Maps / Location Reference (Stage 5). Two independent parts on one page:
// (1) a small reference section (coordinates/GPS/navigation basics - real
//     content, works today), and
// (2) a data-driven map catalog framework - currently EMPTY (no map files
//     shipped this stage, per instruction not to download large datasets
//     or invent placeholder local content). Adding a real map later is:
//     drop the file in public/utility/maps/files/, add one entry to
//     data/utility/maps/catalog.json - no PHP edit needed.
//
// Deliberately does NOT read piratebox_get_mode() - identical in Normal and
// Emergency Mode by design. Reuses the Stage 2/3/4 shared reference-list UI
// component (see OPERATIONAL-DECISIONS.md).
//
// Post-Stage-32 (Travel Mode): the Map Catalog (part 2 above) is
// region-specific by its own design ("for this box's area") - when
// Travel Mode is active it's treated as empty here, same as a box that
// never had any maps added, without touching catalog.json itself. The
// coordinate/GPS reference section (part 1) is universal and always
// shows regardless. See includes/travel_mode.php.

require_once __DIR__ . '/../../../includes/travel_mode.php';
require_once __DIR__ . '/../../../includes/library_links.php';
$travelMode = piratebox_get_travel_mode();

$DATA_DIR = __DIR__ . '/../../../data/utility/maps';

function ref_load_json(string $path): array
{
    $raw = @file_get_contents($path);
    if ($raw === false) return [];
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

$reference = ref_load_json($DATA_DIR . '/reference.json');
$catalog = $travelMode ? [] : ref_load_json($DATA_DIR . '/catalog.json');
$sources = ref_load_json($DATA_DIR . '/sources.json');
// World Reference Map (universal scope): unlike the operator map catalog
// above, this ships with PirateBox itself and is never region-specific,
// so it is NOT gated behind $travelMode - see docs/REFERENCE-CONTENT-
// DESIGN.md and docs/OPERATIONAL-DECISIONS.md for why this stays visible
// regardless of Travel Mode or whether Local Information is configured.
$worldMap = ref_load_json($DATA_DIR . '/world-reference-map.json')[0] ?? null;
$worldMapFileExists = $worldMap !== null
    && is_file(__DIR__ . '/files/' . basename($worldMap['file'] ?? ''));

// United States Reference Map (national scope): same reasoning as the
// World Reference Map above - ships with PirateBox, not region-
// specific to this box's own location, stays visible in Travel Mode
// (per the request's own instruction that universal/national public
// reference material remains available in Travel Mode - only truly
// local/operator-private information is suppressed).
$usMap = ref_load_json($DATA_DIR . '/us-reference-map.json')[0] ?? null;
$usMapFileExists = $usMap !== null
    && is_file(__DIR__ . '/files/' . basename($usMap['file'] ?? ''));

// Cross-link to the Document Library (see includes/library_links.php) -
// metadata-driven from catalog.json's own `related_pages` field, not a
// hardcoded link here.
$libraryLinksHtml = piratebox_render_library_links_html(piratebox_get_library_entries_for_page('/utility/maps/'));

function ref_search_blob(array $fields): string
{
    $parts = [];
    foreach ($fields as $f) {
        if (is_array($f)) $parts[] = implode(' ', $f);
        elseif ($f !== null) $parts[] = (string) $f;
    }
    return htmlspecialchars(strtolower(implode(' ', $parts)));
}

function ref_source_line(array $sources, ?string $sourceId, ?string $secondaryId, ?string $confidence, ?string $note): string
{
    $bits = [];
    if ($sourceId !== null && isset($sources[$sourceId])) {
        $s = $sources[$sourceId];
        $name = htmlspecialchars($s['name']);
        if (!empty($s['url'])) {
            $bits[] = '<a href="' . htmlspecialchars($s['url']) . '" target="_blank" rel="noopener">' . $name . '</a>';
        } else {
            $bits[] = $name;
        }
        if (!empty($s['retrieved'])) $bits[0] .= ' (retrieved ' . htmlspecialchars($s['retrieved']) . ')';
    }
    if ($secondaryId !== null && isset($sources[$secondaryId])) {
        $bits[] = 'plus ' . htmlspecialchars($sources[$secondaryId]['name']);
    }
    $out = 'Source: ' . implode('; ', $bits ?: ['unspecified']);
    if ($confidence !== null) {
        $out .= ' &mdash; confidence: <span class="radio-confidence confidence-' . htmlspecialchars($confidence) . '">' . htmlspecialchars($confidence) . '</span>';
    }
    if (!empty($note)) $out .= '<br>' . htmlspecialchars($note);
    return $out;
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Maps &amp; Location Reference</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Maps &amp; Location Reference</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>Coordinate/GPS/navigation basics, a world reference map, and a United States reference map below all work offline right now, everywhere. The map catalog is a ready-to-use framework for local/regional/evacuation/topographic maps - empty until real maps for this box's area are deliberately added.</p>
        <p class="muted">Unfamiliar term (declination, datum, UTM)? See the <a href="/utility/glossary/">Glossary</a>.</p>

        <?= $libraryLinksHtml ?>

        <div class="doc-figure-gallery">
            <figure class="doc-figure" style="max-width:340px;">
                <img src="/utility/maps/images/bowditch-fig1504-sextant.png" alt="Photograph of a clamp screw vernier marine sextant, labeled parts visible: telescope, index arm, horizon glass, micrometer drum, and handle" loading="lazy">
                <figcaption>Figure 1504. A clamp screw vernier sextant - the instrument at the center of celestial navigation.<span class="doc-figure-source">Source: <em>American Practical Navigator</em> (Bowditch), p. 402 (public domain)</span></figcaption>
            </figure>
            <figure class="doc-figure" style="max-width:420px;">
                <img src="/utility/maps/images/bowditch-fig1505-sextant-use.png" alt="Two diagrams: three telescope views showing the sun being brought down to the horizon during a sextant sighting, and a labeled diagram of sighting a star against the horizon" loading="lazy">
                <figcaption>Figure 1505a/b. What you actually see through a sextant while taking a sun or star sight.<span class="doc-figure-source">Source: <em>American Practical Navigator</em> (Bowditch), p. 403 (public domain)</span></figcaption>
            </figure>
        </div>
        <p class="muted">A glimpse of what's inside the full <em>American Practical Navigator</em> above - the authoritative reference on navigating without GPS or any other electronics, from basic piloting through full celestial navigation.</p>

        <div class="radio-search-bar">
            <input type="text" id="radioSearch" placeholder="Search: coordinates, gps, compass, utm, world map, us map, states..." aria-label="Search maps and location reference">
            <div class="radio-chip-row" id="radioChips" role="group" aria-label="Filter by category">
                <button type="button" class="radio-chip active" data-group="all">All</button>
                <button type="button" class="radio-chip" data-group="reference">Reference</button>
                <button type="button" class="radio-chip" data-group="worldmap">World Map</button>
                <button type="button" class="radio-chip" data-group="usmap">US Map</button>
                <button type="button" class="radio-chip" data-group="catalog">Map Catalog</button>
            </div>
        </div>

        <p class="radio-no-results" id="radioNoResults" hidden>No matches. Try a different search term or choose "All".</p>

        <div id="radioResults">
            <section class="radio-group" data-group-section="reference">
                <h2 class="radio-group-heading">Coordinates, GPS &amp; Navigation Basics</h2>
                <p class="muted">Need to actually convert a coordinate, not just read about the formats? See the <a href="/utility/fieldtools/coordinates/">Coordinate Converter</a> in Field Tools.</p>
                <?php foreach ($reference as $t): ?>
                    <?php $search = ref_search_blob([$t['title'], $t['summary'], $t['keywords'] ?? [], 'reference']); ?>
                    <details class="radio-entry" id="<?= htmlspecialchars($t['id']) ?>" data-group="reference" data-search="<?= $search ?>">
                        <summary>
                            <span class="radio-entry-name"><?= htmlspecialchars($t['title']) ?></span>
                            <span class="radio-entry-mode-badge"><?= htmlspecialchars($t['summary']) ?></span>
                        </summary>
                        <div class="radio-entry-detail">
                            <?php if (!empty($t['quick_actions'])): ?>
                                <ul class="ref-quick-actions">
                                    <?php foreach ($t['quick_actions'] as $qa): ?>
                                        <li><?= htmlspecialchars($qa) ?></li>
                                    <?php endforeach; ?>
                                </ul>
                            <?php endif; ?>
                            <?php if (!empty($t['table'])): ?>
                                <?php if (!empty($t['table_caption'])): ?><p><strong><?= htmlspecialchars($t['table_caption']) ?></strong></p><?php endif; ?>
                                <div class="table-wrapper">
                                    <table class="radio-channel-table">
                                        <?php
                                        // Same union-of-keys approach as Radio's guide tables - a
                                        // reference entry's table rows aren't required to share
                                        // identical columns.
                                        $tCols = [];
                                        foreach ($t['table'] as $row) {
                                            foreach (array_keys($row) as $k) {
                                                if (!in_array($k, $tCols, true)) $tCols[] = $k;
                                            }
                                        }
                                        ?>
                                        <thead>
                                            <tr><?php foreach ($tCols as $c): ?><th><?= htmlspecialchars(ucfirst(str_replace('_', ' ', $c))) ?></th><?php endforeach; ?></tr>
                                        </thead>
                                        <tbody>
                                            <?php foreach ($t['table'] as $row): ?>
                                                <tr>
                                                    <?php foreach ($tCols as $c): ?><td><?= htmlspecialchars((string) ($row[$c] ?? '')) ?></td><?php endforeach; ?>
                                                </tr>
                                            <?php endforeach; ?>
                                        </tbody>
                                    </table>
                                </div>
                            <?php endif; ?>
                            <?php if ($t['id'] === 'true-vs-magnetic-north'): ?>
                                <div class="radio-spectrum-wrap">
                                    <?php require __DIR__ . '/declination.svg.php'; ?>
                                </div>
                                <p class="radio-spectrum-caption">Schematic concept diagram - the declination angle shown is illustrative, not a live figure for any specific location. PirateBox-authored, not copied from any map margin or third-party image.</p>
                            <?php endif; ?>
                            <?php if ($t['id'] === 'reading-contour-lines'): ?>
                                <div class="doc-figure-gallery">
                                    <figure class="doc-figure" style="max-width:480px;">
                                        <img src="/utility/maps/images/fm3-25-26-fig10-26-terrain-features.png" alt="Topographic map excerpt with contour lines, numbered to identify a hill, valley, ridge, saddle, depression, draw, spur, cliff, cut, and fill" loading="lazy">
                                        <figcaption>Figure 10-26. Terrain features &mdash; the ten standard landforms a navigator learns to recognize from contour-line shape alone, on a real topographic map excerpt.<span class="doc-figure-source">Source: FM 3-25.26, <em>Map Reading and Land Navigation</em>, p. 120 (public domain)</span></figcaption>
                                    </figure>
                                </div>
                            <?php endif; ?>
                            <?php if ($t['id'] === 'coordinate-formats'): ?>
                                <div class="radio-spectrum-wrap">
                                    <?php require __DIR__ . '/utm-grid.svg.php'; ?>
                                </div>
                                <p class="radio-spectrum-caption">Simplified schematic of the UTM zone/grid concept - zone count, width, and square layout are illustrative, not a precise projection or a substitute for an actual UTM-gridded map. PirateBox-authored diagram.</p>
                            <?php endif; ?>
                            <?php if (!empty($t['more_info'])): ?>
                                <p><?= htmlspecialchars($t['more_info']) ?></p>
                            <?php endif; ?>
                            <p class="radio-entry-source"><?= ref_source_line($sources, $t['source_id'] ?? null, $t['secondary_source_id'] ?? null, $t['confidence'] ?? null, $t['source_note'] ?? null) ?></p>
                        </div>
                    </details>
                <?php endforeach; ?>
            </section>

            <section class="radio-group" data-group-section="worldmap">
                <h2 class="radio-group-heading">World Reference Map</h2>
                <?php if ($worldMap !== null && $worldMapFileExists): ?>
                    <?php $search = ref_search_blob([$worldMap['title'] ?? '', $worldMap['summary'] ?? '', $worldMap['keywords'] ?? [], 'worldmap']); ?>
                    <details class="radio-entry" id="<?= htmlspecialchars($worldMap['id']) ?>" data-group="worldmap" data-search="<?= $search ?>" open>
                        <summary>
                            <span class="radio-entry-name"><?= htmlspecialchars($worldMap['title']) ?></span>
                            <span class="radio-entry-mode-badge"><?= htmlspecialchars($worldMap['format'] ?? 'map') ?></span>
                        </summary>
                        <div class="radio-entry-detail">
                            <?php if (!empty($worldMap['description'])): ?><p><?= htmlspecialchars($worldMap['description']) ?></p><?php endif; ?>
                            <div class="world-map-frame">
                                <img src="/utility/maps/files/<?= rawurlencode($worldMap['file']) ?>" alt="World reference map - country borders, equirectangular projection" loading="lazy">
                            </div>
                            <p><a href="/utility/maps/files/<?= rawurlencode($worldMap['file']) ?>" target="_blank" rel="noopener">Open full-size in a new tab</a></p>
                            <p class="radio-entry-source"><?= ref_source_line($sources, $worldMap['source_id'] ?? null, null, null, null) ?></p>
                        </div>
                    </details>
                <?php else: ?>
                    <p class="empty-state">World map file not found on this install.</p>
                <?php endif; ?>
            </section>

            <section class="radio-group" data-group-section="usmap">
                <h2 class="radio-group-heading">United States Reference Map</h2>
                <?php if ($usMap !== null && $usMapFileExists): ?>
                    <?php $search = ref_search_blob([$usMap['title'] ?? '', $usMap['summary'] ?? '', $usMap['keywords'] ?? [], 'usmap']); ?>
                    <details class="radio-entry" id="<?= htmlspecialchars($usMap['id']) ?>" data-group="usmap" data-search="<?= $search ?>">
                        <summary>
                            <span class="radio-entry-name"><?= htmlspecialchars($usMap['title']) ?></span>
                            <span class="radio-entry-mode-badge"><?= htmlspecialchars($usMap['format'] ?? 'map') ?></span>
                        </summary>
                        <div class="radio-entry-detail">
                            <?php if (!empty($usMap['description'])): ?><p><?= htmlspecialchars($usMap['description']) ?></p><?php endif; ?>
                            <div class="world-map-frame">
                                <img src="/utility/maps/files/<?= rawurlencode($usMap['file']) ?>" alt="United States reference map - state borders, continental US plus Alaska/Hawaii insets" loading="lazy">
                            </div>
                            <p><a href="/utility/maps/files/<?= rawurlencode($usMap['file']) ?>" target="_blank" rel="noopener">Open full-size in a new tab</a></p>
                            <p class="radio-entry-source"><?= ref_source_line($sources, $usMap['source_id'] ?? null, null, null, null) ?></p>
                        </div>
                    </details>
                <?php else: ?>
                    <p class="empty-state">US map file not found on this install.</p>
                <?php endif; ?>
            </section>

            <section class="radio-group" data-group-section="catalog">
                <h2 class="radio-group-heading">Map Catalog</h2>
                <?php if ($travelMode): ?>
                    <p class="empty-state">Hidden while Travel Mode is active - this box's regional map catalog isn't shown while away from its usual area.</p>
                <?php elseif (empty($catalog)): ?>
                    <p class="empty-state">No maps have been added yet. See "Adding a Map" below to add one for this box's area.</p>
                <?php else: ?>
                    <?php foreach ($catalog as $mapIdx => $m): ?>
                        <?php $search = ref_search_blob([$m['title'] ?? '', $m['region'] ?? '', $m['category'] ?? '', $m['tags'] ?? [], 'catalog']); ?>
                        <details class="radio-entry" id="<?= htmlspecialchars($m['id'] ?? ('map-' . $mapIdx)) ?>" data-group="catalog" data-search="<?= $search ?>">
                            <summary>
                                <span class="radio-entry-name"><?= htmlspecialchars($m['title'] ?? 'Untitled map') ?></span>
                                <span class="radio-entry-mode-badge"><?= htmlspecialchars($m['category'] ?? '') ?></span>
                            </summary>
                            <div class="radio-entry-detail">
                                <?php if (!empty($m['description'])): ?><p><?= htmlspecialchars($m['description']) ?></p><?php endif; ?>
                                <?php if (!empty($m['region'])): ?><p><strong>Region:</strong> <?= htmlspecialchars($m['region']) ?></p><?php endif; ?>
                                <?php if (!empty($m['file'])): ?>
                                    <p><a href="/utility/maps/files/<?= rawurlencode($m['file']) ?>" target="_blank" rel="noopener">Open map file</a> (<?= htmlspecialchars($m['format'] ?? 'file') ?>)</p>
                                <?php endif; ?>
                                <?php if (!empty($m['source'])): ?><p class="radio-entry-source">Source: <?= htmlspecialchars($m['source']) ?><?= !empty($m['date']) ? ' (' . htmlspecialchars($m['date']) . ')' : '' ?></p><?php endif; ?>
                            </div>
                        </details>
                    <?php endforeach; ?>
                <?php endif; ?>

                <div class="help-note">
                    <p><strong>Adding a map:</strong> copy the image/PDF file into <code>/var/www/html/public/utility/maps/files/</code> on the box, then add one entry to <code>data/utility/maps/catalog.json</code> (title, category, region, description, file, format, source, date, tags). No PHP editing required - this page renders whatever the catalog contains.</p>
                </div>

                <div class="help-note utility-placeholder-note">
                    <p><strong>Future option, not implemented:</strong> a proper offline slippy/zoomable map viewer (pan/zoom like an online map) would need a JS mapping library (e.g. Leaflet, self-hosted - no CDN) plus locally-stored map tiles, which can range from tens of MB to several GB depending on area and zoom levels covered. That tradeoff should be a deliberate decision when real map data is chosen, not a default - static images/PDFs above work today with zero extra dependency or storage commitment.</p>
                </div>
            </section>
        </div>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
            <a href="/utility/local/">Local Information</a>
            <a href="/utility/search/">Search</a>
            <a href="/utility/download/">Take This With You</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
