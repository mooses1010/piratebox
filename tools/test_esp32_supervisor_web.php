<?php

declare(strict_types=1);

// Deterministic tests for includes/esp32_supervisor.php - matches the
// project's existing dependency-free tools/test_*.php convention (see
// tools/test_sensors_web.php for the same style, which this file
// mirrors closely since both follow the same fetch/interpret split).
// Run with: php tools/test_esp32_supervisor_web.php

require_once __DIR__ . '/../var/www/html/includes/esp32_supervisor.php';

$failures = [];
$passCount = 0;

function ew_assert_eq(string $label, $actual, $expected): void
{
    global $failures, $passCount;
    if ($actual !== $expected) {
        $failures[] = "$label: expected " . var_export($expected, true) . ", got " . var_export($actual, true);
        return;
    }
    $passCount++;
}

// --- Not installed at all (no export file / undecodable) --------------

$notInstalled = piratebox_get_esp32_supervisor_status(['data' => [], 'stale' => true]);
ew_assert_eq('empty decoded data -> not installed', $notInstalled['installed'], false);
ew_assert_eq('not installed -> not available', $notInstalled['available'], false);
ew_assert_eq('not installed -> no fabricated fw_version', $notInstalled['fw_version'], null);
ew_assert_eq('not installed -> no fabricated temp', $notInstalled['temp_internal_c'], null);

// --- Installed, daemon running, board never connected ------------------

$neverConnected = piratebox_get_esp32_supervisor_status([
    'data' => ['generated_at' => time(), 'connected' => false, 'stale' => true, 'sensors' => []],
    'stale' => false,
]);
ew_assert_eq('daemon export present -> installed=true even if board absent', $neverConnected['installed'], true);
ew_assert_eq('board never connected -> not available', $neverConnected['available'], false);
ew_assert_eq('board never connected -> connected=false', $neverConnected['connected'], false);

// --- Connected and fresh -------------------------------------------------

$good = piratebox_get_esp32_supervisor_status([
    'data' => [
        'generated_at' => time(), 'connected' => true, 'stale' => false,
        'fw_version' => '0.1.0', 'board' => 'esp32s3-n16r8', 'reset_reason' => 'poweron',
        'uptime_ms' => 65000, 'reboot_count' => 0,
        'sensors' => ['temp_internal' => ['ok' => true, 'value' => 33.5, 'unit' => 'C']],
    ],
    'stale' => false,
]);
ew_assert_eq('fresh connected export -> available=true', $good['available'], true);
ew_assert_eq('fw_version carried through', $good['fw_version'], '0.1.0');
ew_assert_eq('board carried through', $good['board'], 'esp32s3-n16r8');
ew_assert_eq('uptime_ms converted to seconds', $good['uptime_seconds'], 65.0);
ew_assert_eq('temp_internal_c extracted from sensors block', $good['temp_internal_c'], 33.5);

// --- Sensor reporting ok=false -> no fabricated temperature -------------

$sensorFailed = piratebox_get_esp32_supervisor_status([
    'data' => [
        'generated_at' => time(), 'connected' => true, 'stale' => false,
        'sensors' => ['temp_internal' => ['ok' => false, 'err' => 'read_failed']],
    ],
    'stale' => false,
]);
ew_assert_eq('sensor ok=false -> temp is null, never fabricated', $sensorFailed['temp_internal_c'], null);
ew_assert_eq('board itself still counts as available even if one sensor failed', $sensorFailed['available'], true);

// --- Heartbeat gone stale on the board side (daemon still publishing) --

$boardStale = piratebox_get_esp32_supervisor_status([
    'data' => ['generated_at' => time(), 'connected' => true, 'stale' => true, 'sensors' => []],
    'stale' => false,
]);
ew_assert_eq('board-side stale flag -> not available', $boardStale['available'], false);
ew_assert_eq('board-side stale flag -> connected still true (link was established)', $boardStale['connected'], true);

// --- Export file itself stale (daemon stopped publishing) --------------

$exportStale = piratebox_get_esp32_supervisor_status([
    'data' => ['generated_at' => time() - 999, 'connected' => true, 'stale' => false, 'sensors' => []],
    'stale' => true,
]);
ew_assert_eq('stale export file -> not available even if the data blob looks fresh', $exportStale['available'], false);
ew_assert_eq('stale export file -> connected forced false', $exportStale['connected'], false);

