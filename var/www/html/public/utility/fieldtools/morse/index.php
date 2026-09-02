<?php
declare(strict_types=1);
session_start();

// Morse Code Converter (Reference -> Tool principle, see
// docs/REFERENCE-CONTENT-DESIGN.md §9). Authoritative implementation -
// the Radio page's Morse Code Reference table links here, and this page
// links back there for the full table/history rather than repeating it.
//
// Core conversion works via a plain POST + server-render round trip
// with NO JavaScript required (includes/morse.php does the real work,
// same file tools/test_fieldtools.php exercises directly). JavaScript,
// where available, enhances the same page for instant conversion as
// you type - it reads the exact same mapping PHP just used, embedded
// below as JSON at render time, not a hand-duplicated second copy (see
// includes/morse.php's own header for why a lookup table gets this
// treatment instead of the hand-mirrored-formula approach
// fieldtools.js uses for arithmetic).
//
// Nothing entered here is logged, stored in $_SESSION, or written to
// any PirateBox data file - computed and shown for this one request
// only.

require_once __DIR__ . '/../../../../includes/morse.php';

$direction = $_POST['direction'] ?? 'text-to-morse';
if (!in_array($direction, ['text-to-morse', 'morse-to-text'], true)) {
    $direction = 'text-to-morse';
}
$inputValue = (string) ($_POST['input'] ?? '');
$result = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST' && trim($inputValue) !== '') {
    $result = $direction === 'text-to-morse'
        ? piratebox_text_to_morse($inputValue)
        : piratebox_morse_to_text($inputValue);
}

$morseMapJson = json_encode(piratebox_morse_map(), JSON_UNESCAPED_SLASHES);
?>
<!doctype html>
<html lang="en">

<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PirateBox - Morse Code Converter</title>
    <link rel="stylesheet" href="/assets/styles.css">
    <script src="/assets/scripts.js"></script>
</head>

