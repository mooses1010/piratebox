<?php
declare(strict_types=1);
session_start();
require_once __DIR__ . '/../../includes/config.php';
require_once __DIR__ . '/../../includes/helpers.php';
require_once __DIR__ . '/../../includes/metrics.php';

// PirateBox admin/status page - Phase 4.
//
// Access control is handled entirely by nginx (HTTP Basic Auth on the
// /admin/ location - see etc/nginx/sites-available/default and
// setup_admin_password.sh). This page assumes it is only ever reached by
// someone who has already authenticated at the web server level.
//
// Security boundaries (see docs/OPERATIONAL-DECISIONS.md for the full
// rationale):
//   - No arbitrary command execution is exposed here or anywhere in the
//     app. PHP's disable_functions already blocks exec/shell_exec/system/
//     passthru/proc_open/popen at the ini level, so even a bug in this
//     file could not shell out.
//   - The handful of stats that require reading privileged/system state
//     (Wi-Fi client count, per-service active/inactive, undervoltage) are
//     NOT gathered by this page directly. They come from
//     /run/piratebox/status.json, written every 30s by a separate,
//     narrowly-scoped root helper (piratebox_status_helper.sh, run via
//     systemd timer) that takes no input and does nothing but read system
//     state. www-data is never granted sudo and never runs that helper
//     itself - it only reads the (world-readable, tmpfs) file it leaves
//     behind.
//   - Destructive actions (clear chat, clear messages, purge uploads) are
//     deliberately narrow: each does exactly one thing, requires the same
//     CSRF token as the rest of the app plus an explicit confirmation
//     checkbox, and uses the same flock()-based locking as Phase 1's
//     chat.php/messages.php so it can never race a concurrent post. There
//     is no service-restart or reboot button - those remain SSH-only (see
//     README) because doing them safely from www-data would require
//     either broad sudo or a privileged helper with a much larger attack
//     surface than this page's other actions; not worth it for this phase.

if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

$UPLOAD_DIR = __DIR__ . '/../uploads';
$DATA_DIR = __DIR__ . '/../../data';
$CHAT_FILE = $DATA_DIR . '/chat.json';
$MESSAGES_FILE = $DATA_DIR . '/messages.json';
$BULLETIN_FILE = $DATA_DIR . '/bulletin.json';
$RECOVERY_FILE = $DATA_DIR . '/recovery-messages.json';

$actionResult = null;

/**
 * Stage 16: read the recovery-messages store the same defensive way every
 * other JSON loader in this project does - missing/corrupt file is never
 * fatal, just an empty list.
 */
