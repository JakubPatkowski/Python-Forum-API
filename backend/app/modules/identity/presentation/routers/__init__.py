"""FastAPI routers exposed by the identity module."""

from app.modules.identity.presentation.routers.admin_users import (
    router as admin_users_router,
)
from app.modules.identity.presentation.routers.auth import router as auth_router
from app.modules.identity.presentation.routers.users import router as users_router

__all__ = ["admin_users_router", "auth_router", "users_router"]
