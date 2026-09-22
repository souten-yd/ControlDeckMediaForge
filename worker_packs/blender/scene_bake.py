# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed CPU tangent-normal / target-only AO bake. Inputs are private fixed files."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
import scene_curves
import scene_surface
from scene_observation import validate_scene_objects


def validate_spec(value: object) -> dict:
    required={'object_id','geometry_sha256','high_object_id','high_geometry_sha256','uv_map','channels','resolution','margin_px','cage_extrusion_m'}
    if not isinstance(value,dict) or set(value)!=required:
        raise RuntimeError('bake specification differs')
    for key in ('object_id','high_object_id'):
        item=value[key]
        if key=='high_object_id' and item is None:continue
        if not isinstance(item,str) or re.fullmatch(r'[a-z][a-z0-9._-]{0,63}',item) is None:raise RuntimeError('bake object ID differs')
    for key in ('geometry_sha256','high_geometry_sha256'):
        item=value[key]
        if key=='high_geometry_sha256' and value['high_object_id'] is None and item is None:continue
        if not isinstance(item,str) or re.fullmatch(r'[a-f0-9]{64}',item) is None:raise RuntimeError('bake geometry hash differs')
    if not isinstance(value['uv_map'],str) or not 1<=len(value['uv_map'])<=64 or re.search(r'[\x00-\x1f/\\]',value['uv_map']):
        raise RuntimeError('bake UV name differs')
    channels=value['channels']
    if not isinstance(channels,list) or not 1<=len(channels)<=2 or len(set(channels))!=len(channels) or any(c not in ('normal','ao') for c in channels):
        raise RuntimeError('bake channels differ')
    if 'normal' in channels and value['high_object_id'] is None:raise RuntimeError('normal bake requires high source')
    if type(value['resolution']) is not int or value['resolution'] not in (256,512,1024):raise RuntimeError('bake resolution differs')
    scene_curves.bounded_int(value['margin_px'],1,32)
    cage=value['cage_extrusion_m']
    if type(cage) not in (int,float) or not math.isfinite(cage) or not 0<=cage<=1:raise RuntimeError('bake cage exceeds bound')
    return value


def target(objects: list, key: str, digest: str, *, low: bool) -> bpy.types.Object:
    matches=[obj for obj in objects if obj.get('media_forge_id')==key]
    if len(matches)!=1 or matches[0].type!='MESH':raise RuntimeError('bake mesh is unavailable or ambiguous')
    obj=matches[0]
    if scene_curves.mesh_hash(obj.data)!=digest:raise RuntimeError('bake geometry selection is stale')
    if obj.parent or obj.constraints or obj.animation_data or obj.data.shape_keys or obj.data.animation_data:
        raise RuntimeError('bake requires static independent meshes')
    if any(abs(scale-1)>1e-5 for scale in obj.scale) or obj.matrix_world.determinant()<=0:
        raise RuntimeError('bake requires unit positive object scale')
    if low and obj.modifiers:raise RuntimeError('low bake target must be an unmodified mesh')
    if any(m.type=='ARMATURE' for m in obj.modifiers):raise RuntimeError('bake before skin binding')
    return obj


