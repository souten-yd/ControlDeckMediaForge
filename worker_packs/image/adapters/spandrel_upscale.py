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
    """Enlarge or repair an image in tiles, so cost follows area instead of exploding.

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
        self.takes_mask = False
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
        from spandrel import ImageModelDescriptor, MaskedImageModelDescriptor, ModelLoader

        started = time.perf_counter()
        # 拡張子では読まない。Hub の snapshot は blob への symlink で、辿った先の
        # 名前は sha256 だけである（実機で "Unsupported model file extension ."
        # になった）。中身で見分ける。包み（params_ema など）は spandrel が解く。
        state = self._state_dict(self._weights())
        # 配布によっては全体をもう 1 段包んでいる（big-lama は
        # `model.generator.model.*` で、spandrel は `generator.model.*` を探す）。
        # 包みを剥がすのは、鍵の名前で系統を見分ける仕組みだからである。
        if state and all(key.startswith("model.") for key in state):
            unwrapped = {key[len("model."):]: value for key, value in state.items()}
            try:
                descriptor = ModelLoader().load_from_state_dict(unwrapped)
            except Exception:
                descriptor = ModelLoader().load_from_state_dict(state)
        else:
            descriptor = ModelLoader().load_from_state_dict(state)
        # 塗った所を埋めるものは、絵と一緒にマスクを取る（別の descriptor に
        # なる）。どちらも「絵を入れて絵が返る」点は同じなので、同じ経路に置く。
        if not isinstance(descriptor, (ImageModelDescriptor, MaskedImageModelDescriptor)):
            raise ValueError("these weights do not take an image")
        self.takes_mask = isinstance(descriptor, MaskedImageModelDescriptor)
        # 拡大（SR）、寸法を変えない補正（Restoration）、塗った所を周りから
        # 埋めるもの（Inpainting）を同じ経路で扱う。どれも標本化せず、prompt も
        # seed も持たない。倍率は重みが持っていて、1 倍なら寸法は変わらない。
        if descriptor.purpose not in {"SR", "Restoration", "Inpainting"}:
            raise ValueError("these weights neither enlarge nor repair an image")
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

    @staticmethod
    def _state_dict(path: Path) -> dict:
        """Read the weights, whichever of the two formats they came in.

        safetensors は先頭 8 byte が header の長さ（little endian）で、その次が
        JSON の `{` である。zip（torch の保存形式）は `PK` で始まる。名前ではなく
        これで見分ける。torch 側は weights_only で任意コードの復元を許さない。
        """
        import torch

        with path.open("rb") as stream:
            head = stream.read(9)
        if len(head) == 9 and head[8:9] == b"{":
            from safetensors.torch import load_file

            return load_file(str(path))
        return torch.load(path, map_location="cpu", weights_only=True)

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

    # 塗った所の周りをどれだけ見せるか。埋める内容はここから決まるので、
    # 狭いと continuation が取れない。塗った範囲と同じだけ、最低 128px。
    ERASE_CONTEXT = 128
    # 一度に通す画素数の上限。切り抜きは塗った範囲の 3 倍角になるので、
    # 広く塗ると跳ね上がる（実測: 21.3MP の写真に 2000x900 を塗ると
    # 切り抜きが 6000x2700 になり 339 秒・14.3 GiB）。超えたら縮めて通し、
    # 埋めた所だけを元の大きさへ戻す。LaMa の出力はもともと滑らかなので、
    # ここで細部を失うことはない。
    ERASE_MAX_PIXELS = 2_500_000

    def erase(self, source_path: Path, mask_path: Path, output_path: Path) -> ImageGenerationResult:
        """Fill the painted area from what surrounds it.

        塗った所だけを、周りの続きで埋める。描き直さないので、絵柄も明るさも
        変わらない（拡散モデルに同じことをさせると、塗った範囲に別のものを描き、
        帯になって残る）。

        画像ぜんぶを一度に通さない。VRAM は面積に比例するので、塗った所の周りを
        切り出して回し、元の画布へ戻す。塗っていない所は元から複製する。
        """
        import torch

        self.load()
        assert self.model is not None
        try:
            with Image.open(source_path) as opened:
                opened.load()
                source = opened.convert("RGB")
            with Image.open(mask_path) as opened:
                opened.load()
                mask = opened.convert("L")
        except (OSError, SyntaxError) as exc:
            raise ValueError("source image or mask is not decodable") from exc
        if mask.size != source.size:
            raise ValueError("edit mask dimensions must match the source image")
        box = mask.point(lambda value: 255 if value > 127 else 0).getbbox()
        if box is None:
            raise ValueError("edit mask must contain at least one painted pixel")

        started = time.perf_counter()
        margin = max(self.ERASE_CONTEXT, box[2] - box[0], box[3] - box[1])
        crop = (
            max(0, box[0] - margin), max(0, box[1] - margin),
            min(source.width, box[2] + margin), min(source.height, box[3] + margin),
        )
        patch = source.crop(crop)
        patch_mask = mask.crop(crop)
        full = patch.size
        pixels = patch.width * patch.height
        if pixels > self.ERASE_MAX_PIXELS:
            ratio = (self.ERASE_MAX_PIXELS / pixels) ** 0.5
            reduced = (max(16, round(patch.width * ratio)), max(16, round(patch.height * ratio)))
            patch = patch.resize(reduced, Image.Resampling.LANCZOS)
            patch_mask = patch_mask.resize(reduced, Image.Resampling.NEAREST)
        device = next(self.model.model.parameters()).device
        image = self._to_tensor(patch).to(device)
        binary = self._to_tensor(patch_mask.convert("RGB"))[:, :1].to(device)
        binary = (binary > 0.5).float()
        with torch.no_grad():
            filled = self.model(image, binary).clamp(0, 1).float().cpu()

        # 塗っていない所は、モデルの出力ではなく元から取る。網は画布ぜんぶを
        # 返すので、そのまま採ると塗っていない所まで通したものになる。混ぜるのは
        # 元の大きさに戻してから。マスクは原寸のものを使う。
        produced = self._as_image(filled)
        if produced.size != full:
            produced = produced.resize(full, Image.Resampling.LANCZOS)
        original = source.crop(crop)
        keep = mask.crop(crop).point(lambda value: 255 if value > 127 else 0)
        blended = Image.composite(produced, original, keep)
        composed = source.copy()
        composed.paste(blended, crop[:2])
        self._save_rgb(composed, output_path)
        self.last_generation_sec = time.perf_counter() - started
        return ImageGenerationResult(output_path=output_path, seed=0)

    @staticmethod
    def _as_image(tensor) -> Image.Image:
        import numpy

        array = tensor[0].permute(1, 2, 0).numpy()
        return Image.fromarray((array * 255.0).round().astype(numpy.uint8))

    @staticmethod
    def _save_rgb(image: Image.Image, output_path: Path) -> None:
        output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        image.convert("RGBA").save(output_path, format="PNG")

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
