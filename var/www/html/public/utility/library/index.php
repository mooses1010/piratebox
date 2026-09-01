<?php
declare(strict_types=1);
session_start();
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Document Library</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <h1>Document Library</h1>

    <section class="help-section">
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <div class="help-note utility-placeholder-note">
            <p><strong>This section is not built yet.</strong> It will hold an organized, browsable library of manuals and reference documents stored on this device (radio, Raspberry Pi/Linux/networking, electronics, vehicle, generator, emergency, first-aid, and maps documents), indexed by dropping files into folders and running one rebuild script - no hand-editing a page per document.</p>
        </div>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
            <a href="/utility/search/">Search</a>
        </div>
    </section>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
