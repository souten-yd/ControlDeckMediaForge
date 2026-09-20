# G9 operator authentication for runtime evaluation

## 2026-09-20 correction: required Host CSRF header

The operator's terminal attempts reached the live Host at 00:44:16Z and
00:44:36Z, but both returned HTTP403 **before credential verification**.
The original helper omitted `X-Requested-With: ControlDeck`, which the Host
requires for cookie-based mutations, including login and logout. The initial
HTTP fixture did not enforce that middleware contract, so its passing login
tests did not detect the omission. These attempts do not show an incorrect
password, username, TOTP or insufficient account permissions.

The helper now sends the same header as the ordinary Host web client. Its
post-login operator client retains it for resource mutations and logout.
Host middleware, accounts, permissions and session authentication are unchanged.
Login failure reports the numeric HTTP status without response bodies, secrets
or automatic retries. The fixture now rejects headerless POSTs, including
cleanup/logout, and five new cases cover CSRF rejection and redacted HTTP
401/403/429/503 errors without retries. All37 focused tests passed.

Real HTTP verification used an empty JSON login body with **no credentials**:
the old client returned403/CSRF rejection; the repaired client returned422 with
missing username/password fields. No cookie was issued; unauthenticated
`auth/me` still returned401. This proves the CSRF gate is satisfied and the
request reaches input validation; it does not establish a successful real login.
The managed helper copy was atomically replaced after these checks. The existing
`bash ~/mf-login.sh` shortcut uses the repaired helper. The operator was asked to
retry in the terminal; no password or TOTP was requested in chat.

Evidence: `maintenance/g9-operator-csrf-20260920/` contains the filtered real
attempt statuses, `live-empty-login.json`, helper hashes and focused test log.
Final `./mf.sh test`: **2279 passed / 2 warnings / 259.96s / exit0**.
No helper or test changes followed. This private helper is outside the app bundle;
the installed version stays0.28.88 without restart or release version change.
Real authenticated session/lease/generation acceptance remains pending.

## Initial authentication boundary

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
bash ~/mf-login.sh
```

The shortcut points to `maintenance/g9-operator-20260920/login.sh` under the
MediaForge feature-data directory; it avoids pasted line breaks in the long path.

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
proxy and no redirects. TLS verification is retained for HTTPS. Every request
includes the ordinary `X-Requested-With: ControlDeck` CSRF header; this header
alone does not authenticate a user or grant a GPU lease.

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

## Initial validation (before the CSRF correction above)

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
