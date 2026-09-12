import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../frontend/app.js", import.meta.url), "utf8");
const translations = source.slice(source.indexOf("const SCENE_TEXT ="), source.indexOf("function sceneText()"));
const functions = source.slice(source.indexOf("function sceneCreationSupported()"), source.indexOf("function setSceneStatus("));

function fixture() {
  const elements = new Map(), calls = [], selections = [];
  const node = () => ({children: [], events: {}, value: "",
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
    addEventListener(name, handler) { this.events[name] = handler; }});
  const byId = (id) => { if (!elements.has(id)) elements.set(id, node()); return elements.get(id); };
  const state = {capabilities: {"3d.scene_recipe": {state: "available", workspace_create: true}},
    blenderRuntime: {state: "ready"}, sceneCreating: false, sceneCreationJobs: [], sceneCreationStatus: "", sceneCreationRefreshing: false,
    sceneCreationRefreshPending: false, disabled: false};
  const backend = {run: async (method) => method === "scenes.creation.list" ? {items: []} : {job_id: "job_a"}};
  const context = vm.createContext({state, byId, document: {createElement: node},
    TERMINAL: new Set(["succeeded", "failed", "canceled"]), sceneRuntimeReady: () => true,
    call: async (method, params) => { calls.push([method, params]); return backend.run(method, params); },
    loadScenes: async () => selections.push("load"), openScene: async (id) => selections.push(id)});
  vm.runInContext(translations + "\nfunction sceneText() {return SCENE_TEXT.en;}\n" + functions, context);
  return {state, byId, calls, selections, backend, run: (code) => vm.runInContext(code, context)};
}

test("capability and disabled state block submission", async () => {
  const f = fixture(); f.byId("scene-create-name").value = "Robot";
  for (const capability of [{state: "available", workspace_create: false}, {state: "unavailable", workspace_create: true}]) {
    f.state.capabilities["3d.scene_recipe"] = capability;
    f.run("renderSceneCreation()");
    assert.equal(f.byId("scene-create-submit").disabled, true);
    await f.run("createWorkspaceScene()");
  }
  assert.equal(f.calls.length, 0);
});

test("blank input and double click do not create extra jobs; watch failure is not submission failure", async () => {
  const f = fixture();
  await f.run("createWorkspaceScene()"); assert.equal(f.calls.length, 0);
  f.byId("scene-create-name").value = " Robot ";
  let complete;
  f.backend.run = async (method) => {
    if (method === "scenes.create") return new Promise(resolve => {complete = resolve;});
    if (method === "jobs.watch") throw Error("connection lost");
    return {items: [{job_id: "job_a", name: "Robot", status: "queued", progress: 0}]};
  };
  const pending = f.run("createWorkspaceScene()");
  await f.run("createWorkspaceScene()");
  assert.equal(f.calls.length, 1); assert.equal(f.calls[0][1].name, "Robot");
  complete({job_id: "job_a"}); await pending;
  assert.notEqual(f.state.sceneCreationStatus, "createFailed");
  assert.equal(f.state.sceneCreationJobs.length, 1); assert.equal(f.state.sceneCreating, false);
});

test("refresh failure retains loaded jobs and renders untrusted names as text", async () => {
  const f = fixture();
  const jobs = [{job_id: "job_a", name: "<img onerror=evil()>", status: "failed", error: {code: "worker_failed"}}];
  f.state.sceneCreationJobs = jobs; f.backend.run = async () => {throw Error("offline");};
  await f.run("refreshSceneCreationJobs()");
  assert.equal(f.state.sceneCreationJobs, jobs);
  assert.equal(f.state.sceneCreationStatus, "createReadFailed");
  const label = f.byId("scene-create-jobs").children[0].children[0];
  assert.match(label.textContent, /<img onerror=evil\(\)>/); assert.equal(label.innerHTML, undefined);
});

test("restored completed jobs select their scene; active jobs use owned cancel route", async () => {
  const f = fixture();
  f.backend.run = async () => ({items: [
    {job_id: "job_a", name: "Completed", status: "succeeded", result: {scene: {id: "scene_a"}}},
    {job_id: "job_b", name: "Pending", status: "queued"},
  ]});
  await f.run("refreshSceneCreationJobs()");
  await f.byId("scene-create-jobs").children[0].children[1].events.click();
  assert.deepEqual(f.selections, ["load", "scene_a"]);
  await f.byId("scene-create-jobs").children[1].children[1].events.click();
  assert.equal(f.calls.find(([method]) => method === "scenes.creation.cancel")[1].job_id, "job_b");
});
