<?php
declare(strict_types=1);
session_start();

// Electronics Reference (Deep bookshelf pass, round 7, 2026-09-03).
// Built for the same reason as the new Mechanical & Repair page: the
// library held six retained "electronics" documents (NEETS Modules 1/
// 3/7/13/16, OSHA electrical safety) with no dedicated web reference
// page - only Field Tools Units' narrower Ohm's Law/multimeter
// sections touched on this material. See docs/IMPLEMENTATION-
// ROADMAP.md round 7 for the audit. Every entry below is written
// originally for this page (Tier 2 PirateBox Reference Material, see
// docs/REFERENCE-CONTENT-DESIGN.md §7), cross-checked against the
// retained sources rather than transcribed from them.
//
// Deliberately does NOT read piratebox_get_mode() - identical in
// Normal and Emergency Mode, same reasoning as every other universal
// reference section.

require_once __DIR__ . '/../../../includes/library_links.php';

$DATA_DIR = __DIR__ . '/../../../data/utility/electronics';

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
    'fundamentals' => 'Fundamentals',
    'components'   => 'Components',
    'protection'   => 'Protection &amp; Control',
];

$libraryLinksHtml = piratebox_render_library_links_html(piratebox_get_library_entries_for_page('/utility/electronics/'));

function ref_search_blob(array $fields): string
{
    $parts = [];
    foreach ($fields as $f) {
        if (is_array($f)) $parts[] = implode(' ', $f);
        elseif ($f !== null) $parts[] = (string) $f;
    }
    return htmlspecialchars(strtolower(implode(' ', $parts)));
}

function ref_source_line(array $sources, ?string $sourceId, ?string $confidence): string
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
    <title>PirateBox - Electronics Reference</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Electronics Reference</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>Core electrical and electronics concepts - voltage/current/power, AC vs. DC, semiconductors, and circuit protection - with the full authoritative source manuals one click away below when you need real depth. For the Ohm's Law calculator and a wire-gauge/multimeter quick reference, see <a href="/utility/fieldtools/units/">Field Tools Units</a> and the <a href="/utility/fieldtools/ohmslaw/">Ohm's Law Solver</a>.</p>

        <div class="help-note">
            <p><strong>This is a conceptual reference, not a substitute for an electrician or a specific device's own service documentation.</strong> Nothing here covers live-mains work, high-voltage systems, or any procedure requiring certification - see the Electrical Safety documents in the Document Library below for hazard-recognition guidance, and a qualified electrician for anything beyond low-voltage DC/battery work.</p>
        </div>

        <?= $libraryLinksHtml ?>

        <div class="radio-search-bar">
            <input type="text" id="radioSearch" placeholder="Search: voltage, current, ac, dc, diode, transistor, fuse, relay, digital..." aria-label="Search electronics reference">
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
                                        <figure class="doc-figure" style="max-width:420px;">
                                            <img src="/utility/electronics/images/<?= rawurlencode($t['diagram']['image']) ?>" alt="<?= htmlspecialchars($t['diagram']['alt']) ?>" loading="lazy">
                                            <figcaption><?= htmlspecialchars($t['diagram']['caption']) ?><span class="doc-figure-source"><?= $t['diagram']['source_line'] ?></span></figcaption>
                                        </figure>
                                    </div>
                                <?php endif; ?>
                                <?php if (!empty($t['more_info'])): ?>
                                    <p><?= htmlspecialchars($t['more_info']) ?></p>
                                <?php endif; ?>
                                <p class="radio-entry-source"><?= ref_source_line($sources, $t['source_id'] ?? null, $t['confidence'] ?? null) ?></p>
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
