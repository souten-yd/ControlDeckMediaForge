"""Real isolated HTTP/Blender repair rejection; never uses installed Host data."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import time
from typing import Any

import httpx
import uvicorn

from mediaforge.app import create_app
from mediaforge.config import Settings


async def run(evidence_dir: Path) -> None:
    root = Path('/data1tb/mf-clean-packaged-0.28.32-QBvHfm')
    feature = root / 'feature'
    data = feature / 'data'
    runtime_id = 'blender-4.5.9-linux-x64'
    scene_id = 'scene_2642c93f480d427d920267ac790405e2'

    def baseline() -> dict[str, str]:
        assert root.resolve(strict=True) == root
        with sqlite3.connect(f'file:{data}/media-forge.sqlite3?mode=ro', uri=True) as db:
            assert not db.execute("select id from jobs where status not in ('succeeded','failed','canceled')").fetchall()
            assert not db.execute("select id from blender_web_sessions where state in ('queued','preparing','starting','ready','saving','stopping')").fetchall()
            assert not db.execute("select id from blender_runtime_operations where state not in ('ready','failed','canceled')").fetchall()
        paths = [data / 'runtime-state/blender-runtimes.json',
                 feature / 'runtimes/blender' / runtime_id / 'install/blender']
        paths += [p for p in (data / 'assets').iterdir() if p.is_file()]
        assert len(paths) > 2
        assert all(not p.is_symlink() and p.resolve().is_relative_to(root) for p in paths)
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

    hashes = await asyncio.to_thread(baseline)
    await asyncio.to_thread(evidence_dir.mkdir, mode=0o700, parents=True, exist_ok=False)
    app = await asyncio.to_thread(create_app, Settings(data_dir=data,
        blender_legacy_runtime_root=root / 'absent-legacy',
        blender_managed_runtime_root=feature / 'runtimes/blender',
        blender_web_runtime_root=feature / 'runtimes/blender-web'))
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level='warning'))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    events: list[dict[str, Any]] = []
    started = time.monotonic()
    sid = None

    async def record(stage: str, **values: Any) -> None:
        row = {'stage': stage, 'elapsed_sec': round(time.monotonic() - started, 3), **values}
        events.append(row)
        await asyncio.to_thread((evidence_dir / 'observations.json').write_text, json.dumps(events, indent=2) + '\n')
        print(json.dumps(row), flush=True)

    try:
        async with asyncio.timeout(15):
            while not server.started:
                assert not serving.done()
                await asyncio.sleep(0.05)
        async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{listener.getsockname()[1]}', timeout=30) as client:
            async def get(path: str) -> Any:
                response = await client.get(path)
                response.raise_for_status()
                return response.json()

            async def post(path: str, value: dict[str, Any]) -> Any:
                response = await client.post(path, json=value)
                response.raise_for_status()
                return response.json()

            sessions = '/workspace-api/blender/sessions'
            operations = '/workspace-api/blender/runtime/operations'

            async def wait_session(state: str) -> dict[str, Any]:
                async with asyncio.timeout(90):
                    while True:
                        value = next(v for v in (await get(sessions))['items'] if v['id'] == sid)
                        if value['state'] == state:
                            return value
                        assert value['state'] not in {'failed', 'interrupted', 'stopped'}, value
                        await asyncio.sleep(0.2)

            before = await get('/workspace-api/scenes/' + scene_id)
            created = await post(sessions, {'action': 'start', 'scene_id': scene_id})
            sid = created['id']
            try:
                ready = await wait_session('ready')
                assert ready['runtime_id'] == runtime_id
                await record('real_blender_ready', session=ready, hashes=hashes)
                operation = await post(operations, {'action': 'repair', 'runtime_id': runtime_id})
                async with asyncio.timeout(300):
                    while True:
                        result = next(v for v in (await get('/workspace-api/blender/runtime'))['operations'] if v['id'] == operation['id'])
                        if result['state'] in {'ready', 'failed', 'canceled'}:
                            break
                        await asyncio.sleep(0.5)
                assert result['state'] == 'failed' and result['error_code'] == 'blender_runtime_in_use', result
                assert (await wait_session('ready'))['id'] == sid
                assert await get('/workspace-api/scenes/' + scene_id) == before

                def verify_hashes() -> None:
                    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in hashes.items())

                await asyncio.to_thread(verify_hashes)
                health = await get('/health')
                await record('repair_rejected_old_usable', operation=result, health=health, files_preserved=len(hashes))
            finally:
                await post(sessions, {'action': 'stop', 'session_id': sid})
                stopped = await wait_session('stopped')
                await record('stopped', session=stopped)
            assert await get('/workspace-api/scenes/' + scene_id) == before
            # The same repair must work after the owned session is stopped.
            destination = feature / 'runtimes/blender' / runtime_id
            inode_before = (await asyncio.to_thread(destination.stat)).st_ino
            repair = await post(operations, {'action': 'repair', 'runtime_id': runtime_id})
            async with asyncio.timeout(300):
                while True:
                    result = next(v for v in (await get('/workspace-api/blender/runtime'))['operations'] if v['id'] == repair['id'])
                    if result['state'] in {'ready', 'failed', 'canceled'}:
                        break
                    await asyncio.sleep(0.5)
            assert result['state'] == 'ready', result
            inode_after = (await asyncio.to_thread(destination.stat)).st_ino
            assert inode_before != inode_after
            await asyncio.to_thread(verify_hashes)
            assert await get('/workspace-api/scenes/' + scene_id) == before
            await record('stopped_runtime_repaired', operation=result,
                inode_before=inode_before, inode_after=inode_after, files_preserved=len(hashes))
            await record('passed')
    finally:
        server.should_exit = True
        await serving
        listener.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence-dir', type=Path, required=True)
    asyncio.run(run(parser.parse_args().evidence_dir))
