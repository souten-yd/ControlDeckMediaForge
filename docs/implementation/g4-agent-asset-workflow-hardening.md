# G4 hardening — Agent Asset Workflow / Purpose-aware Generation / Placement

Status: implementation plan / not yet implemented  
Date: 2026-08-24  
Target repository: `souten-yd/ControlDeckMediaForge`  
Host reference: `souten-yd/ControlDeck` (normally read-only)

This is a **hardening slice after the already-completed G4 Coding Agent placement path**. It does not replace G4, Creative Intelligence, G5, or G6. It records improvements discovered through real OpenCode use and makes the Media Forge / ControlDeck ownership boundary explicit before further plugin growth.

The existing sources of truth remain:

- `docs/base-plan.md`
- `docs/controldeck-integration-plan.md`
- `docs/design-creative-intelligence.md`
- `docs/implementation/goal-roadmap.md`

If implementation reveals a conflict with those documents, update the relevant design source first. Do not silently change the boundary from this implementation plan.

---

## 0. Why this slice exists

A real OpenCode run successfully exercised the intended G4 path:

```text
OpenCode
  -> ControlDeck project output grant
  -> Media Forge image generation
  -> Media Forge inspect
  -> Media Forge media.pack
  -> project asset placement
  -> file existence/type verification
```

The core architecture therefore works. The run also exposed product-level friction that should be fixed before scaling the same path to G6 game packs, responsive Web assets, video, 3D, and future plugins.

Observed issues:

```text
A. A project output grant was obtained too early and later had to be reacquired.
B. The requested destination directory did not yet exist, so the agent had to create it before retrying the grant.
C. The agent wrote a long image-generation prompt itself instead of primarily expressing asset purpose/constraints.
D. A request described as a wide landscape still produced a 1024x1024 image.
E. Multiple related assets were placed through repeated single-asset media.pack calls.
F. The agent used shell-level ls/file checks because the placement response was not sufficient as a final receipt.
G. Generated-image VLM analysis can detect purpose mismatch, but an unbounded generate->critic->regenerate loop would be too expensive and unstable.
```

The goal is **not** to move more behavior into ControlDeck. The goal is to make Media Forge a better media-domain plugin while asking ControlDeck only for generic host primitives that any add-on can reuse.

---

## 1. Non-negotiable ownership boundary

### 1.1 Media Forge owns media semantics and workflow policy

Media Forge owns all decisions that would disappear if Media Forge did not exist:

```text
asset purpose / role
image/video/3D-specific constraints
Creative Director instructions
prompt compilation
aspect-ratio / canvas intent
safe-area intent
reference roles
consistency groups
candidate generation
purpose-aware visual evaluation
bounded creative refinement
asset grouping / placement manifest semantics
media-specific provenance
model capability routing inside Media Forge
```

Examples:

```text
"game title background should be landscape"
"leave visual room for UI in the upper area"
"these three sprites must depict the same character"
"this candidate is compositionally unsuitable for a title screen"
```

These must **not** become ControlDeck core logic.

### 1.2 ControlDeck owns generic host primitives

ControlDeck owns only behavior that remains useful when Media Forge is absent:

```text
add-on lifecycle / capability authorization
current-project resolution
project sandbox / traversal prevention
opaque input/output grants
generic file commit primitives
generic structured grant errors
Jobs / progress / audit
AI runtime selection and lifecycle
text.generate / vision.analyze
AI explicit release
Resource Broker / GPU admission
agent MCP projection
embedded-view security boundary
```

Examples:

```text
"create or authorize a project-relative output directory"
"this grant expired"
"commit these validated bytes inside this grant"
"the add-on's AI turn ended"
"this GPU request must wait"
```

ControlDeck must not know `keyart`, `sprite`, `FLUX`, `M5`, `Media Forge composition`, or any Media-specific role.

### 1.3 Boundary test

For every proposed ControlDeck change ask:

> Would this primitive still make sense for a Blender, CAD, TTS, music, archive-processing, or future unrelated add-on?

If **no**, implement it in Media Forge instead.

A second mandatory test:

> Can Media Forge be disabled or uninstalled without making this ControlDeck capability invalid?

If **no**, the proposed Host change is too Media-specific.

---

## 2. Value assessment and decisions

