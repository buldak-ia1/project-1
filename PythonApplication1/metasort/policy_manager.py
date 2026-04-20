from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .enums import (
    ClassificationCriterion,
    ExecutionMode,
    MetadataMissingHandling,
    UnclassifiedHandling,
)
from .models import ClassificationPolicy, PolicyAxis
from .sample_data import build_default_policy


class PolicyManager:
    def load_or_create(self, policy_path: Path) -> ClassificationPolicy:
        if not policy_path.exists():
            policy = build_default_policy()
            self.save(policy_path, policy)
            return policy
        return self.load(policy_path)

    def load(self, policy_path: Path) -> ClassificationPolicy:
        with policy_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return self._policy_from_dict(payload)

    def save(self, policy_path: Path, policy: ClassificationPolicy) -> None:
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        with policy_path.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(policy), handle, indent=2, ensure_ascii=False)

    def to_dict(self, policy: ClassificationPolicy) -> dict[str, Any]:
        return {
            "policy_id": policy.policy_id,
            "name": policy.name,
            "description": policy.description,
            "execution_mode": policy.execution_mode.value,
            "include_subdirectories": policy.include_subdirectories,
            "similarity_threshold": policy.similarity_threshold,
            "nsfw_threshold": policy.nsfw_threshold,
            "unclassified_handling": policy.unclassified_handling.value,
            "metadata_missing_handling": policy.metadata_missing_handling.value,
            "axes": [
                {
                    "priority": axis.priority,
                    "criterion": axis.criterion.value,
                    "display_name": axis.display_name,
                    "unknown_label": axis.unknown_label,
                    "enabled": axis.enabled,
                }
                for axis in policy.axes
            ],
            "extra_rules": policy.extra_rules,
        }

    def _policy_from_dict(self, payload: dict[str, Any]) -> ClassificationPolicy:
        axes = [self._axis_from_dict(item) for item in payload.get("axes", [])]
        self._validate_axes(axes)

        similarity_threshold = float(payload.get("similarity_threshold", 10.0))
        nsfw_threshold = float(payload.get("nsfw_threshold", 0.65))
        if similarity_threshold < 0:
            raise ValueError("similarity_threshold must be non-negative")
        if not 0 <= nsfw_threshold <= 1:
            raise ValueError("nsfw_threshold must be between 0 and 1")

        return ClassificationPolicy(
            policy_id=str(payload.get("policy_id") or "policy-default"),
            name=str(payload.get("name") or "Unnamed Policy"),
            description=str(payload.get("description") or ""),
            execution_mode=self._load_enum(
                ExecutionMode,
                payload.get("execution_mode"),
                ExecutionMode.COPY,
            ),
            include_subdirectories=bool(payload.get("include_subdirectories", True)),
            similarity_threshold=similarity_threshold,
            nsfw_threshold=nsfw_threshold,
            unclassified_handling=self._load_enum(
                UnclassifiedHandling,
                payload.get("unclassified_handling"),
                UnclassifiedHandling.PLACE_IN_UNCLASSIFIED,
            ),
            metadata_missing_handling=self._load_enum(
                MetadataMissingHandling,
                payload.get("metadata_missing_handling"),
                MetadataMissingHandling.VISUAL_ONLY,
            ),
            axes=axes,
            extra_rules=dict(payload.get("extra_rules") or {}),
        )

    def _axis_from_dict(self, payload: dict[str, Any]) -> PolicyAxis:
        return PolicyAxis(
            priority=int(payload.get("priority", 0)),
            criterion=self._load_enum(
                ClassificationCriterion,
                payload.get("criterion"),
                ClassificationCriterion.NONE,
            ),
            display_name=str(payload.get("display_name") or "Axis"),
            unknown_label=str(payload.get("unknown_label") or "Unknown"),
            enabled=bool(payload.get("enabled", True)),
        )

    def _validate_axes(self, axes: list[PolicyAxis]) -> None:
        enabled_axes = sorted(
            (axis for axis in axes if axis.enabled),
            key=lambda axis: axis.priority,
        )
        if not enabled_axes:
            raise ValueError("At least one enabled axis is required")
        if len(enabled_axes) > 3:
            raise ValueError("A maximum of three enabled axes is supported")

        priorities = [axis.priority for axis in enabled_axes]
        if priorities != list(range(1, len(enabled_axes) + 1)):
            raise ValueError("Enabled axis priorities must be consecutive starting at 1")

        criteria = [
            axis.criterion
            for axis in enabled_axes
            if axis.criterion != ClassificationCriterion.NONE
        ]
        if len(criteria) != len(set(criteria)):
            raise ValueError("Enabled axes must not repeat the same criterion")

    def _load_enum(self, enum_type: type, raw_value: Any, default: Any) -> Any:
        if raw_value is None:
            return default
        try:
            return enum_type(raw_value)
        except ValueError as error:
            raise ValueError(f"Invalid value '{raw_value}' for {enum_type.__name__}") from error
