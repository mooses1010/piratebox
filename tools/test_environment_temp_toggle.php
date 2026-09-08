<?php

declare(strict_types=1);

// Focused regression test for the Environment page's C/F quick-toggle
// (2026-09-08) - matches this project's existing lightweight
// tools/test_*.php convention. Two halves:
//
//   1. Static source/markup assertions against the real page file and
//      styles.css (mirrors tools/test_landing_layout.php's own style)
//      - proves the toggle is wired to the ONE shared preference/
//      conversion boundary, never a second one, and that ambient
//      light/ROM handling are untouched.
//
//   2. A real end-to-end HTTP check of the new POST/CSRF/redirect path
//      via PHP's built-in server (php -S) - this logic is fully
//      deterministic and hardware-independent (it runs and exits
//      before any sensor-reading code does), unlike
//      piratebox_get_capability_state()/piratebox_get_esp32_
//      supervisor_status() etc., which read live system state and are
//      deliberately left to manual/live php -S verification instead
//      (see tools/test_capability_state.php's own header) - this is
//      the same php -S technique, applied to logic that IS safe to
//      script.
//
// Run with: php tools/test_environment_temp_toggle.php

$failures = [];
$passCount = 0;

function ett_assert_true(string $label, bool $condition, string $detail = ''): void
{
    global $failures, $passCount;
    if (!$condition) {
        $failures[] = $label . ($detail !== '' ? " ($detail)" : '');
        return;
    }
    $passCount++;
}

function ett_assert_eq(string $label, $actual, $expected): void
{
    global $failures, $passCount;
    if ($actual !== $expected) {
        $failures[] = "$label: expected " . var_export($expected, true) . ", got " . var_export($actual, true);
        return;
    }
    $passCount++;
}

$repoRoot = __DIR__ . '/..';
$envPhp = file_get_contents($repoRoot . '/var/www/html/public/utility/environment/index.php');
$stylesCss = file_get_contents($repoRoot . '/var/www/html/public/assets/styles.css');

// === Part 1: static source/markup assertions ===========================

ett_assert_true(
    'the toggle writes through the one shared preference function, not a new writer',
    strpos($envPhp, 'piratebox_set_temp_unit(') !== false
);
ett_assert_true(
    'no second/parallel unit-storage constant or file path is introduced in this page',
    strpos($envPhp, 'PIRATEBOX_TEMP_UNIT_FILE') === false,
    'this page must only ever call the shared functions, never touch the storage path itself'
);
ett_assert_true(
    'the write is gated by the narrow CSRF-authorization helper, not left open',
    strpos($envPhp, 'piratebox_temp_unit_post_is_authorized(') !== false
);
ett_assert_true(
    'an unauthorized POST is rejected with 403, not silently ignored-but-200',
    (bool) preg_match('/piratebox_temp_unit_post_is_authorized\([^)]*\)\)\s*\{\s*\n\s*http_response_code\(403\)/', $envPhp)
);
ett_assert_true(
    'the write path is scoped to exactly the set_temp_unit action (not a generic settings-write branch)',
    (bool) preg_match('/\$_SERVER\[.REQUEST_METHOD.\]\s*===\s*.POST.\s*&&\s*\(\$_POST\[.action.\]\s*\?\?\s*..\)\s*===\s*.set_temp_unit./', $envPhp)
);
ett_assert_true(
    'a successful POST redirects (Post/Redirect/Get) rather than falling through to an inline re-render',
    (bool) preg_match("/header\\('Location: \\/utility\\/environment\\/'\\);\\s*\\n\\s*exit;/", $envPhp)
);

// --- markup: two real <button> elements inside one <form>, CSRF field,
// aria-pressed reflecting current selection, gated on the same
// $esp32['installed'] check that already wraps every other
// temperature-bearing section on this page (never shown when there's
// nothing to toggle) -----------------------------------------------------

