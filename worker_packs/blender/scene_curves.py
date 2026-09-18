# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted bounded curve expansion and local mesh operations. No core imports."""
from __future__ import annotations

import hashlib
import json
import math
import struct
from typing import Any

Vec = tuple[float, float, float]
MAX_VERTICES = 16_384


def vec(value: Any) -> Vec:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise RuntimeError("curve vector differs")
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or abs(x) > 10_000 for x in value):
        raise RuntimeError("curve vector exceeds bounds")
    return tuple(float(x) for x in value)


def add(a: Vec, b: Vec) -> Vec:
    return tuple(x+y for x,y in zip(a,b))


def sub(a: Vec, b: Vec) -> Vec:
    return tuple(x-y for x,y in zip(a,b))


def mul(a: Vec, s: float) -> Vec:
    return tuple(x*s for x in a)


def dot(a: Vec, b: Vec) -> float:
    return sum(x*y for x,y in zip(a,b))


def cross(a: Vec, b: Vec) -> Vec:
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def unit(a: Vec) -> Vec:
    length = math.sqrt(dot(a,a))
    if length < 1e-8:
        raise RuntimeError("curve frame collapsed")
    return mul(a,1/length)


def bounded_int(value: Any, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise RuntimeError("curve integer exceeds bounds")
    return value


def profile(operation: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(operation, dict):
        raise RuntimeError("curve profile differs")
    sections = operation.get("sections")
    if operation.get("type") == "mesh.sweep":
        path = operation.get("path_points")
        if not isinstance(path,list) or not 2 <= len(path) <= 32:
            raise RuntimeError("curve path exceeds bounds")
        sections = [{"center":point,"radii":operation.get("radii")} for point in path]
    if not isinstance(sections,list) or not 2 <= len(sections) <= 32:
        raise RuntimeError("curve section count exceeds bounds")
    clean = []
    for section in sections:
        if not isinstance(section,dict) or set(section) != {"center","radii"}:
            raise RuntimeError("curve section differs")
        center, radii = vec(section["center"]), section["radii"]
        if not isinstance(radii,(list,tuple)) or len(radii) != 2 or any(type(r) not in (int,float) or not math.isfinite(r) or not .001 <= r <= 100 for r in radii):
            raise RuntimeError("curve radii exceed bounds")
        if clean and dot(sub(center,clean[-1]["center"]),sub(center,clean[-1]["center"])) < 1e-8:
            raise RuntimeError("adjacent curve centers must be distinct")
        clean.append({"center":center,"radii":tuple(float(r) for r in radii)})
    radial = bounded_int(operation.get("radial_segments",16),8,32)
    samples = bounded_int(operation.get("samples_per_segment",3),1,8)
    caps = operation.get("caps","both")
    if caps not in ("both","start","end","none") or type(operation.get("smooth",True)) is not bool:
        raise RuntimeError("curve cap or shading differs")
    up = unit(vec(operation.get("up",[0,0,1])))
    if ((len(clean)-1)*samples+1)*radial+2 > MAX_VERTICES:
        raise RuntimeError("curve vertex budget exceeded")
    return {"sections":clean,"radial_segments":radial,"samples_per_segment":samples,
            "caps":caps,"up":up,"smooth":operation.get("smooth",True)}


def geometry(operation: dict[str, Any]) -> tuple[list[Vec], list[list[int]], dict[str, Any]]:
    spec = profile(operation)
    sections, radial, samples = spec["sections"], spec["radial_segments"], spec["samples_per_segment"]
    centers, radii = [], []
    for i in range(len(sections)-1):
        p1,p2 = sections[i]["center"],sections[i+1]["center"]
        p0 = sections[i-1]["center"] if i else sub(mul(p1,2),p2)
        p3 = sections[i+2]["center"] if i+2 < len(sections) else sub(mul(p2,2),p1)
        for step in range(samples):
            t = step/samples
            centers.append(tuple(.5*((2*p1[k])+(-p0[k]+p2[k])*t+(2*p0[k]-5*p1[k]+4*p2[k]-p3[k])*t*t+(-p0[k]+3*p1[k]-3*p2[k]+p3[k])*t*t*t) for k in range(3)))
            radii.append(tuple((1-t)*a+t*b for a,b in zip(sections[i]["radii"],sections[i+1]["radii"])))
    centers.append(sections[-1]["center"]); radii.append(sections[-1]["radii"])
    vertices, faces = [], []
    previous_u, previous_t = None, None
    for i,(center,radius) in enumerate(zip(centers,radii)):
        tangent = unit(sub(centers[min(i+1,len(centers)-1)],centers[max(i-1,0)]))
        if previous_t is not None and dot(previous_t,tangent) < -.95:
            raise RuntimeError("curve reverses direction too sharply")
        if previous_u is None:
            up = spec["up"]
            if abs(dot(up,tangent)) > .99:
                up = min(((1.,0.,0.),(0.,1.,0.),(0.,0.,1.)),key=lambda axis:abs(dot(axis,tangent)))
            u = unit(cross(up,tangent))
        else:
            u = unit(sub(previous_u,mul(tangent,dot(previous_u,tangent))))
        v = cross(tangent,u)
        for j in range(radial):
            angle = 2*math.pi*j/radial
            point = add(center,add(mul(u,math.cos(angle)*radius[0]),mul(v,math.sin(angle)*radius[1])))
            # Validate the coordinates at Blender's float precision before allocation.
            vertices.append(struct.unpack("<3f",struct.pack("<3f",*point)))
        previous_u,previous_t = u,tangent
    for i in range(len(centers)-1):
        for j in range(radial):
            n = (j+1)%radial
            faces.append([i*radial+j,i*radial+n,(i+1)*radial+n,(i+1)*radial+j])
    for end,enabled in ((0,spec["caps"] in ("both","start")),(len(centers)-1,spec["caps"] in ("both","end"))):
        if enabled:
            index = len(vertices); vertices.append(struct.unpack("<3f",struct.pack("<3f",*centers[end])))
            for j in range(radial):
                a,b = end*radial+j,end*radial+(j+1)%radial
                faces.append([index,b,a] if end == 0 else [index,a,b])
    validate_faces(vertices,faces)
    return vertices,faces,spec


def validate_faces(vertices: list[Any], faces: list[list[int]]) -> None:
    for face in faces:
        for i in range(1,len(face)-1):
            a,b,c = (tuple(vertices[n]) for n in (face[0],face[i],face[i+1]))
            normal = cross(sub(b,a),sub(c,a))
            if dot(normal,normal) < 1e-20:
                raise RuntimeError("curve has degenerate faces")


def mesh_hash(mesh: Any) -> str:
    if len(mesh.vertices) > MAX_VERTICES or len(mesh.polygons) > 32768:
        raise RuntimeError("editable mesh exceeds bounds")
    digest = hashlib.sha256(struct.pack("<2I",len(mesh.vertices),len(mesh.polygons)))
    for vertex in mesh.vertices:
        digest.update(struct.pack("<3f",*vertex.co))
    for face in mesh.polygons:
        digest.update(struct.pack("<I",len(face.vertices)))
        for index in face.vertices:
            digest.update(struct.pack("<I",index))
    return digest.hexdigest()


def edge_uses(mesh: Any) -> dict[tuple[int,int], list[tuple[int,int]]]:
    edges: dict[tuple[int,int], list[tuple[int,int]]] = {}
    for polygon in mesh.polygons:
        face = list(polygon.vertices)
        for a,b in zip(face,face[1:]+face[:1]):
            edges.setdefault(tuple(sorted((a,b))),[]).append((a,b))
    return edges


def mesh_fact(obj: Any) -> dict[str, Any]:
    edges = edge_uses(obj.data)
    directed = [uses[0] for uses in edges.values() if len(uses)==1]
    pending = set(directed); loops = []
    while pending and len(loops) < 16:
        a,b = min(pending); loop = [a]; pending.remove((a,b))
        while b != loop[0] and len(loop) <= 64:
            loop.append(b)
            choices = sorted(edge for edge in pending if edge[0] == b)
            if len(choices) != 1:
                break
            a,b = choices[0]; pending.remove((a,b))
        if b == loop[0] and 3 <= len(loop) <= 64:
            loops.append(loop)
    fact = {"object_id":obj["media_forge_id"],"geometry_sha256":mesh_hash(obj.data),
            "vertices":len(obj.data.vertices),"triangles":sum(len(p.vertices)-2 for p in obj.data.polygons),
            "boundary_edges":len(directed),"nonmanifold_edges":sum(len(u)>2 for u in edges.values()),
            "inconsistent_edges":sum(len(u)==2 and u[0] != u[1][::-1] for u in edges.values()),
            "boundary_loops":loops}
    raw = obj.get("media_forge_curve")
    if isinstance(raw,str) and len(raw) <= 16384:
        try:
            spec = profile(json.loads(raw))
            if obj.get("media_forge_curve_sha256") == fact["geometry_sha256"]:
                fact["curve"] = spec
        except (ValueError,TypeError,RuntimeError):
            pass  # Stale/non-procedural source remains editable only through other operations.
    return fact


def set_sections(obj: Any, operation: dict[str, Any]) -> None:
    if obj.type != "MESH" or obj.data.users != 1 or obj.data.shape_keys or obj.data.animation_data:
        raise RuntimeError("sections require independent static mesh data")
    actual = mesh_hash(obj.data)
    if operation.get("expected_geometry_sha256") != actual or obj.get("media_forge_curve_sha256") != actual:
        raise RuntimeError("geometry selection is stale")
    raw = obj.get("media_forge_curve")
    if not isinstance(raw,str) or len(raw)>16384:
        raise RuntimeError("procedural sections are unavailable")
    spec = profile(json.loads(raw))
    new = operation.get("sections")
    if not isinstance(new,list) or len(new) != len(spec["sections"]):
        raise RuntimeError("section edit must preserve control count")
    vertices,faces,spec = geometry({**spec,"sections":new})
    if len(vertices) != len(obj.data.vertices) or faces != [list(p.vertices) for p in obj.data.polygons]:
        raise RuntimeError("section edit changed topology")
    for vertex,point in zip(obj.data.vertices,vertices):
        vertex.co = point
    obj.data.update()
    obj["media_forge_curve"] = json.dumps(spec,separators=(",",":"))
    obj["media_forge_curve_sha256"] = mesh_hash(obj.data)


def bridge(obj: Any, other: Any, operation: dict[str, Any]) -> None:
    import bpy
    from mathutils import Vector
    for mesh in (obj,other):
        if mesh is None or mesh.type != "MESH" or mesh.data.users != 1 or mesh.parent or mesh.constraints or mesh.animation_data or mesh.vertex_groups or mesh.modifiers or mesh.data.shape_keys or mesh.data.animation_data:
            raise RuntimeError("bridge requires independent unweighted static meshes without modifiers")
        allowed = {"position", ".edge_verts", ".corner_vert", ".corner_edge", "material_index", "sharp_face", ".select_vert", ".select_edge", ".select_poly"}
        allowed.update(layer.name for layer in mesh.data.uv_layers)
        if mesh.data.color_attributes or any(attribute.name not in allowed for attribute in mesh.data.attributes):
            raise RuntimeError("bridge cannot preserve unsupported mesh attributes")
        if mesh.matrix_world.determinant() <= 1e-9:
            raise RuntimeError("bridge transform is singular or reflected")
    if obj is other or mesh_hash(obj.data) != operation.get("expected_geometry_sha256") or mesh_hash(other.data) != operation.get("other_geometry_sha256"):
        raise RuntimeError("geometry selection is stale")
    loops = []
    for mesh,key in ((obj,"boundary"),(other,"other_boundary")):
        loop = operation.get(key)
        if not isinstance(loop,list) or not 3 <= len(loop) <= 64 or any(type(i) is not int or not 0 <= i < len(mesh.data.vertices) for i in loop) or len(set(loop)) != len(loop):
            raise RuntimeError("bridge loop indices differ")
        edges = edge_uses(mesh.data)
        uses = [edges.get(tuple(sorted((a,b))),[]) for a,b in zip(loop,loop[1:]+loop[:1])]
        if any(len(u)!=1 for u in uses):
            raise RuntimeError("bridge selection is not a boundary")
        orientation = [u[0]==(a,b) for u,a,b in zip(uses,loop,loop[1:]+loop[:1])]
        if len(set(orientation)) != 1:
            raise RuntimeError("bridge boundary winding differs")
        loops.append(loop if orientation[0] else list(reversed(loop)))
    a,b = loops[0],list(reversed(loops[1]))
    if len(a) != len(b):
        raise RuntimeError("bridge loop counts differ")
    twist = bounded_int(operation.get("twist_offset",0),-63,63)
    transform = obj.matrix_world.inverted() @ other.matrix_world
    vertices = [tuple(v.co) for v in obj.data.vertices]+[tuple(transform@v.co) for v in other.data.vertices]
    if len(vertices)>MAX_VERTICES:
        raise RuntimeError("bridge vertex budget exceeded")
    offset = len(obj.data.vertices)
    shift = min(range(len(b)),key=lambda n:sum((Vector(vertices[x])-Vector(vertices[offset+b[(i+n)%len(b)]])).length_squared for i,x in enumerate(a)))
    shift = (shift+twist)%len(b); b = b[shift:]+b[:shift]
    faces = [list(p.vertices) for p in obj.data.polygons]+[[offset+i for i in p.vertices] for p in other.data.polygons]
    bridge_faces = [[a[(i+1)%len(a)],a[i],offset+b[i],offset+b[(i+1)%len(b)]] for i in range(len(a))]
    validate_faces(vertices,bridge_faces); faces.extend(bridge_faces)
    if len(faces)>32768:
        raise RuntimeError("bridge face budget exceeded")
    data = bpy.data.meshes.new("Media Forge joined mesh")
    data.from_pydata(vertices,[],faces)
    if data.validate():
        bpy.data.meshes.remove(data); raise RuntimeError("bridge mesh required repair")
    materials = list(obj.data.materials)
    for material in other.data.materials:
        if material not in materials:
            materials.append(material)
    for material in materials:
        data.materials.append(material)
    target_index = 0
    for source in (obj.data,other.data):
        for polygon in source.polygons:
            target = data.polygons[target_index]; target_index += 1
            target.use_smooth = polygon.use_smooth
            if source.materials:
                target.material_index = materials.index(source.materials[polygon.material_index])
    for polygon in data.polygons[target_index:]:
        polygon.use_smooth = True
    for name in sorted({layer.name for mesh in (obj.data,other.data) for layer in mesh.uv_layers}):
        target = data.uv_layers.new(name=name); loop_offset = 0
        for source in (obj.data,other.data):
            layer = source.uv_layers.get(name)
            if layer:
                for i,uv in enumerate(layer.data):
                    target.data[loop_offset+i].uv = uv.uv
            loop_offset += len(source.loops)
        # New joint UVs need an explicit unwrap; zero is intentional, not UV acceptance.
    old,consumed = obj.data,other.data
    obj.data = data
    for key in ("media_forge_curve","media_forge_curve_sha256"):
        if key in obj: del obj[key]
    bpy.data.objects.remove(other,do_unlink=True)
    bpy.data.meshes.remove(old); bpy.data.meshes.remove(consumed)
    data.update()
