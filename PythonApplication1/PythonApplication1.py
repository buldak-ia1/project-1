
from __future__ import annotations

import json
from pathlib import Path

from metasort.pipeline import run_pipeline


def main() -> None:
    project_root = Path(__file__).resolve().parent
    project_run = run_pipeline(project_root=project_root, use_demo_input=True)
    print(json.dumps(project_run.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
