# G9 Pixal Vulkan NAF correction and remaining trained failure

The first genuinely leased trained Pixal run on the R9700 exited 1 after
61.607146 seconds: `selected backend cannot execute NAF operation: IM2COL`.
The 1024-square, 128-channel, 3x3 F32 im2col would require 4,831,838,208 bytes for
one tensor. The pinned Vulkan backend rejects tensors beyond the device buffer
limit; CPU-only graph allocation did not expose this acceptance problem.

## Change

NAF convolutions now process strips of at most 64 output rows. Each strip reads
its kernel halo from the globally reflected input. Convolution results are
concatenated before bias and global group normalization, preserving the original
neighborhoods and normalization. This uses existing GGML operations; no custom
GPU kernel, source checkpoint change or CPU inference fallback was added.
Unsupported-operation errors include the output size/type and source layout.
The numeric checker adds an actual two-strip 96x128 encoder case, including
intermediate encoder outputs and the downstream projection/flow comparison.

A separate Vulkan numeric failure exposed implicit half-precision rounding.
For the first synthetic convolution, rounding both operands to F16 reproduced
the Vulkan output within 5.960464477539063e-8, while F32 differed by
0.00030875205993652344. Disabling cooperative matrices alone did not resolve it.
The production CLI now explicitly sets the pinned backend's `GGML_VK_DISABLE_F16`,
`GGML_VK_DISABLE_COOPMAT`, and `GGML_VK_DISABLE_COOPMAT2` before Vulkan initialization
to honor its existing `--precision float32` contract. The numeric checker uses
that same policy. The runtime/model identities and backend policy must be included
in any later adoption; previous default-Vulkan timings are not this policy's timings.

## Measurements

Evidence: installed feature `maintenance/g9-real-generation-20260920/`.
The existing checker compares pinned NAF/NATTEN and Pixal reference calculations
with synthetic parameters. Its tolerance remained atol/rtol 5e-5.

| Numeric run | Result |
|---|---|
| Tiled CPU | 10 cases and 14 rejection/cancellation checks passed; max absolute error 1.3969838619232178e-5 |
| Default Vulkan | comparison failed; max absolute error 0.0028330087661743164 |
| Vulkan without cooperative matrices | comparison still failed |
| Vulkan without F16 and cooperative matrices | all 10 cases and 14 checks passed; max absolute error 2.205371856689453e-6; 4.207969 s total |

GPU checks used explicit genuine Host leases on native device 1 / Host gpu0.
The rejection checks in the numeric harness remain CPU checks, not GPU cancellation
acceptance. Sampled VRAM may miss very short allocations; the tiny-run peak is not
used for production adoption.

A fresh sealed CPU preparation was made with the corrected binary descriptor and
unchanged trained weights/options/seed 42. The next complete trained Vulkan attempt
exited 1 after **132.113766 seconds**, with **26 lease renewals**, sampled device-wide
VRAM peak **4,992,151,552 bytes** and owned-process-tree RSS **1,233,801,216 bytes**.
The last observed native progress was `hr_image 1/1`, then `hr_flow 0/12`;
the final error was `non-finite flow velocity`. The previous NAF allocation
failure was passed, but this is not successful image-to-3D generation.
The worker published no GLB and its lease was released after process exit.

This candidate remains **unadopted/unavailable**, with no generated Pixal asset
registered. Do not replace the existing synthetic Library sample's warning label
or present it as a trained output. Following the repository's unstable-model rule,
full Pixal adoption is deferred; working TRELLIS 512 is the available alternative.
Resume only with a bounded diagnosis and reference comparison of the failing
trained HR flow that preserves the fixed inputs, weights, F32 policy and lease
boundary. Do not retry the same full run or invent a new GPU kernel.

NOT TESTED: completed trained Pixal GLB, visual quality, full successful-run peak
memory/runtime, installed Pixal image→Library, bone/animation generation.

Final `./mf.sh test`: **2279 passed, 2 warnings, 266.95 seconds, exit 0**.
