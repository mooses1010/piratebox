<?php
declare(strict_types=1);
session_start();
require_once __DIR__ . '/../../includes/config.php';

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

$actionResult = null;

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

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (empty($_POST['csrf_token']) || !hash_equals($_SESSION['csrf_token'] ?? '', $_POST['csrf_token'])) {
        http_response_code(403);
        exit('Invalid CSRF token.');
    }
    if (empty($_POST['confirm'])) {
        $actionResult = ['ok' => false, 'msg' => 'Action not confirmed - nothing was done.'];
    } else {
        $action = $_POST['action'] ?? '';
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
            case 'purge_uploads':
                [$deleted, $failed] = purgeUploadsDir($UPLOAD_DIR);
                $actionResult = ['ok' => $failed === 0, 'msg' => "Deleted $deleted uploaded file(s)." . ($failed > 0 ? " $failed could not be deleted." : '')];
                break;
            default:
                $actionResult = ['ok' => false, 'msg' => 'Unknown action.'];
        }
    }
}

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

$uptimeSeconds = null;
$uptimeRaw = @file_get_contents('/proc/uptime');
if ($uptimeRaw !== false) {
    $parts = explode(' ', trim($uptimeRaw));
    if (isset($parts[0])) $uptimeSeconds = (float) $parts[0];
}

$memTotalKb = null;
$memAvailableKb = null;
$meminfoRaw = @file_get_contents('/proc/meminfo');
if ($meminfoRaw !== false) {
    if (preg_match('/^MemTotal:\s+(\d+)/m', $meminfoRaw, $m)) $memTotalKb = (int) $m[1];
    if (preg_match('/^MemAvailable:\s+(\d+)/m', $meminfoRaw, $m)) $memAvailableKb = (int) $m[1];
}

$cpuTempC = null;
$tempRaw = @file_get_contents('/sys/class/thermal/thermal_zone0/temp');
if ($tempRaw !== false && is_numeric(trim($tempRaw))) {
    $cpuTempC = ((int) trim($tempRaw)) / 1000.0;
}

// Status snapshot from the root helper timer (Wi-Fi clients, per-service
// health, undervoltage). Treated as advisory/best-effort: if the file is
// missing or stale (timer not running, or its first run hasn't happened
// yet), we say so rather than guessing.
$helperStatus = null;
$helperStale = true;
$helperRaw = @file_get_contents('/run/piratebox/status.json');
if ($helperRaw !== false) {
    $decoded = json_decode($helperRaw, true);
    if (is_array($decoded)) {
        $helperStatus = $decoded;
        $age = time() - (int) ($decoded['generated_at'] ?? 0);
        $helperStale = $age > 300; // helper runs every 30s; 5 min = clearly not running
    }
}

$versionRaw = @file_get_contents(__DIR__ . '/../../includes/VERSION');
$versionLine = $versionRaw !== false ? trim($versionRaw) : null;

function fmtBytes(?int $bytes): string
{
    if ($bytes === null) return 'unknown';
    $units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
    $i = 0;
    $val = (float) $bytes;
    while ($val >= 1024 && $i < count($units) - 1) {
        $val /= 1024;
        $i++;
    }
    return round($val, 1) . ' ' . $units[$i];
}

function fmtDuration(?float $seconds): string
{
    if ($seconds === null) return 'unknown';
    $days = (int) floor($seconds / 86400);
    $hours = (int) floor(($seconds % 86400) / 3600);
    $mins = (int) floor(($seconds % 3600) / 60);
    $out = [];
    if ($days > 0) $out[] = "{$days}d";
    if ($hours > 0) $out[] = "{$hours}h";
    $out[] = "{$mins}m";
    return implode(' ', $out);
}
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

    <h2>Status</h2>
    <div class="stat-grid">
        <div class="stat-card">
            <span class="stat-label">Storage free</span>
            <span class="stat-value"><?= fmtBytes($diskFree !== false ? (int) $diskFree : null) ?></span>
            <span class="stat-sub">of <?= fmtBytes($diskTotal !== false ? (int) $diskTotal : null) ?></span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Uploads</span>
            <span class="stat-value"><?= $uploadCount ?> file<?= $uploadCount === 1 ? '' : 's' ?></span>
            <span class="stat-sub"><?= fmtBytes($uploadBytes) ?> total</span>
        </div>
        <div class="stat-card">
            <span class="stat-label">Uptime</span>
            <span class="stat-value"><?= fmtDuration($uptimeSeconds) ?></span>
        </div>
        <div class="stat-card">
            <span class="stat-label">RAM available</span>
            <span class="stat-value"><?= $memAvailableKb !== null ? fmtBytes($memAvailableKb * 1024) : 'unknown' ?></span>
            <span class="stat-sub">of <?= $memTotalKb !== null ? fmtBytes($memTotalKb * 1024) : 'unknown' ?></span>
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

    <h2>Maintenance</h2>
    <p class="muted" style="text-align:center; max-width:600px; margin:0 auto 1rem auto;">
        Each action below is independent and does exactly what it says - clearing
        chat does not touch messages or uploads, and vice versa. Service
        restarts and reboot are intentionally not available here; see the
        README for the SSH commands.
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

        <form method="post" class="admin-action-form" onsubmit="return confirm('Delete ALL uploaded files? This cannot be undone.');">
            <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION['csrf_token']) ?>">
            <input type="hidden" name="action" value="purge_uploads">
            <label><input type="checkbox" name="confirm" value="1" required> I understand this permanently deletes every uploaded file.</label>
            <button type="submit" class="danger-button">Purge all uploads</button>
        </form>
    </div>
</body>

</html>
