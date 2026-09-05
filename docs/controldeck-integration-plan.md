# ControlDeck Media Forge — ControlDeck Integration Plan

Status: Draft / target architecture  
Date: 2026-08-20

## 1. Executive decision

Media Forge must remain a **real ControlDeck add-on**, not a Media-specific feature compiled into ControlDeck and merely hidden behind a flag.

At the same time, ControlDeck should provide the generic host facilities that powerful add-ons need so integration feels native rather than like an unrelated web app.

The target split is therefore:

### ControlDeck core owns generic host capabilities

- add-on lifecycle and manifest validation
- activation/deactivation state
- declarative UI contribution slots
- embedded/sandboxed view host
- scoped authentication/authorization bridge
- durable Jobs and progress/event surfaces
- file/project grants
- notifications and audit integration
- workflow remote-executor contribution
- agent remote-tool contribution
- generic AI/GPU resource broker and queue/admission control
- health/capability discovery

### Media Forge owns Media-specific behavior

- image/video/animation/3D media APIs
- local model/runtime adapters
- model registry and media capability routing
- media asset library/provenance
- M5Stack profiles and strict validators
- 2D-game/Web/Manga/3D profiles
- Media workspace frontend
- Media-specific worker environments and heavy dependencies

ControlDeck may contain generic UI surfaces capable of rendering add-on contributions, but no Media-specific navigation, route, workflow node, command, model list, or settings panel should appear unless Media Forge is enabled and the corresponding contribution is healthy/authorized.

---

## 2. Why neither extreme is acceptable

### 2.1 Rejected: build Media directly into ControlDeck and hide it when disabled

This looks convenient initially, but creates a plugin-shaped monolith:

- ControlDeck accumulates Media-specific code and dependencies
- Media releases become tied to ControlDeck releases
- future add-ons cannot reuse the integration contract without copying patterns
- disabling a plugin only hides UI rather than removing executable surfaces
- tests and migrations remain permanently coupled

Therefore ControlDeck should contain only generic extension points, not the Media implementation.

### 2.2 Rejected: leave Media Forge as only an external navigation link

ControlDeck Plugin SDK v1 currently exposes only external `navigation`. That boundary is safe, but insufficient for a first-class local AI subsystem.

A new tab cannot provide the desired seamless integration with:

- ControlDeck Jobs
- Project Lab/OpenCode project context
- workflow catalog
- agent tools
- common GPU resource management
- permissions/audit
- global notifications
- native mobile navigation

Therefore Plugin SDK v1 should remain supported for simple plugins, while ControlDeck adds a backward-compatible richer add-on contract.

### 2.3 Rejected: arbitrary plugin Python/JavaScript imports into ControlDeck

Do not solve integration by importing untrusted add-on modules into the ControlDeck backend or main frontend bundle.

That causes:

- dependency conflicts
- crash propagation
- direct cookie/DOM/internal API access
- difficult privilege auditing
- version coupling

The preferred architecture is **out-of-process execution + declarative contributions + scoped bridges**.

---

## 3. Add-on Contract v2: generic host extension model

ControlDeck should evolve Plugin SDK v1 into an Add-on Contract v2 while preserving v1 compatibility.

A v2 add-on is still a separate process/service. Its manifest declares what it contributes and which host capabilities it requests.

Conceptual manifest:

```json
{
  "api_version": "2",
  "id": "media-forge",
  "name": "Media Forge",
  "version": "0.1.0",
  "publisher": "souten-yd",
  "runtime": {
    "kind": "external-service",
    "health_url": "http://127.0.0.1:9130/health"
  },
  "contributions": {
    "navigation": [
      {
        "id": "media",
        "label": "Media",
        "route": "/media",
        "permission": "media.view"
      }
    ],
    "embedded_views": [
      {
        "id": "workspace",
        "route": "/media",
        "source": "http://127.0.0.1:9130/",
        "permission": "media.view"
      }
    ],
    "commands": [
      {
        "id": "create-media",
        "label": "Create media",
        "route": "/media?new=1",
        "permission": "media.generate"
      }
    ],
    "settings": [
      {
        "id": "media-settings",
        "label": "Media Forge",
        "route": "/media/settings",
        "permission": "media.manage"
      }
    ],
    "workflow_executors": [
      {
        "type": "media.generate",
        "schema_url": "/addon/v1/workflow/media.generate/schema"
      }
    ],
    "agent_tools": [
      {
        "name": "media.generate",
        "schema_url": "/addon/v1/tools/media.generate/schema"
      },
      {
        "name": "media.scene.create",
        "schema_url": "/schemas/scene-create-request.json"
      }
    ]
  },
  "host_capabilities": [
    "files.scoped",
    "projects.read",
    "jobs.bridge",
    "notifications.publish",
    "workflow.remote_executor",
    "agent.remote_tools",
    "ai.resource_lease"
  ]
}
```

Exact names may change during implementation. The invariant is that integration is versioned, declarative, capability-scoped, and generic.

---

## 4. Activation semantics

Installed and enabled are distinct.

```text
not installed
installed + disabled
installed + enabled + healthy
installed + enabled + degraded
installed + enabled + unavailable
```

### Disabled means no executable/UI contribution

When Media Forge is disabled:

- no Media sidebar navigation
- no `/media` embedded app route
- no Media command-palette command
- no Media quick action
- no Media settings contribution
- no Media workflow executor in the executable catalog
- no Media agent tool in OpenCode/Codex/OMO tool discovery
- no Media GPU/resource lease holder
- no new host-to-Media background calls

Historical workflows/assets/configuration remain intact. Existing workflow definitions referencing Media operations remain parseable but show `unavailable` rather than being deleted or corrupted.

### Enable sequence

```text
enable requested
  -> manifest/schema validation
  -> runtime health check
  -> requested host-capability policy validation
  -> mint/re-establish scoped add-on session
  -> register effective contributions
  -> expose UI/tool/workflow metadata
```

### Disable sequence

```text
disable requested
  -> stop accepting new calls
  -> revoke add-on sessions
  -> cancel/release resource leases according to policy
  -> unregister effective contributions
  -> remove UI/tool/workflow availability
  -> optionally stop add-on service
```

No browser CSS hiding is accepted as the sole disable mechanism.

---

## 5. UI/UX integration

### 5.1 Native shell, isolated workspace

When enabled, Media Forge should feel like a native ControlDeck feature:

- desktop sidebar `Media`
- mobile navigation/More entry according to ControlDeck mobile-nav policy
- Command Palette actions
- optional Quick Action
- ControlDeck toasts/notifications for completion/failure
- global Jobs deep links
- `/media` within the existing ControlDeck shell
- consistent light/dark/accent/safe-area behavior

The full Media workspace remains isolated in a sandboxed embedded view or equivalent isolated app surface.

### 5.2 Declarative native contributions

Simple host UI is rendered by ControlDeck itself from manifest/runtime metadata:

- navigation
- commands
- quick actions
- settings links
- status badges/cards
- notification actions

This avoids loading Media Forge frontend code into ControlDeck's privileged React context.

### 5.3 Sandboxed embedded view

The Media workspace is shown in the ControlDeck content area rather than a new tab, but it must not automatically receive ControlDeck session cookies or unrestricted same-origin access.

Use a sandboxed iframe/webview plus an explicit MessageChannel/postMessage bridge, or an equivalent strongly isolated mechanism.

### 5.4 Stable design-token bridge

To make the add-on visually seamless without importing private ControlDeck UI components, expose a small stable token contract:

```text
theme
resolved color scheme
accent token
locale
safe-area insets
preferred density
basic radius/spacing token version
```

Media Forge uses these tokens to match ControlDeck while keeping frontend release independence.

---

## 6. Scoped host bridge

Do not issue a token that can call every ControlDeck API.

Media Forge receives only capability-scoped bridge methods granted to `plugin:media-forge`.

Browser-side examples:

```text
host.context.get
host.theme.get
host.route.open
host.file.pick
host.file.export
host.project.pick
host.job.open
host.notification.show
host.permission.has
```

