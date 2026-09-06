"""Real pinned Blender setup over real loopback HTTP, with a throttled archive fixture.

Core Python, PYTHONPATH=backend:. NEW isolated data only. No installed Host,
credentials or service changes. Archive transport is synthetic; archive bytes,
hash verification, extraction and Blender probe are real. Not a browser test.
"""
from __future__ import annotations

import argparse
import asyncio
from collections.abc import AsyncIterator
import hashlib
import json
from pathlib import Path
import socket
import time
from typing import Any

import httpx
import uvicorn

from mediaforge.app import create_app
from mediaforge.config import Settings, REPOSITORY_ROOT
from scripts.blender_runtime import load_spec


class ArchiveStream(httpx.AsyncByteStream):
    def __init__(self, path: Path, offset: int, slow: bool) -> None:
        self.path, self.offset, self.slow = path, offset, slow

    async def __aiter__(self) -> AsyncIterator[bytes]:
        handle = await asyncio.to_thread(self.path.open, "rb")
        try:
            await asyncio.to_thread(handle.seek, self.offset)
            while chunk := await asyncio.to_thread(handle.read, 64 * 1024 if self.slow else 2 * 1024 * 1024):
                if self.slow:
                    await asyncio.sleep(1)
                yield chunk
        finally:
            await asyncio.to_thread(handle.close)


async def run(args: argparse.Namespace) -> None:
    spec = await asyncio.to_thread(load_spec, REPOSITORY_ROOT / "config/blender-runtime.json")
    def verify_archive() -> None:
        assert args.archive.stat().st_size == spec.archive_size_bytes
        with args.archive.open("rb") as handle:
            assert hashlib.file_digest(handle, "sha256").hexdigest() == spec.archive_sha256
    await asyncio.to_thread(verify_archive)
    await asyncio.to_thread(args.data_dir.mkdir, mode=0o700, parents=True, exist_ok=False)
    slow = True

    async def download(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == spec.archive_url
        offset = int(request.headers.get("Range", "bytes=0-").removeprefix("bytes=").removesuffix("-"))
        headers = {"Content-Length": str(spec.archive_size_bytes - offset), "ETag": '"pinned-fixture"'}
        if offset:
            headers["Content-Range"] = f"bytes {offset}-{spec.archive_size_bytes - 1}/{spec.archive_size_bytes}"
        return httpx.Response(206 if offset else 200, headers=headers,
            stream=ArchiveStream(args.archive, offset, slow), request=request)

    app = await asyncio.to_thread(create_app, Settings(data_dir=args.data_dir,
        blender_legacy_runtime_root=args.data_dir / "absent-legacy"),
        blender_download_transport=httpx.MockTransport(download))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    started = time.monotonic()
    observations: list[dict[str, Any]] = []

    async def record(stage: str, **values: Any) -> None:
        event = {"stage": stage, "elapsed_sec": round(time.monotonic() - started, 3), **values}
        observations.append(event)
        await asyncio.to_thread((args.data_dir / "observations.json").write_text,
            json.dumps(observations, indent=2) + "\n")
        print(json.dumps(event), flush=True)

    try:
        async with asyncio.timeout(15):
            while not server.started:
                if serving.done():
                    await serving
                    raise RuntimeError("Source server stopped")
                await asyncio.sleep(0.05)
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{listener.getsockname()[1]}", timeout=30) as client:
            async def action(value: dict[str, Any]) -> dict[str, Any]:
                response = await client.post("/workspace-api/blender/runtime/operations", json=value)
                response.raise_for_status()
                return response.json()

            async def operation(operation_id: str) -> dict[str, Any]:
                response = await client.get("/workspace-api/blender/runtime")
                response.raise_for_status()
                return next(item for item in response.json()["operations"] if item["id"] == operation_id)

            created = await action({"action": "install"})
            await record("created", operation=created)
            while time.monotonic() - started < 620:
                current = await operation(created["id"])
                assert current["state"] not in {"ready", "failed", "canceled"}, current
                health = await client.get("/health")
                health.raise_for_status()
                await record("holding", state=current["state"], bytes_done=current["bytes_done"])
                await asyncio.sleep(30)
            await action({"action": "cancel", "operation_id": created["id"]})
            async with asyncio.timeout(15):
                while (current := await operation(created["id"]))["state"] != "canceled":
                    await asyncio.sleep(0.1)
            await record("canceled_after_ten_minutes", operation=current)
            slow = False
            retry = await action({"action": "install"})
            async with asyncio.timeout(180):
                while (current := await operation(retry["id"]))["state"] not in {"ready", "failed", "canceled"}:
                    await asyncio.sleep(0.5)
            assert current["state"] == "ready", current
            await record("reinstalled", operation=current, archive_sha256=spec.archive_sha256,
                not_tested=["real remote download", "Host credentials", "Settings browser UI"])
    finally:
        server.should_exit = True
        await serving


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
