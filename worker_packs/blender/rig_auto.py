"""実形状を測って、脚のある模型に骨と歩行ループを組む。

骨の位置は当て推量では置けない。bone heat は、どの骨からも遠い頂点に重みを
付けられずに失敗するので、骨は「動かしたい所」だけでなく「頂点が届く所」にも
要る。ここは毎回モデルを測って、その模型の形から骨を置く。

出すのは `armature.create` / `skin.bind_auto` / `animation.clip` の operation 辞書
そのものである。新しい低水準の仕組みは作らない。同じ検査を通す。
"""

from __future__ import annotations

import math

import rig_humanoid
import rig_surface

# 測るのは形であって精度ではない。大きな模型でも 1 回の走査で足りる数に間引く。
MAX_SAMPLED_VERTICES = 200_000
# 脚の断面を数える水平帯の高さ（模型の高さに対する割合）と厚み。
LEG_BAND_HEIGHT = 0.12
LEG_BAND_THICKNESS = 0.05
# 触角などの突起を探す帯。
EXTRA_BAND_HEIGHT = 0.86
EXTRA_BAND_THICKNESS = 0.10
# 水平面を刻む格子の細かさ（水平方向の広がりに対する割合）。細かすぎると 1 本の
# 脚が複数に割れ、粗すぎると隣の脚と繋がる。
CLUSTER_CELL = 1.0 / 28.0
# 1 つの塊として認めるのに要る点の数（帯の点数に対する割合）。
MIN_CLUSTER_SHARE = 0.01
MAX_LEGS = 12
MAX_EXTRAS = 8
# 歩行の振れ幅（度）。upper は前後に振りつつ持ち上げ、lower はそれを追う。
SWING_DEGREES = 18.0
LIFT_DEGREES = -14.0
LOWER_LIFT_DEGREES = 22.0
LOWER_SWING_DEGREES = -6.0


class RigAutoError(RuntimeError):
    """測っても骨を置ける形が見つからなかった。"""


