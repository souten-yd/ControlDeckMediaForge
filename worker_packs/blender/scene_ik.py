# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed two-bone IK, baked to the existing rotation-only clip contract."""
from __future__ import annotations

import json
import math
from typing import Any, Callable


def bake(rig: Any, operation: dict[str, Any], objects: dict[str, Any], check_rig: Callable[...,None], create_clip: Callable[...,None]) -> None:
    import bpy
    from mathutils import Matrix, Vector
    check_rig(rig,allow_animation=True)
    if rig.parent or any(not math.isfinite(rig.matrix_world[i][j]) or abs(rig.matrix_world[i][j]-(i==j))>1e-6 for i in range(4) for j in range(4)):
        raise RuntimeError('IK bake requires an identity typed rig')
    end=operation.get('frame_count');keys=operation.get('targets')
    if type(end) is not int or not 1<=end<=120 or not isinstance(keys,list) or not 2<=len(keys)<=121:
        raise RuntimeError('IK bake sample bounds differ')
    lower=rig.pose.bones.get(operation.get('lower_bone_id',''));upper=rig.pose.bones.get(operation.get('upper_bone_id',''))
    if lower is None or upper is None or lower.parent!=upper or not lower.bone.use_deform or not upper.bone.use_deform:
        raise RuntimeError('IK requires a known parent-child deform chain')
    if (lower.bone.head_local-upper.bone.tail_local).length>1e-5:
        raise RuntimeError('IK requires coincident joint endpoints')
    parsed=[];last=-1
    for item in keys:
        frame=item.get('frame');values=[]
        for name in ('target','pole'):
            row=item.get(name)
            if not isinstance(row,(list,tuple)) or len(row)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>10000 for v in row):
                raise RuntimeError('IK target coordinates differ')
            values.append(Vector(row))
        if type(frame) is not int or not last<frame<=end:raise RuntimeError('IK frames differ')
        parsed.append((frame,*values));last=frame
    if parsed[0][0]!=0 or parsed[-1][0]!=end:raise RuntimeError('IK endpoint frames differ')
    loop=operation.get('loop',False)
    if type(loop) is not bool or (loop and (parsed[0][1]!=parsed[-1][1] or parsed[0][2]!=parsed[-1][2])):
        raise RuntimeError('IK loop targets differ')
    angle=operation.get('pole_angle_degrees',0)
    if type(angle) not in (int,float) or not math.isfinite(angle) or abs(angle)>180:raise RuntimeError('IK pole angle differs')
    # Validate all interpolated samples before creating constraints or scene objects.
    samples=[];cursor=0;origin=upper.bone.head_local;lengths=(upper.bone.length,lower.bone.length)
    for frame in range(end+1):
        while cursor+1<len(parsed)-1 and frame>parsed[cursor+1][0]:cursor+=1
        a,b=parsed[cursor:cursor+2];factor=(frame-a[0])/(b[0]-a[0]);target=a[1].lerp(b[1],factor);pole=a[2].lerp(b[2],factor)
        direction=target-origin;distance=direction.length
        if not abs(lengths[0]-lengths[1])+1e-4<distance<sum(lengths)-1e-4:
            raise RuntimeError('IK target is unreachable or singular')
        if direction.cross(pole-origin).length<1e-5:raise RuntimeError('IK pole is singular')
        samples.append((frame,target,pole))
    if rig.animation_data and rig.animation_data.drivers:raise RuntimeError('IK drivers are unsupported')
    if rig.animation_data:
        if any(not track.mute for track in rig.animation_data.nla_tracks):raise RuntimeError('IK requires muted clip stashes')
        rig.animation_data.action=None
    for pose in rig.pose.bones:pose.matrix_basis=Matrix.Identity(4)
    # A perfectly straight chain is a solver singularity even for reachable targets.
    # A fixed small knee seed initializes the solver; the target/pole define the result.
    lower.rotation_mode='XYZ';lower.rotation_euler=(.1,0,0)
    target_obj=bpy.data.objects.new('MF temporary IK target',None);pole_obj=bpy.data.objects.new('MF temporary IK pole',None)
    bpy.context.collection.objects.link(target_obj);bpy.context.collection.objects.link(pole_obj)
    constraint=lower.constraints.new('IK');constraint.target=target_obj;constraint.pole_target=pole_obj
    constraint.chain_count=2;constraint.use_stretch=False;constraint.iterations=64;constraint.pole_angle=math.radians(angle)
    tracks={upper.name:[],lower.name:[]};max_error=0.
    try:
        for frame,target,pole in samples:
            bpy.context.scene.frame_set(frame);target_obj.location=target;pole_obj.location=pole;bpy.context.view_layer.update()
            evaluated=rig.evaluated_get(bpy.context.evaluated_depsgraph_get())
            error=(evaluated.pose.bones[lower.name].tail-target).length;max_error=max(error,max_error)
            if not math.isfinite(error) or error>.01:raise RuntimeError('IK solve misses target tolerance')
            for pose in (upper,lower):
                solved=evaluated.pose.bones[pose.name];kwargs={}
                if solved.parent:kwargs={'parent_matrix':solved.parent.matrix,'parent_matrix_local':pose.parent.bone.matrix_local}
                local=pose.bone.convert_local_to_pose(solved.matrix,pose.bone.matrix_local,invert=True,**kwargs)
                location,rotation,scale=local.decompose()
                if location.length>1e-5 or any(abs(s-1)>1e-5 for s in scale):raise RuntimeError('IK result cannot be represented as rotation')
                degrees=[math.degrees(v) for v in rotation.to_euler('XYZ')]
                if any(not math.isfinite(v) or abs(v)>180 for v in degrees):raise RuntimeError('IK rotation differs')
                tracks[pose.name].append({'frame':frame,'rotation_degrees':degrees})
    finally:
        lower.constraints.remove(constraint);bpy.data.objects.remove(target_obj,do_unlink=True);bpy.data.objects.remove(pole_obj,do_unlink=True)
    if loop:
        for values in tracks.values():
            if any(abs(a-b)>1e-3 for a,b in zip(values[0]['rotation_degrees'],values[-1]['rotation_degrees'])):
                raise RuntimeError('IK loop solution endpoints differ')
            values[-1]['rotation_degrees']=values[0]['rotation_degrees'][:]
    clip={key:operation[key] for key in ('object_id','clip_id','name','frame_count')}
    clip.update(type='animation.clip',fps=operation.get('fps',24),loop=loop,replace=operation.get('replace',False),tracks=[{'bone_id':key,'keys':values} for key,values in tracks.items()])
    create_clip(rig,clip,objects)
    # Verify the exported representation rather than accepting the solver alone.
    for frame,target,_ in samples:
        bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
        error=(rig.evaluated_get(bpy.context.evaluated_depsgraph_get()).pose.bones[lower.name].tail-target).length
        if not math.isfinite(error) or error>.01:raise RuntimeError('baked IK clip misses target tolerance')
        max_error=max(max_error,error)
    rig.animation_data.action['media_forge_ik_audit']=json.dumps({'samples':len(samples),'max_target_error_m':max_error,'constraints_remaining':0},sort_keys=True)
    bpy.context.scene.frame_set(0)
