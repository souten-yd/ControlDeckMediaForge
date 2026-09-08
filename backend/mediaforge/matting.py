"""被写体の形を推定する経路。重い依存は core に持ち込まない。

クロマキーは背景色が縁へ滲むぶんを残す。閾値では消えない性質のもので、実測
（唐揚げダンジョンの slime を参照にした編集）では残った画素の 3.5〜6.1% が
桃色だった。形そのものを推定すれば、背景色という前提ごと無くなる。

推論は画像ランタイム（`rocm-torch`）の中で走らせる。core は PyInstaller で
固める側なので、onnxruntime と numpy を抱えさせると配布物が数倍になる。
起動から結果まで実測 5.5 秒（session 作成 1.5 + 推論 4.0、CPU）で、
GPU は画像モデルが使うので触らない。

決めるのは core である。ここは「マスクを取ってくる」だけを受け持ち、それを
資産にしてよいかは `cutout.apply_matte` が判断する。
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

# 形を推定する重み。MIT で、CPU で回せる大きさのものを選んでいる。
MATTING_MODEL_ID = "onnx-community/BiRefNet_lite-ONNX"
MATTING_WEIGHTS = "onnx/model.onnx"

# 起動 1.5 秒＋推論 4 秒が実測値。詰まったときに job を道連れにしない幅を取る。
MATTING_TIMEOUT_SEC = 120


class MattingUnavailable(RuntimeError):
    """推定の経路が使えない。呼び出し側はクロマキーへ退避する。"""


def matte_mask(
    image_path: Path,
    mask_path: Path,
    *,
    runtime_python: Path | None,
    model_path: Path | None,
    repository_root: Path,
    timeout_sec: int = MATTING_TIMEOUT_SEC,
) -> None:
    """`image_path` の被写体マスクを `mask_path` へ書く。

    使えないときは `MattingUnavailable` を投げる。呼び出し側は従来どおり
    クロマキーで抜けばよく、資産が出てこなくなることはない。
    """
    if runtime_python is None or not runtime_python.is_file():
        raise MattingUnavailable("image runtime is not installed")
    if model_path is None or not model_path.is_file():
        raise MattingUnavailable("matting weights are not installed")
    request = json.dumps({
        "image_path": str(image_path),
        "model_path": str(model_path),
        "mask_path": str(mask_path),
    })
    try:
        completed = subprocess.run(
            [str(runtime_python), "-m", "worker_packs.image.matte"],
            input=request + "\n",
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(repository_root),
            env={"PYTHONPATH": str(repository_root), "PATH": "/usr/bin:/bin"},
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MattingUnavailable(f"matting worker did not run: {exc}") from exc
    if completed.returncode != 0:
        raise MattingUnavailable(
            completed.stderr.strip()[-300:] or f"matting worker exited {completed.returncode}"
        )
    line = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    try:
        result = json.loads(line)
    except json.JSONDecodeError as exc:
        raise MattingUnavailable("matting worker emitted invalid protocol data") from exc
    if result.get("type") != "result":
        raise MattingUnavailable(str(result.get("message", "matting failed"))[:300])
    if not mask_path.is_file():
        raise MattingUnavailable("matting worker produced no mask")
