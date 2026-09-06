<?php
declare(strict_types=1);
session_start();
require_once __DIR__ . '/../../../includes/helpers.php';
require_once __DIR__ . '/../../../includes/mode.php';
require_once __DIR__ . '/../../../includes/metrics.php';
require_once __DIR__ . '/../../../includes/progression.php';

// Captain's Log - the site-facing presentation layer over PirateBox
// Progression (piratebox_progression.py / docs/OPERATIONAL-DECISIONS.md
// "PirateBox Progression"). READ-ONLY by design: this page cannot
// toggle Silly Mode, cannot reset/import/export Progression, and
// cannot force any event - those remain operator-side only
// (piratebox-silly on the command line). Nothing here writes any file.
//
// SPOILER POLICY (mandatory, matches the backend's own):
// includes/progression.php's piratebox_parse_progression_public()
// already strips anything that could reveal undiscovered content
// before this page ever sees it - no achievement/event id, no
// cooldown, no total-achievement-count denominator, no hint. This page
// additionally never computes or displays such a thing itself (no
// "3 / 47", no locked-achievement placeholders, no progress bars
// toward unknown content) - only what THIS device has actually
// discovered is ever rendered.
//
// 2026-09-06: each discovered achievement now also renders a short
// `description` - its spoiler-safe MEANING (what actually happened),
// never its MECHANICS (the exact trigger/threshold that unlocked it).
// This is exactly as safe as `name` already was: both come from
// piratebox_progression.py's build_public_summary(), which only ever
// iterates THIS device's own unlocked achievement list - an
// undiscovered achievement's description can no more reach this page
// than its name already could. This page adds no spoiler logic of its
// own; it only renders what the backend already decided was safe.
//
// PRIVACY: every number below is an aggregate device statistic already
// produced by Progression - no MAC address, IP, per-visitor identity,
// SSH session detail, or browsing history is read or shown anywhere on
// this page, matching every other public page on this site.

$progression = piratebox_get_progression_public();
$data = $progression['data'];
$stale = $progression['stale'];
$deviceName = $data['device_name'] ?? 'This PirateBox';

// --- Current status snapshot (tier + Silly Mode + mood) ---
// Reuses exactly the same inputs the OLED daemon's own
// compute_display_tier() does (mode + the helper snapshot) - a small,
// intentional, documented duplication of that tiny function in PHP,
// the same kind of cross-language duplication this project already
// accepts elsewhere (e.g. Emergency runtime seconds, computed
// independently in bash/Python/PHP from the same source log) rather
// than a real coupling between the two languages. This is cosmetic
// categorization for this page only - the actual OLED priority
// enforcement lives entirely in the daemon, unaffected by this file.
function piratebox_progression_current_tier(string $mode, ?array $status, bool $statusStale): string
{
    if ($mode === PIRATEBOX_MODE_EMERGENCY) return 'emergency';
    if ($statusStale || !is_array($status)) return 'fault';
    foreach (($status['services'] ?? []) as $ok) {
        if ($ok !== true) return 'fault';
    }
    if (($status['power']['undervoltage_now'] ?? false) === true) return 'warning';
    return 'ok';
}

function piratebox_progression_silly_enabled(): bool
{
    $raw = @file_get_contents('/tmp/piratebox/silly');
    return $raw !== false && strtolower(trim($raw)) === 'on';
}

$mode = piratebox_get_mode();
$helper = piratebox_get_helper_status();
$tier = piratebox_progression_current_tier($mode, $helper['status'], $helper['stale']);
$sillyEnabled = piratebox_progression_silly_enabled();
$wifiClients = (!$helper['stale'] && is_array($helper['status'])) ? (int) ($helper['status']['wifi_clients'] ?? 0) : null;

// A handful of broad, coarse mood keys - deliberately NOT a port of the
// OLED's full expression vocabulary (that stays the daemon's own job -
// see piratebox_oled_daemon.py's EXPRESSIONS). This is an independent,
// much smaller set purpose-built for a static, once-per-load web
// rendering, not a live face.
function piratebox_progression_mood_key(string $tier, ?int $wifiClients, array $traits): string
{
    if ($tier === 'emergency' || $tier === 'fault') return 'serious';
    if ($tier === 'warning') return 'steady';
    if (($wifiClients ?? 0) > 0) return 'content';
    if (($traits['sociability'] ?? '') === 'Solitary') return 'resting';
    return 'content';
}
$mood = piratebox_progression_mood_key($tier, $wifiClients, $data['traits']);

