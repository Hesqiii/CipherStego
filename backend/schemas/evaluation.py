"""Typed request and response contracts for single-sample evaluation."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.operations import EncodedFile


class EvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pdf: EncodedFile
    cover: EncodedFile
    passphrase: str = Field(min_length=12, max_length=1024, strict=True)
    mode: Literal["sequential", "randomized"] = "sequential"


class NumericMetric(BaseModel):
    value: float | None
    unit: str
    status: Literal["finite", "infinite", "not_estimable"] = "finite"
    reason: str | None = None


class EvaluationMetrics(BaseModel):
    mse: NumericMetric
    psnr: NumericMetric
    ssim: NumericMetric


class EvaluationTimings(BaseModel):
    evaluation_total_ms: float
    embedding_total_ms: float
    extraction_total_ms: float
    embedding_permutation_ms: float | None = None
    embedding_lsb_ms: float | None = None
    extraction_permutation_ms: float | None = None
    extraction_lsb_ms: float | None = None


class ChiSquareTest(BaseModel):
    status: Literal["computed", "not_estimable"]
    reason: str | None
    statistic: float | None
    degrees_of_freedom: int | None
    upper_tail_p_value: float | None
    underdispersion_p_value: float | None
    group_count: int
    channel: Literal["red", "green", "blue"]
    prefix_percent: int
    sample_count: int
    possible_embedding_indicator: bool | None
    holm_underdispersion_p_value: float | None = None


class ChiSquareImageResult(BaseModel):
    status: Literal["computed", "not_estimable"]
    family_size: int
    alpha: float
    possible_embedding_indicator: bool | None
    interpretation: str
    tests: list[ChiSquareTest]


class ChiSquareEvaluation(BaseModel):
    cover: ChiSquareImageResult
    stego: ChiSquareImageResult


class RSChannelEstimate(BaseModel):
    status: Literal["computed", "unreliable"]
    reason: str | None
    groups: int
    cover_initial_bias_fraction: float | None
    stego_raw_fraction: float | None
    corrected_fraction: float | None
    corrected_estimated_bits: float | None


class RSEvaluation(BaseModel):
    status: Literal["computed", "partially_unreliable"]
    method: str
    actual_embedded_bits: int
    estimated_total_bits: float | None
    absolute_error_bits: float | None
    relative_error: float | None
    channels: dict[Literal["red", "green", "blue"], RSChannelEstimate]
    limitation: str


class EvaluationResponse(BaseModel):
    mode: Literal["sequential", "randomized"]
    width: int
    height: int
    source_bytes: int
    source_sha256: str
    recovered_sha256: str
    recovery_matches: bool
    metrics: EvaluationMetrics
    timings: EvaluationTimings
    unavailable_metrics: dict[str, str]
    scikit_image_version: str
    chi_square: ChiSquareEvaluation
    rs_analysis: RSEvaluation
