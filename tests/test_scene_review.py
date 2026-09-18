from __future__ import annotations

import asyncio
import base64
from dataclasses import replace
import hashlib
import io
import json
from contextlib import ExitStack
from pathlib import Path
import zipfile
import time

from PIL import Image
import pytest
from pydantic import ValidationError

from mediaforge.domain import JobRequest, JobStatus
from mediaforge.host.ai import HostAIError, HostAIResult
from mediaforge.jobs import JobManager
from mediaforge.scene_recipe_jobs import SceneRecipeJobManager
from mediaforge.scene_review import SceneReviewRequest, VisualReview
from mediaforge.scene_recipes import scene_operation_types
from mediaforge.scenes import SceneError, SceneRevisionInput
from mediaforge.store import Store
from test_reference_set import request as pack_request, spec as reference_spec
from test_scene_observation import observation_workspace
from test_scene_recipe_jobs import Host, IDENTITY
from test_scene_workspace import register_image

ROOT = Path(__file__).parents[1]
VISION_IDENTITY = replace(IDENTITY, actor_subject='user:1', granted_capabilities=frozenset({'jobs.write', 'ai.inference'}))


class Gateway:
    def __init__(self, *, mode='valid', references=False):
        self.mode, self.references = mode, references
        self.calls = []
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def available(self, identity, capability):
        assert capability == 'vision.analyze' and 'ai.inference' in identity.granted_capabilities
        return self.mode != 'unavailable'

    async def complete(self, identity, capability, messages, **kwargs):
        self.calls.append((identity, capability, messages, kwargs))
        self.entered.set()
        if self.mode == 'wait':
            await self.release.wait()
        if self.mode == 'failure':
            raise HostAIError('host_ai_unavailable', 'Host is unavailable')
        issue = {'scope': 'object', 'object_id': 'body', 'evidence_ids': ['observation.front'],
                 'description': 'Body appears too wide', 'expected_improvement': 'Narrow its outline',
                 'suggested_operation': 'transform.set', 'confidence': .8}
        value = {'verdict': 'issues_found', 'reference_consistency': 'consistent' if self.references else 'not_provided',
                 'issues': [issue], 'limitations': ['Still images cannot prove deformation quality']}
        if self.mode == 'unknown_object':issue['object_id'] = 'invented'
        if self.mode == 'unknown_evidence':issue['evidence_ids'] = ['reference.back']
        if self.mode == 'unsupported':issue['suggested_operation'] = 'mesh.arbitrary_python'
        if self.mode == 'no_images':return HostAIResult('I did not receive images', capability)
        if self.mode == 'too_many':value['issues'] = [issue] * 4
        if self.mode == 'contradictory':value['reference_consistency'] = 'contradictory'
        if self.mode == 'pretend_reference':value['reference_consistency'] = 'consistent'
        if self.mode == 'false_clean':value['verdict'] = 'no_visible_issues'
        return HostAIResult(json.dumps(value), capability)


async def fixture(root: Path, *, references=False, canonical=False):
    store, workspace, resolver, observation = await asyncio.to_thread(observation_workspace, root)
    executable = resolver.runtime.executable
    executable.write_text(executable.read_text().replace("'images':images,'object_colors':[],", "'images':images,'object_colors':[],'object_ids':['body'],"))
    if references:
        images = [register_image(store, root).id for _ in range(5 if canonical else 2)]
        spec = reference_spec(*images[:2])
        if canonical:
            spec['views']=[{'view':view,'asset_id':asset_id} for view,asset_id in zip(['front','side','back','three-quarter'],images)]
            spec['canonical_asset_id']=images[-1]
        job = store.create_job(JobRequest.model_validate(pack_request(spec)))
        await JobManager(store)._execute_reference_pack(job, None)
        package_id = store.get_job(job.id).asset_ids[0]
        doc, revisions = workspace.catalog.get('user:1', observation.scene_id)
        head = revisions[0]
        data = head.model_dump(include=set(SceneRevisionInput.model_fields))
        data['dependencies'] = [{'role': 'reference_set', 'asset_id': package_id, 'sha256': store.get_asset(package_id).sha256}]
        _, revision = workspace.catalog.commit('user:1', doc.id, head.id, SceneRevisionInput.model_validate(data))
        observation = observation.model_copy(update={'revision_id': revision.id})
    job = store.create_job(JobRequest(operation='media.inspect', intent='Observation fixture'))
    observed = await workspace.observe_scene('user:1', job.id, observation,
        runtime_id=resolver.runtime.runtime_id, runtime_version=resolver.runtime.version)
    value = SceneReviewRequest(scene_id=observation.scene_id, revision_id=observation.revision_id,
        observation_asset_ids=observed['asset_ids'], intent='Check proportions and contact')
    return store, workspace, resolver, value