Service-side examples:

```text
host.files.stage_read
host.files.commit_write
host.projects.get_context
host.jobs.register_remote
host.jobs.update_remote
host.resources.acquire
host.resources.renew
host.resources.release
```

Every state/data access method is schema-validated, permission-checked, plugin-ID scoped, and auditable.

---

## 7. Authentication and permissions

ControlDeck is the identity authority when Media Forge is used as an add-on.

Media Forge must not receive the raw ControlDeck session cookie.

Use a short-lived audience-bound add-on credential or host-proxied request model with properties such as:

```text
audience = media-forge
plugin_id = media-forge
short TTL
user identity only as required
granted capabilities
nonce/session binding
```

For the current Add-on Runtime HTTP contract, Media Forge validates this
credential through Host token introspection. It does not receive ControlDeck's
signing key and does not validate by importing Host internals.
The execution `subject` remains the authority for each Host operation. When
introspection supplies the additive signed `actor_subject`, Media Forge uses it
only as the stable owner key for durable scenes across per-call Agent Job
subjects; older Hosts safely retain subject-scoped ownership.

### Namespaced permissions

Long term, Add-on Contract v2 should support namespaced plugin permissions, for example:

```text
media.view
media.generate
media.edit
media.export
media.models.view
media.models.manage
media.assets.manage
media.admin
```

Critical concern: dynamically contributed permissions can leave stale RBAC grants after uninstall. Therefore ControlDeck should store plugin permission grants by `(plugin_id, permission_id)` and mark them inactive when the plugin is absent/disabled rather than flattening them permanently into core permission constants.

Until generic namespaced permissions exist, a minimal coordinated Media permission set may be added to ControlDeck, but it is transitional and should not become the pattern for every plugin.

---

## 8. Common AI Resource Broker

### 8.1 Do not make Media Forge reuse the LLM HTTP gateway directly

The existing LLM Gateway has valuable behavior, especially admission control, but its semantics are LLM-specific:

- OpenAI-compatible chat protocol
- prompt/max-token estimation
- llama.cpp slots/KV inspection
- `await_capacity()` for shared KV exhaustion

Images, video and 3D do not use token/KV capacity and may need an entire GPU for tens of seconds or minutes.

Therefore the reusable part must be extracted below the LLM protocol layer.

### 8.2 Target architecture

```text
                 ControlDeck AI Resource Broker
                 ├─ priority/fair queue
                 ├─ GPU/VRAM leases
                 ├─ model residency registry
                 ├─ admission control
                 ├─ wait/wakeup
                 ├─ cancellation
                 ├─ preemption policy (future)
                 └─ telemetry
                    ▲            ▲
                    │            │
          LLM Gateway adapter   Add-on lease API
                    │            │
                 llama.cpp    Media Forge
                                ├─ image
                                ├─ VLM
                                ├─ video
                                └─ 3D
```

The current LLM Gateway remains an OpenAI-compatible protocol adapter and uses the same broker underneath.

### 8.3 Generic resource request

Conceptual lease request:

```json
{
  "owner": "plugin:media-forge",
  "job_id": "abc123",
  "resource_class": "gpu.compute",
  "device": "auto",
  "vram_estimate_bytes": 18000000000,
  "execution_mode": "exclusive-preferred",
  "priority": 20,
  "interactive": true,
  "model_residency_key": "flux2-klein-4b-rocm"
}
```

`owner` above describes the resulting Broker record. An Add-on Runtime client
must omit that field; ControlDeck derives and forces it from the authenticated
Add-on identity so the caller cannot select another owner.

LLM requests may additionally include KV/slot requirements through provider-specific admission probes, but those probes should plug into the same scheduler rather than define the scheduler itself.

### 8.4 Broker responsibilities

- know GPU inventory and memory telemetry
- serialize incompatible large jobs
- permit safe concurrency where resource estimates allow
- avoid loading Media and LLM models simultaneously when VRAM is insufficient
- queue instead of failing with OOM
- report wait reason and queue position
- wake blocked jobs after release/model eviction
- cancel waiting/running leases
- keep an idle model warm when useful
- support priority without indefinite starvation
- expose telemetry to ControlDeck monitoring

