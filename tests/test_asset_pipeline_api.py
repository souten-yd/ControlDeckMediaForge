from conftest import wait_terminal
from test_host_execution import host_client
from pathlib import Path


def test_prompt_pipeline_creates_an_image_job_through_the_host_contract(tmp_path):
    client, headers, _ = host_client(tmp_path)
    with client:
        response = client.post('/addon/v1/agent/pipeline/start', headers=headers, json={
            'input': {'name': 'Prompt pipeline contract', 'prompt': 'a red robot',
                      'width': 256, 'height': 256, 'mode': 'confirm'},
        })
        assert response.status_code == 200, response.json()
        pipeline = response.json()
        job = wait_terminal(client, pipeline['stages'][0]['job_id'])
        assert job['status'] == 'succeeded', job.get('error')
        assert job['request']['operation'] == 'image.generate'
        assert job['request']['constraints']['width'] == 256
        assert job['request']['constraints']['height'] == 256
        polled = client.post('/addon/v1/agent/pipeline/status', headers=headers,
                             json={'input': {'pipeline_id': pipeline['id']}})
        assert polled.status_code == 200, polled.json()
        assert polled.json()['state'] == 'awaiting_approval'
        assert polled.json()['stages'][0]['asset_id'] == job['asset_ids'][0]
        # Different ordinary Host actors cannot read or approve the chain.
        other = {**headers, 'Authorization': 'Bearer valid-other'}
        denied = client.post('/addon/v1/agent/pipeline/status', headers=other,
                             json={'input': {'pipeline_id': pipeline['id']}})
        assert denied.status_code == 404
        health = client.get('/health').json()['contributions']
        assert health['agent_tool:media.pipeline.start'] == 'available'
        assert health['agent_tool:media.pipeline.status'] == 'available'


def test_explicit_pipeline_retry_uses_expected_failed_job_and_actor(tmp_path: Path) -> None:
    client, headers, state = host_client(tmp_path, token='valid-user')
    state['reject_resources'] = True
    with client:
        response = client.post('/addon/v1/agent/pipeline/start', headers=headers, json={
            'input': {'name': 'Retry contract', 'prompt': 'a red robot',
                      'width': 256, 'height': 256, 'mode': 'confirm'},
        })
        assert response.status_code == 200
        pipeline = response.json()
        original = pipeline['stages'][0]['job_id']
        assert wait_terminal(client, original)['status'] == 'failed'
        url = '/addon/v1/agent/pipeline/status'
        assert client.post(url, headers=headers, json={'input': {'pipeline_id': pipeline['id']}}).json()['state'] == 'failed'
        retry = {'pipeline_id': pipeline['id'], 'action': 'retry', 'expected_job_id': original}
        assert client.post(url, headers={**headers, 'Authorization': 'Bearer valid-other'},
                           json={'input': retry}).status_code == 404
        state['reject_resources'] = False
        response = client.post(url, headers=headers, json={'input': retry})
        assert response.status_code == 200, response.json()
        newer = response.json()['stages'][0]
        assert newer['job_id'] != original and newer['failed_attempts'][0]['job_id'] == original
        assert wait_terminal(client, newer['job_id'])['status'] == 'succeeded'
        assert client.post(url, headers=headers, json={'input': retry}).status_code == 409
        value = client.post(url, headers=headers, json={'input': {'pipeline_id': pipeline['id']}}).json()
        assert value['state'] == 'awaiting_approval'
        assert value['stages'][1]['job_id'] is None
