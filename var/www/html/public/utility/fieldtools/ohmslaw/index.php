<?php
declare(strict_types=1);
session_start();

// Ohm's Law / Power Solver (Reference -> Tool principle, see
// docs/REFERENCE-CONTENT-DESIGN.md §9). Companion to the existing
// "Ohm's Law & power relationships" table on Field Tools Units - this
// is the calculator, that table is the at-a-glance reference.
//
// Core calculation works via a plain POST + server-render round trip
// with NO JavaScript required (includes/ohms_law.php does the real
// work, tested directly by tools/test_fieldtools.php). JavaScript
// mirrors the same formulas for instant results.
//
// Deliberately DC resistive-circuit arithmetic only - not live-mains
// procedure. Nothing entered here is logged, stored in $_SESSION, or
// written to any PirateBox data file.

require_once __DIR__ . '/../../../../includes/ohms_law.php';
require_once __DIR__ . '/../../../../includes/library_links.php';

// Cross-link to the Document Library - metadata-driven, see includes/
// library_links.php. Two catalog entries (OSHA electrical-safety
// QuickCard and OSHA 3075) already named this page in their own
// related_pages, but this page never called the render function -
// found and fixed during the round-4 category-page audit.
$libraryLinksHtml = piratebox_render_library_links_html(piratebox_get_library_entries_for_page('/utility/fieldtools/ohmslaw/'));

$v = $_POST['voltage'] ?? '';
$i = $_POST['current'] ?? '';
$r = $_POST['resistance'] ?? '';
$p = $_POST['power'] ?? '';

$result = null;
$filledCount = count(array_filter([$v, $i, $r, $p], fn($x) => trim((string) $x) !== ''));
if ($_SERVER['REQUEST_METHOD'] === 'POST' && $filledCount > 0) {
    $result = piratebox_ohms_law_solve($v, $i, $r, $p);
}

