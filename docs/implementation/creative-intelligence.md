# Creative Intelligence v2 implementation plan

Design: `docs/design-creative-intelligence.md`  
Existing UX base: `docs/design-workspace-ux.md`  
Existing creative base: `docs/implementation/ux2-model-scene.md`

This plan supersedes the earlier future A1–A7 sequencing. A0 is already merged and remains the foundation. The new plan consolidates overlapping work around the **Creative Director**, conditional **Reference Intelligence**, and one **Unified Evaluator** while reusing UX2 C0–C5.

---

## 0. Current baseline and scope

Repository baseline when this plan was rewritten:

```text
main                 8f61d054d09735381a6c5224546b01c64fb1da26
v0.3.0               merged/released through PR #48
Creative Intel A0    PR #46 merged
A0 protected fields PR #49 merged
local full gate       269 passed / 24.58 s (recorded by #49)
open unrelated work   PR #50 video candidate catalog
```

Do not mix this plan into the video-catalog PR. Branch each Creative Intelligence slice from the then-current `main` after checking open PRs.

### Already implemented and reused

```text
backend/mediaforge/creative.py             CreativeSpec + deterministic compiler
backend/mediaforge/creative_batches.py     bounded C3 child jobs
backend/mediaforge/composer.py             C4 deterministic Composer
backend/mediaforge/evaluator.py            C5 six-axis ranking foundation
backend/mediaforge/profiles.py             Character/Style profiles
backend/mediaforge/jobs.py                 deterministic QA + bounded retry budget
backend/mediaforge/creative_intelligence.py
  Host-facing PromptPlan / SubjectSpec / ActionStateSpec / Visual* / Evaluation* models
backend/mediaforge/host/ai.py               provider-neutral HostAIGateway
frontend/index.html + app.js                existing Create/Result/Library/Activity/Settings
```

### Still provider-specific / incomplete

```text
addon.json
  does not yet request ai.inference

backend/mediaforge/semantic_review.py
  direct Ollama /api/tags + /api/chat

backend/mediaforge/evaluator.py
  direct Ollama /api/tags + /api/chat

backend/mediaforge/config.py
  reviewer URL/model defaults

HostAIGateway / PromptPlanner
  foundation only; production Create flow not connected

VisualFacts / VisualAnalysis
  models only; analyzer/cache absent
```

---

## 1. Hard boundaries

```text
B1  No Ollama/llama.cpp/provider/model/port branch in Media Forge production AI assistance.
B2  Text-only creative planning uses ControlDeck `text.generate`.
B3  `vision.analyze` is used only when actual image bytes already exist.
B4  A prompt-only first image never requires `vision.analyze`.
B5  No global ControlDeck gateway key/session cookie copied into Media Forge.
B6  Normal prompt-only generation/edit remains usable without AI assistance.
B7  Deterministic pixel/geometry facts never depend on VLM output.
B8  User facts/overrides outrank deterministic facts, accepted reference semantics, Director inference, and suggestions.
B9  Reuse current CreativeCompiler/C3/C4/C5 paths; no second generation/batch/composer/evaluator stack.
B10 Fixed Pose presets remain fallback/Advanced shortcuts, not the primary vocabulary.
B11 Automatic semantic retry remains bounded by the existing QA budget.
B12 No public frozen JobRequest break and no Media-specific ControlDeck route.
```

---

## 2. Canonical execution flows

### 2.1 New image, no reference

```text
intent
 -> Creative Director (`text.generate`, when available)
 -> PromptPlan / ActionStateSpec
 -> compatibility projection + existing CreativeCompiler
 -> normal image Job/Broker/worker
 -> deterministic validation
 -> optional post-image evaluator (`vision.analyze`)
```

**Pre-generation vision calls: zero.**

### 2.2 New image with reference(s)

```text
reference asset
 -> VisualFacts (deterministic, cached)
 -> VisualAnalysis (`vision.analyze`, cached)

intent + accepted reference summary
 -> Creative Director (`text.generate`)
 -> existing CreativeCompiler / normal generation
 -> optional evaluator
```

