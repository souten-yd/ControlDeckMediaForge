#!/usr/bin/env python3
"""Real-browser acceptance for UX2 M2 Model Management.

The fixture uses the real Media Forge core, private WebSocket transport,
durable SQLite operations, installer, verifier, and atomic managed store. Model
bytes are bounded test data; the retained 15.98 GB development model is never
removed by this script.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

REVISION = "d" * 40
EXTERNAL_WEIGHT = b"external-model"
MANAGED_WEIGHT = b"m" * (32 * 1024 * 1024)
CONFIG = b'{"model_type":"fixture"}'


class SlowStream(httpx.AsyncByteStream):
    def __init__(self, content: bytes):
        self.content = content

    async def __aiter__(self):
        size = 8 * 1024 * 1024
        for offset in range(0, len(self.content), size):
            await asyncio.sleep(2.0)
            yield self.content[offset:offset + size]


def model_entry(model_id: str, weight: bytes) -> dict[str, object]:
    return {
        "model_id": model_id,
        "family": "fixture",
        "version": "1",
        "revision": REVISION,
        "weights_hash": "sha256:" + hashlib.sha256(weight).hexdigest(),
        "license": "Apache-2.0",
        "runtime_adapter": "fixture",
        "capabilities": ["image.text_to_image"],
        "hardware_backends": ["rocm"],
        "state": "available",
        "policy_rank": {"auto": 1},
        "measurements": {
            "resident_vram_bytes": 1024,
            "execution_peak_vram_bytes": 2048,
            "cold_load_peak_vram_bytes": 3072,
            "headroom_vram_bytes": 1024,
            "measured_runtime_sec": 1,
        },
        "required_files": ["config.json"],
        "weights": [{
            "path": "model.safetensors",
            "size_bytes": len(weight),
            "sha256": hashlib.sha256(weight).hexdigest(),
        }],
    }


def catalog_entry(model_id: str, name: str, weight: bytes) -> dict[str, object]:
    return {
        "model_id": model_id,
        "display_name": name,
        "domains": ["general"],
        "media_types": ["image"],
        "description": "Model Management browser fixture.",
        "approx_download_bytes": len(CONFIG) + len(weight),
        "source": {"kind": "huggingface", "repo_id": model_id, "revision": REVISION},
        "ownership": "managed",
        "supports_lora": False,
        "max_references": 0,
        "recommended_profiles": [],
        "gated": False,
        "license_notice": "Apache-2.0",
    }


def install_external(root: Path) -> None:
    repo = root / "hub/models--owner--external"
    blobs = repo / "blobs"
    snapshot = repo / "snapshots" / REVISION
    blobs.mkdir(parents=True)
    snapshot.mkdir(parents=True)
    for relative, content in (("config.json", CONFIG), ("model.safetensors", EXTERNAL_WEIGHT)):
        digest = hashlib.sha256(content).hexdigest()
        blob = blobs / digest
        blob.write_bytes(content)
        link = snapshot / relative
        link.symlink_to(os.path.relpath(blob, link.parent))


def fixture_app(root: Path) -> FastAPI:
    from mediaforge.app import create_app
    from mediaforge.config import Settings
    from mediaforge.host.client import ControlDeckHostClient

    runtime = root / "models.json"
    catalog = root / "catalog.json"
    runtime.write_text(json.dumps({
        "schema_version": "1.0",
        "models": [
            model_entry("owner/external", EXTERNAL_WEIGHT),
            model_entry("owner/managed", MANAGED_WEIGHT),
        ],
    }), encoding="utf-8")
    catalog.write_text(json.dumps({
        "schema_version": "1.0",
        "models": [
            catalog_entry("owner/external", "共有モデル", EXTERNAL_WEIGHT),
            catalog_entry("owner/managed", "おすすめモデル", MANAGED_WEIGHT),
        ],
    }), encoding="utf-8")
    external = root / "external"
    managed = root / "managed"
    install_external(external)

    host_app = FastAPI()

    @host_app.post("/api/v1/addon-runtime/token/introspect")
    async def introspect() -> dict[str, object]:
        return {
            "active": True,
            "addon_id": "media-forge",
            "subject": "user:model-management-e2e",
            "expires_at": int(time.time()) + 300,
            "granted_capabilities": [],
        }

    def download(request: httpx.Request) -> httpx.Response:
        content = CONFIG if request.url.path.endswith("/config.json") else MANAGED_WEIGHT
        range_value = request.headers.get("range", "")
        offset = int(range_value.removeprefix("bytes=").removesuffix("-")) if range_value else 0
        return httpx.Response(
            206 if range_value else 200,
            stream=SlowStream(content[offset:]),
            request=request,
        )

    media = create_app(
        Settings(
            data_dir=root / "data",
            control_deck_url="https://control-deck.test",
            model_manifest=runtime,
            model_catalog_manifest=catalog,
            model_store_root=managed,
            hf_home=external,
        ),
        host_client=ControlDeckHostClient(
            "https://control-deck.test", transport=httpx.ASGITransport(app=host_app)
        ),
        model_download_origin="https://models.invalid",
        model_download_transport=httpx.MockTransport(download),
    )
    outer = FastAPI(lifespan=media.router.lifespan_context)

    @outer.middleware("http")
    async def inject_http_identity(request: Request, call_next):
        if request.url.path.startswith("/media"):
            request.scope["headers"] = [
                *request.scope["headers"],
                (b"authorization", b"Bearer valid-user"),
                (b"x-control-deck-addon-id", b"media-forge"),
            ]
        return await call_next(request)

    class WebSocketIdentity:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "websocket":
                scope = dict(scope)
                requested = next((
                    value.decode() for name, value in scope["headers"]
                    if name.lower() == b"sec-websocket-protocol"
                ), "")
                scope["headers"] = [
                    *scope["headers"],
                    (b"authorization", b"Bearer valid-user"),
                    (b"x-control-deck-addon-id", b"media-forge"),
                ]
                async def accept_protocol(message):
                    if message["type"] == "websocket.accept" and requested:
                        message = {**message, "subprotocol": requested.split(",", 1)[0].strip()}
                    await send(message)

                await self.app(scope, receive, accept_protocol)
                return
            await self.app(scope, receive, send)

    @outer.get("/")
    async def wrapper() -> HTMLResponse:
        return HTMLResponse("""<!doctype html><meta charset=utf-8>
