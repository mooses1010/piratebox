<?php

declare(strict_types=1);

require_once __DIR__ . '/config.php';

// Stage 24 (resilience audit): a shared "is there enough free space to
// accept this small write" check for the flat-file JSON stores
// (chat.json/messages.json/bulletin.json). Mirrors the guard upload.php
// already had (Phase 2) for the much larger uploads path, sized instead
// for PIRATEBOX_MIN_FREE_BYTES_SMALL_WRITE - see includes/config.php for
// why the two thresholds are different.
//
// Found during the Stage 24 audit: chat.php/messages.php (and Stage 22's
// bulletin.php, which copied the same pattern) had NO free-space check at
// all before writing - file_put_contents() failing silently (returns
// false, already correctly checked before the rename) meant a post could
// be silently dropped under genuine storage exhaustion with the poster
// never told their message wasn't saved. This closes that gap the same
// way upload.php already closes it: check BEFORE attempting the write,
// so a low-storage rejection is an explicit, honest message rather than a
// silent no-op.

if (!function_exists('piratebox_low_storage')) {
    /**
     * True if there is NOT enough free space on $checkPath's filesystem to
     * safely accept another small (JSON flat-file) write. Fails open (i.e.
     * returns false / "not low") if disk_free_space() itself can't be
     * read - the guard's job is to catch a real, measurable shortage, not
     * to add a new way for the board to stop working if a stat call ever
     * fails for an unrelated reason.
     */
    function piratebox_low_storage(string $checkPath): bool
    {
        $freeBytes = @disk_free_space($checkPath);
        if ($freeBytes === false) {
            return false;
        }
        return $freeBytes < PIRATEBOX_MIN_FREE_BYTES_SMALL_WRITE;
    }
}