### 2.3 C3 action variation

```text
accepted parent PromptPlan
 -> one text.generate request for 2–4 bounded semantic deltas
 -> existing C3 child CreativeSpecs/Jobs
```

Do not call the Director once per child and do not re-analyze the same reference per child.

### 2.4 C4 multi-cut

Director may produce child shot briefs. Exact layout/text remains the current deterministic Composer.

---

## 3. Old-plan consolidation mapping

The old future slices are retired as planning units:

```text
old A1  semantic reviewer migration       -> CI-1
old A2  VisualFacts                       -> CI-3
old A3  VLM VisualAnalysis                -> CI-3
old A4  Prompt Planner/Refiner            -> CI-2
old A5  Create UI integration             -> CI-2 + CI-3
old A6  multidimensional evaluator        -> CI-4
old A7  installed-host acceptance         -> CI-5
```

A0 stays complete and is not reimplemented.

---

## 4. CI-1 — provider-neutral AI cutover

### Goal

Remove all production provider/model/port decisions from Media Forge before expanding AI usage.

### Required changes

1. Add `ai.inference` to `addon.json` `host_capabilities`.
2. Replace production `OllamaSemanticReviewer` transport with a ControlDeck-backed reviewer using `HostAIGateway(..., "vision.analyze")`.
3. Replace production `OllamaCreativeEvaluator` transport with a ControlDeck-backed evaluator using `vision.analyze` while preserving current C5 scoring behavior.
4. Remove `semantic_reviewer_url` / `semantic_reviewer_model` and corresponding environment variables from production Settings.
5. Move shared bounded review-image preprocessing out of provider-specific code if needed so both Reference Intelligence/Evaluator can reuse it without importing an Ollama implementation.
6. Preserve deterministic-first validation and existing retry/ranking semantics.

### Important constraint

This slice changes transport/boundary, not product behavior. Do not redesign the evaluator or UI here.

### Error normalization

```text
host AI grant missing       host_ai_not_granted
vision unavailable          vision_analyzer_unavailable
host unavailable            host_ai_unavailable
invalid structured response vision_result_invalid
```

No local-provider fallback.

### Tests

- add-on manifest grants `ai.inference`;
- fake Host vision response drives current semantic review/evaluator behavior;
- response/provider/model extras do not affect Media Forge behavior;
- no production `/api/chat`, `/api/tags`, `11434`, provider/model URL setting remains in AI-assistance transport;
- prompt-only generation remains unchanged;
- existing deterministic QA/retry budget tests remain green.

### Real acceptance before merge

- installed ControlDeck service token can call `vision.analyze` through Media Forge;
- change ControlDeck-selected compatible target/runtime and repeat without Media Forge config change;
- normal image generation remains functional when `vision.analyze` is unavailable.

---

## 5. CI-2 — Creative Director for brand-new generation

### Goal

Make arbitrary action/pose/scene/composition direction come from a structured text Director rather than a growing preset list.

### Reuse

Use the already-merged `PromptPlanner`, `PromptPlan`, `SubjectSpec`, `ActionStateSpec`, `HostAIGateway`, and `CreativeCompiler`.

Do **not** create a second planner service. If naming improves clarity, introduce `CreativeDirector` as a thin product-level wrapper around the existing planner implementation.

### User-facing modes

Map the current internal modes without a schema break:

```text
そのまま  -> original
自動      -> refine
演出強め  -> art_direct
```

Simple default: `自動` when `text.generate` is available. The user may always choose `そのまま`.

### Director semantics

`自動`:

- preserve user meaning;
- extract/structure subject and action/state;
- fill only useful missing visible direction conservatively;
- do not compile imaginative optional suggestions automatically;
- never change explicit count/color/identity/action constraints.

`演出強め`:

- may propose camera/lighting/staging/composition;
- additions stay identifiable as AI suggestions;
- accepted suggestions become normal structured values/provenance.

