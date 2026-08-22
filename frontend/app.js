/* Media Forge workspace.

   埋め込み iframe は allow-same-origin なしの opaque sandbox で動く。
   ブラウザ側の保存領域は一切使えないため、覚えておきたい値はすべて backend の
   preferences に置く。画像は /ws 経由の base64 で受け取る。
   （保存 API の名前をこのファイルに 1 度も書かないこと自体を試験で守っている） */

const TERMINAL = new Set(["succeeded", "failed", "canceled"]);
const VIEWS = ["create", "library", "activity", "settings"];

const PHASE_TEXT = {
  starting: "準備しています",
  normalize_request: "準備しています",
  validate_request: "準備しています",
  select_model: "使うモデルを選んでいます",
  waiting_resource: "GPU の空きを待っています",
  generating: "生成しています",
  postprocess: "仕上げています",
  semantic_review: "内容を確認しています",
  validate: "保証を検証しています",
  package: "保存しています",
  register_asset: "保存しています",
};

/* 操作は capability で出し分ける。ここが UI の可用性の唯一の根拠。 */
const EDIT_ACTIONS = [
  {mode: "inpaint", capability: "image.inpaint", label: "一部だけ直す",
   guarantee: "塗っていない場所は 1px も変わりません", preserving: true},
  {mode: "reference", capability: "image.single_reference_edit", label: "全体を直す",
   guarantee: "画像全体が変わることがあります"},
  {mode: "variation", capability: "image.variation", label: "似た別案を作る",
   guarantee: "画像全体が変わることがあります"},
  {mode: "outpaint", capability: "image.outpaint", label: "外側を広げる",
   guarantee: "元の画像は 1px も変わりません", preserving: true},
  {mode: "multi_reference", capability: "image.multi_reference_edit", label: "参考を足して直す",
   guarantee: "画像全体が変わることがあります"},
];

const CAPABILITY_REASON = {
  local_vlm_not_installed: "ローカルの確認用モデルが入っていません",
  model_not_installed: "使うモデルがまだ入っていません",
  capability_not_installed: "対応するモデルがありません",
  model_registry_invalid: "モデル一覧を読み込めません",
  planned_for_g7: "これからの対応予定です",
  planned_for_g9: "これからの対応予定です",
};

const LIBRARY_KINDS = [
  {id: "all", label: "すべて"},
  {id: "generated", label: "作ったもの"},
  {id: "edited", label: "直したもの"},
  {id: "imported", label: "取り込み"},
];

const state = {
  bridgePort: null,
  nonce: "",
  sequence: 0,
  disabled: false,
  hostBusy: false,
  visible: true,
  view: "create",
  mode: "simple",
  preferences: {},
  capabilities: {},
  envelope: null,
  presets: [],
  editMode: "",
  source: null,
  upload: null,
  sourceUrl: "",
  maskFile: null,
  maskPainted: 0,
  outpaintRatio: "source",
  outpaintScale: 1.5,
  estimateSec: null,
  activeJob: "",
  jobs: [],
  libraryCursor: null,
  libraryKind: "all",
  socket: null,
  socketReady: null,
  pending: new Map(),
};

const byId = (id) => document.getElementById(id);
const app = () => byId("app");

/* ── theme ────────────────────────────────────────────────────────────── */

function applyTheme(theme = {}) {
  const root = document.documentElement;
  const names = ["bg", "surface", "text", "border", "muted", "accent"];
  for (const name of names) {
    if (typeof theme[name] === "string") root.style.setProperty(`--${name}`, theme[name]);
  }
  if (typeof theme.surface === "string") root.style.setProperty("--sunk", theme.bg || theme.surface);
  if (theme.color_scheme) {
    root.style.colorScheme = theme.color_scheme;
    root.style.setProperty("--accent-ink", theme.color_scheme === "dark" ? "#0b1110" : "#ffffff");
  }
  if (typeof theme.radius_md === "number") root.style.setProperty("--radius", `${theme.radius_md}px`);
  if (theme.locale) root.lang = theme.locale;
  if (theme.safe_area) applySafeArea(theme.safe_area);
}

function applySafeArea(value = {}) {
  for (const side of ["top", "right", "bottom", "left"]) {
    if (Number.isFinite(value[side])) {
      document.documentElement.style.setProperty(`--safe-${side}`, `${value[side]}px`);
    }
  }
}

/* ── host bridge ──────────────────────────────────────────────────────── */

function callHost(method, params = {}) {
  if (!state.bridgePort) return Promise.reject({code: "bridge_unavailable"});
  return new Promise((resolve, reject) => {
    const id = `media-forge-host-${++state.sequence}`;
    const listener = (event) => {
      const message = event.data;
      if (message?.type !== "response" || message.id !== id) return;
      state.bridgePort.removeEventListener("message", listener);
      message.ok ? resolve(message.result) : reject(message.error);
    };
    state.bridgePort.addEventListener("message", listener);
    state.bridgePort.postMessage({id, method, params, session_nonce: state.nonce});
  });
}

/* host の「未保存」は離脱を警告する。Media Forge には保存の概念が無く、
   実行中の作業はサーバ側の job として残るので、入力しただけでは立てない。
   実際に失うものがある間（取り込み中・受付中）だけ立てる。 */
function setHostBusy(value) {
  if (!state.bridgePort || state.hostBusy === value) return;
  state.hostBusy = value;
  void callHost("host.busy.set", {busy: value}).catch(() => { state.hostBusy = !value; });
}

/* ── workspace transport ──────────────────────────────────────────────── */

function connectSocket() {
  if (state.socketReady) return state.socketReady;
  state.socketReady = new Promise((resolve, reject) => {
    const frameRoot = location.pathname.split("/").slice(0, 3).join("/");
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    state.socket = new WebSocket(`${scheme}://${location.host}${frameRoot}/ws`, [`control-deck-bridge.${state.nonce}`]);
    state.socket.onopen = () => resolve();
    state.socket.onerror = () => reject({code: "workspace_transport_unavailable"});
    state.socket.onclose = () => {
      for (const pending of state.pending.values()) pending.reject({code: "workspace_transport_closed"});
      state.pending.clear();
    };
    state.socket.onmessage = (event) => {
      let message;
      try { message = JSON.parse(event.data); } catch { return; }
      if (!message?.id) return handleEvent(message);
      const pending = state.pending.get(message.id);
      if (!pending) return;
      state.pending.delete(message.id);
      message.ok ? pending.resolve(message.result) : pending.reject(message.error);
    };
  });
  return state.socketReady;
}

function handleEvent(message) {
  if (message?.event !== "job.changed" || !message.data) return;
  const job = message.data;
  if (job.id === state.activeJob) showProgress(job);
  if (TERMINAL.has(job.status)) void finishJob(job);
}

async function standaloneCall(method, params) {
  const json = async (path, options = {}) => {
    const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
    if (!response.ok) throw {code: `http_${response.status}`};
    return response.json();
  };
  if (method === "jobs.create") return json("/api/v1/jobs", {method: "POST", body: JSON.stringify(params)});
  if (method === "jobs.get") return json(`/api/v1/jobs/${encodeURIComponent(params.job_id)}`);
  if (method === "jobs.cancel") return json(`/api/v1/jobs/${encodeURIComponent(params.job_id)}`, {method: "DELETE"});
  if (method === "jobs.list") return json("/api/v1/jobs");
  if (method === "jobs.watch" || method === "jobs.unwatch") return {watching: []};
  if (method === "models.list") return json("/api/v1/models");
  if (method === "assets.provenance") return json(`/api/v1/assets/${encodeURIComponent(params.asset_id)}/provenance`);
  if (method === "preferences.get") return {values: state.preferences};
  if (method === "preferences.set") return {values: {...state.preferences, ...params.values}};
  if (method === "capabilities.get") {
    const document_ = await json("/api/v1/capabilities");
    return {...document_, envelope: null, presets: []};
  }
  if (method === "library.list") {
    const {items} = await json("/api/v1/assets");
    return {items: items.map((asset) => ({
      asset_id: asset.id, width: asset.width, height: asset.height, mime_type: asset.mime_type,
      created_at: asset.created_at, kind: asset.parent_asset_ids.length ? "edited" : "generated",
      summary: asset.suggested_filename, parent_asset_ids: asset.parent_asset_ids,
    })), next_before: null};
  }
  if (method === "assets.thumbnail" || method === "assets.content") {
    const response = await fetch(`/api/v1/assets/${encodeURIComponent(params.asset_id)}/content`);
    if (!response.ok) throw {code: `http_${response.status}`};
    const bytes = new Uint8Array(await response.arrayBuffer());
    let binary = "";
    bytes.forEach((value) => { binary += String.fromCharCode(value); });
    return {mime_type: response.headers.get("content-type") || "image/png", base64: btoa(binary)};
  }
  if (method === "assets.import") {
    const binary = atob(params.base64);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
    const response = await fetch(`/api/v1/assets/import?purpose=${encodeURIComponent(params.purpose)}`, {
      method: "POST", headers: {"Content-Type": "application/octet-stream"}, body: bytes,
    });
    if (!response.ok) throw {code: `http_${response.status}`};
    return response.json();
  }
  throw {code: "workspace_method_unsupported"};
}

