# UX2 — model management + scene / pose / composition controls

Target repository: **ControlDeckMediaForge only**
Design: `docs/design-model-scene-ux.md`
Existing UX source: `docs/design-workspace-ux.md`
Prerequisite: current UX1 workspace remains the base; do not replace it.

## 0. Objective

Extend the current Create/Library/Activity/Settings workspace so users can manage local models and deliberately vary scenes, poses and compositions while preserving the current Simple/Advanced philosophy and current generation/edit flows.

This is an additive product slice. It is **not** a rewrite.

## 1. Hard boundaries

```text
B1  Reuse existing Create UI, result stage, candidate strip, progress, Library, Activity and mobile shell.
B2  Keep 3 navigation items + Settings. Do not reintroduce a top-level Models tab.
B3  Settings > Model Management is reachable in Simple mode.
B4  Create Simple mode does not expose exact model IDs. Exact model selection stays Advanced/manual.
B5  Generate never silently downloads a model. auto_download_models remains false.
B6  Model download/remove is Media Forge owned; do not add Media-specific code to ControlDeck.
B7  Do not import torch/diffusers/transformers into the core environment.
B8  Do not delete arbitrary shared HF/ComfyUI/user files. Only Media-Forge-managed weights may be removed.
B9  Do not break frozen public schemas for workspace-only creative controls. Prefer /ws implementation-detail methods and internal compilation.
B10 Existing image.generate/edit, mask, outpaint, export, G3 profile/reference and provenance behavior must keep working.
```

## 2. Implementation slices / PR order

Each PR must be independently usable and must update the handoff/status only with real evidence.

```text
PR-M0  model-store/catalog schema extension + managed/external ownership
PR-M1  durable model download/remove backend + /ws methods
PR-M2  Settings > Model Management UI (Simple + Advanced detail)
PR-C0  CreativeSpec + template catalog + compiler, no UI replacement
PR-C1  extend current Create screen with Domain + Scene & framing
PR-C2  role-aware references + current Character/Style UI integration
PR-C3  intentional variation batches (scene/pose/composition child specs)
PR-C4  multi-cut planner + deterministic Composer for poster/character sheet
PR-C5  semantic evaluator integration + R9700 acceptance/benchmarks
```

Do not start PR-C4 before C0-C3 are usable with ordinary single-image generation.

---

## 3. PR-M0 — model registry/store extension

### Reuse

Extend `backend/mediaforge/models/registry.py`; do not create a second routing registry.

The existing descriptor already owns:

```text
model_id / family / version / revision / weights_hash / license
runtime_adapter / capabilities / hardware_backends / state / policy_rank
required_files / weights / installed / healthy / measurements / limits
```

Add catalog-facing metadata through an additive manifest version or a separate catalog metadata layer if changing the current strict schema would be disruptive.

Required logical fields:

```text
display_name
domains[]
description
approx_download_bytes
source.kind
source.repo_id
source.revision
ownership = managed|external
supports_lora
max_references
recommended_profiles[]
gated/license_notice
```

### Managed model root

Add a Media-Forge-owned model directory separate from runtime venvs and arbitrary shared caches.

Config principles:

```text
model_store_root = Media Forge owned
HF_HOME/cache     = reusable download cache only; not deletion ownership
external roots    = usable/detectable but read-only from Model Management
```

### Required behavior

- registry can report installed managed and installed external models;
- same model identity cannot ambiguously claim both ownership modes;
- external entries never expose a remove operation;
- catalog entry may exist without being installed;
- not-measured models remain not-measured after download.

### Tests

- schema rejects unknown ownership;
- managed path containment and symlink escape tests;
- external model remains usable but non-removable;
- catalog metadata does not affect capability routing correctness;
- existing registry/routing tests remain unchanged where possible.

---

## 4. PR-M1 — durable download/remove backend

### New workspace implementation-detail methods

Prefer `/ws`; do not add new public generation operations merely for the embedded UI.

Conceptual methods:

```text
models.catalog
models.install
models.remove
models.operations.list
models.operations.watch / unwatch
```

`models.list` may be extended/reused instead of duplicating it if its current semantics remain compatible.

### Download state machine

```text
queued -> preflight -> downloading -> verifying -> installing -> ready
                                      \-> failed
queued/downloading -> canceled
```

Persist operation state so reload/reconnect does not lose progress.

### Install algorithm

1. validate catalog/source entry;
2. verify the model is allowed for local installation;
3. calculate required bytes + safety margin and compare free disk;
4. verify any required authorization/gated state before large transfer;
5. create contained temporary install directory;
6. download at the pinned revision when known;
7. verify required files, byte sizes/checksums when available;
8. atomically promote into managed model root;
9. rescan existing `ModelRegistry`;
10. publish changed state to workspace.

A partially downloaded model must never appear `installed=true`.

### Remove algorithm

1. resolve exact model identity;
2. reject `ownership=external`;
3. reject/queue if a running worker currently holds the model;
4. calculate reclaimable managed bytes;
5. delete only the exact contained managed directory;
6. rescan registry;
7. keep profile metadata unchanged; dependent manual profiles become unavailable, not rewritten.

