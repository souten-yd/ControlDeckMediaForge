#!/usr/bin/env node
// 通しフローを実機の画面から回し、段ごとに止まって承認で進むことを確かめる。
// 固定値は無い。動くのは実機の 3D 生成と Blender である。

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
const observations = {stages: []};
const errors = [];
const browser = await chromium.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: true,
  args: ["--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader"],
});

const shape = () => [...document.querySelectorAll("#pipeline-stages li")]
  .map((row) => `${row.dataset.stage}:${row.dataset.state}`).join(" | ");

try {
  const page = await browser.newPage({viewport: {width: 1280, height: 1000}});
  page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
  page.on("pageerror", (error) => errors.push(String(error)));
  // 3D Studio は「作る」画面の中で、素材の種類を 3D にしたときに出る。
  await page.goto(`${baseUrl}/create`, {waitUntil: "domcontentloaded"});
  await page.waitForSelector('#app[aria-busy="false"]');
  await page.locator("#create-media-3d").click();
  await page.waitForFunction(
    () => document.querySelector("#app").dataset.createMedia === "3d");
  await page.waitForSelector("#pipeline-panel", {state: "visible"});

  // 単体表示では 3D の仕事が走らない（host の資源を借りられない）。ここで
  // 確かめるのは、押せてから失敗するのではなく先に理由を言うことと、
  // 画面の配線が揃っていることである。実際に通す確認は MCP 経由で行う。
  observations.hosted = await page.evaluate(() => window.parent !== window);
  check(!observations.hosted, "this fixture expects the standalone view");
  observations.start_disabled = await page.locator("#pipeline-start").isDisabled();
  check(observations.start_disabled, "the pipeline offered to start without a host");
  observations.status = await page.locator("#pipeline-status").innerText();
  check(observations.status.includes("ControlDeck"),
    `the reason was not stated: ${observations.status}`);

  // 画像の一覧は 3D に切り替えたあとに読み込まれる。入るまで待つ。
  await page.waitForFunction(
    () => [...document.querySelectorAll("#scene-generation-image option")]
      .some((node) => node.value),
    undefined, {timeout: 60_000});
  const options = await page.locator("#scene-generation-image option").evaluateAll(
    (nodes) => nodes.map((node) => node.value).filter(Boolean));
  check(options.length > 0, "no image is available to start from");
  observations.image_options = options.length;
  await page.selectOption("#scene-generation-image", options[0]);
  // 画像を選んでも、host が無い限り押せるようにはならない。
  check(await page.locator("#pipeline-start").isDisabled(),
    "picking an image made it offer to start without a host");

  // 既に作られた通しフローがあれば、段の並びがそのまま読めること。
  const listed = await page.evaluate(async () => {
    const response = await fetch("/workspace-api/pipelines");
    return response.ok ? await response.json() : null;
  });
  check(listed && Array.isArray(listed.items), "the pipeline list is unavailable");
  observations.stored_pipelines = listed.items.length;
  if (listed.items.length > 0) {
    observations.stages = listed.items[0].stages.map(
      (stage) => `${stage.name}:${stage.state}`);
  }

  await page.screenshot({path: screenshot, fullPage: false});
  observations.console_errors = errors;
  check(errors.length === 0, `console errors: ${errors.join(" | ")}`);
  fs.writeFileSync(`${screenshot}.json`, `${JSON.stringify(observations, null, 2)}\n`);
  console.log(JSON.stringify(observations, null, 2));
} finally {
  await browser.close();
}
