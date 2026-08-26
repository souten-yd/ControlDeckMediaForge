from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


REPOSITORY_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


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
    blender_timeout_sec: float = 180.0
    control_deck_url: str = "http://127.0.0.1:8765"
    host_request_timeout_sec: float = 10.0
    host_lease_renew_sec: float = 10.0
    model_manifest: Path = REPOSITORY_ROOT / "worker_packs/image/models.json"
    model_catalog_manifest: Path | None = None
    model_store_root: Path | None = None
    creative_template_manifest: Path = REPOSITORY_ROOT / "creative/templates.json"
    creative_layout_manifest: Path = REPOSITORY_ROOT / "creative/layouts.json"
    hf_home: Path = Path.home() / ".cache/huggingface"
    image_runtime_python: Path = REPOSITORY_ROOT / "runtimes/rocm-torch/.venv/bin/python"
    native_media_runtime_root: Path | None = None
    wan_runtime_python: Path | None = None
    wan_source_root: Path | None = None
    wan_evaluation_preset: str = "smoke"
    hunyuan_runtime_python: Path | None = None
    hunyuan_snapshot_root: Path | None = None
    hunyuan_evaluation_preset: str = "smoke"
    cogvideox2b_runtime_python: Path | None = None
    cogvideox2b_snapshot_root: Path | None = None
    cogvideox2b_evaluation_preset: str = "smoke"
    wan21_vace_runtime_python: Path | None = None
    wan21_vace_snapshot_root: Path | None = None
    wan21_vace_evaluation_preset: str = "smoke"
    model_evaluation_timeout_sec: float = 3600.0
    host_ai_timeout_sec: float = 120.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "control_deck_url", _control_deck_origin(self.control_deck_url))
        object.__setattr__(self, "model_manifest", self.model_manifest.resolve())
        catalog = self.model_catalog_manifest
        if catalog is None and self.model_manifest == (REPOSITORY_ROOT / "worker_packs/image/models.json").resolve():
            catalog = REPOSITORY_ROOT / "worker_packs/image/catalog.json"
        object.__setattr__(self, "model_catalog_manifest", catalog.resolve() if catalog is not None else None)
        model_store_root = self.model_store_root or self.data_dir / "models"
        object.__setattr__(self, "model_store_root", model_store_root.resolve())
        object.__setattr__(self, "hf_home", self.hf_home.resolve())
        object.__setattr__(self, "creative_template_manifest", self.creative_template_manifest.resolve())
        object.__setattr__(self, "creative_layout_manifest", self.creative_layout_manifest.resolve())
        # Preserve the venv launcher path. Resolving its final `python`
        # symlink to /usr/bin/python bypasses pyvenv.cfg discovery and silently
        # starts the system interpreter without the heavyweight dependencies.
        object.__setattr__(
            self,
            "image_runtime_python",
            Path(os.path.abspath(self.image_runtime_python)),
        )
        native_runtime = self.native_media_runtime_root or (
            self.data_dir.parent / "runtimes" / "stable-diffusion-cpp-97d2990"
        )
        object.__setattr__(self, "native_media_runtime_root", native_runtime.resolve())
        if self.wan_runtime_python is not None:
            object.__setattr__(
                self,
                "wan_runtime_python",
                Path(os.path.abspath(self.wan_runtime_python)),
            )
        if self.wan_source_root is not None:
            object.__setattr__(self, "wan_source_root", self.wan_source_root.resolve())
        if self.hunyuan_runtime_python is not None:
            object.__setattr__(
                self,
                "hunyuan_runtime_python",
                Path(os.path.abspath(self.hunyuan_runtime_python)),
            )
        if self.hunyuan_snapshot_root is not None:
            object.__setattr__(self, "hunyuan_snapshot_root", self.hunyuan_snapshot_root.resolve())
        if self.cogvideox2b_runtime_python is not None:
            object.__setattr__(
                self,
                "cogvideox2b_runtime_python",
                Path(os.path.abspath(self.cogvideox2b_runtime_python)),
            )
        if self.cogvideox2b_snapshot_root is not None:
            object.__setattr__(
                self,
                "cogvideox2b_snapshot_root",
                self.cogvideox2b_snapshot_root.resolve(),
            )
        if self.wan21_vace_runtime_python is not None:
            object.__setattr__(
                self,
                "wan21_vace_runtime_python",
                Path(os.path.abspath(self.wan21_vace_runtime_python)),
            )
        if self.wan21_vace_snapshot_root is not None:
            object.__setattr__(
                self,
                "wan21_vace_snapshot_root",
                self.wan21_vace_snapshot_root.resolve(),
            )
        if self.wan_evaluation_preset not in {
            "smoke", "quality-frame", "short-clip", "practical-clip", "candidate-clip",
            "candidate-hq-clip"
        }:
            raise ValueError("Wan evaluation preset is invalid")
        if self.hunyuan_evaluation_preset not in {"smoke", "candidate-clip", "official-clip"}:
            raise ValueError("Hunyuan evaluation preset is invalid")
        if self.cogvideox2b_evaluation_preset not in {"smoke", "official-clip"}:
            raise ValueError("CogVideoX-2B evaluation preset is invalid")
        if self.wan21_vace_evaluation_preset not in {"smoke", "candidate-clip", "official-clip"}:
            raise ValueError("Wan 2.1 VACE evaluation preset is invalid")
        if (
            self.worker_timeout_sec <= 0
            or not 0 < self.blender_timeout_sec <= 180
            or self.host_request_timeout_sec <= 0
            or self.host_lease_renew_sec <= 0
            or self.model_evaluation_timeout_sec <= 0
            or self.host_ai_timeout_sec <= 0
        ):
            raise ValueError(
                "worker and host timeouts must be positive and Blender timeout must be at most 180 seconds"
            )

    @classmethod
    def from_env(cls) -> "Settings":
        configured = os.environ.get("MEDIA_FORGE_DATA_DIR")
        data_dir = Path(configured) if configured else Path.home() / ".local/share/control-deck-media-forge"
        timeout = float(os.environ.get("MEDIA_FORGE_WORKER_TIMEOUT_SEC", "30"))
        return cls(
            data_dir=data_dir.resolve(),
            worker_timeout_sec=timeout,
            blender_timeout_sec=float(os.environ.get("MEDIA_FORGE_BLENDER_TIMEOUT_SEC", "180")),
            control_deck_url=os.environ.get("MEDIA_FORGE_CONTROLDECK_URL", "http://127.0.0.1:8765"),
            host_request_timeout_sec=float(os.environ.get("MEDIA_FORGE_CONTROLDECK_TIMEOUT_SEC", "10")),
            host_lease_renew_sec=float(os.environ.get("MEDIA_FORGE_CONTROLDECK_RENEW_SEC", "10")),
            model_manifest=Path(
                os.environ.get("MEDIA_FORGE_MODEL_MANIFEST", REPOSITORY_ROOT / "worker_packs/image/models.json")
            ),
            model_catalog_manifest=Path(
                os.environ.get("MEDIA_FORGE_MODEL_CATALOG", REPOSITORY_ROOT / "worker_packs/image/catalog.json")
            ),
            model_store_root=Path(os.environ["MEDIA_FORGE_MODEL_STORE_ROOT"])
            if "MEDIA_FORGE_MODEL_STORE_ROOT" in os.environ else None,
            hf_home=Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface")),
            creative_template_manifest=Path(
                os.environ.get(
                    "MEDIA_FORGE_CREATIVE_TEMPLATES", REPOSITORY_ROOT / "creative/templates.json"
                )
            ),
            creative_layout_manifest=Path(
                os.environ.get("MEDIA_FORGE_CREATIVE_LAYOUTS", REPOSITORY_ROOT / "creative/layouts.json")
            ),
            image_runtime_python=Path(
                os.environ.get(
                    "MEDIA_FORGE_IMAGE_RUNTIME_PYTHON",
                    REPOSITORY_ROOT / "runtimes/rocm-torch/.venv/bin/python",
                )
            ),
            native_media_runtime_root=Path(os.environ["MEDIA_FORGE_NATIVE_RUNTIME_ROOT"])
            if "MEDIA_FORGE_NATIVE_RUNTIME_ROOT" in os.environ else None,
            wan_runtime_python=Path(os.environ["MEDIA_FORGE_WAN_RUNTIME_PYTHON"])
            if "MEDIA_FORGE_WAN_RUNTIME_PYTHON" in os.environ else None,
            wan_source_root=Path(os.environ["MEDIA_FORGE_WAN_SOURCE_ROOT"])
            if "MEDIA_FORGE_WAN_SOURCE_ROOT" in os.environ else None,
            wan_evaluation_preset=os.environ.get("MEDIA_FORGE_WAN_EVALUATION_PRESET", "smoke"),
            hunyuan_runtime_python=Path(os.environ["MEDIA_FORGE_HUNYUAN_RUNTIME_PYTHON"])
            if "MEDIA_FORGE_HUNYUAN_RUNTIME_PYTHON" in os.environ else None,
            hunyuan_snapshot_root=Path(os.environ["MEDIA_FORGE_HUNYUAN_SNAPSHOT_ROOT"])
            if "MEDIA_FORGE_HUNYUAN_SNAPSHOT_ROOT" in os.environ else None,
            hunyuan_evaluation_preset=os.environ.get(
                "MEDIA_FORGE_HUNYUAN_EVALUATION_PRESET",
                "smoke",
            ),
            cogvideox2b_runtime_python=Path(os.environ["MEDIA_FORGE_COGVIDEOX2B_RUNTIME_PYTHON"])
            if "MEDIA_FORGE_COGVIDEOX2B_RUNTIME_PYTHON" in os.environ else None,
            cogvideox2b_snapshot_root=Path(os.environ["MEDIA_FORGE_COGVIDEOX2B_SNAPSHOT_ROOT"])
            if "MEDIA_FORGE_COGVIDEOX2B_SNAPSHOT_ROOT" in os.environ else None,
            cogvideox2b_evaluation_preset=os.environ.get(
                "MEDIA_FORGE_COGVIDEOX2B_EVALUATION_PRESET",
                "smoke",
            ),
            wan21_vace_runtime_python=Path(os.environ["MEDIA_FORGE_WAN21_VACE_RUNTIME_PYTHON"])
            if "MEDIA_FORGE_WAN21_VACE_RUNTIME_PYTHON" in os.environ else None,
            wan21_vace_snapshot_root=Path(os.environ["MEDIA_FORGE_WAN21_VACE_SNAPSHOT_ROOT"])
            if "MEDIA_FORGE_WAN21_VACE_SNAPSHOT_ROOT" in os.environ else None,
            wan21_vace_evaluation_preset=os.environ.get(
                "MEDIA_FORGE_WAN21_VACE_EVALUATION_PRESET",
                "smoke",
            ),
            model_evaluation_timeout_sec=float(
                os.environ.get("MEDIA_FORGE_MODEL_EVALUATION_TIMEOUT_SEC", "3600")
            ),
            host_ai_timeout_sec=float(os.environ.get("MEDIA_FORGE_HOST_AI_TIMEOUT_SEC", "120")),
        )