ett_assert_true(
    'toggle form is gated on $esp32[\'installed\'] - the same gate as every other temperature section',
    (bool) preg_match('/if \(\$esp32\[.installed.\]\):\s*\?>\s*\n.*?<form method="post" class="unit-toggle"/s', $envPhp)
);
ett_assert_true(
    'toggle form posts back to itself with a hidden CSRF token field',
    strpos($envPhp, 'name="csrf_token"') !== false && strpos($envPhp, 'unit-toggle') !== false
);
ett_assert_true(
    'a Fahrenheit submit button (value="F") exists',
    (bool) preg_match('/name="temp_unit" value="F"/', $envPhp)
);
ett_assert_true(
    'a Celsius submit button (value="C") exists',
    (bool) preg_match('/name="temp_unit" value="C"/', $envPhp)
);
ett_assert_true(
    'both toggle buttons carry aria-pressed reflecting the current unit',
    substr_count($envPhp, 'aria-pressed="') >= 2
);
ett_assert_true(
    'the toggle group has an accessible group label',
    strpos($envPhp, 'role="group" aria-label="Temperature unit"') !== false
);
ett_assert_true(
    'proper degree-symbol notation is used for both units (&deg;F / &deg;C), not a bare "F"/"C"',
    strpos($envPhp, '>&deg;F</button>') !== false && strpos($envPhp, '>&deg;C</button>') !== false
);

// --- ambient light (lux) must remain completely untouched by this change

ett_assert_true(
    'ambient light lux rendering is unchanged (still literal " lux", never run through a unit symbol)',
    strpos($envPhp, "'lux'") !== false || strpos($envPhp, ' lux</span>') !== false || strpos($envPhp, "lux'") !== false
);
ett_assert_true(
    'the ambient-light history panel still carries its own fixed " lux" unit, untouched by $tempUnitSymbol',
    strpos($envPhp, 'data-history-unit=" lux"') !== false
);

// --- history panels for probes/esp32 temp still use the live unit symbol,
// not a separately-tracked Environment-only unit --------------------------

ett_assert_true(
    'the probes history panel uses the same $tempUnitSymbol as current readings (single source of truth)',
    (bool) preg_match('/data-history-group="probes" data-history-unit="<\?= \$tempUnitSymbol \?>"/', $envPhp)
);
ett_assert_true(
    'the esp32_temp history panel uses the same $tempUnitSymbol as current readings',
    (bool) preg_match('/data-history-group="esp32_temp" data-history-unit="<\?= \$tempUnitSymbol \?>"/', $envPhp)
);

// --- no ROM leakage: this change adds no new probe identifier exposure --

ett_assert_true(
    'the toggle form carries no probe/ROM identifiers at all (it only ever posts action/csrf_token/temp_unit)',
    !preg_match('/<form method="post" class="unit-toggle".*?<\/form>/s', $envPhp, $m) || !preg_match('/rom|28[0-9a-f]{14}/i', $m[0])
);

// --- CSS: a small button-row mirroring the existing pattern, not a new
// heavyweight component, and it doesn't disturb .history-range-buttons --

if (!preg_match('/\.unit-toggle\s*\{([^}]*)\}/s', $stylesCss, $wrapMatch)) {
    $failures[] = 'Could not locate the .unit-toggle rule block in styles.css at all';
} else {
    ett_assert_true(
        '.unit-toggle is a small inline-flex row (not a large standalone settings block)',
        (bool) preg_match('/display\s*:\s*inline-flex/', $wrapMatch[1])
    );
}

if (!preg_match('/\.unit-toggle-btn\.active\s*\{([^}]*)\}/s', $stylesCss, $activeMatch)) {
    $failures[] = 'Could not locate the .unit-toggle-btn.active rule block in styles.css at all';
} else {
    ett_assert_true(
        'the active unit is visually distinguished using the existing accent theme variables',
        strpos($activeMatch[1], 'var(--accent)') !== false && strpos($activeMatch[1], 'var(--text-on-accent)') !== false
    );
}

