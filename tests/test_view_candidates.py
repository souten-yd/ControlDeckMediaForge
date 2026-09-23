from __future__ import annotations

import asyncio
from io import BytesIO
import json
from pathlib import Path

from fastapi import HTTPException
from PIL import Image, ImageDraw
import pytest
from pydantic import ValidationError

from mediaforge.creative import CreativeValidationError
from mediaforge.creative_batches import CreativeBatchRecord
from mediaforge.domain import JobRequest, JobStatus
from mediaforge.view_candidates import ViewCandidateBatchRequest, ViewCandidateContext
from test_host_execution import host_client
from test_workspace_transport import call


def import_front(client, color=(180, 20, 70, 255)):
    image = Image.new('RGBA', (512, 512))
    ImageDraw.Draw(image).rectangle((120, 60, 360, 470), fill=color)
    data = BytesIO(); image.save(data, format='PNG')
    result = client.post('/api/v1/assets/import?purpose=source', content=data.getvalue(),
                         headers={'Content-Type': 'application/octet-stream'})
    assert result.status_code == 201
    return result.json()


def test_distinct_direction_requests_retain_one_front_and_typed_lineage():
    source = 'asset_' + '1' * 32
    values = ViewCandidateBatchRequest(source_asset_id=source).requests(1024)
    assert len(values) == 3 and len({v['intent'] for v in values}) == 3
    assert [v['constraints']['view_candidate']['direction'] for v in values] == ['right', 'back', 'left']
    for value in values:
        request = JobRequest.model_validate(value)
        assert request.inputs[0].asset_id == source
        assert request.output.count == 1 and request.local_only is True
        assert request.constraints['asset_brief']['alpha_intent'] == 'required'
        assert request.constraints['width'] == request.constraints['height'] == 1024
    schema = json.loads((Path(__file__).parents[1]/'schemas/job-request.json').read_text())
    import jsonschema
    for value in values:
        jsonschema.validate(value, schema)


@pytest.mark.parametrize('change', [
    {'directions': ['right', 'right']}, {'directions': []}, {'directions': ['front']},
    {'source_asset_id': '/tmp/photo.png'}, {'seed': True}, {'seed': 2**31 - 3},
    {'local_only': False}, {'model_path': '/tmp/model'},
])
def test_candidate_request_rejects_ambiguous_or_unsafe_input(change):
    with pytest.raises(ValidationError):
        ViewCandidateBatchRequest.model_validate({'source_asset_id': 'asset_'+'1'*32, **change})


@pytest.mark.parametrize('change', [
    {'inputs': [{'asset_id': 'asset_'+'2'*32}]}, {'operation': 'image.generate', 'inputs': []},
    {'constraints': {'edit_mode': 'variation'}}, {'constraints': {'strict_edit': True}},
])
def test_job_ingress_binds_view_context_to_the_actual_source(change):
    value = ViewCandidateBatchRequest(source_asset_id='asset_'+'1'*32).requests(512)[0]
    if 'constraints' in change:
        value['constraints'].update(change['constraints'])
    else:
        value.update(change)
    with pytest.raises(ValidationError):
        JobRequest.model_validate(value)


def test_source_filtered_history_survives_recent_jobs_and_clearing(tmp_path):
    client, headers, _ = host_client(tmp_path, token='valid-user')
    service = client.app.state.view_candidates
    service.available = lambda: True
    with client:
        front = import_front(client)
        other = import_front(client, (20, 180, 70, 255))
        with client.websocket_connect('/ws', headers=headers) as socket:
            response = call(socket, 'images.views.create', {'source_asset_id': front['id']})
            assert response['ok'], response
            batch = response['result']
            assert len(batch['children']) == 3
            assert len({j['id'] for j in batch['children']}) == 3
            assert len({j['request']['intent'] for j in batch['children']}) == 3
            store = client.app.state.store
            for i in range(105):
                store.create_creative_batch(CreativeBatchRecord(
                    id='batch_'+f'{i:032x}', axis='view', requested_count=1,
                    child_plans=[{'view_candidate': ViewCandidateContext(source_asset_id=other['id'], direction='right').model_dump()}],
                    created_at='2099-01-01', updated_at='2099-01-01',
                ))
            store.clear_finished_jobs()
            response = call(socket, 'images.views.list', {'source_asset_id': front['id']})
            assert response['ok'], response
            assert [v['id'] for v in response['result']['items']] == [batch['id']]
            response = call(socket, 'images.views.list', {'source_asset_id': other['id']})
            assert response['result']['next_offset'] == 10
            assert len(response['result']['items']) == 10
            canceled = call(socket, 'creative.batches.cancel', {'batch_id': batch['id']})
            assert canceled['ok'], canceled


