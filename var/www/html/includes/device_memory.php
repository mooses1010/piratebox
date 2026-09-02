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
            'last_boot_at' => null,
            'undervoltage_events_total' => null,
            'undervoltage_events_recent' => null,
            'history_started_at' => null,
            'updated_at' => null,
        ];

        if (!is_array($decoded)) return $unavailable;

        $bootEvents = is_array($decoded['boot_events'] ?? null) ? $decoded['boot_events'] : [];
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
            'last_boot_at' => $bootEvents !== [] ? (int) max($bootEvents) : null,
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
