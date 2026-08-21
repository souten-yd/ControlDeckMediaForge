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
    "attach-image", "source-file", "edit-actions", "guarantee-badge",
    "size-presets", "count-chips",
    "stage", "stage-progress", "stage-result", "candidate-strip", "recent-strip",
    "mini-progress", "library-grid", "library-kinds", "activity-list",
    "capability-list", "detail-dialog",
)

ADVANCED_IDS = (
    "advanced-create", "advanced-width", "advanced-height", "advanced-format",
    "advanced-count", "advanced-policy", "advanced-model", "advanced-semantic",
    "advanced-attempts", "advanced-settings", "advanced-models",
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
    assert 'data-adv-slot="create"' in MARKUP
    assert 'data-adv-slot="settings"' in MARKUP
    assert 'data-adv-template="create"' in MARKUP
    assert 'data-adv-template="settings"' in MARKUP


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
)


def backend_error_codes() -> set[str]:
    codes: set[str] = set()
    for path in BACKEND.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for pattern in CODE_PATTERNS:
            codes.update(re.findall(pattern, source, re.MULTILINE))
    return codes


def test_failure_sentences_only_name_real_backend_codes():
    table = SCRIPT.split("function failureText(", 1)[1].split("}", 2)[0]
    named = set(re.findall(r"^\s{4}([a-z][a-z0-9_]+):", table, re.MULTILINE))
    assert named, "失敗の言い換え表が読み取れなかった"
    unknown = named - backend_error_codes()
    assert not unknown, f"backend に存在しない error code を UI が説明している: {sorted(unknown)}"


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
    assert ADDON["version"] == "0.2.0", "contribution を変えたので version を上げる"


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
