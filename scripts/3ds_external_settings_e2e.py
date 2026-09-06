"""Headed Japanese Settings acceptance against the dedicated source on 9161.

Only unregisters/re-registers its configured external reference. Never uses
managed remove/install/repair, and never targets the installed Host.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    evidence: dict = {"mode": "source_standalone_headed", "checks": [], "errors": []}
    started = time.monotonic()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
            args=["--window-size=1280,1000"])
        try:
            for width in (1280, 320):
                context = browser.new_context(viewport={"width": width, "height": 600}, locale="ja")
                page = context.new_page()
                page.on("pageerror", lambda error: evidence["errors"].append(str(error)[:200]))
                page.goto("http://127.0.0.1:9161/settings")
                page.locator('#app[aria-busy="false"]').wait_for()
                assert page.evaluate("document.documentElement.lang") == "ja"
                if not page.locator("#blender-runtime-list").is_visible():
                    page.locator("#blender-runtime-details-label").click()
                button = page.locator('[data-blender-unregister="legacy-blender-4.5.9"]')
                button.click()
                expect(page.locator("#blender-remove-title")).to_have_text("既存Blenderの登録を解除")
                expect(page.locator("#blender-remove-summary")).to_contain_text("外部Blenderのファイル")
                preview = page.evaluate("state.blenderRemovePreview")
                assert preview["can_remove"] and preview["reclaimable_bytes"] == 0
                assert preview["operation"] == "unregister"
                page.screenshot(path=str(args.evidence_dir / f"confirmation-{width}.png"), full_page=True)
                page.locator("#blender-remove-cancel").click()
                expect(button).to_be_visible()
                button.click()
                page.locator("#blender-remove-confirm").click()
                expect(page.locator("#blender-runtime-register-legacy")).to_be_visible()
                expect(button).to_have_count(0)
                page.reload()
                page.locator('#app[aria-busy="false"]').wait_for()
                expect(page.locator("#blender-runtime-register-legacy")).to_be_visible()
                assert page.evaluate("state.blenderRuntime.legacy_registration_disabled")
                assert page.evaluate("state.blenderRuntime.active_runtime_id") == "blender-4.5.9-linux-x64"
                page.locator("#blender-runtime-register-legacy").click()
                page.wait_for_function("!state.blenderRuntime.legacy_registration_disabled")
                if not page.locator("#blender-runtime-list").is_visible():
                    page.locator("#blender-runtime-details-label").click()
                expect(button).to_be_visible()
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                evidence["checks"].append({"width": width, "cancel": True, "unregister": True,
                    "reload_stays_detached": True, "register": True, "horizontal_overflow": False})
                context.close()
            assert not evidence["errors"]
            evidence["passed"] = True
        except Exception as exc:
            evidence.update(passed=False, error_type=type(exc).__name__, message=str(exc)[:300])
            raise
        finally:
            browser.close()
            evidence["elapsed_sec"] = round(time.monotonic() - started, 3)
            (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
            print(json.dumps(evidence), flush=True)


if __name__ == "__main__":
    main()
