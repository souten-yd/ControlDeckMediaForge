"""Lay LoRA weights on a loaded pipeline.

Two things get in the way of just calling ``load_lora_weights`` with a path.

The first is that Civitai LoRAs are kohya files, which diffusers converts on
the way in. That part works.

The second is a version seam. ``transformers`` 5 flattened the CLIP text
encoder: its modules are now ``encoder.layers.0.mlp.fc1`` where they used to be
``text_model.encoder.layers.0.mlp.fc1``. diffusers 0.40 builds the LoRA rank
table by asking the encoder for its module names and looking each one up in the
converted state dict, which still carries the old ``text_model.`` prefix. Every
lookup misses, the rank table comes out empty, and loading dies on

    IndexError: list index out of range

deep inside peft_utils. Nothing in that message points at the text encoder, and
the LoRA file is fine — measured on add_detail.safetensors, which carries 216
text-encoder tensors and 576 UNet ones.

So the keys are aligned to whatever shape the loaded encoder actually has,
rather than assuming either one. Dropping the text-encoder half instead would
have loaded quietly and produced a different picture than the LoRA's author
intended.
"""

from __future__ import annotations

from typing import Any

TEXT_ENCODER_PREFIXES = ("text_encoder", "text_encoder_2")


def _module_names(component: Any) -> set[str]:
    try:
        return {name for name, _ in component.named_modules()}
    except AttributeError:
        return set()


def align_text_encoder_keys(state_dict: dict[str, Any], pipeline: Any) -> dict[str, Any]:
    """Rewrite text-encoder keys to the module names this pipeline really has.

    Only the segments the encoder does not have are removed, and only when
    removing them makes the key match. A pipeline on an older transformers
    keeps its keys untouched.
    """
    aligned: dict[str, Any] = {}
    caches: dict[str, set[str]] = {}
    for key, value in state_dict.items():
        prefix = next(
            (name for name in TEXT_ENCODER_PREFIXES if key.startswith(f"{name}.")), None
        )
        if prefix is None:
            aligned[key] = value
            continue
        if prefix not in caches:
            caches[prefix] = _module_names(getattr(pipeline, prefix, None))
        names = caches[prefix]
        remainder = key[len(prefix) + 1:]
        module = remainder.rsplit(".lora_", 1)[0].rsplit(".alpha", 1)[0]
        if not names or module in names:
            aligned[key] = value
            continue
        stripped = module.removeprefix("text_model.")
        if stripped != module and stripped in names:
            aligned[f"{prefix}.{remainder.replace(module, stripped, 1)}"] = value
            continue
        # 合わせられないものは触らない。名前を推測して書き換えると、
        # 別の層に載せることになる。
        aligned[key] = value
    return aligned


def apply(pipeline: Any, requested: list[dict[str, Any]]) -> list[str]:
    """Load the requested LoRAs and set their weights.

    The caller has already removed any previous set; this only adds.
    """
    names: list[str] = []
    weights: list[float] = []
    for index, item in enumerate(requested):
        # adapter 名は peft 内部の識別子で、記号を含むものは扱えない。
        name = f"lora{index}"
        # unet_config を渡さないと SGM 形式のブロック名（"8.1.transformer_blocks..."）
        # が変換されず、SDXL の LoRA が「該当する層が無い」で落ちる。
        # load_lora_weights は内部でこれを渡しているので、自前で state dict を
        # 作るならこちらも同じものを渡す必要がある。
        options = {}
        unet = getattr(pipeline, "unet", None)
        if unet is not None and getattr(unet, "config", None) is not None:
            options["unet_config"] = unet.config
        state_dict = pipeline.lora_state_dict(item["path"], **options)
        if isinstance(state_dict, tuple):
            state_dict = state_dict[0]
        pipeline.load_lora_weights(
            align_text_encoder_keys(state_dict, pipeline), adapter_name=name
        )
        names.append(name)
        weights.append(float(item["weight"]))
    pipeline.set_adapters(names, adapter_weights=weights)
    return names
