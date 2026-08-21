# Media Forge implementation status

Date: 2026-08-22
Scope: MF0-0 through MF0-7 complete; G0 and G1 complete (`docs/implementation/mf0-addon-core.md`)
Repository head at final MF0-7 verification: `8c6ab98382f43db8a58ff1dcf7dc6fcde113968a` (`origin/main`)
Repository head released and verified for G1: `1e88472e753fd484638f072f7c4b327c8010ab60` (`v0.1.2`)

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

## MF0-4 — COMPLETE

ControlDeck upstream `main` was re-audited at
`f86cb82055bc0d572c6ec8f91fc956834aaf4dc9`. Its Add-on Runtime provides
token introspection plus scoped Jobs, resource, grant, and output APIs. Media
Forge uses only those HTTP contracts: it imports no ControlDeck module, receives
no session cookie, and no longer provisions or reads the Host signing key.

Incoming credentials are introspected at
`/api/v1/addon-runtime/token/introspect`. Media Forge then verifies active state,
`addon_id=media-forge`, nonempty subject, expiry, maximum lifetime, and granted
capabilities. Credentials are excluded from object representations and Host
errors do not include response bodies. Raw Unix/Windows/file-URI paths remain
recursively rejected; file content moves only through opaque `grant:` and output
IDs.

Hosted generation now creates or attaches a ControlDeck Job before admission,
requests a real Broker lease before entering the worker-local execution guard,
reports all four VRAM dimensions plus `estimated_runtime_sec`, activates and
renews the lease, observes Host cancellation, and releases or cancels Broker
state in `finally`. ControlDeck forces the request owner to
`addon:media-forge`; Media Forge does not send a caller-selected owner. Attached
agent Jobs leave terminal ownership to ControlDeck's outer runner, while Jobs
created for the workspace are terminalled by Media Forge. Host-managed queued
jobs are failed with `host_context_lost` after restart instead of resuming
without their short-lived authority.

Real-process verification on 2026-08-21 used disposable ControlDeck and Media
Forge data directories, the public ControlDeck API, the real AMD GPU Broker,
and separate loopback processes:

```text
agent generation: HTTP 200 in 0.648 sec
ControlDeck Job: 3151f0d8aacf / succeeded / register_asset / 1000 of 1000
Broker lease: c088e41f... / gpu0 / owner addon:media-forge / released
reservation: 335544320 bytes / exclusive-preferred
two concurrent jobs: first granted; second waiting / device_busy_exclusive / queue 1
completion times: 1.685 sec and 2.327 sec; all leases released
Host cancel: running Job 015c881fe14e -> canceled; active lease -> released
10 sec job: HTTP 200 in 10.671 sec; lease.renewed delta 1
scoped file roundtrip: 31 input bytes -> 31 output bytes; content identical
file transport response: grant/output/asset IDs and metadata only; no path
```

The fake worker is CPU-only, but the MF0 contract deliberately acquires a small
real GPU reservation so the complete admission/renew/cancel/release lifecycle is
exercised before G1 substitutes a GPU worker. Two-job contract testing also
confirmed that only one worker subprocess runs while the second job waits for
Host admission.

The initial real-process run found that Workflow and Context Action correlation
subjects could not prove their initiating user to the Runtime API:

```text
workflow executor token subject = workflow:<execution_id>
  Add-on Runtime Jobs/Resources accept numeric user or job:* subjects only
context action token subject = context:<user_id>
  Add-on Runtime Grants accept numeric user or job:* subjects only
```

No Media Forge fallback was added. The generic Host boundary was instead fixed
on merged ControlDeck PR #212 (`2dad80b3`) by separating signed `actor_user_id` from the correlation
subject and binding real Runtime grants through an exact per-call `grant_ids`
allowlist. Media Forge then removed both fail-closed availability blocks, runs
Workflow generation through the same leased Host Job path, and consumes the
actual Context Action read grant without receiving or reflecting a path.

Current exact-code real-process acceptance used ControlDeck main `2dad80b3` and
Media Forge `e0f4b89`, isolated ControlDeck／Media Forge data, separate Uvicorn
processes, the public Host API, and the real AMD GPU Broker. The complete run
took 20.199074 seconds:

```text
discovery: workflow executor 1, context action 1
workflow dry-run: Media Forge Job delta 0
workflow execution: SUCCEEDED; generated Media Forge Job succeeded
context file: 1206-byte 48x48 RGBA PNG validated through Runtime grant; path/grant reflected false
normal generation: 0.627521 sec; 335544320-byte gpu0 reservation; lease released
two concurrent Jobs: second device_busy_exclusive / queue 1; both leases released
Host cancel: Job canceled; lease released
10-second Job: 13.094774 sec wall time; lease renew delta 5; lease released
scoped read/output: 1206 bytes; SHA-256 identical; Host asset committed
disable while active: Job canceled; lease released; re-enable healthy
```

The driver removed its temporary Workflow and uninstalled the Add-on in
`finally`. The isolated services and directories are removed after evidence
collection. No ControlDeck module, cookie, signing key, or path crossed into
Media Forge. Final `./mf.sh test` completed with 51 passed in 3.38 seconds;
this is regression evidence, not a substitute for the real-process run above.

## MF0-5 / MF0-6 / MF0-7 — COMPLETE

The embedded workspace provides Create, Library, Jobs, Models, and Settings without localStorage, sessionStorage, cookies, or parent DOM access. It waits for the MessageChannel handshake before first paint, validates the parent origin, applies initial/theme-change tokens without reload, handles locale/safe-area/route/session/disable events, syncs routes, updates the title, exposes the command-palette shortcut, and clears busy state on disable. Standalone rendering remains available when the page is not framed.

Workflow, agent capability/generate/inspect, command, and edit-image context endpoints are implemented with service-token enforcement and structured job/asset responses. Capability discovery and all agent tool responses contain no model name; inspect returns the license, lineage, validation, warnings, and output hash without implementation identity. Context responses do not echo the scoped token.

The first installed-host attempt exposed three real integration defects that
unit/static checks had not detected: health reason codes outside ControlDeck's
closed enum, 401 responses for external iframe CSS/JS, and 401 responses to
opaque-origin iframe HTTP API calls. The implementation now uses only host
reason codes, serves the trusted workspace CSS/JS inline, and carries bounded
structured workspace RPC over ControlDeck's nonce-bound authenticated WebSocket
proxy. Raw paths are rejected on that transport and asset previews are capped at
12 MiB before base64 encoding.

Final installed-host browser verification used ControlDeck PR #213's exact tree
(merged as `a5e4fc7`), isolated ControlDeck and Media Forge data directories,
real loopback processes, Chromium at 1280x800 and 320x700, and installation
through ControlDeck's public Add-on API. The reusable driver was
`scripts/mf0_control_deck_e2e.py`; it deleted its temporary Workflow and always
uninstalled the Add-on in `finally`. The final run completed in 15.162338 seconds
with zero browser console errors and zero page errors. Observed results:

```text
disabled: Media navigation absent
setup_required: setup dialog and missing model library visible
healthy: Media navigation and opaque iframe workspace visible
workspace initial paint: Host iframe invisible and themed connection overlay visible before response
workspace transport: bridge ready; Create produced one fake asset and one succeeded Host Job; Library preview rendered
theme: light -> dark applied without reload; in-frame marker survived
route: Library back / forward / reload / share URL preserved
Files: real scoped image grant read; edit-image opened /x/media-forge/workspace/create
agent API: media.capabilities returned ControlDeck job_id=6559bae30693 and asset_id=job-result:6559bae30693
agent response: no model_id, fake implementation name, FLUX, or Qwen string
workflow: media.generate discovered; dry-run Media Forge Job delta 0; real execution SUCCEEDED
Broker: second fake GPU Job waiting / device_busy_exclusive / queue 1; both Jobs succeeded
disable: iframe and all executable contributions removed; saved Workflow remained readable
re-enable: all pre-disable assets remained visible
mobile 320px: companion rendered and iframe remained absent
```

The run ended with Broker active 0 / waiting 0 and all four observed leases in
`released`. The FOUC assertion uses a test-only, process-once, maximum-two-second
workspace response delay; normal mode is zero and cannot enable the hook unless
test endpoints are explicitly enabled. The assertion captured the actual Host
iframe as `invisible` with its connection overlay visible before the delayed
workspace response, then observed the bridge becoming ready.

