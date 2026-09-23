"""Persist candidate groups in the existing CreativeBatch and image Job stores."""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException

from .creative import CreativeValidationError
from .creative_batches import CreativeBatchRecord, project_batch
from .domain import JobRequest
from .multiview_inputs import InvalidViews, image_identity
from .jobs import ProfileResolutionError
from .store import Store, utc_now
from .view_candidates import (
    ViewCandidateBatchRequest, ViewCandidateContext, ViewCandidateListRequest, ViewCandidateSelection,
)


class ViewCandidateService:
    def __init__(self, store: Store, available: Callable[[], bool], envelope: Callable[[], dict[str, Any]]) -> None:
        self.store = store
        self.available = available
        self.envelope = envelope

    def _image(self, asset_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if asset_id in self.store.trashed_asset_ids():
            raise CreativeValidationError("view_candidate_deleted", "Restore the image from Trash before using it.")
        asset = self.store.get_asset(asset_id)
        try:
            identity = image_identity(self.store.asset_path(asset_id), allow_webp=True)
        except (InvalidViews, OSError, ValueError) as exc:
            raise CreativeValidationError("view_candidate_image_invalid", "Use a square RGBA image with a transparent background.") from exc
        if identity['sha256'] != asset.sha256:
            raise CreativeValidationError("view_candidate_image_changed", "The stored image content has changed.")
        return asset.model_dump(mode="json"), identity

    async def create(
        self, payload: dict[str, Any], submit: Callable[[JobRequest], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        request = ViewCandidateBatchRequest.model_validate(payload)
        if not self.available():
            raise CreativeValidationError("view_candidate_unavailable", "Single-reference image editing is unavailable.")
        _asset, identity = await asyncio.to_thread(self._image, request.source_asset_id)
        size = identity['size'][0]
        envelope = self.envelope()
        if (not int(envelope['min_side']) <= size <= int(envelope['max_side'])
                or size % int(envelope['multiple_of']) or size * size > int(envelope['max_pixels'])):
            raise CreativeValidationError("view_candidate_canvas_unsupported", "The reference canvas is outside the installed image editor's supported size.")
        children = [JobRequest.model_validate(value) for value in request.requests(size)]
        now = utc_now()
        record = self.store.create_creative_batch(CreativeBatchRecord(
            id=f"batch_{uuid.uuid4().hex}", axis="view", requested_count=len(children),
            child_plans=[{"view_candidate": value.constraints['view_candidate']} for value in children],
            created_at=now, updated_at=now,
        ))
        for child in children:
            try:
                job = await submit(child)
                record.child_job_ids.append(str(job['id']))
            except (HTTPException, ProfileResolutionError, KeyError, ValueError) as exc:
                code = (str(exc.detail.get('code', 'batch_child_submission_failed'))
                        if isinstance(exc, HTTPException) and isinstance(exc.detail, dict)
                        else getattr(exc, 'code', 'batch_child_submission_failed'))
                record.submission_errors.append({'code': code, 'message': child.constraints['view_candidate']['direction']})
            record.updated_at = utc_now()
            self.store.update_creative_batch(record)
        return self.project(record)

    def project(self, record: CreativeBatchRecord) -> dict[str, Any]:
        jobs = []
        for job_id in record.child_job_ids:
            try:
                jobs.append(self.store.get_job(job_id))
            except KeyError:
                continue
        value = project_batch(record, jobs)
        deleted = self.store.trashed_asset_ids()
        # Keep the successful Job's history intact; omit removed assets only
        # from this selection projection, never from its immutable record.
        value['selectable_asset_ids'] = [aid for aid in value['asset_ids'] if aid not in deleted]
        return value

    def list(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = ViewCandidateListRequest.model_validate(payload)
        source = self.store.get_asset(request.source_asset_id)
        records = self.store.list_view_candidate_batches(request.source_asset_id, request.offset)
        return {'source_asset_id': request.source_asset_id, 'source': source.model_dump(mode='json'),
                'items': [self.project(record) for record in records[:10]],
                'next_offset': request.offset + 10 if len(records) > 10 else None}

    def select(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = ViewCandidateSelection.model_validate(payload)
        _source, source_identity = self._image(request.source_asset_id)
        asset, identity = self._image(request.asset_id)
        provenance = self.store.get_provenance(request.asset_id)
        context = ViewCandidateContext.model_validate(provenance.parameters.get('constraints', {}).get('view_candidate'))
        if (context.source_asset_id != request.source_asset_id or context.direction != request.direction
                or asset['parent_asset_ids'] != [request.source_asset_id]
                or provenance.operation != 'image.edit' or provenance.parent_asset_ids != [request.source_asset_id]
                or provenance.reference_asset_hashes.get(request.source_asset_id) != source_identity['sha256']):
            raise CreativeValidationError("view_candidate_source_mismatch", "Choose a candidate made from the current front image.")
        if identity['size'] != source_identity['size']:
            raise CreativeValidationError("view_candidate_canvas_mismatch", "The candidate and front image must have the same canvas.")
        if identity['premultiplied_pixels_sha256'] == source_identity['premultiplied_pixels_sha256']:
            raise CreativeValidationError("view_candidate_duplicate", "This candidate is the same image as the front.")
        return {'asset': asset, 'context': context.model_dump(mode='json'),
                'quality': 'requires_visual_confirmation', 'calibration': 'not_inferred'}
