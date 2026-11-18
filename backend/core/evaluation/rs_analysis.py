"""Per-channel RS steganalysis with explicit initial-bias correction."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from backend.core.evaluation.image_metrics import _validate_rgb_array

CHANNELS = ("red", "green", "blue")
_EPSILON = 1e-12


def _flip(image: np.ndarray, positive: bool) -> np.ndarray:
    values = image.astype(np.int16, copy=True)
    even = (values & 1) == 0
    if positive:
        values[even] += 1
        values[~even] -= 1
    else:
        values[even] -= 1
        values[~even] += 1
    return values


def _group_scores(channel: np.ndarray) -> tuple[float, float, int]:
    height = channel.shape[0] - channel.shape[0] % 2
    width = channel.shape[1] - channel.shape[1] % 2
    if height == 0 or width == 0:
        return 0.0, 0.0, 0
    blocks = channel[:height, :width].reshape(height // 2, 2, width // 2, 2)
    groups = blocks.transpose(0, 2, 1, 3).reshape(-1, 4)
    # M=[1 0; 0 1], -M=[-1 0; 0 -1]. Flattening is TL, TR, BL, BR.
    values = groups.astype(np.int32)
    base = np.abs(np.diff(values, axis=1)).sum(axis=1)
    positive = values + np.asarray((1, 0, 0, 1), dtype=np.int32)
    negative = values + np.asarray((-1, 0, 0, -1), dtype=np.int32)
    positive_delta = np.abs(np.diff(positive, axis=1)).sum(axis=1) - base
    negative_delta = np.abs(np.diff(negative, axis=1)).sum(axis=1) - base
    positive_score = (np.count_nonzero(positive_delta > 0) - np.count_nonzero(positive_delta < 0)) / len(groups)
    negative_score = (np.count_nonzero(negative_delta > 0) - np.count_nonzero(negative_delta < 0)) / len(groups)
    n = len(groups)
    return positive_score, negative_score, n


def _root_estimate(d0: float, d1: float, d_minus0: float, d_minus1: float) -> dict[str, Any]:
    # The four measured RS curves yield the quadratic in the published estimator.
    a = 2.0 * (d1 + d0)
    b = d_minus0 - d_minus1 - d1 - 3.0 * d0
    c = d0 - d_minus0
    if abs(a) <= _EPSILON:
        if abs(b) <= _EPSILON:
            return {"status": "unreliable", "reason": "Persamaan estimator RS degenerat.", "p": None, "root": None}
        roots = [-c / b]
    else:
        discriminant = b * b - 4.0 * a * c
        if discriminant < -_EPSILON:
            return {"status": "unreliable", "reason": "Persamaan estimator RS tidak memiliki akar real.", "p": None, "root": None}
        discriminant = max(0.0, discriminant)
        square_root = math.sqrt(discriminant)
        roots = [(-b + square_root) / (2.0 * a), (-b - square_root) / (2.0 * a)]
    root = min(roots, key=abs)
    denominator = root - 0.5
    if abs(denominator) <= _EPSILON:
        return {"status": "unreliable", "reason": "Akar RS menghasilkan penyebut nol.", "p": None, "root": root}
    p = root / denominator
    if not math.isfinite(p) or not 0.0 <= p <= 1.0:
        return {"status": "unreliable", "reason": "Estimasi RS berada di luar rentang [0, 1].", "p": None, "root": root}
    return {"status": "computed", "reason": None, "p": p, "root": root}


def _estimate_channel(channel: np.ndarray) -> dict[str, Any]:
    original_m, original_minus_m, groups = _group_scores(channel)
    flipped_m, flipped_minus_m, _ = _group_scores(_flip(channel, positive=True))
    estimate = _root_estimate(original_m, flipped_m, original_minus_m, flipped_minus_m)
    return {**estimate, "groups": groups, "d_m_original": original_m, "d_minus_m_original": original_minus_m}


def analyze_rs(cover: np.ndarray, stego: np.ndarray, actual_embedded_bits: int) -> dict[str, Any]:
    """Estimate per-channel payload fraction and correct stego estimates by cover bias."""
    cover_array = _validate_rgb_array(cover, "cover")
    stego_array = _validate_rgb_array(stego, "stego")
    if cover_array.shape != stego_array.shape:
        raise ValueError("Cover dan stego harus memiliki dimensi RGB yang sama.")
    if not isinstance(actual_embedded_bits, int) or actual_embedded_bits < 0:
        raise ValueError("actual_embedded_bits harus bilangan bulat nonnegatif.")
    height, width, _ = cover_array.shape
    channels: dict[str, Any] = {}
    total_corrected_bits = 0.0
    all_reliable = True
    for index, name in enumerate(CHANNELS):
        baseline = _estimate_channel(cover_array[:, :, index])
        observed = _estimate_channel(stego_array[:, :, index])
        corrected = None
        corrected_bits = None
        status = "unreliable"
        reason = observed["reason"] or baseline["reason"]
        if observed["p"] is not None and baseline["p"] is not None:
            denominator = 1.0 - baseline["p"]
            if abs(denominator) > _EPSILON:
                corrected = (observed["p"] - baseline["p"]) / denominator
                if math.isfinite(corrected) and 0.0 <= corrected <= 1.0:
                    corrected_bits = corrected * width * height
                    status, reason = "computed", None
                else:
                    corrected = None
                    reason = "Estimasi setelah koreksi bias berada di luar rentang [0, 1]."
            else:
                reason = "Koreksi bias RS tidak stabil karena bias cover mendekati satu."
        if corrected_bits is None:
            all_reliable = False
        else:
            total_corrected_bits += corrected_bits
        channels[name] = {
            "status": status,
            "reason": reason,
            "groups": observed["groups"],
            "cover_initial_bias_fraction": baseline["p"],
            "stego_raw_fraction": observed["p"],
            "corrected_fraction": corrected,
            "corrected_estimated_bits": corrected_bits,
        }
    estimated_total = total_corrected_bits if all_reliable else None
    error_bits = abs(estimated_total - actual_embedded_bits) if estimated_total is not None else None
    relative_error = (error_bits / actual_embedded_bits) if error_bits is not None and actual_embedded_bits else None
    return {
        "status": "computed" if all_reliable else "partially_unreliable",
        "method": "RS 2x2 disjoint groups; initial-cover-bias correction per RGB channel",
        "actual_embedded_bits": actual_embedded_bits,
        "estimated_total_bits": estimated_total,
        "absolute_error_bits": error_bits,
        "relative_error": relative_error,
        "channels": channels,
        "limitation": "Estimasi RS bergantung pada asumsi model embedding dan sensitivitas terhadap tekstur/noise cover.",
    }