### Failure exits

Every backend error code used by UI needs one user action:

```text
insufficient_disk        -> free storage / choose another store
model_gated              -> authorization required
model_download_failed    -> retry
model_verify_failed      -> retry clean download
model_in_use              -> open Activity / wait
external_model_owned     -> manage at source
model_not_found           -> refresh catalog
```

### Core dependency rule

Do not put ML runtime dependencies into core. Use a bounded installer subprocess/component when required. `httpx`/small support code in core is acceptable only if it does not pull the image runtime into core.

### Tests

- interrupted download never becomes installed;
- restart preserves operation state;
- cancellation cleans temporary files;
- bad hash is rejected;
- path traversal/symlink escape is rejected;
- external remove is rejected;
- in-use remove is rejected without killing the job;
- after successful install `capabilities.get` sees the model without manual config editing.

---

## 5. PR-M2 — Model Management UI

### Existing IA only

Add a Model Management section to the current Settings view.

Simple mode must contain:

```text
storage summary
filter: Installed / Recommended / All
friendly domain chips
model rows/cards
Download / Remove action
inline progress/state
one failure exit
```

Do **not** require Advanced to install/remove models.

Advanced mode adds a details drawer or expanded row:

```text
model_id / revision / hash
runtime adapter / hardware backend
capabilities
measured VRAM / cold load / runtime
license/source/gated state
health/compatibility diagnostics
```

### UX behavior

Download:

- one tap starts after preflight;
- button becomes inline progress;
- leaving Settings does not cancel;
- current global/mini progress pattern may show an active model operation without replacing job progress.

Remove:

- tap Remove;
- compact confirmation sheet with friendly name + reclaimable size + profile references;
- confirm Remove;
- no second settings page.

### Create-screen missing-model exit

When domain/capability has no installed model, reuse current inline error pattern and add exactly one action: `Open Model Management`.

Do not auto-start install from Generate.

### Mobile

- one-column rows/cards;
- 44px+ targets;
- confirmation uses bottom sheet;
- no page-level horizontal scroll;
- download progress remains understandable after navigation.

### Browser acceptance

Desktop + 390px + 320px:

```text
Simple settings can reach Model Management
Advanced details are absent from DOM in Simple mode
Download can be started in <= 2 taps from Settings
Remove requires exactly one confirmation after the Remove action
External model has no destructive action
progress survives route change + reload/reconnect
```

---

## 6. PR-C0 — CreativeSpec / template catalog / compiler

### Do not change the public request contract first

Add internal workspace-side/server-side planning objects:

```text
CreativeSpec
SceneSpec
PoseSpec
CompositionSpec
VariationSpec
ReferenceRole
```

These are implementation details used to compile into the existing request path.

### Templates

Store templates as versioned data, not hardcoded DOM conditionals.

Initial Scene presets:

```text
auto
standing_intro
coding_at_desk
presenting_device
seated
thinking
action
chibi_greeting
```

Initial Pose presets:

```text
auto
holding_item
typing
peace
wave
arms_crossed
sitting
walking
custom
```

Initial Composition presets:

```text
auto
bust_up
full_body_center
full_body_off_center
three_quarter
poster
character_sheet
multi_cut_promo
```

### CreativeCompiler

Input:

```text
existing intent
existing generation profile
existing character/style/reference collections
CreativeSpec
capability/model envelope
```

Output:

```text
existing JobRequest-compatible intent/constraints/profile/reference inputs
+ normalized internal plan snapshot for provenance
```

Do not add engine-specific sampler terms to generic templates.

### Tests

- prompt-only with empty CreativeSpec produces the same request as before;
- each template compiles deterministically;
- invalid pose/composition combination returns a user-facing validation problem before GPU admission;
- unavailable capability does not get compiled as if available;
- compiler output does not force a model ID unless model_policy=manual.

---

## 7. PR-C1 — extend the current Create UI

### Reuse existing controls

Do not move or duplicate:

```text
intent field
reference image import
size presets/custom size
count
Character/Style row
Generate button
result stage/candidate strip
advanced panel
```

### Add to Simple

#### Domain row

Default Auto. Friendly labels only.

Suggested first visible chips:

```text
Auto / Anime / Illustration / Photoreal / 2D Game / Poster / More…
```

Persist last domain as a preference only if user testing shows this helps; do not force persistence if it causes surprising cross-job carryover.

#### Scene & framing accordion

Closed by default. When opened show compact chip/select controls for:

```text
Scene
Pose
Composition
Camera/framing
Variation axis
```

Prompt remains primary; all of these can stay Auto.

### Add to Advanced

Inside the existing advanced template/panel:

```text
full domain list
structured scene fields
structured pose fields
structured composition fields
reference roles/strengths
compatible LoRAs (after model support exists)
variation batch options
```

Keep existing model_policy/manual model selector exactly in Advanced.

### Pre-submit validation

Reuse existing `requestProblem()` / inline failure pattern. No browser-native bubbles and no post-admission avoidable failure.

### Browser acceptance

- existing prompt-only generation route submits the same request shape;
- Simple DOM still contains no `advanced-*` nodes;
- Domain changes routing hint only;
- Scene/Pose/Composition can each be selected independently;
- 320px has no page horizontal scroll;
- keyboard/tab order remains logical.

