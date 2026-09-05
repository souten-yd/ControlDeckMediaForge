"""Isolated real-Blender/source-server recovery-fork acceptance.

Use core Python for --serve with a NEW --data-dir and an existing verified
--legacy-runtime-root. Use Playwright Python for --url against that server.
No installed data, service, or Host credentials are changed.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time


def serve(args: argparse.Namespace) -> None:
    import uvicorn
    from mediaforge.app import create_app
    from mediaforge.config import Settings
    from mediaforge.scene_workspace import BLEND_CHUNK_BYTES
    from mediaforge.scenes import SceneRevisionInput

    args.data_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    app = create_app(Settings(data_dir=args.data_dir, blender_legacy_runtime_root=args.legacy_runtime_root))
    store = app.state.store
    store.initialize()
    workspace = app.state.scene_workspace
    workspace.initialize()
    assert workspace.resolver.register_legacy()
    runtime = workspace.resolver.resolve_g8()
    assert runtime is not None
    original = args.data_dir / "original.blend"
    changed = args.data_dir / "changed.blend"
    expression = (
        "import bpy; "
        f"bpy.ops.wm.save_as_mainfile(filepath={str(original)!r}); "
        "bpy.data.objects['Cube'].location.x=2; "
        f"bpy.ops.wm.save_as_mainfile(filepath={str(changed)!r})"
    )
    subprocess.run([str(runtime.executable), "--background", "--factory-startup", "--disable-autoexec",
                    "--python-expr", expression], check=True, timeout=60, capture_output=True)
    content = original.read_bytes()
    upload = workspace.begin_upload("local", size=len(content), sha256=hashlib.sha256(content).hexdigest(), name="Recovery acceptance")
    for offset in range(0, len(content), BLEND_CHUNK_BYTES):
        chunk = content[offset:offset + BLEND_CHUNK_BYTES]
        workspace.append_upload("local", upload["upload_id"], offset, chunk, hashlib.sha256(chunk).hexdigest())
    imported = asyncio.run(workspace.commit_upload("local", upload["upload_id"]))
    scene_id = imported["scene"]["id"]
    working = workspace.acquire_working_copy("local", scene_id)
    candidate = workspace.working_path_for_runtime("local", working.id)
    shutil.copyfile(changed, candidate)
    workspace.retain_working_copy_for_recovery("local", working.id)
    revision = imported["revision"]
    workspace.catalog.commit("local", scene_id, revision["id"], SceneRevisionInput(**{
        key: revision[key] for key in SceneRevisionInput.model_fields
    }))
    fixture = {"scene_id": scene_id, "working_id": working.id, "runtime": runtime.version,
               "recovery_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
               "recovery_bytes": candidate.stat().st_size}
    (args.data_dir / "fixture.json").write_text(json.dumps(fixture, indent=2) + "\n")
    print(json.dumps(fixture), flush=True)
    uvicorn.run(app, host="127.0.0.1", port=args.port)


def browser_check(args: argparse.Namespace) -> None:
    from playwright.sync_api import sync_playwright

    fixture = json.loads((args.data_dir / "fixture.json").read_text())
    scene_id = fixture["scene_id"]
    evidence: dict[str, object] = dict(fixture)
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--enable-unsafe-swiftshader"])
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.goto(args.url, wait_until="domcontentloaded")
            page.wait_for_selector('#app[aria-busy="false"]', timeout=15000)
            page.click('[data-create-media="3d"]')
            page.locator(f'[data-scene-id="{scene_id}"]').click()
            page.wait_for_function("id => state.sceneDocument?.id === id && !document.querySelector('#scene-recovery-fork').hidden && !document.querySelector('#scene-recovery-fork').disabled", arg=scene_id)
            assert page.locator("#scene-blender-recover").is_disabled()
            assert "上書き" in page.locator("#scene-blender-status").inner_text()
            before = page.request.get(f"{args.url}/workspace-api/scenes/{scene_id}").json()
            # The recovery action is available on 320px without requiring a GUI Web pack.
            page.set_viewport_size({"width": 320, "height": 740})
            assert page.locator("#scene-recovery-fork").is_enabled()
            overflow = page.evaluate("document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth")
            assert overflow == 0, overflow
            started = time.monotonic()
            page.click("#scene-recovery-fork")
            page.wait_for_function("old => state.selectedSceneId !== old && !state.sceneRecoveryBusy", arg=scene_id, timeout=60000)
            recovered_id = page.evaluate("state.selectedSceneId")
            recovered = page.request.get(f"{args.url}/workspace-api/scenes/{recovered_id}").json()
            source_id = recovered["revisions"][0]["source_asset_id"]
            source = page.request.get(f"{args.url}/api/v1/assets/{source_id}/content").body()
            provenance = page.request.get(f"{args.url}/api/v1/assets/{source_id}/provenance").json()
            assert hashlib.sha256(source).hexdigest() == fixture["recovery_sha256"]
            assert provenance["operation"] == "scene.recovery.fork"
            assert provenance["parameters"]["source_scene_id"] == scene_id
            assert page.request.get(f"{args.url}/workspace-api/scenes/{scene_id}").json() == before
            repeated = page.request.post(f"{args.url}/workspace-api/scenes/{scene_id}/recovery/fork",
                                         data={"recovery_working_id": fixture["working_id"]})
            assert repeated.ok and repeated.json()["scene"]["id"] == recovered_id
            candidate = args.data_dir / "scenes/working" / fixture["working_id"] / "scene.blend"
            assert hashlib.sha256(candidate.read_bytes()).hexdigest() == fixture["recovery_sha256"]
            page.evaluate("document.documentElement.lang = 'en'; renderSceneText();")
            assert page.locator("#scene-recovery-fork").text_content() == "Save recovery as a separate scene"
            assert not errors, errors
            evidence.update({"recovered_scene_id": recovered_id, "elapsed_sec": time.monotonic() - started,
                             "mobile_overflow_320": overflow, "source_asset_id": source_id,
                             "browser_errors": errors, "installed_host": "NOT TESTED"})
            page.screenshot(path=str(args.evidence_dir / "recovered.png"), full_page=True)
        finally:
            browser.close()
    (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--legacy-runtime-root", type=Path)
    parser.add_argument("--port", type=int, default=9142)
    parser.add_argument("--url")
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    if args.serve:
        if args.legacy_runtime_root is None:
            parser.error("--serve requires --legacy-runtime-root")
        serve(args)
    else:
        if not args.url or args.evidence_dir is None:
            parser.error("browser mode requires --url and --evidence-dir")
        browser_check(args)
