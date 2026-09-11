<?php

declare(strict_types=1);

// Focused regression test for the landing-page "two sides" tile grid
// (2026-09-08 fix) - matches this project's existing lightweight
// plain-text tools/test_*.php convention for CSS (see
// tools/test_theme_system.php's own header for the same style).
//
// THE BUG: .landing-mini-grid used `grid-template-columns:
// repeat(auto-fit, minmax(120px, 1fr))` - auto-fit picks a column
// count purely from the container's current width, with no awareness
// that this grid always holds exactly 4 tiles. At typical laptop
// widths, three 120px tracks fit but not four, producing an
// unbalanced 3-tiles-then-1 wrap instead of a 2x2 grid.
//
// THE FIX: a fixed `repeat(2, 1fr)` - correct at every width this
// grid actually renders at, since it always holds exactly 4 items
// meant to read as two rows of two.
//
// SECOND BUG, same section (2026-09-11 fix): with the 2x2 fix above
// in place, the two tile grids themselves no longer wrapped oddly,
// but on desktop (side-by-side) they didn't START at the same
// vertical position either - CONNECT & SHARE's description is one
// short sentence while EXPLORE & REFERENCE's wraps to more lines, so
// the shorter side's tile grid began higher, with the leftover
// stretched card height landing as blank space below its grid instead
// of above it.
//
// THE FIX: .landing-side became a column flexbox and its <p> got
// `flex: 1 0 auto` - the paragraph itself absorbs whatever extra
// height CSS Grid's default align-items:stretch gives the shorter
// card, so both tile grids land at the same Y regardless of how many
// lines either description happens to wrap to (never a fixed
// pixel/line-count assumption, and never JS-measured). See
// .landing-side's own CSS comment for the full mechanism.
//
// Run with: php tools/test_landing_layout.php

$failures = [];
$passCount = 0;

function ll_assert_true(string $label, bool $condition, string $detail = ''): void
{
    global $failures, $passCount;
    if (!$condition) {
        $failures[] = $label . ($detail !== '' ? " ($detail)" : '');
        return;
    }
    $passCount++;
}

$repoRoot = __DIR__ . '/..';
$stylesCss = file_get_contents($repoRoot . '/var/www/html/public/assets/styles.css');
$indexPhp = file_get_contents($repoRoot . '/var/www/html/public/index.php');

// --- The actual regression guard: .landing-mini-grid is a fixed 2-column
// grid, not an auto-fit one that can silently drift back to 3+1 -------

if (!preg_match('/\.landing-mini-grid\s*\{([^}]*)\}/s', $stylesCss, $miniGridMatch)) {
    $failures[] = 'Could not locate the .landing-mini-grid rule block in styles.css at all';
} else {
    // Strip /* ... */ comments before checking - this rule's own
    // explanatory comment mentions "auto-fit" by name (documenting
    // what NOT to do), which would otherwise false-positive the
    // no-more-auto-fit check below.
    $miniGridBody = $miniGridMatch[1];
    $miniGridCode = preg_replace('#/\*.*?\*/#s', '', $miniGridBody);
    ll_assert_true(
        '.landing-mini-grid sets a fixed 2-column grid-template-columns',
        (bool) preg_match('/grid-template-columns\s*:\s*repeat\(\s*2\s*,\s*1fr\s*\)/', $miniGridCode),
        'expected repeat(2, 1fr), got: ' . trim($miniGridCode)
    );
    ll_assert_true(
        '.landing-mini-grid no longer uses auto-fit in its actual CSS (comments aside)',
        strpos($miniGridCode, 'auto-fit') === false
    );
}

// --- The outer two-section layout must be untouched - this bug was
// scoped to the INNER tile grid only, never the CONNECT&SHARE /
// EXPLORE&REFERENCE side-by-side layout itself ------------------------

if (!preg_match('/\.landing-sides-grid\s*\{([^}]*)\}/s', $stylesCss, $outerGridMatch)) {
    $failures[] = 'Could not locate the .landing-sides-grid rule block in styles.css at all';
} else {
    ll_assert_true(
        '.landing-sides-grid still uses its existing auto-fit/minmax(300px) two-column layout (unchanged)',
        (bool) preg_match('/grid-template-columns\s*:\s*repeat\(\s*auto-fit\s*,\s*minmax\(\s*300px\s*,\s*1fr\s*\)\s*\)/', $outerGridMatch[1]),
        'the outer section layout must not have been altered by this fix'
    );
}

// --- Structural check on the markup: each "side" really does have
// exactly 4 tiles today - if this ever changes, the fixed 2-column
// grid stops being the right shape and this test should be revisited
// rather than silently keep asserting a now-wrong invariant ------------

