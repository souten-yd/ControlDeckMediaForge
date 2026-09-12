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

## 2026-09-12 minimal diagnostic restored and pathname canary passed

The user explicitly authorized restoring only the necessary code. Restore the
PR502 canary script, its named profile, and its tests on current main; do not
restore deleted `/data1tb/mf-*` fixtures, backups, scripts or historical payloads.
Add the missing `/usr/lib/python3.12/ r` directory rule (the recursive child rule
did not permit listing the directory itself) and the exact local timezone read.
The first defect was confirmed by the actual kernel denial and Python encodings
initialization failure, not inferred from a generic launch error.

The user reloaded the revised profile. Running
`/usr/bin/python3 scripts/3ds_apparmor_ipc_probe.py` returned exit0:

- Actual child label `mediaforge-ipc-canary-v1 (enforce)`; stderr empty.
- Permitted dedicated peer connected and received `mf-owned-canary`.
- Outside dedicated peer connection denied with errno13/EACCES; no payload received.
- `passed=true`, all owned temporary peers removed. No real service socket contacted.

The restored twelve tests and one new directory/no-privilege regression test are
part of the full gate recorded in implementation-status. Parser `-Q -K` also
succeeded without loading policy or writing its cache. No product runner changes.
This passes the pathname canary, **not** the full GUI/fd/process confinement gate.

The current profile remains a temporary, unattached diagnostic profile. Following
the user request to avoid repeated manual application, the production design now
requires one explicit persistent administrator setup followed by OS boot loading
and ordinary non-root entry/checks. Do not ask for repeated canary reloads or call
this diagnostic profile a completed production installer. Future rule updates need
administrator authorization; no global userns exception or unrestricted sudo.

## Web Blender entry investigation (not a GUI fix)

The user reported no editor window after opening the Web Blender navigation.
Current HTML puts `scene-blender-open` inside the initially hidden scene detail;
navigation itself selects the scene browser, not the RFB dialog. Selecting a scene
and pressing the edit button is required. No-scene users only see import/backup
controls and the empty list, so discoverability/new-scene entry remains a gap.

A headless real-browser read-only check against installed0.28.79 standalone
`http://127.0.0.1:9130/web-blender` observed nav1, scene buttons0, editor button
not visible, dialog not visible, and the Japanese no-scenes message. Non-GET
requests were blocked to avoid preference/data writes. This is the standalone
owner, not proof of the reporting user having no scenes. The actual Host URL
redirected the fresh diagnostic browser to login; no password/session was changed.
Core health is currently healthy. User-path reproduction, entry improvements and
actual opaque-frame editor acceptance remain open; the pathname canary does not
resolve this separate UI report.
