"""PBKDF2-HMAC-SHA256 tests."""

import pytest

from backend.core.crypto.constants import PBKDF2_ITERATIONS, SALT_BYTES
from backend.core.crypto.exceptions import CryptoInputError
from backend.core.crypto.key_derivation import (
    derive_master_key,
    generate_salt,
    pbkdf2_hmac_sha256,
)


def test_pbkdf2_sha256_known_vector() -> None:
    # RFC 7914 Appendix B uses PBKDF2-HMAC-SHA256 for this one-iteration vector.
    result = pbkdf2_hmac_sha256(b"password", b"salt", iterations=1, length=32)
    assert result.hex() == "120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b"


def test_master_key_has_proposal_length_and_is_deterministic() -> None:
    salt = bytes(range(SALT_BYTES))
    first = derive_master_key("passphrase-å", salt)
    second = derive_master_key("passphrase-å", salt)

    assert len(first) == 32
    assert first == second
    assert PBKDF2_ITERATIONS == 600_000


def test_different_salts_produce_different_master_keys() -> None:
    assert derive_master_key("same passphrase", b"a" * 16) != derive_master_key(
        "same passphrase", b"b" * 16
    )


def test_passphrase_is_not_silently_normalized() -> None:
    composed = "é"
    decomposed = "e\u0301"
    assert derive_master_key(composed, b"s" * 16) != derive_master_key(decomposed, b"s" * 16)


def test_salt_generation_returns_random_salt_size() -> None:
    salts = {generate_salt() for _ in range(16)}
    assert all(len(salt) == SALT_BYTES for salt in salts)
    assert len(salts) == 16


@pytest.mark.parametrize(
    "password,salt,iterations,length",
    [
        (b"", b"salt", 1, 32),
        (b"pw", b"", 1, 32),
        (b"pw", b"salt", 0, 32),
        (b"pw", b"salt", 1, 0),
        (b"pw", b"salt", True, 32),
    ],
)
def test_invalid_pbkdf2_parameters_are_rejected(
    password: bytes, salt: bytes, iterations: int, length: int
) -> None:
    with pytest.raises(CryptoInputError):
        pbkdf2_hmac_sha256(password, salt, iterations, length)


def test_master_key_rejects_invalid_passphrase_or_salt() -> None:
    with pytest.raises(CryptoInputError):
        derive_master_key("", b"s" * 16)
    with pytest.raises(CryptoInputError):
        derive_master_key("passphrase", b"short")
