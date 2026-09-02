<?php
declare(strict_types=1);
session_start();

// Frequency <-> Wavelength Calculator (Reference -> Tool principle, see
// docs/REFERENCE-CONTENT-DESIGN.md §9). Companion to Radio Reference's
// HF/VHF/UHF and Antenna & Band Guidance guides - this is the
// calculator, those pages are the explanation.
//
// Core calculation works via a plain POST + server-render round trip
// with NO JavaScript required (includes/freq_wavelength.php does the
// real work, tested directly by tools/test_fieldtools.php).
// JavaScript, where available, mirrors the same formula for instant
// results - simple arithmetic, the same accepted duplication pattern
// public/assets/fieldtools.js already uses (no lookup table here, so
// no JSON-embedding needed the way Morse's table gets).
//
// Nothing entered here is logged, stored in $_SESSION, or written to
// any PirateBox data file.

require_once __DIR__ . '/../../../../includes/freq_wavelength.php';

$value = trim((string) ($_POST['value'] ?? ''));
$unit = $_POST['unit'] ?? 'MHz';
if (!in_array($unit, ['Hz', 'kHz', 'MHz', 'GHz'], true)) $unit = 'MHz';

$result = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST' && $value !== '') {
    $result = piratebox_wavelength_info($value, $unit);
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Frequency / Wavelength Calculator</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Frequency / Wavelength Calculator</h1>
        <p class="utility-breadcrumb"><a href="/utility/fieldtools/">&larr; Field Tools</a></p>

        <p>Enter a frequency to get its free-space wavelength, plus common half-wave and quarter-wave antenna reference lengths. For what HF/VHF/UHF and antenna length actually mean, see <a href="/utility/radio/#hf-vhf-uhf-explained">HF vs VHF vs UHF</a> and <a href="/utility/radio/#antenna-basics">Antenna &amp; Band Guidance</a> on Radio Reference.</p>

        <form method="post" action="" id="wl-form">
            <div class="fieldtools-tool" id="ft-wavelength-tool">
                <div class="fieldtools-row">
                    <label for="wl-value">Frequency</label>
                    <input type="number" id="wl-value" name="value" step="any" inputmode="decimal" placeholder="146" value="<?= htmlspecialchars($value) ?>">
                    <select id="wl-unit" name="unit" aria-label="Frequency unit">
                        <?php foreach (['Hz', 'kHz', 'MHz', 'GHz'] as $u): ?>
                            <option value="<?= $u ?>" <?= $unit === $u ? 'selected' : '' ?>><?= $u ?></option>
                        <?php endforeach; ?>
                    </select>
                </div>
                <div class="fieldtools-row">
                    <button type="submit">Calculate</button>
                </div>

                <?php if ($result !== null && isset($result['error'])): ?>
                    <p class="fieldtools-result help-note" id="wl-error"><?= htmlspecialchars($result['error']) ?></p>
                <?php elseif ($result !== null): ?>
                    <div class="table-wrapper" id="wl-result">
                        <table>
                            <tbody>
                                <tr><td>Frequency</td><td><?= htmlspecialchars($result['frequency_display']) ?> <span class="muted">(<?= htmlspecialchars($result['band']) ?> band)</span></td></tr>
                                <tr><td>Free-space wavelength</td><td><?= htmlspecialchars($result['wavelength_m']) ?> m <span class="muted">(<?= htmlspecialchars($result['wavelength_ft']) ?> ft)</span></td></tr>
                                <tr><td>Half-wave (&lambda;/2) reference</td><td><?= htmlspecialchars($result['half_wave_m']) ?> m <span class="muted">(<?= htmlspecialchars($result['half_wave_ft']) ?> ft)</span></td></tr>
                                <tr><td>Quarter-wave (&lambda;/4) reference</td><td><?= htmlspecialchars($result['quarter_wave_m']) ?> m <span class="muted">(<?= htmlspecialchars($result['quarter_wave_ft']) ?> ft)</span></td></tr>
                            </tbody>
                        </table>
                    </div>
                    <div class="help-note">
                        <p><strong>These are free-space theoretical reference lengths, not build dimensions.</strong> A real antenna's actual required length is typically shorter (a practical dipole is often ~95% of the free-space half-wavelength due to "end effect") and depends on wire/element diameter, the antenna's design, velocity factor (for loaded or transmission-line elements), height above ground, and nearby objects. Use this as a starting reference point and trim/tune the real thing, not as a final cut length.</p>
                    </div>
                <?php else: ?>
                    <p class="fieldtools-result" id="ft-wavelength-placeholder">Enter a frequency above, then Calculate.</p>
                <?php endif; ?>
            </div>
        </form>

        <noscript>
            <p class="help-note">JavaScript is off - calculation still works: enter a frequency above and press Calculate.</p>
        </noscript>

        <p class="muted">Unfamiliar term (wavelength, HF/VHF/UHF, dB)? See the <a href="/utility/glossary/">Glossary</a>.</p>
    </div>

    <script>
        (function () {
            var SPEED_OF_LIGHT = 299792458;
            var UNIT_MULT = { Hz: 1, kHz: 1e3, MHz: 1e6, GHz: 1e9 };

            function band(hz) {
                var mhz = hz / 1e6;
                if (mhz < 0.3) return 'MF or below';
                if (mhz < 3) return 'MF';
                if (mhz < 30) return 'HF';
                if (mhz < 300) return 'VHF';
                if (mhz < 3000) return 'UHF';
                return 'SHF or above';
            }
            function fmtLen(m) {
                var decimals = m >= 100 ? 1 : (m >= 1 ? 3 : 4);
                return m.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
            }
            function calc(valueStr, unit) {
                var value = parseFloat(valueStr);
                if (isNaN(value) || value <= 0) return { error: '"' + valueStr + '" isn\'t a valid positive frequency.' };
                var mult = UNIT_MULT[unit];
                if (!mult) return { error: '"' + unit + '" isn\'t a recognized frequency unit.' };
                var hz = value * mult;
                var wlM = SPEED_OF_LIGHT / hz;
                var wlFt = wlM * 3.28084;
                return {
                    band: band(hz),
                    wavelength_m: fmtLen(wlM), wavelength_ft: fmtLen(wlFt),
                    half_wave_m: fmtLen(wlM / 2), half_wave_ft: fmtLen(wlFt / 2),
                    quarter_wave_m: fmtLen(wlM / 4), quarter_wave_ft: fmtLen(wlFt / 4)
                };
            }

            var valueField = document.getElementById('wl-value');
            var unitField = document.getElementById('wl-unit');
            var form = document.getElementById('wl-form');
            if (!valueField || !unitField || !form) return;
            var toolDiv = form.querySelector('.fieldtools-tool');
            var live = null;

            function esc(s) {
                var d = document.createElement('div');
                d.textContent = s;
                return d.innerHTML;
            }

            function render() {
                if (valueField.value.trim() === '') return;
                var r = calc(valueField.value, unitField.value);
                if (!live) {
                    live = document.createElement('div');
                    live.id = 'wl-result-live';
                    toolDiv.appendChild(live);
                    ['wl-error', 'wl-result', 'ft-wavelength-placeholder'].forEach(function (id) {
                        var el = document.getElementById(id);
                        if (el) el.hidden = true;
                    });
                }
                if (r.error) {
                    live.innerHTML = '<p class="fieldtools-result help-note">' + esc(r.error) + '</p>';
                    return;
                }
                live.innerHTML =
                    '<div class="table-wrapper"><table><tbody>' +
                    '<tr><td>Frequency</td><td>' + esc(valueField.value) + ' ' + esc(unitField.value) + ' <span class="muted">(' + esc(r.band) + ' band)</span></td></tr>' +
                    '<tr><td>Free-space wavelength</td><td>' + esc(r.wavelength_m) + ' m <span class="muted">(' + esc(r.wavelength_ft) + ' ft)</span></td></tr>' +
                    '<tr><td>Half-wave (&#955;/2) reference</td><td>' + esc(r.half_wave_m) + ' m <span class="muted">(' + esc(r.half_wave_ft) + ' ft)</span></td></tr>' +
                    '<tr><td>Quarter-wave (&#955;/4) reference</td><td>' + esc(r.quarter_wave_m) + ' m <span class="muted">(' + esc(r.quarter_wave_ft) + ' ft)</span></td></tr>' +
                    '</tbody></table></div>' +
                    '<div class="help-note"><p><strong>Free-space theoretical reference, not a build dimension</strong> - a real antenna is typically shorter (end effect, design, velocity factor, environment). Use as a starting point, not a final cut length.</p></div>';
            }

            valueField.addEventListener('input', render);
            unitField.addEventListener('change', render);
            render();
        })();
    </script>

    <?php require_once __DIR__ . '/../../../../includes/footer.php'; ?>
</body>

</html>
