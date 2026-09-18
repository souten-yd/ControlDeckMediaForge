#!/usr/bin/env bash
# ROCm 経路の重みを取る。上流ライセンスを承諾した上で実行すること。
#
#   TRELLIS.2-4B  MIT              16.2 GB  単視点
#   Pixal3D       MIT              23   GB  多視点（_mv 一式）
#   DINOv3        gated（要 token）  1.2 GB  画像条件付け。両方が使う
#
# RMBG-2.0 も pipeline.json に載っているが gated（承認制）で取れない。
# 入力を切り抜き済み RGBA にすれば背景除去は通らないので、probe 側で無効化する。
set -euo pipefail
export HF_HOME="${HF_HOME:-/data1tb/ControlDeck/data/feature-data/media-forge/hf-cache}"
PY="${PY:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.venv/bin/python}"
WHICH="${1:-all}"

fetch() {
  "$PY" - "$1" "$2" <<'PY'
import sys
from huggingface_hub import snapshot_download
repo, revision = sys.argv[1], sys.argv[2]
extra = {"allow_patterns": ["*.json", "LICENSE", "NOTICE",
                            "ckpts/*_mv*", "ckpts/ss_dec_conv3d*",
                            "ckpts/shape_dec_next*", "ckpts/tex_dec_next*"]} \
        if repo == "TencentARC/Pixal3D" else {}
print("DONE", snapshot_download(repo, revision=revision, max_workers=4, **extra), flush=True)
PY
}

[ "$WHICH" = all ] || [ "$WHICH" = trellis2 ] && fetch microsoft/TRELLIS.2-4B af44b45f2e35a493886929c6d786e563ec68364d
[ "$WHICH" = all ] || [ "$WHICH" = pixal3d ]  && fetch TencentARC/Pixal3D      b0cb2e1b794cab9aa0ac38a95d794a4d9337437f
