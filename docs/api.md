# Media Forge public API

Native OS policy release metadata is specified separately in
[`native-policy-release.schema.json`](../schemas/native-policy-release.schema.json).
It is not an HTTP endpoint or an enabled installation capability. The native
verifier binds canonical JSON/Ed25519 to the existing MediaForge publisher,
confinement purpose, exact release/source commit and package digest/size.
The expected identity comes from trusted release metadata, not a browser request.
Ordinary feature-bundle manifests cannot authorize OS policy installation.
Native approval, protected staging and installation remain separate pending gates.

Status: G1 public contract frozen; G2 additions are backward-compatible
Contract version: `1.0`
Date: 2026-08-22

The API is capability-driven. `model_id` is not required. Normal clients use `model_policy=auto`; an explicit model ID is accepted only with the opt-in `manual` policy.

Model descriptors may additionally expose `manual_only` (default false). Such a
model requires explicit `model_policy=manual` and its `model_id`; all automatic
policies exclude it, including when no other model is installed. This supports
explicit selection of local research configurations without changing defaults.

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

`media.pipeline.start` (`POST /addon/v1/agent/pipeline/start`) accepts
`asset-pipeline-request.json`: exactly one `prompt` or `image_asset_id`, a name,
confirmation mode, and bounded generation/rig/export options. A prompt first
submits an ordinary `image.generate` Job; an image starts at model reconstruction.
`media.pipeline.status` (`POST /addon/v1/agent/pipeline/status`) accepts
`asset-pipeline-action.json` with `pipeline_id` and `action=status|approve|cancel|retry`.
Both use the existing `{"input": ...}` agent envelope and return the persisted
pipeline record, including stages, child Job IDs, scene/revision and final asset IDs.

Status calls advance at most one new Job; polling is required in both modes.
`confirm` pauses before each stage after the first until approved. Cancellation
stops future stages and leaves an already running child Job to finish; it does
not cancel that Job. Failed and canceled pipelines stay terminal on later polls.
Since 0.33.13, explicit `retry` requires `expected_job_id` equal to the failed
stage's current Job ID. The ordinary Job must itself be failed or canceled.
Successful earlier stages, the input request and later confirm-mode approvals
are preserved. The stage records up to eight `failed_attempts`, containing the
previous Job ID, error and timestamps. Repeated/stale requests return 409 and
cannot retry a newer failed attempt. Other actors still receive 404.
Export failures without a Job, successful Jobs with missing results and unknown
submission outcomes are not blindly retried. An interrupted retry dispatch is
persisted before submission and becomes a terminal failure if its Job is unknown.
The `expected_job_id` field is only valid with `action=retry`.
Pipeline records belong to the Host actor; other actors receive 404. Concurrent
read/advance/write operations on one pipeline are serialized in the single core
process, while unrelated pipelines retain independent request identities.
This is not a promise of exactly-once submission across abrupt process crashes.

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

The private status also includes `operation_notices`, an operation-ID-to-code-list
mapping for the authenticated owner only (local operations only on the standalone
bridge). Fixed codes distinguish publication in progress, recovery required,
recovered/rolled-back outcomes, late cancellation/context loss, and pending or
mismatched Host terminal reconciliation. No private publication identity, owner,
Host Job ID, receipt payload, or credential is included. Older clients can ignore
this additive presentation field. Changed reconciliation receipts invalidate the
existing session part; repeated identical receipts do not create an event loop.

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

Removal/unregistration previews additionally expose `in_process_reference_count`
and `durable_reference_counts` (`recipe_jobs`, `working_copies`, `sessions`,
`unresolved_sessions`). `live_reference_count` is their sum: references, not
distinct processes. Nonterminal recipe Jobs and active working copies (even
expired leases until retired) block removal. An unpinned active GUI resolves its
working/recovery copy, then its current scene revision only if no working ID was
specified. An unresolved GUI conservatively blocks every runtime. All these
counts enter the confirmation fingerprint; an older outstanding preview must
be requested again. Already-unregistered removal journals retain recovery cleanup.
Managed preview, admission and execution run their synchronous DB/filesystem work
in worker threads; a started admission/deletion is tracked through request cancellation.
New GUI admissions persist their runtime ID/version while holding the same
resolver guard used by removal. Normal/recovery working-copy acquisition keeps
that guard through runtime validation, file copy and durable lease creation.
Production callers await worker-thread acquisition; cancellation waits for the
copy and releases its newly created lease/files. GUI stop/interruption waits for
the previous preparation task to finish cleanup before terminalizing the session.
An already-removed runtime is rejected before a new GUI record is accepted.
History-confirmed removal and its destructive race acceptance are not yet provided.

The configured fixed legacy reference has separate private methods
`blender.runtime.unregister.preview`, `.unregister`, and `.register_legacy`.
The standalone actions are `unregister_preview`, `unregister`, and `register_legacy`.
Preview accepts only the fixed opaque legacy ID; unregister additionally requires
the latest confirmation fingerprint. Re-registration accepts no parameters and
revalidates only the server-configured legacy installation. These are short atomic
registration changes, not download jobs; reconnect reads the persisted registry.
The preview reports `operation=unregister`, zero reclaimable bytes, and active,
live/session and project references. Unregister rechecks these under the resolver
guard before detaching; external files are never removed. Busy runtime operations
reject the change. Synchronous validation/DB/registry work runs in a worker thread,
and request cancellation waits for any started atomic write to finish.
The registry suppression flag prevents automatic re-registration; Settings exposes
an explicit re-register button only while detached. Existing managed removal is unchanged.

The server setting is `MEDIA_FORGE_BLENDER_LEGACY_ROOT`, a root containing the
fixed runtime stamp and `install/blender`, not a browser-supplied executable path.
Without an override, the root is relative to the running source or packaged code;
a bundle does not implicitly locate a source checkout's existing installation.
An old registry row can consequently report `damaged` even when another copy
exists elsewhere. Explicit registration must validate the configured copy; an
invalid copy leaves suppression intact. See the README's external reference
section for deployment and acceptance preconditions.

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
`inputs[]`. Its optional `edit_mode` is `reference` (default),
`variation`, `inpaint`, or `outpaint`. Reference and variation may change the
whole image; inpaint requires strict editing and an asset mask:

Each entry in `inputs` names either an `asset_id` Media Forge already holds or a
`grant_id` for a file in the current Control Deck project — the agent obtains one
from the host's `control_deck.project_input_grant` tool, and Media Forge imports
the file before the job runs. A path is never accepted. The whole-image modes
(`reference`, `variation`, `multi_reference`) honour an explicit `width`/`height`
pair the same way generation does; the modes with their own size invariant
(strict editing, outpaint, and the repairs) keep deciding for themselves.

Those same modes honour `constraints.asset_brief`. A brief that requires
transparency makes the edit deliver a cut-out subject, the same way generation
does. Transparency is never inferred from the intent on an edit: it applies only
when the brief names it, so a touch-up is never given a cut it did not ask for.
Modes that keep pixels are excluded; cutting out a protected pixel would undo the
guarantee.

