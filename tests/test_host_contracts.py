from __future__ import annotations

import asyncio
import json
import time

from fastapi.testclient import TestClient

from mediaforge.host.files import require_grant_id
from mediaforge.asset_placement import ProjectAssetPlacement, placement_filename
from mediaforge.host.client import HostIdentity
from mediaforge.host.jobs import HostExecution, HostJobReporter, ProgressGate
from pathlib import Path

from mediaforge.host.resources import fake_image_request, image_model_request
from mediaforge.models import ModelDescriptor, ModelState

ROOT = Path(__file__).parents[1]
BACKEND = ROOT / "backend" / "mediaforge"


def test_fake_lease_request_has_complete_vram_and_runtime_estimate():
    payload = fake_image_request("job_123", runtime_sec=12.5)
    assert "owner" not in payload
    assert payload["estimated_runtime_sec"] == 12.5
    assert payload["vram"]["confidence"] == "low"
    assert set(payload["vram"]) == {
        "resident_bytes", "execution_peak_bytes", "cold_load_peak_bytes", "headroom_bytes", "confidence",
    }


def test_measured_image_lease_preserves_all_vram_dimensions():
    model = ModelDescriptor(
        model_id="owner/model",
        family="test",
        version="1",
        revision="a" * 40,
        weights_hash="sha256:" + "b" * 64,
        license="Apache-2.0",
        runtime_adapter="test",
        capabilities=("image.text_to_image",),
        hardware_backends=("rocm",),
        state=ModelState.AVAILABLE,
        policy_rank={"auto": 1},
        required_files=("config.json",),
        weights=(),
        installed=True,
        healthy=True,
        local_path=Path("/model"),
        resident_vram_bytes=11,
        execution_peak_vram_bytes=22,
        cold_load_peak_vram_bytes=33,
        headroom_vram_bytes=44,
        measured_runtime_sec=55.5,
    )
    payload = image_model_request("job_123", model, workload_class="workflow")

    assert payload["vram"] == {
        "resident_bytes": 11,
        "execution_peak_bytes": 22,
        "cold_load_peak_bytes": 33,
        "headroom_bytes": 44,
        "confidence": "measured",
    }
    assert payload["estimated_runtime_sec"] == 55.5
    assert payload["class"] == "workflow"
    assert payload["residency_key"] == "mediaforge:owner/model:" + "a" * 40


def test_bootstrap_image_lease_does_not_claim_measured_confidence():
    model = ModelDescriptor(
        model_id="owner/model",
        family="test",
        version="1",
        revision="a" * 40,
        weights_hash="sha256:" + "b" * 64,
        license="Apache-2.0",
        runtime_adapter="test",
        capabilities=("image.text_to_image",),
        hardware_backends=("rocm",),
        state=ModelState.AVAILABLE,
        policy_rank={"auto": 1},
        required_files=("config.json",),
        weights=(),
        resident_vram_bytes=0,
        execution_peak_vram_bytes=30,
        cold_load_peak_vram_bytes=30,
        headroom_vram_bytes=2,
        measured_runtime_sec=1200,
        measurement_confidence="low",
    )

    assert image_model_request("job_123", model)["vram"]["confidence"] == "low"


def test_host_progress_gate_is_monotonic_and_limited_to_two_hz():
    gate = ProgressGate()
    assert gate.accept(progress=0.1, phase="starting", now=1.0)
    assert not gate.accept(progress=0.2, phase="generating", now=1.2)
    assert not gate.accept(progress=0.2, phase="generating", now=1.5)
    assert gate.accept(progress=0.2, phase="generating", now=1.66)
    assert not gate.accept(progress=0.1, phase="generating", now=2.0)
    assert gate.accept(progress=1.0, phase="complete", terminal=True, now=2.01)


