<?php

declare(strict_types=1);

// Sensor-history query/catalog layer (2026-09-08) - the read side of
// piratebox_history.py's bounded, lightweight time-series store. This
// file NEVER writes history (only piratebox_history_sampler.py does,
// running as piratebox-gpio via its own systemd timer) and NEVER
// touches I2C/1-Wire/serial - it only reads the same durable per-signal
// JSON files that sampler already wrote to /var/lib/piratebox-history/
// (world-readable by design - see that directory's own systemd unit
// comment for why).
//
// IDENTITY vs. LABEL: exactly the same split piratebox_history.py's own
// header describes. Stored signal ids are permanent
// ("ambient_lux", "esp32_temp_internal", "ds18b20_<romhex>"). Public
// callers of this file NEVER see a ROM address - piratebox_history_
// probe_slug_map() below is the ONLY bridge between the two, mapping a
// public, non-semantic slug ("probe_1".."probe_N", from the SAME
// physical_index the live Environment page already uses - see
// piratebox_ds18b20_roles.py) to its internal ROM-keyed signal id. A
// future rename only ever changes the LABEL this map returns, never
// the slug or the underlying stored identity - existing graphs relabel
// themselves automatically on the next page load, with no history
// migration of any kind.
//
// CAPABILITY-DRIVEN: a graph group is only ever listed by piratebox_
// history_catalog() if the underlying capability currently exists
// (install_state !== 'NOT_INSTALLED') - matching this project's
// existing "never invent a category for hardware that isn't
// commissioned yet" discipline (includes/sensors.php,
// includes/esp32_supervisor.php).

require_once __DIR__ . '/esp32_supervisor.php';

if (!defined('PIRATEBOX_HISTORY_DIR')) {
    define('PIRATEBOX_HISTORY_DIR', '/var/lib/piratebox-history');
}

// Mirrors piratebox_history.py's own retention constants exactly - see
// that module's header for the full reasoning. Duplicated rather than
// shared across languages (there is no cross-language shared-constants
// mechanism in this project), but both sides are small and unlikely to
// drift silently since a mismatch here would show up immediately as
// wrong tier selection on the Environment page.
if (!defined('PIRATEBOX_HISTORY_RAW_RETENTION')) {
    define('PIRATEBOX_HISTORY_RAW_RETENTION', 7 * 86400);
}
if (!defined('PIRATEBOX_HISTORY_HOURLY_RETENTION')) {
    define('PIRATEBOX_HISTORY_HOURLY_RETENTION', 90 * 86400);
}

// Supported UI time ranges, in seconds - the ONLY values the history
// endpoint accepts (see environment/index.php's ?history=1 handler).
// Keeping this a fixed, small allowlist (rather than an arbitrary
// client-supplied number of seconds) is what keeps the query cheap and
// predictable: no request can ask this endpoint to scan an unbounded
// or unusual window.
if (!defined('PIRATEBOX_HISTORY_RANGES')) {
    define('PIRATEBOX_HISTORY_RANGES', [
        '6h' => 6 * 3600,
        '24h' => 24 * 3600,
        '7d' => 7 * 86400,
        '30d' => 30 * 86400,
    ]);
}

if (!function_exists('piratebox_history_is_safe_signal_id')) {
    /**
     * Mirrors piratebox_history.py's _is_safe_signal_id() - a signal id
     * is always server-derived (never taken verbatim from the client;
     * see piratebox_history_probe_slug_map()), but this file never
     * trusts that without checking anyway before using it in a path.
     */
    function piratebox_history_is_safe_signal_id(string $signalId): bool
    {
        return $signalId !== ''
            && strlen($signalId) <= 128
            && preg_match('/^[A-Za-z0-9_-]+$/', $signalId) === 1;
    }
}

