# G9 Pixal CPU remesh intermediate budget

After [PR586's Vulkan softmax repair](g9-pixal-vulkan-softmax-20260920.md), the
unchanged trained 1024 pipeline passed all shape/texture flow and decoder stages
but failed after CPU remeshing with `invalid surface mesh dimensions`.
That attempt exited 1 in 842.030839 seconds, published no GLB and released its
genuine Host lease after process cleanup. This is a distinct failure from Vulkan
inference; installed Pixal remains unavailable until complete measured acceptance.

## Independent reproduction and change

The actual upstream CPU remesher turns a closed cube spanning -0.49 to +0.49 at
1024 resolution into an unsigned-distance offset shell with **12,024,064 vertices
and 24,048,120 triangles**. The previous uniform 16-million face check rejects
that valid intermediate before the existing QEM simplifier can reduce it.

Only the post-remesh intermediate now allows up to 32 million triangles, while
retaining the 16-million vertex limit. Raw input, simplified mesh and baked mesh
limits remain 16 million; final requested faces, 64 MiB GLB bound, finite-value
and index checks are unchanged. Dimension errors now include counts and limits.
This does not change remeshing, QEM, UV baking, model weights, inference resolution
or public schemas. The caller still bounds the CPU process's memory and wall time.

`check_surface_budget.py` runs the real CPU remesher under a 12 GiB address-space
limit and 180-second timeout. It deliberately requests cancellation at simplifier
entry, verifying that the corrected boundary is passed and no staging/GLB remains.
The original binary instead fails at the dimension check. The regression does
not claim successful full simplification, GLB export, quality or GPU execution.

Evidence: `maintenance/g9-pixal-hr-diagnosis-20260920/surface-budget-regression/`.
Original: 8.431429 seconds, exit 1, did not reach simplification.
Corrected: 8.420652 seconds, exit 1 at the intentional simplification cancellation.
The harness passed both expected outcomes; input and binary hashes are recorded.

The existing independent surface-export suite also passed with the corrected
binary: **9 export runs, 74 comparisons, 19 rejection/cancellation/no-overwrite
checks, 8 core GLB validations and 8 Blender 4.5.13 imports**. These use synthetic
fixtures. PNG pixels, WebP error checks, geometry/UV/normal comparisons and owned
process termination retain their original expectations. See `surface-cpu-regression/`.

## Trained surface diagnosis

The initial failed worker correctly removed staging, so its generated intermediate
was not available for CPU replay. A single bounded diagnostic run now captures
the unrepaired vertices/faces, texture coordinates/PBR values and exact settings
before running the unchanged surface exporter. The temporary instrumentation
changes neither model computation nor validation limits, and its binary/source
hashes and genuine Host lease are recorded in `surface-capture-build.json` and
`surface-capture-leased/`. The capture reproduced the original failure in 829.822180 seconds, exit 1,
165 lease renewals, sampled device VRAM peak 4,995,043,328 bytes and owned-process
RSS peak 5,228,199,936 bytes. Its process was reaped and lease released.

The actual trained surface contained 5,826,793 vertices and 12,506,508 triangles.
After the two hole-fill passes it contained 5,829,437 vertices and 12,523,196
triangles. Remeshing produced **9,483,982 vertices and 18,976,340 triangles**:
the previous face ceiling is the confirmed cause, while the retained vertex
ceiling still fits. The exact original arrays/settings were saved, with hashes
in `captured-surface-files.json`. Corrected CPU export of those arrays is running;
no completed trained GLB or adoption is claimed yet.

`surface-replay` is a private CPU-only diagnostic over those captured arrays. Its
reader checks header/product/exact byte length and finite values before use.
It accepts up to 96 million F32 elements per tensor to cover the existing
16-million-voxel PBR handoff. The original 16-million mesh checks remain in that
baseline replay. No GPU initialization or adoption is granted by this helper.

The managed candidate `native-surface32m-v1` links the separate corrected GGML
libraries under managed runtime storage. CPU-only preparation for its exact descriptor completed in 49.317878 seconds, exit 0.
It is not yet adopted or fully measured.
The original TRELLIS runtime and installed 0.28.90 remain unchanged.

NOT TESTED: corrected trained surface/full GLB, final visual quality, managed full
measurement, Pixal adoption and installed image→Library/browser, bones/animation.

Final `./mf.sh test`: **2279 passed, 2 warnings, 256.60 seconds, exit 0**.
No app-bundle or public-contract change; installed app version remains 0.28.90.
