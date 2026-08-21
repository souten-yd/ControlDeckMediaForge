# ControlDeck Media Forge — Base Plan

Status: Draft / baseline architecture  
Date: 2026-08-20

Implementation: G0 / MF0 completed on 2026-08-21. G1 real image generation is
implemented and measured on R9700/ROCm; completion remains pending on the
verified release-bundle standard installation E2E. See
`docs/implementation-status.md` for measurements and remaining NOT TESTED items.

## 1. Purpose

ControlDeck Media Forge (Media Forge) is a **local-first, general-purpose media generation subsystem** that can be installed as a ControlDeck add-on while remaining useful through a stable API outside ControlDeck.

The primary goal is not to reproduce ComfyUI's node editor. The primary goal is to let a user or an agent say what asset is needed and receive a validated, reproducible artifact:

- chat-driven general image generation and editing
- general video / animation generation and editing
- assets requested by OpenCode, Codex, OMO, or other coding agents
- M5Stack companion assets with strict pixel/alpha/anchor constraints
- 2D game sprites, portraits, UI, backgrounds, tiles, VFX, and asset packs
- web/app illustrations and UI assets
- reusable character/style/reference libraries
- Blender-assisted 3D asset production
- manga archive indexing and opt-in reference/training workflows when the user has the necessary rights

Media Forge should feel like a local media service, not a model demo.

---

## 2. Product principles

### 2.1 General media first; presets second

The first-class API is generic:

- `image.generate`
- `image.edit`
- `video.generate`
- `video.edit`
- `media.inspect`
- `asset.pack`

M5Stack, 2D game, web, manga, and 3D behavior are **optional profiles/presets** layered on top of these generic operations.

A recipe must never be required just to generate an ordinary image or video.

### 2.2 Capability-driven, not model-driven

Public contracts describe capabilities and constraints rather than specific model names.

Examples:

- `image.text_to_image`
- `image.single_reference_edit`
- `image.multi_reference_edit`
- `image.inpaint`
- `image.typography`
- `video.image_to_video`
- `video.multi_keyframe`
- `vision.quality_review`
- `3d.image_to_3d`

Models are selected by a router from an installable model registry. A model can disappear or be replaced without changing agent tools or project manifests.

### 2.3 Local-first is a policy, not an implementation accident

Initial releases perform inference locally and must not require a cloud generation API.

Default policy:

```yaml
policy:
  local_only: true
  allow_remote_inference: false
  auto_download_models: false
```

The internal provider interface may reserve a future remote provider boundary, but remote inference is disabled by default and is not required for any v1 feature.

### 2.4 Agents are clients, not owners of the architecture

OpenCode is an important client but Media Forge must not depend on OpenCode internals.

The stable integration surface is:

1. HTTP/JSON + WebSocket/SSE job events
2. a small agent-tool schema
3. optional MCP adapter
4. thin OpenCode/Codex/OMO bridges

This avoids creating a second media stack for every agent harness.

### 2.5 Deterministic constraints beat model promises

A vision model cannot guarantee exact pixels, dimensions, alpha values, file names, or safe-region boundaries.

Use deterministic tooling for deterministic requirements:

- Pillow/OpenCV/image libraries for dimensions, alpha, crops, masks, compositing, atlas creation
- FFmpeg for video packaging/transcoding/frame extraction
- Blender for deterministic 3D post-processing/export
- JSON/schema validators for manifests

VLM review is advisory/semantic QA, not a substitute for exact validators.

### 2.6 Preserve unchanged pixels by construction

For tasks such as M5Stack expression parts where the instruction is "change only these pixels", do not ask a generative model to recreate the whole image.

Pipeline:

1. derive or receive an explicit edit mask
2. generate only the editable region
3. compose the generated region over the original
4. copy every unmasked source pixel bit-for-bit
5. run a pixel-diff validator outside the mask

This should become a reusable `strict_edit` capability, not an M5-only hack.

### 2.7 Reproducibility and provenance are part of the asset

Every produced artifact receives a sidecar manifest containing enough information to understand how it was made:

