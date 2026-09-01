<?php
declare(strict_types=1);
session_start();

// "Take This With You" - Stage 19. Serves PRE-BUILT static export bundles
// (tools/build_export_bundles.py) - this page only reads the manifest and
// lists plain download links; it never builds anything on the fly.
//
// EXPORT PRIVACY: this page and the export builder only ever touch
// data/utility/* and the resulting public/utility/exports/ directory -
// there is no code path here that reaches chat/guestbook/recovery
// messages/admin credentials/uploads/system or network configuration.
//
// Deliberately does NOT read piratebox_get_mode() - identical in Normal
// and Emergency Mode by design, like every other Utility section.

$EXPORTS_DIR = __DIR__ . '/../exports';

function ref_load_json(string $path): array
{
    $raw = @file_get_contents($path);
    if ($raw === false) return [];
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

$manifest = ref_load_json($EXPORTS_DIR . '/manifest.json');
$bundles = $manifest['bundles'] ?? [];
$jsonSizes = $manifest['individual_sections_json_bytes'] ?? [];
$generatedAt = $manifest['generated_at'] ?? null;

function fmt_kb($bytes): string
{
    if (!is_numeric($bytes)) return '';
    return round(((float) $bytes) / 1024, 1) . ' KB';
}

$sectionLabels = [
    'radio' => 'Radio Reference', 'emergency' => 'Emergency / Outage Reference',
    'firstaid' => 'First Aid Reference', 'maps' => 'Maps & Location Reference',
    'local' => 'Local Information', 'library' => 'Document Library',
];
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Take This With You</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Take This With You</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>You're only in Wi-Fi range temporarily - take useful information with you before you leave. Save any of these to your phone or computer; once downloaded, they work completely offline, without this PirateBox, a server, or the Internet.</p>

        <?php if (empty($bundles)): ?>
            <p class="empty-state">Export bundles haven't been built yet on this device. Run tools/build_export_bundles.py.</p>
        <?php else: ?>

            <section class="help-section">
                <h2>Complete Offline Utility Library</h2>
                <p class="muted">Everything - Radio, Emergency, First Aid, Maps, Local Information, and Library, all in one self-contained package.</p>
                <?php if (isset($bundles['complete-utility-library.zip'])): ?>
                    <p><a href="/utility/exports/complete-utility-library.zip">Download complete-utility-library.zip</a> (<?= fmt_kb($bundles['complete-utility-library.zip']['bytes']) ?>)</p>
                <?php endif; ?>
            </section>

            <section class="help-section">
                <h2>Logical Bundles</h2>
                <p class="muted">A self-contained mini-site for just the topic you need - open its index.html after extracting.</p>
                <ul class="help-steps">
                    <?php foreach (['radio-bundle.zip' => 'Radio Reference Bundle', 'emergency-reference-bundle.zip' => 'Emergency Reference Bundle (Emergency + First Aid)', 'maps-local-bundle.zip' => 'Maps / Local Reference Bundle', 'manuals-documents-bundle.zip' => 'Manuals / Documents Bundle'] as $file => $label): ?>
                        <?php if (isset($bundles[$file])): ?>
                            <li><a href="/utility/exports/<?= rawurlencode($file) ?>"><?= htmlspecialchars($label) ?></a> - <?= fmt_kb($bundles[$file]['bytes']) ?></li>
                        <?php endif; ?>
                    <?php endforeach; ?>
                </ul>
            </section>

            <section class="help-section">
                <h2>Individual Section Data (Raw JSON)</h2>
                <p class="muted">The raw underlying data for each section, exactly as this PirateBox uses it - useful if you want the data itself rather than a browsable page.</p>
                <ul class="help-steps">
                    <?php foreach ($sectionLabels as $key => $label): ?>
                        <?php if (isset($jsonSizes[$key])): ?>
                            <li><?= htmlspecialchars($label) ?> (<?= fmt_kb($jsonSizes[$key]) ?>):
                                <?php
                                $dir = $EXPORTS_DIR . '/data/' . $key;
                                $files = is_dir($dir) ? array_values(array_filter(scandir($dir), fn($f) => str_ends_with($f, '.json'))) : [];
                                foreach ($files as $i => $fn):
                                    if ($i > 0) echo ', ';
                                    ?><a href="/utility/exports/data/<?= rawurlencode($key) ?>/<?= rawurlencode($fn) ?>"><?= htmlspecialchars($fn) ?></a><?php
                                endforeach;
                                ?>
                            </li>
                        <?php endif; ?>
                    <?php endforeach; ?>
                </ul>
            </section>

            <?php if (isset($bundles['radio-services.csv'])): ?>
                <section class="help-section">
                    <h2>Radio Services (CSV)</h2>
                    <p class="muted">All 25 amateur/broadcast/service bands as a spreadsheet - name, frequency range, mode, license requirement.</p>
                    <p><a href="/utility/exports/radio-services.csv">Download radio-services.csv</a> (<?= fmt_kb($bundles['radio-services.csv']['bytes']) ?>)</p>
                </section>
            <?php endif; ?>

            <div class="help-note">
                <p><strong>How to use a downloaded bundle:</strong> extract the .zip file, then open <code>index.html</code> inside it in any web browser - no PirateBox, server, or Internet connection needed. Live-only features (uploading, chat, guestbook) aren't included, since those need an active PirateBox to talk to.</p>
            </div>

            <?php if ($generatedAt): ?>
                <p class="muted">These bundles were last built <?= htmlspecialchars($generatedAt) ?>. They may not reflect changes made after that if content was updated since.</p>
            <?php endif; ?>
        <?php endif; ?>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
            <a href="/utility/manifest/">What's On This PirateBox?</a>
            <a href="/utility/search/">Search</a>
            <a href="/utility/status/">Status</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
