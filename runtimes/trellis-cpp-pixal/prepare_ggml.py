#!/usr/bin/env python3
"""Prepare a pinned GGML copy with the existing Vulkan reduction corrected.

No download, original runtime mutation, device initialization or kernel creation.
Compile this copy separately and record its manifest and resulting library hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

REVISION = "737e88f25d4f62254f3b7a726fd9663036cc94da"
FILES = tuple(f"src/ggml-vulkan/vulkan-shaders/soft_max_large{i}.comp" for i in (2, 3))


def prepare(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if destination == source or source in destination.parents:
        raise ValueError("GGML candidate must be outside the original runtime")
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != REVISION:
        raise ValueError("GGML source revision differs from the pin")
    if destination.exists():
        raise FileExistsError("use a fresh GGML candidate directory")
    patch = Path(__file__).with_name("patches") / "ggml-vulkan-softmax.patch"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".pixal-ggml-", dir=destination.parent) as temporary:
        root = Path(temporary)
        archive = root / "source.tar"
        subprocess.run(["git", "-C", str(source), "archive", "--format=tar", "--output", str(archive), REVISION], check=True)
        stage = root / "source"
        stage.mkdir()
        with tarfile.open(archive) as stream:
            stream.extractall(stage, filter="data")
        original = {name: hashlib.sha256((stage / name).read_bytes()).hexdigest() for name in FILES}
        subprocess.run(["git", "apply", "--check", str(patch)], cwd=stage, check=True)
        subprocess.run(["git", "apply", str(patch)], cwd=stage, check=True)
        manifest = {
            "source_revision": REVISION,
            "source_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
            "original_sha256": original,
            "patched_sha256": {name: hashlib.sha256((stage / name).read_bytes()).hexdigest() for name in FILES},
            "gpu_executed": False,
        }
        (stage / "mediaforge-patch-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        stage.rename(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source, args.destination)
