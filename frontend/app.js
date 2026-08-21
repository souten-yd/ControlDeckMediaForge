const terminalStates = new Set(["succeeded", "failed", "canceled"]);
let bridgePort = null;
let bridgeNonce = "";
let bridgeSequence = 0;
let activeJobId = "";
let disabled = false;
let hostBusy = false;
let workspaceSocket = null;
let workspaceSocketReady = null;
const workspacePending = new Map();

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
    const id = `media-forge-host-${++bridgeSequence}`;
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

function connectWorkspaceSocket() {
  if (workspaceSocketReady) return workspaceSocketReady;
  workspaceSocketReady = new Promise((resolve, reject) => {
    const frameRoot = location.pathname.split("/").slice(0, 3).join("/");
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    workspaceSocket = new WebSocket(`${scheme}://${location.host}${frameRoot}/ws`, [`control-deck-bridge.${bridgeNonce}`]);
    workspaceSocket.onopen = () => resolve();
    workspaceSocket.onerror = () => reject({code: "workspace_transport_unavailable"});
    workspaceSocket.onclose = () => {
      for (const pending of workspacePending.values()) pending.reject({code: "workspace_transport_closed"});
      workspacePending.clear();
    };
    workspaceSocket.onmessage = (event) => {
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      const pending = workspacePending.get(message?.id);
      if (!pending) return;
      workspacePending.delete(message.id);
      message.ok ? pending.resolve(message.result) : pending.reject(message.error);
    };
  });
  return workspaceSocketReady;
}

async function standaloneCall(method, params) {
  const jsonRequest = async (path, options = {}) => {
    const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
    if (!response.ok) throw {code: `http_${response.status}`};
    return response.json();
  };
  if (method === "jobs.create") return jsonRequest("/api/v1/jobs", {method: "POST", body: JSON.stringify(params)});
  if (method === "jobs.get") return jsonRequest(`/api/v1/jobs/${encodeURIComponent(params.job_id)}`);
  if (method === "jobs.cancel") return jsonRequest(`/api/v1/jobs/${encodeURIComponent(params.job_id)}`, {method: "DELETE"});
  if (method === "jobs.list") return jsonRequest("/api/v1/jobs");
  if (method === "assets.list") return jsonRequest("/api/v1/assets");
  if (method === "assets.import") {
    const binary = atob(params.base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const response = await fetch(`/api/v1/assets/import?purpose=${encodeURIComponent(params.purpose)}`, {
      method: "POST", headers: {"Content-Type": "application/octet-stream"}, body: bytes
    });
    if (!response.ok) throw {code: `http_${response.status}`};
    return response.json();
  }
  if (method === "models.list") return jsonRequest("/api/v1/models");
  if (method === "assets.provenance") return jsonRequest(`/api/v1/assets/${encodeURIComponent(params.asset_id)}/provenance`);
  if (method === "assets.content") {
    const response = await fetch(`/api/v1/assets/${encodeURIComponent(params.asset_id)}/content`);
    if (!response.ok) throw {code: `http_${response.status}`};
    const bytes = new Uint8Array(await response.arrayBuffer());
    let binary = "";
    bytes.forEach((value) => { binary += String.fromCharCode(value); });
    return {mime_type: response.headers.get("content-type") || "application/octet-stream", base64: btoa(binary)};
  }
  throw {code: "workspace_method_unsupported"};
}

async function workspaceCall(method, params = {}) {
  if (window.parent === window) return standaloneCall(method, params);
  await connectWorkspaceSocket();
  return new Promise((resolve, reject) => {
    const id = `media-forge-workspace-${++bridgeSequence}`;
    workspacePending.set(id, {resolve, reject});
    workspaceSocket.send(JSON.stringify({id, method, params}));
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
  if (selected === "models") void loadModels();
  if (sync && bridgePort) void callHost("host.route.sync", {path: selected === "create" ? "/" : `/${selected}`}).catch(() => {});
}

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => activate(tab.dataset.tab)));
document.querySelectorAll("[data-refresh]").forEach((button) => button.addEventListener("click", () => activate(button.dataset.refresh, false)));
document.querySelectorAll("#create-form textarea, #create-form input, #create-form select").forEach((field) => field.addEventListener("input", () => setHostBusy(true)));
document.getElementById("operation").addEventListener("change", (event) => {
  const editing = event.target.value === "image.edit";
  document.getElementById("edit-inputs").hidden = !editing;
  document.getElementById("source-file").required = editing;
  document.getElementById("mask-file").required = editing && document.getElementById("edit-mode").value === "strict";
  document.getElementById("reference-files").required = editing && document.getElementById("edit-mode").value === "multi_reference";
});

document.getElementById("edit-mode").addEventListener("change", (event) => {
  const strict = event.target.value === "strict";
  const multiReference = event.target.value === "multi_reference";
  document.getElementById("mask-input").hidden = !strict;
  document.getElementById("reference-input").hidden = !multiReference;
  document.getElementById("mask-file").required = strict;
  document.getElementById("reference-files").required = multiReference;
  document.getElementById("edit-help").textContent = strict
    ? "白い部分だけを変更するマスクを指定します。黒い部分は1ピクセルも変更しません。"
    : event.target.value === "outpaint"
      ? "幅と高さを元画像以上に設定して外側を生成します。中央の元画像は1ピクセルも変更しません。"
    : multiReference
      ? "元画像に加えて1〜3枚の参照画像を使います。画像全体が変わる可能性があります。"
    : event.target.value === "variation"
      ? "元画像の特徴を参考に別案を作ります。画像全体が変わる可能性があります。"
      : "元画像全体を指示に沿って編集します。ピクセル保持保証はありません。";
});

async function fileBase64(file) {
  if (!file || file.size < 1 || file.size > 64 * 1024 * 1024) throw {code: "invalid_import_size"};
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  const chunk = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunk) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunk));
  }
  return btoa(binary);
}

