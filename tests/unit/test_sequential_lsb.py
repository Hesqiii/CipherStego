"""Known-pattern and round-trip tests for Sequential LSB."""

from __future__ import annotations

import hashlib

import numpy as np
import pytest
from PIL import Image

from backend.core.crypto.constants import HEADER_BYTES
from backend.core.steganography.capacity import capacity_bits, validate_payload_capacity
from backend.core.steganography.exceptions import (
    InsufficientCapacityError,
    InvalidPayloadError,
    UnsupportedImageError,
)
from backend.core.steganography.header import PayloadHeader
from backend.core.steganography.image_io import load_rgb_png, save_rgb_png
from backend.core.steganography.sequential_lsb import (
    embed_sequential,
    extract_sequential,
)


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


def extract_saved(stego: Image.Image, path):
    save_rgb_png(stego, path)
    return extract_sequential(path)


def test_small_payload_round_trip_from_png_path(tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path)
    ciphertext = b"\x00\xffCipherStego\x80\x01\x7f"
    header, ciphertext = make_payload(ciphertext)

    embed_timing = {}
    extraction_timing = {}
    stego = embed_sequential(cover_path, header, ciphertext, timings=embed_timing)
    stego_path = tmp_path / "stego.png"
    save_rgb_png(stego, stego_path)
    recovered = extract_sequential(stego_path, timings=extraction_timing)

    assert recovered.header == header
    assert recovered.ciphertext == ciphertext
    assert embed_timing["embedding_ms"] >= 0
    assert embed_timing["image_load_ms"] >= 0
    assert extraction_timing["extraction_ms"] >= 0
    assert extraction_timing["image_load_ms"] >= 0


@pytest.mark.parametrize("size", [16, 17, 64, 128, 1024, 4096])
def test_binary_random_payloads_round_trip(size: int, tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path, size=(256, 256))
    ciphertext = np.random.default_rng(size).bytes(size)
    header, ciphertext = make_payload(ciphertext)

    stego = embed_sequential(cover_path, header, ciphertext)
    recovered = extract_saved(stego, tmp_path / "stego.png")

    assert recovered == type(recovered)(header=header, ciphertext=ciphertext)


def test_known_pattern_uses_msb_first_and_rgb_row_major_slots(tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path, size=(16, 8), color=(0xAA, 0x55, 0xCC))
    ciphertext = bytes.fromhex("80 01 96 69 3c a5 5a c3 00 ff 10 20 40 08 04 02")
    header, ciphertext = make_payload(ciphertext)
    expected = np.unpackbits(np.frombuffer(header + ciphertext, dtype=np.uint8), bitorder="big")

    stego = embed_sequential(cover_path, header, ciphertext)
    actual = np.asarray(stego).reshape(-1)[: expected.size] & 1

    np.testing.assert_array_equal(actual, expected)
    # The first three slots are pixel (0,0), channels R/G/B; the fourth is (1,0,R).
    pixels = np.asarray(stego)
    np.testing.assert_array_equal(pixels[0, 0, :] & 1, expected[:3])
    assert pixels[0, 1, 0] & 1 == expected[3]


def test_embedding_changes_only_used_lsbs_and_keeps_dimensions(tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    original = save_cover(cover_path, size=(40, 30), color=(0xAA, 0x55, 0xCC))
    ciphertext = bytes(range(64))
    header, ciphertext = make_payload(ciphertext)

    stego = embed_sequential(cover_path, header, ciphertext)
    before = np.asarray(original)
    after = np.asarray(stego)
    used_bits = (HEADER_BYTES + len(ciphertext)) * 8

    assert stego.size == original.size
    np.testing.assert_array_equal(before.reshape(-1)[used_bits:], after.reshape(-1)[used_bits:])
    np.testing.assert_array_equal(before.reshape(-1)[:used_bits] >> 1, after.reshape(-1)[:used_bits] >> 1)


def test_capacity_exact_boundary_is_accepted(tmp_path) -> None:
    # 16 * 8 * 3 = 384 slots = 8 * (32-byte header + 16-byte GCM tag).
    assert capacity_bits(16, 8) == 384
    validate_payload_capacity(16, 8, ciphertext_length=16)
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path, size=(16, 8), color=(0, 0, 0))
    ciphertext = b"t" * 16
    header, ciphertext = make_payload(ciphertext)

    recovered = extract_saved(
        embed_sequential(cover_path, header, ciphertext), tmp_path / "stego.png"
    )
    assert recovered.ciphertext == ciphertext


def test_payload_over_capacity_is_rejected_before_embedding(tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path, size=(16, 8), color=(0, 0, 0))
    ciphertext = b"t" * 17
    header, ciphertext = make_payload(ciphertext)

    with pytest.raises(InsufficientCapacityError, match="requires 392"):
        embed_sequential(cover_path, header, ciphertext)


@pytest.mark.parametrize("mode", ["L", "RGBA", "P"])
def test_loader_rejects_non_rgb_png_modes(mode: str, tmp_path) -> None:
    path = tmp_path / "unsupported.png"
    image = Image.new(mode, (16, 8))
    image.save(path, format="PNG")

    with pytest.raises(UnsupportedImageError):
        load_rgb_png(path)


def test_loader_rejects_jpeg_even_when_extension_is_png(tmp_path) -> None:
    path = tmp_path / "jpeg-disguised.png"
    Image.new("RGB", (16, 8), (10, 20, 30)).save(path, format="JPEG")

    with pytest.raises(UnsupportedImageError):
        load_rgb_png(path)


def test_embedding_rejects_non_png_origin_image(tmp_path) -> None:
    path = tmp_path / "cover.jpg"
    Image.new("RGB", (32, 32)).save(path, format="JPEG")
    ciphertext = b"x" * 16
    header, ciphertext = make_payload(ciphertext)
    with pytest.raises(UnsupportedImageError):
        embed_sequential(path, header, ciphertext)


def test_unmodified_stego_extraction_is_byte_identical(tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path)
    ciphertext = bytes(range(16, 80))
    header, ciphertext = make_payload(ciphertext)
    stego = embed_sequential(cover_path, header, ciphertext)
    stego_path = tmp_path / "stego.png"
    save_rgb_png(stego, stego_path)

    recovered = extract_sequential(stego_path)

    assert recovered.header == header
    assert recovered.ciphertext == ciphertext


def test_source_png_file_is_not_modified(tmp_path) -> None:
    source = tmp_path / "source.png"
    save_cover(source)
    original_hash = hashlib.sha256(source.read_bytes()).digest()
    ciphertext = b"z" * 16
    header, ciphertext = make_payload(ciphertext)

    embed_sequential(source, header, ciphertext)

    assert hashlib.sha256(source.read_bytes()).digest() == original_hash


def test_bad_header_ciphertext_length_is_rejected(tmp_path) -> None:
    cover_path = tmp_path / "cover.png"
    save_cover(cover_path, size=(64, 64))
    header, ciphertext = make_payload(b"a" * 16)

    with pytest.raises(InvalidPayloadError, match="does not match"):
        embed_sequential(cover_path, header, ciphertext + b"b")


def test_extraction_rejects_random_image_without_valid_header(tmp_path) -> None:
    image_path = tmp_path / "random.png"
    save_cover(image_path, size=(64, 64), color=(0, 0, 0))
    with pytest.raises(InvalidPayloadError, match="header"):
        extract_sequential(image_path)

