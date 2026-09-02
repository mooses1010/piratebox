<?php

declare(strict_types=1);

// PirateBox capability/self-awareness state model (docs/ARCHITECTURE.md
// §6/§10/§11 moved from principle to implementation).
//
// ONE tested, reusable function that answers "what is PirateBox, what
// does it have, what's working, what's degraded, what's absent" -
// consumed by /utility/about/ (public-safe summary) and admin/index.php
// (operator-level detail), so neither page re-derives this logic. This
// is the smallest durable model that represents current reality, per
// instruction - it does NOT invent a generic plugin/device-discovery
// framework, does NOT poll hardware directly (everything here reads
// through the exact same channels every other page in this app already
// uses - includes/metrics.php's piratebox_get_helper_status() for
// anything requiring root, includes/fieldtools_time.php for time-source
// state - never a new direct filesystem/hardware read, so this file
// inherits no new open_basedir exposure).
//
// STATE VOCABULARY (docs/ARCHITECTURE.md §10's "prefer honest UNKNOWN
// over a fabricated healthy state", applied consistently here):
//   NOT_INSTALLED - hardware/feature does not exist on this device.
//   AVAILABLE     - present and working normally.
//   DEGRADED      - present, but reporting a real problem.
//   UNAVAILABLE   - should be reporting but currently isn't (e.g. the
//                   status helper snapshot is stale or missing a field).
//   UNKNOWN       - not enough information to say anything else.
// A capability entry may also carry `stale` (bool) when its data source
// is time-bounded - distinguishing "no data" from "old data" per
// docs/ARCHITECTURE.md §10 ("TIME TRUSTED is not equivalent to NO RTC
// DETECTED" - the same discipline generalized here).
//
// LAYER: 'core' | 'operational' | 'optional' - docs/ARCHITECTURE.md §2.
// Every entry also carries `core_dependency` (bool) - whether Core
// actually depends on this capability (should be false for everything
// except the three real Core entries below - see §2's governing rule).

require_once __DIR__ . '/metrics.php';
require_once __DIR__ . '/fieldtools_time.php';
require_once __DIR__ . '/mode.php';
require_once __DIR__ . '/travel_mode.php';
require_once __DIR__ . '/device_id.php';

if (!function_exists('piratebox_classify_service_pair')) {
    /**
     * Pure, directly testable classification - no filesystem/global
     * state - deliberately factored out of piratebox_get_capability_
     * state() so its decision logic can be unit-tested without faking
     * /run/piratebox/status.json. "Both services active" -> AVAILABLE,
     * "helper has no fresh data at all" -> UNKNOWN (never a guessed
     * healthy state), anything else observed -> DEGRADED.
     */
    function piratebox_classify_service_pair(bool $helperAvailable, ?bool $svc1, ?bool $svc2): string
    {
        if (!$helperAvailable) return 'UNKNOWN';
        if ($svc1 === true && $svc2 === true) return 'AVAILABLE';
        return 'DEGRADED';
    }
}

if (!function_exists('piratebox_classify_power')) {
    /** Pure, directly testable - see piratebox_classify_service_pair(). */
    function piratebox_classify_power(bool $helperAvailable, ?bool $undervoltageNow): string
    {
        if (!$helperAvailable) return 'UNAVAILABLE';
        return $undervoltageNow === true ? 'DEGRADED' : 'AVAILABLE';
    }
}

if (!function_exists('piratebox_classify_rtc')) {
    /** Pure, directly testable - see piratebox_classify_service_pair(). */
    function piratebox_classify_rtc(bool $timeSourceAvailable, ?bool $rtcDetected): string
    {
        if (!$timeSourceAvailable) return 'UNKNOWN';
        return $rtcDetected === true ? 'AVAILABLE' : 'NOT_INSTALLED';
    }
}

if (!function_exists('piratebox_default_provider')) {
    /**
     * CAPABILITY and PROVIDER are distinct concepts (see docs/
     * ARCHITECTURE.md's expanded self-awareness section): a capability
     * is "what can be done," a provider is "what currently provides
     * it." Today every real capability on this device has exactly one
     * possible provider - PirateBox's own integrated hardware/software -
     * so this is deliberately a single default, not a list. It exists
     * so a future companion-device provider (docs/ARCHITECTURE.md §3's
     * Integrated/Attachable/Network Companion/Operator Device classes)
     * has a field to occupy without restructuring this array later -
     * the smallest change that keeps that door open, not a multi-
     * provider registry built ahead of an actual second provider.
     *
     * Pure, directly testable - see piratebox_classify_service_pair().
     *
     * @return array{0: ?string, 1: ?string} [provider label, provider class]
     */
    function piratebox_default_provider(string $state): array
    {
        if (in_array($state, ['NOT_INSTALLED', 'UNKNOWN'], true)) {
            return [null, null]; // nothing is providing this right now - say so, don't guess
        }
        return ['PirateBox (this device)', 'integrated'];
    }
}

