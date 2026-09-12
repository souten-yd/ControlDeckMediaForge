"""Worker-local immutable input transport, not signature verification or setup.

Only a dedicated native worker may protect itself and own these descriptors.
Inputs must already be trusted by the caller. Keep the context/holder alive
until the consumer terminates; closing our fd does not revoke another process's
copy. Neither function installs a package, launches code or authorizes anything.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from dataclasses import dataclass
import errno
import fcntl
import os
from typing import Iterator

MAX_INPUT_BYTES = 8 * 1024 * 1024
SEALS = fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE


@dataclass(frozen=True)
class SealedInput:
    # Borrowed descriptor: caller must not close/replace it or publish the path
    # to a browser. pass_fds is only for a specifically trusted native consumer.
    descriptor: int
    proc_path: str
    size_bytes: int


def protect_native_holder() -> None:
    """Opt this dedicated worker out of ordinary same-user inspection.

    Run only in a fresh dedicated worker, never core or a shared test process.
    Root access and explicitly inherited fds are not prevented by this setting.
    The trusted holder must not re-enable dumpability or exec another program.
    """
    libc = ctypes.CDLL(None, use_errno=True)
    prctl = libc.prctl
    prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    prctl.restype = ctypes.c_int
    if prctl(4, 0, 0, 0, 0) != 0 or prctl(3, 0, 0, 0, 0) != 0:
        raise OSError(errno.EPERM, "native holder protection unavailable")


@contextmanager
def hold_immutable_input(data: bytes) -> Iterator[SealedInput]:
    """Seal bounded immutable bytes and own exactly one CLOEXEC descriptor.

    No paths, shell fragments, URLs or publisher keys are accepted. This layer
    does not decide whether bytes are trusted; callers must verify before use.
    A protected holder's proc_path requires a sufficiently privileged reader.
    """
    if type(data) is not bytes or not 0 < len(data) <= MAX_INPUT_BYTES:
        raise ValueError("native input must be bounded immutable bytes")
    descriptor = os.memfd_create("mediaforge-native-input", os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        remaining = memoryview(data)
        while remaining:
            written = os.write(descriptor, remaining[:65536])
            if written <= 0:
                raise OSError(errno.EIO, "native input write failed")
            remaining = remaining[written:]
        fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, SEALS)
        if fcntl.fcntl(descriptor, fcntl.F_GET_SEALS) & SEALS != SEALS:
            raise OSError(errno.EPERM, "native input seals unavailable")
        os.lseek(descriptor, 0, os.SEEK_SET)
        yield SealedInput(descriptor, f"/proc/{os.getpid()}/fd/{descriptor}", len(data))
    finally:
        os.close(descriptor)