function loadRecoveryMessages(string $path): array
{
    if (!file_exists($path)) return [];
    $raw = @file_get_contents($path);
    if ($raw === false) return [];
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

/**
 * Stage 16: atomic write, same temp-file-then-rename pattern as every
 * other JSON store this app writes.
 */
function saveRecoveryMessages(string $path, array $entries): bool
{
    $tmpFile = $path . '.tmp.' . getmypid() . '.' . bin2hex(random_bytes(4));
    if (file_put_contents($tmpFile, json_encode($entries, JSON_PRETTY_PRINT)) === false) {
        return false;
    }
    if (!rename($tmpFile, $path)) {
        @unlink($tmpFile);
        return false;
    }
    return true;
}

/**
 * Atomically replace a JSON data file with an empty array, under the same
 * exclusive lock chat.php/messages.php use for writes. Mirrors Phase 1's
 * write path exactly (temp file + rename) so a reader polling ?fetch=1
 * never sees a partial file, and never races a concurrent post.
 */
function clearJsonFile(string $dataFile): bool
{
    $lockHandle = fopen($dataFile . '.lock', 'c');
    if ($lockHandle === false) {
        return false;
    }
    $ok = false;
    if (flock($lockHandle, LOCK_EX)) {
        $tmpFile = $dataFile . '.tmp.' . getmypid() . '.' . bin2hex(random_bytes(4));
        if (file_put_contents($tmpFile, '[]') !== false) {
            $ok = rename($tmpFile, $dataFile);
            if (!$ok) {
                @unlink($tmpFile);
            }
        }
        flock($lockHandle, LOCK_UN);
    }
    fclose($lockHandle);
    return $ok;
}

/** Delete every regular file directly inside the uploads directory. */
function purgeUploadsDir(string $uploadDir): array
{
    $deleted = 0;
    $failed = 0;
    foreach ((is_dir($uploadDir) ? scandir($uploadDir) : []) as $entry) {
        if ($entry === '.' || $entry === '..') {
            continue;
        }
        $path = $uploadDir . '/' . $entry;
        if (is_file($path)) {
            if (@unlink($path)) {
                $deleted++;
            } else {
                $failed++;
            }
        }
    }
    return [$deleted, $failed];
}

// Stage 16: actions that are genuinely destructive/irreversible require the
// explicit confirmation checkbox, matching every existing action on this
// page. Replying to a recovery message is neither destructive nor
// irreversible (an admin can reply again to correct a mistake), so it's
// deliberately NOT in this set - it still requires the same CSRF token,
// same as everything else here.
$CONFIRM_REQUIRED_ACTIONS = ['clear_chat', 'clear_messages', 'clear_bulletin', 'purge_uploads', 'purge_recovery_one', 'purge_recovery_all'];

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (empty($_POST['csrf_token']) || !hash_equals($_SESSION['csrf_token'] ?? '', $_POST['csrf_token'])) {
        http_response_code(403);
        exit('Invalid CSRF token.');
    }
    $action = $_POST['action'] ?? '';
    if (in_array($action, $CONFIRM_REQUIRED_ACTIONS, true) && empty($_POST['confirm'])) {
        $actionResult = ['ok' => false, 'msg' => 'Action not confirmed - nothing was done.'];
    } else {
        switch ($action) {
            case 'clear_chat':
                $actionResult = clearJsonFile($CHAT_FILE)
                    ? ['ok' => true, 'msg' => 'Chat history cleared.']
                    : ['ok' => false, 'msg' => 'Failed to clear chat history.'];
                break;
            case 'clear_messages':
                $actionResult = clearJsonFile($MESSAGES_FILE)
                    ? ['ok' => true, 'msg' => 'Guestbook messages cleared.']
                    : ['ok' => false, 'msg' => 'Failed to clear messages.'];
                break;
            case 'clear_bulletin':
                $actionResult = clearJsonFile($BULLETIN_FILE)
                    ? ['ok' => true, 'msg' => 'Bulletin board posts cleared.']
                    : ['ok' => false, 'msg' => 'Failed to clear bulletin board.'];
                break;
            case 'purge_uploads':
                [$deleted, $failed] = purgeUploadsDir($UPLOAD_DIR);
                $actionResult = ['ok' => $failed === 0, 'msg' => "Deleted $deleted uploaded file(s)." . ($failed > 0 ? " $failed could not be deleted." : '')];
                break;
            case 'reply_recovery':
                $code = strtoupper(trim($_POST['code'] ?? ''));
                $replyText = mb_substr(trim(strip_tags($_POST['reply'] ?? '')), 0, 1000);
                $entries = loadRecoveryMessages($RECOVERY_FILE);
                $found = false;
                foreach ($entries as &$e) {
                    if (($e['code'] ?? null) === $code) {
                        $e['reply'] = $replyText !== '' ? $replyText : null;
                        $e['replied_at'] = $replyText !== '' ? date('Y-m-d H:i') : null;
                        $e['status'] = $replyText !== '' ? 'replied' : 'new';
                        $found = true;
                        break;
                    }
                }
                unset($e);
                if ($found && saveRecoveryMessages($RECOVERY_FILE, $entries)) {
                    $actionResult = ['ok' => true, 'msg' => "Reply saved for $code."];
                } else {
                    $actionResult = ['ok' => false, 'msg' => 'Could not save reply (message not found or write failed).'];
                }
                break;
            case 'purge_recovery_one':
                $code = strtoupper(trim($_POST['code'] ?? ''));
                $entries = loadRecoveryMessages($RECOVERY_FILE);
                $before = count($entries);
                $entries = array_values(array_filter($entries, fn($e) => ($e['code'] ?? null) !== $code));
                if (count($entries) < $before && saveRecoveryMessages($RECOVERY_FILE, $entries)) {
                    $actionResult = ['ok' => true, 'msg' => "Deleted recovery message $code."];
                } else {
                    $actionResult = ['ok' => false, 'msg' => 'Message not found or delete failed.'];
                }
                break;
            case 'purge_recovery_all':
                $actionResult = saveRecoveryMessages($RECOVERY_FILE, [])
                    ? ['ok' => true, 'msg' => 'All recovery messages cleared.']
                    : ['ok' => false, 'msg' => 'Failed to clear recovery messages.'];
                break;
            default:
                $actionResult = ['ok' => false, 'msg' => 'Unknown action.'];
        }
    }
}

