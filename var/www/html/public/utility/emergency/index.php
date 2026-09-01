<?php
declare(strict_types=1);
session_start();
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Emergency / Outage Reference</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <h1>Emergency / Outage Reference</h1>

    <section class="help-section">
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <div class="help-note utility-placeholder-note">
            <p><strong>This section is not built yet.</strong> It will hold concise, navigable (not wall-of-text) guidance for power outages, severe storms, flooding, wildfire/smoke, earthquakes, extreme heat and cold, communications outages, water storage and safety, food safety without power, generator and carbon-monoxide safety, sanitation, emergency lighting, and battery/power conservation - plus a place to store authoritative PDFs (FEMA, Ready.gov, NOAA/NWS, CDC, Red Cross) locally.</p>
        </div>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
            <a href="/utility/search/">Search</a>
        </div>
    </section>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
