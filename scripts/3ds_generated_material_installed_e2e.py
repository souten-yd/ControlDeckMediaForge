"""Generate one real texture through installed UI, compare, discard, adopt.

Uses an existing dedicated mf-e2e scene; preserves old revisions and generated
assets. No model installation, service restart, Host configuration or overlay.
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
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    status = registry.status("media-forge")
    assert status["version"] == args.expected_version and status["health"] == "healthy"
    args.evidence_dir.mkdir(exist_ok=False)
    spec = importlib.util.spec_from_file_location("helper", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    evidence: dict[str, Any] = {"version": status["version"], "scene_id": args.scene_id, "page_errors": [], "job_states": []}
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        token = create_session(db, user, "127.0.0.1", "Installed generated-material acceptance")
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
                frame.wait_for_function("() => state.sceneMaterialRevisionId === state.sceneDocument.current_revision_id")
                if not frame.locator("#scene-material-object").is_visible():
                    frame.locator("#scene-material-title").click()
                frame.locator("#scene-material-object").select_option("Cube")
                frame.locator("#scene-material-channel").select_option("base_color")
                before = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
                evidence["before"] = before
                previous = frame.evaluate("() => selectedSceneTextureJob()?.id || ''")
                frame.locator("#scene-texture-prompt").fill("Seamless blue ceramic tile texture with thin white grout, flat evenly lit surface, no objects, no text")
                start = time.monotonic()
                frame.locator("#scene-texture-generate").click()
                frame.wait_for_function("previous => selectedSceneTextureJob()?.id && selectedSceneTextureJob().id !== previous", arg=previous, timeout=30000)
                job_id = frame.evaluate("() => selectedSceneTextureJob().id")
                evidence["job_id"] = job_id
                print(json.dumps({"job_id": job_id}), flush=True)
                last_state = None
                while True:
                    job = frame.evaluate("id => call('jobs.get', {job_id:id})", job_id)
                    state = (job["status"], job.get("phase"))
                    if state != last_state:
                        event = {"status": state[0], "phase": state[1], "elapsed_sec": round(time.monotonic() - start, 3)}
                        evidence["job_states"].append(event)
                        print(json.dumps(event), flush=True)
                        last_state = state
                    if job["status"] in {"succeeded", "failed", "canceled"}:
                        break
                    if time.monotonic() - start > 600:
                        raise TimeoutError("Owned texture job exceeded acceptance observation window")
                    page.wait_for_timeout(1000)
                evidence["job"] = job
                evidence["generation_seconds"] = round(time.monotonic() - start, 3)
                assert job["status"] == "succeeded", job.get("error")
                assert job["request"]["local_only"] is True
                assert job["request"]["constraints"]["scene_texture"]["source_revision_id"] == before["scene"]["current_revision_id"]
                asset_id = job["asset_ids"][0]
                evidence["image_asset_id"] = asset_id
                provenance = frame.evaluate("id => call('assets.provenance', {asset_id:id})", asset_id)
                evidence["image_provenance"] = provenance
                assert provenance["model_id"] and provenance["license"]
                assert "fake" not in provenance["model_id"].lower()
                assert frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id) == before
                frame.locator("#scene-texture-use").click()
                frame.wait_for_function("id => document.querySelector('#scene-material-image').value === id", arg=asset_id)

                def prepare() -> None:
                    frame.locator("#scene-material-apply").click()
                    frame.wait_for_function("() => state.sceneCompareReady === 2 && state.sceneMaterialCandidate", timeout=30000)
                    assert frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id) == before

                prepare()
                page.screenshot(path=str(args.evidence_dir / "generated-candidate.png"))
                frame.locator("#scene-compare-cancel").click()
                frame.wait_for_function("() => !state.sceneMaterialCandidate && !document.querySelector('#scene-compare-dialog').open")
                assert frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id) == before
                prepare()
                frame.locator("#scene-compare-restore").click()
                frame.wait_for_function("n => !document.querySelector('#scene-compare-dialog').open && state.sceneRevisions.length === n", arg=len(before["revisions"]) + 1, timeout=30000)
                after = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
                evidence["after"] = after
                revision = next(r for r in after["revisions"] if r["id"] == after["scene"]["current_revision_id"])
                assert any(d["asset_id"] == asset_id for d in revision["dependencies"])
                assert all(r in after["revisions"] for r in before["revisions"])
                evidence["adopted_source_provenance"] = frame.evaluate("id => call('assets.provenance', {asset_id:id})", revision["source_asset_id"])
                evidence["generation_prepare_discard_head_unchanged"] = True
                evidence["adoption_adds_one_revision_with_image_dependency"] = True
                assert not evidence["page_errors"]
            except Exception as error:
                evidence["failure"] = type(error).__name__
                if 'page' in locals():
                    page.screenshot(path=str(args.evidence_dir / "failure.png"))
                if 'job_id' in locals():
                    current = frame.evaluate("id => call('jobs.get', {job_id:id})", job_id)
                    evidence["job_at_failure"] = current
                    if current["status"] not in {"succeeded", "failed", "canceled"}:
                        frame.evaluate("id => call('jobs.cancel', {job_id:id})", job_id)
                raise
            finally:
                browser.close()
    finally:
        with SessionLocal() as db:
            revoke_session(db, token)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({k: v for k, v in evidence.items() if k not in {"before", "after", "job", "image_provenance", "adopted_source_provenance"}}, indent=2))


if __name__ == "__main__":
    main()
