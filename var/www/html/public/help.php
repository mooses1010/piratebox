<?php
declare(strict_types=1);
session_start();
require_once __DIR__ . '/../includes/mode.php';
require_once __DIR__ . '/../includes/device_id.php';
require_once __DIR__ . '/../includes/i18n.php';
$piratebox_mode = piratebox_get_mode();
$piratebox_device_id = piratebox_get_device_id();
$piratebox_locale = piratebox_get_locale();
?>
<!doctype html>
<html lang="<?= htmlspecialchars($piratebox_locale) ?>">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Help</title>
    <link rel="stylesheet" href="assets/styles.css">
    <script src="assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../includes/navbar.php'; ?>

    <h1>Help &amp; About</h1>

    <section class="help-section">
        <p>Two different questions: this page covers <strong>how to connect and what you can do here</strong>. For <strong>what this device actually is and everything currently installed on it</strong>, see <a href="/utility/about/">About This PirateBox</a>.</p>
    </section>

    <section class="help-section">
        <h2><?= htmlspecialchars(piratebox_t('help.connect_heading')) ?></h2>
        <ol class="help-steps">
            <li><?= htmlspecialchars(piratebox_t('help.connect_step1')) ?></li>
            <li><?= htmlspecialchars(piratebox_t('help.connect_step2')) ?></li>
            <li><?= htmlspecialchars(piratebox_t('help.connect_step3')) ?>
                <br><span class="help-url">http://piratebox/</span>
                <br><span class="muted"><?= htmlspecialchars(piratebox_t('help.connect_step3_fallback')) ?> <span class="help-url">http://10.0.0.1/</span></span>
            </li>
        </ol>

        <div class="qr-row">
            <div>
                <div class="qr-card">
                    <img src="assets/qr-wifi.png" alt="QR code to join the open PirateBox Wi-Fi network" width="160" height="160">
                </div>
                <p class="qr-caption"><strong>1 &mdash; Connect to the "PirateBox" Wi-Fi</strong><br>Scan to join (open network, no password)</p>
            </div>
            <div>
                <div class="qr-card">
                    <img src="assets/qr-url.png" alt="QR code linking to http://piratebox/" width="160" height="160">
                </div>
                <p class="qr-caption"><strong>2 &mdash; Open PirateBox</strong><br>Scan once connected to the Wi-Fi above</p>
            </div>
        </div>
    </section>

    <section class="help-section">
        <h2>Connection Status</h2>
        <div class="table-wrapper">
            <table>
                <tbody>
                    <tr><td>Connected to PirateBox</td><td><strong class="status-ok">Yes</strong> - you're reading this page from it</td></tr>
                    <tr><td>Internet access</td><td>Not provided - PirateBox is intentionally offline</td></tr>
                    <tr><td>PirateBox services</td><td>Local only - everything here is served from this device</td></tr>
                    <tr><td>Local address</td><td class="help-url">http://piratebox/ <span class="muted">(or http://10.0.0.1/)</span></td></tr>
                </tbody>
            </table>
        </div>
        <p class="muted">If a "sign in to network" page didn't appear automatically, see the Android/Samsung and Apple/Windows/Linux notes below for what to do.</p>
    </section>

    <section class="help-section" id="trust">
        <h2><?= htmlspecialchars(piratebox_t('help.trust_heading')) ?></h2>
        <p><?= htmlspecialchars(piratebox_t('help.trust_intro')) ?></p>

        <div class="trust-item">
            <h3><?= htmlspecialchars(piratebox_t('help.trust_no_https_title')) ?></h3>
            <p><?= htmlspecialchars(piratebox_t('help.trust_no_https_body')) ?></p>
        </div>

        <div class="trust-item">
            <h3><?= htmlspecialchars(piratebox_t('help.trust_no_cloud_title')) ?></h3>
            <p><?= htmlspecialchars(piratebox_t('help.trust_no_cloud_body')) ?></p>
        </div>

        <div class="trust-item">
            <h3><?= htmlspecialchars(piratebox_t('help.trust_captive_title')) ?></h3>
            <p><?= htmlspecialchars(piratebox_t('help.trust_captive_body')) ?></p>
        </div>

        <div class="trust-item">
            <h3><?= htmlspecialchars(piratebox_t('help.trust_stats_title')) ?></h3>
            <p><?= htmlspecialchars(piratebox_t('help.trust_stats_body')) ?></p>
        </div>

        <div class="trust-item">
            <h3><?= htmlspecialchars(piratebox_t('help.trust_id_title')) ?></h3>
            <p><?= htmlspecialchars(piratebox_t('help.trust_id_body')) ?></p>
        </div>

        <div class="trust-item">
            <h3><?= htmlspecialchars(piratebox_t('help.trust_content_title')) ?></h3>
            <p><?= htmlspecialchars(piratebox_t('help.trust_content_body')) ?></p>
        </div>
    </section>

    <section class="help-section">
        <h2>Android / Samsung</h2>
        <div class="help-note">
            <p><strong>Some modern Android and Samsung phones show "Internet may not be available"</strong> instead of a normal sign-in prompt after joining. This is expected - PirateBox is intentionally offline and doesn't provide Internet access, and some phones are cautious about that.</p>
        </div>
        <p>What to do: choose to stay connected (e.g. "Connect anyway" / "Connect only this time"), then open a browser and manually go to:</p>
        <p><span class="help-url">http://piratebox/</span> <span class="muted">(or http://10.0.0.1/ if that doesn't open)</span></p>
        <p class="muted">You do not need to install any certificate, change any security setting, or click through any HTTPS warning to use PirateBox. If a browser asks you to do any of those things, something else is going on - just use the plain address above instead.</p>
    </section>

    <section class="help-section">
        <h2>Apple, Windows &amp; Linux</h2>
        <p>A sign-in/captive window usually opens automatically on these platforms. If it doesn't, or if it closes before you're done, open a browser and go to:</p>
        <p><span class="help-url">http://piratebox/</span> <span class="muted">(or http://10.0.0.1/ if that doesn't open)</span></p>
    </section>

    <section class="help-section">
        <h2>Using PirateBox</h2>
        <ul class="help-steps">
            <li><strong>Files</strong> - the home page. Upload a file from your device, or download anything others have shared.</li>
            <li><strong>Chat</strong> - a live, shared chat room for everyone currently connected.</li>
            <li><strong>Logbook</strong> - a visitor logbook: sign your name/handle, leave a short note, or just mark that you were here. Stays for later visitors to read.</li>
            <li><strong>Bulletin Board</strong> - post announcements, local info, or requests/offers of help, sorted by category. See <a href="/bulletin.php">Bulletin Board</a>.</li>
            <li><strong>Utility</strong> - an offline reference library: radio, emergency/outage guidance, first aid, maps, local information, manuals, and search - all built into this device, no Internet needed. See <a href="/utility/">Utility Library</a>.</li>
            <li><strong>Admin</strong> - a maintenance page for the device operator (storage/health at a glance, and a few narrow clear-data actions). Locked by a password until the operator sets one - not something a visitor can do. <strong>If you're the operator and don't have a password yet:</strong> this device's own project documentation (README.md, in its source repository) explains how to set one from the device itself - there's no default to guess.</li>
        </ul>
    </section>

    <section class="help-section">
        <h2>What is PirateBox?</h2>
        <p>PirateBox is an open, free-culture project: a small, self-contained device that creates its own local Wi-Fi network for anonymous file sharing and communication, deliberately disconnected from the Internet. It was designed in 2011 by David Darts, an artist and professor at New York University's Steinhardt School, and released under the Free Art License.</p>
        <p>Darts was inspired by pirate radio and the free culture movement, and had also been following the "Dead Drops" project (anonymous USB drives cemented into public spaces for anyone to plug into and swap files). PirateBox took that same offline, anonymous, no-permission-needed spirit and built it on Wi-Fi instead - something portable, that anyone nearby could join without special hardware.</p>
        <p>The original project ran on inexpensive OpenWrt-flashed travel routers (the TP-Link MR3020/MR3040 were common choices), plug computers, Raspberry Pis, and even Android phones. It offered a browser-based file-sharing interface, anonymous chat, and a forum/image board. It became especially popular in Western Europe - notably in France, championed by Jean Debaecker - and later development was primarily maintained by Matthias Strubel. It saw use at festivals and gigs (musicians sharing music directly with an audience), in classrooms, and at CryptoParties and other privacy/censorship-circumvention-focused events.</p>
        <p>A related project, <strong>LibraryBox</strong>, forked from PirateBox in 2012 - librarian Jason Griffey built it for educational and library use ("PirateBox without the pirate"), and its later versions were developed in concert with PirateBox itself, with some code shared back between the two projects.</p>
        <p>The original PirateBox project was <strong>discontinued on November 17, 2019</strong> - Matthias Strubel announced its closure, citing increasingly locked-down router firmware and browsers requiring HTTPS as obstacles that had become impractical to keep working around.</p>
        <p class="muted">Sources: <a href="https://en.wikipedia.org/wiki/PirateBox" target="_blank" rel="noopener">Wikipedia: PirateBox</a>; <a href="https://jasongriffey.net/librarybox/about.php" target="_blank" rel="noopener">The LibraryBox Project</a> (retrieved 2026-09-01).</p>
        <div class="help-note">
            <p><strong>This PirateBox is not an official continuation of the original project</strong> and has no affiliation with David Darts, Matthias Strubel, or the original PirateBox development team. It's an independent, modern reimplementation inspired by the original concept - built on different software (nginx, PHP, a Raspberry Pi) rather than the original's OpenWrt-router-era stack - carrying the name and spirit forward after the original's 2019 discontinuation, not maintained by or representing its original creators.</p>
        </div>
    </section>

    <section class="help-section">
        <h2>This Particular Device</h2>
        <p>This page is being served directly by the PirateBox you're connected to right now - there's no Internet involved anywhere in loading it. The website, every file, and every reference document lives on this one device's local storage; your device is talking directly to it over Wi-Fi. It's built around a Raspberry Pi, local storage, and an independent Wi-Fi access point not connected to any other network - meant to work as a portable community information and file-sharing appliance, useful sitting at home, riding in a vehicle, carried in a backpack, or set up at an event.</p>
        <p><strong>For exactly what's installed on this specific unit, what's working, and its current health</strong> - not a general description, the live, honest state of this device right now - see <a href="/utility/about/">About This PirateBox</a>.</p>

        <?php if ($piratebox_device_id !== null): ?>
            <p>Device ID: <strong class="help-url"><?= htmlspecialchars($piratebox_device_id) ?></strong> <span class="muted">- a random, non-sensitive label for this specific appliance, not derived from any hardware identifier. See <a href="/found/">Found This Device</a> if this unit seems lost or displaced.</span></p>
        <?php endif; ?>

        <div class="help-note utility-placeholder-note">
            <p><strong>Photo pending:</strong> a photograph of this PirateBox's actual physical build will be added here once the hardware is finished - not a stock photo or a generated image, just this note until then.</p>
        </div>
    </section>

    <section class="help-section">
        <h2>If You Encounter This Network</h2>
        <p>PirateBox is portable and may sometimes run unattended. The physical device itself might not be obvious - it may be placed somewhere protected from weather, accidental damage, theft, or interference, simply as part of normal, sensible operation.</p>
        <p><strong>Seeing the "PirateBox" Wi-Fi network is not, by itself, a reason to go looking for the physical hardware.</strong> You're welcome to connect and use whatever it offers - the network isn't dangerous, and it isn't surveillance equipment. There's normally no reason to locate, move, or disturb the appliance itself just because you can see its Wi-Fi signal.
        <?php if ($piratebox_mode === PIRATEBOX_MODE_EMERGENCY): ?>
            In fact, during a situation like this one, leaving an appropriately-placed PirateBox running and undisturbed helps make sure its offline emergency and reference resources stay available to others nearby who may also need them.
        <?php endif; ?>
        </p>
        <p class="muted">Of course, legitimate safety or property concerns always come first - if something about a specific situation genuinely needs attention, use your own judgment. This is just general guidance, not a rule that overrides common sense.</p>
        <p class="muted">If you've physically found this device and think it may be lost, displaced, or abandoned (rather than just seeing its Wi-Fi signal from a distance), see <a href="/found/">About &rarr; Found This Device</a>.</p>
    </section>

    <?php require_once __DIR__ . '/../includes/footer.php'; ?>
</body>

</html>