| Improvement | Value | Cost/risk | Decision | Priority |
|---|---:|---:|---|---|
| Purpose-level `AssetBrief` | 10/10 | medium | **Adopt** | P0 |
| Deterministic role -> aspect/canvas resolution | 10/10 | medium | **Adopt** | P0 |
| Purpose-aware post-image evaluator | 9/10 | medium | **Adopt** | P0 |
| Bounded evaluator-driven refinement | 8.5/10 | medium/high GPU cost | **Adopt, opt-in/bounded only** | P1 |
| Placement receipt with hash/type/dimensions | 8.5/10 | low | **Adopt** | P0 |
| Multi-asset placement manifest | 9/10 | medium | **Adopt** | P1 |
| Related-asset consistency group | 8.5/10 | medium | **Adopt** | P1 |
| Request output grant only immediately before placement | 9/10 | low | **Adopt** | P0 |
| Host `create_if_missing` project-output primitive | 8/10 | medium/security-sensitive | **Adopt as generic Host follow-up** | Host-P1 |
| Machine-readable grant failure codes | 8/10 | low/medium | **Adopt as generic Host follow-up** | Host-P1 |
| Generic Host multi-file transaction | 7.5/10 | medium/high | **Adopt only if all-or-nothing is required** | Host-P2 |
| Generic Add-on Contract conformance fixture | 8/10 | medium | **Adopt as ControlDeck hardening** | Host-P2 |
| Final rendered-screen VLM verification | 7/10 | higher latency/tooling | **Adopt later, optional** | P2 |
| Responsive/mobile derived variants | 6.5/10 | generation cost | **Defer until a consuming project asks** | P2 |
| Grant auto-renew / long-lived grant | 4/10 | security/lifetime complexity | **Reject** | — |
| VLM evaluation after every normal image | 3/10 | latency/VRAM churn | **Reject** | — |
| Let VLM choose exact dimensions | 2/10 | nondeterministic | **Reject** | — |
| Media-specific ControlDeck placement API | 1/10 | core coupling | **Reject** | — |
| Let coding agents remain the primary prompt engineers | 4/10 | inconsistent quality across agents | **Reject as primary path** | — |

The scores are implementation-priority judgments, not product telemetry. Re-evaluate them if real E2E evidence contradicts the assumptions.

---

## 3. P0 — Introduce a private `AssetBrief`

### 3.1 Problem

The current agent can pass an excellent prose prompt but Media Forge cannot reliably distinguish:

```text
"wide landscape composition"
```

from a hard structural requirement such as:

```text
actual output canvas must be landscape / 16:9
```

Prompt wording is not a reliable substitute for generation parameters.

### 3.2 Decision

Add a **private Media Forge orchestration object**, not a second public generation API and not a replacement for JobRequest:

```text
AssetBrief
  role                 semantic usage, e.g. hero/background/sprite/icon/texture/portrait
  target_surface       web/game/m5/general/etc. when known
  original_intent      immutable user/agent intent
  composition_intent   semantic staging
  aspect_intent        auto / square / landscape / portrait / explicit ratio
  target_dimensions    optional explicit dimensions
  safe_areas[]         semantic reserved regions for UI/text
  alpha_intent         auto / required / forbidden
  text_policy          none / deterministic_composer / visual_reference_only
  consistency_group    optional sibling group
  reference_roles[]
  hard_constraints[]
  optional_suggestions[]
```

This object is Media Forge-private unless a later additive agent schema field is proven necessary. First try to project existing agent inputs into it without breaking the frozen public contract.

### 3.2b Where the brief comes from — decision record (2026-08-24)

A proposal was raised to run incoming agent requests through the AI Director so
an LLM normalizes them into an `AssetBrief`. It is **not adopted**, for reasons
measured rather than assumed.

```text
observed on this machine (G6 resource turn measurements)
  LLM resident              31,555,141,632 bytes
  FLUX resident             18,147,024,896 bytes
  GPU total                 34,208,743,424 bytes
  -> the two cannot coexist; every AI step costs a model swap
  LLM load                  4.0 - 12.1 s
  explicit release          0.146 - 0.371 s
  FLUX load                 10.6 - 14.9 s
  -> one swap round trip is roughly 15 - 25 s
```

Putting an LLM in front of *every* request would pay that on every generation,
and would add a second AI layer beside the Director that already calls
`text.generate`.

Adopted instead, two tiers:

```text
tier 1  deterministic extraction from the existing prose intent
        closed vocabulary; zero AI calls; zero swaps
        returns nothing when unsure, so it never silently changes behavior
tier 2  when the Director is invoked anyway, fold brief refinement into that
        existing text.generate call — no extra round trip, no extra swap
```

Tier 1 is sufficient for the observed failure. Replayed against the two real
Hanabi requests, with `constraints` empty exactly as they were sent:

```text
background   1024x576  16:9  source=brief.aspect_intent   (was 1024x1024)
fireworks    1024x576  16:9  source=role_default          (was 1024x1024)
explicit 1:1 1024x1024       source=request.constraints
```

Tier 2 is deferred to A3 and is not required to fix the reported defect.

### 3.3 Priority

```text
explicit user dimensions / ratio
  > explicit project requirement
  > deterministic domain/profile rule
  > accepted reference facts
  > AssetBrief role defaults
  > Director inference
  > model-native default
```

AI must never override an explicit size, ratio, alpha, or deterministic profile requirement.

---

## 4. P0 — Deterministic layout and output geometry resolver

### 4.1 Core rule

Words such as `wide`, `landscape`, `portrait`, `banner`, `icon`, `sprite`, and `title background` may inform the brief, but **actual dimensions/aspect ratio must be resolved structurally before generation**.

Add a deterministic resolver between Director planning and the existing compiler/router:

```text
AssetBrief
  -> Purpose/Layout Resolver
  -> resolved canvas/aspect/alpha/safe-area intent
  -> existing CreativeSpec / JobRequest projection
  -> existing router / worker
```

Do not ask the VLM or diffusion model to make a square canvas "look wide".

### 4.2 Role defaults are fallbacks, not hardcoded universal truth

Example defaults may exist privately:

```text
background / hero    prefer landscape when project context gives no stronger rule
icon                 prefer square
portrait             prefer portrait
sprite               derive from profile/project constraints
M5 companion         bundled deterministic profile is authoritative
```

Do not encode one universal 16:9 rule for every game or Web project.

### 4.3 Safe areas

Safe areas are **composition intent**, not a claim of pixel-perfect object detection.

Media Forge may instruct the Director/worker to reserve an upper/lower/side region, and the evaluator may semantically flag obvious intrusion. Do not claim deterministic proof that a subject occupies less than an exact percentage unless a deterministic detector actually provides that proof.

---

## 5. P0 — Agent-facing behavior: ask for purpose, not prompt craftsmanship

### 5.1 Desired agent request

The normal coding-agent request should be closer to:

```text
purpose: game title background
subject: Japanese summer fireworks festival
layout: landscape; reserve upper area for title UI
consistency: match the title key art
text in generated image: none
```

than to a provider-optimized paragraph containing model-specific prompt tricks.

### 5.2 Media Forge responsibility

Media Forge Creative Director converts purpose-level input into:

```text
AssetBrief
  + PromptPlan
  + CreativeSpec
  + model-family private prompt projection
```

The coding agent should not need to know the preferred wording for FLUX, Qwen Image, SDXL, or a future model.

### 5.3 Tool guidance

Update agent-tool descriptions/instructions additively so coding agents are told:

```text
- describe purpose and hard visual constraints;
- do not name a provider/model unless the user explicitly requested manual model selection;
- use model_policy=auto by default;
- use quality/fast/low_vram only when the user or task actually requires that tradeoff;
- request project output grant immediately before placement, not before a long generation step;
- inspect/evaluate when the task asks for visual suitability or multiple candidates;
- after placement, update code references and run build/test.
```

Do not add an OpenCode-specific fork. The same tool semantics must work for Codex and future agent harnesses.

---

## 6. P0/P1 — Purpose-aware generated-image evaluation

### 6.1 Current evaluator remains the base

Do not create another reviewer stack. Extend the canonical `EvaluationResult` and existing Unified Evaluator behavior.

Evaluation order stays:

```text
deterministic validation
  -> purpose-relevant deterministic checks
  -> optional VLM evaluation
  -> advisory rank / structured issues
  -> optional bounded refinement
```

### 6.2 Evaluate suitability, not generic beauty

When an `AssetBrief` exists, evaluation must compare the candidate against the requested use.

Examples:

```text
title background
  composition / safe-area suitability / distraction level / palette / visual integrity

character sprite
  subject identity / pose/action / alpha/background expectations / silhouette readability

icon
  recognizability at target size / composition / visual integrity
```

A visually attractive square image must still be marked unsuitable if the required output canvas is landscape. Exact dimension mismatch is deterministic and should fail or be corrected before any VLM call.

### 6.3 VLM result becomes structured feedback

Do not append free-form critique directly to the next prompt. Normalize it into bounded deltas such as:

```text
EvaluationDelta
  dimension
  issue
  severity
  requested_change
  preserve[]
```

