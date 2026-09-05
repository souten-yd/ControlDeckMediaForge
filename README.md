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

## Current implementation

MF0-0 through MF0-7 / G0 are complete: the isolated service, durable fake-worker
jobs, assets/provenance, embedded workspace, ControlDeck Jobs/Broker/files,
Workflow, Context Action, and real OpenCode tool discovery/call have passed their
real-process acceptance checks. G1 local image generation is complete with a
measured FLUX.2 Klein 4B automatic route, real R9700/ROCm evidence, and the
verified GitHub release-bundle standard installation path. Public contracts are
frozen at G1; later goals must extend them without breaking existing consumers.
See `docs/implementation-status.md`.

## Run locally

```bash
./mf.sh doctor
./mf.sh serve
./mf.sh model list
./mf.sh blender status
```

Open <http://127.0.0.1:9130/>. The service binds to loopback only in G0.

Normal installation uses ControlDeck's trusted `release-bundle` Optional Feature
provider and a verified GitHub Release artifact. Installing `addon.json`
directly and running this source tree remain developer workflows, not the
Settings default. ControlDeck remains the lifecycle, identity, grant, Jobs
bridge, and resource-broker authority; this repository contains all
Media-specific code.

Model downloads are explicit. The adopted local model can
be fetched to the shared Hugging Face cache with
`./mf.sh model download flux2-klein-4b`. The command pins the repository revision
and excludes the redundant single-file checkpoint.

G8 uses a separately provisioned, revision-pinned Blender runtime. It is never
installed into the core venv or ControlDeck. Build it explicitly with
`./mf.sh blender build`; inspect it without changing state with
`./mf.sh blender status`. Media Forge now resolves that existing runtime through
its own versioned registry and shows read-only Blender diagnostics in Settings.
Settings-based install/update/repair/remove and the browser GUI pack remain
planned work; their absence does not disable image features.

## Test

```bash
./mf.sh test
```

Public contracts are documented in [`docs/api.md`](docs/api.md). Current evidence and untested areas are in [`docs/implementation-status.md`](docs/implementation-status.md).

## Planning documents

- [Integrated 3D Studio](docs/design-3d-studio.md) — phased extension of MediaForge's shared image/3D workspace. The compatibility baseline and read-only Blender runtime resolver/diagnostics are implemented; asset viewer, texture workflows, OpenCode authoring, server-side Blender GUI, and Settings-based lifecycle operations remain planned. Implementation and releases stay in this repository; Blender runs in isolated runtime/session environments.
- [3D implementation plan](docs/implementation/g8-3d-studio-plan.md) — phased work, compatibility gates, real-machine acceptance and coding-agent handoff.
- [3D development and release rules](docs/development-release-3d-studio.md) — existing MediaForge distribution/signing, reference practices from ControlDeck/SonicForge and evidence requirements.

- [Base plan](docs/base-plan.md) — general Media Forge product/runtime architecture and implementation phases.
- [ControlDeck integration plan](docs/controldeck-integration-plan.md) — **normative for add-on integration, enabled-only UI/UX, ControlDeck Jobs integration, and shared AI/GPU resource management**. Where the older base plan describes a Media-Forge-owned global resource scheduler, this integration plan supersedes it: ControlDeck's shared AI Resource Broker is the platform-level admission/queue/lease authority, while Media Forge workers retain only local safety/concurrency guards.

The matching ControlDeck host-side plans are maintained in the ControlDeck repository as `docs/design-addon-platform-v2.md` and `docs/design-ai-resource-broker.md`.

Implementation order and real-machine acceptance gates are documented in
[`docs/implementation/README.md`](docs/implementation/README.md).
