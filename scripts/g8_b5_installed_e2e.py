#!/usr/bin/env python3
"""Installed-ControlDeck acceptance for G8 Blender workspace/agent/grant/cancel.

Run this with ControlDeck's Python environment because browser automation and
Argon2 belong to the Host test fixture, not the Media Forge core environment.
The temporary fixture password and only the sessions created by this run are
restored/revoked in ``finally`` and are never printed.
"""

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import io
import json
from pathlib import Path
import secrets
import sqlite3
import struct
import time
from typing import Any, Iterator
import zipfile

from argon2 import PasswordHasher
from playwright.sync_api import Page, sync_playwright


TERMINAL = {"succeeded", "failed", "canceled", "interrupted"}
BLENDER_EXECUTABLE = (
    Path(__file__).resolve().parents[1] / "runtimes/blender-4.5.9/install/blender"
).resolve()


def check(value: object, message: str) -> None:
    if not value:
        raise AssertionError(message)


def generated_grid_glb(cells: int = 317) -> bytes:
    positions = [(float(x), float(y), 0.0) for y in range(cells + 1) for x in range(cells + 1)]
    indices: list[int] = []
    stride = cells + 1
    for y in range(cells):
        for x in range(cells):
            a = y * stride + x
            indices.extend((a, a + stride, a + 1, a + 1, a + stride, a + stride + 1))
    position_bytes = struct.pack(
        f"<{len(positions) * 3}f", *(component for point in positions for component in point)
    )
    index_bytes = struct.pack(f"<{len(indices)}I", *indices)
    binary = position_bytes + index_bytes
    document = {
        "asset": {"version": "2.0", "generator": "Media Forge generated G8 B5 fixture"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": len(positions), "type": "VEC3"},
            {"bufferView": 1, "componentType": 5125, "count": len(indices), "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(position_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": len(position_bytes), "byteLength": len(index_bytes), "target": 34963},
        ],
        "buffers": [{"byteLength": len(binary)}],
    }
    encoded = json.dumps(document, separators=(",", ":")).encode()
    encoded += b" " * (-len(encoded) % 4)
    binary += b"\0" * (-len(binary) % 4)
    length = 12 + 8 + len(encoded) + 8 + len(binary)
    return (
        struct.pack("<4sII", b"glTF", 2, length)
        + struct.pack("<I4s", len(encoded), b"JSON") + encoded
        + struct.pack("<I4s", len(binary), b"BIN\0") + binary
    )


@contextmanager
def fixture_login(db_path: Path, username: str) -> Iterator[str]:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        "SELECT id, password_hash, updated_at, last_login_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row is None:
        connection.close()
        raise RuntimeError("ControlDeck E2E user is missing")
    user_id = int(row["id"])
    original = (row["password_hash"], row["updated_at"], row["last_login_at"])
    session_floor = int(connection.execute("SELECT COALESCE(MAX(id), 0) FROM sessions").fetchone()[0])
    password = secrets.token_urlsafe(32)
    connection.execute(
        "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
        (PasswordHasher().hash(password), datetime.now(UTC).isoformat(), user_id),
    )
    connection.commit()
    try:
        yield password
    finally:
        now = datetime.now(UTC).isoformat()
        connection.execute(
            "UPDATE users SET password_hash = ?, updated_at = ?, last_login_at = ? WHERE id = ?",
            (*original, user_id),
        )
        connection.execute(
            "UPDATE sessions SET revoked_at = COALESCE(revoked_at, ?) WHERE user_id = ? AND id > ?",
            (now, user_id, session_floor),
        )
        connection.commit()
        connection.close()


def login(page: Page, username: str, password: str) -> None:
    page.goto("/login", wait_until="domcontentloaded")
    page.get_by_label("ユーザー名").fill(username)
    page.get_by_label("パスワード").fill(password)
    page.get_by_role("button", name="ログイン").click()
    page.wait_for_url(lambda url: "/login" not in url, timeout=20_000)


def workspace_frame(page: Page):
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        for frame in page.frames:
            if "/addon-frame/media-forge" in frame.url and frame.locator("#app").count():
                return frame
        page.wait_for_timeout(200)
    raise AssertionError("Media Forge workspace iframe did not become ready")