Then project only accepted/relevant deltas through the existing Creative Director/compiler path.

This reduces prompt drift and preserves explicit user constraints.

### 6.4 Bounded refinement policy

Default single-image generation:

```text
0 mandatory VLM calls
0 automatic retries
```

Explicit compare/quality/agent suitability mode:

```text
<= 1 evaluation round by default
<= existing max_regeneration_attempts budget
never unbounded
```

Keep every generated candidate immutable. A refinement creates a child asset with lineage; it never silently overwrites the original.

### 6.5 Resource-turn reuse

Any evaluator-driven refinement must reuse the G6 resource-turn architecture:

```text
generate
  -> release generation lease
  -> review via Host vision.analyze
  -> if retry is authorized:
       finish AI turn / release as required
       -> reacquire Broker lease
       -> generate child
```

No Media Forge direct LLM process control.

---

## 7. P1 — Related assets and consistency groups

A coding task often needs a set rather than one image:

```text
title key art
background
player portrait
icon
UI illustration
```

Add a private `consistency_group` / shared creative anchor so related assets can reuse:

```text
accepted Director plan fragments
style cues
palette intent
character/reference identities
reference-analysis cache
project/domain context
```

Do not force all sibling assets to share the same ratio or composition. Consistency is about the dimensions explicitly shared by the brief, not making every image visually identical.

When multiple candidates are intentionally compared, group-level evaluation may check style/palette/identity consistency, but it remains optional and bounded.

---

## 8. P0/P1 — Placement manifest and receipt

### 8.1 Current contract

Current `media.pack` safely commits one existing immutable Media Forge asset to an opaque Host output grant. Keep this path compatible.

### 8.2 Additive multi-asset semantic layer

Introduce a Media Forge-private `PlacementManifest` and, if needed, an additive public `items[]` form while preserving the existing singular request:

```text
PlacementManifest
  output_grant_id
  items[]
    asset_id
    filename
    role
    expected_sha256
    expected_media_type
  overwrite_policy
```

Rules:

```text
- asset IDs only; never source paths;
- safe relative filenames only;
- reject duplicate destination names before Host writes;
- preflight every Media Forge asset before first write;
- preserve existing single-asset media.pack input forever;
- do not leak project path in request/response/provenance.
```

### 8.3 Do not overclaim atomicity

Current Host behavior atomically commits **one file**. Media Forge must not label an N-file batch as all-or-nothing unless ControlDeck exposes a generic transaction primitive and that exact path is tested.

Until then:

```text
logical batch = allowed
per-file atomic commit = allowed
all-or-nothing batch claim = forbidden
```

Return per-item outcomes if a later item fails.

### 8.4 Placement receipt

Successful placement should return enough non-path evidence that an agent normally does not need `ls` / `file` just to discover whether Media Forge placed the expected bytes:

```text
PlacementReceipt
  committed
  host_asset_id
  filename
  source_asset_id
  sha256
  size_bytes
  media_type
  width / height when image
  warnings[]
```

For a batch, return one receipt per item plus overall state.

Shell verification may still be used by the coding agent as independent final project verification; it should no longer be required because the Media Forge response is ambiguous.

---

## 9. P0 — Grant timing and failure recovery

### 9.1 Request the grant late

The normal agent flow becomes:

```text
analyze project
  -> generate assets
  -> inspect/evaluate/select
  -> decide exact destination filenames
  -> request project output grant immediately before placement
  -> media.pack
  -> update code
  -> build/test
```

Do not acquire a short-lived output grant before a 30-120 second generation operation unless there is a specific reason.

### 9.2 Expired grants

Do **not** add long-lived or auto-renewed grants just to hide timing mistakes.

On an explicit machine-readable `grant_expired` error:

```text
agent reacquires a new scoped grant
  -> retries an idempotent placement once
  -> otherwise surfaces the failure
```

Media Forge must not inspect ControlDeck grant files, signing material, or raw filesystem state to determine why the grant failed.

---

## 10. ControlDeck follow-ups — separate repository, generic only

Nothing in this section should be implemented inside Media Forge as a workaround.

### H1. Project output grant with explicit directory creation

Candidate generic extension:

```text
project_output_grant(
  relative_directory,
  create_if_missing=false
)
```

Requirements:

```text
- default false for compatibility and least surprise;
- current project resolved by Host;
- path must be relative, normalized, traversal-free, inside the project;
- creation is audited;
- no Media-specific vocabulary;
- works for any eligible add-on;
- response still exposes only opaque grant/non-path metadata.
```

