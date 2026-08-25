from __future__ import annotations

import asyncio
import contextlib
from dataclasses import replace
from pathlib import Path

import pytest

from mediaforge.domain import JobRequest
from mediaforge.host.ai import HostAIReleaseResult
from mediaforge.host.client import HostIdentity
from mediaforge.host.jobs import HostExecution
from mediaforge.jobs import JobManager, OOM_FLOOR_INCREMENT_BYTES, WorkerFailure
from mediaforge.models import ModelDescriptor, ModelState
from mediaforge.store import Store


def measured_model() -> ModelDescriptor:
    return ModelDescriptor(
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
        resident_vram_bytes=100,
        execution_peak_vram_bytes=200,
        cold_load_peak_vram_bytes=300,
        headroom_vram_bytes=50,
        measured_runtime_sec=12.5,
    )


def test_oom_raises_next_broker_admission_floor(tmp_path: Path):
    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)
    model = measured_model()
    job = store.create_job(JobRequest(operation="image.generate", intent="test"))
    execution = HostExecution(
        identity=HostIdentity(
            authorization="Bearer test",
            addon_id="media-forge",
            subject="user:test",
            expires_at=2**31,
            granted_capabilities=frozenset({"jobs.write", "resources.acquire"}),
        ),
        host_job_id="host-job",
        workload_class="interactive",
        owns_terminal=True,
    )

    manager._record_oom(model)
    request = manager._resource_request(job, execution, model, 1.0)

    expected_total = model.measured_vram_bytes + OOM_FLOOR_INCREMENT_BYTES
    assert request["vram"]["execution_peak_bytes"] + request["vram"]["headroom_bytes"] == expected_total
    assert request["vram"]["cold_load_peak_bytes"] + request["vram"]["headroom_bytes"] == expected_total
    assert request["vram"]["confidence"] == "measured"


def test_real_model_rejects_dimensions_outside_measured_envelope_before_lease(tmp_path: Path):
    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)
    model = measured_model()
    model = replace(model, max_width=1024, max_height=1024, max_pixels=1048576)
    job = store.create_job(JobRequest(
        operation="image.generate",
        intent="test",
        constraints={"width": 1536, "height": 512},
    ))

    with pytest.raises(WorkerFailure) as exc:
        manager._validate_generation_limits(job, model)

    assert exc.value.code == "resource_limit"


# ── AI ターンの明示解放（G6 S3） ─────────────────────────────────────────


def host_execution() -> HostExecution:
    return HostExecution(
        identity=HostIdentity(
            authorization="Bearer test",
            addon_id="media-forge",
            subject="user:test",
            expires_at=2**31,
            granted_capabilities=frozenset({"jobs.write", "resources.acquire", "ai.inference"}),
        ),
        host_job_id="host-job",
        workload_class="interactive",
        owns_terminal=True,
    )


class RecordingGateway:
    def __init__(self, result: HostAIReleaseResult):
        self.result = result
        self.calls = 0
        self.required_bytes: list[int] = []

    async def release(self, _identity, *, required_bytes: int = 0) -> HostAIReleaseResult:
        self.calls += 1
        self.required_bytes.append(required_bytes)
        return self.result


def test_ai_turn_is_declared_finished_before_generation(tmp_path: Path):
    """生成 lease を取る前に AI ターンを閉じること。順序が逆だと deadlock する。"""
    store = Store(tmp_path / "data")
    store.initialize()
    gateway = RecordingGateway(HostAIReleaseResult(True, "released", 17_000_000_000))
    manager = JobManager(store, ai_gateway=gateway)
    job = store.create_job(JobRequest(operation="image.generate", intent="test"))

    asyncio.run(manager._release_host_ai(job, host_execution(), None))

    assert gateway.calls == 1
    assert store.get_job(job.id).phase == "release_ai"


