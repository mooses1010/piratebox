<?php
declare(strict_types=1);
session_start();
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Radio Reference</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <h1>Radio Reference</h1>

    <section class="help-section">
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <div class="help-note utility-placeholder-note">
            <p><strong>This section is not built yet.</strong> It will hold a locally searchable, phone-friendly reference for the Malahit-style wideband receiver: amateur radio bands and band plans, NOAA Weather Radio, AM/FM/shortwave broadcast, CB/FRS/GMRS/MURS, marine VHF, airband, railroad frequencies, common modulation types (AM/FM/WFM/USB/LSB/CW), which receiver mode to use for each service, basic antenna guidance, and HF propagation basics.</p>
        </div>

        <p class="muted">Receive information will be clearly separated from transmit/licensing information, and all frequency data will be sourced from authoritative references (FCC, NOAA/NWS, ARRL/ITU) with the source and date recorded - see Utility Library Stage 2.</p>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
            <a href="/utility/search/">Search</a>
        </div>
    </section>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
