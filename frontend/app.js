/* Media Forge workspace.

   埋め込み iframe は allow-same-origin なしの opaque sandbox で動く。
   ブラウザ側の保存領域は一切使えないため、覚えておきたい値はすべて backend の
   preferences に置く。画像は /ws 経由の base64 で受け取る。
   （保存 API の名前をこのファイルに 1 度も書かないこと自体を試験で守っている） */

const TERMINAL = new Set(["succeeded", "failed", "canceled"]);

/* 作りかけの設定は覚えておく。毎回ドメインから選び直させるほどの理由が無い。
   戻したいときのために、初期値は 1 か所に置いてクリアから使えるようにする。 */
const CREATIVE_DEFAULTS = {
  domain: "auto", scene: "auto", pose: "auto", composition: "auto",
  camera: "auto", variation: "auto",
  sceneDetails: "", poseDetails: "", compositionDetails: "", cameraDetails: "",
};
const MODEL_TERMINAL = new Set(["ready", "failed", "canceled"]);
const VIEWS = ["create", "library", "activity", "settings"];

const PHASE_TEXT = {
  starting: "準備しています",
  normalize_request: "準備しています",
  validate_request: "準備しています",
  direct: "演出内容を整理しています",
  select_model: "使うモデルを選んでいます",
  release_ai: "文章・画像認識に使った GPU を空けています",
  waiting_resource: "GPU の空きを待っています",
  generating: "生成しています",
  release_resource: "GPU リソースを解放しています",
  postprocess: "仕上げています",
  semantic_review: "内容を確認しています",
  validate: "保証を検証しています",
  package: "保存しています",
  register_asset: "保存しています",
  canceled: "中止しました",
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
  vision_analyzer_unavailable: "ControlDeck の画像確認機能をいま使えません",
  model_not_installed: "使うモデルがまだ入っていません",
  capability_not_installed: "対応するモデルがありません",
  model_registry_invalid: "モデル一覧を読み込めません",
  planned_for_g7: "これからの対応予定です",
  planned_for_g9: "これからの対応予定です",
  video_runtime_not_adopted: "実用条件を満たす動画の実行環境がまだありません",
  text_generator_unavailable: "ControlDeck の文章による演出補助をいま使えません",
  runtime_not_installed: "3D整形ランタイムが導入されていません",
};