def host_api(page: Page, path: str, method: str = "GET", body: object | None = None) -> dict[str, Any]:
    result = page.evaluate(
        """async value => {
          const response = await fetch(`/api/v1${value.path}`, {
            method: value.method, credentials: 'same-origin',
            headers: {'X-Requested-With': 'ControlDeck', ...(value.body == null ? {} : {'Content-Type': 'application/json'})},
            body: value.body == null ? undefined : JSON.stringify(value.body),
          });
          const text = await response.text();
          return {status: response.status, body: text ? JSON.parse(text) : null};
        }""",
        {"path": path, "method": method, "body": body},
    )
    return result


def wait_media_job(frame, job_id: str, timeout: float = 120) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        last = frame.evaluate("id => call('jobs.get', {job_id: id})", job_id)
        if last.get("status") in TERMINAL:
            return last
        frame.wait_for_timeout(100)
    raise AssertionError(f"Media Forge job did not finish: {last}")


def wait_host_job(page: Page, job_id: str, timeout: float = 120) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        response = host_api(page, f"/jobs/{job_id}?events_from=0")
        check(response["status"] == 200, f"Host Job poll failed: {response}")
        last = response["body"]
        if last.get("status") in TERMINAL:
            return last
        page.wait_for_timeout(100)
    raise AssertionError(f"Host Job did not finish: {last}")


def project_request(asset_id: str) -> dict[str, Any]:
    return {
        "operation": "asset.pack",
        "intent": "Prepare the generated G8 B5 grid as a project-ready GLB",
        "inputs": [{"asset_id": asset_id}],
        "profile": "3d.project.glb",
        "constraints": {"compile_options": {
            "schema_version": "3d.compile-options@1", "apply_transforms": True,
            "repair_normals": True, "remove_degenerate": True,
            "merge_by_distance_m": None, "triangle_budget": 200000,
            "lod_ratios": [], "collision": "none", "materials": "preserve",
            "preview": "fixed_workbench",
        }},
        "output": {"format": "zip", "count": 1},
        "local_only": True,
    }


def package_facts(content: bytes) -> dict[str, Any]:
    check(len(content) <= 64 * 1024 * 1024, "ZIP exceeds artifact bound")
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        check(archive.namelist() == ["asset.glb", "manifest.json", "preview.png"], "ZIP entries differ")
        glb = archive.read("asset.glb")
        manifest_bytes = archive.read("manifest.json")
        preview = archive.read("preview.png")
    check(glb[:4] == b"glTF" and struct.unpack_from("<I", glb, 4)[0] == 2, "output GLB header differs")
    check(struct.unpack_from("<I", glb, 8)[0] == len(glb), "output GLB length differs")
    check(preview.startswith(b"\x89PNG\r\n\x1a\n"), "preview is not PNG")
    manifest = json.loads(manifest_bytes)
    check(manifest["asset"]["sha256"] == hashlib.sha256(glb).hexdigest(), "manifest GLB hash differs")
    check(manifest["preview"]["sha256"] == hashlib.sha256(preview).hexdigest(), "manifest preview hash differs")
    return {
        "zip_bytes": len(content), "zip_sha256": hashlib.sha256(content).hexdigest(),
        "glb_bytes": len(glb), "glb_sha256": hashlib.sha256(glb).hexdigest(),
        "preview_bytes": len(preview), "preview_sha256": hashlib.sha256(preview).hexdigest(),
        "manifest": manifest,
    }


