<?php
declare(strict_types=1);
session_start();

// Document Library (Stage 7). Data-driven catalog - currently EMPTY (no
// documents bundled, per instruction not to bulk-download or fabricate
// entries). Adding a real document later is: drop the file in
// public/utility/library/files/, add one entry to
// data/utility/library/catalog.json - no PHP editing needed. Run
// tools/check_library_catalog.py to verify the catalog and files agree.
//
// Architecture note: files live under webroot (public/utility/library/
// files/), same pattern as Stage 5's Maps catalog, NOT the previously-
// discussed outside-webroot /var/www/library design - deliberately, to
// avoid needing an open_basedir change for a framework with no real
// document payload yet. See docs/OPERATIONAL-DECISIONS.md.
//
// Deliberately does NOT read piratebox_get_mode() - identical in Normal
// and Emergency Mode by design. Reuses the shared reference-list UI
// component from Stages 2-4.

$DATA_DIR = __DIR__ . '/../../../data/utility/library';

function ref_load_json(string $path): array
{
    $raw = @file_get_contents($path);
    if ($raw === false) return [];
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

$categories = ref_load_json($DATA_DIR . '/categories.json');
$catalog = ref_load_json($DATA_DIR . '/catalog.json');

$groups = [];
foreach ($categories as $key => $label) $groups[$key] = [];
foreach ($catalog as $doc) {
    if (isset($groups[$doc['category']])) $groups[$doc['category']][] = $doc;
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
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Document Library</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Document Library</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>A catalog for manuals and reference documents stored on this device - empty until documents are deliberately added for this box's actual equipment and needs.</p>

        <div class="radio-search-bar">
            <input type="text" id="radioSearch" placeholder="Search documents..." aria-label="Search document library">
            <div class="radio-chip-row" id="radioChips" role="group" aria-label="Filter by category">
                <button type="button" class="radio-chip active" data-group="all">All</button>
                <?php foreach ($categories as $key => $label): ?>
                    <button type="button" class="radio-chip" data-group="<?= htmlspecialchars($key) ?>"><?= htmlspecialchars($label) ?></button>
                <?php endforeach; ?>
            </div>
        </div>

        <p class="radio-no-results" id="radioNoResults" hidden>No matches. Try a different search term or choose "All".</p>

        <div id="radioResults">
            <?php if (empty($catalog)): ?>
                <p class="empty-state">No documents have been added yet. See "Adding a Document" below.</p>
            <?php else: ?>
                <?php foreach ($categories as $groupKey => $groupLabel): ?>
                    <?php if (empty($groups[$groupKey])) continue; ?>
                    <section class="radio-group" data-group-section="<?= htmlspecialchars($groupKey) ?>">
                        <h2 class="radio-group-heading"><?= htmlspecialchars($groupLabel) ?></h2>
                        <?php foreach ($groups[$groupKey] as $docIdx => $doc): ?>
                            <?php $search = ref_search_blob([$doc['title'] ?? '', $doc['description'] ?? '', $doc['tags'] ?? [], $groupKey]); ?>
                            <details class="radio-entry" id="<?= htmlspecialchars($doc['id'] ?? ('doc-' . $docIdx)) ?>" data-group="<?= htmlspecialchars($groupKey) ?>" data-search="<?= $search ?>">
                                <summary>
                                    <span class="radio-entry-name"><?= htmlspecialchars($doc['title'] ?? 'Untitled document') ?></span>
                                    <span class="radio-entry-mode-badge"><?= htmlspecialchars($doc['file_type'] ?? '') ?></span>
                                </summary>
                                <div class="radio-entry-detail">
                                    <?php if (!empty($doc['description'])): ?><p><?= htmlspecialchars($doc['description']) ?></p><?php endif; ?>
                                    <?php if (!empty($doc['file'])): ?>
                                        <p><a href="/utility/library/files/<?= rawurlencode($doc['file']) ?>" target="_blank" rel="noopener">Open document</a><?= !empty($doc['file_size']) ? ' (' . htmlspecialchars($doc['file_size']) . ')' : '' ?></p>
                                    <?php endif; ?>
                                    <p class="radio-entry-source">
                                        <?= !empty($doc['source']) ? 'Source: ' . htmlspecialchars($doc['source']) : '' ?>
                                        <?= !empty($doc['date_version']) ? ' (' . htmlspecialchars($doc['date_version']) . ')' : '' ?>
                                        <?php if (!empty($doc['provenance_notes'])): ?><br><?= htmlspecialchars($doc['provenance_notes']) ?><?php endif; ?>
                                    </p>
                                </div>
                            </details>
                        <?php endforeach; ?>
                    </section>
                <?php endforeach; ?>
            <?php endif; ?>
        </div>

        <div class="help-note">
            <p><strong>Adding a document:</strong> copy the file into <code>/var/www/html/public/utility/library/files/</code>, then add one entry to <code>data/utility/library/catalog.json</code> (schema documented in that same directory's <code>README.md</code>). Run <code>tools/check_library_catalog.py</code> to verify everything matches. No PHP editing required. Don't add copyrighted material you don't have the right to redistribute.</p>
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
