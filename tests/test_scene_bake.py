from __future__ import annotations

import asyncio
import base64
from contextlib import ExitStack
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image,PngImagePlugin
import pytest
from pydantic import ValidationError

from mediaforge.domain import JobRequest,JobStatus
from mediaforge.scene_bake import SceneBakeRequest,HighBakeSource
from mediaforge.scene_recipe_jobs import SceneRecipeJobManager
from mediaforge.scene_recipes import UvSeamsSet,UvUnwrap,UvPack,TransformApplyScale
from mediaforge.scenes import SceneError
from mediaforge.store import Store
from test_scene_workspace import fake_scene_workspace,upload_scene
from test_scene_recipe_jobs import Host,IDENTITY
from test_game_static_operations import ROOT,worker


def fixture(root: Path,mode='valid'):
    store,workspace,resolver=fake_scene_workspace(root)
    imported=upload_scene(workspace,b'BLENDER-bake-fixture')
    workspace.bake_worker=workspace.worker
    image=Image.new('RGBA',(256,256),(128,128,255,255));buffer=io.BytesIO();metadata=PngImagePlugin.PngInfo();metadata.add_text('File','private/source.blend')
    image.save(buffer,format='PNG',pnginfo=metadata)
    executable=resolver.runtime.executable
    executable.write_text('#!/usr/bin/python3\nimport json,pathlib,base64,hashlib,time\n'+f'mode={mode!r}\n'+
        "spec=json.loads(pathlib.Path('bake.json').read_text())\n"+
        "if mode=='slow':time.sleep(30)\n"+
        f"data=base64.b64decode({base64.b64encode(buffer.getvalue()).decode()!r})\n"+
        "images=[]\nfor channel in spec['channels']:\n pathlib.Path(channel+'.png').write_bytes(data)\n images.append({'channel':channel,'filename':channel+'.png','sha256':hashlib.sha256(data).hexdigest(),'nontransparent_pixels':65536,'color_space':'non_color','normal_convention':'open_gl' if channel=='normal' else None})\n"+
        "report={'schema_version':'media-forge.scene-bake-result@1','blender_version':'4.5.9','spec':spec,'device':'CPU','frame':0,'samples':16,'autoexec_disabled':True,'uv':{'name':'UVMap','uv_sha256':'a'*64,'loops':3,'finite':True,'degenerate_triangles':0,'bounds_min':[0,0],'bounds_max':[1,1]},'images':images}\n"+
        "if mode=='gpu':report['device']='GPU'\nif mode=='settings':report['spec']={**spec,'resolution':512}\nif mode=='empty':images[0]['nontransparent_pixels']=0\n"+
        "if mode=='bad_image':pathlib.Path('ao.png').write_bytes(b'bad')\nif mode=='symlink':\n pathlib.Path('normal.png').unlink()\n pathlib.Path('normal.png').symlink_to('ao.png')\n"+
        "pathlib.Path('result.json').write_text(json.dumps(report))\n")
    value=SceneBakeRequest(scene_id=imported['scene']['id'],revision_id=imported['revision']['id'],object_id='body',geometry_sha256='a'*64,
        high_source=HighBakeSource(scene_id=imported['scene']['id'],revision_id=imported['revision']['id'],object_id='body',geometry_sha256='a'*64),resolution=256)
    return store,workspace,resolver,value


def test_bake_schema_and_discovery(client):
    assert json.loads((ROOT/'schemas/scene-bake-request.json').read_text())==SceneBakeRequest.model_json_schema()
    capabilities=client.get('/api/v1/capabilities').json()['capabilities']
    assert capabilities['3d.scene_bake']['state']==capabilities['3d.scene_recipe']['state']
    with pytest.raises(ValidationError):SceneBakeRequest(scene_id='scene_'+'a'*32,revision_id='revision_'+'b'*32,object_id='body',geometry_sha256='a'*64)


@pytest.mark.parametrize('changes',[{'resolution':2048},{'margin_px':True},{'channels':['ao','ao']},{'channels':['normal']},
                                     {'cage_extrusion_m':float('nan')},{'uv_map':'../bad'}])
