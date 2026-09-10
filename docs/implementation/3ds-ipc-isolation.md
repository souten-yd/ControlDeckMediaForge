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

## Follow-up: exact OS denial evidence (read-only)

After PR500 mergeff6e25823e6423bce5efa600011ee2ed1871451f, read-only kernel audit
inspection narrowed the observed prerequisite. Command:
`journalctl -k --since '2026-09-10 22:40:00' --until '2026-09-10 22:49:00'
--no-pager --grep='apparmor|userns'`.

- The dedicated systemd probe PID2637017 (22:48:10) transitioned from unconfined
  to unprivileged_userns at userns_create, then AppArmor denied sys_admin.
  Its original service invocation and unchanged mount/net namespace IDs above
  identify the same diagnostic operation, not another service.
- The unshare probe PID2635668 (22:47:16) has the same transition/sys_admin denial.
- The bwrap attempts (22:47:44), parent PIDs2636383/2636409, children2636391/
  2636418, have setpcap/net_admin denials and an explicit denied uid_map write.
- `/etc/apparmor.d/bwrap` and `/etc/apparmor.d/unshare` do not exist. This does not
  prove the absence of every possible alias, loaded profile or alternative.

These records identify actual AppArmor denials for the probes; prior generic
sandbox error messages alone were not sufficient attribution. No sysctl/profile/
kernel/service configuration, installed data or source code was changed here.

Authorization requested, not received: develop and apply a MediaForge-specific
OS isolation configuration. Before applying, enumerate exact administrator-owned
files, trusted launcher identity, scoped permissions, rollback, and negative
acceptance. Do not disable AppArmor or globally relax unprivileged-userns policy;
do not broadly authorize every Python/systemd/bwrap invocation. A mere exception
for a user-replaceable executable is not proof of a secure dedicated boundary.
This is a constrained next-design requirement, not an installed or tested policy.

## 2026-09-11 authorization and restriction-only alternative

The user explicitly approved MediaForge-specific OS isolation work (「良いです」).
The older authorization-pending entries above are historical, not the current
authorization state. Noninteractive `sudo -n true` now returns exit1, `sudo: a
password is required`. Do not ask for the password in chat or relax sudo policy.
The current userns sysctl remains1; `/usr/local` and `/etc/apparmor.d` are root-owned
0755 and `/usr/local/libexec` is absent. No OS policy was changed.

Before designing any namespace exemption, test an alternative that **only adds
restrictions**: an explicitly selected, named AppArmor profile, without executable
attachment or `userns`/capability/profile-escape permission. It cannot make generic
Python or bwrap more privileged. The [AppArmor4.0 upstream manual](https://www.apparmor.net/man/4.0/apparmor.d/)
specifies pathname UNIX sockets are mediated by file access rules, separately from
abstract/anonymous UNIX rules. The installed4.0.1 parser/manual were also inspected.
This is a candidate way to close the ABI8 pathname gap, not evidence of enforcement
on this kernel and not a replacement for all mount/PID/fd isolation acceptance.

### Bounded administrator-assisted canary

- `scripts/mediaforge-ipc-canary-v1.apparmor` is a **diagnostic-only** named profile.
  It attaches to no executable. It allows the installed Python3.12 and necessary
  library reads, socket creation, its own label read, and one task-owned pathname
  socket pattern. No abstractions/base, broad filesystem write, userns, capabilities,
  unconfined execution transition, mount or generic namespace exemption is granted.
- `scripts/3ds_apparmor_ipc_probe.py` runs as the ordinary service user, never root.
  It owns both socket peers; neither is a real Host/service endpoint. A fixed child
  uses `aa-exec -p mediaforge-ipc-canary-v1`, isolated Python startup, a clean
  environment, closed extra descriptors and a five-second timeout. Only its own
  temporary directory is removed. The empty `ipc-probes` parent remains in data.
- The canary requires the actual enforcing label, the permitted peer receiving
  the payload, and the outside peer denied with EACCES/EPERM and receiving nothing.
  Missing profile, complain mode, unrelated socket errors or denied positive access
  are failures. Baseline execution deliberately cannot satisfy the gate.
- `apparmor_parser -Q -K scripts/mediaforge-ipc-canary-v1.apparmor` compiles without
  kernel loading or profile-cache writes. The installed parser accepted the file.
  This is syntax evidence only.

Administrator action is **not performed** by the diagnostic or Feature setup.
After reviewing the exact checked-in profile, the local administrator may load
this temporary, unattached diagnostic profile (no `/etc` file installation):

```bash
sudo /usr/sbin/apparmor_parser -a -K scripts/mediaforge-ipc-canary-v1.apparmor
```

Use `-a`, not `-r`: a preexisting profile with that name must not be replaced.
If loading succeeds, run the canary **without sudo**:

```bash
/usr/bin/python3 scripts/3ds_apparmor_ipc_probe.py
```

After that canary has exited, remove only the profile loaded by this procedure:

```bash
sudo /usr/sbin/apparmor_parser -R -K scripts/mediaforge-ipc-canary-v1.apparmor
```

Do not run the removal if the initial add failed due to a name collision. No service
restart is required by this procedure. No global AppArmor/userns change, persistent
profile, root launcher, Blender install, or Host setting is part of this experiment.

### Current observations and promotion gate

Both ordinary-user commands were executed before any administrator load:

- `--baseline`: exit2, child exit0/unconfined, both dedicated peers received exactly
  `mf-owned-canary`, passed=false, owned temporary peers removed.
- Profile mode: exit2, aa-exec exit1 reporting the named profile does not exist,
  no child evidence, neither peer received data, passed=false, peers removed.
- Twelve focused tests passed, including a real unconfined baseline and retained
  sentinel verification. The full suite result is in implementation-status.

**Loaded-profile enforcement: NOT TESTED.** Administrative authentication is the
next required external action for this canary. Even a passing canary will prove
only this pathname condition. Next implement the production policy/entry with
per-session roots, profile-presence fail-closed checks, exact effective runner
identity, inherited-fd and process/ptrace tests, and actual GUI save/reconnect/stop
acceptance. Preserve existing Landlock layers and no privilege-adding fallback.
Review production installation/rollback separately; this probe profile must never
be shipped or advertised as a complete Blender GUI sandbox.
