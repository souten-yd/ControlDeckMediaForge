from __future__ import annotations

import asyncio
from dataclasses import replace
import time

import httpx
import pytest

from mediaforge.host.client import ControlDeckHostClient, HostApiError, HostIdentity
from mediaforge.host.jobs import HostExecution, ProgressGate
from mediaforge.jobs import JobManager
from test_host_execution import generate_input, host_client
from conftest import wait_terminal


@pytest.mark.parametrize("change", [None, "subject", "actor", "capabilities", "expired", "malformed", "denied"])
def test_job_refresh_validates_scope_and_never_reissues_expired(change):
    async def run():
        calls=[]
        async def respond(request):
            calls.append(request)
            if request.url.path.endswith('/credential/refresh'):
                if change=='denied':
                    return httpx.Response(403)
                return httpx.Response(200,json={'token_type':'Bearer','access_token':'bad token' if change=='malformed' else 'fresh'})
            return httpx.Response(200,json={'active':True,'addon_id':'media-forge',
                'subject':'other' if change=='subject' else 'job:parent',
                'actor_subject':'user:8' if change=='actor' else 'user:7',
                'expires_at':int(time.time())+600,
                'granted_capabilities':['jobs.write','files.export'] if change=='capabilities' else ['jobs.write']})
        client=ControlDeckHostClient('http://host',transport=httpx.MockTransport(respond))
        identity=HostIdentity('Bearer old','media-forge','job:parent',int(time.time())+(-10 if change=='expired' else 60),frozenset({'jobs.write'}),'user:7')
        try:
            if change is None:
                refreshed=await client.refresh_job_identity(identity,'parent')
                assert refreshed.authorization=='Bearer fresh' and refreshed.subject==identity.subject
                assert refreshed.actor_subject==identity.actor_subject and identity.authorization=='Bearer old'
            else:
                with pytest.raises(HostApiError):
                    await client.refresh_job_identity(identity,'parent')
            assert len(calls)==(0 if change=='expired' else 1 if change in {'malformed','denied'} else 2)
        finally:
            await client.close()
    asyncio.run(run())


def test_concurrent_refresh_preserves_attached_ownership_and_progress():
    async def run():
        manager=object.__new__(JobManager)
        class Host:
            calls=0
            async def refresh_job_identity(self, identity, host_job_id):
                self.calls+=1
                await asyncio.sleep(.01)
                assert host_job_id=='parent'
                return replace(identity,expires_at=int(time.time())+600)
        manager.host_client=Host()
        gate=ProgressGate()
        execution=HostExecution(HostIdentity('Bearer test','media-forge','job:parent',int(time.time())+60,frozenset()),
            'parent','workflow',False,progress_gate=gate,progress_offset=.5,progress_span=.25)
        await asyncio.gather(*(manager._refresh_host_identity(execution) for _ in range(3)))
        assert manager.host_client.calls==1
        assert not execution.owns_terminal and execution.progress_gate is gate
        assert execution.progress_offset==.5 and execution.progress_span==.25
    asyncio.run(run())


def test_waiting_image_renews_before_lease_and_reports_with_new_identity(tmp_path,monkeypatch):
    client,headers,state=host_client(tmp_path,token='valid-user')
    manager=client.app.state.jobs
    host=manager.host_client
    original_request=host.request_resource
    original_update=host.update_job
    seen=[]
    async def request(identity,payload):
        granted=await original_request(identity,payload)
        execution=next(iter(manager._host_executions.values()))
        execution.identity=replace(execution.identity,expires_at=int(time.time())+60)
        return {**granted,'state':'waiting','lease_id':None}
    async def update(identity,job_id,payload):
        if payload.get('status'):
            seen.append(identity.authorization)
        return await original_update(identity,job_id,payload)
    monkeypatch.setattr(host,'request_resource',request)
    monkeypatch.setattr(host,'update_job',update)
    with client:
        with client.websocket_connect('/ws',headers=headers) as socket:
            socket.send_json({'id':'wait','method':'jobs.create','params':generate_input('waiting image')})
            created=socket.receive_json()['result']
            assert wait_terminal(client,created['id'])['status']=='succeeded'
            assert state['job_credential_refreshes']==['host-created-1']
    assert seen==['Bearer valid-refreshed']
    assert 'release' in [action for _,action in state['lease_actions']]
