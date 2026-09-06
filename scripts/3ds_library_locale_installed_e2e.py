"""Read-only live Host bridge -> installed MediaForge Library locale acceptance.

Only the browser's language input is a fixture. Neither bridge events nor
workspace responses are synthesized. Run using the existing Host diagnostic
Python, not MediaForge core. No global login/password or scene changes.
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
    parser.add_argument("--candidate-host-ui", action="store_true")
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--width", type=int, choices=(320, 1280), required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--paging-fixture", type=Path,
                        help="Retained installed fixture.json; verify 63 real children before locale changes at offset 60")
    args = parser.parse_args()
    fixture = json.loads(args.paging_fixture.read_text()) if args.paging_fixture else None
    if fixture:
        assert fixture["passed"] and fixture["scene_id"] == args.scene_id
        assert len(fixture["children"]) == 63 and not fixture["parents"]
    installed = registry.status("media-forge")
    assert installed["version"] == args.expected_version and installed["health"] == "healthy"
    assert installed["enabled"]
    args.evidence_dir.mkdir(parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location(
        "installed_browser", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    evidence: dict[str, object] = {"version": args.expected_version, "width": args.width,
        "host_url": args.host_url, "candidate_host_ui": args.candidate_host_ui,
        "language_input": "navigator.language + browser languagechange fixture"}
    errors: list[str] = []
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        token = create_session(db, user, "127.0.0.1", "MediaForge live locale acceptance")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False)
            try:
                context = browser.new_context(base_url=args.host_url, locale="en",
                    viewport={"width": args.width, "height": 800})
                context.add_cookies([{"name": SESSION_COOKIE, "value": token, "url": args.host_url,
                    "httpOnly": True, "sameSite": "Lax"}])
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                try:
                    frame = helpers.open_scene(page, args.scene_id)
                    assert frame.evaluate("self.origin") == "null"
                    before = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
                    source = fixture["source"] if fixture else before["revisions"][-1]["source_asset_id"]
                    frame.locator("#nav-library").click()
                    frame.locator('[data-library-media="blend"]').click()
                    target = frame.locator(f'#library-grid [data-asset-id="{source}"]')
                    frame.wait_for_function("""state.libraryMedia === 'blend' && state.libraryItems.length > 0
                      && state.libraryItems.every(item => item.mime_type === 'application/x-blender')""")
                    for _ in range(40):
                        if target.count():
                            break
                        # A filtered page can be empty while raw-row cursor advances.
                        cursor = frame.evaluate("state.libraryCursor")
                        expect(frame.locator("#library-more")).to_be_visible()
                        frame.locator("#library-more").click()
                        frame.wait_for_function("previous => state.libraryCursor !== previous", arg=cursor)
                    target.click()
                    expect(frame.locator("#detail-body")).to_have_attribute("data-asset-id", source)
                    expect(frame.locator("#detail-body dt").first).to_have_text("Prompt")
                    if fixture:
                        body = frame.locator("#detail-body")
                        children = frame.locator('[data-asset-relations="children"] [data-related-asset-id]')
                        expect(children).to_have_count(60)
                        first_page = children.evaluate_all("nodes => nodes.map(n=>n.dataset.relatedAssetId)")
                        assert frame.locator("#detail-dialog").evaluate("n => n.scrollWidth <= n.clientWidth")
                        frame.locator('[data-relations-offset="60"]').click()
                        expect(body).to_have_attribute("data-offset", "60")
                        expect(children).to_have_count(3)
                        second_page = children.evaluate_all("nodes => nodes.map(n=>n.dataset.relatedAssetId)")
                        assert len(set(first_page + second_page)) == 63
                        assert set(first_page + second_page) == set(fixture["children"])
                        expect(frame.locator('[data-relations-offset="120"]')).to_have_count(0)
                        frame.locator('[data-relations-offset="0"]').click()
                        expect(body).to_have_attribute("data-offset", "0")
                        expect(children).to_have_count(60)
                        assert children.evaluate_all("nodes => nodes.map(n=>n.dataset.relatedAssetId)") == first_page
                        frame.locator('[data-relations-offset="60"]').click()
                        expect(body).to_have_attribute("data-offset", "60")
                        expect(children).to_have_count(3)
                        evidence.update({"real_children": 63, "first_page": 60, "last_page": 3,
                                         "unique_complete_set": True, "back_restores_first_page": True})
                    snapshot = """() => ({asset: document.querySelector('#detail-body').dataset.assetId,
                      offset: document.querySelector('#detail-body').dataset.offset, filter:state.libraryMedia,
                      related:[...document.querySelectorAll('[data-related-asset-id]')].map(n=>n.dataset.relatedAssetId),
                      load:performance.timeOrigin, nonce:state.nonce, scene:state.selectedSceneId})"""
                    identity = frame.evaluate(snapshot)
                    frame.evaluate("""() => {
                      window.__localeAcceptanceEvents = [];
                      const original = state.bridgePort.onmessage;
                      state.bridgePort.onmessage = event => {
                        if(event.data?.event === 'locale.changed')
                          window.__localeAcceptanceEvents.push(event.data.data.locale);
                        original(event);
                      };
                    }""")
                    for locale in ("ja", "en"):
                        page.evaluate("""locale => {
                          Object.defineProperty(navigator, 'language', {configurable:true, get:()=>locale});
                          window.dispatchEvent(new Event('languagechange'));
                        }""", locale)
                        expect(frame.locator("html")).to_have_attribute("lang", locale)
                        expect(frame.locator("#detail-body dt").first).to_have_text(
                            "作った指示" if locale == "ja" else "Prompt")
                        expect(frame.locator("#library-media-kinds")).to_have_attribute(
                            "aria-label", "素材の種類" if locale == "ja" else "Media type")
                        assert frame.evaluate(snapshot) == identity
                        assert frame.locator("#detail-dialog").evaluate("node => node.open")
                        assert frame.locator("#detail-dialog").evaluate("node => node.scrollWidth <= node.clientWidth")
                        assert frame.evaluate("document.documentElement.scrollWidth <= innerWidth")
                        page.screenshot(path=str(args.evidence_dir / f"detail-{locale}.png"))
                    events = frame.evaluate("window.__localeAcceptanceEvents")
                    assert events == ["ja", "en"], events
                    assert frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id) == before
                    assert not errors, errors
                    evidence.update({"asset": source, "offset": identity["offset"],
                        "events": events, "selection_filter_related_load_session_preserved": True,
                        "scene_unchanged": True, "origin": "null"})
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
