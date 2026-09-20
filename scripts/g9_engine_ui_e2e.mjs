#!/usr/bin/env node
// Real Chrome and the unmodified workspace inside an opaque iframe. All
// capability/job responses below are UI fixtures, never real Host/GPU evidence.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {createServer} from 'node:http';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright-core';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const outputArg = process.argv.indexOf('--evidence-dir');
assert(outputArg > 0 && process.argv[outputArg + 1], '--evidence-dir is required');
const output = resolve(process.argv[outputArg + 1]);
await mkdir(output, {recursive: false, mode: 0o700});
const source = {};
for (const name of ['frontend/index.html', 'frontend/styles.css', 'frontend/app.js']) {
  source[name] = await readFile(resolve(root, name), 'utf8');
}
const html = source['frontend/index.html']
  .replace('<!-- MEDIA_FORGE_INLINE_STYLE -->', `<style>${source['frontend/styles.css']}</style>`)
  .replace('<!-- MEDIA_FORGE_INLINE_SCRIPT -->', `<script>${source['frontend/app.js']}</script>`);
const parent = `<!doctype html><meta charset="utf-8"><style>
html,body{margin:0;height:100%;background:#101818}iframe{display:block;border:0;width:100%;height:100%}
</style><iframe title="Source UI fixture" sandbox="allow-scripts allow-forms allow-downloads" src="/x/media-forge/workspace"></iframe>
<script>
window.addEventListener('message',event=>{
 const frame=document.querySelector('iframe');
 if(event.source!==frame.contentWindow || event.data?.type!=='control-deck-addon.connect')return;
 const channel=new MessageChannel();window.fixturePort=channel.port1;
 channel.port1.onmessage=({data})=>{if(data.id)channel.port1.postMessage({type:'response',id:data.id,ok:true,result:{}})};
 frame.contentWindow.postMessage({type:'control-deck-host.connected',session_nonce:'source-ui-fixture',theme:{
  locale:new URLSearchParams(location.search).get('locale')||'ja',color_scheme:'dark',
  bg:'#101818',surface:'#192424',text:'#e5efef',border:'#354343',muted:'#afc0c0',accent:'#63dac3'
 }},'*',[channel.port2]);
});
</script>`;
const server = createServer((request, response) => {
  const path = new URL(request.url, 'http://fixture').pathname;
  if (path === '/' || path === '/x/media-forge/workspace') {
    response.writeHead(200, {'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store'});
    response.end(path === '/' ? parent : html);
  } else if (path === '/favicon.ico') {
    response.writeHead(204); response.end();
  } else {
    response.writeHead(404); response.end();
  }
});
await new Promise((ready) => server.listen(0, '127.0.0.1', ready));
const base = `http://127.0.0.1:${server.address().port}`;
const imageId = `asset_${'1'.repeat(32)}`;
// 実機は trellis.cpp を 1024（既定）と 512 の 2 つで採用し、Pixal3D は 1024。
// 既定は先頭。解像度ごとに測った時間を持つ。
const baseCapability = () => ({state: 'experimental', implementation: 'trellis_cpp',
  resolutions: [1024, 512], estimated_runtime_sec: 520,
  estimated_runtime_by_resolution: {'1024': 520, '512': 104},
  engines: {trellis_cpp: {state: 'experimental', resolutions: [1024, 512], estimated_runtime_sec: 520,
      estimated_runtime_by_resolution: {'1024': 520, '512': 104}},
    pixal3d: {state: 'experimental', resolutions: [1024], estimated_runtime_sec: 1200,
      estimated_runtime_by_resolution: {'1024': 1200}}},
  refine: {state: 'experimental', resolutions: [1024], estimated_runtime_sec: 1200}});
// 実機は trellis.cpp を 512、Pixal3D を 1024 で採用している。段ごとに違う。
const report = {mode: 'source_browser_opaque_iframe_with_transport_fixtures', passed: false,
  real_host: false, gpu_executed: false, weights_used: false, installed_assets_registered: 0,
  source_sha256: Object.fromEntries(Object.entries(source).map(([name, text]) =>
    [name, createHash('sha256').update(text).digest('hex')])), cases: [], page_errors: [],
  not_tested: ['installed Host', 'real adoption/GPU generation', '3D output quality', 'GLB viewer']};
