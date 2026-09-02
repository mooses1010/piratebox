<?php

declare(strict_types=1);

// Deterministic tests for Field Tools' conversion/time functions
// (includes/fieldtools_convert.php, includes/fieldtools_time.php).
//
// Plain PHP CLI, no framework/dependency - matches this project's
// existing dependency-free tools/ convention (check_library_catalog.py,
// apply_travel_mode_quarantine.php). Run with: php tools/test_fieldtools.php
//
// Exits 0 and prints a summary on success; exits 1 and lists every
// failure otherwise - safe to wire into a pre-deploy check later if
// this project ever adds one.

require_once __DIR__ . '/../var/www/html/includes/fieldtools_convert.php';
require_once __DIR__ . '/../var/www/html/includes/fieldtools_time.php';

$failures = [];
$passCount = 0;

function ft_assert_close(string $label, float $actual, float $expected, float $tolerance = 0.0001): void
{
    global $failures, $passCount;
    if (abs($actual - $expected) > $tolerance) {
        $failures[] = "$label: expected $expected, got $actual";
        return;
    }
    $passCount++;
}

function ft_assert_null(string $label, $actual): void
{
    global $failures, $passCount;
    if ($actual !== null) {
        $failures[] = "$label: expected null, got " . var_export($actual, true);
        return;
    }
    $passCount++;
}

function ft_assert_eq(string $label, $actual, $expected): void
{
    global $failures, $passCount;
    if ($actual !== $expected) {
        $failures[] = "$label: expected " . var_export($expected, true) . ", got " . var_export($actual, true);
        return;
    }
    $passCount++;
}

function ft_assert_true(string $label, bool $actual): void
{
    global $failures, $passCount;
    if (!$actual) {
        $failures[] = "$label: expected true";
        return;
    }
    $passCount++;
}

// --- Temperature: boundary/sign cases -------------------------------------

ft_assert_close('0C -> F', piratebox_convert_temperature(0, 'c', 'f'), 32.0);
ft_assert_close('100C -> F', piratebox_convert_temperature(100, 'c', 'f'), 212.0);
ft_assert_close('32F -> C', piratebox_convert_temperature(32, 'f', 'c'), 0.0);
ft_assert_close('-40C -> F (fixed point)', piratebox_convert_temperature(-40, 'c', 'f'), -40.0);
ft_assert_close('-40F -> C (fixed point)', piratebox_convert_temperature(-40, 'f', 'c'), -40.0);
ft_assert_close('-273.15C -> F (absolute zero)', piratebox_convert_temperature(-273.15, 'c', 'f'), -459.67);
ft_assert_close('C -> C round trip (decimal)', piratebox_convert_temperature(piratebox_convert_temperature(37.5, 'c', 'f'), 'f', 'c'), 37.5);
ft_assert_close('Case-insensitive units', piratebox_convert_temperature(0, 'C', 'F'), 32.0);

// --- Distance: round trips + a decimal case --------------------------------

ft_assert_close('1 mi -> km', piratebox_convert_distance(1, 'mi', 'km'), 1.609344);
ft_assert_close('1 in -> cm', piratebox_convert_distance(1, 'in', 'cm'), 2.54);
ft_assert_close('0 mm -> mi', piratebox_convert_distance(0, 'mm', 'mi'), 0.0);
ft_assert_close('5280 ft -> mi (exact)', piratebox_convert_distance(5280, 'ft', 'mi'), 1.0);
ft_assert_close('Round trip m->ft->m', piratebox_convert_distance(piratebox_convert_distance(123.456, 'm', 'ft'), 'ft', 'm'), 123.456, 0.001);

// --- Mass -------------------------------------------------------------

ft_assert_close('1 kg -> lb', piratebox_convert_mass(1, 'kg', 'lb'), 2.2046226, 0.0001);
ft_assert_close('16 oz -> lb (exact)', piratebox_convert_mass(16, 'oz', 'lb'), 1.0);
ft_assert_close('0 g -> kg', piratebox_convert_mass(0, 'g', 'kg'), 0.0);

