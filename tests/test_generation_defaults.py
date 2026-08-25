"""そのモデル本来の設定を、モデル自身の中身から決める。

実測で分かったこと: worker が全モデル共通で 4 歩を既定にしていた。4 は
FLUX.2 Klein（蒸留済み）の値で、SDXL 系をその歩数で回すと像を結ばない。
同じ SDXL が 1024x1024 / 30 歩では指示どおりの絵を出す。共通の既定は
置けない、というのがこのモジュールの前提である。
"""
from __future__ import annotations

import json

import pytest
from pathlib import Path

from mediaforge.models.generation_defaults import (
    DEFAULT_DIFFUSION_STEPS,
    native_side_from_config,
    pipeline_class_from_config,
    resolution_buckets,
    snap_to_native,
    steps_for,
)


def repository(root: Path, *, sample_size: int, vae_stages: int = 4, scheduler: str = "EulerDiscreteScheduler", pipeline: str = "StableDiffusionXLPipeline") -> Path:
    (root / "unet").mkdir(parents=True)
    (root / "vae").mkdir(parents=True)
    (root / "scheduler").mkdir(parents=True)
    (root / "unet" / "config.json").write_text(json.dumps({"sample_size": sample_size}))
    (root / "vae" / "config.json").write_text(
        json.dumps({"block_out_channels": [128] * vae_stages})
    )
    (root / "scheduler" / "scheduler_config.json").write_text(
        json.dumps({"_class_name": scheduler})
    )
    (root / "model_index.json").write_text(json.dumps({"_class_name": pipeline}))
    return root


def test_the_training_resolution_is_read_from_the_model_not_guessed(tmp_path: Path):
    """実測: SDXL / SSD-1B は sample_size 128、VAE 4 段 -> 128 * 8 = 1024。"""
    assert native_side_from_config(repository(tmp_path / "xl", sample_size=128)) == 1024


def test_stable_diffusion_1_5_is_512_by_the_same_arithmetic(tmp_path: Path):
    """1024 を全形式に当てると SD 1.5 は構図が二重になる。表ではなく計算で出す。"""
    assert native_side_from_config(repository(tmp_path / "sd", sample_size=64)) == 512


def test_a_repository_that_does_not_say_returns_nothing(tmp_path: Path):
    """推測した値を「そのモデルの寸法」として記録すると、崩れた理由が残らない。"""
    empty = tmp_path / "empty"
    empty.mkdir()
    assert native_side_from_config(empty) is None


def test_a_plain_diffusion_model_gets_enough_steps(tmp_path: Path):
    root = repository(tmp_path / "xl", sample_size=128)
    assert steps_for(pipeline_class_from_config(root), root) == DEFAULT_DIFFUSION_STEPS


def test_a_distilled_pipeline_is_recognised_by_its_class():
    assert steps_for("Flux2KleinPipeline") == 4


def test_a_distilled_scheduler_overrides_the_family_default(tmp_path: Path):
    """LCM は素の SDXL と同じ pipeline クラスを名乗る。scheduler が違いを言う。"""
    root = repository(tmp_path / "lcm", sample_size=128, scheduler="LCMScheduler")
    assert steps_for(pipeline_class_from_config(root), root) == 8


def test_the_published_sdxl_sizes_come_out_of_the_arithmetic():
    """表を持たずに、SDXL が公表している寸法がそのまま出ることを確かめる。

    表で持つと SDXL にしか効かず、新しい形式が出るたびに書き足すことになる。
    """
    buckets = resolution_buckets(1024)
    for size in ((1024, 1024), (1152, 896), (896, 1152), (1216, 832), (1344, 768), (1536, 640)):
        assert size in buckets, size


def test_a_wide_request_keeps_its_shape_and_the_trained_area():
    """総画素を増やすと、モデルが見たことのない広さになり被写体が 2 つ並ぶ。"""
    width, height = snap_to_native(1920, 1080, 1024)

    assert abs(width / height - 16 / 9) < 0.05
    assert abs(width * height - 1024 * 1024) < 1024 * 1024 * 0.1


def test_the_same_request_gets_a_smaller_canvas_on_a_512_model():
    """同じ「横長が欲しい」でも、そのモデルが学習した広さは違う。"""
    assert snap_to_native(1920, 1080, 512)[0] < snap_to_native(1920, 1080, 1024)[0]


def test_a_square_request_stays_square():
    assert snap_to_native(600, 600, 1024) == (1024, 1024)


