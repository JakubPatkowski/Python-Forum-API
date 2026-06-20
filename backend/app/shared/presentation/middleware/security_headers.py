"""Security headers middleware.

Adds security headers to every HTTP response:
- X-Frame-Options: DENY -- click-jacking protection
- X-Content-Type-Options: nosniff -- blocks MIME-sniffing
- Strict-Transport-Security -- enforces HTTPS
- Referrer-Policy: no-referrer -- limits referer leakage
- Content-Security-Policy: default-src 'self' -- CSP baseline
  (disabled for /docs, /openapi.json and /metrics, because Swagger UI
  requires inline script/style)
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Paths where the CSP must be relaxed (Swagger UI).
_CSP_EXCLUDED_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/metrics")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["Referrer-Policy"] = "no-referrer"

        # CSP -- disable for Swagger UI / metrics (they need inline styles).
        if not request.url.path.startswith(_CSP_EXCLUDED_PREFIXES):
            response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response
