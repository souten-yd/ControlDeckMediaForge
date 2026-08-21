# Media Forge implementation status

Date: 2026-08-21
Scope: MF0-0 through MF0-3 complete; MF0-4 host-blocked; MF0-5/MF0-6 installed-host browser verified where the host contract permits (`docs/implementation/mf0-addon-core.md`)
Repository head at start: `770383a` (`origin/main`)

## MF0-0 — COMPLETE for the requested environment slice

The core service, heavyweight ROCm runtime, caches, and persistent Media Forge data are separated. Section 10 was executed from retreated `.venv` / runtime state on the target host. This status uses runtime observations; lint, syntax checks, and unit tests are not counted as proof that the environments work.

## MF0-1 — COMPLETE

The loopback service skeleton, Add-on v2 manifest, schema serving, four-state health contract, contribution-level availability, and setup snapshot integration are implemented. Unfinished execution contributions fail closed with explicit reasons and actions; no fake job runner or later MF0 behavior is claimed in this slice.

Real-process verification on 2026-08-21:

```text
ControlDeck ./deck.sh ext lint: valid=true, warnings=0
healthy health:        HTTP 200, 0.001353 sec
degraded health:       HTTP 200, 0.000551 sec
unavailable health:    HTTP 200, 0.000397 sec
setup_required health: HTTP 200, 0.000414 sec
schema response:       HTTP 200, 0.003092 sec
placeholder response:  HTTP 200, 178 bytes
```

For all four health states, `navigation:workspace=available` remained stable while `workflow_executor:media.generate=unavailable`. The manual health switch returned 404 unless `MEDIA_FORGE_ENABLE_TEST_ENDPOINTS=1`.

The final default process returned `setup_required` in 0.001575 seconds with a 2373-byte response. Core/runtime/GPU setup items were `ok`, model library was `missing`, and the disabled test switch returned HTTP 404.

## MF0-2 / MF0-3 — COMPLETE for the local job and asset slice

The local API now provides a durable SQLite job queue, a bounded fake-worker subprocess, explicit cancellation/timeout/crash normalization, deterministic validation, immutable asset copies, provenance sidecars, and lineage fields. Host token, GPU lease, and Jobs bridge remain MF0-4 and are not claimed here. The fake worker is CPU-only; it does not acquire or use the GPU.

Real-process evidence using an isolated temporary data directory:

```text
submit -> succeeded -> asset/provenance: 40 ms
PNG: 128x80, 8-bit RGBA, 716 bytes
same intent + seed output SHA-256:
  823c25d57f4e077f3a67fc129ce267cba2a0973d2e011ff39cecb8faa0bf3393
second run same hash: yes
worker crash result: failed / worker_crash
next job after crash: succeeded
running cancel result: canceled
normal terminal work-directory entries: 0
```

The provenance response contained the fake implementation ID, `CC0-1.0` license, empty warnings, and passed `image.non_empty`, `image.dimensions`, `image.mode`, and `image.alpha` validators. Capability discovery did not expose the implementation/model ID.

Shutdown and crash isolation were exercised separately:

- graceful service stop during a running job produced `failed / service_stopped`, not `worker_crash`
- `SIGKILL` of the exact service PID during a running job left the database row running; on restart it became `failed / service_restarted`
- the isolated child worker was gone after parent death and stale work entries changed from 1 before restart to 0 after restart
- persisted job and asset lists remained readable after restart

During the first isolated-data attempt, `mf.sh serve` was found to overwrite an explicit `MEDIA_FORGE_DATA_DIR`. Two exact test jobs and assets therefore entered the default data tree. This was not accepted as isolated evidence: the script was fixed to preserve the explicit variable, the database was backed up to `/tmp/mediaforge-mf03-cleanup.yx1Ia0/media-forge.sqlite3.backup`, the two identified files were moved to trash, and only their exact database rows were deleted. Verification reported zero remaining test jobs/assets. The complete E2E was then rerun successfully in `/tmp/mediaforge-mf03-e2e.s5f9e6`, which was moved to trash after evidence collection.

