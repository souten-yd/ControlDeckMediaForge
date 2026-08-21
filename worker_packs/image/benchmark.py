from __future__ import annotations

import argparse
import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from .adapters import DiffusersFlux2KleinAdapter, ImageGenerationRequest


class GpuMemoryMonitor:
    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.baseline_used_bytes = 0
        self.peak_used_bytes = 0
        self.total_bytes = 0

    def __enter__(self) -> "GpuMemoryMonitor":
        import torch

        free, total = torch.cuda.mem_get_info(0)
        self.total_bytes = int(total)
        self.baseline_used_bytes = int(total - free)
        self.peak_used_bytes = self.baseline_used_bytes

        def sample() -> None:
            while not self._stop.wait(0.01):
                free_now, total_now = torch.cuda.mem_get_info(0)
                self.peak_used_bytes = max(self.peak_used_bytes, int(total_now - free_now))

        self._thread = threading.Thread(target=sample, name="gpu-memory-monitor", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)

    def result(self) -> dict[str, int]:
        return {
            "baseline_used_bytes": self.baseline_used_bytes,
            "peak_used_bytes": self.peak_used_bytes,
            "incremental_peak_bytes": max(0, self.peak_used_bytes - self.baseline_used_bytes),
            "total_bytes": self.total_bytes,
        }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-path", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--steps", type=int, default=4)
    parser.add_argument("--seed", type=int, default=12345)
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--prompt", default="A small red robot reading a paper map, clean studio illustration")
    args = parser.parse_args()
    if not 256 <= args.width <= 2048 or not 256 <= args.height <= 2048 or not 1 <= args.steps <= 50:
        raise SystemExit("benchmark dimensions or steps are outside the bounded range")
    if not 1 <= args.repeat <= 10:
        raise SystemExit("benchmark repeat must be 1..10")

    import diffusers
    import torch
    import transformers

    adapter = DiffusersFlux2KleinAdapter(args.model_path)
    torch.cuda.reset_peak_memory_stats(0)
    with GpuMemoryMonitor() as load_memory:
        adapter.load()
    resident_free, resident_total = torch.cuda.mem_get_info(0)
    records: list[dict[str, Any]] = []
    for index in range(args.repeat):
        output = args.output_dir / f"benchmark-{args.width}x{args.height}-{args.steps}-{index}.png"
        torch.cuda.reset_peak_memory_stats(0)
        with GpuMemoryMonitor() as execution_memory:
            started = time.perf_counter()
            adapter.generate(ImageGenerationRequest(
                prompt=args.prompt,
                width=args.width,
                height=args.height,
                steps=args.steps,
                seed=args.seed,
                output_path=output,
            ))
            torch.cuda.synchronize()
            elapsed = time.perf_counter() - started
        records.append({
            "index": index,
            "elapsed_sec": elapsed,
            "output_bytes": output.stat().st_size,
            "output_sha256": sha256(output),
            "torch_peak_allocated_bytes": int(torch.cuda.max_memory_allocated(0)),
            "device_memory": execution_memory.result(),
        })
    payload = {
        "model_path": str(args.model_path.resolve()),
        "torch_version": torch.__version__,
        "hip_version": torch.version.hip,
        "diffusers_version": diffusers.__version__,
        "transformers_version": transformers.__version__,
        "device_name": torch.cuda.get_device_name(0),
        "gcn_arch": getattr(torch.cuda.get_device_properties(0), "gcnArchName", "unknown"),
        "load_sec": adapter.load_sec,
        "load_memory": load_memory.result(),
        "resident_used_bytes": int(resident_total - resident_free),
        "width": args.width,
        "height": args.height,
        "steps": args.steps,
        "seed": args.seed,
        "records": records,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
