from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from mediaforge.models import ModelOwnership, ModelRegistry
from mediaforge.routing import ModelRouteError, route_model


ROOT = Path(__file__).parents[1]
VIDEO_IDS = {
    "Wan-AI/Wan2.2-TI2V-5B",
    "Wan-AI/Wan2.2-I2V-A14B",
    "Wan-AI/Wan2.2-T2V-A14B",
    "Wan-AI/Wan2.2-Animate-14B",
    "Lightricks/LTX-2.3",
    "zai-org/CogVideoX-2b",
    "Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
    "Wan-AI/Wan2.1-VACE-1.3B-diffusers",
    "tencent/HunyuanVideo-1.5",
    "MiniMaxAI/MiniMax-H3",
    "DiffSynth-Studio/MiniMax-H3-NF4",
    "unsloth/MiniMax-H3-GGUF",
}


def registry() -> ModelRegistry:
    return ModelRegistry.load(
        ROOT / "worker_packs/image/models.json",
        catalog_manifest=ROOT / "worker_packs/image/catalog.json",
    )


def test_video_candidates_are_pinned_and_never_recommended() -> None:
    candidates = {model.model_id: model for model in registry().all() if "video" in model.media_types}

    assert set(candidates) == VIDEO_IDS
    # 実測した候補だけが available になる。測っていないものは experimental のまま。
    adopted = {
        "Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
        "unsloth/MiniMax-H3-GGUF",
        "Wan-AI/Wan2.2-TI2V-5B",
    }
    assert all(
        model.state == ("available" if model_id in adopted else "experimental")
        for model_id, model in candidates.items()
    )
    t2v = candidates["Wan-AI/Wan2.1-T2V-1.3B-Diffusers"]
    assert t2v.measurement_confidence == "measured"
    assert t2v.measured_runtime_sec == 144.64
    assert t2v.execution_peak_vram_bytes == 18_610_000_000
    wan = candidates["Wan-AI/Wan2.2-TI2V-5B"]
    assert wan.measurement_confidence == "measured"
    assert wan.hardware_backends == ("cuda", "rocm")
    # VRAM は G7 V1 の実測を据え置く。2026-08-30 は時間だけを測り直した
    # （384x256 33 フレーム 30 歩を wall 100.51 秒）。採っていない値は上書きしない。
    assert wan.execution_peak_vram_bytes == 30_700_000_000
    assert wan.headroom_vram_bytes == 1024 * 1024 * 1024
    assert wan.measured_runtime_sec == 100.51
    cog = candidates["zai-org/CogVideoX-2b"]
    assert cog.measurement_confidence == "low"
    assert cog.hardware_backends == ("cuda", "rocm")
    vace = candidates["Wan-AI/Wan2.1-VACE-1.3B-diffusers"]
    assert vace.measurement_confidence == "low"
    assert vace.hardware_backends == ("cuda", "rocm")
    assert all(
        model.measurement_confidence == "low"
        and model.measured_runtime_sec is None
        and model.measured_vram_bytes is None
        and model.hardware_backends == ("cuda",)
        for model_id, model in candidates.items()
        # 実測した候補はここでは見ない。測った値を持っているのが正しい。
        if model_id not in {
            wan.model_id, cog.model_id, vace.model_id, t2v.model_id, "unsloth/MiniMax-H3-GGUF",
        }
    )
    assert all(not model.recommended_profiles for model in candidates.values())
    assert all(model.approx_download_bytes >= sum(weight.size_bytes for weight in model.weights)
               for model in candidates.values())


def test_video_checkpoint_identity_hashes_are_reproducible() -> None:
    for model in registry().all():
        if model.model_id not in VIDEO_IDS:
            continue
        canonical = "".join(
            f"{weight.path}\0{weight.size_bytes}\0{weight.sha256}\n"
            for weight in sorted(model.weights, key=lambda item: item.path)
        ).encode()
        assert model.weights_hash == "sha256:" + hashlib.sha256(canonical).hexdigest()


