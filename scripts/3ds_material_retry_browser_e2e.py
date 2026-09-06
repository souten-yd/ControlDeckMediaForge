"""Isolated real HTTP/WebSocket/Blender material failure and UI retry.

Serve with MediaForge Python; browser with existing Playwright diagnostic Python.
Only the first worker target is fault-injected, not requests or browser responses.
No installed service, runtime files, global settings or existing scene changes.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any


def serve(args: argparse.Namespace) -> None:
    import uvicorn
    from mediaforge.app import create_app
    from mediaforge.asset_import import import_image_asset
    from mediaforge.config import Settings

    args.data_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    app = create_app(Settings(data_dir=args.data_dir, blender_legacy_runtime_root=args.runtime_root))
    store, workspace = app.state.store, app.state.scene_workspace
    store.initialize()
    workspace.initialize()
    assert workspace.resolver.register_legacy()
    content = args.blend.read_bytes()
    upload = workspace.begin_upload("local", size=len(content), sha256=hashlib.sha256(content).hexdigest(),
                                    name="Material browser retry acceptance")
    for offset in range(0, len(content), 512 * 1024):
        chunk = content[offset:offset + 512 * 1024]
        workspace.append_upload("local", upload["upload_id"], offset, chunk, hashlib.sha256(chunk).hexdigest())
    scene = asyncio.run(workspace.commit_upload("local", upload["upload_id"]))
    texture = import_image_asset(store, args.image.read_bytes(), purpose="source")
    original = workspace._material_operation
    calls = 0

    async def fail_once(*values: Any, **kwargs: Any) -> Any:
        nonlocal calls
        if kwargs.get("action") == "apply":
            calls += 1
            if calls == 1:
                kwargs["binding"] = kwargs["binding"].model_copy(update={"object_name": "missing-fault-target"})
        return await original(*values, **kwargs)

    workspace._material_operation = fail_once
    (args.data_dir / "fixture.json").write_text(json.dumps({"scene_id": scene["scene"]["id"],
        "image_id": texture.id, "source": scene["revision"]["source_asset_id"],
        "preview": scene["revision"]["preview_asset_id"]}) + "\n")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


def browser(args: argparse.Namespace) -> None:
    from playwright.sync_api import expect, sync_playwright

    fixture = json.loads((args.data_dir / "fixture.json").read_text())
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    evidence: dict = {"mode": "source_standalone_real_blender_worker_target_fault",
                      "width": args.width, "locale": args.locale, "page_errors": []}
    with sync_playwright() as pw:
        chrome = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False)
        try:
            page = chrome.new_page(viewport={"width": args.width, "height": 800}, locale=args.locale)
            page.on("pageerror", lambda error: evidence["page_errors"].append(str(error)))
            page.goto(args.url)
            page.locator('#app[aria-busy="false"]').wait_for()
            page.evaluate("locale => {applyTheme({locale}); renderSceneText();}", args.locale)
            page.locator("#create-media-3d").click()
            page.locator(f'[data-scene-id="{fixture["scene_id"]}"]').click()
            page.wait_for_function("state.sceneMaterialRevisionId && !state.sceneMaterialBusy")
            if not page.locator("#scene-material-object").is_visible():
                page.locator("#scene-material-title").click()
            page.locator("#scene-material-object").select_option("Cube")
            page.locator("#scene-material-image").select_option(fixture["image_id"])

            def scene() -> dict:
                return page.evaluate("id => call('scenes.get', {scene_id:id})", fixture["scene_id"])

            def hashes() -> dict:
                values = {}
                for asset in (fixture["image_id"], fixture["source"], fixture["preview"]):
                    response = page.request.get(f"{args.url}/api/v1/assets/{asset}/content")
                    assert response.ok
                    values[asset] = hashlib.sha256(response.body()).hexdigest()
                return values

            selections = """() => ['scene-material-object','scene-material-image','scene-material-slot',
              'scene-material-channel','scene-material-uv'].map(id=>document.getElementById(id).value)"""
            before, original_hashes = scene(), hashes()
            selected = page.evaluate(selections)
            page.locator("#scene-material-apply").click()
            page.wait_for_function("!state.sceneMaterialBusy && !state.sceneMaterialPreparing && document.querySelector('#scene-compare-dialog').open")
            assert not page.evaluate("state.sceneMaterialCandidate")
            expect(page.locator("#scene-compare-restore")).to_be_disabled()
            expect(page.locator("#scene-compare-old-status")).to_have_text(
                "The current revision is unchanged." if args.locale == "en" else "元の版は変更していません。")
            expect(page.locator("#scene-compare-current-status")).to_have_text(
                "The image material could not be assigned." if args.locale == "en" else "画像素材を割り当てられませんでした。")
            assert page.locator("#scene-compare-status").inner_text()
            evidence["failure_message"] = page.locator("#scene-compare-status").inner_text()
            assert scene() == before and hashes() == original_hashes
            page.screenshot(path=str(args.evidence_dir / "failed.png"))
            page.locator("#scene-compare-cancel").click()
            assert page.evaluate(selections) == selected
            expect(page.locator("#scene-material-apply")).to_be_enabled()
            page.locator("#scene-material-apply").click()
            page.wait_for_function("state.sceneCompareReady === 2 && state.sceneMaterialCandidate", timeout=30000)
            assert scene() == before and hashes() == original_hashes
            page.screenshot(path=str(args.evidence_dir / "retry-candidate.png"))
            page.locator("#scene-compare-restore").click()
            page.wait_for_function("!document.querySelector('#scene-compare-dialog').open && state.sceneRevisions.length === 2", timeout=30000)
            after = scene()
            assert after["revisions"][0] == before["revisions"][0]
            assert any(d["asset_id"] == fixture["image_id"] for d in after["revisions"][-1]["dependencies"])
            assert hashes() == original_hashes
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not evidence["page_errors"]
            evidence.update(passed=True, before=before, after=after, old_asset_hashes=original_hashes,
                failed_head_unchanged=True, selection_preserved=True, retry_not_committed_before_adoption=True,
                not_tested=["installed Host", "new image generation", "Agent retry_job_id"])
        finally:
            chrome.close()
            (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"passed": True, "width": args.width, "locale": args.locale}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--blend", type=Path)
    parser.add_argument("--image", type=Path)
    parser.add_argument("--port", type=int, default=9164)
    parser.add_argument("--url", default="http://127.0.0.1:9164")
    parser.add_argument("--width", type=int, choices=(320, 1280), default=320)
    parser.add_argument("--locale", choices=("ja", "en"), default="ja")
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    serve(args) if args.serve else browser(args)