def test_bake_bounds(changes):
    with pytest.raises(ValidationError):SceneBakeRequest.model_validate({'scene_id':'scene_'+'a'*32,'revision_id':'revision_'+'b'*32,
        'object_id':'body','geometry_sha256':'a'*64,'channels':['ao'],**changes})


@pytest.mark.parametrize('operation',[
    {'type':'uv.seams.set','edges':[[0,0]]},{'type':'uv.seams.set','edges':[[0,1],[1,0]]},
    {'type':'uv.seams.set','edges':[[True,1]]},{'type':'uv.unwrap','method':'PYTHON'},
    {'type':'uv.pack','margin':.5},
])
def test_uv_selector_schema_rejects_invalid_input(operation):
    model={'uv.seams.set':UvSeamsSet,'uv.unwrap':UvUnwrap,'uv.pack':UvPack}[operation['type']]
    with pytest.raises(ValidationError):model.model_validate({'object_id':'body','expected_geometry_sha256':'a'*64,**operation})


def test_uv_worker_rejects_stale_selection_before_blender_ops(monkeypatch):
    module=worker(monkeypatch)
    mesh=SimpleNamespace(users=1,vertices=[SimpleNamespace(co=(0,0,0))],polygons=[])
    obj=SimpleNamespace(type='MESH',data=mesh)
    with pytest.raises(RuntimeError,match='stale'):
        module.scene_surface.apply_uv(obj,{'type':'uv.pack','expected_geometry_sha256':'a'*64})


def test_bake_keeps_heads_and_registers_clean_image_lineage(tmp_path):
    store,workspace,resolver,value=fixture(tmp_path)
    async def scenario():
        job=store.create_job(JobRequest(operation='media.inspect',intent='Bake fixture'))
        result=await workspace.bake_scene('user:1',job.id,value,runtime_id=resolver.runtime.runtime_id,runtime_version='4.5.9')
        assert workspace.catalog.get('user:1',value.scene_id)[0].current_revision_id==value.revision_id
        assert len(result['images'])==2 and result['ray_hit_coverage']=='not_measured' and result['surface_approval']=='not_granted'
        for row in result['images']:
            asset=store.get_asset(row['asset_id']);provenance=store.get_provenance(asset.id)
            assert provenance.operation=='scene.bake' and len(provenance.reference_asset_hashes)==1
            assert set(provenance.reference_asset_hashes)==set(asset.parent_asset_ids)
            assert hashlib.sha256(store.asset_path(asset.id).read_bytes()).hexdigest()==asset.sha256==row['sha256']
            with Image.open(store.asset_path(asset.id)) as image:assert image.info=={} and image.mode=='RGBA'
        assert resolver.references==0 and not list(workspace.bake_root.iterdir())
    asyncio.run(scenario())


@pytest.mark.parametrize('mode',['gpu','settings','empty','bad_image','symlink','slow','registration'])
def test_bake_failure_rolls_back_all_outputs(tmp_path,monkeypatch,mode):
    store,workspace,resolver,value=fixture(tmp_path,mode)
    before=len(store.list_assets())
    if mode=='slow':workspace.process_timeout_sec=.02
    if mode=='registration':
        original=store.register_asset;count=0
        def register(*args,**kwargs):
            nonlocal count
            count+=1
            if count==2:raise RuntimeError('controlled registration failure')
            return original(*args,**kwargs)
        monkeypatch.setattr(store,'register_asset',register)
    async def scenario():
        job=store.create_job(JobRequest(operation='media.inspect',intent='Bake failure fixture'))
        with pytest.raises((SceneError,RuntimeError)):
            await workspace.bake_scene('user:1',job.id,value,runtime_id=resolver.runtime.runtime_id,runtime_version='4.5.9')
        assert len(store.list_assets())==before and resolver.references==0 and not list(workspace.bake_root.iterdir())
    asyncio.run(scenario())