def test_a_refused_release_is_asked_only_once(tmp_path: Path):
    """chat / OpenCode を飢えさせないため、リトライループを作らない。"""
    store = Store(tmp_path / "data")
    store.initialize()
    gateway = RecordingGateway(HostAIReleaseResult(False, "opencode_active"))
    manager = JobManager(store, ai_gateway=gateway)
    job = store.create_job(JobRequest(operation="image.generate", intent="test"))

    asyncio.run(manager._release_host_ai(job, host_execution(), None))

    assert gateway.calls == 1


def test_a_refused_release_names_the_retained_residency_on_vram_failure(tmp_path: Path):
    """匿名の OOM ではなく、なぜ空きが取れなかったのかを返すこと。"""
    store = Store(tmp_path / "data")
    store.initialize()
    gateway = RecordingGateway(HostAIReleaseResult(False, "opencode_active"))
    manager = JobManager(store, ai_gateway=gateway)
    job = store.create_job(JobRequest(operation="image.generate", intent="test"))
    asyncio.run(manager._release_host_ai(job, host_execution(), None))

    failure = manager._admission_failure(job.id, "insufficient_vram")

    assert failure.code == "host_ai_residency_retained"
    assert "opencode_active" in failure.message


def test_a_non_vram_admission_failure_does_not_blame_the_ai_residency(tmp_path: Path):
    """VRAM 以外の受理失敗に AI 常駐の話を混ぜない。"""
    store = Store(tmp_path / "data")
    store.initialize()
    gateway = RecordingGateway(HostAIReleaseResult(False, "opencode_active"))
    manager = JobManager(store, ai_gateway=gateway)
    job = store.create_job(JobRequest(operation="image.generate", intent="test"))
    asyncio.run(manager._release_host_ai(job, host_execution(), None))

    failure = manager._admission_failure(job.id, "policy_denied")

    assert failure.code == "resource_unavailable"


def test_a_successful_release_does_not_blame_the_ai_residency(tmp_path: Path):
    """解放できたのに VRAM が足りないなら、それは AI 常駐のせいではない。"""
    store = Store(tmp_path / "data")
    store.initialize()
    gateway = RecordingGateway(HostAIReleaseResult(True, "released", 17_000_000_000))
    manager = JobManager(store, ai_gateway=gateway)
    job = store.create_job(JobRequest(operation="image.generate", intent="test"))
    asyncio.run(manager._release_host_ai(job, host_execution(), None))

    failure = manager._admission_failure(job.id, "insufficient_vram")

    assert failure.code == "resource_unavailable"


def test_a_release_failure_never_stops_generation(tmp_path: Path):
    """解放要求そのものの失敗で生成を止めない。broker の受理判断に委ねる。"""
    store = Store(tmp_path / "data")
    store.initialize()

    class BrokenGateway:
        async def release(self, _identity):
            raise RuntimeError("host is unreachable")

    manager = JobManager(store, ai_gateway=BrokenGateway())
    job = store.create_job(JobRequest(operation="image.generate", intent="test"))

    asyncio.run(manager._release_host_ai(job, host_execution(), None))

    assert manager._admission_failure(job.id, "insufficient_vram").code == "resource_unavailable"


def test_the_release_says_how_much_the_turn_needs_afterwards(tmp_path: Path):
    """伝えないと Host は「LLM を降ろした」で終わる。実測: それでも 1.16GB の
    embedding が残り、33.35GB を要る画像モデルが 34.2GB のカードに入らなかった。"""
    from mediaforge.models import ModelDescriptor

    store = Store(tmp_path / "data")
    store.initialize()
    gateway = RecordingGateway(HostAIReleaseResult(True, "released", 17_000_000_000))
    manager = JobManager(store, ai_gateway=gateway)
    job = store.create_job(JobRequest(operation="image.generate", intent="test"))
    selected = next(
        item for item in manager.registry.all() if item.measured_vram_bytes
    ) if hasattr(manager, "registry") else None

    asyncio.run(manager._release_host_ai(job, host_execution(), None, selected))

    assert gateway.calls == 1
    if selected is not None:
        assert gateway.required_bytes[0] == selected.measured_vram_bytes
    # selected が無い経路（起動前など）では 0 を送る。嘘の数字は送らない。
    asyncio.run(manager._release_host_ai(job, host_execution(), None, None))
    assert gateway.required_bytes[-1] == 0


