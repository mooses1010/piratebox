<?php
declare(strict_types=1);
session_start();

// "Take This With You" - Stage 19. Serves PRE-BUILT static export bundles
// (tools/build_export_bundles.py) - this page only reads the manifest and
// lists plain download links; it never builds anything on the fly.
//
// EXPORT PRIVACY: this page and the export builder only ever touch
// data/utility/* and the resulting public/utility/exports/ directory -
// there is no code path here that reaches chat/logbook/recovery
// messages/admin credentials/uploads/system or network configuration.
//
// Deliberately does NOT read piratebox_get_mode() - identical in Normal
// and Emergency Mode by design, like every other Utility section.
//
// Post-Stage-32 (Travel Mode): the two bundles that embed Local
// Information (complete-utility-library.zip, maps-local-bundle.zip),
// the raw local/ JSON export, and the local map catalog's own JSON file
// are hidden from these listings when Travel Mode is active - AND are
// additionally physically inaccessible by direct URL while active (see
// includes/travel_mode.php's quarantine mechanism) - hiding the link
// here is a UX nicety on top of that, not the actual protection.
// Previously-downloaded copies obviously cannot be revoked by this or
// anything else - noted explicitly on-page below.

require_once __DIR__ . '/../../../includes/travel_mode.php';
$travelMode = piratebox_get_travel_mode();

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
                <?php if ($travelMode): ?>
                    <p class="empty-state">Unavailable while Travel Mode is active - this bundle includes Local Information.</p>
                <?php elseif (isset($bundles['complete-utility-library.zip'])): ?>
                    <p><a href="/utility/exports/complete-utility-library.zip">Download complete-utility-library.zip</a> (<?= fmt_kb($bundles['complete-utility-library.zip']['bytes']) ?>)</p>
                <?php endif; ?>
            </section>

            <section class="help-section">
                <h2>Logical Bundles</h2>
                <p class="muted">A self-contained mini-site for just the topic you need - open its index.html after extracting.</p>
                <ul class="help-steps">
                    <?php foreach (['radio-bundle.zip' => 'Radio Reference Bundle', 'emergency-reference-bundle.zip' => 'Emergency Reference Bundle (Emergency + First Aid)', 'maps-local-bundle.zip' => 'Maps / Local Reference Bundle', 'manuals-documents-bundle.zip' => 'Manuals / Documents Bundle'] as $file => $label): ?>
                        <?php if ($travelMode && $file === 'maps-local-bundle.zip'): ?>
                            <li class="muted"><?= htmlspecialchars($label) ?> - unavailable while Travel Mode is active (includes Local Information)</li>
                        <?php elseif (isset($bundles[$file])): ?>
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
                        <?php if ($travelMode && $key === 'local'): ?>
                            <li class="muted"><?= htmlspecialchars($label) ?> - unavailable while Travel Mode is active</li>
                        <?php elseif (isset($jsonSizes[$key])): ?>
                            <li><?= htmlspecialchars($label) ?> (<?= fmt_kb($jsonSizes[$key]) ?>):
                                <?php
                                $dir = $EXPORTS_DIR . '/data/' . $key;
                                $files = is_dir($dir) ? array_values(array_filter(scandir($dir), fn($f) => str_ends_with($f, '.json'))) : [];
                                // Travel Mode: the maps section's own JSON directory mixes
                                // the generic reference/sources files with the region-
                                // specific catalog.json - exclude just that one file rather
                                // than hiding the whole maps row.
                                if ($travelMode && $key === 'maps') {
                                    $files = array_values(array_filter($files, fn($f) => $f !== 'catalog.json'));
                                }
                                foreach ($files as $i => $fn):
                                    if ($i > 0) echo ', ';
                                    ?><a href="/utility/exports/data/<?= rawurlencode($key) ?>/<?= rawurlencode($fn) ?>"><?= htmlspecialchars($fn) ?></a><?php
                                endforeach;
                                if ($travelMode && $key === 'maps') {
                                    echo ' <span class="muted">(local map catalog omitted - Travel Mode)</span>';
                                }
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
                <p><strong>How to use a downloaded bundle:</strong> extract the .zip file, then open <code>index.html</code> inside it in any web browser - no PirateBox, server, or Internet connection needed. Live-only features (uploading, chat, the logbook) aren't included, since those need an active PirateBox to talk to.</p>
            </div>

            <?php if ($travelMode): ?>
                <div class="help-note">
                    <p><strong>Travel Mode is active:</strong> anything downloaded from this device before Travel Mode was turned on may still contain this box's Local Information - turning Travel Mode on now cannot remove information from a copy that already left the device. This only affects what's downloadable going forward, from this point on.</p>
                </div>
            <?php endif; ?>

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
