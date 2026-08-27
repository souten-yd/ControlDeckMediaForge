# Media Forge — Model / Scene / Composition UX design

Status: Design extension for the existing workspace
Date: 2026-08-22
Applies to: current UX1 workspace after PR-U7
Related source: `docs/design-workspace-ux.md`
Implementation plan: `docs/implementation/ux2-model-scene.md`

This document extends the current workspace design. It does **not** replace the existing Create/Library/Activity/Settings information architecture, the Simple/Advanced progressive-disclosure model, or the current generation/edit flow.

## 1. Goal

Make Media Forge useful as a local art-production front end without turning it into a node editor or forcing users to understand model internals.

The user must be able to:

- keep using the current Create screen and current prompt/reference/edit flow;
- choose a broad creative domain such as anime, illustration, photoreal, 2D game asset, poster, character sheet, background, or general;
- optionally choose scene, pose, composition, camera/framing, and variation direction;
- reuse Character / Style / Reference profiles already introduced by G3;
- install and remove locally managed models with a small number of taps;
- use downloaded models automatically in Simple mode and select an exact model in Advanced mode;
- create multiple scene/pose/composition variants without rebuilding the UI as a wizard;
- later compose multi-cut posters/character sheets from multiple generated shots.

## 2. Reuse-first rules

These are hard constraints for this extension.

1. **Do not replace the current Create screen.** Add controls to the current instruction panel and reuse the existing result stage, candidate strip, recent assets, progress, error exits, and mobile layout.
2. **Do not add a top-level Models tab.** Keep the existing 3 navigation items plus Settings.
3. **Keep Simple / Advanced.** New controls follow the same L1/L2/L3 disclosure rules as the existing workspace.
4. **Do not expose a node graph.** Scene/pose/composition are user concepts and are compiled into existing generation operations and profiles.
5. **Do not make model names part of the normal generation flow.** Simple mode selects a domain and quality intent; routing chooses an installed capable model. Exact model selection remains Advanced/manual.
6. **Do not auto-download models just because Generate was pressed.** The existing `auto_download_models: false` principle remains. Missing capability produces one clear action to open Model Management.
7. **Do not move Media-specific logic into ControlDeck core.** ControlDeck remains host/scheduler/lease/lifecycle; Media Forge owns catalogs, profiles, creative planning and model installation.

## 3. Critical review decisions

### 3.1 Keep: progressive disclosure

The current Simple/Advanced split is correct. A complete redesign would throw away a UX improvement that already solved the G0 problem of exposing every low-level control at once.

### 3.2 Modify: Models must not be visible only to experts

The earlier design was correct to remove the old standalone Models tab, because model IDs, licenses and capability names were not useful during ordinary generation. However, hiding **installation and removal itself** behind Advanced mode is too restrictive for a local-first product.

Decision:

- `Settings > Model Management` is visible in Simple mode.
- Simple Model Management shows friendly names, domains, approximate size, installed/downloading state, and `Download` / `Remove` actions.
- exact `model_id`, revision, hash, runtime adapter, raw capability list and benchmark diagnostics remain Advanced.
- the Create screen still hides model names in Simple mode.

Experimental candidates are visible under an explicit media filter and carry
an `Experimental / not measured` label. They never appear under Recommended.
When the trusted catalog can describe a candidate but cannot yet package every
runtime-owned dependency, its action is disabled as `Install with external
runtime`; the UI must not start an incomplete managed download.

This preserves capability-driven generation while making local model ownership practical.

### 3.3 Keep: bounded semantic review

Do not introduce an unlimited generate/judge loop. Scene/pose/composition variation can create many expensive jobs. Automatic regeneration therefore keeps an explicit retry budget and is opt-in for subjective review.

### 3.4 Reject: one-shot poster generation as the primary path

A complex poster or character sheet should not depend on one giant prompt. The later production path is multi-pass: generate shots, evaluate/select, then compose deterministically. One-shot generation remains available for quick use.

