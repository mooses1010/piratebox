<?php
declare(strict_types=1);
session_start();

// Radio - Live Receiver (2026-09-05). Companion to index.php's static
// reference content, not a replacement for it - added because the
// stock OpenWebRX+ frontend (installed at /radio/, see
// docs/RADIO-SDR-ARCHITECTURE-DESIGN.md section 13) has no UI control
// that ever sends an arbitrary center-frequency change, even with
// OpenWebRX+'s own allow_center_freq_changes setting enabled -
// confirmed by reading its actual shipped JavaScript (grep found zero
// references to that setting anywhere in htdocs/*.js). The backend
// protocol support is real and already proven (docs/RADIO-SDR-
// ARCHITECTURE-DESIGN.md section 13.6/13.7) - this page is the
// PirateBox-side control OpenWebRX+ itself doesn't provide, not a
// backend workaround.
//
// Deliberately does NOT proxy the tune command through PHP/nginx: the
// browser's own JavaScript opens a direct WebSocket to the same
// /radio/ws/ path OpenWebRX+'s own frontend already uses (see
// etc/nginx/openwebrx-location.conf), replicating the exact protocol
// sequence already validated server-side (docs/RADIO-SDR-ARCHITECTURE-
// DESIGN.md section 13.5's handshake: "SERVER DE CLIENT ... type=
// receiver", then JSON selectprofile/setfrequency messages). No new
// PHP endpoint, no new backend code, no admin credentials anywhere in
// this path - the same visitor-facing allow_center_freq_changes
// setting that makes this possible for OpenWebRX+'s own page makes it
// possible here too.
//
// Graceful degradation: a short server-side TCP probe of OpenWebRX+'s
// loopback port decides whether to show the live tuner/receiver at
// all, or a plain "not currently available" message - this page must
// never show a broken iframe or a JS error to a visitor when the
// optional Radio capability is absent, matching this project's
// existing optional-capability architecture (docs/ARCHITECTURE.md
// section 2).

function radio_live_openwebrx_reachable(): bool
{
    $sock = @fsockopen('127.0.0.1', 8073, $errno, $errstr, 0.75);
    if ($sock === false) {
        return false;
    }
    fclose($sock);
    return true;
}

$reachable = radio_live_openwebrx_reachable();

// Curated presets: only frequencies this project has actually,
// directly confirmed receiving real signal at (docs/RADIO-SDR-
// ARCHITECTURE-DESIGN.md sections 3b.3, 13.5, 13.6/13.7) - not a
// larger "should work" list, so a visitor's first click is never a
// guess.
$presets = [
    ['label' => 'NOAA Weather Radio', 'mhz' => 162.475, 'note' => 'confirmed receiving in this project\'s own testing'],
    ['label' => 'FM Broadcast', 'mhz' => 100.1, 'note' => 'confirmed receiving a real station in this project\'s own testing'],
    ['label' => 'CB / 11m', 'mhz' => 27.185, 'note' => 'confirmed streaming real data in this project\'s own testing'],
];

