#!/usr/bin/env python3
"""Installed-host MF0 browser smoke.

Run this with ControlDeck's Playwright-capable Python environment. The script
installs and always uninstalls Media Forge through the public Add-on API; it
never imports ControlDeck backend modules or accepts a host filesystem path.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from urllib.parse import quote
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, expect, sync_playwright


def media_request(base_url: str, path: str, *, method: str = "GET", payload: object | None = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        method=method,
        headers={} if body is None else {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def addon_request(page: Page, path: str, method: str, body: object | None = None) -> dict[str, Any]:
    return page.evaluate(
        """async ({path, method, body}) => {
          const response = await fetch(`/api/v1${path}`, {
            method,
            credentials: "same-origin",
            headers: {
              "X-Requested-With": "ControlDeck",
              ...(body === null ? {} : {"Content-Type": "application/json"}),
            },
            body: body === null ? undefined : JSON.stringify(body),
          });
          return {status: response.status, text: await response.text()};
        }""",
        {"path": path, "method": method, "body": body},
    )


def parsed(response: dict[str, Any]) -> Any:
    return json.loads(response["text"])


def uninstall_if_present(page: Page) -> None:
    current = addon_request(page, "/addons", "GET")
    if current["status"] == 200 and any(item.get("id") == "media-forge" for item in parsed(current)):
        removed = addon_request(page, "/addons/media-forge", "DELETE")
        assert removed["status"] == 200, removed


def login(page: Page, username: str, password: str) -> None:
    page.goto("/login")
    page.get_by_label("ユーザー名").fill(username)
    page.get_by_label("パスワード").fill(password)
    page.get_by_role("button", name="ログイン").click()
    expect(page).not_to_have_url("/login")


def media_frame(page: Page):
    expect(page.locator('iframe[title="Media Forge — workspace"]')).to_have_count(1)
    return page.frame_locator('iframe[title="Media Forge — workspace"]')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", required=True)
    parser.add_argument("--media-forge-url", default="http://127.0.0.1:9130")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--media-data-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    # Keep the committed manifest canonical while allowing isolated test
    # processes to bind a different loopback port.
    manifest["runtime"]["base_url"] = args.media_forge_url.rstrip("/")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    observations: dict[str, Any] = {"started_at": time.time(), "checks": {}}
    browser_errors: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(base_url=args.control_deck_url, viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.on("console", lambda message: browser_errors.append(f"console:{message.type}:{message.text}") if message.type == "error" else None)
        page.on("pageerror", lambda error: browser_errors.append(f"pageerror:{error}"))
        try:
            login(page, args.username, args.password)
            uninstall_if_present(page)

            media_request(args.media_forge_url, "/test/health", method="POST", payload={"status": "setup_required"})
            installed = addon_request(page, "/addons", "POST", manifest)
            assert installed["status"] == 201, installed

            page.goto("/")
            expect(page.get_by_role("link", name="Media", exact=True)).to_have_count(0)
            observations["checks"]["A_disabled_contributions_absent"] = True

            enabled = addon_request(
                page,
                "/addons/media-forge/enable",
                "POST",
                {"granted_capabilities": manifest["host_capabilities"]},
            )
            assert enabled["status"] == 200, enabled
            assert parsed(enabled)["state"] == "setup_required", parsed(enabled)
            page.goto("/settings?extension=media-forge")
            details = page.get_by_role("dialog", name="Media Forge")
            expect(details.get_by_text("セットアップが必要", exact=True)).to_be_visible()
            expect(details.get_by_text("Model library · missing", exact=True)).to_be_visible()
            observations["checks"]["B_setup_required_visible"] = True

            media_request(args.media_forge_url, "/test/health", method="POST", payload={"status": "healthy"})
            rechecked = addon_request(page, "/addons/media-forge/recheck", "POST")
            assert rechecked["status"] == 200 and parsed(rechecked)["state"] == "healthy", rechecked
            page.goto("/")
            expect(page.get_by_role("link", name="Media", exact=True)).to_be_visible()
            observations["checks"]["C_healthy_navigation_visible"] = True

            page.emulate_media(color_scheme="light")
            page.evaluate("localStorage.setItem('cd-theme', 'system')")
            page.goto("/x/media-forge/workspace")
            embedded = media_frame(page)
            expect(embedded.get_by_role("heading", name="Media Forge", exact=True)).to_be_visible()
            expect(embedded.locator("html")).to_have_attribute("data-bridge", "ready")
            initial_bg = embedded.locator("html").evaluate("el => getComputedStyle(el).getPropertyValue('--bg')")
            embedded.locator("html").evaluate("window.__mediaForgeLoadMarker = crypto.randomUUID()")
            marker = embedded.locator("html").evaluate("window.__mediaForgeLoadMarker")
            page.screenshot(path=args.evidence_dir / "workspace-light.png", full_page=True)
            observations["checks"]["D_workspace_bridge_ready"] = True

            page.emulate_media(color_scheme="dark")
            deadline = time.monotonic() + 5
            dark_bg = initial_bg
            while time.monotonic() < deadline and dark_bg == initial_bg:
                page.wait_for_timeout(50)
                dark_bg = embedded.locator("html").evaluate("el => getComputedStyle(el).getPropertyValue('--bg')")
            assert dark_bg != initial_bg, {"initial_bg": initial_bg, "dark_bg": dark_bg}
            assert embedded.locator("html").evaluate("window.__mediaForgeLoadMarker") == marker
            observations["checks"]["F_theme_without_reload"] = True

            embedded.get_by_role("button", name="Library", exact=True).click()
            expect(page).to_have_url("/x/media-forge/workspace/library")
            page.go_back()
            expect(page).to_have_url("/x/media-forge/workspace")
            page.go_forward()
            expect(page).to_have_url("/x/media-forge/workspace/library")
            page.reload()
            embedded = media_frame(page)
            expect(embedded.get_by_role("heading", name="Library", exact=True)).to_be_visible()
            observations["checks"]["G_history_reload_share_route"] = True

            initial_asset_count = len(media_request(args.media_forge_url, "/api/v1/assets")["items"])
            embedded.get_by_role("button", name="Create", exact=True).click()
            embedded.get_by_label("作りたい画像").fill("MF0 installed browser evidence")
            embedded.get_by_role("button", name="生成する").click()
            expect(embedded.get_by_text("Library", exact=True).first).to_be_visible()
            expect(embedded.locator(".asset-card")).to_have_count(initial_asset_count + 1, timeout=15_000)
            asset_count_before_disable = len(media_request(args.media_forge_url, "/api/v1/assets")["items"])
            assert asset_count_before_disable == initial_asset_count + 1
            newest_asset = media_request(args.media_forge_url, "/api/v1/assets")["items"][0]
            asset_path = args.media_data_dir / "assets" / f"{newest_asset['id']}.png"
            assert asset_path.is_file(), asset_path
            page.screenshot(path=args.evidence_dir / "library-generated.png", full_page=True)
            observations["checks"]["E_local_create_library_partial"] = {"asset_count": asset_count_before_disable}

            page.goto(f"/files?path={quote(str(asset_path.parent), safe='')}")
            file_name = page.get_by_text(asset_path.name, exact=True)
            expect(file_name).to_be_visible()
            file_row = file_name.locator("xpath=ancestor::li")
            page.screenshot(path=args.evidence_dir / "files-context.png", full_page=True)
            file_row.get_by_role("button", name="拡張機能のコンテキストアクション").click()
            context_action = page.get_by_role("menuitem", name="Media Forge で編集（media-forge）", exact=True)
            expect(context_action).to_be_visible()
            page.screenshot(path=args.evidence_dir / "files-context-menu.png", full_page=True)
            context_action.click()
            expect(page.get_by_text("Media Forge で編集を実行しました", exact=True)).to_be_visible()
            observations["checks"]["H_files_context_action_invoked"] = True

            tools = addon_request(page, "/addons/media-forge/agent-tools/media.capabilities/invoke", "POST", {"arguments": {}, "wait": True})
            assert tools["status"] == 200, tools
            tool_output = parsed(tools)
            serialized = json.dumps(tool_output).lower()
            assert tool_output["job_id"] and tool_output["asset_id"].startswith("job-result:")
            assert all(name not in serialized for name in ("fake-image", "flux", "qwen", "model_id"))
            observations["checks"]["J_agent_capabilities_job"] = {
                "job_id": tool_output["job_id"],
                "asset_id": tool_output["asset_id"],
            }

            catalog = addon_request(page, "/addons/execution-contributions", "GET")
            assert catalog["status"] == 200
            contributions = parsed(catalog)["contributions"]
            workflow_ids = [item["id"] for item in contributions["workflow_executors"] if item["addon_id"] == "media-forge"]
            assert workflow_ids == []
            observations["checks"]["I_workflow_unavailable_fail_closed"] = True

            page.goto("/x/media-forge/workspace/library")
            media_frame(page)
            disabled = addon_request(page, "/addons/media-forge/disable", "POST")
            assert disabled["status"] == 200
            expect(page.locator("iframe")).to_have_count(0, timeout=10_000)
            page.goto("/")
            expect(page.get_by_role("link", name="Media", exact=True)).to_have_count(0)
            observations["checks"]["L_disable_removes_contributions"] = True

            reenabled = addon_request(
                page,
                "/addons/media-forge/enable",
                "POST",
                {"granted_capabilities": manifest["host_capabilities"]},
            )
            assert reenabled["status"] == 200 and parsed(reenabled)["state"] == "healthy"
            page.goto("/x/media-forge/workspace/library")
            embedded = media_frame(page)
            expect(embedded.locator(".asset-card")).to_have_count(asset_count_before_disable)
            observations["checks"]["M_reenable_preserves_assets"] = True

            page.set_viewport_size({"width": 320, "height": 700})
            page.goto("/x/media-forge/workspace")
            expect(page.get_by_role("heading", name="Media Forge", exact=True)).to_be_visible()
            expect(page.get_by_text("この拡張機能の作業画面はデスクトップ向けです。", exact=False)).to_be_visible()
            expect(page.locator("iframe")).to_have_count(0)
            page.screenshot(path=args.evidence_dir / "companion-320.png", full_page=True)
            observations["checks"]["N_mobile_companion"] = True
        finally:
            try:
                if not page.is_closed():
                    uninstall_if_present(page)
            finally:
                context.close()
                browser.close()

    observations["finished_at"] = time.time()
    observations["elapsed_sec"] = observations["finished_at"] - observations["started_at"]
    observations["browser_errors"] = browser_errors
    assert not browser_errors, browser_errors
    (args.evidence_dir / "result.json").write_text(json.dumps(observations, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(observations, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
