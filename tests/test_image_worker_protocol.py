from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

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
            "operation": "image.generate",
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
            self.placement = {
                "component_devices": {"transformer": "cuda:0"},
                "device_maps": {"pipeline": {"": "cuda"}},
                "offload_hooks": [],
                "non_gpu_devices": {},
                "non_gpu_map_targets": [],
            }

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
        "placement": {
            "component_devices": {"transformer": "cuda:0"},
            "device_maps": {"pipeline": {"": "cuda"}},
            "offload_hooks": [],
            "non_gpu_devices": {},
            "non_gpu_map_targets": [],
        },
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


def test_image_worker_rejects_edit_source_and_mask_path_escape(monkeypatch, tmp_path):
    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model = model_root / "model"
    model.mkdir(parents=True)
    work_root.mkdir()
    outside = tmp_path / "outside.png"
    Image.new("RGBA", (256, 256), "white").save(outside, format="PNG")
    inside = work_root / "inside.png"
    Image.new("RGBA", (256, 256), "black").save(inside, format="PNG")
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))
    worker = image_worker.ImageWorker()

    source_escape = payload(model, work_root / "source-escape")
    source_escape["request"]["operation"] = "image.edit"
    source_escape["request"]["constraints"]["strict_edit"] = True
    source_escape["worker_inputs"] = {"source_path": str(outside), "mask_path": str(inside)}
    with pytest.raises(ValueError, match="source image is outside"):
        worker.handle(source_escape)

    mask_escape = payload(model, work_root / "mask-escape")
    mask_escape["request"]["operation"] = "image.edit"
    mask_escape["request"]["constraints"]["strict_edit"] = True
    mask_escape["worker_inputs"] = {"source_path": str(inside), "mask_path": str(outside)}
    with pytest.raises(ValueError, match="edit mask is outside"):
        worker.handle(mask_escape)

    reference_escape = payload(model, work_root / "reference-escape")
    reference_escape["request"]["operation"] = "image.edit"
    reference_escape["request"]["constraints"].update({
        "strict_edit": False,
        "edit_mode": "multi_reference",
    })
    reference_escape["worker_inputs"] = {
        "source_path": str(inside),
        "reference_paths": [str(outside)],
    }
    with pytest.raises(ValueError, match="reference image is outside"):
        worker.handle(reference_escape)


def test_every_routable_model_has_an_adapter_the_worker_implements():
    """カタログが名乗る runtime_adapter と、worker が実装している名前が
    食い違っていた。"diffusers.stable-diffusion" という誰も宣言しない名前で
    実装され、カタログの "diffusers.sdxl" は実装が無いまま並んでいた。

    experimental は測っていないという表明なので、まだ実装が無くてよい。
    available は「これで作れる」という表明なので、無いと嘘になる。
    """
    import json

    root = Path(__file__).parents[1]
    manifest = json.loads(
        (root / "worker_packs/image/models.json").read_text(encoding="utf-8")
    )
    implemented = set(image_worker.ADAPTERS)
    routable = {
        model["model_id"]: model["runtime_adapter"]
        for model in manifest["models"]
        if model.get("state") == "available"
    }
    assert routable, "available なモデルが 1 件も無い"
    missing = {
        model_id: adapter
        for model_id, adapter in routable.items()
        if adapter not in implemented
    }
    assert not missing, f"実装の無い adapter を available として出している: {missing}"


def test_the_worker_refuses_an_adapter_it_does_not_implement(tmp_path: Path, monkeypatch):
    """実装の無い adapter は、静かに何かで代用せず、その場で落ちる。"""
    model_root = tmp_path / "models"
    model = model_root / "model"
    model.mkdir(parents=True)
    work_root = tmp_path / "work"
    (work_root / "job" / "outputs").mkdir(parents=True)
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))
    body = payload(model, work_root / "job" / "outputs")
    body["model"]["runtime_adapter"] = "diffusers.sdxl-single-file"
    assert "diffusers.sdxl-single-file" not in image_worker.ADAPTERS
    with pytest.raises(ValueError, match="unsupported"):
        image_worker.ImageWorker().handle(body)


def test_the_sd_adapter_asks_for_the_variant_that_is_on_disk(tmp_path: Path):
    """実機で判明: カタログは fp16 の variant だけを落とす。variant を渡さないと
    diffusers は model.safetensors を探し、落としていないファイルが無いと言って
    落ちる。variant を持たない普通の repository は従来どおり動く必要がある。"""
    from worker_packs.image.adapters.diffusers_sd import DiffusersStableDiffusionAdapter

    plain = tmp_path / "plain"
    (plain / "unet").mkdir(parents=True)
    (plain / "unet" / "diffusion_pytorch_model.safetensors").write_bytes(b"x")
    assert DiffusersStableDiffusionAdapter(plain)._detect_variant() is None

    fp16 = tmp_path / "fp16"
    (fp16 / "unet").mkdir(parents=True)
    (fp16 / "unet" / "diffusion_pytorch_model.fp16.safetensors").write_bytes(b"x")
    assert DiffusersStableDiffusionAdapter(fp16)._detect_variant() == "fp16"
