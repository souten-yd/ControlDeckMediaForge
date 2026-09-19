#!/usr/bin/env python3
"""Pinned Pixal foreground/stage/cascade CPU oracle, with synthetic checkpoints.

Decoder logits/upsampled coordinates are explicit fixtures, not neural decoder
inference. Native noise is saved from Torch; native seed/RNG equivalence is not
claimed. No pretrained weights, network, background-removal or camera model.
"""
from __future__ import annotations

import argparse
import ast
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from typing import List, Optional, Tuple, Union

from convert_vision import NAF_REVISION, PIXAL_REVISION, digest
from prepare_image import frame_foreground, prepare_rgb


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pixal-source", "naf-source", "checkpoint-fixtures", "vision-fixtures", "binary", "output-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--backend", choices=("cpu", "vulkan"), default="cpu")
    parser.add_argument("--device-index", type=int)
    args = parser.parse_args()
    if (args.backend == "vulkan") != (args.device_index is not None):
        parser.error("Vulkan requires an admitted explicit device index")
    for source, pin in ((args.pixal_source, PIXAL_REVISION), (args.naf_source, NAF_REVISION)):
        if subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip() != pin or subprocess.check_output(["git", "-C", str(source), "diff", "HEAD", "--"]):
            parser.error("references must be pinned with no tracked changes")
    if args.output_dir.exists():
        parser.error("use a fresh output directory")
    os.environ.update({"HIP_VISIBLE_DEVICES": "-1", "ROCR_VISIBLE_DEVICES": "-1", "CUDA_VISIBLE_DEVICES": "-1",
                       "HF_HUB_OFFLINE": "1", "ATTN_BACKEND": "sdpa", "SPARSE_ATTN_BACKEND": "sdpa", "SPARSE_CONV_BACKEND": "none"})
    sys.path[:0] = [str(args.pixal_source.resolve()), str(args.naf_source.resolve())]
    import numpy as np
    import torch
    import torch.nn.functional as F
    from PIL import Image
    from torchvision import transforms
    from transformers import DINOv3ViTConfig, DINOv3ViTModel
    from safetensors.torch import load_file
    from natten import na2d
    from src.model.naf import NAF
    from src.layers import attentions
    from pixal3d.models.sparse_structure_flow import SparseStructureFlowModel
    from pixal3d.models.structured_latent_flow import ElasticSLatFlowModel
    from pixal3d.modules.sparse import SparseTensor
    from pixal3d.pipelines.samplers.flow_euler import FlowEulerGuidanceIntervalSampler

    if importlib.metadata.version("transformers") != "4.57.3" or importlib.metadata.version("natten") != "0.21.0":
        raise ValueError("use pinned reference dependencies")
    torch.set_num_threads(2)
    # Same CPU NATTEN adaptation as the separately measured NAF slice.
    def cpu_attention(q, k, v, **kwargs):
        assert kwargs.pop("backend") == "cutlass-fna"
        width = q.shape[-1]
        chunks = []
        for start in range(0, v.shape[-1], width):
            part = v[..., start:start + width]
            chunks.append(na2d(q, k, F.pad(part, (0, width - part.shape[-1])), **kwargs,
                              backend="flex-fna", torch_compile=False)[..., :part.shape[-1]])
        return torch.cat(chunks, dim=-1)
    attentions.na2d = cpu_attention
    namespace = {"torch": torch, "nn": torch.nn, "F": F, "np": np, "Image": Image, "transforms": transforms,
                 "Tuple": Tuple, "Optional": Optional, "Union": Union, "List": List, "DINOv3ViTModel": DINOv3ViTModel,
                 "SparseTensor": SparseTensor}
    projection_source = args.pixal_source / "pixal3d/trainers/flow_matching/mixins/image_conditioned_proj.py"
    names = {"project_points_to_image_batch", "sample_features", "ProjGrid", "DinoV3ProjFeatureExtractor"}
    nodes = [n for n in ast.parse(projection_source.read_text()).body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
    assert len(nodes) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(projection_source), "exec"), namespace)
    pipeline_source = args.pixal_source / "pixal3d/pipelines/pixal3d_image_to_3d.py"
    cls = next(n for n in ast.parse(pipeline_source.read_text()).body if isinstance(n, ast.ClassDef))
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    names = {"preprocess_image", "get_proj_cond_ss", "get_proj_cond_shape", "sample_sparse_structure", "sample_shape_slat", "sample_tex_slat"}
    exec(compile(ast.Module(body=[methods[n] for n in sorted(names)], type_ignores=[]), str(pipeline_source), "exec"), namespace)
    # Execute the exact actual run() cascade, not the older cascade helper.
    body = methods["run"].body
    start = next(i for i, n in enumerate(body) if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "lr_resolution")
    finish = next(i for i in range(start, len(body)) if isinstance(body[i], ast.Assign) and isinstance(body[i].targets[0], ast.Name) and body[i].targets[0].id == "actual_grid_res")
    cascade_code = compile(ast.Module(body=body[start:finish + 1], type_ignores=[]), str(pipeline_source), "exec")
    budget_line = next(n.lineno for n in ast.walk(body[start + 2]) if isinstance(n, ast.If))

    def cascade(raw, resolution, budget):
        env = {"torch": torch, "hr_coords": torch.cat([torch.zeros(len(raw), 1, dtype=torch.int32), torch.from_numpy(raw).int()], dim=1),
               "hr_resolution": resolution, "max_num_tokens": budget}
        attempts = []
        def capture(frame, event, _arg):
            if frame.f_code is cascade_code and event == "line" and frame.f_lineno == budget_line:
                attempts.append([frame.f_locals["actual_hr_resolution"], frame.f_locals["num_tokens"]])
            return capture
        old = sys.gettrace()
        sys.settrace(capture)
        try:
            exec(cascade_code, env)
        finally:
            sys.settrace(old)
        return env["hr_coords_unique"], env["actual_hr_resolution"], attempts

    args.output_dir.mkdir(parents=True)
    rng = np.random.default_rng(9511)
    preprocessing = []
    framed_inputs = []
    for case in ("rgba_rectangle", "rgba_edge", "rgba_threshold", "rgba_large", "rgb_provider", "opaque_rgba_provider", "gray_provider", "palette_provider"):
        width, height = (1361, 1081) if case == "rgba_large" else (37, 21)
        array = rng.integers(0, 256, (height, width, 4), dtype=np.uint8)
        array[:, :, 3] = 0
        if case == "rgba_edge":
            array[0:15, 0:31, 3] = 255
        else:
            array[3:height - 4, 4:width - 7, 3] = 205
        if case == "rgba_threshold":
            array[0, 0, 3] = 204
        original = Image.fromarray(array)
        if "provider" in case:
            mode = {"rgb_provider": "RGB", "opaque_rgba_provider": "RGBA", "gray_provider": "L", "palette_provider": "P"}[case]
            original = original.convert("RGB").convert(mode)
        def provider(image):
            # Protocol fixture only, not background-removal inference.
            a = np.array(image.convert("RGBA")); a[:, :, 3] = 0
            a[2:-3, 3:-4, 3] = 240
            return Image.fromarray(a)
        bg = (27, 131, 233) if case in {"rgba_edge", "rgba_threshold"} else (0, 0, 0)
        expected = namespace["preprocess_image"](SimpleNamespace(low_vram=False, rembg_model=provider), original, bg)
        actual = frame_foreground(original, remove_background=provider, background=bg)
        directory = args.output_dir / "preprocess" / case; directory.mkdir(parents=True)
        original.save(directory / "input.png"); expected.save(directory / "reference.png"); actual.image.save(directory / "actual.png")
        passed = expected.size == actual.image.size and np.array_equal(np.array(expected), np.array(actual.image))
        preprocessing.append({"case": case, "passed": bool(passed), "output_size": actual.image.size,
                              "used_input_alpha": actual.used_input_alpha, "crop_box": actual.crop_box})
        framed_inputs.append(actual.image)
    preprocessing_negative = {}
    empty = Image.new("RGBA", (20, 20), (100, 50, 20, 0))
    single = empty.copy(); single.putpixel((10, 10), (100, 50, 20, 255))
    for name, image, kwargs in (
        ("missing_provider", Image.new("RGB", (10, 10)), {}), ("empty_mask", empty, {}), ("degenerate_mask", single, {}),
        ("bad_background", empty, {"background": (0, 256, 0)}),
        ("provider_rgb", Image.new("RGB", (10, 10)), {"remove_background": lambda im: im}),
        ("provider_extent", Image.new("RGB", (10, 10)), {"remove_background": lambda im: empty}),
        ("collapsed_resize", Image.new("RGBA", (2000, 1)), {}),
    ):
        try:
            frame_foreground(image, **kwargs)
            preprocessing_negative[name] = {"passed": False}
        except (TypeError, ValueError) as exc:
            preprocessing_negative[name] = {"passed": True, "error": str(exc)}

    def command(directory, models=None, fault=None):
        cmd = [str(args.binary.resolve()), str(directory.resolve()), args.backend]
        if args.device_index is not None:
            cmd += ["--device", str(args.device_index)]
        if models:
            for name, path in models.items():
                cmd += ["--" + name, str(path.resolve())]
        if fault:
            cmd += ["--fault", fault]
        return cmd

    def compare(directory, expected, models=None):
        for name, value in expected.items():
            np.save(directory / ("expected_" + name + ".npy"), np.asarray(value).reshape(-1))
        cmd = command(directory, models)
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        (directory / "native.log").write_text(proc.stdout + proc.stderr)
        record = {"case": directory.name, "command": cmd, "returncode": proc.returncode, "tensors": {}, "passed": False}
        if proc.returncode == 0:
            for name, value in expected.items():
                value = np.asarray(value).reshape(-1)
                actual = np.load(directory / ("actual_" + name + ".npy"), allow_pickle=False)
                discrete = name in {"lr_coords", "hr_coords", "cascade", "attempts", "progress", "progress_events"}
                ok = actual.shape == value.shape and (np.array_equal(actual, value) if discrete else np.allclose(actual, value, atol=5e-5, rtol=5e-5))
                error = float(np.max(np.abs(actual - value), initial=0)) if actual.shape == value.shape else None
                record["tensors"][name] = {"passed": bool(ok), "max_abs_error": error, "exact": discrete}
            record["passed"] = all(t["passed"] for t in record["tensors"].values())
        return record

    def save_bridge(directory, resolution, budget, raw, decoded=8, output=4, empty_mask=False):
        directory.mkdir(parents=True)
        logits = np.full((decoded,) * 3, -1, np.float32)
        logits[0, 0, 0] = 0 # strict >0, not >=0
        if not empty_mask:
            logits[1, 0, 1] = np.nextafter(np.float32(0), np.float32(1))
            logits[-1, -1, -1] = 1; logits[3, 4, 2] = 2; logits[5, 1, 6] = .1
        active = torch.from_numpy(logits)[None, None] > 0
        if decoded != output:
            active = F.max_pool3d(active.float(), decoded // output, decoded // output, 0) > .5
        coords = torch.argwhere(active)[:, [0, 2, 3, 4]].int()
        hr, actual_resolution, attempts = cascade(raw, resolution, budget)
        np.save(directory / "logits.npy", logits)
        np.save(directory / "decoder_coords.npy", raw.astype(np.float32))
        np.save(directory / "settings.npy", np.array([decoded, output, resolution, budget], np.float32))
        expected = {"lr_coords": coords[:, 1:].numpy(), "hr_coords": hr[:, 1:].numpy(),
                    "cascade": [actual_resolution, len(hr) < budget], "attempts": attempts}
        return coords, hr, actual_resolution, expected

    diagonal = np.repeat(np.arange(512, dtype=np.int32)[:, None], 3, axis=1)
    small = np.array([[511, 511, 511], [4, 4, 4], [0, 0, 0], [64, 321, 20], [4, 4, 4], [100, 120, 300]], np.int32)
    bridge = []
    cases = [("1024_round_canary", 1024, 100, small, 4, False), ("1536_budget_equal", 1536, 96, diagonal, 4, False),
             ("1536_backoff_1408", 1536, 90, diagonal, 4, False), ("1536_budget_floor", 1536, 64, diagonal, 4, False),
             ("1536_no_backoff", 1536, 97, diagonal, 4, False), ("identity_pool", 1024, 100, small, 8, False),
             ("empty_occupancy", 1024, 100, small, 4, True)]
    for name, resolution, budget, raw, output, empty_mask in cases:
        directory = args.output_dir / "bridge" / name
        _, _, _, expected = save_bridge(directory, resolution, budget, raw, output=output, empty_mask=empty_mask)
        bridge.append(compare(directory, expected))

    def fixture_model(part, model):
        manifest = json.loads((part / "converted/manifest.json").read_text())
        if (manifest["source"]["source_kind"] != "synthetic" or digest(part / "converted/model.gguf") != manifest["output_sha256"]
                or digest(part / "source.safetensors") != manifest["source"]["checkpoint_sha256"]
                or digest(part / "config.json") != manifest["source"]["config_sha256"]):
            raise ValueError("use intact synthetic checkpoint fixtures")
        state = load_file(part / "source.safetensors")
        rounded = {}
        for name, value in state.items():
            value = value.float()
            if manifest["storage"] == "f16" and value.ndim in (2, 4) and name.endswith(".weight"):
                value = value.half().float()
            rounded[name] = value
        # SS constructs this deterministic positional buffer from resolution;
        # the fixture converter intentionally stores learned parameters only.
        if isinstance(model, SparseStructureFlowModel) and "rope_phases" not in rounded:
            rounded["rope_phases"] = model.state_dict()["rope_phases"]
        model.load_state_dict(rounded, strict=True)
        return model.eval(), part / "converted/model.gguf"

    integrated = []
    last_models = None
    for index, (name, vision_case, resolution, budget, raw) in enumerate((
        ("rgba_1024", "f32_full", 1024, 100, small),
        ("composite_1536", "bf16_f16_storage", 1536, 100, small),
        ("backoff_1408", "f32_full", 1536, 90, diagonal),
    )):
        directory = args.output_dir / "integrated" / name
        coords, hr_coords, actual_resolution, expected = save_bridge(directory, resolution, budget, raw)
        frame = framed_inputs[index]
        frame.save(directory / "framed.png")
        vision = args.vision_fixtures / vision_case
        cfg = DINOv3ViTConfig.from_dict(json.loads((vision / "dino/config.json").read_text())); cfg._attn_implementation = "sdpa"
        dino, dino_path = fixture_model(vision / "dino", DINOv3ViTModel(cfg))
        naf, naf_path = fixture_model(vision / "naf", NAF(**json.loads((vision / "naf/config.json").read_text())["args"]))
        size = 12
        extractor = namespace["DinoV3ProjFeatureExtractor"].__new__(namespace["DinoV3ProjFeatureExtractor"])
        torch.nn.Module.__init__(extractor)
        extractor.model = dino; extractor.image_size = size; extractor.patch_number = 3
        extractor.transform = transforms.Normalize([.485, .456, .406], [.229, .224, .225])
        extractor.grid_resolution = 2; extractor.proj_grid = namespace["ProjGrid"](2, size)
        extractor.use_naf_upsample = False; extractor.naf_model = naf; extractor.naf_target_size = (8, 8)
        models = {"dino": dino_path, "naf": naf_path}
        flows = {}
        for stage in ("ss", "shape", "texture"):
            part = args.checkpoint_fixtures / (stage + "_f32_f32")
            config = json.loads((part / "config.json").read_text())
            flow, path = fixture_model(part, (SparseStructureFlowModel if stage == "ss" else ElasticSLatFlowModel)(**config["args"]))
            flows[stage] = flow; models[stage] = path
        sn = {"mean": np.linspace(-.7, .8, 8, dtype=np.float32).tolist(), "std": np.linspace(.2, 1.7, 8, dtype=np.float32).tolist()}
        tn = {"mean": np.linspace(.5, -.3, 8, dtype=np.float32).tolist(), "std": np.linspace(1.8, .7, 8, dtype=np.float32).tolist()}
        samples = {}
        class RecordingSampler(FlowEulerGuidanceIntervalSampler):
            label = "ss"
            @torch.no_grad()
            def sample(self, *positional, **kwargs):
                kwargs["verbose"] = False
                result = super().sample(*positional, **kwargs)
                samples[self.label] = result
                return result
        sampler = RecordingSampler(1e-5)
        class FixtureDecoder:
            def __call__(self, latent):
                expected["ss_dense"] = latent.detach().numpy()
                return torch.from_numpy(np.load(directory / "logits.npy"))[None, None]
        params = {"steps": 3, "guidance_strength": 2.5, "guidance_rescale": .3, "guidance_interval": (0, 1)}
        pipeline = SimpleNamespace(device="cpu", low_vram=False, image_cond_model_ss=extractor,
            models={"sparse_structure_flow_model": flows["ss"], "sparse_structure_decoder": FixtureDecoder()},
            sparse_structure_sampler=sampler, shape_slat_sampler=sampler, tex_slat_sampler=sampler,
            sparse_structure_sampler_params=params, shape_slat_sampler_params=params, tex_slat_sampler_params=params,
            shape_slat_normalization=sn, tex_slat_normalization=tn)
        # Native receives these exact Torch noises. It does not claim its own
        # RNG is seed-identical to PyTorch.
        for label, shape_noise in (("ss", (1, 8, 2, 2, 2)), ("lr", (len(coords), 8)), ("hr", (len(hr_coords), 8)), ("texture", (len(hr_coords), 8))):
            torch.manual_seed(271 + len(label)); noise = torch.randn(*shape_noise)
            if label == "ss": noise = noise[0].reshape(8, -1).T.contiguous()
            np.save(directory / (label + "_noise.npy"), noise.numpy())
        with torch.no_grad():
            # The upstream list-of-PIL branch hardcodes .cuda(). Feed its public
            # tensor branch on CPU with independently reproduced Pillow pixels.
            pixels = np.array(frame.resize((size, size), Image.Resampling.LANCZOS).convert("RGB")).astype(np.float32) / 255
            assert np.array_equal(prepare_rgb(frame, size), pixels.transpose(2, 0, 1))
            rgb = torch.from_numpy(pixels.transpose(2, 0, 1).copy())[None]
            tokens = extractor.extract_features(extractor.transform(rgb))
            expected["global"] = tokens[:, :5].numpy(); expected["patches"] = tokens[:, 5:].numpy()
            high = naf(rgb, tokens[:, 5:].reshape(1, 3, 3, 32).permute(0, 3, 1, 2), (8, 8))
            expected["high"] = high.permute(0, 2, 3, 1).numpy()
            cond = namespace["get_proj_cond_ss"](pipeline, rgb)
            torch.manual_seed(273)
            reference_coords = namespace["sample_sparse_structure"](pipeline, cond, 4)
            assert torch.equal(reference_coords, coords)
            extractor.use_naf_upsample = True; extractor.grid_resolution = 4; extractor.proj_grid = namespace["ProjGrid"](4, size)
            cond = namespace["get_proj_cond_shape"](pipeline, extractor, rgb, coords)
            sampler.label = "lr"; torch.manual_seed(273)
            lr = namespace["sample_shape_slat"](pipeline, cond, flows["shape"], coords)
            expected["lr"] = lr.feats.numpy()
            # Upstream run() HR sample is the same sampler + normalization used
            # in sample_shape_slat; grid override and cascade came from run().
            cond = namespace["get_proj_cond_shape"](pipeline, extractor, rgb, hr_coords, grid_resolution_override=actual_resolution // 16)
            assert extractor.grid_resolution == 4 # override restores source model
            sampler.label = "hr"; torch.manual_seed(273)
            hr = namespace["sample_shape_slat"](pipeline, cond, flows["shape"], hr_coords)
            expected["hr"] = hr.feats.numpy()
            expected["texture_concat"] = ((hr.feats - torch.tensor(sn["mean"])) / torch.tensor(sn["std"])).numpy()
            cond = namespace["get_proj_cond_shape"](pipeline, extractor, rgb, hr_coords, grid_resolution_override=actual_resolution // 16)
            sampler.label = "texture"; torch.manual_seed(278)
            tex = namespace["sample_tex_slat"](pipeline, cond, flows["texture"], hr)
            expected["texture"] = tex.feats.numpy()
            for label, result in samples.items():
                for step, value in enumerate(result.pred_x_t):
                    expected[f"{label}.sample{step}"] = (value.feats if label != "ss" else value[0].reshape(8, -1).T).numpy()
        expected["progress"] = [12]
        expected["progress_events"] = [[done, 3] for _ in range(4) for done in range(4)]
        np.save(directory / "rgb.npy", prepare_rgb(frame, size)); np.save(directory / "target.npy", np.array([8, 8], np.float32))
        np.save(directory / "camera.npy", np.array([.8575560450553894, 2., 1.], np.float32))
        np.save(directory / "shape_norm.npy", np.array([sn["mean"], sn["std"]], np.float32))
        np.save(directory / "texture_norm.npy", np.array([tn["mean"], tn["std"]], np.float32))
        record = compare(directory, expected, models)
        # Repeat the connected computation independently, with the same fixtures.
        old = {p.name: digest(p) for p in directory.glob("actual_*.npy")}
        repeat = subprocess.run(command(directory, models), capture_output=True, text=True, timeout=120)
        (directory / "repeat.log").write_text(repeat.stdout + repeat.stderr)
        record["repeat_bitwise_equal"] = repeat.returncode == 0 and bool(old) and old == {p.name: digest(p) for p in directory.glob("actual_*.npy")}
        record["passed"] &= record["repeat_bitwise_equal"]
        integrated.append(record)
        if index == 0: last_models = models

    negatives = {}
    for fault in ("nan_occupancy", "occupancy_extent", "pool_ratio", "cascade_extent", "cascade_resolution", "cascade_budget", "cascade_empty",
                  "zero_std", "nan_norm", "norm_extent", "cancel_before_ss", "cancel_between_stages", "wrong_stage", "coords_extent", "empty_coords", "noise_extent", "nan_noise", "texture_shape_extent"):
        base = args.output_dir / "integrated/rgba_1024"
        directory = args.output_dir / "negative" / fault
        shutil.copytree(base, directory, ignore=shutil.ignore_patterns("actual_*", "expected_*", "*.log"))
        proc = subprocess.run(command(directory, last_models, fault), capture_output=True, text=True, timeout=30)
        negatives[fault] = {"returncode": proc.returncode, "error": proc.stderr.strip(), "passed": proc.returncode == 1 and not list(directory.glob("actual_*"))}
    report = {"passed": all(r["passed"] for r in preprocessing + bridge + integrated) and all(r["passed"] for r in list(negatives.values()) + list(preprocessing_negative.values())),
        "preprocessing": preprocessing, "preprocessing_negative": preprocessing_negative, "bridge": bridge, "integrated": integrated, "negative_checks": negatives,
        "pixal_revision": PIXAL_REVISION, "pipeline_sha256": digest(pipeline_source), "projection_sha256": digest(projection_source),
        "naf_revision": NAF_REVISION, "binary_sha256": digest(args.binary), "backend": args.backend, "device_index": args.device_index,
        "packages": {n: importlib.metadata.version(n) for n in ("torch", "numpy", "pillow", "transformers", "natten")},
        "torch_gpu_initialized": torch.cuda.is_initialized(), "pretrained_weights": "NOT USED", "decoder_inference": "NOT TESTED; explicit synthetic output fixtures",
        "background_removal_inference_camera_glb_library": "NOT TESTED", "native_rng_seed_equivalence": "NOT TESTED; saved Torch noise supplied explicitly"}
    (args.output_dir / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "foreground_cases": len(preprocessing), "bridge_cases": len(bridge), "connected_cases": len(integrated), "negative_cases": len(negatives) + len(preprocessing_negative)}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
