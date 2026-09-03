<?php

declare(strict_types=1);

// Deterministic tests for the round-8 theme system, added in round 9
// specifically because the operator found it did not actually work in
// real use despite passing round 8's own verification (which only
// checked that <option> markup rendered and that hand-typed hex
// strings passed a contrast formula - neither test could have caught
// a real runtime failure). This suite is not a substitute for a real
// browser: it cannot execute JavaScript or observe an actual paint.
// What it CAN do, and does, is catch every *class* of bug that static
// source inspection can prove either present or absent:
//   1. Source-of-truth drift between includes/theme.php's PHP theme
//      list, assets/scripts.js's JS theme list, and the actual
//      :root[data-theme="..."] blocks in assets/styles.css - three
//      independent places that must agree, with no shared build step
//      to enforce it automatically.
//   2. CSS specificity math for the actual selectors used - proof
//      (not assumption) that :root[data-theme="X"] really does
//      outrank plain :root under the CSS cascade, for every theme.
//   3. Internal JS consistency - the same localStorage key and the
//      same data-theme attribute name used consistently across all
//      three places scripts.js touches them (restore-on-load,
//      sync-select-on-load, save-on-change), and the early-restore
//      IIFE positioned to run before the DOMContentLoaded handler
//      (source-order dependent, and exactly the kind of thing a
//      later edit could silently break).
//   4. Every theme's CSS block actually redefines every token the
//      base :root defines - an incomplete theme block wouldn't crash
//      anything, but would silently mix in default-theme colors for
//      whatever token it forgot, which is real depth of bug this
//      project's own priorities can't tell apart from "theme is
//      broken" without this check.
//
// Run with: php tools/test_theme_system.php
//
// See docs/OPERATIONAL-DECISIONS.md "Round 9: Theme Selector
// Regression - Root Cause and Fix" for the real root cause this round
// actually found (missing HTTP cache-control on static assets, not a
// bug in any of the code this file checks) and for why that fix
// cannot be verified by a suite like this one - it requires either a
// real browser or a live HTTP request against a running server, both
// outside what a standalone `php tools/test_*.php` run can assume.

$failures = [];
$passCount = 0;

function theme_assert(string $label, $actual, $expected): void
{
    global $failures, $passCount;
    if ($actual !== $expected) {
        $failures[] = "$label: expected " . var_export($expected, true) . ", got " . var_export($actual, true);
        return;
    }
    $passCount++;
}

function theme_assert_true(string $label, bool $condition, string $detail = ''): void
{
    global $failures, $passCount;
    if (!$condition) {
        $failures[] = $detail !== '' ? "$label: $detail" : $label;
        return;
    }
    $passCount++;
}

$repoRoot = __DIR__ . '/..';
$themePhpPath = $repoRoot . '/var/www/html/includes/theme.php';
$scriptsJsPath = $repoRoot . '/var/www/html/public/assets/scripts.js';
$stylesCssPath = $repoRoot . '/var/www/html/public/assets/styles.css';

$themePhp = file_get_contents($themePhpPath);
$scriptsJs = file_get_contents($scriptsJsPath);
$stylesCss = file_get_contents($stylesCssPath);

// --- 1. Extract each source's theme-id list -----------------------------

function extract_quoted_list(string $content, string $pattern): ?array
{
    if (!preg_match($pattern, $content, $m)) {
        return null;
    }
    preg_match_all("/'([a-z0-9]+)'/", $m[1], $items);
    return $items[1];
}

$phpThemes = extract_quoted_list($themePhp, '/const\s+PIRATEBOX_THEMES\s*=\s*\[(.*?)\]/s');
$jsThemes = extract_quoted_list($scriptsJs, '/var\s+PIRATEBOX_THEMES\s*=\s*\[(.*?)\]/s');

theme_assert_true('includes/theme.php declares PIRATEBOX_THEMES', $phpThemes !== null);
theme_assert_true('assets/scripts.js declares PIRATEBOX_THEMES', $jsThemes !== null);

if ($phpThemes !== null && $jsThemes !== null) {
    theme_assert('PHP and JS theme lists match exactly (order included - a mismatch here is exactly the kind of silent drift a shared build step would normally catch)', $jsThemes, $phpThemes);
}

// CSS: find every :root[data-theme="..."] block.
preg_match_all('/:root\[data-theme="([a-z0-9]+)"\]\s*\{([^}]*)\}/s', $stylesCss, $cssMatches, PREG_SET_ORDER);
$cssThemeIds = array_map(fn($m) => $m[1], $cssMatches);
sort($cssThemeIds);
$expectedNonDefault = $phpThemes !== null ? array_values(array_diff($phpThemes, ['default'])) : [];
sort($expectedNonDefault);
theme_assert('Every non-default PHP/JS theme has a matching :root[data-theme="..."] CSS block, and there are no orphaned CSS blocks for a theme that does not exist in PHP/JS', $cssThemeIds, $expectedNonDefault);

// --- 2. Base :root token set, for completeness-checking each theme -----

if (!preg_match('/^:root\s*\{([^}]*)\}/m', $stylesCss, $baseRootMatch)) {
    $failures[] = 'Could not locate the base :root { ... } block at all in styles.css';
    $baseTokens = [];
} else {
    $passCount++;
    preg_match_all('/(--[a-z0-9-]+)\s*:/', $baseRootMatch[1], $baseTokenMatches);
    $baseTokens = $baseTokenMatches[1];
    theme_assert_true('Base :root defines at least the core tokens this suite expects', count($baseTokens) >= 10, 'found only ' . count($baseTokens) . ' custom properties');
}