def test_unavailable_editing_rejects_before_batch_or_job(tmp_path):
    client, headers, _ = host_client(tmp_path, token='valid-user')
    with client:
        front = import_front(client)
        store = client.app.state.store
        before = len(store.list_jobs())
        with client.websocket_connect('/ws', headers=headers) as socket:
            response = call(socket, 'images.views.create', {'source_asset_id': front['id']})
        assert response['error']['code'] == 'view_candidate_unavailable'
        assert len(store.list_jobs()) == before
        assert store.list_view_candidate_batches(front['id']) == []


def test_partial_submission_is_persisted_and_successful_child_is_not_lost(tmp_path):
    client, _, _ = host_client(tmp_path, token='valid-user')
    service = client.app.state.view_candidates; service.available = lambda: True
    with client:
        front = import_front(client); store = client.app.state.store
        async def submit(value):
            if value.constraints['view_candidate']['direction'] != 'right':
                raise HTTPException(422, detail={'code': 'fixture_rejection'})
            job = store.create_job(value)
            return store.update_job(job.id, status=JobStatus.SUCCEEDED).model_dump(mode='json')
        result = asyncio.run(service.create({'source_asset_id': front['id']}, submit))
        assert result['state'] == 'partial'
        assert result['succeeded_count'] == 1 and result['failed_count'] == 2
        restored = service.list({'source_asset_id': front['id']})['items'][0]
        assert restored['child_job_ids'] == result['child_job_ids']
        assert [v['message'] for v in restored['submission_errors']] == ['back', 'left']


def test_selection_checks_source_context_pixels_and_deletion(tmp_path):
    client, _, _ = host_client(tmp_path, token='valid-user')
    service = client.app.state.view_candidates
    with client:
        front = import_front(client)
        same = import_front(client)
        different = import_front(client, (20, 180, 70, 255))
        store = client.app.state.store
        # Use stored immutable records as fixtures, not a fake image-quality claim.
        def link(asset):
            prov = store.get_provenance(asset['id'])
            context = ViewCandidateContext(source_asset_id=front['id'], direction='right')
            prov = prov.model_copy(update={'operation': 'image.edit', 'parent_asset_ids': [front['id']],
                'reference_asset_hashes': {front['id']: front['sha256']},
                'parameters': {'constraints': {'view_candidate': context.model_dump()}}})
            with store._connect() as db:
                db.execute('UPDATE assets SET provenance_json=?, metadata_json=? WHERE id=?',
                           (prov.model_dump_json(), json.dumps({**asset, 'parent_asset_ids': [front['id']]}), asset['id']))
        link(same); link(different)
        payload = {'source_asset_id': front['id'], 'asset_id': same['id'], 'direction': 'right'}
        with pytest.raises(CreativeValidationError, match='same image'):
            service.select(payload)
        payload['asset_id'] = different['id']
        result = service.select(payload)
        assert result['quality'] == 'requires_visual_confirmation'
        with pytest.raises(CreativeValidationError, match='current front'):
            service.select({**payload, 'direction': 'back'})
        with pytest.raises(CreativeValidationError, match='current front'):
            service.select({**payload, 'source_asset_id': same['id']})
        original = store.trashed_asset_ids
        store.trashed_asset_ids = lambda: {different['id']}
        try:
            with pytest.raises(CreativeValidationError, match='Trash'):
                service.select(payload)
        finally:
            store.trashed_asset_ids = original
