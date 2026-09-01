<?php
declare(strict_types=1);
session_start();
require_once __DIR__ . '/../../includes/device_id.php';

// Found Device / Local Recovery Messages (Stage 16).
//
// A privacy-conscious, entirely local finder<->operator message system,
// deliberately kept separate from Chat/Guestbook/uploads/normal public
// content (its own data file, never mixed with theirs). No operator PII
// (name/phone/email/address) is ever displayed here. Finder contact info
// is entirely optional. Messages never leave this device - there is no
// Internet connection for them to leave over in the first place.
//
// Rate-limiting is intentionally simple and non-invasive: a short global
// cooldown between accepted submissions (checked against the store's own
// last entry, under the same lock already used for the write - no new
// per-client tracking file), and a session-only cooldown on lookups. No
// IP logging, no device fingerprinting, minimal metadata collected.

if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

$DATA_FILE = __DIR__ . '/../../data/recovery-messages.json';
$SUBMIT_COOLDOWN_SECONDS = 30;
$LOOKUP_COOLDOWN_SECONDS = 5;
$CODE_ALPHABET = '23456789ABCDEFGHJKMNPQRSTUVWXYZ'; // no 0/O/1/I/L - easy to read/type back

function recovery_load(string $path): array
{
    if (!file_exists($path)) return [];
    $raw = @file_get_contents($path);
    if ($raw === false) return [];
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

function recovery_gen_code(string $alphabet): string
{
    $part = function (int $len) use ($alphabet): string {
        $out = '';
        $max = strlen($alphabet) - 1;
        for ($i = 0; $i < $len; $i++) {
            $out .= $alphabet[random_int(0, $max)];
        }
        return $out;
    };
    return $part(4) . '-' . $part(2);
}

$submitResult = null; // ['ok' => bool, 'msg' => string, 'code' => ?string]
$lookupResult = null; // ['found' => bool, 'entry' => ?array]

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (empty($_POST['csrf_token']) || !hash_equals($_SESSION['csrf_token'] ?? '', $_POST['csrf_token'])) {
        http_response_code(403);
        exit('Invalid CSRF token.');
    }

    $action = $_POST['action'] ?? '';

    if ($action === 'submit_recovery') {
        $message = trim(strip_tags($_POST['message'] ?? ''));
        $contact = trim(strip_tags($_POST['contact'] ?? ''));
        $message = mb_substr($message, 0, 1000);
        $contact = mb_substr($contact, 0, 200);

        if ($message === '') {
            $submitResult = ['ok' => false, 'msg' => 'Please enter a message before submitting.', 'code' => null];
        } else {
            $lockHandle = fopen($DATA_FILE . '.lock', 'c');
            if ($lockHandle !== false && flock($lockHandle, LOCK_EX)) {
                $entries = recovery_load($DATA_FILE);

                $lastSubmitted = !empty($entries) ? (int) ($entries[count($entries) - 1]['submitted_at_unix'] ?? 0) : 0;
                if (time() - $lastSubmitted < $SUBMIT_COOLDOWN_SECONDS) {
                    $submitResult = ['ok' => false, 'msg' => 'Please wait a moment before submitting another message.', 'code' => null];
                } else {
                    do {
                        $code = recovery_gen_code($CODE_ALPHABET);
                    } while (array_filter($entries, fn($e) => ($e['code'] ?? null) === $code));

                    $entries[] = [
                        'code' => $code,
                        'message' => $message,
                        'contact' => $contact,
                        'submitted_at' => date('Y-m-d H:i'),
                        'submitted_at_unix' => time(),
                        'reply' => null,
                        'replied_at' => null,
                        'status' => 'new',
                    ];

                    $tmpFile = $DATA_FILE . '.tmp.' . getmypid() . '.' . bin2hex(random_bytes(4));
                    if (file_put_contents($tmpFile, json_encode($entries, JSON_PRETTY_PRINT)) !== false) {
                        if (rename($tmpFile, $DATA_FILE)) {
                            $submitResult = ['ok' => true, 'msg' => 'Message received - thank you.', 'code' => $code];
                        } else {
                            @unlink($tmpFile);
                            $submitResult = ['ok' => false, 'msg' => 'Something went wrong saving your message - please try again.', 'code' => null];
                        }
                    }
                }
                flock($lockHandle, LOCK_UN);
            }
            if ($lockHandle !== false) fclose($lockHandle);
        }
    } elseif ($action === 'lookup_recovery') {
        $lastLookup = (int) ($_SESSION['recovery_last_lookup'] ?? 0);
        if (time() - $lastLookup < $LOOKUP_COOLDOWN_SECONDS) {
            $lookupResult = ['found' => false, 'entry' => null, 'throttled' => true];
        } else {
            $_SESSION['recovery_last_lookup'] = time();
            $codeInput = strtoupper(trim($_POST['code'] ?? ''));
            $entries = recovery_load($DATA_FILE);
            $match = null;
            foreach ($entries as $e) {
                if (($e['code'] ?? null) === $codeInput) {
                    $match = $e;
                    break;
                }
            }
            $lookupResult = ['found' => $match !== null, 'entry' => $match, 'throttled' => false];
        }
    }
}

