"""Continue clean packaged setup: install Web pack, import fixture, open GUI.

Only the dedicated standalone package on loopback 9161 is in scope. UI actions
perform installation/import/session start and stop; no global Blender writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
from typing import Any

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--resume-scene", help="Continue the same isolated scene after a failed browser observation")
    args = parser.parse_args()
    assert args.blend.is_file()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    evidence: dict[str, Any] = {"mode": "isolated_packaged_standalone", "events": [], "errors": []}
    started = time.monotonic()

    def record(stage: str, **values: Any) -> None:
        event = {"stage": stage, "elapsed_sec": round(time.monotonic() - started, 3), **values}
        evidence["events"].append(event)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(event), flush=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
                                    args=["--window-size=1280,1000"])
        page = browser.new_page(no_viewport=True, locale="ja")
        page.on("pageerror", lambda error: evidence["errors"].append(type(error).__name__))
        try:
            page.goto("http://127.0.0.1:9161")
            page.locator('#app[aria-busy="false"]').wait_for()
            page.locator("#nav-settings").click()
            initial = page.evaluate("state.blenderRuntime")
            assert initial["state"] == "ready"
            if args.resume_scene:
                assert initial["web_pack"]["state"] == "ready"
                record("resume", scene_id=args.resume_scene, runtime=initial)
            else:
                assert initial["web_pack"]["state"] == "missing"
                assert not page.evaluate("state.scenes.length")
                record("web_missing", runtime=initial)
                page.locator("#blender-web-install").click()
            deadline = time.monotonic() + 180
            while time.monotonic() < deadline:
                status = page.evaluate("state.blenderRuntime")
                operation = next((o for o in status["operations"] if o["runtime_id"] == initial["web_pack"]["pack_id"]), None)
                if status["web_pack"]["state"] == "ready":
                    break
                if operation and operation["state"] in {"failed", "canceled"}:
                    raise AssertionError(operation)
                page.wait_for_timeout(500)
            else:
                raise AssertionError("Web pack did not become ready")
            record("web_ready", runtime=status)
            page.locator("#nav-web-blender").click()
            if args.resume_scene:
                page.locator(f'[data-scene-id="{args.resume_scene}"]').click()
            else:
                page.locator("#scene-import-file").set_input_files(str(args.blend))
                page.locator("#scene-import-name").fill("Clean package GUI acceptance")
                page.locator("#scene-import-submit").click()
            page.wait_for_function("state.sceneDocument?.revision_count === 1", timeout=90_000)
            before = page.evaluate("state.sceneDocument")
            record("imported", scene=before)
            if not page.evaluate("state.blenderSessions.some(s => s.state === 'ready')"):
                page.locator("#scene-blender-open").click()
                page.wait_for_function("state.blenderSessions.some(s => s.state === 'ready')", timeout=90_000)
            # Current UI separates process start from opening its remote display.
            page.locator("#scene-blender-open").click()
            page.wait_for_function("['接続しました','Connected'].includes(document.querySelector('#scene-blender-connection').textContent)", timeout=30_000)
            session = page.evaluate("state.blenderSessions.find(s => s.state === 'ready')")
            assert session["scene_id"] == before["id"]
            expect(page.locator("#scene-blender-screen canvas")).to_be_visible()
            page.screenshot(path=str(args.evidence_dir / "gui-ready.png"))
            record("gui_ready", session=session)
            page.locator("#scene-blender-discard").click()
            page.wait_for_function("state.blenderSessions.every(s => ['stopped','failed','interrupted'].includes(s.state))", timeout=30_000)
            assert page.evaluate("state.sceneDocument.revision_count") == 1
            assert not evidence["errors"]
            record("passed", sessions=page.evaluate("state.blenderSessions"),
                   not_tested=["installed Host iframe", "image generation", "G8 ZIP", "GUI editing/save"])
        except Exception as error:
            page.screenshot(path=str(args.evidence_dir / "failure.png"))
            record("failed", error_type=type(error).__name__)
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