## MF0-4 — PARTIAL / HOST CONTRACT BLOCKED

Media Forge now verifies the ControlDeck HMAC service token signature, `aud=media-forge`, `kind=service`, subject, issued-at time, expiry, and the 600-second maximum lifetime. It also requires `X-Control-Deck-Addon-ID: media-forge`, never logs the credential, rejects raw Unix/Windows/file-URI paths recursively, and accepts file context only as `grant:`/`asset:` opaque IDs. Verification-key provisioning is explicit through `MEDIA_FORGE_CONTROLDECK_TOKEN_KEY_FILE`; no ControlDeck module is imported.

The lease request builder includes all four VRAM dimensions, `confidence=low`, and mandatory `estimated_runtime_sec`. The Jobs boundary enforces monotonic progress and at most 2 Hz before transport. These contract checks pass, but they are not recorded as live host integration.

The referenced ControlDeck checkout at `9272c05` does not implement the service-side methods required by the normative integration plan:

```text
host.resources.acquire / renew / release
host.jobs.register_remote / update_remote
host.files.stage_read / commit_write
```

Read-only source inspection found that `/api/v1/resources` requires a session cookie, `settings.manage`, and CSRF. The injected Add-on service token is accepted only by the Add-on's upstream endpoint; ControlDeck's resource router does not authenticate it. The signing key also has no public verification/JWKS endpoint or provisioned per-Add-on key exchange. Media Forge will not replay a user cookie, read ControlDeck data implicitly, invent an undocumented URL, or create an independent GPU scheduler. `GET /api/v1/host-integration` therefore reports these three bridges as `unavailable_in_host_revision` with `fallback=none`, and generation contributions remain unavailable in health.

MF0-4 completion and the lease/Jobs/file-grant portions of MF0-7 are blocked until ControlDeck exposes the already-designed audience-bound service bridge. ControlDeck was not modified.

This blocker was re-audited read-only against upstream ControlDeck `main` at
`08a23c57cc1ed2791284924e1c3986570713d94f` using a disposable sparse clone.
The same three service methods and service-token authentication for
`/api/v1/resources` were still absent. The reference checkout was not fetched,
checked out, or modified.

## MF0-5 / MF0-6 — INSTALLED-HOST BROWSER VERIFIED / HOST-LIMITED

The embedded workspace provides Create, Library, Jobs, Models, and Settings without localStorage, sessionStorage, cookies, or parent DOM access. It waits for the MessageChannel handshake before first paint, validates the parent origin, applies initial/theme-change tokens without reload, handles locale/safe-area/route/session/disable events, syncs routes, updates the title, exposes the command-palette shortcut, and clears busy state on disable. Standalone rendering remains available when the page is not framed.

Workflow, agent capability/generate/inspect, command, and edit-image context endpoints are implemented with service-token enforcement and structured job/asset responses. Capability discovery and all agent tool responses contain no model name; inspect returns the license, lineage, validation, warnings, and output hash without implementation identity. Context responses do not echo the scoped token.

Real-process verification on 2026-08-21 used an isolated data directory and an isolated 0600 32-byte signing key; the directory was moved to trash after shutdown:

```text
health:                         HTTP 200, 0.015009 sec, 1421 bytes
workspace HTML:                HTTP 200, 0.004198 sec, 3416 bytes
capabilities without token:    HTTP 401
capabilities with valid token: HTTP 200, 0.000757 sec, 517 bytes
workflow submit:               HTTP 200, 0.005339 sec
submitted state:               queued
observed terminal state:       succeeded, progress 1.0
asset:                         80x48 RGBA PNG, 541 bytes
asset SHA-256:                 64de30334bba9b39174ca24b4fbf903cc474c48c9dce3e1928a0f9bf659611bc
provenance validators:         4, warnings 0, output hash matched
edit-image context action:     HTTP 200, 0.000942 sec
host integration diagnostic:  token configured; resource/jobs/files unavailable; fallback none
```

