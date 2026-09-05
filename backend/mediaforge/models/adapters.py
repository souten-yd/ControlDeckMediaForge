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
    # 拡大は標本化しない。prompt も seed も無く、同じ絵からは同じ絵が出る。
    # 生成ではないが、core が起動する画像 worker の経路としては同じである。
    "spandrel.upscale",
    # FLUX.2-dev 32B。GGUF を stable-diffusion.cpp の pinned build で回す。
    # 動画側の MiniMax H3 と同じ駆動系・同じ commit である。
    "native.stable-diffusion-cpp-flux2",
})

# 動画 worker（worker_packs/video/worker.py）が実装するもの。
# native の方は stable-diffusion.cpp の pinned build（sd-cli）を叩く。python の
# 重い依存を必要とせず、評価で実際に 640x384 の動画を作れている駆動系である。
VIDEO_ADAPTERS = frozenset({
    "diffusers.wan2.1-t2v",
    "native.stable-diffusion-cpp-minimax-h3",
    # 上流の wan package を使う。テキスト符号化と生成を別 process にする作りで、
    # 評価がその形で実際に動かしている。
    "native.wan2.2",
})

RUNNABLE_ADAPTERS = IMAGE_ADAPTERS | VIDEO_ADAPTERS


def is_runnable(runtime_adapter: str) -> bool:
    """このモデルを実際に走らせる worker が居るか。

    居ないものは、測れても選べるようにはならない。評価は候補を調べるための
    ものであって、採用の手続きではない。
    """
    return runtime_adapter in RUNNABLE_ADAPTERS


# CPU（システムRAM）だけで走らせられる adapter。ControlDeck の broker が
# `host` を割り当てたときはこの形で動かす。VRAM を確保しないことが host 配置の
# 条件なので（docs/design-ai-resource-broker.md §0）、GPU を前提にした駆動系は
# ここへ入れない。sd-cli 系と拡大は GPU 前提のまま。
# 画像生成は host（システムRAM）へ置かない。CPU 実行は実測で 1 枚 100 秒、GPU の
# 3.5 秒に対して 28 倍で、待つより LLM を退けたほうが速い。
#
# 「VRAM を少しだけ使って残りは RAM」も測ったが成立しなかった。FLUX.2 Klein 4B /
# 1024² で、group offload の粒度をどれだけ細かくしても VRAM の山は 8.3GB より
# 下がらず（blocks=4: 9.6GB, blocks=2: 8.6GB, blocks=1: 8.3GB）、時間だけが
# 18秒→33秒に伸びた。device_map="balanced" + max_memory は複数 GPU 用で、CPU と
# 混ぜると推論時に device 不一致で落ちる（2026-09-05 実測）。
#
# 空にすると minimum_bytes を宣言しなくなり、broker から見た下限が「全常駐量」に
# なる。入らなければ broker は LLM へ退去を頼み、断られればこの要求は待つ。
# 中途半端な枠で CPU へ落ちるより、退くのを待つほうが速い。
CPU_CAPABLE_ADAPTERS: frozenset[str] = frozenset()


def runs_on_cpu(runtime_adapter: str) -> bool:
    """VRAM を取らずに走らせられるか。host 配置を要求してよいかの判断に使う。"""
    return runtime_adapter in CPU_CAPABLE_ADAPTERS