def test_only_bounded_complete_video_snapshots_are_managed() -> None:
    candidates = {model.model_id: model for model in registry().all() if model.model_id in VIDEO_IDS}

    assert {model_id for model_id, model in candidates.items() if model.ownership == ModelOwnership.MANAGED} == {
        "Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
        "Wan-AI/Wan2.2-TI2V-5B",
        "Wan-AI/Wan2.2-I2V-A14B",
        "Wan-AI/Wan2.2-T2V-A14B",
        "zai-org/CogVideoX-2b",
        "unsloth/MiniMax-H3-GGUF",
    }
    assert {model_id for model_id, model in candidates.items() if model.ownership == ModelOwnership.EXTERNAL} == {
        "Wan-AI/Wan2.2-Animate-14B",
        "Lightricks/LTX-2.3",
        "Wan-AI/Wan2.1-VACE-1.3B-diffusers",
        "tencent/HunyuanVideo-1.5",
        "MiniMaxAI/MiniMax-H3",
        "DiffSynth-Studio/MiniMax-H3-NF4",
    }


def test_the_measured_t2v_candidate_is_routable_and_the_rest_are_not() -> None:
    """実測した候補だけを通す。測っていないものを通すと、VRAM を当てずっぽうで
    確保して利用者の作業中に判明することになる。

    T2V 1.3B は 2026-08-29 に R9700 / gfx1201 で実測した（512x320 33 フレーム
    30 ステップ 144.6 秒、peak VRAM 18.6 GB）。VACE は同条件で条件付けの符号化に
    100 秒を払うため、文章から作る用途では選ばない。
    """
    candidates = {model.model_id: model for model in registry().all()}
    t2v = candidates["Wan-AI/Wan2.1-T2V-1.3B-Diffusers"]
    vace = candidates["Wan-AI/Wan2.1-VACE-1.3B-diffusers"]

    assert t2v.ownership == ModelOwnership.MANAGED
    assert t2v.approx_download_bytes == 28_935_653_511
    assert t2v.capabilities == ("video.text_to_video",)
    assert t2v.hardware_backends == ("cuda", "rocm")
    assert len(t2v.weights) == 10

    assert vace.ownership == ModelOwnership.EXTERNAL
    assert vace.approx_download_bytes == 19_043_130_596
    assert vace.capabilities == (
        "video.image_to_video",
        "video.multi_keyframe",
        "video.video_to_video",
    )
    assert vace.hardware_backends == ("cuda", "rocm")
    assert len(vace.weights) == 8


def test_minimax_h3_is_license_gated_and_never_claims_r9700_support() -> None:
    model = next(item for item in registry().all() if item.model_id == "MiniMaxAI/MiniMax-H3")

    assert model.version == "fl2va-bf16"
    assert model.gated is True
    assert model.ownership == ModelOwnership.EXTERNAL
    # 上流の本体は取得していない。測っていないものを rocm 対応とは言わない。
    assert model.hardware_backends == ("cuda",)
    assert model.state == "experimental"
    assert model.approx_download_bytes == 144_051_182_625
    assert len(model.weights) == 29
    assert len(model.required_files) == 52
    assert model.license_acceptance_id is not None


def test_minimax_h3_nf4_bundle_is_bounded_below_local_download_limit() -> None:
    model = next(
        item for item in registry().all()
        if item.model_id == "DiffSynth-Studio/MiniMax-H3-NF4"
    )

    assert model.version == "fl2va-pruned-nf4"
    assert model.gated is True
    assert model.ownership == ModelOwnership.EXTERNAL
    assert model.approx_download_bytes == 27_705_875_746
    assert model.approx_download_bytes < 32_000_000_000
    assert len(model.weights) == 4
    assert model.hardware_backends == ("cuda",)
    assert model.state == "experimental"


def test_minimax_h3_gguf_composite_bundle_is_bounded_and_pinned() -> None:
    model = next(item for item in registry().all() if item.model_id == "unsloth/MiniMax-H3-GGUF")

    assert model.version == "fl2va-pruned-ud-q2-k-xl"
    assert model.gated is True
    assert model.ownership == ModelOwnership.MANAGED
    assert model.approx_download_bytes == 26_978_277_946
    assert model.approx_download_bytes < 32_000_000_000
    assert len(model.weights) == 4
    assert {item.source.repo_id for item in model.weights if item.source is not None} == {
        "Comfy-Org/MiniMax-H3"
    }
    # 2026-08-30 に R9700 / gfx1201 で実測した（149.28 秒、peak VRAM 14.76 GB）。
    # 宣言に rocm が無いと、測ってあっても routing の候補にならない。
    assert model.hardware_backends == ("cuda", "rocm")
    assert model.state == "available"
    # 評価は 1 歩で測る（動くかを見るため）。lease へ申告するのは実用の設定で
    # 測った値である。2026-08-31 実測: 640x384・121 フレーム・20 歩で 2647.52 秒。
    assert model.measured_runtime_sec == 2647.52


