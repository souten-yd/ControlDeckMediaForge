# Media Forge public API

Status: G1 contract candidate; freeze pending G1 acceptance
Contract version: `1.0`
Date: 2026-08-21

The API is capability-driven. `model_id` is not required. Normal clients use `model_policy=auto`; an explicit model ID is accepted only with the opt-in `manual` policy.

## Current availability

MF0-7 / G0 implements `/health`, `/schemas/{schema_name}`, the local job/capability/
asset/model APIs below, the embedded workspace, and the Add-on execution endpoints. It also provides a development-only
`/test/health` switch. The switch is disabled unless
`MEDIA_FORGE_ENABLE_TEST_ENDPOINTS=1`.

Add-on execution requires an audience-bound ControlDeck service token and
`X-Control-Deck-Addon-ID: media-forge`. Media Forge validates it through the
ControlDeck Add-on Runtime introspection API; no Host signing key or session
cookie is provisioned to Media Forge. Agent and workspace generation use the
Host Jobs and resource APIs. Workflow and Context Action execution use the
Host-signed actor and exact per-call grant allowlist; there is no unleased,
raw-path, or cookie-based fallback.

The embedded opaque-origin workspace uses the private `/ws` transport through
ControlDeck's nonce-bound WebSocket proxy. It accepts only a bounded set of
structured job/asset methods, requires the same Add-on service identity, rejects
host path strings, limits requests to 1 MiB, and limits asset previews to 12 MiB.
This transport is an implementation detail for the workspace; it is not a new
public operation or a replacement for the host resource/Jobs/files bridges.

## Jobs

`POST /api/v1/jobs` accepts [`schemas/job-request.json`](../schemas/job-request.json). G0 executes `image.generate` through a deterministic fake worker. G1 is adding a capability-routed local image worker without changing this request. Other operation names are reserved by the public contract and fail with `capability_unavailable` until their goal is delivered.

`GET /api/v1/jobs` lists durable jobs. `GET /api/v1/jobs/{job_id}` returns one job. `DELETE /api/v1/jobs/{job_id}` requests cancellation.

States are `queued`, `running`, `succeeded`, `failed`, and `canceled`. `phase` is an optional execution detail and is not a separate terminal state.

Every request is local-only. `local_only` defaults to `true`; any explicit `false` value is rejected by backend validation.

## Capabilities

`GET /api/v1/capabilities` reports capability state as `available`, `unavailable`, or `experimental`. Until a G1 model passes the adoption gate, it reports `image.text_to_image` as available with `implementation=fake` and `confidence=low`; it does not claim the experimental model is the default or expose a selected model ID.

## Models

`GET /api/v1/models` reports entries conforming to
[`schemas/model.json`](../schemas/model.json): ID, family,
version/revision, license, adapter, capabilities, adoption state, installed and
healthy flags, and measured VRAM/runtime when available. It never returns a
local filesystem path. A downloaded candidate remains `experimental` and
`healthy=false` until its target-hardware benchmark is recorded and it is
explicitly promoted; installation alone does not alter `model_policy=auto`.

## Assets and provenance

- `GET /api/v1/assets`
- `GET /api/v1/assets/{asset_id}`
- `GET /api/v1/assets/{asset_id}/content`
- `GET /api/v1/assets/{asset_id}/provenance`

Asset and provenance documents conform to [`schemas/asset.json`](../schemas/asset.json) and [`schemas/provenance.json`](../schemas/provenance.json). A provenance sidecar is stored next to every immutable asset copy. The SQLite index can be rebuilt in a future maintenance operation without losing the producing facts.

Parentage uses asset IDs only. Host paths are not part of this API.

## Add-on execution endpoints

ControlDeck calls `/addon/v1/*` endpoints declared by [`addon.json`](../addon.json). Workflow and agent payloads use `{input, correlation}` envelopes. Responses return structured `job_id` and `asset_ids`; agents do not scrape filenames and do not receive a selected model name from generation or capability discovery.

Context actions require a host-issued opaque `grant:` ID. Raw paths are rejected.
Project commit is not available before G4. The development-only
`/test/host-files/roundtrip` endpoint exercises the same private Host bridge and
is hidden unless test endpoints are explicitly enabled.

`GET /api/v1/host-integration` reports non-secret integration readiness and
known Host limitations. It does not expose tokens, lease details belonging to
other owners, or a host filesystem path.

## Contract evolution

G1 is the freeze point for public schemas, manifest contributions, agent tools, workflow executor types, and required asset/provenance fields. Before that point, changes remain reviewable contract candidates. After G1, additions are preferred; a breaking change requires impact, migration, and version-bump documentation.
