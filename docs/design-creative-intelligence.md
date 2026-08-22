# Creative Intelligence v2 — Creative Director / Reference Intelligence / Evaluator

Status: unified design baseline  
Date: 2026-08-22  
Target: ControlDeckMediaForge

Related sources of truth:

- `docs/base-plan.md`
- `docs/controldeck-integration-plan.md`
- `docs/design-workspace-ux.md`
- `docs/design-model-scene-ux.md`
- `docs/implementation/ux2-model-scene.md`
- `docs/implementation/creative-intelligence.md`
- ControlDeck `docs/design-addon-platform-v2.md`
- ControlDeck generic Add-on AI Runtime (`ai.inference`)

This document replaces the earlier Creative Intelligence design baseline for **future Creative Intelligence work**. It does not replace the already-merged UX2 M0–C5 implementation, Create/Library/Activity/Settings, the frozen public JobRequest contract, Character/Style profiles, C3 batches, C4 Composer, or C5 candidate ranking.

---

## 1. Why this revision exists

The previous plan correctly separated text planning from image understanding, but its diagrams made `vision.analyze` look too central to the generation path. That is misleading for a brand-new text-to-image request because **there is no image to analyze before the first image exists**.

The revised design makes three distinct jobs explicit:

1. **Creative Director** — text intent -> structured creative direction. Uses ControlDeck `text.generate`.
2. **Reference Intelligence** — an existing/reference image -> deterministic facts + semantic visual analysis. Uses local deterministic code and, only when an image exists, ControlDeck `vision.analyze`.
3. **Evaluator** — generated/existing image(s) -> advisory semantic comparison/ranking. Uses deterministic validators first and, only after image bytes exist, ControlDeck `vision.analyze`.

The primary path for a new image is therefore **text-first, not vision-first**.

---

## 2. Current implementation baseline (main at `8f61d05`)

Already merged and reusable:

