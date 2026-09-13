import assert from "node:assert/strict";
import {test} from "node:test";
import {HOST_ORIGIN, ownedLoginState, openOwnedWorkspace} from "../scripts/3ds_host_login.mjs";

function fixture({status = 200, contentType = "application/json", identity} = {}) {
  const calls = [];
  const response = {
    status: () => status, headers: () => ({"content-type": contentType}),
    json: async () => identity ?? {id: 7, username: "fixture", permissions: [],
      totp_enabled: false, totp_required: false},
    dispose: async () => { calls.push("dispose"); },
  };
  const page = {
    context: () => ({request: {get: async (...args) => {calls.push(["get", ...args]); return response;}}}),
    goto: async (...args) => { calls.push(["goto", ...args]); },
    locator: selector => ({waitFor: async options => { calls.push(["wait", selector, options]); }}),
  };
  return {page, calls};
}

test("normal login landing on home is followed by explicit workspace navigation", async () => {
  const {page, calls} = fixture();
  assert.deepEqual(await openOwnedWorkspace(page), {state: "authenticated", workspaceOpened: true});
  assert.deepEqual(calls[0], ["get", `${HOST_ORIGIN}/api/v1/auth/me`, {
    headers: {"X-Requested-With": "ControlDeck"}, timeout: 5000, maxRedirects: 0,
  }]);
  assert.equal(calls[1], "dispose");
  assert.equal(calls[2][1], `${HOST_ORIGIN}/x/media-forge/workspace`);
  assert.deepEqual(calls[3], ["wait", 'iframe[title="Media Forge — workspace"]',
    {state: "visible", timeout: 15000}]);
});

test("401 does not navigate away from the user login form", async () => {
  const {page, calls} = fixture({status: 401});
  assert.deepEqual(await openOwnedWorkspace(page), {state: "login_required", workspaceOpened: false});
  assert.equal(calls.length, 2);
});

for (const options of [{status: 302}, {status: 403}, {contentType: "text/html"},
  {identity: {id: 7}}, {identity: {id: 0, username: "fixture", permissions: [], totp_required: false, totp_enabled: false}}]) {
  test(`non-identity response is not login success: ${JSON.stringify(options)}`, async () => {
    const {page, calls} = fixture(options);
    await assert.rejects(ownedLoginState(page), /host_identity_(invalid|unavailable)/);
    assert.equal(calls.at(-1), "dispose");
  });
}

test("required TOTP enrollment is distinct from a usable workspace", async () => {
  const {page, calls} = fixture({identity: {id: 7, username: "fixture", permissions: [],
    totp_required: true, totp_enabled: false}});
  assert.deepEqual(await openOwnedWorkspace(page), {state: "totp_setup_required", workspaceOpened: false});
  assert.equal(calls.length, 2);
});

test("iframe failure after authentication is not workspace success", async () => {
  const {page} = fixture();
  page.locator = () => ({waitFor: async () => {throw new Error("fixture_frame_timeout");}});
  await assert.rejects(openOwnedWorkspace(page), /fixture_frame_timeout/);
});
