# G9 installed image-to-3D and signed 0.28.90 acceptance

## Authentication and release

The ordinary operator login succeeded on 2026-09-20 at 01:23:50 UTC
(10:23:50 JST). Live authenticated HTTP and browser requests subsequently passed.
The earlier `host_login_failed_no_automatic_retry` means that an attempt failed
and was not retried automatically; it does not mean session reuse is unsupported.
Authenticated `/api/v1/users` also confirms active `mf-e2e` (16) and `mfe2e` (17)
test accounts. Their credentials were not needed or changed. The valid operator
session belongs to `souten`; no additional login or model-license consent is needed
for this acceptance. Authentication material remains outside the repository/logs.

PR581 fixed the measured-confidence contract. Signed 0.28.89 exposed the separate
workflow-priority ceiling on the real Add-on Runtime path; the failed Scene Job
published no assets. PR583 fixed priority and prepared 0.28.90. These two failures
and the unsuccessful earlier generation remain recorded, not overwritten by success.

Version 0.28.90 was built from exact merge
`11da1498ea339a06e8103a1238679b357f98861a`, signed with the existing publisher key,
published, independently downloaded/verified, and installed with the normal
`./deck.sh feature update media-forge` command (exit 0).

- Release: <https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.28.90>
- Archive: 31,816,169 bytes; SHA256
  `ee341d8bcf7569c5c9f3c11bd1861171ad32feedca4b2cb57c9a438e34c8b274`.
- Signature, archive checksum and tamper rejection passed. Fresh-directory bundle
  startup took 0.862 seconds and correctly reported unavailable unconfigured
  capabilities; that smoke check is not installed Host acceptance.
- Installed `current=versions/0.28.90`, enabled and healthy, rollback 0.28.89 retained.
  Before/after update: 16 database tables, 2724 asset-file attributes and the Blender
  registry matched exactly. The three previously registered GLB hashes still match.
- Release product gate: `./mf.sh test`, 2279 passed, 2 warnings, 272.22 seconds, exit 0.

## Real installed generation

Only the independently measured TRELLIS 512 configuration was adopted after exact
runtime/model hashes were verified. The live capability is `experimental`, with
resolutions `[512]`; Pixal remains unavailable. See the separate
[native evaluation](g9-real-generation-20260920.md) for the 306.481171-second run,
sampled peak VRAM of 8,986,034,176 bytes, and the failed 1024 buffer allocation.

The ordinary authenticated Host invocation was:

```text
POST /api/v1/addons/media-forge/agent-tools/media.scene.from_image/invoke
name: TRELLIS 画像から3D・機械部品 512
input_asset_id: asset_8cd35ff5ffb145ba94febf7a79cf6583
engine: trellis_cpp; resolution: 512; seed: 20260920; local_only: true
retry_job_id: job_e4c1fb0821734ca8a54ffb3f3a0b9622
```

Host parent `3a9a8cef17c1`, detached child `ed5303b64850`, and MediaForge Job
`job_9576be19cd974c229e5cbd57a8d9e6c5` all reached `succeeded`.
MediaForge timestamps are 02:13:01.810119 to 02:18:21.882239 UTC (320.072120 seconds
including admission/import/publication); native generation provenance records
305.373791 seconds. Genuine lease `4a226ccc-2534-4458-a50b-aa40584a6d17` reserved
9,522,905,088 bytes on Host gpu0 / native device 1 for the detached child and was
observed active during generation, then `released` after process exit. No active
MediaForge Jobs remained at the final snapshot.

The existing scene and asset stores now contain:

| Role | Asset | Bytes | SHA256 |
|---|---|---:|---|
| Source PNG | `asset_8cd35ff5ffb145ba94febf7a79cf6583` | 331690 | `13513e9e7b12dc92e97fcf279b427ef9b91c31ebd6ebb19a66dfbd3451e60e83` |
| Editable Blender scene | `asset_51150a6edd0444c6ad38de8c93e32919` | 15005854 | `eb1e9e6756306164e5a546245139f0f047e70d17fb36e7dbf427e6738bb174e4` |
| Library GLB preview | `asset_1171977ee90444ef873538a86f56255e` | 6366644 | `259449240060cb60fc35d0c62a36fa712d13bc1ff283b367ae3483be90997828` |

