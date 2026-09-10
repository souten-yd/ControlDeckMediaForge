# GUI IPC isolation — scoped signals and abstract sockets

Date: 2026-09-10 / Status: source partial fix; pathname sockets unresolved

## Actual boundary failure

`PYTHONPATH=backend:. .venv/bin/python /data1tb/mf-ipc-boundary-20260910.py`
used SystemdUserSessionController with the actual runner filesystem policy.
The only peers were two task-created UNIX sockets and the diagnostic parent,
whose SIGUSR1 handler recorded receipt without stopping anything.
Evidence `/data1tb/mf-ipc-boundary-b68yu5lm`, exit0/unit inactive:

- Outside pathname and abstract connections both allowed; each peer received
  exactly `mf-owned-canary`.
- Outside SIGUSR1 allowed and received by the diagnostic parent.
- Actual kernel Landlock ABI8. No real Host/service socket, credential or other
  user's process was accessed. This successful observation is a failed boundary.

## Source fix

Apply an ABI6-or-newer Landlock scope for abstract UNIX connections and signals
before starting Xvnc, then retain the existing narrower filesystem layer before
Blender. Runner, Xvnc and Blender inherit one IPC domain so internal X connections
and parent-to-child cleanup remain possible. Missing required ABI fails closed.
The IPC layer grants only REFER from `/` to avoid its implicit default denial
breaking staged atomic saves; it does not grant root read/write/execute rights.
The existing filesystem layer still controls all of those rights and REFER.

Source: [Linux Landlock scope and ABI documentation](https://docs.kernel.org/userspace-api/landlock.html)
and [Linux6.12 UAPI definitions](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/landlock.h).
Scope flags are available from ABI6; pathname UNIX resolution restriction needs
ABI9. The local ABI8 does not implement that latter right. We do not silently
drop an unsupported right and call the full IPC boundary secure.

## Source acceptance

External `mf-ipc-boundary-scoped-20260910.py` uses a separate evidence directory
`mf-ipc-boundary-lwkoutqo`: abstract connection denied/errno1; outside SIGUSR1
denied/no signal received; unit inactive. Pathname connection remains allowed
and its task peer received the canary. The original failure is retained.

Two added tests cover real-kernel outside denial, internal abstract connection,
child termination, filesystem layering/staged rename, and ABI5 fail-closed.
Focused six filesystem/IPC tests passed. No product/test changes after full gate
started; its final result is recorded in implementation-status.

Actual source Blender4.5.13/software GUI via unchanged trusted bootstrap:
`mf-read-policy-rfb-versions-20260910.py 4.5.13`, exit0,
`/data1tb/mf-read-rfb-4.5.13-9v47jk8m`, ready1.018s/save4.224s.
Both RFB connections received16384 raw pixel bytes; saved2077182B/SHA
`4832ed645b4f30e017b1a6b17d6e9b8c7176017432cc6613ee3c1bc4dfd3829d`.
Original asset SHA unchanged, unit952779d8604c4cc58f2cec22a19712bf inactive.
This tests internal X communication and actual child cleanup with the scope;
it is not new browser/installed acceptance.

## Remaining OS prerequisite

Read-only namespace probes on this machine:

- `unshare --user --map-root-user --mount --net /usr/bin/true`: uid_map EPERM.
- `bwrap --unshare-user --unshare-pid --unshare-net --ro-bind / / --proc /proc
  --dev /dev -- /usr/bin/true`: loopback RTM_NEWADDR EPERM.
- Same bwrap without --unshare-net: uid-map permission denied.
- Dedicated systemd user unit with PrivateUsers=yes/PrivateNetwork=yes/
  ProtectSystem=strict ran readlink successfully, but journal explicitly says
  network isolation was unavailable and skipped. Its user namespace changed,
  while mount4026531832/network4026531833 matched the caller. Exit0 is not a
  namespace isolation pass. Unit mf-ipc-namespace-probe-20260910 inactive,
  invocation ef2bd22982504da3b109df367a8431cb.
- apparmor_restrict_unprivileged_userns=1, caller profile unconfined. This is
  observed configuration, not sole-cause proof for every namespace failure.

No OS policy, sysctl, profile or kernel was changed. A narrowly scoped supported
OS isolation configuration or equivalent proven boundary is needed before
pathname sockets can be accepted. Do not broaden access or claim Expert/full
GUI isolation ready. Seek authorization before changing OS security policy.
Inherited-fd and process-information acceptance also remains open.
Installed0.28.71 lacks this source scope change; no new release in this slice.
