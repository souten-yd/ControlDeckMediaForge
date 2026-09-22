# Qwen-Image-2.1 evaluation preparation

Date: 2026-09-22
Status: tooling ready; model inference and adoption NOT TESTED

MediaForge 0.32.2 was published and installed before this work. See
[release verification](release-0.32.2-20260922.md). This slice adds an offline
probe and tests; the model catalog, production adapter and shared runtime pins
are unchanged.

## Identity and consent boundary

The pinned [model metadata](https://huggingface.co/api/models/Qwen/Qwen-Image-2.1/revision/790c92633540aa0cb11d9abf19eb46d861714758?blobs=true)
reports `Qwen/Qwen-Image-2.1`, revision
`790c92633540aa0cb11d9abf19eb46d861714758`, seven safetensors files,
33,115,613,408 bytes (30.841318339 GiB). No model weights were downloaded.

The [license at that revision](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/790c92633540aa0cb11d9abf19eb46d861714758/LICENSE)
has SHA-256 `8dc973f024ff95966bea25866efa443fd16776dcb1001e681e3d467ea572b28d`.
It is the Qwen Research License: research/evaluation purposes only; commercial
use requires a separate license; redistribution has agreement, modification
notice and attribution conditions. Explicit user consent for the pinned weights
was requested and has not yet been received. No acceptance ID was fabricated.

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

These checks establish import compatibility only. FLUX.2 generation, quality,
VRAM and latency regression are NOT TESTED; production pins must stay unchanged.

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

Remaining: user license consent; normal Host login refresh; actual FLUX.2
baseline/candidate regression; bounded Qwen CPU load/generation; GPU bf16 and
int8 runs; numerical reference comparison; RGBA versus existing background
removal and visual quality. The earlier dedicated Host session returned 401;
`bash ~/mf-login.sh` was requested. No GPU inference was run without a lease.
No model registry, product routing, resolution default or quantization default
was changed. The model is not adopted and no Qwen-generated assets exist yet.

Evidence lives in private feature maintenance
`qwen-image-21-evaluation-20260922/`: identity/license digest, dependency pins,
candidate import report, unchanged production metadata, capacity, test logs and
the two real error-result JSON files.
