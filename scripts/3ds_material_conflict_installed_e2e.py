"""Installed stale-binding conflict, preserved image, and UI retry.

Host diagnostic Python only. New retained test scene; no product code overlay,
worker fault injection, runtime changes, or existing scene mutation.
The stale request enters the real product comparison helper directly because
focus refresh normally disables stale form submission. Retry/adopt use buttons.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import sqlite3
from pathlib import Path
from typing import Any

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    from app.database import SessionLocal
    from app.features import registry
    from app.models import User
    from app.security.sessions import SESSION_COOKIE, create_session, revoke_session

    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--locale", choices=("ja", "en"), required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    for path in (args.blend, args.image):
        assert path.is_file() and not path.is_symlink()
    installed = registry.status("media-forge")
    assert installed["version"] == args.expected_version and installed["health"] == "healthy"
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    data = Path("/data1tb/ControlDeck/data/feature-data/media-forge/data")

    def documents() -> dict[str, dict[str, str]]:
        with sqlite3.connect(f"file:{data}/media-forge.sqlite3?mode=ro", uri=True) as db:
            return {t: dict(db.execute(f"select id,value_json from {t}"))
                    for t in ("scene_documents", "scene_revisions")}

    def hashes(ids: list[str]) -> dict[str, str]:
        result = {}
        for asset_id in ids:
            assert asset_id.startswith("asset_") and len(asset_id) == 38
            paths = [p for p in (data / "assets").glob(asset_id + ".*")
                     if p.suffix in (".png", ".blend", ".glb")]
            assert len(paths) == 1 and not paths[0].is_symlink()
            result[asset_id] = hashlib.sha256(paths[0].read_bytes()).hexdigest()
        return result

    existing = documents()
    spec = importlib.util.spec_from_file_location(
        "installed_browser", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    evidence: dict[str, Any] = {"version": args.expected_version, "locale": args.locale,
        "mode": "installed_two_tab_stale_binding_via_product_helper", "page_errors": []}
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        token = create_session(db, user, "127.0.0.1", "MediaForge material conflict acceptance")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
                                         args=["--window-size=1280,1000"])
            try:
                context = browser.new_context(base_url="http://127.0.0.1:8765", no_viewport=True,
                                              locale=args.locale)
                context.add_cookies([{"name": SESSION_COOKIE, "value": token,
                    "url": "http://127.0.0.1:8765", "httpOnly": True, "sameSite": "Lax"}])
                page = context.new_page()
                page.on("pageerror", lambda error: evidence["page_errors"].append(str(error)))
                page.goto("/x/media-forge/workspace/create", wait_until="domcontentloaded")
                frame = helpers.workspace_frame(page)
                frame.wait_for_selector('#app[aria-busy="false"]')
                assert frame.evaluate("self.origin") == "null"
                evidence["viewport"] = page.evaluate("({width:innerWidth,height:innerHeight})")
                frame.locator("#create-media-3d").click()
                frame.locator("#scene-import-file").set_input_files(str(args.blend))
                frame.locator("#scene-import-name").fill("mf-e2e material conflict " + args.locale)
                frame.locator("#scene-import-submit").click()
                frame.wait_for_function("state.selectedSceneId && state.sceneMaterialRevisionId && !state.sceneMaterialBusy", timeout=60000)
                scene_id = frame.evaluate("state.selectedSceneId")
                evidence["scene_id"] = scene_id
                image = frame.evaluate("content => call('assets.import', {purpose:'source',media_type:'image/png',base64:content})",
                                       base64.b64encode(args.image.read_bytes()).decode())
                evidence["image_id"] = image["id"]
                assert image["sha256"] == hashlib.sha256(args.image.read_bytes()).hexdigest()
                frame.evaluate("async () => {state.sceneMaterialImages = await loadSceneMaterialImages(); renderSceneMaterialControls();}")
                if not frame.locator("#scene-material-object").is_visible():
                    frame.locator("#scene-material-title").click()
                frame.locator("#scene-material-object").select_option("Cube")
                frame.locator("#scene-material-image").select_option(image["id"])
                selection = "() => ['object','image','slot','channel','uv'].map(s=>document.getElementById('scene-material-'+s).value)"
                selected = frame.evaluate(selection)
                binding = frame.evaluate("""() => ({source_revision_id:state.sceneMaterialRevisionId,
                    object_name:document.querySelector('#scene-material-object').value,
                    image_asset_id:document.querySelector('#scene-material-image').value,
                    material_slot:Number(document.querySelector('#scene-material-slot').value),
                    uv_map:document.querySelector('#scene-material-uv').value})""")
                other = context.new_page()
                other.on("pageerror", lambda error: evidence["page_errors"].append(str(error)))
                other.goto("/x/media-forge/workspace/create", wait_until="domcontentloaded")
                second = helpers.workspace_frame(other)
                second.wait_for_selector('#app[aria-busy="false"]')
                assert second.evaluate("self.origin") == "null"
                assert second.evaluate("id => call('scenes.get',{scene_id:id})", scene_id)["scene"]["id"] == scene_id
                second.evaluate("p => call('scenes.material.apply', p)", {"scene_id": scene_id, "binding": binding})
                other.close()
                page.bring_to_front()
                before = frame.evaluate("id => call('scenes.get',{scene_id:id})", scene_id)
                assert len(before["revisions"]) == 2
                frame.evaluate("id => openScene(id)", scene_id)
                frame.wait_for_function("!state.sceneMaterialBusy")
                frame.locator("#scene-material-object").select_option("Cube")
                frame.locator("#scene-material-image").select_option(image["id"])
                selected = frame.evaluate(selection)
                ids = [image["id"]] + [r[k] for r in before["revisions"] for k in ("source_asset_id", "preview_asset_id")]
                original_hashes = hashes(ids)
                frame.evaluate("p => compareMaterialCandidate(p.scene_id,p.binding)",
                               {"scene_id": scene_id, "binding": binding})
                frame.wait_for_function("!state.sceneMaterialBusy && !state.sceneMaterialPreparing && document.querySelector('#scene-compare-dialog').open")
                expect(frame.locator("#scene-compare-restore")).to_be_disabled()
                expect(frame.locator("#scene-compare-old-status")).to_have_text(
                    "元の版は変更していません。" if args.locale == "ja" else "The current revision is unchanged.")
                expect(frame.locator("#scene-compare-current-status")).to_have_text(
                    "画像素材を割り当てられませんでした。" if args.locale == "ja" else "The image material could not be assigned.")
                evidence["failure_message"] = frame.locator("#scene-compare-status").inner_text()
                assert "revision" in evidence["failure_message"]
                assert not frame.evaluate("state.sceneMaterialCandidate")
                assert frame.evaluate("id => call('scenes.get',{scene_id:id})", scene_id) == before
                assert hashes(ids) == original_hashes
                page.screenshot(path=str(args.evidence_dir / "conflict.png"))
                frame.locator("#scene-compare-cancel").click()
                assert frame.evaluate(selection) == selected
                frame.evaluate("id => openScene(id)", scene_id)
                frame.wait_for_function("!state.sceneMaterialBusy")
                assert frame.evaluate(selection) == selected
                frame.locator("#scene-material-apply").click()
                frame.wait_for_function("state.sceneCompareReady === 2 && state.sceneMaterialCandidate", timeout=30000)
                assert frame.evaluate("id => call('scenes.get',{scene_id:id})", scene_id) == before
                page.screenshot(path=str(args.evidence_dir / "retry-candidate.png"))
                frame.locator("#scene-compare-restore").click()
                frame.wait_for_function("!document.querySelector('#scene-compare-dialog').open && state.sceneRevisions.length === 3", timeout=30000)
                after = frame.evaluate("id => call('scenes.get',{scene_id:id})", scene_id)
                assert after["revisions"][:2] == before["revisions"]
                assert any(d["asset_id"] == image["id"] and d["sha256"] == image["sha256"] for d in after["revisions"][-1]["dependencies"])
                assert hashes(ids) == original_hashes
                current = documents()
                assert all(current[t][key] == value for t, rows in existing.items() for key, value in rows.items())
                assert not evidence["page_errors"]
                evidence.update(passed=True, before=before, after=after, old_asset_hashes=original_hashes,
                    existing_scenes_unchanged=True, selection_preserved=True,
                    not_tested=["worker crash", "Agent retry_job_id", "new image generation", "mobile touch"])
            except Exception as error:
                evidence["failure"] = type(error).__name__
                if "page" in locals() and not page.is_closed():
                    page.screenshot(path=str(args.evidence_dir / "failure.png"))
                raise
            finally:
                browser.close()
    finally:
        with SessionLocal() as db:
            revoke_session(db, token)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({k: evidence[k] for k in ("passed", "version", "locale", "scene_id", "failure_message")}))


if __name__ == "__main__":
    main()
