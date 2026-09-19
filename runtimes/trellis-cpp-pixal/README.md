# Pixal3D native Vulkan port — projection, DiT and checkpoints

These are the first components of the user-requested Pixal3D port onto trellis.cpp.
It is not yet a complete Pixal3D runner and does not enable MediaForge's Pixal3D
capability. The installed trellis.cpp runtime and generated GLBs are unchanged.

The C++ implementation preserves upstream's single-image front-view projection,
Blender coordinate conversion, image pixel-center offset, bilinear border
sampling and sparse coordinate order. Coordinates/indices are planned on the
host; feature gathering and interpolation are a GGML graph using get_rows,
multiply and add. The selected backend must support every graph operation;
the check driver has no scheduler that could silently fall back to CPU.

Fixed external inputs:

- trellis.cpp: `2516c48b677050c570f47eba2e68dc8a5bc918b0`
- its GGML: `737e88f25d4f62254f3b7a726fd9663036cc94da`
- Pixal3D reference: `f7cf38429b0bd264f1995f0f8743a88b1c728b94`

CMake checks source revisions. It links an existing matching trellis.cpp build;
this check is not a claim that an arbitrary build directory has trusted binary
provenance. Evaluation/adoption must also record and verify the library hashes.
No binary, model weight, venv, GPU driver or separate service is shipped here.

```sh
cmake -S runtimes/trellis-cpp-pixal/native -B /tmp/pixal-projection-build \
  -DTRELLIS_SOURCE_DIR="$TRELLIS_SOURCE" -DTRELLIS_BUILD_DIR="$TRELLIS_BUILD"
cmake --build /tmp/pixal-projection-build -j 4
"$PIXAL_PYTHON" runtimes/trellis-cpp-pixal/check_projection.py \
  --pixal-source "$PIXAL_SOURCE" \
  --binary /tmp/pixal-projection-build/pixal-projection-check \
  --output-dir "$PIXAL_PROJECTION_REPORT" --backend cpu
```

The checker verifies the pinned, unmodified reference file and executes only
its projection functions/class. It uses synthetic tensors on CPU, without
loading models or importing the full GPU-dependent trainer package. Do not run
it in MediaForge's core environment. The test executable accepts locally
created NPY fixtures only; it is not an untrusted upload endpoint.

After acquiring a genuine Host GPU lease, the same checker can select
`--backend vulkan --device-index N`. The index must be mapped to the actual
broker device. The checker does not acquire, fabricate or verify a Host lease;
its caller owns admission, renewal, termination and release. No Vulkan test
has been executed yet.

Measured CPU results: six cases passed (dense grid, non-power-of-two grid,
one-pixel feature map, border/behind-camera coordinates, reordered/repeated
sparse coordinates, and higher-resolution texture projection). Maximum absolute
error versus upstream torch was `1.621246337890625e-05`; tolerance is
`atol=3e-5, rtol=2e-5`. Invalid scale was rejected. Torch GPU initialized=false.
The upstream computed visibility mask is intentionally not applied, matching
ProjGrid's actual behavior even for behind-camera points.

Evidence: managed data `maintenance/g9-pixal-vulkan-20260919/projection-cpu/`.
Full-model generation, Vulkan numerical parity, performance, memory, visual
quality and Library publication remain NOT TESTED. See
[remaining port work](../../docs/implementation/g9-pixal3d-vulkan-port.md).

## Projected DiT graph

`patches/projected-dit.patch` adds optional per-block projected conditioning to
the pinned trellis.cpp graph. `prepare_trellis.py` materializes two canonical
source files from Git into a separate build directory, applies the patch there,
and records original/patched hashes. Existing runtime sources are not edited.
Reusing a differing generated directory fails instead of silently overwriting it.
CMake names generated directories by patch hash and builds both the patched
and unmodified graph test drivers against the same GGML libraries.

The new `DiTParams.proj_in_channels` defaults to zero (existing TRELLIS mode).
A positive value requires the exact `[projected_channels, token_count]` F32
condition. It selects `cross_attn.cross_attn_block` weights and adds each block's
`cross_attn.proj_linear` output. A missing/misshaped projected input is an error;
zero-valued negative conditioning remains a real input and retains learned bias.

`DiTParams.exact_gelu` is an opt-in F32 tanh GELU graph. The default remains the
existing GGML GELU. The initial strict F32 comparison localized an error up to
0.00021521 to GGML CPU's FP16 GELU lookup, while the new projected combination
already matched within 4.77e-7. Enabling the F32 formula reduced the full tiny
model comparison below 9.54e-7 without relaxing its tolerance.

```sh
"$PIXAL_PYTHON" runtimes/trellis-cpp-pixal/check_dit.py \
  --pixal-source "$PIXAL_SOURCE" \
  --binary /tmp/pixal-projection-build/pixal-dit-check \
  --baseline-binary /tmp/pixal-projection-build/pixal-dit-baseline-check \
  --output-dir "$PIXAL_DIT_REPORT" --backend cpu
```

