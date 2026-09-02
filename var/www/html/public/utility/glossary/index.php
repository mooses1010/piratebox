<?php
declare(strict_types=1);
session_start();

// Glossary / Terminology (Deep field library increment, 2026-09-02).
// Reuses the exact same reference-list pattern as Radio/Maps/Emergency/
// First Aid/Computing (details accordion, radioSearch/radioChips,
// ref_search_blob/ref_source_line) - deliberately not a new UI pattern,
// no JavaScript beyond the same shared filter/search scripts.js already
// used everywhere else, works fully with JS off. See docs/REFERENCE-
// CONTENT-DESIGN.md §8 for the full design rationale: this exists so a
// beginner hitting an unfamiliar term (polarization, CIDR, declination)
// has one small place to look it up, instead of every subject page
// growing inline hyperlinks/tooltips to explain its own jargon.
//
// Each entry is AT A GLANCE (summary) -> UNDERSTAND (quick_actions) ->
// TECHNICAL/RELATED (related_pages, linking to the existing deeper
// reference rather than re-explaining it here).

$DATA_DIR = __DIR__ . '/../../../data/utility/glossary';

function ref_load_json(string $path): array
{
    $raw = @file_get_contents($path);
    if ($raw === false) return [];
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

$terms = ref_load_json($DATA_DIR . '/terms.json');
$sources = ref_load_json($DATA_DIR . '/sources.json');

$categoryLabels = [
    'computing'  => 'Computing & Networking',
    'radio'      => 'Radio',
    'maps'       => 'Maps & Navigation',
    'electrical' => 'Electrical & Measurement',
    'weather'    => 'Weather & Environment',
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

function ref_source_line(array $sources, ?string $sourceId, ?string $confidence): string
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
    <title>PirateBox - Glossary</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Glossary</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>Quick definitions for terms used across this Utility Library - what a word means, briefly why it matters, and a link to the fuller reference where one exists. Not a re-explanation of every subject page, just a fast lookup for when a term itself is the question.</p>

        <div class="radio-search-bar">
            <input type="text" id="radioSearch" placeholder="Search: cidr, dhcp, polarization, declination, voltage, checksum..." aria-label="Search glossary">
            <div class="radio-chip-row" id="radioChips" role="group" aria-label="Filter by category">
                <button type="button" class="radio-chip active" data-group="all">All</button>
                <?php foreach ($categoryLabels as $key => $label): ?>
                    <button type="button" class="radio-chip" data-group="<?= htmlspecialchars($key) ?>"><?= htmlspecialchars($label) ?></button>
                <?php endforeach; ?>
            </div>
        </div>

        <p class="radio-no-results" id="radioNoResults" hidden>No matches. Try a different search term or choose "All".</p>

        <div id="radioResults">
            <?php foreach ($categoryLabels as $catKey => $catLabel): ?>
                <?php $catTerms = array_values(array_filter($terms, fn($t) => ($t['category'] ?? '') === $catKey)); ?>
                <?php if (empty($catTerms)) continue; ?>
                <section class="radio-group" data-group-section="<?= htmlspecialchars($catKey) ?>">
                    <h2 class="radio-group-heading"><?= htmlspecialchars($catLabel) ?></h2>
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
                                <?php if (!empty($t['related_pages'])): ?>
                                    <p><strong>Fuller reference:</strong>
                                        <?php foreach ($t['related_pages'] as $i => $rp): ?><?= $i > 0 ? ', ' : '' ?><a href="<?= htmlspecialchars($rp['url']) ?>"><?= htmlspecialchars($rp['label']) ?></a><?php endforeach; ?>
                                    </p>
                                <?php endif; ?>
                                <p class="radio-entry-source"><?= ref_source_line($sources, $t['source_id'] ?? null, $t['confidence'] ?? null) ?></p>
                            </div>
                        </details>
                    <?php endforeach; ?>
                </section>
            <?php endforeach; ?>
        </div>

        <div class="hero-actions">
            <a href="/utility/">&larr; Back to Utility Library</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
