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
command is accepted. A catalog item marked `gated` also requires an explicit
license acceptance identifier derived from that exact model ID, revision,
license, and notice; a stale or missing identifier fails before transfer.
Managed artifacts at or above 32,000,000,000 bytes also fail before an
operation is created. Composite bundles may declare additional catalog-pinned
Hugging Face source identities per weight; clients still cannot supply or
override any source.
`models.operations.list`, `.watch`, `.unwatch`, and
`.cancel` expose durable progress. Watched changes arrive as
`{"type":"event","event":"model.operation.changed"}`. Install states are
`queued`, `preflight`, `downloading`, `verifying`, `installing`, then `ready`,
`failed`, or `canceled`. A reconnect can list and re-watch the same operation.
This workspace surface does not alter the frozen generation contract.
Catalog items also carry validated `media_types` for Settings classification,
`reclaimable_bytes`, and `profile_reference_count`. Routing never reads
`media_types`; runtime capability remains authoritative.

Blender runtime diagnostics also remain private workspace presentation data.
The `blender_runtime` session part, `blender.runtime.status` WebSocket method,
and same-origin development bridge `GET /workspace-api/blender/runtime` return
the resolver state, required version, opaque runtime IDs, ownership, bounded
integrity checks, separate browser-pack state, and a diagnostic fingerprint.
They never return a runtime, registry, manifest, worker, or executable path.
The development bridge is excluded from OpenAPI and none of these additions
change the frozen public API.

3DS-2 adds private `blender.runtime.install`, `.update`, `.switch`, `.repair`,
`.remove.preview`, `.remove`, and `.operations.cancel` methods. The standalone
development mirror is `POST /workspace-api/blender/runtime/operations` with the
same actions. Install/update accept no source parameters; switch/repair/preview
accept one opaque catalog runtime ID; remove also requires the exact fingerprint
returned by its latest preview. No operation accepts a URL, path, executable,
version, or shell command from the browser. The checked-in trusted catalog fixes
the Blender archive identity, size, SHA-256, license, platform, and version.
Operation states are `queued`, `preflight`, `downloading`, `verifying`,
`installing`, `probing`, or `deleting`, then `ready`, `failed`, or `canceled`; the status
projection includes the durable operation journal for reconnect. These private
additions do not modify the frozen public job/model operation schemas. Removal
is limited to managed-root realpaths, refuses the active runtime and live pinned
G8 references, revalidates the preview under the same reference lock, and keeps
assets, scenes, history, external runtimes, and download cache out of scope.

3DS-5a adds private `blender.web.install` and the standalone `web_install`
action to the same durable operation journal. The browser cannot select a URL,
version, path, executable, or command. The checked-in Web pack manifest pins
TigerVNC 1.16.2 and noVNC 1.7.0 by HTTPS source, archive size, SHA-256, extracted
root, required-file SHA-256, and license. The status projection reports only
bounded component identities, checks, state, size, and fingerprint; it exposes
no installed path or VNC credential. This operation installs the software-display
pack only. A `ready` pack does not claim that a GUI session, RFB relay, GPU path,
or authenticated browser connection is available.

3DS-5b adds the private `blender_sessions` session part and
`blender.sessions.list`, `.start`, `.save`, and `.stop` methods. The standalone
development mirror is `GET/POST /workspace-api/blender/sessions`. Start accepts
only a Scene ID; save and stop accept only an opaque session ID. The projection
contains bounded state, fixed runtime/Web-pack identities, a software-display
descriptor, timestamps, error/result fields, and action availability. It never
contains a filesystem path, PID, systemd unit, display number, or RFB socket.
States are `queued`, `preparing`, `starting`, `ready`, `saving`, `stopping`, then
`stopped`, `failed`, or `interrupted`. One active session is allowed across the
service and the existing scene working-copy lock remains the single-writer
authority. Save first asks the live GUI to persist the working `.blend`, stops
the isolated process group, then uses the existing independent Blender/GLB
validation and immutable revision commit. Stop discards a healthy working copy;
a startup, save, runner, or service-reconciliation failure retains it as a
recovery copy. This slice exposes no RFB endpoint: a ready session is not yet a
claim that noVNC, Host proxying, reconnect, idle expiry, or revocation works.

