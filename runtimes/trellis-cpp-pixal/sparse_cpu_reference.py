"""Install pinned FlexGEMM's own Torch reference into Pixal's conv dispatcher.

Only the reference's EXPLICIT_GEMM and Torch neighbor-cache branches execute.
AST extraction avoids importing GPU-only Triton autotuning on a CPU machine;
neither the neural decoder nor its convolution implementation is rewritten.
This helper is an evaluation adapter, never a production fallback.
"""
from __future__ import annotations

import ast
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import typing

FLEX_REVISION = "6dd94a859c26ee8246888502eada3dd8ad85532e"


def install(pixal_source: Path, flex_source: Path) -> dict[str, Any]:
    import torch
    from pixal3d.modules.sparse import SparseTensor
    from pixal3d.modules.sparse.conv import conv, config

    if conv.config.CONV != "none":
        raise ValueError("CPU reference requires SPARSE_CONV_BACKEND=none before import")
    names = ("EXPLICIT_GEMM", "IMPLICIT_GEMM", "IMPLICIT_GEMM_SPLITK", "MASKED_IMPLICIT_GEMM", "MASKED_IMPLICIT_GEMM_SPLITK")
    algorithm = SimpleNamespace(**{name: name.lower() for name in names})
    namespace = {**vars(typing), "torch": torch, "Function": torch.autograd.Function,
                 "Algorithm": algorithm, "spconv": SimpleNamespace(ALGORITHM="explicit_gemm")}
    source = flex_source / "flex_gemm/ops/spconv/submanifold_conv3d.py"
    nodes = [n for n in ast.parse(source.read_text()).body if isinstance(n, ast.ClassDef)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    implementation = namespace["SubMConv3dFunction"]

    def cpu_conv(feats: Any, coords: Any, shape: Any, weight: Any, bias: Any, cache: Any, dilation: Any) -> tuple[Any, Any]:
        if feats.device.type != "cpu":
            raise ValueError("reference adapter is CPU-only")
        if cache is None:
            cache = implementation._compute_neighbor_cache_torch(coords, shape, weight.shape[1:4], dilation)
        return implementation._sparse_submanifold_conv_forward(feats, cache, weight, bias), cache

    # These configuration setters normally select GPU kernels. The extracted
    # reference above explicitly selects its Torch GEMM branch instead.
    def unused_setting(_value: Any) -> None:
        pass

    adapter = pixal_source / "pixal3d/modules/sparse/conv/conv_flex_gemm.py"
    namespace = {"torch": torch, "nn": torch.nn, "math": math, "SparseTensor": SparseTensor,
                 "config": config, "sparse_submanifold_conv3d": cpu_conv,
                 "flex_gemm": SimpleNamespace(ops=SimpleNamespace(spconv=SimpleNamespace(
                     set_algorithm=unused_setting, set_hashmap_ratio=unused_setting)))}
    nodes = [n for n in ast.parse(adapter.read_text()).body if isinstance(n, ast.FunctionDef)]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(adapter), "exec"), namespace)
    conv._backends["none"] = SimpleNamespace(**{k: v for k, v in namespace.items() if k.startswith("sparse_")})
    return {"conv": cpu_conv, "sources": [source, adapter]}
