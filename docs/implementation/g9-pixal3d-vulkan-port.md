# Pixal3D Vulkan port: scope and measured first component

## 2026-09-19 projected NAF output memory

The LR/HR shape and texture stages now evaluate the four NAF pixels needed by
each sparse projection and perform the original ordered four multiply/adds on
the selected GGML backend. The complete encoder, Q and pooled K are retained;
this changes output retention, not the learned attention or neighborhood rule.
The dense API remains available with its original output limit. The projected
API validates coordinates and limits retained elements by sparse token count.
Tile sizes below four evaluate one complete four-corner token. DINO and NAF
weights have separate lifetimes; only projected positive/negative conditions
are retained for subsequent flow sampling.

CPU evidence in `maintenance/g9-pixal-naf-projection-20260919/`:

- NAF: 9 cases / 142 reference comparisons, max abs 1.3969839e-5 under the
  existing 5e-5 tolerance. Three cameras per case match native dense projection
  bit-for-bit, including border/behind-camera, repeated coordinates, unequal
  dilation, F16 storage/F32 arithmetic and changed tile sizes. 14 negatives pass.
- Capacity: target 1024², value width 1024, 49,152 distinct tokens including all
  corners, encoder width 256 / two layers / kernel 9. **Guide image is 64²** and
  weights are synthetic; a spatially constant V provides an analytic oracle.
  25.202264 s CPU, max abs 3.5762787e-7, 192 MiB actual projected output,
  7,033,384,960 bytes maximum child RSS. The 4 GiB dense equivalent is calculated
  from dimensions, not an observed old-path allocation. Graph allocation sizes
  are 3,758,757,024 (encoder) / 1,179,691,008 (attention) bytes, not peak VRAM.
- Pipeline: 7 GLB runs / 111 reference comparisons / 34 negatives / 5 independent
  core and Blender imports. All seven outputs equal the parent PR567 GLB JSON
  except generation time and match its entire binary payload. Actual SIGTERM
  reaps the owned SS-flow process in 0.001084 s with no published GLB.
- Dense stage regression: 8 preprocessing, 7 bridge, 3 connected cases and
  25 negatives pass. No learned weights, GPU execution or Library writes.

Full-image/full-model memory, trained quality/mixed precision, genuine Host
lease plus Vulkan, MoGe/background removal, worker adoption/deployment and new
Library assets/rigs remain NOT TESTED. The overall goal is incomplete.

## 2026-09-19 connected native RGB-to-GLB pipeline

`ux1/pixal3d-native-pipeline`, parent PR566 / `4d0350c`, connects all implemented
vision/flow/neural-decoder stages and GLB export through one `generate_glb` call.
It preserves SS pooling to 32, actual four-stage LR upsampling, quantization and
resolution backoff, HR/texture conditioning, shared decoder subdivisions and
final mesh resolution. It does not accept supplied decoder outputs. Models are
loaded/released by stage; the caller retains backend/Host admission ownership.
The private evaluation CLI is not the installed image-generation adapter.

Original pinned `run()` with actual CPU neural decoders passes 111 comparisons
for 1024, 1536 and 1536→1024, maximum absolute error 1.2278557e-5; all coordinates
and face indices/order are exact. Seven native GLB runs include exact-noise and
native-seed repeats plus a changed image. All repeated arrays and GLB payloads
match excluding generation timestamp. RGB change alters HR latent by 0.31782913
and changes the exported binary. Five GLBs independently pass core and Blender
4.5.9 material/UV/texture/geometry checks. 34 invalid/role/cancel checks pass, plus
real SS-flow process SIGTERM/reap in 0.001081 s without GLB publication.

These are reduced-width, synthetic checkpoints with explicit small image/NAF/
texture extents. SS zero velocity and calibrated decoder bias select four voxels;
shape subdivision/intersection logits intentionally make planar fixture topology.
The final grids are 1024/1536, but this is not learned shape or quality acceptance.
Reference CPU adapters and the unrepaired-mesh boundary are explicit; GPU CuMesh
postprocess parity is not claimed. Native seeded Box-Muller RNG is recorded in
GLB extras and is not Torch seed-equivalent. Exact-noise comparisons supply the
reference's actual draws. Default sampler parameters and resolution 1536 follow
the pinned source/deployed config; reduced settings are explicit test overrides.

Evidence: `maintenance/g9-pixal-pipeline-20260919/cpu-second`, retained first
successful run, native build logs, flow/surface regressions and full tests.
Remaining: full NAF memory, MoGe/background removal, trained/full-width/full-size/
mixed precision, genuine Host lease/Vulkan, quality, worker/adoption/deployment
and generated Library assets/rigs. Weight-license consent remains pending.
The overall goal remains incomplete.