This prevents an add-on from becoming a filesystem authority while avoiding a separate shell `mkdir` round trip when creation is intentionally requested.

### H2. Machine-readable grant error taxonomy

Candidate generic reason codes:

```text
grant_expired
directory_not_found
permission_denied
project_unavailable
invalid_relative_directory
grant_scope_mismatch
```

Human text may change; agent recovery must key on stable reason codes.

### H3. Generic multi-file output transaction — only if justified

Add only after a real use case proves that partial multi-file placement is unacceptable.

Possible Host semantic:

```text
validate N writes under one scoped grant
  -> stage all
  -> verify size/hash/policy
  -> commit all or none
```

The API must be useful for unrelated add-ons. Do not call it `media.pack` or teach Host about images.

### H4. Add-on Contract conformance fixture

High-value Host hardening for future plugins:

```text
fake/reference add-on
  -> lifecycle
  -> health states
  -> contribution enable/disable
  -> scoped token
  -> input/output grants
  -> AI capability
  -> resource lease
  -> MCP projection
  -> opaque iframe rules
```

The purpose is to prove ControlDeck's Add-on Platform without Media Forge installed. Media Forge should be one consumer, not the contract reference implementation baked into core.

### Host non-goals

Never add:

```text
mediaforge_create_directory
mediaforge_prepare_flux
mediaforge_release_llm
keyart-specific output API
image aspect-ratio policy in ControlDeck
Media Forge model/provider routing in ControlDeck
```

---

## 11. Optional P2 — Final integration visual verification

Asset quality in isolation is not always enough. A good background can become poor after the consuming app crops it, overlays a title, or renders it on mobile.

A later agent workflow may optionally:

```text
place asset
  -> update consuming code
  -> render/run project
  -> capture final screen through the agent/browser tooling
  -> import/pass the screenshot as a bounded Media Forge asset/reference
  -> evaluate against the same AssetBrief
  -> propose a bounded correction if explicitly enabled
```

Ownership remains:

```text
coding agent      runs/builds/renders the project
Media Forge       evaluates visual suitability
ControlDeck       supplies generic AI/resources/grants
```

Do not make this a requirement for every asset or every non-visual project. Build/test success is independent from subjective VLM approval.

---

## 12. Optional P2 — Responsive and target-specific variants

Potential later extension:

```text
one semantic AssetBrief
  -> desktop target
  -> mobile target
  -> thumbnail/icon target
```

Prefer deterministic crop/compose from an accepted master when it preserves intent. Regenerate only when a crop cannot satisfy composition/safe-area requirements.

Do not generate three variants by default merely because a Web project exists. This becomes valuable only when a consuming project actually declares multiple target surfaces.

---

## 13. Implementation slices

Implement as small vertical slices. Do not mix the ControlDeck Host changes into the Media Forge feature PRs.

### A1 — AssetBrief + purpose/layout resolver

Media Forge only.

```text
- private AssetBrief schema/model
- role/aspect/alpha/safe-area normalization
- explicit-user-constraint precedence
- projection into existing CreativeSpec / JobRequest
- provenance snapshot
- no new provider/model route
```

Acceptance:

```text
"wide landscape game title background" resolves to an actual landscape canvas
explicit 1024x1024 still wins over inferred landscape
M5 deterministic profile remains authoritative
prompt-only path performs zero pre-generation vision calls
```

### A2 — Agent contract guidance

Media Forge only, additive/non-breaking.

```text
- improve tool descriptions/examples around purpose-level intent
- model_policy=auto default guidance
- output grant requested late
- inspect/evaluate/place/update-code/build-test workflow guidance
```

Do not create separate OpenCode/Codex schemas.

### A3 — Purpose-aware evaluator + bounded refinement

Media Forge only.

```text
- reuse canonical EvaluationResult
- add brief-relevant evaluation rubric/projection
- structured EvaluationDelta
- original candidate immutable
- zero retry default
- bounded opt-in retry using existing QA budget
- resource-turn reuse
```

### A4 — Placement manifest + receipt

Media Forge only unless Host prerequisite is explicitly needed.

```text
- preserve single-item media.pack
- private PlacementManifest
- optional additive multi-item request only if needed
- preflight all items
- per-item receipts with hash/type/dimensions
- never claim all-or-nothing without Host transaction support
```

### H1/H2 — Generic Host output-grant usability

ControlDeck **separate PR** only if still required after A1-A4 evidence.

```text
- create_if_missing
- stable reason codes
```

No Media Forge code or names in the Host implementation.