$recoveryMessages = array_reverse(loadRecoveryMessages($RECOVERY_FILE));

// --- Gather status information (all read-only) ---

// disk_free_space()/disk_total_space() are subject to open_basedir like any
// other filesystem call - '/' itself is not in the allowed list (see
// php.ini), but /var/www/html is, and it's the same filesystem/mountpoint
// as '/' on this system (single-partition SD card), so the numbers are
// identical to what querying '/' directly would give.
$diskTotal = @disk_total_space(__DIR__ . '/../..');
$diskFree = @disk_free_space(__DIR__ . '/../..');

$uploadCount = 0;
$uploadBytes = 0;
foreach ((is_dir($UPLOAD_DIR) ? scandir($UPLOAD_DIR) : []) as $entry) {
    if ($entry === '.' || $entry === '..') continue;
    $path = $UPLOAD_DIR . '/' . $entry;
    if (is_file($path)) {
        $uploadCount++;
        $size = @filesize($path);
        if ($size !== false) $uploadBytes += $size;
    }
}

// Stage 27 (maintenance/consolidation): these all now come from the
// shared includes/metrics.php module the Stats page already uses
// (Stage 21), instead of a second copy of the same /proc reads and
// helper-snapshot logic living only here. Deliberately deferred at the
// time Stage 21 introduced that module - see docs/OPERATIONAL-
// DECISIONS.md for why refactoring this destructive-action-containing
// page wasn't worth doing in the same stage as adding a brand new one,
// and for this stage's regression testing before making the swap.
$uptimeSeconds = piratebox_get_uptime_seconds();
[$memTotalKb, $memAvailableKb] = piratebox_get_meminfo_kb();
$cpuTempC = piratebox_get_cpu_temp_c();

// Status snapshot from the root helper timer (Wi-Fi clients, per-service
// health, undervoltage). Treated as advisory/best-effort: if the file is
// missing or stale (timer not running, or its first run hasn't happened
// yet), we say so rather than guessing.
$helperResult = piratebox_get_helper_status();
$helperStatus = $helperResult['status'];
$helperStale = $helperResult['stale'];

$versionRaw = @file_get_contents(__DIR__ . '/../../includes/VERSION');
$versionLine = $versionRaw !== false ? trim($versionRaw) : null;

// Byte/duration formatting now lives in includes/helpers.php (Phase 5) as
// piratebox_fmt_bytes()/piratebox_fmt_duration() - index.php needs the
// same byte formatting for the file list, so this is now the one shared
// copy instead of a second one living only here.
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Admin</title>
    <link rel="stylesheet" href="../assets/styles.css">
</head>

