from __future__ import annotations

from array import array
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import qwen_image_probe as probe

REVISION = "790c92633540aa0cb11d9abf19eb46d861714758"
SCRIPT = Path(__file__).parents[1] / "scripts/qwen_image_probe.py"


def arguments(*extra: str) -> list[str]:
    return ["--model-id", "Qwen/Qwen-Image-2.1", "--revision", REVISION,
            "--device", "cpu", "--dtype", "bf16", "--quantization", "none",
            "--prompt", "a red cube", "--seed", "42", "--repeat", "3",
            "--width", "64", "--height", "64", "--steps", "2", *extra]


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
    for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY",
                "HF_HUB_DISABLE_IMPLICIT_TOKEN"):
        monkeypatch.setenv(key, os.environ.get(key, "0"))
    root = tmp_path / "snapshot"
    root.mkdir()
    (root / "model_index.json").write_text('{"_class_name":"QwenImage21Pipeline"}')
    for component in ("text_encoder", "transformer", "vae"):
        directory = root / component
        directory.mkdir()
        (directory / "config.json").write_text("{}")
        (directory / "model.safetensors").write_bytes(b"fixture")
    state = SimpleNamespace(root=root, calls=[], events=[], varying=False, alpha=255,
                            nan=False, latent_finite=True, decoded_finite=True,
                            load_failure=False, gpu=False, blas="fixture-auto")

    def preferred_blas_library(value: str | None = None) -> str:
        if value is not None:
            state.blas = value
            state.events.append("blas:" + value)
        return state.blas

    def snapshot(model_id: str, **kwargs: Any) -> str:
        assert model_id == "Qwen/Qwen-Image-2.1"
        assert kwargs == {"revision": REVISION, "local_files_only": True}
        assert os.environ["HF_HUB_OFFLINE"] == "1"
        return str(root)

    class Generator:
        def __init__(self, device: str) -> None:
            self.device = device

        def manual_seed(self, seed: int) -> Generator:
            self.seed = seed
            return self

    class Frame:
        dtype = "float32"

        def __init__(self, width: int, height: int, color: float) -> None:
            self.shape = (height, width, 4)
            self.values = array("f", [float("nan") if state.nan else color, 0, 0, state.alpha / 255])
            self.values *= width * height

        def tobytes(self, order: str) -> bytes:
            assert order == "C"
            return self.values.tobytes()

    class Pipeline:
        def __init__(self) -> None:
            self.vae = SimpleNamespace(decode=lambda *args, **kwargs: (SimpleNamespace(decoded=True),))

        @classmethod
        def from_pretrained(cls, path: Path, **kwargs: Any) -> Pipeline:
            assert path == root
            assert kwargs["torch_dtype"] == "bf16" and kwargs["local_files_only"] is True
            if state.load_failure:
                raise RuntimeError("fixture load failure")
            state.events.append("pipeline")
            return cls()

        def set_progress_bar_config(self, **kwargs: Any) -> None:
            assert kwargs == {"disable": True}

        def to(self, device: str) -> None:
            state.events.append(device)

        def enable_model_cpu_offload(self) -> None:
            state.events.append("offload")

        def __call__(self, **kwargs: Any) -> Any:
            assert kwargs["output_type"] == "np"
            state.calls.append(kwargs)
            for index in range(kwargs["num_inference_steps"]):
                kwargs["callback_on_step_end"](self, index, index, {"latents": object()})
            self.vae.decode(None, return_dict=False)
            color = len(state.calls) / 10 if state.varying else .5
            return SimpleNamespace(images=[Frame(kwargs["width"], kwargs["height"], color)])

    class Component:
        @classmethod
        def from_pretrained(cls, path: Path, **kwargs: Any) -> Any:
            assert kwargs["local_files_only"] is True
            state.events.append("load:" + path.name)
            return SimpleNamespace(name=path.name)

    torch = SimpleNamespace(bfloat16="bf16", float16="fp16", Generator=Generator, version=SimpleNamespace(hip="fixture"),
        backends=SimpleNamespace(cuda=SimpleNamespace(preferred_blas_library=preferred_blas_library)),
        isfinite=lambda value: SimpleNamespace(all=lambda: SimpleNamespace(
            item=lambda: state.decoded_finite if getattr(value, "decoded", False) else state.latent_finite)),
        cuda=SimpleNamespace(is_available=lambda: state.gpu, get_device_name=lambda _: "fixture GPU", reset_peak_memory_stats=lambda: None,
            synchronize=lambda: None, max_memory_allocated=lambda: 1234, max_memory_reserved=lambda: 2345))
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=snapshot))
    monkeypatch.setitem(sys.modules, "diffusers", SimpleNamespace(
        QwenImage21Pipeline=Pipeline, QwenImage21Transformer2DModel=Component))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(Qwen3VLForConditionalGeneration=Component))
    monkeypatch.setitem(sys.modules, "optimum", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "optimum.quanto", SimpleNamespace(qint8="int8",
        quantize=lambda model, **kwargs: state.events.append("quantize:" + model.name),
        freeze=lambda model: state.events.append("freeze:" + model.name),
        quantization_map=lambda model: {"linear": {"weights": "qint8"}}))
    return state


def test_repeated_seed_is_preserved_and_different_outputs_fail_repeatability(fake: SimpleNamespace) -> None:
    fake.varying = True
    result = probe.probe(arguments())
    assert result["error"] is None
    assert result["identical_outputs"] is False
    assert len(set(result["output_sha256"])) == 3
    assert [row["generator"].seed for row in fake.calls] == [42, 42, 42]
    assert result["finite_latent_check_count"] == 6
    assert result["finite_decoded_tensor_check_count"] == 3


@pytest.mark.parametrize("alpha,expected", [(255, False), (0, False), (128, True)])
def test_rgba_requires_visible_foreground_and_nonopaque_pixels(fake: SimpleNamespace, alpha: int, expected: bool) -> None:
    fake.alpha = alpha
    result = probe.probe(arguments("--rgba"))
    assert result["error"] is None
    assert result["identical_outputs"] is True
    assert result["has_alpha"] is expected
    assert "RGBA image with transparency" in result["effective_prompt"]
    assert result["numerical_reference_comparison"] == "NOT TESTED"


def test_loading_failure_is_a_result(fake: SimpleNamespace) -> None:
    fake.load_failure = True
    result = probe.probe(arguments())
    assert result["error"]["code"] == "probe_failed"
    assert result["cold_load_sec"] is not None
    assert result["output_sha256"] == []
    assert result["identical_outputs"] is None


def test_gpu_unavailable_is_reported_before_loading(fake: SimpleNamespace) -> None:
    result = probe.probe(arguments("--device", "gpu"))
    assert result["error"]["code"] == "gpu_unavailable"
    assert result["vram_peak_bytes"] is None
    assert fake.events == []


def test_gpu_offload_and_allocator_measurements_are_explicit(fake: SimpleNamespace) -> None:
    fake.gpu = True
    result = probe.probe(arguments("--device", "gpu", "--offload"))
    assert result["error"] is None
    assert fake.events == ["pipeline", "offload"]
    assert result["device_name"] == "fixture GPU"
    assert result["vram_peak_bytes"] == 1234
    assert result["vram_peak_reserved_bytes"] == 2345
    assert all(row["generator"].device == "cuda" for row in fake.calls)


def test_explicit_gpu_blas_is_selected_before_loading_and_recorded(fake: SimpleNamespace) -> None:
    fake.gpu = True
    result = probe.probe(arguments("--device", "gpu", "--blas-library", "cublas"))
    assert result["error"] is None
    assert fake.events == ["blas:cublas", "pipeline", "cuda"]
    assert result["blas_library"] == {"requested": "cublas", "selected": "cublas"}


