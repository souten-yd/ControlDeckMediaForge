# Model registry and adoption gates

Date: 2026-08-21

## G0 fake worker

The G0 worker is not a generative model and is not eligible for default-model promotion.

- ID: `media-forge/fake-image`
- runtime: separate Python subprocess, CPU-only
- license identifier: `CC0-1.0`
- weights hash: sentinel SHA-256 of all zeroes; no model weights exist
- capability: test implementation of `image.text_to_image`
- confidence: `low`
- GPU lease: not requested because this worker performs no GPU work

Its only purpose is to prove job, process-isolation, asset, validation, provenance, UI, and Add-on contracts. It may be removed after G1 without changing the public API, satisfying model-adoption gate #10.

## G1 default — FLUX.2 [klein] 4B

Adoption state: **accepted for `image.text_to_image` on the measured R9700
envelope of at most 1024x1024 pixels**. Editing capabilities described by the
upstream model card are deliberately not advertised; Media Forge has not yet
implemented or accepted the G2 editing path.

Identity:

```text
model_id: black-forest-labs/FLUX.2-klein-4B
revision: e7b7dc27f91deacad38e78976d1f2b499d76a294
weights_hash: sha256:f3fcfa8fdaf5ebcd26c33cd53b485ec5ebe54939b5ace585b3f488278dfae278
license: Apache-2.0
pinned weight bytes: 15964212614
shared cache: /data1tb/ControlDeck/data/cache/huggingface
```

The path above is deployment evidence, not a public API value. The registry
matches the pinned snapshot and four weight blobs by size and SHA-256 before it
marks the model installed. The worker uses `local_files_only=true`; generation
does not have a remote inference fallback.

### `base-plan.md` section 24 adoption answers

1. It fills the first real local `image.text_to_image` implementation; G0 had
   only the deterministic fake worker.
2. It uses the generic image adapter boundary and a Diffusers
   `Flux2KleinPipeline`. Diffusers 0.40 does not forward `disable_mmap` to its
   Transformers component, so the adapter explicitly loads the Qwen3 text
   encoder with the same bounded options. No special public operation or model
   argument is required.
3. Eight optimized product-path jobs completed on the AMD Radeon AI PRO R9700
   (`gfx1201`) with ROCm 7.2.1 / PyTorch 2.10.0. There were zero unrequested
   failures. Two earlier A/B attempts were explicitly canceled when their load
   paths were already demonstrably slow; they are not counted as successful or
   failed generations.
4. The measured envelope is recorded below. Requests above 1024x1024 or above
   1,048,576 pixels fail with `resource_limit` before requesting a lease.
5. The pinned 4B weights and intended local/commercial use are Apache-2.0. This
   conclusion does not apply to the differently licensed 9B variant.
6. Every observed output carried the pinned model/revision-derived weights
   hash, license, adapter/runtime versions, seed, parameters, validators, and
   output SHA-256 in provenance.
7. The pinned weight blobs cost 15,964,212,614 bytes; the complete cached
   repository occupied 15,988,907,862 bytes on NVMe. No other installed local image
   model filled G1, and the accepted optimized path is fast enough after its
   first-resolution ROCm compilation. Qwen-Image was therefore not downloaded
   merely to create a second default.
8. It runs in the heavyweight image venv as a one-job subprocess. Real Host
   cancellation terminates that subprocess; the core remains healthy and the
   Broker lease is released.
9. It uses maintained PyTorch, Diffusers, Transformers, safetensors, HIP/COMGR,
   and MIOpen paths. There are no ComfyUI custom nodes and no Media Forge custom
   kernels.
10. Yes. Routing is by `image.text_to_image` and model policy. Removing this
    registry entry makes the capability unavailable/fake as appropriate without
    changing job, asset, provenance, workflow, agent, or Add-on contracts.

### R9700 measurements

All accepted generation samples traversed ControlDeck Workflow execution, a
ControlDeck Job, Broker admission, an active and renewed lease, and the separate
Media Forge image worker. Times are wall-clock unless explicitly identified as
adapter timing.

