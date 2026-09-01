# Document Library catalog

`catalog.json` is an array of document entries. Each entry:

```json
{
  "id": "unique-slug",
  "title": "Document title",
  "category": "one of: radio, pi-linux-networking, electronics, vehicle-generator, emergency-firstaid, maps, owned-equipment, other",
  "description": "One or two sentences describing what this document is.",
  "tags": ["keyword1", "keyword2"],
  "file": "filename-in-files-directory.pdf",
  "file_type": "pdf",
  "file_size": "2.3 MB",
  "source": "Publisher/manufacturer name",
  "date_version": "2024 edition / v2.1 / retrieved 2026-09-01",
  "provenance_notes": "Where this came from and any license/copyright notes."
}
```

## Adding a document

1. Copy the file into `public/utility/library/files/` on the box.
2. Add one entry to `catalog.json` (this file's sibling) with the fields
   above - `file` must exactly match the filename you copied.
3. Run `python3 tools/check_library_catalog.py` (repo root) to confirm the
   catalog and the files directory agree - it flags orphaned files with no
   catalog entry, and catalog entries pointing at a missing file.

No PHP/HTML editing is ever required to add a document.

## Do not

- Do not add copyrighted manuals/books you don't have the right to
  redistribute, without checking their license first.
- Do not bulk-import large collections without deliberately deciding to -
  this library is meant to stay lightweight and curated, not become an
  unmanaged dumping ground.
