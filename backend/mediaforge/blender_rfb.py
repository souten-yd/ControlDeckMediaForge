"""Authenticated, bounded WebSocket relay to a private Unix-domain RFB socket."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect


MAX_BROWSER_MESSAGE_BYTES = 1024 * 1024
RFB_READ_BYTES = 64 * 1024
REVALIDATE_INTERVAL_SEC = 15.0


class BlenderRfbError(RuntimeError):
    def __init__(self, code: int, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


def requested_protocols(websocket: WebSocket) -> tuple[str, ...]:
    raw = websocket.headers.get("sec-websocket-protocol", "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


async def relay_rfb(
    websocket: WebSocket,
    socket_path: Path,
    *,
    revalidate: Callable[[], Awaitable[bool]] | None = None,
) -> None:
    """Relay binary frames only. Authentication and reservation happen upstream."""
    if requested_protocols(websocket) != ("binary",):
        await websocket.close(code=4406, reason="binary subprotocol required")
        return
    try:
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
    except (OSError, ValueError):
        await websocket.close(code=1011, reason="Blender display is unavailable")
        return
    accepted = False

    async def browser_to_rfb() -> None:
        while True:
            message = await websocket.receive()
            kind = message.get("type")
            if kind == "websocket.disconnect":
                return
            if kind != "websocket.receive" or message.get("text") is not None:
                raise BlenderRfbError(4400, "binary frames required")
            content = message.get("bytes")
            if not isinstance(content, bytes):
                raise BlenderRfbError(4400, "binary frames required")
            if len(content) > MAX_BROWSER_MESSAGE_BYTES:
                raise BlenderRfbError(4409, "RFB frame too large")
            writer.write(content)
            await writer.drain()

    async def rfb_to_browser() -> None:
        while content := await reader.read(RFB_READ_BYTES):
            await websocket.send_bytes(content)

    async def validate_identity() -> None:
        if revalidate is None:
            await asyncio.Future()
        while True:
            await asyncio.sleep(REVALIDATE_INTERVAL_SEC)
            if not await revalidate():
                raise BlenderRfbError(4403, "host service token expired")

    tasks: list[asyncio.Task[None]] = []
    try:
        await websocket.accept(subprotocol="binary")
        accepted = True
        tasks = [
            asyncio.create_task(browser_to_rfb()),
            asyncio.create_task(rfb_to_browser()),
            asyncio.create_task(validate_identity()),
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()
    except WebSocketDisconnect:
        pass
    except BlenderRfbError as exc:
        if accepted:
            await websocket.close(code=exc.code, reason=exc.reason)
    except (ConnectionError, OSError, RuntimeError):
        if accepted:
            try:
                await websocket.close(code=1011, reason="Blender display disconnected")
            except RuntimeError:
                pass
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass
