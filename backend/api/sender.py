from fastapi import APIRouter, HTTPException, status

from backend.core.crypto.exceptions import CryptoInputError, PayloadFormatError
from backend.core.steganography.exceptions import (
    InsufficientCapacityError,
    InvalidPayloadError,
    UnsupportedImageError,
)
from backend.schemas.operations import EmbedRequest, EmbedResponse
from backend.services.sender_service import create_stego_png
from backend.services.validation_service import (
    InputTooLargeError,
    InputValidationError,
    MAX_COVER_BYTES,
    MAX_PDF_BYTES,
    decode_file_payload,
)

router = APIRouter(prefix="/api", tags=["sender"])


def _not_implemented() -> None:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Simulasi perubahan payload belum tersedia pada milestone ini.",
    )


def _run_embed(request: EmbedRequest) -> EmbedResponse:
    try:
        pdf_data = decode_file_payload(request.pdf, max_bytes=MAX_PDF_BYTES, label="PDF")
        cover_data = decode_file_payload(request.cover, max_bytes=MAX_COVER_BYTES, label="PNG")
        return create_stego_png(
            pdf_data, cover_data, request.passphrase, request.pdf.name, request.mode
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
    except InsufficientCapacityError as exc:
        raise HTTPException(status_code=422, detail="PDF dan header tidak muat pada citra PNG.") from exc
    except (InvalidPayloadError, PayloadFormatError, CryptoInputError) as exc:
        raise HTTPException(status_code=422, detail="Input pengamanan tidak valid.") from exc


@router.post("/sender", response_model=EmbedResponse)
@router.post("/embed", response_model=EmbedResponse)
def sender_endpoint(request: EmbedRequest) -> EmbedResponse:
    """Encrypt a PDF and embed it in a PNG using the requested LSB mode."""
    return _run_embed(request)


@router.post("/tamper", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def existing_frontend_tamper_placeholder() -> None:
    _not_implemented()
