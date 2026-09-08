<?php

declare(strict_types=1);

// PirateBox-wide temperature display-unit preference (2026-09-08).
//
// ARCHITECTURAL RULE (non-negotiable, see docs/ESP32-SUPERVISOR-
// DESIGN.md's temperature-unit section for the full rationale):
// canonical sensor data - the ESP32 wire protocol, the cached export,
// piratebox_history.py's stored history - is ALWAYS Celsius. This file
// exists ONLY to answer "what unit should a human see right now" and
// to do the actual C->F arithmetic at the one place values are about
// to be shown to a person. It never touches, converts, or rewrites
// anything in /run/piratebox-esp32/ or /var/lib/piratebox-history/ -
// callers convert an already-fetched Celsius value at render time,
// every time, and the stored/cached data underneath is untouched by a
// unit change.
//
// STORAGE: mirrors includes/travel_mode.php's exact pattern (a tiny
// JSON file under data/, atomic temp-file-then-rename write) - the
// established "small global device preference" architecture this
// project already has, reused rather than inventing a new settings
// framework for one toggle. Deliberately NOT localStorage (unlike
// includes/theme.php's per-browser preference): the OLED daemon (a
// separate Python process with no browser at all) needs to read the
// SAME choice, so it must be a small server-side file both a PHP
// process (www-data) and the OLED daemon (piratebox-gpio) can reach -
// see piratebox_temp_unit.py, which reads this exact file. The
// resulting file is plain `file_put_contents()` output (0644,
// world-readable, same as every other file this project writes this
// way - e.g. data/travel-mode.json) - no new permission grant needed
// for the OLED daemon to read it, and its own ProtectSystem=strict
// sandboxing only blocks WRITES outside its allowlisted paths, not
// reads elsewhere.
//
// GLOBAL, NOT PER-VISITOR: like Travel Mode, this is one device-wide
// setting an operator sets via /admin/ - this project has no per-
// visitor identity/preference system anywhere (by design - see
// docs/ARCHITECTURE.md's privacy principles), so there is no "each
// browser remembers its own choice" model here, unlike the purely
// cosmetic, no-server-involvement theme switcher.

if (!defined('PIRATEBOX_TEMP_UNIT_FILE')) {
    define('PIRATEBOX_TEMP_UNIT_FILE', __DIR__ . '/../data/temp-unit.json');
}

const PIRATEBOX_TEMP_UNITS = ['C', 'F'];

if (!function_exists('piratebox_get_temp_unit')) {
    /**
     * Returns 'C' or 'F'. Missing file, unreadable, malformed JSON, or
     * a value that isn't exactly one of the two known units - all
     * resolve to 'C', the canonical storage unit itself. This is a
     * deliberately safe default: "preference not set yet" means "show
     * exactly what's stored, no conversion applied" - never a
     * fabricated Fahrenheit default a fresh install never asked for.
     *
     * @param ?string $path Injectable for tests (defaults to the real
     *   PIRATEBOX_TEMP_UNIT_FILE) - same pattern includes/history.php
     *   already established for its own file-path parameters.
     */
    function piratebox_get_temp_unit(?string $path = null): string
    {
        $raw = @file_get_contents($path ?? PIRATEBOX_TEMP_UNIT_FILE);
        if ($raw !== false) {
            $decoded = json_decode($raw, true);
            if (is_array($decoded) && in_array($decoded['unit'] ?? null, PIRATEBOX_TEMP_UNITS, true)) {
                return $decoded['unit'];
            }
        }
        return 'C';
    }
}

if (!function_exists('piratebox_set_temp_unit')) {
    /**
     * Persists a new unit choice. Rejects anything other than exactly
     * 'C' or 'F' (returns false, changes nothing) - never silently
     * coerces an unrecognized value. Atomic temp-file-then-rename
     * write, same pattern every other store in this project uses.
     */
    function piratebox_set_temp_unit(string $unit, ?string $path = null): bool
    {
        if (!in_array($unit, PIRATEBOX_TEMP_UNITS, true)) {
            return false;
        }
        $target = $path ?? PIRATEBOX_TEMP_UNIT_FILE;
        $tmp = $target . '.tmp.' . getmypid() . '.' . bin2hex(random_bytes(4));
        if (file_put_contents($tmp, json_encode(['unit' => $unit], JSON_PRETTY_PRINT)) === false) {
            return false;
        }
        if (!rename($tmp, $target)) {
            @unlink($tmp);
            return false;
        }
        return true;
    }
}

if (!function_exists('piratebox_convert_temp_c')) {
    /**
     * Pure conversion, the ONE place C->F arithmetic happens in PHP.
     * `$celsius` is always assumed to be genuine Celsius (the
     * canonical unit everywhere upstream of this call) - this function
     * has no way to detect a value that was already converted, which
     * is exactly why every caller in this codebase converts an
     * already-fetched Celsius value exactly once, right before
     * display, and never stores or re-passes the converted result
     * anywhere else (see this file's own header).
     *
     * Returns $celsius unchanged (not even a float-cast no-op beyond
     * what's needed) when $unit is 'C' - a null celsius value passes
     * through as null so callers keep their own existing "no reading"
     * handling unchanged.
     */
    function piratebox_convert_temp_c(?float $celsius, string $unit): ?float
    {
        if ($celsius === null || $unit !== 'F') {
            return $celsius;
        }
        return ($celsius * 9.0 / 5.0) + 32.0;
    }
}

if (!function_exists('piratebox_temp_unit_post_is_authorized')) {
    /**
     * Narrow same-session CSRF check guarding this ONE preference when
     * it's changed from a public, unauthenticated page (2026-09-08:
     * the Environment page's own C/F quick-toggle) - NOT a general
     * auth check, and NOT a substitute for /admin/'s own separate
     * nginx Basic Auth + CSRF pairing (which stays exactly as it was,
     * untouched by this function). It only proves the request came
     * from a page this same PHP session already rendered (a third-
     * party site forging a cross-site POST has no way to know the
     * token), without requiring a login - an appropriate, narrow scope
     * for a fully reversible, non-sensitive, two-value display
     * preference (same "fully reversible" reasoning admin/index.php's
     * own set_temp_unit action already documents for this exact
     * setting). Both tokens must be present and non-empty - a session
     * that never minted one (e.g. hasn't visited any page that calls
     * session_start() and seeds $_SESSION['csrf_token']) always fails
     * closed, never open.
     */
    function piratebox_temp_unit_post_is_authorized(?string $sessionToken, ?string $submittedToken): bool
    {
        return !empty($sessionToken) && !empty($submittedToken) && hash_equals($sessionToken, $submittedToken);
    }
}

if (!function_exists('piratebox_temp_unit_symbol')) {
    /**
     * '°C' or '°F' (HTML entity form, matching how every existing
     * temperature display in this codebase already renders the
     * degree sign - see environment/index.php's pre-existing
     * `&deg;C` usage). Falls back to '°C' for anything unrecognized,
     * same fail-safe-default discipline as piratebox_get_temp_unit().
     */
    function piratebox_temp_unit_symbol(string $unit): string
    {
        return $unit === 'F' ? '&deg;F' : '&deg;C';
    }
}
