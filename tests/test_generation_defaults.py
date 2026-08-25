"""そのモデル本来の設定を、モデル自身の中身から決める。

実測で分かったこと: worker が全モデル共通で 4 歩を既定にしていた。4 は
FLUX.2 Klein（蒸留済み）の値で、SDXL 系をその歩数で回すと像を結ばない。
同じ SDXL が 1024x1024 / 30 歩では指示どおりの絵を出す。共通の既定は
置けない、というのがこのモジュールの前提である。
"""
from __future__ import annotations

import json
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
