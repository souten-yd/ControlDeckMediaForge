# GUI filesystem isolation — read boundary

Date: 2026-09-10 / Status: read-policy fix installed and bounded acceptance passed; other OS boundaries pending

## Source remediation acceptance

The runner now handles READ_FILE, READ_DIR and EXECUTE as well as the existing
write rights. It permits only the selected executable, versioned Blender
resources, trusted bootstrap/preferences, selected Vulkan ICD, enumerated OS
dependencies and session working/control/socket roots. It does not grant the
runtime parent or the Host data tree. Runtime resource symlink escape is rejected.
The policy remains mandatory and fails closed when Landlock cannot be applied.

- `./mf.sh test`: 1793 passed, 2 existing warnings, 331.18s, exit0; four new
  isolation tests. The real Linux child-process test denies outside read/list/
  write/execute, a working-directory symlink escape and descendant reads while
  preserving allowed read/write operations.
- `npm run build:viewer`: 60ms, generated file unchanged. Actual
  `node --test tests/model-animation.test.mjs`: 5 passed. An earlier invocation
  named a nonexistent test file and did not run tests.
- Source runner + actual managed Blender4.5.13 software GUI:
  `/data1tb/mf-read-gui-ppq28hrh`, ready1.424s, save4.630s, stopped,
  original source unchanged. This uses the unchanged trusted GUI bootstrap.
- Additional real-Blender canary assertion uses a diagnostic-only bootstrap copy
  (`/data1tb/mf-read-gui-bootstrap-20260910.py`), not an exposed product script API.
  First attempt `/data1tb/mf-read-gui-gq71dwma` failed at the preceding preferences
  subprocess timeout, before the canary check. Unit was stopped and the original
  asset retained; cause is unresolved. Its failed observation is preserved.
- After that attempt was terminal and the full test process finished, a fresh
  attempt of `mf-read-isolation-real-gui-canary-20260910.py` returned exit0:
  `/data1tb/mf-read-gui-mbyfb480`, ready1.617s, save4.620s. Actual Blender denied
  the harmless outside-canary read, saved2077182B, SHA
  `678216ca6e03080cfb0e22da09d1789a7d6ed17333bf89a57eccd8db38515b62`.
  Unit `mediaforge-blender-db561195a1064900bbe97c0ec2e2faf2.service` inactive;
  original source SHA unchanged. No actual secrets were read.

## Source runtime and RFB regression

After PR497 merge7025735e2bffa2f125a10c7d75388152478ce6cb, the external
`/data1tb/mf-read-policy-rfb-versions-20260910.py` ran sequentially with arguments
`4.5.9` and `4.5.13` under `PYTHONPATH=backend:. .venv/bin/python`.
It uses the unchanged trusted bootstrap, fresh isolated working copies and the
actual managed runtimes. Both returned exit0:

| Runtime | Evidence directory under /data1tb | Ready | Save completed |
|---|---|---|---|
| 4.5.9 | mf-read-rfb-4.5.9-y0qube4m | 1.219s | 4.225s |
| 4.5.13 | mf-read-rfb-4.5.13-zrfknuds | 1.220s | 4.024s |

Both reported actual GUI/Vulkan/llvmpipe, 1280x720 RFB initialization, then
16,384 bytes of raw pixels from a 64x64 request on each of two sequential
connections. The first connection was closed before the second. Both saved
2,077,182 bytes and preserved the original immutable source hash. Saved hashes:
4.5.9 `562a63a4ada5840ca72ddfdf23dcc5ecc4c450ac8efa5b3e1ac17559a8569f2e`,
4.5.13 `383442c11d1c7c76a375339063a55bfb8229cf257825b1d5734f3e5f95a6d1fe`.
Dedicated units f3695cefc8cb4628a397ec7713903723 and
199780c23a3d4a4da5d580a61ee95cb9 were independently confirmed inactive.
This is runner/RFB transport acceptance, not a browser/noVNC/Host gateway test,
nor semantic cross-version compatibility of all scene features.