$deviceId = piratebox_get_device_id();
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Found This Device</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../includes/navbar.php'; ?>

    <h1>Found This Device</h1>

    <section class="help-section">
        <p>PirateBox is a small, self-contained offline Wi-Fi appliance - a local file-sharing and reference network, not connected to the Internet. <a href="/help.php">Read more about what PirateBox is</a>.</p>

        <div class="help-note">
            <p><strong>Just seeing the "PirateBox" Wi-Fi network?</strong> That's not a reason to look for the physical device - you're welcome to connect and use what it offers. There's normally no need to locate it.</p>
        </div>

        <p>If you've <strong>physically found the appliance itself</strong> and think it may be lost, displaced, or abandoned: it's an offline network appliance, not dangerous, and not something that needs to be reset, erased, or taken apart just because it was found. If it's safe and reasonable to do so, please leave it where it is (or somewhere equally safe) and consider leaving a message below so the operator knows where it is.</p>

        <p class="muted"><strong>Safety and property concerns always come first.</strong> If leaving it in place isn't appropriate for your situation, use your own judgment - this page is guidance, not a rule that overrides it.</p>

        <?php if ($deviceId !== null): ?>
            <p>This device's ID: <strong class="help-url"><?= htmlspecialchars($deviceId) ?></strong> <span class="muted">(mention this if you contact anyone about it)</span></p>
        <?php endif; ?>
    </section>

    <section class="help-section">
        <h2>Leave a Recovery Message</h2>
        <p class="muted">Messages are stored locally on this PirateBox and are not transmitted over the Internet - there's no connection for them to leave over. The operator reviews messages here and decides whether and how to respond. Your contact information is entirely optional.</p>

        <?php if ($submitResult !== null): ?>
            <p style="text-align:center;"><strong class="<?= $submitResult['ok'] ? 'status-ok' : 'status-bad' ?>"><?= htmlspecialchars($submitResult['msg']) ?></strong></p>
            <?php if ($submitResult['ok'] && $submitResult['code']): ?>
                <div class="help-note">
                    <p><strong>Your recovery code:</strong> <span class="help-url"><?= htmlspecialchars($submitResult['code']) ?></span></p>
                    <p>Write this down. You can return to this page later, enter this code below, and see if the operator has replied - without revealing any contact information to do so.</p>
                </div>
            <?php endif; ?>
        <?php endif; ?>

        <form method="post">
            <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
            <input type="hidden" name="action" value="submit_recovery">
            <label>Your message
                <textarea name="message" maxlength="1000" rows="4" required placeholder="e.g. I found this near ___. It looked safe so I left it there."></textarea>
            </label>
            <label>Contact info (optional)
                <input type="text" name="contact" maxlength="200" placeholder="Only if you want a way to be reached - entirely optional">
            </label>
            <button type="submit">Send Message</button>
        </form>
    </section>

    <section class="help-section">
        <h2>Check for a Reply</h2>
        <p class="muted">Enter the recovery code you received when you submitted a message.</p>

        <?php if ($lookupResult !== null): ?>
            <?php if (!empty($lookupResult['throttled'])): ?>
                <p style="text-align:center;"><strong class="status-bad">Please wait a moment before trying again.</strong></p>
            <?php elseif ($lookupResult['found']): ?>
                <div class="message-card">
                    <div class="message-header">
                        <span class="message-name">Your message</span>
                        <span class="message-time"><?= htmlspecialchars($lookupResult['entry']['submitted_at']) ?></span>
                    </div>
                    <div class="message-body"><?= htmlspecialchars($lookupResult['entry']['message']) ?></div>
                </div>
                <?php if (!empty($lookupResult['entry']['reply'])): ?>
                    <div class="message-card">
                        <div class="message-header">
                            <span class="message-name">Operator reply</span>
                            <span class="message-time"><?= htmlspecialchars($lookupResult['entry']['replied_at'] ?? '') ?></span>
                        </div>
                        <div class="message-body"><?= htmlspecialchars($lookupResult['entry']['reply']) ?></div>
                    </div>
                <?php else: ?>
                    <p class="empty-state">No reply yet - check back later.</p>
                <?php endif; ?>
            <?php else: ?>
                <p style="text-align:center;"><strong class="status-bad">Code not found.</strong></p>
            <?php endif; ?>
        <?php endif; ?>

        <form method="post">
            <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
            <input type="hidden" name="action" value="lookup_recovery">
            <label>Recovery code
                <input type="text" name="code" maxlength="16" placeholder="e.g. H7K2-MQ" required style="text-transform:uppercase;">
            </label>
            <button type="submit">Check</button>
        </form>
    </section>

    <div class="hero-actions">
        <a href="/help.php">Help / About</a>
        <a href="/">Home</a>
    </div>

    <?php require_once __DIR__ . '/../../includes/footer.php'; ?>
</body>

</html>
