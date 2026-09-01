#!/usr/bin/env python3
"""Consistency check for the Document Library catalog (Stage 7).

Not a search-index builder and does not extract PDF metadata - deliberately
dependency-free (no poppler-utils/pdftotext), per instruction not to
install packages for this without stopping first. It only checks that:

  1. every catalog.json entry's "file" points at a file that actually
     exists in the library's files/ directory, and
  2. every file in that directory has a matching catalog.json entry
     (orphaned files are easy to forget about otherwise).

Run from the repo root: python3 tools/check_library_catalog.py
Exit code 0 = clean, 1 = at least one problem found (prints details either
way).
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = REPO_ROOT / "var/www/html/data/utility/library/catalog.json"
FILES_DIR = REPO_ROOT / "var/www/html/public/utility/library/files"


def main() -> int:
    if not CATALOG_PATH.is_file():
        print(f"ERROR: catalog not found at {CATALOG_PATH}")
        return 1

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(catalog, list):
        print("ERROR: catalog.json must be a JSON array")
        return 1

    catalog_files = {}
    problems = []
    seen_ids = set()

    for i, entry in enumerate(catalog):
        entry_id = entry.get("id", f"<entry {i}, no id>")
        if not entry.get("id"):
            problems.append(f"Entry {i}: missing required 'id' field")
        elif entry_id in seen_ids:
            problems.append(f"Entry {i} ('{entry_id}'): duplicate id")
        seen_ids.add(entry_id)

        for required in ("title", "category", "file"):
            if not entry.get(required):
                problems.append(f"Entry '{entry_id}': missing required '{required}' field")

        fname = entry.get("file")
        if fname:
            catalog_files[fname] = entry_id
            if not (FILES_DIR / fname).is_file():
                problems.append(f"Entry '{entry_id}': file '{fname}' not found in {FILES_DIR}")

    if FILES_DIR.is_dir():
        for path in FILES_DIR.iterdir():
            if path.name in (".gitkeep",) or path.name.startswith("."):
                continue
            if path.is_file() and path.name not in catalog_files:
                problems.append(f"Orphaned file '{path.name}' in {FILES_DIR} has no catalog.json entry")
    else:
        problems.append(f"Files directory does not exist: {FILES_DIR}")

    print(f"Catalog entries: {len(catalog)}")
    print(f"Files on disk:   {sum(1 for p in FILES_DIR.glob('*') if p.is_file() and not p.name.startswith('.'))}" if FILES_DIR.is_dir() else "Files on disk:   (directory missing)")

    if problems:
        print(f"\n{len(problems)} problem(s) found:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("\nNo problems found - catalog and files directory agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