def test_core_resolves_the_settings_before_the_worker_sees_them(tmp_path: Path):
    """worker に決めさせない。

    worker に共通の既定を置くと、蒸留済みの 1 モデルに合わせた歩数が全形式に
    掛かる。実測ではそれが 4 歩で、SDXL は像を結ばなかった。
    """
    from mediaforge.domain import JobRequest
    from mediaforge.jobs import JobManager
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
    selected = descriptor(default_steps=30, native_width=1024, native_height=1024)

    job = store.create_job(JobRequest(operation="image.generate", intent="test"))
    resolved = manager._resolved_request(store.get_job(job.id), selected)
    assert resolved["constraints"]["steps"] == 30
    assert resolved["constraints"]["width"] == 1024

    wide = store.create_job(JobRequest(
        operation="image.generate", intent="test",
        constraints={"width": 1920, "height": 1080},
    ))
    resolved = manager._resolved_request(store.get_job(wide.id), selected)
    # 比は守り、面積は学習時に合わせる。1920x1080 のまま回すと被写体が 2 つ並ぶ。
    assert resolved["constraints"]["width"] == 1344
    assert resolved["constraints"]["height"] == 768


def test_an_explicit_step_count_is_not_overwritten(tmp_path: Path):
    """既定は指定が無いところを埋めるだけである。"""
    from mediaforge.domain import JobRequest
    from mediaforge.jobs import JobManager
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
        operation="image.generate", intent="test", constraints={"steps": 12},
    ))
    resolved = manager._resolved_request(
        store.get_job(job.id), descriptor(default_steps=30, native_width=1024, native_height=1024)
    )

    assert resolved["constraints"]["steps"] == 12


def test_a_model_that_declares_its_steps_needs_no_checking():
    """判定できたものまで「確認してください」と並べると、本当に確認が要る
    ものが埋もれる。"""
    from mediaforge.models.generation_defaults import STEPS_DECLARED, summary

    report = summary(
        steps=4, steps_source=STEPS_DECLARED,
        native_width=1024, native_height=1024, guidance_scale=7.0,
    )

    assert report["needs_check"] == []
    assert {entry["item"] for entry in report["settled"]} >= {"歩数", "画面寸法", "ガイダンス"}


def test_an_undecidable_step_count_says_so_and_says_what_to_do():
    """分からないことを黙って既定で埋めると、絵が眠いときに何を触ればよいのか
    が分からない。"""
    from mediaforge.models.generation_defaults import STEPS_ASSUMED, summary

    report = summary(
        steps=30, steps_source=STEPS_ASSUMED,
        native_width=1024, native_height=1024, guidance_scale=None,
    )
    items = {entry["item"]: entry for entry in report["needs_check"]}

    assert "歩数" in items
    assert items["歩数"]["reason"], "なぜ決められなかったのかを言っていない"
    assert items["歩数"]["action"], "何をすればよいのかを言っていない"
    # 寸法は読めているので、確認の側に混ぜない。
    assert "画面寸法" not in items


def test_a_repository_that_hides_its_size_is_listed_for_checking():
    from mediaforge.models.generation_defaults import STEPS_DECLARED, summary

    report = summary(
        steps=30, steps_source=STEPS_DECLARED,
        native_width=None, native_height=None, guidance_scale=7.0,
    )

    assert "画面寸法" in {entry["item"] for entry in report["needs_check"]}


def test_the_distilled_presets_appear_only_when_the_family_is_undecided():
    """素のモデルに 4 歩を勧めると崩れる。分からないときにだけ出す。"""
    from mediaforge.models.generation_defaults import STEPS_ASSUMED, STEPS_DECLARED, presets

    undecided = {item["id"] for item in presets(30, STEPS_ASSUMED, 7.0)}
    decided = {item["id"] for item in presets(30, STEPS_DECLARED, 7.0)}

    assert {"turbo", "lightning"} <= undecided
    assert not ({"turbo", "lightning"} & decided)


def test_the_turbo_preset_turns_guidance_off():
    """歩数だけ合わせてガイダンスを 7.0 のままにすると、絵が焼ける。"""
    from mediaforge.models.generation_defaults import STEPS_ASSUMED, presets

    turbo = next(item for item in presets(30, STEPS_ASSUMED, 7.0) if item["id"] == "turbo")

    assert turbo["steps"] == 4
    assert turbo["guidance_scale"] == 0.0


