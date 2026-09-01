<?php
declare(strict_types=1);
session_start();
require_once __DIR__ . '/../../../includes/helpers.php';
require_once __DIR__ . '/../../../includes/metrics.php';
require_once __DIR__ . '/../../../includes/device_id.php';

// PirateBox public Stats / device status page (Stage 21).
//
// This is deliberately separate from /admin/ - it needs no login, and
// only ever shows AGGREGATE device health and content-catalog numbers.
// PRIVACY: no visitor identity, IP address, MAC address, individual
// download, or per-visitor activity is read or shown anywhere on this
// page - see the explicit statement rendered below. It reuses the same
// read-only /proc reads and /run/piratebox/status.json helper snapshot
// admin/index.php already uses (now shared via includes/metrics.php),
// and the same content-count numbers the manifest page already computes
// from tools/build_export_bundles.py's manifest.json - nothing here is
// computed a third way.
//
// Deliberately does NOT read piratebox_get_mode() for its OWN content -
// identical in Normal and Emergency Mode, like every other Utility
// section - but DOES show the current mode and cumulative Emergency
// Mode runtime as one of the stats themselves, since "is this PirateBox
// currently in Emergency Mode" is itself a fact worth a visitor knowing.

function ref_load_json(string $path): array
{
    $raw = @file_get_contents($path);
    if ($raw === false) return [];
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

$mode = piratebox_get_mode();

// --- Device / uptime / mode ---
$deviceId = piratebox_get_device_id();
$uptimeSeconds = piratebox_get_uptime_seconds();
[$emergencySeconds, $transitionCount] = piratebox_get_emergency_runtime_seconds();

$versionRaw = @file_get_contents(__DIR__ . '/../../../includes/VERSION');
$versionLine = $versionRaw !== false ? trim($versionRaw) : null;

// --- System resources (same /proc reads admin/index.php performs) ---
$diskTotal = @disk_total_space(__DIR__ . '/../../..');
$diskFree = @disk_free_space(__DIR__ . '/../../..');
[$memTotalKb, $memAvailableKb] = piratebox_get_meminfo_kb();
$cpuTempC = piratebox_get_cpu_temp_c();
[$load1, $load5, $load15] = piratebox_get_loadavg();

// --- Helper snapshot (Wi-Fi clients, per-service health) ---
$helper = piratebox_get_helper_status();
$helperStatus = $helper['status'];
$helperStale = $helper['stale'];

// --- Connection statistics (post-Stage-32) - see piratebox_get_connection_stats()
// for the full privacy design. null when the helper snapshot itself is
// missing/stale, same as every other helper-sourced stat above.
$connStats = piratebox_get_connection_stats();

// --- Content catalog (reuse Stage 19/20's export manifest - not a third
// independent count of the same numbers) ---
$exportManifest = ref_load_json(__DIR__ . '/../exports/manifest.json');
$counts = $exportManifest['counts'] ?? [];
$contentGeneratedAt = $exportManifest['generated_at'] ?? null;

$refCounts = [
    'Radio reference entries' => ($counts['radio_services'] ?? 0) + ($counts['radio_modulation'] ?? 0) + ($counts['radio_guides'] ?? 0),
    'Emergency guides' => $counts['emergency_topics'] ?? 0,
    'First-aid topics' => $counts['firstaid_topics'] ?? 0,
    'Maps reference entries' => $counts['maps_reference'] ?? 0,
    'Library documents' => $counts['library_documents'] ?? 0,
    'Total searchable items' => $counts['search_index_items'] ?? 0,
];

// Public shared files - same scandir() logic index.php's own file listing
// and manifest/index.php already use (nothing new exposed).
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

$rows = [
    ['Current mode', ucfirst($mode)],
    ['Uptime', piratebox_fmt_duration($uptimeSeconds)],
    ['Cumulative Emergency Mode runtime', piratebox_fmt_duration($emergencySeconds) . ' (' . $transitionCount . ' mode change' . ($transitionCount === 1 ? '' : 's') . ' logged)'],
    ['Storage free', piratebox_fmt_bytes($diskFree !== false ? (int) $diskFree : null) . ' of ' . piratebox_fmt_bytes($diskTotal !== false ? (int) $diskTotal : null)],
    ['RAM available', ($memAvailableKb !== null ? piratebox_fmt_bytes($memAvailableKb * 1024) : 'unknown') . ' of ' . ($memTotalKb !== null ? piratebox_fmt_bytes($memTotalKb * 1024) : 'unknown')],
    ['CPU temperature', $cpuTempC !== null ? round($cpuTempC, 1) . ' C' : 'unknown'],
    ['CPU load (1/5/15 min)', ($load1 !== null && $load5 !== null && $load15 !== null) ? "$load1 / $load5 / $load15" : 'unknown'],
    ['Wi-Fi clients connected', ($helperStatus && !$helperStale) ? (string) (int) $helperStatus['wifi_clients'] : 'unknown (status helper not reporting)'],
    ['Wi-Fi connection events (last 24h)', $connStats !== null ? (string) $connStats['last_24h'] : 'unknown (status helper not reporting)'],
    ['Peak simultaneous Wi-Fi clients (last 24h)', $connStats !== null ? (string) $connStats['peak_24h'] : 'unknown (status helper not reporting)'],
    ['Publicly shared files', $uploadCount . ' file' . ($uploadCount === 1 ? '' : 's') . ', ' . piratebox_fmt_bytes($uploadBytes) . ' total'],
];
foreach ($refCounts as $label => $count) {
    $rows[] = [$label, (string) $count];
}
$rows[] = ['Software version', $versionLine ?? 'unknown'];
$rows[] = ['Reference content last built', $contentGeneratedAt ?? 'unknown'];

$serviceNames = ['hostapd' => 'hostapd', 'dnsmasq' => 'dnsmasq', 'nginx' => 'nginx', 'php8.4-fpm' => 'PHP-FPM'];

$format = $_GET['format'] ?? '';
if (in_array($format, ['txt', 'json', 'csv'], true)) {
    $generatedAtNow = date('Y-m-d H:i:s');
    if ($format === 'json') {
        header('Content-Type: application/json');
        header('Content-Disposition: attachment; filename="piratebox-status.json"');
        $servicesOut = [];
        foreach ($serviceNames as $key => $label) {
            $servicesOut[$key] = $helperStatus && !$helperStale ? ($helperStatus['services'][$key] ?? null) : null;
        }
        echo json_encode(['generated_at' => $generatedAtNow, 'stats' => $rows, 'services' => $servicesOut], JSON_PRETTY_PRINT);
        exit;
    }
    if ($format === 'csv') {
        header('Content-Type: text/csv');
        header('Content-Disposition: attachment; filename="piratebox-status.csv"');
        $out = fopen('php://output', 'w');
        fputcsv($out, ['stat', 'value']);
        foreach ($rows as $r) fputcsv($out, $r);
        fclose($out);
        exit;
    }
    if ($format === 'txt') {
        header('Content-Type: text/plain');
        header('Content-Disposition: attachment; filename="piratebox-status.txt"');
        echo "PirateBox Status - generated $generatedAtNow\n\n";
        foreach ($rows as $r) {
            echo str_pad($r[0], 36) . $r[1] . "\n";
        }
        exit;
    }
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Status</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>PirateBox Status</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <div class="help-note">
            <p><strong>What this page shows:</strong> aggregate device health and content-catalog numbers only - how much storage is free, how many reference entries exist, whether background services are running. It records no visitor identity, IP address, MAC address, or individual activity, and keeps no per-visitor or per-download logs. This device ID (<?= $deviceId !== null ? htmlspecialchars($deviceId) : 'not assigned' ?>) identifies the PirateBox unit itself, not any visitor - see <a href="/found/">Found This Device?</a> for what it's for.</p>
        </div>

        <h2 class="admin-section-heading">Device <span class="section-tag">read-only</span></h2>
        <div class="table-wrapper">
            <table>
                <thead><tr><th>Stat</th><th>Value</th></tr></thead>
                <tbody>
                    <?php foreach ($rows as $r): ?>
                        <tr><td><?= htmlspecialchars($r[0]) ?></td><td><?= htmlspecialchars($r[1]) ?></td></tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        </div>

        <h2>Services</h2>
        <div class="stat-grid">
            <?php foreach ($serviceNames as $key => $label):
                $active = $helperStatus && !$helperStale ? ($helperStatus['services'][$key] ?? false) : null;
                ?>
                <div class="stat-card">
                    <span class="stat-label"><?= htmlspecialchars($label) ?></span>
                    <span class="stat-value <?= $active === true ? 'status-ok' : ($active === false ? 'status-bad' : '') ?>">
                        <?= $active === null ? 'unknown' : ($active ? 'active' : 'DOWN') ?>
                    </span>
                </div>
            <?php endforeach; ?>
        </div>
        <?php if ($helperStale): ?>
            <p class="muted status-bad">The background status helper isn't reporting right now, so Wi-Fi client count and service state above show as "unknown" rather than a guess. This doesn't affect PirateBox itself - file sharing, chat, the guestbook, and the Utility Library all keep working normally either way.</p>
        <?php endif; ?>

        <h2 class="admin-section-heading">Wi-Fi Connection Activity <span class="section-tag">aggregate only</span></h2>
        <div class="help-note">
            <p><strong>What "connection events" means:</strong> each time a device newly associates with this PirateBox's Wi-Fi, that's one connection event. A device that disconnects and reconnects later - Wi-Fi sleep/wake, walking out of range and back, a phone switching apps - is counted again each time. <strong>This is not a count of distinct people or devices</strong> - one person on one phone that reconnects five times in an hour shows as five connection events, not five visitors. "Peak simultaneous clients" is the highest number of devices ever seen connected at the same moment in the period shown, sampled roughly every 30 seconds.</p>
            <p>No MAC address, IP address, hostname, device name, or any other per-device identifier is ever stored - only small integer counts, grouped by hour. A device's identity is used for a few seconds at most (to tell "still connected" apart from "newly connected" between two 30-second checks) and is never written anywhere. Counts for the current, still-in-progress hour are kept only in memory and are folded into the SD card's saved history once that hour completes - so an unexpected power loss can lose at most the last (incomplete) hour of counts, never anything older.</p>
        </div>
        <?php if ($connStats === null): ?>
            <p class="muted status-bad">The background status helper isn't reporting right now, so connection statistics aren't available. This doesn't affect PirateBox itself.</p>
        <?php else: ?>
            <div class="table-wrapper">
                <table>
                    <thead><tr><th>Hour</th><th>Connection events</th><th>Peak simultaneous clients</th></tr></thead>
                    <tbody>
                        <?php if (empty($connStats['hourly'])): ?>
                            <tr><td colspan="3" class="muted">No data yet - the status helper only just started tracking this, or it's been less than an hour.</td></tr>
                        <?php else: ?>
                            <?php foreach (array_reverse($connStats['hourly']) as $bucket): ?>
                                <tr>
                                    <td><?= htmlspecialchars(date('Y-m-d H:i', $bucket['hour_start'])) ?></td>
                                    <td><?= (int) $bucket['count'] ?></td>
                                    <td><?= (int) $bucket['peak'] ?></td>
                                </tr>
                            <?php endforeach; ?>
                        <?php endif; ?>
                    </tbody>
                </table>
            </div>
        <?php endif; ?>

        <section class="help-section">
            <h2>Download This Status Snapshot</h2>
            <div class="hero-actions">
                <a href="?format=txt">TXT</a>
                <a href="?format=json">JSON</a>
                <a href="?format=csv">CSV</a>
            </div>
        </section>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
            <a href="/utility/manifest/">What's On This PirateBox?</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
