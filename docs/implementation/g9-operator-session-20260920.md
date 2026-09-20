# G9 operator authentication for runtime evaluation

The installed 0.28.88 adapters still require measured adoption and genuine Host
GPU admission. On 2026-09-20, unauthenticated `/api/v1/auth/me` and
`/api/v1/resources` both returned HTTP401. No authenticated ControlDeck tool,
browser session or Host execution credential was available in this agent session.
Model license consent remains valid; it does not provide Host authentication.

`scripts/g9_operator_session.py` provides an explicit operator login path using
the existing Host HTTP API. It does not enable generation, issue an adoption
receipt, request a GPU lease, import Host internals, read browser cookies, alter
users or disable two-factor authentication. It is a private evaluation helper,
outside the lightweight release bundle, with no public API/schema change.

## Operator action on the machine running ControlDeck

Run from a checkout containing this helper, with the MediaForge core Python:

```bash
/data1tb/ControlDeckMediaForge/.venv/bin/python scripts/g9_operator_session.py login \
  --session-dir /data1tb/ControlDeck/data/feature-data/media-forge/maintenance/g9-operator-auth
```

For this handoff, an exact copy and launcher are available in the private managed
evidence directory. This command works independently of the preserved original
checkout, which remains on `feat/g9-image-to-3d`:

```bash
bash /data1tb/ControlDeck/data/feature-data/media-forge/maintenance/g9-operator-20260920/login.sh
```

Enter the ordinary ControlDeck username and password in that terminal; the helper
requests the two-factor code only when the Host requires it. Password/code entry
must be hidden; noninteractive input and an echo-enabled fallback are rejected.
Do not paste secrets into chat or command arguments. Successful output reports
`authenticated: true`, while `gpu_lease` and `runtime_adopted` remain false.
The operator account needs `system.view`, `settings.manage`, and `workflows.run`.
Missing permissions or required TOTP enrollment fail before saving a session.

The helper obtains a **new dedicated** session through `/api/v1/auth/login`,
verifies `/api/v1/auth/me`, and stores only its cookie, Host origin and expiry.
The directory must be operator-owned mode0700, and the file mode0600, outside Git
checkouts. Symlinks, hardlinks, special files, oversized files and existing-session
overwrites are refused. HTTP requests use a literal loopback origin, no environment
proxy and no redirects. TLS verification is retained for HTTPS.

To check or revoke the dedicated session, use the same Python/helper with
`status` or `logout` in place of `login` and the same `--session-dir`. Logout uses
the normal Host endpoint and deletes the local credential only after confirmation;
a failed logout retains it for retry. It also sends an expired local credential
to logout, since the Host may have renewed that session during earlier activity.
It leaves other browser sessions untouched. Delete the empty private directory
after successful logout. Do not include its contents in provenance or reports.

## Evaluation boundary

Private evaluation code can use `operator_client(directory)` for authenticated
HTTP after identity/permission verification. It must still acquire the real
broker request, verify physical device mapping, activate/renew the granted lease,
monitor the native process, reap it, and release the lease on every terminal path.
Use the ordinary Add-on/Scene Jobs boundary for the later installed generation
acceptance. A successful login is not proof of either generation or adoption.

## Validation

The new test module exercises a real helper process in a pseudo-terminal against
a **local HTTP protocol fixture**: password/TOTP are absent from captured terminal
output, login/status/revocation succeed, and no GPU/resource endpoints are called.
Additional cases cover permission rejection, wrong password without retry,
redirect rejection, noninteractive input, preserved existing sessions, failed
logout, local expiry, unsafe storage/origins and redacted diagnostics.
These 32 cases do not create real ControlDeck sessions or establish Host acceptance.
The final `./mf.sh test` passed **2274 tests, 2 warnings, 255.76 seconds, exit 0**.

Live audit, helper identity and the complete repository test log are retained in
`maintenance/g9-operator-20260920/`. The dedicated real login, Host GPU admission,
full trained generation, Vulkan acceptance and runtime adoption remain **NOT TESTED**
until the operator provides the requested authenticated session.