if (!function_exists('piratebox_get_capability_state')) {
    /**
     * @return array<string, array{
     *   layer: string, state: string, label: string,
     *   core_dependency: bool, stale?: bool, detail?: array,
     *   provider: ?string, provider_class: ?string
     * }>
     */
    function piratebox_get_capability_state(): array
    {
        $helper = piratebox_get_helper_status();
        $status = $helper['status'];
        $helperStale = $helper['stale'];
        $helperAvailable = $status !== null && !$helperStale;

        $capabilities = [];

        // --- Core ---------------------------------------------------------

        $capabilities['ap_network'] = [
            'layer' => 'core',
            'core_dependency' => true,
            'label' => 'Wi-Fi access point',
            'state' => piratebox_classify_service_pair($helperAvailable, $status['services']['hostapd'] ?? null, $status['services']['dnsmasq'] ?? null),
            'stale' => $helperStale,
            'detail' => ['wifi_clients' => $helperAvailable ? ($status['wifi_clients'] ?? null) : null],
        ];

        $capabilities['web_app'] = [
            'layer' => 'core',
            'core_dependency' => true,
            'label' => 'Web application (files/chat/community)',
            'state' => piratebox_classify_service_pair($helperAvailable, $status['services']['nginx'] ?? null, $status['services']['php8.4-fpm'] ?? null),
            'stale' => $helperStale,
        ];

        // NOTE: this file lives in includes/ (one level below var/www/html/),
        // not public/admin/ or public/utility/status/ (two/three levels
        // below) - only one '..' is needed to reach the webroot, which is
        // the actual open_basedir boundary (etc/php/8.4/fpm/php.ini). An
        // extra '..' here would resolve one directory too high and be
        // silently blocked - found live, not assumed; see docs/
        // OPERATIONAL-DECISIONS.md for the class of bug this matches.
        $diskTotal = @disk_total_space(__DIR__ . '/..');
        $diskFree = @disk_free_space(__DIR__ . '/..');
        $capabilities['storage'] = [
            'layer' => 'core',
            'core_dependency' => true,
            'label' => 'Storage',
            'state' => ($diskTotal !== false && $diskFree !== false) ? 'AVAILABLE' : 'UNKNOWN',
            'detail' => [
                'free_bytes' => $diskFree !== false ? (int) $diskFree : null,
                'total_bytes' => $diskTotal !== false ? (int) $diskTotal : null,
            ],
        ];

        // --- Operational ----------------------------------------------------

        $capabilities['status_helper'] = [
            'layer' => 'operational',
            'core_dependency' => false,
            'label' => 'Status helper (health/power telemetry source)',
            'state' => $helperAvailable ? 'AVAILABLE' : 'UNAVAILABLE',
            'stale' => $helperStale,
        ];

        // Power/undervoltage: only meaningful if the helper itself is
        // fresh - a stale/missing helper means this is UNAVAILABLE, not
        // a guessed "good."
        $undervoltNow = ($helperAvailable && isset($status['power']['undervoltage_now']))
            ? (bool) $status['power']['undervoltage_now'] : null;
        $capabilities['power_monitoring'] = [
            'layer' => 'operational',
            'core_dependency' => false,
            'label' => 'Power-quality monitoring',
            'state' => piratebox_classify_power($helperAvailable, $undervoltNow),
            'stale' => $helperStale,
            'detail' => $helperAvailable ? [
                'undervoltage_now' => $undervoltNow,
                'undervoltage_since_boot' => (bool) ($status['power']['undervoltage_since_boot'] ?? false),
                'throttled_hex' => $status['power']['throttled_hex'] ?? null,
            ] : null,
        ];

        $timeSource = piratebox_get_time_source_status();
        $capabilities['time_confidence'] = [
            'layer' => 'operational',
            'core_dependency' => false,
            'label' => 'Time confidence',
            'state' => !$timeSource['available'] ? 'UNKNOWN'
                : ($timeSource['rtc_detected'] ? 'AVAILABLE' : 'DEGRADED'),
            'stale' => $timeSource['stale'],
            'detail' => $timeSource,
        ];

        $capabilities['rtc'] = [
            'layer' => 'operational',
            'core_dependency' => false,
            'label' => 'Hardware real-time clock (RTC)',
            // Distinct from time_confidence above: this specifically
            // answers "is the hardware there," not "how much should I
            // trust the clock right now" - see docs/ARCHITECTURE.md §11
            // (observed fact vs. derived confidence are different facts).
            'state' => piratebox_classify_rtc($timeSource['available'], $timeSource['rtc_detected']),
            'stale' => $timeSource['stale'],
        ];

        $capabilities['connection_stats'] = [
            'layer' => 'operational',
            'core_dependency' => false,
            'label' => 'Connection statistics (aggregate, privacy-preserving)',
            'state' => $helperAvailable ? 'AVAILABLE' : 'UNAVAILABLE',
            'stale' => $helperStale,
        ];

        $capabilities['shutdown_button'] = [
            'layer' => 'core', // safety primitive - docs/ARCHITECTURE.md §2
            'core_dependency' => true,
            'label' => 'Physical shutdown button (GPIO25)',
            // No live health channel exists yet for this daemon (see
            // docs/CAPABILITY-REGISTRY.md's own note) - reporting
            // "installed" as a documented architectural fact is honest;
            // reporting "active" would require a status_helper.sh change
            // not made here. AVAILABLE here means "known installed,"
            // not "confirmed running this instant."
            'state' => 'AVAILABLE',
            'detail' => ['live_health_check' => 'not yet implemented - see docs/CAPABILITY-REGISTRY.md'],
        ];

        $capabilities['oled'] = [
            'layer' => 'operational',
            'core_dependency' => false,
            'label' => 'OLED display',
            'state' => 'NOT_INSTALLED',
        ];

        $capabilities['toggle_switch'] = [
            'layer' => 'operational',
            'core_dependency' => false,
            'label' => 'Normal/Emergency toggle switch',
            'state' => 'NOT_INSTALLED',
            'detail' => ['fallback' => 'software toggle (set_piratebox_mode.sh) fully functional'],
        ];

        // Transport lock (docs/PHYSICAL-CONTROL-UX-DESIGN.md §4.2) -
        // design-only, no lock hardware/mechanism exists. Honest
        // NOT_INSTALLED, not a fabricated ENABLED/LOCKED state - see
        // that section's own state vocabulary (this module reuses its
        // existing NOT_INSTALLED rather than adding LOCKED/DEGRADED/
        // INPUT_FAULT states with no real data source behind them yet).
        $capabilities['transport_lock'] = [
            'layer' => 'operational',
            'core_dependency' => false,
            'label' => 'Physical transport lock',
            'state' => 'NOT_INSTALLED',
            'detail' => ['note' => 'design-only concept - see docs/PHYSICAL-CONTROL-UX-DESIGN.md §4.2'],
        ];

        // --- Optional / Field -------------------------------------------

        // Nothing installed today - see docs/CAPABILITY-REGISTRY.md for
        // the full candidate list. Deliberately not enumerated one by
        // one here (that list belongs in the registry, not duplicated in
        // code) - a single honest summary entry instead.
        $capabilities['optional_field_capabilities'] = [
            'layer' => 'optional',
            'core_dependency' => false,
            'label' => 'Optional/field capabilities (GNSS, environmental, SDR, companions, ...)',
            'state' => 'NOT_INSTALLED',
            'detail' => ['note' => 'see docs/CAPABILITY-REGISTRY.md for candidates - none installed'],
        ];

        // Attach provider/provider_class uniformly (see
        // piratebox_default_provider()'s own header) rather than
        // repeating the same two fields in all 13 entries above.
        foreach ($capabilities as $id => $c) {
            [$provider, $providerClass] = piratebox_default_provider($c['state']);
            $capabilities[$id]['provider'] = $provider;
            $capabilities[$id]['provider_class'] = $providerClass;
        }

        return $capabilities;
    }
}

