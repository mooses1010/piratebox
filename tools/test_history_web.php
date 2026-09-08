<?php

declare(strict_types=1);

// Deterministic tests for includes/history.php - matches the project's
// existing dependency-free tools/test_*.php convention. Run with:
//   php tools/test_history_web.php

require_once __DIR__ . '/../var/www/html/includes/history.php';

$failures = [];
$passCount = 0;

function hw_assert_eq(string $label, $actual, $expected): void
{
    global $failures, $passCount;
    if ($actual !== $expected) {
        $failures[] = "$label: expected " . var_export($expected, true) . ", got " . var_export($actual, true);
        return;
    }
    $passCount++;
}

// --- piratebox_history_is_safe_signal_id() -----------------------------

hw_assert_eq('normal id accepted', piratebox_history_is_safe_signal_id('ds18b20_28fd856b0000003b'), true);
hw_assert_eq('path traversal rejected', piratebox_history_is_safe_signal_id('../etc/passwd'), false);
hw_assert_eq('slash rejected', piratebox_history_is_safe_signal_id('a/b'), false);
hw_assert_eq('empty rejected', piratebox_history_is_safe_signal_id(''), false);
hw_assert_eq('overlong rejected', piratebox_history_is_safe_signal_id(str_repeat('a', 200)), false);
hw_assert_eq('space rejected', piratebox_history_is_safe_signal_id('has space'), false);

// --- piratebox_history_choose_tier() ------------------------------------

hw_assert_eq('6h uses raw', piratebox_history_choose_tier(6 * 3600), 'raw');
hw_assert_eq('24h uses raw', piratebox_history_choose_tier(24 * 3600), 'raw');
hw_assert_eq('7d uses raw (within raw retention)', piratebox_history_choose_tier(7 * 86400), 'raw');
hw_assert_eq('30d uses hourly', piratebox_history_choose_tier(30 * 86400), 'hourly');
hw_assert_eq('366d uses daily', piratebox_history_choose_tier(366 * 86400), 'daily');

// --- piratebox_history_probe_slug_map(): ROM redaction + label resolution

$noExport = piratebox_history_probe_slug_map(['data' => [], 'stale' => true]);
hw_assert_eq('no export -> empty map', $noExport, []);

$fiveCommissioned = [
    'data' => [
        'connected' => true, 'stale' => false,
        'sensors' => ['ds18b20' => ['bus_ok' => true, 'probes' => [], 'commissioned' => [
            'aaa1111111111111' => ['name' => null, 'physical_index' => 1],
            'bbb2222222222222' => ['name' => 'Battery', 'physical_index' => 2],
            'ccc3333333333333' => ['name' => null, 'physical_index' => 3],
        ]]],
    ],
    'stale' => false,
];
$map = piratebox_history_probe_slug_map($fiveCommissioned);
hw_assert_eq('three probes mapped', count($map), 3);
hw_assert_eq('unnamed probe gets generic label', $map['probe_1']['label'], 'Probe 1');
hw_assert_eq('named probe uses its name', $map['probe_2']['label'], 'Battery');
hw_assert_eq('signal id is rom-keyed, not label-keyed', $map['probe_1']['signal_id'], 'ds18b20_aaa1111111111111');

$rawJson = json_encode($map);
hw_assert_eq('ROM never appears as a JSON key or bare value outside signal_id',
    strpos($rawJson, '"aaa1111111111111"') === false
    && strpos($rawJson, '"bbb2222222222222"') === false, true);

$uncommissioned = [
    'data' => [
        'connected' => true, 'stale' => false,
        'sensors' => ['ds18b20' => ['bus_ok' => true, 'probes' => [
            'zzz9999999999999' => ['ok' => true, 'value' => 30.0, 'name' => null, 'physical_index' => null],
        ], 'commissioned' => []]],
    ],
    'stale' => false,
];
hw_assert_eq('an uncommissioned probe never appears in the slug map',
    piratebox_history_probe_slug_map($uncommissioned), []);

// --- piratebox_history_catalog(): capability-driven, no fake charts ----

$nothingInstalled = piratebox_history_catalog(['data' => [], 'stale' => true]);
hw_assert_eq('no export -> no ambient light chart', $nothingInstalled['ambient_light'], null);
hw_assert_eq('no export -> no esp32 temp chart', $nothingInstalled['esp32_temp'], null);
hw_assert_eq('no export -> no probe charts', $nothingInstalled['probes'], []);

$healthyFull = [
    'data' => [
        'connected' => true, 'stale' => false,
        'capabilities' => ['temp_internal', 'bh1750', 'ds18b20'],
        'sensors' => [
            'temp_internal' => ['ok' => true, 'value' => 41.5],
            'bh1750' => ['ok' => true, 'value' => 42.0],
            'ds18b20' => ['bus_ok' => true, 'probes' => [
                'aaa1111111111111' => ['ok' => true, 'value' => 29.5],
            ], 'commissioned' => ['aaa1111111111111' => ['name' => null, 'physical_index' => 1]]],
        ],
    ],
    'stale' => false,
];
$catalog = piratebox_history_catalog($healthyFull);
hw_assert_eq('ambient light group present', $catalog['ambient_light']['signal_id'], 'ambient_lux');
hw_assert_eq('ambient light currently available', $catalog['ambient_light']['current_state'], 'AVAILABLE');
hw_assert_eq('esp32 temp group present', $catalog['esp32_temp']['signal_id'], 'esp32_temp_internal');
hw_assert_eq('one probe group present', count($catalog['probes']), 1);
hw_assert_eq('probe currently available', $catalog['probes']['probe_1']['current_state'], 'AVAILABLE');

