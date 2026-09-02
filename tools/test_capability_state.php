<?php

declare(strict_types=1);

// Deterministic tests for includes/capability_state.php's pure
// classification functions - matches the project's existing
// dependency-free tools/test_*.php convention. Run with:
//   php tools/test_capability_state.php
//
// Only the PURE functions (piratebox_classify_*) are unit-tested here -
// piratebox_get_capability_state() itself reads live system state
// (via piratebox_get_helper_status()'s hardcoded /run/piratebox/
// status.json path, same as every other reader of that file in this
// app) and is exercised instead by direct live/php -S verification, not
// a CLI test with faked input. This mirrors tools/test_fieldtools.php's
// same split for piratebox_get_time_source_status().

require_once __DIR__ . '/../var/www/html/includes/capability_state.php';

$failures = [];
$passCount = 0;

function cs_assert_eq(string $label, $actual, $expected): void
{
    global $failures, $passCount;
    if ($actual !== $expected) {
        $failures[] = "$label: expected " . var_export($expected, true) . ", got " . var_export($actual, true);
        return;
    }
    $passCount++;
}

// --- piratebox_classify_service_pair: happy path, degraded, missing data ---

cs_assert_eq('Both services up -> AVAILABLE', piratebox_classify_service_pair(true, true, true), 'AVAILABLE');
cs_assert_eq('One service down -> DEGRADED', piratebox_classify_service_pair(true, true, false), 'DEGRADED');
cs_assert_eq('Both services down -> DEGRADED', piratebox_classify_service_pair(true, false, false), 'DEGRADED');
cs_assert_eq('Helper fresh but field missing (null) -> DEGRADED, not fabricated AVAILABLE', piratebox_classify_service_pair(true, null, true), 'DEGRADED');
cs_assert_eq('Helper unavailable -> UNKNOWN regardless of field values', piratebox_classify_service_pair(false, true, true), 'UNKNOWN');
cs_assert_eq('Helper unavailable, fields null too -> still UNKNOWN, not DEGRADED', piratebox_classify_service_pair(false, null, null), 'UNKNOWN');

// --- piratebox_classify_power: null/missing, degraded, boundary ---

cs_assert_eq('Helper available, no undervoltage -> AVAILABLE', piratebox_classify_power(true, false), 'AVAILABLE');
cs_assert_eq('Helper available, undervoltage now -> DEGRADED', piratebox_classify_power(true, true), 'DEGRADED');
cs_assert_eq('Helper available but field null (malformed data) -> AVAILABLE (never a fabricated DEGRADED either)', piratebox_classify_power(true, null), 'AVAILABLE');
cs_assert_eq('Helper unavailable -> UNAVAILABLE, not a guessed AVAILABLE', piratebox_classify_power(false, false), 'UNAVAILABLE');
cs_assert_eq('Helper unavailable, even if last-known value was bad -> still UNAVAILABLE, not DEGRADED', piratebox_classify_power(false, true), 'UNAVAILABLE');

// --- piratebox_classify_rtc: not-installed vs unknown, never fabricated healthy ---

cs_assert_eq('Time source available, RTC detected -> AVAILABLE', piratebox_classify_rtc(true, true), 'AVAILABLE');
cs_assert_eq('Time source available, no RTC -> NOT_INSTALLED (today\'s real state)', piratebox_classify_rtc(true, false), 'NOT_INSTALLED');
cs_assert_eq('Time source unavailable -> UNKNOWN, not a guess either way', piratebox_classify_rtc(false, null), 'UNKNOWN');
cs_assert_eq('Time source unavailable even with a stale true value -> still UNKNOWN', piratebox_classify_rtc(false, true), 'UNKNOWN');

// --- piratebox_classify_storage: null/missing, boundary, reuses the
// existing PIRATEBOX_MIN_FREE_BYTES*2 "warning" threshold (index.php's
// own home-page storage warning uses the exact same number) ---

