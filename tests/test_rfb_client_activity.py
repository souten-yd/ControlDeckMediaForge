from __future__ import annotations

import struct

import pytest

from mediaforge.rfb_client_activity import RfbClientActivity, RfbClientFramingError

HANDSHAKE = b"RFB 003.008\n\x01\x01"
KEY = b"\x04\x01\0\0\0\0\0a"
POINTER = b"\x05\x01\0\x20\0\x30"
EXT_POINTER = b"\x05\x80\0\x20\0\x30\x01"
EXT_KEY = b"\xff\x00\0\x01\0\0\0a\0\0\0\x1e"
CONTROL = [
    b"\0" * 20,
    b"\x02\0\0\x02" + KEY,
    b"\x03\x01" + b"\0" * 8,
    b"\x06\0\0\0" + struct.pack(">i", len(KEY)) + KEY,
    b"\x06\0\0\0" + struct.pack(">i", -len(POINTER)) + POINTER,
    b"\x96\x01" + b"\0" * 8,
    b"\xf8" + b"\0" * 7 + bytes([len(EXT_KEY)]) + EXT_KEY,
    b"\xfa\0\x01\x01",
    b"\xfb\0\0\x20\0\x30\x01\0" + KEY * 2,
]


@pytest.mark.parametrize("packet", [KEY, POINTER, EXT_POINTER, EXT_KEY])
def test_input_only_counts_once_packet_is_complete(packet: bytes) -> None:
    for split in range(len(packet)):
        parser = RfbClientActivity()
        assert not parser.feed(HANDSHAKE)
        assert not parser.feed(packet[:split])
        assert parser.feed(packet[split:])
        assert not parser.feed(b"")


@pytest.mark.parametrize("packet", CONTROL)
def test_control_payload_cannot_look_like_input(packet: bytes) -> None:
    for split in range(len(packet)+1):
        parser = RfbClientActivity()
        assert not parser.feed(HANDSHAKE + packet[:split])
        assert not parser.feed(packet[split:])
        assert parser.feed(KEY)


def test_byte_fragmentation_and_coalescing_preserve_framing() -> None:
    data = HANDSHAKE + b"".join(CONTROL) + KEY + POINTER + EXT_KEY + EXT_POINTER
    parser = RfbClientActivity()
    hits = 0
    for value in data:
        hits += parser.feed(bytes([value]))
        assert len(parser._header) <= 20
    assert hits == 4
    assert RfbClientActivity().feed(data)


def test_large_payload_is_skipped_without_accumulation() -> None:
    parser = RfbClientActivity()
    assert not parser.feed(HANDSHAKE + b"\x06\0\0\0" + struct.pack(">i", 100_000))
    for _ in range(100):
        assert not parser.feed(b"\x04" * 1000)
        assert not parser._header
    assert parser.feed(KEY)


@pytest.mark.parametrize("data", [
    b"RFB 003.003\n", b"RFB 003.008\n\x02", b"RFB 003.008\n\x01\x02",
    HANDSHAKE + b"\x01", HANDSHAKE + b"\xff\x01" + b"\0" * 10,
    HANDSHAKE + b"\xf8" + b"\0" * 7 + b"\x41",
    HANDSHAKE + b"\x06\0\0\0\x7f\xff\xff\xff",
    HANDSHAKE + b"\x06\0\0\0\x80\0\0\0",
])
def test_unknown_or_oversized_framing_is_rejected(data: bytes) -> None:
    with pytest.raises(RfbClientFramingError):
        RfbClientActivity().feed(data)


def test_display_polling_never_refreshes_idle_activity() -> None:
    parser = RfbClientActivity()
    assert not parser.feed(HANDSHAKE)
    for _ in range(2000):
        assert not parser.feed(CONTROL[2])
    assert parser.feed(POINTER)
