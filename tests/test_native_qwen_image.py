from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from mediaforge.models.adapters import runtime_installed, with_runtime_availability
from mediaforge.routing import ModelRouteError, route_model
from worker_packs.image import worker as image_worker
from worker_packs.image.adapters import ImageGenerationRequest, NativeQwenImage21Adapter


@pytest.fixture
def native_setup(tmp_path: Path, monkeypatch):
    runtime = tmp_path / "runtime"
    executable = runtime / "build/bin/sd-cli"
    executable.parent.mkdir(parents=True)
    executable.write_text(
        f"#!{sys.executable}\n"
        "import sys\nfrom PIL import Image\n"
        "if '--list-devices' in sys.argv:\n"
        " print('Vulkan0\\tTest GPU');sys.exit(0)\n"
        "args=sys.argv\n"
        "im=Image.new('RGBA',(int(args[args.index('-W')+1]),int(args[args.index('-H')+1])),(255,0,0,0))\n"
        "im.putpixel((16,16),(20,100,200,127))\n"
        "im.save(args[args.index('--output')+1])\n"
    )
    executable.chmod(0o700)
    profile = {
        "commit": NativeQwenImage21Adapter.RUNTIME_COMMIT, "backend": "vulkan",
        "vulkan_device_index": 1, "broker_device_id": "gpu0", "device_name": "Test GPU",
        "binary_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
    }
    (runtime / "runtime.json").write_text(json.dumps(profile))
    model = tmp_path / "models/owner/snapshots/revision"
    for _, relative in NativeQwenImage21Adapter.FILES:
        path = model / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test weights")
    monkeypatch.setenv("MEDIA_FORGE_NATIVE_VULKAN_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("MEDIA_FORGE_GPU_DEVICE_ID", "gpu0")
    monkeypatch.setenv("MEDIA_FORGE_VRAM_BUDGET_BYTES", str(20 * 1024**3))
    request = ImageGenerationRequest("test", 256, 256, 4, 42, tmp_path / "work/out.png")
    return runtime, model, request


def test_native_output_preserves_real_alpha(native_setup):
    _, model, request = native_setup
    result = NativeQwenImage21Adapter(model).generate(request)
    with Image.open(result.output_path) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (255, 0, 0, 0)
        assert image.getpixel((16, 16)) == (20, 100, 200, 127)


@pytest.mark.parametrize("fault", ["checksum", "version", "device", "missing_lease"])
def test_native_runtime_fails_closed_before_generation(native_setup, monkeypatch, fault):
    runtime, model, request = native_setup
    profile = json.loads((runtime / "runtime.json").read_text())
    if fault == "checksum":
        profile["binary_sha256"] = "0" * 64
    elif fault == "version":
        profile["commit"] = "0" * 40
    elif fault == "device":
        profile["device_name"] = "another GPU"
    else:
        monkeypatch.delenv("MEDIA_FORGE_GPU_DEVICE_ID")
    (runtime / "runtime.json").write_text(json.dumps(profile))
    with pytest.raises(ValueError):
        NativeQwenImage21Adapter(model).generate(request)
    assert not request.output_path.exists()


def test_native_weights_cannot_escape_repository(native_setup, tmp_path):
    _, model, request = native_setup
    outside = tmp_path / "outside.gguf"
    outside.write_bytes(b"outside")
    weight = model / NativeQwenImage21Adapter.FILES[0][1]
    weight.unlink()
    weight.symlink_to(outside)
    with pytest.raises(ValueError, match="outside"):
        NativeQwenImage21Adapter(model).generate(request)


def test_native_rejects_unaccepted_reference_and_invalid_dimensions(native_setup):
    _, model, request = native_setup
    adapter = NativeQwenImage21Adapter(model)
    with pytest.raises(ValueError, match="reference"):
        adapter.generate(replace(request, reference_paths=(request.output_path,)))
    with pytest.raises(ValueError, match="multiples of 32"):
        adapter.generate(replace(request, width=272))


def test_worker_does_not_initialize_or_report_torch_for_native(native_setup, monkeypatch):
    _, model, request = native_setup
    work = request.output_path.parent
    work.mkdir()
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model.parent.parent))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work))
    def forbidden():
        pytest.fail("Vulkan execution must not use the Torch allocator")
    monkeypatch.setattr(image_worker, "_apply_vram_budget", forbidden)
    monkeypatch.setattr(image_worker, "_own_vram_peak", forbidden)
    result = image_worker.ImageWorker().handle({
        "model": {"id": "test/qwen", "path": str(model), "version": "q8",
                  "weights_hash": "sha256:" + "a" * 64, "license": "test",
                  "runtime_adapter": "native.stable-diffusion-cpp-qwen-image-21"},
        "request": {"operation": "image.generate", "intent": "test",
                    "constraints": {"width": 256, "height": 256, "steps": 4, "seed": 42},
                    "output": {"format": "png", "count": 1}},
        "worker_output_dir": str(work / "outputs"),
    })
    assert result["model"]["runtime_version"] == NativeQwenImage21Adapter.RUNTIME_COMMIT
    assert result["runtime_metrics"]["transformer_quantization"] == "gguf.q8_0"
    assert "peak_vram_bytes" not in result["runtime_metrics"]
    assert result["postprocessing"] == ["alpha.set_opaque"]
    with Image.open(result["outputs"][0]["path"]) as image:
        assert image.getchannel("A").getextrema() == (255, 255)
        assert image.getpixel((16, 16)) == (20, 100, 200, 255)


