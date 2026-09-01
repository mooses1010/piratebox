<?php
declare(strict_types=1);
session_start();
require_once __DIR__ . '/../includes/mode.php';
$piratebox_mode = piratebox_get_mode();
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - What Can I Do Here?</title>
    <link rel="stylesheet" href="assets/styles.css">
    <script src="assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../includes/navbar.php'; ?>

    <h1>What Can I Do Here?</h1>

    <section class="help-section">
        <p>This is an independent offline local network. It provides files, communication tools, maps, radio references, first-aid information, emergency resources, and other offline utilities to anyone within Wi-Fi range. No Internet connection is required.</p>

        <?php if ($piratebox_mode === PIRATEBOX_MODE_EMERGENCY): ?>
            <div class="help-note">
                <p><strong>Emergency Mode is active.</strong> Emergency, First Aid, Radio, Maps, and Local Information have been prioritized on the home page and in navigation, but everything below - sharing, chat, and the rest of the reference library - is still fully available.</p>
            </div>
        <?php else: ?>
            <p><strong>Normal Mode</strong> emphasizes general sharing, communication, and the reference library. <strong>Emergency Mode</strong> (switched by a physical control on the device) reorganizes and prioritizes the same offline resources around information most useful during a power, Internet, weather, or other local emergency - it does not add or remove content, just reorders what's shown first.</p>
        <?php endif; ?>

        <p class="muted">Internet access is not provided by this network. PirateBox is not an official emergency service.</p>
    </section>

    <section class="help-section">
        <h2>You can:</h2>
        <ul class="help-steps">
            <li><strong>Browse and download files</strong> that others have shared - see <a href="/">Files</a>.</li>
            <li><strong>Share your own files</strong> locally with anyone connected here - also on the <a href="/#upload-form">Files</a> page.</li>
            <li><strong>Chat</strong> with others currently connected, or leave a longer note in the <a href="/messages.php">Guestbook</a>.</li>
            <li><strong>Search everything</strong> on this PirateBox from one box - see <a href="/utility/search/">Search</a>.</li>
            <li><strong>Read emergency and outage guidance</strong> - power outages, severe weather, water/food safety, and more - see <a href="/utility/emergency/">Emergency</a>.</li>
            <li><strong>Read basic first-aid reference material</strong> - see <a href="/utility/firstaid/">First Aid</a>.</li>
            <li><strong>Look up radio bands, frequencies, and modes</strong> for a wideband receiver - see <a href="/utility/radio/">Radio</a>.</li>
            <li><strong>View offline maps and local information</strong> - see <a href="/utility/maps/">Maps</a> and <a href="/utility/local/">Local Information</a>.</li>
            <li><strong>Browse manuals and reference documents</strong> stored on this device - see <a href="/utility/library/">Library</a>.</li>
            <li><strong>Take information with you</strong> - useful reference material can be downloaded to your own device before you disconnect, so it's still available after you leave Wi-Fi range.</li>
        </ul>
    </section>

    <div class="hero-actions">
        <a href="/">Home</a>
        <a href="/utility/">Utility Library</a>
        <a href="/help.php">Help / About</a>
    </div>

    <?php require_once __DIR__ . '/../includes/footer.php'; ?>
</body>

</html>
