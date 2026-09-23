from pathlib import Path

from test_host_execution import generate_input, host_client


def test_accepted_pack_failure_retains_the_same_failed_job(tmp_path: Path) -> None:
    client, headers, _state = host_client(tmp_path, token="valid-job")
    with client:
        response = client.post('/addon/v1/agent/generate', headers=headers, json={
            'input': {'operation': 'asset.pack', 'intent': 'Unsupported pack profile',
                      'inputs': [{'asset_id': 'asset_' + '1' * 32}], 'profile': 'unsupported'},
        })
        assert response.status_code == 502
        detail = response.json()['detail']
        assert detail['code'] == 'unsupported_pack_profile'
        assert detail['status'] == 'failed'
        job = client.app.state.store.get_job(detail['job_id'])
        assert job.status.value == 'failed' and not job.asset_ids
        assert detail['code'] == job.error.code
        assert len(client.get('/api/v1/jobs').json()['items']) == 1
        assert set(detail) == {'code', 'job_id', 'status'}


def test_cleanup_timeout_retains_successful_job_without_claiming_cleanup(tmp_path: Path) -> None:
    client, headers, _state = host_client(tmp_path, token="valid-job")
    with client:
        async def stalled_cleanup(_job_id: str) -> None:
            raise TimeoutError('/private/worker/detail-must-not-leak')

        client.app.state.jobs.wait_cleanup = stalled_cleanup
        response = client.post('/addon/v1/agent/generate', headers=headers,
                               json={'input': generate_input('cleanup failure reference')})
        assert response.status_code == 504
        detail = response.json()['detail']
        assert detail['code'] == 'job_cleanup_timeout'
        assert detail['status'] == 'succeeded'
        job = client.app.state.store.get_job(detail['job_id'])
        assert job.status.value == 'succeeded' and len(job.asset_ids) == 1
        assert '/private' not in response.text


def test_pre_admission_validation_does_not_invent_a_job_reference(tmp_path: Path) -> None:
    client, headers, _state = host_client(tmp_path, token="valid-job")
    with client:
        response = client.post('/addon/v1/agent/generate', headers=headers, json={
            'input': {'operation': 'asset.pack', 'intent': 'Missing input'},
        })
        assert response.status_code == 422
        assert 'job_id' not in response.json()['detail']
        assert not client.get('/api/v1/jobs').json()['items']
