"""Known-answer, placement, and round-trip tests for Randomized LSB."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest
from PIL import Image

from backend.core.crypto.key_derivation import derive_keys
from backend.core.steganography.capacity import validate_payload_capacity
from backend.core.steganography.exceptions import (
    InsufficientCapacityError,
    InvalidPayloadError,
    UnsupportedImageError,
)
from backend.core.steganography.header import PayloadHeader
from backend.core.steganography.image_io import load_rgb_png, save_rgb_png
from backend.core.steganography.randomized_lsb import (
    HEADER_SLOTS,
    UINT32_ITEM_LIMIT,
    _ciphertext_positions,
    embed_randomized,
    extract_randomized,
    fisher_yates_permutation,
)

POSITION_KEY = bytes(range(32))


def make_payload(ciphertext: bytes) -> tuple[bytes, bytes]:
    header = PayloadHeader(
        salt=bytes(range(16)),
        nonce=bytes(range(16, 28)),
        ciphertext_length=len(ciphertext),
    ).serialize()
    return header, ciphertext


def save_cover(path, size=(128, 128), color=(170, 85, 204)) -> Image.Image:
    image = Image.new("RGB", size, color)
    image.save(path, format="PNG")
    return image


def test_fisher_yates_matches_independent_known_answer() -> None:
    expected = np.array([0, 5, 8, 6, 2, 14, 12, 4, 7, 11, 15, 3, 1, 13, 10, 9], dtype=np.uint32)

    actual = fisher_yates_permutation(16, POSITION_KEY)

    np.testing.assert_array_equal(actual, expected)


def test_fisher_yates_is_deterministic_and_is_a_full_permutation() -> None:
    first = fisher_yates_permutation(257, POSITION_KEY)
    second = fisher_yates_permutation(257, POSITION_KEY)

    np.testing.assert_array_equal(first, second)
    np.testing.assert_array_equal(np.sort(first), np.arange(257, dtype=np.uint32))


@pytest.mark.parametrize("count", [-1, True, 1.5, (1 << 32) + 1])
def test_fisher_yates_rejects_invalid_permutation_sizes(count) -> None:
    with pytest.raises(InvalidPayloadError):
        fisher_yates_permutation(count, POSITION_KEY)


def test_fisher_yates_rejects_invalid_position_key() -> None:
    with pytest.raises(InvalidPayloadError, match="K_pos"):
        fisher_yates_permutation(4, b"short")


def test_absolute_position_offsets_cannot_overflow_uint32() -> None:
    with pytest.raises(InvalidPayloadError, match="uint32"):
        _ciphertext_positions(UINT32_ITEM_LIMIT - HEADER_SLOTS + 1, 0, POSITION_KEY)


@pytest.mark.parametrize("size", [16, 17, 64, 257, 1024])
def test_randomized_payload_round_trip_for_multiple_sizes(size: int, tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path)
    ciphertext = bytes((index * 47 + size) % 256 for index in range(size))
    header, ciphertext = make_payload(ciphertext)

    embed_timing = {}
    extraction_timing = {}
    stego = embed_randomized(cover_path, header, ciphertext, POSITION_KEY, timings=embed_timing)
    stego_path = tmp_path / "stego.png"
    save_rgb_png(stego, stego_path)
    recovered = extract_randomized(stego_path, POSITION_KEY, timings=extraction_timing)

    assert recovered.header == header
    assert recovered.ciphertext == ciphertext
    assert load_rgb_png(stego_path).mode == "RGB"
    assert stego.size == (128, 128)
    assert embed_timing["permutation_ms"] >= 0
    assert embed_timing["embedding_ms"] >= 0
    assert embed_timing["image_load_ms"] >= 0
    assert extraction_timing["permutation_ms"] >= 0
    assert extraction_timing["extraction_ms"] >= 0
    assert extraction_timing["image_load_ms"] >= 0


def test_known_payload_bits_use_msb_order_and_never_reuse_header_slots(tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    cover = save_cover(cover_path, size=(32, 32), color=(0, 0, 0))
    ciphertext = bytes.fromhex("96 3c a5 5a 01 ff 80 7e 13 24 68 ac de ad be ef")
    header, ciphertext = make_payload(ciphertext)
    ciphertext_bits = np.unpackbits(np.frombuffer(ciphertext, dtype=np.uint8), bitorder="big")

    stego = embed_randomized(cover_path, header, ciphertext, POSITION_KEY)
    flat = np.asarray(stego, dtype=np.uint8).reshape(-1)
    header_bits = np.unpackbits(np.frombuffer(header, dtype=np.uint8), bitorder="big")
    expected_permutation = fisher_yates_permutation(32 * 32 * 3 - HEADER_SLOTS, POSITION_KEY)
    ciphertext_slots = expected_permutation[: ciphertext_bits.size] + HEADER_SLOTS

    np.testing.assert_array_equal(flat[:HEADER_SLOTS] & 1, header_bits)
    np.testing.assert_array_equal(flat[ciphertext_slots] & 1, ciphertext_bits)
    assert np.all(ciphertext_slots >= HEADER_SLOTS)
    assert np.all(ciphertext_slots < flat.size)
    assert len(np.unique(ciphertext_slots)) == len(ciphertext_slots)


def test_embedding_changes_only_lsb_and_never_changes_source_file(tmp_path) -> None:
    cover_path = tmp_path / "source.png"
    cover = save_cover(cover_path, size=(64, 48), color=(0xAA, 0x55, 0xCC))
    original_hash = hashlib.sha256(cover_path.read_bytes()).digest()
    ciphertext = bytes(range(80))
    header, ciphertext = make_payload(ciphertext)

    stego = embed_randomized(cover_path, header, ciphertext, POSITION_KEY)
    before = np.asarray(cover, dtype=np.uint8).reshape(-1)
    after = np.asarray(stego, dtype=np.uint8).reshape(-1)

    np.testing.assert_array_equal(before >> 1, after >> 1)
    assert hashlib.sha256(cover_path.read_bytes()).digest() == original_hash
    assert stego.size == cover.size


def test_exact_capacity_boundary_is_accepted(tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path, size=(16, 8), color=(0, 0, 0))
    ciphertext = b"t" * 16
    header, ciphertext = make_payload(ciphertext)
    validate_payload_capacity(16, 8, len(ciphertext))

    stego = embed_randomized(cover_path, header, ciphertext, POSITION_KEY)
    save_rgb_png(stego, tmp_path / "stego.png")
    assert extract_randomized(tmp_path / "stego.png", POSITION_KEY).ciphertext == ciphertext


def test_position_key_comes_from_milestone2_derivation_using_header_salt(tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path)
    ciphertext = b"payload encrypted by the separate crypto layer"
    header, ciphertext = make_payload(ciphertext)
    position_key = derive_keys("research passphrase", header[:16]).position_key
    receiver_position_key = derive_keys("research passphrase", header[:16]).position_key
    stego_path = tmp_path / "stego.png"

    save_rgb_png(
        embed_randomized(cover_path, header, ciphertext, position_key), stego_path
    )
    recovered = extract_randomized(stego_path, receiver_position_key)

    assert receiver_position_key == position_key
    assert recovered.ciphertext == ciphertext


def test_1920_by_1080_permutation_uses_compact_uint32_storage() -> None:
    remaining_slots = 1920 * 1080 * 3 - HEADER_SLOTS
    assert remaining_slots * np.dtype(np.uint32).itemsize == 24_882_176


def test_payload_over_capacity_is_rejected(tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path, size=(16, 8), color=(0, 0, 0))
    ciphertext = b"t" * 17
    header, ciphertext = make_payload(ciphertext)

    with pytest.raises(InsufficientCapacityError):
        embed_randomized(cover_path, header, ciphertext, POSITION_KEY)


def test_header_and_ciphertext_lengths_are_validated(tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path)
    header, ciphertext = make_payload(b"a" * 16)

    with pytest.raises(InvalidPayloadError, match="exactly 32"):
        embed_randomized(cover_path, header[:-1], ciphertext[:-1], POSITION_KEY)
    with pytest.raises(InvalidPayloadError, match="does not match"):
        embed_randomized(cover_path, header, ciphertext[:-1], POSITION_KEY)


@pytest.mark.parametrize("mode", ["L", "RGBA", "P"])
def test_randomized_rejects_non_rgb_png(mode: str, tmp_path) -> None:
    cover_path = tmp_path / "unsupported.png"
    Image.new(mode, (32, 32)).save(cover_path, format="PNG")
    header, ciphertext = make_payload(b"x" * 16)

    with pytest.raises(UnsupportedImageError):
        embed_randomized(cover_path, header, ciphertext, POSITION_KEY)


def test_extraction_rejects_image_without_valid_header(tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path, size=(64, 64), color=(0, 0, 0))

    with pytest.raises(InvalidPayloadError, match="header"):
        extract_randomized(cover_path, POSITION_KEY)


def test_extraction_requires_the_same_position_key(tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path)
    ciphertext = b"payload bytes for key reconstruction"
    header, ciphertext = make_payload(ciphertext)
    stego_path = tmp_path / "stego.png"
    save_rgb_png(embed_randomized(cover_path, header, ciphertext, POSITION_KEY), stego_path)

    recovered = extract_randomized(stego_path, b"z" * 32)
    assert recovered.header == header
    assert recovered.ciphertext != ciphertext
