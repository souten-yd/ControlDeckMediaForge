#!/usr/bin/env python3
"""Compare native projection with unmodified pinned Pixal3D's CPU ProjGrid.

Only synthetic feature tensors are used. Vulkan execution belongs inside an
existing genuine Host lease; this script does not acquire or claim one.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PIXAL_REVISION = "f7cf38429b0bd264f1995f0f8743a88b1c728b94"
PROJECTION_SOURCE = "pixal3d/trainers/flow_matching/mixins/image_conditioned_proj.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pixal-source", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--backend", choices=("cpu", "vulkan"), default="cpu")
    parser.add_argument("--device-index", type=int)
    args = parser.parse_args()
    if (args.backend == "vulkan") != (args.device_index is not None):
        parser.error("Vulkan requires an explicit device index; CPU does not accept one")
    revision = subprocess.check_output(
        ["git", "-C", str(args.pixal_source), "rev-parse", "HEAD"], text=True,
    ).strip()
    original = subprocess.check_output(
        ["git", "-C", str(args.pixal_source), "show", f"{PIXAL_REVISION}:{PROJECTION_SOURCE}"],
    )
    path = args.pixal_source / PROJECTION_SOURCE
    if revision != PIXAL_REVISION or path.read_bytes() != original:
        parser.error("reference must be the unmodified pinned Pixal3D source")
    # CPU oracle only: don't initialize HIP while evaluating the native Vulkan
    # implementation. The native child selects Vulkan directly through GGML.
    os.environ.update({"HIP_VISIBLE_DEVICES": "-1", "ROCR_VISIBLE_DEVICES": "-1",
                       "CUDA_VISIBLE_DEVICES": "-1", "HF_HUB_OFFLINE": "1"})
    import numpy as np
    import torch
    import torch.nn as nn
    import torch.nn.functional as functional
    from typing import Optional, Tuple

    # Execute only these self-contained, unmodified upstream nodes. Importing
    # its whole trainer module otherwise pulls in unrelated GPU dependencies.
    wanted = {"project_points_to_image_batch", "sample_features", "ProjGrid"}
    tree = ast.parse(original)
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted]
    assert len(nodes) == len(wanted)
    namespace = {"torch": torch, "nn": nn, "F": functional, "Tuple": Tuple, "Optional": Optional}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    torch.set_num_threads(2)
    torch.manual_seed(42)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cases = [
        ("dense", 4, 7, 5, 16, 0.857556, 2.0, 1.0, 512, False),
        ("non_power_grid", 7, 9, 11, 7, 1.2, 2.3, 0.9, 518, False),
        ("single_pixel", 4, 1, 1, 3, 1.0, 2.0, 1.0, 512, False),
        ("border_and_behind_camera", 4, 5, 3, 7, 0.2, 0.1, 0.6, 512, False),
        ("sparse_reordered_repeated", 32, 32, 32, 16, 0.857556, 2.0, 1.0, 512, True),
        ("texture_high_resolution", 16, 64, 64, 7, 0.9, 1.4, 1.1, 1024, True),
    ]
    reports = []
    for name, resolution, height, width, channels, angle, distance, scale, image_res, sparse in cases:
        directory = args.output_dir / name
        directory.mkdir(exist_ok=True)
        features = torch.randn((1, height, width, channels), device="cpu")
        grid = namespace["ProjGrid"](resolution, image_res)
        expected_dense = grid(features, torch.tensor([angle]), torch.tensor([distance]), torch.tensor([scale]))
        coords = torch.stack(torch.meshgrid(*[torch.arange(resolution)]*3, indexing="ij"), dim=-1).reshape(-1, 3)
        if sparse:
            indices = torch.randint(0, len(coords), (257,))
            indices[-1] = indices[0]
            coords = coords[indices]
        else:
            indices = torch.arange(len(coords))
        expected = expected_dense[0, indices].numpy()
        np.save(directory / "features.npy", features[0].numpy())
        np.save(directory / "coords.npy", coords.numpy().astype(np.float32))
        np.save(directory / "camera.npy", np.array([angle, distance, scale, image_res, resolution], dtype=np.float32))
        np.save(directory / "expected.npy", expected)
        command = [str(args.binary.resolve()), str(directory.resolve()), args.backend]
        if args.device_index is not None:
            command.append(str(args.device_index))
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (directory / "native.log").write_text(result.stdout + result.stderr)
        record = {"case": name, "returncode": result.returncode, "passed": False}
        if result.returncode == 0:
            actual = np.load(directory / "actual.npy", allow_pickle=False)
            record.update({
                "max_abs_error": float(np.max(np.abs(actual - expected))),
                "passed": actual.shape == expected.shape and bool(np.allclose(actual, expected, atol=3e-5, rtol=2e-5)),
                "shape": list(actual.shape),
            })
        reports.append(record)
    # Verify native parameter rejection too; no backend is initialized before
    # the invalid plan is rejected.
    bad_dir = args.output_dir / "invalid_scale"
    bad_dir.mkdir(exist_ok=True)
    for filename in ("features.npy", "coords.npy"):
        (bad_dir / filename).write_bytes((args.output_dir / "dense" / filename).read_bytes())
    bad = np.array([0.8, 2, 0, 512, 4], dtype=np.float32)
    np.save(bad_dir / "camera.npy", bad)
    rejected = subprocess.run([str(args.binary.resolve()), str(bad_dir.resolve()), "cpu"], capture_output=True, text=True, timeout=10)
    report = {
        "reference_revision": revision, "reference_sha256": hashlib.sha256(original).hexdigest(),
        "binary_sha256": hashlib.sha256(args.binary.read_bytes()).hexdigest(),
        "backend": args.backend, "device_index": args.device_index,
        "torch_gpu_initialized": torch.cuda.is_initialized(), "cases": reports,
        "invalid_scale_rejected": rejected.returncode != 0 and "projection parameters" in rejected.stderr,
        "full_model_generation": "NOT TESTED",
    }
    report["passed"] = all(r["passed"] for r in reports) and report["invalid_scale_rejected"] and not report["torch_gpu_initialized"]
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
