"""Real Settings install from an empty isolated packaged Blender registry.

The dedicated package must already be serving on loopback 9161. This is a
standalone packaged test, not an installed Host iframe or image/GPU acceptance.
No transport fixtures, direct install API calls, or existing runtime reuse.
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
        context = browser.new_context(no_viewport=True, locale="ja")

        def open_settings() -> Any:
            page = context.new_page()
            page.on("pageerror", lambda error: evidence["errors"].append(type(error).__name__))
            page.goto("http://127.0.0.1:9161")
            page.locator('#app[aria-busy="false"]').wait_for()
            page.locator("#nav-settings").click()
            return page

        try:
            page = open_settings()
            initial = page.evaluate("state.blenderRuntime")
            assert initial["state"] == "missing" and not initial["runtimes"]
            assert not initial["operations"] and not initial["active_runtime_id"]
            assert initial["web_pack"]["state"] == "missing"
            expect(page.locator("#blender-runtime-install")).to_be_visible()
            expect(page.locator("#blender-web-install")).to_be_visible()
            record("empty", runtime=initial)
            page.screenshot(path=str(args.evidence_dir / "empty.png"), full_page=True)
            page.locator("#blender-runtime-install").click()
            page.wait_for_function("state.blenderRuntime.operations.length === 1")
            operation = page.evaluate("state.blenderRuntime.operations[0]")
            assert operation["action"] == "install"
            assert operation["state"] not in {"ready", "failed", "canceled"}
            record("closing_during_install", operation=operation)
            page.close()
            page = open_settings()
            page.wait_for_function("state.blenderRuntime.operations.length === 1")
            resumed = page.evaluate("state.blenderRuntime.operations[0]")
            assert resumed["id"] == operation["id"]
            record("reopened", operation=resumed)
            deadline = time.monotonic() + 300
            previous = None
            while time.monotonic() < deadline:
                current = page.evaluate("state.blenderRuntime.operations[0]")
                if current["state"] != previous:
                    previous = current["state"]
                    record("progress", state=previous, operation_id=current["id"], bytes_done=current["bytes_done"])
                if current["state"] in {"ready", "failed", "canceled"}:
                    assert current["state"] == "ready", current
                    break
                page.wait_for_timeout(500)
            else:
                raise AssertionError("Clean install did not finish within observation deadline")
            page.wait_for_function("state.blenderRuntime.state === 'ready'")
            final = page.evaluate("state.blenderRuntime")
            assert final["active_runtime_id"] == "blender-4.5.9-linux-x64"
            assert len(final["runtimes"]) == len(final["operations"]) == 1
            assert final["web_pack"]["state"] == "missing"
            assert final["operations"][0]["result"]["preflight"]["version"] == "4.5.9"
            expect(page.locator("#blender-runtime-install")).to_be_hidden()
            expect(page.locator("#blender-web-install")).to_be_visible()
            page.screenshot(path=str(args.evidence_dir / "ready.png"), full_page=True)
            page.reload()
            page.locator('#app[aria-busy="false"]').wait_for()
            assert page.evaluate("state.blenderRuntime.operations[0].id") == operation["id"]
            assert page.evaluate("state.blenderRuntime.state") == "ready"
            assert not evidence["errors"]
            record("passed", runtime=final,
                   not_tested=["installed Host iframe", "image generation", "G8 ZIP", "Web pack install", "GUI"])
        except Exception as error:
            record("failed", error_type=type(error).__name__)
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    main()
