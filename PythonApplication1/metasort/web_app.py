from __future__ import annotations

import json
from functools import partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .pipeline import build_frontend_payload, load_existing_payload, run_pipeline


def run_web_server(
    project_root: str | Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    resource_root: str | Path | None = None,
) -> None:
    project_root = Path(project_root).resolve()
    resource_root = Path(resource_root).resolve() if resource_root else project_root
    state = {"latest_payload": None}
    handler = partial(
        MetaSortRequestHandler,
        project_root=project_root,
        resource_root=resource_root,
        state=state,
    )
    server = ThreadingHTTPServer((host, port), handler)
    print(f"MetaSort web UI running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


class MetaSortRequestHandler(BaseHTTPRequestHandler):
    def __init__(
        self,
        *args,
        project_root: Path,
        resource_root: Path,
        state: dict[str, Any],
        **kwargs,
    ) -> None:
        self.project_root = project_root
        self.state = state
        self.frontend_root = resource_root / "frontend"
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._serve_file(self.frontend_root / "index.html", "text/html; charset=utf-8")
            return
        if path == "/assets/styles.css":
            self._serve_file(self.frontend_root / "styles.css", "text/css; charset=utf-8")
            return
        if path == "/assets/app.js":
            self._serve_file(self.frontend_root / "app.js", "application/javascript; charset=utf-8")
            return
        if path == "/api/state":
            payload = self.state.get("latest_payload")
            if payload is None:
                payload = load_existing_payload(self.project_root / "demo_output")
            self._json_response(payload)
            return
        self._json_response({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self._json_response({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            request_payload = self._read_json_body()
            source_root = request_payload.get("source_root")
            output_root = request_payload.get("output_root") or self.project_root / "demo_output"
            policy_path = request_payload.get("policy_path") or self.project_root / "config" / "classification_policy.json"
            execution_mode = request_payload.get("execution_mode")
            use_demo_input = bool(request_payload.get("use_demo_input", False))
            project_run = run_pipeline(
                project_root=self.project_root,
                source_root=source_root,
                output_root=output_root,
                policy_path=policy_path,
                execution_mode=execution_mode,
                use_demo_input=use_demo_input,
            )
            payload = build_frontend_payload(project_run)
            self.state["latest_payload"] = payload
            self._json_response(payload)
        except ValueError as error:
            self._json_response(
                {
                    "error": "invalid_request",
                    "message": str(error),
                },
                status=HTTPStatus.BAD_REQUEST,
            )
        except Exception as error:  # noqa: BLE001
            self._json_response(
                {
                    "error": "run_failed",
                    "message": str(error),
                },
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        if not raw_body:
            return {}
        return json.loads(raw_body.decode("utf-8"))

    def _serve_file(self, file_path: Path, content_type: str) -> None:
        if not file_path.exists():
            self._json_response({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
            return
        data = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_response(self, payload: dict[str, Any] | list[Any] | None, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
