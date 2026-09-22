# 0.33.2 release and installed acceptance

Date: 2026-09-22. Final state: signed release published, normal Host update applied,
real image generation and texture comparison accepted. Earlier 0.33.0/0.33.1
failures remain recorded in the handoff as history; they are not the final state.

## Release identity and verification

- Source: `1ceedb9d3bbcdb6d99c0613ba0061c08342dc863`, merge of PR615.
  PR612 adds the isolated Qwen Vulkan path; PR613 adds texture candidates;
  PR614 preserves admitted image dimensions; PR615 fixes reference sizing and
  uses the measured texture-edit resource profile.
- Release: <https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/0.33.2>.
- Artifact: `control-deck-media-forge-0.33.2-linux-x86_64.tar.gz`, 38,019,571 bytes.
- SHA256: `d542468c1fe6cda59ba5146e15a04b0ab7d22105cbc99e0b1b86d34bd8b31bf8`.
- `./mf.sh test` on the final implementation: **2407 passed, 3 warnings,
  275.70 seconds, exit 0**. The acceptance follow-up changes documentation only.

The exact detached source was packaged with `scripts/build_release_bundle.py
--version 0.33.2`, signed with the existing publisher identity, published and
downloaded again. `verify-release.py` checked both local and downloaded files:
canonical manifest, size/SHA256, Ed25519 against the Host trusted catalog,
tampered-manifest rejection, six archive entries and 241 embedded entries.
Bundled frontend, Blender scripts, native Qwen adapter, image worker, FLUX
adapter and model catalog matched the source bytes. No weights, venvs, SQLite
data or private keys were bundled.

`clean-smoke.py` started the extracted signed package with fresh managed
directories: startup passed in 0.866465 seconds, health was `setup_required`,
and image-to-3D was `runtime_not_installed`. This is package startup evidence,
not a fresh GPU-runtime installation.

`/data1tb/ControlDeck/app/deck.sh feature update media-forge` exited 0. The
effective `current` points to `versions/0.33.2`; manifest, process executable,
working directory and served frontend hashes were checked. After an explicit
restart of `cdapp-feature-media-forge.service`, PID 3675350 was healthy.
All 1513 pre-update Asset records were retained unchanged. Content fetched by
HTTP for the original chest `.blend`, an existing rigged GLB and an earlier
Qwen sample matched their recorded SHA256. The TRELLIS/Pixal3D capability
document was unchanged. Final Host effective state was healthy, with no active
MediaForge or operator-evaluation GPU leases.

## Qwen product generation and transparency

The isolated Vulkan configuration is Qwen-Image-2.1 DiT Q8_0, Qwen3-VL-8B
Q4_K_M and the dedicated BF16 VAE. It is manually selected; existing automatic
model choices and shared FLUX/H3 runtimes remain unchanged. Normal model
installation verified and installed 14,549,481,427 bytes through the managed
operation `modelop_59325176818c47cb8545971a8f7ff792`.

The following actual product Jobs ran on installed 0.33.1 and remained visible
and byte-identical after 0.33.2 update/restart:

| Output | Job | Library Asset | Result |
|---|---|---|---|
| Normal apple | `job_4b31f58e752e4875ae96e33ed49bd27d` | `asset_3a0c2daebeae4197a2eed1d84aa2c06b` | 1024×768 RGBA; alpha 255 throughout |
| Transparent apple | `job_c5e3d5341fa54d4cbf96ea32970ca96e` | `asset_a062b91516da45d198d5ed7500b93ff0` | 1024×1024 RGBA; alpha 0–255 |

The first used the actual Host model picker and Create button. The second used
the normal authenticated Host `jobs.create` route with
`asset_brief.alpha_intent=required`. End-to-end Job durations were 62.253 and
60.102 seconds respectively; these include orchestration and are not isolated
model timings. The transparent output has 619157 fully transparent pixels and
417399 opaque pixels. It was inspected over white, black and checker backgrounds.

Normal PNG SHA256:
`f81c6587937f7ae40a08989226a24dcc5df1ff96ce14595c7b1c02be6a9e7b36`.
Transparent PNG SHA256:
`6f76a8c42a2d15245623b711e070f1e26f847f587057e76c801546aab8c4efb7`.

