from __future__ import annotations

from pathlib import Path

import pytest

from worker_packs.image.adapters import ImageGenerationResult
from worker_packs.image import worker as image_worker


def payload(model_path: Path, output_dir: Path) -> dict:
    return {
        "model": {
            "id": "owner/model",
            "path": str(model_path),
            "version": "1",
            "weights_hash": "sha256:" + "a" * 64,
            "license": "Apache-2.0",
            "runtime_adapter": "diffusers.flux2-klein",
        },
        "request": {
            "intent": "a blue robot",
            "constraints": {"width": 256, "height": 256, "steps": 4, "seed": 7},
            "output": {"format": "png", "count": 1},
        },
        "worker_output_dir": str(output_dir),
    }


def test_image_worker_rejects_model_and_output_path_escape(monkeypatch, tmp_path):
    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model_root.mkdir()
    work_root.mkdir()
    model = model_root / "model"
    model.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))
    worker = image_worker.ImageWorker()

    with pytest.raises(ValueError, match="model path"):
        worker.handle(payload(outside, work_root / "job" / "outputs"))
    with pytest.raises(ValueError, match="output directory"):
        worker.handle(payload(model, outside / "outputs"))


def test_image_worker_returns_bounded_model_metadata_and_per_output_seed(monkeypatch, tmp_path):
    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model = model_root / "model"
    output_dir = work_root / "job" / "outputs"
    model.mkdir(parents=True)
    output_dir.parent.mkdir(parents=True)
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))

    class Adapter:
        def __init__(self, _path, *, device_mode, disable_mmap):
            assert device_mode == "cpu_offload"
            assert disable_mmap is True
            self.load_sec = 1.25
            self.last_generation_sec = None

        def generate(self, request):
            request.output_path.write_bytes(b"png")
            self.last_generation_sec = 0.5
            return ImageGenerationResult(request.output_path, request.seed)

    monkeypatch.setattr(image_worker, "DiffusersFlux2KleinAdapter", Adapter)
    monkeypatch.setattr(image_worker.importlib.metadata, "version", lambda _name: "test-runtime")
    request = payload(model, output_dir)
    request["model"]["runtime_options"] = {"device_mode": "cpu_offload", "disable_mmap": True}
    request["request"]["output"]["count"] = 2
    result = image_worker.ImageWorker().handle(request)

    assert [item["seed"] for item in result["outputs"]] == [7, 8]
    assert result["model"]["id"] == "owner/model"
    assert "path" not in result["model"]
    assert result["runtime_metrics"] == {
        "load_sec": 1.25,
        "generation_sec": 1.0,
        "device_mode": "cpu_offload",
        "disable_mmap": True,
    }


def test_image_worker_has_no_process_override_and_rejects_unknown_mode(monkeypatch, tmp_path):
    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model_root.mkdir()
    work_root.mkdir()
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))

    worker = image_worker.ImageWorker()
    assert worker.device_mode_override is None
    assert worker.disable_mmap_override is None
    monkeypatch.setenv("MEDIA_FORGE_IMAGE_DEVICE_MODE", "dynamic")
    with pytest.raises(ValueError, match="must be full_device, direct_device_map, or cpu_offload"):
        image_worker.ImageWorker()
    monkeypatch.setenv("MEDIA_FORGE_IMAGE_DEVICE_MODE", "full_device")
    monkeypatch.setenv("MEDIA_FORGE_IMAGE_DISABLE_MMAP", "yes")
    with pytest.raises(ValueError, match="must be 0 or 1"):
        image_worker.ImageWorker()


def test_image_worker_rejects_fractional_and_boolean_numeric_constraints(monkeypatch, tmp_path):
    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model = model_root / "model"
    model.mkdir(parents=True)
    work_root.mkdir()
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))
    worker = image_worker.ImageWorker()

    fractional = payload(model, work_root / "fractional")
    fractional["request"]["constraints"]["width"] = 256.5
    with pytest.raises(ValueError, match="width must be an integer"):
        worker.handle(fractional)
    boolean = payload(model, work_root / "boolean")
    boolean["request"]["constraints"]["seed"] = True
    with pytest.raises(ValueError, match="seed must be an integer"):
        worker.handle(boolean)