3DS-3 keeps model viewing on the same private workspace boundary. `library.list`
accepts an allowlisted `media_kind` (`all`, `image`, `video`, or `3d`) and returns
that classification with each card. `assets.model.open` accepts only an Asset ID,
validates raw GLB or the exact `3d.project.glb` ZIP entries and manifest hash, and
returns a connection-scoped opaque handle. `assets.model.bytes` reads at most
512 KiB per call; `.close` releases it, and socket disconnect removes any project
staging. `assets.model.thumbnail` stores only a validated raw-GLB WebP capture up
to 512 px and 256 KiB. The standalone development mirrors apply the same model
validation. The immutable `/viewer-runtime.js` module is CORS-readable by the
opaque iframe and contains no asset URL or server path. Models are capped at
64 MiB, individual texture sides at 8,192 px, and total texture pixels at
67,108,864. These are private presentation methods and do not change OpenAPI,
`schemas/`, `addon.json`, Agent tools, or workflow executors.

Creative planning also remains private. `creative.templates` returns the
versioned trusted template catalog. `creative.validate` accepts an existing
JobRequest-shaped object plus an internal CreativeSpec and returns a
JobRequest-compatible compiled request and normalized plan snapshot. It rejects
unknown templates, invalid scene/pose combinations, unavailable capabilities,
and reference roles that do not name request assets before job submission.
It never introduces `model_id` unless the incoming request already uses
`model_policy=manual`.

`creative.direct` is the private provider-neutral text Director for a brand-new
image. It accepts the original intent, `original` / `refine` / `art_direct`, and
an internal CreativeSpec. The result keeps the original intent verbatim, returns
a canonical PromptPlan plus the projected CreativeSpec, and reports whether
assistance was used. Missing, timed-out, or invalid `text.generate` assistance
is fail-soft: the existing prompt-only request remains usable. Prompt-only
direction sends no image and never calls `vision.analyze`. A directed pose/action
batch may request 2..4 ActionState alternatives in one `text.generate` call;
the existing durable batch and child Job contracts remain unchanged.

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

G7 adds `video.generate` and `video.edit` without making a model name part of
the contract. `video.generate` accepts zero to eight input assets: zero routes
to text-to-video, one to image-to-video, and multiple inputs require a
multi-keyframe-capable runtime. Video output must be `mp4` or `webm`; image and
pack operations cannot request those formats. Until a local runtime passes the
R9700 adoption gate, video requests fail with `capability_unavailable` and the
capability document reports both `video.text_to_video` and
`video.image_to_video` as unavailable with reason `video_runtime_not_adopted`.
The workspace may expose the video form while those capabilities are unavailable,
but it must keep submission disabled and show the reason; visibility is not
runtime availability. Video assets add `video/mp4` and
`video/webm` MIME types plus optional `duration_sec` and `frame_rate`; existing
required asset fields are unchanged.

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

`record_state` reports whether the persisted request could be read strictly by
the running contract. It is `ok` for every normal record. A record written by a
newer additive contract version is served as `degraded`: the job stays in the
list with its status, assets, and error intact, and the request is returned as
stored. Reading never fails a whole collection because one record is degraded.
A `degraded` record is not executable; submitting it fails with
`job_record_unreadable`.

Every request is local-only. `local_only` defaults to `true`; any explicit `false` value is rejected by backend validation.

## User-added models

The shipped catalog stays the trusted path: pinned revision, verified digests,
measured VRAM. `models.custom.resolve` and `models.custom.add` add an explicit
second path for models the catalog does not carry, without loosening the first.

```text
resolve   a moving ref is pinned to an immutable commit before anything is fetched
          every weight carries the digest the Hub reported
          one runnable variant is selected; alternate runtimes and duplicate
          precisions are reported as skipped bytes, not silently downloaded
          the licence and any blocking condition are returned for display
add       the licence must be accepted by its exact name
          the entry lands as `experimental`, so routing never selects it
          promotion to routable requires a real `models.evaluate` measurement
```

Added entries are parsed by the same validators as the shipped manifests. No
repository code is executed and no remote inference path is added.

## Model routing

`model_policy` selects how a model is chosen: `auto`, `fast`, `balanced`,
`quality`, `low_vram`, or `manual`. `manual` requires `model_id` and is never
overridden by an automatic preference.

Automatic policies prefer a model whose catalog `domains` include the scene
domain of the request (`constraints.creative_plan.domain.id`), then order by the
policy rank. If no installed model declares that domain, every candidate stays
eligible: choosing a scene must never remove a usable model.

