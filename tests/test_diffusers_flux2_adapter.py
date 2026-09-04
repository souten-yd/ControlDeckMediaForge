from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from mediaforge.image_edit import validate_strict_edit
from mediaforge.outpaint import validate_outpaint
from worker_packs.image.adapters import ImageEditRequest
from worker_packs.image.adapters.diffusers_flux2 import DiffusersFlux2KleinAdapter


def test_image_worker_pack_does_not_import_core_implementation():
    worker_root = Path(__file__).parents[1] / "worker_packs" / "image"
    violations: list[str] = []
    for path in worker_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "mediaforge":
                violations.append(f"{path.relative_to(worker_root)}:{node.lineno}")
            elif isinstance(node, ast.Import) and any(
                alias.name.split(".")[0] == "mediaforge" for alias in node.names
            ):
                violations.append(f"{path.relative_to(worker_root)}:{node.lineno}")
    assert violations == []


def test_direct_no_mmap_loads_diffusers_and_qwen_components_on_device(monkeypatch, tmp_path: Path):
    model = tmp_path / "model"
    (model / "text_encoder").mkdir(parents=True)
    calls: dict[str, object] = {}
    text_encoder = object()

    class Qwen:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            calls["qwen"] = (path, kwargs)
            return text_encoder

    class Pipeline:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            calls["pipeline"] = (path, kwargs)
            return cls()

        def to(self, device):
            calls["to"] = device

        def enable_model_cpu_offload(self):
            calls["offload"] = True

        def set_progress_bar_config(self, **kwargs):
            calls["progress"] = kwargs

    synchronize_calls: list[bool] = []
    fake_torch = SimpleNamespace(
        bfloat16=object(),
        cuda=SimpleNamespace(synchronize=lambda: synchronize_calls.append(True)),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", SimpleNamespace(Flux2KleinPipeline=Pipeline))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(Qwen3ForCausalLM=Qwen))

    adapter = DiffusersFlux2KleinAdapter(
        model,
        device_mode="direct_device_map",
        disable_mmap=True,
    )
    adapter.load()

    qwen_path, qwen_options = calls["qwen"]
    assert qwen_path == model / "text_encoder"
    assert qwen_options == {
        "dtype": fake_torch.bfloat16,
        "local_files_only": True,
        "disable_mmap": True,
        "device_map": "cuda",
    }
    pipeline_path, pipeline_options = calls["pipeline"]
    assert pipeline_path == model
    assert pipeline_options == {
        "torch_dtype": fake_torch.bfloat16,
        "local_files_only": True,
        "disable_mmap": True,
        "text_encoder": text_encoder,
        "device_map": "cuda",
    }
    assert "to" not in calls
    assert "offload" not in calls
    assert calls["progress"] == {"disable": True}
    assert synchronize_calls == [True]
    assert adapter.placement == {
        "component_devices": {},
        "device_maps": {},
        "offload_hooks": [],
        "non_gpu_devices": {},
        "non_gpu_map_targets": [],
    }


@pytest.mark.parametrize(
    "transformer",
    [
        SimpleNamespace(device="cpu", hf_device_map={"": "cpu"}),
        SimpleNamespace(
            device="cuda:0",
            hf_device_map={"": "cuda"},
            _hf_hook=SimpleNamespace(offload=True),
        ),
        SimpleNamespace(
            device="cuda:0",
            hf_device_map={"": "cuda"},
            named_modules=lambda: [
                ("layer", SimpleNamespace(_hf_hook=SimpleNamespace(offload=True)))
            ],
        ),
    ],
)
def test_direct_device_map_rejects_unexpected_offload(monkeypatch, tmp_path: Path, transformer):
    model = tmp_path / "model"
    model.mkdir()

    class Pipeline:
        hf_device_map = {"transformer": "cuda"}

        def __init__(self):
            self.transformer = transformer

        @classmethod
        def from_pretrained(cls, _path, **_kwargs):
            return cls()

        def set_progress_bar_config(self, **_kwargs):
            pass

    fake_torch = SimpleNamespace(
        bfloat16=object(),
        cuda=SimpleNamespace(synchronize=lambda: None),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", SimpleNamespace(Flux2KleinPipeline=Pipeline))

    adapter = DiffusersFlux2KleinAdapter(
        model,
        device_mode="direct_device_map",
        disable_mmap=False,
    )
    with pytest.raises(RuntimeError, match="unexpectedly selected CPU/disk offload"):
        adapter.load()


def test_accelerate_cpu_offload_hook_type_is_detected():
    CpuOffload = type("CpuOffload", (), {})
    assert DiffusersFlux2KleinAdapter._hook_uses_offload(CpuOffload()) is True


def test_full_device_uses_post_load_transfer_without_qwen_preload(monkeypatch, tmp_path: Path):
    model = tmp_path / "model"
    model.mkdir()
    calls: dict[str, object] = {}

    class Pipeline:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            calls["pipeline"] = (path, kwargs)
            return cls()

        def to(self, device):
            calls["to"] = device

        def set_progress_bar_config(self, **kwargs):
            calls["progress"] = kwargs

    fake_torch = SimpleNamespace(
        bfloat16=object(),
        cuda=SimpleNamespace(synchronize=lambda: None),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", SimpleNamespace(Flux2KleinPipeline=Pipeline))

    adapter = DiffusersFlux2KleinAdapter(model, device_mode="full_device", disable_mmap=False)
    adapter.load()

    assert calls["pipeline"] == (
        model,
        {"torch_dtype": fake_torch.bfloat16, "local_files_only": True, "disable_mmap": False},
    )
    assert calls["to"] == "cuda"


def test_strict_edit_generates_only_bounded_patch_then_preserves_protected_pixels(
    monkeypatch, tmp_path: Path
):
    model = tmp_path / "model"
    model.mkdir()
    source_path = tmp_path / "source.png"
    mask_path = tmp_path / "mask.png"
    output_path = tmp_path / "edited.png"
    source = Image.new("RGBA", (300, 200))
    for y in range(source.height):
        for x in range(source.width):
            source.putpixel((x, y), (x % 256, y % 256, 70, (x + y) % 256))
    source.save(source_path, format="PNG")
    mask = Image.new("RGBA", source.size, (0, 0, 0, 255))
    for y in range(80, 100):
        for x in range(100, 120):
            mask.putpixel((x, y), (255, 255, 255, 255))
    mask.save(mask_path, format="PNG")
    calls: dict[str, object] = {}

    class Generator:
        def __init__(self, *, device):
            calls["generator_device"] = device

        def manual_seed(self, seed):
            calls["seed"] = seed
            return self

    class Pipeline:
        def __init__(self, key):
            self.key = key

        def __call__(self, **kwargs):
            calls[self.key] = kwargs
            return SimpleNamespace(images=[Image.new("RGBA", (kwargs["width"], kwargs["height"]), "orange")])

    fake_torch = SimpleNamespace(
        Generator=Generator,
        cuda=SimpleNamespace(synchronize=lambda: None, empty_cache=lambda: None),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    adapter = DiffusersFlux2KleinAdapter(model, device_mode="direct_device_map")
    adapter.pipeline = Pipeline("pipeline")
    adapter.inpaint_pipeline = Pipeline("inpaint")

    result = adapter.edit(ImageEditRequest(
        prompt="make the eyes orange",
        source_path=source_path,
        mask_path=mask_path,
        width=300,
        height=200,
        steps=4,
        seed=17,
        output_path=output_path,
        strict_edit=True,
    ))

    assert result.output_path == output_path
    # 塗った所がある編集は、塗った所を取る経路を通る。取らない経路へ行くと、
    # model は切り抜きを丸ごと描き直し、それが塗った形に切り抜かれる。
    assert "pipeline" not in calls, "masked edit went to the pipeline that cannot take a mask"
    pipeline_call = calls["inpaint"]
    assert pipeline_call["image"].size == (256, 256)
    assert pipeline_call["width"] == 256 and pipeline_call["height"] == 256
    # 塗った所そのものが渡る。切り抜きと同じ寸法で、白黒の 2 値である。
    painted = pipeline_call["mask_image"]
    assert painted.size == (256, 256)
    assert {value for _count, value in painted.convert("L").getcolors()} <= {0, 255}
    assert painted.getbbox() is not None
    # 塗った所は作り直す。残したいなら塗らない、が操作の意味である。
    assert pipeline_call["strength"] == 1.0
    assert calls["generator_device"] == "cuda" and calls["seed"] == 17
    assert Image.open(output_path).size == source.size
    assert validate_strict_edit(source_path, mask_path, output_path)["protected_pixel_difference"] == 0


def test_reference_edit_uses_full_source_and_requested_output(monkeypatch, tmp_path: Path):
    model = tmp_path / "model"
    model.mkdir()
    source_path = tmp_path / "source.png"
    output_path = tmp_path / "edited.png"
    Image.new("RGBA", (320, 256), "navy").save(source_path, format="PNG")
    calls: dict[str, object] = {}

    class Generator:
        def __init__(self, *, device):
            calls["generator_device"] = device

        def manual_seed(self, seed):
            calls["seed"] = seed
            return self

    class Pipeline:
        def __call__(self, **kwargs):
            calls["pipeline"] = kwargs
            return SimpleNamespace(images=[Image.new("RGBA", (kwargs["width"], kwargs["height"]), "orange")])

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        Generator=Generator,
        cuda=SimpleNamespace(synchronize=lambda: None, empty_cache=lambda: None),
    ))
    adapter = DiffusersFlux2KleinAdapter(model, device_mode="direct_device_map")
    adapter.pipeline = Pipeline()

    adapter.edit(ImageEditRequest(
        prompt="make a cheerful variation",
        source_path=source_path,
        mask_path=None,
        width=320,
        height=256,
        steps=4,
        seed=23,
        output_path=output_path,
        strict_edit=False,
    ))

    pipeline_call = calls["pipeline"]
    assert pipeline_call["image"].size == (320, 256)
    assert pipeline_call["width"] == 320 and pipeline_call["height"] == 256
    assert calls["generator_device"] == "cuda" and calls["seed"] == 23
    assert Image.open(output_path).size == (320, 256)


def test_multi_reference_edit_passes_bounded_image_list(monkeypatch, tmp_path: Path):
    model = tmp_path / "model"
    model.mkdir()
    source_path = tmp_path / "source.png"
    reference_a = tmp_path / "reference-a.png"
    reference_b = tmp_path / "reference-b.png"
    output_path = tmp_path / "edited.png"
    Image.new("RGBA", (320, 256), "navy").save(source_path, format="PNG")
    Image.new("RGBA", (128, 128), "orange").save(reference_a, format="PNG")
    Image.new("RGBA", (640, 512), "green").save(reference_b, format="PNG")
    calls: dict[str, object] = {}

    class Generator:
        def __init__(self, *, device):
            calls["generator_device"] = device

        def manual_seed(self, seed):
            calls["seed"] = seed
            return self

    class Pipeline:
        def __call__(self, **kwargs):
            calls["pipeline"] = kwargs
            return SimpleNamespace(images=[Image.new("RGBA", (kwargs["width"], kwargs["height"]), "orange")])

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        Generator=Generator,
        cuda=SimpleNamespace(synchronize=lambda: None, empty_cache=lambda: None),
    ))
    adapter = DiffusersFlux2KleinAdapter(model, device_mode="direct_device_map")
    adapter.pipeline = Pipeline()

    adapter.edit(ImageEditRequest(
        prompt="combine the references",
        source_path=source_path,
        mask_path=None,
        width=320,
        height=256,
        steps=4,
        seed=31,
        output_path=output_path,
        strict_edit=False,
        edit_mode="multi_reference",
        reference_paths=(reference_a, reference_b),
    ))

    pipeline_call = calls["pipeline"]
    assert isinstance(pipeline_call["image"], list)
    assert len(pipeline_call["image"]) == 3
    assert {item.size for item in pipeline_call["image"]} == {(320, 256)}
    assert pipeline_call["width"] == 320 and pipeline_call["height"] == 256
    assert calls["generator_device"] == "cuda" and calls["seed"] == 31


