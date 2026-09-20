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
from mediaforge.three_d_runtime import ThreeDGenerator
from test_three_d_runtime import native_runtime
from test_pixal_runtime import pixal_runtime

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


def manager_fixture(tmp_path,mode='success',engine='trellis_cpp'):
    data=setup(tmp_path/'workspace')
    store,workspace,resolver,request,*_=data
    resolver.resolve_active=lambda: resolver.runtime
    runtime_root=tmp_path/'native';runtime_root.mkdir()
    if engine == 'pixal3d':
        generator,receipt=pixal_runtime(runtime_root,allowed_root=tmp_path,
            fault='' if mode=='success' else 'sleep_prepare' if mode=='preparation' else 'sleep_generate')
        request=request.model_copy(update={'engine':'pixal3d','seed':16777217})
    else:
        generator,receipt=native_runtime(runtime_root,script="pathlib.Path('pid').write_text(str(os.getpid()))\ntime.sleep(0.1)\n" if mode=='success' else "pathlib.Path('pid').write_text(str(os.getpid()))\ntime.sleep(60)\n")
    host=ResourceHost(mode)
    manager=SceneRecipeJobManager(store,workspace,host,generator=generator,
        control_poll_sec=0.01,lease_renew_sec=0.02,resource_poll_sec=0.01)
    return manager,host,request,receipt


@pytest.mark.parametrize('engine',['trellis_cpp','pixal3d'])
def test_image_generation_uses_child_lease_existing_scene_library_and_provenance(tmp_path,engine):
    async def scenario():
        manager,host,request,receipt=manager_fixture(tmp_path,engine=engine)
        if engine == 'pixal3d':
            original_request=host.request_resource
            async def after_preparation(identity,payload):
                roots=list(manager.workspace.recipe_root.glob('native_*/stage1'))
                assert len(roots)==1 and (roots[0]/'pixal-prepared/ready.json').exists()
                pid=int((roots[0]/'prepare.started').read_text())
                assert not Path(f'/proc/{pid}').exists()
                assert not (roots[0]/'generate.started').exists()
                return await original_request(identity,payload)
            host.request_resource=after_preparation
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
        if engine == 'pixal3d':
            assert source.parameters['generation']['execution']['preprocessing_backend']=='cpu'
            assert source.parameters['generation']['execution']['backend']=='vulkan'
            assert source.seed==16777217
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
@pytest.mark.parametrize('engine',['trellis_cpp','pixal3d'])
def test_cancellation_cleans_pending_admission_or_worker_before_release(tmp_path,stage,engine):
    async def scenario():
        manager,host,request,_=manager_fixture(tmp_path,stage,engine)
        job,_=await manager.submit(request,GENERATION_IDENTITY)
        await asyncio.wait_for(host.requested.wait(),2)
        if stage in {'waiting', 'request'}:
            assert not manager._execution_guard.locked()
        if stage=='worker':
            for _ in range(200):
                pids=list(manager.workspace.recipe_root.glob('native_*/stage1/'+('generate.started' if engine=='pixal3d' else 'pid')))
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
@pytest.mark.parametrize('engine',['trellis_cpp','pixal3d'])
def test_invalid_grant_or_lost_lease_fails_without_publishing(tmp_path,mode,code,engine):
    async def scenario():
        manager,host,request,_=manager_fixture(tmp_path,mode,engine)
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


@pytest.mark.parametrize('engine',['trellis_cpp','pixal3d'])
def test_generation_checks_capability_and_adoption_before_host_admission(tmp_path,engine):
    async def scenario():
        manager,host,request,_=manager_fixture(tmp_path,engine=engine)
        with pytest.raises(SceneError,match='resources.acquire'):
            await manager.submit(request,IDENTITY)
        (manager.generator.pixal_receipt_path if engine=='pixal3d' else manager.generator.receipt_path).unlink()
        with pytest.raises(SceneError,match='unavailable'):
            await manager.submit(request,GENERATION_IDENTITY)
        assert host.created==[] and host.events==[]
    asyncio.run(scenario())


