from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .enums import (
    ClassificationCriterion,
    ExecutionMode,
    GroupType,
    MetadataMissingHandling,
    RunStatus,
    UnclassifiedHandling,
)


def _serialize(value: Any) -> Any:
    if isinstance(value, EnumLike):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {
            field_info.name: _serialize(getattr(value, field_info.name))
            for field_info in fields(value)
        }
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


class EnumLike:
    value: str


@dataclass(slots=True)
class PolicyAxis:
    priority: int
    criterion: ClassificationCriterion
    display_name: str
    unknown_label: str = "Unknown"
    enabled: bool = True


@dataclass(slots=True)
class ClassificationPolicy:
    policy_id: str
    name: str
    description: str
    execution_mode: ExecutionMode
    include_subdirectories: bool = True
    similarity_threshold: float = 10.0
    nsfw_threshold: float = 0.65
    unclassified_handling: UnclassifiedHandling = (
        UnclassifiedHandling.PLACE_IN_UNCLASSIFIED
    )
    metadata_missing_handling: MetadataMissingHandling = (
        MetadataMissingHandling.VISUAL_ONLY
    )
    axes: list[PolicyAxis] = field(default_factory=list)
    extra_rules: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(slots=True)
class RawMetadata:
    source_format: str
    extracted_at: datetime
    raw_text: dict[str, str] = field(default_factory=dict)
    exif: dict[str, Any] = field(default_factory=dict)
    png_text: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class NormalizedMetadata:
    prompt: str | None = None
    negative_prompt: str | None = None
    character_prompts: list[str] = field(default_factory=list)
    seed: int | None = None
    sampler: str | None = None
    steps: int | None = None
    cfg_scale: float | None = None
    model: str | None = None
    software: str | None = None
    artist: str | None = None
    width: int | None = None
    height: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ImageFeature:
    perceptual_hash: str | None = None
    difference_hash: str | None = None
    embedding_vector: list[float] = field(default_factory=list)
    aspect_ratio: float | None = None
    dominant_tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ImageCategoryResult:
    axis_priority: int
    criterion: ClassificationCriterion
    category_key: str
    category_label: str
    confidence: float | None = None
    reason: str | None = None


@dataclass(slots=True)
class ImageFile:
    image_id: str
    file_name: str
    file_path: str
    extension: str
    file_size_bytes: int
    width: int | None = None
    height: int | None = None
    checksum_sha256: str | None = None
    raw_metadata: RawMetadata | None = None
    normalized_metadata: NormalizedMetadata | None = None
    feature: ImageFeature | None = None
    category_results: list[ImageCategoryResult] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GroupMember:
    image_id: str
    relation_score: float | None = None
    is_representative: bool = False


@dataclass(slots=True)
class ImageGroup:
    group_id: str
    category_path: list[str]
    group_type: GroupType
    representative_image_id: str | None = None
    members: list[GroupMember] = field(default_factory=list)


@dataclass(slots=True)
class OutputLog:
    timestamp: datetime
    level: str
    message: str
    image_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ProjectRun:
    run_id: str
    project_name: str
    source_root: str
    output_root: str
    started_at: datetime
    status: RunStatus
    policy: ClassificationPolicy
    images: list[ImageFile] = field(default_factory=list)
    groups: list[ImageGroup] = field(default_factory=list)
    logs: list[OutputLog] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)
