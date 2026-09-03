<?php
declare(strict_types=1);
session_start();

// First Aid Reference (Stage 4). HIGH-STAKES CONTENT - conservative,
// overview-level only, sourced from American Red Cross / CDC. Deliberately
// does NOT read piratebox_get_mode() - identical in Normal and Emergency
// Mode by design. Reuses the Stage 2/3 shared reference-list UI component
// (see OPERATIONAL-DECISIONS.md).

require_once __DIR__ . '/../../../includes/library_links.php';

$DATA_DIR = __DIR__ . '/../../../data/utility/firstaid';

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
    'basics'       => 'Basics: Get Help, CPR/AED, Kit',
    'breathing'    => 'Choking',
    'trauma'       => 'Bleeding, Burns & Injuries',
    'medical'      => 'Medical Emergencies',
    'environmental'=> 'Heat, Cold & Bites/Stings',
];

$groups = [];
foreach ($groupLabels as $key => $label) $groups[$key] = [];
foreach ($topics as $t) {
    if (isset($groups[$t['category']])) $groups[$t['category']][] = $t;
}

// Cross-link to the Document Library - metadata-driven, see includes/library_links.php.
$libraryLinksHtml = piratebox_render_library_links_html(piratebox_get_library_entries_for_page('/utility/firstaid/'));

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
    <title>PirateBox - First Aid Reference</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>First Aid Reference</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <div class="help-note">
            <p><strong>This is not a substitute for professional medical care or hands-on first-aid training.</strong> It's a conservative, high-level overview sourced from the American Red Cross and CDC, meant to help in a moment when you can't look it up online. Call 911 (or your local emergency number) for anything life-threatening. Where a skill genuinely requires practice to do safely - most notably CPR - that's noted explicitly below.</p>
        </div>

        <?= $libraryLinksHtml ?>

        <section class="doc-figure-section">
            <h2 class="radio-group-heading">Illustrated Reference: FM 4-25.11 Diagrams</h2>
            <p>A small set of diagrams selected from the full manual below, because a picture communicates some of these techniques better than text alone. Full pages are shown (not cropped) so captions and surrounding context stay attached. Public domain, U.S. Army Field Manual 4-25.11, <em>First Aid</em> (2002).</p>
            <div class="doc-figure-gallery">
                <figure class="doc-figure">
                    <img src="/utility/firstaid/images/fm4-25-11-fig2-31-pressure-points.png" alt="Diagram of digital pressure points on the body used to help control severe bleeding, at the temple, jaw, neck, shoulder, upper and lower arm, hand, two points on the thigh, foot, and lower leg" loading="lazy">
                    <figcaption>Figure 2-31. Pressure points for controlling severe bleeding when direct pressure on the wound isn't enough.<span class="doc-figure-source">Source: FM 4-25.11, p. 47 (public domain)</span></figcaption>
                </figure>
                <figure class="doc-figure">
                    <img src="/utility/firstaid/images/fm4-25-11-fig2-32-tourniquet.png" alt="Diagram of an improvised tourniquet applied above the knee" loading="lazy">
                    <figcaption>Figure 2-32. Improvised tourniquet placement, above the knee &mdash; last resort for life-threatening limb bleeding that direct pressure can't control.<span class="doc-figure-source">Source: FM 4-25.11, p. 49 (public domain)</span></figcaption>
                </figure>
                <figure class="doc-figure">
                    <img src="/utility/firstaid/images/fm4-25-11-fig3-13-burning-clothing.png" alt="Diagram showing a casualty's burning clothing being smothered with a field jacket and the casualty being rolled on the ground" loading="lazy">
                    <figcaption>Figure 3-13. Smothering burning clothing, then rolling the casualty to fully extinguish it.<span class="doc-figure-source">Source: FM 4-25.11, p. 68 (public domain)</span></figcaption>
                </figure>
                <figure class="doc-figure">
                    <img src="/utility/firstaid/images/fm4-25-11-fig4-1-fracture-types.png" alt="Diagram comparing a closed fracture with two types of open fracture" loading="lazy">
                    <figcaption>Figure 4-1. Closed vs. open fracture types &mdash; what to look for before splinting.<span class="doc-figure-source">Source: FM 4-25.11, p. 91 (public domain)</span></figcaption>
                </figure>
                <figure class="doc-figure">
                    <img src="/utility/firstaid/images/fm4-25-11-fig4-18-19-splints.png" alt="Diagrams of board splints applied to a fractured hip or thigh, and to a fractured or dislocated knee" loading="lazy">
                    <figcaption>Figures 4-18/4-19. Board splints for a fractured hip/thigh and for a fractured or dislocated knee.<span class="doc-figure-source">Source: FM 4-25.11, p. 102 (public domain)</span></figcaption>
                </figure>
            </div>
            <p class="radio-spectrum-caption">Not shown: recovery position &mdash; checked directly against the manual's text and it does not appear in FM 4-25.11, so no recovery-position diagram is included here rather than improvising one.</p>
        </section>

        <div class="radio-search-bar">
            <input type="text" id="radioSearch" placeholder="Search: bleeding, choking, burn, cpr, poison, allergic reaction..." aria-label="Search first aid reference">
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
                                <?php if (!empty($t['training_note'])): ?>
                                    <p class="radio-entry-tx-note"><strong>Training note:</strong> <?= htmlspecialchars($t['training_note']) ?></p>
                                <?php endif; ?>
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
            <a href="/utility/emergency/">Emergency</a>
            <a href="/utility/local/">Local Information</a>
            <a href="/utility/search/">Search</a>
            <a href="/utility/download/">Take This With You</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
