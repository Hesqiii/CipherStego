import numpy as np
import pytest

from backend.core.evaluation.chi_square import (
    _holm_adjust,
    _pool_pair_counts,
    _prefix_test,
    analyze_chi_square,
)


def test_pov_pooling_merges_adjacent_pairs_until_expected_frequency_exceeds_four() -> None:
    histogram = np.zeros(256, dtype=np.int64)
    histogram[0] = 8
    histogram[2] = 2

    assert _pool_pair_counts(histogram) == [(0, 128)]


def test_pov_statistic_and_both_tails_are_returned() -> None:
    samples = np.tile(np.array([0, 0, 1, 1, 2, 2, 3, 3], dtype=np.uint8), 20)

    result = _prefix_test(samples)

    assert result["status"] == "computed"
    assert result["statistic"] == pytest.approx(0.0)
    assert result["degrees_of_freedom"] == result["group_count"] - 1
    assert result["upper_tail_p_value"] == pytest.approx(1.0)
    assert result["underdispersion_p_value"] == pytest.approx(0.0)


def test_holm_adjustment_uses_fixed_family_size_and_is_monotone() -> None:
    rows = [
        {"underdispersion_p_value": value, "status": "computed"}
        for value in (0.01, 0.04, 0.03)
    ]
    _holm_adjust(rows)
    assert [row["holm_underdispersion_p_value"] for row in rows] == pytest.approx(
        [0.03, 0.06, 0.06]
    )


def test_prefixes_are_per_channel_ceil_counts_and_family_has_300_tests() -> None:
    image = np.zeros((11, 13, 3), dtype=np.uint8)

    result = analyze_chi_square(image)

    assert result["family_size"] == 300
    assert len(result["tests"]) == 300
    first = result["tests"][0]
    assert first["channel"] == "red"
    assert first["prefix_percent"] == 1
    assert first["sample_count"] == 2
    assert result["tests"][99]["prefix_percent"] == 100
    assert result["tests"][100]["channel"] == "green"
