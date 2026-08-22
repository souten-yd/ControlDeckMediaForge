# Creative Intelligence implementation plan

Design: `docs/design-creative-intelligence.md`  
Existing UX base: `docs/design-workspace-ux.md`  
Existing creative base: `docs/implementation/ux2-model-scene.md`

This plan is additive. Keep the current Create/Library/Activity/Settings shell and current JobRequest/public schemas.

## 0. Hard boundaries

```text
A1  No Ollama/llama.cpp/provider/model/port branches in Media Forge AI assistance code.
A2  Text planning uses ControlDeck capability `text.generate`.
A3  Image understanding/evaluation uses ControlDeck capability `vision.analyze`.
A4  No global ControlDeck gateway API key copied into Media Forge; use scoped Add-on Runtime credentials.
A5  Prompt-only generation remains usable when AI assistance is absent.
A6  Deterministic pixel/geometry facts never depend on VLM output.
A7  Keep original intent immutable and distinguish AI suggestion from user fact.
A8  Reuse CreativeSpec/Compiler, reference roles, C3 batches, C4 Composer and current semantic QA coordinator.
A9  No new top-level navigation and no wizard.
A10 Automatic semantic retry stays bounded by the existing QA budget.
```

## 1. Current code audit

Already reusable:

```text
backend/mediaforge/creative.py            CreativeSpec + deterministic compiler
backend/mediaforge/creative_batches.py    bounded deliberate variants
backend/mediaforge/composer.py            C4 planner/composer
backend/mediaforge/profiles.py            Character/Style profiles
backend/mediaforge/jobs.py                deterministic QA + bounded semantic retry
frontend/index.html + app.js              current Create/Result/Library/Activity UI
```

Must be replaced/retired:

```text
backend/mediaforge/semantic_review.py
  current production implementation calls Ollama `/api/tags` and `/api/chat` directly.

backend/mediaforge/config.py
  current semantic reviewer defaults name an Ollama URL and a concrete VLM model.
```

ControlDeck facts verified before this plan:

```text
- RuntimeChatRequest/provider layer already normalizes OpenAI-compatible and Ollama generation.
- multimodal content arrays are already converted to Ollama native `images` when required.
- llama.cpp instances already expose `mmproj_path` for VLM operation.
- Ollama model config already has `vlm_enabled`.
- existing public LLM gateway uses a dedicated API key and is not an appropriate secret to copy into an add-on.
- Add-on Runtime currently lacks scoped AI inference; ControlDeck PR #224 adds generic `ai.inference`.
```

## 2. PR order

One slice per PR. Do not combine UI/product behavior with the host-boundary migration.

```text
PR-A0  provider-neutral Host AI seam + typed creative-intelligence models + detailed plan
PR-A1  replace direct Ollama semantic reviewer with ControlDeck `vision.analyze`
PR-A2  deterministic VisualFacts + cached Reference Analyzer backend
PR-A3  VLM VisualAnalysis + apply-to-CreativeSpec/reference roles
PR-A4  text Prompt Planner/Refiner backend + immutable original intent
PR-A5  reuse current Create UI for Refine / analyzed-reference suggestions
PR-A6  multi-dimensional Evaluator + ranking + current bounded retry integration
PR-A7  installed-host acceptance + R9700/selected-runtime swap evidence
```

ControlDeck PR #224 is a dependency for A1/A3/A4/A6. It is a separate repository/PR because the host feature is generic.

---

## 3. PR-A0 — provider-neutral seam

### Deliverables

Add lightweight core types/services only:

```text
HostAIGateway
PromptPlan
SubjectSpec
ActionStateSpec
VisualFacts
VisualAnalysis
EvaluationResult
```

`HostAIGateway` takes existing `ControlDeckHostClient` + `HostIdentity` and calls only:

```text
/{addon_id}/ai/capabilities
/{addon_id}/ai/complete
```

It does not accept provider/model/base_url parameters.

### Acceptance

- fake Host returns structured text and vision responses;
- returned provider/model fields, if a malicious fake includes them, are ignored by typed result code;
- unsupported capability maps to one normalized Media Forge error;
- no production string `/api/chat`, `11434`, `llama.cpp`, or provider branch exists in the new path;
- no existing generation behavior changes in A0.

---

## 4. PR-A1 — semantic reviewer migration

Replace the transport implementation behind the existing `SemanticReviewer` coordinator.

### Required changes

- remove production `OllamaSemanticReviewer`;
- remove `semantic_reviewer_url` / concrete model defaults from Settings;
- hosted semantic review receives the current `HostIdentity` from the active HostExecution;
- standalone semantic QA is unavailable unless a future standalone host-AI adapter is explicitly configured;
- current deterministic-first ordering and bounded retry semantics stay unchanged.

