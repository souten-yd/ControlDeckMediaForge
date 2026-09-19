# Pixal3D Vulkan port: scope and measured first component

The user explicitly requested Pixal3D Vulkan support on 2026-09-19, in addition
to the original image-to-3D integration, Pixal3D evaluation and Library outputs.
This expands the requested implementation; a Python/ROCm-only evaluation is
not sufficient for the added Vulkan requirement. Product boundaries remain
MediaForge + existing Scene Jobs/Host leases/Blender validation/Library.

## Source differences that must be preserved

Inspection of pinned Pixal3D `f7cf3842` and trellis.cpp `2516c48b` found:

1. Pixal3D's global conditioning selects the CLS + register tokens, while patch
   features enter through camera-aware projection. Reusing only TRELLIS.2's
   original global attention context is not equivalent.
2. Each attention block adds its own `proj_linear(projected_features)` to global
   cross-attention. Weight names nest the cross-attention under
   `cross_attn.cross_attn_block`; a weight converter must preserve the new
   projection tensors as well as the original graph structure.
3. Shape/texture stages concatenate low-resolution DINO features with
   NAF-upsampled high-resolution features. Omitting NAF changes the model.
4. Sparse conditioning gathers projected features at the actual sparse grid
   coordinates, preserving their order. Cascade coordinate quantization,
   conditioning resolution and sampling parameters need independent comparison.
5. Default single-image camera estimation uses MoGe 2. The official entrypoint
   also supports explicit camera parameters; those can isolate the native
   generator during development, but do not establish default image-only parity.
6. TRELLIS-compatible shape/texture decoders and GLB output are candidates for
   reuse, subject to fixed weight identities and actual intermediate comparison.

## Implemented and measured

`runtimes/trellis-cpp-pixal/native` contains the single-image projection plan and
GGML interpolation graph. The test driver selects one explicit CPU/Vulkan
backend and rejects an unsupported operation rather than using mixed execution.
No generated model weights are needed for this component.

Actual CMake/GCC13.3 build succeeded against the pinned local GGML libraries.
The retained upstream projection file SHA256 is
`3e02246e00a047d1bc8be170a4313632c32a4077b22447f044956b9810340f56`.
Six synthetic CPU cases compared with the unmodified upstream code all pass;
maximum absolute error is `1.621246337890625e-05`. Invalid-scale rejection passes.
GPU initialized=false. The source preserves coordinate rotations, +0.5 image
pixel center, align_corners=False, border padding, repeated/sparse token order,
and upstream's lack of visibility masking.

Evidence: managed data `maintenance/g9-pixal-vulkan-20260919/projection-cpu`.
This component is not connected to the generation runner yet. A linked Vulkan
library, backend support query or CPU result does not prove GPU execution.

## Projected DiT component measured on 2026-09-19

The next slice `ux1/pixal3d-projected-dit`, based on PR555 / `86527e2`, adds a
reproducible patch for the shared trellis.cpp DiT graph. It loads the nested
Pixal3D cross-attention weights and adds the per-block projection linear output.
It refuses omitted or mismatched projected conditions. The source is generated
in the build directory from pinned Git objects; the installed runtime is intact.

Five small-model CPU cases execute the actual pinned upstream flow class with
synthetic deterministic parameters, covering 59 intermediates/final outputs.
Maximum absolute error: `9.5367431640625e-07`. One case connects the native
projection graph directly to the two-block DiT in one computation graph.
Zero negative conditions retain projection bias. Both negative-input checks pass.

The first comparison exposed the existing GGML CPU FP16 GELU lookup error;
an opt-in F32 formula now matches PyTorch without changing the test tolerance.
The default is unchanged. A separate executable compiled from unmodified
upstream source matches the patched legacy path bit-for-bit. GPU initialized=false.
Evidence: `maintenance/g9-pixal-dit-20260919/cpu-combined`, plus earlier failure
reports and binary/source/library hashes. These are synthetic small-model results,
not trained-model or Vulkan acceptance.

## Flow checkpoint component measured on 2026-09-19