def test_review_contract_and_capability(client):
    for name, model in [('scene-review-request', SceneReviewRequest), ('scene-visual-review', VisualReview)]:
        assert json.loads((ROOT / f'schemas/{name}.json').read_text()) == model.model_json_schema()
    tools = json.loads((ROOT/'addon.json').read_text())['contributions']['agent_tools']
    assert next(t for t in tools if t['id']=='media.scene.review')['endpoint']=='/addon/v1/agent/scene/review'
    assert client.get('/api/v1/capabilities').json()['capabilities']['3d.scene_review']['state']=='unavailable'


@pytest.mark.parametrize('references', [False, True])
def test_review_sends_actual_images_and_records_lineage_without_advancing_head(tmp_path, references):
    async def scenario():
        store, workspace, resolver, value = await fixture(tmp_path, references=references)
        gateway = Gateway(references=references)
        manager = SceneRecipeJobManager(store, workspace, Host(), ai_gateway=gateway)
        job, _ = await manager.submit(value, VISION_IDENTITY)
        await manager.wait_cleanup(job.id)
        projected = manager.projection(job.id, 'user:1')
        assert projected['status']=='succeeded', projected
        report = projected['result']['review']
        assert report['asset_approval']=='not_granted' and report['edits_executed'] is False
        assert len(gateway.calls)==1 and len(report['evidence'])==(6 if references else 4)
        identity, capability, messages, options = gateway.calls[0]
        assert identity.subject=='job:host-child' and capability=='vision.analyze'
        prompt = messages[0]['content'][0]['text']
        context = json.loads(prompt.split('Context JSON: ', 1)[1])
        assert set(context['known_suggested_operations']) == set(scene_operation_types())
        assert 'or null when no known' in prompt
        images = [item['image_url']['url'] for item in messages[0]['content'] if item['type']=='image_url']
        assert len(images)==(2 if references else 1)
        for url, kind in zip(images, ['observation', 'reference']):
            data = base64.b64decode(url.split(',',1)[1])
            image=Image.open(io.BytesIO(data))
            assert max(image.size)<=768
            for evidence in (item for item in report['evidence'] if item['sheet_id']==kind):
                assert hashlib.sha256(data).hexdigest()==evidence['submitted_sha256']
                x0,y0,x1,y1=evidence['image_region_xyxy']
                assert 0<=x0<x1<=image.width and 0<=y0<y1<=image.height
        asset = store.get_asset(projected['asset_ids'][0])
        assert set(value.observation_asset_ids)<=set(asset.parent_asset_ids)
        with zipfile.ZipFile(store.asset_path(asset.id)) as archive:
            assert archive.namelist()==['review.json']
            assert json.loads(archive.read('review.json'))==report
        assert workspace.catalog.get('user:1',value.scene_id)[0].current_revision_id==value.revision_id
        assert resolver.references==0 and not list(workspace.review_root.iterdir())
        await manager.stop()
    asyncio.run(scenario())


def test_distinct_canonical_and_all_views_fit_host_image_bound(tmp_path):
    async def scenario():
        store,workspace,resolver,value=await fixture(tmp_path,references=True,canonical=True)
        gateway=Gateway(references=True)
        job=store.create_job(JobRequest(operation='media.inspect',intent='canonical review'))
        result=await workspace.review_scene('user:1',job.id,value,gateway=gateway,identity=VISION_IDENTITY,
            runtime_id=resolver.runtime.runtime_id,runtime_version=resolver.runtime.version)
        images=[item for item in gateway.calls[0][2][0]['content'] if item['type']=='image_url']
        assert len(images)==3
        evidence=result['review']['evidence']
        assert len(evidence)==9 and 'reference.canonical' in {e['evidence_id'] for e in evidence}
        assert {e['sheet_id'] for e in evidence}=={'observation','reference','reference_2'}
        submitted={hashlib.sha256(base64.b64decode(item['image_url']['url'].split(',',1)[1])).hexdigest() for item in images}
        assert submitted=={e['submitted_sha256'] for e in evidence}
    asyncio.run(scenario())


