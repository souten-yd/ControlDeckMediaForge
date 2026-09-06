"""Continue a dedicated OpenCode sword through real installed UI and Blender.

Host diagnostic venv only; individual login session, no password changes,
overlay, runtime installation, service restart or modification of other scenes.
Preserves all revisions and records failure without claiming full acceptance.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


def main() -> None:
    from app.database import SessionLocal
    from app.features import registry
    from app.models import User
    from app.security.sessions import SESSION_COOKIE, create_session, revoke_session

    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--existing-image-id", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--resume-after-existing", action="store_true",
                        help="Continue the dedicated revision 3 after an interrupted generation")
    parser.add_argument("--resume-gui", action="store_true",
                        help="Reconnect the dedicated revision 4 without regenerating its image")
    parser.add_argument("--resume-gui-revisions", type=int, default=4,
                        help="Exact expected revision count when resuming a recorded GUI attempt")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    status = registry.status("media-forge")
    assert status["version"] == args.expected_version and status["health"] == "healthy"
    args.evidence_dir.mkdir(exist_ok=False)
    spec = importlib.util.spec_from_file_location("helper", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    evidence: dict[str, Any] = {"version": status["version"], "scene_id": args.scene_id, "page_errors": []}
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        token = create_session(db, user, "127.0.0.1", "Dedicated sword UI acceptance")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
                args=["--enable-webgl", "--ignore-gpu-blocklist", "--window-size=1280,1000"])
            try:
                context = browser.new_context(base_url="http://127.0.0.1:8765", no_viewport=True)
                context.add_cookies([{"name": SESSION_COOKIE, "value": token, "url": "http://127.0.0.1:8765", "httpOnly": True, "sameSite": "Lax"}])
                page = context.new_page()
                page.on("pageerror", lambda error: evidence["page_errors"].append(str(error)))
                frame = helpers.open_scene(page, args.scene_id)
                evidence["origin"] = frame.evaluate("self.origin")
                assert evidence["origin"] == "null"

                def scene() -> dict[str, Any]:
                    return frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)

                def current(value: dict[str, Any]) -> dict[str, Any]:
                    return next(r for r in value["revisions"] if r["id"] == value["scene"]["current_revision_id"])

                before = scene()
                assert before["scene"]["name"] == "MF3DS OpenCode sword acceptance"
                expected_revisions = args.resume_gui_revisions if args.resume_gui else 3 if args.resume_after_existing else 2
                assert len(before["revisions"]) == expected_revisions, "Unexpected dedicated scene head"
                evidence["before"] = before

                def material_controls() -> None:
                    frame.wait_for_function("() => state.sceneMaterialRevisionId === state.sceneDocument.current_revision_id")
                    if not frame.locator("#scene-material-object").is_visible():
                        frame.locator("#scene-material-title").click()
                    frame.locator("#scene-material-object").select_option("Blade")
                    frame.locator("#scene-material-channel").select_option("base_color")

                def compare_adopt(image_id: str, label: str) -> dict[str, Any]:
                    material_controls()
                    initial = scene()
                    frame.locator("#scene-material-image").select_option(image_id)
                    for discard in (True, False):
                        frame.locator("#scene-material-apply").click()
                        frame.wait_for_function("() => state.sceneCompareReady === 2 && state.sceneMaterialCandidate", timeout=60000)
                        assert scene() == initial
                        page.screenshot(path=str(args.evidence_dir / (label + ("-discard.png" if discard else "-adopt.png"))))
                        if discard:
                            frame.locator("#scene-compare-cancel").click()
                            frame.wait_for_function("() => !state.sceneMaterialCandidate && !document.querySelector('#scene-compare-dialog').open")
                            assert scene() == initial
                        else:
                            frame.locator("#scene-compare-restore").click()
                            frame.wait_for_function("n => !document.querySelector('#scene-compare-dialog').open && state.sceneRevisions.length === n", arg=len(initial["revisions"]) + 1, timeout=60000)
                    adopted = scene()
                    assert all(r in adopted["revisions"] for r in initial["revisions"])
                    assert any(d["asset_id"] == image_id for d in current(adopted)["dependencies"])
                    evidence[label] = adopted
                    print(json.dumps({"stage": label, "revision": current(adopted)["id"]}), flush=True)
                    return adopted

                if args.resume_gui:
                    textured = before
                    evidence["resumed_gui"] = True
                    evidence["generated_image_id"] = next(d["asset_id"] for d in current(before)["dependencies"] if d["role"].startswith("material.base_color."))
                else:
                    if args.resume_after_existing:
                        assert any(d["asset_id"] == args.existing_image_id for d in current(before)["dependencies"])
                        evidence["resumed_after_existing"] = True
                    else:
                        compare_adopt(args.existing_image_id, "existing-image")
                    material_controls()
                    pre_generation = scene()
                    previous = frame.evaluate("() => selectedSceneTextureJob()?.id || ''")
                    frame.locator("#scene-texture-prompt").fill("Blue steel sword blade surface texture, brushed steel fine linear grain, evenly lit flat surface, no text, no objects")
                    frame.locator("#scene-texture-generate").click()
                    frame.wait_for_function("previous => selectedSceneTextureJob()?.id && selectedSceneTextureJob().id !== previous", arg=previous, timeout=30000)
                    job_id = frame.evaluate("() => selectedSceneTextureJob().id")
                    evidence["image_job_id"] = job_id
                    started = time.monotonic()
                    last = None
                    while True:
                        job = frame.evaluate("id => call('jobs.get', {job_id:id})", job_id)
                        state = (job["status"], job.get("phase"))
                        if state != last:
                            print(json.dumps({"job_id": job_id, "status": state, "elapsed_sec": round(time.monotonic() - started, 3)}), flush=True)
                            last = state
                        if job["status"] in {"succeeded", "failed", "canceled"}:
                            break
                        page.wait_for_timeout(1000)
                    evidence["image_job"] = job
                    assert job["status"] == "succeeded", job.get("error")
                    assert scene() == pre_generation
                    image_id = job["asset_ids"][0]
                    evidence["generated_image_id"] = image_id
                    evidence["image_provenance"] = frame.evaluate("id => call('assets.provenance', {asset_id:id})", image_id)
                    assert "fake" not in evidence["image_provenance"]["model_id"].lower()
                    frame.locator("#scene-texture-use").click()
                    frame.wait_for_function("id => document.querySelector('#scene-material-image').value === id", arg=image_id)
                    textured = compare_adopt(image_id, "generated-image")

                previous_session = helpers.session_projection(frame, args.scene_id)
                frame.locator("#scene-blender-open").click()
                session = helpers.wait_session(frame, args.scene_id, {"ready"}, timeout=90)
                evidence["session_id"] = session["id"]
                if previous_session:
                    assert session["id"] == previous_session["id"]
                if not frame.locator("#scene-blender-dialog[open]").count():
                    frame.locator("#scene-blender-open").click()
                frame.wait_for_function("() => ['接続しました','Connected'].includes(document.querySelector('#scene-blender-connection').textContent)", timeout=30000)
                screen = frame.locator("#scene-blender-screen canvas")
                screen.click(position={"x": 320, "y": 240})
                # Wait for real RFB delivery/Blender input processing between
                # modal operations; DOM key dispatch is not remote completion.
                page.wait_for_timeout(500)
                page.keyboard.press("a")
                page.wait_for_timeout(500)
                page.keyboard.press("Shift+D")
                page.wait_for_timeout(500)
                page.keyboard.press("x")
                page.keyboard.type("0.02", delay=100)
                page.keyboard.press("Enter")
                page.wait_for_timeout(1500)
                page.screenshot(path=str(args.evidence_dir / "blender-edited.png"))
                frame.locator("#scene-blender-save").click()
                frame.wait_for_function("n => state.sceneRevisions.length === n", arg=len(textured["revisions"]) + 1, timeout=90000)
                edited = scene()
                evidence["gui-edited"] = edited
                assert helpers.session_projection(frame, args.scene_id) is None
                def mesh_count(value: dict[str, Any]) -> int:
                    return next(v["facts"]["meshes"] for v in current(value)["validation"] if v["validator"] == "blender.scene")
                assert mesh_count(edited) == mesh_count(textured) * 2, "GUI input did not duplicate the selected meshes"
                frame.locator(f'[data-scene-compare="{current(textured)["id"]}"]').click()
                frame.wait_for_function("() => state.sceneCompareReady === 2", timeout=30000)
                page.screenshot(path=str(args.evidence_dir / "restore-comparison.png"))
                frame.locator("#scene-compare-restore").click()
                frame.wait_for_function("n => !document.querySelector('#scene-compare-dialog').open && state.sceneRevisions.length === n", arg=len(edited["revisions"]) + 1, timeout=60000)
                restored = scene()
                evidence["restored"] = restored
                original = frame.evaluate("id => call('assets.provenance', {asset_id:id})", current(textured)["source_asset_id"])
                restored_provenance = frame.evaluate("id => call('assets.provenance', {asset_id:id})", current(restored)["source_asset_id"])
                assert original["output_sha256"] == restored_provenance["output_sha256"]
                assert all(r in restored["revisions"] for r in edited["revisions"])
                evidence["restored_source_sha256"] = original["output_sha256"]
                assert not evidence["page_errors"]
                evidence["success"] = True
            except Exception as error:
                evidence["failure"] = str(error)
                if "page" in locals():
                    page.screenshot(path=str(args.evidence_dir / "failure.png"))
                raise
            finally:
                browser.close()
    finally:
        with SessionLocal() as db:
            revoke_session(db, token)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({key: evidence[key] for key in ("success", "scene_id", "generated_image_id", "session_id", "restored_source_sha256")}), flush=True)


if __name__ == "__main__":
    main()
