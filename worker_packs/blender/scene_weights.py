# SPDX-License-Identifier: GPL-3.0-or-later
"""Bounded edits to an existing typed deform binding."""
from __future__ import annotations

import math
from typing import Any, Callable

import scene_curves


def normalized(values: dict[int, float]) -> dict[int, float]:
    if any(type(i) is not int or not math.isfinite(w) or not 0 <= w <= 1 for i,w in values.items()):
        raise RuntimeError('skin weights are invalid')
    kept=sorted(((i,w) for i,w in values.items() if w>0),key=lambda item:(-item[1],item[0]))[:4]
    total=sum(w for _,w in kept)
    if total<=0:raise RuntimeError('skin weights are missing')
    return {i:w/total for i,w in kept}


def facts(mesh: Any) -> dict[str, Any] | None:
    modifiers=[m for m in mesh.modifiers if m.type=='ARMATURE']
    if not modifiers:return None
    rigs={m.object for m in modifiers if m.object is not None}
    if len(rigs)!=1:return None
    rig=next(iter(rigs))
    if rig.get('media_forge_rig_schema')!=1 or not isinstance(rig.get('media_forge_id'),str):return None
    known={g.index for g in mesh.vertex_groups if g.name in rig.data.bones}
    missing=invalid=0;maximum=0;error=0.
    for vertex in mesh.data.vertices:
        groups=[(g.group,g.weight) for g in vertex.groups]
        valid=all(i in known and math.isfinite(w) and 0<=w<=1 for i,w in groups)
        positive=[w for _,w in groups if math.isfinite(w) and w>0]
        missing+=not positive;invalid+=not valid;maximum=max(maximum,len(positive))
        error=max(error,abs(sum(positive)-1))
    return {'rig_object_id':rig.get('media_forge_id'),'vertices':len(mesh.data.vertices),
        'unweighted_vertices':missing,'invalid_vertices':invalid,'max_influences':maximum,'max_sum_error':error}


def apply(mesh: Any, operation: dict[str, Any], objects: dict[str, Any], check_rig: Callable[..., None]) -> None:
    rig=objects.get(operation.get('rig_object_id'))
    if rig is None:raise RuntimeError('weight rig is unavailable')
    check_rig(rig,allow_animation=True)
    if (mesh.type!='MESH' or mesh.data.users!=1 or mesh.parent!=rig or mesh.parent_type!='OBJECT'
            or mesh.constraints or mesh.animation_data or mesh.data.shape_keys or mesh.data.animation_data):
        raise RuntimeError('weight target must have an independent typed binding')
    modifiers=list(mesh.modifiers)
    if (not modifiers or modifiers[0].type!='ARMATURE' or modifiers[0].object!=rig
            or any(m.type!='SUBSURF' for m in modifiers[1:])
            or not modifiers[0].use_vertex_groups or modifiers[0].use_bone_envelopes):
        raise RuntimeError('weight modifier stack differs')
    if scene_curves.mesh_hash(mesh.data)!=operation.get('expected_geometry_sha256'):
        raise RuntimeError('geometry selection is stale')
    if not 1<=len(mesh.data.vertices)<=16384 or len(mesh.data.edges)>65536:
        raise RuntimeError('weight mesh exceeds bounds')
    selected=operation.get('vertex_indices')
    if (not isinstance(selected,list) or not 1<=len(selected)<=4096
            or any(type(i) is not int or not 0<=i<len(mesh.data.vertices) for i in selected)
            or len(set(selected))!=len(selected)):
        raise RuntimeError('weight vertex selection differs')
    groups={g.name:g for g in mesh.vertex_groups}
    if any(name not in rig.data.bones or not rig.data.bones[name].use_deform or group.lock_weight
           for name,group in groups.items()):
        raise RuntimeError('unknown or locked weight group')
    allowed={g.index for g in groups.values()}
    raw=[]
    for vertex in mesh.data.vertices:
        values={g.group:g.weight for g in vertex.groups}
        if any(i not in allowed or not math.isfinite(w) or not 0<=w<=1 for i,w in values.items()):
            raise RuntimeError('existing weights are invalid')
        raw.append(values)
    kind=operation.get('type')
    pending={}
    if kind=='skin.weights.set':
        rows=operation.get('influences')
        if not isinstance(rows,list) or not 1<=len(rows)<=4:raise RuntimeError('weight influences exceed bounds')
        names={}
        for row in rows:
            name,weight=row.get('bone_id'),row.get('weight')
            if (name not in rig.data.bones or not rig.data.bones[name].use_deform or name in names
                    or type(weight) not in (int,float) or not math.isfinite(weight) or not 0<weight<=1):
                raise RuntimeError('weight influence differs')
            names[name]=weight
        if abs(sum(names.values())-1)>1e-5:raise RuntimeError('explicit weights must sum to one')
        # Group creation follows every selection/input preflight check.
        for name in names:
            if name not in groups:groups[name]=mesh.vertex_groups.new(name=name)
        pending={i:normalized({groups[name].index:w for name,w in names.items()}) for i in selected}
    elif kind=='skin.weights.normalize':
        pending={i:normalized(raw[i]) for i in selected}
    elif kind=='skin.weights.smooth':
        iterations=operation.get('iterations',1);factor=operation.get('factor',.5)
        if (type(iterations) is not int or not 1<=iterations<=8 or type(factor) not in (int,float)
                or not math.isfinite(factor) or not 0<factor<=1):raise RuntimeError('weight smooth bounds differ')
        neighbors={i:set() for i in selected}
        for edge in mesh.data.edges:
            a,b=edge.vertices
            if a in neighbors:neighbors[a].add(b)
            if b in neighbors:neighbors[b].add(a)
        needed=set(selected).union(*(neighbors[i] for i in selected))
        values={i:normalized(raw[i]) for i in needed}
        for _ in range(iterations):
            pending={}
            for i in selected:
                adjacent=neighbors[i]
                if not adjacent:pending[i]=values[i];continue
                result={g:w*(1-factor) for g,w in values[i].items()}
                for j in adjacent:
                    for g,w in values[j].items():result[g]=result.get(g,0)+factor*w/len(adjacent)
                pending[i]=normalized(result)
            values.update(pending)
    else:raise RuntimeError('unknown weight operation')
    for i,values in pending.items():
        for group in list(mesh.data.vertices[i].groups):mesh.vertex_groups[group.group].remove([i])
        for index,weight in values.items():mesh.vertex_groups[index].add([i],weight,'REPLACE')
    # Require the entire resulting binding, including untouched vertices, to pass.
    audit=facts(mesh)
    if (audit is None or audit['unweighted_vertices'] or audit['invalid_vertices']
            or audit['max_influences']>4 or audit['max_sum_error']>=1e-5):
        raise RuntimeError('resulting skin weights need further correction')
