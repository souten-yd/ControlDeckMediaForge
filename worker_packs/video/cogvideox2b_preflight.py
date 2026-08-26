from __future__ import annotations

"""Weight-free ROCm preflight for the pinned CogVideoX-2B candidate."""

import json


CANDIDATE_REPOSITORY = "zai-org/CogVideoX-2b"
CANDIDATE_REVISION = "1137dacfc2c9c012bed6a0793f4ecf2ca8e7ba01"


def main() -> None:
    import diffusers
    import torch
    import transformers
    from diffusers import (
        AutoencoderKLCogVideoX,
        CogVideoXPipeline,
        CogVideoXTransformer3DModel,
    )
    from diffusers.models.attention_processor import CogVideoXAttnProcessor2_0

    if not torch.cuda.is_available() or torch.version.hip is None:
        raise RuntimeError("CogVideoX-2B preflight requires ROCm")
    properties = torch.cuda.get_device_properties(0)
    architecture = str(getattr(properties, "gcnArchName", ""))
    if architecture != "gfx1201":
        raise RuntimeError("CogVideoX-2B preflight requires the target gfx1201 GPU")
    if not hasattr(torch.nn.functional, "scaled_dot_product_attention"):
        raise RuntimeError("PyTorch SDPA is unavailable")

    print(
        json.dumps(
            {
                "candidate_repository": CANDIDATE_REPOSITORY,
                "candidate_revision": CANDIDATE_REVISION,
                "torch": torch.__version__,
                "hip": torch.version.hip,
                "diffusers": diffusers.__version__,
                "transformers": transformers.__version__,
                "gpu": torch.cuda.get_device_name(0),
                "architecture": architecture,
                "pipeline": CogVideoXPipeline.__name__,
                "transformer": CogVideoXTransformer3DModel.__name__,
                "vae": AutoencoderKLCogVideoX.__name__,
                "attention_processor": CogVideoXAttnProcessor2_0.__name__,
                "attention": "pytorch_sdpa",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
