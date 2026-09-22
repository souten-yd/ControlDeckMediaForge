# Qwen-Image-2.1: Vulkan configuration

Date: 2026-09-22. Status: source integration accepted for manual text-to-image; installed acceptance pending.

The user requested community investigation and application of an appropriate
configuration after accepting the Research License. This is a new evaluation
following the [completed Quanto evaluation](qwen-image-21-evaluation-20260922.md).
The earlier tooling-only instructions describe that completed slice; the new
authorization permits a measured local research integration. Commercial use is
not included in the consent.

## Configuration and sources

The [upstream guide](https://github.com/leejet/stable-diffusion.cpp/blob/6dcb5bbd4278aa8f6d851f7515e87555f8e757b7/docs/qwen_image_2.1.md)
requires Qwen3-VL-8B and its dedicated VAE; old Qwen/Wan VAEs are incompatible.
A [first-hand community report](https://www.reddit.com/r/StableDiffusion/comments/1wmf9jt/qwen_image21_gguf_in_comfyui_doesnt_work/)
describes noise when substituting Qwen3.5-9B and resolving it with Qwen3-VL.
This is a compatibility lead, not a benchmark on this machine.

The [GGUF announcement discussion](https://www.reddit.com/r/StableDiffusion/comments/1wlj8r2/qwenimage21_gguf_is_out/)
also discusses INT8 ConvRot performance. The pinned
[implementation documentation](https://github.com/leejet/stable-diffusion.cpp/blob/6dcb5bbd4278aa8f6d851f7515e87555f8e757b7/docs/int8_convrot.md)
states that accelerated ConvRot kernels are CUDA-specific; Vulkan falls back to
CPU. Those community CUDA timings are therefore not a Vulkan recommendation.
Q8 diffusion weights are the initial quality baseline; no Q4 quality equivalence
or Q8 speed advantage is assumed.

| Component | Repository / revision | File | Bytes |
|---|---|---|---:|
| Diffusion | leejet/Qwen-Image-2.1-GGUF / cc11433936a06e9765f7c0c0b1f0436cfd2b9856 | qwen_image_2.1-Q8_0.gguf | 7,687,155,744 |
| Text encoder | Qwen/Qwen3-VL-8B-Instruct-GGUF / f982a07559d4a2f6c8744d840bf6fccab30eea96 | Qwen3VL-8B-Instruct-Q4_K_M.gguf | 5,027,784,800 |
| Vision projection | same encoder revision | mmproj-Qwen3VL-8B-Instruct-F16.gguf | 1,159,029,824 |
| VAE | Comfy-Org/Qwen-Image-2.1 / ace0edeb3791a594ddfa36ed5f41a178a394e921 | vae/qwen_image_2.1_vae_bf16.safetensors | 675,509,688 |

Diffusion and VAE derivatives retain the approved Qwen Research License; the
official encoder is Apache-2.0. These are file sizes, not runtime VRAM estimates.
Correction to the earlier discussion: the original 1.258 GiB VAE checkpoint
stores F32 tensors. The new 0.629 GiB checkpoint stores BF16 tensors. The previous
Diffusers probe cast the original checkpoint during loading.

## Build and device verification

Pinned stable-diffusion.cpp: `6dcb5bbd4278aa8f6d851f7515e87555f8e757b7`.
Patched GGML: `4bf5f6000653b7881d00963cd6ddb665ccd62a8d`.
Built with CMake/Ninja, Release, SD_VULKAN=ON, SD_HIPBLAS=OFF, SD_CUDA=OFF,
SD_WEBP=OFF, SD_WEBM=OFF, GGML_NATIVE=OFF; target sd-cli, four compile jobs.
Build completed successfully. This does not establish model execution.

`sd-cli --list-devices` reports integrated graphics as Vulkan0 and R9700 as
Vulkan1. With `GGML_VK_VISIBLE_DEVICES=1`, only R9700 is visible, named Vulkan0.
Every actual inference must hold a normal Host gpu0 lease and declare its runtime
estimate. The private supervisor checks capacity/PCI mapping, renews the lease,
limits its own cgroup, preserves a 3 GiB Host RAM floor and releases on failure.

Evidence directory: feature maintenance `qwen-image-21-vulkan-20260922/`.
All four weight digests verified (14,549,480,056 bytes). The experiments below
used the normal operator's exclusive gpu0 lease, renewal, bounded process lifetime
and a 3 GiB free-Host-RAM floor. OOM counters stayed zero, Host health was HTTP 200,
and each supervisor released its lease. Peak device usage includes the small
idle display allocation; it is not a PyTorch allocator measurement.

## Integration under verification

The image worker has a dedicated native adapter and a separately configured
runtime root. The adapter verifies the pinned version, binary checksum, device
name, Host device mapping and the full measured VRAM budget. The worker reports
GGUF Q8_0/Q4_K_M provenance without initializing or reporting the Torch allocator.
Native alpha is not accepted: the product worker keeps RGB unchanged and sets
alpha to opaque, reporting `alpha.set_opaque`. Explicit cutout requests continue
through the existing BiRefNet matting stage. A native child receives PDEATHSIG before exec; a real CPU process test
confirmed that it terminates when its owning worker is killed. Actual GPU cancellation also passed: after loading more than 12 GiB,
SIGTERM of the worker terminated its native child and returned GPU usage to
59,912,192 bytes within 0.504 seconds, with no output. This checks cancellation
during loading; cancellation during denoising through the installed UI remains
NOT TESTED.

Routing accepts Vulkan as a distinct backend. The research candidate is
`manual_only`; all five automatic policies exclude it even if it is the only
installed model. Policy ranks are ascending preferences: zero is the highest
priority, not a disable switch. Existing model defaults remain false for
`manual_only`. A missing native runtime makes both the picker and routing reject
the model. Normal managed installation can copy already downloaded pinned
components from the HF cache, then runs the existing SHA verification/atomic
promotion; it does not trust cached bytes without verification.

## Actual results and chosen defaults

| Run | Setting | Seconds | Peak device bytes | Result |
|---|---|---:|---:|---|
| Normal RGB | 512 square, 8 steps, CFG1 | 8.034 | 15,481,954,304 | Red apple and leaf visible |
| Normal RGB repeat | 1024 square, 20 steps, CFG1 | 60.574 / 61.181 / 60.890 | 19,297,214,464 | Three separate workers, identical PNG SHA |
| Final normal RGB | 1024 square, 16 steps, CFG1 | 50.991 worker / 51.242 supervisor | 19,295,055,872 | Accepted normal-image sample |
| Native alpha | 1024 square, 20 steps, CFG1 | 60.520 | 19,276,914,688 | Background residue and outlines: rejected |
| Native alpha | 512 square, 20 steps, CFG6 | 24.361 | 15,491,592,192 | Stronger alpha but oversaturated and speckled |
| Native alpha | 1024 square, 12 steps, CFG6 | 70.816 | 19,295,633,408 | Stronger alpha, poor color and stray fragments: rejected |
| Reference edit | 512 square, 20 steps, CFG1 | 25.373 | 16,791,158,784 | Red-to-green apple, composition retained |
| Reference edit | 1024 square, 16 steps, CFG1 | 101.695 worker / 101.771 supervisor | 20,580,290,560 | Color changed, excessively altered texture: not adopted |

The final normal worker RSS peak was 18,729,594,880 bytes. The edit sample reached
20,215,345,152 bytes. The three repeated normal images had SHA-256
`a7c06f2ce91f3abebc0eb9133e6e62954c2302e10d446d511851a7fbb6c75094`.
This establishes reproducibility of those executions, not mathematical accuracy
of every GPU operator. Original full BF16 encoder directory/index attempts both
failed metadata validation before inference; no BF16 quality comparison occurred.
No Q8-encoder, Q4-diffusion or ConvRot speed/quality claims are made.

The selected product configuration is **manual text-to-image only**, 1024 square,
16 steps, CFG1. It retains the existing FLUX default and advertises neither
reference editing nor native transparency. A 1 GiB admission headroom is policy,
not an additional measurement. Each sd-cli exits after its image, so subsequent
jobs always request the full allocation, even when the lightweight worker lives.
There is no CPU fallback for a smaller grant. The dimensional limit is 1024 per
side and a multiple of 32. Other prompts and texture UV preservation remain
subject to visual review; one apple is not a broad quality benchmark.

Alpha was inspected in Chromium over white, black and checkerboard backgrounds.
Raw RGB-only image viewers can misleadingly show colored pixels underneath
transparent areas. At CFG6 the background is mostly transparent, but fragments
near the leaf and color oversaturation remained. The existing FLUX + BiRefNet
baseline was cleaner in this comparison, so native RGBA was not adopted.

## Library registration and remaining acceptance

Four unique outputs were imported through installed 0.32.2's normal
`POST /api/v1/assets/import`: red apple, 512 green edit, CFG1 alpha and CFG6 alpha.
Their provenance truthfully records local import rather than a fictitious
production generation Job. Re-encoding changed PNG hashes; decoded RGBA pixels
were byte-identical. Receipts retain original and registered hashes.

- Normal red: `asset_5d2f5cf73e0f4c39b3460ec52b4d2438`
- Green reference edit: `asset_819e61f81fa441c3a2a7075d81d45787`
- Experimental CFG1 alpha: `asset_797082d03d51488c916c2e6a1d951cff`
- Experimental CFG6 alpha: `asset_8ca30c59035946fcbef917ed2567511a`

Actual Host Chromium at 1280px showed all four Library entries in the opaque
iframe, with zero page errors. Nine existing user scenes were visible. Receipt:
`library-import.json`; browser result/screenshot: `library-host-scenes.json`,
`library-host.png`. These imported samples do not establish installed Qwen
routing. Normal managed model installation, signed release/update, installed
manual generation, default-model regression and mobile/restart checks are pending.

The native binary was installed separately at the documented runtime root;
SHA-256 `b29ea3dd643a77b634685d3d4435fa9492cd31facf9ce1153aedfbd2a0ea755a`,
82,211,600 bytes. The existing FLUX/H3 build and Python dependencies were retained.
The source checkout `feat/g9-image-to-3d` remains unchanged.

Source validation: `./mf.sh test` — 2399 passed, 3 warnings, 271.69 seconds.