// --- Malformed field types degrade cleanly, never crash -----------------

$malformed = piratebox_get_esp32_supervisor_status([
    'data' => [
        'generated_at' => time(), 'connected' => true, 'stale' => false,
        'fw_version' => 12345, 'uptime_ms' => 'not a number',
        'sensors' => ['temp_internal' => ['ok' => true, 'value' => 'not a number']],
    ],
    'stale' => false,
]);
ew_assert_eq('non-string fw_version -> null, not fabricated', $malformed['fw_version'], null);
ew_assert_eq('non-numeric uptime_ms -> null', $malformed['uptime_seconds'], null);
ew_assert_eq('non-numeric temp value -> null', $malformed['temp_internal_c'], null);

// --- Privacy/spoiler boundary: structural, not just a value check -----
$src = file_get_contents(__DIR__ . '/../var/www/html/includes/esp32_supervisor.php');
$codeOnly = implode("\n", array_filter(
    array_map('trim', explode("\n", $src)),
    fn($line) => $line !== '' && !str_starts_with($line, '//') && !str_starts_with($line, '*') && !str_starts_with($line, '/*')
));
foreach (['progression.php', 'piratebox_get_progression_public', 'ACHIEVEMENTS[', 'HARDWARE_SIGNALS[', 'register_hardware_signal'] as $forbidden) {
    ew_assert_eq(
        "includes/esp32_supervisor.php's actual code never references '$forbidden'",
        str_contains($codeOnly, $forbidden),
        false
    );
}

// --- piratebox_get_ds18b20_probes(): public-page display logic ---------
// (2026-09-07, DS18B20 phase; reshaped 2026-09-08 for the
// hardware-awareness phase - commissioned-but-unnamed probes now show
// a generic "Probe N" label instead of being folded into a bare count)

$noExport = piratebox_get_ds18b20_probes(['data' => [], 'stale' => true]);
ew_assert_eq('no export -> no probes shown', $noExport['probes'], []);
ew_assert_eq('no export -> zero uncommissioned count', $noExport['uncommissioned_count'], 0);

$neverFoundAny = piratebox_get_ds18b20_probes([
    'data' => ['connected' => true, 'stale' => false, 'sensors' => []],
    'stale' => false,
]);
ew_assert_eq('ds18b20 capability never present -> no probes shown', $neverFoundAny['probes'], []);

$disconnected = piratebox_get_ds18b20_probes([
    'data' => [
        'connected' => false, 'stale' => true,
        'sensors' => ['ds18b20' => ['bus_ok' => true, 'probes' => [
            '28ff641e04170378' => ['ok' => true, 'value' => 21.0, 'name' => 'Enclosure', 'physical_index' => 1],
        ]]],
    ],
    'stale' => false,
]);
ew_assert_eq('supervisor disconnected -> no probes shown even if the data blob has them', $disconnected['probes'], []);

$namedAndUncommissioned = piratebox_get_ds18b20_probes([
    'data' => [
        'connected' => true, 'stale' => false,
        'sensors' => ['ds18b20' => ['bus_ok' => true, 'probes' => [
            '28ff641e04170378' => ['ok' => true, 'value' => 21.4, 'name' => 'Enclosure', 'physical_index' => 1],
            '28aa112233445566' => ['ok' => true, 'value' => 4.0, 'name' => null, 'physical_index' => null],
        ]]],
    ],
    'stale' => false,
]);
ew_assert_eq('exactly one named probe surfaced', count($namedAndUncommissioned['probes']), 1);
ew_assert_eq('named probe shows its own name as the label', $namedAndUncommissioned['probes'][0]['label'], 'Enclosure');
ew_assert_eq('named probe flagged has_name=true', $namedAndUncommissioned['probes'][0]['has_name'], true);
ew_assert_eq('named probe carries its value', $namedAndUncommissioned['probes'][0]['value_c'], 21.4);
ew_assert_eq('ROM address never appears in the public shape', array_key_exists('rom', $namedAndUncommissioned['probes'][0]), false);
ew_assert_eq('the never-commissioned probe is counted, not surfaced', $namedAndUncommissioned['uncommissioned_count'], 1);

