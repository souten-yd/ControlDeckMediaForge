import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import vm from "node:vm";

// Execute the product renderer, not a duplicate of its state logic.
const source = readFileSync(new URL("../frontend/app.js", import.meta.url), "utf8");
const renderer = source.slice(source.indexOf("const ACTIVE_BLENDER_SESSION_STATES"),
  source.indexOf("async function forkSceneRecovery"));
const translations = source.slice(source.indexOf("const SCENE_TEXT ="),
  source.indexOf("function sceneText()"));

function fixture(language = "ja") {
  const elements = new Map();
  const state = {
    selectedSceneId: "", scenes: [{id: "a", name: "<b>robot</b>"}],
    sceneWorkingCopies: [], blenderSessions: [], sceneRecoveryBusy: false,
    blenderRuntime: {state: "ready", web_pack: {state: "ready"}},
  };
  const byId = (id) => {
    if (!elements.has(id)) elements.set(id, {});
    return elements.get(id);
  };
  const context = vm.createContext({state, byId, language,
    sceneRuntimeReady: () => state.blenderRuntime?.state === "ready",
    setBlenderSessionBusy: () => {}, renderSceneBackupControls: () => {},
    closeBlenderView: () => {},
  });
  vm.runInContext(translations + '\nfunction sceneText() { return SCENE_TEXT[language]; }\n' + renderer, context);
  const render = () => vm.runInContext("renderBlenderSessionControls()", context);
  return {state, byId, render};
}

test("no selection is disabled even with both runtimes ready; selection and clearing update the target", () => {
  const {state, byId, render} = fixture();
  render();
  assert.equal(byId("scene-blender-open").disabled, true);
  assert.equal(byId("scene-blender-selection").textContent, "編集するシーンを選んでください。");
  state.selectedSceneId = "a";
  render();
  assert.equal(byId("scene-blender-open").disabled, false);
  assert.equal(byId("scene-blender-selection").textContent, "編集対象: <b>robot</b>");
  assert.equal(byId("scene-blender-selection").innerHTML, undefined);
  state.selectedSceneId = "";
  render();
  assert.equal(byId("scene-blender-open").disabled, true);
});

test("missing basic and web runtimes have distinct guidance", () => {
  const {state, byId, render} = fixture();
  state.blenderRuntime.state = "missing";
  render();
  assert.match(byId("scene-blender-status").textContent, /基本環境/);
  state.blenderRuntime.state = "ready";
  state.blenderRuntime.web_pack.state = "missing";
  render();
  assert.match(byId("scene-blender-status").textContent, /ブラウザ操作環境/);
  assert.equal(byId("scene-blender-open").disabled, true);
});

test("existing session return and other-scene exclusion remain intact", () => {
  const {state, byId, render} = fixture("en");
  state.selectedSceneId = "a";
  state.blenderSessions = [{id: "session", scene_id: "a", state: "ready"}];
  render();
  assert.equal(byId("scene-blender-open").disabled, false);
  assert.equal(byId("scene-blender-open").textContent, "Return to Blender");
  state.selectedSceneId = "b";
  render();
  assert.equal(byId("scene-blender-open").disabled, true);
  assert.match(byId("scene-blender-status").textContent, /another scene/i);
});

test("preparing, saving, stopping, imports, backup, and recovery keep editing disabled", () => {
  const {state, byId, render} = fixture();
  state.selectedSceneId = "a";
  for (const phase of ["queued", "preparing", "starting", "saving", "stopping"]) {
    state.blenderSessions = [{scene_id: "a", state: phase}];
    render();
    assert.equal(byId("scene-blender-open").disabled, true, phase);
  }
  state.blenderSessions = [];
  for (const key of ["sceneImport", "sceneBackup", "sceneRecoveryBusy"]) {
    state[key] = true;
    render();
    assert.equal(byId("scene-blender-open").disabled, true, key);
    state[key] = false;
  }
});
