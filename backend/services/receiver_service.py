"""Compose Sequential LSB extraction, AES-GCM authentication, and PDF return."""

from __future__ import annotations

import base64
from time import perf_counter

from backend.core.crypto.hashing import sha256_hexdigest
from backend.core.crypto.key_derivation import derive_keys
from backend.core.crypto.payload_crypto import decrypt_payload, decrypt_payload_with_keys
from backend.core.steganography.header import parse_payload_header
from backend.core.steganography.randomized_lsb import (
    extract_randomized,
    extract_randomized_header,
)
from backend.core.steganography.sequential_lsb import extract_sequential
from backend.schemas.operations import ExtractResponse
from backend.services.validation_service import safe_output_stem, staged_rgb_png, validate_pdf_bytes


def recover_pdf(
    stego_data: bytes,
    passphrase: str,
    stego_name: str,
    mode: str = "sequential",
) -> ExtractResponse:
    """Authenticate and recover a PDF in memory; return bytes only after GCM passes."""
    started = perf_counter()
    randomized_timings: dict[str, float] = {}
    with staged_rgb_png(stego_data) as (stego_path, (width, height)):
        if mode == "randomized":
            header_bytes = extract_randomized_header(stego_path)
            parsed_header = parse_payload_header(header_bytes)
            keys = derive_keys(passphrase, parsed_header.salt)
            extracted = extract_randomized(
                stego_path, keys.position_key, timings=randomized_timings
            )
            if extracted.header != header_bytes:
                raise ValueError("Header changed during extraction.")
            pdf_data = decrypt_payload_with_keys(header_bytes, extracted.ciphertext, keys)
        elif mode == "sequential":
            extracted = extract_sequential(stego_path)
            # AES-GCM checks the exact serialized 32-byte header as AAD.
            pdf_data = decrypt_payload(passphrase, extracted.header, extracted.ciphertext)
        else:
            raise ValueError("Unknown steganography mode.")

    validate_pdf_bytes(pdf_data)
    filename = f"recovered_{safe_output_stem(stego_name, 'document')}.pdf"
    return ExtractResponse(
        filename=filename,
        pdf_base64=base64.b64encode(pdf_data).decode("ascii"),
        authenticated=True,
        metadata={
            "mode": mode,
            "width": width,
            "height": height,
            "pdf_bytes": len(pdf_data),
            "elapsed_ms": round((perf_counter() - started) * 1000, 3),
            "permutation_ms": round(randomized_timings["permutation_ms"], 3) if mode == "randomized" else None,
            "extraction_ms": round(randomized_timings["extraction_ms"], 3) if mode == "randomized" else None,
            "sha256": sha256_hexdigest(pdf_data),
        },
    )
