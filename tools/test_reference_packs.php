<?php

declare(strict_types=1);

// Deterministic tests for includes/reference_packs.php - matches the
// project's existing dependency-free tools/test_*.php convention.
// Run with: php tools/test_reference_packs.php

require_once __DIR__ . '/../var/www/html/includes/reference_packs.php';

$failures = [];
$passCount = 0;

function rp_assert_eq(string $label, $actual, $expected): void
{
    global $failures, $passCount;
    if ($actual !== $expected) {
        $failures[] = "$label: expected " . var_export($expected, true) . ", got " . var_export($actual, true);
        return;
    }
    $passCount++;
}

// --- piratebox_reference_pack_entry_count(): boundary/malformed cases ---

$tmpDir = sys_get_temp_dir() . '/piratebox_rp_test_' . getmypid();
mkdir($tmpDir);
mkdir($tmpDir . '/data');

function rp_write(string $tmpDir, string $rel, string $content): void
{
    $path = $tmpDir . '/data/' . $rel;
    @mkdir(dirname($path), 0777, true);
    file_put_contents($path, $content);
}

// Use a temp includes/ dir so __DIR__ . '/../data/...' resolves under
// our sandbox, without touching the real repo data files.
mkdir($tmpDir . '/includes');
copy(__DIR__ . '/../var/www/html/includes/reference_packs.php', $tmpDir . '/includes/reference_packs.php');

function rp_count_in_sandbox(string $tmpDir, string $packId, ?string $dataFile)
{
    $code = 'require "' . $tmpDir . '/includes/reference_packs.php"; '
        . 'echo json_encode(piratebox_reference_pack_entry_count(' . var_export($packId, true) . ', ' . var_export($dataFile, true) . '));';
    $out = shell_exec(PHP_BINARY . ' -r ' . escapeshellarg($code));
    return json_decode((string) $out, true);
}

rp_write($tmpDir, 'nonexistent-does-not-exist.json', ''); // not actually written, just documenting intent
rp_assert_eq('Missing file -> null (unknown, not zero)', rp_count_in_sandbox($tmpDir, 'x', 'truly-missing.json'), null);

rp_write($tmpDir, 'empty-array.json', '[]');
rp_assert_eq('Empty array -> 0', rp_count_in_sandbox($tmpDir, 'x', 'empty-array.json'), 0);

rp_write($tmpDir, 'three-items.json', '[1,2,3]');
rp_assert_eq('Three-item array -> 3', rp_count_in_sandbox($tmpDir, 'x', 'three-items.json'), 3);

rp_write($tmpDir, 'malformed.json', '{not valid json');
rp_assert_eq('Malformed JSON -> null (unknown, never fabricated zero)', rp_count_in_sandbox($tmpDir, 'x', 'malformed.json'), null);

rp_write($tmpDir, 'local-blank.json', json_encode([
    'region_label' => '', 'hospitals' => [], 'shelters' => [],
    'amateur_repeaters' => [], 'other_resources' => [], 'map_references' => [],
]));
rp_assert_eq('local-reference: blank region + all empty arrays -> 0 (universal numbers not counted)', rp_count_in_sandbox($tmpDir, 'local-reference', 'local-blank.json'), 0);

rp_write($tmpDir, 'local-configured.json', json_encode([
    'region_label' => 'Somewhere, TX', 'hospitals' => [['name' => 'Test Hospital']],
    'shelters' => [], 'amateur_repeaters' => [], 'other_resources' => [], 'map_references' => [],
]));
rp_assert_eq('local-reference: region set + one hospital -> 2', rp_count_in_sandbox($tmpDir, 'local-reference', 'local-configured.json'), 2);

// --- piratebox_get_reference_packs(): against the REAL repo data (integration-style) ---

$packs = piratebox_get_reference_packs();
rp_assert_eq('Real pack list is non-empty', count($packs) > 0, true);

$byId = [];
foreach ($packs as $p) { $byId[$p['id']] = $p; }