`ux1/pixal3d-checkpoint`, based on PR556 / `3003a21`, adds a local-only
safetensors/config-to-GGUF converter using pinned gguf0.19.0. It validates all
names/shapes/dtypes and the implemented model configuration, preserves projected
weights, emits source/config/output/tensor hashes, and rejects unsupported or
incomplete input without publishing a partial output. F32 is the default;
F16 storage applies only to linear matrices, retaining normalization in F32.
C++ inspects versioned metadata and every weight before backend allocation.
No trained checkpoint was used and no runtime was adopted.

Six synthetic CPU cases use actual upstream dense SS and sparse ElasticSLat
classes. Safetensors F32/BF16/F16 -> GGUF F32/F16 -> real native Model::load ->
projected DiT yields 72 passed comparisons, max absolute error
`7.152557373046875e-07` at atol/rtol5e-5. All serialized values match exactly.
Sparse coordinate order/repeats and doubled texture channels are included.
F16 storage is explicitly cast to F32 for arithmetic; mixed precision is a
separate gate. All eight pinned source training-config denoiser sections are
accepted by the config validator (700 expected tensors each); this does not
verify deployed checkpoint configs or values. Twelve converter and nine native
pre-allocation rejection checks pass; repeated conversion is byte-identical. Existing DiT 59-comparison and
legacy bitwise checks pass. Torch GPU initialized=false.

Evidence: `maintenance/g9-pixal-checkpoint-20260919/cpu-release` and
`dit-regression`, with retained source/GGUF/NPY artifacts and hashes.
An initial negative-fixture writer rejected a non-contiguous slice; corrected
fixture creation allowed the complete rerun. The native arithmetic tolerance
was not changed. The subsequent runner slice is described below.

The next runner slice must pass both global and projected positive/negative
conditions explicitly. Texture sampling concatenates the fixed shape condition
with the evolving texture latent; it must not integrate the shape channels.
The existing trellis.cpp sampler also contains robustness clamps and replacement
of non-finite velocity by zero that are absent from the pinned Pixal sampler.
Do not silently inherit these changes: compare each Euler/CFG/rescale step and
report non-finite model output as failure. Model loading must use the admitted
explicit backend, avoiding trellis.cpp's largest-device heuristic/fallback.

## Stage runner/sampler measured on 2026-09-19

`ux1/pixal3d-flow-runner`, based on PR557 / `aef84a3`, implements an explicit
borrowed-backend model loader, reusable projected DiT graph and Pixal Euler/CFG
sampler. It preserves both positive/negative projected conditions and fixed
texture shape concatenation, rejects unsupported operations on the selected
backend, and never enumerates/selects/falls back to another device. Resource
admission belongs to the existing Host/worker layer, not this native library.
Cancellation before/after each model call and completed-step progress are wired.
Non-finite velocity/rescale is an error instead of a silent numerical repair.

Ten small synthetic CPU cases run the pinned upstream SS/ElasticSLat classes
and real Pixal sampler. All 108 velocity/clean-latent/sample comparisons over
36 Euler steps pass; maximum absolute error `1.6689300537109375e-06`, atol/rtol5e-5.
Forward timestep and positive/negative sequences match exactly. Reusing the graph
for identical sampling is bitwise deterministic. Cases cover time/CFG rescale,
guidance intervals, positive-only/negative-only, shape/texture and F16 storage
with F32 arithmetic. An analytic scale canary covers rescale beyond the old
TRELLIS clamp. Eleven invalid-input/non-finite/cancellation cases reject with
no published output. Prior 72 checkpoint and 59 DiT comparisons plus legacy
bitwise regression pass. Torch GPU initialized=false.

Evidence: `maintenance/g9-pixal-runner-20260919/cpu-release`, checkpoint and DiT
regression reports. No pretrained model or GPU execution was used. The native
stage functions are implemented; the complete image-to-GLB pipeline is not wired.

## Image feature connection measured on 2026-09-19

