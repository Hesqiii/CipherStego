"""Visual quality metrics defined by the CipherStego proposal."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from skimage.metrics import structural_similarity
import skimage


class InvalidEvaluationImageError(ValueError):
    """An image cannot be used in an RGB 8-bit evaluation pair."""


@dataclass(frozen=True)
class VisualMetrics:
    mse: float
    psnr_db: float
    ssim: float


def calculate_visual_metrics(cover: np.ndarray, stego: np.ndarray) -> VisualMetrics:
    """Calculate RGB-channel-averaged MSE and PSNR with MAX=255.

    Arrays must be decoded 8-bit RGB images in H×W×3 channel order. The mean
    covers every pixel and all three channels, matching proposal equation (2).
    """
    cover_array = _validate_rgb_array(cover, "cover")
    stego_array = _validate_rgb_array(stego, "stego")
    if cover_array.shape != stego_array.shape:
        raise InvalidEvaluationImageError(
            "Cover dan stego harus memiliki dimensi dan jumlah kanal RGB yang sama."
        )
    if min(cover_array.shape[:2]) < 11:
        raise InvalidEvaluationImageError(
            "SSIM dengan gaussian_weights=True dan sigma=1.5 memerlukan dimensi minimal 11×11 piksel."
        )

    delta = cover_array.astype(np.int16) - stego_array.astype(np.int16)
    mse = float(np.mean(delta.astype(np.float64) ** 2))
    psnr = math.inf if mse == 0.0 else 10.0 * math.log10((255.0**2) / mse)
    ssim = float(
        structural_similarity(
            cover_array,
            stego_array,
            data_range=255,
            channel_axis=-1,
            gaussian_weights=True,
            sigma=1.5,
            use_sample_covariance=False,
            K1=0.01,
            K2=0.03,
        )
    )
    return VisualMetrics(mse=mse, psnr_db=psnr, ssim=ssim)


def scikit_image_version() -> str:
    return skimage.__version__


def _validate_rgb_array(image: np.ndarray, label: str) -> np.ndarray:
    if not isinstance(image, np.ndarray):
        raise InvalidEvaluationImageError(f"Citra {label} harus berupa array NumPy.")
    if image.dtype != np.uint8:
        raise InvalidEvaluationImageError(f"Citra {label} harus menggunakan piksel uint8.")
    if image.ndim != 3 or image.shape[2] != 3:
        raise InvalidEvaluationImageError(f"Citra {label} harus memiliki representasi RGB H×W×3.")
    if image.shape[0] < 1 or image.shape[1] < 1:
        raise InvalidEvaluationImageError(f"Citra {label} tidak boleh kosong.")
    return image
