"""Bounded RFB 3.8/None client framing for the pinned noVNC/Xvnc pair.

RFC 6143 section 7.5, plus noVNC's QEMU key, extended pointer, fence,
continuous-update and desktop-size messages. This observes, never rewrites,
payloads. Header storage is <=20 bytes regardless of WebSocket fragmentation.
"""
from __future__ import annotations


class RfbClientFramingError(ValueError):
    pass


class RfbClientActivity:
    MAX_PACKET_BYTES = 1024 * 1024
    HEADERS = {0: 20, 2: 4, 3: 10, 4: 8, 5: 2, 6: 8,
               150: 10, 248: 9, 250: 4, 251: 8, 255: 12}

    def __init__(self) -> None:
        self._phase = "version"
        self._header = bytearray()
        self._needed = 12
        self._remaining = 0
        self._input_pending = False

    def feed(self, data: bytes) -> bool:
        """True only after a complete key/pointer packet; no payload is retained."""
        offset = 0
        activity = False
        while offset < len(data):
            if self._remaining:
                count = min(self._remaining, len(data)-offset)
                offset += count
                self._remaining -= count
                if not self._remaining:
                    activity |= self._input_pending
                    self._input_pending = False
                continue
            count = min(self._needed-len(self._header), len(data)-offset)
            self._header.extend(data[offset:offset+count])
            offset += count
            if len(self._header) < self._needed:
                continue
            if self._phase == "version":
                if self._header != b"RFB 003.008\n":
                    raise RfbClientFramingError("unsupported RFB version")
                self._phase, self._needed = "security", 1
            elif self._phase == "security":
                if self._header != b"\x01":
                    raise RfbClientFramingError("unsupported RFB security framing")
                self._phase, self._needed = "init", 1
            elif self._phase == "init":
                if self._header[0] not in (0, 1):
                    raise RfbClientFramingError("invalid RFB client initialization")
                self._phase, self._needed = "message", 1
            elif len(self._header) == 1:
                try:
                    self._needed = self.HEADERS[self._header[0]]
                except KeyError as exc:
                    raise RfbClientFramingError("unsupported RFB client message") from exc
                continue
            else:
                header = self._header
                kind = header[0]
                payload = 0
                is_input = kind in (4, 5, 255)
                if kind == 2:
                    payload = 4 * int.from_bytes(header[2:4], "big")
                elif kind == 5:
                    payload = 4 + bool(header[1] & 0x80)
                elif kind == 6:
                    payload = abs(int.from_bytes(header[4:8], "big", signed=True))
                elif kind == 248:
                    payload = header[8]
                    if payload > 64:
                        raise RfbClientFramingError("RFB fence payload exceeds limit")
                elif kind == 251:
                    payload = 16 * header[6]
                elif kind == 255 and header[1] != 0:
                    raise RfbClientFramingError("unsupported RFB extended key message")
                if len(header) + payload > self.MAX_PACKET_BYTES:
                    raise RfbClientFramingError("RFB client packet exceeds limit")
                self._remaining = payload
                self._input_pending = is_input and bool(payload)
                activity |= is_input and not payload
                self._needed = 1
            self._header.clear()
        return activity
