# Media Forge public API

Status: MF0 contract candidate
Contract version: `1.0`
Date: 2026-08-21

The API is capability-driven. `model_id` is not required. Normal clients use `model_policy=auto`; an explicit model ID is accepted only with the opt-in `manual` policy.

## Current availability

MF0-3 implements `/health`, `/schemas/{schema_name}`, the local job/capability/
asset APIs below, and a development-only
`/test/health` switch. The switch is disabled unless
`MEDIA_FORGE_ENABLE_TEST_ENDPOINTS=1`.

Workflow, agent, context, and host command contracts are declared for stable
discovery but are not executable yet. Health reports each corresponding
contribution as unavailable with a reason and action.

## Jobs

`POST /api/v1/jobs` accepts [`schemas/job-request.json`](../schemas/job-request.json). MF0-2 executes `image.generate` through a deterministic fake worker. Other operation names are reserved by the public contract and fail with `capability_unavailable` until their goal is delivered.

`GET /api/v1/jobs` lists durable jobs. `GET /api/v1/jobs/{job_id}` returns one job. `DELETE /api/v1/jobs/{job_id}` requests cancellation.

States are `queued`, `running`, `succeeded`, `failed`, and `canceled`. `phase` is an optional execution detail and is not a separate terminal state.

Every request is local-only. `local_only` defaults to `true`; any explicit `false` value is rejected by backend validation.

## Capabilities

`GET /api/v1/capabilities` reports capability state as `available`, `unavailable`, or later `experimental`. MF0-2 reports `image.text_to_image` as available with `implementation=fake` and `confidence=low`; it does not claim a real model is installed or expose the selected fake implementation ID.

## Assets and provenance

- `GET /api/v1/assets`
- `GET /api/v1/assets/{asset_id}`
- `GET /api/v1/assets/{asset_id}/content`
- `GET /api/v1/assets/{asset_id}/provenance`

Asset and provenance documents conform to [`schemas/asset.json`](../schemas/asset.json) and [`schemas/provenance.json`](../schemas/provenance.json). A provenance sidecar is stored next to every immutable asset copy. The SQLite index can be rebuilt in a future maintenance operation without losing the producing facts.

Parentage uses asset IDs only. Host paths are not part of this API.

## Add-on execution endpoints (MF0-6 and later)

ControlDeck calls `/addon/v1/*` endpoints declared by [`addon.json`](../addon.json). Workflow and agent payloads use `{input, correlation}` envelopes. Responses return structured `job_id` and `asset_ids`; agents do not scrape filenames and do not receive a selected model name from generation or capability discovery.

Context actions require a host-issued opaque `grant:` ID. Raw paths are rejected. Project commit is not available before G4.

## Contract evolution

G1 is the freeze point for public schemas, manifest contributions, agent tools, workflow executor types, and required asset/provenance fields. Before that point, changes remain reviewable contract candidates. After G1, additions are preferred; a breaking change requires impact, migration, and version-bump documentation.
