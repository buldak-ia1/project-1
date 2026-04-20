from __future__ import annotations

import shutil
import sys
import os
from pathlib import Path


def resource_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root).resolve()
    return Path(__file__).resolve().parent.parent


def workspace_root() -> Path:
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data).resolve() / "MetaSort"
        return Path.home() / "AppData" / "Local" / "MetaSort"
    return Path(__file__).resolve().parent.parent


def ensure_workspace_policy(workspace: Path, resources: Path) -> Path:
    policy_path = workspace / "config" / "classification_policy.json"
    if policy_path.exists():
        return policy_path

    bundled_policy = resources / "config" / "classification_policy.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    if bundled_policy.exists():
        shutil.copy2(bundled_policy, policy_path)
    return policy_path