Downloaded content matches every asset hash. Parent links are PNG → Blender → GLB.
Provenance retains the input hash, TRELLIS runtime revision, model revision/weight
hash, accepted licenses, seed, resolution and elapsed time. The intermediate native
GLB hash differs from the exported Library preview; these are separate artifacts.

The registered GLB passes `glb.structure` 1.1.0 with required `EXT_texture_webp`.
Independent Blender 4.5.13 LTS reimport and four Cycles CPU renders passed:
1 mesh, 145472 triangles, 142040 imported vertices, 1 material, 2 textures at
1024×1024, finite coordinates, 0 bones and 0 actions. The worker's pre-export scene
had 141862 vertices; these counts describe different import/export stages.
All four rendered views were inspected. The front disc, body and side pipe resemble
the reference, but the unseen rear has ragged surfaces/holes. This is an experimental
single-image reconstruction, not CAD fidelity or a quality-approved animated asset.

## Installed Host browser and persistence

The authenticated real Host routes `/x/media-forge/workspace/library` and
`/x/media-forge/workspace/create` were exercised in Chrome 151.0.7922.169 at both
1280 and 320 pixels. The actual Add-on iframe has opaque origin `null`.

Before generation, the existing WebP sample displayed correctly. After generation,
the new GLB opened from Library, reported 145472 triangles/1 mesh/1 material,
rendered, and released the viewer on close. Create → 3D exposed the image-to-3D
form, selected the registered input image and resolution 512, and enabled submit.
These UI checks did not click submit a second time; the actual generation above
used the normal Host agent-tool invocation. Screenshots, assertions and reports
are retained for both widths. Browser page errors, HTTP errors, failed requests
and horizontal overflow were zero on the tested paths. Headless rendering used
SwiftShader; it does not measure physical mobile-GPU performance.

After all Jobs were terminal, `systemctl --user restart
cdapp-feature-media-forge.service` changed PID 2749525 to 2755777. Immediately
after restart, the 16-table snapshot, 2728 asset-file attributes and Blender registry
matched the pre-restart snapshot. Healthy installed version, adoption, source and
both new asset hashes persisted. Authenticated `/api/v1/addons/effective` returned
200, and both browser widths passed again.

After browser interaction, a strict all-table comparison correctly detected a
changed preference timestamp. Read-only row comparison isolated the sole change:
subject 2 `updated_at` advanced from 02:23:48.987419 to 02:25:02.162440 UTC.
All preference values, the other 15 tables, asset attributes and registry were
unchanged. This expected UI save was recorded, not suppressed or repaired by SQL.
The unauthenticated 401 in the generic installed-check report is a separate
negative probe, not an authentication blocker or a failed Host browser check.

## Remaining limits and evidence

[PR584](https://github.com/souten-yd/ControlDeckMediaForge/pull/584) is merged as
`435a3af`: bounded NAF buffer use and actual F32 Vulkan numeric checks pass, but
the trained Pixal pipeline still fails at HR flow with `non-finite flow velocity`.
See [the exact measurements and resumption condition](g9-pixal-vulkan-naf-20260920.md).
The repository's unstable-model rule therefore defers full Pixal adoption. No
trained Pixal GLB was registered; the old synthetic sample retains its warning.
The native change is outside the lightweight bundle and does not require another
app release. Final product-tree tests: 2279 passed, 2 warnings, 266.95 seconds,
exit 0. This acceptance slice changes documentation only.

NOT TESTED / not completed: successful trained Pixal generation, 1024 TRELLIS
generation, bones/animation for this result, cold provisioning, real rollback,
and physical-device browser performance. The overall Pixal/animation request is
not complete merely because TRELLIS delivery and viewing succeeded.

Evidence is under the installed feature's `maintenance/` directory:

- `g9-real-generation-20260920/installed-result/`: HTTP asset/provenance/content,
  terminal Host Jobs, released lease, Blender report/four renders, restart checks.
- `g9-real-generation-20260920/installed-retry-*`: invocation, actual Scene Job
  and active lease snapshots.
- `release-0.28.90-20260920/`: build/sign/download/tamper/smoke/update logs,
  installed status, authenticated browser scripts/reports/screenshots and
  `restart/browser-state-comparison.json`.

No Host source changes, new account credentials, inference fallbacks, or edits to
the original `feat/g9-image-to-3d` checkout were needed.
