#!/usr/bin/env node
// 一覧の GLB サムネイルを、実機の workspace で実際に作らせて確かめる。
// 撮影は本物の WebGL で行われ、保存も本物の host 経路を通る。固定値は無い。

import fs from "node:fs";
import process from "node:process";
import {chromium} from "playwright-core";

function required(name) {
  const index = process.argv.indexOf(name);
  if (index < 0 || !process.argv[index + 1]) throw new Error(`${name} is required`);
  return process.argv[index + 1];
}

function check(value, message) {
  if (!value) throw new Error(message);
}

const baseUrl = required("--base-url").replace(/\/$/, "");
const screenshot = required("--screenshot");
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
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  page.on("pageerror", (error) => errors.push(String(error)));
  page.on("request", (request) => {
    if (request.url().includes("/static/three-viewer.js")) moduleRequests.push(request.url());
  });
  await page.goto(`${baseUrl}/library`, {waitUntil: "domcontentloaded"});
  await page.waitForSelector('#app[aria-busy="false"]');
  if (!(await page.locator("#view-library").isVisible())) await page.locator("#nav-library").click();
  await page.locator('[data-library-media="glb"]').click();
  await page.waitForSelector("#library-grid .card");

  // 1. 押されるまで 3D ランタイムを取りに行かない。一覧を開く費用は変えない。
  const row = page.locator("#library-thumbnails");
  check(await row.isVisible(), "the backfill row is hidden while GLB cards have no picture");
  observations.hint_before = await page.locator("#library-thumbnails-hint").innerText();
  check(/絵の無い 3D が \d+ 件あります。/.test(observations.hint_before),
    `the pending count was not stated: ${observations.hint_before}`);
  check(moduleRequests.length === 0, "3D runtime was fetched before the button was pressed");

  // 2. 絵の無いカードは札を出している。
  const before = await page.locator("#library-grid .card").evaluateAll((cards) => cards.map((card) => ({
    asset_id: card.dataset.assetId,
    placeholder: !card.querySelector(".model-placeholder").hidden,
    image: card.querySelector("img").hidden ? "" : card.querySelector("img").src.slice(0, 24),
  })));
  const missing = before.filter((card) => card.placeholder);
  check(missing.length > 0, "no GLB card was waiting for a picture");
  observations.cards = before.length;
  observations.placeholders_before = missing.length;

  // 3. 押すと、本物の WebGL で描いて撮り、host へ保存して、その場で絵に変わる。
  await page.locator("#library-thumbnails-run").click();
  await page.waitForFunction((id) => {
    const card = [...document.querySelectorAll("#library-grid .card")]
      .find((node) => node.dataset.assetId === id);
    const image = card?.querySelector("img");
    return Boolean(image && !image.hidden && image.src.startsWith("data:image/webp;base64,"));
  }, missing[0].asset_id, {timeout: 180_000});
  check(moduleRequests.length === 1, "3D runtime was not fetched exactly once");
  observations.first_captured = missing[0].asset_id;

  // 4. 走り終わるまで待ち、作った件数を言う。
  await page.waitForFunction(
    () => document.querySelector("#library-thumbnails-run").hidden
      || !document.querySelector("#library-thumbnails-run").disabled,
    undefined, {timeout: 900_000},
  );
  observations.hint_after = await page.locator("#library-thumbnails-hint").innerText();
  const after = await page.locator("#library-grid .card").evaluateAll((cards) => cards.map((card) => ({
    asset_id: card.dataset.assetId,
    placeholder: !card.querySelector(".model-placeholder").hidden,
    webp: card.querySelector("img").src.startsWith("data:image/webp;base64,"),
  })));
  observations.placeholders_after = after.filter((card) => card.placeholder).length;
  observations.captured = after.filter((card) => card.webp).length;
  check(observations.captured > 0, "no picture was captured");
  check(observations.placeholders_after < observations.placeholders_before,
    "the number of cards without a picture did not fall");

  // 5. 撮った絵は host に残る。読み直しても札に戻らない。
  await page.reload({waitUntil: "domcontentloaded"});
  await page.waitForSelector('#app[aria-busy="false"]');
  if (!(await page.locator("#view-library").isVisible())) await page.locator("#nav-library").click();
  await page.locator('[data-library-media="glb"]').click();
  await page.waitForSelector("#library-grid .card");
  const reloaded = await page.locator("#library-grid .card").evaluateAll((cards) => cards.map((card) => ({
    asset_id: card.dataset.assetId,
    placeholder: !card.querySelector(".model-placeholder").hidden,
  })));
  observations.placeholders_reloaded = reloaded.filter((card) => card.placeholder).length;
  check(observations.placeholders_reloaded === observations.placeholders_after,
    "captured pictures did not survive a reload");
  const survivor = reloaded.find((card) => card.asset_id === observations.first_captured);
  check(survivor && !survivor.placeholder, "the first captured card went back to a placeholder");

  await page.screenshot({path: screenshot, fullPage: false});
  observations.console_errors = errors;
  check(errors.length === 0, `console errors: ${errors.join(" | ")}`);
  fs.writeFileSync(`${screenshot}.json`, `${JSON.stringify(observations, null, 2)}\n`);
  console.log(JSON.stringify(observations, null, 2));
} finally {
  await browser.close();
}
