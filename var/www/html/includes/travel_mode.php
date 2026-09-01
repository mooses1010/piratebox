<?php

declare(strict_types=1);

// PirateBox Travel Mode (post-Stage-32) - a privacy-oriented toggle that
// temporarily suppresses location-specific content (Local Information,
// the regional map catalog, and search/export surfaces that could embed
// either) without deleting any of it. See docs/TRAVEL-MODE-DESIGN.md for
// the full design and threat model.
//
// Persisted on the SD card (data/travel-mode.json), unlike mode.php's
// deliberately volatile /tmp state - the whole point is surviving a
// reboot that happens WHILE away from home, so a power cycle mid-trip
// can't silently drop back to showing local info exactly when it
// matters most. Fully orthogonal to piratebox_get_mode() (Normal/
// Emergency) and to includes/content_profile.php - this file never
// reads either, and nothing in this file changes based on either.
//
// FAIL-SAFE DIRECTION (deliberately the OPPOSITE of mode.php's own
// fail-safe): mode.php defaults any unreadable/unexpected state to
// Normal (the least alarming state). Travel Mode defaults any
// unexpected state to ON/suppressed (the least revealing state) - per
// instruction, an unavailable or corrupt state file must never
// accidentally expose local information. The one exception is this
// feature's own first deployment, which explicitly seeds the state
// file with travel_mode=false so shipping this code doesn't suddenly
// hide Local Information for every existing at-home deployment - see
// the deploy step in docs/OPERATIONAL-DECISIONS.md.

define('PIRATEBOX_TRAVEL_MODE_FILE', __DIR__ . '/../data/travel-mode.json');

// Fixed, hardcoded list of local-sensitive static export artifacts,
// relative to public/utility/exports/. This is deliberately a BLUNT
// mechanism, not a content inspector or an authorization system: it
// does not care whether a given path currently contains real local
// data or still-empty placeholder content, and it never tries to
// separate "local" from "universal" content within a single file that
// mixes both (e.g. the exported static Search page, which bakes every
// section's results into one flat HTML file - see the design doc for
// why that one is quarantined wholesale rather than filtered).
// Universal-only bundles (radio, emergency, first aid, manuals, the
// generic maps coordinate/GPS reference) are never in this list.
define('PIRATEBOX_TRAVEL_MODE_QUARANTINE_PATHS', [
    'maps-local-bundle.zip',
    'complete-utility-library.zip',
    'data/local',
    'data/maps/catalog.json',
    'static/local',
    'static/search',
]);

if (!function_exists('piratebox_get_travel_mode')) {
    /**
     * True if Travel Mode is currently active. Any failure mode -
     * missing file, unreadable, malformed JSON, or a value that isn't
     * a real boolean - resolves to true (suppressed), the only
     * privacy-safe default when state can't be trusted. This is the
     * opposite convention from piratebox_get_mode()'s "unknown always
     * means Normal" rule, deliberately - see the file header.
     */
    function piratebox_get_travel_mode(): bool
    {
        $raw = @file_get_contents(PIRATEBOX_TRAVEL_MODE_FILE);
        if ($raw !== false) {
            $decoded = json_decode($raw, true);
            if (is_array($decoded) && isset($decoded['travel_mode']) && is_bool($decoded['travel_mode'])) {
                return $decoded['travel_mode'];
            }
        }
        return true;
    }
}

if (!function_exists('piratebox_set_travel_mode')) {
    /**
     * Persists a new Travel Mode state and immediately re-applies the
     * direct-access quarantine (see piratebox_apply_travel_mode_quarantine())
     * so the on-disk protection is never out of sync with the state a
     * caller just set. Atomic temp-file-then-rename write, same pattern
     * every other store in this project uses.
     */
    function piratebox_set_travel_mode(bool $enabled): bool
    {
        $tmp = PIRATEBOX_TRAVEL_MODE_FILE . '.tmp.' . getmypid() . '.' . bin2hex(random_bytes(4));
        if (file_put_contents($tmp, json_encode(['travel_mode' => $enabled], JSON_PRETTY_PRINT)) === false) {
            return false;
        }
        if (!rename($tmp, PIRATEBOX_TRAVEL_MODE_FILE)) {
            @unlink($tmp);
            return false;
        }
        piratebox_apply_travel_mode_quarantine(__DIR__ . '/../public/utility/exports', __DIR__ . '/../data/travel-mode-quarantine');
        return true;
    }
}

if (!function_exists('piratebox_apply_travel_mode_quarantine')) {
    /**
     * Enforces Travel Mode's direct-access protection: moves the fixed
     * set of local-sensitive static export artifacts (see
     * PIRATEBOX_TRAVEL_MODE_QUARANTINE_PATHS) between their normal,
     * web-servable location under public/utility/exports/ and a
     * holding directory under data/ - which sits OUTSIDE the webroot
     * entirely (nginx's document root is public/, so nothing under
     * data/ is reachable by any URL, the same boundary chat.json/
     * device-id.json already rely on). Nothing new is invented here;
     * this reuses the project's oldest, most-tested security boundary
     * instead of adding a permission check that could have its own
     * bugs.
     *
     * Idempotent and safe to call any number of times, from any
     * starting state: it only moves a path if it isn't already where
     * it needs to be for the current mode. Called from two places -
     * piratebox_set_travel_mode() (immediately, for a live toggle) and
     * tools/apply_travel_mode_quarantine.php (after every real deploy,
     * in case the deploy just wrote fresh, un-quarantined copies of a
     * local-sensitive export over ones that were already quarantined).
     */
    function piratebox_apply_travel_mode_quarantine(string $exportsDir, string $quarantineDir): void
    {
        $enabled = piratebox_get_travel_mode();

        foreach (PIRATEBOX_TRAVEL_MODE_QUARANTINE_PATHS as $relPath) {
            $normal = $exportsDir . '/' . $relPath;
            $quarantined = $quarantineDir . '/' . $relPath;

            if ($enabled) {
                if (file_exists($normal)) {
                    piratebox_travel_mode_move($normal, $quarantined);
                }
            } else {
                if (!file_exists($normal) && file_exists($quarantined)) {
                    piratebox_travel_mode_move($quarantined, $normal);
                }
            }
        }
    }
}

if (!function_exists('piratebox_travel_mode_move')) {
    /**
     * Moves a file or directory from $from to $to, creating $to's
     * parent directory if needed and clearing any stale copy already
     * at $to first (so rename() can't silently fail on a leftover from
     * an interrupted previous move). Best-effort: a failure here means
     * a quarantine move didn't happen, not a fatal error - the next
     * call (next toggle, or next deploy) will retry it.
     */
    function piratebox_travel_mode_move(string $from, string $to): void
    {
        $destParent = dirname($to);
        if (!is_dir($destParent)) {
            @mkdir($destParent, 0755, true);
        }
        if (file_exists($to)) {
            piratebox_travel_mode_remove_path($to);
        }
        @rename($from, $to);
    }
}

if (!function_exists('piratebox_travel_mode_remove_path')) {
    /**
     * Recursively removes a file or directory. Only ever called on
     * paths already scoped to PIRATEBOX_TRAVEL_MODE_QUARANTINE_PATHS
     * by piratebox_travel_mode_move() above - never given arbitrary
     * input.
     */
    function piratebox_travel_mode_remove_path(string $path): void
    {
        if (is_dir($path) && !is_link($path)) {
            foreach (array_diff(scandir($path) ?: [], ['.', '..']) as $entry) {
                piratebox_travel_mode_remove_path($path . '/' . $entry);
            }
            @rmdir($path);
        } else {
            @unlink($path);
        }
    }
}