let browser;
try {
  browser = await chromium.launch({executablePath: '/usr/bin/google-chrome', headless: true,
    args: ['--disable-gpu', '--disable-software-rasterizer'], timeout: 15000});
  report.browser = browser.version();
  async function open(width, locale, capability = baseCapability()) {
    const context = await browser.newContext({viewport: {width, height: 900}, locale});
    const page = await context.newPage();
    page.setDefaultTimeout(10000);
    page.on('pageerror', (error) => report.page_errors.push(String(error)));
    const fixture = {capability, requests: [], traffic: [], jobs: new Map(), job: null, failGet: false};
    await page.routeWebSocket('**/x/media-forge/ws', (socket) => {
      socket.onMessage((data) => {
        const request = JSON.parse(String(data));
        fixture.traffic.push({method: request.method, job_id: request.params?.job_id});
        let result = {};
        if (request.method === 'workspace.session') result = {
          preferences: {values: {last_view: 'web-blender'}},
          capabilities: {capabilities: {'3d.image_to_3d': fixture.capability}},
          blender_runtime: {state: 'ready'}, scenes: {items: [], working_copies: []},
          library: {items: []}, profiles: {items: []}, reference_collections: {items: []},
        };
        else if (request.method === 'creative.templates') result = {
          domains: [], scenes: [], poses: [], compositions: [], cameras: [], variations: [],
        };
        else if (request.method === 'assets.import.begin') {
          fixture.upload = {media_type: request.params.media_type, size: request.params.size, received: 0};
          result = {upload_id: 'upload_fixture', chunk_bytes: 512 * 1024};
        } else if (request.method === 'assets.import.chunk') {
          fixture.upload.received += Buffer.from(request.params.base64, 'base64').length;
          result = {received: fixture.upload.received};
        } else if (request.method === 'assets.import.commit') {
          fixture.imported = {id: `asset_${'2'.repeat(32)}`, mime_type: 'image/png',
            suggested_filename: 'media-forge-import-22222222.png'};
          result = fixture.imported;
        }
        else if (request.method === 'assets.thumbnail') result = {mime_type: 'image/png', base64:
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='};
        else if (request.method === 'assets.list') result = {items: [
          {id: imageId, mime_type: 'image/png', suggested_filename: 'UI fixture.png'},
          ...(fixture.imported ? [fixture.imported] : []),
        ]};
        else if (request.method === 'scenes.from_image') {
          fixture.requests.push(request.params);
          fixture.job = {job_id: `job_${String(fixture.requests.length).padStart(32, '0')}`, status: 'running',
            phase: request.params.engine === 'pixal3d' ? 'prepare_3d_input' : 'generate_3d', progress: .15};
          fixture.jobs.set(fixture.job.job_id, fixture.job);
          result = fixture.job;
        } else if (request.method === 'scenes.jobs.get') {
          if (fixture.holdNextGet) {
            fixture.holdNextGet = false;
            const held = structuredClone(fixture.jobs.get(request.params.job_id));
            fixture.releaseGet = () => socket.send(JSON.stringify({id: request.id, ok: true, result: held}));
            return;
          }
          if (fixture.failGet) {
            fixture.failGet = false;
            socket.send(JSON.stringify({id: request.id, ok: false, error: {code: 'fixture_connection_failure'}}));
            return;
          }
          result = fixture.jobs.get(request.params.job_id);
          if (fixture.mismatchGet) {
            fixture.mismatchGet = false;
            result = {...result, job_id: 'job_'+'9'.repeat(32)};
          }
        } else if (request.method === 'scenes.jobs.cancel') {
          assert.equal(request.params.job_id, fixture.job.job_id);
          fixture.job = {...fixture.job, status: 'canceled', phase: 'canceled'};
          fixture.jobs.set(fixture.job.job_id, fixture.job);
          result = fixture.job;
        } else if (request.method.endsWith('.list')) result = {items: []};
        socket.send(JSON.stringify({id: request.id, ok: true, result}));
      });
    });
    await page.goto(`${base}/?locale=${locale}`);
    const frame = page.frames().find((item) => item.url().includes('/x/media-forge/workspace'));
    assert(frame);
    await frame.locator('#app[aria-busy="false"]').waitFor();
    assert.equal(await page.locator('iframe').getAttribute('sandbox'), 'allow-scripts allow-forms allow-downloads');
    await frame.waitForFunction(() => state.sceneGenerationImages.length === 1 || document.querySelector('#scene-generation-form').hidden);
    return {context, page, frame, fixture};
  }
  const options = (frame, name) => frame.locator(`#scene-generation-${name} option`).evaluateAll(
    (items) => items.map((item) => ({value: item.value, disabled: item.disabled, label: item.textContent})));
  const status = (frame, text) => frame.waitForFunction((value) =>
    document.querySelector('#scene-generation-status').textContent.includes(value), text);
  const refresh = (frame) => frame.evaluate(() => refreshSession(['capabilities']));
  const screenshot = async (page, frame, name) => {
    await frame.evaluate(async () => {
      await document.fonts.ready;
      await new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done)));
    });
    await page.screenshot({path: resolve(output, name), animations: 'disabled'});
  };
  for (const [width, locale] of [[320, 'ja'], [1280, 'en']]) {
    const {context, page, frame, fixture} = await open(width, locale);
    try {
      const by = (name) => frame.locator(`#scene-generation-${name}`);
      await by('options').click();
      assert.equal(await by('engine').inputValue(), 'trellis_cpp');
      // 採用の先頭が既定。解像度ごとに測った目安が選択肢に出る。
      assert.equal(await by('resolution').inputValue(), '1024');
      assert.deepEqual((await options(frame, 'resolution')).map((item) => item.label),
        locale === 'ja' ? ['1024 · 9分', '512 · 2分'] : ['1024 · 9 min', '512 · 2 min']);
      await by('engine').selectOption('pixal3d');
      assert.deepEqual((await options(frame, 'resolution')).map((item) => item.value), ['1024']);
      await by('image').selectOption(imageId);
      await by('name').fill('Pixal source UI fixture');
      await by('seed').fill('16777217');
      const alternate = locale === 'ja' ? 'en' : 'ja';
      await page.evaluate((value) => window.fixturePort.postMessage({type: 'event', event: 'locale.changed', data: {locale: value}}), alternate);
      await frame.waitForFunction((value) => document.documentElement.lang === value, alternate);
      assert.equal(await by('engine').inputValue(), 'pixal3d');
      assert.equal(await by('seed').inputValue(), '16777217');
      await page.evaluate((value) => window.fixturePort.postMessage({type: 'event', event: 'locale.changed', data: {locale: value}}), locale);
      await frame.waitForFunction((value) => document.documentElement.lang === value, locale);
      const layout = await frame.evaluate(() => ({width: innerWidth, scroll: document.documentElement.scrollWidth,
        controls: ['engine', 'resolution', 'name', 'seed', 'submit'].map((name) => ({name,
          height: document.getElementById('scene-generation-'+name).getBoundingClientRect().height}))}));
      assert(layout.scroll <= layout.width);
      assert(layout.controls.every((item) => item.height >= 44), JSON.stringify(layout));
      await by('submit').click();
      await status(frame, locale === 'ja' ? '入力画像を準備' : 'Preparing the input image');
      assert.deepEqual(fixture.requests[0], {name: 'Pixal source UI fixture', input_asset_id: imageId,
        engine: 'pixal3d', refine_with_pixal3d: false, resolution: 1024, seed: 16777217, local_only: true});
      for (const name of ['engine', 'resolution', 'image', 'name', 'seed']) assert(await by(name).isDisabled());
      await screenshot(page, frame, `${width}-${locale}-preparing.png`);
      fixture.job.phase = 'waiting_resource';
      await status(frame, locale === 'ja' ? 'GPUの空き' : 'Waiting for GPU');
      fixture.job.phase = 'generate_3d';
      await status(frame, locale === 'ja' ? '3Dを生成しています' : 'Generating 3D');
      fixture.job.phase = 'validate_generated_scene';
      await status(frame, locale === 'ja' ? '検証して保存' : 'Validating and saving');
      fixture.failGet = true;
      await status(frame, locale === 'ja' ? '生成状況を取得できません' : 'Could not refresh');
      assert.equal(await by('engine').inputValue(), 'pixal3d');
      await by('refresh').click();
      await status(frame, locale === 'ja' ? '検証して保存' : 'Validating and saving');
      fixture.mismatchGet = true;
      await status(frame, locale === 'ja' ? '生成状況を取得できません' : 'Could not refresh');
      assert.equal(await frame.evaluate(() => state.sceneGeneration.job_id), fixture.job.job_id);
      await by('refresh').click();
      await status(frame, locale === 'ja' ? '検証して保存' : 'Validating and saving');
      fixture.job.phase = 'prepare_3d_input';
      await status(frame, locale === 'ja' ? '入力画像を準備' : 'Preparing the input image');
      fixture.holdNextGet = true;
      const deadline = Date.now() + 10000;
      while (!fixture.releaseGet && Date.now() < deadline) await new Promise((done) => setTimeout(done, 20));
      assert(fixture.releaseGet, 'old job read was not held');
      await by('cancel').click();
      await status(frame, locale === 'ja' ? '生成を中止' : 'Generation canceled');
      assert.equal(await by('engine').inputValue(), 'pixal3d');
      assert(!(await by('submit').isDisabled()));
      await by('engine').selectOption('trellis_cpp');
      assert.equal(await by('resolution').inputValue(), '1024');
      await by('resolution').selectOption('512');
      await by('submit').click();
      await status(frame, locale === 'ja' ? '3Dを生成しています' : 'Generating 3D');
      assert.equal(fixture.requests[1].engine, 'trellis_cpp');
      assert.equal(fixture.requests[1].resolution, 512);
      assert.equal(fixture.requests[1].refine_with_pixal3d, false);
      fixture.releaseGet();
      fixture.job.status = 'failed';
      await status(frame, locale === 'ja' ? '生成できません' : 'Generation failed');
      assert.equal(await frame.evaluate(() => state.sceneGeneration.job_id), fixture.job.job_id);
      fixture.capability = {state: 'unavailable', reason: 'three_d_runtime_unavailable', engines: {
        pixal3d: {state: 'experimental', resolutions: [1024]}}};
      await refresh(frame);
      assert.equal(await by('engine').inputValue(), 'trellis_cpp');
      assert((await options(frame, 'engine')).find((item) => item.value === 'trellis_cpp').disabled);
      assert(await by('submit').isDisabled());
      await by('options').click();
      await status(frame, locale === 'ja' ? '生成エンジンは現在利用できません' : 'generation engine is unavailable');
      await frame.evaluate(() => submitSceneGeneration());
      assert.equal(fixture.requests.length, 2);
      await screenshot(page, frame, `${width}-${locale}-unavailable.png`);
      await by('options').click();
      fixture.capability = baseCapability();
      // 採用から 512 が消えたら、選んでいた 512 は理由付きで無効にして送らせない。
      fixture.capability.engines.trellis_cpp.resolutions = [1024];
      fixture.capability.engines.trellis_cpp.estimated_runtime_by_resolution = {'1024': 520};
      await refresh(frame);
      assert.equal(await by('resolution').inputValue(), '512');
      assert((await options(frame, 'resolution')).find((item) => item.value === '512').disabled);
      assert(await by('submit').isDisabled());
      await by('resolution').selectOption('1024');
      assert(!(await by('submit').isDisabled()));
      fixture.capability.engines.pixal3d = {state: 'unavailable', reason: 'three_d_runtime_unavailable'};
      fixture.capability.engines.unknown_engine = {state: 'experimental', resolutions: [512]};
      await refresh(frame);
      const finalChoices = await options(frame, 'engine');
      assert(finalChoices.find((item) => item.value === 'pixal3d').disabled);
      assert(!finalChoices.some((item) => item.value === 'unknown_engine'));
      // 「標準は trellis.cpp まで、チェックで Pixal3D まで」を実画面で確かめる。
      fixture.capability = baseCapability();
      await refresh(frame);
      await by('engine').selectOption('trellis_cpp');
      await by('resolution').selectOption('512');
      const refine = frame.locator('#scene-generation-refine');
      assert(!(await refine.isChecked()), 'Pixal3D must be off by default');
      assert(!(await refine.isDisabled()), 'adopted Pixal3D must be selectable');
      await frame.waitForFunction((value) =>
        document.querySelector('#scene-generation-refine-hint').textContent.includes(value),
        locale === 'ja' ? 'Pixal3Dまで実行すると合計で約22分かかり、1024で走って'
                        : 'takes about 22 min in total, runs at 1024');
      const photo = frame.locator('#scene-generation-photo');
      assert.equal(await photo.count(), 1, 'a device photo picker must exist');
      assert((await photo.getAttribute('accept')).includes('image/*'), 'the picker must accept device photos');
      assert((await photo.getAttribute('accept')).toLowerCase().includes('heic'), 'iPhone photos are HEIC');
      const touchHeight = await frame.evaluate(() => [
        document.getElementById('scene-generation-refine').closest('label').getBoundingClientRect().height,
        document.getElementById('scene-generation-photo').getBoundingClientRect().height,
      ]);
      assert(touchHeight.every((value) => value >= 44), JSON.stringify(touchHeight));
      // 端末の写真をその場で入力にする。Chromium は HEIC を復号しないので、ここで
      // 測れるのは「PNG/JPEG 以外が選択を通り、原本が core へ届いて選ばれる」まで。
      await by('name').fill('');
      await photo.setInputFiles({name: 'IMG_0001.HEIC', mimeType: 'image/heic',
        buffer: Buffer.from('not a decodable HEIC for this browser')});
      await frame.waitForFunction(() => !state.sceneGenerationPhotoBusy && state.sceneGenerationPhotoMessage.length > 0);
      const photoMessage = await frame.evaluate(() => state.sceneGenerationPhotoMessage);
      assert.equal(await by('image').inputValue(), `asset_${'2'.repeat(32)}`, photoMessage);
      assert.equal(fixture.upload.media_type, 'image/heic', 'the original photo must reach core');
      // 空のときだけ名前を埋める。利用者が書いた名前は写真で上書きしない。
      assert.equal(await by('name').inputValue(), 'IMG_0001');
      await by('name').fill('Kept by the user');
      await photo.setInputFiles({name: 'IMG_0002.HEIC', mimeType: 'image/heic',
        buffer: Buffer.from('a second device photo')});
      await frame.waitForFunction(() => !state.sceneGenerationPhotoBusy
        && state.sceneGenerationPhotoMessage.includes('IMG_0002') === false);
      assert.equal(await by('name').inputValue(), 'Kept by the user');
      await frame.waitForFunction(() => !document.getElementById('scene-generation-preview').hidden);
      await by('image').selectOption(imageId);
      await refine.check();
      await by('name').fill('Refined source UI fixture');
      await by('submit').click();
      await status(frame, locale === 'ja' ? '3Dを生成しています' : 'Generating 3D');
      const refined = fixture.requests[fixture.requests.length - 1];
      assert.equal(refined.refine_with_pixal3d, true);
      assert.equal(refined.engine, 'trellis_cpp');
      fixture.job.phase = 'generate_3d_refine';
      await status(frame, locale === 'ja' ? 'Pixal3Dで仕上げ' : 'Finishing with Pixal3D');
      fixture.job.status = 'succeeded';
      fixture.job.result = {refine: {state: 'succeeded', engine: 'pixal3d'},
        scene: {id: `scene_${'3'.repeat(32)}`}};
      await status(frame, locale === 'ja' ? 'Pixal3Dの版' : 'Pixal3D revision');
      // 「一覧から開けます」で終わらせず、その場から開ける。
      await frame.locator('#scene-generation-open').waitFor({state: 'visible'});
      assert(!(await frame.locator('#scene-generation-open').isDisabled()));
      // 採用されていない段は、既定で出さずに理由を言う。
      fixture.capability = baseCapability();
      fixture.capability.engines.pixal3d = {state: 'unavailable', reason: 'three_d_runtime_unavailable'};
      fixture.capability.refine = fixture.capability.engines.pixal3d;
      await refresh(frame);
      assert(await refine.isDisabled(), 'unavailable Pixal3D must not be selectable');
      assert(!(await refine.isChecked()));
      await frame.waitForFunction((value) =>
        document.querySelector('#scene-generation-refine-hint').textContent.includes(value),
        locale === 'ja' ? 'Pixal3Dが準備できていない' : 'Pixal3D is not ready');
      await screenshot(page, frame, `${width}-${locale}-refine.png`);
      fixture.capability = baseCapability();
      await refresh(frame);
      report.cases.push({width, locale, passed: true, layout, requests: fixture.requests,
        refine_default_off: true, refine_opt_in_sends_flag: true, refine_phase_reported: true,
        refine_unavailable_blocks_and_explains: true, device_photo_picker: true,
        device_photo_reaches_core_undecoded: true, selected_input_preview: true,
        phases: ['prepare_3d_input', 'waiting_resource', 'generate_3d', 'validate_generated_scene'],
        cancellation: true, refresh_after_connection_error: true, mismatched_job_response_rejected: true,
        locale_preserves_input: true,
        new_job_polling_after_cancel: true, stale_old_job_response_ignored: true,
        engine_disappearance_preserved_and_blocked: true, resolution_change_requires_selection: true});
    } catch (error) {
      report.failure_state = await frame.evaluate(() => ({job: state.sceneGeneration,
        polling: state.sceneGenerationPolling, message: document.querySelector('#scene-generation-status').textContent}));
      report.fixture_job = fixture.job;
      report.traffic = fixture.traffic;
      await page.screenshot({path: resolve(output, `${width}-${locale}-failure.png`)});
      throw error;
    } finally { await context.close(); }
  }
  for (const [name, capability, expected] of [
    ['unavailable', {state: 'unavailable', engines: {pixal3d: {state: 'unavailable'}}}, null],
    ['explicit_pixal_when_auto_unavailable', {state: 'unavailable', engines: {
      pixal3d: {state: 'experimental', resolutions: [1024]}}}, 'pixal3d'],
    ['legacy_capability', {state: 'experimental', implementation: 'trellis_cpp', resolutions: [512]}, 'auto'],
    ['unsupported_resolution', {state: 'experimental', resolutions: [1536], engines: {
      pixal3d: {state: 'experimental', resolutions: [1536]}}}, null],
  ]) {
    const {context, frame} = await open(320, 'ja', capability);
    try {
      assert.equal(await frame.locator('#scene-generation-form').isVisible(), expected !== null);
      if (expected) assert.equal(await frame.locator('#scene-generation-engine').inputValue(), expected);
      report.cases.push({name, passed: true, selected_engine: expected});
    } finally { await context.close(); }
  }
  assert.deepEqual(report.page_errors, []);
  report.passed = true;
  console.log(JSON.stringify({passed: true, browser: report.browser, cases: report.cases.length}));
} catch (error) {
  report.failure = String(error.stack || error);
  throw error;
} finally {
  await browser?.close();
  server.closeAllConnections();
  await new Promise((done) => server.close(done));
  await writeFile(resolve(output, 'report.json'), JSON.stringify(report, null, 2)+'\n');
}