if (!function_exists('piratebox_get_operational_state')) {
    /**
     * The complementary "what am I doing / what am I exposing" facts -
     * docs/ARCHITECTURE.md §10's distinct question from "what do I
     * have" (piratebox_get_capability_state() above). Kept separate on
     * purpose: mode/Travel Mode/device identity are current-operation
     * facts, not hardware/software capability facts.
     *
     * @return array{mode:string, travel_mode:bool, device_id:?string,
     *   uptime_seconds:?float}
     */
    function piratebox_get_operational_state(): array
    {
        return [
            'mode' => piratebox_get_mode(),
            'travel_mode' => piratebox_get_travel_mode(),
            'device_id' => piratebox_get_device_id(),
            'uptime_seconds' => piratebox_get_uptime_seconds(),
        ];
    }
}

if (!function_exists('piratebox_capability_summary_counts')) {
    /** Small rollup used by the public About page - counts only, no detail. */
    function piratebox_capability_summary_counts(array $capabilities): array
    {
        $counts = ['AVAILABLE' => 0, 'DEGRADED' => 0, 'UNAVAILABLE' => 0, 'NOT_INSTALLED' => 0, 'UNKNOWN' => 0];
        foreach ($capabilities as $c) {
            $counts[$c['state']] = ($counts[$c['state']] ?? 0) + 1;
        }
        return $counts;
    }
}
