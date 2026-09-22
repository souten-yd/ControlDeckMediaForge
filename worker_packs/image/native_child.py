"""Exec a native child which cannot outlive its owning image worker (Linux)."""

from __future__ import annotations

import ctypes
import os
import signal
import sys


def main() -> int:
    if len(sys.argv) < 3:
        return 2
    owner_pid = int(sys.argv[1])
    # Set this in a fresh interpreter, avoiding preexec_fn in a threaded worker.
    # Linux preserves PDEATHSIG across exec of this ordinary, non-setuid binary.
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL) != 0:
        raise OSError(ctypes.get_errno(), "cannot bind native child lifetime")
    if os.getppid() != owner_pid:
        return 3
    os.execv(sys.argv[2], sys.argv[2:])
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
