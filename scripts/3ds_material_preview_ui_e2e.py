"""Serve an isolated real-Blender fixture, then run headed browser acceptance.

Core Python: --serve --data-dir NEW --legacy-runtime-root EXISTING --port PORT.
Playwright Python: --url http://127.0.0.1:PORT --data-dir SAME --evidence-dir NEW.
No installed service, Host identity, or user scene is modified.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from typing import Any


def serve(args: argparse.Namespace) -> None:
    import uvicorn
    from PIL import Image
    from mediaforge.app import create_app
    from mediaforge.config import Settings
    from mediaforge.asset_import import import_image_asset

    spec = importlib.util.spec_from_file_location("preview_core", Path(__file__).with_name("3ds_material_preview_core_e2e.py"))
    assert spec and spec.loader
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    evidence = asyncio.run(core.run(args))
    app = create_app(Settings(data_dir=args.data_dir, blender_legacy_runtime_root=args.legacy_runtime_root))
    app.state.store.initialize()
    content = io.BytesIO()
    Image.new("RGB", (64, 64), (220, 30, 20)).save(content, format="PNG")
    red = import_image_asset(app.state.store, content.getvalue(), purpose="source")
    (args.data_dir / "ui-fixture.json").write_text(json.dumps({"scene_id": evidence["scene_id"], "red_asset_id": red.id}))
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


def browser(args: argparse.Namespace) -> None:
    from playwright.sync_api import sync_playwright
    fixture = json.loads((args.data_dir / "ui-fixture.json").read_text())
    args.evidence_dir.mkdir(exist_ok=False)
    evidence: dict[str, Any] = {"mode": "standalone source / real Blender", "page_errors": []}
    with sync_playwright() as p:
        chrome = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
                                   args=["--enable-webgl", "--ignore-gpu-blocklist"])
        try:
            page = chrome.new_page(viewport={"width": 1280, "height": 900})
            page.on("pageerror", lambda error: evidence["page_errors"].append(str(error)))
            page.goto(args.url)
            page.wait_for_selector('#app[aria-busy="false"]')
            page.locator('[data-create-media="3d"]').click()
            page.locator(f'[data-scene-id="{fixture["scene_id"]}"]').click()
            page.wait_for_function("() => state.sceneMaterialRevisionId && !state.sceneMaterialBusy")
            if not page.locator("#scene-material-object").is_visible():
                page.locator("#scene-material-title").click()

            def scene() -> dict[str, Any]:
                return page.evaluate("id => call('scenes.get', {scene_id:id})", fixture["scene_id"])

            def prepare() -> None:
                page.wait_for_function("() => !document.querySelector('#scene-material-object').disabled")
                page.locator("#scene-material-object").select_option("Cube")
                page.locator("#scene-material-image").select_option(fixture["red_asset_id"])
                page.locator("#scene-material-apply").click()
                page.wait_for_function("() => state.sceneCompareReady === 2 && state.sceneMaterialCandidate", timeout=30000)
                assert not page.locator("#scene-compare-restore").is_disabled()

            before = scene()
            prepare()
            assert scene() == before
            left = page.locator("#scene-compare-old-canvas").screenshot(path=str(args.evidence_dir / "current-blue.png"))
            right = page.locator("#scene-compare-current-canvas").screenshot(path=str(args.evidence_dir / "candidate-red.png"))
            assert hashlib.sha256(left).digest() != hashlib.sha256(right).digest()
            page.screenshot(path=str(args.evidence_dir / "comparison-ja.png"))
            assert "未保存" in page.locator("#scene-compare-current-label").inner_text()
            page.evaluate("() => {document.documentElement.lang='en'; renderSceneText();}")
            assert "not saved" in page.locator("#scene-compare-current-label").inner_text()
            page.set_viewport_size({"width": 320, "height": 740})
            assert "triangle" in page.locator("#scene-compare-old-status").inner_text().lower()
            evidence["mobile_width"] = page.evaluate("() => ({client:document.scrollingElement.clientWidth, scroll:document.scrollingElement.scrollWidth, dialogClient:document.querySelector('#scene-compare-dialog').clientWidth, dialogScroll:document.querySelector('#scene-compare-dialog').scrollWidth})")
            assert evidence["mobile_width"]["scroll"] == evidence["mobile_width"]["client"]
            assert evidence["mobile_width"]["dialogScroll"] == evidence["mobile_width"]["dialogClient"]
            page.screenshot(path=str(args.evidence_dir / "comparison-en-320.png"))
            page.locator("#scene-compare-cancel").click()
            page.wait_for_function("() => !document.querySelector('#scene-compare-dialog').open && !state.sceneMaterialCandidate")
            assert scene() == before
            page.set_viewport_size({"width": 1280, "height": 900})
            prepare()
            page.locator("#scene-compare-restore").click()
            page.wait_for_function("n => !document.querySelector('#scene-compare-dialog').open && state.sceneRevisions.length === n", arg=len(before["revisions"]) + 1, timeout=30000)
            adopted = scene()
            assert len(adopted["revisions"]) == len(before["revisions"]) + 1
            old = before["scene"]["current_revision_id"]
            page.locator(f'[data-scene-compare="{old}"]').click()
            page.wait_for_function("() => state.sceneCompareReady === 2")
            assert "Restore" in page.locator("#scene-compare-restore").inner_text()
            page.locator("#scene-compare-restore").click()
            page.wait_for_function("n => state.sceneRevisions.length === n", arg=len(before["revisions"]) + 2, timeout=30000)
            restored = scene()
            old_revision = next(r for r in before["revisions"] if r["id"] == old)
            new_revision = next(r for r in restored["revisions"] if r["id"] == restored["scene"]["current_revision_id"])
            old_bytes = page.request.get(args.url + "/api/v1/assets/" + old_revision["source_asset_id"] + "/content").body()
            new_bytes = page.request.get(args.url + "/api/v1/assets/" + new_revision["source_asset_id"] + "/content").body()
            assert old_bytes == new_bytes
            prepare()
            page.evaluate("dropSocket()")
            assert page.locator("#scene-compare-restore").is_disabled()
            assert "connection" in page.locator("#scene-compare-status").inner_text()
            page.locator("#scene-compare-cancel").click()
            assert scene() == restored
            assert not evidence["page_errors"]
            evidence.update({"prepare_discard_head_unchanged": True, "initial_revision_count": len(before["revisions"]), "adopt_revision_count": len(adopted["revisions"]),
                             "restore_revision_count": len(restored["revisions"]), "restore_blend_bytes_equal": True,
                             "connection_loss_disables_adopt": True, "ja_en_320": True,
                             "not_tested": ["installed Host", "signed release", "generated image workflow"]})
        except Exception as error:
            evidence["failure"] = type(error).__name__
            page.screenshot(path=str(args.evidence_dir / "failure.png"))
            evidence["failure_state"] = page.evaluate("() => ({ready:state.sceneCompareReady, materialRevision:state.sceneMaterialRevisionId, head:state.sceneDocument?.current_revision_id, candidate:state.sceneMaterialCandidate, status:document.querySelector('#scene-compare-status').textContent, materialStatus:document.querySelector('#scene-material-status').textContent})")
            raise
        finally:
            chrome.close()
            (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--legacy-runtime-root", type=Path)
    parser.add_argument("--port", type=int, default=9047)
    parser.add_argument("--url")
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    serve(args) if args.serve else browser(args)


if __name__ == "__main__":
    main()
