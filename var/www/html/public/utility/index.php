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
        <div class="hero-tagline">Local Offline Network</div>
        <h1>Offline Utility Library</h1>
        <p>No Internet connection is used or required - this network never leaves this device. Everything below is stored locally on this PirateBox: radio references, emergency and first-aid information, maps, manuals, and search all work the same with or without a working Internet connection anywhere nearby.</p>
        <p class="muted">This is an addition to the regular PirateBox file-sharing network, not a replacement for it - Files, Chat, and the Logbook are all still here too.</p>
    </div>

    <div class="utility-grid">
        <a class="utility-card" href="/utility/radio/">
            <span class="utility-card-icon" aria-hidden="true">📻</span>
            <span class="utility-card-title">Radio</span>
            <span class="utility-card-desc">Bands, frequencies, modes &amp; antenna basics for a wideband receiver</span>
        </a>
        <a class="utility-card" href="/utility/emergency/">
            <span class="utility-card-icon" aria-hidden="true">🚨</span>
            <span class="utility-card-title">Emergency</span>
            <span class="utility-card-desc">Power outages, storms, floods, heat/cold &amp; other outage guidance</span>
        </a>
        <a class="utility-card" href="/utility/firstaid/">
            <span class="utility-card-icon" aria-hidden="true">🩹</span>
            <span class="utility-card-title">First Aid</span>
            <span class="utility-card-desc">Basic conservative first-aid reference - not a substitute for care</span>
        </a>
        <a class="utility-card" href="/utility/maps/">
            <span class="utility-card-icon" aria-hidden="true">🗺️</span>
            <span class="utility-card-title">Maps</span>
            <span class="utility-card-desc">A world reference map, coordinates/GPS basics, and a local/regional map catalog</span>
        </a>
        <a class="utility-card" href="/utility/local/">
            <span class="utility-card-icon" aria-hidden="true">📍</span>
            <span class="utility-card-title">Local Info</span>
            <span class="utility-card-desc">Hospitals, shelters, emergency contacts &amp; repeaters for this area</span>
        </a>
        <a class="utility-card" href="/utility/fieldtools/">
            <span class="utility-card-icon" aria-hidden="true">🧰</span>
            <span class="utility-card-title">Field Tools</span>
            <span class="utility-card-desc">Time/date, unit conversion &amp; coordinate calculators for offline field use</span>
        </a>
        <a class="utility-card" href="/utility/computing/">
            <span class="utility-card-icon" aria-hidden="true">🖧</span>
            <span class="utility-card-title">Computing &amp; Networking</span>
            <span class="utility-card-desc">IP addressing, DNS/DHCP, ports, Wi-Fi, cabling, USB/serial &amp; checksums</span>
        </a>
        <a class="utility-card" href="/utility/glossary/">
            <span class="utility-card-icon" aria-hidden="true">📖</span>
            <span class="utility-card-title">Glossary</span>
            <span class="utility-card-desc">Quick definitions for terms used across this library, with links to the fuller reference</span>
        </a>
        <a class="utility-card" href="/utility/outdoor/">
            <span class="utility-card-icon" aria-hidden="true">🪢</span>
            <span class="utility-card-title">Outdoor &amp; Field</span>
            <span class="utility-card-desc">Knots and hitches for basic field utility - not a life-safety/climbing reference</span>
        </a>
        <a class="utility-card" href="/utility/mechanical/">
            <span class="utility-card-icon" aria-hidden="true">🔧</span>
            <span class="utility-card-title">Mechanical &amp; Repair</span>
            <span class="utility-card-desc">Simple machines, fasteners/torque, bearings, hand tools &amp; measurement basics</span>
        </a>
        <a class="utility-card" href="/utility/about/">
            <span class="utility-card-icon" aria-hidden="true">ℹ️</span>
            <span class="utility-card-title">About This PirateBox</span>
            <span class="utility-card-desc">What this device is, what's installed, and its current health</span>
        </a>
        <a class="utility-card" href="/utility/library/">
            <span class="utility-card-icon" aria-hidden="true">📚</span>
            <span class="utility-card-title">Document Library</span>
            <span class="utility-card-desc">Manuals and reference documents stored on this device</span>
        </a>
        <a class="utility-card" href="/utility/search/">
            <span class="utility-card-icon" aria-hidden="true">🔍</span>
            <span class="utility-card-title">Search</span>
            <span class="utility-card-desc">One search box across everything in the Utility Library</span>
        </a>
        <a class="utility-card" href="/utility/download/">
            <span class="utility-card-icon" aria-hidden="true">⬇️</span>
            <span class="utility-card-title">Take This With You</span>
            <span class="utility-card-desc">Download reference material to use after you disconnect</span>
        </a>
    </div>

    <section class="help-section">
        <h2>Also on this PirateBox</h2>
        <div class="hero-actions">
            <a href="/">Files</a>
            <a href="/chat.php">Chat</a>
            <a href="/messages.php">Logbook</a>
            <a href="/help.php">Help / About this network</a>
            <a href="/utility/status/">Status</a>
        </div>
    </section>

    <?php require_once __DIR__ . '/../../includes/footer.php'; ?>
</body>

</html>