async function call(method, params = {}) {
  if (window.parent === window) return standaloneCall(method, params);
  await connectSocket();
  return new Promise((resolve, reject) => {
    const id = `media-forge-workspace-${++state.sequence}`;
    state.pending.set(id, {resolve, reject});
    state.socket.send(JSON.stringify({id, method, params}));
  });
}

/* ── mode / preferences ───────────────────────────────────────────────── */

function setMode(mode, {persist = true} = {}) {
  state.mode = mode === "advanced" ? "advanced" : "simple";
  app().dataset.mode = state.mode;
  byId("mode-simple").setAttribute("aria-pressed", String(state.mode === "simple"));
  byId("mode-advanced").setAttribute("aria-pressed", String(state.mode === "advanced"));
  mountAdvanced();
  if (persist) void savePreferences({mode: state.mode});
}

/* 詳細モードの断片は hidden にせず DOM から外す。
   タブ順とスクリーンリーダーを汚さず、テストが存在で検証できるようにするため。 */
function mountAdvanced() {
  for (const slot of document.querySelectorAll("[data-adv-slot]")) {
    slot.replaceChildren();
    if (state.mode !== "advanced") continue;
    const template = document.querySelector(`[data-adv-template="${slot.dataset.advSlot}"]`);
    if (template) slot.append(template.content.cloneNode(true));
  }
  if (state.mode !== "advanced") return;
  syncAdvancedCreate();
  void loadAdvancedSettings();
}

function syncAdvancedCreate() {
  const width = byId("advanced-width");
  if (!width) return;
  const preset = currentPreset();
  const envelope = sizeEnvelope();
  for (const input of [width, byId("advanced-height")]) {
    input.min = envelope.min_side;
    input.max = envelope.max_side;
    input.step = envelope.multiple_of;
  }
  width.value = preset.width;
  byId("advanced-height").value = preset.height;
  byId("advanced-count").value = selectedCount();
  byId("advanced-size-hint").textContent =
    `${envelope.min_side}〜${envelope.max_side}px・${envelope.multiple_of} の倍数（${
      state.envelope ? (envelope.envelope_source === "measured" ? "実測値" : "暫定値") : "暫定値"}）`;
  const semantic = state.capabilities["image.semantic_review"] || {};
  const check = byId("advanced-semantic");
  check.disabled = semantic.state !== "available";
  byId("advanced-semantic-reason").textContent = check.disabled
    ? CAPABILITY_REASON[semantic.reason] || "いま使えません"
    : "";
  byId("advanced-constraints").textContent = state.editMode
    ? `constraints.edit_mode = ${state.editMode}`
    : "constraints.width / height を直接指定できます";
}

async function savePreferences(values) {
  state.preferences = {...state.preferences, ...values};
  try { await call("preferences.set", {values}); } catch { /* 表示設定の保存失敗は操作を止めない */ }
}

/* ── views ────────────────────────────────────────────────────────────── */

function activate(name, {sync = true} = {}) {
  const view = VIEWS.includes(name) ? name : "create";
  state.view = view;
  app().dataset.view = view;
  for (const section of document.querySelectorAll(".view")) {
    section.hidden = section.dataset.view !== view;
  }
  for (const button of document.querySelectorAll("#shell-nav button")) {
    if (button.dataset.view === view) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  if (view === "library") void loadLibrary({reset: true});
  if (view === "activity") void loadActivity();
  if (view === "settings") void loadSettings();
  if (sync && state.bridgePort) {
    void callHost("host.route.sync", {path: view === "create" ? "/" : `/${view}`}).catch(() => {});
  }
  if (state.preferences.last_view !== view) void savePreferences({last_view: view});
}

/* ── create ───────────────────────────────────────────────────────────── */

/* よく使う比率。envelope に収まるよう長辺を basis に合わせて計算する。
   数値ではなく用途で選べることを優先し、正確な寸法はチップに併記する。 */
const RATIO_PRESETS = [
  {id: "square", label: "正方形", ratio: [1, 1]},
  {id: "landscape", label: "横長", ratio: [4, 3]},
  {id: "portrait", label: "縦長", ratio: [3, 4]},
  {id: "wide", label: "ワイド", ratio: [16, 9]},
  {id: "tall", label: "縦ワイド", ratio: [9, 16]},
  {id: "cinema", label: "シネマ", ratio: [21, 9]},
];

function ratioSize(ratio) {
  const envelope = sizeEnvelope();
  const multiple = envelope.multiple_of;
  const [long, short] = ratio[0] >= ratio[1] ? ratio : [ratio[1], ratio[0]];
  const longSide = envelope.max_side;
  const shortSide = Math.max(envelope.min_side, (longSide * short) / long);
  const snap = (value) => Math.max(multiple, Math.round(value / multiple) * multiple);
  return ratio[0] >= ratio[1]
    ? {width: snap(longSide), height: snap(shortSide)}
    : {width: snap(shortSide), height: snap(longSide)};
}

function renderPresets() {
  const holder = byId("size-presets");
  const chosen = state.preferences.last_preset || "square";
  const chips = RATIO_PRESETS.map((preset) => {
    const size = ratioSize(preset.ratio);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.dataset.preset = preset.id;
    button.dataset.width = size.width;
    button.dataset.height = size.height;
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", String(preset.id === chosen));
    button.textContent = `${preset.label} ${size.width}×${size.height}`;
    return button;
  });
  const custom = document.createElement("button");
  custom.type = "button";
  custom.className = "chip";
  custom.id = "preset-custom";
  custom.dataset.preset = "custom";
  custom.setAttribute("role", "radio");
  custom.setAttribute("aria-checked", String(chosen === "custom"));
  custom.textContent = "カスタム";
  chips.push(custom);
  holder.replaceChildren(...chips);
  renderCustomRatios();
  syncCustomVisibility();
}

/* カスタムでも比率だけは選べるようにする。数値を両方入れ直す手間を無くす。 */
function renderCustomRatios() {
  const holder = byId("custom-ratios");
  if (!holder) return;
  holder.replaceChildren(...RATIO_PRESETS.map((preset) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.dataset.customRatio = preset.ratio.join(":");
    button.textContent = preset.label;
    return button;
  }));
}

function syncCustomVisibility() {
  const chosen = byId("size-presets").querySelector('[aria-checked="true"]');
  const custom = chosen?.dataset.preset === "custom";
  byId("size-custom").hidden = !custom;
  if (!custom) return;
  const width = byId("custom-width");
  if (!width.value) {
    const envelope = sizeEnvelope();
    width.value = Number(state.preferences.last_custom_width) || envelope.max_side;
    byId("custom-height").value = Number(state.preferences.last_custom_height) || envelope.max_side;
  }
  const envelope = sizeEnvelope();
  for (const input of [width, byId("custom-height")]) {
    input.min = envelope.min_side;
    input.max = envelope.max_side;
    input.step = envelope.multiple_of;
  }
  byId("size-note").textContent =
    `${envelope.min_side}〜${envelope.max_side}px・${envelope.multiple_of} の倍数で指定してください。`;
}

function renderCounts() {
  const holder = byId("count-chips");
  const chosen = Number(state.preferences.last_count || 1);
  holder.replaceChildren(...[1, 2, 3, 4].map((value) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.dataset.count = value;
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", String(value === chosen));
    button.textContent = String(value);
    return button;
  }));
}

function currentPreset() {
  const chosen = byId("size-presets").querySelector('[aria-checked="true"]');
  if (chosen?.dataset.preset === "custom") {
    const envelope = sizeEnvelope();
    return {
      id: "custom",
      width: Number(byId("custom-width").value) || envelope.max_side,
      height: Number(byId("custom-height").value) || envelope.max_side,
    };
  }
  return {
    id: chosen?.dataset.preset || "square",
    width: Number(chosen?.dataset.width || 512),
    height: Number(chosen?.dataset.height || 512),
  };
}