### Existing Pose compatibility

First production bridge:

```text
ActionStateSpec
 -> PoseSpec(preset="custom", details=<bounded compiled action text>)
```

All current Scene templates already accept `custom`, so this reuses the current compiler without expanding the public contract.

Canonical provenance still stores `ActionStateSpec`. For non-human subjects, “pose” is only the compatibility field used by the existing compiler.

### Create integration

Reuse the current intent field and Scene & framing area. Add one compact control:

```text
演出 [自動 ▾]
  そのまま
  自動
  演出強め
```

Do not add a wizard or new top-level page.

After a Director run, provide a compact existing-page disclosure:

```text
理解した内容
  user facts
  action/state
  inferred scene/composition/camera
  optional suggestions
```

The current Simple Pose selector is demoted/conditional, not deleted yet. Advanced retains manual Pose/custom details and exposes canonical Action/State fields as they become available.

### Fail-soft policy

If text planning is unavailable/invalid/times out:

- keep the original intent intact;
- explain that Director assistance was skipped;
- allow the existing prompt-only generation path;
- do not convert the image job itself into a Host AI failure.

### Variation upgrade in the same vertical slice

For C3 `pose/action` variations, add a bounded Director method that returns 2–4 ActionState deltas in **one** `text.generate` request. Feed those deltas into the existing C3 parent/child system.

Do not alter batch persistence, reconnect, cancel, partial-retention, candidate-strip, or Broker paths.

### Tests

