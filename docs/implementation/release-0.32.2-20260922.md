# MediaForge 0.32.2 release and installed verification

Date: 2026-09-22

## Published source and artifact

PR [#608](https://github.com/souten-yd/ControlDeckMediaForge/pull/608) merged as
`65aaac3b3c923e85e8ca7aef888a1747d64b66a9`; follow-up
[#609](https://github.com/souten-yd/ControlDeckMediaForge/pull/609) merged as
`c9d25e9ae7dad8c1fa74b5e677bee9a925ab7e9f`.
The latter is the source of [release 0.32.2](https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/0.32.2).
The earlier bundle built before #609 was never published.

The installed local test build was 0.32.1, while the prior public latest was
0.30.1. The Host updater reuses an existing destination when updating to the
same current version. Publishing 0.32.2 ensures the normal updater installs the
verified public bundle. The original `feat/g9-image-to-3d` checkout was preserved.

```text
artifact control-deck-media-forge-0.32.2-linux-x86_64.tar.gz
bytes    37,997,030
sha256   c3989f4bc7fbb11ce9d59ae3dd7985ab0c9d4dba47c571bcdbedbe1662465dcb
```

Built in a detached worktree at the release commit using
`scripts/build_release_bundle.py --version 0.32.2`; signed with the existing
publisher key through `scripts/sign_release.py`. The local and independently
downloaded public artifact both passed canonical manifest, trusted-catalog
Ed25519 signature, tamper rejection, size and SHA checks. Archive: 6 entries;
embedded bundle: 239 entries. Frontend resources and bake worker matched source;
no weights, private keys, SQLite databases or venvs were embedded.

The extracted package started in fresh temporary managed directories, returned
`setup_required`, exposed both pipeline schemas/contributions, and kept
`3d.image_to_3d` unavailable with `runtime_not_installed`. This was a package
startup check, not a clean GPU runtime installation.

## Validation before publication

- #608 `./mf.sh test`: 2360 passed, 3 warnings, 265.45 seconds.
- #609 `./mf.sh test`: 2358 passed, 3 skipped, 3 warnings, 268.30 seconds.
  The skipped signing tests required the build runtime, which was not initially
  connected to that worktree. After connecting it, `tests/test_release_signing.py`
  passed all 3 tests in 0.20 seconds (2 warnings).
- Existing registered immutable Blender inputs were SHA-verified and copied for
  a direct Blender 4.5.13 CPU worker regression: 1.766 seconds, 32,663 triangles,
  1 degenerate UV triangle, normal 753,561 bytes, AO 256,522 bytes. Core report
  validation passed. This did not register assets or approve visual quality.
- Separate real HTTP core processes with a stub Host and fake image worker
  reproduced prompt pipeline start HTTP 422 before #609 and HTTP 200 after it.
  The corrected process produced an image asset and stopped at
  `awaiting_approval` before model reconstruction. This was not GPU inference.

## Normal update and restart

`/data1tb/ControlDeck/app/deck.sh feature update media-forge` exited 0.
Before the update, Jobs, GUI sessions, runtime/model operations and pipelines
had no active entries. SQLite backup and read-only snapshots were taken.

After the update:

- `current` resolved to `versions/0.32.2`; both package manifests were 0.32.2.
- Service PID 3500822 used that version's executable and working directory;
  health was `healthy`. Static app, stylesheet and viewer bytes matched source.
- All 17 database table counts/digests, 3010 asset file attributes and Blender
  runtime registry digest matched the pre-update snapshot exactly.
- Current 3D capabilities were unchanged: TRELLIS resolutions 1024 and 512,
  Pixal3D 1024, both experimental. No runtime promotion occurred.
- The existing GLB and baked image content endpoints returned their registered
  byte counts and SHA-256 hashes:

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `asset_f5d6dbe7a5224f5aa01864abf0085468` | 5,909,000 | `7b834419e4d5010db44d124c378ea753d9f20d8677920bbc877e3c73910b246e` |
| `asset_af62ad8d05574d4dbbc955081e39abec` | 680,481 | `3c6689bd8a2445708ab312c4abaf0cd55167d855976717234033d52a42c16ea0` |
| `asset_4d13d751e55b48b7ac3d4bcd3b5f3918` | 321,903 | `e40448496e39e75bc1146f284a1acd084a4bf5e2e7c80e5ebc249231243bcafb` |

The existing standalone browser fixture passed at 1280px, with eight selectable
images, disabled pipeline start and an explicit ControlDeck requirement; console
errors were zero. Its first attempted URL `/workspace/create` was 404; using the
actual standalone `/create` route resolved the fixture invocation error.

After a fresh idle snapshot, `systemctl --user restart
cdapp-feature-media-forge.service` completed. PID became 3501364. Health, source
bytes, 3D capabilities and the three asset hashes passed again. All 17 tables,
3010 asset attributes and registry hash matched the restart snapshot. The
standalone browser fixture passed again. The previous 0.32.1 directory remains
available for rollback; an actual rollback was not exercised.

## Authenticated Host follow-up after login refresh

The user refreshed the ordinary dedicated Host login on2026-09-22 using
`bash ~/mf-login.sh`. The authenticated effective projection reported healthy
MediaForge, available pipeline start/status contributions and `mobile: embedded`.
Real Chromium at1280px and320px opened `/x/media-forge/workspace/create`, loaded
the opaque iframe, switched to3D and listed eight source images. Selecting an
image enabled pipeline start. Both widths had zero Host/iframe horizontal
overflow, zero console/page errors and zero failed requests. Screenshots were
retained; the mobile screenshot was visually inspected.

Only the user's normal session cookie was passed privately to the browser.
Accounts/passwords were not changed and no Host session was minted internally.
The first fixture attempt inspected page.frames before the iframe navigation
completed and closed early. Waiting for the actual frame navigation fixed that
fixture race; no product source change was needed.

## Remaining acceptance

NOT TESTED in this release verification: submitting a new pipeline from the
Host browser, a new real GPU prompt-to-3D chain, auto mode end-to-end,
visual/deformation quality, and rollback execution.
These remain distinct from the earlier recorded successful image-to-rig pipeline.

Evidence: private feature maintenance directory
`release-0.32.2-20260922/`, including test logs, source/artifact verification,
HTTP reproduction, bake regression, update and restart snapshots, and standalone
screenshots. Qwen-Image evaluation follows this release; no Qwen weights or
product adapter were adopted by 0.32.2.
