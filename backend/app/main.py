"""FastAPI application factory.

The module-level `app` is kept so existing process managers
(`uvicorn app.main:app`) and tests do not need to change. New code should
prefer calling `create_app()` directly — it makes the boot sequence
explicit and testable.

Boot sequence (in order):
1. Configure structured logging.
2. Build FastAPI with title/description/version from settings.
3. Attach middleware (CORS, security headers, upload-size guard).
4. Register global exception handlers from `shared.presentation`.
5. Ensure uploads directory exists (mounted as PVC in k8s).
6. Include the ``/api/v1/*`` module routers (identity, content, files, engagement).
7. Wire health-check endpoints (liveness + DB-backed readiness).
8. Expose Prometheus metrics at ``/metrics``.

`Base.metadata.create_all` is intentionally NOT called anymore — Alembic
manages the schema (`alembic upgrade head`). For local development without
Alembic, run `alembic upgrade head` once and you are set.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.config import settings
from app.shared.infrastructure.db import engine
from app.shared.infrastructure.logging import configure_logging
from app.shared.presentation import register_exception_handlers
from app.shared.presentation.middleware import (
    LimitUploadSizeMiddleware,
    SecurityHeadersMiddleware,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Best-effort: ensure the MinIO bucket exists on boot.

    In docker-compose / k8s a dedicated job creates the bucket; this is a
    convenience for plain ``uvicorn`` dev runs. Failures are non-fatal.
    """
    try:
        from app.container import get_file_storage

        await get_file_storage().ensure_bucket()
    except Exception:
        logger.warning("minio_bucket_init_failed", exc_info=True)
    yield


def create_app() -> FastAPI:
    """Build and configure a FastAPI application instance."""
    # Step 1 — logging first so subsequent imports can log.
    configure_logging(level="DEBUG" if settings.DEBUG else "INFO")

    # Step 2
    app = FastAPI(
        title=settings.APP_NAME,
        description="Fishing forum API (modular monolith, Clean Architecture).",
        version="0.3.0",
        lifespan=_lifespan,
    )

    # Step 3 — middleware (LIFO: last added = first executed).
    # 3a. CORS (must be outermost to set headers on preflight).
    # Methods/headers are restricted to exactly what the SPA uses instead of
    # the "*" wildcard — this narrows the cross-origin attack surface while
    # still covering bearer auth (Authorization) and multipart uploads.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
    )
    # 3b. Security headers (X-Frame-Options, HSTS, CSP, etc.).
    app.add_middleware(SecurityHeadersMiddleware)
    # 3c. Upload size guard — 411 / 413 before body is read.
    app.add_middleware(
        LimitUploadSizeMiddleware,
        max_upload_size=settings.MAX_UPLOAD_SIZE_BYTES,
    )

    # Step 4 — exception handlers (DomainError, validation, fallback).
    register_exception_handlers(app)

    # Step 5 — uploads directory (PVC mount in k8s).
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    # Step 6 — phase-1 identity routers (Clean Architecture, modular monolith).
    from app.modules.identity.presentation import (
        admin_users_router,
        auth_router,
        users_router,
    )

    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
    app.include_router(
        admin_users_router, prefix="/api/v1/admin/users", tags=["admin-users"]
    )

    # Step 7b — phase-2 content routers (modular monolith).
    from app.modules.content.presentation import (
        categories_router,
        comments_router,
        posts_router,
        tags_router,
    )

    app.include_router(posts_router, prefix="/api/v1/posts", tags=["posts"])
    app.include_router(
        comments_router, prefix="/api/v1/comments", tags=["comments"]
    )
    app.include_router(
        categories_router, prefix="/api/v1/categories", tags=["categories"]
    )
    app.include_router(tags_router, prefix="/api/v1/tags", tags=["tags"])

    # Step 7c — phase-3 files module (generic upload to MinIO). Mounted at
    # /api/v1 because it also serves owner-scoped routes such as
    # /api/v1/posts/{id}/files and /api/v1/users/me/avatar.
    from app.modules.files.presentation import files_router

    app.include_router(files_router, prefix="/api/v1", tags=["files"])

    # Step 7c.bis — engagement (polubienia + statystyki usera). Cienki moduł SQL;
    # mount na /api/v1 (ścieżki .../{id}/like, /users/{id}/stats).
    from app.modules.engagement.router import router as engagement_router

    app.include_router(engagement_router, prefix="/api/v1", tags=["engagement"])

    # Step 7 — health-check endpoints.
    _register_health_routes(app)

    # Step 8 — Prometheus metrics (endpoint /metrics).
    Instrumentator().instrument(app).expose(app)

    return app


def _register_health_routes(app: FastAPI) -> None:
    """Liveness and readiness probes used by Kubernetes."""

    @app.get("/", tags=["health"])
    def root() -> dict[str, str]:
        return {"status": "ok", "app": settings.APP_NAME}

    @app.get("/health", tags=["health"])
    def health_legacy() -> dict[str, str]:
        # Kept for backwards compatibility with existing probes.
        return {"status": "healthy"}

    @app.get("/health/live", tags=["health"])
    def health_live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready", tags=["health"])
    def health_ready(response: Response) -> dict[str, str]:
        # Readiness gates traffic: a pod that lost its DB must report 503 so
        # Kubernetes stops routing requests to it (liveness stays green —
        # the process is fine, only its dependency is down).
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            logger.warning("readiness_check_failed", exc_info=True)
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "not_ready", "reason": "database_unavailable"}
        return {"status": "ready"}


# Module-level ASGI app used by `uvicorn app.main:ap
app = create_app()