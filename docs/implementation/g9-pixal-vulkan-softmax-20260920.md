# G9 Pixal Vulkan long-row softmax correction

This follows the bounded resume condition in the [NAF evaluation](g9-pixal-vulkan-naf-20260920.md).
The failed HR input was captured once and replayed without repeating full generation.
The failure is an existing pinned GGML Vulkan reduction error, not evidence that
Pixal requires ROCm. The change corrects two expressions in existing shaders;
it adds no new kernel, CPU inference fallback, model change or relaxed tolerance.

## Diagnosis on the real R9700

Evidence is under the installed feature data directory
`maintenance/g9-pixal-hr-diagnosis-20260920/`. GPU runs used genuine ordinary
operator Host leases on `gpu0`, explicit Vulkan device 1, the existing F32 policy,
bounded owned process groups and release after process exit. No Host internals,
forged sessions or authentication material are included in the evidence.

All 700 HR weight tensors and all captured input arrays were finite. The actual
failed HR input contains 18,000 coordinates, 5x1024 global features, 18000x2048
projected features, 18000x32 noise and timestep 1000. File hashes, shapes and
finite ranges are in `hr-input-manifest.json`; the original trained weights,
seed 42, samplers and precision policy were retained.

- Capture stopped intentionally before HR compute: exit 1, 100.863572 seconds.
- Unmodified full HR replay reproduced non-finite velocity: exit 1, 18.475743 s.
- A bounded node trace first failed at node 89, `SOFT_MAX`, immediately after a
  finite attention-score multiplication. It found 317 non-finite values in 218
  rows. Capturing these rows and evaluating stable CPU F64 softmax produced zero
  non-finite values.
- Replaying the faulty maximum reduction on all 218 rows missed the true maximum
  by 185.8419189453125 to 689.217529296875 after scaling. Every gap exceeded the
  F32 exponential overflow threshold. See `softmax-root-cause.json`.

The pinned GGML revision is `737e88f25d4f62254f3b7a726fd9663036cc94da`.
For columns above 16,384 it dispatches to the existing large-row shaders.
Both `soft_max_large2.comp` and `soft_max_large3.comp` incorrectly reuse each
lane's original `max_val` at every reduction step. They must retain the reduced
`vals[tid]` instead. The two-line patch SHA256 is
`4af70841b6caae023cef813e30a9c9f77f258d376fb2d3bdfa4e27afd1c0464e`.

## Separate, reproducible candidate

`prepare_ggml.py` requires the pinned source revision, exports its tracked archive
into a fresh separate directory, checks/applies the patch, and records the archive,
patch and original/patched file hashes. Source identity mismatch, same-source
destination and existing destination were actually rejected; no invalid destination
was created. The original TRELLIS runtime and GGML tracked files remain unchanged.

The native CMake project accepts `PIXAL_GGML_BUILD_DIR`, retaining its previous
default, so a fresh native build can link the corrected libraries without changing
the adopted TRELLIS binary. Build commands are in the runtime README. The measured
candidate enabled Vulkan/shared libraries and disabled HIP, CUDA, BLAS and native
CPU auto-tuning. The resulting CPU backend still enables its explicit default
AVX/AVX2 options. `fixed-runtime-provenance.json` records actual hashes and `ldd`.
This is not a claim of bitwise-reproducible builds.

`pixal-softmax-check` is a bounded private CPU/Vulkan operator probe. Its caller
must own genuine GPU admission. The checker covers diffuse and moving-extreme
scores at 1024, 16384, 16385, 18000, 32769 and 49152 columns, optional attention
sinks and the actual failed rows. CPU F64 stable softmax is the independent reference;
the tolerance remains atol/rtol 5e-5.

| Measurement | Observed result |
|---|---|
| Original Vulkan, final 17 cases | 5 failures: four large extreme-score cases and captured HR rows; 1.203873 s, exit 1 |
| Corrected Vulkan, same 17 cases | all pass, maximum absolute error 5.4266288240789606e-8; 1.203019 s, exit 0 |
| Corrected CPU, same 17 cases | all pass, maximum absolute error 5.338356534601019e-9; exit 0 |
| Trained 8-coordinate, all-30-layer HR CPU/Vulkan reference | 6 comparisons pass, maximum absolute error 0.00010633468627929688; unchanged atol/rtol 1e-3 |
| Corrected Vulkan, actual 18,000-coordinate full HR forward | exit 0, finite velocity, 19.479243 s; sampled device VRAM peak 4,982,235,136 bytes |
| Equivalent 18,000-coordinate CPU forward | 600-second limit, exit 124; reference completion NOT TESTED |

Short probe sampling can miss allocations; those peaks are not production lease
estimates. The full HR forward above is one sampler step, not completed generation.
All completed GPU probes released their leases after owned process cleanup.

## Full generation and adoption boundary

After the limited replay passed, one full trained Vulkan run was started with the
unchanged nine GGUFs, seed 42, 1024 resolution, 12-step samplers, 49,152-token cap
and 4096 textures. It has passed all 12 HR steps and reached texture flow. Its
terminal result, GLB and visual quality are still pending at this checkpoint.
The live evidence is `fixed-trained-vulkan/{result.json,telemetry.jsonl}` and
`fixed-trained-vulkan/output/native.stdout.log`.

A separate candidate was built inside managed runtime storage with all actual
GGML dependencies resolving there. CPU-only preparation for its exact descriptor
completed in 58.425480630015954 seconds, exit 0. It has not been adopted or used
for a full GPU run. Temporary-build measurements are not silently assigned to
the differently linked managed binary.

Installed 0.28.90 and the working TRELLIS 512 receipt remain unchanged. Pixal is
still unavailable, with no new trained Pixal Library asset. Next: observe the
running full result, independently import/render its GLB, then measure the exact
managed candidate before adoption and the normal Host image-to-Library path.

`./mf.sh test`: **2279 passed, 2 warnings, 266.43 seconds, exit 0**. All native
targets built successfully. This slice changes external native preparation and
diagnostics, not the lightweight app bundle or public contracts; no app version bump.

NOT TESTED: completed full trained Pixal GLB, visual quality, managed full runtime
measurement, Pixal adoption/installed image-to-Library/browser and bone animation.

## Terminal follow-up

PR586 was merged as `9bc0061442054fedeb7d162aa0a004d6ec54eec2`.
The full trained attempt completed all shape/texture flow and decoder stages,
then failed in CPU surface processing after `surface_remesh 0/1` with
`invalid surface mesh dimensions`. It exited 1 after **842.030839 seconds**,
167 lease renewals, sampled device VRAM peak **4,995,760,128 bytes** and
owned-process-tree RSS peak **5,279,264,768 bytes**. The owned process was reaped
and its lease released. The failure removed staging and published no GLB.
This proves progress beyond the Vulkan softmax failure, not complete generation.

A separately bounded CPU 1024 box reproduction reached 12,024,064 vertices and
24,048,120 faces, then hit the fixed 16-million-face intermediate limit. This
does not by itself identify the trained object's counts. One diagnostic Vulkan
run now captures its unrepaired surface before the unchanged CPU export so that
subsequent surface investigations can replay on CPU without repeated inference.
