from pathlib import Path
import json

import httpx
import pytest

from scripts.shopping_street_opencode import RunError, observe, preflight, start


def client_for(root: Path, *, model: str = 'Qwen3.8-27B-Q8_0', timeout: bool = False):
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith('/auth/me'):
            return httpx.Response(200, json={'permissions': ['workflows.run', 'workflows.edit', 'terminal.use']})
        if request.url.path.endswith('/opencode/status'):
            return httpx.Response(200, json={'settings': {
                'base_url': 'http://127.0.0.1:8765/api/v1/llm/v1', 'model': model},
                'active_runtime': 'v1', 'feature': {'installed': True, 'enabled': True}})
        if request.url.path.endswith('/models/llama/instances'):
            return httpx.Response(200, json=[{'alias': 'Qwen3.8-27B', 'runtime': 'llama.cpp',
                'model_path': '/models/Qwen3.8-27B-UD-Q4_K_M.gguf'}])
        if request.url.path.endswith('/opencode/projects'):
            name = json.loads(request.content)['name']
            (root / name).mkdir(exist_ok=True)
            return httpx.Response(201, json={'path': '/untrusted/path/is/not/used'})
        if request.url.path.endswith('/opencode/run'):
            value = json.loads(request.content)
            assert value['project_path'] == str(root / 'MF3DS-test')
            if timeout:
                raise httpx.ReadTimeout('response was lost', request=request)
            return httpx.Response(202, json={'job_id': 'job_123'})
        if request.url.path.endswith('/jobs/job_123'):
            return httpx.Response(200, json={'status': 'succeeded', 'result': {'output': 'private output'}})
        raise AssertionError(request.url.path)

    return httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(handle)), calls


def test_submits_once_then_observes_same_host_job(tmp_path):
    client, calls = client_for(tmp_path)
    receipt = tmp_path / 'receipt.json'
    with client:
        result = start(client, project='MF3DS-test', project_root=tmp_path, prompt='Use MCP', receipt=receipt)
        assert result['job_id'] == 'job_123'
        assert receipt.stat().st_mode & 0o777 == 0o600
        assert observe(client, receipt)['terminal'] is True
        with pytest.raises(RunError, match='observe_the_original_job'):
            start(client, project='MF3DS-test', project_root=tmp_path, prompt='Use MCP', receipt=receipt)
    assert calls.count(('POST', '/api/v1/opencode/run')) == 1
    assert 'private output' not in receipt.read_text()
    assert all(method != 'PUT' for method, _ in calls)


def test_lost_submission_response_never_causes_duplicate_generation(tmp_path):
    client, calls = client_for(tmp_path, timeout=True)
    receipt = tmp_path / 'receipt.json'
    with client:
        with pytest.raises(RunError, match='do_not_submit_again'):
            start(client, project='MF3DS-test', project_root=tmp_path, prompt='Use MCP', receipt=receipt)
        assert json.loads(receipt.read_text())['state'] == 'submission_unknown'
        with pytest.raises(RunError, match='observe_the_original_job'):
            start(client, project='MF3DS-test', project_root=tmp_path, prompt='Use MCP', receipt=receipt)
        with pytest.raises(RunError, match='without_resubmitting'):
            observe(client, receipt)
    assert calls.count(('POST', '/api/v1/opencode/run')) == 1


@pytest.mark.parametrize('status', [401, 404, 503])
def test_failed_observation_does_not_turn_running_job_into_terminal(tmp_path, status):
    receipt = tmp_path / 'receipt.json'
    receipt.write_text(json.dumps({'schema': 1, 'job_id': 'job_123', 'state': 'running'}))
    before = receipt.read_bytes()
    with httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json={'detail': 'unavailable'}))) as client:
        with pytest.raises(RunError, match=f'host_http_{status}'):
            observe(client, receipt)
    assert receipt.read_bytes() == before


def test_wrong_model_cannot_be_silently_substituted(tmp_path):
    client, calls = client_for(tmp_path, model='some-other-model')
    with client, pytest.raises(RunError, match='no_automatic_substitution'):
        preflight(client)
    assert all(method == 'GET' for method, _ in calls)


def test_missing_authentication_cannot_create_a_project_or_job(tmp_path):
    calls = []
    def reject(request):
        calls.append(request.method)
        return httpx.Response(401, json={'detail': 'auth required'})
    with httpx.Client(base_url='http://127.0.0.1:8765', transport=httpx.MockTransport(reject)) as client:
        with pytest.raises(RunError, match='host_http_401'):
            start(client, project='MF3DS-test', project_root=tmp_path, prompt='Use MCP', receipt=tmp_path/'receipt.json')
    assert calls == ['GET']
    assert not (tmp_path/'receipt.json').exists()


def test_auto_is_pinned_to_the_registered_requested_model_without_global_change(tmp_path):
    client, calls = client_for(tmp_path, model='auto')
    with client:
        result = preflight(client)
    assert result['model'] == 'Qwen3.8-27B'
    assert all(method == 'GET' for method, _ in calls)
