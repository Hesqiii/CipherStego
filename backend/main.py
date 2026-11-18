from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api import evaluation, file_inspector, receiver, sender
from backend.middleware import RequestBodyLimitMiddleware
from backend.services.validation_service import MAX_REQUEST_BODY_BYTES

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(
    title="CipherStego Local API",
    description="Local-only PDF protection API using AES-GCM and Sequential or Key-Based Randomized LSB.",
    version="0.2.0",
)
app.add_middleware(RequestBodyLimitMiddleware, max_body_size=MAX_REQUEST_BODY_BYTES)

app.include_router(file_inspector.router)
app.include_router(sender.router)
app.include_router(receiver.router)
app.include_router(evaluation.router)


@app.get("/api/health", tags=["health"])
async def health_check() -> JSONResponse:
    return JSONResponse(
        {"status": "ok", "service": "cipherstego-local", "processing": "sender_receiver_available"}
    )


@app.exception_handler(RequestValidationError)
async def safe_request_validation_error(_, __) -> JSONResponse:
    """Avoid returning rejected input values, which may include a passphrase."""
    return JSONResponse({"detail": "Format request tidak valid."}, status_code=422)


if not FRONTEND_DIR.is_dir():
    raise RuntimeError(f"Frontend directory not found: {FRONTEND_DIR}")

# Mount only copied static assets. The legacy app directory also contains Python
# source files and must never be exposed as static content.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8765, reload=False)