### 3.5 Reject: LoRA training as the first solution for style consistency

Style/character/reference profiles and role-aware references come first. House-style LoRA training is a later optional feature after the user has accumulated suitable assets and explicitly chooses training.

## 4. Information architecture

No top-level navigation change:

```text
Create       existing screen; gains optional domain + creative controls
Library      existing assets + Character / Style / Reference collections
Activity     existing job state/history
Settings     existing settings + Model Management
```

### 4.1 Settings / Model Management

Simple mode:

```text
Model Management
  Storage: 84 GB used / 210 GB free
  [Installed] [Recommended] [All]
  Domain: All / Anime / Illustration / Photoreal / 2D Game / Poster / General

  Illustrious XL       Anime · Illustration         13 GB   [Downloaded] [Remove]
  FLUX.2 Klein         General · Edit · Reference   12 GB   [Downloaded] [Remove]
  Pony Diffusion V6 XL Anime · 2D Game             7 GB    [Download]
  ...
```

Advanced adds:

- exact model ID / revision / weights hash;
- runtime adapter and hardware backend;
- normalized capabilities;
- measured cold load / warm generation / VRAM data;
- source and license details;
- health / compatibility diagnostics;
- manual/custom catalog registration when that feature is implemented.

### 4.2 Download interaction

`Download` is a direct action. It starts immediately after disk/license preflight and the row becomes progress UI; no multi-page wizard.

Display in the same row:

- queued / downloading / verifying / ready / failed;
- bytes and percentage when known;
- pause/cancel only when supported by the installer;
- one actionable failure exit.

A gated model or missing source authorization must fail before downloading and show the required next action.

### 4.3 Remove interaction

Removal is easy but not single-tap destructive.

- first tap: `Remove`;
- compact confirmation sheet: model name + reclaimable size + whether a profile references it;
- confirm: remove only Media-Forge-managed weights;
- active model in a running job cannot be removed until that job releases it;
- profiles are not silently rewritten. If a manual profile references a removed model, it remains reproducible metadata but becomes unavailable and offers `Download again` / `Choose another model`.

This one confirmation is intentional: accidental deletion of multi-GB weights is more costly than one extra tap.

### 4.4 Managed vs external models

Media Forge must not delete arbitrary files from a shared Hugging Face cache, ComfyUI directory, or user-selected external library.

Model entries therefore carry ownership:

- `managed`: downloaded into the Media Forge managed model store; UI may remove it;
- `external`: detected/registered outside the managed store; UI may use it but `Remove` is disabled and explains that the source is externally managed.

This is a safety and interoperability requirement, not a generic confirmation layer.

## 5. Create screen extension

The existing Create screen remains one page.

### 5.1 Simple mode

Keep all existing inputs. Add only two compact concepts.

#### Domain

A small chip row, default `Auto`:

```text
Domain: [Auto] [Anime] [Illustration] [Photoreal] [2D Game] [Poster] [More…]
```

Domain is a routing hint, not a model selector. It narrows recommended profiles/models and can alter default prompt/style templates. `More…` opens the rest without changing route.

If no installed model can satisfy the chosen domain/capability, show an inline message near Generate:

```text
Anime generation is not installed. [Open Model Management]
```

Do not start a download from Generate.

#### Scene & framing

Collapsed by default, one row:

```text
Scene & framing  [Auto]   ▸
```

Expanded Simple controls use friendly chips and optional presets:

- Scene: Auto / standing intro / coding at desk / presenting device / seated / action / custom
- Pose: Auto / holding item / typing / peace / wave / arms crossed / sitting / custom
- Composition: Auto / bust-up / full body / centered / off-center / poster / character sheet
- Camera: Auto / close / medium / full body / low / high / 3/4
- Variation: same idea / vary pose / vary scene / vary composition

Each category is optional. `Auto` means the Art Planner may derive it from the natural-language intent.

The prompt remains the primary control. A user can still write `M5Stackを持って笑顔で横ピース` and press Generate without opening this panel.

