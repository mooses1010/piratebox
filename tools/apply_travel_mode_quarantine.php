#!/usr/bin/env php
<?php

declare(strict_types=1);

// Post-Stage-32 (Travel Mode): re-applies the direct-access quarantine
// against a given webroot. Called from piratebox_deploy.sh after every
// real (non-dry-run) deploy, because a deploy can write fresh,
// un-quarantined copies of local-sensitive static exports (see
// includes/travel_mode.php's PIRATEBOX_TRAVEL_MODE_QUARANTINE_PATHS)
// straight over ones that were already quarantined. Idempotent and
// safe to run any time, in any state - it only moves what actually
// needs to move for whatever the current Travel Mode state already is.
//
// Usage: php apply_travel_mode_quarantine.php <webroot>
//   <webroot> contains public/ and data/ as siblings (e.g. /var/www/html
//   live, or an isolated test copy for the leakage regression test).

if ($argc !== 2 || $argv[1] === '') {
    fwrite(STDERR, "Usage: php apply_travel_mode_quarantine.php <webroot>\n");
    exit(1);
}

$webroot = rtrim($argv[1], '/');
$travelModeFile = $webroot . '/includes/travel_mode.php';

if (!is_file($travelModeFile)) {
    fwrite(STDERR, "apply_travel_mode_quarantine.php: $travelModeFile not found - is $webroot a real PirateBox webroot?\n");
    exit(1);
}

require $travelModeFile;

piratebox_apply_travel_mode_quarantine($webroot . '/public/utility/exports', $webroot . '/data/travel-mode-quarantine');

echo "Travel Mode quarantine re-applied (mode: " . (piratebox_get_travel_mode() ? 'ON' : 'OFF') . ").\n";
