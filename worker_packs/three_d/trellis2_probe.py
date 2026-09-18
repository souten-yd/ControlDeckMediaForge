from __future__ import annotations

"""Local-only, bounded TRELLIS.2 adoption probe.

This is an evaluator, not a production adapter. It never resolves a repository
name and therefore cannot download weights. The caller must provide the exact
pinned Hugging Face snapshot after accepting the upstream license.

Measured on AMD Radeon AI PRO R9700 (gfx1201, RDNA4) with ROCm 7.2.1. Two things
about this machine shape the probe:

* The CUDA rasterizer cannot run here. It uses PTX inline assembly, so the HIP
  build stubs it out and the OpenGL rasterizer takes over. Anything that asks
  for ``RasterizeCudaContext`` has to be redirected to ``RasterizeGLContext``.
* fp32 matmul returns wrong values, silently, once the row count passes 2^19.
  bf16 and fp16 are unaffected. The probe checks this before it reports timings,
  because a fast run that produced corrupt geometry is not a successful run.

See docs/implementation/g9-image-to-3d.md.
"""

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Any


CANDIDATE_REPOSITORY = "microsoft/TRELLIS.2-4B"
CANDIDATE_REVISION = "af44b45f2e35a493886929c6d786e563ec68364d"
GEMM_CORRUPTION_THRESHOLD = 1 << 19


@dataclass(frozen=True)
class ProbePreset:
    simplify_faces: int
    decimation_target: int
    texture_size: int


PRESETS = {
    # Loading and ROCm smoke only. Never quality evidence.
    "smoke": ProbePreset(simplify_faces=1 << 18, decimation_target=50_000, texture_size=1024),
    # What an asset would actually be exported at.
    "asset": ProbePreset(simplify_faces=1 << 24, decimation_target=1_000_000, texture_size=4096),
}


def _contained(root: Path, candidate: Path, *, must_exist: bool = False) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=must_exist)
    if not resolved.is_relative_to(resolved_root):
        raise ValueError("probe path escapes its allowed root")
    return resolved


def _snapshot(path: Path) -> Path:
    """Accept only the pinned revision, laid out as a Hugging Face cache entry."""
    snapshot = path.resolve(strict=True)
    if not snapshot.is_dir() or snapshot.name != CANDIDATE_REVISION:
        raise ValueError("TRELLIS.2 snapshot revision differs from the pinned revision")
    if snapshot.parent.name != "snapshots":
        raise ValueError("TRELLIS.2 snapshot must use a verified Hugging Face cache layout")
    config = (snapshot / "pipeline.json").resolve(strict=True)
    if not config.is_file() or not config.is_relative_to(snapshot):
        raise ValueError("TRELLIS.2 pipeline config escapes its snapshot")
    if config.stat().st_size > 64 * 1024:
        raise ValueError("TRELLIS.2 pipeline config is unbounded")
    return snapshot


def _offline_environment() -> None:
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    # The OpenGL rasterizer replaces the CUDA one on this platform, and flash
    # attention is not built, so fall back to what PyTorch ships.
    os.environ.setdefault("ATTN_BACKEND", "sdpa")


def _gemm_is_sane(torch: Any) -> dict[str, Any]:
    """Check the fp32 GEMM defect before trusting any generated geometry.

    The failure is silent: no exception, no NaN, just wrong numbers. So compare
    against the CPU instead of asking whether the call returned.
    """
    rows = GEMM_CORRUPTION_THRESHOLD * 2
    a = torch.randn(rows, 64, dtype=torch.float32)
    b = torch.randn(64, 32, dtype=torch.float32)
    expected = a @ b
    actual = (a.cuda() @ b.cuda()).cpu()
    mismatched = int((actual - expected).abs().gt(1e-3).sum())
    return {"rows": rows, "mismatched": mismatched, "fp32_matmul_sane": mismatched == 0}


def _peak_vram_bytes(torch: Any) -> int:
    return int(torch.cuda.max_memory_allocated())


def _generate(snapshot: Path, image_path: Path, output: Path, preset_name: str) -> dict[str, Any]:
    _offline_environment()
    import torch
    from PIL import Image

    preset = PRESETS[preset_name]
    report: dict[str, Any] = {
        "repository": CANDIDATE_REPOSITORY,
        "revision": CANDIDATE_REVISION,
        "preset": preset_name,
        "attn_backend": os.environ["ATTN_BACKEND"],
        "torch": torch.__version__,
        "hip": torch.version.hip,
        "device": torch.cuda.get_device_properties(0).gcnArchName,
    }
    report["gemm"] = _gemm_is_sane(torch)

    from trellis2.pipelines import Trellis2ImageTo3DPipeline
    import o_voxel

    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained(str(snapshot))
    pipeline.cuda()
    report["load_sec"] = round(time.perf_counter() - started, 2)

    image = Image.open(image_path)
    started = time.perf_counter()
    mesh = pipeline.run(image)[0]
    report["generate_sec"] = round(time.perf_counter() - started, 2)
    mesh.simplify(preset.simplify_faces)

    started = time.perf_counter()
    glb = o_voxel.postprocess.to_glb(
        vertices=mesh.vertices,
        faces=mesh.faces,
        attr_volume=mesh.attrs,
        coords=mesh.coords,
        attr_layout=mesh.layout,
        voxel_size=mesh.voxel_size,
        aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
        decimation_target=preset.decimation_target,
        texture_size=preset.texture_size,
        remesh=True,
        remesh_band=1,
        remesh_project=0,
        verbose=False,
    )
    glb.export(str(output), extension_webp=True)
    report["export_sec"] = round(time.perf_counter() - started, 2)
    report["peak_vram_bytes"] = _peak_vram_bytes(torch)
    report["output"] = str(output)
    report["output_bytes"] = output.stat().st_size
    report["vertices"] = int(mesh.vertices.shape[0])
    report["faces"] = int(mesh.faces.shape[0])
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", choices=("run",))
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preset", choices=tuple(PRESETS), default="smoke")
    args = parser.parse_args()

    snapshot = _snapshot(args.snapshot)
    work_root = args.work_root.resolve(strict=True)
    output = _contained(work_root, args.output)
    print(json.dumps(_generate(snapshot, args.image.resolve(strict=True), output, args.preset), sort_keys=True))


if __name__ == "__main__":
    main()
