# M3a — bounded curves and local mesh selectors

Date: 2026-09-18. Source implementation; installed/OpenCode and deformation
acceptance remain NOT TESTED. Parent slice: M2b / PR #540 / 4f18ef1.

## Implementation

Five additive recipe operations generate elliptical lofts/sweeps, replace a fixed
number of control sections, bridge two open boundary loops and add bounded
Catmull-Clark subdivision. Core validates compact controls independently of the
trusted Blender worker; the core never imports the worker's geometry generator.
The worker checks controls, generated degeneracy, geometry growth and selectors
before publication. Explicit caps produce consistently wound edge-closed shells;
this does not prove absence of intersections or suitable deformation topology.

Actual mesh positions/face indices yield a float32 SHA256. Recipe results,
provenance and the existing snapshot expose bounded mesh facts and valid curve
controls. Section edits require that hash and unchanged control count, retaining
vertex/face ordering, UVs and weights. Old revisions remain immutable. Imported
or manually changed controls are not silently treated as current. Facts are a
bounded partial projection; absence is not a passed audit.

Bridge verifies both hashes and equal-sized boundary loops on independent
unweighted static meshes without modifiers. It preserves original faces,
materials and UVs, consumes the second ID and ends procedural section editing.
New joint UVs require explicit projection. Unsupported custom attributes fail
rather than disappear; Blender's internal edit-selection flags may be discarded.
Subdivision growth counts triangulated expansion conservatively (including
triangle faces) and fixed observation accepts the same bounded settings.

The worker is shipped in the existing Blender pack. There is no external addon,
Python execution API, second Jobs/Asset system, model install or Host change.
The guide/API and frozen schemas are extended additively.

## Actual Blender evidence

The reproduction script creates isolated Store/SceneWorkspace state using the
installed Blender 4.5.13 binary. It runs typed requests directly through source
SceneWorkspace, validates actual GLB exports and renders four 512 px clay views.
It does not simulate OpenCode or claim that a local LLM authored these fixtures.
The initial complete run generated a continuous curved T-Rex, quadruped and prop,
modified the torso with preserved topology, rejected its stale hash, retained
old source bytes, and bridged two open meshes into a closed one.

Initial observed times: T-Rex create/export 0.525 s / four-view 2.167 s;
quadruped 0.454 / 1.919 s; prop 0.430 / 1.785 s; joint 0.427 / 1.790 s.
The joint cage had 130 vertices, 256 triangles and zero boundary,
nonmanifold or inconsistently wound edges. Five four-view sets yielded 20 PNGs.
The actual images were inspected. The T-Rex silhouette is curved rather than a
box assembly, but face details, intersections at limbs and deformation are not
accepted. Quadruped/prop are generic operation fixtures, not finished game assets.

Adding explicit protection against losing unsupported attributes exposed an
actual regression: Blender's `.select_vert`, `.select_edge`, `.select_poly`
flags were rejected. Read-only inspection of the real saved meshes identified
them. The allowlist now permits those editing flags. An in-progress full test
was stopped for the fix, not counted as a pass; corrected actual and full runs
are recorded in implementation-status and evidence.

Checks assert immutable prior source SHA, changed cage hash with equal topology,
current-head retention after failed edits, runtime-reference release and empty
recipe/observation staging. Execution and geometry checks are separate from
semantic quality and deformation.

## Remaining acceptance

Signed installed operation discovery, real OpenCode/local-LLM authoring,
consistent generated references, actual VLM diagnosis, two-non-improvement
iteration stopping, final UV/PBR/bake, weights/IK/clips and viewer playback remain
separate work. The original primitive T-Rex and installed MediaForge 0.28.84
have not been replaced. M3a source does not complete the entire plan.

## Corrected actual run

- curved-trex: create/export 0.491 s; four-view 2.165 s
- curved-trex-edited: create/export 0.472 s; four-view 2.169 s
- curved-quadruped: create/export 0.454 s; four-view 1.912 s
- curved-prop: create/export 0.428 s; four-view 2.753 s
- joint-closed: create/export 0.427 s; four-view 1.787 s

All five cases completed after the selection-attribute correction, including
stale-selector rejection and zero live runtime references/staging entries.
Evidence: `MF3DS-M1-SixVertex-20260918/evidence/curves-source/`, containing actual
Blend/GLB/PNG, requests, hashes, full report and `run_curves.py`. T-Rex preview
files also reside in `MF3DS-Trex-20260918/curve-prototypes/`; originals are retained.

The full contract test then caught ambiguous `path` naming for sweep coordinates.
The new, not-yet-released field is `path_points`; the ban on path/script/operator
inputs remains unchanged. The matching source and real Blender run passed again.
Final-contract evidence is in `curves-source/final-contract/`.

- curved-trex: create/export 0.505 s; observation 2.198 s
- curved-trex-edited: create/export 0.490 s; observation 2.165 s
- curved-quadruped: create/export 0.476 s; observation 2.037 s
- curved-prop: create/export 0.455 s; observation 1.808 s
- joint-closed: create/export 0.441 s; observation 1.807 s

Actual Blender GLB re-import retained the encoded triangle counts and finite
coordinates in all five files:

- curved-prop.glb: 49976 bytes, 2 meshes, 2688 triangles, 0.037 s
- curved-quadruped.glb: 100028 bytes, 5 meshes, 6336 triangles, 0.012 s
- curved-trex-edited.glb: 233752 bytes, 9 meshes, 12640 triangles, 0.020 s
- curved-trex.glb: 233748 bytes, 9 meshes, 12640 triangles, 0.020 s
- joint-closed.glb: 20480 bytes, 1 meshes, 1088 triangles, 0.002 s
