from __future__ import annotations

"""Weight-free ROCm preflight for the pinned Wan 2.1 1.3B candidates."""

import json


T2V_REPOSITORY = "Wan-AI/Wan2.1-T2V-1.3B-Diffusers"
T2V_REVISION = "0fad780a534b6463e45facd96134c9f345acfa5b"
T2V_SNAPSHOT_BYTES = 28_935_653_511
T2V_WEIGHT_FILES = 10
T2V_WEIGHT_BYTES = 28_928_720_056

VACE_REPOSITORY = "Wan-AI/Wan2.1-VACE-1.3B-diffusers"
VACE_REVISION = "ec4d2cb062b548996b179d493fdd05340de702a1"
VACE_SNAPSHOT_BYTES = 19_043_130_596
VACE_WEIGHT_FILES = 8
VACE_WEIGHT_BYTES = 19_036_896_776


def main() -> None:
    import diffusers
    import torch
    import transformers
    from diffusers import (
        AutoencoderKLWan,
        WanPipeline,
        WanTransformer3DModel,
        WanVACEPipeline,
        WanVACETransformer3DModel,
    )
    from diffusers.models.transformers.transformer_wan import WanAttnProcessor

    if not torch.cuda.is_available() or torch.version.hip is None:
        raise RuntimeError("Wan 2.1 1.3B preflight requires ROCm")
    properties = torch.cuda.get_device_properties(0)
    architecture = str(getattr(properties, "gcnArchName", ""))
    if architecture != "gfx1201":
        raise RuntimeError("Wan 2.1 1.3B preflight requires the target gfx1201 GPU")
    if WanAttnProcessor._attention_backend is not None:
        raise RuntimeError("Wan default attention backend changed")
    if not hasattr(torch.nn.functional, "scaled_dot_product_attention"):
        raise RuntimeError("PyTorch SDPA is unavailable")

    print(
        json.dumps(
            {
                "torch": torch.__version__,
                "hip": torch.version.hip,
                "diffusers": diffusers.__version__,
                "transformers": transformers.__version__,
                "gpu": torch.cuda.get_device_name(0),
                "architecture": architecture,
                "attention": "pytorch_sdpa",
                "custom_kernel": False,
                "vae": AutoencoderKLWan.__name__,
                "t2v": {
                    "repository": T2V_REPOSITORY,
                    "revision": T2V_REVISION,
                    "pipeline": WanPipeline.__name__,
                    "transformer": WanTransformer3DModel.__name__,
                    "snapshot_bytes": T2V_SNAPSHOT_BYTES,
                    "weight_files": T2V_WEIGHT_FILES,
                    "weight_bytes": T2V_WEIGHT_BYTES,
                },
                "i2v": {
                    "repository": VACE_REPOSITORY,
                    "revision": VACE_REVISION,
                    "pipeline": WanVACEPipeline.__name__,
                    "transformer": WanVACETransformer3DModel.__name__,
                    "snapshot_bytes": VACE_SNAPSHOT_BYTES,
                    "weight_files": VACE_WEIGHT_FILES,
                    "weight_bytes": VACE_WEIGHT_BYTES,
                    "conditioning": ["video", "mask", "reference_images"],
                },
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
