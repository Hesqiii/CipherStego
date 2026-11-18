"""Request and response models for the local sender and receiver API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EncodedFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255, strict=True)
    data: str = Field(min_length=4, strict=True)


class _OperationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passphrase: str = Field(min_length=12, max_length=1024, strict=True)
    mode: Literal["sequential", "randomized"] = "sequential"


class EmbedRequest(_OperationRequest):
    pdf: EncodedFile
    cover: EncodedFile


class ExtractRequest(_OperationRequest):
    stego: EncodedFile


class EmbedMetadata(BaseModel):
    mode: Literal["sequential", "randomized"]
    width: int
    height: int
    source_bytes: int
    ciphertext_bytes: int
    capacity_used_percent: float
    elapsed_ms: float
    permutation_ms: float | None = None
    embedding_ms: float | None = None
    source_sha256: str
    note: str


class EmbedResponse(BaseModel):
    filename: str
    png_base64: str
    metadata: EmbedMetadata


class ExtractMetadata(BaseModel):
    mode: Literal["sequential", "randomized"]
    width: int
    height: int
    pdf_bytes: int
    elapsed_ms: float
    permutation_ms: float | None = None
    extraction_ms: float | None = None
    sha256: str


class ExtractResponse(BaseModel):
    filename: str
    pdf_base64: str
    authenticated: Literal[True]
    metadata: ExtractMetadata
