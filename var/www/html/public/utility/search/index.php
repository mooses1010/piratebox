<?php
declare(strict_types=1);
session_start();

// Global Offline Search (Stage 8). Searches a flat, pre-built index
// (data/utility/search-index.json, built by tools/build_search_index.py)
// covering Radio, Emergency, First Aid, Maps, Local Information, and the
// Document Library. Entirely client-side after this page loads - no
// server-side search process, no database.
//
// Progressive enhancement: every result is rendered server-side as a plain
// link with its section/snippet, so the page is fully browsable/useful
// with JS off - the search box and section chips only narrow what's
// already there, using the exact same shared filter component every other
// Utility section page uses (reuses #radioSearch/#radioChips/.radio-entry/
// data-group/data-search - see OPERATIONAL-DECISIONS.md).
//
// Deliberately does NOT read piratebox_get_mode() - identical in Normal
// and Emergency Mode by design.
//
// Post-Stage-32 (Travel Mode): when active, results from the 'local'
// section are filtered out here at render time - the persisted index
// file itself is never touched, so this is a cheap, reversible view,
// not a rebuild. See includes/travel_mode.php.

require_once __DIR__ . '/../../../includes/travel_mode.php';
$travelMode = piratebox_get_travel_mode();

$DATA_DIR = __DIR__ . '/../../../data/utility';

function ref_load_json(string $path): array
{
    $raw = @file_get_contents($path);
    if ($raw === false) return [];
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

$index = ref_load_json($DATA_DIR . '/search-index.json');
if ($travelMode) {
    // Exclude the whole 'local' section, plus any entry elsewhere
    // explicitly flagged 'regional' (e.g. the maps catalog, which
    // shares section="maps" with the generic, universal coordinate/GPS
    // reference entries and can't be told apart by section alone - see
    // tools/build_search_index.py).
    $index = array_values(array_filter(
        $index,
        fn($item) => ($item['section'] ?? null) !== 'local' && empty($item['regional'])
    ));
}

$sectionLabels = [
    'radio'     => 'Radio Reference',
    'emergency' => 'Emergency / Outage Reference',
    'firstaid'  => 'First Aid Reference',
    'maps'      => 'Maps & Location Reference',
    'computing' => 'Computing & Networking Reference',
    'glossary'  => 'Glossary',
    'local'     => 'Local Information',
    'library'   => 'Document Library',
    'fieldtools' => 'Field Tools',
    'about'     => 'About This PirateBox',
];

function ref_search_blob(array $fields): string
{
    $parts = [];
    foreach ($fields as $f) {
        if (is_array($f)) $parts[] = implode(' ', $f);
        elseif ($f !== null) $parts[] = (string) $f;
    }
    return htmlspecialchars(strtolower(implode(' ', $parts)));
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Search</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Search</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>One search box across Radio, Emergency, First Aid, Maps, Local Information, and the Document Library - <?= count($index) ?> indexed items, entirely offline. Results link straight to the answer.</p>

        <div class="radio-search-bar">
            <input type="text" id="radioSearch" placeholder="Search: NOAA, 40 meter, generator, bleeding, hypothermia, GPS, manual..." aria-label="Search everything">
            <div class="radio-chip-row" id="radioChips" role="group" aria-label="Filter by section">
                <button type="button" class="radio-chip active" data-group="all">All</button>
                <?php foreach ($sectionLabels as $key => $label): ?>
                    <button type="button" class="radio-chip" data-group="<?= htmlspecialchars($key) ?>"><?= htmlspecialchars($label) ?></button>
                <?php endforeach; ?>
            </div>
        </div>

        <p class="radio-no-results" id="radioNoResults" hidden>No matches. Try a different search term or choose "All".</p>

        <div id="radioResults">
            <?php if (empty($index)): ?>
                <p class="empty-state">Search index not built yet - run tools/build_search_index.py.</p>
            <?php else: ?>
                <?php foreach ($index as $r): ?>
                    <?php $search = ref_search_blob([$r['title'] ?? '', $r['snippet'] ?? '', $r['keywords'] ?? [], $r['section'] ?? '']); ?>
                    <div class="radio-entry search-result-entry" data-group="<?= htmlspecialchars($r['section'] ?? '') ?>" data-search="<?= $search ?>">
                        <a class="search-result-link" href="<?= htmlspecialchars($r['url'] ?? '/utility/') ?>">
                            <span class="radio-entry-name"><?= htmlspecialchars($r['title'] ?? 'Untitled') ?></span>
                            <?php if (!empty($r['freq'])): ?><span class="radio-entry-freq"><?= htmlspecialchars($r['freq']) ?></span><?php endif; ?>
                            <span class="radio-entry-mode-badge"><?= htmlspecialchars($sectionLabels[$r['section'] ?? ''] ?? ($r['section'] ?? '')) ?></span>
                        </a>
                        <?php if (!empty($r['snippet'])): ?><p class="search-result-snippet"><?= htmlspecialchars($r['snippet']) ?></p><?php endif; ?>
                    </div>
                <?php endforeach; ?>
            <?php endif; ?>
        </div>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
            <a href="/utility/download/">Take This With You</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