ett_assert_true(
    '.history-range-buttons is untouched by this change (still present, unmodified elsewhere in this file)',
    strpos($stylesCss, '.history-range-buttons {') !== false
);

// No horizontal-overflow-prone fixed large width on the toggle:
if (preg_match('/\.unit-toggle\s*\{([^}]*)\}/s', $stylesCss, $m2)) {
    ett_assert_true(
        '.unit-toggle sets no fixed pixel width that could overflow a narrow phone screen',
        !preg_match('/width\s*:\s*\d{3,}px/', $m2[1])
    );
}

// === Part 2: live HTTP integration test of the POST/CSRF/redirect path ==
// Uses PHP's built-in server so the real page file, real session
// handling, and real header()/exit() behavior are exercised exactly as
// a browser would trigger them - this part of the page's logic runs
// and exits before any hardware-dependent sensor-reading code, so it's
// fully deterministic regardless of what's actually installed on this
// machine.

function ett_http(string $port, string $path, array $post, ?string $cookie): array
{
    $content = http_build_query($post);
    $headers = "Content-Type: application/x-www-form-urlencoded\r\n";
    if ($cookie !== null) {
        $headers .= "Cookie: PHPSESSID=$cookie\r\n";
    }
    $context = stream_context_create(['http' => [
        'method' => 'POST',
        'header' => $headers,
        'content' => $content,
        'ignore_errors' => true,
        'timeout' => 5,
        // Inspect the immediate response to this POST, not whatever a
        // followed redirect eventually renders - that's what proves
        // the Location/empty-body redirect behavior itself, which
        // following would otherwise silently replace with the
        // redirected-to page's own 200/HTML.
        'follow_location' => 0,
    ]]);
    $body = @file_get_contents("http://127.0.0.1:$port$path", false, $context);
    $status = 0;
    if (isset($http_response_header[0]) && preg_match('/\s(\d{3})\s/', $http_response_header[0], $sm)) {
        $status = (int) $sm[1];
    }
    return ['status' => $status, 'body' => (string) $body, 'headers' => $http_response_header ?? []];
}

$sandbox = sys_get_temp_dir() . '/piratebox_env_toggle_test_' . getmypid();
$sessDir = $sandbox . '/sessions';
mkdir($sandbox, 0777, true);
mkdir($sessDir, 0777, true);
$tmpUnitFile = $sandbox . '/temp-unit.json';
$prependFile = $sandbox . '/prepend.php';
file_put_contents($prependFile, "<?php\ndefine('PIRATEBOX_TEMP_UNIT_FILE', " . var_export($tmpUnitFile, true) . ");\n");

// A known session, pre-seeded with a known CSRF token - same on-disk
// format PHP's default "php" session.serialize_handler produces.
$sessionId = 'ettestsession01';
file_put_contents($sessDir . '/sess_' . $sessionId, 'csrf_token|s:6:"abc123";');

