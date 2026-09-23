"""Conservative upright-body measurements for the existing typed rig operations."""
from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

Point = tuple[float, float, float]
PlanePoint = tuple[float, float]
Clusterer = Callable[[list[PlanePoint], float, int], list[list[PlanePoint]]]


def _mean(points: list[Point]) -> Point:
    return tuple(sum(p[k] for p in points) / len(points) for k in range(3))  # type: ignore[return-value]


def measure(points: list[Point], feet: list[list[PlanePoint]], cell: float,
            cluster: Clusterer) -> dict[str, Any] | None:
    """Require two feet and three separated components in multiple torso bands.

    Only the canonical upright X-lateral frame is recognized. A crouched,
    rotated or arm-less shape continues through the existing general path.
    Sampling height bands, rather than vertex-rank quantiles, prevents dense
    hands and cuffs from moving a knee up into the torso.
    """
    if len(feet) != 2:
        return None
    bottom, top = min(p[2] for p in points), max(p[2] for p in points)
    height = top - bottom
    width = max(p[0] for p in points) - min(p[0] for p in points)
    if height <= width * 1.4:
        return None
    foot_centres = sorted((sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g)) for g in feet)
    separation = foot_centres[1][0] - foot_centres[0][0]
    if separation < height * .08 or abs(foot_centres[1][1] - foot_centres[0][1]) > separation * .3:
        return None
    centre_x = (foot_centres[0][0] + foot_centres[1][0]) / 2
    sections = []
    # Scan across the waist: simplification removes flat-face vertices but
    # leaves different neighbouring bands intact on different meshes.
    for level_percent in range(42, 59, 2):
        level = level_percent / 100
        band = [p for p in points if abs(p[2] - (bottom + height * level)) <= height * .0125]
        groups = cluster([(p[0], p[1]) for p in band], cell, max(4, int(len(band) * .01)))
        if len(groups) != 3:
            continue
        groups.sort(key=lambda g: sum(p[0] for p in g) / len(g))
        left, body, right = groups
        left_edge, right_edge = min(p[0] for p in body), max(p[0] for p in body)
        if (abs((left_edge + right_edge) / 2 - centre_x) > height * .05
                or right_edge - left_edge < height * .09
                or left_edge - max(p[0] for p in left) < cell * .5
                or min(p[0] for p in right) - right_edge < cell * .5):
            continue
        sections.append((left_edge, right_edge, sum(p[1] for p in body) / len(body)))
    if len(sections) < 2:
        return None
    body_half = sum((right - left) / 2 for left, right, _ in sections) / len(sections)
    centre_y = sum(y for _, _, y in sections) / len(sections)

    def joint(level: float, side: int, *, arm: bool = False) -> Point | None:
        band = [p for p in points if abs(p[2] - (bottom + height * level)) <= height * .015
                and (p[0] - centre_x) * side > (body_half if arm else 0)
                and (arm or abs(p[0] - centre_x) <= body_half * 1.05)]
        return _mean(band) if len(band) >= 8 else None

    legs, arms = [], []
    for index, side in enumerate((-1, 1), 1):
        hip, knee, foot = (joint(level, side) for level in (.48, .26, .04))
        # Wide shoes can extend beyond the waist. They are not hand tips.
        outside = [p for p in points if (p[0] - centre_x) * side > body_half * 1.35
                   and bottom + height * .30 < p[2] < bottom + height * .72]
        if not outside or any(p is None for p in (hip, knee, foot)):
            return None
        ordered = sorted(outside, key=lambda p: p[2])
        hand_tip = _mean(ordered[:max(8, len(ordered) // 30)])
        wrist_level = (hand_tip[2] - bottom) / height + .05
        elbow_level = (wrist_level + .73) / 2
        wrist, elbow = joint(wrist_level, side, arm=True), joint(elbow_level, side, arm=True)
        if wrist is None or elbow is None or not .35 < wrist_level < .53:
            return None
        shoulder = (centre_x + side * body_half * .8, centre_y, bottom + height * .73)
        legs.append({'name': f'leg{index}', 'hip': hip, 'knee': knee, 'foot': foot})
        arms.append({'name': f'arm{index}', 'shoulder': shoulder, 'elbow': elbow,
                     'wrist': wrist, 'hand': hand_tip})
    head_points = [p for p in points if p[2] >= bottom + height * .9
                   and abs(p[0] - centre_x) < body_half]
    if len(head_points) < 8:
        return None
    return {'body_plan': 'humanoid', 'centre': (centre_x, centre_y),
            'body_bottom': bottom + height * .48, 'body_top': bottom + height * .80,
            'body_radius': body_half, 'height': height, 'legs': legs, 'arms': arms,
            'head': _mean(head_points), 'extras': []}


def bones(facts: dict[str, Any]) -> list[dict[str, Any]]:
    x, y = facts['centre']
    result = [{'bone_id': 'head', 'head': [x, y, facts['body_top']],
               'tail': list(facts['head']), 'parent_bone_id': 'root'}]
    for arm in facts['arms']:
        name = arm['name']
        for suffix, start, end, parent in (
            ('upper', 'shoulder', 'elbow', 'root'),
            ('lower', 'elbow', 'wrist', name + '_upper'),
            ('hand', 'wrist', 'hand', name + '_lower'),
        ):
            result.append({'bone_id': name + '_' + suffix, 'head': list(arm[start]),
                           'tail': list(arm[end]), 'parent_bone_id': parent})
    return result


def walk_tracks(facts: dict[str, Any], frame_count: int) -> list[dict[str, Any]]:
    tracks = []
    for index, leg in enumerate(facts['legs']):
        phase = index * .5
        values = {leg['name'] + '_upper': [], leg['name'] + '_lower': [],
                  facts['arms'][index]['name'] + '_upper': []}
        for step in range(5):
            swing = math.sin((step / 4 + phase) * 2 * math.pi)
            angles = (-18 * swing, 25 * max(0., swing), 12 * swing)
            for keys, angle in zip(values.values(), angles, strict=True):
                keys.append({'frame': round(frame_count * step / 4),
                             'rotation_degrees': [round(angle, 2), 0., 0.]})
        tracks.extend({'bone_id': name, 'keys': keys} for name, keys in values.items())
    return tracks
