<?php

declare(strict_types=1);

// Cross-links between subject reference pages (Radio/Maps/Field Tools/
// Emergency/etc.) and the Original-Source Document Library
// (/utility/library/) - so a visitor reading a subject can discover a
// retained authoritative document without first having to know
// /utility/library/ exists, and the Library page can link back to the
// subject pages a document is relevant to.
//
// Metadata-driven, not a hardcoded link graph: each Document Library
// catalog entry (data/utility/library/catalog.json) carries its own
// optional `related_pages` array ([{url, label}, ...]) - that single
// field drives both directions. A subject page asks "which library
// documents point at me" (piratebox_get_library_entries_for_page());
// the Library page itself just renders each entry's own
// `related_pages` array directly, no separate lookup needed.

if (!function_exists('piratebox_get_library_catalog')) {
    /**
     * @return array<int, array<string, mixed>>
     */
    function piratebox_get_library_catalog(): array
    {
        $raw = @file_get_contents(__DIR__ . '/../data/utility/library/catalog.json');
        if ($raw === false) return [];
        $decoded = json_decode($raw, true);
        return is_array($decoded) ? $decoded : [];
    }
}

if (!function_exists('piratebox_get_library_entries_for_page')) {
    /**
     * Every Document Library entry whose `related_pages` names this
     * page's own URL - a subject page calls this with its own URL
     * (matched exactly, e.g. '/utility/maps/') to render an "Original
     * Source Material" box. Never fabricates a relationship: an entry
     * with no `related_pages` field, or one that doesn't name this
     * page, is correctly excluded.
     *
     * @return array<int, array<string, mixed>>
     */
    function piratebox_get_library_entries_for_page(string $pageUrl): array
    {
        $matches = [];
        foreach (piratebox_get_library_catalog() as $doc) {
            if (!is_array($doc) || empty($doc['related_pages']) || !is_array($doc['related_pages'])) continue;
            foreach ($doc['related_pages'] as $rp) {
                if (is_array($rp) && ($rp['url'] ?? null) === $pageUrl) {
                    $matches[] = $doc;
                    break;
                }
            }
        }
        return $matches;
    }
}

if (!function_exists('piratebox_render_library_links_html')) {
    /**
     * Consistent "Original Source Material" box for a subject page -
     * every page that links to the Library renders this the same way,
     * rather than each reinventing its own markup. Returns '' (render
     * nothing) when there's nothing to show - never an empty box.
     */
    function piratebox_render_library_links_html(array $entries): string
    {
        if (empty($entries)) return '';
        $items = '';
        foreach ($entries as $doc) {
            $title = htmlspecialchars((string) ($doc['title'] ?? 'Untitled document'));
            $file = htmlspecialchars(rawurlencode((string) ($doc['file'] ?? '')));
            $size = htmlspecialchars((string) ($doc['file_size'] ?? ''));
            $source = htmlspecialchars((string) ($doc['source'] ?? ''));
            $desc = htmlspecialchars((string) ($doc['description'] ?? ''));
            $items .= '<li><a href="/utility/library/files/' . $file . '" target="_blank" rel="noopener">' . $title . '</a>'
                . ($size !== '' ? ' (' . $size . ')' : '')
                . ($source !== '' ? ' - ' . $source : '')
                . ($desc !== '' ? '<br><span class="muted">' . $desc . '</span>' : '')
                . '</li>';
        }
        return '<div class="help-note library-crosslink">'
            . '<p><strong>Original source material available offline:</strong></p>'
            . '<ul>' . $items . '</ul>'
            . '<p class="muted">Full documents, retained locally with provenance - see <a href="/utility/library/">Document Library</a> for the complete catalog.</p>'
            . '</div>';
    }
}
