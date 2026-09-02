<?php

declare(strict_types=1);

// PirateBox shared configuration.
//
// Centralizing storage-policy constants here so there is one obvious place
// to read/change them later (e.g. from a future admin interface) instead of
// hard-coding policy values across multiple PHP files.

// Minimum free space (in bytes) that must remain on the uploads filesystem
// AFTER an upload is accepted. Uploads that would leave less than this free
// are rejected before being committed to permanent storage.
//
// Chosen as 1 GiB on this system (Phase 2, 2026-08-31): comfortably larger
// than the largest single upload allowed (130MiB), so no single upload can
// ever push free space from "fine" to "exhausted" in one step, while being
// a small fraction of this system's ~114GiB available capacity - it does not
// meaningfully reduce usable storage for uploads. This does not delete any
// existing files; it only guards new uploads. See
// docs/OPERATIONAL-DECISIONS.md for the full rationale.
define('PIRATEBOX_MIN_FREE_BYTES', 1024 * 1024 * 1024);

// Stage 24 (resilience audit): the same kind of guard as above, but sized
// for the tiny flat-file JSON stores (chat.json/messages.json/
// bulletin.json) instead of uploads. A single post there is at most a few
// KB (2000-char message cap), nowhere near upload.php's 130MiB ceiling, so
// reusing the 1GiB uploads threshold would be needlessly conservative -
// it would refuse to save a logbook entry while gigabytes of
// deliberately-reserved uploads headroom sit untouched. 5MiB is chosen as
// comfortably larger than any realistic burst of concurrent small writes
// (even a full 200-post board at the 2000-char cap is under 1MiB total),
// while still catching genuine near-total exhaustion before a write is
// attempted, rather than after.
//
// This does not change upload.php's own guard/threshold - the two are
// deliberately independent, sized for what each path actually writes.
define('PIRATEBOX_MIN_FREE_BYTES_SMALL_WRITE', 5 * 1024 * 1024);