### 5.2 Existing Character / Style controls

Do not create a parallel character/style system. Reuse the G3 profile/reference-collection path and the current `キャラ・画風を使う` affordance.

Extend references with an internal role:

- identity
- style
- pose
- composition
- clothing
- palette
- prop
- environment

Simple mode infers the role from the selected action/profile where possible. Advanced mode allows explicit role assignment.

### 5.3 Advanced mode

The current advanced panel remains the container. Add fields there rather than a new screen:

- full domain list;
- existing `model_policy` and manual model selector;
- optional LoRA list. Selecting a LoRA constrains automatic routing to a
  compatible base-model family; the user does not select or apply that base
  model separately;
- structured SceneSpec / PoseSpec / CompositionSpec values;
- explicit reference roles and strengths;
- seed and compatible engine options when supported;
- variation count/axis and batch policy;
- semantic review and retry budget (existing principle).

Engine-specific knobs stay namespaced and only appear when the chosen adapter declares them.

## 6. Creative planning model

The UI creates an internal `CreativeSpec`; this is a workspace implementation detail and does not require a breaking public API change.

Conceptual structure:

```json
{
  "domain": "anime",
  "scene": {
    "preset": "coding_at_desk",
    "environment": "compact maker desk",
    "props": ["M5Stack", "laptop"],
    "mood": "energetic"
  },
  "pose": {
    "preset": "presenting_device",
    "hand_gesture": "peace",
    "gaze": "camera"
  },
  "composition": {
    "preset": "full_body_off_center",
    "camera": "three_quarter",
    "negative_space": "left"
  },
  "variation": {
    "axis": "pose",
    "count": 4
  }
}
```

A `CreativeCompiler` translates the spec plus existing intent/profile/references into the existing image.generate/image.edit request path. The first implementation must avoid changing frozen public schemas just to support workspace controls.

The normalized spec should be preserved in provenance/sidecar metadata when the existing metadata envelope allows it, so generated assets remain reproducible.

## 7. Model catalog extension

The current registry already has model identity, capabilities, state, weights, hardware backend, policy rank, limits and measurements. Extend catalog metadata rather than replace the registry.

Additional catalog metadata:

```text
display_name
domains[]
description
preview_asset (optional)
approx_download_bytes
source.kind
source.repo_id / source.revision
ownership = managed|external
supports_lora
max_references
recommended_profiles[]
license_notice / gated flag
```

Domain tags are advisory. Routing still verifies normalized capabilities, installed/healthy state, hardware support, measured resource envelope and selected quality policy.

LoRA is a routing constraint, not a standalone generation model. In the normal
flow the LoRA is the only model-like item the user chooses. Media Forge must:

- install a compatible base checkpoint as part of the same confirmed download
  when none is installed;
- present the LoRA and dependency licenses, total download size, and disk
  effect in one confirmation rather than silently accepting a dependency;
- constrain automatic routing to the LoRA family and apply its trigger words;
- reject mixed-family LoRAs before generation; and
- keep the resolved base model in provenance/details without requiring a
  separate base-model choice in the primary UI.

Initial catalog targets are non-binding and must pass the existing R9700/ROCm adoption gate before becoming recommended/default:

- existing FLUX.2 target(s);
- Illustrious / NoobAI family;
- Pony Diffusion V6 XL;
- Animagine / compatible anime models;
- Qwen-Image family;
- RealVisXL / Juggernaut / DreamShaper style SDXL targets when runtime support is verified;
- user-requested janku v6.0 as a catalog/custom target only after exact source, license, architecture and ROCm workflow are verified.

A name in the catalog is **not** proof that a model works on R9700.

## 8. Managed model store

Introduce a Media-Forge-owned store separate from runtime venvs and separate from arbitrary shared caches.

Requirements:

- configurable managed model root;
- download into a temporary contained directory;
- fixed revision when a catalog entry specifies one;
- size/disk preflight;
- checksum/file verification before activation;
- atomic promotion to `ready`;
- interrupted downloads never appear installed;
- installer state survives workspace reload;
- cancellation cleans temporary state safely;
- removal only targets paths known to be managed by Media Forge;
- shared download caches may be used as caches, but ownership of cache blobs must not be assumed.

The core remains lightweight. Heavy model runtime dependencies stay in worker/runtime environments. The installer may be a dedicated subprocess/component rather than importing ML stacks into the core.

## 9. Variation generation

Two levels:

### Level A — one request

For a single selected Scene/Pose/Composition, compile the controls into one existing generation request and use the existing candidate count.

### Level B — intentional variation batch

When `vary pose`, `vary scene`, or `vary composition` is selected, a planner produces child CreativeSpecs and submits bounded child jobs. The existing result stage and candidate strip show the results as one logical batch.

Do not fake intentional variation by only changing seeds and claiming the pose/composition changed.

Batch limits are capability/resource aware and must not bypass the ControlDeck broker. Jobs may queue; they must not independently load enough models to OOM the host.

## 10. Multi-cut / poster / character-sheet path

This is an incremental extension of the current Create flow, not a new product surface.

1. choose `Poster` or `Character Sheet` domain/composition preset;
2. planner derives required shots;
3. each shot is generated using the same Character/Style profiles;
4. user sees/selects candidates in the existing stage;
5. deterministic Composer places shots, titles, labels, frames and UI elements;
6. final composite appears as another asset in the existing Library.

Text and layout that must be exact should be composed with deterministic SVG/Canvas/Pillow tooling instead of relying entirely on the image model.

## 11. Evaluation

Use deterministic validation first:

- dimensions/format/alpha;
- required transparent regions;
- layout boxes / safe regions;
- strict-edit pixel invariants;
- output count and manifest validity.

Semantic evaluation can score:

- identity similarity;
- requested pose/action;
- style similarity;
- scene/composition match;
- obvious hand/face breakage when the chosen VLM can reasonably detect it.

Subjective retry remains bounded. Default behavior is to show alternatives rather than silently spend unbounded GPU time.

## 12. Mobile UX

Reuse the current embedded mobile workspace and bottom navigation.

- Domain chips horizontally scroll only inside their own chip strip; the page itself must not horizontally scroll.
- `Scene & framing` opens as a compact bottom sheet/accordion and returns selected chips to the Create screen.
- Model Management uses one-column cards/rows with 44px+ targets.
- download progress remains visible if the user changes tabs; a small non-blocking progress indicator may reuse the existing mini-progress pattern.
- destructive confirmation is a bottom sheet, not a tiny modal.

## 13. Acceptance criteria

### Reuse

- existing Create/Library/Activity/Settings routes remain;
- current Simple/Advanced preference persists and still controls advanced DOM;
- existing generation/edit/mask/outpaint/library/export flows continue to pass their tests;
- no new top-level Models tab and no node graph.

### Model management

- a user can open Settings > Model Management without enabling Advanced;
- one tap starts a permitted model download after preflight;
- progress survives workspace reload/reconnect;
- completed model becomes selectable/routable without editing config files;
- removing a managed model takes one action plus one confirmation;
- external models cannot be deleted by Media Forge;
- deleting/removing a model never silently rewrites a saved manual profile.

### Creative controls

- prompt-only generation still works unchanged;
- domain selection narrows routing without exposing model names in Simple mode;
- scene, pose and composition can each be changed independently;
- same character/style profile can be reused across at least three pose variants and three composition variants;
- intentional `vary pose` / `vary scene` / `vary composition` creates traceable child specs rather than just different seeds;
- poster/character-sheet mode can use multiple generated shots and deterministic text/layout composition.

### Hardware

- every recommended model is marked measured/not-measured on Radeon AI PRO R9700 + ROCm;
- a not-measured catalog entry is never promoted to the default route merely because it downloaded successfully.
