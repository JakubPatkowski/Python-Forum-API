"""FastAPI routers for the content module."""

from app.modules.content.presentation.routers.categories import (
    router as categories_router,
)
from app.modules.content.presentation.routers.comments import (
    router as comments_router,
)
from app.modules.content.presentation.routers.posts import (
    router as posts_router,
)
from app.modules.content.presentation.routers.tags import router as tags_router

__all__ = [
    "categories_router",
    "comments_router",
    "posts_router",
    "tags_router",
]
