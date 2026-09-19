#!/usr/bin/env python3
"""Inspect a candidate Pixal3D environment without weights, network or GPU use.

Run with the candidate's Python, never the MediaForge core environment.
Exit 0 means the software imports and CPU attention check passed; it does not
mean that this runtime is adopted or that GPU inference has been evaluated.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


def deny_network(event: str, args: tuple[Any, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo"}:
        raise RuntimeError("network is disabled during software preflight")


def inspect_source(path: Path, expected: str) -> dict[str, Any]:
    try:
        revision = subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True, stderr=subprocess.DEVNULL, timeout=10,
        ).strip()
        # HIP compilation generates untracked .hip files. Tracked edits must
        # still be reported; they cannot inherit upstream's pinned identity.
        diff = subprocess.check_output(
            ["git", "-C", str(path), "diff", "HEAD", "--"],
            stderr=subprocess.DEVNULL, timeout=10,
        )
        return {
            "revision": revision, "expected_revision": expected,
            "tracked_changes": bool(diff),
            "passed": revision == expected and not diff,
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {"passed": False, "error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    root = args.runtime_root.resolve(strict=True)
    if Path(sys.prefix).resolve() != (root / ".venv").resolve(strict=True):
        parser.error("run this script with the candidate runtime's .venv/bin/python")
    os.environ.update({
        "HIP_VISIBLE_DEVICES": "-1", "ROCR_VISIBLE_DEVICES": "-1",
        "CUDA_VISIBLE_DEVICES": "-1", "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1", "ATTN_BACKEND": "sdpa",
        "SPARSE_ATTN_BACKEND": "sdpa",
    })
    sys.addaudithook(deny_network)
    pins_path = Path(__file__).with_name("sources.json")
    pins = json.loads(pins_path.read_text())
    paths = {name: root / "sources" / name for name in pins}
    paths["Pixal3D"] = root.parent / "pixal3d-source"
    paths["Eigen"] = paths["TRELLIS.2"] / pins["Eigen"]["submodule_path"]
    sources = {
        name: inspect_source(paths[name], pin["revision"])
        for name, pin in pins.items()
    }
    report: dict[str, Any] = {
        "scope": "software_imports_and_cpu_attention_only",
        "adopted": False, "gpu_inference": "NOT TESTED",
        "sources": sources,
        "source_manifest_sha256": hashlib.sha256(pins_path.read_bytes()).hexdigest(),
        "modules": {},
    }
    # Only execute source imports after checking their exact revision.
    if not all(item["passed"] for item in sources.values()):
        report["passed"] = False
    else:
        sys.path[:0] = [str(paths[name]) for name in ("Pixal3D", "MoGe", "NAF")]
        for name in (
            "torch", "torchvision", "transformers", "diffusers",
            "natten.functional", "utils3d", "moge.model.v2", "src.model.naf",
            "flex_gemm", "flex_gemm.kernels.cuda", "o_voxel", "o_voxel._C",
            "cumesh", "nvdiffrast.torch", "nvdiffrec_render",
            "pixal3d.pipelines",
        ):
            try:
                module = importlib.import_module(name)
                report["modules"][name] = {
                    "passed": True, "version": vars(module).get("__version__"),
                }
            except Exception as exc:
                report["modules"][name] = {
                    "passed": False, "error": f"{type(exc).__name__}: {exc}",
                }
        try:
            import torch
            from natten.functional import na2d

            q = torch.ones((1, 8, 8, 1, 16), device="cpu")
            result = na2d(q, q, q, kernel_size=3, backend="flex-fna", torch_compile=False)
            report["cpu_attention"] = {
                "passed": bool(torch.isfinite(result).all() and torch.allclose(result, q)),
                "shape": list(result.shape),
            }
            report["torch_hip_version"] = torch.version.hip
            report["gpu_initialized"] = torch.cuda.is_initialized()
        except Exception as exc:
            report["cpu_attention"] = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
        report["passed"] = (
            all(item["passed"] for item in report["modules"].values())
            and report["cpu_attention"]["passed"]
            and report.get("gpu_initialized") is False
        )
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