def test_guidance_zero_survives_the_whole_path(tmp_path: Path):
    """0 は「CFG を使わない」という指示で、Turbo 系はそれを前提に蒸留されて
    いる。0 を「未指定」と同じに扱うと、そのモデルを正しく回せない。"""
    from mediaforge.domain import JobRequest
    from mediaforge.jobs import requested_guidance
    from mediaforge.store import Store
    from tests.test_image_evaluation import descriptor

    store = Store(tmp_path / "data")
    store.initialize()
    job = store.create_job(JobRequest(
        operation="image.generate", intent="test", constraints={"guidance_scale": 0},
    ))

    assert requested_guidance(store.get_job(job.id), descriptor(guidance_scale=7.0)) == 0.0


def test_an_unspecified_guidance_keeps_the_model_s_own(tmp_path: Path):
    from mediaforge.domain import JobRequest
    from mediaforge.jobs import requested_guidance
    from mediaforge.store import Store
    from tests.test_image_evaluation import descriptor

    store = Store(tmp_path / "data")
    store.initialize()
    job = store.create_job(JobRequest(operation="image.generate", intent="test"))

    assert requested_guidance(store.get_job(job.id), descriptor(guidance_scale=7.0)) == 7.0


def test_the_worker_runs_a_distilled_model_at_guidance_zero(monkeypatch, tmp_path):
    """core が 0 を通しても worker が弾いたら、経路として通っていない。"""
    from worker_packs.image import worker as image_worker
    from worker_packs.image.adapters import ImageGenerationResult

    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model = model_root / "model"
    output_dir = work_root / "job" / "outputs"
    model.mkdir(parents=True)
    output_dir.parent.mkdir(parents=True)
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))
    seen: dict[str, object] = {}

    class Adapter:
        def __init__(self, _path, *, device_mode, disable_mmap, **family):
            seen.update(family)
            self.load_sec = 0.1
            self.last_generation_sec = None
            self.placement = {
                "component_devices": {}, "non_gpu_devices": {},
                "offload_hooks": [], "non_gpu_map_targets": [],
            }

        def generate(self, request):
            seen["steps"] = request.steps
            request.output_path.write_bytes(b"png")
            self.last_generation_sec = 0.1
            return ImageGenerationResult(request.output_path, request.seed)

    monkeypatch.setattr(image_worker, "DiffusersStableDiffusionAdapter", Adapter)
    monkeypatch.setattr(image_worker.importlib.metadata, "version", lambda _name: "test-runtime")
    image_worker.ImageWorker().handle({
        "model": {
            "id": "owner/turbo", "path": str(model), "version": "1",
            "weights_hash": "sha256:" + "a" * 64, "license": "Apache-2.0",
            "runtime_adapter": "diffusers.sdxl",
            "runtime_options": {"guidance_scale": 0, "default_steps": 4},
        },
        "request": {
            "operation": "image.generate", "intent": "a blue robot",
            "constraints": {"width": 512, "height": 512, "seed": 7},
            "output": {"format": "png", "count": 1},
        },
        "worker_output_dir": str(output_dir),
    })

    assert seen["guidance_scale"] == 0.0
    # 歩数を要求が持っていないときは、そのモデルが宣言した値を使う。
    assert seen["steps"] == 4


def test_the_worker_refuses_to_invent_a_step_count(monkeypatch, tmp_path):
    """共通の既定を置くと、蒸留済みの 1 モデルの値が全形式に掛かる。"""
    from worker_packs.image import worker as image_worker

    model_root = tmp_path / "models"
    work_root = tmp_path / "work"
    model = model_root / "model"
    model.mkdir(parents=True)
    (work_root / "job").mkdir(parents=True)
    monkeypatch.setenv("MEDIA_FORGE_MODEL_ROOT", str(model_root))
    monkeypatch.setenv("MEDIA_FORGE_WORK_ROOT", str(work_root))

    with pytest.raises(ValueError, match="steps"):
        image_worker.ImageWorker().handle({
            "model": {
                "id": "owner/model", "path": str(model), "version": "1",
                "weights_hash": "sha256:" + "a" * 64, "license": "Apache-2.0",
                "runtime_adapter": "diffusers.sdxl",
            },
            "request": {
                "operation": "image.generate", "intent": "a blue robot",
                "constraints": {"width": 512, "height": 512, "seed": 7},
                "output": {"format": "png", "count": 1},
            },
            "worker_output_dir": str(work_root / "job" / "outputs"),
        })
