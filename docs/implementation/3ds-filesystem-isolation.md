# GUI filesystem isolation — read boundary

Date: 2026-09-10 / Status: FAIL / remediation required

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

No product policy change or release is included in this audit slice. The current
installed GUI still has this read boundary gap. Do not claim all 3DS-5/security
acceptance is complete or expand GPU/Expert capability before addressing it.

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