def blender_processes() -> list[int]:
    found: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            executable = (entry / "exe").resolve(strict=True)
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
        except OSError:
            continue
        if executable == BLENDER_EXECUTABLE and "compile_asset.py" in command:
            found.append(int(entry.name))
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-deck-url", default="http://127.0.0.1:8765")
    parser.add_argument("--control-deck-db", type=Path, required=True)
    parser.add_argument("--username", default="mf-e2e")
    parser.add_argument("--host-root", type=Path, default=Path("/home/souten"))
    parser.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    fixture = args.host_root / f"media-forge-g8-b5-{secrets.token_hex(4)}.glb"
    export_dir = args.host_root / f"media-forge-g8-b5-export-{secrets.token_hex(4)}"
    fixture.write_bytes(generated_grid_glb())
    fixture.chmod(0o600)
    export_dir.mkdir(mode=0o700)
    observations: dict[str, Any] = {"source_bytes": fixture.stat().st_size}
    browser_errors: list[str] = []
    try:
        with fixture_login(args.control_deck_db, args.username) as password, sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(base_url=args.control_deck_url, viewport={"width": 1280, "height": 900})
            page = context.new_page()
            page.on("console", lambda message: browser_errors.append(f"console:{message.text}") if message.type == "error" else None)
            page.on("pageerror", lambda error: browser_errors.append(f"pageerror:{error}"))
            login(page, args.username, password)
            resources_before = host_api(page, "/resources")
            check(resources_before["status"] == 200, "resource snapshot is unavailable")
            page.goto("/x/media-forge/workspace/create", wait_until="domcontentloaded")
            frame = workspace_frame(page)
            frame.wait_for_selector('#app[aria-busy="false"]', timeout=20_000)

            # Direct browser bytes cross the opaque iframe transport once.
            browser_import = frame.evaluate(
                """async value => {
                  const binary = atob(value.base64); const bytes = new Uint8Array(binary.length);
                  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
                  return importFile(new File([bytes], value.name, {type: 'model/gltf-binary'}), 'source', null, 'model/gltf-binary');
                }""",
                {"base64": base64.b64encode(fixture.read_bytes()).decode(), "name": fixture.name},
            )
            check(browser_import["mime_type"] == "model/gltf-binary", "browser GLB import failed")

            # The Host picker creates a read grant. Only that opaque ID crosses into the frame/core.
            frame.click("#project-3d-host-file")
            page.get_by_role("button", name=str(args.host_root), exact=True).click()
            page.get_by_role("button", name=fixture.name, exact=True).click()
            frame.wait_for_function("() => state.project3dAsset?.mime_type === 'model/gltf-binary'", timeout=20_000)
            imported = frame.evaluate("() => state.project3dAsset")
            check("path" not in json.dumps(imported), "scoped import leaked a Host path")

            frame.click("#mode-advanced")
            frame.check("#project-3d-repair-normals")
            frame.check("#project-3d-remove-degenerate")
            frame.fill("#project-3d-triangle-budget", "200000")
            known = set(frame.evaluate("() => state.jobs.map(job => job.id)"))
            frame.click("#project-3d-submit")
            deadline = time.monotonic() + 20
            workspace_job: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                jobs = frame.evaluate("() => call('jobs.list', {})")
                workspace_job = next((item for item in jobs["items"] if item["id"] not in known and item["request"]["operation"] == "asset.pack"), None)
                if workspace_job:
                    break
                frame.wait_for_timeout(100)
            check(workspace_job is not None, "workspace compile job was not created")
            workspace_id = workspace_job["id"]
            page.reload(wait_until="domcontentloaded")
            frame = workspace_frame(page)
            frame.wait_for_selector('#app[aria-busy="false"]', timeout=20_000)
            recovered = frame.evaluate("id => call('jobs.get', {job_id: id})", workspace_id)
            check(recovered["id"] == workspace_id, "workspace reconnect lost the job")
            reconnect_status = recovered["status"]
            workspace_job = wait_media_job(frame, workspace_id)
            check(workspace_job["status"] == "succeeded", f"workspace compile failed: {workspace_job}")
            workspace_content = base64.b64decode(
                frame.evaluate("id => call('assets.content', {asset_id: id})", workspace_job["asset_ids"][0])["base64"]
            )
            workspace_package = package_facts(workspace_content)

            request = project_request(imported["id"])
            invoked = host_api(page, "/addons/media-forge/agent-tools/media.generate/invoke", "POST", {
                "arguments": request, "wait": True,
            })
            check(invoked["status"] == 200, f"agent compile failed: {invoked}")
            host_job_id = invoked["body"]["job_id"]
            agent_asset = invoked["body"]["output"]["asset_id"]
            host_job = wait_host_job(page, host_job_id)
            agent_content = base64.b64decode(
                frame.evaluate("id => call('assets.content', {asset_id: id})", agent_asset)["base64"]
            )
            agent_package = package_facts(agent_content)
            check(agent_package["zip_sha256"] == workspace_package["zip_sha256"], "two real Blender processes differ")

            grant = host_api(page, "/addons/media-forge/file-grants", "POST", {
                "path": str(export_dir), "kind": "export",
            })
            check(grant["status"] == 201, f"export grant failed: {grant}")
            placed = host_api(page, "/addons/media-forge/agent-tools/media.pack/invoke", "POST", {
                "arguments": {"asset_id": agent_asset, "output_grant_id": grant["body"]["grant_id"], "filename": "project-ready.zip"},
                "wait": True,
            })
            check(placed["status"] == 200, f"agent placement failed: {placed}")
            committed = export_dir / "project-ready.zip"
            check(committed.read_bytes() == agent_content, "committed grant bytes differ")
            receipt = placed["body"]["output"]
            check(receipt["sha256"] == agent_package["zip_sha256"], "placement receipt hash differs")
            check("path" not in json.dumps({"invoke": invoked, "placed": placed}), "agent payload leaked a path")

            # Cancel an Agent-backed CPU-only compile at the Host Job boundary.
            cancel_started = host_api(page, "/addons/media-forge/agent-tools/media.generate/invoke", "POST", {
                "arguments": request, "wait": False,
            })
            check(cancel_started["status"] == 202, f"cancel job was not accepted: {cancel_started}")
            cancel_host_id = cancel_started["body"]["job_id"]
            deadline = time.monotonic() + 30
            while not blender_processes() and time.monotonic() < deadline:
                page.wait_for_timeout(50)
            child_at_cancel = blender_processes()
            check(child_at_cancel, "real Blender child was not observed before cancel")
            canceled = host_api(page, f"/jobs/{cancel_host_id}/cancel", "POST")
            check(canceled["status"] == 200, f"Host cancel failed: {canceled}")
            deadline = time.monotonic() + 10
            while blender_processes() and time.monotonic() < deadline:
                page.wait_for_timeout(50)
            check(not blender_processes(), "Blender child remained after Host cancel")
            canceled_host = wait_host_job(page, cancel_host_id)
            check(canceled_host["status"] == "canceled", f"Host Job did not stay canceled: {canceled_host}")

            resources_after = host_api(page, "/resources")
            check(resources_after["status"] == 200, "final resource snapshot is unavailable")
            before_requests = {item["request_id"] for item in resources_before["body"].get("requests", [])}
            new_requests = [item for item in resources_after["body"].get("requests", []) if item["request_id"] not in before_requests]
            check(not new_requests, f"CPU-only G8 created GPU resource requests: {new_requests}")
            frame = workspace_frame(page)
            frame.click("#nav-library")
            frame.wait_for_function(
                "id => [...document.querySelectorAll(`[data-asset-id=\"${id}\"] img`)]"
                ".some(image => image.offsetWidth > 0 && image.offsetHeight > 0)",
                arg=agent_asset,
                timeout=20_000,
            )
            library_card_count = frame.locator(f'[data-asset-id="{agent_asset}"]').count()
            page.screenshot(path=str(args.evidence_dir / "g8-b5-installed-library.png"), full_page=True)
            browser.close()

            phases = [event.get("phase") for event in host_job.get("events", []) if event.get("phase")]
            observations.update({
                "browser_import": {"asset_id": browser_import["id"], "sha256": browser_import["sha256"]},
                "scoped_import": {"asset_id": imported["id"], "sha256": imported["sha256"]},
                "workspace": {
                    "job_id": workspace_id, "asset_id": workspace_job["asset_ids"][0],
                    "reconnect_status": reconnect_status,
                },
                "agent": {
                    "host_job_id": host_job_id, "asset_id": agent_asset, "phases": phases,
                    "status": host_job["status"], "phase": host_job.get("phase"),
                    "progress": host_job.get("progress"), "event_count": host_job.get("event_count"),
                },
                "package": agent_package,
                "deterministic_processes": 2,
                "placement": {"receipt": receipt, "committed_sha256": hashlib.sha256(committed.read_bytes()).hexdigest()},
                "cancel": {"host_job_id": cancel_host_id, "child_pids": child_at_cancel, "status": canceled_host["status"]},
                "gpu_resource_requests": len(new_requests),
                "browser_errors": browser_errors,
                "blender_children_final": blender_processes(),
                "library_card_count": library_card_count,
            })
            check(not browser_errors, f"browser emitted errors: {browser_errors}")
    finally:
        fixture.unlink(missing_ok=True)
        for child in export_dir.iterdir() if export_dir.exists() else []:
            child.unlink()
        export_dir.rmdir()
    (args.evidence_dir / "observations.json").write_text(
        json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(observations, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
