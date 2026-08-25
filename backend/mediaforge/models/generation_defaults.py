"""そのモデルを回すときの歩数と画面寸法を、モデル自身の中身から決める。

ここを取り違えると、モデルが正常でも絵が出ない。実測した 3 枚:

* SDXL base を 1024x1024 / 4 歩 → にじんだ壁に破片が浮くだけ
* SDXL base を 512x512 / 8 歩 → 指示した被写体が存在しない別の絵
* SDXL base を 1024x1024 / 30 歩 → 指示どおりの写真

4 歩は FLUX.2 Klein の値である。蒸留済みのモデル 1 つに合わせた数を全形式の
既定にしていたので、SD 系は必ず崩れていた。共通の既定は置けない。

寸法は推測しない。``unet.sample_size`` × VAE の縮小率が、そのモデルが学習
された寸法である。実測: SDXL / SSD-1B は sample_size 128 × 8 = 1024、
SD 1.5 は 64 × 8 = 512。55 の形式のどれでも、repository の中身から同じ手順で
出る。

歩数は中身からは出ない。scheduler が LCM/TCD なら少歩数だと分かるが、
SDXL Turbo も SDXL Lightning も素の SDXL と同じ pipeline クラスと scheduler を
名乗る。ここは分からないと認めて、多い側に倒す。多い分は時間を損するだけで
絵は出るが、少なすぎると絵が出ない。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 蒸留済みで、pipeline クラスから確実に分かるもの。
_FEW_STEP_PIPELINES = {
    "Flux2KleinPipeline": 4,
    "LatentConsistencyModelPipeline": 8,
    "StableCascadeCombinedPipeline": 20,
    "WuerstchenCombinedPipeline": 20,
}
# scheduler が名乗るなら、そちらが pipeline クラスより確かである。
_FEW_STEP_SCHEDULERS = {"LCMScheduler": 8, "TCDScheduler": 8}
DEFAULT_DIFFUSION_STEPS = 30
FALLBACK_NATIVE_SIDE = 1024
# 潜在空間の 1 マスが画素いくつ分か。ここを外れる寸法は、その 1 マスの
# 途中で切ることになり、端に破綻が出る。
LATENT_BLOCK = 64


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
    except (OSError, ValueError):
        return {}
    return document if isinstance(document, dict) else {}


def native_side_from_config(root: Path) -> int | None:
    """そのモデルが学習された 1 辺を、モデル自身の config から求める。

    ``sample_size`` は潜在空間の 1 辺なので、VAE の縮小率を掛けて画素に戻す。
    縮小率は VAE の ``block_out_channels`` の段数から決まる（段ごとに 1/2）。

    読めなければ None を返す。推測した値を「そのモデルの寸法」として記録
    すると、崩れた絵が出る理由が設定のどこにも残らない。
    """
    for component in ("unet", "transformer"):
        sample_size = _read_json(root / component / "config.json").get("sample_size")
        if isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size <= 0:
            continue
        channels = _read_json(root / "vae" / "config.json").get("block_out_channels")
        if not isinstance(channels, list) or not channels:
            continue
        side = sample_size * (2 ** (len(channels) - 1))
        if 256 <= side <= 2048 and side % LATENT_BLOCK == 0:
            return side
    # transformer 系は sample_size を持たないことがある。VAE が画素で持って
    # いる場合はそれを使う（FLUX.2 Klein がこの形）。
    vae_sample = _read_json(root / "vae" / "config.json").get("sample_size")
    if (
        not isinstance(vae_sample, bool)
        and isinstance(vae_sample, int)
        and 256 <= vae_sample <= 2048
        and vae_sample % LATENT_BLOCK == 0
    ):
        return vae_sample
    return None


def pipeline_class_from_config(root: Path) -> str:
    """``model_index.json`` が名乗る pipeline クラス。無ければ空文字。"""
    return str(_read_json(root / "model_index.json").get("_class_name") or "")


def steps_for(pipeline_class: str, root: Path | None = None) -> int:
    """歩数。scheduler が少歩数だと名乗ればそれに従う。"""
    if root is not None:
        scheduler = _read_json(root / "scheduler" / "scheduler_config.json")
        distilled = _FEW_STEP_SCHEDULERS.get(str(scheduler.get("_class_name") or ""))
        if distilled is not None:
            return distilled
    return _FEW_STEP_PIPELINES.get(pipeline_class, DEFAULT_DIFFUSION_STEPS)


def resolution_buckets(native_side: int) -> tuple[tuple[int, int], ...]:
    """そのモデルが扱える寸法の一覧を、学習寸法から組み立てる。

    表を持たない。SDXL の公表バケット（1024x1024, 1152x896, 1216x832,
    1344x768, 1536x640 とその転置）は「64 の倍数で、面積が 1024^2 に近い」
    ものの集合そのものなので、学習寸法さえ分かれば同じ列が出る。表で持つと
    SDXL 以外に効かないうえ、新しい形式が出るたびに書き足すことになる。

    面積を学習時に揃えるのが要点である。総画素を増やすと、モデルが見たことの
    ない広さになり、同じ被写体が 2 つ並ぶ。
    """
    budget = native_side * native_side
    found: dict[tuple[int, int], int] = {}
    for width in range(LATENT_BLOCK * 4, 2048 + 1, LATENT_BLOCK):
        # 面積を超えない範囲で、いちばん budget に近い高さ。
        height = (budget // width) // LATENT_BLOCK * LATENT_BLOCK
        if height < LATENT_BLOCK * 4 or height > 2048:
            continue
        area = width * height
        # 学習時の面積から 1 割以上離れたものは、そのモデルの寸法ではない。
        if abs(area - budget) > budget * 0.1:
            continue
        found[(width, height)] = area
    return tuple(sorted(found))


def snap_to_native(
    width: int, height: int, native_side: int
) -> tuple[int, int]:
    """求められた縦横比を保ったまま、そのモデルが扱える寸法に寄せる。

    利用者が指定するのは「横長が欲しい」であって画素数ではない。比を守り、
    面積を学習時に合わせるのが、そのモデルにとって本来の設定になる。
    """
    buckets = resolution_buckets(native_side)
    if not buckets:
        return width, height
    target = width / height if height else 1.0
    # 比が最も近いもの。同じなら学習寸法に近い方（面積差が小さい方）。
    return min(
        buckets,
        key=lambda size: (
            round(abs(size[0] / size[1] - target), 4),
            abs(size[0] * size[1] - native_side * native_side),
        ),
    )