$moodCopy = [
    'serious' => 'Focused on more important things right now.',
    'steady'  => 'Steady, despite a known power quirk.',
    'content' => 'All quiet and content.',
    'resting' => 'Resting - no one\'s around at the moment.',
];

$moodFaces = [
    // Tiny inline SVGs, stroke="currentColor" so every theme colors
    // them automatically - no per-theme CSS, no external asset.
    'content' => '<circle cx="12" cy="10" r="1.4" fill="currentColor" stroke="none"/><circle cx="24" cy="10" r="1.4" fill="currentColor" stroke="none"/><path d="M10 18c2.5 3 9.5 3 12 0" fill="none"/>',
    'resting' => '<path d="M9 10h6M21 10h6" /><path d="M11 19c2 1.5 6 1.5 8 0" fill="none"/>',
    'steady'  => '<circle cx="12" cy="10" r="1.4" fill="currentColor" stroke="none"/><circle cx="24" cy="10" r="1.4" fill="currentColor" stroke="none"/><path d="M11 19h10" />',
    'serious' => '<path d="M9 9l6 2M27 9l-6 2" /><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="24" cy="12" r="1.2" fill="currentColor" stroke="none"/><path d="M12 20h12" />',
];

$logIcons = ['achievement' => '&#127942;', 'level_up' => '&#11088;', 'title_change' => '&#127988;', 'rare_event' => '&#10024;'];

