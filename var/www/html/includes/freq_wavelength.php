<?php

declare(strict_types=1);

// Frequency <-> Wavelength Calculator (Reference -> Tool principle, see
// docs/REFERENCE-CONTENT-DESIGN.md §9). Companion to Radio Reference's
// HF/VHF/UHF and Antenna & Band Guidance guides - this is the
// calculator, those pages are the explanation.
//
// Pure, deterministic, dependency-free - same discipline as every
// other Field Tools include. Uses the exact speed of light in a
// vacuum (299,792,458 m/s, an SI-defined constant, not measured/
// approximated) for free-space wavelength - see
// piratebox_wavelength_info()'s own note on why a REAL antenna's
// actual required length differs from this.

if (!function_exists('PIRATEBOX_SPEED_OF_LIGHT_MPS')) {
    define('PIRATEBOX_SPEED_OF_LIGHT_MPS', 299792458.0);
}

if (!function_exists('piratebox_frequency_unit_multiplier')) {
    /** @return float|null Hz per unit, or null for an unrecognized unit. */
    function piratebox_frequency_unit_multiplier(string $unit): ?float
    {
        $map = ['hz' => 1.0, 'khz' => 1e3, 'mhz' => 1e6, 'ghz' => 1e9];
        return $map[strtolower($unit)] ?? null;
    }
}

if (!function_exists('piratebox_radio_band_for_frequency')) {
    /**
     * Same HF/VHF/UHF boundaries as the Radio Reference "HF vs VHF vs
     * UHF" guide (3-30 MHz / 30-300 MHz / 300 MHz-3 GHz) - not a
     * separate, potentially-drifting definition.
     */
    function piratebox_radio_band_for_frequency(float $hz): string
    {
        $mhz = $hz / 1e6;
        if ($mhz < 0.3) return 'MF or below';
        if ($mhz < 3) return 'MF';
        if ($mhz < 30) return 'HF';
        if ($mhz < 300) return 'VHF';
        if ($mhz < 3000) return 'UHF';
        return 'SHF or above';
    }
}

if (!function_exists('piratebox_wavelength_info')) {
    /**
     * @return array{error: string}|array{
     *   frequency_hz: float, frequency_display: string, band: string,
     *   wavelength_m: string, wavelength_ft: string,
     *   half_wave_m: string, half_wave_ft: string,
     *   quarter_wave_m: string, quarter_wave_ft: string
     * }
     */
    function piratebox_wavelength_info(string $valueInput, string $unitInput): array
    {
        $valueInput = trim($valueInput);
        if (!is_numeric($valueInput) || (float) $valueInput <= 0) {
            return ['error' => "\"$valueInput\" isn't a valid positive frequency."];
        }
        $multiplier = piratebox_frequency_unit_multiplier($unitInput);
        if ($multiplier === null) {
            return ['error' => "\"$unitInput\" isn't a recognized frequency unit - use Hz, kHz, MHz, or GHz."];
        }
        $hz = (float) $valueInput * $multiplier;
        $wavelengthM = PIRATEBOX_SPEED_OF_LIGHT_MPS / $hz;
        $wavelengthFt = $wavelengthM * 3.28084;

        return [
            'frequency_hz' => $hz,
            'frequency_display' => rtrim(rtrim(number_format((float) $valueInput, 6, '.', ','), '0'), '.') . ' ' . strtoupper($unitInput),
            'band' => piratebox_radio_band_for_frequency($hz),
            'wavelength_m' => piratebox_format_length($wavelengthM),
            'wavelength_ft' => piratebox_format_length($wavelengthFt),
            'half_wave_m' => piratebox_format_length($wavelengthM / 2),
            'half_wave_ft' => piratebox_format_length($wavelengthFt / 2),
            'quarter_wave_m' => piratebox_format_length($wavelengthM / 4),
            'quarter_wave_ft' => piratebox_format_length($wavelengthFt / 4),
        ];
    }
}

if (!function_exists('piratebox_format_length')) {
    /** Trims to a sensible number of significant decimals without implying false precision. */
    function piratebox_format_length(float $meters): string
    {
        $decimals = $meters >= 100 ? 1 : ($meters >= 1 ? 3 : 4);
        return number_format($meters, $decimals, '.', ',');
    }
}