The decision is recorded in provenance under `parameters.model_route`
(`policy`, `capability`, `domain`, `domain_matched`, `candidate_count`).
Generation responses and capability discovery still do not carry a selected
model name.

## Resource turn

A hosted job that needs real GPU capacity runs in ordered stages. ControlDeck's
AI residency and image generation coexist: the Broker places generation on
whichever device has room.

```text
analyze       Host AI (text.generate / vision.analyze). No GPU lease is held.
generate      Broker lease with estimated_runtime_sec, then the image worker.
review        The generation lease is released before any vision evaluation.
```

The lease request carries `preferred_devices: ["gpu0", "host"]` for models that
can run on the CPU, and the grant's `device_id` says where the job actually
runs. `host` means system RAM: the worker loads on the CPU and reserves no
VRAM. Media Forge no longer asks ControlDeck to unload its language model
before generating — with RAM as a fallback there is no need to take the GPU
away from a chat or OpenCode session for one image.

## Capabilities

`GET /api/v1/capabilities` reports capability state as `available`, `unavailable`, or `experimental`.
It reports text generation, single-reference edit, multi-reference edit,
inpaint, outpaint, variation, and strict edit independently from installed measured model capabilities and never
exposes the automatically selected model ID.

`asset.3d_project_pack` is available only when the exact pinned Blender runtime
stamp, executable, and trusted compiler are present. Its `profile` is
`3d.project.glb`; otherwise it is unavailable with `runtime_not_installed`.
Capability discovery does not start Blender and exposes no runtime or project
path.

`image.semantic_review` is the frozen compatibility capability for the unified
evaluator. It is available only for a Host-authenticated execution when
ControlDeck grants `ai.inference` and its provider-neutral `vision.analyze`
capability has a compatible target. Media Forge contains no provider URL, model
name, or local-provider fallback. `qa.semantic=false` never calls Host AI. When
enabled, the evaluator emits the canonical `EvaluationResult` dimensions and
scores only constraints/reference roles relevant to that request. With
`max_regeneration_attempts=0`, a subjective rejection is advisory and the
deterministic-valid asset succeeds with a provenance warning. A positive retry
budget is explicit opt-in; Media Forge creates only that many additional
candidates, selects the first accepted candidate, and retains the frozen
`semantic_review_exhausted` error when all bounded candidates are rejected.

Deterministic validation completes first and can never be overridden by a VLM
score. If the evaluator is unavailable or its response is invalid, a
deterministically valid generated asset remains usable and records an advisory
warning. Candidate/reference images are normalized to bounded data URLs before
the scoped Host call; ControlDeck owns provider, runtime, model selection,
lifecycle, and admission. Standalone prompt-only generation remains available.

## Models

`GET /api/v1/models` reports entries conforming to
[`schemas/model.json`](../schemas/model.json): ID, family,
version/revision, license, adapter, capabilities, adoption state, installed and
healthy flags, and measured VRAM/runtime when available. It never returns a
local filesystem path. `measurement_confidence` is `low` for bootstrap
estimates and `measured` only after target-hardware evidence. A downloaded candidate remains `experimental` and
`healthy=false` until its target-hardware benchmark is recorded and it is
explicitly promoted; installation alone does not alter `model_policy=auto`.
The response also carries additive, optional presentation metadata from the
trusted catalog (`display_name`, domains, media types, source identity,
ownership, reference/LoRA support, size, and license notice). Standalone UI may
therefore render the same catalog classifications without reading repository
files or inventing model capabilities. These fields do not participate in
routing.

## Assets and provenance

- `GET /api/v1/assets`
- `GET /api/v1/assets/{asset_id}`
- `GET /api/v1/assets/{asset_id}/content`
- `GET /api/v1/assets/{asset_id}/provenance`
- `POST /api/v1/assets/import?purpose=source|edit_mask`

The additive import endpoint accepts a raw PNG/JPEG request body, converts it
to the canonical RGBA PNG representation, and returns an Asset document. With
`Content-Type: model/gltf-binary`, `purpose=source` instead accepts one GLB 2.0
file, validates its bounded embedded structure independently of Blender, and
stores the original bytes unchanged. GLB external URIs, unknown required
extensions, and sparse accessors are rejected by the initial fail-closed
boundary. Input is bounded to 64 MiB; images are additionally bounded to
4,194,304 decoded pixels. The endpoint accepts no filename or filesystem path.
Imported assets carry `asset.import` provenance with
`license=user-provided`; import does not imply permission to train a model.