The first installed-host attempt exposed three real integration defects that
unit/static checks had not detected: health reason codes outside ControlDeck's
closed enum, 401 responses for external iframe CSS/JS, and 401 responses to
opaque-origin iframe HTTP API calls. The implementation now uses only host
reason codes, serves the trusted workspace CSS/JS inline, and carries bounded
structured workspace RPC over ControlDeck's nonce-bound authenticated WebSocket
proxy. Raw paths are rejected on that transport and asset previews are capped at
12 MiB before base64 encoding.

Final installed-host browser verification used isolated ControlDeck and Media
Forge data directories, real loopback processes, Chromium at 1280x800 and
320x700, and installation through ControlDeck's public Add-on API. The reusable
driver was `scripts/mf0_control_deck_e2e.py`; it always uninstalled the Add-on in
`finally`. The final run completed in 9.199 seconds with zero browser console
errors and zero page errors. Observed results:

```text
disabled: Media navigation absent
setup_required: setup dialog and missing model library visible
healthy: Media navigation and opaque iframe workspace visible
workspace transport: bridge ready; Create produced one fake asset; Library preview rendered
theme: light -> dark applied without reload; in-frame marker survived
route: Library back / forward / reload / share URL preserved
Files: edit-image context action invoked and success toast visible
agent: media.capabilities returned ControlDeck job_id=baf9eaf98eb0 and asset_id=job-result:baf9eaf98eb0
agent response: no model_id, fake implementation name, FLUX, or Qwen string
workflow: unavailable contribution omitted fail-closed
disable: iframe and Media navigation removed
re-enable: five pre-existing isolated-run assets remained visible
mobile 320px: companion rendered and iframe remained absent
```

Create is deliberately recorded as local/partial: the generated fake job does
not appear in ControlDeck Jobs because the host bridge in MF0-4 is unavailable.
The Files action invocation and toast are verified, but scoped file staging and
route opening are not claimed. Workflow dry-run cannot be performed because the
host correctly omits the unavailable executor. MF0-5/MF0-6 therefore have real
installed-host evidence but G0 remains incomplete until MF0-4 is unblocked.

## Implemented artifacts

- `mf.sh`: non-root guard; Python 3.11+ check; independent data directory; shared cache discovery; stamp-based core/runtime creation; broken-venv rebuild; doctor/build/list/prune/test/serve commands; disk preflight; real ROCm tensor verification; cheap health snapshot generation.
- `requirements.txt`: lightweight core dependencies only. Importing `torch` in the final core environment exits 1 with `ModuleNotFoundError`.
- `runtimes/rocm-torch/`: ROCm 7.2.1 PyTorch 2.10 requirements, size/download metadata, and `.refs` containing `image`. The runtime environment is not shared with core or ControlDeck.
- `config/config.yaml`: Media Forge data defaults to `~/.local/share/control-deck-media-forge`; model libraries remain explicitly unset; `auto_provision=true` starts a visible, locked background runtime build when the environment is missing.
- Environment health is read from `config/environment-status.json`, an ignored snapshot written outside the request handler. Missing/invalid snapshots fail closed as `setup_required`.

Final Python prefixes observed:

```text
core_prefix=/data1tb/ControlDeckMediaForge/.venv
runtime_prefix=/data1tb/ControlDeckMediaForge/runtimes/rocm-torch/.venv
```

## Section 10 real-machine evidence

Host:

```text
Python 3.12.3
ROCm 7.2.1.70201-81~24.04
AMD Radeon AI PRO R9700 / gfx1201
repository filesystem=/dev/nvme0n1p1 ext4
repository filesystem total=983349346304 bytes
```

### 1–4. Retreated state, doctor, cold core start, and health

Both Media Forge venvs were absent for the initial check. `./mf.sh doctor` reported `core_env=missing`, `rocm_runtime=missing`, `model_library=missing`, and both ROCm tools. It selected these shared paths:

```text
PIP_CACHE_DIR=/data1tb/ControlDeck/data/cache/pip
UV_CACHE_DIR=/data1tb/ControlDeck/data/cache/uv
HF_HOME=/data1tb/ControlDeck/data/cache/huggingface
```

Tree hashes before and after the clean `doctor` call were identical:

```text
Media Forge: 35949df532f0149d45eb66f81e7e4dc0622417e95e62b00cedd86cd10324c156
ControlDeck:  8bf954ab6dbce61bd79e58543010ee800825364d6313b74008a89ff006ed5842
```

`./mf.sh serve` created the core environment and served real HTTP in 5.835 seconds. Its cold size was 115724645 bytes. `GET /health` returned HTTP 200 with `status=setup_required`, `rocm_runtime=missing`, and `gpu=checking`.

After the final implementation, a missing runtime stamp was exercised again with automatic provisioning disabled. The real health response included the measured/index-derived estimate:

```text
rocm_runtime.state=missing
rocm_runtime.message="Run ./mf.sh env build rocm-torch; estimated download 2100000000 bytes"
gpu.state=checking
```

### 5–6. Clean runtime construction and actual GPU execution

Before download, `./mf.sh env build rocm-torch` displayed:

```text
runtime=ROCm 7.2.1 PyTorch 2.10 runtime
estimated_download=2100000000 bytes
available=809378115584 bytes
required_with_headroom=8589934592 bytes
```

From runtime-venv creation to installed Torch metadata was 225 seconds. From creation to the final successful GPU snapshot was 264 seconds. The latter includes correction and reruns described below. Final runtime size was 4445904539 bytes. The shared pip cache gained 45 files / 1956470511 bytes.

The first construction attempt installed the packages and then exposed a `set -u` wrapper defect (`snapshot: unbound variable`). That defect was fixed rather than recorded as success. PyTorch then warned that NumPy was absent; NumPy was added to the runtime requirements and the clean final GPU check was rerun.

The final real GPU operation produced:

```json
{
  "torch_version": "2.10.0+rocm7.2.1.gitb07cec22",
  "hip_version": "7.2.53211",
  "device_count": 2,
  "devices": [
    {
      "name": "AMD Radeon AI PRO R9700",
      "gcn_arch": "gfx1201",
      "total_memory_bytes": 34208743424
    },
    {
      "name": "AMD Radeon Graphics",
      "gcn_arch": "gfx1036",
      "total_memory_bytes": 16302784512
    }
  ],
  "selected_device": 0,
  "free_memory_bytes": 33975959552,
  "total_memory_bytes": 34208743424,
  "tensor_result": 16773120.0,
  "elapsed_sec": 0.05090730299707502
}
```

The second device's memory value is the value reported by Torch. `rocm-smi` separately reported a 536870912-byte iGPU VRAM aperture; no inference was made to reconcile those two interfaces.

### 7–10. Warm start, stamps, inventory, and prune safety

- Warm `./mf.sh serve` logged `core requirements unchanged; skipping pip` and reached HTTP readiness in 0.277 seconds.
- A real health request took 0.001537 seconds; repeated requests were 0.001487 and 0.001473 seconds, all below the three-second contract.
- Adding one line to top-level `requirements.txt` caused the next start to log `installing core dependencies`. Restoring the final file caused one final install, and `.venv/.req-stamp` exactly matched the final requirements SHA-256 `875d8f1916f28b5f0e3f98c0302a3664ae21e9a1e671ee1512ab24881fa0ca40`.
- A deliberately non-executable/missing core `bin/python` was detected as broken. `mf.sh` removed only the approved core venv path, rebuilt it, and the resulting real service returned HTTP 200 in 0.001473 seconds.
- With `auto_provision=true` and the runtime stamp retreated, `mf.sh serve` logged the runtime name, 2100000000-byte estimate, 802764632064-byte capacity result, and started a lock-protected background build. It restored the stamp, reran the real GPU operation, and reported a zero-byte pip-cache delta. With `auto_provision=false`, the same missing-stamp setup did not build, remained `setup_required`, and exposed the manual build action.
- Final `./mf.sh env list` output:

```text
core       state=current size_bytes=116345980 refs=-
rocm-torch state=current size_bytes=4445904539 refs=image
```

