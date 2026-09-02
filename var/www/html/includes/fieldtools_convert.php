<?php

declare(strict_types=1);

// Field Tools (Post-Stage-32) - unit/coordinate conversion functions.
//
// Every function here is a small, pure, deterministic function: numbers
// in, a number (or array) out, no filesystem/network/session access, no
// state. That's deliberate - it's what makes tools/test_fieldtools.php
// able to test them directly from the CLI with no web server, database,
// or fixture involved, and it's what makes the client-side copy in
// public/assets/fieldtools.js safe to keep in lockstep with these: the
// formulas themselves are this file's whole job, nothing else.
//
// PHP is the tested, canonical reference implementation. fieldtools.js
// mirrors the same formulas for instant client-side feedback (this
// project has no build step / no shared PHP-to-JS codegen) - see that
// file's own header, and docs/OPERATIONAL-DECISIONS.md ("Field Tools /
// Offline Reference Instruments") for why that duplication was accepted
// rather than adding a fetch round-trip for simple arithmetic.
//
// PRIVACY: pure math on whatever numbers a visitor types in. Nothing
// here reads, writes, or remembers any input - no logging, no session
// storage, no data file. See public/utility/fieldtools/ pages for the
// explicit "nothing you enter is saved" statement shown to visitors.

// --- Temperature --------------------------------------------------------

if (!function_exists('piratebox_convert_temperature')) {
    /**
     * @param string $from 'c' or 'f'
     * @param string $to   'c' or 'f'
     */
    function piratebox_convert_temperature(float $value, string $from, string $to): float
    {
        $from = strtolower($from);
        $to = strtolower($to);
        // Normalize to Celsius first, then out - avoids a 2x2 special-case
        // table for what's really one linear relationship.
        $c = $from === 'f' ? ($value - 32) * 5 / 9 : $value;
        return $to === 'f' ? ($c * 9 / 5) + 32 : $c;
    }
}

// --- Distance -------------------------------------------------------------

if (!function_exists('piratebox_convert_distance')) {
    function piratebox_convert_distance(float $value, string $from, string $to): float
    {
        static $toMeters = [
            'mm' => 0.001,
            'cm' => 0.01,
            'm'  => 1.0,
            'km' => 1000.0,
            'in' => 0.0254,
            'ft' => 0.3048,
            'yd' => 0.9144,
            'mi' => 1609.344,
        ];
        $meters = $value * $toMeters[strtolower($from)];
        return $meters / $toMeters[strtolower($to)];
    }
}

// --- Mass -------------------------------------------------------------

if (!function_exists('piratebox_convert_mass')) {
    function piratebox_convert_mass(float $value, string $from, string $to): float
    {
        static $toGrams = [
            'g'  => 1.0,
            'kg' => 1000.0,
            'oz' => 28.349523125,
            'lb' => 453.59237,
        ];
        $grams = $value * $toGrams[strtolower($from)];
        return $grams / $toGrams[strtolower($to)];
    }
}

// --- Volume -------------------------------------------------------------

if (!function_exists('piratebox_convert_volume')) {
    // US customary throughout (US fl oz / US cups / US pints / US quarts /
    // US gallons) - stated explicitly in the UI, since Imperial volume
    // units share the same names for different sizes and silently mixing
    // them would be a real, easy-to-miss error.
    function piratebox_convert_volume(float $value, string $from, string $to): float
    {
        static $toMl = [
            'ml'      => 1.0,
            'l'       => 1000.0,
            'us_floz' => 29.5735295625,
            'us_cup'  => 236.5882365,
            'us_pint' => 473.176473,
            'us_qt'   => 946.352946,
            'us_gal'  => 3785.411784,
        ];
        $ml = $value * $toMl[strtolower($from)];
        return $ml / $toMl[strtolower($to)];
    }
}

// --- Speed -------------------------------------------------------------

if (!function_exists('piratebox_convert_speed')) {
    function piratebox_convert_speed(float $value, string $from, string $to): float
    {
        static $toMs = [
            'mph' => 0.44704,
            'kmh' => 1000.0 / 3600.0,
            'ms'  => 1.0,
        ];
        $ms = $value * $toMs[strtolower($from)];
        return $ms / $toMs[strtolower($to)];
    }
}

// --- Pressure -------------------------------------------------------------

if (!function_exists('piratebox_convert_pressure')) {
    function piratebox_convert_pressure(float $value, string $from, string $to): float
    {
        static $toKpa = [
            'psi' => 6.894757293168,
            'kpa' => 1.0,
            'bar' => 100.0,
        ];
        $kpa = $value * $toKpa[strtolower($from)];
        return $kpa / $toKpa[strtolower($to)];
    }
}

// --- Storage / data -------------------------------------------------------

if (!function_exists('piratebox_convert_storage')) {
    // Binary (1024-based) throughout, matching piratebox_fmt_bytes() in
    // helpers.php - this device already reports storage that way (Stats
    // page, admin page); a second, decimal (1000-based) convention living
    // in the same app would be a real source of quiet errors, so this
    // deliberately does not offer one. Labeled KiB/MiB/GiB/TiB in the UI
    // for the same reason.
    function piratebox_convert_storage(float $value, string $from, string $to): float
    {
        static $toBytes = [
            'b'   => 1.0,
            'kib' => 1024.0,
            'mib' => 1024.0 ** 2,
            'gib' => 1024.0 ** 3,
            'tib' => 1024.0 ** 4,
        ];
        $bytes = $value * $toBytes[strtolower($from)];
        return $bytes / $toBytes[strtolower($to)];
    }
}

