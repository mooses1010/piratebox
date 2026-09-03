<?php
declare(strict_types=1);
session_start();
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Offline Utility Library</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../includes/navbar.php'; ?>

    <div class="hero">
        <div class="hero-tagline"><?= htmlspecialchars(piratebox_t('utility.hero_tagline')) ?></div>
        <h1><?= htmlspecialchars(piratebox_t('utility.hero_heading')) ?></h1>
        <p><?= htmlspecialchars(piratebox_t('utility.hero_intro')) ?></p>
        <p class="muted"><?= htmlspecialchars(piratebox_t('utility.hero_muted')) ?></p>
    </div>

    <div class="utility-grid">
        <a class="utility-card" href="/utility/radio/">
            <span class="utility-card-icon" aria-hidden="true">📻</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.radio.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.radio.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/emergency/">
            <span class="utility-card-icon" aria-hidden="true">🚨</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.emergency.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.emergency.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/firstaid/">
            <span class="utility-card-icon" aria-hidden="true">🩹</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.firstaid.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.firstaid.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/maps/">
            <span class="utility-card-icon" aria-hidden="true">🗺️</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.maps.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.maps.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/local/">
            <span class="utility-card-icon" aria-hidden="true">📍</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.local.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.local.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/fieldtools/">
            <span class="utility-card-icon" aria-hidden="true">🧰</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.fieldtools.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.fieldtools.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/computing/">
            <span class="utility-card-icon" aria-hidden="true">🖧</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.computing.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.computing.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/glossary/">
            <span class="utility-card-icon" aria-hidden="true">📖</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.glossary.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.glossary.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/outdoor/">
            <span class="utility-card-icon" aria-hidden="true">🪢</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.outdoor.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.outdoor.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/mechanical/">
            <span class="utility-card-icon" aria-hidden="true">🔧</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.mechanical.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.mechanical.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/electronics/">
            <span class="utility-card-icon" aria-hidden="true">🔌</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.electronics.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.electronics.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/materials/">
            <span class="utility-card-icon" aria-hidden="true">⚗️</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.materials.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.materials.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/about/">
            <span class="utility-card-icon" aria-hidden="true">ℹ️</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.about.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.about.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/library/">
            <span class="utility-card-icon" aria-hidden="true">📚</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.library.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.library.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/search/">
            <span class="utility-card-icon" aria-hidden="true">🔍</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.search.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.search.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/download/">
            <span class="utility-card-icon" aria-hidden="true">⬇️</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.download.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.download.desc')) ?></span>
        </a>
    </div>

    <section class="help-section">
        <h2><?= htmlspecialchars(piratebox_t('utility.also_heading')) ?></h2>
        <div class="hero-actions">
            <a href="/"><?= htmlspecialchars(piratebox_t('utility.also.files')) ?></a>
            <a href="/chat.php"><?= htmlspecialchars(piratebox_t('utility.also.chat')) ?></a>
            <a href="/messages.php"><?= htmlspecialchars(piratebox_t('utility.also.logbook')) ?></a>
            <a href="/help.php"><?= htmlspecialchars(piratebox_t('utility.also.help')) ?></a>
            <a href="/utility/status/"><?= htmlspecialchars(piratebox_t('utility.also.status')) ?></a>
        </div>
    </section>

    <?php require_once __DIR__ . '/../../includes/footer.php'; ?>
</body>

</html>
