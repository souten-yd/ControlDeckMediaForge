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

The G0 slice provides the Add-on/API experience with a deterministic CPU-only fake worker. The fake worker runs in a separate process and writes assets through the same job, validation, library, provenance, and lineage contracts that real image workers will use.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
MEDIA_FORGE_DATA_DIR="$PWD/.local-data" .venv/bin/media-forge
```

Open <http://127.0.0.1:9130/>. The service binds to loopback only in G0.

Install [`addon.json`](addon.json) through ControlDeck's Extensions screen to expose the workspace inside the ControlDeck shell. ControlDeck remains the lifecycle, identity, grant, Jobs bridge, and resource-broker authority; this repository contains all Media-specific code.

## Test

```bash
.venv/bin/python -m pytest
```

Public contracts are documented in [`docs/api.md`](docs/api.md). Current evidence and untested areas are in [`docs/implementation-status.md`](docs/implementation-status.md).

## Planning documents

- [Base plan](docs/base-plan.md) — general Media Forge product/runtime architecture and implementation phases.
- [ControlDeck integration plan](docs/controldeck-integration-plan.md) — **normative for add-on integration, enabled-only UI/UX, ControlDeck Jobs integration, and shared AI/GPU resource management**. Where the older base plan describes a Media-Forge-owned global resource scheduler, this integration plan supersedes it: ControlDeck's shared AI Resource Broker is the platform-level admission/queue/lease authority, while Media Forge workers retain only local safety/concurrency guards.

The matching ControlDeck host-side plans are maintained in the ControlDeck repository as `docs/design-addon-platform-v2.md` and `docs/design-ai-resource-broker.md`.
