from __future__ import annotations

import csv
import copy
import json
from pathlib import Path
from typing import Any

from .category_classifier import CategoryClassifier
from .demo_setup import create_demo_input_tree
from .enums import ExecutionMode
from .feature_extractor import FeatureExtractor
from .metadata import MetadataExtractor
from .normalizer import MetadataNormalizer
from .organizer import Organizer
from .policy_manager import PolicyManager
from .report_generator import ReportGenerator
from .sample_data import build_project_run
from .scanner import ImageScanner
from .similarity_grouper import SimilarityGrouper


def run_pipeline(
    *,
    project_root: str | Path,
    source_root: str | Path | None = None,
    output_root: str | Path | None = None,
    policy_path: str | Path | None = None,
    execution_mode: str | ExecutionMode | None = None,
    use_demo_input: bool = False,
):
    project_root = Path(project_root).resolve()
    output_root = _resolve_path(project_root, output_root, default=project_root / "demo_output")
    policy_path = _resolve_path(project_root, policy_path, default=project_root / "config" / "classification_policy.json")
    source_root = _resolve_source_root(project_root, source_root, use_demo_input=use_demo_input)

    if use_demo_input:
        source_root = create_demo_input_tree(Path(source_root))
    _validate_run_paths(source_root=source_root, output_root=output_root)

    policy = PolicyManager().load_or_create(Path(policy_path))
    policy = _apply_execution_mode_override(policy, execution_mode)
    _validate_execution_mode(policy.execution_mode)
    project_run = build_project_run(source_root, output_root, policy=policy)
    ImageScanner().scan(project_run)
    MetadataExtractor().extract(project_run)
    MetadataNormalizer().normalize(project_run)
    FeatureExtractor().extract(project_run)
    CategoryClassifier().classify(project_run)
    SimilarityGrouper().group(project_run)
    Organizer().organize(project_run)
    ReportGenerator().generate(project_run)
    return project_run


def build_frontend_payload(project_run) -> dict[str, Any]:
    output_root = Path(project_run.output_root)
    manifest_path = output_root / "manifest.json"
    summary_path = output_root / "summary.json"
    report_path = output_root / "report.csv"
    run_log_path = output_root / "run.log"

    return {
        "project_run": project_run.to_dict(),
        "manifest": _load_json_file(manifest_path),
        "summary_file": _load_json_file(summary_path),
        "report_preview": _load_csv_preview(report_path, limit=20),
        "run_log_preview": _load_text_lines(run_log_path, limit=20),
    }


def load_existing_payload(output_root: str | Path) -> dict[str, Any]:
    output_root = Path(output_root)
    summary_path = output_root / "summary.json"
    manifest_path = output_root / "manifest.json"
    report_path = output_root / "report.csv"
    run_log_path = output_root / "run.log"

    return {
        "project_run": None,
        "manifest": _load_json_file(manifest_path),
        "summary_file": _load_json_file(summary_path),
        "report_preview": _load_csv_preview(report_path, limit=20),
        "run_log_preview": _load_text_lines(run_log_path, limit=20),
    }


def _resolve_path(project_root: Path, raw_path: str | Path | None, *, default: Path) -> Path:
    path = Path(raw_path) if raw_path else default
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _resolve_source_root(
    project_root: Path,
    raw_path: str | Path | None,
    *,
    use_demo_input: bool,
) -> Path:
    if use_demo_input:
        return (project_root / "demo_input").resolve()
    if raw_path is None or not str(raw_path).strip():
        raise ValueError("Source Root is required unless demo input is enabled.")
    return _resolve_path(project_root, raw_path, default=project_root / "demo_input")


def _apply_execution_mode_override(policy, execution_mode: str | ExecutionMode | None):
    if execution_mode is None:
        return policy
    overridden_policy = copy.deepcopy(policy)
    overridden_policy.execution_mode = (
        execution_mode
        if isinstance(execution_mode, ExecutionMode)
        else ExecutionMode(execution_mode)
    )
    return overridden_policy


def _validate_execution_mode(execution_mode: ExecutionMode) -> None:
    if execution_mode == ExecutionMode.MOVE:
        raise ValueError("Move mode is disabled to protect source and previously sorted files. Use analyze_only or copy.")


def _validate_run_paths(*, source_root: Path, output_root: Path) -> None:
    if not source_root.exists():
        raise ValueError(f"Source Root does not exist: {source_root}")
    if not source_root.is_dir():
        raise ValueError(f"Source Root is not a directory: {source_root}")
    if source_root == output_root:
        raise ValueError("Source Root and Output Root must be different directories.")
    if _is_same_or_nested(source_root, output_root):
        raise ValueError("Output Root cannot be inside Source Root.")
    if _is_same_or_nested(output_root, source_root):
        raise ValueError("Source Root cannot be inside Output Root.")


def _is_same_or_nested(parent: Path, child: Path) -> bool:
    return parent == child or parent in child.parents


def _load_json_file(file_path: Path) -> dict[str, Any] | None:
    if not file_path.exists():
        return None
    with file_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_text_lines(file_path: Path, *, limit: int) -> list[str]:
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8") as handle:
        lines = [line.rstrip("\n") for line in handle.readlines()]
    return lines[-limit:]


def _load_csv_preview(file_path: Path, *, limit: int) -> list[dict[str, str]]:
    if not file_path.exists():
        return []
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for index, row in enumerate(reader):
            if index >= limit:
                break
            rows.append({key: value for key, value in row.items()})
        return rows