```text
hardware: AMD Radeon AI PRO R9700 / gfx1201 / 34208743424 bytes VRAM
software: ROCm 7.2.1, torch 2.10.0+rocm7.2.1, diffusers 0.40.0
storage: NVMe/ext4 shared Hugging Face and ROCm caches
runtime options: device_map="cuda", disable_mmap=true for Diffusers and Qwen3
bounded output: 256..1024 each dimension, multiples of 16, <=1048576 pixels

512x512, 4 steps, seed 424242, separate worker, cache warm:
  without parallel shard loading: total 15.789333 sec
                                  load 11.508421 sec
                                  generate 1.472648 sec
  with parallel shard loading:    total 14.936748 sec
                                  load 10.589401 sec
                                  generate 1.468313 sec
  peak VRAM delta observed:       20216500224 bytes
  output SHA-256 both paths:      0c8d372e7169ca3a7121925fe7a9b00d2615a6b11e57819a990fbe425e079882

1024x1024, 4 steps, seed 424242:
  first resolution-specific ROCm compile: total 208.820067 sec
  later separate worker:                  total 17.933032 sec
                                          load 11.344260 sec
                                          generate 3.537276 sec
  execution peak VRAM delta:              29625200640 bytes
  worst whole-job peak VRAM delta:        32275578880 bytes
  peak worker RSS:                        16384692224 bytes
  peak worker swap:                       0 bytes
  output SHA-256 both runs:               bf83e5941312a6221b13b5c604876ba6b4ea2322c60b4265472f5d756ccdc162
```

The two SHA comparisons prove deterministic equality for the tested same-seed,
same-setting pairs; they do not claim determinism across future runtime or
driver versions. The production Broker estimate uses the worst observed
resolution-specific first run rather than the 14–18 second steady state:

```text
resident_vram_bytes:       0
execution_peak_vram_bytes: 29625200640
cold_load_peak_vram_bytes: 32275578880
headroom_vram_bytes:       1073741824
estimated_runtime_sec:     208.820067
confidence:                measured
```

The one-shot worker releases all VRAM after each job, hence resident is zero.
The 1 GiB headroom plus the larger cold-load peak reserves 33,349,320,704 bytes,
below the R9700's measured total. The first 1024 run populated persistent
COMGR/MIOpen caches on NVMe; the 17.9-second run was a new worker process, so the
speedup is not an in-memory retained model. A forcibly evicted Linux page-cache
run is **NOT TESTED** because flushing global host caches would disturb other
ControlDeck workloads.

### Rejected slow path and mitigation

The original Diffusers sequence loaded mmap-backed tensors on CPU and then
called `pipeline.to("cuda")`. A real 512x512 product job took 852.587283 seconds
while one CPU core copied approximately one GiB per minute; worker swap remained
zero. `device_map="cuda"` alone was still clearly slow and was canceled at
142.209076 seconds. Applying `disable_mmap` only to Diffusers left the Qwen3
text encoder on the old path and was canceled at 353.455380 seconds.

The accepted adapter applies direct device placement and `disable_mmap` to both
component families. Its first optimized product job completed in 37.284804
seconds, a second process in 25.762736 seconds, and later cache-warm runs in
14–18 seconds. Parallel shard loading reduced the measured 512 load by about
0.92 second; adding CPU cores alone is therefore not the fix for the 12-minute
path. `AMD_COMGR_CACHE=1`, COMGR/MIOpen cache directories, and
`HF_ENABLE_PARALLEL_LOADING=YES` are exported through `mf.sh` and remain
user-overridable.

This is not a ComfyUI Dynamic VRAM result: Media Forge does not execute ComfyUI.
The symptom was similar, but process, GPU, disk, RSS, and swap observations
localized this case to mmap transfer/device placement plus first-use ROCm
compilation.

## Deferred candidate — Qwen-Image

Qwen-Image remains **NOT TESTED** and was not downloaded. It is an alternative
only if the accepted FLUX.2 route later fails the target-hardware or quality
gate; candidates are not installed for their own sake.
