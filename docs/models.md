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

## G1 benchmark candidates

FLUX.2 [klein] 4B and Qwen-Image remain unevaluated candidates. Neither is installed, selected by the router, or promoted as a default. The ten answers required by `base-plan.md` §24 and R9700/gfx1201 measurements must be added before promotion.

Current state: **NOT TESTED** for PyTorch/ROCm compatibility, cold/warm load, generation speed, VRAM envelope, failure rate, and license-policy routing.

