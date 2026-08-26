# Media Forge implementation status

Date: 2026-08-26
Scope: MF0-0 through MF0-7 and G0 through G6 complete; G7 V0 complete, V1 adoption deferred
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

### 土台が無ければ、先に知らせる

LoRA は 40MB 前後だが土台は 2〜7GB ある。黙って始めると 40MB のつもりが 7GB
落ちてくる。取り込む前に、載せる先が手元にあるかを調べ、無ければその系統で
最も使われている checkpoint を大きさ付きで見せて確認を取る。

土台は LoRA が入ってから取り込む。先に落として LoRA 側が失敗すると、頼んで
いない 7GB だけが残る。

### UI

* 検索行に種別（モデル本体 / LoRA）。Hugging Face には LoRA の経路が無いので、
  そちらを選んだときは種別を出さない
* 「手元のモデルに載せられるものだけ」の絞り込み
* 結果に系統と起動語。系統は載るなら緑、載らないなら黄で出す
* 生成画面に LoRA の選択と強さ（0〜2、4 個まで）。選んだモデルに載せられる
  ものだけを出す
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
