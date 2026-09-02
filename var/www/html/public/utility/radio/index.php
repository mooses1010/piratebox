<?php
declare(strict_types=1);
session_start();

// Radio Reference (Stage 2). Deliberately does NOT read piratebox_get_mode()
// or includes/mode.php - this page's content is identical in Normal and
// Emergency Mode by design (see docs/OPERATIONAL-DECISIONS.md). Only the
// shared navbar/banner, rendered via includes/navbar.php below, are
// mode-aware.

$DATA_DIR = __DIR__ . '/../../../data/utility/radio';

function radio_load_json(string $path): array
{
    $raw = @file_get_contents($path);
    if ($raw === false) {
        return [];
    }
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

$services = radio_load_json($DATA_DIR . '/services.json');
$modulation = radio_load_json($DATA_DIR . '/modulation.json');
$guides = radio_load_json($DATA_DIR . '/guides.json');
$sigid = radio_load_json($DATA_DIR . '/signal-identification.json');
require_once __DIR__ . '/../../../includes/library_links.php';
$sources = radio_load_json($DATA_DIR . '/sources.json');

// Group services into display sections. Keys are the "group" used for the
// filter chips; a service's `category` (from services.json) maps into one
// of these via $categoryToGroup.
$groupLabels = [
    'amateur'        => 'Amateur Radio Bands',
    'noaa-wx'        => 'NOAA Weather Radio & Emergency Monitoring',
    'broadcast'      => 'Broadcast Radio (AM / FM / Shortwave)',
    'personal-radio' => 'CB / FRS / GMRS / MURS',
    'marine-vhf'     => 'Marine VHF',
    'airband'        => 'Aviation / Airband',
    'railroad'       => 'Railroad',
];
$categoryToGroup = [
    'amateur'             => 'amateur',
    'noaa-wx'             => 'noaa-wx',
    'broadcast-am'        => 'broadcast',
    'broadcast-fm'        => 'broadcast',
    'broadcast-shortwave' => 'broadcast',
    'cb'                  => 'personal-radio',
    'frs'                 => 'personal-radio',
    'gmrs'                => 'personal-radio',
    'murs'                => 'personal-radio',
    'marine-vhf'          => 'marine-vhf',
    'airband'             => 'airband',
    'railroad'            => 'railroad',
];

$groups = [];
foreach ($groupLabels as $key => $label) {
    $groups[$key] = [];
}
foreach ($services as $svc) {
    $group = $categoryToGroup[$svc['category']] ?? null;
    if ($group !== null) {
        $groups[$group][] = $svc;
    }
}

function radio_search_blob(array $fields): string
{
    $parts = [];
    foreach ($fields as $f) {
        if (is_array($f)) {
            $parts[] = implode(' ', $f);
        } elseif ($f !== null) {
            $parts[] = (string) $f;
        }
    }
    return htmlspecialchars(strtolower(implode(' ', $parts)));
}

function radio_source_line(array $sources, ?string $sourceId, ?string $secondaryId, ?string $confidence, ?string $note): string
{
    $bits = [];
    if ($sourceId !== null && isset($sources[$sourceId])) {
        $s = $sources[$sourceId];
        $name = htmlspecialchars($s['name']);
        if (!empty($s['url'])) {
            $bits[] = '<a href="' . htmlspecialchars($s['url']) . '" target="_blank" rel="noopener">' . $name . '</a>';
        } else {
            $bits[] = $name;
        }
        if (!empty($s['retrieved'])) {
            $bits[0] .= ' (retrieved ' . htmlspecialchars($s['retrieved']) . ')';
        }
    }
    if ($secondaryId !== null && isset($sources[$secondaryId])) {
        $s2 = $sources[$secondaryId];
        $bits[] = 'plus ' . htmlspecialchars($s2['name']);
    }
    $out = 'Source: ' . implode('; ', $bits ?: ['unspecified']);
    if ($confidence !== null) {
        $out .= ' &mdash; confidence: <span class="radio-confidence confidence-' . htmlspecialchars($confidence) . '">' . htmlspecialchars($confidence) . '</span>';
    }
    if (!empty($note)) {
        $out .= '<br>' . htmlspecialchars($note);
    }
    return $out;
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Radio Reference</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Radio Reference</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>A fast, offline lookup for a wideband receiver (built with a Malahit DSP2-style receiver in mind). Search or filter below - everything on this page works with no Internet connection. <strong>This is receive-focused.</strong> Owning a receiver does not authorize transmitting anywhere on this page; each entry marks whether transmitting requires a license.</p>

        <div class="radio-spectrum-wrap">
            <?php require __DIR__ . '/spectrum.svg.php'; ?>
        </div>
        <p class="radio-spectrum-caption">Log-scale visual reference (0.5 MHz&ndash;3 GHz) - approximate positions for quick orientation, not precise band-edge measurement.</p>

        <div class="radio-search-bar">
            <input type="text" id="radioSearch" placeholder="Search: NOAA, 2 meter, 40m, airband, GMRS, FRS, marine, CB, shortwave..." aria-label="Search radio reference">
            <div class="radio-chip-row" id="radioChips" role="group" aria-label="Filter by category">
                <button type="button" class="radio-chip active" data-group="all">All</button>
                <?php foreach ($groupLabels as $key => $label): ?>
                    <button type="button" class="radio-chip" data-group="<?= htmlspecialchars($key) ?>"><?= htmlspecialchars($label) ?></button>
                <?php endforeach; ?>
                <button type="button" class="radio-chip" data-group="modulation">Modulation</button>
                <button type="button" class="radio-chip" data-group="sigid">Signal Identification</button>
                <button type="button" class="radio-chip" data-group="guides">Guides</button>
            </div>
        </div>

        <p class="radio-no-results" id="radioNoResults" hidden>No matches. Try a different search term or choose "All".</p>

        <div id="radioResults">
            <?php foreach ($groupLabels as $groupKey => $groupLabel): ?>
                <?php if (empty($groups[$groupKey])) continue; ?>
                <section class="radio-group" data-group-section="<?= htmlspecialchars($groupKey) ?>">
                    <h2 class="radio-group-heading"><?= htmlspecialchars($groupLabel) ?></h2>
                    <?php foreach ($groups[$groupKey] as $svc): ?>
                        <?php
                        $search = radio_search_blob([$svc['name'], $svc['freq_range'], $svc['keywords'] ?? [], $svc['category']]);
                        $txLicensed = !empty($svc['license_required_to_transmit']);
                        ?>
                        <details class="radio-entry" id="<?= htmlspecialchars($svc['id']) ?>" data-group="<?= htmlspecialchars($groupKey) ?>" data-search="<?= $search ?>">
                            <summary>
                                <span class="radio-entry-name"><?= htmlspecialchars($svc['name']) ?></span>
                                <span class="radio-entry-freq"><?= htmlspecialchars($svc['freq_range']) ?></span>
                                <span class="radio-entry-mode-badge"><?= htmlspecialchars($svc['typical_receiver_mode'] ?? implode('/', $svc['common_modes'] ?? [])) ?></span>
                                <span class="radio-tx-badge <?= $txLicensed ? 'tx-licensed' : 'tx-open' ?>">
                                    <?= $txLicensed ? 'License required to transmit' : 'No license required to transmit' ?>
                                </span>
                            </summary>
                            <div class="radio-entry-detail">
                                <?php if (!empty($svc['practical_note'])): ?>
                                    <p><?= htmlspecialchars($svc['practical_note']) ?></p>
                                <?php endif; ?>
                                <?php if (!empty($svc['transmit_note'])): ?>
                                    <p class="radio-entry-tx-note"><strong>Transmit/License:</strong> <?= htmlspecialchars($svc['transmit_note']) ?></p>
                                <?php endif; ?>

                                <?php if (!empty($svc['channels'])): ?>
                                    <div class="table-wrapper">
                                        <table class="radio-channel-table">
                                            <?php
                                            // Union of keys across every row, not just the first - some rows
                                            // (e.g. CB channel 23) carry an extra optional field like "note"
                                            // that others don't, and it must still get its own column.
                                            $cols = [];
                                            foreach ($svc['channels'] as $row) {
                                                foreach (array_keys($row) as $k) {
                                                    if (!in_array($k, $cols, true)) $cols[] = $k;
                                                }
                                            }
                                            ?>
                                            <thead>
                                                <tr><?php foreach ($cols as $c): ?><th><?= htmlspecialchars(ucfirst(str_replace('_', ' ', $c))) ?></th><?php endforeach; ?></tr>
                                            </thead>
                                            <tbody>
                                                <?php foreach ($svc['channels'] as $row): ?>
                                                    <tr>
                                                        <?php foreach ($cols as $c): ?><td><?= htmlspecialchars((string) ($row[$c] ?? '')) ?></td><?php endforeach; ?>
                                                    </tr>
                                                <?php endforeach; ?>
                                            </tbody>
                                        </table>
                                    </div>
                                <?php endif; ?>

                                <p class="radio-entry-source"><?= radio_source_line($sources, $svc['source_id'] ?? null, $svc['secondary_source_id'] ?? null, $svc['confidence'] ?? null, $svc['source_note'] ?? null) ?></p>
                            </div>
                        </details>
                    <?php endforeach; ?>
                </section>
            <?php endforeach; ?>

            <?php if (!empty($modulation)): ?>
                <section class="radio-group" data-group-section="modulation">
                    <h2 class="radio-group-heading">Modulation Types</h2>
                    <?php foreach ($modulation as $m): ?>
                        <?php $search = radio_search_blob([$m['name'], $m['keywords'] ?? []]); ?>
                        <details class="radio-entry" id="<?= htmlspecialchars($m['id']) ?>" data-group="modulation" data-search="<?= $search ?>">
                            <summary>
                                <span class="radio-entry-name"><?= htmlspecialchars($m['name']) ?></span>
                            </summary>
                            <div class="radio-entry-detail">
                                <p><?= htmlspecialchars($m['explainer']) ?></p>
                                <?php if (!empty($m['when_used'])): ?>
                                    <p><strong>Where it's used:</strong> <?= htmlspecialchars($m['when_used']) ?></p>
                                <?php endif; ?>
                                <p class="radio-entry-source"><?= radio_source_line($sources, $m['source_id'] ?? null, null, $m['confidence'] ?? null, $m['source_note'] ?? null) ?></p>
                            </div>
                        </details>
                    <?php endforeach; ?>
                </section>
            <?php endif; ?>

            <?php if (!empty($sigid)): ?>
                <section class="radio-group" data-group-section="sigid">
                    <h2 class="radio-group-heading">Signal Identification</h2>
                    <p class="muted">PirateBox's own compact identification aid - not a copy of any external signal-ID database. (Signal Identification Wiki was investigated as a source for this section; its own content policy states signal recordings/images are user-submitted with no redistribution license, so nothing was copied from it - see docs/OPERATIONAL-DECISIONS.md. No waterfall images or audio samples are included here for the same reason; identification relies on frequency area, modulation, and a plain-language description of what to listen for.)</p>
                    <?php foreach ($sigid as $s): ?>
                        <?php $search = radio_search_blob([$s['name'], $s['category'] ?? '', $s['frequency_area'] ?? '', 'signal identification', 'sigid']); ?>
                        <details class="radio-entry" id="<?= htmlspecialchars($s['id']) ?>" data-group="sigid" data-search="<?= $search ?>">
                            <summary>
                                <span class="radio-entry-name"><?= htmlspecialchars($s['name']) ?></span>
                                <span class="radio-entry-mode-badge"><?= htmlspecialchars($s['modulation'] ?? '') ?></span>
                            </summary>
                            <div class="radio-entry-detail">
                                <?php if (!empty($s['frequency_area'])): ?><p><strong>Typical frequency area:</strong> <?= htmlspecialchars($s['frequency_area']) ?></p><?php endif; ?>
                                <?php if (!empty($s['bandwidth'])): ?><p><strong>Bandwidth:</strong> <?= htmlspecialchars($s['bandwidth']) ?></p><?php endif; ?>
                                <?php if (!empty($s['identifying_characteristics'])): ?><p><strong>How to recognize it:</strong> <?= htmlspecialchars($s['identifying_characteristics']) ?></p><?php endif; ?>
                                <?php if (!empty($s['related'])): ?>
                                    <p><strong>Related:</strong>
                                        <?php foreach ($s['related'] as $i => $relId): ?><?= $i > 0 ? ', ' : '' ?><a href="#<?= htmlspecialchars($relId) ?>"><?= htmlspecialchars($relId) ?></a><?php endforeach; ?>
                                    </p>
                                <?php endif; ?>
                                <p class="radio-entry-source"><?= radio_source_line($sources, $s['source_id'] ?? null, null, $s['confidence'] ?? null, $s['source_note'] ?? null) ?></p>
                            </div>
                        </details>
                    <?php endforeach; ?>
                </section>
            <?php endif; ?>

            <?php if (!empty($guides)): ?>
                <section class="radio-group" data-group-section="guides">
                    <h2 class="radio-group-heading">Practical Guides</h2>
                    <?php foreach ($guides as $g): ?>
                        <?php $search = radio_search_blob([$g['title'], $g['keywords'] ?? []]); ?>
                        <details class="radio-entry" id="<?= htmlspecialchars($g['id']) ?>" data-group="guides" data-search="<?= $search ?>">
                            <summary>
                                <span class="radio-entry-name"><?= htmlspecialchars($g['title']) ?></span>
                            </summary>
                            <div class="radio-entry-detail">
                                <p><?= htmlspecialchars($g['body']) ?></p>
                                <?php if (!empty($g['table'])): ?>
                                    <?php if (!empty($g['table_caption'])): ?><p><strong><?= htmlspecialchars($g['table_caption']) ?></strong></p><?php endif; ?>
                                    <div class="table-wrapper">
                                        <table class="radio-channel-table">
                                            <?php
                                            // Same union-of-keys approach as the services/channels table
                                            // above - a guide's table rows aren't required to share
                                            // identical keys (e.g. the phonetic-alphabet table has no
                                            // "notes" column, the connector table does).
                                            $gCols = [];
                                            foreach ($g['table'] as $row) {
                                                foreach (array_keys($row) as $k) {
                                                    if (!in_array($k, $gCols, true)) $gCols[] = $k;
                                                }
                                            }
                                            ?>
                                            <thead>
                                                <tr><?php foreach ($gCols as $c): ?><th><?= htmlspecialchars(ucfirst(str_replace('_', ' ', $c))) ?></th><?php endforeach; ?></tr>
                                            </thead>
                                            <tbody>
                                                <?php foreach ($g['table'] as $row): ?>
                                                    <tr>
                                                        <?php foreach ($gCols as $c): ?><td><?= htmlspecialchars((string) ($row[$c] ?? '')) ?></td><?php endforeach; ?>
                                                    </tr>
                                                <?php endforeach; ?>
                                            </tbody>
                                        </table>
                                    </div>
                                <?php endif; ?>
                                <?php
                                // Metadata-driven Document Library cross-link, checked per-guide
                                // (not page-level) - a catalog entry names this exact guide's URL
                                // (e.g. '/utility/radio/#emergency-monitoring-quick-reference') in
                                // its own related_pages, so only the relevant guide gets the box.
                                echo piratebox_render_library_links_html(piratebox_get_library_entries_for_page('/utility/radio/#' . $g['id']));
                                ?>
                                <p class="radio-entry-source"><?= radio_source_line($sources, $g['source_id'] ?? null, null, $g['confidence'] ?? null, $g['source_note'] ?? null) ?></p>
                            </div>
                        </details>
                    <?php endforeach; ?>
                </section>
            <?php endif; ?>
        </div>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
            <a href="/utility/emergency/">Emergency</a>
            <a href="/utility/local/">Local Information</a>
            <a href="/utility/search/">Search</a>
            <a href="/utility/download/">Take This With You</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
