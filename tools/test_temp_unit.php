<?php

declare(strict_types=1);

// Deterministic tests for includes/temp_unit.php - matches the
// project's existing dependency-free tools/test_*.php convention.
// Run with: php tools/test_temp_unit.php

require_once __DIR__ . '/../var/www/html/includes/temp_unit.php';

$failures = [];
$passCount = 0;

function tu_assert_eq(string $label, $actual, $expected): void
{
    global $failures, $passCount;
    if ($actual !== $expected) {
        $failures[] = "$label: expected " . var_export($expected, true) . ", got " . var_export($actual, true);
        return;
    }
    $passCount++;
}

// --- piratebox_convert_temp_c() -----------------------------------------

tu_assert_eq('freezing point C->F', piratebox_convert_temp_c(0.0, 'F'), 32.0);
tu_assert_eq('boiling point C->F', piratebox_convert_temp_c(100.0, 'F'), 212.0);
tu_assert_eq('crossover point (-40 is the same in both scales)', piratebox_convert_temp_c(-40.0, 'F'), -40.0);
tu_assert_eq('Celsius passthrough is exactly unchanged', piratebox_convert_temp_c(29.5, 'C'), 29.5);
tu_assert_eq('null passes through for F', piratebox_convert_temp_c(null, 'F'), null);
tu_assert_eq('null passes through for C', piratebox_convert_temp_c(null, 'C'), null);
tu_assert_eq('unrecognized unit behaves like Celsius passthrough', piratebox_convert_temp_c(29.5, 'K'), 29.5);

// No-double-conversion canary: applying the conversion twice must
// never coincidentally look like a single correct conversion - this
// project's own architecture never does this (every caller converts a
// freshly-read Celsius value exactly once), but documents the
// arithmetic reality as a guard against ever introducing it.
$once = piratebox_convert_temp_c(20.0, 'F');
$twice = piratebox_convert_temp_c($once, 'F');
tu_assert_eq('single conversion is correct', $once, 68.0);
tu_assert_eq('double conversion is NOT the same as single (canary)', $twice === $once, false);

// --- piratebox_temp_unit_symbol() ---------------------------------------

tu_assert_eq('Celsius symbol', piratebox_temp_unit_symbol('C'), '&deg;C');
tu_assert_eq('Fahrenheit symbol', piratebox_temp_unit_symbol('F'), '&deg;F');
tu_assert_eq('unrecognized unit falls back to Celsius symbol', piratebox_temp_unit_symbol('K'), '&deg;C');

// --- piratebox_get_temp_unit() / piratebox_set_temp_unit() - injectable path

$tmpDir = sys_get_temp_dir() . '/piratebox_temp_unit_test_' . getmypid();
mkdir($tmpDir);
$tmpFile = $tmpDir . '/temp-unit.json';

tu_assert_eq('missing file defaults to Celsius', piratebox_get_temp_unit($tmpFile), 'C');

tu_assert_eq('set to Fahrenheit succeeds', piratebox_set_temp_unit('F', $tmpFile), true);
tu_assert_eq('reads back Fahrenheit after setting it', piratebox_get_temp_unit($tmpFile), 'F');

tu_assert_eq('set back to Celsius succeeds', piratebox_set_temp_unit('C', $tmpFile), true);
tu_assert_eq('reads back Celsius after setting it', piratebox_get_temp_unit($tmpFile), 'C');

tu_assert_eq('an invalid unit is rejected, not silently coerced', piratebox_set_temp_unit('kelvin', $tmpFile), false);
tu_assert_eq('the file is unchanged after a rejected set', piratebox_get_temp_unit($tmpFile), 'C');

file_put_contents($tmpFile, '{not valid json');
tu_assert_eq('corrupt file defaults to Celsius', piratebox_get_temp_unit($tmpFile), 'C');

file_put_contents($tmpFile, json_encode(['unit' => 'kelvin']));
tu_assert_eq('unrecognized stored value defaults to Celsius', piratebox_get_temp_unit($tmpFile), 'C');

file_put_contents($tmpFile, json_encode(['not_unit' => 'F']));
tu_assert_eq('wrong JSON key defaults to Celsius', piratebox_get_temp_unit($tmpFile), 'C');

// Confirm no leftover .tmp.* files from the atomic-write pattern:
$leftoverTmpFiles = glob($tmpDir . '/temp-unit.json.tmp.*');
tu_assert_eq('no leftover temp files after a successful atomic write', $leftoverTmpFiles, []);

unlink($tmpFile);
rmdir($tmpDir);

// --- piratebox_temp_unit_post_is_authorized() - the Environment page's
// narrow same-session CSRF guard (2026-09-08). Matching tokens only -
// never a general auth check, never bypassed by a missing/empty value
// on either side. ---------------------------------------------------

tu_assert_eq('matching tokens authorize', piratebox_temp_unit_post_is_authorized('abc123', 'abc123'), true);
tu_assert_eq('mismatched tokens are rejected', piratebox_temp_unit_post_is_authorized('abc123', 'xyz789'), false);
tu_assert_eq('missing session token (null) is rejected, not treated as a wildcard', piratebox_temp_unit_post_is_authorized(null, 'abc123'), false);
tu_assert_eq('missing submitted token (null) is rejected', piratebox_temp_unit_post_is_authorized('abc123', null), false);
tu_assert_eq('both missing is rejected, not vacuously true', piratebox_temp_unit_post_is_authorized(null, null), false);
tu_assert_eq('empty-string session token is rejected (a session that never minted one fails closed)', piratebox_temp_unit_post_is_authorized('', 'abc123'), false);
tu_assert_eq('empty-string submitted token is rejected', piratebox_temp_unit_post_is_authorized('abc123', ''), false);
tu_assert_eq('both empty strings is rejected, not treated as a trivial match', piratebox_temp_unit_post_is_authorized('', ''), false);

echo "\n";
if ($failures) {
    echo "FAILURES:\n";
    foreach ($failures as $f) echo "  - $f\n";
    echo "\nTemp unit tests: $passCount passed, " . count($failures) . " failed.\n";
    exit(1);
}
echo "Temp unit tests: $passCount passed, 0 failed.\n";
