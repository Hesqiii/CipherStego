from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/api", tags=["file inspection"])


@router.post("/inspect", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def inspect_file() -> None:
    """Placeholder for future local PDF/PNG inspection."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="File inspection belum tersedia pada milestone ini.",
    )
