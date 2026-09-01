<?php
declare(strict_types=1);
session_start();

// Local Information (Stage 6). A SINGLE editable reference sheet for
// wherever this PirateBox currently is - not a searchable multi-topic
// dataset like Radio/Emergency/First Aid/Maps, so this page intentionally
// does not use the shared radio-entry/search/chip UI those pages share.
//
// To relocate this PirateBox: edit data/utility/local/info.json only.
// No PHP/HTML change is ever required to update local information.
//
// Deliberately does NOT read piratebox_get_mode() - identical in Normal and
// Emergency Mode by design.

$DATA_DIR = __DIR__ . '/../../../data/utility/local';

function ref_load_json(string $path): array
{
    $raw = @file_get_contents($path);
    if ($raw === false) return [];
    $decoded = json_decode($raw, true);
    return is_array($decoded) ? $decoded : [];
}

$info = ref_load_json($DATA_DIR . '/info.json');

function li_empty(string $msg): void
{
    echo '<p class="empty-state">' . htmlspecialchars($msg) . '</p>';
}

/**
 * Stage 17: optional per-entry provenance (source/verified/confidence),
 * documented in data/utility/local/README.md. Renders nothing if none of
 * the three fields are present - purely additive, never required.
 */
function li_provenance(array $entry): string
{
    $bits = [];
    if (!empty($entry['source'])) $bits[] = 'Source: ' . htmlspecialchars((string) $entry['source']);
    if (!empty($entry['verified'])) $bits[] = 'verified ' . htmlspecialchars((string) $entry['verified']);
    if (!empty($entry['confidence'])) {
        $c = htmlspecialchars((string) $entry['confidence']);
        $bits[] = 'confidence: <span class="radio-confidence confidence-' . $c . '">' . $c . '</span>';
    }
    return $bits ? '<br><span class="muted">' . implode(' &middot; ', $bits) . '</span>' : '';
}

