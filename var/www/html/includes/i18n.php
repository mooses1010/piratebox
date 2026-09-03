<?php
declare(strict_types=1);

// Lightweight multilingual foundation (2026-09-03).
//
// WHAT THIS IS: a small, incremental translation layer for PirateBox's
// OWN short, authoritative-tone UI strings (nav labels, the trust
// statement, connect steps) - NOT a general translation system, and
// explicitly NOT a way to translate the Reference Library's retained
// source documents (those stay in their original, authoritative
// language - see docs/OPERATIONAL-DECISIONS.md "Lightweight
// Multilingual Foundation" for the full reasoning) or user-generated
// Chat/Bulletin/Logbook content (never silently machine-translated).
//
// ARCHITECTURE:
//   - One canonical site (this file's whole point) - no per-language
//     site copies, no duplicated page templates. A page that wants a
//     translated string calls piratebox_t('some.key') instead of
//     writing the English text inline; everything else about the page
//     (structure, deterministic tool logic, retained documents) is
//     unchanged regardless of locale.
//   - Dictionaries live in data/i18n/<locale>.json - flat key => string
//     maps. Adding a language is: add one new JSON file with as many
//     or as few keys as exist yet, no PHP change required. A missing
//     key in a non-English dictionary silently falls back to English
//     (see piratebox_t() below) - a partial translation degrades
//     gracefully to English for the untranslated parts, it never
//     shows a raw key or breaks the page.
//   - No external translation API, no runtime network dependency -
//     both dictionaries are static, checked-in JSON files read once
//     per request, same trust boundary as any other data/*.json file
//     this project already reads.
//
// LOCALE SELECTION (manual choice always wins; see piratebox_get_
// locale() below for the exact precedence):
//   1. An explicit ?lang= query parameter (only present on the one
//      request where the user actually clicked a language link) sets
//      a plain preference cookie and is used immediately.
//   2. That cookie, on every later request, is honored ahead of
//      anything automatic.
//   3. With no cookie yet (a visitor's first request), the browser's
//      own Accept-Language header may select a supported language -
//      convenience, not tracking: nothing is written to any log or
//      data store here, no request outside this device is made, and
//      the *result* still becomes an explicit cookie so it behaves
//      identically to a manual choice from then on (including being
//      just as easy to override).
//   4. English otherwise.
// The cookie (PIRATEBOX_LANG_COOKIE below) carries only a two-letter
// locale code - not a session ID, not linked to any account or
// request history, set with no expiry tied to identity (a plain
// 1-year preference, the same category of cookie as a font-size or
// theme choice). It requires no consent banner under this project's
// own privacy model for the same reason the existing PHPSESSID/CSRF
// session cookie doesn't: it identifies a UI preference, not a person
// or a session of activity.

const PIRATEBOX_I18N_DEFAULT_LOCALE = 'en';
const PIRATEBOX_I18N_SUPPORTED_LOCALES = ['en', 'es'];
const PIRATEBOX_LANG_COOKIE = 'piratebox_lang';

if (!function_exists('piratebox_get_locale')) {
    function piratebox_get_locale(): string
    {
        // 1. Explicit choice this request (a language-selector click) -
        // also persists it, so every later request behaves the same
        // way without needing the query parameter again.
        $requested = $_GET['lang'] ?? null;
        if (is_string($requested) && in_array($requested, PIRATEBOX_I18N_SUPPORTED_LOCALES, true)) {
            if (!headers_sent()) {
                setcookie(PIRATEBOX_LANG_COOKIE, $requested, [
                    'expires' => time() + 31536000, // ~1 year, a preference, not a session
                    'path' => '/',
                    'samesite' => 'Lax',
                ]);
            }
            return $requested;
        }

        // 2. A previously-set preference (manual or auto-detected) -
        // always wins over Accept-Language from here on, matching
        // "manual choice always overrides automatic selection."
        $cookieLocale = $_COOKIE[PIRATEBOX_LANG_COOKIE] ?? null;
        if (is_string($cookieLocale) && in_array($cookieLocale, PIRATEBOX_I18N_SUPPORTED_LOCALES, true)) {
            return $cookieLocale;
        }

        // 3. First visit, no preference recorded yet - the browser's
        // own Accept-Language header, parsed locally, no external
        // request. Simple prefix match (e.g. "es-MX" selects "es") is
        // sufficient for the two locales this project supports today.
        $acceptLanguage = $_SERVER['HTTP_ACCEPT_LANGUAGE'] ?? '';
        if (is_string($acceptLanguage) && $acceptLanguage !== '') {
            foreach (explode(',', $acceptLanguage) as $part) {
                $tag = strtolower(trim(explode(';', $part)[0] ?? ''));
                $primary = explode('-', $tag)[0] ?? '';
                if (in_array($primary, PIRATEBOX_I18N_SUPPORTED_LOCALES, true)) {
                    // Make the auto-detected result "sticky" the same
                    // way an explicit choice would be, so a returning
                    // visitor's experience doesn't depend on whether
                    // their browser resends the same header.
                    if (!headers_sent()) {
                        setcookie(PIRATEBOX_LANG_COOKIE, $primary, [
                            'expires' => time() + 31536000,
                            'path' => '/',
                            'samesite' => 'Lax',
                        ]);
                    }
                    return $primary;
                }
            }
        }

        // 4. Default.
        return PIRATEBOX_I18N_DEFAULT_LOCALE;
    }
}

