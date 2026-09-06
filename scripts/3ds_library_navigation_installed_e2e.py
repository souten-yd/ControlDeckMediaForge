"""Read-only installed Library/navigation acceptance with a dedicated login.

Run with the Host diagnostic Python/PYTHONPATH, never the product core venv.
No password changes, frontend overlays, generation, or scene writes.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    from app.database import SessionLocal
    from app.features import registry
    from app.models import User
    from app.security.sessions import SESSION_COOKIE, create_session, revoke_session

    parser = argparse.ArgumentParser()
    parser.add_argument("--host-url", default="http://127.0.0.1:8765")
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--require-scroll-lock", action="store_true")
    parser.add_argument("--locale", choices=("ja", "en"), default="en")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    installed = registry.status("media-forge")
    assert installed["version"] == args.expected_version
    assert installed["health"] == "healthy" and installed["enabled"]
    args.evidence_dir.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location(
        "installed_browser", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    evidence: dict[str, object] = {"version": installed["version"], "scene_id": args.scene_id,
                                   "mode": "installed_no_overlay", "requested_locale": args.locale,
                                   "headless": args.headless}
    errors: list[str] = []
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        token = create_session(db, user, "127.0.0.1", "MediaForge Library navigation acceptance")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=args.headless,
                args=["--enable-webgl", "--ignore-gpu-blocklist", "--window-size=1280,1000"])
            try:
                context = browser.new_context(base_url=args.host_url, no_viewport=True, locale=args.locale)
                context.add_cookies([{"name": SESSION_COOKIE, "value": token, "url": args.host_url,
                                     "httpOnly": True, "sameSite": "Lax"}])
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    frame = helpers.open_scene(page, args.scene_id)
                    evidence["host_language"] = page.evaluate("navigator.language")
                    evidence["frame_language"] = frame.evaluate("document.documentElement.lang")
                    assert evidence["host_language"] == args.locale
                    assert evidence["frame_language"] == args.locale
                    before = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
                    revision = before["revisions"][-1]
                    source, glb = revision["source_asset_id"], revision["preview_asset_id"]
                    texture = revision["dependencies"][0]["asset_id"]
                    assert frame.evaluate("self.origin") == "null"
                    # Count actual private workspace requests, without replacing execution.
                    frame.evaluate("""() => {
                      window.__libraryAcceptanceReads = [];
                      const original = call;
                      call = function(method, params) {
                        window.__libraryAcceptanceReads.push(method);
                        return original(method, params);
                      };
                    }""")
                    rows: list[dict[str, object]] = []
                    for width in (1280, 320):
                        if width == 320:
                            page.set_viewport_size({"width": 320, "height": 700})
                        for view in ("create", "library", "activity", "web-blender"):
                            frame.locator(f"#nav-{view}").click()
                            expect(frame.locator(f"#nav-{view}")).to_have_attribute("aria-current", "page")
                        assert frame.locator("#scene-studio").is_visible()
                        frame.locator("#nav-settings").click()
                        frame.locator("#nav-settings").click()
                        assert frame.locator("#scene-studio").is_visible()
                        frame.locator("#nav-library").click()
                        expect(frame.locator("#library-media-kinds")).to_have_attribute(
                            "aria-label", "素材の種類" if args.locale == "ja" else "Media type")
                        expect(frame.locator('[data-library-media="image"]')).to_have_text(
                            "画像" if args.locale == "ja" else "Images")
                        for kind, mime in (("image", "image/png"), ("glb", "model/gltf-binary"),
                                           ("blend", "application/x-blender")):
                            frame.locator(f'[data-library-media="{kind}"]').click()
                            frame.wait_for_function(
                                "mime => state.libraryItems.length > 0 && state.libraryItems.every(i => i.mime_type === mime)", arg=mime)
                            rows.append({"width": width, "filter": kind,
                                         "count": frame.locator("#library-grid .card").count()})
                        target = frame.locator(f'#library-grid [data-asset-id="{source}"]')
                        for _ in range(30):
                            if target.count():
                                break
                            count = frame.locator("#library-grid .card").count()
                            expect(frame.locator("#library-more")).to_be_visible()
                            frame.locator("#library-more").click()
                            frame.wait_for_function("n => state.libraryItems.length > n", arg=count)
                        target.click()
                        expect(frame.locator("#detail-body")).to_have_attribute("data-asset-id", source)
                        expect(frame.locator("#detail-preview")).to_have_count(0)
                        for direction, asset in (("parents", texture), ("children", source),
                                                  ("children", glb), ("parents", source)):
                            frame.locator(f'[data-asset-relations="{direction}"] [data-related-asset-id="{asset}"]').click()
                            expect(frame.locator("#detail-body")).to_have_attribute("data-asset-id", asset)
                        page.screenshot(path=str(args.evidence_dir / f"lineage-{width}.png"))
                        frame.locator("#close-dialog").click()
                    methods = frame.evaluate("window.__libraryAcceptanceReads")
                    assert not any("model." in method or method == "assets.content" for method in methods), methods
                    target.click()
                    frame.locator(f'[data-asset-relations="children"] [data-related-asset-id="{glb}"]').click()
                    expect(frame.locator("#detail-body")).to_have_attribute("data-asset-id", glb)
                    frame.locator("#detail-preview").click()
                    frame.wait_for_function("id => document.querySelector('#viewer-3d-canvas').dataset.modelAssetId === id", arg=glb)
                    assert frame.locator("#viewer-edit").is_hidden()
                    evidence["viewer_layout"] = frame.evaluate("""() => ({
                        inner_width: innerWidth, root_client: document.scrollingElement.clientWidth,
                        root_scroll: document.scrollingElement.scrollWidth,
                        viewer_client: document.querySelector('#viewer').clientWidth,
                        viewer_scroll: document.querySelector('#viewer').scrollWidth,
                        root_overflow: getComputedStyle(document.documentElement).overflow
                    })""")
                    if args.require_scroll_lock:
                        layout = evidence["viewer_layout"]
                        assert layout["root_scroll"] <= layout["root_client"], layout
                        assert layout["root_overflow"] == "hidden", layout
                    page.screenshot(path=str(args.evidence_dir / "explicit-glb.png"))
                    frame.locator("#viewer-close").click()
                    if args.require_scroll_lock:
                        assert frame.evaluate("getComputedStyle(document.documentElement).overflow") != "hidden"
                    assert frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id) == before
                    assert not errors, errors
                    evidence.update({"filters": rows, "source": source, "glb": glb, "texture": texture,
                        "origin": "null", "scene_unchanged": True, "bidirectional_lineage": True,
                        "explicit_glb_preview": True, "navigation_model_reads": 0})
                except Exception as error:
                    evidence["failure_type"] = type(error).__name__
                    page.screenshot(path=str(args.evidence_dir / "failure.png"))
                    raise
            finally:
                browser.close()
    finally:
        with SessionLocal() as db:
            revoke_session(db, token)
        evidence["page_errors"] = errors
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()