function selectedCount() {
  const chosen = byId("count-chips").querySelector('[aria-checked="true"]');
  return Number(chosen?.dataset.count || 1);
}

function capabilityState(name) {
  return state.capabilities[name]?.state || "unavailable";
}

function renderEditActions() {
  const holder = byId("edit-actions");
  const advanced = state.mode === "advanced";
  const usable = EDIT_ACTIONS.filter((action) => advanced || capabilityState(action.capability) !== "unavailable");
  holder.replaceChildren(...usable.map((action) => {
    const available = capabilityState(action.capability) !== "unavailable";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "edit-action";
    button.dataset.editMode = action.mode;
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", String(state.editMode === action.mode));
    button.disabled = !available;
    const dot = document.createElement("span");
    dot.className = "dot";
    const label = document.createElement("span");
    label.textContent = action.label;
    button.append(dot, label);
    if (!available) {
      const why = document.createElement("span");
      why.className = "why";
      why.textContent = CAPABILITY_REASON[state.capabilities[action.capability]?.reason] || "いま使えません";
      button.append(why);
    }
    if (capabilityState(action.capability) === "experimental") {
      const why = document.createElement("span");
      why.className = "why";
      why.textContent = "試験中";
      button.append(why);
    }
    return button;
  }));
  if (!usable.some((action) => action.mode === state.editMode)) selectEditMode(usable[0]?.mode || "");
  else selectEditMode(state.editMode);
}

/* 生成と outpaint 以外はサイズが結果に影響しない（出力は元画像と同じ寸法）。
   選ばせた値が無視される状態を作らないため、欄ごと隠して理由を書く。 */
function renderSizeSection() {
  const block = byId("size-block");
  const label = byId("size-label");
  const note = byId("size-note");
  if (!state.source) {
    block.hidden = false;
    label.textContent = "サイズ";
    note.textContent = "";
    return;
  }
  // outpaint の寸法は「広げ方」から決まる。詳細モードでだけ数値を触らせる。
  block.hidden = state.editMode !== "outpaint" || state.mode !== "advanced";
  if (!block.hidden) {
    label.textContent = "広げる先の大きさ";
    note.textContent = outpaintProblem(currentPreset()) || "";
    return;
  }
  label.textContent = "サイズ";
  note.textContent = "";
}

function outpaintProblem(target) {
  const source = state.source;
  if (!source) return "";
  if (target.width < source.width || target.height < source.height) {
    return "元画像より小さくはできません。";
  }
  if (target.width === source.width && target.height === source.height) {
    return "少なくとも片方の辺を大きくしてください。";
  }
  return validateSize(target);
}

function selectEditMode(mode) {
  state.editMode = mode;
  for (const button of document.querySelectorAll(".edit-action")) {
    button.setAttribute("aria-checked", String(button.dataset.editMode === mode));
  }
  const action = EDIT_ACTIONS.find((item) => item.mode === mode);
  byId("guarantee-badge").textContent = action ? action.guarantee : "";
  byId("mask-input").hidden = mode !== "inpaint";
  byId("reference-input").hidden = mode !== "multi_reference";
  byId("reference-files").required = mode === "multi_reference";
  byId("outpaint-input").hidden = mode !== "outpaint";
  if (mode === "outpaint") renderOutpaintControls();
  if (mode !== "inpaint") maskReset();
  mountAdvanced();
  renderSizeSection();
  clearError();
  if (state.mode === "advanced") syncAdvancedCreate();
}

function attachedFile() {
  return byId("source-file").files[0] || null;
}

/* 寸法はアップロード前にブラウザ側で測る。
   これが無いと「外側を広げる」の可否が GPU 受付後にしか分からない。 */
async function measure(file) {
  try {
    const bitmap = await createImageBitmap(file);
    const size = {width: bitmap.width, height: bitmap.height};
    bitmap.close();
    return size;
  } catch { return null; }
}

/* 端末の写真は 12 メガピクセル級で、取り込みの画素数上限（2048×2048）を超える。
   出力はどのみち envelope に収まる寸法なので、送る前にここで縮める。
   これをしないと「大きすぎます」で落ちるか、無駄に長いアップロードになる。 */
function fitToEnvelope(width, height) {
  const envelope = sizeEnvelope();
  const multiple = envelope.multiple_of;
  const limit = Math.min(envelope.max_side, 2048);
  const scale = Math.min(1, limit / Math.max(width, height));
  const round = (value) => {
    const bounded = Math.max(envelope.min_side, Math.round(value * scale));
    return Math.max(multiple, Math.round(bounded / multiple) * multiple);
  };
  return {width: round(width), height: round(height)};
}

function needsResize(size) {
  const target = fitToEnvelope(size.width, size.height);
  return target.width !== size.width || target.height !== size.height;
}

async function resized(file, size) {
  const target = fitToEnvelope(size.width, size.height);
  const bitmap = await createImageBitmap(file);
  const canvas = document.createElement("canvas");
  canvas.width = target.width;
  canvas.height = target.height;
  const context = canvas.getContext("2d");
  context.imageSmoothingQuality = "high";
  context.drawImage(bitmap, 0, 0, target.width, target.height);
  bitmap.close();
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
  return {file: new File([blob], "source.png", {type: "image/png"}), size: target};
}

async function refreshAttachment() {
  const file = attachedFile();
  const zone = byId("attach-image");
  zone.classList.toggle("filled", Boolean(file));
  byId("attach-label").textContent = file ? `画像: ${file.name}` : "＋ 画像を追加";
  byId("attach-clear").hidden = !file;
  byId("edit-block").hidden = !file;
  if (!file) maskReset();
  state.upload = null;
  const measured = file ? await measure(file) : null;
  if (file && measured && needsResize(measured)) {
    byId("attach-size").textContent = "読み込んでいます…";
    const prepared = await resized(file, measured);
    state.upload = prepared.file;
    state.source = prepared.size;
    byId("attach-size").textContent =
      `${measured.width}×${measured.height} → ${prepared.size.width}×${prepared.size.height} に縮小して使います`;
  } else {
    state.upload = file;
    state.source = measured;
    byId("attach-size").textContent = measured ? `${measured.width}×${measured.height}` : "";
  }
  if (file) renderEditActions();
  else selectEditMode("");
  renderSizeSection();
  clearError();
}

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

async function importFile(file, purpose, onProgress) {
  if (!file || file.size < 1 || file.size > 64 * 1024 * 1024) throw {code: "invalid_import_size"};
  if (window.parent === window) return call("assets.import", {purpose, base64: await fileBase64(file)});
  const upload = await call("assets.import.begin", {purpose, size: file.size});
  for (let offset = 0; offset < file.size; offset += upload.chunk_bytes) {
    const slice = file.slice(offset, Math.min(file.size, offset + upload.chunk_bytes));
    await call("assets.import.chunk", {upload_id: upload.upload_id, offset, base64: await fileBase64(slice)});
    if (onProgress) onProgress(Math.min(1, (offset + slice.size) / file.size));
  }
  return call("assets.import.commit", {upload_id: upload.upload_id});
}

function maskAsset() {
  const chosen = byId("mask-file");
  return state.maskFile || (chosen && chosen.files[0]) || null;
}

function buildConstraints(preset) {
  const constraints = {width: preset.width, height: preset.height};
  if (state.editMode === "outpaint" && state.mode !== "advanced") {
    const target = outpaintTarget();
    if (target) return target;
  }
  if (state.mode === "advanced" && byId("advanced-width")) {
    constraints.width = Number(byId("advanced-width").value) || preset.width;
    constraints.height = Number(byId("advanced-height").value) || preset.height;
  }
  return constraints;
}

const FALLBACK_ENVELOPE = {min_side: 256, max_side: 1024, multiple_of: 16};

/* envelope が取れなくても検証を止めない。止めると「16 の倍数」の規則が
   受付後にしか効かなくなり、待たせてから落とすことになる。 */
function sizeEnvelope() {
  return state.envelope || FALLBACK_ENVELOPE;
}

function validateSize(constraints) {
  const envelope = sizeEnvelope();
  for (const side of [constraints.width, constraints.height]) {
    if (side % envelope.multiple_of !== 0) return `幅と高さは ${envelope.multiple_of} の倍数にしてください`;
    if (side < envelope.min_side || side > envelope.max_side) {
      return `幅と高さは ${envelope.min_side}〜${envelope.max_side}px にしてください`;
    }
  }
  return "";
}