- asset ID and parent asset IDs
- operation and requested intent
- model ID/version/hash and license metadata
- runtime/engine version
- prompt and structured constraints
- reference asset hashes
- seed and generation parameters where meaningful
- post-processing operations
- tool versions
- output hashes
- QA results and warnings

Generated files without provenance are considered incomplete library entries.

---

## 3. Critical review of earlier ideas

This section records deliberately rejected or modified approaches so the project does not drift back into them.

### 3.1 "Build a smaller ComfyUI"

**Rejected as the product architecture.**

Reason:

- exposes implementation detail rather than user intent
- creates fragile workflow graphs tied to particular model nodes
- raises the learning cost for M5/game/web users
- makes agent integration unnecessarily difficult

However, completely banning ComfyUI is also too rigid. New models often receive community integration quickly. Therefore an **optional ComfyUI-compatible worker/provider** may be implemented later. It is an adapter, never the core API or required runtime.

### 3.2 "Use Diffusers for everything"

**Rejected.**

Diffusers is a good default backend, especially for a local Python/ROCm path, but some models require native repositories, custom kernels, or different runtimes.

Required runtime adapter boundary:

- `diffusers`
- `native-python`
- `comfyui-http` (optional compatibility)
- `blender-cli`
- `ffmpeg`
- future optimized runtimes

### 3.3 "Make M5/game recipes the main API"

**Rejected.**

Recipes are useful for strict repeatable production, but a recipe-first API would make the system less useful for ordinary image/video generation.

Generic operation + optional profile is the rule.

### 3.4 "Choose one best model and standardize on it"

**Rejected.**

Media models are moving too quickly. A model can be excellent at image generation and poor at typography, editing, animation, AMD support, licensing, or memory usage.

Use capability routing and policy profiles such as:

- `auto`
- `fast`
- `balanced`
- `quality`
- `low_vram`
- `manual`

### 3.5 "VLM automatically judges and retries until good"

**Modified.**

Semantic QA is useful, but an unbounded generate/judge loop wastes GPU time and can oscillate.

Every job has a retry budget and explicit acceptance rules. Deterministic failures may be retried automatically; subjective QA should normally return alternatives or require explicit opt-in for iterative regeneration.

### 3.6 "Train LoRAs immediately from the manga ZIP library"

**Rejected as the default.**

First build import, indexing, retrieval, character/style/reference organization, and provenance. Training is opt-in, separately permissioned, and requires the user to confirm that the source material may be used for that purpose.

### 3.7 "3D generation should be a core v1 requirement"

**Rejected.**

3D generation quality, topology quality, material quality, and AMD runtime support are less predictable than 2D generation. Blender automation is stable and valuable even without AI 3D generation.

Therefore:

1. establish image/reference generation
2. establish Blender worker and deterministic post-processing
3. add image-to-3D providers as experimental capabilities

### 3.8 "Put all heavy dependencies inside ControlDeck"

**Rejected.**

ControlDeck should install/enable/disable Media Forge as an add-on, but PyTorch, model runtimes, video dependencies, and Blender belong to Media Forge workers. ControlDeck core should not inherit those dependencies.

---

## 4. System architecture

```text
ControlDeck UI / Chat
OpenCode / Codex / OMO / other agents
Workflow automation
Standalone API client
              │
              ▼
      Media Forge API
      ├─ auth/permissions adapter
      ├─ capability catalog
      ├─ request normalizer
      ├─ policy/model router
      ├─ durable job manager
      ├─ asset library
      ├─ profile/preset registry
      └─ QA/validation coordinator
              │
        Resource Scheduler
        ├─ GPU/VRAM leases
        ├─ worker concurrency
        ├─ priorities
        ├─ cancellation
        └─ model load/unload policy
              │
    ┌─────────┼──────────┬─────────┬──────────┐
    ▼         ▼          ▼         ▼          ▼
 Image     Vision      Video      3D       Utility
 worker     worker     worker    worker      worker
    │         │          │         │          │
Diffusers/   VLM     Wan/LTX/   model      Pillow
native      local      future      │        OpenCV
                                   ▼        FFmpeg
                                Blender
```

