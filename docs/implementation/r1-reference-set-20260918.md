# R1 — immutable reference package and scene binding

Date: 2026-09-18. Scope: source storage/binding implementation. Generated-view
consistency, signed installed acceptance and actual OpenCode use remain NOT TESTED.

## Implementation

The existing `media.generate` / `asset.pack` Job accepts profile `3d.reference_set`.
No new Job manager, Asset database, Host route, model or inference runtime is added.
Two to four unique labelled views (front and side required), an optional canonical
Asset, declared scale/axes, part hierarchy, image landmarks and source notes become
a bounded reproducible ZIP Asset. Source image hashes, provenance and licenses
are recorded; parent Assets are protected by the existing lineage graph.

The package contains a versioned manifest and normalized PNGs. Source bytes and
provenance are checked; EXIF orientation is normalized and metadata removed.
The input/output bounds and API are in [the API reference](../api.md).
Packaging always leaves `needs_review / not_reviewed / unverified`. No image
generation or visual consistency judgment occurs in this slice.

Optional `reference_set_asset_id` on scene create/edit and workflow forms pins a
verified package as a `reference_set` dependency. Omission/null on edit retains
the current set. Replacement changes the new revision only. Existing owner and
current-revision checks still apply. Both source and preview provenance retain
the package hash; the preview's parent is its source, preserving existing lineage.
Retry payloads omit the new null field, preserving older durable requests.
Public schema IDs/descriptions and existing operations remain intact.
Scene backup restore regenerates Library IDs but preserves exact ZIP bytes.
A bounded `reference_set_origin` provenance record retains original image IDs
and hashes; the embedded images remain self-contained. Repeated backup/restore
does not rewrite the reference manifest or make its historical IDs current IDs.

CPU packaging checks cancellation between bounded image/ZIP steps. Task shutdown
drains its writer before staging cleanup, including repeated cancellation.
The existing durable Job restart and terminal transport mechanisms are reused.

## Measurements

Actual isolated Uvicorn process, HTTP import → Job → status → Asset download,
using the existing dinosaur blockout's front/side/three-quarter PNGs as fixtures.
These are rendered blockout images, not newly generated or quality-approved
reference designs. Source uses a separate data directory; installed 0.28.84 is unchanged.

| Measurement | Observed result |
|---|---|
| First HTTP pack | 0.478 s |
| Same-input repeat | 0.473 s |
| ZIP size | 1,596,441 bytes |
| ZIP SHA-256 | `b635a35caf268feb15c9ebe584a3c22115c71ebeb33ce2b91e8daf264b547036` |
| Repeat bytes | Identical SHA-256 |
| Actual Blender 4.5.13 scene edit/binding | 0.438 s |
| Previous revision | Original empty dependency list retained |
| New source/preview | Reference hash present in provenance; source is package child |
| Runtime/staging | Runtime reference count zero; recipe staging empty |

The acceptance script initially lacked `.` in PYTHONPATH and could not start;
the next attempt's assertion incorrectly expected preview → package direct
parentage. It was corrected to the existing preview → source → package graph.
The final complete run passed; no product change was needed for these harness errors.
The owned HTTP process ended after SIGTERM (exit -15); no installed service restart.

An actual Store reopen with a running reference-pack Job changed it to
`failed / service_restarted`; a canceled queued Job remained canceled; Assets=0.
Automated checks cover malformed specs, geometry declarations, source corruption,
input mapping, deterministic ZIP/metadata, malformed archives with valid outer
digests, visual-approval spoofing, cancellation/drain, owner/conflict/history and
retry of a legacy payload. The full test count is recorded in implementation-status.
Additional compatibility inspection found that restored Assets use `scene.restore`
provenance, so the original pack-only check would reject them. The bounded origin
record fixes this without rewriting exact backup bytes. Two actual backup/restore
generations followed by real Blender edits passed, retaining the ZIP hash.

Evidence is retained in project `MF3DS-M1-SixVertex-20260918/evidence/reference-source/`:
request, report, repeat ZIPs, reference-bound GLB, restart report, HTTP log and
reproduction script. Run with `PYTHONPATH=backend:. .venv/bin/python run_live.py`
from the source worktree; it creates a fresh isolated scratch directory.

## Remaining acceptance

R1 storage is available in source. Canonical-conditioned image generation and
consistent four-view reference acceptance are not implemented/verified by this
slice. M2b must consume actual images and produce bounded evidence-based issues;
the immutable package itself must never be silently promoted to approved.
Signed installed/MCP/OpenCode use, VLM review, curves, improved deformation and
the final dinosaur/quadruped/prop comparisons remain separate gates.
