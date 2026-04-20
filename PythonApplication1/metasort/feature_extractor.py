from __future__ import annotations

import hashlib
import math
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .external_models import resolve_embedding_backend
from .models import ImageFeature, OutputLog, ProjectRun

FEATURE_SAMPLE_SIZE = 32
DHASH_WIDTH = 9
DHASH_HEIGHT = 8

POWERSHELL_GRAYSCALE_SCRIPT = r"""
Add-Type -AssemblyName System.Drawing
$ImagePath = $env:METASORT_IMAGE_PATH
$Width = [int]$env:METASORT_SAMPLE_WIDTH
$Height = [int]$env:METASORT_SAMPLE_HEIGHT
$bitmap = [System.Drawing.Bitmap]::new($ImagePath)
$scaled = [System.Drawing.Bitmap]::new($Width, $Height)
$graphics = [System.Drawing.Graphics]::FromImage($scaled)
try {
    $graphics.DrawImage($bitmap, 0, 0, $Width, $Height)
    $pixels = New-Object System.Collections.Generic.List[string]
    for ($y = 0; $y -lt $Height; $y++) {
        for ($x = 0; $x -lt $Width; $x++) {
            $pixel = $scaled.GetPixel($x, $y)
            $gray = [int][Math]::Round(0.299 * $pixel.R + 0.587 * $pixel.G + 0.114 * $pixel.B)
            [void]$pixels.Add($gray.ToString())
        }
    }
    [Console]::Out.Write($pixels -join ',')
}
finally {
    $graphics.Dispose()
    $scaled.Dispose()
    $bitmap.Dispose()
}
"""


@dataclass(slots=True)
class FeatureStats:
    processed_images: int = 0
    skipped_invalid_images: int = 0
    extracted_hashes: int = 0
    extracted_embeddings: int = 0
    external_embeddings: int = 0
    local_embeddings: int = 0
    failed_images: int = 0


