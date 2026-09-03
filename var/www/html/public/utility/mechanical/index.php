<?php
declare(strict_types=1);
session_start();

// Mechanical & Repair Reference (Deep bookshelf pass, round 7, 2026-09-03).
// Built specifically to close a long-standing gap: the library held
// several strong retained sources (Basic Machines, Tools and Their
// Uses, NASA Fastener Design Manual, FM 5-125 Rigging) for months
// before any of them had a corresponding web reference page - see
// docs/IMPLEMENTATION-ROADMAP.md round 7 for the audit that flagged
// this specifically. Every entry below is written originally for this
// page (Tier 2 PirateBox Reference Material, see docs/REFERENCE-
// CONTENT-DESIGN.md §7), cross-checked against the retained sources
// rather than transcribed from them - the Document Library links let
// someone descend into the actual authoritative source for real depth.
//
// Deliberately does NOT read piratebox_get_mode() - identical in
// Normal and Emergency Mode, same reasoning as every other universal
// reference section.

require_once __DIR__ . '/../../../includes/library_links.php';

$DATA_DIR = __DIR__ . '/../../../data/utility/mechanical';

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
    'simple-machines'  => 'Simple Machines &amp; Mechanical Advantage',
    'fasteners'        => 'Fasteners, Threads &amp; Torque',
    'mechanisms'       => 'Bearings &amp; Mechanisms',
    'hand-tools'       => 'Hand Tools &amp; Measurement',
    'practical-repair' => 'Practical Repair Approach',
];

$libraryLinksHtml = piratebox_render_library_links_html(piratebox_get_library_entries_for_page('/utility/mechanical/'));

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
    <title>PirateBox - Mechanical &amp; Repair Reference</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Mechanical &amp; Repair Reference</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>The concepts behind simple machines, fasteners, and hand tools - a starting point for understanding how things actually work, with the full authoritative source manuals one click away below when you need real depth.</p>

        <div class="help-note">
            <p><strong>This is a conceptual and practical-approach reference, not a certified repair procedure or a substitute for a specific piece of equipment's own service manual.</strong> Nothing here covers specialized professional repair procedures (pressurized systems, structural/load-bearing work, anything requiring certification) - those genuinely need training and purpose-built equipment a web page can't provide.</p>
        </div>

        <?= $libraryLinksHtml ?>

        <div class="radio-search-bar">
            <input type="text" id="radioSearch" placeholder="Search: lever, pulley, fastener, torque, bearing, wrench, caliper..." aria-label="Search mechanical and repair reference">
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
                                <?php if (!empty($t['diagram'])): ?>
                                    <div class="doc-figure-gallery">
                                        <figure class="doc-figure" style="max-width:460px;">
                                            <img src="/utility/mechanical/images/<?= rawurlencode($t['diagram']['image']) ?>" alt="<?= htmlspecialchars($t['diagram']['alt']) ?>" loading="lazy">
                                            <figcaption><?= htmlspecialchars($t['diagram']['caption']) ?><span class="doc-figure-source"><?= $t['diagram']['source_line'] ?></span></figcaption>
                                        </figure>
                                    </div>
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
