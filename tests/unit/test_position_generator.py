"""Known-answer and boundary tests for the HMAC position stream."""

from __future__ import annotations

import hashlib
import hmac

import pytest

from backend.core.steganography.position_generator import (
    COUNTER_MAX,
    UINT64_RANGE,
    CounterOverflowError,
    HMACCounterStream,
    PositionGeneratorError,
)

KEY = bytes(range(32))
COUNTER_ZERO_DIGEST = bytes.fromhex(
    "9f0cd9b94097fe4929918d2b8942b344"
    "39574261a35dc50163f06c67d4e48899"
)
COUNTER_ONE_DIGEST = bytes.fromhex(
    "c432e059c378eef7fe2f1181a4050836"
    "f51e0856fd74937be81784fa0efa7a1c"
)


def test_hmac_counter_blocks_match_known_answers() -> None:
    stream = HMACCounterStream(KEY)

    assert stream.read(32) == COUNTER_ZERO_DIGEST
    assert stream.read(32) == COUNTER_ONE_DIGEST


def test_hmac_counter_encoding_is_unsigned_64_bit_big_endian() -> None:
    expected = hmac.new(KEY, bytes(8), hashlib.sha256).digest()
    assert expected == COUNTER_ZERO_DIGEST
    assert HMACCounterStream(KEY).read(32) == expected


def test_buffered_reads_do_not_discard_unused_digest_bytes() -> None:
    stream = HMACCounterStream(KEY)
    expected = COUNTER_ZERO_DIGEST + COUNTER_ONE_DIGEST

    actual = stream.read(7) + stream.read(1) + stream.read(24) + stream.read(32)

    assert actual == expected


def test_u64_words_are_read_big_endian_from_the_digest_buffer() -> None:
    stream = HMACCounterStream(KEY)

    assert stream.next_u64() == 0x9F0CD9B94097FE49
    assert stream.next_u64() == 0x29918D2B8942B344


def test_stream_is_deterministic_for_same_key_and_changes_for_another_key() -> None:
    assert HMACCounterStream(KEY).read(64) == HMACCounterStream(KEY).read(64)
    assert HMACCounterStream(KEY).read(32) != HMACCounterStream(b"x" * 32).read(32)


def test_counter_overflow_fails_without_wrapping() -> None:
    stream = HMACCounterStream(KEY)
    stream._counter = COUNTER_MAX
    expected_last_block = hmac.new(
        KEY, COUNTER_MAX.to_bytes(8, "big"), hashlib.sha256
    ).digest()

    assert stream.read(32) == expected_last_block
    with pytest.raises(CounterOverflowError, match="unsigned 64-bit"):
        stream.read(1)


class _ScriptedWords:
    def __init__(self, *values: int) -> None:
        self.values = iter(values)
        self.calls = 0

    def next_u64(self) -> int:
        self.calls += 1
        return next(self.values)


def test_randbelow_rejects_out_of_range_u64_then_uses_next_word(monkeypatch) -> None:
    bound = 10
    limit = UINT64_RANGE - (UINT64_RANGE % bound)
    scripted = _ScriptedWords(UINT64_RANGE - 1, limit - 1)
    stream = HMACCounterStream(KEY)
    monkeypatch.setattr(stream, "next_u64", scripted.next_u64)

    assert stream.randbelow(bound) == (limit - 1) % bound
    assert scripted.calls == 2


def test_randbelow_power_of_two_accepts_full_domain_and_range_is_valid() -> None:
    scripted = _ScriptedWords(UINT64_RANGE - 1)
    stream = HMACCounterStream(KEY)
    stream.next_u64 = scripted.next_u64

    assert stream.randbelow(8) == 7
    assert scripted.calls == 1


def test_rejection_threshold_makes_each_residue_have_equal_preimage_count() -> None:
    for bound in (3, 10, 255, 1024):
        limit = UINT64_RANGE - (UINT64_RANGE % bound)
        assert limit % bound == 0
        assert (UINT64_RANGE - limit) < bound


@pytest.mark.parametrize("bound", [0, -1, UINT64_RANGE + 1, True, 1.5])
def test_randbelow_rejects_invalid_bounds(bound) -> None:
    with pytest.raises(PositionGeneratorError):
        HMACCounterStream(KEY).randbelow(bound)


@pytest.mark.parametrize("key", [b"", b"short", "not bytes"])
def test_position_stream_rejects_keys_that_are_not_32_bytes(key) -> None:
    with pytest.raises(PositionGeneratorError, match="K_pos"):
        HMACCounterStream(key)
