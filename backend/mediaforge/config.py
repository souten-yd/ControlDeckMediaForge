from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _control_deck_origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("ControlDeck URL must be an HTTP(S) origin")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("ControlDeck URL must not contain a path, query, or fragment")
    if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("plain HTTP ControlDeck URL must be loopback")
    return value.rstrip("/")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    worker_timeout_sec: float = 30.0
    control_deck_url: str = "http://127.0.0.1:8765"
    host_request_timeout_sec: float = 10.0
    host_lease_renew_sec: float = 10.0
    model_manifest: Path = REPOSITORY_ROOT / "worker_packs/image/models.json"
    hf_home: Path = Path.home() / ".cache/huggingface"
    image_runtime_python: Path = REPOSITORY_ROOT / "runtimes/rocm-torch/.venv/bin/python"

    def __post_init__(self) -> None:
        object.__setattr__(self, "control_deck_url", _control_deck_origin(self.control_deck_url))
        object.__setattr__(self, "model_manifest", self.model_manifest.resolve())
        object.__setattr__(self, "hf_home", self.hf_home.resolve())
        object.__setattr__(self, "image_runtime_python", self.image_runtime_python.resolve())
        if self.worker_timeout_sec <= 0 or self.host_request_timeout_sec <= 0 or self.host_lease_renew_sec <= 0:
            raise ValueError("worker and host request timeouts must be positive")

    @classmethod
    def from_env(cls) -> "Settings":
        configured = os.environ.get("MEDIA_FORGE_DATA_DIR")
        data_dir = Path(configured) if configured else Path.home() / ".local/share/control-deck-media-forge"
        timeout = float(os.environ.get("MEDIA_FORGE_WORKER_TIMEOUT_SEC", "30"))
        return cls(
            data_dir=data_dir.resolve(),
            worker_timeout_sec=timeout,
            control_deck_url=os.environ.get("MEDIA_FORGE_CONTROLDECK_URL", "http://127.0.0.1:8765"),
            host_request_timeout_sec=float(os.environ.get("MEDIA_FORGE_CONTROLDECK_TIMEOUT_SEC", "10")),
            host_lease_renew_sec=float(os.environ.get("MEDIA_FORGE_CONTROLDECK_RENEW_SEC", "10")),
            model_manifest=Path(
                os.environ.get("MEDIA_FORGE_MODEL_MANIFEST", REPOSITORY_ROOT / "worker_packs/image/models.json")
            ),
            hf_home=Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface")),
            image_runtime_python=Path(
                os.environ.get(
                    "MEDIA_FORGE_IMAGE_RUNTIME_PYTHON",
                    REPOSITORY_ROOT / "runtimes/rocm-torch/.venv/bin/python",
                )
            ),
        )
