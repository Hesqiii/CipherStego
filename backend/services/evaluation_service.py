"""Run one real sender/receiver pass and evaluate its cover/stego pair."""

from __future__ import annotations

import base64
from time import perf_counter

import numpy as np

from backend.core.evaluation.chi_square import analyze_chi_square
from backend.core.evaluation.image_metrics import calculate_visual_metrics
from backend.core.evaluation.image_metrics import scikit_image_version
from backend.core.evaluation.rs_analysis import analyze_rs
from backend.core.crypto.constants import HEADER_BYTES
from backend.core.steganography.image_io import load_rgb_png
from backend.schemas.evaluation import (
    EvaluationMetrics,
    EvaluationResponse,
    EvaluationTimings,
    NumericMetric,
)
from backend.services.receiver_service import recover_pdf
from backend.services.sender_service import create_stego_png
from backend.services.validation_service import staged_rgb_png

def evaluate_sample(
    pdf_data: bytes,
    cover_data: bytes,
    passphrase: str,
    source_name: str,
    mode: str,
) -> EvaluationResponse:
    """Embed and extract once, then compare the actual cover/stego images."""
    started = perf_counter()
    embedded = create_stego_png(pdf_data, cover_data, passphrase, source_name, mode)
    stego_data = base64.b64decode(embedded.png_base64, validate=True)
    recovered = recover_pdf(stego_data, passphrase, embedded.filename, mode)
    recovered_pdf = base64.b64decode(recovered.pdf_base64, validate=True)

    with staged_rgb_png(cover_data) as (cover_path, _):
        cover_image = load_rgb_png(cover_path)
        cover_array = np.asarray(cover_image, dtype=np.uint8).copy()
    with staged_rgb_png(stego_data) as (stego_path, (width, height)):
        stego_image = load_rgb_png(stego_path)
        stego_array = np.asarray(stego_image, dtype=np.uint8).copy()

    visual = calculate_visual_metrics(cover_array, stego_array)
    chi_cover = analyze_chi_square(cover_array)
    chi_stego = analyze_chi_square(stego_array)
    actual_embedded_bits = 8 * (HEADER_BYTES + int(embedded.metadata.ciphertext_bytes))
    rs_result = analyze_rs(cover_array, stego_array, actual_embedded_bits)
    psnr_is_infinite = np.isinf(visual.psnr_db)
    return EvaluationResponse(
        mode=mode,
        width=width,
        height=height,
        source_bytes=len(pdf_data),
        source_sha256=embedded.metadata.source_sha256,
        recovered_sha256=recovered.metadata.sha256,
        recovery_matches=(recovered_pdf == pdf_data),
        metrics=EvaluationMetrics(
            mse=NumericMetric(value=visual.mse, unit="pixel_value^2"),
            psnr=NumericMetric(
                value=None if psnr_is_infinite else visual.psnr_db,
                unit="dB",
                status="infinite" if psnr_is_infinite else "finite",
            ),
            ssim=NumericMetric(value=visual.ssim, unit="index [-1, 1]"),
        ),
        timings=EvaluationTimings(
            evaluation_total_ms=round((perf_counter() - started) * 1000, 3),
            embedding_total_ms=embedded.metadata.elapsed_ms,
            extraction_total_ms=recovered.metadata.elapsed_ms,
            embedding_permutation_ms=embedded.metadata.permutation_ms,
            embedding_lsb_ms=embedded.metadata.embedding_ms,
            extraction_permutation_ms=recovered.metadata.permutation_ms,
            extraction_lsb_ms=recovered.metadata.extraction_ms,
        ),
        unavailable_metrics={},
        scikit_image_version=scikit_image_version(),
        chi_square={"cover": chi_cover, "stego": chi_stego},
        rs_analysis=rs_result,
    )
