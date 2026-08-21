# Media Forge public API

Status: G1 public contract frozen; G2 additions are backward-compatible
Contract version: `1.0`
Date: 2026-08-22

The API is capability-driven. `model_id` is not required. Normal clients use `model_policy=auto`; an explicit model ID is accepted only with the opt-in `manual` policy.

## Current availability

G1 implements `/health`, `/schemas/{schema_name}`, the local job/capability/
asset/model APIs below, real local image generation, the embedded workspace, and the Add-on execution endpoints.
G2 adds single-reference and strict masked editing without changing the frozen operation or required fields. It also provides a development-only
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

`POST /api/v1/jobs` accepts [`schemas/job-request.json`](../schemas/job-request.json).
`image.generate` routes by `image.text_to_image`. `image.edit` uses one source
`inputs[].asset_id`; strict editing additionally uses these additive constraint fields:

```json
{
  "strict_edit": true,
  "editable_mask_asset_id": "asset_0123456789abcdef0123456789abcdef"
}
```

The mask is an asset ID, never a path. Its dimensions must equal the source.
Mask luminance multiplied by alpha defines editable weight: zero is protected,
nonzero is editable. Empty, full-canvas, mismatched, missing, or non-PNG masks
fail before GPU admission. A strict output succeeds only if the backend's
independent validator measures zero changed protected pixels. Other reserved
operation names fail with `capability_unavailable` until their goal is delivered.

`GET /api/v1/jobs` lists durable jobs. `GET /api/v1/jobs/{job_id}` returns one job. `DELETE /api/v1/jobs/{job_id}` requests cancellation.

States are `queued`, `running`, `succeeded`, `failed`, and `canceled`. `phase` is an optional execution detail and is not a separate terminal state.

Every request is local-only. `local_only` defaults to `true`; any explicit `false` value is rejected by backend validation.

## Capabilities

`GET /api/v1/capabilities` reports capability state as `available`, `unavailable`, or `experimental`.
It reports text generation, single-reference edit, and strict edit independently
from installed measured model capabilities and never exposes the automatically
selected model ID.

## Models

`GET /api/v1/models` reports entries conforming to
[`schemas/model.json`](../schemas/model.json): ID, family,
version/revision, license, adapter, capabilities, adoption state, installed and
healthy flags, and measured VRAM/runtime when available. It never returns a
local filesystem path. `measurement_confidence` is `low` for bootstrap
estimates and `measured` only after target-hardware evidence. A downloaded candidate remains `experimental` and
`healthy=false` until its target-hardware benchmark is recorded and it is
explicitly promoted; installation alone does not alter `model_policy=auto`.

## Assets and provenance

- `GET /api/v1/assets`
- `GET /api/v1/assets/{asset_id}`
- `GET /api/v1/assets/{asset_id}/content`
- `GET /api/v1/assets/{asset_id}/provenance`
- `POST /api/v1/assets/import?purpose=source|edit_mask`

The additive import endpoint accepts a raw PNG or JPEG request body, converts it
to the canonical RGBA PNG representation, and returns an Asset document. Input
is bounded to 64 MiB and 4,194,304 decoded pixels. It accepts no filename or
filesystem path. Imported assets carry `asset.import` provenance with
`license=user-provided`; import does not imply permission to train a model.

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

G1 froze public schemas, manifest contributions, agent tools, workflow executor
types, and required asset/provenance fields. G2 retains contract version `1.0`:
the import route and strict-edit constraint keys are additive, while the existing
`image.edit` operation and open `constraints` object remain unchanged. A future
breaking change still requires impact, migration, and version-bump documentation.
