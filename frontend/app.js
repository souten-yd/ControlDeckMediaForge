const api = (path, options = {}) => fetch(`api/v1/${path}`, {headers: {"Content-Type": "application/json"}, ...options});
const terminalStates = new Set(["succeeded", "failed", "canceled"]);
let bridgePort = null;
let bridgeNonce = "";
let bridgeSequence = 0;
let activeJobId = "";
let disabled = false;
let hostBusy = false;

function applyTheme(theme = {}) {
  const root = document.documentElement;
  const values = {bg: theme.bg, surface: theme.surface, text: theme.text, border: theme.border, muted: theme.muted, accent: theme.accent};
  Object.entries(values).forEach(([name, value]) => { if (typeof value === "string") root.style.setProperty(`--${name}`, value); });
  if (theme.safe_area) applySafeArea(theme.safe_area);
  if (theme.color_scheme) root.style.colorScheme = theme.color_scheme;
  if (theme.locale) root.lang = theme.locale;
}

function applySafeArea(value = {}) {
  const root = document.documentElement;
  for (const side of ["top", "right", "bottom", "left"]) {
    if (Number.isFinite(value[side])) root.style.setProperty(`--safe-${side}`, `${value[side]}px`);
  }
}

function callHost(method, params = {}) {
  if (!bridgePort) return Promise.reject({code: "bridge_unavailable", message: "ControlDeck Host Bridge is unavailable"});
  return new Promise((resolve, reject) => {
    const id = `media-forge-${++bridgeSequence}`;
    const listener = (event) => {
      const message = event.data;
      if (message?.type !== "response" || message.id !== id) return;
      bridgePort.removeEventListener("message", listener);
      message.ok ? resolve(message.result) : reject(message.error);
    };
    bridgePort.addEventListener("message", listener);
    bridgePort.postMessage({id, method, params, session_nonce: bridgeNonce});
  });
}

function setHostBusy(value) {
  if (!bridgePort || hostBusy === value) return;
  hostBusy = value;
  void callHost("host.busy.set", {busy: value}).catch(() => { hostBusy = !value; });
}

function activate(name, sync = true) {
  const selected = document.getElementById(name) ? name : "create";
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === selected));
  document.querySelectorAll(".panel").forEach((panel) => panel.classList.toggle("active", panel.id === selected));
  if (selected === "library") void loadAssets();
  if (selected === "jobs") void loadJobs();
  if (sync && bridgePort) void callHost("host.route.sync", {path: selected === "create" ? "/" : `/${selected}`}).catch(() => {});
}

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => activate(tab.dataset.tab)));
document.querySelectorAll("[data-refresh]").forEach((button) => button.addEventListener("click", () => activate(button.dataset.refresh, false)));
document.querySelectorAll("#create-form textarea, #create-form input, #create-form select").forEach((field) => field.addEventListener("input", () => {
  setHostBusy(true);
}));

document.getElementById("create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (disabled) return;
  const status = document.getElementById("create-status");
  status.textContent = "受付中…";
  const response = await api("jobs", {method: "POST", body: JSON.stringify({
    operation: "image.generate",
    intent: document.getElementById("intent").value,
    model_policy: document.getElementById("policy").value,
    constraints: {width: Number(document.getElementById("width").value), height: Number(document.getElementById("height").value)},
    output: {format: "png", count: Number(document.getElementById("count").value)},
    local_only: true
  })});
  if (!response.ok) { status.textContent = `受付に失敗しました (${response.status})`; return; }
  setHostBusy(false);
  const job = await response.json();
  activeJobId = job.id;
  status.textContent = `Job ${job.id} を実行中…`;
  void pollJob(job.id, status);
});