Asset and provenance documents conform to [`schemas/asset.json`](../schemas/asset.json) and [`schemas/provenance.json`](../schemas/provenance.json). A provenance sidecar is stored next to every immutable asset copy. The SQLite index can be rebuilt in a future maintenance operation without losing the producing facts.

`application/x-blender` is an additive Asset MIME used for immutable, validated
3D scene revisions. The public import endpoint does not accept `.blend` bytes:
3DS-4 stages them only through the bounded private workspace flow and a trusted
Blender worker. Scene/revision operations remain private until the 3DS-7 Agent
tool and workflow compatibility gate.

The private workspace transport accepts `.blend` only as a declared upload:
`scenes.import.begin`, sequential `scenes.import.chunk` calls, then
`scenes.import.commit` or `scenes.import.cancel`. Each chunk is at most 512 KiB;
the declaration is at most 256 MiB and carries the whole-file SHA-256. Working
copies use `scenes.working.acquire/renew/release/commit`; their ten-minute lease,
owner, and base revision are enforced by the server. The standalone development
mirror lives below `/workspace-api/scenes/**`. None of these private routes are
included in OpenAPI, `addon.json`, Agent tools, or workflow executors.
The workspace 3D Studio sends the declared upload in sequential 512 KiB chunks,
then lists the owner-scoped scene documents and immutable revision history. A
revision preview opens through the same validated GLB viewer used by Library;
the raw `.blend` bytes are not exposed to the browser after import.

3DS-6a adds the typed
[`media-forge.material-binding@1`](../schemas/material-binding.json) document.
It fixes the selected source revision, Library image Asset, object/material
slot, channel, UV map, wrap, color space, and normal convention. Private
`scenes.material.targets` inspects the current revision; private
`scenes.material.apply` accepts only a scene ID and one binding. The server
rejects stale revisions and changed image bytes, packs the normalized image
into a trusted Blender working copy, then runs the existing Blender and GLB
validators before committing a new immutable revision. The standalone mirrors
are `GET /workspace-api/scenes/{scene_id}/material-targets` and
`POST /workspace-api/scenes/{scene_id}/materials`. These remain excluded from
OpenAPI, Agent tools, workflow executors, and `addon.json` until the 3DS-7 gate.

3DS-6b reuses the existing durable `image.generate` job for new scene images.
`constraints.scene_texture` is the typed `media-forge.scene-texture-request@1`
return context: scene ID, source revision ID, object, material slot, channel,
and UV map. It is valid only on `image.generate`, is bounded by
`schemas/scene-texture-request.json`, and grants no scene mutation authority.
The request also carries `constraints.asset_brief.role = texture`; the resolved
image is an ordinary immutable Library Asset with normal provenance. 3D Studio
can recover, cancel, or retry the job after reload, preview its first output,
and explicitly select it. Only the separate current-revision MaterialBinding
operation can commit that selected Asset as a new SceneRevision.

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
authenticated private WebSocket transport. When Host text direction is
available, a single-image Auto request uses `creative.direct`, then validates
the projected request with `creative.validate` before job admission. `そのまま`
and fail-soft fallback retain the original prompt-only behavior. Standalone
workspace mode mirrors both steps at `POST /workspace-api/creative/direct` and
`POST /workspace-api/creative/validate`; these routes are same-origin UI
plumbing, are excluded from OpenAPI, and are not a public API contract. Neither
route accepts a model name or filesystem path.

## Add-on execution endpoints

ControlDeck calls `/addon/v1/*` endpoints declared by [`addon.json`](../addon.json). Workflow and agent payloads use `{input, correlation}` envelopes. Responses return structured `job_id` and `asset_ids`; agents do not scrape filenames and do not receive a selected model name from generation or capability discovery.

Context actions require a host-issued opaque `grant:` ID. Raw paths are rejected.
`media.pack` commits one existing immutable Media Forge asset to a Host-issued
project output `grant:`. Its additive request schema accepts only a Media Forge
`asset_id`, the opaque output grant, and an optional safe filename. The Host
stages and atomically commits the bytes after size/SHA-256 verification; the
response returns the Host `asset:` ID and non-path metadata. It never accepts or
returns a project ID, relative directory, or filesystem path. The development-only
`/test/host-files/roundtrip` endpoint exercises the same private Host bridge and
is hidden unless test endpoints are explicitly enabled.

