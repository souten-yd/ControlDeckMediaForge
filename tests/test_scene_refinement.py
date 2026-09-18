from __future__ import annotations

import asyncio
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import uuid

import pytest
from pydantic import ValidationError

from mediaforge.domain import JobStatus
from mediaforge.host.ai import HostAIResult
from mediaforge.scene_recipe_jobs import SceneRecipeJobManager
from mediaforge.scene_refinement import SceneRefineRequest, LocalRepair, ImageComparison
from mediaforge.scene_refinement_runner import mesh_guard
from mediaforge.scenes import SceneError
from mediaforge.store import Store
from test_scene_review import fixture, Gateway as ReviewGateway, VISION_IDENTITY, ROOT
from test_scene_recipe_jobs import Host

FACT={'object_id':'body','geometry_sha256':'a'*64,'vertices':8,'triangles':12,
      'boundary_edges':0,'nonmanifold_edges':0,'inconsistent_edges':0,'boundary_loops':[]}


class Gateway(ReviewGateway):
    def __init__(self,changes=('improved',),mode='valid'):
        super().__init__(mode=mode)
        self.changes=iter(changes);self.comparisons=0;self.plans=0
        self.image_counts=[]

    async def available(self,identity,capability):
        assert capability in {'text.generate','vision.analyze'}
        return self.mode!='unavailable'

    async def complete(self,identity,capability,messages,**kwargs):
        name=kwargs['response_format']['name']
        if name=='mediaforge_scene_review':
            return await super().complete(identity,capability,messages,**kwargs)
        self.calls.append((identity,capability,messages,kwargs))
        self.entered.set()
        if self.mode=='wait_plan' and capability=='text.generate':await self.release.wait()
        if capability=='text.generate':
            self.plans+=1
            value={'issue_indices':[0],'explanation':'Address the measured image-review target',
                   'operations':[{'type':'transform.set','object_id':'body','dimensions':[.8,1,1]}]}
            if self.mode=='bad_target':value['operations'][0]['object_id']='unrelated'
            if self.mode=='bad_issue':value['issue_indices']=[2]
        else:
            self.comparisons+=1
            self.image_counts.append(sum(p['type']=='image_url' for p in messages[0]['content']))
            value={'change':next(self.changes),'explanation':'Controlled comparison result, not live inference',
                   'evidence_ids':['baseline.front','candidate.front'],'remaining_issues':[],
                   'limitations':['Test response does not establish visual quality']}
            if self.mode=='bad_evidence':value['evidence_ids']=['baseline.front','candidate.back']
        return HostAIResult(json.dumps(value),capability)


async def setup(root,monkeypatch,*,references=False):
    store,workspace,resolver,review=await fixture(root,references=references,canonical=references)
    original=workspace.geometry_facts
    monkeypatch.setattr(workspace,'geometry_facts',lambda revision:[FACT] if revision.id==review.revision_id else original(revision))
    async def worker(recipe,runtime,*,source):
        path=workspace.recipe_root/f'fixture_{uuid.uuid4().hex}.blend'
        path.write_bytes(source.read_bytes()+recipe.model_dump_json().encode())
        return path,{'schema_version':'media-forge.scene-recipe-result@1','blender_version':runtime.version,
            'autoexec_disabled':True,'operation_count':len(recipe.operations),'stable_object_ids':['body'],
            'mesh_geometry':[FACT]}
    monkeypatch.setattr(workspace,'_apply_recipe_worker',worker)
    revision=workspace.catalog.get('user:1',review.scene_id)[1][-1]
    facts_by_validator={check.validator:check.facts for check in revision.validation}
    async def validate(source,runtime):
        path=workspace.validation_root/f'fixture_{uuid.uuid4().hex}.glb'
        path.write_bytes(store.asset_path(revision.preview_asset_id).read_bytes())
        return path,facts_by_validator['blender.scene'],facts_by_validator['glb.structure']
    monkeypatch.setattr(workspace,'_validate',validate)

    value=SceneRefineRequest(scene_id=review.scene_id,base_revision_id=review.revision_id,
                            intent='Improve body proportions',observation={'center':[0,0,0],'span_m':3,'mode':'clay','resolution':256,'views':['front','side']})
    return store,workspace,resolver,value


def test_refinement_schema_and_capability(client):
    for name,model in [('scene-refine-request',SceneRefineRequest),('scene-local-repair',LocalRepair),('scene-image-comparison',ImageComparison)]:
        assert json.loads((ROOT/f'schemas/{name}.json').read_text())==model.model_json_schema()
    assert client.get('/api/v1/capabilities').json()['capabilities']['3d.scene_refinement']['state']=='unavailable'


