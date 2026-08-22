# Model registry and adoption gates

Date: 2026-08-21

## Catalog ownership and storage

The runtime registry remains the single source used by capability routing. A
separate `worker_packs/image/catalog.json` adds presentation and installation
metadata without changing the frozen public model schema. Catalog metadata
contains a friendly name, bounded domain tags, source identity, approximate
download size, reference/LoRA support, supported reference roles, explicit
per-reference-strength support, recommendations, gating/license notice, and an
ownership mode. A missing role/strength declaration is treated as unsupported,
not guessed from a generic multi-reference capability.

`managed` means the detected immutable snapshot is inside Media Forge's
configured model store and may later be removed by Model Management. `external`
means the snapshot was detected in the shared Hugging Face cache and is always
read-only. Detection resolves the root, repository, snapshot, required files,
and weight blobs before accepting the installation. A symlink escape is not an
installation, and the same identity resolving as both managed and external is
an invalid registry rather than an arbitrary ownership choice.

Catalog domains are advisory only. They do not bypass capability, state,
health, hardware, policy, or measured-resource routing checks. Downloading a
model also does not promote unmeasured metadata to measured.

Managed installation is explicit and catalog-only. The installer downloads
the exact pinned revision into a contained `.downloads/<operation_id>` tree,
persists progress in Media Forge's SQLite database, resumes HTTP Range
transfers after restart, validates required files and every declared weight
size/SHA-256, then atomically promotes the completed repository on the same
filesystem. Partial content is never exposed as installed. Removal accepts
only the exact resolved managed repository, rejects symlinks and active-job
models, and never targets the shared `HF_HOME` cache.

Files are transferred sequentially (`parallelism=1`). Each file gets up to five
bounded connection retries from its current byte offset. This deliberately
trades peak download throughput for predictable disk/network pressure on the
development workstation.

Catalog `media_types` is presentation metadata with the closed values `image`,
`video`, and `audio_video`. It must agree with the runtime capability family,
but is never a router input. This lets one Model Management view classify future
video models without creating a second installer or changing generation APIs.

### G7 candidate catalog (not adopted)

The following exact revisions are discoverable in Model Management as
`experimental` / `measurement_confidence=low`. None is an adopted default or
an available runtime. The current official runtimes are CUDA-first; therefore
the descriptors advertise only `cuda` until a real ROCm/gfx1201 run succeeds.

```text
general/lightweight T2V+I2V     Wan-AI/Wan2.2-TI2V-5B @ 921dbaf3 (34,201,521,212 B)
high-quality I2V                Wan-AI/Wan2.2-I2V-A14B @ 206a9ee1 (126,202,610,088 B)
high-quality T2V                Wan-AI/Wan2.2-T2V-A14B @ c8c270b1 (126,199,333,288 B)
character/companion animation   Wan-AI/Wan2.2-Animate-14B @ cb93a225 (51,213,260,089 B main set)
high-feature synchronized audio Lightricks/LTX-2.3 @ 6b5a83e3 (46,149,373,312 B distilled 1.1)
quality comparison              tencent/HunyuanVideo-1.5 @ 9b49404b (71,655,871,264 B selected 720p set)
lightweight fallback            select only after R9700 measurements
```

The three bounded Wan generation repositories are eligible for explicit
Media-Forge-managed download. Animate remains external because its official
preprocessing package contains separately structured detection, pose and
segmentation assets that are not yet a bounded worker bundle. LTX-2.3 and
HunyuanVideo 1.5 also remain external because their runnable package includes
runtime-owned dependencies outside the selected primary checkpoint set. The UI
shows this distinction and the backend rejects an install request for external
candidates before creating an operation.

The pinned Wan repositories declare Apache-2.0. LTX-2.3 uses the LTX-2
Community License Agreement dated 2026-01-05. HunyuanVideo 1.5 uses the Tencent
Hunyuan Community License, including territorial and acceptable-use terms;
its LICENSE and NOTICE must be reviewed rather than treating it as Apache-2.0.
Source identities are the official Hugging Face repositories named above.

