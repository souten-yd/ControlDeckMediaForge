# G9 texture and partial-view audit — 2026-09-20

The user reported incomplete geometry and apparently missing image textures.
The earlier Vulkan generation/Library success is a delivery acceptance, not
acceptance of complete geometry or faithful color/pattern reproduction.

## Artifact evidence

Live installed HTTP downloads of the source PNG, TRELLIS GLB
`asset_1171977ee90444ef873538a86f56255e` and Pixal GLB
`asset_d5864d5cce8449ce8f2ff27ec37cfe69` match their registered SHA256 values.
Both GLBs have a base-color texture, metallic/roughness texture, UV attributes
and material assignments using `EXT_texture_webp`.

Extracting the embedded image bytes and decoding them with Pillow gives:

| Image | Dimensions | RGB observation |
|---|---|---|
| Actual input | 700×700 | almost achromatic, range 192–221 |
| TRELLIS base color | 1024×1024 | grayscale 203–204, standard deviation 0.100741/channel |
| Pixal base color | 4096×4096 | nearly gray, mean about 229.771, standard deviation about 0.977/channel |

The decoded source and texture images were visually inspected. The source is a
low-contrast gray mechanical housing, not a colored or patterned reference.
Both base-color and metallic/roughness image byte hashes exactly match their
respective retained native evaluation GLBs, before Blender import/publication.
Thus the Library/Blender boundary did not discard these textures. The trained
Pixal PBR values captured before UV baking are also nearly uniform (sampled
RGB about 0.899–0.905). Presence of two images alone was an insufficient color
quality check. This input cannot establish correct color/pattern generation;
it also does not prove that the input alone explains the near-uniform result.

The prior independent four-view renders already show roughness/holes on unseen
surfaces. A camera fix does not repair that geometry. Complete-object fidelity,
colored-reference reproduction and animation readiness remain NOT ACCEPTED.
No learned model or image was silently replaced. This initial comparison reused
existing outputs; the additional colored-input run below is separately identified.
Existing Asset bytes and runtime receipts are preserved.

## Reproduced viewer clipping

In actual authenticated Host Chrome 151, the 320px Library viewer clips the
Pixal model at initial open and after pressing 「全体」. Its bright model pixels
reach x=0 for 179 rows (bounds x=0–308); the same 1280px path fits correctly.
This is a separate display defect that makes the output appear more incomplete.

The fit camera distance used only vertical field of view. The correction uses
the smaller horizontal/vertical angle so the bounding sphere fits both canvas
dimensions. The viewer bundle and content hash are regenerated; no mesh,
texture, model, inference or public contract is changed.

A candidate viewer response overlay on the actual Host passes at 320/1280px.
At 320px, initial open and 「全体」 show bounds x=47–230, with zero model pixels
on either side edge, without zoom-out clicks. Desktop pixel bounds and count
are identical to the previous build. Model counts remain 935214 triangles,
one mesh/material, zero animation, and the material mode is active. Page/HTTP/
request errors and horizontal overflow are zero. Screenshots were inspected.
The overlay is source acceptance only; signed installation is still pending.

Evidence: installed feature data `maintenance/g9-texture-audit-20260920/`:
`inspection.json`, `native-textures.json`, extracted original texture bytes,
`before-*`, `candidate-*`, and the private ordinary-session browser helper.
No credentials are logged or stored in these reports.

## Release and remaining checks

0.28.91 is prepared for the viewer fix. Final `./mf.sh test`: **2279 passed,
2 warnings, 272.46 seconds, exit 0**. The first full run retained two failures:
this change had not yet updated the viewer lock hashes, and an unchanged Blender
registry repair test observed staging cleanup after terminal-state publication.
The lock is now regenerated. The unchanged publication-lock suite, viewer lock
check and enabled build-runtime signing checks all pass (10 focused cases); the
full rerun also passes. No assertion or unrelated runtime code was weakened.
The first run's three signing skips were eliminated by using the existing isolated
MediaForge bundle-build runtime in this worktree.

Normal PR merge, signed package verification/update and post-update/restart
browser checks are pending. The quality limitations remain after the viewer fix.

A separately identified color/pattern evaluation uses the existing pinned
TRELLIS showcase `assets/showcase/chest/chest.png` (wood grain, brown panels,
gold/dark metal). The source was visually inspected and imported by the ordinary
MediaForge image API as `asset_5a43f6f825d242fcb9fececaa85792b4`. TRELLIS 512,
seed 42 was submitted through the actual authenticated Host agent-tool API;
Job `job_73a467fb80ae43b2acdb964b4fc033a7` is running under genuine resource
admission. Terminal color/geometry acceptance and Pixal's same-input comparison
are pending. This does not reuse the gray input as proof of color fidelity.