$commissionedButUnnamed = piratebox_get_ds18b20_probes([
    'data' => [
        'connected' => true, 'stale' => false,
        'sensors' => ['ds18b20' => ['bus_ok' => true, 'probes' => [
            '28ff641e04170378' => ['ok' => true, 'value' => 30.0, 'name' => null, 'physical_index' => 4],
        ]]],
    ],
    'stale' => false,
]);
ew_assert_eq('commissioned-but-unnamed probe is shown, not hidden', count($commissionedButUnnamed['probes']), 1);
ew_assert_eq('commissioned-but-unnamed probe gets a generic physical-index label',
    $commissionedButUnnamed['probes'][0]['label'], 'Probe 4');
ew_assert_eq('commissioned-but-unnamed probe flagged has_name=false', $commissionedButUnnamed['probes'][0]['has_name'], false);
ew_assert_eq('commissioned-but-unnamed probe is not counted as uncommissioned',
    $commissionedButUnnamed['uncommissioned_count'], 0);

$failedNamedProbe = piratebox_get_ds18b20_probes([
    'data' => [
        'connected' => true, 'stale' => false,
        'sensors' => ['ds18b20' => ['bus_ok' => true, 'probes' => [
            '28ff641e04170378' => ['ok' => false, 'err' => 'disconnected', 'name' => 'Battery', 'physical_index' => 2],
        ]]],
    ],
    'stale' => false,
]);
ew_assert_eq('failed named probe still surfaced (so the page can show "not responding")', count($failedNamedProbe['probes']), 1);
ew_assert_eq('failed probe has ok=false', $failedNamedProbe['probes'][0]['ok'], false);
ew_assert_eq('failed probe has no fabricated value', $failedNamedProbe['probes'][0]['value_c'], null);

$sortOrder = piratebox_get_ds18b20_probes([
    'data' => [
        'connected' => true, 'stale' => false,
        'sensors' => ['ds18b20' => ['bus_ok' => true, 'probes' => [
            '28ff641e04170378' => ['ok' => true, 'value' => 1.0, 'name' => 'Zebra', 'physical_index' => null],
            '28aa112233445566' => ['ok' => true, 'value' => 2.0, 'name' => 'Alpha', 'physical_index' => null],
            '28bb112233445566' => ['ok' => true, 'value' => 3.0, 'name' => null, 'physical_index' => 5],
            '28cc112233445566' => ['ok' => true, 'value' => 4.0, 'name' => null, 'physical_index' => 2],
        ]]],
    ],
    'stale' => false,
]);
ew_assert_eq('named probes sort alphabetically first, then unnamed probes by physical index',
    array_column($sortOrder['probes'], 'label'), ['Alpha', 'Zebra', 'Probe 2', 'Probe 5']);

$malformedProbeEntry = piratebox_get_ds18b20_probes([
    'data' => [
        'connected' => true, 'stale' => false,
        'sensors' => ['ds18b20' => ['bus_ok' => true, 'probes' => [
            '28ff641e04170378' => 'not an array',
            0 => ['ok' => true, 'value' => 1.0, 'name' => 'X'],  // non-string key
        ]]],
    ],
    'stale' => false,
]);
ew_assert_eq('malformed probe entries never crash, never fabricate', $malformedProbeEntry['probes'], []);

// --- piratebox_classify_esp32_link() / piratebox_classify_simple_sensor()
// / piratebox_classify_ds18b20_bus(): shared health vocabulary
// (2026-09-08, hardware-awareness phase) - mirrors piratebox_hardware_
// health.py's Python vocabulary/test coverage.

ew_assert_eq('never installed -> UNKNOWN', piratebox_classify_esp32_link(['installed' => false, 'connected' => false, 'stale' => true]), 'UNKNOWN');
ew_assert_eq('connected and fresh -> AVAILABLE', piratebox_classify_esp32_link(['installed' => true, 'connected' => true, 'stale' => false]), 'AVAILABLE');
ew_assert_eq('connected but stale heartbeat -> DEGRADED', piratebox_classify_esp32_link(['installed' => true, 'connected' => true, 'stale' => true]), 'DEGRADED');
ew_assert_eq('not connected -> UNAVAILABLE', piratebox_classify_esp32_link(['installed' => true, 'connected' => false, 'stale' => true]), 'UNAVAILABLE');

$linkDown = ['installed' => true, 'connected' => false, 'stale' => true];
ew_assert_eq('simple sensor inherits a down link', piratebox_classify_simple_sensor($linkDown, [], 'bh1750'), 'UNAVAILABLE');

