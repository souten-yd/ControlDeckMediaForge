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

See [docs/base-plan.md](docs/base-plan.md) for the initial architecture and implementation plan.
