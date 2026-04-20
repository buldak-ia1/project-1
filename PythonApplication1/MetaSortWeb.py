from __future__ import annotations

from pathlib import Path

from metasort.web_app import run_web_server


def main() -> None:
    run_web_server(Path(__file__).resolve().parent)


if __name__ == "__main__":
    main()
