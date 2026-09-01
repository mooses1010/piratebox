<?php
declare(strict_types=1);
session_start();
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/../includes/helpers.php';

if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

ini_set('upload_max_filesize', '120M');   // maximum size of a single file
ini_set('post_max_size', '130M');   // total size of the POST body
ini_set('memory_limit', '256M');   // optional: helps with large multipart parsing

$UPLOAD_DIR = __DIR__ . '/uploads';
$MAX_SIZE = 120 * 1024 * 1024; // 120MiB per file (adjust as you wish)
$OPEN_FILE_TYPES = ['mp4','mp3','png','jpg','jpeg','gif'];

// Ensure the upload folder exists
if (!is_dir($UPLOAD_DIR)) {
    mkdir($UPLOAD_DIR, 0755, true);
}

$files = [];
foreach ((is_dir($UPLOAD_DIR) ? scandir($UPLOAD_DIR) : []) as $entry) {
    if ($entry === '.' || $entry === '..')
        continue;

    // Skip dotfiles - in particular upload.php's brief ".incoming-*"
    // staging files (see upload.php), which should never normally be
    // visible here but could linger if a worker were killed mid-upload.
    if (str_starts_with($entry, '.'))
        continue;

    $fullPath = $UPLOAD_DIR . '/' . $entry;

    if (!is_file($fullPath))
        continue;

    // A file can vanish between scandir() and here (e.g. an admin purge
    // running at the same moment someone is loading this page) - skip it
    // rather than showing a broken row with a false/empty size or date.
    $size = @filesize($fullPath);
    $mtime = @filemtime($fullPath);
    if ($size === false || $mtime === false)
        continue;

    $files[] = [
        'name' => $entry,
        'size' => $size,
        'uploaded' => $mtime,   // timestamp of last modification (upload time)
    ];
}

// Sort newest first
usort($files, fn($a, $b) => $b['uploaded'] <=> $a['uploaded']);

// Storage visibility (Phase 4) - reuses the same PIRATEBOX_MIN_FREE_BYTES
// reserve upload.php enforces (see includes/config.php), so the number
// shown here always matches the point at which an upload actually gets
// rejected. Shown as a friendly warning once free space is within 2x the
// reserve, well before it actually blocks anything.
$freeBytes = @disk_free_space($UPLOAD_DIR);
$lowStorage = $freeBytes !== false && $freeBytes < (PIRATEBOX_MIN_FREE_BYTES * 2);
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Offline File Share</title>
    <link rel="stylesheet" href="assets/styles.css">
    <script src="assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../includes/navbar.php'; ?>

    <div class="hero">
        <div class="hero-tagline">Offline File Sharing</div>
        <h1>PirateBox</h1>
        <p>This is a local, offline network - no Internet connection is used or required. Share files, chat, and leave messages with anyone else connected to this Wi-Fi.</p>
        <div class="hero-actions">
            <a href="#upload-form">Upload a file</a>
            <a href="chat.php">Chat</a>
            <a href="messages.php">Guestbook</a>
            <a href="help.php">Help</a>
        </div>
    </div>

    <?php if (!empty($msg)): ?>
        <p style="text-align:center;"><strong><?= htmlspecialchars($msg) ?></strong></p>
    <?php endif; ?>

    <form action="/upload.php" method="post" enctype="multipart/form-data" id="upload-form">
        <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
        <label>Select a file (max <?= $MAX_SIZE / 1024 / 1024 ?>MiB):
            <input type="file" name="file" required data-max-size="<?= $MAX_SIZE ?>">
        </label>
        <span id="selected-filename" class="muted" aria-live="polite"></span>
        <button type="submit">Upload</button>
        <div class="upload-progress" id="upload-progress" hidden>
            <div class="upload-progress-bar" id="upload-progress-bar"></div>
        </div>
    </form>

    <?php if ($freeBytes !== false): ?>
        <p class="storage-notice<?= $lowStorage ? ' low' : '' ?>">
            <?= $lowStorage ? 'Storage is running low - ' : '' ?><?= piratebox_fmt_bytes((int) $freeBytes) ?> free
        </p>
    <?php endif; ?>

    <?php if (empty($files)): ?>
        <p class="empty-state">No files uploaded yet - be the first to share something!</p>
    <?php else: ?>
        <h2>Available files</h2>
        <div class="list-controls">
            <div class="search-container">
                <input type="text" id="fileSearch" placeholder="Search files..." aria-label="Search files">
            </div>
            <label for="fileSort">Sort by
                <select id="fileSort" aria-label="Sort files">
                    <option value="newest">Newest</option>
                    <option value="oldest">Oldest</option>
                    <option value="name">Name</option>
                    <option value="size">Size</option>
                </select>
            </label>
        </div>
        <div class="table-wrapper">
            <table id="file-table">
                <thead>
                    <tr>
                        <th class="sortable" data-sort-key="name">Name</th>
                        <th class="sortable" data-sort-key="size">Size</th>
                        <th class="sortable" data-sort-key="uploaded">Uploaded</th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($files as $f): ?>
                        <?php
                        $download = "";
                        if (!in_array(pathinfo(rawurlencode($f['name']), PATHINFO_EXTENSION), $OPEN_FILE_TYPES)) {
                            $download = "download";
                        }
                        ?>
                        <tr data-name="<?= htmlspecialchars(strtolower($f['name'])) ?>" data-size="<?= $f['size'] ?>" data-uploaded="<?= $f['uploaded'] ?>">
                            <td><a href="uploads/<?= rawurlencode($f['name']) ?>" <?= $download ?>><?= htmlspecialchars($f['name']) ?></a></td>
                            <td><?= piratebox_fmt_bytes($f['size']) ?></td>
                            <td><span class="file-timestamp" data-timestamp="<?= $f['uploaded'] ?>"><?= date('Y-m-d H:i', $f['uploaded']) ?></span></td>
                        </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        </div>
    <?php endif; ?>

    <?php require_once __DIR__ . '/../includes/footer.php'; ?>
</body>

</html>