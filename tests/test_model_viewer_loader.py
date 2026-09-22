"""Exercise the actual browser loader with controlled DOM/network boundaries."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_viewer_module_uses_scoped_header_and_releases_blob_on_success_and_failure() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for the browser loader behavior probe")
    script = (Path(__file__).parents[1] / "frontend/app.js").read_text()
    loader = script[script.index("let modelViewerModulePromise = null;"):script.index("const VIEWER_3D_TEXT =")]
    harness = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const loader = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
function setup({embedded=true, nonce='fixture-session', responses=[200], scriptFail=false}={}) {
  const calls=[], urls=[], revoked=[], scripts=[];
  const window={};window.parent=embedded?{}:window;
  const context={window,state:{nonce},workspaceFrameRoot:()=>embedded?'/addon-frame/media-forge':'',
    fetch:async(url,options)=>{calls.push({url,options});const status=responses.shift()??200;
      if(status==='network')throw Error('private network details');
      return {ok:[200,'html','large'].includes(status),status,blob:async()=>({type:status==='html'?'text/html':'text/javascript',size:status==='large'?3*1024*1024:100})};},
    URL:{createObjectURL:(blob)=>{urls.push(blob);return 'blob:fixture';},revokeObjectURL:(url)=>revoked.push(url)},
    document:{createElement:()=>({remove(){this.removed=true;}}),head:{append:(script)=>{scripts.push(script);queueMicrotask(()=>scriptFail?script.onerror():script.onload());}}},
    __mediaForgeCreateModelViewer:()=>{},
  };
  vm.createContext(context);vm.runInContext(loader,context);
  return {context,calls,urls,revoked,scripts,load:()=>context.loadModelViewer()};
}
(async()=>{
  const missing=setup({nonce:''});await assert.rejects(missing.load(),e=>e.code==='model_viewer_module_auth');assert.equal(missing.calls.length,0);
  for(const status of [401,403]) {
    const f=setup({responses:[status,200]});await assert.rejects(f.load(),e=>e.code==='model_viewer_module_auth');
    const first=f.load();assert.equal(first,f.load());await first;
    assert.equal(f.calls.length,2);assert.equal(f.scripts.length,1);assert.equal(f.scripts[0].src,'blob:fixture');
    assert.equal(f.scripts[0].removed,true);assert.deepEqual(f.revoked,['blob:fixture']);
    const call=f.calls[1];assert.equal(call.options.headers['X-Control-Deck-Bridge-Session'],'fixture-session');
    assert.equal(call.options.credentials,'omit');assert.equal(call.options.redirect,'error');assert(!call.url.includes('fixture-session'));
  }
  const badScript=setup({scriptFail:true});await assert.rejects(badScript.load(),e=>e.code==='model_viewer_module_load');assert.deepEqual(badScript.revoked,['blob:fixture']);assert.equal(badScript.scripts[0].removed,true);
  const network=setup({responses:['network',200]});await assert.rejects(network.load(),e=>e.code==='model_viewer_module_load'&&!e.message);await network.load();
  for(const value of ['html','large']){const invalid=setup({responses:[value]});await assert.rejects(invalid.load(),e=>e.code==='model_viewer_module_load');assert.equal(invalid.urls.length,0);}
  const standalone=setup({embedded:false});await standalone.load();assert.equal(standalone.calls.length,0);assert(standalone.scripts[0].src.startsWith('/static/three-viewer.js?'));assert.equal(standalone.revoked.length,0);
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    import json
    subprocess.run([node, "-e", harness], input=json.dumps(loader), text=True, check=True, timeout=10)
