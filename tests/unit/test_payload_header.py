"""Payload-header serialization and validation tests."""

import pytest

from backend.core.crypto.constants import HEADER_BYTES, NONCE_BYTES, SALT_BYTES
from backend.core.crypto.exceptions import PayloadFormatError
from backend.core.steganography.header import (
    PayloadHeader,
    parse_payload_header,
    serialize_payload_header,
)


def test_header_serializes_to_exactly_32_bytes_and_round_trips() -> None:
    header = PayloadHeader(b"s" * SALT_BYTES, b"n" * NONCE_BYTES, 0x01020304)
    encoded = serialize_payload_header(header)

    assert len(encoded) == HEADER_BYTES
    assert encoded == b"s" * 16 + b"n" * 12 + bytes.fromhex("01020304")
    assert parse_payload_header(encoded) == header


def test_header_length_uses_unsigned_big_endian_encoding() -> None:
    header = PayloadHeader(b"s" * 16, b"n" * 12, 0x01020304)
    assert header.serialize()[-4:] == b"\x01\x02\x03\x04"


def test_header_rejects_non_exact_serialized_length() -> None:
    with pytest.raises(PayloadFormatError):
        parse_payload_header(b"h" * 31)
    with pytest.raises(PayloadFormatError):
        parse_payload_header(b"h" * 33)


def test_header_requires_ciphertext_to_include_gcm_tag() -> None:
    with pytest.raises(PayloadFormatError):
        PayloadHeader(b"s" * 16, b"n" * 12, 15)
    assert PayloadHeader(b"s" * 16, b"n" * 12, 16).ciphertext_length == 16


def test_header_accepts_uint32_boundary_values() -> None:
    low = PayloadHeader(b"s" * 16, b"n" * 12, 16)
    high = PayloadHeader(b"s" * 16, b"n" * 12, 0xFFFFFFFF)
    assert parse_payload_header(low.serialize()) == low
    assert parse_payload_header(high.serialize()) == high


@pytest.mark.parametrize(
    "salt,nonce,length",
    [
        (b"short", b"n" * 12, 16),
        (b"s" * 16, b"short", 16),
        (b"s" * 16, b"n" * 12, 0),
        (b"s" * 16, b"n" * 12, 1 << 32),
        (b"s" * 16, b"n" * 12, True),
    ],
)
def test_invalid_header_fields_are_rejected(salt: bytes, nonce: bytes, length: int) -> None:
    with pytest.raises(PayloadFormatError):
        PayloadHeader(salt, nonce, length)
