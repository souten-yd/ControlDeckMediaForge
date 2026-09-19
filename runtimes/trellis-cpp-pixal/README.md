# Pixal3D native Vulkan port — image features, NAF, projection and flow sampling

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
Real checkpoints, mixed precision, Vulkan and full generated assets remain
NOT TESTED. The following slice implements stage execution/sampling on synthetic
checkpoints, with both positive and negative projected conditions.

## Stage runner and Euler/CFG sampler

`native/flow_runner.h` provides `FlowModel`, `FlowRunner` and `sample_flow`.
`FlowModel` uploads validated GGUF weights to a caller-supplied backend, without
device enumeration, a largest-device heuristic, or fallback. The backend is
borrowed and must outlive the model and its runners. The caller owns Host
admission/renewal/release; the library cannot claim or create a lease.
Models/runners release their own weight/graph allocations on destruction and
constructor failure. They are used sequentially on their selected backend.

The runner builds and allocates one projected DiT graph for the stage's token
count, then reuses it. Every forward uploads all inputs, including both global
and projected conditions and the RoPE tables, because GGML's graph allocator
can reuse their storage. Latent and condition vectors are token-major with
contiguous channels. Sparse coordinate order/repeats are preserved; SS requires
the complete ordered dense grid. Texture concatenates the fixed normalized
shape condition after noisy texture channels for each token and returns only
texture velocity. The shape condition is never integrated by the sampler.

The sampler follows pinned Pixal3D's double-precision time schedule, inclusive
guidance interval, positive/negative dispatch, CFG and rescaling. Sparse std
uses the upstream SparseTensor moment formula; dense std uses corrected sample
variance. It does not inherit TRELLIS's CFG ratio clamp or replace NaN velocity
with zeros. Non-finite conditions/velocities/rescale/sample and invalid shapes
fail explicitly. Cancellation is checked before/after each model call, including
between the two CFG forwards and after the final forward; progress callbacks
report completed steps. Process cancellation during a GPU operation remains
the surrounding worker's responsibility.

```sh
"$PIXAL_PYTHON" runtimes/trellis-cpp-pixal/check_flow.py \
  --pixal-source "$PIXAL_SOURCE" \
  --checkpoint-fixtures "$PIXAL_CHECKPOINT_REPORT" \
  --binary /tmp/pixal-projection-build/pixal-flow-check \
  --output-dir "$PIXAL_FLOW_REPORT"
```

Measured CPU results: 10 conditions, 36 Euler steps, 108 velocity/clean/sample
comparisons against the actual pinned upstream sampler and SS/ElasticSLat models,
all passed. Maximum absolute error `1.6689300537109375e-06`, atol/rtol5e-5.
The exact timestep/positive-negative forward sequences match. Cases include
positive-only, negative-only, interval boundaries, time rescaling, CFG rescaling,
sparse shape, texture concatenation and one F16-storage/F32-arithmetic case.
An analytic scale canary independently exercises a ratio above TRELLIS's clamp.
Repeated sampling through the same allocated graph is bitwise identical, and
model/runner destruction retains the borrowed backend.

Eleven negative cases pass: missing positive/negative projection, missing
texture concatenation, non-finite/short velocity, three cancellation points,
zero-variance CFG, invalid steps and invalid coordinates. No output is published
on these failures. Previous checkpoint (72 comparisons) and DiT (59 comparisons,
legacy bitwise parity) regression checks also pass. Torch GPU initialized=false.

Evidence: managed data `maintenance/g9-pixal-runner-20260919/cpu-release` plus
checkpoint/DiT regression reports. These are small synthetic models. Full-stage
trained weights, Vulkan/mixed precision, actual image feature extraction,
DINO global token selection, NAF/MoGe, cascade/decoder/GLB integration and
MediaForge adoption/Library publication remain NOT TESTED. No capability is enabled.

## Pixels to image features and flow conditions

`native/image_features` adapts trellis.cpp's DINOv3 ViT graph to configurable
dimensions while preserving its existing weight naming. It validates RGB range,
image/config dimensions and required weight shapes; applies ImageNet
normalization; executes patch embedding, CLS/register insertion, RoPE, attention,
plain erf GELU MLPs and non-affine final normalization on the model's explicit
backend. Unsupported backend operations fail. The installed trellis.cpp source
and its original encoder are unchanged. Gated-MLP DINO variants are not supported.