Check J was completed after the generic Host projection shipped in ControlDeck
PR #214 (merge `60ab09d8`). No Media-specific route, dependency, tool, or
capability was added to ControlDeck. An isolated ControlDeck process generated a
0600 OpenCode runtime config whose local stdio MCP projected the current effective
Add-on agent tools. External OpenCode 1.18.18 reported
`controldeck_addons connected` and discovered these three public contributions:

```text
media.capabilities
media.generate
media.inspect
```

The stdio MCP called `media.capabilities` through the real Host endpoint and
received ControlDeck Job `4aa6c2f74ae9` plus opaque asset ID
`job-result:4aa6c2f74ae9`. With that token still alive, disabling Media Forge
changed discovery from 3 tools to 0; re-enabling changed it from 0 to 3. This
proves discovery is based on current Host availability rather than a stale
startup snapshot.

Finally, a real `opencode run` process called
`controldeck_addons_media_capabilities` exactly once, received Host Job
`7966ff194635`, and replied `available`. The process exited 0 in 19.5 seconds.
The tool result contained capability names and fake availability metadata but no
`model_id`, model field, FLUX, or Qwen identity. The first `auto` attempt started
the local 27B model but did not reach a tool call within five minutes; it was
interrupted and is not counted as success. The bounded retry used the already
loaded local model with minimal reasoning and completed.

After verification, Media Forge was disabled and uninstalled through the public
Host API. The isolated Host and Media Forge processes, ports 18770/9134, and the
Qwen3.8-27B instance started for this check on port 8097 were stopped. The
token-bearing runtime config and login cookie were deleted.

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
- Latest full `./mf.sh test`: 52 passed in 3.37 seconds with one upstream Starlette/httpx deprecation warning. Core and runtime `pip check` both reported no broken requirements. This is regression evidence only, not runtime proof.
- `bash -n mf.sh` and `git diff --check` passed. These are static checks only.
- ControlDeck's generic Context Action route gap was fixed and merged separately
  in ControlDeck PR #213 (`a5e4fc7`). No Media-specific route, action, dependency,
  or implementation module was added to the Host.

## NOT TESTED / intentionally deferred

- Worker-pack enable/disable mutation of `.refs`: no worker-pack lifecycle is present yet. The current non-empty reference and prune protection were tested.
- Hugging Face model download/cache reuse: no model adoption or weights belong to MF0-0.
- Model library configuration: deliberately remains `missing`; selecting and benchmarking a model belongs to G1.
- ControlDeck Jobs creation, Broker waiting reason, and lease cleanup were
  observed through the real Host API during the browser run. Dedicated visual
  inspection of the Jobs/Broker detail screens and their cancel controls remains
  NOT TESTED.
- Hosted service-shutdown failure and lease cleanup are covered by contract tests
  but not a separate current real-process crash run. Active disable, Host cancel,
  and their lease releases were measured through public APIs.

## Scope boundary

MF0-0 through MF0-7 / G0 and G1 are complete. The real image route, R9700
acceptance evidence, and trusted release-bundle standard installation path were
exercised end-to-end. Media Forge PRs #10/#11/#14 and ControlDeck's generic provider
PRs #216/#217/#219 are merged. G2 and later have not started.

## G1 — local image generation (COMPLETE, 2026-08-21)

### Adopted route and model gate

`black-forest-labs/FLUX.2-klein-4B` at immutable revision
`e7b7dc27f91deacad38e78976d1f2b499d76a294` is installed in the shared NVMe
Hugging Face cache and is the measured automatic `image.text_to_image` route.
The pinned weight set is 15,964,212,614 bytes; the cache repository occupied
15,988,907,862 bytes. A repeated `./mf.sh model download flux2-klein-4b`
completed in 0.36 seconds with 51,144 KiB maximum RSS and did not re-download
weights. The provenance weight identity is
`sha256:f3fcfa8fdaf5ebcd26c33cd53b485ec5ebe54939b5ace585b3f488278dfae278`;
license is Apache-2.0. `docs/models.md` records all ten adoption-gate answers.