- `./mf.sh env prune` printed `keeping rocm-torch: referenced by image`; size remained 4445904539 bytes. Core was never a prune candidate.
- With a temporary required capacity of 9999999999999 bytes, build exited 1 before installation, reported the actual 802764906496 bytes available, preserved runtime size and stamp, and exposed `rocm_runtime.state=error` in the health snapshot. The committed requirement was restored to 8589934592 bytes.

### 11. Shared cache evidence

The runtime used ControlDeck's configured cache root without importing or executing ControlDeck code. The two largest downloaded wheels were present in that shared pip cache:

```text
torch body:  1645259227 bytes, mtime 2026-08-21 08:00:13.355694214 +0900
triton body:  301690151 bytes, mtime 2026-08-21 08:00:44.899307331 +0900
pip cache:   2369228186 bytes total after the run
HF_HOME:     /data1tb/ControlDeck/data/cache/huggingface
HF dir mtime: 2026-08-18 08:13:25.254909152 +0900
```

No model was downloaded in MF0-0, so `HF_HOME` contained no new file and its mtime did not change. Model-cache reuse is therefore NOT TESTED rather than inferred. A warm runtime rebuild reported `pip cache delta: 0 bytes`.

Explicit user cache values were preserved exactly. Running doctor with `/tmp/mf00-user-{pip,uv,hf}` values printed those same paths and did not create them. With all cache variables unset and an unreadable ControlDeck config, doctor warned and selected Media Forge's own `data_dir/cache/{pip,uv,huggingface}` paths.

### 12. Persistent-data independence

No data was deleted. Canonical paths and filesystems were observed as:

```text
Media Forge: /home/souten/.local/share/control-deck-media-forge
             /dev/sda2, device 2050
ControlDeck: /data1tb/ControlDeck/data
             /dev/nvme0n1p1, device 66305
media_inside_controldeck=no
controldeck_inside_media=no
```

The Media Forge path still contained `media-forge.sqlite3`, `assets/`, and `work/`. Thus deleting either configured tree cannot select the other tree by containment. This is the requested non-destructive path proof; actual deletion was intentionally not performed.

## Additional behavior checks

- Temporarily removing the GPU snapshot left the real core service running. Health returned HTTP 200 / `setup_required`, with `gpu.state=checking`; restoring and rerunning the GPU check returned it to `ok`.
- Latest focused `./mf.sh test`: 37 passed in 1.40 seconds with one upstream Starlette/httpx deprecation warning. Core and runtime `pip check` both reported no broken requirements. This is regression evidence only, not runtime proof.
- `bash -n mf.sh` and `git diff --check` passed. These are static checks only.
- Final ControlDeck checkout observation: HEAD `9272c05`, clean `git status --short`. It was read-only throughout this slice; no ControlDeck file was modified.

## NOT TESTED / intentionally deferred

- Worker-pack enable/disable mutation of `.refs`: no worker-pack lifecycle is present yet. The current non-empty reference and prune protection were tested.
- Hugging Face model download/cache reuse: no model adoption or weights belong to MF0-0.
- Model library configuration: deliberately remains `missing`; selecting and benchmarking a model belongs to G1.
- FOUC video/frame capture is NOT TESTED. First rendered workspace state was visually inspected after the handshake, but no frame-by-frame white-flash measurement was made.
- OpenCode discovery is NOT TESTED. Agent tool invocation through the real ControlDeck API and its ControlDeck Job response were tested, but no OpenCode process was involved.
- Workflow dry-run is UNAVAILABLE because the referenced host omits the fail-closed unavailable executor.
- Files context invocation is tested; scoped staging/commit and automatic workspace route opening are UNAVAILABLE with the referenced host bridge/UI behavior.
- Resource acquire/wait/renew/release, two fake exclusive jobs, Jobs bridge progress/toast, scoped file staging/commit, and disable cleanup are UNAVAILABLE in the referenced host revision, not passed or substituted.

## Scope boundary

No real model or Diffusers adapter is included. The embedded workspace and the host-permitted MF0-7 browser paths are verified, but MF0-4 and the bridge-dependent MF0-7 paths remain incomplete for the explicit host-contract reasons above. The ROCm runtime check is environment qualification only and is not a model benchmark or a G1 implementation.