### 8.5 Fairness

Pure priority scheduling can starve background jobs. Use priority plus aging/fairness.

Suggested classes:

```text
interactive          high
agent-interactive    high/medium
workflow             medium
background/batch     low
maintenance          lowest
```

Queue age gradually increases effective priority within safe bounds.

### 8.6 Model residency optimization

VRAM allocation is not the only cost. Model unload/reload can dominate latency.

The broker should understand a `model_residency_key` and prefer batching nearby compatible jobs when it does not violate interactive latency/fairness.

This enables:

- keep current LLM loaded during bursts
- run several FLUX image requests before evicting it
- unload image model before a large video model

without exposing model names in public high-level APIs.

---

## 9. Integrating with ControlDeck Jobs

ControlDeck already has durable Jobs with:

- priority queue
- DB snapshots
- progress/events
- cancellation
- browser-independent execution

Reuse it for the user-facing job concept.

### Required refinement

Current global `MAX_CONCURRENT` execution slots should not be consumed by jobs that are merely waiting for GPU resources.

Introduce explicit job substates or admission phases:

```text
queued
waiting_dependency
waiting_resource
starting
running
postprocessing
validating
succeeded
failed
canceled
```

Recommended scheduler split:

```text
Job Queue
   -> dependency/admission check
   -> Resource Broker lease
   -> execution slot
   -> runner
```

A job waiting 60 seconds for VRAM does not occupy an execution slot intended for CPU/network jobs.

High-frequency diffusion/video step telemetry remains in Media Forge; ControlDeck receives normalized progress milestones to avoid excessive DB/event volume.

---

## 10. Files and Project Lab integration

Media Forge must not gain unrestricted filesystem access because it runs locally.

When called through ControlDeck, use the host's existing allowed-root/project boundary.

Preferred patterns:

1. staged file handles/assets
2. scoped path grants with validated realpath, symlink boundary and access mode

Generation returns a logical asset first:

```text
asset_id
mime_type
size
hash
provenance_id
preview
suggested_filename
```

Writing into a project is a separate authorized commit action.

Future generic project-context actions can make integration seamless:

```text
Create asset for this project
Edit selected image in Media Forge
Generate missing assets
Open project Media library
```

These are generic context/command contributions, not hard-coded imports between Project Lab and Media Forge.

---

## 11. OpenCode / Codex / OMO integration

Media Forge advertises a small capability-driven remote tool catalog only while enabled/healthy:

```text
media.generate
media.edit
media.inspect
media.asset_pack
media.video.generate
media.asset3d
```

Agents discover capabilities such as:

```text
image.text_to_image = available
image.multi_reference_edit = available
image.strict_edit = available
video.image_to_video = unavailable
3d.image_to_3d = experimental
```

Agents do not hardcode FLUX/Qwen/Wan model IDs unless the user explicitly pins a model.

Agent file writes follow the same project grant rules and cannot bypass ControlDeck filesystem restrictions through Media Forge.

### 11.1 Non-interactive project output grant prerequisite

The existing browser file/export picker is not sufficient for an OpenCode run:
the Add-on MCP token is user-bound but is not bound to the current project and
cannot obtain an output grant without a separate human picker action.

**Media Forge cannot solve this gap because doing so would require receiving or
deriving a raw ControlDeck project path.** ControlDeck must provide the minimum
generic acceptance feature instead:

1. bind each OpenCode Add-on MCP token to the already-resolved current Project
   Lab project when that project is inside the managed project root;
2. advertise a generic Host MCP tool that creates an output grant only for an
   enabled Add-on with `projects.pick` and `files.export` grants;
3. accept a bounded project-relative existing directory, resolve it inside the
   token-bound project with the existing realpath/symlink policy, and return only
   an opaque `grant:` ID plus non-path metadata;
