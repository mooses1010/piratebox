<?php
declare(strict_types=1);
session_start();

// Field Tools: Coordinates (Post-Stage-32). See /utility/maps/ for the
// written explanation of coordinate formats (DD/DMS/UTM/MGRS) - this
// page is the calculator, not a second copy of that reference text.
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
            <p class="help-note">JavaScript is off, so this converter isn't interactive. The manual conversion steps are on the <a href="/utility/maps/">Maps &amp; Location Reference</a> page.</p>
        </noscript>

        <h2>Decimal Degrees &rarr; DMS</h2>
        <div class="fieldtools-tool" id="ft-dd-tool">
            <div class="fieldtools-row">
                <label for="ft-dd-lat">Latitude (decimal degrees, -90 to 90)</label>
                <input type="number" id="ft-dd-lat" step="any" inputmode="decimal" placeholder="40.6892">
            </div>
            <div class="fieldtools-row">
                <label for="ft-dd-lon">Longitude (decimal degrees, -180 to 180)</label>
                <input type="number" id="ft-dd-lon" step="any" inputmode="decimal" placeholder="-74.0445">
            </div>
            <p class="fieldtools-result" id="ft-dd-result" aria-live="polite">Enter both values above.</p>
        </div>

        <h2>DMS &rarr; Decimal Degrees</h2>
        <div class="fieldtools-tool" id="ft-dms-tool">
            <div class="fieldtools-row">
                <label for="ft-dms-lat-deg">Lat</label>
                <input type="number" id="ft-dms-lat-deg" min="0" max="90" step="1" placeholder="deg" aria-label="Latitude degrees">
                <input type="number" id="ft-dms-lat-min" min="0" max="59" step="1" placeholder="min" aria-label="Latitude minutes">
                <input type="number" id="ft-dms-lat-sec" min="0" max="59.999" step="any" placeholder="sec" aria-label="Latitude seconds">
                <select id="ft-dms-lat-hemi" aria-label="Latitude hemisphere">
                    <option value="N">N</option>
                    <option value="S">S</option>
                </select>
            </div>
            <div class="fieldtools-row">
                <label for="ft-dms-lon-deg">Lon</label>
                <input type="number" id="ft-dms-lon-deg" min="0" max="180" step="1" placeholder="deg" aria-label="Longitude degrees">
                <input type="number" id="ft-dms-lon-min" min="0" max="59" step="1" placeholder="min" aria-label="Longitude minutes">
                <input type="number" id="ft-dms-lon-sec" min="0" max="59.999" step="any" placeholder="sec" aria-label="Longitude seconds">
                <select id="ft-dms-lon-hemi" aria-label="Longitude hemisphere">
                    <option value="E">E</option>
                    <option value="W">W</option>
                </select>
            </div>
            <p class="fieldtools-result" id="ft-dms-result" aria-live="polite">Enter both latitude and longitude above.</p>
        </div>
    </div>

    <script src="/assets/fieldtools.js"></script>
    <?php require_once __DIR__ . '/../../../../includes/footer.php'; ?>
</body>

</html>
