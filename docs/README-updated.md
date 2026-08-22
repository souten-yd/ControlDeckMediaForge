# ControlDeck Media Forge

ControlDeck Media Forge is a **local-first, general-purpose media generation add-on** for ControlDeck.

The project is not intended to be a simplified ComfyUI clone. Its primary interface is chat/agent/API driven: users and coding agents request the media they need, while Media Forge selects an appropriate local model/engine, runs generation or editing as a managed job, validates the result, and returns reusable assets with provenance.

Primary targets:

- General image generation and image editing
- General video / animation generation
- Asset creation from OpenCode, Codex, OMO, and other coding agents
- M5Stack companion assets with strict pixel/alpha/layout constraints
- 2D game assets, sprite sheets, UI, backgrounds, VFX, and engine-ready packs
- Web/app assets
- Character/style consistency and reusable asset libraries
- Blender-assisted 3D asset production
- Manga archive indexing and, where the user has the necessary rights, opt-in reference/training workflows

The system is designed around **capabilities, not model names**. Models and runtimes are replaceable workers/adapters; recipes/presets are optional constraints layered on top of the same general media APIs.

ControlDeck integration is also deliberately generic: Media Forge remains a separate add-on/runtime, while ControlDeck provides reusable extension points for embedded UI, scoped identity/files/projects, Jobs, workflow/agent contributions, notifications, and a shared AI/GPU resource broker. Media-specific UI/tools are exposed only while the add-on is enabled and authorized.

## Planning documents

- [Base plan](docs/base-plan.md) — general Media Forge product/runtime architecture and implementation phases.
- [ControlDeck integration plan](docs/controldeck-integration-plan.md) — **normative for add-on integration, enabled-only UI/UX, ControlDeck Jobs integration, and shared AI/GPU resource management**. Where the older base plan describes a Media-Forge-owned global resource scheduler, this integration plan supersedes it: ControlDeck's shared AI Resource Broker is the platform-level admission/queue/lease authority, while Media Forge workers retain only local safety/concurrency guards.

The matching ControlDeck host-side plans are maintained in the ControlDeck repository as `docs/design-addon-platform-v2.md` and `docs/design-ai-resource-broker.md`.

## Implementation instructions

- [Implementation index](docs/implementation/README.md) — reading order, goal list, and the rules that apply throughout.
- [Goal roadmap](docs/implementation/goal-roadmap.md) — G0 through G10, organised as user-visible goals rather than technical layers.
- [MF0-0 environment](docs/implementation/mf0-0-environment.md) — runtime isolation from ControlDeck, shared caches, provisioning, and safe removal. Do this first.
- [MF0 add-on core](docs/implementation/mf0-addon-core.md) — G0: become a working add-on with a fake worker and no heavy dependencies.
- [Host load-profile fix](docs/implementation/host-load-profile-fix.md) — a prerequisite for G7 that is implemented in the ControlDeck repository.

Planning documents describe what to build and why. Implementation instructions describe the order of work and the evidence required before a step counts as done. Change the planning documents first when a design decision changes.
