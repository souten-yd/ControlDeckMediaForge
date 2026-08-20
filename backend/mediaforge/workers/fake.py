from __future__ import annotations

import hashlib
import json
import struct
import sys
import time
import zlib
from pathlib import Path


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
        output_path.write_bytes(
            _png(width, height, hashlib.sha256(f"{request['intent']}:{seed}:{index}".encode()).digest())
        )
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
        "postprocessing": [],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
