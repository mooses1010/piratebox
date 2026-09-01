<?php
declare(strict_types=1);
session_start();
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - First Aid Reference</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <h1>First Aid Reference</h1>

    <section class="help-section">
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <div class="help-note utility-placeholder-note">
            <p><strong>This section is not built yet.</strong> It will hold a conservative, basic first-aid reference - getting professional/emergency help, CPR/AED overview, severe bleeding, choking, burns, shock, heat illness, hypothermia, poisoning, common minor injuries, and a first-aid kit reference - built from locally stored authoritative sources with the source clearly identified.</p>
        </div>

        <p class="muted"><strong>This is not, and will not be, a substitute for professional medical care.</strong></p>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
            <a href="/utility/search/">Search</a>
        </div>
    </section>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
