"""Read-only source Settings layout at 320/1280px in Japanese and English.

Uses the isolated source service on 9161. Locale is set on the source document;
this is not an installed Host locale-event acceptance test.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--require-touch-targets", action="store_true")
    args = parser.parse_args()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    observations = []
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False)
        try:
            page = browser.new_page()
            page.on("pageerror", lambda error: errors.append(type(error).__name__))
            for width, language in ((320, "en"), (320, "ja"), (1280, "en"), (1280, "ja")):
                page.set_viewport_size({"width": width, "height": 900})
                page.goto("http://127.0.0.1:9161")
                page.locator('#app[aria-busy="false"]').wait_for()
                before = page.evaluate("() => call('blender.runtime.status', {})")
                page.evaluate("lang => { document.documentElement.lang = lang; renderBlenderRuntime(); }", language)
                page.locator("#nav-settings").click()
                if not page.locator("#blender-runtime-list").is_visible():
                    page.locator("#blender-runtime-details-label").click()
                layout = page.evaluate("""() => ({
                    client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth,
                    buttons: [...document.querySelectorAll('#blender-runtime-list button')].map(button => ({
                        height: button.getBoundingClientRect().height,
                        minHeight: getComputedStyle(button).minHeight
                    })),
                    rows: [...document.querySelectorAll('#blender-runtime-list .row')].map(row => {
                        const a = row.firstElementChild.getBoundingClientRect();
                        const b = row.lastElementChild.getBoundingClientRect();
                        return {text: a.width, textBottom: a.bottom, controlsTop: b.top,
                            client: row.clientWidth, scroll: row.scrollWidth};
                    })
                })""")
                observations.append({"width": width, "language": language, **layout})
                page.screenshot(path=str(args.evidence_dir / f"settings-{width}-{language}.png"), full_page=True)
                assert len(layout["rows"]) == 2
                assert all(row["text"] >= 100 for row in layout["rows"]), layout
                if width == 320:
                    assert all(row["controlsTop"] >= row["textBottom"] for row in layout["rows"]), layout
                    if args.require_touch_targets:
                        assert layout["buttons"] and all(button["height"] >= 44 for button in layout["buttons"]), layout
                assert layout["scroll"] <= layout["client"], layout
                assert all(row["scroll"] <= row["client"] for row in layout["rows"]), layout
                assert page.evaluate("() => call('blender.runtime.status', {})") == before
            assert not errors
        finally:
            browser.close()
            evidence = {"observations": observations, "errors": errors}
            (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
            print(json.dumps(evidence), flush=True)


if __name__ == "__main__":
    main()