The production registry exposes only `image.text_to_image`, state `available`,
installed/healthy true, and confidence `measured`. `model_id` remains optional
and internal routing still accepts `auto / fast / balanced / quality /
low_vram / manual`. Premature edit capabilities were removed rather than
claiming G2 behavior.

### Cold-load diagnosis and bounded optimization

Media Forge uses Diffusers, not ComfyUI, so ComfyUI Dynamic VRAM flags were not
applicable to this route. The directly observed slow path was CPU/mmap loading
followed by `pipeline.to("cuda")`: one 512x512 job took 852.587283 seconds.
`device_map="cuda"` alone was still over 142.209076 seconds when canceled, and
Diffusers-only mmap disabling still left the Qwen3 text encoder loading after
353.455380 seconds when canceled.

The adopted adapter explicitly loads `Qwen3ForCausalLM` and the FLUX pipeline
with direct device placement and mmap disabled. Equivalent jobs then measured
37.284804 seconds on the first optimized attempt, 25.762736 seconds on the
second, and 14.936748–15.789333 seconds after cache/compiler warm-up. Enabling
Hugging Face parallel loading reduced measured 512 load from 11.508421 to
10.589401 seconds (about 8% of load time); it is retained as a secondary
optimization, not described as the root fix. Persistent NVMe Hugging Face,
AMD COMGR, and MIOpen cache paths are exported by `mf.sh`.

On 2026-08-22 the direct route was hardened against silent regression into
offload. After load, the worker inspects component devices, device maps, and
Accelerate hooks; `direct_device_map` fails rather than succeeding if any
CPU/disk/meta target or CPU/offload hook is present. The final real Workflow /
Broker run completed in 15.049693 seconds (load 10.426083, generation 1.487908)
with pipeline, text encoder, transformer, and VAE all on `cuda:0`, zero offload
hooks, zero non-GPU targets, a released lease, and a 168,170-byte PNG.

The bounded `cpu_offload` comparison completed in 40.504328 seconds on its first
valid run (load 25.533552, generation 7.037108; sampled incremental peak VRAM
8,879,714,304 bytes) and 18.069923 seconds after cache warm-up (load 9.655885,
generation 4.586891). It left all four components on CPU between calls and the
worker detected offload hooks on the text encoder, transformer, and VAE. A
separate direct sample used 21,819,142,144 incremental bytes. Identical seed and
settings produced the same SHA-256 on both routes. The first aggressive-observer
attempt that caused `host_unreachable` is excluded, not relabeled as a model
failure. These observations retain direct placement as default; offload is a
low-VRAM diagnostic tradeoff rather than a speed fix.

This hardening is released as v0.1.2. Relative to the frozen v0.1.1
contract, `addon.json` changes only its release version; contribution IDs,
schemas, agent/workflow inputs, and required asset/provenance fields are
unchanged.

The public GitHub Release artifact
`control-deck-media-forge-0.1.2-linux-x86_64.tar.gz` is 29,043,648 bytes with
SHA-256 `855303fd90e25e2ff2886b255fd98365c862eb417e0e57268cb0e8a27c06916c`.
Its release digest, downloaded file, and ControlDeck trusted-catalog pin agree.
The archive contains neither a venv nor model weights; its packaged provision
reused the persistent runtime/model cache and completed in 4.972467 seconds.

ControlDeck PR #219 installed that exact public bundle through the standard
release-bundle provider in 18.375702 seconds. A real Workflow/Broker generation
then completed in 13.327802 seconds (load 9.265287, generation 1.483399), with
all four inspected components on `cuda:0`, no offload hooks or non-GPU map
targets, and the lease released. A final exact-PR-head Chromium run traversed
Settings disable/enable, the opaque Media iframe, Models, Create, Library, and
Provenance in 16.2 seconds with zero page errors. Its separate image job took
12.888887 seconds (load 9.013070, generation 1.458398), again with direct GPU
placement and zero active/waiting Broker work afterward.

A fully empty Hugging Face cache download of approximately 15.99 GB remains
NOT TESTED. The release download and warm persistent-cache reuse above are not
presented as empty-cache model-download evidence.

### R9700 measurements and lease envelope

All measurements below used the AMD Radeon AI PRO R9700 / gfx1201, ROCm, local
NVMe, four inference steps, and a separate PyTorch worker process:

