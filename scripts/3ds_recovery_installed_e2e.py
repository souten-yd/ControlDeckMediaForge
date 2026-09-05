"""Installed opaque-iframe recovery-fork acceptance using the dedicated E2E user.

Reuses the guarded temporary login from 3ds8_installed_browser_e2e.py. Creates a
recovered scene through the actual UI but does not alter the original candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", default="http://127.0.0.1:8765")
    parser.add_argument("--core-url", default="http://127.0.0.1:9130")
    parser.add_argument("--control-deck-db", type=Path, required=True)
    parser.add_argument("--media-forge-data-dir", type=Path, required=True)
    parser.add_argument("--username", default="mf-e2e")
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--working-id", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("installed_helpers", Path(__file__).with_name("3ds8_installed_browser_e2e.py"))
    assert spec is not None and spec.loader is not None
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    working_root = (args.media_forge_data_dir / "scenes/working").resolve()
    candidate = (working_root / args.working_id / "scene.blend").resolve()
    assert candidate.is_relative_to(working_root) and candidate.is_file()
    digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
    evidence: dict[str, object] = {"scene_id": args.scene_id, "working_id": args.working_id,
                                   "recovery_sha256": digest, "recovery_bytes": candidate.stat().st_size}
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    with helpers.fixture_login(args.control_deck_db, args.username) as password, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(base_url=args.control_deck_url, viewport={"width": 1280, "height": 900})
            page = context.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            helpers.login(page, args.username, password)
            frame = helpers.open_scene(page, args.scene_id)
            frame.wait_for_function("id => state.sceneDocument?.id === id && !document.querySelector('#scene-recovery-fork').hidden", arg=args.scene_id)
            assert frame.evaluate("() => self.origin") == "null"
            assert frame.evaluate("() => selectedRecoveryCandidate().id") == args.working_id
            assert frame.locator("#scene-blender-recover").is_disabled()
            assert frame.locator("#scene-recovery-fork").is_enabled()
            before = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
            started = time.monotonic()
            frame.locator("#scene-recovery-fork").click()
            frame.wait_for_function("id => state.selectedSceneId !== id && !state.sceneRecoveryBusy", arg=args.scene_id, timeout=60000)
            recovered_id = frame.evaluate("() => state.selectedSceneId")
            recovered = frame.evaluate("id => call('scenes.get', {scene_id:id})", recovered_id)
            saved = recovered["revisions"][0]
            source_id = saved["source_asset_id"]
            source = page.request.get(f"{args.core_url}/api/v1/assets/{source_id}/content")
            assert source.ok
            assert hashlib.sha256(source.body()).hexdigest() == digest
            provenance = frame.evaluate("id => call('assets.provenance', {asset_id:id})", source_id)
            assert provenance["operation"] == "scene.recovery.fork"
            assert provenance["parameters"]["source_scene_id"] == args.scene_id
            assert hashlib.sha256(candidate.read_bytes()).hexdigest() == digest
            assert frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id) == before
            repeated = frame.evaluate("params => call('scenes.recovery.fork', params)", {
                "scene_id": args.scene_id, "recovery_working_id": args.working_id,
            })
            assert repeated["scene"]["id"] == recovered_id
            assert saved["dependencies"] == next(
                revision["dependencies"] for revision in before["revisions"]
                if revision["id"] == provenance["parameters"]["source_revision_id"]
            )
            assert not errors, errors
            evidence.update({"opaque_origin": "null", "recovered_scene_id": recovered_id,
                             "revision": saved, "elapsed_sec": time.monotonic() - started,
                             "original_revision_count": len(before["revisions"]), "browser_errors": errors})
            page.screenshot(path=str(args.evidence_dir / "recovered.png"), full_page=True)
        finally:
            browser.close()
    (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