class FeatureExtractor:
    def extract(self, project_run: ProjectRun) -> ProjectRun:
        stats = FeatureStats()
        embedding_backend, backend_resolution = resolve_embedding_backend(project_run.policy.extra_rules)
        if backend_resolution.warning:
            project_run.logs.append(
                OutputLog(
                    timestamp=project_run.started_at,
                    level="WARNING",
                    message="External embedding backend fallback applied.",
                    context={
                        "requested_provider": backend_resolution.requested_provider,
                        "active_provider": backend_resolution.provider_name,
                        "warning": backend_resolution.warning,
                    },
                )
            )

        for image in project_run.images:
            file_path = Path(image.file_path)
            image.checksum_sha256 = self._compute_sha256(file_path)

            if "invalid_image_header" in image.issues:
                stats.skipped_invalid_images += 1
                continue

            stats.processed_images += 1
            try:
                grayscale = self._load_grayscale_matrix(file_path, FEATURE_SAMPLE_SIZE, FEATURE_SAMPLE_SIZE)
            except (OSError, RuntimeError, ValueError) as error:
                stats.failed_images += 1
                image.issues.append("feature_extraction_failed")
                project_run.logs.append(
                    OutputLog(
                        timestamp=project_run.started_at,
                        level="WARNING",
                        message="Feature extraction failed.",
                        image_id=image.image_id,
                        context={"file_path": image.file_path, "error": str(error)},
                    )
                )
                continue

            resized_for_dhash = self._resize_matrix(grayscale, DHASH_WIDTH, DHASH_HEIGHT)
            dominant_tags = self._build_enriched_tags(image, grayscale)
            embedding_vector = self._compute_embedding_vector(
                project_run=project_run,
                image=image,
                file_path=file_path,
                grayscale=grayscale,
                dominant_tags=dominant_tags,
                embedding_backend=embedding_backend,
                backend_resolution=backend_resolution,
                stats=stats,
            )
            image.feature = ImageFeature(
                perceptual_hash=self._compute_phash(grayscale),
                difference_hash=self._compute_dhash(resized_for_dhash),
                embedding_vector=embedding_vector,
                aspect_ratio=self._compute_aspect_ratio(image.width, image.height),
                dominant_tags=dominant_tags,
            )
            stats.extracted_hashes += 1
            if embedding_vector:
                stats.extracted_embeddings += 1

        project_run.summary["features"] = {
            "processed_images": stats.processed_images,
            "skipped_invalid_images": stats.skipped_invalid_images,
            "extracted_hashes": stats.extracted_hashes,
            "extracted_embeddings": stats.extracted_embeddings,
            "external_embeddings": stats.external_embeddings,
            "local_embeddings": stats.local_embeddings,
            "embedding_backend": backend_resolution.provider_name,
            "requested_embedding_provider": backend_resolution.requested_provider,
            "using_external_backend": backend_resolution.using_external,
            "failed_images": stats.failed_images,
        }
        project_run.logs.append(
            OutputLog(
                timestamp=project_run.started_at,
                level="INFO",
                message="Feature extraction stage completed.",
                context=project_run.summary["features"],
            )
        )
        return project_run

    def _compute_sha256(self, file_path: Path) -> str:
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _load_grayscale_matrix(
        self, file_path: Path, width: int, height: int
    ) -> list[list[int]]:
        env = os.environ.copy()
        env["METASORT_IMAGE_PATH"] = str(file_path)
        env["METASORT_SAMPLE_WIDTH"] = str(width)
        env["METASORT_SAMPLE_HEIGHT"] = str(height)
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                POWERSHELL_GRAYSCALE_SCRIPT,
            ],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        if result.returncode != 0:
            error_text = result.stderr.strip() or result.stdout.strip() or "unknown backend error"
            raise RuntimeError(error_text)

        pixel_values = [value for value in result.stdout.strip().split(",") if value]
        expected_count = width * height
        if len(pixel_values) != expected_count:
            raise ValueError("Unexpected grayscale backend output size")

        numbers = [int(value) for value in pixel_values]
        return [
            numbers[row_start : row_start + width]
            for row_start in range(0, expected_count, width)
        ]

    def _resize_matrix(
        self, source: list[list[int]], target_width: int, target_height: int
    ) -> list[list[int]]:
        source_height = len(source)
        source_width = len(source[0])
        resized: list[list[int]] = []

        for target_y in range(target_height):
            row: list[int] = []
            source_y = min(int(target_y * source_height / target_height), source_height - 1)
            for target_x in range(target_width):
                source_x = min(int(target_x * source_width / target_width), source_width - 1)
                row.append(source[source_y][source_x])
            resized.append(row)

        return resized

    def _compute_phash(self, grayscale: list[list[int]]) -> str:
        dct_low = self._dct_low_frequency(grayscale, 8)
        flattened = [value for row in dct_low for value in row]
        median = self._median(flattened[1:] or flattened)
        bits = "".join("1" if value >= median else "0" for value in flattened)
        return f"{int(bits, 2):016x}"

    def _compute_dhash(self, grayscale: list[list[int]]) -> str:
        bits: list[str] = []
        for row in grayscale:
            for index in range(len(row) - 1):
                bits.append("1" if row[index] > row[index + 1] else "0")
        return f"{int(''.join(bits), 2):016x}"

    def _dct_low_frequency(self, grayscale: list[list[int]], size: int) -> list[list[float]]:
        dimension = len(grayscale)
        cos_table = [
            [math.cos(((2 * x + 1) * u * math.pi) / (2 * dimension)) for x in range(dimension)]
            for u in range(size)
        ]
        alpha = [
            math.sqrt(1 / dimension) if index == 0 else math.sqrt(2 / dimension)
            for index in range(size)
        ]

        coefficients: list[list[float]] = []
        for u in range(size):
            row: list[float] = []
            for v in range(size):
                total = 0.0
                for x in range(dimension):
                    for y in range(dimension):
                        total += grayscale[x][y] * cos_table[u][x] * cos_table[v][y]
                row.append(alpha[u] * alpha[v] * total)
            coefficients.append(row)
        return coefficients

    def _median(self, values: list[float]) -> float:
        sorted_values = sorted(values)
        middle = len(sorted_values) // 2
        if len(sorted_values) % 2:
            return sorted_values[middle]
        return (sorted_values[middle - 1] + sorted_values[middle]) / 2

    def _compute_aspect_ratio(self, width: int | None, height: int | None) -> float | None:
        if not width or not height:
            return None
        return width / height

    def _build_basic_tags(self, width: int | None, height: int | None) -> list[str]:
        tags: list[str] = []
        if width and height:
            if width == height:
                tags.append("square")
            elif width > height:
                tags.append("landscape")
            else:
                tags.append("portrait")

            area = width * height
            if area <= 512 * 512:
                tags.append("resolution_small")
            elif area <= 1280 * 1280:
                tags.append("resolution_medium")
            else:
                tags.append("resolution_large")
        return tags

    def _build_enriched_tags(self, image, grayscale: list[list[int]]) -> list[str]:
        tags = self._build_basic_tags(image.width, image.height)
        flattened = [value for row in grayscale for value in row]
        if not flattened:
            return tags

        mean_value = sum(flattened) / len(flattened)
        variance = sum((value - mean_value) ** 2 for value in flattened) / len(flattened)
        contrast = math.sqrt(variance)
        if mean_value <= 85:
            tags.append("tone_dark")
        elif mean_value >= 170:
            tags.append("tone_bright")
        else:
            tags.append("tone_balanced")

        if contrast <= 18:
            tags.append("contrast_low")
        elif contrast >= 55:
            tags.append("contrast_high")
        else:
            tags.append("contrast_medium")

        prompt_text = ""
        if image.normalized_metadata and image.normalized_metadata.prompt:
            prompt_text = image.normalized_metadata.prompt.lower()

        style_cues = {
            "style_anime": ["anime", "illustration", "cel shading", "lineart"],
            "style_realistic": ["photorealistic", "realistic", "photo", "cinematic"],
            "style_painterly": ["painterly", "oil painting", "brush", "watercolor"],
            "style_chibi": ["chibi", "super deformed"],
        }
        for tag, keywords in style_cues.items():
            if any(keyword in prompt_text for keyword in keywords):
                tags.append(tag)

        return sorted(dict.fromkeys(tags))

    def _compute_embedding_vector(
        self,
        *,
        project_run: ProjectRun,
        image,
        file_path: Path,
        grayscale: list[list[int]],
        dominant_tags: list[str],
        embedding_backend,
        backend_resolution,
        stats: FeatureStats,
    ) -> list[float]:
        if embedding_backend is not None:
            try:
                vector = embedding_backend.extract_embedding(file_path)
            except Exception as error:
                project_run.logs.append(
                    OutputLog(
                        timestamp=project_run.started_at,
                        level="WARNING",
                        message="External embedding extraction failed; local fallback applied.",
                        image_id=image.image_id,
                        context={
                            "file_path": image.file_path,
                            "provider": backend_resolution.provider_name,
                            "error": str(error),
                        },
                    )
                )
            else:
                if vector:
                    stats.external_embeddings += 1
                    return vector

        flattened = [value for row in grayscale for value in row]
        if not flattened:
            return []
        stats.local_embeddings += 1

        mean_value = sum(flattened) / len(flattened)
        variance = sum((value - mean_value) ** 2 for value in flattened) / len(flattened)
        contrast = math.sqrt(variance)
        edge_density = self._compute_edge_density(grayscale)
        aspect_ratio = self._compute_aspect_ratio(image.width, image.height) or 1.0
        return [
            round(mean_value / 255, 6),
            round(min(contrast / 128, 1.0), 6),
            round(edge_density, 6),
            round(min(aspect_ratio / 4, 1.0), 6),
            self._hash_to_unit_interval(
                (image.normalized_metadata.prompt if image.normalized_metadata else "") or "",
                salt="prompt",
            ),
            self._hash_to_unit_interval(
                (image.normalized_metadata.model if image.normalized_metadata else "") or "",
                salt="model",
            ),
            self._hash_to_unit_interval("|".join(dominant_tags), salt="tags"),
            self._hash_to_unit_interval(image.file_name.lower(), salt="name"),
        ]

    def _compute_edge_density(self, grayscale: list[list[int]]) -> float:
        comparisons = 0
        edges = 0
        for row in grayscale:
            for index in range(len(row) - 1):
                comparisons += 1
                if abs(row[index] - row[index + 1]) >= 12:
                    edges += 1
        if not comparisons:
            return 0.0
        return edges / comparisons

    def _hash_to_unit_interval(self, text: str, *, salt: str) -> float:
        digest = hashlib.sha1(f"{salt}:{text}".encode("utf-8")).digest()
        value = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
        return round(value, 6)