Media Forge cuts by estimating the subject's shape (BiRefNet, MIT, run on CPU in
the image runtime) and falls back to keying a flat background out when those
weights are not installed. With the estimator available the request carries no
background instruction at all — say what background you want and it is honoured,
because the cut does not depend on it. Without it, Media Forge asks the model for
a flat magenta field and drops any background wording from the prompt, since one
prompt cannot ask for two different backgrounds. Either way the result is
inspected before it is registered: a cut that keeps nothing, removes nothing, or
leaves no subject is refused and `alpha_missing` names the reason.

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
to the canonical RGBA PNG representation, and returns an Asset document. Where a
HEIF/HEIC decoder is installed it also accepts phone photos in that format and
converts them the same way, so the stored Asset media type set is unchanged. The
declared request media type only has to be one the device sends; the body is
always decoded to decide what it is. EXIF orientation is applied on import, so a
stored Asset has the dimensions the photo is seen with. With
`Content-Type: model/gltf-binary`, `purpose=source` instead accepts one GLB 2.0
file, validates its bounded embedded structure independently of Blender, and
stores the original bytes unchanged. Embedded WebP textures using
`EXT_texture_webp` are accepted (validator 1.1.0), including required extensions
without a PNG/JPEG fallback. The extension source must reference an embedded
`image/webp` image and be declared in `extensionsUsed`; without a fallback it
must also be in `extensionsRequired`. GLB external URIs, unknown required
extensions, and sparse accessors are rejected by the initial fail-closed
boundary. Input is bounded to 64 MiB; images are additionally bounded to
4,194,304 decoded pixels. The endpoint accepts no filename or filesystem path.
Imported assets carry `asset.import` provenance with
`license=user-provided`; import does not imply permission to train a model.

Asset and provenance documents conform to [`schemas/asset.json`](../schemas/asset.json) and [`schemas/provenance.json`](../schemas/provenance.json). A provenance sidecar is stored next to every immutable asset copy. The SQLite index can be rebuilt in a future maintenance operation without losing the producing facts.

`application/x-blender` is an additive Asset MIME used for immutable, validated
3D scene revisions. The public import endpoint does not accept `.blend` bytes:
3DS-4 stages them only through the bounded private workspace flow and a trusted
Blender worker. Raw import, working-copy and restore operations remain private;
3DS-7 exposes only the bounded typed recipe surface described below.

Typed operation failures retain `error.code=scene_recipe_failed`. When validated
worker context is available, `error.message` identifies the one-based operation
number, type, stable object ID, and a bounded reason. Raw worker exceptions and
paths are not returned; invalid or unavailable diagnostics use a generic message.
The failed recipe does not commit a partial revision. Corrected input is a new
edit attempt, not an unchanged-input retry.

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

Private `assets.relations` (and `GET /workspace-api/assets/{asset_id}/relations`)
additionally returns `scene_links`: owner-checked scene name/ID, original revision
ID/sequence/preview, current revision ID and optional material selection. Resolution
uses immutable provenance/parent Assets and SceneRevisions, not the recent Jobs list.
It visits at most 64 Assets over eight parent edges and returns at most 16 scenes.
Library editing may retain the typed source selection in the additive
`constraints.source_scene_texture` provenance field. This is a navigation hint,
not a Studio execution request or an authorization token. It does not change
image routing, progress, canvas sizing or worker resource profiles.
Caller-supplied owner/path fields are rejected. The standalone mirror uses its local
owner. Scene navigation does not start Blender GUI or commit material changes.

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
OpenAPI and workflow executors. 3DS-7 publishes the same binding through the
dedicated `media.scene.material` Agent tool.

The additive private WebSocket methods `scenes.material.preview.prepare`
(`scene_id`, `binding`), `.read` (`candidate_id`, `offset`, `length`), `.adopt`
(`candidate_id`), and `.discard` (`candidate_id`) support uncommitted material
candidates. Field sets are exact; the client cannot supply the owner or connection
identity. Prepare returns `candidate_id`, `scene_id`, `base_revision_id`,
`saved=false`, `expires_at`, `sha256`, `total_bytes`, and `chunk_bytes`.
Read returns bounded base64 GLB bytes, offset and total size; it never exposes
the Blender source or a path. Only adoption commits a revision. The existing
direct apply API remains unchanged. These additions are not public Agent tools
and are used by the material comparison UI before explicit adoption.
The standalone mirror is `/workspace-api/material-preview/ws`, requires the
same loopback Origin (as standalone Blender RFB), and accepts only these candidate
methods. Hosted `/ws` continues to require Host service authentication. Candidate
IDs cannot transfer between the two connections or subjects.

The server runs at most one candidate request per connection asynchronously,
so disconnect can cancel preparation without blocking unrelated workspace calls.
Disconnect discards unadopted candidates and releases runtime references;
an explicit adoption already in progress completes before cleanup. A five-second
sweeper checks the ten-minute TTL; shutdown removes remaining candidates.
Expiry/access checks serialize with bounded worker operations, so physical
reclamation can wait for an in-flight operation to finish.

3DS-6b reuses the existing durable `image.generate` job for new scene images.
`constraints.scene_texture` is the typed `media-forge.scene-texture-request@1`
return context: scene ID, source revision ID, object, material slot, channel,
and UV map. It is valid on `image.generate` and `image.edit`, is bounded by
`schemas/scene-texture-request.json`, and grants no scene mutation authority.
The request also carries `constraints.asset_brief.role = texture`; the resolved
image is an ordinary immutable Library Asset with normal provenance. 3D Studio
can recover, cancel, or retry the job after reload, preview up to four outputs,
and explicitly select it. Only the separate current-revision MaterialBinding
operation can commit that selected Asset as a new SceneRevision.

3DS-6c adds private workspace method `scenes.revisions.restore` and its same-origin
mirror `POST /workspace-api/scenes/{scene_id}/revisions/restore`. The only input is
`scene_id`, the expected current `base_revision_id`, and an older
`target_revision_id` from that scene. Media Forge rechecks the immutable source,
preview, and dependency identities, clones them under new Asset/provenance IDs,
and advances the head with a new linear SceneRevision. It never rewrites history
or aliases the old source/preview Asset as the new output. This remains excluded
from OpenAPI and the public mutation tools. The Agent snapshot tool can inspect
the resulting immutable current revision but cannot invoke restore.

