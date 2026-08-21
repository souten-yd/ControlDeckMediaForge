from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    worker_timeout_sec: float = 30.0
    host_token_key_file: Path | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        configured = os.environ.get("MEDIA_FORGE_DATA_DIR")
        data_dir = Path(configured) if configured else Path.home() / ".local/share/control-deck-media-forge"
        timeout = float(os.environ.get("MEDIA_FORGE_WORKER_TIMEOUT_SEC", "30"))
        key_file = os.environ.get("MEDIA_FORGE_CONTROLDECK_TOKEN_KEY_FILE")
        return cls(
            data_dir=data_dir.resolve(),
            worker_timeout_sec=timeout,
            host_token_key_file=Path(key_file).resolve() if key_file else None,
        )
