#!/usr/bin/env node

import fs from "node:fs";
import process from "node:process";
import {chromium} from "playwright-core";

function required(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) throw new Error(`${name} is required`);
  return process.argv[index + 1];
}

function optional(name, fallback) {
  const index = process.argv.indexOf(name);
  return index < 0 || !process.argv[index + 1] ? fallback : process.argv[index + 1];
}

function check(value, message) {
  if (!value) throw new Error(message);
}

const baseUrl = required("--base-url").replace(/\/$/, "");
const assetId = required("--asset-id");
const screenshot = required("--screenshot");
const expectPlaceholder = optional("--expect-placeholder", "yes") === "yes";
const expectedTriangles = Number(optional("--triangles", "12"));
const expectedAnimations = Number(optional("--animations", "0"));
const compareAssetId = optional("--compare-asset-id", "");
const imageAssetId = optional("--image-asset-id", "");
const observations = {};
const errors = [];
const moduleRequests = [];
const browser = await chromium.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: false,
  args: ["--enable-webgl", "--ignore-gpu-blocklist"],
});

try {
  const page = await browser.newPage({viewport: {width: 1280, height: 900}});
  await page.addInitScript(() => {
    const requestFrame = window.requestAnimationFrame.bind(window);
    window.__animationFrames = 0;
    window.requestAnimationFrame = (callback) => requestFrame((time) => {
      window.__animationFrames += 1;
      callback(time);
    });
  });
  const session = await page.context().newCDPSession(page);
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  page.on("pageerror", (error) => errors.push(String(error)));
  page.on("request", (request) => {
    if (request.url().includes("/viewer-runtime.js")) moduleRequests.push(request.url());
  });
  await page.goto(`${baseUrl}/library`, {waitUntil: "domcontentloaded"});
  await page.waitForSelector('#app[aria-busy="false"]');
  if (!(await page.locator("#view-library").isVisible())) await page.locator("#nav-library").click();
  const cardSelector = `#library-grid [data-asset-id="${assetId}"]`;
  await page.waitForSelector(cardSelector);
  check(moduleRequests.length === 0, "3D runtime was fetched before a model was opened");
  const card = page.locator(cardSelector);
  if (expectPlaceholder) {
    check(await card.locator(".model-placeholder").isVisible(), "new GLB has no lightweight placeholder");
  }
  if (imageAssetId) {
    const imageCardSelector = `#library-grid [data-asset-id="${imageAssetId}"]`;
    await page.locator('[data-library-media="image"]').click();
    await page.waitForSelector(imageCardSelector);
    const imageKinds = await page.locator("#library-grid .card").evaluateAll(
      (cards) => cards.map((item) => item.dataset.mediaKind),
    );
    check(imageKinds.length > 0 && imageKinds.every((kind) => kind === "image"),
      "image filter included another media type");
    await page.locator(imageCardSelector).click();
    await page.waitForFunction(() => document.querySelector("#viewer-image")?.naturalWidth === 640);
    observations.image_dimensions = await page.locator("#viewer-image").evaluate(
      (image) => [image.naturalWidth, image.naturalHeight],
    );
    await page.locator("#viewer-close").click();
    await page.waitForFunction(() => !document.querySelector("#viewer").open);
    check(moduleRequests.length === 0, "image viewing fetched the 3D runtime");
  }
  await page.locator('[data-library-media="3d"]').click();
  await page.waitForSelector(cardSelector);
  const filteredKinds = await page.locator("#library-grid .card").evaluateAll(
    (cards) => cards.map((card) => card.dataset.mediaKind),
  );
  check(filteredKinds.length > 0 && filteredKinds.every((kind) => kind === "3d"),
    "3D filter did not isolate 3D assets");

  const started = performance.now();
  await page.locator(cardSelector).click();
  await page.waitForFunction(
    (id) => document.querySelector("#viewer-3d-canvas")?.dataset.modelAssetId === id,
    assetId,
  );
  observations.cold_ms = Math.round((performance.now() - started) * 1000) / 1000;
  observations.webgl = await page.locator("#viewer-3d-canvas").evaluate((canvas) => {
    const context = canvas.getContext("webgl2") || canvas.getContext("webgl");
    const debug = context?.getExtension("WEBGL_debug_renderer_info");
    return {
      version: context?.getParameter(context.VERSION) || "unavailable",
      vendor: debug ? context.getParameter(debug.UNMASKED_VENDOR_WEBGL) : "not_exposed",
      renderer: debug ? context.getParameter(debug.UNMASKED_RENDERER_WEBGL) : "not_exposed",
    };
  });
  observations.stats_ja = await page.locator("#viewer-3d-stats").innerText();
  check(observations.stats_ja.includes(`${expectedTriangles.toLocaleString()} 三角形`),
    "triangle count was not rendered");
  check(observations.stats_ja.includes(`アニメ ${expectedAnimations}`),
    "animation count was not rendered");
  check(moduleRequests.length === 1, "3D runtime was not fetched exactly once");
  check(await page.locator("#viewer-3d-shading").innerText() === "材質", "Japanese controls missing");

  await page.locator("#viewer-3d-shading").click();
  await page.locator("#viewer-3d-shading").click();
  check(await page.locator("#viewer-3d-shading").innerText() === "ワイヤー", "wireframe is unreachable");
  await page.locator("#viewer-3d-bounds").click();
  check(await page.locator("#viewer-3d-bounds").getAttribute("aria-pressed") === "true", "bounds toggle failed");
  await page.locator("#viewer-3d-light").click();
  await page.locator("#viewer-3d-background").click();
  if (expectedAnimations > 0) {
    check(await page.locator("#viewer-3d-animation").isVisible(), "animation control is hidden");
    await page.locator("#viewer-3d-animation").click();
    check(await page.locator("#viewer-3d-animation").innerText() === "停止", "animation did not start");
    await page.waitForTimeout(100);
    observations.animation_frames_active = await page.evaluate(() => window.__animationFrames);
    check(observations.animation_frames_active > 1, "animation did not schedule frames");
    await page.evaluate(() => {
      window.__testVisibility = "hidden";
      Object.defineProperty(document, "visibilityState", {
        configurable: true, get: () => window.__testVisibility,
      });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await page.waitForTimeout(100);
    observations.animation_frames_hidden = await page.evaluate(() => window.__animationFrames);
    check(observations.animation_frames_hidden - observations.animation_frames_active <= 1,
      "hidden model continued its animation loop");
    await page.evaluate(() => {
      window.__testVisibility = "visible";
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await page.waitForTimeout(100);
    observations.animation_frames_resumed = await page.evaluate(() => window.__animationFrames);
    check(observations.animation_frames_resumed > observations.animation_frames_hidden + 1,
      "visible model did not resume animation");
    await page.locator("#viewer-3d-animation").click();
    check(await page.locator("#viewer-3d-animation").innerText() === "再生", "animation did not pause");
  } else {
    check(await page.locator("#viewer-3d-animation").isHidden(), "animation control appeared without a clip");
  }

  observations.context_recovery = await page.evaluate(() => {
    const canvas = document.querySelector("#viewer-3d-canvas");
    const context = canvas.getContext("webgl2") || canvas.getContext("webgl");
    window.__viewerLossExtension = context?.getExtension("WEBGL_lose_context");
    window.__viewerLossExtension?.loseContext();
    return Boolean(window.__viewerLossExtension);
  });
  check(observations.context_recovery, "WEBGL_lose_context is unavailable");
  await page.waitForFunction(() => !document.querySelector("#viewer-3d-loading").hidden);
  await page.evaluate(() => window.__viewerLossExtension.restoreContext());
  await page.waitForFunction(() => document.querySelector("#viewer-3d-loading").hidden);

  if (compareAssetId) {
    await page.evaluate(() => { window.__comparisonCanvases = []; });
    const forward = await page.locator("#viewer-next").isEnabled();
    const away = forward ? "#viewer-next" : "#viewer-prev";
    const back = forward ? "#viewer-prev" : "#viewer-next";
    await page.evaluate(() => window.__comparisonCanvases.push(document.querySelector("#viewer-3d-canvas")));
    await page.locator(away).click();
    await page.waitForFunction(
      (id) => document.querySelector("#viewer-3d-canvas")?.dataset.modelAssetId === id,
      compareAssetId,
    );
    observations.compared_asset_id = compareAssetId;
    await page.evaluate(() => window.__comparisonCanvases.push(document.querySelector("#viewer-3d-canvas")));
    await page.locator(back).click();
    await page.waitForFunction(
      (id) => document.querySelector("#viewer-3d-canvas")?.dataset.modelAssetId === id,
      assetId,
    );
    check(moduleRequests.length === 1, "comparison fetched a second runtime module");
  }

  const box = await page.locator("#viewer-3d-canvas").boundingBox();
  check(box && box.width > 100 && box.height > 100, "model canvas has no usable area");
  await page.mouse.move(box.x + box.width * 0.4, box.y + box.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * 0.65, box.y + box.height * 0.4, {steps: 8});
  await page.mouse.up();

  await page.evaluate(() => {
    document.documentElement.lang = "en";
    window.renderViewer3dText();
    window.renderLibraryMediaFilter();
  });
  observations.stats_en = await page.locator("#viewer-3d-stats").innerText();
  check(observations.stats_en.includes(`${expectedTriangles.toLocaleString()} triangles`),
    "English stats did not update without reload");
  check(await page.locator("#viewer-3d-fit").innerText() === "Fit", "English controls missing");
  check(await page.locator("#viewer-3d-canvas").getAttribute("aria-label") === "3D model",
    "English viewer accessibility text did not update");

  await page.setViewportSize({width: 320, height: 640});
  observations.mobile = await page.evaluate(() => ({
    viewport: window.innerWidth,
    client: document.scrollingElement.clientWidth,
    scroll: document.scrollingElement.scrollWidth,
    minimumButton: Math.min(...[...document.querySelectorAll("#viewer-3d-tools button")]
      .filter((button) => !button.hidden).map((button) => button.getBoundingClientRect().height)),
  }));
  check(observations.mobile.viewport === 320
    && observations.mobile.scroll === observations.mobile.client, "viewer overflows at 320px");
  check(observations.mobile.minimumButton >= 40, "3D controls are too small on mobile");
  await page.screenshot({path: screenshot});

  await page.evaluate(() => {
    window.__releasedCanvases = [
      ...(window.__comparisonCanvases || []), document.querySelector("#viewer-3d-canvas"),
    ];
  });
  await page.locator("#viewer-close").click();
  await page.waitForFunction(() => !document.querySelector("#viewer").open);
  await page.waitForFunction(
    (selector) => document.querySelector(selector)?.querySelector("img")?.naturalWidth > 0,
    cardSelector,
  );
  check(await page.locator(`${cardSelector} .model-placeholder`).isHidden(),
    "rendered thumbnail did not replace the placeholder");

  await session.send("HeapProfiler.collectGarbage");
  const first = await session.send("Runtime.getHeapUsage");
  const warmTimes = [];
  for (let index = 0; index < 4; index += 1) {
    const warmStarted = performance.now();
    await page.locator(cardSelector).click();
    await page.waitForFunction(
      (id) => document.querySelector("#viewer-3d-canvas")?.dataset.modelAssetId === id,
      assetId,
    );
    warmTimes.push(Math.round((performance.now() - warmStarted) * 1000) / 1000);
    await page.evaluate(() => window.__releasedCanvases.push(document.querySelector("#viewer-3d-canvas")));
    await page.locator("#viewer-close").click();
    await page.waitForFunction(() => !document.querySelector("#viewer").open);
  }
  await session.send("HeapProfiler.collectGarbage");
  const final = await session.send("Runtime.getHeapUsage");
  observations.warm_ms = warmTimes;
  observations.heap_after_first_close = first.usedSize;
  observations.heap_after_five_closes = final.usedSize;
  observations.heap_growth = final.usedSize - first.usedSize;
  await page.waitForFunction(() => window.__releasedCanvases.every((canvas) => {
    const context = canvas.getContext("webgl2") || canvas.getContext("webgl");
    return !context || context.isContextLost();
  }));
  observations.released_contexts = await page.evaluate(() => window.__releasedCanvases.map((canvas) => {
    const context = canvas.getContext("webgl2") || canvas.getContext("webgl");
    return !context || context.isContextLost();
  }));
  check(observations.released_contexts.every(Boolean), "a released WebGL context is still live");
  check(observations.heap_growth < 10 * 1024 * 1024, "repeated model close retained excessive JS heap");
  check(moduleRequests.length === 1, "immutable viewer module was fetched again");
  observations.module_requests = moduleRequests.length;
  observations.errors = errors;
  check(errors.length === 0, `browser errors: ${errors.join(" | ")}`);
  fs.writeFileSync(`${screenshot}.json`, `${JSON.stringify(observations, null, 2)}\n`);
  console.log(JSON.stringify(observations));
} catch (error) {
  console.error(JSON.stringify({errors, observations, failure: String(error)}));
  throw error;
} finally {
  await browser.close();
}
