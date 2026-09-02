<?php

declare(strict_types=1);

// Deterministic tests for includes/hardware_wiring.php - matches the
// project's existing dependency-free tools/test_*.php convention.
// Run with: php tools/test_hardware_wiring.php

require_once __DIR__ . '/../var/www/html/includes/hardware_wiring.php';

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

// --- piratebox_parse_gpio_wiring(): boundary/malformed cases ---

hw_assert_eq('null input -> null, not empty array', piratebox_parse_gpio_wiring(null), null);
hw_assert_eq('non-array input -> null', piratebox_parse_gpio_wiring('not an array'), null);
hw_assert_eq('empty array -> empty array (valid, just no rows)', piratebox_parse_gpio_wiring([]), []);

$rows = piratebox_parse_gpio_wiring([
    ['function' => 'Test button', 'bcm' => 'GPIO99', 'physical_pin' => '1', 'status' => 'Not wired', 'notes' => 'test note'],
]);
hw_assert_eq('Valid row: count', count($rows), 1);
hw_assert_eq('Valid row: function', $rows[0]['function'], 'Test button');
hw_assert_eq('Valid row: notes', $rows[0]['notes'], 'test note');

$rows = piratebox_parse_gpio_wiring([
    ['function' => 'Missing status field', 'bcm' => 'GPIO1', 'physical_pin' => '1'],
]);
hw_assert_eq('Row missing a required field is silently skipped, not fabricated', $rows, []);

$rows = piratebox_parse_gpio_wiring([
    'not a row at all - a plain string',
    ['function' => 'Valid row after a garbage entry', 'bcm' => 'GPIO2', 'physical_pin' => '2', 'status' => 'Not wired'],
]);
hw_assert_eq('Non-array row entries are skipped, valid ones after them still parsed', count($rows), 1);
hw_assert_eq('notes defaults to empty string when absent, never null/missing', $rows[0]['notes'], '');

// --- piratebox_get_gpio_wiring(): against the REAL repo data ---

$wiring = piratebox_get_gpio_wiring();
hw_assert_eq('Real data file parses, not null', $wiring !== null, true);
hw_assert_eq('Real data file has at least one row', count($wiring ?? []) > 0, true);

$byFunction = [];
foreach ($wiring ?? [] as $r) { $byFunction[$r['function']] = $r; }
hw_assert_eq('Shutdown button row exists', array_key_exists('Shutdown button', $byFunction), true);
hw_assert_eq('Shutdown button is the one row marked wired (matches capability_state.php\'s real shutdown_button=AVAILABLE)', str_contains($byFunction['Shutdown button']['status'] ?? '', 'Wired'), true);
hw_assert_eq('Shutdown button BCM matches the documented pin (docs/HARDWARE-INTEGRATION-DESIGN.md §2)', $byFunction['Shutdown button']['bcm'] ?? null, 'GPIO25');

foreach ($wiring ?? [] as $r) {
    if ($r['function'] === 'Shutdown button') continue;
    hw_assert_eq("Every other row ({$r['function']}) is honestly 'Not wired', matching live gpioinfo (no consumer on those pins)", $r['status'], 'Not wired');
}

echo "\n";
if ($failures) {
    echo "FAILURES:\n";
    foreach ($failures as $f) echo "  - $f\n";
    echo "\nHardware wiring tests: $passCount passed, " . count($failures) . " failed.\n";
    exit(1);
}
echo "Hardware wiring tests: $passCount passed, 0 failed.\n";
