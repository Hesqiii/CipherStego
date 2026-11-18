"""Key-Based Randomized LSB embedding and extraction for RGB PNG files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import numpy as np
from PIL import Image

from backend.core.crypto.constants import HEADER_BYTES
from backend.core.crypto.exceptions import PayloadFormatError
from backend.core.steganography.capacity import validate_payload_capacity
from backend.core.steganography.exceptions import InvalidPayloadError
from backend.core.steganography.header import PayloadHeader, parse_payload_header
from backend.core.steganography.image_io import load_rgb_png
from backend.core.steganography.position_generator import (
    HMACCounterStream,
    PositionGeneratorError,
)

HEADER_SLOTS = HEADER_BYTES * 8
UINT32_ITEM_LIMIT = 1 << 32


@dataclass(frozen=True)
class ExtractedPayload:
    """Serialized header and ciphertext recovered from a stego PNG."""

    header: bytes
    ciphertext: bytes


def _validated_header(header: bytes) -> PayloadHeader:
    if not isinstance(header, bytes) or len(header) != HEADER_BYTES:
        raise InvalidPayloadError(f"Header must be exactly {HEADER_BYTES} bytes.")
    try:
        return parse_payload_header(header)
    except PayloadFormatError as exc:
        raise InvalidPayloadError(f"Invalid payload header: {exc}") from exc


def fisher_yates_permutation(count: int, position_key: bytes) -> np.ndarray:
    """Return a full uint32 Fisher–Yates permutation for ``range(count)``.

    The HMAC stream is deterministic for a given K_pos. The compact uint32
    representation uses four bytes per entry and preserves the full shuffle.
    ``count`` cannot exceed the number of values representable by uint32.
    """
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise InvalidPayloadError("Permutation size must be a non-negative integer.")
    if count > UINT32_ITEM_LIMIT:
        raise InvalidPayloadError("Permutation size exceeds the uint32 position range.")

    try:
        stream = HMACCounterStream(position_key)
    except PositionGeneratorError as exc:
        raise InvalidPayloadError(str(exc)) from exc

    positions = np.arange(count, dtype=np.uint32)
    for i in range(count - 1, 0, -1):
        j = stream.randbelow(i + 1)
        positions[i], positions[j] = positions[j], positions[i]
    return positions


def _ciphertext_positions(
    available_slots: int,
    ciphertext_bit_count: int,
    position_key: bytes,
) -> np.ndarray:
    if available_slots + HEADER_SLOTS > UINT32_ITEM_LIMIT:
        raise InvalidPayloadError("Image exceeds the uint32 randomized-position range.")
    if ciphertext_bit_count > available_slots:
        raise InvalidPayloadError("Ciphertext exceeds available randomized positions.")
    permutation = fisher_yates_permutation(available_slots, position_key)
    # Shift the prefix in place; allocating a second uint32 index array would
    # nearly double permutation memory for full-size research images.
    positions = permutation[:ciphertext_bit_count]
    positions += np.uint32(HEADER_SLOTS)
    return positions


def embed_randomized(
    cover_png: str | Path,
    header: bytes,
    ciphertext: bytes,
    position_key: bytes,
    *,
    timings: dict[str, float] | None = None,
) -> Image.Image:
    """Return a new RGB image with a sequential header and randomized payload.

    The first 256 flattened RGB LSB slots hold the 32-byte header in MSB-first
    order. A full Fisher–Yates permutation is generated over the remaining
    slots; ciphertext bits use its prefix in MSB-first order. The cover file is
    never modified and no encryption or decryption occurs here.
    """
    image_load_started = perf_counter() if timings is not None else None
    image = load_rgb_png(cover_png)
    if timings is not None:
        assert image_load_started is not None
        timings["image_load_ms"] = (perf_counter() - image_load_started) * 1000
    parsed_header = _validated_header(header)
    if not isinstance(ciphertext, bytes):
        raise InvalidPayloadError("Ciphertext must be bytes.")
    if len(ciphertext) != parsed_header.ciphertext_length:
        raise InvalidPayloadError(
            "Ciphertext length does not match the length encoded in the header."
        )

    width, height = image.size
    validate_payload_capacity(width, height, len(ciphertext))
    pixels = np.array(image, dtype=np.uint8, copy=True)
    slots = pixels.reshape(-1)
    ciphertext_bits = np.unpackbits(
        np.frombuffer(ciphertext, dtype=np.uint8), bitorder="big"
    )
    available_slots = slots.size - HEADER_SLOTS
    permutation_started = perf_counter()
    try:
        positions = _ciphertext_positions(
            available_slots, ciphertext_bits.size, position_key
        )
    except PositionGeneratorError as exc:
        raise InvalidPayloadError(str(exc)) from exc
    if timings is not None:
        timings["permutation_ms"] = (perf_counter() - permutation_started) * 1000

    embedding_started = perf_counter()
    header_bits = np.unpackbits(np.frombuffer(header, dtype=np.uint8), bitorder="big")
    slots[:HEADER_SLOTS] = (slots[:HEADER_SLOTS] & 0xFE) | header_bits
    selected_slots = slots[positions]
    selected_slots &= np.uint8(0xFE)
    selected_slots |= ciphertext_bits
    slots[positions] = selected_slots
    if timings is not None:
        timings["embedding_ms"] = (perf_counter() - embedding_started) * 1000
    return Image.fromarray(pixels)


def extract_randomized(
    stego_png: str | Path,
    position_key: bytes,
    *,
    timings: dict[str, float] | None = None,
) -> ExtractedPayload:
    """Read the sequential header, then recover ciphertext by the same shuffle."""
    image_load_started = perf_counter() if timings is not None else None
    image = load_rgb_png(stego_png)
    if timings is not None:
        assert image_load_started is not None
        timings["image_load_ms"] = (perf_counter() - image_load_started) * 1000
    pixels = np.asarray(image, dtype=np.uint8).reshape(-1)
    header = _extract_header(pixels)

    try:
        parsed_header = parse_payload_header(header)
    except PayloadFormatError as exc:
        raise InvalidPayloadError(f"Embedded header is invalid: {exc}") from exc

    width, height = image.size
    validate_payload_capacity(width, height, parsed_header.ciphertext_length)
    ciphertext_bit_count = parsed_header.ciphertext_length * 8
    available_slots = pixels.size - HEADER_SLOTS
    permutation_started = perf_counter()
    try:
        positions = _ciphertext_positions(
            available_slots, ciphertext_bit_count, position_key
        )
    except PositionGeneratorError as exc:
        raise InvalidPayloadError(str(exc)) from exc
    if timings is not None:
        timings["permutation_ms"] = (perf_counter() - permutation_started) * 1000
    extraction_started = perf_counter()
    ciphertext_lsb = pixels[positions]
    ciphertext_lsb &= np.uint8(1)
    ciphertext = np.packbits(ciphertext_lsb, bitorder="big").tobytes()
    if timings is not None:
        timings["extraction_ms"] = (perf_counter() - extraction_started) * 1000
    return ExtractedPayload(header=header, ciphertext=ciphertext)


def extract_randomized_header(stego_png: str | Path) -> bytes:
    """Read and validate only the sequential header before deriving K_pos."""
    image = load_rgb_png(stego_png)
    pixels = np.asarray(image, dtype=np.uint8).reshape(-1)
    return _extract_header(pixels)


def _extract_header(pixels: np.ndarray) -> bytes:
    if pixels.size < HEADER_SLOTS:
        raise InvalidPayloadError(
            f"Image has fewer than {HEADER_SLOTS} RGB LSB slots for a header."
        )
    header = np.packbits(pixels[:HEADER_SLOTS] & 1, bitorder="big").tobytes()
    try:
        parse_payload_header(header)
    except PayloadFormatError as exc:
        raise InvalidPayloadError(f"Embedded header is invalid: {exc}") from exc
    return header