## 2026-09-19 CPU surface export acceptance

`ux1/pixal3d-surface-export`, based on PR565 / `40c50c4`, connects the decoded
surface to hole filling, original-surface BVH projection, CPU remesh/simplify,
UV/PBR bake and PNG/WebP GLB export. Source changes live in a content-addressed
overlay; the installed trellis.cpp checkout/build is unchanged. Pixal's band 1,
project_back 0, final axes, PBR packing and no component-drop behavior are explicit.
The <100-active-voxel trellis heuristic found by the first real check is removed.
The implementation is a CPU adaptation; CuMesh/nvdiffrast/OpenCV whole-output
parity has NOT been established. No fallback mesh/atlas/codec hides a failure.

Measured 9 export runs / 74 comparisons / 19 negative and lifecycle checks passed.
8 artifacts independently pass core GLB validation and actual Blender 4.5.9 import,
including material channels, both embedded 128-square images, UVs, face counts
and orientation/bounds. Three previous synthetic neural-decoder outputs reach
80/272/292 triangles and 9088/28720/22140 bytes. This does not rerun the neural
inference or use trained weights. Sampler error against actual FlexGEMM Torch
with CPU hash adapters is at most 1.1920929e-7; negative-grid boundary checks are
analytic because Torch's truncation differs from its CUDA floor semantics.
PNG/baked bytes and repeat arrays are exact; analytic interior PBR is within
one byte. WebP 80 is explicitly lossy. A real subprocess SIGTERM during UV work
reaps in 0.001070 s without publishing a GLB; parent cleanup removes staging.

Evidence: `maintenance/g9-pixal-surface-export-20260919/cpu-final`, retained
`cpu-first.log` failure, successful `cpu-second`, build provenance and full tests.
The default 4096 texture was only exercised through cancellation; successful
completion at that size is NOT TESTED. Remaining: native whole-pipeline wiring,
MoGe/removal/full NAF capacity, trained/full-width and mixed-precision evaluation,
real Host lease/Vulkan, quality, adoption/deployment/new Library outputs and rigs.
The earlier weight-license question remains pending. The goal is incomplete.

## 2026-09-19 sparse structure neural decoder and connected shape sampling

`ux1/pixal3d-ss-decoder`, based on PR562 / `b6592f0`, adds strict local
safetensors/config conversion, native GGUF inspection/loading and the actual
SS decoder graph. It supports configurable channels/residual stages and input
resolution, with segment cleanup, explicit backend support, progress/cancellation
and no automatic device selection. Conv3d/pixel-shuffle layout and the pinned
source's residual LayerNorm/final optional GroupNorm placement are preserved.
F32 is the implemented arithmetic. FP16-reference configs require an explicit
F32 evaluation option; mixed activations remain unimplemented and untested.

Eight synthetic learned-checkpoint cases execute the unmodified pinned decoder
class: 129 comparisons pass, 386 serialized/loaded tensors match exactly, and
12 converter +22 native rejections pass. Seven direct decode cases repeat
bitwise with/without diagnostic tensor retention. Input8³/16³ and output64³
are tested with reduced channel widths, not a full-width trained decoder.
One connected image/DINO/NAF/SS-flow/SS-decoder/shape-flow case matches all six
sampled steps and exactly 57 coordinates; there are no supplied SS decoder logits.
The combined helper propagates sampler cancellation through decoder stages.

Final logits max absolute error `6.8247318267822266e-06`, coordinates exact.
An 8³ case with four output-feature channels amplifies prior roundoff through
final LayerNorm to `7.270276546478271e-05`. The final norm intermediate gate is
explicitly atol1e-4/rtol5e-5; general/final-logit gates stay atol/rtol5e-5.
Eight same-input norm comparisons independently pass the original gate, max
`2.86102294921875e-06`. The initial stricter-norm failure and corrected
Fortran-order noise fixture error are preserved in the evidence logs.

