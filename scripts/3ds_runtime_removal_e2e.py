"""Real isolated HTTP deletion protection and asset-byte preservation acceptance.

Uses only the owned prior clean setup root, never the installed Host. Deletes
the unreferenced candidate 4.5.13, not project-pinned 4.5.9. Reinstalling the
candidate through Settings/update restores it; assets are never deleted here.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
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
                async with asyncio.timeout(90):
                    while True:
                        value = next(x for x in (await get(runtime_path))["operations"] if x["id"] == created["id"])
                        if value["state"] in {"ready", "failed", "canceled"}:
                            assert value["state"] == "ready", value
                            return value
                        await asyncio.sleep(0.2)

            status = await get(runtime_path)
            assert status["active_runtime_id"] in {old, candidate}
            assert {r["runtime_id"] for r in status["runtimes"]} == {old, candidate}
            existing = [s for s in (await get(sessions_path))["items"]
                        if s["state"] not in {"stopped", "interrupted", "failed"}]
            assert len(existing) <= 1
            scene_before, assets_before = await get(scene_path), await get("/api/v1/assets")
            await record("baseline", assets=hashes_before, scene=scene_before)
            if existing:
                session = existing[0]
                assert session["scene_id"] == scene_before["scene"]["id"]
            else:
                session = await post(sessions_path, {"action": "start", "scene_id": scene_before["scene"]["id"]})
            session_id = session["id"]

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
            await operation({"action": "switch", "runtime_id": candidate})

            async def reject_old(stage: str, session_state: str) -> None:
                current = next(s for s in (await get(sessions_path))["items"] if s["id"] == session_id)
                assert current["state"] == session_state and current["runtime_id"] == old
                preview = await post(actions_path, {"action": "remove_preview", "runtime_id": old})
                assert not preview["can_remove"] and not preview["active"], preview
                assert preview["project_reference_count"] > 0
                assert "project_reference" in preview["blocked_reasons"]
                response = await client.post(actions_path, json={"action": "remove", "runtime_id": old,
                    "confirmation_fingerprint": preview["confirmation_fingerprint"]})
                assert response.status_code == 422, response.text
                assert response.json()["detail"]["code"] == "blender_runtime_in_use", response.text
                await record(stage, preview=preview, rejection=response.json(), session=current)

            await reject_old("running_session_project_protected", "ready")
            await post(sessions_path, {"action": "stop", "session_id": session_id})
            stopped = await wait_session("stopped")
            await reject_old("stopped_project_still_protected", "stopped")
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
        server.should_exit = True
        await serving
        listener.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
