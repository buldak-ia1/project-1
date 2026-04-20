from __future__ import annotations

import string
import struct
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import OutputLog, ProjectRun, RawMetadata


@dataclass(slots=True)
class MetadataStats:
    extracted_images: int = 0
    png_text_images: int = 0
    exif_images: int = 0
    missing_metadata: int = 0
    skipped_invalid_images: int = 0
    failed_images: int = 0


class MetadataExtractor:
    def extract(self, project_run: ProjectRun) -> ProjectRun:
        stats = MetadataStats()

        for image in project_run.images:
            if "invalid_image_header" in image.issues:
                stats.skipped_invalid_images += 1
                project_run.logs.append(
                    OutputLog(
                        timestamp=project_run.started_at,
                        level="WARNING",
                        message="Metadata extraction skipped for invalid image.",
                        image_id=image.image_id,
                        context={"file_path": image.file_path},
                    )
                )
                continue

            try:
                metadata = self._extract_from_file(Path(image.file_path), project_run.started_at)
            except (OSError, ValueError, struct.error, zlib.error) as error:
                stats.failed_images += 1
                image.issues.append("metadata_extraction_failed")
                project_run.logs.append(
                    OutputLog(
                        timestamp=project_run.started_at,
                        level="WARNING",
                        message="Metadata extraction failed.",
                        image_id=image.image_id,
                        context={"file_path": image.file_path, "error": str(error)},
                    )
                )
                continue

            if metadata is None:
                stats.missing_metadata += 1
                continue

            image.raw_metadata = metadata
            stats.extracted_images += 1
            if metadata.png_text:
                stats.png_text_images += 1
            if metadata.exif:
                stats.exif_images += 1

        project_run.summary["metadata"] = {
            "extracted_images": stats.extracted_images,
            "png_text_images": stats.png_text_images,
            "exif_images": stats.exif_images,
            "missing_metadata": stats.missing_metadata,
            "skipped_invalid_images": stats.skipped_invalid_images,
            "failed_images": stats.failed_images,
        }
        project_run.logs.append(
            OutputLog(
                timestamp=project_run.started_at,
                level="INFO",
                message="Metadata extraction stage completed.",
                context=project_run.summary["metadata"],
            )
        )
        return project_run

    def _extract_from_file(
        self, file_path: Path, extracted_at: datetime
    ) -> RawMetadata | None:
        suffix = file_path.suffix.lower()
        if suffix == ".png":
            png_text = self._read_png_text(file_path)
            if not png_text:
                return None
            return RawMetadata(
                source_format="png_text",
                extracted_at=extracted_at,
                raw_text=dict(png_text),
                png_text=png_text,
            )

        if suffix in {".jpg", ".jpeg"}:
            exif = self._read_jpeg_exif(file_path)
            if not exif:
                return None
            return RawMetadata(
                source_format="jpeg_exif",
                extracted_at=extracted_at,
                raw_text=self._build_raw_text_from_exif(exif),
                exif=exif,
            )

        if suffix == ".webp":
            exif = self._read_webp_exif(file_path)
            if not exif:
                return None
            return RawMetadata(
                source_format="webp_exif",
                extracted_at=extracted_at,
                raw_text=self._build_raw_text_from_exif(exif),
                exif=exif,
            )

        return None

    def _read_png_text(self, file_path: Path) -> dict[str, str]:
        with file_path.open("rb") as handle:
            data = handle.read()

        if data[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Invalid PNG signature")

        offset = 8
        png_text: dict[str, str] = {}
        while offset + 8 <= len(data):
            length = struct.unpack(">I", data[offset : offset + 4])[0]
            chunk_type = data[offset + 4 : offset + 8]
            chunk_data_start = offset + 8
            chunk_data_end = chunk_data_start + length
            chunk_data = data[chunk_data_start:chunk_data_end]

            if chunk_type == b"tEXt":
                key, value = chunk_data.split(b"\x00", 1)
                png_text[key.decode("latin-1")] = value.decode("latin-1")
            elif chunk_type == b"zTXt":
                key, compressed = chunk_data.split(b"\x00", 1)
                if compressed[:1] != b"\x00":
                    raise ValueError("Unsupported PNG compression method")
                png_text[key.decode("latin-1")] = zlib.decompress(compressed[1:]).decode(
                    "utf-8", errors="replace"
                )
            elif chunk_type == b"iTXt":
                png_text.update(self._parse_itxt_chunk(chunk_data))

            offset = chunk_data_end + 4
            if chunk_type == b"IEND":
                break

        return png_text

    def _parse_itxt_chunk(self, chunk_data: bytes) -> dict[str, str]:
        keyword, remainder = chunk_data.split(b"\x00", 1)
        compression_flag = remainder[0]
        compression_method = remainder[1]
        remainder = remainder[2:]
        _, remainder = remainder.split(b"\x00", 1)
        _, text_data = remainder.split(b"\x00", 1)

        if compression_flag:
            if compression_method != 0:
                raise ValueError("Unsupported PNG iTXt compression method")
            decoded_text = zlib.decompress(text_data).decode("utf-8", errors="replace")
        else:
            decoded_text = text_data.decode("utf-8", errors="replace")

        return {keyword.decode("latin-1"): decoded_text}

    def _read_jpeg_exif(self, file_path: Path) -> dict[str, Any]:
        with file_path.open("rb") as handle:
            data = handle.read()

        if data[:2] != b"\xff\xd8":
            raise ValueError("Invalid JPEG signature")

        offset = 2
        while offset + 4 <= len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue

            marker = data[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:
                continue

            segment_length = struct.unpack(">H", data[offset : offset + 2])[0]
            segment_start = offset + 2
            segment_end = segment_start + segment_length - 2
            segment_data = data[segment_start:segment_end]

            if marker == 0xE1 and segment_data.startswith(b"Exif\x00\x00"):
                return self._parse_tiff(segment_data[6:])

            offset = segment_end

        return {}

    def _read_webp_exif(self, file_path: Path) -> dict[str, Any]:
        with file_path.open("rb") as handle:
            data = handle.read()

        if len(data) < 16 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
            raise ValueError("Invalid WEBP signature")

        offset = 12
        while offset + 8 <= len(data):
            chunk_type = data[offset : offset + 4]
            chunk_size = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
            chunk_start = offset + 8
            chunk_end = chunk_start + chunk_size
            chunk_data = data[chunk_start:chunk_end]

            if chunk_type == b"EXIF":
                if chunk_data.startswith(b"Exif\x00\x00"):
                    chunk_data = chunk_data[6:]
                return self._parse_tiff(chunk_data)

            offset = chunk_end + (chunk_size % 2)

        return {}

    def _parse_tiff(self, data: bytes) -> dict[str, Any]:
        if len(data) < 8:
            raise ValueError("Incomplete TIFF payload")

        byte_order_marker = data[:2]
        if byte_order_marker == b"II":
            byte_order = "<"
        elif byte_order_marker == b"MM":
            byte_order = ">"
        else:
            raise ValueError("Unsupported TIFF byte order")

        if struct.unpack(f"{byte_order}H", data[2:4])[0] != 42:
            raise ValueError("Invalid TIFF magic number")

        first_ifd_offset = struct.unpack(f"{byte_order}I", data[4:8])[0]
        return self._parse_ifd(data, first_ifd_offset, byte_order, visited_offsets=set())

    def _parse_ifd(
        self,
        data: bytes,
        offset: int,
        byte_order: str,
        *,
        visited_offsets: set[int],
    ) -> dict[str, Any]:
        if offset in visited_offsets or offset <= 0 or offset + 2 > len(data):
            return {}
        visited_offsets.add(offset)

        entry_count = struct.unpack(f"{byte_order}H", data[offset : offset + 2])[0]
        cursor = offset + 2
        exif: dict[str, Any] = {}

        for _ in range(entry_count):
            entry = data[cursor : cursor + 12]
            if len(entry) < 12:
                break

            tag = struct.unpack(f"{byte_order}H", entry[0:2])[0]
            data_type = struct.unpack(f"{byte_order}H", entry[2:4])[0]
            count = struct.unpack(f"{byte_order}I", entry[4:8])[0]
            value_or_offset = entry[8:12]

            value = self._read_tiff_value(data, data_type, count, value_or_offset, byte_order)
            tag_name = self._tag_name(tag)

            if tag in {0x8769, 0x8825, 0xA005} and isinstance(value, int):
                value = self._parse_ifd(
                    data,
                    value,
                    byte_order,
                    visited_offsets=visited_offsets,
                )

            exif[tag_name] = value
            cursor += 12

        next_ifd_offset_position = offset + 2 + entry_count * 12
        if next_ifd_offset_position + 4 <= len(data):
            next_ifd_offset = struct.unpack(
                f"{byte_order}I",
                data[next_ifd_offset_position : next_ifd_offset_position + 4],
            )[0]
            if next_ifd_offset:
                exif["NextIFD"] = self._parse_ifd(
                    data,
                    next_ifd_offset,
                    byte_order,
                    visited_offsets=visited_offsets,
                )

        return exif

    def _read_tiff_value(
        self,
        data: bytes,
        data_type: int,
        count: int,
        value_or_offset: bytes,
        byte_order: str,
    ) -> Any:
        type_sizes = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 7: 1, 9: 4, 10: 8}
        size = type_sizes.get(data_type)
        if size is None:
            return value_or_offset.hex()

        total_size = size * count
        if total_size <= 4:
            raw_value = value_or_offset[:total_size]
        else:
            value_offset = struct.unpack(f"{byte_order}I", value_or_offset)[0]
            raw_value = data[value_offset : value_offset + total_size]

        if data_type == 2:
            return raw_value.rstrip(b"\x00").decode("utf-8", errors="replace")
        if data_type == 3:
            values = [
                struct.unpack(f"{byte_order}H", raw_value[index : index + 2])[0]
                for index in range(0, len(raw_value), 2)
            ]
            return values[0] if count == 1 else values
        if data_type == 4:
            values = [
                struct.unpack(f"{byte_order}I", raw_value[index : index + 4])[0]
                for index in range(0, len(raw_value), 4)
            ]
            return values[0] if count == 1 else values
        if data_type == 5:
            values = []
            for index in range(0, len(raw_value), 8):
                numerator = struct.unpack(f"{byte_order}I", raw_value[index : index + 4])[0]
                denominator = struct.unpack(
                    f"{byte_order}I",
                    raw_value[index + 4 : index + 8],
                )[0]
                values.append((numerator, denominator))
            return values[0] if count == 1 else values
        if data_type == 7:
            if self._is_printable(raw_value):
                return raw_value.rstrip(b"\x00").decode("utf-8", errors="replace")
            return raw_value.hex()
        if data_type == 9:
            values = [
                struct.unpack(f"{byte_order}i", raw_value[index : index + 4])[0]
                for index in range(0, len(raw_value), 4)
            ]
            return values[0] if count == 1 else values
        if data_type == 10:
            values = []
            for index in range(0, len(raw_value), 8):
                numerator = struct.unpack(f"{byte_order}i", raw_value[index : index + 4])[0]
                denominator = struct.unpack(
                    f"{byte_order}i",
                    raw_value[index + 4 : index + 8],
                )[0]
                values.append((numerator, denominator))
            return values[0] if count == 1 else values

        return list(raw_value)

    def _build_raw_text_from_exif(self, exif: dict[str, Any]) -> dict[str, str]:
        raw_text: dict[str, str] = {}
        self._collect_text_values(exif, raw_text)
        return raw_text

    def _collect_text_values(self, source: dict[str, Any], output: dict[str, str]) -> None:
        for key, value in source.items():
            if isinstance(value, dict):
                self._collect_text_values(value, output)
            elif isinstance(value, str) and value:
                output[key] = value

    def _is_printable(self, raw_value: bytes) -> bool:
        printable = set(string.printable.encode("ascii"))
        stripped = raw_value.rstrip(b"\x00")
        return bool(stripped) and all(byte in printable for byte in stripped)

    def _tag_name(self, tag: int) -> str:
        tag_names = {
            0x010E: "ImageDescription",
            0x010F: "Make",
            0x0110: "Model",
            0x0131: "Software",
            0x0132: "DateTime",
            0x8769: "ExifIFD",
            0x8825: "GPSInfo",
            0x9003: "DateTimeOriginal",
            0x9286: "UserComment",
            0x9C9B: "XPTitle",
            0x9C9C: "XPComment",
            0x9C9D: "XPAuthor",
            0x9C9E: "XPKeywords",
            0x9C9F: "XPSubject",
            0xA001: "ColorSpace",
            0xA002: "PixelXDimension",
            0xA003: "PixelYDimension",
            0xA005: "InteropIFD",
        }
        return tag_names.get(tag, f"Tag_{tag:04X}")