$stats = $data['stats'];
$discoveredCount = count($data['achievements']);
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Captain's Log</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page captains-log-page">
        <h1><?= htmlspecialchars($deviceName) ?>'s Captain's Log</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <?php if (!$data['available']): ?>
            <div class="help-note">
                <p><strong>History unavailable.</strong> This PirateBox's Progression history isn't ready yet
                    <?= $stale ? '(the background snapshot may still be starting up).' : '.' ?>
                    Nothing else on this site is affected - come back in a little while.</p>
            </div>
        <?php else: ?>

            <div class="help-note">
                <p>A running record of this specific PirateBox's own history - built from real uptime, real
                    visitors, and real milestones since it was first switched on. Nothing here identifies any
                    visitor: every number is an aggregate about the device itself, never about the people who've
                    connected to it.<?= $stale ? ' <strong>This snapshot may be a little behind</strong> - it refreshes roughly every 30 seconds.' : '' ?></p>
            </div>

            <!-- Identity card -->
            <section class="identity-card">
                <div class="mood-face mood-<?= htmlspecialchars($mood) ?>" aria-hidden="true">
                    <svg viewBox="0 0 36 28" width="72" height="56" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round">
                        <?= $moodFaces[$mood] ?>
                    </svg>
                </div>
                <div class="identity-card-body">
                    <div class="identity-name"><?= htmlspecialchars($deviceName) ?></div>
                    <div class="identity-title"><?= htmlspecialchars($data['title'] ?? 'Unranked') ?> &middot; Level <?= (int) ($data['level'] ?? 1) ?></div>
                    <?php
                    $floor = $data['xp_this_level_floor'] ?? 0;
                    $next = $data['xp_next_level_at'] ?? 0;
                    $frac = $data['xp_progress_fraction'] ?? 0.0;
                    $xpIntoLevel = ($data['xp_total'] ?? 0) - $floor;
                    $xpSpan = max(1, $next - $floor);
                    ?>
                    <div class="xp-bar" role="progressbar" aria-valuenow="<?= (int) round($frac * 100) ?>" aria-valuemin="0" aria-valuemax="100" aria-label="Progress to next level">
                        <div class="xp-bar-fill" style="width: <?= (int) round($frac * 100) ?>%"></div>
                    </div>
                    <div class="xp-bar-label muted"><?= (int) $xpIntoLevel ?> / <?= (int) $xpSpan ?> XP to next level</div>
                    <p class="mood-caption muted"><?= htmlspecialchars($moodCopy[$mood]) ?><?= $sillyEnabled ? ' Silly Mode is on right now.' : '' ?></p>
                </div>
            </section>

            <!-- Personality traits -->
            <?php if (!empty($data['traits'])): ?>
                <h2>Personality</h2>
                <div class="trait-row">
                    <?php foreach ($data['traits'] as $trait => $label): ?>
                        <span class="trait-pill"><span class="muted"><?= htmlspecialchars(ucfirst($trait)) ?>:</span> <?= htmlspecialchars($label) ?></span>
                    <?php endforeach; ?>
                </div>
                <p class="muted trait-note">A slow-moving read on this PirateBox's own history - not a live mood,
                    and never influenced by any single visitor.</p>
            <?php endif; ?>

            <!-- Lifetime stats -->
            <h2>Lifetime Log</h2>
            <div class="stat-grid">
                <div class="stat-card">
                    <span class="stat-label">Lifetime Uptime</span>
                    <span class="stat-value"><?= htmlspecialchars(piratebox_fmt_duration($stats['lifetime_uptime_seconds'] ?? null)) ?></span>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Voyages Begun</span>
                    <span class="stat-value"><?= (int) ($stats['boots_observed'] ?? 0) ?></span>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Visitors Welcomed</span>
                    <span class="stat-value"><?= (int) ($stats['total_client_encounters'] ?? 0) ?></span>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Busiest Moment</span>
                    <span class="stat-value"><?= (int) ($stats['max_simultaneous_clients'] ?? 0) ?> aboard</span>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Storms Weathered</span>
                    <span class="stat-value"><?= (int) ($stats['emergency_exercises'] ?? 0) ?></span>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Visits From the Bridge</span>
                    <span class="stat-value"><?= (int) ($stats['ssh_sessions_observed'] ?? 0) ?></span>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Days of Silliness</span>
                    <span class="stat-value"><?= (int) ($stats['silly_days_used'] ?? 0) ?></span>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Achievements Discovered</span>
                    <span class="stat-value"><?= $discoveredCount ?></span>
                </div>
                <div class="stat-card">
                    <span class="stat-label">Rare Events Witnessed</span>
                    <span class="stat-value"><?= (int) ($stats['rare_events_witnessed'] ?? 0) ?></span>
                </div>
            </div>
            <p class="muted stat-note">"Visitors Welcomed" and "Busiest Moment" count Wi-Fi associations only - the
                same aggregate number every other status page on this site already shows, never a list of who
                connected or when.</p>

            <!-- Achievements -->
            <h2>Achievements</h2>
            <?php if ($discoveredCount === 0): ?>
                <p class="muted">None discovered yet - keep this PirateBox running, and time will tell.</p>
            <?php else: ?>
                <div class="stat-grid achievement-grid">
                    <?php foreach ($data['achievements'] as $a): ?>
                        <div class="achievement-card<?= $a['hidden'] ? ' achievement-secret' : '' ?>">
                            <span class="achievement-badge" aria-hidden="true">&#127942;</span>
                            <span class="achievement-name"><?= htmlspecialchars($a['name']) ?></span>
                            <?php if ($a['hidden']): ?>
                                <span class="achievement-tag muted">secret</span>
                            <?php endif; ?>
                            <?php if ($a['description'] !== ''): ?>
                                <p class="achievement-description"><?= htmlspecialchars($a['description']) ?></p>
                            <?php endif; ?>
                            <span class="achievement-date muted">
                                <?= $a['unlocked_at'] !== null ? 'Discovered ' . htmlspecialchars(date('M j, Y', $a['unlocked_at'])) : 'Discovered sometime in this PirateBox\'s history' ?>
                            </span>
                        </div>
                    <?php endforeach; ?>
                </div>
            <?php endif; ?>

            <!-- Captain's Log timeline -->
            <h2>Captain's Log</h2>
            <?php if (empty($data['history'])): ?>
                <p class="muted">The log is empty so far - nothing notable has happened yet.</p>
            <?php else: ?>
                <ol class="log-timeline">
                    <?php foreach ($data['history'] as $entry): ?>
                        <li class="log-entry log-entry-<?= htmlspecialchars($entry['kind']) ?>">
                            <span class="log-icon" aria-hidden="true"><?= $logIcons[$entry['kind']] ?? '&#8226;' ?></span>
                            <span class="log-label"><?= htmlspecialchars($entry['label']) ?></span>
                            <span class="log-date muted"><?= $entry['ts'] > 0 ? htmlspecialchars(date('Y-m-d', $entry['ts'])) : '' ?></span>
                        </li>
                    <?php endforeach; ?>
                </ol>
            <?php endif; ?>

        <?php endif; ?>

        <div class="hero-actions">
            <a href="/utility/status/">Device Status</a>
            <a href="/utility/">Utility Library</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
