"""Progressive pair-of-values chi-square analysis for RGB images."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from scipy.stats import chi2

from backend.core.evaluation.image_metrics import _validate_rgb_array

PREFIX_PERCENTAGES = tuple(range(1, 101))
CHANNELS = ("red", "green", "blue")
ALPHA = 0.05


def _pool_pair_counts(histogram: np.ndarray) -> list[tuple[int, int]]:
    """Return [start, stop) ranges of adjacent PoV pairs with E > 4."""
    pair_counts = [int(histogram[i] + histogram[i + 1]) for i in range(0, 256, 2)]
    groups: list[tuple[int, int]] = []
    start = 0
    pooled = 0
    for index, count in enumerate(pair_counts):
        pooled += count
        if pooled / 2.0 > 4:
            groups.append((start, index + 1))
            start = index + 1
            pooled = 0
    if start < len(pair_counts):
        if groups:
            previous_start, _ = groups[-1]
            groups[-1] = (previous_start, len(pair_counts))
        else:
            groups.append((start, len(pair_counts)))
    return groups


def _prefix_test_histogram(histogram: np.ndarray) -> dict[str, Any]:
    groups = _pool_pair_counts(histogram)
    if len(groups) < 2:
        return {
            "status": "not_estimable",
            "reason": "Kurang dari dua kelompok PoV memenuhi frekuensi harapan > 4.",
            "statistic": None,
            "degrees_of_freedom": None,
            "upper_tail_p_value": None,
            "underdispersion_p_value": None,
            "group_count": len(groups),
        }

    statistic = 0.0
    for pair_start, pair_stop in groups:
        values_start = pair_start * 2
        values_stop = pair_stop * 2
        observed = int(histogram[values_start:values_stop:2].sum())
        expected = int(histogram[values_start:values_stop].sum()) / 2.0
        if expected <= 0:
            return {
                "status": "not_estimable",
                "reason": "Frekuensi harapan PoV bernilai nol.",
                "statistic": None,
                "degrees_of_freedom": None,
                "upper_tail_p_value": None,
                "underdispersion_p_value": None,
                "group_count": len(groups),
            }
        statistic += ((observed - expected) ** 2) / expected

    degrees = len(groups) - 1
    return {
        "status": "computed",
        "reason": None,
        "statistic": float(statistic),
        "degrees_of_freedom": degrees,
        # The upper-tail test is retained as conventional PoV evidence. The
        # lower tail separately records the direction expected from LSB embedding.
        "upper_tail_p_value": float(chi2.sf(statistic, degrees)),
        "underdispersion_p_value": float(chi2.cdf(statistic, degrees)),
        "group_count": len(groups),
    }


def _prefix_test(samples: np.ndarray) -> dict[str, Any]:
    histogram = np.bincount(samples, minlength=256).astype(np.int64, copy=False)
    return _prefix_test_histogram(histogram)


def _holm_adjust(rows: list[dict[str, Any]]) -> None:
    """Apply step-down Holm to the fixed family of 3 channels × 100 prefixes."""
    m = len(rows)
    values = [
        (row["underdispersion_p_value"] if row["underdispersion_p_value"] is not None else 1.0, i)
        for i, row in enumerate(rows)
    ]
    values.sort(key=lambda item: (item[0], item[1]))
    adjusted_running = 0.0
    for rank, (p_value, original_index) in enumerate(values):
        adjusted_running = max(adjusted_running, min(1.0, p_value * (m - rank)))
        rows[original_index]["holm_underdispersion_p_value"] = adjusted_running
        if rows[original_index]["status"] != "computed":
            rows[original_index]["holm_underdispersion_p_value"] = None


def analyze_chi_square(image: np.ndarray) -> dict[str, Any]:
    """Test PoV parity in each row-major RGB channel prefix (1%…100%)."""
    array = _validate_rgb_array(image, "evaluation")
    height, width, _ = array.shape
    total = height * width
    rows: list[dict[str, Any]] = []
    for channel_index, channel_name in enumerate(CHANNELS):
        values = array[:, :, channel_index].reshape(-1, order="C")
        histogram = np.zeros(256, dtype=np.int64)
        previous_count = 0
        for percentage in PREFIX_PERCENTAGES:
            count = math.ceil(total * percentage / 100)
            if count > previous_count:
                histogram += np.bincount(
                    values[previous_count:count], minlength=256
                )
                previous_count = count
            result = _prefix_test_histogram(histogram)
            result.update(
                channel=channel_name,
                prefix_percent=percentage,
                sample_count=count,
                possible_embedding_indicator=None,
            )
            rows.append(result)
    _holm_adjust(rows)
    for row in rows:
        adjusted = row["holm_underdispersion_p_value"]
        row["possible_embedding_indicator"] = (
            adjusted <= ALPHA if adjusted is not None else None
        )

    valid = [row for row in rows if row["holm_underdispersion_p_value"] is not None]
    indicator = None if not valid else any(
        row["holm_underdispersion_p_value"] <= ALPHA for row in valid
    )
    return {
        "status": "computed" if valid else "not_estimable",
        "family_size": len(rows),
        "alpha": ALPHA,
        "possible_embedding_indicator": indicator,
        "interpretation": (
            "Indikator prefiks bersifat eksploratif; terutama untuk Randomized LSB, "
            "hasil prefiks bukan uji deteksi seluruh citra."
        ),
        "tests": rows,
    }
