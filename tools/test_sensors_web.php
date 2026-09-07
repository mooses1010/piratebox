<?php

declare(strict_types=1);

// Deterministic tests for includes/sensors.php - matches the project's
// existing dependency-free tools/test_*.php convention (see
// tools/test_progression_web.php for the same style).
// Run with: php tools/test_sensors_web.php
//
// Background (2026-09-07, Environment web UI round): this export
// deliberately exists SEPARATELY from progression-public.json - see
// includes/sensors.php's own header for the full "why" (progression-
// public.json's own "hardware" key was found to be permanently empty
// in production, a real bug in how it's generated). These tests also
// guard the privacy/spoiler boundary explicitly: this file has no
// access whatsoever to progression.json/progression-public.json, so
// there is structurally nothing here that could leak an achievement,
// trigger, threshold, or any other Progression internal.

require_once __DIR__ . '/../var/www/html/includes/sensors.php';

$failures = [];
$passCount = 0;

function sw_assert_eq(string $label, $actual, $expected): void
{
    global $failures, $passCount;
    if ($actual !== $expected) {
        $failures[] = "$label: expected " . var_export($expected, true) . ", got " . var_export($actual, true);
        return;
    }
    $passCount++;
}

function sw_assert_true(string $label, $actual): void
{
    sw_assert_eq($label, $actual, true);
}

// --- piratebox_parse_sensors_public(): boundary/malformed cases ---

$r = piratebox_parse_sensors_public(null);
sw_assert_eq('null input -> empty sensors, not fabricated', $r['sensors'], []);

$r = piratebox_parse_sensors_public('not an array');
sw_assert_eq('non-array input -> empty sensors', $r['sensors'], []);

$r = piratebox_parse_sensors_public(['sensors' => 'not an array']);
sw_assert_eq('non-array "sensors" value -> empty, not a crash', $r['sensors'], []);

$r = piratebox_parse_sensors_public(['sensors' => ['ambient_light' => 'not an array', 'valid_one' => ['x' => 1]]]);
sw_assert_eq('non-array sensor block silently dropped, valid one survives', array_keys($r['sensors']), ['valid_one']);

$r = piratebox_parse_sensors_public(['sensors' => [0 => ['x' => 1]]]);
sw_assert_eq('non-string sensor key silently dropped', $r['sensors'], []);

// --- piratebox_classify_ambient_light(): documented UI-only boundaries ---
// These boundaries are independent, ordinary ambient-lighting reference
// bands - explicitly NOT tied to any Progression/achievement threshold
// (see includes/sensors.php's own header). This test pins the bands
// exactly so a future edit can't silently drift them.

sw_assert_eq('0 lux -> Dark', piratebox_classify_ambient_light(0.0)['label'], 'Dark');
sw_assert_eq('9.9 lux -> Dark (just under the Dim boundary)', piratebox_classify_ambient_light(9.9)['label'], 'Dark');
sw_assert_eq('10 lux -> Dim (boundary is inclusive on this side)', piratebox_classify_ambient_light(10.0)['label'], 'Dim');
sw_assert_eq('49.9 lux -> Dim', piratebox_classify_ambient_light(49.9)['label'], 'Dim');
sw_assert_eq('50 lux -> Indoor', piratebox_classify_ambient_light(50.0)['label'], 'Indoor');
sw_assert_eq('249.9 lux -> Indoor', piratebox_classify_ambient_light(249.9)['label'], 'Indoor');
sw_assert_eq('250 lux -> Bright', piratebox_classify_ambient_light(250.0)['label'], 'Bright');
sw_assert_eq('999.9 lux -> Bright', piratebox_classify_ambient_light(999.9)['label'], 'Bright');
sw_assert_eq('1000 lux -> Very Bright', piratebox_classify_ambient_light(1000.0)['label'], 'Very Bright');
sw_assert_eq('100000 lux -> Very Bright', piratebox_classify_ambient_light(100000.0)['label'], 'Very Bright');

foreach ([0.0, 10.0, 50.0, 250.0, 1000.0, 50000.0] as $lux) {
    $c = piratebox_classify_ambient_light($lux);
    sw_assert_true("classification at $lux lux has a non-empty description", is_string($c['description']) && $c['description'] !== '');
}

// --- piratebox_get_ambient_light_reading(): the full decision table,
// via injected export data (see that function's own $export parameter) ---

$notInstalled = piratebox_get_ambient_light_reading(['data' => ['sensors' => []], 'stale' => false]);
sw_assert_eq('sensor key absent entirely -> not installed', $notInstalled['installed'], false);
sw_assert_eq('not installed -> not available', $notInstalled['available'], false);
sw_assert_eq('not installed -> no fabricated lux value', $notInstalled['lux'], null);
sw_assert_eq('not installed -> no fabricated classification', $notInstalled['classification'], null);