All are **NOT TESTED** on the R9700. Before marking one Available or
Recommended, verify the authoritative model/runtime source, license, exact
capabilities, ROCm/gfx1201 operation, VRAM phases, runtime, failure rate, and
all ten adoption-gate answers from `base-plan.md` §24. A candidate that is
removed later must not change the public API.

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
envelope of at most 1024x1024 pixels**. The same pinned implementation is also
accepted for the G2 `image.strict_edit`, `image.single_reference_edit`,
`image.inpaint`, and `image.variation` slices described below.

Identity:

```text
model_id: black-forest-labs/FLUX.2-klein-4B
revision: e7b7dc27f91deacad38e78976d1f2b499d76a294
weights_hash: sha256:f3fcfa8fdaf5ebcd26c33cd53b485ec5ebe54939b5ace585b3f488278dfae278
license: Apache-2.0
pinned weight bytes: 15964212614
shared cache: /data1tb/ControlDeck/data/cache/huggingface
catalog ownership when detected here: external (usable, never removable)
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

### Direct-placement invariant and offload comparison (2026-08-22)

The image adapter now inspects the loaded pipeline, text encoder, transformer,
and VAE before accepting a direct-device load. In `direct_device_map` mode it
fails the worker if any component remains on CPU/meta, any device map targets
CPU/disk/meta, or any Accelerate CPU/offload hook is found. This prevents a
library/runtime change from silently turning the measured route back into an
offload route. The bounded placement summary is internal worker telemetry; it
does not change the frozen public API.

An exact-branch 512x512 / four-step ControlDeck Workflow/Broker run measured:

```text
direct_device_map total:                15.049693 s
  adapter load / generation:            10.426083 / 1.487908 s
  placement:                            pipeline/text encoder/transformer/VAE = cuda:0
  offload hooks / non-GPU targets:      0 / 0
  sampled incremental peak VRAM:        21,819,142,144 bytes (separate run)

cpu_offload first valid comparison:     40.504328 s
  adapter load / generation:            25.533552 / 7.037108 s
  sampled incremental peak VRAM:         8,879,714,304 bytes
cpu_offload cache-warm repeat:           18.069923 s
  adapter load / generation:             9.655885 / 4.586891 s
  placement:                            all four components resident on CPU between calls
  detected offload hooks:               text encoder / transformer / VAE
