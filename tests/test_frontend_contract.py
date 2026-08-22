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
    "create-error", "create-estimate",
    "mask-input", "mask-draw", "mask-preview", "mask-state",
    "mask-dialog", "mask-canvas", "mask-brush", "mask-eraser", "mask-undo", "mask-clear",
    "mask-apply", "mask-cancel",
    "outpaint-input", "outpaint-ratios", "outpaint-scales", "outpaint-preview", "outpaint-note",
    "stage", "stage-progress", "stage-result", "candidate-strip", "recent-strip",
    "mini-progress", "library-grid", "library-kinds", "activity-list",
    "capability-list", "detail-dialog",
    "model-storage", "model-filters", "model-catalog", "model-empty", "model-error",
    "model-mini-progress", "model-mini-phase", "model-mini-bar", "model-mini-cancel",
    "model-remove-dialog", "model-remove-summary", "model-remove-detail",
    "model-remove-cancel", "model-remove-confirm",
    "viewer", "viewer-stage", "viewer-image", "viewer-caption",
    "viewer-detail", "viewer-edit", "viewer-close",
)

ADVANCED_IDS = (
    "advanced-create", "advanced-width", "advanced-height", "advanced-format",
    "advanced-count", "advanced-policy", "advanced-model", "advanced-semantic",
    "advanced-attempts", "advanced-settings", "advanced-models", "advanced-mask-file",
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


def test_advanced_controls_live_only_inside_templates():
    """詳細モードの要素は hidden ではなく template に置く。

    シンプルでは DOM に存在しないことが要件（設計 §3.1）なので、
    静的には「template の外に advanced-* が無い」で担保する。
    """
    without_templates = re.sub(r"<template[\s\S]*?</template>", "", MARKUP)
    for name in ADVANCED_IDS:
        assert f'id="{name}"' not in without_templates, f"{name} が template の外にある"
    for name in ("advanced-create", "advanced-settings"):
        assert f'id="{name}"' in MARKUP, f"{name} の template が無い"
    for slot in ("create", "settings", "mask"):
        assert f'data-adv-slot="{slot}"' in MARKUP
        assert f'data-adv-template="{slot}"' in MARKUP


def test_model_management_actions_are_simple_but_technical_details_are_advanced():
    without_templates = re.sub(r"<template[\s\S]*?</template>", "", MARKUP)
    for name in ("model-filters", "model-catalog", "model-storage"):
        assert f'id="{name}"' in without_templates
    assert 'id="advanced-models"' not in without_templates
    assert "models.install" in SCRIPT and "models.remove" in SCRIPT
    assert "models.operations.watch" in SCRIPT and "model.operation.changed" in SCRIPT
    assert 'data-model-filter="installed"' in MARKUP
    assert 'data-model-filter="recommended"' in MARKUP
    assert 'data-model-filter="all"' in MARKUP
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
    assert 'if (creativeActive(spec))' in SCRIPT
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
    document = source.split("async def capability_document()", 1)[1].split("@app.get", 1)[0]
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
    r'raise \w+\(\s*\n?\s*"([a-z][a-z0-9_]+)"',
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
