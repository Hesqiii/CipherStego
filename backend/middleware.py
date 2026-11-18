"""Small ASGI guards for local API request bodies."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RequestBodyLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests whose declared body exceeds the local JSON API limit."""
    def __init__(self, app, max_body_size: int):
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next):
        raw_content_length = request.headers.get("content-length")
        if raw_content_length is not None:
            try:
                content_length = int(raw_content_length)
            except ValueError:
                return JSONResponse({"detail": "Content-Length tidak valid."}, status_code=400)
            if content_length < 0 or content_length > self.max_body_size:
                return JSONResponse(
                    {
                        "detail": (
                            "Request body melebihi batas "
                            f"{self.max_body_size // (1024 * 1024)} MiB."
                        )
                    },
                    status_code=413,
                )
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > self.max_body_size:
                return JSONResponse(
                    {
                        "detail": (
                            "Request body melebihi batas "
                            f"{self.max_body_size // (1024 * 1024)} MiB."
                        )
                    },
                    status_code=413,
                )
        request._body = bytes(body)
        return await call_next(request)
