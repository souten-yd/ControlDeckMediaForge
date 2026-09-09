"""Read a retained animated GLB into isolated source data; exercise the real viewer.

Serve with MediaForge core Python; browse with the existing Playwright diagnostic Python.
No installed service, original asset, Blender runtime, or global configuration writes.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path


def serve(args: argparse.Namespace) -> None:
    import uvicorn
    from mediaforge.app import create_app
    from mediaforge.asset_import import import_asset_bytes
    from mediaforge.config import Settings

    args.data_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    app = create_app(Settings(data_dir=args.data_dir))
    store = app.state.store
    store.initialize()
    content = args.glb.read_bytes()
    asset = import_asset_bytes(store, content, purpose="source", media_type="model/gltf-binary")
    (args.data_dir / "fixture.json").write_text(json.dumps({"asset_id": asset.id,
        "input_sha256": hashlib.sha256(content).hexdigest()}) + "\n")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


def browser(args: argparse.Namespace) -> None:
    from PIL import Image, ImageChops
    from playwright.sync_api import expect, sync_playwright

    fixture = json.loads((args.data_dir / "fixture.json").read_text())
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    evidence: dict = {"mode": "source_real_GLTFLoader_WebGL", "fixture": fixture, "page_errors": []}
    with sync_playwright() as pw:
        chrome = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False)
        try:
            page = chrome.new_page(viewport={"width": 1280, "height": 900})
            page.on("pageerror", lambda error: evidence["page_errors"].append(str(error)))
            page.goto(args.url + "/library")
            page.locator('#app[aria-busy="false"]').wait_for()
            if not page.locator("#view-library").is_visible():
                page.locator("#nav-library").click()
            page.locator(f'#library-grid [data-asset-id="{fixture["asset_id"]}"]').click()
            page.wait_for_function("viewer.modelInstance !== null")
            canvas = page.locator("#viewer-3d-canvas")
            clip = page.locator("#viewer-3d-clip")
            expect(clip.locator("option")).to_have_count(2)
            evidence["clips"] = page.evaluate("viewer.modelInstance.animationClips")
            evidence["stats"] = page.evaluate("viewer.modelInstance.stats")
            assert evidence["stats"]["animations"] == 2
            assert any("arm_swing" in c["name"] for c in evidence["clips"])
            state = lambda: page.evaluate("viewer.modelInstance.animationState()")

            images = []
            for index in (0, 1):
                clip.select_option(str(index))
                assert state()["index"] == index and state()["playing"] is False
                assert state()["time"] == 0
                page.locator("#viewer-3d-speed").select_option("0.5")
                before = canvas.screenshot()
                page.locator("#viewer-3d-animation").click()
                # The retained idle clip intentionally holds still for its first 0.5 s.
                page.wait_for_function("viewer.modelInstance.animationState().time > viewer.modelInstance.animationState().duration * 0.4")
                page.locator("#viewer-3d-animation").click()
                paused = state()
                assert paused["playing"] is False and paused["speed"] == 0.5
                after = canvas.screenshot()
                assert state() == paused
                # Exclude overlaid controls: changing button text is not geometry evidence.
                canvas_box = canvas.bounding_box()
                tools_box = page.locator("#viewer-3d-tools").bounding_box()
                assert canvas_box and tools_box
                crop = (0, 0, int(canvas_box["width"]), int(tools_box["y"] - canvas_box["y"]))
                assert crop[3] > 100
                changed = ImageChops.difference(Image.open(io.BytesIO(before)).convert("RGB").crop(crop),
                    Image.open(io.BytesIO(after)).convert("RGB").crop(crop)).getbbox()
                assert changed, "Playing a bone animation did not change rendered pixels"
                images.append({"index": index, "paused": paused, "changed_bbox": changed})
                (args.evidence_dir / f"clip-{index}.png").write_bytes(after)
                page.locator("#viewer-3d-restart").click()
                assert state()["time"] == 0 and state()["playing"] is False
            evidence["motion"] = images

            # Switching while playing resets the new clip but continues playback.
            page.locator("#viewer-3d-animation").click()
            clip.select_option("0")
            assert state()["index"] == 0 and state()["playing"] is True
            page.locator("#viewer-3d-animation").click()
            page.locator("#viewer-3d-speed").select_option("2")
            assert state()["speed"] == 2
            page.evaluate("applyTheme({locale:'en'}); renderViewer3dText()")
            expect(clip).to_have_attribute("aria-label", "Animation (repeating preview)")
            assert state()["index"] == 0 and state()["speed"] == 2

            page.set_viewport_size({"width": 320, "height": 800})
            clip.select_option("1")
            page.locator("#viewer-3d-restart").click()
            assert state()["index"] == 1 and state()["time"] == 0
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            evidence["mobile_controls"] = clip.bounding_box()
            assert evidence["mobile_controls"]["width"] <= 320
            assert evidence["mobile_controls"]["height"] >= 40
            page.screenshot(path=str(args.evidence_dir / "mobile.png"))

            page.evaluate("window.__oldViewer = viewer.modelInstance")
            page.locator("#viewer-close").click()
            page.wait_for_function("viewer.modelInstance === null && !document.querySelector('#viewer').open")
            assert page.evaluate("window.__oldViewer.animationState().playing") is False
            assert page.evaluate("window.__oldViewer.toggleAnimation()") is False
            page.locator(f'#library-grid [data-asset-id="{fixture["asset_id"]}"]').click()
            page.wait_for_function("viewer.modelInstance !== null")
            assert state()["index"] == 0 and state()["speed"] == 1 and state()["playing"] is False
            expect(page.locator("#viewer-3d-animation")).to_have_attribute("aria-pressed", "false")
            response = page.request.get(args.url + f'/api/v1/assets/{fixture["asset_id"]}/content')
            assert response.ok and hashlib.sha256(response.body()).hexdigest() == fixture["input_sha256"]
            assert not evidence["page_errors"]
            evidence.update(passed=True, asset_unchanged=True,
                not_tested=["installed opaque Host", "engine playback", "organic weights", "IK"])
        except Exception as error:
            evidence.update(passed=False, error_type=type(error).__name__)
            page.screenshot(path=str(args.evidence_dir / "failed.png"))
            raise
        finally:
            chrome.close()
            (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"passed": True, "clips": evidence["clips"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--glb", type=Path)
    parser.add_argument("--port", type=int, default=8937)
    parser.add_argument("--url", default="http://127.0.0.1:8937")
    args = parser.parse_args()
    if args.serve:
        if not args.glb:
            parser.error("--glb is required for --serve")
        serve(args)
    else:
        if not args.evidence_dir:
            parser.error("--evidence-dir is required for browser")
        browser(args)