@pytest.mark.parametrize('change',[{'max_iterations':7},{'max_iterations':True},{'observation':{'center':[0,0,0],'span_m':3,'mode':'material'}},
                                   {'observation':{'center':[0,0,0],'span_m':3,'mode':'clay','views':['front']}}])
def test_bounds_and_shape_only_gate(change):
    with pytest.raises(ValidationError):SceneRefineRequest.model_validate({'scene_id':'scene_'+'a'*32,'base_revision_id':'revision_'+'b'*32,
        'intent':'Shape','observation':{'center':[0,0,0],'span_m':3,'mode':'clay'},**change})


@pytest.mark.parametrize('changes,selected,reason,attempts',[
    (['improved'],True,'no_visible_issues',1),(['worse','unchanged'],False,'two_non_improvements',2),
    (['inconclusive','worse'],False,'two_non_improvements',2),
])
def test_loop_preserves_original_and_rejects_non_improvements(tmp_path,monkeypatch,changes,selected,reason,attempts):
    async def scenario():
        store,workspace,resolver,value=await setup(tmp_path,monkeypatch)
        original=workspace.catalog.get('user:1',value.scene_id)[1][0]
        old_hash=hashlib.sha256(store.asset_path(original.source_asset_id).read_bytes()).hexdigest()
        gateway=Gateway(changes);manager=SceneRecipeJobManager(store,workspace,Host(),ai_gateway=gateway)
        job,_=await manager.submit(value,VISION_IDENTITY);await manager.wait_cleanup(job.id,10)
        result=manager.projection(job.id,'user:1')['result']
        assert store.get_job(job.id).status==JobStatus.SUCCEEDED,store.get_job(job.id).error
        report=result['refinement'];assert report['stop_reason']==reason and len(report['attempts'])==attempts
        assert (report['selected_scene_id']!=value.scene_id)==selected
        assert workspace.catalog.get('user:1',value.scene_id)[0].current_revision_id==value.base_revision_id
        assert hashlib.sha256(store.asset_path(original.source_asset_id).read_bytes()).hexdigest()==old_hash
        assert gateway.plans==gateway.comparisons==attempts and gateway.image_counts==[2]*attempts
        assert len(workspace.catalog.list('user:1'))==1+attempts
        assert report['asset_approval']=='not_granted' and report['deformation_gate']=='NOT TESTED'
        assert resolver.references==0 and not list(workspace.review_root.iterdir())
        for attempt in report['attempts']:
            scene,revisions=workspace.catalog.get('user:1',attempt['candidate_scene_id'])
            provenance=store.get_provenance(revisions[0].source_asset_id)
            assert provenance.parameters['candidate_origin']=={'scene_id':value.scene_id,'revision_id':value.base_revision_id}
        await manager.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize('mode',['unavailable','bad_target','bad_issue','bad_evidence'])
def test_invalid_or_unavailable_inference_fails_without_advancing_original(tmp_path,monkeypatch,mode):
    async def scenario():
        store,workspace,resolver,value=await setup(tmp_path,monkeypatch)
        gateway=Gateway(mode=mode);manager=SceneRecipeJobManager(store,workspace,Host(),ai_gateway=gateway)
        job,_=await manager.submit(value,VISION_IDENTITY);await manager.wait_cleanup(job.id,10)
        assert store.get_job(job.id).status==JobStatus.FAILED
        assert store.get_job(job.id).error.code=={'unavailable':'host_ai_unavailable','bad_target':'shape_repair_invalid','bad_issue':'shape_repair_invalid','bad_evidence':'vision_result_invalid'}[mode]
        assert workspace.catalog.get('user:1',value.scene_id)[0].current_revision_id==value.base_revision_id
        assert resolver.references==0 and not list(workspace.review_root.iterdir())
        if mode=='unavailable':assert not gateway.calls
        await manager.stop()
    asyncio.run(scenario())