def test_vulkan_routing_requires_its_backend_and_installed_runtime(native_setup):
    from test_model_routing import descriptor
    runtime, _, _ = native_setup
    model = replace(descriptor("qwen", rank=100, vram=10),
                    runtime_adapter="native.stable-diffusion-cpp-qwen-image-21",
                    hardware_backends=("vulkan",))
    args = dict(capability="image.text_to_image", policy="manual", model_id="qwen", free_vram_bytes=100)
    with pytest.raises(ModelRouteError):
        route_model((model,), hardware_backend="rocm", **args)
    assert route_model((model,), hardware_backend=("rocm", "vulkan"), **args).model_id == "qwen"
    assert runtime_installed(model.runtime_adapter, vulkan_root=runtime)
    missing = with_runtime_availability((model,), vulkan_root=runtime / "missing")
    with pytest.raises(ModelRouteError):
        route_model(missing, hardware_backend=("rocm", "vulkan"), **args)


@pytest.mark.parametrize("policy", ["auto", "fast", "balanced", "quality", "low_vram"])
def test_research_model_is_never_an_automatic_fallback(policy):
    from test_model_routing import descriptor
    model = replace(descriptor("research", rank=0, vram=10), manual_only=True)
    with pytest.raises(ModelRouteError):
        route_model((model,), capability="image.text_to_image", policy=policy,
                    hardware_backend="rocm", free_vram_bytes=100)
    assert route_model((model,), capability="image.text_to_image", policy="manual",
                       model_id="research", hardware_backend="rocm", free_vram_bytes=100).model_id == "research"


def test_native_child_dies_when_owning_worker_is_killed(tmp_path):
    wrapper = Path(image_worker.__file__).parent / "native_child.py"
    marker = tmp_path / "child.pid"
    child_code = "import os,time;from pathlib import Path;Path(" + repr(str(marker)) + ").write_text(str(os.getpid()));time.sleep(30)"
    owner_code = (
        "import os,subprocess,sys;subprocess.run([sys.executable,"
        + repr(str(wrapper)) + ",str(os.getpid()),sys.executable,'-c'," + repr(child_code) + "])"
    )
    owner = subprocess.Popen([sys.executable, "-c", owner_code])
    child_pid = None
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert marker.exists()
        child_pid = int(marker.read_text())
        owner.kill()
        owner.wait(timeout=5)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = Path(f"/proc/{child_pid}/stat")
            try:
                process_state = status.read_text().split()[2]
            except FileNotFoundError:
                break  # Successful exit can remove /proc between two reads.
            if process_state == "Z":
                break
            time.sleep(.02)
        else:
            pytest.fail("native inference survived its owning worker")
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=5)
        if child_pid is not None:
            try:
                os.kill(child_pid, 9)
            except ProcessLookupError:
                pass



def test_native_does_not_claim_resident_weights_between_jobs(tmp_path):
    from mediaforge.jobs import JobManager
    from mediaforge.store import Store
    from test_model_routing import descriptor
    from types import SimpleNamespace
    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)
    model = replace(descriptor("qwen", rank=100, vram=10),
                    runtime_adapter="native.stable-diffusion-cpp-qwen-image-21")
    manager._warm_worker = (SimpleNamespace(returncode=None), None)
    manager._warm_model = model.model_id
    assert manager._warm_holds(model) is False


@pytest.mark.parametrize("size,expected", [
    ((1024, 768), (1024, 768)), ((768, 1024), (768, 1024)),
    ((512, 512), (512, 512)), ((1008, 752), (992, 736)),
])
def test_core_canvas_reaches_native_worker_within_admitted_limits(native_setup, tmp_path, size, expected):
    from mediaforge.domain import JobRequest
    from mediaforge.jobs import JobManager
    from mediaforge.store import Store
    from tests.test_image_evaluation import descriptor

    _, model_path, request = native_setup
    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)
    model = descriptor(default_steps=16, native_width=1024, native_height=1024)
    model = replace(model, runtime_adapter="native.stable-diffusion-cpp-qwen-image-21",
                    max_width=1024, max_height=1024, max_pixels=1024**2)
    job = store.create_job(JobRequest(operation="image.generate", intent="test",
                                    constraints={"width": size[0], "height": size[1]}))
    manager._validate_generation_limits(job, model)
    resolved = manager._resolved_request(job, model)["constraints"]
    native_request = replace(request, width=resolved["width"], height=resolved["height"],
                             steps=resolved["steps"])
    result = NativeQwenImage21Adapter(model_path).generate(native_request)
    with Image.open(result.output_path) as image:
        assert image.size == expected
    assert (job.request.constraints["width"], job.request.constraints["height"]) == size
