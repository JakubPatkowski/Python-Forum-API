"""HTTP endpoints for likes and per-user statistics.

Likes are polymorphic (post / comment) and addressed by the target's public
UUID (consistent with the rest of API v1); internally we translate UUID to the
integer primary key.

Endpoints:
* ``POST   /api/v1/{posts,comments}/{public_id}/like``  -> like (idempotent)
* ``DELETE /api/v1/{posts,comments}/{public_id}/like``  -> unlike
* ``GET    /api/v1/{posts,comments}/{public_id}/likes`` -> {count, liked}
* ``GET    /api/v1/users/{user_id}/stats``              -> stats (DB view)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.modules.files.presentation.deps import OptionalCurrentUser
from app.modules.identity.presentation.deps import CurrentUser
from app.shared.presentation.deps import DbSession

router = APIRouter()


class LikeStateResponse(BaseModel):
    count: int
    liked: bool


class MostLikedResponse(BaseModel):
    """Most popular thread (by like count). ``post_id`` is None when empty."""

    post_id: UUID | None = None
    likes: int = 0


class UserStatsResponse(BaseModel):
    posts_count: int
    comments_count: int
    likes_received: int
    joined_at: str | None = None


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

_TABLE = {"post": "posts", "comment": "comments"}


def _resolve_target_id(db: Session, target_type: str, public_id: UUID) -> int:
    """Public UUID -> internal int id (404 when missing / deleted)."""
    table = _TABLE[target_type]
    row = db.execute(
        text(
            f"SELECT id FROM {table} "  # noqa: S608 - target_type from whitelist
            "WHERE public_id = :pid AND is_deleted = false"
        ),
        {"pid": str(public_id)},
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return int(row[0])


def _user_int_id(db: Session, public_id: UUID) -> int:
    row = db.execute(
        text("SELECT id FROM users WHERE public_id = :pid"),
        {"pid": str(public_id)},
    ).first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return int(row[0])


def _like_state(
    db: Session, target_type: str, target_id: int, user_int_id: int | None
) -> LikeStateResponse:
    count = db.execute(
        text("SELECT COUNT(*) FROM reactions WHERE target_type = :tt AND target_id = :tid"),
        {"tt": target_type, "tid": target_id},
    ).scalar_one()
    liked = False
    if user_int_id is not None:
        liked = (
            db.execute(
                text(
                    "SELECT 1 FROM reactions "
                    "WHERE target_type = :tt AND target_id = :tid AND user_id = :uid"
                ),
                {"tt": target_type, "tid": target_id, "uid": user_int_id},
            ).first()
            is not None
        )
    return LikeStateResponse(count=int(count), liked=liked)


# --------------------------------------------------------------------------- #
# Like / unlike                                                               #
# --------------------------------------------------------------------------- #


def _add_like(
    db: Session, target_type: str, public_id: UUID, user: CurrentUser
) -> LikeStateResponse:
    target_id = _resolve_target_id(db, target_type, public_id)
    uid = _user_int_id(db, user.public_id)
    # ON CONFLICT DO NOTHING -> idempotent (double like does not duplicate)
    db.execute(
        text(
            "INSERT INTO reactions (user_id, target_type, target_id) "
            "VALUES (:uid, :tt, :tid) "
            "ON CONFLICT (user_id, target_type, target_id) DO NOTHING"
        ),
        {"uid": uid, "tt": target_type, "tid": target_id},
    )
    db.commit()
    return _like_state(db, target_type, target_id, uid)


def _remove_like(
    db: Session, target_type: str, public_id: UUID, user: CurrentUser
) -> LikeStateResponse:
    target_id = _resolve_target_id(db, target_type, public_id)
    uid = _user_int_id(db, user.public_id)
    db.execute(
        text(
            "DELETE FROM reactions WHERE user_id = :uid AND target_type = :tt AND target_id = :tid"
        ),
        {"uid": uid, "tt": target_type, "tid": target_id},
    )
    db.commit()
    return _like_state(db, target_type, target_id, uid)


def _read_likes(
    db: Session, target_type: str, public_id: UUID, user: OptionalCurrentUser
) -> LikeStateResponse:
    target_id = _resolve_target_id(db, target_type, public_id)
    uid = _user_int_id(db, user.public_id) if user else None
    return _like_state(db, target_type, target_id, uid)


# posts -------------------------------------------------------------------- #


@router.post("/posts/{public_id}/like", response_model=LikeStateResponse)
def like_post(public_id: UUID, db: DbSession, user: CurrentUser) -> LikeStateResponse:
    return _add_like(db, "post", public_id, user)


@router.delete("/posts/{public_id}/like", response_model=LikeStateResponse)
def unlike_post(public_id: UUID, db: DbSession, user: CurrentUser) -> LikeStateResponse:
    return _remove_like(db, "post", public_id, user)


@router.get("/posts/{public_id}/likes", response_model=LikeStateResponse)
def post_likes(public_id: UUID, db: DbSession, user: OptionalCurrentUser) -> LikeStateResponse:
    return _read_likes(db, "post", public_id, user)


# comments ----------------------------------------------------------------- #


@router.post("/comments/{public_id}/like", response_model=LikeStateResponse)
def like_comment(public_id: UUID, db: DbSession, user: CurrentUser) -> LikeStateResponse:
    return _add_like(db, "comment", public_id, user)


@router.delete("/comments/{public_id}/like", response_model=LikeStateResponse)
def unlike_comment(public_id: UUID, db: DbSession, user: CurrentUser) -> LikeStateResponse:
    return _remove_like(db, "comment", public_id, user)


@router.get("/comments/{public_id}/likes", response_model=LikeStateResponse)
def comment_likes(public_id: UUID, db: DbSession, user: OptionalCurrentUser) -> LikeStateResponse:
    return _read_likes(db, "comment", public_id, user)


# --------------------------------------------------------------------------- #
# Featured (most-liked) thread                                                #
# --------------------------------------------------------------------------- #


@router.get("/featured-post", response_model=MostLikedResponse)
def featured_post(
    db: DbSession,
    category_id: UUID | None = None,
) -> MostLikedResponse:
    """Thread with the most likes (optionally within a category).

    The path is deliberately not under ``/posts/...`` to avoid colliding with
    the content module's ``GET /posts/{id}`` route.
    """
    params: dict[str, str] = {}
    cat_clause = ""
    if category_id is not None:
        cat_clause = "AND p.category_id = (SELECT id FROM categories WHERE public_id = :cid)"
        params["cid"] = str(category_id)

    row = db.execute(
        text(
            "SELECT p.public_id, COUNT(r.id) AS likes "  # noqa: S608 - cat_clause is static
            "FROM posts p "
            "LEFT JOIN reactions r "
            "  ON r.target_type = 'post' AND r.target_id = p.id "
            f"WHERE p.is_deleted = false {cat_clause} "
            "GROUP BY p.public_id, p.created_at "
            "ORDER BY likes DESC, p.created_at DESC "
            "LIMIT 1"
        ),
        params,
    ).first()
    if row is None:
        return MostLikedResponse(post_id=None, likes=0)
    return MostLikedResponse(post_id=UUID(str(row[0])), likes=int(row[1]))


# --------------------------------------------------------------------------- #
# User stats (DB view user_stats)                                             #
# --------------------------------------------------------------------------- #


@router.get("/users/{user_id}/stats", response_model=UserStatsResponse)
def user_stats(user_id: UUID, db: DbSession) -> UserStatsResponse:
    row = db.execute(
        text(
            "SELECT posts_count, comments_count, likes_received, joined_at "
            "FROM user_stats WHERE user_public_id = :pid"
        ),
        {"pid": str(user_id)},
    ).first()
    if row is None:
        # User exists but has no row in the view = zero activity; distinguish 404.
        exists = db.execute(
            text("SELECT 1 FROM users WHERE public_id = :pid"),
            {"pid": str(user_id)},
        ).first()
        if exists is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return UserStatsResponse(posts_count=0, comments_count=0, likes_received=0)
    return UserStatsResponse(
        posts_count=int(row[0]),
        comments_count=int(row[1]),
        likes_received=int(row[2]),
        joined_at=str(row[3]) if row[3] is not None else None,
    )
