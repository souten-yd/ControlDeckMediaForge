# Qwen-Image-2.1 evaluation preparation

Date: 2026-09-22
Status: consent received; FLUX regression measured; Qwen weights provisioning;
Qwen inference and adoption NOT TESTED

MediaForge 0.32.2 was published and installed before this work. See
[release verification](release-0.32.2-20260922.md). This slice adds an offline
probe and tests; the model catalog, production adapter and shared runtime pins
are unchanged.

## Identity and consent boundary

The pinned [model metadata](https://huggingface.co/api/models/Qwen/Qwen-Image-2.1/revision/790c92633540aa0cb11d9abf19eb46d861714758?blobs=true)
reports `Qwen/Qwen-Image-2.1`, revision
`790c92633540aa0cb11d9abf19eb46d861714758`, seven safetensors files,
33,115,613,408 bytes (30.841318339 GiB). Weight provisioning began after the
explicit consent below; complete-file verification is still in progress.

The [license at that revision](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/790c92633540aa0cb11d9abf19eb46d861714758/LICENSE)
has SHA-256 `8dc973f024ff95966bea25866efa443fd16776dcb1001e681e3d467ea572b28d`.
It is the Qwen Research License: research/evaluation purposes only; commercial
use requires a separate license; redistribution has agreement, modification
notice and attribution conditions. On 2026-09-22 the user explicitly approved
the presented terms: 「規約同意を承認する」. Private `license-consent.json` records
the exact revision, license digest, message and noncommercial evaluation scope.
The pinned remote license bytes and metadata were rechecked and matched the
previous records before starting a separate 26-file provisioning operation.
No product acceptance ID was fabricated and no model registry entry was added.

## Candidate dependencies

[Upstream PR #14804](https://github.com/huggingface/diffusers/pull/14804) is merged;
the current PyPI diffusers release is still 0.40.0. The candidate is pinned to
diffusers commit `7263f3317f6b392d62f41e9d75ed9d7e21fc5a5c` (0.41.0.dev0).
The downloaded source archive SHA-256 is
`7a2b2685c2ee6f41327dfecf14a2a8c2c778012b0add1c7c0b004ccd6515ef2a`.
The [upstream pipeline documentation](https://github.com/huggingface/diffusers/blob/7263f3317f6b392d62f41e9d75ed9d7e21fc5a5c/docs/source/en/api/pipelines/qwenimage21.md)
specifies 40 steps and no classifier-free guidance by default.

| Dependency | Installed production | Evaluation candidate |
|---|---|---|
| Torch | 2.10.0+rocm7.2.1.lw.gitb07cec22 | same worker package |
| diffusers | 0.40.0 | 0.41.0.dev0, pinned commit above |
| transformers | 5.15.1 | 5.17.0 |
| tokenizers | 0.22.2 | 0.23.1 |
| huggingface-hub | 1.28.0 | 1.32.0 |
| optimum-quanto | 0.2.7 | 0.2.7 |

An isolated evaluation Python uses the existing image worker's site-packages as
a read-only base, with candidate packages installed locally using `--no-deps
--ignore-installed`. Its directory is under private feature maintenance,
`qwen-image-21-evaluation-20260922/candidate/.venv`. It is not a registered
production runtime. [Candidate pins](../../scripts/qwen_image_probe_requirements.txt)
must not be installed into core or the shared production runtime.

The first import failed because the new diffusers imports `httpx` from
`huggingface_hub.utils`, which the installed 1.28.0 does not export. Updating only
the candidate hub to 1.32.0 resolved that failure. With all GPU devices hidden:

- `QwenImage21Pipeline`, `Flux2KleinPipeline` and
  `Qwen3VLForConditionalGeneration` imported successfully.
- `pip check` returned `No broken requirements found`.
- Torch remained ROCm, reporting HIP 7.2.53211; no CUDA wheel replacement occurred.
- A fresh check of the installed production package metadata matched the
  original versions in the table.

Those initial checks established import compatibility only. The subsequent
ordinary Host login and measured FLUX comparison are recorded below. Production
pins remain unchanged.

## Consent, ordinary login and FLUX comparison

The user refreshed the dedicated login after consenting. The normal helper
reported `authenticated: true`, `operator_permissions: true`. All GPU processes
used ordinary `/api/v1/resources` requests, declared `estimated_runtime_sec`,
renewed active exclusive leases and released their own leases afterward.
The broker GPU capacity matched card0 / PCI 0000:03:00.0, and the child verified
one visible device, R9700 / gfx1201 / 34,208,743,424 bytes.

The private supervisor starts one named systemd user service per evaluation,
with cgroup memory limits, swap disabled, a timeout, a 3 GiB host available-memory
floor and Host auth/me latency samples. Production FLUX quantized caches were
copied into separate baseline/candidate directories before invoking the existing
adapter; candidate failures cannot rewrite the production cache.

First measured comparison: identical apple prompt, seed42, 1024x1024, four
steps, int8 text encoder and transformer, CPU offload, four CPU threads,
`ROCBLAS_USE_HIPBLASLT=0`, otherwise automatic PyTorch BLAS selection:

| Metric | Production dependencies | Candidate dependencies |
|---|---:|---:|
| Process cold model load, seconds | 1.046959 | 0.964734 |
| First generation, seconds | 20.604085 | 14.461918 |
| Following generations, seconds | 5.888875 / 5.229638 | 5.777503 / 5.104223 |
| PyTorch peak allocated bytes | 6,572,957,184 | 6,572,957,184 |
| PyTorch peak reserved bytes | 9,093,251,072 | 9,093,251,072 |
| Sampled total device peak bytes | 12,400,848,896 | 9,984,790,528 |
| Sampled process peak RSS bytes | 11,182,993,408 | 11,495,989,248 |

All six PNG hashes were identical:
`856d293206a59a3db9bb69031d50684ff2395b61961ad38829fc95ec4f4c4ea5`.
The viewed image contains the requested red apple, green leaf and white studio
background. There was no image or allocator-memory regression for this input.
The Qwen download ran concurrently; disk page caches and first-use kernel caches
were not flushed. Cold numbers are process/model loading, not uncached disk
throughput. This one prompt does not cover all FLUX edit/reference operations.
All sampled Host auth/me requests returned200, maximum latency0.007862seconds;
both evaluation cgroups recorded zero OOM/OOM-kill events.

## Numerical reference checks

The historical environment-variable workaround was not assumed sufficient.
Under the candidate worker and `ROCBLAS_USE_HIPBLASLT=0`, an independent CPU
comparison used `A(M,64) @ B(64,32)`, seed42, integer-valued inputs in {-1,0,1}.
Every exact dot product is representable in all three tested dtypes, so both
tolerances were zero. M was262144,524288,524289,1048576,4000000.

- Automatic BLAS: fp32 failed above524288 rows, with maximum absolute differences
  14,27,30; bf16/fp16 matched for all five shapes. Finite values did not detect
  these wrong fp32 results.
- Explicit `torch.backends.cuda.preferred_blas_library("cublas")` (hipBLAS alias
  on this ROCm build): all ten fp32/bf16 cases matched exactly. fp16 at4000000
  rows failed with maximum difference29 and56,305,468 mismatched elements.
- The initial preferred backend was `_BlasBackend.Cublaslt`; explicitly selecting
  the other library reported `_BlasBackend.Cublas`.

This is a measured limitation of these operations/build, not proof of Qwen-wide
correctness or a claim that every gfx1201 operation is broken. No kernel was
patched. The probe now permits explicit `--blas-library cublas` for a GPU run
and records the actual preference. fp16 is not used for the forthcoming Qwen
acceptance. FLUX baseline/candidate were repeated with the explicit setting
before interpreting Qwen results under it.
The library names and alias are the installed PyTorch API, also described in
the [upstream backend documentation](https://docs.pytorch.org/docs/stable/backends.html#torch.backends.cuda.preferred_blas_library).
This preference is not a guarantee that every operation uses that library.

The explicit-hipBLAS FLUX comparison again produced six identical images across
the two dependency environments, SHA-256
`5e204790611a6ba700d2c9d066c7ccada785a345c5510c231acd83959425d3b2`.
These differ from the automatic-library images at the byte level; visual
inspection still showed the requested apple, leaf and white background.

| Metric with explicit hipBLAS | Production dependencies | Candidate dependencies |
|---|---:|---:|
| Process cold model load, seconds | 1.202841 | 0.925454 |
| First generation, seconds | 26.544660 | 26.517920 |
| Following generations, seconds | 18.623572 / 18.076541 | 19.718783 / 18.183155 |
| PyTorch peak allocated bytes | 6,606,511,616 | 6,606,511,616 |
| PyTorch peak reserved bytes | 9,126,805,504 | 9,126,805,504 |

The candidate run overlapped the CPU test suite, in addition to the continuing
weight download, so these timings do not isolate small latency changes.
The explicit library is much slower than automatic selection in both dependency
environments; it is an evaluation setting, not a production recommendation.
All nine files of both private FLUX quantized cache copies still matched the
production originals by SHA-256 after these runs.

## Offline measurement tool

[`scripts/qwen_image_probe.py`](../../scripts/qwen_image_probe.py) runs in an
isolated worker Python. Device, dtype, quantization, dimensions, seed and repeat
count are explicit arguments. It forces offline HF access and accepts immutable
revisions only. It checks local component/shard presence before loading.

For int8 it loads and quantizes the text encoder first, then the transformer,
checks that quantized modules exist, and leaves the VAE unquantized. It does not
silently fall back or create a quantization cache. Runtime support and quality of
these real-model operations remain unmeasured.

The result is one JSON object, including ordinary load errors, missing weights,
GPU unavailability and SIGTERM cancellation. Python and native stdout logs go
to stderr, including buffered native shutdown output. An external SIGKILL or
OOM kill cannot be handled by the killed process; the evaluation supervisor
must record that outcome.

Metrics distinguish cold model loading (including quantization), per-image
inference times (including latent finite checks), process peak RSS, and PyTorch
peak allocated/reserved VRAM. Allocator peaks are not total device usage; the
lease supervisor must also sample the physical device. Unavailable values are
null. The optional output directory must be empty and receives PNG samples and
`probe-result.json`, retaining the model revision, inputs, seed, dependency
versions, measurements and output hashes alongside the images.

Each iteration resets the generator to the same seed. The tool checks finite
latents and floating decoder output before converting to PNG. `has_alpha`
requires both nonopaque pixels and retained visible pixels; opaque RGBA and
fully transparent empty images do not pass. Hash agreement measures
repeatability only. The result explicitly leaves numerical reference comparison
`NOT TESTED`; image quality and foreground correctness still require inspection.

Example, after license consent and separate weight provisioning:

```bash
HF_HUB_OFFLINE=1 ROCBLAS_USE_HIPBLASLT=0 \
  "$PROBE_PYTHON" scripts/qwen_image_probe.py \
  --model-id Qwen/Qwen-Image-2.1 \
  --revision 790c92633540aa0cb11d9abf19eb46d861714758 \
  --device cpu --dtype bf16 --quantization int8 \
  --prompt "a red cube" --seed 42 --repeat 3 \
  --width 1024 --height 1024 --steps 40 --rgba \
  --output-dir "$PROBE_OUTPUT"
```

Set `PROBE_PYTHON` to the candidate worker interpreter and `PROBE_OUTPUT` to a
new private evidence directory. The example must run under bounded host memory
and time supervision. GPU runs additionally require an ordinary Host broker
lease with `estimated_runtime_sec`, renewals and cleanup of only the owned job.

The earlier GEMM investigation is recorded at
[commit 57f2838](https://github.com/souten-yd/ControlDeckMediaForge/commit/57f283892d6f733ead644a207672287a8bc03cdf):
it identified hipBLASLt for the measured fp32 shapes and reported a workaround
using `ROCBLAS_USE_HIPBLASLT=0`. That historical result is not a numerical
acceptance of Qwen or of every operation/dtype. Record the BLAS environment,
recheck relevant CPU/GPU reference operations, and compare the same setting
between baseline and candidate FLUX runs.

## Executed checks and remaining gates

- After explicit BLAS selection was added: `./mf.sh test`,2379 passed,
  3 warnings,281.34seconds. Focused probe tests:18 passed; additional cases
  cover backend selection before loading, selection failure without fallback,
  and rejection of a GPU backend setting on the CPU route.
- `./mf.sh test`: 2376 passed, 3 warnings, 267.19 seconds.
- Focused final probe tests: 15 passed, 2 warnings, 0.22 seconds. Coverage includes
  differing repeated images, alpha semantics, non-finite latents/decoder output,
  component quantization order, output preservation, native stdout and SIGTERM.
- Real candidate Python, all GPUs hidden, the documented CPU/int8/1024 request:
  exit 0, exactly one JSON line, `weights_missing`, zero generated images.
- Real candidate Python, GPUs hidden, GPU request: exit 0, exactly one JSON
  line, `gpu_unavailable`, zero generated images.

The read-only capacity sample was host RAM 32,605,822,976 bytes, available
26,889,367,552 bytes, discrete GPU VRAM 34,208,743,424 bytes, and available disk
208,059,334,656 bytes. These are a snapshot, not a future resource reservation
or model peak measurement.

Remaining: complete pinned weight verification; bounded Qwen CPU load/generation;
GPU bf16 and int8 runs; Qwen
numerical reference comparison; RGBA versus existing background removal and
visual quality. The earlier expired dedicated Host session has been refreshed.
No GPU inference was run without a lease.
No model registry, product routing, resolution default or quantization default
was changed. The model is not adopted and no Qwen-generated assets exist yet.

Evidence lives in private feature maintenance
`qwen-image-21-evaluation-20260922/`: identity/license digest, dependency pins,
candidate import report, unchanged production metadata, capacity, test logs and
the two real error-result JSON files.
