from __future__ import annotations

import json
from pathlib import Path
import time

from fastapi.testclient import TestClient
import jsonschema
import pytest

from conftest import fake_settings
from mediaforge.app import create_app
from mediaforge.domain import JobStatus
from test_scene_generation_jobs import GENERATION_IDENTITY, manager_fixture


@pytest.mark.parametrize('workflow',[False,True])
def test_image_generation_public_entry_reaches_durable_scene_and_library(tmp_path,workflow):
    fixture,host,value,_=manager_fixture(tmp_path)
    async def authenticate(headers): return GENERATION_IDENTITY
    async def close(): pass
    host.authenticate=authenticate
    host.close=close
    for job in fixture.store.list_jobs():
        if job.status==JobStatus.QUEUED:
            fixture.store.update_job(job.id,status=JobStatus.SUCCEEDED)
    app=create_app(fake_settings(tmp_path/'workspace'),host_client=host)
    manager=app.state.scene_recipe_jobs
    manager.workspace=fixture.workspace
    manager.generator=fixture.generator
    manager.control_poll_sec=0.01
    manager.lease_renew_sec=0.02
    headers={'Authorization':'Bearer fixture','X-Control-Deck-Addon-ID':'media-forge'}
    body=value.model_dump(mode='json')
    if workflow: body['action']='from_image'
    endpoint='/addon/v1/workflow/media.scene/execute' if workflow else '/addon/v1/agent/scene/from-image'
    with TestClient(app) as client:
        schema=client.get('/schemas/scene-from-image-request.json')
        assert schema.status_code==200
        jsonschema.validate(value.model_dump(mode='json'),schema.json())
        response=client.post(endpoint,json={'input':body},headers=headers)
        assert response.status_code==200,response.text
        job_id=response.json()['job_id']
        deadline=time.monotonic()+5
        while True:
            status=client.post('/addon/v1/agent/job/status',json={'input':{'job_id':job_id}},headers=headers)
            assert status.status_code==200,status.text
            if status.json()['status'] in {'failed','canceled','succeeded'}: break
            assert time.monotonic()<deadline
            time.sleep(0.02)
        final=status.json()
        assert final['status']=='succeeded',final
        assert final['operation']=='scene.from_image'
        for asset_id in final['asset_ids']:
            assert client.get('/api/v1/assets/'+asset_id+'/content').status_code==200
            p=client.get('/api/v1/assets/'+asset_id+'/provenance').json()
            assert p['model_id']=='test/model'
        assert len(client.get('/api/v1/assets').json()['items'])==3


def test_schema_and_endpoints_reject_paths_remote_execution_and_unadopted_runtime(tmp_path):
    fixture,host,value,_=manager_fixture(tmp_path)
    async def authenticate(headers): return GENERATION_IDENTITY
    async def close(): pass
    host.authenticate=authenticate;host.close=close
    app=create_app(fake_settings(tmp_path/'empty'),host_client=host)
    with TestClient(app) as client:
        headers={'Authorization':'Bearer fixture','X-Control-Deck-Addon-ID':'media-forge'}
        payload=value.model_dump(mode='json')
        for change in [{'local_only':False},{'model_path':'/etc/passwd'},{'url':'https://example.invalid/input.png'}]:
            r=client.post('/addon/v1/agent/scene/from-image',json={'input':{**payload,**change}},headers=headers)
            assert r.status_code==422
        r=client.post('/addon/v1/agent/scene/from-image',json={'input':payload},headers=headers)
        assert r.status_code==422 and r.json()['detail']['code']=='three_d_runtime_unavailable'
        assert host.created==[]
    root=Path(__file__).parents[1]
    schema=json.loads((root/'schemas/scene-workflow-request.json').read_text())
    jsonschema.validate({'action':'from_image',**value.model_dump(mode='json')},schema)