// Community-documented practical range for the Rafael Micro R820T/
// R820T2 tuner family confirmed installed in this project's own RTL-SDR
// (docs/RADIO-SDR-ARCHITECTURE-DESIGN.md section 3a.2) - NOT exhaustively
// re-verified across this whole span by this project (only the three
// preset points above have been directly confirmed). Enforced here as
// a client-side sanity bound, not a claim that every frequency in this
// range has been tested or will produce a usable signal.
$rangeLowMhz = 24;
$rangeHighMhz = 1766;
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Live Receiver</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
    <style>
        .radio-live-presets { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 1rem 0; }
        .radio-live-presets button { padding: 0.5rem 0.9rem; }
        .radio-live-manual { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin: 1rem 0; }
        .radio-live-manual input[type=number] { width: 8em; }
        .radio-live-status { min-height: 1.5em; margin: 0.5rem 0; }
        .radio-live-status.is-error { color: #b00020; }
        .radio-live-status.is-ok { color: #1a7a1a; }
        .radio-live-frame-wrap { border: 1px solid var(--border-color, #ccc); border-radius: 6px; overflow: hidden; margin-top: 1rem; }
        .radio-live-frame-wrap iframe { display: block; width: 100%; height: 70vh; border: 0; }
        .radio-live-unavailable { padding: 1.5rem; border: 1px dashed var(--border-color, #ccc); border-radius: 6px; }
    </style>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Live Receiver</h1>
        <p class="utility-breadcrumb"><a href="/utility/radio/">&larr; Radio Reference</a></p>

        <?php if (!$reachable): ?>
            <div class="radio-live-unavailable">
                <p><strong>The live receiver is not currently available.</strong></p>
                <p>This is an optional PirateBox capability (see the
                    <a href="/utility/radio/">Radio Reference</a> page for the
                    static frequency/service reference, which always works with
                    no hardware attached). It depends on an RTL-SDR receiver and
                    a background service that are not running right now - core
                    PirateBox features (uploads, chat, this site) are unaffected
                    either way.</p>
            </div>
        <?php else: ?>
            <p>Tap a preset or enter a frequency to move the receiver below to
                a different part of the radio spectrum. <strong>Each tune shows
                one ~2 MHz-wide slice of spectrum at a time, centered on the
                frequency you pick - it does not show the whole radio spectrum
                at once.</strong> No account or admin login is needed.</p>

            <div class="radio-live-presets" id="radio-live-presets">
                <?php foreach ($presets as $p): ?>
                    <button type="button"
                        data-mhz="<?= htmlspecialchars((string) $p['mhz']) ?>"
                        title="<?= htmlspecialchars($p['note']) ?>">
                        <?= htmlspecialchars($p['label']) ?> (<?= htmlspecialchars((string) $p['mhz']) ?> MHz)
                    </button>
                <?php endforeach; ?>
            </div>

            <form class="radio-live-manual" id="radio-live-manual-form">
                <label for="radio-live-mhz">Frequency (MHz):</label>
                <input type="number" id="radio-live-mhz" name="mhz" step="0.001"
                    min="<?= (int) $rangeLowMhz ?>" max="<?= (int) $rangeHighMhz ?>"
                    placeholder="e.g. 145.500">
                <button type="submit">Tune</button>
                <span class="muted">Valid range: <?= (int) $rangeLowMhz ?>-<?= (int) $rangeHighMhz ?> MHz (this receiver's practical tuning range - not every frequency in it has been tested)</span>
            </form>

            <p class="radio-live-status" id="radio-live-status" role="status" aria-live="polite"></p>

            <p class="radio-live-hint muted">The receiver below also has
                its own small <strong>&lt;</strong> / <strong>&gt;</strong>
                buttons next to the frequency readout - those only nudge
                within the currently shown slice (a few kHz at a time),
                they do not move to a different band. Use the presets or
                the frequency box above to jump broadly.</p>

            <div class="radio-live-frame-wrap">
                <iframe id="radio-live-frame" src="/radio/" title="OpenWebRX+ receiver" loading="lazy"></iframe>
            </div>
        <?php endif; ?>

        <div class="hero-actions">
            <a href="/utility/radio/">Radio Reference</a>
            <a href="/utility/">Utility Library</a>
        </div>
    </div>

    <?php if ($reachable): ?>
    <script>
    (function () {
        'use strict';

        var RANGE_LOW_HZ = <?= (int) ($rangeLowMhz * 1000000) ?>;
        var RANGE_HIGH_HZ = <?= (int) ($rangeHighMhz * 1000000) ?>;
        var PROFILE = 'rtlsdr|general-sdr';

        var statusEl = document.getElementById('radio-live-status');
        var frameEl = document.getElementById('radio-live-frame');

        function setStatus(text, cls) {
            statusEl.textContent = text;
            statusEl.className = 'radio-live-status' + (cls ? ' ' + cls : '');
        }

        // Replicates the exact protocol this project already validated
        // server-side with a standalone Python client (docs/RADIO-SDR-
        // ARCHITECTURE-DESIGN.md section 13.5): a WebSocket handshake
        // string, then JSON control messages. Deliberately does NOT send
        // "dspcontrol start" - that spins up this client's own audio/
        // waterfall demodulation chain, which this one-shot control
        // widget has no use for; selectprofile+setfrequency alone are
        // enough to move the shared underlying receiver's actual center
        // frequency, which is what every other connected client
        // (including the iframe below) sees.
        function tuneTo(freqHz) {
            if (!isFinite(freqHz) || freqHz < RANGE_LOW_HZ || freqHz > RANGE_HIGH_HZ) {
                setStatus('Please enter a frequency between ' + (RANGE_LOW_HZ / 1e6) + ' and ' + (RANGE_HIGH_HZ / 1e6) + ' MHz.', 'is-error');
                return;
            }

            setStatus('Tuning to ' + (freqHz / 1e6).toFixed(3) + ' MHz...', '');

            var proto = (window.location.protocol === 'https:') ? 'wss' : 'ws';
            var ws;
            try {
                ws = new WebSocket(proto + '://' + window.location.host + '/radio/ws/');
            } catch (e) {
                setStatus('Could not reach the receiver (' + e.message + ').', 'is-error');
                return;
            }

            var settled = false;
            var timeoutId = window.setTimeout(function () {
                if (!settled) {
                    settled = true;
                    setStatus('The receiver did not respond in time - it may be busy or unavailable. Try again shortly.', 'is-error');
                    try { ws.close(); } catch (e) { /* ignore */ }
                }
            }, 6000);

            function finish(ok, message) {
                if (settled) {
                    return;
                }
                settled = true;
                window.clearTimeout(timeoutId);
                try { ws.close(); } catch (e) { /* ignore */ }
                setStatus(message, ok ? 'is-ok' : 'is-error');
                if (ok) {
                    // Reload the embedded receiver so its own displayed
                    // frequency/profile catches up with the change - the
                    // underlying shared source retunes immediately, but
                    // an already-open client's own UI doesn't otherwise
                    // know to refresh its display.
                    window.setTimeout(function () {
                        frameEl.src = '/radio/?_t=' + Date.now();
                    }, 400);
                }
            }

            ws.onopen = function () {
                ws.send('SERVER DE CLIENT client=piratebox-radio-tuner type=receiver');
            };

            ws.onmessage = function (evt) {
                if (typeof evt.data !== 'string') {
                    return;
                }
                if (evt.data.indexOf('CLIENT DE SERVER') === 0) {
                    ws.send(JSON.stringify({type: 'selectprofile', params: {profile: PROFILE}}));
                    window.setTimeout(function () {
                        ws.send(JSON.stringify({type: 'setfrequency', params: {frequency: freqHz}}));
                        window.setTimeout(function () {
                            finish(true, 'Tuned to ' + (freqHz / 1e6).toFixed(3) + ' MHz - receiver below updated.');
                        }, 700);
                    }, 300);
                    return;
                }
                try {
                    var msg = JSON.parse(evt.data);
                    if (msg && (msg.type === 'sdr_error' || msg.type === 'demodulator_error')) {
                        finish(false, 'Receiver error: ' + msg.value);
                    }
                } catch (e) {
                    // non-JSON text message (e.g. a log line) - ignore
                }
            };

            ws.onerror = function () {
                finish(false, 'Could not reach the receiver. It may be temporarily unavailable.');
            };

            ws.onclose = function () {
                if (!settled) {
                    finish(false, 'Connection to the receiver closed unexpectedly.');
                }
            };
        }

        document.getElementById('radio-live-presets').addEventListener('click', function (evt) {
            var btn = evt.target.closest('button[data-mhz]');
            if (!btn) {
                return;
            }
            tuneTo(Math.round(parseFloat(btn.getAttribute('data-mhz')) * 1000000));
        });

        document.getElementById('radio-live-manual-form').addEventListener('submit', function (evt) {
            evt.preventDefault();
            var mhz = parseFloat(document.getElementById('radio-live-mhz').value);
            if (!mhz || isNaN(mhz)) {
                setStatus('Please enter a valid frequency in MHz.', 'is-error');
                return;
            }
            tuneTo(Math.round(mhz * 1000000));
        });
    })();
    </script>
    <?php endif; ?>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
