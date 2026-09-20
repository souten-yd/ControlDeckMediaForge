# G9 trained Pixal Vulkan output and Library acceptance

PR586 repaired the pinned GGML Vulkan long-row softmax and merged as
`9bc0061442054fedeb7d162aa0a004d6ec54eec2`. PR587 fixed the bounded CPU remesh
intermediate and merged as `50cc8b0e80870a9efc7a14300797ab41b3b674f6`.
These external native changes leave the signed installed app at 0.28.90;
the existing TRELLIS 512 runtime and receipt are unchanged.

Evidence is in installed feature data
`maintenance/g9-pixal-hr-diagnosis-20260920/`.

## Actual trained output, with the stages distinguished

The genuinely leased diagnostic Vulkan run saved the learned shape and texture
before reproducing the original CPU intermediate-limit failure. It did not
complete a GLB. See the [softmax](g9-pixal-vulkan-softmax-20260920.md) and
[surface-budget](g9-pixal-surface-budget-20260920.md) records for that failure,
fixed inputs, trained weights, source hashes and released lease.

Replaying those exact saved arrays with the corrected CPU surface exporter
completed in **349.854642 seconds, exit 0**, under a 20 GiB address-space and
1200-second limit. `/usr/bin/time` recorded maximum RSS 5,063,600 KiB and no swaps.
No GPU was requested by this replay. Its production surface arithmetic matches
the merged source; the private replay only changes the input reader/entrypoint.

- Original mesh: 5,826,793 vertices / 12,506,508 triangles.
- Remeshed: 9,483,982 vertices / 18,976,340 triangles.
- Simplified: 465,330 vertices / 935,214 triangles; atlas: 660,463 vertices.
- Two 4096-square WebP textures, 1 material, required `EXT_texture_webp`.
- GLB: **32,437,052 bytes**, SHA256
  `f2b6c521e7694ada8d53a5c3e8650c09ff0fb8f2f7360ea974859b6513b9c805`.
- Independent `glb.structure` 1.1.0 passed. Blender 4.5.13 LTS reimport and four
  Cycles CPU renders passed: 658,842 imported vertices, 935,214 triangles,
  finite coordinates, 1 mesh/material, two 4096-square images, 0 bones/actions.

All four renders were inspected. The disc, housing and side pipe resemble the
input; the unseen rear has holes and rough surfaces. The native bake also reports
559 faces with collapsed UVs. This is an experimental single-image reconstruction,
not CAD fidelity, watertightness or an animation-ready quality acceptance.

This is a **split-phase trained Vulkan capture plus CPU export**. The separate
single invocation of the managed production worker also succeeded, as recorded
below; the artifacts and timings are kept distinct.

## Existing Library registration

The evaluated GLB is registered as
`asset_47ac692256534508b068cf044a08da29`, with the Library summary
`[実験的] Pixal3D Vulkan・機械部品 1024` and filename
`pixal3d-vulkan-trained-mechanical-1024-evaluation.glb`.

The same-version Store maintenance path from the earlier
[Library import](g9-pixal-library-20260919.md) was used because the raw-byte public
importer has no intent/warnings input. It did not initialize/migrate the database
or rewrite existing Assets. Registration is `asset.import` / local-import provenance,
not a new inference or runtime adoption. Source metadata retains checkpoint/Vulkan,
CPU preprocessing/postprocessing, split-phase evaluation, the model revision and
nine native weight hashes, exact captured arrays, seed 42 and genuine source lease.
The original input Asset `asset_8cd35ff5ffb145ba94febf7a79cf6583` is the parent;
its served normalized PNG and the evaluated input were verified RGBA-pixel-identical.

The live installed HTTP Asset/provenance/Job/Library projection and full content
all match. A second execution reused the same hash with `created=false` and
created no duplicate. Four previously registered GLBs retained their exact hashes,
including the old synthetic Pixal sample and the installed TRELLIS output.
Warnings state the rough unseen rear and absence of bones/animation.

The authenticated real Host opaque iframe displayed this Asset at 1280 and 320
pixels in Chrome 151.0.7922.169. Both reported 935,214 triangles / 1 mesh / 1
material / 0 animations, and released their model handles on close. Page errors,
HTTP errors, failed requests and horizontal document overflow were zero.
The initial 320-pixel framing crops the object; three existing zoom-out clicks
showed the whole model. This does not claim perfect automatic mobile framing.
Headless rendering uses SwiftShader, not measured physical mobile-GPU performance.

The additional controls script first stopped because it attempted to select an
engine without opening the collapsed detail section. No generation was submitted.
After adding the actual detail click, desktop fit and mobile fit/three zoom-out
clicks, close and the existing TRELLIS 512 form all passed. The failed report is
retained alongside `host-pixal-browser-evaluation-controls-v2.json`.

