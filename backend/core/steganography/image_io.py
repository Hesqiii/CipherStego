"""Strict PNG I/O helpers; incompatible images are rejected, never converted."""

from __future__ import annotations

from pathlib import Path
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError

from backend.core.steganography.exceptions import UnsupportedImageError

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_IHDR_SIZE = 13
PNG_RGB_COLOR_TYPE = 2
PNG_BIT_DEPTH = 8


def _read_rgb_ihdr(source: BinaryIO, path: Path) -> None:
    header = source.read(29)
    if (
        len(header) != 29
        or header[:8] != PNG_SIGNATURE
        or int.from_bytes(header[8:12], "big") != PNG_IHDR_SIZE
        or header[12:16] != b"IHDR"
    ):
        raise UnsupportedImageError(f"{path} is not a valid PNG with an IHDR header.")
    if header[24] != PNG_BIT_DEPTH or header[25] != PNG_RGB_COLOR_TYPE:
        raise UnsupportedImageError(
            f"{path} must be an 8-bit truecolor RGB PNG (color type 2)."
        )


def validate_rgb_image(image: Image.Image) -> None:
    """Validate an already-decoded image without changing its mode or pixels."""
    if not isinstance(image, Image.Image):
        raise UnsupportedImageError("Image input must be a Pillow image or PNG path.")
    if image.mode != "RGB":
        raise UnsupportedImageError(f"Image mode must be RGB; received {image.mode}.")
    if image.format not in (None, "PNG"):
        raise UnsupportedImageError(f"Image format must be PNG; received {image.format}.")
    if image.info.get("transparency") is not None:
        raise UnsupportedImageError("PNG transparency is not supported; use RGB without alpha.")
    if image.width <= 0 or image.height <= 0:
        raise UnsupportedImageError("Image dimensions must be positive.")


def load_rgb_png(path: str | Path) -> Image.Image:
    """Open an 8-bit RGB PNG after checking its actual file signature and IHDR."""
    source_path = Path(path)
    try:
        with source_path.open("rb") as source:
            _read_rgb_ihdr(source, source_path)
        with Image.open(source_path) as probe:
            if probe.format != "PNG":
                raise UnsupportedImageError(f"{source_path} is not a PNG image.")
            probe.verify()
        with Image.open(source_path) as decoded:
            decoded.load()
            validate_rgb_image(decoded)
            return decoded.copy()
    except UnsupportedImageError:
        raise
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise UnsupportedImageError(f"Could not read a valid RGB PNG from {source_path}.") from exc


def save_rgb_png(image: Image.Image, path: str | Path) -> None:
    """Save an RGB image as PNG without converting or changing its pixels."""
    validate_rgb_image(image)
    try:
        image.save(Path(path), format="PNG")
    except OSError as exc:
        raise UnsupportedImageError(f"Could not save PNG image to {path}.") from exc
