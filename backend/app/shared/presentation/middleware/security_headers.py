"""Security headers middleware.

Dodaje nagłówki bezpieczeństwa do każdej odpowiedzi HTTP:
- X-Frame-Options: DENY — ochrona przed click-jacking
- X-Content-Type-Options: nosniff — blokada MIME-sniffing
- Strict-Transport-Security — wymuszenie HTTPS
- Referrer-Policy: no-referrer — ograniczenie wycieku referer
- Content-Security-Policy: default-src 'self' — CSP baseline
  (wyłączony dla /docs, /openapi.json i /metrics, bo Swagger UI
  wymaga inline script/style)

Wzorowane na middleware z projektu kolegi (PythonBackendForum).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Ścieżki, na których CSP musi być luźniejszy (Swagger UI).
_CSP_EXCLUDED_PREFIXES = ("/docs", "/redoc", "/openapi.json", "/metrics")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Dodaje security headers do każdej odpowiedzi."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["Referrer-Policy"] = "no-referrer"

        # CSP — wyłącz dla Swagger UI / metrics (potrzebują inline styles).
        if not request.url.path.startswith(_CSP_EXCLUDED_PREFIXES):
            response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response
