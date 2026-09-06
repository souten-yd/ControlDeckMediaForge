"""Read-only navigation acceptance against an isolated running source server."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(exist_ok=False)
    errors: list[str] = []
    observations: list[dict[str, object]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        try:
            page = browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            for width in (1280, 320):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(args.url)
                page.locator('#app[aria-busy="false"]').wait_for()
                page.locator("#nav-web-blender").click()
                assert page.locator("#nav-web-blender").get_attribute("aria-current") == "page"
                assert page.locator("#scene-studio").is_visible()
                assert not page.locator("#create-form").is_visible()
                page.locator("#nav-settings").click()
                page.locator("#nav-settings").click()
                assert page.locator("#scene-studio").is_visible()
                for view in ("library", "activity", "create"):
                    page.locator(f"#nav-{view}").click()
                    assert page.locator(f"#view-{view}").is_visible()
                    assert not page.locator("#scene-studio").is_visible()
                assert page.locator("#create-form").is_visible()
                page.locator("#create-media-3d").click()
                assert page.locator("#nav-web-blender").get_attribute("aria-current") == "page"
                buttons = page.locator("#shell-nav button").evaluate_all(
                    "els => els.map(e => {const r=e.getBoundingClientRect(); return {text:e.textContent.trim(),x:r.x,y:r.y,width:r.width,height:r.height};})"
                )
                assert len(buttons) == 4
                if width == 320:
                    assert len({button["y"] for button in buttons}) == 1
                    assert all(button["width"] >= 44 and button["height"] >= 44 for button in buttons)
                    assert buttons[-1]["x"] + buttons[-1]["width"] <= width
                observations.append({"width": width, "buttons": buttons, "navigation": "passed"})
                page.screenshot(path=str(args.evidence_dir / f"web-blender-{width}.png"), full_page=True)
            page.goto(args.url + "/web-blender")
            page.locator('#app[aria-busy="false"]').wait_for()
            assert page.locator("#scene-studio").is_visible()
            assert not errors, errors
            evidence = {"observations": observations, "page_errors": errors, "direct_route": "passed"}
            (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2))
            print(json.dumps(evidence))
        finally:
            browser.close()


if __name__ == "__main__":
    main()
