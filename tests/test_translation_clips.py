from __future__ import annotations

import json
import struct
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from mediaforge.scene_recipes import AnimationClip,RotationKey,SceneCreateRequest
from test_animation_clips import clip
from test_animation_facts import worker as document_worker,Action
from test_game_static_operations import worker


def translated():
    value=clip()
    for key,offset in zip(value['tracks'][0]['keys'],([0,0,0],[.2,0,0],[0,0,0])):key['translation_m']=offset
    return value


def test_legacy_rotation_payload_is_unchanged_and_null_is_omitted():
    value=AnimationClip.model_validate(clip()).model_dump(mode='json')
    assert all(set(key)=={'frame','rotation_degrees'} for key in value['tracks'][0]['keys'])
    assert RotationKey(frame=0,rotation_degrees=(0,0,0),translation_m=None).model_dump()=={'frame':0,'rotation_degrees':(0.,0.,0.)}
    assert 'translation_m' not in RotationKey(frame=0,rotation_degrees=(0,0,0)).model_dump_json()
    nested=SceneCreateRequest(name='Legacy',recipe={'operations':[clip()]}).model_dump(mode='json')
    assert 'translation_m' not in json.dumps(nested)


def test_translation_does_not_change_rotation_fields():
    value=AnimationClip.model_validate(translated()).model_dump(mode='json')
    assert value['tracks'][0]['keys'][1]['translation_m']==[.2,0,0]
    assert value['tracks'][0]['keys'][1]['rotation_degrees']==[10,0,0]


@pytest.mark.parametrize('bad',['partial','loop','nan','large','missing_rotation'])
def test_bad_translation_tracks_rejected(bad):
    value=translated();keys=value['tracks'][0]['keys']
    if bad=='partial':keys[0].pop('translation_m')
    elif bad=='loop':keys[-1]['translation_m']=[1,0,0]
    elif bad=='nan':keys[1]['translation_m']=[float('nan'),0,0]
    elif bad=='large':keys[1]['translation_m']=[101,0,0]
    else:keys[1].pop('rotation_degrees')
    with pytest.raises(ValidationError):AnimationClip.model_validate(value)


@pytest.mark.parametrize('bad',['partial','loop','nan','large'])
def test_worker_independently_rejects_bad_translations(monkeypatch,bad):
    module=worker(monkeypatch);monkeypatch.setattr(module,'rigid_armature',lambda *a,**k:None)
    rig=SimpleNamespace(pose=SimpleNamespace(bones={'head':object()}));value=translated();keys=value['tracks'][0]['keys']
    if bad=='partial':keys[0].pop('translation_m')
    elif bad=='loop':keys[-1]['translation_m']=[1,0,0]
    elif bad=='nan':keys[1]['translation_m']=[float('nan'),0,0]
    else:keys[1]['translation_m']=[101,0,0]
    with pytest.raises(RuntimeError):module.create_clip(rig,value,{'rig':rig})


def test_typed_clip_extras_preserve_other_animation_and_binary(tmp_path,monkeypatch):
    module=document_worker(monkeypatch)
    action=Action(media_forge_clip_schema=1,media_forge_clip_id='attack',media_forge_frame_count=36,media_forge_loop=False);action.name='mf.attack.abc'
    module.bpy.data=SimpleNamespace(actions=[action]);module.bpy.context=SimpleNamespace(scene={'media_forge_clip_fps':24})
    document={'asset':{'version':'2.0'},'animations':[{'name':action.name,'extras':{'existing':'kept'}},{'name':'foreign'}]}
    encoded=json.dumps(document).encode();encoded+=b' '*(-len(encoded)%4)
    tail=struct.pack('<II',4,0x004e4942)+b'\x01\x02\x03\x04';path=tmp_path/'preview.glb'
    path.write_bytes(struct.pack('<5I',0x46546c67,2,20+len(encoded)+len(tail),len(encoded),0x4e4f534a)+encoded+tail)
    module.add_clip_metadata(path);data=path.read_bytes();_,_,total,size,_=struct.unpack_from('<5I',data)
    assert total==len(data) and data[20+size:]==tail
    decoded=json.loads(data[20:20+size]);assert decoded['animations'][1]=={'name':'foreign'}
    extras=decoded['animations'][0]['extras'];assert extras['existing']=='kept' and extras['media_forge_clip']['loop_requested'] is False
    assert extras['media_forge_clip']['frame_count']==36