- new text-only prompt makes zero vision calls before generation;
- uncommon human pose -> custom action details -> normal CreativeCompiler;
- robot/vehicle/product actions do not require person-only presets;
- explicit user constraints win over Director output;
- server-owned `version/original_intent/mode` remain protected (#49 regression);
- unknown provider-authored fields still fail closed;
- unavailable text.generate -> prompt-only generation still works;
- C3 action variations use one planner request and create normal child Jobs;
- Simple/Advanced DOM rule and 320/390 px no-overflow remain intact.

---

## 6. CI-3 — Reference Intelligence

### Goal

Analyze existing/reference images without making vision a dependency for new prompt-only generation.

### Part A: deterministic VisualFacts

Implement lightweight Pillow-only analysis:

```text
width
height
aspect_ratio
has_alpha
opaque_fraction
dominant_colors [{hex, coverage}]
accent_colors
mean_luminance
mean_saturation
```

Cache key:

```text
asset sha256 + visual-facts analyzer version
```

Rules:

- downsample before palette quantization;
- ignore highly transparent pixels for palette coverage;
- no torch/transformers/OpenCV dependency in core;
- do not mutate the asset.

### Part B: VLM VisualAnalysis

Only after an image exists, call:

```text
HostAIGateway.complete(..., "vision.analyze", ...)
```

Strict result sections:

```text
subject / count
action_state
scene
composition
style
clothing_props
text_regions
observations
inferences
confidence_by_field
```

Deterministic facts win on measurable fields.

### Reference-role integration

Reuse the current collection/roles:

```text
identity / style / pose / composition / clothing / palette / prop / environment
```

Analysis proposes roles/values; it never silently mutates a Character/Style profile.

### Director integration

The Director receives accepted **analysis JSON summaries**, not raw image bytes. The VLM sees the image; the text Director sees structured accepted context.

### UI

Reuse the current reference area. Add compact shortcuts only when an image exists:

```text
全体 / 主役 / 動き / 色 / 構図 / 画風
```

### Tests

- same bytes -> same VisualFacts/cache key;
- transparent background does not dominate palette;
- person, robot, vehicle/product fixtures produce bounded ActionState semantics;
- no vision call when no reference image exists;
- cached reference analysis reused across C3/C4 children;
- role-specific application does not overwrite unrelated dimensions.

---

## 7. CI-4 — Unified Evaluator and semantic-QA de-duplication

### Goal

Converge the current C5 six-axis evaluator and older binary semantic reviewer into one product-level evaluation result without creating a second judge loop.

### Target model

Use the already-defined `EvaluationResult` dimensions:

```text
intent
subject_identity
action_state
palette
composition
style
props_clothing
visual_integrity
```

### Behavior

1. deterministic validators remain authoritative and run first;
2. VLM evaluation is post-image only;
3. score only dimensions relevant to user constraints/reference roles;
4. default = advisory rank/show/explain;
5. automatic regeneration is opt-in and consumes the existing bounded QA budget;
6. provenance records dimension scores/issues/strengths/capability name, not required provider/model identity.

### Migration

Retire duplicate binary semantic-review interpretation once Jobs can derive required accept/retry behavior from `EvaluationResult`.

Keep one bounded image-preprocessing utility and one ControlDeck `vision.analyze` transport.

### Performance

- do not evaluate every normal single-candidate generation by default;
- rank when user requests compare/quality or when C3 provides multiple candidates;
- batch candidate context where bounded and supported;
- never introduce an unbounded generate->judge->retry loop.

### Tests

- palette-only reference does not penalize action;
- pose/action reference does not require palette match;
- deterministic failure cannot be overridden by VLM score;
- evaluator unavailable leaves valid generated assets usable;
- retry count never exceeds existing configured budget;
- current C5 result-stage ranking behavior remains available.

### Completion (2026-08-23)

Implemented on `creative/ci4-unified-evaluator`. Jobs and C5 comparison now use
the same `HostCreativeEvaluator` and canonical `EvaluationResult`; the binary
`semantic_review.py` implementation was removed. The frozen `qa.semantic` and
`image.semantic_review` names remain compatibility entrances only. Deterministic
validation runs before evaluation, normal single generation remains opt-out,
and the existing 0..3 regeneration budget is the only retry budget.

Real isolated-Host acceptance ranked two imported candidates through two
`vision.analyze` calls in 18.338 seconds. Only `intent` and
`visual_integrity` were relevant; the other six scores were null. Host audit
metadata contained only the capability name, Broker active/waiting counts were
zero, and the selected runtime was unloaded. See `implementation-status.md` for
the full evidence and NOT TESTED scope.

---

## 8. CI-5 — C4 shot direction + bounded quality integration

### Goal

Use the Director to improve multi-cut shot intent while preserving deterministic composition.

### Scope

- Director may create 2–4 structured shot briefs from the accepted parent PromptPlan.
- Existing child Job path generates each shot.
- Existing C4 Composer remains authoritative for layout, crop, frame, title/caption, safe margins, dimensions and exact text.
- Reuse Character/Style/reference analysis across all children.
- Optional evaluator may rank/select child candidates or inspect final composition, but must not regenerate unboundedly.

### Explicit non-goal

Do not ask a diffusion/VLM model to render exact title/logo/UI text that the Composer can place deterministically.

### Completion (2026-08-23)

Implemented on `creative/ci5-shot-quality`. A non-`original` C4 composition now
uses one provider-neutral `text.generate` request to derive the accepted parent
PromptPlan and exactly 2--4 structured shot briefs. Shot count, index, and
`main` / `coding` / `device` / `chibi` roles remain server-owned. The briefs are
projected into the existing ordinary child Job requests; C4 still owns layout,
crop, frame, safe margins, output dimensions, and exact title/caption rendering.
No second batch, composer, evaluator, or retry budget was added.

Reference Intelligence context is reused when already accepted. Prompt-only
composition makes no pre-generation `vision.analyze` call. `original` mode and
AI unavailable/invalid responses fail soft to the existing deterministic
multi-cut route. Existing `qa.semantic` and its 0..3 budget remain unchanged;
the CI-4 evaluator is the only semantic quality path.

Installed-ControlDeck structural acceptance completed in 64.452 seconds with
one text request, zero vision requests, three normal child Jobs, three shot
assets, one deterministic composed asset, 320px overflow 0, and zero browser
console/page errors. The fixture used the fake image worker, so the configured
Broker correctly refused to evict a large LLM for its one-second estimate; an
explicit operator LLM stop was used before the three leases were granted and
released. Automatic text-to-real-image Broker handoff, R9700 visual
consistency, and subjective final quality remain CI-6 work, not CI-5 claims.

---

## 9. CI-6 — installed-host acceptance and release gate

Run against an installed ControlDeck + Media Forge, not mocks only.

Required evidence:

```text
- addon has ai.inference grant
- text.generate works through service token
- brand-new text-only image: Director works, pre-generation vision calls = 0
- `そのまま` mode: no Director call and normal generation works
- vision.analyze works for a real reference image
- ControlDeck selected runtime/target can change without Media Forge config changes
- uncommon human action produces Director custom action/pose details
- non-human action/state works
- C3 action variation creates 2–4 meaningful child actions with one Director request
- reference facts/analysis cache reused
- evaluator ranks at least two candidates when explicitly requested
- no retry beyond existing budget
- AI unavailable -> prompt-only generation still succeeds
- 320px and 390px installed iframe acceptance
- browser console/page errors 0
- Broker active/waiting returns to 0 after tests
```

R9700 measurements should record separately:

```text
Director request latency (warm/cold if observable)
reference VLM analysis latency
candidate evaluation latency
image generation latency
runtime swap/load impact
VRAM/Broker behavior
```

Do not promote a claim from unit tests to real-machine evidence.

### Completion (2026-08-23)

Completed against installed ControlDeck and the installed v0.5.0 bundle on an
R9700/gfx1201 host. The add-on retained its `ai.inference` grant and used only
Host-selected `text.generate` / `vision.analyze`; Media Forge configuration did
not gain a provider, model, or port. A new prompt-only image made one Director
text call and zero pre-generation vision calls. The Director projected an
uncommon one-handed backbend into a custom pose, and the ordinary capability
route generated a validated FLUX asset. `original` mode made no AI call and
generated a non-human solar-panel rover normally.

The existing C3 path made one Director request, produced two distinct repair
actions, and completed two ordinary child Jobs. Explicit CI-4 evaluation ranked
the welding candidate first without creating another generation Job. Real
reference analysis, cache reuse, original-mode bypass, and installed iframe
acceptance were repeated from the v0.5.0 bundle. Removing every compatible Host
AI target while retaining the grant and image capability caused Director to
fail soft with `host_ai_unavailable`; prompt-only real generation still
succeeded. The Host target and policy were restored after the test.

Measured values and output-quality observations are recorded in
`implementation-status.md`. Final Broker leases and requests were both zero,
320px and 390px overflow were zero, and browser console/page errors were zero.
CI-1 through CI-6 are complete. This does not change H3's experimental,
unhealthy, unroutable status and does not claim public video support.

---

## 10. Stop conditions

Return to design instead of patching around the boundary if any implementation would require:

```text
- Media-specific ControlDeck provider/model route;
- provider/model/port choice in Media Forge;
- ControlDeck global gateway key/session cookie in Media Forge;
- vision.analyze before a prompt-only first image exists;
- raw filesystem paths across the Host AI boundary;
- a new public JobRequest break instead of private/additive planning data;
- a second batch/composer/evaluator storage stack;
- an unbounded autonomous retry loop;
- torch/transformers in lightweight core merely for orchestration;
- expansion of a huge human Pose preset catalog as the primary action solution.
```

---

## 11. Implementation order

```text
CI-1  provider-neutral AI cutover
CI-2  Creative Director + new-image path + action variations
CI-3  Reference Intelligence (VisualFacts + VLM + roles/cache)
CI-4  Unified Evaluator / semantic-QA de-duplication
CI-5  C4 Director shot briefs / bounded quality integration
CI-6  installed-host + R9700 acceptance / release
```

CI-1 is mandatory before production use of new AI assistance. CI-2 is the highest user-value slice after the boundary migration because it directly removes dependence on the limited Pose preset vocabulary for brand-new generation.
