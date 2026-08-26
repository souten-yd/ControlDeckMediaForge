from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY

from PIL import Image
import pytest

from worker_packs.video.ffmpeg import probe
from worker_packs.video.wan21_vace_probe import (
    CANDIDATE_REVISION,
    NEGATIVE_PROMPT,
    PRESETS,
    PROMPT,
    SEED,
    _conditioning,
    _encode_frames,
    _invoke_pipeline,
    _load_pipeline,
    _snapshot,
)


def snapshot(tmp_path: Path, *, class_name: str = "WanVACEPipeline") -> Path:
    repository = tmp_path / "models--Wan-AI--Wan2.1-VACE-1.3B-diffusers"
    blobs = repository / "blobs"
    revision = repository / "snapshots" / CANDIDATE_REVISION
    blobs.mkdir(parents=True)
    revision.mkdir(parents=True)
    model_index = blobs / "model-index"
    model_index.write_text(json.dumps({"_class_name": class_name}), encoding="utf-8")
    (revision / "model_index.json").symlink_to(model_index)
    return revision


def test_snapshot_requires_exact_revision_pipeline_and_contained_model_index(tmp_path: Path) -> None:
    valid = snapshot(tmp_path)
    assert _snapshot(valid) == valid.resolve()

    wrong_revision = valid.parent / ("f" * 40)
    wrong_revision.mkdir()
    (wrong_revision / "model_index.json").write_text(
        json.dumps({"_class_name": "WanVACEPipeline"}), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="revision differs"):
        _snapshot(wrong_revision)

    wrong_class = snapshot(tmp_path / "wrong", class_name="OtherPipeline")
    with pytest.raises(ValueError, match="unexpected pipeline"):
        _snapshot(wrong_class)

    escaped = snapshot(tmp_path / "escaped")
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps({"_class_name": "WanVACEPipeline"}), encoding="utf-8")
    (escaped / "model_index.json").unlink()
    (escaped / "model_index.json").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        _snapshot(escaped)


def test_pipeline_load_is_local_only_mixed_dtype_offloaded_and_uses_480p_shift() -> None:
    calls: dict[str, object] = {}

    class Vae:
        @classmethod
        def from_pretrained(cls, snapshot_path: Path, **kwargs: object) -> "Vae":
            calls["vae_snapshot"] = snapshot_path
            calls["vae_load"] = kwargs
            return cls()

        def enable_slicing(self) -> None:
            calls["slicing"] = True

        def enable_tiling(self) -> None:
            calls["tiling"] = True

    class Scheduler:
        @classmethod
        def from_config(cls, config: object, **kwargs: object) -> object:
            calls["scheduler"] = (config, kwargs)
            return "480p-scheduler"

    class Pipeline:
        scheduler: object = SimpleNamespace(config="base-config")

        @classmethod
        def from_pretrained(cls, snapshot_path: Path, **kwargs: object) -> "Pipeline":
            calls["pipeline_snapshot"] = snapshot_path
            calls["pipeline_load"] = kwargs
            instance = cls()
            instance.vae = kwargs["vae"]
            return instance

        def enable_model_cpu_offload(self, *, device: str) -> None:
            calls["offload"] = device

    torch = SimpleNamespace(float32="fp32", bfloat16="bf16")
    path = Path("/trusted/snapshot")
    pipeline = _load_pipeline(path, torch, Vae, Pipeline, Scheduler)

    assert pipeline.scheduler == "480p-scheduler"
    assert calls == {
        "vae_snapshot": path,
        "vae_load": {
            "subfolder": "vae",
            "dtype": "fp32",
            "low_cpu_mem_usage": True,
            "local_files_only": True,
        },
        "pipeline_snapshot": path,
        "pipeline_load": {
            "vae": ANY,
            "dtype": "bf16",
            "low_cpu_mem_usage": True,
            "local_files_only": True,
        },
        "scheduler": ("base-config", {"flow_shift": 3.0}),
        "offload": "cuda:0",
        "slicing": True,
        "tiling": True,
    }


def test_conditioning_locks_first_frame_and_generates_remaining_frames() -> None:
    preset = PRESETS["smoke"]
    video, mask = _conditioning(preset)

    assert len(video) == preset.frames
    assert len(mask) == preset.frames
    assert all(image.size == (preset.width, preset.height) for image in video)
    assert mask[0].getextrema() == (0, 0)
    assert all(image.getextrema() == (255, 255) for image in mask[1:])
    assert video[0].getbbox() is not None


def test_pipeline_call_uses_only_fixed_bounded_i2v_preset() -> None:
    calls: dict[str, object] = {}

    class Generator:
        def __init__(self, *, device: str) -> None:
            calls["generator_device"] = device

        def manual_seed(self, seed: int) -> "Generator":
            calls["seed"] = seed
            return self

    class Pipeline:
        def __call__(self, **kwargs: object) -> SimpleNamespace:
            calls["invoke"] = kwargs
            return SimpleNamespace(frames=[["frame"]])

    preset = PRESETS["candidate-clip"]
    frames = _invoke_pipeline(Pipeline(), SimpleNamespace(Generator=Generator), preset)
    invoke = calls["invoke"]

    assert frames == ["frame"]
    assert calls["generator_device"] == "cuda:0"
    assert calls["seed"] == SEED
    assert isinstance(invoke, dict)
    assert len(invoke.pop("video")) == preset.frames
    assert len(invoke.pop("mask")) == preset.frames
    assert invoke == {
        "prompt": PROMPT,
        "negative_prompt": NEGATIVE_PROMPT,
        "width": 512,
        "height": 320,
        "num_frames": 33,
        "num_inference_steps": 30,
        "guidance_scale": 5.0,
        "generator": ANY,
        "output_type": "pil",
    }


def test_frame_encoder_produces_bounded_h264_and_removes_temporary_frames(tmp_path: Path) -> None:
    preset = PRESETS["smoke"]
    frames = [
        Image.new("RGB", (preset.width, preset.height), (index * 20, 64, 128))
        for index in range(preset.frames)
    ]
    output = tmp_path / "smoke.mp4"

    _encode_frames(frames, output, preset)

    info = probe(output)
    assert info.width == preset.width
    assert info.height == preset.height
    assert info.frame_count == preset.frames
    assert info.frame_rate == 16
    assert info.codec == "h264"
    assert not list(tmp_path.glob("wan21-vace-frames-*"))


def test_frame_encoder_rejects_wrong_count_without_partial_output(tmp_path: Path) -> None:
    output = tmp_path / "smoke.mp4"
    with pytest.raises(RuntimeError, match="frame count"):
        _encode_frames([], output, PRESETS["smoke"])
    assert not output.exists()
