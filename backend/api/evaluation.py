from fastapi import APIRouter, HTTPException

from backend.core.crypto.exceptions import (
    AuthenticationError,
    CryptoInputError,
    PayloadFormatError,
)
from backend.core.steganography.exceptions import (
    InsufficientCapacityError,
    InvalidPayloadError,
    UnsupportedImageError,
)
from backend.core.evaluation.image_metrics import InvalidEvaluationImageError
from backend.schemas.evaluation import EvaluationRequest, EvaluationResponse
from backend.services.evaluation_service import evaluate_sample
from backend.services.validation_service import (
    InputTooLargeError,
    InputValidationError,
    MAX_COVER_BYTES,
    MAX_PDF_BYTES,
    decode_file_payload,
)

router = APIRouter(prefix="/api", tags=["evaluation"])


def _run_evaluation(request: EvaluationRequest) -> EvaluationResponse:
    try:
        pdf_data = decode_file_payload(
            request.pdf, max_bytes=MAX_PDF_BYTES, label="PDF"
        )
        cover_data = decode_file_payload(
            request.cover, max_bytes=MAX_COVER_BYTES, label="PNG"
        )
        return evaluate_sample(
            pdf_data,
            cover_data,
            request.passphrase,
            request.pdf.name,
            request.mode,
        )
    except InputTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except InputValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except UnsupportedImageError as exc:
        raise HTTPException(
            status_code=422,
            detail="Citra harus PNG RGB 8-bit yang valid dan memenuhi batas pemrosesan.",
        ) from exc
    except InvalidEvaluationImageError as exc:
        raise HTTPException(
            status_code=422,
            detail="Ukuran citra minimal 11×11 diperlukan untuk konfigurasi SSIM.",
        ) from exc
    except InsufficientCapacityError as exc:
        raise HTTPException(
            status_code=422, detail="PDF dan header tidak muat pada citra PNG."
        ) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=400,
            detail="Autentikasi payload evaluasi gagal; PDF tidak dipulihkan.",
        ) from exc
    except (InvalidPayloadError, PayloadFormatError, CryptoInputError) as exc:
        raise HTTPException(status_code=422, detail="Input evaluasi tidak valid.") from exc


@router.post("/evaluation", response_model=EvaluationResponse)
@router.post("/evaluate", response_model=EvaluationResponse)
def evaluation_endpoint(request: EvaluationRequest) -> EvaluationResponse:
    """Run one actual embedding/extraction pass and calculate evaluation metrics."""
    return _run_evaluation(request)
