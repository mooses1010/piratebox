<?php
declare(strict_types=1);
session_start();
require_once __DIR__ . '/../../../includes/sensors.php';
require_once __DIR__ . '/../../../includes/esp32_supervisor.php';
require_once __DIR__ . '/../../../includes/history.php';
require_once __DIR__ . '/../../../includes/temp_unit.php';

// Environment - live readings from PirateBox's onboard sensors
// (2026-09-07). First real sensor: BH1750 ambient light. Designed to
// grow: a future commissioned sensor (BME280 temperature/humidity/
// pressure, DS18B20 probes, INA226 power telemetry, or something
// behind a future ESP32-S3 supervisor) gets its OWN reading function
// in includes/sensors.php and its OWN conditionally-rendered section
// below, following the exact same pattern as Ambient Light - never
// rendered until its own hardware signal actually exists in the
// export. Nothing here invents a category for hardware that isn't
// commissioned yet.
//
// CONSUMER, NOT TRANSPORT: this page only ever reads includes/
// sensors.php's already-parsed export - no I2C, no direct hardware
// access, no knowledge of bus numbers or protocols anywhere in this
// file. If a sensor ever moves behind an ESP32-S3 supervisor, only the
// export producer (piratebox_oled_daemon.py) needs to change - this
// page and includes/sensors.php stay exactly as they are.
//
// REFRESH: a tiny same-origin ?fetch=1 JSON endpoint (this same file),
// polled every 30s by the small inline script at the bottom - the
// same established pattern chat.php/messages.php/bulletin.php already
// use elsewhere on this site. This only ever re-reads the cached
// export file already sitting on tmpfs; it never triggers a new I2C
// transaction, and browsing with N tabs open polls the same cheap file
// read N times, never the hardware more than once per the daemon's own
// ~20s publish interval regardless of visitor count.

$ambientLight = piratebox_get_ambient_light_reading();
$esp32 = piratebox_get_esp32_supervisor_status();
$ds18b20 = piratebox_get_ds18b20_probes();
$historyCatalog = piratebox_history_catalog();
// Temperature display-unit preference (2026-09-08) - purely a
// presentation choice, applied here at the render boundary only; the
// export/cache/history this page reads from stays Celsius regardless
// (see includes/temp_unit.php's own header for the full rationale).
$tempUnit = piratebox_get_temp_unit();
$tempUnitSymbol = piratebox_temp_unit_symbol($tempUnit);
// A plain Unicode form for JSON payloads - piratebox_temp_unit_symbol()
// returns an HTML entity (&deg;...), correct when echoed directly into
// this page's own markup but wrong inside JSON/JS, where it would show
// up as the literal text "&deg;C" instead of being entity-decoded (JSON
// isn't HTML - nothing decodes entities in a fetch() response).
$tempUnitSymbolRaw = $tempUnit === 'F' ? '°F' : '°C';

// Narrow, range/query-selection history endpoint (2026-09-08) - never
// dumps the whole stored file, only the points inside the requested
// window at whatever tier fits it (see piratebox_history_query()).
// `group` is one of a small fixed set (never a raw signal id from the
// client - see piratebox_history_probe_slug_map() for the one place a
// ROM address ever gets involved, entirely server-side) so a request
// can only ever ask for a chart this page would legitimately draw.
if (($_GET['history'] ?? '') === '1') {
    header('Content-Type: application/json');
    $group = is_string($_GET['group'] ?? null) ? $_GET['group'] : '';
    $rangeKey = is_string($_GET['range'] ?? null) ? $_GET['range'] : '24h';
    $rangeSeconds = PIRATEBOX_HISTORY_RANGES[$rangeKey] ?? null;
    if ($rangeSeconds === null) {
        http_response_code(400);
        echo json_encode(['error' => 'invalid range']);
        exit;
    }

    // Converts every numeric field (v, min, max) of every point in
    // place - the ONE place history query results get converted for
    // display, right before they leave this endpoint. The stored
    // history file itself is never touched (piratebox_history_query()
    // only ever reads it) - a unit switch changes what this endpoint
    // returns on the next request, never what's on disk.
    $convertPoints = function (array $points) use ($tempUnit): array {
        foreach ($points as &$p) {
            foreach (['v', 'min', 'max'] as $key) {
                if (isset($p[$key])) {
                    $p[$key] = piratebox_convert_temp_c((float) $p[$key], $tempUnit);
                }
            }
        }
        unset($p);
        return $points;
    };

    $series = [];
    if ($group === 'ambient_light' && $historyCatalog['ambient_light'] !== null) {
        // Lux, not temperature - never passed through the converter above.
        $q = piratebox_history_query($historyCatalog['ambient_light']['signal_id'], $rangeSeconds);
        $series[] = ['label' => 'Ambient light', 'points' => $q['points']];
    } elseif ($group === 'esp32_temp' && $historyCatalog['esp32_temp'] !== null) {
        $q = piratebox_history_query($historyCatalog['esp32_temp']['signal_id'], $rangeSeconds);
        $series[] = ['label' => 'ESP32 chip', 'points' => $convertPoints($q['points'])];
    } elseif ($group === 'probes') {
        foreach ($historyCatalog['probes'] as $probe) {
            $q = piratebox_history_query($probe['signal_id'], $rangeSeconds);
            // Never emit a series for a probe with zero points in this
            // window - an empty series is clutter, not information.
            if ($q['points'] !== []) {
                $series[] = ['label' => $probe['label'], 'points' => $convertPoints($q['points'])];
            }
        }
    } else {
        http_response_code(400);
        echo json_encode(['error' => 'invalid group']);
        exit;
    }

    echo json_encode(['series' => $series, 'unit_symbol' => $tempUnitSymbolRaw]);
    exit;
}

