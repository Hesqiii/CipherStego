import math

import numpy as np
import pytest
from skimage.metrics import structural_similarity

from backend.core.evaluation.image_metrics import (
    InvalidEvaluationImageError,
    calculate_visual_metrics,
)


def test_identical_rgb_images_have_zero_mse_and_infinite_psnr() -> None:
    image = np.full((11, 12, 3), 127, dtype=np.uint8)

    result = calculate_visual_metrics(image, image.copy())

    assert result.mse == 0.0
    assert math.isinf(result.psnr_db)
    assert result.ssim == pytest.approx(1.0)


def test_known_channel_changes_match_rgb_mean_and_psnr_equations() -> None:
    cover = np.zeros((11, 12, 3), dtype=np.uint8)
    stego = cover.copy()
    stego[0, 0, 0] = 4
    stego[10, 11, 2] = 2

    result = calculate_visual_metrics(cover, stego)

    expected_mse = (4**2 + 2**2) / (11 * 12 * 3)
    expected_psnr = 10.0 * math.log10((255.0**2) / expected_mse)
    assert result.mse == pytest.approx(expected_mse, abs=1e-12)
    assert result.psnr_db == pytest.approx(expected_psnr, abs=1e-12)
    assert result.ssim == pytest.approx(
        structural_similarity(
            cover,
            stego,
            data_range=255,
            channel_axis=-1,
            gaussian_weights=True,
            sigma=1.5,
            use_sample_covariance=False,
            K1=0.01,
            K2=0.03,
        )
    )


def test_images_with_different_dimensions_are_rejected() -> None:
    with pytest.raises(InvalidEvaluationImageError, match="dimensi"):
        calculate_visual_metrics(
            np.zeros((11, 12, 3), dtype=np.uint8),
            np.zeros((12, 12, 3), dtype=np.uint8),
        )


@pytest.mark.parametrize(
    "image",
    [
        np.zeros((11, 11), dtype=np.uint8),
        np.zeros((11, 11, 1), dtype=np.uint8),
        np.zeros((11, 11, 4), dtype=np.uint8),
        np.zeros((0, 11, 3), dtype=np.uint8),
        np.zeros((11, 11, 3), dtype=np.float32),
        b"corrupt image",
    ],
)
def test_unsupported_or_empty_image_arrays_are_rejected(image) -> None:
    with pytest.raises(InvalidEvaluationImageError):
        calculate_visual_metrics(image, np.zeros((11, 11, 3), dtype=np.uint8))


def test_ssim_requires_default_seven_pixel_window() -> None:
    with pytest.raises(InvalidEvaluationImageError, match="11×11"):
        calculate_visual_metrics(
            np.zeros((10, 12, 3), dtype=np.uint8),
            np.zeros((10, 12, 3), dtype=np.uint8),
        )