### 4.1 ControlDeck boundary

Media Forge should be an add-on, but it should not require deep ControlDeck coupling in order to run.

Preferred integration:

- ControlDeck manages installation, enable/disable, health, and service lifecycle
- Media Forge owns its heavy Python/model environment
- ControlDeck adds a Media route/sidebar entry
- ControlDeck passes a scoped identity/token or accesses Media Forge through a loopback-protected proxy
- project/file operations remain constrained to allowed roots
- Media Forge can contribute agent tools and workflow operations through a stable add-on contract

If ControlDeck's current add-on SDK initially supports only GUI integration, v0.x may run Media Forge as a managed local service plus GUI plugin. Deep backend/workflow contribution can be added after the ControlDeck add-on contract supports it. Media Forge itself must not be blocked on that core change.

### 4.2 Suggested repository layout

```text
ControlDeckMediaForge/
├─ addon.json
├─ backend/
│  └─ mediaforge/
│     ├─ api/
│     ├─ jobs/
│     ├─ assets/
│     ├─ routing/
│     ├─ models/
│     ├─ profiles/
│     ├─ validators/
│     ├─ workers/
│     └─ integrations/
├─ frontend/
├─ worker_packs/
│  ├─ image/
│  ├─ vision/
│  ├─ video/
│  ├─ blender/
│  └─ experimental_3d/
├─ profiles/
│  ├─ m5/
│  ├─ game2d/
│  └─ web/
├─ schemas/
├─ scripts/
├─ tests/
└─ docs/
```

Worker packs may later be separately packaged, but v0.x may keep them in one repository while preserving the boundary.

---

## 5. Stable request model

The API should avoid exposing engine-specific knobs as top-level concepts.

Conceptual job request:

```json
{
  "operation": "image.edit",
  "intent": "Close the character's eyes while preserving everything else",
  "inputs": [
    {"asset_id": "asset_master"}
  ],
  "profile": "m5.companion.expression",
  "model_policy": "auto",
  "constraints": {
    "width": 1280,
    "height": 960,
    "alpha": true,
    "strict_edit": true,
    "editable_mask_asset_id": "mask_eyes"
  },
  "output": {
    "format": "png",
    "count": 3
  },
  "qa": {
    "deterministic": true,
    "semantic": true,
    "max_regeneration_attempts": 1
  }
}
```

Engine-specific advanced parameters may exist under a namespaced `engine_options` object, but profiles and agents should avoid relying on them.

---

## 6. Capability catalog and model registry

Each installed model exposes a normalized capability descriptor.

Example fields:

```text
model_id
family
version
weights_hash
license
runtime_adapter
capabilities[]
hardware_backends[]
recommended_vram
supports_quantization
supports_lora
supports_seed
max_references
resolution_constraints
installed
healthy
```

Routing inputs include:

- required capabilities
- local-only policy
- hardware/backend compatibility
- license policy
- current VRAM availability
- requested quality/speed profile
- installed/healthy state

### 6.1 Initial model candidates (non-binding)

These are adapter targets, not architecture dependencies.

**Image**

- FLUX.2 [klein] 4B: strong candidate for fast local generation/editing and multi-reference work; Apache-2.0 for the 4B model.
- Qwen-Image family: candidate for general generation/editing, typography, posters/comics, and tasks benefiting from strong text/layout handling.

**Vision QA**

- a local multimodal VLM such as the Qwen-VL family or another model available through a local worker/ControlDeck-compatible endpoint.

**Video / animation**

- Wan2.2 family
- LTX-2 family

**3D**

- Hunyuan3D 2.1 and future image-to-3D providers as experimental adapters
- do not promise production-ready topology solely from the generative model

**3D post-processing**

- Blender background/Python worker is the stable production path.

Model choices must be benchmarked on the target AMD system before being promoted to a default profile.

---

## 7. Runtime and hardware strategy

### 7.1 AMD-first, vendor-neutral contract

