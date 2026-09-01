<?php
declare(strict_types=1);
session_start();

// Community Bulletin Board (Stage 22).
//
// Deliberately modeled on messages.php's Guestbook - same JSON flat-file
// store, same flock()-based atomic write, same CSRF token, same
// server-side length caps, same stale-tmp cleanup, same "newest first,
// capped list" retention. The only real difference is one extra field
// (category) and a slightly larger cap (200 vs the Guestbook's 100),
// since this is meant to carry more operationally useful traffic during
// an actual emergency - road closures, "meeting point is X", "need
// water at address Y" - not just casual messages.
//
// This is a COMMUNITY board, not a moderated one: anyone on the network
// can post, same as Chat/Guestbook, and the only cleanup lever is the
// existing admin "clear" action (see admin/index.php) - no per-post
// delete, no accounts, nothing new to keep secure. Categories are a
// plain client-supplied string validated against a fixed allowlist
// server-side (never trusted freeform), used only to color/group the
// post - they carry no other behavior (no routing, no notification, no
// priority queue).

$DATA_FILE = __DIR__ . '/../data/bulletin.json';
$posts = [];
$post_cap = 200;

$CATEGORIES = [
    'announcement' => 'Announcement',
    'info'         => 'Info / Update',
    'need-help'    => 'Need Help',
    'offering-help' => 'Offering Help',
];

if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

if (file_exists($DATA_FILE)) {
    $json = file_get_contents($DATA_FILE);
    if ($json !== false) {
        $decoded = json_decode($json, true);
        if (is_array($decoded)) {
            $posts = $decoded;
        } elseif (trim($json) !== '') {
            error_log('PirateBox: bulletin.json failed to decode (' . json_last_error_msg() . '); showing empty board until the next successful write.');
        }
    }
}

// Used by javascript to fetch json data using ?fetch=1 (badge polling, same
// technique as chat.php/messages.php).
if (isset($_GET['fetch'])) {
    header('Content-Type: application/json');
    echo json_encode($posts);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['message']) && isset($_POST['name'])) {
    if (empty($_POST['csrf_token']) || !hash_equals($_SESSION['csrf_token'] ?? '', $_POST['csrf_token'])) {
        http_response_code(403);
        exit('Invalid CSRF token.');
    }

    $name = trim(strip_tags($_POST['name'] ?? ''));
    $content = trim(strip_tags($_POST['message'] ?? ''));
    $category = $_POST['category'] ?? 'info';
    if (!isset($CATEGORIES[$category])) {
        $category = 'info';
    }

    $name = mb_substr($name, 0, 32);
    $content = mb_substr($content, 0, 2000);

    if ($name === '') {
        $name = 'Anonymous';
    }

    if ($content !== '') {
        $lockHandle = fopen($DATA_FILE . '.lock', 'c');
        if ($lockHandle !== false && flock($lockHandle, LOCK_EX)) {
            $posts = [];
            if (file_exists($DATA_FILE)) {
                $json = file_get_contents($DATA_FILE);
                if ($json !== false) {
                    $decoded = json_decode($json, true);
                    if (is_array($decoded)) {
                        $posts = $decoded;
                    } elseif (trim($json) !== '') {
                        error_log('PirateBox: bulletin.json failed to decode (' . json_last_error_msg() . ') while posting; continuing from empty board.');
                    }
                }
            }

            $next_id = (!empty($posts) && isset($posts[0]['id'])) ? $posts[0]['id'] + 1 : 0;

            $newPost = [
                'id' => $next_id,
                'name' => $name,
                'category' => $category,
                'message' => $content,
                'timestamp' => time(),
            ];

            array_unshift($posts, $newPost);

            if (count($posts) > $post_cap) {
                $posts = array_slice($posts, 0, $post_cap);
            }

            foreach (glob($DATA_FILE . '.tmp.*') ?: [] as $staleTmp) {
                if (is_file($staleTmp) && (time() - (int) filemtime($staleTmp)) > 300) {
                    @unlink($staleTmp);
                }
            }

            $tmpFile = $DATA_FILE . '.tmp.' . getmypid() . '.' . bin2hex(random_bytes(4));
            if (file_put_contents($tmpFile, json_encode($posts, JSON_PRETTY_PRINT)) !== false) {
                if (!rename($tmpFile, $DATA_FILE)) {
                    error_log("PirateBox: failed to rename $tmpFile to $DATA_FILE; the new bulletin post was not saved.");
                    @unlink($tmpFile);
                }
            }

            flock($lockHandle, LOCK_UN);
        }
        if ($lockHandle !== false) {
            fclose($lockHandle);
        }

        header('Location: bulletin.php');
        exit;
    }
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Bulletin Board</title>
    <link rel="stylesheet" href="assets/styles.css">
    <script src="assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../includes/navbar.php'; ?>
    <h1>Community Bulletin Board</h1>
    <p class="muted" style="text-align:center;">Announcements, local info, and requests/offers of help - visible to anyone connected to this PirateBox. Posts aren't private and aren't moderated beyond what an operator clears manually.</p>

    <form id="bulletin-form" action="bulletin.php" method="post">
        <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
        <label>Name:
            <input type="text" name="name" placeholder="Anonymous" maxlength="32">
        </label>
        <label>Category:
            <select name="category">
                <?php foreach ($CATEGORIES as $key => $label): ?>
                    <option value="<?= htmlspecialchars($key) ?>"<?= $key === 'info' ? ' selected' : '' ?>><?= htmlspecialchars($label) ?></option>
                <?php endforeach; ?>
            </select>
        </label>
        <label>Message:
            <textarea name="message" required rows="3" placeholder="What do you want the network to know?" maxlength="2000"></textarea>
        </label>
        <button type="submit">Post to Bulletin Board</button>
        <div class="char-counter">
            <span id="char-count">0 / 2000</span>
        </div>
    </form>

    <div class="message-container">
        <?php if (empty($posts)): ?>
            <p class="empty-state">No bulletin posts yet. Be the first!</p>
        <?php else: ?>
            <?php foreach ($posts as $post): ?>
                <?php $cat = $CATEGORIES[$post['category'] ?? 'info'] ?? 'Info / Update'; ?>
                <div class="message-card">
                    <div class="message-header">
                        <span class="message-name">
                            <?= htmlspecialchars($post['name']) ?>
                            <span class="bulletin-category bulletin-category-<?= htmlspecialchars($post['category'] ?? 'info') ?>"><?= htmlspecialchars($cat) ?></span>
                        </span>
                        <span class="message-time" data-timestamp="<?= $post['timestamp'] ?>"><?= date('Y-m-d H:i', $post['timestamp']) ?></span>
                    </div>
                    <div class="message-body"><?= htmlspecialchars($post['message']) ?></div>
                </div>
            <?php endforeach; ?>
        <?php endif; ?>
    </div>

    <?php require_once __DIR__ . '/../includes/footer.php'; ?>
</body>

</html>