def test_changed_input_during_vision_fails_before_report_publication(tmp_path):
    async def scenario():
        store,workspace,resolver,value=await fixture(tmp_path)
        before=len(store.list_assets());gateway=Gateway(mode='wait')
        manager=SceneRecipeJobManager(store,workspace,Host(),ai_gateway=gateway)
        job,_=await manager.submit(value,VISION_IDENTITY)
        await asyncio.wait_for(gateway.entered.wait(),2)
        store.asset_path(value.observation_asset_ids[0]).write_bytes(b'changed during inference')
        gateway.release.set()
        await manager.wait_cleanup(job.id)
        assert store.get_job(job.id).status==JobStatus.FAILED
        assert len(store.list_assets())==before and not list(workspace.review_root.iterdir())
        await manager.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize('mode', ['unavailable','failure','unknown_object','unknown_evidence','no_images','too_many','pretend_reference','false_clean'])
def test_unavailable_or_invalid_vision_never_publishes_success(tmp_path, mode):
    async def scenario():
        store, workspace, resolver, value = await fixture(tmp_path)
        before = len(store.list_assets())
        gateway=Gateway(mode=mode)
        manager=SceneRecipeJobManager(store,workspace,Host(),ai_gateway=gateway)
        job,_=await manager.submit(value,VISION_IDENTITY)
        await manager.wait_cleanup(job.id)
        result=manager.projection(job.id,'user:1')
        assert result['status']=='failed' and not result['asset_ids']
        assert len(store.list_assets())==before and not list(workspace.review_root.iterdir())
        assert resolver.references==0
        if mode=='unavailable':assert not gateway.calls
        await manager.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize('mode', ['unsupported','contradictory'])
def test_uncertain_or_unsupported_advice_remains_needs_review(tmp_path,mode):
    async def scenario():
        store,workspace,resolver,value=await fixture(tmp_path,references=True)
        gateway=Gateway(mode=mode,references=True)
        job=store.create_job(JobRequest(operation='media.inspect',intent='advisory review'))
        result=await workspace.review_scene('user:1',job.id,value,gateway=gateway,identity=VISION_IDENTITY,
            runtime_id=resolver.runtime.runtime_id,runtime_version=resolver.runtime.version)
        assert result['review']['review_state']=='needs_review'
        assert result['review']['asset_approval']=='not_granted'
    asyncio.run(scenario())


@pytest.mark.parametrize('mode',['owner','revision','foreign_reference','duplicate','missing_side','corrupt'])
def test_input_checks_precede_vision(tmp_path,mode):
    async def scenario():
        store,workspace,resolver,value=await fixture(tmp_path)
        gateway=Gateway()
        owner='user:1'
        if mode=='owner':owner='user:other'
        if mode=='revision':value=value.model_copy(update={'revision_id':'revision_'+'f'*32})
        if mode=='foreign_reference':value=value.model_copy(update={'reference_set_asset_id':'asset_'+'f'*32})
        if mode=='duplicate':
            with pytest.raises(ValidationError):
                SceneReviewRequest.model_validate({**value.model_dump(), 'observation_asset_ids':[value.observation_asset_ids[0]]*2})
            return
        if mode=='missing_side':value=value.model_copy(update={'observation_asset_ids':[value.observation_asset_ids[0],value.observation_asset_ids[2]]})
        if mode=='corrupt':store.asset_path(value.observation_asset_ids[0]).write_bytes(b'corrupt')
        job=store.create_job(JobRequest(operation='media.inspect',intent='invalid review'))
        with pytest.raises((SceneError,KeyError)):
            await workspace.review_scene(owner,job.id,value,gateway=gateway,identity=VISION_IDENTITY,
                runtime_id=resolver.runtime.runtime_id,runtime_version=resolver.runtime.version)
        assert not gateway.calls and not list(workspace.review_root.iterdir())
    asyncio.run(scenario())


