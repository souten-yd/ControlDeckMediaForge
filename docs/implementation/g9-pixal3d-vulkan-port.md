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

## Required remaining acceptance

- Genuine Host lease and physical-device mapping; run the same numerical cases
  on Vulkan, recording device, exact source/library/binary hashes and results.
- Pixal3D checkpoint-to-GGUF conversion and model metadata/shape validation.
- Integrate the implemented projected DiT with the real stage runner and correct
  DINO global-token selection. Compare trained-model block outputs and
  BF16/FlashAttention behavior on the admitted Vulkan device.
- NAF native feature upsampling, with measured memory-bounded execution and
  numerical comparison. Integrate MoGe camera estimation or a separately
  verified native image-only camera path preserving the requested behavior.
- All SS/LR shape/HR shape/texture sampling stages and shared decoder checks.
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
