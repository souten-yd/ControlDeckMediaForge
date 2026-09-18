# M3b — fixed-view candidate refinement

Date: 2026-09-18. Source implementation and controlled lifecycle acceptance.
Live Host text/vision, installed/MCP/OpenCode and semantic quality: NOT TESTED.

## Behavior and boundaries

`scene.edit` gains optional publish_mode=candidate, creating a new owner-scoped
scene with source lineage while retaining the original head. Default advance and
legacy retry payloads are preserved. The existing scene Job manager adds
`media.scene.refine`: fixed clay observations, at most three image-review issues,
a typed local proposal, candidate generation and actual before/after image sheets.
The initial proposal vocabulary is mesh.sections.set and mesh transform.set;
other required repairs remain explicit instead of triggering arbitrary scripts.

One Job runs at most 1–6 attempts (default 3). Two consecutive non-improvements
stop. An evidence-valid improved comparison can select a candidate only when
bounded mesh IDs and edge diagnostics do not regress. Worse/unchanged/inconclusive
or structurally regressed candidates remain inspectable without being selected.
The original head never advances. Selected candidates remain advisory:
asset_approval=not_granted, shape_gate=advisory_only, surface/deformation NOT TESTED.

The existing Host capabilities own text/vision routing and resource admission.
The renewed child identity is retrieved before each call. At most four labelled
sheets carry baseline, candidate and up to five reference images including a
distinct canonical. Hashes, image regions, bounded model output, candidate source
lineage and comparison/final report ZIPs remain under existing Asset/provenance.

Existing scene task records checkpoint published candidates/evidence. Failure,
cancel and service stop retain partial progress, fail closed, and release active
local work; restart fails active refinement stages. Explicit identical-input
retry is a new Job. Actual Host provider cancellation remains a separate gate.

## Verification

Controlled gateway tests exercise improvement/non-improvement selection, the
2-failure stop, current-head and prior-byte preservation, unknown issues/targets/
evidence, unavailable AI, geometry regression overriding a model's improvement,
canonical references within the four-image limit, canceled planning and retry,
permissions and restart. Fake fixtures initially used the wrong image size and
an observation-only fake validator; those harness errors were corrected.
Tests also found two product issues: checkpoint omitted required stage, and
terminal stage updates erased partial progress. Both were corrected and rerun.

The actual script creates a curved T-Rex using Blender 4.5.13 and runs the loop
with **controlled model responses**. Blender, source edits, exports, four-view
renders, image payload preparation, SHA checks, provenance and persistence are
real. Responses and improvement decisions are not real inference or visual truth.

| Case | Observed wall time | Attempts | Published Assets |
|---|---:|---:|---:|
| Worse then unchanged: retain original and stop | 7.718 s | 2 | 20 |
| Improved fixture response: select separate candidate | 4.942 s | 1 | 13 |

The original head/source SHA were retained in both cases. Three distinct
candidate scenes were created; actual image payload hashes were recorded.
Runtime references reached zero and recipe/observation/review staging was empty.
Actual Host inference calls: **0**. semantic_review: **NOT TESTED**.

Evidence: `MF3DS-M1-SixVertex-20260918/evidence/refinement-source/` includes report,
request/response-branch trace, Blend/GLB/PNG/comparison/final ZIPs and
`run_refinement.py`. It deliberately creates controlled responses locally and
must never be reported as a real local-LLM/VLM run. Final full suite results are
recorded in implementation-status.

Remaining: real Host inference/cancellation, signed installed discovery and MCP,
consistent generated references, accepted clay quality, surface/bake, weights/IK,
clips/viewer and the repeated three-family comparison. Installed 0.28.84 and
original project files remain unchanged.
