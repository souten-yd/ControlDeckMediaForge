from __future__ import annotations

import ctypes
import hashlib
import io
import json
import os
import signal
import struct
import sys
import time
import zlib
from pathlib import Path

from PIL import Image

from mediaforge.image_edit import compose_strict_edit, editable_mask


def _terminate_with_parent() -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))
    if os.getppid() == 1:
        raise RuntimeError("worker parent exited during startup")


def _chunk(kind: bytes, data: bytes) -> bytes:
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _png(width: int, height: int, digest: bytes) -> bytes:
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            block = ((x // 32) + (y // 32)) % 2
            base = digest[(x + y) % len(digest)]
            row.extend(((digest[0] + block * 35) % 256, (digest[1] + base // 3) % 256, digest[2], 255))
        rows.append(bytes(row))
    raw = zlib.compress(b"".join(rows), level=9)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", raw)
        + _chunk(b"IEND", b"")
    )


def main() -> int:
    _terminate_with_parent()
    request = json.loads(sys.stdin.buffer.read(1024 * 1024))
    constraints = request.get("constraints", {})
    delay = float(constraints.get("_fake_delay_sec", 0))
    if delay:
        time.sleep(min(delay, 10))
    if constraints.get("_fake_crash"):
        return 19
    if request.get("output", {}).get("format", "png") != "png":
        print(json.dumps({"error": {"code": "unsupported_output_format", "message": "fake worker emits PNG only"}}))
        return 2
    width = int(constraints.get("width", 256))
    height = int(constraints.get("height", 256))
    if not 1 <= width <= 2048 or not 1 <= height <= 2048:
        print(json.dumps({"error": {"code": "invalid_dimensions", "message": "fake dimensions must be 1..2048"}}))
        return 2
    digest = hashlib.sha256(request["intent"].encode("utf-8")).digest()
    seed = int(constraints.get("seed", int.from_bytes(digest[:4], "big")))
    output_dir = Path(request["worker_output_dir"])
    output_dir.mkdir(mode=0o700, parents=False, exist_ok=True)
    outputs = []
    for index in range(int(request.get("output", {}).get("count", 1))):
        output_path = output_dir / f"output-{index}.png"
        generated = _png(width, height, hashlib.sha256(f"{request['intent']}:{seed}:{index}".encode()).digest())
        if request.get("operation") == "image.edit" and constraints.get("strict_edit") is True:
            worker_inputs = request.get("worker_inputs", {})
            source_path = Path(worker_inputs["source_path"])
            mask_path = Path(worker_inputs["mask_path"])
            with Image.open(io.BytesIO(generated)) as patch:
                compose_strict_edit(source_path, mask_path, patch, output_path)
            if constraints.get("_fake_strict_violation") is True:
                mask = editable_mask(mask_path)
                with Image.open(output_path) as opened:
                    image = opened.convert("RGBA")
                protected = next(
                    (index for index, value in enumerate(mask.getdata()) if value == 0),
                    None,
                )
                if protected is not None:
                    x, y = protected % image.width, protected // image.width
                    original = image.getpixel((x, y))
                    image.putpixel((x, y), ((original[0] + 1) % 256, *original[1:]))
                    image.save(output_path, format="PNG")
        else:
            output_path.write_bytes(generated)
        outputs.append({"path": str(output_path), "mime_type": "image/png", "width": width, "height": height})
    print(json.dumps({
        "outputs": outputs,
        "model": {
            "id": "media-forge/fake-image",
            "version": "1.0.0",
            "weights_hash": "sha256:" + "0" * 64,
            "license": "CC0-1.0",
            "runtime_adapter": "fake-subprocess",
            "runtime_version": "1.0.0",
        },
        "seed": seed,
        "postprocessing": (
            ["strict_edit.mask_composite", "strict_edit.protected_pixel_copy"]
            if request.get("operation") == "image.edit" and constraints.get("strict_edit") is True
            else []
        ),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
