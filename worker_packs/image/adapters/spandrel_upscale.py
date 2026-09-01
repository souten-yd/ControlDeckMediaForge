"""Deterministic super-resolution for photographs.

This is not a generator. There is no prompt, no seed and no sampling: the same
picture in gives the same picture out. It is kept apart from the diffusers
adapters for that reason — asking a diffusion model to "improve" a photograph
rewrites it, which is the opposite of what someone wants from their own photo.

`spandrel` reads the architecture out of the weights, so the same adapter takes
any of the ordinary super-resolution checkpoints without a hand-written network
per family. It reaches torch directly; nothing here touches diffusers.
"""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

from .base import ImageGenerationResult


class SpandrelUpscaleAdapter:
    """Enlarge an image in tiles, so cost follows area instead of exploding.

    Whole-image inference measured 8.61 GiB of card for a 512x384 picture:
    attention is quadratic in the tile, so a photograph would not fit at any
    useful size. In 256px tiles the same work holds under 1 GiB regardless of
    how large the picture is (実測: 0.79MP → 12.6MP を 16.2 秒 / 0.81 GiB)。
    """

    # 16 の倍数で、SwinIR の window（8）にも割り切れる。小さくすると継ぎ目の
    # 処理が増えて遅くなり、大きくすると VRAM が二乗で効く。
    TILE = 256
    # 継ぎ目を平均で溶かすための重なり。0 にすると格子が見える。
    OVERLAP = 32

    def __init__(self, model_path: Path, **_options: object):
        self.model_path = Path(model_path)
        self.model = None
        self.scale = 1
        self.load_sec = 0.0
        self.last_generation_sec: float | None = None
        # 1 つの網を丸ごと card に置く。分割も offload もしないので、報告する
        # 配置は 1 行で足りる。空にすると「測っていない」と読めてしまう。
        self.placement: dict[str, object] = {}

    def load(self) -> None:
        if self.model is not None:
            return
        import torch
        from spandrel import ImageModelDescriptor, ModelLoader

        started = time.perf_counter()
        # 拡張子では読まない。Hub の snapshot は blob への symlink で、辿った先の
        # 名前は sha256 だけである（実機で "Unsupported model file extension ."
        # になった）。重みそのものから読み、包み（params_ema など）は spandrel が
        # 解く。weights_only で任意コードの復元は許さない。
        state = torch.load(self._weights(), map_location="cpu", weights_only=True)
        descriptor = ModelLoader().load_from_state_dict(state)
        if not isinstance(descriptor, ImageModelDescriptor):
            raise ValueError("upscale weights are not an image model")
        if descriptor.purpose != "SR":
            raise ValueError("upscale weights are not a super-resolution model")
        if descriptor.input_channels != 3 or descriptor.output_channels != 3:
            raise ValueError("upscale weights must take and return RGB")
        descriptor.eval()
        if torch.cuda.is_available():
            descriptor.cuda()
        self.model = descriptor
        self.scale = int(descriptor.scale)
        self.placement = {
            "component_devices": {"upscaler": str(next(descriptor.model.parameters()).device)},
            "device_maps": {}, "offload_hooks": [],
            "non_gpu_devices": {}, "non_gpu_map_targets": [],
        }
        self.load_sec = time.perf_counter() - started

    def _weights(self) -> Path:
        """Take the single checkpoint in the snapshot, and say so if it is not one.

        Guessing a filename here would put the model registry's pinned
        selection in two places, and they would drift.
        """
        if self.model_path.is_file():
            return self.model_path
        if not self.model_path.is_dir():
            raise ValueError("upscale weights are not present")
        found = sorted(
            path for path in self.model_path.rglob("*")
            if path.is_file() and path.suffix in {".pth", ".safetensors"}
        )
        if len(found) != 1:
            raise ValueError("upscale snapshot must hold exactly one checkpoint")
        return found[0]

    def upscale(self, source_path: Path, output_path: Path) -> ImageGenerationResult:
        import torch

        self.load()
        assert self.model is not None
        try:
            with Image.open(source_path) as opened:
                opened.load()
                source = opened.convert("RGB")
        except (OSError, SyntaxError) as exc:
            raise ValueError("source image is not decodable") from exc

        started = time.perf_counter()
        tensor = self._to_tensor(source)
        _, _, height, width = tensor.shape
        scale = self.scale
        total = torch.zeros(1, 3, height * scale, width * scale)
        counts = torch.zeros_like(total)
        step = self.TILE - self.OVERLAP
        device = next(self.model.model.parameters()).device
        for top in range(0, height, step):
            bottom = min(top + self.TILE, height)
            top_edge = max(0, bottom - self.TILE)
            for left in range(0, width, step):
                right = min(left + self.TILE, width)
                left_edge = max(0, right - self.TILE)
                patch = tensor[:, :, top_edge:bottom, left_edge:right].to(device)
                with torch.no_grad():
                    produced = self.model(patch).clamp(0, 1).float().cpu()
                box = (
                    slice(top_edge * scale, bottom * scale),
                    slice(left_edge * scale, right * scale),
                )
                total[:, :, box[0], box[1]] += produced
                counts[:, :, box[0], box[1]] += 1
                if right >= width:
                    break
            if bottom >= height:
                break
        blended = total / counts.clamp(min=1)
        self._save(blended, output_path)
        self.last_generation_sec = time.perf_counter() - started
        # 拡大に乱数は入らない。同じ絵を入れれば同じ絵が出る。
        return ImageGenerationResult(output_path=output_path, seed=0)

    @staticmethod
    def _to_tensor(image: Image.Image):
        import numpy
        import torch

        array = numpy.asarray(image).astype(numpy.float32) / 255.0
        return torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0)

    @staticmethod
    def _save(tensor, output_path: Path) -> None:
        import numpy

        array = tensor[0].permute(1, 2, 0).numpy()
        image = Image.fromarray((array * 255.0).round().astype(numpy.uint8))
        output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # 出力は RGBA で揃える。core の検証が 8bit RGBA を求める。
        image.convert("RGBA").save(output_path, format="PNG")