`GET /api/v1/host-integration` reports non-secret integration readiness and
known Host limitations. It does not expose tokens, lease details belonging to
other owners, or a host filesystem path.

## Domain profiles and deterministic packs

`GET /api/v1/domain-profiles` returns the bundled M5 shared-canvas profile
documents. `asset.pack` with `profile=m5.companion.pack` accepts exactly one
`base/front`, the fixed 12 eye slots, and the fixed 8 mouth slots through its
normal immutable `inputs` lineage. `constraints.entries` maps each input asset
ID to its fixed layer/name and `constraints.pack_name` is lowercase snake case.
The output must request `format=zip`.

The deterministic result is an `application/zip` asset containing the 21 PNG
layers, `atlas.png`, `manifest.json`, and a current-firmware pack at
`companion/packs/<name>/` with M5A v1 RGB565-BE base/eye/mouth clips and its v2
manifest. Repeating the operation over identical assets produces byte-identical
ZIP output. ZIP placement uses the same
`media.pack` output grant as images; no path field or M5-specific Host route is
added.

`asset.pack` with `profile=3d.project.glb` accepts exactly one
`model/gltf-binary` input, no free-form B2 constraints, and one ZIP output. It
runs the pinned Blender compiler as a separate factory/background process with
autoexec disabled and a fixed trusted request/result contract. The ZIP contains
`asset.glb`, `manifest.json`, and `preview.png` in fixed order with fixed entry
metadata. The manifest records parent/output hashes, bounded scene statistics,
removed unsafe data, ordered operations, compiler versions, and warnings. The
exported GLB and PNG are independently revalidated before the immutable ZIP is
registered. No Blender path, script, operator name, or project path is a public
input.

The optional private `constraints.compile_options` object is versioned as
`3d.compile-options@1` and rejects unknown fields. `apply_transforms=true` and
`preview=fixed_workbench` are fixed. Typed additions are
`repair_normals`/`remove_degenerate` booleans, merge distance `1e-7..1.0` m,
triangle budget `12..200000`, up to three strictly descending LOD ratios in
`0.05..0.95`, collision `none|box|convex_hull`, and materials
`preserve|basic_pbr`. Every operation records bounded parameters, measured
results, and warnings in manifest order. Omitting `compile_options` preserves
the B2 defaults.

The opaque-origin workspace can import the same GLB either from browser bytes
or through the ControlDeck file picker. The picker returns an opaque `grant:`
identifier to the workspace; the private `assets.import_grant` WebSocket method
then reads at most 64 MiB through the scoped-files bridge and accepts only
`purpose=source` plus `media_type=model/gltf-binary`. Neither the workspace nor
the response exposes a Host filesystem path. This is an internal workspace
transport and does not add a public Asset API.

Blender compilation has a hard upper timeout of 180 seconds. Operators may set
`MEDIA_FORGE_BLENDER_TIMEOUT_SEC` to a positive value no greater than 180; a
timeout terminates the process group, records `blender_compile_failed`, and
registers no partial asset.

Private Blender GUI sessions use a 300-second disconnected grace period and a
1,800-second controller-idle timeout by default. Operators may set
`MEDIA_FORGE_BLENDER_DISCONNECT_GRACE_SEC` up to 3,600 seconds and
`MEDIA_FORGE_BLENDER_IDLE_TIMEOUT_SEC` up to 86,400 seconds. Expiry, runner
crash, Host disable, and Host credential revocation stop the isolated unit and
retain the unvalidated working bytes as an owner-scoped recovery candidate.
Opening that candidate copies it into a new writer lease; only a successful
validation and save creates a formal scene revision.

## Contract evolution

G1 froze public schemas, manifest contributions, agent tools, workflow executor
types, and required asset/provenance fields. G2 retains contract version `1.0`:
the import route and edit constraint keys are additive, while the existing
`image.edit` operation and open `constraints` object remain unchanged. A future
breaking change still requires impact, migration, and version-bump documentation.
G5 keeps the same contract version and adds only a ZIP output enum/MIME, a higher
input bound, domain-profile discovery, and a manifest schema. Existing requests
and required fields are unchanged.
G7 V0 likewise keeps contract version `1.0`: the two generic video operations,
two output formats/MIME types, and optional video metadata are additive. A
measured runtime is deliberately not advertised by this contract-only slice.
