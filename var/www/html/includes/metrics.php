<?php

declare(strict_types=1);

// Needed for the PIRATEBOX_MODE_EMERGENCY/PIRATEBOX_MODE_NORMAL constants
// used below. require_once is safe even if a caller already loaded this.
require_once __DIR__ . '/mode.php';

// PirateBox shared metrics reader (Stage 21).
//
// Every function here is a read-only inspection of local state - the same
// /proc reads admin/index.php already performs, plus the same
// /run/piratebox/status.json helper file it already reads. This file does
// NOT duplicate admin/index.php's own copies of that logic (a deliberate
// choice - see docs/OPERATIONAL-DECISIONS.md, Stage 21 - refactoring
// admin/index.php to use this module was judged not worth the regression
// risk to an already-approved, destructive-action-containing page). It
// exists so the new public Stats page, and any future consumer (a status
// line on an OLED display, say - see Stage 29's design notes) can read the
// same numbers without a third copy of this logic.
//
// PRIVACY: everything here is either a system-wide aggregate (CPU temp,
// free RAM, Wi-Fi client COUNT) or content-catalog metadata (how many
// radio entries exist). Nothing here reads or exposes any individual
// visitor's identity, IP, MAC address, or activity - see the Stats page
// itself for the explicit privacy statement shown to visitors.

/**
 * Uptime in seconds, or null if /proc/uptime couldn't be read.
 */
if (!function_exists('piratebox_get_uptime_seconds')) {
    function piratebox_get_uptime_seconds(): ?float
    {
        $raw = @file_get_contents('/proc/uptime');
        if ($raw === false) return null;
        $parts = explode(' ', trim($raw));
        return isset($parts[0]) ? (float) $parts[0] : null;
    }
}

/**
 * [totalKb, availableKb] from /proc/meminfo, either possibly null.
 */
if (!function_exists('piratebox_get_meminfo_kb')) {
    function piratebox_get_meminfo_kb(): array
    {
        $totalKb = null;
        $availableKb = null;
        $raw = @file_get_contents('/proc/meminfo');
        if ($raw !== false) {
            if (preg_match('/^MemTotal:\s+(\d+)/m', $raw, $m)) $totalKb = (int) $m[1];
            if (preg_match('/^MemAvailable:\s+(\d+)/m', $raw, $m)) $availableKb = (int) $m[1];
        }
        return [$totalKb, $availableKb];
    }
}

/**
 * CPU temperature in Celsius, or null.
 */
if (!function_exists('piratebox_get_cpu_temp_c')) {
    function piratebox_get_cpu_temp_c(): ?float
    {
        $raw = @file_get_contents('/sys/class/thermal/thermal_zone0/temp');
        if ($raw === false || !is_numeric(trim($raw))) return null;
        return ((int) trim($raw)) / 1000.0;
    }
}

/**
 * 1/5/15-minute load averages from /proc/loadavg, each possibly null.
 * Not in open_basedir by name specifically, but the existing php.ini
 * allowlist already covers /proc/uptime and /proc/meminfo individually -
 * /proc/loadavg needs the same explicit addition before this will read
 * anything live. Until then (or if the read fails for any reason) this
 * degrades to [null, null, null], same as every other metric here.
 */
if (!function_exists('piratebox_get_loadavg')) {
    function piratebox_get_loadavg(): array
    {
        $raw = @file_get_contents('/proc/loadavg');
        if ($raw === false) return [null, null, null];
        $parts = explode(' ', trim($raw));
        return [
            isset($parts[0]) && is_numeric($parts[0]) ? (float) $parts[0] : null,
            isset($parts[1]) && is_numeric($parts[1]) ? (float) $parts[1] : null,
            isset($parts[2]) && is_numeric($parts[2]) ? (float) $parts[2] : null,
        ];
    }
}

/**
 * Reads the root status helper's snapshot (Wi-Fi client count, per-service
 * health, undervoltage) from /run/piratebox/status.json, with the same
 * staleness check admin/index.php already uses (helper runs every 30s; no
 * update in 5 minutes means the timer/service isn't running).
 *
 * Returns ['status' => array|null, 'stale' => bool]. 'status' is null if
 * the file is missing, unreadable, or not valid JSON - callers must always
 * check 'stale'/null-ness and show an honest "not reporting" state rather
 * than guessing, exactly like admin/index.php does.
 */
if (!function_exists('piratebox_get_helper_status')) {
    function piratebox_get_helper_status(): array
    {
        $status = null;
        $stale = true;
        $raw = @file_get_contents('/run/piratebox/status.json');
        if ($raw !== false) {
            $decoded = json_decode($raw, true);
            if (is_array($decoded)) {
                $status = $decoded;
                $age = time() - (int) ($decoded['generated_at'] ?? 0);
                $stale = $age > 300;
            }
        }
        return ['status' => $status, 'stale' => $stale];
    }
}

/**
 * Cumulative Emergency Mode runtime, computed from the plain append-only
 * transition log set_piratebox_mode.sh writes (data/mode-transitions.log,
 * "<unix timestamp> <mode>" per line). Best-effort by design, same as the
 * log itself:
 *   - Missing file (a device that has never switched mode, or predates
 *     Stage 21) -> zero seconds, not an error.
 *   - Malformed/unparseable lines are skipped individually rather than
 *     failing the whole computation.
 *   - If the log's last entry is "emergency" (currently in Emergency Mode),
 *     the still-open interval up to *now* is included, so the total is
 *     always correct as of the moment this function runs, not just as of
 *     the last logged transition.
 *   - This is a LOG, not the source of truth for current mode - current
 *     mode always still comes from piratebox_get_mode() /
 *     /tmp/piratebox/mode, exactly as everywhere else in this project.
 *
 * Returns [totalEmergencySeconds, transitionCount].
 */
if (!function_exists('piratebox_get_emergency_runtime_seconds')) {
    function piratebox_get_emergency_runtime_seconds(): array
    {
        $path = __DIR__ . '/../data/mode-transitions.log';
        $raw = @file_get_contents($path);
        if ($raw === false || trim($raw) === '') {
            return [0.0, 0];
        }

        $totalSeconds = 0.0;
        $transitionCount = 0;
        $emergencyStartedAt = null;

        foreach (explode("\n", $raw) as $line) {
            $line = trim($line);
            if ($line === '') continue;
            if (!preg_match('/^(\d+)\s+(normal|emergency)$/', $line, $m)) continue;

            $ts = (int) $m[1];
            $mode = $m[2];
            $transitionCount++;

            if ($mode === PIRATEBOX_MODE_EMERGENCY) {
                // A new Emergency period starting - only record the start
                // if one wasn't already open (defensive against a
                // duplicate/out-of-order log line; never double-count).
                if ($emergencyStartedAt === null) {
                    $emergencyStartedAt = $ts;
                }
            } else {
                // Returning to Normal closes any open Emergency interval.
                if ($emergencyStartedAt !== null) {
                    $totalSeconds += max(0, $ts - $emergencyStartedAt);
                    $emergencyStartedAt = null;
                }
            }
        }

        // Still in an open Emergency interval right now - count up to the
        // current moment so the total is accurate as-of "now", not just
        // as-of the last logged transition.
        if ($emergencyStartedAt !== null) {
            $totalSeconds += max(0, time() - $emergencyStartedAt);
        }

        return [$totalSeconds, $transitionCount];
    }
}
