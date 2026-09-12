/** Candidate UI over a live standalone backend. No production writes or GUI starts.
 * Usage: node scripts/3ds_web_entry_readonly.mjs http://127.0.0.1:9130
 * Only the initial scene/runtime snapshot is live. Later state cases are explicitly
 * browser-local fixtures. This is not installed Host iframe or real GUI acceptance.
 */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {chromium} from "playwright-core";

const base = new URL(process.argv[2]);
assert.equal(base.protocol, "http:");
assert.ok(["127.0.0.1", "localhost", "[::1]"].includes(base.hostname));
const file = (name) => readFileSync(new URL(`../frontend/${name}`, import.meta.url), "utf8");
const browser = await chromium.launch({executablePath: "/usr/bin/google-chrome", headless: true});
const observations = [];
const errors = [];
let blockedWrites = 0;
try {
  const page = await browser.newPage();
  page.on("pageerror", (error) => errors.push(error.message));
  await page.route("**/*", async (route) => {
    const request = route.request();
    if (!["GET", "HEAD"].includes(request.method())) {
      blockedWrites += 1;
      return route.fulfill({status: 403, contentType: "application/json", body: '{"error":"readonly_probe"}'});
    }
    if (new URL(request.url()).origin !== base.origin) return route.abort();
    if (request.isNavigationRequest()) {
      const response = await route.fetch();
      assert.equal(response.status(), 200);
      const original = await response.text();
      let html = file("index.html")
        .replace("<!-- MEDIA_FORGE_INLINE_STYLE -->", () => `<style>${file("styles.css")}</style>`)
        .replace("<!-- MEDIA_FORGE_INLINE_SCRIPT -->", () => `<script>${file("app.js")}</script>`);
      for (const [marker, id] of [["WORKSPACE_CONFIG", "workspace-config-data"],
        ["CREATIVE_TEMPLATES", "creative-template-data"]]) {
        const tag = original.match(new RegExp(`<script type="application/json" id="${id}">[\\s\\S]*?</script>`));
        assert.ok(tag, id);
        html = html.replace(`<!-- MEDIA_FORGE_${marker} -->`, () => tag[0]);
      }
      return route.fulfill({response, body: html});
    }
    return route.continue();
  });
  await page.goto(new URL("/web-blender", base).href);
  await page.locator('#app[aria-busy="false"]').waitFor();
  assert.equal(await page.locator("#scene-blender-entry").isVisible(), true);
  assert.equal(await page.locator("#scene-blender-open").isDisabled(), true);
  observations.push({kind: "live_standalone_snapshot_candidate_ui", ...await page.evaluate(() => ({
    sceneCount: state.scenes.length, basic: state.blenderRuntime?.state,
    web: state.blenderRuntime?.web_pack?.state, editorVisible: byId("scene-blender-dialog").open,
  }))});

  for (const locale of ["ja", "en"]) {
    for (const width of [320, 1280]) {
      await page.setViewportSize({width, height: 900});
      await page.evaluate((locale) => {
        document.documentElement.lang = locale;
        renderSceneText();
      }, locale);
      assert.equal(await page.locator("#scene-blender-entry-title").textContent(),
        locale === "ja" ? "Web Blenderで編集" : "Edit in Web Blender");
      assert.equal(await page.locator("#scene-blender-open").isVisible(), true);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.locator("#scene-blender-settings").click();
      assert.equal(await page.locator("#view-settings").isVisible(), true);
      assert.equal(await page.evaluate(() => document.activeElement.id), "blender-settings");
      assert.equal(new URL(page.url()).pathname, "/settings");
      await page.goBack();
      assert.equal(await page.locator("#scene-blender-entry").isVisible(), true);
      observations.push({kind: "candidate_ui", locale, width, overflow: false, settingsAndBack: true});
    }
  }

  // No fixture ID is submitted to the server and the edit button is not clicked.
  await page.evaluate(() => {
    state.blenderRuntime = {state: "ready", web_pack: {state: "ready"}};
    state.blenderSessions = [];
    state.sceneWorkingCopies = [];
    state.scenes = [{id: "browser-only", name: "<b>robot</b>", revision_count: 1}];
    state.selectedSceneId = "browser-only";
    state.sceneDocument = null;
    renderScenes();
    byId("scene-detail").hidden = false;
  });
  assert.equal(await page.locator("#scene-blender-open").isDisabled(), false);
  assert.equal(await page.locator("#scene-blender-selection b").count(), 0);
  assert.match(await page.locator("#scene-blender-selection").textContent(), /<b>robot<\/b>/);
  await page.locator("#scene-detail-close").click();
  assert.equal(await page.locator("#scene-blender-open").isDisabled(), true);
  observations.push({kind: "browser_local_fixture", selectionAndClear: true, literalSceneName: true});
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({passed: true, observations, pageErrors: errors.length, blockedWrites,
    notTested: ["installed candidate", "Host opaque iframe", "Blender GUI", "OS setup", "physical mobile"]}));
} finally {
  await browser.close();
}