def test_cancel_pending_vision_then_retry_preserves_input_and_releases_resources(tmp_path):
    async def scenario():
        store,workspace,resolver,value=await fixture(tmp_path)
        before=len(store.list_assets());gateway=Gateway(mode='wait')
        manager=SceneRecipeJobManager(store,workspace,Host(),ai_gateway=gateway)
        with pytest.raises(SceneError,match='AI'):
            await manager.submit(value,replace(VISION_IDENTITY,granted_capabilities=frozenset({'jobs.write'})))
        job,_=await manager.submit(value,VISION_IDENTITY)
        await asyncio.wait_for(gateway.entered.wait(),2)
        with pytest.raises(KeyError):await manager.cancel(job.id,'user:other')
        await manager.cancel(job.id,'user:1')
        assert store.get_job(job.id).status==JobStatus.CANCELED
        assert len(store.list_assets())==before and not list(workspace.review_root.iterdir()) and resolver.references==0
        gateway.mode='valid'
        retry,_=await manager.submit(value.model_copy(update={'retry_job_id':job.id}),VISION_IDENTITY,retry_of=job.id)
        await manager.wait_cleanup(retry.id)
        assert store.get_job(retry.id).status==JobStatus.SUCCEEDED
        await manager.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize('stage', ['validate_recipe', 'vision_review', 'publish_review'])
def test_restart_review_publication_fails_closed(tmp_path, stage):
    store=Store(tmp_path);store.initialize()
    job=store.create_job(JobRequest(operation='media.inspect',intent='review restart'),host_managed=True)
    store.create_scene_recipe_task(job.id,owner='user:1',host_job_id='child',operation='scene.review',runtime_id='blender-test',
        runtime_version='4.5.9',base_revision_id='revision_'+'a'*32,input_sha256='1'*64,idempotency_key='2'*64,request={})
    store.update_job(job.id,status=JobStatus.RUNNING,phase=stage)
    store.update_scene_recipe_task(job.id,stage=stage)
    store=Store(tmp_path);store.initialize()
    assert store.get_job(job.id).status==JobStatus.FAILED
    assert store.get_scene_recipe_task(job.id).stage=='service_restarted'


def test_review_agent_route_and_strict_input(tmp_path):
    from fastapi.testclient import TestClient
    from conftest import fake_settings
    from mediaforge.app import create_app
    from test_scene_agent_api import Host as APIHost
    class VisionHost(APIHost):
        async def authenticate(self, headers):
            return replace(await super().authenticate(headers), granted_capabilities=frozenset({'jobs.write','ai.inference'}))
    host=VisionHost()
    app=create_app(fake_settings(tmp_path),host_client=host)
    value=SceneReviewRequest(scene_id='scene_'+'a'*32,revision_id='revision_'+'b'*32,
        observation_asset_ids=['asset_'+'c'*32,'asset_'+'d'*32],intent='Review shape')
    app.state.scene_workspace.acquire_recipe_runtime=lambda owner,payload:(ExitStack(),('blender-test','4.5.9',payload.revision_id))
    async def reviewed(owner,job_id,payload,**kwargs):
        assert owner=='user:7' and payload==value and kwargs['identity'].subject.startswith('job:child-')
        return {'scene':{'id':value.scene_id},'revision':{'id':value.revision_id},'asset_ids':['asset_'+'e'*32],
                'review':{'semantic_review':'completed','asset_approval':'not_granted'}}
    app.state.scene_workspace.review_scene=reviewed
    headers={'Authorization':'Bearer request','X-Control-Deck-Addon-ID':'media-forge'}
    with TestClient(app) as client:
        response=client.post('/addon/v1/agent/scene/review',headers=headers,json={'input':value.model_dump(mode='json')})
        assert response.status_code==200 and response.json()['detached'] is True
        deadline=time.monotonic()+3
        while True:
            job=client.post('/addon/v1/agent/job/status',headers=headers,json={'input':{'job_id':response.json()['job_id']}}).json()
            if job['status']=='succeeded' and job['host_terminal_sent']:break
            assert time.monotonic()<deadline
            time.sleep(.01)
        assert job['operation']=='scene.review'
        assert client.post('/addon/v1/agent/scene/review',headers=headers,
            json={'input':{**value.model_dump(mode='json'),'script':'untrusted'}}).status_code==422
        assert host.children==1