$docRoot = realpath($repoRoot . '/var/www/html/public');
$port = 8300 + (getmypid() % 1000); // pid-derived - avoids colliding with a concurrent run of this same test
$descriptors = [1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
// Array form (no shell wrapper) - proc_terminate()/proc_close() below
// then reliably signal the actual php -S process itself, not a /bin/sh
// intermediary that might otherwise survive and keep the port bound
// for a later run.
$cmd = [PHP_BINARY, '-d', 'session.save_path=' . $sessDir, '-d', 'auto_prepend_file=' . $prependFile,
    '-S', '127.0.0.1:' . $port, '-t', $docRoot];
$proc = proc_open($cmd, $descriptors, $pipes);

if ($proc === false) {
    $failures[] = 'Could not start php -S for the live integration test';
} else {
    // Poll for the socket instead of a fixed sleep - more robust under
    // a loaded machine than guessing a fixed startup delay.
    $waited = 0;
    while ($waited < 3000000) {
        $sock = @fsockopen('127.0.0.1', $port, $errno, $errstr, 0.1);
        if ($sock) {
            fclose($sock);
            break;
        }
        usleep(100000);
        $waited += 100000;
    }

    // --- Valid session + matching CSRF token -> unit actually changes,
    // and the response is a redirect with an empty body (never falls
    // through to a full HTML re-render) --------------------------------
    $r1 = ett_http((string) $port, '/utility/environment/index.php', [
        'action' => 'set_temp_unit', 'temp_unit' => 'F', 'csrf_token' => 'abc123',
    ], $sessionId);
    ett_assert_eq('valid CSRF + matching session: HTTP 302 redirect', $r1['status'], 302);
    ett_assert_true(
        'valid CSRF + matching session: Location header points back to this page',
        (bool) array_filter($r1['headers'], fn($h) => stripos($h, 'Location:') === 0 && strpos($h, '/utility/environment/') !== false)
    );
    ett_assert_eq('valid CSRF + matching session: empty body (redirect, not a rendered page)', $r1['body'], '');
    ett_assert_eq(
        'valid CSRF + matching session: the shared preference file was actually updated to F',
        json_decode((string) @file_get_contents($tmpUnitFile), true)['unit'] ?? null,
        'F'
    );

    // --- Same session, WRONG token -> rejected with 403, and the stored
    // preference is left completely unchanged (still F from above) -----
    $r2 = ett_http((string) $port, '/utility/environment/index.php', [
        'action' => 'set_temp_unit', 'temp_unit' => 'C', 'csrf_token' => 'wrong-token',
    ], $sessionId);
    ett_assert_eq('mismatched CSRF token: HTTP 403', $r2['status'], 403);
    ett_assert_eq('mismatched CSRF token: body is the invalid-token message', trim($r2['body']), 'Invalid CSRF token.');
    ett_assert_eq(
        'mismatched CSRF token: the stored preference is untouched by the rejected write',
        json_decode((string) @file_get_contents($tmpUnitFile), true)['unit'] ?? null,
        'F'
    );

    // --- No session cookie at all (a request with no prior GET, so no
    // csrf_token has ever been minted for it) + a guessed token ->
    // fails closed, proving this is not a generic unauthenticated
    // settings-write endpoint --------------------------------------------
    $r3 = ett_http((string) $port, '/utility/environment/index.php', [
        'action' => 'set_temp_unit', 'temp_unit' => 'C', 'csrf_token' => 'abc123',
    ], 'freshsessionwithnotoken');
    ett_assert_eq('no minted CSRF token for this session: HTTP 403 (fails closed, not open)', $r3['status'], 403);
    ett_assert_eq(
        'no minted CSRF token for this session: the stored preference is untouched',
        json_decode((string) @file_get_contents($tmpUnitFile), true)['unit'] ?? null,
        'F'
    );

    // --- An unrelated action name is not accidentally handled by this
    // branch (scoped exactly to set_temp_unit, not a generic dispatcher) -
    $r4 = ett_http((string) $port, '/utility/environment/index.php', [
        'action' => 'something_else', 'temp_unit' => 'C', 'csrf_token' => 'abc123',
    ], $sessionId);
    ett_assert_true(
        'an unrecognized action falls through to the normal page render, not the write path',
        $r4['status'] !== 403 && $r4['body'] !== ''
    );
    ett_assert_eq(
        'an unrecognized action never changes the stored preference',
        json_decode((string) @file_get_contents($tmpUnitFile), true)['unit'] ?? null,
        'F'
    );

    proc_terminate($proc);
    proc_close($proc);
}

// Cleanup
foreach ([$tmpUnitFile, $prependFile, $sessDir . '/sess_' . $sessionId] as $f) {
    @unlink($f);
}
@rmdir($sessDir);
@rmdir($sandbox);

echo "\n";
if ($failures) {
    echo "FAILURES:\n";
    foreach ($failures as $f) echo "  - $f\n";
    echo "\nEnvironment temp-toggle tests: $passCount passed, " . count($failures) . " failed.\n";
    exit(1);
}
echo "Environment temp-toggle tests: $passCount passed, 0 failed.\n";