Public model JSON metadata (no weights) was fetched at immutable revision
`b0cb2e1b794cab9aa0ac38a95d794a4d9337437f`. The deployed
[SS flow config](https://huggingface.co/TencentARC/Pixal3D/blob/b0cb2e1b794cab9aa0ac38a95d794a4d9337437f/ckpts/ss_flow_img_dit_1_3B_64_bf16.json)
uses16³ input; the
[SS decoder config](https://huggingface.co/TencentARC/Pixal3D/blob/b0cb2e1b794cab9aa0ac38a95d794a4d9337437f/ckpts/ss_dec_conv3d_16l8_fp16.json)
declares latent8, channels512/128/32, two middle and two per-stage residual
blocks, reference FP16. The current validators accept all four flow configs
(700 expected tensors each) and the SS decoder config (74 tensors). This closes
the earlier metadata uncertainty, without asserting learned checkpoint acceptance.

Evidence: managed `maintenance/g9-pixal-ss-decoder-20260919/cpu-final`, initial
failure logs, `public-configs/{retrieval,native-config-compatibility}.json` and
build provenance. GPU initialized=false; pretrained weights, installed runtime,
Host and Library remain unchanged. Remaining: full-width trained compatibility/
capacity, mixed precision/Vulkan with a genuine Host lease, shape/texture decoders,
MoGe/removal, GLB/quality/adoption/release/new Library assets. License consent
remains unanswered. No rigged animation was produced; the overall goal is incomplete.

## 2026-09-19 foreground and stage/cascade connection

`ux1/pixal3d-stage-bridge`, based on PR561 / `d231f87`, adds worker-side
foreground framing and native stage bridges. The alpha decision before resize,
strict threshold, crop rounding and composition follow the pinned pipeline.
Opaque input requires an explicit background-removal provider; its neural model
is not implemented or claimed by a deterministic protocol fixture.

The existing image/flow graphs now run through SS, shape and texture helpers with
explicit input noise, actual grid, separate shape/texture normalization, progress
and cancellation. SS output is transposed to the decoder's channel-major layout.
Occupancy logits pool to ordered coordinates; shape-decoder upsample coordinates
use the actual `run()` quantization (grid-1, rounding, sorted unique), strict token
budget and 128-pixel backoff. The old Pixal helper/TRELLIS floor quantization is
different. A plan at 1024 may report an unmet budget; it never truncates tokens.
HR shape and texture preserve the selected grid/coordinate order.

Actual CPU measurements, all learned parameters synthetic:

- Eight foreground cases: exact upstream pixel equality, including transparency,
  threshold/edge rounding, downsize, custom background and opaque callback paths.
- Seven bridge cases: 28 exact comparisons for pooling/cascade/budget attempts,
  including equality at the strict limit and backoff ending over budget at 1024.
- Three loaded-checkpoint RGB/DINO/NAF/SS/LR/HR/texture cases: all 78 comparisons
  pass, maximum absolute error `1.6689300537109375e-06` (atol/rtol5e-5). All 36
  sampler step states, normalization, SS decoder layout and progress agree.
  1024, 1536 and 1536→1408 with the actual conditioning grid are included.
- All repeated connected computations are bitwise equal; 25 invalid-input/
  cancellation checks reject, without publishing native outputs. GPU initialized=false.

The oracle extracts unchanged pipeline methods and the quantization statements
from `run`; image tensors use the supported CPU input branch and Pillow pixels
are independently compared. The source's PIL-list branch hardcodes `.cuda()`.
SS's deterministic positional buffer is constructed by the reference model;
learned checkpoint tensors still load strictly. Initial oracle failures for
these boundaries and the test's initial-zero progress count are retained in logs;
the native numerical tolerance was not relaxed. NATTEN CPU adaptation is unchanged.

Evidence: managed `maintenance/g9-pixal-stages-20260919/cpu-final`, failure logs
and build provenance. Supplied decoder logits/upsampled coordinates are explicitly
synthetic fixtures; real neural decoders are not tested. Native inputs use saved
Torch noise, not a claimed seed-identical native RNG. No trained weights, GPU
execution, installed capability changes or new generated assets occurred.

Remaining: actual neural decoder/config compatibility, MoGe and removal models,
full-size capacity/mixed precision/Vulkan under a genuine Host lease, full GLB
generation/quality, adoption/release and installed Library acceptance. The original
TRELLIS SS decoder hardcodes 16³ latent input, whereas a pinned Pixal training
config declares 8³; do not blindly connect it without deployed config validation.
Earlier weight-license consent remains unanswered. The overall goal is incomplete.

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
exceeded the dense NAF output-element cap at 1024 channels in F32 when this
checkpoint slice was measured. The later projected-NAF slice above removes
that output retention requirement and preserves the target size. Its reduced
guide CPU capacity result is not full-image/Vulkan acceptance. Deployed config
has since been inspected for the connected pipeline; trained adoption remains pending.

## Required remaining acceptance

- Genuine Host lease and physical-device mapping; run the same numerical cases
  on Vulkan, recording device, exact source/library/binary hashes and results.
- Validate the implemented converter against authorized real trained checkpoint
  configurations/weights; small synthetic conversion is not model acceptance.
- Validate authorized DINO/NAF checkpoints through the implemented converters/
  loaders and bind the deployed pipeline parameters. Compare trained-model outputs and
  BF16/FlashAttention behavior on the admitted Vulkan device.
- Measure full-image NAF and the projected output path on Vulkan at actual
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
