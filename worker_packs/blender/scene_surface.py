# SPDX-License-Identifier: GPL-3.0-or-later
"""Trusted bounded UV operations; no external paths or scripts are accepted."""
from __future__ import annotations

import hashlib
import math
import struct
from typing import Any

import scene_curves


def uv_facts(mesh: Any) -> list[dict[str, Any]]:
    facts=[]
    for layer in list(mesh.uv_layers)[:8]:
        values=[tuple(item.uv) for item in layer.data]
        finite=all(math.isfinite(x) for uv in values for x in uv)
        digest=hashlib.sha256()
        for uv in values:digest.update(struct.pack('<2f',*uv))
        degenerate=0
        if finite:
            for polygon in mesh.polygons:
                indices=list(polygon.loop_indices)
                for i in range(1,len(indices)-1):
                    a,b,c=[values[j] for j in (indices[0],indices[i],indices[i+1])]
                    area=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
                    degenerate+=abs(area)<1e-12
        facts.append({'name':layer.name,'uv_sha256':digest.hexdigest(),'loops':len(values),'finite':finite,
            'degenerate_triangles':degenerate if finite else None,
            'bounds_min':[min(v[i] for v in values) for i in range(2)] if values and finite else None,
            'bounds_max':[max(v[i] for v in values) for i in range(2)] if values and finite else None})
    return facts


def apply_uv(obj: Any, operation: dict[str, Any]) -> None:
    import bpy
    if obj.type!='MESH' or obj.data.users!=1:
        raise RuntimeError('UV operation requires independent mesh data')
    if scene_curves.mesh_hash(obj.data)!=operation.get('expected_geometry_sha256'):
        raise RuntimeError('geometry selection is stale')
    kind=operation.get('type')
    if kind=='uv.seams.set':
        selected=operation.get('edges')
        if not isinstance(selected,list) or not 1<=len(selected)<=4096:
            raise RuntimeError('seam selection exceeds bounds')
        edges={tuple(sorted(edge.vertices)):edge for edge in obj.data.edges}
        identities=[]
        for pair in selected:
            if not isinstance(pair,(list,tuple)) or len(pair)!=2 or any(type(i) is not int or not 0<=i<len(obj.data.vertices) for i in pair):
                raise RuntimeError('seam edge indices differ')
            identity=tuple(sorted(pair))
            if identity not in edges or identity in identities:
                raise RuntimeError('seam edge is absent or duplicated')
            identities.append(identity)
        if type(operation.get('mark',True)) is not bool or type(operation.get('clear_existing',False)) is not bool:
            raise RuntimeError('seam flags differ')
        if operation.get('clear_existing',False):
            for edge in obj.data.edges:edge.use_seam=False
        for identity in identities:edges[identity].use_seam=operation.get('mark',True)
        return
    margin=operation.get('margin',.02)
    if type(margin) not in (int,float) or not math.isfinite(margin) or not .001<=margin<=.25:
        raise RuntimeError('UV margin exceeds bounds')
    if kind=='uv.pack':
        if obj.data.uv_layers.active is None or type(operation.get('rotate',True)) is not bool:
            raise RuntimeError('UV pack requires a map and valid rotation flag')
        values=[tuple(item.uv) for item in obj.data.uv_layers.active.data]
        if not values or not all(math.isfinite(x) for uv in values for x in uv):
            raise RuntimeError('UV coordinates are unavailable')
        lo=[min(v[i] for v in values) for i in range(2)]
        span=max(1.,*(max(v[i] for v in values)-lo[i] for i in range(2)))
        for item in obj.data.uv_layers.active.data:item.uv=tuple((item.uv[i]-lo[i])/span for i in range(2))
    elif kind!='uv.unwrap' or operation.get('method','ANGLE_BASED') not in ('ANGLE_BASED','CONFORMAL'):
        raise RuntimeError('UV operation differs')
    bpy.ops.object.select_all(action='DESELECT');obj.select_set(True);bpy.context.view_layer.objects.active=obj
    bpy.ops.object.mode_set(mode='EDIT')
    try:
        bpy.ops.mesh.select_all(action='SELECT')
        if kind=='uv.unwrap':bpy.ops.uv.unwrap(method=operation.get('method','ANGLE_BASED'),margin=margin)
        else:bpy.ops.uv.select_all(action='SELECT');bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM',rotate=operation.get('rotate',True),margin_method='FRACTION',margin=margin)
    finally:bpy.ops.object.mode_set(mode='OBJECT')
    facts=next((item for item in uv_facts(obj.data) if item['name']==obj.data.uv_layers.active.name),None)
    if facts is None or not facts['finite'] or facts['bounds_min'] is None or min(facts['bounds_min']) < -1e-5 or max(facts['bounds_max'])>1.00001:
        raise RuntimeError('UV result lies outside the unit tile')


def apply_scale(obj: Any, operation: dict[str, Any]) -> None:
    if (obj.type!='MESH' or obj.data.users!=1 or obj.parent or obj.children or obj.constraints or obj.animation_data
            or obj.data.shape_keys or obj.data.animation_data or obj.vertex_groups
            or any(modifier.type!='SUBSURF' for modifier in obj.modifiers)):
        raise RuntimeError('scale apply requires an independent static unweighted mesh')
    if scene_curves.mesh_hash(obj.data)!=operation.get('expected_geometry_sha256'):
        raise RuntimeError('geometry selection is stale')
    scale=tuple(obj.scale)
    if any(not math.isfinite(x) or not 0<x<=1000 for x in scale):
        raise RuntimeError('scale apply requires positive bounded scale')
    for vertex in obj.data.vertices:
        if any(not math.isfinite(vertex.co[i]*scale[i]) or abs(vertex.co[i]*scale[i])>10000 for i in range(3)):
            raise RuntimeError('scaled coordinates exceed bounds')
    for vertex in obj.data.vertices:vertex.co=tuple(vertex.co[i]*scale[i] for i in range(3))
    obj.scale=(1,1,1);obj.data.update()