def test_unmeasured_video_candidates_cannot_route_on_r9700() -> None:
    with pytest.raises(ModelRouteError, match="no measured local model"):
        route_model(
            registry().all(),
            capability="video.image_to_video",
            policy="auto",
            hardware_backend="rocm",
            free_vram_bytes=34_208_743_424,
        )


def test_the_upscaler_cannot_be_asked_for_more_than_it_can_hold() -> None:
    """拡大は作り直さない。倍率は重みが持っていて、核が掛け算をする。

    出す大きさは、重みの倍率の約数から選ぶ。約数に限るのは、割り切れる縮小
    だけが画素の格子を保つからである。原寸を選んでも網には元の写真をそのまま
    通すので、荒さを取る働きは残る（費用も 4 倍と同じだけ掛かる）。

    2026-09-01 実測（R9700 / gfx1201、256px タイル・32px 重なり）:
      0.31MP ->  4.9MP   6.3s / 0.79MP -> 12.6MP  20.0s
      1.12MP -> 18.0MP  24.7s / 1.50MP -> 24.0MP  35.6s
    VRAM はタイルで決まるので寸法に依らない（0.82 GiB 一定）。
    """
    model = next(item for item in registry().all() if item.model_id == "mikestealth/SwinIR")

    assert model.capabilities == ("image.upscale",)
    assert model.runtime_adapter == "spandrel.upscale"
    assert model.state == "available"
    assert model.hardware_backends == ("rocm", "cuda")
    assert model.ownership == ModelOwnership.MANAGED
    assert model.gated is False

    profile = model.upscale or {}
    assert profile["scale"] == 4
    assert profile["target_scales"] == [1, 2, 4]
    # 選べる倍率は、重みの倍率を割り切るものだけである。
    assert all(profile["scale"] % value == 0 for value in profile["target_scales"])
    # いちばん小さい倍率で、受ける入力の上限が出力の上限に収まる。大きい倍率が
    # 入らない写真は、収まる倍率を名指して要求ごとに断る（写真ごと断らない）。
    smallest = min(profile["target_scales"])
    assert profile["max_source_pixels"] * smallest ** 2 <= 24_000_000
    # 手元のスマホ写真（4032x3024 = 12.2MP）が通る大きさを受ける。前は
    # 1,500,000 画素までで、荒い写真の大半が受付で断られていた。
    assert profile["max_source_pixels"] >= 4032 * 3024
    # 生成の枠も宣言する。既定の 2048x2048 のままだと、作れるのに断られる。
    assert (model.max_width, model.max_height) == (8192, 8192)
    assert model.max_pixels == 24_000_000
    # 歩数は持たない。標本化しないものに既定を持たせない。
    assert model.default_steps is None
    assert model.measured_runtime_sec == 35.6
    assert model.execution_peak_vram_bytes == 879_555_072


def test_the_deblur_model_repairs_without_changing_the_size() -> None:
    """ブレ補正は作り直さないし、大きさも変えない。

    倍率 1 は「寸法を変えずに直す」である。拡大と同じ経路に置くのは、どちらも
    標本化せず（prompt も seed も持たない）、タイルの回し方も同じだからである。

    2026-09-01 実測（R9700 / gfx1201、256px タイル・32px 重なり）:
      1.40MP 1.65s / 3.00MP 3.14s / 7.68MP 7.55s、peak VRAM 405,778,944 B 一定。
      合成した動きブレで PSNR 23.10 dB -> 24.11 dB。
    """
    model = next(item for item in registry().all() if item.model_id == "tog/nafnet-models")

    assert model.capabilities == ("image.deblur",)
    assert model.runtime_adapter == "spandrel.upscale"
    assert model.state == "available"
    assert model.license == "MIT"
    assert model.gated is False

    profile = model.upscale or {}
    # 寸法が変わらないので、入力の上限は取り込みの上限そのものでよい。
    assert profile["scale"] == 1
    assert profile["max_source_pixels"] == 24_000_000
    assert profile["max_source_pixels"] * profile["scale"] ** 2 <= 24_000_000
    assert model.default_steps is None
    assert model.execution_peak_vram_bytes == 405_778_944
    assert model.measured_runtime_sec == 24.5
