"""Errors raised by image validation and sequential LSB processing."""


class SteganographyError(ValueError):
    """Base class for invalid steganography inputs."""


class UnsupportedImageError(SteganographyError):
    """The input is not a supported 8-bit truecolor RGB PNG."""


class InsufficientCapacityError(SteganographyError):
    """The image does not have enough RGB LSB slots for the payload."""


class InvalidPayloadError(SteganographyError):
    """The header or ciphertext length is invalid for sequential extraction."""
