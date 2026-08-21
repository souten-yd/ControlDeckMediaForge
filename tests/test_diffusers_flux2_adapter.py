from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from mediaforge.image_edit import validate_strict_edit
from mediaforge.outpaint import validate_outpaint
from worker_packs.image.adapters import ImageEditRequest
from worker_packs.image.adapters.diffusers_flux2 import DiffusersFlux2KleinAdapter


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
        def __call__(self, **kwargs):
            calls["pipeline"] = kwargs
            return SimpleNamespace(images=[Image.new("RGBA", (kwargs["width"], kwargs["height"]), "orange")])

    fake_torch = SimpleNamespace(
        Generator=Generator,
        cuda=SimpleNamespace(synchronize=lambda: None, empty_cache=lambda: None),
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    adapter = DiffusersFlux2KleinAdapter(model, device_mode="direct_device_map")
    adapter.pipeline = Pipeline()

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
    pipeline_call = calls["pipeline"]
    assert pipeline_call["image"].size == (256, 256)
    assert pipeline_call["width"] == 256 and pipeline_call["height"] == 256
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