`ux1/pixal3d-image-features`, based on PR558 / `e8c48f1`, connects resized RGB
pixels through native DINOv3, CLS/register/patch splitting, camera projection
and explicit positive/negative flow conditions. The graph adapts pinned
trellis.cpp without editing its original source. Only plain-GELU DINO is
supported; its required weights and input dimensions/range are validated.
Pillow preprocessing preserves Pixal's LANCZOS-then-RGB order, after foreground
framing/compositing. Those earlier image pipeline operations remain separate.

Six small synthetic CPU cases execute transformers4.57.3's actual DINO layers
and unmodified pinned Pixal extractor/projection methods. All 99 intermediate
and sampled-latent comparisons pass, maximum absolute error
`1.1920928955078125e-06` at atol/rtol5e-5. Resize outputs match exactly.
Five cases continue through native flow sampling, with all 15 step states
compared; the wider feature-only case does not use the narrow flow fixture.
Attention biases, register/head dimensions, single-patch inputs, non-square
source images and supplied HR concatenation are covered. HR features are
synthetic inputs, not NAF output. Six invalid-input checks and the existing
10-case/108-comparison flow regression pass. Torch GPU initialized=false.

Evidence: `maintenance/g9-pixal-dino-20260919/cpu-release` and `flow-regression`.
The reference extractor is instantiated without calling its pretrained loader.
No trained DINO/Pixal weights were used. DINO model metadata/conversion/loading
in the production pipeline, NAF/MoGe and full image-to-GLB remain unfinished.

## NAF upsampling measured on 2026-09-19

`ux1/pixal3d-naf`, based on PR559 / `aa0e419`, implements the pinned NAF
evaluation encoder and tiled neighborhood attention with existing GGML ops.
It preserves reflected convolution padding, GroupNorm/SiLU, guide-resize rules,
adaptive pooling, persistent RoPE periods, nearest-exact LR gathering and border
shifts within each dilation residue. Encoder intermediates are freed before
attention; Q/K/V stay resident across tiles on the explicit selected backend.
Unsupported operations fail; no automatic CPU fallback or new GPU kernel.

Nine synthetic CPU cases pass all 115 comparisons with the actual NAF class
(all parameters overwritten) and NATTEN0.21.0. The reference redirects only
NAF's hard-coded cutlass choice to CPU flex-fna and splits/pads independent V
channels for that backend's equal-head-width constraint; NATTEN computes the
original neighborhood mask/attention. Max absolute error 1.3969838619232178e-05,
atol/rtol5e-5. Six cases continue through real LR/HR projection and sparse shape
sampling; all 18 sampled latent states match. Irregular image/pool sizes,
unequal dilation, default 256-channel/9x9 NAF, different feature widths and
F16 storage with explicit F32 arithmetic are included.

Tile-size changes and repetition without diagnostic outputs are bitwise equal.
The latter initially exposed a query view-owner reuse issue, now fixed by
protecting the underlying output tensor; tolerances were not relaxed.
The regular attention graph uses 36768 bytes at tile7 vs 236032 bytes at tile64.
These CPU graph buffers do not establish GPU VRAM/process peak/full-size memory.
Ten negative/cancellation checks pass without publishing output, including
cancellation after final tile compute. DINO regression: 6 cases/99 comparisons/
6 negatives passed. Torch GPU initialized=false; trained weights not used.

Evidence: `maintenance/g9-pixal-naf-20260919/cpu-release` and `image-regression`.
NAF trained checkpoint conversion/metadata/loading, real-sized images, Vulkan,
mixed precision and full GLB pipeline remain NOT TESTED. Earlier fixture/layout
and buffer-reuse failures are retained in sibling logs. This is not adoption.

## Vision checkpoints and connected image path measured on 2026-09-19

`ux1/pixal3d-vision-checkpoints`, based on PR560 / `6a1cfd0`, adds strict local
DINO/NAF checkpoint-to-GGUF conversion, source/config/output/tensor provenance,
native metadata/file-extent validation and explicit borrowed-backend loading.
DINO Q/K/V and absent bias mapping, config epsilon/RoPE/biases and NAF persistent
periods feed the implemented image graphs. Unused DINO mask/final-affine-norm
values are validated/hashed and their omission is documented. Unknown/unsupported
settings and inconsistent tensors fail; no best-effort parameter renaming.

