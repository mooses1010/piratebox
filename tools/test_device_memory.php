<?php

declare(strict_types=1);

// Deterministic tests for includes/device_memory.php's pure parser -
// matches the project's existing dependency-free tools/test_*.php
// convention. Run with: php tools/test_device_memory.php

require_once __DIR__ . '/../var/www/html/includes/device_memory.php';

$failures = [];
$passCount = 0;

function dm_assert_eq(string $label, $actual, $expected): void
{
    global $failures, $passCount;
    if ($actual !== $expected) {
        $failures[] = "$label: expected " . var_export($expected, true) . ", got " . var_export($actual, true);
        return;
    }
    $passCount++;
}

// --- Missing / malformed / empty cases ---

$r = piratebox_parse_device_memory(null); // file missing/unreadable
dm_assert_eq('null decoded -> unavailable', $r['available'], false);
dm_assert_eq('unavailable -> boot_count null, not zero', $r['boot_count'], null);
dm_assert_eq('unavailable -> undervoltage total null, not zero', $r['undervoltage_events_total'], null);

$r = piratebox_parse_device_memory('not an array'); // json_decode of a bare string
dm_assert_eq('scalar decoded -> unavailable', $r['available'], false);

$r = piratebox_parse_device_memory([1, 2, 3]); // a JSON array, not object - wrong shape
dm_assert_eq('list (not assoc array) decoded -> still parsed, defaults applied', $r['available'], true);
dm_assert_eq('wrong shape -> boot_count 0, not null (array itself was valid, fields just absent)', $r['boot_count'], 0);

// --- Fresh/empty history (status helper updated, no events yet) ---

$r = piratebox_parse_device_memory(['boot_events' => [], 'undervoltage_daily' => [], 'history_started_at' => 1000, 'updated_at' => 1000]);
dm_assert_eq('empty history -> available true', $r['available'], true);
dm_assert_eq('empty history -> boot_count 0 (a real observed zero, not unavailable)', $r['boot_count'], 0);
dm_assert_eq('empty history -> last_boot_at null (no boots recorded yet)', $r['last_boot_at'], null);
dm_assert_eq('empty history -> undervoltage total 0', $r['undervoltage_events_total'], 0);

// --- Populated history: boot count, last boot, undervoltage totals ---

$r = piratebox_parse_device_memory([
    'boot_events' => [1000, 2000, 3000],
    'undervoltage_daily' => [
        ['day_start' => 86400, 'count' => 3],
        ['day_start' => 172800, 'count' => 5],
    ],
    'history_started_at' => 500,
    'updated_at' => 3000,
]);
dm_assert_eq('3 boots -> boot_count 3', $r['boot_count'], 3);
dm_assert_eq('last_boot_at is the max timestamp', $r['last_boot_at'], 3000);
dm_assert_eq('undervoltage total sums all daily buckets', $r['undervoltage_events_total'], 8);
dm_assert_eq('history_started_at passed through', $r['history_started_at'], 500);
dm_assert_eq('updated_at passed through', $r['updated_at'], 3000);

// --- Partial/dirty data: one field missing, one malformed bucket ---

$r = piratebox_parse_device_memory(['undervoltage_daily' => [['day_start' => 1, 'count' => 2], 'not-a-bucket', ['count' => 'not-an-int']]]);
dm_assert_eq('boot_events entirely absent -> boot_count 0, not a crash', $r['boot_count'], 0);
dm_assert_eq('malformed buckets skipped, valid one still counted', $r['undervoltage_events_total'], 2);

// --- piratebox_device_memory_since(): boundary cases ---

$unavailable = piratebox_parse_device_memory(null);
$sinceResult = piratebox_device_memory_since($unavailable, 1000);
dm_assert_eq('since(): device memory unavailable -> both fields null, never zero', $sinceResult, ['boots_since' => null, 'undervoltage_events_since' => null]);

$populated = piratebox_parse_device_memory([
    'boot_events' => [1000, 5000, 9000],
    'undervoltage_daily' => [
        ['day_start' => 0, 'count' => 2],
        ['day_start' => 5000, 'count' => 3],
        ['day_start' => 9000, 'count' => 1],
    ],
    'history_started_at' => 0, 'updated_at' => 9000,
]);

$sinceResult = piratebox_device_memory_since($populated, null);
dm_assert_eq('since(): no boundary set -> everything on record counts', $sinceResult, ['boots_since' => 3, 'undervoltage_events_since' => 6]);

$sinceResult = piratebox_device_memory_since($populated, 5000);
dm_assert_eq('since(): boundary excludes earlier boots', $sinceResult['boots_since'], 2);
dm_assert_eq('since(): boundary excludes earlier undervoltage buckets', $sinceResult['undervoltage_events_since'], 4);

$sinceResult = piratebox_device_memory_since($populated, 9000);
dm_assert_eq('since(): boundary exactly matching an event includes it (>=, not >)', $sinceResult['boots_since'], 1);

$sinceResult = piratebox_device_memory_since($populated, 999999);
dm_assert_eq('since(): boundary in the future -> zero, not null (a real observed zero)', $sinceResult, ['boots_since' => 0, 'undervoltage_events_since' => 0]);

$empty = piratebox_parse_device_memory(['boot_events' => [], 'undervoltage_daily' => []]);
$sinceResult = piratebox_device_memory_since($empty, null);
dm_assert_eq('since(): empty history, no boundary -> zero, not null', $sinceResult, ['boots_since' => 0, 'undervoltage_events_since' => 0]);

// --- Review boundary read (structural only) ---
//
// piratebox_get_review_boundary()/piratebox_mark_reviewed() read/write
// the real repo path (data/review-boundary.json) - deliberately NOT
// exercised end-to-end by this CLI test (no live/community-adjacent
// data touched by tests, per project convention - the file doesn't
// exist in this repo checkout and this test doesn't create it).
dm_assert_eq('piratebox_get_review_boundary() returns int or null, never a fabricated value', is_int(piratebox_get_review_boundary()) || piratebox_get_review_boundary() === null, true);

// --- Live smoke test: whatever this environment's real state is ---

$live = piratebox_get_device_memory();
dm_assert_eq('Live function returns available as boolean', is_bool($live['available']), true);
if ($live['available']) {
    dm_assert_eq('Live boot_count is an int when available', is_int($live['boot_count']), true);
} else {
    dm_assert_eq('Live boot_count is null when unavailable (not fabricated)', $live['boot_count'], null);
}

echo "Device memory tests: $passCount passed, " . count($failures) . " failed.\n";
if ($failures) {
    echo "\nFAILURES:\n";
    foreach ($failures as $f) {
        echo "  - $f\n";
    }
    exit(1);
}
exit(0);
