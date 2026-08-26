from __future__ import annotations

import asyncio
from dataclasses import replace
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from mediaforge.host.client import HostIdentity
from mediaforge.model_evaluator import (
    COGVIDEOX2B_COLD_LOAD_PEAK_BYTES,
    COGVIDEOX2B_ESTIMATED_RUNTIME_SEC,
    COGVIDEOX2B_EXECUTION_PEAK_BYTES,
    COGVIDEOX2B_HEADROOM_BYTES,
    COGVIDEOX2B_MODEL_ID,
    COGVIDEOX2B_MODEL_REVISION,
    COGVIDEOX2B_RUNTIME_ADAPTER,
    H3_MODEL_ID,
    H3_RUNTIME_ADAPTER,
    H3_RUNTIME_COMMIT,
    H3ModelEvaluator,
    HUNYUAN_COLD_LOAD_PEAK_BYTES,
    HUNYUAN_CONVERSION_REVISION,
    HUNYUAN_ESTIMATED_RUNTIME_SEC,
    HUNYUAN_EXECUTION_PEAK_BYTES,
    HUNYUAN_HEADROOM_BYTES,
    HUNYUAN_MODEL_ID,
    HUNYUAN_MODEL_REVISION,
    HUNYUAN_RUNTIME_ADAPTER,
    WAN_COLD_LOAD_PEAK_BYTES,
    WAN_ESTIMATED_RUNTIME_SEC,
    WAN_EXECUTION_PEAK_BYTES,
    WAN_HEADROOM_BYTES,
    WAN_MODEL_ID,
    WAN_MODEL_REVISION,
    WAN_RUNTIME_ADAPTER,
)
from mediaforge.models import (
    ModelDescriptor,
    ModelOperationAction,
    ModelOperationError,
    ModelOperationState,
    ModelOwnership,
    ModelState,
)
from mediaforge.models.registry import WeightFile
from mediaforge.store import Store


class FakeHost:
    def __init__(self) -> None:
        self.resource_requests: list[dict[str, Any]] = []
        self.lease_actions: list[str] = []
        self.job_updates: list[dict[str, Any]] = []
        self.cancel_requested = False

    async def create_or_attach_job(self, identity: HostIdentity, *, title: str) -> dict[str, Any]:
        assert title == "Media Forge model evaluation"
        return {"created": True, "job": {"id": "host-evaluation"}}

    async def update_job(
        self,
        identity: HostIdentity,
        host_job_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        assert host_job_id == "host-evaluation"
        self.job_updates.append(payload)
        return {"id": host_job_id}

    async def request_resource(self, identity: HostIdentity, payload: dict[str, Any]) -> dict[str, Any]:
        self.resource_requests.append(payload)
        return {"request_id": "request-evaluation", "state": "granted", "lease_id": "lease-evaluation"}

    async def resource_status(self, identity: HostIdentity, request_id: str) -> dict[str, Any]:
        raise AssertionError("granted request must not be polled")

    async def cancel_resource(self, identity: HostIdentity, request_id: str) -> dict[str, Any]:
        self.lease_actions.append("cancel-request")
        return {"request_id": request_id, "state": "canceled"}

    async def lease_action(self, identity: HostIdentity, lease_id: str, action: str) -> dict[str, Any]:
        assert lease_id == "lease-evaluation"
        self.lease_actions.append(action)
        return {"lease_id": lease_id, "state": action}

    async def refresh_lease_identity(self, identity: HostIdentity, lease_id: str) -> HostIdentity:
        return identity

    async def job_control(self, identity: HostIdentity, host_job_id: str) -> dict[str, Any]:
        return {"cancel_requested": self.cancel_requested}


def identity(*, capabilities: frozenset[str] | None = None) -> HostIdentity:
    return HostIdentity(
        authorization="Bearer test",
        addon_id="media-forge",
        subject="1",
        expires_at=int(time.time()) + 600,
        granted_capabilities=capabilities or frozenset({"jobs.write", "resources.acquire"}),
    )


def descriptor(snapshot: Path) -> ModelDescriptor:
    return ModelDescriptor(
        model_id=H3_MODEL_ID,
        family="minimax-h3",
        version="test",
        revision="d629413c2e5b51b38c453668b75ca3b06ca92703",
        weights_hash="sha256:" + "1" * 64,
        license="test",
        runtime_adapter=H3_RUNTIME_ADAPTER,
        capabilities=("video.text_to_video",),
        hardware_backends=("rocm",),
        state=ModelState.EXPERIMENTAL,
        policy_rank={"auto": 0},
        required_files=("LICENSE",),
        weights=(WeightFile(path="model.gguf", size_bytes=1, sha256="2" * 64),),
        installed=True,
        healthy=False,
        local_path=snapshot,
        ownership=ModelOwnership.MANAGED,
        measurement_confidence="low",
    )


def runtime_root(tmp_path: Path) -> Path:
    root = tmp_path / "runtime"
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "HEAD").write_text(H3_RUNTIME_COMMIT + "\n", encoding="utf-8")
    executable = root / "build" / "bin" / "sd-cli"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o700)
    return root