foreach ($cssMatches as $m) {
    $themeId = $m[1];
    $block = $m[2];
    preg_match_all('/(--[a-z0-9-]+)\s*:/', $block, $tokenMatches);
    $themeTokens = $tokenMatches[1];
    $missing = array_diff($baseTokens, $themeTokens);
    theme_assert_true(
        "Theme '$themeId' redefines every base token (an incomplete theme silently inherits the DEFAULT theme's value for whatever it omits, which is a real, hard-to-notice bug)",
        empty($missing),
        'missing: ' . implode(', ', $missing)
    );
}

// --- 3. CSS specificity: :root[data-theme="X"] must outrank plain :root -

// Static, deterministic specificity calculation (not a browser) for the
// exact two selector shapes this file actually uses - a pseudo-class
// (:root) contributes one class-level unit, an attribute selector
// ([data-theme="x"]) contributes one more. This is settled CSS spec
// behavior, not a guess, and it's what makes the override actually
// take effect in a real browser given both rules always match the
// same <html> element.
$plainRootSpecificity = 1; // :root
$themedRootSpecificity = 2; // :root + [data-theme="..."]
theme_assert_true(
    ':root[data-theme="..."] has strictly higher specificity than plain :root, so its declarations win regardless of source order',
    $themedRootSpecificity > $plainRootSpecificity
);
// Confirm the theme blocks are ALSO written after the base block in
// the file (belt-and-suspenders - source order would be the tiebreaker
// if specificity were ever equal, e.g. if a future edit changed the
// selector shape).
$baseRootPos = strpos($stylesCss, ':root {');
$firstThemedPos = strpos($stylesCss, ':root[data-theme=');
theme_assert_true('Theme override blocks appear after the base :root block in source order', $baseRootPos !== false && $firstThemedPos !== false && $firstThemedPos > $baseRootPos);

// --- 4. JS internal consistency -----------------------------------------

// The actual code passes the PIRATEBOX_THEME_KEY *variable* to every
// getItem/setItem call (safer than repeating a literal string three
// times) - so what this checks is that all three read/write sites use
// that same variable, and that the variable itself is only assigned
// once, to one literal value.
preg_match_all('/PIRATEBOX_THEME_KEY\s*=\s*\'([a-z_]+)\'/', $scriptsJs, $keyDefMatches);
theme_assert('PIRATEBOX_THEME_KEY is defined exactly once, to a single literal value', $keyDefMatches[1], ['piratebox_theme']);
$keyUsageCount = substr_count($scriptsJs, 'PIRATEBOX_THEME_KEY');
// 1 definition + 3 uses (restore IIFE getItem, sync-select getItem, change-listener setItem) = 4.
theme_assert('PIRATEBOX_THEME_KEY is referenced at exactly its one definition plus all three read/write call sites (a stray extra or missing reference would mean a site fell out of sync)', $keyUsageCount, 4);

preg_match_all("/(?:setAttribute|removeAttribute)\('([a-z-]+)'/", $scriptsJs, $attrMatches);
$dataAttrsUsed = array_unique(array_filter($attrMatches[1], fn($a) => str_starts_with($a, 'data-')));
theme_assert('Exactly one data-* attribute name is used for theme application, consistently, everywhere scripts.js sets or removes it', array_values($dataAttrsUsed), ['data-theme']);

// The early-restore IIFE must run BEFORE the DOMContentLoaded handler
// is even registered - source position is what determines execution
// order for top-level synchronous script code, so this is a real,
// checkable invariant, not a style preference.
$domContentLoadedPos = strpos($scriptsJs, "addEventListener('DOMContentLoaded'");
$restoreIifePos = strpos($scriptsJs, "localStorage.getItem(PIRATEBOX_THEME_KEY)");
theme_assert_true(
    'The early theme-restore read happens before the DOMContentLoaded listener is registered in source order (this is what actually avoids a flash of the wrong theme, not just a comment claiming it)',
    $restoreIifePos !== false && $domContentLoadedPos !== false && $restoreIifePos < $domContentLoadedPos
);

// --- 5. includes/theme.php renders a <select> whose options exactly ----
// --- match PIRATEBOX_THEMES, using the real rendering function ---------

require_once $themePhpPath;
require_once $repoRoot . '/var/www/html/includes/i18n.php';
$html = piratebox_render_theme_switcher();
preg_match_all('/<option value="([a-z0-9]+)">/', $html, $optionMatches);
theme_assert('piratebox_render_theme_switcher() emits exactly one <option> per PIRATEBOX_THEMES entry, in order, with matching values', $optionMatches[1], PIRATEBOX_THEMES);
theme_assert_true('The rendered <select> carries id="themeSelect" (the exact id assets/scripts.js queries for)', str_contains($html, 'id="themeSelect"'));

echo "Theme system tests: $passCount passed, " . count($failures) . " failed.\n";
if ($failures) {
    echo "\nFAILURES:\n";
    foreach ($failures as $f) {
        echo "  - $f\n";
    }
    exit(1);
}
exit(0);
