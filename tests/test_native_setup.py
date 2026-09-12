from __future__ import annotations

import asyncio
import ast
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from mediaforge import native_setup
from worker_packs.native_setup import probe


class BusError(Exception):
    remote_name = "org.freedesktop.DBus.Error.Failed"


class Variant:
    def __init__(self, signature: str, value: Any) -> None:
        self.signature, self.value = signature, value

    def unpack(self) -> Any:
        return self.value


class Bus:
    def __init__(self, authorization: tuple[bool, bool, dict[str, str]] = (False, True, {})) -> None:
        self.properties = {"VersionMajor": 1, "VersionMinor": 2, "VersionMicro": 8,
                           "BackendName": "apt", "Locked": False,
                           "MimeTypes": ["application/vnd.debian.binary-package"]}
        self.authorization = authorization
        self.calls: list[tuple[Any, ...]] = []
        self.fail: str | None = None
        self.session: Any = "/org/freedesktop/login1/session/_32"
        self.remote_error = "org.freedesktop.DBus.Error.Failed"

    def get_unique_name(self) -> str:
        return ":1.321"

    def call_sync(self, *args: Any) -> Variant:
        self.calls.append(args)
        method = args[3]
        if method == self.fail:
            error = BusError("private diagnostic details must not be returned")
            error.remote_name = self.remote_error
            raise error
        if method == "GetAll":
            return Variant("(a{sv})", (self.properties,))
        if method == "GetSessionByPID":
            return Variant("(o)", (self.session,))
        assert method == "CheckAuthorization"
        return Variant("((bba{ss}))", (self.authorization,))


def discover(bus: Bus) -> dict[str, Any]:
    return probe.discover(bus, SimpleNamespace(DBusCallFlags=SimpleNamespace(NONE=0),
                          DBusError=SimpleNamespace(get_remote_error=lambda error: error.remote_name)),
                          SimpleNamespace(Variant=Variant, VariantType=SimpleNamespace(new=lambda x: x), Error=BusError))


@pytest.mark.parametrize(("authorized", "challenge", "expected"), [
    (True, False, "granted"), (False, True, "challenge"), (False, False, "denied"),
])
def test_probe_never_prompts_or_creates_transactions(authorized: bool, challenge: bool, expected: str) -> None:
    bus = Bus((authorized, challenge, {"private": "omitted"}))
    value = discover(bus)
    assert value["state"] == "detected" and value["authorization"] == expected
    assert value["installation"] == "not_implemented" and value["interactive_agent"] == "not_checked"
    assert "private" not in repr(value)
    assert [call[3] for call in bus.calls] == ["GetAll", "CheckAuthorization", "GetSessionByPID"]
    assert value["login_session"] == "present"
    assert bus.calls[2][4].signature == "(u)"
    assert bus.calls[2][4].value == (probe.os.getpid(),)
    for call in bus.calls:
        assert call[6] == 0 and call[7] == 2000  # no interactive D-Bus flag, bounded call
    params = bus.calls[1][4]
    assert params.signature == "((sa{sv})sa{ss}us)"
    subject, action, details, flags, cancellation_id = params.value
    assert subject[0] == "system-bus-name"
    assert subject[1]["name"].value == bus.get_unique_name()
    assert action == "org.freedesktop.packagekit.package-install-untrusted"
    assert details == {} and flags == 0 and cancellation_id == ""
    native_setup.NativeSetupProbe.model_validate(value)


@pytest.mark.parametrize("method", ["GetAll", "CheckAuthorization"])
def test_bus_failure_is_explicit_and_redacted(method: str) -> None:
    bus = Bus()
    bus.fail = method
    value = discover(bus)
    assert value["error_code"]
    assert "private" not in repr(value)
    assert value["authorization"] != "granted"
    native_setup.NativeSetupProbe.model_validate(value)


@pytest.mark.parametrize(("key", "value"), [
    ("VersionMajor", True), ("VersionMinor", -1), ("VersionMicro", 65536),
    ("BackendName", "bad\nbackend"), ("Locked", "false"), ("MimeTypes", "application/x-deb"),
])
def test_invalid_properties_do_not_produce_a_detected_provider(key: str, value: Any) -> None:
    bus = Bus()
    bus.properties[key] = value
    answer = discover(bus)
    assert answer["state"] == "unavailable" and answer["error_code"]
    assert len(bus.calls) == 1


@pytest.mark.parametrize("field", ["installation", "interactive_agent", "state", "login_session"])
def test_protocol_cannot_claim_installation_or_agent_readiness(field: str) -> None:
    value = probe.result()
    value[field] = "ready"
    with pytest.raises(ValidationError):
        native_setup.NativeSetupProbe.model_validate(value)


