<?php

declare(strict_types=1);

// Reference Pack model (docs/ARCHITECTURE.md's self-awareness extended
// to content/resources, not just hardware - see that document's note on
// this being a sibling to includes/capability_state.php, not a
// competing framework: same "observed fact, never fabricated" and
// "small durable model" discipline, same UNIVERSAL/NATIONAL/REGIONAL/
// LOCAL scope language, deliberately a separate small module because
// content availability and hardware capability are different kinds of
// fact - see docs/OPERATIONAL-DECISIONS.md for the full reasoning).
//
// Static metadata (id/title/scope/source/license - things that rarely
// change) lives in data/reference-packs.json. State (installed / not
// configured / candidate) is NEVER read from that static file - it's
// computed here, live, from the actual underlying data file's real
// content, the same "don't trust a claim, check the fact" discipline
// piratebox_get_capability_state() already applies to hardware.

if (!function_exists('piratebox_reference_pack_entry_count')) {
    /**
     * How many real entries a pack's underlying data file actually has
     * right now. Deliberately per-shape, not generic reflection - most
     * data files are a plain JSON array (count = entries); Local
     * Information is a single object with several arrays inside it and
     * two universal numbers that don't count as "configured" by
     * themselves (see docs/OPERATIONAL-DECISIONS.md, Stage 6) - handled
     * explicitly rather than guessed at.
     */
    function piratebox_reference_pack_entry_count(string $packId, ?string $dataFile): ?int
    {
        if ($dataFile === null) return null;
        $path = __DIR__ . '/../data/' . $dataFile;
        $raw = @file_get_contents($path);
        if ($raw === false) return null;
        $decoded = json_decode($raw, true);
        if ($decoded === null) return null; // malformed - honestly unknown, not zero

        if ($packId === 'local-reference') {
            // Local Information's two universal numbers (911, Poison
            // Control) ship by design and don't count as "configured" -
            // see data/utility/local/info.json's own header note.
            if (!is_array($decoded)) return 0;
            $count = 0;
            if (!empty($decoded['region_label'])) $count++;
            foreach (['hospitals', 'shelters', 'amateur_repeaters', 'other_resources', 'map_references'] as $key) {
                $count += is_array($decoded[$key] ?? null) ? count($decoded[$key]) : 0;
            }
            return $count;
        }

        return is_array($decoded) ? count($decoded) : null;
    }
}

if (!function_exists('piratebox_get_reference_packs')) {
    /**
     * @return array<int, array{
     *   id: string, title: string, scope: string, url: ?string,
     *   state: string, entry_count: ?int, license: ?string, note: ?string
     * }>
     * state is one of: INSTALLED, NOT_CONFIGURED, CANDIDATE, UNKNOWN
     * (UNKNOWN only if the underlying file exists but is malformed -
     * never silently treated as zero/absent).
     */
    function piratebox_get_reference_packs(): array
    {
        $raw = @file_get_contents(__DIR__ . '/../data/reference-packs.json');
        if ($raw === false) return [];
        $meta = json_decode($raw, true);
        if (!is_array($meta)) return [];

        $packs = [];
        foreach ($meta as $pack) {
            if (!is_array($pack) || empty($pack['id'])) continue;

            if (($pack['state_override'] ?? null) === 'candidate') {
                $state = 'CANDIDATE';
                $count = null;
            } else {
                $count = piratebox_reference_pack_entry_count($pack['id'], $pack['data_file'] ?? null);
                $state = $count === null ? 'UNKNOWN' : ($count > 0 ? 'INSTALLED' : 'NOT_CONFIGURED');
            }

            $packs[] = [
                'id' => $pack['id'],
                'title' => $pack['title'] ?? $pack['id'],
                'scope' => $pack['scope'] ?? 'unknown',
                'url' => $pack['url'] ?? null,
                'state' => $state,
                'entry_count' => $count,
                'license' => $pack['license'] ?? null,
                'note' => $pack['note'] ?? null,
            ];
        }
        return $packs;
    }
}

if (!function_exists('piratebox_reference_pack_scope_order')) {
    /** Universal -> National -> Regional -> Local -> Live, per docs/ARCHITECTURE.md. */
    function piratebox_reference_pack_scope_order(): array
    {
        return ['universal', 'national', 'regional', 'local', 'live'];
    }
}
