<?php

declare(strict_types=1);

// PirateBox Normal/Emergency presentation mode - centralized state read.
//
// This is the ONLY place in the app that knows where mode state lives or
// how to interpret it. Every page that needs to know the current mode calls
// piratebox_get_mode() rather than touching PIRATEBOX_MODE_STATE_FILE
// directly, so the storage mechanism can change later (e.g. once a real
// GPIO daemon exists) without touching page code.
//
// Design (see docs/OPERATIONAL-DECISIONS.md, "Emergency Mode software
// foundation" for the full rationale):
//   - State lives in ONE plain-text file containing exactly the word
//     "normal" or "emergency" - nothing else, no JSON, no database.
//   - The file lives on tmpfs (/tmp/piratebox/mode), not the SD card, so it
//     does not persist across a reboot by itself - a fresh boot always
//     starts with no file present, i.e. the safe Normal fallback, until
//     something (the manual test script today, a future GPIO daemon later)
//     explicitly (re)writes it.
//   - /tmp is already inside php.ini's open_basedir on this system, so
//     reading this file requires zero PHP security-restriction change.
//   - PHP/the web tier NEVER writes this file - only a trusted, privileged,
//     out-of-band actor does (today: set_piratebox_mode.sh, run by hand
//     with sudo; later: a root-owned GPIO daemon). There is deliberately no
//     web-reachable way to change mode - see set_piratebox_mode.sh's own
//     comments for why.
//   - ANY failure mode - missing file, empty file, unreadable file,
//     unexpected content - resolves to 'normal'. This function must never
//     throw and must never return anything other than the two literal
//     strings 'normal' or 'emergency'.

define('PIRATEBOX_MODE_STATE_FILE', '/tmp/piratebox/mode');
define('PIRATEBOX_MODE_NORMAL', 'normal');
define('PIRATEBOX_MODE_EMERGENCY', 'emergency');

if (!function_exists('piratebox_get_mode')) {
    function piratebox_get_mode(): string
    {
        $raw = @file_get_contents(PIRATEBOX_MODE_STATE_FILE);
        if ($raw === false) {
            return PIRATEBOX_MODE_NORMAL;
        }

        $value = strtolower(trim($raw));
        if ($value === PIRATEBOX_MODE_EMERGENCY) {
            return PIRATEBOX_MODE_EMERGENCY;
        }

        // Anything else - 'normal' itself, empty, garbage, a stray newline
        // soup, whatever - is treated as Normal. Normal is the only safe
        // default; there is no third "unknown" mode exposed to pages.
        return PIRATEBOX_MODE_NORMAL;
    }
}
