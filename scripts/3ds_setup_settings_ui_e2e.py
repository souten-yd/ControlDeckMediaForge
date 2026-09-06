"""Browser setup acceptance for the dedicated long-setup source server on 9161.

Updates isolated 4.5.9 to pinned 4.5.13, verifies active deletion protection,
then removes ONLY the unreferenced isolated 4.5.9. Never run against installed.
Run with a Playwright-capable diagnostic Python, not the product core Python.
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
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    evidence: dict[str, Any] = {"mode": "isolated_source_browser", "events": [], "errors": []}
    base, newer = "blender-4.5.9-linux-x64", "blender-4.5.13-linux-x64"
    started = time.monotonic()

    def record(stage: str, **values: Any) -> None:
        event = {"stage": stage, "elapsed_sec": round(time.monotonic() - started, 3), **values}
        evidence["events"].append(event)
        (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
        print(json.dumps(event), flush=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
            args=["--window-size=1280,1000"])
        try:
            page = browser.new_page(no_viewport=True)
            page.on("pageerror", lambda error: evidence["errors"].append(type(error).__name__))
            page.goto("http://127.0.0.1:9161")
            page.locator('#app[aria-busy="false"]').wait_for()
            page.locator("#nav-settings").click()
            initial = page.evaluate("state.blenderRuntime")
            assert initial["active_runtime_id"] == base
            assert {r["runtime_id"] for r in initial["runtimes"]} == {base}

            def details() -> None:
                if not page.locator("#blender-runtime-list").is_visible():
                    page.locator("#blender-runtime-details-label").click()

            def protect(runtime_id: str) -> None:
                details()
                page.locator(f'[data-blender-remove="{runtime_id}"]').click()
                expect(page.locator("#blender-remove-dialog")).to_be_visible()
                preview = page.evaluate("state.blenderRemovePreview")
                assert not preview["can_remove"] and "active_runtime" in preview["blocked_reasons"]
                expect(page.locator("#blender-remove-confirm")).to_be_hidden()
                page.locator("#blender-remove-cancel").click()
                record("active_remove_blocked", runtime_id=runtime_id)

            def wait_action(action: str, old_ids: list[str]) -> dict[str, Any]:
                deadline = time.monotonic() + 300
                last = None
                while time.monotonic() < deadline:
                    items = page.evaluate("state.blenderRuntime?.operations || []")
                    item = next((o for o in items if o["id"] not in old_ids and o["action"] == action), None)
                    if item and item["state"] != last:
                        last = item["state"]
                        record(action, state=last, operation_id=item["id"])
                    if item and item["state"] in {"ready", "failed", "canceled"}:
                        assert item["state"] == "ready", item
                        return item
                    page.wait_for_timeout(500)
                raise AssertionError("Runtime action did not finish")

            protect(base)
            ids = page.evaluate("state.blenderRuntime.operations.map(o => o.id)")
            page.locator("#blender-runtime-update").click()
            updated = wait_action("update", ids)
            assert updated["result"]["preflight"]["version"] == "4.5.13"
            page.wait_for_function("id => state.blenderRuntime.active_runtime_id === id", arg=newer)
            protect(newer)
            details()
            page.locator(f'[data-blender-remove="{base}"]').click()
            expect(page.locator("#blender-remove-dialog")).to_be_visible()
            preview = page.evaluate("state.blenderRemovePreview")
            assert preview["can_remove"] and preview["live_reference_count"] == preview["project_reference_count"] == 0
            ids = page.evaluate("state.blenderRuntime.operations.map(o => o.id)")
            page.locator("#blender-remove-confirm").click()
            removed = wait_action("remove", ids)
            page.wait_for_function("id => !state.blenderRuntime.runtimes.some(r => r.runtime_id === id)", arg=base)
            assert page.evaluate("state.blenderRuntime.active_runtime_id") == newer
            page.screenshot(path=str(args.evidence_dir / "updated-and-removed.png"), full_page=True)
            assert not evidence["errors"]
            record("passed", updated=updated, removed=removed,
                install_visible=page.locator("#blender-runtime-install").is_visible(),
                not_tested=["repair", "clean browser install", "installed Host iframe"])
        except Exception as error:
            record("failed", error_type=type(error).__name__)
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
