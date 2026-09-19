from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from mediaforge.domain import JobStatus
from mediaforge.host.client import HostApiError
from mediaforge.scene_recipe_jobs import SceneRecipeJobManager
from mediaforge.scenes import SceneError
from mediaforge.store import AssetInUse
from test_scene_generation_import import setup
from test_scene_recipe_jobs import Host, IDENTITY
from test_three_d_runtime import native_runtime

GENERATION_IDENTITY = replace(IDENTITY, granted_capabilities=frozenset({'jobs.write','resources.acquire'}))


class ResourceHost(Host):
    def __init__(self, mode='success'):
        super().__init__()
        self.mode=mode
        self.events=[]
        self.requested=asyncio.Event()
        self.allow_response=asyncio.Event()

    async def request_resource(self,identity,payload):
        assert identity.subject=='job:host-child'
        assert payload['estimated_runtime_sec']==1
        assert payload['preferred_devices']==['gpu0']
        self.events.append('request')
        self.requested.set()
        if self.mode=='request':
            await self.allow_response.wait()
        if self.mode=='waiting':
            return {'request_id':'request-1','state':'waiting'}
        return {'request_id':'request-1','state':'granted','lease_id':'lease-1',
                'device_id':'host' if self.mode=='wrong_device' else 'gpu0','granted_bytes':2*1024**3}

    async def resource_status(self,identity,request_id):
        return {'request_id':request_id,'state':'waiting'}

    async def cancel_resource(self,identity,request_id):
        assert request_id=='request-1'
        self.events.append('cancel_request')
        return {}

    async def lease_action(self,identity,lease_id,action):
        assert lease_id=='lease-1'
        self.events.append(action)
        if self.mode=='renew_failure' and action=='renew':
            raise HostApiError('host_lease_lost','fixture lease failure')
        return {}


def manager_fixture(tmp_path,mode='success'):
    data=setup(tmp_path/'workspace')
    store,workspace,resolver,request,*_=data
    resolver.resolve_active=lambda: resolver.runtime
    runtime_root=tmp_path/'native';runtime_root.mkdir()
    generator,receipt=native_runtime(runtime_root,script="pathlib.Path('pid').write_text(str(os.getpid()))\ntime.sleep(0.1)\n" if mode=='success' else "pathlib.Path('pid').write_text(str(os.getpid()))\ntime.sleep(60)\n")
    host=ResourceHost(mode)
    manager=SceneRecipeJobManager(store,workspace,host,generator=generator,
        control_poll_sec=0.01,lease_renew_sec=0.02,resource_poll_sec=0.01)
    return manager,host,request,receipt


def test_image_generation_uses_child_lease_existing_scene_library_and_provenance(tmp_path):
    async def scenario():
        manager,host,request,receipt=manager_fixture(tmp_path)
        original=manager.workspace.import_generated_glb
        async def checked_import(*args,**kwargs):
            assert host.events[-1]=='release'
            return await original(*args,**kwargs)
        manager.workspace.import_generated_glb=checked_import
        job,record=await manager.submit(request,GENERATION_IDENTITY)
        assert record.operation=='scene.from_image'
        await manager.wait_cleanup(job.id)
        final=manager.store.get_job(job.id)
        assert final.status==JobStatus.SUCCEEDED, final.error
        assert len(final.asset_ids)==2
        source=manager.store.get_provenance(final.asset_ids[0])
        assert source.parent_asset_ids==[request.input_asset_id]
        assert source.model_version==receipt.model_revision
        assert host.events[:2]==['request','activate'] and 'renew' in host.events
        assert host.events.count('release')==1
        assert manager.projection(job.id,'user:7')['result']['scene']['name']==request.name
        assert list(manager.workspace.recipe_root.iterdir())==[]
        assert manager.workspace.resolver.references==0
        with pytest.raises(AssetInUse):
            manager.store.delete_asset(request.input_asset_id)
        await manager.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize('stage',['request','waiting','worker'])
