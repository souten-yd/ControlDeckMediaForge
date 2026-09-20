# G9 trained flow allocation on CPU — 2026-09-20

MediaForge source starts at `18660873d10756d264a84fbe90e71f320b3b65b3`
(PR578 merged). The original `feat/g9-image-to-3d` checkout is preserved.
Installed 0.28.88 remains healthy. Host `/api/v1/auth/me` returned HTTP401 and
the dedicated operator session file was absent. The preceding turn delivered a
normal-login helper; this turn measures an independent CPU capacity gate while
the legitimate Host execution context is still unavailable.

## Scope and reproducibility

The new private native target `pixal-flow-allocate-cpu` loads a real trained
checkpoint and constructs/allocates the existing `FlowRunner`. It never calls
`forward` or selects a GPU. Weight arithmetic is explicitly F32 after F16
storage, with five global DINO tokens and `trellis::g_no_fa=true`, matching the
current worker. No attention algorithm or production setting changed.

The upstream non-FA implementation already chunks queries; its 32-chunk cap can
raise each chunk above the nominal 1GiB attention budget. The probe measures the
actual graph allocator instead of inferring failure from an unchunked matrix.
Sparse coordinates are synthetic distinct coordinates at the requested count;
they are not coordinates inferred from the reference image. SS uses the complete
ordered 16-cubed grid from its actual checkpoint.

Build from `runtimes/trellis-cpp-pixal/native` with the documented
`TRELLIS_SOURCE_DIR`/`TRELLIS_BUILD_DIR`, then:

```bash
cmake --build "$PIXAL_BUILD" --target pixal-flow-allocate-cpu -j 2
env -u TRELLIS_ATTN_CHUNK_MB timeout --kill-after=5 90 \
  prlimit --as=25769803776 --core=0 -- \
  "$PIXAL_BUILD/pixal-flow-allocate-cpu" "$TRAINED_SHAPE_HR_GGUF" 49152
```

Actual runs removed inherited `TRELLIS_*`/`GGML_*` overrides, verified each GGUF
SHA-256 against the existing trained inventory and ran sequentially. Source pins:
trellis.cpp `2516c48b677050c570f47eba2e68dc8a5bc918b0`,
GGML `737e88f25d4f62254f3b7a726fd9663036cc94da`.
Models/consent remain the ones recorded in
[trained evaluation](g9-trained-models-20260919.md); no new download or consent.
The initial compile lacked the declaration of `g_no_fa`; including the upstream
`trellis_args.h` fixed it. Both compile logs are retained.

## Measurements

All models have 30 blocks and width1536. All four processes exited0 within the
24GiB address-space and 90-second limits.

| Stage | Tokens | Weight buffer bytes | Graph buffer bytes | Process peak RSS bytes | Process wall seconds |
|---|---:|---:|---:|---:|---:|
| SS | 4,096 | 2,681,370,656 | 934,532,096 | 2,720,595,968 | 0.715585 |
| Shape LR | 32,768 | 2,775,890,048 | 3,328,594,944 | 2,821,517,312 | 0.765187 |
| Shape HR | 49,152 | 2,775,890,048 | 6,181,770,240 | 2,834,518,016 | 0.765443 |
| Texture | 49,152 | 2,775,988,352 | 6,178,821,120 | 2,834,649,088 | 0.715201 |

Allocation is successful, but inference never touches the graph's allocated
pages. This is **not** a physical resident-memory capacity test, GPU VRAM peak,
runtime benchmark, full pipeline result or generation-quality acceptance.
The buffers exclude live image/NAF features, decoder memory, output extraction,
GPU backend workspaces and driver allocations. Do not put these figures into
an adoption receipt or use them as a production lease estimate.

The 49,152 count comes from the unadopted `trained-job.json` candidate's token
target. Actual cascade output is image-dependent; the current 1024 floor can
return `token_budget_met=false`. These measurements do not prove every image is
bounded to this count or authorize that candidate descriptor.

Ten rejection cases exited1 with the expected error and no JSON success:
missing/excessive address-space limit, insufficient 1GiB address space, negative
token count, trailing garbage, count above65,536, sparse count0, partial SS grid,
coordinates exceeding the checkpoint grid and missing arguments.

An additional SS process was traced with `strace -f -e trace=%file,ioctl`:
exit0, no `/dev/dri` or `/dev/kfd` accesses. The shared registry transitively
links the Vulkan library; library loading alone is not GPU initialization or
computation. Native/library digests and trace are retained.

Final `./mf.sh test`: **2274 passed / 2 warnings / 257.58s / exit0**.
Warnings are the existing Starlette/httpx and Pillow deprecations. No code was
changed afterward. These tests supplement the real native allocation processes;
they do not establish full generation or installed GPU acceptance.

## Evidence and remaining work

Managed evidence directory:
`maintenance/g9-flow-capacity-20260920` under the installed feature data root.
It contains build commands/logs, four stdout/stderr pairs, `results.json`,
`rejections.json`, `binary-provenance.json`, `cpu-only.trace` and
`cpu-only-report.json`. The executable is a private diagnostic outside the
lightweight release bundle. No app version change or reinstall is needed.

Next: complete the normal terminal login described in
[operator session](g9-operator-session-20260920.md), validate real Host broker
device mapping/admission, and perform bounded TRELLIS/Pixal GPU runs with genuine
lease activation, renewal and release. Independently validate/render the output
before adoption and the installed image→Scene Job→Library acceptance.

NOT TESTED: GPU/Vulkan operators, full trained inference, peak generation RAM/VRAM,
Pixal visual quality, new generated GLB registration, runtime adoption and bones.
Both generation engines remain unavailable; existing Library samples retain
their original provenance and synthetic Pixal label. The overall goal is open.
