#!/usr/bin/env python3
"""Create a dedicated local Host session using the ordinary interactive login API.

No Host imports, browser-cookie access, account changes, GPU work or adoption.
Run with the MediaForge core Python. Never pass passwords or TOTP as arguments.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass, field
import getpass
from http.cookiejar import Cookie
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from typing import Any, Iterator
from urllib.parse import urlsplit
import warnings

import httpx

COOKIE_NAME = 'cd_session'
SESSION_NAME = 'session.json'
REQUIRED_PERMISSIONS = {'system.view', 'settings.manage', 'workflows.run'}


class SessionError(Exception):
    """Deliberately contains only safe, fixed diagnostics."""


def host_origin(value: str) -> str:
    try:
        url = urlsplit(value)
        valid = (url.scheme in {'http', 'https'} and url.hostname in {'127.0.0.1', '::1'}
                 and url.port is not None and 1 <= url.port <= 65535
                 and not url.username and not url.password and not url.query and not url.fragment
                 and url.path in {'', '/'})
    except ValueError:
        valid = False
    if not valid:
        raise SessionError('host_url_must_be_a_literal_loopback_origin_with_port')
    return value.rstrip('/')


@dataclass(frozen=True)
class OperatorSession:
    origin: str
    value: str = field(repr=False)
    expires: int
    secure: bool

    def encode(self) -> bytes:
        return json.dumps({'schema': 1, 'origin': self.origin, 'value': self.value,
                           'expires': self.expires, 'secure': self.secure}).encode()

    @classmethod
    def decode(cls, raw: bytes) -> OperatorSession:
        try:
            data = json.loads(raw)
            if (type(data) is not dict or set(data) != {'schema', 'origin', 'value', 'expires', 'secure'}
                    or type(data['schema']) is not int or data['schema'] != 1
                    or not isinstance(data['value'], str)
                    or re.fullmatch(r'[A-Za-z0-9_-]{20,256}', data['value']) is None
                    or type(data['expires']) is not int or data['expires'] <= 0
                    or type(data['secure']) is not bool or not isinstance(data['origin'], str)):
                raise ValueError
            origin = host_origin(data['origin'])
            if data['secure'] and not origin.startswith('https://'):
                raise ValueError
            return cls(origin, data['value'], data['expires'], data['secure'])
        except (ValueError, TypeError, KeyError, SessionError):
            raise SessionError('invalid_private_session') from None


class PrivateSession:
    """Pin a private directory; never follow a file or directory symlink."""
    def __init__(self, directory: Path, *, create: bool = False) -> None:
        directory = Path(os.path.abspath(directory))
        if directory.resolve() != directory or any((p/'.git').exists() for p in (directory, *directory.parents)):
            raise SessionError('session_directory_must_be_outside_repositories_without_symlinks')
        if create:
            directory.mkdir(mode=0o700, exist_ok=True)
        self.fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(self.fd)
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            os.close(self.fd)
            raise SessionError('session_directory_requires_current_owner_and_mode_0700')

    def __enter__(self) -> PrivateSession:
        return self

    def __exit__(self, *_: Any) -> None:
        os.close(self.fd)

    def exists(self) -> bool:
        try:
            os.stat(SESSION_NAME, dir_fd=self.fd, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False

    def write_new(self, session: OperatorSession) -> None:
        # O_EXCL also rejects a dangling link and preserves an earlier session.
        fd = os.open(SESSION_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=self.fd)
        try:
            with os.fdopen(fd, 'wb') as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(session.encode())
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            os.unlink(SESSION_NAME, dir_fd=self.fd)
            raise

    def read(self) -> OperatorSession:
        fd = os.open(SESSION_NAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self.fd)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or info.st_size > 4096):
                raise SessionError('session_file_requires_private_regular_file_under_4096_bytes')
            return OperatorSession.decode(stream.read(4097))

    def remove(self) -> None:
        os.unlink(SESSION_NAME, dir_fd=self.fd)


def new_client(origin: str) -> httpx.Client:
    return httpx.Client(base_url=host_origin(origin), timeout=15, follow_redirects=False, trust_env=False)


def read_secret(prompt: str) -> str:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            return getpass.getpass(prompt)
    except getpass.GetPassWarning:
        raise SessionError('terminal_cannot_hide_input') from None


def attach_cookie(client: httpx.Client, session: OperatorSession, *, for_logout: bool = False) -> None:
    client.cookies.jar.set_cookie(Cookie(0, COOKIE_NAME, session.value, None, False,
        urlsplit(session.origin).hostname or '', False, False, '/', True,
        session.secure, None if for_logout else session.expires, False, None, None, {'HttpOnly': None}, False))


def revoke(client: httpx.Client) -> bool:
    response = client.post('/api/v1/auth/logout')
    try:
        return response.status_code == 200 and response.json() == {'ok': True}
    except ValueError:
        return False


def check_identity(client: httpx.Client) -> dict[str, Any]:
    response = client.get('/api/v1/auth/me')
    if response.status_code != 200:
        raise SessionError('host_session_expired_or_not_authenticated')
    try:
        identity = response.json()
        permissions = identity.get('permissions')
        if (type(identity.get('id')) is not int or identity['id'] <= 0
                or not isinstance(identity.get('username'), str) or not identity['username']
                or not isinstance(permissions, list) or not all(isinstance(p, str) for p in permissions)):
            raise ValueError
        if not REQUIRED_PERMISSIONS.issubset(permissions):
            raise SessionError('host_operator_permissions_missing')
        if identity.get('totp_required') is True and identity.get('totp_enabled') is not True:
            raise SessionError('complete_totp_setup_in_control_deck')
    except (ValueError, AttributeError):
        raise SessionError('invalid_host_identity_response') from None
    return {'authenticated': True, 'operator_permissions': True,
            'gpu_lease': False, 'runtime_adopted': False}


@contextmanager
def operator_client(directory: Path) -> Iterator[httpx.Client]:
    """Use only this helper's dedicated session; callers still need real leases."""
    with PrivateSession(directory) as private:
        session = private.read()
    if session.expires <= time.time():
        raise SessionError('host_session_expired_use_logout_then_login')
    with new_client(session.origin) as client:
        attach_cookie(client, session)
        check_identity(client)
        yield client