def test_cancellation_cleans_pending_admission_or_worker_before_release(tmp_path,stage):
    async def scenario():
        manager,host,request,_=manager_fixture(tmp_path,stage)
        job,_=await manager.submit(request,GENERATION_IDENTITY)
        await asyncio.wait_for(host.requested.wait(),2)
        if stage in {'waiting', 'request'}:
            assert not manager._execution_guard.locked()
        if stage=='worker':
            for _ in range(200):
                pids=list(manager.workspace.recipe_root.glob('native_*/pid'))
                if pids: break
                await asyncio.sleep(0.01)
            assert pids
            pid=int(pids[0].read_text())
        with pytest.raises(AssetInUse):
            manager.store.delete_asset(request.input_asset_id)
        cancellation=asyncio.create_task(manager.cancel(job.id,'user:7'))
        if stage=='request':
            await asyncio.sleep(0.02)
            assert not cancellation.done()
            host.allow_response.set()
        await asyncio.wait_for(cancellation,5)
        await manager.wait_cleanup(job.id)
        assert manager.store.get_job(job.id).status==JobStatus.CANCELED
        assert host.events[-1]==('cancel_request' if stage=='waiting' else 'release')
        if stage=='worker':
            assert not Path(f'/proc/{pid}').exists()
        assert len(manager.store.list_assets())==1
        assert list(manager.workspace.recipe_root.iterdir())==[]
        manager.store.delete_asset(request.input_asset_id)
        await manager.stop()
    asyncio.run(scenario())


@pytest.mark.parametrize('mode,code',[('wrong_device','resource_grant_incompatible'),('renew_failure','host_lease_lost')])
def test_invalid_grant_or_lost_lease_fails_without_publishing(tmp_path,mode,code):
    async def scenario():
        manager,host,request,_=manager_fixture(tmp_path,mode)
        job,_=await manager.submit(request,GENERATION_IDENTITY)
        await manager.wait_cleanup(job.id)
        final=manager.store.get_job(job.id)
        assert final.status==JobStatus.FAILED and final.error.code==code
        assert host.events[-1]=='release'
        assert len(manager.store.list_assets())==1
        assert list(manager.workspace.recipe_root.iterdir())==[]
        if mode=='wrong_device': assert 'activate' not in host.events
        await manager.stop()
    asyncio.run(scenario())


def test_generation_checks_capability_and_adoption_before_host_admission(tmp_path):
    async def scenario():
        manager,host,request,_=manager_fixture(tmp_path)
        with pytest.raises(SceneError,match='resources.acquire'):
            await manager.submit(request,IDENTITY)
        manager.generator.receipt_path.unlink()
        with pytest.raises(SceneError,match='unavailable'):
            await manager.submit(request,GENERATION_IDENTITY)
        assert host.created==[] and host.events==[]
    asyncio.run(scenario())


def test_generation_retry_preserves_identity_and_can_publish_after_bad_grant(tmp_path):
    async def scenario():
        manager,host,request,_=manager_fixture(tmp_path)
        host.mode='wrong_device'
        first,_=await manager.submit(request,GENERATION_IDENTITY)
        await manager.wait_cleanup(first.id)
        assert manager.store.get_job(first.id).status==JobStatus.FAILED
        host.mode='success'
        second,record=await manager.submit(request,GENERATION_IDENTITY,retry_of=first.id)
        await manager.wait_cleanup(second.id)
        assert manager.store.get_job(second.id).status==JobStatus.SUCCEEDED
        assert record.retry_of==first.id
        assert record.input_sha256==manager.store.get_scene_recipe_task(first.id).input_sha256
        assert len(manager.store.list_assets())==3
        receipt=manager.generator.resolve()
        manager.generator.receipt_path.write_text(receipt.model_copy(update={'measured_runtime_sec':2}).model_dump_json())
        with pytest.raises(SceneError,match='runtime or input changed'):
            await manager.submit(request,GENERATION_IDENTITY,retry_of=first.id)
        assert len(host.created)==2
        await manager.stop()
    asyncio.run(scenario())
