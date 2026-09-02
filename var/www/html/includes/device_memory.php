<?php

declare(strict_types=1);

// Device Memory (docs/DEVICE-MEMORY-DESIGN.md) - read side.
//
// Reads var/www/html/data/device-history.json, written by
// piratebox_status_helper.sh (see that script's own header for the
// write side / retention design). This file lives under var/www/html/
// data/, inside PHP-FPM's open_basedir (etc/php/8.4/fpm/php.ini) - no
// new exposure, same boundary every other data/*.json reader already
// works within.
//
// Deliberately does NOT compute or cache anything here that the write
// side doesn't already own - this is a thin, honest reader: if the
// file is missing, stale-looking, or malformed, it says so rather than
// inventing zero/empty as if that were a real observation. "No history
// recorded yet" and "zero events happened" are different facts and
// must never be confused (docs/ARCHITECTURE.md §10's core discipline,
// applied here to history the same way includes/capability_state.php
// already applies it to hardware).

if (!function_exists('piratebox_parse_device_memory')) {
    /**
     * Pure, directly testable - takes the already-json_decode()'d value
     * (or null, for "file missing/unreadable") rather than touching the
     * filesystem itself, so every shape - missing, malformed, empty,
     * partially-populated - can be unit-tested without needing a real
     * file on disk. piratebox_get_device_memory() below is the thin
     * filesystem wrapper around this.
     *
     * @param mixed $decoded whatever json_decode($raw, true) produced,
     *   or null if the file couldn't be read at all
     * @return array{
     *   available: bool, boot_count: ?int, last_boot_at: ?int,
     *   undervoltage_events_total: ?int, undervoltage_events_recent: ?array,
     *   history_started_at: ?int, updated_at: ?int
     * }
     * `available` is false whenever nothing trustworthy could be parsed
     * - every other field is null then, never a fabricated zero.
     */
    function piratebox_parse_device_memory($decoded): array
    {
        $unavailable = [
            'available' => false,
            'boot_count' => null,
            'boot_events_recent' => null,
            'last_boot_at' => null,
            'undervoltage_events_total' => null,
            'undervoltage_events_recent' => null,
            'history_started_at' => null,
            'updated_at' => null,
        ];

        if (!is_array($decoded)) return $unavailable;

        $bootEvents = is_array($decoded['boot_events'] ?? null)
            ? array_values(array_filter($decoded['boot_events'], 'is_int')) : [];
        $dailyBuckets = is_array($decoded['undervoltage_daily'] ?? null) ? $decoded['undervoltage_daily'] : [];

        $undervoltageTotal = 0;
        foreach ($dailyBuckets as $bucket) {
            if (is_array($bucket) && isset($bucket['count']) && is_int($bucket['count'])) {
                $undervoltageTotal += $bucket['count'];
            }
        }

        return [
            'available' => true,
            'boot_count' => count($bootEvents),
            'boot_events_recent' => $bootEvents,
            'last_boot_at' => $bootEvents !== [] ? max($bootEvents) : null,
            'undervoltage_events_total' => $undervoltageTotal,
            'undervoltage_events_recent' => $dailyBuckets,
            'history_started_at' => isset($decoded['history_started_at']) ? (int) $decoded['history_started_at'] : null,
            'updated_at' => isset($decoded['updated_at']) ? (int) $decoded['updated_at'] : null,
        ];
    }
}

if (!function_exists('piratebox_get_device_memory')) {
    /**
     * `available` is false if the file doesn't exist yet (the deployed
     * status_helper.sh hasn't been updated to write it - same "code
     * shipped, root script not yet installed" situation
     * includes/fieldtools_time.php's RTC status hit once already, see
     * docs/OPERATIONAL-DECISIONS.md) or is malformed.
     *
     * @return array (see piratebox_parse_device_memory())
     */
    function piratebox_get_device_memory(): array
    {
        $raw = @file_get_contents(__DIR__ . '/../data/device-history.json');
        return piratebox_parse_device_memory($raw === false ? null : json_decode($raw, true));
    }
}

// --- "Since last review" (docs/DEVICE-MEMORY-DESIGN.md §3) ---------------
//
// A small, separate, operator-set boundary - NOT part of device-
// history.json (which the root helper owns exclusively; this file is
// operator-set state, written by the admin page, same trust boundary as
// data/travel-mode.json/data/content-profile.json). Only ever holds a
// single timestamp - "the moment the operator last pressed Mark
// Reviewed" - never a log of review sessions.

define('PIRATEBOX_REVIEW_BOUNDARY_FILE', __DIR__ . '/../data/review-boundary.json');

if (!function_exists('piratebox_get_review_boundary')) {
    /** Null = never marked reviewed (not the same as "reviewed at time 0"). */
    function piratebox_get_review_boundary(): ?int
    {
        $raw = @file_get_contents(PIRATEBOX_REVIEW_BOUNDARY_FILE);
        if ($raw === false) return null;
        $decoded = json_decode($raw, true);
        if (!is_array($decoded) || !isset($decoded['last_reviewed_at']) || !is_int($decoded['last_reviewed_at'])) return null;
        return $decoded['last_reviewed_at'];
    }
}

if (!function_exists('piratebox_mark_reviewed')) {
    /** Sets the boundary to right now. Same atomic temp-file-then-rename
     * pattern every other small state file in this project already uses
     * (see includes/travel_mode.php's piratebox_set_travel_mode()). */
    function piratebox_mark_reviewed(): bool
    {
        $tmp = PIRATEBOX_REVIEW_BOUNDARY_FILE . '.tmp.' . getmypid() . '.' . bin2hex(random_bytes(4));
        if (file_put_contents($tmp, json_encode(['last_reviewed_at' => time()], JSON_PRETTY_PRINT)) === false) {
            return false;
        }
        if (!rename($tmp, PIRATEBOX_REVIEW_BOUNDARY_FILE)) {
            @unlink($tmp);
            return false;
        }
        return true;
    }
}

if (!function_exists('piratebox_device_memory_since')) {
    /**
     * Pure, directly testable - takes an already-parsed device-memory
     * array (piratebox_parse_device_memory()'s output, using its raw
     * boot_events_recent/undervoltage_events_recent fields) and a
     * boundary timestamp (or null for "never reviewed - show everything
     * on record"), returns only what happened at/after that boundary.
     * No filesystem access, so every boundary case (no boundary set, a
     * boundary in the future, one exactly matching an event, an empty
     * history) is unit-testable directly.
     *
     * @return array{boots_since:?int, undervoltage_events_since:?int}
     *   null fields mean "device memory itself isn't available" (see
     *   piratebox_parse_device_memory()) - never a fabricated zero,
     *   same distinction as everywhere else in this module. A daily
     *   undervoltage bucket counts if its day started at/after the
     *   boundary - a bucket straddling the exact boundary moment may
     *   slightly over-count that one day, an accepted imprecision given
     *   the source data is only daily-grained to begin with (see
     *   docs/DEVICE-MEMORY-DESIGN.md §6 on daily granularity being
     *   "plenty" for this purpose).
     */
    function piratebox_device_memory_since(array $deviceMemory, ?int $boundary): array
    {
        if (empty($deviceMemory['available'])) {
            return ['boots_since' => null, 'undervoltage_events_since' => null];
        }
        $since = $boundary ?? 0; // no boundary set yet = everything on record counts

        $bootEvents = is_array($deviceMemory['boot_events_recent'] ?? null) ? $deviceMemory['boot_events_recent'] : [];
        $bootsSince = count(array_filter($bootEvents, fn($t) => is_int($t) && $t >= $since));

        $dailyBuckets = is_array($deviceMemory['undervoltage_events_recent'] ?? null) ? $deviceMemory['undervoltage_events_recent'] : [];
        $undervoltageSince = 0;
        foreach ($dailyBuckets as $bucket) {
            if (is_array($bucket) && ($bucket['day_start'] ?? -1) >= $since && isset($bucket['count']) && is_int($bucket['count'])) {
                $undervoltageSince += $bucket['count'];
            }
        }

        return ['boots_since' => $bootsSince, 'undervoltage_events_since' => $undervoltageSince];
    }
}