<body>
    <nav class="navbar">
        <div class="navbar-brand">
            <img src="../assets/500px-PirateBox-logo.svg.png" alt="PirateBox Logo">
            PirateBox Admin
        </div>
        <ul class="navbar-menu">
            <li><a href="/">Back to PirateBox</a></li>
        </ul>
    </nav>

    <?php if ($actionResult !== null): ?>
        <p style="text-align:center;">
            <strong class="<?= $actionResult['ok'] ? 'status-ok' : 'status-bad' ?>"><?= htmlspecialchars($actionResult['msg']) ?></strong>
        </p>
    <?php endif; ?>

    <h2 class="admin-section-heading">System status <span class="section-tag">read-only</span></h2>
    <div class="stat-grid">
        <div class="stat-card">
            <span class="stat-label">Storage free</span>
            <span class="stat-value"><?= piratebox_fmt_bytes($diskFree !== false ? (int) $diskFree : null) ?></span>
            <span class="stat-sub">of <?= piratebox_fmt_bytes($diskTotal !== false ? (int) $diskTotal : null) ?></span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Uploads</span>
            <span class="stat-value"><?= $uploadCount ?> file<?= $uploadCount === 1 ? '' : 's' ?></span>
            <span class="stat-sub"><?= piratebox_fmt_bytes($uploadBytes) ?> total</span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Uptime</span>
            <span class="stat-value"><?= piratebox_fmt_duration($uptimeSeconds) ?></span>
        </div>
        <div class="stat-card">
            <span class="stat-label">RAM available</span>
            <span class="stat-value"><?= $memAvailableKb !== null ? piratebox_fmt_bytes($memAvailableKb * 1024) : 'unknown' ?></span>
            <span class="stat-sub">of <?= $memTotalKb !== null ? piratebox_fmt_bytes($memTotalKb * 1024) : 'unknown' ?></span>
        </div>
        <div class="stat-card">
            <span class="stat-label">CPU temp</span>
            <span class="stat-value"><?= $cpuTempC !== null ? round($cpuTempC, 1) . '&deg;C' : 'unknown' ?></span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Wi-Fi clients</span>
            <span class="stat-value"><?= ($helperStatus && !$helperStale) ? (int) $helperStatus['wifi_clients'] : '?' ?></span>
            <?php if ($helperStale): ?><span class="stat-sub status-bad">status helper not reporting</span><?php endif; ?>
        </div>
    </div>

    <h2>Services</h2>
    <div class="stat-grid">
        <?php
        $serviceNames = ['hostapd' => 'hostapd', 'dnsmasq' => 'dnsmasq', 'nginx' => 'nginx', 'php8.4-fpm' => 'PHP-FPM'];
        foreach ($serviceNames as $key => $label):
            $active = $helperStatus && !$helperStale ? ($helperStatus['services'][$key] ?? false) : null;
            ?>
            <div class="stat-card">
                <span class="stat-label"><?= htmlspecialchars($label) ?></span>
                <span class="stat-value <?= $active === true ? 'status-ok' : ($active === false ? 'status-bad' : '') ?>">
                    <?= $active === null ? 'unknown' : ($active ? 'active' : 'DOWN') ?>
                </span>
            </div>
        <?php endforeach; ?>
    </div>

    <?php if ($helperStatus && !$helperStale && ($helperStatus['power']['undervoltage_now'] ?? false)): ?>
        <p style="text-align:center;"><strong class="status-bad">Under-voltage detected right now</strong> - known intermittent power issue on this hardware, see README. Not something this admin page can fix.</p>
    <?php elseif ($helperStatus && !$helperStale && ($helperStatus['power']['undervoltage_since_boot'] ?? false)): ?>
        <p style="text-align:center;" class="muted">Under-voltage occurred at least once since boot (not currently active).</p>
    <?php endif; ?>

    <p style="text-align:center;" class="muted">
        <?= $versionLine !== null ? 'Version: ' . htmlspecialchars($versionLine) : 'Version: unknown (no includes/VERSION file - see README)' ?>
    </p>

    <h2 class="admin-section-heading">Recovery messages <span class="section-tag">local only</span></h2>
    <p class="muted" style="text-align:center;">Stage 16 - separate from Chat/Guestbook. Never transmitted over the Internet.</p>
    <?php if (empty($recoveryMessages)): ?>
        <p class="empty-state">No recovery messages.</p>
    <?php else: ?>
        <div class="message-container" style="max-width:900px;margin:0 auto 2rem auto;padding:0 1rem;">
            <?php foreach ($recoveryMessages as $rm): ?>
                <div class="message-card">
                    <div class="message-header">
                        <span class="message-name">
                            <?= htmlspecialchars($rm['code'] ?? '?') ?>
                            <span class="stat-sub"><?= ($rm['status'] ?? 'new') === 'replied' ? '(replied)' : '(new)' ?></span>
                        </span>
                        <span class="message-time"><?= htmlspecialchars($rm['submitted_at'] ?? '') ?></span>
                    </div>
                    <div class="message-body"><?= htmlspecialchars($rm['message'] ?? '') ?></div>
                    <?php if (!empty($rm['contact'])): ?>
                        <p class="muted">Finder contact (optional, as given): <?= htmlspecialchars($rm['contact']) ?></p>
                    <?php endif; ?>
                    <?php if (!empty($rm['reply'])): ?>
                        <div class="message-card" style="border-left-color:#4ade80;">
                            <div class="message-header">
                                <span class="message-name">Your reply</span>
                                <span class="message-time"><?= htmlspecialchars($rm['replied_at'] ?? '') ?></span>
                            </div>
                            <div class="message-body"><?= htmlspecialchars($rm['reply']) ?></div>
                        </div>
                    <?php endif; ?>
                    <form method="post" class="admin-action-form" style="max-width:none;">
                        <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                        <input type="hidden" name="action" value="reply_recovery">
                        <input type="hidden" name="code" value="<?= htmlspecialchars($rm['code'] ?? '') ?>">
                        <label>Reply <textarea name="reply" maxlength="1000" rows="2"><?= htmlspecialchars($rm['reply'] ?? '') ?></textarea></label>
                        <button type="submit">Save Reply</button>
                    </form>
                    <form method="post" class="admin-action-form" style="max-width:none;" onsubmit="return confirm('Delete this recovery message? This cannot be undone.');">
                        <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                        <input type="hidden" name="action" value="purge_recovery_one">
                        <input type="hidden" name="code" value="<?= htmlspecialchars($rm['code'] ?? '') ?>">
                        <label><input type="checkbox" name="confirm" value="1" required> Delete this message.</label>
                        <button type="submit" class="danger-button">Delete</button>
                    </form>
                </div>
            <?php endforeach; ?>
        </div>
        <div class="admin-actions">
            <form method="post" class="admin-action-form" onsubmit="return confirm('Delete ALL recovery messages? This cannot be undone.');">
                <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                <input type="hidden" name="action" value="purge_recovery_all">
                <label><input type="checkbox" name="confirm" value="1" required> I understand this permanently deletes all recovery messages.</label>
                <button type="submit" class="danger-button">Purge all recovery messages</button>
            </form>
        </div>
    <?php endif; ?>

    <div class="maintenance-zone">
        <h2 class="admin-section-heading">Destructive maintenance <span class="section-tag">irreversible</span></h2>
        <p class="maintenance-warning">
            Each action below is independent and does exactly what it says - clearing
            chat does not touch messages or uploads, and vice versa. Every action
            requires the checkbox below AND a confirmation dialog, and cannot be
            undone. Service restarts and reboot are intentionally not available
            here; see the README for the SSH commands.
        </p>
        <div class="admin-actions">
            <form method="post" class="admin-action-form" onsubmit="return confirm('Clear ALL chat history? This cannot be undone.');">
                <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                <input type="hidden" name="action" value="clear_chat">
                <label><input type="checkbox" name="confirm" value="1" required> I understand this permanently deletes all live chat history.</label>
                <button type="submit" class="danger-button">Clear chat history</button>
            </form>

            <form method="post" class="admin-action-form" onsubmit="return confirm('Clear ALL guestbook messages? This cannot be undone.');">
                <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                <input type="hidden" name="action" value="clear_messages">
                <label><input type="checkbox" name="confirm" value="1" required> I understand this permanently deletes all guestbook messages.</label>
                <button type="submit" class="danger-button">Clear messages</button>
            </form>

            <form method="post" class="admin-action-form" onsubmit="return confirm('Clear ALL bulletin board posts? This cannot be undone.');">
                <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                <input type="hidden" name="action" value="clear_bulletin">
                <label><input type="checkbox" name="confirm" value="1" required> I understand this permanently deletes all bulletin board posts.</label>
                <button type="submit" class="danger-button">Clear bulletin board</button>
            </form>

            <form method="post" class="admin-action-form" onsubmit="return confirm('Delete ALL uploaded files? This cannot be undone.');">
                <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
                <input type="hidden" name="action" value="purge_uploads">
                <label><input type="checkbox" name="confirm" value="1" required> I understand this permanently deletes every uploaded file.</label>
                <button type="submit" class="danger-button">Purge all uploads</button>
            </form>
        </div>
    </div>
</body>

</html>
