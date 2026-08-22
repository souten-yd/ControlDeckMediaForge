# Creative Intelligence — Prompt Planner / Reference Analyzer / Evaluator

Status: design baseline for implementation  
Date: 2026-08-22  
Target: ControlDeckMediaForge

Related sources of truth:

- `docs/base-plan.md`
- `docs/controldeck-integration-plan.md`
- `docs/design-workspace-ux.md`
- `docs/design-model-scene-ux.md`
- `docs/implementation/ux2-model-scene.md`
- ControlDeck `docs/design-addon-platform-v2.md`
- ControlDeck `docs/design-llm-runtime-chat-contract.md`

This document extends the current architecture. It does not replace Create, CreativeSpec, Character/Style profiles, C3 variation batches, C4 Composer, the current job path, or the frozen public generation contract.

---

## 1. Goal

Media Forge should accept short natural-language intent and reference images, understand them, turn them into a reusable structured creative plan, and evaluate generated results without forcing a user to manually fill person-specific pose controls.

The target interaction is:

```text
user intent + optional reference images
              |
              v
      Creative Intelligence
      |- Prompt Planner / Refiner
      |- Reference Analyzer
      |- Deterministic visual facts
      |- VLM semantic observations
      |- CreativeSpec suggestions
      '- Evaluator
              |
              v
 existing CreativeCompiler / C3 batch / C4 Composer / JobRequest
              |
              v
 image worker -> deterministic validation -> semantic ranking
```

The system remains generic for people, animals, vehicles, robots, products, architecture, environments, UI/game assets and future video planning.

---

## 2. Important terminology correction: LLM and VLM are different jobs

Earlier discussion used "LLM brush-up" as a broad label. The implementation must distinguish the tasks.

### Text-only planning

Use a text-capable model for:

- prompt cleanup and clarification;
- expansion of terse intent into structured details;
- extraction of hard constraints from natural language;
- creating bounded variations;
- turning user intent into a CreativeSpec suggestion.

Logical host capability: `text.generate`.

### Image understanding and image-to-image evaluation

Use a vision-language model for:

- subject/action/pose/state extraction;
- semantic composition understanding;
- clothing/prop/environment description;
- style cues that are not directly measurable from pixels;
- checking whether a generated candidate matches intent/reference images.

Logical host capability: `vision.analyze`.

### Deterministic analysis

Do **not** use a VLM for facts that pixels or geometry can measure more reliably:

- exact image size/aspect ratio;
- dominant palette and color distribution;
- alpha/background coverage;
- basic luminance/saturation distribution;
- exact hashes;
- known masks and unchanged-pixel constraints;
- output dimensions and safe regions.

These remain ordinary local deterministic code.

---

## 3. Non-negotiable ControlDeck boundary

Media Forge must not bind creative intelligence to Ollama, llama.cpp, LM Studio, a port, a model alias, or any provider-specific API.

Forbidden Media Forge production logic:

```text
http://127.0.0.1:11434
/api/chat
llama-server port selection
provider == "ollama"
provider == "llama.cpp"
qwen3-vl:2b as a required model
```

Media Forge asks ControlDeck for a **capability**, not an implementation:

```text
text.generate
vision.analyze
```

ControlDeck owns:

- selected runtime/provider;
- target model selection;
- multimodal protocol conversion;
- structured-output dialect fallback;
- runtime loading/unloading;
- GPU/KV admission and supervision;
- provider-specific errors and secrets.

Media Forge owns:

- creative prompts and JSON schemas;
- image preprocessing for the analysis request;
- result validation;
- product-level retry/ranking policy;
- UI and provenance.

### Host API dependency

Current ControlDeck has a provider-neutral `RuntimeChatRequest` layer and an OpenAI-compatible gateway, but the existing Add-on Runtime does not yet project a scoped text/vision inference API to add-ons. Media Forge therefore must not copy provider selection locally or steal the global gateway API key.

The generic host extension is:

```text
host capability: ai.inference
GET  /api/v1/addon-runtime/{addon_id}/ai/capabilities
POST /api/v1/addon-runtime/{addon_id}/ai/complete
```

Request chooses only:

```text
capability = text.generate | vision.analyze
messages
response_format
temperature
max_tokens
timeout
```

No provider/model/port field exists in the add-on contract.

ControlDeck PR #224 implements this generic host slice and contains no Media-specific behavior. Media Forge integration must remain fail-closed until that host contract is present and granted.

---

## 4. Findings from the current Media Forge codebase

### Reuse, do not replace

The current implementation already has valuable primitives:

- `CreativeSpec`, `SceneSpec`, `PoseSpec`, `CompositionSpec`, `CameraSpec`, `VariationSpec`;
- deterministic `CreativeCompiler`;
- role-aware references: identity/style/pose/composition/clothing/palette/prop/environment;
- Character/Style profiles and reference collections;
- C3 bounded child variation batches;
- C4 multi-cut planner and deterministic Composer;
- existing Create prompt, reference import, result stage, candidate strip, Library and Activity;
- deterministic image validators;
- existing semantic review coordinator and bounded regeneration budget.

Creative Intelligence must feed these pieces rather than creating a second generation stack.

### Current architectural violation to remove

`backend/mediaforge/semantic_review.py` directly implements an Ollama client and `backend/mediaforge/config.py` defaults it to a named VLM. This is incompatible with the provider-neutral boundary above.

The existing semantic review policy itself is useful:

- deterministic validation happens first;
- semantic review is advisory with zero retry budget;
- automatic regeneration is bounded when explicitly requested.

The transport/provider dependency is the problem, not the QA coordinator.

---

## 5. Critical review of the proposed AI features

The following concerns are valid and are incorporated into the design.

### C1. "Longer prompts always improve detail" is false

A text model can add irrelevant adjectives, conflicting camera terms, invented clothing, extra objects or unwanted scene details. Longer is not automatically better.

Decision:

- retain immutable `original_intent`;
- distinguish user facts from AI suggestions;
- produce structured fields first, model-facing prose second;
- never silently overwrite a user constraint;
- initial UX makes enhancement explicit rather than always-on.

### C2. VLM output is not ground truth

A VLM can misread hands, small props, exact colors, text, depth or occlusion.

Decision:

- every extracted value carries `source=observed|inferred|suggested` and confidence;
- exact palette/geometry stays deterministic;
- low-confidence semantic fields do not become hard constraints automatically;
- evaluator scores are evidence for ranking, not proof.

### C3. A single total score can hide the failure the user cares about

A candidate can score well overall while missing identity or pose.

Decision:

Keep dimension scores:

```text
intent
subject / identity
action / pose / state
palette
composition
style
props / clothing
defects
```

The UI may summarize, but provenance stores the dimensions.

### C4. Automatic generate -> judge -> retry can waste GPU time

Decision:

- default: rank/show alternatives;
- deterministic hard failures may retry according to existing rules;
- semantic retry is opt-in and bounded by the existing QA budget;
- no unbounded autonomous loop.

### C5. Making AI planning mandatory would make the core brittle

Decision:

- prompt-only generation remains valid;
- no AI target means the user can still generate/edit normally;
- deterministic reference facts still work without a VLM;
- only the unavailable assistance action degrades.

### C6. Person-oriented controls do not generalize

Decision:

`PoseSpec` remains for compatibility and internal precision, but the new semantic layer uses the more general concept `ActionStateSpec`.

Examples:

```text
person       kneeling / pointing / gaze-to-camera
animal       running / crouching / flying
vehicle      drifting / parked / door-open
robot        chest-panel-open / crouched / arm-extended
product      static / exploded-view / rotated
architecture intact / under-construction / night-lit
```

The Simple UI should gradually stop requiring the user to think in terms of "pose". Advanced retains explicit pose/action editing.

---

## 6. Structured data model

These are private workspace/planning models. They do not replace the frozen public JobRequest.

### 6.1 PromptPlan

```text
version
original_intent
mode = original | refine | art_direct
subject
primary_action
scene
composition
camera
style_cues[]
details[]
hard_constraints[]
optional_suggestions[]
assumptions[]
```

Rules:

- `original_intent` is immutable;
- `hard_constraints` are only user-stated or deterministic facts;
- AI additions go to `optional_suggestions` unless the user accepts them;
- compiler emits no engine/sampler terminology.