## Managed full Vulkan measurement

`candidates/native-surface32m-v1` / `worker-surface32m-v1` use the exact merged
source and separate corrected GGML libraries inside the managed Pixal runtime.
CPU preparation completed in **49.317878 seconds, exit 0**. The full ordinary
operator-leased `surface-managed-trained-vulkan` run completed in
**1172.211559 seconds, exit 0**. All learned stages used the Vulkan backend,
float32 policy and native device 1; image preparation and mesh postprocessing
used CPU. The model is TencentARC/Pixal3D revision
`b0cb2e1b794cab9aa0ac38a95d794a4d9337437f`, seed 42, resolution 1024, all 12
sampler steps and the measured 49152-token limit. Weights are genuine checkpoints.

Sampled whole-device VRAM peaked at **4,996,214,784 bytes**; process-tree RSS
peaked at **5,253,251,072 bytes**. Real Host lease
`5d0c7d36-0cb4-4e76-81e2-31ebb7ddb77a` received 233 renewals and was released
after process exit. The result is **32,437,096 bytes**, SHA256
`be18d7d31652a0fc7be7d083c79f4b65e4c914be2712ecedb1a9a204e92558ec`.
Independent core GLB validation and Blender 4.5.13 import/four CPU renders passed.
Its complete BIN chunk is identical to the split-phase evaluated GLB (SHA256
`0eaa804daaa84db51107f7823c4f25983bf1c8194362ce7ae4cf881a27371bec`);
all four rendered RGBA pixel arrays are identical too. JSON metadata differs,
so these are not incorrectly assigned the same file hash.

An additional preparation rehearsal used the exact core `run_worker` launch and
minimal environment: **52.571055 seconds, exit 0**, CPU only. Prepared image,
camera, low/high RGB tensors, samplers and normalization arrays match the full
evaluation inputs by hash. An initial diagnostic helper import missed the repo
root on PYTHONPATH and stopped before creating a worker; the corrected rehearsal
is retained separately as `installed-prepare-rehearsal-v2`.

## Adoption and actual installed generation

A hash inventory covers 35,982 runtime/venv/library members (6,937,326-byte JSON)
and the base Python interpreter separately. It includes actual GGML loader
symlink names and excludes bytecode caches; the installed worker uses its private
pycache prefix. All staged source files match the merged code. This inventory
alone grants no adoption. After the successful full run, lease release and
independent verification, `adopt_pixal.py` rechecked the complete inventory and
atomically created the private runtime receipt. Native executable SHA256 is
`b8dd89d8e1e1a43e57fced67c6f4efa14cf45199326f5e04e18cf072a5b9e341`.

The existing receipt schema requires positive file sizes. The first construction
therefore rejected 497 empty package markers before writing anything. Their
hashes/sizes were independently checked and retained in `runtime-empty-members.json`;
35,485 nonempty files are pinned by the published receipt. This does not claim
continuous receipt coverage of the empty markers or relax the public contract.
The receipt is 6,855,338 bytes, SHA256
`49ef12180751a6b0d68b0e856e4ce93e753609291c6b07af0b90e5dcd7ccdc78`.
The already accepted MIT, Apache-2.0 and DINOv3 license identities remain recorded.

After adoption, an idle service restart returned healthy PID 2821940 and retained
the exact 16-table database snapshot, 2730 asset-file attributes and Blender
registry. The preliminary PID helper used the wrong Python and could not import
httpx; no before-PID measurement is claimed. The restart command exited 0 and
the subsequent health, capabilities and full persistence check passed.

The live capability now exposes **Pixal3D / 1024 / experimental** with measured
runtime 1172.211559 seconds. Automatic selection still uses measured TRELLIS 512.
The authenticated actual Host Create → 3D form opened its detail section,
selected Pixal3D, 1024 and seed 42, and submitted the real image Asset. The UI
created MediaForge Job `job_9f4e1ce6efb94811927835616bcd2570` at
05:56:00.231388 UTC. It is currently running. Real Add-on lease
`4908a94b-b0d2-4868-88b6-317d3636e4fd` reserves 5,533,085,696 bytes on gpu0 for
detached Host Job `099b310cb1c7`. The browser closed while the detached Job
continued. There was no second submission or manual replacement of Job output.

No additional login or license consent was needed. Terminal installed Job,
Scene/Library publication and generated-asset restart verification are pending.

Latest product gate (PR587): **2279 tests passed, 2 warnings, 256.60 s, exit 0**.
This acceptance slice changes records only.

NOT TESTED: successful completion of the installed Pixal generation, its generated
Blender/Library lineage and restart persistence, bones/animation, cold provisioning,
real rollback and physical-device browser performance.
