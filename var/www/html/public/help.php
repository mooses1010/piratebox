<?php
declare(strict_types=1);
session_start();
?>
<!doctype html>
<html lang="en">

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
        <h2>Connect</h2>
        <ol class="help-steps">
            <li>Join the Wi-Fi network named <strong>"PirateBox"</strong>. It's open - no password.</li>
            <li>If a "sign in to network" page appears, open it.</li>
            <li>If nothing opens automatically, open any web browser and type in the address:
                <br><span class="help-url">http://10.0.0.1/</span>
            </li>
        </ol>

        <div class="qr-row">
            <div>
                <div class="qr-card">
                    <img src="assets/qr-url.png" alt="QR code linking to http://10.0.0.1/" width="160" height="160">
                </div>
                <p class="qr-caption">Scan to open PirateBox (once connected to the Wi-Fi)</p>
            </div>
            <div>
                <div class="qr-card">
                    <img src="assets/qr-wifi.png" alt="QR code to join the open PirateBox Wi-Fi network" width="160" height="160">
                </div>
                <p class="qr-caption">Scan to join the "PirateBox" Wi-Fi network</p>
            </div>
        </div>
    </section>

    <section class="help-section">
        <h2>Android / Samsung</h2>
        <div class="help-note">
            <p><strong>Some modern Android and Samsung phones show "Internet may not be available"</strong> instead of a normal sign-in prompt after joining. This is expected - PirateBox is intentionally offline and doesn't provide Internet access, and some phones are cautious about that.</p>
        </div>
        <p>What to do: choose to stay connected (e.g. "Connect anyway" / "Connect only this time"), then open a browser and manually go to:</p>
        <p><span class="help-url">http://10.0.0.1/</span></p>
        <p class="muted">You do not need to install any certificate, change any security setting, or click through any HTTPS warning to use PirateBox. If a browser asks you to do any of those things, something else is going on - just use the plain address above instead.</p>
    </section>

    <section class="help-section">
        <h2>Apple, Windows &amp; Linux</h2>
        <p>A sign-in/captive window usually opens automatically on these platforms. If it doesn't, or if it closes before you're done, open a browser and go to:</p>
        <p><span class="help-url">http://10.0.0.1/</span></p>
    </section>

    <section class="help-section">
        <h2>Using PirateBox</h2>
        <ul class="help-steps">
            <li><strong>Files</strong> - the home page. Upload a file from your device, or download anything others have shared.</li>
            <li><strong>Chat</strong> - a live, shared chat room for everyone currently connected.</li>
            <li><strong>Guestbook</strong> - leave a longer message that stays for later visitors to read.</li>
        </ul>
    </section>

    <section class="help-section">
        <h2>About PirateBox</h2>
        <p>PirateBox is a small local file-sharing and messaging network, run entirely from this one device. There's no Internet connection involved anywhere - devices connected to it just talk directly to this box over Wi-Fi.</p>
        <p>Anything uploaded, chatted, or written in the guestbook is stored on this device's storage, for as long as the operator keeps it around.</p>
        <p><strong>"Offline" does not automatically mean "anonymous."</strong> Like any local network, this device can see which devices are connected and the requests they make - being offline is not, by itself, a privacy or anonymity guarantee.</p>
    </section>

    <?php require_once __DIR__ . '/../includes/footer.php'; ?>
</body>

</html>
