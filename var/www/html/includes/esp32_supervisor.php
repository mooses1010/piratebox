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

// --- Shared sensor-health classification (2026-09-08, hardware-
// awareness phase) -------------------------------------------------
//
// Mirrors piratebox_hardware_health.py's Python vocabulary verbatim
// (see that module's own header for the canonical definitions) so an
// operator reading the admin capability table and a Python diagnostic
// never has to learn two different words for the same idea:
//   NOT_INSTALLED / AVAILABLE / DEGRADED / UNAVAILABLE / UNKNOWN
// This is SENSOR HEALTH only ("can I trust this reading right now") -
// it has no concept of physical role/policy, on purpose - see
// piratebox_ds18b20_roles.py's header for why that distinction matters
// and stays deferred until real roles exist.

if (!function_exists('piratebox_classify_esp32_link')) {
    /**
     * @param array{installed: bool, connected: bool, stale: bool} $status
     *   The shape piratebox_get_esp32_supervisor_status() already returns.
     */
    function piratebox_classify_esp32_link(array $status): string
    {
        if (!$status['installed']) {
            // No export has ever been read successfully - not enough
            // information to say "not installed" (an architectural
            // fact) vs. "hasn't published yet" - honest UNKNOWN.
            return 'UNKNOWN';
        }
        if ($status['connected'] && !$status['stale']) {
            return 'AVAILABLE';
        }
        if ($status['connected'] && $status['stale']) {
            return 'DEGRADED';
        }
        return 'UNAVAILABLE';
    }
}

if (!function_exists('piratebox_classify_simple_sensor')) {
    /**
     * For a sensor whose export shape is one flat {ok, value, unit}
     * dict directly under sensors[$capability] - covers temp_internal
     * and bh1750 today.
     *
     * @param array{installed: bool, connected: bool, stale: bool} $status
     * @param array<string, mixed> $decoded Full decoded export (for
     *   'capabilities' and 'sensors').
     */
    function piratebox_classify_simple_sensor(array $status, array $decoded, string $capability): string
    {
        $linkState = piratebox_classify_esp32_link($status);
        if ($linkState !== 'AVAILABLE') {
            return $linkState;
        }
        $capabilities = is_array($decoded['capabilities'] ?? null) ? $decoded['capabilities'] : [];
        if (!in_array($capability, $capabilities, true)) {
            return 'NOT_INSTALLED';
        }
        $sensors = is_array($decoded['sensors'] ?? null) ? $decoded['sensors'] : [];
        $reading = $sensors[$capability] ?? null;
        if (!is_array($reading)) {
            return 'UNKNOWN';
        }
        return ($reading['ok'] ?? false) === true ? 'AVAILABLE' : 'DEGRADED';
    }
}

if (!function_exists('piratebox_classify_ds18b20_bus')) {
    /**
     * The 1-Wire bus as a whole. Reads the export's own top-level
     * "commissioned" map (piratebox_esp32_supervisor.py's
     * _enrich_ds18b20_with_names()) rather than the roles file
     * directly - this file follows this project's "one process owns
     * the hardware, everything else reads its cache" discipline, and
     * the supervisor daemon already merges commissioning identity into
     * its own export for exactly this reason.
     *
     * @param array{installed: bool, connected: bool, stale: bool} $status
     * @param array<string, mixed> $decoded Full decoded export.
     * @return array{state: string, bus_ok: ?bool, probes_ok: int, probes_expected: int, missing_commissioned: list<string>, failing_commissioned: list<string>}
     */
    function piratebox_classify_ds18b20_bus(array $status, array $decoded): array
    {
        $base = ['bus_ok' => null, 'probes_ok' => 0, 'probes_expected' => 0, 'missing_commissioned' => [], 'failing_commissioned' => []];

        $linkState = piratebox_classify_esp32_link($status);
        if ($linkState !== 'AVAILABLE') {
            return ['state' => $linkState] + $base;
        }

        $capabilities = is_array($decoded['capabilities'] ?? null) ? $decoded['capabilities'] : [];
        $sensors = is_array($decoded['sensors'] ?? null) ? $decoded['sensors'] : [];
        $ds18b20 = is_array($sensors['ds18b20'] ?? null) ? $sensors['ds18b20'] : null;
        $commissioned = ($ds18b20 !== null && is_array($ds18b20['commissioned'] ?? null)) ? $ds18b20['commissioned'] : [];
        $commissionedRoms = array_keys($commissioned);

        if (!in_array('ds18b20', $capabilities, true)) {
            $state = $commissionedRoms !== [] ? 'UNAVAILABLE' : 'NOT_INSTALLED';
            return ['state' => $state] + $base + ['probes_expected' => count($commissionedRoms)];
        }
        if ($ds18b20 === null) {
            return ['state' => 'UNKNOWN'] + $base;
        }

        $busOk = $ds18b20['bus_ok'] ?? null;
        $probes = is_array($ds18b20['probes'] ?? null) ? $ds18b20['probes'] : [];
        $probesOk = 0;
        foreach ($probes as $reading) {
            if (is_array($reading) && ($reading['ok'] ?? false) === true) {
                $probesOk++;
            }
        }
        $missing = [];
        $failing = [];
        foreach ($commissionedRoms as $rom) {
            if (!array_key_exists($rom, $probes)) {
                $missing[] = $rom;
            } elseif (!(is_array($probes[$rom]) && ($probes[$rom]['ok'] ?? false) === true)) {
                $failing[] = $rom;
            }
        }
        sort($missing);
        sort($failing);
        $detail = [
            'bus_ok' => is_bool($busOk) ? $busOk : null,
            'probes_ok' => $probesOk,
            'probes_expected' => count($commissionedRoms),
            'missing_commissioned' => $missing,
            'failing_commissioned' => $failing,
        ];

        if ($busOk === false) {
            return ['state' => 'UNAVAILABLE'] + $detail;
        }
        if ($missing !== [] || $failing !== []) {
            return ['state' => 'DEGRADED'] + $detail;
        }
        if ($commissionedRoms === [] && $probes === []) {
            return ['state' => 'NOT_INSTALLED'] + $detail;
        }
        return ['state' => 'AVAILABLE'] + $detail;
    }
}