## Source browser acceptance

`scripts/3ds_autosave_source_e2e.py --serve` used fresh data
`/data1tb/mf-read-policy-browser-data-20260910-r3`, existing read-only managed
4.5.9 and the Web pack parent, and the preceding 4.5.9 saved copy as input.
The browser command used existing diagnostic Playwright Python and
`--verify-input-activity`; evidence is
`/data1tb/mf-read-policy-browser-evidence-20260910-r3`.
Real headed Chrome/noVNC: edited9.183s, input/reconnect assertions34.111s,
default autosave125.213s, dedicated child crash/recovery fork127.064s, exit0.
Recovered2 meshes versus original1, original formal revision unchanged,
candidate/recovered source SHA
`fce6c69731c8c57072dd508ff33d521c10f416cf14eb0fb9324e61866d902532`,
2,083,057 bytes. Screenshot inspected; page errors0. Session
669b74f61a164c4d8ebb7b2844def48e and its cgroup/processes were reclaimed.
The dedicated source server was terminated afterwards, not the installed service.

Earlier attempts remain failed: first Chrome launch lacked Xauthority; second
used an incorrectly nested diagnostic Web root and the real status reported
web_pack=missing, rejecting GUI start. Neither began a GUI. Corrected references
were passed to a new isolated source data directory; no installed config changed.
This source server reports setup_required for its missing normal environment
launcher, not a healthy installed deployment. No CodeDEV project was created.

Version preparation0.28.71: full `./mf.sh test`1793pass/204.70s/2 known warnings,
viewer build41ms/unchanged, Node animation5pass. No product/test edits after gate.

## Signed installed acceptance

PR498 merge/tag0d12b100f98f99883719283dc2bd78d5b4358d74, v0.28.71.
Exact build `/data1tb/mf-0.28.71-build-final-20260910`:31,604,803B,
SHA `1092ce19e30c089f9b08af5350949b3643d30fcc7c7d4acb1742e95a80d73cef`.
External final-audit exit0:203 entries, source equality, resource-cache exclusion,
actual packaged doctor ok. Existing publisher signature, all four public files
re-downloaded and verified by the real Host consumer before standard update.
`mf-0.28.71-install.py` exit0/18.707s, backup mf-0.28.71-update-g3c3ak_g.
All existing DB rows/registry/995 asset-runtime files unchanged; Host PID2552550
unchanged, MediaForge PID2628237 healthy. Actual executable SHA
`7fd000756cf580007bf46332608bb3c2da0e021f5cc5916ceef167a1cb89bad5` and served
UI/schema matched. Standard retention removed only .69 execution bundle; .70/.71 remain.

`mf-0.28.71-installed-gui.py` exit0/9.422s proved connection/save/reopen, but its
immediate reopened screenshot was black before first pixels. Do not use it as
visual proof. Separate `mf-0.28.71-installed-gui-r2.py` waits for real canvas pixels:
6.502s initial display,6.654s same-session reconnect,7.987s saved/stopped,
11.485s new-session display,12.196s cleanup/login revocation. Actual Host opaque
iframe, managed4.5.13, screenshot inspected, page errors0. Evidence directories
`mf-read-policy-gui-installed-0.28.71-20260910` and suffix-r2.
Independent `mf-0.28.71-gui-audit.py` exit0:4 GUI sessions stopped/units inactive,
old revisions retained,10 assets with matching actual hash and provenance.

`mf-0.28.71-installed-boundary-audit.py` extracted the runner from the actual
running executable, compared bytes, then ran the kernel negative test against
that extracted file. All six denied: read/list/write/symlink/child/execute.
Evidence `/data1tb/mf-0.28.71-installed-boundary-m0kx6a0l`; runner SHA
`f6424ca677ec0b31d1dd01a4e3aa959f9bd5eb9a23c579f0496b282c90b26906`.
The audit passed; the combined shell call returned4 because the following
is-active checks correctly reported inactive units. This is not a GUI-console
exploit test. No real secrets were read, no new GPU lease or CodeDEV project.

