#!/usr/bin/env python3
"""Check the pinned softmax against a stable F64 reference at the Vulkan boundary.

GPU use requires the caller's genuine Host lease. No model inference or adoption.
Optionally include captured finite score rows from a failed trained HR forward.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--backend", choices=("cpu", "vulkan"), default="cpu")
    parser.add_argument("--device-index", type=int)
    parser.add_argument("--captured-rows", type=Path)
    args = parser.parse_args()
    if (args.backend == "vulkan") != (args.device_index is not None):
        parser.error("Vulkan requires an explicit device index")
    import numpy as np

    binary = args.binary.resolve(strict=True)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    generator = np.random.default_rng(91231)
    cases = []
    for columns in (1024, 16384, 16385, 18000, 32769, 49152):
        # Move the maximum across every 512-column tile. A reducer that keeps
        # reusing each lane's original maximum misses many of these positions.
        rows = (columns+511)//512
        scores = generator.uniform(-8, 8, (rows, columns)).astype("<f4")
        cases.append((str(columns)+"_diffuse", scores.copy(), None))
        for row in range(rows):
            scores[row, row*512] = 2000
        cases.append((str(columns), scores, None))
        if columns > 16384:
            cases.append((str(columns)+"_sink", scores, 170.0))
    if args.captured_rows:
        captured = np.load(args.captured_rows, allow_pickle=False)
        if captured.dtype != np.float32 or captured.ndim != 2 or not np.isfinite(captured).all():
            parser.error("captured scores must be a finite F32 matrix")
        cases.append(("captured_hr", captured, None))
    reports = []
    for name, scores, sink in cases:
        directory = args.output_dir/name
        directory.mkdir()
        np.save(directory/"input.npy", scores, allow_pickle=False)
        command = [str(binary), str((directory/"input.npy").resolve()),
                   str((directory/"output.npy").resolve()), args.backend,
                   str(args.device_index if args.device_index is not None else -1)]
        if sink is not None:
            np.save(directory/"sink.npy", np.array([sink], dtype="<f4"), allow_pickle=False)
            command.append(str((directory/"sink.npy").resolve()))
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        (directory/"native.log").write_text(result.stdout+result.stderr)
        scaled = scores.astype(np.float64)*float(np.float32(1/np.sqrt(128)))
        maximum = scaled.max(axis=1, keepdims=True)
        if sink is not None:
            maximum = np.maximum(maximum, sink)
        numerator = np.exp(scaled-maximum)
        denominator = numerator.sum(axis=1, keepdims=True)
        if sink is not None:
            denominator += np.exp(sink-maximum)
        expected = numerator/denominator
        report = {"case": name, "returncode": result.returncode, "passed": False}
        if (directory/"output.npy").is_file():
            actual = np.load(directory/"output.npy", allow_pickle=False)
            finite = bool(np.isfinite(actual).all())
            shape = actual.shape == expected.shape
            report.update(nonfinite=int((~np.isfinite(actual)).sum()),
                          max_abs_error=float(np.max(np.abs(actual-expected))) if finite and shape else None,
                          passed=result.returncode == 0 and shape and finite and
                          bool(np.allclose(actual, expected, atol=5e-5, rtol=5e-5)))
        reports.append(report)
    value = {"backend": args.backend, "device_index": args.device_index,
             "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
             "atol": 5e-5, "rtol": 5e-5, "cases": reports,
             "passed": all(item["passed"] for item in reports)}
    (args.output_dir/"report.json").write_text(json.dumps(value, indent=2)+"\n")
    print(json.dumps(value, indent=2))
    return 0 if value["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