// --- Volume -------------------------------------------------------------

ft_assert_close('1 us_gal -> us_qt (exact)', piratebox_convert_volume(1, 'us_gal', 'us_qt'), 4.0);
ft_assert_close('1 L -> mL', piratebox_convert_volume(1, 'l', 'ml'), 1000.0);
ft_assert_close('Round trip us_cup->ml->us_cup', piratebox_convert_volume(piratebox_convert_volume(2.5, 'us_cup', 'ml'), 'ml', 'us_cup'), 2.5, 0.0001);

// --- Speed -------------------------------------------------------------

ft_assert_close('60 mph -> km/h', piratebox_convert_speed(60, 'mph', 'kmh'), 96.56064, 0.001);
ft_assert_close('0 m/s -> mph', piratebox_convert_speed(0, 'ms', 'mph'), 0.0);

// --- Pressure -------------------------------------------------------------

ft_assert_close('1 bar -> kPa (exact)', piratebox_convert_pressure(1, 'bar', 'kpa'), 100.0);
ft_assert_close('14.6959 psi ~ 1 bar', piratebox_convert_pressure(14.6959, 'psi', 'bar'), 1.0129, 0.001);

// --- Storage (binary/1024-based) -------------------------------------------

ft_assert_close('1 MiB -> KiB (exact)', piratebox_convert_storage(1, 'mib', 'kib'), 1024.0);
ft_assert_close('1024 B -> KiB (exact)', piratebox_convert_storage(1024, 'b', 'kib'), 1.0);
ft_assert_close('1 GiB -> B', piratebox_convert_storage(1, 'gib', 'b'), 1073741824.0);

// --- Percentage / ratio: zero and negative cases ---------------------------

ft_assert_close('25 is what % of 200', piratebox_percentage_of(25, 200), 12.5);
ft_assert_null('% of zero whole is undefined', piratebox_percentage_of(5, 0));
ft_assert_close('% change 50 -> 75', piratebox_percentage_change(50, 75), 50.0);
ft_assert_close('% change 100 -> 50 (negative)', piratebox_percentage_change(100, 50), -50.0);
ft_assert_null('% change from zero is undefined', piratebox_percentage_change(0, 10));
ft_assert_close('Apply +10% to 200', piratebox_apply_percentage(200, 10), 220.0);
ft_assert_close('Apply -10% to 200', piratebox_apply_percentage(200, -10), 180.0);

// --- Electrical / battery ---------------------------------------------------

ft_assert_close('12V x 2A = 24W', piratebox_electrical_watts(12, 2), 24.0);
ft_assert_null('Amps undefined at 0V', piratebox_electrical_amps(24, 0));
ft_assert_close('24W / 12V = 2A', piratebox_electrical_amps(24, 12), 2.0);
ft_assert_close('10Ah @ 12V = 120Wh', piratebox_electrical_ah_to_wh(10, 12), 120.0);
ft_assert_null('Runtime undefined at 0W load', piratebox_battery_runtime_hours(100, 0));
ft_assert_null('Runtime undefined at 0 efficiency', piratebox_battery_runtime_hours(100, 10, 0));
ft_assert_close('100Wh @ 10W, 100% efficiency = 10h', piratebox_battery_runtime_hours(100, 10, 1.0), 10.0);
ft_assert_close('100Wh @ 10W, 80% efficiency = 8h', piratebox_battery_runtime_hours(100, 10, 0.8), 8.0);

// --- Coordinates: boundary + sign cases -------------------------------------

// A known reference point: 40.6892, -74.0445 (Statue of Liberty area)
[$deg, $min, $sec, $hemi] = piratebox_dd_to_dms(40.6892, true);
ft_assert_eq('40.6892N -> hemisphere', $hemi, 'N');
ft_assert_eq('40.6892N -> degrees', $deg, 40);
ft_assert_eq('40.6892N -> minutes', $min, 41);

