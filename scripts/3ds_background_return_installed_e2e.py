"""Installed, headful background-tab return and real Blender edit/save.

Host diagnostic Python only. Advances only an explicitly named retained mf-e2e
scene. No simulated visibility, product overlays, password changes or restarts.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import time
from typing import Any, Iterator


DATA = Path('/data1tb/ControlDeck/data/feature-data/media-forge/data')
ACTIVE = {'queued', 'preparing', 'starting', 'ready', 'saving', 'stopping'}


@contextmanager
def native_browser(playwright: Any) -> Iterator[Any]:
    """Do not let automation force every page to stay focused/visible."""
    with tempfile.TemporaryDirectory(prefix='mf-background-browser-') as folder:
        process = subprocess.Popen(['/usr/bin/google-chrome', '--user-data-dir=' + folder,
            '--remote-debugging-port=0', '--no-first-run', '--no-default-browser-check',
            '--window-size=1280,1000', '--lang=en-US', 'about:blank'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            endpoint = Path(folder) / 'DevToolsActivePort'
            deadline = time.monotonic() + 15
            while not endpoint.exists():
                assert process.poll() is None and time.monotonic() < deadline
                time.sleep(0.1)
            port = int(endpoint.read_text().splitlines()[0])
            browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{port}', no_defaults=True)
            try:
                yield browser
            finally:
                browser.close()
        finally:
            # Only this owned browser child, never an existing user browser.
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=15)


def mesh_count(value: dict[str, Any]) -> int:
    revision = next(r for r in value['revisions'] if r['id'] == value['scene']['current_revision_id'])
    return next(v['facts']['meshes'] for v in revision['validation'] if v['validator'] == 'blender.scene')


def asset_hashes(value: dict[str, Any]) -> dict[str, str]:
    """Hash the actual source/preview assets for every immutable old revision."""
    result: dict[str, str] = {}
    root = (DATA / 'assets').resolve(strict=True)
    with sqlite3.connect(f'file:{DATA}/media-forge.sqlite3?mode=ro', uri=True) as db:
        for revision in value['revisions']:
            for key in ('source_asset_id', 'preview_asset_id'):
                aid = revision.get(key)
                if not aid:
                    continue
                row = db.execute('select storage_name from assets where id=?', (aid,)).fetchone()
                assert row is not None
                path = (root / row[0]).resolve(strict=True)
                assert path.is_relative_to(root)
                result[aid] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def main() -> None:
    from playwright.sync_api import sync_playwright
    from app.database import SessionLocal
    from app.features import registry
    from app.models import User
    from app.security.sessions import SESSION_COOKIE, create_session, revoke_session

    parser = argparse.ArgumentParser()
    parser.add_argument('--scene-id', required=True)
    parser.add_argument('--expected-version', required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'scene_[0-9a-f]{32}', args.scene_id)
    installed = registry.status('media-forge')
    assert installed['version'] == args.expected_version and installed['health'] == 'healthy'
    with sqlite3.connect(f'file:{DATA}/media-forge.sqlite3?mode=ro', uri=True) as db:
        assert not any(s in ACTIVE for (s,) in db.execute('select state from blender_web_sessions'))
    args.evidence_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    spec = importlib.util.spec_from_file_location('helpers', Path(__file__).with_name('3ds8_installed_browser_e2e.py'))
    assert spec and spec.loader
    helpers = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helpers)
    evidence: dict[str, Any] = {'mode': 'installed_real_background_tab_return',
        'version': args.expected_version, 'scene_id': args.scene_id, 'events': [], 'page_errors': []}
    began = time.monotonic()

    def record(stage: str, **values: Any) -> None:
        event = {'stage': stage, 'elapsed_sec': round(time.monotonic() - began, 3), **values}
        evidence['events'].append(event)
        (args.evidence_dir / 'observations.json').write_text(json.dumps(evidence, indent=2) + '\n')
        print(json.dumps(event), flush=True)

    with SessionLocal() as db:
        user = db.query(User).filter(User.username == 'mf-e2e').one()
        assert user.is_active
        token = create_session(db, user, '127.0.0.1', 'MediaForge background return acceptance')
    try:
        with sync_playwright() as pw, native_browser(pw) as browser:
            frame = None
            session_id = None
            try:
                context = browser.contexts[0]
                context.add_cookies([{'name': SESSION_COOKIE, 'value': token,
                    'url': 'http://127.0.0.1:8765', 'httpOnly': True, 'sameSite': 'Lax'}])
                page = context.new_page()
                page.on('pageerror', lambda error: evidence['page_errors'].append(type(error).__name__))
                page.goto('http://127.0.0.1:8765/x/media-forge/workspace/create', wait_until='domcontentloaded')
                frame = helpers.workspace_frame(page)
                frame.wait_for_selector('#app[aria-busy="false"]')
                assert frame.evaluate('self.origin') == 'null'
                before = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
                assert before['scene']['name'].startswith('mf-e2e material conflict ')
                assert mesh_count(before) > 0
                evidence['before'] = before
                evidence['old_asset_hashes'] = asset_hashes(before)
                frame.locator('#create-media-3d').click()
                # Product selection helper avoids depending on collapsed list layout.
                frame.evaluate('id => openScene(id)', args.scene_id)
                assert helpers.session_projection(frame, args.scene_id) is None
                created = frame.evaluate("id => call('blender.sessions.start', {scene_id:id})", args.scene_id)
                session_id = created['id']
                record('created', session_id=session_id)
                ready = helpers.wait_session(frame, args.scene_id, {'ready'}, timeout=90)
                assert ready['id'] == session_id
                frame.evaluate('s => openBlenderView(s)', ready)
                frame.wait_for_function("state.blenderRfb?._rfbConnectionState === 'connected'", timeout=30000)
                # Observe actual framebuffer diversity; never substitute connection UI for a frame.
                pixels = """() => {
                    const c = document.querySelector('#scene-blender-screen canvas');
                    if (!c || c.width < 100 || c.height < 100) return 0;
                    const data = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
                    const colors = new Set();
                    for (let i=0; i<data.length; i+=160) colors.add(`${data[i]},${data[i+1]},${data[i+2]}`);
                    return colors.size;
                }"""
                frame.wait_for_function('(' + pixels + ')() > 50', timeout=45000)
                evidence['initial_frame_colors'] = frame.evaluate(pixels)
                page.screenshot(path=str(args.evidence_dir / 'before-background.png'))
                frame.evaluate("""() => {
                    window.__backgroundEvidence = [{state:document.visibilityState, at:performance.now()}];
                    document.addEventListener('visibilitychange', () =>
                        window.__backgroundEvidence.push({state:document.visibilityState, at:performance.now()}));
                }""")
                other = context.new_page()
                other.goto('about:blank')
                other.bring_to_front()
                frame.wait_for_function("document.visibilityState === 'hidden'", polling=100, timeout=10000)
                record('hidden')
                other.wait_for_timeout(15000)
                page.bring_to_front()
                frame.wait_for_function("document.visibilityState === 'visible' && state.blenderRfb?._rfbConnectionState === 'connected'", timeout=30000)
                current = helpers.session_projection(frame, args.scene_id)
                assert current and current['id'] == session_id and current['state'] == 'ready'
                evidence['visibility'] = frame.evaluate('window.__backgroundEvidence')
                assert [v['state'] for v in evidence['visibility']] == ['visible', 'hidden', 'visible']
                evidence['returned_frame_colors'] = frame.evaluate(pixels)
                assert evidence['returned_frame_colors'] > 50
                record('returned', same_session=True)
                frame.locator('#scene-blender-screen canvas').click(position={'x': 320, 'y': 240})
                page.keyboard.press('a')
                page.wait_for_timeout(500)
                page.keyboard.press('Shift+D')
                page.wait_for_timeout(500)
                page.keyboard.press('Escape')
                page.wait_for_timeout(1000)
                page.screenshot(path=str(args.evidence_dir / 'returned-edited.png'))
                frame.locator('#scene-blender-save').click()
                frame.wait_for_function('n => state.sceneRevisions.length === n', arg=len(before['revisions']) + 1, timeout=90000)
                after = frame.evaluate("id => call('scenes.get', {scene_id:id})", args.scene_id)
                evidence['after'] = after
                assert all(r in after['revisions'] for r in before['revisions'])
                assert asset_hashes(before) == evidence['old_asset_hashes']
                assert mesh_count(after) == 2 * mesh_count(before), 'GUI edit did not double mesh count'
                assert helpers.session_projection(frame, args.scene_id) is None
                assert not evidence['page_errors']
                evidence['passed'] = True
                record('passed', meshes_before=mesh_count(before), meshes_after=mesh_count(after))
            except Exception as error:
                record('failed', error_type=type(error).__name__)
                raise
            finally:
                try:
                    if frame is not None and session_id is not None:
                        current = helpers.session_projection(frame, args.scene_id)
                        if current and current['id'] == session_id:
                            frame.evaluate("id => call('blender.sessions.stop', {session_id:id})", session_id)
                            deadline = time.monotonic() + 45
                            while helpers.session_projection(frame, args.scene_id) is not None:
                                if time.monotonic() >= deadline:
                                    raise RuntimeError('Owned session cleanup did not finish')
                                page.wait_for_timeout(250)
                        record('cleanup', owned_session_terminal=True)
                finally:
                    browser.close()
    finally:
        with SessionLocal() as db:
            revoke_session(db, token)
        record('login_revoked')


if __name__ == '__main__':
    main()
