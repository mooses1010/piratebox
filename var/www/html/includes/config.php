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