def command(delay_sec: float, *, return_code: int = 0):
    def build(_model: ModelDescriptor, output: Path, _executable: Path) -> list[str]:
        script = (
            "import pathlib,sys,time; "
            "time.sleep(float(sys.argv[2])); "
            f"pathlib.Path(sys.argv[1]).write_bytes(b'bounded-video'); raise SystemExit({return_code})"
        )
        return [sys.executable, "-c", script, str(output), str(delay_sec)]

    return build


def validator(path: Path) -> dict[str, Any]:
    assert path.read_bytes() == b"bounded-video"
    return {
        "width": 640,
        "height": 384,
        "duration_sec": 0.21,
        "audio_present": True,
    }


async def wait_terminal(store: Store, operation_id: str, timeout: float = 5) -> Any:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        operation = store.get_model_operation(operation_id)
        if operation.state in {
            ModelOperationState.READY,
            ModelOperationState.FAILED,
            ModelOperationState.CANCELED,
        }:
            return operation
        await asyncio.sleep(0.02)
    raise AssertionError("model evaluation did not finish")


def evaluator(tmp_path: Path, host: FakeHost, *, delay: float, return_code: int = 0) -> H3ModelEvaluator:
    store = Store(tmp_path / "data")
    store.initialize()
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    model = descriptor(snapshot)
    return H3ModelEvaluator(
        store,
        host,  # type: ignore[arg-type]
        model_manifest=tmp_path / "unused-models.json",
        catalog_manifest=tmp_path / "unused-catalog.json",
        model_store_root=tmp_path / "models",
        hf_home=tmp_path / "hf",
        runtime_root=runtime_root(tmp_path),
        lease_renew_sec=0.05,
        timeout_sec=10,
        command_builder=command(delay, return_code=return_code),
        artifact_validator=validator,
        vram_probe=lambda: 1024,
        model_resolver=lambda model_id: model if model_id == H3_MODEL_ID else (_ for _ in ()).throw(KeyError()),
    )