function showError(message, exit) {
  const node = byId("create-error");
  node.replaceChildren();
  node.hidden = !message;
  if (!message) return;
  const text = document.createElement("span");
  text.textContent = message;
  node.append(text);
  if (!exit) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "exit";
  button.dataset.exitAction = exit.action;
  if (exit.jobId) button.dataset.exitJob = exit.jobId;
  button.textContent = exit.exit;
  node.append(button);
}

function clearError() {
  showError("");
}

/* GPU を取りに行く前に落とせるものはすべてここで落とす。
   backend も同じ規則で fail-closed するが、受付後に落ちると待ち時間が無駄になる。 */
function requestProblem(constraints) {
  const file = attachedFile();
  if (!byId("create-intent").value.trim()) return "作りたいものを書いてください。";

  if (state.mode === "advanced" && byId("advanced-policy")) {
    if (byId("advanced-policy").value === "manual" && !byId("advanced-model").value) {
      return "manual を選んだときはモデルを指定してください。";
    }
  }

  if (!file) return validateSize(constraints);

  if (!state.editMode) return "この画像をどうするか選んでください。";
  if (state.editMode === "inpaint" && !maskAsset()) {
    return "変えたい場所を塗ってください。";
  }
  if (state.editMode === "multi_reference") {
    const count = byId("reference-files").files.length;
    if (count < 1 || count > 3) return "参考にする画像は 1〜3 枚にしてください。";
  }
  if (state.editMode === "outpaint") {
    const problem = outpaintProblem(constraints);
    if (problem) return problem;
  }
  return "";
}

async function submitJob(event) {
  event.preventDefault();
  if (state.disabled) return;
  const status = byId("create-status");
  const submit = byId("create-submit");
  const preset = currentPreset();
  const constraints = buildConstraints(preset);
  const problem = requestProblem(constraints);
  if (problem) { showError(problem); return; }
  clearError();

  submit.disabled = true;
  submit.textContent = "実行中…";
  status.textContent = "";
  setHostBusy(true);
  showPreparing("受け付けています", 0.05);
  try {
    const file = attachedFile();
    const operation = file ? "image.edit" : "image.generate";
    let inputs = [];
    if (file) {
      showPreparing("画像を取り込んでいます", 0.15);
      const source = await importFile(state.upload || file, "source", (ratio) => {
        showPreparing("画像を取り込んでいます", 0.15 + ratio * 0.35);
      });
      inputs = [{asset_id: source.id}];
      const preserving = state.editMode === "inpaint" || state.editMode === "outpaint";
      if (state.editMode !== "outpaint") {
        constraints.width = source.width;
        constraints.height = source.height;
      } else if (source.width > constraints.width || source.height > constraints.height) {
        // 添付時の計測とサーバの正規化がずれた場合の保険。受付前に止める。
        throw {code: "invalid_dimensions"};
      }
      constraints.strict_edit = preserving;
      constraints.edit_mode = state.editMode;
      if (state.editMode === "inpaint") {
        showPreparing("塗った範囲を取り込んでいます", 0.55);
        const imported = await importFile(maskAsset(), "edit_mask");
        constraints.editable_mask_asset_id = imported.id;
      }
      if (state.editMode === "multi_reference") {
        const files = Array.from(byId("reference-files").files);
        showPreparing("参考画像を取り込んでいます", 0.6);
        for (const reference of files) {
          inputs.push({asset_id: (await importFile(reference, "source")).id});
        }
      }
    }

    const request = {
      operation,
      intent: byId("create-intent").value,
      inputs,
      constraints,
      output: {format: outputFormat(), count: requestedCount()},
      qa: qaOptions(),
      local_only: true,
      ...modelSelection(),
    };
    showPreparing("受け付けています", 0.7);
    const job = await call("jobs.create", request);
    setHostBusy(false);
    state.activeJob = job.id;
    await call("jobs.watch", {job_ids: [job.id]}).catch(() => {});
    showProgress(job);
    status.textContent = "";
    void savePreferences({last_preset: preset.id, last_count: selectedCount()});
    if (window.parent === window) void pollJob(job.id);
  } catch (error) {
    status.textContent = "";
    showError(failureText(error?.code));
    hidePreparing();
  } finally {
    setHostBusy(false);
    submit.disabled = false;
    submit.textContent = "作る";
  }
}

function outputFormat() {
  return state.mode === "advanced" && byId("advanced-format") ? byId("advanced-format").value : "png";
}

function requestedCount() {
  if (state.mode === "advanced" && byId("advanced-count")) {
    return Math.min(8, Math.max(1, Number(byId("advanced-count").value) || 1));
  }
  return selectedCount();
}

function qaOptions() {
  if (state.mode !== "advanced" || !byId("advanced-semantic")) return {};
  return {
    semantic: byId("advanced-semantic").checked,
    max_regeneration_attempts: Math.min(3, Math.max(0, Number(byId("advanced-attempts").value) || 0)),
  };
}

function modelSelection() {
  if (state.mode !== "advanced" || !byId("advanced-policy")) return {};
  const policy = byId("advanced-policy").value;
  if (policy !== "manual") return {model_policy: policy};
  return {model_policy: "manual", model_id: byId("advanced-model").value};
}

