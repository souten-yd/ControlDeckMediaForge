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
              function disconnectBlenderRfb() { setBlenderKeysEnabled(false); state.blenderRfb = null; state.blenderInputAnchor = null; }
            ''' + 'function openBlenderView(session)' + functions +
                'byId("scene-blender-keys").addEventListener' + listener +
                'installBlenderTouchButtons(byId("scene-blender-dialog"));')
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
                assert page.evaluate('''async () => {
                  const canvas = document.createElement('canvas');
                  byId('scene-blender-screen').replaceChildren(canvas);
                  connectBlenderRfb();
                  const rect = canvas.getBoundingClientRect();
                  rememberBlenderInput({target:canvas, clientX:rect.left+rect.width/4,
                    clientY:rect.top+rect.height/3});
                  const order=[];
                  canvas.addEventListener('mousemove', e => order.push(['move',e.clientX,e.clientY]));
                  state.blenderRfb.sendKey=(...args)=>order.push(['key',...args]);
                  await sendBlenderAssistKey('Enter');
                  if(order.length!==2 || order[0][0]!=='move' || order[1][0]!=='key')return false;
                  if(Math.abs(order[0][1]-(rect.left+rect.width/4))>1)return false;
                  order.length=0;
                  const pending=sendBlenderAssistKey('Tab');
                  disconnectBlenderRfb();
                  await pending;
                  return order.length===1 && order[0][0]==='move';
                }''')
                page.evaluate('closeBlenderView()')
                assert not page.locator('#scene-blender-dialog').is_visible()
                results.append({'width': width, 'height': height, 'language': language, 'passed': True})
            # Opaque iframe offset regression, with no Host or Blender involved.
            page.set_content('<meta name="viewport" content="width=device-width, initial-scale=1">'
                             '<body style="margin:0"><div style="height:88px"></div>'
                             '<iframe sandbox="allow-scripts" style="border:0;width:320px;height:490px"></iframe>')
            page.locator('iframe').evaluate('''e => e.srcdoc = `<meta name="viewport" content="width=device-width, initial-scale=1">
              <body style="margin:0"><div style="height:5505px"></div>
              <button id="close" style="position:absolute;top:5650px;left:130px;width:70px;height:44px">Close</button>
              <button id="open" style="position:absolute;top:5726px;left:29px;width:262px;height:46px">Open</button>
              <div style="height:800px"></div><script>window.clicks=[];
              document.addEventListener('click',e=>clicks.push(e.target.id));scrollTo(0,5505)</script>`''')
            frame = page.frames[1]
            frame.wait_for_selector('#open')
            helper = 'function installBlenderTouchButtons' + script.split('function installBlenderTouchButtons', 1)[1].split('function rememberBlenderInput', 1)[0]
            frame.add_script_tag(content=helper + 'installBlenderTouchButtons(document.body);')
            frame.locator('#open').tap()
            page.wait_for_timeout(350)
            assert frame.evaluate('clicks') == ['open']
            assert frame.evaluate('''() => {
              const button=document.getElementById('open'), rect=button.getBoundingClientRect();
              function touch(id, dx=0) { return new Touch({identifier:id,target:button,
                clientX:rect.left+20+dx,clientY:rect.top+20}); }
              function fire(type, touches, changed=touches) {
                const event=new TouchEvent(type,{bubbles:true,cancelable:true,touches,changedTouches:changed});
                button.dispatchEvent(event); return event.defaultPrevented;
              }
              for(const mode of ['drag','cancel','multitouch','disabled','end_outside']) {
                clicks=[]; const first=touch(1);
                fire('touchstart',[first]);
                if(mode==='drag')fire('touchmove',[touch(1,30)]);
                if(mode==='cancel')fire('touchcancel',[],[first]);
                if(mode==='multitouch')fire('touchstart',[first,touch(2)]);
                if(mode==='disabled')button.disabled=true;
                const prevented=fire('touchend',[],[mode==='end_outside'?touch(1,300):first]);
                button.disabled=false;
                if(prevented || clicks.length)return false;
              }
              return true;
            }''')
            print(json.dumps({'passed': True, 'viewports': results, 'opaque_touch_target': 'open_once',
                              'not_tested': ['live RFB/Blender input', 'installed opaque iframe', 'physical mobile']}))
        finally:
            browser.close()


if __name__ == '__main__':
    main()
