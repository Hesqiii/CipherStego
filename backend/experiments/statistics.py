"""Paired statistics at condition level, never at timing-repetition level."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np
from scipy.stats import rankdata, wilcoxon


def holm_adjust(p_values: Sequence[float | None]) -> list[float | None]:
    valid = [(float(value), index) for index, value in enumerate(p_values) if value is not None and math.isfinite(value)]
    result: list[float | None] = [None] * len(p_values)
    if not valid:
        return result
    valid.sort(key=lambda entry: (entry[0], entry[1]))
    running = 0.0
    count = len(valid)
    for rank, (p_value, original_index) in enumerate(valid):
        running = max(running, min(1.0, p_value * (count - rank)))
        result[original_index] = running
    return result


def paired_wilcoxon_summary(
    sequential: Sequence[float], randomized: Sequence[float], *, seed: int = 20261118, bootstrap_samples: int = 20_000
) -> dict[str, float | int | str | None]:
    """Summarize paired conditions; bootstrap CI is over conditions, not repeats."""
    left = np.asarray(sequential, dtype=np.float64)
    right = np.asarray(randomized, dtype=np.float64)
    if left.ndim != 1 or right.shape != left.shape or left.size < 2:
        raise ValueError("Wilcoxon requires equal paired vectors with at least two conditions.")
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("Statistical inputs must be finite.")
    differences = right - left
    nonzero = differences != 0
    if not nonzero.any():
        return {
            "status": "no_nonzero_differences",
            "n_pairs": int(left.size),
            "median_paired_difference": 0.0,
            "mean_paired_difference": 0.0,
            "rank_biserial_effect": 0.0,
            "ci95_mean_difference_low": 0.0,
            "ci95_mean_difference_high": 0.0,
            "p_value": 1.0,
        }
    try:
        test = wilcoxon(left, right, alternative="two-sided", zero_method="wilcox", method="auto").pvalue
    except ValueError:
        test = 1.0
    ranks = rankdata(np.abs(differences[nonzero]), method="average")
    signed_rank_sum = float(np.sum(np.sign(differences[nonzero]) * ranks))
    rank_total = float(np.sum(ranks))
    rng = np.random.default_rng(seed)
    bootstrap_indices = rng.integers(0, differences.size, size=(bootstrap_samples, differences.size))
    bootstrap_means = differences[bootstrap_indices].mean(axis=1)
    low, high = np.quantile(bootstrap_means, [0.025, 0.975])
    return {
        "status": "computed",
        "n_pairs": int(left.size),
        "median_paired_difference": float(np.median(differences)),
        "mean_paired_difference": float(np.mean(differences)),
        "rank_biserial_effect": signed_rank_sum / rank_total if rank_total else 0.0,
        "ci95_mean_difference_low": float(low),
        "ci95_mean_difference_high": float(high),
        "p_value": float(test),
    }
