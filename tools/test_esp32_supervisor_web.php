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
