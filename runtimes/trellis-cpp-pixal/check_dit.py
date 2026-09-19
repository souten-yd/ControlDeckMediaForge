#!/usr/bin/env python3
"""Compare native projected DiT with pinned Pixal3D using synthetic tiny models.

No pretrained checkpoint is loaded. CPU is the default; a genuine Host lease
must surround any explicitly selected Vulkan run, owned by the caller.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

REVISION = "f7cf38429b0bd264f1995f0f8743a88b1c728b94"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pixal-source", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--baseline-binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--backend", choices=("cpu", "vulkan"), default="cpu")
    parser.add_argument("--device-index", type=int)
    args = parser.parse_args()
    if (args.backend == "vulkan") != (args.device_index is not None):
        parser.error("Vulkan requires an explicit device index")
    source = args.pixal_source.resolve(strict=True)
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(source), "diff", "HEAD", "--"])
    if revision != REVISION or dirty:
        parser.error("reference must have the pinned revision with no tracked changes")
    os.environ.update({"HIP_VISIBLE_DEVICES": "-1", "ROCR_VISIBLE_DEVICES": "-1",
                       "CUDA_VISIBLE_DEVICES": "-1", "ATTN_BACKEND": "sdpa",
                       "SPARSE_ATTN_BACKEND": "sdpa", "HF_HUB_OFFLINE": "1"})
    sys.path.insert(0, str(source))
    import numpy as np
    import torch
    from typing import Optional, Tuple
    from pixal3d.models.sparse_structure_flow import SparseStructureFlowModel, TimestepEmbedder

    # Same unmodified projection nodes used by check_projection.py, isolated
    # from the trainer's unused GPU-dependent imports.
    reference_path = source / "pixal3d/trainers/flow_matching/mixins/image_conditioned_proj.py"
    wanted = {"project_points_to_image_batch", "sample_features", "ProjGrid"}
    nodes = [node for node in ast.parse(reference_path.read_text()).body
             if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted]
    assert len(nodes) == len(wanted)
    namespace = {"torch": torch, "nn": torch.nn, "F": torch.nn.functional, "Tuple": Tuple, "Optional": Optional}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(reference_path), "exec"), namespace)

    torch.set_num_threads(2)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    cases = [("trellis_cross", 0, 2, False), ("pixal_ss", 32, 2, False),
             ("pixal_double_features", 64, 3, False), ("pixal_zero_condition", 64, 2, True),
             ("pixal_projection_to_dit", 32, 2, False)]
    for case, projected_channels, resolution, zero_condition in cases:
        torch.manual_seed(4242)
        directory = args.output_dir / case
        (directory / "weights").mkdir(parents=True, exist_ok=True)
        model = SparseStructureFlowModel(
            resolution=resolution, in_channels=8, model_channels=64, cond_channels=32,
            out_channels=8, num_blocks=2, num_heads=4, mlp_ratio=1.5, pe_mode="rope",
            dtype="float32", share_mod=True, qk_rms_norm=True, qk_rms_norm_cross=True,
            image_attn_mode="proj" if projected_channels else "cross",
            proj_in_channels=projected_channels or None,
        ).eval()
        # Upstream initializes some output/modulation layers to zero. Replace
        # every parameter so a missing projection or block cannot pass on zeros.
        with torch.no_grad():
            for name, parameter in model.named_parameters():
                if name.endswith("gamma") or name.endswith("norm2.weight"):
                    parameter.normal_(1.0, 0.03)
                elif parameter.ndim >= 2:
                    parameter.normal_(0.0, 0.5 / math.sqrt(parameter.shape[-1]))
                else:
                    parameter.normal_(0.0, 0.1)
        expected = {}

        def capture(name: str):
            def hook(_module, _inputs, output):
                expected[name] = output.detach().clone().reshape(-1, output.shape[-1]).numpy()
            return hook

        model.input_layer.register_forward_hook(capture("after_input_layer"))
        model.adaLN_modulation.register_forward_hook(capture("t_emb_mod"))
        model.blocks[0].self_attn.register_forward_hook(capture("blk0_msa"))
        model.blocks[0].mlp.register_forward_hook(capture("blk0_mlp"))
        for index, block in enumerate(model.blocks):
            block.register_forward_hook(capture(f"after_block{index}"))
        model.blocks[-1].register_forward_hook(capture("after_block29"))
        cross = model.blocks[0].cross_attn
        cross.register_forward_hook(capture("blk0_cross"))
        if projected_channels:
            cross.cross_attn_block.register_forward_hook(capture("blk0_global_cross"))
            cross.proj_linear.register_forward_hook(capture("blk0_projected"))
        else:
            cross.register_forward_hook(capture("blk0_global_cross"))

        def before_output(_module, inputs):
            value = inputs[0]
            expected["prefinal"] = value.detach().clone().reshape(-1, value.shape[-1]).numpy()

        model.out_layer.register_forward_pre_hook(before_output)
        x = torch.randn((1, 8, resolution, resolution, resolution))
        t = torch.tensor([517.0])
        global_cond = torch.randn((1, 5, 32))
        projected = torch.randn((1, resolution**3, projected_channels)) if projected_channels else None
        from_features = case == "pixal_projection_to_dit"
        if from_features:
            features = torch.randn((1, 5, 7, 32))
            projected = namespace["ProjGrid"](2, 512)(
                features, torch.tensor([0.857556]), torch.tensor([2.0]), torch.tensor([1.0]),
            )
            np.save(directory / "features.npy", features[0].numpy())
            np.save(directory / "camera.npy", np.array([0.857556, 2.0, 1.0, 512, 2], dtype=np.float32))
        if zero_condition:
            global_cond.zero_()
            projected.zero_()
        condition = {"global": global_cond, "proj": projected} if projected_channels else global_cond
        with torch.no_grad():
            output = model(x, t, condition)
        expected["output"] = output[0].reshape(8, -1).T.contiguous().numpy()
        assert np.max(np.abs(expected["output"])) > 0.01
        weights = dict(model.named_parameters())
        (directory / "weights.txt").write_text("\n".join(weights) + "\n")
        for name, tensor in weights.items():
            np.save(directory / "weights" / (name + ".npy"), tensor.detach().contiguous().numpy())
        (directory / "params.txt").write_text(f"2 4 16 64 96 32 {projected_channels} 8 8\n")
        np.save(directory / "input.npy", x[0].reshape(8, -1).T.contiguous().numpy())
        np.save(directory / "timestep.npy", TimestepEmbedder.timestep_embedding(t, 256)[0].numpy())
        np.save(directory / "global.npy", global_cond[0].numpy())
        np.save(directory / "cosine.npy", model.rope_phases.real.reshape(resolution**3, 1, 8, 1).numpy())
        np.save(directory / "sine.npy", model.rope_phases.imag.reshape(resolution**3, 1, 8, 1).numpy())
        if projected is not None:
            np.save(directory / "projected.npy", projected[0].numpy())
        for name, tensor in expected.items():
            np.save(directory / ("expected_" + name + ".npy"), tensor)
        command = [str(args.binary.resolve()), str(directory.resolve()), args.backend]
        if args.device_index is not None:
            command += ["--device", str(args.device_index)]
        if from_features:
            command.append("--from-features")
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (directory / "native.log").write_text(result.stdout + result.stderr)
        record = {"case": case, "returncode": result.returncode, "tensors": {}, "passed": False}
        if result.returncode == 0:
            for name, reference in expected.items():
                actual = np.load(directory / ("actual_" + name + ".npy"), allow_pickle=False)
                shape_ok = actual.shape == reference.shape
                record["tensors"][name] = {
                    "max_abs_error": float(np.max(np.abs(actual-reference))) if shape_ok else None,
                    "passed": shape_ok and bool(np.allclose(actual, reference, atol=5e-5, rtol=5e-5)),
                }
            record["passed"] = all(value["passed"] for value in record["tensors"].values())
        reports.append(record)
    negatives = {}
    for flag, expected_error in [("--omit-proj", "mode/input mismatch"), ("--short-proj", "shape/type mismatch")]:
        result = subprocess.run([str(args.binary.resolve()), str((args.output_dir / "pixal_ss").resolve()), "cpu", flag],
                                capture_output=True, text=True, timeout=10)
        negatives[flag] = result.returncode != 0 and expected_error in result.stderr
    # Compare default/legacy behavior directly with an executable compiled from
    # unmodified trellis.cpp, avoiding tolerance changes for its FP16 GELU table.
    legacy_outputs = {}
    for name, binary in [("patched", args.binary), ("upstream", args.baseline_binary)]:
        directory = args.output_dir / ("legacy_" + name)
        directory.mkdir(exist_ok=True)
        fixture = args.output_dir / "trellis_cross"
        shutil.copytree(fixture / "weights", directory / "weights", dirs_exist_ok=True)
        for filename in ("params.txt", "weights.txt", "input.npy", "timestep.npy", "global.npy", "cosine.npy", "sine.npy"):
            shutil.copyfile(fixture / filename, directory / filename)
        result = subprocess.run([str(binary.resolve()), str(directory.resolve()), "cpu", "--legacy-gelu"],
                                capture_output=True, text=True, timeout=60)
        (directory / "native.log").write_text(result.stdout + result.stderr)
        if result.returncode != 0:
            legacy_outputs[name] = {}
        else:
            legacy_outputs[name] = {
                path.name: np.load(path, allow_pickle=False)
                for path in directory.glob("actual_*.npy")
            }
    legacy_equal = bool(legacy_outputs["upstream"]) and all(
        name in legacy_outputs["patched"] and np.array_equal(tensor, legacy_outputs["patched"][name])
        for name, tensor in legacy_outputs["upstream"].items()
    )
    report = {
        "scope": "synthetic_tiny_dit_full_graph_and_intermediates",
        "reference_revision": revision, "binary_sha256": hashlib.sha256(args.binary.read_bytes()).hexdigest(),
        "backend": args.backend, "device_index": args.device_index, "attention_mode": "exact_f32",
        "gelu_mode": "exact_f32_tanh", "legacy_cpu_bitwise_equal": legacy_equal,
        "baseline_binary_sha256": hashlib.sha256(args.baseline_binary.read_bytes()).hexdigest(),
        "cases": reports, "negative_checks": negatives, "torch_gpu_initialized": torch.cuda.is_initialized(),
        "pretrained_weights": "NOT USED", "full_model_generation": "NOT TESTED",
    }
    report["passed"] = all(item["passed"] for item in reports) and all(negatives.values()) and legacy_equal and not report["torch_gpu_initialized"]
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
