"""Sequential LSB embedding and extraction for fixed-header PNG payloads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter_ns

import numpy as np
from PIL import Image

from backend.core.crypto.constants import HEADER_BYTES
from backend.core.crypto.exceptions import PayloadFormatError
from backend.core.steganography.capacity import validate_payload_capacity
from backend.core.steganography.exceptions import InvalidPayloadError
from backend.core.steganography.header import parse_payload_header
from backend.core.steganography.image_io import load_rgb_png


@dataclass(frozen=True)
class ExtractedPayload:
    """Serialized header and ciphertext recovered from an unmodified stego PNG."""

    header: bytes
    ciphertext: bytes


def _header_bytes(header: bytes) -> bytes:
    if not isinstance(header, bytes) or len(header) != HEADER_BYTES:
        raise InvalidPayloadError(f"Header must be exactly {HEADER_BYTES} bytes.")
    try:
        parse_payload_header(header)
    except PayloadFormatError as exc:
        raise InvalidPayloadError(f"Invalid payload header: {exc}") from exc
    return header


def embed_sequential(
    cover_png: str | Path,
    header: bytes,
    ciphertext: bytes,
    *,
    timings: dict[str, float] | None = None,
) -> Image.Image:
    """Return a new RGB stego image containing header then ciphertext.

    Slots follow flattened row-major pixels and RGB channel order. Bytes are
    emitted MSB-first, one data bit per channel's least-significant bit.
    The supplied cover image/file is never modified.
    """
    load_started = perf_counter_ns() if timings is not None else None
    image = load_rgb_png(cover_png)
    if timings is not None:
        assert load_started is not None
        timings["image_load_ms"] = (perf_counter_ns() - load_started) / 1_000_000
    header = _header_bytes(header)
    if not isinstance(ciphertext, bytes):
        raise InvalidPayloadError("Ciphertext must be bytes.")
    parsed_header = parse_payload_header(header)
    if len(ciphertext) != parsed_header.ciphertext_length:
        raise InvalidPayloadError(
            "Ciphertext length does not match the length encoded in the header."
        )

    width, height = image.size
    validate_payload_capacity(width, height, len(ciphertext))
    payload = header + ciphertext
    bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8), bitorder="big")
    pixels = np.array(image, dtype=np.uint8, copy=True)
    slots = pixels.reshape(-1)
    operation_started = perf_counter_ns() if timings is not None else None
    slots[: bits.size] = (slots[: bits.size] & 0xFE) | bits
    if timings is not None:
        assert operation_started is not None
        timings["embedding_ms"] = (perf_counter_ns() - operation_started) / 1_000_000
    return Image.fromarray(pixels)


def extract_sequential(
    stego_png: str | Path,
    *,
    timings: dict[str, float] | None = None,
) -> ExtractedPayload:
    """Read the 32-byte header first, then exactly its declared ciphertext.

    This function does not derive keys, decrypt, or authenticate ciphertext.
    Those checks belong to the cryptographic receiver layer.
    """
    load_started = perf_counter_ns() if timings is not None else None
    image = load_rgb_png(stego_png)
    if timings is not None:
        assert load_started is not None
        timings["image_load_ms"] = (perf_counter_ns() - load_started) / 1_000_000
    pixels = np.asarray(image, dtype=np.uint8).reshape(-1)
    header_bit_count = HEADER_BYTES * 8
    if pixels.size < header_bit_count:
        raise InvalidPayloadError(
            f"Image has fewer than {header_bit_count} RGB LSB slots for a header."
        )

    operation_started = perf_counter_ns() if timings is not None else None
    header = np.packbits(pixels[:header_bit_count] & 1, bitorder="big").tobytes()
    try:
        parsed_header = parse_payload_header(header)
    except PayloadFormatError as exc:
        raise InvalidPayloadError(f"Embedded header is invalid: {exc}") from exc

    width, height = image.size
    validate_payload_capacity(width, height, parsed_header.ciphertext_length)
    total_bits = (HEADER_BYTES + parsed_header.ciphertext_length) * 8
    if pixels.size < total_bits:
        raise InvalidPayloadError("Image ended before the ciphertext declared by its header.")
    ciphertext = np.packbits(pixels[header_bit_count:total_bits] & 1, bitorder="big").tobytes()
    if timings is not None:
        assert operation_started is not None
        timings["extraction_ms"] = (perf_counter_ns() - operation_started) / 1_000_000
    return ExtractedPayload(header=header, ciphertext=ciphertext)