def test_host_reporter_suppresses_identical_waiting_progress():
    class Client:
        def __init__(self) -> None:
            self.payloads: list[dict[str, object]] = []

        async def update_job(self, _identity, _job_id, payload):
            self.payloads.append(payload)

    async def scenario() -> list[dict[str, object]]:
        client = Client()
        reporter = HostJobReporter(
            client,  # type: ignore[arg-type]
            HostExecution(
                identity=HostIdentity(
                    authorization="Bearer test",
                    addon_id="media-forge",
                    subject="7",
                    expires_at=2_000_000_000,
                    granted_capabilities=frozenset({"jobs.write"}),
                ),
                host_job_id="host-job",
                workload_class="batch",
                owns_terminal=True,
            ),
        )
        assert await reporter.progress("waiting_resource", 0.03, wait_reason="device_busy")
        reporter.gate.last_sent_at = 0
        assert not await reporter.progress("waiting_resource", 0.03, wait_reason="device_busy")
        assert await reporter.progress("waiting_resource", 0.03, wait_reason="yielding")
        return client.payloads

    payloads = asyncio.run(scenario())
    assert [payload.get("wait_reason") for payload in payloads] == ["device_busy", "yielding"]


def test_forced_host_progress_waits_instead_of_bypassing_two_hz_limit():
    class Client:
        def __init__(self) -> None:
            self.sent_at: list[float] = []

        async def update_job(self, _identity, _job_id, _payload):
            self.sent_at.append(time.monotonic())

    async def scenario() -> list[float]:
        client = Client()
        reporter = HostJobReporter(
            client,  # type: ignore[arg-type]
            HostExecution(
                identity=HostIdentity(
                    authorization="Bearer test",
                    addon_id="media-forge",
                    subject="7",
                    expires_at=2_000_000_000,
                    granted_capabilities=frozenset({"jobs.write"}),
                ),
                host_job_id="host-job",
                workload_class="batch",
                owns_terminal=True,
            ),
        )
        assert await reporter.progress("first", 0.1, force=True)
        assert await reporter.progress("second", 0.2, force=True)
        return client.sent_at

    sent_at = asyncio.run(scenario())
    assert len(sent_at) == 2
    assert sent_at[1] - sent_at[0] >= 0.5


def test_attached_job_final_progress_may_repeat_the_last_waiting_state():
    class Client:
        def __init__(self) -> None:
            self.payloads: list[dict[str, object]] = []

        async def update_job(self, _identity, _job_id, payload):
            self.payloads.append(payload)

    async def scenario() -> list[dict[str, object]]:
        client = Client()
        reporter = HostJobReporter(
            client,  # type: ignore[arg-type]
            HostExecution(
                identity=HostIdentity(
                    authorization="Bearer test",
                    addon_id="media-forge",
                    subject="job:host-job",
                    expires_at=2_000_000_000,
                    granted_capabilities=frozenset({"jobs.write"}),
                ),
                host_job_id="host-job",
                workload_class="interactive",
                owns_terminal=False,
            ),
        )
        assert await reporter.progress("waiting_resource", 0.03)
        reporter.gate.last_sent_at = 0
        await reporter.finish_attached(phase="waiting_resource", progress=0.03)
        return client.payloads

    assert len(asyncio.run(scenario())) == 2


