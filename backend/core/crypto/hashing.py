"""SHA-256 helpers for test comparison, not payload authentication."""

from __future__ import annotations

import hashlib
from pathlib import Path

BytesLike = bytes | bytearray | memoryview


def sha256_digest(data: BytesLike) -> bytes:
    """Return the raw 32-byte SHA-256 digest of in-memory data."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("SHA-256 input must be bytes-like.")
    return hashlib.sha256(data).digest()


def sha256_hexdigest(data: BytesLike) -> str:
    """Return the lowercase hexadecimal SHA-256 digest of in-memory data."""
    return sha256_digest(data).hex()


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> bytes:
    """Hash a file incrementally and return the raw 32-byte digest."""
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or chunk_size < 1:
        raise ValueError("chunk_size must be a positive integer.")

    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(chunk_size), b""):
            digest.update(chunk)
    return digest.digest()


def sha256_file_hexdigest(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file incrementally and return its lowercase hexadecimal digest."""
    return sha256_file(path, chunk_size).hex()
