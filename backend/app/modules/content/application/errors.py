"""Application-level errors of the content module.

Each subclass keeps a stable ``code`` so the API can present a meaningful
machine-readable identifier in the error envelope.
"""

from __future__ import annotations

from app.shared.domain.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)


class PostNotFound(NotFoundError):
    code = "POST_NOT_FOUND"

    def __init__(self, identifier: str) -> None:
        super().__init__(f"Post {identifier!r} not found")


class CommentNotFound(NotFoundError):
    code = "COMMENT_NOT_FOUND"

    def __init__(self, identifier: str) -> None:
        super().__init__(f"Comment {identifier!r} not found")


class CategoryNotFound(NotFoundError):
    code = "CATEGORY_NOT_FOUND"

    def __init__(self, identifier: str) -> None:
        super().__init__(f"Category {identifier!r} not found")


class TagNotFound(NotFoundError):
    code = "TAG_NOT_FOUND"

    def __init__(self, identifier: str) -> None:
        super().__init__(f"Tag {identifier!r} not found")


class CategoryAlreadyExists(ConflictError):
    code = "CATEGORY_EXISTS"

    def __init__(self, name: str) -> None:
        super().__init__(f"Category {name!r} already exists", field="name")


class TagAlreadyExists(ConflictError):
    code = "TAG_EXISTS"

    def __init__(self, name: str) -> None:
        super().__init__(f"Tag {name!r} already exists", field="name")


class SlugAlreadyTaken(ConflictError):
    code = "SLUG_TAKEN"

    def __init__(self, slug: str) -> None:
        super().__init__(
            f"You already have a post with slug {slug!r}", field="slug"
        )


class NotPostOwner(PermissionDeniedError):
    code = "NOT_POST_OWNER"

    def __init__(self) -> None:
        super().__init__("Only the author or a moderator can modify this post")


class NotCommentOwner(PermissionDeniedError):
    code = "NOT_COMMENT_OWNER"

    def __init__(self) -> None:
        super().__init__(
            "Only the author or a moderator can modify this comment"
        )


class InvalidCursor(ValidationError):
    code = "INVALID_CURSOR"

    def __init__(self) -> None:
        super().__init__("Pagination cursor is malformed", field="cursor")
