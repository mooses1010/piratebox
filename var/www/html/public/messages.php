<?php
declare(strict_types=1);
session_start();
require_once __DIR__ . '/../includes/storage_guard.php';

$postError = null;

if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

$DATA_FILE = __DIR__ . '/../data/messages.json';
$messages = [];
$message_size = 100;

// Read file
if (file_exists($DATA_FILE)) {
    $json = file_get_contents($DATA_FILE);
    if ($json !== false) {
        $decoded = json_decode($json, true);
        if (is_array($decoded)) {
            $messages = $decoded;
        } elseif (trim($json) !== '') {
            // Non-empty but not valid JSON - surface this rather than
            // silently starting over, so corruption is at least visible
            // in the php-fpm log.
            error_log('PirateBox: messages.json failed to decode (' . json_last_error_msg() . '); showing empty history until the next successful write.');
        }
    }
}

// Used by javascript to fetch json data using ?fetch=1
if (isset($_GET['fetch'])) {
    header('Content-Type: application/json');
    echo json_encode($messages);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST["message"]) && isset($_POST["name"])) {
    if (empty($_POST['csrf_token']) || !hash_equals($_SESSION['csrf_token'] ?? '', $_POST['csrf_token'])) {
        http_response_code(403);
        exit('Invalid CSRF token.');
    }

    $name = trim(strip_tags($_POST['name'] ?? ''));
    $content = trim(strip_tags($_POST['message'] ?? ''));

    // Server-side length caps matching the client-side maxlength attributes
    // (32 / 2000) - those are a UX nicety, not a security boundary, since
    // any raw POST can ignore them. Truncating rather than rejecting keeps
    // this forgiving for a slightly-over-limit legitimate paste, while
    // still bounding how much a single message can grow messages.json by.
    $name = mb_substr($name, 0, 32);
    $content = mb_substr($content, 0, 2000);

    // A logbook entry needs *something* deliberately provided - either a
    // name/handle, a message, or both. Check this before defaulting an
    // empty name to "Anonymous" below, so a genuinely blank submission
    // (nothing typed in either field) still produces no entry at all,
    // exactly as before - it must not turn into a bare "Anonymous" ghost
    // row with an empty body just because the default filled the name in.
    $hasEntry = ($name !== '' || $content !== '');

    if ($name === '') {
        $name = 'Anonymous';
    }

    // Stage 24: check free space BEFORE attempting the write, same guard
    // upload.php already had - a silent file_put_contents() failure under
    // genuine storage exhaustion would otherwise drop the message with no
    // indication to the poster that it wasn't saved.
    if ($hasEntry && piratebox_low_storage(dirname($DATA_FILE))) {
        $postError = 'Not enough free storage space is available to save this entry right now. Please try again later, or let the PirateBox operator know storage is running low.';
    } elseif ($hasEntry) {
        // Serialize concurrent writers with an exclusive lock, then re-read the
        // file while holding it so we never overwrite another request's message
        // (multiple people can post/poll within the same second).
        $lockHandle = fopen($DATA_FILE . '.lock', 'c');
        if ($lockHandle !== false && flock($lockHandle, LOCK_EX)) {
            $messages = [];
            if (file_exists($DATA_FILE)) {
                $json = file_get_contents($DATA_FILE);
                if ($json !== false) {
                    $decoded = json_decode($json, true);
                    if (is_array($decoded)) {
                        $messages = $decoded;
                    } elseif (trim($json) !== '') {
                        error_log('PirateBox: messages.json failed to decode (' . json_last_error_msg() . ') while posting a new message; continuing from empty history.');
                    }
                }
            }

            $next_id = (!empty($messages) && isset($messages[0]['id'])) ? $messages[0]['id'] + 1 : 0;

            $newMessage = [
                'id' => $next_id,
                'name' => $name,
                'message' => $content,
                'timestamp' => time()
            ];

            // Add to the beginning of the array (Newest first)
            array_unshift($messages, $newMessage);

            if (count($messages) > $message_size) {
                $messages = array_slice($messages, 0, $message_size);
            }

            // Opportunistically clean up any stale temp files left behind by a
            // previous crash/power-loss mid-write (harmless if none exist;
            // safe to do here since we already hold the exclusive lock).
            foreach (glob($DATA_FILE . '.tmp.*') ?: [] as $staleTmp) {
                if (is_file($staleTmp) && (time() - (int) filemtime($staleTmp)) > 300) {
                    @unlink($staleTmp);
                }
            }

            // Atomic write: write to a temp file then rename over the real file,
            // so concurrent unlocked readers (the ?fetch=1 poll) never see a
            // partially-written file.
            $tmpFile = $DATA_FILE . '.tmp.' . getmypid() . '.' . bin2hex(random_bytes(4));
            if (file_put_contents($tmpFile, json_encode($messages, JSON_PRETTY_PRINT)) !== false) {
                if (!rename($tmpFile, $DATA_FILE)) {
                    error_log("PirateBox: failed to rename $tmpFile to $DATA_FILE; the new message was not saved.");
                    @unlink($tmpFile);
                }
            }

            flock($lockHandle, LOCK_UN);
        }
        if ($lockHandle !== false) {
            fclose($lockHandle);
        }

        // Redirect to avoid resubmission
        header('Location: messages.php');
        exit;
    }
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Logbook</title>
    <link rel="stylesheet" href="assets/styles.css">
    <script src="assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../includes/navbar.php'; ?>
    <h1>Logbook</h1>
    <p class="muted" style="text-align:center;">Sign the PirateBox logbook - leave your name or handle, a short note, or simply mark that you were here.</p>

    <?php if ($postError !== null): ?>
        <p style="text-align:center;"><strong class="status-bad"><?= htmlspecialchars($postError) ?></strong></p>
    <?php endif; ?>

    <form id="message-form" action="messages.php" method="post">
        <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
        <label>Name / handle / callsign:
            <input type="text" name="name" placeholder="Anonymous" maxlength="32" value="<?= $postError !== null ? htmlspecialchars($_POST['name'] ?? '') : '' ?>">
        </label>
        <label>Message (optional):
            <textarea name="message" rows="3" placeholder="Optional - add a note, or leave blank to just sign in" maxlength="2000"><?= $postError !== null ? htmlspecialchars($_POST['message'] ?? '') : '' ?></textarea>
        </label>
        <button type="submit">Sign Logbook</button>
        <div class="char-counter">
            <span id="char-count">0 / 2000</span>
        </div>
    </form>

    <div class="message-container">
        <?php if (empty($messages)): ?>
            <p class="empty-state">No entries yet. Be the first to sign in!</p>
        <?php else: ?>
            <?php foreach ($messages as $msg): ?>
                <div class="message-card">
                    <div class="message-header">
                        <span class="message-name"><?= htmlspecialchars($msg['name']) ?></span>
                        <span class="message-time" data-timestamp="<?= $msg['timestamp'] ?>"><?= date('Y-m-d H:i', $msg['timestamp']) ?></span>
                    </div>
                    <?php if (($msg['message'] ?? '') !== ''): ?>
                        <div class="message-body"><?= htmlspecialchars($msg['message']) ?></div>
                    <?php endif; ?>
                </div>
            <?php endforeach; ?>
        <?php endif; ?>
    </div>

    <?php require_once __DIR__ . '/../includes/footer.php'; ?>
</body>

</html>