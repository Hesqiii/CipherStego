"""Compose PDF validation, authenticated encryption, and Sequential LSB."""

from __future__ import annotations

import base64
from io import BytesIO
from time import perf_counter

from backend.core.crypto.constants import GCM_TAG_BYTES
from backend.core.crypto.hashing import sha256_hexdigest
from backend.core.crypto.payload_crypto import encrypt_payload, encrypt_payload_with_keys
from backend.core.steganography.randomized_lsb import embed_randomized
from backend.core.steganography.capacity import validate_payload_capacity
from backend.core.steganography.sequential_lsb import embed_sequential
from backend.schemas.operations import EmbedResponse
from backend.services.validation_service import (
    InputValidationError,
    MAX_PDF_BYTES,
    safe_output_stem,
    staged_rgb_png,
    validate_pdf_bytes,
)


def create_stego_png(
    pdf_data: bytes,
    cover_data: bytes,
    passphrase: str,
    source_name: str,
    mode: str = "sequential",
) -> EmbedResponse:
    """Return a real stego-PNG response without persisting source/output files."""
    started = perf_counter()
    validate_pdf_bytes(pdf_data)
    if len(pdf_data) > MAX_PDF_BYTES:
        raise InputValidationError("Ukuran PDF melebihi batas demo 600 KiB.")

    with staged_rgb_png(cover_data) as (cover_path, (width, height)):
        expected_ciphertext_bytes = len(pdf_data) + GCM_TAG_BYTES
        validate_payload_capacity(width, height, expected_ciphertext_bytes)
        randomized_timings: dict[str, float] = {}

        if mode == "randomized":
            encrypted, keys = encrypt_payload_with_keys(passphrase, pdf_data)
            stego_image = embed_randomized(
                cover_path, encrypted.header_bytes, encrypted.ciphertext, keys.position_key,
                timings=randomized_timings,
            )
        elif mode == "sequential":
            encrypted = encrypt_payload(passphrase, pdf_data)
            stego_image = embed_sequential(cover_path, encrypted.header_bytes, encrypted.ciphertext)
        else:
            raise InputValidationError("Metode steganografi tidak dikenal.")
        png_output = BytesIO()
        stego_image.save(png_output, format="PNG", optimize=False)
        png_bytes = png_output.getvalue()

    capacity_used_percent = (
        8 * (len(encrypted.header_bytes) + len(encrypted.ciphertext))
        / (width * height * 3)
        * 100
    )
    filename = f"stego_{safe_output_stem(source_name, 'document')}.png"
    return EmbedResponse(
        filename=filename,
        png_base64=base64.b64encode(png_bytes).decode("ascii"),
        metadata={
            "mode": mode,
            "width": width,
            "height": height,
            "source_bytes": len(pdf_data),
            "ciphertext_bytes": len(encrypted.ciphertext),
            "capacity_used_percent": round(capacity_used_percent, 4),
            "elapsed_ms": round((perf_counter() - started) * 1000, 3),
            "permutation_ms": round(randomized_timings["permutation_ms"], 3) if mode == "randomized" else None,
            "embedding_ms": round(randomized_timings["embedding_ms"], 3) if mode == "randomized" else None,
            "source_sha256": sha256_hexdigest(pdf_data),
            "note": "SHA-256 adalah fingerprint pembanding, bukan autentikasi pengirim.",
        },
    )