The default input is safetensors. NAF's explicit torch archive path uses pinned
torch2.10.0 `weights_only=True`, CPU mapping and mmap, accepting plain tensor state
dictionaries only. It does not invoke hub loading or retry unsafe pickle.
`encode_vision` connects loaded DINO -> optional actual NAF -> global/LR/HR maps;
the caller supplies the stage's NAF target explicitly. Source/original runtime
weights and installed Library remain unchanged. No adoption receipt is created.

Seven synthetic checkpoint cases pass all 174 CPU intermediate/output comparisons,
max absolute error 1.4901161193847656e-06 (atol/rtol5e-5). All 406 serialized
tensors exactly match native-loaded values. Six shape and one SS condition
continue through native sampling and match all 21 reference sampled states.
The reference executes pinned HF DINO, NAF and Pixal extractor/sampler; NATTEN
uses the previously documented CPU backend and independent-V-channel adaptation.
Cases cover F32/F16/BF16 sources, F32/F16 storage with explicit F32 arithmetic,
NAF .pth, bias variations, non-default normalization/RoPE/periods, different
encoder/value dimensions, and LR-only SS. Repeated encoding with/without debug
is bitwise equal; borrowed backend survives model destruction.

Fourteen converter and nineteen native rejection checks pass without published
output. Native metadata/table/truncation failures occur before backend setup;
NaN weight and nonpositive period checks occur while loading values. Both
converters produce identical repeated GGUF bytes. Torch GPU initialized=false.
Evidence: `maintenance/g9-pixal-vision-20260919/cpu-final`.

This is still synthetic CPU evidence, not actual checkpoint/Vulkan acceptance.
The source's texture ft1024 training config requests a 1024 NAF target, which
would exceed the current NAF output-element cap at 1024 channels in F32. This
needs measured memory planning/implementation without silently reducing the
stage target. Deployed pipeline config has not been inspected/accepted yet.

## Required remaining acceptance

- Genuine Host lease and physical-device mapping; run the same numerical cases
  on Vulkan, recording device, exact source/library/binary hashes and results.
- Validate the implemented converter against authorized real trained checkpoint
  configurations/weights; small synthetic conversion is not model acceptance.
- Validate authorized DINO/NAF checkpoints through the implemented converters/
  loaders and bind the deployed pipeline parameters. Compare trained-model outputs and
  BF16/FlashAttention behavior on the admitted Vulkan device.
- Measure full-sized NAF on Vulkan and resolve output-memory limits for actual
  requested stage targets. Integrate MoGe camera estimation or a separately
  verified native image-only camera path preserving the requested behavior.
- Integrate all SS/LR shape/HR shape/texture stages, cascade coordinate/latent
  transformations and shared decoder checks into a complete native pipeline.
  Do not silently substitute TRELLIS.2 weights or skip expensive Pixal3D stages.
- Same-image, same-seed full Vulkan generation; real GPU time/memory, independent
  Blender validation, multi-view visual review and retained reference artifacts.
- Native Pixal adapter/adoption, Scene Jobs cancellation/resource cleanup,
  actual output provenance/lineage and installed Library publication.
- Signed MediaForge deployment and installed UI/API generation and display.

The earlier model-license consent question remains unanswered. The projection
work uses only source and synthetic tensors. It does not load/download weights
or grant adoption. GPU checks additionally need genuine Host admission.

## Additional request: rigging generated assets

The user asked whether generated GLBs can receive bones and animation. Existing
MediaForge authoring includes armature creation, rigid binding, bounded automatic
weights and animation clips. Actual generated input must first be inspected.
CPU Blender inspection of `ref_vk.glb` found one mechanical assembly mesh,
227918 vertices and no armature; four orthographic renders are retained under
`maintenance/g9-rig-evaluation-20260919`. It is a gear/piston assembly, so rigid
part separation and mechanically appropriate bone pivots are needed. Existing
automatic binding is limited to 50000 vertices and is not directly applicable.
No rigged output has been produced or registered. Target selection was asked;
the original source Asset must remain unchanged when publishing a derived rig.
