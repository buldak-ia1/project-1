from __future__ import annotations

import os
import socket
import threading
import time
import webbrowser

from metasort.runtime_paths import ensure_workspace_policy, resource_root, workspace_root
from metasort.web_app import run_web_server


def main() -> None:
    workspace = workspace_root()
    resources = resource_root()
    ensure_workspace_policy(workspace, resources)

    port = _select_port(int(os.environ.get("METASORT_PORT", "8765")))
    url = f"http://127.0.0.1:{port}"
    print(f"MetaSort workspace: {workspace}")
    print(f"MetaSort web UI: {url}")
    print("Close this window or press Ctrl+C to stop MetaSort.")
    if os.environ.get("METASORT_NO_BROWSER") != "1":
        threading.Thread(target=_open_browser, args=(url,), daemon=True).start()
    run_web_server(workspace, port=port, resource_root=resources)


def _open_browser(url: str) -> None:
    time.sleep(1.0)
    webbrowser.open(url, new=1)


def _select_port(preferred_port: int) -> int:
    if _is_port_available(preferred_port):
        return preferred_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.bind(("127.0.0.1", 0))
        return int(handle.getsockname()[1])


def _is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        try:
            handle.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


if __name__ == "__main__":
    main()