```

The outputs were byte-identical for the same seed (168,170-byte PNG, SHA-256
`9f644dfc60d63f51b14858fd01bd34b45f400c682019565cd001484ee48b7037`).
Both routes acquired, renewed, and released a ControlDeck lease; no active
Media Forge lease remained. One earlier comparison attempt was discarded after
the observer itself polled two APIs every 50ms and caused `host_unreachable`;
it is not included in the timing table.

`cpu_offload` is therefore a real VRAM/latency tradeoff for constrained hardware,
not a speed optimization and not the R9700 default. `direct_device_map` plus
`disable_mmap` remains the standard route. The one-shot worker intentionally
exits after lease release, so a later job reloads weights from the persistent
NVMe/page/ROCm caches. Keeping a live 20+GB GPU pipeline between leases would
misreport resident VRAM and obstruct ControlDeck's LLM coexistence policy;
compiled caches can persist on NVMe, live GPU tensors cannot be treated as a
reusable disk artifact.

## Deferred candidate — Qwen-Image

Qwen-Image remains **NOT TESTED** and was not downloaded. It is an alternative
only if the accepted FLUX.2 route later fails the target-hardware or quality
gate; candidates are not installed for their own sake.

## G2 optional semantic reviewer — Qwen3-VL 2B

Adoption state: **accepted as an explicit opt-in, CPU-only advisory reviewer**.
It is not an image generator, does not replace deterministic validation, and is
not called when `qa.semantic=false`.

```text
runtime: Ollama loopback API
model: qwen3-vl:2b-instruct
Ollama ID: ea422f1e7365
size: 1.9 GB
parameters: 2.13B / Q4_K_M
license: Apache-2.0
```

### `base-plan.md` section 24 adoption answers

1. It fills G2's advisory semantic review after deterministic validation.
2. It uses the generic `SemanticReviewer` boundary and loopback HTTP. The core
   imports no model runtime and ControlDeck credentials are not reused.
3. Two direct accepted reviews and two real product jobs ran on the R9700 host.
   The deliberate mismatch product job produced two rejections as intended.
4. Review input is normalized to RGB JPEG, at most 768x768 and 2 MiB; context is
   4,096 tokens and retry count remains the public 0..3 bound.
5. The exact Ollama manifest reports Apache-2.0.
6. Reviewer identity and semantic result are recorded in provenance; the agent
   generation response still exposes only job/asset IDs.
7. It adds about 1.9 GB on disk and about 3.0..4.3 GiB RSS while loaded. The
   request retains it for only one minute to cover bounded retries. The original
   G2 thinking-tag measurements were 31.289228 / 13.745254 seconds; C5 records
   the instruct-tag replacement separately below.
8. Ollama is a separate external process. Requests force `num_gpu=0`; observed
   review-runner swap was zero and GPU VRAM did not increase.
9. It uses Ollama's maintained Qwen3-VL runtime with structured output. No
   custom kernels or arbitrary commands are introduced.
10. Yes. Removing the model makes `image.semantic_review` unavailable without
    changing the frozen job, asset, provenance, workflow, agent, or Add-on
    contracts; ordinary generation and editing continue.

The reviewer remains opt-in because CPU review latency and multi-GiB RSS
are material. A local Ollama install is discovered, never downloaded during a
job. Remote reviewer URLs are rejected. ControlDeck Gateway reuse is deferred
until the Host exposes a generic scoped inference authority; Media Forge does
not read or duplicate the Host's Gateway secret.

## G2 supplement — strict edit

Adoption state: **accepted for `image.strict_edit` on the measured R9700
envelope of at most 1024x1024 source images**. This is an additive capability
of the already adopted immutable FLUX.2 Klein 4B revision, not a new model or
runtime. The public operation remains `image.edit`; strictness and the mask
asset ID are constraints. No model ID or filesystem path was added to the
public contract.

The section 24 answers remain the G1 answers above with these G2-specific
supplements: the upstream Diffusers pipeline accepts a source image; Media
Forge supplies only a bounded mask crop, composites the result itself, copies
every protected RGBA pixel from the immutable source, and independently rejects
any protected-pixel difference before asset registration. The mask hash and
source hash are recorded in provenance. Removing the model still leaves the
generic operation, constraints, asset, lineage, and validator contracts intact,
so gate #10 remains Yes.

Real ControlDeck agent/Broker runs on the R9700 observed:

```text
source/mask/result:             1024x1024 RGBA PNG
first accepted edit total:      17.772403 sec
  adapter load/generation:       9.037687 / 5.164945 sec
same-seed repeat total:         13.942717 sec
  adapter load/generation:       9.045363 / 1.394409 sec
third-generation lineage total: 14.959 sec
  adapter load/generation:      10.085912 / 1.329025 sec
