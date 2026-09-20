from __future__ import annotations

from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import pty
import select
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest
import httpx

from scripts import g9_operator_session as sessions

PASSWORD = 'fixture-password-do-not-echo'
TOKEN = 'fixture-dedicated-session-' + 'a'*32
OTP = '491726'
SCRIPT = Path(sessions.__file__)


@pytest.fixture
def host():
    """HTTP contract fixture only; never a real ControlDeck session/lease."""
    state = {'active': False, 'two_factor': True, 'permissions': True,
             'logout_fails': False, 'redirect': False, 'calls': [], 'login_status': None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def response(self, status, payload, *, cookie=False, redirect=False):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            if cookie:
                self.send_header('Set-Cookie', f'cd_session={TOKEN}; Path=/; HttpOnly; Max-Age=300')
            if redirect:
                self.send_header('Location', '/unexpected-redirect')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            state['calls'].append(('GET', self.path))
            if self.path != '/api/v1/auth/me':
                return self.response(404, {})
            if not state['active'] or f'cd_session={TOKEN}' not in self.headers.get('Cookie', ''):
                return self.response(401, {'detail': TOKEN})
            return self.response(200, {'id': 7, 'username': 'operator',
                'permissions': sorted(sessions.REQUIRED_PERMISSIONS) if state['permissions'] else [],
                'totp_required': True, 'totp_enabled': True})

        def do_POST(self):
            state['calls'].append(('POST', self.path))
            # The real Host enforces this before routing or checking credentials.
            if self.headers.get('X-Requested-With') != 'ControlDeck':
                return self.response(403, {'detail': 'CSRF check failed'})
            if self.path == '/api/v1/auth/logout':
                if state['logout_fails']:
                    return self.response(503, {'detail': TOKEN})
                if f'cd_session={TOKEN}' in self.headers.get('Cookie', ''):
                    state['active'] = False
                return self.response(200, {'ok': True})
            if self.path != '/api/v1/auth/login':
                return self.response(404, {})
            if state['login_status'] is not None:
                return self.response(state['login_status'], {'detail': PASSWORD+' '+TOKEN})
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if state['redirect']:
                return self.response(302, {}, redirect=True)
            if body.get('username') != 'operator' or body.get('password') != PASSWORD:
                return self.response(401, {'detail': PASSWORD})
            if state['two_factor'] and not body.get('totp_code'):
                return self.response(401, {'detail': 'two_factor_required'})
            if state['two_factor'] and body.get('totp_code') != OTP:
                return self.response(401, {'detail': OTP})
            state['active'] = True
            return self.response(200, {}, cookie=True)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', state
    finally:
        server.shutdown(); server.server_close(); thread.join()


def interactive_login(directory: Path, origin: str) -> tuple[int, str]:
    master, slave = pty.openpty()
    process = subprocess.Popen([sys.executable, str(SCRIPT), 'login', '--session-dir', str(directory),
        '--host-url', origin], stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    output = b''
    try:
        for prompt, answer in [('username: ', 'operator'), ('password (hidden): ', PASSWORD),
                               ('TOTP code (hidden): ', OTP)]:
            deadline = time.monotonic()+15
            while prompt.encode() not in output:
                assert process.poll() is None, output.decode(errors='replace')
                assert time.monotonic() < deadline, 'PTY prompt timeout'
                if select.select([master], [], [], .1)[0]:
                    output += os.read(master, 8192)
            os.write(master, (answer+'\n').encode())
        deadline = time.monotonic()+15
        while time.monotonic() < deadline:
            if select.select([master], [], [], .1)[0]:
                try:
                    chunk = os.read(master, 8192)
                except OSError:
                    break
                if not chunk:
                    break
                output += chunk
            elif process.poll() is not None:
                break
        return process.wait(timeout=2), output.decode(errors='replace')
    finally:
        if process.poll() is None:
            process.kill(); process.wait()
        os.close(master)


def stored(directory: Path, origin: str) -> sessions.OperatorSession:
    record = sessions.OperatorSession(origin, TOKEN, int(time.time())+300, False)
    with sessions.PrivateSession(directory, create=True) as private:
        private.write_new(record)
    return record


def mock_terminal(monkeypatch, password=PASSWORD):
    monkeypatch.setattr(sessions, 'sys', SimpleNamespace(
        stdin=SimpleNamespace(isatty=lambda: True), stderr=SimpleNamespace(isatty=lambda: True)))
    monkeypatch.setattr('builtins.input', lambda _: 'operator')
    answers = iter([password, OTP])
    monkeypatch.setattr(sessions, 'read_secret', lambda _: next(answers))


def test_real_process_hidden_tty_login_reuse_and_revoke(tmp_path, host):
    origin, state = host
    directory = tmp_path/'operator'
    code, text = interactive_login(directory, origin)
    assert code == 0 and '"authenticated": true' in text
    assert not any(secret in text for secret in (PASSWORD, OTP, TOKEN))
    assert directory.stat().st_mode & 0o777 == 0o700
    assert (directory/'session.json').stat().st_mode & 0o777 == 0o600
    with sessions.operator_client(directory) as client:
        assert sessions.check_identity(client)['operator_permissions']
    result = subprocess.run([sys.executable, str(SCRIPT), 'logout', '--session-dir', str(directory)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0 and not state['active']
    assert not (directory/'session.json').exists()
    assert all(path.startswith('/api/v1/auth/') for _, path in state['calls'])
    assert not any(secret in result.stdout+result.stderr for secret in (PASSWORD, OTP, TOKEN))


def test_host_contract_rejects_missing_csrf_header(host):
    origin, state = host
    with httpx.Client(base_url=origin, trust_env=False) as client:
        result = client.post('/api/v1/auth/login', json={'username': 'operator', 'password': PASSWORD})
    assert result.status_code == 403 and not state['active']
    with sessions.new_client(origin) as client:
        result = client.post('/api/v1/auth/login', json={'username': 'operator', 'password': PASSWORD})
    assert result.status_code == 401 and result.json()['detail'] == 'two_factor_required'


@pytest.mark.parametrize('status', [401, 403, 429, 503])
def test_login_failure_reports_only_http_status_without_retry(tmp_path, host, monkeypatch, status):
    origin, state = host
    state['login_status'] = status
    mock_terminal(monkeypatch)
    with pytest.raises(sessions.SessionError) as error:
        sessions.login(tmp_path/'private', origin)
    assert str(error.value) == f'host_login_failed_http_{status}_no_automatic_retry'
    assert not any(secret in str(error.value) for secret in (PASSWORD, OTP, TOKEN))
    assert state['calls'] == [('POST', '/api/v1/auth/login')]
    assert not (tmp_path/'private/session.json').exists()


@pytest.mark.parametrize('case', ['password', 'permission', 'redirect'])
def test_failed_login_does_not_save_or_leave_session(tmp_path, host, monkeypatch, case):
    origin, state = host
    state['permissions'] = case != 'permission'
    state['redirect'] = case == 'redirect'
    mock_terminal(monkeypatch, 'wrong' if case == 'password' else PASSWORD)
    with pytest.raises(sessions.SessionError) as error:
        sessions.login(tmp_path/'private', origin)
    assert TOKEN not in str(error.value) and PASSWORD not in str(error.value)
    assert not state['active'] and not (tmp_path/'private/session.json').exists()
    assert not any(path == '/unexpected-redirect' for _, path in state['calls'])
    assert state['calls'].count(('POST', '/api/v1/auth/login')) == (2 if case == 'permission' else 1)


def test_non_tty_login_refuses_before_network_or_file_changes(tmp_path, host):
    origin, state = host
    result = subprocess.run([sys.executable, str(SCRIPT), 'login', '--session-dir', str(tmp_path/'private'),
                             '--host-url', origin], input=PASSWORD+'\n', capture_output=True, text=True)
    assert result.returncode == 2 and 'interactive_terminal' in result.stdout
    assert PASSWORD not in result.stdout+result.stderr
    assert not state['calls'] and not (tmp_path/'private').exists()


def test_existing_session_is_preserved_before_prompt(tmp_path, monkeypatch):
    directory = tmp_path/'private'
    record = stored(directory, 'http://127.0.0.1:8765')
    mock_terminal(monkeypatch)
    with pytest.raises(sessions.SessionError, match='already_exists'):
        sessions.login(directory, record.origin)
    with sessions.PrivateSession(directory) as private:
        assert private.read() == record


def test_logout_sends_expired_local_cookie_and_preserves_on_failure(tmp_path, host):
    origin, state = host
    directory = tmp_path/'private'
    with sessions.PrivateSession(directory, create=True) as private:
        private.write_new(sessions.OperatorSession(origin, TOKEN, 1, False))
    state['active'] = True  # Host expiry could have been extended by earlier use.
    state['logout_fails'] = True
    with pytest.raises(sessions.SessionError, match='retained'):
        sessions.logout(directory)
    assert (directory/'session.json').exists() and state['active']
    state['logout_fails'] = False
    assert sessions.logout(directory)['dedicated_session_revoked']
    assert not state['active'] and not (directory/'session.json').exists()


def test_expired_session_never_sent_for_status(tmp_path, host):
    origin, state = host
    directory = tmp_path/'private'
    with sessions.PrivateSession(directory, create=True) as private:
        private.write_new(sessions.OperatorSession(origin, TOKEN, 1, False))
    with pytest.raises(sessions.SessionError, match='expired'):
        with sessions.operator_client(directory):
            pytest.fail('expired authentication admitted')
    assert not state['calls']


@pytest.mark.parametrize('origin', ['https://example.com:443', 'http://localhost:8765',
    'http://127.0.0.1:8765@evil.test:80', 'http://user:secret@127.0.0.1:8765',
    'http://127.0.0.1', 'http://127.0.0.1:0', 'http://127.0.0.1:99999',
    'http://127.0.0.1:8765/path', 'http://127.0.0.1:8765?secret=1', 'file:///tmp/session'])
def test_credentials_cannot_target_remote_or_ambiguous_origin(origin):
    with pytest.raises(sessions.SessionError):
        sessions.host_origin(origin)


@pytest.mark.parametrize('case', ['directory_permissions', 'file_permissions', 'symlink_file',
    'hardlink_file', 'fifo', 'file_is_directory', 'oversize', 'corrupt_json', 'symlink_directory',
    'in_repository', 'insecure_secure_cookie', 'cookie_injection'])
def test_private_session_rejects_unsafe_storage_and_contents(tmp_path, case):
    directory = tmp_path/'private'
    record = stored(directory, 'http://127.0.0.1:8765')
    path = directory/'session.json'
    if case == 'directory_permissions': directory.chmod(0o755)
    elif case == 'file_permissions': path.chmod(0o644)
    elif case == 'symlink_file': path.unlink(); path.symlink_to(tmp_path/'missing')
    elif case == 'hardlink_file': os.link(path, tmp_path/'copy')
    elif case == 'fifo': path.unlink(); os.mkfifo(path, 0o600)
    elif case == 'file_is_directory': path.unlink(); path.mkdir(mode=0o600)
    elif case == 'oversize': path.write_bytes(b' '*4097)
    elif case == 'corrupt_json': path.write_text('{"value":"'+TOKEN)
    elif case == 'symlink_directory':
        alias=tmp_path/'alias';alias.symlink_to(directory, target_is_directory=True);directory=alias
    elif case == 'in_repository': (tmp_path/'.git').write_text('gitdir: fixture')
    elif case == 'insecure_secure_cookie': path.write_bytes(replace(record, secure=True).encode())
    elif case == 'cookie_injection': path.write_bytes(replace(record, value=TOKEN+'\r\nX: injected').encode())
    with pytest.raises((sessions.SessionError, OSError)):
        with sessions.PrivateSession(directory) as private:
            private.read()


def test_secret_input_refuses_echo_fallback(monkeypatch):
    import warnings
    def fallback(_):
        warnings.warn('echo enabled', sessions.getpass.GetPassWarning)
        pytest.fail('input must not be read with echo enabled')
    monkeypatch.setattr(sessions.getpass, 'getpass', fallback)
    with pytest.raises(sessions.SessionError, match='cannot_hide'):
        sessions.read_secret('hidden: ')


def test_repr_and_cli_failure_do_not_leak_session(tmp_path, host):
    origin, state = host
    directory = tmp_path/'private'
    record = stored(directory, origin)
    assert TOKEN not in repr(record)
    result = subprocess.run([sys.executable, str(SCRIPT), 'status', '--session-dir', str(directory)],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 2 and 'not_authenticated' in result.stdout
    assert TOKEN not in result.stdout+result.stderr
