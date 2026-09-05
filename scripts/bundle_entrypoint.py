from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


RUNTIME_REQUIREMENTS = "runtimes/rocm-torch/requirements.txt"
MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"
MODEL_REVISION = "e7b7dc27f91deacad38e78976d1f2b499d76a294"
MODEL_DOWNLOAD_ESTIMATE_BYTES = 15_988_901_735
RUNTIME_REQUIRED_FREE_BYTES = 8_589_934_592
MODEL_REQUIRED_FREE_BYTES = 21_474_836_480


def _dispatch_internal_worker() -> int | None:
    """Run the one core-owned worker when this executable is its frozen Python.

    Source installs launch ``sys.executable -m mediaforge.workers.fake``. In a
    PyInstaller build ``sys.executable`` is this CLI, not a general Python
    interpreter, so accepting only this exact internal module preserves that
    process boundary without turning the packaged CLI into an arbitrary module
    runner.
    """
    if sys.argv[1:] != ["-m", "mediaforge.workers.fake"]:
        return None
    from mediaforge.workers.fake import main as fake_worker_main

    return fake_worker_main()


def _managed_path(variable: str) -> Path:
    value = os.environ.get(variable)
    if not value:
        raise RuntimeError(f"{variable} is required")
    path = Path(value).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def _runtime_current(runtime: Path, requirements: Path) -> bool:
    python = runtime / ".venv" / "bin" / "python"
    stamp = runtime / ".venv" / ".req-stamp"
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    if not python.is_file() or not stamp.is_file() or stamp.read_text(encoding="ascii").strip() != digest:
        return False
    checked = subprocess.run(
        [str(python), "-c", "import torch, diffusers, transformers, accelerate"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60, check=False,
    )
    return checked.returncode == 0


def _ensure_runtime(feature_data: Path, cache: Path, requirements: Path) -> tuple[Path, bool]:
    runtime = feature_data / "runtimes" / "rocm-torch"
    runtime.mkdir(parents=True, exist_ok=True)
    python = runtime / ".venv" / "bin" / "python"
    if _runtime_current(runtime, requirements):
        return python, True
    venv = runtime / ".venv"
    if venv.exists():
        shutil.rmtree(venv)
    system_python = shutil.which("python3")
    if not system_python:
        raise RuntimeError("python3 is required to provision the image runtime")
    version = subprocess.run(
        [system_python, "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"],
        timeout=10, check=False,
    )
    if version.returncode != 0:
        raise RuntimeError("Python 3.11 or newer is required to provision the image runtime")
    subprocess.run([system_python, "-m", "venv", str(venv)], timeout=300, check=True)
    environment = {**os.environ, "PIP_CACHE_DIR": str(cache / "pip")}
    subprocess.run(
        [str(venv / "bin" / "pip"), "install", "--progress-bar", "on", "-r", str(requirements)],
        env=environment, timeout=3600, check=True,
    )
    (venv / ".req-stamp").write_text(hashlib.sha256(requirements.read_bytes()).hexdigest() + "\n", encoding="ascii")
    if not _runtime_current(runtime, requirements):
        raise RuntimeError("provisioned image runtime failed its import check")
    return python, False


def _verify_gpu(python: Path) -> dict[str, object]:
    program = """\
import json, torch
if not torch.cuda.is_available(): raise SystemExit('torch.cuda.is_available() is false')
torch.cuda.set_device(0)
x = torch.arange(4096, device='cuda', dtype=torch.float32)
if float((x * 2).sum().item()) != 16773120.0: raise SystemExit('GPU tensor result mismatch')
p = torch.cuda.get_device_properties(0)
free, total = torch.cuda.mem_get_info(0)
print(json.dumps({'torch_version': torch.__version__, 'hip_version': torch.version.hip,
 'device': torch.cuda.get_device_name(0), 'gcn_arch': getattr(p, 'gcnArchName', 'unknown'),
 'free_memory_bytes': int(free), 'total_memory_bytes': int(total)}))
"""
    result = subprocess.run([str(python), "-c", program], capture_output=True, text=True, timeout=120, check=True)
    return json.loads(result.stdout)


def _model_installed(cache: Path) -> bool:
    from mediaforge.models import ModelRegistry

    manifest = _resource_root() / "worker_packs" / "image" / "models.json"
    return any(item.model_id == MODEL_ID and item.installed and item.healthy for item in ModelRegistry.load(
        manifest, hf_home=cache / "huggingface"
    ).all())


def _ensure_model(python: Path, cache: Path) -> bool:
    if _model_installed(cache):
        return True
    environment = {**os.environ, "HF_HOME": str(cache / "huggingface")}
    subprocess.run(
        [
            str(python.parent / "hf"), "download", MODEL_ID, "--revision", MODEL_REVISION,
            "--exclude", "flux-2-klein-4b.safetensors", "--max-workers", "4",
        ],
        env=environment, timeout=5400, check=True,
    )
    if not _model_installed(cache):
        raise RuntimeError("downloaded model did not pass the pinned registry checks")
    return False


def _write_environment_status(feature_data: Path, gpu: dict[str, object]) -> None:
    available = shutil.disk_usage(feature_data).free
    payload = {
        "status": "healthy",
        "setup": [
            {"id": "core_env", "label": "Packaged core", "state": "ok"},
            {"id": "rocm_runtime", "label": "Image worker environment", "state": "ok"},
            {
                "id": "gpu",
                "label": "GPU verification",
                "state": "ok",
                "detail": (
                    f"{gpu.get('device', 'GPU')} {gpu.get('gcn_arch', 'unknown')} · "
                    f"torch {gpu.get('torch_version', 'unknown')} · HIP {gpu.get('hip_version', 'unknown')}"
                ),
            },
            {
                "id": "gpu_memory",
                "label": "GPU memory",
                "state": "ok",
                # 実行可否の判定に要る数値。文章の中に埋めると読み取れない。
                "total_bytes": int(gpu.get("total_memory_bytes") or 0),
                "detail": f"{gpu.get('total_memory_bytes', 0)} bytes total",
            },
            {"id": "model_library", "label": "Pinned model library", "state": "ok"},
            {"id": "disk", "label": "Free disk space", "state": "ok", "detail": f"{available} bytes available"},
        ],
    }
    path = feature_data / "environment-status.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def provision() -> dict[str, object]:
    started = time.perf_counter()
    feature_data = _managed_path("CONTROL_DECK_FEATURE_DATA_DIR")
    cache = _managed_path("CONTROL_DECK_SHARED_CACHE_DIR")
    requirements = _resource_root() / RUNTIME_REQUIREMENTS
    if not requirements.is_file():
        raise RuntimeError("bundle runtime requirements are missing")
    lock_path = feature_data / ".provision.lock"
    with lock_path.open("w", encoding="ascii") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        model_present = _model_installed(cache)
        runtime_present = _runtime_current(feature_data / "runtimes" / "rocm-torch", requirements)
        required = (0 if runtime_present else RUNTIME_REQUIRED_FREE_BYTES) + (
            0 if model_present else MODEL_REQUIRED_FREE_BYTES
        )
        if shutil.disk_usage(feature_data).free < required:
            raise RuntimeError(f"insufficient disk space; {required} bytes are required")
        python, runtime_reused = _ensure_runtime(feature_data, cache, requirements)
        gpu = _verify_gpu(python)
        model_reused = _ensure_model(python, cache)
        _write_environment_status(feature_data, gpu)
    return {
        "status": "ok",
        "runtime_reused": runtime_reused,
        "model_reused": model_reused,
        "model_download_estimate_bytes": MODEL_DOWNLOAD_ESTIMATE_BYTES,
        "elapsed_sec": time.perf_counter() - started,
        "gpu": gpu,
    }


def main() -> int:
    internal = _dispatch_internal_worker()
    if internal is not None:
        return internal
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("doctor", "provision", "serve"))
    args = parser.parse_args()
    if args.operation == "provision":
        print(json.dumps(provision()))
        return 0
    if args.operation == "doctor":
        from mediaforge import __version__
        from mediaforge.app import create_app

        create_app
        print(json.dumps({"status": "ok", "version": __version__, "packaged": bool(getattr(sys, "frozen", False))}))
        return 0

    import uvicorn

    from mediaforge.app import create_app

    port = int(os.environ.get("MEDIA_FORGE_PORT", "9130"))
    uvicorn.run(create_app(), host="127.0.0.1", port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
