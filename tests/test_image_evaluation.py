"""測って昇格させる経路。

自作モデルは「誰もここで走らせていない」ので experimental で入る。routing は
それを選ばない — 選ぶには VRAM を推測することになり、答えは誰かの作業中の
out-of-memory として返ってくる。1 度走らせて測れば推測が消える。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from mediaforge.image_evaluation import (
    HEADROOM_BYTES,
    ImageEvaluationError,
    ImageMeasurement,
    measure_image_model,
    worker_payload,
)
from mediaforge.models import ModelDescriptor, ModelState


def descriptor(**overrides) -> ModelDescriptor:
    from mediaforge.models.registry import WeightFile

    values = dict(
        model_id="owner/model",
        family="custom",
        version="1",
        revision="a" * 40,
        weights_hash="sha256:" + "b" * 64,
        license="Apache-2.0",
        runtime_adapter="diffusers.sdxl",
        capabilities=("image.text_to_image",),
        hardware_backends=("rocm", "cuda"),
        state=ModelState.EXPERIMENTAL,
        policy_rank={"auto": 100},
        required_files=(),
        weights=(WeightFile(path="w.safetensors", size_bytes=10, sha256="c" * 64),),
        installed=True,
        local_path=Path("/tmp/models/hub/models--owner--model/snapshots/abc"),
    )
    values.update(overrides)
    return ModelDescriptor(**values)


def test_the_probe_uses_the_same_envelope_as_a_real_generation(tmp_path: Path):
    """別経路で測ると、実際に使う経路ではないものを測ることになる。"""
    payload = worker_payload(descriptor(), tmp_path)

    assert payload["request"]["operation"] == "image.generate"
    assert payload["model"]["runtime_adapter"] == "diffusers.sdxl"


def test_the_probe_runs_at_the_model_s_own_settings(tmp_path: Path):
    """小さく短く測ると、実使用とは別のものを測ることになる。

    実測: SDXL を 512x512 / 8 歩で測ると 8.45GB / 6.07 秒と記録されるが、
    その設定では指示した被写体すら描かれない。動かない設定で「動いた」と
    記録し、その数字で routing が VRAM を確保することになる。
    """
    payload = worker_payload(
        descriptor(native_width=1024, native_height=1024, default_steps=30), tmp_path
    )

    assert payload["request"]["constraints"]["width"] == 1024
    assert payload["request"]["constraints"]["height"] == 1024
    assert payload["request"]["constraints"]["steps"] == 30


def test_a_distilled_model_is_measured_at_its_own_step_count(tmp_path: Path):
    """FLUX.2 Klein を 30 歩で測ると、要りもしない時間を costs として記録する。"""
    payload = worker_payload(descriptor(default_steps=4), tmp_path)

    assert payload["request"]["constraints"]["steps"] == 4


def test_family_options_reach_the_worker(tmp_path: Path):
    payload = worker_payload(descriptor(guidance_scale=7.0, negative_prompt="blurry"), tmp_path)
    options = payload["model"]["runtime_options"]
    assert options["guidance_scale"] == 7.0
    assert options["negative_prompt"] == "blurry"


def test_a_model_without_an_image_adapter_is_refused(tmp_path: Path):
    with pytest.raises(ImageEvaluationError) as failure:
        asyncio.run(measure_image_model(
            descriptor(runtime_adapter="native.wan2.2"),
            runtime_python=tmp_path / "python", work_root=tmp_path,
            repository_root=tmp_path,
        ))
    assert failure.value.code == "model_evaluation_unsupported"


def test_a_model_that_is_not_installed_is_refused(tmp_path: Path):
    with pytest.raises(ImageEvaluationError) as failure:
        asyncio.run(measure_image_model(
            descriptor(installed=False, local_path=None),
            runtime_python=tmp_path / "python", work_root=tmp_path,
            repository_root=tmp_path,
        ))
    assert failure.value.code == "model_not_found"


def test_the_measurement_carries_headroom_over_the_observed_peak():
    """実測ちょうどで受理すると、次に少し上振れした瞬間に落ちる。"""
    measurement = ImageMeasurement(
        execution_peak_vram_bytes=8_450_469_888,
        cold_load_peak_vram_bytes=8_450_469_888,
        measured_runtime_sec=6.0721,
        width=512, height=512, output_bytes=411_811,
    )
    recorded = measurement.catalog_measurements()

    assert recorded["execution_peak_vram_bytes"] == 8_450_469_888
    assert recorded["headroom_vram_bytes"] == HEADROOM_BYTES
    assert recorded["measured_runtime_sec"] == 6.07
    assert recorded["resident_vram_bytes"] == 0


def test_recording_a_measurement_makes_the_model_routable(tmp_path: Path):
    from mediaforge.custom_models import CustomModelCatalog

    catalog = CustomModelCatalog(tmp_path / "custom.json")
    catalog._write([{
        "registry": {
            "model_id": "owner/model", "runtime_adapter": "diffusers.sdxl",
            "state": "experimental", "measurement_confidence": "low",
        },
        "catalog": {"model_id": "owner/model"},
    }])

    catalog.record_measurement("owner/model", {"execution_peak_vram_bytes": 1})

    entry = catalog.entries()[0]["registry"]
    assert entry["state"] == "available"
    assert entry["measurement_confidence"] == "measured"
    assert entry["measurements"] == {"execution_peak_vram_bytes": 1}


def test_a_model_with_no_adapter_is_not_promoted_by_measuring_it(tmp_path: Path):
    """測っても実行アダプタは生えない。使えるようになったと言わない。"""
    from mediaforge.custom_models import CustomModelCatalog, CustomModelError

    catalog = CustomModelCatalog(tmp_path / "custom.json")
    catalog._write([{
        "registry": {
            "model_id": "owner/odd", "runtime_adapter": "unsupported",
            "state": "experimental",
        },
        "catalog": {"model_id": "owner/odd"},
    }])

    with pytest.raises(CustomModelError) as failure:
        catalog.record_measurement("owner/odd", {"execution_peak_vram_bytes": 1})
    assert failure.value.code == "custom_model_unsupported"