- UX2 M0–M2 model ownership/download/Settings model management.
- C0 deterministic `CreativeSpec` compiler.
- C1 current Create controls for Domain / Scene / Pose / Composition / Camera / Variation.
- C2 Character/Style and role-aware references.
- C3 durable intentional child batches.
- C4 deterministic multi-cut Composer.
- C5 six-axis advisory candidate evaluator/ranking and R9700 evidence.
- v0.3.0 release of the creative direction workflow (#48).
- Creative Intelligence A0 (#46): `HostAIGateway`, `PromptPlan`, `SubjectSpec`, `ActionStateSpec`, `VisualFacts`, `VisualAnalysis`, `EvaluationResult`, `PromptPlanner` foundation.
- protected server-owned PromptPlan field fix (#49), with the full local gate recorded as 269 passed.

Important remaining facts:

- `addon.json` does **not yet** request `ai.inference`.
- production `semantic_review.py` still calls Ollama directly.
- production `evaluator.py` still calls Ollama directly.
- `config.py` still contains reviewer URL/model defaults.
- `HostAIGateway` / `PromptPlanner` are foundation code; they are not yet connected to the production Create flow.
- `VisualFacts` / `VisualAnalysis` are data models only; the analyzers/cache are not yet implemented.
- open video-model catalog work is a separate concern and must not be mixed into this Creative Intelligence migration.

---

## 3. Non-negotiable ControlDeck boundary

Media Forge never chooses Ollama, llama.cpp, LM Studio, a port, a model alias, or provider-specific request syntax.

Media Forge may ask ControlDeck only for generic capabilities:

```text
text.generate
vision.analyze
```

through the scoped Add-on Runtime capability:

```text
ai.inference
```

ControlDeck owns:

- runtime/provider selection;
- model selection;
- multimodal protocol conversion;
- model lifecycle;
- GPU/KV admission and Broker policy;
- provider-specific errors and secrets.

Media Forge owns:

- creative task instructions and strict result schemas;
- user constraints and provenance;
- deterministic image facts;
- reference-role policy;
- generation/evaluation product behavior;
- bounded retry/ranking decisions.

No global gateway API key, ControlDeck session cookie, provider URL, model ID, or filesystem path is copied into the Media Forge AI contract.

---

## 4. Capability matrix: when text and vision are actually used

| User operation | `text.generate` | deterministic image analysis | `vision.analyze` before generation | `vision.analyze` after generation |
|---|---|---|---|---|
| New image, text only | Creative Director (Auto/Art Direct) | no | **no** | optional evaluator only |
| New image + reference(s) | Creative Director | yes, once per new reference hash | yes, reference semantics only | optional evaluator |
| Existing image edit | optional Director for semantic instruction | existing validators/mask geometry | optional if semantic understanding is useful | optional evaluator |
| C3 “different action/pose” batch | one Director request for bounded child deltas | reuse cached reference facts | reuse cached reference analysis | optional group ranking |
| C4 poster / character sheet | Director may create shot briefs; Composer remains deterministic | reuse | only for referenced source images | optional final/child evaluation |
| Future video planning | Director -> future MotionSpec | frame/reference facts when present | only when a frame/reference exists | optional video/frame evaluator later |

### Hard rule

`vision.analyze` is **never a prerequisite for prompt-only first-image generation**. The ControlDeck Runtime already requires an actual image for `vision.analyze`; Media Forge should preserve that semantic distinction instead of trying to use a VLM as a text-only Director.

---

## 5. New-image generation is a first-class path

### 5.1 Simple default path

```text
user natural-language intent
        |
        v
Creative Director (ControlDeck text.generate, when available)
        |
        v
PromptPlan
  + SubjectSpec
  + ActionStateSpec
  + scene / composition / camera
  + hard user constraints
        |
        v
compatibility projection + existing CreativeCompiler
        |
        v
existing JobRequest / Broker / image worker
        |
        v
candidate asset
        |
        +--> deterministic validation (always)
        '\--> vision.analyze evaluator (optional, now an image exists)
```

This is the path that solves the limited-pose problem. The Director describes arbitrary **action/state/orientation/gesture/gaze/part relations** instead of being restricted to a small list of Pose presets.

### 5.2 Director modes

Keep the existing internal modes to minimize code churn, but simplify their user-facing meaning:

```text
そのまま        -> internal `original`
自動            -> internal `refine` (Simple default when text.generate is available)
演出強め        -> internal `art_direct`
```

`自動` is conservative. It may structure and clarify missing visible direction, but must not silently invent new hard facts. `演出強め` may propose camera/lighting/staging, but new ideas remain explicitly AI suggestions.

### 5.3 Fail-soft behavior

Creative Director is valuable but not a hard dependency:

- if `text.generate` is unavailable, the current prompt-only generation path remains valid;
- if the Director fails or returns invalid JSON, preserve the original input and allow direct generation;
- show a compact reason instead of failing the image job;
- never fall back to a guessed local provider port.

The user can always choose `そのまま` to bypass the Director.

---

## 6. Pose presets are retained but demoted

The current pose catalog is intentionally small. Expanding it into dozens or hundreds of fixed poses would create a maintenance problem and still fail for robots, vehicles, creatures, products, architecture, and uncommon human actions.

Decision:

- **Do not expand Pose presets as the primary solution.**
- Keep the current presets as fast shortcuts, regression fixtures, deterministic variation anchors, and Advanced/manual controls.
- The canonical semantic representation becomes `ActionStateSpec`.
- Simple UI stops treating Pose as a required creative vocabulary.
- Advanced keeps exact Pose/custom controls.

The current compiler already supports `PoseSpec(preset="custom", details=...)`, and every current Scene template accepts `custom`. Therefore the first implementation can reuse the existing compiler by projecting Director action semantics into `custom` pose details without breaking the public JobRequest.

For non-human subjects, `pose` is only a compatibility projection. Provenance should retain the canonical `ActionStateSpec` so semantics are not lost.

---

## 7. Creative Director responsibilities

Input:

- immutable `original_intent`;
- current user-selected Domain/Character/Style if any;
- explicit Advanced overrides if any;
- cached reference-analysis summaries when references exist;
- requested variation axis / C4 shot context when applicable.

Output:

```text
PromptPlan
  original_intent      Media Forge owned, never AI owned
  mode
  subject              SubjectSpec
  primary_action       ActionStateSpec
  scene
  composition
  camera
  style_cues[]
  details[]
  hard_constraints[]   extracted from explicit user facts only
  optional_suggestions[]
  assumptions[]
```

Priority order:

```text
explicit user override / user facts
    > deterministic observed facts
    > accepted reference semantics
    > Director inference
    > optional Director suggestion
```

The Director must not emit model, sampler, scheduler, provider, port, or engine vocabulary.

### Constraint provenance

The current A0 schema stores strings. During Director production integration, record the source for accepted constraints in the private plan/provenance layer. Do not make an AI-invented suggestion indistinguishable from a user constraint.

---

## 8. Intentional variation uses the Director, not a larger preset table

For C3 requests such as “different action” or “different pose”:

```text
parent PromptPlan
        |
        v
one bounded text.generate request
        |
        v
2–4 semantic child deltas
        |
        v
existing C3 child CreativeSpecs / normal child Jobs
```

Example child action deltas for one character:

1. holding a damaged terminal with both hands and inspecting it;
2. kneeling on one knee while repairing exposed wiring;
3. lifting the terminal toward eye level and checking an error display;
4. placing it on the ground and using a tool with the right hand.

Rules:

- one Director call for the bounded batch, not one call per child;
- vary only the requested axis;
- preserve identity/style/scene unless the user requested those to vary;
- each child remains a normal C3 Job and goes through ordinary Broker admission;
- no new batch storage system.

---

## 9. C4 Composer stays deterministic

The Director may plan **shot briefs** for multi-cut work, but layout/text composition remains the existing deterministic C4 Composer.

```text
Director: what each shot should depict
C3/normal child jobs: generate the shots
Composer: exact regions, crop, frames, title/caption, spacing, final dimensions
```

Do not ask diffusion or a VLM to place exact titles, logos, captions, or UI text when deterministic composition already solves that job.

---

## 10. Reference Intelligence is conditional on an existing image

Reference Intelligence runs only when there is an imported/reference/generated image to inspect.

```text
asset
  -> bounded decode
  -> deterministic VisualFacts
  -> cached by asset SHA-256 + analyzer version
  -> bounded review representation
  -> ControlDeck vision.analyze
  -> strict VisualAnalysis schema
  -> merge deterministic facts + semantic observations
```

### 10.1 Deterministic facts

Use Pillow initially; do not add ML/OpenCV merely for the first implementation.

```text
width / height / aspect_ratio
has_alpha / opaque_fraction
dominant colors + coverage
accent colors
mean luminance
mean saturation
hash / known mask geometry / unchanged-pixel constraints where relevant
```

Pixels win over VLM guesses for measurable facts.

### 10.2 Semantic observations

`vision.analyze` handles:

- subject/category/count;
- action/state/orientation;
- semantic composition;
- clothing/props/environment;
- style cues;
- visible text regions as semantic hints, not exact OCR truth;
- confidence and observed-vs-inferred separation.

### 10.3 Reference roles

Reuse the current roles and reference collections:

```text
identity / style / pose / composition / clothing / palette / prop / environment
```

Analysis proposes roles; it does not silently rewrite profiles. A user can accept all, accept selected dimensions, or edit them.

---

## 11. Evaluator is post-image and advisory

A VLM evaluator cannot judge a candidate that does not yet exist. It runs only after a generated/existing image is available.

Before CI-4, the C5 evaluator and older binary semantic reviewer overlapped.
They now use one product-level evaluator path:

```text
deterministic validators (authoritative)
        |
        v
Unified EvaluationResult
  intent
  subject_identity
  action_state
  palette
  composition
  style
  props_clothing
  visual_integrity
        |
        +-> rank/show alternatives
        +-> explain mismatches
        +-> Activity/provenance
        '-> optional bounded retry using existing QA budget
```

A palette-only reference must not penalize a different pose. Score only dimensions requested by user constraints/reference roles.

Default generation should not require a serial VLM judge call. Evaluation is most valuable for explicit compare/rank/quality actions, multi-candidate batches, and bounded quality modes.

---

## 12. Critical review: accepted and rejected counterarguments

### Accepted: fixed presets are faster and deterministic

Keep them as shortcuts/Advanced/fallback. Do not delete them.

### Accepted: an LLM cannot guarantee exact joint geometry

The Director improves **semantic pose/action variety**, not physical control fidelity. Exact limb placement may still require a pose/reference/control adapter when the selected image model supports one. Do not promise arbitrary exact skeleton reproduction from text alone.

### Accepted: mandatory AI planning would add latency and a new failure dependency

Director Auto is fail-soft, `そのまま` remains available, and prompt-only generation stays supported.

### Accepted: VLM calls can cause GPU/runtime churn

Reference analysis is cached; candidate evaluation is not mandatory on every generation; ControlDeck owns runtime/Broker policy; repeated C3/C4 work reuses analysis instead of re-running it.

### Accepted: generate -> VLM critique -> regenerate can improve quality but is expensive

Do **not** make a two-pass autonomous quality loop the default. If introduced later, it must be an explicit Quality mode with a strict retry budget and measured R9700 cost.

### Rejected: use `vision.analyze` as the Director even for text-only generation

The capability semantically requires image input and would blur responsibilities. Use `text.generate` for creative planning.

### Rejected: add hundreds of Pose presets

This scales poorly, remains person-centric, and duplicates what structured free-form ActionState already provides.

### Rejected: add a Media-specific ControlDeck “creative.direct” endpoint now

The generic `text.generate` / `vision.analyze` boundary is sufficient for the current design. If routing quality later proves insufficient, evolve ControlDeck with a **generic** task/profile mechanism rather than a Media-specific provider route.

### Rejected: silently use Ollama/llama.cpp when ControlDeck AI is unavailable

No provider-specific fallback exists in Media Forge production code after migration.

---

## 13. Simple / Advanced UX after consolidation

### Simple

Keep the current one-screen Create. No new top-level navigation and no wizard.

Target shape:

```text
何を作りますか？
[ natural-language textarea ]

演出 [自動 ▾]      # そのまま / 自動 / 演出強め

Character / Style / references (existing UI)
見せ方 [Auto / Character / Product / Game / Poster / ...]
変化   [Auto / 別の動き / 別の構図 / 別のシーン]

[作る]
```

After Director planning, reuse the existing Create surface for a compact “理解した内容” disclosure. Do not create another editor screen.

The current Pose selector is demoted/conditional in Simple. It is not deleted until real-use evidence confirms the Director path covers the normal case.

### Advanced

Retain/edit:

- canonical Action/State/Gesture/Gaze/Orientation;
- compatibility Pose/custom detail;
- Scene/Composition/Camera;
- exact reference roles/strengths;
- original intent, inferred fields, optional suggestions, confidence;
- model/seed/manual controls already present.

Advanced must remain usable without AI.

---

## 14. Performance and caching policy

One normal image must not require a chain of serial AI calls.

```text
new prompt, no refs:
  <= 1 text Director request before generation
  0 vision requests before generation

new reference asset:
  deterministic facts once
  <= 1 cached vision analysis per asset hash/analyzer version

C3 batch:
  <= 1 Director request for all semantic child deltas
  reuse reference analysis

Evaluator:
  only when explicitly useful; batch candidates where bounded and supported
```

Model-family prompt recipes are private, versioned projections owned by Media
Forge adapters. They may constrain fields, ordering, reference labels, timing,
and verbatim text before calling the existing `text.generate` capability. They
must not execute arbitrary upstream skills or send repository/path/command
metadata to ControlDeck, and they do not create a public model-specific API.
Prompt-only recipes require no pre-generation vision request.

Cache accepted Director plans by a hash of the immutable intent + relevant accepted controls + Director schema/version. Never reuse across changed user constraints.

---

## 15. Failure and degradation behavior

```text
ControlDeck ai.inference not granted
  -> normal generation/edit remains available
  -> Director/semantic reference analysis/evaluator unavailable

text.generate unavailable
  -> use current prompt-only path
  -> existing presets/Advanced/manual controls remain usable

vision.analyze unavailable
  -> new text-only generation is unaffected
  -> deterministic reference facts still work
  -> semantic reference analysis/evaluation unavailable

invalid Director JSON
  -> preserve original input; reject the plan; optionally generate raw prompt

invalid VLM JSON
  -> preserve asset/reference; do not promote uncertain result to a hard constraint
```

---

## 16. Migration / de-duplication target

The revised implementation should converge toward:

```text
HostAIGateway
  |- CreativeDirector       text.generate
  |- ReferenceAnalyzer      deterministic + vision.analyze
  '- CreativeEvaluator      deterministic first + vision.analyze
```

Retire production provider-specific transport from:

```text
semantic_review.py
config.py reviewer URL/model settings
evaluator.py Ollama client
```

Do not create a second asset store, second generation route, second batch engine, second Composer, or second evaluator loop.

---

## 17. Future video compatibility

Do not mix the current video-catalog PR into this implementation. The design remains future-compatible:

- Director can later produce `MotionSpec` using `text.generate`.
- `vision.analyze` is used only when a start/end/reference frame exists.
- model routing remains capability-driven.
- existing Model Management remains shared.
- video runtime adoption still requires its own R9700/ROCm evidence.

---

## 18. Definition of success

Creative Intelligence is successful when all of the following are true:

1. A user can describe an uncommon human/non-human action in natural language without finding a matching Pose preset.
2. New text-only generation uses a Director plan without any pre-generation `vision.analyze` call.
3. Prompt-only generation still works if ControlDeck AI assistance is unavailable.
4. Reference images are analyzed once/cached and may contribute only the roles the user wants.
5. User facts remain distinguishable from AI inference/suggestions.
6. Existing C3/C4/C5 infrastructure is reused rather than replaced.
7. All Media Forge production AI assistance passes through ControlDeck `ai.inference`; no provider/model/port decision remains in Media Forge.
8. Evaluator calls are post-image, advisory by default, and bounded.
9. Installed-host/R9700 evidence confirms runtime switching does not require Media Forge configuration changes.