def test_evaluation_holds_renews_and_releases_host_lease(tmp_path: Path) -> None:
    async def scenario() -> tuple[FakeHost, Any]:
        host = FakeHost()
        service = evaluator(tmp_path, host, delay=1.1)
        await service.start()
        try:
            operation = service.evaluate(H3_MODEL_ID, identity())
            finished = await wait_terminal(service.store, operation.id)
            return host, finished
        finally:
            await service.stop()

    host, finished = asyncio.run(scenario())

    assert finished.action == ModelOperationAction.EVALUATE
    assert finished.state == ModelOperationState.READY
    assert finished.host_job_id == "host-evaluation"
    assert finished.result is not None
    assert finished.result["output_bytes"] == len(b"bounded-video")
    assert finished.result["media"]["audio_present"] is True
    assert host.lease_actions[0] == "activate"
    assert "renew" in host.lease_actions
    assert host.lease_actions[-1] == "release"
    request = host.resource_requests[0]
    assert request["estimated_runtime_sec"] == 1800.0
    assert request["vram"] == {
        "resident_bytes": 0,
        "execution_peak_bytes": 30_000_000_000,
        "cold_load_peak_bytes": 32_000_000_000,
        "headroom_bytes": 1024 * 1024 * 1024,
        "confidence": "low",
    }
    assert host.job_updates[-1]["status"] == "succeeded"


def test_evaluation_cancel_terminates_process_and_releases_lease(tmp_path: Path) -> None:
    async def scenario() -> tuple[FakeHost, Any, str, bool]:
        host = FakeHost()
        service = evaluator(tmp_path, host, delay=30)
        await service.start()
        try:
            operation = service.evaluate(H3_MODEL_ID, identity())
            deadline = asyncio.get_running_loop().time() + 3
            while service.store.get_model_operation(operation.id).state != ModelOperationState.GENERATING:
                assert asyncio.get_running_loop().time() < deadline
                await asyncio.sleep(0.02)
            service.store.request_model_operation_cancel(operation.id)
            finished = await wait_terminal(service.store, operation.id)
            return host, finished, operation.id, operation.id in service._processes
        finally:
            await service.stop()

    host, finished, operation_id, process_remained = asyncio.run(scenario())

    assert finished.state == ModelOperationState.CANCELED
    assert not process_remained, operation_id
    assert host.lease_actions[-1] == "release"
    assert host.job_updates[-1]["status"] == "canceled"


def test_evaluation_native_failure_is_isolated_and_releases_lease(tmp_path: Path) -> None:
    async def scenario() -> tuple[FakeHost, Any]:
        host = FakeHost()
        service = evaluator(tmp_path, host, delay=0.05, return_code=7)
        await service.start()
        try:
            operation = service.evaluate(H3_MODEL_ID, identity())
            finished = await wait_terminal(service.store, operation.id)
            return host, finished
        finally:
            await service.stop()

    host, finished = asyncio.run(scenario())

    assert finished.state == ModelOperationState.FAILED
    assert finished.error_code == "model_evaluation_failed"
    assert host.lease_actions[-1] == "release"
    assert host.job_updates[-1]["status"] == "failed"


def test_evaluation_requires_host_capabilities_before_operation(tmp_path: Path) -> None:
    service = evaluator(tmp_path, FakeHost(), delay=0)
    with pytest.raises(ModelOperationError) as raised:
        service.evaluate(H3_MODEL_ID, identity(capabilities=frozenset({"jobs.write"})))
    assert raised.value.code == "host_capability_not_granted"
    assert service.store.list_model_operations() == []


def test_active_evaluation_fails_closed_after_service_restart(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    operation = store.create_model_operation(H3_MODEL_ID, ModelOperationAction.EVALUATE, bytes_total=0)
    store.update_model_operation(operation.id, state=ModelOperationState.GENERATING, host_job_id="host-evaluation")

    restarted = Store(tmp_path / "data")
    restarted.initialize()
    failed = restarted.get_model_operation(operation.id)
    assert failed.state == ModelOperationState.FAILED
    assert failed.error_code == "host_context_lost"
    assert restarted.resumable_model_operation_ids() == []


def test_real_validator_uses_bounded_ffprobe_array_and_requires_audio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "smoke.webm"
    artifact.write_bytes(b"video")
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs):
        calls.append(args)
        assert kwargs == {"check": False, "capture_output": True, "text": True, "timeout": 30}
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps({
                "streams": [
                    {"codec_type": "video", "width": 640, "height": 384,
                     "codec_name": "vp9", "avg_frame_rate": "24/1"},
                    {"codec_type": "audio", "codec_name": "opus", "channels": 2},
                ],
                "format": {"duration": "0.21"},
            }),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = H3ModelEvaluator._validate_artifact(artifact)
    assert calls == [[
        "/usr/bin/ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(artifact),
    ]]
    assert result == {
        "width": 640,
        "height": 384,
        "video_codec": "vp9",
        "frame_rate": "24/1",
        "duration_sec": 0.21,
        "audio_present": True,
        "audio_codec": "opus",
        "audio_channels": 2,
    }


