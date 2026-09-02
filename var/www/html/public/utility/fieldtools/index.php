<?php
declare(strict_types=1);
session_start();

// Field Tools (Post-Stage-32) - offline field instrument section.
//
// Deliberately does NOT read piratebox_get_mode() - identical in Normal
// and Emergency Mode, same reasoning as every other universal reference
// section (Radio, First Aid). No local-sensitive content anywhere in
// this section, so Travel Mode quarantine (includes/travel_mode.php)
// doesn't apply here either - see docs/OPERATIONAL-DECISIONS.md ("Field
// Tools / Offline Reference Instruments") for that decision explicitly.
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Field Tools</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Field Tools</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>Time, unit conversion, and simple field arithmetic - useful when this PirateBox is operating away from mains power, cell service, or the Internet for days at a time, not just as a file-sharing box. Everything below runs entirely on this device.</p>

        <div class="help-note">
            <p><strong>Nothing you enter here is saved.</strong> These are calculators, not forms - no input or result is logged, stored, or sent anywhere. Estimates are labeled as estimates; see each tool for its own caveats.</p>
        </div>

        <div class="utility-grid">
            <a class="utility-card" href="/utility/fieldtools/time/">
                <span class="utility-card-icon" aria-hidden="true">🕒</span>
                <span class="utility-card-title">Time &amp; Date</span>
                <span class="utility-card-desc">Current local/UTC time, ISO-8601, Unix timestamp, elapsed-time calculator, and this device's time-source status</span>
            </a>
            <a class="utility-card" href="/utility/fieldtools/units/">
                <span class="utility-card-icon" aria-hidden="true">📐</span>
                <span class="utility-card-title">Unit Conversion</span>
                <span class="utility-card-desc">Temperature, distance, mass, volume, speed, pressure, electrical/battery, storage, and percentage tools</span>
            </a>
            <a class="utility-card" href="/utility/fieldtools/coordinates/">
                <span class="utility-card-icon" aria-hidden="true">🧭</span>
                <span class="utility-card-title">Coordinates</span>
                <span class="utility-card-desc">Decimal degrees &harr; degrees/minutes/seconds converter</span>
            </a>
            <a class="utility-card" href="/utility/fieldtools/morse/">
                <span class="utility-card-icon" aria-hidden="true">&#183;&#8212;</span>
                <span class="utility-card-title">Morse Code Converter</span>
                <span class="utility-card-desc">Text &harr; Morse code, entirely offline, works without JavaScript</span>
            </a>
            <a class="utility-card" href="/utility/fieldtools/subnet/">
                <span class="utility-card-icon" aria-hidden="true">🖧</span>
                <span class="utility-card-title">Subnet Calculator</span>
                <span class="utility-card-desc">IPv4 network/broadcast address, usable host range, and prefix &harr; netmask</span>
            </a>
            <a class="utility-card" href="/utility/fieldtools/wavelength/">
                <span class="utility-card-icon" aria-hidden="true">📡</span>
                <span class="utility-card-title">Frequency / Wavelength</span>
                <span class="utility-card-desc">Free-space wavelength plus half/quarter-wave antenna reference lengths</span>
            </a>
            <a class="utility-card" href="/utility/fieldtools/ohmslaw/">
                <span class="utility-card-icon" aria-hidden="true">&#9889;</span>
                <span class="utility-card-title">Ohm's Law Solver</span>
                <span class="utility-card-desc">Enter any two of voltage/current/resistance/power to get the other two</span>
            </a>
            <a class="utility-card" href="/utility/fieldtools/checksum/">
                <span class="utility-card-icon" aria-hidden="true">🔒</span>
                <span class="utility-card-title">Checksum / Hash Calculator</span>
                <span class="utility-card-desc">Verify a file already on this PirateBox, or hash pasted text (SHA-256/MD5)</span>
            </a>
        </div>

        <p class="muted">Looking for what latitude/longitude actually mean, or coordinate formats like UTM/MGRS? See <a href="/utility/maps/">Maps &amp; Location Reference</a> - this section's Coordinates tool is the calculator; that page is the explanation. Likewise: Morse's full table is on <a href="/utility/radio/#morse-code-reference">Radio Reference</a>; Subnet's explanation is on <a href="/utility/computing/#cidr-subnet-mask-reference">Computing &amp; Networking Reference</a>; Frequency/Wavelength's is on <a href="/utility/radio/#hf-vhf-uhf-explained">Radio Reference</a>; Ohm's Law's is on this section's own <a href="/utility/fieldtools/units/#ft-electrical-tool">Unit Conversion</a> page.</p>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
