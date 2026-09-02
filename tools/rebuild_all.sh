#!/bin/bash
#
# Stage 27 (build pipeline): one entrypoint for every "regenerate derived
# content from source data" step this project has accumulated across
# Stages 7/8/19 - tools/check_library_catalog.py, tools/
# build_search_index.py, and tools/build_export_bundles.py - instead of
# the operator needing to remember three separate commands, in the right
# order, every time section content under data/utility/ changes.
#
# Order matters: build_export_bundles.py's own output includes the
# global search index it expects build_search_index.py to have already
# produced (see its own SEARCH_INDEX read), so the index is rebuilt
# first. The library catalog is checked for consistency (orphaned files,
# missing catalog entries) before either build step, so a content
# mistake is caught and reported clearly rather than silently baked into
# the search index or shipped in an export bundle.
#
# Safe to re-run any time - every step here is already independently
# idempotent and non-destructive (see each script's own header). None of
# these touch chat/logbook/bulletin/recovery-message data, uploads, or
# any other live user-generated content - only data/utility/ (source)
# and public/utility/{search-index consumers,exports} (generated
# output), exactly as each script's own scope was already documented at
# the time it was introduced.
#
# Usage: tools/rebuild_all.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Checking Document Library catalog consistency =="
python3 "$HERE/check_library_catalog.py"

echo "== Rebuilding global search index =="
python3 "$HERE/build_search_index.py"

echo "== Rebuilding offline export bundles =="
python3 "$HERE/build_export_bundles.py"

echo "== Rebuild complete =="