# ── 準備をサーバ側に置く ────────────────────────────────────────────────
#
# 演出と検証は画面が順番に呼び、途中結果はそのページだけが持っていた。VLM と
# LLM を 1 回ずつ使った後にタブを閉じると、それが失われる。Host の「処理中」
# 警告はその事実を言っていた。job の記録はブラウザより長く生きるので、同じ
# 手順を phase として持たせる。

def test_direction_and_validation_run_inside_the_job(tmp_path: Path):
    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)

    seen: dict[str, object] = {}

    async def direct(job, spec, mode):
        seen["mode"] = mode
        return {"creative_spec": {**spec, "domain": "anime"}, "plan": None}

    async def validate(job, request, spec, plan):
        seen["spec"] = spec
        return request.model_copy(update={"intent": f"{request.intent}／整えた"})

    manager.creative_director = direct
    manager.creative_validate = validate
    job = store.create_job(JobRequest(
        operation="image.generate",
        intent="青い目のライオン",
        constraints={"creative_spec": {"domain": "auto"}, "director_mode": "refine"},
    ))

    prepared = asyncio.run(manager._prepare_creative(job, None))

    assert seen["mode"] == "refine"
    assert seen["spec"]["domain"] == "anime", "演出の結果が検証へ渡っていない"
    # 書き換えた要求は保存される。保存しないと、ブラウザを閉じた時点で消える。
    assert prepared.request.intent.endswith("／整えた")
    assert store.get_job(job.id).request.intent.endswith("／整えた")


def test_a_request_without_a_creative_spec_is_left_alone(tmp_path: Path):
    """画面が既に用意して送ってくる経路（構図・差分）はそのまま通す。"""
    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)
    manager.creative_validate = None
    job = store.create_job(JobRequest(operation="image.generate", intent="そのまま"))

    assert asyncio.run(manager._prepare_creative(job, None)).request.intent == "そのまま"


def test_a_failed_direction_does_not_stop_the_job(tmp_path: Path):
    """演出が立たなくても生成は続ける。飾りのために本体を落とさない。"""
    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)

    async def boom(job, spec, mode):
        raise RuntimeError("director unavailable")

    async def validate(job, request, spec, plan):
        return request

    manager.creative_director = boom
    manager.creative_validate = validate
    job = store.create_job(JobRequest(
        operation="image.generate", intent="続ける",
        constraints={"creative_spec": {"domain": "auto"}, "director_mode": "refine"},
    ))

    assert asyncio.run(manager._prepare_creative(job, None)).request.intent == "続ける"


def test_routing_sees_the_models_the_picker_offers(tmp_path: Path):
    """自作モデルは shipped manifest に居ない。routing がそれを知らないと、
    選べる状態にしてあるのに「使えるモデルがありません」で落ちる（実測）。"""
    store = Store(tmp_path / "data")
    store.initialize()
    asked: dict[str, int] = {"calls": 0}

    def manifests():
        asked["calls"] += 1
        return [], []

    manager = JobManager(
        store,
        model_manifest=Path(__file__).parents[1] / "worker_packs/image/models.json",
        model_catalog_manifest=Path(__file__).parents[1] / "worker_packs/image/catalog.json",
        hf_home=tmp_path / "hf",
        model_store_root=tmp_path / "models",
        extra_manifests=manifests,
    )
    job = store.create_job(JobRequest(operation="image.generate", intent="test"))
    # 何も導入されていないので選べないのは正しい。見たいのは、選ぶ前に
    # 自作モデルの一覧まで読みに行っているかである。
    with contextlib.suppress(WorkerFailure):
        manager._select_real_model(job)

    assert asked["calls"] == 1, "routing が自作モデルの一覧を読んでいない"
