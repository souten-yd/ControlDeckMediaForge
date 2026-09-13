from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from mediaforge.host.ai import HostAIError, HostAIGateway
from mediaforge.host.client import ControlDeckHostClient, HostIdentity


IDENTITY = HostIdentity("Bearer test", "media-forge", "user:1", 2**31, frozenset({"ai.inference"}))


class Stream(httpx.AsyncByteStream):
    def __init__(self, chunks, *, hold=False):
        self.chunks = chunks
        self.hold = hold
        self.started = asyncio.Event()
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk
        self.started.set()
        if self.hold:
            await asyncio.Event().wait()

    async def aclose(self):
        self.closed = True


def event(value):
    return b"data: " + json.dumps(value, ensure_ascii=False).encode() + b"\n\n"


async def invoke(stream, *, status=200, content_type="text/event-stream", **options):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"content-type": content_type}, stream=stream)

    host = ControlDeckHostClient("http://host", transport=httpx.MockTransport(handler))
    try:
        result = await HostAIGateway(host).complete_streamed(
            IDENTITY, "text.generate", [{"role": "user", "content": "draft"}], **options,
        )
        assert len(calls) == 1
        assert calls[0].url.path == "/api/v1/addon-runtime/media-forge/ai/stream"
        assert calls[0].headers["Authorization"] == "Bearer test"
        assert calls[0].headers["X-Control-Deck-Addon-ID"] == "media-forge"
        assert "model" not in json.loads(calls[0].content)
        return result
    finally:
        await host.close()
        assert stream.closed


def test_split_utf8_and_multiple_events_are_assembled_only_at_done():
    wire = event({"type": "content", "content": "髪"}) + event({"type": "usage"}) + event({"type": "done"})
    result = asyncio.run(invoke(Stream([wire[i:i+1] for i in range(len(wire))])))
    assert result.content == "髪" and result.capability == "text.generate"


def test_crlf_multiline_data_and_comments():
    wire = b': keepalive\r\ndata: {"type":"content",\r\ndata: "content":"{}"}\r\n\r\n' + event({"type": "done"})
    assert asyncio.run(invoke(Stream([wire]))).content == "{}"


@pytest.mark.parametrize("wire", [
    b"", event({"type": "content", "content": "partial"}),
    b"data: bad\n\n", event([]), event({"type": "unexpected"}),
    event({"type": "content", "content": 123}), b"data: \xff\n\n",
])
def test_truncated_or_invalid_stream_never_returns_partial_success(wire):
    with pytest.raises(HostAIError, match="Invalid|without done"):
        asyncio.run(invoke(Stream([wire])))


def test_error_event_fails_without_retry():
    with pytest.raises(HostAIError, match="stream failed"):
        asyncio.run(invoke(Stream([event({"type": "error", "code": "generation_failed"})])))


@pytest.mark.parametrize("options,wire", [
    ({"max_output_bytes": 2}, event({"type": "content", "content": "髪"})),
    ({}, b"x" * (2 * 1024 * 1024 + 1)),
])
def test_wire_and_utf8_output_bounds(options, wire):
    with pytest.raises(HostAIError, match="too large"):
        asyncio.run(invoke(Stream([wire]), **options))


def test_missing_permission_and_wrong_content_type_fail_closed():
    with pytest.raises(HostAIError, match="not granted"):
        asyncio.run(invoke(Stream([]), status=403))
    with pytest.raises(HostAIError, match="Expected"):
        asyncio.run(invoke(Stream([]), content_type="application/json"))


def test_actual_task_cancel_closes_transport_without_retry():
    async def run():
        stream = Stream([event({"type": "content", "content": "partial"})], hold=True)
        task = asyncio.create_task(invoke(stream))
        await stream.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert stream.closed
    asyncio.run(run())


def test_absolute_deadline_closes_stalled_stream(monkeypatch):
    original = asyncio.timeout
    monkeypatch.setattr("mediaforge.host.ai.asyncio.timeout", lambda _: original(.01))
    with pytest.raises(HostAIError, match="interrupted"):
        asyncio.run(invoke(Stream([], hold=True)))