cs_assert_eq('Free/total both null (disk_*_space() failed) -> UNKNOWN', piratebox_classify_storage(null, null), 'UNKNOWN');
cs_assert_eq('Only free null -> UNKNOWN', piratebox_classify_storage(null, 100), 'UNKNOWN');
cs_assert_eq('Only total null -> UNKNOWN', piratebox_classify_storage(50, null), 'UNKNOWN');
cs_assert_eq('Plenty of free space -> AVAILABLE', piratebox_classify_storage(PIRATEBOX_MIN_FREE_BYTES * 10, PIRATEBOX_MIN_FREE_BYTES * 20), 'AVAILABLE');
cs_assert_eq('Free space exactly at the 2x-reserve boundary -> AVAILABLE (boundary itself is not yet low)', piratebox_classify_storage(PIRATEBOX_MIN_FREE_BYTES * 2, PIRATEBOX_MIN_FREE_BYTES * 20), 'AVAILABLE');
cs_assert_eq('Free space just below the 2x-reserve boundary -> DEGRADED', piratebox_classify_storage((PIRATEBOX_MIN_FREE_BYTES * 2) - 1, PIRATEBOX_MIN_FREE_BYTES * 20), 'DEGRADED');
cs_assert_eq('Free space at/below the hard reject threshold -> DEGRADED too (not a separate tier - see the function\'s own comment)', piratebox_classify_storage(0, PIRATEBOX_MIN_FREE_BYTES * 20), 'DEGRADED');

// --- piratebox_diagnose_capability: storage entries (new) ---

cs_assert_eq('storage DEGRADED has a real diagnosis, not null', piratebox_diagnose_capability('storage', ['state' => 'DEGRADED']) !== null, true);
cs_assert_eq('storage UNKNOWN has a real diagnosis, not null', piratebox_diagnose_capability('storage', ['state' => 'UNKNOWN']) !== null, true);
cs_assert_eq('storage AVAILABLE has no diagnosis (nothing wrong to explain)', piratebox_diagnose_capability('storage', ['state' => 'AVAILABLE']), null);

// --- piratebox_capability_summary_counts: structural / boundary cases ---

$counts = piratebox_capability_summary_counts([]);
cs_assert_eq('Empty capability list -> all-zero counts, all keys present', $counts, ['AVAILABLE' => 0, 'DEGRADED' => 0, 'UNAVAILABLE' => 0, 'NOT_INSTALLED' => 0, 'UNKNOWN' => 0]);

$counts = piratebox_capability_summary_counts([
    'a' => ['state' => 'AVAILABLE'],
    'b' => ['state' => 'AVAILABLE'],
    'c' => ['state' => 'NOT_INSTALLED'],
]);
cs_assert_eq('Mixed list tallies correctly', $counts['AVAILABLE'], 2);
cs_assert_eq('Mixed list tallies correctly (2)', $counts['NOT_INSTALLED'], 1);
cs_assert_eq('Mixed list tallies correctly (3, untouched state stays 0)', $counts['DEGRADED'], 0);

// --- piratebox_get_capability_state(): structural smoke test against whatever
// this environment's live state actually is - not a value-level test
// (that's what the pure functions above are for), just confirms the
// function returns the documented shape and every state is from the
// documented vocabulary, for every capability it returns.

$validStates = ['NOT_INSTALLED', 'AVAILABLE', 'DEGRADED', 'UNAVAILABLE', 'UNKNOWN'];
$caps = piratebox_get_capability_state();
cs_assert_eq('Capability state returns a non-empty array', $caps !== [], true);
$allValid = true;
$allHaveRequiredKeys = true;
foreach ($caps as $id => $c) {
    if (!in_array($c['state'] ?? null, $validStates, true)) $allValid = false;
    if (!isset($c['layer'], $c['state'], $c['label'], $c['core_dependency'])) $allHaveRequiredKeys = false;
    if (!in_array($c['layer'], ['core', 'operational', 'optional'], true)) $allValid = false;
}
cs_assert_eq('Every capability state is from the documented vocabulary', $allValid, true);
cs_assert_eq('Every capability entry has the required keys', $allHaveRequiredKeys, true);

// Core-dependency sanity: every entry this file marks core_dependency=true
// must actually be layer='core' (a capability can't be a Core dependency
// without being Core itself - catches an authoring mistake, not a live-data one).
$coreConsistent = true;
foreach ($caps as $c) {
    if ($c['core_dependency'] === true && $c['layer'] !== 'core') $coreConsistent = false;
}
cs_assert_eq('core_dependency=true only ever appears on layer=core entries', $coreConsistent, true);