if (preg_match_all('/<div class="utility-grid landing-mini-grid">(.*?)<\/div>\s*<\/div>/s', $indexPhp, $sideMatches)) {
    ll_assert_true('exactly two .landing-mini-grid tile groups exist on the homepage', count($sideMatches[0]) === 2, (string) count($sideMatches[0]));
    foreach ($sideMatches[1] as $i => $body) {
        $tileCount = substr_count($body, 'class="utility-card"');
        ll_assert_true("landing-mini-grid #" . ($i + 1) . " has exactly 4 tiles (matches the fixed 2x2 grid)", $tileCount === 4, "found $tileCount");
    }
} else {
    $failures[] = 'Could not locate any .landing-mini-grid tile groups in index.php at all';
}

// --- Long titles must still wrap naturally (never truncated/clipped) -

ll_assert_true(
    '.utility-card-title has no white-space:nowrap / text-overflow that would break a long title like "Offline Reference Library"',
    !preg_match('/\.utility-card-title\s*\{[^}]*(white-space\s*:\s*nowrap|text-overflow)/s', $stylesCss)
);

// --- 2026-09-11: the two tile grids must start at the same vertical
// position on desktop, via a structural mechanism - never a fixed
// pixel offset, a hardcoded height, or a JS height-measurement hack
// that would only coincidentally work while the two descriptions
// happen to wrap to a similar number of lines --------------------------

ll_assert_true(
    '.landing-sides-grid is still a real CSS Grid (its default align-items:stretch is what makes the two cards equal height at all)',
    (bool) (preg_match('/\.landing-sides-grid\s*\{([^}]*)\}/s', $stylesCss, $m) && preg_match('/display\s*:\s*grid/', $m[1]))
);

if (!preg_match('/\.landing-side\s*\{([^}]*)\}/s', $stylesCss, $sideMatch)) {
    $failures[] = 'Could not locate the .landing-side rule block in styles.css at all';
} else {
    $sideCode = preg_replace('#/\*.*?\*/#s', '', $sideMatch[1]);
    ll_assert_true(
        '.landing-side is a column flexbox (the alignment mechanism, not a one-off pixel offset)',
        (bool) (strpos($sideCode, 'display: flex') !== false && strpos($sideCode, 'flex-direction: column') !== false),
        'expected display:flex + flex-direction:column, got: ' . trim($sideCode)
    );
    ll_assert_true(
        '.landing-side sets no fixed/hardcoded height that would only coincidentally match the taller side',
        !preg_match('/(?<!min-)(?<!max-)height\s*:\s*\d/', $sideCode)
    );
}

if (!preg_match('/\.landing-side\s+p\s*\{([^}]*)\}/s', $stylesCss, $pMatch)) {
    $failures[] = 'Could not locate the .landing-side p rule block in styles.css at all';
} else {
    ll_assert_true(
        '.landing-side p grows to absorb the stretched extra height (flex-grow >= 1), which is what pushes a shorter description\'s tile grid down to match, structurally rather than by assumption',
        (bool) preg_match('/flex\s*:\s*[1-9]/', $pMatch[1]),
        'expected a flex shorthand with a nonzero grow factor, got: ' . trim($pMatch[1])
    );
}

// The grid itself no longer carries a fixed top margin - that spacing
// responsibility moved to .landing-side p's own margin, which is what
// makes it participate in the flex-grow calculation above.
if (preg_match('/\.landing-mini-grid\s*\{([^}]*)\}/s', $stylesCss, $miniGridMatch2)) {
    $miniGridCode2 = preg_replace('#/\*.*?\*/#s', '', $miniGridMatch2[1]);
    ll_assert_true(
        '.landing-mini-grid no longer sets its own top margin (spacing before it is owned by the flexible paragraph, not a fixed offset on the grid)',
        !preg_match('/margin\s*:\s*[^;]*\d(px|rem|em)\s+0\s+0\s+0/', $miniGridCode2) && !preg_match('/margin-top\s*:\s*[1-9]/', $miniGridCode2)
    );
}

// No JS-based height-measurement/equalization hack was introduced as
// an alternative (or supplement) to the CSS mechanism above - keep
// this a pure-CSS, no-layout-thrash fix.
ll_assert_true(
    'no JS height-equalization hack for .landing-side/.landing-mini-grid exists in scripts.js',
    !preg_match('/landing-side|landing-mini-grid/', (string) @file_get_contents($repoRoot . '/var/www/html/public/assets/scripts.js'))
);
ll_assert_true(
    'no inline <script> on the homepage measures/equalizes .landing-side heights',
    !preg_match('/<script\b[^>]*>(?:(?!<\/script>).)*landing-side(?:(?!<\/script>).)*<\/script>/s', $indexPhp)
);

echo "\n";
if ($failures) {
    echo "FAILURES:\n";
    foreach ($failures as $f) echo "  - $f\n";
    echo "\nLanding layout tests: $passCount passed, " . count($failures) . " failed.\n";
    exit(1);
}
echo "Landing layout tests: $passCount passed, 0 failed.\n";
