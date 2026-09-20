# G9 real Vulkan evaluation and broker contract — 2026-09-20

The ordinary dedicated operator session was validated against the live Host.
Public user metadata also confirms the existing `mf-e2e` and `mfe2e` test accounts.
No account changes, password extraction or additional login were necessary.
The previous `host_login_failed_no_automatic_retry` message described an individual
failed attempt; it is not an unsupported-auto-login capability report.

## Actual GPU evaluation

Evidence is in the installed feature's `maintenance/g9-real-generation-20260920/`.
`leased_eval.py` uses ordinary authenticated public Host resource APIs, one
exclusive lease at a time, activation, five-second renewals, process-group reaping
and release. The evaluation requests 31 GiB with an 1800-second runtime bound.
It samples device-wide VRAM and parent process RSS every 0.2 seconds; these are
sampled observations, not an exact process allocation peak. Pixal's parent RSS
excludes its native child. The inherited address-space limit is 26 GiB.

A separately leased Vulkan enumeration maps native index 1 to the R9700
(RADV GFX1201), Host `gpu0`, PCI 0000:03:00.0. Native index 0 is the integrated GPU.
TRELLIS logs confirm Vulkan1 and the R9700 for auxiliary Vulkan operations.
All ten existing TRELLIS GGUF files were rehashed against recorded distribution
identities (16,467,590,304 bytes; 11.646101 seconds). The clean native revision is
2516c48b677050c570f47eba2e68dc8a5bc918b0; GGML is pinned at
737e88f25d4f62254f3b7a726fd9663036cc94da.

| Run | Observed result | Runtime | Sampled device VRAM peak |
|---|---|---:|---:|
| TRELLIS 512, seed 20260920 | exit 0, WebP GLB 6,361,036 bytes | 306.481171 s | 8,986,034,176 bytes |
| TRELLIS 1024, same input/seed | exit -6, HR flow allocation failure, no GLB | 115.098108 s | 8,985,329,664 bytes |
| Pixal trained, Vulkan, seed 42 | exit 1, NAF IM2COL unsupported, no GLB | 61.607146 s | 3,961,503,744 bytes |

All three leases were released after the owned processes exited. TRELLIS 1024
reached 51,272 HR tokens; the driver rejected a 5,282,267,136-byte allocation as
exceeding its buffer-size limit. This is not evidence that the full GPU memory
was exhausted. Do not advertise 1024 from the successful 512 run.
Pixal completed sparse structure and entered LR image/flow processing before
failing in the NAF operation. No CPU fallback or successful Pixal adoption is claimed.

The TRELLIS GLB SHA-256 is
`0f9678637b3e0e6cdeebf4ddc159394122eee80e3d56f2e360a10768b901d163`.
The MediaForge 1.1.0 validator accepts its required `EXT_texture_webp` extension.
Independent Blender 4.5.13 import and four Cycles CPU renders succeeded: one mesh,
141,862 vertices, 145,472 triangles, one material, two 1024-square textures,
finite positions, zero bones/actions. Visual inspection shows the reference
mechanical housing, front disk and side pipe, with rough surfaces and artifacts
on the unseen rear. This is an experimental reconstruction, not CAD accuracy.

The source image was registered through the installed import API as
`asset_8cd35ff5ffb145ba94febf7a79cf6583`. Import normalizes PNG encoding:
original SHA `be160b8b234fdcc25c67499b7a0be471870feca6f62cfa168518e5059cb162de`,
stored SHA `13513e9e7b12dc92e97fcf279b427ef9b91c31ebd6ebb19a66dfbd3451e60e83`.
The downloaded stored bytes match that digest and all decoded RGBA pixels match
the original exactly. This is source registration, not generated-GLB registration.

## Broker correction

The shared TRELLIS/Pixal adapter emitted `vram.confidence=high`. The running Host's
OpenAPI exposes only `measured`, `estimated`, and `low`. Sending the old value to
the authenticated public resource endpoint produced HTTP 422 at
`body.vram.confidence`, before any lease was created. The adapter now sends
`measured` from its validated adoption measurement. Both engine regression tests
assert the accepted value; no Host code or public MediaForge schema is changed.

`PYTHONPATH=backend .venv/bin/pytest tests/test_three_d_runtime.py tests/test_pixal_runtime.py -q`
passed all 24 tests. `./mf.sh test`: **2279 passed, 2 warnings, 257.81 seconds, exit 0**.

At this checkpoint the 512 adoption candidate has been validated against all
current runtime/model hashes, but is not installed. Next: signed patch release,
512 adoption, real Host image-to-3D invocation, generated Library lineage and
browser acceptance; independently diagnose Pixal's failed operation.
NOT TESTED: installed generation, generated Library registration, Pixal completed
trained GLB/quality, bones/animation. Existing sample assets remain unchanged.