[$deg, $min, $sec, $hemi] = piratebox_dd_to_dms(-74.0445, false);
ft_assert_eq('-74.0445 -> hemisphere W', $hemi, 'W');
ft_assert_eq('-74.0445 -> degrees are non-negative', $deg, 74);

// Exact zero: not negative, defaults to N/E
[$deg, $min, $sec, $hemi] = piratebox_dd_to_dms(0.0, true);
ft_assert_eq('0.0 latitude -> N (not S)', $hemi, 'N');
ft_assert_eq('0.0 latitude -> 0 deg 0 min', $deg, 0);

// Round trip DD -> DMS -> DD
$originalLat = 51.5074; // London
[$deg, $min, $sec, $hemi] = piratebox_dd_to_dms($originalLat, true);
$roundTrip = piratebox_dms_to_dd((float) $deg, (float) $min, $sec, $hemi);
ft_assert_close('DD->DMS->DD round trip (lat)', $roundTrip, $originalLat, 0.0001);

$originalLon = -0.1278; // London
[$deg, $min, $sec, $hemi] = piratebox_dd_to_dms($originalLon, false);
$roundTrip = piratebox_dms_to_dd((float) $deg, (float) $min, $sec, $hemi);
ft_assert_close('DD->DMS->DD round trip (lon, negative)', $roundTrip, $originalLon, 0.0001);

// Invalid DMS input rejected
ft_assert_null('DMS with minutes=60 is invalid', piratebox_dms_to_dd(10, 60, 0, 'N'));
ft_assert_null('DMS with unknown hemisphere is invalid', piratebox_dms_to_dd(10, 0, 0, 'Q'));

// Coordinate range validation
ft_assert_true('Valid coordinate', piratebox_coordinate_is_valid(45.0, -120.0));
ft_assert_true('Boundary coordinate (90, 180) is valid', piratebox_coordinate_is_valid(90.0, 180.0));
ft_assert_eq('Out-of-range latitude rejected', piratebox_coordinate_is_valid(91.0, 0.0), false);
ft_assert_eq('Out-of-range longitude rejected', piratebox_coordinate_is_valid(0.0, -181.0), false);

// --- Time snapshot: structural + known-value checks -------------------------

// A fixed, known instant: 2024-01-01 00:00:00 UTC = 1704067200. Render in
// UTC explicitly so this test doesn't depend on the host's configured
// timezone.
$prevTz = date_default_timezone_get();
date_default_timezone_set('UTC');
$snap = piratebox_fieldtools_now_snapshot(1704067200);
ft_assert_eq('Known instant: weekday', $snap['weekday'], 'Monday');
ft_assert_eq('Known instant: day of year', $snap['day_of_year'], 1);
ft_assert_eq('Known instant: ISO-8601 UTC', $snap['iso8601_utc'], '2024-01-01T00:00:00Z');
ft_assert_eq('Known instant: unix passthrough', $snap['unix'], 1704067200);
ft_assert_eq('2024 is a leap year (366 days)', $snap['days_in_year'], 366);

// Last day of a non-leap year
$snap = piratebox_fieldtools_now_snapshot(1703980800); // 2023-12-31 00:00:00 UTC
ft_assert_eq('Last day of 2023: day of year', $snap['day_of_year'], 365);
ft_assert_eq('2023 is not a leap year (365 days)', $snap['days_in_year'], 365);
date_default_timezone_set($prevTz);

// --- Elapsed-time calculator: sign cases -------------------------------------

$e = piratebox_elapsed_between(1000, 1000);
ft_assert_eq('Elapsed: same instant', $e['direction'], 'same');
ft_assert_eq('Elapsed: same instant seconds', $e['seconds'], 0);

$e = piratebox_elapsed_between(1000, 4600); // +1h exactly
ft_assert_eq('Elapsed: end after start', $e['direction'], 'after');
ft_assert_eq('Elapsed: 1 hour in seconds', $e['seconds'], 3600);