sampled worker peak RSS:         8,743,202,816 bytes
sampled worker swap:             0 bytes
sampled absolute VRAM used:     17,898,610,688 bytes
protected RGBA pixel changes:    0
editable mask pixels:           10,179
changed editable pixels:        10,154
same-seed output SHA-256:       8433840ef27840efe916a82786cab2224fe3d6246dcdb980eab2debab24975e5
```

All inspected pipeline components were on `cuda:0`; offload hooks and non-GPU
targets were zero. Each run used the existing conservative measured lease
request and released it. The VRAM number above is absolute sampled device use,
not an incremental peak and not a replacement for the G1 lease envelope.

The first real edit worker finished in 27.4 seconds but exposed a 25-second
agent wait bound: the Host call returned 504 and postprocessing could not update
the already failed Host Job. This run is not counted as success. The bound is
now 110 seconds, below ControlDeck's 120-second generic execution timeout; the
subsequent three product jobs completed normally.

At the same observation point the host had about 3.9 GB of globally allocated
swap, primarily stale pages belonging to long-lived unrelated processes. The
Media Forge worker used zero swap during both the original 852-second G1 slow
route and the accepted G2 edits; `vmstat` showed no sustained swap-out. RAM
shortage/pagefile thrashing is therefore rejected as the cause of the measured
12-minute-class load. The direct-placement/mmap diagnosis above remains the
observed cause for this implementation.

### Single-reference edit and variation supplement

The same immutable model and adapter are accepted for whole-image reference
editing and variations. These modes use one source asset and produce a new
lineage child; unlike strict/inpaint mode they explicitly do not promise
unchanged pixels. `edit_mode=reference|variation` selects capability routing
without exposing a model name.

The first 1024x1024 variation process completed, but its first reference-image
ROCm compile took 229.208449 seconds after a 9.424858-second load. The browser's
180-second assertion therefore timed out and this run is not browser-success
evidence. The job itself succeeded, its Host lease was released, and a later
separate worker reused persistent compiler/storage caches:

```text
variation browser total:       27.002184 sec
  adapter load/generation:      9.655933 / 10.720631 sec
reference edit browser total:  25.875298 sec
  adapter load/generation:     10.693552 / 9.148814 sec
final exact-branch variation:  25.737216 sec
  adapter load/generation:      9.577456 / 9.121249 sec
output:                        1024x1024 RGBA PNG, 1,447,679 bytes
repeat output SHA-256:         b03dd63d868edc5d2242f6d4ac21a06f8c46bb214e611e5175c666e806778689
placement:                     all inspected components cuda:0
offload hooks/non-GPU targets: 0 / 0
lease after each job:          released; active 0 / waiting 0
```

The accepted visual retained the anime character's orange mesh hair and black/
orange hoodie while producing a cheerful two-hand waving pose. This is a
bounded observed sample, not a general character-identity guarantee; structured
identity evaluation belongs to G3.

### Outpaint supplement

`image.outpaint` uses the same model through `image.edit`. Media Forge builds a
larger centered reference canvas, derives the exterior generation region, then
recopies and independently validates every original RGBA pixel. The model is
never trusted to preserve the source rectangle.

Real installed-host Chromium extended a Media Forge generated 512x512 character
to 768x512 on the R9700:

```text
first outpaint browser total: 108.756109 sec
  adapter load/generation:     10.742962 / 92.188142 sec
warm separate worker total:    19.807051 sec
  adapter load/generation:     10.774391 / 3.397528 sec
preserved source pixels:       262,144; RGBA differences 0
generated exterior pixels:     131,072
output:                        768x512 RGBA PNG, 281,762 bytes
same-seed SHA-256:             04c00781464a760d5d4c066c2c2da8b3d6455cff198988652171eec818298f26
placement:                     all inspected components cuda:0
offload hooks/non-GPU targets: 0 / 0
Broker after each:             active 0 / waiting 0
```

The 92.2-second first generation is retained as a resolution/route-specific
ROCm compile sample. It is not attributed to RAM pressure or swap; the warm
separate-worker repeat demonstrates persistent compiler/cache reuse. Visual
inspection showed the original character unchanged and the neutral background
extended continuously on both sides.

### Multi-reference supplement

The locally installed Diffusers `Flux2KleinPipeline` signature accepts an image
or image list. Media Forge bounds `image.multi_reference_edit` to one primary
plus one to three additional asset references, materializes only job-local
copies, resizes them to the primary generation envelope, and passes the list to
the same isolated worker. The primary is the lineage parent; all input hashes
remain in provenance.

Two installed-host Chromium jobs used a Media Forge-generated 512x512 primary
and two Media Forge-generated 1024x1024 references:

```text
first browser total:           28.895831 sec
  adapter load/generation:      9.890928 / 11.739208 sec