def main() -> None:
    parser=argparse.ArgumentParser();parser.add_argument('--expected-version',required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    if bpy.app.version_string.split()[0]!=args.expected_version:raise RuntimeError('bake runtime differs')
    spec=validate_spec(json.loads(Path('bake.json').read_text()))
    bpy.context.preferences.filepaths.use_scripts_auto_execute=False
    bpy.ops.wm.open_mainfile(filepath=str(Path('source.blend').resolve()),load_ui=False,use_scripts=False)
    scene=bpy.context.scene;scene.frame_set(0)
    low_objects=list(bpy.data.objects);validate_scene_objects(low_objects)
    low=target(low_objects,spec['object_id'],spec['geometry_sha256'],low=True)
    high=None;high_objects=[]
    if spec['high_object_id'] is not None:
        with bpy.data.libraries.load(str(Path('high.blend').resolve()),link=False) as (source,destination):
            if len(source.objects)>1024:raise RuntimeError('high scene object budget exceeded')
            destination.objects=source.objects
        high_objects=[obj for obj in destination.objects if obj is not None]
        for obj in high_objects:scene.collection.objects.link(obj)
        validate_scene_objects(low_objects+high_objects)
        high=target(high_objects,spec['high_object_id'],spec['high_geometry_sha256'],low=False)
    uv=low.data.uv_layers.get(spec['uv_map'])
    if uv is None:raise RuntimeError('bake UV map is unavailable')
    low.data.uv_layers.active_index=list(low.data.uv_layers).index(uv);uv.active_render=True
    uv_fact=next(item for item in scene_surface.uv_facts(low.data) if item['name']==uv.name)
    # UV が面積ゼロの三角形を少数含むのは、面を削った結果として普通に起きる
    # （実測: 24,900 三角形のうち 1 つ）。その三角形にテクセルが乗らないだけで
    # 他の面には影響しないので、全体を断る理由にはならない。壊れた UV
    # （ほとんどが潰れている）は今までどおり断る。
    triangles=sum(max(0,len(polygon.vertices)-2) for polygon in low.data.polygons)
    degenerate_allowance=max(64,triangles//1000)
    if (not uv_fact['finite'] or uv_fact['degenerate_triangles'] is None
            or triangles <= 0 or uv_fact['degenerate_triangles']*2 >= triangles
            or uv_fact['degenerate_triangles']>degenerate_allowance
            or uv_fact['bounds_min'] is None or min(uv_fact['bounds_min']) < -1e-5
            or max(uv_fact['bounds_max'])>1.00001):
        raise RuntimeError('bake UV map must be finite, mostly nondegenerate and in the unit tile')
    for obj in low_objects+high_objects:
        obj.hide_render=obj not in (low,high);obj.hide_set(False)
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=16
    scene.render.threads_mode='FIXED';scene.render.threads=2
    scene.render.bake.use_clear=True;scene.render.bake.margin=spec['margin_px']
    # A temporary target material cannot create a read/write image feedback loop.
    material=bpy.data.materials.new('Media Forge bake target');material.use_nodes=True
    low.data.materials.clear();low.data.materials.append(material)
    for polygon in low.data.polygons:polygon.material_index=0
    node=material.node_tree.nodes.new('ShaderNodeTexImage');material.node_tree.nodes.active=node
    rows=[]
    for channel in spec['channels']:
        image=bpy.data.images.new('Media Forge bake image',width=spec['resolution'],height=spec['resolution'],alpha=True)
        image.generated_color=(0,0,0,0);image.colorspace_settings.name='Non-Color';node.image=image
        bpy.ops.object.select_all(action='DESELECT');low.select_set(True);bpy.context.view_layer.objects.active=low
        selected_to_active=channel=='normal'
        if high is not None:
            high.hide_render=not selected_to_active
            if selected_to_active:high.select_set(True)
        bpy.ops.object.bake(type='NORMAL' if selected_to_active else 'AO',use_selected_to_active=selected_to_active,
            cage_extrusion=spec['cage_extrusion_m'],normal_space='TANGENT',normal_r='POS_X',normal_g='POS_Y',normal_b='POS_Z',
            margin=spec['margin_px'],use_clear=True,target='IMAGE_TEXTURES')
        pixels=list(image.pixels)
        if not all(math.isfinite(v) for v in pixels):raise RuntimeError('bake produced non-finite pixels')
        covered=sum(alpha>=.5 for alpha in pixels[3::4])
        if covered==0:raise RuntimeError('bake produced no covered pixels')
        path=Path(f'{channel}.png');image.filepath_raw=str(path.resolve());image.file_format='PNG';image.save()
        rows.append({'channel':channel,'filename':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                     'nontransparent_pixels':covered,'color_space':'non_color','normal_convention':'open_gl' if channel=='normal' else None})
        node.image=None;bpy.data.images.remove(image)
    Path('result.json').write_text(json.dumps({'schema_version':'media-forge.scene-bake-result@1','blender_version':args.expected_version,
        'spec':spec,'device':'CPU','frame':0,'samples':16,'autoexec_disabled':not bpy.context.preferences.filepaths.use_scripts_auto_execute,
        'uv_triangle_count':triangles,'uv':uv_fact,'images':rows},sort_keys=True,separators=(',',':'))+'\n')


if __name__=='__main__':main()
