from __future__ import annotations

from pathlib import Path


def contained(root: Path, candidate: Path) -> Path:
    resolved_root = root.resolve()
    resolved = candidate.resolve()
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError("path escapes the configured data directory")
    return resolved
