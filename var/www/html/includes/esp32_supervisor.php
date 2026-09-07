<?php

declare(strict_types=1);

// ESP32-S3 hardware/sensor supervisor status (2026-09-07) - read by
// /utility/environment/ alongside includes/sensors.php's own Ambient
// Light section. Its OWN export file, OWN topic, following the exact
// precedent that file's header already documents: a new hardware
// topic gets its own narrow export written by the ONE process that
// actually owns that hardware, rather than being folded into an
// existing file. Here that process is piratebox_esp32_supervisor.py
// (a separate long-running daemon, not the OLED daemon - see that
// script's own header for why), writing
// /run/piratebox-esp32/esp32-public.json.
//
// CONSUMER, NOT TRANSPORT: this file never opens a serial port or
// knows anything about baud rates/protocol versions/framing - it only
// ever reads the already-parsed JSON export sitting on tmpfs.
//
// SAME "honest missing value, never fabricated" discipline as every
// other live-status reader in this app: a missing/stale/malformed
// export degrades to "not connected," never a fabricated reading.
// Same two-function split as includes/sensors.php (fetch+decode vs.
// interpret-an-already-fetched-shape) specifically so tests can inject
// a decoded export without touching the filesystem - see
// tools/test_esp32_supervisor_web.php.

if (!defined('PIRATEBOX_ESP32_PUBLIC_FILE')) {
    define('PIRATEBOX_ESP32_PUBLIC_FILE', '/run/piratebox-esp32/esp32-public.json');
}
if (!defined('PIRATEBOX_ESP32_STALE_AFTER')) {
    // piratebox_esp32_supervisor.py publishes at most every ~5s
    // (EXPORT_PUBLISH_INTERVAL_S) - allow a generous number of missed
    // cycles before treating the EXPORT ITSELF as stale (the daemon
    // has stopped publishing entirely), distinct from the export's own
    // "stale" flag inside it (daemon running, but the board's own
    // heartbeat has gone quiet).
    define('PIRATEBOX_ESP32_STALE_AFTER', 30);
}

if (!function_exists('piratebox_get_esp32_public')) {
    /**
     * @return array{data: array<string, mixed>, stale: bool}
     */
    function piratebox_get_esp32_public(): array
    {
        $raw = @file_get_contents(PIRATEBOX_ESP32_PUBLIC_FILE);
        if ($raw === false) {
            return ['data' => [], 'stale' => true];
        }
        $decoded = json_decode($raw, true);
        if (!is_array($decoded)) {
            return ['data' => [], 'stale' => true];
        }
        $age = time() - (int) ($decoded['generated_at'] ?? 0);
        return ['data' => $decoded, 'stale' => $age > PIRATEBOX_ESP32_STALE_AFTER];
    }
}

if (!function_exists('piratebox_get_esp32_supervisor_status')) {
    /**
     * @param ?array{data: array<string, mixed>, stale: bool} $export
     *   Injectable for tests (the exact shape piratebox_get_esp32_public()
     *   returns) - production callers always omit this and get the real
     *   live export.
     * @return array{
     *   installed: bool, available: bool, stale_export: bool,
     *   connected: bool, stale: bool, fw_version: ?string,
     *   board: ?string, reset_reason: ?string, uptime_seconds: ?float,
     *   reboot_count: ?int, temp_internal_c: ?float
     * }
     *   `installed` - true the instant the export file exists AND
     *     decodes at all (the daemon has run at least once) - this
     *     governs whether any Hardware Supervisor UI section appears;
     *     a supervisor never installed/running stays entirely absent,
     *     never a permanent "unavailable" placeholder.
     *   `available` - true only when there is a CURRENT, connected,
     *     non-stale link to show right now.
     */
    function piratebox_get_esp32_supervisor_status(?array $export = null): array
    {
        $export = $export ?? piratebox_get_esp32_public();
        $decoded = $export['data'];
        $staleExport = $export['stale'];

        if ($decoded === []) {
            return [
                'installed' => false, 'available' => false, 'stale_export' => true,
                'connected' => false, 'stale' => true, 'fw_version' => null,
                'board' => null, 'reset_reason' => null, 'uptime_seconds' => null,
                'reboot_count' => null, 'temp_internal_c' => null,
            ];
        }

        $connected = ($decoded['connected'] ?? false) === true && !$staleExport;
        $stale = (bool) ($decoded['stale'] ?? true) || $staleExport;

        $sensors = is_array($decoded['sensors'] ?? null) ? $decoded['sensors'] : [];
        $tempBlock = $sensors['temp_internal'] ?? null;
        $tempC = (is_array($tempBlock) && ($tempBlock['ok'] ?? false) === true && is_numeric($tempBlock['value'] ?? null))
            ? (float) $tempBlock['value']
            : null;

        $uptimeMs = $decoded['uptime_ms'] ?? null;

        return [
            'installed' => true,
            'available' => $connected && !$stale,
            'stale_export' => $staleExport,
            'connected' => $connected,
            'stale' => $stale,
            'fw_version' => is_string($decoded['fw_version'] ?? null) ? $decoded['fw_version'] : null,
            'board' => is_string($decoded['board'] ?? null) ? $decoded['board'] : null,
            'reset_reason' => is_string($decoded['reset_reason'] ?? null) ? $decoded['reset_reason'] : null,
            'uptime_seconds' => is_numeric($uptimeMs) ? round(((float) $uptimeMs) / 1000.0, 1) : null,
            'reboot_count' => is_int($decoded['reboot_count'] ?? null) ? $decoded['reboot_count'] : null,
            'temp_internal_c' => $tempC,
        ];
    }
}
