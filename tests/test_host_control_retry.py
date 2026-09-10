from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from mediaforge.host.client import ControlDeckHostClient, HostApiError, HostIdentity


@pytest.mark.parametrize("second", ["running", "canceled", "protocol", "denied"])
@pytest.mark.parametrize("failure_type", [httpx.RemoteProtocolError, httpx.ReadError])
def test_control_protocol_disconnect_retries_once(second: str, failure_type: type[httpx.RequestError]) -> None:
    async def run() -> None:
        calls: list[httpx.Request] = []

        async def respond(request: httpx.Request) -> httpx.Response:
            calls.append(request)
            if len(calls) == 1 or second == "protocol":
                raise failure_type("connection closed while reading")
            if second == "denied":
                return httpx.Response(403)
            return httpx.Response(200, json={"host_job_id": "child", "status": second,
                "cancel_requested": second == "canceled"})

        client = ControlDeckHostClient("http://host", transport=httpx.MockTransport(respond))
        identity = HostIdentity("Bearer test", "media-forge", "job:child",
            int(time.time()) + 60, frozenset({"jobs.write"}))
        try:
            if second in {"protocol", "denied"}:
                with pytest.raises(HostApiError) as caught:
                    await client.job_control(identity, "child")
                assert caught.value.code == ("host_unreachable" if second == "protocol" else "host_request_rejected")
            else:
                assert (await client.job_control(identity, "child"))["status"] == second
            assert len(calls) == 2
            assert all(call.method == "GET" and call.url.path.endswith("/jobs/child/control") for call in calls)
            assert calls[0].headers == calls[1].headers
        finally:
            await client.close()

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["timeout", "connect", "expired", "cancel", "json", "denied"])
def test_control_does_not_retry_other_failures(failure: str) -> None:
    async def run() -> None:
        count = 0

        async def respond(request: httpx.Request) -> httpx.Response:
            nonlocal count
            count += 1
            if failure == "json":
                return httpx.Response(200, content=b"invalid")
            if failure == "denied":
                return httpx.Response(401)
            raise {"timeout": httpx.ReadTimeout, "connect": httpx.ConnectError,
                "expired": httpx.RemoteProtocolError, "cancel": asyncio.CancelledError}[failure]("test")

        client = ControlDeckHostClient("http://host", transport=httpx.MockTransport(respond))
        identity = HostIdentity("Bearer test", "media-forge", "job:child",
            int(time.time()) + (-1 if failure == "expired" else 60), frozenset({"jobs.write"}))
        try:
            with pytest.raises(asyncio.CancelledError if failure == "cancel" else HostApiError):
                await client.job_control(identity, "child")
            assert count == 1
        finally:
            await client.close()

    asyncio.run(run())


@pytest.mark.parametrize("action", ["create", "update", "refresh", "terminal"])
def test_host_writes_are_never_replayed(action: str) -> None:
    async def run() -> None:
        count = 0

        async def respond(request: httpx.Request) -> httpx.Response:
            nonlocal count
            count += 1
            raise httpx.RemoteProtocolError("disconnected")

        client = ControlDeckHostClient("http://host", transport=httpx.MockTransport(respond))
        identity = HostIdentity("Bearer test", "media-forge", "job:child",
            int(time.time()) + 60, frozenset({"jobs.write"}))
        try:
            with pytest.raises(HostApiError):
                if action == "create":
                    await client.create_or_attach_job(identity, title="test", detached=True)
                elif action == "update":
                    await client.update_job(identity, "child", {})
                elif action == "refresh":
                    await client.refresh_job_credential(identity, "child")
                else:
                    await client.reconcile_job_terminal(identity, "child", {})
            assert count == 1
        finally:
            await client.close()

    asyncio.run(run())
