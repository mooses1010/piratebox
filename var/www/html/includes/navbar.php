<?php
// Mode-aware nav order + shared Emergency Mode banner.
//
// require_once is safe to call from here even though pages that already
// need the mode (e.g. index.php) also require it themselves - PHP's
// require_once guards against loading it twice.
require_once __DIR__ . '/mode.php';
$piratebox_mode = piratebox_get_mode();

// Same six links/targets in both modes - only the ORDER changes, so
// Emergency Mode surfaces reference material and live chat first without
// hiding or renaming anything Normal Mode users already rely on.
if ($piratebox_mode === PIRATEBOX_MODE_EMERGENCY) {
    $navOrder = ['utility', 'bulletin', 'chat', 'files', 'messages', 'help', 'upload'];
} else {
    $navOrder = ['files', 'upload', 'chat', 'messages', 'bulletin', 'help', 'utility'];
}

$navItems = [
    'files'    => '<a href="/">Files</a>',
    'upload'   => '<a href="/#upload-form">Upload</a>',
    'chat'     => '<a href="/chat.php">Chat<span id="badge-chat" class="badge"></span></a>',
    'messages' => '<a href="/messages.php">Logbook<span id="badge-messages" class="badge"></span></a>',
    'bulletin' => '<a href="/bulletin.php">Bulletin<span id="badge-bulletin" class="badge"></span></a>',
    'help'     => '<a href="/help.php">Help</a>',
    'utility'  => '<a href="/utility/">Utility</a>',
];
?>
<?php if ($piratebox_mode === PIRATEBOX_MODE_EMERGENCY): ?>
    <div class="mode-banner">
        <div class="help-note">
            <p><strong>Emergency Mode</strong> - this is a local offline network. No Internet access is required or provided.</p>
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
    </ul>
</nav>
