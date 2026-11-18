"""SHA-256 test-comparison helpers."""

import hashlib

import pytest

from backend.core.crypto.hashing import (
    sha256_digest,
    sha256_file,
    sha256_file_hexdigest,
    sha256_hexdigest,
)


def test_sha256_known_vectors() -> None:
    assert sha256_hexdigest(b"") == hashlib.sha256(b"").hexdigest()
    assert sha256_hexdigest(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert sha256_digest(b"abc") == hashlib.sha256(b"abc").digest()
    assert len(sha256_digest(b"abc")) == 32


def test_equal_content_has_same_digest_and_different_content_does_not() -> None:
    assert sha256_digest(b"same") == sha256_digest(b"same")
    assert sha256_digest(b"same") != sha256_digest(b"different")


def test_streaming_file_hash_matches_in_memory_hash(tmp_path) -> None:
    data = bytes(range(256)) * 1024
    path = tmp_path / "payload.bin"
    path.write_bytes(data)

    assert sha256_file(path, chunk_size=333) == sha256_digest(data)
    assert sha256_file_hexdigest(path, chunk_size=333) == sha256_hexdigest(data)


def test_invalid_hash_inputs_are_rejected(tmp_path) -> None:
    with pytest.raises(TypeError):
        sha256_digest("not bytes")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        sha256_file(tmp_path / "unused", chunk_size=0)