def test_cancel_pending_plan_retains_evidence_and_drains_staging(tmp_path,monkeypatch):
    async def scenario():
        store,workspace,resolver,value=await setup(tmp_path,monkeypatch)
        gateway=Gateway(mode='wait_plan');manager=SceneRecipeJobManager(store,workspace,Host(),ai_gateway=gateway)
        job,_=await manager.submit(value,VISION_IDENTITY)
        for _ in range(400):
            if any(call[1]=='text.generate' for call in gateway.calls):break
            await asyncio.sleep(.01)
        assert any(call[1]=='text.generate' for call in gateway.calls)
        await manager.cancel(job.id,'user:1');assert store.get_job(job.id).status==JobStatus.CANCELED
        partial=manager.projection(job.id,'user:1')['result'];assert partial['asset_ids'] and partial['state']=='refining'
        assert workspace.catalog.get('user:1',value.scene_id)[0].current_revision_id==value.base_revision_id
        assert resolver.references==0 and not list(workspace.review_root.iterdir())
        gateway.mode='valid';gateway.release.set()
        retry,record=await manager.submit(value,VISION_IDENTITY,retry_of=job.id)
        await manager.wait_cleanup(retry.id,10)
        assert store.get_job(retry.id).status==JobStatus.SUCCEEDED
        assert record.retry_of==job.id and store.get_job(job.id).status==JobStatus.CANCELED
        assert manager.projection(job.id,'user:1')['result']==partial
        await manager.stop()
    asyncio.run(scenario())


def test_geometry_regression_cannot_be_selected():
    assert mesh_guard([FACT],[FACT])==[]
    assert mesh_guard([FACT],[])==['missing_mesh:body']
    assert mesh_guard([FACT],[{**FACT,'boundary_edges':4}])==['increased_boundary_edges:body']


def test_full_canonical_reference_fits_four_image_host_limit(tmp_path,monkeypatch):
    async def scenario():
        store,workspace,resolver,value=await setup(tmp_path,monkeypatch,references=True)
        gateway=Gateway();gateway.references=True
        manager=SceneRecipeJobManager(store,workspace,Host(),ai_gateway=gateway)
        job,_=await manager.submit(value,VISION_IDENTITY);await manager.wait_cleanup(job.id,10)
        assert store.get_job(job.id).status==JobStatus.SUCCEEDED,store.get_job(job.id).error
        assert gateway.image_counts==[4]
        report=manager.projection(job.id,'user:1')['result']['refinement']
        comparison=store.get_asset(report['attempts'][0]['comparison_asset_id'])
        import zipfile
        with zipfile.ZipFile(store.asset_path(comparison.id)) as archive:
            evidence=json.loads(archive.read('comparison.json'))['evidence']
        assert len(evidence)==9 and 'reference.canonical' in {e['evidence_id'] for e in evidence}
        assert resolver.references==0
        await manager.stop()
    asyncio.run(scenario())


def test_model_improvement_cannot_override_geometry_regression(tmp_path,monkeypatch):
    async def scenario():
        store,workspace,_,value=await setup(tmp_path,monkeypatch)
        worker=workspace._apply_recipe_worker
        async def changed(*args,**kwargs):
            path,facts=await worker(*args,**kwargs)
            facts['mesh_geometry']=[{**FACT,'boundary_edges':4}]
            return path,facts
        monkeypatch.setattr(workspace,'_apply_recipe_worker',changed)
        manager=SceneRecipeJobManager(store,workspace,Host(),ai_gateway=Gateway(['improved','improved']))
        job,_=await manager.submit(value,VISION_IDENTITY);await manager.wait_cleanup(job.id,10)
        assert store.get_job(job.id).status==JobStatus.SUCCEEDED,store.get_job(job.id).error
        report=manager.projection(job.id,'user:1')['result']['refinement']
        assert report['selected_scene_id']==value.scene_id and report['stop_reason']=='two_non_improvements'
        assert all(not a['selected'] and a['geometry_regressions'] for a in report['attempts'])
        await manager.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize('stage',['scene_refinement','publish_refinement'])
def test_restart_fails_refinement_stages(tmp_path,stage):
    from test_scene_recipe_jobs import pending_terminal
    store=Store(tmp_path);store.initialize();job_id=pending_terminal(store)
    store.update_job(job_id,status=JobStatus.RUNNING);store.update_scene_recipe_task(job_id,stage=stage)
    reopened=Store(tmp_path);reopened.initialize();assert reopened.get_job(job_id).status==JobStatus.FAILED


def test_permission_required_before_admission(tmp_path,monkeypatch):
    async def scenario():
        store,workspace,_,value=await setup(tmp_path,monkeypatch)
        manager=SceneRecipeJobManager(store,workspace,Host(),ai_gateway=Gateway())
        with pytest.raises(SceneError,match='Host AI'):
            await manager.submit(value,replace(VISION_IDENTITY,granted_capabilities=frozenset({'jobs.write'})))
        await manager.stop()
    asyncio.run(scenario())
