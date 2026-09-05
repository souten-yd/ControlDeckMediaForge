from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

from scripts import blender_manager_cli


class RuntimeHandler(BaseHTTPRequestHandler):
    actions: list[dict] = []

    def log_message(self, _format: str, *_args) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        assert self.path == "/workspace-api/blender/runtime"
        self._send({
            "operations": [{
                "id": "blenderop_cli",
                "state": "ready",
                "error_code": None,
                "error_message": None,
            }],
        })

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        assert self.path == "/workspace-api/blender/runtime/operations"
        length = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(length))
        self.actions.append(payload)
        if payload["action"] == "remove_preview":
            self._send({
                "runtime_id": payload["runtime_id"],
                "version": "4.5.9",
                "reclaimable_bytes": 123,
                "live_reference_count": 0,
                "project_reference_count": 0,
                "blocked_reasons": [],
                "can_remove": True,
                "confirmation_fingerprint": "a" * 64,
            })
        else:
            self._send({"id": "blenderop_cli", "state": "queued"})

    def _send(self, value: dict) -> None:
        content = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def server_url() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), RuntimeHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def test_cli_update_uses_server_orchestrator_and_waits_for_terminal(capsys) -> None:
    RuntimeHandler.actions = []
    server, base_url = server_url()
    try:
        assert blender_manager_cli.main(["--base-url", base_url, "update"]) == 0
    finally:
        server.shutdown()
    assert RuntimeHandler.actions == [{"action": "update"}]
    assert '"state": "ready"' in capsys.readouterr().out


def test_cli_remove_prints_preview_and_sends_its_exact_fingerprint(capsys) -> None:
    RuntimeHandler.actions = []
    server, base_url = server_url()
    try:
        assert blender_manager_cli.main([
            "--base-url", base_url, "remove", "blender-4.5.9-linux-x64", "--yes",
        ]) == 0
    finally:
        server.shutdown()
    assert RuntimeHandler.actions == [
        {"action": "remove_preview", "runtime_id": "blender-4.5.9-linux-x64"},
        {
            "action": "remove",
            "runtime_id": "blender-4.5.9-linux-x64",
            "confirmation_fingerprint": "a" * 64,
        },
    ]
    assert '"can_remove": true' in capsys.readouterr().out


def test_cli_rejects_non_loopback_origin(capsys) -> None:
    assert blender_manager_cli.main(["--base-url", "https://example.com", "status"]) == 1
    assert "plain loopback HTTP origin" in capsys.readouterr().err
