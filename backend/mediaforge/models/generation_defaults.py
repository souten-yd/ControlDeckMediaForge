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


# 歩数がどこから来たか。利用者に「これは分かっている値か、置いた値か」を
# 言えるようにする。分からないまま既定を出すと、絵が眠いときに何を触れば
# よいのかが分からない。
STEPS_FROM_MODEL = "model"      # scheduler か pipeline クラスが名乗った
STEPS_ASSUMED = "assumed"       # 判別できないので多い側に倒した
STEPS_DECLARED = "declared"     # 手元で実測して宣言してある


def steps_for(pipeline_class: str, root: Path | None = None) -> int:
    """歩数。scheduler が少歩数だと名乗ればそれに従う。"""
    return resolve_steps(pipeline_class, root)[0]


def resolve_steps(pipeline_class: str, root: Path | None = None) -> tuple[int, str]:
    """歩数と、その根拠。"""
    if root is not None:
        scheduler = _read_json(root / "scheduler" / "scheduler_config.json")
        distilled = _FEW_STEP_SCHEDULERS.get(str(scheduler.get("_class_name") or ""))
        if distilled is not None:
            return distilled, STEPS_FROM_MODEL
    if pipeline_class in _FEW_STEP_PIPELINES:
        return _FEW_STEP_PIPELINES[pipeline_class], STEPS_FROM_MODEL
    return DEFAULT_DIFFUSION_STEPS, STEPS_ASSUMED


def presets(steps: int, source: str, guidance_scale: float | None) -> tuple[dict, ...]:
    """詳細設定に出す組み合わせ。

    蒸留版（Turbo / Lightning / LCM）は素の親と同じ pipeline クラスと
    scheduler を名乗るので、自動では見分けられない。見分けられなかったときに
    利用者が 1 押しで切り替えられるように、その組み合わせをここで示す。
    数値は各配布元がモデルカードで示している値である。

    ガイダンス 0 は「CFG を使わない」という指示で、Turbo 系はそれを前提に
    蒸留されている。7.0 のまま 4 歩で回すと焼けた絵になる。
    """
    items = [{
        "id": "model_default",
        "label": "モデルの既定",
        "steps": steps,
        "guidance_scale": guidance_scale,
        "detail": "自動で判定した設定" if source != STEPS_ASSUMED else "判定できなかったので多い側に置いた値",
    }]
    if source == STEPS_ASSUMED:
        # 見分けられなかったときだけ出す。素のモデルにこれを勧めても崩れる。
        items.extend([
            {"id": "turbo", "label": "Turbo 系", "steps": 4, "guidance_scale": 0.0,
             "detail": "SDXL Turbo など。CFG を使わない前提で蒸留されている"},
            {"id": "lightning", "label": "Lightning / LCM", "steps": 8, "guidance_scale": 1.5,
             "detail": "少歩数で回す蒸留版。ガイダンスも低めにする"},
        ])
    items.append({
        "id": "quality", "label": "高品質", "steps": 50, "guidance_scale": guidance_scale,
        "detail": "時間を使って歩数を増やす。素のモデル向け",
    })
    return tuple(items)


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