The checker instantiates the pinned upstream sparse-structure flow class with
small dimensions and deterministic synthetic parameters. It does not use a
pretrained checkpoint. Exact F32 attention isolates the graph changes from
FlashAttention's separate low-precision behavior. The five measured cases cover
ordinary cross attention, projected conditioning, concatenated-feature channel
width, all-zero conditioning, and a single graph connecting native image-feature
projection to both DiT blocks and the final output. All 59 tensor comparisons
passed with maximum absolute error `9.5367431640625e-07` (atol/rtol=5e-5).
The legacy/default GELU mode also matched the separately compiled unmodified
upstream executable bit-for-bit for every retained intermediate/output. Missing
and incorrectly shaped projected inputs were rejected. Torch GPU initialized=false.

Evidence: managed data `maintenance/g9-pixal-dit-20260919/cpu-combined` and the
initial `cpu` / `cpu-exact` results, with build manifests and binary/library hashes.
Vulkan execution, real trained weights, BF16/FlashAttention parity, sampler
integration, DINO/NAF/MoGe execution and full image-to-GLB generation are still
NOT TESTED. These source components alone do not enable runtime adoption.

## Flow checkpoint conversion

`convert_flow.py` converts a local, authorized checkpoint (`.safetensors` plus
its `{name,args}` inference JSON) into a new directory containing `model.gguf`
and `manifest.json`. It uses the [official GGUF writer](https://github.com/ggml-org/llama.cpp/tree/master/gguf-py),
pinned by `gguf-lock.txt`, and the worker environment's safetensors reader.
Install the extra package into the isolated Pixal environment only:

```sh
"$PIXAL_PYTHON" -m pip install --require-hashes --no-deps \
  -r runtimes/trellis-cpp-pixal/gguf-lock.txt
"$PIXAL_PYTHON" runtimes/trellis-cpp-pixal/convert_flow.py \
  --checkpoint "$PIXAL_CHECKPOINT" --config "$PIXAL_CHECKPOINT_CONFIG" \
  --stage ss --storage f32 --source-kind checkpoint \
  --source-repository "$PIXAL_MODEL_REPOSITORY" --source-revision "$PIXAL_MODEL_REVISION" \
  --output-dir "$PIXAL_CONVERTED_DIRECTORY"
```

The converter supports the implemented projected/shared-modulation/RoPE/QK RMS
flow configuration for `ss`, `shape`, and `texture`. It validates the exact set
of parameter names and shapes, preserves nested projection weights, and rejects
unknown settings, missing/extra parameters, non-finite tensors, truncated files
and F16 overflow. It never executes pickle or a remote model loader. F32 is the
default; optional F16 storage converts linear matrices while retaining biases
and normalization values (including rank-two RMS gamma) in F32. One tensor is
converted at a time into the writer's temporary spool. No trained checkpoint
has been converted or tested yet.

GGUF metadata carries a private versioned architecture, explicit stage/dimensions,
source/config hashes and fixed reference revision. The manifest adds output and
tensor hashes plus converter/package provenance. Conversion checks source hashes
again before publishing the completed directory and refuses an existing output.
`inspect_flow_checkpoint` validates metadata and every tensor's name/type/shape
before backend allocation. These are trusted runtime artifacts, not Library
uploads. Manifest hashes are provenance evidence; runtime adoption must separately
verify the admitted artifact against its pinned receipt. Conversion does not
assert license acceptance, enable a capability or write an adoption receipt.

```sh
"$PIXAL_PYTHON" runtimes/trellis-cpp-pixal/check_checkpoint.py \
  --pixal-source "$PIXAL_SOURCE" \
  --binary /tmp/pixal-projection-build/pixal-dit-check \
  --output-dir "$PIXAL_CHECKPOINT_REPORT"
```

Measured CPU checks: six cases, using the actual upstream dense SS and sparse
ElasticSLat classes with all parameters replaced by deterministic synthetic
values. All serialized values match exactly; all 72 native intermediate/output
comparisons pass (max absolute error `7.152557373046875e-07`, atol/rtol=5e-5).
Cases cover F32, BF16 and F16 source tensors, F32/F16 storage, reordered/repeated
sparse coordinates and doubled texture input channels. Arithmetic is explicitly
F32 even for F16 storage; this does not validate mixed-precision/Vulkan execution.
Dimensions come from GGUF, without the previous NPY driver's `params.txt`.
Twelve converter rejection checks and nine native pre-allocation rejection
checks pass, and repeated conversion produces identical GGUF bytes. The existing
five-case DiT and bitwise legacy regression checks still pass.

Evidence: managed data `maintenance/g9-pixal-checkpoint-20260919/cpu-release` and
`dit-regression`. Torch GPU initialized=false. The first run reached all six
positive cases but its negative-fixture writer refused a non-contiguous slice;
the fixture was made contiguous before the complete rerun. No tolerance changed.
Real checkpoints, mixed precision, sampler integration, Vulkan and full generated
assets remain NOT TESTED. The next step is stage-runner/sampler integration with
both positive and negative projected conditions and explicit backend ownership.