def test_outpaint_uses_expanded_reference_then_recopies_source(monkeypatch, tmp_path: Path):
    model = tmp_path / "model"
    model.mkdir()
    source_path = tmp_path / "source.png"
    output_path = tmp_path / "outpaint.png"
    source = Image.new("RGBA", (320, 256), (30, 60, 90, 170))
    source.save(source_path, format="PNG")
    calls: dict[str, object] = {}

    class Generator:
        def __init__(self, *, device):
            calls["generator_device"] = device

        def manual_seed(self, seed):
            calls["seed"] = seed
            return self

    class Pipeline:
        def __call__(self, **kwargs):
            calls["pipeline"] = kwargs
            return SimpleNamespace(images=[Image.new("RGBA", (kwargs["width"], kwargs["height"]), "orange")])

    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(
        Generator=Generator,
        cuda=SimpleNamespace(synchronize=lambda: None, empty_cache=lambda: None),
    ))
    adapter = DiffusersFlux2KleinAdapter(model, device_mode="direct_device_map")
    adapter.pipeline = Pipeline()

    adapter.edit(ImageEditRequest(
        prompt="extend the background",
        source_path=source_path,
        mask_path=None,
        width=512,
        height=384,
        steps=4,
        seed=29,
        output_path=output_path,
        strict_edit=True,
        edit_mode="outpaint",
    ))

    pipeline_call = calls["pipeline"]
    assert pipeline_call["image"].size == (512, 384)
    assert pipeline_call["width"] == 512 and pipeline_call["height"] == 384
    assert pipeline_call["image"].getpixel((0, 0))[3] == 0
    assert calls["generator_device"] == "cuda" and calls["seed"] == 29
    assert validate_outpaint(source_path, output_path, width=512, height=384)["source_pixel_difference"] == 0


