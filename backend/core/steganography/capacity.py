"""Capacity checks for the proposal's one-bit-per-RGB-channel format."""

from backend.core.crypto.constants import HEADER_BYTES
from backend.core.steganography.exceptions import InsufficientCapacityError


def _positive_dimension(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return value


def capacity_bits(width: int, height: int) -> int:
    """Return the available number of LSB slots in an RGB image."""
    width = _positive_dimension(width, "width")
    height = _positive_dimension(height, "height")
    return width * height * 3


def capacity_bytes(width: int, height: int) -> int:
    """Return complete bytes available across RGB LSB slots."""
    return capacity_bits(width, height) // 8


def validate_payload_capacity(width: int, height: int, ciphertext_length: int) -> None:
    """Validate 8 * (header + ciphertext) <= width * height * 3.

    ``ciphertext_length`` includes the AES-GCM authentication tag.
    """
    width = _positive_dimension(width, "width")
    height = _positive_dimension(height, "height")
    if (
        isinstance(ciphertext_length, bool)
        or not isinstance(ciphertext_length, int)
        or ciphertext_length < 0
    ):
        raise ValueError("ciphertext_length must be a non-negative integer.")

    required_bits = 8 * (HEADER_BYTES + ciphertext_length)
    available_bits = width * height * 3
    if required_bits > available_bits:
        available_payload_bytes = max(0, available_bits // 8 - HEADER_BYTES)
        raise InsufficientCapacityError(
            f"Payload requires {required_bits} RGB LSB bits, but the image has "
            f"{available_bits}; at most {available_payload_bytes} ciphertext bytes fit."
        )
