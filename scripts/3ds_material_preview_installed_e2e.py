"""Installed opaque-iframe material candidate acceptance on a NEW test scene.

Host diagnostic venv only. Creates and revokes one mf-e2e login session; never
changes passwords. Imports the supplied test blend and a synthetic red image.
Keeps test scene/revisions for provenance. Does not overlay frontend code.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import struct
import zlib
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


def red_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 64, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\0" + bytes((220, 30, 20)) * 64) * 64))
            + chunk(b"IEND", b""))


def main() -> None:
    from app.database import SessionLocal
    from app.features import registry
    from app.models import User
    from app.security.sessions import SESSION_COOKIE, create_session, revoke_session

    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--refresh-during-click", action="store_true",
                        help="Refresh unchanged scene between pointer down/up on revision comparison")
    args = parser.parse_args()
    assert args.blend.is_file() and not args.blend.is_symlink()
    args.evidence_dir.mkdir(exist_ok=False)
    installed = registry.status("media-forge")
    assert installed["version"] == args.expected_version and installed["health"] == "healthy"
    spec = importlib.util.spec_from_file_location("scene_browser", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    evidence: dict[str, Any] = {"installed_version": installed["version"], "frontend": "installed, no overlay", "page_errors": []}
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        token = create_session(db, user, "127.0.0.1", "MediaForge new-scene material candidate acceptance")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
                                         args=["--enable-webgl", "--ignore-gpu-blocklist", "--window-size=1280,1000"])
            try:
                # Headed viewport emulation can exceed the compositor's actual
                # content area; OOPIF bottom clicks then stop at the Host iframe.
                # Measure native geometry instead of claiming a synthetic size.
                context = browser.new_context(base_url="http://127.0.0.1:8765", no_viewport=True)
                context.add_cookies([{"name": SESSION_COOKIE, "value": token, "url": "http://127.0.0.1:8765", "httpOnly": True, "sameSite": "Lax"}])
                page = context.new_page()
                page.on("pageerror", lambda error: evidence["page_errors"].append(str(error)))
                page.goto("/x/media-forge/workspace/create", wait_until="domcontentloaded")
                evidence["native_viewport"] = page.evaluate("() => ({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})")
                frame = helpers.workspace_frame(page)
                frame.wait_for_selector('#app[aria-busy="false"]')
                frame.evaluate("""() => {
                  window.__materialTrace = [];
                  const snapshot = (event, extra = {}) => {
                    window.__materialTrace.push({event, ms: performance.now(),
                      locked: state.hostActionLocked, materialBusy: state.sceneMaterialBusy,
                      restoreBusy: state.sceneRestoreBusy, disabled: state.disabled,
                      ready: state.sceneCompareReady, token: state.sceneCompareToken,
                      head: state.sceneDocument?.current_revision_id,
                      dialog: document.querySelector('#scene-compare-dialog').open, ...extra});
                  };
                  for (const name of ['openScene', 'openSceneCompare', 'closeSceneCompare', 'restoreComparedSceneRevision']) {
                    const original = window[name];
                    window[name] = async function(...args) {
                      snapshot(name + ':start', {args});
                      try { return await original.apply(this, args); }
                      finally { snapshot(name + ':end'); }
                    };
                  }
                  for (const kind of ['pointerdown', 'pointerup', 'click']) document.addEventListener(kind, event => {
                    const target = event.target.closest('button');
                    snapshot(kind, {tag: event.target.tagName, id: target?.id || event.target.id,
                      compare: target?.dataset.sceneCompare || ''});
                  }, true);
                }""")
                frame.locator("#create-media-3d").click()
                frame.locator("#scene-import-file").set_input_files(str(args.blend))
                frame.locator("#scene-import-name").fill("mf-e2e material candidate " + args.expected_version)
                frame.locator("#scene-import-submit").click()
                frame.wait_for_function("() => state.selectedSceneId && state.sceneMaterialRevisionId && !state.sceneMaterialBusy", timeout=60000)
                scene_id = frame.evaluate("() => state.selectedSceneId")
                evidence["scene_id"] = scene_id
                evidence["opaque_origin"] = frame.evaluate("() => self.origin")
                assert evidence["opaque_origin"] == "null"
                red = frame.evaluate("data => call('assets.import', {purpose:'source', media_type:'image/png', base64:data})", base64.b64encode(red_png()).decode())
                evidence["red_asset_id"] = red["id"]
                frame.evaluate("async () => {state.sceneMaterialImages = await loadSceneMaterialImages(); renderSceneMaterialControls();}")
                if not frame.locator("#scene-material-object").is_visible():
                    frame.locator("#scene-material-title").click()

                def scene() -> dict[str, Any]:
                    return frame.evaluate("id => call('scenes.get', {scene_id:id})", scene_id)

                def prepare() -> None:
                    frame.wait_for_function("() => !document.querySelector('#scene-material-object').disabled")
                    frame.locator("#scene-material-object").select_option("Cube")
                    frame.locator("#scene-material-image").select_option(red["id"])
                    frame.locator("#scene-material-apply").click()
                    frame.wait_for_function("() => state.sceneCompareReady === 2 && state.sceneMaterialCandidate", timeout=30000)
                    assert not frame.locator("#scene-compare-restore").is_disabled()

                before = scene()
                assert len(before["revisions"]) == 1
                frame.evaluate("() => {document.documentElement.lang='ja'; renderSceneText();}")
                prepare()
                assert scene() == before
                assert "未保存" in frame.locator("#scene-compare-current-label").inner_text()
                captures = [frame.locator(f"#scene-compare-{side}-canvas").screenshot(path=str(args.evidence_dir / f"{side}.png")) for side in ("old", "current")]
                assert hashlib.sha256(captures[0]).digest() != hashlib.sha256(captures[1]).digest()
                page.screenshot(path=str(args.evidence_dir / "comparison-ja.png"))
                frame.evaluate("() => {document.documentElement.lang='en'; renderSceneText();}")
                assert "not saved" in frame.locator("#scene-compare-current-label").inner_text()
                assert "triangle" in frame.locator("#scene-compare-old-status").inner_text().lower()
                frame.locator("#scene-compare-cancel").click()
                frame.wait_for_function("() => !document.querySelector('#scene-compare-dialog').open && !state.sceneMaterialCandidate")
                assert scene() == before
                prepare()
                frame.locator("#scene-compare-restore").click()
                frame.wait_for_function("() => !document.querySelector('#scene-compare-dialog').open && state.sceneRevisions.length === 2", timeout=30000)
                adopted = scene()
                assert len(adopted["revisions"]) == 2
                old = before["scene"]["current_revision_id"]
                compare = frame.locator(f'[data-scene-compare="{old}"]')
                if args.refresh_during_click:
                    frame.evaluate("id => openScene(id)", scene_id)
                    compare.scroll_into_view_if_needed()
                    compare.hover()
                    box = compare.bounding_box()
                    assert box
                    evidence["comparison_button_box"] = box
                    page.screenshot(path=str(args.evidence_dir / "before-pointer.png"))
                    assert 0 < box["y"] + box["height"] / 2 < page.evaluate("innerHeight")
                    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    page.mouse.down()
                    frame.evaluate("() => {window.__revisionButton = document.querySelector('[data-scene-compare]');}")
                    frame.evaluate("id => openScene(id)", scene_id)
                    evidence["revision_button_retained"] = frame.evaluate("() => window.__revisionButton.isConnected")
                    page.mouse.up()
                    assert evidence["revision_button_retained"], "Unchanged refresh detached the pressed revision button"
                    evidence["refresh_during_click"] = True
                else:
                    compare.click()
                frame.wait_for_function("() => state.sceneCompareReady === 2")
                assert "Restore" in frame.locator("#scene-compare-restore").inner_text()
                frame.locator("#scene-compare-restore").click()
                frame.wait_for_function("() => !document.querySelector('#scene-compare-dialog').open && state.sceneRevisions.length === 3", timeout=30000)
                restored = scene()
                assert len(restored["revisions"]) == 3
                assets = frame.evaluate("() => call('assets.list', {})")["items"]
                hashes = {asset["id"]: asset["sha256"] for asset in assets}
                original_revision = before["revisions"][0]
                restored_revision = next(r for r in restored["revisions"] if r["id"] == restored["scene"]["current_revision_id"])
                assert hashes[original_revision["source_asset_id"]] == hashes[restored_revision["source_asset_id"]]
                evidence["restore_source_sha256_equal"] = True
                evidence["before"] = before
                evidence["adopted"] = adopted
                evidence["restored"] = restored
                prepare()
                frame.evaluate("dropSocket()")
                assert frame.locator("#scene-compare-restore").is_disabled()
                assert "connection" in frame.locator("#scene-compare-status").inner_text()
                frame.locator("#scene-compare-cancel").click()
                assert scene() == restored
                assert not evidence["page_errors"]
                evidence["final_native_viewport"] = page.evaluate("() => ({width:innerWidth,height:innerHeight,dpr:devicePixelRatio})")
                evidence.update({"prepare_discard_head_unchanged": True, "adopt_adds_one_revision": True,
                                 "restore_adds_one_revision": True, "connection_loss_disables_adopt": True,
                                 "not_tested": ["generated image workflow", "mobile touch", "long credential refresh"]})
            except Exception as error:
                evidence["failure"] = type(error).__name__
                if 'page' in locals():
                    page.screenshot(path=str(args.evidence_dir / "failure.png"))
                if 'frame' in locals():
                    evidence["failure_state"] = frame.evaluate("() => ({locked:state.hostActionLocked,disabled:state.disabled,restoreBusy:state.sceneRestoreBusy,compareReady:state.sceneCompareReady,compareToken:state.sceneCompareToken,head:state.sceneDocument?.current_revision_id,materialRevision:state.sceneMaterialRevisionId,dialog:document.querySelector('#scene-compare-dialog').open,status:document.querySelector('#scene-compare-status').textContent})")
                raise
            finally:
                if 'frame' in locals() and not frame.is_detached():
                    evidence["interaction_trace"] = frame.evaluate("() => window.__materialTrace || []")
                browser.close()
    finally:
        with SessionLocal() as db:
            revoke_session(db, token)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({k: v for k, v in evidence.items() if k not in ("before", "adopted", "restored", "interaction_trace")}, indent=2))


if __name__ == "__main__":
    main()
