const api = (path, options = {}) => fetch(`api/v1/${path}`, {headers: {"Content-Type": "application/json"}, ...options});
const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");

function activate(name) {
  tabs.forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
  panels.forEach((panel) => panel.classList.toggle("active", panel.id === name));
  if (name === "library") loadAssets();
  if (name === "jobs") loadJobs();
}
tabs.forEach((tab) => tab.addEventListener("click", () => activate(tab.dataset.tab)));
document.querySelectorAll("[data-refresh]").forEach((button) => button.addEventListener("click", () => activate(button.dataset.refresh)));

document.getElementById("create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = document.getElementById("create-status");
  status.textContent = "受付中…";
  const response = await api("jobs", {method: "POST", body: JSON.stringify({
    operation: "image.generate",
    intent: document.getElementById("intent").value,
    model_policy: "auto",
    constraints: {width: Number(document.getElementById("width").value), height: Number(document.getElementById("height").value)},
    output: {format: "png", count: 1},
    local_only: true
  })});
  if (!response.ok) { status.textContent = `受付に失敗しました (${response.status})`; return; }
  const job = await response.json();
  status.textContent = `Job ${job.id} を実行中…`;
  pollJob(job.id, status);
});

async function pollJob(id, statusNode) {
  for (let attempt = 0; attempt < 150; attempt += 1) {
    const response = await api(`jobs/${id}`);
    if (!response.ok) break;
    const job = await response.json();
    statusNode.textContent = `${job.status} · ${Math.round(job.progress * 100)}% · ${id}`;
    if (job.status === "succeeded") { await loadAssets(); activate("library"); return; }
    if (["failed", "canceled"].includes(job.status)) return;
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  statusNode.textContent = "状態確認がタイムアウトしました。Jobs から確認してください。";
}

async function loadAssets() {
  const grid = document.getElementById("asset-grid");
  const response = await api("assets");
  if (!response.ok) { grid.textContent = "Library を読み込めませんでした。"; return; }
  const {items} = await response.json();
  grid.replaceChildren();
  if (!items.length) { const p = document.createElement("p"); p.className = "muted"; p.textContent = "まだ素材はありません。"; grid.append(p); return; }
  items.forEach((asset) => {
    const card = document.createElement("article"); card.className = "asset-card";
    const image = document.createElement("img"); image.src = `api/v1/assets/${asset.id}/content`; image.alt = asset.suggested_filename;
    const title = document.createElement("strong"); title.textContent = asset.suggested_filename;
    const detail = document.createElement("p"); detail.textContent = `${asset.width}×${asset.height} · ${asset.id}`;
    const button = document.createElement("button"); button.textContent = "Provenance"; button.addEventListener("click", () => showProvenance(asset.id));
    card.append(image, title, detail, button); grid.append(card);
  });
}

async function loadJobs() {
  const list = document.getElementById("job-list");
  const response = await api("jobs");
  if (!response.ok) { list.textContent = "Jobs を読み込めませんでした。"; return; }
  const {items} = await response.json(); list.replaceChildren();
  items.forEach((job) => {
    const card = document.createElement("article"); card.className = "job-card";
    const info = document.createElement("div"); const title = document.createElement("strong"); title.textContent = job.request.intent;
    const detail = document.createElement("p"); detail.textContent = `${job.id} · ${job.phase || "-"}`; info.append(title, detail);
    const state = document.createElement("span"); state.className = "status"; state.textContent = job.status;
    card.append(info, state); list.append(card);
  });
}

async function showProvenance(id) {
  const response = await api(`assets/${id}/provenance`);
  if (!response.ok) return;
  document.getElementById("provenance").textContent = JSON.stringify(await response.json(), null, 2);
  document.getElementById("provenance-dialog").showModal();
}
document.getElementById("close-dialog").addEventListener("click", () => document.getElementById("provenance-dialog").close());

let bridgePort = null; let bridgeNonce = "";
window.addEventListener("message", (event) => {
  if (event.source !== parent || event.data?.type !== "control-deck-host.connected" || !event.ports[0]) return;
  bridgePort = event.ports[0]; bridgeNonce = event.data.session_nonce; bridgePort.start();
  bridgePort.postMessage({id: "media-title", method: "host.title.set", params: {title: "Media Forge"}, session_nonce: bridgeNonce});
});
window.parent.postMessage({type: "control-deck-addon.connect", bridge_version: "1.0"}, "*");