def test_h3_command_is_fixed_and_uses_mixed_ram_vram_placement(tmp_path: Path) -> None:
    host = FakeHost()
    service = evaluator(tmp_path, host, delay=0)
    repo = tmp_path / "models" / "hub" / "models--unsloth--MiniMax-H3-GGUF"
    snapshot = repo / "snapshots" / ("d" * 40)
    blobs = repo / "blobs"
    snapshot.mkdir(parents=True)
    blobs.mkdir()
    names = [
        "minimax_h3_fl2va_pruned-UD-Q2_K_XL.gguf",
        "qwen3vl_32b_minimax_h3-Q2_K_M.gguf",
        "vae/minimax_h3_video_vae_fp16.safetensors",
        "vae/minimax_h3_audio_vae_fp32.safetensors",
    ]
    weights = []
    for index, name in enumerate(names):
        blob = blobs / str(index)
        blob.write_bytes(bytes([index]))
        link = snapshot / name
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(blob)
        weights.append(WeightFile(path=name, size_bytes=1, sha256=str(index) * 64))
    model = replace(descriptor(snapshot), weights=tuple(weights), local_path=snapshot)
    output = tmp_path / "output.webm"
    command_value = service._command(model, output, Path("/trusted/sd-cli"))

    assert command_value[0] == "/trusted/sd-cli"
    assert command_value.count("--prompt") == 1
    assert "--offload-to-cpu" not in command_value
    backend = command_value[command_value.index("--backend") + 1]
    assert backend == "te=cpu,diffusion=ROCm0,vae=ROCm0"
    assert command_value[command_value.index("--params-backend") + 1] == "te=cpu"
    assert command_value[command_value.index("--video-frames") + 1] == "5"
    assert command_value[command_value.index("--steps") + 1] == "1"
    assert command_value[-1] == str(output)


def test_wan_probe_is_pinned_and_uses_separate_runtime(tmp_path: Path) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    runtime_python = tmp_path / "wan-runtime" / "bin" / "python"
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("", encoding="utf-8")
    native_runtime = runtime_root(tmp_path)
    source = tmp_path / "wan-source"
    source.mkdir()
    service = H3ModelEvaluator(
        store,
        FakeHost(),  # type: ignore[arg-type]
        model_manifest=tmp_path / "models.json",
        catalog_manifest=tmp_path / "catalog.json",
        model_store_root=tmp_path / "models",
        hf_home=tmp_path / "hf",
        runtime_root=native_runtime,
        wan_runtime_python=runtime_python,
        wan_source_root=source,
        lease_renew_sec=1,
        timeout_sec=10,
    )
    model = replace(
        descriptor(snapshot),
        model_id=WAN_MODEL_ID,
        family="wan2.2",
        revision=WAN_MODEL_REVISION,
        runtime_adapter=WAN_RUNTIME_ADAPTER,
    )
    command_value = service._command(model, tmp_path / "smoke.mp4", Path("/unused"))
    assert command_value[0] == str(runtime_python)
    assert command_value[2:4] == ["run", "--snapshot"]
    assert command_value[-2:] == ["--preset", "smoke"]
    request = service._resource_request("host-wan", model)
    assert request["estimated_runtime_sec"] == WAN_ESTIMATED_RUNTIME_SEC
    assert request["vram"] == {
        "resident_bytes": 0,
        "execution_peak_bytes": WAN_EXECUTION_PEAK_BYTES,
        "cold_load_peak_bytes": WAN_COLD_LOAD_PEAK_BYTES,
        "headroom_bytes": WAN_HEADROOM_BYTES,
        "confidence": "measured",
    }
    assert str(source) in service._runtime_env(model)["PYTHONPATH"]


