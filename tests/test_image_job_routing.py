from __future__ import annotations

import hashlib
import asyncio
import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from mediaforge.domain import JobRequest
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


def test_generation_does_not_unload_the_language_model(tmp_path: Path):
    """画像 1 枚のために、使っている最中の LLM を降ろさせない。

    broker は VRAM が空いていなければ host（システムRAM）を割り当てるので、
    場所を空けてもらう必要が無くなった（design-ai-resource-broker.md §0）。
    以前は生成の前に毎回 ControlDeck へ AI ターンの終了を宣言していた。
    """
    assert not hasattr(JobManager, "_release_host_ai")
    assert "ai_gateway" not in inspect.signature(JobManager.__init__).parameters


def test_admission_failure_names_the_broker_reason(tmp_path: Path):
    failure = JobManager._admission_failure("insufficient_vram")

    assert failure.code == "resource_unavailable"
    assert "insufficient_vram" in failure.message


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


def installed_custom_model(root: Path, model_id: str, revision: str) -> tuple[dict, dict]:
    """自作モデルが 1 つ導入済みで、実測済みという状態を作る。

    registry は snapshot の中身まで見る（重みは blob への symlink で、名前が
    digest と一致すること）。そこを省いて「導入済み」と言い張ると、routing が
    実際に見ているものとは別のものを試すことになる。
    """
    repo = root / "hub" / ("models--" + model_id.replace("/", "--"))
    weight = b"weights"
    digest = hashlib.sha256(weight).hexdigest()
    (repo / "blobs").mkdir(parents=True)
    (repo / "blobs" / digest).write_bytes(weight)
    snapshot = repo / "snapshots" / revision
    snapshot.mkdir(parents=True)
    (repo / "blobs" / ("f" * 64)).write_text("{}", encoding="utf-8")
    (snapshot / "model.safetensors").symlink_to(repo / "blobs" / digest)
    (snapshot / "model_index.json").symlink_to(repo / "blobs" / ("f" * 64))
    registry = {
        "model_id": model_id,
        "family": "custom",
        "version": "1",
        "revision": revision,
        "weights_hash": "sha256:" + "e" * 64,
        "license": "Apache-2.0",
        "runtime_adapter": "diffusers.sdxl",
        "capabilities": ["image.text_to_image"],
        "hardware_backends": ["rocm", "cuda"],
        "state": "available",
        "measurement_confidence": "measured",
        "policy_rank": {"auto": 1},
        "required_files": ["model_index.json"],
        "weights": [
            {"path": "model.safetensors", "size_bytes": len(weight), "sha256": digest}
        ],
        "measurements": {
            "resident_vram_bytes": 0,
            "execution_peak_vram_bytes": 1024,
            "cold_load_peak_vram_bytes": 1024,
            "headroom_vram_bytes": 1024,
            "measured_runtime_sec": 1.0,
        },
    }
    catalog = {
        "model_id": model_id,
        "display_name": model_id,
        "domains": ["general"],
        "media_types": ["image"],
        "description": "利用者が追加したモデル。",
        "approx_download_bytes": len(weight),
        "source": {"kind": "huggingface", "repo_id": model_id, "revision": revision},
        "ownership": "managed",
        "supports_lora": False,
        "max_references": 0,
        "reference_roles": [],
        "supports_reference_strength": False,
        "recommended_profiles": [],
        "gated": False,
        "license_notice": "テスト用の記載。",
    }
    return registry, catalog


def test_routing_offers_the_model_the_picker_offers(tmp_path: Path):
    """自作モデルは shipped manifest に居ない。routing がそれを知らないと、
    選べる状態にしてあるのに「使えるモデルがありません」で落ちる（実測）。"""
    store = Store(tmp_path / "data")
    store.initialize()
    model_store = tmp_path / "models"
    registry, catalog = installed_custom_model(model_store, "owner/model", "d" * 40)
    asked: dict[str, int] = {"calls": 0}

    def manifests():
        asked["calls"] += 1
        # 追加分と、この機械で測った値。読む側は 1 か所で受け取る。
        return [registry], [catalog], {}

    manager = JobManager(
        store,
        model_manifest=Path(__file__).parents[1] / "worker_packs/image/models.json",
        model_catalog_manifest=Path(__file__).parents[1] / "worker_packs/image/catalog.json",
        hf_home=tmp_path / "hf",
        model_store_root=model_store,
        extra_manifests=manifests,
    )
    job = store.create_job(JobRequest(operation="image.generate", intent="test"))

    selected = manager._select_real_model(job)

    assert asked["calls"] == 1, "routing が自作モデルの一覧を読んでいない"
    assert selected.model_id == "owner/model"


def test_routing_without_the_extra_models_finds_nothing(tmp_path: Path):
    """一覧を読まなければ「使えるモデルがありません」に戻る、を固定する。

    上のテストだけだと、routing が extras を読まずに別の理由で通っても
    気づけない。読まない側の結果を並べて初めて、読んでいることの証拠になる。
    """
    store = Store(tmp_path / "data")
    store.initialize()
    model_store = tmp_path / "models"
    installed_custom_model(model_store, "owner/model", "d" * 40)

    manager = JobManager(
        store,
        model_manifest=Path(__file__).parents[1] / "worker_packs/image/models.json",
        model_catalog_manifest=Path(__file__).parents[1] / "worker_packs/image/catalog.json",
        hf_home=tmp_path / "hf",
        model_store_root=model_store,
        extra_manifests=lambda: ([], [], {}),
    )
    job = store.create_job(JobRequest(operation="image.generate", intent="test"))

    with pytest.raises(WorkerFailure) as failure:
        manager._select_real_model(job)

    assert failure.value.code == "capability_unavailable"
