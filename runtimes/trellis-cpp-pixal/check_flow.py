#!/usr/bin/env python3
"""Compare native stage sampling with pinned Pixal3D on synthetic checkpoints.

Input fixtures are created by check_checkpoint.py. No pretrained weights or GPU
are needed. An explicitly selected Vulkan test requires caller-owned Host lease.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from convert_flow import PIXAL_REVISION, digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pixal-source", required=True, type=Path)
    parser.add_argument("--checkpoint-fixtures", required=True, type=Path)
    parser.add_argument("--binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--backend", choices=("cpu", "vulkan"), default="cpu")
    parser.add_argument("--device-index", type=int)
    args = parser.parse_args()
    if (args.backend == "vulkan") != (args.device_index is not None):
        parser.error("Vulkan requires an explicit admitted device index")
    source = args.pixal_source.resolve(strict=True)
    if subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip() != PIXAL_REVISION or \
            subprocess.check_output(["git", "-C", str(source), "diff", "HEAD", "--"]):
        parser.error("reference must have the pinned revision with no tracked changes")
    if args.output_dir.exists():
        parser.error("use a fresh output directory")
    os.environ.update({"HIP_VISIBLE_DEVICES": "-1", "ROCR_VISIBLE_DEVICES": "-1", "CUDA_VISIBLE_DEVICES": "-1",
                       "ATTN_BACKEND": "sdpa", "SPARSE_ATTN_BACKEND": "sdpa", "SPARSE_CONV_BACKEND": "none",
                       "HF_HUB_OFFLINE": "1"})
    sys.path.insert(0, str(source))
    import numpy as np
    import torch
    from safetensors.torch import load_file
    from pixal3d.models.sparse_structure_flow import SparseStructureFlowModel
    from pixal3d.models.structured_latent_flow import ElasticSLatFlowModel
    from pixal3d.modules.sparse import SparseTensor
    from pixal3d.pipelines.samplers.flow_euler import FlowEulerGuidanceIntervalSampler

    torch.set_num_threads(2)
    args.output_dir.mkdir(parents=True)
    cases = [
        ("ss_cfg", "ss_f32_f32", 4, 1., 2.7, 0., 0., 1.),
        ("ss_interval_rescale", "ss_f32_f32", 5, 2.2, 3.1, .4, .3, .8),
        ("ss_negative_only", "ss_f32_f32", 3, 1., 0., 0., 0., 1.),
        ("ss_positive_only", "ss_f32_f32", 3, 1., 1., 0., 0., 1.),
        ("shape_cfg_rescale", "shape_f32_f32", 4, 1.7, 2.7, .3, 0., 1.),
        ("shape_interval", "shape_f32_f32", 5, 2., 2.3, .4, .25, .8),
        ("texture_cfg_rescale", "texture_f32_f32", 4, 1.5, 2.7, .3, 0., 1.),
        ("texture_negative_only", "texture_f32_f32", 3, 1., 0., 0., 0., 1.),
        ("texture_f16_storage", "texture_bf16_f16", 4, 1.8, 2.7, .2, .3, .9),
        ("rescale_unclamped", "ss_f32_f32", 1, 1., 2., 1., 0., 1.),
    ]
    records = []
    command_base = [str(args.binary.resolve())]
    for case, fixture, steps, rescale_t, strength, rescale, start, end in cases:
        base = args.checkpoint_fixtures.resolve() / fixture
        directory = args.output_dir / case
        directory.mkdir()
        manifest = json.loads((base / "converted/manifest.json").read_text())
        if manifest["source"]["source_kind"] != "synthetic" or manifest["output_sha256"] != digest(base / "converted/model.gguf"):
            raise ValueError("flow check requires intact synthetic checkpoints")
        checkpoint = base / "converted/model.gguf"
        config = json.loads((base / "config.json").read_text())
        stage = manifest["stage"]
        cls = SparseStructureFlowModel if stage == "ss" else ElasticSLatFlowModel
        model = cls(**config["args"]).eval()
        weights = load_file(base / "source.safetensors")
        with torch.no_grad():
            for name, parameter in model.named_parameters():
                value = weights[name].float()
                if manifest["storage"] == "f16" and value.ndim == 2 and name.endswith(".weight"):
                    value = value.half().float()
                parameter.copy_(value)
        raw = torch.from_numpy(np.load(base / "input.npy", allow_pickle=False))
        channels = config["args"]["out_channels"]
        latent = raw[:, :channels].contiguous()
        concat = raw[:, channels:].contiguous() if stage == "texture" else None
        if stage == "ss":
            r = config["args"]["resolution"]
            coords = torch.cartesian_prod(torch.arange(r), torch.arange(r), torch.arange(r))
            noise = latent.T.reshape(1, channels, r, r, r)
        else:
            coords = torch.from_numpy(np.load(base / "coords.npy", allow_pickle=False))[:, 1:]
            sparse_coords = torch.cat([torch.zeros(len(coords), 1, dtype=coords.dtype), coords], dim=1)
            noise = SparseTensor(latent, sparse_coords)
        global_cond = torch.from_numpy(np.load(base / "global.npy", allow_pickle=False)).unsqueeze(0)
        proj = torch.from_numpy(np.load(base / "projected.npy", allow_pickle=False))
        positive = {"global": global_cond, "proj": proj.unsqueeze(0) if stage == "ss" else SparseTensor(proj, sparse_coords)}
        negative = {"global": torch.zeros_like(global_cond),
                    "proj": torch.zeros_like(proj).unsqueeze(0) if stage == "ss" else SparseTensor(torch.zeros_like(proj), sparse_coords)}
        reference_log = []
        analytic = case == "rescale_unclamped"

        def wrapped(x, t, condition, **kwargs):
            reference_log.append([t[0].item(), 1. if condition is positive else 0.])
            if analytic:
                return x * (-1. if condition is positive else -2.99)
            return model(x, t, condition, **kwargs)

        velocities = []

        class RecordingSampler(FlowEulerGuidanceIntervalSampler):
            def _get_model_prediction(self, *positional, **kwargs):
                result = super()._get_model_prediction(*positional, **kwargs)
                velocities.append(result[2])
                return result

        kwargs = {"concat_cond": SparseTensor(concat, sparse_coords)} if concat is not None else {}
        sampler = RecordingSampler(1e-5)
        result = sampler.sample(wrapped, noise, positive, negative, steps=steps, rescale_t=rescale_t,
                                guidance_strength=strength, guidance_rescale=rescale,
                                guidance_interval=(start, end), verbose=False, **kwargs)

        def flat(value):
            return value.feats.detach().numpy() if isinstance(value, SparseTensor) else value[0].reshape(channels, -1).T.contiguous().detach().numpy()

        np.save(directory / "coordinates.npy", coords.numpy().astype(np.float32))
        np.save(directory / "noise.npy", latent.numpy())
        np.save(directory / "global.npy", global_cond[0].numpy())
        np.save(directory / "projected.npy", proj.numpy())
        np.save(directory / "negative_global.npy", torch.zeros_like(global_cond[0]).numpy())
        np.save(directory / "negative_projected.npy", torch.zeros_like(proj).numpy())
        if concat is not None:
            np.save(directory / "concat.npy", concat.numpy())
        (directory / "sampler.txt").write_text(f"{steps} {rescale_t} 0.00001 {strength} {rescale} {start} {end}\n")
        expected = {}
        for i in range(steps):
            expected[f"step{i}_velocity"] = flat(velocities[i])
            expected[f"step{i}_clean"] = flat(result.pred_x_0[i])
            expected[f"step{i}_sample"] = flat(result.pred_x_t[i])
        for name, value in expected.items():
            np.save(directory / ("expected_" + name + ".npy"), value)
        np.save(directory / "expected_forward_log.npy", np.array(reference_log, dtype=np.float32))
        command = command_base + [str(directory.resolve()), str(checkpoint), args.backend]
        if args.device_index is not None: command += ["--device", str(args.device_index)]
        if analytic: command += ["--analytic"]
        native = subprocess.run(command, capture_output=True, text=True, timeout=90)
        (directory / "native.log").write_text(native.stdout+native.stderr)
        record = {"case": case, "returncode": native.returncode, "tensors": {}, "passed": False}
        if native.returncode == 0:
            for name, reference in expected.items():
                actual = np.load(directory / ("actual_" + name + ".npy"), allow_pickle=False)
                record["tensors"][name] = {"max_abs_error": float(np.max(np.abs(actual-reference))),
                                          "passed": actual.shape == reference.shape and bool(np.allclose(actual, reference, atol=5e-5, rtol=5e-5))}
            actual_log = np.load(directory / "actual_forward_log.npy", allow_pickle=False)
            expected_log = np.array(reference_log*2, dtype=np.float32)
            record["forward_sequence_equal"] = bool(np.array_equal(actual_log, expected_log))
            record["native"] = json.loads((directory / "native_result.json").read_text())
            record["passed"] = all(t["passed"] for t in record["tensors"].values()) and record["forward_sequence_equal"] and record["native"]["progress_events"] == steps+1
        records.append(record)
    negatives = {}
    for name, fixture, extra, message in [
        ("missing_projection", "ss_cfg", ["--omit-proj"], "shape or timestep mismatch"),
        ("missing_concat", "texture_cfg_rescale", ["--omit-concat"], "shape or timestep mismatch"),
        ("nan_velocity", "ss_cfg", ["--nan-velocity"], "non-finite flow velocity"),
        ("short_velocity", "ss_cfg", ["--short-output"], "velocity size mismatch"),
        ("cancel_before", "ss_cfg", ["--cancel-after", "0"], "flow cancelled"),
        ("cancel_between_cfg", "ss_cfg", ["--cancel-after", "1"], "flow cancelled"),
        ("cancel_during_last", "ss_positive_only", ["--cancel-after", "3"], "flow cancelled"),
        ("zero_variance", "rescale_unclamped", ["--analytic"], "non-finite CFG rescale ratio"),
        ("invalid_steps", "ss_cfg", [], "invalid flow sampler parameters"),
        ("invalid_coordinate", "ss_cfg", [], "invalid coordinate fixture"),
        ("short_negative_projection", "ss_cfg", [], "shape or timestep mismatch"),
    ]:
        directory = args.output_dir / "negative" / name
        shutil.copytree(args.output_dir / fixture, directory, ignore=shutil.ignore_patterns("actual_*", "native*", "expected_*"))
        if name == "zero_variance":
            np.save(directory / "noise.npy", np.zeros_like(np.load(directory / "noise.npy")))
        elif name == "invalid_steps":
            values = (directory / "sampler.txt").read_text().split()
            values[0] = "0"
            (directory / "sampler.txt").write_text(" ".join(values)+"\n")
        elif name == "invalid_coordinate":
            values = np.load(directory / "coordinates.npy")
            values[0, 0] = -1
            np.save(directory / "coordinates.npy", values)
        elif name == "short_negative_projection":
            values = np.load(directory / "negative_projected.npy")
            np.save(directory / "negative_projected.npy", values[:-1])
        base = "texture_f32_f32" if fixture.startswith("texture") else "ss_f32_f32"
        command = command_base + [str(directory), str(args.checkpoint_fixtures.resolve()/base/"converted/model.gguf"), "cpu"] + extra
        native = subprocess.run(command, capture_output=True, text=True, timeout=30)
        negatives[name] = {"returncode": native.returncode, "stderr": native.stderr.strip(),
                           "passed": native.returncode == 1 and message in native.stderr and not list(directory.glob("actual_*"))}
    report = {"passed": all(r["passed"] for r in records) and all(r["passed"] for r in negatives.values()),
              "reference_revision": PIXAL_REVISION, "binary_sha256": digest(args.binary),
              "backend": args.backend, "device_index": args.device_index, "cases": records, "negative_checks": negatives,
              "torch_gpu_initialized": torch.cuda.is_initialized(), "pretrained_weights": "NOT USED",
              "arithmetic": "F32", "full_image_to_glb": "NOT TESTED"}
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"passed": report["passed"], "cases": len(records), "negative_checks": len(negatives)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
