"""PR-U1: static contract between the workspace UI and the backend.

These catch the drift that silently breaks the UI: a capability name the
backend never emits, an error code with no Japanese sentence, an advanced
control that leaks into simple mode, or a browser storage call sneaking back
into an opaque-origin frame. They are regression evidence only; layout and
behaviour are observed in a real browser (PR-U7).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
FRONTEND = ROOT / "frontend"
BACKEND = ROOT / "backend" / "mediaforge"

SCRIPT = (FRONTEND / "app.js").read_text(encoding="utf-8")
MARKUP = (FRONTEND / "index.html").read_text(encoding="utf-8")
STYLES = (FRONTEND / "styles.css").read_text(encoding="utf-8")
ADDON = json.loads((ROOT / "addon.json").read_text(encoding="utf-8"))

# DOM 契約。app.js の仕様であり、テストと Playwright がこの名前に依存する。
DOM_IDS = (
    "app", "skeleton", "shell-header", "shell-nav",
    "nav-create", "nav-library", "nav-activity", "nav-settings",
    "mode-simple", "mode-advanced",
    "create-media-switch", "create-media-image", "create-media-video",
    "create-intent-label", "video-create-fields",
    "video-create-summary", "video-create-note", "video-create-settings", "result-video",
    "create-form", "create-intent", "create-submit", "create-status",
    "attach-image", "attach-size", "source-file", "edit-actions", "guarantee-badge",
    "size-block", "size-label", "size-note", "size-presets", "count-chips",
    "size-custom", "custom-width", "custom-height", "custom-ratios",
    "creative-simple", "domain-chips", "scene-framing", "scene-framing-summary",
    "creative-scene", "creative-pose", "creative-composition", "creative-camera", "creative-variation",
    "profile-choice", "character-profile", "style-profile", "profile-choice-note",
    # G6 S4: 実装済みだが到達できなかった機能の入口
    "model-choice", "model-choice-model", "model-choice-note",
    "profile-add-character", "profile-add-style", "profile-list", "profile-dialog",
    "profile-name", "profile-appearance", "profile-art-style", "profile-references",
    "pack-section", "pack-profile", "pack-open", "pack-dialog", "pack-slots", "pack-progress",
    "project-3d-section", "project-3d-file", "project-3d-host-file", "project-3d-clear", "project-3d-submit",
    "project-3d-options", "project-3d-error", "project-3d-status",
    "custom-result", "custom-error",
    # UX3: 書き出し導線と、重複を解消した詳細設定
    "viewer-save", "viewer-save-note",
    "catalog-query", "catalog-sort", "catalog-style", "catalog-search",
    "catalog-results", "catalog-empty",
    "model-table", "model-sort",
    "model-downloads", "model-downloads-empty", "model-downloads-count",
    "reference-intelligence", "reference-focuses", "reference-analysis-summary",
    "reference-analysis-note",
    "composition-options", "composition-title", "composition-caption",
    "composition-text-edit", "composition-edit-title", "composition-edit-caption",
    "composition-update-text", "composition-edit-status",
    "create-error",
    "mask-input", "mask-draw", "mask-preview", "mask-state",
    "mask-dialog", "mask-canvas", "mask-brush", "mask-eraser", "mask-undo", "mask-clear",
    "mask-apply", "mask-cancel",
    "outpaint-input", "outpaint-ratios", "outpaint-scales", "outpaint-preview", "outpaint-note",
    "stage", "stage-progress", "stage-result", "candidate-strip", "recent-strip",
    "result-evaluate", "result-evaluation",
    "mini-progress", "library-grid", "library-count", "activity-list",
    "detail-dialog",
    "model-storage", "model-filters", "model-management-note", "model-table", "model-empty", "model-error",
    "model-mini-progress", "model-mini-phase", "model-mini-bar", "model-mini-cancel",
    "model-remove-dialog", "model-remove-summary", "model-remove-detail",
    "model-remove-cancel", "model-remove-confirm",
    "viewer", "viewer-stage", "viewer-image", "viewer-caption",
    "viewer-detail", "viewer-edit", "viewer-close",
)

ADVANCED_IDS = (
    "advanced-create", "advanced-format",
    "advanced-count", "advanced-policy", "advanced-model", "advanced-semantic",
    "advanced-attempts", "advanced-settings", "advanced-models", "advanced-mask-file",
    "advanced-host-state", "advanced-capability-list",
    "advanced-domain", "advanced-scene", "advanced-scene-details", "advanced-pose",
    "advanced-pose-details", "advanced-composition", "advanced-composition-details",
    "advanced-camera", "advanced-camera-details", "advanced-variation",
    "advanced-reference-block", "advanced-reference-roles", "advanced-reference-reason",
    # 自動で決められなかった項目を、確認すべきものとしてまとめて出す場所。
    "model-settings", "model-settings-model", "model-settings-check",
    "model-settings-check-list", "model-settings-settled", "model-settings-settled-list",
    "model-settings-presets", "model-settings-note",
    "advanced-steps", "advanced-guidance",
)

# 配布元の切り替え。モデル管理タブにあり、詳細モードとは無関係。
CATALOG_IDS = (
    "catalog-source", "catalog-source-note", "catalog-type",
    "lora-picker", "lora-picker-note", "lora-list",
)


def test_the_frame_never_touches_browser_storage():
    for forbidden in ("localStorage", "sessionStorage", "document.cookie", "indexedDB"):
        assert forbidden not in SCRIPT, f"opaque sandbox では {forbidden} を使えない"
        assert forbidden not in MARKUP


def test_dom_contract_ids_exist():
    for name in DOM_IDS:
        assert f'id="{name}"' in MARKUP, f"DOM 契約の id が無い: {name}"


def test_3d_project_action_is_capability_and_selection_gated_and_typed():
    body = SCRIPT[SCRIPT.index("function render3dProject"):SCRIPT.index("function submit3dProject")]
    assert 'state.capabilities["asset.3d_project_pack"]' in body
    assert 'byId("project-3d-submit").hidden = !available || !selection;' in body
    assert 'state.mode !== "advanced"' in body
    submit = SCRIPT[SCRIPT.index("async function submit3dProject"):SCRIPT.index("/* backend には asset.pack")]
    assert 'operation: "asset.pack"' in submit
    assert 'profile: "3d.project.glb"' in submit
    assert 'schema_version: "3d.compile-options@1"' in SCRIPT
    for forbidden in ("--python", "bpy.", "blender_path", "project_path", "script_body"):
        assert forbidden not in submit
    picker = SCRIPT[SCRIPT.index("async function pickHost3dProject"):SCRIPT.index("/* backend には asset.pack")]
    assert 'callHost("host.file.pick"' in picker
    assert 'call("assets.import_grant"' in picker
    assert 'media_type: "model/gltf-binary"' in picker


def test_3d_zip_viewer_uses_preview_instead_of_rendering_the_archive():
    viewer = SCRIPT[SCRIPT.index("async function openViewer("):SCRIPT.index("/* 自動で選んだとき")]
    package = viewer[viewer.index('item?.preview_kind === "project_3d"'):]
    assert 'call("assets.thumbnail"' in package
    assert package.index('call("assets.thumbnail"') < package.index('call("assets.content"')
    assert "ZIP · プレビュー" in package


def test_library_does_not_request_a_thumbnail_for_non_preview_assets():
    card = SCRIPT[SCRIPT.index("async function libraryCard"):SCRIPT.index("/* ── 全画面ビューア")]
    gate = card[card.index("if (!item.preview_kind)"):]
    assert gate.index("return card") < gate.index('call("assets.thumbnail"')
    recent = SCRIPT[SCRIPT.index("async function applyRecent"):SCRIPT.index("/* サーバから")]
    assert ".filter((item) => item.preview_kind)" in recent


def test_model_management_actions_are_simple_but_technical_details_are_advanced():
    without_templates = re.sub(r"<template[\s\S]*?</template>", "", MARKUP)
    for name in ("model-filters", "model-table", "model-storage"):
        assert f'id="{name}"' in without_templates
    assert 'id="advanced-models"' not in without_templates
    assert "models.install" in SCRIPT and "models.remove" in SCRIPT and "models.evaluate" in SCRIPT
    assert "models.operations.watch" in SCRIPT and "model.operation.changed" in SCRIPT
    assert 'data-model-filter="installed"' in MARKUP
    assert 'data-model-filter="recommended"' in MARKUP
    assert 'data-model-filter="image"' in MARKUP
    assert 'data-model-filter="video"' in MARKUP
    assert 'data-model-filter="all"' in MARKUP
    assert 'model.ownership !== "managed"' in SCRIPT
    assert '"外部で管理"' in SCRIPT
    assert '"導入済み・利用不可"' in SCRIPT
    assert "ライセンス同意とは別の実用品質・メモリ安全性" in SCRIPT
    assert "ダウンロードだけでは動画生成は有効になりません" in SCRIPT
    assert 'className = "model-action-note"' in SCRIPT
    assert 'experimental: "実験的・未実測"' in SCRIPT
    assert "model.license_acceptance_id" in SCRIPT
    assert "window.confirm" not in SCRIPT
    assert 'id="model-confirm-dialog"' in MARKUP
    assert "confirmModelAction" in SCRIPT
    assert "license_acceptance: licenseAcceptance" in SCRIPT
    assert "MAX_MANAGED_MODEL_DOWNLOAD_BYTES = 32_000_000_000" in SCRIPT
    # 上限超過は操作ではなく状態なので、ボタンではなく理由として出す。
    assert '"容量超過"' in SCRIPT
    assert 'evaluate.textContent = "評価"' in SCRIPT
    assert "state.modelEvaluationIds.has(model.model_id)" in SCRIPT
    assert "card.dataset.modelId" not in SCRIPT
    assert "dataset.modelId =" not in SCRIPT


def test_creative_controls_use_the_versioned_catalog_and_preserve_prompt_only_requests():
    without_templates = re.sub(r"<template[\s\S]*?</template>", "", MARKUP)
    for name in ("domain-chips", "creative-scene", "creative-pose", "creative-composition", "creative-camera"):
        assert f'id="{name}"' in without_templates
    assert 'id="scene-framing"' in without_templates
    assert 'id="advanced-domain"' not in without_templates
    assert "MEDIA_FORGE_CREATIVE_TEMPLATES" in MARKUP
    assert 'byId("creative-template-data")' in SCRIPT
    assert 'if (creativeActive(spec) || directorPlan)' in SCRIPT
    assert 'id="director-mode"' in without_templates
    assert 'id="director-understanding"' in without_templates
    assert 'call("creative.direct"' in SCRIPT
    assert 'call("creative.validate"' in SCRIPT
    assert 'call("jobs.create", request)' in SCRIPT


def test_profiles_are_simple_but_reference_roles_and_strength_are_advanced():
    without_templates = re.sub(r"<template[\s\S]*?</template>", "", MARKUP)
    assert 'id="character-profile"' in without_templates
    assert 'id="style-profile"' in without_templates
    assert 'id="advanced-reference-roles"' not in without_templates
    assert "selectedProfileReferences" in SCRIPT
    assert "max_reference_assets" in SCRIPT
    assert "supports_reference_strength" in SCRIPT


def test_reference_intelligence_is_image_gated_and_uses_the_private_bridge():
    without_templates = re.sub(r"<template[\s\S]*?</template>", "", MARKUP)
    for name in ("reference-intelligence", "reference-focuses", "reference-analysis-summary"):
        assert f'id="{name}"' in without_templates
    for focus in ("overall", "identity", "pose", "palette", "composition", "style"):
        assert f'data-reference-focus="{focus}"' in MARKUP
    assert 'call("references.analyze"' in SCRIPT
    assert 'reference_analysis: referenceAnalysis' in SCRIPT
    assert 'Boolean(attachedFile() || selectedProfileReferences().length)' in SCRIPT
    assert "data:image" not in SCRIPT


def test_intentional_variations_use_durable_batches_and_advanced_drilldown():
    assert 'call("creative.batches.create"' in SCRIPT
    assert 'call("creative.batches.get"' in SCRIPT
    assert 'call("creative.batches.cancel"' in SCRIPT
    assert "restoreCreativeBatch" in SCRIPT
    assert "creativeBatchRow" in SCRIPT
    assert "dataset.cancelBatch" in SCRIPT
    assert "child_job_ids" in SCRIPT


def test_multicut_composer_reuses_create_result_and_viewer():
    assert 'call("creative.compositions.create"' in SCRIPT
    assert "director_mode: state.directorMode" in SCRIPT
    assert "reference_analysis: referenceAnalysis" in SCRIPT
    assert "if (composition.director) renderDirectorPlan(composition.director)" in SCRIPT
    assert 'call("creative.compositions.get"' in SCRIPT
    assert 'call("creative.compositions.update_text"' in SCRIPT
    assert "restoreCreativeComposition" in SCRIPT
    assert 'byId("composition-update-text")' in SCRIPT
    assert 'await showResult(composition.asset_ids)' in SCRIPT


def test_evaluator_only_ranks_existing_candidates():
    assert 'call("creative.evaluate"' in SCRIPT
    assert "ranked_asset_ids" in SCRIPT
    assert "regeneration_requested" not in SCRIPT
    assert 'capabilityState("image.creative_evaluation")' in SCRIPT


def test_model_remove_has_exactly_one_confirmation_dialog():
    assert MARKUP.count('id="model-remove-dialog"') == 1
    assert MARKUP.count('id="model-remove-confirm"') == 1
    assert "openModelRemove" in SCRIPT and 'call("models.remove"' in SCRIPT


def test_navigation_is_declared_once_and_switched_by_css():
    """PC 上部 / モバイル下部は同じ要素を CSS で動かす。id を重複させない。"""
    for name in ("nav-create", "nav-library", "nav-activity"):
        assert MARKUP.count(f'id="{name}"') == 1
    assert "@media (max-width: 767px)" in STYLES
    mobile = STYLES.split("@media (max-width: 767px)", 1)[1]
    assert "#shell-nav" in mobile and "position: fixed" in mobile


def test_mobile_layout_respects_safe_area_and_touch_targets():
    assert "--safe-bottom" in STYLES
    assert "var(--safe-bottom)" in STYLES
    # 主要な操作は 38px 以上、主ボタンとタブは 44px 以上
    assert "min-height: 46px" in STYLES  # primary
    assert "--tabbar: 60px" in STYLES


def capability_names() -> set[str]:
    source = (BACKEND / "app.py").read_text(encoding="utf-8")
    document = source.split("async def capability_document(", 1)[1].split("@app.get", 1)[0]
    return set(re.findall(r'"((?:image|video|3d)\.[a-z_0-9]+)":', document))


# operation は capability ではない。UI は両方を文字列で持つので明示的に分ける。
OPERATIONS = {
    "image.generate", "image.edit", "video.generate", "video.edit", "media.inspect", "asset.pack",
}


def validator_names() -> set[str]:
    """検証の記録名も image.* の形をしている。capability と混ぜて数えない。

    固定表ではなく backend が実際に出している名前を読む。UI が存在しない
    validator を訳している場合は、そちらを別の test が捕まえる。
    """
    names: set[str] = set()
    for path in sorted(BACKEND.glob("*.py")):
        names.update(re.findall(
            r'"validator":\s*"([a-z_0-9.]+)"', path.read_text(encoding="utf-8")
        ))
    return names


def test_every_capability_the_ui_reads_is_emitted_by_the_backend():
    emitted = capability_names()
    assert emitted, "capability document を読み取れなかった"
    used = set(re.findall(r'"((?:image|video|3d)\.[a-z_0-9]+)"', SCRIPT))
    used -= OPERATIONS | validator_names()
    assert used, "UI が capability 名を参照していない"
    assert used <= emitted, f"backend が出さない capability を UI が参照している: {sorted(used - emitted)}"


def test_operations_the_ui_submits_are_valid_schema_values():
    schema = json.loads((ROOT / "schemas" / "job-request.json").read_text(encoding="utf-8"))
    allowed = set(schema["properties"]["operation"]["enum"])
    used = set(re.findall(r'"((?:image|video|3d|media|asset)\.[a-z_0-9]+)"', SCRIPT)) & OPERATIONS
    assert used, "UI が operation を指定していない"
    assert used <= allowed


def test_create_media_switch_is_mobile_safe_and_video_is_capability_gated():
    assert 'data-create-media="image"' in MARKUP
    assert 'aria-label="作る素材"' in MARKUP
    render = SCRIPT[SCRIPT.index("function renderCreateMedia"):SCRIPT.index("function setCreateMedia")]
    assert '"video.text_to_video"' in render
    assert '"video.image_to_video"' in SCRIPT
    assert 'submit.disabled = video && !usable' in render
    submit = SCRIPT[SCRIPT.index("async function submitVideoJob"):SCRIPT.index("async function submitJob")]
    assert 'operation: "video.generate"' in submit
    assert 'output: {format: "mp4", count: 1}' in submit
    problem = SCRIPT[SCRIPT.index("function requestProblem"):SCRIPT.index("async function submitVideoJob")]
    assert 'videoCapabilityUsable()' in problem
    # 切り替えはヘッダーに常駐し、表示モードのすぐ左に並ぶ。狭い画面でも折り返さず、
    # 指で押せる大きさを保つこと。絵だけなので、読み上げには言葉を残す。
    header = MARKUP[MARKUP.index("<header id=\"shell-header\""):MARKUP.index("</header>")]
    assert header.index('id="create-media-switch"') < header.index('class="modeswitch"')
    # 切り替えは左に寄せ、設定だけを右端へ逃がす。余白は 2 つの切り替えの後ろに置く。
    assert header.index('class="modeswitch"') < header.index('class="grow"')
    assert header.index('class="grow"') < header.index('id="nav-settings"')
    assert 'aria-label="画像を作る"' in header and 'aria-label="動画を作る"' in header
    switch = STYLES[STYLES.index(".mediaswitch button {"):STYLES.index(".mediaswitch button svg")]
    assert "min-width: 40px" in switch and "min-height: 32px" in switch
    # 試験中は絵の上の印と、読み上げ・長押しに出る言葉の両方で伝える。
    assert '.mediaswitch button[data-experimental="true"]::after' in STYLES
    assert 'videoButton.setAttribute("aria-label", videoLabel)' in SCRIPT


# 失敗コードは複数の形で書かれる: HTTPException の detail、WorkerFailure の第 1 引数、
# 判定式の中の裸の文字列。どれか 1 つに絞ると UI 側の文言が実在しないコードを説明し始める。
CODE_PATTERNS = (
    r'(?:code=|"code":\s*)"([a-z][a-z0-9_]+)"',
    r'(?:raise|return) \w+\(\s*\n?\s*"([a-z][a-z0-9_]+)"',
    r'^\s*"([a-z][a-z0-9_]{6,})",?$',
    r'else "([a-z][a-z0-9_]{6,})"',
    # detail.get("code", "worker_crash") のような既定値も実在するコード
    r'\.get\("code", "([a-z][a-z0-9_]+)"\)',
)


def backend_error_codes() -> set[str]:
    codes: set[str] = set()
    for path in BACKEND.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for pattern in CODE_PATTERNS:
            codes.update(re.findall(pattern, source, re.MULTILINE))
    return codes


def ui_thrown_codes() -> set[str]:
    """UI 自身が投げる code（受付前に落とすもの）も説明の対象になる。

    standaloneCall は ControlDeck 無しで開発するための shim であり、
    製品経路では通らない。利用者向けの文言を要求しない。
    """
    product = SCRIPT.split("async function standaloneCall(", 1)
    product = product[0] + product[1].split("\nasync function ", 1)[1]
    return set(re.findall(r'throw \{code: "([a-z][a-z0-9_]+)"', product))


def failure_table() -> set[str]:
    table = SCRIPT.split("const FAILURES = {", 1)[1].split("\n};", 1)[0]
    return set(re.findall(r"^\s{2}([a-z][a-z0-9_]+):", table, re.MULTILINE))


def test_failure_sentences_only_name_real_codes():
    named = failure_table()
    assert named, "失敗の言い換え表が読み取れなかった"
    unknown = named - backend_error_codes() - ui_thrown_codes()
    assert not unknown, f"どこにも存在しない error code を UI が説明している: {sorted(unknown)}"


def test_every_code_the_ui_throws_has_a_sentence():
    missing = ui_thrown_codes() - failure_table()
    assert not missing, f"UI が投げるのに説明の無い code: {sorted(missing)}"


def test_every_phase_the_backend_reports_has_japanese_text():
    jobs = (BACKEND / "jobs.py").read_text(encoding="utf-8")
    phases = set(re.findall(r'phase="([a-z_]+)"', jobs))
    table = SCRIPT.split("const PHASE_TEXT = {", 1)[1].split("};", 1)[0]
    described = set(re.findall(r"^\s{2}([a-z_]+):", table, re.MULTILINE))
    assert phases <= described, f"日本語の無い phase がある: {sorted(phases - described)}"


def test_workspace_routes_match_the_views_the_ui_syncs():
    source = (BACKEND / "app.py").read_text(encoding="utf-8")
    served = set(re.findall(r'@app\.get\("(/[a-z]*)"\)', source))
    for route in ("/", "/library", "/activity", "/settings"):
        assert route in served, f"workspace ルートが無い: {route}"


def test_addon_declares_a_real_mobile_view():
    view = next(item for item in ADDON["contributions"]["embedded_views"] if item["id"] == "workspace")
    assert view["mobile"] == "embedded", "モバイル IA を実装したので companion ではない"
    # 版はリリースごとに動く。固定値ではなくパッケージ側と一致していることを見る。
    source = (ROOT / "backend" / "mediaforge" / "__init__.py").read_text(encoding="utf-8")
    packaged = re.search(r'__version__ = "([^"]+)"', source).group(1)
    assert ADDON["version"] == packaged, "addon.json と mediaforge.__version__ が食い違っている"


def test_the_library_has_no_kind_filter():
    """4 つの札が見出しを 1 行占めていた。絞り込む価値のある分け方ではない。"""
    assert 'id="library-kinds"' not in MARKUP
    assert "libraryKind" not in SCRIPT
    assert '"library.list", {kind: "all"' in SCRIPT, "全件を取っていない"
    assert 'id="library-count"' in MARKUP, "何枚あるのかが見出しから消えた"


def test_preference_keys_used_by_the_ui_are_allowlisted():
    from mediaforge import preferences

    used = set(re.findall(r"savePreferences\(\{\s*([a-z_]+)", SCRIPT))
    used.update(re.findall(r"state\.preferences\.([a-z_]+)", SCRIPT))
    assert used, "preferences を使っていない"
    unknown = used - set(preferences.ALLOWED)
    assert not unknown, f"backend が拒否する preference キーを UI が使っている: {sorted(unknown)}"


def test_mask_file_input_is_an_advanced_escape_hatch_only():
    """筆で塗る経路が既定。ファイル指定は詳細モードにだけ残す。"""
    without_templates = re.sub(r"<template[\s\S]*?</template>", "", MARKUP)
    assert 'id="mask-file"' not in without_templates, "マスクのファイル指定が既定経路に出ている"
    assert 'id="mask-file"' in MARKUP, "詳細モード用のファイル指定が消えている"
    assert 'id="mask-draw"' in without_templates, "筆で塗る導線が既定経路に無い"


def test_outpaint_has_no_per_side_controls():
    """backend は元画像を必ず中央へ置く。片側だけ広げられるように見せない。"""
    outpaint = (BACKEND / "outpaint.py").read_text(encoding="utf-8")
    assert "left = (width - source.width) // 2" in outpaint, "中央配置の前提が変わっている"
    for forbidden in ("data-side", "expand-left", "expand-right", "expand-top", "expand-bottom"):
        assert forbidden not in MARKUP and forbidden not in SCRIPT, f"非対称拡張の操作がある: {forbidden}"


def test_custom_size_is_reachable_without_advanced_mode():
    """カスタム寸法は上級者だけのものではない。既定の経路から入力できる。"""
    without_templates = re.sub(r"<template[\s\S]*?</template>", "", MARKUP)
    for name in ("size-custom", "custom-width", "custom-height", "custom-ratios"):
        assert f'id="{name}"' in without_templates, f"{name} が既定経路に無い"
    assert 'dataset.preset = "custom"' in SCRIPT, "カスタムの選択肢が無い"


def test_device_photos_are_resized_before_upload():
    """取り込みの画素数上限を超える端末写真をそのまま送らない。"""
    assert "fitToEnvelope" in SCRIPT and "needsResize" in SCRIPT
    assert "createImageBitmap" in SCRIPT and "toBlob" in SCRIPT


def test_typing_does_not_mark_the_workspace_as_unsaved():
    """保存の概念が無いのに離脱警告を出さない。"""
    assert 'addEventListener("input", () => setHostBusy(true))' not in SCRIPT


def test_every_failure_offers_one_exit():
    """失敗を見せるだけで終わらせない。すべての言い換えに出口を 1 つ持たせる。"""
    table = SCRIPT.split("const FAILURES = {", 1)[1].split("\n};", 1)[0]
    entries = re.findall(r"^  ([a-z][a-z0-9_]+): \{(.*?)\n  \},", table, re.MULTILINE | re.DOTALL)
    assert entries, "失敗表を読み取れなかった"
    for code, body in entries:
        assert "text:" in body, f"{code} に文言が無い"
        assert "exit:" in body and "action:" in body, f"{code} に出口が無い"
    assert "UNKNOWN_FAILURE" in SCRIPT, "未知の失敗にも出口が要る"


def test_library_cards_open_the_full_screen_viewer():
    """一覧のサムネイルは小さい。タップで原寸を見られる場所へ行く。"""
    assert "openViewer(item.asset_id, item, state.libraryItems)" in SCRIPT, \
        "一覧のタップがビューアへ行っていない"
    assert "#viewer[open] { display: grid" in STYLES, "ビューアが全画面になっていない"
    # 12 MiB を超える素材は運べないので、代わりに何を出すかを決めてある
    viewer = SCRIPT.split("async function openViewer(", 1)[1].split("\nasync function ", 1)[0]
    assert "assets.thumbnail" in viewer, "原寸を運べないときの代替が無い"
    assert "書き出して確認" in viewer, "代替表示の理由が書かれていない"


def test_viewer_supports_touch_zoom():
    assert "pointerdown" in SCRIPT and "viewerZoom" in SCRIPT
    assert "touch-action: none" in STYLES


# ── 到達性（G6 S4） ─────────────────────────────────────────────────────

# backend にあるのに UI から呼ばれていなかった method。到達経路を消させない。
REACHABLE_METHODS = (
    "models.custom.resolve",
    "models.custom.add",
    "profiles.create",
    "profiles.delete",
    "reference_collections.create",
    "jobs.create",
)


@pytest.mark.parametrize("method", REACHABLE_METHODS)
def test_the_workspace_can_reach_the_method(method: str):
    assert f'call("{method}"' in SCRIPT, f"{method} に到達する経路が無い"


def test_asset_pack_slots_come_from_the_profile_document_not_from_the_ui():
    """media 固有のスロット名を UI へ書き写さない。profile の宣言だけを根拠にする。"""
    for slot in ("open_center", "sleepy_half", "smile_open"):
        assert slot not in SCRIPT, f"{slot} が UI に直書きされている"
    assert "profile.eye_slots" in SCRIPT or "eye_slots" in SCRIPT


def test_the_model_in_use_is_always_visible_and_auto_stays_reachable():
    """使うモデルは常に見える 1 つの選択にする。おまかせは消さず先頭に残す。

    隠すと、何が使われるか分からないまま作ることになる。おまかせを消すのは
    機能削除なので、選択肢として残して段階開示は詳細モードの policy が担う。
    """
    row = MARKUP[MARKUP.index('id="model-choice-row"'):]
    assert "hidden" not in row[: row.index("</label>")], "モデルの選択を隠している"
    assert '<option value="">おまかせ' in MARKUP
    for policy in ("fast", "balanced", "quality", "low_vram", "manual"):
        assert f'<option value="{policy}">' in MARKUP, f"{policy} へ到達できない"


def test_a_manual_base_model_is_not_discarded_when_a_lora_is_selected():
    """LoRA を選んでも土台の指定を auto へ戻さない。黙って別のモデルにしない。"""
    body = SCRIPT[SCRIPT.index("function modelSelection()"):]
    body = body[: body.index("\nfunction ")]
    assert "selectedLoras()" not in body, "LoRA を理由に手動指定を捨てている"


def test_the_lora_strength_is_offered_only_where_the_lora_can_load():
    """載せられない LoRA につまみを出さない。強さは載せると決めてから。"""
    assert "function loraTargetFamily()" in SCRIPT
    assert "supports_lora" in SCRIPT
    assert "dropIncompatibleLoras" in SCRIPT
    body = SCRIPT[SCRIPT.index("function renderLoraPicker()"):]
    body = body[: body.index("\nfunction ")]
    assert body.index("box.checked") < body.index('weight.type = "range"'), (
        "選ぶ前から強さのつまみを出している"
    )


def test_an_automatic_model_choice_can_explain_itself():
    assert "modelRouteText" in SCRIPT
    assert "model_route" in SCRIPT


def test_a_custom_model_cannot_be_added_without_showing_the_licence_first():
    """取り込む前に必ず中身とライセンスを見せる。承諾は本文の提示が先。"""
    assert "custom-accept" in SCRIPT
    assert "license_acceptance" in SCRIPT
    resolve_at = SCRIPT.index('call("models.custom.resolve"')
    add_at = SCRIPT.index('call("models.custom.add"')
    assert resolve_at < add_at, "resolve より前に add を呼んでいる"


def test_a_custom_model_over_the_download_cap_is_not_offered_for_adding():
    assert "within_download_cap" in SCRIPT


# ── UX3: 設定の重複解消と書き出し導線 ───────────────────────────────────


@pytest.mark.parametrize(
    "control",
    ["advanced-domain", "advanced-scene", "advanced-pose",
     "advanced-composition", "advanced-camera", "advanced-variation"],
)
def test_the_advanced_pane_does_not_repeat_a_control_that_simple_mode_owns(control: str):
    """同じ設定が 2 箇所にあると、どちらが効いているのか利用者に分からない。"""
    assert f'id="{control}"' not in MARKUP


@pytest.mark.parametrize(
    "control",
    ["creative-scene", "creative-pose", "creative-composition",
     "creative-camera", "creative-variation", "domain-chips"],
)
def test_every_creative_control_still_exists_exactly_once(control: str):
    assert MARKUP.count(f'id="{control}"') == 1


@pytest.mark.parametrize(
    "detail",
    ["advanced-scene-details", "advanced-pose-details",
     "advanced-composition-details", "advanced-camera-details"],
)
def test_the_advanced_pane_adds_wording_rather_than_repeating_selects(detail: str):
    """詳細モードは同じ選択を繰り返さず、言葉での補足だけを足す。"""
    assert f'id="{detail}"' in MARKUP


def test_the_library_can_export_an_asset():
    """設計 §F4 保存A。host files bridge は実装済みなのに導線が無かった。"""
    assert 'call("assets.export"' in SCRIPT
    assert "host.files.export" in SCRIPT


def test_export_says_plainly_when_there_is_no_host():
    """単体表示でできないことを、できるように見せない。"""
    assert "単体表示では保存できません" in SCRIPT


def test_editing_the_prompt_discards_the_previous_understanding():
    """実機で、前回の解析が新しい指示の生成に渡っていた。

    state.directorPlan は送信時に director_plan としてそのまま渡るため、
    表示を消すだけでは足りず、状態ごと捨てる必要がある。
    """
    handler = SCRIPT[SCRIPT.index('byId("create-intent").addEventListener("input"'):][:400]

    assert "state.directorPlan = null" in handler
    assert "renderDirectorPlan(null)" in handler


def test_progress_does_not_invent_a_percentage_it_cannot_know():
    """backend は generating で 5% を出したあと次が postprocess の 65%。

    その間に GPU の生成全体が入るため、割合は本当に分からない。嘘の数字を
    動かす代わりに、動いていることと経過時間を見せる。
    """
    assert "INDETERMINATE_PHASES" in SCRIPT
    assert '"generating"' in SCRIPT
    assert "indeterminate" in STYLES


def test_returning_to_the_create_view_restores_the_running_progress():
    """別のタブへ移って戻ると進捗が消えていた。"""
    assert "restoreProgressView" in SCRIPT
    assert 'if (view === "create") restoreProgressView();' in SCRIPT


def test_the_shell_uses_drawn_icons_rather_than_bare_text_tabs():
    """opaque sandbox では外部資産を取りに行けないので SVG を直接埋め込む。"""
    assert MARKUP.count("<svg") >= 4
    assert "currentColor" in STYLES


def test_reduced_motion_users_do_not_get_a_looping_bar():
    assert "prefers-reduced-motion: reduce" in STYLES


def test_models_can_be_found_by_searching_rather_than_by_knowing_the_id():
    """repository ID の手入力だけでは、名前を既に知っている人にしか使えない。"""
    assert 'call("models.custom.search"' in SCRIPT
    for sort in ("downloads", "likes", "lastModified", "createdAt"):
        assert f'value="{sort}"' in MARKUP


def test_search_results_never_install_without_the_confirmation_step():
    """探せることと入れてよいことは別。表から直接は取り込ませない。"""
    handler = SCRIPT[SCRIPT.index('byId("catalog-results").addEventListener'):][:600]

    assert "resolveCustomModel(" in handler
    assert 'call("models.custom.add"' not in handler


def test_already_installed_models_are_marked_in_the_results():
    assert "already_added" in SCRIPT
    assert "導入済み" in SCRIPT


def test_the_table_keeps_numbers_comparable():
    """桁が揃わない表は比較に使えない。"""
    assert "tabular-nums" in STYLES
    assert "table.catalog" in STYLES


def test_installed_models_can_be_listed_as_a_comparable_table():
    """容量や状態を縦に揃えられないと、どれを消すかを決められない。"""
    assert "renderModelTable" in SCRIPT
    for column in ("状態", "採用", "容量", "VRAM", "ライセンス"):
        assert column in SCRIPT


def test_the_table_and_cards_offer_the_same_actions():
    """見た目を変えたら操作が減った、では使えない。"""
    start = SCRIPT.index("function modelActionCell")
    action = SCRIPT[start:SCRIPT.index("function modelTableRow", start)]

    for hook in ("installModel", "removeModel", "evaluateModel", "cancelModelOperation"):
        assert hook in action


def test_the_catalog_has_one_presentation_rather_than_two():
    """カードと表で出すタグが食い違っていた。表示が 2 つあると、片方だけ直る。"""
    assert 'id="model-catalog"' not in MARKUP
    assert "data-model-layout" not in MARKUP
    assert "renderModelTable" in SCRIPT


def test_the_mobile_table_needs_no_horizontal_scrolling():
    """横に伸ばすと、容量・VRAM・操作が画面の外へ出る。"""
    assert "table.catalog thead { display: none; }" in STYLES
    assert "content: attr(data-label)" in STYLES


def test_a_disabled_action_says_what_cannot_be_done():
    """「CLI で管理」は説明のない専門用語だった。"""
    assert "CLI で管理" not in SCRIPT
    assert "操作できません" in SCRIPT


def test_the_catalog_says_whether_a_model_runs_on_this_machine():
    """容量とライセンスが並んでいても「これは動くのか」は分からない。"""
    assert "modelRunnability" in SCRIPT
    for label in ("実行可能", "オフロード前提", "未計測", "起動不可"):
        assert label in SCRIPT


def test_an_unmeasured_model_is_never_called_runnable():
    """実測していないものを「動く」と言わない。"""
    fn = SCRIPT[SCRIPT.index("function modelRunnability"):][:900]

    assert 'return "unknown"' in fn
    assert "measured_vram_bytes" in fn


def test_models_can_be_ordered_by_whether_they_run_here():
    assert 'value="runnable"' in MARKUP
    assert "RUNNABILITY[modelRunnability(a)].rank" in SCRIPT


def test_a_started_download_has_somewhere_to_check_on_it():
    """数十 GB かかることがある。押したあとの行き先が要る。"""
    assert "renderModelDownloads" in SCRIPT
    assert "model-downloads-block" in SCRIPT


def test_finished_downloads_stay_visible_with_their_outcome():
    """何が落ちたのかを後から確かめられないと、やり直してよいのか分からない。"""
    start = SCRIPT.index("function modelDownloadRow")
    fn = SCRIPT[start:SCRIPT.index("function renderModelDownloads", start)]

    assert "error_code" in fn
    assert "完了" in fn and "失敗" in fn


def test_the_settings_view_no_longer_carries_static_diagnostics():
    """静的な説明文と診断表示は、毎回読む価値がないのに毎回場所を取っていた。"""
    assert 'id="advanced-host-integration"' not in MARKUP
    assert 'id="advanced-capability-list"' not in MARKUP
    assert 'data-adv-slot="settings"' not in MARKUP


def test_the_advanced_create_pane_is_still_template_mounted():
    """作る画面の詳細設定は残す。簡易モードへ漏れていないことを守る。"""
    without_templates = MARKUP[:MARKUP.index("<template")]

    assert 'data-adv-template="create"' in MARKUP
    assert 'id="advanced-format"' not in without_templates


def test_a_model_row_offers_download_and_delete():
    """一覧から導入と削除ができないと、結局 CLI へ戻ることになる。"""
    start = SCRIPT.index("function modelActionCell")
    action = SCRIPT[start:SCRIPT.index("function modelTableRow", start)]

    assert "installModel" in action and "ダウンロード" in action
    assert "removeModel" in action and "削除" in action


def test_searching_works_without_a_host():
    """配布元の検索はホストを必要としない。単体表示で死んでいた。"""
    assert "/workspace-api/models/search" in SCRIPT
    backend = (BACKEND / "app.py").read_text(encoding="utf-8")
    assert '"/workspace-api/models/search"' in backend


def test_the_mobile_catalog_uses_two_columns():
    # auto-fill に minmax(0, ...) を渡すと列が無限に増える（実測 13 列）。
    # 最小幅は実数で与える。
    assert "repeat(auto-fill, minmax(150px, 1fr))" in STYLES


def test_search_results_are_labelled_like_the_catalog():
    """積み上げたときに数字が何を指すのか分かること。検索結果だけ裸で並んでいた。"""
    row = SCRIPT[SCRIPT.index("function catalogRow"):SCRIPT.index("function renderCatalogResults")]

    for label in ("ダウンロード", "お気に入り", "更新", "ライセンス", "操作", "モデル"):
        assert f'"{label}"' in row


@pytest.mark.parametrize("control", ["advanced-width", "advanced-height"])
def test_size_is_set_in_one_place_only(control: str):
    """詳細側の幅高さが上のサイズ選択を上書きしており、どちらが効くのか
    分からなかった。サイズは「サイズ」に 1 組だけ置く。"""
    assert f'id="{control}"' not in MARKUP
    assert f'byId("{control}")' not in SCRIPT


def test_cards_in_the_same_row_share_a_height():
    """名前が 2 行になった側だけ伸びると、全体が段差だらけに見える。"""
    assert "align-items: stretch" in STYLES
    assert 'table.catalog td[data-label="操作"] { margin-top: auto; }' in STYLES


def test_the_name_area_reserves_room_so_the_facts_line_up():
    """値の行が揃うよう名前に場所を先に取る。取りすぎると card が伸びるだけ。"""
    name = STYLES[STYLES.index("table.catalog td.name > div {"):]
    reserved = re.search(r"min-height: ([0-9.]+)em", name[:name.index("}")])
    assert reserved, "名前の高さを確保していない"
    assert 2.0 <= float(reserved.group(1)) <= 2.6


def test_an_unavailable_action_is_not_rendered_as_a_button():
    """押せる見た目なのに反応しないと、何が足りないのかを推測させる。"""
    action = SCRIPT[SCRIPT.index("function modelActionCell"):SCRIPT.index("function modelTableRow")]

    assert "const unavailable = (text, why)" in action
    for reason in ("外部で管理", "容量超過", "共有の置き場", "使用中"):
        assert f'"{reason}"' in action


def test_the_search_action_says_where_it_leads():
    """「中身を見る」では何が起きるか分からない。"""
    assert "中身を見る" not in SCRIPT
    assert "追加する" in SCRIPT


def test_the_library_filter_row_stays_on_one_line():
    """札が折り返すと一覧が押し下がり、何枚あるのかが画面から消える。"""
    assert '<div class="view-head one-line">' in MARKUP
    assert ".view-head.one-line { flex-wrap: nowrap; }" in STYLES
    one_line = STYLES[STYLES.index(".view-head.one-line .chips {"):]
    one_line = one_line[:one_line.index("}")]
    assert "flex-wrap: nowrap" in one_line and "overflow-x: auto" in one_line


def test_selection_mode_is_visible_before_it_changes_what_a_tap_does():
    """選択中はカードの押し先が「開く」から「選ぶ」に変わる。同じ場所に
    別の意味を重ねる以上、見た目でも区別が要る。"""
    assert 'byId("library-grid").classList.toggle("selecting", active)' in SCRIPT
    assert ".grid.selecting .card[aria-selected=\"true\"]" in STYLES
    card = SCRIPT[SCRIPT.index("async function libraryCard"):]
    assert "if (state.librarySelecting) return toggleLibrarySelection(item.asset_id);" in card


def test_deleting_assets_asks_first_and_reports_what_survived():
    """まとめ削除は取り返しがつかない。全部消えたとも限らない。"""
    body = SCRIPT[SCRIPT.index("async function deleteSelectedAssets"):]
    body = body[:body.index("\n}")]
    assert "confirmModelAction" in body, "確認なしで消している"
    assert "元には戻せません" in body
    assert "asset_in_use" in body, "残った理由を伝えていない"
    assert "deleted_count" in body


def test_the_download_history_can_be_cleared_and_a_failure_retried():
    """落ちた行から一覧へ戻って同じモデルを探し直させない。"""
    assert 'id="model-downloads-clear"' in MARKUP
    clear = SCRIPT[SCRIPT.index("async function clearModelDownloadHistory"):]
    clear = clear[:clear.index("\n}")]
    assert '"models.operations.clear"' in clear
    assert "MODEL_TERMINAL.has(operation.state)" in clear, "進行中まで手元から消している"
    assert "retry.dataset.retryModelOperation = operation.model_id;" in SCRIPT
    assert "[data-retry-model-operation]" in SCRIPT, "再試行ボタンに受け手が無い"
    assert "[data-cancel-model-operation]" in SCRIPT


def test_the_viewer_can_step_through_the_list_it_was_opened_from():
    """拡大したまま隣と見比べたい。毎回一覧へ戻らせない。"""
    assert 'id="viewer-prev"' in MARKUP and 'id="viewer-next"' in MARKUP
    # 右下の「閉じる」の誤爆を避けるため、送りは左下、つまり行の先頭に置く
    bar = MARKUP[MARKUP.index('<div id="viewer-bar">'):MARKUP.index('id="viewer-close"')]
    assert bar.index('class="viewer-nav"') < bar.index('class="viewer-meta"')
    assert "order: -1;" in STYLES
    # 送り・操作・閉じるが 2 段になると画像の見える高さがその分削られる
    assert "flex-wrap: nowrap;" in STYLES[STYLES.index("#viewer-bar {"):STYLES.index("#viewer-caption")]
    step = SCRIPT[SCRIPT.index("function stepViewer"):SCRIPT.index("async function openViewer")]
    assert "keepList: true" in step, "送るたびに一覧を作り直している"
    viewer = SCRIPT[SCRIPT.index("async function openViewer("):]
    viewer = viewer[:viewer.index("\n/* 自動で選んだとき")]
    assert "const token = ++viewer.token;" in viewer, "連打で古い応答が後から描かれる"
    assert viewer.count("if (token !== viewer.token) return;") >= 3


def test_the_search_results_say_how_big_the_model_is():
    """何 GB 落ちてくるのかが分からないまま押させない。"""
    row = SCRIPT[SCRIPT.index("function catalogRow"):SCRIPT.index("function renderCatalogResults")]
    assert 'labelled(size, "容量")' in row
    assert "item.weight_bytes ? `約 ${formatBytes(item.weight_bytes)}` : \"不明\"" in row
    header = SCRIPT[SCRIPT.index("function renderCatalogResults"):]
    assert '["モデル", "容量", "DL"' in header, "見出しと列がずれている"


def test_the_view_head_actions_sit_at_the_right_edge():
    """左の文字数でボタンの位置が動くと、押す場所が毎回ずれる。"""
    assert ".view-head.one-line > :first-child { flex: 1 1 auto; min-width: 0; }" in STYLES


def test_an_image_that_cannot_be_shown_is_folded_away():
    """出せない絵の枠だけが正方形で残ると、一覧が読めない箱の列になる。"""
    card = SCRIPT[SCRIPT.index("async function libraryCard"):SCRIPT.index("/* ── 全画面ビューア")]
    assert 'image.addEventListener("error", () => { image.hidden = true; });' in card
    assert "catch { image.hidden = true; }" in card
    assert "表示できません" not in card, "壊れた枠に文字だけ残している"
    assert ".card img[hidden] { display: none !important; }" in STYLES


def test_the_close_button_is_not_painted_on_its_own_background():
    """button.icon は .primary より詳細度が高い。accent の背景が当たらず、
    濃い前景色が濃い背景に乗って閉じるボタンがほぼ見えなかった。"""
    rule = STYLES[STYLES.index("#viewer .viewer-actions button.icon.primary {"):]
    rule = rule[:rule.index("}")]
    assert "background: var(--accent) !important;" in rule
    assert "color: var(--accent-ink) !important;" in rule


def test_the_viewer_bar_cannot_push_its_actions_off_screen():
    """grid item の min-width は既定で auto。中身が縮まず操作が画面外へ出ていた。"""
    bar = STYLES[STYLES.index("#viewer-bar {"):]
    bar = bar[:bar.index("}")]
    assert "min-width: 0;" in bar and "overflow: hidden;" in bar


def test_a_gated_repository_says_so_before_the_button_is_pressed():
    """「条件を確認」では何を確認するのか分からない。同意が要ることを名前の側で言う。"""
    row = SCRIPT[SCRIPT.index("function catalogRow"):SCRIPT.index("function renderCatalogResults")]
    assert '"条件を確認"' not in row, "押した先が分からない語がボタンに残っている"
    assert 'button.textContent = "追加する";' in row, "gated だけ別の言葉になっている"
    assert 'gate.textContent = "要同意";' in row
    assert "配布元で利用条件に同意しないと取り込めません。" in row


def test_registering_characters_and_styles_is_its_own_section():
    """モデルの話と、覚えさせる素材の話は別。続けて並べると設定が 1 枚の帯になる。"""
    settings = MARKUP[MARKUP.index('id="model-downloads-block"'):]
    assert settings.index('class="settings-section"') < settings.index("キャラ・画風の登録")
    assert MARKUP.index('id="model-downloads-block"') < MARKUP.index("キャラ・画風の登録")
    assert ".settings-section {" in STYLES


def test_the_detail_dialog_translates_the_validation_record():
    """JSON の塊をそのまま出していた。読む人が知りたいのは通否だけである。"""
    assert "JSON.stringify(provenance.validation)" not in SCRIPT
    body = SCRIPT[SCRIPT.index("function validationList"):SCRIPT.index("async function openDetail")]
    # 記録は status: "passed" と passed: true の二通りある。どちらも読む
    assert 'record?.status ? record.status === "passed" : record?.passed === true' in body
    labels = SCRIPT[SCRIPT.index("const VALIDATOR_LABEL"):SCRIPT.index("function validationList")]
    for name in validator_names():
        assert f'"{name}"' in labels, f"{name} に日本語が無い"


def test_a_long_value_cannot_push_the_detail_dialog_off_screen():
    """grid track の既定 min-width は auto。model ID が track を押し広げていた。"""
    assert ".facts dt, .facts dd { min-width: 0; overflow-wrap: anywhere; }" in STYLES
    narrow = STYLES[STYLES.index("@media (max-width: 560px) {"):]
    assert ".facts div { grid-template-columns: 1fr;" in narrow[:narrow.index("\n}")]


def test_the_create_form_does_not_explain_itself_before_the_button():
    """押す前に所要時間を書いても、押すかどうかは変わらない。待っている最中に
    出しても、当たらない秒数は不安にしかならない。経過時間だけ出す。"""
    assert 'id="create-estimate"' not in MARKUP
    assert "2 回目以降は短くなります" not in SCRIPT
    assert "次の段階で入ります" not in SCRIPT
    assert "estimateSec" not in SCRIPT and "applyEstimate" not in SCRIPT
    assert "elapsedText(job)" in SCRIPT, "経過時間まで消している"


def test_the_search_controls_do_not_stack_four_deep():
    """検索・並び順・画風・ボタンを縦に積むと、結果が画面から押し出される。"""
    assert '<div class="form-row search">' in MARKUP
    form = MARKUP[MARKUP.index('<div class="form-row search">'):]
    form = form[:form.index("</div>")]
    assert 'id="catalog-search"' in form, "ボタンが格子の外にある"
    # 狭い画面で 1 列に落とすと 4 段に戻る
    assert ".form-row:not(.search) { grid-template-columns: 1fr; }" in STYLES


def test_the_download_row_does_not_say_download_twice():
    """「ダウンロード · ダウンロードしています」と二重に出ていた。"""
    row = SCRIPT[SCRIPT.index("function modelDownloadRow"):SCRIPT.index("async function clearModelDownloadHistory")]
    assert 'stateText.startsWith(actionText) ? "" : actionText' in row


def test_the_validation_marks_do_not_reuse_the_checkbox_class():
    """.check は既にチェックボックス付きラベルで使われている。"""
    assert '"checkmark ok"' in SCRIPT and '"checkmark bad"' in SCRIPT
    assert ".checkmark.ok { color: var(--accent); }" in STYLES


def test_progress_is_recovered_from_the_job_that_is_still_running():
    """画面を離れると state.activeJob は消えるが、job はサーバ側で走り続ける。
    「今どれを見ているか」を覚えていないだけで、進捗そのものは失われていない。"""
    body = SCRIPT[SCRIPT.index("function restoreProgressView"):]
    body = body[:body.index("\n}")]
    assert "!TERMINAL.has(item.status)" in body, "走っている job を拾っていない"
    assert 'call("jobs.watch"' in body, "拾い直した job に通知を張っていない"
    # boot でも view に依らず拾う。ミニ進捗は create 以外でも出る。
    boot = SCRIPT[SCRIPT.index('activate(state.preferences.last_view'):]
    assert "restoreProgressView();" in boot[:400], "起動時に拾い直していない"


def test_a_running_job_can_be_reattached_from_the_activity_tab():
    """走っているものが複数あるとき、どれを見るかは利用者が決める。自動で
    拾うと、見たかった方ではない実行の進捗が出る。"""
    body = SCRIPT[SCRIPT.index("function attachToJob"):]
    body = body[:body.index("\n}")]
    # 進捗だけ戻しても、何を頼んだのかが画面から消えたままになる
    assert 'byId("create-intent")' in body, "指示を復旧していない"
    assert 'call("jobs.watch"' in body and 'activate("create")' in body
    assert "TERMINAL.has(job.status)" in body, "終わった job にも繋いでしまう"

    row = SCRIPT[SCRIPT.index("function activityRow"):]
    row = row[:row.index("\nfunction ", 10)]
    assert "attach.dataset.attachJob = job.id;" in row
    assert "job.id !== state.activeJob" in row, "今見ている実行にも接続を出している"
    assert "[data-attach-job]" in SCRIPT, "接続ボタンに受け手が無い"


def test_progress_is_adopted_only_when_there_is_no_choice_to_make():
    """迷いようがあるときは選ばない。複数走っているなら利用者に選ばせる。"""
    body = SCRIPT[SCRIPT.index("function restoreProgressView"):]
    body = body[:body.index("\n}")]
    assert "running.length !== 1" in body


def test_the_activity_tab_can_clear_its_history():
    """終わった実行が積み上がると、走っているものが見えなくなる。"""
    assert 'id="activity-clear"' in MARKUP
    handler = SCRIPT[SCRIPT.index('byId("activity-clear").addEventListener'):]
    handler = handler[:handler.index("\n});")]
    assert "confirmModelAction" in handler, "確認なしで消している"
    assert '"jobs.clear"' in handler
    # 何が残るのかを言う。素材まで消えると読まれると押せない。
    assert "作った素材とその来歴は残ります" in handler
    render = SCRIPT[SCRIPT.index("function renderActivity"):]
    render = render[:render.index("\n}")]
    assert 'byId("activity-clear").hidden = finished.length === 0;' in render


def test_a_dead_socket_is_replaced_rather_than_reused():
    """携帯では頁を離れるだけで socket は閉じられ、戻った頁が bfcache から
    復元されると JS の状態だけが生き残る。解決済みの promise を握ったままだと、
    閉じた socket へ送り続けて画面が空のままになる（再読込するまで直らない）。"""
    connect = SCRIPT[SCRIPT.index("function connectSocket"):]
    connect = connect[:connect.index("\n/* 何 GB")]
    assert "if (state.socketReady && socketOpen()) return state.socketReady;" in connect
    assert "dropSocket();" in connect, "閉じたときに握ったままになっている"

    caller = SCRIPT[SCRIPT.index("async function call(method"):]
    caller = caller[:caller.index("\n}")]
    assert "if (!socketOpen())" in caller, "送る前に生きているか見ていない"
    # 閉じた socket への send は例外にならず、応答が来ないだけになる
    assert "catch (error)" in caller


def test_the_workspace_recovers_when_it_comes_back():
    resume = SCRIPT[SCRIPT.index("async function resumeAfterInterruption"):]
    resume = resume[:resume.index("\n}")]
    # 生きているなら何もしない。常時 polling にはしない。
    assert "if (socketOpen()) return;" in resume
    assert "refreshSession(" in resume
    assert 'document.addEventListener("visibilitychange"' in SCRIPT
    assert 'window.addEventListener("pageshow"' in SCRIPT


def test_boot_retries_instead_of_leaving_an_empty_screen():
    """最初の接続が失敗しただけで画面が永久に空のままになっていた。"""
    boot = SCRIPT[SCRIPT.index("  void (async () => {"):]
    boot = boot[:boot.index("  })();")]
    assert "attempt < 5" in boot
    assert "500 * 2 ** attempt" in boot, "落ちている相手を等間隔で叩き続けている"


def test_being_listed_is_not_reported_as_being_installed():
    """一覧に登録しただけの repository が「追加済み」と出て、ダウンロードが
    始まらない理由が画面から読み取れなかった。"""
    row = SCRIPT[SCRIPT.index("function catalogRow"):SCRIPT.index("function renderCatalogPage")]
    assert '"導入済み"' in row, "落とし終えたものが分からない"
    # 登録しただけでは何も落ちてこない。次にできることを出す。
    assert 'download.dataset.installRepo = item.repo_id;' in row
    assert 'item.catalog_state === "installed"' in row
    backend = (BACKEND / "app.py").read_text(encoding="utf-8")
    assert '"catalog_state"' in backend, "backend が 2 つの状態を区別していない"


def test_the_import_panel_can_be_dismissed():
    """中身を見た後に検索へ戻れないと、確認だけして止める道が無い。"""
    assert 'cancel.id = "custom-cancel";' in SCRIPT
    assert '#custom-cancel' in SCRIPT
    assert ".split-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }" in STYLES


def test_sections_are_separated_from_what_precedes_them():
    """詰まって見えていたのは行間ではなく、節の区切りが無かったため。
    見出しが前の塊に貼り付くと、どこで話が変わったのか読み取れない。"""
    assert ".section-label:not(:first-child) { margin-top: 22px; }" in STYLES
    # 送りは前後どちらの塊にも属さない
    pager = STYLES[STYLES.index(".pager {"):]
    pager = pager[:pager.index("}")]
    assert "margin: 14px 0 4px;" in pager
    assert "justify-content: center;" in pager
    # ダウンロードの状況は独立した塊
    block = STYLES[STYLES.index("#model-downloads-block {"):]
    block = block[:block.index("}")]
    assert "border-top:" in block and "margin-top:" in block


def test_the_ui_reads_the_settings_report_the_backend_emits():
    """自動で決められなかった項目の名前が片方だけ変わると、画面から警告が
    黙って消える。消えたことは誰も気づけない。"""
    defaults = (BACKEND / "models" / "generation_defaults.py").read_text(encoding="utf-8")
    app = (BACKEND / "app.py").read_text(encoding="utf-8")

    for key in ("needs_check", "settled", "presets"):
        assert key in defaults or key in app, f"backend が {key} を出していない"
        assert key in SCRIPT, f"UI が {key} を読んでいない"
    # 判断は判定した側が持つ。UI が steps_source を見て自分で文面を組み立てると、
    # 同じ判断が 2 か所に分かれて片方だけ直る。
    assert "steps_source" in defaults
    assert "steps_source" not in SCRIPT, "UI が判定をやり直している"
    # 各項目は理由と対処を持って初めて役に立つ。値だけ出しても何もできない。
    for field in ("reason", "action"):
        assert f'entry.{field}' in SCRIPT, f"UI が {field} を表示していない"


def test_the_advanced_settings_do_not_leak_into_simple_mode():
    """簡単モードで歩数を見せない。触るべき人にだけ見せる。"""
    assert 'data-adv-template="create"' in MARKUP
    settings = MARKUP.index('id="model-settings"')
    template = MARKUP.index('data-adv-template="create"')
    closing = MARKUP.index("</template>", template)
    assert template < settings < closing, "model-settings が詳細モードの外にある"


def test_the_preset_sets_guidance_together_with_steps():
    """歩数だけ合わせてガイダンスを据え置くと、4 歩で 7.0 のような組み合わせに
    なり絵が焼ける。"""
    assert "chip.dataset.guidance" in SCRIPT
    assert "chip.dataset.steps" in SCRIPT



def test_the_catalog_offers_both_distribution_sites():
    for identifier in CATALOG_IDS:
        assert f'id="{identifier}"' in MARKUP, identifier
    assert 'data-source="civitai"' in MARKUP
    assert 'data-source="huggingface"' in MARKUP


def test_civitai_is_the_default_distribution_site():
    civitai = MARKUP.index('data-source="civitai"')
    assert 'aria-checked="true"' in MARKUP[civitai:civitai + 120]
    defaults = (BACKEND / "custom_models.py").read_text(encoding="utf-8")
    assert 'DEFAULT_MODEL_SOURCE = "civitai"' in defaults


def test_the_search_says_which_site_it_is_asking():
    """配布元を送らないと、既定の側だけを検索し続ける。"""
    assert "source: catalogSource()" in SCRIPT


def test_a_filter_that_the_site_does_not_have_is_hidden():
    """効かない絞り込みを出すと、絞ったつもりの結果を見ることになる。
    Civitai の検索は画風タグを持たない。"""
    assert "styles: false" in SCRIPT



def test_the_catalog_can_look_for_loras():
    assert 'data-model-type="lora"' in MARKUP
    assert 'data-model-type="checkpoint"' in MARKUP
    assert "model_type: catalogType()" in SCRIPT


def test_a_lora_is_never_offered_as_a_model_to_generate_with():
    """LoRA は単体では絵を作れない。選択肢に混ぜると、選んでから断られる。"""
    for line in SCRIPT.splitlines():
        if "model.installed && model.healthy" in line and "kind" not in line:
            following = SCRIPT[SCRIPT.index(line):SCRIPT.index(line) + 200]
            assert 'kind !== "lora"' in following, line


def test_the_base_model_is_reported_before_a_lora_is_taken():
    """容量とライセンスは見せるが、土台を別操作で選ばせない。"""
    assert "必要な土台も自動でダウンロードします" in SCRIPT
    assert "customResolution.dependency" in SCRIPT
    assert "lora-base-together" not in SCRIPT
    backend = (BACKEND / "app.py").read_text(encoding="utf-8")
    assert 'result["dependency"]' in backend


def test_the_base_and_lora_are_one_confirmed_download_request():
    """LoRA の後に土台を別追加する操作を残さない。"""
    add = SCRIPT[SCRIPT.index("async function addCustomModel"):]
    assert 'call("models.custom.add"' in add
    assert "license_acceptance: customResolution.dependency.license" in add
    assert add.count('call("models.custom.add"') == 1


def test_lora_selection_owns_automatic_base_routing():
    """土台を指定していないときは、LoRA の系統だけで backend に選ばせる。

    UI 側で checkpoint を推測しない。指定したときはその指定を送る（別テスト）。
    """
    selection = SCRIPT[SCRIPT.index("function modelSelection()"):]
    selection = selection[: selection.index("\nfunction ")]
    assert 'if (state.modelChoice === "manual")' in selection
    assert "model_id: modelId" in selection
    picker = SCRIPT[SCRIPT.index("function loraTargetFamily()"):]
    picker = picker[: picker.index("\nfunction ")]
    assert "chosenBaseModel()" in picker
    assert "state.selectedLoras" in picker


def test_the_trigger_words_are_shown_where_the_lora_is_chosen():
    """起動語を入れない LoRA は何も起こさない。"""
    assert "trigger_words" in SCRIPT
    assert "自動で足します" in SCRIPT


def test_video_can_be_set_up_without_leaving_the_simple_screen():
    """モデル・画質・長さは、簡易でも詳細でも触れる。

    実機で動画は作れたが、設定が 1 つも無かった。作れるだけで、どう作るかを
    選べない状態だった。段階開示は「簡単にするために削る」ことではない。
    """
    assert 'id="video-settings"' in MARKUP
    for element in (
        'id="video-quality"', 'id="video-length-slider"', 'id="video-cost"',
    ):
        assert element in MARKUP, element
    # 長さは決め打ちの数個ではなく連続で選ばせる。ただしモデルが取る値は
    # 飛び飛びなので、刻みはモデルの実測プロファイルから採る。
    assert "function videoFrameChoices()" in SCRIPT
    assert "profile.frame_step" in SCRIPT
    # 画質も同じ。共通の決め打ちを持つと、どれかのモデルで作れない値が出る。
    assert "function videoSizes()" in SCRIPT
    assert "function videoProfile()" in SCRIPT
    assert "chosen.video" in SCRIPT
    # モデルを選び直したら選択肢を作り直す。前のモデルの寸法を残さない。
    assert "state.videoQuality = null;" in SCRIPT
    # 使うモデルは媒体を問わず出す。画像専用にすると動画で選べなくなる。
    choice = MARKUP[MARKUP.index('id="model-choice"'):MARKUP.index('id="model-choice-note"')]
    assert "data-image-create" not in choice
    # 一覧は作るものに合わせる。画像の一覧に動画モデルを混ぜない。
    assert 'const wanted = state.createMedia === "video" ? "video" : "image";' in SCRIPT

    # 詳細は簡易の上に足す。簡易で選んだものを詳細が奪わない。
    template = MARKUP[MARKUP.index('data-adv-template="video"'):MARKUP.index('data-adv-template="mask"')]
    for element in (
        'id="advanced-video-steps"', 'id="advanced-video-guidance"',
        'id="advanced-video-frames"', 'id="advanced-video-fps"',
        'id="advanced-video-negative"',
    ):
        assert element in template, element


def test_the_video_cost_is_shown_before_it_is_spent():
    """13 分かかるものを、押してから知るのでは遅い。

    面積は注意機構に効くので二乗、長さはフレーム数に比例する。実測
    （512x320 33 フレーム 30 歩で 144.6 秒）からの外挿であることを明示する。
    """
    assert "function videoCostSeconds()" in SCRIPT
    cost = SCRIPT[SCRIPT.index("function videoCostSeconds()"):SCRIPT.index("function renderVideoSettings()")]
    assert "area * area" in cost, "面積は二乗で効く"
    assert "videoFrames() / base.frames" in cost
    # 目安はモデルごとの実測から出す。共通の 1 つに丸めない。
    assert "Number(chosen?.measured_runtime_sec)" in SCRIPT
    # 初回はモデルの読み込みが乗る。触れずに済ませない。
    assert "初回はモデルの読み込み" in SCRIPT