The output separates CLS + register tokens from spatial patch features, matching
Pixal3D. `image_conditions` projects the patch feature map at dense/sparse voxel
coordinates, optionally projects supplied **actual NAF features** independently,
and concatenates LR then HR channels for each voxel. It returns explicit positive
conditions and equally shaped zero negative conditions for `FlowRunner`.

`prepare_image.prepare_rgb` uses the reference Pillow LANCZOS resize-before-RGB
order and returns contiguous unnormalized CHW floats. Its input is an image
already framed/composited by the pipeline. Foreground removal, alpha bounding
box/crop/background compositing and MoGe camera inference are separate work;
this helper does not claim to implement them. Unnormalized RGB remains available
as the NAF guide instead of reusing the normalized DINO input.

```sh
"$PIXAL_PYTHON" runtimes/trellis-cpp-pixal/check_image_features.py \
  --pixal-source "$PIXAL_SOURCE" \
  --checkpoint-fixtures "$PIXAL_CHECKPOINT_REPORT" \
  --binary /tmp/pixal-projection-build/pixal-image-check \
  --output-dir "$PIXAL_IMAGE_FEATURE_REPORT"
```

Measured CPU results: six image-feature cases, 99 tensor comparisons all passed,
maximum absolute error `1.1920928955078125e-06` at atol/rtol5e-5. The checker uses
transformers4.57.3's real two-layer DINO class with all parameters replaced by
synthetic values and the pinned, unmodified Pixal extractor/projection methods.
It never calls `from_pretrained`. It covers non-square source image resizing,
attention bias on/off, different head/register dimensions, one patch and supplied
HR features. All resize results match exactly. Five cases continue through the
native flow runner/sampler, comparing all 15 resulting latent states against
actual Pixal sampling. The 64-channel feature case does not run the 32-channel
synthetic flow. Supplied HR maps are synthetic; NAF inference was not tested.

Six invalid RGB/weight/camera/HR-channel cases fail with no published output.
Existing flow regression remains passed (10 cases/108 comparisons/11 negatives).
Torch GPU initialized=false. Evidence:
`maintenance/g9-pixal-dino-20260919/cpu-release` and `flow-regression`, including
RGB PNGs, NPY inputs/weights/intermediates and fixed reference source hashes.

Remaining: production DINO checkpoint conversion/metadata/loader binding, full
trained dimensions, F16/BF16/Vulkan, native NAF, foreground/camera/cascade/decoder
integration, generated GLB quality and installed Library/adoption/release checks.
These CPU synthetic results do not make image-to-3D available to users yet.

## NAF high-resolution image features

