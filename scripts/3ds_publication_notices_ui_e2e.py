"""Real Chrome/production settings renderer with explicit runtime-status fixtures.

No installed Host, Blender or user data changes. This verifies presentation,
not real Host reconciliation; that requires a separate installed acceptance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    args = parser.parse_args()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[1]
    script = (root / "frontend/app.js").read_text()
    renderer = "const BLENDER_TEXT = " + script.split("const BLENDER_TEXT = ", 1)[1].split("function renderExtensionDetails()", 1)[0]
    errors, results = [], []
    cases = {
        "completed-late-cancel": ("ready", ["late_cancel", "host_mismatch"]),
        "recovered": ("ready", ["publication_recovered", "host_pending"]),
        "rolled-back": ("failed", ["publication_rolled_back", "late_context_lost"]),
        "unresolved": ("failed", ["publication_recovery_required"]),
        "committing": ("probing", ["publication_in_progress", "late_cancel"]),
    }
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True)
        try:
            page = browser.new_page(viewport={"width": 320, "height": 720})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content((root / "frontend/index.html").read_text())
            page.add_style_tag(content=(root / "frontend/styles.css").read_text())
            page.add_script_tag(content="""
                const state = {disabled:true, blenderRuntime:null};
                const byId = id => document.getElementById(id);
                const formatBytes = value => String(value);
                function renderSceneText() {}
            """ + renderer)
            page.evaluate("""() => {
                document.documentElement.dataset.bridge = 'ready';
                document.getElementById('app').dataset.view = 'settings';
                document.querySelectorAll('.view').forEach(e => e.hidden = e.id !== 'view-settings');
                // Only the Blender renderer is initialized in this fixture.
                // Image catalog controls have a separate bootstrap and acceptance.
                document.querySelectorAll('#view-settings > :not(#blender-settings):not(.settings-page-head)')
                    .forEach(e => e.hidden = true);
                document.getElementById('app').removeAttribute('aria-busy');
            }""")
            for width in (320, 1280):
                page.set_viewport_size({"width": width, "height": 900})
                for language in ("ja", "en"):
                    for case, (status, codes) in cases.items():
                        value = {"state": "missing", "management_available": False, "runtimes": [],
                                 "operations": [{"id": "blenderop_" + "a" * 32, "version": "4.5.13", "state": status}],
                                 "operation_notices": {"blenderop_" + "a" * 32: codes}}
                        page.evaluate("""({value,language}) => {
                            document.documentElement.lang = language;
                            state.blenderRuntime = value;
                            renderBlenderRuntime();
                        }""", {"value": value, "language": language})
                        expect(page.locator("#blender-operation-notices")).to_be_visible()
                        assert page.locator("#blender-operation-notices-list .hint").count() == len(codes)
                        overflow = page.evaluate("""() => [...document.querySelectorAll('body *')]
                            .filter(e => { const r=e.getBoundingClientRect(); return r.width && r.right > innerWidth + 1; })
                            .map(e => ({id:e.id, tag:e.tagName, width:e.getBoundingClientRect().width})).slice(0,20)""")
                        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), overflow
                        assert page.evaluate("JSON.stringify(state.blenderRuntime)") == json.dumps(value, separators=(",", ":"))
                        expected = page.evaluate("blenderText().operationStates[state.blenderRuntime.operations[0].state]")
                        assert expected in page.locator("[data-operation-notice] > p").first.inner_text()
                        if case == "completed-late-cancel":
                            assert page.locator("#blender-runtime-cancel").is_hidden()
                            page.locator("#blender-settings").screenshot(path=str(args.evidence_dir / f"late-cancel-{language}-{width}.png"))
                        results.append({"case": case, "width": width, "language": language, "passed": True})
            # Older responses, unknown codes and disconnected data clear stale notices.
            for statement in ("delete state.blenderRuntime.operation_notices",
                              "state.blenderRuntime.operation_notices = {[state.blenderRuntime.operations[0].id]: ['<img src=x onerror=alert(1)>', '__proto__']}",
                              "state.blenderRuntime = null"):
                page.evaluate(statement + "; renderBlenderRuntime()")
                expect(page.locator("#blender-operation-notices")).to_be_hidden()
                assert page.locator("#blender-operation-notices-list img").count() == 0
            assert not errors, errors
        except Exception as error:
            page.screenshot(path=str(args.evidence_dir / "failed.png"), full_page=True)
            (args.evidence_dir / "observations.json").write_text(json.dumps({
                "passed": False, "cases": results, "page_errors": errors,
                "error_type": type(error).__name__, "scope": "production renderer with status fixtures"}, indent=2) + "\n")
            raise
        finally:
            browser.close()
    evidence = {"passed": True, "scope": "production renderer; runtime-status fixtures; real Chrome",
                "cases": results, "page_errors": errors,
                "not_tested": ["installed Host iframe", "live Host reconciliation", "physical mobile"]}
    (args.evidence_dir / "observations.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence), flush=True)


if __name__ == "__main__":
    main()
