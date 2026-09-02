<?php
declare(strict_types=1);
session_start();

// Checksum / Hash Calculator (Reference -> Tool principle, see
// docs/REFERENCE-CONTENT-DESIGN.md §9). Investigated and built because
// PirateBox already stores and distributes files via its own file-
// sharing feature - verifying a download wasn't corrupted in transit
// is a real, recurring need for exactly what this device already
// does, not a speculative "technically possible" utility.
//
// Read-only against the existing uploads directory - NO new upload
// path, no second way to get a file onto this device. A filename is
// only ever accepted if it exactly matches a real file the safe
// listing function just found there (see includes/checksum_tool.php).
//
// Server-only by design (no JS enhancement): hashing an existing
// server-side file has no meaningful client-side equivalent without
// re-transmitting its contents, and the text-hash panel's plain POST
// round trip is simple enough that a JS-only shortcut would add
// complexity (async Web Crypto for SHA-256, no native MD5) without
// real benefit. Nothing entered/selected here is logged or stored
// beyond this one request.

require_once __DIR__ . '/../../../../includes/checksum_tool.php';

$UPLOAD_DIR = __DIR__ . '/../../../uploads';
$uploadedFiles = piratebox_list_uploaded_files($UPLOAD_DIR);

$fileResult = null;
$selectedFile = $_POST['filename'] ?? '';
if (($_POST['ft_form'] ?? '') === 'file' && $_SERVER['REQUEST_METHOD'] === 'POST' && $selectedFile !== '') {
    $fileResult = piratebox_hash_uploaded_file((string) $selectedFile, $UPLOAD_DIR);
}

$textInput = (string) ($_POST['text'] ?? '');
$textResult = null;
if (($_POST['ft_form'] ?? '') === 'text' && $_SERVER['REQUEST_METHOD'] === 'POST' && $textInput !== '') {
    $textResult = piratebox_hash_text($textInput);
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Checksum / Hash Calculator</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Checksum / Hash Calculator</h1>
        <p class="utility-breadcrumb"><a href="/utility/fieldtools/">&larr; Field Tools</a></p>

        <p>Verify a file wasn't corrupted or altered in transit by comparing its hash to one published by the source. Unfamiliar with what a checksum actually proves? See the <a href="/utility/glossary/#checksum">Glossary</a>.</p>

        <div class="help-note">
            <p><strong>A matching hash confirms the bytes are identical - it does not prove the source is trustworthy.</strong> SHA-256 is shown as the hash to actually rely on for integrity verification. MD5 is also shown, but only for matching against older published checksums - MD5 is not secure against deliberate tampering and should never be treated as proof of authenticity.</p>
        </div>

        <h2>Hash a file already on this PirateBox</h2>
        <?php if (empty($uploadedFiles)): ?>
            <p class="muted">No files are currently uploaded - see <a href="/">Upload a file</a> first.</p>
        <?php else: ?>
            <form method="post" action="">
                <input type="hidden" name="ft_form" value="file">
                <div class="fieldtools-tool" id="ft-checksum-file-tool">
                    <div class="fieldtools-row">
                        <label for="checksum-filename">File</label>
                        <select id="checksum-filename" name="filename">
                            <?php foreach ($uploadedFiles as $f): ?>
                                <option value="<?= htmlspecialchars($f) ?>" <?= $selectedFile === $f ? 'selected' : '' ?>><?= htmlspecialchars($f) ?></option>
                            <?php endforeach; ?>
                        </select>
                    </div>
                    <div class="fieldtools-row">
                        <button type="submit">Calculate hash</button>
                    </div>
                    <?php if ($fileResult !== null && isset($fileResult['error'])): ?>
                        <p class="fieldtools-result help-note"><?= htmlspecialchars($fileResult['error']) ?></p>
                    <?php elseif ($fileResult !== null): ?>
                        <div class="table-wrapper">
                            <table>
                                <tbody>
                                    <tr><td>File</td><td><?= htmlspecialchars($fileResult['filename']) ?> (<?= number_format($fileResult['size']) ?> bytes)</td></tr>
                                    <tr><td>SHA-256</td><td class="help-url"><?= htmlspecialchars($fileResult['sha256']) ?></td></tr>
                                    <tr><td>MD5 <span class="muted">(legacy only)</span></td><td class="help-url"><?= htmlspecialchars($fileResult['md5']) ?></td></tr>
                                </tbody>
                            </table>
                        </div>
                    <?php endif; ?>
                </div>
            </form>
        <?php endif; ?>

        <h2>Hash pasted text</h2>
        <form method="post" action="">
            <input type="hidden" name="ft_form" value="text">
            <div class="fieldtools-tool" id="ft-checksum-text-tool">
                <div class="fieldtools-row">
                    <label for="checksum-text">Text</label>
                    <textarea id="checksum-text" name="text" rows="3" placeholder="Paste text to hash"><?= htmlspecialchars($textInput) ?></textarea>
                </div>
                <div class="fieldtools-row">
                    <button type="submit">Calculate hash</button>
                </div>
                <?php if ($textResult !== null): ?>
                    <div class="table-wrapper">
                        <table>
                            <tbody>
                                <tr><td>SHA-256</td><td class="help-url"><?= htmlspecialchars($textResult['sha256']) ?></td></tr>
                                <tr><td>MD5 <span class="muted">(legacy only)</span></td><td class="help-url"><?= htmlspecialchars($textResult['md5']) ?></td></tr>
                            </tbody>
                        </table>
                    </div>
                <?php endif; ?>
            </div>
        </form>

        <p class="muted">Nothing entered or selected here is logged or stored beyond computing this one result.</p>
    </div>

    <?php require_once __DIR__ . '/../../../../includes/footer.php'; ?>
</body>

</html>
