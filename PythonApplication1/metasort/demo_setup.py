from __future__ import annotations

import base64
import json
import shutil
import struct
import zlib
from pathlib import Path

PNG_PIXEL_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7/"
    "X1sAAAAASUVORK5CYII="
)


def create_demo_input_tree(root: Path) -> Path:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    flat_root = root / "batch_a"
    nested_root = root / "batch_a" / "variants"
    broken_root = root / "batch_b"
    prompt_family_root = root / "batch_c"

    flat_root.mkdir(parents=True, exist_ok=True)
    nested_root.mkdir(parents=True, exist_ok=True)
    broken_root.mkdir(parents=True, exist_ok=True)
    prompt_family_root.mkdir(parents=True, exist_ok=True)

    _write_png_with_text(
        flat_root / "miku_001.png",
        {
            "parameters": (
                "masterpiece, best quality, anime illustration, hatsune miku, city lights, artist:null\n"
                "Negative prompt: low quality, blurry\n"
                "Steps: 28, Sampler: k_euler, CFG scale: 6.5, Seed: 123456789, "
                "Model: nai-diffusion-4"
            ),
            "Software": "NovelAI",
            "Comment": json.dumps(
                {
                    "v4_prompt": {
                        "caption": {
                            "base_caption": "anime illustration, city lights",
                            "char_captions": [
                                {"char_caption": "hatsune miku, aqua twin tails, idol outfit"}
                            ],
                        }
                    }
                }
            ),
        },
    )
    _write_png_with_text(
        nested_root / "miku_001.png",
        {
            "parameters": (
                "best quality, anime illustration, hatsune miku, sunset city lights, variation, artist:null\n"
                "Negative prompt: watermark, lowres\n"
                "Steps: 24, Sampler: k_euler_a, CFG scale: 5.5, Seed: 987654321, "
                "Model: nai-diffusion-4"
            ),
            "Comment": json.dumps(
                {
                    "seed": 987654321,
                    "sampler": "k_euler_a",
                    "v4_prompt": {
                        "caption": {
                            "base_caption": "anime illustration, sunset city lights",
                            "char_captions": [
                                {"char_caption": "hatsune miku, aqua twintails, idol costume"}
                            ],
                        }
                    },
                }
            ),
        },
    )
    _write_png_with_text(
        prompt_family_root / "unknown_hero_001.png",
        {
            "parameters": (
                "best quality, anime watercolor, silver haired knight, black armor, crimson eyes, artist:null\n"
                "Negative prompt: watermark, lowres\n"
                "Steps: 22, Sampler: k_euler, CFG scale: 5.0, Seed: 222222222, "
                "Model: nai-diffusion-4"
            ),
            "Software": "NovelAI",
            "Comment": json.dumps(
                {
                    "v4_prompt": {
                        "caption": {
                            "base_caption": "anime watercolor, dramatic lighting",
                            "char_captions": [
                                {"char_caption": "silver haired knight, black armor, crimson eyes"}
                            ],
                        }
                    }
                }
            ),
        },
    )
    _write_png_with_text(
        prompt_family_root / "unknown_hero_002.png",
        {
            "parameters": (
                "masterpiece, anime watercolor, silver haired knight, black armor, red eyes, dramatic pose, artist:null\n"
                "Negative prompt: blurry, lowres\n"
                "Steps: 23, Sampler: k_euler, CFG scale: 5.2, Seed: 333333333, "
                "Model: nai-diffusion-4"
            ),
            "Software": "NovelAI",
            "Comment": json.dumps(
                {
                    "v4_prompt": {
                        "caption": {
                            "base_caption": "anime watercolor, dramatic pose",
                            "char_captions": [
                                {"char_caption": "silver haired knight, black armor, red eyes"}
                            ],
                        }
                    }
                }
            ),
        },
    )
    (flat_root / "notes.txt").write_text("This is not an image file.", encoding="utf-8")
    (broken_root / "broken.webp").write_bytes(b"not-a-real-webp")
    return root


def _write_binary_file(file_path: Path, base64_text: str) -> None:
    file_path.write_bytes(base64.b64decode(base64_text))


def _write_png_with_text(file_path: Path, text_chunks: dict[str, str]) -> None:
    png_bytes = base64.b64decode(PNG_PIXEL_BASE64)
    signature = png_bytes[:8]
    chunks = _parse_png_chunks(png_bytes[8:])
    output = bytearray(signature)

    for chunk_type, chunk_data in chunks:
        if chunk_type == b"IEND":
            for key, value in text_chunks.items():
                output.extend(_build_png_chunk(b"tEXt", _encode_text_chunk(key, value)))
        output.extend(_build_png_chunk(chunk_type, chunk_data))

    file_path.write_bytes(bytes(output))


def _parse_png_chunks(chunk_stream: bytes) -> list[tuple[bytes, bytes]]:
    chunks: list[tuple[bytes, bytes]] = []
    offset = 0
    while offset + 8 <= len(chunk_stream):
        length = struct.unpack(">I", chunk_stream[offset : offset + 4])[0]
        chunk_type = chunk_stream[offset + 4 : offset + 8]
        chunk_data_start = offset + 8
        chunk_data_end = chunk_data_start + length
        chunk_data = chunk_stream[chunk_data_start:chunk_data_end]
        chunks.append((chunk_type, chunk_data))
        offset = chunk_data_end + 4
        if chunk_type == b"IEND":
            break
    return chunks


def _build_png_chunk(chunk_type: bytes, chunk_data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
    return (
        struct.pack(">I", len(chunk_data))
        + chunk_type
        + chunk_data
        + struct.pack(">I", crc)
    )


def _encode_text_chunk(key: str, value: str) -> bytes:
    return key.encode("latin-1") + b"\x00" + value.encode("latin-1")