`native/naf` implements pinned [NAF](https://github.com/valeoai/NAF/tree/37f2dfc180f2de53d98bd601109c0da0dd6b0f43)
evaluation with existing GGML operations. It preserves both reflected-padding
convolution branches, GroupNorm/SiLU blocks, the exact guide-resize rule,
adaptive-average pooling, axial half-rotation using the checkpoint's persistent
periods, pooled keys and nearest-exact key/value sampling. Positional training
augmentation and encoder-disabled variants are not supported.

Attention shifts each neighborhood within the query's dilation residue class
at image borders. It gathers bounded tiles from LR keys/values rather than
materializing every pixel's expanded neighborhood. Q/K/V remain on the selected
backend between tiles; encoder intermediates are released before attention.
The output is the actual attention-weighted HR feature map, suitable for
`image_conditions`' LR/HR concatenation. No backend is chosen inside the library;
every operation must be supported by the caller's backend. Cancellation is
checked before/after encoder computation and each tile, including the last.

```sh
"$PIXAL_PYTHON" runtimes/trellis-cpp-pixal/check_naf.py \
  --naf-source "$NAF_SOURCE" --pixal-source "$PIXAL_SOURCE" \
  --checkpoint-fixtures "$PIXAL_CHECKPOINT_REPORT" \
  --binary /tmp/pixal-projection-build/pixal-naf-check \
  --output-dir "$PIXAL_NAF_REPORT"
```

Measured CPU results: nine synthetic cases and 115 tensor comparisons all pass,
max absolute error `1.3969838619232178e-05` at atol/rtol5e-5. The actual pinned
NAF class executes with all learned parameters replaced by synthetic values.
Its hard-coded cutlass call is redirected to NATTEN0.21.0's original CPU
`flex-fna`, without compilation. That backend requires equal QK/V head widths,
so independent V channels are split/padded while Q/K, attention scale and
NATTEN's neighborhood mask remain unchanged. This does not validate cutlass.

Cases cover irregular rectangular/adaptive bins, pooling to a larger output,
guide downsampling, unequal X/Y dilation, differing QK/V channel widths, default
256-channel/two-block/9x9 architecture, tile tails, and F16 storage with explicit
F32 arithmetic. Six cases continue through LR/HR projection and actual sparse
shape sampling, comparing all 18 sampled states with pinned Pixal code.
Different tile sizes give bitwise-identical output; repeating with/without
diagnostic intermediates also gives bitwise-identical output.

The regular fixture's attention graph allocates 36768 bytes with seven-pixel
tiles versus 236032 bytes with one 64-pixel tile, with identical outputs. The
default-architecture 18x18 fixture allocates 2578048 encoder bytes and 27019520
attention bytes. These are small CPU graph-buffer measurements, not process
peak memory, production performance, GPU VRAM or real trained-model evidence.
Ten invalid-input/cancellation cases fail without publishing output. Existing
DINO/image-to-flow regression also passes (six cases/99 comparisons/six negatives).

During development, intermediate retention exposed a GGML view-owner reuse
bug (query output changed by up to 0.088560 without diagnostics). Output owners
are now protected from reuse; strict tolerances were retained. Initial checker
failures from projection layout and unsupported one-neighbor reference settings
are retained in the evidence logs; fixtures were corrected to supported layouts
and neighborhoods. Torch GPU initialized=false. Evidence:
`maintenance/g9-pixal-naf-20260919/cpu-release` and `image-regression`.

Remaining: production NAF checkpoint conversion/metadata/loading, trained
weights, full-sized images, mixed-precision and Vulkan execution, full pipeline
foreground/camera/cascade/decoder/GLB integration and Library/adoption/release.
This component neither fetches weights nor enables a capability. Source licenses
and attribution are in `NOTICE`, `LICENSE.naf`, and `LICENSE.natten`.

## DINO/NAF checkpoint loading and connected image inference

`convert_vision.py` converts a local authorized DINOv3 ViT or NAF checkpoint
into a private `pixal3d-vision` GGUF and provenance manifest. DINO accepts the
Hugging Face config and a single safetensors file; NAF accepts safetensors or
an explicitly selected PyTorch archive and an inference config such as
`{"name":"NAF","args":{"dim":256,"heads_attn":4,"heads_rope":4,"kernel_size":9,"img_layers":2}}`.
NAF omitted arguments use the fixed upstream defaults. Unsupported settings,
unknown/missing/extra tensors, wrong shapes/types, non-finite values and storage
overflow fail. Encoder-disabled NAF, gated-MLP DINO and sharded checkpoints
are not supported. No model or pretrained loader is instantiated.

DINO Q/K/V matrices are fused in that order, filling only absent source biases
with zeros. Projection and MLP bias flags, layer-normalization epsilon and RoPE
base come from the validated config. The unused mask token and final affine
norm are still checked and hashed, with the reason for omission recorded:
Pixal uses unmasked patches and its own non-affine final normalization. NAF's
persistent periods buffer is preserved, including non-default values.
F16 storage applies only to linear/convolution matrices; tokens, normalization,
bias and periods remain F32. F32 storage is the default.

```sh
"$PIXAL_PYTHON" runtimes/trellis-cpp-pixal/convert_vision.py \
  --kind dino --checkpoint "$DINO_SAFETENSORS" --config "$DINO_CONFIG" \
  --storage f32 --source-kind checkpoint \
  --source-repository "$DINO_REPOSITORY" --source-revision "$DINO_REVISION" \
  --output-dir "$DINO_CONVERTED"
"$PIXAL_PYTHON" runtimes/trellis-cpp-pixal/convert_vision.py \
  --kind naf --input-format torch-weights-only \
  --checkpoint "$NAF_AUTHORIZED_ARCHIVE" --config "$NAF_INFERENCE_CONFIG" \
  --source-kind checkpoint --source-repository "$NAF_REPOSITORY" \
  --source-revision "$NAF_REVISION" --output-dir "$NAF_CONVERTED"
```

The NAF archive path uses the pinned worker torch2.10.0 reader with
`map_location="cpu", weights_only=True, mmap=True`. It requires a plain tensor
state dictionary and never retries with unrestricted pickle, registers custom
safe globals, or invokes hub entrypoints. This is for authorized local runtime
inputs, not untrusted Library uploads. Conversion stages output in a temporary
directory, verifies source/config hashes again, and refuses existing outputs.
Source/config/output/tensor hashes, source identity, format, package versions,
mapping and intentionally unused tensors are retained. A manifest is provenance
evidence; it neither grants model permission nor binds an adoption receipt.

`inspect_vision_checkpoint` verifies architecture/schema/reference, dimensions,
bias flags, the complete tensor table and data extents without a backend.
`VisionModel` validates the same metadata and loads from one owned file handle
onto the caller's borrowed backend. It checks finite values/positive periods
before uploading each tensor and releases allocations on failure/destruction.
There is no device heuristic or CPU fallback. Accepted local artifact identity
must still be verified against an admission/adoption receipt by the caller.

`encode_vision` connects the loaded DINO to optional loaded NAF, returning global,
LR and actual HR features for `image_conditions`. SS can request LR only.
For NAF, the caller must explicitly supply the stage's target size; it is not
guessed from the checkpoint or image. Models must use the same selected backend.
Input RGB is already foreground-framed; background removal and camera estimation
remain outside this helper. Cancellation is checked around DINO and by NAF.

```sh
"$PIXAL_PYTHON" runtimes/trellis-cpp-pixal/check_vision_checkpoints.py \
  --naf-source "$NAF_SOURCE" --pixal-source "$PIXAL_SOURCE" \
  --checkpoint-fixtures "$PIXAL_CHECKPOINT_REPORT" \
  --binary /tmp/pixal-projection-build/pixal-vision-check \
  --output-dir "$PIXAL_VISION_CHECKPOINT_REPORT"
```

Measured CPU checks execute actual HF DINO/NAF classes and pinned Pixal
extractor/sampler with synthetic learned parameters. Seven saved-checkpoint
cases pass all 174 intermediate/output comparisons (max absolute error
`1.4901161193847656e-06`, atol/rtol5e-5). All 406 serialized tensors match the
native-loaded values exactly. Every case continues through flow sampling:
six sparse-shape cases and one dense-SS case, 21 sampled latent states in total.
F32/F16/BF16 source, F32/F16 storage with F32 arithmetic, NAF torch archives,
no-bias and mixed Q/K/V-bias configurations, non-default epsilon/RoPE/periods,
different NAF/DINO widths and LR-only SS are covered. NATTEN's CPU reference
backend/channel adaptation is the same as described in the NAF section above.

Both converters are byte-deterministic for the repeated inputs. Repeated native
encoding without diagnostics is bitwise equal, and destroying the models retains
the borrowed backend. Fourteen converter rejection cases and nineteen native
metadata/value/component/cancellation/target-size rejection cases pass with no
published output. These include a rejected non-tensor torch archive; no unsafe
fallback was used. Torch GPU initialized=false. Evidence:
`maintenance/g9-pixal-vision-20260919/cpu-final`.

Remaining: actual trained checkpoint compatibility, full-size/mixed-precision
Vulkan, foreground and MoGe, all stage/cascade/decoder/GLB wiring, generated
quality, Library registration, adoption and installed release acceptance.
The existing NAF output-element cap also needs measured resolution planning:
the pinned source has a 1024-target texture training config, whose full F32
1024-channel map exceeds that cap. Do not silently lower the requested target
or treat a source training config as the uninspected deployed pipeline config.

## Foreground and stage boundaries

`prepare_image.frame_foreground` implements the pinned pipeline's alpha decision
before resizing, 1024-pixel limit, strict alpha >204 bounds, 1.1 crop sizing,
Pillow coordinate rounding and RGB background composition. Opaque input requires
an explicit background-removal callback returning same-size RGBA. That callback
owns its model and resource lifecycle; this module provides no removal model.
Empty masks, degenerate crops and malformed provider outputs fail explicitly.
The returned frame includes original/resized sizes, crop box and alpha source.
Pass its RGB image to `prepare_rgb` for each image encoder's configured size.

`native/stage_bridge` connects the existing image projection and flow runner to
dense SS, sparse shape and texture stages. The caller supplies noise, camera,
actual grid and separate shape/texture normalization from the pipeline config.
SS results are returned channel-major `[C,X,Y,Z]` for decoding; sparse results
are token-major with their original coordinates and actual grid retained.
Texture re-normalizes the supplied shape and concatenates it at every model
call, integrating texture channels only, then applies texture normalization.
Progress (including initial zero) and cancellation reach the underlying sampler.

`occupancy_coordinates` accepts actual decoder logits, applies >0 then pooling
and emits ordered coordinates. `plan_shape_cascade` accepts actual LR decoder
upsample coordinates on the 512 grid. It follows Pixal **run()**:
`round((xyz+.5)/512*(grid-1))`, sorted unique, strict `< max_tokens`, and 128-pixel
resolution backoff from 1536 to 1024. It reports each attempt and whether the
budget was met at the floor, without truncating tokens. The older Pixal cascade
helper and TRELLIS CLI use a different floor quantization; do not substitute
them. Pass `actual_resolution/16` into both HR shape and texture conditioning.

```sh
"$PIXAL_PYTHON" runtimes/trellis-cpp-pixal/check_stages.py \
  --pixal-source "$PIXAL_SOURCE" --naf-source "$NAF_SOURCE" \
  --checkpoint-fixtures "$PIXAL_CHECKPOINT_REPORT" \
  --vision-fixtures "$PIXAL_VISION_CHECKPOINT_REPORT" \
  --binary /tmp/pixal-projection-build/pixal-stages-check \
  --output-dir "$PIXAL_STAGES_REPORT"
```

CPU evidence `maintenance/g9-pixal-stages-20260919/cpu-final`: eight foreground
cases match upstream pixels exactly; seven bridge cases pass 28 exact coordinate,
resolution and attempt comparisons. Three connected checkpoint cases run RGB →
DINO/NAF → SS → LR shape → HR shape → texture with explicit synthetic decoder
outputs between stages. All 78 comparisons pass (maximum absolute error
`1.6689300537109375e-06`, atol/rtol5e-5), including 36 sampled step latents,
decoder input layout, normalization and progress. Resolution 1024, 1536 and
1536→1408 backoff, F16 vision storage with explicit F32 arithmetic are included.
Repeated computations are bitwise equal. Twenty-five rejection cases pass with
no published native result. Torch GPU initialized=false; no trained weights.

The reference executes unmodified pipeline methods and the actual `run` cascade
AST. Its public tensor image branch runs on CPU, because the PIL-list branch
hardcodes `.cuda()`; Pillow pixels are compared independently. NATTEN uses the
previously documented CPU adaptation. Saved Torch noise is supplied explicitly
to native code; native RNG seed equivalence is **not tested**.

Neural SS/shape/texture decoding, real background removal, MoGe, GLB output,
full-size/Vulkan execution and generated asset adoption remain **NOT TESTED**.
The original trellis.cpp SS decoder hardcodes a 16³ latent while a pinned Pixal
training config declares 8³. Actual deployed config and decoder compatibility
must be established before wiring that decoder; these stage fixtures do not
establish full image-to-3D generation or Library acceptance.

## Sparse structure neural decoder

`convert_ss_decoder.py` converts a local safetensors checkpoint plus explicit
`SparseStructureDecoder` config to private `pixal3d-ss-decoder` GGUF. It checks
every tensor/name/shape/type, finite values, storage overflow and provenance,
packing Torch Conv3d OC/IC into GGML's four-dimensional layout without moving
elements. Bias/norm tensors remain F32; convolution storage may be F32 or F16.
The converter has no hub/model loader and never downloads weights.

`SsDecoderModel` verifies metadata, the tensor table and file extents before
backend allocation, then validates weight values through the same owned file
handle. Backend ownership remains with the caller; there is no device selection
or fallback. `decode_structure` implements input convolution, configurable
middle/residual blocks, pixel shuffle and output normalization/convolution in
separate graph segments. Cancellation/progress are checked at segment boundaries
and during CPU pixel shuffle. All graph operations must be supported by the
selected backend; stats report segment graph buffer sizes, not GPU peak VRAM.

The current arithmetic is F32, including explicitly promoted F16 stored weights.
Configs whose reference torso uses FP16 require explicit `f32_arithmetic=true`;
mixed-activation execution is not implemented or claimed. Pinned Pixal uses
channel LayerNorm inside every residual block even when the decoder config says
`norm_type=group`; only the final output norm uses 32-group GroupNorm. The native
graph preserves that behavior. Input size is validated independently of weights.

`sample_sparse_structure` now joins the existing SS flow to the actual decoder
and pooled occupancy coordinates. It validates flow/decoder/grid compatibility,
propagates both cancellation callbacks through decoding, and publishes diagnostic
outputs only after completion. These coordinates can feed the shape stage.

```sh
"$PIXAL_PYTHON" runtimes/trellis-cpp-pixal/check_ss_decoder.py \
  --pixal-source "$PIXAL_SOURCE" --naf-source "$NAF_SOURCE" \
  --checkpoint-fixtures "$PIXAL_CHECKPOINT_REPORT" \
  --vision-fixtures "$PIXAL_VISION_CHECKPOINT_REPORT" \
  --stages-fixtures "$PIXAL_STAGES_REPORT" \
  --binary /tmp/pixal-projection-build/pixal-ss-decoder-check \
  --output-dir "$PIXAL_SS_DECODER_REPORT"
```

Measured CPU evidence: `maintenance/g9-pixal-ss-decoder-20260919/cpu-final`.
Eight synthetic checkpoint cases pass 129 intermediate/output comparisons,
all 386 serialized/loaded tensors match exactly, and 12 converter plus 22 native
rejection cases pass. Cases cover 8³/16³ input, up to 64³ output with reduced
channel widths, one/three stages, zero/nonzero residual blocks, final GroupNorm,
F32/F16/BF16 source/storage and explicit F32 evaluation of an FP16 reference config.
Seven direct decodes repeat bitwise with/without retained diagnostic tensors.
The connected case runs actual RGB/DINO/NAF → SS flow → SS neural decoder →
57 pooled coordinates → shape flow, comparing all six sampled flow steps.
SS decoder output fixtures are no longer used in that connected case.

Maximum occupancy-logit error is `6.8247318267822266e-06`; all coordinate arrays
match exactly. General atol/rtol remain 5e-5. The four-channel 8³ case amplified
preceding convolution roundoff at final LayerNorm to `7.270276546478271e-05`;
that intermediate uses atol1e-4/rtol5e-5, explicitly documented instead of hiding
the initial failure. Eight additional same-input source/native norm comparisons
pass the original 5e-5 gate (maximum error `2.86102294921875e-06`). Final logits,
coordinates and downstream shape retain their original gates. Initial failure
logs also retain the corrected Fortran-layout noise fixture error.

Public JSON metadata only was inspected at Pixal model revision
`b0cb2e1b794cab9aa0ac38a95d794a4d9337437f`: the distributed SS flow uses 16³,
and its decoder declares channels `[512,128,32]`, 8 latent channels and FP16.
All four deployed flow configs and the SS decoder config pass metadata validators
(700 tensors per flow, 74 decoder tensors). Files/URLs/hashes are retained under
`public-configs`. This resolves the earlier deployed-config uncertainty; it does
not validate learned weights or full-width execution. The source also declares
texture NAF target1024, so its existing full-map capacity issue remains.

Trained checkpoint execution, full-width capacity/quality, mixed activations,
Vulkan under a genuine Host lease, shape/texture neural decoders, MoGe/removal,
GLB generation, adoption/release and newly generated Library assets remain
**NOT TESTED**. Torch GPU initialized=false; trained weights were not used.