/* standalone では push が無いので、そこだけ従来どおり問い合わせる */
async function pollJob(id) {
  for (let attempt = 0; attempt < 3600 && !state.disabled; attempt += 1) {
    let job;
    try { job = await call("jobs.get", {job_id: id}); } catch { return; }
    showProgress(job);
    if (TERMINAL.has(job.status)) return finishJob(job);
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

/* job になる前の待ち時間も進捗として見せる。
   モバイルではステージが画面外にあり、ミニバーだけが手掛かりになる。 */
function showPreparing(text, ratio) {
  byId("stage-progress").hidden = false;
  byId("mini-progress").hidden = false;
  byId("progress-phase").textContent = text;
  byId("mini-phase").textContent = text;
  const percent = `${Math.round(ratio * 100)}%`;
  byId("progress-bar").style.width = percent;
  byId("mini-bar").style.width = percent;
  byId("progress-detail").textContent = "";
}

function hidePreparing() {
  if (state.activeJob) return;
  byId("stage-progress").hidden = true;
  byId("mini-progress").hidden = true;
}

function showProgress(job) {
  const running = !TERMINAL.has(job.status);
  byId("stage-progress").hidden = !running;
  byId("mini-progress").hidden = !running;
  const percent = Math.round((job.progress || 0) * 100);
  const phase = PHASE_TEXT[job.phase] || (job.status === "queued" ? "順番を待っています" : "実行しています");
  byId("progress-phase").textContent = phase;
  byId("mini-phase").textContent = phase;
  byId("progress-bar").style.width = `${percent}%`;
  byId("mini-bar").style.width = `${percent}%`;
  byId("progress-detail").textContent = state.mode === "advanced"
    ? `${job.status} · ${percent}% · ${job.phase || "-"} · ${job.id}`
    : `${percent}%`;
  updateActivityBadge(running ? 1 : 0);
}

async function finishJob(job) {
  if (state.activeJob !== job.id) return;
  state.activeJob = "";
  byId("stage-progress").hidden = true;
  byId("mini-progress").hidden = true;
  updateActivityBadge(0);
  if (job.status === "succeeded" && job.asset_ids.length) {
    await showResult(job.asset_ids);
    await loadRecent();
  } else if (job.status === "failed") {
    const detail = failure(job.error?.code);
    state.jobs = [job, ...state.jobs.filter((item) => item.id !== job.id)];
    showError(detail.text, {...detail, jobId: job.id});
  } else if (job.status === "canceled") {
    byId("create-status").textContent = "中止しました。";
  }
  if (state.bridgePort && !state.visible) {
    void callHost("host.notification.show", {
      title: "Media Forge",
      message: job.status === "succeeded" ? "できあがりました" : failureText(job.error?.code),
      level: job.status === "succeeded" ? "success" : "error",
      dedupe_key: job.id,
    }).catch(() => {});
  }
}

/* 失敗は「何が起きたか」と「次に何ができるか」を必ず対にする。
   exit は job があるときだけ意味を持つものと、いつでも押せるものがある。 */
const FAILURES = {
  invalid_edit_mask: {
    text: "変えたい場所が指定されていません。",
    exit: "もう一度やる", action: "rerun",
  },
  strict_edit_invariant_failed: {
    text: "守るはずの部分が変わってしまったため、結果を破棄しました。",
    exit: "もう一度やる", action: "rerun",
  },
  outpaint_invariant_failed: {
    text: "元の画像を保ったまま広げられませんでした。",
    exit: "広げる量を減らす", action: "open_create",
  },
  semantic_review_exhausted: {
    text: "指示どおりの結果になりませんでした。",
    exit: "指示を書き直す", action: "edit_intent",
  },
  semantic_review_unavailable: {
    text: "内容の自動チェックはいま使えません。",
    exit: "チェックなしで作る", action: "rerun_without_review",
  },
  resource_unavailable: {
    text: "GPU の空きを確保できませんでした。",
    exit: "もう一度やる", action: "rerun",
  },
  host_lease_required: {
    text: "GPU の空きを確保できませんでした。",
    exit: "もう一度やる", action: "rerun",
  },
  worker_timeout: {
    text: "時間内に終わりませんでした。",
    exit: "小さくしてやり直す", action: "open_create",
  },
  worker_crash: {
    text: "処理が途中で止まりました。サービスの再起動などで中断されたときに起きます。",
    exit: "もう一度やる", action: "rerun",
  },
  service_restarted: {
    text: "サービスが再起動したため中断しました。",
    exit: "もう一度やる", action: "rerun",
  },
  host_context_lost: {
    text: "サービスが再起動したため中断しました。",
    exit: "もう一度やる", action: "rerun",
  },
  capability_unavailable: {
    text: "この操作はいま使えません。",
    exit: "できることを見る", action: "open_settings",
  },
  model_unavailable: {
    text: "使えるモデルがありません。",
    exit: "できることを見る", action: "open_settings",
  },
  invalid_dimensions: {
    text: "指定した大きさが使えません。",
    exit: "サイズを選び直す", action: "open_create",
  },
  invalid_reference_count: {
    text: "参考にする画像は 1〜3 枚にしてください。",
    exit: "選び直す", action: "open_create",
  },
  invalid_import_size: {text: "この画像は取り込めません。", exit: "別の画像を選ぶ", action: "open_create"},
  invalid_image_import: {text: "この画像は取り込めません。", exit: "別の画像を選ぶ", action: "open_create"},
  asset_import_too_large: {text: "この画像は大きすぎます。", exit: "別の画像を選ぶ", action: "open_create"},
};

const UNKNOWN_FAILURE = {
  text: "うまくいきませんでした。",
  exit: "もう一度やる",
  action: "rerun",
};

function failure(code) {
  return FAILURES[code] || UNKNOWN_FAILURE;
}

function failureText(code) {
  return failure(code).text;
}

/* 同じ設定でもう一度。素材は取り込み済みなので送り直すだけで済む。 */
async function rerun(job, {withoutReview = false} = {}) {
  if (!job) return;
  const request = JSON.parse(JSON.stringify(job.request));
  if (withoutReview) request.qa = {...(request.qa || {}), semantic: false};
  try {
    const created = await call("jobs.create", request);
    state.activeJob = created.id;
    await call("jobs.watch", {job_ids: [created.id]}).catch(() => {});
    showProgress(created);
    activate("create");
    clearError();
    if (window.parent === window) void pollJob(created.id);
  } catch (error) {
    showError(failureText(error?.code));
    activate("create");
  }
}

/* 失敗行の出口。押した先で必ず次の操作ができる状態にする。 */
function runExit(action, job) {
  if (action === "rerun") return void rerun(job);
  if (action === "rerun_without_review") return void rerun(job, {withoutReview: true});
  if (action === "open_settings") return activate("settings");
  if (action === "edit_intent") {
    activate("create");
    if (job) byId("create-intent").value = job.request.intent;
    byId("create-intent").focus();
    return;
  }
  activate("create");
  if (job) byId("create-intent").value = job.request.intent;
}

async function showResult(assetIds) {
  const stage = byId("stage-result");
  stage.hidden = false;
  const strip = byId("candidate-strip");
  strip.replaceChildren();
  await showAsset(assetIds[0]);
  if (assetIds.length < 2) return;
  for (const assetId of assetIds) {
    const button = await thumbnailButton(assetId, () => void showAsset(assetId));
    strip.append(button);
  }
}

async function showAsset(assetId) {
  try {
    const content = await call("assets.content", {asset_id: assetId});
    const image = byId("result-image");
    image.src = `data:${content.mime_type};base64,${content.base64}`;
    image.dataset.assetId = assetId;
  } catch { /* 表示できなくても以降の操作は続けられる */ }
}

async function thumbnailButton(assetId, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "thumb";
  button.dataset.assetId = assetId;
  const image = document.createElement("img");
  image.alt = "";
  image.width = 84;
  image.height = 84;
  button.append(image);
  button.addEventListener("click", onClick);
  try {
    const thumbnail = await call("assets.thumbnail", {asset_id: assetId, max_side: 192});
    image.src = `data:${thumbnail.mime_type};base64,${thumbnail.base64}`;
  } catch { button.textContent = "?"; }
  return button;
}

/* 実測が無いモデルしか無いときは何も出さない。推測を出さないため。

   registry が持つ measured_runtime_sec は初回実行（モデル読み込みと
   カーネルコンパイルを含む）の実測であり、暖まった後の所要時間ではない。
   一般的な目安として出すと大きく外れるので、何の数字かを明示する。 */
async function loadEstimate() {
  const node = byId("create-estimate");
  node.textContent = "";
  try {
    const {items} = await call("models.list");
    const measured = items
      .filter((model) => model.installed && model.healthy && model.measurement_confidence === "measured")
      .map((model) => model.measured_runtime_sec)
      .filter((value) => typeof value === "number" && value > 0);
    if (!measured.length) return;
    state.estimateSec = Math.min(...measured);
    node.textContent =
      `初回は約 ${Math.round(state.estimateSec)} 秒（モデルの読み込みを含む実測）。2 回目以降は短くなります。`;
  } catch { /* 目安が出せなくても作成はできる */ }
}

async function loadRecent() {
  let items = [];
  try { ({items} = await call("library.list", {limit: 4})); } catch { return; }
  const strip = byId("recent-strip");
  strip.replaceChildren();
  byId("recent-empty").hidden = items.length > 0;
  for (const item of items) {
    strip.append(await thumbnailButton(item.asset_id, () => {
      activate("library");
    }));
  }
}

/* ── マスク編集 ───────────────────────────────────────────────────────── */

/* 塗った所を「変えてよい場所」として扱う。出力は元画像と同寸法の PNG で、
   塗った所が白、それ以外が黒。backend の strict edit がこの規則で保護する。 */
const MASK_HINT = "指やマウスで塗ってください。2 本指または Ctrl+ホイールで拡大できます。";

const mask = {
  canvas: null,
  context: null,
  history: [],
  erasing: false,
  drawing: false,
  pointers: new Map(),
  pinch: 0,
  scale: 1,
};

function maskOpen() {
  const file = state.upload || attachedFile();
  if (!file || !state.source) return;
  const dialog = byId("mask-dialog");
  mask.canvas = byId("mask-canvas");
  mask.canvas.width = state.source.width;
  mask.canvas.height = state.source.height;
  mask.context = mask.canvas.getContext("2d", {willReadFrequently: true});
  mask.history = [];
  mask.scale = 1;
  byId("mask-canvas-wrap").style.transform = "scale(1)";
  setMaskTool(false);

  byId("mask-hint").textContent = MASK_HINT;
  const width = byId("mask-width");
  width.value = Math.max(8, Math.min(256, Math.round(Math.min(state.source.width, state.source.height) * 0.04)));

  if (state.sourceUrl) URL.revokeObjectURL(state.sourceUrl);
  state.sourceUrl = URL.createObjectURL(file);
  byId("mask-source").src = state.sourceUrl;

  if (state.maskFile) {
    const image = new Image();
    image.onload = () => {
      mask.context.drawImage(image, 0, 0, mask.canvas.width, mask.canvas.height);
      URL.revokeObjectURL(image.src);
    };
    image.src = URL.createObjectURL(state.maskFile);
  }
  dialog.showModal();
}

function setMaskTool(erasing) {
  mask.erasing = erasing;
  byId("mask-brush").setAttribute("aria-pressed", String(!erasing));
  byId("mask-eraser").setAttribute("aria-pressed", String(erasing));
}

function maskPoint(event) {
  const rect = mask.canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * mask.canvas.width,
    y: ((event.clientY - rect.top) / rect.height) * mask.canvas.height,
  };
}

function maskSnapshot() {
  mask.history.push(mask.context.getImageData(0, 0, mask.canvas.width, mask.canvas.height));
  if (mask.history.length > 8) mask.history.shift();
}

function maskStroke(from, to) {
  const context = mask.context;
  context.save();
  context.globalCompositeOperation = mask.erasing ? "destination-out" : "source-over";
  context.strokeStyle = "#ffffff";
  context.lineCap = "round";
  context.lineJoin = "round";
  context.lineWidth = Number(byId("mask-width").value);
  context.beginPath();
  context.moveTo(from.x, from.y);
  context.lineTo(to.x, to.y);
  context.stroke();
  context.restore();
}

function maskPointerDown(event) {
  mask.pointers.set(event.pointerId, event);
  if (mask.pointers.size === 2) {
    mask.drawing = false;
    mask.pinch = pointerDistance();
    return;
  }
  if (mask.pointers.size > 2) return;
  mask.canvas.setPointerCapture(event.pointerId);
  byId("mask-hint").textContent = MASK_HINT;
  maskSnapshot();
  mask.drawing = true;
  mask.last = maskPoint(event);
  maskStroke(mask.last, mask.last);
}

function pointerDistance() {
  const [first, second] = [...mask.pointers.values()];
  return Math.hypot(first.clientX - second.clientX, first.clientY - second.clientY);
}

function maskPointerMove(event) {
  if (!mask.pointers.has(event.pointerId)) return;
  mask.pointers.set(event.pointerId, event);
  if (mask.pointers.size === 2 && mask.pinch) {
    const ratio = pointerDistance() / mask.pinch;
    mask.scale = Math.max(1, Math.min(6, mask.scale * ratio));
    mask.pinch = pointerDistance();
    byId("mask-canvas-wrap").style.transform = `scale(${mask.scale})`;
    return;
  }
  if (!mask.drawing) return;
  const point = maskPoint(event);
  maskStroke(mask.last, point);
  mask.last = point;
}

function maskPointerUp(event) {
  mask.pointers.delete(event.pointerId);
  if (mask.pointers.size < 2) mask.pinch = 0;
  if (mask.pointers.size === 0) mask.drawing = false;
}

function maskPaintedPixels() {
  const data = mask.context.getImageData(0, 0, mask.canvas.width, mask.canvas.height).data;
  let painted = 0;
  for (let index = 3; index < data.length; index += 4) if (data[index] > 0) painted += 1;
  return painted;
}

/* 空マスクと全面マスクは backend が受付前に落とす。同じ規則を UI でも見せる。 */
function maskProblem(painted, total) {
  if (painted === 0) return "変えたい場所を塗ってください。";
  if (painted >= total) return "全部を塗ると「一部だけ直す」になりません。塗る範囲を減らすか、別の操作を選んでください。";
  return "";
}

async function maskApply() {
  const total = mask.canvas.width * mask.canvas.height;
  const painted = maskPaintedPixels();
  const problem = maskProblem(painted, total);
  if (problem) { byId("mask-hint").textContent = problem; return; }

  // 出力は白（変える）/ 黒（保護）の 2 値。表示用の半透明は持ち込まない。
  const output = document.createElement("canvas");
  output.width = mask.canvas.width;
  output.height = mask.canvas.height;
  const context = output.getContext("2d");
  context.fillStyle = "#000000";
  context.fillRect(0, 0, output.width, output.height);
  context.drawImage(mask.canvas, 0, 0);

  const blob = await new Promise((resolve) => output.toBlob(resolve, "image/png"));
  state.maskFile = new File([blob], "mask.png", {type: "image/png"});
  state.maskPainted = painted;
  byId("mask-preview").src = URL.createObjectURL(state.maskFile);
  byId("mask-preview").hidden = false;
  byId("mask-state").textContent =
    `${painted.toLocaleString()} ピクセルを変更対象にしました（全体の ${((painted / total) * 100).toFixed(1)}%）。`;
  byId("mask-draw").textContent = "塗り直す";
  byId("mask-dialog").close();
  clearError();
}

function maskReset() {
  state.maskFile = null;
  state.maskPainted = 0;
  byId("mask-preview").hidden = true;
  byId("mask-state").textContent = "まだ塗っていません。";
  byId("mask-draw").textContent = "変えたい場所を塗る";
}

/* ── 外側を広げる ─────────────────────────────────────────────────────── */

const OUTPAINT_RATIOS = [
  {id: "source", label: "元のまま"},
  {id: "16:9", label: "16:9", value: 16 / 9},
  {id: "1:1", label: "正方形", value: 1},
  {id: "9:16", label: "9:16", value: 9 / 16},
];
const OUTPAINT_SCALES = [1.25, 1.5, 2];

function renderOutpaintControls() {
  byId("outpaint-ratios").replaceChildren(...OUTPAINT_RATIOS.map((ratio) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.dataset.ratio = ratio.id;
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", String(ratio.id === state.outpaintRatio));
    button.textContent = ratio.label;
    return button;
  }));
  byId("outpaint-scales").replaceChildren(...OUTPAINT_SCALES.map((scale) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.dataset.scale = String(scale);
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", String(scale === state.outpaintScale));
    button.textContent = `${scale}倍`;
    return button;
  }));
  renderOutpaintPreview();
}