def summary(
    *,
    steps: int | None,
    steps_source: str,
    native_width: int | None,
    native_height: int | None,
    guidance_scale: float | None,
) -> dict[str, Any]:
    """このモデルの設定のうち、何が決まっていて何が決まっていないか。

    利用者に見せる文面をここで作る。UI 側で組み立てると、同じ判断が 2 か所に
    分かれて片方だけ直る。決まった項目と確認が要る項目を 1 つの表にして返す
    ので、画面はそのまま並べればよい。
    """
    settled: list[dict[str, str]] = []
    check: list[dict[str, str]] = []

    if native_width and native_height:
        settled.append({
            "item": "画面寸法",
            "value": f"{native_width}×{native_height}",
            "source": "モデル自身の config から読み取り（sample_size × VAE 縮小率）",
        })
        settled.append({
            "item": "縦横比",
            "value": "学習時の面積に合わせて自動で寄せる",
            "source": f"{native_width}×{native_height} と同じ面積・64 の倍数の組み合わせ",
        })
    else:
        check.append({
            "item": "画面寸法",
            "value": "不明",
            "reason": "この配布物の config から学習寸法を読み取れませんでした。",
            "action": "配布元が示す寸法を詳細設定で指定してください。",
        })

    if steps is None:
        check.append({
            "item": "歩数",
            "value": "未設定",
            "reason": "この形式の歩数が分かりません。",
            "action": "配布元が示す歩数を詳細設定で指定してください。",
        })
    elif steps_source == STEPS_ASSUMED:
        check.append({
            "item": "歩数",
            "value": str(steps),
            "reason": (
                "蒸留版（Turbo / Lightning / LCM）かどうかは配布物から判別できません。"
                "蒸留版も素のモデルと同じ pipeline クラスと scheduler を名乗ります。"
            ),
            "action": (
                f"素のモデルなら {steps} 歩のままで問題ありません。"
                "蒸留版なら下のプリセットで切り替えてください（多すぎる歩数は"
                "時間を損するだけですが、ガイダンスが合わないと絵が焼けます）。"
            ),
        })
    else:
        settled.append({
            "item": "歩数",
            "value": str(steps),
            "source": (
                "手元で実測して宣言済み" if steps_source == STEPS_DECLARED
                else "モデルの scheduler / pipeline クラスが少歩数だと名乗っている"
            ),
        })

    if guidance_scale is not None:
        settled.append({
            "item": "ガイダンス",
            "value": f"{guidance_scale:g}",
            "source": "カタログで宣言済み",
        })
    elif steps_source == STEPS_ASSUMED:
        check.append({
            "item": "ガイダンス",
            "value": "既定（7.0）",
            "reason": "蒸留版はこの値では絵が焼けます。判別できていません。",
            "action": "蒸留版ならプリセットで 0〜1.5 に下げてください。",
        })

    return {"settled": settled, "needs_check": check}


# 単一ファイルの checkpoint と LoRA が名乗る base model を、系統として揃える。
# worker pack 側の同名関数と同じ判断でなければならない。core は worker を
# import できないので写しになっており、ずれたら test_lora が気づく。
_FAMILY_PREFIXES = (
    ("sd35", "sd35"), ("sd3", "sd3"),
    ("sdxl", "sdxl"), ("pony", "pony"),
    ("illustrious", "illustrious"), ("noobai", "noobai"),
    ("sd15", "sd15"), ("sd20", "sd20"), ("sd21", "sd21"),
    ("sd1", "sd15"), ("sd2", "sd21"),
)
# pipeline クラスから見た系統。Hugging Face から入れた diffusers 形式は
# base model を名乗らないので、LoRA を載せられるかを判断する材料が無い。
_PIPELINE_FAMILIES = {
    "StableDiffusionXLPipeline": "SDXL 1.0",
    "StableDiffusionXLPAGPipeline": "SDXL 1.0",
    "StableDiffusionPipeline": "SD 1.5",
    "StableDiffusionPAGPipeline": "SD 1.5",
    "StableDiffusion3Pipeline": "SD 3",
}


def normalize_base_model(value: str) -> str:
    folded = "".join(character for character in (value or "").lower() if character.isalnum())
    for prefix, key in _FAMILY_PREFIXES:
        if folded.startswith(prefix):
            return key
    return ""


def base_model_from_config(root: Path) -> str:
    """その repository が名乗る pipeline から、系統名を決める。

    宣言が無いものに LoRA を載せられるかを判断する材料になる。分からない
    ものは空にする。当てると、載らない組み合わせを載せられると言うことになる。
    """
    return _PIPELINE_FAMILIES.get(pipeline_class_from_config(root), "")
