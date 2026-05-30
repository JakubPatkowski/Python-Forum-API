"""FastAPI application factory.

The module-level `app` is kept so existing process managers
(`uvicorn app.main:app`) and tests do not need to change. New code should
prefer calling `create_app()` directly — it makes the boot sequence
explicit and testable.

Boot sequence (in order):
1. Configure structured logging.
2. Build FastAPI with title/description/version from settings.
3. Attach middleware (CORS for now; security headers in phase 7).
4. Register global exception handlers from `shared.presentation`.
5. Ensure uploads directory exists (mounted as PVC in k8s).
6. Mount static files for the admin SSR panel.
7. Include routers — phase-1 ``/api/v1/*`` and legacy ``/api/*``.
8. Include admin SSR panel under `/admin`.
9. Wire health-check endpoints.

`Base.metadata.create_all` is intentionally NOT called anymore — Alembic
manages the schema (`alembic upgrade head`). For local development without
Alembic, run `alembic upgrade head` once and you are set.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.shared.infrastructure.logging import configure_logging
from app.shared.presentation import register_exception_handlers
from app.shared.presentation.middleware import (
    LimitUploadSizeMiddleware,
    SecurityHeadersMiddleware,
)


def create_app() -> FastAPI:
    """Build and configure a FastAPI application instance."""
    # Step 1 — logging first so subsequent imports can log.
    configure_logging(level="DEBUG" if settings.DEBUG else "INFO")

    # Step 2
    app = FastAPI(
        title=settings.APP_NAME,
        description="Fishing forum API (modular monolith, Clean Architecture).",
        version="0.3.0",
    )

    # Step 3 — middleware (LIFO: last added = first executed).
    # 3a. CORS (must be outermost to set headers on preflight).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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

    # Step 6 — static files for the admin SSR panel.
    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Step 7a — phase-1 identity routers (Clean Architecture, modular monolith).
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

    # Step 7c — legacy routers awaiting migration in phase 3.
    # Posts, comments and categories were retired in phase 2.
    # Attachments stays until phase 3 introduces the generic files module.
    from app.routers import admin, attachments

    app.include_router(
        attachments.router, prefix="/api/attachments", tags=["attachments"]
    )

    # Step 8 — admin SSR panel (excluded from OpenAPI schema).
    app.include_router(
        admin.router,
        prefix="/admin",
        tags=["admin-panel"],
        include_in_schema=False,
    )

    # Step 9 — health-check endpoints.
    _register_health_routes(app)

    # Step 10 — Prometheus metrics (endpoint /metrics).
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
    def health_ready() -> dict[str, str]:
        # TODO(phase 4): check DB and RabbitMQ connectivity.
        return {"status": "ready"}


# Module-level ASGI app used by `uvicorn app.main:app` and tests.
app: FastAPI = create_app()
