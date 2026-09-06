"""Real source Settings actions on owned test server 9162; explicit locale fixture.

Uses native browser clicks and real HTTP/install/remove. Locale is supplied
through the production theme/render functions, not an installed Host event.
Never targets the installed Host or deletes scenes/assets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
import zipfile

from playwright.sync_api import expect, sync_playwright


def hashes(root: Path) -> dict[str, str]:
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--verify-preserved-ui", action="store_true")
    args = parser.parse_args()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    root = Path("/data1tb/mf-clean-packaged-0.28.32-QBvHfm/feature/data/assets")
    before = hashes(root)
    assert len(before) == 6
    old = "blender-4.5.9-linux-x64"
    evidence: dict = {"mode": "source_real_http_headed_locale_fixture", "checks": [], "errors": []}
    started = time.monotonic()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
            args=["--window-size=1280,1000"])
        try:
            for locale in ("ja", "en"):
                for width in (1280, 320):
                    context = browser.new_context(viewport={"width": width, "height": 600}, locale=locale)
                    page = context.new_page()
                    page.on("pageerror", lambda error: evidence["errors"].append(str(error)[:200]))
                    page.goto("http://127.0.0.1:9162/settings")
                    page.locator('#app[aria-busy="false"]').wait_for()
                    page.evaluate("locale => { applyTheme({locale}); renderBlenderRuntime(); }", locale)
                    scene_path = "/workspace-api/scenes/scene_2642c93f480d427d920267ac790405e2"
                    scene_before = page.request.get("http://127.0.0.1:9162" + scene_path).json()
                    if not page.locator("#blender-runtime-list").is_visible():
                        page.locator("#blender-runtime-details-label").click()
                    remove = page.locator(f'[data-blender-remove="{old}"]')
                    remove.click()
                    checkbox = page.locator("#blender-remove-history")
                    confirm = page.locator("#blender-remove-confirm")
                    expect(checkbox).to_be_visible()
                    expect(checkbox).not_to_be_checked()
                    expect(confirm).to_be_disabled()
                    expect(page.locator("#blender-remove-history-label")).to_contain_text("4.5.9")
                    expect(page.locator("#blender-remove-title")).to_have_text(
                        "Blender環境を削除" if locale == "ja" else "Remove Blender runtime")
                    checkbox.check()
                    expect(confirm).to_be_enabled()
                    page.evaluate("renderBlenderRuntime()")
                    expect(checkbox).to_be_checked()  # Refresh/locale rendering must not erase explicit acknowledgement.
                    page.locator("#blender-remove-cancel").click()
                    remove.click()
                    expect(checkbox).not_to_be_checked()  # A new dialog must never inherit acknowledgement.
                    expect(confirm).to_be_disabled()
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                    dialog = page.locator("#blender-remove-dialog")
                    assert dialog.evaluate("el => el.scrollWidth <= el.clientWidth")
                    page.screenshot(path=str(args.evidence_dir / f"dialog-{locale}-{width}.png"), full_page=True)
                    check = {"locale": locale, "width": width, "default_off": True,
                             "refresh_preserves_ack": True, "reopen_resets_ack": True, "overflow": False}
                    if width == 320:
                        checkbox.check()
                        confirm.click()
                        install = page.locator(f'[data-blender-install-exact="{old}"]')
                        expect(install).to_be_visible(timeout=60000)
                        expect(install).to_have_text("この版を導入" if locale == "ja" else "Install this version")
                        assert hashes(root) == before
                        assert page.request.get("http://127.0.0.1:9162" + scene_path).json() == scene_before
                        page.screenshot(path=str(args.evidence_dir / f"missing-{locale}.png"), full_page=True)
                        if args.verify_preserved_ui:
                            page.locator("#nav-web-blender").click()
                            page.locator('[data-scene-id="scene_2642c93f480d427d920267ac790405e2"]').click()
                            expect(page.locator("#scene-revisions .row")).to_have_count(1)
                            with page.expect_download(timeout=60000) as pending:
                                page.locator("#scene-backup-download").click()
                            download = pending.value
                            assert download.failure() is None
                            backup_path = args.evidence_dir / f"preserved-{locale}.zip"
                            download.save_as(backup_path)
                            with zipfile.ZipFile(backup_path) as archive:
                                manifest = json.loads(archive.read("manifest.json"))
                                assert manifest["document"] == scene_before["scene"]
                                assert manifest["revisions"] == scene_before["revisions"]
                                for entry in manifest["entries"]:
                                    content = archive.read(entry["path"])
                                    assert len(content) == entry["size_bytes"]
                                    assert hashlib.sha256(content).hexdigest() == entry["sha256"]
                            page.locator("[data-scene-preview]").click()
                            page.wait_for_function("viewer.modelStats && viewer.modelStats.triangles > 0")
                            expect(page.locator("#viewer-3d-canvas")).to_be_visible()
                            page.screenshot(path=str(args.evidence_dir / f"preserved-viewer-{locale}.png"))
                            page.locator("#viewer-close").click()
                            page.locator("#nav-settings").click()
                            check["missing_runtime_backup_and_glb"] = True
                        install.click()
                        expect(remove).to_be_visible(timeout=180000)
                        assert page.evaluate("state.blenderRuntime.active_runtime_id") == "blender-4.5.13-linux-x64"
                        assert hashes(root) == before
                        assert page.request.get("http://127.0.0.1:9162" + scene_path).json() == scene_before
                        check["actual_remove_and_exact_reinstall"] = True
                    else:
                        page.locator("#blender-remove-cancel").click()
                    evidence["checks"].append(check)
                    print(json.dumps(check), flush=True)
                    context.close()
            assert not evidence["errors"]
            evidence["passed"] = True
        finally:
            evidence["elapsed_sec"] = round(time.monotonic() - started, 3)
            evidence["asset_hashes"] = hashes(root)
            (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
            browser.close()


if __name__ == "__main__":
    main()