```text
1024x1024 first product job:       208.820067 s (included first kernel compilation)
1024x1024 repeated product job:     18.009386 s
1024x1024 parallel-loading repeat:  17.933032 s
  adapter load / generation:        11.344260 / 3.537276 s
512x512 committed-manifest job:     15.031645 s
  adapter load / generation:        11.140961 / 1.471561 s
worker peak RSS:                    16,384,692,224 bytes
worker peak swap:                   0 bytes
resident VRAM:                      0 bytes
execution peak VRAM:                29,625,200,640 bytes
cold-load peak VRAM:                32,275,578,880 bytes
headroom:                            1,073,741,824 bytes
broker reservation:                33,349,320,704 bytes
R9700 total VRAM:                   34,208,743,424 bytes
```

The static lease estimate conservatively uses the worst observed cold-load
peak. Every measured success acquired a Host lease, declared
`estimated_runtime_sec=208.820067`, renewed it, and released it. Eight requested
optimized generations completed without an unrequested failure. The two slow
diagnostic variants were explicitly canceled and are not counted as failures.

### Real product behavior

- The same prompt/settings/seed produced byte-identical 512 and 1024 pairs.
  The 1024 sample SHA-256 is
  `bf83e5941312a6221b13b5c604876ba6b4ea2322c60b4265472f5d756ccdc162`.
- The requested adult tomboy anime character with orange mesh hair was generated
  by Media Forge itself. The retained 1024 asset is
  `/data1tb/mediaforge-g1-e2e-XOqcbh/media-optimized-final/assets/asset_4134e5db722a401e9cac8d5106277f6a.png`.
- An installed-host Playwright run completed Create -> ControlDeck Job -> Library
  preview -> provenance in 17.551425 seconds. It observed a succeeded Host job,
  a 512x512 asset, the real model/hash/license, and zero console/page errors.
- Host cancellation at two seconds ended the Media job as `canceled` in
  2.5947 seconds and left zero active leases.
- SIGKILL of the sole real worker PID during a leased 1024 job was normalized to
  `worker_crash` (`worker exited with code -9`) in 2.431407 seconds. The lease
  count returned to zero and the core remained `healthy`.
- With a live 15,891,902,464-byte llama.cpp model, managed Broker policy retained
  chat availability (`READY`) and placed the image request in `waiting` with
  reason `yield_load_cost_unknown`, queue position 1, cancel/lower-priority
  actions, and the LLM identified as a yieldable blocker. It did not silently
  overcommit or kill chat merely to satisfy the image request.
- Latest full Media Forge regression run: 80 passed in 3.95 seconds with one
  upstream Starlette/httpx deprecation warning. This is regression evidence,
  not the runtime evidence above.

### Release-bundle standard installation

GitHub Release `v0.1.1` publishes the verified linux-x86_64 artifact used by the
trusted ControlDeck catalog. It is 29,041,267 bytes with SHA-256
`66dfb88425d61e533e5ca8b45e0e19169e07e66cbc9ba1846364de4177981d4a`.
The bundle contains the packaged core and pinned runtime recipe, but no source
checkout, prebuilt venv, PyTorch wheels, or model weights. Its `provision`
lifecycle builds the persistent worker venv and verifies GPU/model readiness
before the provider can select the version.

An isolated real ControlDeck updated the public v0.1.0 bundle to v0.1.1 in
37.914599 seconds. During provisioning, `current` and PID 1599352 remained on
v0.1.0. After smoke/health, both version trees remained and `current` switched
atomically to v0.1.1/PID 1627743. The persistent ROCm venv occupied
4,686,979,949 bytes; the shared NVMe pip/model caches were reused. Health
reported R9700/gfx1201, PyTorch 2.10.0+ROCm 7.2.1, and an installed/healthy
model.

A post-switch health-gate fault injection exercised rollback through the real
version tree, systemd service, and Add-on registry. `current`, the running
service, and the enabled manifest returned to v0.1.0 in 10.4 seconds; a normal
API update then restored healthy v0.1.1. This is an explicit health failure
injection, not a claim that a public release was naturally unhealthy.