rp_assert_eq('navigation-universal is INSTALLED (real, sourced content exists)', $byId['navigation-universal']['state'] ?? null, 'INSTALLED');
rp_assert_eq('navigation-universal scope is universal', $byId['navigation-universal']['scope'] ?? null, 'universal');
rp_assert_eq('local-reference is NOT_CONFIGURED by design (Stage 6)', $byId['local-reference']['state'] ?? null, 'NOT_CONFIGURED');
// world-reference-map shipped 2026-09-02 (static SVG built from public-
// domain Natural Earth data, sourced from Claude Code's own development
// environment rather than the Pi's own WAN-less connection - see
// docs/OPERATIONAL-DECISIONS.md) - state now reflects the real,
// live-checked file the same way every other pack does, not a
// hand-set override.
rp_assert_eq('world-reference-map key exists', array_key_exists('world-reference-map', $byId), true);
rp_assert_eq('world-reference-map is INSTALLED (real static asset now shipped)', $byId['world-reference-map']['state'] ?? null, 'INSTALLED');
rp_assert_eq('world-reference-map scope is universal', $byId['world-reference-map']['scope'] ?? null, 'universal');
rp_assert_eq('world-reference-map entry_count reflects its one-entry descriptor, not fabricated', $byId['world-reference-map']['entry_count'] ?? null, 1);

// us-reference-map shipped 2026-09-02 (same pipeline, one admin level
// down - National scope, not Universal).
rp_assert_eq('us-reference-map key exists', array_key_exists('us-reference-map', $byId), true);
rp_assert_eq('us-reference-map is INSTALLED', $byId['us-reference-map']['state'] ?? null, 'INSTALLED');
rp_assert_eq('us-reference-map scope is national, not universal', $byId['us-reference-map']['scope'] ?? null, 'national');
rp_assert_eq('us-reference-map entry_count reflects its one-entry descriptor', $byId['us-reference-map']['entry_count'] ?? null, 1);

$validStates = ['INSTALLED', 'NOT_CONFIGURED', 'CANDIDATE', 'UNKNOWN'];
$allValid = true;
foreach ($packs as $p) {
    if (!in_array($p['state'], $validStates, true)) $allValid = false;
}
rp_assert_eq('Every pack state is from the documented vocabulary', $allValid, true);

$validScopes = piratebox_reference_pack_scope_order();
$allScopesValid = true;
foreach ($packs as $p) {
    if (!in_array($p['scope'], $validScopes, true)) $allScopesValid = false;
}
rp_assert_eq('Every pack scope is from the Universal->Live hierarchy', $allScopesValid, true);

// --- piratebox_get_reference_packs(): state_override='candidate' branch ---
// No real pack uses this branch any more (world-reference-map shipped
// 2026-09-02), but the code path itself is still real and reachable for
// a genuinely-not-yet-sourceable future pack, so it stays covered here
// with a synthetic fixture rather than only via a real pack's data.
// Same sandbox trick as above (a fresh includes/+data/ pair so __DIR__
// . '/../data/reference-packs.json' resolves inside it, not the repo).
mkdir($tmpDir . '/candidate-sandbox/includes', 0777, true);
mkdir($tmpDir . '/candidate-sandbox/data', 0777, true);
copy(__DIR__ . '/../var/www/html/includes/reference_packs.php', $tmpDir . '/candidate-sandbox/includes/reference_packs.php');
file_put_contents($tmpDir . '/candidate-sandbox/data/reference-packs.json', json_encode([[
    'id' => 'synthetic-candidate', 'title' => 'Synthetic Candidate', 'scope' => 'universal',
    'url' => null, 'data_file' => null, 'license' => null, 'state_override' => 'candidate', 'note' => 'test fixture',
]]));
$candidateCode = 'require "' . $tmpDir . '/candidate-sandbox/includes/reference_packs.php"; echo json_encode(piratebox_get_reference_packs());';
$candidateOut = shell_exec(PHP_BINARY . ' -r ' . escapeshellarg($candidateCode));
$candidatePacks = json_decode((string) $candidateOut, true);
rp_assert_eq('state_override=candidate -> state CANDIDATE', $candidatePacks[0]['state'] ?? null, 'CANDIDATE');
rp_assert_eq('state_override=candidate -> entry_count stays null (never fabricated)', array_key_exists('entry_count', $candidatePacks[0] ?? []) ? $candidatePacks[0]['entry_count'] : 'MISSING', null);

// cleanup
function rp_rrmdir(string $dir): void
{
    if (!is_dir($dir)) return;
    foreach (scandir($dir) as $f) {
        if ($f === '.' || $f === '..') continue;
        $path = "$dir/$f";
        is_dir($path) ? rp_rrmdir($path) : unlink($path);
    }
    rmdir($dir);
}
rp_rrmdir($tmpDir);

echo "Reference pack tests: $passCount passed, " . count($failures) . " failed.\n";
if ($failures) {
    echo "\nFAILURES:\n";
    foreach ($failures as $f) {
        echo "  - $f\n";
    }
    exit(1);
}
exit(0);