### 6.2 SubjectSpec

Generic subject description:

```text
kind = person | character | animal | creature | vehicle | robot | product | object |
       architecture | environment | ui_asset | game_asset | other
count
identity_traits[]
appearance_traits[]
materials[]
```

No subject type is required in the UI. Auto is normal.

### 6.3 ActionStateSpec

```text
action
state
orientation
gesture
gaze
motion_hint
body_or_part_relations[]
confidence
```

For people/characters, existing PoseSpec can be populated as a compatibility projection. For non-person subjects, PoseSpec may remain Auto while ActionStateSpec carries the useful semantics.

### 6.4 VisualFacts

Deterministic observation only:

```text
width / height / aspect_ratio
has_alpha
palette.dominant[]
palette.accent[]
luminance
saturation
edge_density (optional later)
```

### 6.5 VisualAnalysis

```text
version
asset_id/hash
facts: VisualFacts
subject: SubjectSpec
action_state: ActionStateSpec
scene
composition
style
clothing_props[]
text_regions[]
observations[]
inferences[]
confidence_by_field
```

### 6.6 EvaluationResult

```text
accepted_for_requested_constraints
scores:
  intent
  subject_identity
  action_state
  palette
  composition
  style
  props_clothing
  visual_integrity
issues[]
strengths[]
retry_suggestions[]
review_budget_used
```

---

## 7. Reference Analyzer pipeline

Input can be an imported reference, profile reference, generated asset, or candidate.

```text
asset
  -> bounded decode
  -> deterministic facts
  -> 768px-class review representation
  -> ControlDeck vision.analyze
  -> strict JSON schema validation
  -> merge facts + semantics
  -> VisualAnalysis snapshot
```

### Deterministic palette

Initial implementation should use Pillow only and remain in the lightweight core:

1. convert RGB/RGBA;
2. downsample to a bounded working size;
3. ignore highly transparent pixels;
4. quantize to a small palette;
5. record color + coverage;
6. derive luminance/saturation summary.

Do not add OpenCV merely for the first palette implementation.

### Semantic VLM analysis

The VLM receives only a bounded review image and a task-specific JSON schema. It should not receive filesystem paths.

The prompt instructs it to:

- describe visible facts before interpretation;
- not invent hidden body parts/objects;
- return confidence per semantic section;
- separate observed from inferred;
- use generic action/state language for non-human subjects.

---

## 8. Prompt Planner / brush-up

The Simple UI keeps `何を作りますか？` as the primary control.

Add one compact action near the intent field:

```text
[指示を整える]
```

After use, show a small review card, not a second page:

```text
理解した内容
  user facts      ...
  AI suggestions  ...
[この内容を使う] [調整] [元に戻す]
```

Initial modes:

```text
Original    no AI rewrite
Refine      preserve meaning, clarify useful visual detail
Art Direct  may suggest camera/lighting/composition, visibly marked as suggestions
```

Do not make Art Direct the default.

### Interaction with existing controls

When a PromptPlan is accepted:

- existing Domain remains a routing hint;
- existing Scene/Composition/Camera can be prefilled;
- existing Pose becomes an Advanced/internal compatibility field;
- C3 variation uses the resulting normalized structured plan;
- C4 Composer uses the same plan for shot briefs.

No duplicate set of scene/pose controls is created.

---

## 9. UI generalization

### Simple

Gradual target:

```text
What to create
[textarea]
[指示を整える]

optional reference image(s)
  [この画像を参考にする]
  -> role shortcuts: 全体 / 主役 / 動き / 色 / 構図 / 画風

見せ方
  Auto / Product / Character / Game Asset / Poster / More

Variation
  Auto / 別の動き / 別の構図 / 別のシーン
```

The current `Scene & framing` accordion is reused. Person-only options should become conditional or move to Advanced rather than expanding the Simple surface.

### Advanced

Retain/edit:

- Subject
- Action / Pose / State
- Scene
- Composition
- Camera
- exact reference roles/strengths
- model/seed/manual settings
- raw analysis confidence and AI suggestions

