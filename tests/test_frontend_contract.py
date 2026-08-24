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
    "create-error", "create-estimate",
    "mask-input", "mask-draw", "mask-preview", "mask-state",
    "mask-dialog", "mask-canvas", "mask-brush", "mask-eraser", "mask-undo", "mask-clear",
    "mask-apply", "mask-cancel",
    "outpaint-input", "outpaint-ratios", "outpaint-scales", "outpaint-preview", "outpaint-note",
    "stage", "stage-progress", "stage-result", "candidate-strip", "recent-strip",
    "result-evaluate", "result-evaluation",
    "mini-progress", "library-grid", "library-kinds", "activity-list",
    "detail-dialog",
    "model-storage", "model-filters", "model-table", "model-empty", "model-error",
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
)


def test_the_frame_never_touches_browser_storage():
    for forbidden in ("localStorage", "sessionStorage", "document.cookie", "indexedDB"):
        assert forbidden not in SCRIPT, f"opaque sandbox では {forbidden} を使えない"
        assert forbidden not in MARKUP


def test_dom_contract_ids_exist():
    for name in DOM_IDS:
        assert f'id="{name}"' in MARKUP, f"DOM 契約の id が無い: {name}"


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
    assert 'model.ownership === "managed"' in SCRIPT
    assert '"外部ランタイムで導入"' in SCRIPT
    assert 'experimental: "実験的・未実測"' in SCRIPT
    assert "model.license_acceptance_id" in SCRIPT
    assert "window.confirm" not in SCRIPT
    assert 'id="model-confirm-dialog"' in MARKUP
    assert "confirmModelAction" in SCRIPT
    assert "license_acceptance: licenseAcceptance" in SCRIPT
    assert "MAX_MANAGED_MODEL_DOWNLOAD_BYTES = 32_000_000_000" in SCRIPT
    assert 'action.textContent = "32GB上限対象"' in SCRIPT
    assert 'evaluate.textContent = "実機で評価"' in SCRIPT
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
OPERATIONS = {"image.generate", "image.edit", "media.inspect", "asset.pack"}


def test_every_capability_the_ui_reads_is_emitted_by_the_backend():
    emitted = capability_names()
    assert emitted, "capability document を読み取れなかった"
    used = set(re.findall(r'"((?:image|video|3d)\.[a-z_0-9]+)"', SCRIPT)) - OPERATIONS
    assert used, "UI が capability 名を参照していない"
    assert used <= emitted, f"backend が出さない capability を UI が参照している: {sorted(used - emitted)}"


def test_operations_the_ui_submits_are_valid_schema_values():
    schema = json.loads((ROOT / "schemas" / "job-request.json").read_text(encoding="utf-8"))
    allowed = set(schema["properties"]["operation"]["enum"])
    used = set(re.findall(r'"((?:image|video|3d|media|asset)\.[a-z_0-9]+)"', SCRIPT)) & OPERATIONS
    assert used, "UI が operation を指定していない"
    assert used <= allowed


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


@pytest.mark.parametrize("kind", ["all", "generated", "edited", "imported"])
def test_library_kinds_match_the_backend_projection(kind: str):
    from mediaforge import library

    assert kind in library.KINDS
    assert f'id: "{kind}"' in SCRIPT


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
    assert "openViewer(item.asset_id, item)" in SCRIPT, "一覧のタップがビューアへ行っていない"
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


def test_model_choice_is_two_stage_and_reaches_every_policy_in_advanced_mode():
    """段階開示で作り、機能削除で作らない。詳細から全 policy へ到達できること。"""
    assert 'data-model-choice="auto"' in MARKUP
    assert 'data-model-choice="manual"' in MARKUP
    for policy in ("fast", "balanced", "quality", "low_vram", "manual"):
        assert f'<option value="{policy}">' in MARKUP, f"{policy} へ到達できない"


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
    assert "追加済み" in SCRIPT


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
    action = SCRIPT[SCRIPT.index("function modelActionCell"):][:1800]

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
    action = SCRIPT[SCRIPT.index("function modelActionCell"):][:1800]

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
    assert "min-height: 2.5em" in STYLES
