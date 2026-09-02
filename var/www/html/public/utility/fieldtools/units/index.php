<?php
declare(strict_types=1);
session_start();

require_once __DIR__ . '/../../../../includes/fieldtools_convert.php';

// Field Tools: Unit Conversion (Post-Stage-32). Interactive conversion
// needs JavaScript (arbitrary user input, live feedback) - see
// public/assets/fieldtools.js, which mirrors these exact formulas. The
// static reference tables below are server-rendered with the SAME
// tested PHP functions (includes/fieldtools_convert.php), so this page
// still shows real, correct numbers with JavaScript off - see the
// noscript note.

$tempExamples = [];
foreach ([-40, -17.8, 0, 20, 37, 100] as $c) {
    $tempExamples[] = [$c, round(piratebox_convert_temperature($c, 'c', 'f'), 1)];
}

$distExamples = [
    ['1 km', round(piratebox_convert_distance(1, 'km', 'mi'), 4) . ' mi'],
    ['1 mi', round(piratebox_convert_distance(1, 'mi', 'km'), 4) . ' km'],
    ['1 m', round(piratebox_convert_distance(1, 'm', 'ft'), 4) . ' ft'],
    ['1 in', round(piratebox_convert_distance(1, 'in', 'cm'), 4) . ' cm'],
];
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Unit Conversion</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Unit Conversion</h1>
        <p class="utility-breadcrumb"><a href="/utility/fieldtools/">&larr; Field Tools</a></p>

        <noscript>
            <p class="help-note">JavaScript is off, so the live converters below aren't interactive. The reference tables under each one are computed by the server and still accurate - use those for common values.</p>
        </noscript>

        <h2>Temperature</h2>
        <div class="fieldtools-tool" id="ft-temp-tool">
            <div class="fieldtools-row">
                <label for="ft-temp-value">Value</label>
                <input type="number" id="ft-temp-value" step="any" inputmode="decimal" placeholder="0">
                <select id="ft-temp-from" aria-label="Convert from">
                    <option value="c">&deg;C</option>
                    <option value="f">&deg;F</option>
                </select>
            </div>
            <p class="fieldtools-result" id="ft-temp-result" aria-live="polite">Enter a value above.</p>
        </div>
        <div class="table-wrapper">
            <table>
                <thead><tr><th>&deg;C</th><th>&deg;F</th></tr></thead>
                <tbody>
                    <?php foreach ($tempExamples as [$c, $f]): ?>
                        <tr><td><?= $c ?></td><td><?= $f ?></td></tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        </div>

        <h2>Distance</h2>
        <div class="fieldtools-tool" id="ft-distance-tool">
            <div class="fieldtools-row">
                <label for="ft-distance-value">Value</label>
                <input type="number" id="ft-distance-value" step="any" inputmode="decimal" placeholder="0">
                <select id="ft-distance-from" aria-label="Convert from">
                    <option value="mm">mm</option>
                    <option value="cm">cm</option>
                    <option value="m" selected>m</option>
                    <option value="km">km</option>
                    <option value="in">in</option>
                    <option value="ft">ft</option>
                    <option value="yd">yd</option>
                    <option value="mi">mi</option>
                </select>
            </div>
            <p class="fieldtools-result" id="ft-distance-result" aria-live="polite">Enter a value above.</p>
        </div>
        <div class="table-wrapper">
            <table>
                <thead><tr><th>Common</th><th>Equivalent</th></tr></thead>
                <tbody>
                    <?php foreach ($distExamples as [$a, $b]): ?>
                        <tr><td><?= htmlspecialchars($a) ?></td><td><?= htmlspecialchars($b) ?></td></tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        </div>

        <h2>Mass</h2>
        <div class="fieldtools-tool" id="ft-mass-tool">
            <div class="fieldtools-row">
                <label for="ft-mass-value">Value</label>
                <input type="number" id="ft-mass-value" step="any" inputmode="decimal" placeholder="0">
                <select id="ft-mass-from" aria-label="Convert from">
                    <option value="g">g</option>
                    <option value="kg" selected>kg</option>
                    <option value="oz">oz</option>
                    <option value="lb">lb</option>
                </select>
            </div>
            <p class="fieldtools-result" id="ft-mass-result" aria-live="polite">Enter a value above.</p>
        </div>

        <h2>Volume <span class="muted">(US customary)</span></h2>
        <div class="fieldtools-tool" id="ft-volume-tool">
            <div class="fieldtools-row">
                <label for="ft-volume-value">Value</label>
                <input type="number" id="ft-volume-value" step="any" inputmode="decimal" placeholder="0">
                <select id="ft-volume-from" aria-label="Convert from">
                    <option value="ml">mL</option>
                    <option value="l" selected>L</option>
                    <option value="us_floz">US fl oz</option>
                    <option value="us_cup">US cups</option>
                    <option value="us_pint">US pints</option>
                    <option value="us_qt">US quarts</option>
                    <option value="us_gal">US gallons</option>
                </select>
            </div>
            <p class="fieldtools-result" id="ft-volume-result" aria-live="polite">Enter a value above.</p>
        </div>

        <h2>Speed</h2>
        <div class="fieldtools-tool" id="ft-speed-tool">
            <div class="fieldtools-row">
                <label for="ft-speed-value">Value</label>
                <input type="number" id="ft-speed-value" step="any" inputmode="decimal" placeholder="0">
                <select id="ft-speed-from" aria-label="Convert from">
                    <option value="mph" selected>mph</option>
                    <option value="kmh">km/h</option>
                    <option value="ms">m/s</option>
                </select>
            </div>
            <p class="fieldtools-result" id="ft-speed-result" aria-live="polite">Enter a value above.</p>
        </div>

        <h2>Pressure</h2>
        <div class="fieldtools-tool" id="ft-pressure-tool">
            <div class="fieldtools-row">
                <label for="ft-pressure-value">Value</label>
                <input type="number" id="ft-pressure-value" step="any" inputmode="decimal" placeholder="0">
                <select id="ft-pressure-from" aria-label="Convert from">
                    <option value="psi" selected>PSI</option>
                    <option value="kpa">kPa</option>
                    <option value="bar">bar</option>
                </select>
            </div>
            <p class="fieldtools-result" id="ft-pressure-result" aria-live="polite">Enter a value above.</p>
        </div>

        <h2>Storage / data <span class="muted">(binary, 1024-based - matches this device's own Status page)</span></h2>
        <div class="fieldtools-tool" id="ft-storage-tool">
            <div class="fieldtools-row">
                <label for="ft-storage-value">Value</label>
                <input type="number" id="ft-storage-value" step="any" inputmode="decimal" placeholder="0">
                <select id="ft-storage-from" aria-label="Convert from">
                    <option value="b">bytes</option>
                    <option value="kib">KiB</option>
                    <option value="mib" selected>MiB</option>
                    <option value="gib">GiB</option>
                    <option value="tib">TiB</option>
                </select>
            </div>
            <p class="fieldtools-result" id="ft-storage-result" aria-live="polite">Enter a value above.</p>
        </div>

        <h2>Percentage / ratio</h2>
        <div class="fieldtools-tool" id="ft-percent-tool">
            <p><strong>What percent is X of Y?</strong></p>
            <div class="fieldtools-row">
                <label for="ft-pct-part">X</label>
                <input type="number" id="ft-pct-part" step="any" inputmode="decimal" placeholder="25">
                <label for="ft-pct-whole">of Y</label>
                <input type="number" id="ft-pct-whole" step="any" inputmode="decimal" placeholder="200">
            </div>
            <p class="fieldtools-result" id="ft-pct-of-result" aria-live="polite"></p>

            <p><strong>Percent change from X to Y</strong></p>
            <div class="fieldtools-row">
                <label for="ft-pct-old">From X</label>
                <input type="number" id="ft-pct-old" step="any" inputmode="decimal" placeholder="50">
                <label for="ft-pct-new">To Y</label>
                <input type="number" id="ft-pct-new" step="any" inputmode="decimal" placeholder="75">
            </div>
            <p class="fieldtools-result" id="ft-pct-change-result" aria-live="polite"></p>
        </div>

        <h2>Electrical &amp; battery runtime</h2>
        <div class="help-note">
            <p><strong>Runtime estimates are theoretical, not a guarantee.</strong> This is plain arithmetic (capacity &divide; load), derated by one efficiency factor you set. Real-world runtime is normally <em>lower</em> than this suggests: inverter/converter losses, a battery's usable capacity dropping at high discharge rates or in cold temperatures, and a load that isn't perfectly constant all reduce actual runtime further. Treat this as a rough planning number, not a promise.</p>
        </div>
        <div class="fieldtools-tool" id="ft-electrical-tool">
            <p><strong>Volts &times; Amps = Watts</strong></p>
            <div class="fieldtools-row">
                <label for="ft-elec-volts">Volts</label>
                <input type="number" id="ft-elec-volts" step="any" inputmode="decimal" placeholder="12">
                <label for="ft-elec-amps">Amps</label>
                <input type="number" id="ft-elec-amps" step="any" inputmode="decimal" placeholder="2">
            </div>
            <p class="fieldtools-result" id="ft-elec-watts-result" aria-live="polite"></p>

            <p><strong>Battery runtime estimate</strong></p>
            <div class="fieldtools-row">
                <label for="ft-batt-capacity">Battery capacity (Wh)</label>
                <input type="number" id="ft-batt-capacity" step="any" inputmode="decimal" placeholder="100">
            </div>
            <div class="fieldtools-row">
                <label for="ft-batt-load">Load (W)</label>
                <input type="number" id="ft-batt-load" step="any" inputmode="decimal" placeholder="10">
            </div>
            <div class="fieldtools-row">
                <label for="ft-batt-efficiency">Efficiency factor (0-1)</label>
                <input type="number" id="ft-batt-efficiency" step="0.05" min="0" max="1" value="0.8">
            </div>
            <p class="fieldtools-result" id="ft-batt-result" aria-live="polite"></p>
            <p class="muted">Have amp-hours instead of watt-hours? Wh = Ah &times; V (e.g. a 10Ah battery at 12V is about 120Wh).</p>
        </div>

        <h2>Electrical Quick Reference</h2>
        <div class="help-note">
            <p><strong>General reference only, not a substitute for the National Electrical Code (NEC) or a qualified electrician.</strong> Real wiring/circuit-breaker sizing must follow local code, the actual wire's insulation rating, bundling/conduit fill, ambient temperature, and run length (voltage drop) - all of which change safe ampacity from the simplified numbers below. Use this for rough field/DC/low-voltage planning, not for permanent household wiring decisions.</p>
        </div>
        <div class="fieldtools-tool">
            <p><strong>Ohm's Law &amp; power relationships</strong></p>
            <div class="table-wrapper">
                <table>
                    <thead><tr><th>To find</th><th>Formula</th><th>Also equals</th></tr></thead>
                    <tbody>
                        <tr><td>Voltage (V)</td><td>V = I &times; R</td><td>V = P &divide; I</td></tr>
                        <tr><td>Current (I, amps)</td><td>I = V &divide; R</td><td>I = P &divide; V</td></tr>
                        <tr><td>Resistance (R, ohms)</td><td>R = V &divide; I</td><td>R = V&sup2; &divide; P</td></tr>
                        <tr><td>Power (P, watts)</td><td>P = V &times; I</td><td>P = I&sup2; &times; R = V&sup2; &divide; R</td></tr>
                    </tbody>
                </table>
            </div>
            <p class="muted">V = volts, I = current in amps, R = resistance in ohms, P = power in watts. Any two known values give the other two.</p>

            <p><strong>Common copper wire gauge (AWG) reference</strong></p>
            <div class="table-wrapper">
                <table>
                    <thead><tr><th>AWG</th><th>Diameter (approx.)</th><th>Typical safe ampacity*</th><th>Common use</th></tr></thead>
                    <tbody>
                        <tr><td>18 AWG</td><td>1.0 mm</td><td>~5 A</td><td>Low-current signal/LED wiring</td></tr>
                        <tr><td>16 AWG</td><td>1.3 mm</td><td>~10 A</td><td>Light-duty extension cords, small accessories</td></tr>
                        <tr><td>14 AWG</td><td>1.6 mm</td><td>~15 A</td><td>Household lighting circuits</td></tr>
                        <tr><td>12 AWG</td><td>2.05 mm</td><td>~20 A</td><td>Household general-purpose outlet circuits</td></tr>
                        <tr><td>10 AWG</td><td>2.6 mm</td><td>~30 A</td><td>Larger appliances, short solar/battery runs</td></tr>
                        <tr><td>8 AWG</td><td>3.3 mm</td><td>~40 A</td><td>Sub-panels, high-current DC runs</td></tr>
                    </tbody>
                </table>
            </div>
            <p class="muted">*Reviewed against NEC-style reference tables (2026-09-02): the 14/12/10 AWG figures above (15/20/30 A) match the NEC's standard branch-circuit overcurrent protection (breaker/fuse) sizing for those gauges - deliberately more conservative than a conductor's raw rated ampacity (NEC Table 310.16 rates 14 AWG up to ~25-36 A depending on insulation type, but code still caps its breaker at 15 A for safety margin). This table intentionally uses the more conservative, code-aligned numbers throughout, not the higher raw ratings. Still not a substitute for the actual NEC tables/a qualified electrician: real safe ampacity also depends on insulation rating, how many conductors are bundled together, ambient temperature, and run length (voltage drop) - especially at 12V/24V DC, where a longer run needs a thicker gauge than this table alone would suggest.</p>
        </div>
    </div>

    <script src="/assets/fieldtools.js"></script>
    <?php require_once __DIR__ . '/../../../../includes/footer.php'; ?>
</body>

</html>
