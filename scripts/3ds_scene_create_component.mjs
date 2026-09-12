// Browser component acceptance with explicit in-memory backend fixtures.
// Does not contact Host, submit real jobs, or claim real Blender acceptance.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {chromium} from "playwright-core";

const root = new URL("../", import.meta.url);
const html = readFileSync(new URL("frontend/index.html", root), "utf8");
const css = readFileSync(new URL("frontend/styles.css", root), "utf8");
const source = readFileSync(new URL("frontend/app.js", root), "utf8");
const form = html.match(/<form id="scene-create-form"[\s\S]*?<\/form>/)?.[0];
assert.ok(form);
const translations = source.slice(source.indexOf("const SCENE_TEXT ="), source.indexOf("function sceneText()"));
const functions = source.slice(source.indexOf("function sceneCreationSupported()"), source.indexOf("function setSceneStatus("));
assert.ok(functions.includes("async function createWorkspaceScene()"));
const browser = await chromium.launch({executablePath: "/usr/bin/google-chrome", args: ["--no-sandbox"]});
const reports = [];
try {
  for (const language of ["ja", "en"]) for (const width of [320, 1280]) {
    const page = await browser.newPage({viewport: {width, height: 900}});
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.setContent(`<html lang="${language}"><head><style>${css}</style></head><body><main id="app" data-create-media="3d"><section id="scene-studio">${form}</section></main></body></html>`);
    await page.addScriptTag({content: `
      const state = {capabilities: {"3d.scene_recipe": {state: "available", workspace_create: true}},
        blenderRuntime: {state: "ready"}, sceneCreating: false, sceneCreationJobs: [], sceneCreationStatus: "",
        sceneCreationRefreshing: false, sceneCreationRefreshPending: false, disabled: false};
      const TERMINAL = new Set(["succeeded", "failed", "canceled"]);
      const byId = id => document.getElementById(id);
      const calls = []; const selections = []; let jobs = [];
      async function call(method, params) {
        calls.push({method, params});
        if (method === "scenes.create") {jobs = [{job_id: "job_fixture", name: params.name, status: "queued", progress: 0}]; return {job_id: "job_fixture"};}
        if (method === "scenes.creation.cancel") jobs[0].status = "canceled";
        return {items: jobs};
      }
      async function loadScenes() {selections.push("load");}
      async function openScene(id) {selections.push(id);}
      ${translations}
      function sceneText() {return SCENE_TEXT[document.documentElement.lang];}
      ${functions}
      byId("scene-create-form").addEventListener("submit", event => {event.preventDefault(); void createWorkspaceScene();});
      renderSceneCreation();
    `});
    const name = language === "ja" ? "ロボットの試作" : "Robot prototype";
    await page.locator("#scene-create-name").fill(name);
    await page.locator("#scene-create-submit").click();
    await page.waitForFunction(() => state.sceneCreationJobs.length === 1 && !state.sceneCreating);
    assert.equal(await page.evaluate(() => calls.filter(item => item.method === "scenes.create").length), 1);
    await page.locator(".scene-creation-job button").click();
    await page.waitForFunction(() => state.sceneCreationJobs[0].status === "canceled");
    await page.evaluate(() => {
      jobs = [{job_id: "job_fixture", name: "<img onerror=alert(1)>".repeat(5), status: "succeeded", result: {scene: {id: "scene_fixture"}}}];
      state.sceneCreationJobs = jobs; renderSceneCreation();
    });
    assert.equal(await page.locator("#scene-create-jobs img").count(), 0);
    await page.locator(".scene-creation-job button").click();
    assert.deepEqual(await page.evaluate(() => selections), ["load", "scene_fixture"]);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.evaluate(() => {state.capabilities["3d.scene_recipe"].workspace_create = false; renderSceneCreation();});
    assert.equal(await page.locator("#scene-create-submit").isDisabled(), true);
    assert.deepEqual(errors, []);
    reports.push({language, width, submit: true, cancel: true, select: true, no_overflow: true, page_errors: errors});
    await page.close();
  }
} finally {await browser.close();}
console.log(JSON.stringify({scope: "browser component with fixture backend; no Host/Blender jobs", reports}));
