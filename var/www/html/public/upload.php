<?php
declare(strict_types=1);
session_start();
require_once __DIR__ . '/../includes/config.php';

// Raise the limits for this request only
ini_set('upload_max_filesize', '120M');   // maximum size of a single file
ini_set('post_max_size', '130M');   // total size of the POST body
ini_set('memory_limit', '256M');   // optional - helps with large multipart parsing

$UPLOAD_DIR = __DIR__ . '/uploads';
$MAX_SIZE = 130 * 1024 * 1024;   // 130MiB change as needed

// Make sure the uploads directory exists (same as index.php)
if (!is_dir($UPLOAD_DIR)) {
    mkdir($UPLOAD_DIR, 0755, true);
}
if (is_dir($UPLOAD_DIR) && !is_writable($UPLOAD_DIR)) {
    chmod($UPLOAD_DIR, 0755);
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !isset($_FILES['file'])) {
    header('Location: /');
    exit;
}

// CSRF Protection
if (empty($_POST['csrf_token']) || !hash_equals($_SESSION['csrf_token'] ?? '', $_POST['csrf_token'])) {
    http_response_code(403);
    exit('Invalid CSRF token.');
}

$err = $_FILES['file']['error'];
$tmp = $_FILES['file']['tmp_name'];
$name = basename($_FILES['file']['name']);

if ($err !== UPLOAD_ERR_OK) {
    $msg = "Upload error (code $err).";
} elseif ($_FILES['file']['size'] > $MAX_SIZE) {
    $msg = "File too big - limit is " . ($MAX_SIZE / 1024 / 1024) . "MiB.";
} elseif (
    ($freeBytes = @disk_free_space($UPLOAD_DIR)) !== false
    && ($freeBytes - $_FILES['file']['size']) < PIRATEBOX_MIN_FREE_BYTES
) {
    // Storage-exhaustion guard: never let an upload consume the last bit of
    // free space on the SD card. Existing files are never touched or
    // deleted to make room - the upload is simply refused before it's
    // committed to permanent storage.
    $msg = "Not enough free storage space is available to accept this upload right now. "
        . "Please try again later, or let the PirateBox operator know storage is running low.";
} else {

    // Security: Prevent PHP execution by renaming dangerous extensions
    if (preg_match('/\.(php|phtml|phar|pl|py|rb|cgi|sh|exe)$/i', $name)) {
        $name .= '.txt';
    }
    // Security: Prevent hidden system files (like .htaccess)
    if (str_starts_with($name, '.')) {
        $name = '_' . substr($name, 1);
    }
    $safe = preg_replace('/[^A-Za-z0-9._-]/', '_', $name);

    // Cap filename length. ext4 rejects a filename component over 255
    // bytes outright; without this, a very long original filename would
    // fail move_uploaded_file()/link() with a confusing "check permissions"
    // error further down instead of just... having a shorter name.
    $info = pathinfo($safe);
    $base = $info['filename'];
    $ext = isset($info['extension']) && $info['extension'] !== '' ? '.' . $info['extension'] : '';
    $maxBaseLen = 180; // leaves headroom for "_NNN" + extension well under 255
    if (strlen($base) > $maxBaseLen) {
        $base = substr($base, 0, $maxBaseLen);
    }
    if ($base === '') {
        $base = 'file';
    }

    // Receive the upload into a privately-named staging file first (the
    // random name can never collide with anything, so this step alone is
    // always safe), then atomically claim the real, user-facing filename
    // with link() - which fails with EEXIST rather than silently
    // overwriting if another request claimed that name microseconds
    // earlier. This is what actually makes two clients uploading the same
    // filename at the same moment safe: the old file_exists()-then-move
    // approach had a race where the loser's file would silently replace
    // the winner's. Both staging and the final uploads/ dir are on the
    // same filesystem (Phase 4 also moved PHP's own upload_tmp_dir here),
    // so link() always works. See docs/OPERATIONAL-DECISIONS.md.
    $staging = $UPLOAD_DIR . '/.incoming-' . bin2hex(random_bytes(16));
    if (!move_uploaded_file($tmp, $staging)) {
        $msg = "Failed to receive the uploaded file. Check permissions.";
    } else {
        $dest = $UPLOAD_DIR . '/' . $base . $ext;
        $claimed = false;
        for ($i = 0; $i <= 1000; $i++) {
            $candidate = $i === 0 ? $dest : ($UPLOAD_DIR . '/' . $base . '_' . $i . $ext);
            if (@link($staging, $candidate)) {
                $dest = $candidate;
                $claimed = true;
                break;
            }
            if (!file_exists($candidate)) {
                // link() failed for a reason other than the name already
                // existing (permissions, filesystem full, etc.) - retrying
                // with a different name won't help.
                break;
            }
        }
        @unlink($staging);

        if ($claimed) {
            // SUCCESS: redirect back to the portal UI (PRG)
            header('Location: /');
            exit;
        } else {
            $msg = "Failed to save the uploaded file. Check permissions and free space.";
        }
    }
}

?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Upload error</title>
    <link rel="stylesheet" href="styles.css">
</head>

<body class="centered-page">
    <h1>Upload error</h1>
    <p><?= htmlspecialchars($msg) ?></p>
    <p><a href="/">Back to files</a></p>
</body>

</html>