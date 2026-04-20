# MetaSort Stage 5 Feature Extraction

## Scope

- Generate file-level and image-level features for later similarity and grouping stages.
- Fill `ImageFeature` with perceptual hash, difference hash, aspect ratio, and basic visual tags.
- Populate `ImageFile.checksum_sha256` for exact duplicate detection groundwork.

## Current Behavior

- `sha256` is computed for every scanned image file, including invalid ones.
- Valid images are decoded through a Windows PowerShell/.NET backend to obtain grayscale samples.
- `perceptual_hash` is generated with a low-frequency DCT-based pHash.
- `difference_hash` is generated from a downsampled grayscale matrix.
- Basic tags such as `portrait`, `landscape`, `square`, and resolution size buckets are added.
- Stage-level counters are saved to `ProjectRun.summary["features"]`.
