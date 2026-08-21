#!/usr/bin/env python3
"""Installed-host MF0 browser smoke.

Run this with ControlDeck's Playwright-capable Python environment. The script
installs and always uninstalls Media Forge through the public Add-on API; it
never imports ControlDeck backend modules or accepts a host filesystem path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
    parser.add_argument("--password-env", default="MEDIA_FORGE_E2E_PASSWORD")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--media-data-dir", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--expect-handshake-delay", action="store_true")
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        raise RuntimeError(f"password environment variable is unset: {args.password_env}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    # Keep the committed manifest canonical while allowing isolated test
    # processes to bind a different loopback port.
    manifest["runtime"]["base_url"] = args.media_forge_url.rstrip("/")
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    observations: dict[str, Any] = {"started_at": time.time(), "checks": {}}
    browser_errors: list[str] = []
    workflow_id: int | None = None

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(base_url=args.control_deck_url, viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.on("console", lambda message: browser_errors.append(f"console:{message.type}:{message.text}") if message.type == "error" else None)
        page.on("pageerror", lambda error: browser_errors.append(f"pageerror:{error}"))
        try:
            login(page, args.username, password)
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
            if args.expect_handshake_delay:
                page.goto("/x/media-forge/workspace", wait_until="commit")
                frame = page.locator('iframe[title="Media Forge — workspace"]')
                expect(frame).to_have_count(1)
                expect(frame).to_have_class(re.compile(r"(?:^|\s)invisible(?:\s|$)"))
                expect(page.get_by_label("拡張機能を接続中")).to_be_visible()
                page.screenshot(path=args.evidence_dir / "workspace-handshake-hidden.png", full_page=True)
                observations["checks"]["D_handshake_hides_iframe_before_ready"] = True
            else:
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
            host_jobs_before = parsed(addon_request(page, "/jobs?limit=100", "GET"))
            host_job_ids_before = {item["id"] for item in host_jobs_before}
            embedded.get_by_role("button", name="Create", exact=True).click()
            embedded.get_by_label("作りたい画像").fill("MF0 installed browser evidence")
            embedded.get_by_role("button", name="生成する").click()
            expect(embedded.get_by_text("Library", exact=True).first).to_be_visible()
            expect(embedded.locator(".asset-card")).to_have_count(initial_asset_count + 1, timeout=15_000)
            asset_count_before_disable = len(media_request(args.media_forge_url, "/api/v1/assets")["items"])
            assert asset_count_before_disable == initial_asset_count + 1
            newest_asset = media_request(args.media_forge_url, "/api/v1/assets")["items"][0]
            host_jobs_after = parsed(addon_request(page, "/jobs?limit=100", "GET"))
            created_host_jobs = [
                item for item in host_jobs_after
                if item["id"] not in host_job_ids_before and item.get("kind") == "addon.runtime.media-forge"
            ]
            assert len(created_host_jobs) == 1, created_host_jobs
            assert created_host_jobs[0]["status"] == "succeeded", created_host_jobs[0]
            asset_path = args.media_data_dir / "assets" / f"{newest_asset['id']}.png"
            assert asset_path.is_file(), asset_path
            page.screenshot(path=args.evidence_dir / "library-generated.png", full_page=True)
            observations["checks"]["E_create_host_job_library"] = {
                "asset_count": asset_count_before_disable,
                "host_job_id": created_host_jobs[0]["id"],
                "host_job_status": created_host_jobs[0]["status"],
            }

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
            expect(page).to_have_url("/x/media-forge/workspace/create")
            embedded = media_frame(page)
            expect(embedded.locator("html")).to_have_attribute("data-bridge", "ready")
            observations["checks"]["H_files_context_action_opened_workspace"] = True

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
            assert workflow_ids == ["media.generate"]
            media_jobs_before_dry_run = len(media_request(args.media_forge_url, "/api/v1/jobs")["items"])
            workflow_definition = {
                "nodes": [
                    {"id": "start", "type": "trigger", "config": {"mode": "manual"}},
                    {
                        "id": "generate",
                        "type": "addon.workflow:media-forge:media.generate",
                        "config": {
                            "operation": "image.generate",
                            "intent": "MF0 installed browser workflow evidence",
                            "model_policy": "auto",
                            "constraints": {"width": 64, "height": 48},
                            "output": {"format": "png", "count": 1},
                            "local_only": True,
                        },
                    },
                ],
                "edges": [{"source": "start", "target": "generate"}],
            }
            created_workflow = addon_request(
                page,
                "/workflows",
                "POST",
                {"name": "MF0 browser delegated workflow", "definition": workflow_definition},
            )
            assert created_workflow["status"] == 201, created_workflow
            workflow_id = int(parsed(created_workflow)["id"])
            dry_run = addon_request(page, f"/workflows/{workflow_id}/dry-run", "POST", {"input": {}})
            assert dry_run["status"] == 200, dry_run
            assert len(media_request(args.media_forge_url, "/api/v1/jobs")["items"]) == media_jobs_before_dry_run
            started_workflow = addon_request(page, f"/workflows/{workflow_id}/test", "POST", {"input": {}})
            assert started_workflow["status"] == 200, started_workflow
            execution_id = int(parsed(started_workflow)["execution_id"])
            workflow_execution: dict[str, Any] = {}
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                workflow_execution = parsed(addon_request(page, f"/workflow-executions/{execution_id}/live", "GET"))
                if workflow_execution.get("status") not in {"RUNNING", "QUEUED", "WAITING"}:
                    break
                page.wait_for_timeout(50)
            assert workflow_execution.get("status") == "SUCCEEDED", workflow_execution
            workflow_job_id = workflow_execution["context"]["generate"]["output"]["job_id"]
            workflow_media_job: dict[str, Any] = {}
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                workflow_media_job = media_request(args.media_forge_url, f"/api/v1/jobs/{workflow_job_id}")
                if workflow_media_job.get("status") in {"succeeded", "failed", "canceled"}:
                    break
                page.wait_for_timeout(50)
            assert workflow_media_job.get("status") == "succeeded", workflow_media_job
            observations["checks"]["I_workflow_dry_run_and_execute"] = {
                "execution_id": execution_id,
                "dry_run_media_job_delta": 0,
                "media_job_id": workflow_job_id,
            }

            def generation_arguments(intent: str, delay: float) -> dict[str, Any]:
                return {
                    "operation": "image.generate",
                    "intent": intent,
                    "model_policy": "auto",
                    "constraints": {"width": 64, "height": 48, "_fake_delay_sec": delay},
                    "output": {"format": "png", "count": 1},
                    "local_only": True,
                }

            first_gpu = addon_request(
                page,
                "/addons/media-forge/agent-tools/media.generate/invoke",
                "POST",
                {"arguments": generation_arguments("MF0 browser serialized first", 1.5), "wait": False},
            )
            assert first_gpu["status"] == 202, first_gpu
            first_gpu_job = parsed(first_gpu)["job_id"]
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                resources = parsed(addon_request(page, "/resources", "GET"))
                if any(item.get("job_id") == first_gpu_job and item.get("state") == "active" for item in resources["leases"]):
                    break
                page.wait_for_timeout(50)
            else:
                raise AssertionError("first fake GPU job did not activate")
            second_gpu = addon_request(
                page,
                "/addons/media-forge/agent-tools/media.generate/invoke",
                "POST",
                {"arguments": generation_arguments("MF0 browser serialized second", 0.2), "wait": False},
            )
            assert second_gpu["status"] == 202, second_gpu
            second_gpu_job = parsed(second_gpu)["job_id"]
            waiting_request: dict[str, Any] | None = None
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                resources = parsed(addon_request(page, "/resources", "GET"))
                waiting_request = next((
                    item for item in resources["requests"]
                    if item.get("job_id") == second_gpu_job and item.get("state") == "waiting"
                ), None)
                if waiting_request is not None:
                    break
                page.wait_for_timeout(50)
            assert waiting_request is not None, resources
            terminal_gpu_jobs: list[dict[str, Any]] = []
            for host_job_id in (first_gpu_job, second_gpu_job):
                host_job: dict[str, Any] = {}
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    host_job = parsed(addon_request(page, f"/jobs/{host_job_id}", "GET"))
                    if host_job.get("status") in {"succeeded", "failed", "canceled", "interrupted"}:
                        break
                    page.wait_for_timeout(50)
                assert host_job.get("status") == "succeeded", host_job
                terminal_gpu_jobs.append(host_job)
            observations["checks"]["K_broker_serializes_fake_gpu_jobs"] = {
                "waiting_reason": waiting_request.get("reason"),
                "queue_position": waiting_request.get("queue_position"),
                "terminal_states": [item["status"] for item in terminal_gpu_jobs],
            }

            asset_count_before_disable = len(media_request(args.media_forge_url, "/api/v1/assets")["items"])
            page.goto("/x/media-forge/workspace/library")
            embedded = media_frame(page)
            expect(embedded.locator("html")).to_have_attribute("data-bridge", "ready")
            disabled = addon_request(page, "/addons/media-forge/disable", "POST")
            assert disabled["status"] == 200
            expect(page.locator("iframe")).to_have_count(0, timeout=10_000)
            disabled_catalog = parsed(addon_request(page, "/addons/execution-contributions", "GET"))["contributions"]
            assert not any(item["addon_id"] == "media-forge" for item in disabled_catalog["workflow_executors"])
            saved_workflow = addon_request(page, f"/workflows/{workflow_id}", "GET")
            assert saved_workflow["status"] == 200, saved_workflow
            page.goto("/")
            expect(page.get_by_role("link", name="Media", exact=True)).to_have_count(0)
            observations["checks"]["L_disable_removes_contributions_preserves_workflow"] = True

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
                    if workflow_id is not None:
                        removed_workflow = addon_request(page, f"/workflows/{workflow_id}", "DELETE")
                        assert removed_workflow["status"] == 200, removed_workflow
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
