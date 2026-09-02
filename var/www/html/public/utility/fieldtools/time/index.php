<?php
declare(strict_types=1);
session_start();

require_once __DIR__ . '/../../../../includes/helpers.php';
require_once __DIR__ . '/../../../../includes/fieldtools_time.php';

// Field Tools: Time & Date (Post-Stage-32). See includes/fieldtools_time.php
// for the snapshot/time-source functions this page is a thin view over -
// deliberately not reimplemented here, same "one tested copy" pattern as
// includes/metrics.php's own header explains.

require_once __DIR__ . '/../../../../includes/metrics.php'; // piratebox_get_uptime_seconds()

$snap = piratebox_fieldtools_now_snapshot();
$timeSource = piratebox_get_time_source_status();
$uptimeSeconds = piratebox_get_uptime_seconds();
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Time &amp; Date</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Time &amp; Date</h1>
        <p class="utility-breadcrumb"><a href="/utility/fieldtools/">&larr; Field Tools</a></p>

        <div class="help-note">
            <?php if (!$timeSource['available']): ?>
                <p><strong>Time source: not currently reporting.</strong>
                    <?php if ($timeSource['stale']): ?>
                        This device's periodic status snapshot hasn't updated recently - see <a href="/utility/status/">Status</a> for the same staleness condition affecting other readings.
                    <?php else: ?>
                        This device's status helper hasn't been updated to report this yet (a small, known pending step - see <code>docs/OPERATIONAL-DECISIONS.md</code>, "Field Tools / Offline Reference Instruments"). Nothing is fabricated in its place.
                    <?php endif; ?>
                </p>
            <?php else: ?>
                <p><strong>Time source:</strong>
                    <?php if ($timeSource['rtc_detected']): ?>
                        a hardware real-time clock is detected on this device - the system clock can be backed by it across a power-off, not just while running.
                    <?php else: ?>
                        <strong>no hardware real-time clock is installed on this device.</strong> A Raspberry Pi has no battery-backed clock of its own - the time below comes from whatever the system clock has held since it was last set (network time sync, if one ever succeeded, or the boot default), and can be significantly wrong after a cold boot with no network available. A DS3231 hardware RTC is planned for this device but not yet installed - see this project's <code>docs/RTC-TIME-READINESS-DESIGN.md</code>. Once it's added, this line updates automatically with no code change.
                    <?php endif; ?>
                </p>
                <p>
                    Network time sync (NTP):
                    <?= $timeSource['ntp_synchronized'] ? '<span class="status-ok">currently synchronized</span>' : '<span class="status-bad">not currently synchronized</span>' ?>.
                    <?php if (!$timeSource['ntp_synchronized']): ?>
                        This PirateBox is an isolated access point by design - if it has no separate uplink to the Internet, it has no path to a real time server, so this is expected here, not necessarily a fault.
                    <?php endif; ?>
                    <?php if (!$timeSource['fake_hwclock_installed'] && !$timeSource['rtc_detected']): ?>
                        <code>fake-hwclock</code> (a software "remember the last known time across a reboot" fallback) is also not installed.
                    <?php endif; ?>
                </p>
            <?php endif; ?>
            <p class="muted">This device does not claim atomic-clock or GPS-level accuracy, and does not fabricate a "last synchronized" time it hasn't actually recorded. Treat the time below as a best-effort local reading, not a certified reference.</p>
            <?php if (strtoupper($snap['tz_name']) === 'UTC'): ?>
                <p class="muted">"Local" and "UTC" below currently read the same: this device's PHP configuration has no timezone explicitly set, so it defaults to UTC regardless of where this box is physically deployed - not a display bug, and consistent with every other timestamp shown elsewhere on this site. See <code>docs/OPERATIONAL-DECISIONS.md</code> ("Field Tools / Offline Reference Instruments") if you want this changed.</p>
            <?php endif; ?>
        </div>

        <h2>Right now</h2>
        <div class="stat-grid" id="ft-now-grid" data-base-unix="<?= (int) $snap['unix'] ?>" data-tz="<?= htmlspecialchars($snap['tz_name']) ?>">
            <div class="stat-card"><span class="stat-label">Local (24h)</span><span class="stat-value" id="ft-local24"><?= htmlspecialchars($snap['local_24h']) ?></span></div>
            <div class="stat-card"><span class="stat-label">Local (12h)</span><span class="stat-value" id="ft-local12"><?= htmlspecialchars($snap['local_12h']) ?></span></div>
            <div class="stat-card"><span class="stat-label">UTC</span><span class="stat-value" id="ft-utc"><?= htmlspecialchars($snap['utc_24h']) ?></span></div>
            <div class="stat-card"><span class="stat-label">ISO-8601 (local)</span><span class="stat-value" id="ft-iso-local"><?= htmlspecialchars($snap['iso8601_local']) ?></span></div>
            <div class="stat-card"><span class="stat-label">ISO-8601 (UTC)</span><span class="stat-value" id="ft-iso-utc"><?= htmlspecialchars($snap['iso8601_utc']) ?></span></div>
            <div class="stat-card"><span class="stat-label">Unix timestamp</span><span class="stat-value" id="ft-unix"><?= (int) $snap['unix'] ?></span></div>
            <div class="stat-card"><span class="stat-label">Weekday</span><span class="stat-value" id="ft-weekday"><?= htmlspecialchars($snap['weekday']) ?></span></div>
            <div class="stat-card"><span class="stat-label">Day of year</span><span class="stat-value" id="ft-doy"><?= (int) $snap['day_of_year'] ?> of <?= (int) $snap['days_in_year'] ?></span></div>
            <div class="stat-card"><span class="stat-label">Date</span><span class="stat-value" id="ft-datelong"><?= htmlspecialchars($snap['date_long']) ?></span></div>
            <div class="stat-card"><span class="stat-label">Configured timezone</span><span class="stat-value"><?= htmlspecialchars($snap['tz_name']) ?></span></div>
            <div class="stat-card"><span class="stat-label">System uptime</span><span class="stat-value"><?= htmlspecialchars(piratebox_fmt_duration($uptimeSeconds)) ?></span></div>
        </div>
        <p class="muted" id="ft-live-note">Ticking live from the reading above (this browser's timer, not its own clock) - reload the page for a fresh reading from the device itself.</p>

        <noscript>
            <p class="help-note">JavaScript is off, so the tools below (elapsed-time calculator, timestamp converter, arbitrary-date lookup) aren't interactive - the "Right now" reading above is still accurate; it's rendered by the server, not JavaScript.</p>
        </noscript>

        <h2>Elapsed-time / duration calculator</h2>
        <p>Enter a start and end date/time (your connected device's own clock and timezone are used to interpret what you type here, not the PirateBox's) to get the duration between them.</p>
        <div class="fieldtools-tool" id="ft-elapsed-tool">
            <div class="fieldtools-row">
                <label for="ft-elapsed-start">Start</label>
                <input type="datetime-local" id="ft-elapsed-start">
            </div>
            <div class="fieldtools-row">
                <label for="ft-elapsed-end">End</label>
                <input type="datetime-local" id="ft-elapsed-end">
            </div>
            <p class="fieldtools-result" id="ft-elapsed-result" aria-live="polite">Enter both a start and end time.</p>
            <p class="muted">A daylight-saving-time change between the two moments can shift the result by about an hour - this is a plain clock-time subtraction, not a timezone-aware one.</p>
        </div>

        <h2>Unix timestamp converter</h2>
        <div class="fieldtools-tool" id="ft-unix-tool">
            <div class="fieldtools-row">
                <label for="ft-unix-input">Unix timestamp (seconds)</label>
                <input type="number" id="ft-unix-input" inputmode="numeric" step="1" placeholder="e.g. 1735689600">
            </div>
            <p class="fieldtools-result" id="ft-unix-result" aria-live="polite">Enter a timestamp above.</p>
            <div class="fieldtools-row">
                <label for="ft-unix-datetime">...or pick a date/time (this device's local time)</label>
                <input type="datetime-local" id="ft-unix-datetime">
            </div>
            <p class="fieldtools-result" id="ft-unix-datetime-result" aria-live="polite"></p>
        </div>

        <h2>Date lookup - weekday &amp; day of year</h2>
        <p>Pure calendar arithmetic - the weekday and day-of-year for any date are the same everywhere on Earth, so no timezone is involved here.</p>
        <div class="fieldtools-tool" id="ft-dateinfo-tool">
            <div class="fieldtools-row">
                <label for="ft-dateinfo-input">Date</label>
                <input type="date" id="ft-dateinfo-input">
            </div>
            <p class="fieldtools-result" id="ft-dateinfo-result" aria-live="polite">Pick a date above.</p>
        </div>

        <h2>12-hour &harr; 24-hour</h2>
        <div class="fieldtools-tool" id="ft-12-24-tool">
            <div class="fieldtools-row">
                <label for="ft-time-input">Time</label>
                <input type="time" id="ft-time-input">
            </div>
            <p class="fieldtools-result" id="ft-time-result" aria-live="polite">Enter a time above.</p>
        </div>
    </div>

    <script src="/assets/fieldtools.js"></script>
    <?php require_once __DIR__ . '/../../../../includes/footer.php'; ?>
</body>

</html>
