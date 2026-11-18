"""Proposal-compatible 32-byte payload header; no LSB code is implemented."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from backend.core.crypto.constants import (
    GCM_TAG_BYTES,
    HEADER_BYTES,
    NONCE_BYTES,
    SALT_BYTES,
    UINT32_MAX,
)
from backend.core.crypto.exceptions import PayloadFormatError


@dataclass(frozen=True)
class PayloadHeader:
    salt: bytes
    nonce: bytes
    ciphertext_length: int

    def __post_init__(self) -> None:
        if not isinstance(self.salt, bytes) or len(self.salt) != SALT_BYTES:
            raise PayloadFormatError(f"Header salt must be exactly {SALT_BYTES} bytes.")
        if not isinstance(self.nonce, bytes) or len(self.nonce) != NONCE_BYTES:
            raise PayloadFormatError(f"Header nonce must be exactly {NONCE_BYTES} bytes.")
        if isinstance(self.ciphertext_length, bool) or not isinstance(self.ciphertext_length, int):
            raise PayloadFormatError("Header ciphertext length must be an integer.")
        if not GCM_TAG_BYTES <= self.ciphertext_length <= UINT32_MAX:
            raise PayloadFormatError(
                f"Header ciphertext length must be between {GCM_TAG_BYTES} and {UINT32_MAX} bytes."
            )

    def serialize(self) -> bytes:
        """Serialize salt || nonce || uint32 ciphertext length (big-endian)."""
        serialized = self.salt + self.nonce + struct.pack(">I", self.ciphertext_length)
        if len(serialized) != HEADER_BYTES:
            raise AssertionError("Internal header size invariant was violated.")
        return serialized

    @classmethod
    def parse(cls, data: bytes) -> "PayloadHeader":
        return parse_payload_header(data)


def serialize_payload_header(header: PayloadHeader) -> bytes:
    """Dedicated serializer for the fixed proposal header format."""
    if not isinstance(header, PayloadHeader):
        raise TypeError("header must be a PayloadHeader.")
    return header.serialize()


def parse_payload_header(data: bytes) -> PayloadHeader:
    """Parse exactly 32 bytes and validate field sizes and GCM tag length."""
    if not isinstance(data, bytes) or len(data) != HEADER_BYTES:
        raise PayloadFormatError(f"Payload header must be exactly {HEADER_BYTES} bytes.")
    salt = data[:SALT_BYTES]
    nonce_start = SALT_BYTES
    nonce_end = nonce_start + NONCE_BYTES
    nonce = data[nonce_start:nonce_end]
    ciphertext_length = struct.unpack(">I", data[nonce_end:HEADER_BYTES])[0]
    return PayloadHeader(salt, nonce, ciphertext_length)