def test_the_context_shown_around_a_painted_area_grows_with_it():
    """効くのは周りの幅そのものではなく、切り抜きに対する塗った所の割合である。

    固定幅だと、広く塗ったときに切り抜きのほとんどが塗った所になり、model は周りを
    見ないまま埋める。実機では元の空とは別の青空が描かれ、塗った形が縁として残った。

    2026-09-01 実測（1024x1024、480x380 の塗り、"a large red hot air balloon"）:
        周り  64px  切り抜き 568x504（塗り 63%）  18.0s  楕円の縁が見える
        周り 160px  切り抜き 664x600（塗り 43%）  87.3s  曇り空に馴染む
        周り 320px  切り抜き 824x760（塗り 29%） 154.6s  馴染む。費用 8.6 倍
    """
    crop = DiffusersFlux2KleinAdapter._edit_crop_box

    # 小さな塗りは下限が効く。透かし程度の塗りの費用は変わらない。
    assert crop((100, 100, 130, 136), 1024, 1024) == (36, 36, 194, 200)
    # 広い塗りは、長辺の 1/3 だけ周りを見せる（480 -> 160）。
    assert crop((520, 60, 1000, 440), 1024, 1024) == (360, 0, 1024, 600)
    # 端は画布で止まる。外へはみ出した切り抜きは作れない。
    assert crop((0, 0, 900, 60), 1024, 1024) == (0, 0, 1024, 360)


