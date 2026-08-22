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
}

DEFAULTS: dict[str, Any] = {
    "mode": "simple",
    "last_custom_width": 0,
    "last_custom_height": 0,
    "last_preset": "square",
    "last_count": 1,
    "last_view": "create",
    "library_kind": "all",
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
        result[key] = value
    return result


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
