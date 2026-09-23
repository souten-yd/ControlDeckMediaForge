"""Bounded measurements of actual triangle sections, without changing the mesh."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
import math

Point = tuple[float, float, float]
Triangle = tuple[int, int, int]
LEVELS = 128
MAX_TRIANGLES = 500_000
MAX_SEGMENTS = 2_000_000
MAX_POINTS = 200_000
MAX_SAMPLE_ATTEMPTS = 2_000_000


class SurfaceMeasurementError(ValueError):
    """The surface cannot be measured within the fixed geometry limits."""


def sample(vertices: Sequence[Point], triangles: Iterable[Triangle], spacing: float) -> list[Point]:
    """Sample horizontal triangle intersections on a scale-relative grid.

    Simplification can preserve the entire surface while removing every vertex
    from a joint band. These samples lie on existing triangle edges/sections;
    they do not add vertices, modify UVs, or infer missing limbs. Deduplication
    prevents triangle density from dominating measurements of neighbouring parts.
    """
    if not vertices or len(vertices) > 500_000 or not math.isfinite(spacing) or spacing <= 0:
        raise SurfaceMeasurementError("surface measurement requires finite geometry")
    if any(not all(math.isfinite(v) for v in p) for p in vertices):
        raise SurfaceMeasurementError("surface measurement requires finite geometry")
    bottom_point = min(vertices, key=lambda p: p[2])
    top_point = max(vertices, key=lambda p: p[2])
    bottom, top = bottom_point[2], top_point[2]
    step = (top - bottom) / LEVELS
    if not math.isfinite(step) or step <= 0:
        raise SurfaceMeasurementError("surface has no height")
    origin_x = min(p[0] for p in vertices)
    origin_y = min(p[1] for p in vertices)
    samples: dict[tuple[int, int, int], Point] = {}
    segments = 0
    attempts = 0
    for triangle_count, indices in enumerate(triangles, 1):
        if triangle_count > MAX_TRIANGLES:
            raise SurfaceMeasurementError("surface measurement triangle limit exceeded")
        if len(indices) != 3 or any(type(i) is not int or not 0 <= i < len(vertices) for i in indices):
            raise SurfaceMeasurementError("surface measurement triangle indices differ")
        a, b, c = (vertices[i] for i in indices)
        low, high = min(a[2], b[2], c[2]), max(a[2], b[2], c[2])
        first = max(0, math.ceil((low - bottom) / step - .5))
        end = min(LEVELS, math.ceil((high - bottom) / step - .5))
        for level in range(first, end):
            z = bottom + (level + .5) * step
            cuts: list[Point] = []
            for p, q in ((a, b), (b, c), (c, a)):
                # Half-open edges handle plane/vertex coincidences consistently.
                if (p[2] <= z < q[2]) or (q[2] <= z < p[2]):
                    t = (z - p[2]) / (q[2] - p[2])
                    cuts.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]), z))
            if len(cuts) != 2:
                continue
            segments += 1
            if segments > MAX_SEGMENTS:
                raise SurfaceMeasurementError("surface measurement section limit exceeded")
            p, q = cuts
            required = math.hypot(q[0] - p[0], q[1] - p[1]) / spacing
            if not math.isfinite(required) or required > MAX_POINTS:
                raise SurfaceMeasurementError("surface measurement point limit exceeded")
            count = max(1, math.ceil(required))
            attempts += count + 1
            if attempts > MAX_SAMPLE_ATTEMPTS:
                raise SurfaceMeasurementError("surface measurement sampling limit exceeded")
            for index in range(count + 1):
                t = index / count
                point = (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]), z)
                key = (level, math.floor((point[0] - origin_x) / spacing),
                       math.floor((point[1] - origin_y) / spacing))
                samples.setdefault(key, point)
                if len(samples) > MAX_POINTS - 2:
                    raise SurfaceMeasurementError("surface measurement point limit exceeded")
    return [bottom_point, top_point, *samples.values()]
