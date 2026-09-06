"""Isolated real HTTP/Chrome relation paging with explicitly synthetic lineage.

Seed uses existing valid .blend/GLB bytes and small PNG fixture bytes. This is
metadata/UI acceptance, not evidence of new Blender production or installed Host.
Run seed with MediaForge Python (PYTHONPATH=backend:tests:.), browser with the
existing Playwright diagnostic Python. Serve seed/data on loopback 9163.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path


def seed(root: Path) -> None:
    from mediaforge.store import Store
    from test_scenes import _register

    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    store = Store(root / "data")
    store.initialize()
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")
    assets = Path("/data1tb/mf-clean-packaged-0.28.32-QBvHfm/feature/data/assets")
    blend = (assets / "asset_24d8b1a3e1654c4d9c4a18a7c046393e.blend").read_bytes()
    glb = (assets / "asset_d8548f7e2e3548359b4656b9dddc4781.glb").read_bytes()
    parents = [_register(store, root, mime_type="image/png", content=png) for _ in range(65)]
    source = _register(store, root, mime_type="application/x-blender", content=blend, parents=[a.id for a in parents])
    children = [_register(store, root, mime_type="model/gltf-binary", content=glb, parents=[source.id]) for _ in range(63)]
    value = {"source": source.id, "parents": [a.id for a in parents], "children": [a.id for a in children],
             "lineage": "synthetic acceptance fixture", "blend_sha256": hashlib.sha256(blend).hexdigest(),
             "glb_sha256": hashlib.sha256(glb).hexdigest()}
    (root / "fixture.json").write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"source": source.id, "parents": 65, "children": 63}))


def browser(root: Path) -> None:
    from playwright.sync_api import expect, sync_playwright

    fixture = json.loads((root / "fixture.json").read_text())
    evidence: dict = {"mode": "source_http_synthetic_lineage", "checks": [], "errors": []}
    with sync_playwright() as pw:
        chrome = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False)
        try:
            for locale in ("ja", "en"):
                context = chrome.new_context(viewport={"width": 320, "height": 700}, locale=locale)
                page = context.new_page()
                page.on("pageerror", lambda error: evidence["errors"].append(str(error)[:200]))
                page.goto("http://127.0.0.1:9163/library")
                page.locator('#app[aria-busy="false"]').wait_for()
                page.evaluate("locale => {applyTheme({locale}); renderLibraryMediaFilter();}", locale)
                page.locator('[data-library-media="blend"]').click()
                target = page.locator(f'[data-asset-id="{fixture["source"]}"]')
                page.wait_for_function("state.libraryMedia === 'blend' && state.libraryItems.every(i => i.mime_type === 'application/x-blender')")
                for _ in range(10):
                    if target.count():
                        break
                    expect(page.locator("#library-more")).to_be_visible()
                    cursor = page.evaluate("state.libraryCursor")
                    page.locator("#library-more").click()
                    page.wait_for_function("cursor => state.libraryCursor !== cursor", arg=cursor)
                target.click()
                body = page.locator("#detail-body")
                expect(body).to_have_attribute("data-asset-id", fixture["source"])
                expect(page.locator('[data-asset-relations="parents"] button')).to_have_count(60)
                expect(page.locator('[data-asset-relations="children"] button')).to_have_count(60)
                first = page.locator('[data-related-asset-id]').evaluate_all("els => els.map(e => e.dataset.relatedAssetId)")
                page.locator('[data-relations-offset="60"]').click()
                expect(body).to_have_attribute("data-offset", "60")
                expect(page.locator('[data-asset-relations="parents"] button')).to_have_count(5)
                expect(page.locator('[data-asset-relations="children"] button')).to_have_count(3)
                expect(page.locator('[data-relations-offset="120"]')).to_have_count(0)
                second = page.locator('[data-related-asset-id]').evaluate_all("els => els.map(e => e.dataset.relatedAssetId)")
                assert len(set(first + second)) == 128
                assert set(first + second) == set(fixture["parents"] + fixture["children"])
                expected = "Source assets" if locale == "en" else "元になった素材"
                expect(page.locator('[data-asset-relations="parents"] h3')).to_have_text(expected)
                if locale == "en":
                    expect(page.locator("#detail-body .facts > div").filter(has_text="Validation").locator("dd")).to_have_text("Not recorded")
                page.screenshot(path=str(root / f"page2-{locale}.png"))
                page.locator('[data-relations-offset="0"]').click()
                expect(body).to_have_attribute("data-offset", "0")
                assert page.locator('[data-related-asset-id]').evaluate_all("els => els.map(e => e.dataset.relatedAssetId)") == first
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                evidence["checks"].append({"locale": locale, "width": 320, "unique_relations": 128,
                    "first_page": [60, 60], "last_page": [5, 3], "back_restores_first_page": True})
                context.close()
            assert not evidence["errors"]
            evidence["passed"] = True
        finally:
            chrome.close()
            (root / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("seed", "browser"))
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    (seed if args.mode == "seed" else browser)(args.evidence_dir)