if (!function_exists('piratebox_load_i18n_dictionary')) {
    /** One dictionary, loaded once per request per locale (static cache -
     * this file is required by many pages per request tree in some
     * layouts, and the JSON is tiny, but there's no reason to parse it
     * twice). Missing/malformed file degrades to an empty dictionary,
     * never a fatal error - every lookup still falls back to English
     * (or the key itself) per piratebox_t() below. */
    function piratebox_load_i18n_dictionary(string $locale): array
    {
        static $cache = [];
        if (isset($cache[$locale])) {
            return $cache[$locale];
        }
        $path = __DIR__ . '/../data/i18n/' . basename($locale) . '.json';
        $raw = @file_get_contents($path);
        $decoded = $raw !== false ? json_decode($raw, true) : null;
        $cache[$locale] = is_array($decoded) ? $decoded : [];
        return $cache[$locale];
    }
}

if (!function_exists('piratebox_t')) {
    /**
     * Look up one short UI string by key. Falls back to the English
     * dictionary if the current locale is missing that key (a partial
     * translation is never a broken page), and falls back to the key
     * itself if even English is missing it (a code bug - visible and
     * greppable in that case, not a silent blank).
     *
     * Deliberately NOT used for retained source documents' own content,
     * user-generated Chat/Bulletin/Logbook text, or deterministic
     * tools' calculation logic - see this file's own header.
     */
    function piratebox_t(string $key): string
    {
        $locale = piratebox_get_locale();
        $dict = piratebox_load_i18n_dictionary($locale);
        if (isset($dict[$key]) && is_string($dict[$key])) {
            return $dict[$key];
        }
        if ($locale !== PIRATEBOX_I18N_DEFAULT_LOCALE) {
            $en = piratebox_load_i18n_dictionary(PIRATEBOX_I18N_DEFAULT_LOCALE);
            if (isset($en[$key]) && is_string($en[$key])) {
                return $en[$key];
            }
        }
        return $key;
    }
}

if (!function_exists('piratebox_render_language_switcher')) {
    /**
     * A small, always-visible "EN / ES" switcher - both options shown
     * at all times (not hidden behind a menu keyed to the current
     * locale) so returning to English is always one obvious click,
     * per instruction. Plain links with ?lang=xx, no JavaScript
     * required; piratebox_get_locale() above does the actual cookie
     * write when one is followed.
     */
    function piratebox_render_language_switcher(): string
    {
        $current = piratebox_get_locale();
        $labels = ['en' => 'EN', 'es' => 'ES'];
        $parts = [];
        foreach (PIRATEBOX_I18N_SUPPORTED_LOCALES as $loc) {
            $label = htmlspecialchars($labels[$loc] ?? strtoupper($loc));
            if ($loc === $current) {
                $parts[] = '<span class="lang-current" aria-current="true">' . $label . '</span>';
            } else {
                $qs = htmlspecialchars($_SERVER['REQUEST_URI'] ?? '/');
                $sep = str_contains($qs, '?') ? '&' : '?';
                $parts[] = '<a href="' . $qs . $sep . 'lang=' . htmlspecialchars($loc) . '">' . $label . '</a>';
            }
        }
        return '<span class="lang-switcher" role="group" aria-label="Language / Idioma">'
            . '&#127760; ' . implode(' / ', $parts) . '</span>';
    }
}