NOT TESTED: Unix-socket/fd/process-information isolation, installed GUI-console
negative attack, all failure/resource combinations. Next: harmless owned-fixture
tests of the remaining OS boundaries. This fix does not close all 3DS-5 security
or scenario E conditions.

## Observed boundary

During the scenario E GPU audit, the GUI runner was found to enforce only
Landlock write rights. The current systemd policy does not make `/data1tb`
unreadable. ProtectSystem=strict is not a confidentiality boundary.

The dedicated `/data1tb/mf-gui-read-boundary-20260910/probe.py` imported the actual
runner function and applied it under the same systemd properties as
SystemdUserSessionController. It read only a task-created harmless canary, not
any actual Host configuration, credential, user data, or another user's file.

- systemd unit `mf-gui-read-boundary-20260910.service`, invocation
  `be3b0887a2c24c4a8954c04b0a9fcd0a`, exit0, 22ms, peak memory2.6M.
- Result: outside_canary_read_allowed=true, outside_canary_write_denied=true.
- Canary SHA remained
  `7aeb687cec6c454bb86e033035d3d072f52edce773954c62a63ba4f4f1d0b988`.
- Unit was independently confirmed inactive afterwards.
- The runner extracted from installed0.28.70's actual executable equals source;
  SHA `1c708ede0c5896d3c87301da5af044413c6d2420907f92cf955a49986f8421f8`.

This is a real kernel-policy test with deployed-equivalent runner bytes, not a
Blender-console/browser exploit test. The probe's successful exit records the
observation; it is a **failed isolation acceptance**, not a product pass.
Existing GUI operation evidence remains valid only for its named operations.

## Next implementation slice

1. Add default-deny read/list/execute rights to the existing process sandbox.
   Derive explicit readable dependencies from validated, server-owned runtime
   and bootstrap identities. Writable working/control data also needs read
   access; neighboring scenes, revisions, and Host data do not.
2. Use narrowly enumerated OS libraries, fonts and configuration dependencies.
   Do not allow all of `/`, `/data1tb`, `/etc`, `/proc`, the user's home, or the
   entire MediaForge data directory merely to get Blender to start.
3. Test read/list/write/execute, symlink escape, and inherited child behavior
   against harmless fixture files. Also verify required files remain readable.
   Missing policy support or required dependency resolution must fail closed.
4. Verify a real isolated Blender GUI's startup, save, reconnect and shutdown
   with the new policy, keeping existing artifacts unchanged. Read restrictions
   alone do not prove Unix-socket, inherited-fd, or process-information isolation.
5. Run the full gate, merge, build/inspect/sign/update normally, and repeat the
   important negative and GUI checks against the installed bundle.

The original audit included no product change; installed0.28.70 had this gap.
The bounded0.28.71 read-policy acceptance above does not complete all3DS-5/security
conditions or authorize unrestricted GPU/Expert capability.

## GPU audit context

The live capability response advertises 15 typed scene operations, not a GPU
render operation. Installed Web pack status is ready; GUI projection says
software and the runner forces Lavapipe with empty HIP/ROCR/CUDA visibility.
The old `mf-3ds8-gpu-probe.QA` result records Blender4.5.9 standalone HIP Cycles
and Eevee timing, but does not bind those renders to a Host Job/lease in its
record. It cannot prove a product GPU rendering or GPU GUI scheduling path.

Live sysfs: card1 PCI device0x7551/vendor0x1002, VRAM34,208,743,424 bytes,
kernel7.0.0-31-generic. These identify the inspected machine, not a new GPU
render acceptance. No render, new GPU lease, model download, Host restart,
or CodeDEV project creation was performed in this audit.
