# M5 — local weights and two-bone IK baking

Source on `ux1/3d-deformation-tools`, parent PR543/c4d21a8. Existing typed
skeleton/binding and immutable recipes are extended with weight set/smooth/
normalize and fixed leg IK baking. No new skeleton database, Host executor,
model weights, runtime or deployed service changes.

## Actual Blender 4.5.13

```bash
PYTHONPATH=backend:. .venv/bin/python /tmp/mediaforge-deformation-live-20260918.py
PYTHONPATH=backend:. .venv/bin/python /tmp/mediaforge-deformation-negatives.py
```

Root `/tmp/mediaforge-deformation-20260918-8wck2ls7`. A continuous 146-vertex limb
is auto-bound to upper/lower/foot deform bones. Binding: 0.440 s; explicit local
weights + three smoothing iterations + normalization: 0.424 s; 24-frame IK
clip bake: 0.438 s. The original head stays on the corrected rest revision;
pose/IK are separate candidates.

Actual source Blend inspection asserts all 98 unselected vertices' weights and
all cage positions are retained, selected weights change, maximum influences 2,
maximum normalization error 2.9802322387695312e-08. The bent front/side images
were rendered and the side image inspected; this is a simple limb deformation
fixture, not a finished character or collision/collapse approval.

The 25 evaluated IK samples have maximum target error 0.00009478896974323901 m,
zero retained constraints and exact loop endpoint position match. Actual Blender
reimports the GLB and evaluates the foot joint at all 25 frames: maximum source
versus reimport difference 0.0000004789509216973468 m. The foot joint is a real
third bone, avoiding assumptions about an importer's displayed bone lengths.
`inspection.json` retains the measurements.

Actual stale weight selection and unreachable IK fail with readable fixed
reasons, no new Assets/head change, zero runtime references and empty staging.

## Failures found and fixed

The first straight-chain IK solve missed the endpoint by about 0.1473 m. Direct
inspection of the fixed worker found a solver initialization singularity. A
fixed 0.1-radian knee seed resolves it; every solved and baked frame still passes
the original 1 cm gate. The tolerance was not relaxed. API reference:
[Blender Bone local/pose conversion](https://docs.blender.org/api/4.3/bpy.types.Bone.html).

An initial test decorator typo and diagnostic-script field/prefix mistakes were
corrected. They are not counted as successful runs. Final live scripts and logs
are retained in the evidence directory.

## Remaining gates

This operation solves one leg's target position, not foot orientation or a
coordinated walk. Anatomy/part-to-bone design stays explicit in the recipe and
ReferenceSet. No completed T-Rex/quadruped joint quality, cloth transfer, root
motion, installed new-tool MCP/OpenCode or viewer playback acceptance is claimed.
Weights summing to one and target accuracy cannot prove good deformation.

Evidence: `/data1tb/ControlDeck/CodeDEV/MF3DS-M1-SixVertex-20260918/evidence/deformation-source`.

Full gate `./mf.sh test`: exit0, 2150 passed / 2 warnings / 232.85 s.
No product changes after this gate.
