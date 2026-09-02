<?php

declare(strict_types=1);

// Checksum / Hash Calculator (Reference -> Tool principle, see
// docs/REFERENCE-CONTENT-DESIGN.md §9). Investigated per instruction:
// this has unusually strong value specifically BECAUSE PirateBox
// already stores and distributes files via its own file-sharing
// feature (public/uploads/) - verifying a download wasn't corrupted
// in transit is a real, recurring need for exactly what this device
// already does, not a speculative "technically possible" utility.
//
// Deliberately read-only against the existing uploads directory - no
// new upload path, no second way to get a file onto this device. A
// filename is only ever accepted if it exactly matches a real file
// scandir() just found there (same safe-listing discipline
// public/index.php's own file list already uses) - never trusted as a
// raw path, which is what would open a path-traversal hole.
//
// SHA-256 is the only hash presented as suitable for integrity
// verification. MD5 is also shown, explicitly and only for legacy
// compatibility identification (many older published checksums are
// MD5) - never described as secure, per instruction not to recommend
// MD5/SHA-1 as secure hashes.

if (!function_exists('piratebox_hash_text')) {
    /** @return array{sha256: string, md5: string} */
    function piratebox_hash_text(string $text): array
    {
        return ['sha256' => hash('sha256', $text), 'md5' => hash('md5', $text)];
    }
}

if (!function_exists('piratebox_list_uploaded_files')) {
    /**
     * Same safe-listing discipline as public/index.php's own file list:
     * skip dotfiles/directories, tolerate a file vanishing mid-scan.
     * @return array<int, string> filenames only, no path
     */
    function piratebox_list_uploaded_files(string $uploadDir): array
    {
        if (!is_dir($uploadDir)) return [];
        $files = [];
        foreach (scandir($uploadDir) ?: [] as $entry) {
            if ($entry === '.' || $entry === '..' || str_starts_with($entry, '.')) continue;
            if (is_file($uploadDir . '/' . $entry)) $files[] = $entry;
        }
        sort($files, SORT_STRING | SORT_FLAG_CASE);
        return $files;
    }
}

if (!function_exists('piratebox_hash_uploaded_file')) {
    /**
     * @return array{error: string}|array{filename: string, size: int, sha256: string, md5: string}
     */
    function piratebox_hash_uploaded_file(string $filename, string $uploadDir): array
    {
        $realFiles = piratebox_list_uploaded_files($uploadDir);
        if (!in_array($filename, $realFiles, true)) {
            return ['error' => 'That file is not in the current upload list - it may have been removed, or an invalid name was submitted.'];
        }
        $path = $uploadDir . '/' . $filename;
        $size = @filesize($path);
        $sha256 = @hash_file('sha256', $path);
        $md5 = @hash_file('md5', $path);
        if ($size === false || $sha256 === false || $md5 === false) {
            return ['error' => 'Could not read that file - it may have been removed just now.'];
        }
        return ['filename' => $filename, 'size' => $size, 'sha256' => $sha256, 'md5' => $md5];
    }
}
