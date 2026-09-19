#!/usr/bin/env python3
"""Real Pixal SS decoder class vs native GGUF decoding, synthetic parameters only."""
from __future__ import annotations

import argparse
import ast
import importlib.metadata
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace
from typing import List, Optional, Tuple, Union

from convert_ss_decoder import ARCHITECTURE, PIXAL_REVISION, convert, decoder_spec, digest, tensor_shapes
from convert_vision import NAF_REVISION


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pixal-source", "naf-source", "checkpoint-fixtures", "vision-fixtures", "stages-fixtures", "binary", "output-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--backend", choices=("cpu", "vulkan"), default="cpu")
    parser.add_argument("--device-index", type=int)
    args = parser.parse_args()
    if (args.backend == "vulkan") != (args.device_index is not None): parser.error("Vulkan requires an admitted explicit device")
    for source, pin in ((args.pixal_source, PIXAL_REVISION), (args.naf_source, NAF_REVISION)):
        if subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip() != pin or subprocess.check_output(["git", "-C", str(source), "diff", "HEAD", "--"]):
            parser.error("reference sources must be pinned with no tracked changes")
    if args.output_dir.exists(): parser.error("use a fresh output directory")
    os.environ.update({"HIP_VISIBLE_DEVICES": "-1", "ROCR_VISIBLE_DEVICES": "-1", "CUDA_VISIBLE_DEVICES": "-1", "HF_HUB_OFFLINE": "1",
                       "ATTN_BACKEND": "sdpa", "SPARSE_ATTN_BACKEND": "sdpa", "SPARSE_CONV_BACKEND": "none"})
    sys.path[:0] = [str(args.pixal_source.resolve()), str(args.naf_source.resolve())]
    import gguf
    import numpy as np
    import torch
    import torch.nn.functional as F
    from PIL import Image
    from safetensors.torch import load_file, save_file
    from torchvision import transforms
    from transformers import DINOv3ViTConfig, DINOv3ViTModel
    from natten import na2d
    from src.model.naf import NAF
    from src.layers import attentions
    from pixal3d.models.sparse_structure_vae import SparseStructureDecoder
    from pixal3d.models.sparse_structure_flow import SparseStructureFlowModel
    from pixal3d.models.structured_latent_flow import ElasticSLatFlowModel
    from pixal3d.modules.sparse import SparseTensor
    from pixal3d.pipelines.samplers.flow_euler import FlowEulerGuidanceIntervalSampler
    if importlib.metadata.version("transformers") != "4.57.3" or importlib.metadata.version("natten") != "0.21.0": raise ValueError("pinned reference packages required")
    torch.set_num_threads(2)
    def cpu_attention(q, k, v, **kwargs):
        assert kwargs.pop("backend") == "cutlass-fna"
        width = q.shape[-1]; chunks = []
        for start in range(0, v.shape[-1], width):
            part = v[..., start:start + width]
            chunks.append(na2d(q, k, F.pad(part, (0, width - part.shape[-1])), **kwargs, backend="flex-fna", torch_compile=False)[..., :part.shape[-1]])
        return torch.cat(chunks, dim=-1)
    attentions.na2d = cpu_attention
    projection_source = args.pixal_source / "pixal3d/trainers/flow_matching/mixins/image_conditioned_proj.py"
    pipeline_source = args.pixal_source / "pixal3d/pipelines/pixal3d_image_to_3d.py"
    namespace = {"torch": torch, "nn": torch.nn, "F": F, "np": np, "Image": Image, "transforms": transforms,
                 "Tuple": Tuple, "Optional": Optional, "Union": Union, "List": List, "DINOv3ViTModel": DINOv3ViTModel, "SparseTensor": SparseTensor}
    names = {"project_points_to_image_batch", "sample_features", "ProjGrid", "DinoV3ProjFeatureExtractor"}
    nodes = [n for n in ast.parse(projection_source.read_text()).body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(projection_source), "exec"), namespace)
    cls = next(n for n in ast.parse(pipeline_source.read_text()).body if isinstance(n, ast.ClassDef))
    names = {"get_proj_cond_ss", "get_proj_cond_shape", "sample_sparse_structure", "sample_shape_slat"}
    nodes = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(pipeline_source), "exec"), namespace)
    args.output_dir.mkdir(parents=True)
    provenance = {"source_repository": "mediaforge/synthetic-ss-decoder", "source_revision": PIXAL_REVISION, "source_kind": "synthetic"}
    records = []

    def run(directory: Path, path: Path, extra: list[str] | None = None) -> subprocess.CompletedProcess[str]:
        cmd = [str(args.binary.resolve()), str(directory.resolve()), args.backend, str(path.resolve())]
        if args.device_index is not None: cmd += ["--device", str(args.device_index)]
        cmd += extra or []
        started = time.monotonic(); result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        (directory / "native.log").write_text(result.stdout + result.stderr)
        (directory / "command.json").write_text(json.dumps({"argv": cmd, "seconds": time.monotonic() - started, "returncode": result.returncode}, indent=2) + "\n")
        return result

    def compare(directory: Path, expected: dict, result: subprocess.CompletedProcess[str], checkpoint: Path) -> dict:
        record = {"case": directory.name, "returncode": result.returncode, "tensors": {}, "loaded_weights_exact": False, "passed": False}
        for name, value in expected.items(): np.save(directory / ("expected_" + name + ".npy"), np.asarray(value).reshape(-1))
        if result.returncode == 0:
            for name, value in expected.items():
                value = np.asarray(value).reshape(-1); actual = np.load(directory / ("actual_" + name + ".npy"), allow_pickle=False)
                # Near-flat four-channel activations amplify prior convolution
                # roundoff at final LayerNorm. Keep the final logits/coordinate
                # gates unchanged and additionally check that norm in isolation.
                atol = 1e-4 if name == "out_layer.0" else 5e-5
                equal = actual.shape == value.shape and (np.array_equal(actual, value) if name in {"coords", "progress"} else np.allclose(actual, value, atol=atol, rtol=5e-5))
                record["tensors"][name] = {"passed": bool(equal), "atol": atol, "rtol": 5e-5, "max_abs_error": float(np.max(np.abs(actual - value), initial=0)) if actual.shape == value.shape else None}
            reader = gguf.GGUFReader(checkpoint)
            record["loaded_weights_exact"] = all(np.array_equal(np.load(directory / ("actual_weight." + t.name + ".npy")), t.data.astype(np.float32).reshape(-1)) for t in reader.tensors)
            record["loaded_tensors"] = len(reader.tensors)
            record["passed"] = record["loaded_weights_exact"] and all(t["passed"] for t in record["tensors"].values())
        return record

    def reference_hook(expected: dict, name: str):
        def hook(_module, _inputs, value): expected[name] = value.detach().float().numpy().copy()
        return hook

    def load_existing(part: Path, model):
        manifest = json.loads((part / "converted/manifest.json").read_text())
        if manifest["source"]["source_kind"] != "synthetic" or any(digest(part / file) != expected for file, expected in (
            ("converted/model.gguf", manifest["output_sha256"]), ("source.safetensors", manifest["source"]["checkpoint_sha256"]), ("config.json", manifest["source"]["config_sha256"]))):
            raise ValueError("use intact synthetic dependency checkpoints")
        state = load_file(part / "source.safetensors")
        if isinstance(model, SparseStructureFlowModel): state["rope_phases"] = model.state_dict()["rope_phases"]
        model.load_state_dict(state, strict=True)
        return model.eval(), part / "converted/model.gguf"

    cases = [("three_stages", 2, [16, 8, 4], 2, 2, "layer", False, "f32", torch.float32),
             ("latent8", 8, [8, 4, 4], 1, 1, "layer", False, "f32", torch.float32),
             ("latent16", 16, [8, 4, 4], 0, 0, "layer", False, "f32", torch.float32),
             ("single_stage", 3, [16], 0, 0, "layer", False, "f32", torch.float32),
             ("group_output", 3, [16, 32], 1, 1, "group", False, "f32", torch.float32),
             ("bf16_f16_storage", 2, [16, 8, 4], 2, 2, "layer", False, "f16", torch.bfloat16),
             ("fp16_config_explicit_f32", 2, [16, 8, 4], 2, 2, "layer", True, "f16", torch.float16),
             ("connected_image", 2, [16, 8, 4], 2, 2, "layer", False, "f32", torch.float32)]
    for name, resolution, channels, blocks, middle, norm, fp16, storage, dtype in cases:
        torch.manual_seed(38215)
        directory = args.output_dir / name; directory.mkdir()
        config = {"name": "SparseStructureDecoder", "args": {"out_channels": 1, "latent_channels": 8, "num_res_blocks": blocks,
                  "channels": channels, "num_res_blocks_middle": middle, "norm_type": norm, "use_fp16": fp16}}
        model = SparseStructureDecoder(**config["args"]).eval()
        with torch.no_grad():
            for key, param in model.named_parameters():
                if "norm" in key or key.startswith("out_layer.0"):
                    param.normal_(1. if key.endswith("weight") else 0., .05)
                elif param.ndim >= 2: param.normal_(0., .4 / math.sqrt(param[0].numel()))
                else: param.normal_(0., .04)
        state = {k: v.detach().to(dtype).contiguous() for k, v in model.state_dict().items()}
        checkpoint = directory / "source.safetensors"; config_path = directory / "config.json"
        save_file(state, checkpoint, metadata={"source": "synthetic, no pretrained weights"}); config_path.write_text(json.dumps(config, indent=2) + "\n")
        manifest = convert(checkpoint, config_path, directory / "converted", storage=storage, **provenance)
        # Explicit F32 evaluation of original reference parameters with only the
        # declared checkpoint rounding. This is not mixed-activation parity.
        model.convert_to_fp32(); model.float()
        rounded = {k: v.float().half().float() if storage == "f16" and v.ndim == 5 else v.float() for k, v in state.items()}
        model.load_state_dict(rounded, strict=True)
        expected = {}
        for key, module in model.named_modules():
            if key == "input_layer" or (key.startswith("middle_block.") and key.count(".") == 1) or (key.startswith("blocks.") and (key.count(".") == 1 or key.endswith(".conv"))) or key in {"out_layer.0", "out_layer.1", "out_layer.2"}:
                module.register_forward_hook(reference_hook(expected, key))
        latent = torch.randn(1, 8, resolution, resolution, resolution)
        output_resolution = resolution * (2 ** (len(channels) - 1))
        if output_resolution % 2 == 0: output_resolution = max(2, output_resolution // 2)
        extra = []
        if name == "connected_image":
            vision = args.vision_fixtures / "f32_full"
            cfg = DINOv3ViTConfig.from_dict(json.loads((vision / "dino/config.json").read_text())); cfg._attn_implementation = "sdpa"
            dino, dp = load_existing(vision / "dino", DINOv3ViTModel(cfg))
            naf, npth = load_existing(vision / "naf", NAF(**json.loads((vision / "naf/config.json").read_text())["args"]))
            flows = {}; paths = {}
            for stage, cls_model in (("ss", SparseStructureFlowModel), ("shape", ElasticSLatFlowModel)):
                part = args.checkpoint_fixtures / (stage + "_f32_f32")
                flows[stage], paths[stage] = load_existing(part, cls_model(**json.loads((part / "config.json").read_text())["args"]))
            extractor = namespace["DinoV3ProjFeatureExtractor"].__new__(namespace["DinoV3ProjFeatureExtractor"])
            torch.nn.Module.__init__(extractor); extractor.model = dino; extractor.image_size = 12; extractor.patch_number = 3
            extractor.transform = transforms.Normalize([.485, .456, .406], [.229, .224, .225])
            extractor.grid_resolution = 2; extractor.proj_grid = namespace["ProjGrid"](2, 12)
            extractor.use_naf_upsample = False; extractor.naf_model = naf; extractor.naf_target_size = (8, 8)
            rgb = torch.from_numpy(np.load(args.stages_fixtures / "integrated/rgba_1024/rgb.npy", allow_pickle=False))[None]
            # Camera remains an explicit input; these tests do not infer it.
            captures = {}
            class RecordingSampler(FlowEulerGuidanceIntervalSampler):
                label = "ss"
                @torch.no_grad()
                def sample(self, *positional, **kwargs):
                    kwargs["verbose"] = False; result = super().sample(*positional, **kwargs); captures[self.label] = result; return result
            sampler = RecordingSampler(1e-5)
            sn = {"mean": [-.7, -.4, -.1, .2, .5, .8, 1.1, 1.4], "std": [.2, .4, .6, .8, 1., 1.2, 1.4, 1.6]}
            params = {"steps": 3, "guidance_strength": 2.5, "guidance_rescale": .3, "guidance_interval": (0, 1)}
            pipeline = SimpleNamespace(device="cpu", low_vram=False, image_cond_model_ss=extractor,
                models={"sparse_structure_flow_model": flows["ss"], "sparse_structure_decoder": model}, sparse_structure_sampler=sampler,
                sparse_structure_sampler_params=params, shape_slat_sampler=sampler, shape_slat_sampler_params=params, shape_slat_normalization=sn)
            def capture_latent(_module, inputs): expected["latent"] = inputs[0].detach().numpy().copy()
            model.register_forward_pre_hook(capture_latent)
            model.register_forward_hook(reference_hook(expected, "logits"))
            torch.manual_seed(7151); noise = torch.randn(1, 8, 2, 2, 2)
            np.save(directory / "noise.npy", noise[0].reshape(8, -1).T.contiguous().numpy())
            with torch.no_grad():
                cond = namespace["get_proj_cond_ss"](pipeline, rgb); torch.manual_seed(7151)
                coords = namespace["sample_sparse_structure"](pipeline, cond, output_resolution)
                if len(coords) == 0: raise ValueError("connected synthetic decoder emitted no coordinates")
                expected["coords"] = coords[:, 1:].numpy()
                extractor.use_naf_upsample = True; extractor.grid_resolution = output_resolution
                extractor.proj_grid = namespace["ProjGrid"](output_resolution, 12)
                cond = namespace["get_proj_cond_shape"](pipeline, extractor, rgb, coords)
                torch.manual_seed(7152); shape_noise = torch.randn(len(coords), 8); np.save(directory / "shape_noise.npy", shape_noise.numpy())
                torch.manual_seed(7152); sampler.label = "shape"
                shape = namespace["sample_shape_slat"](pipeline, cond, flows["shape"], coords)
                expected["shape"] = shape.feats.numpy()
                for label, sampled in captures.items():
                    for i, sample in enumerate(sampled.pred_x_t): expected[f"{label}.sample{i}"] = (sample.feats if label == "shape" else sample[0].reshape(8, -1).T).numpy()
            latent = torch.from_numpy(expected["latent"])
            np.save(directory / "rgb.npy", rgb[0].numpy()); np.save(directory / "camera.npy", np.array([.8575560450553894, 2., 1.], np.float32))
            extra = ["--dino", str(dp), "--naf", str(npth), "--flow", str(paths["ss"]), "--shape", str(paths["shape"])]
        else:
            with torch.no_grad(): logits = model(latent)
            expected["logits"] = logits.numpy()
            mask = logits > 0
            if output_resolution != logits.shape[-1]: mask = F.max_pool3d(mask.float(), logits.shape[-1] // output_resolution) > .5
            expected["coords"] = torch.argwhere(mask)[:, [2, 3, 4]].numpy()
        expected["progress"] = [[i, len(channels)] for i in range(len(channels) + 1)]
        np.save(directory / "latent.npy", latent[0].numpy()); np.save(directory / "output_resolution.npy", np.array([output_resolution], np.float32))
        native_path = directory / "converted/model.gguf"
        record = compare(directory, expected, run(directory, native_path, extra), native_path)
        if record["returncode"] == 0:
            # Source norm evaluated on the exact native preceding activation:
            # separates operator error from accumulated input perturbations.
            previous = f"blocks.{len(model.blocks)-1}" if len(model.blocks) else f"middle_block.{middle-1}" if middle else "input_layer"
            shape = expected["out_layer.0"].shape
            preceding = torch.from_numpy(np.load(directory / ("actual_" + previous + ".npy"))).reshape(shape)
            saved = expected["out_layer.0"].copy()
            with torch.no_grad(): local_norm = model.out_layer[0](preceding).numpy().reshape(-1)
            expected["out_layer.0"] = saved
            actual_norm = np.load(directory / "actual_out_layer.0.npy")
            record["norm_same_input"] = {"passed": bool(np.allclose(actual_norm, local_norm, atol=5e-5, rtol=5e-5)), "max_abs_error": float(np.abs(actual_norm-local_norm).max())}
            record["passed"] &= record["norm_same_input"]["passed"]
            np.save(directory / "reference_norm_same_input.npy", local_norm)
        record["reference_fp16"] = fp16; record["evaluation_arithmetic"] = "F32"; record["decoder_resolution"] = resolution * 2 ** (len(channels) - 1)
        record["minimum_logit_distance_from_zero"] = float(np.abs(expected["logits"]).min())
        records.append(record)
        print(name, record["passed"], flush=True)

    baseline = args.output_dir / "three_stages"
    deterministic = convert(baseline / "source.safetensors", baseline / "config.json", baseline / "repeated", storage="f32", **provenance)["output_sha256"] == digest(baseline / "converted/model.gguf")
    converter_checks = {}
    for case in ("missing_tensor", "extra_tensor", "wrong_shape", "wrong_dtype", "nan", "overflow", "unknown_config", "invalid_group", "invalid_stages", "output_channels", "duplicate_json", "existing_output"):
        directory = args.output_dir / "negative_converter" / case; directory.mkdir(parents=True)
        state = load_file(baseline / "source.safetensors"); config = json.loads((baseline / "config.json").read_text())
        first = next(iter(state))
        if case == "missing_tensor": del state[first]
        elif case == "extra_tensor": state["extra"] = torch.zeros(1)
        elif case == "wrong_shape": state[first] = state[first][:-1].contiguous()
        elif case == "wrong_dtype": state[first] = state[first].int()
        elif case == "nan": state[first].view(-1)[0] = float("nan")
        elif case == "overflow": state["input_layer.weight"].view(-1)[0] = 1e9
        elif case == "unknown_config": config["args"]["extra"] = True
        elif case == "invalid_group": config["args"]["norm_type"] = "group"
        elif case == "invalid_stages": config["args"]["channels"] = []
        elif case == "output_channels": config["args"]["out_channels"] = 2
        cp = directory / "config.json"; cp.write_text('{"args":{},"args":{}}' if case == "duplicate_json" else json.dumps(config))
        sp = directory / "source.safetensors"; save_file(state, sp)
        output = directory / "converted"
        if case == "existing_output": output.mkdir(); (output / "sentinel").write_text("keep")
        try:
            convert(sp, cp, output, storage="f16", **provenance); converter_checks[case] = {"passed": False}
        except ValueError as exc:
            converter_checks[case] = {"passed": not (output / "model.gguf").exists() and (not output.exists() or (case == "existing_output" and (output / "sentinel").read_text() == "keep")), "error": str(exc)}
    native_checks = {}
    mutations = {"schema": ("pixal.schema_version", 99), "reference": ("pixal.reference_revision", "bad"), "missing_metadata": ("pixal.ss_decoder.latent_channels", None),
                 "channels": ("pixal.ss_decoder.channels.0", 3), "normalization": ("pixal.ss_decoder.norm_type", "group"), "source_hash": ("pixal.checkpoint_sha256", "bad"),
                 "tensor_name": (None, None), "tensor_shape": (None, None), "tensor_type": (None, None), "truncated": (None, None), "nan_weight": (None, None)}
    reader = gguf.GGUFReader(baseline / "converted/model.gguf")
    for case, (changed_key, changed_value) in mutations.items():
        directory = args.output_dir / "negative_native" / case; directory.mkdir(parents=True)
        for name in ("latent.npy", "output_resolution.npy"): shutil.copyfile(baseline / name, directory / name)
        path = directory / "model.gguf"; writer = gguf.GGUFWriter(path, ARCHITECTURE)
        for key, field in reader.fields.items():
            if key.startswith("GGUF.") or key == "general.architecture" or (key == changed_key and changed_value is None): continue
            writer.add_key_value(key, changed_value if key == changed_key else field.contents(), field.types[0])
        for i, t in enumerate(reader.tensors):
            value = t.data.copy()
            if case == "tensor_shape" and i == 0: value = value.reshape(-1)[:-1].copy()
            if case == "tensor_type" and i == 0: value = value.astype(np.float16)
            if case == "nan_weight" and i == 0: value.flat[0] = float("nan")
            writer.add_tensor("unexpected" if case == "tensor_name" and i == 0 else t.name, value)
        writer.write_header_to_file(); writer.write_kv_data_to_file(); writer.write_tensors_to_file(); writer.close()
        if case == "truncated":
            with path.open("r+b") as f: f.truncate(path.stat().st_size - 128)
        result = run(directory, path)
        native_checks[case] = {"passed": result.returncode == 1 and not list(directory.glob("actual_*")) and (case == "nan_weight" or "backend_initialized=" not in result.stdout), "error": result.stderr.strip()}
    for case in ("reference_precision", "nan_latent", "latent_extent", "latent_channels", "latent_resolution", "cancel_before", "cancel_between", "cancel_final"):
        directory = args.output_dir / "negative_native" / case; directory.mkdir(parents=True)
        base = args.output_dir / "fp16_config_explicit_f32" if case == "reference_precision" else baseline
        for name in ("latent.npy", "output_resolution.npy"): shutil.copyfile(base / name, directory / name)
        result = run(directory, base / "converted/model.gguf", ["--fault", case])
        native_checks[case] = {"passed": result.returncode == 1 and not list(directory.glob("actual_*")), "error": result.stderr.strip()}
    for case in ("flow_mismatch", "wrapper_cancel", "wrapper_bad_pool"):
        base = args.output_dir / "connected_image"
        directory = args.output_dir / "negative_native" / case
        shutil.copytree(base, directory, ignore=shutil.ignore_patterns("actual_*", "expected_*", "*.log", "converted", "source.safetensors"))
        result = run(directory, base / "converted/model.gguf", extra + ["--fault", case])
        native_checks[case] = {"passed": result.returncode == 1 and not list(directory.glob("actual_*")), "error": result.stderr.strip()}
    reference_file = args.pixal_source / "pixal3d/models/sparse_structure_vae.py"
    report = {"passed": deterministic and all(c["passed"] for c in records) and all(c["passed"] for c in list(converter_checks.values()) + list(native_checks.values())),
              "cases": records, "converter_checks": converter_checks, "native_checks": native_checks, "byte_deterministic": deterministic,
              "reference_revision": PIXAL_REVISION, "source_sha256": digest(reference_file), "pipeline_sha256": digest(pipeline_source), "binary_sha256": digest(args.binary),
              "backend": args.backend, "device_index": args.device_index, "torch_gpu_initialized": torch.cuda.is_initialized(),
              "packages": {n: importlib.metadata.version(n) for n in ("torch", "numpy", "gguf", "transformers", "natten")},
              "trained_weights": "NOT USED", "mixed_activations": "NOT TESTED; explicit F32 evaluation", "shape_texture_decoder_glb_camera_library": "NOT TESTED"}
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "cases": len(records), "converter_checks": len(converter_checks), "native_checks": len(native_checks)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__": raise SystemExit(main())
