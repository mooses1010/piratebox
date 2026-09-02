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
     * What this device actually knows about where its clock comes from -
     * read-only, no shell_exec (PHP-FPM has it disabled - see
     * etc/php/8.4/fpm/php.ini), so this is limited to plain file/
     * directory reads, same constraint every other status reader in this
     * app already works within (see includes/metrics.php's own note).
     *
     * - rtc_detected: true the moment ANY /sys/class/rtc/rtcN device
     *   exists - this is exactly what a DS3231 (or any I2C RTC wired per
     *   docs/HARDWARE-INTEGRATION-DESIGN.md) makes appear, with no driver-
     *   specific code needed here. Today this is empty on this Pi (no RTC
     *   installed - see docs/RTC-TIME-READINESS-DESIGN.md), so this
     *   reads false; the day a DS3231 is added and the kernel overlay
     *   loads, this starts reading true with zero changes to this file.
     * - ntp_synchronized: systemd-timesyncd's own live verdict, read from
     *   the flag file it maintains (/run/systemd/timesync/synchronized
     *   exists only while it believes the clock is synced to a real NTP
     *   server). This Pi is an isolated access point with no confirmed
     *   uplink, so this is normally false by design, not a fault.
     * - fake_hwclock_installed: whether the "last known good" software
     *   fallback discussed in Stage 28 has since been installed (it
     *   wasn't as of that audit - installing it needs an explicit
     *   package-install approval this file doesn't grant itself).
     *
     * Deliberately does NOT report a "last successful NTP sync" instant -
     * no code anywhere on this device currently persists that moment (it
     * would need a new field in piratebox_status_helper.sh's periodic
     * write, which this stage did not add - see docs/OPERATIONAL-
     * DECISIONS.md for why that's future work, not fabricated here).
     */
    function piratebox_get_time_source_status(): array
    {
        $rtcDevices = @glob('/sys/class/rtc/rtc*') ?: [];
        return [
            'rtc_detected'          => count($rtcDevices) > 0,
            'rtc_device_count'      => count($rtcDevices),
            'ntp_synchronized'      => file_exists('/run/systemd/timesync/synchronized'),
            'fake_hwclock_installed' => file_exists('/etc/fake-hwclock.data'),
        ];
    }
}
