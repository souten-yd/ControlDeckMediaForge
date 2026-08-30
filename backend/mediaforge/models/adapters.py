"""どの runtime adapter なら実際に走らせられるか。

core は worker の実装を import しない（AGENTS.md）。しかし「測れる」と
「使える」は別で、その差を利用者に伝えられないと、実行できないモデルの
評価に GPU を 161 秒使って何も選べるようにならない、ということが起きる。
実機で MiniMax がそうだった（2026-08-30）。

ここは core が起動できる adapter の一覧である。worker pack 側の ADAPTERS と
食い違わないことは test が見張る（test は worker を import してよい）。
"""

from __future__ import annotations

# 画像 worker（worker_packs/image/worker.py）が実装するもの。
IMAGE_ADAPTERS = frozenset({
    "diffusers.flux2-klein",
    "diffusers.sdxl",
    "diffusers.sdxl-single-file",
})

# 動画 worker（worker_packs/video/worker.py）が実装するもの。
# native の方は stable-diffusion.cpp の pinned build（sd-cli）を叩く。python の
# 重い依存を必要とせず、評価で実際に 640x384 の動画を作れている駆動系である。
VIDEO_ADAPTERS = frozenset({
    "diffusers.wan2.1-t2v",
    "native.stable-diffusion-cpp-minimax-h3",
})

RUNNABLE_ADAPTERS = IMAGE_ADAPTERS | VIDEO_ADAPTERS


def is_runnable(runtime_adapter: str) -> bool:
    """このモデルを実際に走らせる worker が居るか。

    居ないものは、測れても選べるようにはならない。評価は候補を調べるための
    ものであって、採用の手続きではない。
    """
    return runtime_adapter in RUNNABLE_ADAPTERS
