"""Upload size limit middleware.

Rejects POST/PUT/PATCH requests whose Content-Length exceeds the
configured limit (`settings.MAX_UPLOAD_SIZE_BYTES`).

- Missing Content-Length header -> 411 Length Required.
- Invalid Content-Length value -> 400 Bad Request.
- Payload too large -> 413 Request Entity Too Large.
"""

from __future__ import annotations

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = structlog.get_logger()


class LimitUploadSizeMiddleware(BaseHTTPMiddleware):
    """Limits upload size at the middleware level."""

    def __init__(self, app: ASGIApp, *, max_upload_size: int) -> None:
        super().__init__(app)
        self.max_upload_size = max_upload_size

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in ("POST", "PUT", "PATCH"):
            raw = request.headers.get("content-length")
            if raw is None:
                logger.warning(
                    "upload_rejected_missing_content_length",
                    path=request.url.path,
                )
                return Response(status_code=411)

            try:
                content_length = int(raw)
            except ValueError:
                logger.warning(
                    "upload_rejected_invalid_content_length",
                    path=request.url.path,
                    raw=raw,
                )
                return Response(status_code=400)

            if content_length > self.max_upload_size:
                logger.warning(
                    "upload_rejected_too_large",
                    path=request.url.path,
                    content_length=content_length,
                    max_allowed=self.max_upload_size,
                )
                return Response(status_code=413)

        return await call_next(request)