if (!function_exists('piratebox_history_read_signal')) {
    /**
     * @param ?string $historyDir Injectable for tests (defaults to the
     *   real PIRATEBOX_HISTORY_DIR) - same "inject the one impure
     *   input" pattern this project already uses for $export params
     *   elsewhere, so tests never have to touch /var/lib for real.
     * @return array{schema_version?: int, raw: list, hourly: list, daily: list}
     */
    function piratebox_history_read_signal(string $signalId, ?string $historyDir = null): array
    {
        $empty = ['raw' => [], 'hourly' => [], 'daily' => []];
        if (!piratebox_history_is_safe_signal_id($signalId)) {
            return $empty;
        }
        $path = ($historyDir ?? PIRATEBOX_HISTORY_DIR) . '/' . $signalId . '.json';
        $raw = @file_get_contents($path);
        if ($raw === false) {
            return $empty;  // no history recorded yet for this signal - not an error
        }
        $decoded = json_decode($raw, true);
        if (!is_array($decoded)) {
            return $empty;
        }
        foreach (['raw', 'hourly', 'daily'] as $tier) {
            $empty[$tier] = is_array($decoded[$tier] ?? null) ? $decoded[$tier] : [];
        }
        return $empty;
    }
}

if (!function_exists('piratebox_history_choose_tier')) {
    function piratebox_history_choose_tier(int $rangeSeconds): string
    {
        if ($rangeSeconds <= PIRATEBOX_HISTORY_RAW_RETENTION) {
            return 'raw';
        }
        if ($rangeSeconds <= PIRATEBOX_HISTORY_HOURLY_RETENTION) {
            return 'hourly';
        }
        return 'daily';
    }
}

if (!function_exists('piratebox_history_query')) {
    /**
     * Returns only the points within the requested window - never the
     * whole stored file. Each point is {t, v} for the raw tier, or
     * {t, min, avg, max} for hourly/daily (avg is what a line chart
     * plots; min/max ride along for a future "band" rendering without
     * a second query).
     *
     * @return array{tier: string, points: list<array<string, float|int>>}
     */
    function piratebox_history_query(string $signalId, int $rangeSeconds, ?int $now = null, ?string $historyDir = null): array
    {
        $now = $now ?? time();
        $tier = piratebox_history_choose_tier($rangeSeconds);
        $history = piratebox_history_read_signal($signalId, $historyDir);
        $entries = is_array($history[$tier] ?? null) ? $history[$tier] : [];
        $startT = $now - $rangeSeconds;

        $points = [];
        foreach ($entries as $e) {
            if (!is_array($e) || !is_numeric($e['t'] ?? null)) {
                continue;
            }
            $t = (int) $e['t'];
            if ($t < $startT || $t > $now) {
                continue;
            }
            if ($tier === 'raw') {
                if (!is_numeric($e['v'] ?? null)) {
                    continue;
                }
                $points[] = ['t' => $t, 'v' => (float) $e['v']];
            } else {
                if (!is_numeric($e['avg'] ?? null)) {
                    continue;
                }
                $points[] = [
                    't' => $t,
                    'v' => (float) $e['avg'],
                    'min' => is_numeric($e['min'] ?? null) ? (float) $e['min'] : null,
                    'max' => is_numeric($e['max'] ?? null) ? (float) $e['max'] : null,
                ];
            }
        }
        usort($points, fn($a, $b) => $a['t'] <=> $b['t']);
        return ['tier' => $tier, 'points' => $points];
    }
}