if (($_GET['fetch'] ?? '') === '1') {
    header('Content-Type: application/json');
    echo json_encode([
        'available' => $ambientLight['available'],
        'lux' => $ambientLight['lux'],
        'classification' => $ambientLight['classification'],
        'stale_reading' => $ambientLight['stale_reading'],
        'last_success_seconds_ago' => $ambientLight['last_success_seconds_ago'],
        // Keyed by label (not ROM - the public endpoint never exposes
        // ROM addresses) so the refresh script can find each stat-card
        // by the same label already rendered server-side. `label` is
        // either the operator's own name or a generic "Probe N" -
        // whichever the page rendered for this probe.
        'probes' => array_map(
            fn($p) => [
                'label' => $p['label'],
                'ok' => $p['ok'],
                // Converted at this presentation boundary only - $ds18b20
                // itself (piratebox_get_ds18b20_probes()) still returns
                // the raw Celsius value; nothing upstream of this line
                // is touched by the unit preference.
                'value' => piratebox_convert_temp_c($p['value_c'], $tempUnit),
            ],
            $ds18b20['probes']
        ),
        'unit_symbol' => $tempUnitSymbolRaw,
    ]);
    exit;
}

function piratebox_env_ago_text(?float $seconds): string
{
    if ($seconds === null) {
        return 'unknown';
    }
    if ($seconds < 5) {
        return 'just now';
    }
    if ($seconds < 90) {
        return round($seconds) . ' seconds ago';
    }
    if ($seconds < 3600) {
        return round($seconds / 60) . ' minutes ago';
    }
    return round($seconds / 3600, 1) . ' hours ago';
}

