"""Read-only installed Settings deletion previews at desktop and 320px.

Host diagnostic Python/PYTHONPATH. Dedicated individual login, no password
changes, deletion submission, runtime installation, overlays or scene writes.
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
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--require-readable-layout", action="store_true")
    parser.add_argument("--native-viewport", action="store_true", help="Diagnose pointer input without viewport emulation")
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    status = registry.status("media-forge")
    assert status["version"] == args.expected_version and status["enabled"] and status["health"] == "healthy"
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location("helper", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    evidence = {"version": status["version"], "mode": "installed_no_overlay", "previews": [], "layouts": [], "errors": []}
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        token = create_session(db, user, "127.0.0.1", "MediaForge Settings protection acceptance")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
                args=["--window-size=1280,1000"])
            try:
                context = browser.new_context(base_url="http://127.0.0.1:8765", no_viewport=True)
                context.add_cookies([{"name": SESSION_COOKIE, "value": token,
                    "url": "http://127.0.0.1:8765", "httpOnly": True, "sameSite": "Lax"}])
                page = context.new_page()
                page.on("pageerror", lambda error: evidence["errors"].append(type(error).__name__))
                page.goto("/x/media-forge/workspace/create")
                frame = helpers.workspace_frame(page)
                frame.locator('#app[aria-busy="false"]').wait_for()
                assert frame.evaluate("self.origin") == "null"
                before = frame.evaluate("() => call('blender.runtime.status', {})")
                assert before["active_runtime_id"] == "blender-4.5.13-linux-x64"
                runtimes = [r["runtime_id"] for r in before["runtimes"] if r["ownership"] == "managed"]
                assert set(runtimes) == {"blender-4.5.9-linux-x64", "blender-4.5.13-linux-x64"}
                frame.locator("#nav-settings").click()
                if not frame.locator("#blender-runtime-list").is_visible():
                    frame.locator("#blender-runtime-details-label").click()
                for width in ((1280,) if args.native_viewport else (1280, 320)):
                    if not args.native_viewport:
                        page.set_viewport_size({"width": width, "height": 900})
                    evidence["layouts"].append(frame.evaluate("""() => ({
                        width: innerWidth, client: document.documentElement.clientWidth,
                        scroll: document.documentElement.scrollWidth,
                        rows: [...document.querySelectorAll('#blender-runtime-list .row')].map(row => ({
                            width: row.getBoundingClientRect().width,
                            text: row.firstElementChild.getBoundingClientRect().width,
                            controls: row.lastElementChild.getBoundingClientRect().width
                        }))
                    })"""))
                    if args.require_readable_layout:
                        layout = evidence["layouts"][-1]
                        assert all(row["text"] >= 100 for row in layout["rows"]), layout
                        assert layout["scroll"] <= layout["client"], layout
                    for runtime_id in runtimes:
                        for target in (page, frame):
                            target.evaluate("""() => {
                                window.__settingsPointerEvents = [];
                                if (window.__settingsPointerListening) return;
                                window.__settingsPointerListening = true;
                                for (const type of ['pointerdown', 'pointerup', 'click']) {
                                    document.addEventListener(type, e => {
                                        window.__settingsPointerEvents.push({type, tag: e.target.tagName,
                                            id: e.target.id, x: e.clientX, y: e.clientY});
                                    }, true);
                                }
                            }""")
                        button = frame.locator(f'[data-blender-remove="{runtime_id}"]')
                        button.scroll_into_view_if_needed()
                        diagnostic = {"runtime_id": runtime_id, "requested_width": width,
                            "native_viewport": args.native_viewport,
                            "button": button.bounding_box(),
                            "screen": page.evaluate("""() => ({innerWidth, innerHeight,
                                outerWidth, outerHeight, screenHeight: screen.height,
                                dpr: devicePixelRatio})""")}
                        evidence.setdefault("pointer_diagnostics", []).append(diagnostic)
                        try:
                            button.click()
                            expect(frame.locator("#blender-remove-dialog")).to_be_visible()
                        finally:
                            diagnostic["host_events"] = page.evaluate("window.__settingsPointerEvents")
                            diagnostic["frame_events"] = frame.evaluate("window.__settingsPointerEvents")
                            diagnostic["preview_received"] = frame.evaluate("state.blenderRemovePreview !== null")
                            diagnostic["dialog_open"] = frame.locator("#blender-remove-dialog").evaluate("e => e.open")
                            page.screenshot(path=str(args.evidence_dir / f"pointer-{width}-{runtime_id}.png"))
                        expect(frame.locator("#blender-remove-dialog")).to_be_visible()
                        preview = frame.evaluate("state.blenderRemovePreview")
                        assert not preview["can_remove"]
                        assert preview["project_reference_count"] > 0 and "project_reference" in preview["blocked_reasons"]
                        if runtime_id == before["active_runtime_id"]:
                            assert "active_runtime" in preview["blocked_reasons"]
                        expect(frame.locator("#blender-remove-confirm")).to_be_hidden()
                        expect(frame.locator("#blender-remove-cancel")).to_be_visible()
                        evidence["previews"].append({"width": width, **preview})
                        page.screenshot(path=str(args.evidence_dir / f"preview-{width}-{runtime_id}.png"))
                        frame.locator("#blender-remove-cancel").click()
                after = frame.evaluate("() => call('blender.runtime.status', {})")
                assert after == before, "Runtime state or operation journal changed"
                assert not evidence["errors"]
                evidence["runtime_state_unchanged"] = True
            finally:
                browser.close()
    finally:
        with SessionLocal() as db:
            revoke_session(db, token)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence), flush=True)


if __name__ == "__main__":
    main()