const state = {
  bridgePort: null,
  nonce: "",
  sequence: 0,
  disabled: false,
  hostBusy: false,
  visible: true,
  view: "create",
  mode: "simple",
  createMedia: "image",
  preferences: {},
  capabilities: {},
  envelope: null,
  presets: [],
  creativeTemplates: null,
  creative: {...CREATIVE_DEFAULTS},
  directorMode: "original",
  directorPlan: null,
  profiles: [],
  referenceCollections: [],
  characterProfileId: "",
  styleProfileId: "",
  referenceOverrides: new Map(),
  referenceAnalysis: null,
  referenceFocus: "overall",
  sourceAsset: null,
  project3dAsset: null,
  editMode: "",
  source: null,
  upload: null,
  sourceUrl: "",
  maskFile: null,
  maskPainted: 0,
  outpaintRatio: "source",
  outpaintScale: 1.5,
  activeJob: "",
  activeBatch: "",
  activeComposition: "",
  currentComposition: null,
  resultAssetIds: [],
  batches: [],
  jobs: [],
  libraryCursor: null,
  libraryItems: [],
  librarySelecting: false,
  librarySelected: new Set(),
  modelCatalog: [],
  modelOperations: new Map(),
  catalogResults: [],
  catalogPage: 0,
  modelSpeeds: new Map(),
  modelFilter: "installed",
  modelSort: "runnable",
  lastNonSettingsView: "create",
  deviceVramBytes: 0,
  modelChoice: "auto",
  domainProfiles: [],
  modelManagementAvailable: false,
  modelEvaluationIds: new Set(),
  removeModelId: "",
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

function mediaSwitchButtons() {
  return [byId("create-media-image"), byId("create-media-video")];
}

function setMediaSwitchDisabled(value) {
  for (const button of mediaSwitchButtons()) button.disabled = value;
}

/* host の「未保存」は離脱を警告する。Media Forge には保存の概念が無く、
   実行中の作業はサーバ側の job として残るので、入力しただけでは立てない。
   実際に失うものがある間（取り込み中・受付中）だけ立てる。 */
function setHostBusy(value) {
  if (state.hostBusy === value) return;
  state.hostBusy = value;
  setMediaSwitchDisabled(value);
  if (!state.bridgePort) return;
  void callHost("host.busy.set", {busy: value}).catch(() => {
    state.hostBusy = !value;
    setMediaSwitchDisabled(!value);
  });
}

/* ── workspace transport ──────────────────────────────────────────────── */

/* 接続は切れるものとして扱う。携帯では画面を離れただけで socket は閉じられ、
   戻ってきた頁が bfcache から復元されると JS の状態だけが生き残る。
   以前は解決済みの promise を握ったままだったので、閉じた socket へ send を
   続け、画面は空のままになった（再読込するまで直らない）。 */
function socketOpen() {
  return state.socket && state.socket.readyState === WebSocket.OPEN;
}

function dropSocket() {
  state.socketReady = null;
  state.socket = null;
}

function connectSocket() {
  if (state.socketReady && socketOpen()) return state.socketReady;
  if (state.socketReady && state.socket && state.socket.readyState === WebSocket.CONNECTING) {
    return state.socketReady;
  }
  dropSocket();
  state.socketReady = new Promise((resolve, reject) => {
    const frameRoot = location.pathname.split("/").slice(0, 3).join("/").replace(/\/+$/, "");
    const scheme = location.protocol === "https:" ? "wss" : "ws";
    state.socket = new WebSocket(`${scheme}://${location.host}${frameRoot}/ws`, [`control-deck-bridge.${state.nonce}`]);
    state.socket.onopen = () => resolve();
    state.socket.onerror = () => {
      dropSocket();
      reject({code: "workspace_transport_unavailable"});
    };
    state.socket.onclose = () => {
      // 次の呼び出しで張り直せるようにする。持ったままにすると、以後の
      // すべての要求が閉じた socket へ送られて黙って失敗する。
      dropSocket();
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

/* 何 GB あるかは出していたが、あと何分かかるのかは出していなかった。
   backend は速度を持っていない（持たせると全接続に同じ数字を配ることになる）。
   届いた bytes_done の差分から手元で出す。1 秒未満の差分は雑音なので捨て、
   指数移動平均で均す。生の瞬間値は桁が跳ねて読めない。 */
function recordModelSpeed(operation) {
  if (!operation?.id) return;
  if (MODEL_TERMINAL.has(operation.state)) {
    state.modelSpeeds.delete(operation.id);
    return;
  }
  const now = Date.now();
  const previous = state.modelSpeeds.get(operation.id);
  if (!previous) {
    state.modelSpeeds.set(operation.id, {at: now, bytes: operation.bytes_done, bps: 0});
    return;
  }
  const seconds = (now - previous.at) / 1000;
  const gained = operation.bytes_done - previous.bytes;
  if (seconds < 1 || gained < 0) return;
  const sample = gained / seconds;
  state.modelSpeeds.set(operation.id, {
    at: now,
    bytes: operation.bytes_done,
    bps: previous.bps ? previous.bps * 0.7 + sample * 0.3 : sample,
  });
}

function modelSpeedText(operation) {
  const speed = state.modelSpeeds.get(operation?.id);
  if (!speed?.bps || MODEL_TERMINAL.has(operation.state)) return "";
  const parts = [`${formatBytes(Math.round(speed.bps))}/秒`];
  const left = (operation.bytes_total || 0) - operation.bytes_done;
  if (left > 0) parts.push(`残り ${formatDuration(left / speed.bps)}`);
  return parts.join(" · ");
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "-";
  if (seconds < 90) return `約 ${Math.max(1, Math.round(seconds))} 秒`;
  if (seconds < 5400) return `約 ${Math.round(seconds / 60)} 分`;
  return `約 ${Math.round(seconds / 360) / 10} 時間`;
}

function handleEvent(message) {
  if (!message?.data) return;
  if (message.event === "model.operation.changed") {
    const operation = message.data;
    recordModelSpeed(operation);
    state.modelOperations.set(operation.id, operation);
    renderModelManagement();
    renderModelMiniProgress();
    if (MODEL_TERMINAL.has(operation.state)) void loadModelManagement();
    return;
  }
  if (message.event === "job.changed") {
    const job = message.data;
    // 復元できるよう、届いた最新状態を持っておく。
    const jobs = state.jobs || [];
    const index = jobs.findIndex((item) => item.id === job.id);
    if (index >= 0) jobs[index] = job; else jobs.unshift(job);
    state.jobs = jobs;
    if (job.id === state.activeJob) showProgress(job);
    if (TERMINAL.has(job.status)) void finishJob(job);
    return;
  }
  if (message.event === "session.changed") {
    // 状態の正はサーバにある。変わった部分だけ読み直す。polling はしない。
    const parts = Array.isArray(message.data.parts) ? message.data.parts : [];
    if (parts.length) void refreshSession(parts);
  }
}

async function standaloneCall(method, params) {
  const json = async (path, options = {}) => {
    const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw payload.detail || {code: `http_${response.status}`};
    }
    // 204 は本体を持たない。DELETE を成功として扱う。
    if (response.status === 204) return {};
    return response.json();
  };
  if (method === "jobs.create") return json("/api/v1/jobs", {method: "POST", body: JSON.stringify(params)});
  if (method === "jobs.get") return json(`/api/v1/jobs/${encodeURIComponent(params.job_id)}`);
  if (method === "jobs.cancel") return json(`/api/v1/jobs/${encodeURIComponent(params.job_id)}`, {method: "DELETE"});
  if (method === "jobs.list") return json("/api/v1/jobs");
  if (method === "jobs.watch" || method === "jobs.unwatch") return {watching: []};
  if (method === "creative.validate") {
    return json("/workspace-api/creative/validate", {method: "POST", body: JSON.stringify(params)});
  }
  if (method === "creative.direct") {
    return json("/workspace-api/creative/direct", {method: "POST", body: JSON.stringify(params)});
  }
  if (method === "references.analyze") {
    return json("/workspace-api/references/analyze", {method: "POST", body: JSON.stringify(params)});
  }
  if (method === "creative.batches.create") {
    return json("/workspace-api/creative/batches", {method: "POST", body: JSON.stringify(params)});
  }
  if (method === "creative.batches.list") return json("/workspace-api/creative/batches");
  if (method === "creative.batches.get") {
    return json(`/workspace-api/creative/batches/${encodeURIComponent(params.batch_id)}`);
  }
  if (method === "creative.batches.cancel") {
    return json(`/workspace-api/creative/batches/${encodeURIComponent(params.batch_id)}`, {method: "DELETE"});
  }
  if (method === "creative.compositions.create") {
    return json("/workspace-api/creative/compositions", {method: "POST", body: JSON.stringify(params)});
  }
  if (method === "creative.compositions.list") return json("/workspace-api/creative/compositions");
  if (method === "creative.compositions.get") {
    return json(`/workspace-api/creative/compositions/${encodeURIComponent(params.composition_id)}`);
  }
  if (method === "creative.compositions.update_text") {
    return json(`/workspace-api/creative/compositions/${encodeURIComponent(params.composition_id)}`, {
      method: "PATCH", body: JSON.stringify(params),
    });
  }
  if (method === "creative.compositions.cancel") {
    return json(`/workspace-api/creative/compositions/${encodeURIComponent(params.composition_id)}`, {
      method: "DELETE",
    });
  }
  if (method === "creative.evaluate") {
    return json("/workspace-api/creative/evaluate", {method: "POST", body: JSON.stringify(params)});
  }
  if (method === "models.list") return json("/api/v1/models");
  if (method === "models.catalog") {
    // ローカルのモデル管理はホストを必要としない。単体表示でも本物を返す。
    try { return await json("/workspace-api/models/catalog"); } catch { /* 旧 core は shim へ落ちる */ }
  }
  if (method === "models.operations.list") return json("/workspace-api/models/operations");
  if (method === "models.install") {
    return json("/workspace-api/models/operations", {method: "POST", body: JSON.stringify(
      {action: "install", model_id: params.model_id, license_acceptance: params.license_acceptance})});
  }
  if (method === "models.remove") {
    return json("/workspace-api/models/operations", {method: "POST", body: JSON.stringify(
      {action: "remove", model_id: params.model_id})});
  }
  if (method === "models.operations.cancel") {
    return json("/workspace-api/models/operations", {method: "POST", body: JSON.stringify(
      {action: "cancel", operation_id: params.operation_id})});
  }
  if (method === "models.operations.clear") {
    return json("/workspace-api/models/operations", {method: "POST", body: JSON.stringify(
      {action: "clear"})});
  }
  if (method === "jobs.clear") {
    return json("/workspace-api/jobs/clear", {method: "POST"});
  }
  if (method === "assets.delete") {
    return json("/workspace-api/assets/delete", {method: "POST", body: JSON.stringify(
      {asset_ids: params.asset_ids})});
  }
  if (method === "models.catalog") {
    const {items} = await json("/api/v1/models");
    return {items: items.map((model) => ({
      model_id: model.id, display_name: model.display_name || model.id,
      domains: model.domains || ["general"], media_types: model.media_types || ["image"],
      description: model.description || "", approx_download_bytes: model.approx_download_bytes || 0,
      reclaimable_bytes: 0,
      profile_reference_count: 0, source: model.source || null, ownership: "external",
      installed: model.installed, healthy: model.healthy, removable: false,
      state: model.state, supports_lora: model.supports_lora || false,
      // 種別と系統を落とすと、単体表示では LoRA が土台の一覧に混ざり、
      // 載せられるかどうかも判定できなくなる。
      kind: model.kind || "model", base_model: model.base_model || "",
      trigger_words: model.trigger_words || [],
      max_references: model.max_references || 0,
      reference_roles: model.reference_roles || [],
      supports_reference_strength: model.supports_reference_strength || false,
      recommended_profiles: model.recommended_profiles || [], gated: model.gated || false,
      license: model.license, license_notice: model.license_notice || model.license,
      runtime_adapter: model.runtime_adapter,
      hardware_backends: model.hardware_backends || [], capabilities: model.capabilities,
      weights_hash: "", measurement_confidence: model.measurement_confidence,
      measured_vram_bytes: model.measured_vram_bytes,
      measured_runtime_sec: model.measured_runtime_sec,
    })), storage: {managed_bytes: 0, free_bytes: 0, total_bytes: 0}, management_available: false};
  }
  if (method === "models.operations.watch" || method === "models.operations.unwatch") return {watching: []};
  if (method === "assets.provenance") return json(`/api/v1/assets/${encodeURIComponent(params.asset_id)}/provenance`);
  if (method === "preferences.get") return {values: state.preferences};
  if (method === "preferences.set") return {values: {...state.preferences, ...params.values}};
  if (method === "profiles.list") return json("/api/v1/profiles");
  if (method === "reference_collections.list") return json("/api/v1/reference-collections");
  if (method === "domain_profiles.list") return json("/api/v1/domain-profiles");
  if (method === "models.custom.search") {
    // 配布元の検索はホストを必要としない。単体表示でも使えるべきである。
    return json("/workspace-api/models/search", {method: "POST", body: JSON.stringify(params)});
  }
  if (method === "models.custom.resolve" || method === "models.custom.add"
      || method === "models.custom.remove") {
    // 単体表示ではモデル取り込みに CLI を使う。UI から偽の成功を返さない。
    throw {code: "model_not_found", message: "単体表示ではモデルの取り込みに CLI を使います。"};
  }
  if (method === "profiles.create") {
    return json("/api/v1/profiles", {method: "POST", body: JSON.stringify(params)});
  }
  if (method === "profiles.delete") {
    await json(`/api/v1/profiles/${encodeURIComponent(params.profile_id)}`, {method: "DELETE"});
    return {deleted: true};
  }
  if (method === "reference_collections.create") {
    return json("/api/v1/reference-collections", {method: "POST", body: JSON.stringify(params)});
  }
  if (method === "reference_collections.delete") {
    await json(`/api/v1/reference-collections/${encodeURIComponent(params.collection_id)}`, {method: "DELETE"});
    return {deleted: true};
  }
  if (method === "capabilities.get") {
    const document_ = await json("/api/v1/capabilities");
    const config = embeddedWorkspaceConfig();
    return {...document_, envelope: config?.envelope || null, presets: config?.presets || []};
  }
  if (method === "library.list") {
    return json("/workspace-api/library", {method: "POST", body: JSON.stringify(params)});
  }
  if (method === "assets.thumbnail") {
    return json(`/workspace-api/assets/${encodeURIComponent(params.asset_id)}/thumbnail`, {
      method: "POST", body: JSON.stringify({max_side: params.max_side}),
    });
  }
  if (method === "assets.content") {
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
      method: "POST", headers: {"Content-Type": params.media_type || "application/octet-stream"}, body: bytes,
    });
    if (!response.ok) throw {code: `http_${response.status}`};
    return response.json();
  }
  if (method === "workspace.session") {
    // standalone には集約 endpoint が無い。既存経路を並列で束ね、
    // 呼び出し側から見た形だけ揃える。
    const want = (name) => !params.parts || params.parts.includes(name);
    const part = async (name, run) => {
      if (!want(name)) return [name, undefined];
      try { return [name, await run()]; } catch (error) { return [name, {unavailable: true, code: error?.code}]; }
    };
    const entries = await Promise.all([
      part("preferences", () => standaloneCall("preferences.get", {})),
      part("capabilities", () => standaloneCall("capabilities.get", {})),
      part("profiles", () => standaloneCall("profiles.list", {})),
      part("reference_collections", () => standaloneCall("reference_collections.list", {})),
      part("domain_profiles", () => standaloneCall("domain_profiles.list", {})),
      part("models", () => standaloneCall("models.list", {})),
      part("model_catalog", () => standaloneCall("models.catalog", {})),
      part("model_operations", () => standaloneCall("models.operations.list", {})),
      part("library", () => standaloneCall("library.list", {limit: 4})),
      part("creative_batches", () => standaloneCall("creative.batches.list", {})),
      part("creative_compositions", () => standaloneCall("creative.compositions.list", {})),
      part("jobs", () => standaloneCall("jobs.list", {})),
    ]);
    const snapshot = {session_version: 1};
    for (const [name, value] of entries) if (value !== undefined) snapshot[name] = value;
    return snapshot;
  }
  throw {code: "workspace_method_unsupported"};
}

async function call(method, params = {}) {
  if (window.parent === window) return standaloneCall(method, params);
  await connectSocket();
  if (!socketOpen()) {
    // connectSocket の直後でも閉じていることがある。閉じた socket への send は
    // 例外にならず、応答が永遠に来ないだけなので、ここで気づく。
    dropSocket();
    await connectSocket();
  }
  return new Promise((resolve, reject) => {
    const id = `media-forge-workspace-${++state.sequence}`;
    state.pending.set(id, {resolve, reject});
    try {
      state.socket.send(JSON.stringify({id, method, params}));
    } catch (error) {
      state.pending.delete(id);
      dropSocket();
      reject({code: "workspace_transport_closed"});
    }
  });
}

/* ── mode / preferences ───────────────────────────────────────────────── */

function setMode(mode, {persist = true} = {}) {
  state.mode = mode === "advanced" ? "advanced" : "simple";
  app().dataset.mode = state.mode;
  byId("mode-simple").setAttribute("aria-pressed", String(state.mode === "simple"));
  byId("mode-advanced").setAttribute("aria-pressed", String(state.mode === "advanced"));
  mountAdvanced();
  renderPackProfiles();
  render3dProject();
  if (persist) void savePreferences({mode: state.mode});
}

function videoCapabilityName() {
  return attachedFile() ? "video.image_to_video" : "video.text_to_video";
}

function videoCapabilityUsable(name = videoCapabilityName()) {
  return ["available", "experimental"].includes(capabilityState(name));
}

function installedVideoModels() {
  return state.modelCatalog.filter((model) => model.installed &&
    (model.media_types.includes("video") || model.media_types.includes("audio_video")));
}

function unavailableVideoReason(value) {
  if (value.reason !== "video_runtime_not_adopted") {
    return `${CAPABILITY_REASON[value.reason] || "この動画機能はいま使えません"}。`;
  }
  if (installedVideoModels().length) {
    return "動画モデルは導入済みですが、実用品質とメモリ安全性を満たした実行環境がまだ採用されていません。";
  }
  return "動画モデルがまだ導入されていません。モデル管理で候補を確認してください。";
}

function renderCreateMedia() {
  const video = state.createMedia === "video";
  app().dataset.createMedia = video ? "video" : "image";
  for (const button of mediaSwitchButtons()) {
    button.setAttribute("aria-pressed", String(button.dataset.createMedia === state.createMedia));
  }
  byId("video-create-fields").hidden = !video;
  byId("create-intent-label").textContent = video ? "どんな動画を作りますか？" : "何を作りますか？";
  byId("create-intent").placeholder = video
    ? "静かな机の上で、小さなロボットが手を振る短い動画"
    : "夜の机に置かれた、小さな青いロボット";

  const file = attachedFile();
  byId("attach-label").textContent = file
    ? `画像: ${file.name}`
    : (video ? "＋ 動かす画像を追加（任意）" : "＋ 画像を追加");
  const capability = videoCapabilityName();
  const value = state.capabilities[capability] || {};
  const usable = videoCapabilityUsable(capability);
  const anyExperimental = ["video.text_to_video", "video.image_to_video"]
    .some((name) => capabilityState(name) === "experimental");
  /* 絵は文字を持てない。試験中であることは印と、読み上げ・長押しに出る説明で伝える。 */
  const videoButton = byId("create-media-video");
  const videoLabel = anyExperimental ? "動画を作る（試験中）" : "動画を作る";
  videoButton.dataset.experimental = String(anyExperimental);
  videoButton.setAttribute("aria-label", videoLabel);
  videoButton.title = videoLabel;
  byId("video-create-summary").textContent = file
    ? "追加した画像を始点に短い動画を作ります。"
    : "文章から短い動画を作ります。画像を足すと、その画像を動かします。";
  byId("video-create-note").textContent = usable
    ? (value.state === "experimental" ? "試験中の動画機能です。結果の品質は保証されません。" : "")
    : unavailableVideoReason(value);
  byId("video-create-settings").hidden = usable;

  const submit = byId("create-submit");
  submit.dataset.unavailable = String(video && !usable);
  if (!state.hostBusy) submit.disabled = video && !usable;
  if (!state.hostBusy) {
    submit.textContent = video ? (usable ? "動画を作る" : "動画は現在利用できません") : "作る";
  }
}

function setCreateMedia(media, {persist = true} = {}) {
  state.createMedia = media === "video" ? "video" : "image";
  clearError();
  renderCreateMedia();
  void refreshAttachment();
  if (persist) void savePreferences({create_media: state.createMedia});
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
  // 幅と高さは上の「サイズ」に 1 組だけ置く。詳細モードで同じ欄を再掲して
  // いたが、そちらが上書きしていたため、どちらが効いているのか分からなかった。
  if (!byId("advanced-count")) return;
  const envelope = sizeEnvelope();
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
  renderAdvancedCreative();
  renderModelSettings();
  renderLoraPicker();
}

async function savePreferences(values) {
  state.preferences = {...state.preferences, ...values};
  try { await call("preferences.set", {values}); } catch { /* 表示設定の保存失敗は操作を止めない */ }
}

/* ── views ────────────────────────────────────────────────────────────── */

function activate(name, {sync = true} = {}) {
  const view = VIEWS.includes(name) ? name : "create";
  // 設定を閉じたときに戻る先。設定の前にいた画面へ返す。
  if (state.view && state.view !== "settings") state.lastNonSettingsView = state.view;
  state.view = view;
  app().dataset.view = view;
  for (const section of document.querySelectorAll(".view")) {
    section.hidden = section.dataset.view !== view;
  }
  // 設定はヘッダー側にあるが、現在地であることは同じように示す。
  for (const button of document.querySelectorAll("#shell-nav button, #nav-settings")) {
    if (button.dataset.view === view) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  }
  if (view === "create") restoreProgressView();
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
function embeddedCreativeTemplates() {
  try { return JSON.parse(byId("creative-template-data")?.textContent || "null"); }
  catch { return null; }
}

function embeddedWorkspaceConfig() {
  try { return JSON.parse(byId("workspace-config-data")?.textContent || "null"); }
  catch { return null; }
}

function creativeEntries(section) {
  const entries = state.creativeTemplates?.[section];
  return Array.isArray(entries) ? entries : [];
}

function creativeOption(entry) {
  const option = document.createElement("option");
  option.value = entry.id;
  option.textContent = entry.label;
  return option;
}

function fillCreativeSelect(id, section, selected) {
  const select = byId(id);
  if (!select) return;
  select.replaceChildren(...creativeEntries(section).map(creativeOption));
  select.value = selected;
}

function renderCreative() {
  const holder = byId("domain-chips");
  holder.replaceChildren(...creativeEntries("domains").map((entry) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.dataset.domain = entry.id;
    button.setAttribute("role", "radio");
    button.setAttribute("aria-checked", String(entry.id === state.creative.domain));
    button.textContent = entry.label;
    return button;
  }));
  fillCreativeSelect("creative-scene", "scenes", state.creative.scene);
  fillCreativeSelect("creative-pose", "poses", state.creative.pose);
  fillCreativeSelect("creative-composition", "compositions", state.creative.composition);
  fillCreativeSelect("creative-camera", "cameras", state.creative.camera);
  fillCreativeSelect("creative-variation", "variations", state.creative.variation);
  updateCreativeSummary();
  updateCompositionOptions();
  renderAdvancedCreative();
}

function renderAdvancedCreative() {
  // シーン・構図・カメラの選択は「シーンと見せ方」に 1 組だけ置く。詳細モードは
  // 同じ選択を繰り返さず、言葉での補足だけを足す。同じ設定が 2 箇所にあると、
  // どちらが効いているのか利用者に分からない。
  if (!byId("advanced-scene-details")) return;
  byId("advanced-scene-details").value = state.creative.sceneDetails;
  byId("advanced-pose-details").value = state.creative.poseDetails;
  byId("advanced-composition-details").value = state.creative.compositionDetails;
  byId("advanced-camera-details").value = state.creative.cameraDetails;
  renderAdvancedReferenceRoles();
}

function creativeLabel(section, id) {
  return creativeEntries(section).find((entry) => entry.id === id)?.label || id;
}

function updateCreativeSummary() {
  const chosen = [
    ["scenes", state.creative.scene], ["poses", state.creative.pose],
    ["compositions", state.creative.composition], ["cameras", state.creative.camera],
    ["variations", state.creative.variation],
  ].filter(([, id]) => id !== "auto").map(([section, id]) => creativeLabel(section, id));
  byId("scene-framing-summary").textContent = chosen.length ? chosen.join(" / ") : "自動";
}

/* 打鍵のたびに保存すると往復が増えるだけなので、手が止まってからまとめる。 */
let creativeSaveTimer = 0;

function rememberCreative() {
  window.clearTimeout(creativeSaveTimer);
  creativeSaveTimer = window.setTimeout(() => {
    // 既定のままの項目は送らない。既定を保存しても復元は同じで、
    // 保存できる大きさの上限だけを食う。
    const changed = Object.fromEntries(
      Object.entries(state.creative).filter(([key, value]) => value !== CREATIVE_DEFAULTS[key]),
    );
    void savePreferences({last_creative_spec: changed});
  }, 600);
}

function setCreativeValue(key, value) {
  state.creative[key] = value;
  if (key === "domain") {
    for (const button of byId("domain-chips").children) {
      button.setAttribute("aria-checked", String(button.dataset.domain === value));
    }
  } else {
    const simple = byId(`creative-${key}`);
    if (simple) simple.value = value;
  }
  const advanced = byId(`advanced-${key}`);
  if (advanced) advanced.value = value;
  updateCreativeSummary();
  rememberCreative();
  updateCompositionOptions();
  renderDirectorControl();
  clearError();
}

function compositionTemplate() {
  if (state.creative.domain === "poster" || state.creative.composition === "poster"
      || state.creative.composition === "multi_cut_promo") return "poster";
  if (state.creative.domain === "character_sheet" || state.creative.composition === "character_sheet") {
    return "character_sheet";
  }
  return "";
}

function updateCompositionOptions() {
  const template = compositionTemplate();
  const block = byId("composition-options");
  block.hidden = !template;
  if (template) {
    byId("composition-options-label").textContent = template === "poster"
      ? "複数カットのポスター" : "キャラクター表";
  }
}

function compositionLayout() {
  const template = compositionTemplate();
  if (!template) return null;
  return {
    template,
    title: byId("composition-title").value,
    caption: byId("composition-caption").value,
    shot_count: requestedCount(),
  };
}

function creativeSpec() {
  return {
    domain: state.creative.domain,
    scene: {preset: state.creative.scene, details: state.creative.sceneDetails},
    pose: {preset: state.creative.pose, details: state.creative.poseDetails},
    composition: {
      preset: state.creative.composition,
      details: state.creative.compositionDetails,
    },
    camera: {preset: state.creative.camera, details: state.creative.cameraDetails},
    variation: {axis: state.creative.variation},
    reference_roles: selectedProfileReferences().map(({asset_id, role, strength}) => ({
      asset_id, role, strength,
    })),
  };
}

function creativeActive(spec = creativeSpec()) {
  return spec.domain !== "auto" || spec.scene.preset !== "auto" || spec.scene.details
    || spec.pose.preset !== "auto" || spec.pose.details
    || spec.composition.preset !== "auto" || spec.composition.details
    || spec.camera.preset !== "auto" || spec.camera.details || spec.variation.axis !== "auto";
}

function directorAvailable() {
  return capabilityState("creative.text_direction") === "available";
}

function renderDirectorControl() {
  const available = directorAvailable();
  const select = byId("director-mode");
  for (const option of select.options) option.disabled = !available && option.value !== "original";
  if (!available && state.directorMode !== "original") state.directorMode = "original";
  select.value = state.directorMode;
  byId("director-reason").textContent = available
    ? "作る前に内容を整理します。画像の確認は行いません。"
    : "演出補助は使えません。そのままの文章で作れます。";
  const pose = byId("simple-pose-control");
  pose.hidden = available && state.directorMode !== "original" && state.creative.pose === "auto";
}

function directorRow(label, value) {
  const row = document.createElement("div");
  const term = document.createElement("dt");
  const detail = document.createElement("dd");
  term.textContent = label;
  detail.textContent = value || "—";
  row.append(term, detail);
  return row;
}

function actionSummary(action = {}) {
  return [action.action, action.state, action.orientation, action.gesture, action.gaze, action.motion_hint]
    .concat(action.body_or_part_relations || []).filter(Boolean).join(" / ");
}

function renderDirectorPlan(directed) {
  const holder = byId("director-understanding");
  const plan = directed?.plan;
  if (!plan) {
    holder.hidden = true;
    state.directorPlan = null;
    return;
  }
  holder.hidden = false;
  const facts = byId("director-plan-summary");
  facts.replaceChildren(
    directorRow("元の希望", plan.original_intent),
    directorRow("対象", [plan.subject?.kind, ...(plan.subject?.identity_traits || []),
      ...(plan.subject?.appearance_traits || [])].filter(Boolean).join(" / ")),
    directorRow("動き・状態", actionSummary(plan.primary_action)),
    directorRow("シーン", plan.scene),
    directorRow("構図・カメラ", [plan.composition, plan.camera].filter(Boolean).join(" / ")),
    directorRow("提案", (plan.optional_suggestions || []).join(" / ")),
  );
  const reason = directed.assistance_used ? ""
    : directed.skipped_reason === "original_mode" ? "「そのまま」を使いました。"
    : "演出補助を使えなかったため、元の文章をそのまま使います。";
  byId("director-plan-note").textContent = reason;
  state.directorPlan = directed.assistance_used ? plan : null;
}

function creativeProblem() {
  const scene = creativeEntries("scenes").find((entry) => entry.id === state.creative.scene);
  if (!scene) return "シーンを選び直してください。";
  if (!creativeEntries("poses").some((entry) => entry.id === state.creative.pose)) {
    return "ポーズを選び直してください。";
  }
  if (!scene.compatible_poses.includes(state.creative.pose)) {
    return "選んだシーンとポーズは組み合わせられません。";
  }
  return "";
}

function profileById(id) {
  return state.profiles.find((profile) => profile.id === id) || null;
}

function collectionById(id) {
  return state.referenceCollections.find((collection) => collection.id === id) || null;
}

function selectedProfileReferences() {
  const references = new Map();
  for (const profileId of [state.characterProfileId, state.styleProfileId]) {
    const profile = profileById(profileId);
    const collection = profile ? collectionById(profile.reference_collection_id) : null;
    if (!profile || !collection) continue;
    collection.asset_ids.forEach((assetId, index) => {
      if (references.has(assetId)) return;
      const inferred = collection.roles?.[assetId] || (profile.kind === "character" ? "identity" : "style");
      references.set(assetId, {
        asset_id: assetId,
        role: inferred,
        strength: 1,
        label: `${profile.name} ・ 参照 ${index + 1}`,
      });
    });
  }
  return [...references.values()].map((reference) => ({
    ...reference,
    ...(state.referenceOverrides.get(reference.asset_id) || {}),
  }));
}

function profileOption(profile) {
  const option = document.createElement("option");
  option.value = profile.id;
  option.textContent = profile.name;
  return option;
}

function renderProfileChoices() {
  const characters = state.profiles.filter((profile) => profile.kind === "character");
  const styles = state.profiles.filter((profile) => profile.kind === "style");
  for (const [id, items, value] of [
    ["character-profile", characters, state.characterProfileId],
    ["style-profile", styles, state.styleProfileId],
  ]) {
    const select = byId(id);
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "使わない";
    select.replaceChildren(empty, ...items.map(profileOption));
    select.value = value;
  }
  const references = selectedProfileReferences();
  byId("profile-choice-note").textContent = state.profiles.length
    ? references.length
      ? `参照 ${references.length} 枚を使います。`
      : "必要なときだけ選べます。"
    : "登録済みのキャラ・画風はまだありません。";
  renderAdvancedReferenceRoles();
  renderReferenceIntelligence();
  renderProfileList();
}

/* ── モデルを探す ────────────────────────────────────────────────────── */

/* repository ID を手で入力させるのは、名前を既に知っている人にしか使えない。
   探すところから引き受ける。ただし探せることと入れてよいことは別なので、
   表から直接は取り込まず、必ず中身とライセンスの確認へ渡す。 */

/* モバイルでは横に伸ばさず積み上げる。列名がないと、積んだ途端に
   「14.9 GB」が何の数字なのか分からなくなるので、各セルに持たせる。 */
function labelled(cell, label) {
  cell.dataset.label = label;
  return cell;
}

function formatCount(value) {
  const count = Number(value) || 0;
  if (count >= 1_000_000) return `${(count / 1_000_000).toFixed(1)}M`;
  if (count >= 1_000) return `${(count / 1_000).toFixed(1)}k`;
  return String(count);
}

function formatDay(value) {
  const parsed = Date.parse(value || "");
  if (!Number.isFinite(parsed)) return "-";
  const date = new Date(parsed);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}


/* その LoRA を載せられる系統が手元にあるか。無いものを黙って並べると、
   40MB のつもりで押した先で 7GB の土台が要ると知ることになる。 */
function catalogFits(item) {
  if (item.model_type !== "lora") return true;
  const family = normalizeFamily(item.base_model);
  return !family || (state.installedFamilies || []).includes(family);
}

/* 系統の正規化は backend が持っている判断で、ここでは同じ結果を出すための
   最小限だけを見る。判定そのものは取り込みのときに backend が行う。 */
function normalizeFamily(value) {
  const folded = String(value || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  for (const [prefix, key] of [["sd35","sd35"],["sd3","sd3"],["sdxl","sdxl"],["pony","pony"],
      ["illustrious","illustrious"],["noobai","noobai"],["sd15","sd15"],["sd20","sd20"],
      ["sd21","sd21"],["sd1","sd15"],["sd2","sd21"]]) {
    if (folded.startsWith(prefix)) return key;
  }
  return "";
}

function catalogRow(item) {
  const row = document.createElement("tr");
  const name = document.createElement("td");
  name.className = "name";
  const title = document.createElement("div");
  title.textContent = item.repo_id;
  name.append(title);
  // 「条件を確認」では何を確認するのか分からない。押す前に分かる位置で、
  // 配布元での同意が要ることそのものを言う。押した先の言葉は 1 つでよい。
  if (item.gated) {
    const gate = document.createElement("span");
    gate.className = "tag";
    gate.textContent = "要同意";
    gate.title = "配布元で利用条件に同意しないと取り込めません。";
    name.append(gate);
  }
  /* LoRA は載せる先が要る。どの系統のものかは、名前の次に効く 1 行なので
     タグより前に出す。載せられないものは押す前に分かるようにする。 */
  if (item.base_model) {
    const base = document.createElement("span");
    base.className = "tag base";
    base.textContent = item.base_model;
    if (item.model_type === "lora") {
      const fits = catalogFits(item);
      base.classList.add(fits ? "fits" : "unfit");
      base.title = fits
        ? "この系統のモデルが手元にあります。そのまま載せられます。"
        : "この系統のモデルが手元にありません。取り込むときに土台も要ります。";
    }
    name.append(base);
  }
  for (const word of (item.trigger_words || []).slice(0, 2)) {
    const trigger = document.createElement("span");
    trigger.className = "tag trigger";
    trigger.textContent = word;
    trigger.title = "この語を prompt に入れないと効きません。自動で足します。";
    name.append(trigger);
  }
  for (const tag of (item.tags || []).filter((value) => !value.includes(":")).slice(0, 3)) {
    const chip = document.createElement("span");
    chip.className = "tag";
    chip.textContent = tag;
    name.append(chip);
  }
  const downloads = document.createElement("td");
  downloads.className = "num";
  downloads.textContent = formatCount(item.downloads);
  const likes = document.createElement("td");
  likes.className = "num";
  likes.textContent = formatCount(item.likes);
  const updated = document.createElement("td");
  updated.textContent = formatDay(item.last_modified);
  const license = document.createElement("td");
  license.textContent = item.license || "-";
  // 押す前に一番効く 1 行。何 GB 落ちてきて、この端末に載るのか。
  // 配布元の一覧は容量そのものを返さないので、重みの要素数と型から出した
  // 下限を出す。設定や複数版を含めた実配布物はこれより大きくなる。
  const size = document.createElement("td");
  size.className = "num";
  size.textContent = item.weight_bytes ? `約 ${formatBytes(item.weight_bytes)}` : "不明";
  if (item.weight_bytes) {
    // GGUF は量子化の版を全部足した数で、実際に落とす 1 本より必ず大きい。
    // safetensors 側は逆に重みだけの数で、設定や別版を含めると増える。
    size.title = item.weight_precision === "GGUF"
      ? "配布物全体。量子化の版をすべて含むので、実際に落とす量はこれより小さくなります。"
      : `${item.weight_precision || "重み"} の合計。設定や別版を含めると増えます。`;
  }
  labelled(downloads, "ダウンロード");
  labelled(likes, "お気に入り");
  labelled(updated, "更新");
  labelled(license, "ライセンス");
  labelled(size, "容量");
  updated.classList.add("secondary");
  const action = document.createElement("td");
  if (item.catalog_state === "installed") {
    const note = document.createElement("span");
    note.className = "tag";
    note.textContent = "導入済み";
    note.title = "この端末に落として使える状態です。";
    action.append(note);
  } else if (item.catalog_state === "listed" || item.already_added) {
    // 登録しただけでは何も落ちてこない。「一覧にあります」と書いても、
    // その一覧は既定で「導入済み」に絞られていて見つからない。取り込んだ人が
    // 次にしたいのは落とすことなので、ここから直接できるようにする。
    const download = document.createElement("button");
    download.type = "button";
    download.dataset.installRepo = item.repo_id;
    download.textContent = "ダウンロード";
    download.title = "一覧に登録済みです。この端末へ落とします。";
    action.append(download);
  } else {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.inspectRepo = item.repo_id;
    // 何が起きるか分かる言葉にする。取り込みの入口だと言う。
    button.textContent = "追加する";
    action.append(button);
  }
  row.append(labelled(name, "モデル"), size, downloads, likes, updated, license,
             labelled(action, "操作"));
  return row;
}

/* 30 件を一息に積むと、下まで送らないと何があるのか分からない。1 画面ぶんに
   区切って、行き来できるようにする。件数は表示のためだけに持ち、検索の
   往復は増やさない（結果は既に手元にある）。 */
const CATALOG_PAGE_SIZE = 12;

function renderCatalogPage() {
  const items = state.catalogResults || [];
  const pages = Math.max(1, Math.ceil(items.length / CATALOG_PAGE_SIZE));
  state.catalogPage = Math.min(Math.max(0, state.catalogPage || 0), pages - 1);
  const start = state.catalogPage * CATALOG_PAGE_SIZE;
  renderCatalogResults(items.slice(start, start + CATALOG_PAGE_SIZE));
  const pager = byId("catalog-pager");
  pager.hidden = items.length <= CATALOG_PAGE_SIZE;
  byId("catalog-prev").disabled = state.catalogPage === 0;
  byId("catalog-next").disabled = state.catalogPage >= pages - 1;
  byId("catalog-page").textContent =
    `${start + 1}–${Math.min(items.length, start + CATALOG_PAGE_SIZE)} / ${items.length} 件`;
}

function clearCatalogResults() {
  state.catalogResults = [];
  state.catalogPage = 0;
  byId("catalog-results").hidden = true;
  byId("catalog-results").replaceChildren();
  byId("catalog-pager").hidden = true;
  byId("catalog-empty").hidden = true;
}

function renderCatalogResults(items) {
  const holder = byId("catalog-results");
  const empty = byId("catalog-empty");
  if (!items.length) {
    holder.hidden = true;
    empty.hidden = false;
    empty.textContent = "条件に合うモデルは見つかりませんでした。";
    return;
  }
  empty.hidden = true;
  holder.hidden = false;
  const table = document.createElement("table");
  table.className = "catalog";
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const label of ["モデル", "容量", "DL", "★", "更新", "ライセンス", ""]) {
    const cell = document.createElement("th");
    cell.textContent = label;
    headRow.append(cell);
  }
  head.append(headRow);
  const body = document.createElement("tbody");
  body.append(...items.map(catalogRow));
  table.append(head, body);
  holder.replaceChildren(table);
}



/* ── LoRA の選択 ──────────────────────────────────────────────────────── */

/* いま LoRA を載せられる系統。土台を指定していればそれが決め、指定していなければ
   最初に選んだ LoRA が決める。載せられないときは null を返す。空文字（制約なし）と
   区別できないと、載らない組み合わせに強さのつまみを出すことになる。 */
function loraTargetFamily() {
  const base = chosenBaseModel();
  if (base) return base.supports_lora ? (normalizeFamily(base.base_model) || null) : null;
  const selected = (state.selectedLoras || [])[0];
  if (!selected) return "";
  return normalizeFamily(
    state.modelCatalog.find((item) => item.model_id === selected.model_id)?.base_model);
}

/* LoRA が土台を決める。利用者に先に checkpoint を選ばせるのではなく、最初に
   選んだ LoRA と同じ系統だけを追加候補にする。土台を自分で指定したときは
   その系統が先に決まるので、載せられるものだけを候補にする。 */
function loraCandidates() {
  const target = loraTargetFamily();
  if (target === null) return [];
  return state.modelCatalog.filter((model) =>
    model.kind === "lora" && model.installed
    && (!target || normalizeFamily(model.base_model) === target));
}

/* 土台を変えたら、載らなくなった LoRA の選択は残さない。残すと、画面に出て
   いない選択のまま生成して backend に断られる。 */
function dropIncompatibleLoras() {
  const usable = new Set(loraCandidates().map((lora) => lora.model_id));
  const kept = (state.selectedLoras || []).filter((item) => usable.has(item.model_id));
  const dropped = (state.selectedLoras || []).length - kept.length;
  state.selectedLoras = kept;
  return dropped;
}

function loraPickerNote(installed, candidates) {
  const base = chosenBaseModel();
  if (candidates.length) {
    if ((state.selectedLoras || []).length) {
      return base
        ? `${base.display_name || base.model_id} に載せられる LoRA だけを追加できます。`
        : "同じ系統の LoRA だけを追加できます。土台は自動で選びます。";
    }
    return base
      ? "起動語は自動で足します。"
      : "LoRA を選ぶだけで、互換する土台と起動語を自動適用します。";
  }
  const families = [...new Set(installed.map((lora) => lora.base_model).filter(Boolean))];
  const forWhat = families.length ? `導入済みの LoRA は ${families.join(" / ")} 用です。` : "";
  if (base && !base.supports_lora) {
    return `${base.display_name || base.model_id} は LoRA を載せられません。${forWhat}`;
  }
  if (base) {
    return `${base.display_name || base.model_id}（${base.base_model || "系統不明"}）`
      + `に載せられる LoRA がありません。${forWhat}`;
  }
  return `一緒に使える LoRA がありません。${forWhat}`;
}

function renderLoraPicker() {
  const block = byId("lora-picker");
  if (!block) return;
  const installed = state.modelCatalog.filter((model) => model.kind === "lora" && model.installed);
  block.hidden = installed.length === 0;
  if (block.hidden) return;
  const candidates = loraCandidates();
  byId("lora-picker-note").textContent = loraPickerNote(installed, candidates);
  byId("lora-list").replaceChildren(...candidates.map((lora) => {
    const row = document.createElement("div");
    row.className = "lora-row";
    const label = document.createElement("label");
    label.className = "check";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.dataset.loraId = lora.model_id;
    box.checked = (state.selectedLoras || []).some((item) => item.model_id === lora.model_id);
    const name = document.createElement("span");
    name.textContent = lora.display_name || lora.model_id;
    label.append(box, name);
    const base = document.createElement("span");
    base.className = "tag base";
    base.textContent = lora.base_model || "系統不明";
    label.append(base);
    for (const word of (lora.trigger_words || []).slice(0, 2)) {
      const trigger = document.createElement("span");
      trigger.className = "tag trigger";
      trigger.textContent = word;
      trigger.title = "この語を prompt に自動で足します。";
      label.append(trigger);
    }
    /* 強さは、載せると決めた LoRA にしか意味が無い。選ぶ前から出しても
       動かす先が無く、載らない組み合わせにも出ているように見える。 */
    if (!box.checked) {
      row.classList.add("unused");
      row.append(label);
      return row;
    }
    const weight = document.createElement("input");
    weight.type = "range";
    weight.min = "0";
    weight.max = "2";
    weight.step = "0.05";
    weight.value = String(
      (state.selectedLoras || []).find((item) => item.model_id === lora.model_id)?.weight ?? 1);
    weight.dataset.loraWeight = lora.model_id;
    weight.setAttribute("aria-label", `${lora.display_name || lora.model_id} の強さ`);
    const shown = document.createElement("span");
    shown.className = "lora-weight";
    shown.textContent = Number(weight.value).toFixed(2);
    row.append(label, weight, shown);
    return row;
  }));
}

/* 選んだ LoRA を要求の形にする。強さ 0 は「載せない」ではなく「効かせない」
   なので、選ばれている限り送る。外したいなら選択を外す。 */
function selectedLoras() {
  return (state.selectedLoras || []).slice(0, 4);
}

/* ── 配布元の切り替え ────────────────────────────────────────────────── */

/* 既定は Civitai。実際に絵を作るのに使われている調整済みのモデルはそちらに
   集まっていて、Hugging Face 側には基盤モデルが並ぶ。 */
const CATALOG_SOURCES = {
  civitai: {
    note: "調整済みの checkpoint が並びます。1 モデル = 1 ファイルで、使う前に「評価」が要ります。",
    // Civitai の検索は画風タグを持たない。使えない絞り込みを出さない。
    styles: false,
  },
  huggingface: {
    note: "diffusers 形式の基盤モデルが並びます。",
    styles: true,
  },
};

function catalogType() {
  const chosen = byId("catalog-type")?.querySelector('[aria-checked="true"]');
  return chosen?.dataset.modelType || "checkpoint";
}

function renderCatalogType() {
  const holder = byId("catalog-type");
  if (!holder) return;
  // Hugging Face 側に LoRA の取り込み経路が無い。押せる形で出しておくと、
  // 押した先で断られる。
  const civitai = catalogSource() === "civitai";
  holder.hidden = !civitai;
  if (!civitai) {
    for (const chip of holder.children) {
      chip.setAttribute("aria-checked", String(chip.dataset.modelType === "checkpoint"));
    }
  }
}

function catalogSource() {
  const chosen = byId("catalog-source")?.querySelector('[aria-checked="true"]');
  return chosen?.dataset.source || "civitai";
}

function renderCatalogSource() {
  const holder = byId("catalog-source");
  if (!holder) return;
  const chosen = state.preferences.model_source || "civitai";
  for (const chip of holder.children) {
    chip.setAttribute("aria-checked", String(chip.dataset.source === chosen));
  }
  const shape = CATALOG_SOURCES[chosen] || CATALOG_SOURCES.civitai;
  renderCatalogType();
  byId("catalog-source-note").textContent = catalogType() === "lora"
    ? "LoRA を選ぶと、必要な土台と起動語も自動で準備します。"
    : shape.note;
  // 効かない絞り込みを出しておくと、絞ったつもりの結果を見ることになる。
  const style = byId("catalog-style");
  if (style?.parentElement) style.parentElement.hidden = !shape.styles;
}

async function searchCatalog() {
  const empty = byId("catalog-empty");
  empty.hidden = false;
  empty.textContent = "検索しています…";
  byId("catalog-results").hidden = true;
  let found;
  try {
    found = await call("models.custom.search", {
      source: catalogSource(),
      model_type: catalogType(),
      query: byId("catalog-query").value,
      sort: byId("catalog-sort").value,
      style: byId("catalog-style").value,
    });
  } catch (error) {
    empty.textContent = error?.message || "検索できませんでした。";
    return;
  }
  state.installedFamilies = found.installed_families || [];
  const rows = (found.items || []).map((item) => ({...item, model_type: catalogType()}));
  state.catalogResults = rows;
  state.catalogPage = 0;
  if (!state.catalogResults.length && rows.length) {
    empty.hidden = false;
    empty.textContent = "手元のモデルに載せられるものはありませんでした。絞り込みを外すと全部出ます。";
    return;
  }
  renderCatalogPage();
}

/* ── HuggingFace からモデルを追加 ────────────────────────────────────── */

/* 同梱 catalog は「版が固定され、digest が検証でき、VRAM を実測済み」だから
   信頼できる。一覧に無いモデルのために、その規則を緩めるのではなく、
   明示的な第 2 経路を足す。取り込む前に必ず中身とライセンスを見せる。 */

let customResolution = null;

function customFact(term, value) {
  const wrap = document.createElement("div");
  const dt = document.createElement("dt");
  dt.textContent = term;
  const dd = document.createElement("dd");
  dd.textContent = value;
  wrap.append(dt, dd);
  return wrap;
}

function renderCustomResolution(resolution) {
  const holder = byId("custom-result");
  holder.hidden = false;
  holder.replaceChildren();
  const facts = document.createElement("dl");
  facts.className = "facts";
  facts.append(
    customFact("repository", resolution.repo_id),
    customFact("固定した版", resolution.revision),
    customFact("重みファイル", `${resolution.weight_count} 個 · ${formatBytes(resolution.total_bytes)}`),
    customFact("ライセンス", resolution.license),
  );
  holder.append(facts);

  for (const warning of resolution.warnings || []) {
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = `⚠ ${warning}`;
    holder.append(note);
  }

  if (!resolution.within_download_cap) {
    const blocked = document.createElement("p");
    blocked.className = "hint";
    blocked.textContent = "上限を超えているため取り込めません。";
    holder.append(blocked);
    return;
  }

  const dependency = resolution.dependency;
  if (dependency) {
    const title = document.createElement("p");
    title.className = "settings-check-title";
    title.textContent = "必要な土台も自動でダウンロードします";
    const body = document.createElement("p");
    body.className = "settings-reason";
    body.textContent = `${dependency.display_name} · ${formatBytes(dependency.total_bytes)} · ${dependency.license}`;
    const total = document.createElement("p");
    total.className = "hint";
    total.textContent = `合計ダウンロード: ${formatBytes(
      Number(resolution.total_bytes || 0) + Number(dependency.total_bytes || 0))}`;
    holder.append(title, body, total);
  }

  const accept = document.createElement("label");
  accept.className = "check";
  const box = document.createElement("input");
  box.type = "checkbox";
  box.id = "custom-accept";
  const licenses = dependency
    ? `LoRA「${resolution.license}」と土台「${dependency.license}」`
    : `「${resolution.license}」`;
  accept.append(box, document.createTextNode(`${licenses}の条件を確認して承諾します`));
  const add = document.createElement("button");
  add.type = "button";
  add.id = "custom-add";
  add.className = "primary";
  add.textContent = "同意してダウンロード";
  // 確認だけして止める道を残す。閉じ方が無いと、中身を見た後に検索へ戻れない。
  const cancel = document.createElement("button");
  cancel.type = "button";
  cancel.id = "custom-cancel";
  cancel.textContent = "やめる";
  const actions = document.createElement("div");
  actions.className = "split-actions";
  actions.append(cancel, add);
  holder.append(accept, actions);
}

/* 検索結果から選んだものを、中身とライセンスの確認へ渡す。
   repository の手入力欄は使われないため撤去した（利用者判断）。検索に
   出てこない版が要る場合は CLI から入れる。 */
async function resolveCustomModel(repoId, revision = "main") {
  const error = byId("custom-error");
  error.hidden = true;
  customResolution = null;
  try {
    customResolution = await call("models.custom.resolve", {repo_id: repoId, revision});
  } catch (failure) {
    error.hidden = false;
    error.textContent = failure?.message || "中身を確かめられませんでした。";
    return;
  }
  renderCustomResolution(customResolution);
}

async function addCustomModel() {
  const error = byId("custom-error");
  error.hidden = true;
  if (!customResolution) return;
  if (!byId("custom-accept")?.checked) {
    error.hidden = false;
    error.textContent = "ライセンスを承諾してください。";
    return;
  }
  try {
    const added = await call("models.custom.add", {
      repo_id: customResolution.repo_id,
      revision: customResolution.revision,
      display_name: customResolution.repo_id,
      license_acceptance: customResolution.license,
      ...(customResolution.dependency ? {dependency: {
        repo_id: customResolution.dependency.repo_id,
        revision: customResolution.dependency.revision,
        display_name: customResolution.dependency.display_name,
        license_acceptance: customResolution.dependency.license,
      }} : {}),
    });
    for (const operation of added.operations || []) {
      state.modelOperations.set(operation.id, operation);
    }
    if ((added.operations || []).length) {
      await call("models.operations.watch", {
        operation_ids: added.operations.map((operation) => operation.id),
      });
    }
  } catch (failure) {
    error.hidden = false;
    error.textContent = failure?.message || "取り込めませんでした。";
    return;
  }
  byId("custom-result").hidden = true;
  customResolution = null;
  await refreshSession(["models", "model_catalog"]);
}

/* ── 配布用にまとめる（asset.pack） ──────────────────────────────────── */

function project3dFile() {
  return byId("project-3d-file").files[0] || null;
}

function project3dSelection() {
  const file = project3dFile();
  if (file) return {file, name: file.name, asset: null};
  if (state.project3dAsset) {
    return {file: null, name: state.project3dName || "ControlDeckのGLB", asset: state.project3dAsset};
  }
  return null;
}

function render3dProject() {
  const capability = state.capabilities["asset.3d_project_pack"] || {};
  const available = capability.state === "available";
  const selection = project3dSelection();
  byId("project-3d-section").hidden = !available;
  byId("project-3d-file-text").textContent = selection ? `GLB: ${selection.name}` : "＋ GLBを選ぶ";
  byId("project-3d-file-label").classList.toggle("filled", Boolean(selection));
  byId("project-3d-host-file").hidden = !state.bridgePort;
  byId("project-3d-clear").hidden = !selection;
  // 実行操作は runtime と入力の両方がそろったときだけ見せる。
  byId("project-3d-submit").hidden = !available || !selection;
  byId("project-3d-options").hidden = !available || !selection || state.mode !== "advanced";
  if (!available) {
    byId("project-3d-status").textContent = CAPABILITY_REASON[capability.reason] || "3D整形を利用できません";
  } else if (!selection) {
    byId("project-3d-status").textContent = "";
  }
}

function optionalProjectNumber(id) {
  const text = byId(id).value.trim();
  return text === "" ? null : Number(text);
}

function project3dOptions() {
  if (state.mode !== "advanced") return {schema_version: "3d.compile-options@1"};
  const lodRatios = [1, 2, 3]
    .map((index) => optionalProjectNumber(`project-3d-lod-${index}`))
    .filter((value) => value !== null);
  if (lodRatios.some((value) => !Number.isFinite(value) || value < 0.05 || value > 0.95)
      || lodRatios.some((value, index) => index > 0 && lodRatios[index - 1] <= value)) {
    throw new Error("LOD比率は0.05〜0.95で、大きい順に指定してください。");
  }
  const merge = optionalProjectNumber("project-3d-merge-distance");
  const budget = optionalProjectNumber("project-3d-triangle-budget");
  if (merge !== null && (!Number.isFinite(merge) || merge < 0.0000001 || merge > 1)) {
    throw new Error("近接頂点の距離は0.0000001〜1mで指定してください。");
  }
  if (budget !== null && (!Number.isInteger(budget) || budget < 12 || budget > 200000)) {
    throw new Error("三角形の上限は12〜200000で指定してください。");
  }
  return {
    schema_version: "3d.compile-options@1",
    apply_transforms: true,
    repair_normals: byId("project-3d-repair-normals").checked,
    remove_degenerate: byId("project-3d-remove-degenerate").checked,
    merge_by_distance_m: merge,
    triangle_budget: budget,
    lod_ratios: lodRatios,
    collision: byId("project-3d-collision").value,
    materials: byId("project-3d-materials").value,
    preview: "fixed_workbench",
  };
}

async function submit3dProject() {
  const selection = project3dSelection();
  const error = byId("project-3d-error");
  const status = byId("project-3d-status");
  const button = byId("project-3d-submit");
  error.hidden = true;
  if (!selection) return;
  if (selection.file && (
      !selection.name.toLowerCase().endsWith(".glb")
      || selection.file.size < 1 || selection.file.size > 64 * 1024 * 1024)) {
    error.hidden = false;
    error.textContent = "64MiB以下のGLBを選んでください。";
    return;
  }
  let options;
  try { options = project3dOptions(); }
  catch (failure) {
    error.hidden = false;
    error.textContent = failure.message;
    return;
  }
  button.disabled = true;
  status.textContent = "GLBを取り込んでいます…";
  try {
    state.project3dAsset = selection.asset || state.project3dAsset
      || await importFile(selection.file, "source", null, "model/gltf-binary");
    status.textContent = "3Dプロジェクトを受け付けています…";
    await call("jobs.create", {
      operation: "asset.pack",
      intent: `${selection.name} をプロジェクト用GLBに整える`,
      profile: "3d.project.glb",
      inputs: [{asset_id: state.project3dAsset.id}],
      constraints: {compile_options: options},
      output: {format: "zip", count: 1},
      local_only: true,
    });
    status.textContent = "受け付けました。状況で進み具合を確認できます。";
    activate("activity");
    await loadActivity();
  } catch (failure) {
    error.hidden = false;
    error.textContent = failure?.message || "3Dプロジェクトを作れませんでした。";
  } finally {
    button.disabled = false;
  }
}

async function pickHost3dProject() {
  const error = byId("project-3d-error");
  const status = byId("project-3d-status");
  error.hidden = true;
  status.textContent = "ControlDeckでGLBを選んでください。";
  try {
    const picked = await callHost("host.file.pick", {mode: "file", title: "GLBを選択"});
    if (!picked?.grant_id) return;
    const imported = await call("assets.import_grant", {
      grant_id: picked.grant_id,
      media_type: "model/gltf-binary",
      purpose: "source",
    });
    state.project3dAsset = imported;
    state.project3dName = picked.name || imported.suggested_filename || "ControlDeckのGLB";
    byId("project-3d-file").value = "";
    status.textContent = "ControlDeckのGLBを取り込みました。";
    render3dProject();
  } catch (failure) {
    error.hidden = false;
    error.textContent = failure?.message || "ControlDeckからGLBを取り込めませんでした。";
    status.textContent = "";
  }
}

/* backend には asset.pack があるのに、画面から起動する経路が無かった。
   スロットは profile が宣言しているので、その宣言だけを根拠に組む。
   media 固有のスロット名をここに書き写さない。 */

const pack = {profile: null, slots: [], assignments: new Map(), active: ""};

function packSlots(profile) {
  const slots = [];
  for (const name of profile.base_names || []) slots.push({layer: "base", name});
  for (const name of profile.eye_slots || []) slots.push({layer: "eyes", name});
  for (const name of profile.mouth_slots || []) slots.push({layer: "mouth", name});
  return slots;
}

const PACK_LAYER_LABEL = {base: "土台", eyes: "目", mouth: "口"};

function slotKey(slot) {
  return `${slot.layer}/${slot.name}`;
}

function renderPackProfiles() {
  const select = byId("pack-profile");
  const packs = state.domainProfiles.filter((profile) => packSlots(profile).length > 0);
  byId("pack-section").hidden = state.mode !== "advanced" || packs.length === 0;
  select.replaceChildren(...packs.map((profile) => {
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = profile.id;
    return option;
  }));
  byId("pack-note").textContent = packs.length
    ? `${packs.length} 種類のまとめ方が使えます。`
    : "";
}

function renderPackSlots() {
  const holder = byId("pack-slots");
  holder.replaceChildren(...pack.slots.map((slot) => {
    const key = slotKey(slot);
    const row = document.createElement("article");
    row.className = "row";
    row.dataset.status = pack.assignments.has(key) ? "succeeded" : "queued";
    const info = document.createElement("div");
    const title = document.createElement("p");
    title.className = "t";
    title.textContent = `${PACK_LAYER_LABEL[slot.layer] || slot.layer} · ${slot.name}`;
    const sub = document.createElement("p");
    sub.className = "s";
    sub.textContent = pack.assignments.get(key) || "未割り当て";
    info.append(title, sub);
    const side = document.createElement("div");
    side.className = "row-side";
    const choose = document.createElement("button");
    choose.type = "button";
    choose.dataset.packSlot = key;
    choose.setAttribute("aria-pressed", String(pack.active === key));
    choose.textContent = pack.active === key ? "選択中" : "選ぶ";
    side.append(choose);
    row.append(info, side);
    return row;
  }));
  const done = pack.assignments.size;
  byId("pack-progress").textContent = `${done}/${pack.slots.length} 割り当て済み`;
}

async function renderPackLibrary() {
  const holder = byId("pack-library");
  holder.replaceChildren();
  let page;
  try { page = await call("library.list", {limit: 60}); } catch { return; }
  const strip = document.createElement("div");
  strip.className = "strip";
  for (const item of page.items || []) {
    strip.append(await thumbnailButton(item.asset_id, () => {
      if (!pack.active) return;
      pack.assignments.set(pack.active, item.asset_id);
      const next = pack.slots.find((slot) => !pack.assignments.has(slotKey(slot)));
      pack.active = next ? slotKey(next) : "";
      renderPackSlots();
    }, item.thumbnail));
  }
  holder.append(strip);
}

async function openPackDialog() {
  const profile = state.domainProfiles.find((item) => item.id === byId("pack-profile").value);
  if (!profile) return;
  pack.profile = profile;
  pack.slots = packSlots(profile);
  pack.assignments = new Map();
  pack.active = pack.slots.length ? slotKey(pack.slots[0]) : "";
  byId("pack-dialog-title").textContent = `配布用にまとめる · ${profile.id}`;
  byId("pack-error").hidden = true;
  byId("pack-name").value = "";
  renderPackSlots();
  byId("pack-dialog").showModal();
  await renderPackLibrary();
}

async function submitPack() {
  const error = byId("pack-error");
  error.hidden = true;
  const name = byId("pack-name").value.trim();
  if (!name) {
    error.hidden = false;
    error.textContent = "まとめの名前を入れてください。";
    return;
  }
  const missing = pack.slots.filter((slot) => !pack.assignments.has(slotKey(slot)));
  if (missing.length) {
    error.hidden = false;
    error.textContent = `まだ ${missing.length} 個のスロットが空です。`;
    return;
  }
  const entries = pack.slots.map((slot) => ({
    asset_id: pack.assignments.get(slotKey(slot)), layer: slot.layer, name: slot.name,
  }));
  const seen = [...new Set(entries.map((entry) => entry.asset_id))];
  try {
    await call("jobs.create", {
      operation: "asset.pack",
      intent: `${pack.profile.id} を ${name} としてまとめる`,
      profile: pack.profile.id,
      inputs: seen.map((asset_id) => ({asset_id})),
      constraints: {entries, pack_name: name},
      output: {format: "zip", count: 1},
      local_only: true,
    });
  } catch (failure) {
    error.hidden = false;
    error.textContent = failure?.message || "まとめられませんでした。";
    return;
  }
  byId("pack-dialog").close();
  activate("activity");
  await loadActivity();
}

/* ── キャラ・画風の登録 ───────────────────────────────────────────────── */

/* backend には profiles.create / reference_collections.create があるのに、
   画面には「選ぶ」しか無く「作る」経路が無かった（G3 の UI が未着手）。
   参照コレクションは profile と一体で作る。利用者に 2 段階を意識させない。 */

const profileDraft = {kind: "character", assetIds: []};

function renderProfileList() {
  const list = byId("profile-list");
  list.replaceChildren(...state.profiles.map((profile) => {
    const row = document.createElement("article");
    row.className = "row";
    row.dataset.profileId = profile.id;
    const info = document.createElement("div");
    const title = document.createElement("p");
    title.className = "t";
    title.textContent = profile.name;
    const sub = document.createElement("p");
    sub.className = "s";
    const collection = state.referenceCollections
      .find((item) => item.id === profile.reference_collection_id);
    sub.textContent = [
      profile.kind === "character" ? "キャラ" : "画風",
      collection ? `参照 ${collection.asset_ids.length} 枚` : "参照なし",
      profile.description,
    ].filter(Boolean).join(" · ");
    info.append(title, sub);
    const side = document.createElement("div");
    side.className = "row-side";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.dataset.deleteProfile = profile.id;
    remove.textContent = "削除";
    side.append(remove);
    row.append(info, side);
    return row;
  }));
  byId("profile-empty").hidden = state.profiles.length > 0;
}

function openProfileDialog(kind) {
  profileDraft.kind = kind;
  profileDraft.assetIds = [];
  byId("profile-dialog-title").textContent = kind === "character" ? "キャラを登録" : "画風を登録";
  byId("profile-form").reset();
  for (const holder of document.querySelectorAll("[data-profile-kind]")) {
    holder.hidden = holder.dataset.profileKind !== kind;
  }
  byId("profile-dialog-error").hidden = true;
  void renderProfileReferencePicker();
  byId("profile-dialog").showModal();
}

async function renderProfileReferencePicker() {
  const holder = byId("profile-references");
  holder.replaceChildren();
  let page;
  try { page = await call("library.list", {limit: 24}); } catch { return; }
  const strip = document.createElement("div");
  strip.className = "strip";
  const update = () => {
    const chosen = profileDraft.assetIds.length;
    byId("profile-reference-count").textContent = `${chosen} 枚選択中`;
    // 上限に達したら、押せない枠を並べたままにせず選べないことを示す。
    for (const button of strip.children) {
      const selected = profileDraft.assetIds.includes(button.dataset.assetId);
      button.setAttribute("aria-pressed", String(selected));
      button.disabled = !selected && chosen >= 4;
    }
  };
  for (const item of page.items || []) {
    const button = await thumbnailButton(item.asset_id, () => {
      const index = profileDraft.assetIds.indexOf(item.asset_id);
      if (index >= 0) profileDraft.assetIds.splice(index, 1);
      else if (profileDraft.assetIds.length < 4) profileDraft.assetIds.push(item.asset_id);
      update();
    }, item.thumbnail);
    strip.append(button);
  }
  holder.append(strip);
  update();
  if (!(page.items || []).length) {
    const note = document.createElement("p");
    note.className = "hint";
    note.textContent = "参照に使える画像がまだありません。";
    holder.append(note);
  }
}

function splitTraits(value) {
  return String(value || "").split(/[、,]/).map((item) => item.trim()).filter(Boolean).slice(0, 16);
}

function profileDefinition() {
  if (profileDraft.kind === "character") {
    return {character: {
      appearance: byId("profile-appearance").value.trim(),
      clothing: byId("profile-clothing").value.trim(),
      distinguishing_features: splitTraits(byId("profile-features").value),
    }};
  }
  return {style: {
    art_style: byId("profile-art-style").value.trim(),
    linework: byId("profile-linework").value.trim(),
    coloring: byId("profile-coloring").value.trim(),
  }};
}

async function submitProfile(event) {
  event.preventDefault();
  const error = byId("profile-dialog-error");
  error.hidden = true;
  const name = byId("profile-name").value.trim();
  const definition = profileDefinition();
  const required = profileDraft.kind === "character"
    ? definition.character.appearance : definition.style.art_style;
  if (!name || !required) {
    error.hidden = false;
    error.textContent = profileDraft.kind === "character"
      ? "名前と見た目を入れてください。" : "名前と画風を入れてください。";
    return;
  }
  try {
    let collectionId = null;
    if (profileDraft.assetIds.length) {
      const collection = await call("reference_collections.create", {
        name: `${name} の参照`,
        asset_ids: profileDraft.assetIds,
      });
      collectionId = collection.id;
    }
    await call("profiles.create", {
      kind: profileDraft.kind,
      name,
      description: byId("profile-description").value.trim(),
      ...(collectionId ? {reference_collection_id: collectionId} : {}),
      ...definition,
    });
  } catch (failure) {
    error.hidden = false;
    error.textContent = failure?.message || "登録できませんでした。";
    return;
  }
  byId("profile-dialog").close();
  // 一覧と選択肢はサーバの session.changed が運ぶが、操作直後は待たせない。
  await refreshSession(["profiles", "reference_collections"]);
}

async function deleteProfile(profileId) {
  const failure = byId("profile-error");
  failure.hidden = true;
  try {
    await call("profiles.delete", {profile_id: profileId});
  } catch (error) {
    failure.hidden = false;
    failure.textContent = error?.message || "削除できませんでした。";
    return;
  }
  if (state.characterProfileId === profileId) state.characterProfileId = "";
  if (state.styleProfileId === profileId) state.styleProfileId = "";
  await refreshSession(["profiles", "reference_collections"]);
}

function referenceTarget() {
  if (attachedFile()) return state.sourceAsset ? {asset_id: state.sourceAsset.id, label: "追加した画像"} : null;
  const reference = selectedProfileReferences()[0];
  return reference ? {asset_id: reference.asset_id, label: reference.label} : null;
}

function resetReferenceAnalysis({keepSource = false} = {}) {
  state.referenceAnalysis = null;
  state.referenceFocus = "overall";
  if (!keepSource) state.sourceAsset = null;
  renderReferenceIntelligence();
}

function referenceAnalysisRequest() {
  const target = referenceTarget();
  return state.referenceAnalysis?.analysis && target
    && state.referenceAnalysis.asset_id === target.asset_id
    ? [{asset_id: target.asset_id, focus: state.referenceFocus}]
    : [];
}

function renderReferenceIntelligence() {
  const holder = byId("reference-intelligence");
  const hasImage = Boolean(attachedFile() || selectedProfileReferences().length);
  holder.hidden = !hasImage;
  if (!hasImage) return;
  for (const button of holder.querySelectorAll("[data-reference-focus]")) {
    button.setAttribute("aria-checked", String(button.dataset.referenceFocus === state.referenceFocus));
  }
  const summary = byId("reference-analysis-summary");
  const result = state.referenceAnalysis;
  summary.hidden = !result;
  if (!result) {
    byId("reference-analysis-note").textContent = attachedFile()
      ? "追加した画像を、必要な観点だけ読み取れます。"
      : "選んだキャラ・画風の先頭の参照画像を読み取ります。";
    return;
  }
  const facts = result.facts || {};
  const analysis = result.analysis;
  const colors = (facts.dominant_colors || []).slice(0, 4).map((item) => item.hex).join(" / ");
  const action = analysis ? actionSummary(analysis.action_state) : "";
  const values = {
    overall: analysis ? [analysis.subject?.kind, action, analysis.scene, analysis.composition].filter(Boolean).join(" / ") : "",
    identity: analysis ? [analysis.subject?.kind, ...(analysis.subject?.identity_traits || []), ...(analysis.subject?.appearance_traits || [])].filter(Boolean).join(" / ") : "",
    pose: action,
    palette: colors,
    composition: analysis?.composition || "",
    style: (analysis?.style || []).join(" / "),
  };
  summary.textContent = values[state.referenceFocus] || `${facts.width}×${facts.height}${colors ? ` / ${colors}` : ""}`;
  byId("reference-analysis-note").textContent = analysis
    ? `${result.analysis_cache_hit ? "保存済み解析" : "画像解析"}を「整える」「演出を任せる」で使えます。`
    : "寸法と色は確認できました。内容の解析はControlDeck Visionを利用できません。";
}

async function ensureReferenceTargetAsset() {
  if (!attachedFile()) return referenceTarget();
  if (state.sourceAsset) return {asset_id: state.sourceAsset.id, label: "追加した画像"};
  byId("reference-analysis-note").textContent = "画像を取り込んでいます…";
  state.sourceAsset = await importFile(state.upload || attachedFile(), "source");
  return {asset_id: state.sourceAsset.id, label: "追加した画像"};
}

async function analyzeReferenceFocus(focus) {
  state.referenceFocus = focus;
  renderReferenceIntelligence();
  try {
    const target = await ensureReferenceTargetAsset();
    if (!target) return;
    byId("reference-analysis-note").textContent = "画像を読み取っています…";
    state.referenceAnalysis = await call("references.analyze", {asset_id: target.asset_id});
    renderReferenceIntelligence();
  } catch (error) {
    byId("reference-analysis-note").textContent = FAILURES[error?.code]?.text || "画像を読み取れませんでした。";
  }
}

async function loadProfiles() {
  await refreshSession(["profiles", "reference_collections"]);
}

function renderAdvancedReferenceRoles() {
  const holder = byId("advanced-reference-roles");
  if (!holder) return;
  const roles = Array.isArray(state.envelope?.reference_roles) ? state.envelope.reference_roles : [];
  const labels = new Map(creativeEntries("reference_roles").map((entry) => [entry.id, entry.label]));
  const references = selectedProfileReferences();
  holder.replaceChildren(...references.map((reference) => {
    const row = document.createElement("div");
    row.className = "reference-role-row";
    const name = document.createElement("span");
    name.className = "reference-name";
    name.textContent = reference.label;
    const roleLabel = document.createElement("label");
    roleLabel.textContent = "役割";
    const select = document.createElement("select");
    select.dataset.referenceRole = reference.asset_id;
    select.replaceChildren(...creativeEntries("reference_roles").map((entry) => {
      const option = creativeOption(entry);
      option.disabled = !roles.includes(entry.id);
      return option;
    }));
    select.value = reference.role;
    roleLabel.append(select);
    const strengthLabel = document.createElement("label");
    strengthLabel.textContent = "強さ";
    const strength = document.createElement("input");
    strength.type = "number";
    strength.min = "0";
    strength.max = "1";
    strength.step = "0.05";
    strength.value = String(reference.strength);
    strength.dataset.referenceStrength = reference.asset_id;
    strength.disabled = state.envelope?.supports_reference_strength !== true;
    strengthLabel.append(strength);
    row.append(name, roleLabel, strengthLabel);
    if (!roles.includes(reference.role)) {
      select.title = `${labels.get(reference.role) || reference.role} は現在のモデルでは使えません`;
    }
    return row;
  }));
  byId("advanced-reference-reason").textContent = !references.length
    ? "キャラまたは画風を選ぶと、参照ごとの役割を指定できます。"
    : state.envelope?.supports_reference_strength === true
      ? "役割と強さは job ごとに保存されます。"
      : "現在のモデルは役割に対応しますが、強さは指定できません。";
}

function applyProfileConstraints(constraints) {
  if (state.characterProfileId) constraints.character_profile_id = state.characterProfileId;
  if (state.styleProfileId) constraints.style_profile_id = state.styleProfileId;
}

function profileReferenceProblem() {
  const references = selectedProfileReferences();
  if (!references.length) return "";
  if (capabilityState("image.multi_reference_edit") === "unavailable") {
    return "キャラ・画風の参照に対応するモデルがありません。";
  }
  const direct = attachedFile() ? 1 + (state.editMode === "multi_reference" ? byId("reference-files").files.length : 0) : 0;
  const unique = new Set([...references.map((item) => item.asset_id)]);
  const total = unique.size + direct;
  const limit = Number(state.envelope?.max_reference_assets || 0);
  return total > limit ? `参照画像は合計 ${limit} 枚までです。` : "";
}

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
  byId("attach-clear").hidden = !file;
  byId("edit-block").hidden = state.createMedia === "video" || !file;
  if (!file) maskReset();
  state.upload = null;
  state.sourceAsset = null;
  state.referenceAnalysis = null;
  state.referenceFocus = "overall";
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
  if (file && state.createMedia === "image") renderEditActions();
  else selectEditMode("");
  renderSizeSection();
  renderReferenceIntelligence();
  renderCreateMedia();
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

async function importFile(file, purpose, onProgress, mediaType = file?.type) {
  if (!file || file.size < 1 || file.size > 64 * 1024 * 1024) throw {code: "invalid_import_size"};
  if (window.parent === window) {
    return call("assets.import", {purpose, media_type: mediaType, base64: await fileBase64(file)});
  }
  const upload = await call("assets.import.begin", {purpose, media_type: mediaType, size: file.size});
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
  /* 詳細設定で触った項目だけ送る。触っていない項目を送ると、モデル側の
     既定を上書きしてしまい、自動判定の意味が無くなる。 */
  const loras = selectedLoras();
  return {
    ...constraints,
    ...manualModelSettings(),
    ...(loras.length ? {loras} : {}),
  };
}

/* 歩数とガイダンスは、利用者が既定から変えたときだけ要求に載せる。 */
function manualModelSettings() {
  if (state.mode !== "advanced") return {};
  const settings = currentModelSettings();
  if (!settings) return {};
  const values = {};
  const steps = Number(byId("advanced-steps")?.value);
  if (Number.isFinite(steps) && steps > 0 && steps !== settings.steps) values.steps = steps;
  const guidance = Number(byId("advanced-guidance")?.value);
  const declared = settings.guidance_scale;
  if (
    byId("advanced-guidance")?.value !== ""
    && Number.isFinite(guidance)
    && (declared === null || declared === undefined || guidance !== declared)
  ) {
    values.guidance_scale = guidance;
  }
  return values;
}

/* 詳細設定が対象にしているモデル。方針が manual ならその 1 つ、そうでなければ
   選べるものが 1 つに定まるときだけ。定まらないものの設定を見せると、実際に
   使われるモデルの設定と食い違う。 */
function currentModelSettings() {
  const usable = state.modelCatalog.filter(
    (model) => model.installed && model.healthy && model.generation && model.kind !== "lora"
  );
  const chosen = state.modelChoice === "manual"
    ? byId("model-choice-model")?.value
    : (byId("advanced-policy")?.value === "manual" ? byId("advanced-model")?.value : "");
  if (chosen) return usable.find((model) => model.model_id === chosen)?.generation || null;
  return usable.length === 1 ? usable[0].generation : null;
}

function renderModelSettings() {
  const block = byId("model-settings");
  if (!block) return;
  const settings = currentModelSettings();
  block.hidden = !settings;
  if (!settings) return;

  const usable = state.modelCatalog.filter(
    (model) => model.installed && model.healthy && model.generation && model.kind !== "lora"
  );
  const owner = usable.find((model) => model.generation === settings);
  byId("model-settings-model").textContent = owner
    ? `${owner.display_name || owner.model_id} の設定です。`
    : "";

  const check = byId("model-settings-check");
  const checkItems = settings.needs_check || [];
  check.hidden = checkItems.length === 0;
  byId("model-settings-check-list").replaceChildren(...checkItems.map((entry) => {
    const item = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = `${entry.item}：${entry.value}`;
    const reason = document.createElement("span");
    reason.className = "settings-reason";
    reason.textContent = entry.reason;
    const action = document.createElement("span");
    action.className = "settings-action";
    action.textContent = entry.action;
    item.append(name, reason, action);
    return item;
  }));

  byId("model-settings-settled-list").replaceChildren(...(settings.settled || []).map((entry) => {
    const item = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = `${entry.item}：${entry.value}`;
    const source = document.createElement("span");
    source.className = "settings-reason";
    source.textContent = entry.source;
    item.append(name, source);
    return item;
  }));

  byId("model-settings-presets").replaceChildren(...(settings.presets || []).map((preset) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.dataset.settingPreset = preset.id;
    button.dataset.steps = preset.steps;
    if (preset.guidance_scale !== null && preset.guidance_scale !== undefined) {
      button.dataset.guidance = preset.guidance_scale;
    }
    button.title = preset.detail;
    button.textContent = `${preset.label} ${preset.steps}歩`;
    return button;
  }));

  const steps = byId("advanced-steps");
  if (steps && !steps.value) steps.value = settings.steps || "";
  const guidance = byId("advanced-guidance");
  if (guidance && !guidance.value && settings.guidance_scale !== null
      && settings.guidance_scale !== undefined) {
    guidance.value = settings.guidance_scale;
  }
  byId("model-settings-note").textContent = settings.native_width
    ? `サイズは ${settings.native_width}×${settings.native_height} と同じ面積に自動で寄せます。`
    : "";
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
  if (state.createMedia === "video") {
    if (!videoCapabilityUsable()) {
      return file
        ? "画像から動画を作れる実用モデルがありません。"
        : "文章から動画を作れる実用モデルがありません。";
    }
    return "";
  }
  const directedProblem = creativeProblem();
  if (directedProblem) return directedProblem;
  const referenceProblem = profileReferenceProblem();
  if (referenceProblem) return referenceProblem;
  if (compositionTemplate() && requestedCount() < 2) {
    return "複数カットは2〜4枚を選んでください。";
  }

  if (state.modelChoice === "manual" && !byId("model-choice-model").value) {
    return "使うモデルを選んでください。";
  }

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

async function submitVideoJob() {
  const status = byId("create-status");
  const submit = byId("create-submit");
  const problem = requestProblem({});
  if (problem) { showError(problem); return; }
  clearError();
  submit.disabled = true;
  submit.textContent = "準備しています…";
  status.textContent = "";
  setHostBusy(true);
  showPreparing("受け付けています", 0.05);
  try {
    const file = attachedFile();
    const inputs = [];
    if (file) {
      showPreparing("画像を取り込んでいます", 0.2);
      const source = state.sourceAsset || await importFile(
        state.upload || file, "source", (ratio) => {
          showPreparing("画像を取り込んでいます", 0.2 + ratio * 0.4);
        },
      );
      state.sourceAsset = source;
      inputs.push({asset_id: source.id});
    }
    showPreparing("動画を受け付けています", 0.7);
    const job = await call("jobs.create", {
      operation: "video.generate",
      intent: byId("create-intent").value,
      inputs,
      constraints: {},
      output: {format: "mp4", count: 1},
      local_only: true,
    });
    submit.textContent = "実行中…";
    setHostBusy(false);
    state.activeJob = job.id;
    await call("jobs.watch", {job_ids: [job.id]}).catch(() => {});
    showProgress(job);
    if (window.parent === window) void pollJob(job.id);
  } catch (error) {
    showError(error?.message || failureText(error?.code));
    hidePreparing();
  } finally {
    setHostBusy(false);
    renderCreateMedia();
  }
}

async function submitJob(event) {
  event.preventDefault();
  if (state.disabled) return;
  if (state.createMedia === "video") return submitVideoJob();
  const status = byId("create-status");
  const submit = byId("create-submit");
  const preset = currentPreset();
  const constraints = buildConstraints(preset);
  applyProfileConstraints(constraints);
  const problem = requestProblem(constraints);
  if (problem) { showError(problem); return; }
  clearError();
  byId("composition-text-edit").hidden = true;
  state.currentComposition = null;

  submit.disabled = true;
  // ここはまだ送信前である。演出の整理も参照画像の解析もサーバへ問い合わせる
  // が、結果を持っているのはこの画面で、job はまだ存在しない。だから離れると
  // 本当に失われる（Host の「処理中」もそれを言っている）。
  // 「実行中」と書くと、もうサーバ側の仕事だと読めてしまい、警告と食い違う。
  submit.textContent = "準備しています…";
  status.textContent = "";
  setHostBusy(true);
  showPreparing("受け付けています", 0.05);
  try {
    const file = attachedFile();
    const operation = file ? "image.edit" : "image.generate";
    let inputs = [];
    if (file) {
      showPreparing("画像を取り込んでいます", 0.15);
      const source = state.sourceAsset || await importFile(
        state.upload || file, "source", (ratio) => {
          showPreparing("画像を取り込んでいます", 0.15 + ratio * 0.35);
        },
      );
      state.sourceAsset = source;
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

    let request = {
      operation,
      intent: byId("create-intent").value,
      inputs,
      constraints,
      output: {format: outputFormat(), count: requestedCount()},
      qa: qaOptions(),
      local_only: true,
      ...modelSelection(),
    };
    let spec = creativeSpec();
    const layout = compositionLayout();
    const batchAxes = new Set(["pose", "scene", "composition"]);
    const batchCount = requestedCount();
    const creativeBatch = operation === "image.generate" && batchCount > 1
      && batchAxes.has(spec.variation.axis);
    const directedPoseBatch = operation === "image.generate" && batchCount > 1
      && spec.variation.axis === "pose" && state.directorMode !== "original" && batchCount <= 4;
    let directorPlan = null;
    const referenceAnalysis = referenceAnalysisRequest();
    // 単発生成では演出と検証を job に任せる。ここで呼ぶと、途中結果を持って
    // いるのはこのページだけになり、タブを閉じた時点で失われる（VLM と LLM を
    // 1 回ずつ使った後に、である）。job の記録はブラウザより長く生きる。
    const serverPrepared = operation === "image.generate" && !layout && !creativeBatch;
    if (serverPrepared) {
      renderDirectorPlan(null);
    } else if (state.directorMode !== "original" && !layout && !creativeBatch) {
      showPreparing("演出内容を整理しています", 0.6);
      const directed = await call("creative.direct", {
        intent: request.intent,
        director_mode: state.directorMode,
        creative_spec: spec,
        reference_analysis: referenceAnalysis,
      });
      renderDirectorPlan(directed);
      if (directed.assistance_used) {
        spec = directed.creative_spec;
        directorPlan = directed.plan;
      }
    } else if (state.directorMode === "original") {
      renderDirectorPlan(null);
    }
    if (layout) {
      request.output.count = 1;
      showPreparing("カットを計画しています", 0.65);
      const composition = await call("creative.compositions.create", {
        request, creative_spec: spec, layout,
        director_mode: state.directorMode,
        reference_analysis: referenceAnalysis,
      });
      if (composition.director) renderDirectorPlan(composition.director);
      setHostBusy(false);
      state.activeComposition = composition.id;
      state.currentComposition = composition;
      showCompositionProgress(composition);
      void savePreferences({last_preset: preset.id, last_count: selectedCount()});
      if (window.parent === window) void pollComposition(composition.id);
      return;
    }
    if (batchCount > 1 && batchAxes.has(spec.variation.axis)) {
      request.output.count = 1;
      showPreparing("差分を計画しています", 0.65);
      const batch = await call("creative.batches.create", {
        request, creative_spec: spec, count: batchCount,
        director_mode: directedPoseBatch ? state.directorMode : "original",
        reference_analysis: referenceAnalysis,
      });
      if (batch.director) renderDirectorPlan(batch.director);
      setHostBusy(false);
      state.activeBatch = batch.id;
      showBatchProgress(batch);
      void savePreferences({last_preset: preset.id, last_count: selectedCount()});
      if (window.parent === window) void pollBatch(batch.id);
      return;
    }
    if (serverPrepared) {
      // 何をしてほしいかだけを渡す。演出と検証は job の phase で走る。
      request.constraints = {
        ...request.constraints,
        creative_spec: spec,
        director_mode: state.directorMode,
        ...(referenceAnalysis.length ? {reference_context: referenceAnalysis} : {}),
      };
    } else if (creativeActive(spec) || directorPlan) {
      showPreparing("シーン指定を確認しています", 0.65);
      request = (await call("creative.validate", {
        request, creative_spec: spec, director_plan: directorPlan,
        reference_analysis: referenceAnalysis,
      })).request;
    }
    showPreparing("受け付けています", 0.7);
    const job = await call("jobs.create", request);
    // ここでサーバ側の仕事になった。離れても失われない。
    submit.textContent = "実行中…";
    setHostBusy(false);
    state.activeJob = job.id;
    await call("jobs.watch", {job_ids: [job.id]}).catch(() => {});
    showProgress(job);
    status.textContent = "";
    void savePreferences({last_preset: preset.id, last_count: selectedCount()});
    if (window.parent === window) void pollJob(job.id);
  } catch (error) {
    status.textContent = "";
    showError(error?.message || failureText(error?.code));
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

/* モデルは常に見える 1 つの選択にする。「おまかせ」は選択肢の先頭に残すが、
   既定で隠さない。auto の順位は catalog の policy_rank で決まり、利用者が
   自分で足したモデルは既定順位のまま最後に回る。何が使われるか見えない状態を
   既定にしない。詳細モードでは fast / balanced / quality / low_vram へ到達できる。 */
function modelSelection() {
  /* LoRA を選んでいても土台の指定は捨てない。載るかどうかは backend が
     系統で判定する。ここで auto へ戻すと、選んだ土台が黙って変わる。 */
  if (state.modelChoice === "manual") {
    const modelId = byId("model-choice-model").value;
    return modelId ? {model_policy: "manual", model_id: modelId} : {};
  }
  if (state.mode !== "advanced" || !byId("advanced-policy")) return {};
  const policy = byId("advanced-policy").value;
  if (policy !== "manual") return {model_policy: policy};
  const modelId = byId("advanced-model").value;
  return modelId ? {model_policy: "manual", model_id: modelId} : {};
}

/* 画像を作るための土台だけを並べる。LoRA は単体では絵を作れないので混ぜない。 */
function imageBaseModels() {
  return state.modelCatalog.filter(
    (model) => model.installed && model.healthy && model.kind !== "lora"
      && (model.media_types || ["image"]).includes("image"));
}

/* 手で指定している土台。おまかせのときは null。 */
function chosenBaseModel() {
  if (state.modelChoice !== "manual") return null;
  const modelId = byId("model-choice-model")?.value;
  if (!modelId) return null;
  return state.modelCatalog.find((model) => model.model_id === modelId) || null;
}

function renderModelChoice() {
  const select = byId("model-choice-model");
  const usableModels = imageBaseModels();
  const previous = select.value;
  const auto = document.createElement("option");
  auto.value = "";
  auto.textContent = "おまかせ（自動で選ぶ）";
  select.replaceChildren(auto, ...usableModels.map((model) => {
    const option = document.createElement("option");
    option.value = model.model_id;
    option.textContent = model.display_name || model.model_id;
    return option;
  }));
  select.value = usableModels.some((model) => model.model_id === previous) ? previous : "";
  state.modelChoice = select.value ? "manual" : "auto";
  const note = byId("model-choice-note");
  if (!usableModels.length) {
    note.textContent = "使えるモデルがまだありません。設定から導入してください。";
    return;
  }
  note.textContent = select.value
    ? "指定したモデルだけを使います。"
    : `評価済みの ${usableModels.length} 件から自動で選びます。`
      + "自分で追加したモデルは既定の順位で後ろに回るので、使いたいときは指定してください。";
}

/* standalone には push が無いので、そこだけ従来どおり問い合わせる。
   埋め込み時は session.changed / job.changed に完全に任せ、polling しない。 */
async function pollJob(id) {
  for (let attempt = 0; attempt < 3600 && !state.disabled; attempt += 1) {
    let job;
    try { job = await call("jobs.get", {job_id: id}); } catch { return; }
    showProgress(job);
    if (TERMINAL.has(job.status)) return finishJob(job);
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

async function pollBatch(id) {
  for (let attempt = 0; attempt < 3600 && !state.disabled; attempt += 1) {
    let batch;
    try { batch = await call("creative.batches.get", {batch_id: id}); } catch { return; }
    showBatchProgress(batch);
    if (["succeeded", "partial", "failed", "canceled"].includes(batch.state)) {
      return finishBatch(batch);
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

function showBatchProgress(batch) {
  const running = batch.state === "running";
  const percent = Math.round((batch.progress || 0) * 100);
  byId("stage-progress").hidden = !running;
  byId("mini-progress").hidden = !running;
  byId("progress-phase").textContent = `差分を作っています（${batch.completed_count}/${batch.requested_count}）`;
  byId("mini-phase").textContent = `差分 ${batch.completed_count}/${batch.requested_count}`;
  byId("progress-bar").style.width = `${percent}%`;
  byId("mini-bar").style.width = `${percent}%`;
  byId("progress-detail").textContent = state.mode === "advanced"
    ? `${batch.id} · ${batch.state} · child jobs ${batch.child_job_ids.join(", ")}`
    : `${percent}%`;
  updateActivityBadge(running ? 1 : 0);
}

async function finishBatch(batch) {
  if (state.activeBatch !== batch.id) return;
  state.activeBatch = "";
  byId("stage-progress").hidden = true;
  byId("mini-progress").hidden = true;
  updateActivityBadge(0);
  if (batch.asset_ids.length) {
    await showResult(batch.asset_ids);
    await loadRecent();
  }
  if (batch.state === "partial") {
    showError(`${batch.succeeded_count} 枚は完成し、${batch.failed_count + batch.canceled_count} 枚は完成しませんでした。`);
  } else if (batch.state === "failed") {
    showError("差分を作れませんでした。");
  } else if (batch.state === "canceled") {
    byId("create-status").textContent = "差分作成を中止しました。";
  }
}

async function pollComposition(id) {
  for (let attempt = 0; attempt < 3600 && !state.disabled; attempt += 1) {
    let composition;
    try {
      composition = await call("creative.compositions.get", {composition_id: id});
    } catch { return; }
    showCompositionProgress(composition);
    if (["succeeded", "partial", "failed", "canceled"].includes(composition.state)) {
      return finishComposition(composition);
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}

function showCompositionProgress(composition) {
  const running = composition.state === "running";
  const percent = Math.round((composition.progress || 0) * 90);
  byId("stage-progress").hidden = !running;
  byId("mini-progress").hidden = !running;
  byId("progress-phase").textContent = `カットを作っています（${composition.completed_count}/${composition.layout.shot_count}）`;
  byId("mini-phase").textContent = `カット ${composition.completed_count}/${composition.layout.shot_count}`;
  byId("progress-bar").style.width = `${percent}%`;
  byId("mini-bar").style.width = `${percent}%`;
  byId("progress-detail").textContent = state.mode === "advanced"
    ? `${composition.id} · ${composition.state} · ${composition.child_job_ids.join(", ")}`
    : `${percent}%`;
  updateActivityBadge(running ? 1 : 0);
}

async function finishComposition(composition) {
  if (state.activeComposition !== composition.id) return;
  state.activeComposition = "";
  state.currentComposition = composition;
  byId("stage-progress").hidden = true;
  byId("mini-progress").hidden = true;
  updateActivityBadge(0);
  if (composition.asset_ids.length) {
    await showResult(composition.asset_ids);
    byId("composition-text-edit").hidden = false;
    byId("composition-edit-title").value = composition.layout.title;
    byId("composition-edit-caption").value = composition.layout.caption;
    await loadRecent();
  }
  if (composition.state === "partial") {
    showError("一部のカットが完成しなかったため、合成を完了できませんでした。");
  } else if (composition.state === "failed") {
    showError("カットを1枚にまとめられませんでした。");
  } else if (composition.state === "canceled") {
    byId("create-status").textContent = "複数カットの作成を中止しました。";
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
  if (state.activeJob || state.activeBatch || state.activeComposition) return;
  byId("stage-progress").hidden = true;
  byId("mini-progress").hidden = true;
}

/* 生成中は割合が分からない。

   backend は generating で 5% を出したあと、次の更新が postprocess の 65% で、
   その間に GPU の生成全体（実測 10〜200 秒）が入る。5% のまま固まって一気に
   飛ぶのはそのためだった。

   ここで嘘の割合を動かすことはしない。分からないものは分からないまま、
   動いていることと経過時間を見せる。所要の目安は実測値から別に出している。 */
const INDETERMINATE_PHASES = new Set(["generating", "waiting_resource", "release_ai"]);

function elapsedText(job) {
  const started = Date.parse(job.created_at || "");
  if (!Number.isFinite(started)) return "";
  const seconds = Math.max(0, Math.round((Date.now() - started) / 1000));
  return seconds < 60 ? `${seconds} 秒経過`
    : `${Math.floor(seconds / 60)} 分 ${String(seconds % 60).padStart(2, "0")} 秒経過`;
}

function showProgress(job) {
  const running = !TERMINAL.has(job.status);
  byId("stage-progress").hidden = !running;
  byId("mini-progress").hidden = !running;
  const percent = Math.round((job.progress || 0) * 100);
  const phase = PHASE_TEXT[job.phase] || (job.status === "queued" ? "順番を待っています" : "実行しています");
  const unknown = running && INDETERMINATE_PHASES.has(job.phase);
  byId("progress-phase").textContent = phase;
  byId("mini-phase").textContent = phase;
  for (const id of ["progress-bar", "mini-bar"]) {
    const bar = byId(id);
    bar.classList.toggle("indeterminate", unknown);
    bar.style.width = unknown ? "" : `${percent}%`;
  }
  const elapsed = elapsedText(job);
  byId("progress-detail").textContent = state.mode === "advanced"
    ? `${job.status} · ${unknown ? "所要不明" : `${percent}%`} · ${job.phase || "-"} · ${elapsed} · ${job.id}`
    : unknown ? elapsed : `${percent}%`;
  updateActivityBadge(running ? 1 : 0);
}

/* 別のタブへ移って戻ると進捗が消えていた。表示は state から作り直す。
   実行中の job は state.jobs にあるので、そこから復元する。 */
/* 画面を離れると state.activeJob は消えるが、job はサーバ側で走り続ける。
   別のタブへ移って戻る、埋め込みごと外れて戻る、どちらでも進捗が消えていた。
   「今どれを見ているか」を覚えていないだけなので、走っているものを拾い直す。 */
function restoreProgressView() {
  if (!state.activeJob) {
    // 迷いようがあるときは選ばない。複数走っているなら、状況タブで
    // 「この実行を見る」を押してもらう。
    const running = (state.jobs || []).filter((item) => !TERMINAL.has(item.status));
    if (running.length !== 1) return;
    state.activeJob = running[0].id;
    // 拾い直したものにも通知を張る。張らないと、完了しても画面が動かない。
    void call("jobs.watch", {job_ids: [running[0].id]}).catch(() => {});
    if (window.parent === window) void pollJob(running[0].id);
  }
  const job = (state.jobs || []).find((item) => item.id === state.activeJob);
  if (job) showProgress(job);
}

/* 状況タブから、走っている実行へ戻る。指示と進捗の両方を復旧する:
   進捗だけ戻しても、何を頼んだのかが画面から消えたままになる。 */
function attachToJob(jobId) {
  const job = (state.jobs || []).find((item) => item.id === jobId);
  if (!job || TERMINAL.has(job.status)) return;
  state.activeJob = job.id;
  const intent = byId("create-intent");
  if (intent && job.request?.intent) intent.value = job.request.intent;
  void call("jobs.watch", {job_ids: [job.id]}).catch(() => {});
  if (window.parent === window) void pollJob(job.id);
  activate("create");
  showProgress(job);
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
  vision_analyzer_unavailable: {
    text: "内容の自動チェックはいま使えません。",
    exit: "チェックなしで作る", action: "rerun_without_review",
  },
  host_ai_not_granted: {
    text: "内容の自動チェックを使う権限がありません。",
    exit: "チェックなしで作る", action: "rerun_without_review",
  },
  host_ai_unavailable: {
    text: "ControlDeck の画像確認機能に接続できません。",
    exit: "チェックなしで作る", action: "rerun_without_review",
  },
  vision_result_invalid: {
    text: "内容の自動チェック結果を確認できませんでした。",
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
    exit: "モデル管理を開く", action: "open_model_management",
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
  if (action === "open_model_management") {
    state.modelFilter = "recommended";
    activate("settings");
    return byId("model-table").scrollIntoView({block: "start"});
  }
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
  state.resultAssetIds = [...assetIds];
  const stage = byId("stage-result");
  stage.hidden = false;
  const strip = byId("candidate-strip");
  strip.replaceChildren();
  byId("result-evaluation").textContent = "";
  const evaluate = byId("result-evaluate");
  evaluate.hidden = assetIds.length < 2 || capabilityState("image.creative_evaluation") !== "available";
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
    const video = byId("result-video");
    const isVideo = String(content.mime_type).startsWith("video/");
    image.hidden = isVideo;
    video.hidden = !isVideo;
    byId("result-edit").hidden = isVideo;
    if (isVideo) {
      image.removeAttribute("src");
      image.removeAttribute("data-asset-id");
      video.src = `data:${content.mime_type};base64,${content.base64}`;
      video.dataset.assetId = assetId;
    } else {
      video.pause();
      video.removeAttribute("src");
      video.removeAttribute("data-asset-id");
      image.src = `data:${content.mime_type};base64,${content.base64}`;
      image.dataset.assetId = assetId;
    }
  } catch { /* 表示できなくても以降の操作は続けられる */ }
}

/* 一覧のカードは list に同梱された小さな版を使う。1 枚 1 往復にしない。
   同梱が無いときだけ従来どおり個別に取りに行く。 */
async function thumbnailButton(assetId, onClick, inline) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "thumb";
  button.dataset.assetId = assetId;
  const image = document.createElement("img");
  image.alt = "";
  image.width = 84;
  image.height = 84;
  image.loading = "lazy";
  image.decoding = "async";
  button.append(image);
  button.addEventListener("click", onClick);
  if (inline?.base64) {
    image.src = `data:${inline.mime_type};base64,${inline.base64}`;
    return button;
  }
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
async function loadRecent() {
  await refreshSession(["library"]);
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

async function loadLibrary({reset = false} = {}) {
  const grid = byId("library-grid");
  if (reset) { grid.replaceChildren(); state.libraryCursor = null; }
  let page;
  try {
    page = await call("library.list", {kind: "all", limit: 24, before: state.libraryCursor});
  } catch {
    byId("library-empty").hidden = false;
    byId("library-empty").textContent = "ライブラリを読み込めませんでした。";
    return;
  }
  state.libraryCursor = page.next_before;
  byId("library-more").hidden = !page.next_before;
  if (reset) state.libraryItems = [];
  for (const item of page.items) {
    state.libraryItems.push(item);
    grid.append(await libraryCard(item));
  }
  // 消えた素材を選んだままにしない。削除の後で数だけ残ると、押しても何も起きない。
  const present = new Set(state.libraryItems.map((item) => item.asset_id));
  for (const id of [...state.librarySelected]) if (!present.has(id)) state.librarySelected.delete(id);
  renderLibrarySelection();
  const empty = grid.childElementCount === 0;
  byId("library-empty").hidden = !empty;
  byId("library-empty").textContent = "まだ素材はありません。";
  byId("library-count").textContent = empty
    ? "" : `${state.libraryItems.length} 件${page.next_before ? "＋" : ""}`;
}

/* ── まとめて消す ─────────────────────────────────────────────────────
   1 枚ずつ開いて消すのは、失敗した生成が並んだときに現実的でない。
   選択中はカードの押し先を「開く」から「選ぶ」へ切り替える。同じ場所に
   別の意味を重ねるので、選択中だと分かる印を必ず出す。 */

function setLibrarySelecting(active) {
  state.librarySelecting = active;
  if (!active) state.librarySelected.clear();
  byId("library-grid").classList.toggle("selecting", active);
  const toggle = byId("library-select");
  toggle.setAttribute("aria-pressed", String(active));
  toggle.textContent = active ? "やめる" : "選択";
  renderLibrarySelection();
}

function renderLibrarySelection() {
  const bar = byId("library-selection");
  bar.hidden = !state.librarySelecting;
  const count = state.librarySelected.size;
  byId("library-selection-count").textContent = `${count} 件を選択`;
  byId("library-delete").disabled = count === 0;
  byId("library-delete").textContent = count ? `${count} 件を削除` : "削除";
  for (const card of byId("library-grid").querySelectorAll(".card")) {
    card.setAttribute("aria-selected", String(state.librarySelected.has(card.dataset.assetId)));
  }
}

function libraryNote(text) {
  const note = byId("library-note");
  note.textContent = text;
  note.hidden = !text;
}

function toggleLibrarySelection(assetId) {
  if (state.librarySelected.has(assetId)) state.librarySelected.delete(assetId);
  else state.librarySelected.add(assetId);
  renderLibrarySelection();
}

async function deleteSelectedAssets() {
  const assetIds = [...state.librarySelected];
  if (!assetIds.length) return;
  const accepted = await confirmModelAction({
    title: `${assetIds.length} 件を削除`,
    detail: "選んだ素材とその来歴を消します。元には戻せません。",
    confirmLabel: "削除する",
  });
  if (!accepted) return;
  let response;
  try {
    response = await call("assets.delete", {asset_ids: assetIds});
  } catch {
    return libraryNote("削除できませんでした。");
  }
  // 全部消えたとは限らない。何が残ったのかを、理由込みで伝える。
  const failed = (response.items || []).filter((item) => !item.deleted);
  for (const item of failed) state.librarySelected.add(item.asset_id);
  for (const item of response.items || []) {
    if (item.deleted) state.librarySelected.delete(item.asset_id);
  }
  libraryNote(failed.length
    ? `${response.deleted_count} 件を削除しました。${failed.length} 件は${
        failed.some((item) => item.code === "asset_in_use")
          ? "他の素材の元になっているため" : ""}残りました。`
    : `${response.deleted_count} 件を削除しました。`);
  if (!failed.length) setLibrarySelecting(false);
  await loadLibrary({reset: true});
}

const KIND_LABEL = {generated: "作った", edited: "直した", imported: "取り込み"};

async function libraryCard(item) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = "card";
  card.dataset.assetId = item.asset_id;
  const image = document.createElement("img");
  image.alt = "";
  // 出せない絵の枠だけが正方形で残ると、一覧が読めない箱の列になる。畳む。
  image.addEventListener("error", () => { image.hidden = true; });
  const summary = document.createElement("span");
  summary.className = "sum";
  summary.textContent = item.summary || "(説明なし)";
  const meta = document.createElement("span");
  meta.className = "meta";
  const kind = document.createElement("span");
  kind.textContent = KIND_LABEL[item.kind] || item.kind;
  const size = document.createElement("span");
  const isVideo = String(item.mime_type || "").startsWith("video/");
  size.textContent = item.mime_type === "application/zip"
    ? "ZIP"
    : (item.width && item.height ? `${item.width}×${item.height}` : "");
  if (isVideo) {
    // 一覧に出るのは 1 枚目の静止画なので、動くものだと分からない。
    // 一覧で勝手に再生はしない。押せば動く、と印で伝える。
    card.classList.add("clip");
    const badge = document.createElement("span");
    badge.className = "clip-badge";
    badge.textContent = item.duration_sec ? `▶ ${item.duration_sec.toFixed(1)}秒` : "▶";
    card.append(badge);
  }
  meta.append(kind, size);
  image.loading = "lazy";
  image.decoding = "async";
  card.append(image, summary, meta);
  card.setAttribute("aria-selected", String(state.librarySelected.has(item.asset_id)));
  card.addEventListener("click", () => {
    if (state.librarySelecting) return toggleLibrarySelection(item.asset_id);
    void openViewer(item.asset_id, item, state.libraryItems);
  });
  // 一覧に同梱された小さな版を使う。1 枚 1 往復にしない。
  if (item.thumbnail?.base64) {
    image.src = `data:${item.thumbnail.mime_type};base64,${item.thumbnail.base64}`;
    return card;
  }
  if (!item.preview_kind) {
    image.hidden = true;
    return card;
  }
  try {
    const thumbnail = await call("assets.thumbnail", {asset_id: item.asset_id});
    image.src = `data:${thumbnail.mime_type};base64,${thumbnail.base64}`;
  } catch { image.hidden = true; }
  return card;
}

/* ── 全画面ビューア ───────────────────────────────────────────────────── */

/* 一覧のサムネイルは小さい。タップしたら原寸で見られる場所が要る。
   ピンチ／ホイールで拡大し、拡大中はドラッグで動かせる。 */
const viewer = {
  assetId: "", filename: "", scale: 1, x: 0, y: 0, pointers: new Map(), pinch: 0, drag: null,
  // 一覧から開いたときだけ隣が存在する。単発で開いた素材には送り先がない。
  list: [], index: -1, token: 0,
};

function viewerApply() {
  byId("viewer-image").style.transform =
    `translate(${viewer.x}px, ${viewer.y}px) scale(${viewer.scale})`;
}

function viewerReset() {
  viewer.scale = 1;
  viewer.x = 0;
  viewer.y = 0;
  viewer.pointers.clear();
  viewer.pinch = 0;
  viewer.drag = null;
  viewerApply();
}

function viewerZoom(factor) {
  viewer.scale = Math.max(1, Math.min(8, viewer.scale * factor));
  if (viewer.scale === 1) { viewer.x = 0; viewer.y = 0; }
  viewerApply();
}

function renderViewerNav() {
  const nav = document.querySelector(".viewer-nav");
  if (!nav) return;
  const total = viewer.list.length;
  nav.hidden = total < 2;
  if (total < 2) return;
  byId("viewer-prev").disabled = viewer.index <= 0;
  byId("viewer-next").disabled = viewer.index < 0 || viewer.index >= total - 1;
  byId("viewer-position").textContent = `${viewer.index + 1} / ${total}`;
}

function stepViewer(offset) {
  const next = viewer.index + offset;
  const item = viewer.list[next];
  if (!item) return;
  viewer.index = next;
  void openViewer(item.asset_id, item, viewer.list, {keepList: true});
}

/* 動画と静止画は同じ台の上で入れ替える。両方出したままにすると、
   閉じたつもりの動画が裏で鳴り続ける。 */
function showViewerVideo(active) {
  const image = byId("viewer-image");
  const video = byId("viewer-video");
  if (!video) return;
  image.hidden = active;
  video.hidden = !active;
  if (active) return;
  video.pause();
  video.removeAttribute("src");
  video.load();
}

async function openViewer(assetId, item, list, {keepList = false} = {}) {
  viewer.assetId = assetId;
  viewer.filename = item?.suggested_filename || "";
  if (!keepList) {
    viewer.list = Array.isArray(list) ? list : [];
    viewer.index = viewer.list.findIndex((entry) => entry.asset_id === assetId);
  }
  renderViewerNav();
  byId("viewer-save-note").hidden = true;
  viewerReset();
  const image = byId("viewer-image");
  const video = byId("viewer-video");
  const caption = byId("viewer-caption");
  image.removeAttribute("src");
  image.hidden = false;
  // 送り先を変えたのに前の動画が鳴り続けると、見ているものと音がずれる。
  showViewerVideo(false);
  caption.textContent = "読み込んでいます…";
  if (!byId("viewer").open) byId("viewer").showModal();
  // 送り先を連打されると、遅い方の応答が後から上書きする。最後の要求だけ描く。
  const token = ++viewer.token;
  try {
    if (item?.preview_kind === "project_3d") {
      const thumbnail = await call("assets.thumbnail", {asset_id: assetId, max_side: 512});
      if (token !== viewer.token) return;
      image.src = `data:${thumbnail.mime_type};base64,${thumbnail.base64}`;
      caption.textContent = "ZIP · プレビュー";
      return;
    }
    const content = await call("assets.content", {asset_id: assetId});
    if (token !== viewer.token) return;
    const source = `data:${content.mime_type};base64,${content.base64}`;
    if (String(content.mime_type).startsWith("video/")) {
      showViewerVideo(true);
      video.src = source;
    } else {
      image.src = source;
      image.alt = "";
    }
    // ファイル名は原寸を見ている最中に使わない。行を専有すると操作が押し出される。
    caption.textContent = item?.width && item?.height ? `${item.width}×${item.height}` : "";
  } catch {
    if (token !== viewer.token) return;
    // 12 MiB を超える素材は運べない。小さい版で見せて理由を書く。
    try {
      const thumbnail = await call("assets.thumbnail", {asset_id: assetId, max_side: 512});
      if (token !== viewer.token) return;
      image.src = `data:${thumbnail.mime_type};base64,${thumbnail.base64}`;
      caption.textContent = "原寸は大きすぎて表示できません。書き出して確認してください。";
    } catch {
      if (token !== viewer.token) return;
      image.hidden = true;
      caption.textContent = "表示できません";
    }
  }
}

/* 自動で選んだときこそ根拠が要る。選ばれた理由が見えないと利用者は
   毎回 manual にするしかなくなる。 */
const MODEL_POLICY_TEXT = {
  auto: "おまかせ", fast: "速さ優先", balanced: "つり合い",
  quality: "品質優先", low_vram: "省メモリ", manual: "指定",
};

function modelRouteText(route) {
  if (!route) return "記録なし";
  if (route.policy === "manual") return "指定したモデルを使いました。";
  const policy = MODEL_POLICY_TEXT[route.policy] || route.policy;
  const scene = route.domain && route.domain !== "general" ? `シーン「${route.domain}」` : "シーン指定なし";
  const matched = route.domain_matched
    ? `${scene}に合うモデル`
    : `${scene}に合うモデルが無かったため、使えるモデル`;
  return `${matched} ${route.candidate_count} 件から${policy}で選びました。`;
}

/* 書き出し導線が 1 つも無かった（設計 §F4 保存A）。host files bridge は実装
   済みで疎通実績もあるのに、UI から呼ばれていなかった。ここで繋ぐ。 */
async function saveAsset(assetId) {
  const note = byId("viewer-save-note");
  note.hidden = false;
  note.textContent = "保存先を選んでいます…";
  let grant;
  try {
    grant = await callHost("host.files.export", {suggested_name: viewer.filename || ""});
  } catch (error) {
    // 単体表示にはホストがいない。できないことをできるように見せない。
    note.textContent = error?.code === "bridge_unavailable"
      ? "単体表示では保存できません。ControlDeck から開いてください。"
      : "保存先を選べませんでした。";
    return;
  }
  const grantId = grant?.grant_id || grant?.export_grant_id;
  if (!grantId) {
    note.textContent = "保存を取りやめました。";
    return;
  }
  note.textContent = "保存しています…";
  try {
    const receipt = await call("assets.export", {
      asset_id: assetId,
      export_grant_id: grantId,
      ...(viewer.filename ? {filename: viewer.filename} : {}),
    });
    note.textContent = `${receipt.filename} を保存しました（${formatBytes(receipt.size_bytes)}）。`;
  } catch (error) {
    note.textContent = failureText(error?.code) || "保存できませんでした。";
  }
}

/* 検証の記録は、そのまま出すと JSON の塊が 1 行に並ぶ。読む人が知りたいのは
   「何を見て、通ったのか」だけである。名前を訳し、通否だけを添える。 */
const VALIDATOR_LABEL = {
  "image.non_empty": "中身がある",
  "image.dimensions": "大きさ",
  "image.mode": "形式",
  "image.alpha": "透過",
  "image.outpaint.source_pixel_diff": "元の絵が変わっていない",
  "image.strict_edit.unmasked_pixel_diff": "塗った所だけ変わっている",
  "glb.structure": "3Dファイルの構造",
  "glb.output_structure": "書き出した3Dファイルの構造",
  "package.deterministic_zip": "3Dパッケージの再現性",
  "evaluation.unified": "内容の確認",
  "m5.companion.profile": "機種の設定",
  "m5.companion.edit_mask": "編集範囲",
  "m5.companion.pack": "同梱物",
};

function validationList(validation) {
  const holder = document.createElement("div");
  holder.className = "checks";
  for (const record of validation) {
    // 記録は status: "passed" と passed: true の二通りある。どちらも読む。
    const passed = record?.status ? record.status === "passed" : record?.passed === true;
    const item = document.createElement("span");
    item.className = passed ? "checkmark ok" : "checkmark bad";
    item.textContent = `${passed ? "✓" : "✕"} ${
      VALIDATOR_LABEL[record?.validator] || record?.validator || "不明"}`;
    if (record?.reason) item.title = String(record.reason);
    holder.append(item);
  }
  return holder;
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
      ["使ったモデル", provenance.model_id || "記録なし"],
      ["選んだ理由", modelRouteText(provenance.parameters?.model_route)],
      ["元になった素材", provenance.parent_asset_ids.length ? provenance.parent_asset_ids.join(", ") : "なし"],
      ["ライセンス", provenance.license],
      ["検証", provenance.validation.length
        ? validationList(provenance.validation) : "記録なし"],
    ];
    for (const [term, value] of rows) {
      const wrap = document.createElement("div");
      const dt = document.createElement("dt");
      dt.textContent = term;
      const dd = document.createElement("dd");
      if (value instanceof Node) dd.append(value);
      else dd.textContent = String(value);
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

/* 取得と描画を分ける。session.changed で状態が更新されたら描画だけやり直す。 */
function renderActivity() {
  const list = byId("activity-list");
  const items = state.jobs || [];
  const batches = state.mode === "advanced" ? (state.batches || []) : [];
  const running = items.filter((job) => !TERMINAL.has(job.status));
  const finished = items.filter((job) => TERMINAL.has(job.status));
  const batchRows = batches.map(creativeBatchRow);
  list.replaceChildren(...batchRows, ...[...running, ...finished].map(activityRow));
  const empty = byId("activity-empty");
  empty.textContent = "まだ実行した記録はありません。";
  empty.hidden = items.length + batchRows.length > 0;
  // 消せるものが無いときに押せるボタンを出さない。
  byId("activity-clear").hidden = finished.length === 0;
  updateActivityBadge(running.length + batches.filter((batch) => batch.state === "running").length);
}

function showActivityUnavailable() {
  // 読み込めなかったときも行き止まりにしない。前回の一覧を残し、出口を出す。
  const empty = byId("activity-empty");
  empty.hidden = false;
  empty.replaceChildren();
  const text = document.createElement("span");
  text.textContent = "状況をいま読み込めませんでした。";
  const retry = document.createElement("button");
  retry.type = "button";
  retry.dataset.retryActivity = "1";
  retry.textContent = "もう一度読み込む";
  empty.append(text, retry);
}

async function loadActivity() {
  let snapshot;
  try {
    snapshot = await call("workspace.session", {parts: ["jobs", "creative_batches"]});
  } catch {
    showActivityUnavailable();
    return;
  }
  if (!usable(snapshot.jobs)) {
    showActivityUnavailable();
    return;
  }
  applySessionParts(snapshot);
  renderActivity();
}

function restoreCreativeBatch(snapshot) {
  if (!usable(snapshot.creative_batches)) return;
  const active = (state.batches || []).find((batch) => batch.state === "running");
  if (!active) return;
  state.activeBatch = active.id;
  showBatchProgress(active);
  if (window.parent === window) void pollBatch(active.id);
}

function restoreCreativeComposition(snapshot) {
  if (!usable(snapshot.creative_compositions)) return;
  const active = (snapshot.creative_compositions.items || [])
    .find((composition) => composition.state === "running");
  if (!active) return;
  state.activeComposition = active.id;
  state.currentComposition = active;
  showCompositionProgress(active);
  if (window.parent === window) void pollComposition(active.id);
}

const STATUS_LABEL = {queued: "待機", running: "実行中", succeeded: "完了", failed: "失敗", canceled: "中止"};

function creativeBatchRow(batch) {
  const row = document.createElement("article");
  row.className = "row";
  row.dataset.batchId = batch.id;
  row.dataset.status = batch.state;

  const info = document.createElement("div");
  const title = document.createElement("p");
  title.className = "t";
  title.textContent = `差分セット · ${batch.axis}`;
  const sub = document.createElement("p");
  sub.className = "s";
  sub.textContent = `${batch.succeeded_count}/${batch.requested_count} 枚完成 · ${batch.id}`;
  const children = document.createElement("details");
  const summary = document.createElement("summary");
  summary.textContent = `子ジョブ ${batch.child_job_ids.length} 件`;
  const childList = document.createElement("p");
  childList.className = "s";
  childList.textContent = batch.child_job_ids.map((id, index) => `${index + 1}. ${id}`).join("\n");
  children.append(summary, childList);
  info.append(title, sub, children);

  const side = document.createElement("div");
  side.className = "row-side";
  const status = document.createElement("span");
  status.className = "state";
  status.textContent = STATUS_LABEL[batch.state] || (batch.state === "partial" ? "一部完了" : batch.state);
  side.append(status);
  if (batch.state === "running") {
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.dataset.cancelBatch = batch.id;
    cancel.textContent = "すべて中止";
    side.append(cancel);
  }
  row.append(info, side);
  return row;
}

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
  title.textContent = job.request.intent || "(記録に指示が残っていません)";
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
  // 新しい版が書いた記録は degraded として残す。黙って一覧から消さない。
  if (job.record_state === "degraded") {
    const note = document.createElement("p");
    note.className = "s";
    note.dataset.recordState = "degraded";
    note.textContent = "この記録は新しい版で作られています。内容の一部だけ表示しています。";
    info.append(note);
  }
  if (state.mode === "advanced") {
    const raw = document.createElement("p");
    raw.className = "s";
    const batch = job.request.constraints?.creative_plan?.batch;
    raw.textContent = `${job.id} · ${job.phase || "-"}${job.error ? ` · ${job.error.code}` : ""}`
      + (batch ? ` · ${batch.id} child ${batch.index + 1}/${batch.total}` : "");
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
    // 走っているものが複数あるとき、どれを見るかは利用者が決める。自動で
    // 拾うと、見たかった方ではない実行の進捗が出る。
    if (job.id !== state.activeJob) {
      const attach = document.createElement("button");
      attach.type = "button";
      attach.dataset.attachJob = job.id;
      attach.textContent = "この実行を見る";
      side.append(attach);
    }
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
  "image.creative_evaluation": "候補を比較・順位付けする",
  "creative.text_direction": "演出内容を整理する",
  "video.image_to_video": "動画にする",
  "3d.image_to_3d": "3D にする",
};

const DOMAIN_LABEL = {
  general: "汎用", anime: "アニメ", illustration: "イラスト", photoreal: "写真",
  game2d: "2Dゲーム", poster: "ポスター", character_sheet: "キャラクター表",
  background: "背景",
};
const MEDIA_TYPE_LABEL = {image: "画像", video: "動画", audio_video: "音声付き動画"};
const MAX_MANAGED_MODEL_DOWNLOAD_BYTES = 32_000_000_000;
const MODEL_STATE_LABEL = {
  queued: "順番を待っています", preflight: "容量と利用条件を確認しています",
  downloading: "ダウンロードしています", verifying: "内容を検証しています",
  installing: "導入しています", ready: "準備できました", failed: "導入できませんでした",
  acquiring_resource: "GPU の空きを待っています", loading: "モデルを読み込んでいます",
  generating: "短い検証動画を作っています", validating: "出力を検証しています",
  canceled: "中止しました",
};

const MODEL_OPERATION_ACTION_LABEL = {
  install: "ダウンロード", evaluate: "実機評価", remove: "削除",
};

function modelOperationStateLabel(operation) {
  if (operation?.action === "evaluate") {
    if (operation.state === "ready") return "評価が完了しました";
    if (operation.state === "failed") return "評価できませんでした";
    if (operation.state === "canceled") return "評価を中止しました";
  }
  return MODEL_STATE_LABEL[operation?.state] || operation?.state || "";
}
const MODEL_ADOPTION_LABEL = {
  experimental: "実験的・未実測",
  unavailable: "利用不可",
};

const MODEL_FAILURE = {
  insufficient_disk: {text: "保存先の空き容量が足りません。", exit: "空き容量を見る", action: "storage"},
  model_gated: {text: "配布元で利用条件への同意が必要です。", exit: "詳細を見る", action: "details"},
  model_too_large: {text: "32GB以上のモデルはこの端末ではダウンロードしません。", exit: "詳細を見る", action: "details"},
  model_download_failed: {text: "ダウンロードを続けられませんでした。", exit: "再試行", action: "retry"},
  model_verify_failed: {text: "取得したファイルを検証できませんでした。", exit: "再試行", action: "retry"},
  model_in_use: {text: "実行中の処理がこのモデルを使っています。", exit: "状況を見る", action: "activity"},
  external_model_owned: {text: "共有モデルは配布元で管理してください。", exit: "一覧を更新", action: "refresh"},
  model_not_found: {text: "モデル一覧が更新されています。", exit: "一覧を更新", action: "refresh"},
  model_evaluation_unsupported: {text: "このモデルには固定評価手順がありません。", exit: "詳細を見る", action: "details"},
  model_runtime_unavailable: {text: "検証済みの実行環境がこの端末にありません。", exit: "詳細を見る", action: "details"},
  model_evaluation_failed: {text: "実機評価を完了できませんでした。", exit: "状況を見る", action: "activity"},
  model_evaluation_timeout: {text: "実機評価が制限時間を超えました。", exit: "状況を見る", action: "activity"},
  model_evaluation_invalid_output: {text: "生成された検証動画が要件を満たしません。", exit: "状況を見る", action: "activity"},
  host_capability_not_granted: {text: "ControlDeck がGPU評価権限を許可していません。", exit: "詳細を見る", action: "details"},
  resource_unavailable: {text: "GPUを確保できませんでした。", exit: "状況を見る", action: "activity"},
  host_ai_residency_retained: {
    text: "ControlDeck が文章・画像認識のモデルを GPU に置いたままのため、画像生成の空きを取れませんでした。",
    exit: "状況を見る", action: "activity",
  },
};

function formatBytes(value) {
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  return `${(value / (1024 ** index)).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function modelRecommended(model) {
  return model.state === "available" && model.measurement_confidence === "measured" && !model.gated;
}

function latestModelOperation(modelId) {
  return [...state.modelOperations.values()]
    .filter((item) => item.model_id === modelId)
    .sort((left, right) => right.created_at.localeCompare(left.created_at))[0] || null;
}

function modelFailureNode(code, modelKey) {
  const detail = MODEL_FAILURE[code] || {
    text: "モデル操作を完了できませんでした。", exit: "一覧を更新", action: "refresh",
  };
  const holder = document.createElement("div");
  holder.className = "model-failure";
  const text = document.createElement("span");
  text.textContent = detail.text;
  const exit = document.createElement("button");
  exit.type = "button";
  exit.dataset.modelExit = detail.action;
  exit.dataset.modelKey = modelKey;
  exit.textContent = detail.exit;
  holder.append(text, exit);
  return holder;
}

/* この機材で動くのかを、表の中で一目で分かるようにする。

   容量とライセンスが並んでいても「これは動くのか」は分からない。判定できる
   材料は既にある（実測 VRAM と、この機材の VRAM 量）ので、それを使う。

   実測していないものを「動く」とは言わない。分からないものは分からないと
   出す。CPU オフロードは動くが遅くなる選択肢なので、動くものとは分けて出す。 */
const RUNNABILITY = {
  fits: {label: "実行可能", rank: 0, tone: "ok"},
  offload: {label: "オフロード前提", rank: 1, tone: "warn"},
  unknown: {label: "未計測", rank: 2, tone: "muted"},
  blocked: {label: "起動不可", rank: 3, tone: "bad"},
};

function modelRunnability(model) {
  const device = Number(state.deviceVramBytes) || 0;
  if (!model.capabilities || !model.capabilities.length) return "blocked";
  const measured = Number(model.measured_vram_bytes) || 0;
  if (!device) return "unknown";
  if (!measured) {
    // 未計測。重みの大きさは目安にしかならないので、明らかに載らない場合だけ
    // 起動不可と言い、それ以外は未計測のままにする。
    const approximate = Number(model.approx_download_bytes) || 0;
    return approximate > device * 3 ? "blocked" : "unknown";
  }
  if (measured <= device) return "fits";
  // オフロードすれば動く見込みがある範囲。実測ではないので前提付きで出す。
  return measured <= device * 3 ? "offload" : "blocked";
}

function runnabilityCell(model) {
  const cell = document.createElement("td");
  const key = modelRunnability(model);
  const info = RUNNABILITY[key];
  const badge = document.createElement("span");
  badge.className = "runnable";
  badge.dataset.tone = info.tone;
  badge.textContent = info.label;
  cell.append(badge);
  return cell;
}

/* 導入済みを見比べるには表のほうが向く。カードは 1 件ずつの説明には良いが、
   容量や状態を縦に揃えられないので、どれを消すかを決める用途に使えない。
   検索結果と同じ表の言葉づかいに揃える。 */
function modelStateLabel(model) {
  if (!model.installed) return "未導入";
  return model.healthy ? "導入済み・利用可" : "導入済み・利用不可";
}

function modelActionCell(model, modelKey) {
  const cell = document.createElement("td");
  const operation = latestModelOperation(model.model_id);
  if (operation && !MODEL_TERMINAL.has(operation.state)) {
    const status = document.createElement("span");
    status.className = "model-operation-state";
    status.textContent = `${modelOperationStateLabel(operation)} ${
      operation.bytes_total ? Math.floor(operation.bytes_done / operation.bytes_total * 100) : 0}%`;
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.dataset.cancelModelOperation = operation.id;
    cancel.textContent = "中止";
    cell.append(status, cancel);
    return cell;
  }
  // 押せないものをボタンにしない。押せる見た目なのに反応しないと、何が
  // 足りないのかを利用者が推測することになる。できないときは理由を書く。
  const unavailable = (text, why) => {
    const status = document.createElement("span");
    status.className = "model-action-status";
    status.textContent = text;
    const note = document.createElement("span");
    note.className = "model-action-note";
    note.textContent = why;
    cell.append(status, note);
    return cell;
  };
  if (!state.modelManagementAvailable) {
    return unavailable(
      "操作できません",
      "この表示ではモデルの追加・削除ができません。ControlDeck から開いてください。",
    );
  }
  if (!model.installed && model.ownership !== "managed") {
    return unavailable(
      "外部で管理",
      "このモデルは Media Forge の管理外です。共有のモデル置き場へ入れると、"
      + "同じ画面から同じように使えます。",
    );
  }
  if (!model.installed && model.approx_download_bytes >= MAX_MANAGED_MODEL_DOWNLOAD_BYTES) {
    return unavailable(
      "容量超過",
      `${formatBytes(model.approx_download_bytes)} は 1 度に取り込める上限を超えています。`,
    );
  }
  if (model.installed && model.ownership !== "managed") {
    // ControlDeck 共有の置き場にある。Media Forge が Host のディレクトリを
    // 消しに行くのは越権なので、消せないことと、その理由を書く。
    return unavailable(
      "共有の置き場",
      "ControlDeck が共有するモデル置き場にあります。Media Forge の管理外なので、"
      + "ここからは削除できません。ControlDeck 側で整理してください。",
    );
  }

  const action = document.createElement("button");
  action.type = "button";
  if (!model.installed) {
    action.dataset.installModel = modelKey;
    action.textContent = "ダウンロード";
  } else if (model.removable) {
    action.dataset.removeModel = modelKey;
    action.textContent = "削除";
  } else {
    return unavailable("使用中", "実行中の処理がこのモデルを使っています。");
  }
  if (model.installed && state.modelEvaluationIds.has(model.model_id)) {
    const evaluate = document.createElement("button");
    evaluate.type = "button";
    evaluate.dataset.evaluateModel = modelKey;
      evaluate.textContent = "評価";
      cell.append(evaluate);
  }
  cell.append(action);
  if (!model.installed && model.media_types.some((item) => item === "video" || item === "audio_video")) {
    const note = document.createElement("span");
    note.className = "model-action-note";
    note.textContent = "ダウンロードだけでは動画生成は有効になりません。実機評価と実行環境の採用が別に必要です。";
    cell.append(note);
  }
  return cell;
}

function modelTableRow(model) {
  const modelKey = String(state.modelCatalog.indexOf(model));
  const row = document.createElement("tr");
  row.dataset.modelKey = modelKey;

  const name = document.createElement("td");
  name.className = "name";
  const title = document.createElement("div");
  title.textContent = model.display_name || model.model_id;
  name.append(title);
  for (const label of [
    ...model.media_types.map((item) => MEDIA_TYPE_LABEL[item] || item),
    ...model.domains.map((item) => DOMAIN_LABEL[item] || item),
  ]) {
    const chip = document.createElement("span");
    chip.className = "tag";
    chip.textContent = label;
    name.append(chip);
  }

  const stateCell = document.createElement("td");
  stateCell.textContent = modelStateLabel(model);

  const adoption = document.createElement("td");
  adoption.textContent = MODEL_ADOPTION_LABEL[model.state] || model.state;

  const size = document.createElement("td");
  size.className = "num";
  size.textContent = model.installed && model.reclaimable_bytes
    ? formatBytes(model.reclaimable_bytes)
    : `約 ${formatBytes(model.approx_download_bytes)}`;

  const vram = document.createElement("td");
  vram.className = "num";
  vram.textContent = model.measured_vram_bytes ? formatBytes(model.measured_vram_bytes) : "未計測";

  const license = document.createElement("td");
  license.textContent = model.license || "-";

  row.append(
    labelled(name, "モデル"),
    labelled(runnabilityCell(model), "この機材"),
    labelled(stateCell, "状態"),
    labelled(adoption, "採用"),
    labelled(size, "容量"),
    labelled(vram, "VRAM"),
    labelled(license, "ライセンス"),
    labelled(modelActionCell(model, modelKey), "操作"),
  );
  // モバイルでは 2 列に並べるため、狭い側で落とす欄に印を付ける。
  // 採用とライセンスは表（横並び）では読めるが、狭い枠では名前と容量を潰す。
  adoption.classList.add("secondary");
  license.classList.add("secondary");
  return row;
}

function renderModelTable(visible) {
  const holder = byId("model-table");
  if (!holder) return;
  if (state.modelSort === "runnable") {
    // 動くものを先に。同順位なら実測 VRAM の小さい順（載せやすい順）。
    visible = [...visible].sort((a, b) =>
      RUNNABILITY[modelRunnability(a)].rank - RUNNABILITY[modelRunnability(b)].rank
      || (Number(a.measured_vram_bytes) || Infinity) - (Number(b.measured_vram_bytes) || Infinity)
      || String(a.display_name).localeCompare(String(b.display_name)));
  }
  const table = document.createElement("table");
  table.className = "catalog";
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  for (const label of ["モデル", "この機材", "状態", "採用", "容量", "VRAM", "ライセンス", ""]) {
    const cell = document.createElement("th");
    cell.textContent = label;
    headRow.append(cell);
  }
  head.append(headRow);
  const body = document.createElement("tbody");
  body.append(...visible.map(modelTableRow));
  table.append(head, body);
  holder.replaceChildren(table);
}

/* ダウンロードは数十 GB かかることがあり、押したあとの行き先が要る。
   進行中だけでなく、終わったもの・失敗したものも残す。何が落ちたのかを
   後から確かめられないと、やり直してよいのかが分からない。 */
function modelDownloadRow(operation) {
  const model = state.modelCatalog.find((item) => item.model_id === operation.model_id);
  const row = document.createElement("article");
  row.className = "row";
  row.dataset.status = MODEL_TERMINAL.has(operation.state)
    ? (operation.state === "ready" ? "succeeded" : "failed") : "running";

  const info = document.createElement("div");
  const title = document.createElement("p");
  title.className = "t";
  title.textContent = model?.display_name || operation.model_id;
  const sub = document.createElement("p");
  sub.className = "s";
  const done = formatBytes(operation.bytes_done);
  const total = operation.bytes_total ? formatBytes(operation.bytes_total) : "?";
  // 「ダウンロード · ダウンロードしています」と二重に出ていた。状態の言葉が
  // 何をしているかを既に言っているので、そちらだけ残す。
  const stateText = modelOperationStateLabel(operation);
  const actionText = MODEL_OPERATION_ACTION_LABEL[operation.action] || operation.action;
  sub.textContent = [
    stateText.startsWith(actionText) ? "" : actionText,
    stateText,
    operation.bytes_total ? `${done} / ${total}` : done,
    modelSpeedText(operation),
    operation.error_code ? failureText(operation.error_code) : "",
  ].filter(Boolean).join(" · ");
  info.append(title, sub);

  const side = document.createElement("div");
  side.className = "row-side";
  if (!MODEL_TERMINAL.has(operation.state)) {
    const progress = document.createElement("progress");
    progress.max = Math.max(operation.bytes_total, 1);
    progress.value = operation.bytes_done;
    progress.setAttribute("aria-label", modelOperationStateLabel(operation));
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.dataset.cancelModelOperation = operation.id;
    cancel.textContent = "中止";
    side.append(progress, cancel);
  } else {
    const done_ = document.createElement("span");
    done_.className = "state";
    done_.textContent = operation.state === "ready" ? "完了" : "失敗";
    side.append(done_);
    // 落ちた行にこそ次の一手が要る。一覧まで戻って同じモデルを探し直すのは、
    // 失敗が何件か並んだ時点で現実的でなくなる。
    if (operation.state !== "ready" && operation.action === "install") {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.dataset.retryModelOperation = operation.model_id;
      retry.textContent = "再試行";
      side.append(retry);
    }
  }
  row.append(info, side);
  return row;
}

async function clearModelDownloadHistory() {
  try {
    await call("models.operations.clear", {});
  } catch (error) {
    // 黙って戻ると「押したのに消えない」だけが残り、原因が誰にも見えない。
    showModelError(error?.code || "UNKNOWN_FAILURE", "");
    return;
  }
  // 進行中は残る。手元の控えも同じ規則で間引き、次の一覧取得を待たない。
  for (const [id, operation] of [...state.modelOperations]) {
    if (MODEL_TERMINAL.has(operation.state)) state.modelOperations.delete(id);
  }
  renderModelDownloads();
  await loadModelManagement();
}

function renderModelDownloads() {
  const holder = byId("model-downloads");
  if (!holder) return;
  const operations = [...state.modelOperations.values()]
    .filter((item) => item.action !== "remove")
    .sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)));
  holder.replaceChildren(...operations.map(modelDownloadRow));
  byId("model-downloads-empty").hidden = operations.length > 0;
  const running = operations.filter((item) => !MODEL_TERMINAL.has(item.state)).length;
  byId("model-downloads-clear").hidden = operations.length === running;
  byId("model-downloads-count").textContent = running
    ? `進行中 ${running} 件` : operations.length ? `${operations.length} 件` : "";
  // 進行中があるなら開いておく。押したのに何も見えないのが一番困る。
  if (running) byId("model-downloads-block").open = true;
}

function renderModelManagement() {
  if (!byId("model-table")) return;
  renderCatalogSource();
  const visible = state.modelCatalog.filter((model) => {
    if (state.modelFilter === "installed") return model.installed;
    if (state.modelFilter === "recommended") return modelRecommended(model);
    if (state.modelFilter === "image") return model.media_types.includes("image");
    if (state.modelFilter === "video") {
      return model.media_types.includes("video") || model.media_types.includes("audio_video");
    }
    return true;
  });
  const videoModels = state.modelCatalog.filter((model) =>
    model.media_types.includes("video") || model.media_types.includes("audio_video"));
  const installedVideo = videoModels.filter((model) => model.installed);
  const downloadableVideo = videoModels.filter((model) => !model.installed &&
    model.ownership === "managed" && model.approx_download_bytes < MAX_MANAGED_MODEL_DOWNLOAD_BYTES);
  const removableVideo = videoModels.filter((model) => model.installed && model.removable);
  const note = byId("model-management-note");
  if (state.modelFilter === "video") {
    note.textContent = `動画候補 ${videoModels.length} 件中、導入済み ${installedVideo.length} 件、` +
      `追加可能 ${downloadableVideo.length} 件、削除可能 ${removableVideo.length} 件。` +
      (installedVideo.length && !installedVideo.some((model) => model.healthy)
        ? "導入済みモデルはありますが、ライセンス同意とは別の実用品質・メモリ安全性の評価を満たしていないため、動画生成にはまだ使えません。"
        : "追加・削除は各行の操作欄から行えます。");
    note.hidden = false;
  } else {
    note.textContent = "モデルの追加・削除は各行の操作欄から行えます。操作できない候補には理由を表示します。";
    note.hidden = false;
  }
  renderModelDownloads();
  renderModelTable(visible);
  byId("model-table").hidden = visible.length === 0;
  renderAdvancedModels();
}

function renderAdvancedModels() {
  const holder = byId("advanced-models");
  if (!holder) return;
  holder.replaceChildren(...state.modelCatalog.map((model) => {
    const row = document.createElement("article");
    row.className = "row technical-model";
    const title = document.createElement("p");
    title.className = "t";
    title.textContent = model.display_name;
    const detail = document.createElement("pre");
    detail.textContent = [
      `model_id: ${model.model_id}`, `revision: ${model.source?.revision || "-"}`,
      `weights: ${model.weights_hash || "-"}`, `runtime: ${model.runtime_adapter}`,
      `backend: ${(model.hardware_backends || []).join(", ") || "-"}`,
      `capabilities: ${(model.capabilities || []).join(", ") || "-"}`,
      `VRAM: ${formatBytes(model.measured_vram_bytes)}`,
      `runtime: ${model.measured_runtime_sec ? `${model.measured_runtime_sec.toFixed(2)} sec` : "NOT MEASURED"}`,
      `license: ${model.license} · gated=${model.gated}`,
    ].join("\n");
    row.append(title, detail);
    return row;
  }));
}

function renderModelMiniProgress() {
  const active = [...state.modelOperations.values()]
    .filter((item) => !MODEL_TERMINAL.has(item.state))
    .sort((left, right) => right.created_at.localeCompare(left.created_at))[0];
  const holder = byId("model-mini-progress");
  holder.hidden = !active;
  document.documentElement.dataset.modelProgress = active ? "true" : "false";
  if (!active) return;
  const model = state.modelCatalog.find((item) => item.model_id === active.model_id);
  byId("model-mini-phase").textContent = `${model?.display_name || "モデル"}: ${
    modelOperationStateLabel(active)}`;
  byId("model-mini-bar").style.width = `${active.bytes_total
    ? Math.min(100, active.bytes_done / active.bytes_total * 100) : 0}%`;
  byId("model-mini-cancel").dataset.operationId = active.id;
}

async function loadModelManagement() {
  await refreshSession(["models", "model_catalog", "model_operations"]);
}

/* 詳細モードの「モデル」選択。catalog の表示名で出し、使えるものだけ並べる。 */
function renderAdvancedModelChoices() {
  const select = byId("advanced-model");
  if (!select) return;
  const previous = select.value;
  const usableModels = state.modelCatalog.filter(
    (model) => model.installed && model.healthy && model.kind !== "lora");
  select.replaceChildren(...usableModels.map((model) => {
    const option = document.createElement("option");
    option.value = model.model_id;
    option.textContent = model.display_name || model.model_id;
    return option;
  }));
  if (usableModels.some((model) => model.model_id === previous)) select.value = previous;
}

function showModelError(code, modelId) {
  const holder = byId("model-error");
  const modelKey = String(state.modelCatalog.findIndex((item) => item.model_id === modelId));
  holder.replaceChildren(modelFailureNode(code, modelKey));
  holder.hidden = false;
}

function confirmModelAction({title, detail, confirmLabel}) {
  const dialog = byId("model-confirm-dialog");
  const cancel = byId("model-confirm-cancel");
  const submit = byId("model-confirm-submit");
  byId("model-confirm-title").textContent = title;
  byId("model-confirm-detail").textContent = detail;
  submit.textContent = confirmLabel;
  return new Promise((resolve) => {
    let settled = false;
    const finish = (accepted) => {
      if (settled) return;
      settled = true;
      cancel.removeEventListener("click", onCancel);
      submit.removeEventListener("click", onSubmit);
      dialog.removeEventListener("cancel", onDialogCancel);
      if (dialog.open) dialog.close();
      resolve(accepted);
    };
    const onCancel = () => finish(false);
    const onSubmit = () => finish(true);
    const onDialogCancel = (event) => { event.preventDefault(); finish(false); };
    cancel.addEventListener("click", onCancel);
    submit.addEventListener("click", onSubmit);
    dialog.addEventListener("cancel", onDialogCancel);
    dialog.showModal();
  });
}

async function startModelInstall(modelId) {
  byId("model-error").hidden = true;
  const model = state.modelCatalog.find((item) => item.model_id === modelId);
  let licenseAcceptance = null;
  if (model?.gated) {
    if (!model.license_acceptance_id) return showModelError("model_gated", modelId);
    const accepted = await confirmModelAction({
      title: `${model.display_name} の利用条件`,
      detail: `${model.license_notice}\n\nこの版の条件に同意して、この端末へダウンロードしますか？`,
      confirmLabel: "同意してダウンロード",
    });
    if (!accepted) return;
    licenseAcceptance = model.license_acceptance_id;
  }
  try {
    const operation = await call("models.install", {
      model_id: modelId, license_acceptance: licenseAcceptance,
    });
    state.modelOperations.set(operation.id, operation);
    await call("models.operations.watch", {operation_ids: [operation.id]});
    await loadModelManagement();
  } catch (error) { showModelError(error?.code, modelId); }
}

async function cancelModelOperation(operationId) {
  if (!operationId) return;
  try {
    const operation = await call("models.operations.cancel", {operation_id: operationId});
    state.modelOperations.set(operation.id, operation);
    await loadModelManagement();
  } catch (error) { showModelError(error?.code, ""); }
}

async function startModelEvaluation(modelId) {
  if (!state.modelCatalog.some((item) => item.model_id === modelId) ||
      !state.modelEvaluationIds.has(modelId)) {
    return showModelError("model_runtime_unavailable", modelId);
  }
  try {
    const operation = await call("models.evaluate", {model_id: modelId});
    state.modelOperations.set(operation.id, operation);
    await call("models.operations.watch", {operation_ids: [operation.id]});
    await loadModelManagement();
  } catch (error) { showModelError(error?.code, modelId); }
}

function openModelRemove(modelId) {
  const model = state.modelCatalog.find((item) => item.model_id === modelId);
  if (!model) return;
  state.removeModelId = modelId;
  byId("model-remove-summary").textContent = `${model.display_name} をこの端末から削除します。`;
  byId("model-remove-detail").textContent = `${formatBytes(model.reclaimable_bytes)} を解放 · ${
    model.profile_reference_count || 0} 件のプロファイルが参照`;
  byId("model-remove-dialog").showModal();
}

async function loadSettings() {
  renderExtensionDetails();
  await loadModelManagement();
}

function renderExtensionDetails() {
  const list = byId("advanced-capability-list");
  if (!list) return;
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
  byId("advanced-host-state").textContent = state.bridgePort ? "接続しています" : "この画面だけで動いています";
}

async function loadAdvancedSettings() {
  const holder = byId("advanced-models");
  if (!holder) return;
  renderExtensionDetails();
  try {
    const {items} = await call("models.list");
    renderAdvancedModels();
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
byId("create-media-switch").addEventListener("click", (event) => {
  const button = event.target.closest?.("[data-create-media]");
  if (!button || state.hostBusy) return;
  setCreateMedia(button.dataset.createMedia);
});
byId("video-create-settings").addEventListener("click", () => {
  state.modelFilter = "video";
  activate("settings");
  renderModelManagement();
  byId("model-table").scrollIntoView({block: "start"});
});

document.addEventListener("change", (event) => {
  const box = event.target.closest?.("[data-lora-id]");
  if (box) {
    const id = box.dataset.loraId;
    const rest = (state.selectedLoras || []).filter((item) => item.model_id !== id);
    if (box.checked) {
      const weight = Number(
        byId("lora-list")?.querySelector(`[data-lora-weight="${id}"]`)?.value ?? 1);
      if (rest.length >= 4) {
        box.checked = false;
        showError("LoRA は 4 個までです。");
        return;
      }
      rest.push({model_id: id, weight});
    }
    state.selectedLoras = rest;
    renderLoraPicker();
  }
});

document.addEventListener("input", (event) => {
  const slider = event.target.closest?.("[data-lora-weight]");
  if (!slider) return;
  const id = slider.dataset.loraWeight;
  slider.parentElement.querySelector(".lora-weight").textContent =
    Number(slider.value).toFixed(2);
  const chosen = (state.selectedLoras || []).find((item) => item.model_id === id);
  if (chosen) chosen.weight = Number(slider.value);
});

byId("catalog-type")?.addEventListener("click", (event) => {
  const chip = event.target.closest?.("[data-model-type]");
  if (!chip) return;
  for (const other of byId("catalog-type").children) {
    other.setAttribute("aria-checked", String(other === chip));
  }
  renderCatalogSource();
  // 種別が変われば結果は別物になる。前の種別の一覧を残さない。
  clearCatalogResults();
});

byId("catalog-source")?.addEventListener("click", (event) => {
  const chip = event.target.closest?.("[data-source]");
  if (!chip) return;
  void savePreferences({model_source: chip.dataset.source});
  state.preferences.model_source = chip.dataset.source;
  renderCatalogSource();
  // 配布元が変われば結果は別物になる。前の配布元の一覧を残さない。
  state.catalogResults = [];
  state.catalogPage = 0;
  byId("catalog-results").hidden = true;
  byId("catalog-pager").hidden = true;
  byId("catalog-empty").hidden = false;
  byId("catalog-empty").textContent = "配布元を変えました。もう一度検索してください。";
});

/* プリセットは歩数とガイダンスを一緒に入れる。片方だけ合わせると、
   4 歩なのにガイダンス 7.0 のような組み合わせになり、絵が焼ける。 */
document.addEventListener("click", (event) => {
  const chip = event.target.closest?.("[data-setting-preset]");
  if (!chip) return;
  byId("advanced-steps").value = chip.dataset.steps;
  if (chip.dataset.guidance !== undefined) byId("advanced-guidance").value = chip.dataset.guidance;
  for (const other of byId("model-settings-presets").children) {
    other.setAttribute("aria-pressed", String(other === chip));
  }
});
/* 開いた導線でそのまま閉じられるようにする。開くのと閉じるので押す場所が
   違うのは、片手で使っているときに探すことになる。 */
byId("nav-settings").addEventListener("click", () => {
  activate(state.view === "settings" ? (state.lastNonSettingsView || "create") : "settings");
});
byId("model-filters").addEventListener("click", (event) => {
  const button = event.target.closest("[data-model-filter]");
  if (!button) return;
  state.modelFilter = button.dataset.modelFilter;
  for (const item of byId("model-filters").children) {
    item.setAttribute("aria-checked", String(item === button));
  }
  renderModelManagement();
});

function handleModelExit(button) {
  const action = button.dataset.modelExit;
  const model = state.modelCatalog[Number(button.dataset.modelKey)];
  if (action === "retry" && model) void startModelInstall(model.model_id);
  else if (action === "storage") byId("model-storage").scrollIntoView({block: "center"});
  else if (action === "details") {
    setMode("advanced");
    byId("advanced-models")?.scrollIntoView({block: "center"});
  } else if (action === "activity") activate("activity");
  else void loadModelManagement();
}

for (const holder of [byId("model-table"), byId("model-error")]) {
  holder.addEventListener("click", (event) => {
    const install = event.target.closest("[data-install-model]");
    const installModel = install ? state.modelCatalog[Number(install.dataset.installModel)] : null;
    if (installModel) return void startModelInstall(installModel.model_id);
    const evaluate = event.target.closest("[data-evaluate-model]");
    const evaluateModel = evaluate ? state.modelCatalog[Number(evaluate.dataset.evaluateModel)] : null;
    if (evaluateModel) return void startModelEvaluation(evaluateModel.model_id);
    const remove = event.target.closest("[data-remove-model]");
    const removeModel = remove ? state.modelCatalog[Number(remove.dataset.removeModel)] : null;
    if (removeModel) return openModelRemove(removeModel.model_id);
    const cancel = event.target.closest("[data-cancel-model-operation]");
    if (cancel) return void cancelModelOperation(cancel.dataset.cancelModelOperation);
    const exit = event.target.closest("[data-model-exit]");
    if (exit) handleModelExit(exit);
  });
}

byId("model-mini-cancel").addEventListener("click", () => {
  void cancelModelOperation(byId("model-mini-cancel").dataset.operationId);
});
byId("model-remove-cancel").addEventListener("click", () => byId("model-remove-dialog").close());
byId("model-remove-confirm").addEventListener("click", async () => {
  const modelId = state.removeModelId;
  byId("model-remove-dialog").close();
  if (!modelId) return;
  try {
    const operation = await call("models.remove", {model_id: modelId});
    state.modelOperations.set(operation.id, operation);
    await call("models.operations.watch", {operation_ids: [operation.id]});
    await loadModelManagement();
  } catch (error) { showModelError(error?.code, modelId); }
});
for (const button of document.querySelectorAll("#shell-nav button")) {
  button.addEventListener("click", () => activate(button.dataset.view));
}
for (const button of document.querySelectorAll("[data-refresh]")) {
  button.addEventListener("click", () => activate(button.dataset.refresh, {sync: false}));
}

byId("domain-chips").addEventListener("click", (event) => {
  const chip = event.target.closest("[data-domain]");
  if (chip) setCreativeValue("domain", chip.dataset.domain);
});

byId("character-profile").addEventListener("change", (event) => {
  state.characterProfileId = event.target.value;
  resetReferenceAnalysis({keepSource: true});
  renderProfileChoices();
  clearError();
});
byId("style-profile").addEventListener("change", (event) => {
  state.styleProfileId = event.target.value;
  resetReferenceAnalysis({keepSource: true});
  renderProfileChoices();
  clearError();
});

byId("reference-focuses").addEventListener("click", (event) => {
  const button = event.target.closest("[data-reference-focus]");
  if (button) void analyzeReferenceFocus(button.dataset.referenceFocus);
});

for (const key of ["scene", "pose", "composition", "camera", "variation"]) {
  byId(`creative-${key}`).addEventListener("change", (event) => setCreativeValue(key, event.target.value));
}

/* 指示を書き換えたら、前の解析結果は捨てる。

   これは見た目の問題ではない。state.directorPlan は送信時にそのまま
   director_plan として渡るため、残しておくと「ライオンさん」の解析が
   「宇宙戦艦の戦闘」の生成に効いてしまう。実機で起きていた。 */
byId("create-intent").addEventListener("input", () => {
  if (!state.directorPlan) return;
  state.directorPlan = null;
  renderDirectorPlan(null);
});

byId("director-mode").addEventListener("change", (event) => {
  state.directorMode = event.target.value;
  state.directorPlan = null;
  renderDirectorPlan(null);
  renderDirectorControl();
  void savePreferences({director_mode: state.directorMode});
});

byId("create-form").addEventListener("input", (event) => {
  if (!event.target.id.startsWith("advanced-")) return;
  const detail = {
    "advanced-scene-details": "sceneDetails",
    "advanced-pose-details": "poseDetails",
    "advanced-composition-details": "compositionDetails",
    "advanced-camera-details": "cameraDetails",
  }[event.target.id];
  if (detail) {
    state.creative[detail] = event.target.value;
    rememberCreative();
  }
  clearError();
});

byId("create-form").addEventListener("change", (event) => {
  if (event.target.dataset.referenceRole) {
    const assetId = event.target.dataset.referenceRole;
    const previous = state.referenceOverrides.get(assetId) || {};
    state.referenceOverrides.set(assetId, {...previous, role: event.target.value});
    clearError();
    return;
  }
  if (event.target.dataset.referenceStrength) {
    const assetId = event.target.dataset.referenceStrength;
    const previous = state.referenceOverrides.get(assetId) || {};
    state.referenceOverrides.set(assetId, {...previous, strength: Number(event.target.value)});
    clearError();
    return;
  }
});

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
byId("project-3d-file").addEventListener("change", () => {
  state.project3dAsset = null;
  state.project3dName = "";
  byId("project-3d-error").hidden = true;
  render3dProject();
});
byId("project-3d-clear").addEventListener("click", () => {
  byId("project-3d-file").value = "";
  state.project3dAsset = null;
  state.project3dName = "";
  byId("project-3d-error").hidden = true;
  byId("project-3d-status").textContent = "";
  render3dProject();
});
byId("project-3d-host-file").addEventListener("click", () => void pickHost3dProject());
byId("project-3d-submit").addEventListener("click", () => void submit3dProject());

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

byId("viewer-save").addEventListener("click", () => void saveAsset(viewer.assetId));

byId("model-sort").addEventListener("change", (event) => {
  state.modelSort = event.target.value;
  renderModelManagement();
});

byId("catalog-search").addEventListener("click", () => void searchCatalog());
byId("catalog-query").addEventListener("keydown", (event) => {
  if (event.key === "Enter") { event.preventDefault(); void searchCatalog(); }
});
byId("catalog-results").addEventListener("click", (event) => {
  const install = event.target.closest("[data-install-repo]");
  if (install) {
    // 既にライセンスを承諾して取り込んだものなので、落とすだけで足りる。
    void startModelInstall(install.dataset.installRepo).then(() => {
      // 落とし始めたことが見えるように、状況の欄を開いて上へ運ぶ。
      const block = byId("model-downloads-block");
      block.open = true;
      block.scrollIntoView({block: "start"});
    });
    return;
  }
  const button = event.target.closest("[data-inspect-repo]");
  if (!button) return;
  // 表から直接は取り込まない。必ず中身とライセンスの確認を通す。
  void resolveCustomModel(button.dataset.inspectRepo);
});
byId("custom-result").addEventListener("click", (event) => {
  if (event.target.closest("#custom-add")) void addCustomModel();
  if (event.target.closest("#custom-cancel")) {
    customResolution = null;
    byId("custom-result").hidden = true;
    byId("custom-result").replaceChildren();
    byId("custom-error").hidden = true;
  }
});

byId("pack-open").addEventListener("click", () => void openPackDialog());
byId("pack-close").addEventListener("click", () => byId("pack-dialog").close());
byId("pack-cancel").addEventListener("click", () => byId("pack-dialog").close());
byId("pack-submit").addEventListener("click", () => void submitPack());
byId("pack-slots").addEventListener("click", (event) => {
  const choose = event.target.closest("[data-pack-slot]");
  if (!choose) return;
  pack.active = choose.dataset.packSlot;
  renderPackSlots();
});

byId("model-choice-model").addEventListener("change", () => {
  state.modelChoice = byId("model-choice-model").value ? "manual" : "auto";
  const dropped = dropIncompatibleLoras();
  renderModelChoice();
  renderLoraPicker();
  renderModelSettings();
  clearError();
  if (dropped) {
    byId("create-status").textContent =
      `選んだモデルに載せられない LoRA ${dropped} 件の選択を外しました。`;
  }
});

byId("profile-add-character").addEventListener("click", () => openProfileDialog("character"));
byId("profile-add-style").addEventListener("click", () => openProfileDialog("style"));
byId("profile-cancel").addEventListener("click", () => byId("profile-dialog").close());
byId("profile-form").addEventListener("submit", submitProfile);
byId("profile-list").addEventListener("click", (event) => {
  const remove = event.target.closest("[data-delete-profile]");
  if (remove) void deleteProfile(remove.dataset.deleteProfile);
});

byId("activity-empty").addEventListener("click", (event) => {
  if (event.target.closest("[data-retry-activity]")) void loadActivity();
});

for (const holder of [byId("activity-list"), byId("create-error")]) {
  holder.addEventListener("click", (event) => {
    const exit = event.target.closest("[data-exit-action]");
    if (exit) return runExit(exit.dataset.exitAction, jobById(exit.dataset.exitJob));
    const attach = event.target.closest("[data-attach-job]");
    if (attach) return attachToJob(attach.dataset.attachJob);
    const cancel = event.target.closest("[data-cancel-job]");
    if (cancel) {
      void call("jobs.cancel", {job_id: cancel.dataset.cancelJob})
        .then(() => loadActivity())
        .catch(() => {});
    }
    const cancelBatch = event.target.closest("[data-cancel-batch]");
    if (cancelBatch) {
      void call("creative.batches.cancel", {batch_id: cancelBatch.dataset.cancelBatch})
        .then(() => loadActivity())
        .catch(() => {});
    }
  });
}

byId("library-more").addEventListener("click", () => void loadLibrary());
byId("close-dialog").addEventListener("click", () => byId("detail-dialog").close());
byId("viewer-close").addEventListener("click", () => byId("viewer").close());
/* 閉じ方は 1 つではない。Esc でも背景でも閉じるので、要素そのものの
   close を捉えて止める。押した場所ごとに止め忘れを作らない。 */
byId("viewer").addEventListener("close", () => showViewerVideo(false));
byId("viewer-prev").addEventListener("click", () => stepViewer(-1));
byId("viewer-next").addEventListener("click", () => stepViewer(1));
byId("viewer").addEventListener("keydown", (event) => {
  // 拡大中は矢印でずらしたい、というほどの操作ではない。素直に送りに使う。
  if (event.key === "ArrowLeft") { event.preventDefault(); stepViewer(-1); }
  if (event.key === "ArrowRight") { event.preventDefault(); stepViewer(1); }
});
byId("viewer-detail").addEventListener("click", () => {
  byId("viewer").close();
  if (viewer.assetId) void openDetail(viewer.assetId);
});
byId("viewer-edit").addEventListener("click", () => {
  byId("viewer").close();
  activate("create");
  byId("create-status").textContent = "「画像を追加」から読み込ませてください。";
});

const viewerStage = byId("viewer-stage");
viewerStage.addEventListener("wheel", (event) => {
  event.preventDefault();
  viewerZoom(event.deltaY < 0 ? 1.15 : 0.87);
}, {passive: false});

viewerStage.addEventListener("dblclick", () => viewerZoom(viewer.scale > 1 ? 0.01 : 2.5));

viewerStage.addEventListener("pointerdown", (event) => {
  viewer.pointers.set(event.pointerId, event);
  if (viewer.pointers.size === 2) {
    const [first, second] = [...viewer.pointers.values()];
    viewer.pinch = Math.hypot(first.clientX - second.clientX, first.clientY - second.clientY);
    viewer.drag = null;
    return;
  }
  if (viewer.scale > 1) {
    viewer.drag = {x: event.clientX - viewer.x, y: event.clientY - viewer.y};
    byId("viewer-image").classList.add("dragging");
  }
});

viewerStage.addEventListener("pointermove", (event) => {
  if (!viewer.pointers.has(event.pointerId)) return;
  viewer.pointers.set(event.pointerId, event);
  if (viewer.pointers.size === 2 && viewer.pinch) {
    const [first, second] = [...viewer.pointers.values()];
    const distance = Math.hypot(first.clientX - second.clientX, first.clientY - second.clientY);
    viewerZoom(distance / viewer.pinch);
    viewer.pinch = distance;
    return;
  }
  if (!viewer.drag) return;
  viewer.x = event.clientX - viewer.drag.x;
  viewer.y = event.clientY - viewer.drag.y;
  viewerApply();
});

for (const name of ["pointerup", "pointercancel", "pointerleave"]) {
  viewerStage.addEventListener(name, (event) => {
    viewer.pointers.delete(event.pointerId);
    if (viewer.pointers.size < 2) viewer.pinch = 0;
    if (viewer.pointers.size === 0) {
      viewer.drag = null;
      byId("viewer-image").classList.remove("dragging");
    }
  });
}
byId("library-select").addEventListener("click", () => setLibrarySelecting(!state.librarySelecting));
byId("library-select-all").addEventListener("click", () => {
  for (const item of state.libraryItems) state.librarySelected.add(item.asset_id);
  renderLibrarySelection();
});
byId("library-select-none").addEventListener("click", () => {
  state.librarySelected.clear();
  renderLibrarySelection();
});
byId("library-delete").addEventListener("click", () => void deleteSelectedAssets());
const catalogQuery = byId("catalog-query");
const catalogClear = byId("catalog-clear");
function syncCatalogClear() { catalogClear.hidden = !catalogQuery.value; }
catalogQuery.addEventListener("input", syncCatalogClear);
catalogClear.addEventListener("click", () => {
  catalogQuery.value = "";
  syncCatalogClear();
  catalogQuery.focus();
  void searchCatalog();
});
syncCatalogClear();
byId("catalog-reset").addEventListener("click", () => {
  clearCatalogResults();
  byId("catalog-query").value = "";
  syncCatalogClear();
});
byId("catalog-prev").addEventListener("click", () => {
  state.catalogPage -= 1;
  renderCatalogPage();
  byId("catalog-results").scrollIntoView({block: "start"});
});
byId("catalog-next").addEventListener("click", () => {
  state.catalogPage += 1;
  renderCatalogPage();
  byId("catalog-results").scrollIntoView({block: "start"});
});
/* 画面に戻ったときに、切れていた間の分を取り直す。socket が生きていれば
   何もしない（張り直しも取り直しも要らない）ので、常時 polling にはしない。
   携帯で頁を離れるたびに socket は閉じられるので、ここが実質の復帰点である。 */
async function resumeAfterInterruption() {
  if (window.parent === window || document.visibilityState !== "visible") return;
  if (socketOpen()) return;
  try {
    await connectSocket();
  } catch { return; }
  await refreshSession(["jobs", "library", "model_operations", "creative_batches"]);
  restoreProgressView();
  renderActivity();
}

document.addEventListener("visibilitychange", () => void resumeAfterInterruption());
// bfcache から戻った頁は JS の状態だけが生き残り、socket は閉じている。
window.addEventListener("pageshow", (event) => {
  if (event.persisted) void resumeAfterInterruption();
});

/* 覚えていることの逆。積み上がった指定を 1 つずつ「自動」に戻すのは面倒で、
   結局タブを開き直すことになっていた。1 押しで最初の状態へ戻す。 */
byId("create-reset").addEventListener("click", async () => {
  const accepted = await confirmModelAction({
    title: "初期に戻す",
    detail: "入力した内容と、選んだドメイン・シーン・見せ方を消して最初の状態に戻します。",
    confirmLabel: "戻す",
  });
  if (!accepted) return;
  byId("create-intent").value = "";
  state.creative = {...CREATIVE_DEFAULTS};
  state.characterProfileId = "";
  state.styleProfileId = "";
  clearError();
  byId("create-status").textContent = "";
  renderCreative();
  renderProfileChoices();
  updateCreativeSummary();
  // 覚えている分も消す。残すと次に開いたときに戻ってくる。
  window.clearTimeout(creativeSaveTimer);
  void savePreferences({last_creative_spec: {}});
  byId("create-intent").focus();
});

byId("activity-clear").addEventListener("click", async () => {
  // 走っているものは消えない。消えるのは終わった記録だけで、資産の来歴は
  // 資産側に残る（一覧から下げるだけで、記録そのものは壊さない）。
  const accepted = await confirmModelAction({
    title: "履歴を消す",
    detail: "終わった実行を一覧から消します。作った素材とその来歴は残ります。",
    confirmLabel: "消す",
  });
  if (!accepted) return;
  try { await call("jobs.clear", {}); } catch { return; }
  await loadActivity();
});
byId("model-downloads-clear").addEventListener("click", () => void clearModelDownloadHistory());
// ダウンロード一覧は行ごと作り直す。中止と再試行は委譲で受ける。
byId("model-downloads").addEventListener("click", (event) => {
  const cancel = event.target.closest("[data-cancel-model-operation]");
  if (cancel) return void cancelModelOperation(cancel.dataset.cancelModelOperation);
  const retry = event.target.closest("[data-retry-model-operation]");
  if (retry) return void startModelInstall(retry.dataset.retryModelOperation);
});
byId("result-image").addEventListener("click", () => {
  const assetId = byId("result-image").dataset.assetId;
  if (assetId) void openViewer(assetId);
});
byId("result-detail").addEventListener("click", () => {
  const assetId = byId("result-image").dataset.assetId;
  if (assetId) void openDetail(assetId);
});
byId("result-edit").addEventListener("click", () => {
  byId("create-status").textContent = "ライブラリから画像を選び直して「画像を追加」に読み込ませてください。";
});
byId("result-evaluate").addEventListener("click", async () => {
  const button = byId("result-evaluate");
  const note = byId("result-evaluation");
  if (state.resultAssetIds.length < 2) return;
  button.disabled = true;
  button.textContent = "比べています…";
  try {
    const evaluated = await call("creative.evaluate", {
      asset_ids: state.resultAssetIds,
      reference_asset_ids: selectedProfileReferences().map((item) => item.asset_id).slice(0, 4),
      intent: byId("create-intent").value,
      creative_plan: creativeSpec(),
    });
    await showResult(evaluated.ranked_asset_ids);
    const best = evaluated.results[0];
    note.textContent = state.mode === "advanced"
      ? `おすすめ: ${best.summary} · ${JSON.stringify(best.scores)} · rank ${best.rank_score}`
      : `おすすめ: ${best.summary}`;
  } catch (error) {
    note.textContent = error?.message || "候補を比べられませんでした。";
  } finally {
    button.disabled = false;
    button.textContent = "候補を比べる";
  }
});
byId("composition-update-text").addEventListener("click", async () => {
  const composition = state.currentComposition;
  if (!composition) return;
  const status = byId("composition-edit-status");
  status.textContent = "文字を更新しています…";
  try {
    const updated = await call("creative.compositions.update_text", {
      composition_id: composition.id,
      title: byId("composition-edit-title").value,
      caption: byId("composition-edit-caption").value,
    });
    state.currentComposition = updated;
    await showResult(updated.asset_ids);
    await loadRecent();
    status.textContent = "カットを作り直さず、文字だけ更新しました。";
  } catch (error) {
    status.textContent = error?.message || "文字を更新できませんでした。";
  }
});
for (const id of ["progress-cancel", "mini-cancel"]) {
  byId(id).addEventListener("click", () => {
    if (state.activeComposition) {
      void call("creative.compositions.cancel", {composition_id: state.activeComposition})
        .then(finishComposition).catch(() => {});
    } else if (state.activeBatch) {
      void call("creative.batches.cancel", {batch_id: state.activeBatch}).then(finishBatch).catch(() => {});
    } else if (state.activeJob) void call("jobs.cancel", {job_id: state.activeJob}).catch(() => {});
  });
}

/* ── session ──────────────────────────────────────────────────────────── */

/* 状態の正はサーバ側の session snapshot にある。boot も更新も同じ 1 メソッドで
   読む。旧 boot は直列 10 往復で、そのうえ 1 秒 polling を 3 本回していた。 */

const usable = (part) => part && typeof part === "object" && part.unavailable !== true;

function applySessionParts(snapshot) {
  if (!snapshot || typeof snapshot !== "object") return;
  if (usable(snapshot.preferences)) state.preferences = snapshot.preferences.values || {};
  if (usable(snapshot.capabilities)) {
    state.capabilities = snapshot.capabilities.capabilities || {};
    state.envelope = snapshot.capabilities.envelope || null;
    state.deviceVramBytes = snapshot.capabilities.device?.vram_bytes || 0;
    state.presets = snapshot.capabilities.presets || [];
    render3dProject();
    renderCreateMedia();
  }
  if (usable(snapshot.profiles)) state.profiles = snapshot.profiles.items || [];
  if (usable(snapshot.reference_collections)) {
    state.referenceCollections = snapshot.reference_collections.items || [];
  }
  if (usable(snapshot.domain_profiles)) state.domainProfiles = snapshot.domain_profiles.items || [];
  if (usable(snapshot.creative_batches)) state.batches = snapshot.creative_batches.items || [];
  if (usable(snapshot.jobs)) state.jobs = snapshot.jobs.items || [];
}

function applyModelSession(snapshot) {
  if (usable(snapshot.model_catalog)) {
    const catalog = snapshot.model_catalog;
    state.modelCatalog = catalog.items || [];
    state.modelManagementAvailable = catalog.management_available !== false;
    state.modelEvaluationIds = new Set(catalog.evaluation?.available_model_ids || []);
    const storage = catalog.storage || {};
    byId("model-storage").textContent = state.modelManagementAvailable
      ? `管理中 ${formatBytes(storage.managed_bytes)} · 空き ${formatBytes(storage.free_bytes)}`
      : "この表示では一覧のみです。追加・削除は ControlDeck から開いてください。";
    byId("model-error").hidden = true;
  }
  if (usable(snapshot.model_operations)) {
    // 単体表示では live event が来ない。取り直した一覧からも速度を出す。
    for (const item of snapshot.model_operations.items || []) recordModelSpeed(item);
    state.modelOperations = new Map((snapshot.model_operations.items || []).map((item) => [item.id, item]));
  }
  if (usable(snapshot.model_catalog) || usable(snapshot.model_operations)) {
    renderModelManagement();
    renderModelMiniProgress();
    renderAdvancedModelChoices();
    renderModelChoice();
    renderModelSettings();
    renderLoraPicker();
  }
}

async function applyRecent(page) {
  const items = (page.items || []).filter((item) => item.preview_kind);
  const strip = byId("recent-strip");
  strip.replaceChildren();
  byId("recent-empty").hidden = items.length > 0;
  for (const item of items) {
    strip.append(await thumbnailButton(item.asset_id, () => { activate("library"); }, item.thumbnail));
  }
}

/* サーバから「この部分が変わった」と言われた分だけ読み直す。 */
async function refreshSession(parts) {
  let snapshot;
  try { snapshot = await call("workspace.session", {parts}); } catch { return; }
  applySessionParts(snapshot);
  if (parts.includes("profiles") || parts.includes("reference_collections")) renderProfileChoices();
  if (parts.includes("model_catalog") || parts.includes("model_operations") || parts.includes("models")) {
    applyModelSession(snapshot);
  }
  if (parts.includes("library") && usable(snapshot.library)) await applyRecent(snapshot.library);
  if (parts.includes("creative_batches")) {
    const active = (state.batches || []).find((batch) => batch.id === state.activeBatch);
    if (active) {
      showBatchProgress(active);
      if (["succeeded", "partial", "failed", "canceled"].includes(active.state)) await finishBatch(active);
    }
  }
  if (parts.includes("creative_compositions") && usable(snapshot.creative_compositions)) {
    const items = snapshot.creative_compositions.items || [];
    const active = items.find((item) => item.id === state.activeComposition);
    if (active) {
      state.currentComposition = active;
      showCompositionProgress(active);
      if (["succeeded", "partial", "failed", "canceled"].includes(active.state)) {
        await finishComposition(active);
      }
    }
  }
  if (state.view === "activity") renderActivity();
}

/* ── boot ─────────────────────────────────────────────────────────────── */

async function boot() {
  let snapshot = {};
  try { snapshot = await call("workspace.session"); } catch { snapshot = {}; }
  applySessionParts(snapshot);

  state.creativeTemplates = embeddedCreativeTemplates();
  if (!state.creativeTemplates) {
    try { state.creativeTemplates = await call("creative.templates"); }
    catch { state.creativeTemplates = {domains: [], scenes: [], poses: [], compositions: [], cameras: [], variations: []}; }
  }

  // 前回の続きから始める。毎回ドメインから選び直させるほどの理由が無い。
  const rememberedSpec = state.preferences.last_creative_spec;
  if (rememberedSpec && typeof rememberedSpec === "object") {
    for (const [key, value] of Object.entries(rememberedSpec)) {
      if (key in CREATIVE_DEFAULTS) state.creative[key] = value;
    }
  }
  state.directorMode = directorAvailable()
    ? (state.preferences.director_mode || "refine")
    : "original";
  renderCreative();
  renderDirectorControl();
  renderProfileChoices();
  renderPackProfiles();
  renderPresets();
  renderCounts();
  setMode(state.preferences.mode || "simple", {persist: false});
  setCreateMedia(state.preferences.create_media || "image", {persist: false});
  applyModelSession(snapshot);
  await refreshAttachment();
  if (usable(snapshot.library)) await applyRecent(snapshot.library);
  restoreCreativeComposition(snapshot);
  restoreCreativeBatch(snapshot);
  activate(state.preferences.last_view || "create", {sync: false});
  // create 以外を開いていても、走っている job は拾ってミニ進捗に出す。
  restoreProgressView();
  // watch はサーバが session と一緒に張る。standalone だけ従来どおり要求する。
  if (window.parent === window) await call("jobs.watch", {job_ids: []}).catch(() => {});
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
      if (state.activeComposition) {
        void call("creative.compositions.cancel", {composition_id: state.activeComposition}).catch(() => {});
      }
      if (state.activeBatch) void call("creative.batches.cancel", {batch_id: state.activeBatch}).catch(() => {});
      if (state.activeJob) void call("jobs.cancel", {job_id: state.activeJob}).catch(() => {});
      state.activeBatch = "";
      state.activeComposition = "";
      state.activeJob = "";
      setHostBusy(false);
    }
  };
  state.bridgePort.start();
  // 1 度きりにしない。最初の接続が失敗しただけで画面が永久に空のままになる。
  void (async () => {
    for (let attempt = 0; attempt < 5; attempt += 1) {
      try {
        await connectSocket();
        await boot();
        return;
      } catch {
        document.documentElement.dataset.bridge = "error";
        // 落ちている相手を叩き続けない。間隔を広げながら数回だけ試す。
        await new Promise((wake) => setTimeout(wake, 500 * 2 ** attempt));
      }
    }
  })();
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
