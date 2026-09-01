<?php

declare(strict_types=1);

// PirateBox content profile (Stage 31) - a small, persisted, operator-
// selectable deployment-scenario setting.
//
// This is purely a DISPLAY PRIORITY hint, never a content filter: it
// reorders which Emergency Reference topics appear first within each of
// that page's existing category sections, and never hides, removes, or
// duplicates anything - every topic is still shown, in every profile,
// same as before this stage. It also applies identically in Normal and
// Emergency Mode (this file never reads piratebox_get_mode() and no
// caller of it should either), preserving the mode-content-parity rule
// every stage since the Emergency Mode foundation has maintained.
//
// Persisted on the SD card (data/content-profile.json), unlike mode.php's
// deliberately volatile /tmp state - a deployment's regional hazard
// profile is a fact about where this specific device is physically
// deployed, which doesn't change on every boot the way presentation mode
// can, so it should survive a reboot the same way device-id.json does.
// Read-only from the public site; only admin/index.php's
// 'set_content_profile' action (non-destructive, no confirm-checkbox
// needed - same reasoning as Stage 16's reply_recovery) ever writes it.

define('PIRATEBOX_CONTENT_PROFILE_FILE', __DIR__ . '/../data/content-profile.json');

// Label shown in the admin dropdown and (when a non-default profile is
// active) as a small transparency note on the Emergency Reference page,
// so reordering is never a silent surprise to someone reading the page.
define('PIRATEBOX_CONTENT_PROFILES', [
    'general_community' => 'General / Community (no reordering)',
    'hurricane_coastal'  => 'Hurricane / Coastal Storm',
    'wildfire'           => 'Wildfire',
    'winter_storm'       => 'Winter Storm',
]);

// Which Emergency Reference topic ids (data/utility/emergency/topics.json)
// get priority under each profile, most-relevant first. Deliberately
// spans multiple of the page's existing category sections (hazards,
// utilities, essentials, planning) rather than only 'hazards' - a
// hurricane deployment cares about downed-power-lines (utilities) and
// evacuation (planning) just as much as flood (hazards), so priority is
// applied per-section (see piratebox_apply_content_profile_order()),
// not by moving topics between sections. 'general_community' has no
// entry here on purpose - empty priority means "no reordering," handled
// explicitly below rather than needing a listed no-op.
define('PIRATEBOX_CONTENT_PROFILE_PRIORITY_TOPICS', [
    'hurricane_coastal' => [
        'flood', 'thunderstorms-lightning', 'evacuation', 'shelter-in-place',
        'power-outage', 'downed-power-lines', 'water-storage-safety',
        'communications-outage',
    ],
    'wildfire' => [
        'wildfire-smoke', 'evacuation', 'extreme-heat', 'shelter-in-place',
        'power-outage', 'communications-outage',
    ],
    'winter_storm' => [
        'extreme-cold', 'power-outage', 'carbon-monoxide', 'generator-safety',
        'lighting-fire-safety', 'downed-power-lines', 'water-storage-safety',
    ],
]);

if (!function_exists('piratebox_get_content_profile')) {
    /**
     * Currently active profile key. Any failure mode - missing file,
     * unreadable, malformed JSON, or a value that isn't one of
     * PIRATEBOX_CONTENT_PROFILES's known keys - resolves to
     * 'general_community' (no reordering), the only safe default, same
     * philosophy as piratebox_get_mode()'s "unknown always means the
     * safe baseline" rule.
     */
    function piratebox_get_content_profile(): string
    {
        $raw = @file_get_contents(PIRATEBOX_CONTENT_PROFILE_FILE);
        if ($raw !== false) {
            $decoded = json_decode($raw, true);
            if (is_array($decoded) && isset($decoded['profile'])
                && array_key_exists($decoded['profile'], PIRATEBOX_CONTENT_PROFILES)) {
                return $decoded['profile'];
            }
        }
        return 'general_community';
    }
}

if (!function_exists('piratebox_set_content_profile')) {
    /**
     * Persists a new active profile. Rejects anything not in
     * PIRATEBOX_CONTENT_PROFILES (defensive against a tampered/invalid
     * POST value, same allowlist approach Stage 22 already established
     * for the bulletin board's category field). Atomic
     * temp-file-then-rename write, same pattern every other store in
     * this project uses.
     */
    function piratebox_set_content_profile(string $profile): bool
    {
        if (!array_key_exists($profile, PIRATEBOX_CONTENT_PROFILES)) {
            return false;
        }
        $tmp = PIRATEBOX_CONTENT_PROFILE_FILE . '.tmp.' . getmypid() . '.' . bin2hex(random_bytes(4));
        if (file_put_contents($tmp, json_encode(['profile' => $profile], JSON_PRETTY_PRINT)) === false) {
            return false;
        }
        if (!rename($tmp, PIRATEBOX_CONTENT_PROFILE_FILE)) {
            @unlink($tmp);
            return false;
        }
        return true;
    }
}

if (!function_exists('piratebox_apply_content_profile_order')) {
    /**
     * Reorders $topics (an array of rows each carrying an 'id') so any
     * topic whose id is in the active profile's priority list comes
     * first, in that priority order, followed by every remaining topic
     * in its original order. A stable partial sort, never a filter -
     * every input row is present in the output, always. Returns $topics
     * completely unchanged for 'general_community' or any profile with
     * no priority list defined.
     */
    function piratebox_apply_content_profile_order(array $topics, string $profile): array
    {
        $priority = PIRATEBOX_CONTENT_PROFILE_PRIORITY_TOPICS[$profile] ?? [];
        if (empty($priority)) {
            return $topics;
        }
        $priorityIndex = array_flip($priority);
        $prioritized = [];
        $rest = [];
        foreach ($topics as $t) {
            $id = $t['id'] ?? null;
            if ($id !== null && isset($priorityIndex[$id])) {
                $prioritized[$priorityIndex[$id]] = $t;
            } else {
                $rest[] = $t;
            }
        }
        ksort($prioritized);
        return array_merge(array_values($prioritized), $rest);
    }
}
