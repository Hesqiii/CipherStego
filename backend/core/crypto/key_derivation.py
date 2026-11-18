"""PBKDF2-HMAC-SHA256 and purpose-separated HKDF key derivation."""

from __future__ import annotations

import secrets

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from backend.core.crypto.constants import (
    AES_KEY_BYTES,
    HKDF_ENCRYPTION_INFO,
    HKDF_KEY_BYTES,
    HKDF_POSITION_INFO,
    MASTER_KEY_BYTES,
    PBKDF2_ITERATIONS,
    SALT_BYTES,
)
from backend.core.crypto.exceptions import CryptoInputError
from backend.core.crypto.hkdf import hkdf_sha256
from backend.core.crypto.models import DerivedKeys


def generate_salt() -> bytes:
    """Generate a 16-byte salt using the operating system CSPRNG."""
    return secrets.token_bytes(SALT_BYTES)


def pbkdf2_hmac_sha256(
    password: bytes,
    salt: bytes,
    iterations: int,
    length: int = MASTER_KEY_BYTES,
) -> bytes:
    """Low-level PBKDF2 primitive; parameters are explicit for test vectors."""
    if not isinstance(password, bytes) or not password:
        raise CryptoInputError("PBKDF2 password must be non-empty bytes.")
    if not isinstance(salt, bytes) or not salt:
        raise CryptoInputError("PBKDF2 salt must be non-empty bytes.")
    if isinstance(iterations, bool) or not isinstance(iterations, int) or iterations < 1:
        raise CryptoInputError("PBKDF2 iterations must be a positive integer.")
    if isinstance(length, bool) or not isinstance(length, int) or length < 1:
        raise CryptoInputError("PBKDF2 output length must be a positive integer.")

    return PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=length,
        salt=salt,
        iterations=iterations,
    ).derive(password)


def derive_master_key(passphrase: str, salt: bytes) -> bytes:
    """Derive the 32-byte master key using the proposal's fixed parameters.

    Passphrases are encoded as UTF-8 exactly as supplied. No normalization,
    trimming, or case folding is performed.
    """
    if not isinstance(passphrase, str) or not passphrase:
        raise CryptoInputError("Passphrase must be a non-empty string.")
    if not isinstance(salt, bytes) or len(salt) != SALT_BYTES:
        raise CryptoInputError(f"PBKDF2 salt must be exactly {SALT_BYTES} bytes.")

    return pbkdf2_hmac_sha256(
        passphrase.encode("utf-8"),
        salt,
        iterations=PBKDF2_ITERATIONS,
        length=MASTER_KEY_BYTES,
    )


def derive_subkeys(master_key: bytes) -> DerivedKeys:
    """Derive independent AES and future randomized-LSB keys.

    HKDF uses no explicit salt. Per RFC 5869 this is equivalent to a
    HashLen-byte all-zero salt. Domain separation is provided by the two
    distinct application context labels.
    """
    if not isinstance(master_key, bytes) or len(master_key) != MASTER_KEY_BYTES:
        raise CryptoInputError(f"Master key must be exactly {MASTER_KEY_BYTES} bytes.")

    encryption_key = hkdf_sha256(
        ikm=master_key,
        salt=None,
        info=HKDF_ENCRYPTION_INFO,
        length=AES_KEY_BYTES,
    )
    position_key = hkdf_sha256(
        ikm=master_key,
        salt=None,
        info=HKDF_POSITION_INFO,
        length=HKDF_KEY_BYTES,
    )
    return DerivedKeys(encryption_key=encryption_key, position_key=position_key)


def derive_keys(passphrase: str, salt: bytes) -> DerivedKeys:
    """Apply the proposal's passphrase KDF followed by HKDF key separation."""
    return derive_subkeys(derive_master_key(passphrase, salt))