The first optimized target is Linux + AMD GPU/ROCm, but public APIs must not contain ROCm-specific assumptions.

Runtime capability examples:

- `rocm`
- `cuda`
- `cpu`
- future accelerators

Initial preferred image path:

- PyTorch/ROCm
- Diffusers when supported
- native repository adapter when necessary

### 7.2 Resource scheduler is mandatory

Image and especially video models cannot be treated like ordinary HTTP handlers.

The scheduler must understand:

- GPU identity
- total/free VRAM estimate
- model residency
- requested worker memory class
- exclusive vs shareable jobs
- priority
- queue age
- cancellation
- timeout

Do not allow three independent UI tabs/agents to OOM the machine by independently loading large media models.

A future ControlDeck-wide GPU lease interface would be preferable so LLM and Media Forge jobs can coordinate instead of fighting for VRAM.

### 7.3 Load-on-demand

Default behavior:

- only load a model when a job requires it
- keep it warm for a configurable idle window
- evict lower-priority models under VRAM pressure
- do not preload every installed image/video/VLM model at boot

---

## 8. Image subsystem

First-class operations:

- text-to-image
- single-reference edit
- multi-reference edit
- inpaint
- outpaint
- variation
- strict masked edit
- upscale (adapter capability)
- background/foreground processing (utility capability)
- batch variants

The UI should expose:

- prompt/chat
- reference drop zone
- canvas/aspect ratio
- number of outputs
- Auto/Fast/Balanced/Quality/Manual
- optional advanced settings

The default UI should not expose a node graph.

---

## 9. Strict editing and M5Stack profile

M5Stack is a high-value validation case because it requires more than visual similarity.

### 9.1 Profile capabilities

Potential profiles:

- `m5.companion.base`
- `m5.companion.eyes`
- `m5.companion.mouth`
- `m5.companion.expression`
- `m5.companion.pose`
- `m5.companion.pack`

### 9.2 Constraint examples

- exact canvas dimensions
- RGBA requirement
- transparent background requirement
- safe rectangles
- anchor/pupil centers
- layer boundaries
- maximum changed region
- file naming rules
- atlas/manifest output

### 9.3 Validation

Deterministic validator:

- dimensions
- format/mode
- alpha constraints
- safe-region containment
- non-empty bounds
- exact unchanged-pixel comparison outside edit mask
- expected file count/names

Semantic validator (VLM):

- character identity changed
- hair/accessories changed unintentionally
- requested expression is visually correct
- obvious anatomical/artifact failure

A semantic pass must never override a deterministic failure.

---

## 10. 2D game asset subsystem

Profiles should produce engine-friendly artifacts, not just attractive PNGs.

Initial asset categories:

- character portrait / bust / full-body
- sprite frames
- sprite sheet / atlas
- enemy pack
- item/icon pack
- UI pack
- tiles/backgrounds
- VFX frames

Possible pack output:

```text
asset-pack/
├─ images/
├─ frames/
├─ spritesheet.png
├─ preview.webp
├─ manifest.json
├─ generation.json
└─ engine/
   ├─ godot/
   └─ generic/
```

The generation model should not be responsible for final sprite-sheet geometry. Frames are normalized/cropped/packed deterministically after generation.

Character consistency should progress in this order:

1. reference asset sets
2. structured Character Profile / Character Bible
3. multi-reference generation/editing
4. optional LoRA/fine-tuning only when needed

Do not make custom training a prerequisite for useful game asset generation.

---

## 11. Video and animation subsystem

The video API remains generic even when used to create game/M5 animation.

Operations:

- text-to-video
- image-to-video
- multi-keyframe/keyframe-conditioned video when supported
- video-to-video
- extend
- loop-oriented generation/post-processing
- frame extraction

Video output is always passed through a deterministic FFmpeg stage for:

- codec/container normalization
- frame rate
- dimensions
- duration constraints
- thumbnails/contact sheets
- frame extraction
- loop packaging where possible