if (!function_exists('piratebox_get_ds18b20_probes')) {
    /**
     * DS18B20 probes for the PUBLIC Environment page (2026-09-07,
     * extended 2026-09-08 for the hardware-awareness phase) - ROM
     * addresses themselves NEVER reach this function's return value or
     * this page - engineering detail that belongs in
     * tools/ds18b20_commission.py/admin diagnostics only.
     *
     * Every COMMISSIONED probe (an established, permanent physical
     * identity - see piratebox_ds18b20_roles.py) is shown, whether or
     * not it has been given a cosmetic name yet:
     *   - named:  the operator's own name.
     *   - not yet named: a stable, non-semantic "Probe N" label using
     *     the durable physical_index from the ORIGINAL physical
     *     identification order (warming test) - never raw discovery
     *     order, never the ROM. `has_name` distinguishes the two so a
     *     caller can style/caption them differently if useful.
     * A probe that has never been commissioned at all (no physical_index,
     * no name - e.g. a brand new probe just appeared on the bus) is
     * NOT shown here - it's diagnostic-only information until the
     * operator acknowledges it exists, folded into `uncommissioned_count`
     * instead so the page can honestly say "N more probe(s) detected,
     * not yet set up" without exposing anything about them.
     *
     * @param ?array{data: array<string, mixed>, stale: bool} $export
     * @return array{probes: list<array{label: string, has_name: bool, value_c: ?float, ok: bool}>, uncommissioned_count: int}
     */
    function piratebox_get_ds18b20_probes(?array $export = null): array
    {
        $export = $export ?? piratebox_get_esp32_public();
        $decoded = $export['data'];
        $empty = ['probes' => [], 'uncommissioned_count' => 0];

        if ($decoded === [] || $export['stale']) {
            return $empty;
        }
        $connected = ($decoded['connected'] ?? false) === true;
        $linkStale = (bool) ($decoded['stale'] ?? true);
        if (!$connected || $linkStale) {
            return $empty;
        }

        $sensors = is_array($decoded['sensors'] ?? null) ? $decoded['sensors'] : [];
        $ds18b20 = is_array($sensors['ds18b20'] ?? null) ? $sensors['ds18b20'] : null;
        if ($ds18b20 === null) {
            return $empty;  // this firmware/board has never found a DS18B20 probe
        }
        $readings = is_array($ds18b20['probes'] ?? null) ? $ds18b20['probes'] : [];

        $display = [];
        $uncommissionedCount = 0;
        foreach ($readings as $rom => $reading) {
            if (!is_string($rom) || !is_array($reading)) {
                continue;
            }
            $name = is_string($reading['name'] ?? null) ? trim($reading['name']) : '';
            $physicalIndex = is_int($reading['physical_index'] ?? null) ? $reading['physical_index'] : null;
            if ($name === '' && $physicalIndex === null) {
                $uncommissionedCount++;
                continue;  // never commissioned - engineering detail only, not shown to visitors
            }
            $label = $name !== '' ? $name : "Probe {$physicalIndex}";
            $ok = ($reading['ok'] ?? false) === true;
            $value = ($ok && is_numeric($reading['value'] ?? null)) ? (float) $reading['value'] : null;
            $display[] = [
                'label' => $label,
                'has_name' => $name !== '',
                'value_c' => $value,
                'ok' => $ok && $value !== null,
                'sort_key' => $name !== '' ? "0:{$name}" : sprintf('1:%05d', $physicalIndex ?? 0),
            ];
        }
        // Deterministic display order: named probes alphabetically
        // first, then unnamed-but-commissioned probes by physical
        // index - dict iteration order is an implementation detail of
        // however the firmware/daemon happened to walk the bus this
        // cycle, never something to show visitors.
        usort($display, fn($a, $b) => strcmp($a['sort_key'], $b['sort_key']));
        foreach ($display as &$item) {
            unset($item['sort_key']);
        }
        unset($item);

        return ['probes' => $display, 'uncommissioned_count' => $uncommissionedCount];
    }
}