### H3/H4 — Host transaction / contract fixture

Separate follow-up; do not block A1-A4 unless a concrete acceptance case requires it.

### A5 — Real OpenCode/Codex acceptance

Use an actual small project and the installed ControlDeck/Media Forge path.

Required path:

```text
project analysis
  -> purpose-level asset request
  -> generated candidate
  -> inspect / optional evaluator
  -> late project output grant
  -> placement receipt
  -> code reference update
  -> build
  -> test
```

For a visual app, also inspect the running/rendered result manually or through the existing browser fixture. Optional VLM final-screen evaluation is P2 and must be labeled if not implemented.

---

## 14. Regression and acceptance gates

### Media Forge automated tests

```text
AssetBrief
  explicit dimensions > role default > Director inference
  invalid ratio/dimensions fail before GPU admission
  no provider/model/port fields

Agent path
  default auto policy remains valid
  legacy media.generate/media.pack requests remain valid
  raw filesystem paths remain rejected

Evaluator
  deterministic failure cannot be overridden by VLM
  single normal generation has no mandatory VLM call
  retry budget 0 creates no child retry
  retry budget N creates at most N additional candidates
  each retry preserves original hard constraints
  original asset is never overwritten

Placement
  duplicate filenames fail before write
  bad asset/hash/type fails before write
  receipts match source immutable asset hash/type/dimensions
  multi-item response does not claim atomic batch semantics without Host evidence
```

### Real installed acceptance

Record actual values, not assumptions:

```text
ControlDeck commit/version
Media Forge exact head/release
OpenCode or Codex version
selected output ratio and actual pixel dimensions
Director text.generate count
pre-generation vision.analyze count
post-generation evaluator call count
retry count
AI release / Broker lifecycle
placement receipt hashes
final Broker active/waiting counts
project build/test outcome
browser/runtime screenshot outcome where applicable
```

A quality improvement is not COMPLETE merely because the VLM says it is better. Preserve the image(s) or screenshot evidence needed for human inspection.

---

## 15. Completion definition

This hardening slice is complete when:

1. Coding agents can request assets primarily by **purpose and constraints**, without needing model-specific prompt craftsmanship.
2. Output aspect/canvas is structural; a landscape requirement cannot silently remain 1:1 unless an explicit stronger constraint says so.
3. Generated-image VLM analysis can explain purpose mismatch and drive an **explicitly bounded** refinement path without becoming mandatory for normal generation.
4. Related assets can share intentional creative anchors without forcing identical dimensions/compositions.
5. Project output grants are requested late enough that normal generation does not routinely expire them.
6. Placement returns a useful non-path receipt so an agent can verify exact committed content without scraping internal Host files.
7. Multi-asset placement is supported semantically without falsely claiming all-or-nothing atomicity.
8. Any ControlDeck changes are generic Add-on Platform primitives that still make sense with Media Forge uninstalled.
9. Legacy public agent requests, JobRequest, schemas, and single-item `media.pack` remain compatible.
10. Real installed OpenCode/Codex E2E reaches **generate -> inspect/evaluate -> place -> code update -> build/test** and records NOT TESTED items honestly.

---

## 16. Instructions for Claude / Codex implementing this plan

Before implementation:

```text
1. Read AGENTS.md and all source-of-truth docs listed at the top.
2. Refresh main and open PRs; do not implement against stale commit IDs in this document.
3. Finish/record any still-open G5/G6 real-machine acceptance gate before claiming a regression baseline.
4. Inspect current agent schemas, Creative Director, evaluator, media.pack, output-grant bridge, and tests before changing contracts.
```

During implementation:

```text
- implement A1-A4 in ControlDeckMediaForge;
- keep ControlDeck read-only unless working on a separately scoped H-series Host PR;
- never add Media-specific Host code;
- prefer private/internal orchestration models before adding public fields;
- if a public field is necessary, make it additive and preserve all legacy forms;
- reuse CreativeSpec, PromptPlan, EvaluationResult, C3/C4, existing Jobs, Broker and media.pack rather than creating parallel stacks;
- no unbounded AI loop;
- no pre-generation VLM for a prompt-only first image;
- never mark unrun real-machine gates as passed.
```

After each slice:

```text
focused tests
  -> full ./mf.sh test
  -> real installed acceptance when required
  -> docs/implementation-status.md
  -> docs/implementation/ux1-handoff.md
  -> PR/review/merge
```

Do not fold H1-H4 into a Media Forge PR merely because doing so is convenient. The repository boundary is part of the acceptance criteria.
