# MetaSort Stage 2 File Scan

## Scope

- Scan the user-selected source folder.
- Respect the `include_subdirectories` policy flag.
- Filter files by supported image extensions.
- Build `ImageFile` records with file name, path, size, extension, and basic dimensions.
- Mark unreadable or malformed image files with scan issues instead of stopping the whole run.

## Current Scanner Behavior

- Supported extensions default to `.png`, `.jpg`, `.jpeg`, `.webp`.
- PNG, JPEG, and WEBP dimensions are read from the binary header without external dependencies.
- Non-image files are skipped during scan statistics.
- Broken image headers are captured as `invalid_image_header` in `ImageFile.issues`.
- Scan summary is stored in `ProjectRun.summary["scan"]`.

## Demo Flow

- `demo_setup.py` creates a small sample input tree.
- `PythonApplication1.py` creates a `ProjectRun`, runs `ImageScanner`, and prints the resulting JSON.