$bh1750NeverInstalled = [
    'data' => [
        'connected' => true, 'stale' => false,
        'capabilities' => ['temp_internal'],
        'sensors' => ['temp_internal' => ['ok' => true, 'value' => 41.5]],
    ],
    'stale' => false,
];
hw_assert_eq('bh1750 never advertised -> no ambient light chart group at all (not a fake empty one)',
    piratebox_history_catalog($bh1750NeverInstalled)['ambient_light'], null);

$disconnected = [
    'data' => [
        'connected' => false, 'stale' => true,
        'capabilities' => ['ds18b20'],
        'sensors' => ['ds18b20' => ['bus_ok' => true, 'probes' => [], 'commissioned' => [
            'aaa1111111111111' => ['name' => null, 'physical_index' => 1],
        ]]],
    ],
    'stale' => false,
];
$catalogDisconnected = piratebox_history_catalog($disconnected);
hw_assert_eq('disconnected link -> probe still LISTED (historical data may still be worth showing)',
    array_key_exists('probe_1', $catalogDisconnected['probes']), true);
hw_assert_eq('disconnected link -> probe current_state reflects the LINK problem, not a fake DEGRADED',
    $catalogDisconnected['probes']['probe_1']['current_state'], 'UNAVAILABLE');

// --- piratebox_history_read_signal() / piratebox_history_query() -------
// Both take an injectable $historyDir - never touches the real
// /var/lib/piratebox-history. Same "inject the one impure input"
// pattern this project already uses for $export params elsewhere.

$tmpDir = sys_get_temp_dir() . '/piratebox_history_test_' . getmypid();
mkdir($tmpDir);

$testSignal = 'test_signal';
$testFile = $tmpDir . '/' . $testSignal . '.json';
$now = 1000000;
$fixture = [
    'schema_version' => 1,
    'raw' => [
        ['t' => $now - 100, 'v' => 21.0],
        ['t' => $now - 50, 'v' => 22.0],
        ['t' => $now - 10, 'v' => 23.0],
    ],
    'hourly' => [['t' => $now - 7200, 'min' => 20.0, 'avg' => 21.0, 'max' => 22.0, 'n' => 12]],
    'daily' => [],
];
file_put_contents($testFile, json_encode($fixture));

$read = piratebox_history_read_signal($testSignal, $tmpDir);
hw_assert_eq('read_signal returns the raw tier', count($read['raw']), 3);

$queried = piratebox_history_query($testSignal, 200, $now, $tmpDir);
hw_assert_eq('query filters to the requested window', count($queried['points']), 3);
hw_assert_eq('query uses the raw tier for a short range', $queried['tier'], 'raw');
hw_assert_eq('query points are in chronological order',
    array_column($queried['points'], 't'), [$now - 100, $now - 50, $now - 10]);
hw_assert_eq('raw-tier points carry a plain v', $queried['points'][0]['v'], 21.0);

$narrowQuery = piratebox_history_query($testSignal, 60, $now, $tmpDir);
hw_assert_eq('a narrower window excludes older points', count($narrowQuery['points']), 2);

$missingSignal = piratebox_history_query('does_not_exist', 200, $now, $tmpDir);
hw_assert_eq('a signal with no file yet returns an empty result, not an error', $missingSignal['points'], []);

$traversal = piratebox_history_query('../../../etc/passwd', 200, $now, $tmpDir);
hw_assert_eq('path traversal in signal id returns empty, never reads outside the history dir',
    $traversal['points'], []);

// A 30-day query correctly picks the hourly tier (not raw, even though
// raw data exists in the fixture) and returns exactly the one hourly
// entry the fixture actually has within that window - never the raw
// points, never a fabricated point.
$longRangeQuery = piratebox_history_query($testSignal, 30 * 86400, $now, $tmpDir);
hw_assert_eq('a 30-day query selects the hourly tier', $longRangeQuery['tier'], 'hourly');
hw_assert_eq('a 30-day query returns exactly the hourly entries in range', count($longRangeQuery['points']), 1);

// Confirms hourly-tier point shape (min/max ride alongside v=avg):
$fixtureForHourly = ['raw' => [], 'hourly' => [['t' => $now - 3600, 'min' => 18.0, 'avg' => 19.5, 'max' => 21.0, 'n' => 12]], 'daily' => []];
file_put_contents($testFile, json_encode($fixtureForHourly));
$hourlyResult = piratebox_history_query($testSignal, 40 * 86400, $now, $tmpDir);
hw_assert_eq('hourly-tier points carry min/max alongside v', $hourlyResult['points'][0]['min'], 18.0);
hw_assert_eq('hourly-tier v is the average', $hourlyResult['points'][0]['v'], 19.5);

unlink($testFile);
rmdir($tmpDir);

echo "\n";
if ($failures) {
    echo "FAILURES:\n";
    foreach ($failures as $f) echo "  - $f\n";
    echo "\nHistory web tests: $passCount passed, " . count($failures) . " failed.\n";
    exit(1);
}
echo "History web tests: $passCount passed, 0 failed.\n";
