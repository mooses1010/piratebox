<?php
declare(strict_types=1);

// Lightweight theme system (round 8).
//
// WHAT THIS IS: a small, curated set of presentation-only appearance
// variants for PirateBox's own public UI - NOT a user-accounts feature,
// NOT a way to change content or behavior, and NOT modeled on
// includes/i18n.php's server-side/cookie approach even though the two
// selectors sit next to each other in the navbar.
//
// WHY THIS IS DIFFERENT FROM i18n: a locale changes what TEXT the
// server sends (so it has to be resolved server-side, before the page
// is rendered, via piratebox_get_locale()/a cookie). A theme changes
// only which CSS custom-property values apply to that same, unchanged
// HTML - a purely client-side concern. So there is no
// piratebox_get_theme(), no theme cookie, and no server-side branch
// anywhere: the actual selection, persistence (one localStorage key),
// and application (a data-theme attribute set on <html>) all live in
// assets/scripts.js. See docs/OPERATIONAL-DECISIONS.md "Lightweight
// Theme System" for the full design and reasoning.
//
// WHAT THIS FILE IS FOR: a single source of truth for the theme id ->
// display-label mapping, so includes/navbar.php's <select> and
// assets/scripts.js's validation list can't silently drift apart from
// each other. PIRATEBOX_THEMES here must be kept in sync with the
// PIRATEBOX_THEMES array at the top of assets/scripts.js by hand (a
// plain PHP array has no clean way to hand a value to a separately-
// loaded static JS file without a build step, which this project
// deliberately doesn't have) - both lists are short and reviewed
// together in the same commit whenever a theme is added or removed.
//
// Display labels are translated via includes/i18n.php like every other
// short UI string; the underlying theme ids themselves are plain
// ASCII keys, not language-dependent.
const PIRATEBOX_THEMES = ['default', 'terminal', 'amber', 'lowlight', 'pirate'];

if (!function_exists('piratebox_render_theme_switcher')) {
    /**
     * A small <select> of theme choices. Deliberately has no "selected"
     * attribute baked in server-side - assets/scripts.js sets its
     * displayed value from localStorage on load, so this always starts
     * as a plain, theme-neutral control regardless of what the visitor
     * last chose. If JavaScript is unavailable, the select simply shows
     * its first ("PirateBox / Default") option and does nothing when
     * changed - a safe, inert fallback rather than a broken control.
     */
    function piratebox_render_theme_switcher(): string
    {
        $labels = [
            'default'  => piratebox_t('theme.default'),
            'terminal' => piratebox_t('theme.terminal'),
            'amber'    => piratebox_t('theme.amber'),
            'lowlight' => piratebox_t('theme.lowlight'),
            'pirate'   => piratebox_t('theme.pirate'),
        ];
        $options = '';
        foreach (PIRATEBOX_THEMES as $id) {
            $label = htmlspecialchars($labels[$id] ?? $id);
            $options .= '<option value="' . htmlspecialchars($id) . '">' . $label . '</option>';
        }
        $ariaLabel = htmlspecialchars(piratebox_t('theme.switcher_label'));
        return '<select id="themeSelect" class="theme-switcher" aria-label="' . $ariaLabel . '">' . $options . '</select>';
    }
}
