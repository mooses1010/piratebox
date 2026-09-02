<?php
declare(strict_types=1);
session_start();

// Computing / Networking Reference (Deep field library increment,
// 2026-09-02). PirateBox itself is a computing/networking appliance, so a
// compact durable offline reference for the concepts behind it (IP
// addressing, DNS/DHCP, ports, Wi-Fi, Ethernet, USB/serial, checksums,
// text encoding) is a genuine fit for this device's own mission -
// deliberately scoped tight, not a general Linux/sysadmin manual.
// Deliberately does NOT read piratebox_get_mode() - identical in Normal
// and Emergency Mode. Reuses the same shared reference-list UI pattern as
// Maps/Radio/Emergency/First Aid.

require_once __DIR__ . '/../../../includes/library_links.php';

$DATA_DIR = __DIR__ . '/../../../data/utility/computing';

function ref_load_json(string $path): array
{
    $raw = @file_get_contents($path);
    if ($raw === false) return [];
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

$reference = ref_load_json($DATA_DIR . '/reference.json');
$sources = ref_load_json($DATA_DIR . '/sources.json');

// Cross-link to the Document Library - metadata-driven, see includes/library_links.php.
$libraryLinksHtml = piratebox_render_library_links_html(piratebox_get_library_entries_for_page('/utility/computing/'));

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
    <title>PirateBox - Computing &amp; Networking Reference</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Computing &amp; Networking Reference</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>PirateBox is itself a small computer network - this page is a compact, offline reference for the concepts behind it and behind networking/computing in general: addressing, DNS/DHCP, ports, Wi-Fi, cabling, USB/serial, checksums, and text encoding. Deliberately tight in scope, not a general Linux/sysadmin manual.</p>

        <?= $libraryLinksHtml ?>

        <div class="radio-search-bar">
            <input type="text" id="radioSearch" placeholder="Search: ip address, subnet, dns, dhcp, port, wifi, ethernet, usb, hash, encoding..." aria-label="Search computing and networking reference">
            <div class="radio-chip-row" id="radioChips" role="group" aria-label="Filter">
                <button type="button" class="radio-chip active" data-group="all">All</button>
            </div>
        </div>

        <p class="radio-no-results" id="radioNoResults" hidden>No matches. Try a different search term.</p>

        <div id="radioResults">
            <section class="radio-group" data-group-section="reference">
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
                            <?php if (!empty($t['more_info'])): ?>
                                <p><?= htmlspecialchars($t['more_info']) ?></p>
                            <?php endif; ?>
                            <p class="radio-entry-source"><?= ref_source_line($sources, $t['source_id'] ?? null, $t['secondary_source_id'] ?? null, $t['confidence'] ?? null, $t['source_note'] ?? null) ?></p>
                        </div>
                    </details>
                <?php endforeach; ?>
            </section>
        </div>

        <div class="hero-actions">
            <a href="/utility/">&larr; Back to Utility Library</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
