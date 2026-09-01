<?php
declare(strict_types=1);
session_start();

// Emergency / Outage Reference (Stage 3). Deliberately does NOT read
// piratebox_get_mode() - this page's content is identical in Normal and
// Emergency Mode by design (see docs/OPERATIONAL-DECISIONS.md).
//
// Reuses the exact same CSS classes and JS filter element IDs (#radioSearch,
// #radioChips, .radio-entry, .radio-chip, etc.) that Stage 2's Radio
// Reference introduced. This is a deliberate reuse of one shared
// "searchable reference list" UI component across every Utility Library
// section, not a copy/paste mistake - see OPERATIONAL-DECISIONS.md for the
// naming rationale. Because each page is loaded independently, reusing the
// same element IDs across different pages is safe and requires zero changes
// to the already-tested scripts.js filter logic.

$DATA_DIR = __DIR__ . '/../../../data/utility/emergency';

function ref_load_json(string $path): array
{
    $raw = @file_get_contents($path);
    if ($raw === false) return [];
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

$topics = ref_load_json($DATA_DIR . '/topics.json');
$sources = ref_load_json($DATA_DIR . '/sources.json');

$groupLabels = [
    'hazards'   => 'Severe Weather & Hazards',
    'utilities' => 'Power, Utilities & Home Safety',
    'essentials'=> 'Water, Food & Sanitation',
    'planning'  => 'Planning & Communication',
    'pets'      => 'Pets',
];

$groups = [];
foreach ($groupLabels as $key => $label) $groups[$key] = [];
foreach ($topics as $t) {
    if (isset($groups[$t['category']])) $groups[$t['category']][] = $t;
}

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
    <title>PirateBox - Emergency Reference</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Emergency / Outage Reference</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>Practical, skimmable guidance for power outages, severe weather, and other emergencies - works with no Internet connection. This is general preparedness information, not a substitute for official local alerts or instructions from emergency responders. <strong>Always follow official evacuation orders and instructions from local authorities</strong> - this reference is meant to help you act quickly, not override them.</p>

        <div class="radio-search-bar">
            <input type="text" id="radioSearch" placeholder="Search: flood, generator, water, hypothermia, evacuation..." aria-label="Search emergency reference">
            <div class="radio-chip-row" id="radioChips" role="group" aria-label="Filter by category">
                <button type="button" class="radio-chip active" data-group="all">All</button>
                <?php foreach ($groupLabels as $key => $label): ?>
                    <button type="button" class="radio-chip" data-group="<?= htmlspecialchars($key) ?>"><?= htmlspecialchars($label) ?></button>
                <?php endforeach; ?>
            </div>
        </div>

        <p class="radio-no-results" id="radioNoResults" hidden>No matches. Try a different search term or choose "All".</p>

        <div id="radioResults">
            <?php foreach ($groupLabels as $groupKey => $groupLabel): ?>
                <?php if (empty($groups[$groupKey])) continue; ?>
                <section class="radio-group" data-group-section="<?= htmlspecialchars($groupKey) ?>">
                    <h2 class="radio-group-heading"><?= htmlspecialchars($groupLabel) ?></h2>
                    <?php foreach ($groups[$groupKey] as $t): ?>
                        <?php $search = ref_search_blob([$t['title'], $t['summary'], $t['keywords'] ?? [], $t['category']]); ?>
                        <details class="radio-entry" id="<?= htmlspecialchars($t['id']) ?>" data-group="<?= htmlspecialchars($groupKey) ?>" data-search="<?= $search ?>">
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
                                <p class="radio-entry-source"><?= ref_source_line($sources, $t['source_id'] ?? null, $t['secondary_source_id'] ?? null, $t['confidence'] ?? null, $t['source_note'] ?? null) ?></p>
                            </div>
                        </details>
                    <?php endforeach; ?>
                </section>
            <?php endforeach; ?>
        </div>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
            <a href="/utility/firstaid/">First Aid</a>
            <a href="/utility/local/">Local Information</a>
            <a href="/utility/search/">Search</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