For 2D games, a video model is not automatically the correct tool. Some animation packs should instead use pose/keyframe generation plus frame cleanup and deterministic atlas packing. Routing must be allowed to choose the cheaper/more stable path.

---

## 12. Blender and 3D subsystem

Blender should be treated as a deterministic asset compiler/toolchain, not merely a GUI application controlled by an agent.

Stable Blender operations may include:

- import
- transform normalization
- mesh validation/cleanup
- normals repair
- decimation
- LOD generation
- UV operations
- texture/material assignment
- texture baking
- collision proxy generation
- turntable rendering
- GLB/GLTF/FBX export

### 12.1 Safety

Do not directly execute arbitrary Blender Python emitted from a chat prompt in the long-running ControlDeck process.

Use:

- bounded worker jobs
- validated operation schemas
- trusted templates/operators for common operations
- isolated temporary working directories
- timeout/cancel
- explicit path allowlists

A future "custom script" expert mode can be separately permissioned.

### 12.2 Generative 3D

Image-to-3D/text-to-3D is an experimental upstream provider that produces a raw asset. Production export goes through Blender validation/post-processing.

Desired pipeline:

```text
text/agent intent
  -> concept/reference images
  -> optional multi-view references
  -> experimental 3D generator
  -> raw mesh/materials
  -> Blender worker
  -> validation + LOD + export
  -> GLB + previews + manifest
```

---

## 13. Manga library subsystem

The manga archive feature is an asset/reference corpus first, not an automatic training pipeline.

### 13.1 Import

- ZIP/CBZ-style archive ingest
- preserve original archives read-only
- page extraction/cache
- duplicate/hash detection
- metadata and rights/use-policy fields

### 13.2 Analysis

Optional local workers may provide:

- panel segmentation
- OCR
- speech-bubble regions
- embeddings/search
- character/reference clustering with user correction
- pose/expression/layout tagging

### 13.3 Reuse

Build:

- reference collections
- Character Profiles
- Style Profiles
- location/object references
- composition/layout references

### 13.4 Training

Training/fine-tuning is separate, explicit, and opt-in. No imported archive is automatically added to a training dataset.

The UI must distinguish:

- reference/search permission
- generation reference permission
- training permission

This is useful even for a single-user local system because it prevents accidental future misuse of mixed-source libraries.

---

## 14. Agent integration

Keep the tool surface small and semantic.

Proposed tools:

- `media.capabilities`
- `media.generate`
- `media.edit`
- `media.inspect`
- `media.pack`
- `media.animate`
- `media.create_3d`
- `media.blender`

M5/game/web presets are parameters, not separate tools.

Example agent flow:

```text
OpenCode: "Add an electric slime enemy to this Godot project"
  -> inspect project conventions
  -> media.generate(profile=game2d.enemy, ...)
  -> Media Forge returns candidates + manifest
  -> media.inspect / deterministic validation
  -> select approved asset
  -> OpenCode writes/imports project code and metadata
```

Agents should receive structured job and asset IDs rather than scraping filenames from textual logs.

---

## 15. Asset library and lineage

Core entities:

- Asset
- AssetVersion
- GenerationJob
- InputReference
- ModelInstall
- WorkerRuntime
- Profile
- CharacterProfile
- StyleProfile
- ProjectLink
- ValidationResult

Asset lineage must support:

```text
master.png
  ├─ eyes-closed v1
  ├─ eyes-closed v2
  └─ smile v1
       └─ game portrait v1
```

A user or agent should be able to ask:

- what generated this file?
- which references were used?
- which version was accepted?
- regenerate with the same seed/settings
- create a variant from an earlier parent

---

## 16. UI

Initial navigation:

```text
Media Forge
├─ Create
├─ Library
├─ Projects
├─ Characters
├─ Profiles
├─ Models
└─ Jobs
```

`Create` is chat/prompt oriented and supports image/video modes, references, and advanced options.

M5/game/web workflows should appear as optional profile shortcuts, not separate applications.

Node graph editing is intentionally out of scope for the primary UI. If advanced pipeline visualization is later useful, expose the internal execution plan read-only first before considering editable graphs.