@pytest.mark.parametrize('engine',['trellis_cpp','pixal3d'])
def test_generation_retry_preserves_identity_and_can_publish_after_bad_grant(tmp_path,engine):
    async def scenario():
        manager,host,request,_=manager_fixture(tmp_path,engine=engine)
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
        path=manager.generator.pixal_receipt_path if engine=='pixal3d' else manager.generator.receipt_path
        path.write_text(receipt.model_copy(update={'measured_runtime_sec':2}).model_dump_json())
        with pytest.raises(SceneError,match='runtime or input changed'):
            await manager.submit(request,GENERATION_IDENTITY,retry_of=first.id)
        assert len(host.created)==2
        await manager.stop()
    asyncio.run(scenario())


def test_pixal_preparation_cancel_creates_no_gpu_request(tmp_path):
    async def scenario():
        manager,host,request,_=manager_fixture(tmp_path,'preparation','pixal3d')
        job,_=await manager.submit(request,GENERATION_IDENTITY)
        for _ in range(200):
            pids=list(manager.workspace.recipe_root.glob('native_*/stage1/prepare.started'))
            if pids: break
            await asyncio.sleep(.01)
        assert pids and host.events==[]
        assert manager.store.get_job(job.id).phase=='prepare_3d_input'
        pid=int(pids[0].read_text())
        await manager.cancel(job.id,'user:7')
        await manager.wait_cleanup(job.id)
        assert manager.store.get_job(job.id).status==JobStatus.CANCELED
        assert host.events==[] and not Path(f'/proc/{pid}').exists()
        assert len(manager.store.list_assets())==1 and list(manager.workspace.recipe_root.iterdir())==[]
        await manager.stop()
    asyncio.run(scenario())


def test_pixal_adoption_changed_while_admission_pending_releases_without_activation(tmp_path):
    async def scenario():
        manager,host,request,receipt=manager_fixture(tmp_path,'request','pixal3d')
        job,_=await manager.submit(request,GENERATION_IDENTITY)
        await asyncio.wait_for(host.requested.wait(),2)
        manager.generator.pixal_receipt_path.write_text(receipt.model_copy(update={'measured_runtime_sec':2}).model_dump_json())
        host.allow_response.set()
        await manager.wait_cleanup(job.id)
        final=manager.store.get_job(job.id)
        assert final.status==JobStatus.FAILED and final.error.code=='three_d_runtime_changed'
        assert host.events==['request','release']
        assert len(manager.store.list_assets())==1 and list(manager.workspace.recipe_root.iterdir())==[]
        await manager.stop()
    asyncio.run(scenario())


def test_gpu_lease_keeps_renewing_until_canceled_worker_finishes_cleanup(tmp_path):
    async def scenario():
        manager,host,request,_=manager_fixture(tmp_path)
        running=asyncio.Event();cleaning=asyncio.Event();allow_cleanup=asyncio.Event()
        async def generation(*args,**kwargs):
            running.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaning.set()
                await allow_cleanup.wait()
        manager.generator.generate=generation
        job,_=await manager.submit(request,GENERATION_IDENTITY)
        await asyncio.wait_for(running.wait(),2)
        cancellation=asyncio.create_task(manager.cancel(job.id,'user:7'))
        await asyncio.wait_for(cleaning.wait(),2)
        before=host.events.count('renew')
        await asyncio.sleep(.08)
        assert host.events.count('renew')>before and 'release' not in host.events
        assert not cancellation.done()
        allow_cleanup.set()
        await asyncio.wait_for(cancellation,2)
        await manager.wait_cleanup(job.id)
        assert host.events[-1]=='release' and manager.store.get_job(job.id).status==JobStatus.CANCELED
        await manager.stop()
    asyncio.run(scenario())


def refine_fixture(tmp_path, *, pixal_fault=''):
    """trellis.cpp のあとに Pixal3D を足した、2 段の採用を 1 つの generator で持つ。

    実機と同じく段ごとに測った解像度が違う（trellis.cpp 512 / Pixal3D 1024）。
    1 段目の解像度を 2 段目へ押し付けると、選べるのに必ず落ちる組み合わせになる。
    """
    data=setup(tmp_path/'workspace')
    store,workspace,resolver,request,*_=data
    resolver.resolve_active=lambda: resolver.runtime
    runtime_root=tmp_path/'native';runtime_root.mkdir()
    _,native=native_runtime(runtime_root,script="time.sleep(0.05)\n")
    (runtime_root/'receipt.json').write_text(
        native.model_copy(update={'evaluated_resolution':512}).model_dump_json())
    pixal_runtime(runtime_root,allowed_root=tmp_path,fault=pixal_fault)
    generator=ThreeDGenerator(runtime_root/'receipt.json',
        pixal_receipt_path=runtime_root/'pixal3d-runtime.json')
    request=request.model_copy(update={'engine':'trellis_cpp','refine_with_pixal3d':True,'resolution':512})
    host=ResourceHost()
    manager=SceneRecipeJobManager(store,workspace,host,generator=generator,
        control_poll_sec=0.01,lease_renew_sec=0.02,resource_poll_sec=0.01)
    return manager,host,request


