# MediaForge 0.28.88 installed acceptance

Date: 2026-09-20 JST. User requested the established merge/release procedure.

## Source and delivery

- G9 PRs [553](https://github.com/souten-yd/ControlDeckMediaForge/pull/553)
  through [575](https://github.com/souten-yd/ControlDeckMediaForge/pull/575),
  23 total, merged through PRs with exact head guards. Main's active ruleset
  requires PRs, with zero required approvals and no required CI checks.
- PR570's status/handoff insertion conflict was resolved by retaining both its
  historical Library record and the newer trained evaluation. Other open PRs and
  the original `feat/g9-image-to-3d` checkout at `524553d` were preserved.
- Version PR [576](https://github.com/souten-yd/ControlDeckMediaForge/pull/576)
  merged as `a30181cc7c6a1c7faba4b87cbd8cab616309b2c3`. Build used this exact
  commit; its tree equals the validated version branch.
- `./mf.sh test`: **2242 passed, 2 warnings, 252.68 seconds, exit 0**.
- Standard `scripts/build_release_bundle.py` and `scripts/sign_release.py`,
  existing publisher key and isolated bundle-build venv; no key rotation or
  Host catalog/code change. Core/add-on/feature/signed manifest/tag all 0.28.88.
- [Release v0.28.88](https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.28.88)
  contains the ordinary tarball, SHA file, canonical manifest and Ed25519 signature.
  Artifact: **31,818,827 bytes**,
  SHA-256 `14a91d84b2aa4249bf32d54fd6036b7d1c7e11e076f25025f5e0c3724f699f7a`.
- Independent GitHub download matched the built artifact and trusted publisher
  verification; altered manifest rejected. Archive: 6 entries; executable:
  226 entries and 1029 Python modules. No venv, secrets, weights or forbidden ML
  modules (`torch`, `diffusers`, `transformers`, `timm`); new G9 core modules present.
- Extracted package in fresh isolated directories served real health,
  capabilities and 3D workspace HTTP responses in **0.864846 seconds**.
  Missing environment/runtime correctly reported `setup_required` and
  `3d.image_to_3d=unavailable/runtime_not_installed`. The initial checker wrongly
  expected `healthy`; its log is retained, and only that expectation was corrected.
  This was package startup acceptance, not a full cold GPU/model provision.

## Installed results

`/data1tb/ControlDeck/app/deck.sh feature update media-forge` exited 0.
`current` resolves to `versions/0.28.88`; installed, enabled and requested_enabled
remain true, health `healthy`, rollback directory 0.28.87 retained.
The installed executable's real `doctor` reports packaged 0.28.88.
Source/installed manifest and served HTML include the new tool and engine UI.

Before update, a SQLite backup and logical hashes of all **16 tables**, attributes
of **2722 asset files**, and the Blender registry hash were recorded. They match
after update, browser use and restart. Active Jobs, Blender sessions, runtime
operations and model operations were zero before each service change.

The genuine installed standalone UI was exercised with Chrome **151.0.7922.169**,
real HTTP and software WebGL, without transport fixtures. Both 1280px and 320px
viewports opened Library GLB cards, rendered all three existing models, closed
viewer handles, and reached the 3D workspace. Horizontal overflow, HTTP errors,
failed requests and page exceptions were zero. The synthetic Pixal label remains.

| Asset | Bytes | Triangles | Animation clips |
|---|---:|---:|---:|
| `asset_eb160c5649954d48a615693f0e3c3c6b` | 11443236 | 276178 | 0 |
| `asset_77a23cf2d502453a8046b376d161adec` | 11189676 | 283034 | 0 |
| `asset_fb6f0e144cfe45e3bec02996b366eb53` | 48220 | 576 | 0 |

All three complete HTTP content hashes match the previously registered originals.
The first two retain WebP textures. No new asset was registered during release.
This verifies display and retention, not generated geometry quality or rigging.

After `systemctl --user restart cdapp-feature-media-forge.service`, service PID
changed from **2600491** to **2601191**, both executing `versions/0.28.88`.
Health, doctor, capability, original asset hashes, managed data comparison and
the same eight browser cases passed again.

## Explicit remaining gates

Both engines still report `unavailable/three_d_runtime_unavailable`; generation
form is hidden and submit disabled. Neither adoption receipt was created.
The accepted model license consent remains effective and is not requested again.

Authenticated Host `GET /api/v1/addons/effective` returned **401** before/after
update and restart. Authenticated Host iframe/effective contribution acceptance
is **NOT TESTED**; standalone UI evidence does not replace it. No Host-internal
session/token fabrication or user-cookie extraction was used. Host service itself
was not restarted; only the idle MediaForge feature was restarted.

Also **NOT TESTED**: full cold provision, actual rollback execution, fresh image
generation, genuine leased Vulkan/full trained Pixal quality and VRAM, runtime
adoption, installed generation-to-Library, skeletons or animation authoring.
Next generation work needs an ordinary authenticated Host execution context,
genuine broker admission/device mapping and measured runtime adoption.

## Evidence and cleanup

Managed evidence: `maintenance/release-0.28.88-20260920/` under the installed
feature-data directory. It includes PR/merge manifests, full-test/build/update
logs, release-source/signing/published-release records, two independent signature
reports, module audit, clean package smoke, installed before/after restart reports,
browser scripts/reports/screenshots, and before/after data hashes.

After successful comparison and restart, only this release's duplicate built and
downloaded tarballs and temporary pre-update SQLite backup were deleted:
**75,794,582 bytes** reclaimed, paths/hashes in `cleanup.json`. Those raw copies
are no longer retained. Published release assets, small evidence, current/rollback
versions, user assets, model weights and runtime environments remain intact.