/* 元画像は必ず中央に置かれる（backend の outpaint_plan）。
   片側だけ広げる操作は作らない。 */
function outpaintTarget() {
  const source = state.source;
  if (!source) return null;
  const envelope = sizeEnvelope();
  const multiple = envelope.multiple_of;
  const ratio = OUTPAINT_RATIOS.find((item) => item.id === state.outpaintRatio);
  const area = Math.max(source.width, source.height) * state.outpaintScale;
  let width = area;
  let height = area;
  if (ratio?.value) {
    if (ratio.value >= 1) height = area / ratio.value;
    else width = area * ratio.value;
  } else {
    width = source.width * state.outpaintScale;
    height = source.height * state.outpaintScale;
  }
  const round = (value, floor) => {
    const bounded = Math.min(envelope.max_side, Math.max(floor, envelope.min_side, value));
    return Math.ceil(bounded / multiple) * multiple;
  };
  return {width: round(width, source.width), height: round(height, source.height)};
}

function renderOutpaintPreview() {
  const target = outpaintTarget();
  const note = byId("outpaint-note");
  const box = byId("outpaint-source");
  if (!target || !state.source) { note.textContent = ""; return; }
  const frame = 116;
  const scale = frame / Math.max(target.width, target.height);
  byId("outpaint-preview").style.width = `${Math.round(target.width * scale)}px`;
  byId("outpaint-preview").style.height = `${Math.round(target.height * scale)}px`;
  box.style.width = `${Math.round(state.source.width * scale)}px`;
  box.style.height = `${Math.round(state.source.height * scale)}px`;
  const problem = outpaintProblem(target);
  note.textContent = problem
    ? problem
    : `${state.source.width}×${state.source.height} を中央に置いて ${target.width}×${target.height} へ広げます。`;
}

/* ── library ──────────────────────────────────────────────────────────── */

function renderLibraryKinds() {
  const holder = byId("library-kinds");
  holder.replaceChildren(...LIBRARY_KINDS.map((kind) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.dataset.kind = kind.id;
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", String(kind.id === state.libraryKind));
    button.textContent = kind.label;
    return button;
  }));
}

async function loadLibrary({reset = false} = {}) {
  const grid = byId("library-grid");
  if (reset) { grid.replaceChildren(); state.libraryCursor = null; }
  let page;
  try {
    page = await call("library.list", {kind: state.libraryKind, limit: 24, before: state.libraryCursor});
  } catch {
    byId("library-empty").hidden = false;
    byId("library-empty").textContent = "ライブラリを読み込めませんでした。";
    return;
  }
  state.libraryCursor = page.next_before;
  byId("library-more").hidden = !page.next_before;
  for (const item of page.items) grid.append(await libraryCard(item));
  const empty = grid.childElementCount === 0;
  byId("library-empty").hidden = !empty;
  byId("library-empty").textContent = "まだ素材はありません。";
}

const KIND_LABEL = {generated: "作った", edited: "直した", imported: "取り込み"};

async function libraryCard(item) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = "card";
  card.dataset.assetId = item.asset_id;
  const image = document.createElement("img");
  image.alt = item.summary || "";
  const summary = document.createElement("span");
  summary.className = "sum";
  summary.textContent = item.summary || "(説明なし)";
  const meta = document.createElement("span");
  meta.className = "meta";
  const kind = document.createElement("span");
  kind.textContent = KIND_LABEL[item.kind] || item.kind;
  const size = document.createElement("span");
  size.textContent = item.width && item.height ? `${item.width}×${item.height}` : "";
  meta.append(kind, size);
  card.append(image, summary, meta);
  card.addEventListener("click", () => void openDetail(item.asset_id));
  try {
    const thumbnail = await call("assets.thumbnail", {asset_id: item.asset_id});
    image.src = `data:${thumbnail.mime_type};base64,${thumbnail.base64}`;
  } catch { image.alt = "表示できません"; }
  return card;
}