<body>
    <?php require_once __DIR__ . '/../../../../includes/navbar.php'; ?>

    <div class="radio-page">
        <h1>Morse Code Converter</h1>
        <p class="utility-breadcrumb"><a href="/utility/fieldtools/">&larr; Field Tools</a></p>

        <p>Convert between plain text and International Morse Code, entirely offline. For the full character table, history, and why CW is still used on the air, see the <a href="/utility/radio/#morse-code-reference">Morse Code Reference</a> on the Radio page.</p>

        <div class="help-note">
            <p><strong>Notation:</strong> separate <em>letters</em> with a single space. Separate <em>words</em> with a slash ( <code>/</code> ) or extra spacing - both are understood. Example: <code>PIRATEBOX</code> &rarr; <code>.--. .. .-. .- - . -... --- -..-</code>, and <code>SOS</code> &rarr; <code>... --- ...</code> back the other way.</p>
        </div>

        <form method="post" action="" id="morse-form">
            <div class="fieldtools-tool" id="ft-morse-tool">
                <div class="fieldtools-row">
                    <label for="morse-direction">Direction</label>
                    <select id="morse-direction" name="direction">
                        <option value="text-to-morse" <?= $direction === 'text-to-morse' ? 'selected' : '' ?>>Text &rarr; Morse</option>
                        <option value="morse-to-text" <?= $direction === 'morse-to-text' ? 'selected' : '' ?>>Morse &rarr; Text</option>
                    </select>
                    <button type="button" id="morse-swap" title="Swap direction">&#8646; Swap</button>
                </div>

                <div class="fieldtools-row">
                    <label for="morse-input" id="morse-input-label"><?= $direction === 'text-to-morse' ? 'Text' : 'Morse code' ?></label>
                    <textarea id="morse-input" name="input" rows="3" placeholder="<?= $direction === 'text-to-morse' ? 'PIRATEBOX' : '... --- ...' ?>"><?= htmlspecialchars($inputValue) ?></textarea>
                </div>

                <div class="fieldtools-row">
                    <button type="submit">Convert</button>
                </div>

                <?php if ($result !== null): ?>
                    <label for="morse-output"><?= $direction === 'text-to-morse' ? 'Morse code' : 'Text' ?></label>
                    <textarea id="morse-output" rows="3" readonly onclick="this.select()"><?= htmlspecialchars($result['output']) ?></textarea>
                    <?php if (!empty($result['unknown'])): ?>
                        <p class="fieldtools-result help-note">
                            <strong>Not standard Morse notation, shown <?= $direction === 'text-to-morse' ? 'in { curly braces }' : 'in [ square brackets ]' ?> above:</strong>
                            <?= htmlspecialchars(implode(', ', $result['unknown'])) ?>
                            - no mapping was guessed for <?= count($result['unknown']) === 1 ? 'it' : 'these' ?>.
                        </p>
                    <?php endif; ?>
                <?php elseif ($_SERVER['REQUEST_METHOD'] === 'POST'): ?>
                    <p class="fieldtools-result" id="ft-morse-result">Enter some text or Morse code above.</p>
                <?php else: ?>
                    <p class="fieldtools-result" id="ft-morse-result">Enter text or Morse code above, then Convert.</p>
                <?php endif; ?>
            </div>
        </form>

        <noscript>
            <p class="help-note">JavaScript is off - conversion still works: enter your text or Morse code above and press Convert.</p>
        </noscript>
    </div>

    <script>
        // Enhancement only - the form above already works with JS off via
        // the server round trip. This mirrors includes/morse.php's own
        // logic in JS for instant feedback, reading the EXACT SAME
        // mapping PHP just used (embedded below, not hand-duplicated).
        (function () {
            var MORSE_MAP = <?= $morseMapJson ?>;
            var REVERSE_MAP = {};
            for (var k in MORSE_MAP) REVERSE_MAP[MORSE_MAP[k]] = k;

            function textToMorse(text) {
                var unknown = [];
                var words = text.trim().split(/\s+/).filter(Boolean);
                var wordCodes = words.map(function (word) {
                    var letters = Array.from(word).map(function (ch) {
                        var upper = ch.toUpperCase();
                        if (MORSE_MAP[upper]) return MORSE_MAP[upper];
                        if (unknown.indexOf(upper) === -1) unknown.push(upper);
                        return '{' + upper + '}';
                    });
                    return letters.join(' ');
                });
                return { output: wordCodes.join(' / '), unknown: unknown };
            }

            function morseToText(morse) {
                var unknown = [];
                var normalized = morse.trim().replace(/\s{2,}/g, ' / ');
                var words = normalized.split(/\s*\/\s*/).filter(Boolean);
                var outWords = words.map(function (word) {
                    var tokens = word.trim().split(/\s+/).filter(Boolean);
                    var letters = tokens.map(function (tok) {
                        if (REVERSE_MAP[tok]) return REVERSE_MAP[tok];
                        if (unknown.indexOf(tok) === -1) unknown.push(tok);
                        return '[' + tok + ']';
                    });
                    return letters.join('');
                });
                return { output: outWords.join(' '), unknown: unknown };
            }

            var directionSelect = document.getElementById('morse-direction');
            var input = document.getElementById('morse-input');
            var inputLabel = document.getElementById('morse-input-label');
            var swapBtn = document.getElementById('morse-swap');
            var form = document.getElementById('morse-form');
            if (!directionSelect || !input || !form) return;

            // Build a live output area under the form fields (replaces the
            // server-rendered one visually once JS takes over, same markup
            // shape so styling matches).
            var liveOutput = null;
            var liveWarning = null;

            function render() {
                var direction = directionSelect.value;
                inputLabel.textContent = direction === 'text-to-morse' ? 'Text' : 'Morse code';
                input.placeholder = direction === 'text-to-morse' ? 'PIRATEBOX' : '... --- ...';

                var value = input.value;
                if (value.trim() === '') {
                    if (liveOutput) liveOutput.value = '';
                    if (liveWarning) liveWarning.hidden = true;
                    return;
                }
                var result = direction === 'text-to-morse' ? textToMorse(value) : morseToText(value);

                if (!liveOutput) {
                    liveOutput = document.createElement('textarea');
                    liveOutput.id = 'morse-output-live';
                    liveOutput.rows = 3;
                    liveOutput.readOnly = true;
                    liveOutput.addEventListener('click', function () { liveOutput.select(); });
                    var label = document.createElement('label');
                    label.setAttribute('for', 'morse-output-live');
                    label.id = 'morse-output-live-label';
                    liveWarning = document.createElement('p');
                    liveWarning.className = 'fieldtools-result help-note';
                    form.querySelector('.fieldtools-tool').appendChild(label);
                    form.querySelector('.fieldtools-tool').appendChild(liveOutput);
                    form.querySelector('.fieldtools-tool').appendChild(liveWarning);
                    // Hide the server-rendered (pre-JS) output/message, if any.
                    ['morse-output', 'ft-morse-result'].forEach(function (id) {
                        var prevLabel = document.querySelector('label[for="' + id + '"]');
                        var el = document.getElementById(id);
                        if (prevLabel) prevLabel.hidden = true;
                        if (el) el.hidden = true;
                    });
                }
                document.getElementById('morse-output-live-label').textContent = direction === 'text-to-morse' ? 'Morse code' : 'Text';
                liveOutput.value = result.output;

                if (result.unknown.length) {
                    var bracket = direction === 'text-to-morse' ? 'in { curly braces }' : 'in [ square brackets ]';
                    liveWarning.textContent = 'Not standard Morse notation, shown ' + bracket + ' above: ' + result.unknown.join(', ') + ' - no mapping was guessed for ' + (result.unknown.length === 1 ? 'it' : 'these') + '.';
                    liveWarning.hidden = false;
                } else {
                    liveWarning.hidden = true;
                }
            }

            input.addEventListener('input', render);
            directionSelect.addEventListener('change', render);
            if (swapBtn) {
                swapBtn.addEventListener('click', function () {
                    directionSelect.value = directionSelect.value === 'text-to-morse' ? 'morse-to-text' : 'text-to-morse';
                    var currentOutput = liveOutput ? liveOutput.value : '';
                    if (currentOutput) input.value = currentOutput;
                    render();
                });
            }
            render();
        })();
    </script>

    <?php require_once __DIR__ . '/../../../../includes/footer.php'; ?>
</body>

</html>