def test_wan_validator_accepts_one_frame_video_without_audio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "smoke.mp4"
    artifact.write_bytes(b"video")

    def fake_run(args: list[str], **kwargs):
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps({
                "streams": [{
                    "codec_type": "video", "width": 256, "height": 256,
                    "codec_name": "h264", "avg_frame_rate": "24/1", "nb_frames": "1",
                }],
                "format": {"duration": "0.042"},
            }),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    service = evaluator(tmp_path, FakeHost(), delay=0)
    assert service._validate_wan_artifact(artifact) == {
        "width": 256,
        "height": 256,
        "video_codec": "h264",
        "frame_rate": "24/1",
        "duration_sec": 0.042,
        "audio_present": False,
    }


def test_wan_failed_probe_removes_sensitive_and_partial_outputs(tmp_path: Path) -> None:
    service = evaluator(tmp_path, FakeHost(), delay=0)
    operation = service.store.create_model_operation(
        WAN_MODEL_ID,
        ModelOperationAction.EVALUATE,
        bytes_total=0,
    )
    service.store.update_model_operation(operation.id, state=ModelOperationState.FAILED)
    output_dir = service.output_root / operation.id
    frames = output_dir / "frames"
    frames.mkdir(parents=True)
    (output_dir / "prompt.safetensors").write_bytes(b"prompt")
    (output_dir / "smoke.mp4").write_bytes(b"partial")
    (output_dir / "probe.json").write_text("{}", encoding="utf-8")
    (frames / "000000.png").write_bytes(b"frame")

    service._cleanup_probe_intermediates(operation.id)

    assert sorted(item.name for item in output_dir.iterdir()) == []


