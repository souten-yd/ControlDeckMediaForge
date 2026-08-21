from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

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
