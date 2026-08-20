from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def setup_snapshot() -> dict[str, Any] | None:
    """Read the cheap snapshot produced by mf.sh; never probe GPU/disk here."""
    configured = os.environ.get("MEDIA_FORGE_ENV_STATUS_FILE")
    if not configured:
        return None
    path = Path(configured)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "status": "setup_required",
            "setup": [
                {
                    "id": "environment_status",
                    "label": "Environment status",
                    "state": "error",
                    "message": "Environment snapshot is unavailable; run ./mf.sh doctor",
                    "action": {"kind": "open_route", "route": "/x/media-forge/workspace/settings"},
                }
            ],
        }
    if not isinstance(payload, dict) or not isinstance(payload.get("setup"), list):
        return {
            "status": "setup_required",
            "setup": [
                {
                    "id": "environment_status",
                    "label": "Environment status",
                    "state": "error",
                    "message": "Environment snapshot is invalid; run ./mf.sh doctor",
                    "action": {"kind": "open_route", "route": "/x/media-forge/workspace/settings"},
                }
            ],
        }
    return payload
