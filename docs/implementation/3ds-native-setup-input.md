# Native setup: immutable package input acceptance

Date: 2026-09-12. Status: package-input candidate rejected; setup NOT IMPLEMENTED.

The no-code requirement remains: Settings starts setup, the OS obtains explicit
administrator consent, the dedicated policy survives reboot, and ordinary GUI
editing never needs repeated command entry. This experiment does not install a
package, load a policy, or supply that workflow.

## Read-only native experiment

Base main `3b0fb59` (PR520 merged), PackageKit package
`1.2.8-2ubuntu1.5`, Ubuntu24.04/APT. A task-owned metadata-only Debian package was
built with `dpkg-deb --root-owner-group --build`. Its control fields were:

```text
Package: mediaforge-native-inspection-fixture
Version: 0.0.0
Architecture: all
Maintainer: MediaForge test <test@example.invalid>
Description: Read-only package metadata fixture; never install this package
```

No payload or maintainer scripts. Size526B; SHA256
`f5a37c51393ab1b1fc32c443068106d68f40ed91d8e6938aae75eed2efbda18a`.
The first build rejected the task's DEBIAN directory mode0700; changing only
that owned directory to0755 allowed the build. An earlier diagnostic's output
was unavailable after context truncation; its result is NOT VERIFIED. Its
process was confirmed absent before the following separate experiment.

Tool `8d0056`, exit0, wall0.201842s: OS `/usr/bin/python3 -I -`, Gio system-bus
connection, a normal file versus `os.memfd_create("fixture.deb", MFD_CLOEXEC |
MFD_ALLOW_SEALING)` containing the same bytes. The latter had all four seals
WRITE/GROW/SHRINK/SEAL applied with `fcntl(F_ADD_SEALS)` before the request.
The worker held that fd open throughout the transaction and supplied
`/proc/<its-own-pid>/fd/<fd>` as the second path.

Each case used CreateTransaction and GetDetailsLocal on the **same persistent
D-Bus connection**, with flags NONE, method timeout3000ms and signal-loop
timeout12s. Details/ErrorCode/Finished were subscribed before the request.
Only bounded signal text was printed. No InstallFiles, InstallPackages,
interactive authorization, or package-manager write command was called.

| Input | Details | ErrorCode | Finished |
|---|---|---|---|
| normal fixture.deb | package-id `mediaforge-native-inspection-fixture;0.0.0;all;local`, size526 | none | `(uint32 1, uint32 170)` |
| sealed proc-fd path | **none** | none | `(uint32 1, uint32 109)` |

Thus terminal success alone is insufficient: the expected package identity and
metadata must actually be received. The sealed-input candidate did not meet
even this metadata gate. This is not an InstallFiles test, nor proof of the
precise underlying rejection cause. In particular, the absence of a `.deb`
suffix is a hypothesis, not an established cause.

Follow-up tool `30d0f2`: `dpkg-query -W mediaforge-native-inspection-fixture`
reported no matching package, and PackageKit GetTransactionList returned
`(@ao [],)`. No production runtime/service/user assets were changed.
The two task fixture files and their empty native-handoff-probe directories
were subsequently removed; this record retains the observations, not raw files.

## Source cross-check and next boundary

Upstream v1.2.8 resolves through annotated tag1b765bd to commit
`09ef076e065ede945a3f827d6ba2b2b5889c9982`. In its
[InstallFiles implementation](https://github.com/PackageKit/PackageKit/blob/09ef076e065ede945a3f827d6ba2b2b5889c9982/src/pk-transaction.c#L3970),
existence/content-type checks precede copying the **path strings** into
cached_full_paths and obtaining authorization. It does not seal the supplied
bytes at that boundary. This is an upstream-source observation, not a claim
that every Ubuntu patch or downstream read has been audited.

Do not replace the unsuccessful proc-fd route with a mutable `.deb` symlink,
chmod-only user-owned file, or another pre-approval hash check and claim the
verified-to-installed bytes invariant. Do not implement the proposed memfd
holder as production integration until its actual consumer works.

Next work must establish a trusted native handoff: either an OS-supported
signature-verified immutable input path, or a narrowly scoped, explicitly
approved native bootstrap that verifies pinned publisher identity and bytes
inside the privileged boundary before staging/installation. The trust/bootstrap
and mobile-to-PC approval path must be designed before choosing either route.
No new privileged daemon or generic Python/bwrap/sudo exemption is authorized
by this experiment. Existing Host hw-helper only supports GPU properties and
fixed-catalog service control; it is not an installer or signature verifier.

The first PackageKit discovery module remains correct as discovery only;
`installation=not_implemented` and `interactive_agent=not_checked` remain true.
Production package, actual approval/rejection/cancel, rollback/removal/reboot,
GUI confinement, and Settings integration are NOT IMPLEMENTED/TESTED here.
All GOAL-01–10/A–F and game-asset scope remain unchanged and PARTIAL.