async function openDetail(assetId) {
  const body = byId("detail-body");
  byId("detail-title").textContent = "詳細";
  body.replaceChildren();
  try {
    const provenance = await call("assets.provenance", {asset_id: assetId});
    const summary = document.createElement("dl");
    summary.className = "facts";
    const rows = [
      ["作った指示", provenance.intent],
      ["元になった素材", provenance.parent_asset_ids.length ? provenance.parent_asset_ids.join(", ") : "なし"],
      ["ライセンス", provenance.license],
      ["検証", provenance.validation.length ? JSON.stringify(provenance.validation) : "記録なし"],
    ];
    for (const [term, value] of rows) {
      const wrap = document.createElement("div");
      const dt = document.createElement("dt");
      dt.textContent = term;
      const dd = document.createElement("dd");
      dd.textContent = String(value);
      wrap.append(dt, dd);
      summary.append(wrap);
    }
    body.append(summary);
    if (state.mode === "advanced") {
      const raw = document.createElement("pre");
      raw.textContent = JSON.stringify(provenance, null, 2);
      body.append(raw);
    }
    byId("detail-dialog").showModal();
  } catch { /* 詳細が出せなくても一覧は使える */ }
}

/* ── activity ─────────────────────────────────────────────────────────── */

function updateActivityBadge(count) {
  const badge = byId("activity-badge");
  badge.hidden = count < 1;
  badge.textContent = String(count);
}

async function loadActivity() {
  const list = byId("activity-list");
  let items = [];
  try { ({items} = await call("jobs.list")); state.jobs = items; } catch {
    byId("activity-empty").hidden = false;
    byId("activity-empty").textContent = "状況を読み込めませんでした。";
    return;
  }
  const running = items.filter((job) => !TERMINAL.has(job.status));
  const finished = items.filter((job) => TERMINAL.has(job.status));
  list.replaceChildren(...[...running, ...finished].map(activityRow));
  byId("activity-empty").hidden = items.length > 0;
  updateActivityBadge(running.length);
}

const STATUS_LABEL = {queued: "待機", running: "実行中", succeeded: "完了", failed: "失敗", canceled: "中止"};

function relativeTime(value) {
  const seconds = Math.max(0, (Date.now() - Date.parse(value)) / 1000);
  if (seconds < 60) return "たった今";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分前`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 時間前`;
  return `${Math.floor(seconds / 86400)} 日前`;
}

function activityRow(job) {
  const row = document.createElement("article");
  row.className = "row";
  row.dataset.jobId = job.id;
  row.dataset.status = job.status;

  const info = document.createElement("div");
  const title = document.createElement("p");
  title.className = "t";
  title.textContent = job.request.intent;
  const sub = document.createElement("p");
  sub.className = "s";
  const running = !TERMINAL.has(job.status);
  if (running) {
    sub.textContent = `${PHASE_TEXT[job.phase] || "実行しています"} · ${Math.round((job.progress || 0) * 100)}%`;
  } else if (job.status === "succeeded") {
    sub.textContent = `できあがりました · ${relativeTime(job.updated_at)}`;
  } else if (job.status === "canceled") {
    sub.textContent = `中止しました · ${relativeTime(job.updated_at)}`;
  } else {
    sub.textContent = `${failureText(job.error?.code)} · ${relativeTime(job.updated_at)}`;
  }
  info.append(title, sub);
  if (state.mode === "advanced") {
    const raw = document.createElement("p");
    raw.className = "s";
    raw.textContent = `${job.id} · ${job.phase || "-"}${job.error ? ` · ${job.error.code}` : ""}`;
    info.append(raw);
  }

  const side = document.createElement("div");
  side.className = "row-side";
  const status = document.createElement("span");
  status.className = "state";
  status.textContent = STATUS_LABEL[job.status] || job.status;
  side.append(status);

  // 出口はここで作る。失敗を見せるだけで終わらせない。
  if (running) {
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.dataset.cancelJob = job.id;
    cancel.textContent = "中止";
    side.append(cancel);
  } else if (job.status === "failed") {
    const detail = failure(job.error?.code);
    const exit = document.createElement("button");
    exit.type = "button";
    exit.dataset.exitAction = detail.action;
    exit.dataset.exitJob = job.id;
    exit.textContent = detail.exit;
    side.append(exit);
  } else if (job.status === "succeeded") {
    const again = document.createElement("button");
    again.type = "button";
    again.dataset.exitAction = "rerun";
    again.dataset.exitJob = job.id;
    again.textContent = "同じ設定でもう一度";
    side.append(again);
  }

  row.append(info, side);
  return row;
}

/* ── settings ─────────────────────────────────────────────────────────── */

const CAPABILITY_LABEL = {
  "image.text_to_image": "画像を作る",
  "image.single_reference_edit": "画像全体を直す",
  "image.inpaint": "一部だけ直す",
  "image.outpaint": "外側を広げる",
  "image.variation": "似た別案を作る",
  "image.multi_reference_edit": "参考を足して直す",
  "image.strict_edit": "変えない部分を保証する",
  "image.semantic_review": "内容を自動で確認する",
  "video.image_to_video": "動画にする",
  "3d.image_to_3d": "3D にする",
};

async function loadSettings() {
  const list = byId("capability-list");
  list.replaceChildren(...Object.entries(state.capabilities).map(([name, value]) => {
    const row = document.createElement("article");
    row.className = "row";
    row.dataset.capability = name;
    const info = document.createElement("div");
    const title = document.createElement("p");
    title.className = "t";
    title.textContent = CAPABILITY_LABEL[name] || name;
    info.append(title);
    if (value.state !== "available") {
      const sub = document.createElement("p");
      sub.className = "s";
      sub.textContent = CAPABILITY_REASON[value.reason] || "いま使えません";
      info.append(sub);
    }
    const status = document.createElement("span");
    status.className = "state";
    status.textContent = {available: "使えます", experimental: "試験中", unavailable: "使えません"}[value.state] || value.state;
    row.append(info, status);
    return row;
  }));
  byId("host-state").textContent = state.bridgePort ? "接続しています" : "この画面だけで動いています";
}

async function loadAdvancedSettings() {
  const holder = byId("advanced-models");
  if (!holder) return;
  try {
    const {items} = await call("models.list");
    holder.replaceChildren(...items.map((model) => {
      const row = document.createElement("article");
      row.className = "row";
      const info = document.createElement("div");
      const title = document.createElement("p");
      title.className = "t";
      title.textContent = model.id;
      const sub = document.createElement("p");
      sub.className = "s";
      sub.textContent = `${model.state} · ${model.installed ? "installed" : "not installed"} · ${model.license}`;
      info.append(title, sub);
      row.append(info);
      return row;
    }));
    const select = byId("advanced-model");
    if (select) {
      select.replaceChildren(...items.map((model) => {
        const option = document.createElement("option");
        option.value = model.id;
        option.textContent = model.id;
        return option;
      }));
    }
  } catch { holder.textContent = "モデル一覧を読み込めませんでした。"; }
}

/* ── wiring ───────────────────────────────────────────────────────────── */

byId("mode-simple").addEventListener("click", () => setMode("simple"));
byId("mode-advanced").addEventListener("click", () => setMode("advanced"));
byId("nav-settings").addEventListener("click", () => activate("settings"));
for (const button of document.querySelectorAll("#shell-nav button")) {
  button.addEventListener("click", () => activate(button.dataset.view));
}
for (const button of document.querySelectorAll("[data-refresh]")) {
  button.addEventListener("click", () => activate(button.dataset.refresh, {sync: false}));
}

byId("size-presets").addEventListener("click", (event) => {
  const chip = event.target.closest("[data-preset]");
  if (!chip) return;
  for (const other of byId("size-presets").children) {
    other.setAttribute("aria-checked", String(other === chip));
  }
  syncCustomVisibility();
  renderSizeSection();
  clearError();
  if (state.mode === "advanced") syncAdvancedCreate();
  void savePreferences({last_preset: chip.dataset.preset});
});

