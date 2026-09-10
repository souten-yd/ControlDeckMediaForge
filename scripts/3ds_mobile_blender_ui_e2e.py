"""Real Chrome DOM acceptance with an explicit RFB transport fixture.

No live Blender, Host, credentials or production data are used by this check.
Run with an existing environment containing Playwright; no dependency installs.
"""
from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    script = (root / "frontend/app.js").read_text()
    html = (root / "frontend/index.html").read_text()
    dialog = '<dialog id="scene-blender-dialog"' + html.split('<dialog id="scene-blender-dialog"', 1)[1].split('</dialog>', 1)[0] + '</dialog>'
    functions = script.split('function openBlenderView(session)', 1)[1].split('async function finishBlenderSession', 1)[0]
    listener = script.split('byId("scene-blender-keys").addEventListener', 1)[1].split('byId("scene-blender-save").addEventListener', 1)[0]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True)
        try:
            page = browser.new_page(viewport={'width': 320, 'height': 640}, has_touch=True)
            page.set_content(dialog)
            page.add_style_tag(content=(root / 'frontend/styles.css').read_text())
            texts = 'const SCENE_TEXT = ' + script.split('const SCENE_TEXT = ', 1)[1].split('function sceneText()', 1)[0]
            page.add_script_tag(content=texts + '''
              const state = {blenderRfb: null, blenderRfbConnected: false};
              const byId = id => document.getElementById(id);
              const sent = [];
              function connectBlenderRfb() {
                state.blenderRfb = {sendKey: (...args) => sent.push(args)};
                setBlenderKeysEnabled(true);
              }
              function disconnectBlenderRfb() { setBlenderKeysEnabled(false); state.blenderRfb = null; }
            ''' + 'function openBlenderView(session)' + functions +
                'byId("scene-blender-keys").addEventListener' + listener)
            results = []
            for width, height, language in ((320, 640, 'ja'), (320, 640, 'en'),
                                            (640, 320, 'ja'), (640, 320, 'en'),
                                            (1280, 800, 'ja'), (1280, 800, 'en')):
                page.set_viewport_size({'width': width, 'height': height})
                page.evaluate('''language => {
                  document.documentElement.lang = language;
                  const text = SCENE_TEXT[language];
                  for (const [id, key] of Object.entries({
                    'scene-blender-guidance': 'blenderDesktop',
                    'scene-blender-dialog-title': 'blenderDialog',
                    'scene-blender-close': 'blenderClose',
                    'scene-blender-save': 'blenderSave',
                    'scene-blender-discard': 'blenderDiscard'})) byId(id).textContent = text[key];
                }''', language)
                page.evaluate('openBlenderView({id: "fixture"})')
                assert page.locator('#scene-blender-dialog').is_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                bounds = page.locator('#scene-blender-dialog').bounding_box()
                assert bounds and bounds['width'] <= width
                assert page.evaluate('byId("scene-blender-dialog").scrollWidth <= byId("scene-blender-dialog").clientWidth')
                for key in ('Escape', 'Tab', 'Enter', 'ArrowLeft', 'ArrowUp', 'ArrowDown', 'ArrowRight'):
                    page.locator(f'[data-blender-key="{key}"]').tap()
                assert page.evaluate('sent.slice(-7).map(x => x[1])') == [
                    'Escape', 'Tab', 'Enter', 'ArrowLeft', 'ArrowUp', 'ArrowDown', 'ArrowRight']
                count = page.evaluate('sent.length')
                page.evaluate('disconnectBlenderRfb(); sendBlenderAssistKey("Enter")')
                assert page.evaluate('sent.length') == count
                assert page.locator('#scene-blender-keys button:disabled').count() == 7
                page.evaluate('closeBlenderView()')
                assert not page.locator('#scene-blender-dialog').is_visible()
                results.append({'width': width, 'height': height, 'language': language, 'passed': True})
            print(json.dumps({'passed': True, 'viewports': results,
                              'not_tested': ['live RFB/Blender input', 'installed opaque iframe', 'physical mobile']}))
        finally:
            browser.close()


if __name__ == '__main__':
    main()
