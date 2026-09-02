<?php
declare(strict_types=1);
session_start();

// Field Tools: Coordinates (Post-Stage-32). See /utility/maps/ for the
// written explanation of coordinate formats (DD/DMS/UTM/MGRS) - this
// page is the calculator, not a second copy of that reference text.
//
// Retrofitted 2026-09-02 (Reference -> Tool principle, see docs/
// REFERENCE-CONTENT-DESIGN.md §9) to add a server-rendered POST
// fallback: this page previously only worked with JavaScript on, with
// a noscript notice sending a JS-off visitor away to do the
// arithmetic by hand. It already had a tested, canonical PHP
// implementation sitting unused (includes/fieldtools_convert.php's
// piratebox_dd_to_dms/piratebox_dms_to_dd, exercised directly by
// tools/test_fieldtools.php) - this just wires the existing page to
// it, matching the no-JS-required bar every tool built since Morse
// follows. Not a duplicate implementation: fieldtools.js's own
// dd/dms functions remain the instant-feedback path when JS is on.

require_once __DIR__ . '/../../../../includes/fieldtools_convert.php';

function ft_coord_num(array $src, string $key): ?float
{
    $raw = trim((string) ($src[$key] ?? ''));
    return ($raw !== '' && is_numeric($raw)) ? (float) $raw : null;
}

$ddResult = null;
$ddLat = $_POST['dd_lat'] ?? '';
$ddLon = $_POST['dd_lon'] ?? '';
if (($_POST['ft_form'] ?? '') === 'dd' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $lat = ft_coord_num($_POST, 'dd_lat');
    $lon = ft_coord_num($_POST, 'dd_lon');
    if ($lat === null || $lon === null) {
        $ddResult = 'Enter both values above.';
    } elseif (!piratebox_coordinate_is_valid($lat, $lon)) {
        $ddResult = ($lat < -90 || $lat > 90) ? 'Latitude must be between -90 and 90.' : 'Longitude must be between -180 and 180.';
    } else {
        [$latDeg, $latMin, $latSec, $latHemi] = piratebox_dd_to_dms($lat, true);
        [$lonDeg, $lonMin, $lonSec, $lonHemi] = piratebox_dd_to_dms($lon, false);
        $ddResult = sprintf('%d°%d′%s″ %s, %d°%d′%s″ %s',
            $latDeg, $latMin, number_format($latSec, 2), $latHemi,
            $lonDeg, $lonMin, number_format($lonSec, 2), $lonHemi);
    }
}