def test_a_patch_never_grows_past_what_the_model_holds():
    """切り抜きは元画像の大きさと塗った範囲で決まるので、際限なく伸びる。

    attention は面積の二乗で効くので、上限を持たないと card に載らなくなる。
    比を保ったまま学習した面積へ収める。上限が掛かるのは切り抜きだけで、生成
    そのものには掛からない（掛けると、いま 2048 まで通る参考編集が黙って縮む）。
    """
    size = DiffusersFlux2KleinAdapter._patch_generation_size
    assert DiffusersFlux2KleinAdapter._generation_size(4000, 3000) == (4000, 3008)

    # 収まるものは 16 の倍数へ切り上げるだけ。切り下げると切り抜きの端が落ちる。
    assert size(568, 504) == (576, 512)
    assert size(329, 299) == (336, 304)
    assert size(1024, 1024) == (1024, 1024)
    # 小さすぎるものは、model が扱える下限まで上げる。
    assert size(30, 30) == (256, 256)
    # 超えるものは比を保ったまま収める。
    wide = size(4000, 3000)
    assert wide[0] * wide[1] <= 1024 * 1024
    assert wide[0] % 16 == 0 and wide[1] % 16 == 0
    assert abs(wide[0] / wide[1] - 4000 / 3000) < 0.02


def test_host_placement_loads_on_cpu_and_does_not_touch_the_gpu(monkeypatch, tmp_path: Path):
    """broker が host を割り当てたら VRAM を確保しない。

    契約は docs/design-ai-resource-broker.md §0 の 3 で、守れない Add-on は
    host 配置を要求してはならない。`torch.cuda` を触らないことまでを見る。
    初期化されていない GPU に synchronize を投げると、そこで落ちる。
    """
    model = tmp_path / "model"
    model.mkdir()
    calls: dict[str, object] = {}

    class Pipeline:
        @classmethod
        def from_pretrained(cls, path, **kwargs):
            calls["pipeline"] = (path, kwargs)
            return cls()

        def to(self, device):
            calls["to"] = device

        def enable_model_cpu_offload(self):
            calls["offload"] = True

        def set_progress_bar_config(self, **kwargs):
            calls["progress"] = kwargs

    def forbidden():
        raise AssertionError("host placement must not touch the GPU")

    fake_torch = SimpleNamespace(
        bfloat16=object(),
        cuda=SimpleNamespace(synchronize=forbidden, empty_cache=forbidden),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "diffusers", SimpleNamespace(Flux2KleinPipeline=Pipeline))

    adapter = DiffusersFlux2KleinAdapter(model, device_mode="cpu", disable_mmap=False)
    adapter.load()

    assert calls["to"] == "cpu"
    assert "offload" not in calls
    assert "device_map" not in calls["pipeline"][1]
    assert adapter.torch_device == "cpu"
