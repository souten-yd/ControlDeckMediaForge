# SPDX-License-Identifier: GPL-3.0-or-later
"""Repair only tiny gaps in a successful upright character heat binding."""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

Point = tuple[float, float, float]
Weights = dict[int, float]
Nearest = Callable[[Point], Sequence[tuple[int, float]]]


def plan(points: list[Point], edges: list[tuple[int, int]], weights: list[Weights],
         nearest: Nearest) -> tuple[dict[int, Weights], dict[str, int | float]]:
    """Plan from original donors; do not mutate weights or propagate repairs."""
    missing = {i for i, value in enumerate(weights) if not value}
    if not missing:
        return {}, {"repaired_vertices": 0}
    if len(points) != len(weights) or len(missing) > min(128, len(points) * .005):
        raise RuntimeError("automatic skin weight repair exceeds vertex budget")
    height = max(p[2] for p in points) - min(p[2] for p in points)
    if not math.isfinite(height) or height <= 0:
        raise RuntimeError("automatic skin weight repair needs finite height")
    adjacent: dict[int, list[int]] = {i: [] for i in missing}
    for a, b in edges:
        if a in missing and b in missing:
            adjacent[a].append(b)
            adjacent[b].append(a)
    unseen = set(missing)
    components = 0
    while unseen:
        pending = [min(unseen)]
        island = []
        while pending:
            index = pending.pop()
            if index not in unseen:
                continue
            unseen.remove(index)
            island.append(index)
            pending.extend(adjacent[index])
        span = math.sqrt(sum((max(points[i][k] for i in island)
                              - min(points[i][k] for i in island)) ** 2 for k in range(3)))
        if len(island) > 64 or not math.isfinite(span) or span > height * .02:
            raise RuntimeError("automatic skin weight repair island is too large")
        components += 1
    repairs: dict[int, Weights] = {}
    maximum_distance = 0.
    for index in sorted(missing):
        donors = sorted(nearest(points[index]), key=lambda pair: (pair[1], pair[0]))[:3]
        donors = [(i, distance) for i, distance in donors
                  if math.isfinite(distance) and 0 <= distance <= height * .005]
        if not donors or any(i in missing or not 0 <= i < len(weights) for i, _ in donors):
            raise RuntimeError("automatic skin weight repair has no close original donor")
        maximum_distance = max(maximum_distance, max(distance for _, distance in donors))
        values: Weights = {}
        factors = [1 / max(distance, height * 1e-8) ** 2 for _, distance in donors]
        denominator = sum(factors)
        for (donor, _), factor in zip(donors, factors, strict=True):
            if (not weights[donor] or any(not math.isfinite(w) or w <= 0 for w in weights[donor].values())
                    or abs(sum(weights[donor].values()) - 1) > 1e-5):
                raise RuntimeError("automatic skin weight repair donor is invalid")
            for group, weight in weights[donor].items():
                values[group] = values.get(group, 0.) + weight * factor / denominator
        kept = sorted(values.items(), key=lambda pair: (-pair[1], pair[0]))[:4]
        total = sum(weight for _, weight in kept)
        repairs[index] = {group: weight / total for group, weight in kept}
    return repairs, {"repaired_vertices": len(repairs), "components": components,
                     "max_donor_distance_m": maximum_distance,
                     "distance_limit_m": height * .005, "body_height_m": height}


def for_mesh(mesh: Any, weights: list[Weights]) -> tuple[dict[int, Weights], dict[str, int | float]]:
    # Blender stays in the worker. The planner can be checked without bpy.
    from mathutils.kdtree import KDTree

    points = [tuple(mesh.matrix_world @ vertex.co) for vertex in mesh.data.vertices]
    original = [i for i, value in enumerate(weights) if value]
    if not original:
        raise RuntimeError("automatic skin weights are missing")
    tree = KDTree(len(original))
    for index in original:
        tree.insert(points[index], index)
    tree.balance()

    def nearest(point: Point) -> list[tuple[int, float]]:
        return [(index, distance) for _, index, distance in tree.find_n(point, min(3, len(original)))]

    return plan(points, [tuple(edge.vertices) for edge in mesh.data.edges], weights, nearest)
