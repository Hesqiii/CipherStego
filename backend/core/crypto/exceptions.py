"""Exceptions raised by the standalone cryptographic engine."""


class CryptoInputError(ValueError):
    """An input violates the documented cryptographic format or parameters."""


class PayloadFormatError(CryptoInputError):
    """A payload header or ciphertext length is malformed or inconsistent."""


class AuthenticationError(ValueError):
    """AES-GCM authentication failed; no plaintext is returned."""