async function pollJob(id, statusNode) {
  for (let attempt = 0; attempt < 300 && !disabled; attempt += 1) {
    const response = await api(`jobs/${encodeURIComponent(id)}`);
    if (!response.ok) break;
    const job = await response.json();
    statusNode.textContent = `${job.status} · ${Math.round(job.progress * 100)}% · ${job.phase || "-"}`;
    if (terminalStates.has(job.status)) {
      activeJobId = "";
      if (job.status === "succeeded") { await loadAssets(); activate("library"); }
      if (bridgePort) void callHost("host.notification.show", {title: "Media Forge", message: `Job ${job.status}`, level: job.status === "succeeded" ? "success" : "error", dedupe_key: id}).catch(() => {});
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  if (!disabled) statusNode.textContent = "状態確認がタイムアウトしました。Jobsから確認してください。";
}

async function loadAssets() {
  const grid = document.getElementById("asset-grid");
  const response = await api("assets");
  if (!response.ok) { grid.textContent = "Libraryを読み込めませんでした。"; return; }
  const {items} = await response.json();
  grid.replaceChildren();
  if (!items.length) { const p = document.createElement("p"); p.className = "muted"; p.textContent = "まだ素材はありません。"; grid.append(p); return; }
  items.forEach((asset) => {
    const card = document.createElement("article"); card.className = "asset-card";
    const image = document.createElement("img"); image.src = `api/v1/assets/${encodeURIComponent(asset.id)}/content`; image.alt = asset.suggested_filename;
    const title = document.createElement("strong"); title.textContent = asset.suggested_filename;
    const detail = document.createElement("p"); detail.textContent = `${asset.width}×${asset.height} · ${asset.id}`;
    const button = document.createElement("button"); button.textContent = "Provenance"; button.addEventListener("click", () => showProvenance(asset.id));
    card.append(image, title, detail, button); grid.append(card);
  });
}

async function loadJobs() {
  const list = document.getElementById("job-list");
  const response = await api("jobs");
  if (!response.ok) { list.textContent = "Jobsを読み込めませんでした。"; return; }
  const {items} = await response.json(); list.replaceChildren();
  if (!items.length) { list.textContent = "Job履歴はありません。"; return; }
  items.forEach((job) => {
    const card = document.createElement("article"); card.className = "job-card";
    const info = document.createElement("div"); const title = document.createElement("strong"); title.textContent = job.request.intent;
    const detail = document.createElement("p"); detail.textContent = `${job.id} · ${job.phase || "-"}`; info.append(title, detail);
    const state = document.createElement("span"); state.className = "status"; state.textContent = job.status;
    card.append(info, state); list.append(card);
  });
}

async function showProvenance(id) {
  const response = await api(`assets/${encodeURIComponent(id)}/provenance`);
  if (!response.ok) return;
  document.getElementById("provenance").textContent = JSON.stringify(await response.json(), null, 2);
  document.getElementById("provenance-dialog").showModal();
}

document.getElementById("close-dialog").addEventListener("click", () => document.getElementById("provenance-dialog").close());
document.getElementById("open-host-jobs").addEventListener("click", () => {
  void callHost("host.route.open", {route: "/jobs"}).catch(() => {});
});

window.addEventListener("message", (event) => {
  const expectedOrigin = document.referrer ? new URL(document.referrer).origin : location.origin;
  if (event.source !== parent || event.origin !== expectedOrigin || event.data?.type !== "control-deck-host.connected" || !event.ports[0]) return;
  bridgePort = event.ports[0]; bridgeNonce = event.data.session_nonce; applyTheme(event.data.theme);
  bridgePort.onmessage = (messageEvent) => {
    const message = messageEvent.data;
    if (message?.type !== "event") return;
    if (message.event === "theme.changed") applyTheme(message.data);
    if (message.event === "locale.changed" && message.data?.locale) document.documentElement.lang = message.data.locale;
    if (message.event === "safe_area.changed") applySafeArea(message.data);
    if (message.event === "route.changed") activate(String(message.data?.path || "/").split("/")[1] || "create", false);
    if (message.event === "session.updated") bridgeNonce = message.data.session_nonce;
    if (message.event === "disable.pending") {
      disabled = true;
      if (activeJobId) void api(`jobs/${encodeURIComponent(activeJobId)}`, {method: "DELETE"}).catch(() => {});
      activeJobId = "";
      setHostBusy(false);
    }
  };
  bridgePort.start();
  document.documentElement.dataset.bridge = "ready";
  document.getElementById("workspace").setAttribute("aria-busy", "false");
  void callHost("host.title.set", {title: "Media Forge"}).catch(() => {});
});

window.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k" && bridgePort) {
    event.preventDefault(); bridgePort.postMessage({type: "shortcut", shortcut: "command_palette", session_nonce: bridgeNonce});
  }
});

if (window.parent === window) {
  document.documentElement.dataset.bridge = "standalone";
  document.getElementById("workspace").setAttribute("aria-busy", "false");
} else {
  window.parent.postMessage({type: "control-deck-addon.connect", bridge_version: "1.0"}, "*");
}