---

## 17. Internal execution graph

Rejecting a node editor does **not** mean rejecting DAGs internally.

A job may compile into an internal typed execution plan:

```text
NormalizeRequest
  -> SelectModel
  -> AcquireGpuLease
  -> Generate
  -> DeterministicPostprocess
  -> Validate
  -> SemanticReview(optional)
  -> Package
  -> RegisterAsset
```

This makes retries, tracing, cancellation, and future visual inspection possible without exposing model-specific graph authoring to normal users.

Internal nodes are implementation contracts and are not a public workflow format until deliberately versioned.

---

## 18. Security and isolation

Minimum rules:

- non-root service
- no arbitrary host filesystem access
- all project paths go through allowlisted roots and realpath/symlink checks
- prompt text never becomes a shell command
- worker subprocess calls use argument arrays, not `shell=True`
- bounded stdout/stderr and output sizes
- job timeout and cancellation
- temporary directories are per-job and cleaned
- model downloads are explicit unless the administrator enables them
- model sources/checksums/licenses are recorded
- `local_only=true` blocks remote inference at the backend, not merely in UI
- Blender/custom-script execution is separately permissioned

---

## 19. Observability

Every job should expose:

- state and progress
- queue wait
- worker/model selected
- GPU/VRAM estimate and peak when available
- generation duration
- post-process duration
- QA duration
- retries
- outputs/warnings

Do not log secret values or full private source material unnecessarily.

Useful job states:

```text
QUEUED
WAITING_RESOURCE
LOADING_MODEL
RUNNING
POSTPROCESSING
VALIDATING
PACKAGING
SUCCEEDED
FAILED
CANCELLED
```

---

## 20. Model licensing

Model license is part of routing and provenance, not a README footnote.

The registry should allow policies such as:

```text
allow_apache=true
allow_noncommercial=false
allow_research_only=false
```

A project intended for commercial distribution should not silently use a non-commercial model merely because it scored higher in a benchmark.

Asset manifests record the producing model license identifier known at generation time.

---

## 21. Testing strategy

### 21.1 Core tests

- request schema and capability matching
- deterministic routing using fake model registry
- durable job recovery
- cancel/timeout
- resource lease contention
- worker crash handling
- model load/unload lifecycle
- asset lineage
- path containment and symlink escape
- local-only remote-provider denial

### 21.2 Media deterministic tests

- image dimension/format/alpha
- mask containment
- strict unchanged-pixel checks
- sprite-sheet geometry
- manifest schema
- FFmpeg normalized output
- Blender export existence/mesh checks with fixtures

### 21.3 M5 golden tests

Use real template fixtures and assert:

- exact canvas size
- transparent background
- safe regions
- anchor coordinates
- no changed pixels outside the allowed mask
- expected pack filenames

### 21.4 Adapter contract tests

Every model/runtime adapter passes the same capability contract suite using small smoke inputs. Defaults are not promoted until they pass the target hardware benchmark.

---

## 22. Implementation phases

### Phase 0 — Add-on/API skeleton

Goal: establish boundaries before adding heavy models.

Deliver:

- addon manifest and lifecycle contract
- standalone Media Forge service
- ControlDeck route/health integration
- API/job schemas
- durable job store
- asset library + sidecar manifest
- fake worker for tests
- capability/model registry
- resource scheduler skeleton
- local-only enforcement

Exit criterion: an agent can submit a fake generation job and receive a registered asset through the same API later used by real models.

### Phase 1 — General local image generation

Deliver:

- AMD/ROCm image worker baseline
- Diffusers adapter
- native adapter interface
- one fast local image model promoted after benchmark
- text-to-image
- references/edit where supported
- Create UI
- thumbnails/library/history
- image deterministic validators

Candidate first benchmark: FLUX.2 [klein] 4B.

Exit criterion: general image generation works without M5/game presets and without cloud services.

### Phase 2 — Editing + M5 + 2D/Web asset profiles

Deliver:

- strict masked editing
- multi-reference routing where supported
- semantic VLM review with bounded retry
- M5 profiles/validators/package exporter
- 2D game profiles
- sprite/atlas deterministic packer
- web asset profiles
- Character Profile/reference collections
- agent tools for OpenCode/Codex/OMO

Exit criterion: current M5 companion image work can be performed through Media Forge, and a coding agent can request and place a 2D asset pack.

### Phase 3 — General video/animation

Deliver:

- video runtime adapter
- FFmpeg worker
- T2V/I2V baseline
- keyframe/video-edit capabilities when available
- job progress/cancellation for long jobs
- animation-oriented profiles

Candidate benchmarks: Wan2.2 and LTX-2 families.

Exit criterion: ordinary chat-driven video creation works without requiring a game/M5 recipe.

### Phase 4 — Blender production worker

Deliver:

- Blender background worker
- typed operations for clean/LOD/material/render/export
- 3D asset manifest and previews
- OpenCode/agent Blender tool
- deterministic validation

Exit criterion: an agent can safely process an existing 3D asset into a project-ready GLB without writing arbitrary Blender Python into the ControlDeck process.

### Phase 5 — Experimental generative 3D

Deliver:

- image-to-3D provider adapter
- reference/multi-view preparation
- raw asset -> Blender production pipeline
- explicit experimental quality labels

Candidate benchmark: Hunyuan3D 2.1 and then-current local alternatives.

Exit criterion: generated 3D can flow through the same asset lineage and validation pipeline, while failures remain isolated from the stable Blender feature.

### Phase 6 — Manga library/studio

Deliver:

- ZIP/CBZ ingest
- page/panel indexing
- local OCR/search/embeddings as optional workers
- reference collections and Character/Style Profiles
- storyboard/panel generation workflow
- explicit rights/training policy metadata
- optional training dataset builder; no automatic training

Exit criterion: owned/authorized archives can serve as a searchable reference corpus and controlled generation source without being silently converted into training data.

---

## 23. Non-goals for the first releases

- clone all ComfyUI nodes
- invent a new model graph ecosystem
- ship every known diffusion/video/3D model
- guarantee perfect 3D retopology from generative AI
- automatically fine-tune on imported media
- let agents execute arbitrary shell/Blender scripts by default
- depend on a single agent framework
- make cloud APIs necessary for core functionality

---

## 24. Decision checklist for accepting a new model/runtime

Before adding a model as a supported default, answer:

1. What capability gap does it fill?
2. Does an existing adapter support it, or does it require a special runtime?
3. Does it run reliably on target AMD/ROCm hardware?
4. What is its actual VRAM/runtime envelope on that hardware?
5. What license applies to weights and intended use?
6. Can its outputs carry full provenance?
7. Does it improve enough over installed alternatives to justify disk/maintenance cost?
8. Can it be cancelled and isolated as a worker job?
9. Are its required custom nodes/kernels maintainable?
10. Can the model be removed later without changing public APIs?

A "no" to #10 is an architecture smell.

---

## 25. Baseline architectural decision

Adopt Media Forge as:

> **A local-first, capability-routed media asset service and ControlDeck add-on, with generic image/video APIs at its core; deterministic production/validation around generative models; optional domain profiles for M5Stack, 2D games, web, manga, and 3D; and thin integrations for coding agents rather than agent-specific media stacks.**

This baseline intentionally prioritizes replaceability, reproducibility, strict asset constraints, GPU resource management, and useful project-ready outputs over exposing every model parameter or node graph.

---

## 26. Current upstream references (non-normative)

These links are references for initial adapter evaluation only. The architecture must remain valid if every model listed here is replaced.

- FLUX.2 official inference repository: https://github.com/black-forest-labs/flux2
- Qwen-Image official repository: https://github.com/QwenLM/Qwen-Image
- Wan2.2 official repository: https://github.com/Wan-Video/Wan2.2
- LTX-Video / LTX-2 official repository: https://github.com/Lightricks/LTX-Video
- Hunyuan3D 2.1 official repository: https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1
- Blender Python API: https://docs.blender.org/api/current/