def test_worker_arguments_and_root_are_rejected_before_dbus(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    monkeypatch.setattr(probe.sys, "argv", ["probe", "arbitrary-package.deb"])
    assert probe.main() == 2
    assert "native_setup_arguments_forbidden" in capsys.readouterr().out
    monkeypatch.setattr(probe.sys, "argv", ["probe"])
    monkeypatch.setattr(probe.os, "geteuid", lambda: 0)
    assert probe.main() == 2
    assert "native_setup_root_forbidden" in capsys.readouterr().out


def test_worker_source_has_only_fixed_readonly_dbus_calls() -> None:
    tree = ast.parse(Path(probe.__file__).read_text())
    methods = [node.args[3].value for node in ast.walk(tree)
               if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and node.func.attr == "call_sync"]
    assert methods == ["GetAll", "CheckAuthorization", "GetSessionByPID"]


@pytest.mark.parametrize(("name", "expected"), [
    ("org.freedesktop.login1.NoSessionForPID", "absent"),
    ("org.freedesktop.DBus.Error.AccessDenied", "unknown"),
    ("org.freedesktop.DBus.Error.NoReply", "unknown"),
])
def test_session_scope_uses_exact_error_not_error_text(name: str, expected: str) -> None:
    bus = Bus()
    bus.fail = "GetSessionByPID"
    bus.remote_error = name
    value = discover(bus)
    assert value["login_session"] == expected
    assert value["interactive_agent"] == "not_checked"
    assert value["installation"] == "not_implemented"
    assert "private" not in repr(value)
    native_setup.NativeSetupProbe.model_validate(value)


@pytest.mark.parametrize("session", [None, 1, "/", "/org/freedesktop/login1/session/", "x" * 1000])
def test_invalid_session_reply_is_unknown(session: Any) -> None:
    bus = Bus()
    bus.session = session
    value = discover(bus)
    assert value["login_session"] == "unknown"
    assert value["interactive_agent"] == "not_checked"


@pytest.mark.parametrize(("payload", "expected"), [
    ('print("invalid json")', "native_setup_invalid_reply"),
    ('import sys; sys.exit(3)', "native_setup_worker_failed"),
    ('print("x" * 100000)', "native_setup_output_limit"),
    ('import time; time.sleep(10)', "native_setup_timed_out"),
])
def test_bounded_real_children_are_reaped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str, expected: str) -> None:
    script = tmp_path / "probe.py"
    script.write_text(payload)
    monkeypatch.setattr(native_setup, "PROBE_SCRIPT", script)
    monkeypatch.setattr(native_setup, "PROBE_TIMEOUT_SEC", 0.1)
    real_spawn = asyncio.create_subprocess_exec
    children: list[asyncio.subprocess.Process] = []

    async def spawn(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        assert args == ("/usr/bin/python3", "-I", str(script))
        assert kwargs["close_fds"] and kwargs["stdin"] == asyncio.subprocess.DEVNULL
        assert "DBUS_SYSTEM_BUS_ADDRESS" not in kwargs["env"]
        assert "PYTHONPATH" not in kwargs["env"]
        child = await real_spawn(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    answer = asyncio.run(native_setup.probe_native_setup())
    assert answer.error_code == expected
    assert len(children) == 1 and children[0].returncode is not None


@pytest.mark.parametrize("during_spawn", [False, True])
def test_cancellation_during_spawn_and_read_reaps_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, during_spawn: bool) -> None:
    script = tmp_path / "probe.py"
    script.write_text("import time; time.sleep(10)")
    monkeypatch.setattr(native_setup, "PROBE_SCRIPT", script)
    real_spawn = asyncio.create_subprocess_exec

    async def scenario() -> None:
        created, release = asyncio.Event(), asyncio.Event()
        children: list[asyncio.subprocess.Process] = []

        async def spawn(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
            child = await real_spawn(*args, **kwargs)
            children.append(child)
            created.set()
            if during_spawn:
                await release.wait()
            return child

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        task = asyncio.create_task(native_setup.probe_native_setup())
        await asyncio.wait_for(created.wait(), 2)
        if not during_spawn:
            await asyncio.sleep(0.02)
        task.cancel()
        if during_spawn:
            await asyncio.sleep(0.01)
            task.cancel()
            assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert len(children) == 1 and children[0].returncode is not None

    asyncio.run(scenario())


def test_missing_worker_executable_is_not_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    async def missing(*args: Any, **kwargs: Any) -> asyncio.subprocess.Process:
        raise FileNotFoundError("not logged")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", missing)
    answer = asyncio.run(native_setup.probe_native_setup())
    assert answer.state == "unavailable" and answer.error_code == "native_setup_worker_unavailable"


def test_fragmented_reply_keeps_event_loop_responsive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = json.dumps(discover(Bus()))
    midpoint = len(payload) // 2
    script = tmp_path / "probe.py"
    script.write_text("import sys,time\n"
                      f"sys.stdout.write({payload[:midpoint]!r});sys.stdout.flush()\n"
                      "time.sleep(0.15)\n"
                      f"sys.stdout.write({payload[midpoint:]!r});sys.stdout.flush()\n")
    monkeypatch.setattr(native_setup, "PROBE_SCRIPT", script)

    async def scenario() -> None:
        task = asyncio.create_task(native_setup.probe_native_setup())
        ticks = 0
        while not task.done():
            await asyncio.sleep(0.005)
            ticks += 1
        answer = await task
        assert ticks >= 5
        assert answer.state == "detected" and answer.authorization == "challenge"
        assert answer.installation == "not_implemented"

    asyncio.run(scenario())
