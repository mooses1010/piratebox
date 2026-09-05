<?php

declare(strict_types=1);

// PirateBox Progression - read side, for the Captain's Log web page
// (public/utility/captains-log/). Reads /run/piratebox/
// progression-public.json, written every ~30s by
// piratebox_status_helper.sh (running as root) from
// piratebox_progression.py's own build_public_summary() - see that
// Python function's own header for the full "why a separate export"
// rationale. This is the exact same "privileged helper publishes a
// public tmpfs snapshot, PHP reads it directly" bridge
// includes/metrics.php's piratebox_get_helper_status() already uses
// for status.json - nothing new architecturally, one more consumer of
// an already-established pattern.
//
// IMPORTANT - this file trusts NOTHING it reads from that file as
// already-safe HTML: every string is escaped at render time by the
// page itself (htmlspecialchars, as everywhere else on this site).
// Progression data is written by a trusted local process, not visitor
// input, but treating it as untrusted at the render boundary anyway
// costs nothing and matches this project's own instruction to do so.
//
// Deliberately does NOT itself decide what's spoiler-safe - that
// decision was already made once, correctly, by
// piratebox_progression.py's build_public_summary() (the raw
// progression.json - achievement ids, cooldowns, seen_events, the
// total achievement count - is never even reachable from here; this
// file only ever sees the already-curated export). This file's own job
// is purely: read the file, validate its shape, degrade honestly on
// anything unexpected - the same "no fabricated success" discipline
// includes/device_memory.php and includes/capability_state.php already
// follow.

define('PIRATEBOX_PROGRESSION_PUBLIC_FILE', '/run/piratebox/progression-public.json');
define('PIRATEBOX_PROGRESSION_STALE_AFTER', 300); // matches metrics.php's own status.json staleness window

if (!function_exists('piratebox_parse_progression_public')) {
    /**
     * Pure, directly testable - takes the already-json_decode()'d value
     * (or null for "file missing/unreadable") rather than touching the
     * filesystem itself. Every shape - missing, malformed, the
     * daemon's own honest `{"available": false}` fallback, a
     * partially-populated file - degrades to `available => false`
     * rather than a guessed/fabricated profile.
     *
     * @param mixed $decoded whatever json_decode($raw, true) produced,
     *   or null if the file couldn't be read at all
     * @return array{
     *   available: bool,
     *   device_name: ?string, level: ?int, title: ?string,
     *   xp_total: ?int, xp_this_level_floor: ?int, xp_next_level_at: ?int,
     *   xp_progress_fraction: ?float,
     *   stats: array<string,int|bool>,
     *   achievements: list<array{name:string,hidden:bool,unlocked_at:?int}>,
     *   history: list<array{ts:int,kind:string,label:string}>,
     *   traits: array<string,string>,
     *   hardware: array<string,mixed>
     * }
     */
    function piratebox_parse_progression_public($decoded): array
    {
        $unavailable = [
            'available' => false,
            'device_name' => null, 'level' => null, 'title' => null,
            'xp_total' => null, 'xp_this_level_floor' => null, 'xp_next_level_at' => null,
            'xp_progress_fraction' => null,
            'stats' => [],
            'achievements' => [],
            'history' => [],
            'traits' => [],
            'hardware' => [],
        ];

        if (!is_array($decoded) || ($decoded['available'] ?? false) !== true) {
            return $unavailable;
        }

        $xp = is_array($decoded['xp'] ?? null) ? $decoded['xp'] : [];
        $device = is_array($decoded['device'] ?? null) ? $decoded['device'] : [];
        $stats = is_array($decoded['stats'] ?? null) ? $decoded['stats'] : [];
        $traits = is_array($decoded['traits'] ?? null) ? $decoded['traits'] : [];
        $hardware = is_array($decoded['hardware'] ?? null) ? $decoded['hardware'] : [];

        $achievements = [];
        $rawAchievements = is_array($decoded['achievements'] ?? null) ? $decoded['achievements'] : [];
        foreach ($rawAchievements as $a) {
            if (!is_array($a) || !isset($a['name']) || !is_string($a['name'])) continue;
            $achievements[] = [
                'name' => $a['name'],
                'hidden' => ($a['hidden'] ?? false) === true,
                'unlocked_at' => is_numeric($a['unlocked_at'] ?? null) ? (int) $a['unlocked_at'] : null,
            ];
        }

        $history = [];
        $rawHistory = is_array($decoded['history'] ?? null) ? $decoded['history'] : [];
        foreach ($rawHistory as $e) {
            if (!is_array($e) || !isset($e['label'], $e['kind']) || !is_string($e['label']) || !is_string($e['kind'])) continue;
            $history[] = [
                'ts' => is_numeric($e['ts'] ?? null) ? (int) $e['ts'] : 0,
                'kind' => $e['kind'],
                'label' => $e['label'],
            ];
        }
        // Newest first - a "Captain's Log" reads chronologically-recent-first,
        // matching every other feed on this site (chat, logbook, bulletin).
        usort($history, fn($a, $b) => $b['ts'] <=> $a['ts']);

        return [
            'available' => true,
            'device_name' => is_string($device['name'] ?? null) ? $device['name'] : null,
            'level' => is_int($xp['level'] ?? null) ? $xp['level'] : null,
            'title' => is_string($decoded['title'] ?? null) ? $decoded['title'] : null,
            'xp_total' => is_int($xp['total'] ?? null) ? $xp['total'] : null,
            'xp_this_level_floor' => is_int($xp['this_level_floor'] ?? null) ? $xp['this_level_floor'] : null,
            'xp_next_level_at' => is_int($xp['next_level_at'] ?? null) ? $xp['next_level_at'] : null,
            'xp_progress_fraction' => is_numeric($xp['progress_fraction'] ?? null) ? (float) $xp['progress_fraction'] : null,
            'stats' => $stats,
            'achievements' => $achievements,
            'history' => $history,
            'traits' => $traits,
            'hardware' => $hardware,
        ];
    }
}

if (!function_exists('piratebox_get_progression_public')) {
    /**
     * Thin filesystem wrapper - returns ['data' => ..., 'stale' => bool]
     * exactly like piratebox_get_helper_status() does for status.json,
     * so page code can use the same "if stale/unavailable, say so
     * honestly" pattern already established there.
     */
    function piratebox_get_progression_public(): array
    {
        $raw = @file_get_contents(PIRATEBOX_PROGRESSION_PUBLIC_FILE);
        if ($raw === false) {
            return ['data' => piratebox_parse_progression_public(null), 'stale' => true];
        }
        $decoded = json_decode($raw, true);
        $data = piratebox_parse_progression_public($decoded);
        $age = time() - (int) ($decoded['generated_at'] ?? 0);
        $stale = !$data['available'] || $age > PIRATEBOX_PROGRESSION_STALE_AFTER;
        return ['data' => $data, 'stale' => $stale];
    }
}
