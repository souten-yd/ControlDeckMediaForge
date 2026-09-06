"""Read-only installed comparison pointer hit-test; no scene mutation or overlay."""
from __future__ import annotations

import argparse
import importlib.util
import json
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
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--bottom", action="store_true", help="Place comparison near the viewport bottom")
    parser.add_argument("--native-viewport", action="store_true", help="Use the native headed window without viewport emulation")
    args = parser.parse_args()
    args.evidence_dir.mkdir(exist_ok=False)
    spec = importlib.util.spec_from_file_location("helper", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    evidence: dict[str, Any] = {"scene_id": args.scene_id, "version": registry.status("media-forge")["version"]}
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        token = create_session(db, user, "127.0.0.1", "Read-only MediaForge comparison hit-test")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
                                        args=["--enable-webgl", "--ignore-gpu-blocklist", "--window-size=1280,1000"])
            try:
                context = browser.new_context(base_url="http://127.0.0.1:8765",
                                              **({"no_viewport": True} if args.native_viewport else {"viewport": {"width": 1280, "height": 900}}))
                evidence["native_viewport"] = args.native_viewport
                context.add_cookies([{"name": SESSION_COOKIE, "value": token, "url": "http://127.0.0.1:8765", "httpOnly": True, "sameSite": "Lax"}])
                page = context.new_page()
                cdp = context.new_cdp_session(page)
                evidence["native_window"] = cdp.send("Browser.getWindowForTarget")
                frame = helpers.open_scene(page, args.scene_id)
                before = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
                evidence["screen"] = page.evaluate("() => ({innerHeight,outerHeight,screenHeight:screen.height,availableHeight:screen.availHeight,dpr:devicePixelRatio})")
                for target in (page, frame):
                    target.evaluate("""() => {
                      window.__hitEvents=[];
                      for(const type of ['pointerdown','pointerup','click']) document.addEventListener(type,e=>{
                        window.__hitEvents.push({type,tag:e.target.tagName,id:e.target.id,x:e.clientX,y:e.clientY});
                      },true);
                    }""")
                button = frame.locator("[data-scene-compare]").first
                frame.locator("#scene-material-title").click()
                button.scroll_into_view_if_needed()
                button.hover()
                if args.bottom:
                    button.evaluate("e => {const r=e.getBoundingClientRect();scrollBy(0,r.y+r.height/2-(innerHeight-18));}")
                    page.wait_for_timeout(100)
                evidence["button_box"] = button.bounding_box()
                evidence["button_dom"] = button.evaluate("""e => {
                  const r=e.getBoundingClientRect();const hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
                  return {rect:r.toJSON(),hitTag:hit?.tagName,hitId:hit?.id,hitIsButton:hit===e,
                    innerWidth,innerHeight,scrollX,scrollY,scale:visualViewport.scale};
                }""")
                iframe = frame.frame_element()
                evidence["iframe"] = iframe.evaluate("""e => {
                  const r=e.getBoundingClientRect(),s=getComputedStyle(e);
                  return {rect:r.toJSON(),zoom:s.zoom,transform:s.transform,pointerEvents:s.pointerEvents,
                    innerWidth,innerHeight,scrollX,scrollY,scale:visualViewport.scale};
                }""")
                box = evidence["button_box"]
                evidence["host_hit"] = page.evaluate("""p => {
                  const e=document.elementFromPoint(p.x+p.width/2,p.y+p.height/2);
                  return {tag:e?.tagName,id:e?.id,className:typeof e?.className==='string'?e.className:''};
                }""", box)
                page.screenshot(path=str(args.evidence_dir / "before.png"))
                button.click(timeout=5000)
                page.wait_for_timeout(1000)
                evidence["pointer_open"] = frame.locator("#scene-compare-dialog").evaluate("e=>e.open")
                evidence["host_events"] = page.evaluate("window.__hitEvents")
                evidence["frame_events"] = frame.evaluate("window.__hitEvents")
                page.screenshot(path=str(args.evidence_dir / "after-pointer.png"))
                if not evidence["pointer_open"]:
                    button.focus()
                    button.press("Enter")
                    page.wait_for_timeout(1000)
                    evidence["keyboard_open"] = frame.locator("#scene-compare-dialog").evaluate("e=>e.open")
                if frame.locator("#scene-compare-dialog").evaluate("e=>e.open"):
                    frame.locator("#scene-compare-cancel").click()
                after = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
                evidence["scene_unchanged"] = before == after
                assert evidence["scene_unchanged"]
            finally:
                browser.close()
    finally:
        with SessionLocal() as db:
            revoke_session(db, token)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
