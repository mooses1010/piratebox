<?php
declare(strict_types=1);
session_start();
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Search the Utility Library</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <h1>Search</h1>

    <section class="help-section">
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <div class="help-note utility-placeholder-note">
            <p><strong>This section is not built yet.</strong> It will provide one search box across everything in the Utility Library (radio, emergency, first aid, maps, local info, and the document library), running entirely client-side against a small locally generated index - no server-side search process, and it works with the Wi-Fi already connected here, no Internet needed.</p>
        </div>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
        </div>
    </section>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
