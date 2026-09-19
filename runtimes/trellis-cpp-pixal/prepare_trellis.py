#!/usr/bin/env python3
"""Materialize a pinned, patched DiT source copy without changing trellis.cpp."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

REVISION = "2516c48b677050c570f47eba2e68dc8a5bc918b0"
FILES = ("include/dit.h", "src/dit.cpp")


def prepare(source: Path, destination: Path) -> None:
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if destination == source or source in destination.parents:
        raise ValueError("patched source must be outside the original runtime checkout")
    actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if actual != REVISION:
        raise ValueError("trellis.cpp source revision differs from the pinned revision")
    patch = Path(__file__).with_name("patches") / "projected-dit.patch"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".pixal-dit-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "source"
        stage.mkdir()
        original = {}
        for name in FILES:
            content = subprocess.check_output(["git", "-C", str(source), "show", f"{REVISION}:{name}"])
            path = stage / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(content)
            original[name] = hashlib.sha256(content).hexdigest()
        subprocess.run(["git", "apply", "--check", str(patch)], cwd=stage, check=True)
        subprocess.run(["git", "apply", str(patch)], cwd=stage, check=True)
        manifest = {
            "source_revision": REVISION,
            "patch_sha256": hashlib.sha256(patch.read_bytes()).hexdigest(),
            "original_sha256": original,
            "patched_sha256": {name: hashlib.sha256((stage / name).read_bytes()).hexdigest() for name in FILES},
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        if destination.exists():
            for name in (*FILES, "manifest.json"):
                if (destination / name).read_bytes() != (stage / name).read_bytes():
                    raise ValueError("existing patched-source directory differs; use a fresh build directory")
        else:
            stage.rename(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    arguments = parser.parse_args()
    prepare(arguments.source, arguments.destination)
