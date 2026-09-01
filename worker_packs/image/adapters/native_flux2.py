"""FLUX.2-dev through the pinned stable-diffusion.cpp build.

32B は python の拡散スタックでは載らない。BF16 の実体は 64GB あり、量子化した
ものを載せる仕組みも diffusers 側には無い。GGUF へ量子化した重みを、動画側が
既に使っている pinned build（`sd-cli`）で回す。**駆動系を 2 つ持たない。**

配置は実機で決めた。`--offload-to-cpu`（重みを RAM に置いて VRAM へ流し込む）は
この機械では成立しない。拡散本体 19.15GB を RAM に展開する段階で 30GB を使い切り、
GPU が 3% のまま 11 分進まなかった。拡散を直接 VRAM に置き、文章モデルだけを RAM に
残すと swap ゼロで通る（2026-09-01 実測）。
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from PIL import Image

from .base import ImageEditRequest, ImageGenerationRequest, ImageGenerationResult


class NativeFlux2Adapter:
    """Drive FLUX.2-dev with the native runtime, one process per image."""

    # 動画側と同じ pinned build である。別の commit を指すと、片方だけ直して
    # もう片方が動かなくなる。
    RUNTIME_COMMIT = "97d2990807fe6d558e395f8764198d7c7e7b411c"

    # 1 つの gguf では動かない。拡散本体・文章モデル・VAE の 3 つを渡す。
    # 名前は registry が宣言している置き場所と同じで、別のものを掴まないよう
    # repository の内側に収まることを確かめてから渡す。
    FILES = (
        ("--diffusion-model", "flux2-dev-Q4_K_M.gguf"),
        ("--llm", "text_encoder/Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf"),
        ("--vae", "vae/full_encoder_small_decoder.safetensors"),
    )

    # 実機で決めた配分。文章モデル 15.3GB は RAM、拡散 19.3GB は VRAM。
    # 逆にすると（RAM に拡散を置くと）30GB の RAM を使い切って進まなくなる。
    BACKEND = "te=cpu,diffusion=ROCm0,vae=ROCm0"

    # 駆動系が要る場所。無いと libomp.so が見つからず起動しない。動画側と同じ。
    ROCM_LIBS = "/opt/rocm/lib/llvm/lib:/opt/rocm/lib"

    def __init__(
        self,
        model_path: Path,
        *,
        device_mode: str = "full_device",
        disable_mmap: bool = False,
        **_options: object,
    ):
        self.model_path = Path(model_path)
        self.device_mode = device_mode
        self.disable_mmap = disable_mmap
        # 重みはこの process に載らない。sd-cli が読み書きする。
        self.load_sec = 0.0
        self.last_generation_sec: float | None = None
        self.placement: dict[str, object] = {
            "component_devices": {
                "text_encoder": "cpu", "diffusion": "ROCm0", "vae": "ROCm0",
            },
            "device_maps": {}, "offload_hooks": [],
            "non_gpu_devices": {"text_encoder": "cpu"}, "non_gpu_map_targets": [],
        }

    @property
    def runtime_version(self) -> str:
        return self.RUNTIME_COMMIT

    def load(self) -> None:
        """Nothing is held here. The weights live for one sd-cli process only."""

    def _executable(self) -> Path:
        root = os.environ.get("MEDIA_FORGE_NATIVE_RUNTIME_ROOT")
        if not root:
            raise ValueError("the native media runtime is not configured")
        runtime = Path(root).resolve(strict=True)
        executable = (runtime / "build" / "bin" / "sd-cli").resolve(strict=True)
        if not executable.is_relative_to(runtime):
            raise ValueError("the native runtime executable is outside its root")
        if not os.access(executable, os.X_OK):
            raise ValueError("the native media runtime is not executable")
        return executable

    def _model_file(self, relative: str) -> Path:
        """Follow the snapshot name to the blob, then check the boundary.

        Hub の置き方では snapshot の中身は blobs/ への symlink である。snapshot
        だけを境界にすると、正しい重みが「外にある」と判定される。境界はその
        repository の根（snapshots/ と blobs/ を含む階層）に置く。動画側と同じ。
        """
        candidate = self.model_path / relative
        try:
            resolved = candidate.resolve(strict=True)
            repo_root = self.model_path.parent.parent.resolve(strict=True)
        except OSError as exc:
            raise ValueError(f"model file {relative} is missing") from exc
        if not resolved.is_relative_to(repo_root):
            raise ValueError(f"model file {relative} is outside the model repository")
        return resolved

    def _environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        existing = environment.get("LD_LIBRARY_PATH")
        environment["LD_LIBRARY_PATH"] = (
            f"{self.ROCM_LIBS}:{existing}" if existing else self.ROCM_LIBS
        )
        # 統合 GPU（gfx1036）を掴ませない。--list-devices はそれも ROCm1 として
        # 数えるので、明示しないと配分が別の card へ向くことがある。
        environment["ROCR_VISIBLE_DEVICES"] = "0"
        environment["HIP_VISIBLE_DEVICES"] = "0"
        return environment

    def _command(self, request: ImageGenerationRequest) -> list[str]:
        command = [str(self._executable()), "-M", "img_gen"]
        for flag, relative in self.FILES:
            command += [flag, str(self._model_file(relative))]
        command += [
            # VAE の潜在表現の形は名前からは決まらない。auto に任せると別の
            # 系統として読まれる。
            "--vae-format", "flux2",
            "--prompt", request.prompt,
            # dev は guidance を焼き込んである。真の CFG を掛けると二重になる。
            "--cfg-scale", "1.0",
            "--sampling-method", "euler",
            "--steps", str(request.steps),
            "-W", str(request.width),
            "-H", str(request.height),
            "--seed", str(request.seed),
            "--backend", self.BACKEND,
            "--diffusion-fa",
            "--mmap",
            "--output", str(request.output_path),
        ]
        return command

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if request.reference_paths:
            # sd-cli は `-r` で参照を取れるが、この経路では測っていない。
            # 受けられるように見せて別のものを返すより、断る方がよい。
            raise ValueError("this model does not take reference images yet")
        request.output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        command = self._command(request)
        started = time.perf_counter()
        completed = subprocess.run(
            command, check=False, capture_output=True, env=self._environment(),
        )
        self.last_generation_sec = time.perf_counter() - started
        if completed.returncode != 0 or not request.output_path.is_file():
            detail = completed.stderr.decode("utf-8", "replace")[-300:]
            raise ValueError(f"the native image runtime failed: {detail}")
        # 核は 8bit RGBA を求める。sd-cli は RGB の PNG を書く。
        with Image.open(request.output_path) as opened:
            opened.load()
            produced = opened.convert("RGBA")
        produced.save(request.output_path, format="PNG")
        return ImageGenerationResult(output_path=request.output_path, seed=request.seed)

    def edit(self, _request: ImageEditRequest) -> ImageGenerationResult:
        raise ValueError("this model does not edit images yet")
