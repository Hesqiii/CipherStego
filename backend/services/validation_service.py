"""Bounded input decoding and content validation for API operations."""

from __future__ import annotations

import base64
import binascii
import re
import struct
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from backend.schemas.operations import EncodedFile
from backend.core.steganography.image_io import load_rgb_png
from backend.core.steganography.exceptions import UnsupportedImageError

MAX_PDF_BYTES = 600 * 1024
MAX_COVER_BYTES = 16 * 1024 * 1024
MAX_IMAGE_PIXELS = 8_000_000
MAX_REQUEST_BODY_BYTES = 24 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class InputValidationError(ValueError):
    """An uploaded document violates the local processing limits or format."""


class InputTooLargeError(InputValidationError):
    """An encoded file exceeds the per-file limit."""


def decode_file_payload(file: EncodedFile, *, max_bytes: int, label: str) -> bytes:
    """Decode one strict Base64 file field while rejecting oversized input early."""
    if not isinstance(file, EncodedFile):
        raise InputValidationError(f"Field {label} tidak valid.")
    encoded = file.data
    if len(encoded) > 4 * ((max_bytes + 2) // 3):
        raise InputTooLargeError(f"Ukuran {label} melebihi batas yang diizinkan.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InputValidationError(f"Field {label} harus berisi Base64 yang valid.") from exc
    if not data:
        raise InputValidationError(f"Berkas {label} kosong.")
    if len(data) > max_bytes:
        raise InputTooLargeError(f"Ukuran {label} melebihi batas yang diizinkan.")
    return data


def validate_pdf_bytes(data: bytes) -> None:
    """Apply bounded PDF signature and EOF checks without trusting filename/MIME."""
    if not isinstance(data, bytes) or not data:
        raise InputValidationError("Berkas PDF kosong atau tidak valid.")
    if len(data) > MAX_PDF_BYTES:
        raise InputTooLargeError("Ukuran PDF melebihi batas demo 600 KiB.")
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-4096:]:
        raise InputValidationError("Konten atau signature PDF tidak valid.")


def _validate_png_dimensions(data: bytes) -> None:
    if len(data) < 29 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        raise UnsupportedImageError("Citra harus berupa PNG RGB 8-bit yang valid.")
    if struct.unpack(">I", data[8:12])[0] != 13:
        raise UnsupportedImageError("Header PNG tidak valid.")
    width, height = struct.unpack(">II", data[16:24])
    if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
        raise UnsupportedImageError("Dimensi citra melebihi batas pemrosesan lokal.")


@contextmanager
def staged_rgb_png(data: bytes) -> Iterator[tuple[Path, tuple[int, int]]]:
    """Temporarily stage and strictly validate PNG bytes for path-based LSB APIs."""
    if not isinstance(data, bytes) or not data:
        raise UnsupportedImageError("Citra PNG kosong atau tidak valid.")
    if len(data) > MAX_COVER_BYTES:
        raise InputTooLargeError("Ukuran PNG melebihi batas pemrosesan lokal 16 MiB.")
    _validate_png_dimensions(data)

    with TemporaryDirectory(prefix="cipherstego-input-") as temporary_directory:
        path = Path(temporary_directory) / "input.png"
        path.write_bytes(data)
        image = load_rgb_png(path)
        yield path, image.size


def validate_png_bytes(data: bytes) -> tuple[int, int]:
    """Validate cover/stego bytes through the Milestone 3 strict PNG loader."""
    with staged_rgb_png(data) as (_, dimensions):
        return dimensions


def safe_output_stem(filename: str, fallback: str) -> str:
    """Turn a client filename into a path-free display/download stem."""
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_-.")[:64]
    return safe or fallback
