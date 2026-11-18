"""High-level payload encryption using the proposal's authenticated header."""

from __future__ import annotations

import secrets

from backend.core.crypto.aes_gcm import decrypt_aes_gcm, encrypt_aes_gcm
from backend.core.crypto.constants import GCM_TAG_BYTES, NONCE_BYTES, SALT_BYTES, UINT32_MAX
from backend.core.crypto.exceptions import CryptoInputError, PayloadFormatError
from backend.core.crypto.key_derivation import derive_keys, generate_salt
from backend.core.crypto.models import DerivedKeys, EncryptedPayload
from backend.core.steganography.header import PayloadHeader, parse_payload_header


def generate_nonce() -> bytes:
    """Generate a fresh 96-bit nonce from the operating system CSPRNG."""
    return secrets.token_bytes(NONCE_BYTES)


def encrypt_payload(passphrase: str, plaintext: bytes) -> EncryptedPayload:
    encrypted, _ = encrypt_payload_with_keys(passphrase, plaintext)
    return encrypted


def encrypt_payload_with_keys(
    passphrase: str, plaintext: bytes
) -> tuple[EncryptedPayload, DerivedKeys]:
    """Build the AAD header, encrypt, and return the same request-scoped keys."""
    if not isinstance(plaintext, bytes):
        raise CryptoInputError("Payload plaintext must be bytes.")
    if len(plaintext) > UINT32_MAX - GCM_TAG_BYTES:
        raise PayloadFormatError("Payload is too large for the 4-byte ciphertext length field.")

    salt = generate_salt()
    nonce = generate_nonce()
    ciphertext_length = len(plaintext) + GCM_TAG_BYTES
    header = PayloadHeader(salt, nonce, ciphertext_length)
    header_bytes = header.serialize()
    keys = derive_keys(passphrase, salt)
    ciphertext = encrypt_aes_gcm(keys.encryption_key, nonce, plaintext, header_bytes)
    return EncryptedPayload(header=header, ciphertext=ciphertext), keys


def decrypt_payload(passphrase: str, header_bytes: bytes, ciphertext: bytes) -> bytes:
    """Authenticate a payload against its serialized header before returning it."""
    header = parse_payload_header(header_bytes)
    if not isinstance(ciphertext, bytes):
        raise CryptoInputError("Payload ciphertext must be bytes.")
    if len(ciphertext) != header.ciphertext_length:
        raise PayloadFormatError(
            "Ciphertext length does not match the length declared in the header."
        )

    keys = derive_keys(passphrase, header.salt)
    return decrypt_payload_with_keys(header_bytes, ciphertext, keys)


def decrypt_payload_with_keys(
    header_bytes: bytes, ciphertext: bytes, keys: DerivedKeys
) -> bytes:
    """Authenticate using request-scoped keys already derived from this header."""
    header = parse_payload_header(header_bytes)
    if not isinstance(ciphertext, bytes):
        raise CryptoInputError("Payload ciphertext must be bytes.")
    if len(ciphertext) != header.ciphertext_length:
        raise PayloadFormatError(
            "Ciphertext length does not match the length declared in the header."
        )
    # Use the received serialized bytes themselves as AAD, byte-for-byte.
    return decrypt_aes_gcm(keys.encryption_key, header.nonce, ciphertext, header_bytes)
