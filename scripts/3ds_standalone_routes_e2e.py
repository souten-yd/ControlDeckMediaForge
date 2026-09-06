"""Real browser route acceptance on the dedicated loopback service, no overlays."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    evidence: dict[str, Any] = {"events": [], "errors": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False)
        try:
            context = browser.new_context(base_url="http://127.0.0.1:9161", locale="ja")
            page = context.new_page()
            page.on("pageerror", lambda error: evidence["errors"].append(type(error).__name__))

            def snapshot() -> dict[str, Any]:
                result = {}
                for key, path in (("runtime", "/workspace-api/blender/runtime"),
                                  ("sessions", "/workspace-api/blender/sessions"),
                                  ("jobs", "/api/v1/jobs"), ("assets", "/api/v1/assets")):
                    response = context.request.get(path)
                    assert response.status == 200
                    result[key] = response.json()
                return result

            def check(view: str, stage: str) -> None:
                page.locator('#app[aria-busy="false"]').wait_for()
                expect(page.locator("#app")).to_have_attribute("data-view", view)
                expect(page.locator(f"#nav-{view}")).to_have_attribute("aria-current", "page")
                expect(page.locator(f'#view-{view}')).to_be_visible()
                evidence["events"].append({"stage": stage, "view": view, "url": page.url})

            before = snapshot()
            for width in (1280, 320):
                page.set_viewport_size({"width": width, "height": 720})
                for path, view in (("/library", "library"), ("/activity", "activity"),
                                   ("/settings", "settings"), ("/web-blender", "web-blender"),
                                   ("/", "create"), ("/create", "create"),
                                   ("/jobs", "activity"), ("/models", "settings"), ("/profiles", "settings")):
                    page.goto(path)
                    check(view, f"direct-{width}")
                    page.reload()
                    check(view, f"reload-{width}")
                page.goto("/library")
                check("library", "history-start")
                page.locator("#nav-web-blender").click()
                check("web-blender", "navigate")
                assert page.url.endswith("/web-blender")
                count = page.evaluate("history.length")
                page.locator("#nav-web-blender").click()
                assert page.evaluate("history.length") == count
                page.locator("#nav-activity").click()
                check("activity", "navigate")
                page.go_back()
                check("web-blender", "back")
                page.go_back()
                check("library", "back")
                page.go_forward()
                check("web-blender", "forward")
                page.screenshot(path=str(args.evidence_dir / f"web-blender-{width}.png"))
            assert snapshot() == before, "Navigation must not start jobs/sessions or install Blender"
            assert not evidence["errors"]
            evidence["passed"] = True
        finally:
            page.screenshot(path=str(args.evidence_dir / "final.png"))
            (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
            browser.close()
    print(json.dumps({"passed": True, "checks": len(evidence["events"])}))


if __name__ == "__main__":
    main()
