"""Read-only installed material revision comparison and viewer cleanup acceptance.

Run in the Host diagnostic venv. An existing mf-e2e session fixture is created
and individually revoked; no password, scene, revision, or image is changed.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    from app.database import SessionLocal
    from app.features import registry
    from app.models import User
    from app.security.sessions import SESSION_COOKIE, create_session, revoke_session

    parser = argparse.ArgumentParser()
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--old-sequence", required=True, type=int)
    parser.add_argument("--current-sequence", required=True, type=int)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--candidate-module", type=Path)
    parser.add_argument("--candidate-app", type=Path)
    parser.add_argument("--steel-fixture", action="store_true",
                        help="Assert the known revision 12 silver / 13 blue-black blade ROI")
    args = parser.parse_args()
    args.evidence_dir.mkdir(exist_ok=False)
    spec = importlib.util.spec_from_file_location("scene_browser", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    installed = registry.status("media-forge")
    assert installed["health"] == "healthy"
    evidence: dict = {"installed_version": installed["version"], "scene_id": args.scene_id, "page_errors": []}
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        token = create_session(db, user, "127.0.0.1", "MediaForge read-only comparison acceptance")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
                                        args=["--enable-webgl", "--ignore-gpu-blocklist"])
            try:
                context = browser.new_context(base_url="http://127.0.0.1:8765", viewport={"width": 1280, "height": 900})
                context.add_cookies([{"name": SESSION_COOKIE, "value": token, "url": "http://127.0.0.1:8765",
                                      "httpOnly": True, "sameSite": "Lax"}])
                page = context.new_page()
                page.on("pageerror", lambda error: evidence["page_errors"].append(str(error)))
                if args.candidate_app:
                    context.grant_permissions(["local-network-access"], origin="http://127.0.0.1:8765")
                    source = args.candidate_app.read_text()
                    evidence["candidate_app_sha256"] = hashlib.sha256(source.encode()).hexdigest()
                    evidence["candidate_browser_permission"] = "local-network-access"
                    document_cdp = context.new_cdp_session(page)

                    def replace_document(event: dict) -> None:
                        assert event["responseStatusCode"] == 200
                        original = document_cdp.send("Fetch.getResponseBody", {"requestId": event["requestId"]})
                        html = base64.b64decode(original["body"]).decode() if original["base64Encoded"] else original["body"]
                        pattern = r'<script>(?:(?!</script>).)*const MODEL_VIEWER_BUNDLE(?:(?!</script>).)*</script>'
                        html, count = re.subn(pattern, lambda _: '<script>' + source + '</script>', html, flags=re.S)
                        assert count == 1
                        document_cdp.send("Fetch.fulfillRequest", {"requestId": event["requestId"], "responseCode": 200,
                            "responseHeaders": [h for h in event["responseHeaders"] if h["name"].lower() not in {"content-encoding", "content-length", "transfer-encoding"}],
                            "body": base64.b64encode(html.encode()).decode()})

                    document_cdp.on("Fetch.requestPaused", replace_document)
                    document_cdp.send("Fetch.enable", {"patterns": [{"urlPattern": "*/addon-frame/media-forge/create*", "requestStage": "Response"}]})
                frame = helpers.open_scene(page, args.scene_id)
                evidence["frontend_mode"] = "candidate_module" if args.candidate_module else "installed"
                if args.candidate_module:
                    module = args.candidate_module.read_bytes()
                    evidence["candidate_module_sha256"] = hashlib.sha256(module).hexdigest()
                    cdp = context.new_cdp_session(frame)

                    def replace_module(event: dict) -> None:
                        assert event["responseStatusCode"] == 200
                        headers = event["responseHeaders"]
                        cdp.send("Fetch.fulfillRequest", {"requestId": event["requestId"], "responseCode": 200,
                            "responseHeaders": [h for h in headers if h["name"].lower() not in {"content-encoding", "content-length", "transfer-encoding"}],
                            "body": base64.b64encode(module).decode()})

                    cdp.on("Fetch.requestPaused", replace_module)
                    cdp.send("Fetch.enable", {"patterns": [{"urlPattern": "*/addon-frame/media-forge/static/three-viewer.js*", "requestStage": "Response"}]})
                before = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
                old = next(r for r in before["revisions"] if r["sequence"] == args.old_sequence)
                current = next(r for r in before["revisions"] if r["id"] == before["scene"]["current_revision_id"])
                assert current["sequence"] == args.current_sequence
                assert old["preview_asset_id"] != current["preview_asset_id"]
                evidence["revisions"] = {"old": old, "current": current}
                frame.locator(f'[data-scene-compare="{old["id"]}"]').click()
                frame.wait_for_function("() => state.sceneCompareReady === 2")
                assert not frame.locator("#scene-compare-restore").is_disabled()
                assert frame.evaluate("() => self.origin") == "null"
                evidence["labels"] = {
                    side: frame.locator(f"#scene-compare-{side}-label").inner_text()
                    for side in ("old", "current")
                }
                evidence["captures"] = {}
                rendered = {}
                for side in ("old", "current"):
                    canvas = frame.locator(f"#scene-compare-{side}-canvas")
                    data = canvas.screenshot(path=str(args.evidence_dir / f"{side}.png"))
                    evidence["captures"][side] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                    rendered[side] = data
                assert evidence["captures"]["old"]["sha256"] != evidence["captures"]["current"]["sha256"]
                def measure(left: bytes, right: bytes) -> dict:
                    return frame.evaluate("""async values => {
                      const decode=async text=>{
                        const bitmap=await createImageBitmap(new Blob([Uint8Array.from(atob(text),c=>c.charCodeAt(0))],{type:'image/png'}));
                        const c=new OffscreenCanvas(bitmap.width,bitmap.height),ctx=c.getContext('2d');
                        ctx.drawImage(bitmap,0,0);bitmap.close();
                        const data=ctx.getImageData(0,0,c.width,c.height).data;
                        const mean=[0,0,0];let n=0;
                        for(let y=Math.floor(c.height*.2);y<Math.floor(c.height*.5);y++)for(let x=Math.floor(c.width*.497);x<Math.floor(c.width*.505);x++){
                          for(let channel=0;channel<3;channel++)mean[channel]+=data[(y*c.width+x)*4+channel];n++;
                        }
                        return {width:c.width,height:c.height,data,mean:mean.map(v=>v/n)};
                      };
                      const [a,b]=await Promise.all(values.map(decode));
                      if(a.width!==b.width||a.height!==b.height)throw Error('canvas dimensions differ');
                      let changed=0;
                      // Status glyph antialiasing is outside the WebGL render.
                      for(let i=40*a.width*4;i<a.data.length;i+=4)if(a.data[i]!==b.data[i]||a.data[i+1]!==b.data[i+1]||a.data[i+2]!==b.data[i+2])changed++;
                      return {left_blade_rgb:a.mean,right_blade_rgb:b.mean,render_changed_pixels:changed};
                    }""", [base64.b64encode(v).decode() for v in (left, right)])
                evidence["pixel_comparison"] = measure(rendered["old"], rendered["current"])
                if args.steel_fixture:
                    assert args.old_sequence == 12 and args.current_sequence == 13
                    rgb = evidence["pixel_comparison"]
                    assert min(rgb["left_blade_rgb"]) > 40, "silver metal is black"
                    assert rgb["right_blade_rgb"][2] > rgb["right_blade_rgb"][0] + 10, "blue texture is not visible"
                page.screenshot(path=str(args.evidence_dir / "comparison.png"))
                status_before = frame.locator("#scene-compare-old-status").inner_text()
                frame.evaluate("() => {window.__compareLoss = document.querySelector('#scene-compare-old-canvas').getContext('webgl2').getExtension('WEBGL_lose_context'); if(!window.__compareLoss) throw Error('context-loss extension unavailable'); window.__compareLoss.loseContext();}")
                frame.wait_for_function("() => document.querySelector('#scene-compare-old-canvas').getContext('webgl2').isContextLost()")
                page.wait_for_timeout(150)
                frame.evaluate("() => window.__compareLoss.restoreContext()")
                frame.wait_for_function("() => !document.querySelector('#scene-compare-old-canvas').getContext('webgl2').isContextLost()")
                page.wait_for_timeout(500)
                evidence["status_after_restore"] = frame.locator("#scene-compare-old-status").inner_text()
                restored = frame.locator("#scene-compare-old-canvas").screenshot(path=str(args.evidence_dir / "restored.png"))
                evidence["restored_sha256"] = hashlib.sha256(restored).hexdigest()
                assert evidence["status_after_restore"] == status_before
                evidence["context_restore_comparison"] = measure(rendered["old"], restored)
                assert evidence["context_restore_comparison"]["render_changed_pixels"] == 0
                frame.evaluate("() => {window.__compareContexts = ['old','current'].map(s=>document.querySelector(`#scene-compare-${s}-canvas`).getContext('webgl2'));}")
                frame.locator("#scene-compare-cancel").click()
                frame.wait_for_function("() => !document.querySelector('#scene-compare-dialog').open && state.sceneCompareInstances.size === 0 && state.sceneCompareHandles.size === 0")
                released = frame.evaluate("() => window.__compareContexts.map(gl => gl.isContextLost())")
                assert released == [True, True]
                evidence["closed_contexts_lost"] = released
                after = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
                assert before == after
                assert not evidence["page_errors"]
                evidence["scene_unchanged"] = True
            finally:
                browser.close()
    except Exception as error:
        evidence["failure_type"] = type(error).__name__
        raise
    finally:
        with SessionLocal() as db:
            revoke_session(db, token)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
