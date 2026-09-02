<?php

declare(strict_types=1);

// GPIO wiring self-description (docs/ARCHITECTURE.md §17's "self-
// describing/inheritable device" - wiring assignments was the one
// explicit, concrete gap named there: "reachable today only by reading
// this repository's own docs directly, not from a page").
//
// data/gpio-wiring.json mirrors docs/HARDWARE-INTEGRATION-DESIGN.md
// §2's table - that design doc stays the authoritative source for
// wiring *decisions*; this file is what actually renders on-device so
// a future owner doesn't need the repo. Deliberately NOT live-sensed:
// there is no software way to discover "what a floating, unclaimed
// GPIO pin is physically wired to" - `status` here is the same
// operator-maintained fact the design doc already records (update both
// together when a wire actually gets connected - see that doc's own
// note about keeping it current). What IS true and checkable stays
// checkable elsewhere (e.g. GPIO25's real state already surfaces
// through includes/capability_state.php's `shutdown_button` capability
// - this file doesn't duplicate that, just adds the physical-pin
// context capability_state.php doesn't carry).

if (!function_exists('piratebox_parse_gpio_wiring')) {
    /**
     * Pure parser - validates shape, never fabricates a row. Returns
     * null (not []) on missing/malformed input, same "unknown, not
     * empty" discipline as piratebox_reference_pack_entry_count().
     *
     * @return array<int, array{function: string, bcm: string, physical_pin: string, status: string, notes: string}>|null
     */
    function piratebox_parse_gpio_wiring($decoded): ?array
    {
        if (!is_array($decoded)) return null;

        $rows = [];
        foreach ($decoded as $row) {
            if (!is_array($row)) continue;
            if (!isset($row['function'], $row['bcm'], $row['physical_pin'], $row['status'])) continue;
            $rows[] = [
                'function' => (string) $row['function'],
                'bcm' => (string) $row['bcm'],
                'physical_pin' => (string) $row['physical_pin'],
                'status' => (string) $row['status'],
                'notes' => (string) ($row['notes'] ?? ''),
            ];
        }
        return $rows;
    }
}

if (!function_exists('piratebox_get_gpio_wiring')) {
    /**
     * Thin fs wrapper - see piratebox_parse_gpio_wiring(). Returns null
     * (not a fabricated empty list) if the file is missing or
     * malformed, so the admin page can say "unavailable" honestly
     * rather than silently show "no wiring assigned."
     *
     * @return array<int, array{function: string, bcm: string, physical_pin: string, status: string, notes: string}>|null
     */
    function piratebox_get_gpio_wiring(): ?array
    {
        $raw = @file_get_contents(__DIR__ . '/../data/gpio-wiring.json');
        if ($raw === false) return null;
        $decoded = json_decode($raw, true);
        return piratebox_parse_gpio_wiring($decoded);
    }
}
