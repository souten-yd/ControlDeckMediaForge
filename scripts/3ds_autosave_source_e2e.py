"""Real isolated source GUI: default autosave, owned Blender crash, recovery fork.

Serve with MediaForge Python; browser with diagnostic Playwright Python.
Uses a new data directory and existing read-only runtime/Web pack. No Host restart.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import sqlite3
import subprocess
import time
from typing import Any


def serve(args: argparse.Namespace) -> None:
    import uvicorn
    from mediaforge.app import create_app
    from mediaforge.config import Settings

    args.data_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    app = create_app(Settings(data_dir=args.data_dir, blender_legacy_runtime_root=args.runtime_root,
        blender_web_runtime_root=args.web_root))
    app.state.store.initialize()
    workspace = app.state.scene_workspace
    workspace.initialize()
    assert workspace.resolver.register_legacy()
    content = args.blend.read_bytes()
    upload = workspace.begin_upload('local', size=len(content), sha256=hashlib.sha256(content).hexdigest(), name='Autosave acceptance')
    for offset in range(0, len(content), 512 * 1024):
        chunk = content[offset:offset + 512 * 1024]
        workspace.append_upload('local', upload['upload_id'], offset, chunk, hashlib.sha256(chunk).hexdigest())
    scene = asyncio.run(workspace.commit_upload('local', upload['upload_id']))
    (args.data_dir / 'fixture.json').write_text(json.dumps({'scene_id': scene['scene']['id'],
        'blender': str(workspace.resolver.resolve_g8().executable)}) + '\n')
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')


def browser(args: argparse.Namespace) -> None:
    from playwright.sync_api import sync_playwright

    fixture = json.loads((args.data_dir / 'fixture.json').read_text())
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    evidence: dict[str, Any] = {'mode': 'source_real_gui_default_autosave_crash', 'events': [], 'page_errors': []}
    began = time.monotonic()

    def log(stage: str, **values: Any) -> None:
        event = {'stage': stage, 'elapsed_sec': round(time.monotonic() - began, 3), **values}
        evidence['events'].append(event)
        (args.evidence_dir / 'observations.json').write_text(json.dumps(evidence, indent=2) + '\n')
        print(json.dumps(event), flush=True)

    def record(sid: str) -> dict:
        with sqlite3.connect(f'file:{args.data_dir}/media-forge.sqlite3?mode=ro', uri=True) as db:
            return json.loads(db.execute('select value_json from blender_web_sessions where id=?', (sid,)).fetchone()[0])

    with sync_playwright() as pw:
        chrome = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=False,
            args=['--window-size=1280,1000'])
        sid = None
        protected_directory = None
        directory_mode = None
        try:
            page = chrome.new_page(no_viewport=True, locale='en')
            page.on('pageerror', lambda e: evidence['page_errors'].append(type(e).__name__))
            page.goto(args.url)
            page.locator('#app[aria-busy="false"]').wait_for()

            def call(method: str, params: dict) -> dict:
                return page.evaluate('p => call(p.method,p.params)', {'method':method,'params':params})

            def wait(states: set[str], seconds: float = 90) -> dict:
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    s = next(s for s in call('blender.sessions.list', {})['items'] if s['id'] == sid)
                    if s['state'] in states:
                        return s
                    assert s['state'] in {'queued','preparing','starting','ready','saving','stopping'}, s
                    page.wait_for_timeout(250)
                raise AssertionError('owned session did not reach requested state')

            scene_id = fixture['scene_id']
            before = call('scenes.get', {'scene_id':scene_id})
            evidence['before'] = before
            page.locator('#create-media-3d').click()
            page.evaluate('id => openScene(id)', scene_id)
            sid = call('blender.sessions.start', {'scene_id':scene_id})['id']
            log('started', session_id=sid)
            ready = wait({'ready'})
            page.evaluate("() => refreshSession(['blender_sessions','scenes'])")
            owned = record(sid)
            root = args.data_dir / 'sessions/blender' / sid
            candidate = args.data_dir / 'scenes/working' / owned['working_id'] / 'scene.blend'
            initial_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
            page.evaluate('s => openBlenderView(s)', ready)
            page.wait_for_function("state.blenderRfb?._rfbConnectionState === 'connected'", timeout=30000)
            page.wait_for_timeout(5000)
            page.locator('#scene-blender-screen canvas').click(position={'x':320,'y':240})
            page.keyboard.press('a')
            page.wait_for_timeout(500)
            page.keyboard.press('Shift+D')
            page.wait_for_timeout(500)
            page.keyboard.press('Escape')
            page.wait_for_timeout(1000)
            assert hashlib.sha256(candidate.read_bytes()).hexdigest() == initial_hash
            log('edited_not_saved')

            if args.verify_input_activity:
                # Real RFB display requests, not a substituted activity clock.
                # Requests may split/coalesce in the actual noVNC WebSocket.
                last_input = record(sid)['last_activity_at']
                for _ in range(24):
                    page.evaluate("""() => {
                        const sock=state.blenderRfb._sock;
                        sock.sQpushBytes(new Uint8Array([3,1,0,0,0,0,0,64,0,64]));
                        sock.flush();
                    }""")
                    page.wait_for_timeout(500)
                assert record(sid)['last_activity_at'] == last_input
                page.locator('#scene-blender-screen canvas').click(position={'x':320,'y':240})
                page.wait_for_timeout(1000)
                assert record(sid)['last_activity_at'] != last_input
                last_input = record(sid)['last_activity_at']
                page.locator('#scene-blender-close').click()
                page.wait_for_function("""async sid => {
                    const s=(await call('blender.sessions.list',{})).items.find(s=>s.id===sid);
                    return s?.connection_state==='disconnected';
                }""", arg=sid)
                page.evaluate('s => openBlenderView(s)', wait({'ready'}))
                page.wait_for_function("state.blenderRfb?._rfbConnectionState === 'connected'", timeout=30000)
                page.wait_for_timeout(2000)
                assert record(sid)['last_activity_at'] == last_input
                evidence['input_activity'] = {'display_requests':24, 'display_does_not_touch':True,
                                              'pointer_does_touch':True, 'reconnect_preserves_input_time':True}
                log('input_activity_verified')

            def await_autosave(wanted: bool) -> None:
                deadline = time.monotonic() + 150
                while True:
                    if (root / 'autosave.json').exists():
                        value = json.loads((root / 'autosave.json').read_text())
                        if value.get('ok') is wanted:
                            return
                    assert time.monotonic() < deadline
                    log('waiting_autosave', wanted_ok=wanted)
                    page.wait_for_timeout(15000)

            if args.fail_first_autosave:
                protected_directory = candidate.parent.resolve(strict=True)
                assert protected_directory.is_relative_to((args.data_dir / 'scenes/working').resolve(strict=True))
                directory_mode = stat.S_IMODE(protected_directory.stat().st_mode)
                protected_directory.chmod(0o500)
                await_autosave(False)
                assert hashlib.sha256(candidate.read_bytes()).hexdigest() == initial_hash
                page.evaluate("() => refreshSession(['blender_sessions'])")
                warning = page.locator('#scene-blender-autosave-warning')
                warning.wait_for(state='visible')
                evidence['warning_text'] = warning.inner_text()
                assert any(text in evidence['warning_text'] for text in (
                    'Automatic recovery save failed', '自動復旧用の保存に失敗しました'))
                page.screenshot(path=str(args.evidence_dir / 'autosave-failed.png'))
                log('save_failure_visible_previous_bytes_retained')
                protected_directory.chmod(directory_mode)
            await_autosave(True)
            status = json.loads((root / 'autosave.json').read_text())
            assert status['ok'] is True and status['session_id'] == sid
            assert hashlib.sha256(candidate.read_bytes()).hexdigest() != initial_hash
            assert call('scenes.get', {'scene_id':scene_id}) == before
            page.evaluate("() => refreshSession(['blender_sessions'])")
            page.locator('#scene-blender-autosave-warning').wait_for(state='hidden')
            page.screenshot(path=str(args.evidence_dir / 'autosaved.png'))
            digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
            log('autosaved', sha256=digest, size_bytes=candidate.stat().st_size)
            unit = owned['unit_id']
            assert unit == 'mediaforge-blender-' + sid.removeprefix('blendersession_') + '.service'
            group = subprocess.run(['systemctl','--user','show',unit,'--property=ControlGroup','--value'],
                check=True,capture_output=True,text=True,timeout=10).stdout.strip()
            cgroup = Path('/sys/fs/cgroup') / group.lstrip('/')
            assert group and cgroup.is_dir()
            pids = sorted({int(p) for f in cgroup.rglob('cgroup.procs') for p in f.read_text().split()})
            executable = Path(fixture['blender']).resolve(strict=True)
            targets = [p for p in pids if Path(f'/proc/{p}/exe').resolve() == executable]
            assert len(targets) == 1
            pid = targets[0]
            fd = os.pidfd_open(pid)
            try:
                assert Path(f'/proc/{pid}/exe').resolve(strict=True) == executable
                assert pid in {int(p) for f in cgroup.rglob('cgroup.procs') for p in f.read_text().split()}
                signal.pidfd_send_signal(fd, signal.SIGKILL)
            finally:
                os.close(fd)
            terminal = wait({'failed','interrupted'})
            assert terminal['error_code'] == 'blender_session_runner_lost'
            assert not cgroup.exists() and not root.exists() and all(not Path(f'/proc/{p}').exists() for p in pids)
            assert hashlib.sha256(candidate.read_bytes()).hexdigest() == digest
            recovered = call('scenes.recovery.fork', {'scene_id':scene_id,
                'recovery_working_id':terminal['result']['recovery']['working_id']})
            facts = next(v['facts'] for v in recovered['revision']['validation'] if v['validator']=='blender.scene')
            original = next(r for r in before['revisions'] if r['id']==before['scene']['current_revision_id'])
            original_facts = next(v['facts'] for v in original['validation'] if v['validator']=='blender.scene')
            assert facts['meshes'] == 2 * original_facts['meshes']
            source = args.data_dir / 'assets' / (recovered['revision']['source_asset_id'] + '.blend')
            assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
            assert call('scenes.get', {'scene_id':scene_id}) == before
            assert not evidence['page_errors']
            evidence.update(passed=True, recovered=recovered, terminal=terminal, autosave=status,
                pids=pids, signaled_pid=pid, candidate_sha256=digest)
            log('passed', recovered_meshes=facts['meshes'])
        except Exception as error:
            evidence['connection'] = page.evaluate("({dialog:document.querySelector('#scene-blender-dialog')?.open, state:state.blenderRfb?._rfbConnectionState, label:document.querySelector('#scene-blender-connection')?.textContent})")
            page.screenshot(path=str(args.evidence_dir / 'failed.png'))
            log('failed', error_type=type(error).__name__)
            raise
        finally:
            try:
                if protected_directory is not None and directory_mode is not None:
                    protected_directory.chmod(directory_mode)
                if sid and record(sid)['state'] in {'queued','preparing','starting','ready','saving','stopping'}:
                    call('blender.sessions.stop', {'session_id':sid})
                    wait({'stopped','failed','interrupted'})
            finally:
                chrome.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path)
    parser.add_argument('--web-root', type=Path)
    parser.add_argument('--blend', type=Path)
    parser.add_argument('--port', type=int, default=8797)
    parser.add_argument('--url', default='http://127.0.0.1:8797')
    parser.add_argument('--evidence-dir', type=Path)
    parser.add_argument('--fail-first-autosave', action='store_true')
    parser.add_argument('--verify-input-activity', action='store_true')
    args = parser.parse_args()
    serve(args) if args.serve else browser(args)
