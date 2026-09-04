from __future__ import annotations

import time
from itertools import islice
from pathlib import Path
from typing import Any

from PIL import Image

from .base import ImageEditRequest, ImageGenerationRequest, ImageGenerationResult
from ..edit_composition import (
    compose_outpaint,
    compose_strict_edit,
    editable_mask,
    outpaint_reference,
    strict_edit_plan,
)


class DiffusersFlux2KleinAdapter:
    """FLUX.2 Klein adapter loaded only inside the heavyweight image runtime."""

    def __init__(
        self,
        model_path: Path,
        *,
        device_mode: str = "full_device",
        disable_mmap: bool = False,
    ):
        if device_mode not in {"full_device", "direct_device_map", "cpu_offload", "cpu"}:
            raise ValueError("unsupported image device mode")
        self.model_path = model_path.resolve(strict=True)
        self.device_mode = device_mode
        self.disable_mmap = disable_mmap
        self.pipeline: Any | None = None
        # 塗った所を渡せる経路。重みは base と共有するので、載せ直しは起きない。
        self.inpaint_pipeline: Any | None = None
        self.load_sec: float | None = None
        self.last_generation_sec: float | None = None
        self.placement: dict[str, Any] = {}

    @property
    def torch_device(self) -> str:
        """置き場所。broker が host を割り当てた要求は VRAM を取らない。"""
        return "cpu" if self.device_mode == "cpu" else "cuda"

    def _settle(self) -> None:
        """GPU の後始末。CPU 実行では触らない（初期化されていないこともある）。"""
        import torch

        if self.device_mode == "cpu":
            return
        torch.cuda.synchronize()
        if self.device_mode == "cpu_offload":
            torch.cuda.empty_cache()

    @staticmethod
    def _hook_uses_offload(hook: object, *, depth: int = 0) -> bool:
        if depth > 4:
            return False
        hook_type = type(hook).__name__.lower()
        if "offload" in hook_type:
            return True
        if getattr(hook, "offload", False) is True:
            return True
        nested = getattr(hook, "hooks", ())
        if not isinstance(nested, (list, tuple)):
            return False
        return any(
            DiffusersFlux2KleinAdapter._hook_uses_offload(item, depth=depth + 1)
            for item in nested[:32]
        )

    @staticmethod
    def _component_device(component: object) -> str | None:
        device = getattr(component, "device", None)
        if device is not None:
            return str(device)
        parameters = getattr(component, "parameters", None)
        if not callable(parameters):
            return None
        try:
            parameter = next(iter(parameters()))
        except (StopIteration, TypeError):
            return None
        value = getattr(parameter, "device", None)
        return str(value) if value is not None else None

    @staticmethod
    def _device_map(component: object) -> dict[str, str]:
        value = getattr(component, "hf_device_map", None)
        if not isinstance(value, dict):
            return {}
        return {
            str(name)[:120]: str(target)[:40]
            for name, target in list(value.items())[:64]
        }

    @classmethod
    def _offload_hook_paths(cls, components: dict[str, object]) -> list[str]:
        found: set[str] = set()
        visited: set[int] = set()
        for component_name, component in components.items():
            candidates: list[tuple[str, object]] = [(component_name, component)]
            named_modules = getattr(component, "named_modules", None)
            if callable(named_modules):
                try:
                    candidates.extend(
                        (f"{component_name}.{name}" if name else component_name, module)
                        for name, module in islice(named_modules(), 8192)
                    )
                except (TypeError, RuntimeError):
                    pass
            for path, module in candidates:
                identity = id(module)
                if identity in visited:
                    continue
                visited.add(identity)
                if cls._hook_uses_offload(getattr(module, "_hf_hook", None)):
                    found.add(path[:200])
                    if len(found) >= 64:
                        return sorted(found)
        return sorted(found)

    def _inspect_placement(self, pipeline: object) -> dict[str, Any]:
        components: dict[str, object] = {"pipeline": pipeline}
        for name in ("text_encoder", "transformer", "vae"):
            component = getattr(pipeline, name, None)
            if component is not None:
                components[name] = component
        devices = {
            name: device
            for name, component in components.items()
            if (device := self._component_device(component)) is not None
        }
        device_maps = {
            name: mapping
            for name, component in components.items()
            if (mapping := self._device_map(component))
        }
        offload_hooks = self._offload_hook_paths(components)
        non_gpu_devices = {
            name: device
            for name, device in devices.items()
            if not device.lower().startswith(("cuda", "hip"))
        }
        non_gpu_map_targets = sorted({
            target
            for mapping in device_maps.values()
            for target in mapping.values()
            if target.lower() in {"cpu", "disk", "meta"}
        })
        return {
            "component_devices": devices,
            "device_maps": device_maps,
            "offload_hooks": offload_hooks,
            "non_gpu_devices": non_gpu_devices,
            "non_gpu_map_targets": non_gpu_map_targets,
        }

    def _verify_direct_placement(self) -> None:
        if self.device_mode != "direct_device_map":
            return
        if (
            self.placement.get("offload_hooks")
            or self.placement.get("non_gpu_devices")
            or self.placement.get("non_gpu_map_targets")
        ):
            raise RuntimeError(
                "direct_device_map unexpectedly selected CPU/disk offload: "
                f"{self.placement}"
            )

    def load(self) -> None:
        if self.pipeline is not None:
            return
        import torch
        from diffusers import Flux2KleinPipeline

        started = time.perf_counter()
        text_encoder: Any | None = None
        if self.disable_mmap:
            # Diffusers 0.40 forwards disable_mmap to Diffusers components but
            # not to Transformers components. Load Qwen explicitly so half of
            # the pipeline does not silently remain on the slow mmap transfer
            # path (huggingface/diffusers#12599).
            from transformers import Qwen3ForCausalLM

            text_encoder_options: dict[str, Any] = {
                "dtype": torch.bfloat16,
                "local_files_only": True,
                "disable_mmap": True,
            }
            if self.device_mode == "direct_device_map":
                text_encoder_options["device_map"] = "cuda"
            text_encoder = Qwen3ForCausalLM.from_pretrained(
                self.model_path / "text_encoder",
                **text_encoder_options,
            )
        load_options: dict[str, Any] = {
            "torch_dtype": torch.bfloat16,
            "local_files_only": True,
            "disable_mmap": self.disable_mmap,
        }
        if text_encoder is not None:
            load_options["text_encoder"] = text_encoder
        if self.device_mode == "direct_device_map":
            load_options["device_map"] = "cuda"
        pipeline = Flux2KleinPipeline.from_pretrained(self.model_path, **load_options)
        if self.device_mode == "cpu_offload":
            pipeline.enable_model_cpu_offload()
        elif self.device_mode == "full_device":
            pipeline.to("cuda")
        elif self.device_mode == "cpu":
            pipeline.to("cpu")
        pipeline.set_progress_bar_config(disable=True)
        self._settle()
        self.placement = self._inspect_placement(pipeline)
        self._verify_direct_placement()
        self.pipeline = pipeline
        self.load_sec = time.perf_counter() - started

    def _inpainter(self) -> Any:
        """The pipeline that takes the painted area, over the weights already loaded.

        描き足すには、塗った所を model へ渡さなければならない。渡さずに切り抜きを
        描き直して塗った所だけ採ると、model は「どこへ描くか」を知らないまま自分の
        再構成を作り、それが塗った形に切り抜かれる。書き足しではなく書き換えになる。

        構成要素は base と同じものを渡すので、重みはもう card の上にあり、載せ直しも
        追加の常駐も起きない。

        `is_distilled` は構成要素ではないので `components` には入らない。既定の
        False のまま作ると、pipeline は classifier-free guidance を前提にする。
        klein は蒸留済みで guidance が焼き込まれており、そこへ 1.0 を渡すと prompt が
        ほとんど効かない（実機で、塗った所が周りの続きで埋まるだけになった）。
        base が宣言している値をそのまま引き継ぐ。
        """
        if self.inpaint_pipeline is not None:
            return self.inpaint_pipeline
        from diffusers import Flux2KleinInpaintPipeline

        assert self.pipeline is not None
        pipeline = Flux2KleinInpaintPipeline(
            **self.pipeline.components,
            is_distilled=bool(getattr(self.pipeline.config, "is_distilled", False)),
        )
        pipeline.set_progress_bar_config(disable=True)
        self.inpaint_pipeline = pipeline
        return pipeline

    def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        import torch

        self.load()
        assert self.pipeline is not None
        generator = torch.Generator(device=self.torch_device).manual_seed(request.seed)
        references: list[Image.Image] = []
        for path in request.reference_paths:
            try:
                with Image.open(path) as opened:
                    opened.load()
                    reference = opened.convert("RGBA")
            except (OSError, SyntaxError) as exc:
                raise ValueError("profile reference image is not decodable") from exc
            if reference.size != (request.width, request.height):
                reference = reference.resize((request.width, request.height), Image.Resampling.LANCZOS)
            references.append(reference)
        started = time.perf_counter()
        try:
            arguments = dict(
                prompt=request.prompt,
                width=request.width,
                height=request.height,
                num_inference_steps=request.steps,
                guidance_scale=1.0,
                generator=generator,
            )
            if references:
                arguments["image"] = references
            result = self.pipeline(**arguments)
            image = result.images[0].convert("RGBA")
        finally:
            self._settle()
        self.last_generation_sec = time.perf_counter() - started
        request.output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        image.save(request.output_path, format="PNG")
        return ImageGenerationResult(output_path=request.output_path, seed=request.seed)

    # 塗った所の周りを最低どれだけ見せるか。これを下回ると、小さな塗りでは
    # 切り抜きが塗った所とほぼ同じになり、model は周りを見ずに描くことになる。
    EDIT_CONTEXT = 64

    @staticmethod
    def _edit_crop_box(
        mask_box: tuple[int, int, int, int],
        width: int,
        height: int,
        *,
        context_pixels: int | None = None,
    ) -> tuple[int, int, int, int]:
        """How much of the surroundings the model is shown around the painted area.

        効くのは幅そのものではなく、切り抜きに対して塗った所が占める割合である。
        固定幅だと、広く塗ったときに切り抜きのほとんどが塗った所になり、model は
        周りをほとんど見ないまま塗った所を埋める。実機では、そこに元の空とは別の
        青空が描かれ、塗った楕円の形が縁として残った。

        2026-09-01 実測（480x380 の塗り、"a large red hot air balloon"）:
            周り  64px  切り抜き 568x504（塗り 63%）  18.0s  楕円の縁が見える
            周り 160px  切り抜き 664x600（塗り 43%）  87.3s  曇り空に馴染む
            周り 320px  切り抜き 824x760（塗り 29%） 154.6s  馴染む。費用 8.6 倍
        塗った所の長辺の 1/3 を取ると、480 に対して 160 になる。小さな塗りでは
        下限の 64 が効くので、透かし程度の塗りの費用はほとんど変わらない。
        """
        left, top, right, bottom = mask_box
        if context_pixels is None:
            longest = max(right - left, bottom - top)
            context_pixels = max(DiffusersFlux2KleinAdapter.EDIT_CONTEXT, longest // 3)
        return (
            max(0, left - context_pixels),
            max(0, top - context_pixels),
            min(width, right + context_pixels),
            min(height, bottom + context_pixels),
        )

    @staticmethod
    def _generation_size(width: int, height: int) -> tuple[int, int]:
        return (
            max(256, (width + 15) // 16 * 16),
            max(256, (height + 15) // 16 * 16),
        )

    # 塗った所の切り抜きを 1 度に通す画素数の上限。FLUX.2 Klein が学習した面積
    # （1024x1024）である。切り抜きは元画像の大きさと塗った範囲で決まるので、
    # 大きな写真に広く塗ると際限なく伸びる。attention は面積の二乗で効くため、
    # 上限を持たないと card に載らなくなる。
    #
    # 生成そのものの枠ではない。ここを他の編集にも掛けると、いま 2048 まで
    # 通っている参考編集が黙って縮む。掛けるのは切り抜きだけである。
    MAX_PATCH_PIXELS = 1024 * 1024

    @classmethod
    def _patch_generation_size(cls, width: int, height: int) -> tuple[int, int]:
        """The size to run the painted-area crop at, bounded by what the model holds.

        比を保ったまま上限へ収める。合成は原寸の切り抜きへ戻すので、縮めた分は
        塗った所の細かさに出る（塗っていない所は元のままである）。
        """
        if width * height <= cls.MAX_PATCH_PIXELS:
            return cls._generation_size(width, height)
        ratio = (cls.MAX_PATCH_PIXELS / (width * height)) ** 0.5
        # 収めたものは切り下げる。ここで切り上げると上限を越え直す。
        return (
            max(256, int(width * ratio) // 16 * 16),
            max(256, int(height * ratio) // 16 * 16),
        )

    def edit(self, request: ImageEditRequest) -> ImageGenerationResult:
        import torch

        self.load()
        assert self.pipeline is not None
        try:
            with Image.open(request.source_path) as opened:
                opened.load()
                source = opened.convert("RGBA")
        except (OSError, SyntaxError) as exc:
            raise ValueError("source image is not decodable") from exc

        patch_box = (0, 0, source.width, source.height)
        reference: Image.Image | list[Image.Image] = source
        if request.edit_mode == "outpaint":
            reference, _plan = outpaint_reference(request.source_path, request.width, request.height)
        elif request.strict_edit:
            if request.mask_path is None:
                raise ValueError("strict edit requires an edit mask")
            plan = strict_edit_plan(request.source_path, request.mask_path)
            patch_box = self._edit_crop_box(plan.crop_box, plan.width, plan.height)
            reference = source.crop(patch_box)
        if request.edit_mode == "outpaint":
            generation_size = self._generation_size(request.width, request.height)
        elif request.strict_edit:
            assert isinstance(reference, Image.Image)
            generation_size = self._patch_generation_size(reference.width, reference.height)
        else:
            generation_size = self._generation_size(source.width, source.height)
        if request.edit_mode == "multi_reference" or request.reference_paths:
            assert isinstance(reference, Image.Image)
            references = [reference]
            for path in request.reference_paths:
                try:
                    with Image.open(path) as opened:
                        opened.load()
                        references.append(opened.convert("RGBA"))
                except (OSError, SyntaxError) as exc:
                    raise ValueError("reference image is not decodable") from exc
            reference = references
        if isinstance(reference, list):
            reference = [
                item if item.size == generation_size else item.resize(generation_size, Image.Resampling.LANCZOS)
                for item in reference
            ]
        elif reference.size != generation_size:
            reference = reference.resize(generation_size, Image.Resampling.LANCZOS)

        # 塗った所があるなら、それを model へ渡す経路を通す。切り抜きを描き直して
        # 塗った形に切り抜くのと違い、塗っていない所は model の中でも動かないので、
        # 描かれたものは塗った所へ入り、境目に帯も出ない。
        painting = (
            request.strict_edit
            and request.mask_path is not None
            and request.edit_mode != "outpaint"
            and not request.reference_paths
            and request.edit_mode != "multi_reference"
        )
        generator = torch.Generator(device=self.torch_device).manual_seed(request.seed)
        started = time.perf_counter()
        try:
            if painting:
                assert request.mask_path is not None
                assert isinstance(reference, Image.Image)
                painted = editable_mask(request.mask_path).crop(patch_box)
                if painted.size != generation_size:
                    painted = painted.resize(generation_size, Image.Resampling.LANCZOS)
                # 縮小で付いた半端な縁を落とす。塗った形そのものを渡す。最終的な
                # 合成は原寸のマスクで行うので、ここが厳密さの根拠ではない。
                painted = painted.point(lambda value: 255 if value > 127 else 0)
                result = self._inpainter()(
                    image=reference,
                    mask_image=painted,
                    prompt=request.prompt,
                    width=generation_size[0],
                    height=generation_size[1],
                    num_inference_steps=request.steps,
                    # 塗った所は作り直す。残したいなら塗らない、が操作の意味である。
                    strength=1.0,
                    guidance_scale=1.0,
                    generator=generator,
                )
            else:
                result = self.pipeline(
                    image=reference,
                    prompt=request.prompt,
                    width=generation_size[0],
                    height=generation_size[1],
                    num_inference_steps=request.steps,
                    guidance_scale=1.0,
                    generator=generator,
                )
            generated = result.images[0].convert("RGBA")
        finally:
            self._settle()
        self.last_generation_sec = time.perf_counter() - started

        if request.edit_mode == "outpaint":
            compose_outpaint(
                request.source_path,
                generated,
                request.output_path,
                width=request.width,
                height=request.height,
            )
        elif request.strict_edit:
            assert request.mask_path is not None
            compose_strict_edit(
                request.source_path,
                request.mask_path,
                generated,
                request.output_path,
                patch_box=patch_box,
            )
        else:
            output = generated.resize((request.width, request.height), Image.Resampling.LANCZOS)
            request.output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            output.save(request.output_path, format="PNG")
        return ImageGenerationResult(output_path=request.output_path, seed=request.seed)
