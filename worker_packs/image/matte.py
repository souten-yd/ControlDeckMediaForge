"""被写体の形を推定して、切り抜きのためのマスクを書き出す。

クロマキー（単色背景で描かせて、背景色と等しい画素を抜く）は、背景色が被写体
の縁へ滲む分をどうしても残す。業界でも「キーイングとは別に despill という工程
が要る」とされているもので、閾値の調整では消えない。実測（唐揚げダンジョンの
slime を参照にした編集）では、残った画素の 3.5〜6.1% が桃色だった。

ここでは背景色を当てにせず、被写体の形そのものを推定する。BiRefNet（MIT）の
ONNX を CPU で回す。GPU は画像モデルが使っているので取り合いにしない。実測で
512² も 1024² も 4 秒である。

出すのはマスクだけで、合成は core が行う。決定的な後処理は core に置く、
という切り分け（`cutout`、`conform_to_layout` と同じ）を崩さないためである。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 学習時の入力。前処理はモデルカードの preprocessor_config.json と揃える。
INPUT_SIDE = 1024
IMAGE_MEAN = (0.485, 0.456, 0.406)
IMAGE_STD = (0.229, 0.224, 0.225)


def _mask(image_path: Path, model_path: Path, mask_path: Path) -> dict[str, object]:
    import numpy as np
    import onnxruntime
    from PIL import Image

    with Image.open(image_path) as opened:
        opened.load()
        source = opened.convert("RGBA")
    # 透過を持つ画を渡されることがある（取り込んだ素材の作り直し）。透明を
    # そのまま RGB へ落とすと黒になり、モデルは黒い被写体を見ることになる。
    # 見えている部分だけを渡す。
    flattened = Image.new("RGB", source.size, (0, 0, 0))
    flattened.paste(source.convert("RGB"), mask=source.getchannel("A"))
    resized = flattened.resize((INPUT_SIDE, INPUT_SIDE), Image.Resampling.BILINEAR)

    array = np.asarray(resized, dtype=np.float32) / 255.0
    array = (array - np.array(IMAGE_MEAN, dtype=np.float32)) / np.array(IMAGE_STD, dtype=np.float32)
    tensor = np.transpose(array, (2, 0, 1))[None]

    session = onnxruntime.InferenceSession(
        str(model_path), providers=["CPUExecutionProvider"]
    )
    logits = session.run(None, {session.get_inputs()[0].name: tensor})[0]
    probability = 1.0 / (1.0 + np.exp(-logits[0, 0]))
    # 切り捨てると、確率 1.0 の画素が 254 になり被写体の内側まで半透明になる。
    # 丸める。
    mask = Image.fromarray(np.rint(probability * 255).astype(np.uint8), mode="L")
    mask = mask.resize(source.size, Image.Resampling.BILINEAR)
    mask.save(mask_path, format="PNG")
    return {
        "type": "result",
        "width": source.width,
        "height": source.height,
        "covered": float((np.asarray(mask) >= 128).mean()),
    }


def main() -> int:
    raw = sys.stdin.readline()
    try:
        request = json.loads(raw)
        result = _mask(
            Path(request["image_path"]),
            Path(request["model_path"]),
            Path(request["mask_path"]),
        )
    except Exception as exc:  # noqa: BLE001 - 失敗も 1 行で名乗る
        print(json.dumps({"type": "error", "message": str(exc)[:500]}), flush=True)
        return 1
    print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
