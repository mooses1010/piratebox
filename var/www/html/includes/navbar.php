<?php
// Mode-aware nav order + shared Emergency Mode banner.
//
// require_once is safe to call from here even though pages that already
// need the mode (e.g. index.php) also require it themselves - PHP's
// require_once guards against loading it twice.
require_once __DIR__ . '/mode.php';
require_once __DIR__ . '/i18n.php';
$piratebox_mode = piratebox_get_mode();

// Same six links/targets in both modes - only the ORDER changes, so
// Emergency Mode surfaces reference material and live chat first without
// hiding or renaming anything Normal Mode users already rely on.
if ($piratebox_mode === PIRATEBOX_MODE_EMERGENCY) {
    $navOrder = ['utility', 'bulletin', 'chat', 'files', 'messages', 'help', 'upload'];
} else {
    $navOrder = ['files', 'upload', 'chat', 'messages', 'bulletin', 'help', 'utility'];
}

// Labels are translated (see includes/i18n.php); hrefs/badge IDs are
// not - those are structural, not language-dependent.
$navItems = [
    'files'    => '<a href="/">' . htmlspecialchars(piratebox_t('nav.files')) . '</a>',
    'upload'   => '<a href="/#upload-form">' . htmlspecialchars(piratebox_t('nav.upload')) . '</a>',
    'chat'     => '<a href="/chat.php">' . htmlspecialchars(piratebox_t('nav.chat')) . '<span id="badge-chat" class="badge"></span></a>',
    'messages' => '<a href="/messages.php">' . htmlspecialchars(piratebox_t('nav.messages')) . '<span id="badge-messages" class="badge"></span></a>',
    'bulletin' => '<a href="/bulletin.php">' . htmlspecialchars(piratebox_t('nav.bulletin')) . '<span id="badge-bulletin" class="badge"></span></a>',
    'help'     => '<a href="/help.php">' . htmlspecialchars(piratebox_t('nav.help')) . '</a>',
    'utility'  => '<a href="/utility/">' . htmlspecialchars(piratebox_t('nav.utility')) . '</a>',
];
?>
<?php if ($piratebox_mode === PIRATEBOX_MODE_EMERGENCY): ?>
    <div class="mode-banner">
        <div class="help-note">
            <p><strong><?= htmlspecialchars(piratebox_t('emergency.banner_title')) ?></strong> - <?= htmlspecialchars(piratebox_t('emergency.banner_text')) ?></p>
        </div>
    </div>
<?php endif; ?>
<nav class="navbar">
    <a class="navbar-brand" href="/">
        <img src="/assets/500px-PirateBox-logo.svg.png" alt="PirateBox Logo">
        PirateBox
    </a>
    <button class="navbar-toggler" aria-label="Toggle navigation" aria-expanded="false" aria-controls="primary-nav">&#9776;</button>
    <ul class="navbar-menu" id="primary-nav">
        <?php foreach ($navOrder as $key): ?>
            <li><?= $navItems[$key] ?></li>
        <?php endforeach; ?>
        <li><?= piratebox_render_language_switcher() ?></li>
    </ul>
</nav>
