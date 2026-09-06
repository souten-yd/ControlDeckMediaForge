"""Exercise Library filters and bidirectional lineage against a real source fixture."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    fixture = json.loads((args.data_dir / "ui-fixture.json").read_text())
    args.evidence_dir.mkdir(exist_ok=False)
    errors: list[str] = []
    requests: list[str] = []
    observations: list[dict[str, object]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False,
                                             args=["--enable-webgl", "--ignore-gpu-blocklist"])
        try:
            page = browser.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append(request.url))
            scene_url = args.url + "/workspace-api/scenes/" + fixture["scene_id"]
            before = page.request.get(scene_url).json()
            revision = before["revisions"][-1]
            source = revision["source_asset_id"]
            glb = revision["preview_asset_id"]
            texture = revision["dependencies"][0]["asset_id"]
            for width, language in ((1280, "ja"), (320, "en")):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(args.url)
                page.locator('#app[aria-busy="false"]').wait_for()
                page.evaluate("lang => { document.documentElement.lang = lang; renderLibraryMediaFilter(); }", language)
                page.locator("#nav-library").click()
                for kind, mime in (("image", "image/png"), ("glb", "model/gltf-binary"), ("blend", "application/x-blender")):
                    with page.expect_response(lambda response: response.url.endswith("/workspace-api/library")):
                        page.locator(f'[data-library-media="{kind}"]').click()
                    page.wait_for_function("mime => state.libraryItems.length > 0 && state.libraryItems.every(i => i.mime_type === mime)", arg=mime)
                    observations.append({"width": width, "language": language, "filter": kind,
                                         "count": page.locator("#library-grid .card").count()})
                page.locator(f'#library-grid [data-asset-id="{source}"]').click()
                expect(page.locator("#detail-body")).to_have_attribute("data-asset-id", source)
                expect(page.locator("#detail-preview")).to_have_count(0)
                page.locator(f'[data-asset-relations="parents"] [data-related-asset-id="{texture}"]').click()
                expect(page.locator("#detail-body")).to_have_attribute("data-asset-id", texture)
                page.locator(f'[data-asset-relations="children"] [data-related-asset-id="{source}"]').click()
                expect(page.locator("#detail-body")).to_have_attribute("data-asset-id", source)
                page.locator(f'[data-asset-relations="children"] [data-related-asset-id="{glb}"]').click()
                expect(page.locator("#detail-body")).to_have_attribute("data-asset-id", glb)
                page.locator(f'[data-asset-relations="parents"] [data-related-asset-id="{source}"]').click()
                expect(page.locator("#detail-body")).to_have_attribute("data-asset-id", source)
                page.screenshot(path=str(args.evidence_dir / f"lineage-{width}.png"), full_page=True)
                page.locator("#close-dialog").click()
            assert not any("/content" in url or "/model/open" in url or "/model/bytes" in url for url in requests), requests
            page.locator('[data-library-media="blend"]').click()
            page.locator(f'#library-grid [data-asset-id="{source}"]').click()
            expect(page.locator("#detail-body")).to_have_attribute("data-asset-id", source)
            page.locator(f'[data-asset-relations="children"] [data-related-asset-id="{glb}"]').click()
            expect(page.locator("#detail-body")).to_have_attribute("data-asset-id", glb)
            page.locator("#detail-preview").click()
            try:
                page.locator("#viewer-3d-tools").wait_for(state="visible")
            except Exception:
                page.screenshot(path=str(args.evidence_dir / "preview-failure.png"), full_page=True)
                print(json.dumps({"loading": page.locator("#viewer-3d-loading").inner_text(), "errors": errors}))
                raise
            assert page.locator("#viewer-edit").is_hidden()
            page.locator("#viewer-close").click()
            assert page.request.get(scene_url).json() == before
            assert not errors, errors
            evidence = {"observations": observations, "scene_id": fixture["scene_id"], "source": source,
                        "glb": glb, "texture": texture, "bidirectional_navigation": True,
                        "full_asset_requests_during_navigation": 0, "explicit_glb_preview": True,
                        "scene_unchanged": True, "page_errors": errors}
            (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2))
            print(json.dumps(evidence))
        finally:
            browser.close()


if __name__ == "__main__":
    main()
