#!/usr/bin/env bash
# TRELLIS.2 の Python ソースを、flash-attn の無い ROCm 機で動くようにする。
#
# 直すのは2か所だけで、どちらも「この機体に無いものを要求している」ことに対する手当て。
#
# 1. sparse transformer の attention backend が 'xformers' / 'flash_attn' /
#    'flash_attn_3' しか受け付けない。ATTN_BACKEND=sdpa を渡しても弾かれ、既定の
#    flash_attn のまま重みを読み終えたあとで ModuleNotFoundError になる。
#    'sdpa' を受け付けるようにし、PyTorch の scaled_dot_product_attention で
#    可変長 attention を実装する。
#
# 2. 全経路が dr.RasterizeCudaContext を使う。CUDA ラスタライザは PTX の
#    インラインアセンブリなので HIP へ移植できず stub になっている。
#    OpenGL ラスタライザへ差し替える。
#
# flash-attn を入れない理由は上流 setup.sh の HIP 分岐が GPU_ARCHS=gfx942（MI300）
# 決め打ちで、この機体（gfx1201 / RDNA4）に合わないため。
#
# Pixal3D は既に sdpa を受け付けるので 1 は当たらない（冪等に素通りする）。
# 冪等。何度流してもよい。
set -euo pipefail

SRC="${1:-/data1tb/ControlDeck/data/feature-data/media-forge/runtimes/trellis2-source}"
# TRELLIS.2 と Pixal3D はどちらも同じ形なので、package 名だけ見分ける。
if   [ -d "$SRC/trellis2" ]; then PKG=trellis2
elif [ -d "$SRC/pixal3d" ];  then PKG=pixal3d
else echo "TRELLIS.2 / Pixal3D のソースが見つからない: $SRC" >&2; exit 1; fi
echo "package: $PKG"

CONFIG="$SRC/$PKG/modules/sparse/config.py"
FULL_ATTN="$SRC/$PKG/modules/sparse/attention/full_attn.py"

# --- 1a. backend の許可一覧へ sdpa を足す ---
if ! grep -q "'sdpa'" "$CONFIG"; then
    sed -i "s/in \['xformers', 'flash_attn', 'flash_attn_3'\]/in ['xformers', 'flash_attn', 'flash_attn_3', 'sdpa']/" "$CONFIG"
    echo "config.py: sdpa を許可した"
fi

# --- 1b. sdpa の実装を足す ---
if ! grep -q "config.ATTN == 'sdpa'" "$FULL_ATTN"; then
    python3 - "$FULL_ATTN" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
anchor = "    elif config.ATTN == 'flash_attn':"
branch = '''    elif config.ATTN == 'sdpa':
        # flash-attn の無い機体向け。可変長の並びを配列ごとに切って
        # PyTorch の scaled_dot_product_attention へ渡す。
        # 融合されていないぶん遅いが、同じものを計算する。
        import torch.nn.functional as _F
        if num_all_args == 1:
            q, k, v = qkv.unbind(dim=1)
            kv_lens = q_seqlen
        elif num_all_args == 2:
            k, v = kv.unbind(dim=1)
            kv_lens = kv_seqlen
        else:
            kv_lens = kv_seqlen
        outs = []
        q_at = 0
        kv_at = 0
        for q_len, kv_len in zip(q_seqlen, kv_lens):
            qi = q[q_at:q_at + q_len].transpose(0, 1).unsqueeze(0)
            ki = k[kv_at:kv_at + kv_len].transpose(0, 1).unsqueeze(0)
            vi = v[kv_at:kv_at + kv_len].transpose(0, 1).unsqueeze(0)
            oi = _F.scaled_dot_product_attention(qi, ki, vi)
            outs.append(oi.squeeze(0).transpose(0, 1))
            q_at += q_len
            kv_at += kv_len
        out = torch.cat(outs, dim=0)
'''
assert anchor in source, "flash_attn の分岐が見つからない"
path.write_text(source.replace(anchor, branch + anchor, 1), encoding="utf-8")
print("full_attn.py: sdpa の実装を足した")
PY
fi

# --- 2. CUDA ラスタライザを OpenGL ラスタライザへ差し替える ---
changed=0
while IFS= read -r f; do
    sed -i 's/RasterizeCudaContext/RasterizeGLContext/g' "$f"
    changed=$((changed + 1))
done < <(grep -rl "RasterizeCudaContext" "$SRC/$PKG" 2>/dev/null || true)
[ "$changed" -gt 0 ] && echo "RasterizeCudaContext → RasterizeGLContext: ${changed} files"

echo "done"
