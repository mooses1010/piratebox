<?php
declare(strict_types=1);
session_start();
require_once __DIR__ . '/../includes/config.php';
require_once __DIR__ . '/../includes/helpers.php';
require_once __DIR__ . '/../includes/mode.php';
require_once __DIR__ . '/../includes/metrics.php';

$piratebox_mode = piratebox_get_mode();
$connStats = piratebox_get_connection_stats();

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
    <title><?= $piratebox_mode === PIRATEBOX_MODE_EMERGENCY ? 'PirateBox - Local Emergency Information Network' : 'PirateBox - Offline File Share' ?></title>
    <link rel="stylesheet" href="assets/styles.css">
    <script src="assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../includes/navbar.php'; ?>

    <?php if ($connStats !== null): ?>
        <p class="conn-status-line muted" style="text-align:center;" title="Counts Wi-Fi association activity, not people or devices - a device that disconnects and reconnects (e.g. Wi-Fi sleep/wake) is counted again. See the Stats page for detail.">
            <span class="<?= $connStats['current'] > 0 ? 'status-ok' : '' ?>">&#9679;</span>
            <?= $connStats['current'] ?> connected &middot; <?= $connStats['last_24h'] ?> connection<?= $connStats['last_24h'] === 1 ? '' : 's' ?> in 24h
        </p>
    <?php endif; ?>

    <?php if ($piratebox_mode === PIRATEBOX_MODE_EMERGENCY): ?>
        <div class="hero hero-emergency">
            <div class="hero-tagline">Emergency Mode is Active</div>
            <h1>This Network Does Not Require Internet Access</h1>
            <p>This is an intentionally local, offline network - it is designed to run on battery power, and does not provide or require Internet access.</p>
            <p>Emergency, First Aid, Radio, Maps, and Local Information have been prioritized below because they're likely to be most useful right now - the same file sharing and chat/community tools from normal operation still work too, just further down this page.</p>
            <p class="muted">PirateBox is not an official emergency service and does not replace calling 911 or your local emergency services for anything urgent.</p>
        </div>

        <div class="utility-grid">
            <a class="utility-card" href="/utility/emergency/">
                <span class="utility-card-icon" aria-hidden="true">🚨</span>
                <span class="utility-card-title">Emergency Info</span>
                <span class="utility-card-desc">Outage, storm &amp; disaster guidance</span>
            </a>
            <a class="utility-card" href="/utility/firstaid/">
                <span class="utility-card-icon" aria-hidden="true">🩹</span>
                <span class="utility-card-title">First Aid</span>
                <span class="utility-card-desc">Basic conservative reference</span>
            </a>
            <a class="utility-card" href="/utility/radio/">
                <span class="utility-card-icon" aria-hidden="true">📻</span>
                <span class="utility-card-title">Radio</span>
                <span class="utility-card-desc">Bands, frequencies &amp; modes</span>
            </a>
            <a class="utility-card" href="/utility/maps/">
                <span class="utility-card-icon" aria-hidden="true">🗺️</span>
                <span class="utility-card-title">Maps</span>
                <span class="utility-card-desc">Local &amp; regional maps</span>
            </a>
            <a class="utility-card" href="/utility/search/">
                <span class="utility-card-icon" aria-hidden="true">🔍</span>
                <span class="utility-card-title">Search</span>
                <span class="utility-card-desc">Search everything on this network</span>
            </a>
            <a class="utility-card" href="/utility/library/">
                <span class="utility-card-icon" aria-hidden="true">📚</span>
                <span class="utility-card-title">Library</span>
                <span class="utility-card-desc">Manuals &amp; reference documents</span>
            </a>
            <a class="utility-card" href="/chat.php">
                <span class="utility-card-icon" aria-hidden="true">💬</span>
                <span class="utility-card-title">Messages / Chat</span>
                <span class="utility-card-desc">Talk with others connected here</span>
            </a>
            <a class="utility-card" href="#files">
                <span class="utility-card-icon" aria-hidden="true">📁</span>
                <span class="utility-card-title">Files</span>
                <span class="utility-card-desc">Share &amp; download files</span>
            </a>
        </div>

        <section class="help-section">
            <h2>Also on this network</h2>
            <div class="hero-actions">
                <a href="/messages.php">Logbook</a>
                <a href="/help.php">Help / About This PirateBox</a>
                <a href="/utility/">Full Utility Library</a>
            </div>
        </section>
    <?php endif; ?>

    <div class="hero" id="files">
        <div class="hero-tagline">Offline File Sharing</div>
        <?= $piratebox_mode === PIRATEBOX_MODE_EMERGENCY ? '<h2>PirateBox</h2>' : '<h1>PirateBox</h1>' ?>
        <p>This is a local, offline network - no Internet connection is used or required. Share files, chat, and leave messages with anyone else connected to this Wi-Fi.</p>
        <?php if ($piratebox_mode !== PIRATEBOX_MODE_EMERGENCY): ?>
            <p>This PirateBox also carries an offline reference library - maps, radio references, first-aid and emergency guidance, manuals, and search - available any time, not just during an outage. See <a href="/whatcanidohere.php">What can I do here?</a> for the full list, or switch to Emergency Mode by physical switch to prioritize that material. <span class="muted">PirateBox is not an official emergency service.</span></p>
        <?php endif; ?>
        <div class="hero-actions">
            <a href="#upload-form">Upload a file</a>
            <a href="chat.php">Chat</a>
            <a href="messages.php">Logbook</a>
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