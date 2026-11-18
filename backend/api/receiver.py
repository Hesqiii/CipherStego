from fastapi import APIRouter, HTTPException, status

from backend.core.crypto.exceptions import AuthenticationError, CryptoInputError, PayloadFormatError
from backend.core.steganography.exceptions import (
    InsufficientCapacityError,
    InvalidPayloadError,
    UnsupportedImageError,
)
from backend.schemas.operations import ExtractRequest, ExtractResponse
from backend.services.receiver_service import recover_pdf
from backend.services.validation_service import (
    InputTooLargeError,
    InputValidationError,
    MAX_COVER_BYTES,
    decode_file_payload,
)

router = APIRouter(prefix="/api", tags=["receiver"])


def _run_extract(request: ExtractRequest) -> ExtractResponse:
    try:
        stego_data = decode_file_payload(request.stego, max_bytes=MAX_COVER_BYTES, label="stego-PNG")
        return recover_pdf(stego_data, request.passphrase, request.stego.name, request.mode)
    except InputTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except InputValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=400,
            detail="Passphrase salah atau payload telah berubah. PDF tidak dipulihkan.",
        ) from exc
    except UnsupportedImageError as exc:
        raise HTTPException(
            status_code=422,
            detail="Citra harus berupa PNG RGB 8-bit yang valid.",
        ) from exc
    except InsufficientCapacityError as exc:
        raise HTTPException(status_code=422, detail="Header atau payload tidak sesuai kapasitas citra.") from exc
    except (InvalidPayloadError, PayloadFormatError, CryptoInputError) as exc:
        raise HTTPException(status_code=422, detail="Header atau payload stego tidak valid.") from exc


@router.post("/receiver", response_model=ExtractResponse)
@router.post("/extract", response_model=ExtractResponse)
def receiver_endpoint(request: ExtractRequest) -> ExtractResponse:
    """Extract, authenticate, and return a PDF only after AES-GCM succeeds."""
    return _run_extract(request)