[Upstream Qwen-Image-2.1](https://github.com/QwenLM/Qwen-Image-2.1) supports
native RGBA generation/editing. Our native Vulkan alpha probes had background
residue/halos or excessive color changes and did not pass visual acceptance.
The product therefore uses ordinary Qwen generation plus the existing explicit
background-removal path. Native alpha and Qwen reference editing are not adopted.
The sample's precise background-removal method is not recoverable from its
provenance: worker `alpha.set_opaque` is recorded, but the existing core cutout
stage does not append its step. The final alpha validation and PNG hash are
recorded. Do not describe this sample as native RGBA or as a confirmed BiRefNet run.

## Real AI texture candidates and 3D comparison

On installed 0.33.2, the real Host UI extracted the current packed texture from
`scene_b9aad097879747d5ab674bdd78eda073` (Pixal3D wooden chest), then requested
three 1024×1024 variants. The original scene head was
`revision_459c6661ae0a47b982cd7fbbd146d5f0`; source Asset was
`asset_81497d6049c5440e9a22fecee6b11848`.

`job_2940588ac49541f2a798982b113b6ae3` completed from
08:26:29.609226 to 08:27:14.137476 UTC: **44.528250 seconds**. It used the
adopted FLUX.2-klein-4B reference editor and normal Host broker grant of
15,419,755,724 bytes, subsequently released. The extracted source image was
`asset_97c0a6c9271f48d2a2147588d9f6c0d2` (4096×4096). The original texture was
retained; inference fitted the reference to the 1024×1024 output canvas.

| Candidate Asset | PNG SHA256 |
|---|---|
| `asset_ca1f5bc9707547d895414664b72c01fe` | `229904303cb7b08214b25ff256e7cd71a3ddcc669a40493bbfffacb59446779e` |
| `asset_bc049097a63e4d10afa7175d0f1b4726` | `84bf030b59cabeb1846859175129bf6a7291d46af4e906247de98cadbe292c2a` |
| `asset_d8cbd52af33f457e80a5f1f29dbf00fa` | `13f6b121c80f9b3cf1abd43f8fd9e01e731fcb00f2dfeb63eb2421005981309d` |

All three are distinct opaque RGBA images. Provenance retains the image→original
`.blend` and candidate→extracted-image parent chains and reference hashes, with
`reference.fit_to_output` and `pil.convert.rgba` processing steps.

Real Chromium on the actual Host selected candidate 2 and ran the real Blender
material preview. The comparison showed both original and candidate chest,
with the candidate's lighter wood and changed grain. Both meshes retained
973502 triangles, one material and zero animations. The comparison was discarded
after inspection; the original scene JSON/head/source remained unchanged.
The three candidates remain selectable for the user's own adoption.

At 1280px and 320px, Library displayed both new Qwen outputs and all three
texture candidates. Host/frame overflow was zero and the iframe remained opaque.
No page errors occurred. The same five Library Assets remained visible after
service restart; the scene panel restored all three candidates at 320px with
zero overflow/errors.

## Evidence and limits

Private evidence root:
`/data1tb/ControlDeck/data/feature-data/media-forge/maintenance/`.

- `release-0.33.2-20260922/`: release verifier and manifests, clean startup,
  update log, `after-restart-check.json`, final effective/resource snapshots,
  actual Job receipts/PNGs, `texture-lineage.json`, `texture-host-check.json`,
  `texture-3d-comparison.png`, `library-final.json` and `texture-restored.json`.
- `release-0.33.1-20260922/alpha-comparison.png`: transparent PNG over three
  backgrounds; actual Qwen product Job receipts originate in this directory.
- `texture-runtime-20260922/`: guarded real GPU profile measurements and
  `full-0.33.2.log`. The successful profile trial produced three candidates in
  51.989532 seconds with whole-device peak 12,581,740,544 bytes and cgroup peak
  15,094,476,800 bytes. The earlier stopped trial reached 13,057,523,712 GPU bytes;
  this larger observation sets the texture profile, plus existing broker headroom.
- `texture-variants-20260922/`: real Blender extraction and explicitly fake
  image-worker source-UI checks, separate from the real installed acceptance.
- `qwen-image-21-vulkan-20260922/`: native probes and the first four imported
  samples. These imports are separate from the two actual product Jobs above.

Automatic adoption of a candidate into the user's chest was not performed.
The new candidates passed visual comparison, not a pixelwise UV-preservation
guarantee. Native Qwen transparency/editing remains unadopted; installed UI
cancellation during denoising, fresh GPU provisioning and rollback are
**NOT TESTED** here. The original checkout `feat/g9-image-to-3d` at `524553d`
was left clean and unchanged. No Host source changes were made.
