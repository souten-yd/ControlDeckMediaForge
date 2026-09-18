#!/usr/bin/env bash
# TRELLIS.2 / Pixal3D の ROCm 環境を、この機体（gfx1201 / RDNA4 / ROCm 7.2.1）に
# ゼロから組み直す。重みは含まない（別途 fetch-rocm-weights.sh）。
#
# 素の上流手順では入らない。要るのは主に4つで、理由は
# docs/implementation/g9-image-to-3d.md §1.2〜§1.6 に実測とともに残してある。
#
#   1. torch の ROCM_HOME 自動判定がこの機体では /opt/rocm-7.2.1/core-10.0 を掴む。
#      そこに include/hip が無いので、HIP 拡張が全部 hip_runtime.h not found で落ちる。
#   2. CuMesh は上流のままでは組めない。fork と3種のソース修正が要る。
#   3. FlexGEMM の Triton 設定が TF32 を前提にしている。ROCm には無い。
#   4. nvdiffrast の CUDA ラスタライザは PTX なので移植できない。OpenGL 版へ差し替える。
#
# 前提: ROCm 7.2.1、hipcc、libegl1-mesa-dev、Python 3.12。
# 所要: 20〜30 分（大半が拡張のコンパイル）。
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
PROBE="${REPO_ROOT}/runtimes/trellis2-probe"
VENV="${PROBE}/.venv"
PY="${VENV}/bin/python"
WORK="${WORK:-/data1tb/ControlDeck/data/feature-data/media-forge/runtimes}"
EXT="${WORK}/trellis2-ext"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/data1tb/ControlDeck/data/cache/pip}"

# torch の自動判定はこの機体では当てにならない。明示する。
export ROCM_HOME=/opt/rocm
export ROCM_PATH=/opt/rocm
export GPU_ARCHS="${GPU_ARCHS:-gfx1201}"
export BUILD_TARGET=rocm
export MAX_JOBS="${MAX_JOBS:-16}"

step() { echo; echo "=== $* ==="; }

step "venv と基本依存"
[ -x "$PY" ] || python3 -m venv "$VENV"
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r "${PROBE}/requirements.txt"

step "ソースを取る"
mkdir -p "$EXT"
[ -d "${WORK}/trellis2-source" ] || \
    git clone -q -b main --recursive --depth 1 https://github.com/microsoft/TRELLIS.2.git "${WORK}/trellis2-source"
# CuMesh は上流ではなく fork を使う。上流は HIP で組めない。
[ -d "${EXT}/CuMesh" ] || \
    git clone -q --recursive --depth 1 https://github.com/visualbruno/CuMesh.git "${EXT}/CuMesh"
[ -d "${EXT}/FlexGEMM" ] || \
    git clone -q --recursive --depth 1 https://github.com/JeffreyXiang/FlexGEMM.git "${EXT}/FlexGEMM"

step "CuMesh へ ROCm パッチを当てる"
cd "${EXT}/CuMesh"
if ! grep -q CUMESH_TUPLE src/clean_up.cu; then
    # libcu++ の ::cuda::std::tuple は HIP に無い。rocprim::tuple へ替える。
    # rocprim::tuple は explicit constructor なのでブレース初期化も直す。
    sed -i 's/::cuda::std::tuple/CUMESH_TUPLE/g' src/clean_up.cu
    sed -i '/#include <cub\/cub.cuh>/a \
#ifdef __HIP_PLATFORM_AMD__\
#include <rocprim\/types\/tuple.hpp>\
#define CUMESH_TUPLE rocprim::tuple\
#else\
#define CUMESH_TUPLE ::cuda::std::tuple\
#endif' src/clean_up.cu
    sed -i 's/return {key\.x, key\.y, key\.z};/return CUMESH_TUPLE<int\&, int\&, int\&>(key.x, key.y, key.z);/' src/clean_up.cu
fi
# hipcub::DeviceSegmentedReduce は identity を host から作る。既定 constructor を host でも呼べるように。
sed -i 's/__device__ __forceinline__ Vec3f();/__host__ __device__ __forceinline__ Vec3f();/' src/dtypes.cuh
sed -i 's/^__device__ __forceinline__ Vec3f::Vec3f() {/__host__ __device__ __forceinline__ Vec3f::Vec3f() {/' src/dtypes.cuh
# NVCC 専用フラグは hipcc が知らない。
sed -i -e '/"--extended-lambda",/d' -e '/"--expt-relaxed-constexpr",/d' \
       -e '/"-U__CUDA_NO_HALF_OPERATORS__",/d' -e '/"-U__CUDA_NO_HALF_CONVERSIONS__",/d' \
       -e '/"-U__CUDA_NO_HALF2_OPERATORS__",/d' setup.py
