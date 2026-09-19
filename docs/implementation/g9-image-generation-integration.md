# G9 image generation integration — source implementation and remaining acceptance

The requested outcome is image-to-3D through trellis.cpp, plus installation,
evaluation and Library outputs for Pixal3D. The existing `feat/g9-image-to-3d`
checkout is preserved. This additive integration starts from main `bbdc69a`;
it does not remove existing typed Blender tools or replace the asset/Jobs system.

## Source behavior

- `media.scene.from_image`, Workflow `media.scene` action `from_image`, and
  opaque workspace `scenes.from_image` accept an image Asset. The 3D panel
  offers Library image selection, name, measured resolution, seed, status and
  cancellation. It appears only for an available/experimental capability.
- Scene Jobs pin the generator receipt and input hash, acquire a detached Host
  Job, request the measured GPU budget, activate/renew the lease, and reap the
  native process before release. CPU Blender work uses the existing scene slot;
  GPU waiting does not occupy it. Queued input images cannot be deleted.
- The native CLI uses only pinned local files and a sanitized environment.
  Core does not import ML libraries. The output passes the GLB validator, then
  a trusted Blender process packs the scene. Independent reopen/export validation
  precedes source and preview Asset registration and immutable Scene creation.
- Both registered Assets carry model/runtime identities and lineage. Retry
  refuses a changed input, generator receipt or unavailable pinned Blender.
  No runtime installation, weight download or license acceptance is implicit.

Private adoption configuration is under
`<data_dir>/runtime-state/image-to-3d-runtime.json`, validated by
`ThreeDRuntimeReceipt`. It records executable/shared-library and model hashes,
the pinned model snapshot, license acceptance, native-to-broker device mapping,
measured VRAM/runtime/resolution, and a validated evaluation output hash.
There is no receipt in the installed service for this new adapter. Do not create
one from guessed measurements or treat the synthetic test receipts as adoption.
Receipt provisioning/evaluation tooling and native device verification remain
part of the next implementation/acceptance work.

## Measured import acceptance on 2026-09-19

Executed `scripts/3ds_generated_import_e2e.py` twice with the existing trellis.cpp
WebP GLBs and the installed, read-only Blender 4.5.9 runtime. Each run used its
own Store and registry, a synthetic image, and explicitly fixture-only generator
metadata. No weights, inference or real Host calls were used in these runs.

| Existing GLB | Input bytes | Import, validation and publication time |
|---|---:|---:|
| ref_vk.glb | 11,443,236 | 1.077 sec |
| s01_vk.glb | 11,189,676 | 1.052 sec |

Both produced a packed `.blend`, validated Library GLB, one Scene revision and
input-image dependency. Stored bytes matched Asset/provenance hashes; source
GLBs remained unchanged, staging was empty, and runtime references returned to 0.
Evidence is in the installed feature-data maintenance directories
`g9-import-20260919-ref/observations.json` and
`g9-import-20260919-s01/observations.json`. These isolated fixture Assets are
not user Library results and are not evidence of successful new inference.

The original two user-provided GLBs are already registered in installed 0.28.87
as recorded in the WebP acceptance entry; that separate result remains valid.

Pixal3D source was cloned from `https://github.com/TencentARC/Pixal3D.git` and
detached at `f7cf38429b0bd264f1995f0f8743a88b1c728b94` under the existing
managed data's `runtimes/pixal3d-source`. Its checkout is clean; LICENSE, NOTICE,
requirements and inference entrypoint hashes are recorded in
`g9-import-20260919-ref/pixal3d-source.json`. This is source preparation only:
no Pixal3D environment, weights, evaluation output or adoption receipt exists
from this step. Inspection confirms automatic model-loading paths in the stock
entrypoint; do not execute it until the consent and offline provisioning gates
are satisfied. The default source installs from unpinned MoGe Git and uses
DINOv3 model references, so the stock requirements/entrypoint are not yet the
reproducible isolated runtime needed by MediaForge.

## Remaining work for the full request

1. Resolve the pending explicit license consent for DINOv3 and Pixal3D weight
   use, then provision pinned software/weights with their notices. Preserve
   existing source/runtime/model files and other running inference workloads.
2. Add reproducible evaluation/adoption tooling and verify physical device
   mapping under genuine Host admission. Measure trellis.cpp generation time,
   peak memory, output validation and independent views on the requested image.
3. Install and run Pixal3D in its isolated environment; verify ROCm behavior,
   dependencies, memory, runtime, images and geometry. Record failures honestly.
   The current native adapter deliberately rejects `engine=pixal3d` as unadopted.
4. Register the actual evaluation outputs with their actual model identities
   and original-image lineage in the installed Library; verify downloaded bytes.
5. Signed release/update of this feature, installed MCP/Workflow/opaque workspace
   checks, real GPU waiting/cancellation, and real browser 3D display/operations.
   Source tests and the real Blender import above do not satisfy these gates.

Final source checks: `./mf.sh test` completed with 2211 passed, 2 warnings,
237.44 sec, exit 0. `node --check frontend/app.js` also exited 0.
Browser rendering, genuine Host admission and inference remain NOT TESTED.

Status: source integration implemented; the full goal remains open.