def test_hunyuan_probe_is_hidden_until_exact_external_snapshot_is_configured(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    runtime_python = tmp_path / "hunyuan-runtime" / "bin" / "python"
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("", encoding="utf-8")
    native_runtime = runtime_root(tmp_path)
    model = replace(
        descriptor(tmp_path / "unused-official-snapshot"),
        model_id=HUNYUAN_MODEL_ID,
        family="hunyuan-video-1.5",
        revision=HUNYUAN_MODEL_REVISION,
        runtime_adapter=HUNYUAN_RUNTIME_ADAPTER,
        installed=False,
        local_path=None,
    )

    unavailable = H3ModelEvaluator(
        store,
        FakeHost(),  # type: ignore[arg-type]
        model_manifest=tmp_path / "models.json",
        catalog_manifest=tmp_path / "catalog.json",
        model_store_root=tmp_path / "models",
        hf_home=tmp_path / "hf",
        runtime_root=native_runtime,
        hunyuan_runtime_python=runtime_python,
        lease_renew_sec=1,
        timeout_sec=10,
        model_resolver=lambda model_id: model if model_id == HUNYUAN_MODEL_ID else (_ for _ in ()).throw(
            ModelOperationError("model_not_found", "not configured")
        ),
    )
    assert unavailable.available_model_ids() == []

    repository = tmp_path / "models--hunyuanvideo-community--candidate"
    blobs = repository / "blobs"
    snapshot = repository / "snapshots" / HUNYUAN_CONVERSION_REVISION
    blobs.mkdir(parents=True)
    snapshot.mkdir(parents=True)
    model_index = blobs / "model-index"
    model_index.write_text(
        json.dumps({"_class_name": "HunyuanVideo15Pipeline"}),
        encoding="utf-8",
    )
    (snapshot / "model_index.json").symlink_to(model_index)
    available = H3ModelEvaluator(
        store,
        FakeHost(),  # type: ignore[arg-type]
        model_manifest=tmp_path / "models.json",
        catalog_manifest=tmp_path / "catalog.json",
        model_store_root=tmp_path / "models",
        hf_home=tmp_path / "hf",
        runtime_root=native_runtime,
        hunyuan_runtime_python=runtime_python,
        hunyuan_snapshot_root=snapshot,
        hunyuan_evaluation_preset="candidate-clip",
        lease_renew_sec=1,
        timeout_sec=10,
        model_resolver=lambda model_id: model if model_id == HUNYUAN_MODEL_ID else (_ for _ in ()).throw(
            ModelOperationError("model_not_found", "not configured")
        ),
    )
    assert available.available_model_ids() == [HUNYUAN_MODEL_ID]
    command_value = available._command(model, tmp_path / "smoke.mp4", Path("/unused"))
    assert command_value[0] == str(runtime_python)
    assert command_value[2:4] == ["run", "--snapshot"]
    assert command_value[-2:] == ["--preset", "candidate-clip"]
    request = available._resource_request("host-hunyuan", model)
    assert request["estimated_runtime_sec"] == HUNYUAN_ESTIMATED_RUNTIME_SEC
    assert request["vram"] == {
        "resident_bytes": 0,
        "execution_peak_bytes": HUNYUAN_EXECUTION_PEAK_BYTES,
        "cold_load_peak_bytes": HUNYUAN_COLD_LOAD_PEAK_BYTES,
        "headroom_bytes": HUNYUAN_HEADROOM_BYTES,
        "confidence": "low",
    }
    available.wan_source_root = tmp_path / "unrelated-wan-source"
    assert str(available.wan_source_root) not in available._runtime_env(model).get("PYTHONPATH", "")


def test_hunyuan_validator_requires_exact_silent_h264_bounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "smoke.mp4"
    artifact.write_bytes(b"video")
    codec = "h264"

    def fake_run(args: list[str], **kwargs):
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps({
                "streams": [{
                    "codec_type": "video",
                    "width": 256,
                    "height": 256,
                    "codec_name": codec,
                    "avg_frame_rate": "24/1",
                    "nb_frames": "5",
                }],
                "format": {"duration": "0.209", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
            }),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    service = evaluator(tmp_path, FakeHost(), delay=0)
    assert service._validate_hunyuan_artifact(artifact) == {
        "width": 256,
        "height": 256,
        "video_codec": "h264",
        "frame_rate": "24/1",
        "duration_sec": 0.209,
        "audio_present": False,
    }

    codec = "vp9"
    with pytest.raises(ModelOperationError, match="encoding differs"):
        service._validate_hunyuan_artifact(artifact)


def test_cogvideox2b_probe_is_hidden_until_complete_exact_snapshot_is_configured(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "data")
    store.initialize()
    runtime_python = tmp_path / "cog-runtime" / "bin" / "python"
    runtime_python.parent.mkdir(parents=True)
    runtime_python.write_text("", encoding="utf-8")
    model = replace(
        descriptor(tmp_path / "unused"),
        model_id=COGVIDEOX2B_MODEL_ID,
        family="cogvideox",
        revision=COGVIDEOX2B_MODEL_REVISION,
        runtime_adapter=COGVIDEOX2B_RUNTIME_ADAPTER,
        required_files=("LICENSE", "model_index.json"),
        weights=(WeightFile(path="transformer/model.safetensors", size_bytes=1, sha256="3" * 64),),
        installed=False,
        local_path=None,
        ownership=ModelOwnership.EXTERNAL,
    )
    repository = tmp_path / "models--zai-org--CogVideoX-2b"
    snapshot = repository / "snapshots" / COGVIDEOX2B_MODEL_REVISION
    snapshot.mkdir(parents=True)
    (snapshot / "model_index.json").write_text(
        json.dumps({"_class_name": "CogVideoXPipeline"}), encoding="utf-8"
    )
    (snapshot / "LICENSE").write_text("Apache-2.0", encoding="utf-8")

    unavailable = H3ModelEvaluator(
        store,
        FakeHost(),  # type: ignore[arg-type]
        model_manifest=tmp_path / "models.json",
        catalog_manifest=tmp_path / "catalog.json",
        model_store_root=tmp_path / "models",
        hf_home=tmp_path / "hf",
        runtime_root=runtime_root(tmp_path),
        cogvideox2b_runtime_python=runtime_python,
        cogvideox2b_snapshot_root=snapshot,
        lease_renew_sec=1,
        timeout_sec=10,
        model_resolver=lambda model_id: model if model_id == COGVIDEOX2B_MODEL_ID else (_ for _ in ()).throw(
            ModelOperationError("model_not_found", "not configured")
        ),
    )
    assert unavailable.available_model_ids() == []

    weight = snapshot / "transformer" / "model.safetensors"
    weight.parent.mkdir()
    weight.write_bytes(b"x")
    available = H3ModelEvaluator(
        store,
        FakeHost(),  # type: ignore[arg-type]
        model_manifest=tmp_path / "models.json",
        catalog_manifest=tmp_path / "catalog.json",
        model_store_root=tmp_path / "models",
        hf_home=tmp_path / "hf",
        runtime_root=runtime_root(tmp_path / "available"),
        cogvideox2b_runtime_python=runtime_python,
        cogvideox2b_snapshot_root=snapshot,
        cogvideox2b_evaluation_preset="official-clip",
        lease_renew_sec=1,
        timeout_sec=10,
        model_resolver=lambda model_id: model if model_id == COGVIDEOX2B_MODEL_ID else (_ for _ in ()).throw(
            ModelOperationError("model_not_found", "not configured")
        ),
    )
    assert available.available_model_ids() == [COGVIDEOX2B_MODEL_ID]
    command_value = available._command(model, tmp_path / "smoke.mp4", Path("/unused"))
    assert command_value[0] == str(runtime_python)
    assert command_value[2:4] == ["run", "--snapshot"]
    assert command_value[-2:] == ["--preset", "official-clip"]
    request = available._resource_request("host-cog", model)
    assert request["estimated_runtime_sec"] == COGVIDEOX2B_ESTIMATED_RUNTIME_SEC
    assert request["vram"] == {
        "resident_bytes": 0,
        "execution_peak_bytes": COGVIDEOX2B_EXECUTION_PEAK_BYTES,
        "cold_load_peak_bytes": COGVIDEOX2B_COLD_LOAD_PEAK_BYTES,
        "headroom_bytes": COGVIDEOX2B_HEADROOM_BYTES,
        "confidence": "low",
    }


def test_cogvideox2b_validator_requires_exact_silent_h264_bounds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "smoke.mp4"
    artifact.write_bytes(b"video")
    frame_count = "8"

    def fake_run(args: list[str], **kwargs):
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps({
                "streams": [{
                    "codec_type": "video",
                    "width": 720,
                    "height": 480,
                    "codec_name": "h264",
                    "avg_frame_rate": "8/1",
                    "nb_frames": frame_count,
                }],
                "format": {"duration": "0.625", "format_name": "mov,mp4,m4a,3gp,3g2,mj2"},
            }),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    service = evaluator(tmp_path, FakeHost(), delay=0)
    assert service._validate_cogvideox2b_artifact(artifact) == {
        "width": 720,
        "height": 480,
        "video_codec": "h264",
        "frame_rate": "8/1",
        "duration_sec": 0.625,
        "audio_present": False,
    }

    frame_count = "4"
    with pytest.raises(ModelOperationError, match="bounds differ"):
        service._validate_cogvideox2b_artifact(artifact)