def login(directory: Path, origin: str) -> dict[str, Any]:
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise SessionError('login_requires_interactive_terminal_no_piped_credentials')
    origin = host_origin(origin)
    with PrivateSession(directory, create=True) as private:
        if private.exists():
            raise SessionError('session_already_exists_use_status_or_logout')
        username = input('ControlDeck username: ').strip()
        if not username or len(username) > 64:
            raise SessionError('invalid_username')
        password = read_secret('ControlDeck password (hidden): ')
        body = {'username': username, 'password': password}
        saved = False
        with new_client(origin) as client:
            try:
                response = client.post('/api/v1/auth/login', json=body)
                if response.status_code == 401:
                    try:
                        two_factor = response.json().get('detail') == 'two_factor_required'
                    except (ValueError, AttributeError):
                        two_factor = False
                    if two_factor:
                        body['totp_code'] = read_secret('ControlDeck TOTP code (hidden): ')
                        response = client.post('/api/v1/auth/login', json=body)
                if response.status_code != 200:
                    raise SessionError('host_login_failed_no_automatic_retry')
                result = check_identity(client)
                cookies = [c for c in client.cookies.jar if c.name == COOKIE_NAME]
                if len(cookies) != 1 or cookies[0].expires is None:
                    raise SessionError('host_login_did_not_issue_expected_expiring_cookie')
                cookie = cookies[0]
                session = OperatorSession.decode(OperatorSession(
                    origin, cookie.value or '', cookie.expires, cookie.secure).encode())
                private.write_new(session)
                saved = True
                return result
            finally:
                body.clear()
                if not saved and any(c.name == COOKIE_NAME for c in client.cookies.jar):
                    try:
                        if not revoke(client):
                            raise SessionError('failed_login_session_cleanup_failed_check_host_sessions')
                    except httpx.HTTPError:
                        raise SessionError('failed_login_session_cleanup_failed_check_host_sessions') from None


def logout(directory: Path) -> dict[str, Any]:
    # Even an expired session can use the ordinary idempotent logout endpoint.
    with PrivateSession(directory) as private:
        session = private.read()
        with new_client(session.origin) as client:
            # The Host may have renewed its expiry during evaluation. Always
            # send the dedicated credential to revoke, even after local expiry.
            attach_cookie(client, session, for_logout=True)
            if not revoke(client):
                raise SessionError('host_logout_failed_private_session_retained')
        private.remove()
    return {'authenticated': False, 'dedicated_session_revoked': True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('login', 'status', 'logout'))
    parser.add_argument('--session-dir', type=Path, required=True)
    parser.add_argument('--host-url', default='http://127.0.0.1:8765')
    args = parser.parse_args()
    try:
        if args.action == 'login':
            result = login(args.session_dir, args.host_url)
        elif args.action == 'logout':
            result = logout(args.session_dir)
        else:
            with operator_client(args.session_dir) as client:
                result = check_identity(client)
        print(json.dumps(result))
        return 0
    except (SessionError, OSError, httpx.HTTPError) as exc:
        # Never render HTTP exceptions, response bodies, cookies, credentials or paths.
        reason = str(exc) if isinstance(exc, SessionError) else 'private_session_or_host_unavailable'
        print(json.dumps({'authenticated': False, 'reason': reason}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
