"""Long-lived installed RFB acceptance using one dedicated mf-e2e session.

Host diagnostic Python only. No overlays, password changes, TTL changes or
service restarts. A successful run adds a revision to the explicitly selected
test scene; a failed run stops only the Blender session created by this run.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import time
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
    installed = registry.status("media-forge")
    assert installed["version"] == args.expected_version
    assert installed["enabled"] and installed["health"] == "healthy"
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location(
        "helper", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    evidence: dict[str, Any] = {"version": installed["version"], "scene_id": args.scene_id,
        "mode": "installed_no_overlay", "events": [], "page_errors": []}
    started = time.monotonic()

    def record(stage: str, **values: Any) -> None:
        event = {"stage": stage, "elapsed_sec": round(time.monotonic() - started, 3), **values}
        evidence["events"].append(event)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(event), flush=True)

    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "mf-e2e").one()
        assert user.is_active
        token = create_session(db, user, "127.0.0.1", "MediaForge RFB renewal acceptance")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
                args=["--enable-webgl", "--ignore-gpu-blocklist", "--window-size=1280,1000"])
            frame = None
            session_id = None
            try:
                context = browser.new_context(base_url="http://127.0.0.1:8765", no_viewport=True)
                context.add_cookies([{"name": SESSION_COOKIE, "value": token,
                    "url": "http://127.0.0.1:8765", "httpOnly": True, "sameSite": "Lax"}])
                page = context.new_page()
                page.on("pageerror", lambda error: evidence["page_errors"].append(type(error).__name__))
                frame = helpers.open_scene(page, args.scene_id)
                assert frame.evaluate("self.origin") == "null"
                assert helpers.session_projection(frame, args.scene_id) is None, "Existing session: do not take over"
                before = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
                evidence["before"] = before
                # Record ownership immediately, including when startup later fails.
                created = frame.evaluate("id => call('blender.sessions.start', {scene_id:id})", args.scene_id)
                session_id = created["id"]
                record("created", session_id=session_id)
                ready = helpers.wait_session(frame, args.scene_id, {"ready"}, timeout=90)
                assert ready["id"] == session_id
                frame.evaluate("() => refreshSession(['blender_sessions'])")
                frame.locator("#scene-blender-open").click()
                frame.wait_for_function("() => state.blenderRfb?._rfbConnectionState === 'connected'", timeout=30000)
                connected_at = time.monotonic()
                # Observe object identity only; never record bearer/nonce/protocol headers.
                frame.evaluate("() => { window.__renewalRfbs = new Set(); }")
                while True:
                    current = helpers.session_projection(frame, args.scene_id)
                    assert current and current["id"] == session_id and current["state"] == "ready", "Session lost before renewal acceptance"
                    observation = frame.evaluate("""() => {
                        const rfb = state.blenderRfb;
                        if (rfb?._rfbConnectionState === 'connected') window.__renewalRfbs.add(rfb);
                        return {connected: rfb?._rfbConnectionState === 'connected',
                                connections: window.__renewalRfbs.size};
                    }""")
                    held = time.monotonic() - connected_at
                    record("holding", held_sec=round(held, 3), **observation)
                    if held >= 660:
                        assert observation["connected"] and observation["connections"] >= 2, "No successful automatic reconnect"
                        break
                    if observation["connected"]:
                        frame.locator("#scene-blender-screen canvas").click(position={"x": 320, "y": 240})
                        page.keyboard.press("Shift")
                    page.wait_for_timeout(30000)
                # Real remote edit AFTER the original credential's lifetime.
                page.keyboard.press("a")
                page.wait_for_timeout(500)
                page.keyboard.press("Shift+D")
                page.wait_for_timeout(500)
                page.keyboard.press("Escape")
                page.wait_for_timeout(1000)
                page.screenshot(path=str(args.evidence_dir / "after-renewal-edit.png"))
                frame.locator("#scene-blender-save").click()
                frame.wait_for_function("n => state.sceneRevisions.length === n",
                    arg=len(before["revisions"]) + 1, timeout=90000)
                after = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
                evidence["after"] = after
                assert all(revision in after["revisions"] for revision in before["revisions"])
                def mesh_count(scene: dict[str, Any]) -> int:
                    revision = next(r for r in scene["revisions"] if r["id"] == scene["scene"]["current_revision_id"])
                    return next(v["facts"]["meshes"] for v in revision["validation"] if v["validator"] == "blender.scene")
                assert mesh_count(before) > 0 and mesh_count(after) == 2 * mesh_count(before)
                assert helpers.session_projection(frame, args.scene_id) is None
                assert not evidence["page_errors"]
                record("passed", same_session=True, gui_edit_saved=True)
            except Exception as error:
                record("failed", error_type=type(error).__name__)
                raise
            finally:
                try:
                    if frame is not None and session_id is not None:
                        current = helpers.session_projection(frame, args.scene_id)
                        if current and current["id"] == session_id:
                            frame.evaluate("id => call('blender.sessions.stop', {session_id:id})", session_id)
                            deadline = time.monotonic() + 30
                            while helpers.session_projection(frame, args.scene_id) is not None:
                                if time.monotonic() >= deadline:
                                    raise RuntimeError("Owned session cleanup did not finish")
                                page.wait_for_timeout(250)
                        record("cleanup", owned_session_terminal=True)
                finally:
                    browser.close()
    finally:
        with SessionLocal() as db:
            revoke_session(db, token)
        record("login_revoked")


if __name__ == "__main__":
    main()