async function importFile(file, purpose) {
  if (!file || file.size < 1 || file.size > 64 * 1024 * 1024) throw {code: "invalid_import_size"};
  if (window.parent === window) {
    return workspaceCall("assets.import", {purpose, base64: await fileBase64(file)});
  }
  const upload = await workspaceCall("assets.import.begin", {purpose, size: file.size});
  for (let offset = 0; offset < file.size; offset += upload.chunk_bytes) {
    const slice = file.slice(offset, Math.min(file.size, offset + upload.chunk_bytes));
    const base64 = await fileBase64(slice);
    await workspaceCall("assets.import.chunk", {upload_id: upload.upload_id, offset, base64});
  }
  return workspaceCall("assets.import.commit", {upload_id: upload.upload_id});
}

document.getElementById("create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (disabled) return;
  const status = document.getElementById("create-status");
  status.textContent = "受付中…";
  try {
    const operation = document.getElementById("operation").value;
    let inputs = [];
    const constraints = {
      width: Number(document.getElementById("width").value),
      height: Number(document.getElementById("height").value)
    };
    if (operation === "image.edit") {
      const editMode = document.getElementById("edit-mode").value;
      const strict = editMode === "strict";
      const preserving = strict || editMode === "outpaint";
      status.textContent = strict ? "元画像とマスクをローカルへ取り込み中…" : "元画像をローカルへ取り込み中…";
      const sourceFile = document.getElementById("source-file").files[0];
      const source = await importFile(sourceFile, "source");
      inputs = [{asset_id: source.id}];
      if (editMode !== "outpaint") {
        constraints.width = source.width;
        constraints.height = source.height;
      }
      constraints.strict_edit = preserving;
      constraints.edit_mode = editMode === "strict" ? "inpaint" : editMode;
      if (strict) {
        const maskFile = document.getElementById("mask-file").files[0];
        const mask = await importFile(maskFile, "edit_mask");
        constraints.editable_mask_asset_id = mask.id;
      }
      if (editMode === "multi_reference") {
        const files = Array.from(document.getElementById("reference-files").files);
        if (files.length < 1 || files.length > 3) throw {code: "invalid_reference_count"};
        status.textContent = "元画像と参照画像をローカルへ取り込み中…";
        for (const file of files) {
          const reference = await importFile(file, "source");
          inputs.push({asset_id: reference.id});
        }
      }
    }
    const job = await workspaceCall("jobs.create", {
      operation,
      intent: document.getElementById("intent").value,
      inputs,
      model_policy: document.getElementById("policy").value,
      constraints,
      output: {format: "png", count: Number(document.getElementById("count").value)},
      local_only: true
    });
    setHostBusy(false);
    activeJobId = job.id;
    status.textContent = `Job ${job.id} を実行中…`;
    void pollJob(job.id, status);
  } catch (error) {
    status.textContent = `受付に失敗しました (${error?.code || "unknown"})`;
  }
});