byId("count-chips").addEventListener("click", (event) => {
  const chip = event.target.closest("[data-count]");
  if (!chip) return;
  for (const other of byId("count-chips").children) {
    other.setAttribute("aria-checked", String(other === chip));
  }
  if (state.mode === "advanced") syncAdvancedCreate();
  void savePreferences({last_count: Number(chip.dataset.count)});
});

byId("size-custom").addEventListener("input", (event) => {
  if (!event.target.id.startsWith("custom-")) return;
  clearError();
  renderSizeSection();
  void savePreferences({
    last_custom_width: Number(byId("custom-width").value) || 0,
    last_custom_height: Number(byId("custom-height").value) || 0,
  });
});

byId("custom-ratios").addEventListener("click", (event) => {
  const chip = event.target.closest("[data-custom-ratio]");
  if (!chip) return;
  const [first, second] = chip.dataset.customRatio.split(":").map(Number);
  const size = ratioSize([first, second]);
  byId("custom-width").value = size.width;
  byId("custom-height").value = size.height;
  clearError();
  renderSizeSection();
  void savePreferences({last_custom_width: size.width, last_custom_height: size.height});
});

byId("library-kinds").addEventListener("click", (event) => {
  const chip = event.target.closest("[data-kind]");
  if (!chip) return;
  state.libraryKind = chip.dataset.kind;
  renderLibraryKinds();
  void savePreferences({library_kind: state.libraryKind});
  void loadLibrary({reset: true});
});

byId("edit-actions").addEventListener("click", (event) => {
  const button = event.target.closest("[data-edit-mode]");
  if (button && !button.disabled) selectEditMode(button.dataset.editMode);
});

byId("mask-draw").addEventListener("click", maskOpen);
byId("mask-close").addEventListener("click", () => byId("mask-dialog").close());
byId("mask-cancel").addEventListener("click", () => byId("mask-dialog").close());
byId("mask-apply").addEventListener("click", () => void maskApply());
byId("mask-brush").addEventListener("click", () => setMaskTool(false));
byId("mask-eraser").addEventListener("click", () => setMaskTool(true));
byId("mask-clear").addEventListener("click", () => {
  maskSnapshot();
  mask.context.clearRect(0, 0, mask.canvas.width, mask.canvas.height);
});
byId("mask-undo").addEventListener("click", () => {
  const previous = mask.history.pop();
  if (previous) mask.context.putImageData(previous, 0, 0);
});
byId("mask-canvas").addEventListener("pointerdown", maskPointerDown);
byId("mask-canvas").addEventListener("pointermove", maskPointerMove);
for (const name of ["pointerup", "pointercancel", "pointerleave"]) {
  byId("mask-canvas").addEventListener(name, maskPointerUp);
}
byId("mask-stage").addEventListener("wheel", (event) => {
  if (!event.ctrlKey) return;
  event.preventDefault();
  mask.scale = Math.max(1, Math.min(6, mask.scale * (event.deltaY < 0 ? 1.1 : 0.9)));
  byId("mask-canvas-wrap").style.transform = `scale(${mask.scale})`;
}, {passive: false});

byId("outpaint-ratios").addEventListener("click", (event) => {
  const chip = event.target.closest("[data-ratio]");
  if (!chip) return;
  state.outpaintRatio = chip.dataset.ratio;
  renderOutpaintControls();
  clearError();
});
byId("outpaint-scales").addEventListener("click", (event) => {
  const chip = event.target.closest("[data-scale]");
  if (!chip) return;
  state.outpaintScale = Number(chip.dataset.scale);
  renderOutpaintControls();
  clearError();
});

byId("source-file").addEventListener("change", () => void refreshAttachment());
byId("attach-clear").addEventListener("click", () => {
  byId("source-file").value = "";
  void refreshAttachment();
});

const dropzone = byId("attach-image");
for (const name of ["dragenter", "dragover"]) {
  dropzone.addEventListener(name, (event) => {
    event.preventDefault();
    dropzone.classList.add("dragging");
  });
}
for (const name of ["dragleave", "drop"]) {
  dropzone.addEventListener(name, () => dropzone.classList.remove("dragging"));
}
dropzone.addEventListener("drop", (event) => {
  event.preventDefault();
  const file = event.dataTransfer?.files?.[0];
  if (!file || !file.type.startsWith("image/")) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  byId("source-file").files = transfer.files;
  void refreshAttachment();
});
byId("create-form").addEventListener("submit", submitJob);
function jobById(id) {
  return state.jobs.find((item) => item.id === id) || null;
}

for (const holder of [byId("activity-list"), byId("create-error")]) {
  holder.addEventListener("click", (event) => {
    const exit = event.target.closest("[data-exit-action]");
    if (exit) return runExit(exit.dataset.exitAction, jobById(exit.dataset.exitJob));
    const cancel = event.target.closest("[data-cancel-job]");
    if (cancel) {
      void call("jobs.cancel", {job_id: cancel.dataset.cancelJob})
        .then(() => loadActivity())
        .catch(() => {});
    }
  });
}

byId("library-more").addEventListener("click", () => void loadLibrary());
byId("close-dialog").addEventListener("click", () => byId("detail-dialog").close());
byId("open-host-jobs").addEventListener("click", () => void callHost("host.route.open", {route: "/jobs"}).catch(() => {}));
byId("result-detail").addEventListener("click", () => {
  const assetId = byId("result-image").dataset.assetId;
  if (assetId) void openDetail(assetId);
});
byId("result-edit").addEventListener("click", () => {
  byId("create-status").textContent = "ライブラリから画像を選び直して「画像を追加」に読み込ませてください。";
});
for (const id of ["progress-cancel", "mini-cancel"]) {
  byId(id).addEventListener("click", () => {
    if (state.activeJob) void call("jobs.cancel", {job_id: state.activeJob}).catch(() => {});
  });
}

/* ── boot ─────────────────────────────────────────────────────────────── */

async function boot() {
  try {
    const {values} = await call("preferences.get");
    state.preferences = values || {};
  } catch { state.preferences = {}; }
  try {
    const document_ = await call("capabilities.get");
    state.capabilities = document_.capabilities || {};
    state.envelope = document_.envelope || null;
    state.presets = document_.presets || [];
  } catch { state.capabilities = {}; }

  state.libraryKind = state.preferences.library_kind || "all";
  renderPresets();
  renderCounts();
  renderLibraryKinds();
  setMode(state.preferences.mode || "simple", {persist: false});
  await refreshAttachment();
  void loadEstimate();
  await loadRecent();
  activate(state.preferences.last_view || "create", {sync: false});
  await call("jobs.watch", {job_ids: []}).catch(() => {});
  document.documentElement.dataset.bridge = window.parent === window ? "standalone" : "ready";
  app().setAttribute("aria-busy", "false");
}

window.addEventListener("message", (event) => {
  const expectedOrigin = document.referrer ? new URL(document.referrer).origin : location.origin;
  if (event.source !== parent || event.origin !== expectedOrigin
      || event.data?.type !== "control-deck-host.connected" || !event.ports[0]) return;
  state.bridgePort = event.ports[0];
  state.nonce = event.data.session_nonce;
  applyTheme(event.data.theme);
  state.bridgePort.onmessage = (messageEvent) => {
    const message = messageEvent.data;
    if (message?.type !== "event") return;
    if (message.event === "theme.changed") applyTheme(message.data);
    if (message.event === "locale.changed" && message.data?.locale) document.documentElement.lang = message.data.locale;
    if (message.event === "safe_area.changed") applySafeArea(message.data);
    if (message.event === "visibility.changed") state.visible = message.data?.visible !== false;
    if (message.event === "route.changed") activate(String(message.data?.path || "/").split("/")[1] || "create", {sync: false});
    if (message.event === "session.updated") state.nonce = message.data.session_nonce;
    if (message.event === "disable.pending") {
      state.disabled = true;
      if (state.activeJob) void call("jobs.cancel", {job_id: state.activeJob}).catch(() => {});
      state.activeJob = "";
      setHostBusy(false);
    }
  };
  state.bridgePort.start();
  void connectSocket()
    .then(boot)
    .catch(() => { document.documentElement.dataset.bridge = "error"; });
  void callHost("host.title.set", {title: "Media Forge"}).catch(() => {});
});

window.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k" && state.bridgePort) {
    event.preventDefault();
    state.bridgePort.postMessage({type: "shortcut", shortcut: "command_palette", session_nonce: state.nonce});
  }
});

if (window.parent === window) void boot();
else window.parent.postMessage({type: "control-deck-addon.connect", bridge_version: "1.0"}, "*");
