<?php
declare(strict_types=1);
session_start();
require_once __DIR__ . '/../../../includes/helpers.php';

// "What's On This PirateBox?" manifest (Stage 20).
//
// Combines two sources, each read-only:
//   - Stage 19's export manifest.json (content counts, bundle sizes) -
//     reused rather than recomputed, since Stage 19 already built it.
//   - A live count of public/uploads/ - the exact same scandir() logic
//     index.php's file listing already uses; nothing new is exposed since
//     that listing is already public on the home page.
//
// PRIVACY: only ever reads data/utility/*, the exports manifest, and
// public/uploads/ - never chat/guestbook/recovery messages/admin
// credentials/system or network configuration. Deliberately does NOT
// read piratebox_get_mode() - identical in both modes, like every other
// Utility section.

function ref_load_json(string $path): array
{
    $raw = @file_get_contents($path);
    if ($raw === false) return [];
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

$exportManifest = ref_load_json(__DIR__ . '/../exports/manifest.json');
$counts = $exportManifest['counts'] ?? [];

// Live, public-safe upload count (same data already shown on the home page).
$UPLOAD_DIR = __DIR__ . '/../../uploads';
$uploadCount = 0;
$uploadBytes = 0;
foreach ((is_dir($UPLOAD_DIR) ? scandir($UPLOAD_DIR) : []) as $entry) {
    if ($entry === '.' || $entry === '..' || str_starts_with($entry, '.')) continue;
    $path = $UPLOAD_DIR . '/' . $entry;
    if (is_file($path)) {
        $uploadCount++;
        $size = @filesize($path);
        if ($size !== false) $uploadBytes += $size;
    }
}

$freeBytes = @disk_free_space($UPLOAD_DIR);

$rows = [
    ['Public shared files', (string) $uploadCount, piratebox_fmt_bytes($uploadBytes)],
    ['Radio reference entries', (string) (($counts['radio_services'] ?? 0) + ($counts['radio_modulation'] ?? 0) + ($counts['radio_guides'] ?? 0)), ''],
    ['Emergency guides', (string) ($counts['emergency_topics'] ?? 0), ''],
    ['First-aid topics', (string) ($counts['firstaid_topics'] ?? 0), ''],
    ['Maps reference entries', (string) ($counts['maps_reference'] ?? 0), ''],
    ['Library documents', (string) ($counts['library_documents'] ?? 0), ''],
    ['Total searchable items', (string) ($counts['search_index_items'] ?? 0), ''],
];

$bundleSizeKb = isset($exportManifest['bundles']['complete-utility-library.zip']['bytes'])
    ? round($exportManifest['bundles']['complete-utility-library.zip']['bytes'] / 1024, 1) . ' KB'
    : 'unknown';

$format = $_GET['format'] ?? '';
if (in_array($format, ['txt', 'json', 'csv'], true)) {
    $generatedAt = $exportManifest['generated_at'] ?? date('Y-m-d H:i');
    if ($format === 'json') {
        header('Content-Type: application/json');
        header('Content-Disposition: attachment; filename="piratebox-manifest.json"');
        echo json_encode(['generated_at' => $generatedAt, 'items' => $rows, 'complete_bundle_size' => $bundleSizeKb], JSON_PRETTY_PRINT);
        exit;
    }
    if ($format === 'csv') {
        header('Content-Type: text/csv');
        header('Content-Disposition: attachment; filename="piratebox-manifest.csv"');
        $out = fopen('php://output', 'w');
        fputcsv($out, ['category', 'count', 'size']);
        foreach ($rows as $r) fputcsv($out, $r);
        fclose($out);
        exit;
    }
    if ($format === 'txt') {
        header('Content-Type: text/plain');
        header('Content-Disposition: attachment; filename="piratebox-manifest.txt"');
        echo "PirateBox Manifest - generated $generatedAt\n\n";
        foreach ($rows as $r) {
            echo str_pad($r[0], 28) . $r[1] . ($r[2] ? " ($r[2])" : '') . "\n";
        }
        echo "\nComplete Offline Utility Library bundle: $bundleSizeKb\n";
        exit;
    }
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - What's On This PirateBox?</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>What's On This PirateBox?</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>A public inventory of what's available here - nothing private or system-related is included.</p>

        <div class="table-wrapper">
            <table>
                <thead><tr><th>Category</th><th>Count</th><th>Size</th></tr></thead>
                <tbody>
                    <?php foreach ($rows as $r): ?>
                        <tr><td><?= htmlspecialchars($r[0]) ?></td><td><?= htmlspecialchars($r[1]) ?></td><td><?= htmlspecialchars($r[2]) ?></td></tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        </div>

        <p>Complete Offline Utility Library bundle size: <strong><?= htmlspecialchars($bundleSizeKb) ?></strong> - see <a href="/utility/download/">Take This With You</a> to download it.</p>
        <?php if ($freeBytes !== false): ?>
            <p class="muted">Storage free: <?= htmlspecialchars(piratebox_fmt_bytes((int) $freeBytes)) ?></p>
        <?php endif; ?>

        <section class="help-section">
            <h2>Download This Manifest</h2>
            <div class="hero-actions">
                <a href="?format=txt">TXT</a>
                <a href="?format=json">JSON</a>
                <a href="?format=csv">CSV</a>
            </div>
        </section>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
            <a href="/utility/download/">Take This With You</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