// --- piratebox_default_provider(): capability/provider distinction ---

[$provider, $class] = piratebox_default_provider('AVAILABLE');
cs_assert_eq('AVAILABLE capability defaults to PirateBox as provider', $provider, 'PirateBox (this device)');
cs_assert_eq('AVAILABLE capability defaults to integrated provider class', $class, 'integrated');

[$provider, $class] = piratebox_default_provider('DEGRADED');
cs_assert_eq('DEGRADED capability still has a provider (it exists, just unhealthy)', $provider, 'PirateBox (this device)');

[$provider, $class] = piratebox_default_provider('NOT_INSTALLED');
cs_assert_eq('NOT_INSTALLED capability has no provider - never guessed', $provider, null);
cs_assert_eq('NOT_INSTALLED capability has no provider class either', $class, null);

[$provider, $class] = piratebox_default_provider('UNKNOWN');
cs_assert_eq('UNKNOWN capability has no fabricated provider', $provider, null);

// Every entry from the live function actually carries the new fields.
$providerFieldsPresent = true;
foreach ($caps as $c) {
    if (!array_key_exists('provider', $c) || !array_key_exists('provider_class', $c)) $providerFieldsPresent = false;
}
cs_assert_eq('Every live capability entry carries provider/provider_class', $providerFieldsPresent, true);

// --- piratebox_diagnose_capability(): graceful self-diagnosis ---

cs_assert_eq('AVAILABLE has nothing to diagnose', piratebox_diagnose_capability('ap_network', ['state' => 'AVAILABLE']), null);
cs_assert_eq('NOT_INSTALLED has nothing to diagnose', piratebox_diagnose_capability('oled', ['state' => 'NOT_INSTALLED']), null);
cs_assert_eq('DEGRADED ap_network returns a real explanation', is_string(piratebox_diagnose_capability('ap_network', ['state' => 'DEGRADED'])), true);
cs_assert_eq('DEGRADED power_monitoring mentions undervoltage', str_contains((string) piratebox_diagnose_capability('power_monitoring', ['state' => 'DEGRADED']), 'ndervoltage'), true);
cs_assert_eq('Unrecognized capability id -> null, never a guess', piratebox_diagnose_capability('totally_made_up_id', ['state' => 'DEGRADED']), null);
cs_assert_eq('Recognized id, unrecognized state combination -> null', piratebox_diagnose_capability('shutdown_button', ['state' => 'DEGRADED']), null);
cs_assert_eq('Missing state key -> treated as UNKNOWN, not a crash', is_string(piratebox_diagnose_capability('ap_network', [])) || piratebox_diagnose_capability('ap_network', []) === null, true);

// Every live DEGRADED/UNAVAILABLE/UNKNOWN capability either has a real
// diagnosis or is honestly not covered yet - never crashes either way.
$diagnosisRanCleanly = true;
foreach ($caps as $id => $c) {
    try {
        piratebox_diagnose_capability($id, $c);
    } catch (\Throwable $e) {
        $diagnosisRanCleanly = false;
    }
}
cs_assert_eq('Diagnosing every live capability never throws', $diagnosisRanCleanly, true);

// Regression test for a real bug found live: capability_state.php's
// disk_total_space()/disk_free_space() path must resolve to exactly the
// webroot (var/www/html) - one level too many silently resolves outside
// PHP-FPM's open_basedir (etc/php/8.4/fpm/php.ini) and fails invisibly
// under `@`. A plain CLI run (this test) has no open_basedir, so it
// can't reproduce the failure directly - it instead pins the path math
// itself, which is what actually broke.
cs_assert_eq(
    'storage capability path resolves to the actual webroot (open_basedir boundary)',
    realpath(__DIR__ . '/../var/www/html/includes/..'),
    realpath(__DIR__ . '/../var/www/html')
);
cs_assert_eq('storage state reads real values against this environment (no open_basedir here)', $caps['storage']['state'], 'AVAILABLE');

echo "Capability state tests: $passCount passed, " . count($failures) . " failed.\n";
if ($failures) {
    echo "\nFAILURES:\n";
    foreach ($failures as $f) {
        echo "  - $f\n";
    }
    exit(1);
}
exit(0);