def _sampled_points(obj) -> list[tuple[float, float, float]]:
    matrix = obj.matrix_world
    vertices = obj.data.vertices
    stride = max(1, len(vertices) // MAX_SAMPLED_VERTICES)
    points = []
    for index in range(0, len(vertices), stride):
        world = matrix @ vertices[index].co
        points.append((world.x, world.y, world.z))
    return points


def _surface_points(obj, cell: float) -> list[tuple[float, float, float]]:
    obj.data.calc_loop_triangles()
    world = [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]
    try:
        return rig_surface.sample(
            [(p.x, p.y, p.z) for p in world],
            (tuple(tri.vertices) for tri in obj.data.loop_triangles), cell * .25)
    except rig_surface.SurfaceMeasurementError as exc:
        raise RigAutoError(str(exc)) from exc


def _clusters(points: list[tuple[float, float]], cell: float, minimum: int) -> list[list[tuple[float, float]]]:
    """水平面を格子に刻み、隣り合う升を繋げて塊にする。"""
    if cell <= 0:
        raise RigAutoError("model has no horizontal extent")
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for x, y in points:
        grid.setdefault((math.floor(x / cell), math.floor(y / cell)), []).append((x, y))
    seen: set[tuple[int, int]] = set()
    found = []
    for start in grid:
        if start in seen:
            continue
        stack = [start]
        members: list[tuple[float, float]] = []
        while stack:
            current = stack.pop()
            if current in seen or current not in grid:
                continue
            seen.add(current)
            members.extend(grid[current])
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    neighbour = (current[0] + dx, current[1] + dy)
                    if neighbour in grid and neighbour not in seen:
                        stack.append(neighbour)
        if len(members) >= minimum:
            found.append(members)
    return found


def _band(points, low, high):
    return [point for point in points if low <= point[2] <= high]


def _mean(values):
    count = len(values)
    return (
        sum(value[0] for value in values) / count,
        sum(value[1] for value in values) / count,
        sum(value[2] for value in values) / count,
    )


def _slice_mean(ordered, start, end):
    count = len(ordered)
    lower = max(0, min(count - 1, int(count * start)))
    upper = max(lower + 1, min(count, int(count * end)))
    return _mean(ordered[lower:upper])


def measure(obj) -> dict[str, object]:
    """模型を測り、胴の範囲・脚ごとの 3 点・突起を出す。"""
    if obj.type != "MESH" or not obj.data.vertices:
        raise RigAutoError("automatic rigging needs a mesh with vertices")
    points = _sampled_points(obj)
    zs = [point[2] for point in points]
    bottom, top = min(zs), max(zs)
    height = top - bottom
    if height <= 0:
        raise RigAutoError("model is flat; there is no up direction to rig along")
    centre_x = sum(point[0] for point in points) / len(points)
    centre_y = sum(point[1] for point in points) / len(points)
    spread = max(
        max(point[0] for point in points) - min(point[0] for point in points),
        max(point[1] for point in points) - min(point[1] for point in points),
    )
    cell = spread * CLUSTER_CELL

    band = _band(points, bottom + height * (LEG_BAND_HEIGHT - LEG_BAND_THICKNESS / 2),
                 bottom + height * (LEG_BAND_HEIGHT + LEG_BAND_THICKNESS / 2))
    used_surface = len(band) < 24
    if used_surface:
        # Decimation can remove every intermediate vertex from flat trousers.
        # Measure the remaining surface; keep the established dense-mesh path
        # byte-for-byte unchanged, including its bone/weight placement.
        points = _surface_points(obj, cell)
        bottom, top = min(p[2] for p in points), max(p[2] for p in points)
        height = top - bottom
        band = _band(points, bottom + height * (LEG_BAND_HEIGHT - LEG_BAND_THICKNESS / 2),
                     bottom + height * (LEG_BAND_HEIGHT + LEG_BAND_THICKNESS / 2))
        centre_x = sum(point[0] for point in points) / len(points)
        centre_y = sum(point[1] for point in points) / len(points)
    if len(band) < 24:
        raise RigAutoError(
            "too little surface crosses the horizontal band near the base"
        )
    groups = _clusters([(point[0], point[1]) for point in band], cell,
                       max(4, int(len(band) * MIN_CLUSTER_SHARE)))
    if len(groups) < 2:
        raise RigAutoError("fewer than two limbs were found; this model is not a legged shape")
    if len(groups) > MAX_LEGS:
        raise RigAutoError(f"found {len(groups)} limbs, more than automatic rigging handles")

    humanoid = rig_humanoid.measure(points, groups, cell, _clusters)
    if humanoid is None and len(groups) == 2 and height > spread * 1.4:
        # Close arms can share neighbouring coarse cells with the torso.
        # A finer grid alone splits sparse flat faces into false components;
        # first sample the actual surface, then repeat the same body guards.
        surface = points if used_surface else _surface_points(obj, cell)
        surface_bottom = min(p[2] for p in surface)
        surface_height = max(p[2] for p in surface) - surface_bottom
        feet_band = _band(surface,
                          surface_bottom + surface_height * (LEG_BAND_HEIGHT - LEG_BAND_THICKNESS / 2),
                          surface_bottom + surface_height * (LEG_BAND_HEIGHT + LEG_BAND_THICKNESS / 2))
        feet = _clusters([(p[0], p[1]) for p in feet_band], cell,
                         max(4, int(len(feet_band) * MIN_CLUSTER_SHARE)))
        humanoid = rig_humanoid.measure(surface, feet, cell * .75, _clusters)
    if humanoid is not None:
        return humanoid

    # 胴の太さは、上半分にある点の中央値の半径で見る。脚は下に伸びているので、
    # 上半分は胴だけで占められている。
    upper = [point for point in points if point[2] >= bottom + height * 0.55]
    radii = sorted(math.hypot(point[0] - centre_x, point[1] - centre_y) for point in upper)
    body_radius = radii[len(radii) // 2] if radii else spread / 4
    body_points = [
        point for point in points
        if math.hypot(point[0] - centre_x, point[1] - centre_y) <= body_radius
    ]
    body_bottom = min(point[2] for point in body_points) if body_points else bottom
    body_top = max(point[2] for point in body_points) if body_points else top

    bearings = sorted(
        math.atan2(sum(y for _, y in group) / len(group) - centre_y,
                   sum(x for x, _ in group) / len(group) - centre_x)
        for group in groups
    )
    half_sector = math.pi / len(bearings)
    legs = []
    for index, bearing in enumerate(bearings):
        sector = [
            point for point in points
            if abs((math.atan2(point[1] - centre_y, point[0] - centre_x) - bearing + math.pi)
                   % (2 * math.pi) - math.pi) <= half_sector
            and point[2] <= bottom + height * 0.6
        ]
        if len(sector) < 8:
            raise RigAutoError("a limb was found in the band but carries too little geometry to place bones")
        ordered = sorted(sector, key=lambda point: point[2])
        # 下から順に、足・膝・付け根。高さで 3 つに切って、それぞれの重心を使う。
        legs.append({
            "name": f"leg{index + 1}",
            "foot": _slice_mean(ordered, 0.0, 0.06),
            "knee": _slice_mean(ordered, 0.40, 0.55),
            "hip": _slice_mean(ordered, 0.88, 1.0),
            "bearing_degrees": round(math.degrees(bearing), 1),
        })

    extra_band = _band(points, bottom + height * (EXTRA_BAND_HEIGHT - EXTRA_BAND_THICKNESS / 2),
                       bottom + height * (EXTRA_BAND_HEIGHT + EXTRA_BAND_THICKNESS / 2))
    extras = []
    if len(extra_band) >= 24:
        for group in _clusters([(point[0], point[1]) for point in extra_band], cell,
                               max(4, int(len(extra_band) * MIN_CLUSTER_SHARE))):
            tip = max(group, key=lambda point: math.hypot(point[0] - centre_x, point[1] - centre_y))
            if math.hypot(tip[0] - centre_x, tip[1] - centre_y) <= body_radius:
                continue
            height_at_tip = max(
                point[2] for point in extra_band
                if abs(point[0] - tip[0]) < cell and abs(point[1] - tip[1]) < cell
            )
            extras.append((tip[0], tip[1], height_at_tip))
            if len(extras) >= MAX_EXTRAS:
                break

    return {
        "centre": (centre_x, centre_y),
        "body_bottom": body_bottom,
        "body_top": body_top,
        "body_radius": body_radius,
        "height": height,
        "legs": legs,
        "extras": extras,
    }


def armature_operation(facts: dict[str, object], rig_object_id: str, name: str) -> dict[str, object]:
    centre_x, centre_y = facts["centre"]
    body_bottom, body_top = facts["body_bottom"], facts["body_top"]
    # root は胴を下から上まで貫く。胴の頂点を覆う骨が無いと bone heat が解けない。
    bones = [{
        "bone_id": "root",
        "head": [centre_x, centre_y, body_bottom],
        "tail": [centre_x, centre_y, body_top],
    }]
    if facts.get("body_plan") == "humanoid":
        bones.extend(rig_humanoid.bones(facts))
    attachment = [centre_x, centre_y, body_bottom + (body_top - body_bottom) * 0.72]
    for index, tip in enumerate(facts["extras"]):
        bones.append({
            "bone_id": f"extra{index + 1}",
            "head": list(attachment),
            "tail": [tip[0], tip[1], tip[2]],
            "parent_bone_id": "root",
        })
    for leg in facts["legs"]:
        bones.append({
            "bone_id": f"{leg['name']}_upper",
            "head": list(leg["hip"]), "tail": list(leg["knee"]), "parent_bone_id": "root",
        })
        bones.append({
            "bone_id": f"{leg['name']}_lower",
            "head": list(leg["knee"]), "tail": list(leg["foot"]),
            "parent_bone_id": f"{leg['name']}_upper",
        })
    return {"type": "armature.create", "object_id": rig_object_id, "name": name, "bones": bones}


def walk_operation(
    facts: dict[str, object], rig_object_id: str, clip_id: str, fps: int, frame_count: int
) -> dict[str, object]:
    """隣り合う脚を半周期ずらす。6 本なら三脚歩行、4 本なら斜対歩になる。

    振れ幅の軸は、この operation が組んだ upper / lower の向きに合わせてある。
    手で置いた骨に当てると意図した向きに曲がらない。
    """
    tracks = []
    if facts.get("body_plan") == "humanoid":
        return {
            "type": "animation.clip", "object_id": rig_object_id, "clip_id": clip_id,
            "name": clip_id, "fps": fps, "frame_count": frame_count, "loop": True,
            "tracks": rig_humanoid.walk_tracks(facts, frame_count),
        }
    for index, leg in enumerate(facts["legs"]):
        phase = 0.0 if index % 2 == 0 else 0.5
        upper, lower = [], []
        for step in range(5):
            frame = round(frame_count * step / 4)
            position = (step / 4 + phase) % 1.0
            swing = math.sin(position * 2 * math.pi)
            lift = max(0.0, math.sin(position * 2 * math.pi))
            upper.append({"frame": frame, "rotation_degrees": [
                round(LIFT_DEGREES * lift, 2), 0.0, round(SWING_DEGREES * swing, 2)]})
            lower.append({"frame": frame, "rotation_degrees": [
                round(LOWER_LIFT_DEGREES * lift, 2), 0.0, round(LOWER_SWING_DEGREES * swing, 2)]})
        tracks.append({"bone_id": f"{leg['name']}_upper", "keys": upper})
        tracks.append({"bone_id": f"{leg['name']}_lower", "keys": lower})
    return {
        "type": "animation.clip", "object_id": rig_object_id, "clip_id": clip_id,
        "name": clip_id, "fps": fps, "frame_count": frame_count, "loop": True, "tracks": tracks,
    }
