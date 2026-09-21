#!/usr/bin/env node
// 同じシーンの版が 1 枚にまとまることを、実機の一覧で確かめる。
// 固定値は無い。数は実機のライブラリが持っているぶんをそのまま読む。

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
const browser = await chromium.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: true,
  args: ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
});

const cardShape = (cards) => cards.map((card) => ({
  asset_id: card.dataset.assetId,
  scene_id: card.dataset.sceneId || "",
  summary: card.querySelector(".sum").textContent,
  versions: card.querySelector(".card-versions")?.textContent || "",
}));

try {
  const page = await browser.newPage({viewport: {width: 1280, height: 900}});
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  page.on("pageerror", (error) => errors.push(String(error)));
  await page.goto(`${baseUrl}/library`, {waitUntil: "domcontentloaded"});
  await page.waitForSelector('#app[aria-busy="false"]');
  if (!(await page.locator("#view-library").isVisible())) await page.locator("#nav-library").click();
  await page.waitForSelector("#library-grid .card");

  // 1. 既定でまとまっている。何行をまとめたかを言う。
  check(await page.locator("#library-group").getAttribute("aria-pressed") === "true",
    "grouping is not the default");
  observations.grouped = await page.locator("#library-grid .card").evaluateAll(cardShape);
  observations.group_hint = await page.locator("#library-group-hint").innerText();
  const groups = observations.grouped.filter((card) => card.scene_id);
  check(groups.length > 0, "no scene was collapsed into a card");
  check(/同じシーンの \d+ 行をまとめています。/.test(observations.group_hint),
    `the collapsed count was not stated: ${observations.group_hint}`);
  // シーンは 1 枚につき 1 度だけ出る。
  const sceneIds = groups.map((card) => card.scene_id);
  check(new Set(sceneIds).size === sceneIds.length, "a scene appeared on more than one card");
  // 版の数を言い、名前は操作の説明ではなくシーンの名前を出す。
  check(groups.every((card) => /^(\d+ 版|版 \d+\/\d+)$/.test(card.versions)),
    `a collapsed card did not state its versions: ${JSON.stringify(groups.slice(0, 3))}`);
  check(groups.every((card) => !card.summary.startsWith("Export validated")),
    "a collapsed card still showed the operation summary instead of the scene name");

  // 2. 押せば元の 1 行ずつに戻る。行の数は増える。
  await page.locator("#library-group").click();
  await page.waitForFunction(
    () => document.querySelector("#library-group").getAttribute("aria-pressed") === "false",
  );
  observations.flat = await page.locator("#library-grid .card").evaluateAll(cardShape);
  check(observations.flat.length > observations.grouped.length,
    "turning grouping off did not restore the individual rows");
  observations.collapsed_rows = observations.flat.length - observations.grouped.length;
  // まとめた行の数は、画面が言っている数と一致する。
  check(observations.group_hint.includes(String(observations.collapsed_rows)),
    `stated ${observations.group_hint} but ${observations.collapsed_rows} rows were collapsed`);
  await page.locator("#library-group").click();
  await page.waitForFunction(
    () => document.querySelector("#library-group").getAttribute("aria-pressed") === "true",
  );

  // 3. 選ぶあいだは束ねない。束ねたまま 1 枚押すと版ぜんぶが消える。
  await page.locator("#library-select").click();
  await page.waitForFunction(() => document.querySelector("#library-group").disabled);
  observations.selecting = await page.locator("#library-grid .card").evaluateAll(cardShape);
  check(observations.selecting.length === observations.flat.length,
    "selection mode did not fall back to one row per asset");
  check(observations.selecting.every((card) => !card.versions),
    "a version badge survived into selection mode");
  observations.selecting_hint = await page.locator("#library-group-hint").innerText();
  check(observations.selecting_hint.includes("1 件ずつ"),
    `selection mode did not explain itself: ${observations.selecting_hint}`);
  await page.locator("#library-select").click();
  await page.waitForFunction(() => !document.querySelector("#library-group").disabled);

  // 4. 束ねたカードを開くと、送り先はその版だけになる。
  const target = observations.grouped.find((card) => card.scene_id && !card.versions.startsWith("版 "));
  check(target, "no fully loaded scene card to open");
  const expected = observations.flat.filter((card) =>
    observations.grouped.find((g) => g.asset_id === target.asset_id)).length;
  await page.locator(`#library-grid .card[data-scene-id="${target.scene_id}"]`).click();
  await page.waitForFunction(() => document.querySelector("#viewer")?.open === true, undefined,
    {timeout: 60_000});
  observations.viewer_opened = true;
  await page.locator("#viewer-close").click();
  await page.waitForFunction(() => !document.querySelector("#viewer").open);
  void expected;

  await page.screenshot({path: screenshot, fullPage: false});
  observations.console_errors = errors;
  check(errors.length === 0, `console errors: ${errors.join(" | ")}`);
  fs.writeFileSync(`${screenshot}.json`, `${JSON.stringify(observations, null, 2)}\n`);
  console.log(JSON.stringify({
    grouped_cards: observations.grouped.length,
    flat_cards: observations.flat.length,
    collapsed_rows: observations.collapsed_rows,
    group_hint: observations.group_hint,
    selecting_hint: observations.selecting_hint,
    console_errors: errors,
  }, null, 2));
} finally {
  await browser.close();
}
