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

        /* "Move Spectrum" controls (hardware center retune) are deliberately
           styled distinctly from the plain "Tune" button above and from
           OpenWebRX+'s own on-screen demodulator controls, so a visitor
           doesn't conflate the two - see the hint paragraph below. */
        .radio-spectrum-shift { display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem; margin: 1rem 0; padding: 0.6rem 0.8rem; border: 1px solid var(--accent-color, #2a5db0); border-radius: 6px; }
        .radio-spectrum-shift button { padding: 0.5rem 0.9rem; border: 1px solid var(--accent-color, #2a5db0); background: transparent; font-weight: 600; }
        .radio-spectrum-shift-label { font-size: 0.9em; }

        .radio-spectrum-map-wrap { margin: 1rem 0; }
        .radio-spectrum-map { position: relative; height: 34px; border: 1px solid var(--border-color, #ccc); border-radius: 4px; background: linear-gradient(to right, rgba(42,93,176,0.08), rgba(42,93,176,0.18)); cursor: crosshair; }
        .radio-spectrum-map-window { position: absolute; top: 0; bottom: 0; min-width: 3px; background: rgba(42,93,176,0.55); border-left: 1px solid #2a5db0; border-right: 1px solid #2a5db0; pointer-events: none; }
        .radio-spectrum-map-ticks { position: relative; height: 1.4em; font-size: 0.75em; margin-top: 2px; }
        .radio-spectrum-map-ticks span { position: absolute; transform: translateX(-50%); white-space: nowrap; }
        .radio-spectrum-map-readout { margin: 0.4rem 0 0; }
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

            <div class="radio-spectrum-shift" id="radio-spectrum-shift">
                <button type="button" id="radio-spectrum-prev">&laquo; Previous Spectrum</button>
                <span class="radio-spectrum-shift-label">Moves the receiver's own ~2&nbsp;MHz sampled window
                    (a real hardware retune, like the presets/frequency box above) - different from the
                    small tuning controls built into the receiver below.</span>
                <button type="button" id="radio-spectrum-next">Next Spectrum &raquo;</button>
            </div>

            <div class="radio-spectrum-map-wrap">
                <p class="muted">Or click anywhere on this bar to jump the ~2&nbsp;MHz window near that
                    part of the spectrum. The scale is <em>logarithmic</em> (not linear) so both ends of
                    this receiver's wide practical range stay usable - the highlighted band shows
                    approximately what's currently sampled, not a claim that the whole bar is live at once.</p>
                <div class="radio-spectrum-map" id="radio-spectrum-map" title="Click to move the receiver's sampled window here">
                    <div class="radio-spectrum-map-window" id="radio-spectrum-map-window"></div>
                </div>
                <div class="radio-spectrum-map-ticks" id="radio-spectrum-map-ticks"></div>
                <p class="radio-spectrum-map-readout muted" id="radio-spectrum-map-readout"></p>
            </div>

            <p class="radio-live-hint muted">The receiver below also has
                its own small <strong>&lt;</strong> / <strong>&gt;</strong>
                buttons next to the frequency readout, plus a "Tuning step"
                dropdown - those move the yellow <em>demodulator</em> marker
                a small, adjustable amount within the currently shown ~2&nbsp;MHz
                slice. They do not move the slice itself. Use the presets, the
                frequency box, the Previous/Next Spectrum buttons, or the bar
                above to move the receiver's sampled window to a different
                part of the spectrum.</p>

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

        // Matches general-sdr's samp_rate in etc/openwebrx/sdrs_seed.py -
        // the actual width of the one slice of spectrum the RTL-SDR
        // samples live at a time. Used only to size the Previous/Next
        // Spectrum shift and the range-bar's window indicator; it is not
        // sent to the receiver (the profile itself already fixes the real
        // sample rate server-side).
        var SPECTRUM_SAMP_RATE_HZ = 2048000;

        // Deliberately smaller than the full sampled width above, not
        // equal to it: a full-width jump would place a signal that was
        // sitting right at one edge of the old window exactly at the
        // opposite edge of the new one - easy to skip over entirely,
        // especially for anything not centered. Shifting by 1.5 MHz
        // instead leaves about 548 kHz (~27%) of overlap between
        // consecutive windows, so nothing near an edge disappears between
        // one click and the next.
        var SPECTRUM_SHIFT_HZ = 1500000;

        // Best-effort starting guess only, for sizing the first
        // Previous/Next/map-click shift before any tune has happened on
        // this page load - not a claim about which profile OpenWebRX+
        // itself actually loaded by default. It matches this project's
        // existing "known good" anchor frequency (the FM Broadcast preset/
        // general-sdr's own default center_freq) used elsewhere on this
        // page already. Every tuneTo() call below sends an explicit,
        // absolute setfrequency regardless of this guess, and updates it
        // to the real value immediately on success - so any mismatch here
        // self-corrects on the very first click.
        var currentCenterHz = 100100000;

        var statusEl = document.getElementById('radio-live-status');
        var frameEl = document.getElementById('radio-live-frame');
        var mapEl = document.getElementById('radio-spectrum-map');
        var mapWindowEl = document.getElementById('radio-spectrum-map-window');
        var mapTicksEl = document.getElementById('radio-spectrum-map-ticks');
        var mapReadoutEl = document.getElementById('radio-spectrum-map-readout');

        function setStatus(text, cls) {
            statusEl.textContent = text;
            statusEl.className = 'radio-live-status' + (cls ? ' ' + cls : '');
        }

        function clampToRange(hz) {
            return Math.min(Math.max(hz, RANGE_LOW_HZ), RANGE_HIGH_HZ);
        }

        // Log scale, not linear: this receiver's practical range (24-1766
        // MHz) is dominated by its top end on a linear scale, which would
        // squeeze the low end (where two of the three curated presets
        // live) into an unusably thin sliver. A log scale keeps every
        // decade of the range comparably readable/clickable.
        var MAP_LOG_LOW = Math.log(RANGE_LOW_HZ);
        var MAP_LOG_HIGH = Math.log(RANGE_HIGH_HZ);

        function freqToFraction(hz) {
            var clamped = clampToRange(hz);
            return (Math.log(clamped) - MAP_LOG_LOW) / (MAP_LOG_HIGH - MAP_LOG_LOW);
        }

        function fractionToFreq(frac) {
            var clamped = Math.min(Math.max(frac, 0), 1);
            return Math.exp(MAP_LOG_LOW + clamped * (MAP_LOG_HIGH - MAP_LOG_LOW));
        }

        function updateSpectrumMap() {
            var leftFrac = freqToFraction(currentCenterHz - SPECTRUM_SAMP_RATE_HZ / 2);
            var rightFrac = freqToFraction(currentCenterHz + SPECTRUM_SAMP_RATE_HZ / 2);
            mapWindowEl.style.left = (leftFrac * 100) + '%';
            mapWindowEl.style.width = (Math.max(rightFrac - leftFrac, 0.004) * 100) + '%';
            mapReadoutEl.textContent = 'Current window: approximately ' +
                ((currentCenterHz - SPECTRUM_SAMP_RATE_HZ / 2) / 1e6).toFixed(3) + '-' +
                ((currentCenterHz + SPECTRUM_SAMP_RATE_HZ / 2) / 1e6).toFixed(3) + ' MHz.';
        }

        (function buildSpectrumMapTicks() {
            var tickMhz = [30, 50, 100, 200, 500, 1000, 1700].filter(function (mhz) {
                return mhz * 1e6 >= RANGE_LOW_HZ && mhz * 1e6 <= RANGE_HIGH_HZ;
            });
            tickMhz.forEach(function (mhz) {
                var span = document.createElement('span');
                span.textContent = mhz + ' MHz';
                span.style.left = (freqToFraction(mhz * 1e6) * 100) + '%';
                mapTicksEl.appendChild(span);
            });
        })();

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
                    currentCenterHz = freqHz;
                    updateSpectrumMap();
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

        function shiftSpectrum(deltaHz) {
            var target = clampToRange(currentCenterHz + deltaHz);
            if (target === currentCenterHz) {
                setStatus('Already at the ' + (deltaHz < 0 ? 'low' : 'high') + ' end of this receiver\'s tunable range.', '');
                return;
            }
            tuneTo(target);
        }

        document.getElementById('radio-spectrum-prev').addEventListener('click', function () {
            shiftSpectrum(-SPECTRUM_SHIFT_HZ);
        });
        document.getElementById('radio-spectrum-next').addEventListener('click', function () {
            shiftSpectrum(SPECTRUM_SHIFT_HZ);
        });

        mapEl.addEventListener('click', function (evt) {
            var rect = mapEl.getBoundingClientRect();
            var frac = (evt.clientX - rect.left) / rect.width;
            tuneTo(Math.round(fractionToFreq(frac) / 1000) * 1000);
        });

        updateSpectrumMap();
    })();
    </script>
    <?php endif; ?>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