async function pollJob(id, statusNode) {
  for (let attempt = 0; attempt < 3600 && !disabled; attempt += 1) {
    let job;
    try { job = await workspaceCall("jobs.get", {job_id: id}); } catch { break; }
    statusNode.textContent = `${job.status} · ${Math.round(job.progress * 100)}% · ${job.phase || "-"}`;
    if (terminalStates.has(job.status)) {
      activeJobId = "";
      if (job.status === "succeeded") { await loadAssets(); activate("library"); }
      if (bridgePort) void callHost("host.notification.show", {title: "Media Forge", message: `Job ${job.status}`, level: job.status === "succeeded" ? "success" : "error", dedupe_key: id}).catch(() => {});
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  if (!disabled) statusNode.textContent = "状態確認がタイムアウトしました。Jobsから確認してください。";
}

async function loadAssets() {
  const grid = document.getElementById("asset-grid");
  let items;
  try { ({items} = await workspaceCall("assets.list")); } catch { grid.textContent = "Libraryを読み込めませんでした。"; return; }
  grid.replaceChildren();
  if (!items.length) { const p = document.createElement("p"); p.className = "muted"; p.textContent = "まだ素材はありません。"; grid.append(p); return; }
  for (const asset of items) {
    const card = document.createElement("article"); card.className = "asset-card";
    const image = document.createElement("img"); image.alt = asset.suggested_filename;
    try {
      const content = await workspaceCall("assets.content", {asset_id: asset.id});
      image.src = `data:${content.mime_type};base64,${content.base64}`;
    } catch { image.alt = `${asset.suggested_filename} (preview unavailable)`; }
    const title = document.createElement("strong"); title.textContent = asset.suggested_filename;
    const detail = document.createElement("p"); detail.textContent = `${asset.width}×${asset.height} · ${asset.id}`;
    const button = document.createElement("button"); button.textContent = "Provenance"; button.addEventListener("click", () => showProvenance(asset.id));
    card.append(image, title, detail, button); grid.append(card);
  }
}

async function loadJobs() {
  const list = document.getElementById("job-list");
  let items;
  try { ({items} = await workspaceCall("jobs.list")); } catch { list.textContent = "Jobsを読み込めませんでした。"; return; }
  list.replaceChildren();
  if (!items.length) { list.textContent = "Job履歴はありません。"; return; }
  items.forEach((job) => {
    const card = document.createElement("article"); card.className = "job-card";
    const info = document.createElement("div"); const title = document.createElement("strong"); title.textContent = job.request.intent;
    const detail = document.createElement("p"); detail.textContent = `${job.id} · ${job.phase || "-"}`; info.append(title, detail);
    const state = document.createElement("span"); state.className = "status"; state.textContent = job.status;
    card.append(info, state); list.append(card);
  });
}

async function loadModels() {
  const list = document.getElementById("model-list");
  let items;
  try { ({items} = await workspaceCall("models.list")); } catch { list.textContent = "Modelsを読み込めませんでした。"; return; }
  list.replaceChildren();
  if (!items.length) { list.textContent = "登録済みモデルはありません。"; return; }
  items.forEach((model) => {
    const card = document.createElement("article"); card.className = "info-card";
    const title = document.createElement("strong"); title.textContent = model.id;
    const state = document.createElement("p");
    state.textContent = `${model.state} · ${model.installed ? "installed" : "not installed"} · ${model.license}`;
    const capabilities = document.createElement("p"); capabilities.className = "muted";
    capabilities.textContent = model.capabilities.join(" · ");
    card.append(title, state, capabilities); list.append(card);
  });
}

async function showProvenance(id) {
  try {
    document.getElementById("provenance").textContent = JSON.stringify(await workspaceCall("assets.provenance", {asset_id: id}), null, 2);
    document.getElementById("provenance-dialog").showModal();
  } catch { /* bounded, visible library remains usable */ }
}

document.getElementById("close-dialog").addEventListener("click", () => document.getElementById("provenance-dialog").close());
document.getElementById("open-host-jobs").addEventListener("click", () => void callHost("host.route.open", {route: "/jobs"}).catch(() => {}));

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
      if (activeJobId) void workspaceCall("jobs.cancel", {job_id: activeJobId}).catch(() => {});
      activeJobId = "";
      setHostBusy(false);
    }
  };
  bridgePort.start();
  void connectWorkspaceSocket().then(() => {
    document.documentElement.dataset.bridge = "ready";
    document.getElementById("workspace").setAttribute("aria-busy", "false");
  }).catch(() => { document.documentElement.dataset.bridge = "error"; });
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
