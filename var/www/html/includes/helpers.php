<?php

declare(strict_types=1);

// PirateBox shared formatting helpers - Phase 5.
//
// Pulled out of admin/index.php (which had its own copy) once index.php
// also needed human-readable byte formatting for the file list, so there
// isn't a third copy. Pure formatting only - no filesystem/system access,
// so this file itself needs no open_basedir considerations.

if (!function_exists('piratebox_fmt_bytes')) {
    function piratebox_fmt_bytes(?int $bytes): string
    {
        if ($bytes === null) return 'unknown';
        $units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
        $i = 0;
        $val = (float) $bytes;
        while ($val >= 1024 && $i < count($units) - 1) {
            $val /= 1024;
            $i++;
        }
        return round($val, 1) . ' ' . $units[$i];
    }
}

if (!function_exists('piratebox_fmt_duration')) {
    function piratebox_fmt_duration(?float $seconds): string
    {
        if ($seconds === null) return 'unknown';
        $days = (int) floor($seconds / 86400);
        $hours = (int) floor(($seconds % 86400) / 3600);
        $mins = (int) floor(($seconds % 3600) / 60);
        $out = [];
        if ($days > 0) $out[] = "{$days}d";
        if ($hours > 0) $out[] = "{$hours}h";
        $out[] = "{$mins}m";
        return implode(' ', $out);
    }
}
