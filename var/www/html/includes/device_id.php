<?php

declare(strict_types=1);

// PirateBox public device ID reader (Stage 16). The ID itself is
// generated once, offline, by tools/generate_device_id.sh - this file
// only ever READS it, exactly like every other "read a JSON file, fall
// back safely" helper in this project (piratebox_get_mode(), the Utility
// data loaders, etc.).

if (!function_exists('piratebox_get_device_id')) {
    function piratebox_get_device_id(): ?string
    {
        $raw = @file_get_contents(__DIR__ . '/../data/device-id.json');
        if ($raw === false) {
            return null;
        }
        $decoded = json_decode($raw, true);
        if (!is_array($decoded) || empty($decoded['id']) || !is_string($decoded['id'])) {
            return null;
        }
        return $decoded['id'];
    }
}