4. pass only that grant ID to the Add-on tool call. The Add-on never receives the
   project ID, relative directory, absolute path, or Host filesystem metadata.

This is an Add-on Platform/OpenCode project-output feature, not a Media-specific
route, provider, model, or policy. TUI/runs outside a managed Project Lab project
do not receive the Host grant tool. Grant creation is request-scoped and keeps
the existing owner/add-on/expiry checks. The first Media Forge vertical slice
uses the existing atomic single-output commit; bounded multi-file pack
transactionality remains a later G4 slice if a pack contains more than one file.

Implemented and accepted on 2026-08-23. ControlDeck PR #232 binds only a direct
managed-project CodeDEV run and exposes the generic
`control_deck.project_output_grant`; PR #233 aligns the generic MCP client timeout
with the existing Host job/bridge bounds. Media Forge `media.pack` consumes only
the resulting opaque export grant and uses the existing staged atomic output
commit. A real OpenCode 1.18.18 run completed generate, inspect, grant, pack,
project reference update, build, and test without exposing a Host path.

---

## 12. Workflow integration

Add-on Contract v2 should support **remote workflow executors**, not imported Python executor modules.

Keep the catalog high-level, for example:

```text
media.generate
media.transform
media.asset
```

Avoid model-specific node proliferation.

ControlDeck owns:

- workflow permission checks
- dry-run contract
- template expansion
- timeout/cancellation
- job correlation

Media Forge owns media-specific execution.

When the add-on is disabled, historical nodes remain visible as unavailable but cannot execute.

---

## 13. Health and partial capabilities

Do not confuse plugin activation with optional worker health.

Examples:

```text
Media core service healthy
Image worker available
VLM worker available
Video worker not installed
Blender worker available
3D generative worker experimental/unavailable
```

The Media workspace should remain usable even if an optional worker is absent. Tabs/actions should be capability-aware:

- hide or disable only the unavailable operation
- explain missing worker/model
- do not fail the entire add-on because video or 3D is unavailable

ControlDeck removes the whole contribution only if the add-on is disabled/uninstalled or the core workspace cannot be served.

---

## 14. ControlDeck-side implementation phases

### Host Phase A — Contribution framework

- Add-on Contract v2 manifest/schema
- preserve Plugin SDK v1 compatibility
- enabled-only effective contribution registry
- generic navigation/command/settings/quick-action metadata
- `/api/v1/meta` or authenticated extension metadata split as appropriate
- fail-closed schema validation

Exit:

- a test add-on can appear/disappear without ControlDeck rebuild
- disabled add-on routes/contributions are not executable

### Host Phase B — Embedded isolated workspace

- same-shell add-on route host
- sandbox policy
- host bridge
- theme/design tokens
- mobile behavior

Exit:

- add-on visually operates inside ControlDeck without raw session-cookie exposure

### Host Phase C — Scoped service bridge

- short-lived add-on credentials
- capability grants
- file/project broker
- notifications/audit
- generic namespaced permission framework or transitional mapping

### Host Phase D — Jobs + AI Resource Broker

- resource-aware admission before execution slots
- GPU inventory/VRAM leases
- priority + aging queue
- wait reason/position
- lease cancellation/expiry
- LLM Gateway moved to broker-backed admission
- add-on lease API

### Host Phase E — Workflow/Agent contributions

- remote workflow executor contract
- remote agent tool contract
- enabled/healthy-only discovery
- historical unavailable-node behavior

### Host Phase F — project/context extensibility

- generic context commands
- Project Lab selection/context bridge
- artifact import/export bridge

---

## 15. Media Forge implementation phases against the host

### MF0 — Standalone core + v1 compatibility

Media Forge local service, generic image API, jobs/assets/provenance. It may initially register a Plugin SDK v1 navigation link while Add-on v2 is under development.

### MF1 — Add-on v2 workspace

Move to native-shell `/media`, contribution metadata, scoped identity/bridge.

### MF2 — Common resource broker

Media image/VLM workers request ControlDeck leases; remove any independent global-GPU admission logic except worker-local safeguards.

### MF3 — Agent/workflow/project integration

