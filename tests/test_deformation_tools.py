from __future__ import annotations

import json
from types import SimpleNamespace

import jsonschema
import pytest
from pydantic import ValidationError

from mediaforge.scene_recipes import SceneCreateRequest,IkLegBake
from test_game_static_operations import ROOT,request,worker


def weight(kind='set',**changes):
    result={'type':'skin.weights.'+kind,'object_id':'mesh','rig_object_id':'rig','expected_geometry_sha256':'a'*64,'vertex_indices':[0]}
    if kind=='set':result['influences']=[{'bone_id':'upper','weight':.3},{'bone_id':'lower','weight':.7}]
    return {**result,**changes}


def ik(**changes):
    return {'type':'ik.leg.bake','object_id':'rig','upper_bone_id':'upper','lower_bone_id':'lower','clip_id':'step','name':'Step','fps':24,'frame_count':24,'loop':True,
        'targets':[{'frame':0,'target':[0,.1,.2],'pole':[0,-1,1]},{'frame':24,'target':[0,.1,.2],'pole':[0,-1,1]}],**changes}


def test_published_deformation_contracts():
    recipe=request(weight(),weight('smooth'),weight('normalize'),ik())
    SceneCreateRequest.model_validate(recipe)
    for name,payload in [('scene-create-request.json',recipe),('scene-edit-request.json',{'scene_id':'scene_'+'a'*32,'base_revision_id':'revision_'+'b'*32,'recipe':recipe['recipe']}),('scene-workflow-request.json',{'action':'create',**recipe})]:
        jsonschema.validate(payload,json.loads((ROOT/'schemas'/name).read_text()))


@pytest.mark.parametrize('op',[
    weight(vertex_indices=[]),weight(vertex_indices=[1,1]),weight(vertex_indices=[True]),weight(vertex_indices=[16384]),
    weight(vertex_indices=list(range(4097))),weight(expected_geometry_sha256='old'),weight(rig_object_id='mesh'),
    weight(influences=[{'bone_id':'upper','weight':.2}]),weight(influences=[{'bone_id':'upper','weight':.5}]*2),
    weight(influences=[{'bone_id':'upper','weight':float('nan')}]),weight('smooth',iterations=9),weight('smooth',iterations=True),
    weight('smooth',factor=0),weight('smooth',factor=float('inf')),weight('normalize',python='pass'),
    ik(upper_bone_id='lower'),ik(frame_count=121),ik(fps=True),ik(loop='yes'),ik(pole_angle_degrees=float('nan')),
    ik(targets=[{'frame':0,'target':[0,0,0],'pole':[0,0,1]},{'frame':24,'target':[1,0,0],'pole':[0,0,1]}]),
])
def test_deformation_bounds(op):
    with pytest.raises(ValidationError):SceneCreateRequest.model_validate(request(op))


class Groups(list):
    def __init__(self,vertices):super().__init__();self.vertices=vertices
    def new(self,name):
        index=len(self);group=SimpleNamespace(index=index,name=name,lock_weight=False)
        def remove(indices):
            for i in indices:self.vertices[i].groups[:]=[g for g in self.vertices[i].groups if g.group!=index]
        def add(indices,value,mode):
            assert mode=='REPLACE';remove(indices)
            for i in indices:self.vertices[i].groups.append(SimpleNamespace(group=index,weight=value))
        group.remove=remove;group.add=add;self.append(group);return group


class Rig(SimpleNamespace):
    def get(self,key):return {'media_forge_id':'rig','media_forge_rig_schema':1}.get(key)
    __hash__=object.__hash__


def fixture(monkeypatch):
    module=worker(monkeypatch);vertices=[SimpleNamespace(index=i,co=(i,0,0),groups=[]) for i in range(3)]
    groups=Groups(vertices);groups.new('upper').add([0,1],1,'REPLACE');groups.new('lower').add([2],1,'REPLACE')
    rig=Rig(data=SimpleNamespace(bones={'upper':SimpleNamespace(use_deform=True),'lower':SimpleNamespace(use_deform=True)}))
    mesh=SimpleNamespace(type='MESH',parent=rig,parent_type='OBJECT',constraints=[],animation_data=None,vertex_groups=groups,
        modifiers=[SimpleNamespace(type='ARMATURE',object=rig,use_vertex_groups=True,use_bone_envelopes=False)],
        data=SimpleNamespace(users=1,shape_keys=None,animation_data=None,vertices=vertices,polygons=[],edges=[SimpleNamespace(vertices=(0,1)),SimpleNamespace(vertices=(1,2))]))
    operation=weight('smooth',vertex_indices=[1],factor=1,iterations=1,expected_geometry_sha256=module.scene_curves.mesh_hash(mesh.data))
    return module,mesh,rig,operation


def test_neighbor_smoothing_keeps_unselected_weights(monkeypatch):
    module,mesh,rig,op=fixture(monkeypatch)
    module.scene_weights.apply(mesh,op,{'rig':rig},lambda *a,**k:None)
    weights=lambda i:{g.group:g.weight for g in mesh.data.vertices[i].groups}
    assert weights(0)=={0:1} and weights(2)=={1:1} and weights(1)=={0:.5,1:.5}
    facts=module.scene_weights.facts(mesh)
    assert facts['unweighted_vertices']==0 and facts['max_influences']==2 and facts['max_sum_error']==0


@pytest.mark.parametrize('change',['stale','locked','unknown','indices','rig','modifier','missing'])
def test_weight_worker_preflight_and_result_failure(monkeypatch,change):
    module,mesh,rig,op=fixture(monkeypatch)
    if change=='stale':op['expected_geometry_sha256']='f'*64
    elif change=='locked':mesh.vertex_groups[0].lock_weight=True
    elif change=='unknown':mesh.vertex_groups[0].name='unrecognized'
    elif change=='indices':op['vertex_indices']=[3]
    elif change=='rig':op['rig_object_id']='absent'
    elif change=='modifier':mesh.modifiers[0].use_bone_envelopes=True
    elif change=='missing':mesh.data.vertices[0].groups=[]
    with pytest.raises(RuntimeError):module.scene_weights.apply(mesh,op,{'rig':rig},lambda *a,**k:None)


def test_normalize_preserves_top_four_deterministically(monkeypatch):
    module=worker(monkeypatch)
    assert module.scene_weights.normalized({i:.1 for i in range(5)})=={0:.25,1:.25,2:.25,3:.25}
    with pytest.raises(RuntimeError):module.scene_weights.normalized({0:0})
    with pytest.raises(RuntimeError):module.scene_weights.normalized({0:float('nan')})