Advanced must not require AI. Every accepted plan remains editable as ordinary structured values.

---

## 10. Evaluator integration

Reuse the existing semantic-review coordinator and QA budget instead of creating a second judge loop.

Evolution:

```text
current binary accepted + summary
          |
          v
multi-dimensional EvaluationResult
          |
          +-> current advisory validation entry
          +-> candidate ranking
          +-> optional bounded retry
          '-> Activity / provenance detail
```

Deterministic validators run first. VLM never overrides an exact failure such as dimension, alpha, mask or unchanged-pixel validation.

For a reference-driven job, evaluator input includes:

- candidate review image;
- selected reference review images;
- normalized CreativeSpec/PromptPlan;
- user hard constraints;
- deterministic facts.

Avoid asking the VLM to compare irrelevant dimensions. Example: a palette-only reference must not penalize a different pose.

---

## 11. Storage and provenance

Do not create a second asset database.

Store analysis/planning snapshots as bounded JSON linked to existing asset/job/profile records where possible.

Required provenance additions:

```text
original_intent
accepted PromptPlan version/hash
AI-added suggestions that were accepted
reference analysis version/hash
reference roles
EvaluationResult dimension scores
host AI capability used: text.generate / vision.analyze
```

Do not store ControlDeck provider/model identity as a Media Forge requirement. If the Host returns implementation metadata for diagnostics in the future, treat it as optional provenance, not a behavioral dependency.

---

## 12. Failure and degradation behavior

```text
ControlDeck AI bridge unavailable
  -> normal generation still works
  -> enhancement/analyze/evaluate action says unavailable

text.generate unavailable
  -> reference deterministic facts + VLM analysis may still work if vision is available

vision.analyze unavailable
  -> palette/geometry facts still work
  -> semantic reference extraction/evaluation unavailable

malformed AI JSON
  -> reject result, keep original user input, allow retry

AI adds conflict with explicit user constraint
  -> explicit user value wins; log conflict as suggestion rejection
```

No silent fallback to Ollama, llama.cpp, a guessed port, or a bundled VLM is allowed in core.

---

## 13. Performance policy

Creative Intelligence should not make one image require several serial AI calls by default.

Rules:

- Prompt refinement is opt-in initially.
- Reference analysis is cached by asset hash + analyzer version.
- Deterministic facts run once per asset version.
- VLM analysis results are reusable across jobs.
- Evaluator batches candidate/reference context where supported, but keeps request bounds.
- C3 children reuse parent analysis rather than re-analyzing the same reference N times.
- C4 shots reuse the same Character/Style/reference analysis.

Target first-pass overhead excluding model cold load:

```text
prompt plan request        <= one text AI request
reference analysis         <= one vision request per new asset hash
evaluation                 <= one vision request per candidate group where feasible
```

---

## 14. Security / privacy

- AI calls stay under ControlDeck scoped authorization.
- No ControlDeck session cookie enters Media Forge.
- No global ControlDeck gateway API key is copied into Media Forge.
- No raw provider port is persisted.
- Images sent to Host AI are downscaled/bounded data, not filesystem paths.
- Remote image URLs in the add-on AI bridge are rejected.
- The existing local-first policy remains in force; remote provider support is a separate ControlDeck policy decision and must not be silently enabled by Media Forge.

---

## 15. Completion definition

Creative Intelligence is complete when all of these are demonstrated on the installed host:

1. short prompt -> optional Refine -> accepted PromptPlan -> ordinary generation;
2. the same request works after changing the ControlDeck selected AI runtime without a Media Forge configuration change;
3. one person reference extracts action/pose + palette + composition;
4. one non-person reference (vehicle/robot/product) extracts generic action/state without forcing person pose fields;
5. deterministic palette matches pixel-derived values independent of VLM wording;
6. generation candidates receive dimension scores and can be ranked;
7. no semantic retry exceeds the existing explicit retry budget;
8. prompt-only generation with AI assistance unused stays behaviorally unchanged;
9. grep/code inspection finds no production Ollama/llama provider branch in the new Media Forge AI path;
10. 320px/mobile reuses the existing Create/Result/Library flow without a new wizard or top-level navigation item.
