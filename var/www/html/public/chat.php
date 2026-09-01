<?php
declare(strict_types=1);
session_start();

if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

$DATA_FILE = __DIR__ . '/../data/chat.json';
$chat = [];
$chat_size = 100;

// Read file
if (file_exists($DATA_FILE)) {
    $json = file_get_contents($DATA_FILE);
    if ($json !== false) {
        $decoded = json_decode($json, true);
        if (is_array($decoded)) {
            $chat = $decoded;
        } elseif (trim($json) !== '') {
            // Non-empty but not valid JSON - surface this rather than
            // silently starting over, so corruption is at least visible
            // in the php-fpm log.
            error_log('PirateBox: chat.json failed to decode (' . json_last_error_msg() . '); showing empty history until the next successful write.');
        }
    }
}

// Used by javascript to fetch json data using ?fetch=1
if (isset($_GET['fetch'])) {
    header('Content-Type: application/json');
    echo json_encode($chat);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST["message"]) && isset($_POST["name"])) {
    if (empty($_POST['csrf_token']) || !hash_equals($_SESSION['csrf_token'] ?? '', $_POST['csrf_token'])) {
        http_response_code(403);
        exit('Invalid CSRF token.');
    }

    $name = trim(strip_tags($_POST['name'] ?? ''));
    $message = trim(strip_tags($_POST['message'] ?? ''));

    // Server-side length caps matching the client-side maxlength attributes
    // (32 / 2000) - those are a UX nicety, not a security boundary, since
    // any raw POST can ignore them. Truncating rather than rejecting keeps
    // this forgiving for a slightly-over-limit legitimate paste, while
    // still bounding how much a single message can grow chat.json by.
    $name = mb_substr($name, 0, 32);
    $message = mb_substr($message, 0, 2000);

    if ($name === '') {
        $name = 'Anonymous';
    }

    if ($message !== '') {
        // Serialize concurrent writers with an exclusive lock, then re-read the
        // file while holding it so we never overwrite another request's message
        // (multiple people can post/poll within the same second).
        $lockHandle = fopen($DATA_FILE . '.lock', 'c');
        if ($lockHandle !== false && flock($lockHandle, LOCK_EX)) {
            $chat = [];
            if (file_exists($DATA_FILE)) {
                $json = file_get_contents($DATA_FILE);
                if ($json !== false) {
                    $decoded = json_decode($json, true);
                    if (is_array($decoded)) {
                        $chat = $decoded;
                    } elseif (trim($json) !== '') {
                        error_log('PirateBox: chat.json failed to decode (' . json_last_error_msg() . ') while posting a new message; continuing from empty history.');
                    }
                }
            }

            $next_id = (count($chat) > 0) ? $chat[count($chat) - 1]["id"] + 1 : 0;

            $newChat = [
                "id" => $next_id,
                "name" => $name,
                "message" => $message,
                "timestamp" => time()
            ];

            // Add to the end of the array (Newest last)
            $chat[] = $newChat;

            if (count($chat) > $chat_size) {
                $chat = array_slice($chat, -$chat_size);
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
            if (file_put_contents($tmpFile, json_encode($chat, JSON_PRETTY_PRINT)) !== false) {
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
    }
}

?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Live Chat</title>
    <link rel="stylesheet" href="assets/styles.css">
    <script src="assets/scripts.js"></script>
</head>

<body class="chat-page">
    <?php require_once __DIR__ . '/../includes/navbar.php'; ?>
    <h1>Chat</h1>
    <ul id="chat" data-last-message-id="<?= !empty($chat) ? $chat[count($chat) - 1]['id'] : -1 ?>">
        <?php if (empty($chat)): ?>
            <li class="muted empty-state" style="text-align:center;">No messages yet - say hello!</li>
        <?php endif; ?>
        <?php foreach ($chat as $msg): ?>
            <li>
                <small>
                    <span class="chat-name"><?= htmlspecialchars($msg['name']) ?></span> (<span class="chat-timestamp" data-timestamp="<?= $msg['timestamp'] ?>"><?= date('Y-m-d H:i', $msg['timestamp']) ?></span>):
                </small>
                <span><?= htmlspecialchars($msg['message']) ?></span>
            </li>
        <?php endforeach; ?>
        <template>
            <li class="pending">
                <small>…</small>
                <span>…</span>
            </li>
        </template>
    </ul>

    <form id="chat-form" method="post" action="chat.php">
        <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
        <div class="input-group">
            <input type="text" name="name" placeholder="Anonymous" maxlength="32">
            <input type="text" name="message" placeholder="Message" maxlength="2000" autofocus>
            <button type="submit">Send</button>
        </div>
        <div class="char-counter">
            <span id="char-count">0 / 2000</span>
        </div>
    </form>

</body>

</html>