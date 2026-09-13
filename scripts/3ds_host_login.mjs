// Read-only acceptance preparation using a fresh, owned browser context.
// Never imports cookies, records credentials, or submits a production job.
import {pathToFileURL} from "node:url";
import {setTimeout as delay} from "node:timers/promises";

export const HOST_ORIGIN = "http://127.0.0.1:8765";

/** @param {import('playwright-core').Page} page */
export async function ownedLoginState(page) {
  const response = await page.context().request.get(`${HOST_ORIGIN}/api/v1/auth/me`, {
    headers: {"X-Requested-With": "ControlDeck"}, timeout: 5000,
    maxRedirects: 0,
  });
  try {
    if (response.status() === 401) return "login_required";
    if (response.status() !== 200) throw new Error("host_identity_unavailable");
    if (!response.headers()["content-type"]?.includes("application/json")) {
      throw new Error("host_identity_invalid");
    }
    const identity = await response.json();
    if (!identity || !Number.isSafeInteger(identity.id) || identity.id < 1
        || typeof identity.username !== "string" || !Array.isArray(identity.permissions)
        || typeof identity.totp_required !== "boolean" || typeof identity.totp_enabled !== "boolean") {
      throw new Error("host_identity_invalid");
    }
    return identity.totp_required && !identity.totp_enabled ? "totp_setup_required" : "authenticated";
  } finally {
    await response.dispose();
  }
}

/** @param {import('playwright-core').Page} page */
export async function openOwnedWorkspace(page) {
  const state = await ownedLoginState(page);
  if (state !== "authenticated") return {state, workspaceOpened: false};
  // The current Host login page navigates to '/', ignoring the initial route.
  // Authentication and presence of the MediaForge frame are different gates.
  await page.goto(`${HOST_ORIGIN}/x/media-forge/workspace`, {timeout: 15000});
  await page.locator('iframe[title="Media Forge — workspace"]').waitFor({state: "visible", timeout: 15000});
  return {state, workspaceOpened: true};
}

async function main() {
  const {chromium} = await import("playwright-core");
  const browser = await chromium.launch({executablePath: "/usr/bin/google-chrome",
    headless: false, args: ["--window-size=1280,1000"]});
  try {
    const context = await browser.newContext({viewport: null});
    const page = await context.newPage();
    await page.goto(`${HOST_ORIGIN}/login`);
    console.log(JSON.stringify({stage: "own_login_window_open"}));
    const deadline = Date.now() + 600000;
    while (!page.isClosed() && Date.now() < deadline) {
      const result = await openOwnedWorkspace(page);
      if (result.workspaceOpened) {
        console.log(JSON.stringify({stage: "authenticated_workspace_opened"}));
        return;
      }
      if (result.state === "totp_setup_required") {
        console.log(JSON.stringify({stage: "totp_setup_required"}));
        return;
      }
      await delay(1000);
    }
    console.log(JSON.stringify({stage: "login_not_confirmed"}));
    process.exitCode = 2;
  } finally {
    await browser.close();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(() => {
    // Playwright errors may include request details: do not print raw errors.
    console.error(JSON.stringify({stage: "host_login_preflight_failed"}));
    process.exitCode = 1;
  });
}
