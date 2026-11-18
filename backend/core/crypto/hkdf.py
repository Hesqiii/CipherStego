"""RFC 5869 HKDF-SHA256 wrapper with explicit input validation."""

from __future__ import annotations

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from backend.core.crypto.constants import HKDF_SHA256_MAX_BYTES
from backend.core.crypto.exceptions import CryptoInputError


def hkdf_sha256(
    ikm: bytes,
    salt: bytes | None,
    info: bytes,
    length: int,
) -> bytes:
    """Derive output key material with RFC 5869 HKDF-SHA256."""
    if not isinstance(ikm, bytes) or not ikm:
        raise CryptoInputError("HKDF input key material must be non-empty bytes.")
    if salt is not None and not isinstance(salt, bytes):
        raise CryptoInputError("HKDF salt must be bytes or None.")
    if not isinstance(info, bytes):
        raise CryptoInputError("HKDF info must be bytes.")
    if isinstance(length, bool) or not isinstance(length, int):
        raise CryptoInputError("HKDF output length must be an integer.")
    if not 1 <= length <= HKDF_SHA256_MAX_BYTES:
        raise CryptoInputError(
            f"HKDF output length must be between 1 and {HKDF_SHA256_MAX_BYTES} bytes."
        )

    return HKDF(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        info=info,
    ).derive(ikm)
