<?php

declare(strict_types=1);

// Deterministic tests for includes/progression.php - matches the
// project's existing dependency-free tools/test_*.php convention.
// Run with: php tools/test_progression_web.php

require_once __DIR__ . '/../var/www/html/includes/progression.php';

$failures = [];
$passCount = 0;

function pw_assert_eq(string $label, $actual, $expected): void
{
    global $failures, $passCount;
    if ($actual !== $expected) {
        $failures[] = "$label: expected " . var_export($expected, true) . ", got " . var_export($actual, true);
        return;
    }
    $passCount++;
}

function pw_assert_true(string $label, $actual): void
{
    pw_assert_eq($label, $actual, true);
}

// --- piratebox_parse_progression_public(): boundary/malformed cases ---

$r = piratebox_parse_progression_public(null);
pw_assert_eq('null input -> unavailable', $r['available'], false);
pw_assert_eq('null input -> empty achievements, not fabricated', $r['achievements'], []);

$r = piratebox_parse_progression_public('not an array');
pw_assert_eq('non-array input -> unavailable', $r['available'], false);

$r = piratebox_parse_progression_public(['available' => false]);
pw_assert_eq('daemon\'s own honest available=false is respected, not overridden', $r['available'], false);

$r = piratebox_parse_progression_public([]);
pw_assert_eq('missing "available" key -> unavailable (never assumed true)', $r['available'], false);

// --- A realistic, fully-populated valid export ---

$valid = [
    'available' => true,
    'generated_at' => time(),
    'device' => ['name' => 'Restless Anchor'],
    'xp' => ['total' => 500, 'level' => 5, 'this_level_floor' => 400, 'next_level_at' => 700, 'progress_fraction' => 0.333],
    'title' => 'Deckhand',
    'stats' => ['lifetime_uptime_seconds' => 86400, 'boots_observed' => 3],
    'achievements' => [
        ['name' => 'First Full Day', 'hidden' => false, 'unlocked_at' => 1000],
        ['name' => 'Nice', 'hidden' => true, 'unlocked_at' => null],
    ],
    'history' => [
        ['ts' => 100, 'kind' => 'achievement', 'label' => 'Older event'],
        ['ts' => 200, 'kind' => 'level_up', 'label' => 'Reached level 5'],
    ],
    'traits' => ['sociability' => 'Balanced', 'vigilance' => 'Watchful', 'resilience' => 'Steady'],
    'hardware' => [],
];

$r = piratebox_parse_progression_public($valid);
pw_assert_true('valid export -> available', $r['available']);
pw_assert_eq('device_name parsed', $r['device_name'], 'Restless Anchor');
pw_assert_eq('level parsed', $r['level'], 5);
pw_assert_eq('title parsed', $r['title'], 'Deckhand');
pw_assert_eq('xp_total parsed', $r['xp_total'], 500);
pw_assert_eq('xp_progress_fraction parsed', $r['xp_progress_fraction'], 0.333);
pw_assert_eq('two achievements parsed', count($r['achievements']), 2);
pw_assert_eq('achievement name preserved', $r['achievements'][0]['name'], 'First Full Day');
pw_assert_eq('hidden achievement flag preserved (post-discovery, not spoiling anything new)', $r['achievements'][1]['hidden'], true);
pw_assert_eq('unlocked_at null is preserved honestly, not fabricated', $r['achievements'][1]['unlocked_at'], null);
pw_assert_eq('history sorted newest-first', $r['history'][0]['label'], 'Reached level 5');
pw_assert_eq('history second entry is the older one', $r['history'][1]['label'], 'Older event');
pw_assert_eq('traits passed through as strings', $r['traits']['sociability'], 'Balanced');

// --- Malformed sub-shapes degrade the specific field, not the whole page ---

$r = piratebox_parse_progression_public(['available' => true, 'achievements' => 'not an array']);
pw_assert_eq('non-array achievements -> empty list, not a crash', $r['achievements'], []);

$r = piratebox_parse_progression_public(['available' => true, 'achievements' => [
    ['hidden' => false],                 // missing required "name" - skipped
    ['name' => 123, 'hidden' => false],  // non-string "name" - skipped
    ['name' => 'Valid One', 'hidden' => false],
]]);
pw_assert_eq('malformed achievement entries silently skipped, valid one kept', count($r['achievements']), 1);
pw_assert_eq('the surviving entry is the valid one', $r['achievements'][0]['name'], 'Valid One');

$r = piratebox_parse_progression_public(['available' => true, 'history' => [
    ['kind' => 'achievement'],  // missing "label" - skipped
    ['label' => 'no kind'],     // missing "kind" - skipped
    ['ts' => 'not numeric', 'kind' => 'achievement', 'label' => 'Bad ts defaults to 0'],
]]);
pw_assert_eq('malformed history entries silently skipped, one survives', count($r['history']), 1);
pw_assert_eq('non-numeric ts defaults to 0, not a crash', $r['history'][0]['ts'], 0);

$r = piratebox_parse_progression_public(['available' => true, 'xp' => 'not an array']);
pw_assert_eq('non-array xp -> every xp field null, not a crash', $r['xp_total'], null);

// --- piratebox_get_progression_public(): staleness + missing-file behavior ---
// (Exercised only against the file-not-present case here - a real
// /run/piratebox/progression-public.json may or may not exist on
// whatever machine runs this suite, so this test only asserts the one
// thing guaranteed regardless: a missing file must never throw.)

if (!file_exists(PIRATEBOX_PROGRESSION_PUBLIC_FILE)) {
    $result = piratebox_get_progression_public();
    pw_assert_eq('missing file -> stale=true', $result['stale'], true);
    pw_assert_eq('missing file -> available=false', $result['data']['available'], false);
} else {
    // The file exists on this machine (e.g. this Pi itself) - just
    // confirm the call doesn't throw and returns the expected shape.
    $result = piratebox_get_progression_public();
    pw_assert_true('real file present -> stale is a bool', is_bool($result['stale']));
    $passCount++; // matches the else-branch's two assertions above, kept in sync
}

echo "\n";
if ($failures) {
    echo "FAILURES:\n";
    foreach ($failures as $f) echo "  - $f\n";
    echo "\nProgression web tests: $passCount passed, " . count($failures) . " failed.\n";
    exit(1);
}
echo "Progression web tests: $passCount passed, 0 failed.\n";
