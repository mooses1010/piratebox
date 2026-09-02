<?php

declare(strict_types=1);

// Field Tools (Post-Stage-32) - time/date helpers.
//
// Two jobs: (1) a plain snapshot of "what time does this device think it
// is, in every format someone in the field might need," and (2) an
// honest report of WHY it thinks that - this Pi has no hardware RTC as
// of this writing (see docs/RTC-TIME-READINESS-DESIGN.md, Stage 28), so
// (2) matters as much as (1). Nothing here claims accuracy the device
// doesn't actually have.
//
// piratebox_get_time_source_status() is written to need zero code
// changes when a DS3231 (or any /sys/class/rtc-visible RTC) is later
// installed - it already reports whatever it finds there. See that
// function's own comment.

require_once __DIR__ . '/helpers.php'; // piratebox_fmt_duration()

if (!function_exists('piratebox_fieldtools_now_snapshot')) {
    /**
     * A full snapshot of the current time in every format Field Tools'
     * Time page shows. Takes an optional timestamp (for testing / for
     * rendering a non-"now" moment) - defaults to the real current time.
     */
    function piratebox_fieldtools_now_snapshot(?int $ts = null): array
    {
        $ts = $ts ?? time();
        $tz = date_default_timezone_get();

        return [
            'unix'          => $ts,
            'tz_name'       => $tz,
            'local_24h'     => date('Y-m-d H:i:s', $ts),
            'local_12h'     => date('Y-m-d g:i:s A', $ts),
            'utc_24h'       => gmdate('Y-m-d H:i:s', $ts) . ' UTC',
            'iso8601_local' => date(DATE_ATOM, $ts),
            'iso8601_utc'   => gmdate('Y-m-d\TH:i:s\Z', $ts),
            'weekday'       => date('l', $ts),
            'date_long'     => date('F j, Y', $ts),
            'day_of_year'   => (int) date('z', $ts) + 1, // date('z') is 0-indexed
            'days_in_year'  => ((int) date('L', $ts) === 1) ? 366 : 365,
            'week_of_year'  => (int) date('W', $ts),
        ];
    }
}

if (!function_exists('piratebox_elapsed_between')) {
    /**
     * Human-readable elapsed time between two unix timestamps, plus
     * whether $endTs is after, before, or equal to $startTs. Reuses
     * piratebox_fmt_duration() (already tested/used by the Stats page)
     * rather than a second duration formatter.
     *
     * @return array{seconds:int, direction:string, formatted:string}
     *   direction is 'after', 'before', or 'same'.
     */
    function piratebox_elapsed_between(int $startTs, int $endTs): array
    {
        $diff = $endTs - $startTs;
        $direction = $diff > 0 ? 'after' : ($diff < 0 ? 'before' : 'same');
        return [
            'seconds'   => $diff,
            'direction' => $direction,
            'formatted' => piratebox_fmt_duration((float) abs($diff)),
        ];
    }
}

if (!function_exists('piratebox_get_time_source_status')) {
    /**
     * What this device actually knows about where its clock comes from.
     *
     * NOT a direct filesystem read (an earlier version of this function
     * tried that - /sys/class/rtc, /run/systemd/timesync/synchronized,
     * /etc/fake-hwclock.data - and found live that PHP-FPM's own
     * open_basedir restriction, etc/php/8.4/fpm/php.ini, blocks every one
     * of those paths, producing a PHP warning and a silently-wrong
     * "false" that looked like a real negative result but wasn't). This
     * reads piratebox_status_helper.sh's periodic snapshot instead - the
     * established pattern this whole app already uses for exactly this
     * situation (see includes/metrics.php's own header: "PHP cannot
     * obtain [this] on its own... without exec()/shell_exec(), both
     * deliberately unavailable"). That script runs as root with no
     * open_basedir restriction and publishes a "time_source" block into
     * /run/piratebox/status.json (which IS inside open_basedir) - see
     * that script for what it actually checks and why:
     * - rtc_detected: true the moment ANY /sys/class/rtc/rtcN device
     *   exists - exactly what a DS3231 (or any I2C RTC wired per
     *   docs/HARDWARE-INTEGRATION-DESIGN.md) makes appear, no driver-
     *   specific code needed anywhere in this chain.
     * - ntp_synchronized: systemd-timesyncd's own live verdict. Normally
     *   false on this device by design (isolated AP, no confirmed
     *   uplink), not a fault.
     * - fake_hwclock_installed: whether Stage 28's other candidate
     *   mitigation has since been installed.
     *
     * @return array{available:bool, stale:bool, rtc_detected:?bool,
     *   ntp_synchronized:?bool, fake_hwclock_installed:?bool}
     *   `available` is false if the status helper hasn't been updated to
     *   publish this block yet (an old copy of piratebox_status_helper.sh
     *   still running) or hasn't reported at all - the three data fields
     *   are then null, never a fabricated guess. `stale` mirrors
     *   piratebox_get_helper_status()'s own >300s staleness window.
     *
     * Deliberately does NOT report a "last successful NTP sync" instant -
     * no code anywhere on this device currently persists that moment (see
     * docs/OPERATIONAL-DECISIONS.md for why that's future work, not
     * fabricated here).
     */
    function piratebox_get_time_source_status(): array
    {
        require_once __DIR__ . '/metrics.php'; // piratebox_get_helper_status()
        $helper = piratebox_get_helper_status();
        $timeSource = $helper['status']['time_source'] ?? null;
        $available = !$helper['stale'] && is_array($timeSource);
        return [
            'available'              => $available,
            'stale'                  => $helper['stale'],
            'rtc_detected'           => $available ? (bool) ($timeSource['rtc_detected'] ?? false) : null,
            'ntp_synchronized'       => $available ? (bool) ($timeSource['ntp_synchronized'] ?? false) : null,
            'fake_hwclock_installed' => $available ? (bool) ($timeSource['fake_hwclock_installed'] ?? false) : null,
        ];
    }
}
