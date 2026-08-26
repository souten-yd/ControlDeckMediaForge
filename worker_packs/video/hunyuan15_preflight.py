from __future__ import annotations

"""Weight-free ROCm preflight for the pinned HunyuanVideo 1.5 candidate."""

import json


CANDIDATE_REPOSITORY = (
    "hunyuanvideo-community/HunyuanVideo-1.5-Diffusers-480p_t2v_distilled"
)
CANDIDATE_REVISION = "1abb14f06518f37448dcf3a6917dd086dd7045c7"
OFFICIAL_MODEL_REPOSITORY = "tencent/HunyuanVideo-1.5"
OFFICIAL_MODEL_REVISION = "9b49404b3f5df2a8f0b31df27a0c7ab872e7b038"


def main() -> None:
    import diffusers
    import torch
    import transformers
    from diffusers import (
        AutoencoderKLHunyuanVideo15,
        HunyuanVideo15Pipeline,
        HunyuanVideo15Transformer3DModel,
    )
    from diffusers.models.transformers.transformer_hunyuan_video15 import (
        HunyuanVideo15AttnProcessor2_0,
    )

    if not torch.cuda.is_available() or torch.version.hip is None:
        raise RuntimeError("HunyuanVideo 1.5 preflight requires ROCm")
    properties = torch.cuda.get_device_properties(0)
    architecture = str(getattr(properties, "gcnArchName", ""))
    if architecture != "gfx1201":
        raise RuntimeError("HunyuanVideo 1.5 preflight requires the target gfx1201 GPU")
    if HunyuanVideo15AttnProcessor2_0._attention_backend is not None:
        raise RuntimeError("HunyuanVideo 1.5 default attention backend changed")
    if not hasattr(torch.nn.functional, "scaled_dot_product_attention"):
        raise RuntimeError("PyTorch SDPA is unavailable")

    print(
        json.dumps(
            {
                "candidate_repository": CANDIDATE_REPOSITORY,
                "candidate_revision": CANDIDATE_REVISION,
                "official_model_repository": OFFICIAL_MODEL_REPOSITORY,
                "official_model_revision": OFFICIAL_MODEL_REVISION,
                "torch": torch.__version__,
                "hip": torch.version.hip,
                "diffusers": diffusers.__version__,
                "transformers": transformers.__version__,
                "gpu": torch.cuda.get_device_name(0),
                "architecture": architecture,
                "pipeline": HunyuanVideo15Pipeline.__name__,
                "transformer": HunyuanVideo15Transformer3DModel.__name__,
                "vae": AutoencoderKLHunyuanVideo15.__name__,
                "attention": "pytorch_sdpa",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