def test_requested_pixal_stage_runs_after_trellis_and_keeps_both_revisions(tmp_path):
    """「Pixal3D まで実行する」は、1 段目を捨てずに同じシーンの次の版にする。"""
    async def scenario():
        manager,host,request=refine_fixture(tmp_path)
        job,_=await manager.submit(request,GENERATION_IDENTITY)
        await manager.wait_cleanup(job.id)
        final=manager.store.get_job(job.id)
        assert final.status==JobStatus.SUCCEEDED, final.error
        result=manager.projection(job.id,'user:7')['result']
        assert result['refine']=={'state':'succeeded','engine':'pixal3d','reason':None}
        # 版は 2 つ。現在の版は Pixal3D の側である。
        assert result['scene']['revision_count']==2
        assert result['revision']['sequence']==2
        assert result['scene']['current_revision_id']==result['revision']['id']
        assert result['generation']['runtime_adapter']=='pixal3d'
        # 段ごとに測った解像度で走る。1 段目 512 / 2 段目 1024。
        assert result['generation']['resolution']==1024
        first={manager.store.get_provenance(a).parameters['generation']['resolution']
               for a in final.asset_ids
               if manager.store.get_provenance(a).runtime_adapter=='native.trellis-cpp'}
        assert first=={512}
        # 1 段目の Asset も残る。並べて比べられることが、選ぶ理由である。
        assert len(final.asset_ids)==4
        adapters={manager.store.get_provenance(a).runtime_adapter for a in final.asset_ids}
        assert adapters=={'native.trellis-cpp','pixal3d'}
        # 2段目は1段目の.blendからではなく同じ入力画像から作られている。
        # 版の親子はcatalogが持つ。Assetのlineageに前段を親として入れない。
        blends=[a for a in final.asset_ids
                if manager.store.get_asset(a).mime_type=='application/x-blender']
        assert len(blends)==2
        for asset_id in blends:
            assert manager.store.get_provenance(asset_id).parent_asset_ids==[request.input_asset_id]
        # 段ごとに lease を取り、段ごとに返している。またいで握らない。
        assert host.events.count('activate')==2 and host.events.count('release')==2
        assert list(manager.workspace.recipe_root.iterdir())==[]
        await manager.stop()
    asyncio.run(scenario())


def test_failed_pixal_stage_keeps_the_published_trellis_scene_and_says_why(tmp_path):
    """追加の段が落ちても、既定の段の成果物は残す。落ちたことは黙らせない。"""
    async def scenario():
        manager,host,request=refine_fixture(tmp_path,pixal_fault='fail_generate')
        job,_=await manager.submit(request,GENERATION_IDENTITY)
        await manager.wait_cleanup(job.id)
        final=manager.store.get_job(job.id)
        assert final.status==JobStatus.SUCCEEDED, final.error
        result=manager.projection(job.id,'user:7')['result']
        assert result['refine']['state']=='failed'
        assert result['refine']['reason']=='three_d_generation_failed'
        assert result['scene']['revision_count']==1
        assert result['generation']['runtime_adapter']=='native.trellis-cpp'
        assert len(final.asset_ids)==2
        assert host.events.count('release')==2
        assert list(manager.workspace.recipe_root.iterdir())==[]
        await manager.stop()
    asyncio.run(scenario())


def test_unadopted_pixal_stage_is_refused_at_admission(tmp_path):
    """足せない段を黙って落とさない。受付で理由を返す。"""
    async def scenario():
        manager,host,request=refine_fixture(tmp_path)
        manager.generator.pixal_receipt_path.unlink()
        with pytest.raises(SceneError,match='3D runtime is unavailable|has not been adopted|unavailable'):
            await manager.submit(request,GENERATION_IDENTITY)
        assert host.created==[]
        await manager.stop()
    asyncio.run(scenario())
