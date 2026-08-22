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

Workspace presentation methods were added for the UI slice and keep that same
status. `capabilities.get` returns the public capability document plus the size
envelope and clamped presets the UI may offer. `library.list` returns assets with
their origin, a bounded summary, and the measured protected-pixel result, hiding
edit masks unless they are explicitly requested. `assets.thumbnail` returns a
cached WebP bounded to 512 px and 64 KiB. `preferences.get` / `preferences.set`
persist an allowlisted set of presentation choices per ControlDeck identity
subject, because the sandboxed view has no browser storage; they reject unknown
keys and payloads above 4 KiB. `jobs.watch` / `jobs.unwatch` push
`{"type": "event", "event": "job.changed"}` frames for up to ten jobs per
connection, coalesced to at most one frame per job every 200 ms, so progress is
no longer polled from a single panel. None of these appear in the public API,
`schemas/`, or `addon.json`.

Model Management also stays on this private transport. `models.catalog`
returns trusted catalog metadata, managed-store capacity and effective
managed/external ownership without returning a local path. `models.install`
and `models.remove` accept only a catalog `model_id`; no URL, repository or
command is accepted. `models.operations.list`, `.watch`, `.unwatch`, and
`.cancel` expose durable progress. Watched changes arrive as
`{"type":"event","event":"model.operation.changed"}`. Install states are
`queued`, `preflight`, `downloading`, `verifying`, `installing`, then `ready`,
`failed`, or `canceled`. A reconnect can list and re-watch the same operation.
This workspace surface does not alter the frozen generation contract.
Catalog items also carry validated `media_types` for Settings classification,
`reclaimable_bytes`, and `profile_reference_count`. Routing never reads
`media_types`; runtime capability remains authoritative.

Creative planning also remains private. `creative.templates` returns the
versioned trusted template catalog. `creative.validate` accepts an existing
JobRequest-shaped object plus an internal CreativeSpec and returns a
JobRequest-compatible compiled request and normalized plan snapshot. It rejects
unknown templates, invalid scene/pose combinations, unavailable capabilities,
and reference roles that do not name request assets before job submission.
It never introduces `model_id` unless the incoming request already uses
`model_policy=manual`.

Intentional variation batches are also private workspace orchestration.
`creative.batches.create` accepts an existing JobRequest-shaped object, an
internal CreativeSpec, and a bounded count (2..8). It returns a durable logical
batch with explicit child plans and child job IDs. `creative.batches.get`,
`.list`, and `.cancel` support reconnect, Activity drilldown, and safe logical
cancel. Every child still uses the normal `jobs.create` / hosted Broker admission
route; successful child assets are retained when siblings fail or are canceled.
The standalone same-origin `/workspace-api/creative/batches` bridge mirrors
these methods for development, is excluded from OpenAPI, and is not a public API.

`creative.compositions.create` is the corresponding private multi-cut surface.
It accepts an existing JobRequest-shaped object, internal CreativeSpec, and a
trusted `poster` or `character_sheet` layout with 2..4 shots. Children use normal
job/Broker admission; the CPU-only Composer then returns one `asset.pack` asset.
`.get`, `.list`, and `.cancel` support durable progress. `.update_text` changes
title/caption and creates a new deterministic final revision without creating
new image-generation jobs. Its provenance contains every child asset ID/hash,
the normalized layout snapshot, and the cached font hash. The same-origin
`/workspace-api/creative/compositions` development bridge is excluded from
OpenAPI and accepts no path.

## Jobs

`POST /api/v1/jobs` accepts [`schemas/job-request.json`](../schemas/job-request.json).
`image.generate` routes by `image.text_to_image`. `image.edit` uses one source
`inputs[].asset_id`. Its optional `edit_mode` is `reference` (default),
`variation`, `inpaint`, or `outpaint`. Reference and variation may change the
whole image; inpaint requires strict editing and an asset mask:

```json
{
  "edit_mode": "inpaint",
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
`variation` cannot be combined with `strict_edit`; a mask ID without strict
editing also fails explicitly rather than being ignored.

Multi-reference editing uses `edit_mode=multi_reference`, `strict_edit=false`,
and 2..4 `inputs`. The first input is the editable primary and sole lineage
parent; remaining inputs are visual references. Provenance records the content
hash of every input. Other modes continue to require exactly one input.

Outpaint uses `strict_edit=true`, target `width`/`height`, and no mask asset. The
target must be a multiple of 16, contain the complete source, expand at least
one dimension, and stay within the selected model envelope. Media Forge centers
the source, derives the exterior mask, recopies every source RGBA pixel, and
rejects a result unless `image.outpaint.source_pixel_diff` reports zero.

`GET /api/v1/jobs` lists durable jobs. `GET /api/v1/jobs/{job_id}` returns one job. `DELETE /api/v1/jobs/{job_id}` requests cancellation.

States are `queued`, `running`, `succeeded`, `failed`, and `canceled`. `phase` is an optional execution detail and is not a separate terminal state.

Every request is local-only. `local_only` defaults to `true`; any explicit `false` value is rejected by backend validation.

## Capabilities

`GET /api/v1/capabilities` reports capability state as `available`, `unavailable`, or `experimental`.
It reports text generation, single-reference edit, multi-reference edit,
inpaint, outpaint, variation, and strict edit independently from installed measured model capabilities and never
exposes the automatically selected model ID.

`image.semantic_review` is available only for a Host-authenticated execution when
ControlDeck grants `ai.inference` and its provider-neutral `vision.analyze` capability has a
compatible target. Media Forge does not contain a provider URL, model name, or local-provider
fallback. `qa.semantic=false` never calls Host AI. With semantic review
enabled and `max_regeneration_attempts=0`, a subjective rejection is advisory:
the deterministic-valid asset succeeds with a provenance warning. A positive
retry budget is explicit opt-in; Media Forge creates only that many additional
candidates, selects the first accepted candidate, and fails with
`semantic_review_exhausted` when the bounded candidates are all rejected.
Deterministic validation completes first and can never be overridden by a
semantic pass. Candidate/reference images are normalized to bounded data URLs before the scoped
Host call; ControlDeck owns provider, runtime, model selection, lifecycle, and admission. Host AI
failures are normalized as `host_ai_not_granted`, `vision_analyzer_unavailable`,
`host_ai_unavailable`, or `vision_result_invalid`. Standalone prompt-only generation remains
available, while standalone semantic review is unavailable because it has no Host identity.

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

## Reference collections and profiles

- `GET /api/v1/reference-collections`
- `POST /api/v1/reference-collections`
- `DELETE /api/v1/reference-collections/{collection_id}`
- `GET /api/v1/profiles`
- `POST /api/v1/profiles`
- `DELETE /api/v1/profiles/{profile_id}`

Reference collections conform to
[`schemas/reference-collection.json`](../schemas/reference-collection.json) and
contain one to four immutable asset IDs, never paths. The additive optional
`roles` map classifies collection assets as `identity`, `style`, `pose`,
`composition`, `clothing`, `palette`, `prop`, or `environment`; omitted roles
remain valid and are inferred from the selected profile kind. Character and style
profiles conform to [`schemas/profile.json`](../schemas/profile.json); their
definitions are structured separately and may point to one reference
collection.

Generation and editing keep their existing operations. Callers optionally set
`constraints.character_profile_id` and/or `constraints.style_profile_id`.
Media Forge resolves and snapshots the full profile and collection before Host
Job creation, routes reference-conditioned work by capability, and supplies
only contained job-local image copies to the worker. A maximum of four unique
job/profile reference assets is enforced. Provenance retains the full resolved
snapshot plus every reference asset hash, so deleting a profile does not erase
the producing facts. Jobs without profiles follow the unchanged G1/G2 route.

The `roles` property is an additive extension to the frozen collection schema:
existing stored collections and clients may omit it, no existing field changes
meaning, and no migration or contract version bump is required. Per-job role
overrides and strengths live in the private CreativePlan snapshot. The active
model envelope is authoritative for the reference limit, supported roles, and
whether numeric strength is usable; unsupported controls are disabled rather
than silently ignored.

Parentage uses asset IDs only. Host paths are not part of this API.

The workspace obtains the versioned CreativeSpec template catalog through its
authenticated private WebSocket transport and validates directed requests with
`creative.validate` before job admission. Standalone workspace mode uses the
same compiler through `POST /workspace-api/creative/validate`; this route is
same-origin UI plumbing, is excluded from OpenAPI, and is not a public API
contract. Prompt-only/Auto requests bypass it and retain their prior request
shape. Neither route accepts a model name or filesystem path.

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
the import route and edit constraint keys are additive, while the existing
`image.edit` operation and open `constraints` object remain unchanged. A future
breaking change still requires impact, migration, and version-bump documentation.