def test_owner_and_high_revision_are_checked(tmp_path):
    store,workspace,resolver,value=fixture(tmp_path)
    async def scenario():
        job=store.create_job(JobRequest(operation='media.inspect',intent='Scope fixture'))
        with pytest.raises((SceneError,KeyError)):
            await workspace.bake_scene('user:other',job.id,value,runtime_id=resolver.runtime.runtime_id,runtime_version='4.5.9')
        bad=value.model_copy(update={'high_source':value.high_source.model_copy(update={'revision_id':'revision_'+'f'*32})})
        with pytest.raises(SceneError,match='high bake revision'):
            await workspace.bake_scene('user:1',job.id,bad,runtime_id=resolver.runtime.runtime_id,runtime_version='4.5.9')
        assert not list(workspace.bake_root.iterdir())
    asyncio.run(scenario())


@pytest.mark.parametrize('stage',['blender_bake','publish_bake'])
def test_bake_restart_fails_closed(tmp_path,stage):
    from test_scene_recipe_jobs import pending_terminal
    store=Store(tmp_path);store.initialize();job_id=pending_terminal(store)
    store.update_job(job_id,status=JobStatus.RUNNING);store.update_scene_recipe_task(job_id,stage=stage)
    reopened=Store(tmp_path);reopened.initialize();assert reopened.get_job(job_id).status==JobStatus.FAILED


def test_bake_cancel_drain_and_staging_recovery(tmp_path):
    store,workspace,resolver,value=fixture(tmp_path,'slow')
    async def scenario():
        job=store.create_job(JobRequest(operation='media.inspect',intent='Cancel bake'))
        task=asyncio.create_task(workspace.bake_scene('user:1',job.id,value,runtime_id=resolver.runtime.runtime_id,runtime_version='4.5.9'))
        await asyncio.sleep(.03);task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert resolver.references==0 and not list(workspace.bake_root.iterdir())
    asyncio.run(scenario())
    outside=tmp_path/'kept.txt';outside.write_text('keep')
    (workspace.bake_root/'stale').mkdir();(workspace.bake_root/'link').symlink_to(outside)
    workspace.initialize();assert outside.read_text()=='keep' and not list(workspace.bake_root.iterdir())


def test_a_few_zero_area_uv_triangles_do_not_block_a_bake() -> None:
    """面を削ると UV に面積ゼロの三角形が少数できる。実測 24,900 中 1 つ。

    その三角形にテクセルが乗らないだけで他の面には影響しないので、全体を
    断る理由にはならない。ほとんどが潰れている UV は今までどおり断る。
    """
    from mediaforge.scene_bake_runner import validate_report

    value = SceneBakeRequest.model_validate({
        "scene_id": "scene_" + "a" * 32, "revision_id": "revision_" + "b" * 32,
        "object_id": "generated_0", "geometry_sha256": "c" * 64,
        "channels": ["ao"], "resolution": 256,
    })

    def report(degenerate: int) -> dict:
        return {
            "schema_version": "media-forge.scene-bake-result@1", "blender_version": "4.5.13",
            "spec": value.worker_spec(), "device": "CPU", "frame": 0, "samples": 16,
            "autoexec_disabled": True,
            "uv": {"name": "UVMap", "uv_sha256": "d" * 64, "loops": 74_700, "finite": True,
                   "degenerate_triangles": degenerate,
                   "bounds_min": [0.0, 0.0], "bounds_max": [1.0, 1.0]},
            "images": [{"channel": "ao", "filename": "ao.png", "sha256": "e" * 64,
                        "nontransparent_pixels": 1000, "color_space": "non_color",
                        "normal_convention": None}],
        }

    # 実測値（24,900 三角形のうち 1 つ）は通る。
    validate_report(report(1), value, "4.5.13")
    # 許容は 1000 分の 1 か 64 の大きい方。
    validate_report(report(74), value, "4.5.13")
    with pytest.raises(ValueError):
        validate_report(report(75), value, "4.5.13")
    # 数えられなかった UV は通さない。
    with pytest.raises(ValueError):
        validate_report(report(None), value, "4.5.13")