# cubvh は vendored で submodule ではないため、eigen を直接取る。
if [ ! -f third_party/cubvh/third_party/eigen/Eigen/Dense ]; then
    mkdir -p third_party/cubvh/third_party
    rm -rf third_party/cubvh/third_party/eigen
    git clone -q --depth 1 https://gitlab.com/libeigen/eigen.git third_party/cubvh/third_party/eigen
fi

step "ネイティブ拡張を組む（o_voxel / FlexGEMM / CuMesh）"
"$PY" -m pip install "${WORK}/trellis2-source/o-voxel" --no-build-isolation --no-deps
"$PY" -m pip install "${EXT}/FlexGEMM"                 --no-build-isolation --no-deps
"$PY" -m pip install "${EXT}/CuMesh"                   --no-build-isolation --no-deps

step "FlexGEMM の TF32 を止める"
SITE="$("$PY" -c 'import site; print(site.getsitepackages()[0])')"
CFG="${SITE}/flex_gemm/kernels/triton/spconv/config.py"
if [ -f "$CFG" ] && ! grep -q 'torch.version, "hip"' "$CFG"; then
    grep -q "^import torch" "$CFG" || sed -i '1s/^/import torch\n/' "$CFG"
    # TF32 は NVIDIA 専用。ROCm の Triton は ieee / bf16x3 / bf16x6 しか持たない。
    sed -i 's/^allow_tf32 = True$/allow_tf32 = not getattr(torch.version, "hip", None)/' "$CFG"
fi
rm -rf ~/.triton/cache 2>/dev/null || true
curl -fsSL -o "${SITE}/cumesh/remeshing.py" \
    "https://raw.githubusercontent.com/visualbruno/CuMesh/main/cumesh/remeshing.py"

step "nvdiffrast と nvdiffrec を組む"
bash "${PROBE}/build-nvdiffrast-rocm.sh"

step "TRELLIS.2 のソースへパッチを当てる"
bash "${PROBE}/patch-trellis2-source.sh" "${WORK}/trellis2-source"

step "確認"
cd /tmp && "$PY" - <<'PY'
import torch
print("torch", torch.__version__, "device", torch.cuda.get_device_properties(0).gcnArchName)
for m in ("flex_gemm", "cumesh", "nvdiffrast.torch", "nvdiffrec_render", "o_voxel"):
    __import__(m); print(f"  {m:20} OK")
import nvdiffrast.torch as dr
ctx = dr.RasterizeGLContext(output_db=True, device="cuda")
pos = torch.tensor([[[-0.8,-0.8,0.,1.],[0.8,-0.8,0.,1.],[0.,0.8,0.,1.]]], dtype=torch.float32, device="cuda")
tri = torch.tensor([[0,1,2]], dtype=torch.int32, device="cuda")
rast, _ = dr.rasterize(ctx, pos, tri, resolution=[64,64])
covered = int((rast[...,3] > 0).sum())
assert 1100 < covered < 1500, f"ラスタライズの被覆が想定外: {covered}"
print(f"  RasterizeGLContext   OK (被覆 {covered}/4096)")
# hipBLASLt は gfx1201 で fp32 GEMM を壊す。ROCBLAS_USE_HIPBLASLT=0 が要る。
a = torch.randn(1 << 20, 64); b = torch.randn(64, 32)
bad = int(((a.cuda() @ b.cuda()).cpu() - (a @ b)).abs().gt(1e-3).sum())
print(f"  fp32 GEMM            {'OK' if bad == 0 else f'壊れている（{bad:,} 要素）— ROCBLAS_USE_HIPBLASLT=0 を設定すること'}")
PY

echo
echo "完了。実行時は必ず以下を設定すること:"
echo "  ROCBLAS_USE_HIPBLASLT=0   # これが無いと fp32 GEMM が黙って壊れる"
echo "  ATTN_BACKEND=sdpa SPARSE_ATTN_BACKEND=sdpa"
echo "  HF_HOME=/data1tb/ControlDeck/data/feature-data/media-forge/hf-cache"