---

## 8. PR-C2 — Character / Style / role-aware references

### Reuse G3

Do not create new Character/Style stores.

Extend existing reference collection metadata with roles where an additive internal representation is possible:

```text
identity
style
pose
composition
clothing
palette
prop
environment
```

Simple mode:

- reuse current `キャラ・画風を使う` interaction;
- role is inferred from selected profile/action when possible;
- no matrix of strength sliders.

Advanced:

- explicit role per reference;
- role strength when adapter supports it;
- capability-aware maximum reference count;
- unsupported role/adapter combination disabled with reason.

### Acceptance

- same Character/Style profile produces at least three deliberate pose variants;
- identity reference can remain fixed while pose reference changes;
- style reference can remain fixed while composition reference changes;
- reference count cannot exceed active envelope before admission.

---

## 9. PR-C3 — intentional variation batches

### Problem

Current `count > 1` can produce candidates but does not guarantee the requested variation axis changed.

### Design

For `vary_pose`, `vary_scene`, or `vary_composition`:

1. planner derives N bounded child CreativeSpecs;
2. each child has explicit plan metadata and seed;
3. jobs use normal ControlDeck Broker admission;
4. parent logical batch tracks child state;
5. current result stage/candidate strip shows child outputs together;
6. Activity can drill down to child jobs in Advanced mode.

No child runs outside the broker and no batch preloads N copies of a model.

### Acceptance

- `vary pose x4` records four distinct pose specs;
- `vary composition x4` records four distinct composition specs;
- canceling logical batch cancels queued/running children safely;
- partial success is visible and does not discard successful assets;
- reconnect restores batch progress.

---

## 10. PR-C4 — multi-cut planner + deterministic Composer

### Reuse existing Create/Library

Poster/Character Sheet are domains/composition presets, not new top-level apps.

### Planner

A layout template defines regions such as:

```text
main character
secondary coding shot
secondary device-presenting shot
chibi shot
title area
caption/info area
```

Generate shots as ordinary child jobs with the same Character/Style profiles.

### Composer

Use deterministic tooling for exact elements:

```text
image placement/crop
masks
text
logo/title
frames
speech bubbles/info panels
safe margins
final export dimensions
```

Do not ask the model to regenerate the whole poster merely to change a title.

### Acceptance

- 2-4 generated shots can be composed into one asset;
- title/caption text can be edited without regenerating character shots;
- final output is reproducible from layout spec + child asset IDs;
- all child lineage appears in provenance;
- mobile can inspect final output using the existing viewer.

---

## 11. PR-C5 — evaluator and R9700 acceptance

### Semantic evaluation

Add only after deterministic and planner constraints are working.

Possible semantic scores:

```text
identity match
style match
pose/action match
scene match
composition match
obvious visual breakage
```

Default behavior: rank/show alternatives.
Automatic regeneration requires an explicit bounded budget.

### R9700 model adoption gate

Every catalog target promoted to Recommended must record on Radeon AI PRO R9700 / ROCm:

```text
exact model/revision/runtime
cold load time
warm generation time at named resolution/steps
resident VRAM
execution peak VRAM
cold-load peak VRAM
headroom
multi-reference result if supported
LoRA result if supported
failure/recovery behavior
```

A downloaded model with no measurement is allowed as `Not measured` / Experimental but not silently selected as the default recommended route.

### Initial candidate handling

Do not hardcode assumptions from external recommendation lists. Verify exact source/architecture/license/runtime first, especially for community names such as `janku v6.0`.

---

## 12. Data/API implementation notes

### Workspace methods

Keep model-management and creative-planning UI methods under the existing authenticated workspace transport where possible.

Potential additive methods:

```text
models.catalog
models.install
models.remove
models.operations.list
creative.templates
creative.validate
```

Do not return raw host paths. Use internal IDs and friendly metadata.

### Preferences allowlist

Only add keys that materially improve continuity, e.g.:

```text
last_domain (optional)
creative_panel_open (optional; evaluate whether worth persisting)
model_catalog_filter (optional)
```

Do not persist secrets, model source tokens, paths, or temporary prompt state in preferences.

### Provenance

Preserve:

```text
selected domain
CreativeSpec/template IDs + versions
reference roles
actual routed model identity
variation parent/child relation
composer layout spec + child asset IDs
```

when allowed by the existing provenance metadata envelope.

---

## 13. Definition of done

UX2 is complete when a normal user can do this without leaving the current product flow:

1. Settings -> Model Management -> download an anime model.
2. Return to Create.
3. Keep Simple mode.
4. Choose Anime + existing Character/Style profile.
5. Enter one natural-language intent.
6. Optionally choose Pose and Composition without seeing a model ID.
7. Generate multiple deliberate pose/composition variants.
8. Inspect them in the existing result stage/Library.
9. In Advanced mode, reproduce the job with an exact installed model and explicit reference roles.
10. Remove a Media-Forge-managed model from Settings with one confirmation.

And all existing UX1 generation/edit/export/mask/mobile tests still pass.
