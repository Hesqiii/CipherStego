"""Typed results for cryptographic operations."""

from dataclasses import dataclass, field

from backend.core.steganography.header import PayloadHeader


@dataclass(frozen=True)
class DerivedKeys:
    encryption_key: bytes = field(repr=False)
    position_key: bytes = field(repr=False)


@dataclass(frozen=True)
class EncryptedPayload:
    header: PayloadHeader
    ciphertext: bytes = field(repr=False)

    @property
    def header_bytes(self) -> bytes:
        return self.header.serialize()
