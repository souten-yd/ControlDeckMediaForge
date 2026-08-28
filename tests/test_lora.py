"""LoRA は「モデル」ではなく、選んだ checkpoint に載せるもの。

実機で確かめたこと（2026-08-25、AMD Radeon AI PRO R9700）:

* SD 1.5 の LoRA を DreamShaper 8（単一ファイル）に載せて、同じ seed で
  絵が変わった
* SDXL の LoRA を SDXL base 1.0（ディレクトリ形式）に載せて、同じ seed で
  絵が変わった

どちらも adapter の経路が別なので、両方通して初めて「LoRA が動く」と言える。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mediaforge.models.generation_defaults import normalize_base_model


def test_the_two_copies_of_the_family_rule_agree():
    """core は worker pack を import できないので、同じ判断が両側にある。
    ずれると、core が「載せられる」と言ったものを worker が落とす。"""
    from worker_packs.image.adapters.diffusers_single_file import (
        normalize_base_model as worker_side,
    )

    for value in (
        "SD 1.5", "SD 1.5 Hyper", "SDXL 1.0", "Pony", "Illustrious",
        "NoobAI XL", "SD 3.5 Large", "Flux.1 D", "", "なんだこれ",
    ):
        assert normalize_base_model(value) == worker_side(value), value


def test_a_lora_is_never_a_candidate_for_generation():
    """routing は capability で候補を絞る。旗を立てて後から除外する作りだと、
    除外を書き忘れた経路が 1 つでもあれば LoRA が本体として選ばれる。"""
    from mediaforge.models.registry import ModelDescriptor, ModelState, WeightFile
    from mediaforge.routing.router import ModelRouteError, route_model

    lora = ModelDescriptor(
        model_id="civitai/58390", family="custom", version="1", revision="1",
        weights_hash="sha256:" + "a" * 64, license="x", runtime_adapter="lora.diffusers",
        capabilities=("image.lora",), hardware_backends=("rocm",),
        state=ModelState.AVAILABLE, policy_rank={"auto": 1}, required_files=(),
        weights=(WeightFile(path="w.safetensors", size_bytes=1, sha256="b" * 64),),
        installed=True, healthy=True, local_path=Path("/tmp/lora"),
        execution_peak_vram_bytes=1, cold_load_peak_vram_bytes=1, headroom_vram_bytes=1,
        measured_runtime_sec=1.0,
    )

    assert lora.is_lora
    with pytest.raises(ModelRouteError):
        route_model(
            [lora], capability="image.text_to_image", policy="auto",
            hardware_backend="rocm", free_vram_bytes=2**40,
        )


def test_a_lora_cannot_be_reached_by_naming_it_directly():
    """manual でも選べてはいけない。"""
    from mediaforge.models.registry import ModelDescriptor, ModelState, WeightFile
    from mediaforge.routing.router import ModelRouteError, route_model

    lora = ModelDescriptor(
        model_id="civitai/58390", family="custom", version="1", revision="1",
        weights_hash="sha256:" + "a" * 64, license="x", runtime_adapter="lora.diffusers",
        capabilities=("image.lora",), hardware_backends=("rocm",),
        state=ModelState.AVAILABLE, policy_rank={"auto": 1}, required_files=(),
        weights=(WeightFile(path="w.safetensors", size_bytes=1, sha256="b" * 64),),
        installed=True, healthy=True, local_path=Path("/tmp/lora"),
    )

    with pytest.raises(ModelRouteError):
        route_model(
            [lora], capability="image.text_to_image", policy="manual",
            hardware_backend="rocm", free_vram_bytes=2**40, model_id="civitai/58390",
        )


def test_text_encoder_keys_are_aligned_to_the_encoder_that_is_loaded():
    """実測: transformers 5 で CLIP のモジュール名から text_model. が消えた。
    diffusers 0.40 は古い名前で rank を引くので、空になって
    IndexError: list index out of range で落ちる。LoRA 側は壊れていない。"""
    from worker_packs.image.adapters.lora import align_text_encoder_keys

    class Encoder:
        def named_modules(self):
            return [("encoder.layers.0.mlp.fc1", None)]

    class Pipeline:
        text_encoder = Encoder()

    aligned = align_text_encoder_keys({
        "text_encoder.text_model.encoder.layers.0.mlp.fc1.lora_A.weight": 1,
        "unet.down_blocks.0.lora_A.weight": 2,
    }, Pipeline())

    assert "text_encoder.encoder.layers.0.mlp.fc1.lora_A.weight" in aligned
    # LoRA と無関係の鍵は触らない。
    assert aligned["unet.down_blocks.0.lora_A.weight"] == 2


def test_an_encoder_that_still_has_the_old_names_is_left_alone():
    """新しい名前に合わせて常に削ると、古い transformers で壊れる。"""
    from worker_packs.image.adapters.lora import align_text_encoder_keys

    class Encoder:
        def named_modules(self):
            return [("text_model.encoder.layers.0.mlp.fc1", None)]

    class Pipeline:
        text_encoder = Encoder()

    key = "text_encoder.text_model.encoder.layers.0.mlp.fc1.lora_A.weight"
    assert key in align_text_encoder_keys({key: 1}, Pipeline())


def test_a_lora_for_another_family_is_refused_before_it_loads(tmp_path: Path):
    """SD 1.5 の LoRA を SDXL に載せると次元が合わずに落ちる。運が悪いと形だけ
    通って絵が崩れる。落ちる方がまだよいが、どちらも起きる前に断る。"""
    from mediaforge.domain import JobRequest
    from mediaforge.jobs import JobManager, WorkerFailure
    from mediaforge.store import Store
    from tests.test_image_evaluation import descriptor

    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(
        store,
        model_manifest=Path(__file__).parents[1] / "worker_packs/image/models.json",
        model_catalog_manifest=Path(__file__).parents[1] / "worker_packs/image/catalog.json",
        hf_home=tmp_path / "hf",
        model_store_root=tmp_path / "models",
    )
    job = store.create_job(JobRequest(
        operation="image.generate", intent="test",
        constraints={"loras": [{"model_id": "civitai/58390", "weight": 1.0}]},
    ))

    with pytest.raises(WorkerFailure) as failure:
        manager._resolved_loras(store.get_job(job.id), descriptor(base_model="SDXL 1.0"))

    # 導入されていないので lora_not_installed が先に出る。どちらにせよ載らない。
    assert failure.value.code in {"lora_incompatible", "lora_not_installed"}


def test_the_weight_and_the_count_are_bounded(tmp_path: Path):
    from mediaforge.domain import JobRequest
    from mediaforge.jobs import JobManager, WorkerFailure
    from mediaforge.store import Store

    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)

    for constraints in (
        {"loras": [{"model_id": "a", "weight": 5}]},
        {"loras": [{"model_id": str(index)} for index in range(5)]},
        {"loras": "civitai/1"},
    ):
        job = store.create_job(JobRequest(
            operation="image.generate", intent="t", constraints=constraints
        ))
        with pytest.raises(WorkerFailure):
            manager._requested_loras(store.get_job(job.id))


def test_lora_choices_resolve_one_base_family_without_a_user_model_choice(tmp_path: Path):
    from mediaforge.domain import JobRequest
    from mediaforge.jobs import JobManager
    from mediaforge.models import ModelDescriptor, ModelState
    from mediaforge.models.registry import WeightFile
    from mediaforge.store import Store

    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)
    path = tmp_path / "lora.safetensors"
    path.write_bytes(b"x")
    lora = ModelDescriptor(
        model_id="civitai/1", family="custom", version="1", revision="1",
        weights_hash="sha256:" + "a" * 64, license="x",
        runtime_adapter="lora.diffusers", capabilities=("image.lora",),
        hardware_backends=("rocm",), state=ModelState.EXPERIMENTAL,
        policy_rank={"auto": 1}, required_files=(),
        weights=(WeightFile(path=path.name, size_bytes=1, sha256="b" * 64),),
        installed=True, local_path=path, base_model="SDXL 1.0",
    )
    job = store.create_job(JobRequest(
        operation="image.generate", intent="test",
        constraints={"loras": [{"model_id": lora.model_id}]},
    ))

    assert manager._required_lora_family(store.get_job(job.id), (lora,)) == "sdxl"


def test_mixed_lora_families_are_refused_before_routing(tmp_path: Path):
    from dataclasses import replace

    from mediaforge.domain import JobRequest
    from mediaforge.jobs import JobManager, WorkerFailure
    from mediaforge.models import ModelDescriptor, ModelState
    from mediaforge.models.registry import WeightFile
    from mediaforge.store import Store

    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)
    path = tmp_path / "lora.safetensors"
    path.write_bytes(b"x")
    first = ModelDescriptor(
        model_id="civitai/1", family="custom", version="1", revision="1",
        weights_hash="sha256:" + "a" * 64, license="x",
        runtime_adapter="lora.diffusers", capabilities=("image.lora",),
        hardware_backends=("rocm",), state=ModelState.EXPERIMENTAL,
        policy_rank={"auto": 1}, required_files=(),
        weights=(WeightFile(path=path.name, size_bytes=1, sha256="b" * 64),),
        installed=True, local_path=path, base_model="SDXL 1.0",
    )
    second = replace(first, model_id="civitai/2", base_model="SD 1.5")
    job = store.create_job(JobRequest(
        operation="image.generate", intent="test",
        constraints={"loras": [{"model_id": first.model_id}, {"model_id": second.model_id}]},
    ))

    with pytest.raises(WorkerFailure) as failure:
        manager._required_lora_family(store.get_job(job.id), (first, second))

    assert failure.value.code == "lora_incompatible"


def test_a_lora_path_outside_the_allowed_roots_is_refused(tmp_path: Path, monkeypatch):
    """境界の無い経路を通すと、任意の safetensors を読み込ませられる。"""
    from worker_packs.image import worker as image_worker

    allowed = tmp_path / "models"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "evil.safetensors").write_bytes(b"x")
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(allowed))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(tmp_path / "work"))
    monkeypatch.setenv("MEDIA_FORGE_LORA_ROOTS", str(allowed))
    (tmp_path / "work").mkdir()

    with pytest.raises(ValueError, match="boundary"):
        image_worker.ImageWorker()._loras(
            [{"id": "x", "path": str(outside / "evil.safetensors"), "weight": 1.0}]
        )


def test_a_lora_beside_the_model_is_accepted(tmp_path: Path, monkeypatch):
    """LoRA は選んだモデルとは別の repository に入る。モデルの境界で見ると
    必ず外に出るので、そこで弾いていると 1 つも載せられない。"""
    from worker_packs.image import worker as image_worker

    store = tmp_path / "models"
    (store / "hub" / "models--civitai--58390").mkdir(parents=True)
    lora = store / "hub" / "models--civitai--58390" / "add_detail.safetensors"
    lora.write_bytes(b"x")
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(store / "hub" / "models--other--model"))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(tmp_path / "work"))
    monkeypatch.setenv("MEDIA_FORGE_LORA_ROOTS", str(store))
    (tmp_path / "work").mkdir()

    resolved = image_worker.ImageWorker()._loras(
        [{"id": "civitai/58390", "path": str(lora), "weight": 0.8}]
    )

    assert resolved[0]["weight"] == 0.8


def test_a_lora_without_a_measured_base_is_refused_instead_of_running_without_one(
    tmp_path: Path, monkeypatch
):
    """載せる先が無いことを、黙って「モデル無し」の経路へ落とさない。

    落とすと model を持たない payload でワーカーが起動し、exit code 2 で死ぬ。
    実機ではこれが理由の分からない worker_crash に見えていた（job_e4a1b7cf、
    2026-08-28）。ついでに AI ターンの終了宣言も飛ばされ、LLM が居座った。
    """
    from dataclasses import replace

    from mediaforge.domain import JobRequest
    from mediaforge import jobs as jobs_module
    from mediaforge.jobs import JobManager, WorkerFailure
    from mediaforge.models import ModelDescriptor, ModelState
    from mediaforge.models.registry import WeightFile
    from mediaforge.store import Store

    store = Store(tmp_path / "data")
    store.initialize()
    manager = JobManager(store)
    manager.model_manifest = tmp_path / "models.json"
    manager.hf_home = tmp_path / "hf"
    path = tmp_path / "lora.safetensors"
    path.write_bytes(b"x")
    lora = ModelDescriptor(
        model_id="civitai/1", family="custom", version="1", revision="1",
        weights_hash="sha256:" + "a" * 64, license="x",
        runtime_adapter="lora.diffusers", capabilities=("image.lora",),
        hardware_backends=("rocm",), state=ModelState.EXPERIMENTAL,
        policy_rank={"auto": 1}, required_files=(),
        weights=(WeightFile(path=path.name, size_bytes=1, sha256="b" * 64),),
        installed=True, local_path=path, base_model="SD 1.5",
    )
    # 同じ系統の土台はあるが、まだ measured でないので available にならない。
    base = replace(
        lora, model_id="civitai/4384", runtime_adapter="diffusers.sdxl-single-file",
        capabilities=("image.text_to_image",), base_model="SD 1.5",
    )

    class Loaded:
        @staticmethod
        def all() -> tuple[ModelDescriptor, ...]:
            return (lora, base)

    monkeypatch.setattr(jobs_module.ModelRegistry, "load", staticmethod(lambda *a, **k: Loaded))
    job = store.create_job(JobRequest(
        operation="image.generate", intent="test", model_policy="auto",
        constraints={"loras": [{"model_id": lora.model_id}]},
    ))

    with pytest.raises(WorkerFailure) as failure:
        manager._select_real_model(store.get_job(job.id))

    assert failure.value.code == "lora_base_unavailable"


def test_a_self_added_checkpoint_can_take_a_lora(tmp_path: Path):
    """載せられるかは、宣言ではなく実際に載せられるかで決める。

    利用者が自分で足したモデルは常に supports_lora=false で登録される
    (custom_models.py)。backend は旗を見ずに系統だけで判定するので、画面だけが
    worker なら載せられる組み合わせを隠していた。実機では、評価まで通した
    Lykon/DreamShaper (SD 1.5) に SD 1.5 の LoRA を載せられなかった。
    """
    from dataclasses import replace

    from mediaforge.models import ModelDescriptor, ModelState
    from mediaforge.models.registry import ModelRegistry, WeightFile

    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    checkpoint = ModelDescriptor(
        model_id="Lykon/DreamShaper", family="custom", version="1", revision="1",
        weights_hash="sha256:" + "a" * 64, license="x",
        runtime_adapter="diffusers.sdxl", capabilities=("image.text_to_image",),
        hardware_backends=("rocm",), state=ModelState.EXPERIMENTAL,
        policy_rank={"auto": 1}, required_files=(),
        weights=(WeightFile(path="w.safetensors", size_bytes=1, sha256="b" * 64),),
        installed=True, local_path=snapshot, base_model="SD 1.5",
        supports_lora=False, default_steps=30, native_width=512, native_height=512,
    )

    assert ModelRegistry._observed_defaults(checkpoint, snapshot).get("supports_lora") is True
    # 系統が分からないものは、載せられると言わない。
    unknown = replace(checkpoint, base_model="")
    assert ModelRegistry._observed_defaults(unknown, snapshot).get("supports_lora") is None
    # 宣言で立っているものを触らない。
    declared = replace(checkpoint, supports_lora=True)
    assert "supports_lora" not in ModelRegistry._observed_defaults(declared, snapshot)
    # diffusers 以外は読めた気にならない。
    native = replace(checkpoint, runtime_adapter="native.h3")
    assert ModelRegistry._observed_defaults(native, snapshot) == {}


def test_the_timeout_budget_counts_the_images_that_were_asked_for(tmp_path: Path):
    """実測は 1 枚ぶん。頼まれた枚数を数えないと、枚数のぶんだけ落ちる。

    実機では measured_runtime_sec=13.0 の DreamShaper に 4 枚頼み、予算は
    13*3+30=69 秒のままだった。同じ設定が通ったり worker_timeout で落ちたりして
    いたのはこれである（2026-08-28、job_8838a3c7 成功 / job_d1f45685 失敗）。
    """
    source = (Path(__file__).parents[1] / "backend/mediaforge/jobs.py").read_text(encoding="utf-8")
    budget = source[
        source.index("            wanted = 1"):source.index("        process = await asyncio.create_subprocess_exec")
    ]
    assert 'payload.get("request", {}).get("output", {}).get("count")' in budget
    assert "* 3 * wanted + 30" in budget

    # 実機の数字で確かめる。1 枚ぶんの予算では 4 枚は収まらない。
    measured, count, floor = 13.0, 4, 30.0
    assert max(floor, measured * 3 + 30) < 80.0          # 成功に 80.0 秒かかった
    assert max(floor, measured * 3 * count + 30) > 106.5  # 失敗は 106.5 秒で切られた
