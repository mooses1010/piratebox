<?php
declare(strict_types=1);
session_start();

require_once __DIR__ . '/../../../includes/capability_state.php';
require_once __DIR__ . '/../../../includes/helpers.php';
require_once __DIR__ . '/../../../includes/reference_packs.php';

// About This PirateBox (self-description, docs/ARCHITECTURE.md §7/§9).
//
// PUBLIC tier of progressive disclosure - deliberately the shallowest
// end of "ANSWER -> USEFUL DETAIL -> TECHNICAL DETAIL -> DIAGNOSTICS"
// (docs/ARCHITECTURE.md §9). Shows only what this app's existing public
// Stats page (/utility/status/) already treats as public-safe (storage,
// device ID, aggregate service-up/down) - deliberately excludes anything
// that page keeps operator-only (power/undervoltage detail, per-
// capability breakdown - see admin/index.php's new "Capabilities &
// Health" section for that tier instead, gated by the same nginx Basic
// Auth every other admin content already requires). No new exposure
// decision was made here - this page follows the exposure boundary the
// Stats page already established, not a new one.
//
// Deliberately does NOT read piratebox_get_mode() for its own content -
// identical in Normal and Emergency Mode, same reasoning as every other
// universal reference page (Radio, Field Tools).

$caps = piratebox_get_capability_state();
$ops = piratebox_get_operational_state();
$counts = piratebox_capability_summary_counts($caps);

$coreStates = array_filter($caps, fn($c) => $c['layer'] === 'core');
$coreDegraded = count(array_filter($coreStates, fn($c) => $c['state'] !== 'AVAILABLE')) > 0;

$optionalStates = array_filter($caps, fn($c) => $c['layer'] === 'optional');
$optionalInstalled = count(array_filter($optionalStates, fn($c) => $c['state'] === 'AVAILABLE'));

$diskFree = $caps['storage']['detail']['free_bytes'] ?? null;
$diskTotal = $caps['storage']['detail']['total_bytes'] ?? null;

$refPacks = piratebox_get_reference_packs();
$scopeLabels = ['universal' => 'Universal', 'national' => 'National', 'regional' => 'Regional', 'local' => 'Local', 'live' => 'Current/Live'];
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>About This PirateBox</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>About This PirateBox</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>An independent, offline, local-first Wi-Fi file-share and field-utility appliance - no Internet connection, cloud account, or outside service is used or required. See <a href="/help.php">Help / About</a> for what PirateBox is and where this implementation came from.</p>

        <h2>Right now</h2>
        <div class="stat-grid">
            <div class="stat-card">
                <span class="stat-label">Core services</span>
                <span class="stat-value <?= $coreDegraded ? 'status-bad' : 'status-ok' ?>"><?= $coreDegraded ? 'Degraded' : 'Operational' ?></span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Storage</span>
                <span class="stat-value"><?= $diskFree !== null ? piratebox_fmt_bytes((int) $diskFree) . ' free of ' . piratebox_fmt_bytes((int) $diskTotal) : 'unknown' ?></span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Device ID</span>
                <span class="stat-value"><?= $ops['device_id'] !== null ? htmlspecialchars($ops['device_id']) : 'not assigned' ?></span>
            </div>
            <div class="stat-card">
                <span class="stat-label">Optional/field capabilities installed</span>
                <span class="stat-value"><?= $optionalInstalled ?></span>
            </div>
        </div>

        <div class="help-note">
            <p><strong>What this page shows:</strong> device-level facts only - the same information the public <a href="/utility/status/">Status</a> page already shows, organized around "what is this and is it working," not new information. It records no visitor identity or activity. An operator with the admin password sees a fuller capability/health breakdown at <code>/admin/</code> - that page requires the same password it always has; nothing about this page changes that boundary.</p>
        </div>

        <h2>What this PirateBox has</h2>
        <p>PirateBox is built in three layers: <strong>Core</strong> (the Wi-Fi network, this web app, storage - always present), <strong>Operational</strong> (things that improve reliability/usability but aren't required, like time-source and connection-statistics tracking), and <strong>Optional/Field</strong> (specialized field-instrument hardware, installed only if actually present). A capability failing never disables PirateBox - only degrades the one thing that failed. Full architecture documentation lives in this device's own local source repository, not published on this site.</p>

        <div class="table-wrapper">
            <table>
                <thead><tr><th>Layer</th><th>Working</th><th>Not installed</th></tr></thead>
                <tbody>
                    <?php foreach (['core' => 'Core', 'operational' => 'Operational', 'optional' => 'Optional/Field'] as $layerKey => $layerLabel): ?>
                        <?php
                        $inLayer = array_filter($caps, fn($c) => $c['layer'] === $layerKey);
                        $working = count(array_filter($inLayer, fn($c) => $c['state'] === 'AVAILABLE'));
                        $notInstalled = count(array_filter($inLayer, fn($c) => $c['state'] === 'NOT_INSTALLED'));
                        ?>
                        <tr><td><?= $layerLabel ?></td><td><?= $working ?> of <?= count($inLayer) ?></td><td><?= $notInstalled ?></td></tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        </div>

        <h2>Reference content</h2>
        <p>Organized universal &rarr; national &rarr; regional &rarr; local &rarr; current, per <a href="/utility/">the Utility Library</a>. Universal/national material is useful anywhere and doesn't depend on this device's location; local material adds relevance if the operator configures it, but nothing here requires that to be useful.</p>
        <div class="table-wrapper">
            <table>
                <thead><tr><th>Scope</th><th>Reference</th><th>State</th></tr></thead>
                <tbody>
                    <?php foreach (piratebox_reference_pack_scope_order() as $scopeKey): ?>
                        <?php foreach ($refPacks as $p): if ($p['scope'] !== $scopeKey) continue; ?>
                            <tr>
                                <td><?= htmlspecialchars($scopeLabels[$scopeKey] ?? $scopeKey) ?></td>
                                <td><?= $p['url'] !== null ? '<a href="' . htmlspecialchars($p['url']) . '">' . htmlspecialchars($p['title']) . '</a>' : htmlspecialchars($p['title']) ?></td>
                                <td class="<?= $p['state'] === 'INSTALLED' ? 'status-ok' : '' ?>"><?= htmlspecialchars($p['state']) ?><?= $p['entry_count'] !== null ? ' (' . $p['entry_count'] . ')' : '' ?></td>
                            </tr>
                        <?php endforeach; ?>
                    <?php endforeach; ?>
                </tbody>
            </table>
        </div>

        <h2>Also useful</h2>
        <div class="hero-actions">
            <a href="/utility/status/">Status</a>
            <a href="/utility/fieldtools/">Field Tools</a>
            <a href="/utility/">Utility Library</a>
            <a href="/found/">Found This Device?</a>
            <a href="/help.php">Help</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