def test_file_boundary_accepts_only_opaque_grant_ids():
    assert require_grant_id("grant:abc-123") == "grant:abc-123"
    for value in ("/tmp/file.png", "file.png", "asset:abc", "grant:/tmp/file.png"):
        try:
            require_grant_id(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted unscoped value: {value}")


def test_project_asset_placement_accepts_only_safe_matching_filenames():
    value = ProjectAssetPlacement.model_validate({
        "asset_id": "asset_" + "a" * 32,
        "output_grant_id": "grant:opaque-1",
    })
    assert placement_filename(
        requested=value.filename,
        suggested="generated.png",
        mime_type="image/png",
    ) == "generated.png"
    assert placement_filename(
        requested="kizuna-m5-companion.zip",
        suggested="generated.zip",
        mime_type="application/zip",
    ) == "kizuna-m5-companion.zip"
    assert placement_filename(
        requested="project-ready.glb",
        suggested="generated.glb",
        mime_type="model/gltf-binary",
    ) == "project-ready.glb"
    for filename in ("../outside.png", "nested/output.png", "nested\\output.png", "output.jpg"):
        try:
            request = ProjectAssetPlacement.model_validate({
                "asset_id": value.asset_id,
                "output_grant_id": value.output_grant_id,
                "filename": filename,
            })
            placement_filename(
                requested=request.filename,
                suggested="generated.png",
                mime_type="image/png",
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted unsafe or mismatched filename: {filename}")


# ControlDeck の SetupChecklistItem は extra="forbid" である。1 つでも知らない
# 鍵があると health 全体が ValidationError になり、service が正常に応答して
# いるのに「接続できません」と出る。実際にそうなった: 実行可否の判定に要る
# gpu_memory.total_bytes を、そのまま Host へ渡していた。
HOST_SETUP_ITEM_FIELDS = {"id", "label", "state", "detail", "message", "action"}


def test_health_setup_items_carry_only_host_contract_fields(tmp_path: Path, monkeypatch):
    from mediaforge.app import create_app
    from conftest import fake_settings

    settings = fake_settings(tmp_path)
    environment = {
        "status": "healthy",
        "setup": [
            {"id": "core_env", "label": "Packaged core", "state": "ok"},
            {
                "id": "gpu_memory",
                "label": "GPU memory",
                "state": "ok",
                # ローカルには残す。実行可否の判定がこの数値を読む。
                "total_bytes": 34_208_743_424,
                "detail": "34208743424 bytes total",
            },
        ],
    }
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    status_file = settings.data_dir / "environment-status.json"
    status_file.write_text(json.dumps(environment), encoding="utf-8")
    monkeypatch.setenv("MEDIA_FORGE_ENV_STATUS_FILE", str(status_file))

    app = create_app(settings)
    with TestClient(app) as client:
        payload = client.get("/health").json()

    items = payload["setup"]
    assert any(item["id"] == "gpu_memory" for item in items), "setup が読み込まれていない"
    for item in items:
        extra = set(item) - HOST_SETUP_ITEM_FIELDS
        assert not extra, f"Host 契約に無い鍵を出している: {sorted(extra)}"
    # 数値そのものは失わない。文章側に残す。
    memory = next(item for item in items if item["id"] == "gpu_memory")
    assert "34208743424" in memory["detail"]


def test_the_local_environment_file_still_carries_the_number_for_runnability():
    """Host へ出さないことと、手元で持たないことは別。VRAM 量は判定に要る。"""
    entrypoint = (ROOT / "scripts" / "bundle_entrypoint.py").read_text(encoding="utf-8")
    assert '"total_bytes": int(gpu.get("total_memory_bytes") or 0)' in entrypoint
    app_source = (BACKEND / "app.py").read_text(encoding="utf-8")
    assert 'item.get("total_bytes")' in app_source, "実行可否の判定が数値を読まなくなっている"


def _descriptor(runtime_adapter: str, host_resident_bytes: int | None = None) -> ModelDescriptor:
    return ModelDescriptor(
        model_id="owner/model",
        family="test",
        version="1",
        revision="a" * 40,
        weights_hash="sha256:" + "b" * 64,
        license="Apache-2.0",
        runtime_adapter=runtime_adapter,
        capabilities=("image.text_to_image",),
        hardware_backends=("rocm",),
        state=ModelState.AVAILABLE,
        policy_rank={"auto": 1},
        required_files=("config.json",),
        weights=(),
        installed=True,
        healthy=True,
        local_path=Path("/model"),
        resident_vram_bytes=11,
        execution_peak_vram_bytes=22,
        cold_load_peak_vram_bytes=33,
        headroom_vram_bytes=44,
        measured_runtime_sec=55.5,
        host_resident_bytes=host_resident_bytes,
    )


def test_a_cpu_capable_model_offers_ram_as_a_second_place():
    """順序が「空いていれば VRAM、無ければ RAM」を表す。

    host は opt-in で、挙げなければ VRAM だけが候補になる
    （docs/design-ai-resource-broker.md §0）。
    """
    payload = image_model_request("job_123", _descriptor("diffusers.flux2-klein"))

    assert payload["preferred_devices"] == ["gpu0", "host"]


def test_a_gpu_only_model_does_not_ask_for_ram():
    """VRAM を確保しないことが host 配置の条件である。守れない駆動系は要求しない。"""
    payload = image_model_request("job_123", _descriptor("native.stable-diffusion-cpp-flux2"))

    assert payload["preferred_devices"] == []


def test_generation_shares_the_device_with_the_llm():
    """exclusive だと、LLM が載っている間は VRAM の空きに関係なく断られる。"""
    assert image_model_request("job_123", _descriptor("diffusers.sdxl"))["compute_mode"] == "shared-safe"
    assert fake_image_request("job_123", runtime_sec=1)["compute_mode"] == "shared-safe"


def test_ram_placement_declares_what_it_actually_costs():
    """VRAM の見積りを RAM に当てない。

    vram は device_map で段階的に載せるときの GPU 側ピークで、RAM 配置の実態とは
    別物である。実測: FLUX.2 Klein 4B は vram 31.1GB の申告に対し CPU 実行の RSS が
    18.8GB（1024x1024/4歩、2026-09-04）。VRAM の数字を当てると、30GB の機械では
    host が永久に grant されない。
    """
    payload = image_model_request(
        "job_123", _descriptor("diffusers.flux2-klein", host_resident_bytes=19_209_719_808)
    )

    assert payload["host_bytes"] == 19_209_719_808 + payload["vram"]["headroom_bytes"]


def test_an_unmeasured_model_does_not_guess_what_ram_costs():
    """測っていない量を送らない。小さすぎれば OOM、大きすぎれば載らない。"""
    payload = image_model_request("job_123", _descriptor("diffusers.flux2-klein"))

    assert "host_bytes" not in payload
    assert payload["preferred_devices"] == ["gpu0", "host"]


def test_a_gpu_only_model_never_declares_a_ram_figure():
    """host を挙げない要求の host_bytes は broker に拒否される。"""
    payload = image_model_request(
        "job_123",
        _descriptor("native.stable-diffusion-cpp-flux2", host_resident_bytes=19_209_719_808),
    )

    assert "host_bytes" not in payload


def test_the_floor_is_not_declared_per_model():
    """モデルごとに下限を宣言しない。

    宣言すると、測っていないモデルは枠を貸してもらえず、測った値が少しでも
    足りなければそのモデルだけ突然使えなくなる。実際 FLUX.2 Klein 4B で 1 枚ぶんの
    実測 8GiB を宣言したところ、連続生成の 2 枚目が OOM した（2026-09-05）。
    必要量は解像度・枚数・参照画像で変わるので、事前に 1 つの数字で言い当てられない。
    """
    from mediaforge.host.resources import MINIMUM_USABLE_VRAM_BYTES

    for adapter in ("diffusers.flux2-klein", "diffusers.sdxl", "diffusers.sdxl-single-file"):
        payload = image_model_request("job_123", _descriptor(adapter))
        assert payload["vram"]["minimum_bytes"] == MINIMUM_USABLE_VRAM_BYTES, adapter


def test_a_gpu_only_model_declares_no_floor():
    """枠を切り詰めて貸せない駆動系に下限は要らない。"""
    payload = image_model_request("job_123", _descriptor("native.stable-diffusion-cpp-flux2"))

    assert "minimum_bytes" not in payload["vram"]
