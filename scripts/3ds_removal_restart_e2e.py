"""Real isolated core-process restart with durable history removal confirmation.

Only the fixed prior clean acceptance root is writable. The first core pauses
removal before filesystem changes; SIGTERM exits that owned process. A fresh
unmodified core resumes the actual removal, then reinstalls the exact version.
This is an explicit timing fixture, not installed Host or crash/power-loss proof.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import sys
import time
from typing import Any

import httpx
import uvicorn

from mediaforge.app import create_app
from mediaforge.blender_operation import BlenderRuntimeOperationState
from mediaforge.config import Settings


ROOT = Path("/data1tb/mf-clean-packaged-0.28.32-QBvHfm/feature")
DATA = ROOT / "data"
OLD = "blender-4.5.9-linux-x64"
NEW = "blender-4.5.13-linux-x64"
RUNTIME = "/workspace-api/blender/runtime"


def snapshot() -> dict[str, Any]:
    assert ROOT.resolve(strict=True) == ROOT
    with sqlite3.connect(f"file:{DATA}/media-forge.sqlite3?mode=ro", uri=True) as db:
        assert db.execute("SELECT count(*) FROM blender_web_sessions WHERE state NOT IN (?,?,?)",
                          ("stopped", "failed", "interrupted")).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM blender_runtime_operations WHERE state NOT IN (?,?,?)",
                          ("ready", "failed", "canceled")).fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM jobs WHERE status NOT IN (?,?,?)",
                          ("succeeded", "failed", "canceled")).fetchone()[0] == 0
        scenes = db.execute("SELECT id,value_json FROM scene_documents ORDER BY id").fetchall()
        revisions = db.execute("SELECT id,value_json FROM scene_revisions ORDER BY id").fetchall()
    hashes = {}
    for path in sorted((DATA / "assets").rglob("*")):
        assert not path.is_symlink()
        if path.is_file():
            with path.open("rb") as handle:
                hashes[str(path.relative_to(DATA))] = hashlib.file_digest(handle, "sha256").hexdigest()
    assert hashes and scenes and revisions
    return {"scenes": scenes, "revisions": revisions, "hashes": hashes}


def child(fd: int, pause: bool) -> None:
    app = create_app(Settings(data_dir=DATA, blender_legacy_runtime_root=ROOT / "absent-legacy",
        blender_managed_runtime_root=ROOT / "runtimes/blender",
        blender_web_runtime_root=ROOT / "runtimes/blender-web"))
    if pause:
        async def paused_remove(operation: Any) -> None:
            await asyncio.to_thread(app.state.store.update_blender_runtime_operation, operation.id,
                                  state=BlenderRuntimeOperationState.PREFLIGHT)
            await asyncio.Event().wait()
        app.state.blender_runtime_operations._remove = paused_remove
    uvicorn.run(app, fd=fd, log_level="warning")


async def run(evidence: Path) -> None:
    await asyncio.to_thread(evidence.mkdir, mode=0o700, parents=True, exist_ok=False)
    before = await asyncio.to_thread(snapshot)
    process: asyncio.subprocess.Process | None = None
    events: list[dict[str, Any]] = []
    started = time.monotonic()

    async def record(stage: str, **values: Any) -> None:
        event = {"stage": stage, "elapsed_sec": round(time.monotonic() - started, 3), **values}
        events.append(event)
        await asyncio.to_thread((evidence / "observations.json").write_text, json.dumps(events, indent=2) + "\n")
        print(json.dumps(event), flush=True)

    async def start(pause: bool) -> str:
        nonlocal process
        assert process is None or process.returncode is not None
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        log = await asyncio.to_thread((evidence / ("paused-core.log" if pause else "resumed-core.log")).open, "xb")
        try:
            process = await asyncio.create_subprocess_exec(sys.executable, str(Path(__file__).resolve()),
                "--child-fd", str(listener.fileno()), *(["--pause-removal"] if pause else []),
                pass_fds=(listener.fileno(),), stdout=log, stderr=asyncio.subprocess.STDOUT)
        finally:
            listener.close()
            await asyncio.to_thread(log.close)
        url = f"http://127.0.0.1:{port}"
        async with httpx.AsyncClient(timeout=2) as client:
            async with asyncio.timeout(20):
                while True:
                    assert process.returncode is None, f"core exited {process.returncode}; inspect owned log"
                    try:
                        response = await client.get(url + "/health")
                        response.raise_for_status()
                        break
                    except httpx.TransportError:
                        await asyncio.sleep(0.1)
        await record("core_started", pid=process.pid, paused_removal=pause, health=response.json()["status"])
        return url

    async def stop() -> None:
        assert process is not None
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 20)
            except TimeoutError:
                process.kill()
                await process.wait()
                raise
        await record("core_exited", pid=process.pid, returncode=process.returncode)

    async def get(client: httpx.AsyncClient, path: str) -> Any:
        response = await client.get(path)
        response.raise_for_status()
        return response.json()

    async def post(client: httpx.AsyncClient, value: dict[str, Any]) -> Any:
        response = await client.post(RUNTIME + "/operations", json=value)
        response.raise_for_status()
        return response.json()

    async def wait(client: httpx.AsyncClient, operation_id: str, state: str = "ready") -> Any:
        async with asyncio.timeout(300):
            while True:
                operation = next(row for row in (await get(client, RUNTIME))["operations"] if row["id"] == operation_id)
                if operation["state"] == state:
                    return operation
                assert operation["state"] not in {"ready", "failed", "canceled"}, operation
                await asyncio.sleep(0.1)

    await record("baseline", snapshot=before)
    try:
        url = await start(True)
        async with httpx.AsyncClient(base_url=url, timeout=30) as client:
            status = await get(client, RUNTIME)
            original_active = status["active_runtime_id"]
            assert original_active in {OLD, NEW}
            assert {row["runtime_id"] for row in status["runtimes"]} == {OLD, NEW}
            assert all(row["state"] in {"ready", "failed", "canceled"} for row in status["operations"])
            switched = await post(client, {"action": "switch", "runtime_id": NEW})
            await wait(client, switched["id"])
            preview = await post(client, {"action": "remove_preview", "runtime_id": OLD})
            assert preview["can_remove_with_history"] and not preview["can_remove"]
            operation = await post(client, {"action": "remove", "runtime_id": OLD,
                "confirmation_fingerprint": preview["confirmation_fingerprint"], "acknowledge_history": True})
            paused = await wait(client, operation["id"], "preflight")
            assert paused["result"] == {"removal_preview": preview, "acknowledge_history": True}
        # A distinct HTTP client reconnects after the confirming connection closes.
        async with httpx.AsyncClient(base_url=url, timeout=30) as client:
            reconnected = await wait(client, operation["id"], "preflight")
            assert reconnected["result"] == paused["result"]
        await record("confirmation_survives_client_reconnect", operation=paused)
        first_pid = process.pid
        await stop()
        url = await start(False)
        assert process.pid != first_pid
        async with httpx.AsyncClient(base_url=url, timeout=30) as client:
            removed = await wait(client, operation["id"])
            assert removed["result"]["removal_preview"] == preview
            assert removed["result"]["acknowledge_history"] is True
            assert not await asyncio.to_thread((ROOT / "runtimes/blender" / OLD).exists)
            assert await asyncio.to_thread(snapshot) == before
            await record("same_confirmation_resumed", operation=removed, preserved_files=len(before["hashes"]))
            installed = await post(client, {"action": "install_exact", "runtime_id": OLD})
            installed = await wait(client, installed["id"])
            switched = await post(client, {"action": "switch", "runtime_id": original_active})
            await wait(client, switched["id"])
            assert await asyncio.to_thread(snapshot) == before
            await record("passed", reinstalled=installed, restored_default=original_active,
                not_tested=["installed Host/browser", "power loss", "mid-rename crash", "GUI re-edit"])
    finally:
        if process is not None and process.returncode is None:
            await stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--child-fd", type=int)
    parser.add_argument("--pause-removal", action="store_true")
    args = parser.parse_args()
    if args.child_fd is not None:
        child(args.child_fd, args.pause_removal)
    elif args.evidence_dir is not None:
        asyncio.run(run(args.evidence_dir))
    else:
        parser.error("--evidence-dir is required")
