"""Observe missing Blender and usable empty Library in a dedicated signed package.

This is a preflight, not evidence of successful real image generation.
Run in the existing browser diagnostic environment; no Host imports or writes.
"""
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
    evidence: dict[str, Any] = {"mode": "isolated_signed_package_preflight", "errors": [],
                                "real_image_generation": "NOT TESTED"}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False)
        try:
            context = browser.new_context(base_url="http://127.0.0.1:9161", locale="ja")
            for name, path in (("health", "/health"), ("runtime", "/workspace-api/blender/runtime"),
                               ("capabilities", "/api/v1/capabilities")):
                response = context.request.get(path)
                assert response.status == 200
                evidence[name] = response.json()
            runtime = evidence["runtime"]
            assert runtime["state"] == "missing" and runtime["runtimes"] == []
            assert runtime["operations"] == [] and runtime["active_runtime_id"] is None
            capabilities = evidence["capabilities"]["capabilities"]
            assert capabilities["image.text_to_image"]["state"] == "available"
            assert capabilities["3d.scene_recipe"]["state"] == "unavailable"
            page = context.new_page()
            page.on("pageerror", lambda error: evidence["errors"].append(type(error).__name__))
            page.goto("/")
            page.locator('#app[aria-busy="false"]').wait_for()
            page.locator("#nav-library").click()
            expect(page.locator("#library-empty")).to_be_visible()
            expect(page.locator("#library-media-kinds")).to_be_visible()
            evidence["library_empty_text"] = page.locator("#library-empty").inner_text()
            page.screenshot(path=str(args.evidence_dir / "library.png"))
            assert not evidence["errors"]
            evidence["passed"] = True
        finally:
            (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
            browser.close()
    print(json.dumps({"passed": True, "real_image_generation": "NOT TESTED"}))


if __name__ == "__main__":
    main()
