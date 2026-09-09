"""Trusted Blender timer contract, with no bpy dependency in the core environment."""
from __future__ import annotations

import importlib.util
import asyncio
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest


def bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, list[dict]]:
    scene = tmp_path / 'scene.blend'
    scene.write_bytes(b'BLENDER-original')
    control = tmp_path / 'control'
    control.mkdir()
    calls: list[dict] = []

    def save(**kwargs: Any) -> set[str]:
        calls.append(kwargs)
        Path(kwargs['filepath']).write_bytes(b'BLENDER-edited')
        return {'FINISHED'}

    bpy = SimpleNamespace(ops=SimpleNamespace(wm=SimpleNamespace(
        open_mainfile=lambda **kw: None, save_as_mainfile=save)),
        app=SimpleNamespace(version=(4, 5, 13), background=False,
            timers=SimpleNamespace(register=lambda *a, **kw: None)),
        context=SimpleNamespace(preferences=SimpleNamespace(filepaths=SimpleNamespace(
            use_scripts_auto_execute=False, use_auto_save_temporary_files=True))))
    monkeypatch.setitem(sys.modules, 'bpy', bpy)
    monkeypatch.setitem(sys.modules, 'gpu', SimpleNamespace(platform=SimpleNamespace(
        backend_type_get=lambda: 'VULKAN', renderer_get=lambda: 'llvmpipe')))
    monkeypatch.setattr(sys, 'argv', ['blender', '--', '--scene', str(scene), '--control', str(control),
        '--session-id', 'blendersession_' + 'a' * 32])
    script = Path(__file__).resolve().parents[1] / 'worker_packs/blender/gui_session_bootstrap.py'
    spec = importlib.util.spec_from_file_location('gui_bootstrap', script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, calls


def test_autosave_interval_and_atomic_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module, calls = bootstrap(tmp_path, monkeypatch)
    start = module.LAST_AUTOSAVE
    module._autosave(start + 119)
    assert not calls
    module._autosave(start + 120)
    assert len(calls) == 1 and calls[0]['copy'] is True and calls[0]['relative_remap'] is False
    assert module.SCENE.read_bytes() == b'BLENDER-edited'
    assert json.loads((module.CONTROL / 'autosave.json').read_text())['ok'] is True
    assert not list(tmp_path.glob('.autosave-*'))
    assert module.bpy.context.preferences.filepaths.use_auto_save_temporary_files is False
    module._autosave(start + 121)
    assert len(calls) == 1


def test_manager_exposes_and_clears_autosave_warning(tmp_path: Path) -> None:
    from test_blender_session_manager import OWNER, session_fixture, wait_state
    _, _, scene_id, _, manager = session_fixture(tmp_path, monitor_interval_sec=0.01)

    async def scenario() -> None:
        await manager.start()
        try:
            created = await manager.create(OWNER, scene_id)
            await wait_state(manager, created['id'], 'ready')
            status = manager._session_root(created['id']) / 'autosave.json'
            for ok, wanted in [(False, 'blender_session_autosave_failed'), (True, None)]:
                status.write_text(json.dumps({'schema_version': 1, 'session_id': created['id'], 'ok': ok}))
                for _ in range(100):
                    result = manager.get(OWNER, created['id'])
                    if result['error_code'] == wanted:
                        break
                    await asyncio.sleep(0.01)
                assert result['state'] == 'ready' and result['error_code'] == wanted
            manager.discard_and_stop(OWNER, created['id'])
            await wait_state(manager, created['id'], 'stopped')
        finally:
            await manager.stop()

    asyncio.run(scenario())


def test_autosave_status_read_does_not_block_event_loop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from test_blender_session_manager import OWNER, session_fixture, wait_state
    _, _, scene_id, _, manager = session_fixture(tmp_path, monitor_interval_sec=0.01)
    entered, release = threading.Event(), threading.Event()

    def slow_read(_sid: str) -> None:
        entered.set()
        release.wait(2)

    monkeypatch.setattr(manager, '_autosave_failed', slow_read)

    async def scenario() -> None:
        await manager.start()
        try:
            began = time.monotonic()
            created = await manager.create(OWNER, scene_id)
            await wait_state(manager, created['id'], 'ready')
            assert await asyncio.to_thread(entered.wait, 1)
            await asyncio.sleep(0.01)
            assert time.monotonic() - began < 1
            assert not release.is_set()
            release.set()
            manager.discard_and_stop(OWNER, created['id'])
            await wait_state(manager, created['id'], 'stopped')
        finally:
            release.set()
            await manager.stop()

    asyncio.run(scenario())


def test_autosave_status_rejects_symlink_and_wrong_identity(tmp_path: Path) -> None:
    from test_blender_session_manager import session_fixture
    _, _, _, _, manager = session_fixture(tmp_path)
    sid = 'blendersession_' + 'b' * 32
    root = manager._session_root(sid)
    root.mkdir(parents=True)
    status = root / 'autosave.json'
    assert manager._autosave_failed(sid) is None
    status.write_text(json.dumps({'schema_version':1,'session_id':'wrong','ok':True}))
    assert manager._autosave_failed(sid) is True
    status.unlink()
    status.symlink_to(tmp_path / 'absent')
    assert manager._autosave_failed(sid) is True


def test_missing_or_stale_autosave_status_is_not_success(tmp_path: Path) -> None:
    from test_blender_session_manager import session_fixture
    _, _, _, _, manager = session_fixture(tmp_path)
    sid = 'blendersession_' + 'c' * 32
    root = manager._session_root(sid)
    root.mkdir(parents=True)
    ready = root / 'ready.json'
    ready.write_text('{}')
    os.utime(ready, (1, 1))
    assert manager._autosave_failed(sid) is True
    status = root / 'autosave.json'
    status.write_text(json.dumps({'schema_version':1,'session_id':sid,'ok':True}))
    assert manager._autosave_failed(sid) is False
    os.utime(status, (1, 1))
    assert manager._autosave_failed(sid) is True


def test_status_disk_failure_does_not_unregister_timer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module, _ = bootstrap(tmp_path, monkeypatch)
    start = module.LAST_AUTOSAVE

    def fail_report(*_a: Any, **_kw: Any) -> None:
        raise OSError('fixture disk full')

    monkeypatch.setattr(module, '_atomic_json', fail_report)
    monkeypatch.setattr(module.time, 'monotonic', lambda: start + 120)
    assert module._control_tick() == module.CONTROL_INTERVAL_SEC
    assert module.SCENE.read_bytes() == b'BLENDER-edited'


@pytest.mark.parametrize('failure', ['write', 'cancel', 'header', 'replace'])
def test_autosave_failure_retains_last_snapshot_and_retries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    module, calls = bootstrap(tmp_path, monkeypatch)
    original_save = module.bpy.ops.wm.save_as_mainfile
    original_replace = module.os.replace

    def bad_save(**kw: Any) -> set[str]:
        Path(kw['filepath']).write_bytes(b'partial')
        if failure == 'write':
            raise OSError('fixture disk full')
        return {'CANCELLED'} if failure == 'cancel' else {'FINISHED'}

    def bad_replace(source: Path, destination: Path) -> None:
        if destination == module.SCENE:
            raise OSError('fixture replace failure')
        original_replace(source, destination)

    if failure == 'replace':
        monkeypatch.setattr(module.os, 'replace', bad_replace)
    else:
        monkeypatch.setattr(module.bpy.ops.wm, 'save_as_mainfile', bad_save)
    start = module.LAST_AUTOSAVE
    module._autosave(start + 120)
    assert module.SCENE.read_bytes() == b'BLENDER-original'
    assert json.loads((module.CONTROL / 'autosave.json').read_text())['ok'] is False
    assert not list(tmp_path.glob('.autosave-*'))
    monkeypatch.setattr(module.os, 'replace', original_replace)
    monkeypatch.setattr(module.bpy.ops.wm, 'save_as_mainfile', original_save)
    module._autosave(start + 240)
    assert module.SCENE.read_bytes() == b'BLENDER-edited'
    assert json.loads((module.CONTROL / 'autosave.json').read_text())['ok'] is True