// --- Percentage / ratio -------------------------------------------------

if (!function_exists('piratebox_percentage_of')) {
    /** What percent $part is of $whole. Null if $whole is 0 (undefined). */
    function piratebox_percentage_of(float $part, float $whole): ?float
    {
        if ($whole == 0.0) return null;
        return ($part / $whole) * 100;
    }
}

if (!function_exists('piratebox_percentage_change')) {
    /** Percent change from $old to $new. Null if $old is 0 (undefined). */
    function piratebox_percentage_change(float $old, float $new): ?float
    {
        if ($old == 0.0) return null;
        return (($new - $old) / $old) * 100;
    }
}

if (!function_exists('piratebox_apply_percentage')) {
    /** $value plus (or minus, for a negative $percent) $percent of itself. */
    function piratebox_apply_percentage(float $value, float $percent): float
    {
        return $value * (1 + $percent / 100);
    }
}

// --- Electrical / battery -------------------------------------------------

if (!function_exists('piratebox_electrical_watts')) {
    /** P = V x I. */
    function piratebox_electrical_watts(float $volts, float $amps): float
    {
        return $volts * $amps;
    }
}

if (!function_exists('piratebox_electrical_amps')) {
    /** I = P / V. Null if V is 0 (undefined). */
    function piratebox_electrical_amps(float $watts, float $volts): ?float
    {
        if ($volts == 0.0) return null;
        return $watts / $volts;
    }
}

if (!function_exists('piratebox_electrical_watt_hours')) {
    /** Energy = power x time. */
    function piratebox_electrical_watt_hours(float $watts, float $hours): float
    {
        return $watts * $hours;
    }
}

if (!function_exists('piratebox_electrical_ah_to_wh')) {
    /** Amp-hours at a given voltage -> watt-hours. */
    function piratebox_electrical_ah_to_wh(float $ampHours, float $volts): float
    {
        return $ampHours * $volts;
    }
}

if (!function_exists('piratebox_battery_runtime_hours')) {
    /**
     * THEORETICAL runtime estimate only - see the caveat text shown
     * alongside this tool in the UI. Real-world runtime is normally
     * lower than this arithmetic suggests: inverter/converter losses,
     * a battery's usable capacity dropping at high discharge rates or
     * low temperature, and a load that isn't perfectly constant all
     * push the real number down, not up. $efficiency (0-1) is a single
     * blunt derate factor for all of that combined, not a precise
     * model - it is deliberately not hidden inside the arithmetic.
     *
     * Returns null if $loadWatts <= 0 or $efficiency <= 0 (undefined /
     * meaningless inputs), rather than a divide-by-zero or a negative
     * "runtime."
     */
    function piratebox_battery_runtime_hours(float $capacityWh, float $loadWatts, float $efficiency = 0.8): ?float
    {
        if ($loadWatts <= 0.0 || $efficiency <= 0.0) return null;
        return ($capacityWh * $efficiency) / $loadWatts;
    }
}

// --- Coordinates -------------------------------------------------------

if (!function_exists('piratebox_dd_to_dms')) {
    /**
     * Decimal degrees -> [degrees, minutes, seconds, hemisphere letter].
     * $isLatitude picks N/S vs E/W for the hemisphere letter; the
     * returned degrees/minutes/seconds are always non-negative (the sign
     * is expressed as the hemisphere letter, the conventional DMS form).
     */
    function piratebox_dd_to_dms(float $decimalDegrees, bool $isLatitude): array
    {
        $hemisphere = $isLatitude
            ? ($decimalDegrees < 0 ? 'S' : 'N')
            : ($decimalDegrees < 0 ? 'W' : 'E');
        $abs = abs($decimalDegrees);
        $deg = (int) floor($abs);
        $minFloat = ($abs - $deg) * 60;
        $min = (int) floor($minFloat);
        $sec = ($minFloat - $min) * 60;
        // Carry a floating-point-rounded 60.00s up into minutes/degrees
        // rather than displaying an impossible "60" seconds value.
        if (round($sec, 6) >= 60.0) {
            $sec = 0.0;
            $min++;
        }
        if ($min >= 60) {
            $min = 0;
            $deg++;
        }
        return [$deg, $min, $sec, $hemisphere];
    }
}

if (!function_exists('piratebox_dms_to_dd')) {
    /**
     * Degrees/minutes/seconds + hemisphere letter -> signed decimal
     * degrees. Returns null for an out-of-range minutes/seconds value or
     * an unrecognized hemisphere letter, rather than silently producing
     * a wrong coordinate.
     */
    function piratebox_dms_to_dd(float $degrees, float $minutes, float $seconds, string $hemisphere): ?float
    {
        $hemisphere = strtoupper(trim($hemisphere));
        if (!in_array($hemisphere, ['N', 'S', 'E', 'W'], true)) return null;
        if ($minutes < 0 || $minutes >= 60 || $seconds < 0 || $seconds >= 60 || $degrees < 0) return null;
        $dd = $degrees + ($minutes / 60) + ($seconds / 3600);
        return in_array($hemisphere, ['S', 'W'], true) ? -$dd : $dd;
    }
}

if (!function_exists('piratebox_coordinate_is_valid')) {
    /** Sanity check for a decimal-degrees pair, not a format check. */
    function piratebox_coordinate_is_valid(float $lat, float $lon): bool
    {
        return $lat >= -90.0 && $lat <= 90.0 && $lon >= -180.0 && $lon <= 180.0;
    }
}
