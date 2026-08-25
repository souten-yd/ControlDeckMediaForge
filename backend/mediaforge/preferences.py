"""Workspace preferences.

The embedded view runs in an opaque sandbox, so it has no localStorage and no
cookie. Anything the workspace must remember across reloads is stored here,
keyed by the ControlDeck identity subject. Only presentation choices belong
here: no secrets, no paths, no host identifiers.
"""

from __future__ import annotations

from typing import Any

MAX_PAYLOAD_BYTES = 4 * 1024
STANDALONE_SUBJECT = "local"

ALLOWED: dict[str, tuple[type, tuple[Any, ...] | None]] = {
    "mode": (str, ("simple", "advanced")),
    "last_preset": (str, ("square", "landscape", "portrait", "wide", "tall", "cinema", "custom")),
    "last_count": (int, (1, 2, 3, 4, 5, 6, 7, 8)),
    "last_custom_width": (int, None),
    "last_custom_height": (int, None),
    "last_view": (str, ("create", "library", "activity", "settings")),
    "library_kind": (str, ("all", "generated", "edited", "imported")),
    "director_mode": (str, ("original", "refine", "art_direct")),
    "model_layout": (str, ("table", "cards")),
    # どの配布元を検索するか。既定は Civitai。
    "model_source": (str, ("civitai", "huggingface")),
    # 作りかけの設定。画面を離れても、次に開いたときに続きから始められる。
    # 中身は creative_spec の一部（domain / scene / 構図など）で、どれも
    # templates.json の id なので、鍵ごとの列挙ではなく形と大きさで縛る。
    "last_creative_spec": (dict, None),
}

# 自由形式の設定は、鍵の数と値の長さで縛る。列挙できないものを無制限に
# 受けると、preferences が任意の入れ物になる。
MAX_SPEC_KEYS = 24
MAX_SPEC_VALUE_LENGTH = 128

DEFAULTS: dict[str, Any] = {
    "mode": "simple",
    "last_custom_width": 0,
    "last_custom_height": 0,
    "last_preset": "square",
    "last_count": 1,
    "last_view": "create",
    "library_kind": "all",
    "director_mode": "refine",
    # 見比べる用途が多いので既定は表。カードは 1 件ずつの説明向け。
    "model_layout": "table",
    "model_source": "civitai",
    "last_creative_spec": {},
}


class PreferenceError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def validate(values: object) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise PreferenceError("invalid_preferences", "preferences must be an object")
    result: dict[str, Any] = {}
    for key, value in values.items():
        rule = ALLOWED.get(key) if isinstance(key, str) else None
        if rule is None:
            raise PreferenceError("invalid_preference_key", f"unsupported preference: {key!r}"[:120])
        expected, choices = rule
        if isinstance(value, bool) or not isinstance(value, expected):
            raise PreferenceError("invalid_preference_value", f"preference {key} has an unsupported type")
        if choices is not None and value not in choices:
            raise PreferenceError("invalid_preference_value", f"preference {key} has an unsupported value")
        if expected is dict:
            value = _bounded_spec(key, value)
        result[key] = value
    return result


def _bounded_spec(key: str, value: dict[str, Any]) -> dict[str, Any]:
    """Accept a small, flat map of short strings and nothing else.

    The values are template identifiers, so there is no reason for nesting or
    for long strings. Without a bound here, preferences becomes a place to store
    arbitrary data under a name that sounds harmless.
    """
    if len(value) > MAX_SPEC_KEYS:
        raise PreferenceError("invalid_preference_value", f"preference {key} has too many entries")
    bounded: dict[str, Any] = {}
    for name, item in value.items():
        if not isinstance(name, str) or len(name) > 64:
            raise PreferenceError("invalid_preference_value", f"preference {key} has an unsupported entry")
        if isinstance(item, bool) or not isinstance(item, (str, int)):
            raise PreferenceError("invalid_preference_value", f"preference {key} has an unsupported entry")
        if isinstance(item, str) and len(item) > MAX_SPEC_VALUE_LENGTH:
            raise PreferenceError("invalid_preference_value", f"preference {key} has an oversized entry")
        bounded[name] = item
    return bounded


def merged(stored: dict[str, Any]) -> dict[str, Any]:
    """Unknown keys from an older build never reach the workspace."""
    values = dict(DEFAULTS)
    for key, value in stored.items():
        if key in ALLOWED:
            values[key] = value
    return values


def subject_of(identity: object) -> str:
    value = getattr(identity, "subject", None)
    return value if isinstance(value, str) and value else STANDALONE_SUBJECT