function ohms_fmt(float $n): string
{
    return rtrim(rtrim(number_format($n, 4, '.', ','), '0'), '.') ?: '0';
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Ohm's Law Solver</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Ohm's Law Solver</h1>
        <p class="utility-breadcrumb"><a href="/utility/fieldtools/">&larr; Field Tools</a></p>

        <p>Enter exactly <strong>two</strong> of the four values below and leave the other two blank - voltage (V), current (A), resistance (&#8486;), and power (W) are all related, so any two determine the other two. For the underlying formulas, see the <a href="/utility/fieldtools/units/#ft-electrical-tool">Ohm's Law &amp; power relationships</a> table on the Units page.</p>

        <div class="help-note">
            <p><strong>DC resistive-circuit arithmetic only, not a substitute for the National Electrical Code or a qualified electrician.</strong> This does not account for AC reactance/impedance, and does not cover live-mains work - see Field Tools Units' own Electrical Quick Reference caveat for that boundary.</p>
        </div>

        <?= $libraryLinksHtml ?>

        <form method="post" action="" id="ohms-form">
            <div class="fieldtools-tool" id="ft-ohms-tool">
                <div class="fieldtools-row">
                    <label for="ohms-voltage">Voltage (V)</label>
                    <input type="number" id="ohms-voltage" name="voltage" step="any" inputmode="decimal" placeholder="12" value="<?= htmlspecialchars((string) $v) ?>">
                </div>
                <div class="fieldtools-row">
                    <label for="ohms-current">Current (A)</label>
                    <input type="number" id="ohms-current" name="current" step="any" inputmode="decimal" placeholder="2" value="<?= htmlspecialchars((string) $i) ?>">
                </div>
                <div class="fieldtools-row">
                    <label for="ohms-resistance">Resistance (&#8486;)</label>
                    <input type="number" id="ohms-resistance" name="resistance" step="any" inputmode="decimal" placeholder="6" value="<?= htmlspecialchars((string) $r) ?>">
                </div>
                <div class="fieldtools-row">
                    <label for="ohms-power">Power (W)</label>
                    <input type="number" id="ohms-power" name="power" step="any" inputmode="decimal" placeholder="24" value="<?= htmlspecialchars((string) $p) ?>">
                </div>
                <div class="fieldtools-row">
                    <button type="submit">Solve</button>
                    <button type="button" id="ohms-clear">Clear</button>
                </div>

                <?php if ($result !== null && isset($result['error'])): ?>
                    <p class="fieldtools-result help-note" id="ohms-error"><?= htmlspecialchars($result['error']) ?></p>
                <?php elseif ($result !== null): ?>
                    <div class="table-wrapper" id="ohms-result">
                        <table>
                            <tbody>
                                <tr><td>Voltage</td><td><?= ohms_fmt($result['voltage']) ?> V</td></tr>
                                <tr><td>Current</td><td><?= ohms_fmt($result['current']) ?> A</td></tr>
                                <tr><td>Resistance</td><td><?= ohms_fmt($result['resistance']) ?> &#8486;</td></tr>
                                <tr><td>Power</td><td><?= ohms_fmt($result['power']) ?> W</td></tr>
                            </tbody>
                        </table>
                    </div>
                <?php else: ?>
                    <p class="fieldtools-result" id="ft-ohms-placeholder">Enter any two values above, then Solve.</p>
                <?php endif; ?>
            </div>
        </form>

        <noscript>
            <p class="help-note">JavaScript is off - solving still works: enter two values above and press Solve.</p>
        </noscript>

        <p class="muted">Unfamiliar term (voltage, current, resistance, power)? See the <a href="/utility/glossary/">Glossary</a>.</p>
    </div>

    <script>
        (function () {
            function fmt(n) {
                if (!isFinite(n)) return '0';
                var s = n.toFixed(4).replace(/0+$/, '').replace(/\.$/, '');
                return s === '' || s === '-' ? '0' : s;
            }
            function solve(v, i, r, p) {
                var known = {};
                if (v !== '') known.voltage = parseFloat(v);
                if (i !== '') known.current = parseFloat(i);
                if (r !== '') known.resistance = parseFloat(r);
                if (p !== '') known.power = parseFloat(p);
                for (var k in known) if (isNaN(known[k])) return { error: 'One of the entered values is not a valid number.' };
                var keys = Object.keys(known);
                if (keys.length !== 2) return { error: 'Enter exactly two values (voltage, current, resistance, or power) and leave the other two blank.' };
                if ((known.resistance !== undefined && known.resistance < 0) || (known.power !== undefined && known.power < 0)) {
                    return { error: "Resistance and power can't be negative in this model." };
                }
                keys.sort();
                var pair = keys.join('+');
                var V, I, R, P;
                switch (pair) {
                    case 'current+voltage':
                        V = known.voltage; I = known.current;
                        if (I === 0) return { error: 'Current of 0 A with a nonzero voltage implies infinite resistance (an open circuit) - resistance and power cannot be computed from these two alone.' };
                        R = V / I; P = V * I;
                        break;
                    case 'resistance+voltage':
                        V = known.voltage; R = known.resistance;
                        if (R === 0) return { error: 'Resistance of 0 Ω with a nonzero voltage implies infinite current (a short circuit) - current and power cannot be computed from these two alone.' };
                        I = V / R; P = (V * V) / R;
                        break;
                    case 'power+voltage':
                        V = known.voltage; P = known.power;
                        if (V === 0) return { error: 'Voltage of 0 V with nonzero power is not physically possible in this model - current and resistance cannot be computed from these two alone.' };
                        I = P / V; R = (V * V) / P;
                        break;
                    case 'current+resistance':
                        I = known.current; R = known.resistance;
                        V = I * R; P = (I * I) * R;
                        break;
                    case 'current+power':
                        I = known.current; P = known.power;
                        if (I === 0) return { error: 'Current of 0 A with nonzero power is not physically possible in this model - voltage and resistance cannot be computed from these two alone.' };
                        V = P / I; R = P / (I * I);
                        break;
                    case 'power+resistance':
                        R = known.resistance; P = known.power;
                        V = R === 0 ? 0 : Math.sqrt(P * R);
                        I = R === 0 ? 0 : Math.sqrt(P / R);
                        break;
                    default:
                        return { error: 'Unexpected combination of values.' };
                }
                return { voltage: V, current: I, resistance: R, power: P };
            }

            var fields = ['ohms-voltage', 'ohms-current', 'ohms-resistance', 'ohms-power'].map(function (id) { return document.getElementById(id); });
            var form = document.getElementById('ohms-form');
            var clearBtn = document.getElementById('ohms-clear');
            if (fields.some(function (f) { return !f; }) || !form) return;
            var toolDiv = form.querySelector('.fieldtools-tool');
            var live = null;

            function esc(s) {
                var d = document.createElement('div');
                d.textContent = s;
                return d.innerHTML;
            }

            function render() {
                var vals = fields.map(function (f) { return f.value.trim(); });
                if (!live) {
                    live = document.createElement('div');
                    live.id = 'ohms-result-live';
                    toolDiv.appendChild(live);
                    ['ohms-error', 'ohms-result', 'ft-ohms-placeholder'].forEach(function (id) {
                        var el = document.getElementById(id);
                        if (el) el.hidden = true;
                    });
                }
                if (vals.every(function (v) { return v === ''; })) {
                    live.innerHTML = '';
                    return;
                }
                var r = solve(vals[0], vals[1], vals[2], vals[3]);
                if (r.error) {
                    live.innerHTML = '<p class="fieldtools-result help-note">' + esc(r.error) + '</p>';
                    return;
                }
                live.innerHTML =
                    '<div class="table-wrapper"><table><tbody>' +
                    '<tr><td>Voltage</td><td>' + esc(fmt(r.voltage)) + ' V</td></tr>' +
                    '<tr><td>Current</td><td>' + esc(fmt(r.current)) + ' A</td></tr>' +
                    '<tr><td>Resistance</td><td>' + esc(fmt(r.resistance)) + ' &#8486;</td></tr>' +
                    '<tr><td>Power</td><td>' + esc(fmt(r.power)) + ' W</td></tr>' +
                    '</tbody></table></div>';
            }

            fields.forEach(function (f) { f.addEventListener('input', render); });
            if (clearBtn) {
                clearBtn.addEventListener('click', function () {
                    fields.forEach(function (f) { f.value = ''; });
                    render();
                });
            }
            render();
        })();
    </script>

    <?php require_once __DIR__ . '/../../../../includes/footer.php'; ?>
</body>

</html>