separate-worker repeat:        21.830374 sec
  adapter load/generation:      9.882474 / 4.771229 sec
output:                        512x512 RGBA PNG, 352,021 bytes
same-seed SHA-256:             7ce548fa7ed146e60862ba9de01f2f65bc759988887f92e113c31f516db4d281
lineage parents:               primary only (1)
provenance reference hashes:   primary plus two references (3)
placement:                     all inspected components cuda:0
offload hooks/non-GPU targets: 0 / 0
Broker after each:             active 0 / waiting 0
```

Visual inspection found that the result combined the primary black/orange hair
design and clothing with the referenced orange mesh detail and two-hand waving
pose. This is evidence that the multi-image route is active, not a statistical
G3 character-consistency guarantee.

## UX2 C5 adoption refresh — R9700 and creative evaluator

The exact FLUX.2 Klein 4B revision remains the Recommended local image route.
C5 did not promote a new image model. An isolated current-source Media Forge,
an isolated ControlDeck Host, the real Broker, and the retained managed model
store produced three new 512x512 / four-step character candidates:

```text
model/revision:       black-forest-labs/FLUX.2-klein-4B
                      e7b7dc27f91deacad38e78976d1f2b499d76a294
runtime:              Diffusers 0.40.0 / PyTorch 2.10.0+ROCm 7.2.1
placement:            direct_device_map, all components cuda:0, mmap disabled
first process:        15.967179 s (load 11.335529 / generation 1.584339)
later processes:      17.460744 / 19.440341 s
                      (load 13.448332 / 14.989607,
                       generation 1.461965 / 1.592628)
sampled VRAM:         21,245,644,800 first absolute peak;
                      17,478,889,472 / 17,470,918,656 later absolute peaks
worker peak RSS:      16,494,501,888 bytes
worker swap:          0 bytes
lease after runs:     active 0 / waiting 0
```

The conservative 1024 acceptance envelope remains authoritative: resident 0,
execution peak 29,625,200,640, cold-load peak 32,275,578,880, headroom
1,073,741,824, reservation 33,349,320,704 bytes. C5 did not flush the shared
kernel page cache, so fully storage-cold load remains **NOT TESTED**. Existing
same-revision multi-reference acceptance above remains applicable; it was not
rerun in C5. The catalog declares `supports_lora=false`, therefore LoRA is
**UNAVAILABLE**, not unmeasured.

The optional CPU evaluator now uses `qwen3-vl:2b-instruct`, Ollama digest
`ea422f1e7365`, 1,889,519,783 bytes, Apache-2.0. The prior `qwen3-vl:2b`
thinking tag ignored `think=false` under Ollama 0.31.1, spent 105 seconds in
reasoning, returned empty content, and correctly failed closed. The instruct
renderer evaluated three candidates in 40.60 seconds; GPU VRAM was unchanged
at 59,949,056 bytes and Media Forge job count remained 3. Installed-host browser
ranking repeated in 40.222 seconds with no job delta. Scores are advisory and
never override deterministic validation or request regeneration.

The unchanged G2 semantic-review path also accepted a real candidate with the
instruct tag. Its first call completed before a probe-output typo at 12.88
seconds; the corrected warm call took 2.08 seconds. Both observed GPU samples
remained 59,949,056 bytes.

A bounded worker-crash probe killed the image subprocess with SIGKILL after
lease acquisition. The job failed as `worker_crash`, the lease count returned
to zero, and core health remained `healthy` after 1.374453 seconds.