def test_blas_selection_failure_stops_before_model_loading(fake: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
    fake.gpu = True

    def unavailable(_: str) -> None:
        raise RuntimeError("fixture BLAS unavailable")

    monkeypatch.setattr(sys.modules["torch"].backends.cuda, "preferred_blas_library", unavailable)
    result = probe.probe(arguments("--device", "gpu", "--blas-library", "cublas"))
    assert result["error"]["code"] == "probe_failed"
    assert fake.events == []


def test_cpu_rejects_gpu_blas_selection(fake: SimpleNamespace) -> None:
    result = probe.probe(arguments("--blas-library", "cublas"))
    assert result["error"]["code"] == "invalid_arguments"
    assert fake.events == []


def test_incomplete_shards_are_weights_missing(fake: SimpleNamespace) -> None:
    path = fake.root / "transformer"
    (path / "model.safetensors.index.json").write_text('{"weight_map":{"layer":"absent.safetensors"}}')
    result = probe.probe(arguments())
    assert result["error"]["code"] == "weights_missing"
    assert fake.events == []


def test_nonfinite_decoder_is_not_hidden_by_image_conversion(fake: SimpleNamespace) -> None:
    fake.nan = True
    result = probe.probe(arguments())
    assert result["error"]["code"] == "numerical_nonfinite"
    assert result["output_sha256"] == []


def test_nonfinite_raw_decoder_is_rejected_before_finite_clamped_pixels(fake: SimpleNamespace) -> None:
    fake.decoded_finite = False
    result = probe.probe(arguments())
    assert result["error"]["code"] == "numerical_nonfinite"
    assert "raw VAE" in result["error"]["message"]
    assert result["output_sha256"] == []


def test_nonfinite_latents_stop_inference(fake: SimpleNamespace) -> None:
    fake.latent_finite = False
    assert probe.probe(arguments())["error"]["code"] == "numerical_nonfinite"


def test_int8_is_applied_before_loading_the_next_component(fake: SimpleNamespace) -> None:
    result = probe.probe(arguments("--quantization", "int8"))
    assert result["error"] is None
    assert fake.events == ["load:text_encoder", "quantize:text_encoder", "freeze:text_encoder",
        "load:transformer", "quantize:transformer", "freeze:transformer", "pipeline", "cpu"]
    assert result["quantized_module_counts"] == {"text_encoder": 1, "transformer": 1}
    assert result["vae_quantization"] == "none"


def test_outputs_are_saved_and_existing_evidence_is_preserved(fake: SimpleNamespace, tmp_path: Path) -> None:
    output = tmp_path / "outputs"
    assert probe.probe(arguments("--output-dir", str(output)))["error"] is None
    assert len(list(output.glob("*.png"))) == 3
    receipt = json.loads((output / "probe-result.json").read_text())
    assert receipt["config"]["revision"] == REVISION
    assert len(receipt["output_sha256"]) == 3
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    assert probe.probe(arguments("--output-dir", str(output)))["error"]["code"] == "output_invalid"
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}


@pytest.mark.parametrize("device", ["cpu", "gpu"])
def test_cli_failure_outputs_one_json_even_with_native_stdout(tmp_path: Path, device: str) -> None:
    (tmp_path / "torch.py").write_text("import os\nos.write(1,b'native log\\n')\n"
        "import ctypes\nctypes.CDLL(None).printf(b'buffered native log\\n')\n"
        "from types import SimpleNamespace\ncuda=SimpleNamespace(is_available=lambda:False)\n")
    (tmp_path / "huggingface_hub.py").write_text(
        "def snapshot_download(*args,**kwargs):\n assert kwargs['local_files_only']\n raise FileNotFoundError('fixture missing')\n")
    result = subprocess.run([sys.executable, str(SCRIPT), *arguments("--device", device)],
        env={**os.environ, "PYTHONPATH": str(tmp_path)}, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert len(result.stdout.splitlines()) == 1
    assert value["error"]["code"] == ("gpu_unavailable" if device == "gpu" else "weights_missing")
    assert "native log" in result.stderr


def test_sigterm_produces_canceled_json(tmp_path: Path) -> None:
    (tmp_path / "torch.py").write_text("import sys,time\nprint('ready',file=sys.stderr,flush=True)\ntime.sleep(30)\n")
    process = subprocess.Popen([sys.executable, str(SCRIPT), *arguments()],
        env={**os.environ, "PYTHONPATH": str(tmp_path)}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert process.stderr is not None
        assert process.stderr.readline().strip() == "ready"
        process.terminate()
        stdout, stderr = process.communicate(timeout=10)
        assert process.returncode == 0, stderr
        assert json.loads(stdout)["error"]["code"] == "canceled"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