$linkUp = ['installed' => true, 'connected' => true, 'stale' => false];
ew_assert_eq('capability never advertised -> NOT_INSTALLED',
    piratebox_classify_simple_sensor($linkUp, ['capabilities' => ['temp_internal']], 'bh1750'), 'NOT_INSTALLED');
ew_assert_eq('advertised and ok -> AVAILABLE',
    piratebox_classify_simple_sensor($linkUp, ['capabilities' => ['bh1750'], 'sensors' => ['bh1750' => ['ok' => true, 'value' => 42.5]]], 'bh1750'),
    'AVAILABLE');
ew_assert_eq('advertised but not ok -> DEGRADED',
    piratebox_classify_simple_sensor($linkUp, ['capabilities' => ['bh1750'], 'sensors' => ['bh1750' => ['ok' => false]]], 'bh1750'),
    'DEGRADED');

$busLinkDown = piratebox_classify_ds18b20_bus($linkDown, []);
ew_assert_eq('ds18b20 bus inherits a down link', $busLinkDown['state'], 'UNAVAILABLE');

$busNeverInstalled = piratebox_classify_ds18b20_bus($linkUp, ['capabilities' => []]);
ew_assert_eq('capability never present, nothing commissioned -> NOT_INSTALLED', $busNeverInstalled['state'], 'NOT_INSTALLED');

$busAllOk = piratebox_classify_ds18b20_bus($linkUp, [
    'capabilities' => ['ds18b20'],
    'sensors' => ['ds18b20' => [
        'bus_ok' => true,
        'probes' => [
            'aaa' => ['ok' => true, 'value' => 29.5],
            'bbb' => ['ok' => true, 'value' => 29.6],
        ],
        'commissioned' => ['aaa' => ['name' => null, 'physical_index' => 1], 'bbb' => ['name' => null, 'physical_index' => 2]],
    ]],
]);
ew_assert_eq('all commissioned probes present and ok -> AVAILABLE', $busAllOk['state'], 'AVAILABLE');
ew_assert_eq('probes_ok reflects the live count', $busAllOk['probes_ok'], 2);

$busMissingOne = piratebox_classify_ds18b20_bus($linkUp, [
    'capabilities' => ['ds18b20'],
    'sensors' => ['ds18b20' => [
        'bus_ok' => true,
        'probes' => ['aaa' => ['ok' => true, 'value' => 29.5]],
        'commissioned' => ['aaa' => ['name' => null, 'physical_index' => 1], 'bbb' => ['name' => null, 'physical_index' => 2]],
    ]],
]);
ew_assert_eq('a commissioned probe missing this cycle -> DEGRADED', $busMissingOne['state'], 'DEGRADED');
ew_assert_eq('missing_commissioned lists the absent ROM', $busMissingOne['missing_commissioned'], ['bbb']);

$busOkFalse = piratebox_classify_ds18b20_bus($linkUp, [
    'capabilities' => ['ds18b20'],
    'sensors' => ['ds18b20' => ['bus_ok' => false, 'probes' => [], 'commissioned' => []]],
]);
ew_assert_eq('bus_ok false -> UNAVAILABLE even with nothing commissioned', $busOkFalse['state'], 'UNAVAILABLE');

$busNeverWired = piratebox_classify_ds18b20_bus($linkUp, [
    'capabilities' => ['ds18b20'],
    'sensors' => ['ds18b20' => ['bus_ok' => true, 'probes' => [], 'commissioned' => []]],
]);
ew_assert_eq('genuinely never wired (bus_ok true, nothing found/commissioned) -> NOT_INSTALLED', $busNeverWired['state'], 'NOT_INSTALLED');

// --- Live-file behavior, same "only assert what's guaranteed" convention

if (!file_exists(PIRATEBOX_ESP32_PUBLIC_FILE)) {
    $result = piratebox_get_esp32_public();
    ew_assert_eq('missing file -> stale=true', $result['stale'], true);
    ew_assert_eq('missing file -> empty data, not fabricated', $result['data'], []);
} else {
    $result = piratebox_get_esp32_public();
    ew_assert_eq('real file present -> stale is a bool', is_bool($result['stale']), true);
}

echo "\n";
if ($failures) {
    echo "FAILURES:\n";
    foreach ($failures as $f) echo "  - $f\n";
    echo "\nESP32 supervisor web tests: $passCount passed, " . count($failures) . " failed.\n";
    exit(1);
}
echo "ESP32 supervisor web tests: $passCount passed, 0 failed.\n";