<style>html,body,iframe{width:100%;height:100%;margin:0;border:0}</style>
<iframe id=workspace src=/media/></iframe>
<script>
window.addEventListener('message', event => {
  if (event.data?.type !== 'control-deck-addon.connect') return;
  const channel = new MessageChannel();
  channel.port1.onmessage = message => {
    const request = message.data;
    if (!request?.id) return;
    channel.port1.postMessage({id: request.id, ok: true, result: {}});
  };
  event.source.postMessage({type:'control-deck-host.connected', session_nonce:'valid-user',
    theme:{bg:'#f4f7f6',surface:'#ffffff',text:'#17201e',border:'#cad5d2',muted:'#64736f',
      accent:'#167c68',color_scheme:'light',radius_md:10,safe_area:{top:0,right:0,bottom:0,left:0}}},
    location.origin,[channel.port2]);
});
</script>""")

    outer.mount("/media", WebSocketIdentity(media))
    return outer


def serve_fixture(root: Path, port: int) -> None:
    uvicorn.run(fixture_app(root), host="127.0.0.1", port=port, log_level="warning")


def wait_server(url: str) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=1).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.1)
    raise RuntimeError("fixture server did not start")


def run_browser(url: str, evidence: Path) -> dict[str, object]:
    from playwright.sync_api import sync_playwright

    evidence.mkdir(parents=True, exist_ok=True)
    observations: dict[str, object] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        console_errors: list[str] = []
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("pageerror", lambda error: console_errors.append(str(error)))
        page.goto(url)
        frame = page.frame_locator("#workspace")
        frame.locator('#app[aria-busy="false"]').wait_for(timeout=15_000)
        frame.locator("#nav-settings").click()
        frame.locator("#model-catalog .model-card").first.wait_for()
        assert frame.locator("#advanced-models").count() == 0
        assert frame.locator("#model-catalog .model-card").count() == 1
        assert "共有モデル" in frame.locator("#model-catalog").inner_text()
        shared_button = frame.locator("#model-catalog button", has_text="共有モデル")
        assert shared_button.count() == 1 and shared_button.is_disabled()

        frame.locator('[data-model-filter="all"]').click()
        assert frame.locator("#model-catalog .model-card").count() == 2
        started = time.perf_counter()
        frame.locator('.model-card', has_text="おすすめモデル").locator("[data-install-model]").click()
        frame.locator("#model-catalog progress").wait_for(timeout=5_000)
        observations["download_taps"] = 1
        frame.locator("#nav-create").click()
        assert frame.locator("#model-mini-progress").is_visible()

        page.reload()
        frame = page.frame_locator("#workspace")
        frame.locator('#app[aria-busy="false"]').wait_for(timeout=15_000)
        frame.locator("#model-mini-progress").wait_for(timeout=3_000)
        observations["reload_preserved_operation"] = True
        frame.locator("#nav-settings").click()
        frame.locator('[data-model-filter="all"]').click()
        frame.locator('.model-card', has_text="おすすめモデル").locator("[data-remove-model]").wait_for(timeout=15_000)
        observations["install_wall_sec"] = round(time.perf_counter() - started, 3)

        frame.locator("#mode-advanced").click()
        frame.locator("#advanced-models").wait_for()
        assert "model_id: owner/managed" in frame.locator("#advanced-models").inner_text()
        frame.locator("#mode-simple").click()
        assert frame.locator("#advanced-models").count() == 0

        frame.locator('.model-card', has_text="おすすめモデル").locator("[data-remove-model]").click()
        dialog = frame.locator("#model-remove-dialog")
        assert dialog.is_visible()
        assert frame.locator("#model-remove-dialog").count() == 1
        assert "32.0 MB" in frame.locator("#model-remove-detail").inner_text()
        frame.locator("#model-remove-confirm").click()
        frame.locator('.model-card', has_text="おすすめモデル").locator("[data-install-model]").wait_for(timeout=10_000)
        observations["remove_confirmations"] = 1

        for width, height in ((390, 844), (320, 640)):
            page.set_viewport_size({"width": width, "height": height})
            frame.locator("#nav-settings").click()
            overflow = frame.locator("html").evaluate(
                "node => node.scrollWidth - node.clientWidth"
            )
            assert overflow <= 0
            observations[f"overflow_{width}px"] = overflow
            page.screenshot(path=str(evidence / f"model-management-{width}.png"), full_page=True)

        page.set_viewport_size({"width": 1280, "height": 800})
        page.screenshot(path=str(evidence / "model-management-desktop.png"), full_page=True)
        observations["console_page_errors"] = console_errors
        assert not console_errors
        browser.close()
    (evidence / "observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return observations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve-fixture", action="store_true")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--port", type=int, default=9141)
    parser.add_argument("--evidence-dir", type=Path, default=Path("/tmp/mediaforge-m2-evidence"))
    args = parser.parse_args()
    if args.serve_fixture:
        if args.root is None:
            parser.error("--root is required with --serve-fixture")
        serve_fixture(args.root, args.port)
        return 0
    with tempfile.TemporaryDirectory(prefix="mediaforge-m2-") as temporary:
        root = Path(temporary)
        server_python = ROOT / ".venv/bin/python"
        process = subprocess.Popen([
            str(server_python), str(Path(__file__).resolve()), "--serve-fixture",
            "--root", str(root), "--port", str(args.port),
        ])
        try:
            url = f"http://127.0.0.1:{args.port}/"
            wait_server(url)
            print(json.dumps(run_browser(url, args.evidence_dir), ensure_ascii=False, indent=2))
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
