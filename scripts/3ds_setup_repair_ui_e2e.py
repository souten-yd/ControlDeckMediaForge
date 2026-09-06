"""Continue the dedicated 9161 source Settings test with install and repair.

Only the isolated long-setup data is modified. Temporarily moves its inactive
4.5.9 stamp into evidence storage; restores it on failure if repair did not.
Never targets installed runtime or global Blender. Run after setup_settings_ui.
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
    root = Path("/data1tb/mf-long-setup-source-20260906")
    assert root.resolve() == root and not root.is_symlink()
    base, newer = "blender-4.5.9-linux-x64", "blender-4.5.13-linux-x64"
    stamp = root / "runtimes/blender" / base / ".runtime.json"
    backup = args.evidence_dir.resolve() / "original-runtime-stamp.json"
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    started = time.monotonic()

    def record(stage: str, **values: Any) -> None:
        event = {"stage": stage, "elapsed_sec": round(time.monotonic() - started, 3), **values}
        events.append(event)
        (args.evidence_dir / "observations.json").write_text(json.dumps(events, indent=2) + "\n")
        print(json.dumps(event), flush=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/usr/bin/google-chrome", headless=False)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 1000})
            page.on("pageerror", lambda error: errors.append(type(error).__name__))
            page.goto("http://127.0.0.1:9161")
            page.locator('#app[aria-busy="false"]').wait_for()
            page.locator("#nav-settings").click()
            assert page.evaluate("state.blenderRuntime.active_runtime_id") == newer
            assert page.evaluate("state.blenderRuntime.runtimes.map(r => r.runtime_id)") == [newer]

            def finish(action: str, ids: list[str]) -> dict[str, Any]:
                deadline = time.monotonic() + 180
                while time.monotonic() < deadline:
                    rows = page.evaluate("state.blenderRuntime.operations")
                    row = next((r for r in rows if r["id"] not in ids and r["action"] == action), None)
                    if row and row["state"] in {"ready", "failed", "canceled"}:
                        assert row["state"] == "ready", row
                        record(action, operation=row)
                        return row
                    page.wait_for_timeout(500)
                raise AssertionError("Setup operation did not finish")

            ids = page.evaluate("state.blenderRuntime.operations.map(o => o.id)")
            page.locator("#blender-runtime-install").click()
            finish("install", ids)
            assert stamp.resolve() == stamp and stamp.is_file() and not backup.exists()
            stamp.rename(backup)
            record("isolated_stamp_retained", runtime_id=base)
            page.locator("#blender-runtime-refresh").click()
            if not page.locator("#blender-runtime-list").is_visible():
                page.locator("#blender-runtime-details-label").click()
            repair = page.locator(f'[data-blender-repair="{base}"]')
            expect(repair).to_be_visible(timeout=30000)
            page.screenshot(path=str(args.evidence_dir / "damaged.png"), full_page=True)
            ids = page.evaluate("state.blenderRuntime.operations.map(o => o.id)")
            repair.click()
            repaired = finish("repair", ids)
            assert repaired["result"]["preflight"]["version"] == "4.5.9"
            assert stamp.is_file() and backup.is_file()
            assert page.evaluate("state.blenderRuntime.active_runtime_id") == newer
            page.wait_for_function("id => state.blenderRuntime.runtimes.some(r => r.runtime_id === id && r.state === 'ready')", arg=base)
            page.screenshot(path=str(args.evidence_dir / "repaired.png"), full_page=True)
            assert not errors
            record("passed", active_unchanged=True, stamp_restored=True,
                not_tested=["installed Host iframe", "completely empty browser install", "live reference deletion"])
        except Exception as error:
            record("failed", error_type=type(error).__name__)
            raise
        finally:
            if backup.exists() and not stamp.exists():
                backup.rename(stamp)
                record("original_stamp_restored_after_failure")
            browser.close()


if __name__ == "__main__":
    main()
