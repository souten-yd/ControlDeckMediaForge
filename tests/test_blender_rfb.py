from __future__ import annotations

import asyncio
from pathlib import Path

from mediaforge.blender_rfb import MAX_BROWSER_MESSAGE_BYTES, relay_rfb


class FakeWebSocket:
    def __init__(self, protocols: str, messages: list[dict] | None = None) -> None:
        self.headers = {"sec-websocket-protocol": protocols}
        self.messages: asyncio.Queue[dict] = asyncio.Queue()
        for message in messages or []:
            self.messages.put_nowait(message)
        self.accepted: str | None = None
        self.sent: list[bytes] = []
        self.closed: tuple[int, str] | None = None

    async def accept(self, *, subprotocol: str | None = None) -> None:
        self.accepted = subprotocol

    async def receive(self) -> dict:
        return await self.messages.get()

    async def send_bytes(self, content: bytes) -> None:
        self.sent.append(content)

    async def close(self, *, code: int, reason: str) -> None:
        self.closed = (code, reason)


def test_relay_requires_exact_binary_subprotocol_without_opening_socket(tmp_path: Path) -> None:
    websocket = FakeWebSocket("control-deck-bridge.nonce, binary")
    asyncio.run(relay_rfb(websocket, tmp_path / "absent.sock"))  # type: ignore[arg-type]
    assert websocket.accepted is None
    assert websocket.closed == (4406, "binary subprotocol required")


def test_relay_moves_binary_both_directions_over_unix_socket(tmp_path: Path) -> None:
    async def scenario() -> None:
        path = tmp_path / "rfb.sock"

        async def echo(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            writer.write(b"RFB 003.008\n")
            await writer.drain()
            content = await reader.readexactly(4)
            writer.write(content.upper())
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_unix_server(echo, path=str(path))
        websocket = FakeWebSocket("binary", [{"type": "websocket.receive", "bytes": b"test"}])
        try:
            await asyncio.wait_for(
                relay_rfb(websocket, path), timeout=2  # type: ignore[arg-type]
            )
        finally:
            server.close()
            await server.wait_closed()
        assert websocket.accepted == "binary"
        assert b"".join(websocket.sent) == b"RFB 003.008\nTEST"
        assert websocket.closed is None

    asyncio.run(scenario())


def test_relay_rejects_text_and_oversized_browser_messages(tmp_path: Path) -> None:
    async def case(message: dict, expected_code: int) -> None:
        path = tmp_path / f"rfb-{expected_code}.sock"

        async def hold(_reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await asyncio.sleep(1)
            writer.close()

        server = await asyncio.start_unix_server(hold, path=str(path))
        websocket = FakeWebSocket("binary", [message])
        try:
            await asyncio.wait_for(
                relay_rfb(websocket, path), timeout=2  # type: ignore[arg-type]
            )
        finally:
            server.close()
            await server.wait_closed()
        assert websocket.closed is not None and websocket.closed[0] == expected_code

    async def scenario() -> None:
        await case({"type": "websocket.receive", "text": "no"}, 4400)
        await case(
            {"type": "websocket.receive", "bytes": b"x" * (MAX_BROWSER_MESSAGE_BYTES + 1)},
            4409,
        )

    asyncio.run(scenario())
