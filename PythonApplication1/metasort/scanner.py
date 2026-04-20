from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path

from .enums import RunStatus
from .models import ImageFile, OutputLog, ProjectRun

DEFAULT_SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")


@dataclass(slots=True)
class ScanStats:
    visited_files: int = 0
    image_candidates: int = 0
    scanned_images: int = 0
    skipped_non_images: int = 0
    invalid_images: int = 0


class ImageScanner:
    def __init__(self, supported_extensions: tuple[str, ...] | None = None) -> None:
        self.supported_extensions = tuple(
            extension.lower()
            for extension in (supported_extensions or DEFAULT_SUPPORTED_EXTENSIONS)
        )

    def scan(self, project_run: ProjectRun) -> ProjectRun:
        source_root = Path(project_run.source_root)
        stats = ScanStats()
        supported_extensions = self._resolve_supported_extensions(project_run)

        if not source_root.exists():
            project_run.status = RunStatus.FAILED
            project_run.logs.append(
                OutputLog(
                    timestamp=project_run.started_at,
                    level="ERROR",
                    message="Source root does not exist.",
                    context={"source_root": str(source_root)},
                )
            )
            project_run.summary["scan"] = {"error": "source_root_missing"}
            return project_run

        project_run.images.clear()
        project_run.groups.clear()

        for file_path in self._iter_files(
            source_root, include_subdirectories=project_run.policy.include_subdirectories
        ):
            stats.visited_files += 1
            if file_path.suffix.lower() not in supported_extensions:
                stats.skipped_non_images += 1
                continue

            stats.image_candidates += 1
            image_file = self._build_image_record(file_path)
            if image_file.issues:
                stats.invalid_images += 1
                project_run.logs.append(
                    OutputLog(
                        timestamp=project_run.started_at,
                        level="WARNING",
                        message="Image header probe failed.",
                        image_id=image_file.image_id,
                        context={"file_path": image_file.file_path},
                    )
                )
            else:
                stats.scanned_images += 1

            project_run.images.append(image_file)

        project_run.status = RunStatus.COMPLETED
        project_run.summary["scan"] = {
            "source_root": str(source_root),
            "include_subdirectories": project_run.policy.include_subdirectories,
            "supported_extensions": list(supported_extensions),
            "visited_files": stats.visited_files,
            "image_candidates": stats.image_candidates,
            "scanned_images": stats.scanned_images,
            "skipped_non_images": stats.skipped_non_images,
            "invalid_images": stats.invalid_images,
        }
        project_run.summary["image_count"] = len(project_run.images)
        project_run.logs.append(
            OutputLog(
                timestamp=project_run.started_at,
                level="INFO",
                message="File scan stage completed.",
                context=project_run.summary["scan"],
            )
        )
        return project_run

    def _resolve_supported_extensions(self, project_run: ProjectRun) -> tuple[str, ...]:
        configured_extensions = project_run.policy.extra_rules.get("supported_extensions")
        if not configured_extensions:
            return self.supported_extensions
        return tuple(extension.lower() for extension in configured_extensions)

    def _iter_files(
        self, source_root: Path, *, include_subdirectories: bool
    ) -> list[Path]:
        if include_subdirectories:
            return [path for path in source_root.rglob("*") if path.is_file()]
        return [path for path in source_root.iterdir() if path.is_file()]

    def _build_image_record(self, file_path: Path) -> ImageFile:
        width, height, issues = self._probe_image(file_path)
        return ImageFile(
            image_id=self._build_image_id(file_path),
            file_name=file_path.name,
            file_path=str(file_path),
            extension=file_path.suffix.lower(),
            file_size_bytes=file_path.stat().st_size,
            width=width,
            height=height,
            issues=issues,
        )

    def _build_image_id(self, file_path: Path) -> str:
        digest = hashlib.sha1(str(file_path).encode("utf-8")).hexdigest()
        return f"img-{digest[:12]}"

    def _probe_image(self, file_path: Path) -> tuple[int | None, int | None, list[str]]:
        suffix = file_path.suffix.lower()
        try:
            if suffix == ".png":
                return (*self._read_png_size(file_path), [])
            if suffix in (".jpg", ".jpeg"):
                return (*self._read_jpeg_size(file_path), [])
            if suffix == ".webp":
                return (*self._read_webp_size(file_path), [])
        except (OSError, ValueError, struct.error):
            return None, None, ["invalid_image_header"]

        return None, None, ["unsupported_extension"]

    def _read_png_size(self, file_path: Path) -> tuple[int, int]:
        with file_path.open("rb") as handle:
            header = handle.read(24)
        if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Invalid PNG signature")
        return struct.unpack(">II", header[16:24])

    def _read_jpeg_size(self, file_path: Path) -> tuple[int, int]:
        with file_path.open("rb") as handle:
            if handle.read(2) != b"\xff\xd8":
                raise ValueError("Invalid JPEG signature")

            while True:
                marker_prefix = handle.read(1)
                if not marker_prefix:
                    break
                if marker_prefix != b"\xff":
                    continue

                marker = handle.read(1)
                while marker == b"\xff":
                    marker = handle.read(1)

                if not marker or marker in {b"\xd8", b"\xd9"}:
                    continue

                segment_length = struct.unpack(">H", handle.read(2))[0]
                if marker in {
                    b"\xc0",
                    b"\xc1",
                    b"\xc2",
                    b"\xc3",
                    b"\xc5",
                    b"\xc6",
                    b"\xc7",
                    b"\xc9",
                    b"\xca",
                    b"\xcb",
                    b"\xcd",
                    b"\xce",
                    b"\xcf",
                }:
                    handle.read(1)
                    height, width = struct.unpack(">HH", handle.read(4))
                    return width, height

                handle.seek(segment_length - 2, 1)

        raise ValueError("JPEG size marker not found")

    def _read_webp_size(self, file_path: Path) -> tuple[int, int]:
        with file_path.open("rb") as handle:
            header = handle.read(30)

        if len(header) < 16 or header[:4] != b"RIFF" or header[8:12] != b"WEBP":
            raise ValueError("Invalid WEBP signature")

        chunk_type = header[12:16]
        if chunk_type == b"VP8X":
            if len(header) < 30:
                raise ValueError("Incomplete WEBP VP8X header")
            width = 1 + int.from_bytes(header[24:27], "little")
            height = 1 + int.from_bytes(header[27:30], "little")
            return width, height

        if chunk_type == b"VP8 ":
            if len(header) < 30 or header[23:26] != b"\x9d\x01\x2a":
                raise ValueError("Invalid WEBP VP8 header")
            width = struct.unpack("<H", header[26:28])[0] & 0x3FFF
            height = struct.unpack("<H", header[28:30])[0] & 0x3FFF
            return width, height

        if chunk_type == b"VP8L":
            if len(header) < 25 or header[20] != 0x2F:
                raise ValueError("Invalid WEBP VP8L header")
            bits = int.from_bytes(header[21:25], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return width, height

        raise ValueError("Unsupported WEBP chunk")
