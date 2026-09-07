<?php
declare(strict_types=1);
session_start();
// i18n.php is normally pulled in by includes/navbar.php further down -
// required explicitly here too (require_once, so no double-load) since
// piratebox_t() is now needed for the environment card BEFORE navbar
// renders, not just after it like every other card on this page.
require_once __DIR__ . '/../../includes/i18n.php';
require_once __DIR__ . '/../../includes/sensors.php';

// Environment card (2026-09-07): a live one-line snippet when a
// current reading is actually available, falling back to the same
// plain static description every other card uses otherwise - the
// landing page must stay lightweight and never show a stale/bogus
// number (see includes/sensors.php's own honest-degrade discipline).
$ambientLight = piratebox_get_ambient_light_reading();
$environmentCardDesc = piratebox_t('utility.card.environment.desc');
if ($ambientLight['available'] && $ambientLight['classification'] !== null) {
    $environmentCardDesc = sprintf(
        'Ambient light: %.1f lux (%s)',
        $ambientLight['lux'],
        $ambientLight['classification']['label']
    );
}
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
        <a class="utility-card" href="/utility/captains-log/">
            <span class="utility-card-icon" aria-hidden="true">📜</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.captainslog.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars(piratebox_t('utility.card.captainslog.desc')) ?></span>
        </a>
        <a class="utility-card" href="/utility/environment/">
            <span class="utility-card-icon" aria-hidden="true">🌤️</span>
            <span class="utility-card-title"><?= htmlspecialchars(piratebox_t('utility.card.environment.title')) ?></span>
            <span class="utility-card-desc"><?= htmlspecialchars($environmentCardDesc) ?></span>
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
