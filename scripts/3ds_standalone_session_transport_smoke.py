"""Real Chromium/HTTP transport check, not Blender recovery acceptance.

Run with a Python environment containing Playwright and its Chromium browser.
Only an ephemeral loopback HTTP recorder is started; no installed data is used.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


def main() -> None:
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<!doctype html><title>Transport recorder</title>")

        def do_POST(self) -> None:
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append({"path": self.path, "body": payload})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

    source = (Path(__file__).resolve().parents[1] / "frontend/app.js").read_text()
    function = source[source.index("async function standaloneCall"):source.index("async function call(")]
    scene_id = "scene_" + "a" * 32
    recovery_id = "working_" + "b" * 32
    session_id = "blendersession_" + "c" * 32
    cases = [
        ("start", {"scene_id": scene_id, "recovery_working_id": recovery_id}),
        ("start", {"scene_id": scene_id}),
        ("save", {"session_id": session_id}),
        ("stop", {"session_id": session_id}),
    ]
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/")
                page.add_script_tag(content=function)
                for action, params in cases:
                    result = page.evaluate(
                        "([method, params]) => standaloneCall(method, params)",
                        [f"blender.sessions.{action}", params],
                    )
                    assert result == {"action": action, **params}, result
                assert requests == [
                    {"path": "/workspace-api/blender/sessions", "body": {"action": action, **params}}
                    for action, params in cases
                ], requests
                assert not errors, errors
                print(json.dumps({"requests": requests, "browser_errors": errors,
                                  "blender_recovery": "NOT TESTED"}, indent=2))
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