Private `scenes.recovery.fork` accepts only `scene_id` and `recovery_working_id`.
Its standalone mirror is `POST /workspace-api/scenes/{scene_id}/recovery/fork`,
with only `recovery_working_id` in the body. It returns `{scene, revision}` for
a separate, validated scene. The retained candidate and original head remain
unchanged, including on validation failure. Repeating a candidate returns the
same recovered scene; owner checks apply before lookup. The original revision,
candidate hash and source asset lineage are in the new source provenance.
The opaque workspace method `scenes.simplify` (`scene_id`, `base_revision_id`,
`ratio`, optional `weld_distance_m`, `min_faces` and `object_id`) submits the
fixed reduction as an ordinary scene edit job: `mesh.weld` followed by
`mesh.decimate` at the requested ratio. The screen sends only the strength; the
recipe is assembled on the server, so the workspace never gains the ability to
run an arbitrary recipe. Agents already reach the same two operations through
`media.scene.edit`, which is why no new Agent tool is added. Poll it with
`scenes.jobs.get` like any other scene job.

This private operation is excluded from OpenAPI and Agent/workflow tools.
Both workspace scene lists include owner-scoped `working_copies` for recovery UI,
and `library_models`: the Library GLBs that no scene revision owns yet. The
opaque workspace method `scenes.from_glb` (`asset_id`, `name`, optional `tags`
and `collection`) turns one of those into an editable scene through the same
isolated Blender import, validation and revision publication the generated path
uses. A GLB that already is a revision's preview is refused rather than
duplicated; the source GLB is recorded as a `source_glb` dependency and as the
new blend's lineage parent. It is a workspace method, not an Agent or workflow
tool, and stays out of OpenAPI.

### Typed 3D scene Agent and workflow tools

