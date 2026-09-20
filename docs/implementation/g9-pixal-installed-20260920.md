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

This is a **split-phase trained Vulkan capture plus CPU export**, not a successful
single invocation of the managed production worker. That separate full run is
still in progress below; neither result is substituted for the other.

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

## Managed candidate and remaining acceptance

`candidates/native-surface32m-v1` / `worker-surface32m-v1` use the exact merged
source and separate corrected GGML libraries inside the managed Pixal runtime.
CPU preparation completed in **49.317878 seconds, exit 0**. A full ordinary
operator-leased Vulkan run is active as `surface-managed-trained-vulkan`; it has
passed all learned stages and reached CPU simplification. Its terminal GLB,
runtime and memory measurements are still pending.

A hash inventory covers 35,982 runtime/venv/library members (6,937,326-byte JSON)
and the base Python interpreter separately. It includes actual GGML loader
symlink names and excludes bytecode caches; the installed worker uses its private
pycache prefix. All staged source files match the merged code. This inventory
grants no adoption. `adopt_pixal.py` is prepared but not executed: it requires the
exact managed run to succeed, release its lease, and pass GLB plus independent
Blender verification before checking all hashes and publishing a private receipt.

At this checkpoint the installed capability still reports TRELLIS 512 as
experimental and Pixal as unavailable. No additional login or license consent
is needed. Next: complete the managed full measurement, then adopt and exercise
the real Host image→3D form through new Scene/Library publication and persistence.

Latest product gate (PR587): **2279 tests passed, 2 warnings, 256.60 s, exit 0**.
This acceptance slice changes records only.

NOT TESTED: managed full success/adoption, installed Pixal generation submission,
its generated Blender/Library lineage and restart persistence, bones/animation.