$e = piratebox_elapsed_between(4600, 1000); // reversed
ft_assert_eq('Elapsed: end before start', $e['direction'], 'before');
ft_assert_eq('Elapsed: negative seconds preserved', $e['seconds'], -3600);

// --- Time source status: structural check only (live-system-dependent) -----
//
// piratebox_get_time_source_status() reads /run/piratebox/status.json
// (via piratebox_get_helper_status()) rather than touching restricted
// paths directly (see that function's own header - PHP-FPM's
// open_basedir blocks /sys/class/rtc etc., found live). Whether this
// CLI run's environment has a fresh, time_source-publishing status
// snapshot available is itself live-system-dependent (this repo's fix
// may be newer than whatever piratebox_status_helper.sh is actually
// installed/running) - so this only checks the SHAPE is honest, not a
// specific value: when 'available' is true the three fields must be
// real booleans; when false, they must be null, never a fabricated
// guess either way.

$status = piratebox_get_time_source_status();
ft_assert_true('Time source status has available key', array_key_exists('available', $status));
ft_assert_true('Time source status has stale key', array_key_exists('stale', $status));
ft_assert_true('Time source status has rtc_detected key', array_key_exists('rtc_detected', $status));
ft_assert_true('Time source status has ntp_synchronized key', array_key_exists('ntp_synchronized', $status));
ft_assert_true('Time source status has fake_hwclock_installed key', array_key_exists('fake_hwclock_installed', $status));
ft_assert_true('available is boolean', is_bool($status['available']));
ft_assert_true('stale is boolean', is_bool($status['stale']));
foreach (['rtc_detected', 'ntp_synchronized', 'fake_hwclock_installed'] as $field) {
    if ($status['available']) {
        ft_assert_true("$field is boolean when available", is_bool($status[$field]));
    } else {
        ft_assert_null("$field is null when unavailable (never fabricated)", $status[$field]);
    }
}

// Direct check of the pure shape logic (not live-system-dependent):
// unavailable input must never leak a fabricated true/false.
function ft_time_source_shape(bool $stale, $timeSource): array
{
    $available = !$stale && is_array($timeSource);
    return [
        'available'              => $available,
        'stale'                  => $stale,
        'rtc_detected'           => $available ? (bool) ($timeSource['rtc_detected'] ?? false) : null,
        'ntp_synchronized'       => $available ? (bool) ($timeSource['ntp_synchronized'] ?? false) : null,
        'fake_hwclock_installed' => $available ? (bool) ($timeSource['fake_hwclock_installed'] ?? false) : null,
    ];
}
$shape = ft_time_source_shape(false, null); // fresh snapshot, but old status helper (no time_source key yet)
ft_assert_eq('Shape: fresh snapshot, missing time_source block -> unavailable', $shape['available'], false);
ft_assert_null('Shape: rtc_detected null when block missing', $shape['rtc_detected']);
$shape = ft_time_source_shape(true, ['rtc_detected' => true]); // stale snapshot, even with a time_source block
ft_assert_eq('Shape: stale snapshot -> unavailable even if block present', $shape['available'], false);
ft_assert_null('Shape: rtc_detected null when stale', $shape['rtc_detected']);
$shape = ft_time_source_shape(false, ['rtc_detected' => true, 'ntp_synchronized' => false, 'fake_hwclock_installed' => false]);
ft_assert_eq('Shape: fresh + present block -> available', $shape['available'], true);
ft_assert_eq('Shape: rtc_detected true passes through', $shape['rtc_detected'], true);
ft_assert_eq('Shape: ntp_synchronized false passes through (not null)', $shape['ntp_synchronized'], false);

// --- Summary ---------------------------------------------------------------

echo "Field Tools tests: $passCount passed, " . count($failures) . " failed.\n";
if ($failures) {
    echo "\nFAILURES:\n";
    foreach ($failures as $f) {
        echo "  - $f\n";
    }
    exit(1);
}
exit(0);
