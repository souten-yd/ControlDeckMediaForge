"""Small durable generation marker for a freshly prepared managed candidate.

Call only from an owned worker thread. Creation is exclusive: never stamp over
an existing runtime generation to manufacture evidence of a repair.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import uuid

from .paths import contained

MARKER_NAME = ".publication-generation"


def _candidate(allowed_root: Path, root: Path) -> Path:
    if root.is_symlink():
        raise ValueError("Publication candidate must not be a symlink")
    return contained(allowed_root, root)


def create_generation(allowed_root: Path, root: Path) -> str:
    candidate = _candidate(allowed_root, root)
    relative = candidate.relative_to(allowed_root.resolve() / ".staging")
    if (len(relative.parts) != 2 or relative.parts[1] != "candidate"
            or not re.fullmatch(r"blenderop_[0-9a-f]{32}", relative.parts[0])):
        raise ValueError("Generation creation requires an operation staging candidate")
    if not candidate.is_dir():
        raise ValueError("Publication candidate directory is missing")
    generation = uuid.uuid4().hex
    descriptor = os.open(candidate / MARKER_NAME,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write((generation + "\n").encode("ascii"))
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(candidate, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    return generation


def read_generation(allowed_root: Path, root: Path) -> str | None:
    candidate = _candidate(allowed_root, root)
    try:
        descriptor = os.open(candidate / MARKER_NAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != 33:
            raise ValueError("Invalid publication generation marker")
        value = stream.read(34)
    if not re.fullmatch(rb"[0-9a-f]{32}\n", value):
        raise ValueError("Invalid publication generation value")
    return value[:-1].decode("ascii")
