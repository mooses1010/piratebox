<?php

declare(strict_types=1);

// Morse Code <-> Text converter (Reference -> Tool principle, see
// docs/REFERENCE-CONTENT-DESIGN.md §9). PHP here is the tested,
// canonical implementation (tools/test_fieldtools.php exercises it
// directly with no web server) - same discipline as
// includes/fieldtools_convert.php's own header note.
//
// UNLIKE fieldtools.js's hand-duplicated formulas, the *table* below is
// not hand-copied into JavaScript: public/utility/fieldtools/morse/
// index.php embeds this exact array as a JSON blob at render time
// (json_encode(piratebox_morse_map())), so the JS-enhanced instant
// conversion reads from the identical data this file defines - zero
// drift risk for a ~40-entry lookup table, which is a real risk hand-
// duplication doesn't have for simple arithmetic. No build step, no
// fetch round-trip - just server-side embedding once per page load.
//
// International Morse code (ITU-R M.1677-1) - letters, digits, and the
// common punctuation this standard actually defines. Prosigns beyond
// SOS are deliberately not included (a much longer, less-agreed-upon
// list - out of scope for a general-purpose converter).

if (!function_exists('piratebox_morse_map')) {
    /** @return array<string, string> uppercase character -> Morse code */
    function piratebox_morse_map(): array
    {
        return [
            'A' => '.-',    'B' => '-...',  'C' => '-.-.',  'D' => '-..',
            'E' => '.',     'F' => '..-.',  'G' => '--.',   'H' => '....',
            'I' => '..',    'J' => '.---',  'K' => '-.-',   'L' => '.-..',
            'M' => '--',    'N' => '-.',    'O' => '---',   'P' => '.--.',
            'Q' => '--.-',  'R' => '.-.',   'S' => '...',   'T' => '-',
            'U' => '..-',   'V' => '...-',  'W' => '.--',   'X' => '-..-',
            'Y' => '-.--',  'Z' => '--..',
            '0' => '-----', '1' => '.----', '2' => '..---', '3' => '...--',
            '4' => '....-', '5' => '.....', '6' => '-....', '7' => '--...',
            '8' => '---..', '9' => '----.',
            '.' => '.-.-.-', ',' => '--..--', '?' => '..--..', "'" => '.----.',
            '!' => '-.-.--', '/' => '-..-.',  '(' => '-.--.',  ')' => '-.--.-',
            '&' => '.-...',  ':' => '---...', ';' => '-.-.-.', '=' => '-...-',
            '+' => '.-.-.',  '-' => '-....-', '_' => '..--.-', '"' => '.-..-.',
            '$' => '...-..-', '@' => '.--.-.',
        ];
    }

    /** Reverse lookup, built once from the canonical map above. */
    function piratebox_morse_reverse_map(): array
    {
        return array_flip(piratebox_morse_map());
    }
}

if (!function_exists('piratebox_text_to_morse')) {
    /**
     * @return array{output: string, unknown: array<int, string>}
     * `output` uses a single space between letters and " / " between
     * words. `unknown` lists distinct characters (uppercased) that had
     * no standard mapping and were passed through literally in output,
     * wrapped in curly braces - e.g. an accented letter or emoji.
     */
    function piratebox_text_to_morse(string $text): array
    {
        $map = piratebox_morse_map();
        $words = preg_split('/\s+/', trim($text));
        $unknown = [];
        $wordCodes = [];

        foreach ($words as $word) {
            if ($word === '') continue;
            $letterCodes = [];
            foreach (preg_split('//u', $word, -1, PREG_SPLIT_NO_EMPTY) as $char) {
                $upper = strtoupper($char);
                if (isset($map[$upper])) {
                    $letterCodes[] = $map[$upper];
                } else {
                    $letterCodes[] = '{' . $upper . '}';
                    if (!in_array($upper, $unknown, true)) $unknown[] = $upper;
                }
            }
            $wordCodes[] = implode(' ', $letterCodes);
        }

        return ['output' => implode(' / ', $wordCodes), 'unknown' => $unknown];
    }
}

if (!function_exists('piratebox_morse_to_text')) {
    /**
     * Accepts a single space between letters and either "/" or 2+
     * spaces between words (both common conventions - never guessed at
     * beyond that). Any token that doesn't match a known code is kept
     * literally in the output wrapped in square brackets and listed in
     * `unknown`, never silently dropped or invented.
     *
     * @return array{output: string, unknown: array<int, string>}
     */
    function piratebox_morse_to_text(string $morse): array
    {
        $reverse = piratebox_morse_reverse_map();
        // Normalize word separators: a literal "/" or 2+ spaces both
        // mean "word break" - collapse either to a single marker before
        // splitting, so both conventions are read unambiguously.
        $normalized = preg_replace('/\s{2,}/', ' / ', trim($morse));
        $words = preg_split('/\s*\/\s*/', $normalized);
        $unknown = [];
        $outWords = [];

        foreach ($words as $word) {
            $word = trim($word);
            if ($word === '') continue;
            $letters = [];
            foreach (preg_split('/\s+/', $word) as $token) {
                if ($token === '') continue;
                if (isset($reverse[$token])) {
                    $letters[] = $reverse[$token];
                } else {
                    $letters[] = '[' . $token . ']';
                    if (!in_array($token, $unknown, true)) $unknown[] = $token;
                }
            }
            $outWords[] = implode('', $letters);
        }

        return ['output' => implode(' ', $outWords), 'unknown' => $unknown];
    }
}