The installed v0.1.1 bundle generated through the real ControlDeck
Workflow/Broker path. It acquired a 33,349,320,704-byte lease, renewed it six
times, released it, and produced a 512x512 PNG of 128,589 bytes with SHA-256
`9a1920654a48007c4917385d05af43a82d144803c66c19cefb906a9e93be962e`.
Its provenance identifies FLUX.2 Klein 4B, Apache-2.0, and Media Forge 0.1.1.
A Chromium Settings -> enable -> Media -> Create -> Library -> Provenance run
also produced a 159,515-byte PNG, passed in 19.5 seconds, and observed no page
errors or active lease after completion.

The isolated uninstall stopped and removed the managed service, disabled and
unregistered the Add-on, and removed `current`, `versions`, and `downloads`.
The provider reported `installed=false`, `enabled=false`, `not-installed` and
required no Host reload. Persistent feature data remained exactly
4,687,592,191 bytes / 8 files, including both generated PNGs (128,589 and
159,515 bytes); the worker runtime and shared cache were not deleted.

After the lifecycle environment was hardened and ControlDeck PR #217 was
merged, its exact provider contents were run again against the isolated host.
Install job `de4cf085cfd3` completed in 11.521913 seconds from persistent warm
runtime/cache state and returned v0.1.1 / healthy; the live service again
reported R9700/gfx1201, ROCm 7.2.1, and model installed/healthy. A second real
uninstall returned `not-installed` and left the same 4,687,592,191 bytes / 8
files. This closes the gap between the pre-hardening runtime evidence and the
merged provider implementation.

Media Forge full regression at the released code completed with 80 passed in
8.01 seconds. ControlDeck provider final-head regression completed with 738
passed / 1 skipped in 61.79 seconds, frontend production build transformed
1,542 modules, and the installed-bundle browser E2E passed. These are regression
evidence and do not replace the real process observations above.

### G1 public contract freeze

The public contract is frozen at Media Forge commit `b29cec0` / release v0.1.1.
The freeze covers `schemas/*.json`, `addon.json` contributions, agent tool and
workflow executor names/inputs, and required asset/provenance fields as
documented in `docs/api.md`. The recorded SHA-256 values are:

```text
addon.json                    30d1c9f64c7069eb556cc9ef1bf10bc1fc508855c1a32ca98d32fed6bd1d2583
asset-reference.json          76bcdf271278cc206d1595a8ea5d96737382d9ed2c8649ea9856acfac5c7147b
asset.json                    51903d157035ccb75e6384ea4fb63b5180e847be1890cecc3a8560bd61510241
empty-input.json              c26eb030dfc9f52409427dd4e03b4dc270b2151d534e864ac546531607d753af
job-reference.json            41191771b145ff3984e658622a57d1d6d154fb608b54e139ed02f44f761c34ab
job-request.json              e5f42b412f39f37e3435717aba4a1ba0af15e99d25bcfaef89a179151ced43f4
model.json                    a1495f9f2ee395a1865fbcd73a8a77baf2e8a1a9eaefec918d8412884a963234
provenance.json               9579f96c0921176617474867515b1797cb68aa0a62c3dbd8c1bbb5d1f89b8697
```

Future goals may add capabilities or optional fields. A breaking change first
requires the documented impact, migration, and contract/schema version bump.

### NOT TESTED / intentionally deferred

- A kernel page-cache drop was intentionally not performed on the shared host;
  fully cache-cold storage timing is NOT TESTED.
- Qwen-Image fallback was not downloaded or benchmarked because the adopted
  route passed the measured gate.
- A natural hardware OOM is NOT TESTED. Error normalization and admission-floor
  adjustment are covered by tests; unsafe oversized requests are rejected by
  model limits before lease acquisition.
- A fully cache-empty download of the pinned 15.99GB model is NOT TESTED. Both
  direct bundle provisioning and the ControlDeck update reused the verified
  shared NVMe model cache; this is not reported as cold-download evidence.
- The installed-bundle Settings/Create E2E used a 1280x800 Chromium viewport.
  A separate 320px mobile Settings layout run is NOT TESTED; Media uses the
  declared companion surface rather than squeezing the workspace into mobile.
- G2 strict edit, G3 character consistency, and G5 M5Stack expression/gesture
  variants are NOT TESTED and were not started out of roadmap order.
