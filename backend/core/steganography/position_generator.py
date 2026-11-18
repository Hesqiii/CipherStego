"""Deterministic HMAC-SHA256 stream and unbiased integer selection."""

from __future__ import annotations

import hashlib
import hmac

from backend.core.crypto.constants import HKDF_KEY_BYTES

COUNTER_BYTES = 8
COUNTER_MAX = (1 << (COUNTER_BYTES * 8)) - 1
UINT64_RANGE = 1 << 64


class PositionGeneratorError(ValueError):
    """The key or request cannot be represented by the position generator."""


class CounterOverflowError(PositionGeneratorError):
    """The 64-bit big-endian HMAC counter has no unused value remaining."""


class HMACCounterStream:
    """Buffered HMAC bytes keyed by K_pos with an unsigned 64-bit counter.

    Block ``i`` is HMAC-SHA256(K_pos, I2OSP(i, 8)), where I2OSP uses
    unsigned big-endian encoding and the first counter is zero. Consumers read
    each digest from its first byte onward; exhausted bytes trigger the next
    counter block. The counter is never allowed to wrap.
    """

    def __init__(self, key: bytes) -> None:
        if not isinstance(key, bytes) or len(key) != HKDF_KEY_BYTES:
            raise PositionGeneratorError(
                f"K_pos must be exactly {HKDF_KEY_BYTES} bytes."
            )
        self._key = key
        self._counter = 0
        self._buffer = b""
        self._offset = 0

    def _refill(self) -> None:
        if self._counter > COUNTER_MAX:
            raise CounterOverflowError("HMAC counter exceeds its unsigned 64-bit range.")
        counter_bytes = self._counter.to_bytes(COUNTER_BYTES, "big", signed=False)
        self._buffer = hmac.digest(self._key, counter_bytes, "sha256")
        self._counter += 1
        self._offset = 0

    def read(self, length: int) -> bytes:
        """Read exactly ``length`` bytes, retaining unused digest bytes."""
        if isinstance(length, bool) or not isinstance(length, int) or length < 0:
            raise PositionGeneratorError("Byte count must be a non-negative integer.")
        if length == 0:
            return b""

        output = bytearray(length)
        written = 0
        while written < length:
            if self._offset >= len(self._buffer):
                self._refill()
            amount = min(length - written, len(self._buffer) - self._offset)
            output[written : written + amount] = self._buffer[
                self._offset : self._offset + amount
            ]
            written += amount
            self._offset += amount
        return bytes(output)

    def next_u64(self) -> int:
        """Read one unsigned 64-bit word in big-endian stream order."""
        return int.from_bytes(self.read(8), "big", signed=False)

    def randbelow(self, bound: int) -> int:
        """Return a uniform value in ``[0, bound)`` using rejection sampling."""
        if isinstance(bound, bool) or not isinstance(bound, int):
            raise PositionGeneratorError("Range bound must be an integer.")
        if not 1 <= bound <= UINT64_RANGE:
            raise PositionGeneratorError("Range bound must be between 1 and 2^64.")

        limit = UINT64_RANGE - (UINT64_RANGE % bound)
        while True:
            value = self.next_u64()
            if value < limit:
                return value % bound
