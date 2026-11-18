"""AES-256-GCM operations backed by the cryptography package."""

from __future__ import annotations

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.core.crypto.constants import AES_KEY_BYTES, GCM_TAG_BYTES, NONCE_BYTES
from backend.core.crypto.exceptions import AuthenticationError, CryptoInputError


def _validate_inputs(key: bytes, nonce: bytes, data: bytes, aad: bytes) -> None:
    if not isinstance(key, bytes) or len(key) != AES_KEY_BYTES:
        raise CryptoInputError(f"AES-256-GCM key must be exactly {AES_KEY_BYTES} bytes.")
    if not isinstance(nonce, bytes) or len(nonce) != NONCE_BYTES:
        raise CryptoInputError(f"AES-GCM nonce must be exactly {NONCE_BYTES} bytes.")
    if not isinstance(data, bytes):
        raise CryptoInputError("AES-GCM input must be bytes.")
    if not isinstance(aad, bytes):
        raise CryptoInputError("AES-GCM AAD must be bytes.")


def encrypt_aes_gcm(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    """Encrypt and authenticate; the returned bytes include the 16-byte tag."""
    _validate_inputs(key, nonce, plaintext, aad)
    return AESGCM(key).encrypt(nonce, plaintext, aad)


def decrypt_aes_gcm(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    """Authenticate and decrypt; unauthenticated plaintext is never returned."""
    _validate_inputs(key, nonce, ciphertext, aad)
    if len(ciphertext) < GCM_TAG_BYTES:
        raise CryptoInputError("AES-GCM ciphertext is shorter than its authentication tag.")

    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise AuthenticationError(
            "AES-GCM authentication failed; passphrase or payload may be incorrect or modified."
        ) from exc