Remote tools/executors and project asset workflows.

### MF4+ — Video/Blender/3D/Manga capability packs

Add without changing ControlDeck public integration primitives.

---

## 16. Acceptance criteria

### Plugin reality

- Media Forge implementation is in its own repository/runtime environment.
- ControlDeck does not import Media Forge backend/frontend implementation modules.
- ControlDeck core has no hard dependency on PyTorch/Diffusers/Wan/Blender/etc.
- Media Forge can be upgraded independently within declared contract compatibility.

### Activation correctness

- clean ControlDeck with Media Forge absent has no Media UI/API/tool/executor contribution.
- installed but disabled has no Media UI/API/tool/executor contribution.
- enabled and healthy shows appropriate Media UI/UX.
- disabling revokes the effective contributions without deleting user Media data.
- stale direct navigation to `/media` while disabled returns unavailable/404 rather than silently rendering a hidden feature.

### Integration

- Media workspace is embedded in ControlDeck shell.
- theme/mobile/notifications/jobs are coherent with ControlDeck.
- OpenCode/Codex/OMO see tools only while enabled and authorized.
- workflow operations are executable only while enabled/healthy.
- file writes cannot escape granted roots/projects.

### Resource management

- LLM and Media jobs share a common GPU resource broker.
- a large Media job queues rather than OOMing a resident LLM when policy says they cannot coexist.
- waiting-for-GPU jobs do not consume unrelated execution slots.
- cancellation of a waiting job removes its lease/request promptly.
- queue status/reason is visible to the user.

### Extensibility

- the same Add-on v2 mechanisms can host a future non-Media add-on without adding another plugin-specific path to ControlDeck core.

---

## 17. Final architecture rule

**ControlDeck should know how to host capabilities; Media Forge should know how to create media.**

If a proposed change requires ControlDeck to understand a specific Media model, prompt format, sprite recipe, diffusion step, Blender operator, or manga parser, the boundary is probably wrong.

If a proposed Media Forge feature bypasses ControlDeck's generic identity, project/file boundary, Jobs, or resource coordination when used as an add-on, the integration is probably too weak.

## 18. Integrated 3D Studio boundary (2026-09-05)

The 3D Studio, texture authoring and server-side Web Blender are MediaForge features.
Implementation, docs, shared assets/Jobs and release packaging remain in this repository.
Keep the existing `media-forge` identity, service and workspace; do not register a second add-on.
See [3D Studio](design-3d-studio.md), [runtime/Web](design-blender-runtime-and-web.md),
[assets/OpenCode](design-3d-assets-and-opencode.md) and [release rules](development-release-3d-studio.md).

- Reuse Host Agent MCP projection; do not install a separate OpenCode or edit its global config.
- Keep existing image/G8 tools unchanged. New scene tools require additive schemas and current Host validation.
- Long authoring/render operations return durable job references. Validate the current detached Host Job
  and job credential refresh path; do not extend a synchronous agent call indefinitely.
- Browser GUI traffic uses the existing authenticated binary WebSocket relay with a session-owned gateway.
  The presence of a relay is not proof of noVNC compatibility or post-connect revocation: test both.
- GPU GUI sessions must account for retained VRAM. Release GPU processes before returning their lease;
  coordinate image/LLM/Blender stages without holding competing leases across waits.
- Browser disconnect is not batch cancellation. GUI disconnect has explicit save/grace/idle/stop policy.
- Blender and display processes are non-root isolated runners, managed independently of HTTP request lifetime.
- Blender install/update/remove are MediaForge setup operations; OS drivers and privileged dependencies
  are diagnosed, not silently installed. Runtime removal preserves user assets and scene history.
- ControlDeck signature verification is already present at the referenced current commit. Use the existing
  MediaForge publisher/capability trust; do not add a new feature ID or per-release Host checksum pin.
- If a generic Host facility is insufficient, document the exact gap and use a separate generic Host PR.

These are target requirements. This documentation change does not register new tools, modify Host,
install Blender, or claim the new GUI/session integration has passed acceptance.