function li_field_row(string $label, ?string $value): void
{
    if (empty($value)) return;
    echo '<p><strong>' . htmlspecialchars($label) . ':</strong> ' . htmlspecialchars($value) . '</p>';
}
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Local Information</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Local Information</h1>
        <p class="utility-breadcrumb"><a href="/utility/">&larr; Utility Library</a></p>

        <p>
            One editable reference sheet for wherever this PirateBox currently is.
            <?php if (!empty($info['region_label'])): ?>
                Currently set for: <strong><?= htmlspecialchars($info['region_label']) ?></strong>.
            <?php else: ?>
                <strong>No region has been set yet</strong> - this box hasn't been configured for a specific location.
            <?php endif; ?>
        </p>
        <?php if (!empty($info['last_updated'])): ?>
            <p class="muted">Last updated: <?= htmlspecialchars($info['last_updated']) ?></p>
        <?php endif; ?>

        <section class="help-section">
            <h2>Emergency Management &amp; NWS Office</h2>
            <?php if (empty($info['emergency_management']['name']) && empty($info['nws_office']['name'])): ?>
                <?php li_empty('Not yet added for this location.'); ?>
            <?php else: ?>
                <?php if (!empty($info['emergency_management']['name'])): ?>
                    <h3>Local Emergency Management</h3>
                    <?php li_field_row('Name', $info['emergency_management']['name']); ?>
                    <?php li_field_row('Phone', $info['emergency_management']['phone'] ?? null); ?>
                    <?php li_field_row('Website', $info['emergency_management']['website'] ?? null); ?>
                    <?php li_field_row('Notes', $info['emergency_management']['notes'] ?? null); ?>
                <?php endif; ?>
                <?php if (!empty($info['nws_office']['name'])): ?>
                    <h3>NOAA / National Weather Service Office</h3>
                    <?php li_field_row('Name', $info['nws_office']['name']); ?>
                    <?php li_field_row('Phone', $info['nws_office']['phone'] ?? null); ?>
                    <?php li_field_row('Website', $info['nws_office']['website'] ?? null); ?>
                    <?php li_field_row('Notes', $info['nws_office']['notes'] ?? null); ?>
                <?php endif; ?>
            <?php endif; ?>
        </section>

        <section class="help-section">
            <h2>Emergency Numbers</h2>
            <?php if (empty($info['emergency_numbers'])): ?>
                <?php li_empty('None added yet for this location.'); ?>
            <?php else: ?>
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>What</th><th>Number</th><th>Notes</th></tr></thead>
                        <tbody>
                            <?php foreach ($info['emergency_numbers'] as $n): ?>
                                <tr>
                                    <td><?= htmlspecialchars($n['label'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($n['number'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($n['notes'] ?? '') ?></td>
                                </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            <?php endif; ?>
        </section>

        <section class="help-section">
            <h2>Hospitals</h2>
            <?php if (empty($info['hospitals'])): ?>
                <?php li_empty('None added yet for this location.'); ?>
            <?php else: ?>
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>Name</th><th>Address</th><th>Phone</th><th>Notes</th></tr></thead>
                        <tbody>
                            <?php foreach ($info['hospitals'] as $h): ?>
                                <tr>
                                    <td><?= htmlspecialchars($h['name'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($h['address'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($h['phone'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($h['notes'] ?? '') ?><?= li_provenance($h) ?></td>
                                </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            <?php endif; ?>
        </section>

        <section class="help-section">
            <h2>Shelters</h2>
            <?php if (empty($info['shelters'])): ?>
                <?php li_empty('None added yet for this location.'); ?>
            <?php else: ?>
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>Name</th><th>Address</th><th>Phone</th><th>Notes</th></tr></thead>
                        <tbody>
                            <?php foreach ($info['shelters'] as $s): ?>
                                <tr>
                                    <td><?= htmlspecialchars($s['name'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($s['address'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($s['phone'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($s['notes'] ?? '') ?><?= li_provenance($s) ?></td>
                                </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            <?php endif; ?>
        </section>

        <section class="help-section">
            <h2>Local Amateur Radio Repeaters</h2>
            <?php if (empty($info['amateur_repeaters'])): ?>
                <?php li_empty('None added yet for this location.'); ?>
            <?php else: ?>
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>Callsign</th><th>Frequency</th><th>Offset</th><th>Tone</th><th>Location</th><th>Notes</th></tr></thead>
                        <tbody>
                            <?php foreach ($info['amateur_repeaters'] as $r): ?>
                                <tr>
                                    <td><?= htmlspecialchars($r['callsign'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($r['frequency'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($r['offset'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($r['tone'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($r['location'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($r['notes'] ?? '') ?><?= li_provenance($r) ?></td>
                                </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            <?php endif; ?>
            <?php if (!empty($info['radio_notes'])): ?>
                <p><strong>Region-specific radio notes:</strong> <?= htmlspecialchars($info['radio_notes']) ?></p>
            <?php endif; ?>
            <p class="muted">See the <a href="/utility/radio/">Radio Reference</a> for general band/frequency information that applies everywhere.</p>
        </section>

        <section class="help-section">
            <h2>Local Map References</h2>
            <?php if (empty($info['map_references'])): ?>
                <?php li_empty('None added yet for this location.'); ?>
            <?php else: ?>
                <ul class="ref-quick-actions">
                    <?php foreach ($info['map_references'] as $m): ?>
                        <li><strong><?= htmlspecialchars($m['title'] ?? '') ?></strong><?= !empty($m['note']) ? ' - ' . htmlspecialchars($m['note']) : '' ?></li>
                    <?php endforeach; ?>
                </ul>
            <?php endif; ?>
            <p class="muted">See the full <a href="/utility/maps/">Maps &amp; Location Reference</a> catalog.</p>
        </section>

        <section class="help-section">
            <h2>Other Local Resources</h2>
            <?php if (empty($info['other_resources'])): ?>
                <?php li_empty('None added yet for this location.'); ?>
            <?php else: ?>
                <div class="table-wrapper">
                    <table>
                        <thead><tr><th>Name</th><th>Contact</th><th>Notes</th></tr></thead>
                        <tbody>
                            <?php foreach ($info['other_resources'] as $r): ?>
                                <tr>
                                    <td><?= htmlspecialchars($r['name'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($r['contact'] ?? '') ?></td>
                                    <td><?= htmlspecialchars($r['notes'] ?? '') ?><?= li_provenance($r) ?></td>
                                </tr>
                            <?php endforeach; ?>
                        </tbody>
                    </table>
                </div>
            <?php endif; ?>
        </section>

        <div class="help-note">
            <p><strong>Keeping this current:</strong> everything on this page comes from one file, <code>data/utility/local/info.json</code>. Edit that file when this PirateBox moves or local details change - no PHP/HTML editing required.</p>
        </div>

        <div class="hero-actions">
            <a href="/utility/">Utility Library</a>
            <a href="/utility/emergency/">Emergency</a>
            <a href="/utility/maps/">Maps</a>
            <a href="/utility/search/">Search</a>
        </div>
    </div>

    <?php require_once __DIR__ . '/../../../includes/footer.php'; ?>
</body>

</html>