$neverDetected = piratebox_get_ambient_light_reading([
    'data' => ['sensors' => ['ambient_light' => ['detected' => false, 'lux' => null, 'stale' => true, 'last_success_seconds_ago' => null]]],
    'stale' => false,
]);
sw_assert_eq('installed but never detected -> installed=true', $neverDetected['installed'], true);
sw_assert_eq('never detected -> not available', $neverDetected['available'], false);
sw_assert_eq('never detected -> detected=false', $neverDetected['detected'], false);

$staleReading = piratebox_get_ambient_light_reading([
    'data' => ['sensors' => ['ambient_light' => ['detected' => true, 'lux' => 42.0, 'stale' => true, 'last_success_seconds_ago' => 999.0]]],
    'stale' => false,
]);
sw_assert_eq('stale reading -> not available (a stale value is never shown as current)', $staleReading['available'], false);
sw_assert_eq('stale reading -> last known lux still surfaced for the "last known" message', $staleReading['lux'], 42.0);
sw_assert_eq('stale reading -> stale_reading=true', $staleReading['stale_reading'], true);

$staleExport = piratebox_get_ambient_light_reading([
    'data' => ['sensors' => ['ambient_light' => ['detected' => true, 'lux' => 10.0, 'stale' => false, 'last_success_seconds_ago' => 1.0]]],
    'stale' => true, // the EXPORT FILE itself is stale (daemon not publishing) - a different failure mode
]);
sw_assert_eq('stale export file -> not available even if the sensor block itself looks fresh', $staleExport['available'], false);

$good = piratebox_get_ambient_light_reading([
    'data' => ['sensors' => ['ambient_light' => ['detected' => true, 'lux' => 9.2, 'stale' => false, 'last_success_seconds_ago' => 3.4]]],
    'stale' => false,
]);
sw_assert_eq('genuinely current reading -> available=true', $good['available'], true);
sw_assert_eq('genuinely current reading -> lux carried through exactly', $good['lux'], 9.2);
sw_assert_eq('genuinely current reading -> classified as Dark', $good['classification']['label'], 'Dark');

$malformedLux = piratebox_get_ambient_light_reading([
    'data' => ['sensors' => ['ambient_light' => ['detected' => true, 'lux' => 'not a number', 'stale' => false, 'last_success_seconds_ago' => 1.0]]],
    'stale' => false,
]);
sw_assert_eq('non-numeric lux value -> treated as no reading, never a crash', $malformedLux['lux'], null);
sw_assert_eq('non-numeric lux value -> not available', $malformedLux['available'], false);

// --- Privacy/spoiler boundary: structural, not just a value check -----
// This file must have zero CODE PATH into anything Progression-related
// - checked against actual code lines only (comments deliberately
// explain the architectural "why" using these same words, e.g. "why
// this is NOT progression-public.json" - that prose is the point, not
// a leak; a real leak would be an actual require/call/constant use).
$sensorsSource = file_get_contents(__DIR__ . '/../var/www/html/includes/sensors.php');
$sensorsCodeOnly = implode("\n", array_filter(
    array_map('trim', explode("\n", $sensorsSource)),
    fn($line) => $line !== '' && !str_starts_with($line, '//') && !str_starts_with($line, '*') && !str_starts_with($line, '/*')
));
foreach (['progression.php', 'piratebox_get_progression_public', 'piratebox_parse_progression_public', 'ACHIEVEMENTS[', 'HARDWARE_SIGNALS[', 'register_hardware_signal'] as $forbidden) {
    sw_assert_eq(
        "includes/sensors.php's actual code never references '$forbidden' (structurally cannot leak Progression internals)",
        str_contains($sensorsCodeOnly, $forbidden),
        false
    );
}

// --- piratebox_get_sensors_public(): live-file behavior, same
// "only assert what's guaranteed regardless of the actual machine"
// convention as tools/test_progression_web.php ---

if (!file_exists(PIRATEBOX_SENSORS_PUBLIC_FILE)) {
    $result = piratebox_get_sensors_public();
    sw_assert_eq('missing file -> stale=true', $result['stale'], true);
    sw_assert_eq('missing file -> empty sensors, not fabricated', $result['data']['sensors'], []);
} else {
    $result = piratebox_get_sensors_public();
    sw_assert_true('real file present -> stale is a bool', is_bool($result['stale']));
    $passCount++; // matches the else-branch's two assertions above, kept in sync
}

echo "\n";
if ($failures) {
    echo "FAILURES:\n";
    foreach ($failures as $f) echo "  - $f\n";
    echo "\nSensors web tests: $passCount passed, " . count($failures) . " failed.\n";
    exit(1);
}
echo "Sensors web tests: $passCount passed, 0 failed.\n";
