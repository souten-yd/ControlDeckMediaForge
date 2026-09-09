"""Isolated real HTTP/Blender update failure while the old GUI session is pinned.

Uses the previous clean-setup acceptance data only. Default mode replaces the
candidate probe script. --terminate-candidate-probe instead uses the unchanged
real probe and terminates only its exact staged process through a PID descriptor.
Download, extraction, binaries and old-version probe are real. Neither mode is
an installed Host/browser or naturally occurring failure acceptance.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import socket
import threading
import time
from typing import Any

import httpx
import uvicorn
from websockets.asyncio.client import connect

from mediaforge.app import create_app
from mediaforge.config import Settings, REPOSITORY_ROOT
from scripts.blender_runtime import load_spec, preflight
from scripts.blender_probe_fault import terminate_candidate_probe


async def run(args: argparse.Namespace) -> None:
    root = Path("/data1tb/mf-clean-packaged-0.28.32-QBvHfm")
    assert await asyncio.to_thread(root.resolve, strict=True) == root
    feature = root / "feature"
    data = feature / "data"
    await asyncio.to_thread(args.evidence_dir.mkdir, mode=0o700, parents=True, exist_ok=False)
    app = await asyncio.to_thread(create_app, Settings(data_dir=data,
        blender_legacy_runtime_root=root / "absent-legacy",
        blender_managed_runtime_root=feature / "runtimes/blender",
        blender_web_runtime_root=feature / "runtimes/blender-web"))
    manager = app.state.blender_runtime_operations
    original_probe = manager.preflight_script
    old, new = "blender-4.5.9-linux-x64", "blender-4.5.13-linux-x64"
    executable = feature / "runtimes/blender" / old / "install/blender"
    spec = await asyncio.to_thread(load_spec, REPOSITORY_ROOT / "config/blender-runtime.json")
    def binary_hash() -> str:
        with executable.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()
    before_hash = await asyncio.to_thread(binary_hash)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    started = time.monotonic()
    events: list[dict[str, Any]] = []
    session_id: str | None = None
    gateway = None
    fault_stop = threading.Event()
    fault_task: asyncio.Task[dict[str, int | str]] | None = None

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
            async def get(path: str) -> Any:
                response = await client.get(path)
                response.raise_for_status()
                return response.json()

            async def post(path: str, payload: dict[str, Any]) -> Any:
                response = await client.post(path, json=payload)
                assert response.is_success, response.text
                response.raise_for_status()
                return response.json()

            runtime_path = "/workspace-api/blender/runtime"
            sessions_path = "/workspace-api/blender/sessions"
            async def wait_operation(operation_id: str) -> dict[str, Any]:
                async with asyncio.timeout(300):
                    while True:
                        value = next(x for x in (await get(runtime_path))["operations"] if x["id"] == operation_id)
                        if value["state"] in {"ready", "failed", "canceled"}:
                            return value
                        await asyncio.sleep(0.5)

            async def current_session() -> dict[str, Any]:
                return next(x for x in (await get(sessions_path))["items"] if x["id"] == session_id)

            baseline = await get(runtime_path)
            if args.terminate_candidate_probe:
                assert not [s for s in (await get(sessions_path))['items']
                            if s['state'] not in {'stopped', 'failed', 'interrupted'}]
                assert not [o for o in baseline['operations'] if o['state'] not in {'ready', 'failed', 'canceled'}]
                assert baseline['active_runtime_id'] in {old, new}
                if baseline['active_runtime_id'] != old:
                    switch = await post(runtime_path + '/operations', {'action': 'switch', 'runtime_id': old})
                    assert (await wait_operation(switch['id']))['state'] == 'ready'
                if new in {r['runtime_id'] for r in baseline['runtimes']}:
                    preview = await post(runtime_path + '/operations', {'action': 'remove_preview', 'runtime_id': new})
                    assert preview['can_remove'] and preview['project_reference_count'] == 0
                    removal = await post(runtime_path + '/operations', {'action': 'remove', 'runtime_id': new,
                        'confirmation_fingerprint': preview['confirmation_fingerprint']})
                    assert (await wait_operation(removal['id']))['state'] == 'ready'
                baseline = await get(runtime_path)
            assert baseline["active_runtime_id"] == old
            assert {r["runtime_id"] for r in baseline["runtimes"]} == {old}
            scene_path = "/workspace-api/scenes/scene_2642c93f480d427d920267ac790405e2"
            scene_before = await get(scene_path)
            assets_before = await get("/api/v1/assets")
            existing = [s for s in (await get(sessions_path))["items"]
                        if s["state"] not in {"failed", "stopped", "interrupted"}]
            assert len(existing) <= 1
            if existing:
                session = existing[0]
                assert session["scene_id"] == "scene_2642c93f480d427d920267ac790405e2"
            else:
                session = await post(sessions_path, {"action": "start", "scene_id": "scene_2642c93f480d427d920267ac790405e2"})
            session_id = session["id"]
            await record("session_started", session=session)
            async with asyncio.timeout(90):
                while (session := await current_session())["state"] != "ready":
                    assert session["state"] not in {"failed", "stopped", "interrupted"}, session
                    await asyncio.sleep(0.5)
            assert session["runtime_id"] == old
            origin = str(client.base_url).rstrip("/")
            gateway = await connect(origin.replace("http:", "ws:", 1) +
                                    f"/workspace-api/blender/sessions/{session_id}/rfb", origin=origin,
                                    subprotocols=["binary"])
            buffered = bytearray()
            async def read_rfb(size: int) -> bytes:
                while len(buffered) < size:
                    chunk = await gateway.recv()
                    assert isinstance(chunk, bytes)
                    buffered.extend(chunk)
                value = bytes(buffered[:size])
                del buffered[:size]
                return value
            async with asyncio.timeout(20):
                assert (await read_rfb(12)).startswith(b"RFB ")
                await gateway.send(b"RFB 003.008\n")
                kinds = await read_rfb((await read_rfb(1))[0])
                assert 1 in kinds
                await gateway.send(b"\x01")
                assert await read_rfb(4) == b"\x00" * 4
                await gateway.send(b"\x01")
                header = await read_rfb(24)
                name = await read_rfb(int.from_bytes(header[20:24], "big"))
            await record("rfb_handshake", width=int.from_bytes(header[:2], "big"),
                         height=int.from_bytes(header[2:4], "big"), name=name.decode(errors="replace"))
            await record("old_session_ready", session=session, executable_sha256=before_hash)
            if not args.terminate_candidate_probe:
                manager.preflight_script = REPOSITORY_ROOT / "scripts/fixtures/blender_probe_reject.py"
            created = await post(runtime_path + "/operations", {"action": "update"})
            if args.terminate_candidate_probe:
                fault_task = asyncio.create_task(asyncio.to_thread(terminate_candidate_probe,
                    feature / 'runtimes/blender', created['id'], parent_pid=os.getpid(),
                    script=original_probe, version='4.5.13', stop=fault_stop))
            failed = await wait_operation(created["id"])
            if fault_task is not None:
                await record('owned_candidate_probe_terminated', **await fault_task)
            assert failed["state"] == "failed" and failed["error_code"] == "blender_runtime_install_failed", failed
            assert ('preflight failed' if args.terminate_candidate_probe else 'preflight result differs') in failed['error_message'], failed
            status = await get(runtime_path)
            assert status["active_runtime_id"] == old
            assert {r["runtime_id"] for r in status["runtimes"]} == {old}
            assert (await current_session())["state"] == "ready"
            manager.preflight_script = original_probe
            old_probe = await asyncio.to_thread(preflight, executable, original_probe, spec)
            assert await asyncio.to_thread(binary_hash) == before_hash
            assert await get(scene_path) == scene_before
            assert await get("/api/v1/assets") == assets_before
            await record("candidate_rejected_old_usable", operation=failed, old_probe=old_probe,
                         session=await current_session(), scene_unchanged=True, assets_unchanged=True)
            retry = await post(runtime_path + "/operations", {"action": "update"})
            ready = await wait_operation(retry["id"])
            assert ready["state"] == "ready", ready
            assert (await get(runtime_path))["active_runtime_id"] == new
            pinned = await current_session()
            assert pinned["state"] == "ready" and pinned["runtime_id"] == old
            await record("retry_ready_old_session_pinned", operation=ready, session=pinned)
            await post(sessions_path, {"action": "stop", "session_id": session_id})
            async with asyncio.timeout(30):
                while (session := await current_session())["state"] != "stopped":
                    await asyncio.sleep(0.2)
            switch = await post(runtime_path + "/operations", {"action": "switch", "runtime_id": old})
            assert (await wait_operation(switch["id"]))["state"] == "ready"
            assert await get(scene_path) == scene_before and await get("/api/v1/assets") == assets_before
            assert await asyncio.to_thread(binary_hash) == before_hash
            await record("passed", session=session, active_runtime_id=(await get(runtime_path))["active_runtime_id"])
    except Exception as exc:
        await record("failed", error_type=type(exc).__name__, message=str(exc)[:300])
        raise
    finally:
        fault_stop.set()
        if fault_task is not None:
            await asyncio.gather(fault_task, return_exceptions=True)
        try:
            # New mode never leaves its own GUI running after an assertion or
            # injection timeout. Do not affect a session from another run.
            if args.terminate_candidate_probe and session_id is not None and server.started:
                async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{listener.getsockname()[1]}", timeout=15) as cleanup:
                    response = await cleanup.get('/workspace-api/blender/sessions')
                    response.raise_for_status()
                    current = next(s for s in response.json()['items'] if s['id'] == session_id)
                    if current['state'] not in {'stopped', 'failed', 'interrupted'}:
                        response = await cleanup.post('/workspace-api/blender/sessions',
                            json={'action': 'stop', 'session_id': session_id})
                        response.raise_for_status()
                        async with asyncio.timeout(45):
                            while True:
                                response = await cleanup.get('/workspace-api/blender/sessions')
                                response.raise_for_status()
                                current = next(s for s in response.json()['items'] if s['id'] == session_id)
                                if current['state'] in {'stopped', 'failed', 'interrupted'}:
                                    break
                                await asyncio.sleep(0.2)
        finally:
            manager.preflight_script = original_probe
            if gateway is not None:
                await gateway.close()
            server.should_exit = True
            await serving
            listener.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument('--terminate-candidate-probe', action='store_true',
        help='Isolated root only: remove unreferenced candidate, SIGTERM its exact new probe via pidfd, then retry')
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
