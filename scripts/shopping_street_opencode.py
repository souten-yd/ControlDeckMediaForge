#!/usr/bin/env python3
"""Run bounded OpenCode acceptance through ordinary authenticated Host HTTP.

No Host imports, credential issuance, direct inference, or repeated submissions.
The receipt identifies the same Host job across observation timeouts/restarts.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any
from urllib.parse import urlsplit

import httpx

from scripts.g9_operator_session import SessionError, operator_client

TERMINAL = {'succeeded', 'failed', 'canceled', 'cancelled', 'interrupted'}
DEFAULT_SESSION = Path('/data1tb/ControlDeck/data/feature-data/media-forge/maintenance/g9-operator-auth')
DEFAULT_PROJECT_ROOT = Path('/data1tb/ControlDeck/CodeDEV')


class RunError(RuntimeError):
    """Only fixed, credential-free messages are returned to the caller."""


def write_json(path: Path, value: dict[str, Any], *, exclusive: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_EXCL, 0o600)
    else:
        fd, name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
        temporary = Path(name)
    try:
        with os.fdopen(fd, 'w') as output:
            os.fchmod(output.fileno(), 0o600)
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        if temporary is not None:
            os.replace(temporary, path)
        directory = os.open(path.parent, os.O_DIRECTORY | os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)



def response_json(response: httpx.Response) -> dict[str, Any]:
    if response.status_code >= 400:
        raise RunError(f'host_http_{response.status_code}')
    value = response.json()
    if not isinstance(value, dict):
        raise RunError('host_response_not_object')
    return value


def preflight(client: httpx.Client) -> dict[str, str]:
    identity = response_json(client.get('/api/v1/auth/me'))
    if not {'terminal.use', 'workflows.edit', 'workflows.run'} <= set(identity.get('permissions', [])):
        raise RunError('host_project_and_run_permissions_required')
    status = response_json(client.get('/api/v1/opencode/status'))
    settings = status.get('settings', {})
    endpoint, model = str(settings.get('base_url', '')), str(settings.get('model', ''))
    parsed = urlsplit(endpoint)
    origin = urlsplit(str(client.base_url))
    if (parsed.scheme != origin.scheme or parsed.hostname != origin.hostname or parsed.port != origin.port
            or parsed.path.rstrip('/') != '/api/v1/llm/v1'
            or parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise RunError('configured_local_host_gateway_required')
    if model == 'auto':
        # Pin this run to the requested registered local model; never change
        # global OpenCode settings or let gateway priority select another model.
        response = client.get('/api/v1/models/llama/instances')
        if response.status_code != 200:
            raise RunError(f'host_http_{response.status_code}')
        instances = response.json()
        if not isinstance(instances, list):
            raise RunError('local_model_instances_invalid')
        candidates = [item for item in instances if isinstance(item, dict)
                      and re.fullmatch(r'.*qwen38.*27b.*', re.sub('[^a-z0-9]', '', str(item.get('alias', '')).lower()))
                      and re.fullmatch(r'.*qwen38.*27b.*', re.sub('[^a-z0-9]', '', Path(str(item.get('model_path', ''))).name.lower()))
                      and item.get('runtime') == 'llama.cpp']
        if len(candidates) != 1:
            raise RunError('unique_registered_qwen38_27b_required')
        model = candidates[0]['alias']
    normalized = re.sub('[^a-z0-9]', '', model.lower())
    if not re.fullmatch(r'.*qwen38.*27b.*', normalized):
        raise RunError('configured_qwen38_27b_required_no_automatic_substitution')
    feature = status.get('feature', {})
    if feature.get('installed') is not True or feature.get('enabled') is not True:
        raise RunError('opencode_runtime_not_enabled')
    return {'base_url': endpoint, 'model': model, 'runtime': str(status.get('active_runtime', ''))}


def start(
    client: httpx.Client, *, project: str, project_root: Path, prompt: str, receipt: Path,
) -> dict[str, Any]:
    if not re.fullmatch(r'MF3DS-[A-Za-z0-9_-]{1,58}', project):
        raise RunError('dedicated_project_name_required')
    if not prompt.strip() or len(prompt) > 32000:
        raise RunError('prompt_must_have_1_to_32000_characters')
    if receipt.exists() or receipt.is_symlink():
        raise RunError('receipt_exists_observe_the_original_job')
    settings = preflight(client)
    # The project path is operator-supplied locally, never taken from a Host
    # response or forwarded into a MediaForge asset/execution request.
    project_path = project_root / project
    if project_root.resolve() != project_root or project_path.is_symlink():
        raise RunError('project_root_must_be_canonical')
    response_json(client.post('/api/v1/opencode/projects', json={'name': project}))
    if not project_path.is_dir() or project_path.resolve().parent != project_root:
        raise RunError('host_project_root_differs_from_local_project_root')
    state: dict[str, Any] = {'schema': 1, 'project': project, 'model': settings['model'],
                             'runtime': settings['runtime'], 'state': 'submission_unknown'}
    # Persist before POST: a lost response cannot be mistaken for no submission.
    write_json(receipt, state, exclusive=True)
    try:
        created = response_json(client.post('/api/v1/opencode/run', json={
            'operation': 'implement', 'project_path': str(project_path), 'instruction': prompt,
            'base_url': settings['base_url'], 'model': settings['model'],
        }))
        job_id = created.get('job_id')
        if not isinstance(job_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', job_id):
            raise RunError('host_job_identifier_missing')
        state.update(job_id=job_id, state='submitted')
        write_json(receipt, state)
    except (httpx.HTTPError, RunError, ValueError):
        # Keep submission_unknown; manual inspection must resolve ambiguity.
        raise RunError('submission_not_confirmed_do_not_submit_again') from None
    return state


def observe(client: httpx.Client, receipt: Path) -> dict[str, Any]:
    state = json.loads(receipt.read_text())
    job_id = state.get('job_id')
    if not isinstance(job_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', job_id):
        raise RunError('submission_unknown_inspect_host_jobs_without_resubmitting')
    # An HTTP failure leaves the last known receipt unchanged, including a
    # running state. Only the authoritative response can establish termination.
    job = response_json(client.get(f'/api/v1/jobs/{job_id}'))
    status = job.get('status')
    if status not in TERMINAL | {'queued', 'pending', 'running', 'canceling'}:
        raise RunError('host_job_status_not_recognized')
    state.update(state=status, terminal=status in TERMINAL)
    write_json(receipt, state)
    # Do not print the Host's event/output bodies; tool arguments may be private.
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'start', 'status'))
    parser.add_argument('--session-dir', type=Path, default=DEFAULT_SESSION)
    parser.add_argument('--project', default='MF3DS-ShoppingStreet-20260923')
    parser.add_argument('--project-root', type=Path, default=DEFAULT_PROJECT_ROOT)
    parser.add_argument('--prompt-file', type=Path)
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if args.action != 'preflight' and args.receipt is None:
        parser.error('--receipt is required for start/status')
    if args.action == 'start' and args.prompt_file is None:
        parser.error('--prompt-file is required for start')
    try:
        with operator_client(args.session_dir) as client:
            if args.action == 'preflight':
                result: dict[str, Any] = preflight(client)
            elif args.action == 'start':
                result = start(client, project=args.project, project_root=args.project_root,
                               prompt=args.prompt_file.read_text(), receipt=args.receipt)
            else:
                result = observe(client, args.receipt)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except SessionError as error:
        print(json.dumps({'error': str(error)}))
    except RunError as error:
        print(json.dumps({'error': str(error)}))
    except FileNotFoundError:
        print(json.dumps({'error': 'required_private_session_or_input_file_missing'}))
    except (OSError, ValueError, httpx.HTTPError):
        print(json.dumps({'error': 'observation_or_input_failed_no_automatic_resubmission'}))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
