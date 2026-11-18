"""AES-GCM and payload envelope tests."""

import pytest

from backend.core.crypto.aes_gcm import decrypt_aes_gcm, encrypt_aes_gcm
from backend.core.crypto.constants import GCM_TAG_BYTES
from backend.core.crypto.exceptions import AuthenticationError, CryptoInputError, PayloadFormatError
from backend.core.crypto.payload_crypto import decrypt_payload, encrypt_payload, generate_nonce

KEY = b"k" * 32
NONCE = b"n" * 12
AAD = b"authenticated header"


def test_aes_gcm_round_trip() -> None:
    plaintext = b"private document bytes"
    ciphertext = encrypt_aes_gcm(KEY, NONCE, plaintext, AAD)

    assert len(ciphertext) == len(plaintext) + GCM_TAG_BYTES
    assert decrypt_aes_gcm(KEY, NONCE, ciphertext, AAD) == plaintext


def test_wrong_key_fails_authentication() -> None:
    ciphertext = encrypt_aes_gcm(KEY, NONCE, b"message", AAD)
    with pytest.raises(AuthenticationError):
        decrypt_aes_gcm(b"x" * 32, NONCE, ciphertext, AAD)


def test_modified_ciphertext_fails_authentication() -> None:
    ciphertext = bytearray(encrypt_aes_gcm(KEY, NONCE, b"message", AAD))
    ciphertext[0] ^= 1
    with pytest.raises(AuthenticationError):
        decrypt_aes_gcm(KEY, NONCE, bytes(ciphertext), AAD)


def test_modified_tag_fails_authentication() -> None:
    ciphertext = bytearray(encrypt_aes_gcm(KEY, NONCE, b"message", AAD))
    ciphertext[-1] ^= 1
    with pytest.raises(AuthenticationError):
        decrypt_aes_gcm(KEY, NONCE, bytes(ciphertext), AAD)


def test_modified_aad_fails_authentication() -> None:
    ciphertext = encrypt_aes_gcm(KEY, NONCE, b"message", AAD)
    with pytest.raises(AuthenticationError):
        decrypt_aes_gcm(KEY, NONCE, ciphertext, AAD + b"!")


@pytest.mark.parametrize(
    "key,nonce",
    [(b"short", NONCE), (KEY, b"short")],
)
def test_invalid_key_or_nonce_lengths_are_rejected(key: bytes, nonce: bytes) -> None:
    with pytest.raises(CryptoInputError):
        encrypt_aes_gcm(key, nonce, b"data", AAD)


def test_ciphertext_shorter_than_tag_is_rejected() -> None:
    with pytest.raises(CryptoInputError):
        decrypt_aes_gcm(KEY, NONCE, b"short", AAD)


def test_empty_plaintext_is_supported() -> None:
    ciphertext = encrypt_aes_gcm(KEY, NONCE, b"", AAD)
    assert len(ciphertext) == GCM_TAG_BYTES
    assert decrypt_aes_gcm(KEY, NONCE, ciphertext, AAD) == b""


def test_high_level_payload_binds_exact_header_as_aad() -> None:
    payload = encrypt_payload("correct horse", b"PDF-like bytes")
    assert len(payload.header_bytes) == 32
    assert payload.header.ciphertext_length == len(payload.ciphertext)
    assert payload.header.ciphertext_length == len(b"PDF-like bytes") + GCM_TAG_BYTES
    assert decrypt_payload("correct horse", payload.header_bytes, payload.ciphertext) == b"PDF-like bytes"


def test_wrong_passphrase_does_not_return_plaintext() -> None:
    payload = encrypt_payload("right passphrase", b"secret")
    with pytest.raises(AuthenticationError):
        decrypt_payload("wrong passphrase", payload.header_bytes, payload.ciphertext)


def test_ciphertext_length_mismatch_is_rejected_before_decryption() -> None:
    payload = encrypt_payload("passphrase", b"message")
    with pytest.raises(PayloadFormatError):
        decrypt_payload("passphrase", payload.header_bytes, payload.ciphertext[:-1])


def test_nonce_generator_returns_fresh_96_bit_values() -> None:
    nonces = {generate_nonce() for _ in range(128)}
    assert all(len(nonce) == 12 for nonce in nonces)
    assert len(nonces) == 128
