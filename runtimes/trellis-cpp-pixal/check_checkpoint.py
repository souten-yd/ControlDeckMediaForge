#!/usr/bin/env python3
"""CPU safetensors -> GGUF -> native Model/DiT round-trip with synthetic weights."""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys

from convert_flow import PIXAL_REVISION, convert, digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pixal-source", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    source = args.pixal_source.resolve(strict=True)
    if subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip() != PIXAL_REVISION or \
            subprocess.check_output(["git", "-C", str(source), "diff", "HEAD", "--"]):
        parser.error("reference source must be pinned with no tracked changes")
    if args.output_dir.exists():
        parser.error("use a fresh output directory")
    os.environ.update({"HIP_VISIBLE_DEVICES": "-1", "ROCR_VISIBLE_DEVICES": "-1",
                       "CUDA_VISIBLE_DEVICES": "-1", "ATTN_BACKEND": "sdpa",
                       "SPARSE_ATTN_BACKEND": "sdpa", "SPARSE_CONV_BACKEND": "none", "HF_HUB_OFFLINE": "1"})
    sys.path.insert(0, str(source))
    import gguf
    import numpy as np
    import torch
    from safetensors.torch import save_file
    from pixal3d.models.sparse_structure_flow import SparseStructureFlowModel, TimestepEmbedder
    from pixal3d.models.structured_latent_flow import ElasticSLatFlowModel
    from pixal3d.modules.sparse import SparseTensor
    from pixal3d.modules.attention import RotaryPositionEmbedder

    torch.set_num_threads(2)
    args.output_dir.mkdir(parents=True)
    reports = []
    conversion_args = {"source_repository": "mediaforge/synthetic-flow-check", "source_revision": PIXAL_REVISION,
                       "source_kind": "synthetic"}
    # The sparse cases use non-grid token order and a repeated coordinate.
    # Texture has doubled input channels: the flow receives noisy texture + shape.
    for stage, source_dtype, storage in [("ss", "f32", "f32"), ("shape", "f32", "f32"),
                                         ("texture", "f32", "f32"), ("ss", "bf16", "f16"),
                                         ("shape", "f16", "f16"), ("texture", "bf16", "f16")]:
        case = f"{stage}_{source_dtype}_{storage}"
        directory = args.output_dir / case
        directory.mkdir()
        torch.manual_seed(7342)
        model_args = {"resolution": 2 if stage == "ss" else 4,
                      "in_channels": 16 if stage == "texture" else 8, "out_channels": 8,
                      "model_channels": 64, "cond_channels": 32, "num_blocks": 2,
                      "num_heads": 4, "mlp_ratio": 1.5, "pe_mode": "rope", "share_mod": True,
                      "qk_rms_norm": True, "qk_rms_norm_cross": True, "image_attn_mode": "proj",
                      "proj_in_channels": 32 if stage == "ss" else 64}
        cls = SparseStructureFlowModel if stage == "ss" else ElasticSLatFlowModel
        config = {"name": cls.__name__, "args": model_args}
        config_path = directory / "config.json"
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        model = cls(**model_args).eval()
        with torch.no_grad():
            for name, parameter in model.named_parameters():
                if name.endswith("gamma") or name.endswith("norm2.weight"):
                    parameter.normal_(1.0, 0.03)
                elif parameter.ndim >= 2:
                    parameter.normal_(0.0, 0.5/math.sqrt(parameter.shape[-1]))
                else:
                    parameter.normal_(0.0, 0.1)
        dtype = {"f32": torch.float32, "f16": torch.float16, "bf16": torch.bfloat16}[source_dtype]
        state = {name: parameter.detach().to(dtype).contiguous() for name, parameter in model.named_parameters()}
        checkpoint = directory / "source.safetensors"
        save_file(state, checkpoint, metadata={"source": "synthetic; no pretrained weights"})
        converted = directory / "converted"
        manifest = convert(checkpoint, config_path, converted, stage=stage, storage=storage, **conversion_args)
        # Independent reader verifies every serialized value/dimension. Reference
        # calculation uses the same rounded weights but F32 arithmetic, so the
        # numerical threshold does not hide a storage conversion error.
        values_match = True
        with torch.no_grad():
            rounded = {}
            for name, value in state.items():
                v = value.float()
                if storage == "f16" and name.endswith(".weight") and v.ndim == 2:
                    v = v.half().float()
                rounded[name] = v
            for name, parameter in model.named_parameters():
                parameter.copy_(rounded[name])
        reader = gguf.GGUFReader(converted / "model.gguf")
        for tensor in reader.tensors:
            expected = rounded[tensor.name].numpy()
            actual = tensor.data.reshape(expected.shape).astype(np.float32)
            values_match &= bool(np.array_equal(actual, expected))
        expected = {}

        def capture(name: str):
            def hook(_module, _inputs, value):
                if isinstance(value, SparseTensor):
                    value = value.feats
                expected[name] = value.detach().reshape(-1, value.shape[-1]).numpy().copy()
            return hook

        model.input_layer.register_forward_hook(capture("after_input_layer"))
        model.adaLN_modulation.register_forward_hook(capture("t_emb_mod"))
        model.blocks[0].self_attn.register_forward_hook(capture("blk0_msa"))
        model.blocks[0].mlp.register_forward_hook(capture("blk0_mlp"))
        model.blocks[0].cross_attn.register_forward_hook(capture("blk0_cross"))
        model.blocks[0].cross_attn.cross_attn_block.register_forward_hook(capture("blk0_global_cross"))
        model.blocks[0].cross_attn.proj_linear.register_forward_hook(capture("blk0_projected"))
        for i, block in enumerate(model.blocks):
            block.register_forward_hook(capture(f"after_block{i}"))
        model.blocks[-1].register_forward_hook(capture("after_block29"))

        def before_output(_module, inputs):
            value = inputs[0].feats if isinstance(inputs[0], SparseTensor) else inputs[0]
            expected["prefinal"] = value.detach().reshape(-1, value.shape[-1]).numpy().copy()

        model.out_layer.register_forward_pre_hook(before_output)
        if stage == "ss":
            x = torch.randn(1, 8, 2, 2, 2)
            native_x = x[0].reshape(8, -1).T.contiguous()
            phases = model.rope_phases
            count = 8
        else:
            coords = torch.tensor([[0,3,1,0], [0,0,0,2], [0,2,3,1], [0,3,1,0],
                                   [0,1,1,2], [0,0,3,0], [0,2,2,2]], dtype=torch.int32)
            count = len(coords)
            native_x = torch.randn(count, model_args["in_channels"])
            x = SparseTensor(native_x, coords)
            phases = RotaryPositionEmbedder(16, 3)(coords[:, 1:])
            np.save(directory / "coords.npy", coords.numpy())
        t = torch.tensor([517.0])
        global_cond = torch.randn(1, 5, 32)
        projected = torch.randn(count, model_args["proj_in_channels"])
        condition = {"global": global_cond, "proj": projected.unsqueeze(0) if stage == "ss" else projected}
        with torch.no_grad():
            output = model(x, t, condition)
        expected["output"] = output[0].reshape(8, -1).T.contiguous().numpy() if stage == "ss" else output.feats.numpy()
        np.save(directory / "input.npy", native_x.numpy())
        np.save(directory / "timestep.npy", TimestepEmbedder.timestep_embedding(t, 256)[0].numpy())
        np.save(directory / "global.npy", global_cond[0].numpy())
        np.save(directory / "projected.npy", projected.numpy())
        np.save(directory / "cosine.npy", phases.real.reshape(count, 1, 8, 1).numpy())
        np.save(directory / "sine.npy", phases.imag.reshape(count, 1, 8, 1).numpy())
        for name, value in expected.items():
            np.save(directory / ("expected_" + name + ".npy"), value)
        # There is no params.txt: native dimensions must come from the GGUF.
        command = [str(args.binary.resolve()), str(directory.resolve()), "cpu", "--gguf", str(converted / "model.gguf")]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (directory / "native.log").write_text(result.stdout + result.stderr)
        record = {"case": case, "returncode": result.returncode, "serialized_values_equal": values_match,
                  "output_sha256": manifest["output_sha256"], "tensors": {}, "passed": False}
        if result.returncode == 0:
            for name, reference in expected.items():
                actual = np.load(directory / ("actual_" + name + ".npy"), allow_pickle=False)
                shape_ok = actual.shape == reference.shape
                record["tensors"][name] = {"max_abs_error": float(np.max(np.abs(actual-reference))) if shape_ok else None,
                                          "passed": shape_ok and bool(np.allclose(actual, reference, atol=5e-5, rtol=5e-5))}
            record["passed"] = values_match and all(v["passed"] for v in record["tensors"].values())
        reports.append(record)

    # Failures must leave no published output; do not accept unknown weights,
    # a silent projection downgrade, non-finite input or lossy F16 overflow.
    negative_dir = args.output_dir / "negative"
    negative_dir.mkdir()
    negatives = {}
    base_config = json.loads((args.output_dir / "ss_f32_f32/config.json").read_text())
    from safetensors.torch import load_file
    base_state = load_file(args.output_dir / "ss_f32_f32/source.safetensors")
    for case in ("missing_projection", "wrong_shape", "extra_weight", "gated_mode", "wrong_stage",
                 "nan", "f16_overflow", "invalid_heads", "unknown_argument", "truncated", "duplicate_json"):
        state = {k: v.clone() for k, v in base_state.items()}
        config = copy.deepcopy(base_config)
        tensor_name = "blocks.0.cross_attn.proj_linear.weight"
        if case == "missing_projection": del state[tensor_name]
        elif case == "wrong_shape": state[tensor_name] = state[tensor_name][:, :-1].contiguous()
        elif case == "extra_weight": state["unexpected"] = torch.ones(1)
        elif case == "gated_mode": config["args"]["image_attn_mode"] = "gated_proj"
        elif case == "nan": state[tensor_name][0, 0] = float("nan")
        elif case == "f16_overflow": state[tensor_name][0, 0] = 1e10
        elif case == "invalid_heads": config["args"]["num_heads"] = 3
        elif case == "unknown_argument": config["args"]["unimplemented"] = True
        path = negative_dir / (case + ".safetensors")
        save_file(state, path)
        if case == "truncated": path.write_bytes(path.read_bytes()[:-10])
        config_path = negative_dir / (case + ".json")
        config_path.write_text(json.dumps(config) if case != "duplicate_json" else '{"args":{},"args":{}}')
        output_dir = negative_dir / case
        error = None
        try:
            convert(path, config_path, output_dir, stage="texture" if case == "wrong_stage" else "ss",
                    storage="f16", **conversion_args)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        negatives[case] = {"passed": error is not None and not output_dir.exists(), "error": error}
    baseline = args.output_dir / "ss_f32_f32"
    before_hash = digest(baseline / "converted/model.gguf")
    try:
        convert(baseline / "source.safetensors", baseline / "config.json", baseline / "converted",
                stage="ss", storage="f32", **conversion_args)
        overwrite_rejected = False
    except ValueError as exc:
        overwrite_rejected = "already exists" in str(exc)
    negatives["existing_output"] = {"passed": overwrite_rejected and digest(baseline / "converted/model.gguf") == before_hash}
    repeat = convert(baseline / "source.safetensors", baseline / "config.json", baseline / "repeated",
                     stage="ss", storage="f32", **conversion_args)
    deterministic = repeat["output_sha256"] == before_hash
    # Forge semantically invalid but structurally readable GGUFs independently
    # of the converter. Native inspection must reject before Model allocates CPU
    # weights (and hence before any production backend could be initialized).
    original = gguf.GGUFReader(baseline / "converted/model.gguf")
    native_negatives = {}
    mutations = {"schema": ("pixal.schema_version", 99), "architecture": ("general.architecture", "trellis"),
                 "stage": ("pixal.stage", "texture"), "channels": ("pixal.flow.proj_in_channels", 31),
                 "missing_metadata": ("pixal.flow.d_model", None), "source_hash": ("pixal.checkpoint_sha256", "invalid"),
                 "tensor_name": (None, None), "tensor_type": (None, None), "tensor_shape": (None, None)}
    for case, (changed_key, changed_value) in mutations.items():
        path = negative_dir / ("native_" + case + ".gguf")
        writer = gguf.GGUFWriter(path, "trellis" if case == "architecture" else "pixal3d-flow")
        for key, field in original.fields.items():
            if key.startswith("GGUF.") or key == "general.architecture" or (key == changed_key and changed_value is None):
                continue
            value = changed_value if key == changed_key else field.contents()
            writer.add_key_value(key, value, field.types[0])
        for i, tensor in enumerate(original.tensors):
            name = "unexpected" if case == "tensor_name" and i == 0 else tensor.name
            value = np.asarray(tensor.data)
            if case == "tensor_type" and i == 0: value = value.astype(np.float16)
            if case == "tensor_shape" and i == 0: value = value.reshape(-1)[:-1].copy()
            writer.add_tensor(name, value)
        writer.write_header_to_file()
        writer.write_kv_data_to_file()
        writer.write_tensors_to_file()
        writer.close()
        result = subprocess.run([str(args.binary.resolve()), str(baseline), "cpu", "--gguf", str(path)],
                                capture_output=True, text=True, timeout=10)
        native_negatives[case] = {"passed": result.returncode == 1 and "[trellis] CPU backend" not in result.stderr,
                                  "returncode": result.returncode, "stderr": result.stderr.strip()}
    report = {"passed": all(r["passed"] for r in reports) and all(r["passed"] for r in negatives.values()),
              "reference_revision": PIXAL_REVISION, "binary_sha256": digest(args.binary),
              "backend": "cpu", "arithmetic": "F32 including converted F16 weights", "cases": reports,
              "negative_checks": negatives, "native_negative_checks": native_negatives,
              "deterministic_gguf_bytes": deterministic, "torch_gpu_initialized": torch.cuda.is_initialized(),
              "pretrained_weights": "NOT USED", "vulkan_and_full_generation": "NOT TESTED"}
    report["passed"] &= deterministic and all(r["passed"] for r in native_negatives.values())
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "cases": len(reports), "negative_checks": len(negatives)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