`media.scene.from_image` adds image-conditioned generation through
`POST /addon/v1/agent/scene/from-image` (the usual `{"input": {...}}` envelope).
`schemas/scene-from-image-request.json` requires `name` and `input_asset_id`;
optional fields are `engine` (`auto`, `trellis_cpp`, `pixal3d`),
`refine_with_pixal3d`, `resolution`
(512 or 1024; only the adopted runtime's measured value is accepted), `seed`,
`tags`, `collection`, and `retry_job_id`. `local_only` can only be true.
Paths, URLs, arbitrary scripts, and model downloads are not public inputs.
The additive workflow action is `from_image` on the existing `media.scene`
executor. The opaque workspace method is `scenes.from_image`; its job methods
are `scenes.jobs.get` and `scenes.jobs.cancel`, each taking only `job_id`.

Check `3d.image_to_3d` before submission. A missing adoption receipt, unavailable
Blender, or unmeasured resolution fails closed. Pixal3D has its own private worker
adapter and adoption receipt; it remains unavailable until independently measured
and adopted. The additive `engines` map reports each adapter separately. `auto`
prefers an existing TRELLIS receipt, and considers Pixal only when that receipt is
absent; invalid receipts or unmeasured resolutions do not select another engine.
Pixal currently accepts only an adopted 1024 resolution through this public API.

`refine_with_pixal3d` (default false) runs one pinned chain instead of one engine:
the selected engine first, then Pixal3D. It adds no stage when the selected engine
is already `pixal3d`, and admission fails closed when Pixal3D is not adopted rather
than silently falling back to a single stage. The later stage runs at its own
measured resolution, because the two adapters are measured independently and need
not share one. Each stage takes and releases its own resource lease. The first
stage publishes the Scene; the later stage is committed as the next revision of
that same Scene, so both generations and their Assets remain. When only the later
stage fails, the published first stage is kept and the Job result reports
`refine` as `{state, engine, reason}`; `state` is `not_requested`, `succeeded` or
`failed`. Admission pins the digest of the whole ordered chain, so replacing any
adopted stage after admission is detected. Multi-view conditioning is not offered:
the adopted `trellis-cli` and Pixal worker each accept exactly one input image.
Admission requires `jobs.write` and `resources.acquire`. The returned
detached Job uses the existing `media.job.status` / `media.job.cancel` endpoints
and owner checks. Its phases cover CPU input preparation (`prepare_3d_input` for
Pixal), GPU waiting, generation, and independent
Blender validation. A later stage repeats those phases with a `_refine` suffix.
The CPU Blender step follows GPU process termination and lease release; another scene's CPU work can proceed while GPU admission waits.
Pixal preparation exits before requesting the GPU lease. Cancellation and timeout
drain the owned process group before releasing it. Its generation provenance also
records the descriptor/prepared-input hashes and explicit CPU/Vulkan stages.

Success creates one Scene revision with an editable packed `.blend` and a GLB
in the shared Library. Source provenance names the input Asset, pinned model
and runtime identities, weights hash, seed, resolution, elapsed generation time,
and raw GLB hash. Preview provenance links to that source. The original image is
retained and cannot be deleted during the active Job or while referenced by the
published assets. Retry preserves the exact input, generator receipt fingerprint
and Blender version; changed identities require a new request. Structural
validation and visual quality are distinct; this capability is experimental.

3DS-7 adds `media.scene.create`, `media.scene.edit`, `media.scene.material`,
`media.scene.snapshot`, `media.scene.export`, `media.job.status`, and
`media.job.cancel`, plus the `media.scene` workflow executor. Their self-contained
Draft 2020-12 schemas are `schemas/scene-*.json`. Create/edit recipes accept at
most 64 sequential operations from a closed vocabulary: primitive creation,
meter-based dimensions/transform, stable object IDs, bounded bevel, Principled
material, smart-project UV, light, camera, independent mesh duplication
(`object.duplicate`) and a bounded non-destructive mirror (`modifier.mirror`).
`modifier.array` adds a fixed-count non-destructive array to a static mesh:
`count` is an integer from 2 to 64 including the original, and `local_offset`
is a nonzero XYZ vector in local mesh coordinates (-10000..10000 each).
Object scale and rotation affect world-space spacing. This is not a world-meter
offset or relative bounding-box multiplier. At most one array per object;
parented, constrained, animated or shape-key meshes are rejected. No object/curve
offset, caps, fit-length, or vertex merging is exposed. Growth is bounded before
allocation, including subsequent duplicate/mirror and bevel on the array mesh.
Array does not join disconnected geometry or guarantee a watertight result.
The vocabulary also includes `armature.create`, rigid `skin.bind`, and `pose.set`.
Armatures have identity transforms, 1..128 named bones (ASCII IDs up to 48 chars),
ordered parent references, finite rest endpoints, and minimum length 0.001m;
creating a rig enforces 256 total scene bones. Skin binding assigns all vertices
of each listed independent mesh to one bone at weight 1, preserving rest world
geometry. It rejects existing parents, weights, constraints, animation, shape
keys, and unsupported modifiers; at most 64 meshes / 1,000,000 input vertices
per bind. Binding requires a rest pose. Pose setting replaces rest-local XYZ
rotations in degrees (-180..180), for 1..128 distinct existing bones.
Bind/pose currently target only typed Media Forge armatures, without shared
armature data, animation, or constraints. Unspecified bones are unchanged.
Rigid binding does not distribute weights; use the separate automatic operation below.
`pose.set` rejects scenes containing actions or other rig kinds. For static scenes
consisting only of typed rigs, GLB export uses the current pose as its rest pose
so the exported preview retains that pose. The source blend retains its original
bone rest data. Existing untyped/animated scenes retain their export setting;
this static-pose behavior is not animation-clip support.

`skin.bind_auto` adds bone-heat binding of 1..16 distinct `mesh_object_ids` to the
typed rig identified by `object_id`. The rig must have identity world transform,
rest pose, and deform bones; meshes must have independent static data, no parent,
weights, constraints, animation, shape keys or modifiers, and a finite positive
non-singular world transform. It does not silently apply modifiers or replace weights.
Before heat computation, selected inputs are limited to 50,000 vertices,
100,000 polygons, 300,000 face corners and 1,000,000 vertex/bone pairs. Faces must
have finite nonzero area. CPU worker timeout/cancel still apply.
Every vertex must receive finite nonnegative weights for known bones. The strongest
four influences are retained (ties by group index), explicitly normalized, and
stored sums checked within 1e-5. Missing/invalid weights fail rather than falling
back to rigid assignment. Rest world geometry is verified before publication.
Failure, including a later recipe operation failure, leaves the previous revision
unchanged. Existing pose/clip operations work on the bound mesh. Automatic binding
is not weight painting, IK or a guarantee of character deformation quality.

`animation.clip` adds a new named clip to a typed rig, without replacing an
existing clip ID by default. Optional strict boolean `replace=true` instead
requires that ID to exist on the same typed rig and replaces its complete clip
definition in a new scene revision. Shared/unknown action references are rejected.
Old revisions and unrelated clips remain unchanged; FPS must still match.
Clip/key/sample budgets apply to the resulting scene, excluding the replaced
action only after validating its structure. Omitted/false keeps insert-only behavior.
Tracks contain known bone IDs and 2..256 ordered keys with
frame numbers and rest-local XYZ rotations (-180..180 degrees); interpolation
is LINEAR, not quaternion shortest-path/IK. Keys span frame 0 to frame_count.
Unspecified bones receive zero rotation tracks. FPS is 1..60, frame_count
1..600 and duration at most 120 seconds. Existing clips must share the same FPS.
Loop requests must explicitly set `loop=true` on every requested looping clip.
Omission defaults to false even if endpoint rotations match; matching keys do not
enable loop validation. This validates equal first/last rotations, not velocity
continuity or game-engine playback settings. Agents must compare submitted clip
fields with the requested motion before execution, not infer compliance from Job success.

New revisions expose optional `animation_settings` in their `blender.scene`
validation facts, available in creation/edit Job results and `media.scene.snapshot`.
Its schema is `schemas/scene-animation-settings.json`. The independent Blender
validator reads effective scene FPS and actual action frame ranges, plus saved
typed rig/clip IDs and `loop_requested` metadata (at most 32 clips).
This is not loop-quality certification or an engine playback flag. General actions,
invalid/duplicate typed metadata and overflow are counted in `unreported_actions`;
they are not silently presented as absent. Missing facts on older revisions mean
not inspected, not zero clips. Compare these observations with the requested motion.

At most 128 tracks/clip, 32 clips/scene, 262144 scalar keys and 250000 bone-frame
samples are accepted, counting saved curves again before adding a clip.
Only typed actions and muted single-action NLA stashes are accepted; drivers,
constraints, other rig kinds and non-rig animation are rejected. Unrelated clips
remain stashed, the new clip becomes active. Original blend/GLB scene revisions
remain immutable. Clip display names are metadata; Blender/glTF action names use
`mf.<clip_id>.<rig_hash>`. Later additive M5/M6 operations below provide local
weights, fixed leg IK baking and optional translation keys. Scale tracks, general
IK/FK controls, retargeting and engine gameplay integration remain separate.
Available `3d.scene_recipe.supported_operations` is derived from the same
request vocabulary. Check the current schema/capability before sending a new
operation to an older deployment; existing operations retain their meaning.
Duplicate takes a source stable ID and a fresh target ID/name, with optional
absolute transforms. It copies mesh data while retaining referenced materials;
parent/constraint/animation/shape-key sources are not yet supported.
Mirror takes unique X/Y/Z axes and an optional different reference object ID,
otherwise uses the target origin. Merge threshold is 0..0.1 in local mesh
coordinates (object scale affects world-space tolerance; 0 disables merge).
At most one mirror per target. Static geometry growth uses a conservative
1,000,000-unit vertex/triangle estimate before copying/adding a mirror; modifiers
other than mirror/bevel must be applied before these growth operations.
The existing worker timeout and independent output validation still apply.
No schema accepts Python, a
Blender operator name, shell text, URL, or filesystem path.

Create, edit, and image MaterialBinding return a local durable Job reference
immediately after ControlDeck creates a `detached=true` child Job. Media Forge
switches to the returned child credential for progress/control, refreshes it
before expiry, polls Host cancel, and never persists the bearer token. SQLite
persists the local/Host Job IDs, stable owner, exact input and idempotency hashes,
pinned Blender runtime/version, base revision, stage, result, retry parent, and
terminal outbox state. A restart without the short-lived identity fails closed
as `service_restarted` or `host_context_lost`; it does not replay Blender work.
While a valid child identity remains in memory, unsent terminals retry with bounded
backoff. After restart, an authenticated owner `media.job.status` or `media.job.cancel`
request may replay that requested job's outbox through the Host's terminal-only
reconciliation API. `host_terminal_sent` becomes true only on confirmed delivery or
an exact terminal match. The additive nullable `host_terminal_reconciliation` follows
[`schemas/host-terminal-reconciliation.json`](../schemas/host-terminal-reconciliation.json).
A different existing Host terminal is retained with `terminal_matches=false` and
`host_terminal_sent=false`. An older/unreachable Host or unavailable current authority
leaves the payload pending. No token is persisted and no recipe is replayed.
Retry is a new Job and must carry byte-equivalent typed input through
`retry_job_id`. Successful revisions require the same independent Blender and
GLB validators as UI work.

ControlDeck Agent calls use a different execution `job:` subject for each tool.
When current Host introspection returns its signed optional `actor_subject`, it
is the scene owner key across those calls; the execution/child subject remains
the only Host-operation authority. On older Hosts, ownership remains scoped to
the individual subject instead of guessing a user. Status/cancel/snapshot/export
recheck this owner and expose only opaque Scene/Revision/Asset/Job IDs.

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

After `media.generate` accepts a Job, terminal failure/cancellation returns HTTP
502 with `detail.code`, `detail.job_id` and its terminal `detail.status`.
A cleanup timeout returns 504 with `job_cleanup_timeout` and the same accepted
Job reference/last observed status. A wait deadline returns 504 with
`job_wait_timeout` and the Job ID, without asserting termination. Callers must
inspect that Job before deciding on an explicit retry. Pre-admission errors have
no accepted Job ID. Success responses are unchanged; errors do not expose worker
messages or paths.

`media.generate.batch` (`POST /addon/v1/agent/generate/batch`) takes up to 50
independent generation items and runs them one after another inside a single
call. It exists because a separate call per asset is not merely slower: the Host
unloads the language model around each generation and rebuilds the caller's
conversation afterwards, which measured 40-350 seconds against 13-16 seconds of
actual image generation. The image model stays loaded for the whole batch, so
items after the first skip the model load; the run is sequential because one GPU
and one worker cannot be shared. No clock bounds the batch as a whole: each item
is bounded by the worker timeout it already had, and the Host is kept informed by
progress that only moves forward, reported as this item's share of the batch.
Items are independent, so one failure does not stop the rest and the response
reports each outcome with `partial` and `atomic: false`.

Context actions require a host-issued opaque `grant:` ID. Raw paths are rejected.
`media.pack` commits one existing immutable Media Forge asset to a Host-issued
project output `grant:`. Choose exactly one of two mutually exclusive forms:

- Single: `output_grant_id`, `asset_id`, optional `filename`; omit `items`.
- Batch: `output_grant_id`, `items` (1–32); omit top-level `asset_id` and
  `filename`. Each item has its own `asset_id`, optional `filename` and `role`.

Prefer the single form for one file. Mixed forms are rejected before writing;
unused fields must be omitted, not filled with duplicate values or nulls. The Host
stages and atomically commits the bytes after size/SHA-256 verification; the
response returns the Host `asset:` ID and non-path metadata. In a batch, each
file commits independently; the whole batch is not atomic, and per-file receipts
report success or failure. It never accepts or
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
For `asset.pack`, omitted `output` or omitted `output.format` selects ZIP. An explicit
format must be `zip`, with `count=1`. Invalid explicit formats/counts are rejected
before Job creation. Image defaults remain PNG; historical Job requests keep their
original values.

The deterministic result is an `application/zip` asset containing the 21 PNG
layers, `atlas.png`, `manifest.json`, and a current-firmware pack at
`companion/packs/<name>/` with M5A v1 RGB565-BE base/eye/mouth clips and its v2
manifest. Repeating the operation over identical assets produces byte-identical
ZIP output. ZIP placement uses the same
`media.pack` output grant as images; no path field or M5-specific Host route is
added.

`asset.pack` with `profile=3d.reference_set` accepts two to five unique image
Assets and one ZIP output. `constraints` follows
[`reference-set-spec.json`](../schemas/reference-set-spec.json): distinct front
and side views are required; back/three-quarter and a canonical design are
optional. Declare `scale_m` along `scale_axis`, orthogonal forward/up axes,
parts with acyclic parents, and per-view landmarks (`uv` normalized from the
image's top-left, right/down positive). Scale and axes are declarations, not
measurements recovered from images. `origin_notes` records the source context.
Every declared image must occur exactly once in `inputs`; canonical may reuse
a view Asset. Routing is `auto`, semantic QA is false, and regeneration is zero.

The deterministic CPU ZIP contains `manifest.json` and `images/<asset_id>.png`.
The [manifest schema](../schemas/reference-set-manifest.json) records source and
normalized-image hashes, original license/provenance, and dimensions. PNG/JPEG/WebP
inputs are limited to 8 MiB and 4096 pixels per side, one frame; orientation is
normalized, private metadata stripped, and pixels are not resized. Output is
limited to 8 MiB per PNG, 128 KiB manifest and 64 MiB ZIP. No inference is run.
`needs_review`, `visual_consistency=not_reviewed` and `projection=unverified`
cannot be promoted by a caller; successful packaging is not visual approval.

Scene create/edit and their workflow forms accept optional
`reference_set_asset_id`. Only verified reference packages can be attached.
An edit with null/omitted field retains the prior package; a new ID replaces
the current dependency while old revisions retain their own ID/hash. Existing
scene ownership, revision conflicts and source/preview provenance apply.
No change is made to the package by an edit, and a new package is required for
changed images or declarations. ZIP download/delivery uses existing Asset APIs.
Scene backup/restore preserves the ZIP bytes and historical source-image IDs.
`scene.restore` provenance records a bounded `reference_set_origin`; those IDs
describe the original inputs, not new Library IDs. The package's embedded PNGs
remain usable even when its original parent images were outside the scene backup.

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

The optional `constraints.compile_options` object is included in the published job request schema and versioned as
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

Available `3d.scene_recipe` now includes additive `authoring_guidance` metadata,
also returned by `media.capabilities`. It describes capability/schema discovery,
staged edits, actual image evidence, recovery and separate completion gates.
It does not enable a VLM or advertise future operations. Runtime-unavailable
responses omit both operation lists and authoring guidance. See
[agent guide](agent-3d-authoring-guide.md) and [research](research/ai-blender-game-asset-authoring.md).

The additive `mesh.create` typed operation accepts 3–4096 local-space vertices,
1–4096 triangle/quad faces with zero-based indices, a new stable object ID, name,
smooth shading and optional location/rotation. Repeated/out-of-range indices,
duplicate faces, degenerate fan triangles and unreferenced vertices are rejected.
The worker independently checks topology and the existing scene growth budget
before allocation. Open surfaces are allowed for garments; watertightness,
retopology, UV generation and simulation are not implied. Existing recipe tools,
Jobs, provenance and independently validated `.blend`/GLB revisions are reused.

Additive `mesh.create.require_closed` is a strict boolean, default `false`.
When `true`, core and worker reject boundary edges, edges shared by more than two
faces, and two incident faces traversing their shared edge in the same direction.
Core/worker diagnostic exceptions report boundary/multiple/winding edge counts
before allocation; the public route retains its `invalid_scene_recipe` error code.
Detailed per-edge MCP feedback is not added in this slice. This
does not verify vertex fans, self-intersections, signed volume, outward orientation
or visual quality, and does not repair geometry. Omission retains open-cloth support.
Discover the field in the installed schema before submitting it to an older worker.

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


## Scene observation (additive M2a)

`media.scene.observe` → `POST /addon/v1/agent/scene/observe`.
Input schema: [`scene-observe-request.json`](../schemas/scene-observe-request.json).
Use the normal authenticated agent envelope. Requires existing `jobs.write` authority.

```json
{"input":{"scene_id":"scene_11111111111111111111111111111111",
"revision_id":"revision_22222222222222222222222222222222",
"observation":{"center":[0,0,1],"span_m":4,"views":["front","side","back","three-quarter"],
"mode":"clay","resolution":512}}}
```

Returns the existing detached scene Job projection (`job_id`, `status`, `host_job_id`,
`input_sha256`). Poll `media.job.status`; cancellation/retry use the existing scene Job
lifecycle. Optional retry_job_id requires identical input and the original runtime pin.
Historical revisions are allowed; ownership and revision membership are verified before
Host child admission. Rendering does not commit a new scene revision.

The succeeded result contains the selected `revision`, scene document, frozen `observation`,
`images` entries with view/asset_id/sha256, renderer identity, and `object_colors` for object-ID
mode. Job asset_ids are ordinary PNG assets. Source hash/revision/spec are in provenance. Renderer PNG metadata (including private paths and dates)
is stripped before registration; image pixels are preserved as RGB.
The scene document may have a newer current_revision_id than the historical rendered revision.

Limits: center coordinates ±10000m; span_m >0.001 and ≤10000m; 1–4 unique fixed views;
256 or 512 square pixels; one mode (material/clay/silhouette/object_id); frame0;
256 mesh objects / 1024 total objects; conservative geometry cost ≤1000000;
only mesh/armature/empty/light/camera, no instances or particles, and bounded
bevel/mirror/fixed array/armature modifiers; unsupported geometry is rejected;
each PNG ≤4MiB; worker report ≤128KiB; existing Blender timeout.
CPU Cycles, 2 threads, 16 samples, fixed lights and explicit orthographic framing.
No GPU is used or leased. A scene render is evidence, not an automatic quality verdict;
semantic_review on an observation result remains not_tested; image creation itself does not review the scene.

### Advisory scene image review

`media.scene.review` → `POST /addon/v1/agent/scene/review`, with
[`scene-review-request.json`](../schemas/scene-review-request.json).
Requires normal scene ownership, `jobs.write` and `ai.inference`. It returns an
existing detached scene Job; poll `media.job.status`, cancel with `media.job.cancel`.
The exact revision's runtime identity remains pinned, but review launches no Blender
process and acquires no second GPU lease. Host owns vision admission and routing.

Provide `scene_id`, `revision_id`, `intent`, and 2–4 unique `observation_asset_ids`.
Images must include front and side, originate from `scene.observe` for that exact
source/revision/runtime, have matching ObservationSpec and object IDs, and pass
byte/provenance/dimension checks. Historical revisions are allowed. Rendering
another revision with identical-looking bytes is not interchangeable evidence.
New observation provenance records actual stable mesh IDs; old observations may
have none, in which case object-specific findings cannot name guessed IDs.

The revision's `reference_set` dependency is used automatically. If optional
`reference_set_asset_id` is supplied it must equal that dependency. Reference
images are read from the verified package, including restored packages whose
historical original image IDs are no longer current Library IDs.

Images are sent to `vision.analyze` as one labelled observation sheet and, when
present, one or two reference sheets (at most 768 pixels per side). A distinct
canonical image is included too: at most three submitted sheets for nine original
images. This respects Host's four-image bound without dropping selected views. Panels are fitted
independently; their pixel sizes are not metric measurements. Evidence records
source hashes, submitted JPEG hashes/bytes, sheet IDs and image pixel regions.

The model must return the bounded [visual review schema](../schemas/scene-visual-review.json):
at most three issues with validated evidence IDs, scope, known object ID where
applicable, expected improvement and optional suggested operation. Unknown
evidence/objects or inconsistent verdicts fail the Job. Unsupported operation
suggestions remain advisory, are listed explicitly, and set `review_state=needs_review`.
Unavailable vision/invalid response is a failure with no successful review Asset;
there is no text-only fallback. Cancellation interrupts the awaited gateway call;
live provider termination/resource-release acceptance is a separate gate.

Successful execution returns an immutable ZIP Asset containing `review.json` and
a `result.review` projection with deterministic revision validation separated
from advisory visual findings. All cited input Assets are rechecked after inference.
`semantic_review=completed` means the call and evidence/schema checks completed;
`asset_approval=not_granted` and `edits_executed=false` are fixed. A no-visible-issues
verdict applies only to the submitted stills. It does not certify topology,
deformation, animation, reference calibration or game readiness, and cannot
rewrite the ReferenceSet's needs_review state or advance the scene head.
No workflow action is added; existing create/edit/material workflow contracts are unchanged.

Invalid input returns invalid_scene_observation; runtime/owner/revision failures reuse scene
errors. Worker/timeout/report failures are scene_observation_failed/scene_observation_timeout/
scene_observation_invalid. Partial images are never published as a succeeded observation.
Untrusted scripts, paths, arbitrary cameras, render engines or operators are not accepted.

### Bounded curve operations and mesh selectors (M3a)

Scene recipes add `mesh.loft`, `mesh.sweep`, `mesh.sections.set`,
`mesh.bridge_loops`, `modifier.subdivision`, `mesh.weld` and `mesh.decimate`. Public create/edit/workflow
schemas enumerate the exact fields. Existing operations retain their meaning.

```json
{"type":"mesh.loft","object_id":"tail","name":"Tail",
 "sections":[{"center":[0,0,0],"radii":[0.3,0.25]},
             {"center":[0,0.7,0.1],"radii":[0.15,0.13]},
             {"center":[0,1.3,0.3],"radii":[0.01,0.01]}],
 "radial_segments":16,"samples_per_segment":3,"caps":"both"}
```

Sweep uses `path_points` (coordinate arrays, never filesystem paths).
Loft/sweep use 2–32 controls, 8–32 radial segments, 1–8 samples per segment,
local-meter coordinates and positive radii 0.001–100 m. Uniform Catmull-Rom
centers with transported elliptical frames produce mesh geometry. Radius
interpolation is linear. Optional location/rotation transforms act on the whole
mesh. Closed caps do not check self-intersection or anatomical quality.

Recipe results, source provenance and `media.scene.snapshot.mesh_geometry`
provide bounded facts conforming to `schemas/scene-mesh-geometry.json`: actual
float32 position/face SHA256, counts, edge diagnostics, up to 16 boundary loops
of 3–64 indices, and valid procedural controls. This is a partial selector
projection: only meshes up to 16,384 vertices / 32,768 polygons among the first
256 stable object IDs are included. Older/non-recipe revisions may have no
recorded facts; absence is not a passed geometry audit.

`mesh.sections.set` requires `expected_geometry_sha256` and the same number
of control sections. Sampling/topology, UVs and vertex weights are retained;
stale hashes or externally changed topology fail before mutation/publication.
Scene edits also retain the existing current-base-revision check.

`mesh.bridge_loops` requires `object_id`, `other_object_id`, both geometry hashes,
ordered `boundary` / `other_boundary` with equal counts, and optional
`twist_offset` -63..63. Both meshes must be independent, static, unweighted and
without modifiers/parents/constraints; transforms must be nonsingular and not
reflected. The worker verifies single-face boundary edges, chooses nearest loop
alignment plus twist, preserves face winding and consumes the other object.
Existing materials/UVs are preserved. New joint UVs are unset (zero) and require
an explicit UV operation. Procedural controls end after joining; old revisions
remain available. No hole cutting, intersection resolution or retopology is implied.

`mesh.weld` merges vertices that share a position (`distance_m`, default 1e-5)
and optionally recalculates normals. glTF splits vertices at UV seams and the
importer does not rejoin them, so generated 3D arrives as a triangle soup: one
measured model held 47,262 vertices in 11,466 disconnected shells with 16,902
loose vertices, and bone-heat binding could not weight a single vertex. Welding
it produced one shell with no loose vertices and a complete bind. UVs live on
face corners, so merging by position does not move a seam. It fails when nothing
merged, and when more than half the faces disappeared, rather than accepting a
distance that dissolved the model. Welding alone removed 52% of the vertices
here, so the decimation that follows can stay gentle.

`mesh.decimate` collapse-decimates one mesh in place to `ratio` of its faces
(0.001 < ratio < 1) and applies the modifier immediately, so later operations see
the reduced cage rather than an unevaluated dense one. `min_faces` is a floor: a
mesh already at or below it, or a decimation that would fall below it, fails
instead of committing. It refuses meshes carrying generating modifiers (subsurf,
mirror, array, bevel) or shape keys, and fails when nothing was removed. This
exists because generated 3D arrives as one dense mesh while `skin.bind_auto`
caps at 50,000 vertices and 100,000 polygons; collapse keeps panel edges that a
voxel-grid reduction erases. Reducing geometry is lossy and is not a retopology
or a quality operation.

`modifier.subdivision` adds one Catmull-Clark modifier at levels 1–2. It is
non-destructive and accepted by fixed observation. Conservative triangulated
geometry estimates are checked before growth, including repeated modifier
amplification. Geometry selectors refer to the original cage, not evaluated
subdivision vertices. Rig binding order/compatibility and deformation require
separate acceptance.

### Candidate edits and bounded refinement (M3b)

`media.scene.edit` accepts additive `publish_mode: "advance" | "candidate"`.
The default preserves existing behavior and durable retry payloads. Candidate
mode applies the recipe to the exact named current revision, validates the output
and creates a separate owner-scoped scene. The original head stays unchanged;
source provenance records `candidate_origin` and the original source hash.
Returned scene/revision IDs belong to the new candidate. No implicit adoption
or overwrite occurs.

`media.scene.refine` (`POST /addon/v1/agent/scene/refine`) accepts the existing
`{input:{...}}` envelope and returns a detached scene Job. Inputs are `scene_id`,
`base_revision_id`, `intent`, a fixed clay `observation` including front/side,
`max_iterations` 1–6 (default 3), and optional unchanged-input `retry_job_id`.
It requires current bounded geometry facts, the pinned runtime, jobs.write and
ai.inference, plus available Host vision.analyze and text.generate capabilities.

The loop renders actual observations, obtains at most three visual issues,
requests a typed local repair, creates a candidate, renders it under the same
settings and compares baseline/candidate/reference image sheets. The initial
local vocabulary is `mesh.sections.set` and `transform.set` on known mesh issue
targets, at most six operations per attempt. Camera/light/material changes,
unknown targets or hashes, arbitrary scripts and unavailable operations cannot
substitute for a local repair. A missing supported repair ends with
`local_repair_unavailable`; contradictory/uncertain initial references end with
`baseline_needs_review`.

Comparison includes at most four image sheets (two observations plus up to two
reference sheets). Each image/region/submitted JPEG hash is retained. A candidate
is selected only for an evidence-valid `improved` comparison with no increase in
reported boundary/nonmanifold/inconsistently wound edges and no missing bounded
mesh IDs. These deterministic checks are partial negative checks, not proof of
intersection-free or deformable geometry. Unchanged/worse/inconclusive or
structurally regressed candidates count as non-improvements. Two consecutive
non-improvements stop; a selected improvement resets that counter.

The original scene head is never advanced. The result includes selected
scene/revision IDs, all published Asset IDs, `report_asset_id` and a `refinement`
report with attempts, comparisons, stop reason and remaining issues. The immutable
ZIP report records full parent hashes. `asset_approval=not_granted` and
`shape_gate=advisory_only` remain fixed; surface/deformation are NOT TESTED.
Job success means bounded execution finished, including an explicit stop.

On failure/cancel, published candidates/evidence and a partial `refining` task
result remain inspectable. Active CPU preparation/processes are drained and the
current AI await is canceled. Actual Host provider termination/resource release
requires its own live acceptance. Restart marks active refinement stages failed;
an explicit identical-input retry starts a new Job without changing the original.
The refreshed child identity is read before every AI request.

### Hash-pinned UV editing and CPU texture baking (M4)

Recipes add `uv.seams.set`, `uv.unwrap`, `uv.pack` and `transform.apply_scale`.
Each names a stable mesh `object_id` and its current `expected_geometry_sha256`.
Seam selection is 1–4096 actual vertex-index edge pairs, with `mark` (default true)
and `clear_existing` (default false). Unwrap supports ANGLE_BASED/CONFORMAL;
unwrap/pack margin is 0.001–0.25 (default 0.02). Pack optionally rotates islands.
Results must have finite UV coordinates in the unit tile. Snapshot mesh facts
add up to eight UV map hashes, bounds and degenerate-triangle counts. These facts
do not certify overlap, texel density or appearance.

`transform.apply_scale` folds positive bounded scale into independent static,
unweighted mesh coordinates and sets object scale to one. Parents, children,
constraints, animation, shape keys and modifiers other than subdivision are
rejected. It changes the geometry hash and invalidates old procedural selectors.

`media.scene.bake` (`POST /addon/v1/agent/scene/bake`, `{input:{...}}`) creates an
existing detached scene Job. See `schemas/scene-bake-request.json`. Inputs pin
low scene/revision/object/geometry hash, optional `high_source` with the same four
identifiers, UV map (default UVMap), unique channels normal/ao, resolution
256/512/1024, margin 1–32 pixels and cage extrusion 0–1 meters. Normal requires
high_source. Both revisions must belong to the caller and use the same pinned
runtime. The historical low revision need not be the current scene head.

The fixed Blender worker uses CPU Cycles, frame zero, 16 samples, two threads
and disabled autoexec. The low target must be static, unit-scale, unmodified and
have finite, nondegenerate UVs in [0,1]. High geometry is loaded only in the
private bake process, never inserted into the low scene. Normal is tangent-space
OpenGL; AO is isolated target occlusion. Existing geometry growth limits apply.

All PNGs and source hashes are verified before publication through existing
Assets/provenance. Metadata is stripped. Both parent source hashes, settings,
UV hash and worker/output hashes are retained. `nontransparent_pixels` counts
alpha values at least 0.5; it is **not** ray-hit coverage. Results explicitly mark
`ray_hit_coverage=not_measured`, `uv_overlap=not_checked` and
`surface_approval=not_granted`. No scene head changes. Normal images can be applied
through existing non_color normal material binding. AO binding/export is not
added by this slice. Cancellation/timeout drains the owned process and runtime
pin; failed publication rolls back outputs. Restart fails active bake Jobs.

### Local weights and baked leg IK (M5)

Recipes add `skin.weights.set`, `skin.weights.smooth`, `skin.weights.normalize`
and `ik.leg.bake`. Existing bind/pose/rotation clip contracts remain intact.
Weight operations name mesh `object_id`, `rig_object_id`, the current
`expected_geometry_sha256` and 1–4096 unique `vertex_indices` (0–16383).
`set` replaces each selected vertex's influences with 1–4 distinct known deform
bones, positive weights summing to one. `smooth` averages along actual cage edges
with factor (0,1] (default .5), 1–8 iterations (default 1), deterministic top-four
selection and normalization each iteration. Neighbors outside the selection
contribute but are not changed. `normalize` retains/normalizes the strongest four
existing nonzero weights, with group-index tie breaking.

Targets must be independent meshes already parented to a typed rig with an
armature-first/subdivision-after stack. Unknown/locked groups, invalid weights,
stale geometry and resulting unweighted/unnormalized bindings fail without a new
revision. Geometry and unselected weights are preserved. Additive `skin_weights`
mesh facts report counts, maximum influences and sum error for bounded meshes;
no collapse/intersection or anatomical quality approval is implied.

`ik.leg.bake` requires an identity typed rig, connected known `upper_bone_id` and
`lower_bone_id`, `clip_id`, `name`, `fps` 1–60 (default 24), `frame_count` 1–120,
`loop` / `replace` (default false), optional pole_angle_degrees ±180 and 2–121
ordered `targets`. Each target has `frame`, finite world `target` and `pole`
coordinates. First/last frames are zero/frame_count; loop endpoints must match.
Target/pole values interpolate linearly and are solved at every integer frame.

Fixed CPU Blender IK uses two bones, 64 iterations and no stretch. A fixed small
knee rotation seeds a straight chain; targets/poles determine the solution.
Unreachable targets and singular poles fail before scene controls are created.
Temporary controls/constraints are removed, then the ordinary rotation clip is
created and reevaluated at every sample. Any target error above 1 cm or unrepresentable
translation/scale fails. Loop solutions must agree before endpoint rounding.
The source action retains a bounded `media_forge_ik_audit` JSON property with
sample count, maximum target error and zero retained constraints. Other clips
remain stashed. This is not foot orientation, root motion, multi-leg coordination
or a complete walk generator; pose and viewer acceptance remain necessary.

### Translation keys and typed playback intent (M6)

`animation.clip` rotation keys add optional `translation_m`, a rest-bone-local
XYZ meter offset bounded to ±100 on each axis. Rotation remains required. Every
key in a translated track must include translation; loop clips require equal
first/last offsets as well as rotations. Missing/null translation is omitted
from serialized requests, preserving legacy retry payloads and rotation-only
curves/budgets. Added location curves count toward the same scalar-key budget.
Saved typed location channels are recognized when appending/replacing clips;
old clips and their immutable revisions are retained. This is node translation,
not gameplay root-motion extraction or retargeting.

GLB animation extras add `media_forge_clip` only for matched typed action names:
`schema_version=media-forge.clip-playback@1`, `clip_id`, `fps`, `frame_count`,
`loop_requested`. Other animation extras and binary buffers are retained.
This declares playback intent, not seam/velocity quality. In the MediaForge
viewer, a valid typed false flag plays once and holds the last frame; true repeats.
Unknown/legacy metadata preserves repeat behavior. Play resumes a paused clip
or restarts a finished clip; explicit Stop restores rest, while Restart returns
the selected clip to its first frame. Switching stops old actions before activating
the selected clip, including tracks which animate different properties.

Public `/schemas/{schema_name}` responses use compact JSON so expanded scene contracts
fit the Host 64 KiB discovery limit. Parsed schema content and media type are unchanged.

For agent discovery, `job-request.json` also declares the existing ReferenceSetSpec
fields directly in `constraints`. They are optional on generic jobs; the existing
`3d.reference_set` pack validator still requires its name/views/scale/origin fields.
Image generation does not require them. No wrapper field or second packing API is added.

Private `scenes.material.extract` (`POST /workspace-api/scenes/{scene_id}/material-image`
for standalone) accepts `selection` as the existing scene-texture context. It
verifies owner/current revision and extracts only directly connected packed
base-color or emission images through the trusted Blender worker. It creates an
immutable PNG with scene-source lineage, leaving the scene unchanged. External
images and shader-derived appearances are rejected. The texture panel uses
normal `image.edit` inputs for 1–4 candidates, so their parent image is recorded.
Candidate selection still requires separate material preview and adoption.

Private `scenes.material.images` accepts only `{scene_id}` and returns Library metadata
with `scene_image_kind` (`used`, `base`, `variant`) for authorized scene revisions,
source ancestors and image descendants. `GET /workspace-api/scenes/{scene_id}/material-images`
uses the standalone owner. Reads do not extract images or create jobs. Traversal is
bounded to 1024 direct matches, 1024 graph records, eight edges per direction
and 256 returned images;
`truncated` is explicit. No asset bytes, paths or client-supplied owner are accepted.

## Library Trash (private workspace)

`library.trash.preview` / `library.trash.apply` (workspace WebSocket) and
`POST /workspace-api/library/trash/{preview|apply}` (standalone workspace)
accept `action: trash|restore|purge` and 1–100 `asset_ids`. A scene asset expands
only to its revision's Blender/GLB pair. Apply requires the preview's
`confirmation_fingerprint`; changed selections must be confirmed again.
`all_trashed: true` replaces `asset_ids` only for purge, bounded to 5,000 assets
and excluding scene revisions owned by another account. Running work blocks removal.
These are private workspace operations; the frozen public required fields remain unchanged.

Normal Library/scene lists omit trashed revisions. Trash listing uses `trash: true`.
Purged content/metadata asset endpoints return 404; immutable provenance and lineage
records remain with a deletion tombstone. Private relation projections expose
`in_trash` / `purged`. Completed scenes retain embedded images; purge verifies
packing for retained material dependencies. Filesystem cleanup is durable/retryable:
a failed unlink returns `library_purge_cleanup_pending`, remains in Trash, and is
retried on startup or another explicit purge. Purged assets cannot be restored.


### Automatic rigging of upright characters (0.33.11)

The existing `media.scene.rig` / `rig.auto` contracts are unchanged. When the
mesh has two separated feet and multiple torso cross-sections containing the
body and both arms, the worker recognizes an upright character with lateral X
and vertical Z axes. It adds head, upper-arm, forearm and hand support and uses
forward/back leg swing with opposing arms. Other shapes retain the general
limb rig. Classification does not certify anatomy or animation quality; inspect
the saved revision's deformation and contact with the ground.

The source revision remains immutable. Already rigged revisions are not
rewritten by a service update; restore the original unrigged revision as a new
revision before applying the improved rig.

Since 0.33.12, upright `rig.auto` can interpolate a tiny missing heat-weight
island from the nearest original weighted vertices. Missing vertices must be
at most 0.5% of the mesh and 128 total, each island at most 64 vertices and 2%
of body height across, and donors within 0.5% of height. The worker records
counts and distances in `automatic_weight_repairs`; geometry, UVs and images
are preserved. Larger omissions still fail. General `skin.bind_auto` keeps
its strict missing-weight rejection.
