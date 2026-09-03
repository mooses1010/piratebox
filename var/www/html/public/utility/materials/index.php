<?php
declare(strict_types=1);
session_start();

// Materials & Chemical Safety Reference (Deep bookshelf pass, round 7,
// 2026-09-03). Closes the audit's most explicitly named gap: before
// this page, the materials-chemistry catalog category held only the
// NIOSH Pocket Guide - a strong anchor but not, on its own, a web
// reference layer. Two short authoritative OSHA QuickCards were added
// alongside it (GHS pictograms, SDS structure) specifically to round
// this out. Every entry below is written originally for this page
// (Tier 2 PirateBox Reference Material, see docs/REFERENCE-CONTENT-
// DESIGN.md §7), grounded in the retained sources rather than
// transcribed from them, and deliberately stops at hazard recognition
// and safe-handling habits - this is NOT a hazardous-procedure library
// and does not walk through specific chemical procedures.
//
// Deliberately does NOT read piratebox_get_mode() - identical in
// Normal and Emergency Mode, same reasoning as every other universal
// reference section.

require_once __DIR__ . '/../../../includes/library_links.php';

$DATA_DIR = __DIR__ . '/../../../data/utility/materials';

function ref_load_json(string $path): array
{
    $raw = @file_get_contents($path);
    if ($raw === false) return [];
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

$reference = ref_load_json($DATA_DIR . '/reference.json');
$sources = ref_load_json($DATA_DIR . '/sources.json');

$categoryLabels = [
    'labels-hazcom'      => 'Labels &amp; Hazard Communication',
    'hazard-recognition' => 'Hazard Recognition',
    'material-properties' => 'Material Properties',
    'safe-handling'      => 'Safe Handling &amp; Storage',
];

$libraryLinksHtml = piratebox_render_library_links_html(piratebox_get_library_entries_for_page('/utility/materials/'));

function ref_search_blob(array $fields): string
{
    $parts = [];
    foreach ($fields as $f) {
        if (is_array($f)) $parts[] = implode(' ', $f);
        elseif ($f !== null) $parts[] = (string) $f;
    }
    return htmlspecialchars(strtolower(implode(' ', $parts)));
}

function ref_source_line(array $sources, ?string $sourceId, ?string $secondaryId, ?string $confidence): string
{
    $bits = [];
    if ($sourceId !== null && isset($sources[$sourceId])) {
        $s = $sources[$sourceId];
        $name = htmlspecialchars($s['name']);
        if (!empty($s['url'])) {
            $bits[] = '<a href="' . htmlspecialchars($s['url']) . '">' . $name . '</a>';
        } else {
            $bits[] = $name;
        }
    }
    if ($secondaryId !== null && isset($sources[$secondaryId])) {
        $bits[] = 'plus ' . htmlspecialchars($sources[$secondaryId]['name']);
    }
    $out = 'Source: ' . implode('; ', $bits ?: ['unspecified']);
    if ($confidence !== null) {
        $out .= ' &mdash; confidence: <span class="radio-confidence confidence-' . htmlspecialchars($confidence) . '">' . htmlspecialchars($confidence) . '</span>';
    }
    return $out;
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Materials &amp; Chemical Safety Reference</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Materials &amp; Chemical Safety Reference</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>How to read a chemical label and a Safety Data Sheet, recognize categories of hazard, and follow general safe-handling habits - plus a few everyday material-property basics useful for repair work. The full authoritative documents are one click away below when you need real depth on a specific chemical.</p>

        <div class="help-note">
            <p><strong>This is a hazard-recognition and safe-handling reference, not a set of chemical procedures.</strong> It will not walk through how to work with any specific hazardous substance - always follow that substance's own label, Safety Data Sheet, and any applicable local regulations. If you don't have those for something in hand, treat it as an unknown hazard until you do.</p>
        </div>

        <?= $libraryLinksHtml ?>

        <div class="radio-search-bar">
            <input type="text" id="radioSearch" placeholder="Search: pictogram, sds, exposure limit, ppe, corrosion, storage..." aria-label="Search materials and chemical safety reference">
            <div class="radio-chip-row" id="radioChips" role="group" aria-label="Filter by category">
                <button type="button" class="radio-chip active" data-group="all">All</button>
                <?php foreach ($categoryLabels as $key => $label): ?>
                    <button type="button" class="radio-chip" data-group="<?= htmlspecialchars($key) ?>"><?= $label ?></button>
                <?php endforeach; ?>
            </div>
        </div>

        <p class="radio-no-results" id="radioNoResults" hidden>No matches. Try a different search term or choose "All".</p>

        <div id="radioResults">
            <?php foreach ($categoryLabels as $catKey => $catLabel): ?>
                <?php $catTerms = array_values(array_filter($reference, fn($t) => ($t['category'] ?? '') === $catKey)); ?>
                <?php if (empty($catTerms)) continue; ?>
                <section class="radio-group" data-group-section="<?= htmlspecialchars($catKey) ?>">
                    <h2 class="radio-group-heading"><?= $catLabel ?></h2>
                    <?php foreach ($catTerms as $t): ?>
                        <?php $search = ref_search_blob([$t['title'], $t['summary'], $t['keywords'] ?? [], $catKey]); ?>
                        <details class="radio-entry" id="<?= htmlspecialchars($t['id']) ?>" data-group="<?= htmlspecialchars($catKey) ?>" data-search="<?= $search ?>">
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
                                <?php if (!empty($t['more_info'])): ?>
                                    <p><?= htmlspecialchars($t['more_info']) ?></p>
                                <?php endif; ?>
                                <p class="radio-entry-source"><?= ref_source_line($sources, $t['source_id'] ?? null, $t['secondary_source_id'] ?? null, $t['confidence'] ?? null) ?></p>
                            </div>
                        </details>
                    <?php endforeach; ?>
                </section>
            <?php endforeach; ?>
        </div>

        <p class="muted">Unfamiliar term? See the <a href="/utility/glossary/">Glossary</a>.</p>

        <div class="hero-actions">
            <a href="/utility/">&larr; Back to Utility Library</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
