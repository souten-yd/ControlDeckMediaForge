# Media Forge implementation status

Date: 2026-08-26
Scope: MF0-0 through MF0-7 and G0 through G6 complete; G7 V0 complete, V1 adoption deferred; G8 B0-B4 complete

G8 planning started on 2026-08-26. The current host has no `blender` executable. The implementation order,
license/process boundary, GLB-only first import, deterministic compiler/package, typed options, and installed
acceptance are fixed in `docs/implementation/g8-blender-production.md`. Blender execution, GLB import, worker,
workspace, agent placement, and installed acceptance are **NOT TESTED** at this point.
Planning gate: `./mf.sh test` reported `711 passed, 1 warning in 48.10s`; `git diff --check` passed.
Repository head at final MF0-7 verification: `8c6ab98382f43db8a58ff1dcf7dc6fcde113968a` (`origin/main`)
Repository head released and verified for G1: `1e88472e753fd484638f072f7c4b327c8010ab60` (`v0.1.2`)

## Video model candidate catalog — IMPLEMENTED, SNAPSHOT VERIFIED

Wan 2.2 TI2V-5B／I2V-A14B／T2V-A14B／Animate-14B、LTX-2.3、HunyuanVideo-1.5の
exact revisionとbounded checkpoint identityを、既存Model Registry／Model Managementへ追加した。
全候補は`experimental`、recommended profileなしであり、R9700向けavailable/defaultや動画worker実装を
主張しない。Wan TI2V-5B だけは 2026-08-26 の bounded R9700 probe 後に resource measurement
confidence を `measured` としたが、品質 gate は不合格で unavailable のままである。その他は
measurement confidence `low`、ROCm未実測。runtime packageまでsnapshotが閉じるWan生成3件だけを
managed download対象とし、Animate／LTX／Hunyuanはexternal ownerとしてbackendでもdownloadを拒否する。
UIは動画候補filter、実験的表示、外部runtime所有表示を追加し、別の動画モデル管理APIは作っていない。

ローカル自動検証はcatalog／manager／frontend集中46件成功、`./mf.sh test`全274件成功（23.54秒）。

実model download: 製品のdurable installerを並列1で使い、Wan 2.2 TI2V-5Bのfixed revision
`921dbaf3f1674a56f47e83fb80a34bac8a8f203e`を取得した。operation
`modelop_0164bf6e9d79411b87bfe97c2c0c9f3d`は2026-08-22 18:12:50 JSTから19:15:16 JSTまで
3,745.295068秒で、34,201,521,212／34,201,521,212 bytes、errorなし、`ready`となった。download中は
partialが`.downloads/<operation_id>`内だけにあり、全取得後に`verifying`を経てsnapshotへatomic配置された。
平均転送量は約9.13 MB/sで、配信帯域の一時低下は観測したがretry/errorは観測しなかった。resumeは実中断を
行っていないためNOT TESTED。

初回の開発CLIはtracked configのhome既定を使い、root filesystemへ一旦配置した。これはNVMe証拠として採用せず、
同一filesystem上の実運用store
`/data1tb/ControlDeck/data/feature-data/media-forge/data/models`へcopy後、5 weight全てのsizeとSHA-256を
独立再計算した。34,201,521,212 bytesの全weightがcatalogと一致し、required file 7件とrevisionも一致した
（25.66秒、最大RSS 31,768 KiB）。その後registryはWanを`managed/removable/installed`、既存共有FLUXを
`external/installed/available`として同時に検出した。home既定model pathはこのNVMe storeへのsymlinkに切り替え、
root filesystem使用率は89%から77%へ戻った。誤配置元の同一copyは削除せず
`/data1tb/mediaforge-recovery/root-misplaced-Wan2.2-TI2V-5B-20260822`へ退避している。

Wanの主用途はText-to-Video／Image-to-Video、規模は5B、R9700の第一評価候補である。snapshot取得時点では
ROCm runtime動作は NOT TESTED だったが、2026-08-26 の G7 V1 で bounded T2V を実測した。
現在は hardware backend に ROCm、resource measurement confidence `measured` を記録する。一方、
stateは`experimental`、healthy=false、recommended profileなし、公開 capability unavailable を維持する。
詳細と不採用理由は末尾の G7 V1 節を正とする。

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

MF0-0 through MF0-7 / G0 through G2 are complete. The real image route, R9700
acceptance evidence, and trusted release-bundle standard installation path were
exercised end-to-end. Media Forge PRs #10/#11/#14 and ControlDeck's generic provider
PRs #216/#217/#219 are merged. G2's measured editing and bounded semantic-review
evidence is recorded below. G3 and later have not started.

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
- G3 character consistency and G5 M5Stack expression/gesture variants have not
  started out of roadmap order.

## G2 — image editing (COMPLETE, measured 2026-08-22)

The existing frozen `image.edit` operation now accepts exactly one imported
source asset plus `strict_edit=true` and an `editable_mask_asset_id`. Imports
are bounded PNG/JPEG byte streams; neither the public API nor the opaque
workspace transport accepts a filesystem path. Masks are canonical RGBA PNGs,
must match the source, and empty/full masks fail explicitly before GPU
admission.

The worker sends only the bounded mask crop to the model. Core then composites
the patch, recopies protected pixels from the immutable source, and runs an
independent RGBA-channel comparison. Any protected-pixel difference produces
`strict_edit_invariant_failed` and no asset. Provenance records source and mask
hashes; lineage contains the source as the parent. No schema or Add-on
contribution changed after the G1 freeze.

Real R9700 acceptance used isolated Media Forge and ControlDeck data, the
installed-host agent route, a real Broker lease, the retained Media Forge G1
anime character, and a 10,179-pixel mouth mask:

```text
first accepted edit:       17.772403 sec (load 9.037687, generation 5.164945)
same-seed repeat:          13.942717 sec (load 9.045363, generation 1.394409)
third-generation edit:     14.959 sec (load 10.085912, generation 1.329025)
protected pixel changes:   0 in every accepted output
editable pixels changed:   10,154 of 10,179
same-seed output hash:     identical
three-generation lineage: source -> edit -> re-edit
sampled worker peak RSS:   8,743,202,816 bytes
sampled worker swap:       0 bytes
sampled absolute VRAM use: 17,898,610,688 bytes
lease after completion:    active 0 / waiting 0
invalid full mask:         failed / invalid_edit_mask / asset count 0
```

The first real attempt found a product defect rather than producing accepted
evidence: the worker completed in about 27.4 seconds but the agent endpoint's
25-second bounded wait returned 504 first. The wait is now 110 seconds, below
the Host's 120-second generic execution timeout; three later runs passed. This
failed attempt is not counted as a successful generation.

Installed-host Chromium then exercised Create operation selection, chunked
source/mask upload through the authenticated opaque iframe transport, real edit,
Library, and provenance. It completed in 17.786943 seconds, added exactly three
assets, observed protected difference 0 and editable pixels 10,179, and recorded
zero console/page errors. After the final fail-closed/upload-cleanup audit, the
exact branch was restarted and the same browser route passed again in 32.869204
seconds (adapter load 9.219171, generation 17.133812), again adding exactly
three assets with protected difference 0 and no browser errors. Evidence is
retained at `/data1tb/mediaforge-g2-e2e.Frwz2w/browser-final/`.

The host had approximately 3.9 GB of globally allocated swap during diagnosis,
mostly stale pages from unrelated long-lived processes. Media Forge worker swap
was zero and `vmstat` showed no sustained swap-out. RAM shortage/pagefile
thrashing is therefore not the cause of the observed 12-minute-class G1 load;
the measured direct-placement/mmap path remains the applicable fix.

Focused strict-edit, worker, adapter, and host-transport regression completed
with 49 passed. Full `./mf.sh test` completed with 101 passed in 5.41 seconds.
These are regression evidence only; the product evidence is the real
process/browser run above.

### Outpaint

Outpaint remains the existing `image.edit` operation with
`edit_mode=outpaint`, `strict_edit=true`, and a larger target canvas. It accepts
no mask because the exterior region is derived deterministically. The source is
centered, recopied after model generation, and independently checked before
registration. Crop-sized, unchanged-sized, non-multiple-of-16, non-strict, and
caller-mask combinations fail before worker execution.

A real installed-host Chromium run extended the retained Media Forge-generated
512x512 anime character to 768x512:

```text
first browser total:        108.756109 sec
  load/generation:           10.742962 / 92.188142 sec
warm separate-worker total:  19.807051 sec
  load/generation:           10.774391 / 3.397528 sec
source RGBA differences:     0 across 262,144 pixels
generated exterior:          131,072 pixels
same-seed repeat:             byte-identical 281,762-byte PNG
lineage:                      imported source -> outpaint result
browser errors:               0
placement/offload:            all cuda:0 / hooks 0 / non-GPU targets 0
Broker after each:            active 0 / waiting 0
```

The first route-specific compile cost is recorded rather than hidden. The warm
run came from a new worker process and reused persistent NVMe/ROCm caches.
Visual inspection found the entire character unchanged and the gray background
continued naturally into both generated side regions. Evidence is retained at
`/data1tb/mediaforge-g2-e2e.Frwz2w/outpaint-browser/` and
`outpaint-browser-warm/`.

Focused outpaint/edit/adapter/API/host regression completed with 85 passed.
Full `./mf.sh test` completed with 118 passed in 9.65 seconds. These are
regression evidence only.

### NOT TESTED / remaining limits

- Natural OOM during edit is NOT TESTED. Existing conservative G1 lease values
  remain in use; the sampled absolute VRAM value is not substituted for the
  lease envelope.
- A 60-second Host iframe proxy read bound returned 502 before the intentionally
  failing 108-second two-candidate semantic review reached its terminal state.
  The durable Media Forge and ControlDeck Jobs continued, stopped at the stated
  retry budget, and released the lease. Long synchronous agent-tool UX belongs
  to G4 and is not claimed as solved by G2.
- No release version is assigned by this source-development slice.

### Single-reference edit, inpaint, and variation

PR #16 merged the strict masked compositor and validator as Media Forge main
`18960a8`. The next additive slice keeps `image.edit` and exposes an `edit_mode`
constraint: `reference` for whole-image instruction editing, `variation` for a
new alternative from one source, and `inpaint` for strict masked editing. The UI
requires a mask only for inpaint and clearly warns that reference/variation may
change the whole image. Invalid combinations fail before GPU admission.

The first 1024x1024 variation job found a new first-use cost: load completed in
9.424858 seconds, while reference-image ROCm compilation/generation took
229.208449 seconds. Its 180-second browser assertion timed out, so it is not
reported as a browser pass. The underlying job succeeded and released its
lease. Two cache-warm, separate-worker installed-host Chromium runs then passed:

```text
variation:       27.002184 sec browser total; load 9.655933; generation 10.720631
reference edit:  25.875298 sec browser total; load 10.693552; generation 9.148814
final exact branch variation: 25.737216 sec; load 9.577456; generation 9.121249
assets per run:  source import + one lineage child
output pair:     identical 1,447,679-byte PNG / SHA-256 b03dd63d...778689
browser errors:  0
placement:       pipeline/text encoder/transformer/VAE cuda:0; offload hooks 0
Broker after:    active 0 / waiting 0
```

The final exact branch also reported `available` for single-reference edit,
inpaint, variation, and strict edit, and the post-run Broker query returned
active 0 / waiting 0.

Visual inspection confirmed the requested cheerful two-hand waving pose while
retaining the orange mesh hair and black/orange hoodie. This is edit quality
evidence for this sample, not a G3 consistency claim. Evidence is retained under
`/data1tb/mediaforge-g2-e2e.Frwz2w/variation-browser-warm/` and
`reference-browser-warm/`.

Focused editing/API/host regression completed with 68 passed. Full
`./mf.sh test` completed with 106 passed in 5.62 seconds. These are regression
evidence, not substitutes for the real browser and worker observations above.

### Multi-reference edit

`image.edit` now accepts `edit_mode=multi_reference` with 2..4 asset inputs.
The first input is the editable primary and sole lineage parent; additional
inputs are visual references, and provenance hashes every input. Strict mode is
rejected for this path. The worker receives only contained job-local copies and
the FLUX.2 adapter uses its official image-list input; model identity remains
absent from capability/tool responses.

Real installed-host Chromium used a Media Forge-generated 512x512 primary and
two Media Forge-generated references. Both separate-worker runs succeeded:

```text
first browser total:          28.895831 sec; load 9.890928; generation 11.739208
repeat browser total:         21.830374 sec; load 9.882474; generation 4.771229
assets per run:               3 imports + 1 result
lineage parent count:         1 (primary)
provenance reference hashes:  3
same-seed result:             byte-identical 352,021-byte PNG
browser errors:               0
placement/offload:            all cuda:0 / hooks 0 / non-GPU targets 0
Broker after each:            active 0 / waiting 0
```

Visual inspection confirmed that features from all routes were reflected: the
primary black/orange design and hoodie, orange mesh detail, and the referenced
two-hand waving pose. This does not claim the broader G3 identity metric.
Evidence is retained under
`/data1tb/mediaforge-g2-e2e.Frwz2w/multi-reference-browser/` and
`multi-reference-browser-repeat/`.

Focused multi-reference/edit/adapter/API/host regression completed with 90
passed. Full `./mf.sh test` completed with 123 passed in 6.54 seconds. These are
regression evidence only.

### Bounded semantic review

The frozen `qa.semantic` and `qa.max_regeneration_attempts` fields now drive an
optional local VLM review. The reviewer endpoint is restricted to a loopback
HTTP origin; its request forces `num_gpu=0`, `temperature=0`, a 4,096-token
context, structured output, and a 768x768 / 2 MiB maximum review image. Core has
no VLM/torch dependency. `image.semantic_review` is unavailable when the exact
configured model is absent.

Deterministic validation of every candidate completes before the first VLM
call. With the default retry budget zero, rejection is advisory and is retained
as a provenance warning. A positive budget is explicit opt-in: only `count +
budget` candidates are generated and all-rejected output fails with
`semantic_review_exhausted`; a semantic pass never overrides a deterministic
failure.

The optional reviewer is Ollama `qwen3-vl:2b`, ID `0635d9d857d4`, 1.9 GB,
Apache-2.0. Direct R9700-host measurements using the retained Media
Forge-generated 512x512 character were:

```text
first CPU-only review before bounded-JPEG change: 40.665945 sec
warm review before bounded-JPEG change:           16.612088 sec
exact bounded-JPEG cold review:                   31.289228 sec
exact bounded-JPEG warm review:                   13.745254 sec
Ollama processor:                                 100% CPU
review runner RSS observed:                       about 3.0..4.3 GiB
review runner swap:                               0 bytes
GPU VRAM before/after direct review:              184,848,384 / 184,848,384 bytes
```

A real ControlDeck agent/Broker product job generated a new 512x512 image and
then reviewed it successfully in 40 seconds. The exact final branch repeated
the same job in 35 seconds as asset
`asset_c99a931c8d624d6baeee6262682f3757`. It recorded the real FLUX model, reviewer,
passed deterministic validators, semantic result, seed, license, and output
SHA-256 `8f6b4aa1...69fd78c`; the two outputs were byte-identical and all 17 observed
Broker leases were released with zero waiting requests after the run.

A second real strict-edit job deliberately requested a full-scene blue
elephant through a small edit mask. Both VLM reviews rejected the two bounded
candidates and the durable job failed explicitly with
`semantic_review_exhausted` at retry budget one after about 108 seconds. No
asset was registered and the Broker lease was released. Full `./mf.sh test`
completed with 133 passed on the final branch. These are regression evidence
only; the real jobs above are the runtime evidence.

## UX1 — workspace UI/UX (DESIGNED, NOT IMPLEMENTED, 2026-08-22)

設計と実装指示のみを追加した段階であり、**コードは 1 行も書いていない**。
実測値は存在しない。以下はすべて「未実施」である。

```text
docs/design-workspace-ux.md            設計の正（IA・段階開示・レイアウト・文言表・却下案）
docs/implementation/ux1-workspace.md   PR-U0〜U7 の実装指示とテスト計画
docs/base-plan.md §16                  ナビゲーション決定を改訂（7 項目 → 3 + 設定）
docs/base-plan.md §3.9 / §3.10         却下案を追記（平坦な全表示 / host 側モバイル画面）
```

### 設計が解こうとしている実測済みの欠落

G0 の workspace のまま G1〜G3 を積んだ結果として、以下がコード読解で確認済み。

```text
モバイル       addon.json が mobile: "companion" のため、ControlDeck は 768px 未満で
               AddonCompanion（状態カードのみ）を描画する。asset も進捗も出ない。
書き出し       host.file.export と host files bridge は実装済み（/test/host-files/roundtrip で
               疎通実績あり）だが、workspace UI に書き出し導線が 1 つも無い。
マスク作成     inpaint はマスク PNG を要求するが、UI はファイル選択のみ。
capability     /api/v1/capabilities を UI が呼んでいない（出し分けが無い）。
進捗           pollJob が create-status ノードにのみ書き込み、タブ移動で見えなくなる。
ライブラリ     asset ごとに assets.content（実測 1.4 MB 級）を直列取得している。
G3 UI          profile / reference collection の UI が存在しない。
```

### 契約に対する予定変更（実施前）

```text
公開 API / schemas / workflow / agent tools / provenance 必須項目   変更なし
/ws への追加メソッド                                                実装詳細として追加予定
addon.json  mobile: "companion" → "embedded" / version 0.1.2 → 0.2.0  実施前
ControlDeck リポジトリ                                              変更しない（差分 0 行が完了条件）
```

`embedded` への変更は、モバイル専用 IA を実装した PR でのみ行う。
未実装のまま宣言だけ変えることを禁止する（縮小 workspace は UX 規約違反）。

### NOT TESTED（このセクション時点ですべて未実施）

```text
新 /ws メソッドの実装・テスト
モバイル埋め込みの実機確認（状態カードではなく workspace が出ること）
マスクエディタ
書き出しの sha256 一致
サムネイル導入前後の転送量比較
push 更新の遅延測定
320px / 390×844 でのレイアウト実測
```

### PR-U0 — workspace transport foundation (IMPLEMENTED, measured 2026-08-22)

`/ws` に表示系メソッドを追加した。公開 API・`schemas/`・`addon.json` は変更していない。

```text
capabilities.get   公開 capability document + サイズ envelope + clamp 済み preset
library.list       asset に由来(generated/edited/imported)・要約・保護画素差分を付与
                   edit_mask は既定で除外。ページングは読み取った最古行を基準にする
assets.thumbnail   WebP・長辺 512px 上限・64KiB 上限・data_dir/thumbnails へキャッシュ
preferences.*      ControlDeck identity subject 単位。allowlist 外のキーを拒否、4KiB 上限
jobs.watch/unwatch job.changed を push。接続あたり 10 job、200ms 間引き、終端で自動解除
```

#### 実測（本開発機、fake worker 構成、1024×1024 ノイズ画像 50 枚）

`assets.list` + `assets.content`（現行 app.js の経路）と、
`library.list` + `assets.thumbnail` を同一データで比較した。
`/ws` は base64 で運ぶため、content の実バイト数を 4/3 倍して計上している。

```text
元 PNG 1 枚:                        295,396 bytes
before  転送量 50 枚:            19,715,361 bytes (18.80 MiB)
after   転送量 50 枚:             2,777,682 bytes (2.65 MiB)
削減:                                  85.9%
after   生成込み所要:                 1.163 sec
after   キャッシュ命中時:             0.009 sec
最大サムネイル:                      41,392 bytes（上限 65,536）
```

サムネイル形式は測定で決めた。同じ画像を 256px へ縮小したとき PNG は
220,714 バイトで 64KiB に収まらず、解像度を 128px まで落とす必要があった。
WebP q80 は 256px を保ったまま 41,392 バイト。実装は画質を先に譲り
（80→65→50）、それでも収まらない場合にだけ解像度を下げる。

#### 確認したこと

```text
./mf.sh test                      155 passed（追加 17 件。従来 138 件は不変）
新メソッドの host identity 要求    未認証接続は従来どおり 4401 で切断
reject_host_paths                 5 メソッドすべてで unscoped_host_path を確認
listener 例外の隔離               購読側が例外を投げても job 更新が継続することを確認
preferences の秘密漏れ            拒否メッセージに送信値が含まれないことを確認
```

#### NOT TESTED / 未実施

```text
subresource 直接取得の可否（設計 §10.1）
    installed host とログイン資格情報が必要なため未実施。
    PR-U5（書き出し・原寸プレビュー）の着手前までに実施する。
    サムネイルはこの結論に依存しないため、PR-U1〜U4 は先行できる。
実ブラウザでの動作
    本 PR は transport のみ。UI は未実装であり、実機証拠は PR-U7 で取る。
実 GPU での生成を伴う push 挙動
    fake worker 構成でのみ確認。実 worker の phase 遷移頻度は未計測。
```

### PR-U1 — workspace shell (IMPLEMENTED, browser-observed 2026-08-22)

情報構造を 5 タブから 3 ナビ + 設定へ作り替え、段階開示とモバイル専用レイアウトを入れた。

```text
frontend/index.html   3 ナビ・モードトグル・skeleton・詳細断片を <template> に分離
frontend/styles.css   PC 2 ペイン / モバイル単一列 + 下部タブ。edit.css を統合して 1 本化
frontend/app.js       capability による出し分け、preferences 復元、jobs.watch での進捗、
                      library.list + assets.thumbnail での一覧、phase/失敗の日本語化
addon.json            mobile: "companion" -> "embedded" / version 0.1.2 -> 0.2.0
backend/app.py        /activity ルート追加、stylesheet を 1 本に
```

#### 実機ブラウザ観測（standalone、Chromium、light と dark の 2 パス）

`scripts/ux_standalone_e2e.py` を実行。証跡は `/data1tb/mediaforge-ux1-evidence/{light,dark}/`。

```text
desktop 1280x800   2 ペイン / ナビ 3 / シンプルで advanced-* が DOM に 0 件
詳細モード          advanced-* 16 件が出現、モデル方針 6 種、戻すと再び 0 件
capability 反映     video.image_to_video と 3d.image_to_3d を「使えません」と表示
編集操作            画像添付で 5 種が出現し、保護保証の文言が操作と同時に切り替わる
phone 390x844      下部タブが position: fixed、単一列、横スクロール 0px、
                    タップ標的 60px、一覧 2 列
narrow 320x640     横スクロール 0px
console / page error  両パスとも 0 件
初期表示            0.06 sec（standalone・fake ではない実 manifest 構成）
```

崩れを 1 件見つけて直した。`[hidden]` が `.sub-field { display: grid }` に負けており、
「一部だけ直す」を選んでいるのに参照画像の入力と件数バッジ 0 が出ていた。
`[hidden] { display: none !important }` を入れ、E2E に選択と入力の対応を検査する
assertion を追加した（スクリーンショット目視だけでは見落とす種類の崩れ）。

#### 確認したこと

```text
./mf.sh test        171 passed（追加 16 件の静的契約テストを含む）
静的契約テスト       storage API 不使用 / DOM 契約 id / advanced-* が template の外に無い /
                    UI が読む capability が backend の出力の部分集合 /
                    失敗文言の code が実在 / 全 phase に日本語がある /
                    preferences キーが allowlist 内 / addon.json の mobile と version
```

`./mf.sh test` は 1 度だけ
`test_workspace_websocket_chunk_import_exceeds_single_message_bound_and_cleans_up`
で失敗した。standalone の開発サーバを同時に動かしていた回であり、その後
単体 1 回・全体 5 回では再現しなかった。原因は特定できていないため、
再発したら記録する。

#### NOT TESTED / 未実施

```text
installed host での埋め込み表示
    768px 未満で状態カードではなく workspace が出ることを実機で未確認。
    addon.json は embedded を宣言済みだが、確認は PR-U7 で行う。
モードの再読込またぎの復元
    preferences の永続化は backend 単体テスト済みだが、UI 経路は standalone では
    /ws を張れないため未確認（standalone は identity を持てない）。
theme token の反映・safe_area・route 同期・通知条件
    host bridge が要るため未確認。
サイズ preset の実値
    standalone では capabilities.get が envelope を返さずフォールバック値を使う。
    実 envelope に基づく preset は installed host で確認する。
マスクを筆で描く経路
    未実装（PR-U3）。現在はマスク画像のファイル指定のみ。
失敗時の「出口」ボタン
    未実装（PR-U4）。現在は日本語 1 文までで、操作は付いていない。
```

### PR-U2 — create experience (IMPLEMENTED, browser-observed 2026-08-22)

作成画面の検証を「GPU を取りに行く前」に寄せ、無視される入力を出さないようにした。

```text
送信前検証   intent 未記入 / manual なのにモデル未指定 / 16 の倍数でない寸法 /
             envelope 外 / inpaint でマスク未指定 / 参考画像 1〜3 枚の範囲外 /
             outpaint が元画像より小さい・広がっていない
             すべて inline error で止め、import も job 作成も行わない
寸法の計測   添付時に createImageBitmap でブラウザ側が測る。
             これが無いと outpaint の可否が受付後にしか分からない
サイズ欄     出力寸法が元画像で決まる操作（inpaint / reference / variation /
             multi_reference）では欄ごと隠す。選ばせた値が無視される状態を作らない
             outpaint では「広げる先の大きさ」に変わり、元画像の寸法を併記する
目安時間     measured な実測がある場合のみ表示
ドロップ     画像のドラッグ&ドロップに対応
```

`<form novalidate>` にした。ブラウザ既定の吹き出しは文言を持てず、モバイルで
見落としやすいため、検証と表示を `requestProblem()` に一本化している。

#### 実機ブラウザ観測（standalone、Chromium、light と dark の 2 パス）

送信は `page.route` で捕捉して 202 を返し、実際の生成は起こしていない
（この開発機には実モデルが入っており、本当に投げると GPU を数分占有するため）。

```text
16 の倍数でない幅 1000      送信されず「幅と高さは 16 の倍数にしてください」
広がっていない outpaint     送信されず「少なくとも片方の辺を大きくしてください。」
manual を選んだ送信         model_policy=manual と model_id が載り schema 適合
既定の送信                  schema 適合 / local_only=true / model_id は載らない
編集を選んだとき            サイズ欄が消え、外側を広げるときだけ戻る
console・page error         両パスとも 0 件
```

捕捉した送信内容は `/data1tb/mediaforge-ux1-evidence/light/submitted-request.json`。

#### 直したこと

```text
envelope 未取得時に寸法検証が丸ごと無効化されていた
    standalone や取得失敗時に「16 の倍数」の規則が受付後にしか効かなかった。
    フォールバック envelope（256〜1024・16 の倍数）を使って必ず検証する。
目安時間の表示が誤解を招いていた
    registry の measured_runtime_sec は初回実行（モデル読み込みと
    カーネルコンパイル込み）の実測 208.82 秒であり、暖まった後の 10〜17 秒台とは
    別物。「目安 209 秒前後」と出すと大きく外れるため、
    「初回は約 209 秒（モデルの読み込みを含む実測）。2 回目以降は短くなります。」に変更。
```

#### 確認したこと

```text
./mf.sh test   172 passed（UI が投げる code にも日本語文言を要求する試験を追加）
```

#### NOT TESTED / 未実施

```text
実際の生成を伴う受付         送信は捕捉して止めているため、GPU 経路は未確認
installed host での検証       envelope の実値・theme・grant は PR-U7
筆でマスクを描く経路          未実装（PR-U3）。現在はマスク画像のファイル指定のみ
outpaint の方向ハンドル       未実装（PR-U3）。現在はプリセットからの寸法指定のみ
失敗時の出口ボタン            未実装（PR-U4）
```

### PR-U3 — mask editor and outpaint (IMPLEMENTED, browser-observed 2026-08-22)

外部ペイントツールが必須だった inpaint を、画面内で完結できるようにした。

```text
マスク編集   canvas に筆で塗る。太さ（短辺の 4% を既定）・消しゴム・取り消し 8 段・全消去
             pointer events で 1 本指描画 / 2 本指ピンチ拡大 / Ctrl+ホイール拡大
             出力は元画像と同寸法の 2 値 PNG（塗った所=白、それ以外=黒）で、
             既存の import 経路（purpose=edit_mask）へ流す
             空マスクと全面マスクは決定時に止める（backend と同じ規則を UI でも見せる）
外側を広げる 比率（元のまま / 16:9 / 正方形 / 9:16）と倍率（1.25 / 1.5 / 2）から
             目標寸法を計算し、元画像を中央に置いた枠を preview で見せる
             16 の倍数・元画像を内包・少なくとも 1 辺拡大・envelope 内を UI で保証
詳細モード   マスク画像の直接指定を残す（既存経路を消さない）
```

#### 設計を 1 件修正した

実装前に backend を確認したところ、`outpaint_plan` は
`left = (width - source.width) // 2` で元画像を**必ず中央へ置く**。
設計に書いていた「上下左右のハンドルをドラッグ」は非対称拡張を前提にしており、
現行契約では表現できない。できるかのような操作を見せないため、
比率と倍率の選択に変更し、`design-workspace-ux.md` §6 F2 と
`ux1-workspace.md` §5 に根拠を記録した。中央配置の前提が変わっていないことを
静的試験でも検査している。

#### 実機ブラウザ観測（standalone、Chromium、light と dark の 2 パス）

実際のポインタ操作で塗り、送信は捕捉して生成させていない。

```text
何も塗らずに決定       ダイアログが閉じず「変えたい場所を塗ってください。」
実際に塗った結果       1,108 ピクセル（全体の 1.7%）を変更対象として記録
取り消し・消しゴム     操作でき、状態が切り替わる
送信された constraints strict_edit=true / edit_mode=inpaint /
                       editable_mask_asset_id=asset_... （実際に import された資産）
外側を広げる           「256×256 を中央に置いて 512×288 へ広げます。」
                       constraints は 16 の倍数・元画像を内包・1 辺拡大・strict_edit=true
console・page error    両パスとも 0 件
```

証跡: `/data1tb/mediaforge-ux1-evidence/{light,dark}/`（`mask-editor.png` / `outpaint.png` を含む）

#### 確認したこと

```text
./mf.sh test   174 passed
静的試験の追加  マスクのファイル指定が詳細モードにしか無いこと、
                非対称拡張の操作が UI に無いこと、中央配置の前提が変わっていないこと
```

#### NOT TESTED / 未実施

```text
実機のタッチ操作        pointer events で実装しているが、実端末の指操作は未確認。
                        Playwright のマウス操作でのみ確認した
実際の生成を伴う inpaint 送信を捕捉して止めているため、strict edit の実行経路は未確認
全面マスクの UI 阻止    筆で全面を塗る操作が長いため未実施。backend 側は既存試験で確認済み
installed host での確認 PR-U7
失敗時の出口ボタン      未実装（PR-U4）
```

## Release v0.2.0 (2026-08-22)

UX1 の PR-U0〜U3 と G3 backend を含む版を公開した。

```text
artifact  control-deck-media-forge-0.2.0-linux-x86_64.tar.gz
bytes     29,121,065
sha256    ec7dd2296b8a640acb780c30b39c54e19c65a5488ebc4ec1c876bf9aa43f97c6
release   https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.2.0
```

#### リリース物そのものに対する検証

ソースツリーではなく、**展開したバンドルを起動して**確認した。

```text
起動            bin/mediaforge-core serve が health 200 を返す
配信内容        workspace HTML 80,781 バイトに 3 ナビ・モードトグル・マスク編集・
                広げ方・詳細テンプレート・受付前エラー・モバイル下部タブが含まれ、
                旧 UI の operation select は含まれない
addon manifest  version 0.2.0 / mobile embedded
実ブラウザ試験  scripts/ux_standalone_e2e.py がバンドルに対して PASSED
                1280×800 の 2 ペイン / 390×844 の下部タブ・横スクロール 0px /
                320px 崩れなし / console・page error 0 件
```

#### 未確認のまま公開した点（リリースノートにも明記）

```text
installed host での埋め込み表示
    mobile: "embedded" を宣言しているが、実機ホストで 768px 未満に
    状態カードではなく workspace が出ることを確認できていない。
    確認には ControlDeck のログイン資格情報が必要（PR-U7）。
実端末のタッチ操作          Playwright のマウス操作でのみ確認
実際の生成を伴う inpaint    送信を捕捉して止めているため実行経路は未確認
生成物の書き出し            未実装（PR-U5）
キャラクター／画風の UI      未実装（PR-U6）
```

#### ホスト側カタログ

ControlDeck の `backend/app/features/trusted-catalog.json` は v0.1.2 を pin している。
v0.2.0 を配布するには ControlDeck 側の別 PR が必要。

## PR-U7 partial — installed-host acceptance (2026-08-22)

テスト用の管理者 `mf-e2e` を作り、実機の ControlDeck に対して
`scripts/ux_control_deck_e2e.py` を実行した。

```text
bridge                ready（standalone ではなく host bridge に接続）
theme token           host から届いた値が適用される（accent #3b82f6 等）
サイズ preset         実 envelope 由来の 1024x1024 / 1024x576 / 576x1024
                      standalone のフォールバックではない
詳細モードの永続化    再読込後も維持される（standalone では確認できなかった項目）
route 同期            /x/media-forge/workspace/library まで URL へ反映
モバイル 390x844      状態カードではなく workspace が出る（embedded 宣言が効いている）
                      下部タブ fixed / 単一列 / 横スクロール 0px / タップ標的 60px / 一覧 2 列
console・page error   0 件
```

`mobile: "embedded"` の実機確認は v0.2.0 時点で唯一残っていた重要な未確認事項であり、
これで解消した。

## 実使用で見つかった不具合（2026-08-22）

実機のモバイルで実際に触ったことで、試験では出なかった問題が 6 件出た。

### 1. パッケージ済み worker が起動できない（最も重い）

installed bundle での画像生成が**必ず** `worker_crash` になっていた。
worker を手で起動して原因を特定した。

```text
ModuleNotFoundError: No module named 'mediaforge'
  worker_packs/image/adapters/diffusers_flux2.py:10
```

G2 で adapter が `mediaforge.image_edit` / `mediaforge.outpaint` を import する
ようになったが、bundle には凍結された core しか無く worker の venv からは
import できない。dev で気付かなかったのは、親プロセスから継いだ `PYTHONPATH` に
たまたま `backend` が含まれていたためで、経路として保証されていなかった。

修正: bundle へ `backend/mediaforge` を同梱し、worker の `PYTHONPATH` を明示する。
`worker_packs` が import する自リポジトリのパッケージが bundle に入っているかを
検査する試験を追加した。

**残る設計上の問題**: worker が core を import すること自体が
`AGENTS.md`「worker は core から実装を import しない」に反する。
今回は動作を先に戻した。`image_edit` / `outpaint` は PIL だけに依存する純粋な
幾何処理なので、worker pack 側へ寄せるのが筋。層の整理は未着手。

### 2. 端末の写真が取り込めない

3024x4032 の写真は取り込みの画素数上限（2048x2048）を超えて失敗し、
画面には「うまくいきませんでした」としか出ていなかった。
出力はどのみち envelope 内の寸法になるので、送る前にブラウザ側で縮小する。

### 3. base64 の chunk がパスとして誤検出される

`reject_host_paths` が運搬用の base64 本体まで検査しており、先頭が `/` になる
chunk（base64 のアルファベットに含まれるため約 1/64）が `unscoped_host_path` で
拒否されていた。取り込みが不定期に失敗する原因であり、
`test_workspace_websocket_chunk_import_exceeds_single_message_bound_and_cleans_up` の
間欠失敗の正体でもある。

この間欠失敗は PR-U0 より前のコミット（6499047）を worktree に取り出して
8 回中 1 回再現することを確認しており、UX1 の変更が持ち込んだものではない。
修正後は 5 回連続で通る。

### 4. 入力しただけで「未保存」警告が出る

`host.busy` を keystroke ごとに立てて降ろしていなかった。Media Forge に保存の
概念は無く、実行中の作業はサーバ側の job として残る。実際に失うものがある間だけ立てる。

### 5. 取り込み中の進捗が出ない

job になる前の取り込み時間が最も長いのに進捗が無かった。モバイルではステージが
画面外にあり、常時表示のミニバーが唯一の手掛かりになる。

### 6. 版の出所が二重化していた

`doctor` が 0.1.2 を返し、provenance にも 0.1.2 が記録されていた。
`mediaforge.__version__` へ一本化し、pyproject は hatch の dynamic version で読む。

### 修正後の実機確認

```text
インストール済み 0.2.2 経由の実生成   1024x1024 が 20 秒で完了し結果を表示
モバイルの進捗バー                    生成中に表示される
「未保存」                            入力しただけでは出ない
端末写真の取り込み                    3024x4032 -> 768x1024 に縮小して成功
console・page error                   0 件
```

## Release v0.2.1 / v0.2.2

```text
v0.2.1  b3405cd7662de9972dabe5182c8996ac3f6b63a4807c7ecbf42f0929324ca75a  29,126,043 bytes
v0.2.2  a8e6e7342d2a4885bf3a45ca23803f671de3b1f53915caf13232f101a2817992  29,320,459 bytes
```

ControlDeck の `trusted-catalog.json` は v0.2.2 を pin 済み（ControlDeck PR #222）。
この開発機の稼働環境も 0.2.2 へ更新し、旧版は versions/ に残してロールバック可能。

## ControlDeck 側の変更（利用者の許可のもと・汎用機能に限定）

```text
PR #220  trusted-catalog の pin を v0.2.0 へ
PR #221  quick action / command を宣言どおり実行する host API と、
         Quick Actions のアイコンを NAVIGATION から引く修正
PR #222  trusted-catalog の pin を v0.2.2 へ
```

PR #221 は「宣言された contribution を実行する」汎用機能であり、Media 固有の
分岐は入れていない。Media Forge 側は contract どおり
`{"route": "/x/media-forge/workspace/create"}` を返しており、host が呼んで
いなかっただけだった。

## UX2 PR-M0 — model catalog and ownership (2026-08-22)

既存の単一 `ModelRegistry` に、公開 `/api/v1/models` schema を変更せず
catalog metadata を合成した。Media Forge 管理ストアと共有 Hugging Face cache は
別 root として走査し、同じ model identity が双方で有効なら registry 全体を
`model ownership is ambiguous` として fail-closed にする。管理 root からの symlink
脱出は installed と認めない。external snapshot は生成に利用できるが
`removable=false` である。

開発機で `./mf.sh model list` を実行した実測:

```text
model       black-forest-labs/FLUX.2-klein-4B
revision    e7b7dc27f91deacad38e78976d1f2b499d76a294
domains     general,illustration,poster,background
source      /data1tb/ControlDeck/data/cache/huggingface (NVMe/ext4)
state       available / installed=yes / healthy=yes
ownership   external / removable=no
scan time   0.03 seconds
max RSS     14,340 KiB
```

別プロセスの core を `127.0.0.1:9138` で起動し、`/health` は healthy、
`/api/v1/models` は従来の公開 field 集合のまま上記モデルを installed/healthy と返し、
`/api/v1/capabilities` は `image.text_to_image` を local/measured/available と返した。
この確認用 managed root は `/data1tb/ControlDeckMediaForge/.runtime-evidence/m0/models`
（NVMe device 66305）を指定し、観測後の一時データは `/tmp` へ退避した。

`./mf.sh test` は 189 passed（13.24 秒）。これは契約回帰の証拠であり、上記の
実プロセス/API/実ストレージ観測とは区別する。モデルの新規 download、resume、
verify、remove、Settings UI は PR-M1/M2 のため **NOT TESTED**。稼働中の installed
bundle は v0.2.4 であり、M0 はまだリリース bundle へ含めていない。ControlDeck の
コード変更は不要だった。

## UX2 PR-M1 — durable model install/remove backend (2026-08-22)

trusted catalog の pinned revision だけを対象にする durable operation を実装した。
URL、repository、command は workspace input として受け取らない。転送は常に
`parallelism=1` で、各ファイルは現在 offset から最大 5 回まで再試行する。
partial は `.downloads/<operation_id>` に隔離し、required file と weight の
size/SHA-256 検証後に同一 filesystem 上で atomic promote する。明示 cancel は
partial を削除し、service shutdown / Ctrl-C は再開用に残す。external model と
実行中 job が保持する managed model の削除は拒否する。

開発機の NVMe 上に空の external cache と専用 managed root を作り、実際の
FLUX.2 Klein 4B を取得した。

```text
operation id       modelop_f392eb94cd4d445499a957d5e5b87485
model/revision      black-forest-labs/FLUX.2-klein-4B
                    e7b7dc27f91deacad38e78976d1f2b499d76a294
managed root        data/model-management/managed（/dev/nvme0n1p1, ext4）
transfer mode       sequential, parallelism=1
interruption        780,840,902 bytes で Ctrl-C
resume              同じ operation id / queued から再開し 781,119,430 bytes を観測
resume process      1,592.15 seconds / max RSS 63,088 KiB
operation elapsed   1,691.26 seconds（中断と再起動を含む DB timestamp 差）
verified blobs      15,975,681,525 bytes / 13 snapshot files
final state         ready / installed=yes / healthy=yes / ownership=managed /
                    removable=yes
partial cleanup     ready 後 `.downloads/` に operation directory なし
registry rescan     0.10 seconds / max RSS 24,892 KiB
repeat install      model_already_installed、0.15 seconds、exit 1
```

開発中の実転送では 2 件の失敗も観測した。1 件目は size 未知の完了済み小ファイルへ
Range request を送り HTTP 416 になったため、`Content-Range: bytes */<total>` と
local size が一致する場合だけ完了として扱うよう修正した。2 件目は受信途中の
remote close で失敗したため、offset 継続の bounded retry を追加した。失敗 operation
は `failed` のまま durable history に残り、partial は削除されている。成功 run では
約 10.39 GB 地点で受信停止後に同じ operation のまま進行が戻った。

実転送対象の合計が cache directory 全体の初期概算より 13,226,337 bytes 小さいことを
観測したため、catalog の `approx_download_bytes` は検証対象 13 files の実合計
15,975,681,525 bytes に補正した。成功 operation は補正前の概算値を durable history
として保持しているが、以後の operation は補正値を使う。

同じ managed root と空の external cache で実 core を `127.0.0.1:9139` に起動した。
最初の確認で `model_library=missing` を観測し、`mf.sh` の setup 判定が外部
`HF_HOME/hub` の存在だけを前提にしていたことを特定した。managed hub も判定対象にし、
core venv の interpreter で registry を読むよう修正後、実 HTTP で `/health` は
`healthy` / `model_library=ok`、`/api/v1/models` は対象モデルを
`installed=true` / `healthy=true` / `available` と返した。

`./mf.sh test` は 202 passed（14.39 秒、全 command 15.50 秒、最大 RSS
180,192 KiB）。これは契約回帰の証拠であり、上記の実ダウンロード、再開、検証、
実プロセス/API観測とは区別する。実 15.98 GB model の remove は、次工程でも使うため
**NOT TESTED**。小さい隔離 fixture の remove、external/in-use拒否、cancel cleanup、
hash不一致、symlink脱出、workspace event はテストで確認した。managed copyからの
実画像生成と Settings UI は **NOT TESTED**（後続 M2/C5）。ControlDeck のコード変更は
不要だった。

## UX2 PR-M2 — Settings Model Management (2026-08-22)

既存 Settings に、Simple から到達できるモデル管理を追加した。保存容量、
Installed / Recommended / All、media type/domain chip、friendly name、導入・削除、
inline progress、global model progress を表示する。model ID、revision、hash、runtime、
backend、生 capability、VRAM/時間、license/gated は Advanced template を mount した
ときだけ DOM に現れる。Simple の操作対象は一時 catalog index で結び、model ID を
`data-*` にも置かない。

`media_types`（image / video / audio_video）は catalog/UI 分類専用として追加した。
routing は読まず capability が唯一の挙動契約である。runtime capability family と
矛盾する catalog は registry 全体を fail-closed にする。これにより将来の動画・
音声付き動画も同じ Model Management を使えるが、G7 model の download/worker/default
昇格には着手していない。

実ブラウザと実 core/private WebSocket/durable SQLite を使う隔離 E2E
`scripts/ux_model_management_e2e.py` を実行した。モデル byte だけを 32 MiB の
fixture にし、実 installer/verifier/atomic managed store/remove を通した。

```text
Download開始                 1 tap
install wall time            10.539 seconds
別画面の global progress     visible
reload/reconnect             同じ active operation を operations.list から復元
Advanced detail              Simple DOM には無し / Advanced で model_id 等を確認
external model               disabled「共有モデル」/ destructive action 無し
Remove                       action 後の確認 dialog は 1 回だけ
390x844 horizontal overflow  0 px
320x640 horizontal overflow  0 px
console / page error         0 件
evidence                     /tmp/mediaforge-m2-evidence/
```

この試験で 3 件の実不具合を検出して修正した。

1. mount URL が `/` で終わると WebSocket URL が `//ws` になったため末尾 slash を正規化。
2. 最後に Settings 以外を見て reload すると operation を復元しなかったため、boot 時に
   durable operation を常に読む。
3. 小さい remove が watch 登録前に完了すると queued 表示に残ったため、watch 直後にも
   durable list/catalog を再取得して event race を収束させる。

実 managed FLUX.2 Klein 4B を読む standalone core に対して既存
`scripts/ux_standalone_e2e.py` も実行し PASSED。desktop ready 0.120 秒、390px/320px
overflow 0、console error 0 件だった。既存スクリプトが outpaint 後の
`source → target` 寸法表示を旧形式として parse していた 2 箇所も更新した。

`./mf.sh test` は 207 passed（12.10 秒、全 command 13.22 秒、最大 RSS
181,556 KiB）。これは契約回帰で、上記ブラウザ/実process観測とは区別する。
実 15.98 GB model の削除、installed ControlDeck の配布版でのM2表示、G7動画model、
managed copyからの画像生成は **NOT TESTED**。大容量modelはNVMeに保持した。
ControlDeck のコード変更は不要だった。

## UX2 PR-C0 — CreativeSpec/template/compiler (2026-08-22)

公開 JobRequest/schema/addon contract を変更せず、private planning object と
deterministic compiler を追加した。`CreativeSpec` は domain、SceneSpec、PoseSpec、
CompositionSpec、CameraSpec、VariationSpec、ReferenceRole を持つ。template は
`creative/templates.json` のversioned dataであり、DOMやengine adapterへhardcode
していない。Cameraは将来の動画でも共用できるが、MotionSpecはG7まで受理しない。

`creative.templates` と `creative.validate` はauthenticated workspace transportだけに
追加した。compilerは既存intent/constraintsへcompileし、template ID/version、役割、
envelopeを含むnormalized planを`constraints.creative_plan`へ保存する。空/全Autoは
requestを1 fieldも変えない。scene/pose不整合、unknown template、unavailable
capability、requestに無いreference role assetをjob作成前に拒否する。routingは
変えず、auto requestへmodel IDを追加しない。

別Python processで実templateをloadし、anime / presenting_device / holding_item /
full_body_off_center / eye_level / expressionのspecを1,000回compileした。

```text
catalog version            2026.08.22
template counts            domain 6 / scene 8 / pose 9 / composition 8 /
                           camera 7 / variation 5 / reference role 5
empty request identical    true
1,000 compile elapsed      0.029042 seconds
deterministic hashes       unique=1
process wall / max RSS     0.11 seconds / 30,012 KiB
model routing              model_policy=auto / model_id=null
plan snapshot              constraints内のplanとcompiler resultが一致
invalid combination        creative_combination_invalid / field=pose /
                           「選んだシーンとポーズは組み合わせられません。」
```

最初の測定コマンドは製品起動時と同じ`PYTHONPATH=backend`を付け忘れ、
`ModuleNotFoundError: mediaforge`で0.01秒終了した。上記の成功値には含めていない。
focused testは43 passed。`./mf.sh test`は222 passed（15.63秒、全 command
16.93秒、最大 RSS 185,752 KiB）。これは契約回帰の証拠であり、上記の
実 process compile 実測とは区別する。CreativeSpecを使うUI、
実job生成、profile/reference統合、variation child生成はC1〜C3のため **NOT TESTED**。
G7 MotionSpec/動画modelは **NOT TESTED**。ControlDeck変更は不要だった。

## UX2 PR-C1 — Create creative direction UI (2026-08-22)

既存 Create の intent、画像取り込み、サイズ、枚数、実行、result stage、
Advanced panel を移動・複製せず、Simple に Domain と閉じた
「シーンと見せ方」を追加した。全ラベルは C0 の versioned template data
から導出し、Simple に model 名や engine 語を出していない。Advanced の
domain/scene/pose/composition/camera/variation と自由補足は従来どおり
template を mount したときだけ DOM に存在する。

Auto のままでは `creative.validate` を呼ばず、prompt-only の既存 JobRequest
形を維持する。指定があるときだけ private compiler による検証・compile
を job admission 前に行う。standalone workspace も同じ compiler を使うため、
OpenAPI から除外した same-origin の `/workspace-api/creative/validate` を追加した。
これは public API ではなく、path/model を受理しない。

隔離 data dir の実 core（`127.0.0.1:9141`）と Chromium で
`scripts/ux_creative_c1_e2e.py` を実行した。

```text
Simple advanced nodes          0
Domain labels                  自動 / アニメ / イラスト / 写真 / 2Dゲーム / ポスター
prompt-only constraints        width=1024 / height=1024 / creative_plan無し
directed selections            scene / pose / composition / camera / variation を独立選択
compiled routing               domain=anime / model_id=null / catalog=2026.08.22
invalid combination            job POST 0件 / inline理由を表示
Advanced nodes                 27
320x640 horizontal overflow    0 px
tab order                      intent -> scene/pose/composition/camera/variation -> submit
console / page errors          0 / 0
evidence                       /tmp/mediaforge-c1-evidence/
```

`./mf.sh test` は224 passed（15.64秒、全 command 16.89秒、最大 RSS
189,288 KiB）。これは回帰gateであり、上記の実process/browser観測とは区別する。
Character/Style と role-aware reference は C2、複数差分 job は C3 のため
**NOT TESTED**。CreativeSpec 指定での実 GPU 生成・品質差は C5 のため
**NOT TESTED**。G7 MotionSpec/動画モデルは **NOT TESTED**。ControlDeck 変更は不要だった。

## UX2 PR-C2 — Character / Style / role-aware references (2026-08-22)

新しい profile store を作らず、G3 の ReferenceCollection / CharacterProfile /
StyleProfile を Create に接続した。Simple では「キャラ・画風を使う」の選択だけを
出し、collectionのrole metadata、またはprofile kindからidentity/styleを推定する。
strength sliderのmatrixはSimple DOMに存在しない。

ReferenceCollection schema に省略可能な `roles` map を加法的に追加した。
旧asset/collection/clientは省略でき、既存fieldの意味は変わらず、migrationと
contract version bumpは不要。jobごとのoverrideはprofileを変更せず
CreativePlan/provenanceに保存する。roleはidentity/style/pose/composition/clothing/
palette/prop/environment。

model catalog に `reference_roles` と `supports_reference_strength` を加法し、
active model群の共通role、最小`max_references`、strength対応をprivate envelopeの正とした。
FLUX.2 Klein 4Bは8 role、最大4参照、numeric strength未対応とし、未対応
strengthは理由付きでdisabledにした。

隔離data dirの実core（`127.0.0.1:9142`）に6画像、2 collection、2 profileを
実HTTPで登録し、Chromiumで`scripts/ux_reference_roles_c2_e2e.py`を実行した。

```text
Simple profile inference       character refs 3枚 / role matrix DOM 0
deliberate pose variants       wave / peace / holding_item（同一profile・identity）
identity fixed / pose changed  identityは固定、pose役のassetだけswap
style fixed / composition      style profileは固定、composition役assetだけswap
strength support               3 controls全てdisabled（model metadata=false）
reference admission            character 3 + style 3は上限4枚の手前でjob POST 0
320x640 horizontal overflow    0 px
console / page errors          0 / 0
evidence                       /tmp/mediaforge-c2-evidence/
```

初回browser probeでstandalone shimにprivate envelopeが渡らず上限0枚と表示する
実不具合を検出した。coreが算出したtemplate/preset/envelopeをworkspace HTMLへ
dataとして埋め込み、standaloneとembeddedが同じ数値的正を使うよう修正した。

`./mf.sh test`は228 passed（12.59秒、全command 13.93秒、最大RSS
191,848 KiB）。実GPUで3 pose/reference swapの視覚品質はC5のため **NOT TESTED**。
numeric strengthは対象modelが未対応なで **UNAVAILABLE**。ControlDeck変更は不要だった。

## UX2 PR-C3 — intentional pose/scene/composition batches (2026-08-22)

`count > 1` と pose / scene / composition variation の組み合わせを、単一workerへの
曖昧な複数出力ではなく、2〜8件の明示的child CreativeSpecへ展開するplannerを追加した。
各childは異なるtemplate snapshot、seed、batch ID/indexを持ち、通常のjob admissionを
1件ずつ通る。親batchはSQLiteへ永続化し、reload後のprogress復元、logical cancel、
successful assetを残すpartial stateを提供する。public JobRequest/schema/addon contractは
変更していない。

隔離data dirの実core（`127.0.0.1:9143`）、fake workerの別process、Chromiumで
`scripts/ux_creative_batches_c3_e2e.py`を実行した。

```text
pose x4                  holding_item / typing / peace / wave
pose seeds               1664062594 / 1664062595 / 1664062596 / 1664062597
composition x4           bust_up / full_body_center / full_body_off_center /
                         three_quarter
result candidate assets  pose batch 4件
reload/reconnect          batch IDを復元、表示は「差分を作っています（0/4）」
logical cancel            child 4件すべて canceled、queued/running 0件
partial success           succeeded 1 / canceled 3 / retained asset 1
Advanced Activity         親batchからchild job ID 4件を展開
browser wall time         3.4 seconds
320x640 overflow          0 px
console / page errors     0 / 0
evidence                  /tmp/mediaforge-c3-evidence-20260822d/
```

初回browser runは実modelを空rootへ隔離した結果、capabilityが正しく
`model_not_installed`となり受付前に422で停止した。実modelを偽ってavailableにせず、
experimental manifestでfake workerを明示するfixtureへ切り替えた。次のrunではSimpleの
progress detailにbatch IDが出ると仮定したprobeがtimeoutし、実際のSimple表現に合わせて
進捗文言と可視状態を観測した。3回目は新しいparent drilldownの長いIDが320pxでoverflow
する実不具合を検出し、grid childのmin-widthと折返しを修正後に上記runが完了した。

`./mf.sh test`は240 passed（16.39秒、全command 17.81秒、最大RSS 203,108 KiB）。
これは契約回帰であり、上記の実process/browser観測とは区別する。
実GPUによる4 pose / 4 compositionの視覚品質、ControlDeck broker上での4-child連続
admission、installed-host iframeでのreconnectはC5まで **NOT TESTED**。fake workerは
CPU-onlyでありlease不要。ControlDeck変更は不要だった。

## UX2 PR-C4 — multi-cut planner + deterministic Composer (2026-08-22)

Poster / Character Sheetを新しいtop-level appやpublic operationにせず、既存Createの
Domainとcomposition presetとして追加した。2〜4件のmain/coding/device/chibi shotを
同じCharacter/Style constraintを持つ通常の`image.generate` child jobへ展開し、完了後に
CPU-only Composerがversioned layoutのregionへcrop/配置、枠、safe margin、日本語title/
caption、固定出力寸法を適用する。最終assetは`asset.pack`で、全child assetをlineageと
hash付きprovenanceに持つ。

日本語fontは環境から選んだNoto Sans CJKをdata dirへSHA-256名で初回cacheし、layout
snapshotへfont hashを保存する。model/venv内へ置かず、text再編集時も同じcached bytesを
使う。今回の実測cacheは19,484,784 bytes、SHA-256は
`b76b0433203017ca80401b2ee0dd69350349871c4b19d504c34dbdd80541690a`。

隔離data dirの実core（`127.0.0.1:9144`）、別process fake worker、Chromiumで
`scripts/ux_multicut_composer_c4_e2e.py`を実行した。

```text
child shots                 3 jobs / 3 assets（main / coding / device）
final poster                1024x1536 RGBA PNG
initial SHA-256             b6168adc74b8c34db2090aa1bd8661132490eb060da95d3d065ca6f0e14512fb
title/caption update        image.generate job delta 0 / final revision +1
changed SHA-256             ee99bf1ef7f1c2b0789d35096dfa18d61d12c9ab3187e74be218598af2bd09b5
same layout+children        initial SHA-256と再一致
lineage                     parent asset 3件がshot asset 3件と完全一致
mobile viewer               natural 1024x1536 / existing viewerを使用
browser wall time           4.6 seconds
320x640 overflow            0 px
console / page errors       0 / 0
evidence                    /tmp/mediaforge-c4-evidence-20260822b/
```

最初のbrowser runではPillow default fontが日本語を豆腐字形にする実不具合を画像で確認した。
上記のcontent-addressed font cacheへ修正し、2回目の画像で日本語glyphを目視確認した。
focused testでは2/3/4 shot layoutのbyte-for-byte再現、safe dimensions、hosted workspace
child path、文字更新時のchild不変を確認した。実GPU shotの視覚的一貫性とinstalled-host
iframeはC5まで **NOT TESTED**。`./mf.sh test`は255 passed（23.75秒、全command
25.21秒、最大RSS 248,256 KiB）。これは回帰gateであり、上記の実process/browser観測とは
区別する。ControlDeck変更は不要だった。

## UX2 PR-C5 — semantic evaluator + R9700 acceptance (2026-08-22)

既存のdeterministic validatorとC0 plannerの後段に、6軸（identity / style /
pose-action / scene / composition / obvious breakage）のCPU-only advisory
Evaluatorを追加した。候補asset IDだけを受け取り、結果を順位表示する。自動再生成は行わず、
評価前後のjob件数も不変である。入力は最大8候補・4参照・16KiB plan、画像は既存の
768x768 / 2MiB境界を再利用する。path入力、remote origin、壊れたJSON、timeoutは
`creative_evaluation_unavailable`でfail-closedする。public schema / addon.json /
agent tool / workflow executorは変更していない。

隔離ControlDeck（`127.0.0.1:18765`）と現在のMedia Forgeソース
（`127.0.0.1:19130`）、実Broker、R9700/gfx1201、保持済みNVMe modelを使った。
3件はすべてControlDeck Workflowからleaseを取得し、完了後に解放した。

```text
candidate 1                  15.967179 s; load 11.335529 / generation 1.584339
candidate 2                  17.460744 s; load 13.448332 / generation 1.461965
candidate 3                  19.440341 s; load 14.989607 / generation 1.592628
resolution / steps           512x512 / 4
first absolute VRAM peak     21,245,644,800 bytes
later absolute VRAM peaks    17,478,889,472 / 17,470,918,656 bytes
maximum worker RSS           16,494,501,888 bytes
worker swap                  0 bytes
lease renew / after          each 1 / active 0
model/revision               FLUX.2-klein-4B / e7b7dc27...a294
runtime                      Diffusers 0.40.0 / direct_device_map / cuda:0
weights / license            f3fcfa8f...ae278 / Apache-2.0
```

目視では3枚とも短い黒髪、オレンジメッシュ、黒/オレンジhoodie、顔と配色が
一貫し、端末提示・手振り・3/4 poseの差分が成立した。実出力と証跡は
`/data1tb/mediaforge-c5-e2e-20260822/`へ保持する。

Ollama 0.31.1の`qwen3-vl:2b` thinking tagは`think=false`を無視し、1画像でも
約105秒をreasoningだけに使ってcontentを空で返した。最初の3候補評価と切り分け1候補は
HTTP 422でfail-closedし、成功扱いしていない。非thinking rendererの同容量
`qwen3-vl:2b-instruct`（digest `ea422f1e7365`, 1,889,519,783 bytes,
Apache-2.0）へ切り替え、以下を実測した。初回pullは72%後に再試行したため、安定取得とは
記録しない。

```text
direct evaluator             3 candidates / 40.60 s
ranked first                 asset_906012a17a1145d399fc82545d639385
Media Forge jobs             3 -> 3
GPU VRAM before / after      59,949,056 / 59,949,056 bytes
regeneration_requested       false
installed-host iframe        40.222 s / same first candidate
320px overflow               0 px
browser console/page errors  0 / 0
semantic review instruct     accepted / first response 12.88 s / warm 2.08 s
```

workerをlease取得後1秒でSIGKILLしたprobeは1.374453秒で`worker_crash`へ正規化され、
active lease 0、core health `healthy`を確認した。既存の同一revision multi-reference
実測は`docs/models.md`のG2 supplementを採用ゲート証跡として参照するが、C5では再実行
していない。LoRAはcatalog metadataが`supports_lora=false`のため **UNAVAILABLE**。
共有Hostのkernel page cache dropは行わず、完全storage-cold loadは **NOT TESTED**。
ControlDeckコード変更とhosted CI利用はどちらも0件。

focused evaluator / semantic / frontend / workspace transport regressionは84 passed、
full `./mf.sh test`は262 passed（25.10秒）。これは契約回帰証跡であり、上記の
実Workflow/GPU/VLM/browser観測とは区別する。

## Release v0.3.0 — Creative direction workflow (2026-08-22)

UX2 M0〜C5を、ポーズ指定を含む最初のCreative direction機能版として公開した。
Release tagは、version bumpと全bundle入力を含むexact commit
`c4754ac26fb310978f1d806d0a55e4b993aabdee`を指す。動画候補catalogの作業中差分は
別worktree/別branchに隔離し、このartifactへ含めていない。

```text
release       https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.3.0
artifact      control-deck-media-forge-0.3.0-linux-x86_64.tar.gz
bytes         30,781,945
sha256        d8055331b96befc3de2bbf99cb3823ad6a5159158a0fab6521f40f8d719aa48f
build         18.02 seconds / max RSS 115,648 KiB
doctor        status=ok / version=0.3.0 / packaged=true
manifest      addon 0.3.0 / feature 0.3.0 / entrypoint bin/mediaforge
```

展開したbundleを`127.0.0.1:9140`で実際に起動し、source treeではなく配布binaryへ
HTTPとChromiumを接続した。標準workspace試験は20.52秒、desktop ready 0.076秒、
390px/320px horizontal overflow 0、console error 0件でPASSED。入力fixtureは既存の
858-byte PNG（SHA-256 `8314eb3e...e47`）を証跡directoryへ明示配置した。fixtureが
無い最初の試行は`FileNotFoundError`で停止しており、成功には数えていない。

ポーズ専用のbrowser試験は1.32秒で、`presenting_device` scene、`holding_item` pose、
`full_body_off_center` compositionが別々のCreativePlan fieldへcompileされ、model IDを
強制しなかった。`coding_at_desk + wave`の不正組合せはjob送信前に日本語理由付きで
拒否された。320x640 overflowは0、console/page errorは0/0。証跡は
`/data1tb/mediaforge-v0.3.0-evidence/`へ保持する。

version bump後の`./mf.sh test`は262 passed（24.97秒、全command 26.43秒、最大RSS
257,956 KiB）。これは回帰gateであり、上記の配布binary/HTTP/browser観測とは区別する。
v0.3.0 bundleのControlDeck trusted catalog導入・installed-host更新と、実端末の指操作は
**NOT TESTED**。動画runtimeはこのReleaseに含まれず **UNAVAILABLE**。hosted CIと
ControlDeckコード変更は0件。

## Creative Intelligence protected-field regression fix (2026-08-22)

PR #46 merge後のfull gateで、モデル応答がfull `PromptPlan`をechoすると、server-owned
`version / original_intent / mode`まで`PromptPlanDraft(extra=forbid)`へ渡され、意図を
保護する既存試験が`prompt_plan_invalid`で失敗する回帰を観測した。provider出力を
objectに限定し、この3 fieldだけをvalidation前に捨てる。その他の未知fieldは従来どおり
fail-closedであり、`provider_model`混入を拒否する試験を追加した。

```text
before full gate     1 failed / 272 passed（動画catalog統合branch上で観測）
focused after fix    7 passed
main full after fix  269 passed / 24.58 seconds
full command         26.06 seconds / max RSS 261,500 KiB
```

これはAI応答境界の回帰修正であり、実providerへのHTTP、実画像生成、GPU動作は
**NOT TESTED**。public schema / addon.json / agent tool / workflow executorは変更していない。
hosted CIとControlDeckコード変更は0件。

## Settings の拡張情報を詳細モードへ移動 (2026-08-22)

Settings の既定表示から「この拡張機能について」と capability 一覧を外し、ヘッダーの
「詳細」を選んだ時だけ `template` から DOM へ載せる詳細領域へ移した。モデル管理は
シンプル／詳細の両方に残し、backend の capability document と local-only 強制は変更して
いない。ControlDeck 側の変更も不要だった。

現在のソースを隔離data directory・`127.0.0.1:9140`で実起動し、Chromiumから標準workspace
試験を実行した。シンプル設定では `advanced-capability-list` が DOM に0件、詳細切替後は
11 capability が表示された。desktop ready 0.071秒、390px/320px horizontal overflow 0、
console/page error 0件で、全browser試験は20.5秒でPASSEDした。証跡は
`/tmp/mediaforge-settings-detail-evidence/`に置いた。

最初の試行はfixture不在の`FileNotFoundError`、2回目は試験が詳細モードからシンプルへ
戻さず後続mask検査へ進む問題で停止しており、成功には数えていない。installed-host iframe、
実端末の指操作、リリースbundleは **NOT TESTED**。hosted CIは使用していない。
full `./mf.sh test`は275 passed（28.86秒）。これは回帰gateであり、上記の実process/browser
観測とは区別する。

## Creative Intelligence CI-1 — provider-neutral AI cutover (2026-08-22)

productionのsemantic reviewerとCreative EvaluatorからOllama固有のURL、model、port、
`/api/tags`、`/api/chat`を除去し、ControlDeck `ai.inference` grant配下の
`vision.analyze`へ置き換えた。Media Forgeはcapabilityと画像data URL、構造化response schema
だけを送り、Host応答のprovider/model追加fieldは無視する。候補画像は768px・JPEG・2MiBに
制限し、最大4参照は1枚の決定的なreference sheetへまとめる。deterministic validation、
advisory既定、bounded retry/rankingは変更していない。

ControlDeck exact `d97508b103cd302add46e6bf26899613a46920c3`を、既存PR #226の隔離data
directory・`127.0.0.1:18776`で実起動した。現在のMedia Forge sourceは
`127.0.0.1:19131`、既存のexperimental fake worker fixtureを使い、source manifestを
Add-on v2として登録・`ai.inference`を含む11 grantでenableした。ControlDeck発行service
token経由のagent generationで次を観測した。

```text
target 1              qwen3-vl:2b-instruct / ControlDeck-selected Ollama
job                   job_f2ebdcfc33be4d0c881b6cfb017cd85b / succeeded
elapsed               7.510583 seconds
asset                 asset_aa62546278e94d0e8bb21c8eff54fe04
target 2              qwen3-vl:2b / ControlDeck-selected Ollama
job                   job_52ccfff09b304269bea80d6c52784304 / succeeded
elapsed               2.182804 seconds
asset                 asset_5df5b8d9449b40adb8c6b647ed748162
Media Forge config    target切替前後で変更0件
Host audit            addon.runtime.ai.complete / resource_id=vision.analyze
audit metadata        capabilityだけ。provider/model identityなし
```

2件目はsemantic rejectionを正しくadvisory warningとして返し、再生成要求0件だった。1件目は
summaryが意図不一致を述べた一方`accepted=true`を返すモデル品質上の矛盾を観測したため、
transport成功とは分けて品質PASSには数えない。これはCI-4 evaluatorで扱う課題である。

両VLMの`vlm_enabled`をfalseにした状態でagent capabilityが
`vision_analyzer_unavailable`となることを確認した。同じHost経路で`qa.semantic=false`の
prompt-only生成は0.492620秒、job `job_b73babe372414904aa1cdf76248c3542`、asset
`asset_47f39979736b4215be58bf04e0ba0b3c`でsucceededした。semantic=trueはjob
`job_dc773d1fdfd54d5cb7a757d50a9b3f3a`が`vision_analyzer_unavailable`でfail-closedした。

隔離Host停止前にruntime policyとmodel configを元へ戻し、試験でloadしたOllama VLMもunload
した。共有ControlDeckは`control-deck-web.service`を再起動し、`active`かつ
`GET /api/v1/health = {"ok":true}`を確認した。ControlDeck repository変更は0件で、既存の
`frontend/tsconfig.tsbuildinfo`差分は保持した。llama.cpp runtimeへの切替を通した
Media Forge再実行、installed release bundle、実画像workerは **NOT TESTED**。hosted CIは
使用していない。

focused CI-1 / semantic / evaluator / frontend / workspace / host execution regressionは116 passed。
full `./mf.sh test`は275 passed（23.36秒）。これは回帰gateであり、上記の実Host・service
token・target切替観測とは区別する。

## 画像モデルカタログ v1 (2026-08-22)

測定済み既定のFLUX.2 Klein 4Bに、用途が重複しない3候補を追加した。publisherの
Hugging Face APIから同日に取得したexact revision、各weightのsize/SHA-256を固定し、
canonical weight identity hashの再現試験を追加した。

```text
general/text quality    Qwen/Qwen-Image-2512 @ 25468b98 / external / 57,704,574,910 B
anime/illustration      Illustrious-XL-v2.0 @ 69459c1f / managed / 6,938,042,078 B
lightweight fallback    segmind/SSD-1B FP16 @ 60987f37 / managed / 4,468,829,801 B
```

3候補はすべて`experimental`、`measurement_confidence=low`、CUDA metadataのみ、
recommended profileなしである。未実測候補はROCm routerへ入らず、downloadしても
Availableへ昇格しない。Illustriousはbounded single checkpoint、SSD-1Bはbounded FP16
Diffusers setなので明示download対象にできる。57.7GBのQwenはruntime envelope未確定のため
externalのままにした。

単体workspaceが`/api/v1/models`の最小応答を全件「汎用画像」と推測していたため、trusted
catalog由来の表示metadataを既存Model schemaへoptional fieldとして加法追加した。既存required
field、routing、job/asset/provenance、agent/workflow契約は不変で、migrationとversion bumpは
不要。catalog metadataが無いregistryでは従来の最小応答のままである。

現在のsourceを`127.0.0.1:9142`で実起動した。実HTTPは全10件、画像4件を返し、既存FLUXだけが
available/installed/healthy、3候補はexperimental/not-installed/not-healthyだった。Chromiumの
単体workspaceでSettingsの「画像候補」を選ぶと次の4 cardが0.148秒で表示された。

```text
FLUX.2 Klein 4B
Qwen Image 2512
Illustrious XL v2.0
Segmind SSD-1B (FP16)
console / page errors       0 / 0
standalone action boundary  4 cardsすべて「CLI で管理」（UI installを偽らない）
```

private WebSocket、durable model operation、installerを使う既存実ブラウザfixtureも再実行した。
画像filter 2 cards、download tap 1、reload後のoperation復元、削除確認1、install 10.538秒、
390px/320px overflow 0、console/page error 0/0を観測した。最初の単体browser assertionは
仕様にない日本語「軽量」tagを期待して停止したため成功に数えず、実card名とadoption tagを
検査する形へ直して再実行した。

focused catalog/model manager/frontend/API regressionは67 passedと39 passed、最終
`./mf.sh test`は279 passed（28.51秒）。これは回帰gateであり、上記の実HTTP/browser観測とは
区別する。3候補のweight download、runtime adapter、R9700/ROCm推論、VRAM/時間/品質、
 installed-host iframeは **NOT TESTED**。ControlDeck変更とhosted CI利用は0件。

## Creative Intelligence CI-2 — Creative Director / action variations (2026-08-22)

既存PromptPlanner、CreativeCompiler、C3 durable batch/child Jobを再利用し、新規画像向けの
provider-neutral Creative Directorを実装した。UIは`そのまま` / `自動` / `演出強め`を持ち、
`text.generate`利用可能時だけSimpleの既定を`自動`にする。ActionStateは既存
`PoseSpec(preset=custom)`へbounded projectionし、canonical PromptPlanはprivate
CreativePlan/provenanceへ保存する。manual scene/pose/composition/cameraはDirector出力より優先する。

実モデル初回試験でprovider schemaの全fieldが省略可能だったため、`{}`が合法になり
`assistance_used=true`だが内容が空になる欠陥を観測した。この試行は成功に数えない。provider
向けstrict schemaだけ全object fieldをrequiredにし、内容ゼロも`prompt_plan_invalid`へ正規化して
fail-softにした。canonical product modelの既定値とpublic schemaは変更していない。

ControlDeck PR #226 merge commit `d97508b103cd302add46e6bf26899613a46920c3`の隔離Hostを
`127.0.0.1:18776`、source Media Forgeを`127.0.0.1:19131`で実起動した。隔離Hostから
現在稼働中のQwen3.8-27B llama.cpp endpointをControlDeck policyで選択し、Media Forgeには
provider/model/portを渡していない。実service tokenで次を観測した。

```text
Host capabilities             text.generate=true / vision.analyze=true
creative.text_direction       available
prompt-only Director          robot / inspecting / PoseSpec custom
original intent               compile後も先頭一致
canonical source              control-deck:text.generate
Host audit delta              text.generate 1 / vision.analyze 0
directed action batch         3 child Jobs / custom pose 3 / distinct action 3
batch Host audit delta        text.generate 1 / vision.analyze 0
batch persistence             reconnect getでchild 3件
```

画像生成は、共有LLMが25,166,778,368 bytesをresident使用しHost policyがexclusiveかつ
supervision=observedだったため、GPU leaseが`device_busy_exclusive`で正しく待機した。3 child
Jobsと先行確認jobは明示cancelした。installed-host browserの最終job
`job_e14912bacadd4328a5d6bdcfbdfc1a4a`は画面で待機を観測した後、8096 endpoint停止後にHostが
leaseをactivateし、fake workerがsucceeded、asset `asset_edd01a97d4ae4c658ed293050e559fb5`
1件、lease releaseまで到達した。最終確認はactive lease 0 / waiting request 0。この検証で
leaseを迂回してworkerを走らせていない。別のstandalone実プロセスではtext assistance unavailableを
`text_generator_unavailable`としてfail-softにし、元prompt不変のままCPU fake job
`job_337079b8298240abb00bf8cb83b56990`がsucceeded、asset 1件を返した。

実installed-host Chromiumでは`自動`が既定、Simple PoseがAuto時だけhidden、生成後の
「理解した内容」に元の希望・対象・動き/状態・scene・構図/camera・提案が表示された。
Hostは生成jobを「GPU の空きを待っています」と表示し、その後のjob terminalは上記のとおり
succeededだった。browser観測は16.581秒、console/page error 0件。
standalone Chromiumは390px/320pxともoverflow 0、3 mode、
理解した内容DOM 1、Advanced Pose到達を確認した。証跡は
`/tmp/mediaforge-ci2-hosted-ui.oeKn9z`と`/tmp/mediaforge-ci2-director-ui.uZ6kC2`。

実GPU画像生成、実画像品質、art_directの主観品質、reference付きVision連携（CI-3）は
**NOT TESTED**。focused CI-2 regressionは130 passed、最終`./mf.sh test`は287 passed
（24.93秒）。これは回帰gateであり、上記実Host／実browser観測とは区別する。
ControlDeck repository変更0件、hosted CI利用0件。

## Creative Intelligence CI-3 — Reference Intelligence (2026-08-22)

既存assetをPillowだけで測るversioned `VisualFacts` と、ControlDeck
`vision.analyze`から厳格な`VisualAnalysis`を得るprivate workspace経路を追加した。cache keyは
asset SHA-256とfacts/semantic analyzer versionから作り、同一bytesを別asset IDで参照しても
再解析しない。paletteは256px以内へ縮小してから量子化し、alpha 32未満を除外する。完全透過
画像へ黒を捏造しない。元assetは読み取りだけで、coreへtorch/transformers/OpenCVを追加していない。

Createには画像が存在するときだけ「全体／主役／動き／色／構図／画風」を表示する。選択した
観点のserver生成JSON要約だけをCreative Directorへ渡し、画像data URLはVision呼び出しだけに
留める。profileは変更しない。`そのまま`かつ参照なしではText/Vision呼び出し0件を回帰試験で
固定した。C3の3 childは同一cache要約を共有し、Vision呼び出しは親で1件だけだった。

ControlDeck PR #226 merge commit `d97508b103cd302add46e6bf26899613a46920c3`の隔離Hostを
`127.0.0.1:18776`、現在のMedia Forge sourceを`127.0.0.1:19131`、ControlDeckが選択した
Qwen3.8-27B + mmproj endpointを`127.0.0.1:8096`で実起動した。C5でR9700生成済みの
512x512 RGBA画像（SHA-256 `78fa04f7...f3a2`）をinstalled-host Chromiumから取り込み、
次を観測した。

```text
VisualFacts                    512x512 / alpha=true / opaque_fraction=1.0
Vision VisualAnalysis          50.353 seconds / subject=person / action=holding smartphone
facts cache                    573 bytes
semantic cache                 4,414 bytes
same asset second analysis     0.060 seconds / analysis_cache_hit=true
Director with pose summary     13.287 seconds / structured context 1件
Host audit delta               vision.analyze 1 / text.generate 1
original assistance            false / 追加audit 0
320px overflow                 0 px
browser console/page errors    0 / 0
evidence                       /data1tb/mediaforge-ci3-evidence-20260822/
```

最初のbrowser試行は存在しない一時model manifestを指定してworkspace初期化が停止したため、
成功に数えていない。その後の2試行で、長い実asset名が320px幅を95px押し広げる実不具合を
観測した。Director grid子の縮小境界と添付名の`overflow-wrap:anywhere`を追加し、fresh data/cache
で上記最終runを再実行した。最終確認はBroker active lease 0 / waiting request 0、試験用LLMを
unload、隔離Host/Media Forgeを停止、共有ControlDeckはactiveかつhealth okだった。

focused reference/director/batch/workspace/frontend regressionは109 passed。最終
`./mf.sh test`は303 passed（28.11秒）。これは契約回帰証跡であり、上記の実Host/Vision/browser
観測とは区別する。public schemas / addon.json / agent tool / workflow executorは変更していない。
C4 multi-cutのAI shot briefはCI-5、Evaluator統合はCI-4なので **NOT TESTED**。実GPU生成、
profileへの自動反映（仕様上行わない）、installed release bundleは **NOT TESTED**。
ControlDeck repository変更0件、hosted CI利用0件。
# MiniMax H3 bounded catalog and runtime evaluation (2026-08-22 to 2026-08-23, active)

The official `MiniMaxAI/MiniMax-H3` FL2VA revision
`42ed227ee7df40d41602854ae760620d6eb651fe` was measured from the Hugging Face
tree as 81 selected files / 144,051,182,625 bytes. A real managed download to
the NVMe model store was canceled at 1,865,101,859 bytes after the 32GB local
artifact limit was established. The operation reached `canceled`; its contained
`.downloads/modelop_2f7d58dbfd13401d94b3a6eb7d70c1c2` tree was absent afterward,
and no installed `models--MiniMaxAI--MiniMax-H3` repository existed.

The replacement candidate is `unsloth/MiniMax-H3-GGUF` revision
`d629413c2e5b51b38c453668b75ca3b06ca92703`: pruned FL2VA UD-Q2_K_XL,
Qwen3-VL Q2_K_M, and two Comfy-Org VAEs at revision
`0f7fb980293fcc4d55c1158cbda920806682ed5d`, totaling 26,978,277,946 bytes.
The installer now accepts only those catalog-pinned per-weight sources, requires
an exact license-acceptance identifier, rejects managed artifacts at or above
32,000,000,000 bytes before creating an operation, and still transfers one file
at a time directly under the configured model store.

Observed local gate after these changes:

```text
./mf.sh test
309 passed, 1 warning in 27.88 sec
```

The real GGUF download operation `modelop_0dfc422e9d9d480a996e02ba552d6b89`
ran sequentially against the NVMe feature-data model store from
`2026-08-22T14:12:33.901575+00:00` through
`2026-08-22T15:01:33.263368+00:00` (49 minutes 00 seconds). It reached
`ready` with `26,978,277,946 / 26,978,277,946` bytes and no error or cancel
request. The installed snapshot occupied 26,978,361,344 bytes; the NVMe had
657,629,118,464 bytes available afterward. The operation-specific temporary
download tree was absent after promotion, and catalog discovery reported
`installed=yes`, `healthy=no`, `state=experimental`.

An independent `sha256sum` over all four inference files completed in 17.49
seconds with 3,740 KiB maximum RSS. All values matched the catalog pins:

```text
denoiser      cfe0795c00ab6e6ebf8c64fe4574f45a828e8a93e0876bca704e055662a9d7b8
text encoder  a8ccadccd57ef34c838ffb8a7da8368bb554721b2760274a1d3b0df63960b997
video VAE     7c1f131492e7eddacaac9069a61b81bdd39de5cc96561e677c5eab1cdce5e522
audio VAE     8e505d95dd1561d47abd43d4238fd40d9bb1ae9e147ed0a4cba778d76ae4db48
```

This proves bounded download, verification, and installation only. The pinned
stable-diffusion.cpp runtime was then fetched at exact commit
`97d2990807fe6d558e395f8764198d7c7e7b411c` with pinned shallow submodules and
configured for HIPBLAS/gfx1201. The documented `clang` command first failed in
0.18 seconds because clang was not on `PATH`; using the ROCm 7.2.1 compiler at
`/opt/rocm-7.2.1/lib/llvm/bin/{clang,clang++}` configured successfully in 2.59
seconds. A single-parallel Release build completed in 539.64 seconds with
7,153,248 KiB maximum RSS. The runtime tree occupied 1,233,055,744 bytes and
the resulting `sd-cli` SHA-256 was
`7c2aebea172e4199da1307769a1b6dc38cecd73c102e3262351283702ed7de03`.

The first CLI smoke correctly exposed a missing runtime search path for
ROCm's `libomp.so`; no system library was installed. With the isolated runtime
library path `/opt/rocm-7.2.1/lib/llvm/lib:/opt/rocm-7.2.1/lib`, `sd-cli
--help` succeeded and `--list-devices` completed in 0.06 seconds / 86,796 KiB
maximum RSS. It reported the R9700 as `ROCm0`, gfx1201, 32,624 MiB VRAM, plus
the integrated gfx1036 GPU as a separate `ROCm1`; future evaluation must pin
the R9700 explicitly.

Immediately before inference, the host had 32,605,573,120 total RAM,
27,586,805,760 available RAM, and 1,516,511,232 bytes of swap already used.
The 26.98GB weight set therefore leaves too little evidence to assume that
full `--offload-to-cpu` will be practical. A mixed/streamed placement may still
be viable, but must be measured rather than inferred.

R9700 model load/generation, VRAM execution phases, RAM/swap deltas, output
quality, runtime cancellation, and prompt-recipe Gateway projection are still
**NOT TESTED**. They were not run directly because every GPU evaluation must
hold a ControlDeck lease, while this catalog slice does not yet provide an H3
worker/evaluator capable of receiving a Host service identity, creating its
Host Job, renewing the lease, and releasing it. An unauthenticated resource
probe returned HTTP 401 as designed; no token was forged, signing key read, or
unrelated model lease reused. Runtime evaluation may use bounded CPU/RAM offload even
when working memory exceeds 32GB VRAM, but only practical measured wall time,
safe RAM headroom, and absence of sustained swap thrashing can make that route
eligible. The 32,000,000,000-byte managed-artifact limit remains unchanged.
After recording the download checkpoint, the local full `./mf.sh test` gate
reported 309 passed and one dependency deprecation warning in 25.47 seconds.
After the runtime/device evidence update, the final local full gate reported
the same 309 passed and one warning in 26.30 seconds. Hosted CI
was not used, and ControlDeck repository changes remain zero.

## MiniMax H3 bounded evaluator implementation (2026-08-23, active)

A private Model Management evaluation action now accepts only the catalog-pinned
`unsloth/MiniMax-H3-GGUF` identifier. It creates or attaches a ControlDeck Host
Job, requests the broker with all four VRAM dimensions and
`estimated_runtime_sec=1800`, activates and renews the granted lease, observes
both local and Host cancel, and releases the lease in its isolation boundary.
The native command is an argument array with a fixed 640x384 / 5-frame / 1-step
bounded smoke preset. It pins `ROCm0`, places the text encoder on CPU and
diffusion/VAE on the GPU, and does not enable unbounded full CPU offload.

The evaluator records elapsed time, worker RSS/process swap, system swap-in and
swap-out page deltas, baseline/peak R9700 VRAM, output bytes/hash, and bounded
ffprobe metadata. The output and runtime log stay below the private data root;
no path, prompt, repository, URL, or command is accepted from the workspace.
Evaluation metadata is capped at 16 KiB. A service restart fail-closes an
in-flight evaluation because its short-lived Host identity cannot be resumed.

An isolated preflight using a temporary SQLite data directory and the actual
NVMe model/runtime roots returned
`available_model_ids=['unsloth/MiniMax-H3-GGUF']`. Focused evaluator, Model
Management, frontend-contract, Host-execution, and video-catalog tests passed
86 tests in 11.45 seconds. The full local gate after the evaluator changes was:

```text
./mf.sh test
317 passed, 1 warning in 31.12 sec
```

The isolated subprocess tests observed lease activate/renew/release, Host and
local cancellation, process-group termination, nonzero native exit isolation,
restart fail-closed behavior, fixed mixed placement, and video-plus-audio
validation. These are implementation/contract observations, not R9700 tensor
execution evidence. The real evidence is recorded in the following section.
Hosted CI was not used and the ControlDeck repository was not changed by this
evaluator slice.

## MiniMax H3 real R9700 evaluation and RAM-offload decision (2026-08-23)

The first installed-workspace action exposed two integration defects before a
model was allowed to run. The Host accepted and activated a real 33,073,741,824
byte lease, but consecutive forced Job progress updates exceeded the Host's
2 Hz limit and HTTP 429 was normalized to `host_request_rejected` in operation
`modelop_0bded9ab51d4431eb060a7f2d9331a3c`. `force=True` now waits until the
0.55-second progress interval instead of bypassing `ProgressGate`; a focused
clock-based regression test covers this behavior. The lease was released.

The workspace had also used `window.confirm()` even though the Host's opaque
iframe intentionally omits `allow-modals`; Chrome ignored the call and no
request was submitted. Gated license acceptance now uses an in-workspace
`dialog`, and the non-destructive evaluation action starts directly. An actual
installed-host Chromium action subsequently reached the evaluator with zero
console/page errors. The Host sandbox was not weakened.

Operation `modelop_c52ded655bbc4f3a8d5d1aee12bc7c79`, Host Job
`19498496a63a`, completed the shipped bounded smoke preset:

```text
input                         640x384, 5 requested frames, 1 step, 24 fps
elapsed                       160.860 sec
parameter placement           text encoder 13,985.83 MB RAM
                              diffusion + VAE 13,331.93 MB VRAM
peak process RSS              26,347,757,568 bytes
peak process swap             0 bytes
baseline / peak R9700 VRAM    59,912,192 / 14,614,786,048 bytes
incremental peak VRAM         14,554,873,856 bytes
system pswpin / pswpout       +1,167 / +192,766 pages
output                        122,118-byte WebM, SHA-256
                              0a66b4e5b71e769b5c10b6daf04de0ca5b4d5aa92b51e50d0143bd2617b6712a
media                         VP8 640x384 24fps 0.167sec + stereo PCM s16le
```

Independent `sha256sum` and `ffprobe` reproduced the stored hash and media
metadata. The extracted frame was inspected at original resolution and showed
an incoherent hair/skin smear with no complete person. A one-step smoke is not
a quality preset; it proves the native runtime and output validator only.

A second internal probe used the upstream README's 640x384, 25-frame, 4-step
shape to test useful quality. MiniMax aligned 25 frames to 39. Text conditioning
took 115.48 seconds, and diffusion tensor load then took 65.33 seconds. Sampled
RSS reached at least 19.78 GB, process swap at least 671.3 MB, and system
swap-free fell by about 1.31 GB before sampling ended. `systemd-journald`
reported memory pressure at 01:23:57, 01:24:01, and 01:24:24 JST. The
ControlDeck watchdog timed out at 01:24:30 and restarted the Host at 01:24:57.
Operation `modelop_93008f35df39411fbc3dcf885f6d30f8` failed closed as
`host_unreachable` after about 182 seconds; no video was written. The evaluator
then terminated its worker boundary. No GPU runtime crash is inferred from
these observations.

This quality route is rejected: placing working memory beyond VRAM into RAM is
permitted in principle, but it is practical only if measured wall time, safe
RAM headroom, non-growing swap, Host responsiveness, cancellation, and output
quality all pass. Here Host coexistence, swap behavior, completion, and quality
failed. The shipped evaluator therefore stays at the successful bounded smoke
preset, and H3 remains `experimental`, `healthy=no`, and unroutable. The
32,000,000,000-byte managed-artifact download limit is unchanged and is not a
working-memory limit.

Finally, an installed-host Chromium run started
`modelop_5881b25aec82401fbcb6bed66cbfdffb` and pressed the workspace cancel
button after 6 seconds. It reached `canceled` in 6.24 seconds with no browser
console errors; no `sd-cli` process remained. Host API `/api/v1/resources`
reported request `a0a10307-d048-4abf-8aa6-c0a8a6a51db0`, lease
`258a08cd-5fc5-4a9f-8a0d-b9398f00bcca` as `released`, and Host Job
`470a851b4cc5` as `canceled`. Hosted CI was not used. Public schemas,
`addon.json`, agent tools, workflow executors, and asset/provenance contracts
were not changed. The final local regression gate for this exact worktree was
`318 passed, 1 warning in 31.05s`; this is regression evidence and is not
substituted for the real browser, Host API, process, or R9700 observations
above.

## v0.3.1 release-bundle and installed Host update (2026-08-23)

PR #58 merged as `bcfa6701aee892f5fa2c574c5f6ae1f464fb1207`. An exact-head local
bundle build produced
`control-deck-media-forge-0.3.1-linux-x86_64.tar.gz`, 30,641,380 bytes,
SHA-256 `1b15eaa58f477bce982c3dcc3b093518c84382d11f8fc6bb7a9e1afe47dd30c4`.
The checksum file verified locally and the uploaded GitHub Release asset digest
reported the same value. The release target is the merge commit above.

The extracted bundle started as a real process on port 9137. Its isolated temp
data root correctly reported `setup_required`, rather than claiming a configured
runtime. Standalone Chromium then passed both light and dark runs with 32
advanced nodes, 320px/narrow overflow 0, console errors 0, deterministic edit
and outpaint assertions, and 13 capability states. Evidence is under
`/tmp/mediaforge-v031-evidence.bkUipk/` and is ephemeral local evidence.

ControlDeck PR #227 changed only the trusted artifact SHA. The first real
update failed closed before changing `current`, because the v0.3.1 manifest's
standard `ai.inference` capability was not yet in the trusted allowlist. The
existing v0.3.0 service was restored healthy. ControlDeck PR #228 then added
only that existing provider-neutral capability to the catalog allowlist; it did
not add a Media route, implementation, dependency, or UI string. The corrected
local Host gates passed 28 release-bundle/add-on-AI/contract tests. Hosted CI
was not used.

The second real Optional Feature Manager update succeeded:

```text
version:          0.3.1
state:            installed, managed, enabled, healthy
current:          versions/0.3.1
previous_version: 0.3.0
systemd main PID: 421078
```

Real HTTP `/health` returned contract 2.0 / healthy with the R9700 gfx1201,
ROCm Torch runtime, model library, and disk checks all `ok`. H3 evaluation was
not started without a normal authenticated workspace action: unsigned token
creation, signing-key access, and reuse of another job's lease remain forbidden.
Therefore actual H3 load/generation, RAM/VRAM/swap peaks, output validation,
real cancel, and quality remain **NOT TESTED**. The installed logged-in browser
was opened at `/x/media-forge/workspace/settings`; at that checkpoint the H3
card's `実機で評価` button remained unpressed. The later bounded smoke evidence
below supersedes that checkpoint.

After recording the exact release and installed state, the local full gate
remained 317 passed with one dependency deprecation warning in 28.02 seconds.

## v0.3.2 release-bundle and installed Host update (2026-08-23)

PR #60 merged as `676f8cce1e4ecdc929967a2923250440cc4de817`. An exact-head
local bundle build produced
`control-deck-media-forge-0.3.2-linux-x86_64.tar.gz`, 30,642,575 bytes,
SHA-256 `ec864154b9d5e79fdfee8f616d3b02bd74ac29f80fd10822ac676881de12e3d9`.
The checksum file verified locally and the uploaded GitHub Release asset digest
reported the same value. Release v0.3.2 targets the merge commit above. Hosted
CI was not used.

The extracted artifact started as a real process on port 9137. Its isolated
data root correctly returned `setup_required`, and the bundle served the
v0.3.2 manifest, in-workspace model dialog, and updated JavaScript. Standalone
Chromium passed light and dark runs with 32 advanced nodes, 13 capability
states, phone and 320px overflow 0, 60px mobile tabs, deterministic mask and
outpaint assertions, and zero console errors. The first attempts also exposed
that `scripts/ux_standalone_e2e.py` did not create its declared `sample.png`;
manual fixtures made the release checks pass, and this evidence slice adds a
dependency-free deterministic 64x64 PNG writer so future runs are self-contained.
Evidence is under `/tmp/mediaforge-v032-evidence.9nl0ol/` and is ephemeral.

ControlDeck PR #230 changed only the generic trusted-catalog SHA and merged as
`a47e4175e55f74d18b20bb5400b2fea96d048167`. No route, provider code,
dependency, capability, or Media-specific UI string was added. From the Host's
expected backend cwd, the local release-bundle, Add-on AI, and contract gate
passed 28 tests in 1.18 seconds. A prior invocation from the repository root
failed two subprocess CLI checks because `app` was not importable from that
cwd; the correct invocation passed and no code change was needed.

The real Optional Feature Manager update completed in 23.59 seconds:

```text
version:             0.3.2
state:               installed, managed, enabled, healthy
current:             versions/0.3.2
previous_version:    0.3.1 (update result)
retained versions:   0.3.1, 0.3.2
systemd main PID:    474013
```

The installed service unit and `current` symlink both resolve to v0.3.2. Real
HTTP `/health` returned contract 2.0 / healthy with core, ROCm runtime, R9700
gfx1201, model library, and disk checks all `ok`. An authenticated installed
Chromium session observed Host bridge `ready`, the H3 card and evaluation
button, the new model dialog, and zero console/page errors. Host
`/api/v1/resources` reported zero active Media Forge leases.

The shared data/model boundary was preserved. Before and after update the H3
snapshot occupied 26,978,278,484 bytes, and the denoiser blob independently
hashed to its pinned
`cfe0795c00ab6e6ebf8c64fe4574f45a828e8a93e0876bca704e055662a9d7b8`.
No native H3 worker remained. The update did not delete Media Forge assets,
models, feature data, or shared caches. Public contracts were unchanged. After
the self-contained light/dark browser rerun, the local full regression gate was
`318 passed, 1 warning in 29.34s`; tests are not substituted for the installed
service, browser, Host API, and filesystem evidence above.

The evidence and self-contained E2E fixture merged in Media Forge PR #61 as
`4c310cb19d26bbf548c93c145a24f84314a0cd80`. ControlDeck recorded the Host-side
update in PR #231 as `ee28acb1527ccad8856bacbad297c7954bc55739`.

## MiniMax H3 version-pinned prompt recipe (2026-08-23)

Media Forge now owns a private `minimax-h3-prompt-writing` projection based on
the upstream `skills/h3-prompt-writing` layout at commit
`d21241f0a4b3acbb34c97dae47fa417b7065e438`. The adapter supports T2VA, I2VA,
FL2VA, L2VA, and Ref2VA without adding a public model-specific API. It bounds
duration to 4--15 seconds, validates mode-specific reference counts, assigns
`<Picture n>` / `<Video n>` / `<Audio n>` labels, validates required and unknown
labels, preserves caller-declared dialogue/lyrics/visible text verbatim, and
renders a fixed three-field or six-field result. Arbitrary skill execution,
repository/path/command input, and Media Forge provider/model/port selection do
not exist.

The upstream skill text was not vendored because that pinned repository commit
has no root license file covering it. The consulted `SKILL.md`, `base-en.txt`,
and `ref-en.txt` hashes are pinned in code as
`a7000443588ca3f145e3b3fd8900f14e0325dc460bd811268fac89a9dc8e56d0`,
`2cfebc096a6e08370f288d468d90b60f7f9bcb938f94bf090816e910e48e75fc`, and
`1e574f356716ad55612247ffb7bbccbcdb484ad96599d63c7dca1af186b1fab7`.
This records provenance without redistributing the source text.

An isolated real ControlDeck process on port 18776 used its normal AI routing
policy and a normal Add-on bridge service identity. A source Media Forge process
on port 19131 submitted a prompt-only T2VA projection. ControlDeck selected and
served its configured text model; Media Forge sent exactly one
`text.generate` request and no `vision.analyze` request. The successful warm
request completed in 14.126 seconds and returned a 1,519-byte rendered prompt
with the required field order and the Japanese dialogue string preserved. Host
audit entries recorded only capability `text.generate`; no provider/model
identity was added to Media Forge provenance.

The first real response was strict-schema JSON inside one Markdown JSON fence.
The initial parser rejected it as `prompt_recipe_invalid`; the adapter now
accepts exactly one bounded JSON fence while still rejecting surrounding prose.
A projection that omitted required verbatim text also failed closed, and a
subsequent corrected projection succeeded. No automatic retry loop was added.
After the run, the selected text runtime was unloaded, Broker active/waiting
counts were both zero, isolated processes were stopped, and the shared installed
v0.3.2 service remained healthy on port 9130. ControlDeck source changes were
zero; its pre-existing `frontend/tsconfig.tsbuildinfo` modification was not
touched.

Focused recipe/workspace transport tests passed 38 tests. The full local gate
was `333 passed, 1 warning in 34.60s`. Hosted CI was not used. Public schemas,
`addon.json`, agent tools, workflow executors, and asset/provenance contracts
were unchanged. Real H3 generation with this projection, video quality, and a
release bundle containing this slice are **NOT TESTED**. H3 remains
Experimental, unhealthy, and unroutable. CI-4 Unified Evaluator was completed in
the following slice; public G7 video work remains deferred.

## Creative Intelligence CI-4 — Unified Evaluator (2026-08-23)

The former binary semantic reviewer and C5 six-axis evaluator now converge on
one `HostCreativeEvaluator` and the canonical `EvaluationResult` dimensions:
`intent`, `subject_identity`, `action_state`, `palette`, `composition`, `style`,
`props_clothing`, and `visual_integrity`. `semantic_review.py` and its binary
provider schema were removed. The frozen `qa.semantic`,
`image.semantic_review`, and `semantic_review_exhausted` contract names remain
compatibility entrances/results, but they no longer select a second reviewer.

Deterministic PNG/edit/outpaint validation still completes first. Normal
single-candidate generation with `qa.semantic=false` performs no VLM call.
Explicit comparison and opt-in QA use the same evaluator. Only dimensions
implied by user controls and reference roles are scored; all other dimensions
must be null or the provider result fails closed. Acceptance and advisory rank
derive from that result. Opt-in regeneration consumes only the existing 0..3
candidate budget, and provenance records scores, issues, strengths, retry
suggestions, relevant dimensions, review budget used, and capability-level
evaluator identity. It records no required provider/model identity. If the
evaluator is unavailable or invalid, deterministic-valid output remains usable
with an explicit advisory warning.

Focused evaluator, QA, and Creative Intelligence tests passed 30 tests. They
cover palette-only references not scoring action, role-specific dimensions,
irrelevant-score rejection, deterministic failure preceding VLM, advisory
single-candidate behavior, second-candidate acceptance with
`review_budget_used=2`, bounded exhaustion, evaluator-unavailable degradation,
and existing C5 result-stage ranking.

For real acceptance, an isolated ControlDeck on port 18776 and source Media
Forge on port 19131 used a normal login, bridge handshake, and Host-issued
service identity. Two deterministic 192x192 imported PNG candidates were sent
through the existing `creative.evaluate` workspace method. The request
completed in 18.338 seconds, returned two advisory ranked results, requested no
regeneration, and populated only `intent` and `visual_integrity`; the other six
canonical scores were null. Both candidates were accepted with rank score 100.
This is transport/schema/ranking evidence for deliberately simple fixtures, not
a broad subjective-quality benchmark.

The isolated Host audit DB contained exactly two successful
`addon.runtime.ai.complete` entries, each with only capability
`vision.analyze`. Broker active leases and waiting requests were both zero.
The ControlDeck-selected text/vision runtime was unloaded, ports 18776, 19131,
and 8096 were closed, the shared Add-on registry was restored byte-for-byte to
its pre-test normalized v0.3.2 manifest, and installed port 9130 remained
healthy. ControlDeck source changes were zero; the pre-existing
`frontend/tsconfig.tsbuildinfo` modification was untouched.

Installed-bundle browser behavior, release bundle creation, real FLUX candidate
evaluation, and subjective ranking across complex reference roles are **NOT
TESTED** in this slice. Public schemas, `addon.json`, agent tools, workflow
executors, and asset/provenance contracts were unchanged. Hosted CI was not
used. G4 Coding Agent project/output grant placement was completed in the later
section below; G7 video remains deferred.

The final full local regression gate for this worktree was
`336 passed, 1 warning in 32.36s`. This is regression evidence and is not
substituted for the real Host bridge, AI audit, process, or cleanup observations
above.

## G4 prerequisite design correction (2026-08-23)

Repository inspection found that ControlDeck already provides browser-issued
read/export grants and atomic Runtime output commit, but its OpenCode Add-on MCP
token is not bound to the current project and has no non-interactive generic
project-output grant tool. Therefore the earlier roadmap statement that all G4
Host acceptance was implemented was too broad. Media Forge cannot close this
gap without receiving or deriving a raw Host project path, which is forbidden.

`controldeck-integration-plan.md` §11.1 now defines the minimum generic Host
prerequisite: bind the MCP token to an already-resolved managed project and
issue an opaque Add-on output grant for a bounded existing project-relative
directory. No Media-specific Host route/policy is permitted. Host
implementation, Media Forge `media.pack`, atomic real project placement,
OpenCode code-reference update, and build/test are **NOT TESTED** at this design
checkpoint. The docs-only worktree retained the full regression gate at
`336 passed, 1 warning in 33.19s`; hosted CI was not used.

## G4 Coding Agent project asset placement (2026-08-23)

ControlDeck PR #232 implemented the minimum generic prerequisite from
`controldeck-integration-plan.md` §11.1: direct CodeDEV child projects are bound
to job-scoped OpenCode MCP tokens, and eligible Add-ons can receive an opaque
project output grant for one bounded existing subdirectory. Root, traversal,
backslash, and symlink escape requests fail closed. PR #233 changed the generic
generated MCP client timeout from 10 to 135 seconds, above the existing 120-second
Host Agent Job and 130-second stdio bridge bounds. Neither Host change contains a
Media-specific route, provider, model, or path contract.

Media Forge adds the `media.pack` agent tool and additive
`project-asset-placement.json` schema. It accepts only an immutable Media Forge
asset ID, an opaque export `grant:` ID, and an optional safe filename. It requires
the token-bound correlation job, rejects raw paths and MIME/extension mismatch,
then reuses the existing Host staged upload and atomic commit. The response
contains the Host `asset:` ID, Media Forge asset ID, filename, MIME, size, and
SHA-256; it contains no project/model/provider/path identity.

Real acceptance used installed ControlDeck, the source Media Forge on port 19131,
OpenCode 1.18.18, the configured local 27B text/vision runtime, and R9700 gfx1201.
The first resource attempts correctly exposed and retained three failures:

```text
observed supervision       resource_unavailable / insufficient_capacity
old generated MCP config  request timed out at 10.006 and 10.005 seconds
pre-fix semantic QA       image worker ended but its exclusive lease remained,
                          so vision runtime load and job waited until endpoint timeout
```

The semantic-QA deadlock was fixed by canceling lease maintenance and confirming
the image generation lease release immediately after the worker exits, before
deterministic post-processing can opt into `vision.analyze`. Release failure now
fails the job closed instead of starting Host AI while ownership is ambiguous.
The Host audit shows the successful final lease activated at 09:21:28, renewed
seven times, and released at 09:22:43; only then did `vision.analyze` complete at
09:23:06. A regression records an empty Host reserved-lease snapshot at the AI
call. Repeated diagnostic runs entered the Broker anti-thrash window, so the final
run explicitly stopped the then-idle LLM before the tool request; a preceding run
had already demonstrated automatic managed yield to the same R9700 worker.

The successful OpenCode run performed the planned sequence without human file
placement:

```text
project inspect           README.md / index.html / package.json / verify.mjs
media.generate            107.901 seconds, capability auto, local_only=true
worker                    load 64.520666 s / generation 1.236461 s
Media Forge asset         asset_c591c6e3e07b43a094a0b76be1f006ec
output                    PNG RGBA 256x256 / 73,238 bytes
SHA-256                   a10381bf2e99f650f69b145cb5457f2ac816885e77a6a82bd16aef41f085a45e
deterministic validators  non-empty / dimensions / mode / alpha all passed
unified evaluator         accepted; intent 1.0 / visual_integrity 1.0
Host output grant         opaque grant only; no path returned to Media Forge
Host committed asset      asset:d21d042b-444d-4cc3-9fa0-5e5e68522b0e
code update               index.html -> assets/player-robot.png
npm run build             PASS / verified 73238 byte project asset
npm test                  PASS / verified 73238 byte project asset
```

The committed Host asset size and SHA match the immutable Media Forge asset. A
visual inspection confirmed a readable centered blue robot with transparent
background; this is direct output-quality evidence for this one 2D-game fixture,
not a broad model-quality benchmark. Focused host/evaluator regression passed 47
tests. The final full gate passed 344 tests in 34.58 seconds with one upstream
Starlette/httpx deprecation warning. The exact-head bundle, extracted bundle,
installed update, and installed-browser acceptance were completed in the release
section below. Hosted CI was not used.

## v0.4.0 G0–G4 release-bundle and installed Host update (2026-08-23)

Release v0.4.0 targets G4 merge commit
`5a340ac2a9729b1fd591e4287c7adfca1252ff4a`. The exact-head local bundle is
`control-deck-media-forge-0.4.0-linux-x86_64.tar.gz`, 30,971,889 bytes, SHA-256
`51ee55c1da6d491852e145d6e2fc42b1b46eccedfae50176b1a34d6ba5f98799`.
The local checksum and GitHub Release asset digest match. Hosted CI was not used.

The extracted artifact ran as a real process on port 9137 with an isolated data
root. It correctly returned `setup_required`, contract 2.0, and
`agent_tool:media.pack=available`; the packaged manifest reported version 0.4.0
and the additive `media.pack` endpoint/schema. Standalone Chromium light and dark
runs both passed with 32 advanced nodes, 13 capability states, mask/outpaint
pointer assertions, 390px and 320px overflow 0, 60px mobile tabs, and zero
console errors.

ControlDeck PR #234 changed only the generic trusted artifact SHA and merged as
`f716630b9067ca0d91ffe2722ac75ce849bb5ac6`; PR #235 records Host evidence.
The release-bundle/Add-on-AI/contract focus passed 28 tests in 1.19 seconds.
The real Optional Feature Manager update completed in 12.75 seconds with max RSS
784,004 KiB and returned version 0.4.0, previous version 0.3.2, installed,
managed, enabled, and healthy. `current`, service WorkingDirectory, and ExecStart
all resolve to v0.4.0; versions 0.3.2 and 0.4.0 are retained. Real HTTP health
reported every R9700 gfx1201/ROCm/model/disk setup check `ok`.

The first installed-browser attempt stopped on a stale E2E fixture assertion:
the current UI intentionally has six ratio presets plus custom, while the script
still required exactly three. The fixture now verifies the six named bounded
presets, 16-pixel divisibility, and a dimensionless custom choice. Rerun light
and dark Chromium both passed with Host bridge `ready`, correct theme tokens,
advanced-mode persistence across reload, Host route sync, 390px overflow 0,
60px tabs, two-column mobile library, and zero console/page errors.

Post-update cleanup observed Host active lease 0, waiting request 0, Media Forge
lease 0; saved Media Forge jobs 41 with active 0; and no image/video worker.
The H3 snapshot remained 26,978,278,484 bytes and its 8,063,029,344-byte denoiser
blob retained SHA-256
`cfe0795c00ab6e6ebf8c64fe4574f45a828e8a93e0876bca704e055662a9d7b8`.
All 94 asset files remained. Browser-test sessions were revoked and the existing
fixture user's password hash was restored after each run. H3 quality generation,
public video generation, CI-5, and CI-6 remain **NOT TESTED** by this release.
The final release-evidence worktree regression gate passed 344 tests in 34.55
seconds with one upstream Starlette/httpx deprecation warning.

## Creative Intelligence CI-5 — C4 shot direction (2026-08-23)

C4 multi-cut compositions now accept the existing Director mode and accepted
Reference Intelligence context. For non-`original` mode, Media Forge sends one
provider-neutral `text.generate` request and validates exactly 2--4 structured
shot briefs. Count, index, and the `main` / `coding` / `device` / `chibi` roles
are supplied and revalidated by Media Forge rather than selected by the model.
The accepted parent plan and per-shot action, scene, composition, camera, and
details are projected into the existing normal child Job path. The existing C4
Composer remains authoritative for crop, frame, safe margins, dimensions, and
exact title/caption. Exact composition text is absent from the diffusion child
plans.

No new generation, batch, composer, evaluator, or retry subsystem was added.
The CI-4 `EvaluationResult` path remains the only semantic evaluator, and the
existing `qa.semantic` 0..3 budget is preserved. An accepted reference analysis
is reused across children. Prompt-only composition does not request
`vision.analyze`. `original` mode makes no AI call, and unavailable, invalid,
duplicate, or non-distinct AI results fail soft to deterministic C4 planning.

Real installed-ControlDeck structural acceptance used the source service on
port 19132, the installed Host on port 8765, its configured Qwen3.8 27B text
runtime, R9700/gfx1201 Broker, and the existing fake image worker. The successful
browser run completed in 64.452 seconds and observed:

```text
Director calls              1 text.generate / 0 vision.analyze
composition                 composition_0914b433af5d44aa8a877c9ab8578e4b
server-owned roles          main / coding / device
ordinary child Jobs         3 succeeded
shot assets                 3
deterministic final assets  1
exact text                  CI5 EXACT TITLE / CI5 EXACT CAPTION, composer only
mobile                      320px overflow 0
browser errors              console 0 / page 0
wall time                   64.452 seconds
```

The fake worker declares a one-second resource estimate while the selected
LLM's measured yield threshold was 47.188 seconds. Broker therefore correctly
reported `yield_thrash_cost` instead of evicting the LLM for a shorter fake
task. After an explicit operator `llama.stop_instance()` action, the three
ordinary child requests were granted in order; all three leases activated and
released, and the final restored Host snapshot had active leases 0, waiting
requests 0, lease-reserved bytes 0, and no resident key. This is bounded
structural/transport evidence, not evidence that a one-second fake workload
should trigger automatic managed yield.

Initial setup recorded one rejected test configuration and one real integration
defect. A raw source manifest was rejected because it lacked the Host-normalized
runtime contract; the test then used the installed normalized manifest with
only its loopback base URL changed. With that corrected, three concurrently
waiting child Jobs eventually received HTTP 429 from Host progress updates: the client scheduled at
the exact 0.5-second boundary using request-start time and repeatedly sent the
same waiting state, while resource and cancel state were each polled every 0.1
seconds. Media Forge now uses a 0.65-second progress margin, suppresses identical
waiting reports, and polls waiting resource state at 0.5 seconds. Focused Host,
workspace, composer, Creative Intelligence, and frontend regression passed 147
tests. The full local gate passed 351 tests in 38.71 seconds with one upstream
Starlette/httpx deprecation warning.

After acceptance, test browser sessions 457--460 were revoked and the fixture
password hash restored. The Add-on registry, state, and runtime policy were
restored byte-for-byte to SHA-256 `ceefb170451e3f396de4e4ac6c6f28d2c1374e9629de667a4788f814aeca5556`,
`9d56a834f40c90cdd3784e8d10abceddd23fa87e6c0a24dca7ce9c7379d220c4`,
and `4aa1aa93f1051dbe1d5e5b3addaa1be60ac2d964f7a4ee3d07173cedc0abbc2f`.
Installed v0.4.0 returned healthy on port 9130 with `observed` supervision and
120-second minimum uptime. ControlDeck remained at exact `origin/main`; its
pre-existing `frontend/tsconfig.tsbuildinfo` modification was untouched.

Automatic managed text-to-real-image handoff, real R9700 multi-shot image
generation, identity/style consistency, evaluator ranking of real child
candidates, subjective final-composition quality, 390px installed acceptance,
and a release bundle containing CI-5 are **NOT TESTED**. These remain CI-6
acceptance items. Hosted CI was not used and public frozen contracts were not
changed.

## v0.5.0 CI-5 release-bundle and installed Host update (2026-08-23)

Release v0.5.0 targets CI-5 merge commit
`8e822876864a48078edd41e5ca3a8957d78da067`. The exact-head artifact is
`control-deck-media-forge-0.5.0-linux-x86_64.tar.gz`, 30,982,625 bytes,
SHA-256 `9e24c3bff45cc4ab1763269758c202c55ab60ffd517664b1775bbd8eeecfa0be`.
The local checksum and GitHub Release digest match.

The extracted bundle ran on port 9137 from
`/tmp/mediaforge-v050-extracted.GK26Zm` with an isolated data root and returned
`setup_required`, contract 2.0, and `media.pack=available`. Standalone light and
dark Chromium runs reported ready in 0.130 and 0.125 seconds, 32 advanced nodes,
all six bounded ratio presets plus custom, 320px overflow 0, 60px mobile tabs,
a two-column phone library, and zero console errors.

ControlDeck PR #236 changed only the trusted catalog artifact SHA and merged as
`0b56d309fa1cafe195012a0961cf20f6e7bd1a8c`. Its focused release-bundle tests
passed 28 tests in 1.22 seconds. The real feature update from v0.4.0 completed in
15.29 seconds with max RSS 784,384 KiB and swap operations 0. Installed status
reported v0.5.0, managed, enabled, and healthy; retained versions are v0.4.0 and
v0.5.0. The pre-update 94 asset files and 67,170,534,265-byte feature-data root
were retained. Hosted CI was not used.

## Creative Intelligence CI-6 — installed Host and R9700 gate (2026-08-23)

Acceptance used installed ControlDeck on port 8765, installed Media Forge
v0.5.0 on port 9130, the Host-selected Qwen3.8-27B Vulkan text/vision target,
and FLUX.2 Klein 4B on the R9700/gfx1201 ROCm worker. The add-on effective state
contained `ai.inference`. Media Forge `config/config.yaml` remained SHA-256
`9a0acf73dbacc75a02df29ae19cd88b042d988c3959a9b9243a861a2c8bb80e2`
and contains no provider, model, or port selection. CI-1 acceptance had already
switched between two ControlDeck-selected Qwen3-VL Ollama targets with zero
Media Forge config changes; this run used the later Qwen3.8 llama.cpp target
through the same capability contract.

The v0.5.0 real-reference run imported the retained 512x512 character image.
`vision.analyze` completed in 50.263 seconds, the same asset hash hit the cache
in 0.061 seconds, and the reference-aware Director completed in 11.851 seconds.
The Host audit delta was exactly `vision.analyze`, then `text.generate`.
Original mode used no assistance. The installed iframe had 320px overflow 0
and browser errors 0.

The main R9700 run produced these results:

```text
prompt-only Director       15.218 s / text.generate 1 / pre-generation vision 0
uncommon human action      custom one-handed backbend pose / 17.107 s image Job
original non-human action  solar-panel rover / Director calls 0 / 22.407 s image Job
C3 action variation        text.generate 1 / 2 child Jobs / 37.504 s total
child actions              welding cracked panel / replacing blown fuse
generated outputs          4 PNG RGBA assets at 256x256 / deterministic validation PASS
QA budget                  semantic=false / max_regeneration_attempts=0 / retries 0
installed mobile           390px overflow 0 / 320px overflow 0
browser                    console errors 0 / page errors 0
```

Visual inspection confirmed the human backbend and lantern, an orange rover
with deployed solar panels, an orange robot welding with visible sparks, and a
second orange robot working at a fuse panel. This is direct evidence for these
five bounded prompts, not a broad FLUX quality benchmark or a claim of perfect
identity consistency.

Explicit unified evaluation compared the two real C3 candidates in 34.456
seconds and ranked the welding asset first for the welding intent. Generation
Job count remained 46 before and after, proving advisory evaluation created no
new Job. Its 320px overflow and browser errors were zero.

For fail-soft acceptance, the installed grant and image capability remained
present while compatible Host text/vision targets were temporarily reduced to
zero. Director returned `host_ai_unavailable`; the unchanged prompt-only path
generated a validated solar-panel rover in 20.088 seconds. The add-on state,
Qwen role selection, and Broker policy were restored afterward. Removing the
grant itself was also tried and correctly made the Host hide the contribution
as missing a declared requirement; that pre-generation attempt is not counted
as the AI-unavailable generation result.

Before managed handoff, resident Qwen used 31,582,920,704 of 34,208,743,424
R9700 VRAM bytes. The real image lease automatically yielded it and VRAM fell
to approximately 8.1 GB before worker loading. The sampler observed maximum
GPU use 98%; swap moved from 3,631,087,616 to a maximum 3,994,058,752 bytes.
After all tests, ControlDeck reported requests 0, leases 0,
lease-reserved bytes 0, resident keys 0, and R9700 VRAM used 59,924,480 bytes.
RAM available was 28,657,033,216 bytes and swap used 3,917,365,248 bytes.

All temporary browser sessions were revoked and the fixture password hash was
restored. Add-on state returned to SHA-256
`9d56a834f40c90cdd3784e8d10abceddd23fa87e6c0a24dca7ce9c7379d220c4`;
runtime policy returned to `observed` with 120-second minimum uptime. Installed
v0.5.0 remained healthy. The retained H3 snapshot stayed 26,978,278,484 bytes
and its 8,063,029,344-byte denoiser retained SHA-256
`cfe0795c00ab6e6ebf8c64fe4574f45a828e8a93e0876bca704e055662a9d7b8`.
H3 quality was not retried and remains experimental, unhealthy, and unroutable.
Public video generation remains **NOT TESTED**. Hosted CI was not used and the
frozen public contracts were unchanged.

The final canonical local regression gate passed 351 tests in 42.27 seconds
with one upstream Starlette/httpx deprecation warning. This is regression
evidence and is not substituted for the installed browser, Host audit, Broker,
R9700, provenance, or visual observations above.

## Worker/core image composition boundary (2026-08-23)

The image worker no longer imports `mediaforge.image_edit` or
`mediaforge.outpaint`. Worker-owned PIL planning/composition now lives in
`worker_packs/image/edit_composition.py`. The independently implemented core
`validate_strict_edit` and `validate_outpaint` remain authoritative after the
worker exits; no worker validation result is trusted or reused by core.

The real worker environment now sets `PYTHONPATH` to the worker-pack root only
and does not inherit the parent development path or expose `backend`. The
release builder no longer ships `backend/mediaforge` source as worker data. A
static AST regression rejects every absolute `mediaforge` import under the
image worker pack, and the bundle regression rejects reintroducing core source
for the worker. Frozen public schemas, `addon.json`, operations, tools,
provenance, and Host contracts did not change.

Focused strict-edit, outpaint, adapter, routing, and bundle regression passed
48 tests. Real acceptance stopped the installed v0.5.0 unit and ran the exact
source branch on the same port 9130 with the installed data, model store, ROCm
runtime, and ControlDeck Host/Broker path. The installed unit was restored
afterward.

```text
strict edit       20.106 s / asset_486013ae0738421c9cad20fab48fb115
worker timing     load 10.639245 s / generation 5.877777 s
core validator    protected pixel difference 0 / editable pixels 10,179
outpaint          107.367 s / asset_2bcb5869f4b44471b249af134a42fb04
worker timing     load 8.383039 s / generation 94.004853 s
core validator    source pixel difference 0 / generated pixels 131,072
placement         all components cuda:0 / offload hooks 0 / non-GPU targets 0
browser errors    0
Broker cleanup    active 0 / waiting 0 / reserved bytes 0
```

Visual inspection confirmed the strict result retained the source outside the
mouth edit and the outpaint result retained the complete centered 512x512
source while generating both side regions. The first browser attempt was
**not** a generation result: the historical G2 fixture still targeted a removed
operation select and stopped before asset import or GPU work. The dedicated
boundary fixture uses the current opaque bridge and completed both Jobs.

Installed v0.5.0 returned healthy after restoration, no image worker remained,
and R9700 VRAM use was 59,924,480 bytes. H3 quality was not run. Hosted CI was
not used. The final canonical local regression gate passed 352 tests in 37.33
seconds with one upstream Starlette/httpx deprecation warning. G5 M5 companion
profiles/validators/pack are the next slice.

## v0.5.1 worker-boundary release and installed Host update (2026-08-23)

Release v0.5.1 targets worker-boundary merge commit
`2b3114dd8e2c92c1b4464a1c2d600b0a8aff57cd`. The exact-head artifact is
`control-deck-media-forge-0.5.1-linux-x86_64.tar.gz`, 30,585,125 bytes,
SHA-256 `a615fc014d6584c255c72399b40963dbc06a4f5bd99d02ee3137b083f7409c0f`.
The local checksum and published GitHub Release digest match.

PyInstaller archive inspection found
`worker_packs/image/edit_composition.py` and the FLUX adapter, and found zero
worker data entries for `mediaforge/image_edit.py` or `mediaforge/outpaint.py`.
The extracted bundle ran on port 9137 with an isolated data root and returned
`setup_required`, contract 2.0, and the existing contributions. Standalone
Chromium reported ready in 0.082 seconds, 32 advanced nodes, 320px and narrow
overflow 0, 60px tabs, a two-column phone grid, and console errors 0.

ControlDeck PR #237 changed only the generic trusted artifact SHA and merged as
`ab2b9c82440f5e6adfb8833ce38ea7983ddf89bf`. The canonical backend-cwd
release-bundle/Add-on-AI/contract suite passed 28 tests in 1.19 seconds with one
upstream warning. An earlier root-cwd invocation passed 26 but failed two CLI
subprocess tests because `app` was not on their module path; that environment
mistake is not counted as a product result.

The real Optional Feature update completed from v0.5.0 to v0.5.1 in 11.51
seconds with max RSS 786,632 KiB and swap operations 0. It retained the existing
116 asset/provenance files and 67,174,355,135-byte feature-data root. Installed
worker acceptance then produced:

```text
strict edit       13.086 s / protected pixel difference 0 / editable 10,179
outpaint          108.380 s / source pixel difference 0 / generated 131,072
browser errors    0
installed light   bridge ready 0.639 s / mobile overflow 0 / console errors 0
installed dark    bridge ready 0.638 s / mobile overflow 0 / console errors 0
```

Final `current`, service WorkingDirectory, and ExecStart resolved to v0.5.1;
versions v0.5.0 and v0.5.1 were retained. Status was active, running, enabled,
and healthy. The persistent asset/provenance file count became 126 after the two
source/mask/result groups, with feature data 67,177,490,449 bytes. Broker active
leases, waiting requests, and reserved bytes were zero, no image worker
remained, and R9700 VRAM use was 59,924,480 bytes.

The H3 snapshot remained 26,978,278,484 bytes and its 8,063,029,344-byte
denoiser retained SHA-256
`cfe0795c00ab6e6ebf8c64fe4574f45a828e8a93e0876bca704e055662a9d7b8`.
H3 quality was not retried. Hosted CI was not used and frozen public contracts
were unchanged. G5 is the next implementation slice.

## G6 S1 — 永続化読み出しの前方互換（2026-08-24）

利用者報告「状況タブが読めない」を実プロセスで再現し、根本原因を特定した。
installed v0.5.1（pid 705506 / :9130）へ実 HTTP を投げた結果:

```text
GET http://127.0.0.1:9130/api/v1/jobs   ->  500  21 bytes
service.log の traceback
  mediaforge/app.py:1092 list_jobs -> store.py:292 list_jobs -> store.py:720 _job
  pydantic ValidationError: 2 errors for JobRequest
    inputs         List should have at most 16 items after validation, not 21
    output.format  Input should be 'png','webp' or 'jpeg', input_value='zip'
```

`Store._job()` が保存済み行を **その時点の `JobRequest` で再検証**していた。
公開契約を加法的に広げた版が書いた行を旧版が読めず、1 行の不整合が
`jobs.list` を**コレクション単位**で落としていた。UI はこの失敗を捕まえて
「状況を読み込めませんでした。」と出すだけなので、状況タブ全体が死ぬ。

実データでの実測。installed の実 DB（`media-forge.sqlite3` 491,520 bytes）を
複製し、v0.5.1 の契約（`inputs<=16` / `format` に `zip` 無し）で読ませた:

```text
実 DB の job 行                              90
v0.5.1 契約で厳格に読めない行                3
  job_bbd62caeea9a47aba49a8f9e2ac112b2
  job_c24d3e60d7514a22bce00d8fb6e6036f
  job_7319eaf22ee34a2d95e54c266ce13509
修正前   この 3 行のうち 1 行目で例外。一覧全体が 500
修正後   提供できた行 90 / 90、degraded 3、失われた行 0
```

修正は「ingress で厳格に検証し、読み出しは寛容にする」。
`StoredJobRequest` は `JobRequest` の部分型で、値の意味は変えず受理範囲だけ広げる。
`Job.request` を `SerializeAsAny` にしたので、新しい版が書いた未知フィールドを
古い版が黙って落とさない（`future_field` が往復することをテストで固定した）。
degraded 行は表示は続けるが実行は fail-closed（`job_record_unreadable`）。

欠陥は job 固有ではなかったため、コレクション読み出し全体を行単位 fail-soft に
した（assets / library page / profiles / reference collections / creative
batches / creative compositions）。

```text
./mf.sh test   363 passed, 1 warning in 36.59s（G5 の 359 + S1 4 件）
```

NOT TESTED: 修正版を実 installed へ入れ替えた状態でのブラウザ操作は未実施。
S2 以降と合わせて 1 度で実機受入する。

## G6 S2 — workspace session と一覧サムネイルの往復削減（2026-08-24）

「GUI が重い」の内訳を実ブラウザで計測した。installed v0.5.1（実データ:
job 90 / asset 95）の workspace を読み取りのみで開き、要求を数えた。

```text
修正前   boot ready 2.609 秒   要求 104 件
           api/v1/assets/{asset}/content   95   一覧カード 1 枚 1 往復
           api/v1/models                    2
           その他（capabilities / profiles / reference-collections /
           assets / creative batches / compositions / index）  7
```

主因は 2 つあった。

1. boot が直列 10 往復で状態を組み立てていた（`preferences.get` から
   `jobs.watch` まで）。状態の正がクライアント側の `state` にあった。
2. 一覧のサムネイルが 1 枚 1 往復だった。埋め込み時は 24 枚 = 24 往復、
   standalone の shim では `limit` を無視して 95 枚の**原寸**を取っていた。

対応は 2 つ。

```text
workspace.session   boot と更新を 1 メソッドへ集約。部分指定で読み直せる
                    部分ごとに fail-soft（Host AI probe が落ちても session は返る）
                    jobs / model operations の watch はサーバが張る
session.changed     変わった部分名だけを push。1 秒 polling 3 本を削除
                    （job / creative batch / creative composition）
                    polling は push の無い standalone にだけ残した
一覧サムネイル      160px WebP をカードに同梱。往復 0
                    原寸と拡大表示は従来どおり個別要求のまま
```

同じ実データでの実測。

```text
修正前   boot ready 2.609 秒 / 要求 104 件
修正後   boot ready 0.264 秒 / 要求  14 件      -89.9% / -86.5%
```

埋め込み時はさらに減る。standalone に残る 13 件は集約 endpoint を持たない
shim がクライアント側で束ねているためで、埋め込みでは `workspace.session`
1 往復になる（サムネイル同梱により追加要求 0）。

サーバ側の集約コストは増えていない。実 DB に対する in-process 実測で
旧 11 メソッドの合計 14.05 ms に対し `workspace.session` は 14.25 ms。

```text
./mf.sh test                368 passed
scripts/ux_standalone_e2e.py PASSED / console errors 0 / phone overflow 0
```

NOT TESTED: installed ControlDeck の埋め込み iframe での実測。S3 以降と
合わせて 1 度で実機受入する。

## G6 S3 — AI と画像生成の resource turn 分割（2026-08-24）

「VLM が VRAM を返さないため画像生成が失敗する」の根本原因を実機設定から特定した。

```text
/data1tb/ControlDeck/data/model-runtime-policy.json
  supervision = "observed"   （"managed" ではない）
-> LlamaCapacityProvider._managed() が False
-> reservations() の yield_level が常に NONE
-> broker は設計上 LLM を降ろさない
実機 LLM   Qwen3.8-27B-UD-Q4_K_M + mmproj-BF16 / ctx_size 262144 / n_gpu_layers 999
実機 GPU   R9700 34,208,743,424 B
```

Media Forge は既に生成 lease を vision 前に解放していた（image -> vision 方向）。
足りないのは逆方向（LLM -> image）で、add-on から「AI ターン終了」を伝える口が
公開契約に存在しなかった。

### ControlDeck 本体 / OpenCode との競合（利用者指摘）

実機の経路を確認した。

```text
integrations/opencode/settings.json
  base_url = http://127.0.0.1:8765/api/v1/llm/v1   use_gateway = true
runtime policy  gateway_only = true
```

OpenCode も ControlDeck chat も同じ gateway を通るため、add-on の `ai/complete`
と同じ `_acquire_gateway_lease` / `_active_requests` に集約される。ControlDeck は
idle unload 用に「使用中なら降ろさない」判定を既に持っている
（`_has_connected_clients` / `_opencode_session_uses` / `idle_exclude` / `role`）。

**新しい判定を作らず**、明示解放はこの判定集合と drain 経路をそのまま再利用した。
30 分の idle unload と同じ決定を、時間ではなく要求で起こすだけにした。

### 変更

```text
ControlDeck（別 PR #238）
  POST /{addon_id}/ai/release   ai.inference を持つ任意の add-on が使える宣言
  /ai/complete + ensure_ready   gateway_chat と同じ on-demand 起動
                                これが無いと解放が次の要求を壊す

Media Forge（本 PR）
  4 ステージ  analyze -> release_ai -> generate -> review
              release_ai は lease を持たずに宣言だけ行う
              先に AI 常駐を落としてから受理を求めるので二重予約も deadlock も無い
  1 回だけ    リトライループを作らない（chat / OpenCode を飢えさせない）
  理由付き    解放拒否 + VRAM 由来の受理失敗のときだけ
              host_ai_residency_retained として拒否理由を添える
              それ以外の受理失敗に AI 常駐の話を混ぜない
  旧 Host     404 は既知状態として扱い、従来どおり broker 受理へ落とす
```

```text
./mf.sh test                            376 passed
ControlDeck backend pytest -q           760 passed, 1 skipped（62.93 秒）
```

`llama.py` の `asyncio` は関数内 import のままにした。module 直下へ移すと
`test_jobs_persistence::test_two_exclusive_resource_jobs_execute_serially` の
broker 受理が `queued` のまま止まることを実測で切り分けた。

NOT TESTED: 実機での「LLM 常駐 -> 解放 -> 画像生成」通し。ControlDeck PR #238 を
入れてから rocm-smi の VRAM 推移込みで 1 度に実測する。

## G6 S4/S5 — 到達性とモデル選択（2026-08-24）

backend の /ws method 48 件と frontend の呼び出しを突き合わせ、実装済みだが
GUI から到達できない機能を洗い出した。

```text
到達できなかった
  profiles.create / profiles.delete            G3 一貫性プロファイル（PR-U6 未着手）
  reference_collections.create / .delete       参照コレクション
  asset.pack                                   G5 M5 companion pack
  creative.prompt_recipe                       H3 版固定 prompt recipe
  assets.list                                  library.list が上位互換
  jobs.unwatch / models.operations.unwatch     内部用。UI 機能ではない
```

### 追加した入口

```text
キャラ・画風の登録   設定画面に作成・削除を追加した
                     参照コレクションは profile と一体で作る
                     （利用者に 2 段階を意識させない）
配布用にまとめる     詳細モードから asset.pack を起動できるようにした
                     スロットは profile の宣言だけを根拠に組む
                     media 固有のスロット名を UI へ書き写さない
使うモデル           おまかせ / 指定する の 2 段。詳細モードで
                     fast / balanced / quality / low_vram / manual へ到達できる
選んだ理由           provenance の parameters.model_route から日本語で出す
```

### 出さなかったもの（理由付き）

```text
creative.prompt_recipe   H3 は experimental / healthy=no / unroutable のまま。
                         完了できない機能を GUI に出さない。
                         H3 の条件が改善したときに同じ PR で出す。
media.inspect            operation としては未実装（G0 から capability_unavailable）。
                         「実装済みだが到達できない」ではないため入口を作らない。
                         agent 用 /addon/v1/agent/inspect は provenance 参照であり、
                         workspace では assets.provenance から既に到達できる。
assets.list              library.list が上位互換。二重の入口を作らない。
```

### domain 対応 routing

catalog は各モデルに `domains` を持っていたのに routing が使っていなかった。
`route()` が domain 一致を policy_rank より前段の候補絞りに使うようにした。
一致 0 件なら全候補へ落とす（シーンを選んだだけで使えるモデルが消えない）。
明示指定は自動判断より強く、domain で上書きしない。

### 実ブラウザでの到達確認（読み取り + 実操作）

```text
model_choice_visible                     true
model_choice_manual_reveals_select       true
profile_add_buttons                      true
profile_dialog_open / character_fields   true / true
pack_hidden_in_simple                    true
pack_visible_in_advanced                 true
pack_profiles                            ["m5.companion.pack"]
pack_slot_rows                           21   （base 1 + eyes 12 + mouth 8）
pack_progress                            "0/21 割り当て済み"
page_errors                              []
```

キャラ登録の往復も実操作で確認した。

```text
character_options_before                 1（「使わない」のみ）
作成後 profile_rows                      1   "オレンジの子"
作成後 character_options                 ["使わない", "オレンジの子"]
削除後 profile_rows                      0
削除後 character_options                 1
page_errors                              []
```

```text
./mf.sh test                 387 passed
ux_standalone_e2e.py         PASSED / console errors 0
boot ready                   0.081 秒 / 要求 15 件（機能追加後も退行なし）
```

NOT TESTED: installed ControlDeck の埋め込み iframe での操作。

## G6 S6 — 利用者が追加する HuggingFace モデル（2026-08-24）

「HuggingFace などからダウンロードできるカタログ機能」への対応。
取得系は既にあった（`worker_packs/image/catalog.json` の revision pin 付き
エントリ、`models.install` の SHA-256 検証・再開・32GB 上限）。不足していたのは
**利用者が任意の HF モデルを足せない**ことだけだった。

### 採用しなかった案

```text
GUI から HF Hub を検索して任意 repo を導入する
  却下。revision 非固定・実測 VRAM 無し・license gate・任意コード実行の risk。
  local-first の検証可能性が壊れる。
```

curated pinned catalog を信頼経路として維持し、明示的な第 2 経路を足した。
信頼経路を検証可能にしている規則は、追加分にもそのまま適用する。

```text
revision 固定   moving ref を取得前に不変 commit へ解決する
digest         配布元が返した sha256 を全 weight に持たせ、既存 installer が検証する
license        表示した名前をそのまま承諾させる（本文の提示が先）
実測 gate      experimental で登録し、routing は選ばない
               models.evaluate の実測に成功して初めて昇格する
parser         追加分も shipped manifest と同じ validator を通す
```

### variant 選択（実測で必要と判明）

実 API に当てて分かったこと。HF の diffusers repository は同じ重みの
Flax / ONNX / OpenVINO 版と、fp32 / fp16 の二重持ちを同居させている。
全部数えると導入上限を超え、代表的な repository がひとつも入らない。

```text
stabilityai/stable-diffusion-xl-base-1.0
  全ファイル      49,952,537,087 バイト   上限 32,000,000,000 を超過
  1 variant 選択   7,105,346,772 バイト   weights 5 個
stabilityai/sdxl-turbo
  全ファイル      42,463,333,800 バイト
  1 variant 選択   6,938,011,430 バイト   weights 4 個
```

shard（`model-00001-of-00002.safetensors`）を variant と取り違えて落とすと
壊れたモデルが届くため、shard は全て残すことをテストで固定した。

### 実 HuggingFace に対する /ws 実測

```text
resolve                0.285 秒
  固定した revision    462165984030d82259a11f4367a4eed129e94a7b（要求は "main"）
  weights / bytes      5 / 7,105,346,772
  license              openrail++
  usable_for_generation false
  warn                 実行アダプタ未実測 / 重複 42,011,397,612 バイトは取り込まない
承諾なしの追加          ok=false  custom_model_license_not_accepted
承諾ありの追加          ok=true
catalog 反映            state=experimental installed=false rev=462165984030
二重追加                ok=false  custom_model_exists
削除                    catalog から除去された
```

### Flux 系と SD 系で個別ローダーが要るか（利用者質問への回答）

要る。ただし「モデルごとに 1 から書く」ではなく**系統ごとの薄い adapter**である。

```text
worker_packs/image/adapters/ が既にその境界
  base.py            ImageAdapter Protocol（generate / edit）
  diffusers_flux2.py FLUX.2 用。pipeline class と参照編集の意味論が固有
  native.py          Diffusers を使えない runtime 用の口（未実装）

SD1.5 / SDXL / SD3 は Diffusers の AutoPipelineForText2Image /
Image2Image / Inpaint で 1 個の共通 adapter に相乗りできる。
新規に要るのは pipeline class の選択、dtype と offload 方針、
inpaint / img2img / reference の引数対応表、negative prompt や scheduler の有無だけ。

別 adapter が要るのは次の場合に限る
  Diffusers に pipeline が無い（stable-diffusion.cpp / GGUF 単一ファイル等）
  参照編集の意味論が固有（FLUX.2 の multi-reference がこれ）
  trust_remote_code を要求する（原則入れない）
```

本 PR では共通 adapter を**実装していない**。実測していない adapter を
available にしないため、追加したモデルは `usable_for_generation=false` として
その理由を明示する。取り込みと検証はできるが生成にはまだ使えない、が現状。

```text
./mf.sh test                 412 passed
ux_standalone_e2e.py         PASSED / console errors 0
実ブラウザ到達確認            page errors 0
```

NOT TESTED: 追加したモデルの実ダウンロードと `models.evaluate` の実測。
共通 adapter が無い状態で実行しても生成の証拠にならないため、別スライスへ送る。

## G6 S3 実機検証 — LLM 常駐 / 解放 / 復帰（2026-08-24）

ControlDeck を `infra/addon-ai-explicit-release` ブランチのまま再起動して実測した。

```text
経路の存在      POST /api/v1/addon-runtime/media-forge/ai/release
                無効 token -> 401（404 ではない = 配線済み）
runtime policy  llama.cpp / supervision=observed / gateway_only=true / yield_max=4
対象            Qwen3.8-27B-UD-Q4_K_M + mmproj-BF16 / ctx 262144 / n_gpu_layers 999
GPU             R9700 34,208,743,424 バイト
```

### ❷ の根本原因が数値で確定した

```text
LLM 常駐時の VRAM   59,912,192 -> 31,555,141,632（+31,495,229,440）
```

**34.2GB の GPU のうち 31.5GB を LLM が占有する。** FLUX.2 Klein 4B の
実行 peak は 29,625,200,640 バイトなので、常駐したままでは絶対に入らない。
`supervision=observed` では broker が降ろさないため、待っても解消しない。

### 解放の実測

```text
実行中の要求がある間   released=False reason=drain_timeout（120.058 秒待って拒否）
使用が終わったあと     released=True  reason=released  0.737 秒
                       VRAM 31,555,141,632 -> 59,912,192（全量返却）
推論を 1 回通した直後  released=True  reason=released  2.380 秒
```

### ❽ OpenCode 経由の生成（利用者指摘 2026-08-24）

**最初の設計では成立しなかった。** 実測で判明した。

```text
integrations/opencode/settings.json  base_url = .../api/v1/llm/v1  use_gateway = true
resolve_backend_port()               8096（LLM の実ポートと一致する）
-> _opencode_session_uses は活動中の OpenCode セッションに True を返し続ける
-> 解放は常に opencode_active で拒否される
-> OpenCode から add-on へ生成を頼む経路が、この機能が必要な場面でだけ死ぬ
```

明示解放が idle unload の 30 分窓を引き継いでいたのが誤りだった。idle loop が
「最近誰か触ったか」を見るのは**誰も要求していない**からで、その場合は暖めた
まま保つのが安全側になる。明示解放は逆で、**要求した側が今その VRAM を必要と
している**。実行中の推論を切らない保証は drain 側が持ち、降ろしたものは
`ensure_ready` で自動復帰する。

修正後、OpenCode セッションが活動中に見える状態を再現して測り直した。

```text
load              4.040 秒   VRAM 59,912,192 -> 31,555,141,632
旧判定            _opencode_session_uses = True   （これを見ていたら解放できない）
新判定            release_reason = ""             （解放可）
解放要求          released=True reason=released 0.356 秒
                  VRAM 31,555,141,632 -> 59,912,192（-31,495,229,440 全量返却）
次の turn の復帰   ok=True 5.836 秒（ensure_ready による自動復帰）
後片付け          VRAM 59,912,192（測定前と同じ）
```

残る保証は変えていない。

```text
実行中の推論を切らない      drain（実測 drain_timeout で拒否）
streaming 中は降ろさない    _has_connected_clients
運用者の明示除外            idle_exclude
embedding / reranker        role で対象外
```

`freed_bytes` は降ろしたモデルファイルの大きさである。実際に空く VRAM は
KV cache を含むため大きい（16,464,440,224 に対し 31,495,229,440）。

```text
ControlDeck backend pytest -q   764 passed, 1 skipped（57.66 秒）
```

NOT TESTED: Media Forge 側を実 add-on として動かした「analyze -> release_ai ->
generate」の通し。installed feature は v0.5.1（旧 core）のままであり、
本 PR の core を bundle 化して入れ替えるまで実行しない。

## G6 v0.6.0 バンドル導入と installed 実測（2026-08-24）

```text
bundle   ./mf.sh bundle build 0.6.0 /data1tb/mediaforge-release-bundles
artifact control-deck-media-forge-0.6.0-linux-x86_64.tar.gz
bytes    30,640,703
sha256   ef57f26f78bb5816f967c9256dfce07ae9a135d64602f4137f09004b9bfed73d
```

展開したバンドルを :9137 で起動し、配信 HTML が新 UI であることを確認した。

```text
model-choice 14 / pack-section 2 / custom-repo 2 / profile-add-character 2
workspace.session 4 / session.changed 4
ux_standalone_e2e.py   PASSED / console errors 0
到達確認                pack_slot_rows 21 / page errors 0
```

installed feature を v0.5.1 から v0.6.0 へ入れ替えた（systemd drop-in で
`versions/0.6.0` を指す。`current` symlink も更新）。

### ❸ が installed で解消した

```text
修正前   GET http://127.0.0.1:9130/api/v1/jobs -> 500（1 行の不整合で全件喪失）
修正後   GET http://127.0.0.1:9130/api/v1/jobs -> 200  90 件  degraded 0
         /api/v1/assets -> 200   /api/v1/capabilities -> 200
```

degraded 0 なのは v0.6.0 の契約が当該行を厳格に読めるため。旧契約で読めない
行が来ても一覧は落ちないことは `tests/test_store.py` と実 DB 90 行での
before/after 実測（v0.5.1 契約で 3 行が読めず、修正後は 90/90 提供）で固定した。

### 残る未実測と再現手順

Media Forge 側の「analyze -> release_ai -> generate」通しは、ControlDeck への
ログインが要るため未実施。**利用者のパスワードは扱わない**方針のため、
そのまま実行できる受け入れスクリプトを用意した。

```bash
MEDIA_FORGE_E2E_PASSWORD=... \
  /data1tb/ControlDeck-release-bundle/.venv/bin/python \
  scripts/g6_resource_turn_e2e.py \
    --control-deck-url http://127.0.0.1:8765 \
    --username <name> \
    --evidence-dir /data1tb/mediaforge-g6-evidence
```

このスクリプトが検証すること。

```text
1. boot が workspace.session 1 往復で終わること（WebSocket frame を数える）
2. 状況タブが記録を読めること（degraded 行があっても落ちない）
3. Host LLM を gateway 経由で常駐させ、実際に VRAM を握らせること
4. 実画像 job の phase 列に release_ai が現れ、generating より前にあること
5. VRAM が生成前に返っていること / 実画像が 1 枚できること
6. Broker が空で残り、worker プロセスが残らないこと
```

VRAM は rocm-smi の実測値を phase ごとに記録する。モデル自身の申告ではなく
デバイスを読む。


## G6 resource turn E2E スクリプトの事前検証（2026-08-24）

利用者に実行してもらう前に、ログイン不要で検証できる部分を実プロセスに当てて直した。

```text
framesent の payload      dict ではなく Union[bytes, str] を直接渡す仕様だった。
                          dict 前提のままだと全フレームが空になり、
                          「boot が 1 往復」の判定が常に偽で落ちていた。
                          binary / 非 JSON / method 無しフレームも来るため
                          数えられないものは捨てる形に直し、単体で確認した。
broker snapshot の経路    /api/v1/resources/snapshot は 404。正しくは
                          /api/v1/resources（未認証で 401 = 経路は存在する）。
login helper              ci6_r9700_e2e.py の実績あるものをそのまま再利用した。
                          ControlDeck の login は SPA なので HTML からは確認できない。
```

boot 判定は「`workspace.session` がちょうど 1 回」に加えて、
旧 boot が個別に投げていた 10 メソッドが 1 つも復活していないことも見るようにした。

## G6 resource turn の物理受け入れ（2026-08-24）

利用者から login アカウント作成の承認が出たが、**アカウント作成とパスワード入力は
実施しない**方針を維持した。代わりに、認証境界だけを stub にして物理現象は
すべて実物で測る受け入れを作った（`scripts/g6_resource_turn_physical_e2e.py`）。

```text
実物        常駐 LLM / それが握る VRAM / 実際の解放 / FLUX worker / 生成 PNG
stub        ControlDeck の token・lease の HTTP 面だけ
            ただし ai/release は ControlDeck 自身のコードで本物の unload を行う
別途実測済  Host 側の解放可否判断（G6 S3。実 ControlDeck に対して実測）
```

### 結果

```text
LLM 常駐            VRAM 59,912,192 -> 31,555,141,632   load 8.038 秒
解放                released=true reason=released       0.146 秒
解放後の VRAM        59,912,192（全量返却）
生成                 succeeded / asset 1 枚 / 17.706 秒
  model_id           black-forest-labs/FLUX.2-klein-4B
  runtime_adapter    diffusers.flux2-klein
  weights_hash       sha256:f3fcfa8f…dfae278（manifest と一致）
  output             256x256 PNG / 114,310 bytes
  model_route        policy=auto domain=general domain_matched=true candidate_count=1
worker placement     device_mode=direct_device_map
                     component_devices すべて cuda:0
                     offload_hooks=[] non_gpu_devices={} non_gpu_map_targets=[]
worker timing        load 10.640 秒 / generation 1.074 秒
解放後の VRAM ピーク   18,147,024,896（51 サンプル / 0.25 秒間隔）
後片付け             VRAM 59,912,192 / loaded instance 0
```

順序は log でも確認した。

```text
POST .../ai/release        200
uvicorn.error              ai turn released ... released=True reason=released
POST .../resources/requests 202
POST .../resources/leases/lease-request-1/activate 200
image worker timing / placement
```

**AI ターンの終了宣言が、生成 lease の要求より前**にある。設計どおり。

### ❷ が物理的に確定した

```text
LLM 常駐          31,555,141,632 バイト
FLUX 実占有        18,147,024,896 バイト（解放後の実測ピーク）
合計              49,702,166,528 バイト
GPU 総容量         34,208,743,424 バイト
```

**合計が GPU 容量を 15.5GB 超える。** 常駐したままでは物理的に共存できない。
`supervision=observed` では broker が降ろさないため、待っても解消しない。

### 測定側の誤りを 2 回直した（緑を鵜呑みにしない）

```text
1 回目   phase 境界でだけ VRAM を読んでいた。generating に入るのは worker が
         確保する前なので idle を拾い、「GPU を使っていない」ように見えた。
2 回目   ジョブ全区間のピークで見ていた。常駐 LLM の 31.5GB に支配されるため、
         画像 worker が GPU を 1 バイトも使わなくても必ず通る判定だった。
3 回目   サンプルに時刻を持たせ、解放より後の区間だけでピークを取るようにした。
         これで初めて 18,147,024,896 バイトという画像 worker の実占有が出た。
```

worker の placement log は worker 自身の申告なので、rocm-smi の実測と揃えて
初めて証拠として扱う。両方を assertion に入れた。

### CPU オフロードについて（利用者指示 2026-08-24）

許容の指示を受けたが、**今回は不要だった**。`direct_device_map` のまま
`offload_hooks=[]` で完走している。

catalog の `measured_vram_bytes` は 33,349,320,704 で、今回の実占有
18,147,024,896 の約 1.84 倍を申告している。これは最大解像度側の envelope で
あり誤りとは限らないが、broker へ GPU のほぼ全量を予約させる値ではある。
`device_mode: cpu_offload` は registry が既に受理する値なので、より大きな
モデルを載せる際の選択肢として使える。ただし wall time / RAM headroom /
swap / Host watchdog を実測するまで available へ昇格させない（H3 と同じ gate）。

## G6 resource turn E2E のログイン失敗を診断可能にした（2026-08-24）

利用者が実行したところ 20 秒の Playwright TimeoutError で止まった。原因は
監査ログで確定した。

```text
SELECT timestamp, action, username, result FROM audit_logs WHERE action LIKE 'login%'
2026-08-24 02:46:42  login  user='mfe2e'  result='failure'
```

**パスワード違い**であって TOTP でも rate limit でもスクリプトの不具合でもなかった。
この環境の TOTP は `totp_requirement=optional` / `require_totp_for_admin=False`
なので、そもそも二要素は要求されない。

問題は、原因が違っても症状が同じになっていたこと。URL の遷移だけを待つと
パスワード違い・rate limit・二要素要求のどれもが同じ 20 秒 timeout と
40 行のトレースバックになり、利用者が原因を知る手段が無かった。

`/auth/login` の応答を直接見て、サーバが実際に言ったことを返すようにした。

```text
401 + detail                  -> ユーザー名とパスワードの確認を促し、
                                 ./deck.sh passwd <user> を案内する
401 + two_factor_required     -> TOTP が有効である旨と reset-totp を案内する
429                           -> 5 回/分・20 回/分の制限と待ち時間を案内する
200 だが遷移しない            -> 現在の URL を出す
```

実測（誤ったパスワードで意図的に失敗させた）:

```text
FAILED: ログインに失敗しました（HTTP 401: ユーザー名またはパスワードが正しくありません）。
        ユーザー名 mfe2e とパスワードを確認してください。
        パスワードを設定し直すには ./deck.sh passwd <user> を使います。
```

40 行のトレースバック / 20 秒 -> 1 行 / 6 秒。

なお、この環境には既に `mf-e2e`（ハイフン入り）という E2E 用アカウントがあり、
2026-08-23 の CI-6 実行で繰り返し成功している。新規作成は不要だった。

## G4H A1 — AssetBrief と決定的な出力幾何（2026-08-24）

実使用（OpenCode の Hanabi プロジェクト）で報告された「wide landscape と要求
したのに 1024x1024 が生成された」を、実物と記録から追って直した。

### 実物で確認した欠陥

```text
/data1tb/ControlDeck/CodeDEV/Hanabi/assets/keyart/
  background-keyart.png   1024x1024  RGBA  1,296,977 bytes
  fireworks-keyart.png    1024x1024  RGBA  1,977,542 bytes
```

provenance を追うと、要求は次の形だった。

```text
constraints    {}            <- 寸法がひとつも渡されていない
model_policy   quality       <- agent が方針まで選んでいる
intent         "... wide landscape composition ..."  <- 散文の中だけ
validation     image.dimensions passed (1024x1024)   <- 寸法の存在は見るが用途は見ない
```

生成側の既定は `worker_packs/image/worker.py` の
`width_default = 1024` で、**stack の最下層**にある。ここは用途を知らない。

消費側の実害も確認した。

```text
index.html   #title-bg   object-fit: cover
-> 正方形を横長の面へ cover するため上下が切られる
-> 「上 2/3 の空を開ける」「下端に観客のシルエット」という指示どおりに
   構図された部分が、まさに切り落とされる
```

もう 1 件、報告に無かった欠陥を実物から見つけた。

```text
fireworks-keyart.png は #title-fw として背景の上に 300px で重ねられている
alpha min=255 max=255  半透明以下の画素 0/1,048,576 (0.00%)
-> 透過が要件のはずの重ね要素が、独自の夜空と観客を持つ不透明な完成シーン
-> 背景と内容が重複し、drop-shadow は花火ではなく四角い箱の縁に付く
```

### 対応

用途から幾何を**生成前に決定的に**解決する層を入れた（`asset_brief.py`）。

```text
AssetBrief          role / aspect_intent / target_dimensions / safe_areas /
                    alpha_intent / consistency_group / hard_constraints
                    provider・model・sampler・prompt の欄を持たない
resolve_layout      優先順位は
                      request の明示寸法
                      > brief の明示寸法
                      > brief の aspect 指定
                      > role 既定
                      > 従来どおり（何も推論しない）
                    envelope（multiple_of / min / max / max_pixels）へ必ず収める
infer_brief_from_intent
                    既存の散文から構造語だけを決定的に拾う。AI 呼び出し 0 回。
                    確信が持てなければ何も推論せず従来の挙動を変えない。
```

公開契約は変えていない。brief は既に自由形の `JobRequest.constraints` に載る。

### 実測（当時と同じ形で再実行）

```text
background    1024x576  16:9  source=brief.aspect_intent   （当時 1024x1024）
fireworks     1024x576  16:9  source=role_default          （当時 1024x1024）
明示 1024x1024 1024x1024       source=request.constraints   （推論は明示を上書きしない）
AI 呼び出し    0 回
```

### AI Director を要求変換に挟む案（利用者提案 2026-08-24）

**採用しない。** 実測に基づく理由を `g4-agent-asset-workflow-hardening.md` §3.2b
へ記録した。LLM 31.5GB と FLUX 18.1GB は 34.2GB の GPU で共存できず、AI を
挟むたびにモデルのスワップが要る。実測でスワップ 1 往復は 15〜25 秒
（LLM load 4.0〜12.1 秒 / release 0.146〜0.371 秒 / FLUX load 10.6〜14.9 秒）。
全生成の前段に置くとこれを毎回払う。Director は既に `text.generate` を持って
おり、二つ目の AI 層にもなる。

決定的抽出で報告された欠陥は解消したため、Director への相乗り（tier 2）は
A3 へ送り、本スライスでは実装しない。

```text
./mf.sh test   451 passed（従来 412 + A1 39）
```

NOT TESTED: 解決後の寸法での実画像生成、および透過が必要な emblem 用途の
実生成。A3 / A5 で実機確認する。

## G4H A1b — defect と finding の分離（2026-08-24）

利用者の指摘「予算を制限する場合、必要な生成が行われない可能性はないか」への
対応。あり得るため、規則を明示して実体化した。

```text
予算は「任意の改善」を縛る
予算は「必要な修正」を縛らない
予算切れは報告する。黙って成功にしない
```

二つの階層を型で分けた。

```text
BriefDefect   用途に対して客観的に誤っている
              canvas 不一致 / 必須 alpha の欠落 / 想定外の透過
              -> 予算に関係なく修正するか、理由を名指しで失敗する
finding       評価器の主観的な判断（A3 で実装）
              -> QA 予算で縛る。予算切れは未解決事項を添えて返す
```

最良の守りは検査ではなく予防である。A1 で canvas を構造的に解決したため、
寸法不一致は「検出して作り直す」対象ではなくなった。予防は swap 0 回、
作り直しは 1 往復まるごと（実測 15〜25 秒）。

### validator の主張を正直にした

`validate_png` は `{"validator": "image.alpha", "alpha": true}` を返していたが、
これは「mode が RGBA である」という意味でしかなかった。Hanabi の花火キーアートは
完全不透明のままこの検査を通過していた。実際の最小 alpha を見るようにした。

```text
before  {"validator": "image.alpha", "status": "passed", "alpha": true}
after   {"validator": "image.alpha", "status": "passed",
         "mode_has_alpha_channel": true, "has_transparency": false, "minimum_alpha": 255}
```

### 実物での検出確認

```text
background-keyart.png  実物 1024x1024 透過=False  要求 1024x576
  DEFECT canvas_mismatch  expected=1024x576  actual=1024x1024
fireworks-keyart.png   実物 1024x1024 透過=False  要求 透過必須
  DEFECT alpha_missing    expected=alpha channel with transparent regions  actual=fully opaque
```

alpha は required / forbidden / auto の三状態を保つ。bool へ潰すと「不要」と
「禁止」が混ざり、片方が誤って defect になる。

```text
./mf.sh test   458 passed
```

NOT TESTED: defect 検出後の自動再生成（A3 の範囲。現時点では理由を名指しして失敗する）。

## G4H — 資産生成の手順設計（2026-08-24）

利用者提案「画像以外を全部実装してから資産をまとめて生成し、VLM で確認して
コード修正か再生成をまとめる。逆も」を評価し、`g4-agent-asset-workflow-hardening.md`
§6.8 に決定を記録した。

```text
採用    コード先行。Hanabi では必要な事実が既に CSS にあった
          #title-bg object-fit: cover        -> 面は横長。正方形は切られる
          #title-fw width: min(52vw, 300px)  -> 小さな重ね要素であって完成シーンではない
                    filter: drop-shadow(...) -> 形のある被写体を期待する = 透過が要る
        brief を「推測」から「実測」に変えられる

不採用  検査前に全部まとめて生成する形。画風が外れると N 枚無駄になる
        代わりに anchor 1 枚を先に作って確認する。同じ FLUX 常駐の中で
        行うので追加 swap は 0

不採用  資産を先に作ってからコードを書く順序
        brief が測る対象を持たず、形容詞へ退行する。Hanabi の失敗の再現になる

採用    「画像ではなくコードを直す」判断はしばしば正しく、再生成より安い
        ただし Media Forge は project source を書き換えない。不一致と
        どちら側で解決できるかを報告し、決めて直すのは coding agent
```

結果として swap は資産数によらず 2 回のまま。

## G4H A1c/A2 — 複数枚生成と agent への指針（2026-08-24）

### 複数枚生成での defect の扱い（利用者指摘）

「生成枚数は 1 枚だけじゃない場合も適用しているか」という指摘で、扱いの誤りを
見つけた。`_validate_output` は候補ごとに走るが、最初の defect で全体を失敗させて
いた。4 枚頼まれて 1 枚の alpha が欠けただけで、良い 3 枚まで捨てることになる。

```text
修正前   候補 1 枚の defect -> job 全体が失敗
修正後   defect のある候補だけを落とす
         残りが 0 なら理由を名指しで失敗する（黙って返さない）
         落とした事実は warnings に残す
```

幾何は job 単位で 1 度だけ解決されるので、`output.count` が何枚でも全候補が
同じ面に収まる（テストで固定）。

### A2 — agent へ届く指針

指針が確実に届く経路は **JSON Schema の `description`** である。どの agent
harness でも提示されるため、OpenCode 専用の分岐を作らずに済む。
`addon.json` の contribution 形は変えていない。

`schemas/job-request.json` へ加法的に追記した。

```text
top level          用途を伝える。provider 向けの prompt を書かない。model を名指さない
intent             構造要件は asset_brief へ。実使用で "wide landscape" が
                   この欄にしか無く、正方形が返った事実を明記
constraints        明示 width/height は常に推論に勝つ
constraints.asset_brief   role / aspect / safe_areas / alpha / consistency_group
                          role ごとの既定（emblem・sprite は alpha 必須、
                          background は横長・不透明）を説明文に書いた
model_policy       auto のままにする。quality / low_vram は必要なときだけ
qa                 既定のまま。semantic=true は model swap を伴う。
                   予算は主観的な再試行だけを縛り、brief への客観的な不一致は
                   予算に関係なく修正または報告される
examples           Hanabi の 2 資産（背景と emblem）を正しい形で載せた
```

`schemas/project-asset-placement.json` へは grant のタイミングを書いた。

```text
grant は配置の直前に取る。生成の前に取らない（生成は数十秒かかり期限切れになる）
期限切れなら新しい grant を取り直して 1 度だけ再試行する
Media Forge は path を受け取らない
```

例が古びて嘘になるのを防ぐため、schema の `examples` が自分自身の schema を
通ること、かつ実サービスが 202 で受理することをテストで固定した。

```text
./mf.sh test   468 passed
```

NOT TESTED: 実 agent harness（OpenCode / Codex）がこの description を提示して
実際に purpose-level 要求を出すか。A5 の実機 E2E で確認する。

## G4H A3 — 用途に応じた評価（2026-08-24）

Hanabi の背景は単体では美しく、実際に prompt どおりに構図されていた。使えな
かったのは面の比が違ったからで、それは主観の問題ではない。「良い画像か」と
訊いていたら yes と答えていたはずである。

評価を「綺麗か」から「その用途に使えるか」へ変えた。既存の Unified Evaluator と
canonical `EvaluationResult` をそのまま使い、別系統は作っていない。

```text
brief_dimensions   用途が要求する観点だけを選ぶ
                     background          composition / palette
                     character_portrait  subject_identity / composition
                     sprite              subject_identity
                     texture             style
                     safe_areas あり     composition を追加
                     general             追加なし
brief_rubric       その用途で「使える」とは何かを評価器へ渡す
                     background  上に描かれる。UI や文字の背後で読めるか。
                                 支えるのではなく主張しすぎていないか
                     emblem      独立した紋章として読めるか。背景と重複する
                                 完成シーンになっていないか
                     safe_areas  「上 40% は title and menu のために空けること。
                                 被写体が侵入していないか報告せよ」
                     hard        「no text in the image」等をそのまま渡す
```

寸法・alpha・形式は決定的に解決済みなので、評価器には
「canvas は 1024x576 (16:9) で確定済み。寸法や形式について述べるな」と明示する。
VLM に蒸し返させない。

brief を渡さない既存の呼び出しでは観点の選び方が一切変わらないことをテストで
固定した。

### 予算切れの扱いを実装に合わせて訂正した

計画 §6.7 に「予算切れは最良候補を返す」と書いていたが、実装は
`semantic_review_exhausted` で job を失敗させる。確認した結果、実装の側が
正しい。`qa.semantic=true` と retry 予算は、呼び出し側が「不適合なら拒否せよ」と
明示的に頼んでいる状態であり、拒否された候補を黙って返せばそのゲートを
無意味にする。§6.7 の要件は「隠さないこと」であって「成功させること」ではない。

既知の代償として記録した: 決定的には妥当な候補も job ごと捨てられるため、
実 GPU 仕事が主観的判断で失われる。失敗した job が資産を持つ形は public な
意味を変えるため、A3 には畳み込まない。

defect の判定が QA 予算をまったく参照しないことも、経路の形でテストに固定した。
参照させた瞬間に、予算を使い切った job が誤った資産を成功として返せるようになる。

```text
./mf.sh test   486 passed
```

NOT TESTED: 実 VLM がこの rubric で用途不一致を実際に指摘するか。A5 の実機
E2E で、Hanabi 相当の資産に対して確認する。

## G4H A4 — 配置マニフェストと受領書（2026-08-24）

実使用では、関連する資産を 1 個ずつ `media.pack` へ渡していた。呼び出し側から
見ると何が配置されたのか応答から確定できず、最後に shell の `ls` / `file` で
確かめる必要があった。応答が受領書として不足していたためである。

### 受領書

単体形の応答へ加法的に `receipt` を足した。既存の呼び出し側が読んでいる欄
（`asset_id` / `media_asset_id` / `name` / `mime_type` / `size` / `sha256`）は
そのまま残る。

```text
PlacementReceipt
  committed / source_asset_id / host_asset_id / filename / media_type
  sha256 / size_bytes / width / height / role / warnings / error
```

project の path は入れない。呼び出し側が知るのは「どのバイト列がどの名前で
置かれたか」だけで、project がどこにあるかは知らない。

### 複数件配置

`items[]` 形を追加した。単体形はそのまま維持し、応答の形も呼ばれた形に揃える。

```text
preflight   1 バイトも書く前に全件の宛先名を確定させる
            重複名 / 欠落資産 / 拡張子と MIME の不一致はここで拒否し、
            何も commit しない
書き込み     1 件ずつ commit する。失敗したらそこで止め、残りは
            not_attempted として報告する
応答        committed_count / requested_count / partial / atomic:false
```

**`atomic: false` を明示する。** ControlDeck が原子的に扱えるのは 1 ファイルで
あり、N 件をまとめて「全部か無か」と名乗ると、部分的に書かれた状態を呼び出し側が
見落とす。Host に汎用 transaction primitive が入るまでこの表現は変えない
（計画 §8.3 / H3）。

### 実測

```text
3 件一括           committed_count 3 / partial false / 各 receipt の
                   sha256・size・width・height が元資産と一致
重複名             422 duplicate_placement_filename / outputs 0 件
                   （大文字小文字を畳んで比較する）
欠落資産           404 asset_not_found / outputs 0 件
同一資産の二重指定  422 invalid_project_asset_placement
受領書の path 漏れ  なし
./mf.sh test       492 passed
```

NOT TESTED: 途中失敗して `partial: true` になる経路。stub host が commit を
失敗させないため、実機 E2E（A5）で確認する。

## UX3 — シーン/見せ方カタログの汎用化と設定の重複解消（2026-08-24）

### カタログがキャラクター中心だった

利用者指摘「シーンと構図が一般的ではない」。実際、全項目が「人物が何をしているか」
だった。Hanabi のような背景・風景・物・抽象の依頼を表す手段が無く、実使用でも
散文へ逃げていた。

```text
                旧    新
domains          7 ->  16   水彩 / 油彩 / フラット / ドット絵 / 線画 / 3D /
                            コンセプトアート / 浮世絵 / 背景 を追加
scenes           8 ->  34   場所・時間帯・天候を追加（自然 / 街 / 室内 / 夜空 /
                            水辺 / 朝焼け / 夕暮れ / 雨 / 雪 / 霧 / 森 / 山 /
                            砂漠 / 宇宙 / 水中 / 廃墟 / カフェ / 教室 /
                            ファンタジー / SF 都市 / 祭り など）
compositions     8 ->  27   汎用レイアウトを追加（中央 / 三分割 / 左右対称 /
                            上下横の余白 / 広く見渡す / 寄り / 真上から /
                            継ぎ目なし / 斜め / 誘導線 / 額縁 / シルエット /
                            奥行き / パノラマ / アイソメ / 見下ろし / 横スクロール）
cameras          7 ->  16   俯瞰 / 接写 / 遠景 / 傾け / あおり / 望遠圧縮 /
                            広角 / 背景ぼけ / 全面ピント
variations       6 ->   9   配色違い / 光の違い / アングル違い
```

人物を必要としない場面は `compatible_poses` を `auto` だけにして、関係のない
ポーズ選択を出さない。既存 ID は 1 つも削除していない（`poster` /
`character_sheet` は composer が参照している）。

`registry._DOMAINS` に `background` があるのに選ぶ手段が無かったので追加した。

### 詳細モードで同じ設定が 2 箇所に出ていた

利用者指摘「シーンと見せ方と詳細設定で設定内容がかぶる」。実際に重複していた。

```text
簡易 #creative-simple        ドメイン / シーン / ポーズ / 構図 / カメラ / 変化
詳細 #advanced-create        ドメイン / シーン / ポーズ / 構図 / カメラ / 変化
                             （同じ 6 つが再掲され、同じ state を書いていた）
```

同じ設定が 2 箇所にあると、どちらが効いているのか利用者に分からない。

```text
整理後
  選択      「シーンと見せ方」に 1 組だけ置く
  詳細モード 同じ選択を繰り返さず、言葉での補足だけを足す
             （シーン / ポーズ / 構図 / カメラ の詳細 4 欄）
             幅・高さ・出力形式・枚数・モデル方針・参照の役割・QA は従来どおり詳細のみ
```

### 生成画像の書き出し

設計 §F4 保存A で仕様が決まっていて host files bridge も実装済みだったが、
**UI から呼ぶ導線が 1 つも無かった**（`design-workspace-ux.md` §25 が既に指摘済み）。

`assets.export` を実装し、ビューアに「保存」を足した。応答は配置と同じ
`PlacementReceipt` 形で返し、保存したものを `ls` で確かめ直さずに済むようにした。
単体表示ではホストがいないため、その旨を明示して失敗させる（できないことを
できるように見せない）。

### 実測（実ブラウザ）

```text
simple_scene_options        34
simple_composition_options  27
simple_camera_options       16
domain_chips                16
詳細モードでの select 重複    0（旧 advanced-* の 6 つは削除済み）
詳細モードの補足入力          4
page_errors                 []
./mf.sh test                499 passed
```

NOT TESTED: 実 ControlDeck 上での `assets.export` の往復（host bridge の
`host.files.export` 応答形を実機で確認していない）。実機受入で確認する。

## UX3b — シェルの刷新と、実機で見つかった 3 件の不具合（2026-08-24）

利用者が実機（モバイル埋め込み）の画面を提示。表示の問題より先に、動作の
不具合が 2 件見つかった。

### 1. 前回の解析結果が新しい指示の生成に渡っていた

画面では指示が「宇宙戦艦…」なのに「理解した内容」は前回の「ライオンさん」の
ままだった。表示だけの問題ではない。`state.directorPlan` は送信時に
`director_plan` としてそのまま渡るため、**前の解析が別の生成に効いていた**。

`director-mode` の変更時には捨てていたが、指示文の変更時に捨てていなかった。
指示を書き換えたら解析結果ごと捨てるようにした。

### 2. 進捗が 5% から完了へ飛ぶ

backend の phase と progress を追うと原因は明白だった。

```text
generating   0.05
  （ここに GPU の生成全体が入る。実測 load 10.6-14.9 秒 + 生成 1.1-2.2 秒、
    大きい面では最大 208 秒）
postprocess  0.65
```

割合は本当に分からない区間である。嘘の数字を動かす代わりに、
`generating` / `waiting_resource` / `release_ai` は不確定表示にし、
経過時間と実測由来の目安を出すようにした。`prefers-reduced-motion` では
ループさせない。

### 3. タブを移って戻ると進捗が消える

`showProgress` は届いたイベントでしか描かれず、状態から作り直す経路が無かった。
`job.changed` で受け取った最新状態を `state.jobs` に保ち、作る画面へ戻ったとき
`restoreProgressView()` で描き直す。

### シェルの見た目

```text
ナビ      文字だけのタブ -> 線画アイコン + ラベル。現在地は上側の細い印
          （ホストのタブバーと縦に並ぶため、下線だと読みにくい）
設定      絵文字の歯車 -> 線画アイコン。現在地を示すようにした
アイコン  SVG を直接埋め込む。opaque sandbox では外部資産を取りに行けず
          CSP でも止まる。currentColor で塗るので theme.changed に追随する
```

```text
./mf.sh test   515 passed
実ブラウザ      430x860 で描画確認、page errors 0
```

NOT TESTED: 実 ControlDeck 埋め込みでの見え方（ホストのタブバーとの重なり）。

## SD 系共通 adapter と、配布元の検索カタログ（2026-08-24）

### 系統ごとの薄い adapter（利用者質問への実装での回答）

「Flux 系と Stable Diffusion 系で個別のローダー開発が必要か」への回答を実装で示した。
**要るが、モデルごとに 1 から書くのではなく系統ごとの薄い adapter である。**

```text
worker_packs/image/adapters/
  base.py            ImageAdapter Protocol（generate / edit）
  diffusers_flux2.py FLUX.2 用。pipeline class と参照編集の意味論が固有
  diffusers_sd.py    SD 1.5 / SDXL / SD 3 共通（新規）
  native.py          Diffusers を使えない runtime 用の口（未実装）
```

SD 系が 1 個で足りるのは、Diffusers の `AutoPipelineForText2Image` が
pipeline class の解決を既に引き受けているためである。実際に系統固有なのは
次の 4 点だけだった。

```text
どの pipeline class を作るか        AutoPipeline が config から解決する
この機材での dtype と offload 方針   SD 系は fp16。bf16 の FLUX とは別
generate / img2img / inpaint の対応  1 つの Protocol へ寄せる
negative prompt と guidance          FLUX.2 Klein は取らない
```

worker は `runtime_adapter` の名前で adapter を選ぶ。表は module 属性名を持ち、
import 時にクラスを固めない（固めると試験が差し替えた偽 adapter が使われない）。

`trust_remote_code` は明示的に `False` にしている。取り込んだ重みが任意の
コードを持ち込める経路を開かない。

`edit` は実装せず `NotImplementedError` で落とす。strict inpaint には
protected-pixel 保証、outpaint には別の不変条件があり、実測していない経路が
それらを名乗るのは、無いことより悪い。

**実測していないため、この adapter を使う catalog エントリは `experimental` の
ままである。** 実機での測定は別スライス。

### 配布元の検索

repository ID の手入力だけでは、名前を既に知っている人にしか使えなかった。
検索を足した。

```text
models.custom.search
  query / sort / pipeline_tag / limit
  sort は downloads / likes / lastModified / createdAt
  未知の並び順は黙って別の順で返さず拒否する
    （黙って返すと、並べ替えたつもりのまま誤った表を読むことになる）
  library=diffusers と使える pipeline に限って問い合わせる
    （取り込めない形式ばかり並べても選べない）
  壊れた要素は飛ばし、検索全体を失敗させない
  導入済みは already_added として印を付ける
```

UI は表で出す。数値は等幅で縦に揃える（桁が揃わない表は比較に使えない）。
**表から直接は取り込まない。** 「中身を見る」は既存の resolve へ渡し、
版の固定・digest・ライセンス明示承諾を必ず通る。

実 API 実測（`stable diffusion` で検索）:

```text
sort=downloads    1,605,410 DL  stabilityai/stable-diffusion-xl-base-1.0
                  1,440,259 DL  stable-diffusion-v1-5/stable-diffusion-v1-5
sort=likes        8,068 ★      stabilityai/stable-diffusion-xl-base-1.0
                  7,054 ★      CompVis/stable-diffusion-v1-4
sort=lastModified 2026-08-24    pruna-test/test-save-tiny-stable-diffusion-pipe-smashed
```

```text
./mf.sh test   529 passed
実ブラウザ      表 3 行を描画、page errors 0
```

NOT TESTED: SD adapter による実生成。実機測定まで `experimental` を維持する。
LoRA は利用者指示どおり後続の計画とする。

## UX4 — 導入済みモデルを見比べられる表（2026-08-24）

モデル管理はカードだけだった。カードは 1 件ずつの説明には向くが、容量・状態・
VRAM を縦に揃えられないため、「どれを消すか」「どれが使えるか」を決める用途に
使えない。検索結果と同じ表の言葉づかいに揃えた。

```text
列        モデル / 状態 / 採用 / 容量 / VRAM / ライセンス / 操作
既定       表（見比べる用途が多い）。カードは切り替えで残す
数値       等幅で縦に揃える
操作       表とカードで同じ（ダウンロード / 削除 / 実機で評価 / 中止）
保持       model_layout として preferences に置く。ブラウザ保存領域は使わない
```

実ブラウザ実測:

```text
layout chips     ['表', 'カード']
既定             table 表示 / cards 非表示
行数             13（同梱カタログ全件）
切り替え後        table 非表示 / cards 表示
page errors      []
```

FLUX.2 Klein 4B が「導入済み / available / 約 14.9 GB / VRAM 31.1 GB」、
それ以外が「未導入 / 実験的・未実測 / 未計測」と一目で分かる形になった。

```text
./mf.sh test   532 passed
```

## UX5 — この機材で動くかを表に出す / ダウンロードの行き先（2026-08-24）

### 実行可否

容量とライセンスが並んでいても「これは動くのか」は分からなかった。判定できる
材料は既にあった（各モデルの実測 VRAM と、この機材の VRAM 量）が、後者が
どこにも出ていなかった。

```text
環境スナップショット   _verify_gpu は total_memory_bytes を既に取得していたのに
                       文章の中にしか入れていなかった。gpu_memory として数値で出す
capabilities           device.vram_bytes として UI へ届ける
                       取れないときは 0。推測しない
```

判定は 4 段階にした。

```text
実行可能        実測 VRAM <= この機材の VRAM
オフロード前提   実測 VRAM が上回るが、CPU オフロードで動く見込みの範囲
未計測          実測が無い。分からないものは分からないと出す
起動不可        明らかに載らない、または capability を持たない
```

**実測していないものを「動く」とは言わない。** 未計測は未計測のまま出し、
重みの大きさは目安にしかならないので、明らかに載らない場合だけ起動不可とする。
CPU オフロードは動くが遅くなる選択肢なので、実行可能とは分けて出す。

並び順に「この機材で動く順」を足した（同順位なら実測 VRAM の小さい順）。

実ブラウザ実測（VRAM 34,208,743,424 バイトとして）:

```text
実行可能  1 件   FLUX.2 Klein 4B（実測 31.1 GB）
未計測    9 件
起動不可  3 件   MiniMax H3 系（117-134 GB）
page errors 0
```

### ダウンロードの行き先

ダウンロードは数十 GB かかることがあり、押したあとの行き先が無かった。
進行中・完了・失敗を 1 か所にまとめ、進行中があれば自動で開く。
終わったものも残す（何が落ちたのかを後から確かめられないと、やり直して
よいのかが分からない）。

```text
./mf.sh test   537 passed
```

NOT TESTED: 実機での `gpu_memory` 出力（provision を再実行するまで既存の
environment-status.json には現れない）。実機受入で確認する。

## UX6 — 実機フィードバックによるモバイル最適化（2026-08-24）

LAN プレビューを実機（iPhone）で確認してもらい、指摘を反映した。

### ダイアログの入力に指が届かなかった

利用者から「タップしても入力できない。モックサーバの仕様か」と質問。
**モックの仕様ではなく CSS の不具合だった。** 決めつけずに調べて正解だった。

```text
dialog { max-height: 82vh }   高さは切っていた
                              overflow-y が無く、はみ出した部分へ到達できない
```

キャラ登録の名前欄は上部にあり、画面外へ出たまま送れなかった。
`overflow-y: auto` を入れ、モバイルでは下からのシートにした（中央寄せの小窓は
ソフトキーボードが出ると入力欄ごと隠れる）。実機幅 390px で名前・見た目の
両方に入力できることを確認した。

### カードと表で出す情報が食い違っていた

同じモデルなのに、カードは 5 つのタグ、表は 2 つしか出していなかった。
表示が 2 つあると、片方だけ直る。**表に統一し、カードと切替を削除した**
（利用者指示）。死んだカード描画 4,480 文字も除去した。

### 「CLI で管理」が何を指すか分からなかった

説明のない専門用語だった。何ができないのかを言うようにした。

```text
before  CLI で管理
after   操作できません（+ この表示では追加・削除ができない旨を title と見出しに）
```

### モバイルで必要な情報が画面外に出ていた

横に伸びる表では、容量・VRAM・操作が右へはみ出して読めなかった。モバイルでは
1 行を積み上げ、各セルに列名を添える（積んだ途端に「14.9 GB」が何の数字か
分からなくなるため）。

```text
実測（390px）  page_overflow_px 0 / table_overflow_px 0
               モデル・この機材・状態・採用・容量・VRAM・ライセンス・操作の
               8 項目すべてが横スクロールなしで可視
```

### 「用途」は選ぶ基準になっていなかった

利用者指摘「用途って何？不要ではない？」。そのとおりだった。
`text-to-image` / `image-to-image` は配布元の技術的分類で、SD 系はほぼ全部が
text-to-image のため絞り込みの役に立たない。実際に決めているのは
「どんな絵を作るモデルか」なので、配布元のタグで画風を選べるようにした。

```text
実 API 実測
  anime      -> Lykon/dreamshaper-7, John6666/nova-furry-xl-il-v120-sdxl
  pixel-art  -> Limbicnation/pixel-art-lora, adirik/pixel-art-lora-flux.2-klein-4B
  realistic  -> John6666/diving-illustrious-real-asian-v50-sdxl
```

### その他

```text
参照の選択    「最大 4 枚」と書きながら選択状態が見えなかった。選択中の枚数を
              出し、上限に達したら選べない枠を淡くする
並び順        ダウンロードの状況と repository 直指定を、使用頻度の低い順に下げた
歯車          もう一度押すと閉じ、設定の前にいた画面へ戻る
```

```text
./mf.sh test   539 passed
```

## UX7 — 実機での作り込み（2026-08-24）

LAN プレビューを見ながら、指摘のたびに直した。以下はすべて実機の指摘由来。

### 撤去したもの

```text
「この拡張機能について」以下   静的な説明文と診断表示。毎回読む価値がないのに
                              毎回場所を取っていた
repository の直接指定          検索が入ったことで使われない。検索に出てこない版が
                              要る場合は CLI から入れる
モデルのカード表示             表と出すタグが食い違っていた。表示が 2 つあると
                              片方だけ直る。表に統一した
詳細設定の幅・高さ             上の「サイズ」と重複し、しかも詳細側が上書きして
                              いた。どちらが効くのか分からない状態だった
```

### 直した不具合

```text
検索が動かない       単体表示に検索経路が無かった。配布元の検索はホストを
                     必要としないので /workspace-api/models/search を足した
導入・削除が出ない   単体表示の shim が management_available を false に固定して
                     いた。ローカルのモデル管理もホストを必要としないので、
                     実際に設定されているものを返すようにした
検索結果の表が崩れる  セルに列名が無く、積み上げると数字だけが裸で並んでいた
2 列が 13 列になる    auto-fill に minmax(0, ...) を渡すと列が無限に増える。
                     最小幅は実数で与え、はみ出しは子の min-width: 0 で防ぐ
横あふれ 76px        td.name に後から display:block を当てており、潰せる指定が
                     効いていなかった。長いモデル名が枠を押し広げていた
カードがガタつく      align-items: start で名前が 2 行の側だけ伸びていた。
                     stretch にし、操作を margin-top: auto で下端へ揃え、
                     名前に 2 行ぶんの場所を先に取る
```

### 実測（390px）

```text
横あふれ            0
列数                2
同じ行の高さ不一致   0
操作ボタン          ダウンロード / 共有モデル / 外部ランタイムで導入 / 32GB上限対象
検索                anime で 3 件（実 API）
./mf.sh test        547 passed
```

## G4H A5 — coding agent から build/test までの実機受け入れ（2026-08-25）

`scripts/a5_agent_asset_path_e2e.py` が経路全体を 1 回で通す。実物は GPU・
モデル・生成された画素・プロジェクト・その build と test。stub は ControlDeck
の grant 配管だけで、commit されたバイトは実プロジェクトへ書く（メモリ内で
済ませると、壊れた配置が誰にも気づかれず通ってしまう）。

```text
project analysis
  -> purpose-level asset request   prompt / model / 画素数を一切書かない
  -> real generation on the GPU
  -> deterministic inspection against the brief
  -> output grant requested late   バイトが在ってから頼む
  -> placement receipt
  -> code updated from the receipt 推測したパスではなく受領書の名前と digest
  -> build
  -> test
```

実測（2026-08-25、AMD Radeon AI PRO R9700）:

```text
agent が出した brief   role=background surface=game aspect_intent=landscape
                      hard_constraints=["no text in the image"]
                      safe_areas=[top 35% title and menu]
Media Forge が決めた   1024x576（landscape を用途から解決）
routing               black-forest-labs/FLUX.2-klein-4B（agent は指定していない）
生成                   28.05 秒 / 730,468 bytes
受領書                 committed=true sha256 が検査済み資産と一致
project への commit    title-background.png 730,468 bytes
build / test          0 / 0（3 passed）
./mf.sh test          588 passed
```

### 実機でしか出なかったこと — 宣言された必須条件が検査されていない

初回実行は緑で通ったが、生成物には文字が入っていた。`hard_constraints` に
`"no text in the image"` を宣言していたにもかかわらずである。

`hard_constraints` は評価器の rubric にしか渡っておらず、評価器は既定で回さ
ない。回さないこと自体は意図した設計で、必須条件のために毎回 model 載せ替え
を強いるのは高すぎる。問題は `warnings: []` を返していたことで、これは「確か
めた、問題なかった」と読める。決定的検査が見ているのは幾何・mode・alpha まで
で、絵の中身は読んでいない。

確かめていないものは、確かめていないと言う。評価器は既定のまま回さず、
warnings に未検査の必須条件を名指しで残す。

```text
before  warnings: []
after   warnings: ["以下は宣言された必須条件ですが、この実行では検査して
                   いません（qa.semantic を有効にすると検査します）:
                   no text in the image"]
```

NOT TESTED: OpenCode の UI から人手で駆動した経路。ここでは coding agent の
役を script が演じている。OpenCode 固有の部分（session、tool 呼び出しの形）は
未検証で、Media Forge 側の入口は同じ `/addon/v1/agent/pack` を使っている。

## 導入済み画像モデルの一括検証（2026-08-25）

`scripts/verify_installed_models.py` が、導入済みの画像モデルを 1 つずつ実際に
走らせて確かめる。カタログが並べている 55 の pipeline クラスは「ランタイムが
構築できる形式」であって「全部この機材で動く」ではない。後者を証明するには
55 個落とすことになるので、証明できるのは手元にあるものだけである。

未実測なら測って昇格し、実測済みでも 1 回走らせる。数か月前に測ったモデルが
ランタイム更新で壊れても、走らせなければ誰も気づかないためである。画像ワーカー
の経路でないモデル（GGUF 動画系）は、黙って省かず「対象外」として並べる。省くと
報告が「全部通った」に見える。

実測（2026-08-25、AMD Radeon AI PRO R9700 / 512x512 / 8 steps）:

```text
black-forest-labs/FLUX.2-klein-4B     20.7 GB   45.34 秒   333,821 bytes
segmind/SSD-1B                         5.8 GB    6.93 秒   278,849 bytes
stabilityai/stable-diffusion-xl-base    8.5 GB    7.78 秒   411,811 bytes
Wan-AI/Wan2.2-TI2V-5B                 対象外（native.wan2.2）
unsloth/MiniMax-H3-GGUF               対象外（native.stable-diffusion-cpp）

通った 3 / 失敗 0 / 対象外 2
```

NOT TESTED: 落としていない 52 形式。構築できることは runtime の mapping から
分かるが、この機材で動くことは落として走らせるまで分からない。新しく入れたら
このスクリプトを回す。

## モデル本来の設定を、モデル自身から決める（2026-08-25）

SDXL base の生成結果がおかしいという指摘から。実測 3 枚:

```text
1024x1024 / 4 歩   にじんだ壁に robot の破片が浮くだけ   ← 実際の生成経路
512x512  / 8 歩    指示した被写体が存在しない別の絵      ← 検証スクリプト
1024x1024 / 30 歩  指示どおりの写真                     ← SDXL 本来の設定
```

モデルは正常で、流し込んでいた設定が間違っていた。`worker.py` が歩数を一律
`4` に既定していた。4 は FLUX.2 Klein（蒸留済み）の値で、core は歩数を一切
送っていなかったので、SD 系は必ずこの歩数で回っていた。共通の既定は置けない。

寸法は推測しない。`unet.sample_size` × VAE の縮小率が、そのモデルが学習された
寸法である。SDXL / SSD-1B は 128 × 8 = 1024、SD 1.5 は 64 × 8 = 512。55 の形式
のどれでも repository の中身から同じ手順で出るので、形式ごとの表を持たない。

縦横比も同じ考えで揃える。SDXL が公表しているバケット（1024x1024, 1152x896,
1216x832, 1344x768, 1536x640 とその転置）は「64 の倍数で面積が 1024^2 に近い」
ものの集合そのものなので、学習寸法から計算で出る。要求された比を保ったまま、
面積を学習時に合わせる。総画素を増やすと、モデルが見たことのない広さになり
同じ被写体が 2 つ並ぶ。

歩数だけは中身から出ない。scheduler が LCM/TCD なら少歩数だと分かるが、
SDXL Turbo も SDXL Lightning も素の SDXL と同じ pipeline クラスと scheduler を
名乗る。分からないと認めて多い側（30 歩）に倒してある。多い分は時間を損する
だけで絵は出るが、少なすぎると絵が出ない。「評価」で実際の値が分かる。

評価も本来の設定で走らせる。小さく短く測ると速いが、測った値が実使用と別物に
なる。SDXL は 512x512 / 8 歩で 8.45GB と記録されていたが、本来の 1024x1024 /
30 歩では 12.55GB 要る。その差だけ routing が少なく確保していた。実測済みでも
測り直して書き戻すようにした。

`verify_installed_models.py` の "verified" は "generated" に改めた。PNG が
返ったことしか見ていないので、崩れた絵を「通った」と報告していた。

実測（2026-08-25、AMD Radeon AI PRO R9700、いずれも本来の設定）:

```text
black-forest-labs/FLUX.2-klein-4B   1024x1024 /  4 歩  29.9 GB  17.36 秒
segmind/SSD-1B                      1024x1024 / 30 歩  18.9 GB  11.34 秒
stabilityai/stable-diffusion-xl     1024x1024 / 30 歩  12.5 GB  12.76 秒
```

NOT CHECKED: 絵が正しいかどうかは自動では見ていない。上の 3 枚は目視した。

## 自動で決められない設定を、言って選べるようにする（2026-08-25）

寸法と縦横比はモデル自身の config から決まるが、歩数だけは決まらない。
蒸留版（Turbo / Lightning / LCM）は素の親と同じ pipeline クラスと scheduler を
名乗るので、配布物からは見分けられない。多い側（30 歩）に倒してあるが、
Turbo 系にそれを当てると時間を損し、ガイダンス 7.0 のままだと絵が焼ける。

そこで「何が決まっていて、何が決まっていないか」を判定した側が文章にして
返す。`generation_defaults.summary()` が `settled` と `needs_check` を作り、
`/api/v1/models` の `generation` に載る。UI はそれを並べるだけで、判断を
やり直さない。2 か所に分けると片方だけ直る。

詳細設定に出るもの:

* 確認が必要な項目（枠付き）— 項目・現在値・なぜ決められなかったか・どうするか
* 自動で決まった項目（折りたたみ）— 項目・値・何を根拠に決めたか
* プリセット — 判別できなかったときだけ Turbo / Lightning が出る。素のモデルに
  4 歩を勧めると崩れるので、決まっているモデルには出さない
* 歩数とガイダンスの直接入力。既定から変えたときだけ要求に載せる

ガイダンス 0 を通せるようにした。0 は「CFG を使わない」という指示で、Turbo 系は
それを前提に蒸留されている。registry と worker の両方が `0 <` で弾いていたので、
そのモデルを正しく回せなかった。

実測（2026-08-25、導入済み 3 件）:

```text
FLUX.2 Klein   4 歩 declared  確認が必要: なし              プリセット 2
SSD-1B        30 歩 declared  確認が必要: なし              プリセット 2
SDXL base     30 歩 assumed   確認が必要: 歩数・ガイダンス   プリセット 4
```

描画は jsdom に実物の template を載せて確認した。NOT TESTED: 実ブラウザでの
見た目（playwright がこの環境に無い）。

## 配布元として Civitai を選べるようにし、既定にする（2026-08-25）

Hugging Face には diffusers 形式の基盤モデルが並ぶが、実際に絵を作るときに
使われている調整済みのものは Civitai にある。検索できないものは存在しない
のと同じなので、切り替えられるようにし、既定を Civitai にした。

**検索だけ足すと「見つかるが動かない」ものが既定で並ぶ。** Civitai が配るのは
単一の safetensors で、`diffusers.sdxl` は `from_pretrained` でディレクトリを
読む。`diffusers.sdxl-single-file` は models.json に名前だけあって実装が無かった。
単一ファイルの読み込みまで含めて 1 つの作業とした。

系統は safetensors の中身から判定しない。判定には UNet の次元を読むことになり、
Pony や Illustrious のような派生で外す。配布元が `baseModel` として名乗って
いるものを使い、名乗っていなければ取り込まない。

実測して分かったこと:

```text
検索    GET /api/v1/models      認証不要
形式    1 version = 1 .safetensors
系統    version.baseModel が "SD 1.5" / "SDXL 1.0" / "Pony" などを名乗る
digest  file.hashes.SHA256 が付く。手元計算ではなく配布元の公表値を使う
取得    /api/download/models/{versionId} が署名付き URL へ転送する
UA      既定の User-Agent は 403。認証の問題ではないので鍵を求めない
```

Hugging Face の token を Civitai に送らない。他所の資格情報を、要求されても
いない相手に渡すことになる。

実機で通した経路（2026-08-25）:

```text
検索      civitai/4384 DreamShaper 8      SD 1.5   1.99GB
解決      base_model=SD 1.5 → 512x512 / 30 歩、diffusers.sdxl-single-file
取得      2,132,625,894 バイト、sha256 が API の公表値と一致
生成      512x512 / 30 歩 / 60.7 秒 → 指示どおりの絵（目視）
```

やらないこと: LoRA。Civitai の多くは LoRA だが Media Forge に経路が無い。
検索を Checkpoint に絞ってある。NSFW は既定で外す。

## LoRA を使えるようにする（2026-08-25）

LoRA は「モデル」ではない。選んだ checkpoint に載せるもので、単体では絵を
作れない。registry には別の capability（`image.lora`）で載せた。routing は
`capability in item.capabilities` で候補を絞るので、`image.text_to_image` を
求める経路には最初から現れない。旗を立てて後から除外する作りにすると、除外を
書き忘れた経路が 1 つでもあれば LoRA が本体として選ばれる。

### 読み込めるまでに 2 つ詰まった。どちらもエラーからは分からない

**transformers 5 で CLIP のモジュール名が変わっていた。** 今は
`encoder.layers.0.mlp.fc1` で、以前は `text_model.encoder.layers.0.mlp.fc1`
だった。diffusers 0.40 は encoder にモジュール名を訊いて、それを変換済みの
state dict から引いて rank 表を作る。state dict 側には古い接頭辞が残っている
ので全部外れ、空の表を持って `IndexError: list index out of range` で落ちる。
場所も理由も示さないし、LoRA 側は壊れていない（実測: add_detail.safetensors は
text encoder 216 個・UNet 576 個のテンソルを持つ）。読み込んだ encoder の形に
合わせて鍵を書き換える。逆方向には触らないので、古い transformers でも動く。
text encoder 側を捨てて UNet だけ載せる手もあるが、それは黙って別の絵になる。

**SDXL の LoRA は SGM のブロック番号で保存されている。** `load_lora_weights`
は unet の config を `lora_state_dict` に渡して変換している。こちらで state
dict を作るなら同じものを渡す必要があり、渡さないと「該当する層が無い」と
延々並べて落ちる。

**LoRA は選んだモデルとは別の repository に入る。** モデルの境界は
そのモデル 1 つ分に絞ってあるので、同じ境界で見ると必ず外に出る。境界を
広げるのではなく、LoRA 用の根（導入先）を別に渡す。

`peft` をランタイムの依存に追加した。無いと `load_lora_weights` が拒む。

### 実機で確かめたこと（AMD Radeon AI PRO R9700）

```text
SD 1.5   midjourneyanime を DreamShaper 8（単一ファイル）に  絵が変わった
SDXL 1.0 Detail Tweaker XL を SDXL base（ディレクトリ）に      絵が変わった
```

adapter の経路が別なので、両方通して初めて「LoRA が動く」と言える。同じ seed
で前後を並べて目視した。

Civitai の一部の LoRA は 401 を返す（早期公開など）。鍵が要る配布物なので、
そう伝える。UA 不足の 403 とは別の理由である。

### 土台は同じ操作で自動解決する（2026-08-27 更新）

LoRA は 40MB 前後だが土台は 2〜7GB ある。取り込む前に、載せる先が手元に
あるかを調べる。無ければその系統の checkpoint を依存として解決し、LoRA と
合わせた容量・双方のライセンスを 1 回の確認にまとめる。利用者が土台を選ぶ、
別のチェックを入れる、別のダウンロードを押す、という操作は要求しない。

登録は LoRA と土台を 1 回の durable 更新で行い、ダウンロードも同じ要求から
開始する。生成時は LoRA の系統で routing 候補を絞る。UI の手動モデル選択に
互換性判定を委ねない。

### UI

* 検索行に種別（モデル本体 / LoRA）。Hugging Face には LoRA の経路が無いので、
  そちらを選んだときは種別を出さない
* 結果に系統と起動語。系統は詳細情報であり、土台を選ばせる操作にはしない
* 生成画面に LoRA の選択と強さ（0〜2、4 個まで）。最初に選んだ LoRA と同じ
  系統だけを追加選択でき、土台は自動 routing する
* モデルの選択肢から LoRA を除く。混ぜると、選んでから断られる

起動語は prompt に自動で足す。足したことは job に残る。既に入っている語は
足さない（二重に入れても効きは強くならず、他の語の重みが薄まる）。

やらないこと: LoRA の学習。動画モデルへの適用（経路が別で未計測）。

## 署名した通りのバイト列を配る（2026-08-25）

v0.9.0 の導入が「信頼できる publisher の鍵に一致しない」で拒まれた。署名も
鍵も正しく、canonical なバイト列に対しては検証が通る。原因は配っている
ファイルの方で、末尾に改行を 1 つ足していた。

署名は改行の無いバイト列に付いている。ControlDeck 側が受け取ったバイト列から
改行を落としてくれている間は通っていたが、検証を厳格化してその処理が無く
なった途端に、正しい署名が拒まれた。落としてもらう前提で配っていたのが
間違いである。配るものと署名したものを同じにする。

v0.7.3 と v0.8.0 も同じ形で配ってある。既に導入済みで、downgrade は拒まれる
ので影響は無いが、それらを今から検証し直すことはできない。

## G7 V0 — additive video contract と FFmpeg 正規化境界（2026-08-26）

G7 を `docs/implementation/g7-video-runtime.md` の V0〜V4 に分けた。V0 はモデルを
動かさず、既存の汎用 `video.generate` / `video.edit` 設計を公開 JobRequest へ加法的に
載せ、生成物を公開する前の決定的 FFmpeg 境界を worker pack に置くスライスである。

契約:

```text
video.generate inputs 0 / 1 / 2..8   T2V / I2V / multi-keyframe の将来 routing
video.edit     inputs 1..8            入力なしと 9 件以上を ingress で拒否
output                                mp4 / webm のみ
Asset MIME                            video/mp4 / video/webm を加法追加
Asset metadata                        duration_sec / frame_rate を任意追加
capability                            unavailable / planned_for_g7 を維持
runtime 未実測 job                    capability_unavailable で fail-closed
```

FFmpeg worker 境界は配列 subprocess、timeout、1 video stream、偶数寸法、fps 1..120、
尺 300 秒以下を強制する。MP4 は H.264/AAC、WebM は VP9/Opus。ffprobe で codec、
container、寸法、fps、frame count、audio を再検証し、失敗時は partial output を消す。

実ファイルでの単体実測（Ubuntu system FFmpeg 6.1.1、保存先
`/data1tb/mediaforge-g7-v0-evidence/2026-08-26/`）:

```text
source.mkv       160x90 / 24fps / 2秒 / video+audio   251,768 bytes
normalized.mp4   128x72 / 12fps / 1.25秒 / 15 frames / H.264 / audioなし
                 0.07秒、max RSS 61,564 KiB、6,259 bytes
                 sha256 45052db72a23d29525aecb028a84056e27a61a9044b46a045999f33d4e755daf
normalized.webm   96x64 / 24fps / 0.508秒 / 12 frames / VP9 / Opus audio
                 0.09秒、max RSS 72,752 KiB、18,194 bytes
                 sha256 6a8495a0033d2f67c63aecee0d19beb20a4185480a5cfeb1055aca75bf081ed5
GPU               use 0%、KFD process 0、R9700 VRAM used 59,912,192 bytes
```

branch core を `127.0.0.1:9160` で実起動し、実 HTTP でも確認した。

```text
POST /api/v1/jobs video.generate/mp4
  202 Location /api/v1/jobs/job_a9756b1cd48a4dd0966d7294967d8fc8
GET 同 job
  failed / capability_unavailable / "video.generate has no measured local runtime"
GET /api/v1/capabilities
  video.image_to_video = unavailable / planned_for_g7
installed v0.9.0 GET :9130/health
  healthy / R9700 gfx1201 / torch 2.10.0+rocm7.2.1.gitb07cec22 / HIP 7.2.53211
```

検証:

```text
focused + store + bundle   61 passed
./mf.sh test               683 passed, 1 warning in 50.24s
git diff --check           PASS
compileall                 PASS
```


NOT TESTED: 動画モデルの import/generation/quality、R9700 VRAM、Broker lease/wait/cancel、
LLM 退避/復帰、SonicForge job との同時 admission、installed bundle/browser playback。
V1 の revision-pinned candidate probe と V2〜V4 の範囲であり、video capability は
それらが通るまで unavailable のままにする。release bundle 上の system FFmpeg 検出/
provision も V2 前提として未実施。ControlDeck の変更は 0 件。

実装 PR: Media Forge #119。

## G7 V1 — Wan2.2 TI2V-5B revision-pinned R9700 probe（2026-08-26）

V1 は production video worker を作らず、既存の private Model Management evaluator へ
fixed preset を追加して候補採否を測るスライスとした。公式 model revision は
`921dbaf3f1674a56f47e83fb80a34bac8a8f203e`、weight は 34,201,521,212 bytes、
Wan2.2 source は commit `42bf4cfaa384bc21833865abc2f9e6c0e67233dc`、license は
Apache-2.0。source は unrelated S2V/Animate の eager import だけを除く固定 patch
（diff SHA-256 `4fd9b36b24f3385057445de8551c79b947498f253c061f56a457dc42a21afb93`）を
preflight で検証する。モデル本体の FlashAttention 呼び出しは upstream に既存の PyTorch
SDPA fallback へ置換し、custom kernel は追加していない。

runtime は外部 `/data1tb/mediaforge-g7-v1/runtime` に分離し、torch 2.10.0 / ROCm 7.2.1、
diffusers 0.33.1、transformers 4.51.3 ほかを exact version で構築した。core と image runtime
は共有していない。最初の diffusers 0.40 組合せは Hugging Face Hub dependency bounds が
衝突したため不採用とし、採用した runtime は `pip check` が成功した。UMT5 は meta device
構築、mmap weight、`assign=True` で CPU process に読み、GPU generation process と重ねない。
実 encode は 8.37 秒、max RSS 10,455,924 KiB、process swap 0 だった。

実 ControlDeck の installed iframe から短命 browser identity を取得し、Host Job、Broker
request/activate/renew/release を通して評価した。導入済み manifest は変えず、評価中だけ branch
core を同じ 9130 port / data directory で起動した。テスト account の password hash は実行中だけ
置換し、各 run の `finally` で元の exact hash に復元した。秘密値は証跡・log に出していない。

固定 prompt / seed、guide 5.0 の 512x320 / 17 frames / 30 steps:

```text
cold operation modelop_6a8a15fa02884ec29ad315c3e1d31fab
  elapsed 412.790 sec / peak VRAM 30,612,889,600 B / peak RSS 20,501,524,480 B
  process swap 0 / H.264 24fps / 0.708 sec / 117,318 B

direct-BF16 warm 3 samples
  elapsed                    75.955 / 71.972 / 71.221 sec
  peak VRAM                  30,611,857,408 / 30,612,119,552 / 30,611,984,384 B
  peak RSS                   20,525,383,680 / 19,526,950,912 / 20,201,570,304 B
  process swap               0 / 0 / 0 B
  output                     512x320 / 17 frames / H.264 / 24fps / 0.708 sec / 97,849 B
  SHA-256                    6b0e0d22ea349394cc4436fd84bed19f67b70739ab8aca83b7bd43c2ad9fe90a
```

3 warm sample は同一 hash で、抽出 frame では orange robot、solar panel、landscape を識別でき、
短尺比較候補としての prompt coherence があった。cold 412.790 秒は初回 kernel/cache compile を
含む観測で、warm runtime と混同しない。resource request は最大実測 30,700,000,000 bytes と
1 GiB headroom に更新した。

実用最短を狙った 256x256 / 49 frames / 30 steps は operation
`modelop_73cade3efa7546ad89807e115321a4d3`、Host Job `c59e40978822` で完走した。

```text
elapsed                    235.053 sec
peak VRAM                  20,528,300,032 B（incremental 20,468,387,840 B）
peak RSS / process swap    19,341,029,376 / 1,754,775,552 B
system swap pages delta    in 540,476 / out 539,847
output                     256x256 / 49 frames / H.264 / 24fps / 2.042 sec / 130,960 B
SHA-256                    9b7ec4eca742b20783597803aa94cf2f762d833f9dbc7e1017ac5014e9c9dfd2
```

decode と container は正常だったが、frame 0/24/48 の目視では被写体が崩れ、orange robot / solar
panel / dusk を維持しなかった。さらに process swap が 0 でない。したがって「実用 clip quality /
host RAM safety」は **FAIL** とし、Wan を Available/Recommended/production route に採用しない。
catalog の `measured` は bounded resource envelope の confidence だけを意味し、品質採用ではない。

Broker / cancellation / 共存:

```text
SonicForge/LLM hold 中     30.239 GB request は insufficient_capacity で fail-closed
hold 解放後                同じ browser route が granted、Wan process が開始
cancel                     modelop_65ac98568fa541378a70a38a8e8e6f48
                           VRAM 11,342,323,712 B 時点から 1.007 sec で canceled
                           lease release、Wan process 0、VRAM 59,912,192 B
SonicForge 後続 request    Media Forge release の 0.717 sec 後に activate
completed cleanup          lease 0、Wan process 0、baseline VRAM 59,912,192 B
```

cancel run で最初に prompt embedding が残ることを発見し、terminal state に関係なく削除し、
failed/canceled では partial video/frame/probe も削除するよう修正した。回帰 test を追加した。
評価後は branch core を停止し、installed Media Forge v0.9.0 service を再起動した。実 health は
`healthy`、R9700 gfx1201、torch 2.10.0+rocm7.2.1、HIP 7.2.53211、GPU memory
34,208,743,424 bytes と応答した。ControlDeck の変更は 0 件。

`base-plan.md` §24:

1. T2V/I2V の軽量候補だが、今回証明したのは bounded T2V だけ。
2. isolated Wan runtime と private evaluator が必要。既存 image adapter は使わない。
3. gfx1201 で smoke/短尺/49-frame は完走したが、実用 gate は swap/quality で不合格。
4. 上記に cold/warm、VRAM/RSS/swap/runtime を記録。resource envelope は measured。
5. weight/source は Apache-2.0。
6. 公開 asset/provenance は V2 未実装のため **NOT TESTED**。
7. 17-frame は有望だが、実用 clip は installed alternatives を正当化する品質でない。
8. process group cancel、Host Job、Broker release は実測 PASS。
9. upstream SDPA fallback のみ。custom kernel はない。固定 source patch は evaluator import 用。
10. generic video capability の裏側なので catalog/runtime を削除しても公開 API は変わらない。

判定: runtime/import、bounded short generation、Broker isolation、cancel は **PASS**。実用 clip
品質と zero-swap は **FAIL**。I2V、native 720p、公式既定 121 frames / 50 steps、V0 FFmpeg
normalizer との production 接続、公開 Asset/provenance、installed release bundle の動画再生は
**NOT TESTED**。V1 model adoption は **DEFERRED**。再開条件は、prompt を維持し process swap 0
で完走する実用最短 profile、または別候補の比較結果である。V2 へは昇格させない。

検証:

```text
focused evaluator/catalog    17 passed
./mf.sh test                 686 passed, 1 warning in 48.38s
git diff --check             PASS
compileall                   PASS
```

## G7 V1b — Wan evaluator host-memory lifecycle 比較（2026-08-26）

V1 の 49-frame probe で観測した process swap を、transformer offload と VAE decode に分離した。
upstream `offload_model=True` は denoise 後に約10GBの transformer を CPU へ移してから decode
する。1 job で終了する evaluator は transformer を再利用しないため、同じ offload 境界で
parameter storage を meta tensor 化して GPU storage を破棄し、CPU copy を作らないようにした。
custom kernel、upstream source patch、ControlDeck 変更は追加していない。

実 installed browser identity / Host Job / Broker route:

```text
discard smoke operation     modelop_5b67d9512287455e8919e1aa994a1c62
elapsed                     25.307 sec
peak VRAM / RSS / swap      13,752,025,088 / 19,181,559,808 / 0 B
output                      256x256 / 1 frame / H.264 / 24fps / 2,411 B
SonicForge hold wait        acquiring_resource 35.4 sec、release 後に生成

candidate operation         modelop_2adb1fff80bb4c8397f639c8c9885f0e
profile                     384x256 / 33 frames / 30 steps / guide 5.0
elapsed                     284.677 sec（VAE decode 210.810 sec）
peak VRAM / RSS / swap      14,045,294,592 / 20,670,320,640 / 0 B
system swap pages delta     in 55,845 / out 63,443
output                      H.264 / 24fps / 1.375 sec / 115,130 B
SHA-256                     db3188a464db34aa1a6b5196897061df78e495f6ef56be116d6c323c549f14f5
```

384x256 の frame 0/16/32 は robot / panel / landscape に近い構造を持つが、形状崩れが大きく
採用品質ではない。RAM lifecycle は **PASS**、この profile の実用品質は **FAIL**。

より高解像度の 512x320 / 33 frames は、約30.239GBの SonicForge/LLM residency 中の
operation `modelop_d3703e07a74949dcab9622e8ceb96cf1` と直後の再試行を Broker が
`insufficient_capacity` で fail-closed にした。worker/GPU process は起動せず、test account
hash は復元した。その residency が自然 release した後、同じ profile を2回実行した。

```text
operation                   modelop_389b17382055448f9fc36300599387f2
elapsed                     185.270 sec
peak VRAM / RSS / swap      20,762,644,480 / 17,313,533,952 / 2,501,005,312 B

operation                   modelop_bcc4b8bf3672437e986905bcfc1a3291
elapsed                     129.742 sec
peak VRAM / RSS / swap      25,293,598,720 / 19,265,691,648 / 346,812,416 B

both outputs                512x320 / 33 frames / H.264 / 24fps / 1.375 sec / 143,262 B
both SHA-256                744c4f85f0b52bc29cba9cd4a423e5ac95b93fdf53ec8c9e23e6073907e95d6a
```

frame 0/16/32 は orange robot、前面 solar panel、dusk field を維持し、時間方向も一貫した。
品質と deterministic output は **PASS**。ただし process swap が2回とも0ではなく、改善後も
346,812,416 bytes 残ったため zero-swap / operational reliability は **FAIL** とする。

結論: meta-discard lifecycle と 512x320/33-frame 品質は有望だが、Wan の production adoption は
引き続き **DEFERRED**。別候補またはさらに単純な maintainable lifecycle が prompt coherence と
zero-process-swap を同時に満たすまで V2 へ進まない。評価終了後は branch core を停止し、installed
Media Forge v0.9.0 を再起動した。実 health は `healthy`、contract 2.0、R9700 gfx1201、
torch 2.10.0+rocm7.2.1、HIP 7.2.53211。Wan worker は0、ControlDeck変更は0件。

検証:

```text
focused evaluator/catalog    17 passed
./mf.sh test                 686 passed, 1 warning in 51.30s
git diff --check             PASS
compileall                   PASS
```

## G7 V1c — HunyuanVideo-1.5 weight-free R9700 preflight（2026-08-26）

Wan 512x320 practical profile が prompt quality は通った一方で2回とも process swap を残したため、
別候補を一次資料から比較した。LTX-2.3/2.5 は 22B transformer に別の 12B text encoder を要し、
公式 quick start bundle は約66GiB、low-memory route は FP8/offload 前提である。HunyuanVideo-1.5
は公式に 8.3B、offload 有効時の minimum GPU memory 14GB、480p T2V と Diffusers default
attention route を公開しているため、次の bounded candidate に選んだ。

評価 identity:

```text
official model       tencent/HunyuanVideo-1.5
official revision    9b49404b3f5df2a8f0b31df27a0c7ab872e7b038
Diffusers conversion hunyuanvideo-community/HunyuanVideo-1.5-Diffusers-480p_t2v_distilled
conversion revision  1abb14f06518f37448dcf3a6917dd086dd7045c7
bundle               13 weight files / 53,367,753,676 bytes
all snapshot files   53,384,320,234 bytes
```

core/image/Wan runtime と分離した `/data1tb/mediaforge-g7-hunyuan15/runtime` を exact package
versions で構築した。size は 4,688,976,346 bytes、`pip check` は broken requirements 0。
最終 weight-free preflight は 2.34 秒、max RSS 832,056 KiB、OS swap 0 で完了した。

```text
torch          2.10.0+rocm7.2.1.gitb07cec22 / HIP 7.2.53211
GPU            AMD Radeon AI PRO R9700 / gfx1201
diffusers      0.40.0
transformers   5.15.1
imports        HunyuanVideo15Pipeline / HunyuanVideo15Transformer3DModel /
               AutoencoderKLHunyuanVideo15
attention      PyTorch SDPA default / custom kernel 0
GPU process    preflight 後 0
```

公式 runtime が挙げる Flash Attention、Flex-Block-Attention、SageAttention、SGL-Kernel は
CUDA/H-series向け最適化であり、この probe には入れない。standard PyTorch SDPA で gfx1201 を
先に評価する。

license は Tencent Hunyuan Community License Agreement（HunyuanVideo 1.5 release
2025-11-21）。利用開始が同意となり、EU/UK/South Korea を除く Territory、acceptable-use、
distribution/notice、第三者提供時の表示条件、100M MAU 条件などを含む。conversion repository
の `license: other` 表示だけで単純化しない。利用者の明示同意なしに 53GB weight を取得しない。

判定: isolated runtime build/import、R9700 enumeration、default SDPA は **PASS**。weight download、
hash verification、model load、generation、VRAM/RSS/swap、quality、cancel、Broker、installed browser は
**NOT TESTED**。次の操作は license acceptance 後の bounded sequential download であり、現在は
**BLOCKED PENDING LICENSE ACCEPTANCE**。ControlDeck 変更は0件。

最終 gate:

```text
dedicated pip check        broken requirements 0
weight-free preflight      PASS / 2.34 s / max RSS 832,056 KiB / OS swap 0
installed /health          healthy / contract 2.0
ROCm process cleanup       KFD process 0
full                       686 passed / 2 warnings / 51.28 s
git diff --check           PASS
compileall                 PASS
```

## G7 V1d — Hunyuan license-gated evaluator preparation（2026-08-26）

V1c merge 後も weight / partial snapshot 0 を維持したまま、同意後の実測で使う private evaluator
runner と core admission 経路を実装した。公式推奨では 480p T2V CFG-distilled は 50 steps が必要で、
8/12 steps は 480p I2V step-distilled 向けであるため、T2V quality preset を短縮推測値へ置換しない。

runner invariant:

```text
model identity       tencent/HunyuanVideo-1.5@9b49404b
conversion identity  hunyuanvideo-community/...480p_t2v_distilled@1abb14f0
snapshot ingress     local path only / exact revision / HF cache containment
network              local_files_only / HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE
runtime              dedicated Python / torch BF16 / model CPU offload / VAE tiling
attention            PyTorch SDPA / custom kernel 0
input                 fixed prompt / negative prompt / seed 260826 / fixed presets
artifact              H.264 yuv420p MP4 / exact dimensions, fps, frame count
failure               partial MP4 and temporary frame directory cleanup
```

core へ optional runtime/snapshot/preset 設定を追加した。両 path と revision containment が通らない
限り model evaluation control に現れない。設定後の操作も既存 Host Job → Broker queue/lease/renew/
cancel/release → process-group metrics → ffprobe validation を通す。実測前の request は
`execution_peak=30,700,000,000`、`cold_load_peak=32,000,000,000`、
`headroom=1,073,741,824 bytes`、`estimated_runtime_sec=3600`、`confidence=low` とし、採用値ではない。
Wan source `PYTHONPATH` は Hunyuan subprocess へ漏らさない。

実 runtime で runner CLI import と既存 weight-free R9700 preflight を再実行した。

```text
runner --help              PASS / heavy import・network なし
weight-free preflight      PASS / R9700 gfx1201 / PyTorch SDPA
ROCm process cleanup       KFD process 0
focused                    20 passed / 1 warning
full                       693 passed / 1 warning / 46.96 s
model load / generation    NOT TESTED
weight / partial snapshot  0 / license acceptance 待ち
ControlDeck changes        0
```

判定: evaluator/admission/evidence preparation は **PASS**。model load、Host Broker 実要求、cancel、
artifact、VRAM/RSS/swap、quality/determinism は weight 不在のため **NOT TESTED**。通常の video
capability は unavailable、catalog は experimental/unmeasured のまま。

isolated data directory / `127.0.0.1:9162` で branch core を実起動した。`GET /health` は
`setup_required`（空の isolated data なので正しい）/ contract 2.0、model catalog は
`evaluation.available_model_ids=[]` を返した。Hunyuan entry は `experimental`、`installed=false`、
`measurement_confidence=low`、recommended profile 0。`video.image_to_video` は
`unavailable/planned_for_g7` のままで、設定なしの evaluator 準備が capability を誤昇格させないことを
確認した。branch core は正常 shutdown、installed v0.9.0 は `healthy`、KFD process は0。

最終 gate:

```text
focused                    20 passed / 1 warning
full                       693 passed / 1 warning / 46.96 s
branch core real HTTP      PASS / hidden-until-configured / capability unavailable
installed /health          healthy / contract 2.0
ROCm process cleanup       KFD process 0
git diff --check           PASS
compileall                 PASS
```

## G7 V1e — CogVideoX-2B Apache fallback evaluation（2026-08-26）

HunyuanVideo 1.5 は Tencent Hunyuan Community License の明示同意待ちを維持し、先に
Apache-2.0 の T2V-only 候補 `zai-org/CogVideoX-2b` を評価した。model revision は
`1137dacfc2c9c012bed6a0793f4ecf2ca8e7ba01`。19 files / 13,775,572,738 bytes の exact
snapshot を取得し、5 LFS object の size と SHA-256 を全件照合した。取得中に Xet route が
connection struggling で停止したため、partial を削除せず `HF_HUB_DISABLE_XET=1` の公式 Range
route へ切り替えて完了した。

core/image/Wan/Hunyuan と分離した `/data1tb/mediaforge-g7-cogvideox2b/runtime` を使った。
torch 2.10.0+rocm7.2.1、HIP 7.2.53211、Diffusers 0.40.0、Transformers 5.15.1。
weight-free preflight は R9700/gfx1201、CogVideoX pipeline/transformer/VAE import、PyTorch SDPA
を確認した。runner は exact local snapshot、offline-only、FP16、sequential CPU offload、VAE
slicing/tiling、固定 prompt/negative prompt/seed、H.264 MP4 を強制する。公式外の低解像度を品質
証拠にせず、720x480 を維持した。

最初の 5-frame smoke は Diffusers の temporal compression 条件と一致せず、6分42.98秒後に
frame-count validation で FAIL した。partial output は残らず、GPU は baseline へ復帰した。
通常 frame count は4の倍数、公式 profile は48生成frames + conditioning frameの49であることを
runtime source/configから確認し、smokeを8 framesへ修正した。修正後 smoke:

```text
preset / network             720x480 / 8 frames / 1 step / offline
elapsed / wall               53.316 / 57.85 sec
load / generate              0.893 / 52.077 sec
max RSS / process swap       19,452,981,248 / 0 B（/usr/bin/time: 18,997,052 KiB / swaps 0）
output                       H.264 / 8fps / 11,443 B
SHA-256                      8c9aefea092a9efef17ea7794d0a98c097f9bf4b01a8f325ecbd40214a47d0f4
system swap pages delta      in 612 / out 19,540
```

公式 quality run は installed v0.9.0 を一時停止し、branch core を同じ9130/data
directoryで起動して、短命 Host service identityから実行した。このsliceによるControlDeck
code/DB/manifest変更は0。Host worktreeには今回触れていない既存
`frontend/tsconfig.tsbuildinfo`変更1件がある。

```text
operation                    modelop_eea78a015e9c45aab311a6e14b6424ba
Host Job                     bf25a3d596be
Broker request / lease       52c974fe-c64f-4145-bda0-0e4c5b813553 /
                             6aaa9ab9-09f7-476a-bc95-4326ef3a0cf6
preset                       720x480 / 49 frames / 50 steps / 8fps
elapsed                      930.861 sec（denoise 282 sec、decode支配）
peak VRAM                    14,996,635,648 B（delta 14,936,723,456 B）
peak RSS / process swap      19,315,003,392 / 0 B
system swap pages delta      in 29,888 / out 29,985
output                       H.264 / 6.125 sec / 235,251 B
SHA-256                      a0932382761efe621e8b30c03be59ddb1ed70c78acff44f3ba87e00f8aceb857
```

Host audit は request `granted`、lease `active`、約10秒ごとの renew、10分時点の短命 credential
refresh、最終 `released` を記録した。完了後 Cog process 0、KFD process 0、R9700 VRAM
59,912,192 B。branch coreを正常停止し、installed Media Forge v0.9.0を再起動した。実 `/health`
は `healthy` / contract 2.0。

frame 0/24/48 の目視では orange field robot、solar panel、dusk field、locked camera を一貫して
維持し、SSIM は0→24が0.724、24→48が0.810だった。被写体・構図品質は **PASS**。一方、要求した
「solar panels を折り畳む」動作は明瞭でなく action adherence は **FAIL**。system swap activityと
930.861秒のlatencyも実用gateを満たさない。process swap 0、Broker lifecycle、artifact boundsは
**PASS**。deterministic repeat、Cog固有cancel、SonicForge active residencyとの同時要求、公開
Asset/provenance、I2Vは **NOT TESTED**（I2Vは本modelのcapability外）。

判定: CogVideoX-2BはR9700 backendを実証したが、`experimental` / low-confidence / recommended
profile 0のまま **DEFERRED**。T2V production routeへ採用せず、V2へ昇格しない。Apache-2.0候補
なのでHunyuanのterritory/MAU/AUP制約はないが、再配布時のLICENSE/NOTICE、変更表示、特許・商標
条件は維持する。次の再開条件は、zero system-swapと明確なaction adherenceを短いruntimeで満たす
別T2V候補、またはCogの保守可能なdecode/RAM lifecycle改善である。

最終 gate:

```text
focused                    33 passed / 1 warning
full                       700 passed / 1 warning / 49.15 s
git diff --check           PASS
compileall                 PASS
installed /health          healthy / contract 2.0
ROCm process cleanup       KFD process 0 / VRAM 59,912,192 B
ControlDeck slice changes  0（既存 frontend/tsconfig.tsbuildinfo 変更1件は保全）
```

## G7 V1f — Wan 2.1 1.3B T2V/I2V candidate preflight（2026-08-26）

CogVideoX-2B が action adherence、latency、system swap の gate を落としたため、次の Apache-2.0
候補を official Hugging Face metadata / model card / Diffusers 実装から固定した。T2V は
`Wan-AI/Wan2.1-T2V-1.3B-Diffusers@0fad780a534b6463e45facd96134c9f345acfa5b`、I2V は
`Wan-AI/Wan2.1-VACE-1.3B-diffusers@ec4d2cb062b548996b179d493fdd05340de702a1`。
両方とも public / non-gated、model card の license tag は Apache-2.0。

official tree API の全件を revision 固定で列挙した。

```text
T2V snapshot / weights      28,935,653,511 / 28,928,720,056 bytes
T2V files / LFS inference   31 / 10
T2V weights identity        sha256:5ae5898aacc245296343d129de399f7dcc153900dbbdf882da12a4b18b162569
VACE snapshot / weights     19,043,130,596 / 19,036,896,776 bytes
VACE files / LFS inference  27 / 8
VACE weights identity       sha256:2c488c292438aaa2914e96dea0b8cb929eda504adfb6bb583f721ea63d1be315
```

T2V の text encoder は float32 約22.7GB、VACE は bfloat16 約11.4GB。VACE official card と
Diffusers 0.40.0 の call signature は video / mask / reference_images conditioning を持ち、first-last-
frame-to-video と image/video-to-video を明示する。このため VACE を I2V 候補、T2V 1.3B を T2V
候補として別々に実測する。

専用 `wan21-1.3b-probe` runtime を `./mf.sh env build` で構築した。

```text
runtime size               4,686,651,246 bytes
build elapsed              26 sec / pip cache delta 160 bytes
pip check                  broken requirements 0
torch / HIP                2.10.0+rocm7.2.1 / 7.2.53211
Diffusers / Transformers   0.40.0 / 5.15.1
preflight                  PASS / 2.15 sec / max RSS 959,360 KiB / swaps 0
GPU                        AMD Radeon AI PRO R9700 / gfx1201
attention                  PyTorch SDPA default / custom kernel 0
cleanup                    KFD process 0 / VRAM 59,912,192 bytes
```

exact snapshots には model card がリンクする `LICENSE.txt`、LICENSE、NOTICE がいずれも存在せず、
revision 固定 HTTP は全て404だった。model card の Apache-2.0 宣言は記録するが、managed promotion /
再配布前に authoritative license text と applicable notices を bundle へ含める。

判定: source/license identity、bundle bounds、dedicated runtime、R9700 imports/default attention は
**PASS**。weight download/hash/model load/generation、VRAM/RSS/swap、quality、determinism、cancel、
Broker、installed browser、SonicForge coexistence は **NOT TESTED**。catalog は external /
experimental / low-confidence / recommended profile 0、公開 capability は unavailable のまま。
次は小さい VACE snapshot を先に download/hash し、Broker 経由 I2V gate を評価する。

最終 gate:

```text
focused                    9 passed / 1 warning
full                       702 passed / 2 warnings / 48.88 sec
compileall / diff check    PASS / PASS
installed /health          healthy / contract 2.0 / Media Forge v0.9.0
SonicForge                 sonicforge-acceptance.service active
ROCm cleanup               KFD process 0 / R9700 VRAM 59,912,192 bytes
ControlDeck slice changes  0（既存 frontend/tsconfig.tsbuildinfo 変更1件は保全）
```

## G7 V1g — Wan 2.1 VACE 1.3B bounded I2V evaluation（2026-08-26）

exact snapshot `Wan-AI/Wan2.1-VACE-1.3B-diffusers@ec4d2cb062b548996b179d493fdd05340de702a1`
を `/data1tb/mediaforge-g7-wan21-vace/hf` へ取得した。27 files / 19,043,130,596 bytes、incomplete
0件。8 inference LFS objects / 19,036,896,776 bytes は全件でsize/SHA-256が一致し、aggregate identityは
`sha256:2c488c292438aaa2914e96dea0b8cb929eda504adfb6bb583f721ea63d1be315`。

pinned Diffusers snapshotにLICENSE/NOTICEはない。official original VACE
`@574e6a744642ce3bee319afc31496b88bde8aac4` の `LICENSE.txt` は11,357 bytes、SHA-256
`c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`でApache License 2.0本文。
これをDiffusers snapshot内への同梱証拠とは扱わない。

exact local snapshot/offline-only、内部生成first-frame/mask、固定prompt/seed/preset、BF16 transformer、
FP32 VAE、model CPU offload、VAE slicing/tiling、PyTorch SDPA、silent H.264 MP4のprivate runnerと、
complete-snapshot-onlyのHost Job/Broker evaluatorを実装した。通常routing/recommended profileは変えない。

最初のload smokeはDiffusers prompt cleanerの`ftfy`不足を実検出してFAIL。partial output、lease、GPU
processは残らなかった。専用runtimeへ`ftfy==6.3.1`をpinして再buildし、size 4,691,289,880 bytes、
`pip check` broken requirements 0、R9700/gfx1201 preflight PASSを確認した。

installed v0.9.0を一時停止し、branch coreを同じ127.0.0.1:9130/data directoryで実行した。ControlDeck
code/DB/manifest変更0。Hostの既存`frontend/tsconfig.tsbuildinfo`変更は保全した。

```text
first operation / Host Job  modelop_1cc631a2db6d4feb8a12797981c23ac8 / 765f6c654597
Broker request / lease      4e3c79f5-4001-4a6d-b3a4-8d42bc0c7e5d / 234e804e-1c51-48e1-a11a-6966f4cc2b8a
preset                      256x256 / 5 frames / 1 step / 16fps / offline
core / runner / generate    264.045 / 260.206 / 258.718 sec
peak VRAM / delta           15,692,148,736 / 15,632,236,544 B
peak RSS / process swap     22,964,568,064 / 0 B
system swap page delta      in 2,890 / out 24,510
output / SHA-256            12,745 B / f216c929e95fde9aec4e99a7c10c1ef1061d9f934f232d64435db65244765077
Broker lifecycle            granted / active / renew 26 / released
```

lease release後、Qwen3.8-27B llama.cppが約30.3GB VRAM residentの状態で再要求するとoperation
`modelop_04311ee8578b4b3590997067b713ffae` / Host Job `762746655151` / request
`51e03af2-b510-4d17-b9b2-52c866b88554` は `insufficient_capacity`。worker未起動・直接競合なしで
Broker fail-closed **PASS**。実LLMを停止せず、最終利用12:22:43からControlDeckの30-minute policyを
待ち、12:53:19の自然解放後にだけ再実行した。

```text
optimized operation / Job   modelop_0c6d098f7b5e4b0981faea6206ae8c89 / 5dadb1a12ac9
Broker request / lease      58a6b7e6-0a84-42c3-afc2-da05767dce81 / 956e199a-e74f-4abc-b42a-35d6f35c55e2
bound                       max_sequence_length=128
core / runner / generate    234.486 / 213.310 / 209.625 sec（denoise 136.06 sec）
peak VRAM / delta           15,686,881,280 / 15,626,969,088 B
peak RSS / process swap     20,991,193,088 / 3,891,077,120 B
system swap page delta      in 965,924 / out 1,066,354
output / SHA-256            14,494 B / 9a5bebd61075b14d854d232d6fd1bb3f2590c180330faf3aeaff242246fdac4e
artifact                    H.264 / 256x256 / 16fps / 5 frames / 0.3125 sec
Broker lifecycle            granted / active / renew 22 / released
```

frame 0/2/4はblue panel、orange body、arms、wheels、green fieldとlocked compositionを保持し、smoke
subject stabilityは **PASS**。ただし1-step/5-frameで234.486秒、3.89GB process swap、100万超の
system swap-out pagesとなりlatency/RAM gateは **FAIL**。512x320 / 33 frames / 30 steps candidateは
採用判定を変えずswapを悪化させるため実行しない。

判定: ROCm/offline boundary、Host Job/Broker lifecycle、artifact bounds、LLM優先coexistenceは
**PASS**。candidate quality、repeat、cancel、公開Asset/provenanceは **NOT TESTED**。VACEはexternal /
experimental / low-confidence / recommended profile 0のまま **DEFERRED**、G7 V2へ昇格しない。
再開条件はprocess/system swap 0を実測できる保守可能なoffload/RAM改善または別I2V候補。T2V 1.3B
weights/partial snapshotは0を維持する。

最終 gate:

```text
focused                    32 passed / 1 warning
full                       711 passed / 1 warning / 48.38 sec
compileall / diff check    PASS / PASS
installed /health          healthy / contract 2.0 / Media Forge v0.9.0
services                   Media Forge / ControlDeck / SonicForge active
ROCm cleanup               VACE/KFD process 0 / R9700 VRAM 59,912,192 B
ControlDeck slice changes  0（既存 frontend/tsconfig.tsbuildinfo 変更1件は保全）
```

## G7 V1h — VACE prompt/model lifecycle follow-up（2026-08-26）

V1gの3,891,077,120 B process swapを追加weight/custom kernel/Host変更なしで改善した。固定prompt embedsを
GPUで生成し、UMT5/tokenizerを破棄してからmodel CPU offloadを適用すると同一SHA、process swap 0を
2回再現したが、system swap-outは5,639 / 1,921 pages残った。

VAE/scheduler/tokenizer/text encoder/transformerを公式component loaderで直列化し、text encoder破棄後に
transformerをロードした最良値:

```text
operation / Host Job         modelop_c50d8aa2472440d9b126450f67cd750f / eedcdf7b2887
Broker request / lease       7f3cfff0-c1a8-4fe3-9d20-add9c0edc9e4 / 67a50ea4-d7cd-44cd-bb35-da728fffba0a
core / runner / generate     110.622 / 108.069 / 103.037 sec
peak VRAM / delta            19,462,033,408 / 19,402,121,216 B
peak RSS / process swap      10,251,010,048 / 0 B
system swap page delta       in 70 / out 401
output / SHA-256             14,494 B / 9a5bebd61075b14d854d232d6fd1bb3f2590c180330faf3aeaff242246fdac4e
```

`device_map` direct GPU loadはpeak RSS 12,437,766,144 B、swap-out 14,940 pagesへ悪化したため除外。
V1g比でlatency/RSS/process swapは改善しdeterminismも **PASS** だが、zero system-swapは **FAIL**。
candidate quality/cancel/public assetは **NOT TESTED**、VACEは **DEFERRED** のまま。LTX-Video 2B
0.9.8、SkyReels 1.3B、Hunyuanはいずれも独自licenseの明示acceptanceなしにweight取得しない。

最終 gate は lifecycle/preflight/catalog/evaluator の focused が `32 passed, 1 warning in 5.85s`、
`./mf.sh test` が `711 passed, 1 warning in 48.28s`。対象2ファイルの `compileall` と
`git diff --check` も通過した。branch core停止後、installed Media Forge v0.9.0を復元し、
Media Forge / ControlDeck / SonicForge はすべてactive、実 `/health` はhealthy / contract 2.0、
VACE/KFD process 0、R9700 VRAM 59,912,192 Bを確認した。ControlDeck変更は0で、既存
`frontend/tsconfig.tsbuildinfo` の変更1件を保全した。

## G7 V1i — VACE VAE delayed-load comparison / G7 deferral（2026-08-26）

V1hの残存system swapに対し、追加weight、custom kernel、Host変更なしでVAEのロード順だけを比較した。
installed Media Forge v0.9.0を一時停止し、branch coreを同じ9130/data directoryで起動した。実
installed iframe identity、Host Job、Broker、R9700、SonicForge activeの経路を使った。

```text
                              VAE delayed load                   V1h control
operation                     modelop_2caa9d49a5f24be69d69f8bb49a36d1f
                                                                modelop_1954e9cd95c94d6fa612a6f7c5038acd
Host Job                      8697762eb240                      d50b0d07bda3
core elapsed                  111.829 sec                       110.931 sec
peak RSS / process swap       10,430,042,112 / 0 B              10,245,021,696 / 0 B
peak VRAM / delta             22,179,917,824 / 22,120,005,632 B 19,462,152,192 / 19,402,240,000 B
system swap in / out          123 / 3,597 pages                 9,748 / 2,977 pages
output                        14,494 B / H.264 / 5 frames       same
SHA-256                       9a5bebd61075b14d854d232d6fd1bb3f2590c180330faf3aeaff242246fdac4e
```

遅延loadはRSS、VRAM、swap-outの全てで対照より悪く、コード差分を戻した。Diffusers 0.40.0の
group/disk offloadは利用可能だが、1-step denoiseが約51秒のVACEで各blockを30 steps再転送する経路は
実用latencyを改善しない。専用runtimeにはTorchAO / bitsandbytesがなく、ROCm/gfx1201で検証済みの
量子化backendも確認できないため追加しなかった。

判定は **DEFERRED**。V2〜V4、candidate quality、cancel、公開Asset/provenanceは **NOT TESTED**。
通常video capability、catalog state、recommended profileは変更しない。再開条件は明示license acceptance
済みの軽量候補、またはzero-swapと実用latencyを同時に満たす別のpermissive候補。評価後はbranch coreを
正常停止し、installed v0.9.0を復元した。Media Forge / ControlDeck / SonicForgeはactive、実healthは
healthy / contract 2.0、VACE/KFD process 0、R9700 VRAM 59,912,192 B。試験用`mf-e2e` password hashは
各run後に元値へ復元し、新規browser sessionをrevokeした。ControlDeck code/manifest変更0、既存
`frontend/tsconfig.tsbuildinfo`変更1件は保全した。

最終 gate はVACE runner focused `6 passed, 1 warning`、`./mf.sh test`が
`711 passed, 1 warning in 48.01s`、`git diff --check`がPASS。採用コード差分は0件。

## G8 B0 — pinned Blender runtime / license boundary（2026-08-26）

実機にはsystem Blenderが無かったため、ControlDeck、core venv、ML runtimeへ依存を追加せず、公式
Blender 4.5.9 LTS Linux x64 portable archiveを専用runtimeへ明示provisionした。

```text
archive                     blender-4.5.9-linux-x64.tar.xz
download / SHA-256          377,929,956 B / dcdc3eca6c9825bb35a8033b689c053f3cb5a9b0cd2a61b2eac2a49436b4ad3d
archive safety              6,510 members / extracted payload 1,168,332,002 B
runtime total               1,546,263,669 B
Blender / embedded Python   4.5.9 / 3.11.11
real preflight              background=true / glTF import=true / export=true
status                      0.21 sec / max RSS 264,380 KiB
ready build                 0.21 sec / max RSS 272,104 KiB / reused=true
```

installerはexact HTTPS host/name/size/hash、単一top-level root、relative contained link、member count、
展開sizeを強制し、device/FIFO/escapeを拒否する。stagingで実preflight後だけatomic installし、runtime rootは
repository `runtimes/`配下に限定する。preflightは固定 `--background --factory-startup --disable-autoexec
--python <trusted-file>` のみで、temporary HOME/XDG/Blender user dirsを終了時に削除する。`--python-expr`、
chat script、root installは実装していない。

Blender/bpy workerはGPL-3.0-or-later境界として分離した。Blender binaryはrelease bundleへ同梱せず、
生成assetのlicenseをGPLと記録しない。focused installer testsは10件PASS。B1以降のGLB import、compile、
asset/provenance、preview、timeout/cancel、installed browser/agentは **NOT TESTED**。

実行後Blender process 0、R9700 VRAM 59,912,192 B、Media Forge / ControlDeck / SonicForge active、
installed healthはhealthy / contract 2.0。ControlDeck code/manifest変更0、既存
`frontend/tsconfig.tsbuildinfo`変更1件を保全した。

最終 gateはfocused `10 passed, 1 warning`、full `721 passed, 1 warning in 46.48s`、Python
`compileall`、`bash -n mf.sh`、`git diff --check`がPASS。

## G8 B1 — bounded GLB import / independent validation（2026-08-26）

public Asset MIMEへ `model/gltf-binary` を加法的に追加し、`purpose=source` の browser / workspace
byte transportから単一GLB 2.0をimportできるようにした。filenameやpathは入力せず、元bytesを変更せず
hash/storeする。Blenderと独立したcore validatorはmagic/version/declared length、JSON/BIN chunk、
UTF-8/finite JSON/depth/value count、top-level count、bufferView/accessor range、mesh/node/scene reference、
external buffer/image URI、required extensionをboundedに検査する。未計測のrequired extensionとsparse
accessorはB1ではfail-closed。

コード生成した第三者asset非依存のtriangle GLBは620 B。一時data rootと実Uvicorn
`127.0.0.1:9160`に対するHTTP importは201を返し、Asset/contentのSHA-256はともに
`29e22906825ae044e2b37aee45e767f6f253227e9f5b8e2f50b281fbddec4e5f`。provenanceは
`asset.import` / `user-provided` / `validator.glb=1.0.0`、scene/node/mesh/primitives=1、
accessor/bufferView=2を返し、source filename/pathは含まなかった。破損bodyは422
`invalid_glb_import`、失敗後work entry 0。サーバ停止後に一時data rootを削除し、port 9160の
listenerも0。

focused GLB tests 10件はPASS。Blender re-import、Host `grant:` read、installed-host browser、B2 compile /
preview / package / cancelは **NOT TESTED**。ControlDeck code/DB/manifestは変更していない。
最終gateは `./mf.sh test` が `731 passed, 1 warning in 47.16s`、Python `compileall`、
`node --check frontend/app.js`、`git diff --check` がPASS。

## G8 B2 — deterministic Blender compile package（2026-08-26）

既存 `asset.pack` にcanonical `profile=3d.project.glb` を加法し、1件のGLB Assetから
`asset.glb` / `manifest.json` / `preview.png` の3 entry ZIPを作る固定経路を実装した。
G1のprofile regexは先頡英字だけで計画済みIDを受理できなかったため、既存値を壊さない
加法的変更として先頭数字を許可した。それ以外のpattern、path、operator、scriptは許可しない。

coreが起動できる子processは次の固定形だけ。request/resultもjob root内の固定名で、
workerは入出力filenameとexact fieldを再検査する。

```text
blender --background --factory-startup --disable-autoexec \
  --python worker_packs/blender/compile_asset.py -- \
  --request request.json --result result.json
```

temporary HOME/XDG/Blender user dirs、`LIBGL_ALWAYS_SOFTWARE=1`、GPU visibility空、process group
timeout/cancel、stdout/stderr各256 KiB上限をcoreで強制する。workerはcamera/light/text/driver/
custom propertyを除去し、MESH/EMPTY/ARMATURE以外をreject、meter/Y-up・finite transform・
transform apply・normal inspection・orphan purge後にGLBを書き出す。previewは固定Workbenchで描画し、
Blenderが付けるDate/RenderTimeなどのancillary PNG metadataを除いてから独立検査する。

最終CPU-only設定の別process 2回は1.19 / 1.01 sec、max RSS 652,092 / 658,288 KiB。
生成triangleのhashは次の3件で完全一致した。Eeveeとmetadata未正規化Workbenchはpreview
hash不一致のため不採用。assertionは緩めていない。

```text
asset.glb    8135b0ea92cdfa047a8eeaf11bbd8a5ff634f0086696d40aaf1e05438c450868
preview.png  6dc759022f4cc116e0ce216483962c4db63efb844ad06f0b320352ac357b046f
ZIP          aaa87f7fe6fdb5873360e60749208b68c0f9fad1d52bce8042a9013edf3740e3
```

最終コードの実Uvicorn `127.0.0.1:9160` でJob APIを2回実行し、job
`job_7af008abcb38430fbff26fc2ed3548cb` / `job_1b30c0e07fb64a238b864f18201ce306` は両方
succeeded、ZIP hashも上記と一致しbyte-identical。実行後work entry 0、Blender process 0、
R9700 VRAM 59,912,192 B。一時data rootはtrashへ移動し、port 9160 listenerも0。

focused B2 tests 5件はpackage metadata/order、2回hash、Asset/provenance、任意option reject、
failure/cancel partial asset 0、trusted commandをPASS。実process cancel/timeout、installed Host Job phase、
browser/agent/grant、B3 optionは **NOT TESTED**。
最終gateは `./mf.sh test` が `736 passed, 1 warning in 50.77s`、Python `compileall`、
`node --check frontend/app.js`、`git diff --check` がPASS。

## G8 B3 — typed production options（2026-08-26）

`constraints.compile_options` にprivate versioned `3d.compile-options@1` を追加した。Pydanticとtrusted
Blender workerの両方がexact fields/type/boundsを検査し、unknown field、`apply_transforms=false`、
非降順LOD、budget 12未満、任意operator/script/pathをrejectする。compile optionを省略した
B2 requestは既存の固定defaultと同じ。

```text
apply_transforms       true固定
repair_normals         bool
remove_degenerate      bool
merge_by_distance_m    null or 0.0000001..1.0
triangle_budget        null or 12..200,000
lod_ratios             0..3件 / 0.05..0.95 / strict descending
collision              none / box / convex_hull
materials              preserve / basic_pbr
preview                fixed_workbench固定
```

workerはmesh edit、triangle budget、material単純化、LOD mesh、collision proxyを明示option時だけ
実行し、manifestの固定10 operationそれぞれに `parameters/results/warnings` を保存する。
コード生成material cubeで全optionを別process 2回実行し、base 12 triangles、LOD 6、box
collision 12、material changed 1、最終scene 30 triangles / 21 vertices / 3 meshes。hashは次の3件で
byte-identical。

```text
asset.glb    908d3fb060e268c9b1321aca2eb7e476b91cad4d27b4e59aba2b6a15155ba48e
preview.png  3832e4195bf68fb6a8af843102e3ac48319a345177028699b921b7c78292411a
ZIP          e2b9994cde08796f5d51b7f057c7be832cb2ea4b3f3632f8a4e79cece987e3f2
```

repair fixtureはmerge 1e-6 m + degenerate removal + normal repairで4→3 vertices、2→1 triangles、warning 0。
cube convex hullは8 vertices / 12 triangles。triangle budget上限はコード生成3,625,792 B gridで
推測でなく測定した。200,978→199,999 triangles、別process 2回は2.09 / 2.03 sec、max RSS
880,552 / 887,708 KiB、GLB SHA
`d19346f5f044dc9eca525d75958264ae53bea7b8a937e89a896a87b46a20e853`、ZIP SHA
`f98ef70872f2dd40983016f62b5b5b43a57b41f0592f845a4f806be6d128c99b`で完全一致。

focused B3/schema/job testsは9件PASS。実installed Host/browser/agentのoption入力、real cancel/timeout、
rig/animation付きassetは **NOT TESTED**。
最終gateは `./mf.sh test` が `740 passed, 1 warning in 54.70s`、Python `compileall`、
`node --check frontend/app.js`、`git diff --check` がPASS。

B3はsoftware rendering + GPU visibility空で実行し、Qwen/llama processには触れていない。最終確認時、
先行していたtransient `sonicforge-acceptance.service` は14:52:03にexternal操作でsuccess停止・unit削除済み。
代わりにPID 2116151/2116153が `/tmp/cd-sf-catalog-v010-acceptance/.../sonicforge-core serve`
としてport 9140で稼働し、healthは `setup_required` / contract 2.0、Qwen/llama process 0。
このexternal SonicForge acceptance環境は変更・停止していない。

## G8 B4 — workspace / agent / project placement（2026-08-26）

Blenderをrequest時に起動しないexact stamp / executable / trusted worker確認をcapability
`asset.3d_project_pack`へ追加した。Createはruntime ready時だけGLB選択を表示し、Simpleではasset選択後だけ
「プロジェクト用ZIPを作る」を表示する。AdvancedはB3の型付きfieldだけへ到達し、Simpleへ戻した場合は
hiddenだったAdvanced値を送らず固定defaultへ戻る。公開jobは既存 `asset.pack` +
`profile=3d.project.glb`、Agentは既存 `media.generate`、配置は既存 `media.pack` のままで、raw project /
Blender path、operator、script bodyは追加していない。

Library投影へpreview種別とsuggested filenameを加えた。3D packageはZIPをfilesystemへ展開せず、entry順を
`asset.glb` / `manifest.json` / `preview.png` に固定し、暗号化、member count、展開後合計128 MiB、manifest
1 MiB、preview 8 MiB、manifest schema/profile/preview size/hashを検査してからpreview bytesだけをWebPへ
変換する。`../escaped` を含むarchiveはrejectされ、外部file作成0。画像でも3D packageでもないassetは
thumbnail HTTPを要求しない。単体表示もembedded transportと同じLibrary投影を使う。

実Uvicorn `127.0.0.1:9162`、一時data root、実Blender 4.5.9、実Chromiumで620 B triangle GLBを選択した。
Simpleで未選択時action非表示、選択後表示、Advancedでnormal repair / degenerate removal / merge 1e-6 m /
triangle budget 12 / box collision / basic PBRを入力し、browserが送ったexact typed requestをassertした。
job `job_a90bb3d8adee4db79b6e3265e60b2386` は0.727 secでsucceededし、40,603 B ZIP Asset
`asset_393d4c4a6db44bdeb217e9b621647539`、SHA-256
`adb22b8daadd6aae5c14b79460d4d774dcc8588ff213afdf5bd7b7b696d7ae3e` を登録した。Library cardは
`data:image/webp;base64,` preview、viewerは `ZIP · プレビュー`、console/page errorは0。スクリーンショットは
15,144 B。GLB選択後のSimple表示は320px viewportでhorizontal overflow 0。終了時core healthはhealthy /
contract 2.0、work entry 0、Blender child 0、port 9162 listener 0。

Host stubを使うfocused contractでは、同じ3D requestを既存Agent generateへ渡し、embedded WebSocket
Library cardのWebPを取得後、既存Agent packで `project-ready.zip` を `grant:export-1`へcommitした。
receiptは `application/zip`、payloadはZIP magic、tmp/repository path leak 0。hostile ZIP、capability
stamp fail-closed、Simple/Advanced disclosure、Agent/Library/placementを含むfocused 200 testsはPASS。
実installed ControlDeck browser/identity/Host Job/real grant、real Agent Blender execution、reconnect、
cancel/timeout、rig/animation付きassetはB5として **NOT TESTED**。

最終gateは `./mf.sh test` が `746 passed, 1 warning in 48.51s`、Python `compileall`、
`node --check frontend/app.js`、`git diff --check` がPASS。ControlDeck code/DB/manifest変更0、既存
`frontend/tsconfig.tsbuildinfo`変更1件は保全した。installed Media Forgeは127.0.0.1:9130でhealthy /
contract 2.0、R9700 VRAM 59,912,192 B、Qwen/llama process 0。SonicForge 9140はexternal変更により現在
healthy / contract 2.0（Speech Essentials/Music ok、Game Audio missing）であり、このsliceでは変更していない。

## G8 B5 — installed ControlDeck acceptance（2026-08-26）

実installed ControlDeck、branch core、実Chromium、実Blender 4.5.9でB5を完了した。workspaceへ
browser bytesとHost file pickerの両方から3,625,792 B / 200,978-triangle GLBをimportし、Asset
`asset_ecbc752b93624c31a19b7434a32fbb89` / `asset_6ce100e79154436199748fd798788674` は入力と同じ
SHA-256 `4e4e65714e409e34d18b3be5e21cc39eddee6e3eca6467e292846801ca13c04c`。Host picker経路は
opaque `grant:` IDだけをprivate workspace transportへ渡し、Host pathを送受信しなかった。

workspace job `job_2eed58a192c149ea92dab25c57a23f38` は実行中reload後の再接続でも`running`を観測して
succeeded。Agent Host Job `c43db95ba470` もsucceededし、Host最終phaseは`package`、progressは
1000/1000、event 1件。両経路の別Blender processが作ったZIPはbyte-identicalだった。独立検査値は次の通り。

```text
source GLB     3,625,792 B  4e4e65714e409e34d18b3be5e21cc39eddee6e3eca6467e292846801ca13c04c
package ZIP      919,412 B  8568abd66b538f543b2a9a95993e5caa07a841b7f0a68f4696fe0c4debc5424e
asset.glb      4,815,840 B  0b1e065062f160a4f668dc000e0d860a08226da6b039f7134931b01e782f775a
preview.png       36,338 B  26d07b3311c80ab56feb2dda838e033a7c347d4eb2a02528543a1143867e6cc0
manifest facts  triangles=200,000 / vertices=100,627 / bounds=[0,0,0]..[317,0,317]
```

Libraryは実previewを表示し、browser console/page errorは0、screenshotは108,791 B。Agent packは
Host asset `asset:fe47805b-72ea-49dd-b882-16415862f24e`へ919,412 Bをcommitし、receiptと実committed
bytesのSHA-256はZIPと一致した。

Host cancel job `64c1e07551e5` は実Blender child PID 2235001を観測後canceledへ収束し、child 0、partial
asset/work 0。CPU-only `asset.pack`中のHost cancelをGPU lease taskに依存せずpollするよう修正し、実行中の
ControlDeck resource request増分は0だった。`MEDIA_FORGE_BLENDER_TIMEOUT_SEC=0.05`の別processではjob
`job_d7ef5e588ea04ea489db073afe9b5bdf` が0.070 secでfailed、errorは`blender_compile_failed` /
`Blender compiler exceeded the 0.05 second timeout`、asset/work 0、coreはhealthy。

永続store `/tmp/mediaforge-g8-b5-recovery-R3jDf5` では、core停止中にqueuedだった実Blender job
`job_1d07586985694ff786a95d0fcf506129` が再起動後succeeded。別job
`job_7b8a1398f19d4ce898a3ab22a7ec0056` は`running` / phase `validate`で、service cgroup内の実Blender
PID 2236235をsystemdのkill記録で確認して
service cgroupをSIGKILLし、DBにrunningのまま残ることを確認した。同じstoreで再起動するとfailed /
`service_restarted` / asset 0へ収束し、work file 0、health healthy。

実project placementでHostの中央stagingとgrant先が別filesystemの場合に`os.replace`が`EXDEV`となる
generic境界不具合を観測した。Media Forge側ではraw pathを受けず、Hostのatomic commit契約も弱めず解けないため、
ControlDeck別PR #246でgrant先directory内tempへのcopy、fsync、同一directory内no-overwrite atomic publishへ修正した。
exact head `2cdc1cd264ed777651c5c0ba8af9ffbf2a473261`、merge commit
`8a6fc31d748c789b131282911e49a131ae03ff8d`。ControlDeck focused 31件はPASS。fullは814 passed / 1 skipped /
5 failedで、4件は共有Host Job active-limit状態、1件は固定1秒のresource timingであり、各該当testはclean
processまたは単独実行でPASSした。Media固有route/dependency/文言はHostへ追加していない。

schema discoveryでroot `type`を要求する実Hostに合わせ、placement schemaへ`type: object`を追加した。
各`oneOf` branchは既にobject限定のため受理集合は変わらない。Host progressのforced final updateがrate gate
境界で自己rejectした実raceは10 ms safety marginで修正した。

終了時、導入済みMedia Forge v0.9.0をsystemd PID 2237186/2237197で127.0.0.1:9130へ復元しhealth
healthy / contract 2.0。SonicForge 9140は変更せずhealthy（Speech Essentials/Music ok、Game Audio missing）。
実Blender process 0。rig/animation付きassetは **NOT TESTED** であり、静的mesh profileの対応範囲へ含めない。

最終gateはfocused 200件、`./mf.sh test` 750件がPASS（既知のStarlette warning 1件 / 50.23s）。
Python `compileall`、`node --check frontend/app.js`、`git diff --check`もPASSした。

## Mobile Create media switch（2026-08-26）

利用者の明示要求により、Create最上部へ「画像を作る／動画を作る」の2択segmented controlを追加した。
390pxと320pxでは全幅2列、各touch target高さ44pxで、server-side preference `create_media` に選択を
保存する。画像側の既存挙動は維持し、動画側はpromptと任意の元画像を表示する。これはtimeline型の動画編集器では
なく、元画像なしは`video.text_to_video`、1件ありは`video.image_to_video`へ対応する生成面である。

現在の公開capabilityは両方とも`unavailable / video_runtime_not_adopted`。動画面への切り替えと入力は可能だが、
実行ボタンを「動画は現在利用できません」として無効化し、理由と設定へのexitを表示する。capabilityを
`experimental`または`available`として受け取った場合だけ、既存公開契約`video.generate`、MP4、count 1、
`local_only=true`を送る。元画像ありではimport済みopaque asset IDをinputsへ1件入れ、pathやmodel名は送らない。

実standalone Chromiumで390px / 320pxを確認した。horizontal overflowは両方0、390pxの各切り替えは
176x44px、320pxは141x44px、browser console/page errorは0。unavailable時の理由表示、実行不可、設定exitを
assertした。テスト内でcapability documentだけを`experimental`へ置き換え、text-to-videoではinputs 0件、
image-to-videoではinputs 1件となるexact requestを捕捉した。

導入済みControlDeckの実mobile shellでも、branch coreを一時的に127.0.0.1:9130へ接続して同じUIを確認した。
390px / 320pxのhorizontal overflowは0、touch targetは176x44px / 141x44px、console/page errorは0。
終了後はbranch coreを停止し、導入済みMedia Forge v0.9.0を127.0.0.1:9130へ復元した。

focused frontend/API/schema/video testsはPASS。最終gateは`./mf.sh test`が
`751 passed, 1 warning in 54.86s`、Python `compileall`、`node --check frontend/app.js`、
`git diff --check`がPASS。実動画runtime、weight取得、GPU動画生成、出力再生品質、timeline編集は
**NOT TESTED**。Tencent licenseへの同意・利用開始は行っていない。ControlDeck code/DB変更0、既存
`frontend/tsconfig.tsbuildinfo`変更1件は保全した。

## v0.9.1 release / installed video-screen reachability（2026-08-26）

利用者が実ControlDeckから動画生成面へ到達できないことを報告した。稼働processは
`versions/0.9.0/bin/mediaforge-core`、配信HTMLに`create-media-switch`は無く、原因はmerged UIを含まない
旧bundleへ復元したままだったことであり、Host routeやcapability gatingの不具合ではなかった。

versionを`addon.json`と`mediaforge.__version__`で0.9.1へ揃え、Media Forge #147（exact head
`f7f42c7af6e34420d2dba4017f733a6f4d58c8c7`、merge commit
`cc3f342d77a20e98d95fcc43d276e1aafdcd8d94`）をmergeした。同じmerge commitをtag `v0.9.1`として
bundleを構築・署名・公開した。

```text
artifact   control-deck-media-forge-0.9.1-linux-x86_64.tar.gz
bytes      30,954,097
SHA-256    ae9087ca6f1548260dd69f980face65cde003f380f8fa74488e68b4d8d098bf2
manifest   275 B / signature 89 B
release    https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.9.1
```

公開releaseから別fileへ再downloadし、30,954,097 Bと同じSHA-256を確認した。展開した配布binaryの
`doctor`は`version=0.9.1 / packaged=true`。別port 9166で起動したbundleはHTMLに切り替えを含み、
両video capabilityを`unavailable / video_runtime_not_adopted`として返した。

実ControlDeckの標準`./deck.sh feature update media-forge`は11.89秒、max RSS 783,412 KiBで成功し、
結果は`version=0.9.1 / previous_version=0.9.0 / healthy`。`current`は`versions/0.9.1`を指し、
rollback用0.9.0も保持した。0.9.0 / 0.9.1 version treeは31,082,798 B / 31,222,710 B、永続
feature-dataは78,755,964,188 B、Asset APIは18件。終了時service PID 2325466/2325471、9130 healthは
`healthy / contract 2.0`。

実ControlDeckへ短命test identityでloginし、route `/x/media-forge/workspace/create`のopaque iframe内で
「動画を作る」を押して動画面へ到達した。390px / 320pxの各touch targetは176x44px / 141x44px、
horizontal overflow 0、browser console/page error 0。理由は「実用条件を満たす動画モデルがまだありません。」、
submitはdisabledだった。これは導線のPASSであり、実動画runtime/weight/GPU生成/品質/timeline編集は引き続き
**NOT TESTED**。license同意・モデル取得は0。ControlDeck code/DB schema変更0、既存
`frontend/tsconfig.tsbuildinfo`変更1件は保全した。

release前gateはfocused 199件と`./mf.sh test` 751件がPASS（既知warning 1件 / 53.52s）。GitHubの
required checkは設定0件だった。

## v0.9.2 video model management clarity（2026-08-27）

実ControlDeck v0.9.1の`/x/media-forge/workspace/create`から動画面、設定exit、動画候補filterまでを
短命test identityで再現した。候補12件は表示されたが、導入済みWan TI2V／MiniMax H3 GGUFだけが削除可能、
未導入候補は外部管理または容量超過であり、操作不能理由がhover titleに隠れていた。また導入済み未採用状態を
「要確認」、Create側を「実用条件を満たす動画モデルがまだありません」と表示していたため、利用者からは
追加・削除機能が無く、license acceptance不足で生成不可に見える状態だった。

設定contributionとPCヘッダの入口を「モデル管理」と明記し、動画filterで候補／導入済み／追加可能／削除可能の
件数を表示する。各行は`導入済み・利用可/利用不可`を区別し、外部管理・容量超過の理由をtouchでも常時読める
本文にした。Createは導入済み動画モデルを検出した場合、モデル不足とは言わず「実用品質とメモリ安全性を
満たした実行環境が未採用」と説明する。license acceptanceはexact checkpointのdownload許可であり、runtime
採用ではないことも動画filterへ明記した。

CogVideoX-2Bは13,775,572,738 bytes、exact revision、LICENSE、必須file、全weight size/SHA-256が閉じ、
32,000,000,000 bytes未満のmanaged installer条件を満たすため、checkpoint ownershipだけを`managed`へ変更した。
これにより現在の動画filterは候補12／導入済み2／追加可能1／削除可能2となる。CogVideoXのdownload/removeは
可能になるが、R9700評価でaction adherence、latency、system swap gateを落としているため`experimental`、
healthy=false、recommended 0、公開video capability unavailableは維持する。download操作の横にも、取得だけで
動画生成は有効にならないと表示する。

focused frontend/catalog/manager/transportは211件、その後catalog/manager/frontendは155件がPASSした。
最終`./mf.sh test`は751 passed / warning 1件 / 51.73秒。branch coreを実feature-dataへread-only相当で
別port 9131起動し、standalone Chromium 1280px/320pxで上記件数、CogVideoX download表示、理由本文、横overflow 0、
console/page error 0を確認した。既存Wan/H3 modelは削除していない。

Media Forge #149（exact head `cb3e760d9e1e7339e1ae921568a9cd025c79181b`、merge
`0d69a24abfc7389424cc09901e7de760bd1b7af7`）をmergeし、同じmerge commitをtag `v0.9.2`として
bundleを構築・署名・公開した。署名はmanifestのexact bytesに対してEd25519検証した。公開Releaseを
別のtemporary directoryへ再downloadし、local buildと同じ30,866,305 bytes、SHA-256
`61a0a41ef3a068625ca3068634fa4bdb3d3b655005a00d6cda571d707d490c55`を確認した。manifestは275 bytes、
signatureは89 bytes。展開binaryの`doctor`は`version=0.9.2 / packaged=true`。別port 9166のbundleは
CogVideoXを`managed / installed=false / experimental`として返し、320px Chromiumで追加可能表示、
横overflow 0、console/page error 0だった。

実ControlDeckの標準`./deck.sh feature update media-forge`は14.22秒、max RSS 786,400 KiBで成功した。
`version=0.9.2 / previous_version=0.9.1 / healthy`、`current`は`versions/0.9.2`、rollback v0.9.1を保持。
version treeはv0.9.1が31,222,710 bytes、v0.9.2が31,133,110 bytes、永続feature-dataは
78,755,927,268 bytes。9130の実processはPID 46572、exact v0.9.2 binary、health healthy / contract 2.0。

短命test identityで実ControlDeckのopaque iframeを1280px/320pxで操作した。Createは「動画モデルは
導入済みだが実用品質とメモリ安全性を満たす実行環境が未採用」と表示し、設定exit後は動画候補12、
導入済み2、追加可能1、削除可能2を表示した。CogVideoXにはダウンロードbuttonと「取得だけでは生成は
有効にならない」の本文、Wan TI2V／H3 GGUFには`導入済み・利用不可`と削除buttonを確認した。
320pxの横overflow 0、両幅console/page error 0。公開capabilityはT2V/I2Vとも
`unavailable / video_runtime_not_adopted`のまま。

CogVideoX 13.8GBの実managed download/removeは、既存外部evaluation snapshotを変更しないため
**NOT TESTED**。既存snapshot 18,734,841,514 bytesとpartialを移動・削除していない。production動画生成も
不採用gateを維持して **NOT TESTED**。Release: https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.9.2

## LoRA zero-config base routing（2026-08-27）

LoRA は単体生成モデルではなく、互換する base checkpoint が必要である。旧UIは不足時に
「土台も一緒に取り込む」チェックと別downloadを要求し、生成時も手動checkpoint選択へ
候補を従属させていた。さらにcustom Civitai entryのsourceを`huggingface`と保存していたため、
登録後の実download URLが誤っていた。

LoRA resolveは不足するbaseをexact revision・license・bytes込みのdependencyとして返す。
UIはLoRAとdependencyの条件・合計容量を1回で確認し、1回の`models.custom.add`でcatalogを
atomic更新して両方のmanaged downloadを開始する。baseはinstall後に同じ要求の後続処理で
自動評価する。Createはinstalled LoRAをmanaged catalogでも`kind=lora`として認識し、LoRAを
選ぶと手動model指定をautoへ戻す。core routingは選択LoRAの正規化familyをhard constraintにし、
異系統混在をworker起動前に拒否する。trigger word自動追加とprovenance上のresolved modelは維持した。

実Civitai APIで`civitai/58390`をread-only resolveした結果、revision `62833`、
`lora.diffusers`、base `SD 1.5`、37,861,176 bytesと観測した。手元にbaseが無い条件では
DreamShaper `civitai/4384` revision `128713`、2,132,625,894 bytesをdependencyとして解決した。
検索APIではDetail Tweaker XL `civitai/122359` revision `135867`、base `SDXL 1.0`、
228,452,344 bytesも観測した。重みdownloadは利用者による当該配布条件の同意前なので開始していない。

focused 6 filesはPASS。最終`./mf.sh test`は757 passed / warning 1件 / 64.13秒。
release bump後の再実行も757 passed / warning 1件 / 55.35秒。

Media Forge #151（exact head `e321755890fd013acf14b90263d5e77fa8cd1e18`、merge
`963f26712e513515ef02b75aa249c4bab34e392c`）とv0.9.3 release #152（exact head
`7c80970267521b69910f17495e3444d1717c1898`、merge/tag
`db4eddd77cde5c2349b5ba80872832ce815f2495`）をmergeした。bundleは30,957,893 bytes、
SHA-256 `41d7d392dba52527bfa8a11506eaeb0c83489926a01ea196085275389d70d397`。
公開Releaseを別temporary directoryへ再取得してhash一致、manifest 275 bytes、signature 89 bytes、
trusted publisher公開鍵によるEd25519検証成功を確認した。

実ControlDeckの標準`./deck.sh feature update media-forge`は13.15秒、max RSS 786,640 KiB、
swap 0で成功した。`version=0.9.3 / previous_version=0.9.2 / healthy`、`current`は
`versions/0.9.3`。実process PID 159617/159621のうち159621が127.0.0.1:9130をlistenし、
healthはhealthy / contract 2.0。v0.9.3 version treeは31,225,870 bytes、永続feature-dataは
78,755,927,268 bytesで変更していない。

短命identityで実ControlDeck opaque iframeを操作した。1280pxでLoRA検索結果
`civitai/58390`、不足baseの「必要な土台も自動でダウンロードします」、単一の
「同意してダウンロード」、旧`lora-base-together` 0件を確認した。1280px/320pxとも
horizontal overflow 0、console/page error 0。短命sessionは終了時にrevokeした。

当該配布条件の同意ボタンは押していないため、実LoRA weight downloadとsame-seed適用比較は
**NOT TESTED**。これはライセンス未同意を成功扱いしない境界である。2026-08-25のSD1.5/SDXL
実weight適用証跡は維持する。Release: https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.9.3

## Civitai LoRA/DreamShaper registration repair（2026-08-27）

利用者が実ControlDeck v0.9.3でCivitaiのLoRAと自動base DreamShaperを導入しようとすると、
「導入できない」と表示された。永続状態をread-only調査したところ、16:25の試行後も新規
model operationは0件で、custom catalogにもCivitai entryは残っていなかった。download開始前の
catalog parser rollbackである。

実Civitai exact revision `civitai/58390@62833`（LoRA）と`civitai/4384@128713`
（DreamShaper）をtemporary catalogへ組むと、最初に`model registry identity is invalid`を再現した。
source parserはCivitaiの数値versionを許可していたが、runtime descriptorだけ40桁Git commit固定だった。
`civitai/<number>` namespaceに限って1〜12桁の数値versionをimmutable runtime identityとして許可した。
generic repositoryの40-hex制約は維持する。

続いて単一SafeTensor配布の`required_files=[]`を拒否する不整合も再現した。weightsは従来どおり
非空、正のsize、公開SHA-256必須のまま、追加config fileだけ空を許可した。修正後、live Civitai
metadataから組んだtemporary registryはLoRA `62833 / lora.diffusers / SD 1.5`とDreamShaper
`128713 / diffusers.sdxl-single-file / SD 1.5`の2件をparseし、installed=falseとして返した。
重みdownloadは行っていない。

focused 6 filesはPASS。最終`./mf.sh test`は759 passed / warning 1件 / 51.13秒。
release bump後の再実行も759 passed / warning 1件 / 52.19秒。

Media Forge #154（exact head `240beeaccac8730d49b2af5bdf696f95a0f3dc07`、merge
`0965efe5f51daa7869a338c6ddcedcb2304c36d5`）とv0.9.4 release #155（exact head
`4e9629c`、merge/tag `9fc7793a1dc7e1a7c673aecc35dfad090ef25c98`）をmergeした。
bundleは30,959,024 bytes、SHA-256
`cec0920bb79dd0179965d2ecc6f220fbed477348c8a4c915b719ec77e5d59093`。公開Releaseを
別temporary directoryへ再取得してhash一致、manifest 275 bytes、signature 89 bytes、Ed25519
検証成功を確認した。

実ControlDeckの標準updateは16.68秒、max RSS 786,880 KiB、swap 0で成功した。
`version=0.9.4 / previous_version=0.9.3 / healthy`、`current=versions/0.9.4`、PID
181500/181506、127.0.0.1:9130、contract 2.0。v0.9.4 treeは31,226,582 bytes。

短命identityで実installed iframeを再確認した。1280pxで`civitai/58390`を検索・resolveし、
DreamShaper dependency、自動base本文、単一の「同意してダウンロード」を確認した。1280px/320px
ともhorizontal overflow 0、console/page error 0。sessionはrevokeした。同意ボタンは押しておらず、
07:00 UTC以降のmodel operationは0件、weight download 0。利用者がUIから再同意して初めて実取得を
開始する。Release: https://github.com/souten-yd/ControlDeckMediaForge/releases/tag/v0.9.4
証跡更新後のexact main gateは`./mf.sh test` 751 passed / warning 1件 / 54.52秒、`git diff --check` PASS。

## 使うモデルの常時表示と LoRA 互換ゲート（2026-08-28）

利用者から実機 v0.9.4 の「画像を作る」で、モデルが FLUX.2 Klein 4B のまま LORA 欄に
`civitai/16014 SD 1.5 lineart monochrome` が並び、未チェックなのに強さのスライダーが 1.00 で
出ている、という指摘を受けた。FLUX.2 Klein 4B は catalog 上 `supports_lora=false` で LoRA 系統も
持たないため、この組み合わせは成立しない。

まず「おまかせ」が実際に変わるのかを read-only で確認した。`routing/router.py` の `route()` は
capability → hardware backend → installed/local path → `state==available` かつ healthy →
`measured_vram_bytes <= free_vram_bytes` → 要求 domain 一致（fail-soft）→ `policy_rank[policy]` →
model_id の順で絞る。仕組みとしては変わるが、`worker_packs/image/models.json` で image の
`available` は `black-forest-labs/FLUX.2-klein-4B`（auto 10）と `segmind/SSD-1B`（auto 50）の
2 件だけである。さらに `custom_models.py` は利用者追加モデルへ
`policy_rank {"auto": 1000000}` を与え、`record_measurement()` は `state` を `available` へ上げても
`policy_rank` を更新しない。よって利用者が自分で入れたモデルは auto で選ばれ得ない。
「おまかせは事実上ほぼ固定」であり、選択を常時出すという利用者の条件が成立する。

frontend だけを変更した。使うモデルは常時見える単一 select（先頭が「おまかせ（自動で選ぶ）」、
以降は導入済み・healthy・`kind != lora` の image 土台）にした。LoRA 選択中に手動指定を黙って
auto へ落とす旧挙動をやめた（`jobs.py` の `_resolved_loras()` が既に系統不一致を
`lora_incompatible` で日本語表示する）。LoRA 一覧は `loraTargetFamily()` で絞り、土台指定時は
`supports_lora=false` なら候補 0 件、それ以外は `normalizeFamily` 一致のみ。強さのスライダーは
チェック済みの行にだけ描画し、未使用行は 1 列 grid にした。土台変更で載らなくなった選択は外し、
外した件数を 1 行で知らせる。backend/API/契約は変更していない。

実 Chrome（Chrome/151.0.7922.169、headless、CDP、390x844 mobile emulation）で
`http://127.0.0.1:9131/` の実 build を操作し、SD 1.5 / SDXL 1.0 の LoRA を catalog へ足して
実機の状況を再現した。観測は以下のとおり。

```text
おまかせ    : select=(auto) 非 hidden、候補 3（おまかせ / FLUX.2 Klein 4B / Segmind SSD-1B）
              LoRA 2 行とも未チェック・スライダー無し、payload {}
FLUX.2 指定 : payload {"model_policy":"manual","model_id":"black-forest-labs/FLUX.2-klein-4B"}
              LoRA 行 0 件、「FLUX.2 Klein 4B は LoRA を載せられません。導入済みの LoRA は
              SD 1.5 / SDXL 1.0 用です。」
SSD-1B 指定 : LoRA 行は SDXL 1.0 の 1 件のみ（SD 1.5 は消える）、未チェックでスライダー無し
チェック後  : 同じ行にスライダー出現、0.75 へ動かすと表示 0.75 /
              state.selectedLoras [{"model_id":"civitai/99999","weight":0.75}]
FLUX.2 へ戻す: 行 0 件、状況欄「選んだモデルに載せられない LoRA 1 件の選択を外しました。」
```

`./mf.sh test` は 761 passed / warning 1 件 / 58.62 秒、`git diff --check` PASS。
frontend contract に、モデルが常時見えて auto に戻れること、LoRA 選択が手動土台を捨てないこと、
強さが載る組み合わせにだけ出ることの 3 件を追加した。

実 ControlDeck（`/data1tb/ControlDeck/data/features/media-forge/versions/0.9.4`、PID 181506、
127.0.0.1:9130）へはまだ入れていない。実 LoRA weight を載せた生成での見た目差分は
**NOT TESTED**。導入済み instance での確認は release 時に行う。

## 機能切り替えのヘッダー移設と題名の重複解消（2026-08-28）

利用者から、MediaForge と SonicForge の両方で機能切り替えを「詳細」の左のヘッダーへ移し、
題名が二重に出ているので下側を消す、切り替えは「シンプルスマート」に、という指示を受けた。

`画像を作る / 動画を作る` の 2 ボタンは `#create-media-picker` として本文の先頭にあり、モバイルでは
横幅いっぱいの sticky で 1 行を丸ごと使っていた。これをヘッダー常駐の単一 select
（`.function-switch`、SonicForge と同じ形）に置き換え、`.modeswitch` の直前に置いた。試験中バッジは
select の項目に入れられないので、`video.*` が experimental のときだけ項目名を「動画を作る（試験中）」に
する。`#create-media-picker`・`.media-switch`・`.switch-badge` の CSS と、`create-media-image` /
`create-media-video` / `create-media-video-badge` の参照は消えた。backend/API/契約は変更していない。

題名は ControlDeck の host ヘッダーが同じ文字列を出すので二重に見える。DOM から消すと読み上げが
題名を失うため、`html:not([data-bridge="standalone"])` のときだけ視覚的に隠す（1x1 + `clip-path`）。
スタンドアロンでは従来どおり見える。モバイルでは幅を切り替えの側に回すため常に隠す。

実 Chrome（Chrome/151.0.7922.169、headless、CDP）で `MEDIA_FORGE_PORT=9131 ./mf.sh serve` の実 build を
1440x900 と 390x844 で操作した。観測は以下のとおり。

```text
1440 画像 : 切り替えは header 内、右端 1145 <= modeswitch 左端 1155、header 高 <= 72、横溢れ無し
1440 動画 : select=video、#app[data-create-media]=video、題名は standalone なので表示
390  画像 : 切り替え x=75 w=109、modeswitch x=194 w=132、1 行に収まり縦書きに潰れない、題名は非表示
390  動画 : 同上で value=video
埋め込み  : data-bridge="ready" にすると題名は 1x1 / clip-path: inset(50%)、DOM には残る
例外      : JavaScript 例外 0 件、console error は favicon.ico の 404 のみ
```

`./mf.sh test` は 761 passed。frontend contract は、切り替えが header 内で `.modeswitch` より左に
あること、`.function-switch select` が押せる高さと `appearance: none` を保つことを検証する。
実 ControlDeck 導入済み instance での確認は release 時に行う。

## 作る素材の切替をヘッダーの絵 2 択にする（2026-08-28）

v0.9.5 の時点では、作る素材の切替はヘッダーのプルダウン 1 個だった。利用者から
「動画を作る／画像を作るはアイコンにしてシンプル／詳細の左に置いてほしい」という指示があり、
`.mediaswitch` として `.modeswitch` と同じ丸みの分割ボタンへ置き換えた。選択肢が 2 つしか無く
どちらも一目で分かる形を持つため、開いてから選ぶ手数が 1 つ減る。絵は文字を持てないので、
試験中であることは印（`[data-experimental="true"]::after`）と `aria-label` / `title` の
両方で伝える。

実装中に、既存の総称ボタン規則
`button:not(.primary):not(.chip):not(.icon):not(.edit-action):not(.modeswitch button):not(#shell-nav button)`
が `.mediaswitch button` にも当たり、`:not()` 内の id によって特異度が勝つため押下中の
accent 背景が出ないことを実ブラウザの描画で見つけた。除外へ `.mediaswitch button` を足して直した。
テストは通ったままだったので、これは実機描画でしか出なかった不具合である。

実 Chrome（Chrome/151.0.7922.169、headless、CDP、390x844 mobile emulation）での観測。

```text
ヘッダー並び : H1 | ローカルのみ | grow | create-media-switch | modeswitch | nav-settings
              高さ 52px、horizontal overflow 0
当たり判定  : 画像 44x38 / 動画 44x38（狭幅 359px 以下は min-width 34px へ）
画像→動画    : aria-pressed が入れ替わり、createMedia=video、
              「どんな動画を作りますか？」、動画欄 hidden=false
動画→画像    : 元へ戻る。overflow は常に 0
取り込み中   : setHostBusy(true) で 2 つとも disabled、押しても素材は変わらない
```

`./mf.sh test` 761 passed / 2 warnings / 59.69 秒、`git diff --check` PASS。

host header の 詳細 ボタンと 2 段ヘッダーは Media Forge 側では消せない。実体は
ControlDeck の `app/frontend/src/features/addons/EmbeddedAddonView.tsx:403-408` にある
埋め込み add-on 共通ヘッダーで、`{title}` と `{addon.name} · {routePath}` に加えて
`/settings?extension=<id>` へ飛ぶ 詳細 ボタンを常に描く。add-on 側から header へ
操作を出す拡張点は contract 2.0 に存在しない。**NOT IMPLEMENTED**。

## v0.9.5 の署名リリースと実 ControlDeck 反映（2026-08-28）

Media Forge #157（exact head `891601f`、merge `d7fae4f`）、#158（`7d2305e` /
`1a97074`）、#159（`8430a4d` `e42df1f` / `d9aa5e1`）、#160（`4823347` /
`e8fb0d1`）を main へ merge した。#160 は自分の `git add -A` が `dist/` を巻き込み、
30MB の tarball と署名が main まで入った件の後始末である。`dist/` を追跡から外し
`.gitignore` へ足した。履歴の blob は残す（push 済み main の書き換えは割に合わない）。

先に tag と本文だけ作った asset 0 件の v0.9.5 は、#159 / #160 を含まないため削除し、
`e8fb0d1dfb38f900b5f7477bb80fcf09d8b94213` から作り直した。bundle は 30,961,873 bytes、
SHA-256 `167b1b924b4f65e798d173c5de5d1658783660213e994a18099c5f1342645f2a`。
manifest 275 bytes、signature 89 bytes。公開 Release を別 directory へ再取得して
`sha256sum -c` 一致、manifest の feature_id / version / platform / architecture /
size_bytes / sha256 が bundle と一致することを確認した。

実 ControlDeck の標準 `./deck.sh feature update media-forge` は 11.88 秒、max RSS
784,320 KiB、swap 0、exit 0 で成功した。`version=0.9.5 / previous_version=0.9.4 /
healthy`、`current` は `versions/0.9.5`、rollback 用に `versions/0.9.4` を保持。実 process は
PID 726119/726123 で 726123 が 127.0.0.1:9130 を listen し、health は healthy /
contract 2.0。v0.9.5 version tree は 31,229,870 bytes。

実 installed instance（127.0.0.1:9130）を実 Chrome（390x844）で操作した観測。

```text
ヘッダー  : H1 | ローカルのみ | grow | create-media-switch | modeswitch | nav-settings
           高さ 52px、絵 2 択は表示モードの左、当たり判定 40x32、horizontal overflow 0
           動画アイコン押下で aria-pressed 入替・「どんな動画を作りますか？」・動画欄表示
使うモデル: 非 hidden。おまかせ + 導入済み 3 件
           （FLUX.2 Klein 4B / Segmind SSD-1B / stabilityai SDXL base）
LoRA      : 導入済みは civitai/16014（SD 1.5）1 件
  おまかせ            → 行 1 件・未チェック・スライダー無し
  FLUX.2 Klein 4B     → 行 0 件「LoRA を載せられません。導入済みの LoRA は SD 1.5 用です。」
  Segmind SSD-1B      → 行 0 件「（SDXL 1.0）に載せられる LoRA がありません。」
  stabilityai SDXL    → 行 0 件「LoRA を載せられません。」
  おまかせでチェック  → 同じ行にスライダー、selectedLoras [{civitai/16014, 1}]
```

利用者のスクリーンショットにあった「FLUX.2 Klein 4B なのに SD 1.5 LoRA と強さの
スライダーが出ている」状態は、実機で再現しなくなった。

この確認中に、今回の slice の外にある実データの問題を 2 件観測した。どちらも未修正である。

```text
1. LoRA civitai/16014 が要る SD 1.5 の土台 civitai/4384（DreamShaper）は healthy=false で、
   土台の一覧に出ない。state も experimental なので auto でも選ばれない。つまり実機では
   この LoRA を載せられる土台が 1 つも無い。おまかせでチェックはできるが、
   生成まで進めば backend が拒否する見込みである（実行は未実施）。
2. loraCandidates() は installed だけを見て healthy を見ないため、healthy=false の
   civitai/16014 が候補に出ている。土台側は healthy で絞っており、扱いが揃っていない。
```

利用者が追加した `stabilityai/stable-diffusion-xl-base-1.0` は base_model が SDXL 1.0 でも
`supports_lora=false` として登録されており、LoRA を載せられない。custom model の既定値である。

host header の 詳細 削除と 2 段ヘッダーの 1 行化は利用者が別タスクで進めるため、
この slice では **NOT IMPLEMENTED** のままとする。

## LoRA が連れてきた土台が使えるようになるまで（2026-08-28）

利用者から「生成まで進んでバックエンドで断られるのは嫌なので、必要な土台は
ダウンロード時に自動で導入して動くようにしてほしい」という指示があった。実機の
`civitai/16014`（SD 1.5 LoRA）は導入済みだが、載せられる土台が 1 つも無い状態だった。

実機の永続状態を read-only で調べ、原因を特定した。

```text
model_operations   civitai/16014 install ready 18,986,312/18,986,312   22:13:43→22:13:47
                   civitai/4384  install ready 2,132,625,894/同        22:13:43→22:17:03
                   civitai/4384 の evaluate 操作は 0 件
custom-models.json civitai/4384  state=experimental / confidence=low
```

土台の自動ダウンロード自体は動いていた。止まっていたのは、その次の自動評価である。
`ModelEvaluator.evaluate()` は operation を作る前に `_preflight()` を呼ぶが、
`_preflight()` は Wan / Hunyuan / CogVideoX / VACE / H3 の 5 preset しか知らず、
それ以外は `model_evaluation_unsupported` を送出する。一方 `_run()` は画像モデルを
`_preflight()` の**前**に `_run_image_evaluation()` へ振り分けていた。判定が 2 か所に
分かれて食い違っていたため、画像モデルは「評価を始めることだけができない」。
operation 行すら作られないので、画面にも記録にも何も残らなかった。
`evaluate_installed_lora_base` はその `ModelOperationError` を握り潰していた。

`stabilityai/stable-diffusion-xl-base-1.0` が measured なのは、UI ではなく
`scripts/verify_installed_models.py`（CLI）で測ったためである。UI からの画像モデル
評価は一度も成立していなかった。

直したのは 3 点である。

```text
1. 画像評価かどうかの判定を _runs_as_image_evaluation() 1 か所に集約し、
   evaluate() と _run() の両方がそれを使う。画像モデルは _preflight() を通さない
2. 追従を in-process task 頼みにしない。unmeasured_lora_bases() が「導入済み LoRA が
   要る系統で、まだ measured でない土台」を挙げ、models.list のたびに評価を始める。
   再起動で task が消えても次に開いたときに追いつく
3. 失敗を握り潰さない。始められなかった評価は理由付きで log へ出す。
   一度 failed になった評価は自動で繰り返さず、利用者が押し直すまで再開しない
```

`./mf.sh test` は 765 passed / 1 warning / 68.32 秒（新規 4 件）、`git diff --check` PASS。
新規テストは修正を戻すと `model_evaluation_unsupported` で落ちることを確認済みである。

v0.9.6 を実機へ入れた直後、追従の掛け先を間違えていたことが分かった。帳尻合わせを
bridge の `models.list` にだけ置いていたが、埋め込みの boot は個別 method を呼ばず
集約の `workspace.session` を通る（`models.list` を呼ぶのは詳細モードの再描画だけ）。
つまり ControlDeck の中では一度も走らない。15 分待っても評価は始まらず、実機ログにも
`/ws` 接続が無かった。`session_snapshot()` の `models` を作るところへ移し、
そこを外すと落ちるテストを足した。766 passed / 1 warning / 61.45 秒。

## 実機が出した次の 2 段（2026-08-28）

v0.9.7 を入れた後、利用者が画面を開き、実機ログに帳尻合わせの実行と、その失敗理由が出た。

```text
INFO:     WebSocket /ws [accepted]
WARNING:  could not start the base evaluation for civitai/4384: model_not_found
```

握り潰しをやめたことで理由が出た。追従の掛け先（session_snapshot）は正しく動いている。
止まっていたのは、同じ種類のずれの 3 段目である。`_image_candidates()` は custom を含む
`registry_loader` を見るのに、`_model()` は shipped manifest しか見ないため、
`civitai/4384` を「信頼カタログに無い」として拒否していた。`_model()` に custom loader への
フォールバックを足した。

同じ時刻に利用者が実行した生成 job も失敗していた。

```text
job_e4a1b7cf6ab544978f7e25ed6069deda  host_managed=1  failed
  created 2026-08-28T04:32:37Z / updated 04:34:10Z
  model_policy=auto  loras=[{civitai/16014, weight 1}]
  intent  "ロボット. indoor. standing; idle; front-facing; …"（演出が動いた＝LLMを使った）
  error   worker_crash / worker exited with code 2
```

経路はこうである。演出で LLM がロードされる → LoRA を選んでいるので routing は SD 1.5 系に
絞る → SD 1.5 の土台は `civitai/4384` だけで未計測、`available` 0 件 → `_select_real_model()`
が例外ではなく `None` を返す（本物のモデルが 1 つも無い開発環境向けのフォールバック）→
`selected is None` なので `_release_host_ai()` が飛ばされ、**AI ターンの終了宣言が行われない**
→ model を持たない payload でワーカーが起動し exit code 2 で落ちる。

「LLM が降りない」と「理由の分からない worker_crash」は同じ 1 つの分岐から出ていた。
LoRA を選んでいるのに載せる先が無い場合は、既にある `lora_base_unavailable`
（「選んだ LoRA に互換する評価済みの土台がありません」）で断るようにした。LoRA を
選んでいない場合の `None` は開発経路として残す。

AI ターンの解放方針そのもの（使ったら必ず閉じるか、VRAM が要るときだけ要求するか）は
利用者の判断で**現状維持**とした。モデルの寿命は ControlDeck が持つ、という境界を変えない。

過去の成功 job では解放は正しく効いている（`released=True reason=released
freed_bytes=16,464,440,224`）。

`./mf.sh test` は 768 passed / 1 warning / 66.15 秒（新規 2 件）、`git diff --check` PASS。
どちらの新規テストも、修正を戻すと `model_not_found` と `DID NOT RAISE` で落ちる。


## 落とし終えたものを、人が開くまで放置しない（2026-08-28）

利用者が `civitai/4384` を削除し、HuggingFace の `Lykon/DreamShaper` を入れ直した。
download は 05:47:29→05:56:22 の 8 分 53 秒、5,481,450,296 bytes で ready になった。
系統は落とした `model_index.json` の pipeline class（`StableDiffusionPipeline`）から
`SD 1.5` に解決され、LoRA `civitai/16014` を載せられる土台がやっと揃った。
v0.9.8 の修正も効いており、評価候補に `Lykon/DreamShaper` が載る。

```text
評価できる候補 : ["unsloth/MiniMax-H3-GGUF", "Lykon/DreamShaper"]
導入済みLoRAの系統: {"sd15"}
評価待ちの土台  : ["Lykon/DreamShaper"]
```

しかし評価は始まらなかった。帳尻合わせは workspace の boot でしか走らず、download が
終わった 05:56 以降、誰も画面を開いていなかったためである。追従を LoRA 依存の経路だけに
掛けていたので、checkpoint を単体で入れたときは何も起きない。落とし終えたものが、人が
開くまで使えないまま残る。

`follow_install()` に寄せ、`models.install` からも同じ追従に乗せた。依存の経路と 2 つ
持たない。boot での帳尻合わせは、再起動を跨いだ取りこぼしの受け皿として残す。

`./mf.sh test` は 769 passed / 1 warning / 63.09 秒（新規 1 件）、`git diff --check` PASS。

途中、利用者から「ControlDeck に接続できない」との報告があった。実機を確認すると
ControlDeck 本体（PID 851488、15:24:47 起動）は正常で、`/health` は LAN 192.168.68.200 /
192.168.68.67 と Tailscale 100.82.8.44 のいずれからも 200 を返した。原因は iPhone 側の
Tailscale が offline（`last seen 5m ago`、relay "tok" 経由）だったことである。
Media Forge 側の変更とは無関係で、13:51:52 起動の 0.9.8 process は稼働を続けていた。

## 載せられるかを宣言ではなく実際で決める（2026-08-28）

`Lykon/DreamShaper` の自動評価は動いた。06:48:42→06:48:56 の 14 秒で ready、
execution peak VRAM 3,939,438,592 bytes、runtime 13.0 秒、512x512、出力 325,726 bytes。
記録後は `state=available / healthy=true / measured_vram_bytes=5,013,180,416` となり、
「使うモデル」の候補が 3 件から 4 件へ増えた。

それでも LoRA は載せられなかった。実 Chrome（installed 127.0.0.1:9130、390x844）で
DreamShaper を指定すると LoRA 行は 0 件、説明は
「Lykon/DreamShaper は LoRA を載せられません。導入済みの LoRA は SD 1.5 用です。」だった。

原因は `custom_models.py:1205` が、利用者の追加したモデルを常に
`"supports_lora": False` で登録することである。一方 backend はこの旗を一切見ておらず、
`_resolved_loras()` は系統の一致だけで判定する（`jobs.py` / `router.py` に
`supports_lora` の参照は 0 件）。つまり旗は画面専用のゲートで、自分で足した
checkpoint は worker なら載せられるのに、画面が必ず隠していた。

載る条件は「diffusers の checkpoint であること」と「系統が分かること」の 2 つで、
これは導入後に repository 自身を読めば決まる。`_observed_defaults()` で
`base_model` を読む場所に寄せ、立てる方向にだけ動かすようにした。系統を持たない
FLUX.2 Klein 4B は false のまま残り、宣言で立っている SSD-1B は触らない。

`./mf.sh test` は 769 passed / 1 warning / 53.30 秒（新規 1 件）、`git diff --check` PASS。

## 打ち切りの予算が枚数を数えていなかった（2026-08-28）

利用者から「そんなに長い時間動かしていないのに失敗した」との報告。実機の job を見ると、
同じ設定が通ったり落ちたりしていた。

```text
job_8838a3c7  succeeded  80.0s   count=4 1024x1024 lora あり
job_d1f45685  failed     103.4s  count=4 1024x1024 lora あり  worker_timeout
job_9a482525  failed     106.5s  count=4 1024x768  lora あり  worker_timeout
```

`jobs.py` の打ち切りは `max(worker_timeout_sec, measured_runtime_sec * 3 + 30)` で、
`measured_runtime_sec` は評価で 1 枚だけ作ったときの値である（DreamShaper は 13.0 秒）。
つまり 4 枚頼まれていても予算は 13*3+30 = 69 秒のままで、モデルが遅いのではなく
枚数のぶんだけ落ちていた。ぎりぎり通ったのが 80.0 秒の 1 件である。

最初は枚数を掛けて予算を広げたが、利用者から「そんなにギリギリでなくてよい。生成器が
動いているかを見て、定期的に数え直す方がよいのでは」との指摘があり、そちらへ変えた。
総時間の予測は、枚数も解像度も要求ごとに変わる以上どう組んでも外れる。見るべきは
止まっていないかである。

`_communicate_while_progressing()` が、出力先の枚数が増えている間は待ち、増えなくなって
からの時間だけを数える。猶予は `max(worker_timeout_sec, measured_runtime_sec * 3 + 30)`
のままで、これは「総時間」ではなく「1 枚ぶんが止まったと判断するまで」の意味になった。
最初の 1 猶予はモデルの読み込みに使われる。枚数ぶん予算を積む作りと違い、本当に固まった
worker には 1 猶予で気づける。

成功した job の実測も記録しておく。4 枚とも 512x512 で出ており、SD 1.5 の native へ
正しく寄せられている（要求は 1024x1024）。`Lykon/DreamShaper` に `civitai/16014` が
載り、provenance に model_id と LoRA が残っている。**LoRA は実機で動いた。**

## ヘッダーの寄せ方（2026-08-28）

利用者の指示により、作る素材の切り替えと表示モードの切り替えを左へ、設定だけを右端へ
逃がした。余白（`.grow`）を 2 つの切り替えの後ろへ移すだけで済む。実 Chrome（390x844）で
左端からの余白 16px、右端までの余白 16px、horizontal overflow 0 を確認した。

`./mf.sh test` は 771 passed / 1 warning / 62.93 秒（新規 2 件）、`git diff --check` PASS。

## G7 の不採用理由を実測で訂正する（2026-08-28〜29）

利用者から「Reddit などで ROCm の動画生成の相場を調べてほしい。2 分で 5 フレームは
普通ではないか」との指摘を受けた。調べたところ相場は次のとおりで、指摘は正しかった。

```text
AMD Radeon AI PRO R9700 (32GB, gfx1201) / ROCm 7.2
  Wan 2.2 i2v 1024x576 81 frames        初回 約 300 秒（2 回目以降は既知の不具合で 45 分超）
RX 7900 XTX
  Wan 2.1 1.3B 832x480 25 steps         約 24 分
  14B FP8 480P 81 frames 30 steps       20 分弱（TeaCache + torch.compile 後）
```

出典: ComfyUI issue #12672、Wan2.1-T2V-1.3B の AMD support discussion。

そのうえで V1 をやり直した。まず判明したのは、DEFERRED の根拠だった「111.8 秒で 5 フレーム」
が `smoke` プリセット（256x256・**1 step**）の値で、生成性能を測っていなかったことである。
実用プリセットは一度も走っていなかった。

実用プリセット（512x320・33 frames・30 steps）を RAM オフロード可の条件で完走させた。

```text
elapsed 3408.2s（56.8 分） / generate 3401.3s / load 6.1s
peak VRAM 18.61 GB / 34.2 GB      max RSS 11.0 GB
swap in +127 MB / out +96 MB
出力 h264 512x320 33 frames 2.06 秒 54,568 B / デコード正常 / exit 0
```

**メモリは合格である。** 不採用理由の半分だった zero-swap は、GPU が空いた状態では
実質的に満たしている。以前の測定は GPU に 26 GB が常駐した状態のものだった可能性が高い。

残る 56.8 分の内訳を切り分けた。仮説を 4 つ潰してから、pipeline 内部を計測して特定した。

```text
CPU オフロード on/off        107.9s → 102.2s        影響なし
ステップ 1 → 3              +0.4 秒                0.19 秒/step。健全
VAE タイリング on/off        101.68 / 101.71s       影響なし（256x256 では発動しない。比較は無効）
同一 process で 2・3 回目     101.774 / 101.591 / 101.710s   初回限定の支度ではない

内部計測（256x256 5 frames 1 step、float32、オフロードなし）
  vae.encode           2 回  100.21s   最遅 50.12s   ← 固定費のほぼ全部
  vae.decode           1 回    1.20s
  transformer.forward  2 回    0.22s   ← ノイズ除去は速い
```

VAE を bfloat16 にすると悪化した（encode 239.50s / decode 22.22s）。ROCm/RDNA4 では
この 3D 畳み込みは float32 の方が速い経路に乗る。現状の float32 は正しい。

**符号化 100.2 秒に対して復号 1.2 秒**という 83 倍の非対称が残る。そしてこの符号化は
VACE 固有である。VACE は参照映像とマスクを条件に取るモデルなので、生成前にそれらを
潜在空間へ通す（だから 2 回）。素の text-to-video にはこの処理が無い。

公開している文言は「文章から短い動画を作ります」であり、主用途は T2V である。条件付け
専用の重い前処理を持つ VACE を評価候補の中心に据えていたことが、そもそもの取り違えだった。
ノイズ除去そのものは 0.22 秒で、モデルもハードも問題を示していない。

したがって G7 の DEFERRED 理由「実用 latency を満たさない」は、実測に照らして正しくない。
Wan 2.2 TI2V-5B での再計測へ進む。

probe には計測手段を追加した（`--offload` / `--vae-memory` / `--vae-dtype` / `--steps` /
`--repeat` / `--trace`）。既定は従来の挙動のままである。

## ライブラリで動画を見られるようにする（2026-08-29）

ビューアは `<img>` しか持たず、動画 asset を開いても再生できなかった。`<video>` を足し、
mime が `video/` のときはそちらへ渡す。閉じ方は閉じるボタン・Esc・背景と複数あるので、
要素の `close` イベントで停止と解放を行い、押した場所ごとの止め忘れを作らない。

## V1 合格 — Wan 2.1 T2V 1.3B（2026-08-29）

VACE の 100 秒が条件付け符号化であるという見立てを、条件付けを持たない候補で確かめた。
`Wan-AI/Wan2.1-T2V-1.3B-Diffusers` の固定 revision `0fad780a534b6463e45facd96134c9f345acfa5b`
（Apache-2.0）を利用者の明示同意のうえ取得した（2,514.9 秒、27 GB、incomplete 0）。
preflight が既に pin していた revision をそのまま使い、専用 runtime
`runtimes/wan21-1.3b-probe`（torch 2.10.0+rocm7.2.1 / diffusers 0.40.0 / ftfy 6.3.1）で測った。

同一条件（256x256・5 frames・1 step）の比較。

```text
                       VACE            T2V
vae.encode        2 回 100.21s        0 回      ← 条件付けが無い
vae.decode        1 回   1.20s        1 回 1.23s
transformer       2 回   0.22s        2 回 0.39s
generate 合計         101.78s             3.87s
```

`vae.encode` は 1 度も呼ばれない。101.7 秒の固定費は VACE 固有の条件付けであった。

実用プリセット（512x320・33 frames・30 steps）。

```text
generate 144.64s（2.4 分）   load 162.77s（コールド、process 1 回きり）
wall 321.05s（5.4 分、mp4 書き出し込み）   max RSS 24,699,984 KiB
  transformer.forward  60 回   24.16s   0.8 秒/step
  vae.decode            1 回  118.20s   ← 生成の 82%。現在の最大費目
  vae.encode            0 回
出力 h264 512x320 33 frames 2.06 秒 29,629 B / デコード正常 / exit 0
swap out +1,226,210 ページ (4.68 GB) / in +1,142,815 ページ (4.36 GB)
```

同じ R9700 の公開報告は 1024x576・81 frames で約 300 秒であり、今回の 512x320・33 frames
生成 144.6 秒／全体 321 秒は同等の水準である。**latency は相場どおりで、不採用の理由に
ならない。** G7 の DEFERRED 判定は、評価候補の取り違え（T2V の用途に対して条件付け
専用の VACE を中心に据えた）と、性能を測っていない数字（smoke = 1 step）に基づいていた。

正直に残す点が 2 つある。swap は 4.68 GB 書き出しており、max RSS 24.7 GB は本機 30 GB に
対して小さくない。同時に重いものを動かせば影響が出る。もう 1 つは VAE 復号が 118.2 秒で
生成の 82% を占めることで、今回はタイリングを切って測った。ここは詰める余地がある。

なお background で起動した probe は 2 回とも読み込み中に停止された（利用者の操作では
ないことを確認済み、OOM の記録は権限の都合で未確認）。前景では完走する。原因は未特定。

## 生成した動画をライブラリへ出す道は、まだ無い（2026-08-29）

利用者の「生成した動画はライブラリから見れるようにして」に対し、ビューアは `<video>` を
持つようにした。しかしその先が繋がっていない。

```text
asset import   PNG / JPEG / GLB のみ。video/mp4 は受け付けない（asset_import.py）
asset 登録     operation ごとに image/png か application/zip を直書き（jobs.py）
thumbnail      is_thumbnailable は image/png,jpeg,webp,application/zip のみ
```

つまり動画 asset を作る経路が core に無く、V1 で作った mp4 を見せる手段が現時点で存在
しない。これは G7 V2（本番実行）の範囲であり、V1 合格を受けて次に作るものである。

## V2-a — 動画 asset をライブラリが扱えるようにする（2026-08-29）

V1 合格を受けて、動画を一覧と拡大表示で扱える土台を作った。生成経路（V2-b）はまだ無いので、
この段階では「動画 asset があれば正しく出せる」ところまでである。

```text
thumbnails   video/mp4 を is_thumbnailable へ追加し、1 枚目を取り出して静止画の経路に乗せる
             worker の FFmpeg 実装は import せず、system binary を配列引数・timeout 20 秒・
             使い捨て directory の中だけで呼ぶ。壊れた入力は枠を作らず ThumbnailError
library      preview_kind に "video" を足し、duration_sec / frame_rate を entry へ出す
frontend     カードに ▶ と尺の印。一覧では自動再生しない。viewer は video 要素で再生し、
             dialog の close で停止・解放する（閉じ方が 3 通りあるため押下箇所ごとに書かない）
```

実クリップでの確認: V1 で作った 512x320 33 frames 2.06 秒 29,629 B の mp4 から、
256x160 の webp ポスターを 2,154 B で生成できた。

`./mf.sh test` は 775 passed / 1 warning / 64.82 秒（新規 2 件）、`git diff --check` PASS。

## V2-b（1/2）— 動画 worker（2026-08-29）

`worker_packs/video/worker.py` を追加した。core はこの実装を import せず、やり取りは
画像 worker と同じ行ごとの JSON である（`ok` / `error`、`resource_oom` の区別、
`MAX_MESSAGE_BYTES`）。

実測にもとづく既定を worker へ固定した。

```text
VAE dtype        float32。bfloat16 は符号化 2.4 倍・復号 18 倍の悪化を実測
device 配置      収まる限り退避しない。退避しても生成は 5% しか変わらず読み込みが倍
pipeline 保持    process が生きている間 1 度きり。コールド 162.8 秒を要求ごとに払わない
出力             frames -> ffmpeg で組み立て -> ffmpeg.normalize -> probe で検証
                 公開する形は正規化済みの 1 つに揃え、生成器の書き出しをそのまま出さない
```

外から来る値は信じない。model path は境界内に限り、adapter は既知のものだけ、
寸法は偶数かつ 16..1024、frames 5..161、steps 1..50、fps 1..120、intent は非空。
境界の外や範囲外は GPU を動かす前に断る。

test は GPU を要さない部分（境界・検証・規約の一致）で 10 件。生成そのものは V1 の実測で
裏付けている。`./mf.sh test` は 785 passed / 1 warning / 66.88 秒。

残りは core 側である。`video.generate` の実行経路（worker 起動・phase・asset 登録）と
routing / capability がまだ無い。

## V2-b（2/2）と V2-c — core 側の実行経路と採用（2026-08-29）

core に `video.generate` の経路を作り、capability の固定をやめた。

```text
capability     video.text_to_video を実態から出す。runtime が無ければ
               video_runtime_not_installed、モデルが無ければ model_not_installed。
               入力画像から動かす経路は worker に無いので image_to_video は据置
runtime        画像と別 venv。MEDIA_FORGE_VIDEO_RUNTIME_PYTHON で差し替えられる。
               同じ venv に載せると片方の pin を動かしたときもう片方が黙って壊れる
worker 選択    adapter が動画のものなら動画 worker を起動する
asset 登録     _register_video_outputs。画像側の検証（brief defect、意味レビュー）は
               絵を見る前提なので当てない。形の検証だけを行い、中身が動画かは
               worker の probe が見ている。video/mp4 / 寸法 / 尺 / fps を asset へ残す
catalog        Wan-AI/Wan2.1-T2V-1.3B-Diffusers を available / managed / measured へ。
               既存 entry を置き換えではなくその場で更新した（revision と weight hash は
               取得済みのものと一致）。measurements は実測値をそのまま入れた
```

旧方針を守っていた test 5 件を更新した。守る値は残し、「動画候補は routable にしない」
という前提だけを外した。available な adapter は画像 worker が実装しているものに限る、
という不変条件は、実装している worker を全部足す形へ広げた。

重みは同一 filesystem 上のハードリンクで実機の置き場へ配置した（27 GB、空き容量の変化なし）。

`./mf.sh test` は 785 passed / 1 warning / 63.70 秒、`git diff --check` PASS。

## V2-c / V2-d — 実機で video.generate が通るまで（2026-08-29）

0.10.0 を入れた直後は `video_runtime_not_installed` だった。bundle launcher が画像 runtime しか
feature data へ向けておらず、installed な Media Forge が repository の中を探していた。
`MEDIA_FORGE_VIDEO_RUNTIME_PYTHON` を feature data 配下（`runtimes/wan21-t2v`）へ向け、
runtime と重みを同一 filesystem のハードリンクで配置した（venv は複製せず、
`sys.prefix` が配置先を指すことと torch 2.10.0+rocm7.2.1 / diffusers 0.40.0 / ftfy 6.3.1 の
import を実機で確認）。

0.10.1 で capability が変わった。

```text
video.text_to_video  -> available / implementation local / confidence measured / local_only
video.image_to_video -> unavailable / video_runtime_not_adopted（worker に経路が無い）
```

次に job を投げると `capability_unavailable` で落ちた。dispatcher が
`image.generate` / `image.edit` / `asset.pack` の 3 つしか知らず、runtime が揃っていても
video を弾いていた。通すようにしたうえで、動かせる動画モデルが無いときは fake worker へ
落とさず理由を名指しするようにした（落とすと「PNG しか出せない」と言われ、何が足りないのか
分からなくなる。LoRA で直したのと同じ形である）。0.10.2 で反映。

REST の `/api/v1/jobs` から投げた job は `host_lease_required` で落ちる。これは正しい。
GPU job は ControlDeck の lease を通す必要があり（AGENTS.md 規約 8）、workspace 経由の
identity を持つ経路だけが実行できる。画面からの実行は **NOT TESTED**。

画面側の条件は満たしている。`videoCapabilityUsable()` は available / experimental を通し、
作るボタンは `video && !usable` のときだけ無効になるので、いまは押せる状態にある。

installed v0.10.2 / healthy / contract 2.0。`./mf.sh test` 785 passed。

## 画面から動画を作ると即失敗した（2026-08-29）

実機で 2 件、0.9〜1.2 秒で `worker_error: width must be an integer` として落ちた
（job_6bfb298d / job_d92ab004）。画面は `constraints: {}` を送っており、これは正しい。
どのモデルが選ばれるか画面は知らないのだから、公開要求に寸法を持ち込ませない設計である。
埋める場所を worker に求めていたのが誤りだった。worker 側に既定を置くと、モデルを増やす
たびにその固定値が全部へ掛かる。

`_resolved_video_request()` を core に置き、選んだモデルの実測既定から埋めるようにした。
画像側の `_resolved_request()` と同じ考え方である。指定された値は動かさない。正規化は
偶数しか受けないので、奇数は生成の前に落とす。catalog には実測した設定
（native 512x320 / steps 30）を入れ、frames 33 / fps 16 は 2.06 秒のクリップとして
144.6 秒で作れた設定を core の既定に置いた。

`./mf.sh test` 786 passed。

## 受理が 10 秒で切れていた（2026-08-29〜30）

寸法の修正後、画面からの動画 job は `width must be an integer` を出さなくなった。次に
出たのは 22〜27 秒後の `host_unreachable: ControlDeck Host API is unreachable`
（job_65751f36 / job_e2b2afa2）。ControlDeck 本体は稼働しており、`/health` も
`/api/v1/health` も 200 を返していた。AI ターンの解放も成功している。

原因は 2 つ重なっていた。

```text
1. host client の共通 timeout が 10 秒。受理は VRAM を空けることを含むので足りない。
   実測では 16.5 GB の常駐を降ろしてからでないと通らない要求がある
2. httpx のあらゆる失敗を "ControlDeck Host API is unreachable" の 1 文へ潰していた。
   timeout なのか接続不能なのかが区別できず、切り分けに 1 往復ぶん余計にかかった
```

受理の POST だけ 120 秒へ広げた。待機そのものは `resource_status` の速い poll が
引き受けるので、長く待つのは最初の 1 度きりである。エラーは例外の型と本文を添えるように
した。これで次に落ちたときは理由が残る。

`./mf.sh test` 787 passed。

## 動画の設定を簡易にも詳細にも置く（2026-08-30）

利用者から「動画は作れたし再生もできた。ただし簡易・詳細とも設定項目が一切なかった。
特にモデル選択と画質、時間設定は両方でできるように」との指摘。作れるだけで、どう作るかを
選べない状態だった。段階開示は「簡単にするために削る」ことではない。

```text
使うモデル   媒体で一覧が変わる。画像は FLUX.2 / SSD-1B、動画は Wan 2.1 T2V 1.3B。
             以前は data-image-create で画像専用だったため、動画では選べなかった
画質 (L1)    標準 512x320 / 横長 640x384 / 正方形 448x448。数値ではなく意味で選ばせる
長さ (L1)    2秒 33 / 3秒 49 / 5秒 81 フレーム
目安時間(L1) 実測 144.64 秒（512x320・33 フレーム・30 歩）からの外挿。面積は注意機構に
             二乗で効き、長さはフレーム数に比例する。初回のモデル読み込みは別に明示する
詳細 (L3)    歩数 / ガイダンス / フレーム数 / fps / 打ち消し語。簡易の選択を奪わない。
             指定したものだけを送り、残りは選ばれたモデルの実測既定で埋まる
```

実 Chrome（390x844）での観測。

```text
画像        モデル候補 3 件（おまかせ + FLUX.2 + SSD-1B）、動画設定は hidden
動画へ切替  モデル候補 2 件（おまかせ + Wan 2.1 T2V 1.3B）、画質・長さが出る
            目安「512×320 / 33 フレーム。作るのにおよそ 2 分かかります。」
横長 + 5秒  目安「640×384 / 81 フレーム。作るのにおよそ 13 分かかります。」
            送信 {"width": 640, "height": 384, "frames": 81}
詳細モード  歩数・ガイダンス・フレーム数・fps・打ち消し語が出る
```

面積を 1.5 倍・長さを 2.45 倍にすると目安が 2 分から 13 分へ伸びる。二乗で効くことが
画面の数字に出ている。押してから知らせない。

`./mf.sh test` 789 passed / 1 warning / 61.34 秒（新規 2 件）、`git diff --check` PASS。

## 評価は終わっていたが、何も変わっていなかった（2026-08-30）

利用者から「MiniMax の評価ボタンを押しても評価が終わらない。ブラウザを閉じたからか」との
問い合わせ。実機を見ると評価は**成功して終わっていた**。

```text
modelop_fc571456  unsloth/MiniMax-H3-GGUF  evaluate  ready
  03:37:45 → 03:40:15（149.28 秒）  host_job=2cfdf9cb277f
  peak VRAM 14,763,892,736 B / peak RSS 23,699,308,544 B / process swap 0
  出力 640x384 vp8 0.167 秒 122,118 B
```

ブラウザを閉じたことは関係ない。job も model operation も server 側の durable な記録で、
閉じても走り続ける。

止まっていたのは記録の方だった。`record_measurement` は `_run_image_evaluation` にしか
無く、MiniMax のような native 経路は結果を operation に残すだけでモデルの計測値を
更新しない。150 秒かけて測っても `measurement_confidence` は low、
`measured_vram_bytes` は None のまま。画面は何も変わらないので「終わらない」ように見える。

画像経路には既に正しい注記があった。「測れたのに書き残せないなら、成功と言っては
いけない。次に開いたとき、また未計測に戻っている」。同じことが native 経路で起きていた。

```text
native 経路      _record_native_measurement() を完了直前に呼ぶ。書き残せなくても
                 評価そのものは成功しているので job は失敗させない
出荷モデル       出荷 manifest は実行時に書き換えない。測った値は runtime 側の
                 measurements.json へ重ねる。ModelRegistry.load が上から被せる
state           動かさない。測ることと使ってよいと決めることは別で、測っただけで
                 routing に載るなら評価を押すことが採用を意味してしまう
読む側          custom_models.overlay() が追加分と測定値を 1 組で返す。測定値だけ
                 別経路で渡すと、渡し忘れた読み手が「未計測」と言い続ける
```

`./mf.sh test` 791 passed / 1 warning / 53.10 秒（新規 2 件）、`git diff --check` PASS。

## workspace の配信が無圧縮だった（2026-08-30）

利用者から「Media Forge への接続にめっちゃ時間がかかる。軽量化してほしい」との指摘。
測ると、workspace の文書だけが無圧縮で出ていた。

```text
配信          356,733 B / content-encoding なし / cache-control: no-store
gzip -9 相当   91,349 B（74% 減）
内訳          <script> 253,108 B（app.js） / <style> 48,623 B / markup 他
```

workspace は markup と style と script を 1 応答へ畳んで返す作りなので、この 1 本が
そのまま接続の待ち時間になる。手元は 15 ms でも、実機は Tailscale の relay 経由である
（`relay "tok"` を 2026-08-28 に観測済み）。

WebSocket は無関係だった。uvicorn の `ws_per_message_deflate` が既定 True で、boot の
session snapshot は既に圧縮されている。無圧縮で残っていたのは HTTP の文書だけである。

`GZipMiddleware(minimum_size=1024)` を入れた。実測。

```text
/                            356,733 B -> 91,376 B  (74% 減)
/api/v1/models                24,158 B ->  5,190 B  (79% 減)
/workspace-api/models/catalog 22,919 B ->  5,180 B  (77% 減)
/api/v1/capabilities           1,602 B ->    372 B  (77% 減)
```

小さな応答まで圧縮しても CPU を使うだけなので下限を 1 KB に置いた。

boot のうち thumbnail は 4 件で base64 12,368 B（160px webp）であり、重い側ではない。
文書が全体の 74% を占めていた。

`./mf.sh test` 792 passed / 1 warning / 66.15 秒（新規 1 件）、`git diff --check` PASS。

## 評価が記録されず、実行環境の無いモデルが候補に見えていた（2026-08-30）

利用者から「MiniMax を評価したが終わらなかったし、動画生成 AI の候補としても
選択できない」との指摘。別々の 2 件だった。

### 1. 記録が効いていなかった（私の取り違え）

0.11.1 で native 経路にも `record_measurement` を足したはずが、15:36 の評価
（161 秒、ready）でも `measurements.json` は作られず、`measurement_confidence` は
low のままだった。原因は `RuntimeMetrics` に `elapsed_sec` が無いのに
`getattr(metrics, "elapsed_sec", 0)` で拾おうとしていたことで、0 が返って
ガードが黙って抜けていた。

```text
RuntimeMetrics  started_at / baseline_* / peak_rss_bytes / peak_process_swap_bytes / peak_vram_bytes
result          elapsed_sec / peak_vram_bytes / peak_rss_bytes / ...
```

operation へ残すのと同じ `result` から読むようにした。加えて、前のテストが
ソース文字列しか見ておらず壊れた実装を通していたので、実際に関数を呼ぶテストへ
差し替えた。旧実装では落ちることを確認済みである。

### 2. MiniMax は動画候補になり得ない

`unsloth/MiniMax-H3-GGUF` が名乗る adapter は
`native.stable-diffusion-cpp-minimax-h3` で、これを実装する worker が無い。

```text
画像 worker  diffusers.flux2-klein / diffusers.sdxl / diffusers.sdxl-single-file
動画 worker  diffusers.wan2.1-t2v
出荷カタログの動画候補 12 件のうち、実行できるのは Wan 2.1 T2V 1.3B のみ
```

候補として並ぶこと自体は正しい（調べる対象である）。誤っていたのは、その差を
画面に出していなかったことで、実行できないモデルの評価に GPU を 161 秒使っても
選べるようにならない、と押す前に分からなかった。

`models/adapters.py` に core が起動できる adapter を置き、公開文書へ
`has_runtime` を足した。画面は「実行環境なし」として一覧の判定に組み込み、
モデル管理では押す前に理由を書く。core は worker を import しないので知識が
2 か所に分かれる。食い違わないことは test が見張る（test は worker を import
してよい）。available なモデルは必ず実行できる、という条件も同じ test で守る。

`./mf.sh test` 795 passed / 2 warnings / 53.72 秒（新規 3 件）、`git diff --check` PASS。

## MiniMax H3 FL2VA を本番経路へ載せる（2026-08-30）

利用者の指示は「MiniMax H3 FL2VA と Wan の実行環境を準備し、既に開発済みの
ドライバーがあれば組み込む方針で調査・導入・検証・生成まで」。調べると、駆動系は
**既に完成していた**。評価が使っている `stable-diffusion.cpp` の pinned build
（`97d2990`、`build/bin/sd-cli`）がそれで、実際に 640x384 の動画を作れている。

```text
重み（実機に導入済み、4 点）
  minimax_h3_fl2va_pruned-UD-Q2_K_XL.gguf   拡散本体（FL2VA）
  qwen3vl_32b_minimax_h3-Q2_K_M.gguf        言語モデル
  vae/minimax_h3_video_vae_fp16.safetensors 映像 VAE
  vae/minimax_h3_audio_vae_fp32.safetensors 音声 VAE
起動          sd-cli -M vid_gen / te=cpu,diffusion=ROCm0,vae=ROCm0 / --mmap / --diffusion-fa
```

本番の動画 worker に adapter を足し、同じ組み合わせで起動するようにした。評価と本番で
2 通りの起動を持たない。実機で通すまでに 3 つ塞いだ。

```text
1. 重みが blobs/ への symlink である。snapshot だけを境界にすると正しい重みが
   「外」と判定される。境界を repository の根に置く（評価側と同じ扱い）
2. LD_LIBRARY_PATH が無いと libomp.so が見つからず sd-cli が起動しない。
   評価が使っているのと同じ環境を worker にも持たせる
3. MiniMax H3 は音も作る。正規化で include_audio を落とさない
```

実機での生成（本番 worker を直接叩いた）。

```text
生成 57.11 秒 / wall 57.50 秒 / max RSS 23,985,892 KiB / exit 0
出力 h264 640x384 5 フレーム 24fps 0.208 秒 39,070 B + aac 音声
runtime_version 97d2990807fe6d558e395f8764198d7c7e7b411c
```

registry では available / measured / rocm 対応にした（2026-08-30 の評価から
peak VRAM 14,763,892,736 B、149.28 秒）。宣言に rocm が無いと、測ってあっても
routing の候補にならない。

`./mf.sh test` 795 passed（新規 2 件）。

## Wan 2.2 TI2V-5B の実行環境を復元して生成まで通す（2026-08-30）

上流の駆動系（`wan` package）は `/data1tb/mediaforge-g7-v1/Wan2.2-source` に残っていた。
消えていたのは venv だけである。`runtimes/wan-ti2v-probe/requirements.txt` から作り直したが、
そのままでは `wan.configs` が読めなかった。

```text
不足していた依存   einops / imageio（requirements から抜けていた）
追記               imageio==2.37.4 / einops==0.8.1 を pin
```

実機で通した実測（text encoder は CPU、生成は GPU の 2 process）。

```text
smoke          256x256 1 フレーム 1 歩    encode 24.37s + generate 24.57s / wall 61.52s
quality-frame  256x256 1 フレーム 30 歩   encode 27.74s + generate 28.36s / wall 109.52s
candidate-clip 384x256 33 フレーム 30 歩  encode 14.01s + generate 73.48s / wall 100.51s
               出力 h264 384x256 33 フレーム 1.375 秒 115,130 B / max RSS 19.4 GB / exit 0
```

30 歩は 1 歩に対して +3.79 秒（0.13 秒/歩）で、費用の大半は読み込みである。

本番 worker に `native.wan2.2` を足し、評価が使っている probe をそのまま呼ぶ形にした。
評価と本番で 2 通りの起動を持たない。text encoder と生成を別 process に保つのは
device の取り合いを避けるためで、1 つに畳むと 5B が載らない。

registry は available / native 384x256 30 歩、`measured_runtime_sec` を 100.51 へ更新した。
VRAM は G7 V1 の実測（30.7 GB）を据え置く。今回は採取していないので上書きしない。

### 実機の runtime を一度壊し、復旧した

実機の動画 runtime へ `wan` の依存を足すとき、索引を指定せずに pip を走らせたため
torch が CUDA 版 2.13.0 へ入れ替わり、`Found no NVIDIA driver` で動かなくなった。
repository 側の venv は無事だったので、実機側を消して hardlink で作り直し、ROCm の
find-links を明示して入れ直した。

```text
復旧後  torch 2.10.0+rocm7.2.1.gitb07cec22 / torchvision 0.25.0+rocm7.2.1.git82df5f59
        wan.configs 読み込み OK（ti2v-5B を含む 5 構成）/ diffusers 経路も健全
```

ROCm の venv へ何かを足すときは、常に `--find-links` を付ける。付けないと pip は
CUDA 版で上書きする。

`./mf.sh test` 797 passed。

## 動画の設定をモデルごとに最適化する（2026-08-31）

利用者から「時間はもっと選択肢がないか。スライダーで選べるか。各モデルに合わせて
最適化し、評価で確認した適切な設定が選べる UI/UX にしてほしい」との指摘。

3 択だったのはモデルの制限ではなく私の決め打ちだった。ただし連続に選ばせる前に、
モデル側の本当の制約を確かめる必要があった。

```text
Wan（2.1 / 2.2）  num_frames % 4 == 1 でなければならない。外すと diffusers が黙って
                  丸めるので、頼んだ長さと返る長さが食い違う
MiniMax H3        sd-cli は任意のフレーム数を取る。刻み 1 で選ばせてよい
Wan 2.2（私の実装） probe の preset へ丸めていた。頼んだ寸法と違うものが返る作りだった
```

Wan 2.2 の probe に寸法・フレーム数・歩数の上書きを足し、本番は preset を下敷きに
しつつ実際の要求で作るようにした。preset へ丸めるのをやめた。

長さは連続のつまみにし、刻みをモデルが取れる並びに合わせた。画質もカタログの実測
プロファイルから組む。共通の決め打ちを持つと、どれかのモデルで「選べるのに作れない」
値を出すことになる。

```text
registry に video プロファイルを足した（すべて 2026-08-29〜31 の実測）
  Wan 2.1 T2V   16fps / 4 刻み 9..81 / 512x320・640x384・448x448 / 実測 512x320 33f
  Wan 2.2 TI2V  24fps / 4 刻み 9..81 / 384x256・512x320・256x256 / 実測 384x256 33f
  MiniMax H3    24fps / 1 刻み 5..49 / 640x384・512x320・384x384 / 実測 640x384 5f
```

目安時間もモデルごとの実測から出す。面積は注意機構に二乗で、長さはフレーム数に比例
して効く。モデルを選び直したら画質と長さを組み直す。前のモデルの寸法を残すと、
選べるのに作れない値が画面に残る。

実 Chrome（390x844）での観測。

```text
Wan 2.2 指定  画質 384×256 / 長さ 0..18（4 刻み）→ 1.4 秒 / 送信 fps 24
Wan 2.1 指定  画質 512×320 / 長さ 0..18（4 刻み）→ 2.1 秒 / 送信 fps 16
MiniMax 指定  画質 640×384 / 長さ 0..44（1 刻み）→ 0.2 秒 / 送信 fps 24
つまみを動かす 640×384 / 10 フレーム / 目安 2 分 → 5 分
```

途中、公開文書の 3 か所（`/api/v1/models`、管理カタログ、単体表示のマッピング）で
`video` を落としていた。どれか 1 つでも落とすと、画面はどのモデルでも同じ選択肢を出す。
`kind` や `base_model` で以前起きたのと同じ形である。

`./mf.sh test` 797 passed、`git diff --check` PASS。

## 最長の長さが誤っていた／FastH3 LoRA は当たらない（2026-08-31）

利用者から「最大でも 5.1 秒、H3 は 2 秒と表示されるが、生成最大時間は正しいか」との指摘。
表示は私が入れた値どおりだったが、その値が上流の定義と合っていなかった。

```text
Wan 2.1 T2V   81 フレーム / 16fps = 5.06 秒   diffusers の既定と一致。正しかった
Wan 2.2 TI2V  上流 wan/configs/wan_ti2v_5B.py の frame_num = 121 / 24fps = 5.04 秒
              入れていたのは 81（3.4 秒）。低すぎた
MiniMax H3    sd.cpp のドキュメントが 3 例とも --video-frames 56（24fps で 2.33 秒）
              入れていたのは 49（2.0 秒）。根拠のない当て推量だった
```

上流の定義に合わせて直した。H3 はモデル自体が 15 秒まで作れると公表されているが、
この駆動系での上限は未確認なので、ドキュメントが実際に使っている 56 を上限に置く。

### FastH3 / Turbo LoRA は現在の駆動系に当たらない

利用者の「MiniMax H3 Flash は使えるか」を調べた。MiniMax の Fast H3 v1（2026-08-29 発表）は
NVIDIA Blackwell 上で約 14 倍という数字で、重みの配布形態も技術報告も未公開である。
一方 open weight 側では高速化 LoRA として実物が出ている。

```text
lightx2v/Minimax-h3-Turbo          4step / 8step、Apache-2.0、DL 884,976
alibaba-pai/MiniMax-H3-Acc-LoRAs   8step、other
drozbay/MiniMax-H3-FastH3-Preview-LoRA  FastH3 preview、other
```

`sd-cli` は `--lora-model-dir` を持つので、当てられるはずだった。Apache-2.0 の
`minimax_h3_fl2v_turbo_4step_v1.1_768p_bf16.safetensors`（1,383,677,808 B）を取得して
実機で試した結果、**当たらなかった**。

```text
[WARN] Only (0 / 600) LoRA tensors have been applied
unused lora tensor |lora.model.diffusion_model.transformer_blocks.22.attn.to_out.0.weight.lora_down|
4 歩 LoRA なし  63.12 秒
4 歩 LoRA あり  89.31 秒（1.38 GB を読んで 0 個適用。遅くなるだけ）
```

テンソル名の規約が gguf 側と噛み合わない。ComfyUI 版も同じ系統の命名なので見込みは薄い。

なお H3 は読み込みが支配的で、1 歩 57 秒に対し 4 歩 63 秒（1 歩あたり約 2 秒）である。
仮に LoRA が当たっても、速度への効きは小さい。効くのは低歩数での品質の方である。

`./mf.sh test` 797 passed。

## H3 は 15 秒まで作れた／目安時間を実測の形へ（2026-08-31）

利用者から「H3 は 15 秒ならそうして」との指示。公表値をそのまま入れず、この機械で
作れるかを確かめた。前回 56 を入れて誤ったのは、根拠を実測ではなくドキュメントの例に
置いたためである。同じ形を繰り返さない。

```text
640x384 / 4 歩 / R9700
    5 フレーム (0.21 秒)     63.12 秒   max RSS 23.2 GB
  121 フレーム (5.13 秒)    594.72 秒   max RSS 24.9 GB   映像 vp8 + 音声 pcm 正常
  360 フレーム (15.04 秒)  1889.53 秒   max RSS 25.1 GB   17,218,141 B / 正常
```

**15.04 秒が完走した。** 上限を 360 フレームへ上げた。VRAM は 17.8 GB で頭打ちにならず、
制約は時間の方である。あわせて H3 の既定歩数を 1（評価用の下限）から 4（実測した値）へ。

### 目安時間を 1 点比例から固定費＋単価へ

1 点からの比例では、読み込みの固定費が大きいモデルで大きく外れる。H3 の実測
（149.28 秒 / 5 フレーム）を比例で伸ばすと 360 フレームで 179 分となり、実測 31.5 分の
5.7 倍になる。使えない案内である。

実測から固定費と 1 フレーム単価に分け、面積の効き（注意機構は二乗）だけを掛ける。

```text
Wan 2.1 T2V   固定 25.0 秒 + 3.6 秒/フレーム   （33 フレームで 144 秒。実測 144.6 秒）
Wan 2.2 TI2V  固定 20.0 秒 + 2.4 秒/フレーム   （33 フレームで  99 秒。実測 100.5 秒）
MiniMax H3    固定 40.0 秒 + 5.0 秒/フレーム   （  5 フレームで  65 秒。実測  63.1 秒）
                                              （360 フレームで 1840 秒。実測 1889.5 秒）
```

実 Chrome での表示。

```text
Wan 2.2   目盛 0..28   0.4 秒(9f) 1 分未満 / 5.0 秒(121f) 5 分
Wan 2.1   目盛 0..18   0.6 秒(9f) 1 分未満 / 5.1 秒(81f)  5 分
MiniMax   目盛 0..355  0.2 秒(5f) 1 分     / 15.0 秒(360f) 31 分
```

`./mf.sh test` 797 passed。

## 動画を取り込めるようにする（2026-08-31）

利用者から「サンプル動画は見れるようにライブラリに入れておいて」との指示。
実行してみると、取り込み経路が PNG / JPEG / GLB しか受けなかった。生成した動画は
job から登録されるが、既にファイルとして手元にあるものを library へ入れる道が無い。

`video/mp4` / `video/webm` / `video/quicktime` を受けるようにした。上限は画像と分けて
96 MiB に置く（実測: 640x384 の 15 秒で 17.2 MB。共通の 64 MiB で切ると、少し大きい
ものが理由なく弾かれる）。

**取り込んだものは h264/aac の mp4 へ揃える。** 駆動系は webm/vp8 を書くものもあるが、
iOS はそれを再生しない。そのまま置くと、作った端末でだけ見える asset ができる。
library に置くものは見られる形にする、という一点のために正規化する。

中身が本当に動画かは ffprobe で確かめる（worker の実装は import せず、system binary を
配列引数・timeout 付きで呼ぶ）。映像 stream はちょうど 1 本、寸法は 16px 以上かつ
画素上限内、尺は 0 < s <= 300、fps は 0 < f <= 120。外れるものは枠を作らず断る。

`./mf.sh test` 797 passed（新規 1 件）。

## 歩数の既定が誤っていた（2026-08-31）

利用者から「動画がおかしい。画像生成のときも試行回数が少なくおかしかったが、動画は
問題ないか」との指摘。**正しかった。** 同じ誤りを歩数で繰り返していた。

```text
sd-cli の既定        20 歩
ドキュメントの 3 例   --steps を書かない（= 20 を使う）
登録していた値        4 歩   ← library の H3 2 本はこれで作った
```

4 は私が測定に使った値であって、このモデルが要る歩数ではない。frame_max を 56 に
したのと同じ手癖である。**設定値は実測の副産物ではなく、モデルが要求する値から決める。**

20 歩で測り直した（640x384）。

```text
    5 フレーム   177.69 秒   （4 歩では 63.12 秒）
  121 フレーム  2647.52 秒   （4 歩では 594.72 秒。歩数 5 倍に対し 4.45 倍）
  → 固定 71.2 秒 + 21.29 秒/フレーム。360 フレームなら 129 分の見込み
```

1 歩の単価は約 7.2 秒で、目安計算に使っていた 2 秒の 3.6 倍だった。目安時間も過小に
出ていたことになる。式へ歩数を織り込み、どの歩数で測った値かを `measured_steps` として
記録する。書かないと、歩数を変えたときに式が黙って外れる。

lease へ申告する `measured_runtime_sec` も、評価の 1 歩（149.28 秒）から実用設定での
実測（2647.52 秒）へ変えた。評価は「動くか」を見るためのもので、その所要時間を実用の
見積りに流用してはいけない。

Wan 2.1 / 2.2 は上流の既定 30 歩を使っており、この問題は無い。

`./mf.sh test` 798 passed。

## 評価が測った時間で、実用の実測を潰していた（2026-08-31）

前項の 20 歩の実測を出荷しても、実機では効かなかった。overlay が勝っていた。

```text
manifest        measured_runtime_sec 2647.52   （20 歩 121 フレーム）
overlay が上書き                      158.409   （評価の 1 歩 5 フレーム）
実機の API が返す値                    158.409
```

`ModelRegistry.load(measurements=)` は manifest の `measurements` を**丸ごと**
置き換える。評価の記録は VRAM を測るためのものだが、時間の欄まで probe の値で
埋めていたため、出荷した実測が毎回の評価で消えていた。lease は 17 分の 1 で
確保され、実用の設定で回すと途中で切れる。

VRAM は probe が測ったものを残し、時間は manifest の実測を通す。評価は「動くか」を
見る最小の実行であって、実用の設定で払う時間ではない。実機の overlay も直した。

### 宣言した歩数が画面に届いていなかった

`generation` block は `diffusers.` 経路にしか付かない。native の動画モデル
（H3 / Wan 2.2）には届かず、画面は `measured_steps` で代用していた。今日は
両方 20 と 30 で一致しているが、`measured_steps` は「その実測が何歩だったか」で
あって生成に使う歩数ではない。測り直した歩数がそのまま既定にすり替わる。
`video` profile に `default_steps` を入れ、画面はそれを見る。

生成そのものは `_resolved_video_request` が `selected.default_steps` を入れており、
最初から 20 歩で回っていた。ずれていたのは画面の目安時間の方である。

`./mf.sh test` 799 passed（新規 1 件）。

## 写真を撮ったままの解像度で直せるようにする（2026-09-01）

利用者から「自分で撮った写真の透かし除去と画質改善をしたい」。透かし除去は
「一部だけ直す」で今日できるが、**写真を 2048px に縮めてからでないと通らなかった**。
透かしを消すために写真全体の解像度を捨てることになる。

`MAX_IMPORT_PIXELS = 2048 * 2048` は strict edit を入れたとき（d08dae4）の丸い数で、
根拠は残っていない。**strict edit は元画像の解像度をモデルに渡していない。**
生成されるのはマスクの外接矩形＋64px の切り抜きだけで、原寸の元画像へ貼り戻す。
縮小は何も守っていなかった。

何が実際に縛るかを測った（合成 + 検証、原寸 RGBA を数枚持つ）。

```text
   3.1MP  合成 0.81s  検証 0.24s  PNG  4.6MiB  peak RSS  139MiB
  12.2MP       2.90s       0.91s      13.6MiB           433MiB   ← 携帯の標準
  24.4MP       5.22s       1.71s      22.2MiB           828MiB   ← 一眼の標準
  48.0MP       9.16s       3.27s      35.6MiB          1607MiB
```

VRAM は使わない。縛るのは core の RAM である。**24,000,000 画素**に置いた。48MP は
1 ジョブが 1.6GB を抱えるので取らない。動画は尺のぶんだけ復号するため、
`MAX_VIDEO_IMPORT_PIXELS` として 2048x2048 のまま分けた。

worker 側にも同じ 2048 があり（`strict edit dimensions must be in the range 1..2048`）、
こちらも画布の寸法にしか使っていない。同じ線に揃えた。境界の都合で core を
import できないので、値を両方から確かめる試験を置く。

### 実機（R9700 / gfx1201）

4032x3024（12.2MP）の写真に透かしを焼き、その上だけを塗って worker を直接回した。

```text
取り込み           HTTP 201  2.68s   13.57MiB を原寸のまま
生成               1.69s（読み込み 5.42s）  ← 塗った範囲だけを作るので寸法に依らない
出力               4032x3024  13.70MiB
保護画素の差       0（image.strict_edit.unmasked_pixel_diff 通過）
変わった範囲       (3640, 2860, 4001, 2971) = 塗った範囲そのもの
```

透かしは消え、周囲は原寸のまま無傷だった。

### 見られなくなる問題を先に塞ぐ

原寸の写真は PNG で 13.6MiB あり、workspace の転送上限（12MiB）を超える。
`assets.content` はこれを**断っていた**ので、上限だけ上げると「透かしは消せたが
見られない」になる。見るための縮小版（1600px / 2MiB、実測 220KiB）を返し、
縮めたことを画面に書く。原寸は保存で取り出せる（`assets.export` は host へ
ファイルのまま渡すので、この上限に縛られない）。

画面の縮小は、モードで行き先を変える。画像全体を作り直すモードは今までどおり
envelope に収める。「一部だけ直す」だけが原寸を保つ。

`./mf.sh test` 803 passed（新規 4 件）。

## 写真を作り直さずに拡大する（2026-09-01）

利用者の「画質改善」に応える機能が無かった。あるのは生成と編集だけで、「全体を
直す」や「似た別案を作る」は**画像全体を作り直す**。写真の画質を上げる道具ではない。

拡散モデルに「良くして」と頼むのは、写真に対しては誤りである。SwinIR
（Apache-2.0, Liang et al.）の実写 4 倍を入れた。標本化しないので prompt も seed も
無く、同じ絵からは同じ絵が出る。

### 全体を 1 度に通すと入らない

```text
512x384 を丸ごと      43.6 秒   peak VRAM 8.61 GiB   ← 注意機構が面積の二乗
```

写真の大きさでは載らない。256px のタイルに 32px の重なりで処理し、重なりは
平均で溶かす。VRAM がタイルで決まるので、寸法に依らなくなる。

### 実機（R9700 / gfx1201）

```text
0.31MP ->  4.9MP    6.3s   peak VRAM 0.82 GiB   PNG  5.4MiB
0.79MP -> 12.6MP   20.0s              0.81 GiB      15.7MiB
1.12MP -> 18.0MP   24.7s              0.81 GiB      23.2MiB
1.50MP -> 24.0MP   35.6s              0.82 GiB      35.8MiB   ← 上限ちょうど
読み込み 0.12 秒 / cold VRAM 0.06 GiB
```

入力 1 メガ画素あたり約 21.5 秒。**入力の上限は 1,500,000 画素**に置いた。4 倍にすると
16 倍の画素数になるので、これが取り込みの上限（24,000,000 画素）に収まる最大である。
超える画像は、選べるのに作れない値にならないよう受付で断る。

倍率は重みが持っている。核が 1 度だけ掛け算をして出力寸法を決め、画面にも worker にも
させない。別の倍率の重みを足したときに片方だけ直る、という形にしないためである。

### 依存を足すときの固定

`torchvision` を固定せずに入れて、**実機の image runtime を壊した**。pip が PyPI の
最新を選び、それが要求する CUDA 版 torch で ROCm の torch を置き換えた
（torch 2.13.0+cu130、`cuda.is_available()` が False、transformers の遅延 import まで
連鎖して停止）。`requirements.txt` から入れ直し、CUDA の残骸を external して復旧。
生成 1.6 秒で復帰を確認した。

固定すれば find-links の ROCm wheel が選ばれ、torch は触られない
（`torchvision==0.25.0+rocm7.2.1` が入り、torch は据え置き）。**版を書かない
`pip install` を runtime に対して打たない。**

`./mf.sh test` 806 passed（新規 3 件）。

## 加工と生成を分ける（2026-09-01）

利用者から「完全に画像生成しかできないように見える」「加工と生成が混ざっているなら
適切に処置して」。実機の画面を見ると、そのとおりだった。編集は写真を添付して初めて
現れるので、**写真を直しに来た人には入口が無い**。

媒体に「写真を直す」を足した。線は「元の絵が残るか」で引く。

```text
写真を直す（加工）  一部だけ直す / 画質を上げる / 外側を広げる
画像を作る（生成）  文章から / 全体を直す / 似た別案 / 参考を足して直す
```

写真モードでは、作る道具（サイズ・枚数・モデル選択・LoRA・演出）を一切出さない。
出すと「作る」画面に見え、直しに来た人が自分の用事を見つけられない。

### 拡大が選べるのに送れなかった

同時に、実機で報告された失敗を 4 つ直した。いずれも**黙って落ちる**形だった。

1. **SwinIR が土台のモデル一覧に出ていた。** 拡大は絵を大きくするだけで作れない。
   選ぶと、その利用者のあらゆる「作る」が `model_unavailable` で落ちた（実機で再現）。
   `has_runtime` と同じ理由で、選べても作れないものを出さない。
2. **拡大なのに指示欄が必須だった。** 空のまま押しても理由が出ない。拡大は指示を
   取らないので、欄ごと隠して検査からも外す。job の名前だけ核が付ける。
3. **送信する内容が拡大に合っていなかった。** 寸法・`strict_edit`・枚数を付けて
   送っており、受付が「倍率から決めます」と断る。付けない。
4. **読めない画像を「選んでいない」と同じ見た目にしていた。** 選べたのに何も
   起きないように見える。理由を出す。

### 加工した写真が添付できない

`createImageBitmap` に `imageOrientation` を渡していなかった。EXIF で回している写真は
ブラウザとサーバで縦横が食い違い、寸法の一致を要求する「一部だけ直す」が受付で断られる。
向きの付いた写真だけ添付できない、という形で出ていた。見えているとおりに開く。

canvas も直した。携帯の canvas には面積の上限があり、超えると `toBlob` が投げずに
`null` を返す。そのまま `File` を作ると壊れたものを送っていた。入らなければ半分ずつ
落とし、実際に用意できた寸法を表示する。

また、形式が PNG / JPEG でないものは寸法が足りていても canvas を通す。以前は大きい
写真が必ず縮小され、その途中で PNG に直っていたので表に出ていなかった。原寸で
預かるようにした結果、HEIC がそのまま送られて受付で断られる経路ができていた。

実 Chrome で確認（写真モードに切り替え、1024x768 を添付）。

```text
ラベル        ＋ 直したい写真を選ぶ / 送信ボタン「直す」
生成用の欄    サイズ・枚数・モデル選択・LoRA すべて非表示
編集の選択肢  一部だけ直す / 画質を上げる / 外側を広げる
拡大の案内    1024×768 → 4096×3072（およそ 17 秒）
上限超        この画像は大きすぎます。1,500,000 画素までを 4 倍にできます。
拡大時        指示欄は隠れ、送信前の検査も通る
```

`./mf.sh test` 806 passed。

## 手元の端末へ保存する／ライブラリから直す（2026-09-01）

利用者から iPhone で 2 件。

### 「保存先を選べませんでした」

保存は `host.files.export`、つまり **ControlDeck が動いている機械のファイル選択**
だった。手元が携帯だと選ばせる相手が別の機械なので、必ずここで終わる。

見ている端末へ保存する経路にした。共有シートがあればそれを使い（iOS はここから
「画像を保存」で写真に入る）、無ければ普通のダウンロードにする。埋め込みの iframe には
`allow-downloads` が付いているので、どちらも通る。host のファイル選択は、同じ機械で
使っているときの控えとして残す。

原寸は表示用とは別の経路で取る。`assets.content` は 12MiB を超えると縮小版を返すので、
それを保存すると小さくなったことに気づかないまま原寸を失う。`assets.bytes` を足し、
4MiB ずつに区切って運ぶ（base64 が 4/3 に膨らんだうえで 1 つの socket message に
載る必要がある）。実測: 19.8MiB の PNG を、byte 単位で一致したまま取り出せた。

### 「編集ボタンを押しても画像が添付されない」

**そのとおりで、何もしていなかった。** ビューアを閉じて「『画像を追加』から
読み込ませてください」と案内文を出すだけだった。実際に添付する。

原寸を取ってから file input に入れ、普段の添付とまったく同じ道を通す。着地は
「写真を直す」にした。生成側へ落とすと、作り直す選択肢しか出ないうえ、元画像が
モデルの寸法（1024x768）まで縮められる。

あわせて、写真モードでは何を選ぶ前から原寸を保つようにした。縮めてから選び直させると
canvas を 2 度通ることになり、携帯では目に見えて待たされる。例外は「外側を広げる」で、
これは画布ぜんぶをモデルが描くため、モデルが出せる寸法に収める必要がある。

実 Chrome で確認。

```text
原寸の取り出し   19.8MiB を byte 単位で一致（表示側は縮小版を返している）
ライブラリの編集 1200x900 を原寸のまま添付・媒体は「写真を直す」・
                 選択肢は 一部だけ直す / 画質を上げる / 外側を広げる
```

`./mf.sh test` 807 passed（新規 1 件）。

## 写真モードが押されて見えず、選択肢も出ていなかった（2026-09-01）

利用者から実機で 3 件。写真モードを入れた直後の作りが、いくつも不足していた。

### 選んでいるのに押されて見えない

`mediaSwitchButtons()` が image と video しか返しておらず、写真の button に
`aria-pressed` が付かない。画面の中身は写真モードなのに、印だけが画像のまま残る。
**媒体を足したらここに足す。**

### 高画質化が画面に無かった

`#edit-block` に `data-image-create` が付いていた。写真モードは
`[data-image-create]` を消す規則なので、**編集の選択肢そのものが消えていた**。
DOM には在るので、browser 越しの確認で `.edit-action` を数えるだけでは通ってしまう
（実際そうやって見落とした）。表示されているかを見る。

### 並びが「作る」のままだった

指示 → 添付 の順なので、写真を直しに来た人が最初に文章を求められる。利用者の
「変更は不要で高画質化したいだけの場合も対応して」はこの形のことだった。写真モードでは
添付 → 何をするか → 指示 の順に並べ替え、拡大では指示欄ごと消す。

```text
添付 138px / 編集の選択肢 218px / 指示 534px（実 Chrome）
拡大を選ぶと  指示欄 非表示・案内「900×1200 → 3600×4800（およそ 23 秒）」
              送信前の検査も通る
```

### 生成側の選択肢を減らしてしまっていた

写真モードに「直す」を移したとき、生成側からも外していた。利用者から「以前は複数
あったのに 2 つになっている。写真モードとは別で戻して」。**そのとおりで、入口を
増やすつもりが既にある道を塞いでいた。** 生成側は写真モードを足す前と同じ一式に戻す。

```text
画像を作る  一部だけ直す / 外側を広げる / 全体を直す / 似た別案を作る / 参考を足して直す
写真を直す  一部だけ直す / 画質を上げる / 外側を広げる
```

拡大だけは生成側に置かない。元の解像度を要するのに、生成側は添付を envelope まで
縮めるので、縮めた絵を拡大することになる。

`./mf.sh test` 807 passed。

### ライブラリの編集は、選んでいるモードへ入れる

「これを編集」を写真モードへ移していたが、利用者から「選択中の機能モードへ添付して」。
**そのとおりで、利用者が選んだ場所を勝手に捨てていた。** 媒体は変えない。

```text
画像を作る で押す → 画像を作る のまま（envelope に合わせて 1024x768）
写真を直す で押す → 写真を直す のまま（1200x900 原寸）
動画を作る で押す → 動画を作る のまま（動かす元の画像として添付）
```

あわせて、編集を出さない媒体では選択肢を DOM から消す。隠れているだけの前の
選択肢は、「見えていないこと」の確認を素通りする。

## ブレを直す／顔が崩れる件の調査（2026-09-01）

利用者から 2 件。「ブレとかも消せるか」「透かしを消した所が顔だと崩壊する。他の
画像を参考に補完できるか」。

### ブレ補正は入った

拡大（SwinIR）は BSRGAN 系の劣化を想定した学習で、動きブレを取るものではない。
NAFNet の GoPro 版（MIT, Chen et al.）を足した。

丸ごと通すと 1.4MP で 2.94 GiB。拡大と同じタイル処理に載せると寸法に依らなくなる。

```text
1.40MP  1.65s   3.00MP  3.14s   7.68MP  7.55s   peak VRAM 405,778,944 B 一定
合成した動きブレ  PSNR 23.10 dB -> 24.11 dB（丸ごとなら 24.66 dB）
```

倍率 1 なので寸法は変わらず、入力の上限は取り込みの上限（24,000,000 画素）そのままで
よい。拡大と同じ経路・同じ adapter に載せる。どちらも標本化せず、prompt も seed も
持たない。

**最初の測定は誤りだった。** 合成したブレが画像をずらしていたため PSNR が下がり、
「効いていない」と読めた。ずれない形で作り直して測り直した。

### 顔が崩れる件 — 私の仮説は外れた

塗った範囲の切り抜き寸法のまま生成していることが原因だと考え、生成を 768〜1024px へ
上げ、文脈も広げて試した。**実測では逆に悪くなった。**

```text
顔の上の透かし 148x44 を塗って消す
  元の設定（368x320 で生成）   1.4 秒   目がはっきり残る
  変更後（768px へ拡大）      86.6 秒   目が潰れる
```

60 倍遅くなったうえで質が落ちる。仮説を捨てて元に戻した。

崩れるのは**塗った範囲が大きいとき**である。顔の広い範囲を塗ると、モデルはそこに
別人の顔を描く。透かしだけを細く塗れば周りの顔が文脈として残り、実用になる。

### 参考画像は、いまの経路では使えない

adapter は strict edit と `reference_paths` を同時に受ける形になっていたので、
そのまま試した。**参考画像がマスクの中へ縮小コピーとして貼り付いた**（生成 7.3 秒。
条件付けが効いておらず、参考画像そのものが出力になっている）。作り込みが要るので、
使えるものとしては出さない。

`./mf.sh test` 808 passed（新規 1 件）。

## 消して埋める（LaMa）と、拡大モデルの比較（2026-09-01）

利用者から「高画質化に適切な AI を調査して」「透かしを消すと違和感が出る」。

### 透かしを消すと帯になるのは、道具が違うから

いまの「一部だけ直す」は FLUX に**塗った範囲を描き直させて**いる。透かしを消したい
だけの場所でも新しい絵を描くので、絵柄と明るさが変わり、マスクの形の帯が残る。

上流の評価でも、除去は拡散モデルではなく LaMa を採る、とされている
（"LaMa is adopted over traditional diffusion-based methods to preserve original
image characteristics, as diffusion-based techniques often introduce
inconsistencies and artifacts"）。実機で並べると差は明白だった。

```text
顔にかかった透かし（292x36）を消す
  FLUX  25.67 秒   別スタイルの帯が残る
  LaMa   0.42 秒   帯が出ない。周りの網点がそのまま続く
```

LaMa（big-lama, Apache-2.0）を `image.erase` として足し、画面では「消して埋める」に
した。既存の inpaint は「塗った所に描き足す」に改名した。**消すのと描くのは別の
用事である。**

塗っていない所は 1px も変わらない（実測でマスク外の最大差 0）。

費用は写真の大きさではなく塗った範囲で決まる。切り抜いて通すためである。

```text
21.3MP の写真   塗り 300x40     4.23s / 0.58 GiB
                塗り 900x300  115.70s / 3.18 GiB   ← 切り抜きが上限に当たる
                塗り 2000x900 115.86s / 3.19 GiB
```

上限を付ける前は 2000x900 の塗りで 339 秒・14.3 GiB まで伸びた（切り抜きは塗った
範囲の 3 倍角になる）。2,500,000 画素で頭打ちにし、超えたら縮めて通して埋めた所だけ
元の大きさへ戻す。LaMa の出力はもともと滑らかなので、ここで細部は失わない。

### 拡大モデルの比較

OpenModelDB で実写向けとして挙がる 2 つを、同じ写真・同じ機械で回した。

```text
512x683 -> 2048x2732
  SwinIR-M（いま採用）      9.5s   0.82 GiB
  4xNomos8kDAT (CC-BY-4.0) 48.6s   1.57 GiB
  4xNomos8kSCHAT-L         183.7s  2.70 GiB
```

Nomos 系は質感を足す学習をしているぶん粒状感が乗る。手元の試験画像が画面を撮った
もの（網点あり）なので、その粒を強調する形になり、SwinIR の方が素直だった。
**実写の写真での比較はできていない**ので、置き換えは判断しない。速さは 5〜19 倍違う。

### 重みの読み込み

`.safetensors` を `torch.load` に渡していて読めなかった。Hub の blob は拡張子を
持たないので、中身で見分ける（safetensors は先頭 8 byte が長さ、次が `{`）。
big-lama はさらに全体が `model.` で包まれており、spandrel が探す鍵と 1 段ずれる。
剥がしてから渡す。

`./mf.sh test` 808 passed。

## 高画質化で、出す大きさを選ぶ（2026-09-01）

利用者から「画像が荒い写真を高画質化したい」。**両方あるので、大きさを選ばせて
ほしい**との指定。

### 荒い写真の大半が、受付で断られていた

「画質を上げる」はあったが、出す寸法は重みの倍率（4 倍）で固定だった。出力は
取り込みの上限（24,000,000 画素）に収める必要があるので、受ける入力は
1,500,000 画素までになる。**スマホの写真（4032x3024 = 12.2MP）はそこで断られる。**

荒い写真は、小さいとは限らない。もう十分に大きくて、ノイズと圧縮の跡だけが乗って
いる写真の方がむしろ多い。その人に「4 倍にする」しか出していなかった。

重みの倍率の**約数**までを選べるようにした。約数に限るのは、割り切れる縮小だけが
画素の格子を保つからである（面積平均で落とす。補間の種類を選ぶ余地が無く、位置も
ずれない）。網には倍率に関わらず元の写真をそのまま通す。縮めた写真を入れる形には
しない — それでは元の細部を捨ててから直すことになる。

```text
                      前              後
選べる大きさ          4 倍のみ        原寸のまま / 2倍 / 4倍（models.json の宣言）
受ける入力            1,500,000 px    24,000,000 px（取り込みの上限と同じ）
12.2MP のスマホ写真   受付で拒否      原寸で通る
断る対象              写真そのもの    その写真で出せない倍率だけ（収まるものを名指す）
```

入力の上限はもう倍率に依らない。倍率ごとの可否は要求のたびに見る。

### 実測（R9700 / gfx1201、256px タイル・32px 重なり）

同じ 1024x1024 を 3 通りで通した。**費用は出す大きさではなく元画像の面積で決まる**
（どの倍率でも網には同じものを通すため）。VRAM もタイルで決まるので変わらない。

```text
1024x1024 (1.05MP) を入れる
  4 倍  -> 4096x4096  25.51s  24.33s/MP  879,555,072 B
  2 倍  -> 2048x2048  22.18s  21.15s/MP  871,166,464 B
  原寸  -> 1024x1024  21.22s  20.24s/MP  871,166,464 B

4032x3024 (12.19MP) を原寸のまま直す — 前は受付で断られていた大きさ
  原寸  -> 4032x3024  212.1s  17.39s/MP  879,555,072 B  peak RSS 2,036,879,360 B
```

VRAM は 12 倍の面積でも変わらない（タイルで決まる）。大きい方が 1 メガピクセル
あたりは速い（端のタイルの割合が減る）。`per_source_megapixel_sec` は 1.5MP で
測った 21.5 のままにしてある — 17.4〜24.3 の幅の上側で、案内も打ち切りも余裕を
持つ側に外れる。

溜める場所は出す寸法の側へ移した。網の倍率で溜めると、原寸を頼まれたときにも
16 倍の面積を抱える。重なりの数も 3 面から 1 面にした（24MP の出力で 192MB の差）。

worker を実プロセスで回し、同じ 1024x1024 から 1024 / 2048 / 4096 が出ることを
確認した（`upscale_scale` が核 → worker → adapter へ届いている）。

### 出荷済みの「ブレを直す」「消して埋める」が、押すと必ず失敗していた

倍率を通す経路に `scale < 2` の門が残っていた。ブレ補正も消して埋めるも倍率 1 で
同じ経路を通るので、両方ともそこで落ちる。画面には出ているのに押すと失敗する。

main（56897f7）と作業ツリーで、実際の models.json の descriptor を使って核の
解決を回した実測:

```text                     main                                 いま
拡大    OK 3200x2400                          OK 3200x2400  upscale_scale=4
ブレ    FAIL この拡大モデルは倍率を宣言していません   OK 800x600  upscale_scale=1
消して  FAIL この拡大モデルは倍率を宣言していません   OK 800x600  upscale_scale=1
```

前の 2 つの機能追加は adapter までは実測していたが、**核の解決を通していなかった。**
テストも通っていない（テスト環境ではモデルが導入されておらず fake worker へ落ちる
ので、実モデルの経路に入らない）。実一覧の descriptor で解決を回す試験を足した。

画面にも同じ形の取り違えがあった。案内の単価と倍率を引く先が「ブレ補正なら
image.deblur、それ以外は image.upscale」になっていて、消して埋めるを選ぶと拡大の
倍率と単価が出ていた。直し方から capability を引く表にした。実ブラウザで、ブレ補正
が "1024×1024 のまま（およそ 1 秒）"（NAFNet の 1.02 秒/MP）を出し、拡大の 21.5 を
出さないことを確認した。

### 打ち切りを、1 枚の実測ではなく面積で組む

worker の打ち切りは `measured_runtime_sec * 3 + 30` を無出力の猶予にしていた。
SwinIR の実測は 35.6 秒なので猶予は 136.8 秒、1 枚だけ作る直しでは実質 273 秒。
**12.2MP の写真は 4 分掛かるので、上限を上げただけでは受け付けた job が時間切れで
落ちる。** 直しは費用が元画像の面積に比例し、その係数をモデルが宣言しているので、
そこから見積もる。broker へ申告する占有時間も同じ値にした。

### PSNR はこの重みの物差しにならない

採用しているのは `..._SwinIR-M_x4_GAN`、知覚品質へ寄せた GAN 系である。生成した
写真らしい画像（1024x1024）を基準に、荒らしてから直して測った。

```text
A 原寸のまま  JPEG q20 (66,621B) へ荒らし、寸法を変えずに直す
    荒い入力    PSNR 30.40 dB
    直した      PSNR 27.42 dB   21.18s / 879,555,072 B
B 4 倍        256x256 + JPEG q30 (9,131B) から 1024x1024 へ戻す
    LANCZOS     PSNR 23.91 dB
    直した      PSNR 21.71 dB   1.12s / 871,166,464 B
```

**どちらも PSNR は下がるが、目で見ると明らかに良い。** 1:1 で拡大して並べると、
A は JPEG の 8x8 のブロックと色のにじみが消え、木目の筋が基準とほぼ同じに戻る。
B は LANCZOS のぼやけに対して輪郭と質感が立つ。GAN 系は基準に無い質感を作るので
画素単位の一致は落ちる、という既知の性質そのものである。

ずれや明るさの狂いではないことは確かめた（変位を -2..+2 で走査して最良が dy=0,
dx=0、平均 133.66 -> 133.13）。標準偏差だけが 68.16 -> 71.54 と上がっている。
**知覚品質の指標（LPIPS / NIQE）は測っていない。** ブレ補正（NAFNet, L2 学習）で
PSNR を使ったのは正しいが、この重みには当てはまらない。

基準は局所で生成した写真らしい画像であって、**カメラで撮った写真ではない**。
前回からの「実写の写真での比較はできていない」は解消していない。

### 実ブラウザ

`scripts/ux_upscale_scale_e2e.py`（standalone、Chromium headless、1280x900）。

```text
1024x1024   原寸のまま / 2倍 / 4倍 が出て、既定は 4倍
            案内 "1024×1024 → 4096×4096（およそ 23 秒）"
            原寸を押すと "1024×1024 のまま（およそ 23 秒）"（矢印は出ない）
2000x1500   原寸のまま / 2倍。4 倍は 48MP で上限を超えるので出さない
            "…｜4倍は 24,000,000 画素を超えるので選べません"
4032x3024   選べるのが 1 つなので選択肢そのものを出さない
            "4032×3024 のまま（およそ 4 分）｜2倍・4倍は…選べません"
            前はここで "この画像は大きすぎます" だった
```

倍率は models.json の `target_scales` から出す。画面は決め打ちを持たない。

### 未実施

```text
ControlDeck 統合下での end-to-end   dev の service は host lease を要求するため、
                                    HTTP から実 GPU 生成を回せない。核の解決・
                                    worker 実プロセス・実ブラウザまでで確認した
実写の写真での画質比較              手元にカメラの写真が無い
LPIPS / NIQE                        依存を足していない。目視のみ
```

`./mf.sh test` 823 passed（新規 15 件）。

## 塗った所に描き足す — 書き換えになっていた（2026-09-01）

利用者から「塗った場所に書き足すがうまくいかない」「**書き足すというより、書き換える
じゃないか**」。そのとおりで、実際に書き換えていた。

### 塗った所を model へ渡していなかった

経路はこうなっていた。塗った範囲の外周 64px を切り出す → **その切り抜きを丸ごと
描き直す** → 返ってきた絵から塗った所の画素だけ採る。`self.pipeline(image=..., prompt=...)`
にマスクは入っていない。マスクは切り抜きの位置決めと、後段の合成にしか使っていない。

model は「塗った所に描け」と聞いていない。切り抜き全体を prompt で描き直し、それが
塗った形に切り抜かれる。**書き足しではなく書き換えである。**

実機で再現した（1024x1024、空に 200x170 の楕円、"a small red bird flying"）:

```text
切り抜き 329x299 -> 336x304 で全体を描き直し、47.0 秒
  楕円の形がそのまま帯として出る（描き直しで露出が変わり、楕円の中だけ差し替わる）
  鳥は楕円の上端に小さく、大半が切り落とされている
```

diffusers 0.40.0 には `Flux2KleinInpaintPipeline` がある。いま採用している重みの
ままで使える（構成要素は base と同一なので、載せ直しも追加の常駐も無い）。

### 2 つめの罠 — 蒸留の宣言が引き継がれない

`Flux2KleinInpaintPipeline(**pipeline.components)` は `is_distilled` を受け取らない
（構成要素ではないので `components` に入らない）。既定は False で、そのとき pipeline は
classifier-free guidance を前提にする。klein は蒸留済みで guidance が焼き込まれており、
そこへ 1.0 を渡すと **prompt がほとんど効かない**。

実機では、帯は消えたが頼んだ鳥が出ず、塗った所が周りの続きで埋まるだけになった。
これは「消して埋める」の動きであって、描き足しではない。`base.config.is_distilled` を
引き継いだら prompt が効いた。

塗った範囲を振って確かめた（"a large red hot air balloon"、4 歩）:

```text
塗り  3.2% (200x170)   気球が塗った所に出る
塗り 17.4% (480x380)   気球が塗った範囲を埋める
塗り 40.7% (820x520)   大きな気球
いずれも塗っていない所（杭・草・砂利）は元のまま
```

### 周りをどれだけ見せるかは、幅ではなく割合で決まる

塗った所を渡す経路にしても、塗った範囲が広いと model が塗った所の中に**自分の背景
ごと**描いた（曇り空の中で、塗った楕円の中だけが青空になる）。効いていたのは周りの
幅そのものではなく、**切り抜きに対して塗った所が占める割合**だった。

480x380 の塗りに "a large red hot air balloon" を頼んで、周りの幅を振った実測:

```text
周り  64px   切り抜き 568x504（塗り 63%）   18.0s  17.9 GB  楕円の縁が見える
周り 160px   切り抜き 664x600（塗り 43%）   87.3s  18.6 GB  曇り空に馴染む
周り 320px   切り抜き 824x760（塗り 29%）  154.6s  19.9 GB  馴染む。費用 8.6 倍
```

固定 64px をやめ、塗った所の長辺の 1/3（下限 64px）にした。480 に対して 160 になり、
透かし程度の小さな塗りは下限が効くので費用がほとんど変わらない。

切り抜きは元画像の大きさと塗った範囲で決まるので、大きな写真に広く塗ると際限なく
伸びる。attention は面積の二乗で効くため、切り抜きだけに 1024x1024 の上限を掛けた。
**生成そのものには掛けない** — 掛けると、いま 2048 まで通っている参考編集が黙って
縮む。前はどちらにも上限が無く、大きな塗りは card に載らない大きさまで伸びていた。

### 直した後（R9700 / gfx1201、adapter の経路そのまま）

```text
             所要     peak VRAM        塗っていない所の最大差
bird        38.5s   16,677,486,080 B   0
balloon     91.7s   18,430,786,560 B   0
flower      40.0s   17,132,960,256 B   0
（前）      47.0s   —                  帯が残り、頼んだものは楕円の縁で切れる
```

`validate_strict_edit` は 3 件とも passed。塗っていない所の最大差を独立にもう一度
測っても 0 だった。VRAM は生成の実測（29.6GB）より下がる。

### 残っている粗さ

塗った範囲が広く、頼んだものが自分の背景を持つ場合（空に浮かぶ気球など）、model は
塗った所の中にその背景ごと描くので、**塗った形が縁として見えることがある**。周りを
広く見せたことで大きく減ったが、消えてはいない（気球は雲の一部が縁に残る。鳥と花は
縁が見えない）。書き換えではないので写真そのものは壊れない。

### 未実施

```text
ControlDeck 統合下での end-to-end   dev の service は host lease を要求する。
                                    adapter の経路と strict 検証までで確認した
実ブラウザ                          画面側は変えていない（文言も操作も同じ）
周りの割合 1/3 の根拠                1 件の塗りで測った。他の被写体・他の写真では
                                    測っていない
```

`./mf.sh test` 810 passed（新規 2 件）。

## FLUX.2-dev 32B を GGUF で載せる（2026-09-01）

利用者から「Flux で、私の環境で動くより大きなモデルを下さい」「FLUX.2 dev 32B で
別ランタイム含め用意して」「Gguf」。

### 駆動系は既にあった

`stable-diffusion.cpp` の pinned build（`97d2990`、2026-08-19）に `docs/flux2.md` が
入っている。**MiniMax H3 で既に使っている pin がそのまま FLUX.2 に対応していた**ので、
新しい commit を立てる必要は無かった。同じ commit を gfx1201 / HIPBLAS / Release で
建て直した（Ninja、-j8）。

```text
sd-cli sha256 7d4b5a3577db1785158d2feab3a10f55fcde42b1e4c036908991d6aaedc27494
--list-devices  ROCm0 = AMD Radeon AI PRO R9700 / gfx1201 / 32,624 MiB
                ROCm1 = 統合 GPU gfx1036 / 15,547 MiB（掴ませない）
```

前回記録の `7c2aebea…` とは異なるが、同じ commit である（前回は Unix Makefiles で
-j1、今回は Ninja で -j8）。

### 重みは 3 つのリポジトリから来る

```text
拡散  flux2-dev-Q4_K_M.gguf                     20,082,414,560 B  city96/FLUX.2-dev-gguf
文章  Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M 14,333,922,848 B  unsloth（Apache-2.0）
VAE   full_encoder_small_decoder.safetensors        249,519,092 B  BFL small-decoder（Apache-2.0）
                                            合計 34,665,856,500 B
```

**3 つとも gated ではない。** 本体の `black-forest-labs/FLUX.2-dev` は gated だが、
VAE は上流の文書が代替として案内している別リポジトリの Apache-2.0 版で足りる。
HF のトークンは要らなかった。

FLUX.2 は CLIP+T5 をやめて汎用の言語モデルを文章符号化器に据えた設計である。Klein 4B
でも同じ形で、実測すると text_encoder 8.05GB（Qwen3）/ transformer 7.75GB / vae 0.17GB。
「4B」のリポジトリが 16GB あるのはそのためで、dev ではここが Mistral 24B になる。

registry の導入判定は、weight の実体が**主リポジトリの配下**にあることを求める
（`_weight_matches`）。MiniMax H3 が別リポジトリの VAE を抱えているのと同じ形に
組み、blob 名は宣言した sha256 に一致させた。

### `--offload-to-cpu` はこの機械では成立しない

上流の例に従って `--offload-to-cpu` で回すと、**11 分進まなかった**。

```text
文章符号化まで  正常（12,057.93 MB を ROCm0 へ展開 → 10.16 秒 → 解放）
拡散本体        19,152.06 MB を RAM へ展開する段階で停止
                CPU 87.7%（1 コア）/ GPU 3% / RSS 25.53 GB / swap 2→4 GB
```

重みを RAM に置いて VRAM へ流し込む方式なので、RAM 30GB を使い切って swap と往復
していた。計算ではなくメモリ移動で詰まっている（GPU が遊んでいる）。

拡散を直接 VRAM に置き、文章モデルだけ RAM に残す配分に変えたら通った。動画側の
MiniMax H3 と同じ `te=cpu,diffusion=ROCm0,vae=ROCm0` である。

### 実測（R9700 / gfx1201）

```text
配置   総計 34,608.50 MB = VRAM 19,271.14 MB（拡散）+ RAM 15,337.36 MB（文章）
       作業領域 flux 656.00 MB + vae 1,248.50 MB（VRAM）

512x512   4 歩   条件付け  7.14s  標本化  21.39s  復号 0.80s  全体  31.48s
1024x1024 20 歩  条件付け 13.01s  標本化 161.76s  復号 1.91s  全体 181.91s

peak VRAM 26,395,885,568 B（84 サンプル、2 秒ごと）/ 31.86 GiB
最大 RSS  26,911,692 KiB   Swaps 0
```

4 歩では網目状のムラが残る。dev は蒸留された歩数モデルではないので、既定を 20 歩に
した。20 歩の 1024x1024 は写真として通る出来だった。

Klein 4B（1024x1024、4 歩、20.8 秒）に対して **8.7 倍遅い**。

`policy_rank` は**小さいほど優先**である（`router.py` が昇順に並べる）。最初これを
逆に読み、`auto` を 0 にして「おまかせの候補から外した」つもりでいた。実際には
**おまかせで最優先**になる置き方で、1 枚 3 分が既定になるところだった。速さで選ぶ
方針（auto / fast / balanced / low_vram）では 4B より大きい数、質で選ぶ方針では
小さい数にした。試験は絶対値ではなく 4B との前後関係で書いた。

### 本番の worker を実プロセスで通した

評価用の経路ではなく、`worker_packs.image.worker` に本番と同じ payload を渡した。

```text
outputs        1024x1024 RGBA PNG 1,851,581 B
generation_sec 179.02
runtime_version 97d2990807fe6d558e395f8764198d7c7e7b411c
placement      text_encoder=cpu / diffusion=ROCm0 / vae=ROCm0
```

`runtime_version` は diffusers の版を返していた。native の経路は diffusers を通らない
ので、そのまま記録すると嘘になる。adapter が名乗る値を優先し、無いときだけ diffusers
の版に落ちるようにした。

画像側にも native の駆動系を使うものが出たので、核は画像 worker にも
`MEDIA_FORGE_NATIVE_RUNTIME_ROOT` を渡すようにした。渡さないと adapter は起動できない。

### 未実施

```text
ControlDeck 統合下での end-to-end   dev の service は host lease を要求する。
                                    本番 worker の実プロセスまでで確認した
参照画像による編集                  sd-cli は `-r` を持つが測っていない。
                                    adapter は受けたら断る
Klein 4B との画質比較               同じ prompt・同じ seed での並べ比べはしていない
歩数の詰め                          20 歩で採った。28〜50 は測っていない
実ブラウザ                          画面側は変えていない（一覧に 1 つ増えるだけ）
```

`./mf.sh test` 810 passed（新規 2 件）。

## iPhone の写真が投入できなかった（2026-09-01）

利用者から「写真だが定型のサイズしか入らないの？」「任意のサイズに切り取った画像を
iPhone で選択しても投入されない」。

### 変換する仕組みはあったのに、選択でそこまで届いていなかった

```html
frontend/index.html:238
  <input id="source-file" type="file" accept="image/png,image/jpeg">
```

iPhone の写真は既定で HEIC である。画面には HEIC を canvas で PNG へ直す経路が
**既にあった**（`converting = !IMPORTABLE_TYPES.has(file.type)`、コメントにも
「端末の写真は HEIC のことがある」と書いてある）。届いていなかっただけである。
選択の絞り込みを `image/*` にした。参考画像の入口も同じだったので揃えた。

塗った範囲の入口（`#mask-file`）は画面が作る PNG しか受けないので、そのままにした。

### 復号を端末に任せる経路を足した

`createImageBitmap` が HEIC を断る版がある。そこで諦めると「選んだのに何も
起きない」になるので、断られたら `<img>` へ落とすようにした。Safari は `<img>`
なら HEIC を復号する。EXIF の向きは、どちらの経路でも見えているとおりに開く。

`ImageBitmap` 以外は `close()` を持たないので、呼び出しを `close?.()` にした。

### 断りが、出したそばから消えていた

読めない画像を選ぶと `showError` は出ていたが、その後 `refreshAttachment` の末尾と
`selectEditMode` の 2 か所が `clearError()` を呼んで消していた。**画面に残るのは
添付欄の小さな文字だけ**で、これも「選んでも何も起きない」の一因だった。

添付が読めていない状態を `state.attachProblem` として持ち、`clearError()` は立って
いる断りを残すようにした。次の写真を選んだときに下ろす。

### 実ブラウザ（`scripts/ux_phone_photo_e2e.py`、Chromium headless、390x844）

```text
accept              source / reference とも image/*
IMG_0001.HEIC       1007x661 のまま載る。送るのは image/png へ変換したもの
IMG_0002（type 空） 同上。形式を名乗らない端末でも通る
shot.png            そのまま送る。余分な canvas を通さない
notes.txt           載せない。「読み込めませんでした」が画面に残る
```

**Chromium は HEIC を復号しない。** ここで確かめられるのは「PNG / JPEG 以外が選択を
通り、変換されて原寸のまま載るか」までで、実際の HEIC 復号は端末側の仕事である。

### 未実施

```text
実機の iPhone            HEIC の復号そのものは Chromium では測れない
ControlDeck の埋め込み下  standalone で確認した。iframe 越しは未確認
```

`./mf.sh test` 808 passed（画面のみの変更で、新規テストは実ブラウザ側）。

## 直すだけの道具が、土台のモデルとして並んでいた（2026-09-01）

利用者から「Flux がモデル選択に出ない」。出ない理由は稼働中がリリース版で PR が
未 merge だったからだが、確認の途中で**別の不具合**が見つかった。

土台の一覧に「NAFNet ブレ補正」と「LaMa 消して埋める」が並んでいた。どちらも
「無から絵を作る」ことはできない。実測でどれも落ちる。

```text
model_policy=manual で 512x512 の生成を投げた
  tog/nafnet-models               failed  model_unavailable
  AEmotionStudio/lama-inpainting  failed  model_unavailable
  mikestealth/SwinIR              failed  model_unavailable
```

`isBaseModel` が**拡大 1 つを名指しで除いていた**のが原因である。

```js
return capabilities.some((name) => name !== "image.upscale");
```

この関数のコメント自身が「ここに並ぶと、選んだ利用者のあらゆる『作る』が
model_unavailable で落ちる（実機でそうなった）」と書いている。拡大を足したときに
書かれた規則が、ブレ補正と消して埋めるを足したときに追随していなかった。

除く根拠を名前から性質へ変えた。「直すだけ」の capability しか宣言していないものは
土台になれない。次に直す道具を足しても、その集合へ 1 行足すだけで済む。

### 実ブラウザ（`scripts/ux_base_model_choices_e2e.py`）

```text
前  おまかせ / FLUX.2 Klein 4B / Segmind SSD-1B / NAFNet ブレ補正 / LaMa 消して埋める
後  おまかせ / FLUX.2 Klein 4B / Segmind SSD-1B
```

一覧に並ぶ数と選択肢の数が一致すること、直すだけの道具が並ばないこと、作れるものが
落ちていないことを、カタログの宣言から導いて確かめている。

`./mf.sh test` 808 passed（画面のみの変更で、証跡は実ブラウザ側）。

## 使うモデルの一覧が、頼む操作に追随していなかった（2026-09-01）

利用者から「FLUX.2-dev を iPhone で選択すると使えるモデルがないと出る」。

### モデルによって、できることは違う

FLUX.2-dev は `image.text_to_image` しか宣言していない。編集は宣言していない。
それでも編集のときに一覧へ並んでいたので、選んで押すと落ちる。実機
（インストール版 0.21.0）で確認した。

```text
image.generate  manual=city96/FLUX.2-dev-gguf  -> routing 通過
image.edit      manual=city96/FLUX.2-dev-gguf  -> model_unavailable
```

画面はこれを「使えるモデルがありません。」と出す。**モデルは入っていて健全で、
選択肢にも並んでいるのに、である。**

一覧を組むときに、いま頼もうとしている操作が要る capability を見るようにした。
添付が無ければ `image.text_to_image`、あれば選んでいる直し方の capability。まだ
直し方を選んでいないときは絞らない（絞る根拠が無いのに減らすと、選べたはずの
ものが消える）。

指定していたモデルが一覧から消えたときは、`renderModelChoice` が既におまかせへ
戻す作りになっていた。そこはそのまま効く。

### 直すだけの操作では、そもそも選ばせない

拡大・ブレ補正・消して埋めるは capability でモデルが 1 つに決まる。選ばせる意味が
無いうえ、前に指定したモデルが残っていると、それが直せないモデルなので同じ
`model_unavailable` になる。`#model-choice` を出さず、指定も外す。

`data-generate-only` という属性が markup に付いていたが、参照している所は無かった。
死んだ宣言に頼らず、`REPAIR_MODES` から出す。

### 1 件も無いときの案内

「使えるモデルがまだありません。設定から導入してください」は、**入れてはあるが
この操作ができない**ときには誤りである。次にやることが違う（導入ではなく、別の
直し方を選ぶ）。2 つを分けた。

なお `model.installed && model.healthy` を含む行は、契約試験が「LoRA を除いて
いるか」を見張っている。ここで訊いているのは土台に選べるかではないので、
`anythingInstalled()` として別の名前で書いた。試験は正しく反応した。

### 実ブラウザ（`scripts/ux_model_choice_follows_the_job_e2e.py`、390x844）

```text
添付なし          文章から作れるものが並ぶ
写真 + 全体を直す  文章からしか作れないものが消える。指定も auto へ戻る
写真 + 画質を上げる 使うモデルの欄そのものが出ない
```

`./mf.sh test` 827 passed。

## FLUX.2-dev は編集できる。私が測らずに「できない」と書いていた（2026-09-03）

利用者から「本当に画像変更できないの？改めて Flux dev の仕様書や Reddit などを
チェックして」。**指摘のとおりで、私の誤りだった。**

### 何を間違えたか

FLUX.2-dev を入れたとき、`image.text_to_image` だけを宣言した。参照編集を測って
いなかったからである。そこまでは正しい。誤りはその後で、**自分が書いた宣言を根拠に
「モデル側の制約でできない」と説明した**ことである。循環している。

モデルカードには最初からこう書いてある。

```text
"a 32 billion parameter rectified flow transformer capable of generating,
 editing and combining images based on text instructions"
"excels in single-reference editing and multi-reference editing"
参照画像は最大 10 枚、4 メガピクセルまで
```

自分で引用した sd.cpp の `docs/flux2.md` にも「All variants support image editing
with the `-r` flag for context inputs」とあった。読んでいたのに、宣言の方を信じた。

なお**ライセンスは非商用のままである**（`flux-non-commercial-license`）。検索結果に
Apache-2.0 とあったのは Klein との取り違えで、Hub の API で確認した。

### 実測（R9700 / gfx1201、1024x1024、20 歩）

```text
生成のみ              181.9 秒
参照 1 枚の編集       436.1 秒（7:16）   最大 RSS 18.8 GB  Swaps 0
参照 2 枚の合成       724.0 秒（12:04）  最大 RSS 21.4 GB  Swaps 0
塗った所を指す編集    212.9 秒（3:33）   最大 RSS 22.0 GB  Swaps 0
```

参照 1 枚で 2.4 倍、2 枚で 4.0 倍。条件付けの系列が参照ごとに伸びるので素直に
比例する。2 枚の合成では「image 1 の杭を image 2 の納屋の前に」という**番号での
指定が効いた**（`--increase-ref-index`）。

単一参照編集は、元の杭のひび割れ・樹皮・節・垂れた草の茎まで保ったまま季節だけを
冬に変えた。参照編集として期待どおりに働く。

### 塗った所は「守る範囲」ではなく「指す場所」

`--mask` を渡すと、頼んだ鳥の群れは塗った楕円の中に出た。ただし**塗っていない所も
描き直されている**。

```text
塗った所の外  最大差 224  平均 3.52   ← 1px も変わらない、ではない
塗った所の中  最大差 246  平均 53.88
```

この repo の strict edit は「塗っていない所は 1px も変わらない」を不変条件にして
いる。貼り戻せば差は 0 になり `validate_strict_edit` も passed になる（GPU を使わず
確かめた）。**しかしそれをすると塗った形が縁として出る。** model が描いた空と元の
写真の空とで露出が違うためで、PR #195 で Klein 4B について直したのと同じ現象である。
あのときは塗った所を model へ渡すことで解いたが、この経路では `--mask` を渡しても
model は絵全体を描き直して返すので、同じ手が効かない。

守れない保証を名乗るより、守らないと言う方を選んだ。`image.inpaint` は宣言しない。
代わりに `image.masked_edit` を足した。**塗った所は指す場所である**、という別の
capability である。画面では「塗った所を指して直す」、保証欄は「画像全体が変わる
ことがあります」。Klein 4B の「塗った所に描き足す」（1px も変わらない）はそのまま残る。

`strict_edit` を真で受けたら断る。名乗らせると、核が後段で守れたことを検証して
しまう。

### 本番の worker を実プロセスで通した

```text
参照編集        1024x1024  生成 406.5 秒  postprocessing ['pil.convert.rgba']
塗った所を指す  1024x1024  生成 250.5 秒  同上
```

`postprocessing` に strict の合成が入っていない。保証を名乗らない経路なので、
入っていたら誤りである。塗った所を指す編集では、合成しないぶん縁が出ない。

### 未実施

```text
参照 3 枚以上          モデルカードは 10 枚までと言う。2 枚までしか測っていない
image.variation        宣言していない。測っていない
ControlDeck 統合下     本番 worker の実プロセスまでで確認した
実ブラウザ             「塗った所を指して直す」の画面は未確認
```

`./mf.sh test` 827 passed。

### 触っていない不安定なテスト

`test_workspace_websocket_chunk_import_exceeds_single_message_bound_and_cleans_up` が
ときどき落ちる。websocket を閉じた後の後始末を 5 秒待って見る作りで、機械が忙しいと
間に合わない。**このスライスとは無関係である。** 負荷を揃えて交互に 10 回ずつ回した:

```text
origin/main    passed=4  failed=6
このブランチ    passed=5  failed=5
```

手を触れていない main の方が多く落ちる。テスト自身のコメントも「待たずに見ると、
機械が忙しいときだけ落ちるテストになる（実際そうなっていた）」と書いており、5 秒では
足りていない。直すなら別のスライスにする。

## UX1 差分の 4 枚で model を 4 回載せ直していた

`creative_batches.py` は 4 枚の差分を `count=1` の job 4 本に展開する。worker の
`main()` は stdin を 1 行ずつ読む loop で、`ImageWorker` は読み込んだ adapter を
`model_id` で持ち続ける。つまり載せたまま次の要求を受けられる作りである。ところが
呼び出し側が `process.communicate(payload)` を使っていた。`communicate` は stdin を
閉じるので、worker は 1 本ごとに終わり、次の job はまた最初から載せていた。

実機の log に残っていた、続けて走った job の載せ直し:

```text
data/features/media-forge/logs/service.log
load_sec=12.637492 generation_sec=16.041516
load_sec=13.154964 generation_sec=15.535938
load_sec=12.775642 generation_sec=15.543959
```

生成が 15.5 秒の要求に、載せ直しが 12.6〜13.2 秒付いていた。

### 直した後

`_exchange_while_progressing` で 1 要求 1 応答を交換し、プロセスは残す。続きの job が
無くなったときだけ下ろす。4 枚ぶんの job で worker を何回起こすかを数えた:

```text
jobs=4  worker_spawns=4   変更前
jobs=4  worker_spawns=1   変更後
```

`fake_settings` の JobManager に 4 本投入し、`asyncio.create_subprocess_exec` を数えた。
実測の載せ直し時間は GPU を llama-server が 22.6 GB 使用中のため測っていない。

### 一緒に直した 4 件

```text
先読みバッファ    `for raw in sys.stdin.buffer` は EOF まで 1 行目を返さない。
                  stdin を開いたまま待つ使い方では止まる。readline にした
print の buffer   pipe 相手の print はブロックバッファで、書いても届かない
返り値の判定      `returncode != 0` は、残してある worker を crash と見なす。
                  失敗は応答の形（`error`）で見る
後始末            communicate は pipe を畳んでいた。使い回しでは自分で畳まないと
                  transport が GC 任せになり、loop を閉じた後に落ちる
```

最後の 1 件は、`stop()` が job task を cancel すると片付けの途中で取り消されて
worker が残る、という形でも出ていた。取り消されても pipe だけは同期で畳む。

`./mf.sh test` 829 passed（warning は 25 件から 1 件に減った）。

## host 配置（システムRAM）への追従

ControlDeck の broker は 2026-09-04 に「誰を追い出すか」から「どこへ載せるか」へ
変わった（`docs/design-ai-resource-broker.md` §0）。LLM の KV が RAM へ落ちると
デコードが致命的に遅くなる（実測 75.4 → 32.6 tok/s）一方、画像生成のような
計算律速の処理は RAM 配置の劣化が桁違いに小さい、という非対称からである。

Add-on 側の契約は 3 つ。

```text
1  CPU で走らせられるなら preferred_devices: ["gpu0", "host"] を送る
2  実際の配置は grant の RequestStatus.device_id が返す
3  device_id == "host" なら VRAM を確保せず RAM で実行する
```

3 を守れないものは host を要求してはならない。要求しなければ従来どおり VRAM だけが
候補になる（`_eligible_devices` の opt-in）。

### 送る側

`image_model_request` は、CPU で走らせられる adapter のときだけ host を候補に挙げる。
`native.stable-diffusion-cpp-*` と `spandrel.upscale` は GPU 前提の駆動系なので挙げない。

`compute_mode` を `exclusive-preferred` から `shared-safe` に変えた。exclusive は
「その device に他の lease も provider 予約も無いこと」を求めるので、LLM が載って
いる限り VRAM の空きに関係なく `device_busy_exclusive` で断られ、共存にならない。
バイトの勘定は `admitted_free_bytes`（observed と予約の大きい方を使う）が見ている。

### 受ける側

grant の `device_id` を `HostExecution` に持ち、`host` なら worker へ渡す
`device_mode` を `cpu` にする。adapter は `pipeline.to("cpu")` で載せ、`torch.cuda`
には触らない。初期化されていない GPU に `synchronize` を投げるとそこで落ちる。

置き場所は 2 か所の鍵に入れた。どちらも「VRAM に載せたものを host 配置の要求へ
渡さない」ためである。

```text
warm worker の署名     置き場所が違えばプロセスを作り直す
adapter cache の鍵     (model_id, device_mode)。model_id だけだと使い回す
```

乱数の器も置き場所に合わせた（`torch.Generator(device=...)`）。CPU と CUDA の
generator は同じ seed でも違う雑音を出すので、**配置が変わると同じ seed でも絵が
変わる**。これは避けられない。

### 測っていないこと

CPU 実行の所要時間は測っていない。GPU を llama-server が 22.6 GB 使用中で、
FLUX.2 Klein（15 GB）を載せると OpenCode 側の LLM を壊すためである。
既知の近い実測は `docs/models.md` の SD 512x512 / 4 歩の比較で、
`direct_device_map` 15.0 秒に対し `cpu_offload`（RAM 常駐・GPU へ逐次転送）が
18.1 秒、ピーク VRAM は 21.8 GB から 8.9 GB だった。`cpu` はそれよりさらに遅い。

`./mf.sh test` 838 passed。

## 生成のたびに LLM を降ろさせるのをやめる

`_release_host_ai` は、実モデルの生成に入る前に毎回 ControlDeck へ「AI ターンを
終える」と宣言していた。画像モデルが 34.2 GB のカードに 33.35 GB を要り、
場所を空けてもらう以外に載せる方法が無かった頃の作りである。

broker が host 配置を持つようになって前提が変わった。VRAM が空いていなければ
生成は RAM へ載る。場所を空けてもらう必要が無い一方、降ろさせる側の代償は
そのまま残っていた ── 使っている最中の OpenCode や chat のモデルを、画像 1 枚の
ために落とすことになる。

消したもの:

```text
_release_host_ai              生成前の宣言そのもの
phase="release_ai"            それを表示するための段階と、UI の不確定表示
_ai_release / _VRAM_WAIT_REASONS
                              拒否理由を握って、後の受理失敗に添えるための保持
host_ai_residency_retained    その言い換え。降ろさせないので起きない
HostAIGateway.release         上を消すと呼び手が居なくなる
HostAIReleaseResult
JobManager(ai_gateway=...)    release 以外に使っていなかった
```

`HostAIGateway` 自体は残る。演出の立案・prompt・評価が `ai.inference` を使う。
ControlDeck 側の `POST /{addon_id}/ai/release` も残る。あれは利用者が「AI の番を
終えた」と宣言する経路で、add-on が job ごとに叩くものではない。

受理の待ちそのもの（`waiting` の 0.5 秒間隔の照会、`max_wait_sec` 300）は残す。
broker の受理は非同期で、照会以外に知る方法が無い。

acceptance script（`g6_resource_turn_e2e.py` / `_physical_e2e.py`）は、
「LLM が VRAM を返したこと」を確かめる形から「LLM が VRAM を持ったまま生成が
通ること」を確かめる形へ変えた。物理側の `ai/release` stub は呼ばれなくなるので
消した。

`./mf.sh test` 833 passed。

## RAM 配置の必要量を VRAM の見積りと分ける

host 配置は宣言だけあって、**一度も効いていなかった**。broker の `_required_bytes`
は device を問わず `vram.required_bytes` を返す。`vram` の見積りは `device_map` で
段階的に載せるときの GPU 側ピークで、RAM 配置の実態とは別物である。

CPU 実行を実測した（2026-09-04、FLUX.2 Klein 4B、`device_mode: cpu`）。
llama-server が VRAM 22.6GB を使ったまま、GPU を一切触らずに測れる。

```text
                       generation_sec   最大RSS      VRAM
512x512  / 4歩              40.26      16.26 GB    変化なし
1024x1024 / 4歩            113.44      18.76 GB    変化なし
placement: pipeline / text_encoder / transformer / vae すべて cpu
```

申告している `vram.required_bytes` は 31.1 GB で、実態の約 2 倍である。この機械の
RAM は 30 GB なので、31.1 GB の要求は host device の総容量を超え、必ず落ちる。
`admitted_free_bytes` との比較で弾かれて gpu0 が空くまで待ち続ける ── つまり
「VRAM が空いていなければ RAM へ」が成立していなかった。

ControlDeck 側に `ResourceRequest.host_bytes` を足し（PR #254）、MediaForge は
実測した常駐量に headroom を足して送る。測っていないモデルには送らない。小さすぎ
れば OOM、大きすぎれば載らない。どちらも推測で決めてよい数字ではない。

カタログの `measurements.host_resident_bytes` は任意である。GPU 前提の駆動系や、
まだ測っていないモデルは持たない。

参考として、カタログの GPU 経路は `measured_runtime_sec` 208.8 秒である。CPU の
113.4 秒はそれより速いが、測り方（cold load を含むか）が違うので直接は比べられない。

`./mf.sh test` 836 passed。

## VRAM の測り方が間違っていた

`DeviceSampler.peak()` がカード全体の使用量の**絶対値**を返し、`baseline` を引いて
いなかった。同じファイルの `GpuMemoryMonitor` は `incremental_peak_bytes` を持って
いるのに、評価側だけが絶対値を採っていた。測定時に載っていた LLM の VRAM が丸ごと
「このモデルに要る量」として記録されていた。

```text
FLUX.2 Klein 4B（重み 15GB）      申告        実測（2026-09-05）
読み込みピーク                 30.1 GiB     14.87 GiB
実行ピーク                     27.6 GiB     20.86 GiB
required_bytes                 31.1 GiB     21.9 GiB
生成 1024²/4歩（2枚目）        208.82 秒     2.98 秒
```

32GB のカードに載らないモデルとして扱われ、「~33GB が確保できません」で拒否されて
いた。RAM 配置（host_bytes）が 30GB の機械に永久に載らなかったのも同じ数字が原因。

直しは 2 段構えにした。

```text
DeviceSampler.increment(baseline)   外から見るなら増分を使う
worker が自分の確保量を申告        torch.cuda.max_memory_allocated()
```

増分でも、測っている間に他の process が伸びれば混ざる。確保した本人に聞けば混ざら
ない。申告があるときはそちらを使い、無いときだけ増分に落とす。

## lease を返しても VRAM は空いていなかった

生成の lease は評価の前に返す。exclusive な画像 lease を持ったまま Host に VLM を
載せさせると単一 GPU で deadlock するからである。ところが差分の 4 枚で載せ直さない
ために worker を残す作りにしたぶん（`_reuse_or_spawn_worker`）、**lease を返しても
VRAM は空かない**。broker から見て「空いた」のに物理的には埋まったままになり、
入らないはずの VLM が admit される。

```text
jobs.py  _release_host_resource()   lease を返す。broker は空いたと見る
         ↓ worker は生きていて 21GiB を握ったまま
         postprocess → vision.analyze   VLM の読み込みを要求
         ↓
         worker を終わらせるのは job queue が空になったとき（もっと後）
```

救っていたのは `observed_used_bytes`（2 秒間隔で更新）だけだった。

評価を行う job では、lease を返す前に worker を終わらせるようにした。評価を行わない
job では worker を残すので、差分の 4 枚で載せ直さない利点は保たれる。

## 全常駐できないときの下限を申告する

`measurements.minimum_vram_bytes` を足した。broker はここまで枠を切り詰めて貸し、
利用者はその枠に自分を縛る（ControlDeck #256）。実測で 8 GiB では成立し、7 GiB では
OOM したので 8 GiB を宣言する。測っていないモデルには送らない。

`./mf.sh test` 840 passed。

## 貸してもらった枠の中で走る

ControlDeck が空き状況から枠を決め（#256）、worker はその枠に自分を縛る。add-on は
他に何が載っているか知らないので、固定値を名乗ると LLM の構成が変わるたびに破綻する。

```text
grant の granted_bytes         →  HostExecution.granted_bytes
  ↓
枠 ≧ 全常駐   direct_device_map   カタログどおり VRAM に載せる
枠 < 全常駐   cpu_offload         重みは RAM、実行するモジュールだけ VRAM へ
device_id=host                cpu  VRAM を取らない
枠が返らない（旧 Host）        カタログの値のまま（後方互換）
  ↓
MEDIA_FORGE_VRAM_BUDGET_BYTES →  torch.cuda.set_per_process_memory_fraction
```

### 実機の通し確認（2026-09-05、llama-server 常駐のまま）

```text
枠 7.92 GiB を渡す      実ピーク 7.83 GiB（枠内に収まった）
device_mode             cpu_offload（自動で切り替わった）
生成 1024²/4歩          38.88 秒（初回。2 枚目以降は 6.7 秒）
llama-server            22.95 GB を保持したまま無傷
```

枠を割ったときは、この process だけが HIP の OOM で落ちる。実測で枠 7/6/4/3 GiB の
いずれでもカードには 24.5〜28.5 GiB の空きが残り、LLM は無傷だった。**見積りを
外しても被害が add-on 側に閉じる**ので、管理側が枠を決める形が安全に成立する。

### LLM が居ない場合

```text
LLM が居ない              gpu0  枠 24.26 GiB  → direct_device_map（全常駐・最速）
LLM 常駐・使用していない   gpu0  枠 10.44 GiB  → cpu_offload
LLM 常駐・使用中           gpu0  枠 10.44 GiB  → cpu_offload
大きい LLM 常駐・使用中     host  枠 18.89 GiB  → cpu
```

LLM が居なければ従来どおり全常駐で最速になる。速度を落とすのは、落とさなければ
そもそも走れない場合だけである。

`./mf.sh test` 846 passed。

## 空いているぶんを使う（モデルごとの下限をやめる）

`measurements.minimum_vram_bytes` を撤回した。モデル固有の値を宣言すると、測って
いないモデルは枠を貸してもらえず、測った値が少しでも足りなければ**そのモデルだけ
突然使えなくなる**。実際 FLUX.2 Klein 4B で 1 枚ぶんの実測 8 GiB を宣言したところ、
連続生成の 2 枚目が OOM した。

```text
枠  7.92 GiB   1枚目 成功（ピーク 7.83）→ 2枚目 resource_oom
枠 10.44 GiB   4 枚とも成功  22.05 / 35.23 / 5.36 / 5.17 秒
```

必要量は解像度・枚数・参照画像で変わるので、事前に 1 つの数字で言い当てられない。
`PYTORCH_HIP_ALLOC_CONF=expandable_segments:True` でも改善しなかったので、断片化では
なく offload の残留分である。

代わりに「これ未満では何をやっても動かない」線（2 GiB）だけを共通で置き、足りるか
どうかは実行が決める。外したら軽い載せ方へ落として走り直す。

```text
direct_device_map  →  cpu_offload  →  cpu（RAM のみ）
```

実機で確認（2026-09-05、llama-server 常駐のまま）:

```text
枠 2GiB / cpu_offload   resource_oom（worker だけが落ちる）
降格して cpu            成功 105.45 秒
llama-server            22.95 GB を保持したまま無傷
```

RAM のみなら VRAM の空きに左右されないので、必ずどこかで着地する。broker も
`residency_key` ごとに OOM 後の下限を学習する（`oom_recommendation`）。


## 2026-09-05 — 統合3D Studio設計・実装計画（文書のみ）

利用者は画像/3DをMediaForgeへ実装まで統合する方針を選択し、設計もMediaForgeへ置くよう指定した。
別SceneForgeリポジトリ/アドオン/配布系統は使わない。

追加文書:

- `docs/design-3d-studio.md`: 設計ゴール、責務、共通Library/UI、初期提供範囲。
- `docs/design-blender-runtime-and-web.md`: 設定から導入/更新/修復/切替/削除、サーバーBlender GUI、保存/再接続/GPU/隔離。
- `docs/design-3d-assets-and-opencode.md`: scene revision、材質/画像、GLB viewer、typed OpenCode制作、durable job。
- `docs/development-release-3d-studio.md`: 既存MediaForgeの開発/管理/署名配布と実機品質gate。
- `docs/implementation/g8-3d-studio-plan.md`: 3DS-0〜8、条件付きExpert、PR単位、受入、開始指示。
- `docs/reference-3d-studio.md`: ControlDeck/MediaForge/SonicForgeの参照commitと確認事項。

AGENTS/README/base-plan/integration/workspace UX/goal-roadmap/handoffから導線を追加した。
AGENTSの古いmobile=companion指示は現行addon.jsonのembeddedへ合わせ、3D追加で退行させない規則とした。
現行ControlDeckにはpublisher署名検証、binary WS relay、detached Jobs、CPU-only job credential refreshの
コードが存在することを確認。noVNC実機、GPU GUI、長時間再接続の動作証拠にはしていない。

検証対象は文書リンク、変更差分、参照commit、既存契約との整合性。実装コード・公開schema・
addon.json・release version・OS/runtime・他リポジトリはこのMediaForge PRでは変更しない。
新規3DS機能: NOT IMPLEMENTED。unit/integration/GPU/Blender/browser/release実機受入: NOT TESTED。
次: 現行mainと対象機を再確認する3DS-0、その後3DS-1を独立PRで実装。


## 2026-09-05 — 3DS-0 current-state / compatibility baseline

PR #213はmerge commit `9469d8e4e4980752082f5081da7ba6e95d184622`でmainへ入った。
3DS-0では `tests/fixtures/3ds-baseline-contract.json` と
`tests/test_3d_studio_baseline.py` に、既存Add-on identity/mobile、Agent/workflow contribution、
public job operation/Asset MIME、G8 profile/package/runtimeを加法的互換性の基準として固定した。
対象状態とCHECK-01〜08は `docs/implementation/3ds-compatibility.md` に記録した。

実機のsource runtimeはBlender 4.5.9 / Python 3.11.11、background・GLTF import/export probeが
すべてtrue。一時data rootと実Uvicorn `127.0.0.1:9164`へ796 Bのcube GLBをHTTP importし、
実Blenderによる `asset.pack + 3d.project.glb` を2回実行した。両jobはsucceeded、44,292 BのZIPは
SHA-256 `c78ef18d6c4da0334a9e3e2c451519d4b9bd2541ead1022cfa3979b0ef3a468b`でbyte-identical、
2回目は受付から終端まで1,055 ms。entryは固定3件、終了後work entry 0 / Blender child 0。

ControlDeck管理版は `current -> versions/0.27.0`、systemd PID 1241393、9130でhealthy / contract 2.0。
live capabilityは画像を`available / local / measured / local_only`とし、live storeの最新画像Assetは
704x1472 PNG / 7,262 B。一方G8は`unavailable / runtime_not_installed`で、bundle外runtimeをinstalled
serviceから解決する3DS-1の実ギャップを確認した。新規画像GPU jobとbrowser操作は **NOT TESTED**。
Web Blender、scene/revision、viewer、材質、OpenCode制作、setup/update/repair/removeは
**NOT IMPLEMENTED / NOT TESTED**。3DS-0の証拠をこれらへ読み替えない。

最終gateはfocused 176件、`./mf.sh test` 851件がPASS（既知Starlette warning 1件 / 62.14秒）。
Python compileall、frontend JavaScript構文、shell構文、変更Markdownの相対link、
`git diff --check`もPASSした。

## 2026-09-05 — 3DS-1 Blender runtime resolver / read-only Settings diagnostics

PR #215、実装commit `4c7c6f793f2c6936b74bfc755fe5f3a29e14def6`。
MediaForge-ownedのversioned registry/resolverを追加し、既存4.5.9 runtimeを
`legacy-blender-4.5.9`としてopaque登録した。registryは258 B / mode 0600で、JSONに
`/data1tb`、`/home`、`/tmp`は含まれない。symlink registry/managed runtime、root脱出、
不正record、壊れたmanifest/stamp/executable/trusted workerをfail-closedにした。
active runtimeと既存G8用4.5.9解決を分け、設定refresh時は既存runtimeの固定identityだけを
再確認・登録し、移動、削除、download、operator指定activeの上書きをしない。

private workspaceへ`blender_runtime` session part、`blender.runtime.status`、同一origin開発用
`GET /workspace-api/blender/runtime`を追加した。応答はopaque ID、版、ownership、4 integrity check、
別管理のWeb操作pack状態、fingerprintだけでraw pathを返さない。Settingsの先頭へread-only Blender
診断を置き、ready/missing/damaged/invalid/unsupported、legacy/managed、日英locale変更、320 pxを
扱う。3DS-1ではdownload/update/repair/switch/removeを提供せず、画像機能の状態と分離表示する。

一時data rootと実Uvicorn `127.0.0.1:9164`でstatusはready、required 4.5.9、active/G8は
`legacy-blender-4.5.9`、4検査true、fingerprint
`c5015f19e7a0fb8228e426386d0e7aee19be7501852d814da1c08c0f163ebcd9`。
同じ796 B cubeをresolver経由で実Blender加工したjob
`job_23d828f247fa420995b451d07b0a5246`は1.462秒でsucceededし、ZIP 44,292 B / SHA-256
`c78ef18d6c4da0334a9e3e2c451519d4b9bd2541ead1022cfa3979b0ef3a468b`は3DS-0とbyte-identical。
entry 3件、終了後work entry 0 / Blender child 0。

standalone Chromeで日本語ready/診断、英語rerender、別serverのmissing表示を操作した。320 pxで
clientWidth/scrollWidthはともに320、更新ボタン39 px、最終console/page/HTTP errorは0件。
実ControlDeck URLは未認証browserが`/login`へ遷移したため、installed opaque iframe操作は
**NOT TESTED**。installed 0.27.0へのsource変更deployment、GPU Blender、lifecycle操作、Web Blender、
scene/revision、viewer、材質、OpenCode制作も **NOT TESTED / NOT IMPLEMENTED**。

local gateは`./mf.sh test` 859 passed / 既知Starlette warning 1件 / 70.27秒。
Python compileall、frontend JavaScript構文、shell構文、Markdown相対link、`git diff --check`を
最終差分でも再実行する。ControlDeck変更は0件で、既存dirty `frontend/tsconfig.tsbuildinfo`を保持した。
