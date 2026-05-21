"""Logika biznesowa komentarzy — drzewo, walidacja głębokości."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.comment import Comment
from app.models.post import Post
from app.schemas.comment import CommentCreate, CommentTreeOut


def create_comment(
    db: Session,
    data: CommentCreate,
    author_id: int,
) -> Comment:
    """Tworzy komentarz, walidując parent_id i głębokość."""
    # 1. Post musi istnieć
    post = db.query(Post).filter(Post.id == data.post_id).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post nie istnieje")

    depth = 0
    if data.parent_id is not None:
        parent = db.query(Comment).filter(Comment.id == data.parent_id).first()
        if not parent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Komentarz nadrzędny nie istnieje",
            )
        if parent.post_id != data.post_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Komentarz nadrzędny należy do innego posta",
            )
        depth = parent.depth + 1
        if depth >= settings.MAX_COMMENT_DEPTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Przekroczono maksymalną głębokość zagnieżdżenia ({settings.MAX_COMMENT_DEPTH})",
            )

    comment = Comment(
        content=data.content,
        content_format=data.content_format,
        post_id=data.post_id,
        parent_id=data.parent_id,
        depth=depth,
        author_id=author_id,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


def list_comments_tree(db: Session, post_id: int) -> list[CommentTreeOut]:
    """Zwraca komentarze danego posta jako listę drzew (top-level z dziećmi).

    Ładujemy płasko jednym zapytaniem i budujemy drzewo w pamięci — O(n).
    """
    flat: list[Comment] = (
        db.query(Comment)
        .filter(Comment.post_id == post_id)
        .order_by(Comment.created_at.asc())
        .all()
    )

    # Buduj DTO i indeksuj po id
    nodes: dict[int, CommentTreeOut] = {
        c.id: CommentTreeOut.model_validate(c) for c in flat
    }
    roots: list[CommentTreeOut] = []
    for c in flat:
        node = nodes[c.id]
        if c.parent_id is None:
            roots.append(node)
        else:
            parent = nodes.get(c.parent_id)
            if parent is not None:
                parent.children.append(node)
            else:
                # parent spoza scope (nie powinno się zdarzyć przy poprawnych danych)
                roots.append(node)
    return roots
