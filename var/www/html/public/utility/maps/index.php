<?php
declare(strict_types=1);
session_start();
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Maps &amp; Local Information</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <h1>Maps &amp; Local Information</h1>

    <section class="help-section">
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <div class="help-note utility-placeholder-note">
            <p><strong>This section is not built yet.</strong> It will hold offline local/regional/state/US maps and evacuation/topographic references, plus a single centralized, editable file of local information - emergency phone numbers, hospitals, shelters, emergency management contacts, NOAA/NWS info, and local amateur radio repeaters - so it stays easy to update if this PirateBox moves.</p>
        </div>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
            <a href="/utility/search/">Search</a>
        </div>
    </section>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
