# Pixal3D isolated runtime preparation

This directory describes candidate software, not an adopted runtime. The core
environment and existing image workers must remain unchanged. Weight consent,
native extension validation, genuine Host admission, measured GPU execution and
actual output validation remain required before capability availability.

Source: TencentARC/Pixal3D, pinned commit
`f7cf38429b0bd264f1995f0f8743a88b1c728b94`. Source and notices are retained under
the managed runtime root as `pixal3d-source`; the separate environment is
`pixal3d-probe/.venv`. Weights belong in the managed model cache, not this venv.

`requirements.txt` pins the AMD ROCm 7.2.1 builds of torch/torchvision/Triton and
the Pixal3D Python dependencies. It does not execute `inference.py`, torch.hub,
model `from_pretrained`, GPU smoke tests or any weight downloader. Native
extensions, MoGe/NAF code and utils3d still require their own pinned sources and
verification. Do not run the upstream requirements unmodified: they select an
unpinned MoGe Git HEAD, and resolving plain torch can replace the ROCm build.

NATTEN 0.21.0 has an official pure Python Flex Attention backend. Install its
source/wheel without libnatten (CUDA kernel library) on this target. Its setup
autodetects GPUs, so set HIP/ROCR/CUDA visibility to `-1` during installation;
do not set a fake CUDA architecture. Record installation and import results
separately from a real broker-leased attention check. PyTorch import or a
successful package install alone does not prove ROCm inference support.

References:
- https://github.com/TencentARC/Pixal3D/tree/f7cf38429b0bd264f1995f0f8743a88b1c728b94
- https://github.com/SHI-Labs/NATTEN/tree/v0.21.0
- https://natten.org/install/#natten-via-pypi
- https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2.1/

## Repeatable software-only checks

The lock files record Python 3.12 / Linux x86-64 artifacts observed on this
machine. Use a new candidate venv. They are not a multi-platform lock.
Install in order, with GPU visibility disabled for each command:

```sh
# PIXAL_PYTHON is the candidate venv's absolute bin/python path.
env HIP_VISIBLE_DEVICES=-1 ROCR_VISIBLE_DEVICES=-1 CUDA_VISIBLE_DEVICES=-1 \
  "$PIXAL_PYTHON" -m pip install --require-hashes --no-deps -r python-lock.txt
env HIP_VISIBLE_DEVICES=-1 ROCR_VISIBLE_DEVICES=-1 CUDA_VISIBLE_DEVICES=-1 \
  "$PIXAL_PYTHON" -m pip install --require-hashes --no-deps --no-build-isolation -r natten-lock.txt
env HIP_VISIBLE_DEVICES=-1 ROCR_VISIBLE_DEVICES=-1 CUDA_VISIBLE_DEVICES=-1 \
  "$PIXAL_PYTHON" -m pip install --require-hashes --no-deps -r utils3d-lock.txt
```

NATTEN metadata imports torch, so it must be installed after the base lock.
`requirements.txt` documents the direct dependencies used for the initial
installation; use the artifact locks when reproducing that resolved environment.
The locks were generated from actual pip reports. Fresh installation from all
three lock files has not yet been tested.

Fetch the exact `sources.json` revisions into `pixal3d-probe/sources/<name>`;
Pixal3D itself resides in the sibling `pixal3d-source` directory. Initialize only
the recorded Eigen submodule in TRELLIS.2. MoGe is intentionally pinned to its
2.0 implementation: newer HEAD is MoGe 3 and resolves different dependencies.
MoGe and NAF are imported directly from their pinned source directories by the
preflight, without installing MoGe's unrelated Gradio/CLI dependency set or
executing NAF's weight-downloading hub entrypoint.

`o-voxel` and `FlexGEMM` were built with the candidate Python's
`pip install --no-deps --no-build-isolation <source-directory>`, with
`BUILD_TARGET=rocm`, `GPU_ARCHS=gfx1201`, `PYTORCH_ROCM_ARCH=gfx1201`,
`ROCM_HOME=/opt/rocm`, `ROCM_PATH=/opt/rocm`, `MAX_JOBS=4` and all three GPU
visibility variables set to `-1`. FlexGEMM setup writes to its home directory;
its build subprocess received a private `pixal3d-probe/build-home` as HOME.
The user's global cache was not modified. Build output includes generated
untracked HIP files; tracked upstream source files remain unchanged.

```sh
"$PIXAL_PYTHON" preflight.py --runtime-root "$PIXAL_RUNTIME_ROOT" \
  --output "$PIXAL_REPORT_PATH"
"$PIXAL_PYTHON" -m pip check
```

The preflight verifies source revisions and tracked edits before importing,
blocks network connections, hides GPUs, and performs only a tiny CPU attention
check. A failing import remains a failing check. In particular, FlexGEMM and
o-voxel Python wrappers inspect GPU properties while importing and fail when
GPUs are hidden; that is not evidence of a driver failure on visible hardware.
Lazy pipeline imports do not prove the pipeline is executable. No weights are
loaded and no runtime-adoption receipt is written.

## Observed preparation result (2026-09-19)

- AMD torch 2.10.0 / HIP 7.2.53211, torchvision, transformers 4.57.3,
  diffusers 0.37.1 and NATTEN 0.21.0 import. Tiny NATTEN CPU check passes.
- `utils3d`, MoGe 2's model module and NAF's model module import without weights.
- o-voxel builds in 45.187 seconds; its native `_C` module imports.
- FlexGEMM builds in 32.522 seconds. Its wrapper needs a visible GPU at import;
  a genuine Host lease is required for that next check.
- Unmodified pinned CuMesh fails to build in 32.763 seconds:
  `src/clean_up.hip:234:27: no member named 'cuda' in the global namespace`.
  CUDA tuple compatibility is a software build blocker, not model evaluation.
- CuMesh, nvdiffrast and nvdiffrec_render are not installed. Full software
  preflight exits 1. After adding o-voxel, `pip check` also exits 1 because
  its declared CuMesh dependency is missing (base Python-only check passed).
- Model loading, GPU inference, VRAM/runtime/quality evaluation, Library
  publication and adoption remain NOT TESTED.

Evidence: managed MediaForge data's
`maintenance/g9-runtime-preparation-20260919` (pip reports, compiler logs,
source pins, CPU/import reports). The user additionally requested a Pixal3D
Vulkan port. That work must add Pixal3D-specific execution to trellis.cpp;
these ROCm installation results do not establish Vulkan compatibility.
