"""Verify installed opaque viewer pixels using an existing owned static scene.

Host diagnostic venv only. Uses a dedicated mf-e2e session fixture, not a password
change; revokes exactly that session on exit. No authoring or generation;
the viewer may populate its normal thumbnail cache. Candidate overlay mode
changes only this browser's response bodies and is not installed acceptance.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


def main() -> None:
    from app.database import SessionLocal
    from app.features import registry
    from app.models import User
    from app.security.sessions import SESSION_COOKIE, create_session, revoke_session

    parser = argparse.ArgumentParser()
    parser.add_argument("--host-url", default="http://127.0.0.1:8765")
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--candidate-frontend", type=Path,
                        help="Browser-only candidate overlay; NOT installed release acceptance")
    args = parser.parse_args()
    args.evidence_dir.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("scene_browser", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    installed = registry.status("media-forge")
    assert installed["health"] == "healthy"
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        token = create_session(db, user, "127.0.0.1", "MediaForge viewer pixel acceptance")
    evidence: dict = {"version": installed["version"], "scene_id": args.scene_id, "captures": {}, "comparisons": {}}
    evidence["frontend_mode"] = "candidate_overlay" if args.candidate_frontend else "installed"
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
                args=["--enable-webgl", "--ignore-gpu-blocklist"])
            page = None
            frame = None
            try:
                context = browser.new_context(base_url=args.host_url, viewport={"width": 1280, "height": 900})
                context.add_cookies([{"name": SESSION_COOKIE, "value": token, "url": args.host_url, "httpOnly": True, "sameSite": "Lax"}])
                page = context.new_page()
                if args.candidate_frontend:
                    context.grant_permissions(["local-network-access"], origin=args.host_url)
                    evidence["candidate_browser_permission"] = "local-network-access"
                    candidate = args.candidate_frontend.resolve()
                    evidence["candidate_sha256"] = {
                        name: hashlib.sha256((candidate / name).read_bytes()).hexdigest()
                        for name in ("app.js", "index.html", "three-viewer.js")
                    }
                    pattern = r'(<div id="viewer-3d-tools"[^>]*>)(.*?)(</div>)'
                    toolbar = re.search(pattern, (candidate / "index.html").read_text(), re.S)
                    assert toolbar

                    cdp = context.new_cdp_session(page)

                    def overlay(event: dict) -> None:
                        request_id = event["requestId"]
                        path = urlsplit(event["request"]["url"]).path
                        status = event.get("responseStatusCode", 0)
                        evidence.setdefault("candidate_requests", []).append({
                            "path": path, "status": status,
                        })
                        if status != 200:
                            cdp.send("Fetch.continueResponse", {"requestId": request_id})
                            return
                        headers = event.get("responseHeaders", [])
                        content_type = next((h["value"] for h in headers if h["name"].lower() == "content-type"), "")
                        if path.endswith("/app.js"):
                            body = (candidate / "app.js").read_bytes()
                        elif path.endswith("/static/three-viewer.js"):
                            body = (candidate / "three-viewer.js").read_bytes()
                        elif "text/html" in content_type:
                            original = cdp.send("Fetch.getResponseBody", {"requestId": request_id})
                            html = base64.b64decode(original["body"]).decode() if original["base64Encoded"] else original["body"]
                            html, count = re.subn(pattern, lambda _: toolbar.group(0), html, flags=re.S)
                            assert count == 1
                            script_pattern = r'<script>(?:(?!</script>).)*const MODEL_VIEWER_BUNDLE(?:(?!</script>).)*</script>'
                            html, count = re.subn(script_pattern, lambda _: '<script>' + (candidate / "app.js").read_text() + '</script>', html, flags=re.S)
                            assert count == 1
                            body = html.encode()
                        else:
                            cdp.send("Fetch.continueResponse", {"requestId": request_id})
                            return
                        cdp.send("Fetch.fulfillRequest", {
                            "requestId": request_id, "responseCode": status,
                            "responseHeaders": [h for h in headers if h["name"].lower() not in {"content-encoding", "content-length", "transfer-encoding"}],
                            "body": base64.b64encode(body).decode(),
                        })

                    cdp.on("Fetch.requestPaused", overlay)
                    cdp.send("Fetch.enable", {"patterns": [{"urlPattern": "*/addon-frame/media-forge/*", "requestStage": "Response"}]})
                errors: list[str] = []
                evidence["page_errors"] = errors
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
                frame = helpers.open_scene(page, args.scene_id)
                if args.candidate_frontend:
                    # Chrome isolates the opaque iframe in another target. Its
                    # module response must be intercepted on that target too.
                    cdp = context.new_cdp_session(frame)
                    cdp.on("Fetch.requestPaused", overlay)
                    cdp.send("Fetch.enable", {"patterns": [{"urlPattern": "*/addon-frame/media-forge/static/three-viewer.js*", "requestStage": "Response"}]})
                before = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
                preview = before["revisions"][0]["preview_asset_id"]
                frame.locator("#nav-library").click()
                frame.wait_for_selector("#library-grid .card")
                frame.locator('[data-library-media="3d"]').click()
                frame.wait_for_function("() => {const cards=[...document.querySelectorAll('#library-grid .card')]; return cards.length && cards.every(c=>c.dataset.mediaKind==='3d')}")
                target = frame.locator(f'#library-grid [data-asset-id="{preview}"]')
                for _ in range(20):
                    if target.count():
                        break
                    count = frame.locator("#library-grid .card").count()
                    assert frame.locator("#library-more").is_visible(), "fixture absent from Library"
                    frame.locator("#library-more").click()
                    frame.wait_for_function("n => document.querySelectorAll('#library-grid .card').length > n", arg=count)
                assert target.count() == 1
                target.click()
                evidence["entrypoint"] = "Library / 3D / asset card"
                frame.wait_for_function("id => document.querySelector('#viewer-3d-canvas').dataset.modelAssetId === id", arg=preview)
                canvas = frame.locator("#viewer-3d-canvas")
                assert frame.evaluate("() => self.origin") == "null"
                evidence["preview_asset_id"] = preview
                evidence["stats"] = frame.locator("#viewer-3d-stats").inner_text()
                evidence["opaque_origin"] = "null"
                evidence["renderer"] = canvas.evaluate("""canvas => {
                  const gl=canvas.getContext('webgl2'), ext=gl.getExtension('WEBGL_debug_renderer_info');
                  return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'not_exposed';
                }""")

                def capture(name: str) -> bytes:
                    page.wait_for_timeout(150)
                    data = canvas.screenshot(path=str(args.evidence_dir / f"{name}.png"))
                    evidence["captures"][name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                    return data

                def compare(name: str, left: bytes, right: bytes, *, changed: bool) -> None:
                    measured = frame.evaluate("""async values => {
                      const decode = async text => {
                        const bitmap = await createImageBitmap(new Blob([Uint8Array.from(atob(text), c => c.charCodeAt(0))], {type:'image/png'}));
                        const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
                        const ctx = canvas.getContext('2d'); ctx.drawImage(bitmap, 0, 0); bitmap.close();
                        return {width:canvas.width,height:canvas.height,data:ctx.getImageData(0,0,canvas.width,canvas.height).data};
                      };
                      const [a,b] = await Promise.all(values.map(decode));
                      if (a.width !== b.width || a.height !== b.height) throw Error('capture dimensions differ');
                      let pixels=0;
                      for(let i=0;i<a.data.length;i+=4) {
                        if(Math.max(Math.abs(a.data[i]-b.data[i]),Math.abs(a.data[i+1]-b.data[i+1]),Math.abs(a.data[i+2]-b.data[i+2]))>10) pixels++;
                      }
                      return {changed_pixels:pixels,fraction:pixels/(a.width*a.height)};
                    }""", [base64.b64encode(value).decode("ascii") for value in (left, right)])
                    fraction = measured["fraction"]
                    evidence["comparisons"][name] = measured
                    # A thin sword rotated about its long axis occupies much
                    # less than 0.5% of the viewport. Require actual changed
                    # pixels, with exact idle/inverse restoration as controls.
                    assert measured["changed_pixels"] > 100 if changed else fraction == 0, (name, measured)

                initial = capture("material_initial")
                compare("idle_stable", initial, capture("material_idle"), changed=False)
                for axis in ("x", "y", "z"):
                    for direction in (1, -1):
                        frame.locator(f'[data-viewer-rotate="{axis}"][data-direction="{direction}"]').click()
                        rotated_axis = capture(f"{axis}_{direction}")
                        compare(f"{axis}_{direction}", initial, rotated_axis, changed=True)
                        frame.locator(f'[data-viewer-rotate="{axis}"][data-direction="{-direction}"]').click()
                        compare(f"{axis}_{direction}_restored", initial, capture(f"{axis}_{direction}_restored"), changed=False)
                frame.locator("#viewer-3d-zoom-in").click()
                compare("zoom_button_in", initial, capture("zoom_button_in"), changed=True)
                frame.locator("#viewer-3d-zoom-out").click()
                compare("zoom_button_restored", initial, capture("zoom_button_restored"), changed=False)
                frame.locator("#viewer-3d-zoom-out").click()
                compare("zoom_button_out", initial, capture("zoom_button_out"), changed=True)
                frame.locator("#viewer-3d-fit").click()
                box = canvas.bounding_box()
                assert box and box["width"] > 100 and box["height"] > 100
                page.mouse.move(box["x"] + box["width"] * .4, box["y"] + box["height"] * .5)
                page.mouse.down()
                page.mouse.move(box["x"] + box["width"] * .65, box["y"] + box["height"] * .35, steps=12)
                page.mouse.up()
                rotated = capture("orbit")
                compare("orbit", initial, rotated, changed=True)
                page.mouse.wheel(0, -400)
                zoomed = capture("zoom")
                compare("zoom", rotated, zoomed, changed=True)
                frame.locator("#viewer-3d-fit").click()
                fitted = capture("fit")
                compare("fit_restores_camera", initial, fitted, changed=False)
                page.set_viewport_size({"width": 320, "height": 640})
                page.wait_for_timeout(200)
                mobile = frame.evaluate("() => ({inner:innerWidth,scroll:document.scrollingElement.scrollWidth})")
                assert mobile["scroll"] <= mobile["inner"]
                evidence["mobile"] = mobile
                capture("mobile")
                assert frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id) == before
                assert not errors, errors
                evidence["page_errors"] = errors
                evidence["scene_unchanged"] = True
            except Exception as error:
                evidence["failure_type"] = type(error).__name__
                if page and not page.is_closed() and frame:
                    evidence["viewer_state"] = frame.evaluate("""() => ({
                      loading:document.querySelector('#viewer-3d-loading')?.textContent,
                      caption:document.querySelector('#viewer-caption')?.textContent,
                      asset:document.querySelector('#viewer-3d-canvas')?.dataset.modelAssetId
                    })""")
                    page.screenshot(path=str(args.evidence_dir / "failure.png"))
                raise
            finally:
                browser.close()
    finally:
        with SessionLocal() as db:
            revoke_session(db, token)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
