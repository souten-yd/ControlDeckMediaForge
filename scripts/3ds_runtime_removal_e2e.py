"""Real isolated HTTP deletion protection and asset-byte preservation acceptance.

Uses only the owned prior clean setup root, never the installed Host. Default
mode deletes the unreferenced candidate 4.5.13. --history-reinstall explicitly
removes project-pinned inactive 4.5.9, checks preserved history/assets, installs
that exact version again and reopens the same scene. Assets are never deleted.
--hold-removal adds an explicit thread barrier inside the real deletion guard;
it does not model a naturally occurring slow filesystem or installed Host race.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
import threading
import time
from typing import Any

import httpx
import uvicorn

from mediaforge.app import create_app
from mediaforge.config import Settings


def asset_hashes(root: Path) -> dict[str, dict[str, Any]]:
    """Hash all immutable asset files, including provenance, off the event loop."""
    rows: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        assert not path.is_symlink(), path
        if path.is_file():
            with path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            rows[str(path.relative_to(root))] = {"size": path.stat().st_size, "sha256": digest}
    assert rows and any(name.endswith(".blend") for name in rows)
    assert any(name.endswith(".glb") for name in rows)
    return rows


async def run(args: argparse.Namespace) -> None:
    root = Path("/data1tb/mf-clean-packaged-0.28.32-QBvHfm")
    feature = root / "feature"
    data = feature / "data"
    managed = feature / "runtimes/blender"
    old, candidate = "blender-4.5.9-linux-x64", "blender-4.5.13-linux-x64"
    await asyncio.to_thread(args.evidence_dir.mkdir, mode=0o700, parents=True, exist_ok=False)
    app = await asyncio.to_thread(create_app, Settings(data_dir=data,
        blender_legacy_runtime_root=root / "absent-legacy",
        blender_managed_runtime_root=managed,
        blender_web_runtime_root=feature / "runtimes/blender-web"))
    admission_entered, admission_release = threading.Event(), threading.Event()
    removal_entered, removal_release = threading.Event(), threading.Event()
    gui_admission_entered = threading.Event()
    if args.hold_removal:
        original_unregister = app.state.scene_workspace.resolver.unregister_managed
        original_create = app.state.blender_sessions._create_guarded

        def observed_create(*values: Any) -> Any:
            if removal_entered.is_set() and not removal_release.is_set():
                gui_admission_entered.set()
            return original_create(*values)

        def held_unregister(runtime_id: str) -> bool:
            assert runtime_id == old
            removal_entered.set()
            if not removal_release.wait(15):
                raise TimeoutError("acceptance removal gate was not released")
            return original_unregister(runtime_id)

        app.state.scene_workspace.resolver.unregister_managed = held_unregister
        app.state.blender_sessions._create_guarded = observed_create
    if args.hold_working_admission:
        original_acquire = app.state.scene_workspace._acquire_working_copy

        def held_acquire(*values: Any) -> Any:
            admission_entered.set()
            if not admission_release.wait(15):
                raise TimeoutError("acceptance admission gate was not released")
            return original_acquire(*values)

        app.state.scene_workspace._acquire_working_copy = held_acquire
    hashes_before = await asyncio.to_thread(asset_hashes, data / "assets")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    events: list[dict[str, Any]] = []
    started = time.monotonic()

    async def record(stage: str, **values: Any) -> None:
        row = {"stage": stage, "elapsed_sec": round(time.monotonic() - started, 3), **values}
        events.append(row)
        await asyncio.to_thread((args.evidence_dir / "observations.json").write_text,
            json.dumps(events, indent=2) + "\n")
        print(json.dumps(row), flush=True)

    try:
        async with asyncio.timeout(15):
            while not server.started:
                if serving.done():
                    await serving
                    raise RuntimeError("server stopped before startup")
                await asyncio.sleep(0.05)
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{listener.getsockname()[1]}", timeout=30) as client:
            runtime_path = "/workspace-api/blender/runtime"
            actions_path = runtime_path + "/operations"
            sessions_path = "/workspace-api/blender/sessions"
            scene_path = "/workspace-api/scenes/scene_2642c93f480d427d920267ac790405e2"

            async def get(path: str) -> Any:
                response = await client.get(path)
                response.raise_for_status()
                return response.json()

            async def post(path: str, payload: dict[str, Any]) -> Any:
                response = await client.post(path, json=payload)
                assert response.is_success, response.text
                return response.json()

            async def operation(payload: dict[str, Any]) -> dict[str, Any]:
                created = await post(actions_path, payload)
                async with asyncio.timeout(300):
                    while True:
                        value = next(x for x in (await get(runtime_path))["operations"] if x["id"] == created["id"])
                        if value["state"] in {"ready", "failed", "canceled"}:
                            assert value["state"] == "ready", value
                            return value
                        await asyncio.sleep(0.2)

            status = await get(runtime_path)
            assert status["active_runtime_id"] in {old, candidate}
            if args.history_reinstall and candidate not in {r["runtime_id"] for r in status["runtimes"]}:
                await operation({"action": "install_exact", "runtime_id": candidate})
                status = await get(runtime_path)
            if args.live_references_only:
                assert old in {r["runtime_id"] for r in status["runtimes"]}
            else:
                assert {r["runtime_id"] for r in status["runtimes"]} == {old, candidate}
            sessions_before = (await get(sessions_path))["items"]
            existing = [s for s in sessions_before
                        if s["state"] not in {"stopped", "interrupted", "failed"}]
            assert len(existing) <= 1
            if args.hold_working_admission or args.hold_removal:
                assert not existing, "held admission requires a new session, not an existing runner"
            scene_before, assets_before = await get(scene_path), await get("/api/v1/assets")
            await record("baseline", assets=hashes_before, scene=scene_before)
            if existing:
                session = existing[0]
                assert session["scene_id"] == scene_before["scene"]["id"]
            else:
                session = await post(sessions_path, {"action": "start", "scene_id": scene_before["scene"]["id"]})
            session_id = session["id"]
            if args.hold_working_admission:
                assert session["runtime_id"] == old and session["runtime_version"] == "4.5.9"
                assert await asyncio.to_thread(admission_entered.wait, 5)
                pending_preview = asyncio.create_task(post(actions_path,
                    {"action": "remove_preview", "runtime_id": old}))
                await asyncio.sleep(0.2)
                health_started = time.monotonic()
                health_response = await client.get("/health")
                health_response.raise_for_status()
                health_elapsed = time.monotonic() - health_started
                assert health_elapsed < 2, health_elapsed
                assert not pending_preview.done()
                admission_release.set()
                guarded_preview = await pending_preview
                assert guarded_preview["durable_reference_counts"]["sessions"] == 1
                assert guarded_preview["durable_reference_counts"]["working_copies"] == 1
                await record("held_admission_released", queued_session=session,
                    health_http_status=health_response.status_code,
                    health_status=health_response.json()["status"], health_elapsed_sec=round(health_elapsed, 6),
                    preview_was_pending=True, preview_after_release=guarded_preview)

            async def wait_session(target: str) -> dict[str, Any]:
                async with asyncio.timeout(90):
                    while True:
                        value = next(s for s in (await get(sessions_path))["items"] if s["id"] == session_id)
                        if value["state"] == target:
                            return value
                        assert value["state"] not in {"failed", "interrupted"}, value
                        await asyncio.sleep(0.2)

            ready = await wait_session("ready")
            assert ready["runtime_id"] == old
            if not args.live_references_only:
                await operation({"action": "switch", "runtime_id": candidate})

            async def reject_old(stage: str, session_state: str) -> None:
                current = next(s for s in (await get(sessions_path))["items"] if s["id"] == session_id)
                assert current["state"] == session_state and current["runtime_id"] == old
                preview = await post(actions_path, {"action": "remove_preview", "runtime_id": old})
                assert not preview["can_remove"], preview
                if not args.live_references_only:
                    assert not preview["active"], preview
                assert preview["project_reference_count"] > 0
                assert "project_reference" in preview["blocked_reasons"]
                if args.live_references_only:
                    durable = preview["durable_reference_counts"]
                    assert durable["sessions"] == int(session_state == "ready"), preview
                    assert durable["working_copies"] == int(session_state == "ready"), preview
                    assert durable["recipe_jobs"] == durable["unresolved_sessions"] == 0
                    assert preview["in_process_reference_count"] == 0
                    if session_state == "ready":
                        assert "live_reference" in preview["blocked_reasons"]
                response = await client.post(actions_path, json={"action": "remove", "runtime_id": old,
                    "confirmation_fingerprint": preview["confirmation_fingerprint"]})
                assert response.status_code == 422, response.text
                assert response.json()["detail"]["code"] == "blender_runtime_in_use", response.text
                if args.history_reinstall and session_state == "ready":
                    assert not preview["can_remove_with_history"]
                    acknowledged = await client.post(actions_path, json={"action": "remove", "runtime_id": old,
                        "confirmation_fingerprint": preview["confirmation_fingerprint"], "acknowledge_history": True})
                    assert acknowledged.status_code == 422, acknowledged.text
                await record(stage, preview=preview, rejection=response.json(), session=current)

            await reject_old("running_session_project_protected", "ready")
            await post(sessions_path, {"action": "stop", "session_id": session_id})
            stopped = await wait_session("stopped")
            await reject_old("stopped_project_still_protected", "stopped")
            if args.history_reinstall:
                preview = await post(actions_path, {"action": "remove_preview", "runtime_id": old})
                assert preview["can_remove_with_history"] and not preview["can_remove"]
                removal = asyncio.create_task(operation({"action": "remove", "runtime_id": old,
                    "confirmation_fingerprint": preview["confirmation_fingerprint"], "acknowledge_history": True}))
                if args.hold_removal:
                    contender = None
                    try:
                        assert await asyncio.to_thread(removal_entered.wait, 5)
                        contender = asyncio.create_task(client.post(sessions_path,
                            json={"action": "start", "scene_id": scene_before["scene"]["id"]}))
                        assert await asyncio.to_thread(gui_admission_entered.wait, 5)
                        await asyncio.sleep(0.2)
                        health_started = time.monotonic()
                        response = await client.get("/health")
                        response.raise_for_status()
                        health_elapsed = time.monotonic() - health_started
                        assert health_elapsed < 2, health_elapsed
                        assert not contender.done(), "GUI admission bypassed removal guard"
                        await record("removal_holds_gui_admission", health_elapsed_sec=health_elapsed,
                            health_status=response.json()["status"], gui_request_pending=True)
                    finally:
                        removal_release.set()
                        try:
                            if contender is not None:
                                rejected = await contender
                        finally:
                            await removal
                    assert rejected.status_code == 422, rejected.text
                    assert rejected.json()["detail"]["code"] == "scene_runtime_unavailable", rejected.text
                    assert len((await get(sessions_path))["items"]) == len(sessions_before) + 1
                    await record("removal_first_gui_rejected", rejection=rejected.json())
                removed = await removal
                assert removed["result"]["acknowledge_history"] is True
                assert not await asyncio.to_thread((managed / old).exists)
                assert (await get(runtime_path))["active_runtime_id"] == candidate
                assert await get(scene_path) == scene_before
                assert await get("/api/v1/assets") == assets_before
                assert await asyncio.to_thread(asset_hashes, data / "assets") == hashes_before
                unavailable = await client.post(sessions_path, json={"action": "start", "scene_id": scene_before["scene"]["id"]})
                assert unavailable.status_code == 422, unavailable.text
                await record("history_preserved_after_old_removal", removed=removed, unavailable=unavailable.json(), assets=hashes_before)
                reinstalled = await operation({"action": "install_exact", "runtime_id": old})
                assert (await get(runtime_path))["active_runtime_id"] == candidate
                reopened = await post(sessions_path, {"action": "start", "scene_id": scene_before["scene"]["id"]})
                session_id = reopened["id"]
                ready_again = await wait_session("ready")
                assert ready_again["runtime_id"] == old and ready_again["runtime_version"] == "4.5.9"
                await post(sessions_path, {"action": "stop", "session_id": session_id})
                await wait_session("stopped")
                assert await get(scene_path) == scene_before
                assert await get("/api/v1/assets") == assets_before
                assert await asyncio.to_thread(asset_hashes, data / "assets") == hashes_before
                if args.hold_removal:
                    await operation({"action": "switch", "runtime_id": status["active_runtime_id"]})
                await record("history_reinstall_passed", reinstalled=reinstalled, reopened=ready_again,
                    assets_unchanged=hashes_before, not_tested=["installed Host/browser", "GUI framebuffer/input"])
                return
            if args.live_references_only:
                assert await get(scene_path) == scene_before
                assert await get("/api/v1/assets") == assets_before
                assert await asyncio.to_thread(asset_hashes, data / "assets") == hashes_before
                await record("live_references_passed", session=stopped, assets_unchanged=hashes_before,
                    not_tested=["installed Host/browser", "GUI framebuffer/input", "confirmed history removal",
                                "atomic GUI admission/removal race", "runtime deletion"])
                return
            await operation({"action": "switch", "runtime_id": old})
            preview = await post(actions_path, {"action": "remove_preview", "runtime_id": candidate})
            assert preview["can_remove"] and not preview["blocked_reasons"], preview
            await record("unreferenced_candidate_removal_preview", preview=preview)
            removed = await operation({"action": "remove", "runtime_id": candidate,
                "confirmation_fingerprint": preview["confirmation_fingerprint"]})
            assert not await asyncio.to_thread((managed / candidate).exists)
            assert await asyncio.to_thread((managed / old / "install/blender").is_file)
            final = await get(runtime_path)
            assert final["active_runtime_id"] == old
            assert {r["runtime_id"] for r in final["runtimes"]} == {old}
            assert await get(scene_path) == scene_before
            assert await get("/api/v1/assets") == assets_before
            assert await asyncio.to_thread(asset_hashes, data / "assets") == hashes_before
            await record("passed", removed=removed, session=stopped, assets_unchanged=hashes_before,
                not_tested=["installed Host/browser", "remove project-pinned old runtime", "external unregister"])
    except Exception as exc:
        await record("failed", error_type=type(exc).__name__, message=str(exc)[:300])
        raise
    finally:
        admission_release.set()
        removal_release.set()
        server.should_exit = True
        await serving
        listener.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--live-references-only", action="store_true",
                        help="Start/stop real GUI and assert durable blockers; do not switch or delete runtimes")
    parser.add_argument("--hold-working-admission", action="store_true",
                        help="Inject a thread gate during copy admission and verify HTTP remains responsive")
    parser.add_argument("--history-reinstall", action="store_true",
                        help="Remove inactive project-pinned 4.5.9 with acknowledgement and reinstall the exact version")
    parser.add_argument("--hold-removal", action="store_true",
                        help="Hold real removal before unregister; verify concurrent GUI admission and HTTP health")
    args = parser.parse_args()
    if args.hold_working_admission and not args.live_references_only:
        parser.error("--hold-working-admission requires --live-references-only")
    if args.history_reinstall and args.live_references_only:
        parser.error("--history-reinstall cannot be combined with --live-references-only")
    if args.hold_removal and not args.history_reinstall:
        parser.error("--hold-removal requires --history-reinstall")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