if (!function_exists('piratebox_history_probe_slug_map')) {
    /**
     * The ONE bridge between a public, non-semantic slug ("probe_1"..)
     * and its permanent internal signal id ("ds18b20_<romhex>") - the
     * ROM itself never leaves this function. Sorted by physical_index
     * (the durable warming-test identification order - never bus
     * discovery order), matching the exact same order the Environment
     * page's live probe cards already use.
     *
     * @param ?array{data: array<string, mixed>, stale: bool} $export Injectable for tests.
     * @return array<string, array{signal_id: string, label: string}> slug => {signal_id, label}
     */
    function piratebox_history_probe_slug_map(?array $export = null): array
    {
        $export = $export ?? piratebox_get_esp32_public();
        $decoded = $export['data'];
        if ($decoded === []) {
            return [];
        }
        $sensors = is_array($decoded['sensors'] ?? null) ? $decoded['sensors'] : [];
        $ds18b20 = is_array($sensors['ds18b20'] ?? null) ? $sensors['ds18b20'] : null;
        $commissioned = ($ds18b20 !== null && is_array($ds18b20['commissioned'] ?? null)) ? $ds18b20['commissioned'] : [];

        $entries = [];
        foreach ($commissioned as $rom => $info) {
            if (!is_string($rom) || !is_array($info)) {
                continue;
            }
            $physicalIndex = is_int($info['physical_index'] ?? null) ? $info['physical_index'] : null;
            if ($physicalIndex === null) {
                continue;  // commissioned but no physical_index recorded - shouldn't happen, skip defensively
            }
            $name = is_string($info['name'] ?? null) ? trim($info['name']) : '';
            $entries[] = [
                'rom' => $rom,
                'physical_index' => $physicalIndex,
                'label' => $name !== '' ? $name : "Probe {$physicalIndex}",
            ];
        }
        usort($entries, fn($a, $b) => $a['physical_index'] <=> $b['physical_index']);

        $map = [];
        foreach ($entries as $e) {
            $slug = "probe_{$e['physical_index']}";
            $map[$slug] = ['signal_id' => "ds18b20_{$e['rom']}", 'label' => $e['label']];
        }
        return $map;
    }
}

if (!function_exists('piratebox_history_catalog')) {
    /**
     * The graph groups the Environment page should render RIGHT NOW -
     * never a fake/empty chart for hardware that doesn't exist. Each
     * group names its own current live-availability state (from the
     * SAME classifiers the admin capability table uses) SEPARATELY
     * from whether historical data exists, per instruction: a sensor
     * that's currently stale/unavailable still gets its historical
     * chart (there may be real past data worth seeing), just with an
     * honest "currently unavailable" note alongside it - never hidden,
     * never faked as currently healthy.
     *
     * @return array{
     *   ambient_light: ?array{signal_id: string, current_state: string},
     *   esp32_temp: ?array{signal_id: string, current_state: string},
     *   probes: array<string, array{signal_id: string, label: string, current_state: string}>
     * }
     */
    function piratebox_history_catalog(?array $export = null): array
    {
        $export = $export ?? piratebox_get_esp32_public();
        $decoded = $export['data'];
        $status = piratebox_get_esp32_supervisor_status($export);

        $catalog = ['ambient_light' => null, 'esp32_temp' => null, 'probes' => []];
        if ($decoded === []) {
            return $catalog;
        }

        $lightState = piratebox_classify_simple_sensor($status, $decoded, 'bh1750');
        if ($lightState !== 'NOT_INSTALLED') {
            $catalog['ambient_light'] = ['signal_id' => 'ambient_lux', 'current_state' => $lightState];
        }

        $tempState = piratebox_classify_simple_sensor($status, $decoded, 'temp_internal');
        if ($tempState !== 'NOT_INSTALLED') {
            $catalog['esp32_temp'] = ['signal_id' => 'esp32_temp_internal', 'current_state' => $tempState];
        }

        $linkState = piratebox_classify_esp32_link($status);
        $sensors = is_array($decoded['sensors'] ?? null) ? $decoded['sensors'] : [];
        $ds18b20Block = is_array($sensors['ds18b20'] ?? null) ? $sensors['ds18b20'] : [];
        $probes = is_array($ds18b20Block['probes'] ?? null) ? $ds18b20Block['probes'] : [];
        foreach (piratebox_history_probe_slug_map($export) as $slug => $entry) {
            if ($linkState !== 'AVAILABLE') {
                // The link itself has a problem - every probe inherits
                // that, same as piratebox_classify_ds18b20_bus() does,
                // rather than each one separately (and misleadingly)
                // reporting DEGRADED for what is actually a link outage.
                $currentState = $linkState;
            } else {
                $rom = substr($entry['signal_id'], strlen('ds18b20_'));
                $reading = $probes[$rom] ?? null;
                $currentState = (is_array($reading) && ($reading['ok'] ?? false) === true) ? 'AVAILABLE' : 'DEGRADED';
            }
            $catalog['probes'][$slug] = [
                'signal_id' => $entry['signal_id'],
                'label' => $entry['label'],
                'current_state' => $currentState,
            ];
        }

        return $catalog;
    }
}
