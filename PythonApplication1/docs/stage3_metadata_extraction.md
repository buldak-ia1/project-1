# MetaSort Stage 3 Metadata Extraction

## Scope

- Extract raw metadata from scanned image files.
- Support PNG text chunks and EXIF-based metadata sources.
- Store extracted values in `ImageFile.raw_metadata` without normalizing them yet.
- Keep extraction failures isolated per file so the run can continue.

## Current Behavior

- PNG metadata reads `tEXt`, `zTXt`, and `iTXt` chunks.
- JPEG metadata reads `APP1 Exif` blocks and parses TIFF tag values into a dictionary.
- WEBP metadata reads `EXIF` chunks when present.
- Broken files are skipped if scan stage already marked them invalid.
- Stage-level counters are saved to `ProjectRun.summary["metadata"]`.

## Demo Notes

- Demo PNG files now contain embedded text metadata such as `parameters` and `Software`.
- The main script runs scan first and metadata extraction second, then prints the combined JSON output.
