"""RFC 5869 HKDF-SHA256 tests."""

import pytest

from backend.core.crypto.exceptions import CryptoInputError
from backend.core.crypto.hkdf import hkdf_sha256
from backend.core.crypto.key_derivation import derive_subkeys


def test_rfc5869_test_case_1_sha256() -> None:
    ikm = bytes.fromhex("0b" * 22)
    salt = bytes.fromhex("000102030405060708090a0b0c")
    info = bytes.fromhex("f0f1f2f3f4f5f6f7f8f9")
    expected_prk = "077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5"
    expected_okm = (
        "3cb25f25faacd57a90434f64d0362f2a"
        "2d2d0a90cf1a5a4c5db02d56ecc4c5bf"
        "34007208d5b887185865"
    )

    # RFC's OKM is checked directly; PRK is checked through the published vector
    # by using the extract operation with the same HMAC-SHA256 inputs.
    from hmac import new as hmac_new
    from hashlib import sha256

    assert hmac_new(salt, ikm, sha256).hexdigest() == expected_prk
    assert hkdf_sha256(ikm, salt, info, 42).hex() == expected_okm


def test_context_labels_derive_distinct_32_byte_keys() -> None:
    keys = derive_subkeys(b"m" * 32)
    assert len(keys.encryption_key) == 32
    assert len(keys.position_key) == 32
    assert keys.encryption_key != keys.position_key


def test_hkdf_accepts_rfc_zero_salt_policy() -> None:
    actual = hkdf_sha256(b"input key material", None, b"context", 32)
    expected = hkdf_sha256(b"input key material", b"\x00" * 32, b"context", 32)
    assert actual == expected


@pytest.mark.parametrize(
    "ikm,salt,info,length",
    [
        (b"", None, b"context", 32),
        (b"input", "not bytes", b"context", 32),
        (b"input", None, "not bytes", 32),
        (b"input", None, b"context", 0),
        (b"input", None, b"context", 8161),
        (b"input", None, b"context", True),
    ],
)
def test_invalid_hkdf_parameters_are_rejected(
    ikm: bytes, salt: bytes | None, info: bytes, length: int
) -> None:
    with pytest.raises(CryptoInputError):
        hkdf_sha256(ikm, salt, info, length)


def test_derived_key_fields_are_not_in_repr() -> None:
    keys = derive_subkeys(b"secret master key".ljust(32, b"."))
    assert keys.encryption_key.hex() not in repr(keys)
    assert keys.position_key.hex() not in repr(keys)
