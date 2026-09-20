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
surfaces. A camera fix does not repair that geometry. Complete-object fidelity
and animation readiness remain NOT ACCEPTED. Color/material delivery is
separately measured with the reference below.
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
The overlay is source acceptance. Signed installation and restart acceptance
below independently reproduce the same result without a response overlay.

Evidence: installed feature data `maintenance/g9-texture-audit-20260920/`:
`inspection.json`, `native-textures.json`, extracted original texture bytes,
`before-*`, `candidate-*`, and the private ordinary-session browser helper.
No credentials are logged or stored in these reports.

## Release and remaining checks

0.28.91 includes the viewer fix. Final `./mf.sh test`: **2279 passed,
2 warnings, 272.46 seconds, exit 0**. The first full run retained two failures:
this change had not yet updated the viewer lock hashes, and an unchanged Blender
registry repair test observed staging cleanup after terminal-state publication.
The lock is now regenerated. The unchanged publication-lock suite, viewer lock
check and enabled build-runtime signing checks all pass (10 focused cases); the
full rerun also passes. No assertion or unrelated runtime code was weakened.
The first run's three signing skips were eliminated by using the existing isolated
MediaForge bundle-build runtime in this worktree.

PR [589](https://github.com/souten-yd/ControlDeckMediaForge/pull/589) merged as
`fc6e0c977af816d096038e82d66242077abb57a5`. The signed
[0.28.91 release](https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.28.91)
was built from that exact merge, verified against the Host's trusted publisher
key, independently downloaded and verified again. Canonical manifest/signature,
tamper rejection, SHA sidecar, six-member archive and embedded viewer hash pass.
The 31,819,207-byte artifact SHA256 is
`29da67e4937ce77c953ea804a6758f9291b6717e4bd7b580c44247dbdac078a8`.
Fresh-directory package smoke passes in 0.865923 seconds: unauthenticated setup
and unadopted generation remain unavailable, rather than becoming false success.

`./deck.sh feature update media-forge` installed 0.28.91 with 0.28.90 retained.
The actual `current` target, effective API HTTP200 and healthy service agree.
The served viewer SHA256 is
`3a86ca91deb71ba0be7ea8b89a01d08052914f600b6cfd7898fb57b2a32e8c88`.
All 16 database tables, 2740 asset-file size/mtime records and Blender registry
hash match immediately before/after update. A fresh idle snapshot and restart
(PID2852320 → 2853139) preserve them again. The Pixal adoption receipt is unchanged;
TRELLIS512/Pixal1024 remain adopted experimental engines. Both existing mechanical
GLBs and the new TRELLIS color blend/GLB pass HTTP content hash verification.

Actual installed Host browser checks, without overlay or manual zoom-out, pass
before and after restart at 320/1280px. Initial open and Fit both reproduce
x47–230 / 20073 bright model pixels at 320px, zero left/right-edge pixels;
desktop remains x262–687 / 107165 pixels. Page/HTTP/request errors and horizontal
overflow are zero. The quality limitations remain after the viewer fix.
Release evidence: installed feature data `maintenance/release-0.28.91-20260920/`
(`artifacts/verification.json`, `downloaded/verification.json`, `clean-smoke.json`,
`state/`, `restart/`, `installed-check.json`, `restarted-check.json`).

## Colored-reference generation

A separately identified color/pattern evaluation uses the existing pinned
TRELLIS showcase `assets/showcase/chest/chest.png` (wood grain, brown panels,
gold/dark metal). The source was visually inspected and imported by the ordinary
MediaForge image API as `asset_5a43f6f825d242fcb9fececaa85792b4`. TRELLIS 512,
seed 42 was submitted through the actual authenticated Host agent-tool API;
Job `job_73a467fb80ae43b2acdb964b4fc033a7` succeeded in 183.317879 seconds,
including native generation 167.717147 seconds. Genuine Host lease
`2e7b8dcb-974e-4954-a7a3-821a8d33ac01` reserved 9,522,905,088 bytes and is released.

- Name: `TRELLIS 色・模様検証 木製宝箱`.
- Source: `asset_5a43f6f825d242fcb9fececaa85792b4`;
  normalized input SHA256 `42381be89464914529c73dc2ebd25ef953d2099e62f851613a23421cb3d53723`.
- Blend: `asset_66b3820e158c4be7809b26c76fea5ce8`, 13,552,257 bytes,
  SHA256 `bee723480206f87d503b7eff1974da334499f8d2478cf2c772d84b5699ee2c87`.
- GLB: `asset_83b93b9570394d069ff3c16f6232e329`, 5,368,720 bytes,
  SHA256 `8ad7563a4503a038425bd30b10508cc0f2244018040a57cf901ed09a0582f99a`.

The existing Scene/Library contains both assets and their source lineage.
Independent Blender4.5.13 import and four CPU-rendered views pass: 108709 vertices,
135930 triangles, one mesh/material, two embedded 1024² textures, finite coordinates,
zero bones/actions. The base texture RGB ranges are 17–193 / 0–164 / 0–123;
channel standard deviations are 24.66428 / 25.55253 / 25.26202. Atlas, four renders
and installed Host 320/1280px screenshots were visually inspected: brown wood
grain, gold trim and dark metal bands remain visible. Viewer errors/overflow are
zero. This establishes color/material delivery for this reference. Fine-grain
detail is smoothed, hardware shapes are approximate, and the unseen sides are
inferred; exact reconstruction, watertightness and animation readiness are not
accepted from these images. Generation provenance correctly records 0.28.90,
the version used before the viewer-only update.

Pixal's same-input comparison succeeded on installed 0.28.91:
Job `job_409a09766ec442629eb3d4a75ef5039a`, Host child `eb3b6aad5c0d`,
1024/seed42. Its prepared manifest matches the same normalized source SHA256;
the actual background-removed/framed image was inspected and retains the entire
colored chest. Total Job elapsed time is 1105.231606 seconds (18m25s), generation
facts 1078.385081 seconds including CPU preprocessing 79.932288 seconds.
Subsequent neural inference uses Vulkan device1 / float32; CPU preprocessing and
surface processing are distinct stages. Genuine Host gpu0 lease
`1c0de4ef-91cf-47b8-b78d-27a928001165` reserved 5,533,085,696 bytes, was renewed
and is released. The owned native recipe directory was removed by normal cleanup.

- Name: `Pixal3D 色・模様検証 木製宝箱`.
- Blend: `asset_81497d6049c5440e9a22fecee6b11848`, 96,436,384 bytes,
  SHA256 `cf072580f97193622034a344b41f950281b4f4e5bd442dfc1a39aae5e7410853`.
- GLB: `asset_6f52e48162974d1c827e9b54b72fb3a6`, 38,303,512 bytes,
  SHA256 `6ef649bbb77b4af1948f251501f8549c15f041f3c6097495d190b5ba0183e60b`.

Independent Blender4.5.13 import/four CPU renders pass: 729844 vertices,
973502 triangles, one mesh/material, two 4096² textures, finite coordinates,
zero bones/actions. The base-color RGB ranges are 18–222 / 2–204 / 0–149;
standard deviations are 25.14150 / 24.03227 / 17.63739. Native→published base-color
and metallic/roughness embedded image bytes match exactly. Base-color image SHA256
is `9e2f4d35d8a5ffabda68ead732e82eddba3b5da94a641e1f27624c65017242b5`;
metallic/roughness is `3c015cc73c686c3f2182e2a68c71d3811dffe2ad5b9ba1809262d53d71280583`.
The registered asset/lineage/provenance and HTTP content hashes agree.

Four renders and actual installed Host 320/1280px screenshots visibly retain
brown wood grain, gold trim and dark bands. Material mode and initial/Fit views
load without manual zoom-out; page/HTTP/request errors and horizontal overflow
are zero. Pixal's generated object is tilted, panels/hardware are distorted and
an unseen lid-side gap remains. Those are geometry/pose quality limitations,
not fixed by texture delivery. Exact reconstruction and watertightness remain
NOT ACCEPTED. The original mechanical assets retain their earlier holes/roughness;
neither color experiment is a repaired replacement for them.

The actual Host scene-list response contains both named scenes:
`scene_f2803b465d184a66841fc140af7ea627` (TRELLIS),
`scene_b9aad097879747d5ab674bdd78eda073` (Pixal), one revision each.
The current Library GLB card instead displays the generic provenance summary
`Export validated scene preview` and a `3D` placeholder; it does not display the
scene name or a rendered thumbnail. Therefore scene names above identify the
3D Studio scene list, not a Library card label. Opening each actual GLB in the
Library is independently verified and does display the textures.

| Gate | Result |
|---|---|
| Portrait initial/Fit clipping | Fixed in installed signed 0.28.91, including restart |
| Native→Library texture transfer | Exact embedded image hashes preserved |
| Colored-reference material display | Both engines pass for this wooden chest |
| Exact geometry/detail/pose reconstruction | Not accepted; documented distortions/gaps remain |
| Original mechanical-part geometry repair | Not performed; prior limitations remain |
| Rigging/animation, general-input quality | NOT TESTED by this color evaluation |

Evidence: `maintenance/g9-texture-audit-20260920/color-trellis_cpp/`,
`color-pixal3d/`, `installed-*`, `restarted-*`, `installed-pixel-bounds.json`.

After acceptance, HTTP hashes of all six copied registered outputs were checked
again. Eleven owned redundant files (318,916,079 bytes: downloaded blend/GLB
copies, captured native GLB, duplicate release archives and completed-update DB
snapshots) were removed; see `cleanup.json`. Their raw copies no longer exist in
the evidence directories. Registered originals, scene history, runtimes and the
Host's official rollback version are untouched. Reports/signatures, source and
texture images, four-view renders and browser screenshots remain for the user's
follow-up review of this reported quality issue; they can be reclaimed when that
comparison is closed. Final service health is healthy. The original checkout
remains clean at `524553d5700121dfcfc8c556e232638ba15f6873`.
