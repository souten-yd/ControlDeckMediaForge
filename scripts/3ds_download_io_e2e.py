"""Real archive/disk + HTTP health with explicit slow-write and transport fixtures.

Reads the fixed verified prior acceptance archive without modifying it. Writes
only fresh evidence data. This exercises download/cancel/resume, not Blender
installation, real CDN behavior, installed Host, or physical disk exhaustion.
"""
from __future__ import annotations

import argparse
import asyncio
from collections.abc import AsyncIterator
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
from mediaforge.blender_operation import BlenderRuntimeOperationAction, BlenderRuntimeOperationState
from mediaforge.config import Settings


SOURCE = Path("/data1tb/mf-clean-packaged-0.28.32-QBvHfm/feature/data/runtime-state/blender-downloads/blender-4.5.9-linux-x64.tar.xz")


def digest(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


class ArchiveStream(httpx.AsyncByteStream):
    def __init__(self, offset: int) -> None:
        self.offset = offset

    async def __aiter__(self) -> AsyncIterator[bytes]:
        handle = await asyncio.to_thread(SOURCE.open, "rb")
        try:
            await asyncio.to_thread(handle.seek, self.offset)
            while chunk := await asyncio.to_thread(handle.read, 1024 * 1024):
                yield chunk
        finally:
            await asyncio.to_thread(handle.close)


async def run(evidence: Path) -> None:
    await asyncio.to_thread(evidence.mkdir, mode=0o700, parents=True, exist_ok=False)
    app = await asyncio.to_thread(create_app, Settings(data_dir=evidence / "data",
        blender_managed_runtime_root=evidence / "managed", blender_legacy_runtime_root=evidence / "absent",
        blender_web_runtime_root=evidence / "web"))
    manager, store = app.state.blender_runtime_operations, app.state.store
    spec = await asyncio.to_thread(lambda: manager.spec)
    assert await asyncio.to_thread(SOURCE.resolve, strict=True) == SOURCE
    assert await asyncio.to_thread(digest, SOURCE) == spec.archive_sha256
    ranges: list[int] = []

    def response(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == spec.archive_url
        offset = int(request.headers.get("range", "bytes=0-").removeprefix("bytes=").removesuffix("-"))
        ranges.append(offset)
        headers = {"ETag": '"fixed-archive-fixture"', "Content-Length": str(spec.archive_size_bytes - offset)}
        if offset:
            assert request.headers["if-range"] == headers["ETag"]
            headers["Content-Range"] = f"bytes {offset}-{spec.archive_size_bytes - 1}/{spec.archive_size_bytes}"
        return httpx.Response(206 if offset else 200, headers=headers, stream=ArchiveStream(offset))

    manager.transport = httpx.MockTransport(response)
    entered, release = threading.Event(), threading.Event()
    original_append = manager._append_download_chunk
    loop_thread = threading.get_ident()

    def delayed_append(*args: Any) -> None:
        assert threading.get_ident() != loop_thread
        entered.set()
        assert release.wait(10), "acceptance write gate expired"
        original_append(*args)

    manager._append_download_chunk = delayed_append
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    download = None
    operation = None
    events: list[dict[str, Any]] = []
    started = time.monotonic()

    async def record(stage: str, **values: Any) -> None:
        row = {"stage": stage, "elapsed_sec": round(time.monotonic() - started, 3), **values}
        events.append(row)
        await asyncio.to_thread((evidence / "observations.json").write_text, json.dumps(events, indent=2) + "\n")
        print(json.dumps(row), flush=True)

    try:
        async with asyncio.timeout(15):
            while not server.started:
                assert not serving.done()
                await asyncio.sleep(0.05)
        operation = await asyncio.to_thread(store.create_blender_runtime_operation,
            "blender-4.5.9-linux-x64", spec.version, BlenderRuntimeOperationAction.INSTALL,
            bytes_total=spec.archive_size_bytes)
        partial = manager.download_root / (spec.archive_name + ".partial")
        metadata = manager.download_root / (spec.archive_name + ".partial.json")
        download = asyncio.create_task(manager._download_attempt(operation, spec, partial, metadata))
        assert await asyncio.to_thread(entered.wait, 5)
        async with httpx.AsyncClient(timeout=2) as client:
            health_started = time.monotonic()
            health = await client.get(f"http://127.0.0.1:{listener.getsockname()[1]}/health")
            health.raise_for_status()
            latency = time.monotonic() - health_started
        assert latency < 1 and not download.done()
        for _ in range(3):
            download.cancel()
            await asyncio.sleep(0.01)
        assert not download.done()
        release.set()
        result = (await asyncio.gather(download, return_exceptions=True))[0]
        assert isinstance(result, asyncio.CancelledError)
        checkpoint = await asyncio.to_thread(store.get_blender_runtime_operation, operation.id)
        assert checkpoint.bytes_done == 1024 * 1024
        assert (await asyncio.to_thread(partial.stat)).st_size == checkpoint.bytes_done
        await record("canceled_write_drained", cancel_count=3, persisted_bytes=checkpoint.bytes_done,
                     health_sec=latency, health_status=health.json()["status"])
        manager._append_download_chunk = original_append
        archive = await manager._download(operation, spec)
        actual = await asyncio.to_thread(digest, archive)
        assert actual == spec.archive_sha256
        assert await asyncio.to_thread(digest, SOURCE) == actual
        assert ranges == [0, 1024 * 1024], ranges
        assert not await asyncio.to_thread(partial.exists)
        assert not await asyncio.to_thread(metadata.exists)
        await record("passed", archive_sha256=actual, archive_bytes=spec.archive_size_bytes,
                     range_offsets=ranges, not_tested=["installation/probe", "real CDN", "installed Host", "physical ENOSPC"])
    finally:
        release.set()
        if download is not None:
            if not download.done():
                download.cancel()
            await asyncio.gather(download, return_exceptions=True)
        if operation is not None:
            # This was download-only acceptance, never a completed install.
            await asyncio.to_thread(store.update_blender_runtime_operation, operation.id,
                state=BlenderRuntimeOperationState.CANCELED, result={"download_only_acceptance": True})
        server.should_exit = True
        await serving
        listener.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    asyncio.run(run(parser.parse_args().evidence_dir))