### Error mapping

```text
host capability not granted -> host_ai_not_granted
vision unavailable          -> vision_analyzer_unavailable
host unreachable            -> host_ai_unavailable
malformed structured result -> vision_result_invalid
```

No fallback to a local provider port.

---

## 5. PR-A2 — deterministic VisualFacts

Add a lightweight analyzer under core, Pillow-only initially.

### Input

Existing asset ID/path after current containment checks.

### Output

```text
width
height
aspect_ratio
has_alpha
opaque_fraction
dominant_colors [{hex, coverage}]
accent_colors[]
mean_luminance
mean_saturation
```

### Cache key

```text
asset sha256 + VisualFacts analyzer version
```

Do not mutate the asset.

### Acceptance

- same bytes produce same facts/hash;
- alpha-transparent pixels do not dominate palette;
- bounded memory on a large input by downsampling before quantization;
- no ML dependency enters core.

---

## 6. PR-A3 — VLM VisualAnalysis

Use `vision.analyze` through HostAIGateway.

### Schema sections

```text
subject
subject_count
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

### Merge rule

Deterministic VisualFacts wins on measurable facts. VLM values are semantic annotations and cannot override exact dimensions/palette samples.

### Reference-role application

Analysis may **suggest** roles:

```text
identity / style / pose / composition / clothing / palette / prop / environment
```

The current reference collection is reused. No second reference store.

### Non-person requirement

At least vehicle, robot and product fixtures must produce ActionStateSpec without requiring PoseSpec.

---

## 7. PR-A4 — Prompt Planner / Refiner

Call `text.generate` with strict structured output.

### Modes

```text
original
refine
art_direct
```

### Invariants

- store original intent unchanged;
- explicit user constraints win;
- AI additions are marked suggestions until accepted;
- no engine-specific sampler/scheduler vocabulary;
- accepted plan compiles through existing CreativeCompiler;
- empty/unaccepted plan leaves current JobRequest unchanged.

### Tests

- conflict resolution;
- malformed host JSON;
- same accepted plan compiles deterministically;
- text target unavailable leaves original generation usable.

---

## 8. PR-A5 — current Create UI integration

Do not redesign the page.

Reuse the current intent field and `Scene & framing` disclosure.

### Add

Near intent:

```text
[指示を整える]
```

Inline result card:

```text
理解した内容
user facts
AI suggestions
[使う] [調整] [元に戻す]
```

For an attached/reference image add compact role shortcuts:

```text
全体 / 主役 / 動き / 色 / 構図 / 画風
```

The current explicit Pose selector is not deleted in this slice. Simple may hide/demote it after real-use evidence shows Prompt Planner + reference analysis covers the common path. Advanced retains exact Pose/Action fields.

### Mobile

320px/390px: inline card, no modal wizard, no horizontal scroll.

---

## 9. PR-A6 — Evaluator

Evolve the existing binary semantic review result, do not create another judge loop.

### Scores

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

### Reference-role awareness

Only score dimensions requested by the reference role. Example: a palette reference does not penalize pose.

### Default behavior

```text
score -> rank/show alternatives
```

Automatic regeneration remains opt-in and uses the current `max_regeneration_attempts` bound.

### Provenance

Store dimension scores, issues, strengths, and host AI capability name. Do not make provider/model identity a required field.

---

## 10. PR-A7 — real acceptance

Installed ControlDeck + Media Forge, not standalone mocks only.

Required evidence:

```text
- ControlDeck ai.inference grant present
- text.generate works through service token
- vision.analyze works through service token
- switch selected ControlDeck runtime/target and repeat without Media Forge config change
- reference image: person action + palette + composition extracted
- reference image: non-person action/state extracted
- prompt refine -> accepted plan -> normal generation
- evaluator ranks at least two candidates
- no retry beyond budget
- normal prompt-only route still works with AI assistance unused
- 320px/390px browser acceptance
- console/page errors 0
```

Any missing real-model evidence is recorded `NOT TESTED`, never inferred from unit tests.

---

## 11. Stop conditions

Stop and return to design if:

```text
- host AI contract would need a Media-specific route or model name;
- Media Forge would need a ControlDeck session cookie or global gateway API key;
- VLM requires raw filesystem paths crossing the host boundary;
- public frozen JobRequest must be broken rather than extended privately;
- evaluator needs an unbounded retry loop;
- core would need torch/transformers only for analysis orchestration.
```