$dmsResult = null;
$dmsVals = ['lat_deg' => '', 'lat_min' => '', 'lat_sec' => '', 'lat_hemi' => 'N', 'lon_deg' => '', 'lon_min' => '', 'lon_sec' => '', 'lon_hemi' => 'E'];
foreach ($dmsVals as $k => $default) $dmsVals[$k] = $_POST['dms_' . $k] ?? $default;
if (($_POST['ft_form'] ?? '') === 'dms' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $latDeg = ft_coord_num($_POST, 'dms_lat_deg');
    $latMin = ft_coord_num($_POST, 'dms_lat_min');
    $latSec = ft_coord_num($_POST, 'dms_lat_sec');
    $lonDeg = ft_coord_num($_POST, 'dms_lon_deg');
    $lonMin = ft_coord_num($_POST, 'dms_lon_min');
    $lonSec = ft_coord_num($_POST, 'dms_lon_sec');
    if ($latDeg === null || $latMin === null || $latSec === null || $lonDeg === null || $lonMin === null || $lonSec === null) {
        $dmsResult = 'Enter both latitude and longitude above.';
    } else {
        $lat = piratebox_dms_to_dd($latDeg, $latMin, $latSec, (string) $dmsVals['lat_hemi']);
        $lon = piratebox_dms_to_dd($lonDeg, $lonMin, $lonSec, (string) $dmsVals['lon_hemi']);
        $dmsResult = ($lat === null || $lon === null) ? 'Check minutes/seconds are 0-59.' : number_format($lat, 6) . ', ' . number_format($lon, 6);
    }
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Coordinate Converter</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Coordinate Converter</h1>
        <p class="utility-breadcrumb"><a href="/utility/fieldtools/">&larr; Field Tools</a></p>

        <p>Decimal Degrees (DD) &harr; Degrees/Minutes/Seconds (DMS). For what these formats mean and how UTM/MGRS relate, see <a href="/utility/maps/">Maps &amp; Location Reference</a>.</p>

        <noscript>
            <p class="help-note">JavaScript is off - conversion still works: enter values below and press Convert.</p>
        </noscript>

        <h2>Decimal Degrees &rarr; DMS</h2>
        <form method="post" action="">
            <input type="hidden" name="ft_form" value="dd">
            <div class="fieldtools-tool" id="ft-dd-tool">
                <div class="fieldtools-row">
                    <label for="ft-dd-lat">Latitude (decimal degrees, -90 to 90)</label>
                    <input type="number" id="ft-dd-lat" name="dd_lat" step="any" inputmode="decimal" placeholder="40.6892" value="<?= htmlspecialchars((string) $ddLat) ?>">
                </div>
                <div class="fieldtools-row">
                    <label for="ft-dd-lon">Longitude (decimal degrees, -180 to 180)</label>
                    <input type="number" id="ft-dd-lon" name="dd_lon" step="any" inputmode="decimal" placeholder="-74.0445" value="<?= htmlspecialchars((string) $ddLon) ?>">
                </div>
                <div class="fieldtools-row">
                    <button type="submit">Convert</button>
                </div>
                <p class="fieldtools-result" id="ft-dd-result" aria-live="polite"><?= htmlspecialchars($ddResult ?? 'Enter both values above.') ?></p>
            </div>
        </form>

        <h2>DMS &rarr; Decimal Degrees</h2>
        <form method="post" action="">
            <input type="hidden" name="ft_form" value="dms">
            <div class="fieldtools-tool" id="ft-dms-tool">
                <div class="fieldtools-row">
                    <label for="ft-dms-lat-deg">Lat</label>
                    <input type="number" id="ft-dms-lat-deg" name="dms_lat_deg" min="0" max="90" step="1" placeholder="deg" aria-label="Latitude degrees" value="<?= htmlspecialchars((string) $dmsVals['lat_deg']) ?>">
                    <input type="number" id="ft-dms-lat-min" name="dms_lat_min" min="0" max="59" step="1" placeholder="min" aria-label="Latitude minutes" value="<?= htmlspecialchars((string) $dmsVals['lat_min']) ?>">
                    <input type="number" id="ft-dms-lat-sec" name="dms_lat_sec" min="0" max="59.999" step="any" placeholder="sec" aria-label="Latitude seconds" value="<?= htmlspecialchars((string) $dmsVals['lat_sec']) ?>">
                    <select id="ft-dms-lat-hemi" name="dms_lat_hemi" aria-label="Latitude hemisphere">
                        <option value="N" <?= $dmsVals['lat_hemi'] === 'N' ? 'selected' : '' ?>>N</option>
                        <option value="S" <?= $dmsVals['lat_hemi'] === 'S' ? 'selected' : '' ?>>S</option>
                    </select>
                </div>
                <div class="fieldtools-row">
                    <label for="ft-dms-lon-deg">Lon</label>
                    <input type="number" id="ft-dms-lon-deg" name="dms_lon_deg" min="0" max="180" step="1" placeholder="deg" aria-label="Longitude degrees" value="<?= htmlspecialchars((string) $dmsVals['lon_deg']) ?>">
                    <input type="number" id="ft-dms-lon-min" name="dms_lon_min" min="0" max="59" step="1" placeholder="min" aria-label="Longitude minutes" value="<?= htmlspecialchars((string) $dmsVals['lon_min']) ?>">
                    <input type="number" id="ft-dms-lon-sec" name="dms_lon_sec" min="0" max="59.999" step="any" placeholder="sec" aria-label="Longitude seconds" value="<?= htmlspecialchars((string) $dmsVals['lon_sec']) ?>">
                    <select id="ft-dms-lon-hemi" name="dms_lon_hemi" aria-label="Longitude hemisphere">
                        <option value="E" <?= $dmsVals['lon_hemi'] === 'E' ? 'selected' : '' ?>>E</option>
                        <option value="W" <?= $dmsVals['lon_hemi'] === 'W' ? 'selected' : '' ?>>W</option>
                    </select>
                </div>
                <div class="fieldtools-row">
                    <button type="submit">Convert</button>
                </div>
                <p class="fieldtools-result" id="ft-dms-result" aria-live="polite"><?= htmlspecialchars($dmsResult ?? 'Enter both latitude and longitude above.') ?></p>
            </div>
        </form>

        <p class="muted">Unfamiliar term (latitude, longitude, DMS)? See the <a href="/utility/glossary/">Glossary</a>.</p>
    </div>

    <script src="/assets/fieldtools.js"></script>
    <?php require_once __DIR__ . '/../../../../includes/footer.php'; ?>
</body>

</html>