function piratebox_env_duration_text(?float $seconds): string
{
    if ($seconds === null) {
        return 'unknown';
    }
    if ($seconds < 90) {
        return round($seconds) . ' seconds';
    }
    if ($seconds < 3600) {
        return round($seconds / 60) . ' minutes';
    }
    return round($seconds / 3600, 1) . ' hours';
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Environment</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Environment</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility</a></p>

        <p>Live readings from this PirateBox's own onboard environmental sensors - not from the Internet, and not stored anywhere: each reading shown here reflects the sensor right now, not a history.</p>

        <?php if (!$ambientLight['installed'] && !$esp32['installed']): ?>
            <div class="help-note">
                <p><strong>No environmental sensors are currently installed on this PirateBox.</strong> This page will show real readings automatically once one is wired and commissioned - nothing is fabricated in the meantime.</p>
            </div>
        <?php else: ?>
            <?php if ($ambientLight['installed']): ?>

            <h2>Ambient Light</h2>
            <?php if (!$ambientLight['available']): ?>
                <div class="help-note" id="env-ambient-unavailable">
                    <?php if (!$ambientLight['detected']): ?>
                        <p><strong>Sensor status: <span class="status-bad">not responding</span>.</strong> No successful reading has been recorded yet.</p>
                    <?php elseif ($ambientLight['stale_reading']): ?>
                        <p><strong>Sensor status: <span class="status-bad">stale</span>.</strong>
                            <?php if ($ambientLight['lux'] !== null): ?>
                                Last known reading was <?= htmlspecialchars(number_format($ambientLight['lux'], 1)) ?> lux, <?= htmlspecialchars(piratebox_env_ago_text($ambientLight['last_success_seconds_ago'])) ?> - too old to show as current.
                            <?php else: ?>
                                No recent reading is available.
                            <?php endif; ?>
                        </p>
                    <?php else: ?>
                        <p><strong>Sensor status: <span class="status-bad">unavailable</span>.</strong> This device's periodic sensor snapshot hasn't updated recently.</p>
                    <?php endif; ?>
                </div>
            <?php else: ?>
                <div class="stat-grid" id="env-ambient-grid">
                    <div class="stat-card">
                        <span class="stat-label">Current reading</span>
                        <span class="stat-value" id="env-ambient-lux"><?= htmlspecialchars(number_format($ambientLight['lux'], 1)) ?> lux</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-label">Conditions</span>
                        <span class="stat-value" id="env-ambient-label"><?= htmlspecialchars($ambientLight['classification']['label']) ?></span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-label">Sensor status</span>
                        <span class="stat-value status-ok" id="env-ambient-status">Responding</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-label">Last updated</span>
                        <span class="stat-value" id="env-ambient-updated"><?= htmlspecialchars(piratebox_env_ago_text($ambientLight['last_success_seconds_ago'])) ?></span>
                    </div>
                </div>
                <p class="muted" id="env-ambient-description"><?= htmlspecialchars($ambientLight['classification']['description']) ?></p>
            <?php endif; ?>

            <p class="muted">Sensor: BH1750 ambient light sensor, connected to this PirateBox's onboard hardware supervisor. "Lux" is a standard unit of how much visible light is actually falling on a surface - roughly 0.1-1 lux under full moonlight, 50-150 lux in a typically-lit room, and well over 10,000 lux in direct sunlight. It measures light level only, not color, heat, or UV.</p>

            <p class="muted">This reading updates automatically about every 30 seconds while this page is open (no action needed) - it never queries the sensor directly; it only reflects PirateBox's own periodically-refreshed snapshot, so having this page open in several browser tabs or devices at once never polls the hardware any more often.</p>

            <?php endif; // $ambientLight['installed'] ?>

            <?php if ($esp32['installed']): ?>

            <h2>Hardware Supervisor</h2>
            <?php if (!$esp32['available']): ?>
                <div class="help-note" id="env-esp32-unavailable">
                    <?php if (!$esp32['connected']): ?>
                        <p><strong>Status: <span class="status-bad">not connected</span>.</strong> The onboard ESP32-S3 hardware/sensor supervisor is not currently reachable over its serial link.</p>
                    <?php else: ?>
                        <p><strong>Status: <span class="status-bad">stale</span>.</strong> The supervisor connected recently but hasn't reported in - its data is too old to show as current.</p>
                    <?php endif; ?>
                </div>
            <?php else: ?>
                <div class="stat-grid" id="env-esp32-grid">
                    <div class="stat-card">
                        <span class="stat-label">Status</span>
                        <span class="stat-value status-ok" id="env-esp32-status">Connected</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-label">Firmware</span>
                        <span class="stat-value" id="env-esp32-fw"><?= htmlspecialchars($esp32['fw_version'] ?? 'unknown') ?></span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-label">Uptime</span>
                        <span class="stat-value" id="env-esp32-uptime"><?= htmlspecialchars(piratebox_env_duration_text($esp32['uptime_seconds'])) ?></span>
                    </div>
                    <?php if ($esp32['temp_internal_c'] !== null): ?>
                    <div class="stat-card">
                        <span class="stat-label">Chip temperature</span>
                        <span class="stat-value" id="env-esp32-temp"><?= htmlspecialchars(number_format(piratebox_convert_temp_c($esp32['temp_internal_c'], $tempUnit), 1)) ?> <?= $tempUnitSymbol ?></span>
                    </div>
                    <?php endif; ?>
                </div>
                <p class="muted">"Chip temperature" is the ESP32-S3's own on-die sensor - a rough indicator of the board itself, not a calibrated room/ambient reading (that's what Ambient Light, above, is for).</p>
            <?php endif; ?>

            <p class="muted">Hardware Supervisor: an ESP32-S3 microcontroller, connected to this PirateBox over a local serial link, dedicated to real-time sensor/hardware duties. It has no network or cloud access of any kind.</p>

            <?php if ($ds18b20['probes']): ?>

            <h2>Temperature Probes</h2>
            <div class="stat-grid" id="env-probes-grid">
                <?php foreach ($ds18b20['probes'] as $probe): ?>
                <div class="stat-card" data-probe-name="<?= htmlspecialchars($probe['label']) ?>">
                    <span class="stat-label"><?= htmlspecialchars($probe['label']) ?></span>
                    <?php if ($probe['ok']): ?>
                    <span class="stat-value probe-value"><?= htmlspecialchars(number_format(piratebox_convert_temp_c($probe['value_c'], $tempUnit), 1)) ?> <?= $tempUnitSymbol ?></span>
                    <?php else: ?>
                    <span class="stat-value probe-value status-bad">not responding</span>
                    <?php endif; ?>
                </div>
                <?php endforeach; ?>
            </div>
            <p class="muted">Waterproof DS18B20 temperature probes, physically identified one at a time when this PirateBox was commissioned. Probes shown as "Probe N" haven't been given a descriptive name yet; that's expected until each one's physical placement is finalized.</p>
            <?php if ($ds18b20['uncommissioned_count'] > 0): ?>
            <p class="muted"><?= $ds18b20['uncommissioned_count'] ?> more probe<?= $ds18b20['uncommissioned_count'] === 1 ? '' : 's' ?> detected but not yet set up - not shown here.</p>
            <?php endif; ?>
            <?php elseif ($ds18b20['uncommissioned_count'] > 0): ?>

            <h2>Temperature Probes</h2>
            <p class="muted"><?= $ds18b20['uncommissioned_count'] ?> probe<?= $ds18b20['uncommissioned_count'] === 1 ? '' : 's' ?> detected but not yet set up - not shown here.</p>
            <?php endif; ?>

            <?php endif; // $esp32['installed'] ?>

        <?php endif; ?>

        <?php if ($historyCatalog['ambient_light'] !== null || $historyCatalog['esp32_temp'] !== null || $historyCatalog['probes'] !== []): ?>
        <h2>History</h2>
        <p class="muted">How these readings have changed over time - sampled roughly every 5 minutes, never a live poll. A gap in a line means the sensor genuinely had no valid reading then, not zero.</p>

        <?php if ($historyCatalog['ambient_light'] !== null): ?>
        <div class="history-chart-panel" data-history-group="ambient_light" data-history-unit=" lux">
            <h3>Ambient Light</h3>
            <?php if ($historyCatalog['ambient_light']['current_state'] !== 'AVAILABLE'): ?>
            <p class="muted status-bad">Current reading unavailable right now - showing past history only.</p>
            <?php endif; ?>
            <div class="history-range-buttons" role="group" aria-label="Time range"></div>
            <div class="history-chart-container"><canvas></canvas></div>
        </div>
        <?php endif; ?>

        <?php if ($historyCatalog['probes'] !== []): ?>
        <div class="history-chart-panel" data-history-group="probes" data-history-unit="<?= $tempUnitSymbol ?>">
            <h3>Temperature Probes</h3>
            <div class="history-range-buttons" role="group" aria-label="Time range"></div>
            <div class="history-chart-container"><canvas></canvas></div>
        </div>
        <?php endif; ?>

        <?php if ($historyCatalog['esp32_temp'] !== null): ?>
        <div class="history-chart-panel" data-history-group="esp32_temp" data-history-unit="<?= $tempUnitSymbol ?>">
            <h3>ESP32 Chip Temperature</h3>
            <?php if ($historyCatalog['esp32_temp']['current_state'] !== 'AVAILABLE'): ?>
            <p class="muted status-bad">Current reading unavailable right now - showing past history only.</p>
            <?php endif; ?>
            <div class="history-range-buttons" role="group" aria-label="Time range"></div>
            <div class="history-chart-container"><canvas></canvas></div>
        </div>
        <?php endif; ?>
        <?php endif; ?>

        <noscript>
            <p class="help-note">JavaScript is off - the reading above is still accurate as of when this page loaded; reload the page for a fresh one.</p>
        </noscript>
    </div>

    <?php if (($ambientLight['installed'] && $ambientLight['available']) || $ds18b20['probes']): ?>
    <script>
        (function () {
            function ago(seconds) {
                if (seconds === null || seconds === undefined) return 'unknown';
                if (seconds < 5) return 'just now';
                if (seconds < 90) return Math.round(seconds) + ' seconds ago';
                if (seconds < 3600) return Math.round(seconds / 60) + ' minutes ago';
                return (Math.round(seconds / 3600 * 10) / 10) + ' hours ago';
            }
            async function refresh() {
                try {
                    const res = await fetch('/utility/environment/?fetch=1', { cache: 'no-cache' });
                    if (!res.ok) return;
                    const data = await res.json();
                    if (data.available) {
                        const luxEl = document.getElementById('env-ambient-lux');
                        const labelEl = document.getElementById('env-ambient-label');
                        const updatedEl = document.getElementById('env-ambient-updated');
                        const descEl = document.getElementById('env-ambient-description');
                        if (luxEl) luxEl.textContent = Number(data.lux).toFixed(1) + ' lux';
                        if (labelEl && data.classification) labelEl.textContent = data.classification.label;
                        if (descEl && data.classification) descEl.textContent = data.classification.description;
                        if (updatedEl) updatedEl.textContent = ago(data.last_success_seconds_ago);
                    } // else: leave the last good ambient-light reading visible rather than blanking it
                    // The server has already converted `value` to the
                    // current display unit and sends its own symbol
                    // (° C or ° F) - this script never does C/F math of
                    // its own, so there is exactly one place in the
                    // whole app that conversion happens for this data.
                    (data.probes || []).forEach(function (probe) {
                        const card = document.querySelector('[data-probe-name="' + CSS.escape(probe.label) + '"] .probe-value');
                        if (!card) return; // a probe that appears later needs a full page reload, not just JS - fine
                        if (probe.ok) {
                            card.textContent = Number(probe.value).toFixed(1) + ' ' + (data.unit_symbol || '°C');
                            card.classList.remove('status-bad');
                        } else {
                            card.textContent = 'not responding';
                            card.classList.add('status-bad');
                        }
                    });
                } catch (e) {
                    // Offline/transient fetch failure - leave the last known values on screen.
                }
            }
            setInterval(refresh, 30000);
        })();
    </script>
    <?php endif; ?>

    <?php if ($historyCatalog['ambient_light'] !== null || $historyCatalog['esp32_temp'] !== null || $historyCatalog['probes'] !== []): ?>
    <script src="/assets/history-chart.js"></script>
    <script>
        (function () {
            var RANGES = [['6h', '6h'], ['24h', '24h'], ['7d', '7d'], ['30d', '30d']];
            var DEFAULT_RANGE = '24h';

            // History is sampled roughly every 5 minutes (see
            // piratebox-history-sample.timer) - re-fetching more often
            // than that on a timer would just re-draw identical data.
            // Charts load once per page view / range-button click, not
            // on an interval - deliberately lighter than the 30s "live
            // now" refresh above, appropriate for slow-changing history.
            document.querySelectorAll('.history-chart-panel').forEach(function (panel) {
                var group = panel.dataset.historyGroup;
                var unit = panel.dataset.historyUnit || '';
                var canvas = panel.querySelector('canvas');
                var buttonRow = panel.querySelector('.history-range-buttons');
                var buttons = {};

                RANGES.forEach(function (pair) {
                    var key = pair[0], label = pair[1];
                    var btn = document.createElement('button');
                    btn.type = 'button';
                    btn.textContent = label;
                    btn.addEventListener('click', function () { load(key); });
                    buttonRow.appendChild(btn);
                    buttons[key] = btn;
                });

                function setActive(key) {
                    Object.keys(buttons).forEach(function (k) {
                        buttons[k].classList.toggle('active', k === key);
                    });
                }

                async function load(rangeKey) {
                    setActive(rangeKey);
                    try {
                        var res = await fetch(
                            '/utility/environment/?history=1&group=' + encodeURIComponent(group) +
                            '&range=' + encodeURIComponent(rangeKey),
                            { cache: 'no-cache' }
                        );
                        if (!res.ok) return;
                        var data = await res.json();
                        window.PirateboxHistoryChart.render(canvas, data.series || [], { unit: unit });
                    } catch (e) {
                        // Offline/transient fetch failure - leave whatever was last drawn.
                    }
                }

                load(DEFAULT_RANGE);

                // Canvas needs its backing size recomputed for a new
                // container width - simplest correct way is re-running
                // the active range's load(). Debounced so a window
                // drag-resize doesn't fire a burst of redundant fetches.
                var resizeTimer = null;
                window.addEventListener('resize', function () {
                    clearTimeout(resizeTimer);
                    resizeTimer = setTimeout(function () {
                        var activeKey = Object.keys(buttons).find(function (k) { return buttons[k].classList.contains('active'); });
                        if (activeKey) load(activeKey);
                    }, 250);
                });
            });
        })();
    </script>
    <?php endif; ?>
</body>

</html>
